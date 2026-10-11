"""Tick-fidelity check: how well do candle-synthesized quotes approximate REAL tick execution?

For a window covered by real ticks for all seven pairs, each arm is run twice in RESEARCH/base mode: (a) from the
candle-synthesized quote stream used for the full-window evaluation, (b) from the real tick stream. Trades are matched by
(pair, direction, signal bar close). Differences in matched entry/exit prices and in R quantify the approximation error.
This is a validation of the SIMULATION, not a strategy evaluation; it must be run on a window that is not used to judge
strategies (the DEVELOPMENT partition).

  python -m fast_research.run_fidelity --minute-dir <dir> --tick-dir <dir> --start <iso> --end <iso> --out fidelity.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .harness import instruments as I, runner

FAMILIES = ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "F07R"]


def compare(candle_trades, tick_trades):
    key = lambda t: (t["pair"], t["dir"], t["signal_close_ns"])
    c, k = {key(t): t for t in candle_trades}, {key(t): t for t in tick_trades}
    both = sorted(set(c) & set(k))
    out = {"n_candle": len(c), "n_tick": len(k), "n_matched": len(both)}
    if both:
        pip = lambda t: I.PIP[t["pair"]]
        ent = [abs(c[x]["entry_px"] - k[x]["entry_px"]) / pip(c[x]) for x in both]
        ext = [abs(c[x]["exit_px"] - k[x]["exit_px"]) / pip(c[x]) for x in both]
        dr = [c[x]["r_net"] - k[x]["r_net"] for x in both]
        out.update({
            "entry_abs_diff_pips_mean": float(np.mean(ent)), "entry_abs_diff_pips_max": float(np.max(ent)),
            "exit_abs_diff_pips_mean": float(np.mean(ext)), "exit_abs_diff_pips_max": float(np.max(ext)),
            "r_diff_mean(candle-tick)": float(np.mean(dr)), "r_abs_diff_mean": float(np.mean(np.abs(dr))),
            "same_exit_reason_fraction": float(np.mean([c[x]["exit_reason"] == k[x]["exit_reason"] for x in both])),
            "stop_exit_fraction_candle": float(np.mean([t["exit_reason"] == "STOP" for t in candle_trades])) if candle_trades else None,
            "stop_exit_fraction_tick": float(np.mean([t["exit_reason"] == "STOP" for t in tick_trades])) if tick_trades else None})
    out["net_eur_candle"] = float(sum(t["net_eur"] for t in candle_trades))
    out["net_eur_tick"] = float(sum(t["net_eur"] for t in tick_trades))
    out["mean_net_r_candle"] = float(np.mean([t["r_net"] for t in candle_trades])) if candle_trades else None
    out["mean_net_r_tick"] = float(np.mean([t["r_net"] for t in tick_trades])) if tick_trades else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minute-dir", required=True)
    ap.add_argument("--tick-dir", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--families", default=",".join(FAMILIES))
    a = ap.parse_args()
    res = {"window": [a.start, a.end], "arms": {}}
    for i, fam in enumerate(a.families.split(",")):
        rc = runner.run_arm(fam, "base", Path(a.minute_dir), a.start, a.end, mode="research", tag=100 + 2 * i)
        rt = runner.run_arm(fam, "base", Path(a.minute_dir), a.start, a.end, mode="research", tag=101 + 2 * i, tick_dir=a.tick_dir)
        res["arms"][fam] = compare(rc["trades"], rt["trades"])
        res["arms"][fam].update({"n_quotes_candle": rc["n_quotes"], "n_quotes_tick": rt["n_quotes"]})
        print(fam, json.dumps(res["arms"][fam], default=str), flush=True)
    Path(a.out).write_text(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
