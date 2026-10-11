"""Tests for episode clustering, cluster bootstrap, partitions, drawdown and the pre-registered evidence classifier."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fast_research import specs as S  # noqa: E402
from fast_research.harness import evidence as EV, metrics as MT  # noqa: E402

MIN = 60 * 10**9
P = S.HARNESS["partitions"]


def ns(s):
    return int(pd.Timestamp(s, tz="UTC").value)


def tr(entry, pair="EURUSD", d=1, r=1.0, hold=30, net=None, reason="TIME_EXIT", stop=0.0010, px=1.1):
    e = ns(entry)
    n = r * 2.0 if net is None else net
    return {"entry_ts_ns": e, "exit_ts_ns": e + hold * MIN, "pair": pair, "dir": d, "r_net": r, "net_eur": n,
            "gross_eur": n + 0.1, "cost_eur": 0.1, "exit_reason": reason, "stop_distance": stop, "entry_px": px}


class EpisodeTests(unittest.TestCase):
    def test_same_currency_same_direction_within_an_hour_is_one_episode(self):
        a = tr("2026-04-08 10:00", "EURUSD", +1)      # long EUR, short USD
        b = tr("2026-04-08 10:20", "GBPUSD", +1)      # long GBP, short USD  -> shares short-USD
        c = tr("2026-04-08 10:30", "USDJPY", -1)      # short USD, long JPY -> shares short-USD
        self.assertEqual(len(set(MT.assign_episodes([a, b, c]))), 1)

    def test_opposite_usd_direction_or_far_apart_in_time_is_independent(self):
        a = tr("2026-04-08 10:00", "EURUSD", +1)
        b = tr("2026-04-08 10:10", "GBPUSD", -1)      # long USD vs short USD -> no shared same-sign currency
        c = tr("2026-04-08 13:00", "EURUSD", +1)      # 3 h later
        self.assertEqual(len(set(MT.assign_episodes([a, b, c]))), 3)


class BootstrapTests(unittest.TestCase):
    def test_deterministic_and_resamples_clusters_not_trades(self):
        vals = [1.0, 1.0, 1.0, 1.0, -1.0, -1.0]
        clusters = [0, 0, 0, 0, 1, 2]
        a = MT.cluster_bootstrap_mean(vals, clusters, 2000, seed=1)
        b = MT.cluster_bootstrap_mean(vals, clusters, 2000, seed=1)
        self.assertEqual(a, b)
        self.assertLess(a[1], a[0]); self.assertGreater(a[2], a[0] - 1e-12)
        # with every trade independent the interval is tighter than when 4 of them are one correlated cluster
        ind = MT.cluster_bootstrap_mean(vals, list(range(6)), 2000, seed=1)
        self.assertLess(ind[2] - ind[1], a[2] - a[1])

    def test_empty(self):
        self.assertTrue(np.isnan(MT.cluster_bootstrap_mean([], [])[0]))


class PartitionAndStatsTests(unittest.TestCase):
    def test_partition_assignment_by_entry_time(self):
        self.assertEqual(MT.partition_of(ns("2026-05-01 00:00"), P), "DEVELOPMENT")
        self.assertEqual(MT.partition_of(ns("2026-08-01 00:00"), P), "VALIDATION")
        self.assertEqual(MT.partition_of(ns("2026-09-01 00:00"), P), "OUT_OF_SAMPLE")
        self.assertEqual(MT.partition_of(ns("2026-09-25 00:00"), P), "RESERVED_FORWARD")
        self.assertIsNone(MT.partition_of(ns("2026-03-01 00:00"), P))

    def test_profit_factor_drawdown_and_win_rate(self):
        self.assertAlmostEqual(MT.profit_factor([2, 1, -1, -0.5]), 2.0)
        self.assertTrue(np.isinf(MT.profit_factor([1, 2])))
        trades = [tr("2026-04-08 10:00", net=5), tr("2026-04-09 10:00", net=-10), tr("2026-04-10 10:00", net=-20), tr("2026-04-13 10:00", net=30)]
        mdd, frac = MT.max_drawdown(trades, 500.0)
        self.assertAlmostEqual(mdd, 30.0)
        self.assertAlmostEqual(frac, 30.0 / 505.0)
        s = MT.summarize(trades, P, (ns("2026-04-01 00:00"), ns("2026-04-30 00:00")), resamples=200)
        self.assertEqual(s["n_trades"], 4); self.assertAlmostEqual(s["win_rate"], 0.5)

    def test_exposure_uses_interval_union(self):
        t = [tr("2026-04-08 10:00", hold=60), tr("2026-04-08 10:30", hold=60)]      # overlap -> union 90 min
        e = MT.exposure_fraction(t, ns("2026-04-08 10:00"), ns("2026-04-08 13:00"))
        self.assertAlmostEqual(e["any_position_fraction"], 90 / 180)
        self.assertAlmostEqual(e["mean_concurrency"], 120 / 180)


def synth_summary(per_part, n_ep=40, ci=(0.01, 0.4), pf=1.5):
    out = {k: {"mean_net_r": v, "unique_episodes": n_ep // 3, "n_trades": n_ep // 3} for k, v in per_part.items()}
    pooled = (per_part["VALIDATION"] + per_part["OUT_OF_SAMPLE"]) / 2
    out["VAL_PLUS_OOS"] = {"mean_net_r": pooled, "mean_net_r_ci95": list(ci), "profit_factor_r": pf, "unique_episodes": n_ep * 2 // 3}
    out["ALL_EVALUATED"] = {"unique_episodes": n_ep}
    return out


class EvidenceTests(unittest.TestCase):
    pairs_ok = {p: {"mean_net_r": 0.2} for p in "ABCDE"}

    def test_insufficient_data_when_too_few_episodes(self):
        base = synth_summary({"DEVELOPMENT": .2, "VALIDATION": .2, "OUT_OF_SAMPLE": .2}, n_ep=12)
        self.assertEqual(EV.classify(base, None, self.pairs_ok, {}, 0.05)["classification"], "INSUFFICIENT_DATA")

    def test_negative_evidence(self):
        base = synth_summary({"DEVELOPMENT": -.2, "VALIDATION": -.3, "OUT_OF_SAMPLE": -.1}, ci=(-.5, -.05), pf=0.5)
        self.assertEqual(EV.classify(base, None, self.pairs_ok, {}, 0.2)["classification"], "NEGATIVE_EVIDENCE")

    def test_mixed_when_positive_but_ci_includes_zero(self):
        base = synth_summary({"DEVELOPMENT": .1, "VALIDATION": .1, "OUT_OF_SAMPLE": .05}, ci=(-.2, .3), pf=1.1)
        self.assertEqual(EV.classify(base, None, self.pairs_ok, {}, 0.05)["classification"], "MIXED_EVIDENCE")

    def test_promising_needs_every_criterion(self):
        base = synth_summary({"DEVELOPMENT": .2, "VALIDATION": .2, "OUT_OF_SAMPLE": .2})
        c = EV.classify(base, None, self.pairs_ok, {}, 0.05)
        self.assertEqual(c["classification"], "PROMISING_RESEARCH")
        few_pairs = {p: {"mean_net_r": 0.2 if i < 3 else -0.1} for i, p in enumerate("ABCDE")}
        self.assertEqual(EV.classify(base, None, few_pairs, {}, 0.05)["classification"], "MIXED_EVIDENCE")

    def test_shadow_forward_eligible_needs_adverse_robustness_and_volume(self):
        base = synth_summary({"DEVELOPMENT": .2, "VALIDATION": .2, "OUT_OF_SAMPLE": .2}, n_ep=300)
        base["OUT_OF_SAMPLE"]["unique_episodes"] = 60
        adv = {"VAL_PLUS_OOS": {"mean_net_r": 0.05}}
        reg = {"volatility_tercile": {"low": {"mean_net_r": .1}, "mid": {"mean_net_r": .2}, "high": {"mean_net_r": -.1}}}
        self.assertEqual(EV.classify(base, adv, self.pairs_ok, reg, 0.05)["classification"], "SHADOW_FORWARD_ELIGIBLE")
        adv_bad = {"VAL_PLUS_OOS": {"mean_net_r": -0.05}}
        self.assertEqual(EV.classify(base, adv_bad, self.pairs_ok, reg, 0.05)["classification"], "PROMISING_RESEARCH")


if __name__ == "__main__":
    unittest.main()
