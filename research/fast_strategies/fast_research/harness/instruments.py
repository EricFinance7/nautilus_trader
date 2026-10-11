"""Instrument definitions for the seven FAST pairs (venue SIM), EUR 500 retail margin-account assumptions.

Margin: ESMA retail majors 30:1 -> initial margin 1/30, maintenance 1/60 (50% close-out of initial), applied with the
StandardMarginModel so the instrument's fixed percentages are used as-is (no hidden extra leverage).
Order size: 1,000-unit minimum and step (0.01 lot), the smallest size the candidate brokers quote; a computed size
below the minimum is REJECTED upstream, never rounded up.
"""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model import Currency, CurrencyPair, InstrumentId, Price, Quantity, Symbol, Venue

VENUE = Venue("SIM")
PAIRS = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD")
PRICE_PRECISION = {p: (3 if p.endswith("JPY") else 5) for p in PAIRS}
PIP = {p: (0.01 if p.endswith("JPY") else 0.0001) for p in PAIRS}
MIN_UNITS = 1000
STEP_UNITS = 1000
MARGIN_INIT = Decimal(1) / Decimal(30)
MARGIN_MAINT = Decimal(1) / Decimal(60)


def symbol(pair: str) -> str:
    return f"{pair[:3]}/{pair[3:]}"


def instrument_id(pair: str) -> InstrumentId:
    return InstrumentId(Symbol(symbol(pair)), VENUE)


def make_instrument(pair: str) -> CurrencyPair:
    prec = PRICE_PRECISION[pair]
    return CurrencyPair(
        instrument_id=instrument_id(pair), raw_symbol=Symbol(symbol(pair)),
        base_currency=Currency.from_str(pair[:3]), quote_currency=Currency.from_str(pair[3:]),
        price_precision=prec, size_precision=0,
        price_increment=Price(10 ** -prec, prec), size_increment=Quantity.from_int(STEP_UNITS),
        ts_event=0, ts_init=0,
        min_quantity=Quantity.from_int(MIN_UNITS), max_quantity=Quantity.from_int(10_000_000),
        lot_size=Quantity.from_int(STEP_UNITS),
        margin_init=MARGIN_INIT, margin_maint=MARGIN_MAINT,
    )
