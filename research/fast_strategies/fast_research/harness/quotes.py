"""Deterministic conversion of normalized 1-minute BID/ASK candles into a QuoteTick stream for the Nautilus matching
engine, with cost scenarios applied inside the data (so every market and stop fill pays them natively).

For each VALID minute starting at s (bar-open, UTC), four quotes are emitted -- only values that exist in the candles:
    s + 1 s   : (bid_open,  ask_open)                      <- the first real quote of the minute
    s + 20 s  : first extreme   (bid_high/ask_high  OR  bid_low/ask_low)
    s + 40 s  : second extreme
    s + 59 s  : (bid_close, ask_close)                     <- the last real quote of the minute
The extreme visited first is the one nearer the MID open (Nautilus's own `bar_adaptive_high_low_ordering` heuristic).
Limitation (stated, not hidden): the timing of intrabar extremes is unobservable from candles; the path is a
deterministic convention. Ask-side extremes are paired with bid-side extremes, which can only widen the spread at the
extremes (ask_high >= bid_high, ask_low >= bid_low), never cross it.

Cost scenarios (see specs.HARNESS['costs']):  half_extra = (spread_multiplier - 1) / 2 * (ask - bid);
    bid' = bid - half_extra - slip,   ask' = ask + half_extra + slip     (slip = slippage_pips_market * pip)
Zero-volume minutes are never emitted (no information => no quote), so weekends and information gaps stay empty.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

OFFSETS_NS = {"open": 1_000_000_000, "first": 20_000_000_000, "second": 40_000_000_000, "close": 59_000_000_000}


def quote_arrays(df: pd.DataFrame, pip: float, precision: int, spread_multiplier: float = 1.0,
                 slippage_pips: float = 0.0):
    """df: normalized minute rows (columns per minute_dataset.COLS). Returns (ts_ns, bid, ask) numpy arrays, 4 per
    valid minute, sorted by time."""
    d = df[df["valid"]]
    n = len(d)
    ts = d["ts"].astype("int64").to_numpy()
    bo, bh, bl, bc = (d[f"bid_{k}"].to_numpy() for k in ("open", "high", "low", "close"))
    ao, ah, al, ac = (d[f"ask_{k}"].to_numpy() for k in ("open", "high", "low", "close"))
    mo, mh, ml = (bo + ao) / 2, (bh + ah) / 2, (bl + al) / 2
    high_first = np.abs(mh - mo) <= np.abs(mo - ml)  # open nearer the high -> O,H,L,C
    b1 = np.where(high_first, bh, bl); a1 = np.where(high_first, ah, al)
    b2 = np.where(high_first, bl, bh); a2 = np.where(high_first, al, ah)
    out_ts = np.empty(n * 4, dtype="int64"); out_b = np.empty(n * 4); out_a = np.empty(n * 4)
    for k, (off, b, a) in enumerate(((OFFSETS_NS["open"], bo, ao), (OFFSETS_NS["first"], b1, a1),
                                     (OFFSETS_NS["second"], b2, a2), (OFFSETS_NS["close"], bc, ac))):
        out_ts[k::4] = ts + off; out_b[k::4] = b; out_a[k::4] = a
    half = (spread_multiplier - 1.0) / 2.0 * (out_a - out_b)
    slip = slippage_pips * pip
    out_b = np.round(out_b - half - slip, precision)
    out_a = np.round(out_a + half + slip, precision)
    return out_ts, out_b, out_a


def to_quote_ticks(instrument_id, ts_ns, bid, ask, precision: int, size: int = 1_000_000):
    from nautilus_trader.model import Price, Quantity, QuoteTick
    q = Quantity.from_int(size)
    return [QuoteTick(instrument_id, Price(float(b), precision), Price(float(a), precision), q, q, int(t), int(t))
            for t, b, a in zip(ts_ns, bid, ask)]
