"""Cross-asset open-to-close gap continuation in Treasury / gold ETFs
(daily timeline: position at 09:30 in the direction of the overnight gap,
explicit 0.0 row at 16:00).

Hypothesis
----------
TLT and GLD open after their primary markets (Treasury futures, London gold)
have already moved, and the US-session flows that follow (08:30 / 10:00 macro
data, rebalancing by slower macro allocators) push in the same direction.
Round 1 found gap *continuation* in TLT (t 3.0, 2010-2026) and GLD (6.8 bp/day
at |z| > 1) while equity index ETFs show none (and reverse OOS). This sleeve
trades that: at 09:30 of day d, for each basket ETF compute

    gap_d = Open[d] / Close[d-1] - 1
    z_d   = gap_d / std(gap_{d-20..d-1})          (trailing 20 gaps, through d-1)

and hold sign(gap_d) x (inverse-vol basket weight) from 09:30 to 16:00 when
|z_d| > `k` (default 1.0). Shorts are allowed (gap down -> short) because the
effect is symmetric; `long_only=True` gives the long-biased variant.

Research trail (research/notes/crossasset.md): the effect exists in TLT (all
years), weakly in GLD (2022+ mainly), and is *not* tradable in the low-vol
bond ETFs (IEF/IEI/TIP/LQD/HYG: the bp edge is below the 2 bp round trip) or
in EEM/EFA/FXI/EWJ (neither continuation nor fade). Net Sharpe of the default
is ~0.45 ex-cash with a small CAGR: a diversifier, not a return engine.

Causality
---------
Weights stamped 09:30 of day d use Open[d] (allowed: "day d's Open only"),
Close/Open through d-1 for the gap std and the vol weights, and ^VIX close of
d-1 if the optional VIX cap is on. Every 09:30 row is followed by a 0.0 row at
16:00 of the same day, so nothing is held overnight.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantbot.data import MarketData

ET = "America/New_York"


@dataclass
class CrossAssetParams:
    # Basket. TLT + GLD is the prior-driven set; IEF/IEI/TIP/LQD/HYG lose after
    # costs and EEM/EFA/FXI/EWJ show no effect (see notes).
    assets: tuple[str, ...] = ("TLT", "GLD")
    # Trade only when |gap| / trailing gap std > k. k=0 trades every day.
    k: float = 1.0
    gap_window: int = 20            # days of gaps used for the z-score std
    # "fixed": size 1 when active; "zscaled": size = min(|z|, z_cap).
    sizing: str = "fixed"
    z_cap: float = 1.0
    long_only: bool = False         # drop the short (gap-down) leg
    direction: int = 1              # +1 continuation, -1 fade (research only)
    # Basket weights: "ivol" = 1/trailing-vol normalised over the whole basket
    # (an inactive asset leaves its share in cash), "eq" = 1/n.
    weighting: str = "ivol"
    vol_window: int = 20
    # Optional regime cap: stand aside when VIX close of d-1 > vix_max. The
    # effect is concentrated in VIX <= 20 for TLT (IS and OOS) but the gain is
    # small, so off by default.
    vix_max: float | None = None
    max_gross: float = 1.0


def _open_weights(md: MarketData, p: CrossAssetParams) -> pd.DataFrame:
    """Date-indexed target weights for the 09:30 -> 16:00 hold."""
    tickers = list(p.assets)
    missing = [t for t in tickers if t not in md.close.columns]
    if missing:
        raise KeyError(f"{missing} not in market data")
    o, c = md.open[tickers], md.close[tickers]

    gap = o / c.shift(1) - 1.0
    gap_sd = gap.shift(1).rolling(p.gap_window, min_periods=p.gap_window).std()
    z = gap / gap_sd
    active = (z.abs() > p.k) & z.notna()

    if p.sizing == "fixed":
        size = active.astype(float)
    elif p.sizing == "zscaled":
        size = z.abs().clip(upper=p.z_cap) * active
    else:
        raise ValueError(f"unknown sizing {p.sizing!r}")
    w = np.sign(gap) * p.direction * size
    if p.long_only:
        w = w.clip(lower=0.0)

    if p.weighting == "ivol":
        vol = c.pct_change(fill_method=None).rolling(p.vol_window, min_periods=p.vol_window).std().shift(1)
        inv = 1.0 / vol
        w = w * inv.div(inv.sum(axis=1), axis=0)
    elif p.weighting == "eq":
        w = w / len(tickers)
    else:
        raise ValueError(f"unknown weighting {p.weighting!r}")

    if p.vix_max is not None:
        vix_prev = md.aux["^VIX"].reindex(c.index).ffill().shift(1)
        w = w.mul((vix_prev <= p.vix_max).astype(float), axis=0)

    w = w.fillna(0.0)
    gross = w.abs().sum(axis=1)
    over = gross > p.max_gross
    if over.any():
        w.loc[over] = w.loc[over].div(gross[over], axis=0) * p.max_gross
    return w


def crossasset_weights(md: MarketData, p: CrossAssetParams = CrossAssetParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline.

    09:30 rows: sign(gap) x basket weight for each active ETF (0 otherwise);
    16:00 rows: explicit 0.0 (flat overnight).
    """
    w_open = _open_weights(md, p)
    dates = pd.DatetimeIndex(w_open.index)
    w_open.index = (dates + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    w_close = pd.DataFrame(0.0, index=(dates + pd.Timedelta(hours=16)).tz_localize(ET),
                           columns=w_open.columns)
    out = pd.concat([w_open, w_close]).sort_index()
    return out.reindex(out.index.intersection(md.px_daily.index))
