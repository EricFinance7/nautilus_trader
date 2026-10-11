# Isolated install and Dukascopy replay test

Purpose: prove (or disprove) that NautilusTrader can be installed on this Windows machine and can replay the Trading
Intelligence Engine's own Dukascopy tick samples. **Smoke test only. No performance conclusion may be drawn from it.**
No broker connection, no orders, no live data. The source data is read-only; nothing is written to it.

## Environment (recorded 2026-10-11)

- Windows 11, Python 3.12.10, no Rust toolchain installed (wheels only, nothing compiled).
- Two throwaway virtualenvs created **outside both projects**: `E:\Projects\nautilus-eval-sandbox\v1231` and
  `...\v2rc6`. Delete the whole `nautilus-eval-sandbox` folder to remove them; nothing else depends on it.
- Never install v1 and v2 in the same environment (both import as `nautilus_trader`).

```
python -m venv v1231 && v1231\Scripts\python -m pip install nautilus_trader==1.231.0
python -m venv v2rc6 && v2rc6\Scripts\python -m pip install --pre nautilus_trader==2.0.0rc6
```

## Running

`TIE_DUKASCOPY_TICK_DIR` must point at a directory of hourly Dukascopy jetta tick JSON files (set it to your own
path; the loader refuses to run without it).

```
set TIE_DUKASCOPY_TICK_DIR=<path to .../dukascopy/EURUSD/tick>
v1231\Scripts\python evaluation\install_test\backtest_v1231.py
v2rc6\Scripts\python evaluation\install_test\backtest_v2rc6.py
v2rc6\Scripts\python evaluation\install_test\catalog_roundtrip_v2rc6.py
v1231\Scripts\python evaluation\install_test\crossed_quote_probe.py
v2rc6\Scripts\python evaluation\install_test\crossed_quote_probe.py
```

## Results

| Script | v1.231.0 | v2.0.0rc6 |
|---|---|---|
| install + import | OK | OK |
| `backtest_*`: 7,459 EURUSD quote ticks (2 h, 2026-07-10 12:00–14:00 UTC) → 1-min internal bars → EMA strategy | 38 orders, 19 positions, final balance 999,734.21 USD | 36 orders, 18 positions |
| `catalog_roundtrip_v2rc6.py` | n/a | 7,459 written / 7,459 read back, exact bid/ask/timestamp match, 10.4 bytes per tick |
| `crossed_quote_probe.py` (bid > ask) | constructed and replayed | constructed and replayed |

Order counts differ because the two strategies were written independently for each API; they are not comparable.
Recorded outputs: `result_v1231.json`, `result_v2rc6.json`.

## Known gaps in this test

- Dukascopy volumes are not mapped to order-book size; a constant 1,000,000 was used for bid/ask size.
- The sample contained zero crossed quotes, so matching-engine behavior against a crossed book is untested (only
  construction and replay were).
- Instrument specs are the testkit's generic FX default, not IBKR contract details.
- No fee/spread/slippage calibration; v1 used the default fee model, v2 used an explicit zero-fee model.
