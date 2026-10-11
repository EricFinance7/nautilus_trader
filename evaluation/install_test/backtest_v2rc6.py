"""v2.0.0rc6 smoke test: Dukascopy EURUSD quote ticks -> QuoteTick -> BacktestEngine (simple EMA-cross strategy).
Purpose is ONLY to prove the ingestion/replay/fill/report path works. The strategy is NOT a candidate, and no
performance conclusion may be drawn from a 2-hour sample."""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dukascopy_loader import load_all_ticks  # noqa: E402

import nautilus_trader  # noqa: E402
from nautilus_trader.backtest import BacktestEngine  # noqa: E402
from nautilus_trader.common import LogLevel  # noqa: E402
from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig  # noqa: E402
from nautilus_trader.execution import MakerTakerFeeModel  # noqa: E402
from nautilus_trader.indicators import ExponentialMovingAverage  # noqa: E402
from nautilus_trader.model import (  # noqa: E402
    AccountType, BarType, Currency, InstrumentId, Money, OmsType, OrderSide, Price, QuoteTick, Quantity,
    TraderId, Venue,
)
from nautilus_trader.testkit.providers import TestInstrumentProvider  # noqa: E402
from nautilus_trader.trading import Strategy  # noqa: E402


class EmaCfg(StrategyConfig):
    def __init__(self, *, instrument_id, bar_type, trade_size, fast, slow, **_kw):
        super().__init__()
        self.instrument_id, self.bar_type, self.trade_size = instrument_id, bar_type, trade_size
        self.fast, self.slow = fast, slow


class Ema(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self.f, self.s = ExponentialMovingAverage(config.fast), ExponentialMovingAverage(config.slow)

    def on_start(self):
        self.register_indicator_for_bars(self.config.bar_type, self.f)
        self.register_indicator_for_bars(self.config.bar_type, self.s)
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, _bar):
        if not self.indicators_initialized():
            return
        iid = self.config.instrument_id
        want_long = self.f.value >= self.s.value
        if want_long and not self.portfolio.is_net_long(iid):
            if self.portfolio.is_net_short(iid):
                self.close_all_positions(iid)
            self.submit(OrderSide.BUY)
        elif not want_long and not self.portfolio.is_net_short(iid):
            if self.portfolio.is_net_long(iid):
                self.close_all_positions(iid)
            self.submit(OrderSide.SELL)

    def submit(self, side):
        inst = self.cache.instrument(self.config.instrument_id)
        self.submit_order(self.order_factory.market(self.config.instrument_id, side,
                                                    inst.make_qty(self.config.trade_size)))

    def on_stop(self):
        self.close_all_positions(self.config.instrument_id)


SIM = Venue("SIM")
USD = Currency.from_str("USD")
instrument = TestInstrumentProvider.default_fx_ccy("EUR/USD", SIM)
raw = load_all_ticks()
ticks = [
    QuoteTick(instrument.id, Price(r["bid"], 5), Price(r["ask"], 5),
              Quantity.from_int(1_000_000), Quantity.from_int(1_000_000),
              r["ts_ms"] * 1_000_000, r["ts_ms"] * 1_000_000)
    for r in raw
]

engine = BacktestEngine(config=BacktestEngineConfig(
    trader_id=TraderId("EVAL-001"), logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
engine.add_venue(venue=SIM, oms_type=OmsType.HEDGING, account_type=AccountType.MARGIN, base_currency=USD,
                 starting_balances=[Money(1_000_000, USD)],
                 fee_model=MakerTakerFeeModel(maker_rate=Decimal("0"), taker_rate=Decimal("0")))
engine.add_instrument(instrument)
engine.add_data(ticks)
engine.add_strategy(Ema(EmaCfg(instrument_id=instrument.id,
                               bar_type=BarType.from_str(f"{instrument.id}-1-MINUTE-BID-INTERNAL"),
                               trade_size=Decimal(100_000), fast=3, slow=8)))
engine.run()

result = {"version": nautilus_trader.__version__, "ticks_loaded": len(ticks)}
for name, fn in (("orders", lambda: len(engine.cache.orders())), ("positions", lambda: len(engine.cache.positions()))):
    try:
        result[name] = fn()
    except Exception as e:  # report API differences rather than hide them
        result[name] = f"ERR {type(e).__name__}: {e}"
print(json.dumps(result, indent=2))
(Path(__file__).parent / "result_v2rc6.json").write_text(json.dumps(result, indent=2))
engine.dispose()
