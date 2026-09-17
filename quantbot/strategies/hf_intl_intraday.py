"""International-ETF intraday drift sleeve (daily timeline: long at 09:30,
explicit 0.0 row at 16:00 - flat overnight).

Hypothesis
----------
The US overnight premium has a mirror image in ETFs whose home market is
closed during US hours. EWJ (Japan) earns essentially all of its return
between the 09:30 and 16:00 New York prints (+4.3 bp/day, t 4.4, 2010-2026;
IS +4.4 t 4.2, OOS +3.9 t 1.8) and nothing overnight (-0.7 bp/day), the
opposite of SPY/QQQ (overnight +3.6 / +5.1 bp, intraday +2.2 / +2.6). The US
session 09:30-16:00 ET is 22:30-05:00 Tokyo, i.e. the Japanese market's
*overnight*, so the US-hours drift in EWJ is the home market's overnight
premium (Cooper, Cliff & Gulen 2008; Lou, Polk & Skouras 2019) harvested
through a US-listed wrapper, plus the low-beta-earns-intraday pattern of
Hendershott, Livdan & Rosch (2020). The same decomposition holds for every
Asia/Europe single-country ETF tested (overnight ~0, intraday +2.4 to +4.8
bp) but at 2 bp/side only EWJ's drift clears the round trip with a margin.

What the sleeve does
--------------------
At 09:30 of day d, hold `assets` (default: EWJ only) equal-weight (or
inverse-vol) from the open to the close; explicit 0.0 at 16:00. Optional
gates (all off by default, kept for the sensitivity tables in the notes):

* gate="trend":        close[d-1] > `ma_window`-day MA of close (through d-1)
* gate="session_down": sum of the last `trail_window` intraday returns
                       (through d-1) < 0 - the analogue of the overnight
                       sleeve's "5 weak nights" rule for the *session* return
* vix_min:             hold only when ^VIX close of d-1 > vix_min
* rv_ref:              scale by min((rv_ref / 20d realised vol)^2, 1)

Research trail (research/notes/intl_intraday.md): the unconditional EWJ
sleeve is net Sharpe ~0.55 (IS 0.65 / OOS 0.35) at 1 bp/side, breakeven
~2.1 bp/side; every gate that helps in-sample (trend) fails out-of-sample
and vice versa (VIX > 18, session_down), so the default is unconditional.
The pre-registered five-name basket (EWJ, EWT, EFA, XLP, XLU) is 0.20 net.

Causality
---------
Weights stamped 09:30 of day d use Open[d] (only for the optional
open-based trend variant; the default uses nothing from day d), Close
through d-1 for MAs / vols / trailing session returns, and ^VIX close of d-1
(shifted one day) for the optional VIX gate. Every 09:30 row is followed by
an explicit 0.0 row at 16:00 of the same day.

Implementation: market-on-open buy, market-on-close sell. EWJ is a $70-80
ETF with ~1 cent spreads (~1.3 bp full spread, ~0.7 bp half) and deep
auctions, so the 1 bp/side assumption is realistic for MOO/MOC fills.

Data requirement: EWJ is in `HF_EXTRA_ETFS`, so this sleeve needs
`MarketData(HFConfig.wide())` or `HFConfig.research()`; on the core
`HFConfig()` it raises KeyError rather than silently returning nothing.
Verdict in the notes: REJECT (allocation 0) - it is not wired into any profile.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantbot.data import MarketData

ET = "America/New_York"


@dataclass
class IntlIntradayParams:
    # ETFs held 09:30 -> 16:00. EWJ is the only name whose intraday drift
    # clears its round-trip cost with a >= 2 bp/day margin in-sample; EFA is
    # the second-best (1 bp margin) and dilutes the Sharpe (see notes).
    assets: tuple[str, ...] = ("EWJ",)
    # "eq" = 1/n per available asset, "ivol" = inverse trailing vol, normalised.
    weighting: str = "eq"
    vol_window: int = 20
    # Optional gate: "none" | "trend" | "session_down".
    gate: str = "none"
    ma_window: int = 200            # for gate="trend" (close[d-1] vs its MA)
    trail_window: int = 1           # for gate="session_down" (sessions summed)
    # Optional VIX floor on ^VIX close of d-1 (None = off). Research option:
    # the OOS drift is concentrated above 18 but the IS drift is not.
    vix_min: float | None = None
    # Optional Moreira-Muir scaling by own 20d realised variance (None = off).
    rv_ref: float | None = None
    # Hard cap on gross long exposure (cash account).
    max_gross: float = 1.0
    start: str | None = None        # optional first date of weights


def _open_weights(md: MarketData, p: IntlIntradayParams) -> pd.DataFrame:
    """Date-indexed target weights for the 09:30 -> 16:00 hold. Every input
    on row d is known at 09:30 of d (Close/Open through d-1, VIX of d-1)."""
    tickers = list(p.assets)
    missing = [t for t in tickers if t not in md.close.columns]
    if missing:
        raise KeyError(f"{missing} not in market data")
    c, o = md.close[tickers], md.open[tickers]
    avail = c.notna() & o.notna()

    on = avail.copy()
    if p.gate == "trend":
        ma = c.shift(1).rolling(p.ma_window, min_periods=p.ma_window).mean()
        on &= c.shift(1) > ma
    elif p.gate == "session_down":
        sess = (c / o - 1.0).shift(1)
        trail = sess.rolling(p.trail_window, min_periods=p.trail_window).sum()
        on &= trail < 0.0
    elif p.gate != "none":
        raise ValueError(f"unknown gate {p.gate!r}")

    if p.vix_min is not None:
        vix_prev = md.aux["^VIX"].reindex(c.index).ffill().shift(1)
        on = on.mul((vix_prev > p.vix_min).astype(bool), axis=0)

    w = on.astype(float)
    if p.weighting == "ivol":
        rv = c.pct_change(fill_method=None).rolling(p.vol_window, min_periods=p.vol_window).std().shift(1)
        inv = (1.0 / rv).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        w = w * inv
        denom = (avail.astype(float) * inv).sum(axis=1)
    elif p.weighting == "eq":
        denom = avail.astype(float).sum(axis=1)
    else:
        raise ValueError(f"unknown weighting {p.weighting!r}")
    # Normalise so the fully-on basket sums to 1; an off asset leaves cash.
    w = w.div(denom.replace(0.0, np.nan), axis=0).fillna(0.0)

    if p.rv_ref is not None:
        rv_ann = c.pct_change(fill_method=None).rolling(20, min_periods=20).std().shift(1) * np.sqrt(252)
        scale = ((p.rv_ref / rv_ann) ** 2).clip(upper=1.0).fillna(0.0)
        w = w * scale

    gross = w.sum(axis=1)
    over = gross > p.max_gross
    if over.any():
        w.loc[over] = w.loc[over].div(gross[over], axis=0) * p.max_gross
    if p.start is not None:
        w = w.loc[pd.Timestamp(p.start):]
    return w


def intl_intraday_weights(md: MarketData, p: IntlIntradayParams = IntlIntradayParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline.

    09:30 rows: basket weights (long), 16:00 rows: explicit 0.0 (flat overnight).
    """
    w_open = _open_weights(md, p)
    dates = pd.DatetimeIndex(w_open.index)
    w_open.index = (dates + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    w_close = pd.DataFrame(0.0, index=(dates + pd.Timedelta(hours=16)).tz_localize(ET),
                           columns=w_open.columns)
    out = pd.concat([w_open, w_close]).sort_index()
    return out.reindex(out.index.intersection(md.px_daily.index))
