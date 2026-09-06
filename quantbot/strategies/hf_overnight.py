"""Overnight-premium sleeve (daily timeline: long at 16:00, flat at 09:30).

Hypothesis
----------
The equity premium in index ETFs accrues disproportionately overnight
(Cooper/Cliff/Gulen; Lou, Polk & Skouras 2019; Bogousslavsky 2021). Since
2010 the *unconditional* overnight premium in SPY barely covers 1 bp/side
costs, so this sleeve (a) picks the ETFs whose overnight premium is largest
per unit of cost (QQQ, SMH, IWM) and (b) conditions on two cheap, causal
signals evaluated at the 16:00 close:

1. Trend gate: close > N-day moving average of close (default 200d).
   Below the MA the overnight premium is ~zero in-sample and negative
   out-of-sample (2022 bear market).
2. Short-term overnight reversal: the sum of the last `on_window` overnight
   returns (close[d-k] -> open[d-k+1], all known by 16:00 of day d) is below
   `on_threshold` (default 0). After a run of weak nights the next night's
   mean return is ~3x larger; after strong nights it is roughly zero.

Both conditions must hold for an ETF to be held that night. Weights are
equal (1/len(assets)); an ETF whose signal is off contributes 0 (cash).
Nothing here uses any data stamped after the 16:00 decision timestamp.

See research/notes/overnight.md for the full research trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quantbot.data import MarketData

ET = "America/New_York"


@dataclass
class OvernightParams:
    # ETFs held overnight; each gets 1/len(assets) of the sleeve when its signal is on.
    assets: tuple[str, ...] = ("QQQ", "SMH", "IWM")
    # Trend gate: close must be above its own `ma_window`-day simple MA.
    require_trend: bool = True
    ma_window: int = 200
    # Overnight-reversal gate: trailing sum of the last `on_window` overnight
    # returns must be < on_threshold.
    require_on_reversal: bool = True
    on_window: int = 5
    on_threshold: float = 0.0
    # Optional: substitute a leveraged ETF for an asset's slot (same weight, 2x
    # exposure), e.g. {"QQQ": "QLD"}. Adds CAGR at ~equal ex-cash Sharpe and
    # ~1.5x the drawdown; off by default.
    leverage_map: dict[str, str] = field(default_factory=dict)
    # Optional inverse-realized-vol scaling of each slot (None = off). Lowers
    # vol/MaxDD but does not improve the ex-cash Sharpe, so off by default.
    vol_target: float | None = None
    vol_window: int = 20
    vol_cap: float = 1.0
    # Hard cap on gross long exposure (cash account).
    max_gross: float = 1.0


def _signals(md: MarketData, ticker: str, p: OvernightParams) -> pd.Series:
    """Boolean Series (date -> hold tonight?) using only data through that
    day's 16:00 close."""
    c = md.close[ticker]
    o = md.open[ticker]
    ok = c.notna()
    if p.require_trend:
        ma = c.rolling(p.ma_window, min_periods=p.ma_window).mean()
        ok &= c > ma
    if p.require_on_reversal:
        # Overnight return that *ended* at today's open: close[d-1] -> open[d].
        on_prev = o / c.shift(1) - 1.0
        trail = on_prev.rolling(p.on_window, min_periods=p.on_window).sum()
        ok &= trail < p.on_threshold
    return ok.fillna(False)


def overnight_weights(md: MarketData, p: OvernightParams = OvernightParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline.

    16:00 rows: 1/len(assets) in each ETF whose signal is on (0 otherwise),
    09:30 rows: explicit 0.0 (flat during the day).
    """
    dates = pd.DatetimeIndex(md.close.index)
    slot = 1.0 / len(p.assets)
    held = {}
    for t in p.assets:
        target = p.leverage_map.get(t, t)
        if target not in md.close.columns:
            raise KeyError(f"{target} not in market data")
        w = _signals(md, t, p).astype(float) * slot
        if p.vol_target is not None:
            rv = md.close[t].pct_change().rolling(p.vol_window).std() * np.sqrt(252)
            scale = (p.vol_target / rv).clip(upper=p.vol_cap)
            w = (w * scale).fillna(0.0)
        # Cannot hold the (possibly leveraged) target before it has a price.
        w = w.where(md.close[target].notna(), 0.0)
        held[target] = held.get(target, 0.0) + w
    w_close = pd.DataFrame(held, index=dates).fillna(0.0)

    gross = w_close.sum(axis=1)
    over = gross > p.max_gross
    if over.any():
        w_close.loc[over] = w_close.loc[over].div(gross[over], axis=0) * p.max_gross

    close_idx = (dates + pd.Timedelta(hours=16)).tz_localize(ET)
    open_idx = (dates + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    w_close.index = close_idx
    w_open = pd.DataFrame(0.0, index=open_idx, columns=w_close.columns)
    out = pd.concat([w_close, w_open]).sort_index()
    # Only rows that exist on the price panel (guards against calendar drift).
    return out.reindex(out.index.intersection(md.px_daily.index))
