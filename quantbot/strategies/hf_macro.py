"""Pre-FOMC overnight sleeve (daily timeline: long at 16:00 the day before a
scheduled FOMC decision, flat at 09:30 on the decision day).

Hypothesis
----------
Lucca & Moench (2015, JF, "The pre-FOMC announcement drift"): US equities
earn a large excess return in the 24 hours before scheduled FOMC statements
(14:00 ET). Savor & Wilson (2013) document a broader premium on scheduled
macro-announcement days. In 2010-2026 daily data only the FOMC part
replicates, and it lives in the overnight session: QQQ 16:00 (d-1) -> 09:30
(d) averages +21 bp in-sample (2010-21, t 3.1) and +34 bp out-of-sample
(2022+, t 3.2) into the 133 scheduled decision days, versus ~5 bp on other
nights; the 09:30 -> 16:00 session on decision day is ~0 (the announcement
reaction nets out). Employment, CPI and PPI release days carry no reliable
premium here (CPI's 2022-23 spike is not there before 2022; PPI is negative
in-sample), so they are not traded. See research/notes/macro.md.

Design
------
At 16:00 of the trading day before each scheduled FOMC decision day, hold the
asset(s) (default QQQ, optionally through a leveraged fund via leverage_map,
same convention as the overnight sleeve) until the 09:30 open of decision
day. ~8 nights a year. Decision days come from `quantbot.macro_calendar.FOMC`
(primary source: federalreserve.gov; unscheduled and cancelled meetings
excluded). Not regime-scaled: it is an event premium, not a trend bet.

Causality: the FOMC schedule is published a year ahead; at 16:00 of d-1 the
decision day d is known. Nothing else is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from quantbot.data import MarketData
from quantbot.macro_calendar import announcement_days

ET = "America/New_York"


@dataclass
class MacroParams:
    kinds: tuple[str, ...] = ("FOMC",)          # release kinds whose eve-nights to hold
    assets: tuple[str, ...] = ("QQQ",)          # equal-weight basket, 1/len(assets) each
    leverage_map: dict = field(default_factory=dict)   # e.g. {"QQQ": "QLD"}
    require_trend: bool = False                 # optional: asset above its own 200d MA
    ma_window: int = 200
    max_gross: float = 1.0


def eve_days(kinds) -> pd.DatetimeIndex:
    """The NYSE trading day strictly before each release day, from the exchange
    calendar - NOT from the price panel. (Using the panel marks its last row as
    the eve of every future meeting: a live trader would buy every evening,
    and a truncated backtest would hold a phantom position at the cut. Caught
    by the truncation test, 2026-09-24.)"""
    from quantbot.calendar import is_trading_day
    eves = set()
    for e in announcement_days(kinds):
        d = e - pd.Timedelta(days=1)
        for _ in range(10):
            if is_trading_day(d):
                eves.add(d)
                break
            d -= pd.Timedelta(days=1)
    return pd.DatetimeIndex(sorted(eves))


def macro_weights(md: MarketData, p: MacroParams = MacroParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline: 16:00 rows on the eve of each
    release day (1/len(assets) per asset, 0 otherwise), explicit 0.0 at 09:30."""
    dates = pd.DatetimeIndex(md.close.index)
    on = pd.Series(dates.isin(eve_days(list(p.kinds))), index=dates)

    slot = 1.0 / len(p.assets)
    held: dict[str, pd.Series] = {}
    for t in p.assets:
        target = p.leverage_map.get(t, t)
        if target not in md.close.columns:
            raise KeyError(f"{target} not in market data")
        w = on.astype(float) * slot
        if p.require_trend:
            c = md.close[t]
            w = w.where(c > c.rolling(p.ma_window, min_periods=p.ma_window).mean(), 0.0)
        w = w.where(md.close[target].notna(), 0.0)
        held[target] = held.get(target, 0.0) + w
    w_close = pd.DataFrame(held, index=dates).fillna(0.0)
    gross = w_close.sum(axis=1)
    over = gross > p.max_gross
    if over.any():
        w_close.loc[over] = w_close.loc[over].div(gross[over], axis=0) * p.max_gross

    close_idx = (dates + pd.Timedelta(hours=16)).tz_localize(ET)
    open_idx = (dates + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    w_close.index = close_idx
    w_open = pd.DataFrame(0.0, index=open_idx, columns=w_close.columns)
    out = pd.concat([w_close, w_open]).sort_index()
    return out.reindex(out.index.intersection(md.px_daily.index)).fillna(0.0)
