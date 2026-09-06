"""Standard research report so every sleeve is judged the same way."""
from __future__ import annotations

import pandas as pd

from .engine import SessionResult, format_hf_summary
from .validation import bootstrap_sharpe_ci, deflated_sharpe, split_stats, yearly_table


def report(res: SessionResult, split: str | None = None, n_trials: int = 1,
           benchmark_daily: pd.Series | None = None) -> None:
    """Print the full scorecard for a backtest result.

    split:     date separating in-sample from out-of-sample (be honest about it)
    n_trials:  number of parameter combinations / variants tried before settling
    """
    print("=" * 110)
    print(format_hf_summary(res.stats))
    s = res.stats
    rf_mean = s.get("rf_annual", 0.0)
    rf = res.rf_daily if res.rf_daily is not None else rf_mean
    print(f"  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean {rf_mean:.1%} over the period)")
    print(f"  time in market {s['time_in_market']:.1%} | turnover/day {s['turnover_per_day']:.2f} | "
          f"trades/day {s['trades_per_day']:.2f} | skew {s['skew']:.2f} | kurt {s['kurtosis']:.1f} | "
          f"best {s['best_day']:+.2%} | worst {s['worst_day']:+.2%}")
    excess = res.excess_daily
    lo, pt, hi = bootstrap_sharpe_ci(excess)
    print(f"  Sharpe 95% bootstrap CI: [{lo:.2f}, {hi:.2f}]")
    ds = deflated_sharpe(excess, n_trials=n_trials)
    print(f"  Deflated Sharpe: P(SR > null max of {n_trials} trials = {ds['expected_max_null_sharpe_annual']:.2f}) "
          f"= {ds['prob_sharpe_exceeds_null']:.3f}")
    if benchmark_daily is not None:
        b = benchmark_daily.reindex(res.daily_returns.index).fillna(0.0)
        corr = res.daily_returns.corr(b)
        beta = res.daily_returns.cov(b) / b.var() if b.var() > 0 else float("nan")
        print(f"  vs benchmark: corr {corr:.2f} | beta {beta:.2f}")
    print("\n  Yearly:")
    yt = yearly_table(res.daily_returns, rf_annual=rf)
    print(yt.to_string(float_format=lambda x: f"{x:8.3f}"))
    if split is not None:
        print(f"\n  In-sample / out-of-sample split at {split}:")
        print(split_stats(res.daily_returns, split, res.label, rf_annual=rf)
              .to_string(float_format=lambda x: f"{x:8.3f}"))
    print("=" * 110)
