"""Restart recovery = same frozen logic, same trades. An interrupted run that is restarted (indicator state warmed by
replaying history WITHOUT trading, ledger rebuilt from the append-only journal) must produce exactly the trades an
uninterrupted run produces after the restart point.

Integration test on real normalized candles: set TIE_MINUTE_DIR to a directory of <PAIR>.parquet minute files covering
2026-04-06..2026-04-17 (skipped otherwise)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MINUTE_DIR = os.environ.get("TIE_MINUTE_DIR")


@unittest.skipUnless(MINUTE_DIR and Path(MINUTE_DIR).exists(), "TIE_MINUTE_DIR not set")
class RestartTests(unittest.TestCase):
    START, SPLIT, END = "2026-04-06T00:00:00Z", "2026-04-13T00:00:00Z", "2026-04-17T00:00:00Z"   # SPLIT is a Monday 00:00 UTC: flat

    def _cmp(self, family, mode):
        from fast_research.harness import runner
        tmp = Path(tempfile.mkdtemp())
        a = runner.run_arm(family, "base", Path(MINUTE_DIR), self.START, self.END, mode=mode, journal_path=str(tmp / "A.jsonl"), tag=1)
        b = runner.run_arm(family, "base", Path(MINUTE_DIR), self.START, self.SPLIT, mode=mode, journal_path=str(tmp / "B.jsonl"), tag=2)
        c = runner.run_arm(family, "base", Path(MINUTE_DIR), self.START, self.END, mode=mode, journal_path=str(tmp / "C.jsonl"), tag=3,
                           trade_from_ns=int(pd.Timestamp(self.SPLIT).value), restore_journal=str(tmp / "B.jsonl"))
        split = int(pd.Timestamp(self.SPLIT).value)
        key = lambda t: (t["pair"], t["dir"], t["units"], t["entry_ts_ns"], t["exit_ts_ns"], round(t["entry_px"], 6), round(t["exit_px"], 6), t["exit_reason"])
        ta = sorted(key(t) for t in a["trades"] if t["entry_ts_ns"] >= split)
        tc = sorted(key(t) for t in c["trades"] if t["entry_ts_ns"] >= split)
        pre_a = sorted(key(t) for t in a["trades"] if t["entry_ts_ns"] < split)
        pre_c = sorted(key(t) for t in c["trades"] if t["entry_ts_ns"] < split)
        return a, b, c, ta, tc, pre_a, pre_c

    def test_governed_restart_reproduces_the_uninterrupted_run(self):
        for fam in ("F01", "F05"):
            a, b, c, ta, tc, pre_a, pre_c = self._cmp(fam, "governed")
            self.assertGreater(len(ta), 0, fam)
            self.assertEqual(pre_a, pre_c, fam)          # restored history is exactly the pre-split trades
            self.assertEqual(ta, tc, fam)                # and the post-restart trades are identical, including sizing from the restored equity
            self.assertAlmostEqual(a["ledger_equity_eur"], c["ledger_equity_eur"], places=6)

    def test_journal_is_append_only_and_continuous_after_restart(self):
        from fast_research.harness import runner
        tmp = Path(tempfile.mkdtemp())
        runner.run_arm("F01", "base", Path(MINUTE_DIR), self.START, self.SPLIT, mode="governed", journal_path=str(tmp / "J.jsonl"), tag=1)
        n_before = len((tmp / "J.jsonl").read_text().splitlines())
        runner.run_arm("F01", "base", Path(MINUTE_DIR), self.START, self.END, mode="governed", journal_path=str(tmp / "J.jsonl"), tag=2,
                       trade_from_ns=int(pd.Timestamp(self.SPLIT).value), restore_journal=str(tmp / "J.jsonl"))
        lines = (tmp / "J.jsonl").read_text().splitlines()
        self.assertGreater(len(lines), n_before)
        import json
        seqs = [json.loads(l)["seq"] for l in lines]
        self.assertEqual(seqs, sorted(seqs))               # monotonically increasing; nothing rewritten


if __name__ == "__main__":
    unittest.main()
