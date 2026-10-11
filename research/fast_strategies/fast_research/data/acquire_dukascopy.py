#!/usr/bin/env python
"""Resumable, concurrent acquisition of FREE Dukascopy historical data for the seven FAST FX pairs.

Source: Dukascopy's official public historical datafeed (static .bi5 files), over plain HTTP. As of 2026-10-11:
  * https://datafeed.dukascopy.com:443 does not accept TCP connections from this machine (connect timeout);
    http://datafeed.dukascopy.com:80 serves the same files.
  * The jetta.dukascopy.com JSON API now sits behind an AWS WAF *bot challenge* (HTTP 202, empty body,
    `x-amzn-waf-action: challenge`). This script does NOT attempt to defeat or work around that challenge.
Because the datafeed is slow (5-40 s/request) and returns many transient 503s, every unit is retried with
jittered exponential backoff and the whole run is resumable.

Two tiers, run in this order:
  1. candles : native 1-minute BID and ASK candles, one file per (pair, side, day).  [~2.7k requests]
  2. ticks   : hourly tick files, newest week first, so the largest COHERENT completed period (all seven pairs,
               contiguous) grows backwards from the most recent data.

Layout (identical to the Trading Intelligence Engine's python/dukascopy_audit/downloader.py bi5 mechanism):
  <root>/raw/dukascopy/<PAIR>/minute/<BID|ASK>/<YYYY-MM-DD>.bi5
  <root>/raw/dukascopy/<PAIR>/tick/<YYYY-MM-DDTHH>.bi5
Checkpoint (append-only JSONL): <root>/checkpoints/dukascopy/fast6m_acquisition.jsonl
Nothing is fabricated: a unit that cannot be fetched stays missing and is reported by the manifest/gap report.

Usage:
  python acquire_dukascopy.py --root E:\\Tradingdata --start 2026-04-01 --end 2026-10-09 --workers 24
  python acquire_dukascopy.py --root E:\\Tradingdata --status        # progress summary only
Stop gracefully: create <root>/checkpoints/dukascopy/STOP (units in flight finish; rerun resumes).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import lzma
import os
import random
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# price_scale per pair: Dukascopy's own declared decimal precision, verified against the live instruments list on
# 2026-09-27 by the Trading Intelligence Engine (python/dukascopy_audit/instruments.py).
PAIRS = {"EURUSD": 5, "GBPUSD": 5, "USDJPY": 3, "USDCHF": 5, "AUDUSD": 5, "USDCAD": 5, "NZDUSD": 5}
BASE_URL = "http://datafeed.dukascopy.com/datafeed"
TICK_RECORD, MINUTE_RECORD = 20, 24  # bytes per record: >iiiff and >iiiiif
USER_AGENT = "Mozilla/5.0 (personal non-commercial research acquisition client; FAST_STRATEGIES_V1)"
TERMINAL = {"OK", "EMPTY", "NOT_FOUND"}


def session_hours(d: dt.date) -> range | list:
    """UTC hours worth requesting for the FX week (northern-summer schedule, valid for the Apr-Oct 2026 window:
    open Sun 21:00 UTC, close Fri 21:00 UTC). Saturday is skipped. Deliberately one hour wider at each end so a
    schedule shift cannot silently drop a real hour; empty/404 responses are recorded, not hidden."""
    wd = d.weekday()  # Mon=0 .. Sun=6
    if wd == 5:
        return []
    if wd == 6:
        return range(20, 24)
    if wd == 4:
        return range(0, 22)
    return range(0, 24)


def unit_key(kind: str, pair: str, d: dt.date, side: str | None = None, hour: int | None = None) -> str:
    if kind == "candles":
        return f"candles|{pair}|{side}|{d.isoformat()}"
    return f"ticks|{pair}|{d.isoformat()}T{hour:02d}"


def unit_path(root: Path, kind: str, pair: str, d: dt.date, side=None, hour=None) -> Path:
    base = root / "raw" / "dukascopy" / pair
    if kind == "candles":
        return base / "minute" / side / f"{d.isoformat()}.bi5"
    return base / "tick" / f"{d.isoformat()}T{hour:02d}.bi5"


def unit_url(kind: str, pair: str, d: dt.date, side=None, hour=None) -> str:
    seg = f"{BASE_URL}/{pair}/{d.year}/{d.month - 1:02d}/{d.day:02d}"  # month is zero-based in the feed
    return f"{seg}/{side}_candles_min_1.bi5" if kind == "candles" else f"{seg}/{hour:02d}h_ticks.bi5"


def validate(raw: bytes, kind: str) -> None:
    """Corrupt-file detection: empty is legitimate (closed market); otherwise must LZMA-decompress to a whole
    number of fixed-size records."""
    if not raw:
        return
    data = lzma.decompress(raw)
    rec = MINUTE_RECORD if kind == "candles" else TICK_RECORD
    if len(data) % rec:
        raise ValueError(f"decompressed size {len(data)} is not a multiple of {rec}")


def build_units(start: dt.date, end: dt.date, tiers: list[str]):
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    if "candles" in tiers:
        for d in days:
            if d.weekday() == 5:  # Saturday: market closed, every candle is a zero-volume stale bar (verified on 2026-04-04)
                continue
            for pair in PAIRS:
                for side in ("BID", "ASK"):
                    yield ("candles", pair, d, side, None)
    if "ticks" in tiers:
        # newest ISO week first; within a week chronological, all pairs interleaved per hour
        by_week: dict[tuple, list] = {}
        for d in days:
            by_week.setdefault(d.isocalendar()[:2], []).append(d)
        for wk in sorted(by_week, reverse=True):
            for d in by_week[wk]:
                for h in session_hours(d):
                    for pair in PAIRS:
                        yield ("ticks", pair, d, None, h)


class Checkpoint:
    def __init__(self, path: Path):
        self.path, self.lock, self.state = path, threading.Lock(), {}
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.state[rec["key"]] = rec  # last record wins
        self.fh = open(path, "a", encoding="utf-8")

    def done(self, key: str) -> bool:
        rec = self.state.get(key)
        return bool(rec and rec["status"] in TERMINAL)

    def record(self, rec: dict) -> None:
        with self.lock:
            self.state[rec["key"]] = rec
            self.fh.write(json.dumps(rec, sort_keys=True) + "\n")
            self.fh.flush()


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.c: dict[str, int] = {}

    def add(self, k: str, n: int = 1):
        with self.lock:
            self.c[k] = self.c.get(k, 0) + n


def fetch_unit(root: Path, cp: Checkpoint, stats: Stats, stop_file: Path, deadline: float | None,
               kind: str, pair: str, d: dt.date, side, hour, max_attempts: int) -> None:
    key = unit_key(kind, pair, d, side, hour)
    target = unit_path(root, kind, pair, d, side, hour)
    if cp.done(key):
        stats.add("skipped_done")
        return
    if target.exists():  # a previous run wrote the file but died before checkpointing: accept only if it validates
        try:
            raw = target.read_bytes()
            validate(raw, kind)
            cp.record({"key": key, "status": "OK" if raw else "EMPTY", "bytes": len(raw),
                       "sha256": hashlib.sha256(raw).hexdigest(), "attempts": 0, "note": "recovered_existing",
                       "ts": dt.datetime.now(dt.timezone.utc).isoformat()})
            stats.add("recovered_existing")
            return
        except Exception:  # noqa: BLE001
            target.unlink(missing_ok=True)
    url = unit_url(kind, pair, d, side, hour)
    last = "?"
    for attempt in range(1, max_attempts + 1):
        if stop_file.exists() or (deadline and time.time() > deadline):
            stats.add("stopped_before_fetch")
            return
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=75) as r:
                raw = r.read()
            validate(raw, kind)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".bi5.part")
            tmp.write_bytes(raw)
            os.replace(tmp, target)
            cp.record({"key": key, "status": "OK" if raw else "EMPTY", "bytes": len(raw),
                       "sha256": hashlib.sha256(raw).hexdigest(), "attempts": attempt,
                       "ts": dt.datetime.now(dt.timezone.utc).isoformat()})
            stats.add("ok" if raw else "empty")
            stats.add(f"{kind}_done")
            return
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 404:
                cp.record({"key": key, "status": "NOT_FOUND", "bytes": 0, "attempts": attempt,
                           "ts": dt.datetime.now(dt.timezone.utc).isoformat()})
                stats.add("not_found")
                stats.add(f"{kind}_done")
                return
            stats.add(f"http_{e.code}")
        except Exception as e:  # noqa: BLE001 - timeouts, resets, LZMA errors all retry identically
            last = type(e).__name__
            stats.add("net_error")
        time.sleep(min(60.0, 3.0 * 1.7 ** (attempt - 1)) * (0.7 + 0.6 * random.random()))
    cp.record({"key": key, "status": "FAILED", "bytes": 0, "attempts": max_attempts, "last_error": last,
               "ts": dt.datetime.now(dt.timezone.utc).isoformat()})
    stats.add("failed")


def status(cp: Checkpoint, start: dt.date, end: dt.date) -> dict:
    out = {"candles": {}, "ticks": {}}
    for kind in ("candles", "ticks"):
        for (k, pair, d, side, hour) in build_units(start, end, [kind]):
            key = unit_key(k, pair, d, side, hour)
            s = cp.state.get(key, {}).get("status", "PENDING")
            out[kind][s] = out[kind].get(s, 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="large-data root (e.g. E:\\Tradingdata); never inside git")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--tiers", default="candles,ticks")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-attempts", type=int, default=10)
    ap.add_argument("--max-minutes", type=float, default=None)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    cp_dir = root / "checkpoints" / "dukascopy"
    cp = Checkpoint(cp_dir / "fast6m_acquisition.jsonl")
    if a.status:
        print(json.dumps(status(cp, start, end), indent=2))
        return
    stop_file = cp_dir / "STOP"
    stop_file.unlink(missing_ok=True)
    deadline = time.time() + a.max_minutes * 60 if a.max_minutes else None
    units = list(build_units(start, end, a.tiers.split(",")))
    print(f"[{dt.datetime.now():%H:%M:%S}] {len(units)} units ({a.tiers}); workers={a.workers}", flush=True)
    stats = Stats()
    t0 = time.time()
    stop_report = threading.Event()

    def reporter():
        while not stop_report.wait(60):
            with stats.lock:
                snap = dict(stats.c)
            fetched = snap.get("ok", 0) + snap.get("empty", 0) + snap.get("not_found", 0)
            print(f"[{dt.datetime.now():%H:%M:%S}] fetched={fetched} rate={fetched / max(1, time.time() - t0):.2f}/s "
                  f"{json.dumps(snap, sort_keys=True)}", flush=True)

    threading.Thread(target=reporter, daemon=True).start()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(fetch_unit, root, cp, stats, stop_file, deadline, k, p, d, s, h, a.max_attempts)
                for (k, p, d, s, h) in units]
        for f in futs:
            f.result()
    stop_report.set()
    print("FINISHED", json.dumps(stats.c, sort_keys=True), flush=True)
    print(json.dumps(status(cp, start, end), indent=2), flush=True)


if __name__ == "__main__":
    main()
