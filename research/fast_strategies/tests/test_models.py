"""Deterministic tests of the F01-F07 signal rules on crafted bar sequences, plus look-ahead and DST properties."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fast_research import specs as S  # noqa: E402
from fast_research.harness import bars as B  # noqa: E402
from fast_research.strategies import models as M  # noqa: E402

NS = 10**9
MIN = 60 * NS


def ns(s):
    return int(pd.Timestamp(s, tz="UTC").value)


class Ctx:
    risk_fraction = 0.005

    def __init__(self, pairs=("EURUSD",), tfs=(1, 5, 15, 60)):
        self.state = {p: B.PairState(tfs) for p in pairs}


def spec(fid):
    return S.family_spec(fid)


def put(ctx, pair, tf, bars):
    ctx.state[pair].aggs[tf].bars.extend(bars)


def mkbars(tf, t0, steps, rng=0.0010, start=1.1000, n_flat=20):
    """n_flat flat bars (TR == rng) then bars moving by `steps` (price units per bar, TR kept == rng where |step|<=rng-2*pad).
    Returns (list of Bar, atr)."""
    out, price, i = [], start, 0
    pad = rng * 0.1
    tfns = tf * MIN
    for _ in range(n_flat):
        out.append(B.Bar(t0 + i * tfns, t0 + (i + 1) * tfns, price, price + rng / 2, price - rng / 2, price, tf)); i += 1
    for st in steps:
        c = price + st
        hi, lo = max(price, c) + pad, min(price, c) - pad
        # widen to exactly rng where possible so ATR stays == rng
        extra = rng - (hi - lo)
        if extra > 0:
            hi, lo = hi + extra / 2, lo - extra / 2
        out.append(B.Bar(t0 + i * tfns, t0 + (i + 1) * tfns, price, hi, lo, c, tf)); i += 1; price = c
    return out


class F01Tests(unittest.TestCase):
    T0 = ns("2026-04-08 06:00")

    def run_f01(self, steps):
        ctx = Ctx()
        put(ctx, "EURUSD", 15, mkbars(15, self.T0, steps))
        last = list(ctx.state["EURUSD"].bars(15))[-1]
        return M.F01(spec("F01")).entry(ctx, "EURUSD", {15: last})

    def test_long_when_displacement_exceeds_scaled_threshold_and_last_bar_up(self):
        out = self.run_f01([0.0008] * 4)             # disp 0.0032 ; ATR 0.0010 ; z = 0.0032/(0.0010*2) = 1.6
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].direction, out[0].reason), (1, "F01_TREND"))
        self.assertAlmostEqual(out[0].stop_distance, 1.5 * 0.0010, places=6)
        self.assertEqual((out[0].hold_minutes, out[0].time_exit_tf), (60, 15))

    def test_short_mirror(self):
        out = self.run_f01([-0.0008] * 4)
        self.assertEqual(out[0].direction, -1)

    def test_no_signal_below_threshold(self):
        self.assertEqual(self.run_f01([0.0006] * 4), [])    # z = 1.2

    def test_unscaled_atr_would_have_fired_but_scaled_does_not(self):
        # 4-bar displacement of 1.5*ATR passes the OLD unscaled rule (z=1.5) but is only 0.75 in sqrt(k)-scaled units
        self.assertEqual(self.run_f01([0.000375] * 4), [])

    def test_last_bar_must_close_in_the_direction(self):
        self.assertEqual(self.run_f01([0.0012, 0.0012, 0.0012, -0.0002]), [])   # net up 0.0034 but last bar down

    def test_warmup_requires_atr_history(self):
        ctx = Ctx()
        put(ctx, "EURUSD", 15, mkbars(15, self.T0, [0.0008] * 4, n_flat=5))
        last = list(ctx.state["EURUSD"].bars(15))[-1]
        self.assertEqual(M.F01(spec("F01")).entry(ctx, "EURUSD", {15: last}), [])


class F02Tests(unittest.TestCase):
    T0 = ns("2026-04-08 06:00")

    def _ctx(self, closes, tf=5):
        ctx = Ctx()
        bars = mkbars(tf, self.T0, [], n_flat=20)
        t = bars[-1].t_close
        price = bars[-1].c
        for c in closes:
            bars.append(B.Bar(t, t + tf * MIN, price, max(price, c) + 0.0003, min(price, c) - 0.0003, c, tf))
            t += tf * MIN; price = c
        put(ctx, "EURUSD", tf, bars)
        return ctx, bars[-1]

    def test_fades_an_extreme_upward_deviation(self):
        ctx, last = self._ctx([1.1000] * 11 + [1.1020])        # last close far above the 12-bar mean
        out = M.F02(spec("F02")).entry(ctx, "EURUSD", {5: last})
        self.assertEqual(out[0].direction, -1)

    def test_fades_an_extreme_downward_deviation(self):
        ctx, last = self._ctx([1.1000] * 11 + [1.0980])
        self.assertEqual(M.F02(spec("F02")).entry(ctx, "EURUSD", {5: last})[0].direction, 1)

    def test_no_trade_when_deviation_is_ordinary_or_dispersion_is_zero(self):
        ctx, last = self._ctx([1.1000] * 12)
        self.assertEqual(M.F02(spec("F02")).entry(ctx, "EURUSD", {5: last}), [])

    def test_partial_reversion_exit_signal(self):
        ctx, last = self._ctx([1.1000] * 6 + [1.1002] * 5 + [1.1001])      # last close ~ at the 12-bar mean (|z| ~ 0.1)
        self.assertEqual(M.F02(spec("F02")).exit_signal(ctx, "EURUSD", {}, {5: last}), "REVERSION_EXIT")


class F03Tests(unittest.TestCase):
    T0 = ns("2026-04-08 00:00")

    def _bars(self, last_close_delta):
        # 60 bars of normal range, then 8 compressed bars, then the breakout bar
        tf, t0 = 15, self.T0
        out, price, i = [], 1.1000, 0
        for _ in range(60):
            out.append(B.Bar(t0 + i * tf * MIN, t0 + (i + 1) * tf * MIN, price, price + 0.0010, price - 0.0010, price, tf)); i += 1
        for _ in range(8):
            out.append(B.Bar(t0 + i * tf * MIN, t0 + (i + 1) * tf * MIN, price, price + 0.0002, price - 0.0002, price, tf)); i += 1
        c = price + last_close_delta
        out.append(B.Bar(t0 + i * tf * MIN, t0 + (i + 1) * tf * MIN, price, max(price, c) + 0.0001, min(price, c) - 0.0001, c, tf))
        return out

    def test_breakout_after_compression_long_and_short(self):
        for delta, d in ((+0.0010, 1), (-0.0010, -1)):
            ctx = Ctx(); bars = self._bars(delta); put(ctx, "EURUSD", 15, bars)
            out = M.F03(spec("F03")).entry(ctx, "EURUSD", {15: bars[-1]})
            self.assertEqual([o.direction for o in out], [d])

    def test_no_signal_inside_the_range_or_without_compression(self):
        ctx = Ctx(); bars = self._bars(+0.0001); put(ctx, "EURUSD", 15, bars)
        self.assertEqual(M.F03(spec("F03")).entry(ctx, "EURUSD", {15: bars[-1]}), [])
        ctx2 = Ctx(); b2 = mkbars(15, self.T0, [0.0008] * 4, n_flat=60); put(ctx2, "EURUSD", 15, b2)
        self.assertEqual(M.F03(spec("F03")).entry(ctx2, "EURUSD", {15: b2[-1]}), [])


def _pair_bars(rng, disp, tf=15, n_flat=20, start=1.1000, t0=None):
    t0 = t0 or ns("2026-04-08 06:00")
    steps = [disp / 4.0] * 4 if disp else []
    return mkbars(tf, t0, steps, rng=rng, start=start, n_flat=n_flat if disp else n_flat + 4)


class F04Tests(unittest.TestCase):
    RNG = {"EURUSD": 0.0010, "GBPUSD": 0.0010, "AUDUSD": 0.0010, "NZDUSD": 0.0010, "USDCHF": 0.0010, "USDCAD": 0.0010, "USDJPY": 0.10}

    def _ctx(self, disp):
        ctx = Ctx(tuple(self.RNG))
        for p, r in self.RNG.items():
            put(ctx, p, 15, _pair_bars(r, disp.get(p, 0.0), start=150.0 if p == "USDJPY" else 1.0))
        return ctx

    def test_long_strongest_short_weakest_is_usd_neutral(self):
        # EUR strongest (+), JPY weakest (USDJPY up => JPY weak)
        ctx = self._ctx({"EURUSD": 0.0040, "USDJPY": 0.40})
        last = list(ctx.state["USDJPY"].bars(15))[-1]
        legs = M.F04(spec("F04")).entry(ctx, "USDJPY", {15: last})
        self.assertEqual(sorted((l.pair, l.direction) for l in legs), [("EURUSD", 1), ("USDJPY", 1)])
        self.assertEqual({l.group for l in legs}, {legs[0].group})
        self.assertTrue(all(abs(l.risk_fraction - 0.0025) < 1e-12 for l in legs))

    def test_quote_currency_direction_logic(self):
        # CHF strongest (USDCHF falls) vs GBP weakest (GBPUSD falls): long CHF = SELL USDCHF ; short GBP = SELL GBPUSD
        ctx = self._ctx({"USDCHF": -0.0040, "GBPUSD": -0.0040})
        last = list(ctx.state["GBPUSD"].bars(15))[-1]
        legs = M.F04(spec("F04")).entry(ctx, "GBPUSD", {15: last})
        self.assertEqual(sorted((l.pair, l.direction) for l in legs), [("GBPUSD", -1), ("USDCHF", -1)])

    def test_below_gap_threshold_no_trade(self):
        ctx = self._ctx({"EURUSD": 0.0016})   # normalized strength 0.8, gap < 3
        last = list(ctx.state["EURUSD"].bars(15))[-1]
        self.assertEqual(M.F04(spec("F04")).entry(ctx, "EURUSD", {15: last}), [])

    def test_requires_all_seven_pairs_aligned_on_the_boundary(self):
        ctx = self._ctx({"EURUSD": 0.0040, "USDJPY": 0.40})
        ctx.state["GBPUSD"].aggs[15].bars.pop()                   # GBPUSD missed this boundary
        last = list(ctx.state["USDJPY"].bars(15))[-1]
        self.assertEqual(M.F04(spec("F04")).entry(ctx, "USDJPY", {15: last}), [])


class F05Tests(unittest.TestCase):
    def _run(self, open_utc, offset_minutes=0, n_or_minutes=30, breakout=+1):
        """Build the opening range minute by minute from `open_utc + offset`, then a 5m breakout bar."""
        model = M.F05(spec("F05"))
        ctx = Ctx(("EURUSD",))
        t0 = ns(open_utc) + offset_minutes * MIN
        price = 1.1000
        # warm ATR(15m) with 20 bars of 0.0010 range ending before the open
        put(ctx, "EURUSD", 15, mkbars(15, t0 - 21 * 15 * MIN, [], rng=0.0010, n_flat=21))
        for i in range(n_or_minutes):
            model.on_minute(ctx, "EURUSD", t0 + i * MIN, price, price + 0.0003, price - 0.0003, price)
        t5 = t0 + 30 * MIN
        c = price + breakout * 0.0009
        bar = B.Bar(t5, t5 + 5 * MIN, price, max(price, c), min(price, c), c, 5)
        put(ctx, "EURUSD", 5, [bar])
        return model.entry(ctx, "EURUSD", {5: bar})

    def test_london_open_range_breakout_in_summer_and_winter(self):
        self.assertEqual([i.direction for i in self._run("2026-07-01 07:00")], [1])    # 08:00 BST
        self.assertEqual([i.direction for i in self._run("2026-01-12 08:00")], [1])    # 08:00 GMT
        self.assertEqual([i.direction for i in self._run("2026-07-01 07:00", breakout=-1)], [-1])

    def test_new_york_open_range_breakout_in_summer_and_winter(self):
        self.assertEqual([i.reason for i in self._run("2026-07-01 12:00")], ["F05_OR_NEW_YORK"])
        self.assertEqual([i.reason for i in self._run("2026-01-12 13:00")], ["F05_OR_NEW_YORK"])

    def test_wrong_utc_hour_for_the_season_builds_no_range(self):
        self.assertEqual(self._run("2026-01-12 07:00"), [])      # London winter open is 08:00 UTC, not 07:00
        self.assertEqual(self._run("2026-07-01 08:00"), [])      # London summer open is 07:00 UTC, not 08:00

    def test_range_with_too_few_valid_minutes_is_not_traded(self):
        self.assertEqual(self._run("2026-07-01 07:00", n_or_minutes=20), [])

    def test_only_one_signal_per_pair_session_day(self):
        model = M.F05(spec("F05"))
        ctx = Ctx(("EURUSD",)); t0 = ns("2026-07-01 07:00")
        put(ctx, "EURUSD", 15, mkbars(15, t0 - 21 * 15 * MIN, [], n_flat=21))
        for i in range(30):
            model.on_minute(ctx, "EURUSD", t0 + i * MIN, 1.1, 1.1003, 1.0997, 1.1)
        t5 = t0 + 30 * MIN
        b1 = B.Bar(t5, t5 + 5 * MIN, 1.1, 1.1009, 1.1, 1.1009, 5)
        b2 = B.Bar(t5 + 5 * MIN, t5 + 10 * MIN, 1.1009, 1.1012, 1.1009, 1.1012, 5)
        put(ctx, "EURUSD", 5, [b1, b2])
        self.assertEqual(len(model.entry(ctx, "EURUSD", {5: b1})), 1)
        self.assertEqual(model.entry(ctx, "EURUSD", {5: b2}), [])


class F06F07Tests(unittest.TestCase):
    T0 = ns("2026-04-08 06:00")

    def _f06(self, trend_up=True, fine_up=True):
        ctx = Ctx()
        fine = [0.0008] * 6 if fine_up else [-0.0008] * 6
        put(ctx, "EURUSD", 5, mkbars(5, self.T0, fine))
        h1 = []
        for i in range(12):
            c = 1.0900 if trend_up else 1.1200
            h1.append(B.Bar(self.T0 + i * 60 * MIN, self.T0 + (i + 1) * 60 * MIN, c, c, c, c, 60))
        last = 1.1100 if trend_up else 1.0800
        h1.append(B.Bar(self.T0 + 12 * 60 * MIN, self.T0 + 13 * 60 * MIN, last, last, last, last, 60))
        put(ctx, "EURUSD", 60, h1)
        return ctx, list(ctx.state["EURUSD"].bars(5))[-1]

    def test_f06_requires_coarse_trend_alignment(self):
        ctx, last = self._f06(trend_up=True, fine_up=True)
        self.assertEqual([i.direction for i in M.F06(spec("F06")).entry(ctx, "EURUSD", {5: last})], [1])
        ctx, last = self._f06(trend_up=False, fine_up=True)             # fine up but coarse trend down -> filtered
        self.assertEqual(M.F06(spec("F06")).entry(ctx, "EURUSD", {5: last}), [])
        ctx, last = self._f06(trend_up=False, fine_up=False)
        self.assertEqual([i.direction for i in M.F06(spec("F06")).entry(ctx, "EURUSD", {5: last})], [-1])

    def _f07(self, cls):
        ctx = Ctx()
        put(ctx, "EURUSD", 1, mkbars(1, self.T0, [0.00005] * 5, rng=0.00004, n_flat=20))   # tiny 1m ATR, fast impulse (z ~ 2.5)
        put(ctx, "EURUSD", 5, mkbars(5, self.T0, [], rng=0.0006, n_flat=20))
        return ctx, list(ctx.state["EURUSD"].bars(1))[-1]

    def test_f07_momentum_and_f07r_is_its_exact_mirror(self):
        ctx, last = self._f07(M.F07)
        m = M.F07(spec("F07")).entry(ctx, "EURUSD", {1: last})
        r = M.F07R(spec("F07")).entry(ctx, "EURUSD", {1: last})
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0].direction, -r[0].direction)
        self.assertEqual((m[0].stop_distance, m[0].hold_minutes), (r[0].stop_distance, r[0].hold_minutes))
        self.assertAlmostEqual(m[0].stop_distance, 1.5 * 0.0006, places=7)    # stop scale from 5m ATR, not 1m


class NoLookAheadTests(unittest.TestCase):
    """Decisions made at minute t may depend only on minutes <= t: change the future, the past decisions stay identical."""

    def _decisions(self, closes, fid):
        spec_f = spec("F07" if fid == "F07R" else fid)
        model = M.MODELS[fid](spec_f)
        ctx = Ctx(("EURUSD",), tfs=(1, 5, 15, 60))
        t0 = ns("2026-04-08 00:00")
        out, prev = [], closes[0]
        for i, c in enumerate(closes):
            h, l = max(prev, c) + 0.0002, min(prev, c) - 0.0002
            done = ctx.state["EURUSD"].feed(t0 + i * MIN, prev, h, l, c)
            model.on_minute(ctx, "EURUSD", t0 + i * MIN, prev, h, l, c)
            for it in model.entry(ctx, "EURUSD", done):
                out.append((i, it.direction, round(it.stop_distance, 9)))
            prev = c
        return out

    def test_prefix_decisions_are_independent_of_the_future(self):
        rng = np.random.default_rng(7)
        base = 1.1 + np.cumsum(rng.normal(0, 0.0004, 1800))
        alt = base.copy()
        alt[1200:] = 1.1 + np.cumsum(rng.normal(0, 0.0015, 600)) * 3      # radically different future
        for fid in ("F01", "F02", "F03", "F05", "F06", "F07", "F07R"):
            a = [d for d in self._decisions(list(base), fid) if d[0] < 1200]
            b = [d for d in self._decisions(list(alt), fid) if d[0] < 1200]
            self.assertEqual(a, b, fid)


if __name__ == "__main__":
    unittest.main()
