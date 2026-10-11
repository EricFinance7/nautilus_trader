"""Turn the per-arm run files into the common-methodology evidence tables and pre-registered classifications.

  python -m fast_research.analyze --runs-dir <results dir> --out-dir research/fast_strategies/results
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

from . import specs as S
from .harness import evidence as EV, metrics as MT

FAMILIES = ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "F07R"]
EVALUATED = ("DEVELOPMENT", "VALIDATION", "OUT_OF_SAMPLE")


def load(runs_dir: Path, fam: str, mode: str, scenario: str):
    p = runs_dir / "runs" / f"{fam}_{mode}_{scenario}.json"
    return json.loads(p.read_text()) if p.exists() else None


def fmt(x, nd=2):
    if x is None:
        return "-"
    if isinstance(x, float) and (x != x):
        return "n/a"
    if isinstance(x, float) and x == float("inf"):
        return "inf"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def analyze(runs_dir: Path, resamples: int = 5000) -> dict:
    P = S.HARNESS["partitions"]
    cfg = json.loads((runs_dir / "RUN_CONFIG.json").read_text())
    window = (int(pd.Timestamp(cfg["start"]).value), int(pd.Timestamp(cfg["end"]).value))
    out = {"run_config": cfg, "families": {}}
    for fam in FAMILIES:
        base = load(runs_dir, fam, "research", "base")
        if base is None:
            continue
        opt, adv = load(runs_dir, fam, "research", "optimistic"), load(runs_dir, fam, "research", "adverse")
        gov = load(runs_dir, fam, "governed", "base")
        ev_trades = [t for t in base["trades"] if MT.partition_of(t["entry_ts_ns"], P) in EVALUATED]
        parts = MT.by_partition(base["trades"], P, window, resamples)
        parts_adv = MT.by_partition(adv["trades"], P, window, resamples) if adv else None
        parts_opt = MT.by_partition(opt["trades"], P, window, resamples) if opt else None
        pairs = MT.stability_by_pair(ev_trades) if ev_trades else {}
        regime = MT.stability_by_regime(ev_trades) if ev_trades else {}
        gov_trades = [t for t in (gov["trades"] if gov else []) if MT.partition_of(t["entry_ts_ns"], P) in EVALUATED]
        gov_mdd_eur, gov_mdd_frac = MT.max_drawdown(gov_trades) if gov_trades else (0.0, 0.0)
        cls = EV.classify(parts, parts_adv, pairs, regime, gov_mdd_frac if gov else None)
        out["families"][fam] = {
            "config_hash": base["config_hash"], "harness_sha256": base["harness_sha256"], "nautilus_trader": base["nautilus_trader"],
            "classification": cls, "partitions_base": parts,
            "cost_sensitivity": {
                "optimistic": parts_opt["ALL_EVALUATED"] if parts_opt else None,
                "base": parts["ALL_EVALUATED"], "adverse": parts_adv["ALL_EVALUATED"] if parts_adv else None},
            "by_pair": pairs, "by_regime": regime,
            "governed": None if not gov else {
                "n_trades": len(gov_trades), "final_ledger_equity_eur": gov["ledger_equity_eur"],
                "engine_balance_eur": gov["engine_balance_eur"], "ledger_minus_engine_eur": gov["ledger_minus_engine_eur"],
                "paused_drawdown": gov["paused_drawdown"], "max_drawdown_eur": gov_mdd_eur, "max_drawdown_fraction": gov_mdd_frac,
                "net_eur": sum(t["net_eur"] for t in gov_trades)},
            "reject_counts_research_base": base["reject_counts"],
            "tf_resets": base["tf_resets"], "seconds": base["seconds"],
        }
    return out


def tables(res: dict) -> str:
    L = ["# F01-F07 evaluation: common-methodology evidence table", "",
         f"Window: {res['run_config']['start']} -> {res['run_config']['end']} (DEVELOPMENT + VALIDATION + OUT_OF_SAMPLE; RESERVED_FORWARD untouched).",
         "All figures are RESEARCH-mode, BASE cost scenario (fixed EUR 500 sizing, drawdown pause off) unless stated. R = net P&L / risk at the stop.", "",
         "## Summary (all evaluated partitions)", "",
         "| Arm | Class | Trades | Indep. episodes (trades/episode) | Gross (mid-to-mid, before any cost) % of 500 | Net (after spread, slippage, commission) % of 500 | Mean net R [95% CI] | Win % | Avg win EUR | Avg loss EUR | Profit factor (R) | Max DD % | Exposure % |",
         "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for fam, d in res["families"].items():
        a = d["partitions_base"]["ALL_EVALUATED"]
        if a["n_trades"] == 0:
            L.append(f"| {fam} | {d['classification']['classification']} | 0 | 0 | - | - | - | - | - | - | - | - | - |")
            continue
        ci = a["mean_net_r_ci95"]
        L.append(f"| {fam} | **{d['classification']['classification']}** | {a['n_trades']} | {a['unique_episodes']} ({fmt(a['trades_per_episode_mean'], 2)}) | {fmt(a['gross_return_pct_of_500'])} | "
                 f"{fmt(a['net_return_pct_of_500'])} | {fmt(a['mean_net_r'], 3)} [{fmt(ci[0], 3)}, {fmt(ci[1], 3)}] | {fmt(100 * a['win_rate'], 1)} | "
                 f"{fmt(a['avg_win_eur'])} | {fmt(a['avg_loss_eur'])} | {fmt(a['profit_factor_r'])} | {fmt(100 * a['max_drawdown_fraction'], 1)} | {fmt(100 * a['any_position_fraction'], 1)} |")
    L += ["", "## By partition (mean net R, trades / episodes)", "",
          "| Arm | DEVELOPMENT | VALIDATION | OUT_OF_SAMPLE | VAL+OOS pooled [95% CI] |", "|---|---|---|---|---|"]
    for fam, d in res["families"].items():
        p = d["partitions_base"]
        cell = lambda k: ("-" if p[k]["n_trades"] == 0 else f"{fmt(p[k]['mean_net_r'], 3)} ({p[k]['n_trades']}/{p[k]['unique_episodes']})")
        pv = p["VAL_PLUS_OOS"]
        pooled = "-" if pv["n_trades"] == 0 else f"{fmt(pv['mean_net_r'], 3)} [{fmt(pv['mean_net_r_ci95'][0], 3)}, {fmt(pv['mean_net_r_ci95'][1], 3)}]"
        L.append(f"| {fam} | {cell('DEVELOPMENT')} | {cell('VALIDATION')} | {cell('OUT_OF_SAMPLE')} | {pooled} |")
    L += ["", "## Cost sensitivity (all evaluated, RESEARCH mode)", "", "| Arm | Optimistic: trades, mean R, net EUR | Base | Adverse |", "|---|---|---|---|"]
    for fam, d in res["families"].items():
        def c(x):
            return "-" if not x or x["n_trades"] == 0 else f"{x['n_trades']}, {fmt(x['mean_net_r'], 3)}, {fmt(x['net_eur'])}"
        cs = d["cost_sensitivity"]
        L.append(f"| {fam} | {c(cs['optimistic'])} | {c(cs['base'])} | {c(cs['adverse'])} |")
    L += ["", "## GOVERNED run (the real EUR 500 capital rules: compounding sizing, 10% drawdown pause)", "",
          "| Arm | Trades | Final ledger equity EUR | Net EUR | Max DD % | Drawdown pause triggered | Ledger minus engine EUR |", "|---|---:|---:|---:|---:|---|---:|"]
    for fam, d in res["families"].items():
        g = d["governed"]
        if g:
            L.append(f"| {fam} | {g['n_trades']} | {fmt(g['final_ledger_equity_eur'])} | {fmt(g['net_eur'])} | {fmt(100 * g['max_drawdown_fraction'], 1)} | {g['paused_drawdown']} | {fmt(g['ledger_minus_engine_eur'])} |")
    L += ["", "## Why trades were NOT taken (RESEARCH/base rejection counts)", ""]
    for fam, d in res["families"].items():
        L.append(f"- **{fam}**: {json.dumps(d['reject_counts_research_base'], sort_keys=True)}")
    L += ["", "## Classification reasons", ""]
    for fam, d in res["families"].items():
        L.append(f"- **{fam}** -> {d['classification']['classification']}: {d['classification']['reason']}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--resamples", type=int, default=5000)
    a = ap.parse_args()
    runs_dir, out_dir = Path(a.runs_dir), Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    res = analyze(runs_dir, a.resamples)
    (out_dir / "evidence_summary.json").write_text(json.dumps(res, indent=2, default=str))
    (out_dir / "EVIDENCE_TABLE.md").write_text(tables(res), encoding="utf-8")
    for fam in res["families"]:
        base = load(runs_dir, fam, "research", "base")
        cols = ["family", "pair", "dir", "units", "signal", "entry_ts_ns", "exit_ts_ns", "entry_px", "exit_px", "exit_reason",
                "gross_eur", "gross_fill_eur", "net_eur", "cost_eur", "spread_slippage_cost_eur", "commission_eur", "planned_risk_eur", "actual_risk_eur", "r_net", "spread_pips_at_signal", "group"]
        with open(out_dir / f"trades_{fam}_research_base.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(base["trades"])
    print((out_dir / "EVIDENCE_TABLE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
