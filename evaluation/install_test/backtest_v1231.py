"""v1.231.0 smoke test: Dukascopy EURUSD quote ticks -> QuoteTick -> BacktestEngine (EMA-cross example strategy).
Purpose is ONLY to prove the ingestion/replay/fill/report path works. The strategy is NOT a candidate, and no
performance conclusion may be drawn from a 2-hour sample."""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dukascopy_loader import load_all_ticks  # noqa: E402

import nautilus_trader  # noqa: E402
from nautilus_trader.backtest.engine import BacktestEngine  # noqa: E402
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig  # noqa: E402
from nautilus_trader.examples.strategies.ema_cross import EMACross, EMACrossConfig  # noqa: E402
from nautilus_trader.model.currencies import USD  # noqa: E402
from nautilus_trader.model.data import BarType, QuoteTick  # noqa: E402
from nautilus_trader.model.enums import AccountType, OmsType  # noqa: E402
from nautilus_trader.model.identifiers import TraderId, Venue  # noqa: E402
from nautilus_trader.model.objects import Money, Price, Quantity  # noqa: E402
from nautilus_trader.test_kit.providers import TestInstrumentProvider  # noqa: E402

SIM = Venue("SIM")
instrument = TestInstrumentProvider.default_fx_ccy("EUR/USD", SIM)
raw = load_all_ticks()
ticks = [
    QuoteTick(
        instrument_id=instrument.id,
        bid_price=Price(r["bid"], 5), ask_price=Price(r["ask"], 5),
        bid_size=Quantity.from_int(1_000_000), ask_size=Quantity.from_int(1_000_000),
        ts_event=r["ts_ms"] * 1_000_000, ts_init=r["ts_ms"] * 1_000_000,
    )
    for r in raw
]

engine = BacktestEngine(config=BacktestEngineConfig(
    trader_id=TraderId("EVAL-001"), logging=LoggingConfig(log_level="ERROR")))
engine.add_venue(venue=SIM, oms_type=OmsType.HEDGING, account_type=AccountType.MARGIN, base_currency=USD,
                 starting_balances=[Money(1_000_000, USD)])
engine.add_instrument(instrument)
engine.add_data(ticks)
engine.add_strategy(EMACross(EMACrossConfig(
    instrument_id=instrument.id, bar_type=BarType.from_str(f"{instrument.id}-1-MINUTE-BID-INTERNAL"),
    trade_size=Decimal(100_000), fast_ema_period=3, slow_ema_period=8)))
engine.run()

result = {
    "version": nautilus_trader.__version__, "ticks_loaded": len(ticks),
    "orders": len(engine.cache.orders()), "positions": len(engine.cache.positions()),
    "iterations": engine.iteration,
    "account_balance_usd": str(engine.portfolio.account(SIM).balance_total(USD)),
}
print(json.dumps(result, indent=2))
(Path(__file__).parent / "result_v1231.json").write_text(json.dumps(result, indent=2))
engine.dispose()
