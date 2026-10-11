# Prospective virtual trading readiness

```
PROSPECTIVE_VIRTUAL_TRADING_ACTIVE = FALSE
SIMULATION_INFRASTRUCTURE          = COMPLETE AND TESTED (historical replay, restart recovery, append-only records)
MISSING_DEPENDENCY                 = a forward FX quote feed with seconds-level latency (none is currently available)
BROKER_ORDERS_SUBMITTED            = 0
TRADING_ENABLED / LIVE_TRADING_ENABLED = not touched, remain false; no broker connection of any kind was made
```

Prospective trading means deciding on data that has *just arrived* with no knowledge of what follows. Nothing in this
repository does that yet, and I am not claiming it does. What exists is the machinery that will run the *same frozen
logic* once a feed exists.

## What is built and proven (tests in `tests/`)

| Capability | Status | Evidence |
|---|---|---|
| Same frozen strategy code for historical and forward use | The strategy class consumes quotes through the engine's normal data path; it never reads files or the clock | `harness/fast_strategy.py` |
| Strategy-specific positions, portfolio exposure | Per-pair position and pending-order books; 3-position and 1.5% combined-risk gates | `test_engine_mechanics.py` |
| Entry, exit, stop-loss events and rejected signals | Every one is journaled (`ENTRY_SUBMITTED/FILLED/REJECTED`, `EXIT_SUBMITTED`, `TRADE_CLOSED`) with reasons | journal files, `test_core_pure.LedgerTests` |
| Cost-adjusted P&L, daily equity, drawdown | Ledger books EUR net per trade (spread, slippage, commission), UTC-day roll, peak-to-trough drawdown, daily-loss halt, drawdown pause | `test_core_pure.LedgerTests` |
| Append-only event records | JSONL, flushed per event, sequence numbers strictly increasing, never rewritten | `test_restart_recovery.test_journal_is_append_only_and_continuous_after_restart` |
| **Restart recovery** | A restarted run warms indicators by replaying history **without trading**, rebuilds the ledger from the journal, and produces **exactly the same trades, sizes and equity** as an uninterrupted run | `test_restart_recovery.test_governed_restart_reproduces_the_uninterrupted_run` (F01 and F05) |
| Fail-closed on defects | A strategy exception (which the engine only logs) aborts the run; an unsizable or too-costly trade is rejected, never loosened | `runner.py`, `test_engine_mechanics.py` |

Restart policy that is **not** proven: recovery of a position that is *open at the moment of a crash*. The design makes this
rare (everything is flat by 16:55 New York time, so restarts at a flat boundary are exact), but a mid-position crash would need a
Redis- or Postgres-backed Nautilus cache (their documented Postgres backing does not persist strategy state) and is out of
scope here. Until then the safe policy is: after a crash, flatten any broker position manually before restarting.

## What is missing, precisely: a forward quote feed

| Candidate feed | Why it cannot make trading "prospective" today |
|---|---|
| **Dukascopy public datafeed** (the source of all historical data here) | Files are published per completed hour/day and the server throttles to about 12 files/minute with frequent 503s; its JSON API is behind an AWS WAF bot challenge that I do not circumvent. At best this gives a delayed replay with at least an hour of latency, which would not exercise decision-time semantics. |
| **Interactive Brokers** (existing paper account) | The account lacks FX market-data entitlement (API errors 10089/162 in earlier phases). IB Gateway was not running during this work, and the v2 Nautilus IB adapter requires API protocol >= 213 (our Gateway's real maximum is unverified). |
| **Broker demo streaming** (Pepperstone cTrader Open API demo, IG demo) | Both would give genuine real-time prices, but need the manual account/API steps in `BROKER_REPORT.md`, and **NautilusTrader has no adapter for either** (a custom data client is required). |
| Nautilus **Sandbox** execution adapter | Exists and simulates fills on live data; untested here because it needs a live data source. |

Once any one of these provides quotes within seconds, the remaining work is small and bounded:

1. A thin data client that turns the feed into `QuoteTick`s with exchange timestamps.
2. `trade_from_ns` set to "now" after a warm-up replay of recent history (already implemented and tested).
3. A supervisor (Windows Task Scheduler or service wrapper) to restart the node; Nautilus documents none.
4. Shipping the journal into the Neon research database through its insert-only registry pattern (design only; **no production table was touched**).

## Risk Gate status

- **In the harness (implemented, tested):** 0.5% risk per trade, 3 simultaneous positions, 1.5% combined risk, 2% daily loss limit, 10% drawdown pause, 30:1 margin enforced by the engine, minimum size, a 20% cost-to-risk gate, a session entry block and a daily force-flat.
- **The Trading Intelligence Engine's independent deterministic SQL Risk Gate is NOT connected** to this harness. The intended integration is a fail-closed pre-trade call from a Nautilus actor (reject on error or timeout) so the SQL gate stays the final authority. This is a design item, not built, and must exist before any order could ever leave the simulator.

## Criteria for changing `PROSPECTIVE_VIRTUAL_TRADING_ACTIVE` to TRUE

1. A forward quote feed with documented latency and a measured outage rate.
2. The independent Risk Gate wired in fail-closed.
3. A process supervisor and an alert on journal inactivity.
4. At least one strategy classified `SHADOW_FORWARD_ELIGIBLE` by the pre-registered rules (none is expected from a six-month sample; see the final report).
5. Your explicit authorization.
