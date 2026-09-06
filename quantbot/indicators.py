"""Vectorized indicator helpers. All functions take/return DataFrames indexed
by date with one column per ticker, and only use information available up to
each row (no lookahead)."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def returns(close: pd.DataFrame, periods: int = 1) -> pd.DataFrame:
    return close.pct_change(periods, fill_method=None)


def sma(close: pd.DataFrame, window: int) -> pd.DataFrame:
    return close.rolling(window, min_periods=window).mean()


def momentum(close: pd.DataFrame, lookback: int, skip: int) -> pd.DataFrame:
    """Total return over [t-lookback, t-skip]; skipping the most recent days
    avoids the well-documented short-term reversal effect."""
    return close.shift(skip) / close.shift(lookback) - 1.0


def zscore(close: pd.DataFrame, window: int) -> pd.DataFrame:
    """Z-score of price vs its recent window (short-horizon stretch measure)."""
    m = close.rolling(window, min_periods=window).mean()
    s = close.rolling(window, min_periods=window).std()
    return (close - m) / s.replace(0.0, np.nan)


def realized_vol(close: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Annualized realized volatility from daily returns."""
    return returns(close).rolling(window, min_periods=window).std() * np.sqrt(TRADING_DAYS)
