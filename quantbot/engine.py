"""Session-based backtest engine for the short-horizon system.

The engine is timeline-agnostic: `prices` is a DataFrame indexed by execution
timestamps (e.g. 09:30 and 16:00 each day, or hourly bar ends) and `weights`
gives the *target* portfolio weight of each asset immediately after trading at
that timestamp. Weights set at time t earn the asset return from t to the next
timestamp. Negative weights are short positions.

Conventions (deliberately conservative):
- Fill price = the panel price at that timestamp (auction print for open/close).
- Every dollar traded pays a per-asset cost in bps (half-spread + slippage).
- Idle cash earns `cash_yield_annual`, pro-rated by wall-clock time between
  sessions (so weekends earn 3 days of interest, an intraday hour earns ~0).
- Short proceeds earn nothing; shorts pay `borrow_bps_annual`.
- Turnover is drift-adjusted: the pre-trade weight is last session's weight
  scaled by the asset's return relative to the portfolio's.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import cost_bps_for
from .data import session_dates
from .metrics import equity_curve, summary

DAYS_PER_YEAR = 365.25


@dataclass
class SessionResult:
    label: str
    session_returns: pd.Series          # net, per session
    daily_returns: pd.Series            # net, compounded per calendar day
    weights: pd.DataFrame               # post-trade weights per session
    turnover: pd.Series                 # sum |dw| per session
    costs: pd.Series                    # cost drag per session (fraction of equity)
    equity: pd.Series                   # growth of $1 per session
    rf_daily: pd.Series | None = None   # annualized risk-free rate per calendar day
    stats: dict = field(default_factory=dict)

    @property
    def excess_daily(self) -> pd.Series:
        """Daily returns in excess of the risk-free rate (what Sharpe is built on)."""
        if self.rf_daily is None:
            return self.daily_returns
        return self.daily_returns - self.rf_daily.reindex(self.daily_returns.index).fillna(0.0) / 252.0

    def __repr__(self) -> str:
        return format_hf_summary(self.stats)


def _ts(x, tz) -> pd.Timestamp:
    t = pd.Timestamp(x)
    if t.tz is None and tz is not None:
        t = t.tz_localize(tz)
    return t


def _cost_vector(columns: pd.Index, cost_bps) -> pd.Series:
    if cost_bps is None:
        return pd.Series([cost_bps_for(t) for t in columns], index=columns) / 1e4
    if isinstance(cost_bps, (int, float)):
        return pd.Series(float(cost_bps), index=columns) / 1e4
    if isinstance(cost_bps, dict):
        return pd.Series([cost_bps.get(t, cost_bps_for(t)) for t in columns], index=columns) / 1e4
    return pd.Series(cost_bps).reindex(columns).fillna(3.0) / 1e4


def _rf_per_session(cash_yield_annual, index: pd.DatetimeIndex) -> pd.Series:
    """Annualized cash yield at each session stamp. Accepts a float or a daily
    (date-indexed, percent-or-fraction) Series such as ^IRX; the rate on date d
    applies from d's 16:00 close onward."""
    if isinstance(cash_yield_annual, (int, float)):
        return pd.Series(float(cash_yield_annual), index=index)
    s = pd.Series(cash_yield_annual).dropna().astype(float)
    if s.median() > 1.0:          # ^IRX is quoted in percent
        s = s / 100.0
    s.index = (pd.DatetimeIndex(s.index) + pd.Timedelta(hours=16))
    if index.tz is not None:
        s.index = s.index.tz_localize(index.tz)
    return s.reindex(s.index.union(index)).ffill().reindex(index).bfill().fillna(0.0)


def run_session_backtest(
    weights: pd.DataFrame,
    prices: pd.DataFrame,
    cost_bps=None,
    cash_yield_annual=0.04,
    borrow_bps_annual: float = 50.0,
    margin_spread_annual: float = 0.015,
    label: str = "strategy",
    start=None,
    end=None,
) -> SessionResult:
    """cash_yield_annual may be a float or a daily Series (e.g. ^IRX).
    Long exposure above 1.0 is financed at cash_yield + margin_spread_annual."""
    prices = prices.sort_index()
    if start is not None:
        prices = prices.loc[_ts(start, prices.index.tz):]
    if end is not None:
        prices = prices.loc[:_ts(end, prices.index.tz)]

    cols = [c for c in weights.columns if c in prices.columns]
    dropped = set(weights.columns) - set(cols)
    if dropped:
        print(f"[engine] dropping weights for assets without prices: {sorted(dropped)}")
    px = prices[cols].ffill()
    # Targets are held until the next explicit target; missing => flat.
    w = weights[cols].reindex(px.index).ffill().fillna(0.0)
    # Cannot hold an asset before it has a price.
    w = w.where(px.notna(), 0.0)

    asset_ret = px.pct_change(fill_method=None).fillna(0.0)
    w_prev = w.shift(1).fillna(0.0)
    gross_ret = (w_prev * asset_ret).sum(axis=1)

    # Drift-adjusted pre-trade weights -> turnover -> costs.
    w_pre = w_prev * (1.0 + asset_ret)
    w_pre = w_pre.div((1.0 + gross_ret).replace(0.0, np.nan), axis=0).fillna(0.0)
    dw = (w - w_pre)
    turnover = dw.abs().sum(axis=1)
    costs = (dw.abs() * _cost_vector(pd.Index(cols), cost_bps)).sum(axis=1)

    # Time-proportional carry on cash and shorts.
    dt_years = pd.Series(px.index, index=px.index).diff().dt.total_seconds().fillna(0.0) / (86400 * DAYS_PER_YEAR)
    long_expo = w_prev.clip(lower=0.0).sum(axis=1)
    short_expo = (-w_prev.clip(upper=0.0)).sum(axis=1)
    cash_frac = (1.0 - long_expo).clip(lower=0.0)
    borrowed = (long_expo - 1.0).clip(lower=0.0)          # margin debit
    rf = _rf_per_session(cash_yield_annual, px.index)
    rf_prev = rf.shift(1).bfill()
    carry = (cash_frac * rf_prev * dt_years
             - borrowed * (rf_prev + margin_spread_annual) * dt_years
             - short_expo * (borrow_bps_annual / 1e4) * dt_years)

    net = gross_ret + carry - costs

    # Trim warm-up before the first non-zero target. Nothing is held before
    # the first trade, but its entry cost is real.
    active = w.abs().sum(axis=1).gt(0)
    if not active.any():
        raise ValueError("weights are all zero")
    first = active.idxmax()
    net, w, turnover, costs = net.loc[first:], w.loc[first:], turnover.loc[first:], costs.loc[first:]
    net.iloc[0] = -costs.iloc[0]

    dates = session_dates(net.index)
    daily = (1.0 + net).groupby(dates).prod() - 1.0
    daily.index = pd.DatetimeIndex(daily.index)
    rf_daily = rf.loc[first:].groupby(dates).last()
    rf_daily.index = pd.DatetimeIndex(rf_daily.index)

    # Sharpe/Sortino are excess of the cash yield the engine credits, so a
    # sleeve that sits in cash 80% of the time gets no free ratio boost.
    stats = summary(daily, label, rf_annual=rf_daily)
    stats["rf_annual"] = float(rf_daily.mean())
    stats.update(_extra_stats(net, daily, w, turnover, costs))
    return SessionResult(
        label=label, session_returns=net, daily_returns=daily, weights=w,
        turnover=turnover, costs=costs, equity=equity_curve(net), rf_daily=rf_daily, stats=stats,
    )


def _extra_stats(net: pd.Series, daily: pd.Series, w: pd.DataFrame,
                 turnover: pd.Series, costs: pd.Series) -> dict:
    n_days = max(len(daily), 1)
    years = n_days / 252.0
    gross_long = w.clip(lower=0.0).sum(axis=1)
    gross_short = (-w.clip(upper=0.0)).sum(axis=1)
    pos_days = daily[daily > 0]
    neg_days = daily[daily < 0]
    tstat = daily.mean() / daily.std() * np.sqrt(n_days) if daily.std() > 0 else np.nan
    return {
        "n_days": n_days,
        "n_sessions": len(net),
        "tstat": tstat,
        "skew": daily.skew(),
        "kurtosis": daily.kurt(),
        "best_day": daily.max(),
        "worst_day": daily.min(),
        "profit_factor": pos_days.sum() / abs(neg_days.sum()) if len(neg_days) and neg_days.sum() != 0 else np.nan,
        "avg_long": gross_long.mean(),
        "avg_short": gross_short.mean(),
        "time_in_market": (w.abs().sum(axis=1) > 0).mean(),
        "turnover_per_day": turnover.sum() / n_days,
        "annual_cost_drag": costs.sum() / years if years > 0 else np.nan,
        "trades_per_day": (w.diff().abs() > 1e-9).sum(axis=1).sum() / n_days,
    }


def format_hf_summary(s: dict) -> str:
    return (
        f"{s['label']:<18} | CAGR {s['cagr']:>7.2%} | Vol {s['vol']:>6.2%} | Sharpe {s['sharpe']:>5.2f} | "
        f"Sortino {s['sortino']:>5.2f} | MaxDD {s['max_drawdown']:>7.2%} | Calmar {s['calmar']:>5.2f} | "
        f"t {s.get('tstat', float('nan')):>5.2f} | PF {s.get('profit_factor', float('nan')):>4.2f} | "
        f"exp L/S {s.get('avg_long', 0):.2f}/{s.get('avg_short', 0):.2f} | "
        f"cost/yr {s.get('annual_cost_drag', 0):.2%} | days {s.get('n_days', 0)}"
    )


def yearly_returns(daily: pd.Series) -> pd.Series:
    return (1.0 + daily).groupby(daily.index.year).prod() - 1.0


def combine_weights(sleeves: dict[str, pd.DataFrame], allocations: dict[str, float],
                    index: pd.DatetimeIndex) -> pd.DataFrame:
    """Sum sleeve weights (each reindexed+ffilled onto `index`) times allocation."""
    total = None
    for name, w in sleeves.items():
        a = allocations.get(name, 0.0)
        if a == 0.0:
            continue
        wi = w.reindex(index).ffill().fillna(0.0) * a
        total = wi if total is None else total.add(wi, fill_value=0.0)
    return total.fillna(0.0) if total is not None else pd.DataFrame(0.0, index=index, columns=[])
