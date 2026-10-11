# Supplementary forward-holdout (RESERVED_FORWARD) pass

One pass of the frozen strategies over the reserved period (2026-09-20T19:12Z to 2026-10-10), RESEARCH mode. It is reported **for information only**: it does not change any classification (those were fixed on DEV+VAL+OOS), it is a short window (about 3 weeks), and trades overlap in time, so per-trade statistics here are not independent.

| Arm | Scenario | Trades | Mean net R | Win % | Profit factor | Gross EUR (mid-to-mid) | Net EUR |
|---|---|---:|---:|---:|---:|---:|---:|
| F01 | optimistic | 107 | -0.250 | 30.8 | 0.54 | -22.86 | -57.65 |
| F01 | base | 102 | -0.269 | 32.4 | 0.48 | -23.03 | -56.07 |
| F01 | adverse | 66 | -0.188 | 34.8 | 0.61 | -1.12 | -24.38 |
| F02 | optimistic | 311 | -0.207 | 47.6 | 0.56 | -26.23 | -140.40 |
| F02 | base | 222 | -0.333 | 38.7 | 0.38 | -78.45 | -161.19 |
| F02 | adverse | 182 | -0.272 | 42.3 | 0.44 | -26.89 | -96.63 |
| F03 | optimistic | 91 | +0.012 | 42.9 | 1.02 | +42.58 | +7.36 |
| F03 | base | 90 | -0.084 | 37.8 | 0.84 | +18.29 | -17.99 |
| F03 | adverse | 32 | +0.013 | 53.1 | 1.03 | +12.45 | -0.25 |
| F04 | optimistic | 18 | -0.430 | 22.2 | 0.30 | -4.83 | -7.08 |
| F04 | base | 12 | -0.580 | 16.7 | 0.15 | -4.71 | -6.16 |
| F04 | adverse | 10 | -0.592 | 10.0 | 0.03 | -3.74 | -5.41 |
| F05 | optimistic | 88 | -0.074 | 40.9 | 0.80 | +5.50 | -14.77 |
| F05 | base | 88 | -0.102 | 38.6 | 0.73 | +4.27 | -17.74 |
| F05 | adverse | 78 | -0.172 | 34.6 | 0.55 | +0.63 | -24.24 |
| F06 | optimistic | 83 | -0.579 | 13.3 | 0.31 | -72.85 | -103.30 |
| F06 | base | 78 | -0.586 | 12.8 | 0.29 | -67.32 | -95.27 |
| F06 | adverse | 43 | -0.761 | 9.3 | 0.08 | -46.94 | -63.94 |
| F07 | optimistic | 435 | -0.127 | 39.8 | 0.67 | +35.75 | -123.70 |
| F07 | base | 372 | -0.162 | 37.1 | 0.59 | +7.95 | -133.79 |
| F07 | adverse | 266 | -0.213 | 32.0 | 0.44 | +1.40 | -108.06 |
| F07R | optimistic | 278 | -0.221 | 40.3 | 0.49 | -34.88 | -138.19 |
| F07R | base | 297 | -0.211 | 40.7 | 0.47 | -19.05 | -131.66 |
| F07R | adverse | 227 | -0.233 | 34.8 | 0.39 | -12.27 | -103.98 |
