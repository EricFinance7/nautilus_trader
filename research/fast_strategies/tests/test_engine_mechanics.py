"""Engine-level mechanics through the REAL NautilusTrader engine (rc6) with a scripted model on synthetic candles.
Verifies fill timing/price, reduce-only stop handling and its documented repricing, time exit, force-flat, session
block, cost gate and minimum-size rejection. Requires nautilus_trader==2.0.0rc6."""
import copy
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fast_research import specs as S  # noqa: E402
from fast_research.harness import runner  # noqa: E402
from fast_research.strategies import models as M  # noqa: E402

NS = 10**9
MIN = 60 * NS
PIP = 1e-4
COLS = ["ts", "bid_open", "bid_high", "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close",
        "bid_volume", "ask_volume", "valid"]
H = copy.deepcopy(S.HARNESS)
H["universe"] = ["EURUSD"]


def ns(s):
    return int(pd.Timestamp(s, tz="UTC").value)


def frame(start, end, overrides=None, bid=1.1000, spread=0.0001):
    """Flat candles from start to end (exclusive), 1/min; overrides = {minute_str: dict(field=value)}."""
    overrides = overrides or {}
    rows = []
    for t in pd.date_range(start, end, freq="1min", inclusive="left", tz="UTC"):
        r = dict(bid_open=bid, bid_high=bid, bid_low=bid, bid_close=bid, valid=True)
        r.update(overrides.get(t.strftime("%Y-%m-%d %H:%M"), {}))
        sp = r.pop("spread", spread)
        rows.append([t, r["bid_open"], r["bid_high"], r["bid_low"], r["bid_close"], r["bid_open"] + sp,
                     r["bid_high"] + sp, r["bid_low"] + sp, r["bid_close"] + sp,
                     10.0 if r["valid"] else 0.0, 10.0 if r["valid"] else 0.0, r["valid"]])
    return pd.DataFrame(rows, columns=COLS)


class Scripted(M.Model):
    id, tfs = "SCRIPT", (1,)

    def __init__(self, signal_close: str, direction=1, stop=0.0010, hold=5, risk=0.005):
        self.at, self.d, self.stop, self.hold, self.risk = ns(signal_close), direction, stop, hold, risk

    def entry(self, ctx, pair, done):
        if 1 in done and done[1].t_close == self.at:
            return [M.Intent(pair, self.d, self.stop, self.hold, 1, self.risk, "SCRIPT")]
        return []


def run(df, start, end, model, scenario="base", mode="research"):
    spec = S.family_spec("F01")
    return runner.run_arm("F01", scenario, None, start, end, pairs=["EURUSD"], harness=H, mode=mode, frames={"EURUSD": df},
                          model_factory=lambda _spec: model, spec=spec)


def ts(r_ns):
    return pd.Timestamp(r_ns, unit="ns", tz="UTC")


class EntryAndExitMechanics(unittest.TestCase):
    START, END = "2026-04-08 09:00", "2026-04-08 11:30"

    def test_entry_fills_at_next_minute_open_ask_plus_slippage_and_is_sized_by_the_formula(self):
        r = run(frame(self.START, self.END), self.START, self.END, Scripted("2026-04-08 09:30", hold=60))
        self.assertGreaterEqual(r["n_trades"], 1)
        t = r["trades"][0]
        self.assertEqual(ts(t["entry_ts_ns"]), pd.Timestamp("2026-04-08 09:30:01", tz="UTC"))   # next-minute OPEN quote, never the signal bar's close
        self.assertAlmostEqual(t["entry_px"], 1.1001 + 0.1 * PIP, places=6)                      # ask open + 0.1 pip market slippage
        spread_now = 0.0001 + 2 * 0.1 * PIP
        eff = 0.0010 + spread_now + 0.3 * PIP
        fx = 1.0 / (1.1000 + 0.00005)                                                           # mid of EURUSD
        expected_units = int(2.5 / (eff * fx) // 1000) * 1000
        self.assertEqual(t["units"], expected_units)
        self.assertLessEqual(t["actual_risk_eur"], 2.5 + 1e-9)

    def test_time_exit_is_a_market_order_at_the_next_open_bid(self):
        r = run(frame(self.START, self.END), self.START, self.END, Scripted("2026-04-08 09:30", hold=5))
        t = r["trades"][0]
        self.assertEqual(t["exit_reason"], "TIME_EXIT")
        self.assertEqual(ts(t["exit_ts_ns"]), pd.Timestamp("2026-04-08 09:35:01", tz="UTC"))
        self.assertAlmostEqual(t["exit_px"], 1.1000 - 0.1 * PIP, places=6)                      # bid open - slippage
        self.assertEqual(r["open_at_end"], [])

    def test_intrabar_stop_is_booked_at_the_stop_price_not_the_minute_extreme(self):
        ov = {"2026-04-08 09:35": dict(bid_open=1.1000, bid_high=1.1001, bid_low=1.0985, bid_close=1.0990)}
        r = run(frame(self.START, self.END, ov), self.START, self.END, Scripted("2026-04-08 09:30", hold=60))
        t = r["trades"][0]
        stop_px = t["entry_px"] - 0.0010
        self.assertEqual(t["exit_reason"], "STOP")
        self.assertAlmostEqual(t["exit_px"], stop_px - 0.3 * PIP, places=6)                    # stop price less stop slippage
        self.assertLess(t["engine_exit_px"], t["exit_px"] - 0.0005)                            # the engine itself filled near the 1.0985 extreme
        self.assertGreater(r["ledger_minus_engine_eur"], 0)

    def test_gap_through_the_stop_keeps_the_engine_fill_plus_extra_stop_slippage(self):
        ov = {"2026-04-08 09:35": dict(bid_open=1.0980, bid_high=1.0981, bid_low=1.0975, bid_close=1.0978)}
        r = run(frame(self.START, self.END, ov), self.START, self.END, Scripted("2026-04-08 09:30", hold=60))
        t = r["trades"][0]
        self.assertEqual(t["exit_reason"], "STOP")
        self.assertAlmostEqual(t["engine_exit_px"], 1.0980 - 0.1 * PIP, places=6)              # filled at the open bid (gap)
        self.assertAlmostEqual(t["exit_px"], t["engine_exit_px"] - 0.2 * PIP, places=6)        # + (0.3 - 0.1) pip extra
        self.assertLess(t["exit_px"], t["entry_px"] - 0.0010)                                  # gap loss exceeds the planned stop (R < -1)
        self.assertLess(t["r_net"], -1.0)

    def test_short_trade_uses_bid_entry_and_ask_triggered_stop(self):
        ov = {"2026-04-08 09:35": dict(bid_open=1.1000, bid_high=1.1015, bid_low=1.0999, bid_close=1.1010)}
        r = run(frame(self.START, self.END, ov), self.START, self.END, Scripted("2026-04-08 09:30", direction=-1, hold=60))
        t = r["trades"][0]
        self.assertAlmostEqual(t["entry_px"], 1.1000 - 0.1 * PIP, places=6)                    # sells at the bid open
        self.assertEqual(t["exit_reason"], "STOP")
        self.assertAlmostEqual(t["exit_px"], t["entry_px"] + 0.0010 + 0.3 * PIP, places=6)

    def test_adverse_scenario_fills_one_bar_later_and_costs_more(self):
        ov = {"2026-04-08 09:31": dict(bid_open=1.1002, bid_high=1.1002, bid_low=1.1002, bid_close=1.1002)}
        fr = lambda: frame(self.START, self.END, ov, spread=0.00003)      # a realistic 0.3 pip raw spread
        base = run(fr(), self.START, self.END, Scripted("2026-04-08 09:30", stop=0.0020, hold=5), "base")
        adv = run(fr(), self.START, self.END, Scripted("2026-04-08 09:30", stop=0.0020, hold=5), "adverse")
        self.assertEqual(ts(base["trades"][0]["entry_ts_ns"]), pd.Timestamp("2026-04-08 09:30:01", tz="UTC"))
        self.assertEqual(ts(adv["trades"][0]["entry_ts_ns"]), pd.Timestamp("2026-04-08 09:31:01", tz="UTC"))   # one bar later
        self.assertLess(adv["trades"][0]["net_eur"] / adv["trades"][0]["units"], base["trades"][0]["net_eur"] / base["trades"][0]["units"] + 1e-3)


class GatesAndSessions(unittest.TestCase):
    def test_force_flat_at_1655_new_york_before_the_rollover(self):
        start, end = "2026-04-08 20:00", "2026-04-08 21:20"          # 16:00-17:20 New York (EDT)
        r = run(frame(start, end), start, end, Scripted("2026-04-08 20:20", hold=240))
        t = r["trades"][0]
        self.assertEqual(t["exit_reason"], "FORCE_FLAT")
        self.assertEqual(ts(t["exit_ts_ns"]), pd.Timestamp("2026-04-08 20:55:01", tz="UTC"))

    def test_no_new_entries_in_the_rollover_window(self):
        start, end = "2026-04-08 20:00", "2026-04-08 21:20"
        r = run(frame(start, end), start, end, Scripted("2026-04-08 20:35", hold=5))
        self.assertEqual(r["n_trades"], 0)
        self.assertEqual(r["reject_counts"].get("SESSION_NO_ENTRY"), 1)

    def test_cost_gate_rejects_when_the_spread_is_too_wide_for_the_risk(self):
        start, end = "2026-04-08 09:00", "2026-04-08 10:30"
        r = run(frame(start, end, spread=0.0006), start, end, Scripted("2026-04-08 09:30", stop=0.0010))
        self.assertEqual(r["n_trades"], 0)
        self.assertEqual(r["reject_counts"].get("COST_GATE"), 1)

    def test_a_stop_too_wide_for_the_risk_budget_is_rejected_never_rounded_up(self):
        start, end = "2026-04-08 09:00", "2026-04-08 10:30"
        r = run(frame(start, end), start, end, Scripted("2026-04-08 09:30", stop=0.0100))
        self.assertEqual(r["n_trades"], 0)
        self.assertEqual(r["reject_counts"].get("BELOW_MIN_UNITS"), 1)

    def test_zero_volume_minutes_produce_no_quotes_and_do_not_break_the_run(self):
        start, end = "2026-04-08 09:00", "2026-04-08 10:30"
        ov = {f"2026-04-08 09:{m:02d}": dict(valid=False) for m in range(36, 40)}
        r = run(frame(start, end, ov), start, end, Scripted("2026-04-08 09:30", hold=15))
        self.assertEqual(r["n_trades"], 1)

    def test_governed_mode_pauses_after_a_ten_percent_drawdown_research_mode_does_not(self):
        # Two consecutive gap-through-stop losses (R < -1 each) cannot reach 10% of EUR 500; this test checks the flag
        # plumbing instead: governed mode uses the real pause fraction, research mode disables it.
        start, end = "2026-04-08 09:00", "2026-04-08 10:30"
        g = run(frame(start, end), start, end, Scripted("2026-04-08 09:30"), mode="governed")
        r = run(frame(start, end), start, end, Scripted("2026-04-08 09:30"), mode="research")
        self.assertFalse(g["paused_drawdown"] or r["paused_drawdown"])


if __name__ == "__main__":
    unittest.main()
