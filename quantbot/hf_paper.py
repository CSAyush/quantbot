"""Paper trading for the short-horizon system ($1,000 fake-money account).

Design principle: the live trader is the backtest. Each run
  1. refreshes daily + hourly data,
  2. masks anything not knowable at the session being traded (e.g. at 09:30
     today's close/high/low/volume are blanked, at 15:30 the in-progress bar
     is dropped) so a sleeve with hidden lookahead breaks loudly instead of
     silently cheating,
  3. computes the ensemble weight matrix exactly as the backtest does,
  4. takes the row at the session timestamp as the target and fills at the
     panel price for that timestamp (the open/close auction print, or the
     15:30 trade),
  5. pays the same per-asset costs as the backtest and accrues cash yield /
     short borrow pro-rata since the previous session.

Sessions: 09:30 (open), 15:30 (last-hour entry), 16:00 (close). Run via
launchd/cron a couple of minutes after each; `--session auto` picks the most
recent session timestamp not yet processed.

State: paper_state/hf/state.json, trades in paper_state/hf/trades.csv,
per-session equity history in paper_state/hf/history.csv.
"""
from __future__ import annotations

import datetime as dt
import json
import zoneinfo
from pathlib import Path

import numpy as np
import pandas as pd

from .config import STATE_DIR, HFConfig, cost_bps_for
from .data import ET, MarketData

HF_STATE_DIR = STATE_DIR / "hf"
ACCOUNTS_DIR = HF_STATE_DIR / "accounts"

TZ = zoneinfo.ZoneInfo(ET)
SESSION_TIMES = {"open": dt.time(9, 30), "last-hour": dt.time(15, 30), "close": dt.time(16, 0)}
LATE_WARN_MINUTES = 20


class Account:
    """Paths for one paper account. 'live' is paper_state/hf/ (the original
    account); any other name lives under paper_state/hf/accounts/<name>/.
    Shadow accounts let a candidate configuration trade the same sessions
    as the live book so a switch is decided on live evidence."""

    def __init__(self, name: str = "live"):
        self.name = name
        self.dir = HF_STATE_DIR if name == "live" else ACCOUNTS_DIR / name
        self.state_file = self.dir / "state.json"
        self.trades_file = self.dir / "trades.csv"
        self.history_file = self.dir / "history.csv"
        self.log_file = self.dir / "log.txt"

    def exists(self) -> bool:
        return self.state_file.exists()

    @staticmethod
    def all() -> list["Account"]:
        names = ["live"] + sorted(p.name for p in ACCOUNTS_DIR.iterdir() if p.is_dir()) if ACCOUNTS_DIR.exists() else ["live"]
        return [a for a in (Account(n) for n in names) if a.exists()]


# --------------------------------------------------------------------------- state
def _blank_state(cfg: HFConfig, profile: str | None = None) -> dict:
    from .strategies.hf_ensemble import DEFAULT_PROFILE
    return {
        "cash": cfg.starting_cash,
        "starting_cash": cfg.starting_cash,
        "profile": profile or DEFAULT_PROFILE,
        "inception": None,
        "positions": {},           # ticker -> shares (negative = short)
        "last_session": None,      # ISO timestamp of last processed session
        "sessions_processed": 0,
    }


def load_state(cfg: HFConfig, acct: Account) -> dict:
    if acct.state_file.exists():
        return json.loads(acct.state_file.read_text())
    return _blank_state(cfg)


def save_state(state: dict, acct: Account) -> None:
    acct.dir.mkdir(parents=True, exist_ok=True)
    acct.state_file.write_text(json.dumps(state, indent=2))


def reset(cfg: HFConfig, capital: float | None = None, profile: str | None = None,
          account: str = "live") -> None:
    acct = Account(account)
    if capital:
        cfg.starting_cash = capital
    state = _blank_state(cfg, profile)
    save_state(state, acct)
    for f in (acct.trades_file, acct.history_file):
        if f.exists():
            f.unlink()
    print(f"HF paper account '{acct.name}' reset with ${cfg.starting_cash:,.2f} (profile '{state['profile']}')")


def _append_csv(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


def _log(msg: str, acct: Account) -> None:
    acct.dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(tz=TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    with acct.log_file.open("a") as f:
        f.write(f"[{stamp}] {msg}\n")


# --------------------------------------------------------------------------- data masking
def _mask_for_session(md: MarketData, ts: pd.Timestamp) -> None:
    """Remove everything that would not be known at session `ts` (in place)."""
    day = ts.tz_convert(TZ).tz_localize(None).normalize()
    if ts.time() == dt.time(9, 30):
        # Today's open is known, the rest of today's bar is not.
        for f in ["High", "Low", "Close", "Volume"]:
            if day in md.daily[f].index:
                md.daily[f].loc[day] = np.nan
        if day in md.aux.index:
            # VIX open is fine to use but keep it simple: yesterday's VIX.
            md.aux.loc[day] = np.nan
    if ts.time() < dt.time(16, 0):
        # Today's daily bar is incomplete before the close.
        md.px_daily = md.px_daily.loc[:ts]
    if md.px_intraday is not None:
        md.px_intraday = md.px_intraday.loc[:ts]
        if md.intraday is not None:
            starts = pd.DatetimeIndex(md.intraday["Close"].index).tz_convert(TZ)
            is_1530 = (starts.hour == 15) & (starts.minute == 30)
            ends = starts + pd.to_timedelta(np.where(is_1530, pd.Timedelta(minutes=30), pd.Timedelta(hours=1)))
            keep = ends <= ts  # only bars that have fully closed by the session time
            md.intraday = {f: df[keep] for f, df in md.intraday.items()}


def _inject_live_prints(md: MarketData, now: dt.datetime) -> None:
    """Build today's session prints from 1-minute bars.

    Yahoo's daily row for the current day is unreliable while the market is
    open: the Open can be *yesterday's* (2026-09-03, both accounts exited at
    stale prices) and the Close is whatever traded last. `fetch_ohlcv` now
    drops that row before 16:10 ET, so this function is the only source of
    today's 09:30 print (first 1m bar's open, which must be stamped 09:30) and,
    after the close, of today's 16:00 print when the official daily row has
    not arrived (last 1m bar, which must be stamped >= 15:59).

    Nothing is guessed: if the bars are not there, the row stays NaN and the
    trader's hard price guard refuses to trade (the scheduled retry will).
    """
    from .data import daily_session_prices

    now_et = pd.Timestamp(now).tz_convert(TZ)
    if now_et.weekday() >= 5 or now_et.time() < dt.time(9, 31):
        return
    today = now_et.tz_localize(None).normalize()
    tickers = list(md.tickers)
    for f in ["Open", "High", "Low", "Close", "Volume", "AdjFactor"]:
        if today not in md.daily[f].index:
            md.daily[f].loc[today] = np.nan
            md.daily[f] = md.daily[f].sort_index()

    after_close = now_et.time() >= dt.time(16, 10)
    recent = md.daily["Close"].loc[:today].iloc[-6:-1].notna().any()
    yday_open = md.daily["Open"].loc[:today].iloc[-2]
    today_open = md.daily["Open"].loc[today]
    # A row whose opens equal yesterday's for many names is a stale placeholder.
    stale = (today_open == yday_open) & recent
    if stale.sum() > 0.3 * recent.sum():
        print(f"[paper] today's daily Open equals yesterday's for {int(stale.sum())} names -> treating as missing")
        md.daily["Open"].loc[today] = np.nan
    if after_close:
        have_close = md.daily["Close"].loc[today].notna() & recent
        if have_close.sum() < 0.9 * recent.sum():
            print(f"[paper] official close present for only {int(have_close.sum())}/{int(recent.sum())} names; "
                  f"using 1m bars for the rest")
    need_open = (md.daily["Open"].loc[today].isna() & recent)
    need_close = (md.daily["Close"].loc[today].isna() & recent) if after_close else pd.Series(False, index=tickers)
    if not need_open.any() and not need_close.any():
        md.px_daily = daily_session_prices(md.daily)
        return

    import yfinance as yf
    raw = None
    for attempt in range(3):
        try:
            raw = yf.download(tickers, period="1d", interval="1m", progress=False, group_by="column",
                              auto_adjust=False, prepost=False)
        except Exception as exc:  # noqa: BLE001
            print(f"[paper] 1m download error: {exc}")
            raw = None
        if raw is not None and not raw.empty:
            break
        if attempt < 2:
            import time
            time.sleep(15)
    if raw is None or raw.empty:
        print("[paper] no 1m bars available for today; today's prints stay missing")
        md.px_daily = daily_session_prices(md.daily)
        return
    idx = pd.DatetimeIndex(raw.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx
    raw.index = idx.tz_convert(TZ)
    raw = raw[raw.index.normalize() == today.tz_localize(TZ)]
    if raw.empty:
        print("[paper] 1m bars returned are not from today; today's prints stay missing")
        md.px_daily = daily_session_prices(md.daily)
        return

    def field(name: str) -> pd.DataFrame:
        df = raw[name] if isinstance(raw.columns, pd.MultiIndex) else raw[[name]].set_axis(tickers, axis=1)
        return df.reindex(columns=tickers)

    if need_open.any():
        first_bar = raw.index[0]
        if first_bar.time() != dt.time(9, 30):
            print(f"[paper] first 1m bar is {first_bar.strftime('%H:%M')}, not 09:30; opens stay missing")
        else:
            opens = field("Open").iloc[0]
            fill = opens[need_open[need_open].index]
            md.daily["Open"].loc[today, fill.index] = fill.values
            print(f"[paper] today's open set from the 09:30 1m bar for {int(fill.notna().sum())}/{len(fill)} names")
    if need_close.any():
        last_bar = raw.index[-1]
        if last_bar.time() < dt.time(15, 59):
            print(f"[paper] last 1m bar is {last_bar.strftime('%H:%M')}; session not complete, closes stay missing")
        else:
            closes = field("Close").apply(lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan)
            fill = closes[need_close[need_close].index]
            md.daily["Close"].loc[today, fill.index] = fill.values
            hi, lo, vol = field("High").max(), field("Low").min(), field("Volume").sum()
            md.daily["High"].loc[today, fill.index] = hi[fill.index].values
            md.daily["Low"].loc[today, fill.index] = lo[fill.index].values
            md.daily["Volume"].loc[today, fill.index] = vol[fill.index].values
            print(f"[paper] today's close set from the {last_bar.strftime('%H:%M')} 1m bar for "
                  f"{int(fill.notna().sum())}/{len(fill)} names")
    md.px_daily = daily_session_prices(md.daily)


def _expected_session(now: dt.datetime) -> pd.Timestamp | None:
    """The session stamp that should exist given the wall clock (weekdays):
    today's 09:30 once the open has printed, today's 16:00 after the close."""
    now_et = pd.Timestamp(now).tz_convert(TZ)
    if now_et.weekday() >= 5:
        return None
    day = now_et.normalize()
    if now_et.time() >= dt.time(16, 10):
        return day + pd.Timedelta(hours=16)
    if now_et.time() >= dt.time(9, 32):
        return day + pd.Timedelta(hours=9, minutes=30)
    return None


def _resolve_session(md: MarketData, session: str, now: dt.datetime) -> pd.Timestamp:
    idx = md.px_intraday.index if md.px_intraday is not None else md.px_daily.index
    now_ts = pd.Timestamp(now).tz_convert(TZ)
    if session == "auto":
        candidates = idx[idx <= now_ts]
        if len(candidates) == 0:
            raise RuntimeError("no session timestamp at or before now")
        return candidates[-1]
    t = SESSION_TIMES[session]
    today = now_ts.normalize()
    ts = (today + pd.Timedelta(hours=t.hour, minutes=t.minute))
    if ts not in idx:
        # Fall back to the most recent stamp with this time of day (e.g. run after hours).
        same_tod = idx[(idx.hour == t.hour) & (idx.minute == t.minute) & (idx <= now_ts)]
        if len(same_tod) == 0:
            raise RuntimeError(f"no {session} session available yet")
        ts = same_tod[-1]
    return ts


# --------------------------------------------------------------------------- core
def portfolio_value(state: dict, prices: pd.Series) -> float:
    return state["cash"] + sum(sh * float(prices.get(t, np.nan)) for t, sh in state["positions"].items()
                               if not np.isnan(prices.get(t, np.nan)))


def trade_all(cfg: HFConfig, session: str = "auto", force: bool = False, refresh: bool = True) -> None:
    """Process the session for the live account and every shadow account.
    Failures are isolated per account; the exit code is non-zero if any failed."""
    failures = 0
    for i, acct in enumerate(Account.all()):
        print(f"\n=== account '{acct.name}' ===")
        try:
            # Every account refreshes: partial-day rows are never cached, so a
            # later account must not depend on what an earlier one fetched.
            trade(cfg, session=session, force=force, refresh=refresh, account=acct.name)
        except SystemExit as exc:
            failures += int(exc.code or 0) != 0
        except Exception as exc:  # noqa: BLE001 - one account must not block the others
            failures += 1
            msg = f"ERROR: unhandled {type(exc).__name__}: {exc}"
            print(msg)
            _log(msg, acct)
    if failures:
        raise SystemExit(2)


def trade(cfg: HFConfig, session: str = "auto", force: bool = False, refresh: bool = True,
          now: dt.datetime | None = None, account: str = "live") -> None:
    from .strategies.hf_ensemble import EnsembleParams, config_for, hf_ensemble_weights

    acct = Account(account)
    now = now or dt.datetime.now(tz=TZ)
    state = load_state(cfg, acct)
    params = EnsembleParams.from_profile(state.get("profile"))
    if params.universe != "core":
        cfg = config_for(params)
    # Hourly data is only needed if an intraday sleeve is funded.
    timeline = "hourly" if params.alloc.get("intraday_momentum", 0) > 0 else "daily"
    md = MarketData(cfg, refresh=refresh, intraday=(timeline == "hourly"))
    _inject_live_prints(md, now)
    ts = _resolve_session(md, session, now)

    if state["last_session"] and pd.Timestamp(state["last_session"]) >= ts and not force:
        expected = _expected_session(now)
        if expected is not None and expected > ts and state["positions"]:
            # The session that should exist by now is missing from the data.
            # Holding a levered overnight book through the day because Yahoo
            # was late is the worst silent failure this trader can have.
            msg = (f"ERROR: expected session {expected.strftime('%Y-%m-%d %H:%M')} has no price data "
                   f"(latest available {ts.strftime('%Y-%m-%d %H:%M')}). Positions UNCHANGED: "
                   f"{state['positions']}. Data outage or market holiday - re-run `hf trade` shortly.")
            print(msg)
            _log(msg, acct)
            raise SystemExit(2)
        print(f"Session {ts} already processed (last: {state['last_session']}). Use --force to redo.")
        return
    late_min = (pd.Timestamp(now).tz_convert(TZ) - ts).total_seconds() / 60
    if late_min > LATE_WARN_MINUTES:
        print(f"[warn] running {late_min:.0f} min after the {ts.strftime('%H:%M')} session; "
              f"fills use the {ts.strftime('%H:%M')} print (mild hindsight).")

    _mask_for_session(md, ts)
    weights = hf_ensemble_weights(md, timeline=timeline, params=params)
    if ts not in weights.index:
        raise RuntimeError(f"ensemble produced no weights for {ts}")
    target = weights.loc[ts].fillna(0.0)
    px_panel = md.px_intraday if md.px_intraday is not None and ts in md.px_intraday.index else md.px_daily
    prices = px_panel.loc[ts]

    # Never mark or trade the book with a missing price: equity would be
    # understated and a position that should be exited would be silently
    # held (this happened 2026-09-02 09:30 with IWM/QLD). Exit non-zero so
    # the scheduled retry processes the session once Yahoo has the prints.
    unpriced = [t for t in state["positions"] if pd.isna(prices.get(t, np.nan))]
    wanted = [t for t in weights.columns if abs(float(target.get(t, 0.0))) > 0 and pd.isna(prices.get(t, np.nan))]
    if unpriced or wanted:
        msg = (f"ERROR: no {ts.strftime('%H:%M')} price yet for held {unpriced} / targeted {wanted} at session "
               f"{ts.strftime('%Y-%m-%d %H:%M')}. Nothing traded; retry shortly.")
        print(msg)
        _log(msg, acct)
        raise SystemExit(2)

    # Carry since last session: cash yield on positive cash, borrow fee on shorts.
    if state["last_session"]:
        dt_years = (ts - pd.Timestamp(state["last_session"])).total_seconds() / (86400 * 365.25)
        short_val = sum(-sh * float(prices.get(t, 0.0)) for t, sh in state["positions"].items() if sh < 0)
        rf_now = md.cash_yield(cfg.cash_yield_annual)
        rf_now = float(rf_now.dropna().iloc[-1]) if isinstance(rf_now, pd.Series) else float(rf_now)
        if state["cash"] >= 0:
            state["cash"] += state["cash"] * rf_now * dt_years
        else:  # margin debit (margin2x profile) financed at T-bill + 1.5%
            state["cash"] += state["cash"] * (rf_now + 0.015) * dt_years
        state["cash"] -= short_val * (cfg.borrow_bps_annual / 1e4) * dt_years
    if state["inception"] is None:
        state["inception"] = ts.isoformat()

    equity_before = portfolio_value(state, prices)

    def build_orders(budget: float) -> list[tuple[str, float, float]]:
        out = []
        for ticker in weights.columns:
            price = prices.get(ticker)
            if price is None or pd.isna(price) or price <= 0:
                if abs(float(target.get(ticker, 0.0))) > 0:
                    print(f"[warn] no price for {ticker}; skipping")
                continue
            cur_shares = state["positions"].get(ticker, 0.0)
            delta = budget * float(target.get(ticker, 0.0)) - cur_shares * price
            if abs(delta) >= cfg.min_trade_dollars:
                out.append((ticker, float(price), delta))
        return out

    # Size targets off equity net of the costs this rebalance will incur, so a
    # 100%-long target never drives cash negative.
    est_cost = sum(abs(d) * cost_bps_for(t) / 1e4 for t, _, d in build_orders(equity_before))
    orders = build_orders(equity_before - est_cost)
    orders.sort(key=lambda o: o[2])  # sells first, frees cash for buys

    trades = []
    for ticker, price, delta in orders:
        shares_delta = delta / price
        cost = abs(delta) * cost_bps_for(ticker) / 1e4
        state["cash"] -= delta + cost
        new_shares = state["positions"].get(ticker, 0.0) + shares_delta
        if abs(new_shares * price) < 0.01:
            state["positions"].pop(ticker, None)
        else:
            state["positions"][ticker] = new_shares
        trades.append({
            "session": ts.isoformat(), "ticker": ticker,
            "side": "BUY" if delta > 0 else "SELL",
            "shares": round(shares_delta, 6), "price": round(price, 4),
            "dollars": round(delta, 2), "cost": round(cost, 4),
            "target_w": round(float(target.get(ticker, 0.0)), 4),
        })

    equity_after = portfolio_value(state, prices)
    long_val = sum(sh * float(prices.get(t, 0.0)) for t, sh in state["positions"].items() if sh > 0)
    short_val = sum(-sh * float(prices.get(t, 0.0)) for t, sh in state["positions"].items() if sh < 0)
    spy = float(prices.get("SPY", np.nan))

    state["last_session"] = ts.isoformat()
    state["sessions_processed"] += 1
    save_state(state, acct)
    if trades:
        _append_csv(acct.trades_file, trades)
    _append_csv(acct.history_file, [{
        "session": ts.isoformat(), "equity": round(equity_after, 4), "cash": round(state["cash"], 4),
        "long": round(long_val, 2), "short": round(short_val, 2), "spy": spy,
        "n_positions": len(state["positions"]), "n_trades": len(trades),
        "cost": round(sum(t["cost"] for t in trades), 4),
    }])

    label = ts.strftime("%Y-%m-%d %H:%M")
    msg = (f"{label} | equity ${equity_after:,.2f} | cash ${state['cash']:,.2f} | "
           f"long {long_val / equity_after:.0%} short {short_val / equity_after:.0%} | {len(trades)} fills")
    print(msg)
    _log(msg, acct)
    if trades:
        print(pd.DataFrame(trades)[["ticker", "side", "shares", "price", "dollars", "cost", "target_w"]]
              .to_string(index=False))
    if state["positions"]:
        rows = [{"ticker": t, "shares": round(sh, 4), "value": round(sh * float(prices.get(t, np.nan)), 2),
                 "weight": round(sh * float(prices.get(t, np.nan)) / equity_after, 4)}
                for t, sh in sorted(state["positions"].items())]
        print(pd.DataFrame(rows).to_string(index=False))
    else:
        print("Flat (100% cash).")


def status(cfg: HFConfig, plot: bool = True, account: str = "live") -> None:
    acct = Account(account)
    state = load_state(cfg, acct)
    if state["inception"] is None or not acct.history_file.exists():
        print(f"No paper history for account '{acct.name}'. Run: python3 run.py hf trade")
        return
    hist = pd.read_csv(acct.history_file, parse_dates=["session"])
    hist = hist.drop_duplicates("session", keep="last").sort_values("session")
    eq = hist.set_index("session")["equity"]
    spy = hist.set_index("session")["spy"]
    start = state["starting_cash"]
    pnl = eq.iloc[-1] - start
    spy_ret = spy.iloc[-1] / spy.iloc[0] - 1.0 if spy.notna().all() and len(spy) > 1 else float("nan")

    print(f"Account:      {acct.name}")
    print(f"Profile:      {state.get('profile')}")
    print(f"Inception:    {state['inception']}")
    print(f"Sessions:     {state['sessions_processed']}")
    print(f"Equity:       ${eq.iloc[-1]:,.2f}  (start ${start:,.2f})")
    print(f"P&L:          ${pnl:,.2f} ({pnl / start:+.2%})")
    print(f"SPY B&H same period: {spy_ret:+.2%}")
    print(f"Costs paid:   ${hist['cost'].sum():,.2f}")
    live_daily = None
    if len(eq) > 2:
        # Daily returns from end-of-day equity.
        daily_eq = eq.groupby(eq.index.tz_convert(TZ).normalize()).last()
        live_daily = daily_eq.pct_change().dropna()
        if len(live_daily) > 5:
            from .metrics import sharpe, max_drawdown
            print(f"Realized:     Sharpe {sharpe(live_daily, cfg.cash_yield_annual):.2f} | "
                  f"MaxDD {max_drawdown(live_daily):.2%} | days {len(live_daily)} | "
                  f"avg |daily| {live_daily.abs().mean():.2%}")
    _expectation_check(cfg, state, live_daily, hist)  # noqa
    if state["positions"]:
        print("\nPositions:")
        for t, sh in sorted(state["positions"].items()):
            print(f"  {t:<6} {sh:>10.4f} sh")
    else:
        print("\nFlat (100% cash).")
    if acct.trades_file.exists():
        tr = pd.read_csv(acct.trades_file)
        print(f"\nLast fills ({len(tr)} total):")
        print(tr.tail(8).to_string(index=False))
    if plot and len(eq) > 1:
        _plot_status(hist, start, acct)


def _expectation_check(cfg: HFConfig, state: dict, live_daily: pd.Series | None, hist: pd.DataFrame) -> None:
    """Compare the live track to what the backtest says is normal.

    The backtest's daily return distribution (for the account's profile) gives
    an expected cumulative return after N days and a 2-sigma band around it.
    Inside the band = behaving as designed, regardless of sign. Below the band
    for a sustained period = investigate (data, fills, regime) before touching
    parameters. Also reports how many days are needed before the realized
    Sharpe becomes informative.
    """
    from .strategies.hf_ensemble import EnsembleParams, config_for, hf_ensemble_weights
    from .engine import run_session_backtest

    try:
        params = EnsembleParams.from_profile(state.get("profile"))
        md = MarketData(config_for(params), refresh=False, intraday=False)
        w = hf_ensemble_weights(md, timeline="daily", params=params)
        bt = run_session_backtest(w, md.px_daily, cash_yield_annual=md.cash_yield(cfg.cash_yield_annual),
                                  label=state.get("profile", ""))
    except Exception as exc:  # noqa: BLE001 - status must never crash on this
        print(f"\n[expectation check unavailable: {exc}]")
        return
    r = bt.daily_returns
    mu, sd = r.mean(), r.std()
    hit = (r > 0).mean()
    n = len(live_daily) if live_daily is not None else 0
    print("\nExpectation card (backtest 2010->now, same profile, net of costs):")
    print(f"  daily mean {mu:+.3%} | daily sd {sd:.3%} | positive days {hit:.0%} | "
          f"Sharpe {bt.stats['sharpe']:.2f} | MaxDD {bt.stats['max_drawdown']:.1%} | "
          f"typical exposure {bt.stats['avg_long']:.0%}")
    if n >= 1 and live_daily is not None:
        live_cum = (1 + live_daily).prod() - 1
        exp_cum = mu * n
        band = 2 * sd * np.sqrt(n)
        z = (live_cum - exp_cum) / (sd * np.sqrt(n)) if sd > 0 else float("nan")
        verdict = "inside the 2-sigma band" if abs(z) <= 2 else ("ABOVE band" if z > 2 else "BELOW band - investigate")
        print(f"  after {n} days: live {live_cum:+.2%} vs expected {exp_cum:+.2%} +/- {band:.2%}  "
              f"(z = {z:+.2f}) -> {verdict}")
        print(f"  live positive days {(live_daily > 0).mean():.0%} (expected {hit:.0%}) | "
              f"live daily sd {live_daily.std():.3%} (expected {sd:.3%})")
    days_for_sig = int(np.ceil((2.0 / max(bt.stats['sharpe'], 1e-6)) ** 2 * 252))
    print(f"  days of live data before a Sharpe of {bt.stats['sharpe']:.2f} is distinguishable from 0 "
          f"at 2 sigma: ~{days_for_sig} (~{days_for_sig / 252:.1f} years). Judge shape, not sign, before then.")
    missed = _missed_sessions(md, hist)
    if missed:
        print(f"  [warn] {len(missed)} scheduled session(s) not processed since inception, latest: {missed[-1]}")


def _missed_sessions(md: MarketData, hist: pd.DataFrame) -> list[str]:
    done = set(pd.to_datetime(hist["session"], utc=True).dt.tz_convert(TZ))
    first = min(done)
    expected = md.px_daily.index[(md.px_daily.index > first) & (md.px_daily.index <= pd.Timestamp.now(tz=TZ))]
    return [t.strftime("%Y-%m-%d %H:%M") for t in expected if t not in done]


def _plot_status(hist: pd.DataFrame, start: float, acct: Account) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    h = hist.set_index("session")
    eq, spy = h["equity"], h["spy"]
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1, 1]})
    axes[0].plot(eq.index, eq.values, label="quantbot HF (paper)", lw=1.6)
    if spy.notna().all():
        axes[0].plot(spy.index, spy.values / spy.iloc[0] * start, label="SPY buy & hold", lw=1.1, alpha=0.8)
    axes[0].axhline(start, color="grey", lw=0.8, ls="--")
    axes[0].set_ylabel("Equity ($)")
    axes[0].grid(alpha=0.3)
    axes[0].legend()
    axes[0].set_title(f"Paper account '{acct.name}' since inception ({len(h)} sessions)")

    dd = eq / eq.cummax() - 1.0
    axes[1].fill_between(dd.index, dd.values, 0, alpha=0.6)
    axes[1].set_ylabel("Drawdown")
    axes[1].grid(alpha=0.3)

    expo = (h["long"] + h["short"]) / eq
    axes[2].step(expo.index, expo.values, where="post", lw=1.0, label="gross exposure")
    trades = h["n_trades"]
    axes[2].bar(trades.index, trades.values / max(trades.max(), 1), width=0.15, alpha=0.35,
                label=f"fills per session (max {int(trades.max())})")
    axes[2].set_ylabel("Exposure / fills")
    axes[2].set_ylim(0, 1.15)
    axes[2].grid(alpha=0.3)
    axes[2].legend(loc="upper left")

    out = acct.dir / "equity.png"
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print(f"\nSaved chart: {out}")
