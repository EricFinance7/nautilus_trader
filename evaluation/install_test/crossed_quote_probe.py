"""Does NautilusTrader construct/replay a crossed (bid>ask) FX quote? Dukascopy audit found ~10.6% of raw ticks cross momentarily."""
import sys
import nautilus_trader
v = nautilus_trader.__version__
V1 = v.startswith("1.")
if V1:
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.data import QuoteTick
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.identifiers import Venue
    from nautilus_trader.model.objects import Money, Price, Quantity
    from nautilus_trader.test_kit.providers import TestInstrumentProvider
    cfg = BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"))
    kw = {}
else:
    from decimal import Decimal
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig
    from nautilus_trader.execution import MakerTakerFeeModel
    from nautilus_trader.model import AccountType, Currency, Money, OmsType, Price, Quantity, QuoteTick, Venue
    from nautilus_trader.testkit.providers import TestInstrumentProvider
    USD = Currency.from_str("USD")
    cfg = BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR))
    kw = {"fee_model": MakerTakerFeeModel(maker_rate=Decimal("0"), taker_rate=Decimal("0"))}

SIM = Venue("SIM")
inst = TestInstrumentProvider.default_fx_ccy("EUR/USD", SIM)
def q(b, a, ms):
    ns = ms * 1_000_000
    return QuoteTick(inst.id, Price(b, 5), Price(a, 5), Quantity.from_int(1_000_000), Quantity.from_int(1_000_000), ns, ns)
out = {"version": v}
try:
    ticks = [q(1.14311, 1.14313, 1000), q(1.14315, 1.14312, 2000), q(1.14310, 1.14314, 3000)]  # middle one crossed
    out["construct_crossed"] = "accepted"
    e = BacktestEngine(config=cfg)
    e.add_venue(venue=SIM, oms_type=OmsType.HEDGING, account_type=AccountType.MARGIN, base_currency=USD,
                starting_balances=[Money(1_000_000, USD)], **kw)
    e.add_instrument(inst); e.add_data(ticks); e.run()
    out["replay_crossed"] = "completed"
except Exception as ex:
    out["error"] = f"{type(ex).__name__}: {ex}"
print(out)
