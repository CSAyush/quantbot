"""Overfitting defenses. A backtest Sharpe means little without these.

- split_stats:        in-sample vs out-of-sample comparison on a date split
- bootstrap_sharpe_ci: block-bootstrap confidence interval for Sharpe
- deflated_sharpe:    Bailey & Lopez de Prado (2014) probability that the
                      observed Sharpe beats zero after accounting for the
                      number of strategy variants tried
- sensitivity:        run a strategy across a parameter grid; a real edge
                      degrades smoothly, an overfit one falls off a cliff
- yearly_table:       per-year returns/Sharpe so one lucky year can't hide
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from scipy import stats as sps

from .metrics import sharpe, summary

TRADING_DAYS = 252


def _rf_for(rf_annual, r: pd.Series):
    """Align a float or daily Series risk-free rate to the return slice `r`."""
    if isinstance(rf_annual, pd.Series):
        return rf_annual.reindex(r.index).ffill().fillna(0.0)
    return rf_annual


def split_stats(daily: pd.Series, split: str, label: str = "strategy", rf_annual=0.0) -> pd.DataFrame:
    """rf_annual: float, or a daily Series of annualized rates aligned to `daily`."""
    split_ts = pd.Timestamp(split)
    ins = daily.loc[:split_ts]
    oos = daily.loc[split_ts:]
    rows = []
    for name, r in [("in-sample", ins), ("out-of-sample", oos), ("full", daily)]:
        if len(r) < 20:
            continue
        s = summary(r, f"{label} {name}", rf_annual=_rf_for(rf_annual, r))
        s["days"] = len(r)
        rows.append(s)
    df = pd.DataFrame(rows).set_index("label")
    return df[["days", "cagr", "vol", "sharpe", "sortino", "max_drawdown", "calmar"]]


def bootstrap_sharpe_ci(daily: pd.Series, n_boot: int = 2000, block: int = 10,
                        alpha: float = 0.05, seed: int = 0) -> tuple[float, float, float]:
    """Stationary block bootstrap of the annualized Sharpe. Returns (lo, point, hi)."""
    r = daily.dropna().to_numpy()
    n = len(r)
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot)
    n_blocks = int(np.ceil(n / block))
    for b in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel() % n
        sample = r[idx[:n]]
        sd = sample.std()
        out[b] = sample.mean() / sd * np.sqrt(TRADING_DAYS) if sd > 0 else 0.0
    lo, hi = np.percentile(out, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(sharpe(daily)), float(hi)


def deflated_sharpe(daily: pd.Series, n_trials: int, sharpe_variance_across_trials: float | None = None) -> dict:
    """Probabilistic / Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014).

    n_trials: how many strategy variants were evaluated before picking this one.
    Returns the annualized Sharpe, the expected max Sharpe under the null given
    n_trials, and the probability the true Sharpe exceeds that benchmark.
    """
    r = daily.dropna()
    n = len(r)
    sr_daily = r.mean() / r.std() if r.std() > 0 else 0.0
    skew, kurt = r.skew(), r.kurt() + 3.0  # non-excess kurtosis
    if sharpe_variance_across_trials is None:
        # Conservative default: variance of trial Sharpes ~ that of a null strategy.
        sharpe_variance_across_trials = 1.0 / n
    euler = 0.5772156649
    v = np.sqrt(sharpe_variance_across_trials)
    n_trials = max(int(n_trials), 1)
    if n_trials == 1:
        sr0 = 0.0
    else:
        sr0 = v * ((1 - euler) * sps.norm.ppf(1 - 1.0 / n_trials)
                   + euler * sps.norm.ppf(1 - 1.0 / (n_trials * np.e)))
    denom = np.sqrt(max(1 - skew * sr_daily + (kurt - 1) / 4 * sr_daily ** 2, 1e-12))
    z = (sr_daily - sr0) * np.sqrt(n - 1) / denom
    return {
        "sharpe_annual": sr_daily * np.sqrt(TRADING_DAYS),
        "expected_max_null_sharpe_annual": sr0 * np.sqrt(TRADING_DAYS),
        "prob_sharpe_exceeds_null": float(sps.norm.cdf(z)),
        "n_trials": n_trials,
        "n_days": n,
    }


def sensitivity(run: Callable[..., pd.Series], grid: dict[str, list], base: dict | None = None,
                metric: Callable[[pd.Series], float] = sharpe) -> pd.DataFrame:
    """One-at-a-time sensitivity: for each parameter, vary it over its grid
    holding the others at `base`, and record `metric` of the returned daily
    return series. `run(**params)` must return daily returns."""
    base = dict(base or {})
    rows = []
    for name, values in grid.items():
        for v in values:
            params = dict(base)
            params[name] = v
            try:
                daily = run(**params)
                val = metric(daily)
            except Exception as exc:  # noqa: BLE001 - report, don't abort the sweep
                val = float("nan")
                print(f"[sensitivity] {name}={v} failed: {exc}")
            rows.append({"param": name, "value": v, "metric": val})
    return pd.DataFrame(rows)


def yearly_table(daily: pd.Series, rf_annual=0.0) -> pd.DataFrame:
    g = daily.groupby(daily.index.year)
    return pd.DataFrame({
        "return": g.apply(lambda r: (1 + r).prod() - 1),
        "vol": g.std() * np.sqrt(TRADING_DAYS),
        "sharpe": g.apply(lambda r: sharpe(r, _rf_for(rf_annual, r))),
        "max_dd": g.apply(lambda r: ((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min()),
        "days": g.size(),
    })


def rolling_sharpe(daily: pd.Series, window: int = 126) -> pd.Series:
    return daily.rolling(window).mean() / daily.rolling(window).std() * np.sqrt(TRADING_DAYS)
