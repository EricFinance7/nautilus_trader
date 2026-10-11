"""Pre-registered evidence classification (rules frozen in specs.HARNESS['evidence_rules'] before any evaluation).

Decision order: INSUFFICIENT_DATA -> NEGATIVE_EVIDENCE -> SHADOW_FORWARD_ELIGIBLE / PROMISING_RESEARCH -> MIXED_EVIDENCE.
Inputs are summaries from metrics.by_partition for the RESEARCH-mode runs (base costs; adverse costs for the shadow gate).
"""
from __future__ import annotations

import math


def _g(d: dict, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def classify(base: dict, adverse: dict | None, pair_stab: dict, regime: dict, governed_mdd_fraction: float | None) -> dict:
    ev = {}
    ep_all = _g(base, "ALL_EVALUATED", "unique_episodes", default=0)
    ep_vo = _g(base, "VAL_PLUS_OOS", "unique_episodes", default=0)
    ep_oos = _g(base, "OUT_OF_SAMPLE", "unique_episodes", default=0)
    ev["unique_episodes"] = {"all": ep_all, "val_plus_oos": ep_vo, "oos": ep_oos}
    if ep_all < 30 or ep_vo < 15:
        return {"classification": "INSUFFICIENT_DATA", "criteria": ev,
                "reason": f"unique episodes: all={ep_all} (<30?) val+oos={ep_vo} (<15?)"}
    m = {k: _g(base, k, "mean_net_r") for k in ("DEVELOPMENT", "VALIDATION", "OUT_OF_SAMPLE")}
    pooled = _g(base, "VAL_PLUS_OOS", "mean_net_r")
    lo, hi = _g(base, "VAL_PLUS_OOS", "mean_net_r_ci95", default=[float("nan")] * 2)
    pf = _g(base, "VAL_PLUS_OOS", "profit_factor_r")
    ev.update({"mean_net_r_by_partition": m, "pooled_val_oos_mean_net_r": pooled, "pooled_ci95": [lo, hi], "pooled_profit_factor": pf})
    finite = lambda x: x is not None and not (isinstance(x, float) and math.isnan(x))
    neg = (finite(pooled) and pooled < 0) and ((finite(hi) and hi < 0) or all(finite(v) and v < 0 for v in m.values()))
    if neg:
        return {"classification": "NEGATIVE_EVIDENCE", "criteria": ev,
                "reason": "pooled VAL+OOS mean net R < 0 with CI upper < 0 or negative in every partition"}
    pos_all = all(finite(v) and v > 0 for v in m.values())
    pairs_pos = sum(1 for v in pair_stab.values() if v["mean_net_r"] > 0)
    ev["pairs_positive"] = pairs_pos
    promising = (pos_all and finite(lo) and lo > 0 and finite(pf) and pf >= 1.2 and pairs_pos >= 4)
    if promising:
        adv = _g(adverse or {}, "VAL_PLUS_OOS", "mean_net_r")
        terc = [v["mean_net_r"] for v in (regime.get("volatility_tercile") or {}).values() if v.get("mean_net_r") is not None]
        terc_pos = sum(1 for v in terc if v > 0)
        ev.update({"adverse_pooled_mean_net_r": adv, "volatility_terciles_positive": terc_pos, "governed_max_drawdown_fraction": governed_mdd_fraction})
        shadow = (finite(adv) and adv > 0 and (governed_mdd_fraction is not None and governed_mdd_fraction < 0.10)
                  and ep_all >= 100 and ep_oos >= 30 and terc_pos >= 2)
        return {"classification": "SHADOW_FORWARD_ELIGIBLE" if shadow else "PROMISING_RESEARCH", "criteria": ev,
                "reason": "all PROMISING criteria met" + (" and all SHADOW criteria met" if shadow else "; SHADOW criteria not all met")}
    return {"classification": "MIXED_EVIDENCE", "criteria": ev,
            "reason": "sufficient data; neither NEGATIVE_EVIDENCE nor PROMISING_RESEARCH criteria satisfied"}
