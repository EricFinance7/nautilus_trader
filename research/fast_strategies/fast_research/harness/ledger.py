"""Append-only virtual ledger and event journal (mirrors the FRONT-1 design: current equity is always reconstructed
from recorded events, never a free-floating counter).

Realized virtual equity starts at EUR 500 and changes only by booked, cost-adjusted trade results. The daily realized
loss limit (2%, UTC day) blocks new entries for the rest of the UTC day; the 10% peak-to-trough drawdown pause blocks
new entries for the remainder of the run (human review required to resume). Every event is journaled (JSONL, flushed
per event) so a restart can rebuild the ledger exactly: `VirtualLedger.rebuild(path)`.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


class VirtualLedger:
    def __init__(self, initial_eur: float = 500.0, daily_loss_fraction: float = 0.02, drawdown_fraction: float = 0.10,
                 journal_path: str | Path | None = None):
        self.initial = initial_eur
        self.equity = initial_eur
        self.peak = initial_eur
        self.daily_loss_fraction = daily_loss_fraction
        self.drawdown_fraction = drawdown_fraction
        self.day_key: str | None = None
        self.day_start_equity = initial_eur
        self.paused = False
        self.events: list[dict] = []
        self.trades: list[dict] = []
        self._fh = None
        if journal_path:
            p = Path(journal_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(p, "w", encoding="utf-8")

    @staticmethod
    def _day(ts_ns: int) -> str:
        return dt.datetime.fromtimestamp(ts_ns / 1e9, tz=dt.timezone.utc).strftime("%Y-%m-%d")

    def _roll_day(self, ts_ns: int) -> None:
        d = self._day(ts_ns)
        if d != self.day_key:
            self.day_key, self.day_start_equity = d, self.equity

    def log(self, kind: str, ts_ns: int, **data) -> None:
        ev = {"seq": len(self.events), "ts_ns": int(ts_ns), "kind": kind, **data}
        self.events.append(ev)
        if self._fh:
            self._fh.write(json.dumps(ev, sort_keys=True, default=str) + "\n")
            self._fh.flush()

    def book_trade(self, ts_ns: int, trade: dict) -> None:
        """trade must contain net_eur; everything else is carried into the journal."""
        self._roll_day(ts_ns)
        self.equity += trade["net_eur"]
        self.peak = max(self.peak, self.equity)
        if (self.peak - self.equity) / self.peak >= self.drawdown_fraction:
            self.paused = True
        self.trades.append(trade)
        self.log("TRADE_CLOSED", ts_ns, equity_after=self.equity, **trade)

    def entries_allowed(self, ts_ns: int):
        self._roll_day(ts_ns)
        if self.paused:
            return False, "DRAWDOWN_PAUSED"
        if self.equity - self.day_start_equity <= -self.daily_loss_fraction * self.day_start_equity:
            return False, "DAILY_LOSS_HALT"
        return True, None

    @classmethod
    def rebuild(cls, journal_path: str | Path, **kw) -> "VirtualLedger":
        led = cls(**kw)
        for line in Path(journal_path).read_text(encoding="utf-8").splitlines():
            ev = json.loads(line)
            led.events.append(ev)
            if ev["kind"] == "TRADE_CLOSED":
                led._roll_day(ev["ts_ns"])
                led.equity += ev["net_eur"]
                led.peak = max(led.peak, led.equity)
                if (led.peak - led.equity) / led.peak >= led.drawdown_fraction:
                    led.paused = True
                led.trades.append({k: v for k, v in ev.items() if k not in ("seq", "kind", "equity_after", "ts_ns")})
        return led

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None
