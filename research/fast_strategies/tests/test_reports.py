"""Tests for the fidelity comparison, data-report generator and analyzer table rendering (synthetic inputs)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fast_research import run_fidelity as RF  # noqa: E402
from fast_research.data import report as DR  # noqa: E402


def t(pair, d, sig, entry, exit_, r, reason="TIME_EXIT", net=1.0):
    return {"pair": pair, "dir": d, "signal_close_ns": sig, "entry_px": entry, "exit_px": exit_, "r_net": r, "exit_reason": reason, "net_eur": net}


class FidelityTests(unittest.TestCase):
    def test_matches_by_pair_direction_and_signal_time_and_measures_pip_differences(self):
        candle = [t("EURUSD", 1, 100, 1.10000, 1.10100, 1.0), t("USDJPY", -1, 200, 150.000, 149.900, 0.5), t("GBPUSD", 1, 300, 1.2, 1.2, 0.0)]
        tick = [t("EURUSD", 1, 100, 1.10002, 1.10090, 0.8, reason="STOP"), t("USDJPY", -1, 200, 150.010, 149.900, 0.5),
                t("AUDUSD", 1, 400, 0.7, 0.7, 0.0)]
        r = RF.compare(candle, tick)
        self.assertEqual((r["n_candle"], r["n_tick"], r["n_matched"]), (3, 3, 2))
        self.assertAlmostEqual(r["entry_abs_diff_pips_mean"], (0.2 + 1.0) / 2)       # 0.2 pip EURUSD, 1.0 pip USDJPY (pip=0.01)
        self.assertAlmostEqual(r["same_exit_reason_fraction"], 0.5)

    def test_no_matches_is_reported_not_an_error(self):
        r = RF.compare([t("EURUSD", 1, 1, 1, 1, 0)], [t("EURUSD", 1, 2, 1, 1, 0)])
        self.assertEqual(r["n_matched"], 0)


class DataReportTests(unittest.TestCase):
    def test_renders_from_checkpoint_and_qc_without_hand_typed_numbers(self):
        root = Path(tempfile.mkdtemp())
        cp = root / "checkpoints" / "dukascopy"; cp.mkdir(parents=True)
        recs = [{"key": "candles|EURUSD|BID|2026-04-01", "status": "OK", "bytes": 100},
                {"key": "candles|EURUSD|ASK|2026-04-01", "status": "OK", "bytes": 120},
                {"key": "ticks|EURUSD|2026-04-01T09", "status": "FAILED", "bytes": 0}]
        (cp / "fast6m_acquisition.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
        qc = {"window": ["2026-04-01", "2026-04-02"], "pairs": {"EURUSD": {
            "rows": 1440, "days_missing": [], "crossed_quotes": {"open": 0, "high": 0, "low": 0, "close": 0},
            "ohlc_invariant_violations": {"bid": 0, "ask": 0}, "deterministic_rebuild_hash_matches": True,
            "session": {"valid_minutes_in_session": 1400, "zero_volume_minutes_in_session": 40, "valid_minutes_outside_session": 0},
            "in_session_gaps": {"longest_minutes": 3},
            "spread_pips": {"open_median": 0.3, "open_mean": 0.5, "open_p95": 0.9, "close_median": 0.4, "close_mean": 0.5, "close_p95": 1.0, "close_max": 19.6, "negative_close": 0}}}}
        text = DR.render(root, qc, None)
        self.assertIn("{\"OK\": 2}", text); self.assertIn("{\"FAILED\": 1}", text)
        self.assertIn("1,440", text); self.assertIn("0.30 / 0.50 / 0.90", text)
        self.assertIn("bot challenge", text)


if __name__ == "__main__":
    unittest.main()
