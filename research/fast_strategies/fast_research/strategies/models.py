"""Pure signal models for F01-F07 (v1_builder_proposed). No Nautilus imports: every model is a deterministic function
of COMPLETED bars held in `PairState`, so it cannot see the future and can be unit-tested with synthetic bars.

A model produces entry `Intent`s (all-or-nothing as a group for F04) and optionally a signal-based exit. Sizing, risk
gates, costs and order handling live in the shared harness, never here. Parameters are read from the frozen spec.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import math

from ..harness.bars import atr, sma_close, std_close
from ..harness.session import local_date, session_open_utc_ns

NS_MIN = 60_000_000_000
USD_PAIRS = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD")
BASE_VS_USD = {"EURUSD": "EUR", "GBPUSD": "GBP", "AUDUSD": "AUD", "NZDUSD": "NZD"}   # currency is the BASE: strength = +move
QUOTE_VS_USD = {"USDJPY": "JPY", "USDCHF": "CHF", "USDCAD": "CAD"}                    # currency is the QUOTE: strength = -move


@dataclass
class Intent:
    pair: str
    direction: int            # +1 long, -1 short
    stop_distance: float      # price units from the entry fill
    hold_minutes: int
    time_exit_tf: int         # minutes; the time exit is taken at the first such boundary >= signal close + hold
    risk_fraction: float
    reason: str
    meta: dict = field(default_factory=dict)
    group: str | None = None  # all intents sharing a group are sent together or not at all


def _up(bar) -> bool:
    return bar.c > bar.o


class Model:
    id = "BASE"
    tfs: tuple = ()
    spec: dict = {}

    def __init__(self, spec: dict):
        self.spec = spec["operationalization"]

    def on_minute(self, ctx, pair, t_open, o, h, l, c) -> None:  # optional accumulation hook (F05)
        return None

    def entry(self, ctx, pair, done: dict) -> list:
        return []

    def exit_signal(self, ctx, pair, trade, done: dict):
        return None


class F01(Model):
    id, tfs = "F01", (15,)

    def entry(self, ctx, pair, done):
        if 15 not in done:
            return []
        p = self.spec
        bars = ctx.state[pair].bars(15)
        a = atr(bars, p["atr_n"])
        k = p["lookback_bars"]
        if a is None or a <= 0 or len(bars) < k + 1:
            return []
        seq = list(bars)
        b, ref = seq[-1], seq[-1 - k]
        z = (b.c - ref.c) / (a * math.sqrt(k))
        thr = p["move_threshold_atr"]
        if z >= thr and _up(b):
            d = 1
        elif z <= -thr and b.c < b.o:
            d = -1
        else:
            return []
        return [Intent(pair, d, p["stop_multiple"] * a, p["max_holding_minutes"], 15, ctx.risk_fraction, "F01_TREND",
                       {"z": z, "atr": a})]


class F02(Model):
    id, tfs = "F02", (5,)

    def _z(self, ctx, pair):
        bars = ctx.state[pair].bars(5)
        sd, m = std_close(bars, 12), sma_close(bars, 12)
        if sd is None or sd <= 0:
            return None
        return (list(bars)[-1].c - m) / sd

    def entry(self, ctx, pair, done):
        if 5 not in done:
            return []
        p = self.spec
        a = atr(ctx.state[pair].bars(5), p["atr_n"])
        z = self._z(ctx, pair)
        if a is None or a <= 0 or z is None:
            return []
        if z >= p["entry_z"]:
            d = -1
        elif z <= -p["entry_z"]:
            d = 1
        else:
            return []
        return [Intent(pair, d, p["stop_multiple"] * a, p["max_holding_minutes"], 5, ctx.risk_fraction, "F02_FADE",
                       {"z": z, "atr": a})]

    def exit_signal(self, ctx, pair, trade, done):
        if 5 not in done:
            return None
        z = self._z(ctx, pair)
        if z is not None and abs(z) <= self.spec["exit_z"]:
            return "REVERSION_EXIT"
        return None


class F03(Model):
    id, tfs = "F03", (15,)

    def entry(self, ctx, pair, done):
        if 15 not in done:
            return []
        p = self.spec
        bars = ctx.state[pair].bars(15)
        n_rng = p["range_bars"]
        a14 = atr(bars, p["atr_n"])
        s_prev = atr(bars, p["compression_short_atr"], end=1)
        l_prev = atr(bars, p["compression_long_atr"], end=1)
        if a14 is None or a14 <= 0 or s_prev is None or l_prev is None or l_prev <= 0 or len(bars) < n_rng + 1:
            return []
        if s_prev / l_prev > p["compression_ratio_max"]:
            return []
        seq = list(bars)
        b, prior = seq[-1], seq[-1 - n_rng:-1]
        hi, lo = max(x.h for x in prior), min(x.l for x in prior)
        if b.c > hi:
            d = 1
        elif b.c < lo:
            d = -1
        else:
            return []
        return [Intent(pair, d, p["stop_multiple"] * a14, p["max_holding_minutes"], 15, ctx.risk_fraction, "F03_BREAKOUT",
                       {"ratio": s_prev / l_prev, "atr": a14, "range_hi": hi, "range_lo": lo})]


class F04(Model):
    id, tfs = "F04", (15,)

    def entry(self, ctx, pair, done):
        if 15 not in done:
            return []
        p = self.spec
        t_close = done[15].t_close
        k = p["lookback_bars"]
        strength = {}
        atrs = {}
        for q in USD_PAIRS:
            bars = ctx.state[q].bars(15)
            seq = list(bars)
            a = atr(bars, p["atr_n"])
            if a is None or a <= 0 or len(seq) < k + 1 or seq[-1].t_close != t_close:
                return []   # all seven pairs must have a completed, aligned bar for this boundary
            m = (seq[-1].c - seq[-1 - k].c) / (a * math.sqrt(k))
            atrs[q] = a
            if q in BASE_VS_USD:
                strength[BASE_VS_USD[q]] = (m, q, +1)
            else:
                strength[QUOTE_VS_USD[q]] = (-m, q, -1)
        # Alignment above guarantees only the LAST pair to complete this boundary reaches this point, so the
        # decision is evaluated exactly once per boundary.
        ranked = sorted(strength.items(), key=lambda kv: kv[1][0])
        weak, strong = ranked[0], ranked[-1]
        if strong[1][0] - weak[1][0] < p["min_strength_gap_atr"]:
            return []
        gid = f"F04@{t_close}"
        legs = []
        for (ccy, (s, q, role)), want_strong in ((strong, True), (weak, False)):
            # want to be LONG the currency if strong, SHORT if weak; BASE role: long ccy == BUY pair; QUOTE role: long ccy == SELL pair
            long_ccy = want_strong
            d = (+1 if long_ccy else -1) * role
            legs.append(Intent(q, d, p["stop_multiple"] * atrs[q], p["max_holding_minutes"], 15, p["leg_risk_fraction"],
                               "F04_RELATIVE_STRENGTH", {"currency": ccy, "strength": s, "gap": strong[1][0] - weak[1][0]}, gid))
        return legs


class F05(Model):
    id, tfs = "F05", (1, 5, 15)

    def __init__(self, spec):
        super().__init__(spec)
        self.rng: dict = {}      # (pair, session, local_date) -> dict(hi, lo, n, taken)

    def _keys(self, t_open):
        for s in self.spec["sessions"]:
            ld = local_date(t_open, s["tz"])
            hh, mm = (int(x) for x in s["open_local"].split(":"))
            open_ns = session_open_utc_ns(ld, s["tz"], dt.time(hh, mm))
            yield s["name"], ld, open_ns

    def on_minute(self, ctx, pair, t_open, o, h, l, c):
        w = self.spec["range_window_minutes"] * NS_MIN
        for name, ld, open_ns in self._keys(t_open):
            if open_ns <= t_open < open_ns + w:
                r = self.rng.setdefault((pair, name, ld), {"hi": h, "lo": l, "n": 0, "taken": False})
                r["hi"], r["lo"], r["n"] = max(r["hi"], h), min(r["lo"], l), r["n"] + 1

    def entry(self, ctx, pair, done):
        if 5 not in done:
            return []
        p = self.spec
        b5 = done[5]
        w = p["range_window_minutes"] * NS_MIN
        ew = p["entry_window_minutes"] * NS_MIN
        for name, ld, open_ns in self._keys(b5.t_open):
            if not (open_ns + w <= b5.t_open and b5.t_close <= open_ns + w + ew):
                continue
            r = self.rng.get((pair, name, ld))
            if r is None or r["taken"] or r["n"] < 24:
                continue
            a = atr(ctx.state[pair].bars(15), p["atr_n"])
            if a is None or a <= 0:
                continue
            width = r["hi"] - r["lo"]
            if not (p["range_width_atr_min"] * a <= width <= p["range_width_atr_max"] * a):
                r["taken"] = True      # range quality fails for this session-day
                continue
            if b5.c > r["hi"]:
                d, dist = 1, b5.c - r["lo"]
            elif b5.c < r["lo"]:
                d, dist = -1, r["hi"] - b5.c
            else:
                continue
            r["taken"] = True            # first breakout bar is the one signal for this pair/session/day
            dist = max(dist, 1.0 * a)
            if dist > 2.5 * a:
                continue
            return [Intent(pair, d, dist, p["max_holding_minutes"], 5, ctx.risk_fraction, f"F05_OR_{name}",
                           {"session": name, "range_hi": r["hi"], "range_lo": r["lo"], "atr": a})]
        return []


class F06(Model):
    id, tfs = "F06", (5, 60)

    def entry(self, ctx, pair, done):
        if 5 not in done:
            return []
        p = self.spec
        b5s = ctx.state[pair].bars(5)
        a = atr(b5s, p["atr_n"])
        k = p["fine_lookback_bars"]
        h1 = ctx.state[pair].bars(60)
        if a is None or a <= 0 or len(b5s) < k + 1 or len(h1) < p["coarse_sma_bars"]:
            return []
        seq = list(b5s)
        b, ref = seq[-1], seq[-1 - k]
        z = (b.c - ref.c) / (a * math.sqrt(k))
        thr = p["fine_threshold_atr"]
        if z >= thr and _up(b):
            d = 1
        elif z <= -thr and b.c < b.o:
            d = -1
        else:
            return []
        sma = sma_close(h1, p["coarse_sma_bars"])
        last = list(h1)[-1].c
        trend = 1 if last > sma else (-1 if last < sma else 0)
        if trend != d:
            return []
        return [Intent(pair, d, p["stop_multiple"] * a, p["max_holding_minutes"], 5, ctx.risk_fraction, "F06_MTF",
                       {"z": z, "trend": trend, "atr": a})]


class F07(Model):
    id, tfs = "F07", (1, 5)
    sign = 1  # momentum arm

    def entry(self, ctx, pair, done):
        if 1 not in done:
            return []
        p = self.spec
        b1 = ctx.state[pair].bars(1)
        a1 = atr(b1, p["atr_n"])
        a5 = atr(ctx.state[pair].bars(5), p["atr_n"])
        k = p["lookback_bars"]
        if a1 is None or a1 <= 0 or a5 is None or a5 <= 0 or len(b1) < k + 1:
            return []
        seq = list(b1)
        b, ref = seq[-1], seq[-1 - k]
        z = (b.c - ref.c) / (a1 * math.sqrt(k))
        thr = p["impulse_threshold_atr"]
        if z >= thr and _up(b):
            d = 1
        elif z <= -thr and b.c < b.o:
            d = -1
        else:
            return []
        return [Intent(pair, d * self.sign, p["stop_multiple"] * a5, p["max_holding_minutes"], 1, ctx.risk_fraction,
                       "F07_MOMENTUM" if self.sign == 1 else "F07R_REVERSAL", {"z": z, "atr1": a1, "atr5": a5})]


class F07R(F07):
    id = "F07R"
    sign = -1


MODELS = {"F01": F01, "F02": F02, "F03": F03, "F04": F04, "F05": F05, "F06": F06, "F07": F07, "F07R": F07R}
