"""Run the common evaluation for F01-F07 (+ the pre-declared F07R mirror arm).

Every arm is run in its own NautilusTrader engine with its own EUR 500 account. Runs per arm:
    RESEARCH mode  x  optimistic / base / adverse costs     (evidence + cost sensitivity, fixed EUR 500 sizing, no pause)
    GOVERNED mode  x  base costs                            (what the capital rules would actually have done)
Window: DEVELOPMENT + VALIDATION + OUT_OF_SAMPLE only (RESERVED_FORWARD is never touched here).

  python -m fast_research.run_evaluation --minute-dir <normalized minute dir> --out-dir <results dir> [--workers 4]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import time
from pathlib import Path

from . import specs as S
from .harness import runner

FAMILIES = ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "F07R"]
RUNS = [("research", "optimistic"), ("research", "base"), ("research", "adverse"), ("governed", "base")]


def _one(args):
    family, mode, scenario, minute_dir, start, end, out_dir, tag = args
    out = Path(out_dir) / "runs" / f"{family}_{mode}_{scenario}.json"
    if out.exists():
        return str(out), "cached", 0.0
    t0 = time.time()
    journal = Path(out_dir) / "journals" / f"{family}_{mode}_{scenario}.jsonl"
    r = runner.run_arm(family, scenario, Path(minute_dir), start, end, tag=tag, mode=mode, journal_path=str(journal))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, default=str))
    return str(out), "ran", time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minute-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--start", default=S.HARNESS["partitions"]["DEVELOPMENT"][0])
    ap.add_argument("--end", default=S.HARNESS["partitions"]["OUT_OF_SAMPLE"][1])
    a = ap.parse_args()
    out_dir = Path(a.out_dir)
    (out_dir / "journals").mkdir(parents=True, exist_ok=True)
    (out_dir / "runs").mkdir(parents=True, exist_ok=True)
    (out_dir / "RUN_CONFIG.json").write_text(json.dumps({
        "start": a.start, "end": a.end, "families": a.families.split(","), "runs": RUNS,
        "harness_sha256": S.sha256(S.HARNESS), "config_hashes": {f: S.config_hash("F07" if f == "F07R" else f) for f in a.families.split(",")},
        "note": "RESERVED_FORWARD (from %s) is excluded from this evaluation." % S.HARNESS["partitions"]["RESERVED_FORWARD"][0],
    }, indent=2))
    jobs, tag = [], 1
    for fam in a.families.split(","):
        for mode, sc in RUNS:
            jobs.append((fam, mode, sc, a.minute_dir, a.start, a.end, str(out_dir), tag)); tag += 1
    t0 = time.time()
    with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
        for path, status, secs in ex.map(_one, jobs):
            print(f"[{time.time() - t0:7.0f}s] {status:6s} {secs:6.0f}s  {Path(path).name}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
