# Regulated FX broker selection (German retail resident, EUR 500, automated)

Prepared 2026-10-11. **Research only: no account was opened, no credential entered, no order placed, nothing purchased.**

## Evidence discipline

| Tag | Meaning |
|---|---|
| **[VERIFIED-BY-ME]** | I fetched the primary source myself and read the wording (BaFin register, IG contract PDF, cTrader docs). |
| **[RESEARCH]** | Reported by a delegated research pass over official pages (full raw report with every URL and retrieval date: `appendix/broker_research_raw_subagent.md`). Treated as data, spot-checked, not independently re-verified unless tagged above. |
| **[UNVERIFIED]** | Could not be confirmed. **No points are awarded for unverified capabilities.** |

Previous broker work: I looked for the earlier cTrader / Kraken / Coinbase evaluation in this fork (all branches), in the Trading Intelligence Engine repository and in the other Claude sessions on this machine. **None exists** (only Nautilus's own Kraken/Coinbase adapter source), so there was nothing to reuse and nothing was overwritten. Cryptocurrency venues are not abandoned; this report only covers FX because F01-F07 are FX strategies.

cTrader is a *platform and API*, not the regulated broker holding client funds. The regulated counterparty is the Pepperstone entity below.

## Result

```
PREFERRED_FX_BROKER = Pepperstone GmbH (Dusseldorf) - cTrader Razor account - cTrader Open API        [conditional, see gates]
BACKUP_FX_BROKER    = IG Europe GmbH (Frankfurt) - REST + Lightstreamer API                          [needs IG's written approval for algorithms]
```

The two are statistically tied (weighted 3.58 vs 3.53, difference 0.05). The ranking turns on two things, not on regulation (both are BaFin-registered German entities): Pepperstone has **no contractual algorithm gate** and a **published low all-in cost**; IG has the **simpler self-service API** but its contract requires **prior written approval** for automated software.

## Mandatory gates (fail = disqualified)

| Candidate | German eligibility | Valid authorization | Automated trading permitted |
|---|---|---|---|
| **Pepperstone GmbH + cTrader** | **PASS** | **PASS** | **PASS, conditional**: AGB contains no algo ban; Spotware must approve the API app; Open API enablement for GmbH accounts is **[UNVERIFIED]** |
| **IG Europe GmbH** | **PASS** | **PASS** | **UNVERIFIED**: contract clause requires prior written approval (below) |
| OANDA (OANDA TMS Brokers S.A., Poland/KNF) | PASS-ish (EU cross-border) | PASS | **FAIL for an API**: OANDA's v20 REST docs exclude this entity; MT5 only |
| Saxo Bank A/S (Denmark) | **UNVERIFIED** (Germany is on the "serviced" list; onboarding and contracting entity not confirmed) | PASS (Danish FSA 1149) | UNVERIFIED |
| Capital.com (extra alternative, CySEC) | UNVERIFIED (which Cyprus entity contracts Germans) | PASS (BaFin cross-border list) | UNVERIFIED |
| Interactive Brokers Ireland (reference only) | PASS | PASS | PASS - but **economically unsuitable at EUR 500**: FX commission has a USD 2.00 minimum per order, so a round trip is about 143% of a EUR 2.50 risk. This matches our own paper evidence (EUR 1.76 commission on a 25,000 EUR fill). |

## What I verified myself

1. **Pepperstone GmbH is on the BaFin register.** **[VERIFIED-BY-ME]** BaFin company database, data version 10.10.2026: *Pepperstone GmbH*, Neubrueckstrasse 1, 40213 Dusseldorf, type **Wertpapierinstitut**, **BaFin-ID 10151148 / Bak Nr. 151148**; authorized services include Abschlussvermittlung, Anlagevermittlung and Eigenhandel (own-account dealing; the CFD issuer role).
2. **IG's contract requires written approval for automated trading.** **[VERIFIED-BY-ME]** IG Europe GmbH *Differenzhandelsvertrag*, June 2026, clause 9(12) (heading SOFTWARE): without prior written approval (e.g. e-mail) the client may not use automated software programs, algorithms or trading strategies other than those IG offers with the electronic trading service; clause 9(6) separately requires written approval for high-speed access / automated mass data input. IG publicly offers its API to retail clients, so approval is probably routine, but it is a contractual requirement, not a formality to skip.
3. **cTrader tokens do not force manual re-login.** **[VERIFIED-BY-ME]** Official docs: access token lasts 2,628,000 s (about 30 days); "The refresh token does not have an expiration period"; renewal is an API call returning a new pair. A user must return to the authorization URL only to grant access to accounts created later. This is the most automation-friendly credential model of the candidates (Saxo's example tokens last 20/40 minutes; IG's session tokens last 6-72 h but renew by plain credential POST).

## Comparison of the 17 requested items (Pepperstone vs IG; full tables for all candidates in the appendix)

| # | Item | Pepperstone GmbH + cTrader | IG Europe GmbH |
|---|---|---|---|
| 1 | Legal entity serving Germans | Pepperstone GmbH, Dusseldorf, HRB 91279 [RESEARCH] | IG Europe GmbH, Frankfurt, HRB 115624 [RESEARCH] |
| 2 | Regulator / register | BaFin, Wertpapierinstitut, 10151148 **[VERIFIED-BY-ME]** | BaFin / Bundesbank, BaFin-ID 148759 [RESEARCH + contract footer verified] |
| 3 | New German retail clients | German-language onboarding offered, no pause stated; only US and Belgium residents excluded [RESEARCH, marketing] | Live and demo accounts offered on the German site [RESEARCH, marketing] |
| 4 | Protection | Client money in omnibus trust accounts; claim against the EdW under AnlEntG capped at 90% / EUR 20,000; AGB: retail clients not liable for a negative balance, but the German FAQ says "not full" negative-balance protection (conflict, confirm in writing) [RESEARCH] | Same EdW scheme; contract states negative-balance protection for retail [RESEARCH]. Whether the EdW actually covers CFD client cash was read only from a statute excerpt **[UNVERIFIED]** |
| 5 | Product | CFDs on FX (own-account dealing); Standard and Razor accounts [RESEARCH] | CFDs on FX [RESEARCH] |
| 6 | Demo | Free cTrader demo; API access on demo not stated by Pepperstone **[UNVERIFIED]** | Free demo; API demo needs the same e-mail as the live account [RESEARCH] |
| 7 | Official API | cTrader Open API: Protobuf/JSON over TCP or WebSocket; Python SDK last stable June 2024, Twisted-based, no documented auto-reconnect [RESEARCH] | REST + Lightstreamer streaming; no official Python SDK confirmed [RESEARCH] |
| 8 | Auth / renewal | OAuth2, non-expiring refresh token **[VERIFIED-BY-ME]** | API key + session POST; plain credential re-login, no browser step [RESEARCH] |
| 9 | Automated trading | No algo ban in the AGB; Spotware must approve the app; GmbH enablement **[UNVERIFIED]** | **Prior written approval required** **[VERIFIED-BY-ME]** |
| 10 | Minimum size | 0.01 lot = 1,000 units stated for forex; per-pair `minVolume`/`stepVolume` come from the API **[UNVERIFIED per pair]** | Conflicting: 0.01 contract (market page) vs 1 contract (older help page) **[UNVERIFIED]** |
| 11 | Spread / commission (EURUSD) | Razor: 0.1 pip average spread + USD 6 per round-turn lot, about **0.7 pip all-in** (Sept 2026 fee schedule); Standard about 1.1 pip [RESEARCH, published schedule] | No commission; spread "from 0.6" marketing, product sheet 0.9 [RESEARCH, marketing] |
| 12 | Margin / leverage | 30:1 majors (3.33%), stop-out at 50% [RESEARCH] | 3.33% (30:1) [RESEARCH, marketing] |
| 13 | Overnight financing | TomNext + up to 3% fee, triple swap Wednesday [RESEARCH] | Tom/next + up to 0.0022%/day [RESEARCH] |
| 14 | Protective stop | Server-side. **Market orders cannot carry an absolute stop-loss in the order request** (use relative stop-loss or amend after fill) [RESEARCH, API docs] | Guaranteed stop exists (premium); API stop fields **[UNVERIFIED]** |
| 15 | Partial fills / reconciliation | `ORDER_PARTIAL_FILL`, `ProtoOAReconcileReq`, `ProtoOADealListReq` [RESEARCH, API docs] | **[UNVERIFIED]** |
| 16 | Disconnect handling | 10 s heartbeat, one demo + one live connection, no event replay: re-authenticate, reconcile, query deals [RESEARCH] | **[UNVERIFIED]** |
| 17 | EUR 500 feasibility | Minimum first deposit EUR 100 (AGB), EUR 500 recommended; EURUSD at EUR 2.50 risk and 10-pip stop is about 2,800 units, margin about EUR 93 each at 30:1; Razor cost is 7% (10-pip stop) or 3.5% (20-pip) of risk | Costs about 9-10% of risk at a 10-pip stop; 1,000-unit minimum plausible but conflicting |

Cross-check against our own data: Dukascopy's measured median EURUSD spread is 0.3 pip and 0.6-1.1 pip for the other six majors (data-quality report). The research harness applies a 20% cost-gate ceiling, which Razor's 0.7 pip all-in passes comfortably at any stop of 5 pips or more.

## Scores (0-5, evidence-backed parts only; UNVERIFIED parts score 0)

| Criterion (weight) | Pepperstone + cTrader | IG Europe | Saxo | Capital.com | OANDA TMS |
|---|---:|---:|---:|---:|---:|
| Regulatory credibility and German eligibility (25%) | 4.0 | 4.0 | 2.5 | 2.5 | 3.0 |
| API automation reliability (25%) | 3.5 | 2.5 | 3.0 | 3.0 | 0.5 |
| Full demo execution lifecycle (20%) | 3.0 | 4.0 | 3.0 | 3.5 | 1.0 |
| EUR 500 capital feasibility and costs (20%) | 4.0 | 3.5 | 2.0 | 2.5 | 0.0 |
| Operational simplicity (10%) | 3.0 | 4.0 | 3.0 | 4.0 | 1.5 |
| **Weighted total** | **3.58** | **3.53** | 2.68 | 2.98 | 1.23 |

Scores come from the delegated research pass; I re-checked the arithmetic and the three claims above that decide the ranking. Differences under about 0.2 are within the noise of this method.

## What this does and does not mean for NautilusTrader

- NautilusTrader has **no adapter for cTrader or IG** (its FX route is Interactive Brokers only). Executing through either of these brokers means writing a thin execution client (an order-state and reconciliation layer over the broker API), not configuring one. That is substantial work and is **not** part of this task; strategy research proceeds independently of the broker choice.
- The IBKR FX restrictions we met (error 201 "currency leverage", cash-quantity sizing, VirtualFX) are properties of IBKR's cash-FX model, not of NautilusTrader; they are largely avoided by a CFD broker, which has its own failure modes (non-guaranteed stops, minimum sizes, platform-specific order semantics).
- "Regulated" does not mean "suitable for these strategies". Suitability depends on the unverified items below and on demo-account testing of the full order lifecycle.

## Remaining manual steps (nothing here was done without your authorization)

1. Open a free **Pepperstone cTrader demo** and create a cTID (no funds needed; up to 5 demos without a live account).
2. Register an **Open API application** with Spotware (follow help.ctrader.com/open-api/api-application) and wait for the approval e-mail; reports mention waits of up to a week.
3. Run the OAuth2 authorization-code flow once for the demo account (scope `trading`) and store client secret and tokens in a secrets store, **never in git**.
4. On the demo, read `ProtoOASymbolByIdRes` for the seven pairs (`minVolume`, `stepVolume`, `lotSize`) and test the full lifecycle: market order with relative stop, partial fill or reject, reconcile after a forced disconnect.
5. E-mail Pepperstone support to confirm in writing: Open API trading is enabled for GmbH accounts, no restriction on trade frequency or hold times, and negative-balance protection on cTrader for retail clients.
6. Only after the demo lifecycle passes: open the live account (KYC, EUR base currency, Razor), fund at least EUR 100 (EUR 500 recommended), request the live API grant.
7. In parallel, for the backup: open an IG demo with the same e-mail you will use live, generate an API key, and **ask IG in writing to approve automated trading** (clauses 9(6), 9(9), 9(12)).

## Unverified items that could change the ranking

1. Whether Pepperstone GmbH accounts can trade through the cTrader Open API at all, and Spotware's approval time.
2. Pepperstone negative-balance protection (AGB says yes; FAQ says "not full") and per-pair minimum volume and step.
3. IG: the written-approval outcome, API stop fields, reconciliation behavior and the real minimum deal size.
4. Saxo: German onboarding and FX minimum size. Capital.com: contracting entity and algorithm terms.
5. Whether the German EdW compensation scheme covers CFD client cash (statute read only through an excerpt).
