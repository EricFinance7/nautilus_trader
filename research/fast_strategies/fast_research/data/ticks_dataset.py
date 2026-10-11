"""Normalize raw hourly Dukascopy tick files (.bi5) into per-pair, per-day Parquet, with data-quality checks and a
deterministic 1-minute candle reconstruction that is cross-checked against the NATIVE candles.

Tick record: ms offset from hour start (true UTC), ASK, BID, ask volume, bid volume (see decode.py). Prices are exact
decimals (integer / 10**scale). Nothing is interpolated: an hour with no file or no ticks stays empty and is reported.

Output: <root>/normalized/dukascopy/ticks/<PAIR>/<YYYY-MM-DD>.parquet   columns: ts (UTC ns), bid, ask, bid_volume, ask_volume
"""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .decode import decode_ticks
from .minute_dataset import PAIRS, PIP


def load_day(root: Path, pair: str, day: dt.date):
    """Returns (DataFrame, hours_present, hours_empty). Hours without a file are simply absent."""
    scale = 10 ** PAIRS[pair]
    frames, present, empty = [], [], []
    for h in range(24):
        p = root / "raw" / "dukascopy" / pair / "tick" / f"{day.isoformat()}T{h:02d}.bi5"
        if not p.exists():
            continue
        raw = p.read_bytes()
        rec = decode_ticks(raw) if raw else None
        if rec is None or len(rec) == 0:
            empty.append(h)
            continue
        present.append(h)
        base = int(pd.Timestamp(f"{day.isoformat()}T{h:02d}:00:00", tz="UTC").value)
        frames.append(pd.DataFrame({
            "ts": (base + rec["ms"].astype("int64") * 1_000_000),
            "bid": np.round(rec["bid"] / scale, PAIRS[pair]), "ask": np.round(rec["ask"] / scale, PAIRS[pair]),
            "bid_volume": rec["bid_vol"].astype("float32"), "ask_volume": rec["ask_vol"].astype("float32")}))
    if not frames:
        return pd.DataFrame(columns=["ts", "bid", "ask", "bid_volume", "ask_volume"]), present, empty
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = pd.to_datetime(df["ts"], unit="ns", utc=True)
    return df, present, empty


def qc_ticks(df: pd.DataFrame, pair: str) -> dict:
    if df.empty:
        return {"rows": 0}
    ts = df["ts"].dt.as_unit("ns").astype("int64").to_numpy()
    key = pd.util.hash_pandas_object(df[["ts", "bid", "ask"]], index=False)
    sp = (df["ask"] - df["bid"]) / PIP[pair]
    return {
        "rows": int(len(df)), "first": str(df["ts"].iloc[0]), "last": str(df["ts"].iloc[-1]),
        "tz": str(df["ts"].dt.tz), "monotonic_non_decreasing": bool((np.diff(ts) >= 0).all()),
        "exact_duplicate_ticks": int(key.duplicated().sum()),
        "crossed_bid_gt_ask": int((df["bid"] > df["ask"]).sum()), "locked_bid_eq_ask": int((df["bid"] == df["ask"]).sum()),
        "non_positive": int(((df["bid"] <= 0) | (df["ask"] <= 0)).sum()),
        "spread_pips": {"mean": float(sp.mean()), "median": float(sp.median()), "p95": float(sp.quantile(0.95)), "max": float(sp.max())},
        "max_gap_seconds": float(np.diff(ts).max() / 1e9) if len(ts) > 1 else 0.0,
    }


def candles_from_ticks(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic 1-minute BID/ASK candles from ticks: bar-open labeled, half-open [t, t+60s), open=first, close=last."""
    t = df.assign(minute=df["ts"].dt.floor("1min"))
    g = t.groupby("minute", sort=True)
    out = pd.DataFrame({
        "bid_open": g["bid"].first(), "bid_high": g["bid"].max(), "bid_low": g["bid"].min(), "bid_close": g["bid"].last(),
        "ask_open": g["ask"].first(), "ask_high": g["ask"].max(), "ask_low": g["ask"].min(), "ask_close": g["ask"].last(),
        "ticks": g["bid"].size()})
    return out


def compare_to_native(tick_candles: pd.DataFrame, native: pd.DataFrame) -> dict:
    """native: normalized minute dataset rows (valid only) indexed by ts. Compares OHLC on the minutes both contain."""
    nat = native[native["valid"]].set_index("ts")
    j = tick_candles.join(nat[[c for c in tick_candles.columns if c != "ticks"]], rsuffix="_native", how="inner")
    res = {"minutes_compared": int(len(j)), "minutes_only_in_ticks": int(len(tick_candles.index.difference(nat.index))),
           "minutes_only_in_native": int(len(nat.index.difference(tick_candles.index)))}
    worst = 0.0
    for c in [c for c in tick_candles.columns if c != "ticks"]:
        d = (j[c] - j[c + "_native"]).abs()
        res[f"{c}_mismatch_minutes"] = int((d > 1e-9).sum())
        worst = max(worst, float(d.max()) if len(d) else 0.0)
    res["max_abs_diff"] = worst
    return res


def tick_quote_arrays(df: pd.DataFrame, pip: float, precision: int, spread_multiplier: float = 1.0, slippage_pips: float = 0.0):
    """Real ticks -> (ts_ns, bid, ask) with the same scenario transforms as the candle-synthesized stream."""
    d = df[df["bid"] <= df["ask"]]       # a crossed tick is not a tradable quote; the count is reported by qc_ticks
    ts = d["ts"].dt.as_unit("ns").astype("int64").to_numpy()
    b, a = d["bid"].to_numpy(), d["ask"].to_numpy()
    half = (spread_multiplier - 1.0) / 2.0 * (a - b)
    slip = slippage_pips * pip
    return ts, np.round(b - half - slip, precision), np.round(a + half + slip, precision)


def build_range(root: Path, start: dt.date, end: dt.date, out_dir: Path | None = None, pairs=None) -> dict:
    out_dir = out_dir or (root / "normalized" / "dukascopy" / "ticks")
    report = {"window": [start.isoformat(), end.isoformat()], "pairs": {}}
    for pair in (pairs or PAIRS):
        rep = {"days": {}}
        day = start
        while day <= end:
            if day.weekday() != 5:
                df, present, empty = load_day(root, pair, day)
                q = qc_ticks(df, pair)
                q.update({"hours_with_ticks": present, "hours_empty_files": empty})
                if len(df):
                    p = out_dir / pair / f"{day.isoformat()}.parquet"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    df.to_parquet(p, compression="zstd", index=False)
                    q["parquet_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
                rep["days"][day.isoformat()] = q
            day += dt.timedelta(days=1)
        report["pairs"][pair] = rep
    return report
