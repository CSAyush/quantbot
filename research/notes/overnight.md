# Overnight premium sleeve (`quantbot/strategies/hf_overnight.py`)

Timeline: daily (`md.px_daily`). Long at 16:00, explicit 0.0 row at 09:30. Long-only.
Final rule: hold 1/3 each of QQQ, SMH, IWM overnight **iff** (close > 200d MA) **and**
(sum of the last 5 overnight returns < 0). Tuned on data < 2022-01-01. `n_trials = 286`.

## 1. Hypothesis and literature

Equity index returns since the 1990s accrued disproportionately in the overnight
session (Cooper, Cliff & Gulen 2008; Kelly & Clark 2011). Lou, Polk & Skouras (2019
JFE) show the overnight/intraday split is systematic: momentum and other
"institutional" anomalies earn their premium overnight and reverse intraday, and
overnight returns are persistent cross-sectionally. Bogousslavsky (2021) attributes
part of the overnight premium to inventory/hedging demand at the close and to
retail/institutional clientele differences. Since 2010 the *unconditional* SPY
overnight premium (3.6 bp/night gross) barely clears a 1 bp/side round trip, so the
hypothesis tested here is that (a) the premium is concentrated in higher-beta /
growth ETFs (QQQ, SMH, IWM) where it is large relative to a fixed-bp cost, and (b)
it is state-dependent: present in uptrends and after a run of weak nights (short-term
reversal of the overnight return itself), absent in downtrends.

## 2. Everything tested (net of default costs unless stated; Sharpe uses the engine's 4% cash yield - see 3b)

**Cost arithmetic:** a daily round trip at 1 bp/side = 2 bp/day = ~5.0%/yr for
ETFs, ~10%/yr for 2x/3x ETFs, ~12.6%/yr for stocks. Every filter that keeps you
out of nights with ~zero expected return saves cost one-for-one.

### 2a. Unconditional overnight, all 24 ETFs (24 trials), 2010-01 -> 2026-09

| Ticker | overnight mean bp/night (t) | intraday mean bp (t) | gross Sharpe | net Sharpe | net CAGR | MaxDD | OOS 2022+ net Sharpe |
|---|---|---|---|---|---|---|---|
| SPY | 3.57 (3.4) | 2.26 (1.8) | 0.90 | 0.43 | 4.2% | -30% | 0.23 |
| QQQ | 5.11 (4.2) | 2.58 (1.6) | 1.08 | 0.68 | 8.1% | -30% | 0.39 |
| IWM | 5.22 (4.0) | -0.09 (-0.1) | 1.04 | 0.67 | 8.3% | -29% | 0.40 |
| DIA | 3.27 (3.2) | 1.94 (1.7) | 0.85 | 0.37 | 3.4% | -29% | -0.06 |
| **SMH** | **7.84 (4.4)** | 2.95 (1.3) | 1.12 | **0.85** | 14.8% | -38% | **1.04** |
| XLK | 4.90 (3.6) | 3.18 (1.9) | 0.94 | 0.58 | 7.3% | -36% | 0.36 |
| XLF | 3.84 (2.8) | 1.55 | 0.73 | 0.38 | 4.5% | -49% | -0.09 |
| XLE | 4.55 (2.7) | 0.08 | 0.72 | 0.42 | 5.9% | -46% | 0.58 |
| XLV | 2.50 (2.8) | 2.74 (2.1) | 0.77 | 0.22 | 1.6% | -37% | -0.89 |
| XLY | 4.02 (3.2) | 2.15 | 0.85 | 0.45 | 5.1% | -32% | -0.04 |
| XLP | 1.13 (1.5) | 3.10 (2.8) | 0.46 | -0.19 | -1.7% | -37% | -0.45 |
| XLI | 3.95 (3.3) | 1.84 | 0.88 | 0.47 | 5.0% | -45% | 0.56 |
| XLU | 2.40 (3.0) | 1.92 | 0.84 | 0.22 | 1.4% | -49% | 1.16 |
| TLT | -0.35 (-0.3) | 1.73 (1.7) | -0.01 | -0.50 | -5.6% | -64% | -1.20 |
| IEF | 0.46 (1.0) | 0.63 | 0.40 | -0.66 | -3.2% | -45% | -0.75 |
| GLD | 3.54 (2.9) | 0.06 | 0.78 | 0.37 | 3.9% | -49% | 0.93 |
| SLV | 6.01 (2.6) | -1.15 | 0.67 | 0.46 | 8.3% | -69% | 0.79 |
| HYG | 1.75 (3.2) | 0.42 | 0.91 | 0.02 | 0.0% | -34% | -0.50 |
| EEM | 1.80 (1.1) | 1.02 | 0.31 | 0.02 | -1.2% | -47% | -0.08 |
| EFA | 0.19 (0.1) | 3.18 (3.0) | 0.08 | -0.26 | -4.8% | -66% | -0.18 |
| SSO (2x SPY) | 6.47 (3.0) | 4.01 | 0.78 | 0.32 | 4.6% | -54% | -0.04 |
| QLD (2x QQQ) | 8.98 (3.7) | 5.26 | 0.93 | 0.53 | 10.6% | -58% | 0.14 |
| UPRO (3x SPY) | 9.58 (3.0) | 5.80 | 0.76 | 0.45 | 9.7% | -70% | 0.10 |
| TQQQ (3x QQQ) | 14.33 (3.9) | 7.28 | 0.98 | 0.71 | 21.6% | -71% | 0.25 |

Findings: the premium is an *equity beta* phenomenon - it is largest in SMH, QQQ,
IWM (5-8 bp/night, t ~4), weak in defensives (XLP, XLV, XLU), absent in bonds
(TLT/IEF: negative net) and in EFA/EEM (whose overnight session is their home
market's trading day). GLD/SLV carry a positive overnight premium but with -50%
to -70% drawdowns. **Leverage does not preserve Sharpe:** QLD gross Sharpe 0.93 vs
QQQ 1.08 (vol drag + 2x cost); net 0.53 vs 0.68. Leveraged ETFs only make sense once
a filter has cut the number of nights held (see 4).

### 2b. Conditioning signals (64 tables: 16 signals x SPY/QQQ/SMH/IWM), in-sample < 2022 vs OOS

Reported as next-night mean (bp), t-stat, and the same for 2022+ OOS. Full tables in
the research log; summary of what mattered:

| Signal (at 16:00, day d) | SPY IS mean bp (t) | QQQ IS | SMH IS | Consistent OOS? | Verdict |
|---|---|---|---|---|---|
| **close > 200d MA** | 4.1 (4.3) vs below 3.1 (0.6) | 5.6 (4.5) vs 5.9 (1.0) | 7.6 (4.3) vs 2.9 (0.6) | **Yes** - OOS below-MA is negative for all: SPY -0.3, QQQ -5.0, SMH -5.5, IWM +1.4 bp | **Use.** Clearest regime effect; below the 200d MA there is no overnight premium |
| **sum of last 5 overnight rets < 0** | 7.7 (3.0) vs > 0: 1.5 (1.2) | 11.3 (3.9) vs 2.2 (1.6) | 12.0 (3.6) vs 2.9 (1.4) | **Yes** for QQQ (11.0 vs -1.4, t 2.5) and SMH (17.6 vs 6.8, t 2.6); SPY 4.6 vs 1.2; IWM flat | **Use.** Overnight returns *mean-revert* at the 5-day horizon in ETFs |
| last night's overnight ret < 0 | 8.1 (3.9) vs 0.7 | 9.8 (4.2) vs 2.5 | 10.2 (3.5) vs 3.7 | Mixed - SPY flips OOS (0.7 vs 4.2) | Weaker, noisier version of the above; not used |
| today's intraday ret < 0 (sign) | 4.7 vs 3.3 | 5.4 vs 5.8 | 8.1 vs 5.0 | No - SMH reverses OOS (6.8 vs 15.5) | Reported effect is small and unstable; not used |
| intraday ret < -1% | 9.4 (1.2) | 8.3 (1.3) | 6.7 (1.2) | No (SPY OOS 1.1 bp) | Not used |
| intraday ret > +1% | -4.6 (-0.5) | 3.5 (0.6) | 2.5 (0.5) | QQQ/SPY OOS negative | Weak "skip after big up days"; not used (adds a rule for little) |
| close > 50d MA | 3.3 vs 5.7 (below!) | 4.5 vs 8.7 (below) | 6.2 vs 7.1 | Reverses OOS | Not used; 200d is the right horizon |
| VIX level 20-35 | 8-10 bp (t 1.6-2.5) | 8.4-9.6 | 12-16 | **No** - OOS negative (-0.7 to -1.8 bp) | Level effect is a 2010-2021 artefact; not used |
| VIX < 15 | 2.9 (3.1) | 4.8 (3.9) | 6.1 (3.3) | Yes but small | Consistent but weak; redundant with 200d MA |
| VIX/VIX3M > 1 (backwardation) | 4.9 (0.5) | 8.2 (0.8) | 5.5 (0.4) | Small n, noisy | No clear effect either way; not used |
| VIX > own 20d MA | 3.9 vs 3.9 | 5.1 vs 6.0 | 5.7 vs 7.0 | Flips OOS | No effect |
| realised vol 20d top quartile | 8.9 (2.0) | 12.9 (2.5) | 9.4 (1.2) | **No** - OOS -0.0 / -4.3 bp | High-vol nights paid in 2010-21, lost in 2022; subsumed by the trend gate |
| day of week (decision day) | Mon 7.0 (2.5), Tue 4.5; Wed 1.6, Fri 3.3 | Mon 9.9, Tue 7.8; Wed 2.7 | Mon 9.8, Tue 7.9; Wed 2.5 | Tue holds OOS (t 2.2-2.5), Mon fades, Wed rebounds | Mon/Tue nights are the best; Fri->Mon (weekend) is *not* special. Not used (calendar rules = overfitting risk) |
| last trading day of month | 18.7 (3.0), hit 72% | 21.6 (3.2) | 32.8 (4.1) | **No** - OOS -2 to -16 bp (n=57) | Striking in-sample, gone OOS. Not used |
| first 3 days of month | 1.7 | 2.4 | 4.0 | OOS strongly negative (-8 to -13 bp) | Not used, but see insights |
| 5d close-to-close ret < 0 | 6.9 (2.6) vs 2.2 | 8.2 vs 4.0 | 8.2 vs 5.3 | Partially | Correlated with the 5-night rule; the overnight-only version is cleaner |

### 2c. Strategy variants (140 trials: 7 asset sets x 20 rules), net, full period / OOS Sharpe

Selected rows (full = 2010-2026; OOS = 2022+):

| Assets | Rule | time in mkt | cost/yr | net Sharpe | CAGR | MaxDD | OOS Sharpe | OOS CAGR |
|---|---|---|---|---|---|---|---|---|
| QQQ | none | 50% | 5.0% | 0.68 | 8.1% | -30% | 0.39 | 4.5% |
| QQQ | ma200 | 43% | 4.3% | 1.01 | 9.6% | -20% | 1.10 | 11.0% |
| QQQ | on5_dn | 19% | 1.9% | 1.22 | 11.9% | -28% | 1.18 | 12.4% |
| QQQ | ma200 & on5_dn | 15% | 1.5% | 1.53 | 10.0% | -21% | 1.91 | 12.5% |
| SMH | none | 50% | 5.0% | 0.85 | 14.8% | -38% | 1.04 | 24.3% |
| SMH | ma200 | 40% | 4.1% | 1.20 | 18.2% | -23% | 1.51 | 32.2% |
| SMH | ma200 & on5_dn | 15% | 1.5% | 1.40 | 13.6% | -22% | 1.74 | 22.7% |
| IWM | ma200 & on5_dn | 13% | 1.3% | 1.13 | 6.5% | -11% | 1.07 | 7.5% |
| SPY | ma200 & on5_dn | 16% | 1.6% | 1.43 | 7.0% | -10% | 1.19 | 5.8% |
| QQQ+SMH | ma200 & on5_dn | 19% | 1.5% | 1.57 | 11.9% | -20% | 1.94 | 17.6% |
| **QQQ+SMH+IWM** | **ma200 & on5_dn** | **22%** | **1.4%** | **1.62** | **10.1%** | **-15%** | **1.91** | **14.2%** |
| QQQ+SMH+IWM | ma200 & (on5_dn or prev_on_dn) | 31% | 2.2% | 1.56 | 12.0% | -15% | 1.53 | 14.4% |
| QQQ+SMH+IWM | ma200 & on3_dn | 23% | 1.5% | 1.36 | 8.8% | -12% | 1.62 | 12.5% |
| QQQ+SMH+IWM | ma200 & on10_dn | 20% | 1.2% | 1.28 | 7.2% | -18% | 1.61 | 10.5% |
| QQQ+SMH+IWM | ma200 & intraday down | 28% | 1.8% | 1.08 | 7.2% | -12% | 0.93 | 7.6% |
| QQQ+SMH+IWM | ma200 & VIX<25 | 41% | 3.8% | 1.05 | 9.6% | -15% | 1.20 | 14.3% |
| QQQ+SMH+IWM | ma200 & VIX/VIX3M<1 | 42% | 3.8% | 1.21 | 11.3% | -14% | 1.26 | 14.5% |
| QQQ+SMH+IWM | ma200 & VIX<20dMA | 26% | 2.4% | 1.17 | 7.7% | -14% | 0.75 | 5.9% |
| QQQ+SMH+IWM | ma200 & Mon/Tue only | 17% | 1.6% | 1.36 | 7.7% | -9% | 0.98 | 6.7% |
| QQQ+SMH+IWM | tilt: 0.5 if ma200, 1.0 if also on5_dn | 44% | 2.7% | 1.47 | 11.1% | -15% | 1.68 | 15.5% |
| SPY+QQQ+SMH+IWM | ma200 & on5_dn | 23% | 1.5% | 1.65 | 9.4% | -13% | 1.84 | 12.1% |
| QQQ+SMH+IWM+SPY+DIA+XLK | ma200 & on5_dn | 25% | 1.5% | 1.56 | 8.4% | -14% | 1.66 | 9.8% |

`ma200 & on5_dn` is the best rule for every asset set both in-sample and OOS; adding
SPY/DIA/XLK dilutes CAGR for no Sharpe gain (in-sample Sharpe 1.56 vs 1.49 for the
4- vs 3-asset basket, ex-cash 1.09 vs 1.11 - a wash). Chose QQQ+SMH+IWM.

### 2d. Cross-sectional variant: mega-cap 12-1 momentum held overnight (8 trials), stock costs 2.5 bp/side

| Variant | cost/yr | net Sharpe | ex-cash Sharpe | CAGR | MaxDD | OOS Sharpe |
|---|---|---|---|---|---|---|
| EW all 70 stocks, every night | 12.6% | -0.04 | -0.11 | -1.1% | -34% | -0.64 |
| top-5 12-1 momentum, inverse-vol | 12.6% | 1.06 | 1.02 | 17.2% | -33% | 0.75 |
| top-5 + SPY>200d gate | 10.7% | 1.39 | 1.30 | 19.0% | -17% | 1.00 |
| top-10, inverse-vol | 12.6% | 0.73 | 0.67 | 9.2% | -31% | 0.46 |
| top-10 + SPY>200d gate | 10.7% | 1.08 | 0.96 | 11.0% | -19% | 0.82 |
| top-20 + SPY>200d gate | 10.7% | 0.73 | 0.57 | 5.7% | -21% | 0.48 |
| bottom-10 (losers), inverse-vol | 12.6% | -0.34 | -0.40 | -5.3% | -58% | -1.11 |

Lou-Polk-Skouras confirmed in this universe: top-5 12-1 winners earn +12.9 bp/night
gross (top-10: +10.0) vs bottom-10 losers +3.6 and the 70-stock average +4.5, and the
unconditional stock overnight premium does **not** survive 2.5 bp costs (5 bp round
trip vs 4.5 bp mean). Top-5 momentum is a real but cost-heavy (10-13%/yr),
concentrated (5 names), lower-OOS alternative with 0.50 correlation to the ETF sleeve. Not the
main sleeve; handed to the cross-sectional/momentum agent as an insight.

### 2e. Sizing and leverage (14 trials, all on the QQQ+SMH+IWM ma200&on5_dn base)

| Variant | net Sharpe (cash 4%) | **ex-cash Sharpe** | CAGR | MaxDD | OOS Sharpe |
|---|---|---|---|---|---|
| base EW 1/3 | 1.62 | 1.11 | 10.1% | -15.1% | 1.91 |
| 1/n_active (concentrate into active ETFs) | 1.29 | 0.94 | 11.5% | -20.3% | 1.56 |
| inverse-vol, target 15%, cap 1x | 1.90 | 1.12 | 8.2% | -8.5% | 2.29 |
| inverse-vol, target 20%, cap 1x | 1.75 | 1.11 | 8.9% | -10.2% | 2.05 |
| inverse-vol, target 25%, cap 1x | 1.71 | 1.12 | 9.5% | -10.8% | 1.96 |
| inverse-vol, target 20%, cap 0.5x | 2.30 | 1.11 | 7.0% | -7.1% | 2.48 |
| QLD in the QQQ slot | 1.49 | 1.10 | 12.2% | -22.3% | 1.78 |
| TQQQ in the QQQ slot | 1.46 | 1.14 | 14.9% | -28.9% | 1.73 |
| QLD in QQQ slot only when all 3 signals on | 1.53 | 1.10 | 11.2% | -17.7% | 1.79 |

**Inverse-vol scaling does not add edge**: the ex-cash Sharpe is 1.11-1.12 in every
row; the higher headline Sharpe comes entirely from holding more cash at 4%. It does
cut MaxDD roughly in half, which the ensemble can achieve by allocation instead.
Left available (`vol_target`) but off. **Leverage substitution** works as expected
once nights are filtered: QLD adds +2.1 pp CAGR at the same ex-cash Sharpe with ~1.5x
the drawdown; TQQQ +4.8 pp CAGR at ~2x drawdown. Off by default (`leverage_map`).

### 2f. Hourly timeline (5 trials, `md.px_intraday`, 2023-10 -> 2026-09, OOS split 2025-09-01)

| Entry -> exit | net Sharpe | CAGR | MaxDD | IS Sharpe | OOS Sharpe |
|---|---|---|---|---|---|
| **16:00 -> 09:30** (main sleeve on hourly panel) | 2.63 | 22.3% | -9.4% | 3.30 | 2.02 |
| 16:00 -> 10:30 | 1.97 | 19.6% | -8.8% | 2.65 | 1.31 |
| 16:00 -> 11:30 | 1.72 | 17.0% | -6.4% | 2.31 | 1.11 |
| 15:30 -> 09:30 | 2.42 | 21.5% | -8.9% | 2.93 | 1.96 |
| 15:30 -> 10:30 | 1.82 | 18.8% | -8.2% | 2.37 | 1.28 |

(Daily panel over the same window: Sharpe 2.65 - the two panels agree.) Holding
through the first hour **hurts**: on the mornings after a night we were long, the
09:30->10:30 return averaged -2.8 bp for all three ETFs (t ~ -0.7), i.e. no
first-hour continuation, mild reversal. Entering at 15:30 is slightly worse than the
close. Main sleeve stays 16:00 -> 09:30.

### 2g. Sensitivity + ablation (24 trials) - see section 4.

**n_trials = 24 + 64 + 140 + 8 + 14 + 5 + 24 + 7 (per-asset / gross / ex-cash / QLD scorecards) = 286.**

## 3. Final scorecard

### 3a. Net of default costs (engine defaults, 4% cash yield) - `report()` output

```
overnight          | CAGR  10.11% | Vol  6.04% | Sharpe  1.62 | Sortino  1.31 | MaxDD -15.07% | Calmar  0.67 | t  6.47 | PF 1.58 | exp L/S 0.14/0.00 | cost/yr 1.43% | days 3992
  time in market 22.0% | turnover/day 0.57 | trades/day 1.71 | skew -0.54 | kurt 23.5 | best +3.07% | worst -5.16%
  Sharpe 95% bootstrap CI: [1.04, 2.22]
  Deflated Sharpe: P(SR > null max of 286 trials = 0.72) = 1.000
  vs benchmark: corr 0.32 | beta 0.11

  Yearly:
       return      vol   sharpe   max_dd  days
2010    0.004    0.069    0.281   -0.021    53
2011    0.030    0.060    0.533   -0.053   252
2012    0.081    0.048    1.647   -0.042   250
2013    0.183    0.049    3.445   -0.019   252
2014    0.115    0.046    2.419   -0.024   252
2015    0.042    0.033    1.267   -0.024   252
2016    0.030    0.038    0.815   -0.036   252
2017    0.111    0.029    3.699   -0.015   251
2018    0.074    0.050    1.450   -0.033   251
2019    0.005    0.060    0.112   -0.108   252
2020    0.116    0.100    1.139   -0.147   253
2021    0.171    0.060    2.681   -0.035   252
2022    0.012    0.032    0.392   -0.029   251
2023    0.043    0.074    0.614   -0.062   250
2024    0.307    0.071    3.783   -0.026   252
2025    0.182    0.060    2.839   -0.025   250
2026    0.137    0.112    1.787   -0.094   167

  In-sample / out-of-sample split at 2022-01-01:
                         days     cagr      vol   sharpe  sortino  max_drawdown   calmar
overnight in-sample      2822    0.085    0.055    1.493    1.123        -0.151    0.561
overnight out-of-sample  1170    0.142    0.071    1.906    1.779        -0.094    1.508
overnight full           3992    0.101    0.060    1.624    1.311        -0.151    0.671
```

Gross (zero cost): Sharpe 1.86, CAGR 11.7%, MaxDD -14.6%; IS 1.76 / OOS 2.09.
Cost drag is 1.43%/yr (vs 5%/yr for the unconditional version).

### 3b. Ex-cash view (cash_yield_annual = 0) - the honest risk-adjusted number

The engine pays 4%/yr on idle cash and `metrics.sharpe` uses rf = 0, so a sleeve
that is in the market 22% of the time gets ~3%/yr of zero-vol carry, worth ~+0.5
Sharpe here. All sleeves are judged this way (the brief's baselines include it), but
for the ensemble the excess-return numbers are what matter:

```
overnight ex-cash  | CAGR   6.76% | Vol  6.05% | Sharpe  1.11 | Sortino  1.03 | MaxDD -17.25% | Calmar  0.39 | t  4.43 | PF 1.39 | cost/yr 1.43%
  Sharpe 95% bootstrap CI: [0.56, 1.67]
  Deflated Sharpe: P(SR > null max of 286 trials = 0.72) = 0.933
  in-sample Sharpe 0.94 (CAGR 5.2%) | out-of-sample Sharpe 1.46 (CAGR 10.7%, MaxDD -9.5%)
  ex-cash yearly Sharpe: 2011 0.0, 2012 1.0, 2013 2.9, 2014 1.8, 2015 0.4, 2016 0.0, 2017 2.6, 2018 0.8,
                         2019 -0.4, 2020 0.8, 2021 2.2, 2022 -0.8, 2023 0.2, 2024 3.3, 2025 2.3, 2026 1.5
```

Same-window comparison, ex-cash: QQQ unconditional overnight is 0.68 - 0.5 = ~0.2;
SPY buy & hold 0.86 (rf = 0). The sleeve's ex-cash Sharpe of 1.1 on 14% average
exposure is the useful number; the gross-of-cash 1.62 is what `report()` prints.

Shared-code note (not a bug, a convention): `metrics.sharpe` is not rf-adjusted while
the engine credits cash carry, so low-exposure sleeves look better than high-exposure
ones with identical edge. Suggest the ensemble compare sleeves on
`cash_yield_annual=0` results or on Sharpe of excess returns.

## 4. Sensitivity (one-at-a-time around the chosen params; net Sharpe incl. cash)

| param | value | in-sample | OOS | full |
|---|---|---|---|---|
| ma_window | 50 | 1.69 | 1.61 | 1.62 |
| | 100 | 1.55 | 1.56 | 1.53 |
| | 150 | 1.43 | 1.74 | 1.53 |
| | **200** | **1.49** | **1.91** | **1.62** |
| | 250 | 1.52 | 2.02 | 1.68 |
| | 300 | 1.26 | 2.00 | 1.50 |
| on_window | 2 | 1.12 | 1.62 | 1.29 |
| | 3 | 1.24 | 1.62 | 1.36 |
| | 4 | 1.34 | 1.96 | 1.54 |
| | **5** | **1.49** | **1.91** | **1.62** |
| | 6 | 1.27 | 1.93 | 1.49 |
| | 7 | 1.15 | 1.75 | 1.34 |
| | 10 | 1.12 | 1.61 | 1.28 |
| | 15 | 1.41 | 1.75 | 1.52 |
| on_threshold | -1.0% | 1.43 | 1.94 | 1.59 |
| | -0.5% | 1.60 | 1.95 | 1.71 |
| | -0.25% | 1.46 | 1.86 | 1.59 |
| | **0.0%** | **1.49** | **1.91** | **1.62** |
| | +0.25% | 1.31 | 1.99 | 1.54 |
| | +0.5% | 1.39 | 1.86 | 1.54 |
| | +1.0% | 1.15 | 1.72 | 1.34 |

Ablation (full / IS / OOS net Sharpe): both rules 1.62 / 1.49 / 1.91; trend only
1.21 / 1.15 / 1.33; reversal only 1.13 / 1.13 / 1.12; neither 0.79 / 0.82 / 0.73.

The MA window and the threshold are flat plateaus (every value in the grid beats
either single rule). The overnight-reversal window is the one parameter with a
visible in-sample peak at 4-6 days (1.34-1.49) versus 1.12-1.24 at 2-3 and 7-10
days; OOS is flat (1.6-2.0) across the whole grid, so the *existence* of the effect
is robust but 5 is a modest in-sample choice, not a magic number. Honest reading:
expect the ex-cash Sharpe going forward closer to 0.9 (in-sample) than to 1.5 (OOS).

## 5. Correlations

- Daily returns vs SPY close-to-close: **0.32** (beta 0.11); OOS only 0.25. On the
  days after a held night the correlation is 0.57 (it *is* long equity beta on
  those nights); on the ~58% of days with no position it is 0 by construction.
- vs SPY overnight return (aligned): 0.49; vs QQQ unconditional overnight: 0.53.
- vs the cross-sectional momentum-overnight variant (2d, top-5 + SPY gate): 0.50.
- No other sleeve notes exist in `research/notes/` yet. Expected: low-to-moderate
  positive correlation with any long-biased intraday/trend sleeve on the same ETFs
  (shared 200d gate), near zero with intraday mean-reversion sleeves (we are flat
  09:30-16:00), and negative with a "short overnight after strong nights" design.

## 6. Failure modes / when to turn it off

- **Gap risk is the whole risk.** Vol is 6% but kurtosis is 23; the worst days are
  gap-downs after a night held (2020-03-09 -5.2%, 2020-02-24 -3.8%, 2011-03-15
  -2.9%). The 200d gate is slow - it stays long into the first leg of a crash
  (Feb 2020) and only exits once the MA is breached. Daily MaxDD -15% (Mar 2020);
  -11% in 2019 via a slow bleed rather than a crash.
- **Prolonged bear markets = flat / cash.** 2022: 10% time in market, +1.2% (cash
  carry). Fine, but the sleeve contributes nothing in downtrends - by design.
- **Regime where overnight premium migrates intraday.** 2019 (ex-cash -0.4) and
  2015-16 (~0) were years where the overnight premium in QQQ/SMH was near zero
  despite an uptrend. Monitor the trailing 250-night gross mean of the held-night
  return; if it falls below ~1 bp, the edge has left and costs dominate.
- **Data caveats:** Yahoo opens are auction prints; live fills at MOO/MOC should be
  close to them, and the 1 bp/side cost is 2-5x conservative for QQQ/SMH/IWM. If
  execution slips to 2 bp/side the net Sharpe is 1.39 (CAGR 8.5%, drag 2.9%/yr); at
  3 bp/side 1.15 (CAGR 7.0%, drag 4.3%/yr). OOS stays 1.5-1.7 in both cases.
- `^VIX3M` is missing after 2026-07-17 in the cache (and 32 days since 2011). Not
  used by the final sleeve, but any sleeve using the VIX term structure must ffill.
- Semiconductor concentration: SMH is 1/3 of the sleeve and 1/2 of the CAGR
  (stand-alone SMH CAGR 13.6% vs 6.5% for IWM). A sector-specific shock in
  semis after hours (earnings from NVDA/TSM/ASML) is the largest idiosyncratic risk.
  Earnings-night avoidance was not tested.

## 7. Recommended params and ensemble allocation

`OvernightParams()` defaults: assets (QQQ, SMH, IWM), require_trend=True, ma_window=200,
require_on_reversal=True, on_window=5, on_threshold=0.0, leverage_map={}, vol_target=None.

Suggested allocation: **25-35% of the ensemble's gross budget** to this sleeve, on
the basis of ex-cash Sharpe ~1.0 with 0.3 correlation to SPY and only 22% time in
market (its cash is free for other sleeves between 09:30 and 16:00, and on the ~58%
of nights it is flat). If the ensemble wants more CAGR from the same signal without
raising the allocation, set `leverage_map={"QQQ": "QLD"}` (+2 pp CAGR, MaxDD -22%
instead of -15%, identical ex-cash Sharpe) rather than concentrating into fewer ETFs.
Do not use `vol_target` for Sharpe - it only adds cash carry.

## 8. Insights for other sleeves

1. **200d MA on the asset's own close is the single most robust regime gate found.**
   Below the MA, the overnight premium in QQQ/SMH is *negative* OOS (-5 bp/night).
   Any long-biased sleeve should at minimum halve exposure below the 200d MA. The
   50d MA does not work (reverses OOS). Regime agent: use 200d, not 50d, not VIX level.
2. **VIX level and realised-vol regime are unstable conditioners for overnight
   returns.** VIX 20-35 / top-quartile RV paid 8-13 bp/night in 2010-21 and lost
   money in 2022+. VIX term structure (VIX/VIX3M) had no reliable effect. VIX below
   its own 20d MA: no effect. Regime agent: don't build on VIX buckets alone.
3. **Overnight returns in index ETFs mean-revert at 3-6 night horizons** (sum of last
   5 overnight returns < 0 -> next night ~3x the mean). Conversely, after 5 strong
   nights the next night is ~zero. This is the time-series opposite of the
   cross-sectional persistence in Lou-Polk-Skouras and is the highest-value
   conditioning signal here. A short-overnight sleeve after strong nights below the
   200d MA is worth a look (not tested - long-only mandate).
4. **Intraday session is where reversal lives, overnight is where beta lives.** IWM
   intraday mean is ~0 (all of its return is overnight); SPY/QQQ intraday mean is
   positive but ~half the overnight. First-hour (09:30-10:30) return after an
   overnight rally is slightly negative: no continuation. Intraday sleeves should
   be mean-reversion / short-biased in the first hour, not momentum.
5. **Stock overnight premium does not survive 2.5 bp costs unconditionally** (EW-70
   ex-cash Sharpe -0.1, 12.6%/yr cost) but **12-1 momentum top-5 winners earn +13
   bp/night overnight** vs +3.6 for losers (top-5 + SPY>200d: net Sharpe 1.39, CAGR
   19%, OOS 1.0). The spread is ~9 bp/night, i.e. the momentum premium is overnight.
   Momentum/cross-sectional agent: put the long leg on overnight, be flat intraday.
6. **Calendar effects are traps.** Last-trading-day-of-month overnight was +19 to
   +33 bp with 72% hit rate in-sample (t 3-4) and *negative* OOS; first-3-days of
   month went from flat to -8/-13 bp OOS. Mon/Tue nights are consistently the best
   and Wed the worst, but the weekend (Fri->Mon) carries no premium beyond its extra
   calendar days.
7. **Leverage arithmetic:** 2x/3x ETFs lose ~0.15 Sharpe vs the 1x version when held
   every night (vol drag + double cost) but preserve ex-cash Sharpe once a filter
   cuts holding to <25% of nights. Use them only behind a filter.
8. **Engine convention:** `report()` Sharpe includes 4% cash carry with rf = 0. A
   sleeve that is 78% in cash gets ~+0.5 Sharpe for free; compare sleeves with
   `cash_yield_annual=0` before allocating.
