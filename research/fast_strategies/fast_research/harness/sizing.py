"""Risk-based sizing and the cost gate (pure functions). Equity used is the VIRTUAL realized equity only; nothing here
can read a broker balance.

    effective_stop = stop_distance + spread_now + stop_slippage          (price units)
    units = floor_to_step( risk_eur / (effective_stop * eur_per_quote) )   ; < min units  =>  REJECT (never round up)
    expected_round_trip_cost_eur = units * (spread_now + 2*market_slippage) * eur_per_quote
                                   + 2 * commission_rate * units * price * eur_per_quote
    cost gate: expected_round_trip_cost_eur / risk_eur <= 0.20   (same ceiling as the frozen FRONT-1 policy)
"""
from __future__ import annotations

import math

MIN_UNITS = 1000
STEP_UNITS = 1000
MAX_COST_FRACTION = 0.20


def floor_to_step(units: float, step: int = STEP_UNITS) -> int:
    return int(math.floor(units / step + 1e-12)) * step


def position_size(risk_eur: float, stop_distance: float, spread_now: float, stop_slippage: float,
                  eur_per_quote: float):
    """Returns (units, effective_stop, reason). units == 0 means rejected, with the reason."""
    if not (risk_eur > 0 and stop_distance > 0 and eur_per_quote > 0):
        return 0, None, "INVALID_INPUT"
    eff = stop_distance + max(spread_now, 0.0) + max(stop_slippage, 0.0)
    raw = risk_eur / (eff * eur_per_quote)
    units = floor_to_step(raw)
    if units < MIN_UNITS:
        return 0, eff, "BELOW_MIN_UNITS"
    return units, eff, None


def expected_round_trip_cost_eur(units: int, price: float, spread_now: float, market_slippage: float,
                                 commission_rate_per_side: float, eur_per_quote: float) -> float:
    return (units * (max(spread_now, 0.0) + 2.0 * market_slippage) + 2.0 * commission_rate_per_side * units * price) * eur_per_quote


def cost_gate(cost_eur: float, risk_eur: float, max_fraction: float = MAX_COST_FRACTION):
    """Returns (allowed, fraction)."""
    if risk_eur <= 0:
        return False, float("inf")
    frac = cost_eur / risk_eur
    return frac <= max_fraction, frac
