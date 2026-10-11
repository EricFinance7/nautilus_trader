"""Engine-independent bar aggregation and indicators.

Timeframe bars are built from the 1-minute MID bars the engine delivers. Rules (from the FAST foundation spec):
  * UTC-aligned, left-closed, left-labeled buckets;
  * a bucket completes ONLY when its final minute arrives (the minute whose close time is a multiple of the timeframe);
    a bucket whose final minute is missing is dropped, never completed late and never fabricated;
  * all state resets when consecutive valid minutes are more than `gap_reset_minutes` apart (weekend/outage), so no
    indicator ever looks back across a market gap.
Every function here uses only bars already completed, so it cannot see the future.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

NS_MIN = 60_000_000_000


@dataclass(frozen=True, slots=True)
class Bar:
    t_open: int   # ns, bucket open (UTC)
    t_close: int  # ns, bucket close = t_open + tf (the moment the bar becomes known)
    o: float
    h: float
    l: float
    c: float
    n_minutes: int


class TFAggregator:
    def __init__(self, tf_minutes: int, maxlen: int = 400):
        self.tf = tf_minutes
        self.tf_ns = tf_minutes * NS_MIN
        self.bars: deque[Bar] = deque(maxlen=maxlen)
        self._cur = None  # [bucket_start, o, h, l, c, n]

    def reset(self) -> None:
        self.bars.clear()
        self._cur = None

    def on_minute(self, t_open: int, o: float, h: float, l: float, c: float):
        """Feed one valid 1-minute bar (open time `t_open`). Returns the completed Bar or None."""
        bucket = (t_open // self.tf_ns) * self.tf_ns
        cur = self._cur
        if cur is None or cur[0] != bucket:
            cur = self._cur = [bucket, o, h, l, c, 0]  # any earlier incomplete bucket is discarded
        else:
            if h > cur[2]:
                cur[2] = h
            if l < cur[3]:
                cur[3] = l
            cur[4] = c
        cur[5] += 1
        if (t_open + NS_MIN) % self.tf_ns == 0:  # final minute of the bucket
            bar = Bar(bucket, bucket + self.tf_ns, cur[1], cur[2], cur[3], cur[4], cur[5])
            self.bars.append(bar)
            self._cur = None
            return bar
        return None


class PairState:
    """All timeframe aggregators for one pair, with the gap-reset rule."""

    def __init__(self, tfs, gap_reset_minutes: int = 60):
        self.aggs = {tf: TFAggregator(tf) for tf in sorted(set(tfs))}
        self.gap_ns = gap_reset_minutes * NS_MIN
        self.last_open: int | None = None
        self.resets = 0

    def bars(self, tf: int) -> deque:
        return self.aggs[tf].bars

    def feed(self, t_open: int, o: float, h: float, l: float, c: float) -> dict:
        """Returns {tf: completed Bar} for every timeframe completed by this minute."""
        if self.last_open is not None and t_open - self.last_open > self.gap_ns:
            for a in self.aggs.values():
                a.reset()
            self.resets += 1
        self.last_open = t_open
        done = {}
        for tf, a in self.aggs.items():
            b = a.on_minute(t_open, o, h, l, c)
            if b is not None:
                done[tf] = b
        return done


# --- indicators (pure functions of completed bars) -------------------------------------------------------------

def true_range(bar: Bar, prev_close: float) -> float:
    return max(bar.h - bar.l, abs(bar.h - prev_close), abs(bar.l - prev_close))


def atr(bars, n: int, end: int = 0):
    """Simple mean of the last n true ranges ending `end` bars before the latest (end=0 -> latest). Returns None
    until n+1 bars are available."""
    seq = list(bars)
    last = len(seq) - end
    if last < n + 1:
        return None
    total = 0.0
    for i in range(last - n, last):
        total += true_range(seq[i], seq[i - 1].c)
    return total / n


def sma_close(bars, n: int):
    seq = list(bars)
    if len(seq) < n:
        return None
    return sum(b.c for b in seq[-n:]) / n


def std_close(bars, n: int):
    seq = list(bars)
    if len(seq) < n:
        return None
    xs = [b.c for b in seq[-n:]]
    m = sum(xs) / n
    return (sum((x - m) ** 2 for x in xs) / n) ** 0.5
