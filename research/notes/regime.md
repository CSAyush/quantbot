# Risk / regime layer (`quantbot/strategies/hf_regime.py`)

Timeline: daily dates (tz-naive, `= md.close.index`). The multiplier stamped on date d
uses only data through the 16:00 close of d and applies to trades at the 16:00 close of d
and the 09:30 open of d+1. Tuned on data < 2022-01-01. **`n_trials = 190`** (rounded to
200 in the `report()` calls).

Final rule (`RegimeParams()` defaults):

```
mult[d] = clip( trend_gate * vol_scale , 0.1 , 1.0 )
  trend_gate = 1.0 if SPY close > 200d MA else 0.5
  vol_scale  = (0.16 / realised_vol_20d(QQQ close-to-close))^2      # Moreira-Muir 1/variance
```

Mean multiplier 0.75 (IS 0.79, OOS 0.63); = 1.0 on 49% of days, < 0.5 on 25% of days.
Yearly mean: 2020 0.48, 2022 0.17, 2025 0.70 (0.04 for all of April 2025).

Sharpe conventions used below. The brief's baselines (SPY 0.86, QQQ-overnight 0.68) are
**raw** = engine cash yield 4%, rf 0. While this work was in progress `engine.summary`
switched to reporting Sharpe **excess of the 4% cash yield**, which is what `report()`
now prints. Tables say which one they use; the last table shows all three.

## 1. Hypothesis and literature

Index returns per unit of variance are not constant: variance is highly persistent and
forecastable at 1-4 week horizons while the conditional mean is not, so exposure
proportional to 1/realised variance raises Sharpe and cuts drawdowns (Moreira & Muir
2017 JF, "Volatility-Managed Portfolios"; the gain is concentrated in *reducing*
exposure after vol spikes, not in levering calm markets). A slow trend filter (close vs
200d MA; Faber 2007, Moskowitz-Ooi-Pedersen 2012 time-series momentum) removes the
worst left tail and, for overnight holds, the overnight premium is ~zero below the 200d
MA (see overnight.md). VIX term structure (VIX/VIX3M > 1 = backwardation; Simon &
Campasano 2014) and VIX level relative to its own history are the other candidate
stress flags. The drawdown throttle is the standard "de-risk after losses" rule and was
tested as a generic helper on the strategy's own equity.

## 2. Everything tested

All tests apply the candidate multiplier to two risk-on baselines on `md.px_daily`
with default costs: **QQQ overnight** (long 16:00 -> 09:30, weight = mult[d]) and **SPY
buy & hold** (weight = mult[d], rebalanced each 16:00). Raw Sharpe (rf 0, cash 4%).
Split at 2022-01-01. NaN in ^VIX3M/^VIX9D (pre-2011, 32 missing days, and after
2026-07-17 in the cache) counts as neutral = risk-on.

### 2a. Standalone components (38 trials)

| Component / variant | QQQon Sharpe (IS / OOS) | QQQon CAGR | QQQon MaxDD | SPYbh Sharpe (IS / OOS) | SPYbh CAGR | SPYbh MaxDD |
|---|---|---|---|---|---|---|
| **baseline** | 0.68 (0.81 / 0.39) | 8.1% | -30% | 0.86 (0.91 / 0.75) | 14.1% | -34% |
| **1. VIX term structure** | | | | | | |
| VIX/VIX3M < 1.00 else flat | 0.80 (0.99 / 0.47) | 7.8% | -30% | 0.92 (1.04 / 0.67) | 12.1% | -29% |
| VIX/VIX3M < 0.95 | 0.76 (0.95 / 0.42) | 6.5% | -30% | 0.88 (0.96 / 0.70) | 10.1% | -27% |
| VIX/VIX3M < 1.05 | 0.87 (1.15 / 0.37) | 9.3% | -30% | 0.97 (1.10 / 0.70) | 14.1% | -25% |
| VIX/VIX3M < 1 else half | 0.77 (0.95 / 0.44) | 8.0% | -30% | 0.94 (1.03 / 0.73) | 13.3% | -27% |
| 3d-mean ratio < 1 | 0.86 (1.09 / 0.49) | 8.6% | -30% | 0.92 (1.03 / 0.70) | 12.3% | -26% |
| VIX9D/VIX < 1 | 0.72 (0.99 / 0.22) | 6.2% | -26% | 0.83 (0.90 / 0.67) | 9.4% | -19% |
| both in contango | 0.83 (1.04 / 0.43) | 6.8% | -24% | 0.89 (0.95 / 0.75) | 9.7% | -22% |
| linear 1+5(1-ratio), clip [0,1] | 0.85 (1.11 / 0.40) | 9.1% | -30% | 0.95 (1.06 / 0.70) | 13.7% | -25% |
| **2. Vol-managed (MM), c/RV^2 with c = 1/mean_IS(1/RV^2), cap 1** | | | | | | |
| RV = SPY c2c 20d | 1.08 (0.99 / 1.27) | 6.6% | -11% | 1.04 (1.06 / 1.00) | 8.6% | -8% |
| RV = QQQ c2c 20d | 1.13 (1.00 / 1.52) | 6.7% | -11% | 1.08 (1.04 / 1.24) | 9.0% | -10% |
| RV = QQQ overnight-only 20d | 0.98 (0.92 / 1.18) | 6.1% | -15% | 1.01 (0.99 / 1.12) | 8.5% | -13% |
| RV = SPY c2c 60d | 0.90 (0.89 / 0.93) | 6.7% | -12% | 0.93 (0.94 / 0.90) | 9.0% | -13% |
| RV = QQQ c2c 60d | 0.96 (0.90 / 1.12) | 7.0% | -12% | 0.98 (0.96 / 1.08) | 9.6% | -14% |
| RV = QQQ o/n 60d | 0.91 (0.89 / 0.94) | 6.3% | -15% | 0.97 (0.97 / 1.00) | 9.2% | -14% |
| target-vol 12% / RV_SPY20 (power 1) | 0.93 (0.98 / 0.82) | 8.0% | -16% | 1.02 (1.07 / 0.90) | 11.7% | -14% |
| target-vol 15% | 0.85 (0.95 / 0.68) | 8.2% | -21% | 0.99 (1.05 / 0.84) | 12.6% | -18% |
| target-vol 18% | 0.83 (0.95 / 0.58) | 8.5% | -24% | 0.96 (1.03 / 0.81) | 13.2% | -20% |
| c / VIX^2 (implied instead of realised) | 0.88 (0.97 / 0.73) | 6.4% | -16% | 0.96 (1.01 / 0.85) | 9.1% | -13% |
| 15 / VIX, 18 / VIX | 0.83, 0.77 | 7.0%, 7.3% | -21%, -26% | 0.95, 0.92 | 10.6%, 11.5% | -17%, -20% |
| the same with cap 1.5 (6 rows, sanity, no lev cost) | all 0.05-0.10 *lower* Sharpe than cap 1 | | | | | |
| **3. Trend** | | | | | | |
| SPY > 200d MA else flat | 0.99 (1.08 / 0.77) | 9.1% | -20% | 0.93 (0.95 / 0.88) | 11.2% | -17% |
| SPY > 200d MA else half | 0.87 (0.99 / 0.59) | 8.7% | -25% | 0.96 (0.99 / 0.88) | 12.9% | -26% |
| 50d MA > 200d MA | 0.74 (0.72 / 0.78) | 7.8% | -28% | 0.75 (0.73 / 0.82) | 10.4% | -34% |
| QQQ > own 200d MA | 1.00 (0.96 / 1.10) | 9.6% | -20% | 0.86 (0.80 / 1.10) | 10.8% | -23% |
| SPY > 100d MA | 0.88 (0.92 / 0.80) | 7.8% | -21% | 0.89 (0.86 / 0.96) | 10.2% | -16% |
| **4. VIX level** | | | | | | |
| VIX < 25 / < 30 / < 35 else flat | 0.73 / 0.68 / 0.69 | 6.5-7.3% | -26 to -35% | 0.91 / 0.80 / 0.70 | 9.8-10.8% | -21 to -31% |
| VIX <= 20d MA + 1 sd (spike filter) | 0.67 (1.00 / **0.04**) | 6.2% | -33% | 0.87 (0.97 / 0.63) | 11.1% | -20% |
| VIX <= 20d MA + 2 sd | 0.59 (0.77 / 0.19) | 6.3% | -34% | 0.78 (0.83 / 0.65) | 11.4% | -43% |
| VIX 1y percentile < 0.9 | 0.73 (0.94 / 0.33) | 7.0% | -34% | 0.87 (1.04 / 0.49) | 11.2% | -31% |
| VIX < own 10d MA (vol falling) | 0.99 (1.26 / 0.44) | 7.7% | -25% | **1.10 (1.09 / 1.14)** | 12.0% | -15% |
| **5. Drawdown throttle on QQQon's own equity (returns through d-1)** | | | | | | |
| dd > 10% -> x0.5 | 0.71 (0.83 / 0.41) | 7.4% | -23% | | | |
| dd > 15% -> x0.5 | 0.70 (0.83 / 0.39) | 7.6% | -24% | | | |
| dd > 20% -> x0.5 | 0.73 (0.86 / 0.42) | 8.3% | -26% | | | |
| dd > 10% -> flat | 0.68 (0.79 / 0.35) | 6.5% | -18% | | | |

Verdicts:
- **Vol-managed 1/RV^2 (20d) is the strongest single component** on both baselines
  and the only one that improves *OOS* materially (QQQon OOS 0.39 -> 1.27-1.52). QQQ's
  realised vol beats SPY's, and close-to-close beats overnight-only RV (the overnight
  series is too noisy at 20d). Power 2 (variance) beats power 1 (target-vol). 60d
  windows are too slow. Implied (VIX) is a worse forecaster than 20d realised.
- **200d trend gate is the second robust component** (QQQon 0.68 -> 0.99, MaxDD -30 ->
  -20%; SPY MaxDD -34 -> -17%). 50/200 crossover is useless here (too slow), 100d is a
  slightly worse 200d. Full-flat below the MA beats half for overnight; for B&H half is
  as good (the below-MA SPY return is positive but volatile).
- **VIX term structure has modest standalone value** (QQQon 0.68 -> 0.80, SPY 0.86 ->
  0.92; both cut MaxDD by ~5 pp) that is almost entirely subsumed by the RV rule once
  combined (2b). Backwardation days are 8% of the sample; on them the next-night QQQ
  overnight Sharpe is 0.55 vs 1.21 in contango, but next-day SPY c2c is *higher*
  (12.9 bp vs 5.2 bp) - it is a vol flag, not a return flag. VIX9D/VIX hurts OOS.
- **VIX level rules do not work.** Absolute thresholds (25/30/35) are neutral-to-negative
  and the "spike" rule (VIX > 20d MA + k sd) is *destructive* OOS (QQQon 0.04): by the
  time VIX has spiked, the next nights are the high-premium ones. Consistent with
  overnight.md's finding that VIX buckets are unstable conditioners. The one VIX rule
  with value, "VIX below its 10d MA" (vol falling), is strong on SPY B&H (1.10, OOS
  1.14) but flips OOS on overnight (0.44); it is ~50% on/off and turnover-heavy, so it
  is left as an insight, not a rule.
- **Drawdown throttle is marginal standalone** (+0.03-0.05 Sharpe, MaxDD -30 -> -23%)
  and adds *nothing* on top of the multiplier (1.087 -> 1.074). Keep it in the ensemble
  as a cheap circuit-breaker, not as a source of edge.

### 2b. Combinations, with leverage caps implemented via 2x/3x ETFs (72 trials)

T0 = trend gate flat below MA, T.5 = half below MA; mm<tk><ref> = (ref%/RV_20d(tk))^2;
tv = target-vol (power 1); TS.5 = x0.5 in backwardation. Raw Sharpe full (IS / OOS),
then CAGR, MaxDD. Cap > 1 uses QLD/TQQQ (SSO/UPRO) at 2 bp/side.

| Rule | cap | QQQon | CAGR | MaxDD | SPYbh | CAGR | MaxDD | mean mult |
|---|---|---|---|---|---|---|---|---|
| trend only (T0) | 1.0 | 0.99 (1.10 / 0.77) | 9.2% | -20% | 0.95 (0.98 / 0.88) | 11.4% | -17% | 0.86 |
| mmqqq16 | 1.0 | 1.06 (1.00 / 1.21) | 8.0% | -13% | 1.10 (1.09 / 1.11) | 11.3% | -14% | 0.77 |
| T0 * mmqqq16 | 1.0 | 1.11 (1.05 / 1.24) | 7.8% | -10% | 1.05 (1.05 / 1.06) | 10.1% | -11% | 0.72 |
| **T.5 * mmqqq16** | **1.0** | **1.10 (1.04 / 1.25)** | **7.9%** | **-12%** | **1.09 (1.08 / 1.11)** | **10.7%** | **-11%** | **0.75** |
| T.5 * mmqqq14 | 1.0 | 1.14 (1.05 / 1.41) | 7.3% | -11% | 1.10 (1.08 / 1.17) | 9.7% | -10% | 0.67 |
| T.5 * mmqqq18 | 1.0 | 1.05 (1.03 / 1.12) | 8.3% | -12% | 1.08 (1.08 / 1.07) | 11.5% | -12% | 0.80 |
| T.5 * mmspy16 | 1.0 | 0.98 (1.03 / 0.87) | 8.4% | -16% | 1.04 (1.10 / 0.89) | 11.6% | -13% | 0.84 |
| T0 * tvqqq16 (power 1) | 1.0 | 1.08 (1.09 / 1.05) | 8.4% | -11% | 1.03 (1.04 / 1.00) | 10.8% | -12% | 0.78 |
| T0 * mmqqq16 * TS.5 | 1.0 | 1.09 (1.01 / 1.28) | 7.5% | -10% | 1.05 (1.06 / 1.03) | 9.9% | -10% | 0.71 |
| mmqqq16 * TS.5 | 1.0 | 1.08 (1.02 / 1.23) | 7.8% | -11% | 1.12 (1.13 / 1.07) | 11.0% | -10% | 0.75 |
| T0 * TS.5 | 1.0 | 0.99 (1.07 / 0.83) | 8.7% | -20% | 0.96 (1.00 / 0.87) | 10.9% | -17% | 0.84 |
| T.5 * mmqqq16 | 1.5 | 0.96 (0.86 / 1.24) | 8.4% | -16% | 0.96 (0.95 / 0.99) | 11.7% | -15% | 0.94 |
| T.5 * mmqqq16 | 2.0 | 0.88 (0.75 / 1.28) | 8.6% | -19% | 0.89 (0.87 / 0.96) | 12.1% | -18% | 1.07 |
| T.5 * mmspy16 | 1.5 | 0.89 (0.92 / 0.85) | 9.9% | -19% | 0.96 (1.03 / 0.77) | 14.0% | -16% | 1.15 |
| T.5 * mmspy18 | 2.0 | 0.82 (0.85 / 0.76) | 11.6% | -25% | 0.90 (0.99 / 0.69) | 16.9% | -21% | 1.51 |
| (all other cap 1.5 / 2.0 rows) | | every one below its cap-1 twin by 0.1-0.3 | | | | | | |

Choice: **T.5 * mmqqq16, cap 1.0** - at or near the top on *both* baselines in *both*
periods, with only two rules. The term-structure factor moves things by +-0.02 and is
left in the code as an option (`use_term_structure=False`). vol_ref 14% would score
higher but means 33% average cash; 16% is the middle of a smooth plateau (see 4).

### 2c. Leverage: fidelity and drag of the 2x/3x ETFs (6 trials + analytics)

(i) Fidelity, regression of fund return on 1x return, 2010-2026 (OOS = 2022+):

| pair | leg | alpha (bp/period) | beta | R^2 | resid sd (bp) |
|---|---|---|---|---|---|
| QQQ/QLD | overnight | -1.19 | 1.991 | 0.996 | 10 |
| QQQ/QLD | intraday | +0.11 | 1.998 | 0.998 | 10 |
| QQQ/QLD | overnight OOS | -2.49 | 2.007 | 0.999 | 5.5 |
| QQQ/TQQQ | overnight | -0.86 | 2.954 | 0.994 | 18 |
| QQQ/TQQQ | overnight OOS | -3.74 | 2.996 | 0.999 | 8.4 |
| SPY/SSO | overnight | -0.70 | 2.008 | 0.994 | 10.5 |
| SPY/UPRO | overnight | -1.15 | 3.005 | 0.994 | 16 |

The funds are an almost exact L-x of the 1x on overnight holds (beta 1.99-3.00, R^2 >
0.994), **but the whole day's financing + expense lands in the overnight session**
(intraday alpha ~0, overnight alpha -1.2 bp/night for QLD, -2.5 bp since rates rose,
-3.7 bp for TQQQ). An overnight-only holder pays 24h of fund financing for 17.5h of
exposure. Daily tracking vs `L*r - (L-1)*4%/252`: QLD +1.1%/yr better before 2022 (the
fund financed at ~0.3%), -1.7%/yr worse since 2022 (~5.5% + 0.95% ER); TQQQ +2.5% / -3.1%.

(ii) Multi-day holds, fund vs a 2x/3x margin buy-and-hold financed at 4%, mean difference
per hold (bp) and 5th percentile:

| N days | QLD mean (5th pct) | TQQQ mean (5th pct) | SSO mean (5th pct) |
|---|---|---|---|
| 1 | +0.4 (-12) | +0.9 (-19) | +0.4 (-10) |
| 5 | +1.1 (-21) | +2.5 (-53) | +1.4 (-15) |
| 21 | +2.8 (-70) | +6.6 (-188) | +4.1 (-44) |
| 63 | +1.4 (-216) | +0.6 (-592) | +3.5 (-135) |
| 252 | +89 (-829) | +158 (-2637) | +33 (-986) |

"Volatility decay" is not an expected-return drag: relative to a constant-leverage
margin position the mean difference is ~0 (slightly positive because the fund's
financing was cheaper than 4% for 12 of 16 years); it is a *path* effect, (L^2-L)/2 *
sigma^2 = 4.3%/yr (QLD) / 12.8%/yr (TQQQ) of log-return dispersion vs an unrebalanced
position, visible in the left tail. Engine backtests confirm: buy & hold "1.5x QQQ" as
0.5 QQQ + 0.5 QLD gives Sharpe 0.91, CAGR 26.1%, MaxDD -51% vs a synthetic 1.5x at 4%
borrow 0.89 / 25.6% / -51%. For multi-day the ETFs are a faithful and (pre-2022) cheaper
substitute for margin.

(iii) Overnight-only, engine, every night (no filter): 1x QQQ Sharpe 0.68 / CAGR 8.1%;
1.5x via 0.5 QQQ + 0.5 QLD 0.59 / 9.7% / MaxDD -45%; 2x via QLD 0.53 / 10.8% / -58%;
3x via TQQQ 0.72 / 21.7% / -71% (synthetic frictionless 1.5x / 2x: 0.96 / 0.92). At the
brief's 2 bp/side, an overnight round trip in QLD costs 4 bp + 1.2-2.5 bp of
financing = 5-6.5 bp/night per unit of QLD against ~5 bp/night gross overnight premium
per unit of QQQ exposure (2.5 per unit of QLD-exposure): the marginal exposure barely
breaks even.

**Leverage cost sensitivity of the chosen multiplier** (raw Sharpe full / IS / OOS, CAGR):

| max_mult | lev-ETF cost/side | QQQ overnight x mult | SPY B&H x mult |
|---|---|---|---|
| 1.0 | any | 1.10 / 1.04 / 1.24, 7.9% | 1.09 / 1.09 / 1.12, 10.8% |
| 1.5 | 2.0 bp | 0.96 / 0.86 / 1.24, 8.4% | 0.96 / 0.95 / 0.99, 11.7% |
| 1.5 | 1.0 bp | 1.07 / 0.99 / 1.30, 9.5% | 0.96 / 0.96 / 0.99, 11.7% |
| 1.5 | 0.5 bp | 1.13 / 1.06 / 1.32, 10.0% | 0.96 / 0.96 / 0.99, 11.7% |
| 1.5 | 0.0 bp | 1.18 / 1.12 / 1.35, 10.6% | 0.96 / 0.96 / 1.00, 11.8% |
| 2.0 | 2.0 bp | 0.88 / 0.75 / 1.28, 8.6% | 0.89 / 0.87 / 0.96, 12.1% |
| 2.0 | 0.5 bp | 1.12 / 1.04 / 1.39, 11.4% | 0.89 / 0.88 / 0.97, 12.3% |

Ex-cash (cash yield 0) the picture is the same: QQQon x mult 0.88 at cap 1 vs 0.78 at
cap 1.5 vs 0.72 at cap 2. **Recommendation: `max_mult = 1.0`.** The MM literature's gain
comes from de-levering after vol spikes; levering calm markets adds exposure with a
below-average Sharpe, and on multi-day holds the fund's financing (now ~5.5%) plus the
0.95% ER makes >1x strictly worse than 1x. The only case for >1x is *overnight-only*
with cheap fills: at <= 0.5 bp/side on QLD (plausible for MOC/MOO auction fills), 1.5x is
Sharpe-neutral (+0.03) and adds ~2 pp CAGR for 4 pp more MaxDD. Treat 1.5x as the hard
ceiling for overnight-only, only after paper-trading confirms fill costs, and 1.0x
(1.25x at most) for anything held through the day. Never 3x: TQQQ's -3.7 bp/night
financing alone eats most of the overnight premium.

### 2d. Applied to the real overnight sleeve and the regime-timing sanity sleeve (14 trials)

`hf_overnight.py` appeared during this work (QQQ+SMH+IWM, 200d gate + 5-night reversal,
Sharpe 1.62 / OOS 1.91 raw). Raw Sharpe full (IS / OOS), CAGR, MaxDD:

| Variant | Sharpe | CAGR | MaxDD |
|---|---|---|---|
| overnight sleeve as published | 1.62 (1.49 / 1.91) | 10.1% | -15.1% |
| overnight x mult | 1.84 (1.70 / 2.14) | 8.6% | -9.2% |
| overnight x vol-scale only (sleeve has its own 200d gate) | 1.85 (1.69 / 2.19) | 8.7% | -9.2% |
| overnight x mult with term structure on | 1.81 (1.68 / 2.09) | 8.2% | -9.3% |
| QQQon x mult, trend flat below MA (T0) | 1.08 (1.03 / 1.20) | 7.6% | -10.6% |
| QQQon x mult with term structure on | 1.07 (1.00 / 1.26) | 7.5% | -10.7% |
| QQQon x mult x dd-throttle(10%, 0.5) | 1.07 (1.01 / 1.24) | 7.7% | -11.5% |
| mult floor 0 / 0.1 / 0.2 / 0.3 (QQQon) | 1.090 / 1.087 / 1.049 / 0.996 | | |
| **timing sleeve: QQQ x mult, rest cash** | **1.14 (1.18 / 1.03)** | **14.4%** | **-12.0%** |
| timing sleeve: QQQ x mult, rest TLT | 0.96 (1.21 / 0.42) | 13.6% | -40% |
| timing sleeve: SPY x mult, rest cash | 1.07 (1.05 / 1.12) | 10.6% | -11.2% |
| timing: QQQ, binary 200d trend only, rest cash | 1.03 (1.14 / 0.78) | 16.1% | -22.7% |
| QQQ buy & hold (reference) | 0.94 (1.07 / 0.67) | 18.8% | -35% |

The regime-timing sleeve confirms the multiplier has value as a standalone position:
QQQ sized by the multiplier beats QQQ buy & hold on Sharpe in both periods (1.14 vs
0.94; OOS 1.03 vs 0.67) with a third of the drawdown (-12% vs -35%) and 0.75 average
exposure. TLT as the defensive asset was a disaster OOS (2022 bond bear: -40% MaxDD);
use cash. A floor of 0.1 on the multiplier costs nothing (1.090 -> 1.087) and keeps a
live footprint; adopted.

## 3. Final scorecard

### 3a. Effect of the multiplier under the three Sharpe conventions

Full (IS / OOS). Raw = cash 4%, rf 0 (the brief's baselines); ex-cash = cash 0, rf 0;
excess = cash 4%, rf 4% (what `report()` now prints).

| Sleeve | convention | baseline | x multiplier | CAGR | MaxDD |
|---|---|---|---|---|---|
| **QQQ overnight** | raw | 0.69 (0.82 / 0.39) | **1.10 (1.04 / 1.24)** | 8.2% -> 7.9% | -30% -> -11.5% |
| | ex-cash | 0.63 (0.76 / 0.33) | 0.88 (0.84 / 0.97) | 7.4% -> 6.2% | -31% -> -13% |
| | excess | 0.37 (0.49 / 0.10) | 0.54 (0.48 / 0.69) | | |
| | gross ex-cash (no costs) | 1.02 (1.17 / 0.70) | 1.40 (1.40 / 1.40) | | |
| **SPY buy & hold** | raw | 0.87 (0.92 / 0.75) | 1.09 (1.09 / 1.12) | 14.4% -> 10.8% | -34% -> -11% |
| | ex-cash | 0.87 (0.92 / 0.75) | 0.99 (1.00 / 0.95) | 14.4% -> 9.7% | -34% -> -12% |
| | excess | 0.64 (0.69 / 0.52) | 0.69 (0.69 / 0.67) | | |
| **QQQ buy & hold** (= timing sleeve) | raw | 0.95 (1.09 / 0.67) | 1.17 (1.23 / 1.03) | 19.2% -> 14.8% | -35% -> -12% |
| | ex-cash | 0.95 (1.09 / 0.67) | 1.09 (1.16 / 0.91) | 19.2% -> 13.6% | -35% -> -14% |
| | excess | 0.76 (0.88 / 0.50) | 0.85 (0.91 / 0.71) | | |
| **overnight sleeve** | raw | 1.62 (1.49 / 1.91) | 1.84 (1.70 / 2.14) | 10.1% -> 8.6% | -15% -> -9% |
| | ex-cash | 1.11 (0.94 / 1.46) | 1.13 (0.96 / 1.48) | 6.8% -> 5.2% | -17% -> -10% |
| | excess | 0.96 (0.77 / 1.34) | 0.96 (0.77 / 1.36) | | |

Honest reading: on *unconditioned* risk-on exposure the multiplier adds +0.1 to +0.25
ex-cash Sharpe (more OOS: +0.2 to +0.6, because 2022 and April 2025 are exactly the
regimes it removes) and cuts MaxDD by ~60% everywhere. On the *already conditioned*
overnight sleeve (200d gate + reversal) it adds no ex-cash Sharpe - it is a drawdown and
tail controller (MaxDD -15% -> -9%, kurtosis 23 -> 19, worst day -5.2% -> -2.8%) that
costs 1.5 pp of CAGR. The raw-Sharpe gains (+0.2 to +0.4) overstate it because idle cash
earns 4%.

### 3b. `report()` output - QQQ overnight baseline x multiplier (raw Sharpe 1.09 / IS 1.03 / OOS 1.24)

```
QQQon x mult       | CAGR   7.80% | Vol  7.14% | Sharpe  0.53 | Sortino  0.67 | MaxDD -11.51% | Calmar  0.68 | t  4.43 | PF 1.21 | exp L/S 0.37/0.00 | cost/yr 3.76% | days 4191
  (Sharpe/Sortino are excess of the 4.0% cash yield)
  time in market 50.0% | turnover/day 1.49 | trades/day 2.00 | skew -0.54 | kurt 4.2 | best +2.44% | worst -3.57%
  Sharpe 95% bootstrap CI: [0.09, 0.96]
  Deflated Sharpe: P(SR > null max of 200 trials = 0.68) = 0.271
  vs benchmark: corr 0.46 | beta 0.19

  Yearly (excess Sharpe):
       return      vol   sharpe   max_dd  days
2010    0.099    0.075    0.761   -0.056   252
2011   -0.014    0.069   -0.752   -0.061   252
2012    0.077    0.076    0.493   -0.046   250
2013    0.145    0.074    1.324   -0.034   252
2014    0.110    0.061    1.081   -0.034   252
2015    0.059    0.072    0.278   -0.060   252
2016   -0.032    0.068   -1.040   -0.093   252
2017    0.155    0.055    1.920   -0.025   251
2018    0.035    0.063   -0.057   -0.039   251
2019    0.063    0.078    0.306   -0.102   252
2020    0.124    0.077    1.040   -0.068   253
2021    0.067    0.077    0.358   -0.044   252
2022   -0.025    0.033   -1.969   -0.038   251
2023    0.078    0.075    0.508   -0.046   250
2024    0.209    0.085    1.807   -0.028   252
2025    0.172    0.078    1.579   -0.063   250
2026    0.011    0.085   -0.234   -0.079   167

  In-sample / out-of-sample split at 2022-01-01:
                            days     cagr      vol   sharpe  sortino  max_drawdown   calmar
QQQon x mult in-sample      3021    0.073    0.071    0.460    0.576        -0.115    0.631
QQQon x mult out-of-sample  1170    0.092    0.073    0.694    0.933        -0.079    1.163
QQQon x mult full           4191    0.078    0.071    0.527    0.673        -0.115    0.677
```

For reference the unconditioned QQQ overnight baseline in the same convention is excess
Sharpe 0.37 (IS 0.49 / OOS 0.10), MaxDD -30%. 2022 is the one losing year (-2.5%, with
17% average exposure) - the multiplier turned a -29% year for the baseline into -2.5%.

### 3c. `report()` output - overnight sleeve x multiplier (raw 1.84 / IS 1.70 / OOS 2.14)

```
overnight x mult   | CAGR   8.61% | Vol  4.54% | Sharpe  0.96 | Sortino  1.22 | MaxDD  -9.16% | Calmar  0.94 | t  7.33 | PF 1.64 | exp L/S 0.12/0.00 | cost/yr 1.22% | days 3992
  (Sharpe/Sortino are excess of the 4.0% cash yield)
  time in market 22.0% | turnover/day 0.49 | trades/day 1.71 | skew 0.00 | kurt 19.3 | best +2.93% | worst -2.82%
  Sharpe 95% bootstrap CI: [0.46, 1.47]
  Deflated Sharpe: P(SR > null max of 200 trials = 0.69) = 0.853
  vs benchmark: corr 0.28 | beta 0.07
  Yearly excess Sharpe: 2011 -0.4, 2012 0.9, 2013 2.6, 2014 1.4, 2015 0.0, 2016 -0.3, 2017 2.3, 2018 0.1,
                        2019 -0.6, 2020 1.3, 2021 1.9, 2022 -0.9, 2023 0.4, 2024 3.2, 2025 2.2, 2026 0.7
  In-sample 0.767 (CAGR 7.4%, MaxDD -9.2%) | out-of-sample 1.361 (CAGR 11.5%, MaxDD -7.7%)
```

### 3d. `report()` output - regime-timing sleeve, QQQ x mult / cash (raw 1.14 / IS 1.18 / OOS 1.03)

```
timing QQQ/cash    | CAGR  14.40% | Vol 12.47% | Sharpe  0.82 | Sortino  1.04 | MaxDD -11.97% | Calmar  1.20 | t  4.66 | PF 1.22 | exp L/S 0.75/0.00 | cost/yr 0.06% | days 4191
  (Sharpe/Sortino are excess of the 4.0% cash yield)
  time in market 100.0% | turnover/day 0.02 | trades/day 0.49 | skew -0.63 | kurt 3.0 | best +3.18% | worst -4.96%
  Sharpe 95% bootstrap CI: [0.36, 1.30]
  Deflated Sharpe: P(SR > null max of 200 trials = 0.68) = 0.716
  vs benchmark: corr 0.71 | beta 0.52
  Yearly excess Sharpe: 2010 0.9, 2011 -0.3, 2012 0.7, 2013 2.2, 2014 0.7, 2015 0.1, 2016 0.2, 2017 2.4, 2018 0.0,
                        2019 1.4, 2020 1.3, 2021 0.9, 2022 -2.0, 2023 1.8, 2024 1.1, 2025 0.6, 2026 0.5
  In-sample 0.864 (CAGR 15.0%, MaxDD -11.1%) | out-of-sample 0.708 (CAGR 12.8%, MaxDD -12.0%)
```

vs QQQ buy & hold (excess): 0.76 (0.88 / 0.50), CAGR 19.2%, MaxDD -35%; vs SPY buy &
hold (excess) 0.64, MaxDD -34%. 2022 is the failure year (-8.2%): the 200d gate only
halves exposure, and the vol scale reacts to realised vol, so the slow grind of H1 2022
was only partially avoided (QQQ -33% that year).

## 4. Sensitivity (one-at-a-time around the chosen params; raw Sharpe full / IS / OOS)

QQQon = QQQ overnight x mult; SPYbh = SPY buy & hold x mult.

| param | value | QQQon | QQQon CAGR | SPYbh | SPYbh CAGR | mean mult |
|---|---|---|---|---|---|---|
| vol_ref | 0.12 | 1.16 / 1.02 / 1.62 | 6.4% | 1.08 / 1.03 / 1.29 | 8.3% | 0.58 |
| | 0.14 | 1.12 / 1.03 / 1.39 | 7.2% | 1.08 / 1.05 / 1.17 | 9.6% | 0.67 |
| | **0.16** | **1.09 / 1.03 / 1.24** | 7.8% | **1.07 / 1.05 / 1.12** | 10.6% | 0.75 |
| | 0.18 | 1.04 / 1.01 / 1.12 | 8.2% | 1.05 / 1.05 / 1.08 | 11.3% | 0.80 |
| | 0.20 | 1.03 / 1.02 / 1.06 | 8.6% | 1.06 / 1.06 / 1.06 | 12.0% | 0.84 |
| | 0.22 | 1.03 / 1.05 / 1.00 | 9.1% | 1.06 / 1.07 / 1.04 | 12.5% | 0.86 |
| vol_window | 10 | 1.07 / 1.02 / 1.17 | 7.7% | 1.04 / 1.05 / 1.03 | 10.3% | 0.75 |
| | 15 | 1.07 / 1.05 / 1.12 | 7.6% | 1.07 / 1.08 / 1.04 | 10.5% | 0.75 |
| | **20** | **1.09 / 1.03 / 1.24** | 7.8% | **1.07 / 1.05 / 1.12** | 10.6% | 0.75 |
| | 30 | 1.10 / 1.03 / 1.26 | 8.0% | 1.08 / 1.05 / 1.17 | 10.8% | 0.75 |
| | 42 | 1.05 / 1.00 / 1.16 | 7.8% | 1.04 / 1.03 / 1.11 | 10.5% | 0.75 |
| | 63 | 1.03 / 1.01 / 1.09 | 7.8% | 0.99 / 0.99 / 1.00 | 10.0% | 0.74 |
| vol_power | 0 (trend only) | 0.87 / 0.99 / 0.59 | 8.7% | 0.96 / 0.99 / 0.88 | 12.9% | 0.93 |
| | 1 (target-vol) | 1.03 / 1.05 / 0.98 | 8.3% | 1.05 / 1.06 / 1.04 | 11.5% | 0.82 |
| | 1.5 | 1.07 / 1.04 / 1.13 | 8.1% | 1.06 / 1.06 / 1.09 | 11.0% | 0.78 |
| | **2** | **1.09 / 1.03 / 1.24** | 7.8% | **1.07 / 1.05 / 1.12** | 10.6% | 0.75 |
| | 3 | 1.09 / 0.98 / 1.36 | 7.3% | 1.05 / 1.03 / 1.15 | 9.9% | 0.70 |
| trend_ma | 100 | 1.07 / 0.97 / 1.32 | 7.5% | 1.06 / 1.01 / 1.21 | 10.1% | 0.73 |
| | 150 | 1.09 / 1.01 / 1.30 | 7.8% | 1.05 / 1.02 / 1.18 | 10.3% | 0.74 |
| | **200** | **1.09 / 1.03 / 1.24** | 7.8% | **1.07 / 1.05 / 1.12** | 10.6% | 0.75 |
| | 250 | 1.08 / 1.00 / 1.26 | 7.8% | 1.04 / 1.02 / 1.08 | 10.3% | 0.75 |
| trend_off_mult | 0.0 | 1.08 / 1.03 / 1.20 | 7.6% | 1.05 / 1.04 / 1.09 | 10.3% | 0.74 |
| | 0.25 | 1.08 / 1.03 / 1.21 | 7.7% | 1.05 / 1.04 / 1.10 | 10.3% | 0.74 |
| | **0.5** | **1.09 / 1.03 / 1.24** | 7.8% | **1.07 / 1.05 / 1.12** | 10.6% | 0.75 |
| | 0.75 | 1.08 / 1.01 / 1.23 | 7.9% | 1.07 / 1.06 / 1.12 | 10.8% | 0.76 |
| | 1.0 (no trend) | 1.05 / 0.99 / 1.21 | 7.9% | 1.08 / 1.06 / 1.11 | 11.1% | 0.77 |
| vol_ticker | **QQQ** | **1.09 / 1.03 / 1.24** | 7.8% | **1.07 / 1.05 / 1.12** | 10.6% | 0.75 |
| | SPY | 0.97 / 1.02 / 0.87 | 8.3% | 1.02 / 1.07 / 0.89 | 11.4% | 0.84 |
| max_mult | **1.0** | **1.09 / 1.03 / 1.24** | 7.8% | **1.07 / 1.05 / 1.12** | 10.6% | 0.75 |
| | 1.25 | 1.02 / 0.94 / 1.22 | 8.2% | 1.01 / 1.00 / 1.04 | 11.3% | 0.86 |
| | 1.5 | 0.95 / 0.85 / 1.24 | 8.3% | 0.94 / 0.93 / 0.99 | 11.5% | 0.94 |
| | 2.0 | 0.87 / 0.74 / 1.27 | 8.5% | 0.87 / 0.86 / 0.96 | 12.0% | 1.07 |

Everything degrades smoothly. `vol_ref` is a monotone Sharpe-vs-CAGR dial (lower = more
cash); `vol_window` is flat from 10 to 30 days and fades by 63; `vol_power` 1.5-3 is a
plateau and 0 (trend only) is clearly worse; `trend_ma` 100-250 is flat;
`trend_off_mult` barely matters once the vol scale is on (0-0.5 best for overnight,
0.75-1 for B&H, 0.5 chosen as the compromise). The one non-trivial choice is
`vol_ticker`: QQQ's realised vol beats SPY's OOS by 0.2-0.4 because 2022 was a
QQQ-led bear; QQQ is what the risk-on sleeves hold, so it is the right vol to scale by.
The multiplier floor (0 / 0.1 / 0.2 / 0.3 -> 1.090 / 1.087 / 1.049 / 0.996) is flat up to
0.1 and 0.1 is adopted so the sleeves never go fully dark.

## 5. Correlations (daily returns, 2010-2026)

|  | QQQon x mult | overnight x mult | timing QQQ/cash | SPY | QQQon base |
|---|---|---|---|---|---|
| QQQon x mult | 1.00 | 0.65 | 0.58 | 0.45 | 0.78 |
| overnight x mult | 0.65 | 1.00 | 0.39 | 0.28 | 0.46 |
| timing QQQ/cash | 0.58 | 0.39 | 1.00 | 0.70 | 0.45 |
| SPY | 0.45 | 0.28 | 0.70 | 1.00 | 0.62 |

The multiplier *lowers* correlation with SPY (QQQ overnight 0.62 -> 0.45; beta 0.19)
because it is smallest exactly when the market is most volatile. The timing sleeve is a
0.7-correlated, beta-0.5 version of the index - it is a *replacement* for holding
QQQ/SPY outright, not a diversifier; correlation to the overnight sleeve is 0.39.

## 6. Failure modes / when to turn this off

- **It sells after the drop and is slow to come back.** 1/RV^2 with a 20d window stays
  low for ~4 weeks after a spike: the multiplier was 0.04 for all of April 2025 and 0.17
  on average in 2022, so the sleeves missed the 9 April 2025 +12% day and the H2-2022
  rallies. That is the price of the ~60% drawdown reduction; sharp V-shaped recoveries
  (Dec 2018, Apr 2020, Apr 2025) are where it costs the most CAGR. `vol_window` 10-15
  recovers faster at a small Sharpe cost.
- **Slow grinding bears are only half-avoided.** H1 2022 had moderate realised vol and
  SPY hovered around its 200d MA: the timing sleeve still lost 8% that year.
- **The trend gate is redundant with sleeves that have their own** (overnight.md's
  200d gate). Set `trend_off_mult=1.0` (vol-only) for such sleeves; identical results.
- **Sleeves that like volatility must not be scaled.** Reversal-type edges are
  strongest when VIX > 25 (see 8); apply the multiplier to risk-on (long-beta) sleeves
  only and use `vol_regime` to *tilt toward* mean-reversion sleeves in high vol.
- **Leverage > 1x makes it worse** at 2 bp/side, and the fund financing is now ~5.5%
  + 0.95% ER. Only revisit if live fills on QLD are <= 0.5 bp.
- **Cash-yield accounting.** With `cash_yield_annual=0.04` the multiplied strategies earn
  ~1%/yr of riskless carry on the ~25% they hold in cash; in 2010-21 T-bills paid ~0.5%.
  Both the raw and the excess-of-4% Sharpe conventions are shown above; the ex-cash
  column is the fair one for 2010-21.
- **Data:** `^VIX3M` is missing after 2026-07-17 in the cache; the term-structure gate
  treats NaN as neutral and is off by default. The multiplier itself needs only QQQ
  and SPY closes, so it cannot break on aux data.
- **Shared-code note (not a bug):** `engine.summary` now passes `rf_annual =
  cash_yield_annual` so `report()` and `res.stats["sharpe"]` are excess of the cash
  yield, while `metrics.sharpe(x)` called directly is still rf 0 and the brief's
  baselines are rf 0. Anyone comparing numbers across notes should check which
  convention a table uses.

## 7. Recommended params and ensemble use

`RegimeParams()` defaults: `trend_ticker="SPY", trend_ma=200, trend_off_mult=0.5,
vol_ticker="QQQ", vol_window=20, vol_ref=0.16, vol_power=2.0, use_term_structure=False,
max_mult=1.0, min_mult=0.1, vix_low=15, vix_high=25, dd_level=0.10, dd_mult=0.5,
timing_asset="QQQ", timing_defensive=None`.

- Apply `regime_multiplier(md)` to the risk-on sleeves (overnight, any long-beta ETF
  sleeve, regime_timing). Expect a 25% average haircut on their exposure, ~60% lower
  MaxDD, a -1 to -1.5 pp CAGR cost and +0.0 to +0.25 ex-cash Sharpe depending on how
  conditioned the sleeve already is. Do **not** apply it to reversal / intraday-momentum
  sleeves.
- `leverage_map(weights, mult=None, max_cash=1.0)` is the cash-account implementation
  step (QQQ/SPY exposure > 1 -> QLD/TQQQ, SSO/UPRO; pro-rata scale-down if several
  sleeves overflow 1.0 of cash). With `max_mult=1.0` it only ever triggers when sleeves
  overlap; keep `EnsembleParams.max_exposure` <= 1.5 and prefer 1.0-1.25 unless
  paper-trading shows sub-1 bp leveraged-ETF fills.
- `drawdown_throttle(daily_returns, 0.10, 0.5)` at the ensemble level: harmless, small
  MaxDD benefit, no Sharpe. Keep as a circuit-breaker.
- **Regime-timing sleeve allocation: 0-25%.** It is a beta-0.5 index replacement
  (excess Sharpe 0.82 vs 0.64-0.76 for SPY/QQQ B&H, MaxDD -12% vs -35%). It is what a
  cash account should hold *instead of* an unconditioned index position; it adds
  little diversification to the overnight sleeve (corr 0.39) and 0.7 to SPY, so size it
  by how much index beta the ensemble wants, not by its Sharpe. Suggested 20% if the
  ensemble wants daytime beta; 0% if it wants to stay market-neutral intraday.

## 8. Insights for other sleeves

1. **Realised variance is the regime signal; VIX buckets are not.** Scaling by
   1/RV_20d^2 of QQQ improved every long-beta baseline in-sample *and* OOS (2022, Apr
   2025), while every VIX-level rule (> 25/30/35, > 20d MA + k sd, 1y percentile) was
   neutral to destructive OOS. Anyone conditioning on "vol" should use 20-30d realised
   variance of the traded asset, power 2, not the VIX level.
2. **Mean reversion is a high-vol phenomenon.** Next-day SPY 1-day reversal (short
   yesterday's sign) by `vol_regime`: VIX > 25 Sharpe 1.26 (IS 1.38, OOS 0.93, +16.5
   bp/day); VIX 15-25 -0.16; VIX < 15 -0.21 (OOS -1.7). A reversal sleeve should be
   gated *on* by `vol_regime == "high"` (13% of days) and the ensemble should tilt
   toward it, not away, when the risk-on multiplier is low. Gap-continuation
   ("intraday momentum" after an overnight gap) is the mirror image: -1.4 Sharpe in
   high vol OOS, ~0 otherwise.
3. **The overnight premium survives high vol but not downtrends.** Next-night QQQ
   overnight return by regime: VIX > 25 7.8 bp (Sharpe 0.83), normal 5.0 bp (1.09), low
   4.3 bp (1.52); above the 200d MA 5.7 bp (1.43) vs below 1.9 bp (0.21). So for
   overnight sleeves the 200d gate does the work and the vol scale is a tail control;
   for sleeves that hold through the day the vol scale does the work.
4. **Leveraged ETFs charge their whole day's financing overnight.** QLD's overnight
   alpha vs 2x QQQ is -1.2 bp/night (-2.5 since 2022), intraday ~0. Any overnight-only
   sleeve using QLD/TQQQ pays ~24h of financing (5.5% + 0.95% ER now) for 17.5h of
   exposure plus 2 bp/side. Use them behind a filter that cuts nights held (as
   overnight.md found) and never for exposure above 1.5x; for multi-day holds they are
   a faithful, pre-2022-cheaper substitute for margin at 4%, but at today's rates
   they cost ~1.7%/yr (2x) and ~3.1%/yr (3x) more than 4% margin would.
5. **Volatility decay is a path effect, not a mean drag.** vs a 2x margin buy-and-hold
   at 4%, QLD's mean N-day excess is +0.4 to +2.8 bp for N = 1-21 with a 5th percentile
   of -12 to -70 bp; the (L^2-L)/2 sigma^2 term (4.3%/yr for QLD) shows up as dispersion
   and in the left tail, not in the average. Don't "correct" leveraged-ETF backtests for
   decay; the daily price series already contains it.
6. **VIX term structure is a vol proxy, not a return signal.** Backwardation (8% of
   days) has higher *next-day* SPY c2c mean (12.9 bp vs 5.2) with much higher vol;
   conditioning on VIX/VIX3M < 1 gave +0.1 Sharpe standalone that vanishes once realised
   variance is in the rule. Sleeves already using RV scaling gain nothing from it.
7. **TLT is not a safe haven on this horizon.** Rotating into TLT when risk-off turned a
   -12% MaxDD into -40% (2022); its overnight premium is negative (overnight.md).
   Risk-off means cash.
8. **Cash carry inflates raw Sharpe of anything that sits in cash.** 25% average cash
   at 4% = ~+0.15 raw Sharpe for the multiplied sleeves and ~+0.5 for the overnight
   sleeve; compare sleeves with `cash_yield_annual=0` or on the excess-Sharpe convention.
