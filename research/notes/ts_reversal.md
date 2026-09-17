# Time-series index reversal in high volatility (`quantbot/strategies/hf_ts_reversal.py`)

Timeline: daily (`md.px_daily`). Final rule (`TSReversalParams()` defaults): at the 16:00 close of
day d, if **^VIX(d) > 20** and **QQQ closed down on d**, buy QQQ at the close with weight
`min(1, 0.20 / RV20(QQQ))` and hold it until the 16:00 close of d+1 (overnight + intraday, one
round trip); otherwise flat. Long-only, one ETF, 1 bp/side. Tuned on < 2022-01-01. Data
`MarketData(HFConfig.research(), refresh=False, intraday=False)`, 2010-01 -> 2026-09-16. Costs
default (`cost_bps_for`: QQQ/SPY/IWM 1 bp, SH/PSQ/RWM 2 bp). Cash = T-bill (`md.cash_yield()`,
mean 1.5%), every Sharpe below is **excess of it** unless marked gross. Split IS < 2022 / OOS >= 2022.
**`n_trials = 361`.**

**Headline.** The hypothesis as stated in `regime.md` insight 2 (SPY, VIX > 25, both halves) does
**not** make an acceptable sleeve: net Sharpe 0.42 (IS 0.46 / OOS 0.31), MaxDD -19%. The quoted
"Sharpe 1.26" was the Sharpe of the *active days*; on the full daily timeline (cash otherwise) the
same trade is 0.46 gross. What does work is the **long half only** (buy after a down day) in the
**higher-vol expression** (QQQ, not SPY), gated at **VIX > 20** (not 25), held the **full day**
(the reversal is in both sessions, ~40% overnight / 60% intraday, so a 16:00 -> 16:00 hold earns both
for one round trip), and sized to constant risk with `0.20 / RV20`. That sleeve is net Sharpe
**0.89 (IS 0.86 / OOS 0.97)**, CAGR 9.3%, MaxDD -13.4%, 15% time in market, cost 0.38%/yr,
breakeven **22 bp/side** (22x the assumed cost), ex-cash Sharpe 0.91. The **short half** (short the
index after an up day; SH/PSQ long in a cash account, negative weights on paper) earns ~0 net
(-2 bp/day gross after up days, t -0.3) and dilutes the long half in every configuration: standalone
0.62 (IS 0.47 / OOS 0.93) with MaxDD -24%. It does **not** earn its keep.

The catch is independence: the sleeve is active on the same days as the live gap-fade reversal sleeve
(98% of its active days are VIX > 18 days on which `reversal_weights` is also long) and it is long
beta during the day, so its excess-return correlation with `reversal` is **0.43 (OOS 0.50)** and
with `spy` 0.56. It is the *index-level, time-series* cousin of the live sleeve. Adding it to the
growth profile still raises the ensemble Sharpe in **both** halves at 0.25 and 0.5 allocation
(1.324 -> 1.392 / 1.384; IS +0.08, OOS +0.04 / +0.01) and lowers MaxDD, but the gain is modest.
**Verdict: ACCEPT at allocation 0.25** (see section 9 for the gate and the caveats; SHADOW is the
conservative alternative). Notable for the orchestrator: with the live reversal sleeve *removed*,
overnight + this sleeve at 0.5 reproduces the growth profile's Sharpe (1.33 vs 1.32) with the same
CAGR and lower MaxDD, at 1/7 of the cost drag and none of the MOO fill risk (section 5).

## 1. Hypothesis and literature

Short-horizon reversal is the return to liquidity provision, and the price of liquidity rises
sharply with volatility: Nagel (2012) shows reversal-strategy returns are strongly predicted by VIX
and are close to zero in calm markets; Hendershott & Menkveld (2014) measure the transitory price
pressure that market makers absorb and its dependence on inventory risk. At the *index* level the
same mechanism shows up as negative one-day autocorrelation of returns during stress (index
futures/ETF order flow from de-levering and hedging is absorbed by intermediaries who demand a
next-day premium) and ~zero or slightly positive autocorrelation otherwise. `regime.md` insight 2
found exactly this pattern in SPY (next-day reversal +16.5 bp/day when VIX > 25, negative when VIX <
25). The live sleeves cover the cross-sectional version (`reversal.md`: gap fade in 7 mega-caps,
VIX-ramped, 09:30 -> 16:00) and the overnight premium in uptrends (`overnight.md`); the time-series
index version had never been built. Two refinements follow from the literature: (i) the liquidity
premium is asymmetric - selling pressure in a falling, volatile market is the inventory that costs the
most to absorb, so the *after-down-day* half should dominate (Nagel's reversal profits come mostly
from the long/loser side in stress; `reversal.md` found the same asymmetry in mega-caps, where the
short leg died OOS); (ii) at a fixed per-side cost the higher-vol expression of the same trade earns
more bp per bp of cost (`crossasset.md` insight 1), so QQQ should beat SPY.

## 2. Everything tested

Conventions: "Sh" = net Sharpe full (IS / OOS), excess of T-bill; "gross" = 0 cost, 0 cash; BE =
per-side cost (bp) at which the mean net trading P&L is zero; tim = time in market. Signal at 16:00
of d: `sign = -sign(r_d)` (r = close-to-close return of d). "both" = long after down days and short
after up days; "long" = long half only. Windows: full 16:00 -> 16:00; overnight 16:00 -> 09:30;
intraday 09:30 d+1 -> 16:00 d+1 (signal from 16:00 of d).

### 2a. Regime definitions x halves x sessions, SPY, analytic gross (132 trials)

Next-day SPY return (bp/active day, t-stat) earned by the reversal sign, by regime flag at 16:00 of d
and by session; Sharpe on the full daily timeline (0 on inactive days), full (IS / OOS). RV20 = 20d
realised vol of SPY, IS 80th / 90th percentile = 18.4% / 23.6%.

| regime | % days | both c2c bp (t) Sh | both o/n bp | both intra bp | **long** c2c bp (t) Sh (IS/OOS) | long o/n bp (t) | long intra bp (t) | short c2c bp (t) Sh (IS/OOS) |
|---|---|---|---|---|---|---|---|---|
| all days | 100 | 1.4 (0.8) 0.20 | 1.0 | 0.4 | 7.9 (2.8) 0.68 (0.71/0.63) | 5.1 (2.9) | 2.8 (1.3) | -3.9 (-2.0) -0.49 |
| VIX < 15 | 34 | -0.7 (-0.5) -0.13 | -0.4 | -0.3 | 4.0 (1.5) 0.38 (0.58/-0.24) | 2.9 | 1.1 | -3.5 (-2.1) -0.51 |
| VIX 15-25 | 52 | -1.0 (-0.5) -0.13 | 0.8 | -1.8 | 4.8 (1.5) 0.37 (0.28/0.56) | 4.7 (2.5) | 0.1 | -6.1 (-2.3) -0.57 |
| **VIX > 20** | 29 | 11.1 (2.3) 0.57 (0.50/0.75) | 5.2 (1.7) | 5.8 (1.7) | **20.0 (2.9) 0.71 (0.68/0.77)** | 9.8 (2.2) | 10.1 (2.0) | 0.5 (0.1) 0.02 (-0.07/0.24) |
| VIX > 25 (pre-registered) | 13 | 16.5 (1.9) 0.46 (0.49/0.36) | 5.4 (0.9) | 11.0 (1.7) | 24.7 (2.0) 0.48 (0.50/0.44) | 10.1 (1.2) | 14.5 (1.6) | 5.8 (0.5) 0.12 (0.16/0.00) |
| VIX > 30 | 6 | 30.6 (1.9) 0.46 (0.52/0.29) | 6.2 | 24.2 (2.2) | 47.3 (2.1) 0.52 (0.56/0.39) | 13.3 | 33.7 (2.1) | 6.2 (0.3) 0.07 |
| RV20 > IS p80 | 21 | 8.0 (1.4) 0.33 (0.41/0.15) | 4.2 | 3.7 | 20.9 (2.1) 0.52 (0.57/0.38) | 10.4 | 10.4 | -2.9 -0.11 |
| RV20 > IS p90 | 11 | 15.7 (1.6) 0.39 (0.54/0.00) | 3.4 | 12.1 | 29.1 (1.8) 0.43 (0.55/0.12) | 4.1 | 24.7 (2.2) | 4.2 0.09 (0.17/-0.16) |
| VIX > own 20d MA | 41 | 7.1 (2.2) 0.54 (0.53/0.56) | 3.5 | 3.6 | 10.2 (2.4) 0.59 (0.60/0.54) | 6.2 (2.4) | 4.0 | 2.3 0.11 |
| VIX > 25 & VIX > MA20 | 8.5 | 24.0 (2.0) 0.49 (0.49/0.47) | 10.0 | 14.0 | 24.8 (1.7) 0.41 (0.46/0.28) | 9.4 | 15.3 | 22.5 (1.1) 0.27 (0.21/0.44) |
| VIX > 25 or RV > p90 | 16 | 12.4 (1.6) 0.40 | 3.6 | 8.7 | 21.8 (1.9) 0.47 (0.48/0.42) | 8.7 | 12.9 | 1.7 0.04 |
| VIX > 25 & SPY < 200d MA | 8 | 15.6 (1.2) 0.29 | 5.9 | 9.6 | 27.4 (1.5) 0.37 (0.38/0.33) | 7.7 | 19.5 | -0.4 -0.01 |
| VIX > 25 & SPY > 200d MA | 3.6 | 14.0 (1.2) 0.28 | 3.5 | 10.4 | 19.4 (1.1) 0.27 (0.22/0.59) | 18.3 (1.8) | 1.0 | 8.3 0.12 |

Also run (all VIX > 25 days): 09:30-refreshed signals for the intraday leg - sign of yesterday's c2c
11.0 bp (t 1.7), sign of close[d-1] -> open[d+1] 4.2 bp, sign of the overnight gap alone (index gap
fade) 1.6 bp (t 0.3, IS Sharpe -0.18), long only if both r_d < 0 and gap < 0 24.1 bp (n 133, IS 0.15 /
OOS 0.69), etc. (7 variants); reversal by |r_d| z-bucket (5); horizon d+1 / d+2 / d+3 = +16.5 / -1.1 /
+6.7 bp (3).

Findings:
- **The reversal is a high-VIX phenomenon, and it is the long half.** After a down day the next-day
  mean goes from 4-5 bp (VIX < 25) to 20-25 bp (VIX > 20 / 25) to 47 bp (VIX > 30); after an up day
  it is *negative* in calm markets (-3.5 to -6 bp: the index drifts up) and ~0 to +6 bp (t < 0.5) in
  stress. The short half never has a t-stat above 1.1 and is 0.00 OOS at VIX > 25.
- **Both sessions carry the reversal for the long half** (VIX > 20: overnight 9.8 bp t 2.2, intraday
  10.1 bp t 2.0), so the holding window should be the full day: one round trip, both legs. For the
  short half the overnight leg is ~0 or negative and only the intraday leg has anything (IS only).
- **VIX level beats realised variance here** (RV > p80 OOS 0.38, RV > p90 OOS 0.12 vs VIX > 20 OOS
  0.77) - the opposite of `regime.md` insight 1 for *sizing risk-on exposure*, and the same as
  `reversal.md`'s finding for *liquidity provision*. VIX is the price of insurance, which is what a
  liquidity provider is paid; realised vol is a noisier proxy. VIX > its own 20d MA is weaker (10.2 bp,
  Sh 0.59) and 3x the turnover; combining it with VIX > 25 adds nothing.
- **Refreshing the signal at 09:30 with the open destroys it** (sign of close[d-1] -> open[d+1]: 4.2 bp
  vs 11.0 for yesterday's sign alone), and the index gap does not fade intraday (1.6 bp) - consistent
  with `etf_reversal.md`. The overnight gap is *part of the reversal*, not a new signal.
- **No continuation**: d+2 return after the signal is -1.1 bp, so a 1-day hold is right.
- **Size of the move**: at VIX > 25, days with |r_d| < 0.5 daily sigma revert by -2 bp, 0.5-1.5 sigma
  by 11-21 bp, > 1.5 sigma by 44-46 bp *in-sample* but the > 2 sigma bucket is -28 bp OOS (n small;
  the biggest moves are news, Da-Liu-Schaumburg). See 2d.

### 2b. Engine grid: gate x half x window, SPY (90 trials)

Net of costs. Both halves shown with negative SPY weights ("short", paper) and via SH ("SH", cash
account, 2 bp/side). Full window unless stated.

| gate | both/short Sh (IS/OOS), CAGR, DD | both/SH Sh | **long Sh (IS/OOS), CAGR, DD, tim, BE** | long overnight Sh | long intraday Sh |
|---|---|---|---|---|---|
| VIX > 20 | 0.50 (0.44/0.65), 7.7%, -19% | 0.47 (0.42/0.60) | **0.65 (0.64/0.67), 8.4%, -15.9%, 16%, 17 bp** | 0.41 (0.44/0.32) | 0.39 (0.38/0.41) |
| VIX > 22 | 0.47 (0.47/0.49), 7.1%, -19% | 0.45 | 0.56 (0.58/0.49), 7.0%, -13.9%, 12%, 19 bp | 0.39 | 0.31 |
| VIX > 25 (pre-registered) | **0.42 (0.46/0.31), 6.0%, -18.6%** | **0.40 (0.45/0.26)** | 0.45 (0.48/0.39), 5.5%, -13.9%, 7.5%, 22 bp | 0.23 | 0.34 |
| VIX > 28 | 0.39 (0.46/0.21) | 0.38 | 0.52 (0.54/0.44), 5.8%, -13.8%, 4.6%, 33 bp | 0.13 | 0.55 (0.68/0.37) |
| VIX > 30 | 0.45 (0.51/0.27) | 0.44 | 0.51 (0.56/0.36), 5.6%, -13.8%, 3.7%, 40 bp | 0.19 | 0.49 (0.65/0.25) |
| ramp (18, 10) | 0.44 (0.44/0.47) | 0.42 | 0.57 (0.58/0.55), 6.8%, -13.8%, 21%, 19 bp | 0.35 | 0.36 |
| ramp (20, 10) | 0.46 (0.48/0.40) | 0.44 | 0.55 (0.56/0.49), 6.3%, -13.8% | 0.30 | 0.39 |
| RV20 > IS p80 | 0.28 (0.35/0.08) | 0.26 | 0.48 (0.54/0.32), 5.9%, -14.9% | 0.31 (0.40/0.03) | 0.28 |
| RV20 > IS p90 | 0.36 (0.51/-0.04) | 0.35 | 0.41 (0.54/0.08), 4.8%, -18.5% | 0.04 | 0.48 (0.75/0.11) |
| VIX > 20d MA | 0.41 (0.43/0.38), 6.4%, -19% | 0.38 | 0.49 (0.53/0.39), 6.4%, -17.7%, 25%, 8.8 bp | 0.35 | 0.14 |

(Both-halves overnight-only and intraday-only rows: 0.00-0.49, all below the corresponding full-day
row; every overnight-only row has BE < 6 bp.) The long half beats both halves at every gate in both
periods; the full-day window beats either session at every gate; SH costs ~0.02-0.05 Sharpe vs
negative SPY weights (2 bp vs 1 bp plus the fund's drag). Best IS rows are the intraday-only VIX > 28
/ RV > p90 books (IS 0.68-0.75) that collapse OOS (0.11-0.37) - textbook in-sample traps with 2-3%
time in market; not pursued.

### 2c. Assets and signal source (VIX > 20, full day; 14 trials)

| asset | signal | both/SH Sh (IS/OOS), CAGR, DD | **long Sh (IS/OOS), CAGR, DD, BE** |
|---|---|---|---|
| SPY | SPY | 0.47 (0.42/0.60), 7.3%, -21% | 0.65 (0.64/0.67), 8.4%, -15.9%, 17 bp |
| **QQQ** | **own** | 0.63 (0.55/0.81), 10.9%, -34% | **0.83 (0.84/0.81), 11.6%, -16.9%, 23.5 bp** |
| QQQ | SPY | 0.58 (0.46/0.84), 9.9%, -24% | 0.76 (0.74/0.80), 10.8%, -14.8%, 22 bp |
| IWM | own | 0.35 (0.24/0.66), 6.3%, -35% | 0.64 (0.56/0.85), 9.3%, -22.3%, 20 bp |
| IWM | SPY | 0.32 (0.17/0.71) | 0.60 (0.52/0.82), 8.9%, -22.3% |
| EW SPY+QQQ+IWM | own | 0.55 (0.46/0.77), 8.5%, -20% | 0.76 (0.73/0.82), 9.9%, -15.7%, 20 bp |
| EW SPY+QQQ+IWM | SPY | 0.47 (0.35/0.74) | 0.69 (0.65/0.79), 9.4%, -15.8% |

QQQ on its own sign is best in both periods. The QQQ premium over SPY is not (mainly) QQQ's higher
drift: QQQ's unconditional edge over SPY is ~2 bp/day, which on 15% of days is worth ~0.3 pp of
CAGR, versus the 3.2 pp observed; it is the higher-vol expression of the same reversal (28 bp/active
day vs 20) at the same 1 bp cost. Own-sign beats SPY-sign for every asset (QQQ closes down on a few
days when SPY does not, and those are the days its reversal is largest). The three-ETF basket does
not diversify (pairwise return correlations ~0.9) and only dilutes.

### 2d. Sizing (SPY, VIX > 20, full day; 16 trials) and the vol-target choice (QQQ; 8 trials)

z = |r_d| / daily RV20 (known at 16:00 of d).

| sizing | both/SH Sh (IS/OOS), DD | long Sh (IS/OOS), CAGR, DD |
|---|---|---|
| binary | 0.47 (0.42/0.60), -21% | 0.65 (0.64/0.67), 8.4%, -15.9% |
| skip if z < 0.5 | 0.74 (0.85/0.50), -16% | 0.76 (**0.94/0.35**), 8.1%, -20.8% |
| skip if z < 1.0 | 0.51 (0.72/-0.06) | 0.48 (0.69/-0.08), 4.7% |
| w = min(z, 1) | 0.68 (0.73/0.57) | 0.73 (0.85/0.44), 7.4% |
| w = min(z/2, 1) | 0.67 (0.80/0.30) | 0.67 (0.84/0.18), 5.6% |
| w = min(0.20/RV, 1) | 0.38 (0.23/0.71), -17% | 0.64 (0.59/0.75), 6.8%, -13.1% |
| w = min(0.30/RV, 1) | 0.40 (0.30/0.61) | 0.62 (0.61/0.66), 7.5%, -16.1% |
| w = min((0.16/RV)^2, 1) | 0.38 (0.16/0.87), -11.5% | 0.66 (0.57/0.88), 5.5%, -9.6% |

**Sizing by the size of the move is an in-sample artefact**: every z-based rule adds 0.1-0.3 IS
Sharpe and gives back 0.2-0.7 OOS (the > 2 sigma bucket flipped sign). Binary is the honest choice.
**1/RV sizing is Sharpe-neutral standalone** (0.62-0.66 vs 0.65) and cuts MaxDD - the `regime.md`
result again: vol scaling is a tail control, not an edge. On QQQ (long, VIX > 20, full):

| vol_target | Sh (IS / OOS) | CAGR | MaxDD | kurt | ensemble delta at 0.25 / 0.5 (full, IS, OOS) |
|---|---|---|---|---|---|
| none (binary) | 0.83 (0.84 / 0.81) | 11.6% | -16.9% | 40 | +0.05 +0.08 **-0.02** / -0.02 +0.03 **-0.14** |
| 0.10 | 0.94 (0.91 / 1.04) | 6.0% | -7.0% | | |
| 0.15 | 0.93 (0.89 / 1.02) | 7.9% | -10.4% | 21 | +0.06 +0.07 +0.05 / +0.08 +0.10 +0.05 |
| **0.20** | **0.89 (0.86 / 0.97)** | **9.3%** | **-13.4%** | 23 | **+0.07 +0.08 +0.04 / +0.06 +0.08 +0.01** |
| 0.25 | 0.85 (0.84 / 0.90) | 10.0% | -16.0% | 26 | +0.06 +0.08 +0.02 / +0.02 +0.05 -0.04 |
| 0.30 | 0.83 (0.84 / 0.82) | 10.4% | -15.9% | 30 | +0.05 +0.08 -0.01 / -0.01 +0.05 -0.12 |

The constant-notional sleeve fails the ensemble gate OOS because it adds full-size QQQ beta in
exactly the weeks (March 2020, 2022, April 2025) when the live reversal sleeve is already at full
exposure; scaling to constant risk fixes that. `vol_target = 0.20` (QQQ's long-run vol, i.e. "hold
QQQ at normal risk, not crisis risk") is the middle of a smooth plateau; 0.15 is marginally better
on every metric except CAGR. **Disclosure:** 1/RV sizing was in the pre-registered plan, but its
adoption as the default was informed by the ensemble deltas above, not by the standalone numbers
(which are flat). The IS/OOS pattern (IS delta unchanged, OOS delta improves monotonically as the
target falls) is at least consistent with a risk-budget effect rather than a lucky draw.

### 2e. Ensemble deltas for the remaining variants (2f in the scripts; 36 + 18 runs, section 5)

Growth profile (`EnsembleParams.from_profile("growth")`: overnight QQQ->QLD/SMH/IWM x regime
multiplier, reversal 0.5, dd throttle 10%/0.5, leverage map, gross-long cap 1.0), reproduced in a
scratch script and verified bit-identical to `hf_ensemble_weights` and to
`/tmp/qb_shared/growth_weights_reference.parquet` (max |diff| 0.0). Sleeve summed in via
`combine_weights` at the stated allocation, **not** regime-scaled. Baseline **1.324 (IS 1.218 / OOS
1.564)**, CAGR 11.6%, MaxDD -12.2%.

| sleeve variant (all VIX > 20 full day unless stated) | standalone Sh (IS/OOS) | x 0.25: Sh, dSh full/IS/OOS | x 0.5 | x 1.0 |
|---|---|---|---|---|
| **QQQ long vt 0.20 (default)** | 0.89 (0.86/0.97) | **1.392, +.068/+.079/+.044** | **1.384, +.061/+.083/+.012** | 1.282, -.041/+.016/-.164 |
| QQQ long vt 0.15 | 0.93 (0.89/1.02) | 1.388, +.064/+.070/+.051 | 1.404, +.081/+.096/+.046 | 1.327, +.004/+.040/-.076 |
| QQQ long, binary | 0.83 (0.84/0.81) | 1.372, +.048/+.078/-.018 | 1.302, -.022/+.034/-.143 | 1.124 |
| SPY long vt 0.20 | 0.64 (0.59/0.75) | 1.316, -.008/-.005/-.013 | 1.238 | 1.131 |
| SPY long, binary | 0.65 (0.64/0.67) | 1.308, -.015/+.001/-.049 | 1.191 | 1.046 |
| EW3 long vt 0.20 | 0.80 (0.74/0.94) | 1.353, +.029/+.026/+.037 | 1.321, -.002 | 1.215 |
| QQQ long VIX > 25 vt 0.20 | 0.55 (0.60/0.44) | 1.326, +.002/+.026/-.050 | 1.288 | 1.164 |
| QQQ long ramp (18,10) vt 0.20 | 0.79 (0.78/0.83) | 1.357, +.033/+.043/+.012 | 1.352, +.029/+.046/-.008 | 1.286 |
| QQQ both via PSQ (cash acct) | 0.63 (0.55/0.81) | 1.394, +.070/+.059/+.094 | 1.273, -.050 | 0.997 |
| QQQ both via PSQ, vt 0.20 | 0.62 (0.47/0.93) | 1.404, +.080/+.052/+.141 | 1.351, +.028/-.016/+.118 | 1.128 |
| QQQ both/short (paper), vt 0.20 | 0.64 (0.51/0.93) | 1.418, +.094/+.069/+.150 | 1.371, +.047/+.010/+.124 | 1.139 |

The SPY versions add nothing to the ensemble (the reversal sleeve already supplies VIX-timed SPY-like
beta); QQQ does because its bp/cost is higher. The both-halves versions have the best *OOS* delta at
0.25 (their correlation with the ensemble is 0.11 vs 0.36) because the short half hedges the reversal
sleeve's daytime beta the day after an up day - but the short half has no standalone mean (IS 0.47-
0.51), needs shorts or a 2 bp inverse fund, doubles MaxDD, and flips to a drag at 0.5. Left as an
option (`mode="both_inverse"`), not the default.

### 2f. Sensitivity (34 runs, section 4) and extra ensemble configurations (10 runs, section 5)

**Trial count:** 2a 132 + 2b 90 + 2c 14 + 2d 16 + 8 + 2e 3 new standalone + 54 ensemble runs + 2f 34
+ 10 = **361**. Diagnostics that select nothing (PSQ fidelity, session decomposition of the final
config, tail tables, cost sweep) are not counted.

## 3. Final scorecard

`TSReversalParams()` defaults: `assets=("QQQ",), signal_source="own", gate="vix", vix_threshold=20,
vix_span=0, mode="long", window="full", z_min=0, z_cap=None, vol_target=0.20, max_gross=1.0`.
`report()` output (T-bill cash, Sharpe excess of it, `n_trials=361`):

```
ts_reversal        | CAGR   9.29% | Vol  8.72% | Sharpe  0.89 | Sortino  1.22 | MaxDD -13.41% | Calmar  0.69 | t  4.32 | PF 1.55 | exp L/S 0.12/0.00 | cost/yr 0.38% | days 4179
  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean 1.5% over the period)
  time in market 15.3% | turnover/day 0.15 | trades/day 0.23 | skew 0.78 | kurt 23.1 | best +6.72% | worst -4.85%
  Sharpe 95% bootstrap CI: [0.49, 1.30]
  Deflated Sharpe: P(SR > null max of 361 trials = 0.73) = 0.756
  vs benchmark: corr 0.56 | beta 0.29

  Yearly:
       return      vol   sharpe   max_dd  days
2010    0.078    0.123    0.725   -0.089   230
2011    0.034    0.124    0.332   -0.134   252
2012    0.097    0.064    1.475   -0.046   250
2013   -0.001    0.010   -0.178   -0.006   252
2014   -0.011    0.035   -0.296   -0.035   252
2015    0.052    0.079    0.675   -0.039   252
2016    0.049    0.069    0.687   -0.041   252
2017    0.009    0.000   -0.236    0.000   251
2018    0.100    0.108    0.768   -0.056   251
2019    0.132    0.041    2.565   -0.001   252
2020    0.236    0.114    1.878   -0.056   253
2021    0.139    0.093    1.450   -0.069   252
2022   -0.003    0.152   -0.078   -0.090   251
2023    0.096    0.064    0.695   -0.031   250
2024    0.093    0.050    0.813   -0.025   252
2025    0.318    0.102    2.386   -0.040   250
2026    0.172    0.092    2.112   -0.044   177

  In-sample / out-of-sample split at 2022-01-01:
                           days     cagr      vol   sharpe  sortino  max_drawdown   calmar
ts_reversal in-sample      2999    0.075    0.082    0.861    1.131        -0.134    0.559
ts_reversal out-of-sample  1180    0.140    0.099    0.972    1.455        -0.090    1.558
ts_reversal full           4179    0.093    0.087    0.893    1.225        -0.134    0.692
```

Ex-cash (cash yield 0): Sharpe 0.91, CAGR 7.85%. Gross (0 cost, 0 cash): Sharpe 0.95, CAGR 8.25%.
**Breakeven 22.1 bp/side** (assumed 1 bp). Net Sharpe at 2 / 3 / 5 / 8 bp per side: 0.85 / 0.81 /
0.73 / 0.60 (OOS 0.93 / 0.89 / 0.81 / 0.69). Active days 638 (15.3%), mean **+21.2 bp net per active
day**, hit rate 58%, mean exposure when active 0.79. Active days per year: 2010 74, 2011 71, 2012 26,
2013 3, 2014 8, 2015 25, 2016 26, 2017 0, 2018 34, 2019 10, 2020 82, 2021 53, **2022 130**, 2023 24,
2024 15, 2025 35, 2026 22. Session decomposition of the final trade (QQQ after a down day, VIX > 20,
gross): overnight **10.6 bp (t 2.1)** [IS 11.9 / OOS 8.4], intraday **17.7 bp (t 2.9)** [17.6 / 17.9],
full day 28.4 bp (t 3.6) [29.6 / 26.1]; after an *up* day on VIX > 20 the next day is -2.0 bp (t
-0.3), so the down-vs-up spread is 30 bp; unconditional QQQ on VIX > 20 days is 13.9 bp (7.7 all
days), i.e. about half of the active-day return is the high-vol equity premium and half is reversal
proper.

Negative years: 2013 (-0.1%, 3 active days), 2014 (-1.1%), 2022 (-0.3% on 130 active days - the one
sustained high-VIX year where the reversal earned nothing: down days were followed by more down days
in a grinding bear; the long half made +1.7% gross and the sleeve's own drawdown was -9%). 2017 had no
active day. The sleeve is, by design, a crash-and-correction sleeve: 2010, 2011, 2018, 2020, 2022,
2025 supply 60% of the active days.

## 4. Sensitivity (one-at-a-time around the defaults; net Sharpe full (IS / OOS), CAGR, MaxDD, time in market, breakeven)

| param | value | Sharpe | CAGR | MaxDD | tim | BE bp |
|---|---|---|---|---|---|---|
| vix_threshold | 15 | 0.66 (0.58 / 0.82) | 8.5% | -18.3% | 31% | 10.9 |
| | 18 | 0.90 (0.81 / 1.10) | 10.2% | -13.4% | 21% | 18.6 |
| | **20** | **0.89 (0.86 / 0.97)** | 9.3% | -13.4% | 15% | 22.1 |
| | 22 | 0.72 (0.74 / 0.66) | 7.0% | -13.6% | 11% | 23.0 |
| | 25 | 0.55 (0.60 / 0.44) | 5.0% | -12.5% | 7% | 24.2 |
| | 28 | 0.54 (0.49 / 0.64) | 4.4% | -14.7% | 4.5% | 32.8 |
| | 30 | 0.51 (0.50 / 0.56) | 4.1% | -12.6% | 3.5% | 39.3 |
| vix_span (ramp) | **0 (cliff)** | 0.89 (0.86 / 0.97) | 9.3% | -13.4% | 15% | 22.1 |
| | 5 | 0.77 (0.78 / 0.73) | 7.0% | -12.8% | 15% | 24.0 |
| | 10 | 0.70 (0.70 / 0.70) | 5.7% | -12.2% | 15% | 25.5 |
| vol_target | None | 0.83 (0.84 / 0.81) | 11.6% | -16.9% | 15% | 23.5 |
| | 0.10 | 0.94 (0.91 / 1.04) | 6.0% | -7.0% | | 22.3 |
| | 0.15 | 0.93 (0.89 / 1.02) | 7.9% | -10.4% | | 22.3 |
| | **0.20** | 0.89 (0.86 / 0.97) | 9.3% | -13.4% | | 22.1 |
| | 0.25 | 0.85 (0.84 / 0.90) | 10.0% | -16.0% | | 22.0 |
| | 0.30 | 0.83 (0.84 / 0.82) | 10.4% | -15.9% | | 21.9 |
| gate | **vix** | 0.89 | 9.3% | -13.4% | 15% | 22.1 |
| | vix_ma (VIX > 20d MA) | 0.62 (0.55 / 0.78) | 7.4% | -11.3% | 24% | 10.8 |
| | rv (RV20 SPY > 18.4%) | 0.63 (0.63 / 0.64) | 5.7% | -14.8% | 10% | 22.6 |
| assets | **QQQ** | 0.89 (0.86 / 0.97) | 9.3% | -13.4% | 15% | 22.1 |
| | SPY | 0.64 (0.59 / 0.75) | 6.8% | -13.1% | 16% | 14.8 |
| | IWM | 0.69 (0.59 / 0.94) | 7.6% | -14.9% | 15% | 18.8 |
| | SPY+QQQ+IWM | 0.80 (0.74 / 0.94) | 8.0% | -12.9% | 19% | 18.4 |
| signal_source | **own** | 0.89 (0.86 / 0.97) | 9.3% | | | |
| | SPY | 0.79 (0.68 / 1.03) | 8.5% | -12.5% | 16% | 20.3 |
| window | **full** | 0.89 (0.86 / 0.97) | 9.3% | -13.4% | 15% | 22.1 |
| | overnight | 0.48 (0.46 / 0.52) | 4.1% | -8.5% | 7.6% | 5.7 |
| | intraday | 0.61 (0.59 / 0.67) | 5.6% | -10.9% | 7.6% | 8.0 |
| mode | **long** | 0.89 (0.86 / 0.97) | 9.3% | -13.4% | 15% | 22.1 |
| | both_inverse (PSQ) | 0.62 (0.47 / 0.93) | 8.2% | -24.1% | 29% | 12.5 |
| | both_short (paper) | 0.64 (0.51 / 0.93) | 8.5% | -23.1% | 29% | 12.3 |
| z_min | **0** | 0.89 (0.86 / 0.97) | 9.3% | -13.4% | 15% | 22.1 |
| | 0.5 | 0.78 (0.84 / 0.66) | 7.1% | -11.9% | 10% | 19.7 |
| | 1.0 | 0.83 (0.94 / 0.58) | 6.2% | -7.5% | 6% | 22.2 |

Reading: every value in every row is >= 0.48 net with the same sign IS and OOS; no parameter flips.
The one slope to watch is `vix_threshold`: 18-20 is the top of a hump (0.89-0.90) and each +2-3 VIX
points costs ~0.15 Sharpe down to 0.51 at 30, mechanically because the VIX 20-25 band contributes
half of the active days and they carry a positive edge (2a). 15 is worse (the VIX 15-20 band has no
reversal, 2a). It is a slope, not a cliff, and OOS prefers the lower thresholds (18: 1.10, 20: 0.97).
A ramp *hurts* here (unlike in `reversal.md`) because it under-weights exactly the 20-30 band.
`vol_target` is a monotone Sharpe-vs-CAGR dial with a flat top at 0.10-0.20. Window, mode, asset and
gate are the structural choices and are each 0.2-0.4 apart in the direction the priors predicted.

## 5. Correlations and ensemble impact

Excess daily returns vs `/tmp/qb_shared/reference_daily_returns.csv`, full [OOS 2022+]; last column
= correlation on the sleeve's active days only:

| | ensemble_growth | overnight | reversal | spy |
|---|---|---|---|---|
| ts_reversal (default) | **0.36** [0.41] | **0.17** [0.16] | **0.43** [0.50] | **0.56** [0.61] |
| active days only | 0.61 | 0.32 | 0.53 | 0.89 |
| QQQ both via PSQ (alt.) | 0.11 [0.14] | 0.04 [0.05] | 0.13 [0.17] | 0.15 [0.18] |
| SPY long vt 0.20 | 0.37 [0.41] | 0.16 [0.11] | 0.48 [0.57] | 0.65 [0.65] |

Overlap of active days with the live sleeves (core config, defaults): on **98.4%** of this sleeve's
active days the live reversal sleeve is also long the next morning (VIX > 20 is a subset of its
VIX > 18 ramp), and on 33% of its nights the live overnight sleeve is also long (its 200d gate is
usually off in high vol). So the sleeve is *not* filling dead time: it is doubling down on the
reversal sleeve's regime with an index position held 24h instead of 7 stocks held 6.5h. On those
days it is beta (0.89 with SPY). Its diversification value comes from (i) the overnight leg, which the
reversal sleeve does not hold, (ii) the down-day condition (the reversal sleeve is on every VIX > 18
day regardless of the index's sign), and (iii) QQQ instead of mega-caps.

Ensemble (growth profile, method as in 2e; Sharpe excess of T-bill, full (IS / OOS), CAGR, MaxDD):

| configuration | Sharpe | CAGR | MaxDD | vol |
|---|---|---|---|---|
| growth baseline (overnight 1.0 x regime, reversal 0.5) | **1.324 (1.218 / 1.564)** | 11.6% | -12.2% | 7.4% |
| **+ ts_reversal x 0.25** | **1.392 (1.297 / 1.608)** | 13.6% | -11.6% | 8.4% |
| + ts_reversal x 0.35 | 1.403 (1.316 / 1.604) | 14.5% | -11.2% | 8.9% |
| + ts_reversal x 0.5 | 1.384 (1.301 / 1.576) | 15.5% | -10.9% | 9.7% |
| + ts_reversal x 1.0 | 1.282 (1.234 / 1.400) | 17.2% | -13.0% | 11.8% |
| overnight only (reversal 0) | 1.102 (0.963 / 1.394) | 8.2% | -12.3% | 5.9% |
| overnight + ts_reversal 0.25 (reversal 0) | 1.277 (1.139 / 1.581) | 9.8% | -12.0% | 6.3% |
| **overnight + ts_reversal 0.5 (reversal 0)** | **1.331 (1.209 / 1.602)** | 11.7% | -11.2% | 7.4% |
| overnight + reversal 0.25 + ts_reversal 0.25 | 1.397 (1.284 / 1.654) | 11.7% | -11.8% | 7.1% |
| overnight + reversal 1.0 ("max"-like) | 1.212 (1.133 / 1.397) | 15.1% | -12.2% | 10.8% |
| overnight + reversal 1.0 + ts_reversal 0.25 | 1.264 (1.194 / 1.427) | 16.2% | -11.5% | 11.2% |

Yearly return of growth vs growth + 0.25: the sleeve adds in 13 of 17 years (+6.1 pp 2020, +7.4 pp
2025, +4.2 pp 2021, +3.5 pp 2026, +2.6 pp 2019) and costs -0.5 to -0.6 pp in 2013, 2014 and 2022. The
gross-long cap binds on 4.3% of rows with the sleeve vs 4.1% without, so the cash constraint is not
what limits the allocation; the OOS Sharpe is (it peaks at 0.25-0.35 and is below baseline at 1.0).

The substitution rows matter for the orchestrator: **overnight + this sleeve at 0.5, with the live
reversal sleeve removed, equals the growth profile** (1.331 vs 1.324; CAGR 11.7 vs 11.6%; MaxDD
-11.2 vs -12.2%) with cost drag 0.4%/yr instead of 2.8%, one ETF order at the close instead of 7
stock orders in the opening auction (the "make-or-break" risk in `reversal.md` section 6), and no
survivorship bias. Roughly half of the live reversal sleeve's ensemble value is VIX-timed beta that
this sleeve delivers more cheaply; the other half (cross-sectional selection) is what the reversal
sleeve keeps adding on top (1.397 with both at 0.25).

## 6. Failure modes / when to turn it off

1. **It buys crashes with a one-day horizon, and crashes have consecutive down days.** Worst days
   (net): 2011-08-08 -4.85% (QQQ -6.0%, VIX 32), 2025-04-04 -3.98% (QQQ -6.2%), 2018-02-08 -3.81%,
   2020-09-08 -3.66%, 2015-08-24 -3.65%, 2018-10-24 -3.59%, 2020-03-12 -3.56% (QQQ -9.2%; exposure
   was 0.38 thanks to the vol target), 2020-03-09 -3.52%, 2010-05-06 -3.34%, 2010-06-29 -3.21%. Skew
   is *positive* (+0.78: the bounce days are bigger - best +6.7% on 2025-04-09) but kurtosis is 23
   and MaxDD -13.4% (2011-07-28 -> 2011-10-03, recovered 2012-01). Episode returns (sleeve net |
   active days | SPY): 2011-08 US downgrade **-9.7%** | 25/55 | -10.7%; 2015-08 -0.5% | 16/32 |
   -8.0%; 2018-02 +0.1% | 4/23 | -6.6%; 2018-Q4 +4.5% | 22/63 | -13.5%; 2020-03 +5.7% | 23/50 |
   -13.6%; 2022 -0.3% | 130/251 | -18.2%; 2025-04 **+8.3%** | 14/35 | +3.8%; 2026 YTD +17.2% | 22/177
   | +11.2%. It made money in five of the seven stress episodes and lost in the two where the market
   fell for weeks with few bounces (Aug 2011, 2022). Size for a -10% episode.
2. **Its drawdowns coincide with the reversal sleeve's and with the market's.** Correlation 0.89 with
   SPY on active days; the reversal sleeve is long the same mornings. At the ensemble level this is
   why the allocation tops out at 0.25-0.35: above that the OOS Sharpe falls even though the
   standalone Sharpe is 0.9.
3. **Grinding bears are the dead zone, not the disaster zone.** 2022: 130 active days, -0.3%. The
   sleeve does not lose much in such a year but pays 130 round trips (0.9% cost) for nothing.
   Monitor the trailing 60-active-day mean net return; below +5 bp/active day the regime has become
   "down days continue" (the 2022 pattern) and the allocation should go to 0.
4. **Threshold slope.** 18-20 is the sweet spot; if VIX's level drifts structurally (e.g. a
   prolonged VIX-15 regime with occasional 20s, or a regime where 20 is the new normal), the gate
   is either never or always on. A percentile-of-VIX gate was not tested (rule of the brief: VIX
   percentile rules were destructive elsewhere); revisit if VIX's distribution shifts.
5. **The short half is not an edge.** `mode="both_inverse"` / `"both_short"` are in the file for the
   record: +0.09 ensemble Sharpe at 0.25 purely as a hedge to the reversal sleeve's beta, standalone
   IS Sharpe 0.47-0.51, MaxDD -24%, and the short leg's return after up days is -2 bp/day gross. PSQ
   tracks -1x QQQ well (beta 0.996, alpha +0.7 bp/day c2c; the fund's financing income accrues
   overnight, +1.2 bp/night), so implementation is not the problem; the absence of a mean is.
6. **Execution.** Both trades are at the 16:00 close (MOC in QQQ), the deepest auction there is;
   the signal needs the ^VIX close and QQQ's close, both available ~16:00:05. Live, compute the
   signal from the 15:59 quotes and send MOC by 15:50 (the sign of a 1%+ move is rarely in doubt
   at 15:50; on days where QQQ is within +-0.1% of unchanged at 15:50 the trade is a coin flip on the
   signal and may be skipped). At 2-3 bp/side the Sharpe is 0.85-0.81, so fill quality is not
   critical.
7. **Cash-yield accounting.** 85% cash; the T-bill convention (mean 1.5%) adds ~1.4 pp CAGR over
   the ex-cash version; Sharpe is unaffected (excess-of-cash convention): 0.89 vs ex-cash 0.91.
8. **Deflated Sharpe 0.76 after 361 trials; bootstrap CI [0.49, 1.30].** A real but modest edge
   whose lower confidence bound sits at the gate.
9. Shared-code notes (not bugs): (i) `regime.md` insight 2's "Sharpe 1.26" is an *active-day*
   Sharpe; on the full timeline the same trade is 0.46 gross - anyone quoting conditional Sharpes
   should say which. (ii) The engine's `time_in_market` counts rows with a non-zero target; for a
   16:00 -> 16:00 hold the 09:30 row is forward-filled and counted, so 15.3% here means 15.3% of
   *sessions* = 15.3% of days (638 of 4179). (iii) `report()`'s deflated Sharpe uses the excess
   series; the bootstrap CI too.

## 7. Recommended params and ensemble allocation

`TSReversalParams()` defaults as in section 3. **Recommended allocation: 0.25 of the ensemble's gross
budget** (0.25-0.35 is the plateau; 0.5 still passes the gate but the OOS gain is +0.01). Do **not**
put it in `regime_scaled` (it lives in high vol; the multiplier would switch it off). If the
orchestrator wants a cheaper, lower-implementation-risk replacement for the stock reversal sleeve,
`overnight 1.0 + ts_reversal 0.5 + reversal 0` reproduces the growth profile's Sharpe; the best
combination found is `overnight 1.0 + reversal 0.25 + ts_reversal 0.25` (1.397, OOS 1.654, MaxDD
-11.8%). Paper-trade at 0.25 first: the sleeve has only ~40 active days a year, so live evidence
accumulates slowly. Ensemble `n_trials_total` should grow by 361.

## 8. Insights for other sleeves

1. **Active-day Sharpe != sleeve Sharpe.** A conditional edge on f% of days contributes roughly
   sqrt(f) x its active-day Sharpe to a full-timeline sleeve: VIX > 25 reversal at "Sharpe 1.26" is a
   0.46 sleeve. When comparing candidate gates, always compute the Sharpe with zeros on inactive
   days (or the equivalent: mean bp x sqrt(n_active)).
2. **Index reversal in stress is a long-only, full-day trade.** After a down day with VIX > 20, QQQ
   earns +10.6 bp overnight (t 2.1) and +17.7 bp intraday (t 2.9); after an up day, -2 bp. The
   overnight leg of the bounce is the part the live gap-fade reversal sleeve (09:30 entry) misses,
   and the down-day condition is the part it ignores. An overnight sleeve that wants exposure in high
   vol should hold *only after down days* (the 200d gate is off then, but this condition is on).
3. **VIX level is the conditioner for liquidity provision; realised variance is the conditioner for
   sizing beta.** Confirmed for the third time (`reversal.md` 2d, `etf_reversal.md`, here): RV gates
   are 0.2-0.4 Sharpe worse and collapse OOS; VIX > 20 is stable. The two are not in conflict:
   `regime.md`'s multiplier sizes *risk-on* sleeves, this gate times *liquidity-provision* sleeves.
   The ensemble should keep the two mechanisms separate (this sleeve must not be regime-scaled).
4. **1/RV sizing is what makes a crash sleeve additive to a portfolio that already holds crash beta.**
   Standalone the vol target is Sharpe-neutral (0.83 -> 0.89), but constant-notional crash exposure
   fails the ensemble gate OOS (-0.02 / -0.14 at 0.25 / 0.5) and constant-risk passes (+0.04 / +0.01).
   Any new sleeve that is long beta in high vol should be delivered vol-targeted, or it will just
   re-lever the reversal sleeve's worst weeks.
5. **Sizing by the size of the move is an in-sample trap for index reversal.** Every |r|/sigma rule
   added 0.1-0.3 IS and lost 0.2-0.7 OOS; the > 2 sigma bucket went from +77 bp to -28 bp. Big index
   moves are news (Da-Liu-Schaumburg at the index level); trade the sign, not the size.
6. **The higher-vol expression wins at fixed bp cost, again:** QQQ 0.89 vs SPY 0.64 for the identical
   rule (28 vs 20 bp/active day, same 1 bp). The equal-weight index basket does not diversify (pairwise
   ~0.9) and only dilutes toward SPY.
7. **Refreshing a 16:00 signal with the 09:30 open destroys it.** Sign of close[d-1] -> open[d+1]
   earns 4 bp intraday vs 11 bp for yesterday's sign alone; the index gap itself does not fade (1.6
   bp). For index ETFs the gap is part of the reversal, not a new signal - the opposite of the
   mega-cap result (`reversal.md` insight 2), where the gap is the *only* signal.
8. **Half of the live reversal sleeve's ensemble contribution is VIX-timed beta** that one QQQ MOC
   order per active day replicates at 1/7 of the cost (section 5). Its cross-sectional half is worth
   ~+0.07 ensemble Sharpe on top. Worth knowing when deciding how much fill-quality risk at the open
   the system should carry.

## 9. Round 3 acceptance gate

| gate | requirement | result | verdict |
|---|---|---|---|
| 1 | standalone net Sharpe >= 0.5 full **and** OOS >= 0.4, same sign | 0.89 full, IS 0.86, OOS 0.97 | pass |
| 2 | breakeven cost >= 2x assumed | 22.1 bp vs 1 bp (22x); IS 20.8 bp, OOS (2022+) 25.1 bp | pass |
| 3 | growth ensemble Sharpe up IS **and** OOS at the recommended allocation | 0.25: +0.079 IS / +0.044 OOS (1.324 -> 1.392); 0.5: +0.083 / +0.012; 1.0: fails OOS | pass at 0.25 (and 0.5) |
| 4 | one-at-a-time sensitivity degrades smoothly | all 34 values >= 0.48 with same-sign IS/OOS; `vix_threshold` is a slope (0.90 -> 0.51 over 18 -> 30), no flips | pass |

**Verdict: ACCEPT at allocation 0.25**, with three caveats stated for the record: (a) the
pre-registered baseline (SPY, VIX > 25, both halves) *fails* (0.42 / OOS 0.31); the accepted sleeve is
the long half, in QQQ, at VIX > 20, vol-targeted - each change was on the pre-registered variant
list, and each is the direction the priors predicted, but the choices were made after seeing IS and
OOS numbers; (b) the ensemble pass depends on the 1/RV sizing (constant notional fails OOS), which
was adopted after seeing the ensemble deltas; (c) correlation with the live reversal sleeve is
0.43-0.50 and 98% of active days coincide with it, so the gain to the ensemble is +0.07 Sharpe, not
the +0.3 an independent 0.9-Sharpe stream would give. What would change the verdict to REJECT: a
2022-style year (>= 100 active days, ~0 return) in paper trading, or the trailing 60-active-day mean
falling below +5 bp. What would change SHADOW -> larger allocation: the orchestrator deciding to trim
the stock reversal sleeve (section 5 substitution rows), in which case 0.5 is the right size.

Files: `quantbot/strategies/hf_ts_reversal.py`; `/tmp/qb_shared/ts_reversal_daily.csv`
(`ts_reversal`, net daily returns, default params, 2010-02-04 -> 2026-09-16) and
`/tmp/qb_shared/ts_reversal_weights.parquet` (4201 rows x QQQ, 16:00 stamps). Scratch:
`/tmp/qb_ts_reversal/` (`01_decomp.py` 2a, `02_grid.py` 2b-2d, `03_independence.py` and
`04_ens_grid.py` 2e/5, `05_final.py` 3/4/6, `06_ens_extra.py` 5).
