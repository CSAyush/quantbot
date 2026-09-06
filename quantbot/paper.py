"""Paper trading engine.

Maintains a simulated portfolio on disk (paper_state/state.json) and a trade
log (paper_state/trades.csv). Each `trade` run:
  1. refreshes market data,
  2. computes today's ensemble target weights,
  3. rebalances the paper portfolio toward those targets at current prices,
     paying the same commission + slippage the backtest assumes.

Designed to be run once per day near the close (e.g. 3:45pm ET) via cron or
manually. Running it more often is harmless - it just rebalances to the same
targets and the minimum-trade filter suppresses churn.
"""
from __future__ import annotations

import datetime as dt
import json
import zoneinfo
from pathlib import Path

import pandas as pd

from .config import STATE_DIR, Config
from .data import benchmark_series, fetch_prices
from .strategies import ensemble_weights

STATE_FILE = STATE_DIR / "state.json"
TRADES_FILE = STATE_DIR / "trades.csv"
HISTORY_START = "2014-01-01"  # enough history for 200d indicators + context
MIN_TRADE_DOLLARS = 100.0

ET = zoneinfo.ZoneInfo("America/New_York")


def market_is_open(now: dt.datetime | None = None) -> bool:
    now = now or dt.datetime.now(tz=ET)
    if now.weekday() >= 5:
        return False
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= now <= close_t


def load_state(cfg: Config) -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "cash": cfg.starting_cash,
        "starting_cash": cfg.starting_cash,
        "inception": None,
        "positions": {},          # ticker -> shares
        "history": [],            # [{date, equity, benchmark}]
    }


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def reset(cfg: Config, capital: float | None = None) -> None:
    if capital:
        cfg.starting_cash = capital
    state = {
        "cash": cfg.starting_cash,
        "starting_cash": cfg.starting_cash,
        "inception": None,
        "positions": {},
        "history": [],
    }
    save_state(state)
    if TRADES_FILE.exists():
        TRADES_FILE.unlink()
    print(f"Paper account reset with ${cfg.starting_cash:,.2f}")


def _append_trades(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    header = not TRADES_FILE.exists()
    df.to_csv(TRADES_FILE, mode="a", header=header, index=False)


def portfolio_value(state: dict, prices: pd.Series) -> float:
    pos_val = sum(
        shares * prices.get(t, 0.0) for t, shares in state["positions"].items()
    )
    return state["cash"] + pos_val


def trade(cfg: Config, force: bool = False, refresh: bool = True) -> None:
    if not force and not market_is_open():
        print(
            "Market is closed (9:30-16:00 ET, Mon-Fri). "
            "Use --force to rebalance at last close prices anyway."
        )
        return

    today = dt.date.today().isoformat()
    tickers = cfg.universe + [cfg.benchmark]
    try:
        all_close = fetch_prices(tickers, start=HISTORY_START, refresh=refresh)
    except RuntimeError:
        all_close = fetch_prices(cfg.universe, start=HISTORY_START, refresh=refresh)
    universe = [t for t in cfg.universe if t in all_close.columns]
    close = all_close[universe]
    bench = benchmark_series(all_close, cfg.benchmark, universe)

    weights = ensemble_weights(close, bench, cfg)
    target = weights.iloc[-1]
    asof = weights.index[-1].date().isoformat()
    prices = close.iloc[-1]

    state = load_state(cfg)
    if state["inception"] is None:
        state["inception"] = today

    equity = portfolio_value(state, prices)
    cost_rate = (cfg.commission_bps + cfg.slippage_bps) / 1e4

    trades: list[dict] = []
    # Sells first so cash is available for buys.
    orders = []
    for ticker in universe:
        price = prices.get(ticker)
        if price is None or pd.isna(price) or price <= 0:
            continue
        current_shares = state["positions"].get(ticker, 0.0)
        target_dollars = equity * float(target.get(ticker, 0.0))
        delta_dollars = target_dollars - current_shares * price
        if abs(delta_dollars) < MIN_TRADE_DOLLARS:
            continue
        orders.append((ticker, price, delta_dollars))
    orders.sort(key=lambda o: o[2])  # sells (negative) first

    for ticker, price, delta_dollars in orders:
        shares_delta = delta_dollars / price
        cost = abs(delta_dollars) * cost_rate
        state["cash"] -= delta_dollars + cost
        new_shares = state["positions"].get(ticker, 0.0) + shares_delta
        if abs(new_shares) < 1e-9:
            state["positions"].pop(ticker, None)
        else:
            state["positions"][ticker] = new_shares
        trades.append(
            {
                "date": today,
                "ticker": ticker,
                "side": "BUY" if delta_dollars > 0 else "SELL",
                "shares": round(shares_delta, 4),
                "price": round(price, 4),
                "dollars": round(delta_dollars, 2),
                "cost": round(cost, 4),
            }
        )

    equity_after = portfolio_value(state, prices)
    bench_price = float(bench.iloc[-1])
    state["history"].append(
        {"date": today, "equity": round(equity_after, 2), "benchmark": bench_price}
    )
    save_state(state)
    if trades:
        _append_trades(trades)

    gross = sum(
        s * prices.get(t, 0.0) for t, s in state["positions"].items()
    ) / equity_after if equity_after else 0.0
    print(f"Rebalanced {len(trades)} positions (signals as of {asof}).")
    print(f"Equity: ${equity_after:,.2f} | Cash: ${state['cash']:,.2f} | Invested: {gross:.1%}")
    if trades:
        print(pd.DataFrame(trades).to_string(index=False))


def status(cfg: Config) -> None:
    state = load_state(cfg)
    if state["inception"] is None:
        print("No paper trading history yet. Run: python run.py paper trade")
        return

    tickers = cfg.universe + [cfg.benchmark]
    try:
        all_close = fetch_prices(tickers, start=HISTORY_START, refresh=False)
    except RuntimeError:
        all_close = fetch_prices(cfg.universe, start=HISTORY_START, refresh=False)
    prices = all_close.ffill().iloc[-1]

    equity = portfolio_value(state, prices)
    start_cash = state["starting_cash"]
    pnl = equity - start_cash

    print(f"Inception:  {state['inception']}")
    print(f"Equity:     ${equity:,.2f}")
    print(f"Cash:       ${state['cash']:,.2f}")
    print(f"P&L:        ${pnl:,.2f} ({pnl / start_cash:+.2%})")

    if state["history"]:
        hist = pd.DataFrame(state["history"])
        first_bench = hist["benchmark"].iloc[0]
        last_bench = prices.get(cfg.benchmark, hist["benchmark"].iloc[-1])
        bench_ret = last_bench / first_bench - 1.0
        print(f"Benchmark ({cfg.benchmark}) over same period: {bench_ret:+.2%}")

    if state["positions"]:
        rows = []
        for t, shares in sorted(state["positions"].items()):
            px = prices.get(t, float("nan"))
            rows.append(
                {"ticker": t, "shares": round(shares, 4),
                 "price": round(float(px), 2), "value": round(shares * px, 2)}
            )
        print(pd.DataFrame(rows).to_string(index=False))
    else:
        print("No open positions (fully in cash).")
