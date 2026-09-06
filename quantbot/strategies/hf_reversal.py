"""Cross-sectional short-term reversal in mega-caps (daily timeline, intraday hold).

What this sleeve does
---------------------
At 09:30 of day d it ranks the 70 mega-caps by their *overnight gap*
(close[d-1] -> open[d]), beta-adjusted for the average gap of the universe and
scaled by each name's trailing daily volatility. It buys the `n` biggest
gap-down names (default "long" mode; "ls" mode also shorts the `n` biggest
gap-up names, "hedged" shorts SPY against the long leg) and is flat again at
the 16:00 close. Exposure is scaled by the prior day's VIX close: zero
at/below `vix_floor`, full at `vix_floor + vix_span`.

Default mode is "long": the short (gap-up winners) leg earned its keep in
2010-2021 but not out-of-sample (2022+), while the long leg's edge over the
equal-weight universe is stable across the split. See the notes for numbers.

Why this design (see research/notes/reversal.md for the full trail)
--------------------------------------------------------------------
* The classic close-to-close reversal (Lehmann 1990, Jegadeesh 1990) does NOT
  survive 2.5 bp/side in this universe: long-only losers underperform the
  equal-weight universe, and the market-neutral version is negative net.
* Reversal is an intraday phenomenon (Bogousslavsky 2021; Lou, Polk &
  Skouras 2019): a gap at the open partly fades during the same session.
  Holding losers overnight adds nothing but cost.
* Residual (beta-adjusted) and vol-scaled signals rank better than raw
  returns (Blitz, Huij, Lansdorp & Verbeek 2013).
* Reversal profits are compensation for liquidity provision and rise with
  VIX (Nagel 2012). Below VIX ~18 the gross fade (~4-5 bp/day on the L/S
  book) does not cover the 5 bp round trip, so the sleeve stays in cash.

Causality
---------
Weights stamped 09:30 of day d use: Open[d] of the tradables (allowed by the
brief: "day d's Open only"), Close/Open through d-1 for betas and vols, and
^VIX close of d-1. Every 09:30 row is followed by an explicit 0.0 row at
16:00 of the same day, so nothing is held overnight.

Implementation caveat: the signal uses the 09:30 auction print and the fill
is assumed at that same print. Live, compute the gap from the pre-market
quote at ~09:28 and send market-on-open orders.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantbot.data import MarketData

ET = "America/New_York"


@dataclass
class ReversalParams:
    n: int = 7                      # names per leg
    mode: str = "long"              # "long": long losers 1.0 (cash-account friendly)
                                    # "ls": long losers 0.5 / short winners 0.5
                                    # "hedged": long losers 0.5 / short SPY 0.5
    weighting: str = "eq"           # "eq" or "ivol" (inverse trailing vol)
    residual: bool = True           # subtract beta * universe-average gap
    zscore: bool = True             # divide by trailing daily vol
    beta_window: int = 60           # days, beta of daily returns to SPY
    vol_window: int = 20            # days, trailing std of daily returns
    vix_floor: float = 18.0         # exposure 0 when VIX(d-1) <= floor
    vix_span: float = 10.0          # full exposure at floor + span (linear ramp)
    skip_abs_gap: float | None = None  # drop names with |gap| above this (news gaps)
    start: str | None = None        # optional first date of weights
    # --- breadth options (research/notes/reversal_wide.md); None = legacy behaviour ---
    universe: tuple[str, ...] | None = None   # restrict to these stocks (subset of md.stocks())
    top_liquidity: int | None = None          # keep only the K most liquid names each day, by
    liq_window: int = 60                      #   trailing median dollar volume (Close*Volume) to d-1
    frac: float | None = None                 # if set, n = max(1, round(frac * names ranked that day))


def _gap_signal(md: MarketData, p: ReversalParams) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (signal, gap, vol) indexed by trading day, columns = stocks.
    Everything is known at 09:30 of the row's date."""
    st = md.stocks()
    if p.universe is not None:
        keep = set(p.universe)
        st = [s for s in st if s in keep]
    close, open_ = md.close[st], md.open[st]
    r1 = close.pct_change(fill_method=None)
    gap = open_ / close.shift(1) - 1.0
    if p.top_liquidity is not None:
        # Liquidity screen known at 09:30 of d: median dollar volume over the
        # liq_window sessions ending d-1. Names outside the top-K are dropped
        # before the universe-average gap is formed.
        dvol = (close * md.daily["Volume"][st]).rolling(
            p.liq_window, min_periods=int(p.liq_window * 0.75)).median().shift(1)
        liquid = dvol.rank(axis=1, ascending=False) <= p.top_liquidity
        gap = gap.where(liquid)
    vol = r1.rolling(p.vol_window, min_periods=int(p.vol_window * 0.75)).std().shift(1)

    sig = gap.copy()
    if p.residual:
        rspy = md.close["SPY"].pct_change(fill_method=None)
        mp = int(p.beta_window * 0.66)
        beta = r1.rolling(p.beta_window, min_periods=mp).cov(rspy).div(
            rspy.rolling(p.beta_window, min_periods=mp).var(), axis=0).shift(1)
        mkt_gap = gap.mean(axis=1)
        sig = gap.sub(beta.mul(mkt_gap, axis=0))
    if p.zscore:
        sig = sig / vol
    if p.skip_abs_gap is not None:
        sig = sig.where(gap.abs() <= p.skip_abs_gap)
    return sig, gap, vol


def _leg(mask: pd.DataFrame, weighting: str, vol: pd.DataFrame) -> pd.DataFrame:
    m = mask.astype(float)
    if weighting == "ivol":
        m = m * (1.0 / vol).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return m.div(m.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)


def reversal_weights(md: MarketData, p: ReversalParams = ReversalParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline: a row at 09:30 (enter) and an
    explicit all-zero row at 16:00 (exit) for every trading day."""
    sig, gap, vol = _gap_signal(md, p)

    if p.frac is None:
        n = p.n
    else:
        n = (p.frac * sig.notna().sum(axis=1)).round().clip(lower=1)
    losers = sig.rank(axis=1, ascending=True).le(n, axis=0)
    long_w = _leg(losers, p.weighting, vol)
    if p.mode == "ls":
        winners = sig.rank(axis=1, ascending=False).le(n, axis=0)
        w = 0.5 * long_w - 0.5 * _leg(winners, p.weighting, vol)
    elif p.mode == "hedged":
        w = 0.5 * long_w
        w["SPY"] = -0.5 * (long_w.sum(axis=1) > 0).astype(float)
    elif p.mode == "long":
        w = long_w
    else:
        raise ValueError(f"unknown mode {p.mode!r}")

    # Nagel (2012): scale with (lagged) VIX; the ramp avoids a cliff at one level.
    vix = md.aux["^VIX"].reindex(w.index).ffill().shift(1)
    scale = ((vix - p.vix_floor) / p.vix_span).clip(lower=0.0, upper=1.0).fillna(0.0)
    w = w.mul(scale, axis=0)

    if p.start is not None:
        w = w.loc[pd.Timestamp(p.start):]

    days = pd.DatetimeIndex(w.index)
    enter = w.copy()
    enter.index = (days + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    exit_ = pd.DataFrame(0.0, index=(days + pd.Timedelta(hours=16)).tz_localize(ET), columns=w.columns)
    out = pd.concat([enter, exit_]).sort_index().fillna(0.0)
    return out.reindex(out.index.intersection(md.px_daily.index))
