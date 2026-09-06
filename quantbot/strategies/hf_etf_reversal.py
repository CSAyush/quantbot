"""Cross-sectional short-term reversal among equity ETFs (daily timeline).

RESULT: NEGATIVE. This sleeve is implemented so the finding is reproducible
and so the ensemble can monitor it, but its recommended allocation is 0.
See research/notes/etf_reversal.md for the full trail (n_trials = 145).

What it does
------------
Universe: 25 equity ETFs (11 sector SPDRs, 6 industry ETFs, 8 broad/regional
index ETFs). No leveraged, bond or commodity ETFs. Two signal families:

* ``signal="multiday"`` (default): at 16:00 of day d rank the ETFs by their
  ``lookback``-day return *relative to SPY* (beta-adjusted, optionally
  z-scored by trailing vol); go long the ``k`` biggest relative losers and,
  in ``mode="ls"``, short the ``k`` biggest relative winners. The book is
  held ``hold`` days as ``hold`` overlapping tranches of 1/``hold`` each
  (the classic Jegadeesh-Titman construction), which cuts turnover to
  ~1/``hold`` of a full book per day.
* ``signal="gap"``: at 09:30 of day d rank by the overnight gap
  (close[d-1] -> open[d]) relative to SPY's gap, hold 09:30 -> 16:00, flat
  overnight (an explicit 0.0 row is emitted at 16:00).

Modes: ``"ls"`` (0.5 long / 0.5 short, dollar-neutral), ``"long"`` (long
losers, sum 1.0), ``"hedged"`` (0.5 long losers / 0.5 short SPY). Optional
VIX ramp gate (``vix_floor``/``vix_span``, off by default) and
inverse-vol weighting.

Why it does not work (short version)
------------------------------------
Single-name short-term reversal is a liquidity-provision return on
idiosyncratic order flow (Nagel 2012). ETF prices are arbitraged to their
baskets, so an ETF's relative move is almost entirely *information* about
its sector/region, not inventory pressure - and sector/industry returns
exhibit *momentum*, not reversal, at weekly-monthly horizons (Moskowitz &
Grinblatt 1999). The long-short book is ~0 gross Sharpe at every horizon
(1-20 days), in both sessions (overnight / intraday), for every ranking
variant, and no gate (VIX, dispersion) finds a sub-sample with enough edge
to pay 1 bp/side. The long-only variant is just equity beta with -35 to -45%
drawdowns and a Sharpe below SPY buy & hold.

Causality
---------
16:00 rows of day d use Close through d (and ^VIX close of d). 09:30 rows of
day d use Open[d], Close/Open through d-1, betas/vols through d-1 and ^VIX
close of d-1.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantbot.data import MarketData

ET = "America/New_York"

ETF_REVERSAL_UNIVERSE: tuple[str, ...] = (
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLC", "XLRE", "XLB",   # sectors
    "SMH", "KRE", "XBI", "IBB", "ARKK", "VNQ",                                       # industries
    "IWM", "DIA", "QQQ", "SPY", "EEM", "EFA", "FXI", "EWJ",                          # broad / regions
)


@dataclass
class EtfReversalParams:
    universe: tuple[str, ...] = ETF_REVERSAL_UNIVERSE
    signal: str = "multiday"        # "multiday" (16:00 -> hold `hold` days) or "gap" (09:30 -> 16:00)
    lookback: int = 5               # formation window in days (multiday only)
    hold: int = 5                   # holding period in days = number of overlapping tranches (multiday only)
    k: int = 3                      # ETFs per leg
    mode: str = "ls"                # "ls": long losers 0.5 / short winners 0.5
                                    # "long": long losers 1.0
                                    # "hedged": long losers 0.5 / short SPY 0.5
    weighting: str = "eq"           # "eq" or "ivol" (inverse trailing vol)
    residual: bool = True           # subtract beta * SPY return (else raw return)
    zscore: bool = True             # divide by trailing vol * sqrt(lookback)
    beta_window: int = 60           # days, beta of daily returns to SPY
    vol_window: int = 20            # days, trailing std of daily returns
    vix_floor: float | None = None  # if set: exposure = clip((VIX - floor) / span, 0, 1)
    vix_span: float = 10.0
    start: str | None = None        # optional first date of weights


def _ranked_universe(md: MarketData, p: EtfReversalParams) -> list[str]:
    return [t for t in p.universe if t in md.close.columns]


def _signal(md: MarketData, p: EtfReversalParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(signal, vol) indexed by trading day, columns = universe minus SPY.

    multiday: everything on the row for day d is known at 16:00 of d.
    gap:      everything on the row for day d is known at 09:30 of d.
    """
    u = _ranked_universe(md, p)
    close, open_ = md.close[u], md.open[u]
    r1 = close.pct_change(fill_method=None)
    rspy = md.close["SPY"].pct_change(fill_method=None)
    vol = r1.rolling(p.vol_window, min_periods=int(p.vol_window * 0.75)).std()
    mp = int(p.beta_window * 0.66)
    beta = r1.rolling(p.beta_window, min_periods=mp).cov(rspy).div(
        rspy.rolling(p.beta_window, min_periods=mp).var(), axis=0)

    if p.signal == "gap":
        ret = open_ / close.shift(1) - 1.0
        ret_spy = ret["SPY"]
        beta, vol, horizon = beta.shift(1), vol.shift(1), 1
    elif p.signal == "multiday":
        L = p.lookback
        lr = np.log1p(r1)
        ret = np.expm1(lr.rolling(L, min_periods=L).sum())
        ret_spy = np.expm1(np.log1p(rspy).rolling(L, min_periods=L).sum())
        horizon = L
    else:
        raise ValueError(f"unknown signal {p.signal!r}")

    sig = ret.sub(beta.mul(ret_spy, axis=0)) if p.residual else ret
    if p.zscore:
        sig = sig / (vol * np.sqrt(horizon))
    return sig.drop(columns=["SPY"]), vol


def _leg(mask: pd.DataFrame, weighting: str, vol: pd.DataFrame) -> pd.DataFrame:
    m = mask.astype(float)
    if weighting == "ivol":
        m = m * (1.0 / vol.reindex(columns=m.columns)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return m.div(m.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)


def etf_reversal_weights(md: MarketData, p: EtfReversalParams = EtfReversalParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline (sum |w| <= 1)."""
    u = _ranked_universe(md, p)
    sig, vol = _signal(md, p)

    losers = sig.rank(axis=1, ascending=True) <= p.k
    long_w = _leg(losers, p.weighting, vol)
    if p.mode == "ls":
        winners = sig.rank(axis=1, ascending=False) <= p.k
        w = 0.5 * long_w - 0.5 * _leg(winners, p.weighting, vol)
    elif p.mode == "hedged":
        w = 0.5 * long_w
        w["SPY"] = -0.5 * (long_w.sum(axis=1) > 0).astype(float)
    elif p.mode == "long":
        w = long_w
    else:
        raise ValueError(f"unknown mode {p.mode!r}")
    w = w.reindex(columns=u).fillna(0.0)

    if p.vix_floor is not None:
        # At 16:00 of d the VIX close of d is known; at 09:30 only d-1's is.
        lag = 1 if p.signal == "gap" else 0
        vix = md.aux["^VIX"].reindex(w.index).ffill().shift(lag)
        scale = ((vix - p.vix_floor) / p.vix_span).clip(lower=0.0, upper=1.0).fillna(0.0)
        w = w.mul(scale, axis=0)

    days = pd.DatetimeIndex(w.index)
    open_idx = (days + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    close_idx = (days + pd.Timedelta(hours=16)).tz_localize(ET)
    if p.signal == "gap":
        enter = w.copy(); enter.index = open_idx
        exit_ = pd.DataFrame(0.0, index=close_idx, columns=u)
        out = pd.concat([enter, exit_])
    else:
        if p.hold > 1:
            # `hold` overlapping tranches, each 1/hold of the book, formed on consecutive days.
            w = w.rolling(p.hold, min_periods=1).mean()
        out = w.copy(); out.index = close_idx

    out = out.sort_index().fillna(0.0)
    if p.start is not None:
        out = out.loc[pd.Timestamp(p.start, tz=ET):]
    return out.reindex(out.index.intersection(md.px_daily.index))
