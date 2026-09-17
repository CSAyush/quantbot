"""Time-series index reversal in high volatility (daily timeline, 16:00 -> 16:00).

What this sleeve does
---------------------
At the 16:00 close of day d, if the volatility regime is "stressed" (^VIX close
of d above `vix_threshold`, optionally a linear ramp) and the index ETF closed
*down* on d (close-to-close return < 0), buy it at the close and hold until the
16:00 close of d+1 (both the overnight and the intraday session). Otherwise be
flat. Default: QQQ, VIX > 20, long-only, position = min(1, 0.20 / RV20) so the
sleeve carries roughly constant risk across stress levels, one round trip per
active day (~15% of days, mean exposure 0.79 when active).

The mirror trade - short the index after an *up* day in high vol - is available
(`mode="both_inverse"` holds the inverse ETF SH/PSQ/RWM long, the cash-account
implementation; `mode="both_short"` uses negative weights, paper only) but is
OFF by default: in 2010-2026 the short half earned ~0 net and was negative
out-of-sample, so it only dilutes the long half.

Hypothesis (research/notes/ts_reversal.md, regime.md insight 2)
---------------------------------------------------------------
Next-day index reversal is a stress phenomenon: liquidity providers demand a
premium to absorb order flow when volatility is high (Nagel 2012; Hendershott &
Menkveld 2014), so the index's one-day autocorrelation is negative when VIX is
elevated and ~zero otherwise. After a down day in high vol the next-day mean
return is 20-25 bp (t ~3) split roughly evenly between the overnight and the
intraday session, versus 4-5 bp when VIX < 20; after an up day it is ~0. A
full-day hold captures both sessions for one round trip, so it is strictly
better than either session alone at a fixed per-side cost. The higher-vol
expression of the same trade (QQQ rather than SPY) earns more bp per unit of
fixed cost, which is why QQQ is the default; SPY and an equal-weight basket are
the same bet at lower Sharpe (see the notes).

Causality
---------
Everything stamped at 16:00 of d uses Close[<= d] of the tradables and ^VIX
close of d (allowed: at 16:00 you may use day d's full OHLCV and aux values).
`window="intraday"` executes at 09:30 of d+1 using only the same 16:00-of-d
information (the signal is NOT refreshed with the open; refreshing it was
tested and is worse). Weights are emitted on md.px_daily's timeline with an
explicit row at every 16:00 (0.0 when flat) so the engine's forward-fill never
carries a stale position.

Implementation notes
--------------------
* Costs: QQQ/SPY/IWM 1 bp/side; inverse ETFs 2 bp/side (`cost_bps_for`).
* Do NOT apply the risk-on regime multiplier to this sleeve (it lives in high
  vol; the multiplier would zero it exactly when it earns).
* `vol_target=0.20` scales the position by min(1, 0.20 / RV20 of the asset).
  Standalone it is roughly Sharpe-neutral (0.83 -> 0.89) and cuts MaxDD
  (-16.9% -> -13.4%); in the ensemble it is what makes the sleeve additive
  out-of-sample, because a constant-notional version adds full-size beta in
  exactly the weeks when the live reversal sleeve is already fully exposed.
  `vol_target=None` gives the constant-notional version.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantbot.data import MarketData

ET = "America/New_York"

# base index ETF -> -1x inverse fund (long-only way to hold short exposure)
INVERSE_ETF: dict[str, str] = {"SPY": "SH", "QQQ": "PSQ", "IWM": "RWM"}


@dataclass
class TSReversalParams:
    # Index ETFs traded; each gets 1/len(assets) of the sleeve when its own signal is on.
    assets: tuple[str, ...] = ("QQQ",)
    # "own": each asset trades on the sign of its own close-to-close return;
    # "SPY": every asset trades on the sign of SPY's return.
    signal_source: str = "own"
    # --- volatility regime gate (evaluated on ^VIX close of day d) ---
    gate: str = "vix"                 # "vix" (level), "vix_ma" (VIX > its own MA), "rv" (20d realised vol)
    vix_threshold: float = 20.0       # active when VIX > threshold (gate="vix")
    vix_span: float = 0.0             # > 0: linear ramp, exposure = clip((VIX - threshold)/span, 0, 1)
    vix_ma_window: int = 20           # gate="vix_ma"
    rv_threshold: float = 0.184       # gate="rv": annualised 20d realised vol of `rv_ticker` (IS 80th pct)
    rv_ticker: str = "SPY"
    rv_window: int = 20
    # --- which half of the reversal to trade ---
    mode: str = "long"                # "long": buy after down days only (cash account)
                                      # "both_inverse": + long inverse ETF after up days
                                      # "both_short": + negative weight on the base ETF (paper only)
    # --- holding window ---
    window: str = "full"              # "full" 16:00 d -> 16:00 d+1; "overnight" 16:00 -> 09:30;
                                      # "intraday" 09:30 d+1 -> 16:00 d+1 (signal from 16:00 of d)
    # --- sizing ---
    z_min: float = 0.0                # skip days with |r_d| / daily RV below this (0 = off)
    z_cap: float | None = None        # if set, weight = min(|r_d| / daily RV, z_cap) / z_cap
    vol_target: float | None = 0.20   # weight *= min(1, vol_target / RV20 of the asset); None = binary 1.0
    max_gross: float = 1.0            # hard cap on sum |weights| (cash account)
    start: str | None = None          # optional first date of weights


def _gate(md: MarketData, p: TSReversalParams, idx: pd.DatetimeIndex) -> pd.Series:
    """Exposure scale in [0, 1] known at the 16:00 close of each date."""
    if p.gate == "vix":
        vix = md.aux["^VIX"].reindex(idx)
        if p.vix_span > 0:
            g = ((vix - p.vix_threshold) / p.vix_span).clip(lower=0.0, upper=1.0)
        else:
            g = (vix > p.vix_threshold).astype(float)
        return g.where(vix.notna(), 0.0)
    if p.gate == "vix_ma":
        vix = md.aux["^VIX"].reindex(idx)
        ma = vix.rolling(p.vix_ma_window, min_periods=p.vix_ma_window).mean()
        return (vix > ma).astype(float).where(ma.notna(), 0.0)
    if p.gate == "rv":
        rv = md.close[p.rv_ticker].pct_change().rolling(p.rv_window, min_periods=p.rv_window).std() * np.sqrt(252)
        return (rv > p.rv_threshold).astype(float).where(rv.notna(), 0.0)
    raise ValueError(f"unknown gate {p.gate!r}")


def ts_reversal_signal(md: MarketData, p: TSReversalParams = TSReversalParams()) -> pd.DataFrame:
    """Signed target exposure per asset (date d -> asset), decided at 16:00 of d.

    +x = long the asset, -x = short it (implemented per `p.mode`). Uses only
    closes through d and the ^VIX close of d.
    """
    idx = pd.DatetimeIndex(md.close.index)
    gate = _gate(md, p, idx)
    out = {}
    for t in p.assets:
        if t not in md.close.columns:
            raise KeyError(f"{t} not in market data")
        c = md.close[t]
        src = md.close["SPY"] if p.signal_source == "SPY" else c
        r = src.pct_change()
        sig = -np.sign(r).fillna(0.0)                       # opposite of today's sign
        if p.mode == "long":
            sig = sig.clip(lower=0.0)
        elif p.mode not in ("both_inverse", "both_short"):
            raise ValueError(f"unknown mode {p.mode!r}")
        size = pd.Series(1.0, index=idx)
        if p.z_min > 0 or p.z_cap is not None:
            sd = r.rolling(20, min_periods=20).std()
            z = (r.abs() / sd)
            if p.z_min > 0:
                size = size * (z >= p.z_min).astype(float)
            if p.z_cap is not None:
                size = size * (z.clip(upper=p.z_cap) / p.z_cap)
            size = size.where(z.notna(), 0.0)
        if p.vol_target is not None:
            rv = c.pct_change().rolling(20, min_periods=20).std() * np.sqrt(252)
            size = size * (p.vol_target / rv).clip(upper=1.0).where(rv.notna(), 0.0)
        w = (sig * gate * size).where(c.notna(), 0.0).fillna(0.0)
        out[t] = w / len(p.assets)
    return pd.DataFrame(out, index=idx)


def ts_reversal_weights(md: MarketData, p: TSReversalParams = TSReversalParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline.

    window="full":      a row at every 16:00 (target for the next 24h; 0.0 when flat).
    window="overnight": 16:00 row = target, 09:30 row = explicit 0.0.
    window="intraday":  09:30 row of d+1 = target decided at 16:00 of d, 16:00 row = 0.0.
    Negative exposure is held as the inverse ETF (mode="both_inverse") or as a
    negative weight (mode="both_short").
    """
    expo = ts_reversal_signal(md, p)
    dates = pd.DatetimeIndex(expo.index)
    cols = list(p.assets)
    if p.mode == "both_inverse":
        cols += [INVERSE_ETF[t] for t in p.assets if t in INVERSE_ETF]
    w = pd.DataFrame(0.0, index=dates, columns=sorted(set(cols)))
    for t in p.assets:
        pos = expo[t].clip(lower=0.0)
        neg = (-expo[t]).clip(lower=0.0)
        w[t] = w[t] + pos
        if p.mode == "both_short":
            w[t] = w[t] - neg
        elif p.mode == "both_inverse":
            inv = INVERSE_ETF.get(t)
            if inv is None or inv not in md.close.columns:
                raise KeyError(f"no inverse ETF with prices for {t}")
            w[inv] = w[inv] + neg.where(md.close[inv].reindex(dates).notna(), 0.0)

    gross = w.abs().sum(axis=1)
    over = gross > p.max_gross
    if over.any():
        w.loc[over] = w.loc[over].div(gross[over], axis=0) * p.max_gross

    if p.start is not None:
        w = w.loc[pd.Timestamp(p.start):]
        dates = pd.DatetimeIndex(w.index)

    close_idx = (dates + pd.Timedelta(hours=16)).tz_localize(ET)
    open_idx = (dates + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    if p.window == "full":
        out = w.copy()
        out.index = close_idx
    elif p.window == "overnight":
        a = w.copy()
        a.index = close_idx
        b = pd.DataFrame(0.0, index=open_idx, columns=w.columns)
        out = pd.concat([a, b]).sort_index()
    elif p.window == "intraday":
        # The target decided at 16:00 of d is executed at 09:30 of the next
        # trading day and closed at that day's 16:00.
        nxt = pd.Series(dates, index=dates).shift(-1).dropna()
        a = w.loc[nxt.index].copy()
        nxt_dates = pd.DatetimeIndex(nxt.values)
        a.index = (nxt_dates + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
        b = pd.DataFrame(0.0, index=(nxt_dates + pd.Timedelta(hours=16)).tz_localize(ET), columns=w.columns)
        out = pd.concat([a, b]).sort_index()
    else:
        raise ValueError(f"unknown window {p.window!r}")
    # Only rows that exist on the price panel (guards against calendar drift).
    return out.reindex(out.index.intersection(md.px_daily.index)).fillna(0.0)
