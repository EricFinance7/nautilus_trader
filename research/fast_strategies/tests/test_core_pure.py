"""Deterministic tests for the engine-independent core: bar aggregation, indicators, look-ahead safety, sessions/DST,
sizing, cost gate, quote generation, ledger and frozen specs. No network, no Nautilus runtime required."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fast_research import specs as S  # noqa: E402
from fast_research.harness import bars as B, ledger as L, quotes as Q, session as SE, sizing as SZ  # noqa: E402

NS = 10**9
MIN = 60 * NS


def ns(s: str) -> int:
    return int(pd.Timestamp(s, tz="UTC").value)


def feed_series(state, t0_ns, closes, step=1):
    """Feed 1-minute bars whose open==previous close; returns list of completed dicts per minute."""
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        h, l = max(prev, c) + 0.0001, min(prev, c) - 0.0001
        out.append(state.feed(t0_ns + i * MIN, prev, h, l, c))
        prev = c
    return out


class AggregationTests(unittest.TestCase):
    def test_bucket_completes_only_on_final_minute_and_ohlc_is_correct(self):
        agg = B.TFAggregator(5)
        t0 = ns("2026-04-08 10:00")
        done = [agg.on_minute(t0 + i * MIN, 1.0 + i, 2.0 + i, 0.5 + i, 1.5 + i) for i in range(5)]
        self.assertEqual([d is None for d in done], [True, True, True, True, False])
        bar = done[-1]
        self.assertEqual((bar.t_open, bar.t_close, bar.n_minutes), (t0, t0 + 5 * MIN, 5))
        self.assertEqual((bar.o, bar.h, bar.l, bar.c), (1.0, 6.0, 0.5, 5.5))

    def test_utc_alignment(self):
        agg = B.TFAggregator(15)
        t0 = ns("2026-04-08 10:07")   # mid-bucket start: first bucket is [10:00,10:15) and only has minutes 07..14
        got = [agg.on_minute(t0 + i * MIN, 1, 1, 1, 1) for i in range(8)]
        self.assertIsNotNone(got[-1])
        self.assertEqual(got[-1].t_open, ns("2026-04-08 10:00"))
        self.assertEqual(got[-1].n_minutes, 8)

    def test_bucket_with_missing_final_minute_is_dropped_never_fabricated(self):
        agg = B.TFAggregator(5)
        t0 = ns("2026-04-08 10:00")
        for i in (0, 1, 2, 3):                        # minute 4 (the final one) never arrives
            self.assertIsNone(agg.on_minute(t0 + i * MIN, 1, 1, 1, 1))
        self.assertIsNone(agg.on_minute(t0 + 5 * MIN, 2, 2, 2, 2))   # next bucket starts: previous incomplete one discarded
        self.assertEqual(len(agg.bars), 0)

    def test_gap_over_60_minutes_resets_all_state_but_small_gaps_do_not(self):
        st = B.PairState((1, 5), gap_reset_minutes=60)
        t0 = ns("2026-04-08 10:00")
        for i in range(10):
            st.feed(t0 + i * MIN, 1, 1, 1, 1)
        self.assertGreater(len(st.bars(5)), 0)
        st.feed(t0 + 70 * MIN, 1, 1, 1, 1)             # 61-minute gap after minute 9
        self.assertEqual(st.resets, 1)
        self.assertEqual(len(st.bars(5)), 0)
        st2 = B.PairState((1,), 60)
        st2.feed(t0, 1, 1, 1, 1); st2.feed(t0 + 60 * MIN, 1, 1, 1, 1)   # exactly 60 minutes: allowed
        self.assertEqual(st2.resets, 0)


class IndicatorTests(unittest.TestCase):
    def _bars(self, closes, rng=0.2):
        out, prev = [], closes[0]
        for i, c in enumerate(closes):
            out.append(B.Bar(i * 900 * NS, (i + 1) * 900 * NS, prev, max(prev, c) + rng, min(prev, c) - rng, c, 15))
            prev = c
        return out

    def test_atr_known_value_and_warmup(self):
        bars = self._bars([1, 2, 3, 4, 5, 6], rng=0.0)       # TR of each bar after the first = 1 (|H-Cprev|)
        self.assertIsNone(B.atr(bars, 6))                     # needs n+1 bars
        self.assertAlmostEqual(B.atr(bars, 5), 1.0)

    def test_atr_end_shift_is_one_bar_earlier(self):
        bars = self._bars([1, 1, 1, 1, 1, 9], rng=0.0)
        self.assertAlmostEqual(B.atr(bars, 4, end=1), 0.0)    # excludes the final jump
        self.assertGreater(B.atr(bars, 4, end=0), 1.0)

    def test_no_lookahead_indicators_at_t_ignore_later_bars(self):
        a = self._bars([1.0, 1.1, 1.05, 1.2, 1.15, 1.3, 1.25, 1.4, 1.35, 1.5])
        b = list(a[:7]) + self._bars([50, 60, 70])[0:3]       # same history up to index 6, different future
        for n in (3, 5):
            self.assertAlmostEqual(B.atr(a[:7], n), B.atr(b[:7], n))
        self.assertAlmostEqual(B.sma_close(a[:7], 5), B.sma_close(b[:7], 5))
        self.assertAlmostEqual(B.std_close(a[:7], 5), B.std_close(b[:7], 5))


class SessionTests(unittest.TestCase):
    def test_london_and_new_york_open_shift_with_dst(self):
        summer, winter = dt.date(2026, 7, 1), dt.date(2026, 1, 12)
        o = lambda d, tz: SE.session_open_utc_ns(d, tz, dt.time(8, 0))
        self.assertEqual(o(summer, "Europe/London"), ns("2026-07-01 07:00"))
        self.assertEqual(o(winter, "Europe/London"), ns("2026-01-12 08:00"))
        self.assertEqual(o(summer, "America/New_York"), ns("2026-07-01 12:00"))
        self.assertEqual(o(winter, "America/New_York"), ns("2026-01-12 13:00"))

    def test_uk_and_us_dst_transitions_do_not_coincide(self):
        # 2026-03-20: US already on DST (since Mar 8), UK not yet (Mar 29)
        d = dt.date(2026, 3, 20)
        self.assertEqual(SE.session_open_utc_ns(d, "America/New_York", dt.time(8, 0)), ns("2026-03-20 12:00"))
        self.assertEqual(SE.session_open_utc_ns(d, "Europe/London", dt.time(8, 0)), ns("2026-03-20 08:00"))

    def test_entry_block_and_force_flat_follow_new_york_clock_in_both_seasons(self):
        # summer: 16:30 NY = 20:30 UTC ; winter: 16:30 NY = 21:30 UTC
        self.assertFalse(SE.entry_blocked(ns("2026-07-01 20:29")))
        self.assertTrue(SE.entry_blocked(ns("2026-07-01 20:30")))
        self.assertFalse(SE.entry_blocked(ns("2026-07-01 23:00")))   # 19:00 NY: window over
        self.assertFalse(SE.entry_blocked(ns("2026-01-12 21:29")))
        self.assertTrue(SE.entry_blocked(ns("2026-01-12 21:30")))
        self.assertFalse(SE.force_flat_due(ns("2026-07-01 20:54")))
        self.assertTrue(SE.force_flat_due(ns("2026-07-01 20:55")))
        self.assertTrue(SE.force_flat_due(ns("2026-01-12 21:55")))

    def test_classify_session_labels(self):
        self.assertEqual(SE.classify_session(ns("2026-07-01 13:00")), "LONDON_NEW_YORK_OVERLAP")  # 14:00 BST / 09:00 EDT
        self.assertEqual(SE.classify_session(ns("2026-07-01 21:30")), "ROLLOVER_LOW_LIQUIDITY")   # 17:30 EDT


class SizingTests(unittest.TestCase):
    def test_floor_never_rounds_up(self):
        self.assertEqual(SZ.floor_to_step(2999.9), 2000)
        self.assertEqual(SZ.floor_to_step(3000), 3000)
        self.assertEqual(SZ.floor_to_step(999.99), 0)

    def test_below_min_units_is_rejected_not_rounded_up(self):
        units, eff, why = SZ.position_size(2.5, 0.0030, 0.0001, 0.00003, 0.86)   # ~950 raw units
        self.assertEqual((units, why), (0, "BELOW_MIN_UNITS"))

    def test_sizing_uses_effective_stop_including_spread_and_slippage(self):
        units, eff, why = SZ.position_size(2.5, 0.0010, 0.0002, 0.0001, 0.86)
        self.assertAlmostEqual(eff, 0.0013)
        self.assertEqual(units, SZ.floor_to_step(2.5 / (0.0013 * 0.86)))
        self.assertIsNone(why)

    def test_actual_risk_never_exceeds_budget(self):
        for stop in (0.0007, 0.0013, 0.0021, 0.0044):
            u, eff, why = SZ.position_size(2.5, stop, 0.0001, 0.00003, 0.86)
            if u:
                self.assertLessEqual(u * eff * 0.86, 2.5 + 1e-9)

    def test_cost_gate_boundary_is_inclusive_20_percent(self):
        self.assertTrue(SZ.cost_gate(0.50, 2.5)[0])
        self.assertFalse(SZ.cost_gate(0.5001, 2.5)[0])
        self.assertFalse(SZ.cost_gate(0.1, 0)[0])

    def test_expected_cost_components(self):
        c = SZ.expected_round_trip_cost_eur(10000, 1.1, 0.0001, 0.00001, 0.000026, 1.0)
        self.assertAlmostEqual(c, 10000 * (0.0001 + 2 * 0.00001) + 2 * 0.000026 * 10000 * 1.1)


def _frame(rows):
    cols = ["ts", "bid_open", "bid_high", "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close",
            "bid_volume", "ask_volume", "valid"]
    return pd.DataFrame(rows, columns=cols)


class QuoteGenerationTests(unittest.TestCase):
    def _row(self, t, bo, bh, bl, bc, spread=0.0001, valid=True):
        return [pd.Timestamp(t, tz="UTC"), bo, bh, bl, bc, bo + spread, bh + spread, bl + spread, bc + spread,
                10.0 if valid else 0.0, 10.0 if valid else 0.0, valid]

    def test_four_quotes_per_valid_minute_at_fixed_offsets(self):
        df = _frame([self._row("2026-04-08 10:00", 1.1000, 1.1010, 1.0990, 1.1005)])
        ts, b, a = Q.quote_arrays(df, 1e-4, 5)
        base = ns("2026-04-08 10:00")
        self.assertEqual(list(ts - base), [1 * NS, 20 * NS, 40 * NS, 59 * NS])
        self.assertEqual((b[0], a[0]), (1.1000, 1.1001))      # open quote = the candle's open
        self.assertEqual((b[3], a[3]), (1.1005, 1.1006))      # close quote = the candle's close

    def test_extreme_nearer_the_open_is_visited_first(self):
        up = _frame([self._row("2026-04-08 10:00", 1.1000, 1.1002, 1.0980, 1.0990)])   # open near the high
        _, b, _ = Q.quote_arrays(up, 1e-4, 5)
        self.assertEqual((b[1], b[2]), (1.1002, 1.0980))
        dn = _frame([self._row("2026-04-08 10:00", 1.1000, 1.1020, 1.0998, 1.1010)])   # open near the low
        _, b, _ = Q.quote_arrays(dn, 1e-4, 5)
        self.assertEqual((b[1], b[2]), (1.0998, 1.1020))

    def test_zero_volume_minutes_emit_nothing(self):
        df = _frame([self._row("2026-04-08 10:00", 1.1, 1.1, 1.1, 1.1, valid=False),
                     self._row("2026-04-08 10:01", 1.1, 1.1, 1.1, 1.1, valid=True)])
        ts, _, _ = Q.quote_arrays(df, 1e-4, 5)
        self.assertEqual(len(ts), 4)
        self.assertTrue((ts >= ns("2026-04-08 10:01")).all())

    def test_never_crossed_and_scenarios_widen_cost(self):
        df = _frame([self._row("2026-04-08 10:00", 1.1000, 1.1010, 1.0990, 1.1005, spread=0.0002)])
        _, b0, a0 = Q.quote_arrays(df, 1e-4, 5)
        _, b1, a1 = Q.quote_arrays(df, 1e-4, 5, spread_multiplier=1.5, slippage_pips=0.3)
        self.assertTrue((a0 >= b0).all() and (a1 >= b1).all())
        self.assertTrue(np.all(a1 - b1 > a0 - b0))
        # 1.5x spread -> +0.0001 total; +0.3 pip slip each side -> +0.00006 total
        self.assertAlmostEqual(float((a1 - b1)[0] - (a0 - b0)[0]), 0.0001 + 0.00006, places=9)


class LedgerTests(unittest.TestCase):
    def test_daily_loss_limit_blocks_until_utc_midnight(self):
        led = L.VirtualLedger(500.0)
        t = ns("2026-04-08 10:00")
        self.assertTrue(led.entries_allowed(t)[0])
        led.book_trade(t, {"net_eur": -10.5})                  # > 2% of 500
        self.assertEqual(led.entries_allowed(t + MIN), (False, "DAILY_LOSS_HALT"))
        self.assertTrue(led.entries_allowed(ns("2026-04-09 00:00"))[0])

    def test_drawdown_pause_is_permanent_and_research_mode_disables_it(self):
        led = L.VirtualLedger(500.0, drawdown_fraction=0.10)
        led.book_trade(ns("2026-04-08 10:00"), {"net_eur": -9.0})
        led.book_trade(ns("2026-04-09 10:00"), {"net_eur": -9.0})
        led.book_trade(ns("2026-04-10 10:00"), {"net_eur": -9.0})
        led.book_trade(ns("2026-04-13 10:00"), {"net_eur": -25.0})
        self.assertTrue(led.paused)
        self.assertEqual(led.entries_allowed(ns("2026-05-20 10:00")), (False, "DRAWDOWN_PAUSED"))
        r = L.VirtualLedger(500.0, drawdown_fraction=1e9)
        r.book_trade(ns("2026-04-08 10:00"), {"net_eur": -200.0})
        self.assertFalse(r.paused)

    def test_rebuild_from_journal_reproduces_state_exactly(self):
        import tempfile
        p = Path(tempfile.mkdtemp()) / "j.jsonl"
        led = L.VirtualLedger(500.0, journal_path=p)
        for i, pnl in enumerate((3.2, -1.1, 4.4, -9.9)):
            led.log("ENTRY_SUBMITTED", ns("2026-04-08 10:00") + i)
            led.book_trade(ns("2026-04-08 10:00") + i * NS, {"net_eur": pnl, "pair": "EURUSD"})
        led.close()
        re = L.VirtualLedger.rebuild(p)
        self.assertAlmostEqual(re.equity, led.equity)
        self.assertAlmostEqual(re.peak, led.peak)
        self.assertEqual(len(re.trades), 4)


class SpecTests(unittest.TestCase):
    def test_partition_boundaries_follow_the_55_20_15_10_arithmetic(self):
        p = S.HARNESS["partitions"]
        s, e = pd.Timestamp("2026-04-01", tz="UTC"), pd.Timestamp("2026-10-10", tz="UTC")
        tot = e - s
        for frac, key in ((0.55, "DEVELOPMENT"), (0.75, "VALIDATION"), (0.90, "OUT_OF_SAMPLE")):
            self.assertEqual(pd.Timestamp(p[key][1]), s + tot * frac)
        self.assertEqual(p["DEVELOPMENT"][1], p["VALIDATION"][0])
        self.assertEqual(p["OUT_OF_SAMPLE"][1], p["RESERVED_FORWARD"][0])

    def test_hashes_are_deterministic_and_change_with_content(self):
        a = S.config_hash("F01")
        self.assertEqual(a, S.config_hash("F01"))
        self.assertNotEqual(a, S.config_hash("F02"))
        mutated = json.loads(json.dumps(S.HARNESS)); mutated["capital_and_risk"]["risk_per_trade_fraction"] = 0.01
        self.assertNotEqual(S.sha256(S.HARNESS), S.sha256(mutated))

    def test_every_family_quotes_the_registry_and_lists_what_was_missing(self):
        self.assertEqual(sorted(S.FAMILIES), ["F01", "F02", "F03", "F04", "F05", "F06", "F07"])
        for fid, f in S.FAMILIES.items():
            self.assertEqual(f["registry_version"], "v0_concept")
            self.assertIn("CONCEPT ONLY", f["source_registry"]["original_signal_definition"])
            self.assertIn("stop-loss methodology", f["missing_in_source"])
            self.assertTrue(f["gap_fill_decisions"])

    def test_capital_model_matches_the_task(self):
        c = S.HARNESS["capital_and_risk"]
        self.assertEqual((c["initial_virtual_equity_eur"], c["risk_per_trade_fraction"], c["max_simultaneous_positions"]), (500.0, 0.005, 3))
        self.assertEqual((c["max_combined_open_risk_fraction"], c["daily_realized_loss_limit_fraction"], c["drawdown_pause_fraction"]), (0.015, 0.02, 0.10))
        self.assertFalse(c["martingale"] or c["averaging_down"] or c["pyramiding"])


if __name__ == "__main__":
    unittest.main()
