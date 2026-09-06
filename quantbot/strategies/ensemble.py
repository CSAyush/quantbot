"""Ensemble portfolio construction with risk overlays.

Blends the three sleeves (momentum / trend / mean reversion), then applies,
in order:
  1. per-name weight cap
  2. market regime filter  - cut gross exposure when SPY is below its 200d MA
  3. drawdown throttle     - cut exposure after the strategy itself draws down
  4. volatility targeting  - scale exposure so trailing portfolio vol ~ target

Every overlay only uses information available strictly before the day the
weights are applied (enforced with shift), so there is no lookahead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config
from ..indicators import TRADING_DAYS, returns, sma
from .mean_reversion import mean_reversion_weights
from .momentum import momentum_weights
from .trend import trend_weights


def _cap_and_renormalize(weights: pd.DataFrame, cap: float) -> pd.DataFrame:
    """Cap single-name weight; excess is dropped to cash (no renorm above cap)."""
    return weights.clip(upper=cap)


def ensemble_weights(
    close: pd.DataFrame,
    benchmark_close: pd.Series,
    cfg: Config,
) -> pd.DataFrame:
    w_mom = momentum_weights(close, cfg)
    w_tr = trend_weights(close, cfg)
    w_mr = mean_reversion_weights(close, cfg)

    # Slow sleeves (momentum, trend) only rebalance every N days; holding the
    # weights between rebalances cuts turnover dramatically at almost no cost
    # to signal quality. Mean reversion stays daily - speed is its edge.
    slow = cfg.w_momentum * w_mom + cfg.w_trend * w_tr
    rebal_mask = pd.Series(False, index=slow.index)
    rebal_mask.iloc[:: cfg.rebalance_days] = True
    slow = slow.where(rebal_mask).ffill().fillna(0.0)

    weights = slow + cfg.w_meanrev * w_mr
    weights = _cap_and_renormalize(weights, cfg.max_weight)

    # --- Regime filter: defensive when the index is below its long MA ---
    bench_ma = benchmark_close.rolling(cfg.regime_ma, min_periods=cfg.regime_ma).mean()
    risk_on = (benchmark_close > bench_ma).reindex(weights.index).ffill()
    regime_mult = risk_on.map({True: 1.0, False: cfg.defensive_exposure}).fillna(1.0)
    weights = weights.mul(regime_mult, axis=0)

    # --- Base strategy returns (pre-scaling) for the overlays below ---
    asset_ret = returns(close)
    base_ret = (weights.shift(1) * asset_ret).sum(axis=1)

    # --- Drawdown throttle (causal: uses curve through yesterday) ---
    curve = (1.0 + base_ret.fillna(0.0)).cumprod()
    dd = curve / curve.cummax() - 1.0
    throttled = (dd.shift(1) < -cfg.dd_throttle)
    dd_mult = np.where(throttled, cfg.dd_exposure, 1.0)
    weights = weights.mul(pd.Series(dd_mult, index=weights.index), axis=0)

    # --- Volatility targeting (causal: trailing vol through yesterday) ---
    # The raw daily scale is noisy; smoothing it with an EMA avoids re-trading
    # the entire book every day just because measured vol wiggled.
    scaled_ret = (weights.shift(1) * asset_ret).sum(axis=1)
    port_vol = scaled_ret.rolling(cfg.vol_lookback).std() * np.sqrt(TRADING_DAYS)
    scale = (cfg.target_vol / port_vol.shift(1)).clip(upper=cfg.max_leverage)
    scale = scale.ewm(span=10).mean().fillna(1.0).clip(upper=cfg.max_leverage)
    weights = weights.mul(scale, axis=0)

    # Long-only sanity: gross exposure can never exceed max_leverage.
    gross = weights.sum(axis=1)
    over = gross > cfg.max_leverage
    weights.loc[over] = weights.loc[over].div(gross[over], axis=0) * cfg.max_leverage

    return weights.fillna(0.0)
