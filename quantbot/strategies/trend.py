"""Time-series trend following.

Hold a name only while it is in a confirmed uptrend (price above slow MA and
fast MA above slow MA). Position size is inverse-volatility so risk is spread
evenly across whatever is trending. When few names trend, the strategy
naturally holds cash - that is its defensive value in bear markets.
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..indicators import realized_vol, sma


def trend_weights(close: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    fast = sma(close, cfg.trend_fast)
    slow = sma(close, cfg.trend_slow)
    in_trend = (close > slow) & (fast > slow)

    vol = realized_vol(close, cfg.vol_lookback)
    inv_vol = (1.0 / vol).where(in_trend)

    total = inv_vol.sum(axis=1)
    weights = inv_vol.div(total, axis=0)

    # Scale exposure by breadth: if only a handful of names trend, don't pile
    # the whole book into them - keep the rest in cash.
    breadth = in_trend.sum(axis=1) / close.shape[1]
    exposure = breadth.clip(upper=1.0) ** 0.5  # concave: 25% breadth -> 50% exposure
    weights = weights.mul(exposure, axis=0)
    return weights.fillna(0.0)
