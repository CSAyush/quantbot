# Gap-fade reversal on the 300-name universe (`hf_reversal.py`, Round 2 breadth study)

Question: the live sleeve buys the 7 biggest beta-adjusted, vol-scaled gap-down names out of
70 mega-caps at 09:30, is flat at 16:00, exposure = clip((VIX[d-1]-18)/10, 0, 1). The red team
found Sharpe 0.77 -> ~0.5 on a 38-name universe, i.e. breadth helps. Does the 300-name
`HFConfig.wide()` universe help, by how much, and is the gain real (survivorship, liquidity,
costs) and worth switching the live sleeve for?

Conventions: daily timeline, start 2010-06-01, rf = `md.cash_yield()` (^IRX, mean 1.5%),
Sharpe in excess of it, net of costs (2.5 bp/side stocks unless stated; "5 bp" = 5 bp/side on
every stock, ETFs at their defaults). IS < 2022-01-01, OOS >= 2022. Tuning used IS only; the
gate parameters were deliberately *not* re-tuned (section 6). **`n_trials = 86`** this round
(tally in 2h); cumulative for the sleeve 354 + 86 = **440**, used in the deflated Sharpe.
Cost re-pricings (5 / 7.5 / 10 bp, tiered) are not counted: they do not select anything.

**Headline.** Same rule, same n = 7, 300 names instead of 70: net Sharpe **0.77 -> 1.36**
(IS 0.78 -> 1.60, OOS 0.74 -> 0.88), CAGR 8.5% -> 17.8%, MaxDD -12.3% -> -19.4%. At an honest
5 bp/side for the wide universe: **1.15** (IS 1.39 / OOS 0.66), CAGR 14.9%. Larger n is
monotonically worse (n = 15: 1.02; n = 30: 0.76 = the 70-name sleeve). The whole gain comes from
the *less liquid* two-fifths of the universe (a top-150 liquidity screen gives 0.76, top-200
0.87): Avramov-Chordia-Goyal, exactly as the literature predicts, which also means the gain sits
where costs, open-print quality and survivorship are worst. Removing the 50 names that did not
exist in June 2010 costs 0.17 Sharpe; a pseudo point-in-time universe (the 150 most liquid
survivors *as of 2010*) gives 0.93 (OOS 0.76), i.e. the credible low-survivorship breadth gain
is ~+0.15 Sharpe with an unchanged OOS. Nearly half of the wide sleeve's P&L is 2011 + 2020;
dropping 2010-11 and 2020 leaves 0.85 (0.66 at 5 bp) vs 0.69 for the 70-name sleeve. In the
growth ensemble at the same 0.5 allocation: Sharpe 1.31 -> **1.75** (1.60 at 5 bp), CAGR 11.5% ->
16.5% (15.1%), MaxDD -12.2% -> -12.4%; OOS 1.53 -> 1.58 (**1.42 at 5 bp**). Recommendation in
section 11: **do not switch the live sleeve yet**; shadow-trade the wide book for fill quality
and switch to n = 7 / allocation 0.5 (never more) once fills are shown to be within ~3 bp of
the open print in the illiquid tail.

## 1. Hypothesis

Breadth helps a cross-sectional sort twice: the bottom-7-of-300 gap is a more extreme
(more liquidity-driven, less news-driven) selection than bottom-7-of-70, and the universe-average
gap used for the beta adjustment is better estimated. Against that, the extra names are smaller
and less liquid: Avramov, Chordia & Goyal (2006) and Nagel (2012) say reversal is *larger* there
(liquidity provision is scarcer), but the same names have wider spreads, noisier opening prints
and - because the 300 are an early-2026 snapshot - the strongest survivorship bias. So the prior
was "gross edge up, but the honest net gain is smaller than the backtest shows". Confirmed.

## 2. Everything tested

### 2a. Universe and n (14 trials; n as a fraction = round(frac x names ranked that day))

| variant | Sharpe (IS / OOS) @2.5 bp | CAGR | MaxDD | Sharpe (IS / OOS) @5 bp | CAGR @5 | names/day | max w |
|---|---|---|---|---|---|---|---|
| **core-70 n=7 (live)** | **0.77 (0.78 / 0.74)** | 8.5% | -12.3% | 0.50 (0.53 / 0.44) | 5.9% | 7 | 14% |
| core-70 n=3 / 5 / 10 | 0.89 / 0.85 / 0.67 | 11 / 10 / 7% | -15 / -12 / -15% | | | | |
| **wide-300 n=7** | **1.36 (1.60 / 0.88)** | 17.8% | -19.4% | **1.15 (1.39 / 0.66)** | 14.9% | 7 | 14% |
| wide-300 n=10 | 1.13 (1.32 / 0.73) | 13.9% | -17.7% | 0.90 (1.10 / 0.48) | 11.1% | 10 | 10% |
| wide-300 n=15 | 1.02 (1.20 / 0.64) | 12.0% | -15.2% | 0.78 (0.97 / 0.39) | 9.3% | 15 | 6.7% |
| wide-300 n=20 | 0.94 (1.10 / 0.60) | 10.7% | -13.1% | 0.68 (0.85 / 0.34) | 8.0% | 20 | 5% |
| wide-300 n=30 | 0.76 (0.89 / 0.48) | 8.6% | -12.4% | 0.50 (0.64 / 0.20) | 5.9% | 30 | 3.3% |
| wide-300 n=5 | 1.35 (1.69 / 0.66) | 19.4% | -23.0% | 1.16 (1.50 / 0.45) | 16.5% | 5 | 20% |
| wide-300 n=3 | 1.27 (1.61 / 0.50) | 20.3% | -32.1% | 1.09 (1.44 / 0.31) | 17.3% | 3 | 33% |
| wide-300 frac 2% (~5.7) | 1.36 (1.65 / 0.76) | 18.7% | -20.9% | 1.16 (1.45 / 0.54) | 15.8% | 5.7 | |
| wide-300 frac 3% (~8.6) | 1.21 (1.42 / 0.77) | 15.2% | -19.0% | 0.98 (1.20 / 0.53) | 12.4% | 8.6 | |
| wide-300 frac 5% (~14) | 1.03 (1.22 / 0.64) | 12.2% | -15.2% | 0.79 (0.98 / 0.39) | 9.4% | 14.1 | |
| wide-300 frac 7% / 10% | 0.95 / 0.80 | 10.8 / 9.1% | -12.8 / -12.5% | 0.70 / 0.55 | | 20 / 28 | |

The max-weight column is per name at full exposure (1/n); the ensemble's 0.5 allocation and the
VIX ramp (mean exposure 0.10) halve it again. Cost/yr is 2.49% for every row at 2.5 bp (4.98% at
5 bp): the sleeve trades a full round trip on 40% of days regardless of n, so n does not change
the cost, only the dilution. **Sharpe falls monotonically in n on 300 names**: the signal is
concentrated in the extreme tail, and holding 15-30 names does not lower idiosyncratic noise
enough to pay for the dilution. n = 7 (or frac 2%) is the IS optimum among sensible sizes and
also the OOS optimum; n = 3-5 wins IS and loses OOS, as in round 1. `frac` adds nothing over
a fixed n = 7 (the universe count barely moves after 2012) and is left off.

### 2b. Liquidity screen (12 trials): keep only the top-K names by trailing 60d median dollar volume (known at 09:30 of d)

Dollar-volume context (60d median, $M/day) at rank 1 / 70 / 150 / 200 / 250 / last: 2012:
11083 / 175 / 84 / 49 / 12 / 1; 2018: 6811 / 339 / 182 / 126 / 78 / 18; 2025: 33338 / 860 /
473 / 339 / 262 / 57. The top-150 today contains all 70 core names; the top-100 contains 63.

| K | n=5 | n=7 | n=10 | n=15 | (all @2.5 bp; @5 bp in parentheses for n=7) |
|---|---|---|---|---|---|
| 100 | 0.66 (0.80 / 0.39) | 0.64 (0.73 / 0.46) (5 bp: 0.41) | 0.58 | 0.47 | worse than core-70 |
| 150 | 0.83 (0.98 / 0.53) | 0.76 (0.93 / 0.44) (5 bp: 0.53) | 0.75 | 0.65 | = core-70 |
| 200 | 0.86 (1.04 / 0.52) | 0.87 (1.00 / 0.62) (5 bp: 0.65) | 0.79 | 0.76 | small gain, OOS below core |
| 300 (none) | 1.35 | **1.36 (1.60 / 0.88)** (5 bp: 1.15) | 1.13 | 1.02 | |

**The breadth gain is the illiquid tail.** Restricting to the 150 most liquid names gives back the
entire improvement; even the top-200 keeps only a quarter of it, and the top-100 by *dollar
volume* (which swaps low-volume mega-caps like LIN/SPGI/BLK for heavily-traded names like
TSLA/AMD/COIN) is *worse* than the 70 by market cap. Where the picks come from and what they earn
(wide n=7, active days, gross intraday return of the picked names by liquidity rank):

| liquidity rank of pick | picks | gross bp/pick | t | EW of that bucket, same days |
|---|---|---|---|---|
| 1-70 | 3548 (32%) | 21.9 | 5.4 | 6.1 |
| 71-150 | 3416 (30%) | 21.6 | 4.6 | 6.3 |
| 151-200 | 1816 (16%) | 31.7 | 5.3 | 6.7 |
| 201-250 | 1708 (15%) | 49.2 | 7.9 | 7.7 |
| 251+ | 859 (8%) | 66.9 | 5.8 | 10.0 |

Picks below rank 200 are 23% of the book and earn 2-3x the fade of the liquid names; the
unconditional (EW) intraday drift of those buckets is only 2-4 bp higher, so the extra is
conditional on the gap, i.e. genuine cross-sectional reversal in less liquid names (Avramov et
al.), not just drift. Only 30% of picks are core-70 names. Most-picked: NEM 145 days, LIN 98,
JNJ 87, FCX 81, CCL 79, COP 76, XOM 72. Top-15 names by P&L contribution = 31% of the total
(EQT 12% of total, TRGP 9%, NEM 8.5%, COIN 8%, CMCSA 6%); no single name dominates.

### 2c. Signal refinements on wide (12 trials)

| variant | n=5 | n=7 | n=10 | n=15 |
|---|---|---|---|---|
| eq (base) | 1.35 (1.69 / 0.66) | **1.36 (1.60 / 0.88)** | 1.13 (1.32 / 0.73) | 1.02 (1.20 / 0.64) |
| ivol weighting | 1.30 (1.67 / 0.53), DD -21.5% | 1.34 (1.62 / 0.77), DD -17.3% | 1.10 (1.36 / 0.58) | 1.01 (1.23 / 0.55) |
| skip \|gap\| > 8% | | 1.16 (1.43 / 0.64) | | 0.89 (1.08 / 0.51) |
| skip \|gap\| > 5% | | 1.01 (1.20 / 0.62) | | 0.76 (0.89 / 0.49) |
| mode = ls (0.5/0.5) | | 1.91 (2.40 / 0.79), CAGR 14.1%, DD -10.7%; 5 bp: 1.52 (2.04 / 0.35) | | |
| mode = hedged (short SPY) | | 1.40 (1.77 / 0.57), CAGR 7.5%, DD -7.7% | | |

Inverse-vol weighting: a wash on Sharpe (-0.02), lowers MaxDD by 2 pts at n = 7, worse OOS -
left at eq. **The outlier filter hurts on 300 names** (opposite of "does nothing" on 70): with a
wider universe the bottom-7 contains more big gaps and those *do* revert here (the 251+ bucket
above). Sector-neutral ranking: no sector data, not tested. The `ls` book is again spectacular
in-sample (2.40) and again dies OOS (0.79 -> 0.35 at 5 bp): the short leg's IS/OOS collapse is
universe-independent. Long-only stays the design.

### 2d. VIX gate on wide (11 trials) - see section 6 for the bucket table

| gate (wide n=7) | active | Sharpe (IS / OOS) @2.5 | CAGR | MaxDD | cost/yr | @5 bp |
|---|---|---|---|---|---|---|
| none | 100% | 1.92 (2.55 / 0.70) | 45.0% | -24.8% | 12.6% | 1.27 (1.85 / 0.14) |
| none, n=15 | 100% | 1.52 (2.18 / 0.21) | 28.8% | -23.8% | 12.6% | |
| none, core-70 n=7 | 100% | 0.84 (1.19 / 0.08) | 14.5% | -31.7% | 12.6% | |
| floor 12 | 46% | 1.70 (2.08 / 0.99) | 29.8% | -22.1% | 6.4% | 1.28 (1.66 / 0.57) |
| floor 14 | 37% | 1.58 (1.88 / 1.02) | 25.1% | -21.6% | 4.7% | 1.24 (1.54 / 0.67) |
| floor 16 | 28% | 1.47 (1.72 / 0.99) | 21.2% | -20.8% | 3.4% | 1.20 (1.45 / 0.71) |
| **floor 18 (live)** | 20% | **1.36 (1.60 / 0.88)** | 17.8% | -19.4% | 2.5% | **1.15 (1.39 / 0.66)** |
| floor 20 | 14% | 1.24 (1.50 / 0.70) | 14.8% | -17.0% | 1.8% | 1.07 (1.33 / 0.52) |
| floor 22 | 10% | 1.19 (1.43 / 0.62) | 12.9% | -13.9% | 1.3% | 1.05 (1.30 / 0.47) |
| span 1 (cliff at 18) | 20% | 1.63 (1.84 / 1.25) | 28.3% | -22.2% | 4.6% | |
| span 5 | 20% | 1.46 (1.66 / 1.07) | 22.1% | -21.5% | 3.4% | |
| span 15 | 20% | 1.37 (1.60 / 0.86) | 15.6% | -15.2% | 1.9% | |

### 2e. Survivorship variants (9 trials incl. 2010-liquidity split) - section 4

### 2f. Ensemble variants (28 trials) - section 9

### 2g. Not counted: cost re-pricings (5 / 7.5 / 10 bp, tiered), breakeven, drop-year and block checks, decomposition tables.

### 2h. Trial count

2a 14 + 2b 12 + 2c 12 + 2d 11 + 2e 9 + 2f 28 = **86**. With round 1's 354: **440**.

## 3. Final scorecard: `ReversalParams(n=7)` on `MarketData(HFConfig.wide())` (= the defaults; only the universe changes)

Weights build in 0.2 s. `report()` at 2.5 bp/side:

```
reversal wide      | CAGR  17.80% | Vol 11.40% | Sharpe  1.36 | Sortino  2.09 | MaxDD -19.40% | Calmar  0.92 | t  6.02 | PF 1.69 | exp L/S 0.10/0.00 | cost/yr 2.49% | days 4090
  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean 1.5% over the period)
  time in market 19.8% | turnover/day 0.40 | trades/day 5.55 | skew 2.74 | kurt 29.1 | best +8.26% | worst -5.48%
  Sharpe 95% bootstrap CI: [0.92, 1.79]
  Deflated Sharpe: P(SR > null max of 440 trials = 0.75) = 0.997
  vs benchmark: corr 0.37 | beta 0.25

  Yearly:
       return      vol   sharpe   max_dd  days
2010    0.238    0.121    3.006   -0.069   150
2011    0.606    0.170    2.864   -0.083   252
2012    0.050    0.036    1.355   -0.031   250
2013    0.006    0.004    1.501   -0.002   252
2014    0.064    0.036    1.747   -0.011   252
2015    0.146    0.087    1.601   -0.019   252
2016    0.094    0.068    1.306   -0.046   252
2017    0.009    0.000   -0.236    0.000   251
2018    0.034    0.089    0.209   -0.073   251
2019    0.083    0.037    1.610   -0.018   252
2020    1.161    0.255    3.126   -0.148   253
2021    0.065    0.071    0.920   -0.057   252
2022    0.213    0.230    0.868   -0.194   251
2023    0.108    0.038    1.420   -0.023   250
2024    0.120    0.051    1.289   -0.019   252
2025    0.151    0.127    0.861   -0.082   250
2026    0.132    0.080    1.910   -0.051   168

  In-sample / out-of-sample split at 2022-01-01:
                             days     cagr      vol   sharpe  sortino  max_drawdown   calmar
reversal wide in-sample      2919    0.187    0.108    1.598    2.697        -0.148    1.265
reversal wide out-of-sample  1171    0.156    0.129    0.883    1.203        -0.194    0.804
reversal wide full           4090    0.178    0.114    1.362    2.095        -0.194    0.917
```

At 5 bp/side on every stock (the honest number for a universe whose tail traded $12-50M/day in
2012): `CAGR 14.91% | Vol 11.36% | Sharpe 1.15 | Sortino 1.73 | MaxDD -20.54% | cost/yr 4.98%`,
bootstrap CI [0.70, 1.58], deflated P = 0.959; IS 1.39 / OOS 0.66; yearly Sharpe 2022-26:
0.50 / 1.14 / 1.16 / 0.70 / 1.68.

Ex-cash (pure trading P&L): Sharpe 1.37 (IS 1.60 / OOS 0.89), CAGR 16.1%, MaxDD -19.7%. Gross
ex-cash: 1.58 (1.81 / 1.12), CAGR 19.0%. Active days 1622 (40%), mean +16.1 bp (core: +7.2),
hit rate 58% (core 55%), worst -5.48% (2025-04-04), best +8.26% (2020-06-15). **Breakeven cost
18.1 bp/side** (core 9.7; wide n=15 13.0; wide top-200 12.2; survivors-250 15.6). At 7.5 bp
Sharpe 0.93 (OOS 0.43), at 10 bp 0.71 (OOS 0.20).

Year by year vs the live sleeve (net, 2.5 bp): wide beats core in 14 of 17 years; the misses are
2012 (5.0 vs 6.4%), 2018 (3.4 vs 12.5%) and, on Sharpe, 2022 (0.87 vs 1.08) and 2024 (1.29 vs
1.59). **2011 (+61%) and 2020 (+116%) are 47% of the wide sleeve's summed daily returns** (core:
25%); 2022+ is 26% (core 37%).

| period | core-70 | wide-300 @2.5 | wide-300 @5 |
|---|---|---|---|
| 2010-2015 | 1.09 (CAGR 9.1%, DD -11.1%) | 1.85 (18.3%, -8.3%) | 1.63 (15.8%, -9.0%) |
| 2016-2021 | 0.55 (6.0%, -12.3%) | 1.44 (19.1%, -14.8%) | 1.24 (16.1%, -16.3%) |
| 2022-2026 | 0.74 (11.2%, -10.2%) | 0.88 (15.6%, -19.4%) | 0.66 (12.3%, -20.5%) |
| 3y blocks 2010-12 / 13-15 / 16-18 / 19-21 / 22-24 / 25- | 1.32 / 0.91 / 0.65 / 0.52 / 0.87 / 0.47 | 2.36 / 1.27 / 0.55 / 1.98 / 0.77 / 1.15 | 2.05 / 1.18 / 0.41 / 1.73 / 0.52 / 0.97 |
| drop 2020 | 0.80 | 1.16 | 0.95 |
| drop 2010-11 | 0.67 | 1.14 | 0.95 |
| drop 2010-11 + 2020 | 0.69 | 0.85 | 0.66 |

Reading: the wide sleeve is a *bigger stress-regime bet*. It earns far more than the core sleeve
in the three liquidity-crisis episodes (2011, 2020, the 2025-26 spring) and roughly the same,
or less after honest costs, in ordinary years and in 2022 (when it took its -19% drawdown while
the core sleeve had its best year). At 5 bp it beats the core sleeve in 4 of 6 three-year blocks.

## 4. Survivorship

The 300 names are the largest S&P constituents in early 2026. 250 had a price on 2010-06-01
(255 start in 2010, 5 in 2011, 6 in 2012, ... 1 in 2026); the 50 late entrants are IPOs and
spin-offs (ABBV ABNB ANET APO APP CARR CEG COIN CRWD DASH DDOG GEHC GEV HOOD KKR META NOW PANW
PLTR PYPL TRGP TSLA UBER ...). A second, sharper cut: rank the 250 survivors by their **2010-H2
dollar volume**; the top 150 are the names a 2010 researcher would plausibly have picked
("big-in-2010"); the other 100 were small/illiquid in 2010 and grew into the 2026 top-300
("small-in-2010": ACGL AJG AME APH AVGO AXON BX CDNS CPRT CTAS DLR EQIX EQT FICO FTNT GWW ...).
EW buy & hold CAGR: big-in-2010 17.7%, small-in-2010 20.7%, core-70 20.1%; intraday-only drift
2.8 / 3.8 / 3.2 bp/day.

| universe | names | Sharpe (IS / OOS) @2.5 | CAGR | MaxDD | @5 bp | 2010-15 / 2016-21 / 2022-26 |
|---|---|---|---|---|---|---|
| all 300, n=7 | 300 | 1.36 (1.60 / 0.88) | 17.8% | -19.4% | 1.15 (1.39 / 0.66) | 1.85 / 1.44 / 0.88 |
| survivors (data on 2010-06-01), n=7 | 250 | 1.19 (1.42 / 0.70) | 14.9% | -18.1% | 0.96 (1.20 / 0.47) | 1.79 / 1.17 / 0.70 |
| survivors, n=15 | 250 | 1.02 (1.18 / 0.70) | 11.5% | -13.1% | 0.76 | 1.65 / 0.84 / 0.70 |
| survivors not in core-70, n=7 | 185 | 1.05 (1.31 / 0.48) | 13.4% | -18.0% | | 1.80 / 0.99 / 0.48 |
| late entrants only, n=3 | 50 | 0.67 (0.74 / 0.56) | 11.1% | -26.0% | | |
| **big-in-2010 (pseudo point-in-time), n=7** | 150 | **0.93 (1.02 / 0.76)** | 11.3% | **-12.2%** | 0.70 (0.79 / 0.50) | |
| big-in-2010, n=5 | 150 | 0.91 (1.00 / 0.71) | 11.6% | -12.3% | 0.68 | |
| big-in-2010 + top-100 liquidity screen, n=7 | | 0.63 (0.67 / 0.53) | 7.6% | -12.5% | | |
| small-in-2010, n=7 | 100 | 1.07 (1.31 / 0.54) | 12.8% | -14.5% | 0.83 (1.08 / 0.29) | |
| small-in-2010, n=5 | 100 | 1.08 (1.40 / 0.40) | 13.8% | -16.2% | 0.86 | |
| core-70, n=7 | 70 | 0.77 (0.78 / 0.74) | 8.5% | -12.3% | 0.50 (0.53 / 0.44) | 1.09 / 0.55 / 0.74 |

Decomposition of the gross VIX-ramped book into market (EW universe held 09:30-16:00 with the
same ramp) and cross-sectional (book minus EW) parts, bp/day over all days:

| period | L7-wide gross | EW-300 | **xs-wide** (t) | L7-core gross | EW-70 | **xs-core** |
|---|---|---|---|---|---|---|
| 2010-15 | 7.7 | 1.1 | 6.6 (6.5) | 4.4 | 0.9 | 3.5 |
| 2016-21 | 7.8 | 1.1 | 6.7 (4.6) | 3.1 | 1.0 | 2.1 |
| 2022-26 | 5.7 | 2.1 | 3.6 (2.3) | 4.0 | 2.1 | 2.0 |
| full | 7.2 | 1.4 | 5.8 (7.4) | 3.8 | 1.3 | 2.5 |

Reading:
- Removing the 50 late entrants costs 0.17 Sharpe (1.36 -> 1.19) and 3 pts of CAGR; those names
  on their own are an unremarkable 0.67. So the pure "did not exist yet" bias is real but not the
  story.
- The bigger effect is *who was small in 2010*. Names that grew into the index show the classic
  survivorship signature: strong IS (1.31-1.40), weak OOS (0.40-0.54), while the names that were
  already large in 2010 are stable across the split (1.02 / 0.76). The pseudo point-in-time
  150-name universe is the number I would defend as low-bias: **0.93 vs 0.77 for the 70, with the
  same OOS (0.76 vs 0.74) and the same MaxDD (-12%)**. I.e. breadth per se is worth ~+0.15
  Sharpe; the rest of 1.36 - 0.77 is the illiquid/grew-into-the-index tail whose backtest return
  cannot be separated from survivorship with this data.
- The OOS period (2022+) is the least survivorship-affected (the snapshot is close to the actual
  top-300 then): cross-sectional alpha is 3.6 bp/day for wide vs 2.0 for core, t = 2.3. The
  breadth gain is real OOS but the wide book also has 40% more volatility, so OOS Sharpe is 0.88
  vs 0.74 at 2.5 bp and **0.66 vs 0.74 once wide pays 5 bp**.
- 2010-15 xs alpha of 6.6 bp/day (t 6.5) is where the wide result looks too good; this is the
  period where a 2026 snapshot is furthest from the true universe.

## 5. Cost sensitivity

| config | 2.5 bp | 5 bp | 7.5 bp | 10 bp | tiered* | breakeven bp/side |
|---|---|---|---|---|---|---|
| core-70 n=7 | 0.77 (OOS 0.74) | 0.50 (0.44) | ~0.2 | | | 9.7 |
| wide-300 n=7 | 1.36 (0.88) | 1.15 (0.66) | 0.93 (0.43) | 0.71 (0.20) | 1.27 (IS 1.50 / OOS 0.79), cost 3.6%/yr | 18.1 |
| wide-300 n=10 | 1.13 (0.73) | 0.90 (0.48) | | | 1.02 (0.62) | |
| wide-300 n=15 | 1.02 (0.64) | 0.78 (0.39) | | | 0.91 (0.53) | 13.0 |
| wide top-200 liq n=7 | 0.87 (0.62) | 0.65 (0.39) | | | | 12.2 |
| wide survivors-250 n=7 | 1.19 (0.70) | 0.96 (0.47) | | | | 15.6 |
| big-in-2010 150 n=7 | 0.93 (0.76) | 0.70 (0.50) | | | | |

\* tiered = per-ticker cost by full-sample median liquidity rank: 155 names at 2.5 bp, 114 at
5 bp, 31 at 7.5 bp. Cost drag scales with time-in-market only (2.49%/yr per 2.5 bp), so every
wide variant loses ~0.22 Sharpe per extra 2.5 bp of cost; the core sleeve loses 0.27 because its
gross edge is smaller. The wide sleeve's breakeven is 18 bp vs 9.7 bp - a much larger margin -
but that margin is bought with the illiquid names whose realistic cost is the uncertain one.
Reference: at today's volumes ($260M+/day at rank 250) 5 bp is conservative for MOO auction
fills; in 2012 the rank-250 name traded $12M/day and 5 bp is generous.

## 6. The VIX gate on 300 names

Ungated wide-300 L7 and L15 books, gross bp/day by VIX(d-1) bucket (net at 2.5 bp = gross - 5;
at 5 bp = gross - 10). Core-70 L7 for comparison; xs = book minus EW universe:

| VIX(d-1) | days | L7-wide gross (t) | net @2.5 | net @5 | L15-wide | EW-300 | xs-wide (t) | L7-core | xs-core | L7-wide IS | L7-wide OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| <= 14 | 1104 | 16.1 (6.1) | 11.1 | 6.1 | 11.8 | 1.3 | 14.8 (6.6) | 6.6 | 4.6 | 17.1 | 10.1 |
| 14-18 | 1364 | 10.4 (3.6) | 5.4 | 0.4 | 8.4 | 0.8 | 9.6 (4.1) | 5.9 | 5.2 | 17.4 | **-4.4** |
| 18-22 | 773 | 26.8 (6.0) | 21.8 | 16.8 | 21.4 | 8.5 | 18.3 (5.6) | 15.4 | 7.6 | 29.4 | 22.1 |
| 22-28 | 525 | 17.9 (2.7) | 12.9 | 7.9 | 13.4 | -2.1 | 20.0 (4.4) | 9.1 | 12.3 | 14.9 | 23.2 |
| 28-40 | 273 | 48.0 (4.1) | 43.0 | 38.0 | 33.0 | 9.6 | 38.4 (5.0) | 23.9 | 14.5 | 59.4 | 24.7 |
| > 40 | 51 | 132.9 (3.6) | 127.9 | 122.9 | 92.4 | 57.7 | 75.3 (2.5) | 78.4 | 16.6 | 124.4 | 232.9 |

Is the gate still needed? On the full sample, no: the wide book earns 10-16 bp/day gross below
VIX 18 against a 5-10 bp round trip (core: 6-7 bp, breakeven), and the ungated sleeve shows
Sharpe 1.92 / CAGR 45% (IS 2.55). **Out of sample, yes**: in the 14-18 bucket the fade is -4.4
bp/day since 2022 and in the <= 14 bucket 10 bp (= 0 net at 5 bp), so the ungated sleeve's OOS
is 0.70 (0.14 at 5 bp) vs 0.88 (0.66) gated. The calm-day edge is the part that decayed, exactly
as on 70 names, and the calm-day book is also where survivorship-flattered names and 12.6%/yr of
costs live. An IS-only tuner would pick floor 12 and span 1 (IS 2.08 / 1.84); I keep the live
gate (18 / 10) for the same reasons as round 1 - cost robustness, no cliff, and because the
bucket table (which uses the full sample) is what motivates it, so its OOS is not a blind test.
Note that the cliff (span 1) and floor 16 look better OOS too (1.25 / 0.99); I read that as the
2025-26 episodes rewarding faster full exposure, not as a reason to change a parameter that was
fixed before the OOS period.

## 7. Sensitivity (wide, n=7, one at a time; net Sharpe full (IS / OOS))

n: 3 -> 1.27 (1.61 / 0.50), 5 -> 1.35 (1.69 / 0.66), **7 -> 1.36 (1.60 / 0.88)**, 10 -> 1.13
(1.32 / 0.73), 15 -> 1.02 (1.20 / 0.64), 20 -> 0.94, 30 -> 0.76. vix_floor: 12 -> 1.70, 14 ->
1.58, 16 -> 1.47, **18 -> 1.36**, 20 -> 1.24, 22 -> 1.19 (OOS 0.99 / 1.02 / 0.99 / 0.88 / 0.70 /
0.62). vix_span: 1 -> 1.63, 5 -> 1.46, **10 -> 1.36**, 15 -> 1.37. weighting ivol 1.34.
skip_abs_gap 8% 1.16, 5% 1.01. top_liquidity 200 / 150 / 100 -> 0.87 / 0.76 / 0.64. universe:
survivors-250 1.19, big-in-2010 0.93. Everything but the liquidity screen and the universe is a
smooth plateau; those two are cliffs, and they are the same cliff (the illiquid tail).

## 8. Correlations (daily excess returns, 2010-06 ->; OOS in parentheses)

| | overnight | rev core | rev wide | SPY |
|---|---|---|---|---|
| overnight | 1 | 0.00 (-0.01) | **-0.02 (-0.01)** | 0.33 |
| rev core | | 1 | **0.78 (0.84)** | 0.50 (0.59) |
| rev wide n=7 | | | 1 | **0.37 (0.49)** |

The wide sleeve is the same bet as the core sleeve (0.78) with *less* market beta (corr with SPY
0.37 vs 0.50, beta 0.25 vs 0.27): more of its return is cross-sectional. Still zero correlation
with the overnight sleeve. It is a replacement for, not an addition to, the core sleeve.

## 9. Ensemble impact (growth profile: overnight QQQ->QLD / SMH / IWM at 1.0 with regime multiplier, reversal sleeve at the stated allocation, dd throttle, leverage map; replicated by hand and verified identical to `hf_ensemble_weights` on the core config; the overnight sleeve and regime multiplier are identical on the wide data)

| reversal sleeve in the ensemble | alloc | Sharpe (IS / OOS) | CAGR (OOS) | MaxDD (OOS) | cost/yr | corr with live |
|---|---|---|---|---|---|---|
| **core-70 n=7 (live growth)** | 0.50 | **1.31 (1.22 / 1.53)** | 11.5% (17.3%) | -12.2% (-9.6%) | 2.83% | 1 |
| **wide-300 n=7 @2.5 bp** | **0.50** | **1.75 (1.83 / 1.58)** | **16.5% (19.7%)** | **-12.4% (-9.9%)** | 2.83% | 0.90 |
| | 0.75 | 1.77 (1.90 / 1.49) | 20.9% (22.2%) | -14.2% (-14.2%) | 3.44% | 0.84 |
| | 1.00 | 1.74 (1.88 / 1.42) | 25.0% (24.7%) | -18.2% (-18.2%) | 4.03% | 0.79 |
| **wide-300 n=7 @5 bp** | **0.50** | **1.60 (1.69 / 1.42)** | **15.1% (18.0%)** | -12.4% (-10.6%) | 4.09% | 0.90 |
| | 0.75 | 1.59 (1.72 / 1.30) | 18.6% (19.6%) | -15.2% | 5.31% | |
| | 1.00 | 1.55 (1.69 / 1.22) | 22.0% (21.3%) | -19.2% | 6.47% | |
| wide-300 n=10 @2.5 / @5 | 0.50 | 1.58 (1.63 / 1.48) / 1.42 (1.47 / 1.32) | 14.6% / 13.1% | -12.3% / -12.4% | | |
| | 0.75 | 1.57 (1.66 / 1.36) / 1.38 (1.48 / 1.17) | 17.8% / 15.7% | -13.4% / -14.4% | | |
| | 1.00 | 1.54 (1.65 / 1.30) / 1.34 (1.46 / 1.09) | 21.3% / 18.3% | -15.9% / -16.9% | | |
| wide-300 n=15 @2.5 / @5 | 0.50 | 1.50 (1.53 / 1.44) / 1.34 (1.38 / 1.27) | 13.6% / 12.1% | -12.4% / -12.4% | | |
| | 0.75 | 1.48 (1.57 / 1.30) / 1.28 (1.38 / 1.09) | 16.3% / 14.2% | -12.4% / -13.4% | | |
| | 1.00 | 1.43 (1.55 / 1.16) / 1.21 (1.34 / 0.94) | 19.0% / 16.1% | -16.2% / -17.9% | | |
| wide top-200 liquidity n=7 | 0.50 / 0.75 / 1.00 | 1.40 (1.40 / 1.40) / 1.34 (1.40 / 1.23) / 1.30 (1.35 / 1.20) | 13.1 / 15.6 / 18.0% | -12.4 / -14.5 / -15.6% | | |
| wide survivors-250 n=7 @2.5 | 0.50 / 0.75 / 1.00 | 1.62 (1.71 / 1.46) / 1.62 (1.75 / 1.33) / 1.58 (1.73 / 1.21) | 15.1 / 18.6 / 21.9% | -12.0 / -13.3 / -17.7% | | |
| wide survivors-250 n=7 @5 | 0.50 / 0.75 / 1.00 | 1.47 (1.55 / 1.30) / 1.43 (1.57 / 1.13) / 1.37 (1.54 / 1.00) | 13.7 / 16.4 / 19.0% | -12.1 / -14.3 / -18.8% | | |

`report()` for growth with wide n=7 at 0.5 (2.5 bp): Sharpe 1.75, Sortino 2.44, MaxDD -12.4%,
Calmar 1.34, t 7.84, bootstrap CI [1.27, 2.22], corr SPY 0.46 / beta 0.22, time in market 41%,
cost 2.83%/yr; yearly returns 2010-26: 19.1 24.8 11.3 20.6 12.4 8.3 3.1 11.2 3.8 -0.3 60.9 16.3
| 10.2 10.9 36.3 23.5 13.2%; IS CAGR 15.3% / OOS 19.7%.

Reading: at 0.5 the full-sample ensemble gains +0.44 Sharpe (+0.29 at 5 bp) and +5 pts CAGR with
no change in MaxDD. **Out of sample the gain is +0.05 at 2.5 bp and -0.11 at 5 bp**: the wide
sleeve adds more return but also more volatility to the ensemble's 2022-26, and the calm-year
cross-sectional alpha that pays for 5 bp is thinner OOS. Allocation above 0.5 buys CAGR with
drawdown and a lower OOS Sharpe at every cost level - 0.5 is the right size for either universe,
as round 1 and the red team concluded.

## 10. Failure modes specific to the wide universe

1. **Open-print fills in the illiquid tail.** The gain lives in names ranked 150-300 by dollar
   volume. Their 09:30 auction print is thinner and the pre-market quote from which the live gap
   is computed is wider; the red team already flagged open-print ambiguity for the 70 mega-caps
   and it is worse here. This is the one thing paper trading *can* measure (realised fill vs
   09:30 print per liquidity bucket) and it should be measured before switching.
2. **Survivorship.** ~0.2 Sharpe of the 0.6 gain is attributable to names that did not exist or
   were small in 2010 (section 4); the credible breadth gain is ~+0.15. Expect the live wide sleeve
   to look more like the big-in-2010 row (0.9 / CAGR 11%) than the headline (1.36 / 18%).
3. **Concentration of P&L in crises.** 47% of the return is 2011 + 2020; MaxDD -19% (2022) vs
   -12%. It is a bigger liquidity-provision bet on the worst days, sized by the VIX ramp *into*
   the crash. The ensemble absorbs this at 0.5 (MaxDD unchanged) but not at 0.75-1.0.
4. **Single-name/earnings risk is larger**: the bottom-7 of 300 has bigger gaps (the |gap| > 8%
   filter now costs 0.2 Sharpe because those gaps revert on average, but a -6% earnings gap in a
   mid-cap that keeps falling is a -1.4% sleeve day at 1/7 weight).
5. **Operational**: 300 pre-market quotes at 09:28 instead of 70; the live path must handle
   names with missing opens (the engine zeroes weights where the price is NaN; the paper trader
   should do the same and *not* redistribute to the remaining names).
6. Turn-off rule unchanged: trailing 250-active-day mean of (book gross - EW-universe 09:30-16:00
   return) below +2 bp/day => the cross-sectional part is gone. For the wide book the 2022-26
   figure is 3.6 bp/day, so it has less headroom than its headline suggests.

## 11. Recommended params and recommendation

"Wide" configuration: `MarketData(HFConfig.wide())` with `ReversalParams()` **defaults**
(n = 7, mode long, eq, residual, zscore, beta 60, vol 20, vix_floor 18, vix_span 10, no
liquidity screen, no outlier filter). Nothing in the rule changes except the universe. The new
optional parameters (`universe`, `top_liquidity`, `liq_window`, `frac`) are research handles and
should stay at None in production; the only one with a live use is `universe=<tuple>` if the
orchestrator wants a fixed, hand-vetted list (e.g. the 150 big-in-2010 names, section 4).

**Recommendation: do not switch the live sleeve to the wide universe now; shadow it.**
- For: same rule, 0.77 -> 1.36 (1.15 at 5 bp), 14 of 17 years better, breakeven 18 vs 9.7 bp,
  the direction is what the literature predicts, and the ensemble goes 1.31 -> 1.75 (1.60 at 5 bp)
  with unchanged MaxDD at the same 0.5 allocation.
- Against: the whole gain is the illiquid tail (top-150 liquidity screen = no gain), which is
  where (i) costs are least certain, (ii) open-print fills are least reliable, (iii) survivorship is
  worst (grew-into-the-index names: IS 1.3 / OOS 0.5; pseudo point-in-time universe 0.93 with OOS
  0.76 = core). OOS at honest costs the sleeve is 0.66 vs 0.74 and the ensemble 1.42 vs 1.53,
  and outside 2010-11/2020 it is 0.66 vs 0.69. The brief's criteria are cost-robust and
  OOS-credible; on those two the wide sleeve is a wash, not an improvement, and it adds
  operational risk to a system that has been live for two days.
- Do: compute the wide n=7 book every morning alongside the live one (it is 0.2 s), log its
  hypothetical fills against the 09:30 print by liquidity bucket, and its gross return minus
  EW-300. Switch to **wide n=7 at allocation 0.5** (not 0.75 or 1.0: no Sharpe, more drawdown) if
  after ~60 active days (a) median slippage vs the open print in rank-150+ names is < 3 bp and
  (b) the live xs edge is >= 2 bp/day. If the orchestrator wants the switch today regardless,
  use n=7 / 0.5 and budget for the 5 bp numbers (standalone 1.15, ensemble 1.60 full / 1.42 OOS,
  CAGR ~15%), not the 2.5 bp ones. A middle path with most of the credible gain and none of the
  tail risk does not exist: `top_liquidity=200` gives 0.87 / OOS 0.62.

## 12. Insights for other sleeves

1. **Breadth in cross-sectional sorts pays only through the tail you add.** Going 70 -> 300 names
   changed nothing for the 150 most liquid names' contribution; the entire gain was the 150 less
   liquid ones. Any sleeve proposing a wider universe should show the top-K-liquidity version -
   if that is flat, the "breadth" gain is a liquidity (and survivorship, and cost) gain in disguise.
2. **Survivorship test that works without point-in-time constituents:** split today's survivors
   by their dollar volume at the *start* of the sample. Names that were already large are a
   plausible 2010 universe; names that were small and are large now carry the bias, and they show
   it as a large IS/OOS gap (1.3 -> 0.5 here). Use `ReversalParams(universe=...)`-style filters.
3. **The reversal edge scales with illiquidity, not with the number of names**: gross fade per
   pick 22 bp (rank 1-150) -> 49-67 bp (rank 200+), while Sharpe *falls* in n at every universe
   size. For a $1k account this is tempting (no impact), but it is exactly the segment where the
   09:30 print is not a fill.
4. **The VIX gate's calm-day edge decayed everywhere.** VIX 14-18 days: +17 bp/day gross IS,
   -4 bp OOS, on 300 names; same sign as on 70. Whatever a stock sleeve does at VIX < 18, it
   should be sized for zero edge there.
5. **Outlier filters are universe-dependent**: skipping |gap| > 8% did nothing on 70 mega-caps
   and costs 0.2 Sharpe on 300 names, where large gaps in mid-caps *do* revert. Do not port a
   filter across universes without re-testing.
6. The short leg died OOS on 300 names too (ls 2.40 -> 0.79; 0.35 at 5 bp). Universe breadth
   does not resurrect a dead leg.

## 13. Implementation note

`quantbot/strategies/hf_reversal.py`: four optional fields added to `ReversalParams`
(`universe: tuple | None`, `top_liquidity: int | None`, `liq_window: int = 60`,
`frac: float | None`), all defaulting to legacy behaviour; `_gap_signal` restricts the stock
list and/or masks the gap to the top-K names by trailing `liq_window`-day median dollar volume
(`Close*Volume`, shifted one day so it is known at 09:30) before the universe-average gap is
formed; `reversal_weights` accepts a per-day n when `frac` is set. Defaults unchanged.
**Verification:** `reversal_weights(MarketData(HFConfig()), ReversalParams())` saved before the
edit and recomputed after: same index (8384 rows) and columns (70), 0 differing cells, max abs
diff 0.0, `DataFrame.equals` True - bit-identical. Also checked: the core sleeve computed on the
wide `MarketData` with `universe=tuple(HF_STOCKS)` reproduces the core daily returns exactly,
and the hand-built ensemble equals `hf_ensemble_weights` on the core config.
Scratch scripts: `/tmp/qb_wide/` (`exp1_breadth.py` ... `exp9_dropyears.py`, `common.py`).
