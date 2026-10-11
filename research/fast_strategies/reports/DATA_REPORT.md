# Data report: Dukascopy 1-minute BID/ASK candles (and ticks where acquired)

Window requested: 2026-04-01 to 2026-10-09 (Saturdays are not acquired: the market is closed and every candle is a stale zero-volume bar).

## Source and method

- Source: Dukascopy's public historical datafeed (`datafeed.dukascopy.com/datafeed/<PAIR>/<yyyy>/<month0>/<dd>/...`), free, over **plain HTTP**.
  HTTPS (port 443) to that host does not accept connections from this machine; the `jetta.dukascopy.com` JSON API now sits behind an AWS WAF **bot challenge** (HTTP 202, empty body, `x-amzn-waf-action: challenge`). That challenge was **not** circumvented.
- The datafeed throttles: it returned HTTP 503 for roughly a third of requests and settled at about 12 files per minute regardless of the number of workers; the acquisition script retries with jittered exponential backoff and is fully resumable (append-only checkpoint with a SHA-256 per file).
- Candles: native 1-minute BID and ASK candles, bar-open labeled, true UTC. The Trading Intelligence Engine's microstructure validation proved native candles equal tick-derived OHLC bit-for-bit (EURUSD, one full day), so native candles are the primary series.

## Acquisition result

- Candle files: {"OK": 2365}; 21.9 MB compressed on disk.
- Tick files: {"OK": 10}; 0.2 MB compressed on disk.

## Coverage and quality checks (per pair)

| Pair | Minutes | Valid minutes in session | Zero-volume minutes in session | Longest in-session gap (min) | Missing days | Crossed quotes (O/H/L/C) | OHLC violations (bid/ask) | Valid minutes outside session | Rebuild identical |
|---|---:|---:|---:|---:|---|---|---|---:|---|
| EURUSD | 237,600 | 197,557 | 983 | 5 | none | 0/0/0/0 | 0/0 | 0 | True |
| GBPUSD | 237,600 | 197,520 | 1,020 | 8 | none | 0/0/0/0 | 0/0 | 0 | True |
| USDJPY | 237,600 | 197,637 | 903 | 19 | none | 0/0/0/0 | 0/0 | 0 | True |
| USDCHF | 237,600 | 197,238 | 1,302 | 15 | none | 0/0/0/0 | 0/0 | 0 | True |
| AUDUSD | 237,600 | 197,304 | 1,236 | 5 | none | 0/0/0/0 | 0/0 | 0 | True |
| USDCAD | 237,600 | 197,133 | 1,407 | 7 | none | 0/0/0/0 | 0/0 | 0 | True |
| NZDUSD | 237,600 | 197,108 | 1,432 | 19 | none | 0/0/0/0 | 0/0 | 0 | True |

## Spreads (pips, valid in-session minutes)

| Pair | Open: median / mean / p95 | Close: median / mean / p95 / max | Negative spreads |
|---|---|---|---:|
| EURUSD | 0.30 / 0.43 / 0.70 | 0.30 / 0.45 / 0.70 / 19.7 | 0 |
| GBPUSD | 0.70 / 0.97 / 1.40 | 0.70 / 0.98 / 1.40 / 34.7 | 0 |
| USDJPY | 0.40 / 0.67 / 1.10 | 0.40 / 0.68 / 1.10 / 34.8 | 0 |
| USDCHF | 0.80 / 1.18 / 1.60 | 0.80 / 1.19 / 1.60 / 40.0 | 0 |
| AUDUSD | 0.90 / 1.05 / 1.30 | 0.90 / 1.07 / 1.30 / 34.1 | 0 |
| USDCAD | 1.10 / 1.38 / 1.80 | 1.10 / 1.39 / 1.80 / 29.7 | 0 |
| NZDUSD | 1.00 / 1.20 / 1.50 | 1.00 / 1.20 / 1.50 / 35.0 | 0 |

## What each check means

- **Timestamps / UTC**: every row is bar-open, minute-aligned, strictly increasing, no duplicates, timezone UTC.
- **Bid and ask**: both candles are required for a day to be used; a mismatch in their timestamps stops the build.
- **Price precision**: prices are integers divided by `10**price_scale` (5 decimals; 3 for JPY), rounded to that scale.
- **Missing intervals**: a zero-volume minute carries no information (no tick). It is kept in the table as `valid=False`, **never replayed and never filled**. Gaps longer than 60 minutes reset all indicator state in the strategies.
- **Duplicate ticks / chronological order**: see the tick section (ticks were acquired only for the weeks listed there).
- **Spread calculation**: spread is derived (ask - bid), never stored as raw; zero negative spreads in candle values.
- **Deterministic construction**: building the dataset twice from the same raw files yields the same content hash for every pair.
