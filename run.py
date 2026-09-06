#!/usr/bin/env python3
"""quantbot CLI.

Examples:
  python run.py backtest --start 2016-01-01
  python run.py backtest --start 2016-01-01 --sleeves     # per-sleeve breakdown
  python run.py paper trade                                # rebalance paper account
  python run.py paper trade --force                        # ignore market hours
  python run.py paper status
  python run.py paper reset --capital 100000
"""
from __future__ import annotations

import argparse
import datetime as dt

from quantbot.backtest import run_backtest
from quantbot.config import PROJECT_ROOT, Config
from quantbot.data import benchmark_series, fetch_prices
from quantbot.metrics import format_summary, summary
from quantbot.strategies import (
    ensemble_weights,
    mean_reversion_weights,
    momentum_weights,
    trend_weights,
)


def cmd_backtest(args: argparse.Namespace) -> None:
    cfg = Config()
    end = args.end or dt.date.today().isoformat()
    tickers = cfg.universe + [cfg.benchmark]
    try:
        all_close = fetch_prices(tickers, start=args.start, end=end, refresh=args.refresh)
    except RuntimeError:
        all_close = fetch_prices(cfg.universe, start=args.start, end=end, refresh=args.refresh)
    universe = [t for t in cfg.universe if t in all_close.columns]
    close = all_close[universe]
    bench = benchmark_series(all_close, cfg.benchmark, universe)
    bench_label = cfg.benchmark if cfg.benchmark in all_close.columns else "EW index"

    weights = ensemble_weights(close, bench, cfg)
    result = run_backtest(weights, close, cfg, label="ensemble")

    bench_ret = bench.pct_change(fill_method=None).reindex(result.daily_returns.index)
    bench_stats = summary(bench_ret, f"{bench_label} B&H")

    print(f"\nBacktest {result.daily_returns.index[0].date()} -> "
          f"{result.daily_returns.index[-1].date()}  "
          f"({len(result.daily_returns)} trading days, "
          f"{len(cfg.universe)} names, costs "
          f"{cfg.commission_bps + cfg.slippage_bps:.0f} bps/side)\n")
    print(format_summary(result.stats))
    print(format_summary(bench_stats))
    print(f"\nAvg daily turnover: {result.stats['avg_turnover']:.2%} | "
          f"annual cost drag: {result.stats['annual_cost_drag']:.2%}")

    if args.sleeves:
        print("\nPer-sleeve (each run standalone, same costs):")
        for name, fn in [
            ("momentum", momentum_weights),
            ("trend", trend_weights),
            ("meanrev", mean_reversion_weights),
        ]:
            w = fn(close, cfg)
            r = run_backtest(w, close, cfg, label=name)
            print(format_summary(r.stats))

    if args.plot:
        _plot(result, bench_ret, cfg, bench_label)


def _plot(result, bench_ret, cfg, bench_label: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from quantbot.metrics import equity_curve

    strat = result.equity
    bench = equity_curve(bench_ret.fillna(0.0))

    fig, axes = plt.subplots(
        3, 1, figsize=(11, 9), sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1]},
    )
    axes[0].plot(strat.index, strat.values, label="quantbot ensemble", lw=1.6)
    axes[0].plot(bench.index, bench.values, label=f"{bench_label} buy & hold", lw=1.2, alpha=0.8)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Growth of $1 (log)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    dd = strat / strat.cummax() - 1.0
    bdd = bench / bench.cummax() - 1.0
    axes[1].fill_between(dd.index, dd.values, 0, alpha=0.6, label="strategy")
    axes[1].fill_between(bdd.index, bdd.values, 0, alpha=0.3, label="benchmark")
    axes[1].set_ylabel("Drawdown")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    gross = result.weights.sum(axis=1)
    axes[2].plot(gross.index, gross.values, lw=0.8)
    axes[2].set_ylabel("Gross exposure")
    axes[2].set_ylim(0, 1.1)
    axes[2].grid(alpha=0.3)

    out = PROJECT_ROOT / "backtest_report.png"
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"\nSaved chart: {out}")


def cmd_paper(args: argparse.Namespace) -> None:
    from quantbot import paper

    cfg = Config()
    if args.paper_cmd == "trade":
        paper.trade(cfg, force=args.force, refresh=not args.no_refresh)
    elif args.paper_cmd == "status":
        paper.status(cfg)
    elif args.paper_cmd == "reset":
        paper.reset(cfg, capital=args.capital)


from quantbot.strategies.hf_ensemble import PROFILES  # noqa: E402


def cmd_hf(args: argparse.Namespace) -> None:
    from quantbot import hf_paper
    from quantbot.config import HFConfig

    cfg = HFConfig()
    if args.hf_cmd == "backtest":
        from quantbot.strategies.hf_ensemble import run_hf_backtest
        run_hf_backtest(cfg, timeline=args.timeline, refresh=args.refresh, plot=args.plot,
                        sleeves=args.sleeves, n_trials=args.n_trials, profile=args.profile)
    elif args.hf_cmd == "trade":
        if args.account:
            hf_paper.trade(cfg, session=args.session, force=args.force, refresh=not args.no_refresh,
                           account=args.account)
        else:
            hf_paper.trade_all(cfg, session=args.session, force=args.force, refresh=not args.no_refresh)
    elif args.hf_cmd == "status":
        hf_paper.status(cfg, plot=not args.no_plot, account=args.account or "live")
    elif args.hf_cmd == "reset":
        hf_paper.reset(cfg, capital=args.capital, profile=args.profile, account=args.account or "live")
    elif args.hf_cmd == "schedule":
        from quantbot.schedule import install_launchd, uninstall_launchd, show_schedule
        if args.install:
            install_launchd()
        elif args.uninstall:
            uninstall_launchd()
        else:
            show_schedule()


def main() -> None:
    p = argparse.ArgumentParser(description="quantbot - research & paper trading")
    sub = p.add_subparsers(dest="cmd", required=True)

    hf = sub.add_parser("hf", help="short-horizon system ($1k paper account)")
    hsub = hf.add_subparsers(dest="hf_cmd", required=True)
    hb = hsub.add_parser("backtest", help="backtest the HF ensemble")
    hb.add_argument("--timeline", choices=["hourly", "daily"], default="daily",
                    help="daily = 09:30/16:00 sessions, 2010+ (default); hourly = ~2y incl. intraday sleeves")
    hb.add_argument("--profile", choices=sorted(PROFILES), default=None)
    hb.add_argument("--refresh", action="store_true")
    hb.add_argument("--plot", action="store_true")
    hb.add_argument("--sleeves", action="store_true", help="also show each sleeve standalone")
    hb.add_argument("--n-trials", type=int, default=None, help="override trial count for deflated Sharpe")
    ht = hsub.add_parser("trade", help="process one paper session (all accounts unless --account)")
    ht.add_argument("--session", choices=["auto", "open", "last-hour", "close"], default="auto")
    ht.add_argument("--force", action="store_true", help="re-process an already processed session")
    ht.add_argument("--no-refresh", action="store_true")
    ht.add_argument("--account", default=None, help="'live' (default account) or a shadow account name")
    hs = hsub.add_parser("status", help="paper account status")
    hs.add_argument("--no-plot", action="store_true")
    hs.add_argument("--account", default=None)
    hr = hsub.add_parser("reset", help="reset (or create) a paper account")
    hr.add_argument("--capital", type=float, default=None)
    hr.add_argument("--account", default=None, help="omit for the live account; any other name = shadow account")
    hr.add_argument("--profile", choices=sorted(PROFILES), default=None)
    hsc = hsub.add_parser("schedule", help="show/install launchd jobs for the three daily sessions")
    hsc.add_argument("--install", action="store_true")
    hsc.add_argument("--uninstall", action="store_true")
    hf.set_defaults(func=cmd_hf)

    bt = sub.add_parser("backtest", help="run historical backtest")
    bt.add_argument("--start", default="2016-01-01")
    bt.add_argument("--end", default=None)
    bt.add_argument("--refresh", action="store_true", help="force data re-download")
    bt.add_argument("--sleeves", action="store_true", help="show per-strategy stats")
    bt.add_argument("--plot", action="store_true", help="save equity curve chart")
    bt.set_defaults(func=cmd_backtest)

    pp = sub.add_parser("paper", help="paper trading")
    psub = pp.add_subparsers(dest="paper_cmd", required=True)
    tr = psub.add_parser("trade", help="rebalance the paper portfolio")
    tr.add_argument("--force", action="store_true", help="trade outside market hours")
    tr.add_argument("--no-refresh", action="store_true", help="use cached data")
    psub.add_parser("status", help="show paper portfolio")
    rs = psub.add_parser("reset", help="reset paper account")
    rs.add_argument("--capital", type=float, default=None)
    pp.set_defaults(func=cmd_paper)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
