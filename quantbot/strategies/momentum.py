"""Cross-sectional momentum.

Each day, rank the universe by trailing ~6-month return (skipping the most
recent month to sidestep short-term reversal) and hold the top N names,
weighted by inverse volatility so no single high-vol name dominates risk.
This is one of the most robust anomalies in the academic literature
(Jegadeesh & Titman 1993 and hundreds of follow-ups).
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..indicators import momentum, realized_vol


def momentum_weights(close: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    mom = momentum(close, cfg.mom_lookback, cfg.mom_skip)
    vol = realized_vol(close, cfg.vol_lookback)

    # Rank descending; keep top N each day.
    ranks = mom.rank(axis=1, ascending=False)
    selected = ranks <= cfg.mom_top_n

    inv_vol = (1.0 / vol).where(selected)
    weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
    return weights.fillna(0.0)
