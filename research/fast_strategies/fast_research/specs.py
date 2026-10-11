"""FROZEN specifications for F01-F07 (v1 operationalization) and the shared harness.

PROVENANCE AND HONESTY NOTE
---------------------------
In the Trading Intelligence Engine, F01-F07 exist ONLY as concept-level registrations
(`database/migrations/055_fast_strategy_family_registry_v1.sql`, strategy_version `v0_concept`, status DISCOVERED):
"CONCEPT ONLY ... No formula frozen", "No parameter is frozen here". Entry/exit rules, stops, session filters and
thresholds were never defined. This module therefore does three things for every family:
  1. `source_registry`  - quotes the registered hypothesis / candidate horizons / data needs VERBATIM;
  2. `missing_in_source` - lists every requirement the source leaves undefined;
  3. `operationalization` - a BUILDER-PROPOSED v1 completion that is as minimal and textbook-standard as possible,
     uses ONE fixed value per parameter (no sweeps), restricts horizons to the registry's candidate sets, and was
     fixed BEFORE any VALIDATION / OUT_OF_SAMPLE / RESERVED_FORWARD data was examined. Each choice is logged in
     `gap_fill_decisions` with its rationale so the operator can ratify or replace it (a replacement is a NEW
     strategy_version, never a silent edit).
No parameter here was derived from backtest results. `config_hash` = sha256 of the canonical JSON of
(family spec + shared harness spec); it identifies exactly what was run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SPEC_VERSION = "v1_builder_proposed"

# --------------------------------------------------------------------------------------------------------------
# Shared harness specification (identical for all seven families)
# --------------------------------------------------------------------------------------------------------------
HARNESS = {
    "harness_version": "fast_harness_v1",
    "nautilus_trader": "2.0.0rc6",
    "universe": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"],
    "data": {
        "provider": "dukascopy_datafeed_bi5_http",
        "window_start_utc": "2026-04-01",
        "window_end_utc": "2026-10-09",
        "base_series": "native 1-minute BID and ASK candles (bar-open, left-labeled, UTC)",
        "valid_minute_rule": "bid_volume > 0 or ask_volume > 0; zero-volume minutes carry no information and are never replayed or fabricated",
        "session_reset_gap_minutes": 60,
        "session_reset_rule": "all indicator state resets when consecutive valid minutes are > 60 min apart (weekend / outage); no look-back spans a gap",
        "signal_price": "MID OHLC = (bid+ask)/2 at each of open/high/low/close",
        "tf_aggregation": "UTC-aligned, left-closed, left-labeled; a bar completes only when its final minute is received; empty buckets produce no bar",
    },
    "partitions": {
        "method": "55/20/15/10 calendar-fraction split, as in fast_fx_v2_partitions.json, fixed from the date range before any returns were computed",
        "DEVELOPMENT": ["2026-04-01T00:00:00Z", "2026-07-15T14:24:00Z"],
        "VALIDATION": ["2026-07-15T14:24:00Z", "2026-08-23T00:00:00Z"],
        "OUT_OF_SAMPLE": ["2026-08-23T00:00:00Z", "2026-09-20T19:12:00Z"],
        "RESERVED_FORWARD": ["2026-09-20T19:12:00Z", "2026-10-10T00:00:00Z"],
        "boundary_arithmetic": "192 days from 2026-04-01T00:00Z to 2026-10-10T00:00Z; cumulative fractions 0.55 / 0.75 / 0.90 -> +105.6 d / +144 d / +172.8 d",
        "rule": "Code correctness may be debugged on DEVELOPMENT only. VALIDATION/OUT_OF_SAMPLE/RESERVED_FORWARD results are produced exactly once, after spec hashes are committed. No parameter may change after that without a new strategy_version.",
    },
    "execution_timing": {
        "decision": "on completion of the signal-timeframe bar",
        "order_type_entry": "MARKET",
        "latency_base_seconds": 2,
        "latency_adverse_seconds": 62,
        "synthetic_quote_schedule_seconds_into_minute": {"open": 1, "first_extreme": 20, "second_extreme": 40, "close": 59},
        "intrabar_path": "open -> extreme nearer the open -> other extreme -> close (Nautilus bar_adaptive_high_low_ordering heuristic), applied to bid and ask candles separately",
        "note": "Base fill = first quote after decision+2s = the next minute's OPEN bid/ask. No same-bar-close fill is permitted. Adverse = one bar later.",
        "protective_stop": "native STOP_MARKET submitted immediately on entry fill (bid-triggered for longs, ask-triggered for shorts)",
        "non_stop_exits": "evaluated only on completed bars, executed as MARKET at the next open (never as resting limit orders)",
    },
    "capital_and_risk": {
        "base_currency": "EUR", "initial_virtual_equity_eur": 500.0, "risk_per_trade_fraction": 0.005,
        "initial_risk_budget_eur": 2.5, "max_simultaneous_positions": 3, "max_combined_open_risk_fraction": 0.015,
        "daily_realized_loss_limit_fraction": 0.02, "daily_boundary": "UTC midnight",
        "drawdown_pause_fraction": 0.10, "drawdown_basis": "peak-to-trough on realized equity; pause = no new entries for the rest of the run",
        "martingale": False, "averaging_down": False, "pyramiding": False,
        "equity_used_for_sizing": "realized virtual equity only; the IBKR paper balance is never read",
        "leverage_model": {"max_leverage": 30, "basis": "ESMA retail majors (30:1)", "margin_init": "1/30", "margin_maint": "1/60 (50% close-out of initial)", "no_hidden_leverage": True},
        "sizing_formula": "units = floor_to_step( risk_eur / ((stop_distance + spread_now + slippage_allowance) * eur_per_quote_unit) )",
        "min_order_units": 1000, "order_step_units": 1000,
        "min_units_rule": "if computed units < min_order_units the trade is REJECTED (never rounded up)",
        "cost_gate": "reject if expected_round_trip_cost_eur / risk_eur > 0.20 (same ceiling as frozen FRONT-1 policy)",
    },
    "session_filters": {
        "session_model": "classify_session (zoneinfo, DST-correct): ASIA / LONDON / NEW_YORK / LONDON_NEW_YORK_OVERLAP / ROLLOVER_LOW_LIQUIDITY / OTHER",
        "no_new_entries": "from 16:30 to 19:00 America/New_York (rollover spread blow-outs; max observed 19.6-30 pip closes)",
        "force_flat": "all positions closed at market at 16:55 America/New_York (also guarantees flat before the Friday close; no swap/rollover modeled)",
    },
    "costs": {
        "provenance": {"spread": "OBSERVED (Dukascopy bid/ask candle values)", "commission": "BROKER_SCHEDULE (Pepperstone GmbH cTrader Razor: USD 3 per side per 100k, Sept 2026 fee schedule, vendor-published; broker NOT yet selected)", "slippage": "CONSERVATIVE_ASSUMPTION"},
        "scenarios": {
            "optimistic": {"spread_multiplier": 1.0, "commission_rate_per_side": 0.000026, "slippage_pips_market": 0.0, "slippage_pips_stop": 0.0, "latency": "base"},
            "base": {"spread_multiplier": 1.0, "commission_rate_per_side": 0.000026, "slippage_pips_market": 0.1, "slippage_pips_stop": 0.3, "latency": "base"},
            "adverse": {"spread_multiplier": 1.5, "commission_rate_per_side": 0.000040, "slippage_pips_market": 0.3, "slippage_pips_stop": 0.6, "latency": "adverse"},
        },
        "evidence_scenario": "base",
        "commission_rate_note": "fraction of notional in quote currency; 0.000026 ~= USD 3 per 100k EUR notional at EURUSD ~1.17",
        "carry": "not modeled (positions never held across the 16:55 New York force-flat); stated limitation",
    },
    "evidence_rules": {
        "unit": "net result in R = net P&L (EUR) / planned risk (EUR); sizing path effects are removed",
        "episodes": "trades are grouped into independent episodes: a trade joins an open episode if its entry is within 60 min of the episode's latest entry AND shares a currency exposure with the same net direction; otherwise it starts a new episode",
        "bootstrap": {"method": "episode-level (cluster) bootstrap", "resamples": 5000, "seed": 20261011, "ci": 0.95},
        "INSUFFICIENT_DATA": "unique episodes (DEV+VAL+OOS) < 30 OR unique episodes in VALIDATION+OUT_OF_SAMPLE < 15",
        "NEGATIVE_EVIDENCE": "sufficient data AND base-cost pooled VAL+OOS mean net R < 0 AND (bootstrap CI upper bound < 0 OR mean net R < 0 in all of DEV, VAL, OOS)",
        "PROMISING_RESEARCH": "sufficient data AND base-cost mean net R > 0 in each of DEV, VAL and OOS AND pooled VAL+OOS bootstrap CI lower bound > 0 AND pooled VAL+OOS profit factor >= 1.2 AND positive mean net R in >= 4 of 7 pairs",
        "SHADOW_FORWARD_ELIGIBLE": "PROMISING_RESEARCH AND adverse-cost pooled VAL+OOS mean net R > 0 AND max drawdown < 10% AND >= 100 unique episodes AND >= 30 unique episodes in OOS AND positive mean net R in >= 2 of 3 volatility terciles",
        "MIXED_EVIDENCE": "sufficient data that satisfies neither NEGATIVE_EVIDENCE nor PROMISING_RESEARCH",
        "multiplicity": "eight strategy arms are tested (F01-F07 plus the pre-declared F07 reversal mirror); no multiple-testing correction is applied, which makes any positive finding weaker, not stronger",
        "win_rate_target": "none; no target (including 85%) is forced",
    },
    "common_definitions": {
        "TR": "max(H-L, |H-C_prev|, |L-C_prev|) on MID bars of the stated timeframe",
        "ATR_n": "simple mean of the last n true ranges (needs n+1 contiguous bars), as in the FRONT-1 stop calculation",
        "z_move_k": "(C_t - C_{t-k}) / ATR_14 on the stated timeframe",
        "stop_distance": "stop_multiple * ATR_14 of the stated stop timeframe, applied to the actual entry fill price",
    },
}

# --------------------------------------------------------------------------------------------------------------
# Verbatim registry text (database/migrations/055_fast_strategy_family_registry_v1.sql in the Trading Intelligence Engine)
# --------------------------------------------------------------------------------------------------------------
_COMMON_MISSING = [
    "formula / entry condition", "exit condition", "stop-loss methodology", "numeric thresholds and lookbacks",
    "position-sizing rule (supplied by the EUR 500 capital model of this task)", "session filters",
    "single outcome horizon (registry lists candidate sets only)", "cost model (supplied by the shared harness)",
]

FAMILIES = {
    "F01": {
        "strategy_id": "f01_intraday_trend_continuation", "registry_version": "v0_concept", "name": "FAST -- Intraday Trend Continuation",
        "source_registry": {
            "original_signal_definition": "CONCEPT ONLY: an established short-horizon directional move continues over the near-term outcome horizon (momentum persistence at intraday scale). No formula frozen.",
            "candidate_observation_frequency": "1m/5m base, decision frequency TBD",
            "candidate_outcome_horizons": "5m/15m/30m/1h/2h/4h, subset chosen at preregistration",
            "required_data": "1-minute canonical FX bars (recommended base frequency), derived 5m/15m/30m/1h.",
            "intended_horizon": "5m-4h (multiple candidate horizons, none frozen)",
            "constraint": "must NOT reuse R05's methodology or parameters",
        },
        "missing_in_source": _COMMON_MISSING,
        "operationalization": {
            "signal_timeframe": "15m", "lookback_bars": 4, "move_threshold_atr": 1.5, "atr_n": 14,
            "rule": "LONG if z_move_4 >= +1.5 AND the last completed 15m bar closed up; SHORT mirror. z_move_4 = (C_t - C_{t-4}) / ATR14(15m).",
            "entry": "market at next-open after bar completion", "stop_timeframe": "15m", "stop_multiple": 1.5,
            "exits": ["stop", "time exit at the first 15m boundary >= entry fill + 60 min", "force_flat"],
            "max_holding_minutes": 60, "one_position_per_pair": True,
        },
        "gap_fill_decisions": [
            "outcome horizon 60 min (member of the registry set) and 15m signal timeframe (derived from the 1m base)",
            "'established move' = 4 completed 15m bars (1h) of net displacement >= 1.5 ATR; 1.5 chosen as the same multiple used by FRONT-1's frozen stop policy, not tuned",
            "last-bar confirmation added so the signal is not taken on a bar that already reverses the move",
        ],
    },
    "F02": {
        "strategy_id": "f02_intraday_mean_reversion", "registry_version": "v0_concept", "name": "FAST -- Intraday Mean Reversion",
        "source_registry": {
            "original_signal_definition": "CONCEPT ONLY: a short-horizon extreme deviation from a local reference level tends to partially revert. No formula frozen.",
            "candidate_outcome_horizons": "5m/15m/30m/1h", "required_data": "1-minute canonical FX bars, derived coarser frequencies.",
            "intended_horizon": "5m-1h (multiple candidate horizons, none frozen)",
            "note": "the natural counterpart to F01",
        },
        "missing_in_source": _COMMON_MISSING + ["definition of the 'local reference level'", "definition of 'extreme' and of 'partial' reversion"],
        "operationalization": {
            "signal_timeframe": "5m", "reference": "SMA of the last 12 completed 5m closes (1h)", "dispersion": "population std of those 12 closes",
            "entry_z": 2.0, "exit_z": 0.5, "atr_n": 14,
            "rule": "z = (C_t - SMA12) / std12. SHORT if z >= +2.0, LONG if z <= -2.0 (fade). Skip if std12 == 0.",
            "entry": "market at next-open", "stop_timeframe": "5m", "stop_multiple": 1.5,
            "exits": ["stop", "partial reversion: on a completed 5m bar with |z| <= 0.5 exit at next open", "time exit at the first 5m boundary >= entry fill + 30 min", "force_flat"],
            "max_holding_minutes": 30, "one_position_per_pair": True,
        },
        "gap_fill_decisions": [
            "local reference = 1h simple mean; 'extreme' = |z| >= 2.0 (standard); 'partial reversion' = back inside 0.5 sigma (about three quarters of the way back)",
            "outcome horizon 30 min (member of the registry set)",
        ],
    },
    "F03": {
        "strategy_id": "f03_volatility_breakout_expansion", "registry_version": "v0_concept", "name": "FAST -- Volatility Breakout / Expansion",
        "source_registry": {
            "original_signal_definition": "CONCEPT ONLY: a period of compressed range/volatility is followed by directional expansion. No formula frozen.",
            "candidate_outcome_horizons": "15m/30m/1h/2h", "required_data": "1-minute canonical FX bars for range/ATR construction, derived coarser frequencies.",
            "intended_horizon": "15m-2h (multiple candidate horizons, none frozen)", "note": "requires BAR_BASED range/ATR",
        },
        "missing_in_source": _COMMON_MISSING + ["definition of 'compressed'", "definition of 'expansion' / breakout trigger"],
        "operationalization": {
            "signal_timeframe": "15m", "compression_short_atr": 8, "compression_long_atr": 48, "compression_ratio_max": 0.7, "range_bars": 8, "atr_n": 14,
            "rule": "At the prior bar t-1, compressed if ATR8/ATR48 <= 0.7. At bar t: LONG if C_t > max(H over bars t-8..t-1); SHORT if C_t < min(L over bars t-8..t-1).",
            "entry": "market at next-open", "stop_timeframe": "15m", "stop_multiple": 1.5,
            "exits": ["stop", "time exit at the first 15m boundary >= entry fill + 120 min", "force_flat"],
            "max_holding_minutes": 120, "one_position_per_pair": True,
        },
        "gap_fill_decisions": [
            "compression = short-term range (ATR8, 2h) at most 70% of the 12h norm (ATR48); breakout = close beyond the prior 2h extreme",
            "outcome horizon 2 h (member of the registry set)",
        ],
    },
    "F04": {
        "strategy_id": "f04_cross_currency_relative_strength", "registry_version": "v0_concept", "name": "FAST -- Cross-Currency Relative Strength",
        "source_registry": {
            "original_signal_definition": "CONCEPT ONLY: rank currencies by short-horizon relative strength and take relative (not outright) positions. No formula frozen.",
            "candidate_outcome_horizons": "TBD", "required_data": "1-minute canonical FX bars across the full candidate universe simultaneously (common-timestamp alignment).",
            "intended_horizon": "15m-1h (multiple candidate horizons, none frozen)",
            "note": "introduces currency-exposure netting considerations more directly than any other FAST family",
        },
        "missing_in_source": _COMMON_MISSING + ["strength measure", "direction (momentum vs reversal) of the relative position", "how a 'relative position' is built from the available pairs"],
        "operationalization": {
            "signal_timeframe": "15m", "lookback_bars": 4, "min_strength_gap_atr": 3.0, "atr_n": 14,
            "rule": "For each pair p: m_p = (C_t - C_{t-4}) / ATR14_p. Non-USD currency strength s_c = +m_p where the currency is the BASE (EUR, GBP, AUD, NZD vs USD) and -m_p where it is the QUOTE (JPY, CHF, CAD in USDJPY, USDCHF, USDCAD). If max(s) - min(s) >= 3.0: BUY the strongest currency vs USD and SELL the weakest currency vs USD (USD-neutral relative position, two pair legs).",
            "entry": "both legs market at next-open; all-or-nothing (if either leg fails any gate neither is sent)",
            "leg_risk_fraction": 0.0025, "stop_timeframe": "15m", "stop_multiple": 1.5,
            "exits": ["either leg's stop closes only that leg's position (the other continues to its own exit)", "time exit of both legs at the first 15m boundary >= entry fill + 60 min", "force_flat"],
            "max_holding_minutes": 60, "one_position_per_pair": True,
        },
        "gap_fill_decisions": [
            "strength = ATR-normalised 1h displacement vs USD; momentum direction chosen because 'relative strength' conventionally means long strong / short weak (the registry does not state the direction)",
            "relative position = two USD-pair legs, each 0.25% risk, so the pair-trade totals the standard 0.5%",
        ],
    },
    "F05": {
        "strategy_id": "f05_session_opening_range_behavior", "registry_version": "v0_concept", "name": "FAST -- Session / Opening-Range Behavior",
        "source_registry": {
            "original_signal_definition": "CONCEPT ONLY: price behavior in a defined window after a session open (e.g. London open, NY open) has a distinct distribution from the general base rate. No formula frozen.",
            "candidate_outcome_horizons": "15m/30m/1h following the session-open window", "required_data": "1-minute canonical FX bars plus session labels.",
            "intended_horizon": "15m-1h (multiple candidate horizons, none frozen)",
            "dependency": "python/research_lake/fast_session_model.py for DST-correct session boundaries",
        },
        "missing_in_source": _COMMON_MISSING + ["opening-range window length", "which opens", "trigger within the window", "whether to trade with or against the range"],
        "operationalization": {
            "sessions": [{"name": "LONDON", "tz": "Europe/London", "open_local": "08:00"}, {"name": "NEW_YORK", "tz": "America/New_York", "open_local": "08:00"}],
            "range_window_minutes": 30, "entry_window_minutes": 60, "atr_timeframe": "15m", "atr_n": 14, "range_width_atr_min": 0.5, "range_width_atr_max": 3.0,
            "rule": "Opening range = max/min of MID highs/lows over [open, open+30m). After the window, on the first completed 5m bar within the next 60 min whose close is beyond the range: LONG above, SHORT below. One trade per pair per session-day. Skip if range width is outside [0.5, 3.0] x ATR14(15m).",
            "entry": "market at next-open", "stop": "opposite range boundary, but at least 1.0 x ATR14(15m); skip if the distance exceeds 2.5 x ATR14(15m)",
            "exits": ["stop", "time exit at the first 5m boundary >= entry fill + 60 min", "force_flat"],
            "max_holding_minutes": 60, "one_position_per_pair": True,
        },
        "gap_fill_decisions": [
            "both London and New York opens, 08:00 local (the session model's own desk-hour start); 30 min range window; breakout (trade WITH the range break) because the registry is silent on direction",
            "post-window horizon 60 min (member of the registry set)",
        ],
    },
    "F06": {
        "strategy_id": "f06_multi_timeframe_trend_alignment", "registry_version": "v0_concept", "name": "FAST -- Multi-Timeframe Trend Alignment",
        "source_registry": {
            "original_signal_definition": "CONCEPT ONLY: a signal on a fine timeframe is filtered/confirmed by trend direction on a coarser derived timeframe (e.g. 5m signal aligned with 1h trend). No formula frozen.",
            "candidate_outcome_horizons": "TBD", "required_data": "1-minute canonical FX bars, derived 5m/15m/30m/1h for the coarser confirmation layer.",
            "intended_horizon": "15m-4h (multiple candidate horizons, none frozen)",
            "note": "must keep the signal-vs-holding-horizon distinction explicit",
        },
        "missing_in_source": _COMMON_MISSING + ["the fine-timeframe signal itself", "definition of coarse 'trend direction'"],
        "operationalization": {
            "fine_timeframe": "5m", "coarse_timeframe": "1h", "fine_lookback_bars": 6, "fine_threshold_atr": 1.5, "coarse_sma_bars": 12, "atr_n": 14,
            "rule": "Fine trigger (as F01 but on 5m): LONG candidate if (C_t - C_{t-6}) / ATR14(5m) >= +1.5 and the last 5m bar closed up; SHORT mirror. Coarse trend: sign(C_1h - SMA12(1h closes)) from the last COMPLETED 1h bar. Trade only if coarse trend == trigger direction.",
            "entry": "market at next-open", "stop_timeframe": "5m", "stop_multiple": 1.5,
            "exits": ["stop", "time exit at the first 5m boundary >= entry fill + 60 min", "force_flat"],
            "max_holding_minutes": 60, "one_position_per_pair": True,
        },
        "gap_fill_decisions": [
            "fine signal = the F01 continuation trigger at 5m (the registry gives no fine signal); trend = last completed 1h close vs its 12-hour mean",
            "holding horizon 60 min is deliberately longer than the 30 min fine lookback (signal vs holding horizon kept distinct)",
        ],
    },
    "F07": {
        "strategy_id": "f07_short_horizon_momentum_reversal", "registry_version": "v0_concept", "name": "FAST -- Short-Horizon Momentum / Reversal",
        "source_registry": {
            "original_signal_definition": "CONCEPT ONLY: the shortest-horizon sibling of F01/F02 (e.g. 1m-5m lookback, 5m-15m outcome) -- kept as a distinct family rather than a parameter of F01/F02 because its cost sensitivity and data-quality requirements (Section 6/9) are qualitatively different at this timescale.",
            "candidate_outcome_horizons": "5m/15m", "required_data": "1-minute canonical FX bars (least tolerance for any base-frequency coarser than 1-minute).",
            "intended_horizon": "5m-15m (multiple candidate horizons, none frozen)",
            "note": "most cost-sensitive of the seven families -- explicitly flagged as the one most likely to be rejected once a real cost model is applied",
        },
        "missing_in_source": _COMMON_MISSING + ["whether the arm is momentum or reversal (the name lists both)", "impulse definition"],
        "operationalization": {
            "signal_timeframe": "1m", "lookback_bars": 5, "impulse_threshold_atr": 3.0, "atr_n": 14,
            "rule": "z_move_5 = (C_t - C_{t-5}) / ATR14(1m). MOMENTUM arm (official F07): LONG if z_move_5 >= +3.0 and the last 1m bar closed up; SHORT mirror. Pre-declared companion arm F07R (REVERSAL mirror): identical trigger, opposite direction; reported but not promotable on its own.",
            "entry": "market at next-open", "stop_timeframe": "5m", "stop_multiple": 1.5,
            "exits": ["stop", "time exit at the first 1m boundary >= entry fill + 15 min", "force_flat"],
            "max_holding_minutes": 15, "one_position_per_pair": True,
        },
        "gap_fill_decisions": [
            "momentum arm is the registered F07; reversal arm pre-declared as F07R so both signs of the same trigger are reported (no post-hoc choice of sign)",
            "stop scale uses ATR14 of 5m bars (about 3-4 pips) instead of 1m ATR (about 1 pip), which would sit inside the spread; outcome horizon 15 min (registry set)",
        ],
    },
}


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def family_spec(fid: str) -> dict:
    f = FAMILIES[fid]
    return {"family": fid, "spec_version": SPEC_VERSION, **f}


def config_hash(fid: str) -> str:
    return sha256({"family_spec": family_spec(fid), "harness": HARNESS})


def write_specs(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    hashes = {"spec_version": SPEC_VERSION, "harness_sha256": sha256(HARNESS), "families": {}}
    (out_dir / "HARNESS_v1.json").write_text(json.dumps(HARNESS, indent=2, sort_keys=True), encoding="utf-8")
    for fid in FAMILIES:
        spec = family_spec(fid)
        (out_dir / f"{fid}_{SPEC_VERSION}.json").write_text(json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8")
        hashes["families"][fid] = {"family_spec_sha256": sha256(spec), "config_hash": config_hash(fid)}
    (out_dir / "SPEC_HASHES.json").write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8")
    return hashes


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "specs"
    print(json.dumps(write_specs(out), indent=2))
