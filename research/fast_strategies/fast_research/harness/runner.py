"""Builds one independent NautilusTrader BacktestEngine per (family, cost scenario) and runs it over a time window.

Each arm gets its OWN engine, account (EUR 500) and ledger, so strategies are never combined. Quotes are generated
deterministically from the normalized candles (quotes.py), loaded week by week through the engine's streaming mode.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from .. import specs as S
from . import instruments as I
from . import quotes as Q
from .fast_strategy import FastConfig, FastStrategy

WEEK_NS = 7 * 86400 * 10**9
SAT_OFFSET_NS = 2 * 86400 * 10**9   # the epoch is a Thursday; Saturday 00:00 UTC is epoch + 2 days


def iso_to_ns(s: str) -> int:
    return int(pd.Timestamp(s).value)


def load_minutes(minute_dir: Path, pair: str) -> pd.DataFrame:
    return pd.read_parquet(Path(minute_dir) / f"{pair}.parquet")


def build_engine(harness: dict, scenario: str, tag: int):
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig
    from nautilus_trader.data import DataEngineConfig
    from nautilus_trader.execution import MakerTakerFeeModel, StaticLatencyModel
    from nautilus_trader.model import AccountType, Currency, Money, OmsType, StandardMarginModel, TraderId

    sc = harness["costs"]["scenarios"][scenario]
    et = harness["execution_timing"]
    latency_s = et["latency_base_seconds"] if sc["latency"] == "base" else et["latency_adverse_seconds"]
    eur = Currency.from_str("EUR")
    engine = BacktestEngine(config=BacktestEngineConfig(
        trader_id=TraderId(f"FAST-{tag:03d}"), logging=LoggerConfig(stdout_level=LogLevel.ERROR),
        data_engine=DataEngineConfig(time_bars_build_with_no_updates=False)))
    engine.add_venue(
        venue=I.VENUE, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, base_currency=eur,
        starting_balances=[Money(harness["capital_and_risk"]["initial_virtual_equity_eur"], eur)],
        default_leverage=Decimal(1), margin_model=StandardMarginModel(),
        fee_model=MakerTakerFeeModel(maker_rate=Decimal("0"), taker_rate=Decimal(str(sc["commission_rate_per_side"]))),
        latency_model=StaticLatencyModel(base_latency_nanos=int(round(latency_s * 1e9))), bar_execution=False)
    return engine


def run_arm(family: str, scenario: str, minute_dir: Path, start: str, end: str, tag: int = 1, pairs=None,
            journal_path=None, harness=None, mode="governed", frames=None, model_factory=None, spec=None, tick_dir=None, trade_from_ns=0, restore_journal=None) -> dict:
    """Run one strategy arm. `start`/`end` are ISO UTC timestamps (end exclusive)."""
    harness = harness or S.HARNESS
    pairs = list(pairs or harness["universe"])
    sc = harness["costs"]["scenarios"][scenario]
    fam_key = "F07" if family == "F07R" else family
    spec = spec or S.family_spec(fam_key)
    t0 = time.time()
    engine = build_engine(harness, scenario, tag)
    t_start, t_end = iso_to_ns(start), iso_to_ns(end)

    per_pair = {}
    for p in pairs:
        if tick_dir is not None:      # REAL ticks (fidelity tier): every tick is a quote
            from ..data import ticks_dataset as TD
            parts = [pd.read_parquet(f) for f in sorted((Path(tick_dir) / p).glob("*.parquet"))]
            tdf = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["ts", "bid", "ask"])
            _t = Q.ts_ns(tdf["ts"])
            tdf = tdf[(_t >= t_start) & (_t < t_end)]
            ts, b, a = TD.tick_quote_arrays(tdf, I.PIP[p], I.PRICE_PRECISION[p], sc["spread_multiplier"], sc["slippage_pips_market"])
        else:
            df = frames[p] if frames is not None else load_minutes(minute_dir, p)
            _t = Q.ts_ns(df["ts"])
            df = df[(_t >= t_start) & (_t < t_end)]
            ts, b, a = Q.quote_arrays(df, I.PIP[p], I.PRICE_PRECISION[p], sc["spread_multiplier"], sc["slippage_pips_market"])
        inst = I.make_instrument(p)
        engine.add_instrument(inst)
        per_pair[p] = (inst, ts, b, a)

    strat = FastStrategy(FastConfig(family=family, family_spec=spec, harness=harness, scenario=scenario,
                                    journal_path=journal_path, mode=mode, model_factory=model_factory,
                                    trade_from_ns=trade_from_ns, restore_journal=restore_journal))
    engine.add_strategy(strat)

    all_weeks = sorted({int(w) for p in pairs for w in np.unique((per_pair[p][1] - SAT_OFFSET_NS) // WEEK_NS)})
    n_quotes = 0
    for w in all_weeks:
        batch = []
        for p in pairs:
            inst, ts, b, a = per_pair[p]
            wk = (ts - SAT_OFFSET_NS) // WEEK_NS
            m = wk == w
            if m.any():
                batch += Q.to_quote_ticks(inst.id, ts[m], b[m], a[m], I.PRICE_PRECISION[p])
        n_quotes += len(batch)
        engine.add_data(batch)
        engine.run(streaming=True)
        engine.clear_data()
    engine.end()
    if strat.errors:
        raise RuntimeError("strategy callback raised (the engine only logs these): " + strat.errors[0])

    from nautilus_trader.model import Currency
    bal = engine.portfolio.account(I.VENUE).balance_total(Currency.from_str("EUR"))
    ledger = strat.ledger
    result = {
        "family": family, "scenario": scenario, "mode": mode, "start": start, "end": end, "pairs": pairs,
        "config_hash": S.config_hash(fam_key), "harness_sha256": S.sha256(harness),
        "nautilus_trader": __import__("nautilus_trader").__version__,
        "n_quotes": n_quotes, "n_trades": len(ledger.trades),
        "ledger_equity_eur": ledger.equity, "engine_balance_eur": float(str(bal).split()[0]),
        "ledger_minus_engine_eur": strat.ledger_minus_engine_eur,
        "paused_drawdown": ledger.paused, "reject_counts": strat.reject_counts,
        "open_at_end": list(strat.open), "tf_resets": {p: strat.state[p].resets for p in pairs},
        "seconds": round(time.time() - t0, 1),
        "trades": ledger.trades,
    }
    engine.dispose()
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    ap.add_argument("--scenario", default="base")
    ap.add_argument("--minute-dir", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--pairs", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = run_arm(a.family, a.scenario, Path(a.minute_dir), a.start, a.end, pairs=a.pairs.split(",") if a.pairs else None)
    summary = {k: v for k, v in r.items() if k != "trades"}
    print(json.dumps(summary, indent=2, default=str))
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=2, default=str))
