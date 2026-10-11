"""Common evaluation metrics for every F-family arm (identical methodology for F01-F07).

Unit of analysis is R = net P&L (EUR) / actual risk at the stop (EUR), which removes position-size path effects.
Trades are grouped into independent EPISODES (a trade joins an open episode if it is within 60 min of the episode's
latest entry and shares a currency exposure with the same net direction), and the bootstrap resamples whole episodes,
so correlated same-currency trades are not counted as independent evidence.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

from . import session as SE

NS_MIN = 60_000_000_000


def partition_of(entry_ns: int, partitions: dict) -> str | None:
    t = pd.Timestamp(entry_ns, unit="ns", tz="UTC")
    for name in ("DEVELOPMENT", "VALIDATION", "OUT_OF_SAMPLE", "RESERVED_FORWARD"):
        a, b = (pd.Timestamp(x) for x in partitions[name])
        if a <= t < b:
            return name
    return None


def exposures(pair: str, d: int) -> dict:
    return {pair[:3]: d, pair[3:]: -d}


def assign_episodes(trades: list, gap_minutes: int = 60) -> list:
    """Returns a list of episode ids aligned with `trades` (any order). Greedy, time ordered."""
    order = sorted(range(len(trades)), key=lambda i: trades[i]["entry_ts_ns"])
    eps = []   # dicts: last_ts, exp (net exposure per currency)
    ids = [None] * len(trades)
    for i in order:
        t = trades[i]
        ex = exposures(t["pair"], t["dir"])
        joined = None
        for k, e in enumerate(eps):
            if t["entry_ts_ns"] - e["last"] <= gap_minutes * NS_MIN and any(
                    c in e["exp"] and e["exp"][c] * s > 0 for c, s in ex.items()):
                joined = k
                break
        if joined is None:
            eps.append({"last": t["entry_ts_ns"], "exp": dict(ex)})
            joined = len(eps) - 1
        else:
            e = eps[joined]
            e["last"] = t["entry_ts_ns"]
            for c, s in ex.items():
                e["exp"][c] = e["exp"].get(c, 0) + s
        ids[i] = joined
    return ids


def cluster_bootstrap_mean(values: list, clusters: list, resamples: int = 5000, seed: int = 20261011, ci: float = 0.95):
    """Episode-level bootstrap of the pooled mean. Returns (mean, lo, hi)."""
    if not values:
        return float("nan"), float("nan"), float("nan")
    by = {}
    for v, c in zip(values, clusters):
        by.setdefault(c, []).append(v)
    groups = [np.asarray(v, dtype=float) for v in by.values()]
    sums = np.array([g.sum() for g in groups]); cnts = np.array([len(g) for g in groups])
    rng = np.random.default_rng(seed)
    n = len(groups)
    idx = rng.integers(0, n, size=(resamples, n))
    means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    lo, hi = np.quantile(means, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return float(np.mean(np.concatenate(groups))), float(lo), float(hi)


def profit_factor(rs) -> float:
    w = sum(r for r in rs if r > 0)
    l = -sum(r for r in rs if r < 0)
    if l == 0:
        return float("inf") if w > 0 else float("nan")
    return w / l


def max_drawdown(trades: list, start_equity: float = 500.0):
    """Peak-to-trough on cumulative NET EUR booked in exit order. Returns (eur, fraction of the running peak)."""
    eq, peak, mdd, mdd_frac = start_equity, start_equity, 0.0, 0.0
    for t in sorted(trades, key=lambda x: x["exit_ts_ns"]):
        eq += t["net_eur"]
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
        mdd_frac = max(mdd_frac, (peak - eq) / peak)
    return mdd, mdd_frac


def exposure_fraction(trades: list, window_start_ns: int, window_end_ns: int) -> dict:
    """Share of the window during which at least one position was open (interval union), plus mean concurrency."""
    iv = sorted((t["entry_ts_ns"], t["exit_ts_ns"]) for t in trades)
    union, cur = 0, None
    for a, b in iv:
        if cur is None or a > cur[1]:
            if cur:
                union += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        union += cur[1] - cur[0]
    total = max(window_end_ns - window_start_ns, 1)
    return {"any_position_fraction": union / total, "position_minutes": sum(b - a for a, b in iv) / NS_MIN,
            "mean_concurrency": sum(b - a for a, b in iv) / total}


def summarize(trades: list, partitions: dict, window: tuple, resamples: int = 5000) -> dict:
    out = {"n_trades": len(trades)}
    if not trades:
        return out
    rs = [t["r_net"] for t in trades]
    ids = assign_episodes(trades)
    n_ep = len(set(ids))
    m, lo, hi = cluster_bootstrap_mean(rs, ids, resamples)
    wins = [t["net_eur"] for t in trades if t["net_eur"] > 0]
    losses = [t["net_eur"] for t in trades if t["net_eur"] <= 0]
    mdd, mdd_frac = max_drawdown(trades)
    hold = [(t["exit_ts_ns"] - t["entry_ts_ns"]) / NS_MIN for t in trades]
    out.update({
        "unique_episodes": n_ep, "trades_per_episode_mean": len(trades) / n_ep,
        "share_of_trades_in_multi_trade_episodes": sum(1 for i in ids if ids.count(i) > 1) / len(ids) if len(ids) < 5000 else None,
        "gross_eur": sum(t["gross_eur"] for t in trades), "net_eur": sum(t["net_eur"] for t in trades),
        "cost_eur": sum(t["cost_eur"] for t in trades),
        "spread_slippage_cost_eur": sum(t.get("spread_slippage_cost_eur", 0.0) for t in trades),
        "commission_eur": sum(t.get("commission_eur", 0.0) for t in trades),
        "gross_return_pct_of_500": 100 * sum(t["gross_eur"] for t in trades) / 500.0,
        "net_return_pct_of_500": 100 * sum(t["net_eur"] for t in trades) / 500.0,
        "mean_net_eur": float(np.mean([t["net_eur"] for t in trades])),
        "mean_net_r": m, "mean_net_r_ci95": [lo, hi],
        "win_rate": len(wins) / len(trades),
        "avg_win_eur": float(np.mean(wins)) if wins else 0.0, "avg_loss_eur": float(np.mean(losses)) if losses else 0.0,
        "profit_factor_r": profit_factor(rs),
        "max_drawdown_eur": mdd, "max_drawdown_fraction": mdd_frac,
        "holding_minutes_mean": float(np.mean(hold)), "holding_minutes_median": float(np.median(hold)),
        "exits": {k: sum(1 for t in trades if t["exit_reason"] == k) for k in sorted({t["exit_reason"] for t in trades})},
    })
    out.update(exposure_fraction(trades, *window))
    return out


def by_partition(trades: list, partitions: dict, window: tuple, resamples: int = 5000) -> dict:
    res = {}
    for name in ("DEVELOPMENT", "VALIDATION", "OUT_OF_SAMPLE"):
        sub = [t for t in trades if partition_of(t["entry_ts_ns"], partitions) == name]
        a, b = (int(pd.Timestamp(x).value) for x in partitions[name])
        res[name] = summarize(sub, partitions, (max(a, window[0]), min(b, window[1])), resamples)
    pooled = [t for t in trades if partition_of(t["entry_ts_ns"], partitions) in ("VALIDATION", "OUT_OF_SAMPLE")]
    a = int(pd.Timestamp(partitions["VALIDATION"][0]).value); b = int(pd.Timestamp(partitions["OUT_OF_SAMPLE"][1]).value)
    res["VAL_PLUS_OOS"] = summarize(pooled, partitions, (a, min(b, window[1])), resamples)
    res["ALL_EVALUATED"] = summarize([t for t in trades if partition_of(t["entry_ts_ns"], partitions) in
                                      ("DEVELOPMENT", "VALIDATION", "OUT_OF_SAMPLE")], partitions, window, resamples)
    return res


def stability_by_pair(trades: list) -> dict:
    out = {}
    for p in sorted({t["pair"] for t in trades}):
        sub = [t for t in trades if t["pair"] == p]
        out[p] = {"n": len(sub), "mean_net_r": float(np.mean([t["r_net"] for t in sub])),
                  "net_eur": sum(t["net_eur"] for t in sub), "win_rate": sum(1 for t in sub if t["net_eur"] > 0) / len(sub)}
    return out


def stability_by_regime(trades: list) -> dict:
    """Session at entry, and volatility terciles of the (price-normalised) stop distance, a per-arm proxy for the
    volatility regime in which the trade was taken."""
    out = {"session": {}, "volatility_tercile": {}}
    for t in trades:
        s = SE.classify_session(t["entry_ts_ns"])
        out["session"].setdefault(s, []).append(t["r_net"])
    out["session"] = {k: {"n": len(v), "mean_net_r": float(np.mean(v))} for k, v in sorted(out["session"].items())}
    vals = [t.get("stop_distance", 0) / t["entry_px"] for t in trades if t.get("stop_distance")]
    if len(vals) >= 3:
        q1, q2 = np.quantile(vals, [1 / 3, 2 / 3])
        buckets = {"low": [], "mid": [], "high": []}
        for t in trades:
            if not t.get("stop_distance"):
                continue
            v = t["stop_distance"] / t["entry_px"]
            buckets["low" if v <= q1 else ("mid" if v <= q2 else "high")].append(t["r_net"])
        out["volatility_tercile"] = {k: {"n": len(v), "mean_net_r": float(np.mean(v)) if v else None} for k, v in buckets.items()}
    return out
