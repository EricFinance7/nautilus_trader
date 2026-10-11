"""Tests for the data layer: .bi5 decoding (candles + ticks), tick QC, deterministic candle reconstruction and the
tick-vs-native comparison, using synthetic files written in the real Dukascopy binary layout."""
import datetime as dt
import lzma
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fast_research.data import decode as D, minute_dataset as MD, ticks_dataset as TD  # noqa: E402


def bi5_ticks(rows):
    """rows: (ms, ask_raw, bid_raw, ask_vol, bid_vol)"""
    return lzma.compress(b"".join(struct.pack(">iiiff", *r) for r in rows))


def bi5_minutes(rows):
    """rows: (sec, open, close, low, high, vol)  -- note the on-disk order open, CLOSE, low, high"""
    return lzma.compress(b"".join(struct.pack(">iiiiif", *r) for r in rows))


class DecodeTests(unittest.TestCase):
    def test_tick_layout_ask_before_bid(self):
        arr = D.decode_ticks(bi5_ticks([(250, 114313, 114311, 1.5, 2.5)]))
        self.assertEqual((arr["ms"][0], arr["ask"][0], arr["bid"][0]), (250, 114313, 114311))
        self.assertAlmostEqual(float(arr["ask_vol"][0]), 1.5); self.assertAlmostEqual(float(arr["bid_vol"][0]), 2.5)

    def test_minute_layout_close_before_low_high(self):
        arr = D.decode_minute(bi5_minutes([(60, 114300, 114310, 114290, 114320, 12.0)]))
        self.assertEqual((arr["sec"][0], arr["open"][0], arr["close"][0], arr["low"][0], arr["high"][0]), (60, 114300, 114310, 114290, 114320))

    def test_empty_file_is_empty_not_error(self):
        self.assertEqual(len(D.decode_ticks(b"")), 0)
        self.assertEqual(len(D.decode_minute(b"")), 0)

    def test_truncated_record_is_rejected(self):
        with self.assertRaises(ValueError):
            D.decode_ticks(lzma.compress(b"\x00" * 21))


def make_root(tick_rows_by_hour, minute_rows=None, pair="EURUSD", day="2026-04-08"):
    root = Path(tempfile.mkdtemp())
    for h, rows in tick_rows_by_hour.items():
        p = root / "raw" / "dukascopy" / pair / "tick" / f"{day}T{h:02d}.bi5"
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(bi5_ticks(rows))
    return root


class TickDatasetTests(unittest.TestCase):
    DAY = dt.date(2026, 4, 8)

    def test_load_decodes_exact_utc_times_and_prices(self):
        root = make_root({10: [(0, 114313, 114311, 1, 1), (30_000, 114314, 114312, 1, 1)]})
        df, present, empty = TD.load_day(root, "EURUSD", self.DAY)
        self.assertEqual(present, [10])
        self.assertEqual(str(df["ts"].iloc[0]), "2026-04-08 10:00:00+00:00")
        self.assertEqual(str(df["ts"].iloc[1]), "2026-04-08 10:00:30+00:00")
        self.assertEqual((df["bid"].iloc[0], df["ask"].iloc[0]), (1.14311, 1.14313))

    def test_qc_counts_duplicates_crossed_locked_and_ordering(self):
        rows = [(0, 114313, 114311, 1, 1), (0, 114313, 114311, 1, 1),        # exact duplicate
                (1000, 114310, 114312, 1, 1),                                  # crossed: bid 1.14312 > ask 1.14310
                (2000, 114312, 114312, 1, 1)]                                  # locked
        root = make_root({10: rows})
        df, _, _ = TD.load_day(root, "EURUSD", self.DAY)
        q = TD.qc_ticks(df, "EURUSD")
        self.assertEqual((q["rows"], q["exact_duplicate_ticks"], q["crossed_bid_gt_ask"], q["locked_bid_eq_ask"]), (4, 1, 1, 1))
        self.assertTrue(q["monotonic_non_decreasing"])
        self.assertEqual(q["tz"], "UTC")

    def test_candles_from_ticks_are_deterministic_half_open_bid_ask(self):
        rows = [(0, 100010, 100000, 1, 1), (20_000, 100030, 100020, 1, 1), (59_999, 100005, 99995, 1, 1), (60_000, 100050, 100040, 1, 1)]
        root = make_root({10: rows})
        df, _, _ = TD.load_day(root, "EURUSD", self.DAY)
        c = TD.candles_from_ticks(df)
        m0 = c.loc[pd.Timestamp("2026-04-08 10:00", tz="UTC")]
        self.assertEqual((m0["bid_open"], m0["bid_high"], m0["bid_low"], m0["bid_close"], m0["ticks"]), (1.0, 1.0002, 0.99995, 0.99995, 3))
        m1 = c.loc[pd.Timestamp("2026-04-08 10:01", tz="UTC")]            # the 60_000 ms tick belongs to the NEXT minute
        self.assertEqual((m1["bid_open"], m1["ticks"]), (1.0004, 1))
        pd.testing.assert_frame_equal(c, TD.candles_from_ticks(df))      # same input, same output

    def test_comparison_with_native_candles_flags_a_difference(self):
        rows = [(0, 100010, 100000, 1, 1), (59_000, 100020, 100010, 1, 1)]
        root = make_root({10: rows})
        df, _, _ = TD.load_day(root, "EURUSD", self.DAY)
        tc = TD.candles_from_ticks(df)
        row = tc.iloc[0]
        native = pd.DataFrame([{"ts": tc.index[0], "valid": True, **{k: row[k] for k in tc.columns if k != "ticks"}}])
        self.assertEqual(TD.compare_to_native(tc, native)["max_abs_diff"], 0.0)
        native.loc[0, "bid_high"] += 0.0003
        r = TD.compare_to_native(tc, native)
        self.assertEqual(r["bid_high_mismatch_minutes"], 1); self.assertGreater(r["max_abs_diff"], 2e-4)

    def test_tick_quote_arrays_drop_crossed_ticks_and_apply_the_scenario(self):
        root = make_root({10: [(0, 100010, 100000, 1, 1), (1000, 100000, 100020, 1, 1)]})   # second tick is crossed
        df, _, _ = TD.load_day(root, "EURUSD", self.DAY)
        ts, b, a = TD.tick_quote_arrays(df, 1e-4, 5, spread_multiplier=1.0, slippage_pips=0.5)
        self.assertEqual(len(ts), 1)
        self.assertAlmostEqual(float(b[0]), 1.0 - 0.00005, places=9); self.assertAlmostEqual(float(a[0]), 1.0001 + 0.00005, places=9)


class CandleNormalizationTests(unittest.TestCase):
    def test_zero_volume_minutes_are_kept_but_marked_invalid(self):
        root = Path(tempfile.mkdtemp())
        day = dt.date(2026, 4, 8)
        for side in ("BID", "ASK"):
            p = root / "raw" / "dukascopy" / "EURUSD" / "minute" / side / f"{day.isoformat()}.bi5"
            p.parent.mkdir(parents=True, exist_ok=True)
            rows = [(60 * m, 114300, 114300, 114300, 114300, 0.0 if m == 1 else 5.0) for m in range(1440)]
            p.write_bytes(bi5_minutes(rows))
        df, missing = MD.build_pair(root, "EURUSD", day, day)
        self.assertEqual((len(df), missing), (1440, []))
        self.assertFalse(bool(df.loc[1, "valid"])); self.assertTrue(bool(df.loc[0, "valid"]))
        self.assertEqual(df["ts"].dt.tz.__str__(), "UTC")

    def test_saturdays_are_not_counted_as_missing(self):
        root = Path(tempfile.mkdtemp())
        df, missing = MD.build_pair(root, "EURUSD", dt.date(2026, 4, 4), dt.date(2026, 4, 4))   # a Saturday
        self.assertEqual((len(df), missing), (0, []))


if __name__ == "__main__":
    unittest.main()
