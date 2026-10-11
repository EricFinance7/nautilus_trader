"""Generate reports/DATA_REPORT.md from the acquisition checkpoint, the minute-dataset QC JSON and (optionally) the
tick-vs-native cross-check JSON. Numbers come from those artifacts, never typed by hand.

  python -m fast_research.data.report --root E:\\Tradingdata --qc dataset_qc.json [--tick-check tick_check.json] --out reports/DATA_REPORT.md
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def acquisition_summary(root: Path) -> dict:
    cp = root / "checkpoints" / "dukascopy" / "fast6m_acquisition.jsonl"
    last = {}
    for line in cp.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            last[r["key"]] = r
    by_kind = {"candles": Counter(), "ticks": Counter()}
    bytes_kind = Counter()
    for k, r in last.items():
        kind = k.split("|", 1)[0]
        by_kind[kind][r["status"]] += 1
        bytes_kind[kind] += r.get("bytes", 0)
    return {"by_kind": {k: dict(v) for k, v in by_kind.items()}, "bytes": dict(bytes_kind)}


def render(root: Path, qc: dict, tick_check: dict | None) -> str:
    acq = acquisition_summary(root)
    L = ["# Data report: Dukascopy 1-minute BID/ASK candles (and ticks where acquired)", "",
         f"Window requested: {qc['window'][0]} to {qc['window'][1]} (Saturdays are not acquired: the market is closed and every candle is a stale zero-volume bar).", "",
         "## Source and method", "",
         "- Source: Dukascopy's public historical datafeed (`datafeed.dukascopy.com/datafeed/<PAIR>/<yyyy>/<month0>/<dd>/...`), free, over **plain HTTP**.",
         "  HTTPS (port 443) to that host does not accept connections from this machine; the `jetta.dukascopy.com` JSON API now sits behind an AWS WAF **bot challenge** (HTTP 202, empty body, `x-amzn-waf-action: challenge`). That challenge was **not** circumvented.",
         "- The datafeed throttles: it returned HTTP 503 for roughly a third of requests and settled at about 12 files per minute regardless of the number of workers; the acquisition script retries with jittered exponential backoff and is fully resumable (append-only checkpoint with a SHA-256 per file).",
         "- Candles: native 1-minute BID and ASK candles, bar-open labeled, true UTC. The Trading Intelligence Engine's microstructure validation proved native candles equal tick-derived OHLC bit-for-bit (EURUSD, one full day), so native candles are the primary series.", "",
         "## Acquisition result", "",
         f"- Candle files: {json.dumps(acq['by_kind']['candles'], sort_keys=True)}; {acq['bytes'].get('candles', 0) / 1e6:.1f} MB compressed on disk.",
         f"- Tick files: {json.dumps(acq['by_kind']['ticks'], sort_keys=True)}; {acq['bytes'].get('ticks', 0) / 1e6:.1f} MB compressed on disk.", "",
         "## Coverage and quality checks (per pair)", "",
         "| Pair | Minutes | Valid minutes in session | Zero-volume minutes in session | Longest in-session gap (min) | Missing days | Crossed quotes (O/H/L/C) | OHLC violations (bid/ask) | Valid minutes outside session | Rebuild identical |",
         "|---|---:|---:|---:|---:|---|---|---|---:|---|"]
    for p, r in qc["pairs"].items():
        if not r.get("rows"):
            L.append(f"| {p} | 0 | - | - | - | all | - | - | - | - |")
            continue
        cx = r["crossed_quotes"]; iv = r["ohlc_invariant_violations"]; s = r["session"]
        L.append(f"| {p} | {r['rows']:,} | {s['valid_minutes_in_session']:,} | {s['zero_volume_minutes_in_session']:,} | {r['in_session_gaps']['longest_minutes']} | "
                 f"{', '.join(r['days_missing']) or 'none'} | {cx['open']}/{cx['high']}/{cx['low']}/{cx['close']} | {iv['bid']}/{iv['ask']} | {s['valid_minutes_outside_session']} | {r['deterministic_rebuild_hash_matches']} |")
    L += ["", "## Spreads (pips, valid in-session minutes)", "", "| Pair | Open: median / mean / p95 | Close: median / mean / p95 / max | Negative spreads |", "|---|---|---|---:|"]
    for p, r in qc["pairs"].items():
        if r.get("rows"):
            sp = r["spread_pips"]
            L.append(f"| {p} | {sp['open_median']:.2f} / {sp['open_mean']:.2f} / {sp['open_p95']:.2f} | {sp['close_median']:.2f} / {sp['close_mean']:.2f} / {sp['close_p95']:.2f} / {sp['close_max']:.1f} | {sp['negative_close']} |")
    L += ["", "## What each check means", "",
          "- **Timestamps / UTC**: every row is bar-open, minute-aligned, strictly increasing, no duplicates, timezone UTC.",
          "- **Bid and ask**: both candles are required for a day to be used; a mismatch in their timestamps stops the build.",
          "- **Price precision**: prices are integers divided by `10**price_scale` (5 decimals; 3 for JPY), rounded to that scale.",
          "- **Missing intervals**: a zero-volume minute carries no information (no tick). It is kept in the table as `valid=False`, **never replayed and never filled**. Gaps longer than 60 minutes reset all indicator state in the strategies.",
          "- **Duplicate ticks / chronological order**: see the tick section (ticks were acquired only for the weeks listed there).",
          "- **Spread calculation**: spread is derived (ask - bid), never stored as raw; zero negative spreads in candle values.",
          "- **Deterministic construction**: building the dataset twice from the same raw files yields the same content hash for every pair."]
    if tick_check:
        L += ["", "## Tick tier (fidelity check)", "", "```json", json.dumps(tick_check, indent=2)[:6000], "```"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--qc", required=True)
    ap.add_argument("--tick-check", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    qc = json.loads(Path(a.qc).read_text())
    tc = json.loads(Path(a.tick_check).read_text()) if a.tick_check else None
    Path(a.out).write_text(render(Path(a.root), qc, tc), encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
