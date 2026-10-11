# Cost, execution and risk assumptions (frozen in `specs/HARNESS_v1.json`, hash in `specs/SPEC_HASHES.json`)

Every number below is read from `fast_research/specs.py`; none was tuned on a result. Amendments A1-A4 were made *before any
strategy was evaluated* and are recorded, with their reasons and whether performance was used, inside the hashed spec.

## Capital and risk (EUR 500 virtual account)

| Rule | Value |
|---|---|
| Initial virtual equity | EUR 500 (the IBKR paper account's ~EUR 1,000,000 is never read) |
| Planned risk per trade | 0.5% of equity; EUR 2.50 initially (F04 pair-trades: 0.25% per leg) |
| Max simultaneous positions | 3 |
| Max combined open risk | 1.5% of equity |
| Daily realized loss limit | 2% of start-of-day equity (UTC day); blocks new entries until the next UTC day |
| Peak-to-trough drawdown pause | 10% of the realized-equity peak; blocks new entries for the rest of the run |
| Martingale / averaging down / pyramiding | none; one position per pair |
| Leverage | ESMA retail majors 30:1: margin 1/30 initial, 1/60 maintenance; the engine denies any order whose margin exceeds free balance (`INITIAL_MARGIN_EXCEEDS_FREE_BALANCE`) |
| Size | `floor_to_step( risk / ((stop + spread + stop_slippage) * EUR_per_quote) )`, step and minimum 1,000 units; below the minimum the trade is **rejected, never rounded up** |
| Cost gate | reject if expected round-trip cost / risk > 0.20 (same ceiling as frozen FRONT-1) |
| Equity used for sizing | realized virtual equity only. In RESEARCH mode (amendment A4) it is fixed at EUR 500 and the drawdown pause is off, so the evidence is measured in R and is not distorted by compounding |

Because size moves in 1,000-unit steps and is always rounded **down**, the realized risk is between roughly 0.25% and 0.5%
of equity; evidence is measured in R = net P&L / actual risk at the stop so this does not bias comparisons.

## Execution timing (no instant fills)

- A decision is taken when the signal-timeframe bar completes. A market order arrives 0.5 s later (adverse scenario: 60.5 s)
  and fills at the first quote after arrival: **the next minute's OPEN bid/ask** (adverse: the open one minute later).
- Entries are market orders. Protective stops are native reduce-only `STOP_MARKET` orders placed on the entry fill (also
  delayed by the same latency). All other exits (time, signal, force-flat) are market orders at the next open.
- No entries 16:30-19:00 New York time (rollover spread blow-outs: observed closes of 19-30 pips), and everything is closed at
  16:55 New York time, so nothing is held across the 17:00 rollover, over a weekend, or through swap; carry is therefore not modeled.

## Costs and their provenance

| Component | Base | Optimistic | Adverse | Provenance |
|---|---|---|---|---|
| Spread | observed Dukascopy bid/ask as is (x1.0) | x1.0 | x1.5 | **OBSERVED** (candle values). Median spreads: EURUSD 0.3 pip, USDJPY 0.6, GBPUSD 0.7, USDCHF 0.8, AUDUSD 0.9, NZDUSD 1.0, USDCAD 1.1 |
| Commission (per side, fraction of notional) | 0.000026 | 0.000026 | 0.000040 | **BROKER_SCHEDULE**: Pepperstone GmbH cTrader Razor, USD 3 per side per 100k, Sept 2026 published fee schedule. The broker is *not yet selected or opened*; this is a vendor-published figure, not an observed fill |
| Market-order slippage (each side) | 0.1 pip | 0 | 0.3 pip | **CONSERVATIVE_ASSUMPTION** (baked into the quote stream so every market fill pays it) |
| Extra stop slippage | 0.3 pip total | 0 | 0.6 pip total | **CONSERVATIVE_ASSUMPTION** (applied to the ledger's stop exits) |

Gross return in the reports is **mid-to-mid before any cost**; net return is after spread, slippage and commission, and the
two are reconciled exactly (`gross - spread&slippage - commission = net`, checked in the data of every run).

## Known simplifications (stated, not hidden)

1. **Candle-synthesized quotes.** Each valid minute becomes four quotes (open, first extreme, second extreme, close) built only
   from values in the BID/ASK candles. The intraminute path and the timing of extremes are unobservable from candles; the
   path convention is Nautilus's own adaptive high/low ordering. Real tick data (where acquired) is used for a fidelity check.
2. **Stop fills are re-priced** in the virtual ledger (stop price less slippage, unless the stop was crossed by the minute-open
   quote, i.e. a gap). The engine's own fill at the crossing path quote would otherwise be the minute extreme. The size of the
   correction is reported for every run (`ledger_minus_engine_eur`).
3. **Bid and ask extremes are paired** at the same path point, which can only widen the modeled spread at extremes, never cross it.
4. **No carry/swap**, no commission minimums, no broker rejections or requotes, no partial fills (quote sizes are 1,000,000
   units; orders are at most tens of thousands).
5. **Mid prices** used for signals are (bid + ask)/2 of each OHLC field; the mid high/low is therefore approximate.
6. **Broker minimum size** is assumed to be 1,000 units; per-pair values are unverified (see the broker report).
