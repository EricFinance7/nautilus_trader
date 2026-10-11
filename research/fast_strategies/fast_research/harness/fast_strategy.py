"""Generic Nautilus strategy that runs ANY F-family model under the shared EUR 500 harness.

Responsibilities kept here (never in the models): entry gating (session block, daily loss, drawdown pause, max
positions, combined open risk), risk-based sizing + cost gate, native order submission (market entry, reduce-only
STOP_MARKET protection, reduce-only market exits), stop handling, trade finalization into the virtual ledger, and the
append-only journal. The engine remains the source of fills, positions and margin; the ledger adds only the documented
stop-fill repricing and EUR conversion.
"""
from __future__ import annotations

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import BarType, OrderSide, Quantity, TriggerType
from nautilus_trader.trading import Strategy

from ..strategies.models import MODELS
from . import instruments as I
from .bars import PairState
from .ledger import VirtualLedger
from .session import entry_blocked, force_flat_due
from .sizing import cost_gate, expected_round_trip_cost_eur, position_size

NS_MIN = 60_000_000_000


def guarded(fn):
    """Nautilus only LOGS exceptions raised inside strategy callbacks and keeps running, which would let a broken
    strategy silently do nothing. Record them so the runner can fail loudly."""
    import functools
    import traceback

    @functools.wraps(fn)
    def wrapper(self, *a, **k):
        try:
            return fn(self, *a, **k)
        except Exception:  # noqa: BLE001
            if len(self.errors) < 5:
                self.errors.append(traceback.format_exc())
            raise
    return wrapper


def money_value(m) -> float:
    for attr in ("as_double", "as_f64", "to_float"):
        f = getattr(m, attr, None)
        if f is not None:
            return float(f())
    return float(m.as_decimal())


class FastConfig(StrategyConfig):
    def __init__(self, *, family: str, family_spec: dict, harness: dict, scenario: str, journal_path=None, mode: str = "governed", model_factory=None, trade_from_ns: int = 0, restore_journal=None, **_):
        super().__init__()
        self.family, self.family_spec, self.harness = family, family_spec, harness
        self.scenario, self.journal_path, self.mode, self.model_factory = scenario, journal_path, mode, model_factory
        self.trade_from_ns, self.restore_journal = trade_from_ns, restore_journal


class FastStrategy(Strategy):
    def __init__(self, config: FastConfig):
        super().__init__(config)
        h = config.harness
        cap, self.sc = h["capital_and_risk"], h["costs"]["scenarios"][config.scenario]
        self.cap = cap
        self.model = (config.model_factory or MODELS[config.family])(config.family_spec)
        self.family = config.family
        self.trade_from_ns = config.trade_from_ns
        self.errors: list[str] = []
        self.pairs = list(h["universe"])
        tfs = set(self.model.tfs) | {1, 5, 15}
        self.state = {p: PairState(tfs, h["data"]["session_reset_gap_minutes"]) for p in self.pairs}
        self.research = config.mode == "research"   # amendment A4: fixed sizing equity, drawdown pause off
        dd = 1e9 if self.research else cap["drawdown_pause_fraction"]
        if config.restore_journal:    # restart recovery: rebuild equity/peak/daily state from the append-only journal
            # Never open a journal for writing before it has been read (that would truncate the record).
            self.ledger = VirtualLedger.rebuild(config.restore_journal, append=False,
                                                initial_eur=cap["initial_virtual_equity_eur"],
                                                daily_loss_fraction=cap["daily_realized_loss_limit_fraction"],
                                                drawdown_fraction=dd)
            if config.journal_path:
                self.ledger._fh = open(config.journal_path, "a", encoding="utf-8")
        else:
            self.ledger = VirtualLedger(cap["initial_virtual_equity_eur"], cap["daily_realized_loss_limit_fraction"],
                                        dd, config.journal_path)
        self.risk_fraction = cap["risk_per_trade_fraction"]
        self.open: dict[str, dict] = {}
        self.pending: dict[str, dict] = {}
        self.roles: dict[str, tuple] = {}
        self.now_ns = 0
        self.reject_counts: dict[str, int] = {}
        self.ledger_minus_engine_eur = 0.0
        self._iid_to_pair = {str(I.instrument_id(p)): p for p in self.pairs}
        self._max_pos = cap["max_simultaneous_positions"]
        self._max_open_risk = cap["max_combined_open_risk_fraction"]

    # ------------------------------------------------------------------ lifecycle
    def on_start(self):
        for p in self.pairs:
            self.subscribe_bars(BarType.from_str(f"{I.symbol(p)}.SIM-1-MINUTE-MID-INTERNAL"))

    # ------------------------------------------------------------------ helpers
    def _quote(self, pair):
        return self.cache.quote(I.instrument_id(pair))

    def _mid(self, pair):
        q = self._quote(pair)
        return None if q is None else (float(q.bid_price) + float(q.ask_price)) / 2.0

    def eur_per_quote(self, quote_ccy: str):
        if quote_ccy == "EUR":
            return 1.0
        eurusd = self._mid("EURUSD")
        if eurusd is None:
            return None
        if quote_ccy == "USD":
            return 1.0 / eurusd
        usd_x = self._mid("USD" + quote_ccy)
        return None if usd_x is None else 1.0 / (eurusd * usd_x)

    def _reject(self, reason: str, intent=None, **extra):
        self.reject_counts[reason] = self.reject_counts.get(reason, 0) + 1
        self.ledger.log("ENTRY_REJECTED", self.now_ns, reason=reason,
                        pair=getattr(intent, "pair", None), family=self.family, signal=getattr(intent, "reason", None), **extra)

    # ------------------------------------------------------------------ data
    @guarded
    def on_bar(self, bar):
        pair = self._iid_to_pair.get(str(bar.bar_type.instrument_id))
        if pair is None:
            return
        t_close = bar.ts_event
        self.now_ns = t_close
        t_open = t_close - NS_MIN
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        done = self.state[pair].feed(t_open, o, h, l, c)
        self.model.on_minute(self, pair, t_open, o, h, l, c)
        self._manage(pair, done, t_close)
        self._maybe_enter(pair, done, t_close)

    # ------------------------------------------------------------------ exits
    def _manage(self, pair, done, now):
        tr = self.open.get(pair)
        if tr is None or tr["exit_sent"]:
            return
        reason = None
        if force_flat_due(now):
            reason = "FORCE_FLAT"
        elif now >= tr["deadline"] and now % (tr["tf"] * NS_MIN) == 0:
            reason = "TIME_EXIT"
        else:
            reason = self.model.exit_signal(self, pair, tr, done)
        if reason:
            self._send_exit(pair, reason)

    def _send_exit(self, pair, reason):
        tr = self.open[pair]
        tr["exit_sent"], tr["exit_reason"] = True, reason
        inst = self.cache.instrument(I.instrument_id(pair))
        side = OrderSide.SELL if tr["dir"] > 0 else OrderSide.BUY
        o = self.order_factory.market(inst.id, side, inst.make_qty(tr["units"]), reduce_only=True)
        self.roles[o.client_order_id.value] = ("EXIT", pair)
        self.ledger.log("EXIT_SUBMITTED", self.now_ns, pair=pair, reason=reason, family=self.family)
        self.submit_order(o)

    # ------------------------------------------------------------------ entries
    def _maybe_enter(self, pair, done, now):
        if self.family != "F04" and (pair in self.open or pair in self.pending):
            return   # one position per pair: nothing to evaluate while it is busy
        intents = self.model.entry(self, pair, done)
        if not intents or now < self.trade_from_ns:     # warm-up replay after a restart: state advances, nothing trades
            return
        ok, why = self.ledger.entries_allowed(now)
        if not ok:
            for it in intents:
                self._reject(why, it)
            return
        if entry_blocked(now):
            for it in intents:
                self._reject("SESSION_NO_ENTRY", it)
            return
        for it in intents:
            if it.pair in self.open or it.pair in self.pending:
                self._reject("POSITION_OPEN", it)
                return
        n_now = len(self.open) + len(self.pending)
        if n_now + len(intents) > self._max_pos:
            for it in intents:
                self._reject("MAX_POSITIONS", it)
            return
        equity = self.ledger.initial if self.research else self.ledger.equity
        open_risk = sum(t["planned_risk_eur"] for t in self.open.values()) + sum(t["planned_risk_eur"] for t in self.pending.values())
        new_risk = sum(it.risk_fraction * equity for it in intents)
        if open_risk + new_risk > self._max_open_risk * equity * (1 + 1e-9):
            for it in intents:
                self._reject("COMBINED_RISK", it)
            return
        plans = []
        for it in intents:
            q = self._quote(it.pair)
            if q is None:
                self._reject("NO_QUOTE", it)
                return
            bid, ask = float(q.bid_price), float(q.ask_price)
            pip = I.PIP[it.pair]
            fx = self.eur_per_quote(it.pair[3:])
            if fx is None:
                self._reject("NO_FX_RATE", it)
                return
            risk_eur = it.risk_fraction * equity
            units, eff, why = position_size(risk_eur, it.stop_distance, ask - bid, self.sc["slippage_pips_stop"] * pip, fx)
            if units == 0:
                self._reject(why or "SIZE", it, stop_distance=it.stop_distance)
                return
            price = (bid + ask) / 2.0
            # `ask - bid` already contains the scenario's spread widening AND the market slippage (both are baked into
            # the quote stream), so no separate slippage term is added here (it would double count).
            cost = expected_round_trip_cost_eur(units, price, ask - bid, 0.0,
                                                self.sc["commission_rate_per_side"], fx)
            allowed, frac = cost_gate(cost, risk_eur)
            if not allowed:
                self._reject("COST_GATE", it, cost_fraction=round(frac, 4))
                return
            plans.append((it, units, eff, risk_eur, fx, ask - bid, bid, ask))
        # all-or-nothing group: every leg passed every gate -> send
        for it, units, eff, risk_eur, fx, spread, bid, ask in plans:
            inst = self.cache.instrument(I.instrument_id(it.pair))
            side = OrderSide.BUY if it.direction > 0 else OrderSide.SELL
            o = self.order_factory.market(inst.id, side, inst.make_qty(units))
            self.roles[o.client_order_id.value] = ("ENTRY", it.pair)
            self.pending[it.pair] = {
                "intent": it, "dir": it.direction, "units": units, "planned_risk_eur": risk_eur, "eff_stop": eff,
                "stop_distance": it.stop_distance, "signal_close": now, "deadline": now + it.hold_minutes * NS_MIN,
                "tf": it.time_exit_tf, "fx_entry": fx, "spread_at_signal": spread, "group": it.group,
                "actual_risk_eur": units * eff * fx, "exit_sent": False, "exit_reason": None,
            }
            self.ledger.log("ENTRY_SUBMITTED", now, pair=it.pair, family=self.family, dir=it.direction, units=units,
                            risk_eur=round(risk_eur, 4), reason=it.reason, meta=it.meta, group=it.group)
            self.submit_order(o)

    # ------------------------------------------------------------------ order events
    @guarded
    def on_order_filled(self, ev):
        role, pair = self.roles.get(ev.client_order_id.value, (None, None))
        if role is None:
            return
        if role == "ENTRY":
            p = self.pending.pop(pair, None)
            if p is None:
                return
            p["entry_px"], p["entry_ts"] = float(ev.last_px), ev.ts_event
            q = self._quote(pair)
            p["entry_spread"] = (float(q.ask_price) - float(q.bid_price)) if q is not None else p["spread_at_signal"]
            p["entry_comm_quote"] = money_value(ev.commission)
            self.open[pair] = p
            inst = self.cache.instrument(I.instrument_id(pair))
            d = p["dir"]
            stop_px = p["entry_px"] - d * p["stop_distance"]
            p["stop_px"] = stop_px
            side = OrderSide.SELL if d > 0 else OrderSide.BUY
            so = self.order_factory.stop_market(inst.id, side, inst.make_qty(p["units"]), inst.make_price(stop_px),
                                                TriggerType.DEFAULT, reduce_only=True)
            self.roles[so.client_order_id.value] = ("STOP", pair)
            self.ledger.log("ENTRY_FILLED", ev.ts_event, pair=pair, px=p["entry_px"], units=p["units"], stop_px=stop_px)
            self.submit_order(so)
        elif role in ("STOP", "EXIT"):
            self._finalize(role, pair, ev)

    def _finalize(self, role, pair, ev):
        tr = self.open.pop(pair, None)
        if tr is None:
            return
        d, units, pip = tr["dir"], tr["units"], I.PIP[pair]
        eng_exit = float(ev.last_px)
        comm_exit_engine = money_value(ev.commission)
        if role == "STOP":
            off_s = (ev.ts_event % NS_MIN) / 1e9
            sl_stop, sl_mkt = self.sc["slippage_pips_stop"] * pip, self.sc["slippage_pips_market"] * pip
            if abs(off_s - 1.0) < 1e-6:        # triggered by the minute-open quote: a gap through the stop -> engine fill, plus the extra stop slippage
                exit_px = eng_exit - d * max(sl_stop - sl_mkt, 0.0)
            else:                              # crossed intrabar -> booked at the stop price less stop slippage
                exit_px = tr["stop_px"] - d * sl_stop
            comm_exit = self.sc["commission_rate_per_side"] * units * exit_px
            reason = "STOP"
        else:
            exit_px, comm_exit, reason = eng_exit, comm_exit_engine, tr["exit_reason"]
            self.cancel_all_orders(I.instrument_id(pair))
        fx = self.eur_per_quote(pair[3:]) or tr["fx_entry"]
        q = self._quote(pair)
        exit_spread = (float(q.ask_price) - float(q.bid_price)) if q is not None else tr["entry_spread"]
        # mid-equivalent prices: a long enters at the ask / exits at the bid, a short the reverse
        entry_mid = tr["entry_px"] - d * tr["entry_spread"] / 2.0
        exit_mid = exit_px + d * exit_spread / 2.0
        gross_mid_eur = d * (exit_mid - entry_mid) * units * fx
        gross_q = d * (exit_px - tr["entry_px"]) * units
        net_q = gross_q - tr["entry_comm_quote"] - comm_exit
        eng_net_q = d * (eng_exit - tr["entry_px"]) * units - tr["entry_comm_quote"] - comm_exit_engine
        net_eur, gross_eur = net_q * fx, gross_q * fx
        self.ledger_minus_engine_eur += (net_q - eng_net_q) * fx
        r_mult = net_eur / tr["actual_risk_eur"] if tr["actual_risk_eur"] > 0 else 0.0
        self.ledger.book_trade(ev.ts_event, {
            "family": self.family, "pair": pair, "dir": d, "units": units, "entry_ts_ns": tr["entry_ts"],
            "exit_ts_ns": ev.ts_event, "signal_close_ns": tr["signal_close"], "entry_px": tr["entry_px"],
            "exit_px": exit_px, "engine_exit_px": eng_exit, "exit_reason": reason, "signal": tr["intent"].reason,
            "gross_eur": gross_mid_eur, "gross_fill_eur": gross_eur, "net_eur": net_eur, "cost_eur": gross_mid_eur - net_eur,
            "spread_slippage_cost_eur": gross_mid_eur - gross_eur, "commission_eur": gross_eur - net_eur, "planned_risk_eur": tr["planned_risk_eur"],
            "actual_risk_eur": tr["actual_risk_eur"], "stop_distance": tr["stop_distance"], "r_net": r_mult, "spread_pips_at_signal": tr["spread_at_signal"] / pip,
            "group": tr["group"], "meta": tr["intent"].meta,
        })

    def _entry_failed(self, ev, why):
        role, pair = self.roles.get(ev.client_order_id.value, (None, None))
        if role == "ENTRY":
            p = self.pending.pop(pair, None)
            self._reject(f"ENGINE_{why}", p["intent"] if p else None, detail=str(getattr(ev, "reason", ""))[:160])
            if p and p.get("group"):  # a broken pair-trade leaves a naked leg: flatten the sibling immediately
                for q, t in list(self.open.items()):
                    if t.get("group") == p["group"] and not t["exit_sent"]:
                        self._send_exit(q, "GROUP_BROKEN")
        elif role == "STOP":
            tr = self.open.get(pair)
            if tr and not tr["exit_sent"]:
                self._send_exit(pair, "STOP_REJECTED")
        elif role == "EXIT":
            self.ledger.log("EXIT_FAILED", self.now_ns, pair=pair, why=why, detail=str(getattr(ev, "reason", ""))[:160])

    @guarded
    def on_order_denied(self, ev):
        self._entry_failed(ev, "DENIED")

    @guarded
    def on_order_rejected(self, ev):
        self._entry_failed(ev, "REJECTED")

    def on_stop(self):
        self.ledger.log("RUN_END", self.now_ns, open_positions=list(self.open), equity=self.ledger.equity)
        self.ledger.close()
