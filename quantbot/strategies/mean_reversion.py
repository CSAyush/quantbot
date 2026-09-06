"""Short-term mean reversion with explicit entry/exit holding logic.

Enter quality names (above their long-term MA, i.e. still in an uptrend) when
they become sharply oversold (deep negative short-window z-score). Hold until
the stretch closes (z back above exit level) or a time stop hits. Capacity is
capped at mr_top_n concurrent positions, prioritized by how oversold they are.

The stateful loop matters: re-selecting a fresh oversold basket every day (the
naive vectorized version) churns the whole sleeve daily and dies to costs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config
from ..indicators import sma, zscore


def mean_reversion_weights(close: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    z = zscore(close, cfg.mr_lookback)
    uptrend = close > sma(close, cfg.trend_slow)

    enter_sig = ((z < cfg.mr_zscore_entry) & uptrend).to_numpy()
    exit_sig = (z > cfg.mr_zscore_exit).to_numpy()
    zv = z.to_numpy()

    n_days, n_assets = zv.shape
    w = np.zeros((n_days, n_assets))
    holding = np.zeros(n_assets, dtype=bool)
    age = np.zeros(n_assets, dtype=int)

    for t in range(n_days):
        age[holding] += 1
        stale = age >= cfg.mr_max_hold
        holding &= ~(exit_sig[t] | stale)

        capacity = cfg.mr_top_n - int(holding.sum())
        if capacity > 0:
            candidates = np.where(enter_sig[t] & ~holding)[0]
            if candidates.size:
                # Most oversold first.
                best = candidates[np.argsort(zv[t, candidates])][:capacity]
                holding[best] = True
                age[best] = 0

        if holding.any():
            w[t, holding] = 1.0 / cfg.mr_top_n

    return pd.DataFrame(w, index=close.index, columns=close.columns)
