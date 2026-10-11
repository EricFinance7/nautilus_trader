"""DST-correct session helpers (zoneinfo), matching the Trading Intelligence Engine's python/research_lake/
fast_session_model.py (classify_session). Local times are converted per the actual calendar date, never with fixed UTC
offsets. All inputs are UTC nanoseconds."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
TOKYO, LONDON, NEW_YORK = ZoneInfo("Asia/Tokyo"), ZoneInfo("Europe/London"), ZoneInfo("America/New_York")

_ASIA = (dt.time(0, 0), dt.time(15, 0), TOKYO)
_LON = (dt.time(8, 0), dt.time(17, 0), LONDON)
_NY = (dt.time(8, 0), dt.time(17, 0), NEW_YORK)
_ROLL = (dt.time(17, 0), dt.time(19, 0), NEW_YORK)

NO_ENTRY_START = dt.time(16, 30)   # America/New_York
NO_ENTRY_END = dt.time(19, 0)
FORCE_FLAT = dt.time(16, 55)


def to_dt(ts_ns: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts_ns / 1e9, tz=UTC)


def _in(t: dt.datetime, w) -> bool:
    s, e, tz = w
    return s <= t.astimezone(tz).time() < e


def classify_session(ts_ns: int) -> str:
    t = to_dt(ts_ns)
    lon, ny = _in(t, _LON), _in(t, _NY)
    if lon and ny:
        return "LONDON_NEW_YORK_OVERLAP"
    if _in(t, _ROLL):
        return "ROLLOVER_LOW_LIQUIDITY"
    if lon:
        return "LONDON"
    if ny:
        return "NEW_YORK"
    if _in(t, _ASIA):
        return "ASIA"
    return "OTHER"


def ny_time(ts_ns: int) -> dt.time:
    return to_dt(ts_ns).astimezone(NEW_YORK).time()


def entry_blocked(ts_ns: int) -> bool:
    """No new entries from 16:30 to 19:00 New York time (rollover spread blow-outs)."""
    return NO_ENTRY_START <= ny_time(ts_ns) < NO_ENTRY_END


def force_flat_due(ts_ns: int) -> bool:
    """True from 16:55 New York until the entry block ends (positions must not cross the 17:00 rollover or the
    Friday close)."""
    return FORCE_FLAT <= ny_time(ts_ns) < NO_ENTRY_END


def session_open_utc_ns(local_date: dt.date, tz_name: str, open_local: dt.time) -> int:
    tz = ZoneInfo(tz_name)
    local = dt.datetime.combine(local_date, open_local, tzinfo=tz)
    return int(local.astimezone(UTC).timestamp()) * 1_000_000_000


def local_date(ts_ns: int, tz_name: str) -> dt.date:
    return to_dt(ts_ns).astimezone(ZoneInfo(tz_name)).date()
