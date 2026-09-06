"""Performance metrics for daily return series."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def equity_curve(daily_returns: pd.Series, initial: float = 1.0) -> pd.Series:
    return initial * (1.0 + daily_returns.fillna(0.0)).cumprod()


def cagr(daily_returns: pd.Series) -> float:
    curve = equity_curve(daily_returns)
    years = len(curve) / TRADING_DAYS
    if years <= 0 or curve.iloc[-1] <= 0:
        return float("nan")
    return curve.iloc[-1] ** (1.0 / years) - 1.0


def annual_vol(daily_returns: pd.Series) -> float:
    return daily_returns.std() * np.sqrt(TRADING_DAYS)


def sharpe(daily_returns: pd.Series, rf_annual: float = 0.0) -> float:
    excess = daily_returns - rf_annual / TRADING_DAYS
    vol = excess.std()
    if vol == 0 or np.isnan(vol):
        return float("nan")
    return excess.mean() / vol * np.sqrt(TRADING_DAYS)


def sortino(daily_returns: pd.Series, rf_annual: float = 0.0) -> float:
    excess = daily_returns - rf_annual / TRADING_DAYS
    downside = excess[excess < 0].std()
    if downside == 0 or np.isnan(downside):
        return float("nan")
    return excess.mean() / downside * np.sqrt(TRADING_DAYS)


def max_drawdown(daily_returns: pd.Series) -> float:
    curve = equity_curve(daily_returns)
    return (curve / curve.cummax() - 1.0).min()


def summary(daily_returns: pd.Series, label: str = "strategy", rf_annual: float = 0.0) -> dict:
    """rf_annual: risk-free rate subtracted for Sharpe/Sortino. Pass the cash
    yield the backtest credits on idle cash, otherwise low-exposure strategies
    get a free Sharpe boost from interest."""
    mdd = max_drawdown(daily_returns)
    c = cagr(daily_returns)
    return {
        "label": label,
        "cagr": c,
        "vol": annual_vol(daily_returns),
        "sharpe": sharpe(daily_returns, rf_annual),
        "sortino": sortino(daily_returns, rf_annual),
        "rf_annual": rf_annual,
        "max_drawdown": mdd,
        "calmar": c / abs(mdd) if mdd < 0 else float("nan"),
        "win_rate": (daily_returns > 0).mean(),
        "total_return": equity_curve(daily_returns).iloc[-1] - 1.0,
    }


def format_summary(stats: dict) -> str:
    return (
        f"{stats['label']:<12} | CAGR {stats['cagr']:>7.2%} | Vol {stats['vol']:>6.2%} | "
        f"Sharpe {stats['sharpe']:>5.2f} | Sortino {stats['sortino']:>5.2f} | "
        f"MaxDD {stats['max_drawdown']:>7.2%} | Calmar {stats['calmar']:>5.2f} | "
        f"Total {stats['total_return']:>8.2%}"
    )
