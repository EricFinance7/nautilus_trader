# FAST strategies F01-F07 on NautilusTrader (research harness)

Branch `research/fast-strategies-and-fx-broker-v1` of `EricFinance7/nautilus_trader`. **Research and simulation only.**
No broker connection, no orders, no live trading, no subscriptions. Large datasets live outside git (`E:\Tradingdata`).

Start with `reports/FINAL_REPORT.md`. Then:

| File | What it is |
|---|---|
| `reports/FINAL_REPORT.md` | Results, evidence classification of every strategy, limitations, GitHub status |
| `results/EVIDENCE_TABLE.md`, `results/evidence_summary.json` | The common-methodology evidence tables and all numbers behind them |
| `reports/DATA_REPORT.md` | What data was acquired and every quality check |
| `reports/BROKER_REPORT.md` | Regulated FX broker comparison and selection |
| `reports/PROSPECTIVE_READINESS.md` | Virtual-trading readiness and the exact missing dependency |
| `reports/COST_AND_RISK_ASSUMPTIONS.md` | Capital model, costs, execution timing, and their provenance |
| `specs/` | Frozen F01-F07 specs, the shared harness spec, and `SPEC_HASHES.json` |

## Layout

```
fast_research/
  specs.py                      frozen specs + config hashes (single source of truth for every parameter)
  data/acquire_dukascopy.py     resumable acquisition from Dukascopy's public .bi5 datafeed
  data/decode.py                .bi5 decoders (candles, ticks)
  data/minute_dataset.py        normalized 1-minute BID/ASK dataset + data-quality checks
  data/ticks_dataset.py         tick normalizer, QC, candle reconstruction, native cross-check
  harness/bars.py               timeframe aggregation (no fabricated bars) + indicators
  harness/session.py            DST-correct sessions, entry block, force-flat
  harness/sizing.py             risk-based sizing and the cost gate
  harness/quotes.py             deterministic candle -> QuoteTick stream with cost scenarios
  harness/instruments.py        the seven CurrencyPair definitions (30:1 margin, 1,000-unit steps)
  harness/ledger.py             append-only virtual ledger + journal (restart recovery)
  harness/fast_strategy.py      the one Nautilus Strategy that runs every model
  harness/runner.py             per-arm engine construction and streaming run
  harness/metrics.py, evidence.py   metrics, episode clustering, cluster bootstrap, pre-registered classifier
  strategies/models.py          pure signal models F01-F07 (+ F07R mirror arm)
  run_evaluation.py, analyze.py orchestration and reporting
tests/                          deterministic tests (see below)
```

## Reproduce

Pinned environment (Python 3.12 on Windows): `nautilus_trader==2.0.0rc6` (no Python dependencies of its own), plus
`numpy==2.5.4 pandas==3.0.6 pyarrow==26.0.0` for data handling. See `requirements.lock.txt`.

```bash
# 1. acquire (resumable; the server throttles to roughly 12 files/min, so this takes hours)
python -m fast_research.data.acquire_dukascopy --root E:\Tradingdata --start 2026-04-01 --end 2026-10-09 --workers 4 --tiers candles
# 2. normalize + quality checks
python -m fast_research.data.minute_dataset --root E:\Tradingdata --start 2026-04-01 --end 2026-10-09 --out-json dataset_qc.json
# 3. tests
python -m unittest discover -s tests -t .           # set TIE_MINUTE_DIR=<normalized minute dir> to include the restart-recovery integration test
# 4. evaluate (DEVELOPMENT + VALIDATION + OUT_OF_SAMPLE only; RESERVED_FORWARD is never read)
python -m fast_research.run_evaluation --minute-dir <normalized minute dir> --out-dir <results dir> --workers 3
python -m fast_research.analyze --runs-dir <results dir> --out-dir results
```

Everything is deterministic: the same normalized data and the same `config_hash` reproduce the same trades.

## Rules the code enforces (and the tests prove)

- No same-bar fill: an order decided on bar N fills at the first quote after decision + 0.5 s, i.e. the next minute's OPEN bid/ask.
- No fabricated data: zero-volume minutes emit no quote; a timeframe bucket whose final minute is missing is dropped; every indicator resets across a gap longer than 60 minutes.
- No look-ahead: a decision at time t is provably unchanged when the future is altered (`tests/test_models.py`).
- Protective stops are native reduce-only STOP_MARKET orders; they are cancelled on any other exit.
- A trade that cannot be sized at or above the 1,000-unit minimum, or whose expected round-trip cost exceeds 20% of its risk, is REJECTED, never rounded up or loosened. `NO_TRADE` is a normal outcome.
- A strategy exception that the engine would only log makes the run fail.

## Tests

`tests/test_core_pure.py` (aggregation, indicators, sessions/DST, sizing, quote generation, ledger, specs), `test_models.py`
(F01-F07 rules, look-ahead invariance, F04 leg mapping, F05 DST), `test_engine_mechanics.py` (real engine: fill timing and
price, stop repricing, time exit, force-flat, session block, cost gate, minimum size), `test_metrics_evidence.py`,
`test_data_layer.py` (bi5 layout, tick QC, candle reconstruction), `test_restart_recovery.py` (a restarted run reproduces the
uninterrupted run exactly).
