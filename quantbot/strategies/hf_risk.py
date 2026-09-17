"""Risk sizing and allocation tools for the short-horizon ensemble.

Pure functions only: nothing here touches market data, the ensemble or any
sleeve file, and nothing is wired into `hf_ensemble_weights`. The research
that uses them (and the resulting recommendation) is in
research/notes/risk_allocation.md; the scratch pipeline that applied them to
the live 'growth' profile lives outside the repo.

Three groups:

1. Sizing helpers (daily-date Series in, daily-date Series out)
   - realised_vol / trailing_vol       annualised rolling vol, causal lag
   - vol_target_scale                  min(cap, (target / RV)^power), Moreira-Muir when power = 2
   - ramp_exposure                     the reversal sleeve's clip((VIX - floor) / span, 0, 1)
   - reversal_vol_sizing               VIX-gated vol-targeted exposure for the gap-fade sleeve
   - rv_tilt                           multiply an exposure series by (ref / RV)^power, capped
   - book_intraday_returns             09:30 -> 16:00 return of a per-date weight book
   - scale_by_date                     apply a per-date factor to a session-timeline weight matrix
2. Ensemble-level vol targeting (session timeline)
   - ensemble_vol_scale                scale-down-only multiplier from the book's own causal returns
3. Combination tools (dict / DataFrame of daily *excess* returns)
   - sharpe_ratio, sharpe_table, naive_sharpe_bound
   - max_sharpe_weights (no-short QP), inverse_vol_weights, sharpe_proportional_weights
   - combine_max_sharpe, combination_report

Causality conventions
---------------------
A value stamped on date d in a *daily* series is computable at the 16:00
close of d. `lag=1` therefore means "known at 09:30 of d" (returns through
d-1). `daily_to_sessions` maps a daily series onto the 09:30/16:00 timeline
with the same convention `hf_ensemble` uses for the regime multiplier: the
value for d applies from the 16:00 close of d until the next 16:00 close.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quantbot.data import session_dates

ET = "America/New_York"
TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# 1. Sizing helpers (daily timeline)
# ---------------------------------------------------------------------------
def realised_vol(daily_returns: pd.Series, window: int = 20, min_periods: int | None = None) -> pd.Series:
    """Annualised rolling standard deviation; value on d uses returns through d."""
    mp = window if min_periods is None else min_periods
    return daily_returns.rolling(window, min_periods=mp).std() * np.sqrt(TRADING_DAYS)


def trailing_vol(daily_returns: pd.Series, window: int = 20, lag: int = 1,
                 min_periods: int | None = None) -> pd.Series:
    """`realised_vol` shifted by `lag` rows: with lag=1 the value on d is known at 09:30 of d."""
    return realised_vol(daily_returns, window, min_periods).shift(lag)


def vol_target_scale(daily_returns: pd.Series, target: float, window: int = 20,
                     power: float = 1.0, cap: float = 1.0, lag: int = 1,
                     fill: float | None = None) -> pd.Series:
    """Exposure multiplier min(cap, (target / RV_window)^power).

    power = 1 is classic vol targeting, power = 2 the Moreira-Muir 1/variance
    rule. The value on date d uses returns through d - lag. Where RV is not
    yet defined (warm-up) the multiplier is `fill` (default: `cap`, i.e. no
    scaling).
    """
    rv = realised_vol(daily_returns, window)
    scale = (target / rv) ** power
    scale = scale.where(rv.notna() & (rv > 0)).clip(upper=cap).shift(lag)
    return scale.fillna(cap if fill is None else fill)


def ramp_exposure(vix_prev: pd.Series, floor: float = 18.0, span: float = 10.0) -> pd.Series:
    """The gap-fade sleeve's Nagel ramp: clip((VIX(d-1) - floor) / span, 0, 1), NaN -> 0."""
    return ((vix_prev - floor) / span).clip(lower=0.0, upper=1.0).fillna(0.0)


def reversal_vol_sizing(vix_prev: pd.Series, sigma_hat: pd.Series, target: float,
                        vix_gate: float = 18.0, cap: float = 1.0) -> pd.Series:
    """Vol-targeted exposure for an intraday sleeve, gated on by VIX.

    exposure[d] = min(cap, target / sigma_hat[d]) if vix_prev[d] > vix_gate else 0.
    `sigma_hat` must already be causal for 09:30 of d (e.g. `trailing_vol(..., lag=1)`
    of the sleeve's own or an equal-weight book's 09:30 -> 16:00 returns).
    Days with undefined sigma_hat get 0 (no sizing information -> stay flat).
    """
    expo = (target / sigma_hat).clip(upper=cap)
    expo = expo.where(sigma_hat.notna() & (sigma_hat > 0), 0.0)
    on = (vix_prev > vix_gate).fillna(False)
    return expo.where(on, 0.0).astype(float)


def rv_tilt(exposure: pd.Series, rv: pd.Series, ref: float, power: float = 1.0,
            cap: float = 1.0) -> pd.Series:
    """exposure * (ref / rv)^power, capped at `cap`; where rv is undefined the
    exposure is left unchanged."""
    tilt = (ref / rv) ** power
    out = (exposure * tilt).where(rv.notna() & (rv > 0), exposure)
    return out.clip(upper=cap).fillna(0.0)


def book_intraday_returns(book: pd.DataFrame, open_: pd.DataFrame, close: pd.DataFrame) -> pd.Series:
    """09:30 -> 16:00 return of a per-date weight book (rows = dates, cols =
    tickers): sum_i w[d, i] * (close[d, i] / open[d, i] - 1). Known at 16:00 of d."""
    cols = [c for c in book.columns if c in open_.columns]
    r = close[cols] / open_[cols] - 1.0
    return (book[cols].reindex(r.index).fillna(0.0) * r.fillna(0.0)).sum(axis=1)


def scale_by_date(weights: pd.DataFrame, factor_daily: pd.Series, fill: float = 0.0) -> pd.DataFrame:
    """Multiply every session row of `weights` by the factor of its calendar date.

    For a sleeve that is flat at one of the two sessions (the gap-fade sleeve is
    all-zero at 16:00) this rescales the sleeve's daily exposure. Dates absent
    from `factor_daily` get `fill`.
    """
    dates = session_dates(pd.DatetimeIndex(weights.index))
    f = pd.Series(factor_daily).reindex(dates).fillna(fill).to_numpy()
    return weights.mul(f, axis=0)


def daily_to_sessions(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Daily (date-indexed) series -> session stamps: the value for date d
    applies from the 16:00 close of d until the next 16:00 close (same
    convention as the regime multiplier in `hf_ensemble`)."""
    s = pd.Series(series).copy()
    s.index = (pd.DatetimeIndex(s.index) + pd.Timedelta(hours=16)).tz_localize(ET)
    if index.tz is not None:
        s.index = s.index.tz_convert(index.tz)
    else:
        s.index = s.index.tz_localize(None)
    return s.reindex(index.union(s.index)).ffill().reindex(index)


# ---------------------------------------------------------------------------
# 2. Ensemble-level vol targeting (session timeline)
# ---------------------------------------------------------------------------
def book_daily_returns(weights: pd.DataFrame, prices: pd.DataFrame) -> pd.Series:
    """Gross (pre-cost, pre-cash) daily returns of a session-timeline weight
    matrix: same arithmetic as the drawdown throttle in `hf_ensemble`."""
    cols = [c for c in weights.columns if c in prices.columns]
    px = prices[cols].ffill()
    asset_ret = px.pct_change(fill_method=None).fillna(0.0)
    sess = (weights[cols].shift(1).fillna(0.0) * asset_ret).sum(axis=1)
    dates = session_dates(pd.DatetimeIndex(sess.index))
    daily = (1.0 + sess).groupby(dates).prod() - 1.0
    daily.index = pd.DatetimeIndex(daily.index)
    return daily


def ensemble_vol_scale(weights: pd.DataFrame, prices: pd.DataFrame, target: float,
                       window: int = 20, power: float = 1.0, cap: float = 1.0) -> pd.Series:
    """Scale-down-only multiplier on the session index of `weights`.

    scale[d] = min(cap, (target / RV_window(book daily returns through d))^power),
    applied from the 16:00 close of d through the 09:30 open of d+1 (so the
    09:30 row of d uses returns through the 16:00 close of d-1). Warm-up rows
    get `cap`. power = 2 is the Moreira-Muir form.
    """
    daily = book_daily_returns(weights, prices)
    scale_daily = vol_target_scale(daily, target, window=window, power=power, cap=cap, lag=0)
    return daily_to_sessions(scale_daily, pd.DatetimeIndex(weights.index)).fillna(cap)


# ---------------------------------------------------------------------------
# 3. Combination tools (daily excess returns)
# ---------------------------------------------------------------------------
def sharpe_ratio(excess: pd.Series) -> float:
    """Annualised Sharpe of a daily *excess* return series (rf already removed)."""
    r = pd.Series(excess).dropna()
    sd = r.std()
    if len(r) < 2 or not np.isfinite(sd) or sd == 0:
        return float("nan")
    return float(r.mean() / sd * np.sqrt(TRADING_DAYS))


def _split(excess: pd.DataFrame | pd.Series, split: str | None):
    if split is None:
        return excess, excess.iloc[0:0]
    t = pd.Timestamp(split)
    return excess.loc[:t - pd.Timedelta(nanoseconds=1)], excess.loc[t:]


def sharpe_table(excess: pd.DataFrame, split: str | None = "2022-01-01") -> pd.DataFrame:
    """Per-column Sharpe (full / IS / OOS), annualised vol, mean bp/day, kurtosis, n."""
    ins, oos = _split(excess, split)
    rows = []
    for c in excess.columns:
        r = excess[c].dropna()
        rows.append({
            "series": c,
            "sharpe": sharpe_ratio(r),
            "sharpe_is": sharpe_ratio(ins[c].dropna()) if len(ins) else np.nan,
            "sharpe_oos": sharpe_ratio(oos[c].dropna()) if len(oos) else np.nan,
            "vol": r.std() * np.sqrt(TRADING_DAYS),
            "mean_bp": r.mean() * 1e4,
            "kurtosis": r.kurt(),
            "worst_day": r.min(),
            "n_days": len(r),
            "start": r.index.min(),
        })
    return pd.DataFrame(rows).set_index("series")


def naive_sharpe_bound(sharpes) -> float:
    """sqrt(sum S_i^2): the Sharpe of the optimal combination of uncorrelated
    streams (negative-Sharpe streams contribute 0)."""
    s = np.clip(np.asarray(list(sharpes), dtype=float), 0.0, None)
    return float(np.sqrt(np.nansum(s ** 2)))


def _normalise_gross(w: pd.Series) -> pd.Series:
    g = w.abs().sum()
    return w / g if g > 0 else w


def inverse_vol_weights(excess_is: pd.DataFrame) -> pd.Series:
    """Equal-risk weights w_i proportional to 1 / vol_i, gross 1."""
    vol = excess_is.std()
    w = (1.0 / vol).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return _normalise_gross(w)


def sharpe_proportional_weights(excess_is: pd.DataFrame) -> pd.Series:
    """Max-Sharpe weights for *uncorrelated* streams: w_i proportional to
    S_i / vol_i = mu_i / vol_i^2 (negative-Sharpe streams get 0), gross 1."""
    mu, vol = excess_is.mean(), excess_is.std()
    w = (mu / vol ** 2).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    return _normalise_gross(w)


def max_sharpe_weights(excess_is: pd.DataFrame, no_short: bool = True) -> pd.Series:
    """In-sample mean-variance tangency weights, normalised to gross 1.

    Unconstrained: w proportional to Sigma^-1 mu (closed form; may be negative).
    no_short: min w' Sigma w  s.t.  mu' w = 1, w >= 0  (convex QP via SLSQP),
    which is the tangency portfolio on the no-short efficient frontier. If no
    stream has a positive mean the result is all zeros.
    """
    cols = list(excess_is.columns)
    mu = excess_is.mean().to_numpy()
    cov = excess_is.cov().to_numpy()
    n = len(cols)
    if not no_short:
        try:
            w = np.linalg.solve(cov, mu)
        except np.linalg.LinAlgError:
            w = np.linalg.pinv(cov) @ mu
        return _normalise_gross(pd.Series(w, index=cols))
    if (mu <= 0).all():
        return pd.Series(0.0, index=cols)
    from scipy.optimize import minimize
    w0 = np.clip(mu, 0, None)
    w0 = w0 / (mu @ w0)
    res = minimize(lambda w: w @ cov @ w, w0, jac=lambda w: 2 * cov @ w, method="SLSQP",
                   bounds=[(0.0, None)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: mu @ w - 1.0, "jac": lambda w: mu}],
                   options={"maxiter": 500, "ftol": 1e-14})
    w = np.clip(res.x, 0.0, None)
    if not res.success or w.sum() <= 0:
        # Fall back to direct Sharpe maximisation on the simplex.
        def neg_sharpe(w):
            v = np.sqrt(max(w @ cov @ w, 1e-18))
            return -(mu @ w) / v
        res = minimize(neg_sharpe, np.ones(n) / n, method="SLSQP", bounds=[(0.0, 1.0)] * n,
                       constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0}])
        w = np.clip(res.x, 0.0, None)
    return _normalise_gross(pd.Series(w, index=cols))


def combine_max_sharpe(excess: pd.DataFrame, split: str | None = "2022-01-01",
                       no_short: bool = True) -> dict:
    """IS tangency weights (gross 1) and the Sharpe of that fixed-weight
    combination in-sample, out-of-sample and over the full sample."""
    ins, oos = _split(excess, split)
    w = max_sharpe_weights(ins if len(ins) else excess, no_short=no_short)
    port = excess.fillna(0.0) @ w
    p_is, p_oos = _split(port, split)
    return {
        "weights": w,
        "sharpe_is": sharpe_ratio(p_is),
        "sharpe_oos": sharpe_ratio(p_oos) if len(p_oos) else np.nan,
        "sharpe_full": sharpe_ratio(port),
        "returns": port,
    }


def combine_fixed(excess: pd.DataFrame, weights: pd.Series, split: str | None = "2022-01-01") -> dict:
    """Sharpe (IS / OOS / full) of a fixed-weight combination of the columns."""
    w = pd.Series(weights).reindex(excess.columns).fillna(0.0)
    port = excess.fillna(0.0) @ w
    p_is, p_oos = _split(port, split)
    return {
        "weights": w,
        "sharpe_is": sharpe_ratio(p_is),
        "sharpe_oos": sharpe_ratio(p_oos) if len(p_oos) else np.nan,
        "sharpe_full": sharpe_ratio(port),
        "returns": port,
    }


def align_excess(series: dict[str, pd.Series], rf_daily: pd.Series | None = None,
                 how: str = "inner") -> pd.DataFrame:
    """Dict of daily return Series -> DataFrame of daily *excess* returns.

    rf_daily: annualised T-bill rate per date (divide by 252), subtracted from
    every series (pass None if the inputs are already excess / ex-cash).
    how = "inner": keep dates where every series is defined (fair covariance);
    how = "zero":  union of dates, missing days count as 0 (flat, in cash).
    """
    df = pd.DataFrame({k: pd.Series(v).astype(float) for k, v in series.items()})
    df.index = pd.DatetimeIndex(df.index)
    if rf_daily is not None:
        rf = pd.Series(rf_daily).astype(float)
        rf.index = pd.DatetimeIndex(rf.index)
        rf = rf.reindex(df.index).ffill().fillna(0.0) / TRADING_DAYS
        df = df.sub(rf, axis=0).where(df.notna())
    if how == "inner":
        return df.dropna(how="any")
    if how == "zero":
        return df.fillna(0.0)
    raise ValueError(f"unknown how={how!r}")


def combination_report(series: dict[str, pd.Series], rf_daily: pd.Series | None = None,
                       split: str | None = "2022-01-01", how: str = "inner") -> dict:
    """The orchestrator's decision table for a set of candidate sleeves.

    Returns a dict with:
      sharpes      per-series Sharpe full / IS / OOS, vol, mean bp, kurtosis, n
      corr         pairwise correlation of daily excess returns (full sample)
      corr_oos     the same on the OOS part
      bound        sqrt(sum S_i^2) using full-sample Sharpes (and IS / OOS)
      combos       one row per combination rule (max-Sharpe no-short, max-Sharpe
                   unconstrained, Sharpe/vol proportional, inverse-vol, equal
                   weight): IS-fitted weights, Sharpe IS / OOS / full
      excess       the aligned excess-return frame used
    """
    ex = align_excess(series, rf_daily, how=how)
    ins, oos = _split(ex, split)
    st = sharpe_table(ex, split)
    rules = {
        "max_sharpe_noshort": max_sharpe_weights(ins if len(ins) else ex, no_short=True),
        "max_sharpe_unconstrained": max_sharpe_weights(ins if len(ins) else ex, no_short=False),
        "sharpe_over_vol": sharpe_proportional_weights(ins if len(ins) else ex),
        "inverse_vol": inverse_vol_weights(ins if len(ins) else ex),
        "equal_weight": pd.Series(1.0 / ex.shape[1], index=ex.columns),
    }
    rows = []
    for name, w in rules.items():
        c = combine_fixed(ex, w, split)
        row = {"rule": name, "sharpe_is": c["sharpe_is"], "sharpe_oos": c["sharpe_oos"],
               "sharpe_full": c["sharpe_full"]}
        row.update({f"w_{k}": float(v) for k, v in w.items()})
        rows.append(row)
    combos = pd.DataFrame(rows).set_index("rule")
    return {
        "sharpes": st,
        "corr": ex.corr(),
        "corr_oos": oos.corr() if len(oos) > 20 else None,
        "bound": naive_sharpe_bound(st["sharpe"]),
        "bound_is": naive_sharpe_bound(st["sharpe_is"]),
        "bound_oos": naive_sharpe_bound(st["sharpe_oos"]),
        "combos": combos,
        "excess": ex,
        "start": ex.index.min(),
        "n_days": len(ex),
    }
