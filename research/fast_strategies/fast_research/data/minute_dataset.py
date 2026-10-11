"""Build the normalized 1-minute BID/ASK dataset from raw Dukascopy candle files, and run the data-quality checks.

Rules (inherited from the Trading Intelligence Engine's FAST foundation / microstructure validation):
  * timestamps are bar-OPEN, left-labeled, true UTC;
  * a minute with zero BID and zero ASK volume carries NO information (closed market or no ticks): it is kept in the
    table with valid=False so gaps stay visible, but it is NEVER replayed as a quote and never fabricated;
  * prices are exact decimals (integer raw / 10**scale);
  * spreads are DERIVED (ask - bid), never stored as raw.
Output (per pair): <root>/normalized/dukascopy/minute/<PAIR>.parquet (zstd), plus a manifest with sha256.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .decode import decode_minute

PAIRS = {"EURUSD": 5, "GBPUSD": 5, "USDJPY": 3, "USDCHF": 5, "AUDUSD": 5, "USDCAD": 5, "NZDUSD": 5}
PIP = {"EURUSD": 1e-4, "GBPUSD": 1e-4, "USDJPY": 1e-2, "USDCHF": 1e-4, "AUDUSD": 1e-4, "USDCAD": 1e-4, "NZDUSD": 1e-4}
COLS = ["ts", "bid_open", "bid_high", "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close",
        "bid_volume", "ask_volume", "valid"]


def _load_side(root: Path, pair: str, side: str, day: dt.date):
    p = root / "raw" / "dukascopy" / pair / "minute" / side / f"{day.isoformat()}.bi5"
    if not p.exists():
        return None
    raw = p.read_bytes()
    return decode_minute(raw) if raw else np.zeros(0, dtype=decode_minute(b"").dtype)


def build_pair(root: Path, pair: str, start: dt.date, end: dt.date):
    """Returns (DataFrame, missing_days list). Days where either side is missing are excluded entirely (reported)."""
    scale = 10 ** PAIRS[pair]
    frames, missing = [], []
    day = start
    while day <= end:
        if day.weekday() == 5:   # Saturday: market closed, not acquired by design (every candle would be a zero-volume stale bar)
            day += dt.timedelta(days=1)
            continue
        b, a = _load_side(root, pair, "BID", day), _load_side(root, pair, "ASK", day)
        if b is None or a is None or len(b) == 0 or len(a) == 0:
            missing.append(day.isoformat())
        else:
            if len(b) != len(a) or not np.array_equal(b["sec"], a["sec"]):
                raise ValueError(f"{pair} {day}: BID/ASK candle timestamps differ ({len(b)} vs {len(a)})")
            base = np.datetime64(day.isoformat() + "T00:00:00", "ns")
            df = pd.DataFrame({
                "ts": base + (b["sec"].astype("int64") * 1_000_000_000).astype("timedelta64[ns]"),
                "bid_open": b["open"] / scale, "bid_high": b["high"] / scale,
                "bid_low": b["low"] / scale, "bid_close": b["close"] / scale,
                "ask_open": a["open"] / scale, "ask_high": a["high"] / scale,
                "ask_low": a["low"] / scale, "ask_close": a["close"] / scale,
                "bid_volume": b["volume"].astype("float32"), "ask_volume": a["volume"].astype("float32"),
            })
            frames.append(df)
        day += dt.timedelta(days=1)
    if not frames:
        return pd.DataFrame(columns=COLS), missing
    out = pd.concat(frames, ignore_index=True)
    for c in out.columns:
        if c.startswith(("bid_", "ask_")) and not c.endswith("volume"):
            out[c] = out[c].round(PAIRS[pair])
    out["valid"] = (out["bid_volume"] > 0) | (out["ask_volume"] > 0)
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    return out[COLS].sort_values("ts", kind="stable").reset_index(drop=True), missing


def content_hash(df: pd.DataFrame) -> str:
    """Deterministic content hash independent of parquet encoding."""
    h = hashlib.sha256()
    h.update(df["ts"].astype("int64").to_numpy().tobytes())
    for c in COLS[1:]:
        h.update(df[c].to_numpy().tobytes())
    return h.hexdigest()


def in_expected_session(ts: pd.Series) -> pd.Series:
    """FX week for the northern-summer schedule (valid for Apr-Oct 2026): open Sun 21:00 UTC, close Fri 21:00 UTC."""
    wd, hr = ts.dt.weekday, ts.dt.hour
    return (((wd == 6) & (hr >= 21)) | wd.isin([0, 1, 2, 3]) | ((wd == 4) & (hr < 21)))


def qc_pair(df: pd.DataFrame, pair: str, missing_days: list, start: dt.date, end: dt.date) -> dict:
    pip = PIP[pair]
    n_days_expected = sum(1 for i in range((end - start).days + 1) if (start + dt.timedelta(days=i)).weekday() != 5)
    res = {"pair": pair, "rows": int(len(df)), "days_expected": n_days_expected, "days_missing": missing_days,
           "first_ts": str(df["ts"].iloc[0]) if len(df) else None, "last_ts": str(df["ts"].iloc[-1]) if len(df) else None}
    if not len(df):
        return res
    ts = df["ts"]
    res["timestamps"] = {
        "tz": str(ts.dt.tz), "duplicates": int(ts.duplicated().sum()), "monotonic_increasing": bool(ts.is_monotonic_increasing),
        "not_minute_aligned": int(((ts.astype("int64") // 10**9) % 60 != 0).sum()),
    }
    res["crossed_quotes"] = {f: int((df[f"bid_{f}"] > df[f"ask_{f}"]).sum()) for f in ("open", "high", "low", "close")}
    inv = {}
    for side in ("bid", "ask"):
        inv[side] = int(((df[f"{side}_low"] > df[f"{side}_open"]) | (df[f"{side}_low"] > df[f"{side}_close"]) |
                         (df[f"{side}_high"] < df[f"{side}_open"]) | (df[f"{side}_high"] < df[f"{side}_close"]) |
                         (df[f"{side}_low"] > df[f"{side}_high"])).sum())
    res["ohlc_invariant_violations"] = inv
    res["non_positive_prices"] = int((df[[c for c in COLS if c.startswith(("bid_", "ask_")) and "volume" not in c]] <= 0).any(axis=1).sum())
    sess = in_expected_session(ts)
    v = df["valid"]
    res["session"] = {
        "minutes_in_expected_session": int(sess.sum()),
        "valid_minutes_in_session": int((v & sess).sum()),
        "zero_volume_minutes_in_session": int((~v & sess).sum()),
        "valid_minutes_outside_session": int((v & ~sess).sum()),
    }
    # runs of consecutive zero-volume minutes INSIDE the expected session (information gaps)
    gap = (~v & sess).to_numpy()
    runs, cur = [], 0
    for i, g in enumerate(gap):
        if g:
            cur += 1
        elif cur:
            runs.append((i - cur, cur)); cur = 0
    if cur:
        runs.append((len(gap) - cur, cur))
    long_runs = [{"start": str(ts.iloc[s]), "minutes": n} for s, n in runs if n >= 5]
    res["in_session_gaps"] = {"runs_ge_5min": len(long_runs), "longest_minutes": max([n for _, n in runs], default=0),
                              "examples": long_runs[:10]}
    vv = df[v & sess]
    sp_open = (vv["ask_open"] - vv["bid_open"]) / pip
    sp_close = (vv["ask_close"] - vv["bid_close"]) / pip
    res["spread_pips"] = {
        "open_mean": float(sp_open.mean()), "open_median": float(sp_open.median()), "open_p95": float(sp_open.quantile(0.95)),
        "close_mean": float(sp_close.mean()), "close_median": float(sp_close.median()), "close_p95": float(sp_close.quantile(0.95)),
        "close_max": float(sp_close.max()), "negative_close": int((sp_close < 0).sum()),
    }
    res["content_sha256"] = content_hash(df)
    res["deterministic_rebuild_hash_matches"] = None  # filled by the caller after a second build
    return res


def build_all(root: Path, start: dt.date, end: dt.date, out_dir: Path | None = None, pairs=None) -> dict:
    out_dir = out_dir or (root / "normalized" / "dukascopy" / "minute")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"window": [start.isoformat(), end.isoformat()], "pairs": {}}
    for pair in (pairs or PAIRS):
        df, missing = build_pair(root, pair, start, end)
        rep = qc_pair(df, pair, missing, start, end)
        if len(df):
            df2, _ = build_pair(root, pair, start, end)
            rep["deterministic_rebuild_hash_matches"] = content_hash(df2) == rep["content_sha256"]
            path = out_dir / f"{pair}.parquet"
            df.to_parquet(path, compression="zstd", index=False)
            rep["parquet_path"] = str(path)
            rep["parquet_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        report["pairs"][pair] = rep
    return report


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out-json", default=None)
    a = ap.parse_args()
    rep = build_all(Path(a.root), dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
    text = json.dumps(rep, indent=2, default=str)
    if a.out_json:
        Path(a.out_json).write_text(text)
    print(text)
