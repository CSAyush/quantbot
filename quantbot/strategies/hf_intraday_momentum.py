"""Market intraday momentum / last-half-hour sleeve (hourly timeline).

Literature: Gao, Han, Li & Zhou (2018, JFE) show that SPY's first half-hour
return (measured from the previous close, so it includes the overnight gap)
positively predicts the last half-hour return; Baltussen, Da, Lammers &
Martens (2021, JFE) confirm it in global index futures and attribute it to
leveraged-ETF rebalancing and dealer gamma hedging.

What we actually find on hourly data 2023-10 -> 2026-09 (see
research/notes/intraday_momentum.md): the last-half-hour *continuation* of the
morning move is gone in US index ETFs (sign(r_first) earns ~0 bp). Two things
do survive:

1. Last-half-hour REVERSAL of the day's intraday move: the 15:30 -> 16:00
   return moves against the 09:30 -> 15:30 return, ~2-3 bp/day gross,
   consistent across SPY/QQQ/IWM/DIA/SMH and in/out of sample. Gross is at or
   just above the 2 bp round-trip cost, so it is only a marginal day trade
   (ex-cash net Sharpe ~0.3 at 1 bp/side, ~0.7-0.9 if the 16:00 exit is a
   free MOC fill).
2. In this sample the first-hour move predicts the *overnight* leg (15:30 ->
   next 09:30): SPY earns ~10.6 bp when r_first > 0 vs ~2 bp when r_first < 0
   (ex-cash Sharpe ~1.9). BUT the 16-year daily analog (gap sign -> next
   overnight return) has the OPPOSITE sign in 2010-2023 (t = -5.7), so this is
   a 2023-26 regime artefact and is NOT the default.

The default parameters implement (1) long-only (long the basket into the
close when the intraday move is down, flat otherwise). (2) is available via
`signal="first", direction=1, exit="next_open"`.

Causality: a weight stamped at 15:30 of day d uses only prices with stamps
<= 15:30 of day d, the previous day's close, daily closes through d-1 for the
trailing vol estimate, and the VIX close of day d-1 (the VIX daily print is
16:15 ET, so day d's value is not yet known at 15:30).

Half days (no 15:30 bar) are skipped. Weights sum to <= max_gross in absolute
value; leverage only via the leveraged ETF tickers if requested.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..data import MarketData, session_dates

ET = "America/New_York"


@dataclass
class IntradayMomentumParams:
    tickers: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "IWM", "SMH"])
    # Signal measured at 15:30 of day d:
    #   "first":            P(10:30)/P(prev 16:00) - 1   (first hour incl. overnight gap; Gao et al.)
    #   "open":             P(10:30)/P(09:30) - 1        (first hour ex gap)
    #   "gap":              P(09:30)/P(prev 16:00) - 1   (overnight gap only)
    #   "day_so_far":       P(15:30)/P(prev 16:00) - 1
    #   "intraday_so_far":  P(15:30)/P(09:30) - 1
    #   "h1330":            P(13:30)/P(12:30) - 1        (the 12:30-13:30 hour)
    signal: str = "intraday_so_far"
    direction: int = -1             # +1 = trade with the signal (momentum), -1 = against it (reversal)
    entry: str = "1530"             # "1530" (market order at the 15:30 print) or "1600" (closing auction)
    exit: str = "close"             # "close" (16:00 same day), "next_open" (09:30 d+1), "next_1030" (10:30 d+1)
    long_only: bool = True          # if True: long when signal says long, else flat (no shorts)
    threshold_z: float = 0.0        # trade only if |signal| > threshold_z * trailing daily vol (0 = always)
    vol_lookback: int = 20          # days of close-to-close returns for the vol estimate
    sizing: str = "fixed"           # "fixed" = max_gross split equally; "zscaled" = |signal|/vol capped at 1
    zscale_cap: float = 1.0
    vol_filter: str = "none"        # "none", "vix_above_median" (expanding median of prior VIX), "vix_above_20", "rv_above_median"
    max_gross: float = 1.0


def _stamp_table(px: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """date x time-of-day price table (columns p0930, p1030, ..., p1600) + p_prev."""
    s = px[ticker].dropna()
    tod = s.index.tz_convert(ET).strftime("%H%M")
    df = pd.DataFrame({"px": s.to_numpy(), "date": session_dates(s.index), "tod": tod})
    wide = df.pivot(index="date", columns="tod", values="px")
    wide.columns = [f"p{c}" for c in wide.columns]
    for c in ("p0930", "p1030", "p1230", "p1330", "p1530", "p1600"):
        if c not in wide.columns:
            wide[c] = np.nan
    wide["p_prev"] = wide["p1600"].shift(1)
    return wide


def _signal(w: pd.DataFrame, name: str) -> pd.Series:
    if name == "first":
        return w["p1030"] / w["p_prev"] - 1.0
    if name == "open":
        return w["p1030"] / w["p0930"] - 1.0
    if name == "gap":
        return w["p0930"] / w["p_prev"] - 1.0
    if name == "day_so_far":
        return w["p1530"] / w["p_prev"] - 1.0
    if name == "intraday_so_far":
        return w["p1530"] / w["p0930"] - 1.0
    if name == "h1330":
        return w["p1330"] / w["p1230"] - 1.0
    raise ValueError(f"unknown signal {name!r}")


def _regime_ok(md: MarketData, dates: pd.DatetimeIndex, w: pd.DataFrame, p: IntradayMomentumParams) -> pd.Series:
    ok = pd.Series(True, index=dates)
    if p.vol_filter == "none":
        return ok
    if p.vol_filter.startswith("vix"):
        vix = md.aux["^VIX"].copy()
        vix.index = pd.DatetimeIndex(vix.index).normalize()
        vix_prev = vix.shift(1).reindex(dates)          # day d-1 close is the latest known at 15:30 of d
        if p.vol_filter == "vix_above_20":
            return (vix_prev > 20.0).fillna(False)
        if p.vol_filter == "vix_above_median":
            med = vix.shift(1).expanding(min_periods=250).median().reindex(dates)
            return (vix_prev > med).fillna(False)
    if p.vol_filter == "rv_above_median":
        cc = w["p1600"].pct_change()
        rv = cc.rolling(p.vol_lookback).std().shift(1)   # through d-1
        med = rv.expanding(min_periods=120).median()
        return (rv > med).fillna(False)
    raise ValueError(f"unknown vol_filter {p.vol_filter!r}")


def intraday_momentum_weights(md: MarketData, p: IntradayMomentumParams = IntradayMomentumParams()) -> pd.DataFrame:
    px = md.px_intraday
    tickers = [t for t in p.tickers if t in px.columns]
    if not tickers:
        raise ValueError("no requested tickers in px_intraday")
    per_asset = p.max_gross / len(tickers)

    rows: dict[pd.Timestamp, dict[str, float]] = {}

    def put(ts: pd.Timestamp, ticker: str, value: float) -> None:
        rows.setdefault(ts, {})[ticker] = value

    # Full-day session dates and the stamps we need (15:30 entry; 16:00 / next 09:30 / next 10:30 exit).
    all_dates = pd.DatetimeIndex(sorted(set(session_dates(px.index))))
    next_date = pd.Series(all_dates, index=all_dates).shift(-1)

    def stamp(date, hh, mm) -> pd.Timestamp:
        return (pd.Timestamp(date) + pd.Timedelta(hours=hh, minutes=mm)).tz_localize(ET)

    for tk in tickers:
        w = _stamp_table(px, tk)
        sig = _signal(w, p.signal)
        # Trailing daily vol from closes through d-1 (used for threshold / sizing).
        vol = w["p1600"].pct_change().rolling(p.vol_lookback).std().shift(1)
        ok = _regime_ok(md, w.index, w, p)
        full_day = w["p1530"].notna() & w["p1600"].notna() & w["p_prev"].notna()

        z = sig / vol
        raw_dir = np.sign(sig) * p.direction
        tradeable = full_day & sig.notna() & (raw_dir != 0) & ok
        if p.threshold_z > 0:
            tradeable &= z.abs() > p.threshold_z
        if p.long_only:
            tradeable &= raw_dir > 0

        if p.sizing == "zscaled":
            size = (z.abs() / p.zscale_cap).clip(upper=1.0).fillna(0.0)
        else:
            size = pd.Series(1.0, index=w.index)
        target = (raw_dir * size * per_asset).where(tradeable, 0.0)

        if p.entry == "1600" and p.exit == "close":
            raise ValueError("entry='1600' requires an overnight exit")
        for d in w.index[full_day.to_numpy()]:
            entry = stamp(d, 15, 30) if p.entry == "1530" else stamp(d, 16, 0)
            if entry not in px.index:
                continue
            wt = float(target.loc[d])
            put(entry, tk, wt)
            if p.exit == "close":
                put(stamp(d, 16, 0), tk, 0.0)
            else:
                nd = next_date.get(d)
                if pd.isna(nd):
                    continue
                hh, mm = (9, 30) if p.exit == "next_open" else (10, 30)
                ex = stamp(nd, hh, mm)
                if ex not in px.index:        # e.g. data gap; fall back to next available stamp
                    later = px.index[px.index > entry]
                    if len(later) == 0:
                        continue
                    ex = later[0]
                put(ex, tk, 0.0)

    weights = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    weights = weights.reindex(columns=tickers).fillna(0.0)
    weights = weights.loc[weights.index.isin(px.index)]
    return weights
