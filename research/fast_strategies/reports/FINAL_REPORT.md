# FINAL REPORT: FAST strategies F01-F07 on NautilusTrader + regulated FX broker selection

Prepared 2026-10-12. Research and simulation only. **Actual broker orders submitted: ZERO.** `TRADING_ENABLED` and `LIVE_TRADING_ENABLED`
were not touched and remain false. IBKR was not activated, no account was opened, nothing was purchased, no production Neon table was written.

## Headline

No strategy shows a positive edge after costs. Seven of the eight arms lose money net of spread, slippage and commission over the
full 5.7-month evaluated window, and the eighth (F04) produced only 16 trades. Five arms are classified `NEGATIVE_EVIDENCE`, one
`INSUFFICIENT_DATA`, and two `MIXED_EVIDENCE`. None is `PROMISING_RESEARCH` or `SHADOW_FORWARD_ELIGIBLE`. `NO_TRADE` is the right
answer for all of them today. I did not tune anything to change this, and I did not force a target.

## DATA

| Item | Result |
|---|---|
| Source | Dukascopy public datafeed, free, plain HTTP `.bi5` files (no paid service). The JSON API sits behind an AWS WAF bot challenge, which I did not circumvent |
| Pairs | EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD (all seven) |
| Coverage | **2026-04-01 to 2026-10-09 (192 days)**, native 1-minute BID and ASK candles, 2,310 of 2,310 files acquired, 0 failed |
| Candle counts | 237,600 rows per pair (1,663,200 total), of which about 197,100 to 197,600 per pair are valid in-session minutes (1,381,497 in total). Zero-volume minutes (about 900 to 1,430 per pair in session) are kept flagged, never replayed or filled |
| Tick counts | Tick tier is a **limited sample only** (a 3-day development window for the fidelity check): see "Tick fidelity" below. Full-period ticks were not acquired |
| Missing-data limits | No missing days in any pair. Longest in-session gap is 5 to 19 minutes depending on pair. Zero crossed quotes, zero OHLC-invariant violations, zero negative spreads, dataset rebuild hash identical on every pair. No valid minutes outside the session. Saturdays are not downloaded (market closed) |
| Median spread at the open (pips) | EURUSD 0.3, USDJPY 0.4, GBPUSD 0.7, USDCHF 0.8, AUDUSD 0.9, NZDUSD 1.0, USDCAD 1.1 |
| Location | `E:\Tradingdata` (outside git). Only QC JSON and small result files are in the repository |

Full per-pair table: `reports/DATA_REPORT.md`. QC JSON with file hashes: `results/dataset_qc.json`.

## STRATEGIES

Specs were recovered from the original engine's strategy registry, with what the registry does not say recorded in `specs/` (`missing_in_source`) and every
filling-in decision recorded as a pre-registered operationalization. Definitions and config hashes were **frozen and committed before any result existed**
(`specs/SPEC_HASHES.json`). Four disclosed amendments (A1-A4, all before evaluation, all motivated by mechanics or signal frequency on the development sample, none by P&L) are inside the hashed spec.
Partitions (fixed from the date range, 55/20/15/10): DEVELOPMENT to 2026-07-15, VALIDATION to 2026-08-23, OUT_OF_SAMPLE to 2026-09-20, RESERVED_FORWARD after that.
The evaluation was run **once** on DEV+VAL+OOS. Common methodology, base costs, fixed EUR 500 sizing (research mode) so results are measured in R.

| ID | Strategy (as operationalized) | Implemented + tested | Independent episodes (trades) | Gross return (mid-to-mid, % of EUR 500) | Net return (% of EUR 500) | Max drawdown | Profit factor (R) | Mean net R [95% CI] | Evidence class |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| F01 | Intraday Trend Continuation (15m displacement) | Yes | 393 (708) | -13.3 | -58.4 | 60.8% | 0.59 | -0.208 [-0.296, -0.115] | **NEGATIVE_EVIDENCE** |
| F02 | Intraday Mean Reversion (5m z-score fade) | Yes | 391 (983) | +5.5 | -70.7 | 71.2% | 0.60 | -0.171 [-0.230, -0.110] | **NEGATIVE_EVIDENCE** |
| F03 | Volatility Breakout / Expansion (15m compression, range breakout) | Yes | 324 (554) | -9.1 | -52.0 | 59.8% | 0.58 | -0.220 [-0.327, -0.108] | **MIXED_EVIDENCE** (see note) |
| F04 | Cross-Currency Relative Strength (15m, USD-neutral two-leg) | Yes | 16 (16) | +0.9 | +0.3 | 0.6% | 1.16 | +0.066 [-0.417, +0.613] | **INSUFFICIENT_DATA** |
| F05 | Session / Opening-Range Behavior (London/NY 30-min range breakout) | Yes | 308 (688) | +0.9 | -39.3 | 40.3% | 0.64 | -0.144 [-0.229, -0.055] | **NEGATIVE_EVIDENCE** |
| F06 | Multi-Timeframe Trend Alignment (5m trigger, 1h trend) | Yes | 258 (428) | -15.6 | -47.6 | 51.3% | 0.61 | -0.246 [-0.389, -0.093] | **NEGATIVE_EVIDENCE** |
| F07 | Short-Horizon Momentum (1m burst) | Yes | 428 (1,085) | +4.9 | -78.3 | 78.9% | 0.55 | -0.173 [-0.230, -0.116] | **NEGATIVE_EVIDENCE** |
| F07R | Short-Horizon Reversal: mirror of F07 (diagnostic arm, not promotable) | Yes | 327 (748) | -6.1 | -63.1 | 64.4% | 0.49 | -0.200 [-0.258, -0.144] | MIXED_EVIDENCE (diagnostic only) |

Drawdown here is on the fixed EUR 500 base across the whole window, in research mode (no drawdown pause), so it measures the strategy rather than the risk gate.
All numbers: `results/EVIDENCE_TABLE.md` and `results/evidence_summary.json`; every trade of every arm: `results/trades_*.csv`.

What the numbers say, without spin:

- **Costs are the whole story for the arms that have any gross edge.** F02 (+5.5%) and F07 (+4.9%) are slightly positive before costs and lose 70 to 80% after costs. F01, F03 and F06 are negative even before costs. The mean net R is below zero in **every** partition for F01, F02, F05, F06 and F07.
- **The cost gate removed most of the F02/F07 signals** (F02 13,493 and F07 22,233 signals rejected because expected cost exceeded 20% of risk). The surviving trades still lose.
- **Cost sensitivity does not rescue anything.** Even at optimistic costs (no slippage, observed spreads) all arms except F04 stay clearly negative. Adverse costs are worse or have too few trades.
- **F03 `MIXED_EVIDENCE` is a classifier outcome, not a sign of promise.** The pre-registered rule looks at the pooled VALIDATION+OUT_OF_SAMPLE sample and F03's CI there spans zero (-0.150 [-0.356, +0.079]). Its OUT_OF_SAMPLE mean R is +0.193 (70 trades, 44 episodes) but DEVELOPMENT (-0.250) and VALIDATION (-0.406) are strongly negative, and over the whole window its CI is entirely below zero. I'd treat a single positive partition after two strongly negative ones as noise until shown otherwise.
- **F04 is untestable on this window.** It fired 16 times (needs a cross-currency strength gap of at least 3.0); the CI is [-0.42, +0.61]. That is `INSUFFICIENT_DATA`, not evidence of a working strategy.
- **F07R (the mirror of F07)** is also negative; it exists only to check whether F07's losses are a pure cost effect. It is not a strategy candidate.
- **Governed EUR 500 run** (real capital rules, compounding sizing): every arm except F04 hit the 10% drawdown pause and ended between EUR 446 and EUR 457 (a 9% to 11% loss); F04 ended at EUR 501.66 on 16 trades.
- **Win rates** are 29% to 46% with average wins smaller than or only modestly larger than average losses (profit factor 0.49 to 0.64 for the seven non-F04 arms). I did not look for an 85% win rate and none appears.
- **Overlap and correlation:** trades cluster (1.7 to 2.5 trades per independent episode), so the bootstrap is done on episodes, not on trades.

### Supplementary: RESERVED_FORWARD pass (2026-09-20 to 2026-10-10)

Run once after the main results were committed, for information only, no reclassification (`results/reserved_forward/FORWARD_HOLDOUT.md`). At base costs all arms were net-negative
(F01 -56, F02 -161, F03 -18, F04 -6, F05 -18, F06 -95, F07 -134, F07R -132 EUR, research mode), consistent with the main result. F03 was marginally positive only at optimistic costs (+7.4 EUR on 91 trades, profit factor 1.02), which is within noise for roughly three weeks.

## EXECUTION

| Item | Status |
|---|---|
| Historical simulation | **Complete.** 32 runs (8 arms x research optimistic/base/adverse + governed base) on Nautilus BacktestEngine 2.0.0rc6, bid/ask quote execution, 0.5 s latency, next-minute-open fills, native reduce-only protective stops, spread/slippage/commission, margin enforcement. 92 deterministic tests pass |
| Prospective virtual trading | **NOT ACTIVE.** Infrastructure is built and tested (append-only journal, restart recovery proven bit-exact against an uninterrupted run, daily equity/drawdown, rejected-signal log). **Missing dependency: a forward FX quote feed with seconds-level latency.** Dukascopy publishes delayed hourly files and throttles; the IBKR paper account has no FX market-data entitlement and Gateway was not running; broker demo feeds need the manual setup below plus a custom Nautilus data client. Details: `reports/PROSPECTIVE_READINESS.md` |
| Risk Gate | Harness gates implemented and tested: 0.5% risk (EUR 2.50), 3 positions, 1.5% combined risk, 2% daily loss limit, 10% drawdown pause, 30:1 margin, minimum size (below it the trade is rejected, never rounded up), 20% cost-to-risk gate. **The Trading Intelligence Engine's independent SQL Risk Gate is NOT connected** to this harness (design only). It must be wired in fail-closed before any order could leave a simulator |
| Actual broker orders submitted | **ZERO** |

Candle-synthesized quotes are an approximation of the intraminute path (four quotes per minute). The documented cost/fill assumptions are in `reports/COST_AND_RISK_ASSUMPTIONS.md`.

## BROKERS

Full report with evidence tags: `reports/BROKER_REPORT.md` (raw research with URLs: `reports/appendix/`). No earlier cTrader/Kraken/Coinbase evaluation exists in this fork, the engine repository or other sessions, so nothing was reused.

| Item | Result |
|---|---|
| **PREFERRED_FX_BROKER** | **Pepperstone GmbH (Dusseldorf), cTrader Razor account, cTrader Open API** (weighted score 3.58) |
| **BACKUP_FX_BROKER** | **IG Europe GmbH (Frankfurt)**, REST + Lightstreamer API (3.53); needs IG's written approval for algorithms |
| Regulatory verification | Verified by me: Pepperstone GmbH is on the BaFin company database (Wertpapierinstitut, BaFin-ID 10151148, data version 10.10.2026). Verified by me: IG's contract clause 9(12) forbids automated software without prior written approval. Verified by me: cTrader refresh tokens do not expire. Other items are from official pages through a delegated research pass and marked `[RESEARCH]` or `[UNVERIFIED]`; unverified items earn no points |
| German eligibility | Both pass the gate (German GmbH entities, BaFin-registered, German-language onboarding). Marketing claims are labeled as such |
| Demo / API readiness | Pepperstone: free cTrader demo; **demo API access and GmbH Open API enablement unverified**; Spotware must approve an API app. IG: self-service REST API key, demo available, written approval needed. Neither has a NautilusTrader adapter: a custom execution client is required |
| EUR 500 feasibility | Pepperstone Razor about 0.7 pip all-in on EURUSD, costs 3.5% to 7% of EUR 2.50 risk at 10-to-20-pip stops, minimum 1,000 units, margin about EUR 93 per 2,800-unit position at 30:1. IBKR is economically unsuitable at EUR 500 (USD 2 minimum commission per order, about 143% of the risk) |
| Remaining manual steps | (1) open a free cTrader demo; (2) register a Spotware Open API application; (3) run the OAuth flow once and store tokens outside git; (4) read per-pair `minVolume`/`stepVolume` and test the full order lifecycle on the demo; (5) get Pepperstone's written confirmation on API access and negative-balance protection; (6) only then consider the live account; (7) for the backup, open an IG demo and ask IG in writing to approve algorithmic trading. Not done by me: it needs your identity, KYC and consent |

The two brokers are statistically tied (difference 0.05); the ranking is not a recommendation to trade. Given the strategy results above, the useful next use of a demo account is to validate execution mechanics, not to run these strategies.

## GITHUB

| Item | Value |
|---|---|
| Repository | `EricFinance7/nautilus_trader` (fork of nautilus_trader) |
| Branch | `research/fast-strategies-and-fx-broker-v1` (not merged; default branch untouched) |
| Commit SHA | see the final line of this report's footer in the chat reply (the SHA of the commit containing this file cannot be written inside itself) |
| Tests | 92 passed, 0 failed (`python -m unittest discover -s tests -t .`, with `TIE_MINUTE_DIR` set so the restart-recovery integration test runs) |
| Remaining blockers | Forward quote feed; independent SQL Risk Gate integration; broker demo setup (manual); full-period tick data (only a 3-day sample) |

## Reproduce

See `README.md`. Pinned `nautilus_trader==2.0.0rc6`, deterministic, same data plus same config hash reproduces the same trades.
