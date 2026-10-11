# F01-F07 evaluation: common-methodology evidence table

Window: 2026-04-01T00:00:00Z -> 2026-09-20T19:12:00Z (DEVELOPMENT + VALIDATION + OUT_OF_SAMPLE; RESERVED_FORWARD untouched).
All figures are RESEARCH-mode, BASE cost scenario (fixed EUR 500 sizing, drawdown pause off) unless stated. R = net P&L / risk at the stop.

## Summary (all evaluated partitions)

| Arm | Class | Trades | Indep. episodes (trades/episode) | Gross (mid-to-mid, before any cost) % of 500 | Net (after spread, slippage, commission) % of 500 | Mean net R [95% CI] | Win % | Avg win EUR | Avg loss EUR | Profit factor (R) | Max DD % | Exposure % |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| F01 | **NEGATIVE_EVIDENCE** | 708 | 393 (1.80) | -13.30 | -58.44 | -0.208 [-0.296, -0.115] | 33.6 | 1.88 | -1.57 | 0.59 | 60.8 | 8.2 |
| F02 | **NEGATIVE_EVIDENCE** | 983 | 391 (2.51) | 5.54 | -70.67 | -0.171 [-0.230, -0.110] | 46.2 | 1.16 | -1.66 | 0.60 | 71.2 | 4.8 |
| F03 | **MIXED_EVIDENCE** | 554 | 324 (1.71) | -9.14 | -51.97 | -0.220 [-0.327, -0.108] | 31.2 | 2.07 | -1.62 | 0.58 | 59.8 | 10.7 |
| F04 | **INSUFFICIENT_DATA** | 16 | 16 (1.00) | 0.85 | 0.33 | 0.066 [-0.417, 0.613] | 43.8 | 1.12 | -0.69 | 1.16 | 0.6 | 0.2 |
| F05 | **NEGATIVE_EVIDENCE** | 688 | 308 (2.23) | 0.89 | -39.32 | -0.144 [-0.229, -0.055] | 40.8 | 1.33 | -1.40 | 0.64 | 40.3 | 6.4 |
| F06 | **NEGATIVE_EVIDENCE** | 428 | 258 (1.66) | -15.56 | -47.57 | -0.246 [-0.389, -0.093] | 29.2 | 2.73 | -1.91 | 0.61 | 51.3 | 3.9 |
| F07 | **NEGATIVE_EVIDENCE** | 1085 | 428 (2.54) | 4.91 | -78.27 | -0.173 [-0.230, -0.116] | 37.5 | 1.17 | -1.28 | 0.55 | 78.9 | 3.9 |
| F07R | **MIXED_EVIDENCE** | 748 | 327 (2.29) | -6.06 | -63.09 | -0.200 [-0.258, -0.144] | 38.1 | 1.05 | -1.33 | 0.49 | 64.4 | 2.9 |

## By partition (mean net R, trades / episodes)

| Arm | DEVELOPMENT | VALIDATION | OUT_OF_SAMPLE | VAL+OOS pooled [95% CI] |
|---|---|---|---|---|
| F01 | -0.209 (472/240) | -0.228 (125/83) | -0.182 (111/70) | -0.206 [-0.344, -0.054] |
| F02 | -0.169 (924/356) | -0.206 (36/21) | -0.201 (23/14) | -0.204 [-0.454, 0.079] |
| F03 | -0.250 (390/213) | -0.406 (94/67) | 0.193 (70/44) | -0.150 [-0.356, 0.079] |
| F04 | 0.068 (10/10) | 0.088 (2/2) | 0.049 (4/4) | 0.062 [-0.516, 0.682] |
| F05 | -0.093 (429/187) | -0.262 (152/71) | -0.181 (107/50) | -0.229 [-0.343, -0.114] |
| F06 | -0.265 (289/161) | -0.290 (76/52) | -0.107 (63/45) | -0.207 [-0.487, 0.136] |
| F07 | -0.170 (1018/380) | -0.172 (49/34) | -0.298 (18/14) | -0.206 [-0.428, 0.081] |
| F07R | -0.204 (702/300) | -0.356 (23/14) | 0.067 (23/13) | -0.145 [-0.408, 0.131] |

## Cost sensitivity (all evaluated, RESEARCH mode)

| Arm | Optimistic: trades, mean R, net EUR | Base | Adverse |
|---|---|---|---|
| F01 | 733, -0.167, -255.27 | 708, -0.208, -292.18 | 464, -0.228, -190.64 |
| F02 | 939, -0.155, -311.97 | 983, -0.171, -353.33 | 885, -0.197, -339.66 |
| F03 | 584, -0.168, -216.69 | 554, -0.220, -259.87 | 219, -0.172, -72.06 |
| F04 | 16, 0.102, 1.53 | 16, 0.066, 1.66 | 6, 0.078, 0.51 |
| F05 | 701, -0.141, -202.82 | 688, -0.144, -196.61 | 528, -0.213, -214.43 |
| F06 | 439, -0.235, -226.55 | 428, -0.246, -237.84 | 203, -0.190, -73.10 |
| F07 | 900, -0.196, -380.12 | 1085, -0.173, -391.35 | 918, -0.222, -389.29 |
| F07R | 900, -0.146, -286.14 | 748, -0.200, -315.45 | 802, -0.238, -370.06 |

## GOVERNED run (the real EUR 500 capital rules: compounding sizing, 10% drawdown pause)

| Arm | Trades | Final ledger equity EUR | Net EUR | Max DD % | Drawdown pause triggered | Ledger minus engine EUR |
|---|---:|---:|---:|---:|---|---:|
| F01 | 89 | 446.14 | -53.86 | 10.9 | True | 3.76 |
| F02 | 81 | 452.09 | -47.91 | 10.3 | True | 11.23 |
| F03 | 95 | 453.92 | -46.08 | 10.8 | True | 12.91 |
| F04 | 16 | 501.66 | 1.66 | 0.6 | False | 0.64 |
| F05 | 311 | 450.53 | -49.47 | 10.1 | True | 9.60 |
| F06 | 79 | 446.95 | -53.05 | 10.6 | True | 8.05 |
| F07 | 182 | 456.85 | -43.15 | 10.6 | True | 18.85 |
| F07R | 60 | 449.65 | -50.35 | 10.1 | True | 19.29 |

## Why trades were NOT taken (RESEARCH/base rejection counts)

- **F01**: {"BELOW_MIN_UNITS": 10, "COST_GATE": 346, "DAILY_LOSS_HALT": 187, "ENGINE_DENIED": 22, "MAX_POSITIONS": 279, "SESSION_NO_ENTRY": 10}
- **F02**: {"COST_GATE": 13493, "DAILY_LOSS_HALT": 5808, "ENGINE_DENIED": 2127, "MAX_POSITIONS": 285, "SESSION_NO_ENTRY": 896}
- **F03**: {"BELOW_MIN_UNITS": 1, "COST_GATE": 1117, "DAILY_LOSS_HALT": 428, "ENGINE_DENIED": 32, "MAX_POSITIONS": 233, "SESSION_NO_ENTRY": 357}
- **F04**: {"BELOW_MIN_UNITS": 4, "COST_GATE": 4, "POSITION_OPEN": 6, "SESSION_NO_ENTRY": 2}
- **F05**: {"BELOW_MIN_UNITS": 1, "COST_GATE": 104, "DAILY_LOSS_HALT": 19, "MAX_POSITIONS": 308}
- **F06**: {"COST_GATE": 1658, "DAILY_LOSS_HALT": 195, "ENGINE_DENIED": 9, "MAX_POSITIONS": 142, "SESSION_NO_ENTRY": 69}
- **F07**: {"BELOW_MIN_UNITS": 3, "COST_GATE": 22233, "DAILY_LOSS_HALT": 12231, "ENGINE_DENIED": 3139, "MAX_POSITIONS": 451, "SESSION_NO_ENTRY": 2266}
- **F07R**: {"BELOW_MIN_UNITS": 3, "COST_GATE": 24857, "DAILY_LOSS_HALT": 9009, "ENGINE_DENIED": 4233, "MAX_POSITIONS": 157, "SESSION_NO_ENTRY": 2830}

## Classification reasons

- **F01** -> NEGATIVE_EVIDENCE: pooled VAL+OOS mean net R < 0 with CI upper < 0 or negative in every partition
- **F02** -> NEGATIVE_EVIDENCE: pooled VAL+OOS mean net R < 0 with CI upper < 0 or negative in every partition
- **F03** -> MIXED_EVIDENCE: sufficient data; neither NEGATIVE_EVIDENCE nor PROMISING_RESEARCH criteria satisfied
- **F04** -> INSUFFICIENT_DATA: unique episodes: all=16 (<30?) val+oos=6 (<15?)
- **F05** -> NEGATIVE_EVIDENCE: pooled VAL+OOS mean net R < 0 with CI upper < 0 or negative in every partition
- **F06** -> NEGATIVE_EVIDENCE: pooled VAL+OOS mean net R < 0 with CI upper < 0 or negative in every partition
- **F07** -> NEGATIVE_EVIDENCE: pooled VAL+OOS mean net R < 0 with CI upper < 0 or negative in every partition
- **F07R** -> MIXED_EVIDENCE: sufficient data; neither NEGATIVE_EVIDENCE nor PROMISING_RESEARCH criteria satisfied
