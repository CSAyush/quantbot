"""Risk / regime layer for the short-horizon system (daily timeline).

This module does not hold a view on *which* asset to buy; it decides *how much*
of a risk-on sleeve to hold on a given night/day, and how a $1,000 cash
account can implement exposure above 1.0 (only via 2x/3x ETFs).

Hypothesis
----------
Index returns per unit of variance are not constant: variance is persistent
and forecastable while mean returns are not, so scaling exposure by
1 / realised variance raises the Sharpe ratio (Moreira & Muir 2017, JF).
A slow trend filter (close vs 200d MA) removes the worst left-tail regimes
(Faber 2007; Moskowitz-Ooi-Pedersen 2012) and, for overnight holds, the
overnight premium is roughly zero below the 200d MA. VIX term structure
(^VIX/^VIX3M > 1 = backwardation) flags stress (Simon & Campasano 2014) but
in-sample it is subsumed by the realised-variance rule, so it is optional.

Everything stamped on date d uses only closes/aux values through the 16:00
close of d. The multiplier for date d applies to trades executed at the
16:00 close of d and at the 09:30 open of d+1.

Public API
----------
regime_multiplier(md, p)      -> pd.Series (daily dates) in [0, p.max_mult]
vol_regime(md, p)             -> pd.Series (daily dates) of "low"/"normal"/"high"
regime_components(md, p)      -> pd.DataFrame with every intermediate signal
drawdown_throttle(daily_returns, dd_level, mult, lag=1) -> pd.Series
leverage_map(weights, mult=None, max_cash=1.0) -> pd.DataFrame (session timeline)
regime_timing_weights(md, p)  -> pd.DataFrame sleeve: QQQ sized by the multiplier,
                                 remainder in TLT or cash

Daily-rebalanced leveraged ETF arithmetic used by `leverage_map`
-----------------------------------------------------------------
A daily-rebalanced L-x fund returns L * r_t each day (minus financing and
fees). Exposure e in (1, 2] of base B is implemented as
    w_B = 2 - e,  w_2x = e - 1          (cash used = 1.0, exposure = e)
and e in (2, 3] as
    w_2x = 3 - e, w_3x = e - 2          (cash used = 1.0, exposure = e).
Over N days the fund compounds prod(1 + L r_t) rather than 1 + L * prod(1+r_t)
- 1; in log terms the difference is the "volatility decay" (L^2 - L)/2 *
sigma^2 per year (4.3%/yr for QLD at QQQ's 20.7% vol, 12.8%/yr for TQQQ).
That is a *variance* effect, not an expected-return drag: versus a
constant-leverage margin position the mean difference is ~0 (see notes).
The real costs are (a) the fund's financing + 0.9% expense ratio, which
accrues once per day and lands entirely in the overnight session (QLD
overnight alpha -1.2 bp/night 2010-26, -2.5 bp/night since 2022), and
(b) the 2 bp/side transaction cost on the leveraged line.

See research/notes/regime.md for the full research trail.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantbot.data import MarketData

ET = "America/New_York"

# base -> (2x fund, 3x fund)
LEVERAGE_FUNDS: dict[str, tuple[str, str]] = {"QQQ": ("QLD", "TQQQ"), "SPY": ("SSO", "UPRO")}


@dataclass
class RegimeParams:
    # --- trend gate: multiplier is trend_off_mult when trend_ticker < its MA ---
    trend_ticker: str = "SPY"
    trend_ma: int = 200
    trend_off_mult: float = 0.5        # 0.0 = fully flat below the MA
    # --- volatility-managed scale (Moreira & Muir): (vol_ref / realised vol)^vol_power ---
    vol_ticker: str = "QQQ"
    vol_window: int = 20
    vol_ref: float = 0.16              # annualised; scale = 1 when realised vol = vol_ref
    vol_power: float = 2.0             # 2 = 1/variance (MM), 1 = target-vol
    # --- VIX term structure (optional; off by default, subsumed by the vol rule) ---
    use_term_structure: bool = False
    backwardation_mult: float = 0.5    # applied when ^VIX/^VIX3M > 1
    # --- cap. 1.0 recommended: exposure > 1 via 2x ETFs lowered Sharpe in every test ---
    max_mult: float = 1.0
    # --- floor: keep a small live footprint even in the worst regime (0.0 = allow flat) ---
    min_mult: float = 0.1
    # --- vol regime buckets on ^VIX (for tilting between sleeves, not for sizing) ---
    vix_low: float = 15.0
    vix_high: float = 25.0
    # --- drawdown throttle defaults (generic helper) ---
    dd_level: float = 0.10
    dd_mult: float = 0.5
    # --- regime-timing sanity sleeve ---
    timing_asset: str = "QQQ"
    timing_defensive: str | None = None   # e.g. "TLT"; None = cash


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------
def regime_components(md: MarketData, p: RegimeParams = RegimeParams()) -> pd.DataFrame:
    """Every intermediate signal on the daily-date index of md.close.

    All values on row d are computable at the 16:00 close of d.
    """
    close = md.close
    idx = pd.DatetimeIndex(close.index)
    out = pd.DataFrame(index=idx)

    px = close[p.trend_ticker]
    ma = px.rolling(p.trend_ma, min_periods=p.trend_ma).mean()
    # Neutral (risk-on) while the MA is still warming up.
    out["trend_on"] = (px > ma).where(ma.notna(), True)

    rv = close[p.vol_ticker].pct_change().rolling(p.vol_window, min_periods=p.vol_window).std() * np.sqrt(252)
    out["realised_vol"] = rv
    out["vol_scale"] = ((p.vol_ref / rv) ** p.vol_power).where(rv.notna() & (rv > 0), 1.0)

    aux = md.aux.reindex(idx)
    vix = aux["^VIX"] if "^VIX" in aux else pd.Series(np.nan, index=idx)
    out["vix"] = vix
    if "^VIX3M" in aux:
        out["ts_ratio"] = vix / aux["^VIX3M"]
    else:
        out["ts_ratio"] = np.nan
    if "^VIX9D" in aux:
        out["ts_ratio_9d"] = aux["^VIX9D"] / vix
    else:
        out["ts_ratio_9d"] = np.nan
    # NaN (pre-2011 or missing print) counts as neutral = contango.
    out["contango"] = (out["ts_ratio"] < 1.0).where(out["ts_ratio"].notna(), True)

    out["vol_regime"] = np.select(
        [vix < p.vix_low, vix > p.vix_high], ["low", "high"], default="normal"
    )
    out.loc[vix.isna(), "vol_regime"] = "normal"
    return out


def regime_multiplier(md: MarketData, p: RegimeParams = RegimeParams()) -> pd.Series:
    """Exposure multiplier in [0, p.max_mult], indexed by daily dates (tz-naive).

    mult[d] = clip( trend_gate[d] * vol_scale[d] * ts_gate[d], min_mult, max_mult )
      trend_gate = 1 if trend_ticker close > MA else trend_off_mult
      vol_scale  = (vol_ref / realised_vol_20d)^2
      ts_gate    = backwardation_mult if ^VIX/^VIX3M > 1 else 1 (only if enabled)
    Uses only data through the 16:00 close of d.
    """
    c = regime_components(md, p)
    gate = np.where(c["trend_on"], 1.0, p.trend_off_mult)
    mult = c["vol_scale"] * gate
    if p.use_term_structure:
        mult = mult * np.where(c["contango"], 1.0, p.backwardation_mult)
    mult = mult.clip(lower=min(p.min_mult, p.max_mult), upper=p.max_mult).fillna(1.0)
    mult.name = "regime_mult"
    return mult


def vol_regime(md: MarketData, p: RegimeParams = RegimeParams()) -> pd.Series:
    """'low' / 'normal' / 'high' by ^VIX close (thresholds p.vix_low / p.vix_high).

    Sizing rules above *cut* exposure in high vol; reversal / intraday-momentum
    sleeves tend to earn more in high vol, so the ensemble can use this to
    tilt between sleeves rather than simply de-risking.
    """
    s = regime_components(md, p)["vol_regime"]
    s.name = "vol_regime"
    return s


def drawdown_throttle(daily_returns: pd.Series, dd_level: float = 0.10, mult: float = 0.5,
                      lag: int = 1) -> pd.Series:
    """Multiplier (1 or `mult`) indexed like `daily_returns`.

    Row d equals `mult` when the strategy's own drawdown, measured on returns
    through d - lag, is deeper than -dd_level. With lag=1 the value on date d
    uses returns through yesterday, so it is safe to apply at any session on d.
    """
    r = daily_returns.fillna(0.0)
    curve = (1.0 + r).cumprod()
    dd = curve / curve.cummax() - 1.0
    throttled = dd.shift(lag) < -abs(dd_level)
    out = pd.Series(np.where(throttled, mult, 1.0), index=r.index, name="dd_throttle")
    return out


# ---------------------------------------------------------------------------
# Cash-account leverage via 2x/3x ETFs
# ---------------------------------------------------------------------------
def _split_exposure(e: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Desired long exposure e (>= 0, capped at 3) -> (w_base, w_2x, w_3x) using
    <= 1.0 of cash. e <= 1: all base. (1,2]: base 2-e, 2x e-1. (2,3]: 2x 3-e, 3x e-2."""
    e = e.clip(lower=0.0, upper=3.0)
    w1 = e.where(e <= 1.0, (2.0 - e).clip(lower=0.0))
    w2 = pd.Series(0.0, index=e.index)
    w3 = pd.Series(0.0, index=e.index)
    mid = (e > 1.0) & (e <= 2.0)
    w2 = w2.mask(mid, e - 1.0)
    hi = e > 2.0
    w2 = w2.mask(hi, 3.0 - e)
    w3 = w3.mask(hi, e - 2.0)
    w1 = w1.mask(hi, 0.0)
    return w1, w2, w3


def _mult_on_index(mult: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Daily mult[d] -> session index: applies from the 16:00 close of d
    through the 09:30 open of d+1 (forward-filled from 16:00 stamps). Sessions
    before the first multiplier date (only the very first 09:30 row when mult
    covers md.close.index) get a neutral 1.0."""
    m = mult.astype(float).copy()
    m.index = (pd.DatetimeIndex(m.index) + pd.Timedelta(hours=16)).tz_localize(ET)
    if index.tz is not None:
        m.index = m.index.tz_convert(index.tz)
    else:
        m.index = m.index.tz_localize(None)
    return m.reindex(m.index.union(index)).ffill().reindex(index).fillna(1.0)


def leverage_map(weights: pd.DataFrame, mult: pd.Series | None = None,
                 max_cash: float = 1.0) -> pd.DataFrame:
    """Scale `weights` by the daily multiplier and implement exposure > 1.0 in
    QQQ/SPY with QLD/TQQQ and SSO/UPRO so that cash used stays <= max_cash.

    weights: session-timeline targets (index = md.px_daily.index or a subset),
             columns = tickers. Long exposure per row is what gets levered.
    mult:    optional daily-date Series (from `regime_multiplier`); if given,
             every row is multiplied by mult[d] (d = the date of the 16:00
             stamp at or before the row's timestamp).
    Desired QQQ exposure of 1.5 becomes 0.5 QQQ + 0.5 QLD (cash 1.0,
    exposure 1.5); 2.5 becomes 0.5 QLD + 0.5 TQQQ. Exposure > 3 is clipped.
    Any pre-existing weight on the leveraged fund is preserved and added to.
    If total long cash still exceeds max_cash (e.g. several sleeves all long),
    all long weights are scaled down pro rata.
    """
    w = weights.copy().astype(float)
    if mult is not None:
        w = w.mul(_mult_on_index(mult, pd.DatetimeIndex(w.index)), axis=0)

    for base, (two, three) in LEVERAGE_FUNDS.items():
        if base not in w.columns:
            continue
        e = w[base]
        over = e > 1.0 + 1e-12
        if not over.any():
            continue
        w1, w2, w3 = _split_exposure(e.where(over, 0.0))
        w[base] = e.where(~over, w1)
        for fund, add in ((two, w2), (three, w3)):
            if fund not in w.columns:
                w[fund] = 0.0
            w[fund] = w[fund].fillna(0.0) + add.where(over, 0.0)

    long_cash = w.clip(lower=0.0).sum(axis=1)
    hot = long_cash > max_cash + 1e-9
    if hot.any():
        scale = (max_cash / long_cash[hot])
        longs = w.loc[hot].clip(lower=0.0).mul(scale, axis=0)
        shorts = w.loc[hot].clip(upper=0.0)
        w.loc[hot] = longs + shorts
    return w.fillna(0.0)


# ---------------------------------------------------------------------------
# Sanity-check sleeve: regime timing of a single index ETF
# ---------------------------------------------------------------------------
def regime_timing_weights(md: MarketData, p: RegimeParams = RegimeParams()) -> pd.DataFrame:
    """Hold `p.timing_asset` at weight = regime_multiplier (rebalanced at each
    16:00 close, held through the next day) and put the remainder of the
    unit budget into `p.timing_defensive` (or cash if None). Exposure above
    1.0 (if p.max_mult > 1) is implemented with 2x/3x ETFs.
    """
    mult = regime_multiplier(md, p)
    dates = pd.DatetimeIndex(md.close.index)
    close_idx = (dates + pd.Timedelta(hours=16)).tz_localize(ET)
    w = pd.DataFrame({p.timing_asset: mult.reindex(dates).fillna(0.0).to_numpy()}, index=close_idx)
    if p.timing_defensive:
        w[p.timing_defensive] = (1.0 - w[p.timing_asset]).clip(lower=0.0)
    w = leverage_map(w, max_cash=1.0)
    for t in w.columns:
        if t in md.close.columns:
            has_px = md.close[t].reindex(dates).notna().to_numpy()
            w[t] = np.where(has_px, w[t], 0.0)
    return w.reindex(w.index.intersection(md.px_daily.index))
