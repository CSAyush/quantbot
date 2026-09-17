"""Alpaca execution for the HF system (paper account first, live later).

Why this exists: the simulated accounts fill at the official auction print.
A real broker fills a market-on-open (MOO) / market-on-close (MOC) order at
that same auction, but the order has to be *submitted beforehand* (Alpaca
accepts MOO until 09:28 ET and MOC until 15:50 ET), so the decision must be
made from a live estimate of the session price. This module does that and
then measures how far the real fill landed from the official print - the one
number the simulation could never give us.

Per trading day, three steps (scheduled by GitHub Actions):
  submit --session open   (~09:18 ET)  estimate today's opens from the latest
                                        pre-market trades, compute targets at
                                        the 09:30 stamp, send MOO orders
  submit --session close  (~15:44 ET)  estimate today's closes from the latest
                                        trades, compute targets at 16:00, send MOC
  reconcile               (~09:40 / ~16:20 ET, inside `hf trade`)  read the
                                        fills, update the account, record
                                        fill-vs-print slippage

Sizing: whole shares (auction orders cannot be fractional), so this account
runs at a larger notional (default $10,000 of the paper balance). Compare it
to the simulated accounts in percent.

Credentials: .alpaca.env in the repo root (gitignored) or environment
variables ALPACA_KEY_ID / ALPACA_SECRET_KEY / ALPACA_PAPER.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import zoneinfo

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, HFConfig
from .data import ET, MarketData, daily_session_prices

TZ = zoneinfo.ZoneInfo(ET)
ENV_FILE = PROJECT_ROOT / ".alpaca.env"
CLIENT_ID_PREFIX = "qb"
# Alpaca accepts MOO until 09:28 ET and MOC from the open until 15:50 ET.
# The close window starts after the open auction so the day's exits are done
# (Alpaca rejects a buy while a sell is open on the same symbol). A close
# estimate made before REFINE_FROM is replaced by a later in-window run.
SUBMIT_WINDOWS = {"open": (dt.time(8, 45), dt.time(9, 28)), "close": (dt.time(9, 40), dt.time(15, 50))}
REFINE_FROM = dt.time(15, 10)


# --------------------------------------------------------------------------- credentials / clients
def load_credentials() -> dict:
    creds = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("ALPACA_KEY_ID", "ALPACA_SECRET_KEY", "ALPACA_PAPER"):
        if os.environ.get(k):
            creds[k] = os.environ[k]
    if not creds.get("ALPACA_KEY_ID") or not creds.get("ALPACA_SECRET_KEY"):
        raise RuntimeError(f"Alpaca credentials missing: put ALPACA_KEY_ID / ALPACA_SECRET_KEY in {ENV_FILE} "
                           "or the environment")
    creds["paper"] = str(creds.get("ALPACA_PAPER", "true")).lower() in ("1", "true", "yes")
    return creds


def trading_client():
    from alpaca.trading.client import TradingClient
    c = load_credentials()
    return TradingClient(c["ALPACA_KEY_ID"], c["ALPACA_SECRET_KEY"], paper=c["paper"])


def data_client():
    from alpaca.data.historical import StockHistoricalDataClient
    c = load_credentials()
    return StockHistoricalDataClient(c["ALPACA_KEY_ID"], c["ALPACA_SECRET_KEY"])


def to_alpaca(sym: str) -> str:
    """Yahoo 'BRK-B' -> Alpaca 'BRK.B'."""
    return sym.replace("-", ".")


def from_alpaca(sym: str) -> str:
    return sym.replace(".", "-")


def latest_trades(symbols: list[str]) -> pd.Series:
    """Latest trade price per (Yahoo-style) symbol from the free IEX feed
    (includes pre-market prints where they exist). Missing symbols are NaN."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockLatestTradeRequest
    out = pd.Series(np.nan, index=symbols, dtype=float)
    dc = data_client()
    for i in range(0, len(symbols), 200):
        batch = [to_alpaca(s) for s in symbols[i:i + 200]]
        try:
            res = dc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=batch, feed=DataFeed.IEX))
        except Exception as exc:  # noqa: BLE001
            print(f"[alpaca] latest-trade request failed for a batch: {exc}")
            continue
        for sym, tr in res.items():
            out[from_alpaca(sym)] = float(tr.price)
    return out


# --------------------------------------------------------------------------- targets from a live estimate
def _estimate_session_targets(md: MarketData, session: str, now: pd.Timestamp, params) -> tuple[pd.Timestamp, pd.Series, pd.Series]:
    """Inject live prices as today's Open (open session) or Close (close
    session), then compute the ensemble target row at the session stamp.
    Returns (stamp, targets, estimated_prices)."""
    from .strategies.hf_ensemble import hf_ensemble_weights
    from .hf_paper import _mask_for_session

    today = now.tz_localize(None).normalize()
    tickers = list(md.tickers)
    for f in ["Open", "High", "Low", "Close", "Volume", "AdjFactor"]:
        if today not in md.daily[f].index:
            md.daily[f].loc[today] = np.nan
            md.daily[f] = md.daily[f].sort_index()

    live = latest_trades(tickers)
    n_live = int(live.notna().sum())
    print(f"[alpaca] live prices for {n_live}/{len(tickers)} names")
    if n_live < 0.5 * len(tickers):
        raise RuntimeError("too few live prices to estimate the session; not submitting")

    if session == "open":
        # Names with no pre-market print: fall back to yesterday's close (gap = 0,
        # so the reversal sleeve will not pick them; the overnight sleeve's exit
        # does not depend on the level).
        yday_close = md.daily["Close"].loc[:today].iloc[-2]
        est = live.fillna(yday_close)
        md.daily["Open"].loc[today] = est.values
        stamp = (today + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    else:
        est = live.fillna(md.daily["Close"].loc[:today].iloc[-2])
        for f in ["Open", "High", "Low", "Close"]:
            if md.daily[f].loc[today].isna().all():
                md.daily[f].loc[today] = est.values
        md.daily["Close"].loc[today] = est.values
        stamp = (today + pd.Timedelta(hours=16)).tz_localize(ET)
    md.px_daily = daily_session_prices(md.daily)

    _mask_for_session(md, stamp)
    if session == "close":
        # The mask blanks nothing at 16:00. The ts_reversal sleeve gates on
        # today's VIX close, so estimate it from the latest 1m bar (else
        # yesterday's value carries forward, logged).
        from .hf_paper import _fill_today_aux
        _fill_today_aux(md, today, final=False)
    weights = hf_ensemble_weights(md, timeline="daily", params=params)
    if stamp not in weights.index:
        raise RuntimeError(f"no ensemble weights at {stamp}")
    return stamp, weights.loc[stamp].fillna(0.0), est


# --------------------------------------------------------------------------- state
def _blank_state(notional: float, profile: str) -> dict:
    return {"type": "alpaca", "profile": profile, "notional": notional, "starting_cash": notional,
            "cash": notional, "positions": {}, "inception": None, "last_session": None,
            "sessions_processed": 0, "pending": {}}


def submit(acct, cfg: HFConfig, session: str, now: dt.datetime | None = None) -> None:
    """Estimate the session price, compute targets, send MOO/MOC orders."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
    from .calendar import is_trading_day
    from .hf_paper import _log, load_state, save_state
    from .strategies.hf_ensemble import EnsembleParams, config_for

    now_ts = pd.Timestamp(now or dt.datetime.now(tz=TZ)).tz_convert(TZ)
    if not is_trading_day(now_ts):
        print(f"{now_ts.date()} is not a trading day; nothing to submit.")
        return
    window_start, deadline = SUBMIT_WINDOWS[session]
    if now_ts.time() < window_start:
        print(f"{now_ts.strftime('%H:%M')} ET is before the {session} submission window "
              f"({window_start}-{deadline}); nothing to do.")
        return
    if now_ts.time() >= deadline:
        late_min = (now_ts - now_ts.replace(hour=deadline.hour, minute=deadline.minute, second=0)).total_seconds() / 60
        if late_min > 15:
            # A stray cron (GitHub schedules run hours late); the evening queue covers the next session.
            print(f"{now_ts.strftime('%H:%M')} ET is well past the {session} window; nothing to do.")
            return
        msg = f"ERROR: {now_ts.strftime('%H:%M')} ET is past the {session} submission deadline {deadline}; not submitting"
        print(msg); _log(msg, acct)
        raise SystemExit(2)

    state = load_state(cfg, acct)
    params = EnsembleParams.from_profile(state["profile"])
    cfg = config_for(params)
    md = MarketData(cfg, refresh=True, intraday=False)
    if session == "close":
        # Book this morning's exits first so cash and positions are current.
        from .hf_paper import _inject_live_prints
        _inject_live_prints(md, now_ts)
        earlier = [v for v in state.get("pending", {}).values()
                   if pd.Timestamp(v["stamp"]) < now_ts.normalize() + pd.Timedelta(hours=16)]
        if earlier:
            reconcile(acct, cfg, md, now=now_ts)
            state = load_state(cfg, acct)
    stamp, target, est = _estimate_session_targets(md, session, now_ts, params)
    if state.get("last_session") and pd.Timestamp(state["last_session"]) >= stamp:
        print(f"[alpaca] session {stamp} already reconciled; nothing to do")
        return
    client = trading_client()
    same = {k: v for k, v in state.get("pending", {}).items() if v["stamp"] == stamp.isoformat()}
    if same:
        # Idempotent, with one exception: a close estimate made early in the
        # day is replaced once by a run that lands in the refinement window.
        est_times = [pd.Timestamp(v["est_time"]).tz_convert(TZ).time() for v in same.values() if v.get("est_time")]
        refine = (session == "close" and now_ts.time() >= REFINE_FROM
                  and est_times and all(t < REFINE_FROM for t in est_times))
        if not refine:
            print(f"[alpaca] orders for {stamp} already submitted; nothing to do")
            return
        for coid, v in same.items():
            try:
                client.cancel_order_by_id(v["order_id"])
            except Exception as exc:  # noqa: BLE001
                print(f"[alpaca] could not cancel {v['symbol']} order: {exc}")
            state["pending"].pop(coid, None)
        print(f"[alpaca] replaced {len(same)} early close estimate(s) with a {now_ts.strftime('%H:%M')} estimate")
    other = [v for v in state.get("pending", {}).values() if v["stamp"] != stamp.isoformat()]
    if other:
        print(f"[alpaca] note: {len(other)} order(s) pending for other sessions")
    # Broker truth for current holdings of the symbols we trade.
    held = {from_alpaca(p.symbol): float(p.qty) for p in client.get_all_positions()}
    equity = state["cash"] + sum(q * float(est.get(s, np.nan)) for s, q in held.items() if not np.isnan(est.get(s, np.nan)))

    tif = TimeInForce.OPG if session == "open" else TimeInForce.CLS
    orders, pending = [], {}
    for sym in target.index:
        px = float(est.get(sym, np.nan))
        if np.isnan(px) or px <= 0:
            if abs(float(target[sym])) > 0:
                print(f"[alpaca] no live price for {sym}; skipping")
            continue
        want_qty = int(round(equity * float(target[sym]) / px))       # whole shares
        delta = want_qty - int(held.get(sym, 0))
        if delta == 0:
            continue
        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        coid = f"{CLIENT_ID_PREFIX}-{stamp.strftime('%Y%m%d-%H%M')}-{sym}"
        try:
            o = client.submit_order(MarketOrderRequest(symbol=to_alpaca(sym), qty=abs(delta), side=side,
                                                       time_in_force=tif, client_order_id=coid))
        except Exception as exc:  # noqa: BLE001
            print(f"[alpaca] order rejected {sym} {side.value} {abs(delta)}: {exc}")
            continue
        orders.append((sym, side.value, abs(delta), px, float(target[sym])))
        pending[coid] = {"symbol": sym, "side": side.value, "qty": abs(delta), "est_price": px,
                         "target_w": float(target[sym]), "order_id": str(o.id), "stamp": stamp.isoformat(),
                         "est_time": now_ts.isoformat()}

    state["pending"].update(pending)
    save_state(state, acct)
    msg = (f"{stamp.strftime('%Y-%m-%d %H:%M')} SUBMIT {session}: {len(orders)} {tif.value} orders "
           f"(equity est ${equity:,.2f}, live px for {int(est.notna().sum())} names)")
    print(msg); _log(msg, acct)
    for sym, side, qty, px, w in orders:
        print(f"   {sym:<6} {side:<4} {qty:>4} sh @~{px:.2f}  target {w:.3f}")


def reconcile(acct, cfg: HFConfig, md: MarketData, now: dt.datetime | None = None) -> None:
    """Read fills for pending orders, update the account, record slippage
    against the official print, and mark the session processed."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    from .hf_paper import _append_csv, _log, load_state, save_state

    state = load_state(cfg, acct)
    pending = state.get("pending", {})
    now_ts = pd.Timestamp(now or dt.datetime.now(tz=TZ)).tz_convert(TZ)
    if not pending:
        print("[alpaca] nothing pending to reconcile")
        return
    stamps = sorted({v["stamp"] for v in pending.values()})
    stamp = pd.Timestamp(stamps[0])
    if now_ts < stamp + pd.Timedelta(minutes=5):
        print(f"[alpaca] session {stamp} not over yet; reconcile later")
        return
    if stamp not in md.px_daily.index:
        msg = f"ERROR: official {stamp.strftime('%H:%M')} prints not available yet for {stamp.date()}; retry shortly"
        print(msg); _log(msg, acct)
        raise SystemExit(2)
    official = md.px_daily.loc[stamp]

    client = trading_client()
    since = (stamp - pd.Timedelta(hours=8)).tz_convert("UTC").to_pydatetime()
    closed = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=since, limit=500))
    by_coid = {o.client_order_id: o for o in closed}

    fills, still_pending, cost_total = [], {}, 0.0
    for coid, p in pending.items():
        if p["stamp"] != stamps[0]:
            still_pending[coid] = p
            continue
        o = by_coid.get(coid)
        if o is None or o.filled_qty is None or float(o.filled_qty) == 0:
            status = getattr(o, "status", "not found")
            msg = f"[alpaca] {p['symbol']} order {coid} not filled ({status})"
            print(msg); _log(msg, acct)
            continue
        qty = float(o.filled_qty) * (1 if p["side"] == "buy" else -1)
        fill_px = float(o.filled_avg_price)
        print_px = float(official.get(p["symbol"], np.nan))
        slip_bps = (fill_px / print_px - 1.0) * 1e4 * (1 if qty > 0 else -1) if not np.isnan(print_px) else np.nan
        dollars = qty * fill_px
        state["cash"] -= dollars
        new_q = state["positions"].get(p["symbol"], 0.0) + qty
        if abs(new_q) < 1e-9:
            state["positions"].pop(p["symbol"], None)
        else:
            state["positions"][p["symbol"]] = new_q
        fills.append({"session": stamp.isoformat(), "ticker": p["symbol"], "side": p["side"].upper(),
                      "shares": qty, "fill_price": round(fill_px, 4), "official_print": round(print_px, 4),
                      "slippage_bps": round(slip_bps, 2), "est_price_at_submit": round(p["est_price"], 4),
                      "dollars": round(dollars, 2), "target_w": p["target_w"],
                      "filled_at": str(getattr(o, "filled_at", ""))})
    state["pending"] = still_pending
    if state["inception"] is None:
        state["inception"] = stamp.isoformat()

    equity = state["cash"] + sum(q * float(official.get(s, np.nan)) for s, q in state["positions"].items()
                                 if not np.isnan(official.get(s, np.nan)))
    long_val = sum(q * float(official.get(s, 0.0)) for s, q in state["positions"].items() if q > 0)
    try:
        broker_equity = float(client.get_account().equity)
    except Exception:  # noqa: BLE001
        broker_equity = np.nan
    state["last_session"] = stamp.isoformat()
    state["sessions_processed"] += 1
    save_state(state, acct)
    if fills:
        _append_csv(acct.trades_file, fills)
    _append_csv(acct.history_file, [{
        "session": stamp.isoformat(), "equity": round(equity, 4), "cash": round(state["cash"], 4),
        "long": round(long_val, 2), "short": 0.0, "spy": float(official.get("SPY", np.nan)),
        "n_positions": len(state["positions"]), "n_trades": len(fills),
        "cost": 0.0, "broker_equity": broker_equity,
        "avg_slippage_bps": round(float(np.nanmean([f["slippage_bps"] for f in fills])), 2) if fills else np.nan,
    }])
    slip = [f["slippage_bps"] for f in fills if not np.isnan(f["slippage_bps"])]
    msg = (f"{stamp.strftime('%Y-%m-%d %H:%M')} RECONCILE: {len(fills)} fills | equity ${equity:,.2f} "
           f"(broker ${broker_equity:,.2f}) | avg slippage vs print {np.mean(slip):+.1f} bp" if slip else
           f"{stamp.strftime('%Y-%m-%d %H:%M')} RECONCILE: {len(fills)} fills | equity ${equity:,.2f}")
    print(msg); _log(msg, acct)
    if fills:
        print(pd.DataFrame(fills)[["ticker", "side", "shares", "fill_price", "official_print", "slippage_bps"]]
              .to_string(index=False))


def queue_next_session(acct, cfg: HFConfig, now: dt.datetime | None = None) -> None:
    """Evening job (19:00 ET -> 08:30 ET): Alpaca queues MOO/MOC orders
    submitted after 19:00 ET for the next session, so this is the
    timing-proof baseline for the exits: queues market-on-open SELLS of every
    held position (the overnight sleeve always exits at the open). Close
    entries are placed during the day by `submit("close")` (09:40-15:50 ET),
    and reversal-sleeve entries by an in-window morning run."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
    from .calendar import is_trading_day
    from .hf_paper import _inject_live_prints, _log, load_state, save_state
    from .strategies.hf_ensemble import EnsembleParams, config_for

    now_ts = pd.Timestamp(now or dt.datetime.now(tz=TZ)).tz_convert(TZ)
    if not (now_ts.time() >= dt.time(19, 0) or now_ts.time() < dt.time(8, 30)):
        print(f"{now_ts.strftime('%H:%M')} ET is outside the evening queue window (19:00-08:30); nothing to do.")
        return
    # Next trading day.
    d = now_ts.normalize() + (pd.Timedelta(days=1) if now_ts.time() >= dt.time(19, 0) else pd.Timedelta(0))
    while not is_trading_day(d):
        d += pd.Timedelta(days=1)
    open_stamp = d + pd.Timedelta(hours=9, minutes=30)
    state = load_state(cfg, acct)
    params = EnsembleParams.from_profile(state["profile"])
    cfg = config_for(params)
    md = MarketData(cfg, refresh=True, intraday=False)
    _inject_live_prints(md, now_ts)
    if state.get("pending"):
        reconcile(acct, cfg, md, now=now_ts)
        state = load_state(cfg, acct)
    if any(v["stamp"] == open_stamp.isoformat() for v in state.get("pending", {}).values()):
        print(f"[alpaca] orders for {d.date()} already queued; nothing to do")
        return

    client = trading_client()
    held = {from_alpaca(p.symbol): float(p.qty) for p in client.get_all_positions()}
    last_close_stamp = md.px_daily.index[md.px_daily.index.hour == 16][-1]
    close_px = md.px_daily.loc[last_close_stamp]
    equity = state["cash"] + sum(q * float(close_px.get(s, 0.0)) for s, q in held.items())

    pending, lines = {}, []
    # (a) exits at the open
    for sym, q in held.items():
        if q <= 0:
            continue
        coid = f"{CLIENT_ID_PREFIX}-{open_stamp.strftime('%Y%m%d-%H%M')}-{sym}"
        try:
            o = client.submit_order(MarketOrderRequest(symbol=to_alpaca(sym), qty=int(q), side=OrderSide.SELL,
                                                       time_in_force=TimeInForce.OPG, client_order_id=coid))
        except Exception as exc:  # noqa: BLE001
            print(f"[alpaca] OPG sell rejected {sym}: {exc}")
            continue
        pending[coid] = {"symbol": sym, "side": "sell", "qty": int(q), "est_price": float(close_px.get(sym, np.nan)),
                         "target_w": 0.0, "order_id": str(o.id), "stamp": open_stamp.isoformat(), "queued_estimate": True}
        lines.append(f"   {sym:<6} SELL {int(q):>4} sh  MOO {d.date()}")
    # Close entries cannot be queued alongside the exits (Alpaca rejects a buy
    # while a sell is open on the same symbol); `submit("close")` places them
    # any time between 09:40 and 15:50 ET.
    state.setdefault("pending", {}).update(pending)
    save_state(state, acct)
    msg = f"QUEUE for {d.date()}: {len(pending)} orders (equity est ${equity:,.2f})"
    print(msg); _log(msg, acct)
    for ln in lines:
        print(ln)


def reconcile_now(acct, cfg: HFConfig, now: dt.datetime | None = None, refresh: bool = True) -> None:
    """Build market data with today's official prints and reconcile."""
    from .hf_paper import _inject_live_prints, load_state
    from .strategies.hf_ensemble import EnsembleParams, config_for

    state = load_state(cfg, acct)
    if not state.get("pending"):
        print("[alpaca] nothing pending to reconcile")
        return
    params = EnsembleParams.from_profile(state["profile"])
    md = MarketData(config_for(params), refresh=refresh, intraday=False)
    now_ts = pd.Timestamp(now or dt.datetime.now(tz=TZ)).tz_convert(TZ)
    _inject_live_prints(md, now_ts)
    reconcile(acct, cfg, md, now=now_ts)


def auto_session(now: dt.datetime | None = None) -> str:
    """Which action the wall clock calls for: evening queue, open refinement,
    or close refinement."""
    now_ts = pd.Timestamp(now or dt.datetime.now(tz=TZ)).tz_convert(TZ)
    t = now_ts.time()
    if t >= dt.time(19, 0) or t < dt.time(8, 30):
        return "queue"
    return "open" if t < dt.time(12, 0) else "close"


def run_auto(acct, cfg: HFConfig, session: str = "auto", now: dt.datetime | None = None) -> None:
    session = auto_session(now) if session == "auto" else session
    if session == "queue":
        queue_next_session(acct, cfg, now=now)
    else:
        submit(acct, cfg, session=session, now=now)


def check_connection() -> None:
    client = trading_client()
    a = client.get_account()
    c = load_credentials()
    print(f"Connected to Alpaca ({'PAPER' if c['paper'] else 'LIVE'}) account {a.account_number}: "
          f"status {a.status}, equity ${float(a.equity):,.2f}, buying power ${float(a.buying_power):,.2f}")
    clock = client.get_clock()
    print(f"Market {'open' if clock.is_open else 'closed'}; next open {clock.next_open}, next close {clock.next_close}")
