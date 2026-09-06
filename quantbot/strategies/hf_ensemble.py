"""Short-horizon ensemble: combines the research sleeves and applies the
risk layer. This is the single function both the backtest and the paper
trader call, so live behaviour is the backtest by construction.

Pipeline (all causal):
  1. each sleeve -> target weights on its own timeline (daily 09:30/16:00 or hourly)
  2. reindex + forward-fill everything onto the ensemble timeline, scale by
     the sleeve's capital allocation and sum
  3. regime multiplier (VIX term structure / trend / vol) scales the
     risk-on sleeves; sleeves that thrive on volatility are left alone
  4. drawdown throttle on the ensemble's own (causal) equity curve
  5. cash-account constraint: gross long <= 1.0 of equity; desired exposure
     above that is implemented with 2x/3x ETFs via `leverage_map`
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config import PROJECT_ROOT, HFConfig
from ..data import ET, MarketData, session_dates
from ..engine import SessionResult, combine_weights, run_session_backtest
from ..research import report


DEFAULT_PROFILE = "growth"

# Risk profiles. Backtests 2010-2026 (net of costs, idle cash at the actual
# T-bill rate, Sharpe in excess of it) put all three on the same Sharpe
# plateau (~1.3); they differ only in how much of the overnight edge is
# levered through 2x/3x ETFs and how much capital the daytime reversal
# sleeve gets. Pick by drawdown tolerance.
PROFILES = {
    # Sharpe 1.28 | CAGR 10.0% | MaxDD  -9.0% | OOS(2022+) Sharpe 1.49, CAGR 15.2%
    "balanced": {"reversal_alloc": 0.5, "overnight_leverage": {}},
    # Sharpe 1.31 | CAGR 11.5% | MaxDD -12.2% | OOS Sharpe 1.53, CAGR 17.3%
    # 2x on the QQQ overnight slot; reversal held at 0.5 because its own
    # research supports only a modest allocation (see REDTEAM.md issue 5).
    "growth": {"reversal_alloc": 0.5, "overnight_leverage": {"QQQ": "QLD"}},
    # Sharpe 1.28 | CAGR 16.9% | MaxDD -14.8% | OOS Sharpe 1.43, CAGR 23.4% | 3x slot
    "max": {"reversal_alloc": 1.0, "overnight_leverage": {"QQQ": "TQQQ"}},
    # Margin account: the balanced book run at 2x gross (borrow at T-bill +
    # 1.5%). Not implementable in a cash account; exists to show what the
    # Sharpe converts to at SPY-like volatility. Needs Reg-T margin for real.
    "margin2x": {"reversal_alloc": 0.5, "overnight_leverage": {}, "gross_scale": 2.0},
    # growth with the reversal sleeve on the 300-name universe (5 bp/side on
    # names outside the core 70). Big full-sample gain that lives in the
    # illiquid tail; OOS at honest costs is a wash. Runs as a SHADOW paper
    # account until live fill quality in that tail is measured
    # (research/notes/reversal_wide.md).
    "growth-wide": {"reversal_alloc": 0.5, "overnight_leverage": {"QQQ": "QLD"}, "universe": "wide"},
}


def config_for(params: "EnsembleParams") -> HFConfig:
    """The market-data config a profile needs (core 94 names or wide 340)."""
    return HFConfig.wide() if params.universe == "wide" else HFConfig()


@dataclass
class EnsembleParams:
    # Capital allocation per sleeve (fraction of equity the sleeve may deploy
    # when fully invested). Overnight (16:00->09:30) and reversal (09:30->16:00)
    # never hold at the same time, so both can be near 1.0 without exceeding
    # the cash-account limit. The gross-long cap below is the hard limit.
    # intraday_momentum: the Gao et al. effect is absent in 2023-26 ETF data
    # and the deflated Sharpe fails (research/notes/intraday_momentum.md) ->
    # allocation 0, code kept for monitoring.
    # crossasset (TLT/GLD gap continuation, L/S): real gross edge but net
    # Sharpe 0.44 and deflated-Sharpe P=0.13 -> fails the same gate that
    # rejected intraday momentum; optional at 0 (research/notes/crossasset.md).
    # etf_reversal: negative result, not wired (research/notes/etf_reversal.md).
    alloc: dict = field(default_factory=lambda: {
        "overnight": 1.0,
        "intraday_momentum": 0.0,
        "reversal": 0.5,
        "regime_timing": 0.0,
        "crossasset": 0.0,
    })
    # Leveraged-ETF substitution inside the overnight sleeve, e.g. {"QQQ": "QLD"}.
    overnight_leverage: dict = field(default_factory=lambda: {"QQQ": "QLD"})
    # Margin: scale the whole book by this factor and allow gross long up to it.
    gross_scale: float = 1.0
    # "core" (70 mega-caps + 24 ETFs) or "wide" (300 stocks + 40 ETFs).
    universe: str = "core"
    profile: str = DEFAULT_PROFILE

    @classmethod
    def from_profile(cls, name: str = DEFAULT_PROFILE) -> "EnsembleParams":
        if name not in PROFILES:
            raise ValueError(f"unknown profile {name!r}; choose from {sorted(PROFILES)}")
        spec = PROFILES[name]
        p = cls(profile=name)
        p.alloc["reversal"] = spec["reversal_alloc"]
        p.overnight_leverage = dict(spec["overnight_leverage"])
        p.gross_scale = spec.get("gross_scale", 1.0)
        p.universe = spec.get("universe", "core")
        if p.gross_scale > 1.0:
            p.max_gross_long_cash = p.gross_scale
            p.max_exposure = p.gross_scale
            p.use_leverage_map = False   # real margin, no ETF substitution
        return p
    # Which sleeves the regime multiplier scales (risk-on sleeves).
    regime_scaled: tuple = ("overnight", "regime_timing")
    use_regime: bool = True
    use_leverage_map: bool = True
    max_exposure: float = 1.5          # cap on total *exposure* (incl. via leveraged ETFs)
    max_gross_long_cash: float = 1.0   # cash-account hard limit on dollars deployed
    dd_throttle_level: float = 0.10    # cut exposure in half below this drawdown
    dd_throttle_mult: float = 0.5
    # Every variant evaluated across all research agents (286 overnight + 525
    # intraday momentum + 190 regime + reversal), used for the deflated Sharpe.
    n_trials_total: int = 1200


def _daily_to_sessions(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Map a daily (date-indexed) series to session stamps: value for date d
    applies from the 16:00 close of d until the next 16:00 close."""
    s = series.copy()
    s.index = (pd.DatetimeIndex(s.index) + pd.Timedelta(hours=16)).tz_localize(ET)
    return s.reindex(index.union(s.index)).ffill().reindex(index)


def sleeve_weights(md: MarketData, timeline: str, params: EnsembleParams) -> dict[str, pd.DataFrame]:
    """Compute every active sleeve's weights on its native timeline."""
    from .hf_overnight import OvernightParams, overnight_weights
    sleeves: dict[str, pd.DataFrame] = {}
    if params.alloc.get("overnight", 0) > 0:
        sleeves["overnight"] = overnight_weights(
            md, OvernightParams(leverage_map=dict(params.overnight_leverage)))
    if params.alloc.get("reversal", 0) > 0:
        from .hf_reversal import reversal_weights
        sleeves["reversal"] = reversal_weights(md)
    if params.alloc.get("regime_timing", 0) > 0:
        from .hf_regime import regime_timing_weights
        sleeves["regime_timing"] = regime_timing_weights(md)
    if params.alloc.get("crossasset", 0) > 0:
        from .hf_crossasset import crossasset_weights
        sleeves["crossasset"] = crossasset_weights(md)
    if timeline == "hourly" and md.px_intraday is not None and params.alloc.get("intraday_momentum", 0) > 0:
        from .hf_intraday_momentum import intraday_momentum_weights
        sleeves["intraday_momentum"] = intraday_momentum_weights(md)
    return sleeves


def hf_ensemble_weights(md: MarketData, timeline: str = "hourly",
                        params: EnsembleParams | None = None) -> pd.DataFrame:
    params = params or EnsembleParams()
    if timeline == "hourly" and md.px_intraday is None:
        timeline = "daily"
    px = md.px_intraday if timeline == "hourly" else md.px_daily
    index = px.index

    sleeves = sleeve_weights(md, timeline, params)
    if not sleeves:
        raise ValueError("no sleeves active")

    # Regime multiplier applied to risk-on sleeves only.
    if params.use_regime:
        from .hf_regime import regime_multiplier
        mult_daily = regime_multiplier(md)
        mult = _daily_to_sessions(mult_daily, index).fillna(1.0)
        for name in params.regime_scaled:
            if name in sleeves:
                w = sleeves[name].reindex(index).ffill().fillna(0.0)
                sleeves[name] = w.mul(mult, axis=0)

    weights = combine_weights(sleeves, params.alloc, index)
    weights = weights.reindex(columns=[c for c in weights.columns if c in px.columns]).fillna(0.0)
    if params.gross_scale != 1.0:
        weights = weights * params.gross_scale

    # Drawdown throttle on the pre-throttle ensemble (uses returns through the
    # previous session only).
    if params.dd_throttle_level:
        asset_ret = px[weights.columns].ffill().pct_change(fill_method=None).fillna(0.0)
        base = (weights.shift(1).fillna(0.0) * asset_ret).sum(axis=1)
        curve = (1.0 + base).cumprod()
        dd = curve / curve.cummax() - 1.0
        throttled = (dd.shift(1) < -params.dd_throttle_level).astype(float)
        weights = weights.mul(np.where(throttled > 0, params.dd_throttle_mult, 1.0), axis=0)

    # Exposure cap, then implement >1x with leveraged ETFs (or clip if disabled).
    long_expo = weights.clip(lower=0.0).sum(axis=1)
    over = long_expo > params.max_exposure
    if over.any():
        weights.loc[over] = weights.loc[over].div(long_expo[over], axis=0) * params.max_exposure
    if params.use_leverage_map:
        from .hf_regime import leverage_map
        weights = leverage_map(weights, max_cash=params.max_gross_long_cash)
    long_cash = weights.clip(lower=0.0).sum(axis=1)
    over = long_cash > params.max_gross_long_cash + 1e-9
    if over.any():
        weights.loc[over] = weights.loc[over].div(long_cash[over], axis=0) * params.max_gross_long_cash

    return weights.fillna(0.0)


def run_hf_backtest(cfg: HFConfig, timeline: str = "daily", refresh: bool = False,
                    plot: bool = False, sleeves: bool = False, n_trials: int | None = None,
                    params: EnsembleParams | None = None, profile: str | None = None) -> SessionResult:
    params = params or EnsembleParams.from_profile(profile or DEFAULT_PROFILE)
    if params.universe != "core":
        cfg = config_for(params)
    md = MarketData(cfg, refresh=refresh, intraday=(timeline == "hourly"))
    px = md.px_intraday if timeline == "hourly" else md.px_daily
    split = "2025-09-01" if timeline == "hourly" else "2022-01-01"
    bench = md.close["SPY"].pct_change()

    rf = md.cash_yield(cfg.cash_yield_annual)   # historical T-bill yield, not a flat 4%
    weights = hf_ensemble_weights(md, timeline=timeline, params=params)
    res = run_session_backtest(weights, px, cash_yield_annual=rf,
                               borrow_bps_annual=cfg.borrow_bps_annual,
                               label=f"HF {params.profile} ({timeline})")
    print(f"\nHF ensemble backtest, profile '{params.profile}', {timeline} timeline: "
          f"{res.daily_returns.index[0].date()} -> {res.daily_returns.index[-1].date()}")
    report(res, split=split, n_trials=n_trials or params.n_trials_total, benchmark_daily=bench)

    spy_w = pd.DataFrame(1.0, index=px.index, columns=["SPY"])
    spy_res = run_session_backtest(spy_w, px, label="SPY buy&hold", cost_bps=0.0, cash_yield_annual=rf,
                                   start=res.session_returns.index[0])
    print(spy_res)

    if sleeves:
        print("\nStandalone sleeves (same timeline, same costs):")
        for name, w in sleeve_weights(md, timeline, params).items():
            r = run_session_backtest(w, px, cash_yield_annual=rf,
                                     borrow_bps_annual=cfg.borrow_bps_annual, label=name,
                                     start=res.session_returns.index[0])
            print(r)
            corr = r.daily_returns.corr(res.daily_returns.reindex(r.daily_returns.index))
            print(f"    corr with ensemble {corr:.2f} | corr with SPY "
                  f"{r.daily_returns.corr(bench.reindex(r.daily_returns.index)):.2f}")

    if plot:
        _plot(res, spy_res, timeline)
    return res


def _plot(res: SessionResult, spy_res: SessionResult, timeline: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(11, 9.5), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1, 1]})
    eq = (1 + res.daily_returns).cumprod()
    beq = (1 + spy_res.daily_returns).cumprod().reindex(eq.index).ffill()
    axes[0].plot(eq.index, eq.values, label=res.label, lw=1.6)
    axes[0].plot(beq.index, beq.values, label="SPY buy & hold", lw=1.1, alpha=0.8)
    axes[0].set_yscale("log"); axes[0].set_ylabel("Growth of $1 (log)"); axes[0].legend(); axes[0].grid(alpha=0.3)
    dd = eq / eq.cummax() - 1; bdd = beq / beq.cummax() - 1
    axes[1].fill_between(dd.index, dd.values, 0, alpha=0.6, label="ensemble")
    axes[1].fill_between(bdd.index, bdd.values, 0, alpha=0.3, label="SPY")
    axes[1].set_ylabel("Drawdown"); axes[1].legend(); axes[1].grid(alpha=0.3)
    gross = res.weights.abs().sum(axis=1)
    dates = session_dates(gross.index)
    g_daily = gross.groupby(dates).max()
    axes[2].plot(g_daily.index, g_daily.values, lw=0.8)
    axes[2].set_ylabel("Max gross / day"); axes[2].grid(alpha=0.3)
    out = PROJECT_ROOT / f"hf_backtest_{res.label.split()[1]}_{timeline}.png"
    fig.tight_layout(); fig.savefig(out, dpi=130)
    print(f"\nSaved chart: {out}")
