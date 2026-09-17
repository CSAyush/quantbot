# Non-equity overnight sleeve (`quantbot/strategies/hf_overnight_alt.py`)

Timeline: daily (`md.px_daily`). Long at 16:00, explicit 0.0 row at 09:30. Long-only, 1 bp/side ETFs.
Data: `MarketData(HFConfig.research(), refresh=False, intraday=False)`, 2010-01 -> 2026-09-16; IS < 2022-01-01, OOS 2022+.
All Sharpes are net of default costs, idle cash at the T-bill rate, Sharpe in excess of it (the round-3 convention).

**Verdict: pre-registered sleeve REJECT; post-hoc precious-metals variant SHADOW at <= 0.25, no live capital.**
`n_trials = 67` (22 per-asset screens + 22 default/sensitivity/ablation/gold trials + 6 metals follow-ups
+ 10 ensemble runs + 7 metals sensitivity; the 8-point cost scan in 3b is not counted as it re-prices one weight matrix).

## 1. Hypothesis and literature

The overnight premium may not be only an equity-beta effect. Gold's return accrues mostly outside London/New
York trading hours (Caminschi & Heaney 2014, "Fixing a leaky fixing", and the gold-overnight literature), and
the ETF overnight literature (Lou, Polk & Skouras 2019; Bogousslavsky 2021) finds a positive close-to-open
drift across liquid ETFs. `overnight.md` 2a measured GLD +3.5 bp/night (t 2.9, intraday ~0), SLV +6.0 (t 2.6),
XLE +4.6 (t 2.7), XLU +2.4 (t 3.0) with unconditional net Sharpes 0.2-0.5 and -50%/-70% drawdowns, and never
conditioned on them. Because GLD/SLV/GDX/XLE/XOP/USO/DBC have low daily correlation with QQQ (0.05-0.48), a
*conditioned* overnight sleeve on them should be nearly uncorrelated with the live overnight sleeve
(QQQ/SMH/IWM) and with the intraday reversal sleeve, which is what the round-3 Sharpe push needs. The
pre-registered plan was to transplant the live sleeve's two validated gates (own close > 200d MA AND own
last-5-nights overnight sum < 0) onto each asset's own series, select assets in-sample, and then test.

## 2. Everything tested

### 2.1 Per-asset screen: unconditional vs the two-gate rule on the asset's own series (22 trials)

| Asset | cost | uncond bp/night (t) | intraday bp | uncond net S / OOS | MaxDD | 2-gate nights (TIM) | gross bp (t) | net bp | gross IS / OOS bp | **net S** | **IS** | **OOS** | CAGR | MaxDD | corr c2c QQQ / SPY |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GLD | 1 | 3.6 (3.0) | 0.0 | 0.23 / 0.68 | -50% | 966 (23%) | 3.1 (1.2) | 1.1 | 1.0 / 6.7 | 0.05 | -0.11 | 0.29 | 1.7% | -23% | 0.08 / 0.07 |
| SLV | 1 | 6.1 (2.6) | -1.2 | 0.38 / 0.67 | -70% | 740 (18%) | 5.8 (1.0) | 3.8 | 5.5 / 6.4 | 0.14 | 0.15 | 0.13 | 2.5% | -23% | 0.22 / 0.23 |
| GDX | 2 | 8.7 (4.0) | -3.9 | 0.47 / 0.28 | -35% | 765 (18%) | 7.5 (1.4) | 3.5 | 10.1 / 4.2 | 0.13 | 0.28 | -0.06 | 2.4% | -32% | 0.21 / 0.22 |
| XLE | 1 | 4.6 (2.8) | 0.0 | 0.31 / 0.36 | -47% | 965 (23%) | 4.0 (1.3) | 2.0 | 6.3 / 0.0 | 0.13 | **0.38** | -0.24 | 2.2% | -15% | **0.48** / 0.65 |
| XOP | 2 | 7.9 (3.6) | -4.1 | 0.38 / 0.05 | -54% | 854 (20%) | 11.8 (2.9) | 7.8 | 18.1 / 0.5 | 0.46 | **0.88** | -0.29 | 5.2% | -17% | **0.45** / 0.59 |
| XLU | 1 | 2.4 (3.1) | 1.8 | -0.02 / 0.67 | -52% | 1299 (31%) | -0.2 (-0.2) | -2.2 | -0.5 / 0.7 | -0.54 | -0.58 | -0.42 | -0.7% | -36% | 0.43 / 0.57 |
| USO | 1 | 1.2 (0.5) | -0.4 | -0.12 / 0.74 | -92% | 845 (20%) | 2.6 (0.5) | 0.6 | -1.5 / 10.6 | 0.01 | -0.22 | 0.30 | 1.1% | -39% | 0.23 / 0.31 |
| DBC | 1 | 1.8 (1.5) | -0.2 | -0.14 / 0.18 | -63% | 870 (21%) | 3.7 (1.4) | 1.7 | 3.5 / 3.9 | 0.11 | 0.14 | 0.07 | 2.0% | -18% | 0.29 / 0.37 |
| UNG | 1 | -3.5 (-1.0) | -3.5 | -0.43 / -0.42 | -97% | 414 (10%) | -11.5 (-1.0) | -13.5 | -15.9 / -1.5 | -0.31 | -0.50 | -0.07 | -3.2% | -59% | 0.05 / 0.07 |
| TLT (control) | 1 | -0.3 (-0.3) | 1.7 | -0.68 / -1.52 | -67% | 980 (23%) | 1.3 (0.7) | -0.7 | 2.3 / -3.4 | -0.14 | 0.04 | -0.80 | 0.8% | -10% | -0.22 / -0.28 |
| IEF (control) | 1 | 0.5 (1.0) | 0.6 | -1.06 / -1.42 | -49% | 1120 (27%) | 1.9 (2.5) | -0.1 | 2.3 / 0.8 | -0.18 | 0.06 | -0.72 | 1.1% | -5% | -0.19 / -0.25 |

Findings. (i) **The two-gate rule does not transfer.** For GLD it selects nights *worse* than average (3.1 bp
vs 3.6 unconditional, t 1.2 vs 3.0); for SLV/GDX/DBC it selects average nights; only XLE/XOP look better
in-sample and both go to ~0 bp OOS. On QQQ the same two gates took the net Sharpe from 0.68 to 1.53. (ii) The
unconditional commodity overnight premium is real but *mirror-imaged in time* relative to equities: IS ~0,
OOS 0.67-0.74 net for GLD/SLV/XLU/USO (the 2023-26 metals bull market accrued overnight), so a 2022 split
flatters it. (iii) Controls behaved as expected (TLT/IEF negative OOS). (iv) **Pre-registered selection (IS
net S > 0.3 AND corr QQQ < 0.5) -> XLE, XOP**: two energy-equity ETFs with corr 0.6 to SPY, i.e. not the
diversifier the hypothesis was after.

### 2.2 Pre-registered default: EW XLE+XOP, own 200d & own on5 < 0 - and its one-at-a-time variants (22 trials)

| Variant | net S | IS | OOS | CAGR | MaxDD | TIM | cost/yr |
|---|---|---|---|---|---|---|---|
| **default EW(XLE,XOP) own200 & on5** | **0.32** | **0.69** | **-0.28** | 3.8% | -14.7% | 13.9% | 1.7% |
| reference: all-7 EW (GLD SLV GDX XLE XOP USO DBC) | 0.24 | 0.37 | 0.06 | 2.7% | -12.0% | 28.4% | 1.4% |
| reference: metals EW (GLD SLV GDX) | 0.14 | 0.17 | 0.11 | 2.3% | -18.7% | 16.5% | 1.4% |
| ma_window 100 / 150 / 250 | 0.26 / 0.22 / 0.29 | 0.57 / 0.51 / 0.62 | -0.33 / -0.26 / -0.21 | 3.2 / 2.9 / 3.5% | -19 / -15 / -15% | 13-14% | 1.5-1.7% |
| on_window 3 / 7 / 10 | 0.39 / 0.43 / 0.55 | 0.77 / 0.64 / 0.70 | -0.17 / 0.11 / 0.36 | 4.3 / 4.6 / 5.2% | -11 / -9 / -8% | 13-15% | 1.5-1.8% |
| on_threshold -0.5% | 0.39 | 0.66 | -0.06 | 4.0% | -12.5% | 9.9% | 1.2% |
| SPY>200d gate instead of own | 0.31 | 0.31 | 0.32 | 4.0% | -27.1% | 19.8% | 2.6% |
| own AND SPY>200d | 0.36 | 0.65 | -0.38 | 3.7% | -14.6% | 12.6% | 1.5% |
| inverse-vol 15%, cap 1 | 0.32 | 0.66 | -0.32 | 2.9% | -7.3% | 13.9% | 1.1% |
| ablation: trend only | 0.31 | 0.56 | -0.07 | 4.6% | -21.9% | 32.4% | 4.5% |
| ablation: on5 only | 0.31 | 0.40 | 0.00 | 4.9% | -42.4% | 23.7% | 3.1% |
| ablation: neither (unconditional EW XLE+XOP) | 0.36 | 0.41 | 0.19 | 6.7% | -46.9% | 50.0% | 7.6% |

The ablation is the key row: with both gates, one gate or none, the Sharpe is 0.31-0.36. The gates only cut
time in market (and cost) - they add no selectivity. In-sample 0.69 vs OOS -0.28 is a regime flip of the XOP
premium (18 bp/night IS -> 0.5 bp OOS), the same "energy gap effect reversed in 2022" that `crossasset.md`
8.2 documents. Every variant has OOS <= 0.36 and the OOS sign is negative in 8 of 12. **REJECT.**

### 2.3 Pre-registered gold question: does GLD's overnight depend on the same day's US-session sign? (6 trials)

Conditional next-night mean, bp (t), n; "own>200d" = close above own 200d MA:

| Asset | filter | US session **up** | US session **down** | IS up / down | OOS up / down |
|---|---|---|---|---|---|
| GLD | uncond | 4.5 (2.8) n=2096 | 2.8 (1.5) | 3.2 / 1.2 | 7.7 / 6.7 |
| GLD | own>200d | **6.4 (3.0)** n=1293 | 1.6 (0.7) | **5.2 (2.1) / -1.2** | **8.4 (2.2) / 6.1** |
| SLV | uncond | **10.5 (3.4)** n=2018 | 3.2 (0.9) | 10.4 (3.2) / -0.4 | 10.9 / 12.3 |
| SLV | own>200d | 14.4 (3.1) n=1036 | 9.4 (1.6) | 18.2 (3.5) / 2.8 | 8.9 / 18.9 |
| GDX | uncond | 12.1 (3.9) | 4.8 (1.5) | 12.6 / 5.0 | 11.0 / 4.2 |
| GDX | own>200d | 13.0 (3.0) | -4.4 (-0.9) | 16.0 / -4.0 | 9.0 / -5.0 |
| XLE | uncond | 9.1 (4.2) | -0.1 (0.0) | 11.0 (4.4) / -2.5 | 4.2 / 6.4 |
| QQQ | own>200d | 6.2 (4.4) | 5.7 (3.1) | 6.1 / 5.1 | 6.5 / 7.1 |

| Trial | net S | IS | OOS | CAGR | MaxDD | TIM |
|---|---|---|---|---|---|---|
| GLD uncond, US session down | 0.04 | -0.14 | 0.40 | 1.4% | -40% | 25% |
| GLD uncond, US session up | 0.30 | 0.18 | 0.54 | 3.7% | -32% | 25% |
| GLD own200 & down | -0.10 | -0.36 | 0.27 | 0.5% | -28% | 15% |
| **GLD own200 & up** | **0.45** | **0.38** | **0.58** | 4.5% | -20% | 16% |
| SLV uncond, down | 0.05 | -0.19 | 0.50 | 0.7% | -68% | 25% |
| **SLV uncond, up** | **0.63** | **0.74** | **0.48** | 10.5% | -32% | 24% |

Answer: it is **continuation, not a fixing reversal**. After an up US session gold/silver/miners keep rising
into the Asian session; after a down session the overnight premium is ~0 (negative for GDX above its MA).
The asymmetry is 3-5 bp/night for GLD, 7-11 for SLV, 7-17 for GDX, present in both halves for GLD and SLV
(IS and OOS both positive on the up side), and **absent in QQQ** (6.2 vs 5.7 bp) - consistent with
`overnight.md` 2b, which found the intraday sign useless for equities. XLE has it in-sample only.

### 2.4 Post-hoc follow-up (6 trials, counted): does a metals basket on this signal form a sleeve?

| Trial | net S | IS | OOS | CAGR | MaxDD | TIM | cost/yr | skew | kurt |
|---|---|---|---|---|---|---|---|---|---|
| **GLD+SLV EW, own200 & US session up** (chosen) | **0.65** | **0.83** | **0.44** | 6.8% | -16.9% | 19.5% | 1.5% | 0.0 | 18.7 |
| GLD+SLV+GDX EW, own200 & up | 0.64 | 0.86 | 0.39 | 6.8% | -17.5% | 21.3% | 1.8% | 0.0 | 18.4 |
| GLD+SLV EW, own200 & up & on5<0 | 0.42 | 0.50 | 0.34 | 3.4% | -9.1% | 8.3% | 0.6% | 1.5 | 55.9 |
| GLD+SLV EW, uncond & up (no trend) | 0.58 | 0.60 | 0.56 | 7.3% | -30.9% | 29.5% | 2.5% | 0.3 | 10.3 |
| SLV own200 & up | 0.62 | 0.92 | 0.29 | 8.8% | -22.7% | 12.9% | 1.3% | -0.1 | 24.3 |
| GDX own200 & up | 0.48 | 0.67 | 0.23 | 6.4% | -22.5% | 12.7% | 2.6% | 0.1 | 19.3 |

GLD+SLV was preferred over +GDX on priors (GDX is 2 bp/side, an equity, and adds nothing) and over SLV alone
(concentration); the three are within noise of each other. The 200d gate matters for drawdown (-17% vs -31%),
not Sharpe. Adding the equity sleeve's on5 gate hurts (0.42) - again it does not transfer.

### 2.5 Ensemble runs (10 trials) - see section 5.

## 3. Final scorecard - `OvernightAltParams()` defaults (GLD+SLV, own 200d MA, US session up)

```
overnight_alt      | CAGR   6.78% | Vol  8.32% | Sharpe  0.65 | Sortino  0.84 | MaxDD -16.87% | Calmar  0.40 | t  3.31 | PF 1.28 | exp L/S 0.15/0.00 | cost/yr 1.47% | days 4002
  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean 1.5% over the period)
  time in market 19.5% | turnover/day 0.58 | trades/day 1.16 | skew -0.01 | kurt 18.7 | best +4.43% | worst -5.42%
  Sharpe 95% bootstrap CI: [0.17, 1.14]
  Deflated Sharpe: P(SR > null max of 67 trials = 0.60) = 0.574
  vs benchmark: corr 0.02 | beta 0.01

  Yearly:
       return      vol   sharpe   max_dd  days        SPY
2010    0.040    0.132    1.453   -0.038    53      0.131
2011    0.502    0.097    4.255   -0.033   252      0.019
2012   -0.004    0.038   -0.106   -0.027   250      0.160
2013   -0.010    0.023   -0.454   -0.026   252      0.323
2014   -0.090    0.046   -2.035   -0.099   252      0.135
2015   -0.041    0.024   -1.746   -0.052   252      0.012
2016    0.175    0.094    1.736   -0.068   252      0.120
2017   -0.001    0.029   -0.351   -0.034   251      0.217
2018   -0.031    0.027   -1.841   -0.043   251     -0.046
2019    0.058    0.067    0.574   -0.035   252      0.312
2020    0.255    0.111    2.074   -0.053   253      0.183
2021   -0.054    0.061   -0.897   -0.084   252      0.287
2022   -0.036    0.062   -0.881   -0.067   251     -0.182
2023    0.021    0.069   -0.400   -0.055   250      0.262
2024    0.086    0.098    0.383   -0.062   252      0.249
2025    0.199    0.129    1.176   -0.112   250      0.177
2026    0.152    0.193    0.948   -0.099   177      0.112

  In-sample / out-of-sample split at 2022-01-01:
                             days     cagr      vol   sharpe  sortino  max_drawdown   calmar
overnight_alt in-sample      2822    0.060    0.066    0.834    1.157        -0.169    0.356
overnight_alt out-of-sample  1180    0.087    0.114    0.439    0.552        -0.112    0.775
overnight_alt full           4002    0.068    0.083    0.646    0.843        -0.169    0.402
```

Gross (zero cost): Sharpe 0.82 / IS 1.02 / OOS 0.61, CAGR 8.4%. Per asset on held nights: GLD 1293 nights,
+6.4 bp gross (t 3.0; IS 5.2, OOS 8.4); SLV 1036 nights, +14.4 bp (t 3.1; IS 18.2, OOS 8.9).

### 3a. Where the return comes from (the honest part)

| window | Sharpe |
|---|---|
| full 2010-2026 | 0.65 |
| ex-2011 | 0.36 |
| in-sample ex-2011 | 0.33 |
| 2012-2019 | -0.02 |
| 2012-2024 | 0.15 |
| ex-2011 and ex-2025-26 | 0.19 |

2011 (silver at $50) alone is 48% of the total excess return; 2011 + 2016 + 2020 + 2025-26 are ~127% of it
and the other 12 years net to ~-27%. Eight of 17 calendar years have negative Sharpe. Rolling 3-year Sharpe: median
0.31, negative 37% of the time, min -1.69 (window ending 2016-02). The sleeve is "long precious metals
overnight after an up session while they trend", and it earns only while metals are in a bull market. That
is a coherent economic story (the 24h metals market carries the New York move into Asia, and the 200d gate
puts you in the trend) but it is *not* a steady premium like the QQQ/SMH overnight edge.

### 3b. Cost scan (per-side bp on both assets) and breakeven

| cost/side | 0 | 1 (assumed) | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| Sharpe full / IS / OOS | 0.82 / 1.02 / 0.61 | 0.65 / 0.83 / 0.44 | 0.47 / 0.64 / 0.27 | 0.29 / 0.45 / 0.10 | 0.12 / 0.26 / -0.07 | -0.06 / 0.07 / -0.24 | -0.24 |
| excess return/yr | 6.8% | 5.4% | 3.9% | 2.4% | 1.0% | -0.5% | -2.0% |

Breakeven cost **4.7 bp/side** (4.7x the assumed 1 bp; GLD alone 3.2 bp, SLV 7.2 bp). A 1 c spread is
0.3 bp on GLD ($392) but 1.8 bp on SLV ($57), so 1 bp/side is conservative for GLD and about right for SLV;
MOO/MOC auction fills pay no spread.

### 3c. Tails and episodes

Skew -0.01, kurtosis 18.7. Worst 5 days: 2025-12-29 -5.4% (GLD+SLV), 2026-04-02 -5.2% (GLD+SLV),
2026-03-03 -4.5% (SLV), 2024-04-22 -3.5% (GLD+SLV), 2020-08-11 -3.3% (SLV) - all in metals bull phases when
the sleeve is fully on and metals vol is 25-40%. Best 5 days all in 2026 Q1 (+3.4% to +4.4%).
2020-02-20 -> 04-30: +5.0%, MaxDD -1.2%, 46% of nights held (GLD's 200d gate was on 94% of those days,
SLV's only 20%; the March-2020 gold liquidation did not hurt the up-session nights). 2020-03 alone +1.0%.
2022: -3.6% (MaxDD -6.7%, 31% of nights); the Mar-Nov 2022 gold drawdown (-20%) cost only -2.4% because the
200d gate switched SLV off on 2022-04-25 and GLD off on 2022-05-10. 2013 gold crash: 0 nights held.
2025-01 -> 2026-09: +38%, vol 16%, MaxDD -11%, 56% of nights held; trailing-1y vol is now 29% for GLD and
62% for SLV, so current per-night risk is roughly twice the full-sample average.

## 4. Sensitivity (one-at-a-time around the defaults; net Sharpe full / IS / OOS; 7 trials)

| Variant | net S | IS | OOS | CAGR | MaxDD | TIM |
|---|---|---|---|---|---|---|
| **base: GLD+SLV own200 & US session up** | **0.65** | **0.83** | **0.44** | 6.8% | -16.9% | 19.5% |
| ma_window 100 | 0.55 | 0.75 | 0.28 | 5.7% | -17.8% | 19.4% |
| ma_window 150 | 0.66 | 0.91 | 0.35 | 6.8% | -14.7% | 19.5% |
| ma_window 250 | 0.67 | 0.89 | 0.46 | 6.9% | -12.4% | 19.2% |
| + SPY>200d gate | 0.64 | 0.78 | 0.48 | 6.2% | -16.8% | 16.8% |
| inverse-vol 15%, cap 1 | 0.57 | 0.70 | 0.38 | 4.4% | -13.3% | 19.5% |
| "up" = close-to-close > 0 instead of US session | 0.38 | 0.44 | 0.34 | 4.7% | -19.8% | 20.7% |
| "up" = last night's gap > 0 instead of US session | 0.18 | 0.21 | 0.15 | 2.8% | -27.4% | 20.7% |
| no trend gate (2.4) | 0.58 | 0.60 | 0.56 | 7.3% | -30.9% | 29.5% |
| + on5 < 0 gate (2.4) | 0.42 | 0.50 | 0.34 | 3.4% | -9.1% | 8.3% |

No cliffs: the MA window is a plateau (0.55-0.67), the equity gate is irrelevant (-0.01), inverse-vol only
trades Sharpe for drawdown. The two signal-definition rows are the useful ones: the effect is specific to the
*US-session* return (0.65) and is not generic 1-day momentum (0.38 on close-to-close, 0.18 on the previous
gap). Gate 4 (smooth degradation) passes.

## 5. Correlations and ensemble effect

Daily **excess** returns vs `/tmp/qb_shared/reference_daily_returns.csv` (common dates 2010-10 -> 2026-09):

| | ensemble_growth | overnight | reversal | spy |
|---|---|---|---|---|
| full | **0.01** | **0.04** | **0.00** | **0.02** |
| OOS 2022+ | 0.03 | 0.07 | 0.00 | 0.03 |
| days after a held night (39%) | 0.02 | 0.07 | 0.00 | 0.03 |

(Pre-registered XLE+XOP for comparison: 0.18 / 0.23 / -0.03 / 0.13 full; 0.31 / 0.38 / -0.06 / 0.28 on held
nights - energy equities are equity beta.) The metals sleeve is as uncorrelated as anything can be.

Growth ensemble reproduced in `/tmp/qb_overnight_alt/step4_ensemble.py` (overnight with QQQ->QLD, reversal
0.5, regime multiplier on the live overnight sleeve only, dd throttle 10%/0.5, exposure cap 1.5,
`leverage_map`, gross-long cap 1.0). Reproduction matches `growth_weights_reference.parquet` exactly
(max |dw| = 0, max |daily return diff| 1e-16). The alt sleeve is summed in via `combine_weights` **unscaled**
by the regime multiplier (decision: the multiplier is SPY-trend x QQQ-realised-variance, an equity construct;
metals' overnight return did not depend on the SPY trend in 4.2).

| Allocation | Sharpe full / IS / OOS | delta full | delta IS | delta OOS | CAGR | MaxDD |
|---|---|---|---|---|---|---|
| growth, alt 0 | 1.32 / 1.22 / 1.56 | - | - | - | 11.64% | -12.19% |
| **+ alt 0.25** | 1.45 / 1.40 / 1.59 | **+0.13** | **+0.18** | **+0.03** | 13.01% | -10.08% |
| + alt 0.5 | 1.47 / 1.48 / 1.50 | +0.15 | +0.26 | -0.07 | 14.18% | -9.62% |
| + alt 1.0 | 1.30 / 1.43 / 1.15 | -0.02 | +0.21 | -0.42 | 15.17% | -12.81% |
| + alt 0.5, regime-scaled (1 trial) | 1.48 / 1.43 / 1.59 | +0.15 | +0.22 | +0.03 | 13.56% | -9.62% |
| pre-registered XLE+XOP @ 0.25 / 0.5 / 1.0 | 1.30 / 1.22 / 1.02 | -0.03 / -0.10 / -0.30 | +0.03 / +0.03 / -0.03 | -0.16 / -0.39 / -0.83 | | |

Gate 3 passes only at 0.25 (both deltas positive; the OOS delta of +0.03 is noise-level). At 0.5 the OOS
delta is negative; at 1.0 the sleeve's 2021-23 losses and its 11-16% vol overwhelm the diversification.

**Cash-account gross-cap competition.** The alt sleeve holds 16:00 -> 09:30 at the same time as the live
overnight sleeve. At 16:00 rows: alt on 37.1% of nights, live overnight on 42.0%, **both on 15.7% (660
nights)**. Pre-cap gross long > 1.0 on 3.3% / 5.6% / 12.0% of nights at allocation 0.25 / 0.5 / 1.0 (mean
pre-cap gross 1.17 / 1.27 / 1.45, mean pro-rata scale 0.86 / 0.80 / 0.71 on those nights). The alt sleeve
realises 98% / 96% / 89% of its intended exposure; the live sleeve loses the same fraction on those nights.
At 0.25 the interaction is negligible.

## 6. Failure modes / when to turn it off

- **It is a metals-bull-market strategy.** Section 3a: 2012-2019 Sharpe -0.02; 2021-2023 -0.9/-0.9/-0.4. When
  gold/silver chop around their 200d MA (2012-15, 2021-23) the sleeve is flat to -9%/yr. Monitor the trailing
  250-night gross mean on held nights; the sleeve has no edge when it is below ~2 bp.
- **Gap risk with 25-60% vol assets.** Kurtosis 19; the five worst days (-3.3% to -5.4%) are all recent. At
  0.25 allocation that is -1.4% of ensemble equity on a bad night. Silver is ~2x gold's vol and roughly
  two-thirds of the sleeve's gross P&L (14.4 bp x 1036 nights vs 6.4 bp x 1293) and most of its tail;
  `weighting="inverse_vol"` cuts the drawdown to -13% at -0.08 Sharpe.
- **Post-hoc selection.** The rule was chosen after the pre-registered rule failed; deflated-Sharpe P = 0.57
  at 67 trials; bootstrap CI [0.17, 1.14]. Treat the backtest Sharpe as an upper bound.
- **Signal timing live.** The US-session sign uses the 16:00 close vs the 09:30 open; live, compute it from
  the ~15:59 price and send MOC orders. Signals that flip in the last minute are not modelled (not tested).
- **Data:** GLD/SLV Yahoo opens are Arca auction prints; fills at MOO should be close. The metals also trade
  nearly 24h in futures, so the "overnight" return here is the ETF's 16:00 -> 09:30 print, not a session in
  the underlying.

## 7. Recommended params and allocation

`OvernightAltParams()` defaults: assets (GLD, SLV), require_own_trend=True, ma_window=200,
require_on_reversal=False, intraday_sign="up", weighting="equal", max_gross=1.0. Do not regime-scale it.

**Allocation: SHADOW paper account at 0.25; 0 live.** The round-3 gate is numerically met at 0.25 (Sharpe
0.65 >= 0.5 with OOS 0.44 >= 0.4 same sign; breakeven 4.7 bp >= 2 bp; ensemble delta +0.18 IS / +0.03 OOS;
smooth sensitivity) but the edge is episodic (3a), the selection was post hoc and the OOS ensemble gain is
zero within noise. What would change my mind: 12 months of shadow P&L with positive gross bp on held nights
*outside* a metals rally, or a 2012-2024-style window in the shadow record that is not negative. What would
kill it: held-night gross mean < 2 bp over 250 nights, or GLD/SLV spreads > 3 bp at the close.

## 8. Insights for other sleeves

1. **The live sleeve's two gates are equity-specific.** Own-200d & own-on5 took QQQ from 0.68 to 1.53 net;
   on GLD/SLV/GDX/USO/DBC they select nights no better than average (ablation: 0.31-0.36 for both/one/no
   gate on XLE+XOP). Overnight-return mean reversion at 5 nights does not exist in commodities. Do not port
   `hf_overnight`'s rules to non-equity ETFs without re-testing them.
2. **Commodities show US-session -> overnight *continuation*; equities do not.** GLD +6.4 bp after an up
   session vs +1.6 after a down one (above 200d MA), SLV 14.4 vs 9.4, GDX 13.0 vs -4.4, XLE 9.1 vs -0.1
   (IS only); QQQ 6.2 vs 5.7. It is specific to the 09:30-16:00 return (close-to-close and prior-gap
   definitions fail). Any commodity/metals sleeve should carry the NY session sign into the night; a
   short-overnight leg after down sessions in GDX (-4.4 bp, -5.0 OOS) may be worth a look for a long/short
   design (not tested - long-only mandate).
3. **The unconditional commodity overnight premium is time-mirrored vs equities.** GLD/SLV/XLU/USO
   unconditional overnight: IS ~0, OOS 0.67-0.74 net (2023-26 metals rally) - the opposite of QQQ (OOS 0.39).
   A 2022 split makes any long-metals overnight rule look good OOS; check 2012-2019 explicitly.
4. **Selection screens on 12 years flip.** Both assets that passed the IS screen (XLE 0.38, XOP 0.88) went to
   -0.24/-0.29 OOS, exactly the `crossasset.md` 8.3 pattern (EEM/VNQ). XOP's 18 bp/night in-sample was a
   2010-21 energy regime, not a rule.
5. **Silver at $50 (2011) is 48% of a 16-year metals backtest.** Anything long SLV/GDX in 2010-11 needs an
   ex-2011 number next to it.
6. **Gross-cap competition is small at <= 0.25.** Two overnight sleeves both on 16% of nights; pre-cap gross
   > 1 on 3% of nights at 0.25, 12% at 1.0. Report it for any new 16:00 -> 09:30 sleeve.
7. **Trial accounting:** 67 trials for a 0.65 net Sharpe with deflated P 0.57. If the orchestrator pools
   trials, add 67.
