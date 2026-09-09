"""NYSE trading calendar (holidays + early closes) without external deps.

Rules per NYSE: New Year's Day, Martin Luther King Jr. Day, Presidents' Day,
Good Friday, Memorial Day, Juneteenth, Independence Day, Labor Day,
Thanksgiving, Christmas. Saturday holidays are observed Friday, Sunday
holidays on Monday (New Year's falling on Saturday is not observed).
Early closes (13:00): day after Thanksgiving, Christmas Eve, and July 3 when
they fall on a weekday.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    Holiday,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
    sunday_to_monday,
)


class NYSECalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


@lru_cache(maxsize=8)
def _holidays(year: int) -> set:
    cal = NYSECalendar()
    hs = cal.holidays(start=f"{year - 1}-12-01", end=f"{year + 1}-01-31")
    return set(pd.DatetimeIndex(hs).normalize())


def is_trading_day(day: dt.date | pd.Timestamp) -> bool:
    d = pd.Timestamp(day).tz_localize(None).normalize() if pd.Timestamp(day).tz is not None else pd.Timestamp(day).normalize()
    if d.weekday() >= 5:
        return False
    return d not in _holidays(d.year)


def is_early_close(day: dt.date | pd.Timestamp) -> bool:
    d = pd.Timestamp(day).normalize()
    if not is_trading_day(d):
        return False
    thanksgiving = [h for h in _holidays(d.year) if h.month == 11 and h.weekday() == 3]
    if thanksgiving and d == thanksgiving[0] + pd.Timedelta(days=1):
        return True
    if (d.month, d.day) in {(12, 24), (7, 3)} and d.weekday() < 5:
        return True
    return False


def close_time(day: dt.date | pd.Timestamp) -> dt.time:
    return dt.time(13, 0) if is_early_close(day) else dt.time(16, 0)
