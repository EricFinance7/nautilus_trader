"""Decoders for Dukascopy .bi5 files (LZMA-compressed big-endian fixed-size records).

Record layouts (verified against the Trading Intelligence Engine's python/dukascopy_audit/client.py, whose decoders
were cross-checked 0/4049 mismatches against the JSON feed during DUKASCOPY_FAST_TIMESTAMP_AND_ACQUISITION_AUDIT_V1):
  minute candle (24 bytes) >iiiiif : seconds-from-day-start, open, CLOSE, low, high, volume   (NB: close precedes low/high)
  tick          (20 bytes) >iiiff  : ms-from-hour-start, ASK, BID, ask_volume, bid_volume      (NB: ask precedes bid)
Prices are integers divided by 10**price_scale. Candle timestamps are bar-OPEN, left-labeled, half-open [t, t+60s),
true UTC. Tick timestamps are exact event time (ms), true UTC.
"""
from __future__ import annotations

import lzma

import numpy as np

MINUTE_DTYPE = np.dtype([("sec", ">i4"), ("open", ">i4"), ("close", ">i4"), ("low", ">i4"), ("high", ">i4"),
                         ("volume", ">f4")])
TICK_DTYPE = np.dtype([("ms", ">i4"), ("ask", ">i4"), ("bid", ">i4"), ("ask_vol", ">f4"), ("bid_vol", ">f4")])


def decompress(raw: bytes) -> bytes:
    return lzma.decompress(raw) if raw else b""


def decode_minute(raw: bytes) -> np.ndarray:
    """Structured array of raw integer candle records (empty array for an empty file)."""
    data = decompress(raw)
    if len(data) % MINUTE_DTYPE.itemsize:
        raise ValueError(f"minute payload {len(data)} bytes is not a multiple of {MINUTE_DTYPE.itemsize}")
    return np.frombuffer(data, dtype=MINUTE_DTYPE)


def decode_ticks(raw: bytes) -> np.ndarray:
    data = decompress(raw)
    if len(data) % TICK_DTYPE.itemsize:
        raise ValueError(f"tick payload {len(data)} bytes is not a multiple of {TICK_DTYPE.itemsize}")
    return np.frombuffer(data, dtype=TICK_DTYPE)
