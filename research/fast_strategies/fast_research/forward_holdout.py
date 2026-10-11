"""Supplementary RESERVED_FORWARD summary: one pass of the frozen strategies, no reclassification.

  python -m fast_research.forward_holdout --runs-dir <dir> --out results/reserved_forward/FORWARD_HOLDOUT.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

FAMILIES = ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "F07R"]


def summarize(trades):
    if not trades:
        return None
    r = np.array([t["r_net"] for t in trades], float)
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    return {"n": len(r), "mean_r": float(r.mean()), "win_pct": float((r > 0).mean() * 100),
            "pf": float(wins / losses) if losses > 0 else None,
            "net_eur": float(sum(t["net_eur"] for t in trades)),
            "gross_eur": float(sum(t.get("gross_eur", 0.0) for t in trades))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs = Path(a.runs_dir) / "runs"
    L = ["# Supplementary forward-holdout (RESERVED_FORWARD) pass", "",
         "One pass of the frozen strategies over the reserved period (2026-09-20T19:12Z to 2026-10-10), RESEARCH mode. It is reported **for information only**: "
         "it does not change any classification (those were fixed on DEV+VAL+OOS), it is a short window (about 3 weeks), and trades overlap in time, so per-trade statistics here are not independent.", "",
         "| Arm | Scenario | Trades | Mean net R | Win % | Profit factor | Gross EUR (mid-to-mid) | Net EUR |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    out = {}
    for fam in FAMILIES:
        for sc in ("optimistic", "base", "adverse"):
            f = runs / f"{fam}_research_{sc}.json"
            if not f.exists():
                continue
            s = summarize(json.loads(f.read_text())["trades"])
            out[f"{fam}_{sc}"] = s
            if s is None:
                L.append(f"| {fam} | {sc} | 0 | - | - | - | - | - |")
            else:
                pf = f"{s['pf']:.2f}" if s["pf"] is not None else "-"
                L.append(f"| {fam} | {sc} | {s['n']} | {s['mean_r']:+.3f} | {s['win_pct']:.1f} | {pf} | {s['gross_eur']:+.2f} | {s['net_eur']:+.2f} |")
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    Path(a.out).with_suffix(".json").write_text(json.dumps(out, indent=2))
    print("\n".join(L))


if __name__ == "__main__":
    main()
