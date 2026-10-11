# NautilusTrader evaluation for the Trading Intelligence Engine

Prepared 2026-10-11 on branch `research/trading-intelligence-evaluation` of the `EricFinance7` fork.
Status: **evaluation only. Nothing was migrated, no broker was contacted, no order was placed, nothing was
purchased, and the existing Trading Intelligence Engine was not modified.**

**Recommendation: PILOT** (research and simulation only, Option A "hybrid", pinned to a v2 release candidate,
no live or IBKR execution through NautilusTrader). Reasoning in section 15.

## 0. How to read this report

Every claim carries an evidence tag so verified behavior is not confused with marketing or roadmap text.

| Tag | Meaning |
|---|---|
| **[V]** | Verified first-hand in this evaluation: read in the source tree, queried from GitHub/PyPI, or executed here. |
| **[D]** | Stated in upstream documentation or code comments only. Not exercised by me. |
| **[U]** | Untested or an assumption. Needs a test before anyone relies on it. |

What I did and did not do:

- Read the README, ROADMAP, RELEASES, MIGRATION_V2, the integration/concept docs, the Interactive Brokers (IB)
  adapter source, and the open-issue list. **[V]**
- Installed two builds into throwaway virtual environments **outside both projects** and ran them against real
  samples of your Dukascopy ticks (section 12). **[V]**
- Did **not** compile from source (no Rust toolchain installed here), did **not** connect to IB Gateway (it was
  not running), did **not** run any live, sandbox-with-live-data, or broker-connected test. **[V]**

## 1. Identity and provenance

| Item | Value |
|---|---|
| Original repository | https://github.com/nautechsystems/nautilus_trader |
| Your fork | https://github.com/EricFinance7/nautilus_trader |
| Local clone | `E:\Projects\nautilus-trader-eric` |
| Remotes | `origin` = your fork, `upstream` = `nautechsystems/nautilus_trader` |
| Fork-point commit (`develop`) | `3a8e04289896d945598741558374119fd38060ac` ("Fix Interactive Brokers order ID start below used IDs (#5284)"). `origin/develop` and `upstream/develop` were identical at clone time. **[V]** |
| License | GNU LGPL-3.0 (`LICENSE`; GitHub API `lgpl-3.0`); forking allowed (`allow_forking: true`) **[V]** |
| Upstream scale | ~29.9k stars, ~4.0k forks, 21,723 commits since 2018-06-25 **[V]** |

**Deviations from your instructions, stated plainly:**

1. **The GitHub CLI (`gh`) is not installed on this machine**, so I could not verify "gh auth" literally. I used
   the GitHub connector available to this session instead. It reports it is authenticated as `EricFinance7`
   (user id 330061649), which is the correct account. The fork it created is a genuine GitHub fork (parent
   `nautechsystems/nautilus_trader`, full history), not a copy.
2. **The fork is named `nautilus_trader`, not `nautilus-trader-eric`.** The connector's fork call cannot set a
   custom name. You named `nautilus_trader` as the acceptable fallback. If you prefer the original preferred
   name: GitHub → fork → Settings → Repository name (one rename; GitHub redirects the old URL).
3. Local identity on the clone is set **repo-locally only** to `EricFinance7` with the GitHub noreply address, so no
   personal email is embedded in commits. Global git config was not changed.

## 2. Which version? (the "stable" question has an awkward answer)

| Line | Latest | Commit | Status |
|---|---|---|---|
| v1 (Cython) | **v1.231.0** (2026-08-02) | `27a8e54e7ac3c57d6cbf8891f0283dfbaee97317` | Last non-prerelease on PyPI. Classified "Development Status :: 4 - Beta". **Frozen**: receives "only critical security backports" for ~3 months after the v2 cutover, "no feature or parity work" **[V: MIGRATION_V2.md]** |
| v2 (Rust core, PyO3) | **2.0.0rc6** (2026-10-05) | `7b766f8825b2539c5b2ac1375e9d97b41c509edb` | Release candidate. README: "We do not recommend using release candidates in production environments, such as live trading controlling real capital." **[V]** |
| v2 `develop` | 2.0.0rc7 (unreleased) | fork-point above | Development; drops Python 3.12 **[V: RELEASES.md]** |

Important consequences:

- `upstream/master` now points at the **rc6 release commit**, so the README's "master is recommended for
  production" now means a release candidate, not a stable release. **[V]**
- "Stable" and "supported" are different things here. v1.231.0 is the only non-prerelease, but it is a dead-end
  line; code written against it must later be ported (MIGRATION_V2.md is 1,097 lines; the Python package changes
  from Cython to PyO3, with many renamed APIs). v2 has no stable release yet.
- **Recommended pin for a pilot: `2.0.0rc6` (`7b766f8`)**, on the understanding that it is a release candidate used
  for research and simulation only. Re-evaluate when `2.0.0` final ships. Fallback only if v2 is blocked:
  `1.231.0` (`27a8e54`), accepting a later port.
- I did **not** assume the newest prerelease is production-ready, and I am not recommending it for capital.

## 3. Architecture and dependency map **[V]**

- **Hybrid Rust + Python.** A Cargo workspace under `crates/` (2,813 Rust source files) provides the engine;
  Python (253 files under `python/`) is the control plane via PyO3/maturin (`nautilus_trader._libnautilus`).
  Toolchain pin: Rust 1.99.0 (`rust-toolchain.toml`); MSRV tracks latest stable Rust.
- **Crate groups:** `core, model, common, system, data, execution, risk, portfolio, trading, backtest, live,
  persistence, serialization, indicators, analysis, network, cryptography, event_store, infrastructure,
  adapters/*, pyo3, plugin, testkit, cli, macros`.
- **Runtime shape (event-driven):** `DataEngine → Strategies/Actors → RiskEngine → ExecutionEngine → execution
  client`, all sharing a `Cache`, `MessageBus`, `Portfolio`, and a clock. The same strategy code runs in
  backtest, sandbox (simulated fills on live data), and live contexts. **[D, partly V: smoke test ran the same
  strategy pattern]**
- **Strategy lifecycle:** configure → `on_start` (subscribe, register indicators) → event callbacks (`on_bar`,
  `on_quote_tick`, order/position events) → `on_stop`. **[V: exercised in smoke test]**
- **Python dependencies:** v1.231.0 requires click, fsspec, msgspec, numpy, pandas, portion, pyarrow, pytz,
  tzdata, tqdm (plus uvloop off Windows). **v2.0.0rc6 declares no Python dependencies** (the wheel is
  self-contained; pandas/plotly only for the optional `visualization` extra). **[V: pyproject + `pip list`]**
- **Persistence backends:** Parquet data catalog (native); Redis (cache database + message bus); PostgreSQL (cache
  database only, `postgres` feature compiled into wheels). DuckDB: **no integration anywhere in the repo**
  (searched). **[V]**
- **Scope boundary (ROADMAP):** single-node backtesting/live for individual and small-team quants. UI dashboards,
  distributed orchestration, built-in AI/ML tooling, and **integrated hyper-parameter optimization** are
  explicitly out of scope. **[V]**

## 4. Trading capabilities and adapters

Adapters present in `crates/adapters` and `python/nautilus_trader/adapters` **[V]**: Architect AX, Betfair,
Binance, Blockchain, Bybit, Coinbase, Databento, Deribit, Derive, dYdX, Hyperliquid, **Interactive Brokers**,
Kraken, Lighter, OKX, Polymarket, **Sandbox**, Tardis. README rates all listed integrations "stable" **[D]** — that
label is the project's own and is contradicted in places by the open-issue list (section 7).

| Asset class | Support | Route relevant to us |
|---|---|---|
| **Forex (spot)** | Yes, `CurrencyPair` instrument; IB maps `CASH`/`IDEALPRO` **[V]** | **Interactive Brokers is the only FX broker adapter.** No OANDA/FXCM/cTrader-class adapter exists. |
| Equities / ETFs | Yes (IB, Databento data) | Not a current focus of ours |
| Futures | Yes (IB, Databento, crypto venues) | — |
| Options | Yes (IB, Deribit, Databento) | — |
| Crypto (spot/perps/futures/options) | Yes, many venues | — |
| Betting / prediction markets | Betfair, Polymarket | — |

## 5. Research capabilities

| Capability | Finding |
|---|---|
| Historical ingestion | `ParquetDataCatalog`; wranglers for quotes/trades/bars/book; CSV loaders for histdata and TrueFX exist as *examples*. **Zero mentions of Dukascopy** in the repo. **[V]** |
| Tick-level backtest | Quote ticks, trade ticks, bars, L2/L3 book; ns timestamps; venue `book_type` must match the data granularity (L1 for quotes/bars). **[D + V: ran 7,459 quote ticks]** |
| Fill realism | Fill models (best-price, one-tick slippage, probabilistic, tiered, market-hours), `StaticLatencyModel`, explicit per-venue fee models (every venue needs one), FX-rollover and CFD-swap simulation modules. **[D]** |
| Parameter testing | Supported only as *repeated runs*: fresh `BacktestNode` per config, or `engine.reset()` to reuse loaded data. **No built-in optimizer.** **[V]** |
| Walk-forward | **Not built in.** Would be orchestrated by us (loop of `BacktestRunConfig` with `start_time`/`end_time` windows). **[V: grep; ROADMAP]** |
| Reproducibility | Deterministic matching and deterministic trade IDs for identical replayed data. **[D]** Dataset hashing, preregistration and evidence registry would remain ours. |
| Simulated trading | Backtest venues (SIM), and a **Sandbox** execution adapter that matches orders against live market data with the production matching engine. **[D: crate README]** |

## 6. Automation, restarts and failure handling

- **Live node:** builds → restores cache (if a backing DB is attached) → connects data/exec clients → startup
  reconciliation → starts strategies → runs event loop → coordinated shutdown. **[D]**
- **Reconnects:** the IB transport (`ibapi` crate) reconnects with Fibonacci backoff to a bounded attempt count;
  data streams then resubscribe; farm-outage notices are handled separately from socket failure; a dead
  order-update stream marks the execution client disconnected rather than silently healthy. **[D]**
- **Reconciliation:** "An explicit position report is authoritative. During startup reconciliation, the engine
  either aligns to that report within reconciliation tolerances or **fails closed**"; unresolved reports prevent
  strategies from starting. Fill dedupe, commission pairing, and missing-fill recovery from execution history are
  described. **[D]**
- **State persistence:** Redis backs cache, message bus, and strategy/actor state. **PostgreSQL backing does not
  persist actor/strategy state or cache heartbeats** and is rejected under `run_async()`. **[V: MIGRATION_V2 known
  limitations]**
- **"Unattended" is not turnkey.** Nothing in the docs describes a service wrapper, watchdog, or process supervisor
  (searched `live.md`, `configure_live_trading.md`, `installation.md`). Running continuously on Windows would need
  our own supervision (Task Scheduler, a service wrapper, or Docker restart policy). **[V: absence; U: how well it
  behaves under that supervision]**

## 7. Execution and the IBKR FX question (the part that decides most things)

You asked me not to assume an adapter resolves broker restrictions. It does not, and here is the evidence.

**What the IB adapter does well [D]:** order types market/limit/stop/stop-limit/MIT/LIT/trailing; time-in-force
DAY/GTC/IOC/FOK/GTD; submit order lists including brackets and linked orders; modify/cancel; mass status; open-order
and position reconciliation after restart; fill dedupe across IB execution replays; order rejection codes 200–399
become a terminal `OrderRejected`. Paper ports 4002 (Gateway) / 7497 (TWS) are the defaults.

**What it does *not* do for FX [V: source search]:**

| Our observed IBKR FX behavior | NautilusTrader handling |
|---|---|
| Error 201 "FX trade would expose account to currency leverage" on an exact `totalQuantity` BUY | No special handling. It would surface as `OrderRejected`. |
| `cashQty` (quote-currency sizing) was what let our restoration order fill | The adapter sets `cashQty` **only for inverse instruments with quote-quantity (e.g. crypto on PAXOS)**; `CurrencyPair` "is never inverse", so a plain FX order is sent with `totalQuantity`. Same in v1.231.0. |
| IBKR VirtualFX vs real currency balances (`CASH` trade vs `FXCONV` conversion; `reqPositions` returns a virtual EUR/USD position) | No `FXCONV`, `isCcyConv`, or VirtualFX logic anywhere in the adapter. Position reports from `reqPositions` feed reconciliation directly. |
| Our paper account holds a **residual virtual FX position** from the earlier probe | On connect, reconciliation would treat IB's position report as authoritative and try to align (adopt it via a reconciliation fill, or fail closed). This would need to be handled deliberately, not discovered live. **[D reasoning + U]** |

**Open upstream issues touching exactly this path (open on 2026-10-11) [V]:**
#5298 FX history/quotes arrive off the instrument's `price_increment`; #5299 execution client's account base
currency hardcoded to `None`; #5297 price magnifier applied inconsistently; #5277 order ID seeded below used IDs so
every order is refused with error 103 (a fix, #5284, is the fork-point commit but is unreleased); #5233 orders for
instruments loaded only by the data client rejected with error 200; #5281 protobuf decoder breaks on IB Gateway
10.51+; #5280 periodic position check can close positions for clients that do not report them; #5119 `RiskEngine`
admits buys that together exceed a cash account's free balance (label: bug).

**Version coupling [D]:** the v2 adapter pins `ibapi 4.0.1` and requires a TWS/Gateway **API protocol version of
213 or newer**. Your Gateway negotiated protocol 178 through `ib_async` in an earlier phase — that number is
probably capped by `ib_async`'s own client ceiling, so the Gateway's true maximum is **unknown [U]** and Gateway was
not running during this evaluation. It must be checked before any v2 IB test.

Also: rc7 (develop) contains further breaking IB changes (connection wrappers removed, stricter contract filters),
i.e. the IB adapter is still moving.

**Conclusion:** NautilusTrader would give a more complete order-state machine and reconciliation layer than we
have, but **the IBKR FX semantics we had to learn the hard way would still have to be solved by us** (a wrapper
that sizes FX by `cashQty`, avoids exact-quantity BUYs, and understands VirtualFX), and the Rust IB adapter has
open FX-specific bugs. Execution through NautilusTrader should not be on the near-term path.

## 8. Costs

| Item | Cost |
|---|---|
| NautilusTrader (LGPL-3.0) | **$0.** No subscription, license key or paywall found in the repo. **[V]** |
| Required infrastructure for the pilot | **$0 incremental**: runs locally on Windows; Docker is optional. |
| Redis (only if used as cache/message bus) | Free (local container). |
| PostgreSQL | Already have Neon; used by Nautilus only as a *cache* store. Suitability of Neon free tier for that is **[U]**. |
| Market data | Pilot uses data we already hold (Dukascopy). **Live** FX quotes via IB would need an entitlement our paper account currently lacks (errors 10089/162 seen earlier); the adapter offers delayed/frozen modes. Price of an IB subscription **not verified**. |
| Databento / Tardis | Optional paid data vendors; not needed for the pilot. Prices not verified. |
| Always-on hosting | Not needed for research. A live deployment would need an always-on Windows host or VPS (unquantified). |
| Broker fees | Unchanged; they depend on IBKR, not on the engine. |

**Estimated additional mandatory subscription cost: $0.** Optional costs above are real but I did not verify
vendor prices and will not invent figures.

## 9. Compatibility

| Area | Finding |
|---|---|
| Windows | `win_amd64` wheels exist for v1.231.0 (cp312–cp314) and v2.0.0rc6 (cp312–cp314). **Both installed and ran on this machine (Windows 11, Python 3.12.10).** **[V]** |
| Python | v1.231.0: 3.12–3.14. rc6 wheels: 3.12–3.14. **develop/rc7: 3.13–3.14 only** (3.12 dropped), so a pin to rc6 is the last that works with the Python we have today. **[V]** |
| Rust | Not needed for wheels. Building from source needs Rust 1.99.0, clang, and MSVC Build Tools. `rustc` is not installed here and I did not attempt a source build. **[V]** |
| Docker | Official images on `ghcr.io` (signed, SBOM). Docker 29.8 is installed here. Not exercised. **[V: tool present; U: images]** |
| PostgreSQL | Cache backend only; not a research database. **[V]** |
| Parquet | Native catalog; **exact round trip verified** (section 12). DuckDB is not used by Nautilus. |
| n8n | No integration. **n8n Cloud cannot reach a process on your PC** (same constraint that shaped FRONT-1). Any coupling would be through Postgres, files, or Redis streams written by a local process. **[V reasoning]** |
| Claude Code | The repo ships `AGENTS.md`/`CLAUDE.md`, so agent-assisted work is expected; no special integration needed. **[V]** |

## 10. Maturity **[V unless tagged]**

- Release cadence ~2–3 weeks; v2 RCs: rc3 (Aug 21), rc4 (Sep 2), rc5 (Sep 15), rc6 (Oct 5); rc7 pending.
- Activity: 571 commits on `develop` in the last 30 days, 1,876 in 90 days, 59 distinct authors in 90 days.
- Open: 103 issues, 13 PRs. Only 4 carry the `bug` label, but issue labeling is sparse, so that number understates
  defects (several IB/FX defects above are unlabeled).
- README warning: "NautilusTrader is still under active development… breaking changes can occur between releases."
- v1 is in security-backport-only mode; v2 has no stable release.
- Recent rc7 fix notes include many correctness fixes in reconciliation, accounting and adapters — evidence of both
  rapid improvement and a still-settling surface.

## 11. Comparison with the Trading Intelligence Engine

Current engine (read-only inspection): 24 exported n8n workflows, 61 SQL migrations, Neon registry with insert-only
evidence tables, `python/fxlake` DuckDB/Parquet engine (bar-based, strategies S01–S06/S08, cost-aware walk-forward
matrix), `python/dukascopy_audit` (validated tick model, resumable downloader), SQL deterministic risk gates,
TrendSpider webhook ingestion, `python/tradingintel` IBKR adapter with the FRONT-1 paper benchmark, and F01–F07 all at
status **DISCOVERED** (none preregistered or backtested).

**Data reality check:** `E:\Tradingdata` currently holds ~3.3 MB of raw Dukascopy samples (EURUSD ticks for two hours
plus minute candles) and one 0.1 MB Parquet sample; `ticks/`, `duckdb/` and `normalized/` are empty. The bulk pull
(estimated ~14.4 GB) has been designed and tested on a small sample but **not run**.

| Our component | NautilusTrader relationship | Verdict |
|---|---|---|
| F01–F07 / R-series *research definitions, preregistration, evidence* | Nautilus has no research governance | **Keep independent** |
| Neon registry (experiments, datasets, hashes, decisions) | Not a research DB; Postgres is cache-only | **Keep independent** |
| `fxlake` bar-based hourly engine | Nautilus is event-driven tick/quote capable; a different tool for a different resolution | **Keep for hourly; Nautilus complements for intraday** |
| **Intraday tick/quote-level simulation with real bid/ask fills (FAST/F-series)** | Our repo has no event-driven tick simulator; Nautilus provides one (fill/latency/fee models) | **Candidate to replace "build it ourselves"** (needs custom integration) |
| Dukascopy ingestion + validation (`dukascopy_audit`) | No Dukascopy support; our validated model is the source of truth | **Keep; add a converter into a Nautilus catalog** |
| Parquet lake + dataset hashing/manifests | Nautilus catalog is a second format; no dataset registry | **Keep ours; export to catalog on demand** |
| n8n orchestration | No equivalent; Nautilus is a long-running local process | **Keep; n8n cannot drive a local node directly** |
| Quant Engine + AI analysis | Out of Nautilus scope (ROADMAP: no built-in AI/ML) | **Keep independent** |
| **Deterministic SQL Risk Gate** | Nautilus `RiskEngine` does pre-trade checks (notional, rate), not evidence/portfolio policy | **Keep independent**; if used, call it from a strategy/actor *fail-closed* |
| TrendSpider integration (webhooks into `signals`) | No equivalent; would be a custom actor/data source | **Keep independent** |
| IBKR paper adapter / FRONT-1 execution service | Overlaps in order state, fills, reconciliation; but our `cashQty`/VirtualFX/structural live-prohibition logic has no Nautilus equivalent | **Partial overlap; keep ours for now** |
| FRONT-1 virtual EUR 500 ledger | Sandbox adapter can simulate fills on live data; ledger truth stays in Postgres | **Possible later use of Sandbox; keep ledger** |
| Historical backtesting / prospective simulation / execution lifecycle | Nautilus unifies these under one runtime | **Strongest conceptual fit, but unproven for us** |

## 12. Dukascopy tick-data feasibility and the isolated test **[V]**

Sandbox (outside both projects): `E:\Projects\nautilus-eval-sandbox` with two virtualenvs. Scripts and recorded
outputs are in `evaluation/install_test/`. Source data was read from your raw samples; nothing was written back.

| Test | v1.231.0 | v2.0.0rc6 |
|---|---|---|
| Install from prebuilt Windows wheel, Python 3.12.10 | OK | OK |
| Decode 2 h of EURUSD Dukascopy ticks → 7,459 `QuoteTick` (bid+ask kept) | OK | OK |
| Replay through `BacktestEngine` (FX CurrencyPair, margin account, 1-min internal bars from quotes, EMA strategy) | 38 orders / 19 positions | 36 orders / 18 positions |
| Parquet catalog write + query-back | not run | **7,459 / 7,459, exact bid/ask/ts match, 10.4 bytes per tick** |
| Crossed quote (bid>ask), constructed and replayed | accepted | accepted |

The order counts differ only because the two strategies were written separately; they are **not** a performance
comparison, and the strategy is not a candidate. **No profitability conclusion can or should be drawn from a 2-hour
sample.**

Findings and caveats:

- Dukascopy → Nautilus is a ~40-line converter, but it is **ours to write and own**; there is no upstream support.
- Dukascopy tick volumes were replaced with a constant size (1,000,000) because the unit mapping of Dukascopy
  volumes to FX order-book size is not established. **[U]**
- Your audit found ~10.6% of raw ticks cross momentarily. Nautilus accepts crossed quotes; **whether its matching
  engine fills sensibly against a crossed top-of-book is untested.** The sample here had zero crossed ticks.
- Instrument definitions (precision, lot size, margin) used the testkit's generic FX default, not IBKR's real
  contract specifications. **[U]**

## 13. Feasibility of F01–F07 in NautilusTrader **[assessment; U until built]**

None of F01–F07 has code, preregistration, or a backtest today, so "compatibility" means "can the platform express
and test them," not "do they work."

| Family | Fit | Notes |
|---|---|---|
| F01 Trend continuation, F02 Mean reversion | Good | Bars from quotes, indicators and spread-aware fills are native. Our own priority doc ranks F01–F03 first. |
| F03 Volatility breakout | Good | ATR/range indicators exist; needs real bid/ask for cost realism. |
| F04 Cross-currency relative strength | Plausible | Multi-instrument streams merge chronologically in the engine; cross-sectional ranking logic is custom. |
| F05 Session / opening range | Plausible, custom | Needs a session model; rc7 adds zoned calendar timers (unreleased). |
| F06 Multi-timeframe alignment | Good | Multiple bar aggregations per instrument are native. |
| F07 Short-horizon momentum/reversal | Best fit for the tool | Most cost-sensitive family; quote-level fills and latency models matter most here. |

Every family still needs: preregistration under our governance, a strategy written against the Nautilus API
(Python on v2 is supported), and a bulk Dukascopy dataset that does not yet exist locally.

## 14. Paper and virtual trading readiness

- **Backtest-venue simulation:** works today (section 12). **[V]**
- **Sandbox (paper on live data):** exists and documents full order-type matching with configurable fill/fee models
  and cash/margin accounts. **[D]** It needs a *live* data source; our IB account lacks FX market-data entitlement,
  and there is no Dukascopy live adapter, so **a sandbox run is blocked today for lack of a live FX feed.** **[U]**
- **IBKR paper via Nautilus:** not tested (Gateway offline, protocol version unverified, open FX issues). **Not
  ready.**
- Nautilus accounts model venue-level balances; our FRONT-1 rule that the EUR 1M IBKR paper balance never sizes
  trades would have to be enforced by configuring a separate virtual EUR 500 sandbox account, not by trusting the
  broker account. **[U]**

## 15. Option A versus Option B

| Dimension | **A: Hybrid** (keep our engine for intelligence/evidence/risk; use Nautilus for backtesting, virtual execution, order management, later adapters) | **B: Nautilus-centered** (Nautilus is the trading runtime; our research/Quant/risk plug in) |
|---|---|---|
| Custom engineering (rough judgment, person-effort) | **~2–3 weeks** for a research-only pilot: Dukascopy→catalog converter (prototyped), real FX instrument specs, one F-family strategy port, results→Neon bridge | **~3–5+ months**: re-home ingestion, TrendSpider, SQL risk gate callouts, FRONT-1 ledger, evidence registry bridge, supervision, IB FX semantics, migration of tests/workflows |
| Execution reliability | Unchanged until we choose to route orders; our fail-closed gate stays authoritative | Potentially stronger order-state/reconciliation, **but** depends on a Rust IB adapter with open FX bugs and an RC runtime |
| Research speed | Fast for intraday tick-level questions we currently cannot test; no disruption to the hourly engine | Slower: everything must be re-expressed on one runtime first |
| Risk to existing work | Low; additive and reversible | High; touches governance-critical pieces (risk gate, ledger, n8n coupling) |
| Fit with constraints | Respects "PostgreSQL is source of truth, n8n orchestrates, SQL gates risk" | Competes with those principles; n8n Cloud cannot drive a local node |
| Dependence on upstream | Limited to a simulator and a data format | Total (breaking v1→v2 changes, RC status, Python 3.12 removal in rc7) |

**Option A requires less custom engineering, carries far less risk, and gets to research progress faster.
Option B is not justified now.** Reconsider B only if 2.0.0 final ships, the IB FX issues close, and A has shown a
measurable research advantage.

## 16. Engineering effort and migration risks

Effort figures are my rough engineering judgment, not measurements.

| Work | Effort | Risk |
|---|---|---|
| Bulk Dukascopy acquisition (existing separate task) | already planned | Prerequisite for any meaningful test |
| Converter to Nautilus catalog + manifest linkage to dataset hashes | 2–3 days | Low; prototype works |
| Real FX instrument specs (IBKR contract details, lot/precision/margin) | 1–2 days | Medium (open price-increment issue #5298) |
| First F-family port + comparison against `fxlake` on overlapping hours | 3–5 days | Low–medium |
| Results → Neon (`experiment_runs` with dataset hash, config hash, engine version) | 2–3 days | Low |
| FX execution wrapper (`cashQty`, avoid exact-quantity BUYs, VirtualFX awareness) if ever routed through Nautilus | 2–4 weeks + paper validation | **High** |
| Porting v2 RC code when 2.0.0 final lands | unknown | Medium: pre-2.0 API still changing |

Principal risks: RC status; v1 being a dead end; Python 3.12 removal in rc7; the IB FX defects; Redis/Postgres
cache-backend gaps; no walk-forward or optimizer; LGPL obligations if we ever distribute modified Nautilus code
(using it as an unmodified library is straightforward; modifications to the library itself must be shared on
distribution); and "unattended" operation needing our own supervision.

## 17. Recommendation: **PILOT**

Narrow, reversible, research-only, Option A.

1. **Pin** `nautilus_trader==2.0.0rc6` in a dedicated virtual environment; keep the existing engine untouched.
2. **Stage gate 1 (no broker, no live data):** after the bulk Dukascopy pull, convert one pair/period to a catalog
   with a manifest tied to our dataset hash, preregister **one** F-family test (F01 or F02 per our priority matrix),
   and compare its fill/cost realism against the bar-based `fxlake` result on overlapping periods. Success means
   reproducible runs and a clear, documented cost-realism difference — not profitability.
3. **Stage gate 2:** results exported into Neon with run/dataset/engine-version identity.
4. **Not yet:** Sandbox on live data (needs a live FX feed), and any IBKR execution through Nautilus. Revisit only
   after `2.0.0` final, closure of #5298/#5299/#5297/#5233, verification of Gateway API protocol ≥213, and a
   separately designed FX wrapper tested on paper with the `cashQty` lessons from our restoration.
5. **Stop criteria:** no measurable advantage over `fxlake` at Gate 1; or 2.0.0 final slips or breaks the API again.

Why not ADOPT: v2 is a release candidate that upstream itself says not to use for real capital, v1 is frozen, the FX
execution path has open defects and does not address the IBKR FX semantics we hit, and our F-series has no tested
strategy to migrate yet. Why not REJECT: the intraday tick-level simulation capability is real, ran against your own
data with an exact Parquet round trip, costs nothing, and fills a genuine gap in the current engine.

## 18. Answers in the requested order

1. Original: https://github.com/nautechsystems/nautilus_trader
2. Fork: https://github.com/EricFinance7/nautilus_trader (named `nautilus_trader`; see section 1)
3. Local path: `E:\Projects\nautilus-trader-eric`
4. Upstream: `upstream` → `https://github.com/nautechsystems/nautilus_trader.git`; `origin` → your fork
5. Forked commit: `3a8e04289896d945598741558374119fd38060ac`
6. Evaluation branch: `research/trading-intelligence-evaluation` (commit SHA reported in the hand-off message)
7. Recommended version: pilot on `2.0.0rc6` (`7b766f8…`); the only non-prerelease is `1.231.0` (`27a8e54…`), a frozen line
8. Asset classes: FX (spot), equities/ETFs, futures, options, crypto (spot/perps/futures/options), betting, prediction markets
9. Relevant broker integrations: Interactive Brokers (only FX-capable broker adapter); Sandbox for simulated execution
10. Dukascopy: no native support; custom converter proven on 7,459 ticks with exact Parquet round trip
11. FAST (F01–F07): expressible; none yet preregistered/backtested; needs bulk data and ports
12. Paper/virtual readiness: backtest simulation ready; Sandbox blocked by no live FX feed; IBKR paper through Nautilus not ready
13. Additional mandatory subscriptions: $0 (optional data/hosting costs unverified)
14. Could replace custom code: event-driven tick/quote simulator and fill/latency/fee models (we have none), parts of
    order-state/reconciliation machinery, Parquet catalog format; not our evidence, governance, risk gate, orchestration or FX semantics
15. Major limitations: RC/frozen-v1 split, IB FX defects and no `cashQty`/VirtualFX handling for FX, no optimizer/walk-forward,
    PostgreSQL cache gaps, no supervisor for unattended runs, Python 3.12 dropped in rc7, no Dukascopy support
16. A vs B: A (hybrid) wins on effort, risk and speed; B not justified now
17. Final recommendation: **PILOT**
