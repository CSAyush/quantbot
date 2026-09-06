"""Vectorized daily backtest engine.

Assumptions (deliberately conservative):
- Signals are computed from closes through day t; trades execute at the close
  of day t (i.e. market-on-close orders submitted just before the bell).
- Every dollar of turnover pays commission + slippage.
- Long-only, no leverage, cash earns nothing.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import Config
from .indicators import returns
from .metrics import equity_curve, summary


@dataclass
class BacktestResult:
    daily_returns: pd.Series          # net of costs
    weights: pd.DataFrame
    turnover: pd.Series
    costs: pd.Series                  # daily cost drag (fraction of equity)
    equity: pd.Series
    stats: dict


def run_backtest(
    weights: pd.DataFrame,
    close: pd.DataFrame,
    cfg: Config,
    label: str = "strategy",
) -> BacktestResult:
    asset_ret = returns(close).reindex(weights.index)

    gross = (weights.shift(1) * asset_ret).sum(axis=1)

    # Uninvested cash earns the T-bill rate (e.g. parked in SGOV/BIL).
    cash_frac = (1.0 - weights.shift(1).sum(axis=1)).clip(lower=0.0, upper=1.0)
    cash_ret = cash_frac * (cfg.cash_yield_annual / 252)

    turnover = (weights - weights.shift(1)).abs().sum(axis=1).fillna(0.0)
    cost_rate = (cfg.commission_bps + cfg.slippage_bps) / 1e4
    costs = turnover * cost_rate

    net = gross + cash_ret - costs

    # Trim warmup period where no positions exist yet.
    first_active = weights.abs().sum(axis=1).gt(0).idxmax()
    net = net.loc[first_active:]
    weights = weights.loc[first_active:]
    turnover = turnover.loc[first_active:]
    costs = costs.loc[first_active:]

    stats = summary(net, label)
    stats["avg_turnover"] = turnover.mean()
    stats["annual_cost_drag"] = costs.mean() * 252

    return BacktestResult(
        daily_returns=net,
        weights=weights,
        turnover=turnover,
        costs=costs,
        equity=equity_curve(net),
        stats=stats,
    )
