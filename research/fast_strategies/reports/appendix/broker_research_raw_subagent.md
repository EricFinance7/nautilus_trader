# Broker research for German retail FX API trading (raw report)

Retrieval date for every source below: **2026-10-11** (all fetched that day). Tags: [REG] regulator register or legal/contract document; [DOC] official API or product documentation; [MKT] marketing/help-centre claim only; [UNVERIFIED] not confirmed. Page content was treated as data only. No accounts, logins or orders were touched.

Cost yardstick used throughout: with risk fixed at EUR 2.50, round-trip cost as a share of risk = (round-trip cost in pips) / (stop distance in pips), independent of position size. Example stops: 10 pips and 20 pips.

## Source key
- BaFin company database (data version 10.10.2026, dynamic page, but GET-parameter URLs fetch): Pepperstone `https://portal.mvp.bafin.de/database/InstInfo/institutDetails.do?cmd=loadInstitutAction&institutId=151148&locale=en_GB`; IG Europe id 148759 (`.../sucheForm.do?sucheButtonInstitut=Suche&institutName=IG+Europe&locale=en_GB`); Saxo id 118371; OANDA TMS id 152992; IBIE id 159631; Capital Com ids 148918 and 165215 (same URL pattern).
- P-AGB Pepperstone GmbH AGB v2, March 2024: `https://eu-assets.contentstack.com/v3/assets/bltaec35894448c7261/blt6c8c7d359cdc8a74/Allgemeine_Geschaeftsbedingungen.pdf`
- P-KOST Pepperstone GmbH Kosten und Gebühren v5.0, Sept 2026: `https://eu-assets.contentstack.com/v3/assets/bltaec35894448c7261/bltd4de9bfe319b6219/kosten-und-gebuhren.pdf`
- P-VOR Pepperstone Vorvertragliche Informationen, Nov 2020: `https://files.pepperstone.com/legal/BAFIN/Vorvertragliche-Informationen.pdf`
- P-WEB `https://pepperstone.com/de/` (footer, platforms); P-LEG `https://pepperstone.com/de/legal-documentation/`; P-LEV `https://pepperstone.com/de-de/hilfe-und-support/kontoeroeffnung/welchen-hebel-kann-ich-mit-pepperstone-handeln/`; P-FAQ `https://pepperstone.com/de-de/support/faq/`; P-DEMO `https://pepperstone.com/en/ways-to-trade/demo-accounts/`
- cTrader Open API (help.ctrader.com/open-api/): C-HOME `/`, C-AUTH `/account-authentication/`, C-APP `/api-application`, C-NEW `/creating-new-app/`, C-CONN `/connection/`, C-ENDP `/proxies-endpoints/`, C-MSG `/messages/`, C-MODEL `/model-messages/`, C-TOS `/terms-of-use/`; C-PYPI `https://pypi.org/pypi/ctrader-open-api/json`; C-GH `https://github.com/spotware/OpenApiPy`
- Saxo: S-LIC `https://www.home.saxo/legal/saxo-bank-licenses/saxo-bank-license-details`; S-DISC `https://www.home.saxo/legal/disclaimer/saxo-disclaimer`; S-IND `https://www.home.saxo/accounts/individual`; S-CTRY `https://www.help.saxo/hc/en-us/articles/10611416570269-Which-countries-are-serviced-by-Saxo`; S-KID Rolling FX Spot KID (Jan 2023) `https://www.home.saxo/en-ch/-/media/documents/key-information-documents/products/fx-spot-kid.pdf/1000`; S-SPR `https://www.home.saxo/rates-and-conditions/forex/spreads-and-commissions`; developer.saxo/openapi/learn/ pages: S-ENV `environments`, S-SEC `security`, S-OAUTH `oauth-authorization-code-grant`, S-RATE `rate-limiting`, S-ORD `order-placement`, S-STR `streaming`, S-EVT `order-events`, S-LIVE `direct-clients-request-for-openapi-application-credentials-for-the-live-environ`
- OANDA: O-EU `https://www.oanda.com/eu-de/`, O-V20 `https://developer.oanda.com/rest-live-v20/introduction/`, O-INFO `https://cdn.tms.pl/sites/default/files/documents/06-02-2026/karta_informacyjna_o_oanda_tms_2026_02_06.pdf`
- IG: G-API `https://www.ig.com/de/handelsplattformen/apis`, G-HOW `https://www.ig.com/de/handelsplattformen/apis/wie-werden-ig-apis-verwendet`, G-REST `https://labs.ig.com/rest-trading-api-guide.html`, G-AGR IG Europe Differenzhandelsvertrag June 2026 `https://www.ig.com/usermanagement/customeragreements?igCompany=igde&agreementType=customer_agreement&productCode=IGCFD&locale=de_DE&legalEntity=IGE`, G-EUR `https://www.ig.com/de/forex/maerkte-forex/eur-usd`, G-FX `https://www.ig.com/de/hilfe-und-support/cfds/kosten-und-gebuehren/wie-lauten-die-cfd-produktinformationen-fuer-forex`
- Capital.com: K-API `https://open-api.capital.com/`, K-WEB `https://capital.com/de`, K-PRICE `https://capital.com/en-int/ways-to-trade/pricing`
- IBKR: I-COM `https://www.interactivebrokers.ie/en/pricing/commissions-spot-currencies.php`
- German statute AnlEntG §4 (EdW 90% / EUR 20,000): `https://www.gesetze-im-internet.de/eaeg/__4.html` (seen only via search excerpt, not fetched)

---

## A) Pepperstone GmbH + cTrader Open API

| # | Item | Finding | Tag / source |
|---|---|---|---|
| 1 | Entity | **Pepperstone GmbH**, Neubrückstr. 1, 40213 Düsseldorf, Germany; HRB 91279 (Düsseldorf). Note: the 2020 pre-contract paper cites "Handelsregister Berlin HRB 190318B"; the 2024-26 documents use HRB 91279. | [REG] BaFin DB; P-AGB; P-KOST; P-VOR |
| 2 | Regulator / register | BaFin, "Wertpapierinstitut", BaFin-ID 10151148 / Bak Nr 151148, status active in data version 10.10.2026. Authorisations (WpIG): Anlagevermittlung (§2(2) Nr.3), Abschlussvermittlung (§2(2) Nr.5), Eigenhandel (§2(2) Nr.10), valid since 26.06.2021 (KWG predecessors since 04.08.2020). The group's separate EEA entity Pepperstone EU Ltd (CySEC 388/20) is not the German contract party. | [REG] BaFin DB; Pepperstone EU Ltd from `https://pepperstone.com/en-eu/legal-documentation` |
| 3 | New German retail clients | German-language sign-up offered, no stated pause; only US and Belgium residents are excluded. No explicit "we accept new German clients" statement found. | [MKT] P-WEB, P-VOR |
| 4 | Protection | Client money held in omnibus trust accounts (Sammeltreuhandkonten), segregated from firm money, not per client. Insolvency: claim against EdW under AnlEntG; statute caps at 90% of claim and EUR 20,000 (EUR/EEA-currency amounts only). **Negative-balance protection:** AGB says retail clients are not liable for a negative balance (excludes fees). Conflict: the German FAQ says non-FCA clients are "not protected by full negative balance protection". The signed contract (AGB) governs; confirm in writing. | [REG] P-AGB (A.II.1.b, A.II.6.f), P-VOR (m), AnlEntG §4; [MKT] P-FAQ |
| 5 | Product | CFDs (Differenzkontrakte) on FX, issued by Pepperstone GmbH (own-account dealing). Accounts: Standard and Razor. | [REG] P-VOR, P-KOST |
| 6 | Demo | Free cTrader demo, unlimited virtual balance, top-up in cTrader; up to 5 demos without a live account, 10 with. Expiry statements conflict (DE FAQ: 30 days; EN page: cTrader 90 days inactivity). API access on the demo is not stated by Pepperstone. | [MKT] P-DEMO, P-FAQ |
| 7 | API | cTrader Open API: Protobuf (port 5035) or JSON (5036) over SSL TCP or WebSocket; live `live.ctraderapi.com`, demo `demo.ctraderapi.com`. Official SDKs C# and Python (OpenApiPy, MIT, Twisted+protobuf; last stable 0.9.2 on 2024-06-26, 0.9.3 yanked). Python SDK has no WebSocket and no documented auto-reconnect. Open to "anyone registered with a cTrader-affiliated broker"; Pepperstone GmbH lists cTrader. No NautilusTrader adapter. | [DOC] C-HOME, C-CONN, C-ENDP, C-PYPI, C-GH; [MKT] P-WEB |
| 8 | Auth | OAuth2 authorization code (scope `trading`); code valid 1 min; access token 2,628,000 s (~30 days); **refresh token has no expiry**; refresh via HTTP `apps/token` or `ProtoOARefreshTokenReq`, issues new access+refresh pair and invalidates old. New accounts need re-grant. Manual login only for first grant (and if user revokes: not documented). | [DOC] C-AUTH |
| 9 | Automated trading permitted | AGB contains no ban on algorithmic trading; only a clause against manipulation, latency abuse, arbitrage (A.II.4.e) and market abuse via algo trading. DE FAQ says Expert Advisors allowed. Open API requires a registered app **approved by Spotware** (email decision; community reports of week-long waits; new apps may start in demo-only mode). Open API terms: app must not trade for a trader without his explicit prior approval (satisfied for own account). No Pepperstone approval step found. Whether Pepperstone GmbH accounts are actually enabled for Open API trading: not documented anywhere I could reach. | [REG] P-AGB; [MKT] P-FAQ; [DOC] C-APP, C-NEW, C-TOS; [UNVERIFIED] Pepperstone-specific Open API enablement |
| 10 | Min size / step | cTrader volume is in 0.01 units; per-symbol `minVolume`, `stepVolume`, `maxVolume`, `lotSize` come from `ProtoOASymbol`. Pepperstone states a 0.01 lot (1,000 units) minimum for forex and 100 lots max per trade; per-symbol values for the seven pairs not read. | [DOC] C-MODEL; [MKT] P-FAQ (max), search excerpt (0.01 lot min); [UNVERIFIED] per-pair values |
| 11 | Spread / commission EURUSD | Published illustrative table (Sept 2026): Razor min 0.0 / avg 0.1 pip; Standard min 1.0 / avg 1.1 pip. cTrader Razor commission USD 3 per side per 100k (USD 6 round turn = 0.6 pip). All-in Razor about **0.7 pip**, Standard about **1.1 pip**. Cost/risk: Razor 7% (10-pip stop) or 3.5% (20-pip); Standard 11% / 5.5%. Figures are illustrative examples, not guarantees. | [REG] P-KOST |
| 12 | Margin / leverage | German retail: 30:1 majors (3.33%), 20:1 non-major pairs, gold, major indices; 10:1 other commodities; 5:1 shares; 2:1 crypto. cTrader margin call at <100%, stop-out at <=50% for retail. | [MKT] P-LEV; [REG] P-AGB (A.II.6 "bb) cTrader") |
| 13 | Swap | Forex swap = TomNext rate from liquidity providers plus financing fee of TomNext x up to 3%; rollover 17:00 New York; triple swap Wednesday (USDCAD Thursday). Platform "Specifications" tab shows live rates. | [REG] P-KOST |
| 14 | Protective stop | `ProtoOANewOrderReq`: absolute `stopLoss`/`takeProfit` **not supported on MARKET orders**; use `relativeStopLoss` (1/100000 price units) or amend after fill; LIMIT/STOP orders accept absolute SL/TP. `trailingStopLoss` flag exists. `guaranteedStopLoss` only for Limited Risk accounts. Server-side. Name of the amend-SL message not read. | [DOC] C-MSG; [UNVERIFIED] amend message, Pepperstone GSL availability |
| 15 | Partial fills / reconciliation | `ProtoOAExecutionType` includes ORDER_PARTIAL_FILL, ORDER_FILLED, ORDER_REJECTED, SWAP; `ProtoOAReconcileReq/Res` returns open positions and pending orders (optionally protection orders); `ProtoOADealListReq` by time window; `ProtoOAGetPositionUnrealizedPnLReq`; `isServerEvent` flags stop-outs. | [DOC] C-MSG, C-MODEL |
| 16 | Disconnect handling | Send `ProtoHeartbeatEvent` every 10 s; max one demo and one live connection; rate limit 50 req/s (5/s historical); reconnect logic is the client's job; no event replay: after a gap, re-auth, reconcile, deal-list query. | [DOC] C-HOME, C-CONN |
| 17 | EUR 500 feasibility | Minimum first deposit EUR 100 in AGB (March 2024); FAQ says no minimum, EUR 500 recommended. No inactivity fee, no deposit/withdrawal fee. Sizing at EUR 2.50 risk and 10-pip stop: about 2,800 units; margin about EUR 93 each at 30:1, about EUR 280 for three (56% of equity), tight but workable; 20-pip stops halve this. Costs per yardstick above (3.5-7% Razor). | [REG] P-AGB, P-KOST; [MKT] P-FAQ |

**Verdict A.** Pepperstone GmbH is the only candidate where regulator register (BaFin Wertpapierinstitut), contract (no algo ban, retail negative-balance protection in the AGB) and published fee schedule (Razor cTrader about 0.7 pip all-in, Sept 2026) all check out from primary documents. The cTrader Open API is the cleanest protocol of the set (Protobuf/WebSocket, non-expiring refresh token, reconcile request), but three frictions are real: Spotware must approve the app, market orders cannot carry an absolute stop in the order request, and the Python SDK is stale (June 2024) and Twisted-based, so expect to write a thin reconnecting client. Unconfirmed: Pepperstone-specific Open API enablement and per-symbol minimum volumes.

---

## B) Saxo Bank + Saxo OpenAPI

| # | Item | Finding | Tag / source |
|---|---|---|---|
| 1 | Entity | **Saxo Bank A/S**, Hellerup, Denmark (CVR 15731249, LEI 549300TL5406IC1XKD09). Saxo says contracts are with "the relevant Saxo entity based on country of residence"; no German entity or branch named (branches: UAE, CZ, FR, BE, NL). The entity for a German resident is not stated. | [REG] S-LIC, S-DISC; [UNVERIFIED] contracting entity for Germans |
| 2 | Regulator / register | Danish FSA, licence no. 1149. BaFin DB lists Saxo Bank A/S as cross-border service provider (KI) under §53b KWG, so Danish bank may serve Germany. Danish FSA register not fetched. | [REG] S-LIC, BaFin DB |
| 3 | New German clients | Germany is on the "countries we service" list, but Saxo warns this may differ from countries it onboards; no German locale/legal page found; account-opening country list not reachable. | [DOC] S-CTRY; [UNVERIFIED] German onboarding |
| 4 | Protection | Danish Guarantee Fund: EUR 100,000 deposits; EUR 20,000 investor compensation if instruments are not returned. Scope is described for Saxo Bank A/S and named branches; Germany not named. Retail FX Spot has negative-balance protection. | [DOC] S-DISC, web search of home.saxo; [REG] S-KID |
| 5 | Product | "Rolling FX Spot": margin contract on currency pairs, KID (Jan 2023) issued by Saxo Bank A/S; Saxo's pricing page calls spot FX a CFD for retail. | [REG] S-KID; [DOC] S-SPR |
| 6 | Demo | SIM environment with simulated USD 100,000; separate keys and endpoints; 24-hour test token from portal; "reporting and market data not available" in SIM; low priority for SIM issues. Expiry of demo account not stated. | [DOC] S-ENV, S-SEC |
| 7 | API | REST plus WebSocket streaming (binary, optional Protobuf); portal developer.saxo; no official Python SDK found (samples only). | [DOC] S-STR, learn page |
| 8 | Auth | OAuth2 code grant (server apps) or PKCE; example access token 20 min, refresh token 40 min (example values); refresh issues new pair and invalidates old; streaming socket needs explicit token re-authorize PUT. Certificate (server-to-server) auth **not offered to retail**. Refresh expiry means an outage longer than the refresh lifetime forces a manual login. | [DOC] S-OAUTH, S-SEC, S-STR |
| 9 | Automated trading | Direct retail clients can request a LIVE app: needs at least one SIM app, a funded live account; "in most cases handled automatically within minutes", some manual review; apps are monitored for error rates. Contract text for algorithmic trading not read (German AGB is for another entity). | [DOC] S-LIVE; [UNVERIFIED] contractual terms |
| 10 | Min size | Not stated; page says per-pair info button. KID example uses 10,000 EUR; Swiss CFD page cites 5,000 for forex CFDs (different entity). | [UNVERIFIED] |
| 11 | Spread / commission | Classic tier "1 pip" majors (Platinum 0.9, VIP 0.7); KID example EURUSD spread 0.0001; no FX commission. About 10% of risk at 10-pip stop. | [MKT] S-IND; [REG] S-KID example |
| 12 | Margin / leverage | KID example EURUSD initial margin 3.33%, maintenance 1.67%; ESMA 30:1 majors. | [REG] S-KID |
| 13 | Swap | Tom/Next points from Tier-1 rates with client mark-up +/-0.75% (Classic, from 1 Nov 2025) plus financing on unrealised P/L at overnight rate +/-2.00%; roll 17:00 EST. | [DOC] S-SPR |
| 14 | Protective stop | Place entry order with `Orders` array of related orders (limit plus stop, up to 3); entry types Market/Limit/Stop/StopLimit; a trailing stop is implied by the `TrailingStopOrderMove` event status but its order placement was not read. Guaranteed stop: not found. Errors: OrderRelatedPositionMissMatch, TooFarFromMarket, etc. | [DOC] S-ORD, S-EVT |
| 15 | Partial fills / reconcile | Status `Fill` (partial) vs `FinalFill`, `FilledAmount`, `AveragePrice`; positions vs NetPositions; `TradeNotCompleted` means check Portfolio before retry; duplicate protection via `x-request-id` (identical POST within 15 s rejected). | [DOC] S-EVT, S-ORD |
| 16 | Disconnect | `_heartbeat`, `_resetsubscriptions`, `_disconnect`; reconnect with same ContextId and last `messageid` gives limited replay from a small buffer, not guaranteed. | [DOC] S-STR |
| 17 | EUR 500 | No minimum funding to open; min FX size UNVERIFIED; about 10% of risk spread cost; rate limits 120 req/min per service group per session, 1 order/s. | [MKT] S-IND; [DOC] S-RATE; [UNVERIFIED] min size |

**Verdict B.** Best-documented API and strong regulation as a Danish bank, but two gates cannot be passed on evidence: I could not confirm Saxo currently onboards German residents, or which entity contracts with them, and the FX minimum size and algorithmic-trading contract terms are unread. The 20/40-minute example token lifetimes and no retail certificate auth make unattended multi-day operation fragile. Keep as a candidate only if the operator can reach the account-opening form with Germany selectable.

---

## C) OANDA (OANDA TMS Brokers S.A.)

| # | Item | Finding | Tag / source |
|---|---|---|---|
| 1 | Entity | **OANDA TMS Brokers S.A.**, Warsaw (KRS 0000204776). OANDA Europe Markets Ltd (Malta) closed March 2023. | [REG] O-EU, O-INFO |
| 2 | Regulator | KNF (Poland), licence KPWiG-4021-54-1/2004 (26 Apr 2004). BaFin DB lists "OANDA TMS Brokers Spółka Akcyjna" as cross-border provider (§74 WpIG). KNF register not fetched. | [REG] O-EU, BaFin DB |
| 3 | New German clients | Company sheet says it serves residents of any EU member state, restrictions concern RU/BY for Stocks only; German-language site exists; no Germany-specific onboarding statement. | [REG] O-INFO; [UNVERIFIED] practical onboarding |
| 4 | Protection | KDPW compensation system: 100% of first EUR 3,000, then 90% of the excess, cap EUR 22,000 (PLN equivalent); client money at domestic banks. Negative-balance protection not read. | [REG] O-INFO; [UNVERIFIED] NBP |
| 5 | Product | Leveraged CFDs/FX on MT5 and mobile app; TradingView integration. | [DOC] O-EU |
| 6 | Demo | Free demo account offered. API on demo: none. | [MKT] O-EU |
| 7 | API | OANDA's v20 REST docs state v20 accounts are available to all divisions **except OANDA Global Markets and OANDA TMS BROKERS S.A.** So no REST API for this entity. Only MT5. | [DOC] O-V20 |
| 8 | Auth | n/a (no API). | n/a |
| 9 | Automated trading | MT5 Expert Advisors presumably possible; contract not read. | [UNVERIFIED] |
| 10-17 | Min size, spreads, margin, swap, stops, reconcile, disconnect, EUR 500 | Not researched beyond the API exclusion because it disqualifies the entity for this project. | [UNVERIFIED] |

**Verdict C.** Eligibility and authorisation look fine, but the official OANDA REST API is explicitly not offered to the EU entity serving Germans, leaving only MT5, which is not a broker API. Fails the stated API requirement.

---

## D) IG Europe GmbH + IG REST/Streaming API

| # | Item | Finding | Tag / source |
|---|---|---|---|
| 1 | Entity | **IG Europe GmbH**, Westhafenplatz 1, 60327 Frankfurt, HRB 115624. | [REG] G-API footer, G-AGR |
| 2 | Regulator | BaFin/Bundesbank; BaFin DB: type Wertpapierinstitut and Kryptowertedienstleister, BaFin-ID 148759. Authorisation list not opened. | [REG] BaFin DB; G-AGR |
| 3 | New German clients | German site offers live and demo accounts, ID verification usually instant; no pause stated. | [MKT] G-API |
| 4 | Protection | Contract (June 2026): EdW coverage; client money in open collective trust accounts. Retail clients cannot lose more than funds on account and need make no additional payment (negative-balance protection). EdW cap 90% / EUR 20,000. | [REG] G-AGR; AnlEntG §4 |
| 5 | Product | CFDs on FX (also spread-bet-style products not for DE), provider IG Europe GmbH. | [REG] G-AGR |
| 6 | Demo | Free demo; to use API on demo the demo must use the **same email as the live account**. | [MKT] G-API, G-HOW |
| 7 | API | REST (JSON) at `api.ig.com/gateway/deal` (demo `demo-api.ig.com`), Streaming via Lightstreamer; FIX only institutional; Python usable (only third-party libraries seen, no official SDK confirmed). | [DOC] G-REST, G-HOW |
| 8 | Auth | API key from account settings plus `POST /session`: v1/v2 tokens (CST, X-SECURITY-TOKEN) valid 6 h, extended while in use up to 72 h; v3 OAuth access token ~60 s with refresh token (~10 min after expiry); re-login is a plain credential POST (needs stored credentials, no browser step). | [DOC] G-REST |
| 9 | Automated trading | **Contract clause 9(12): without prior written approval (e.g. email) the client may not use automated software, algorithms or trading strategies other than those IG Europe offers with the electronic trading service; clause 9(6): automated mass data input / high-speed access only with prior written approval; clause 9(9): custom interface requires IG's prior written consent.** IG publicly offers the REST API to retail, which suggests approval is routine, but the contract requires it in writing. | [REG] G-AGR (Ziffer 9); [MKT] G-API |
| 10 | Min size | Market page: min 0.01 contract, contract size EUR 100,000 (i.e. 1,000 units). Older help page: min 1 contract (mini contract 10,000). Conflict; the API instrument details would settle it. | [MKT] G-EUR vs G-FX; [UNVERIFIED] |
| 11 | Spread / commission | No commission. Spread claims "from 0.6" (market page); product sheet min 0.9, average 0.9 / 1.04 (data to Jan 2021, stale). About 9-10% of risk at 10-pip stop. | [MKT] G-EUR, G-FX |
| 12 | Margin | 3.33% (30:1) retail, steps to 6% above large sizes. | [MKT] G-EUR |
| 13 | Swap | Tom/next rate on contract size plus IG charge up to 0.0022%/day; three-day adjustment Wednesday. | [MKT] G-FX |
| 14 | Protective stop | Guaranteed stop exists (min distance 2.0%, premium 1.2 pts if triggered); standard min stop distance 10. API parameters for attaching stops/trailing not read this session. | [MKT] G-EUR, G-FX; [UNVERIFIED] API fields |
| 15-16 | Partial fills, reconciliation, disconnect | Not read this session (Lightstreamer trade-update subscription and deal confirmation exist but were not verified). | [UNVERIFIED] |
| 17 | EUR 500 | No minimum deposit stated; costs about 9-10% of risk at 10-pip stop; 1,000-unit minimum plausible but conflicting. | [MKT] |

**Verdict D.** Strong German footing (BaFin, EdW, contractual negative-balance protection) and the simplest self-service API access (key from account settings, no third-party app approval, demo with same email). The decisive issue is contractual: the June 2026 agreement requires IG's prior written approval for algorithmic or automated trading and for custom interfaces, so the "automated trading permitted" gate stays UNVERIFIED until IG confirms in writing. Costs are modestly above Pepperstone Razor.

---

## E) Alternative checked: Capital.com (Capital Com SV Investments Ltd / Capital Com Group Ltd, CySEC)

| Item | Finding | Tag / source |
|---|---|---|
| Entity / register | Footer names two Cyprus companies: SV Investments Ltd (HE 354252, CySEC 319/17) and Group Ltd (HE 446198, CySEC 463/25). Both appear in BaFin DB as cross-border service providers (SV 2017; Group 03/03/2026). Which one contracts Germans: not stated. | [REG] BaFin DB; [MKT] K-WEB; [UNVERIFIED] contracting entity |
| German onboarding / protection | German site exists; CySEC ICF EUR 20,000 plus USD 1m private insurance since June 2025 reported. NBP not read. | [MKT] K-WEB, press via search; [UNVERIFIED] |
| API | Official REST + WebSocket; live `api-capital.backend-capital.com`, demo `demo-api-capital.backend-capital.com`; API key from Settings (2FA); `POST /session` yields CST + X-SECURITY-TOKEN valid 10 min of inactivity (re-POST renews, no browser); 10 req/s, 1 order per 0.1 s, `POST /session` 1/s; WebSocket 40 instruments, ping <=10 min. Stop via `stopLevel/stopDistance/stopAmount`, `guaranteedStop`, `trailingStop`; confirm via `GET /confirms/{dealReference}`. | [DOC] K-API |
| Costs | EURUSD example spread 0.6 pip, no commission; 0.7% conversion fee when instrument currency differs from account currency; swap = benchmark +/- daily fee. | [MKT] K-PRICE |
| Min size, automated-trading terms, reconcile, disconnect detail | Not confirmed (help article blocked). | [UNVERIFIED] |

Capital.com has the lowest API friction and no app approval, but the contracting entity for Germans, algo terms and min size are all unconfirmed, and it is a CFD dealer whose costs depend on marketing spreads.

## F) Reference only: Interactive Brokers Ireland (IBIE)

IBIE appears in BaFin DB as cross-border provider (§74 WpIG) [REG]. FX spot commission: 0.20 bp of trade value, **minimum USD 2.00 per order** [DOC, I-COM]. A round trip is therefore at least USD 4 (about EUR 3.6), i.e. about 143% of a EUR 2.50 risk unless the notional exceeds about USD 100,000 per order. This confirms the economic problem you already saw; no scoring.

---

## Gates (fail = disqualified)

| Candidate | German eligibility | Valid authorisation | Automated trading permitted |
|---|---|---|---|
| Pepperstone GmbH + cTrader | **PASS** ([REG] BaFin entry; new-client acceptance [MKT]) | **PASS** [REG] | **PASS (conditional)**: no ban in AGB; Spotware app approval and Pepperstone Open API enablement still to confirm |
| Saxo Bank A/S | **UNVERIFIED** (serviced list yes, onboarding not confirmed) | PASS [REG] (Danish FSA, BaFin cross-border) | UNVERIFIED (contract unread; live app mostly automatic) |
| OANDA TMS Brokers S.A. | PASS-ish (EU residents served, BaFin cross-border) | PASS [REG] | **FAIL** for API requirement (v20 excluded); EA on MT5 UNVERIFIED |
| IG Europe GmbH | **PASS** | **PASS** [REG] | **UNVERIFIED**: contract demands prior written approval |
| Capital.com (alt.) | UNVERIFIED entity, cross-border listed | PASS [REG] BaFin list / CySEC licence | UNVERIFIED |

## Scores (0-5; UNVERIFIED parts score 0 for the part they cover and are flagged)

| Criterion (weight) | Pepperstone+cTrader | Saxo | OANDA TMS | IG Europe | Capital.com |
|---|---|---|---|---|---|
| Regulatory credibility and German eligibility (25%) | 4.0 | 2.5 (German onboarding UNVERIFIED) | 3.0 | 4.0 | 2.5 (entity UNVERIFIED) |
| API automation reliability (25%) | 3.5 | 3.0 | 0.5 | 2.5 (written-approval clause) | 3.0 (terms UNVERIFIED) |
| Full demo execution lifecycle (20%) | 3.0 | 3.0 | 1.0 | 4.0 | 3.5 |
| EUR 500 feasibility and costs (20%) | 4.0 | 2.0 (min size UNVERIFIED) | 0.0 (UNVERIFIED) | 3.5 | 2.5 (min size UNVERIFIED) |
| Operational simplicity (10%) | 3.0 | 3.0 | 1.5 | 4.0 | 4.0 |
| **Weighted total** | **3.58** | **2.68** | **1.23** | **3.53** | **2.98** |

Arithmetic (weighted parts): Pepperstone 1.00+0.875+0.60+0.80+0.30 = 3.575; Saxo 0.625+0.75+0.60+0.40+0.30 = 2.675; OANDA 0.75+0.125+0.20+0.00+0.15 = 1.225; IG 1.00+0.625+0.80+0.70+0.40 = 3.525; Capital.com 0.625+0.75+0.70+0.50+0.40 = 2.975.

Scoring notes: Pepperstone and IG are within noise (0.05). Pepperstone wins on published low costs (Razor 0.7 pip) and no contractual algo gate; IG wins on self-service API and demo. Pepperstone's API score is capped by the Spotware approval step and the stale Python SDK; IG's by the written-approval clause.

## Recommendation

- **PREFERRED: Pepperstone GmbH, cTrader Razor account, cTrader Open API (Protobuf/JSON over WebSocket or TCP).** Lowest verified cost, verified BaFin register entry, AGB with no algo ban and with retail negative-balance protection. Plan to write a thin reconnecting client (do not depend on the Twisted SDK's reconnect behaviour), use `relativeStopLoss` or immediate amend for market orders, and reconcile with `ProtoOAReconcileReq` after every reconnect.
- **BACKUP: IG Europe GmbH, REST + Lightstreamer.** Obtain IG's written approval first.
- Not recommended: OANDA TMS (no API), Saxo (German onboarding unverified), IBKR (min USD 2 commission per order).

## Biggest UNVERIFIED items
1. Pepperstone GmbH accounts working with the cTrader Open API for trading (any independent report) and Spotware app approval timing.
2. Pepperstone: negative-balance protection conflict (AGB says yes; FAQ says not full); per-symbol min volume/step for the seven pairs on cTrader; hedged vs netted account type.
3. IG: written approval for algorithms (contract clause 9(12)); API stop parameters, reconcile/streaming behaviour; actual min deal size (0.01 vs 1 contract); rate limits.
4. Saxo: whether Germans can be onboarded and under which entity; FX minimum size.
5. Capital.com: contracting entity for Germans, min size, algo terms.
6. BaFin EdW applicability to CFD client cash: statute caps at 90% / EUR 20,000 (amounts in EEA currency only); I read the statute only through a search excerpt.

## Remaining MANUAL steps for the operator (Pepperstone path)
1. Open a free cTrader demo account on pepperstone.com (German site) and create the cTID (no live funds needed; up to 5 demos without a live account).
2. Register an Open API application at the Spotware cTrader Open API portal (follow `https://help.ctrader.com/open-api/api-application`; the portal URL differs between pages, use the link from that page), with a detailed description and a redirect URI you control; wait for the approval email.
3. Run the OAuth2 authorization-code flow once (scope `trading`) for the demo account; store client secret, access and refresh tokens in your secrets store, not in git.
4. On the demo, read `ProtoOASymbolByIdRes` for the seven pairs (`minVolume`, `stepVolume`, `lotSize`), `ProtoOATrader.accountType`, and test: market order with relative stop, partial fill/reject, reconcile after forced disconnect.
5. Email Pepperstone support (support@pepperstone.com, +49 211 81999940) to confirm in writing: Open API trading is enabled for GmbH accounts, no restriction on your trade frequency/hold times, negative-balance protection for retail on cTrader, and swap/min-size per pair.
6. Only after the demo lifecycle passes: open the live Pepperstone GmbH account (identity verification, suitability questions, EUR base currency, Razor); fund at least EUR 100 (AGB minimum; EUR 500 recommended); request the live Open API grant (live app mode) and repeat step 3 on `live.ctraderapi.com`.
7. In parallel for the backup: open an IG demo with the same email as a future live account, generate an API key, and email IG to request written approval for automated trading (clauses 9(6), 9(9), 9(12)).
