"""Market data loading with local caching and multiple sources.

Source priority:
  1. local parquet cache (data_cache/close.parquet) if it covers the window
  2. Yahoo Finance via yfinance (primary live source)
  3. offline S&P 500 dataset (data_cache/sp500/data/<TICKER>.parquet) - a
     GitHub-hosted mirror of daily adjusted closes, useful when Yahoo is
     unreachable. Refresh it with scripts in README or re-download the
     release tarball.

All prices are split/dividend adjusted daily closes.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE_DIR

LOCAL_DATASET_DIR = CACHE_DIR / "sp500" / "data"


def _cache_path() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / "close.parquet"


def _load_cache(tickers: list[str], start: str, end: str | None) -> pd.DataFrame | None:
    path = _cache_path()
    if not path.exists():
        return None
    close = pd.read_parquet(path)
    if not set(tickers).issubset(close.columns):
        return None
    end_dt = pd.Timestamp(end) if end else pd.Timestamp(dt.date.today())
    covers_start = close.index.min() <= pd.Timestamp(start) + pd.Timedelta(days=7)
    covers_end = end_dt - close.index.max() <= pd.Timedelta(days=5)
    if covers_start and covers_end:
        return close[tickers]
    return None


def _fetch_yahoo(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if raw is None or raw.empty:
        raise RuntimeError("Yahoo Finance returned no data")
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = tickers
    close = close.sort_index().dropna(how="all")
    missing = [t for t in tickers if t not in close.columns or close[t].isna().all()]
    if missing:
        raise RuntimeError(f"Yahoo Finance returned no data for: {missing}")
    return close[tickers]


def _fetch_local_dataset(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
    if not LOCAL_DATASET_DIR.exists():
        raise RuntimeError(
            f"Offline dataset not found at {LOCAL_DATASET_DIR}. "
            "Download it with: curl -L -o /tmp/d.tar.gz "
            "https://github.com/irresi/bl-view-mcp/releases/download/data-snp500-latest/data.tar.gz "
            f"&& mkdir -p {LOCAL_DATASET_DIR.parent} && tar -xzf /tmp/d.tar.gz -C {LOCAL_DATASET_DIR.parent}"
        )
    series = {}
    missing = []
    for t in tickers:
        p = LOCAL_DATASET_DIR / f"{t}.parquet"
        if p.exists():
            series[t] = pd.read_parquet(p)["Close"]
        else:
            missing.append(t)
    if not series:
        raise RuntimeError("Offline dataset contains none of the requested tickers")
    close = pd.DataFrame(series).sort_index()
    close = close.loc[pd.Timestamp(start):]
    if end:
        close = close.loc[:pd.Timestamp(end)]
    if missing:
        print(f"[data] offline dataset missing {missing} - proceeding without them")
    return close


def fetch_prices(
    tickers: list[str],
    start: str,
    end: str | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Adjusted close prices (index=date, one column per ticker)."""
    if not refresh:
        cached = _load_cache(tickers, start, end)
        if cached is not None:
            return cached

    try:
        close = _fetch_yahoo(tickers, start, end)
        source = "yahoo"
    except Exception as exc:  # network blocked, rate limited, etc.
        print(f"[data] Yahoo fetch failed ({type(exc).__name__}), "
              f"falling back to offline dataset")
        close = _fetch_local_dataset(tickers, start, end)
        source = "offline"

    close.to_parquet(_cache_path())
    print(f"[data] loaded {close.shape[1]} tickers x {close.shape[0]} days "
          f"from {source} ({close.index.min().date()} -> {close.index.max().date()})")
    return close


# ---------------------------------------------------------------------------
# OHLCV + intraday data for the short-horizon system
# ---------------------------------------------------------------------------

ET = "America/New_York"
FIELDS = ["Open", "High", "Low", "Close", "Volume"]
# yfinance history limits per interval (lookback window it will serve).
INTRADAY_PERIOD = {"1m": "7d", "2m": "60d", "5m": "60d", "15m": "60d",
                   "30m": "60d", "60m": "730d", "1h": "730d", "90m": "60d"}


def _download(tickers: list[str], adjust_from_adjclose: bool = False, **kw) -> dict[str, pd.DataFrame]:
    """yf.download wrapper returning {field: DataFrame(index=time, cols=tickers)}.

    With `adjust_from_adjclose`, downloads raw prices plus 'Adj Close' and
    applies the total-return factor (AdjClose/Close) to OHLC itself, keeping
    the factor as an extra 'AdjFactor' field so intraday bars (which Yahoo
    serves unadjusted for dividends) can be put on the same basis.
    """
    import time

    import yfinance as yf

    fields = FIELDS + (["Adj Close"] if adjust_from_adjclose else [])
    raw = None
    for attempt, pause in enumerate((0, 20, 60)):
        if pause:
            print(f"[data] Yahoo returned nothing; retrying in {pause}s (attempt {attempt + 1}/3)")
            time.sleep(pause)
        try:
            raw = yf.download(tickers, progress=False, group_by="column", threads=True,
                              auto_adjust=not adjust_from_adjclose, **kw)
        except Exception as exc:  # noqa: BLE001 - network hiccup, retry
            print(f"[data] download error: {type(exc).__name__}: {exc}")
            raw = None
        if raw is not None and not raw.empty:
            break
    if raw is None or raw.empty:
        raise RuntimeError("Yahoo Finance returned no data after 3 attempts")

    def get(f: str) -> pd.DataFrame:
        if isinstance(raw.columns, pd.MultiIndex):
            df = raw[f].copy()
        else:
            df = raw[[f]].copy()
            df.columns = tickers
        return df.reindex(columns=tickers).sort_index()

    out = {f: get(f) for f in fields}
    if adjust_from_adjclose:
        factor = (out["Adj Close"] / out["Close"]).replace([np.inf, -np.inf], np.nan)
        for f in ["Open", "High", "Low", "Close"]:
            out[f] = out[f] * factor
        out["AdjFactor"] = factor
        del out["Adj Close"]
    return out


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write to a temp file then rename, so a crash or a concurrent reader
    (e.g. the launchd job and a manual run) never sees a half-written file."""
    import os
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    df.to_parquet(tmp)
    os.replace(tmp, path)


def _panel_path(interval: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"ohlcv_{interval}.parquet"


def _to_panel(fields: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(fields, axis=1)  # columns: MultiIndex (field, ticker)


def _from_panel(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {f: panel[f] for f in panel.columns.levels[0] if f in panel.columns.get_level_values(0)}


def _merge_panels(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """New data wins where it exists; old data is kept where the new download
    is empty (Yahoo rate-limits large requests and returns all-NaN columns -
    those must never overwrite good history)."""
    if old is None:
        return new
    cols = sorted(set(old.columns) | set(new.columns))
    idx = old.index.union(new.index)
    combined = new.reindex(index=idx, columns=cols).combine_first(old.reindex(index=idx, columns=cols))
    return combined.sort_index()


def _retry_empty(fields: dict[str, pd.DataFrame], tickers: list[str], **kw) -> dict[str, pd.DataFrame]:
    """Re-download tickers that came back all-NaN, in small batches."""
    empty = [t for t in tickers if fields["Close"][t].isna().all()]
    for attempt in range(2):
        if not empty:
            break
        print(f"[data] {len(empty)} tickers returned no data; retrying in small batches (attempt {attempt + 1})")
        for i in range(0, len(empty), 25):
            batch = empty[i:i + 25]
            try:
                part = _download(batch, **kw)
            except Exception as exc:  # noqa: BLE001
                print(f"[data] retry batch failed: {exc}")
                continue
            for f, df in part.items():
                if f in fields:
                    fields[f].loc[:, batch] = df.reindex(index=fields[f].index, columns=batch)
        empty = [t for t in tickers if fields["Close"][t].isna().all()]
    if empty:
        print(f"[data] WARNING: still no data for {len(empty)} tickers: {empty[:15]}{'...' if len(empty) > 15 else ''}")
    return fields


def fetch_ohlcv(
    tickers: list[str],
    start: str,
    end: str | None = None,
    refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """Daily adjusted OHLCV for `tickers`. Cached in data_cache/ohlcv_1d.parquet;
    the cache is extended (not replaced) on each refresh so history accumulates."""
    path = _panel_path("1d")
    panel = pd.read_parquet(path) if path.exists() else None

    need_fetch = refresh or panel is None
    if panel is not None and not need_fetch:
        have = set(panel.columns.get_level_values(1))
        end_dt = pd.Timestamp(end) if end else pd.Timestamp(dt.date.today())
        stale = end_dt - panel.index.max() > pd.Timedelta(days=4)
        need_fetch = (not set(tickers).issubset(have)) or stale \
            or panel.index.min() > pd.Timestamp(start) + pd.Timedelta(days=10)

    if need_fetch:
        fields = _download(tickers, adjust_from_adjclose=True, start=start, end=end)
        fields = _retry_empty(fields, tickers, adjust_from_adjclose=True, start=start, end=end)
        new = _to_panel(fields)
        new.index = pd.DatetimeIndex(new.index).tz_localize(None).normalize()
        # Yahoo serves a row for the current day while the market is open. Its
        # Open can be yesterday's (observed 2026-09-03) and its Close is just
        # the last trade. Drop it until the session is over; the paper trader
        # sources today's prints from 1-minute bars instead.
        now_et = pd.Timestamp.now(tz=ET)
        if now_et.time() < dt.time(16, 10):
            today = now_et.tz_localize(None).normalize()
            new = new[new.index < today]
        panel = _merge_panels(panel, new) if panel is not None else new
        _atomic_to_parquet(panel, path)
        print(f"[data] daily OHLCV: {len(tickers)} tickers, "
              f"{panel.index.min().date()} -> {panel.index.max().date()}")

    panel = panel.loc[pd.Timestamp(start):]
    if end:
        panel = panel.loc[:pd.Timestamp(end)]
    fields = _from_panel(panel)
    present = [t for t in tickers if t in fields["Close"].columns]
    missing = sorted(set(tickers) - set(present))
    if missing:
        print(f"[data] no daily data for {missing}")
    return {f: df[present] for f, df in fields.items()}


def fetch_intraday(
    tickers: list[str],
    interval: str = "1h",
    refresh: bool = True,
) -> dict[str, pd.DataFrame]:
    """Intraday bars. Yahoo only serves a trailing window (730d for 1h, 60d for
    5m/15m/30m, 7d for 1m), so every call appends to a persistent cache - the
    longer the bot runs, the more intraday history it accumulates."""
    path = _panel_path(interval)
    panel = pd.read_parquet(path) if path.exists() else None

    if refresh or panel is None:
        fields = _download(tickers, period=INTRADAY_PERIOD[interval], interval=interval,
                           prepost=False)
        new = _to_panel(fields)
        idx = pd.DatetimeIndex(new.index)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx
        new.index = idx.tz_convert(ET)
        # Regular-hours bars only; Yahoo sometimes emits a stray 16:00 print.
        tod = new.index.time
        new = new[(tod >= dt.time(9, 30)) & (tod < dt.time(16, 0))]
        panel = _merge_panels(panel, new) if panel is not None else new
        _atomic_to_parquet(panel, path)
        print(f"[data] {interval} bars: {panel.shape[0]} rows, "
              f"{panel.index.min()} -> {panel.index.max()}")

    fields = _from_panel(panel)
    present = [t for t in tickers if t in fields["Close"].columns]
    return {f: df[present] for f, df in fields.items()}


def daily_session_prices(ohlcv: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Price panel on the twice-daily timeline: 09:30 ET (open auction) and
    16:00 ET (close auction) for every trading day. Index is tz-aware ET."""
    o, c = ohlcv["Open"], ohlcv["Close"]
    days = pd.DatetimeIndex(c.index)
    open_idx = (days + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    close_idx = (days + pd.Timedelta(hours=16)).tz_localize(ET)
    op = o.copy(); op.index = open_idx
    cl = c.copy(); cl.index = close_idx
    return pd.concat([op, cl]).sort_index()


def intraday_session_prices(
    bars: dict[str, pd.DataFrame],
    adj_factor: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Price panel on the intraday timeline. Each bar contributes its close at
    the bar-end timestamp; the first bar of the day also contributes its open
    at 09:30. Yahoo's 1h bars start on the half hour and the 15:30 bar is only
    30 minutes long (ends at the 16:00 close). On half days Yahoo omits the
    final bar, so the last available print is 12:30.

    `adj_factor` (daily AdjClose/Close from `fetch_ohlcv`) puts the intraday
    prices - which Yahoo serves split- but not dividend-adjusted - on the same
    total-return basis as the daily panel.
    """
    o, c = bars["Open"], bars["Close"]
    idx = pd.DatetimeIndex(c.index).tz_convert(ET)
    dates = idx.normalize()
    meta = pd.DataFrame({"ts": idx, "date": dates}, index=idx)
    is_first = (meta.groupby("date")["ts"].transform("min") == meta["ts"]).to_numpy()

    is_1530 = (idx.hour == 15) & (idx.minute == 30)
    step = np.where(is_1530, pd.Timedelta(minutes=30), pd.Timedelta(hours=1))
    bar_end = pd.DatetimeIndex(idx + pd.to_timedelta(step))

    op = o.copy(); op.index = idx
    op = op[is_first]
    cl = c.copy(); cl.index = bar_end
    panel = pd.concat([op, cl]).sort_index()
    panel = panel[~panel.index.duplicated(keep="last")]

    if adj_factor is not None:
        f = adj_factor.reindex(columns=panel.columns)
        f.index = pd.DatetimeIndex(f.index).normalize()
        day = pd.DatetimeIndex(panel.index).tz_convert(ET).tz_localize(None).normalize()
        f_rows = f.reindex(day).ffill().bfill()
        f_rows.index = panel.index
        panel = panel * f_rows.fillna(1.0)
    return panel


def session_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Calendar date (tz-naive, normalized) of each session timestamp."""
    return pd.DatetimeIndex(index).tz_convert(ET).tz_localize(None).normalize()


class MarketData:
    """Everything the short-horizon sleeves need, loaded once.

    daily[field]      : DataFrame(date -> ticker), adjusted OHLCV, tradables only
    aux               : DataFrame(date -> series) of non-tradable inputs (^VIX, ...)
    intraday[field]   : DataFrame(bar start ts -> ticker) hourly bars (~2y)
    px_daily          : price panel on the 09:30/16:00 timeline (full history)
    px_intraday       : price panel on the hourly timeline (~2y), dividend-adjusted
    """

    def __init__(self, cfg, refresh: bool = False, intraday: bool = True):
        from .config import HFConfig  # local import to avoid cycles
        self.cfg: HFConfig = cfg
        all_daily = fetch_ohlcv(cfg.tradable + cfg.aux, start=cfg.history_start, refresh=refresh)
        tradable = [t for t in cfg.tradable if t in all_daily["Close"].columns]
        # Only names with actual prices count; a column that is all-NaN (failed
        # download) must not silently shrink the universe.
        has_data = all_daily["Close"][tradable].notna().any()
        dead = [t for t in tradable if not has_data[t]]
        if dead:
            print(f"[data] WARNING: {len(dead)} tickers have no prices at all and are excluded: "
                  f"{dead[:10]}{'...' if len(dead) > 10 else ''}")
        tradable = [t for t in tradable if has_data[t]]
        self.tickers = tradable
        # VIX indices print pre-market, which leaves a row for "today" with no
        # equity prices yet; keep only dates where tradables actually traded.
        valid = all_daily["Close"][tradable].notna().any(axis=1)
        self.daily = {f: df.loc[valid, tradable] for f, df in all_daily.items()}
        aux_cols = [a for a in cfg.aux if a in all_daily["Close"].columns]
        self.aux = all_daily["Close"].loc[valid, aux_cols]
        self.px_daily = daily_session_prices(self.daily)

        self.intraday = None
        self.px_intraday = None
        if intraday:
            bars = fetch_intraday(tradable, interval=cfg.intraday_interval, refresh=refresh)
            self.intraday = bars
            self.px_intraday = intraday_session_prices(bars, adj_factor=all_daily.get("AdjFactor"))

    def cash_yield(self, fallback: float = 0.04) -> pd.Series | float:
        """Annualized T-bill yield per date (fraction) from ^IRX, or `fallback`.
        The last observation carries forward; ^IRX is quoted in percent."""
        if "^IRX" not in self.aux.columns or self.aux["^IRX"].notna().sum() < 100:
            return fallback
        return (self.aux["^IRX"].ffill() / 100.0).clip(lower=0.0)

    @property
    def close(self) -> pd.DataFrame:
        return self.daily["Close"]

    @property
    def open(self) -> pd.DataFrame:
        return self.daily["Open"]

    def etfs(self) -> list[str]:
        return [t for t in self.cfg.etfs if t in self.tickers]

    def stocks(self) -> list[str]:
        return [t for t in self.cfg.stocks if t in self.tickers]


def benchmark_series(close: pd.DataFrame, benchmark: str, universe: list[str]) -> pd.Series:
    """Benchmark close series; falls back to an equal-weight index of the
    universe if the benchmark ticker is unavailable (e.g. offline dataset)."""
    if benchmark in close.columns and not close[benchmark].isna().all():
        return close[benchmark]
    ew_ret = close[universe].pct_change(fill_method=None).mean(axis=1)
    print(f"[data] {benchmark} unavailable - using equal-weight universe index "
          "as benchmark/regime proxy")
    return (1.0 + ew_ret.fillna(0.0)).cumprod() * 100.0
