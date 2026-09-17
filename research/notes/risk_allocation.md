# Portfolio construction: sizing, vol targeting, throttle, allocation, regime (round 3)

Tools: `quantbot/strategies/hf_risk.py` (pure functions, nothing wired in). Pipeline under
test: `hf_ensemble_weights(md, 'daily', EnsembleParams.from_profile('growth'))` on
`MarketData(HFConfig(), refresh=False, intraday=False)`, reproduced in a scratch script
(`/tmp/qb_risk/pipeline.py`) that imports the sleeves / regime / engine pieces and applies
the modifications; with every modification off it reproduces the reference weights
bit-for-bit (md5 `59f06819cdf380d6a5cb841e84c54188`, shape (8402, 73), max |diff| 0.0, daily
returns equal to the reference CSV to 1e-16). All ensemble numbers below are net of default
costs, idle cash at the T-bill rate, **Sharpe in excess of it**; sleeve-level numbers are
**ex-cash** (cash yield 0, rf 0) unless stated. IS = < 2022-01-01, OOS = 2022+. Under this
evaluation the live growth profile is **Sharpe 1.324 (IS 1.218 / OOS 1.564), CAGR 11.64%,
Vol 7.41%, MaxDD -12.19%** (the OOS 1.53 quoted in `PROFILES` was computed on an earlier
data end; every comparison here uses the same function on the same data).

**`n_trials = 356`** (102 reversal sizing + 43 vol-target/throttle + 162 allocation/regime +
27 joint sizing x allocation + 20 final sensitivity + 2 cost-curve candidates). Diagnostics
that select nothing (bucket tables, bootstrap, cost curves of already-counted variants,
combination tables) are not counted.

## 0. Headline

| | Sharpe (IS / OOS) | CAGR | Vol | MaxDD (IS / OOS) | kurt | worst day | cost/yr |
|---|---|---|---|---|---|---|---|
| live growth | 1.324 (1.218 / 1.564) | 11.64% | 7.41% | -12.19% (-12.2 / -9.6) | 10.6 | -3.81% | 2.83% |
| **recommended** | **1.404 (1.286 / 1.680)** | 12.12% | 7.29% | -10.87% (-10.9 / -10.0) | 9.4 | -3.81% | 3.45% |
| ex-cash, live | 1.362 (1.23 / 1.66) | 10.32% | | -12.6% | | | |
| ex-cash, recommended | 1.45 (1.30 / 1.79) | 10.82% | | -11.3% | | | |

One change carries all of it: **how the gap-fade reversal sleeve is sized**. Replace the
VIX ramp `clip((VIX-18)/10, 0, 1)` (exposure rises linearly with VIX, so the sleeve is
largest exactly when its variance is highest; daily kurtosis 30, worst day -4.9%) by a
short gate ramp times a vol target on the equal-weight intraday book,
`clip((VIX[d-1]-18)/2, 0, 1) * min(1, 0.06 / sigma_EW20[d-1])`, weight the 7 names by
inverse trailing vol, and raise the sleeve's allocation from 0.5 to 1.0 (it never overlaps
the overnight sleeve, so the cash cap is untouched). Sleeve ex-cash Sharpe 0.77 (0.79 /
0.75) -> 0.92 (0.92 / 0.93), kurtosis 30.6 -> 14.2, worst day -4.87% -> -2.64%, MaxDD -12.3%
-> -5.9%. Everything else tested - ensemble-level vol targeting, the drawdown throttle,
the allocation between the two live sleeves, the regime multiplier's parameters - is
either neutral or harmful for Sharpe and should be left alone (section 9).

Caveat that must travel with the recommendation: the re-sized sleeve is **less
cost-robust** than the ramp (breakeven 7.9 vs 9.7 bp/side; the ensemble advantage over
the live profile disappears at ~5 bp/side on stocks, section 1e). It is the right trade
at the 2.5 bp the brief assumes (and MOO fills at the auction print should be at or
below that), but paper-trading fill quality decides it.

## 1. Reversal sleeve sizing (task 1)

### 1a. All variants (102 trials)

Sleeve = long-7 gap-fade book, `ReversalParams()` defaults except the sizing / weighting
shown, ex-cash, alloc 1, from 2010-06-01. `vt_ew` = exposure `min(1, target / sigma)` with
sigma = trailing 20d annualised vol of the equal-weight 70-stock 09:30->16:00 return
(through d-1), gated ON only when VIX(d-1) > 18; `vt_own` = the same with sigma from the
sleeve's own unscaled (exposure 1) 09:30->16:00 returns; `ramp x vt` = the live ramp times
the vol target; `rvtilt` = ramp x (ref / RV)^p with ref = IS median RV; `cap` = ramp
clipped at the cap. "ens @a" = growth ensemble with the sleeve substituted at allocation
a (T-bill cash, excess Sharpe). sigma_EW on active days: q10 8.1%, median 13.7%, q90
24.8%; own-book sigma ~1.3x that.

| variant | avg expo | sleeve Sharpe (IS / OOS) | vol | MaxDD | kurt | worst | ens @0.5 (IS / OOS) | ens @1.0 (IS / OOS) |
|---|---|---|---|---|---|---|---|---|
| **ramp (live)** | 0.200 | 0.77 (0.79 / 0.75) | 9.2% | -12.3% | 30.6 | -4.87% | **1.324 (1.22 / 1.56)** | 1.212 (1.13 / 1.40) |
| (d) ramp + ivol | 0.200 | 0.80 (0.81 / 0.79) | 8.7% | -12.5% | 33.3 | -4.74% | 1.341 (1.23 / 1.60) | 1.257 (1.17 / 1.46) |
| (c) ramp cap 0.5 | 0.138 | 0.84 (0.88 / 0.76) | 5.4% | -6.5% | 19.1 | -2.43% | 1.325 (1.21 / 1.58) | 1.352 (1.27 / 1.55) |
| (c) ramp cap 0.75 | 0.175 | 0.80 (0.83 / 0.74) | 7.5% | -9.1% | 24.1 | -3.65% | 1.335 (1.23 / 1.57) | 1.280 (1.21 / 1.46) |
| (a) vt_ew tgt 0.06 | 0.183 | 0.88 (0.95 / 0.72) | 5.3% | -7.2% | 9.7 | -2.58% | 1.343 (1.25 / 1.56) | 1.386 (1.33 / 1.52) |
| (a) vt_ew tgt 0.08 | 0.240 | 0.85 (0.92 / 0.69) | 6.9% | -9.2% | 9.4 | -3.44% | 1.357 (1.28 / 1.55) | 1.338 (1.30 / 1.42) |
| (a) vt_ew tgt 0.10 | 0.285 | 0.83 (0.91 / 0.66) | 8.2% | -10.9% | 8.6 | -3.56% | 1.352 (1.28 / 1.51) | 1.288 (1.28 / 1.32) |
| (a) vt_ew tgt 0.12 | 0.320 | 0.83 (0.92 / 0.65) | 9.3% | -11.9% | 8.6 | -3.82% | 1.353 (1.30 / 1.49) | 1.256 (1.26 / 1.25) |
| (a) vt_ew tgt 0.15 | 0.353 | 0.85 (0.94 / 0.66) | 10.4% | -11.9% | 9.5 | -4.78% | 1.358 (1.31 / 1.48) | 1.236 (1.24 / 1.22) |
| (a) vt_ew tgt 0.20 | 0.380 | 0.86 (0.95 / 0.67) | 11.6% | -12.8% | 10.7 | -5.58% | 1.361 (1.32 / 1.46) | 1.195 (1.21 / 1.15) |
| (a) vt_ew tgt 0.30 (= binary gate) | 0.395 | 0.92 (1.02 / 0.72) | 12.3% | -13.3% | 11.4 | -5.58% | 1.399 (1.37 / 1.48) | 1.233 (1.26 / 1.17) |
| (a) vt_own tgt 0.10 | 0.236 | 0.85 (0.90 / 0.72) | 7.0% | -9.3% | 9.4 | -2.71% | 1.358 (1.27 / 1.56) | 1.332 (1.28 / 1.46) |
| (a) vt_own tgt 0.12 | 0.276 | 0.85 (0.92 / 0.70) | 8.2% | -10.3% | 9.3 | -3.25% | 1.364 (1.29 / 1.54) | 1.302 (1.26 / 1.39) |
| (a) vt_own tgt 0.15 | 0.323 | 0.84 (0.92 / 0.66) | 9.7% | -11.1% | 9.4 | -3.99% | 1.356 (1.30 / 1.49) | 1.254 (1.24 / 1.28) |
| (a) vt_own tgt 0.20 | 0.365 | 0.86 (0.94 / 0.67) | 11.2% | -12.8% | 10.3 | -4.75% | 1.357 (1.31 / 1.47) | 1.214 (1.23 / 1.17) |
| (a) vt_own tgt 0.25 | 0.382 | 0.89 (0.97 / 0.71) | 11.9% | -13.3% | 10.8 | -5.58% | 1.375 (1.33 / 1.48) | 1.209 (1.22 / 1.19) |
| (a) vt_own tgt 0.30 | 0.390 | 0.92 (1.01 / 0.72) | 12.3% | -13.3% | 11.4 | -5.58% | 1.396 (1.36 / 1.48) | 1.229 (1.25 / 1.18) |
| (a) vt_own tgt 0.40 | 0.393 | 0.94 (1.03 / 0.74) | 12.5% | -13.3% | 12.0 | -5.58% | 1.410 (1.37 / 1.50) | 1.244 (1.27 / 1.19) |
| ramp x vt_ew tgt 0.10 | 0.124 | 0.66 (0.64 / 0.72) | 5.1% | -7.8% | 23.2 | -3.19% | 1.249 (1.11 / 1.56) | 1.242 (1.11 / 1.54) |
| ramp x vt_ew tgt 0.15 | 0.164 | 0.66 (0.65 / 0.69) | 7.0% | -9.4% | 26.0 | -4.78% | 1.265 (1.14 / 1.55) | 1.191 (1.08 / 1.45) |
| ramp x vt_ew tgt 0.20 | 0.184 | 0.68 (0.69 / 0.67) | 8.2% | -11.3% | 27.2 | -4.87% | 1.274 (1.16 / 1.53) | 1.165 (1.07 / 1.38) |
| (b) ramp x rvtilt ew p0.5 | 0.156 | 0.73 (0.72 / 0.74) | 6.6% | -8.8% | 24.1 | -3.90% | 1.297 (1.17 / 1.58) | 1.252 (1.15 / 1.50) |
| (b) ramp x rvtilt ew p1 | 0.127 | 0.68 (0.66 / 0.74) | 5.1% | -8.5% | 23.8 | -3.45% | 1.258 (1.12 / 1.57) | 1.257 (1.13 / 1.56) |
| (b) ramp x rvtilt ew p2 | 0.094 | 0.63 (0.58 / 0.77) | 3.6% | -7.5% | 37.0 | -3.45% | 1.213 (1.07 / 1.54) | 1.244 (1.09 / 1.60) |
| (b) ramp x rvtilt own p0.5 | 0.164 | 0.73 (0.72 / 0.75) | 7.0% | -9.0% | 24.8 | -3.84% | 1.300 (1.18 / 1.58) | 1.242 (1.14 / 1.49) |
| (b) ramp x rvtilt own p1 | 0.138 | 0.67 (0.64 / 0.75) | 5.7% | -8.5% | 24.0 | -3.20% | 1.270 (1.13 / 1.58) | 1.247 (1.12 / 1.55) |
| (b) ramp x rvtilt own p2 | 0.106 | 0.58 (0.51 / 0.79) | 4.2% | -8.4% | 34.3 | -2.95% | 1.222 (1.07 / 1.56) | 1.229 (1.07 / 1.60) |
| vt_ew tgt 0.10, sigma window 10 | 0.289 | 0.88 (0.96 / 0.70) | 8.3% | -11.3% | 9.5 | -3.56% | 1.385 (1.32 / 1.54) | |
| vt_ew tgt 0.10, window 40 | 0.283 | 0.87 (0.96 / 0.65) | 8.3% | -11.4% | 9.5 | -3.91% | 1.367 (1.31 / 1.51) | |
| vt_ew tgt 0.10, window 60 | 0.283 | 0.88 (0.96 / 0.69) | 8.5% | -11.7% | 10.8 | -4.43% | 1.369 (1.30 / 1.53) | |
| vt_ew tgt 0.08 + ivol | 0.240 | 0.88 (0.91 / 0.81) | 6.4% | -8.9% | 10.0 | -3.51% | 1.361 (1.25 / 1.61) | 1.360 (1.29 / 1.52) |
| vt_ew tgt 0.10 + ivol | 0.285 | 0.86 (0.90 / 0.76) | 7.6% | -10.4% | 9.0 | -3.52% | 1.359 (1.26 / 1.58) | 1.303 (1.27 / 1.38) |
| vt_ew tgt 0.12 + ivol | 0.320 | 0.86 (0.92 / 0.74) | 8.6% | -11.1% | 9.1 | -3.72% | 1.364 (1.28 / 1.56) | 1.273 (1.25 / 1.33) |
| vt_own tgt 0.15 + ivol | 0.337 | 0.86 (0.92 / 0.75) | 9.4% | -10.7% | 9.9 | -3.85% | 1.366 (1.28 / 1.55) | 1.264 (1.23 / 1.34) |
| vt_own tgt 0.20 + ivol | 0.372 | 0.88 (0.93 / 0.79) | 10.7% | -11.7% | 10.8 | -4.74% | 1.376 (1.30 / 1.56) | 1.229 (1.22 / 1.26) |

Reading: every rule that *does not* increase exposure with VIX beyond the gate (binary
gate, vol target, capped ramp) beats the ramp in-sample by 0.07-0.25 sleeve Sharpe and
matches it OOS; every rule that keeps the ramp and multiplies it by a vol tilt (`ramp x
vt`, `rvtilt`) is *worse* in both periods - the ramp and the tilt fight each other, and
the product ends up under-weighting the VIX 18-22 days (which have the best net return
per unit of variance, 1b) and still over-weighting the crash days. Inverse-vol name
weighting adds +0.03 in both periods (as reversal.md found). The kurtosis story is
mechanical: the ramp's kurtosis of 30 comes from being 100% exposed on the days when the
book's own vol is 2-3x normal; any of the alternatives cuts it to 8-12.

### 1b. Why: the sleeve's edge scales with its variance (diagnostics, not trials)

Unit book (exposure 1, long-7, eq) net of 5 bp round trip, by lagged VIX bucket. `mu/var`
is the Kelly-optimal exposure up to a constant.

| VIX(d-1) | IS days | IS net bp | IS sd bp | IS Sharpe | IS mu/var | OOS days | OOS net bp | OOS sd bp | OOS Sharpe | OOS mu/var |
|---|---|---|---|---|---|---|---|---|---|---|
| <= 14 | 935 | 1.3 | 66 | 0.32 | 3.0 | 169 | 3.2 | 76 | 0.66 | 5.5 |
| 14-18 | 926 | 5.9 | 82 | 1.14 | 8.8 | 447 | **-9.2** | 98 | -1.49 | -9.5 |
| 18-22 | 493 | 13.3 | 101 | 2.09 | 13.1 | 280 | 5.3 | 104 | 0.81 | 4.9 |
| 22-28 | 335 | 5.8 | 124 | 0.75 | 3.8 | 190 | 1.1 | 115 | 0.15 | 0.8 |
| 28-40 | 183 | 16.1 | 140 | 1.82 | 8.2 | 90 | 24.5 | 150 | 2.59 | 10.8 |
| > 40 | 47 | 62.8 | 252 | 3.96 | 9.9 | 4 | 198 | 477 | 6.61 | 8.7 |

Within VIX > 18 days, by tercile of sigma_EW (the vol-target input):

| tercile | IS net bp | IS sd bp | IS Sharpe | IS mu/var | OOS net bp | OOS sd bp | OOS Sharpe | OOS mu/var |
|---|---|---|---|---|---|---|---|---|
| low sigma (~9%) | 7.6 | 94 | 1.28 | 8.5 | 6.7 | 91 | 1.18 | 8.2 |
| mid sigma (~14%) | 8.8 | 115 | 1.21 | 6.6 | 4.0 | 120 | 0.53 | 2.8 |
| high sigma (~24%) | 24.5 | 159 | 2.44 | 9.7 | 14.1 | 149 | 1.50 | 6.4 |

The mean return of the fade rises roughly with the *variance* of the book (Nagel:
liquidity-provision returns scale with volatility), so `mu/var` is approximately flat
across sigma terciles and across VIX buckets above 18 (8-13 with one weak 22-28 bucket in
both periods). Flat `mu/var` means the Kelly-consistent rule is *constant* exposure when
on: the ramp (exposure rising with VIX) over-bets the high-variance days, and a vol
target (exposure falling with sigma) under-bets them. That is exactly what the tables
show: the binary gate is the Sharpe-maximiser (IS 1.02), the vol target gives up a little
Sharpe versus it (IS 0.92-0.95) in exchange for a much smaller tail, and the ramp is the
worst of the three (IS 0.79) *and* has the fattest tail. The 14-18 bucket flipping from
+5.9 to -9.2 bp confirms the gate at 18 (reversal.md) and is why the gate is kept.

Paired stationary block bootstrap (block 10, 2000 draws) of Sharpe(variant) - Sharpe(ramp),
sleeve ex-cash:

| variant | IS dSharpe [95% CI], P(>0) | OOS dSharpe [95% CI] | full dSharpe [95% CI], P(>0) |
|---|---|---|---|
| binary gate VIX > 18 | +0.24 [-0.00, +0.50], 0.97 | -0.00 [-0.48, +0.46] | +0.17 [-0.04, +0.39], 0.94 |
| vt_ew 0.06 | +0.16 [-0.20, +0.55], 0.80 | -0.02 [-0.66, +0.62] | +0.11 [-0.22, +0.45], 0.75 |
| vt_ew 0.08 | +0.14 [-0.24, +0.53], 0.77 | -0.05 [-0.71, +0.58] | +0.08 [-0.24, +0.41], 0.69 |
| vt_own 0.10 | +0.12 [-0.26, +0.49], 0.74 | -0.02 [-0.55, +0.54] | +0.08 [-0.21, +0.36], 0.69 |
| ramp cap 0.5 | +0.09 [-0.03, +0.22], 0.93 | +0.01 [-0.17, +0.18] | +0.07 [-0.04, +0.17], 0.90 |
| ramp + ivol | +0.02 [-0.05, +0.10], 0.73 | +0.04 [-0.11, +0.25] | +0.03 [-0.04, +0.11], 0.79 |

Yearly sleeve Sharpe (ex-cash): the ramp's OOS parity is one year - 2022 (ramp 1.09,
binary 0.73, vt 0.58; the ramp was fully exposed through the VIX 28-35 months and 2022
paid +18%) - against 2023-25 where binary / vt were as good or better (2023 1.30 / 1.43 /
1.36; 2024 1.59 / 1.60 / 1.71; 2025 0.71 / 0.94 / 0.74). In-sample the vt variants lose
in 2011, 2014, 2020 (crash years the ramp was sized into) and win in 2010, 2013, 2015,
2016, 2019, 2021. Exposure correlates +0.23 with the book's |return| under the ramp and
-0.21 under the vol target - the sign flip is the whole point.

### 1c. Joint sizing x allocation (27 trials; IS chooses, OOS confirms)

With the sleeve's vol cut roughly in half, the IS max-Sharpe allocation (w proportional
to S/vol) rises from 0.46 (live ramp, section 4) to ~0.9. Growth ensemble, T-bill cash:

| variant | Sharpe (IS / OOS) | ex-cash | CAGR | Vol | MaxDD | kurt | avg expo |
|---|---|---|---|---|---|---|---|
| live: ramp, eq, alloc 0.5 | 1.324 (1.22 / 1.56) | 1.362 | 11.6% | 7.4% | -12.2% | 10.6 | 0.167 |
| vt_ew 0.05 eq alloc 0.75 | 1.366 (1.28 / 1.56) | 1.410 | 11.0% | 6.7% | -11.5% | 11.4 | 0.175 |
| vt_ew 0.05 eq alloc 1.0 | 1.383 (1.31 / 1.55) | 1.425 | 12.1% | 7.4% | -11.2% | 8.9 | 0.194 |
| vt_ew 0.06 eq alloc 0.75 | 1.379 (1.30 / 1.55) | 1.422 | 11.6% | 7.1% | -11.4% | 9.8 | 0.186 |
| vt_ew 0.06 eq alloc 1.0 | 1.386 (1.33 / 1.52) | 1.426 | 12.9% | 7.9% | -10.8% | 7.6 | 0.209 |
| vt_ew 0.08 eq alloc 0.75 | 1.368 (1.31 / 1.50) | 1.408 | 12.7% | 7.9% | -10.8% | 7.6 | 0.207 |
| vt_ew 0.08 eq alloc 1.0 | 1.338 (1.30 / 1.42) | 1.374 | 14.2% | 9.1% | -12.2% | 6.4 | 0.237 |
| vt_ew 0.05 ivol alloc 0.75 | 1.369 (1.26 / 1.62) | 1.414 | 10.9% | 6.6% | -11.4% | 12.1 | 0.175 |
| vt_ew 0.05 ivol alloc 1.0 | 1.395 (1.29 / 1.63) | 1.438 | 11.9% | 7.2% | -11.0% | 9.7 | 0.194 |
| vt_ew 0.06 ivol alloc 0.75 | 1.388 (1.28 / 1.63) | 1.431 | 11.5% | 7.0% | -11.2% | 10.5 | 0.186 |
| **vt_ew 0.06 ivol alloc 1.0** | **1.399 (1.31 / 1.62)** | 1.440 | 12.7% | 7.7% | -10.7% | 8.4 | 0.209 |
| vt_ew 0.08 ivol alloc 0.75 | 1.379 (1.29 / 1.59) | 1.420 | 12.4% | 7.6% | -10.7% | 8.4 | 0.207 |
| vt_ew 0.08 ivol alloc 1.0 | 1.360 (1.29 / 1.52) | 1.398 | 13.9% | 8.8% | -11.9% | 6.9 | 0.237 |
| binary gate eq alloc 0.4 | 1.421 (1.37 / 1.54) | 1.461 | 12.9% | 7.7% | -11.6% | 7.5 | 0.197 |
| binary gate ivol alloc 0.4 | 1.434 (1.36 / 1.60) | 1.476 | 12.7% | 7.5% | -11.4% | 8.2 | 0.197 |
| binary gate eq alloc 0.5 | 1.412 (1.38 / 1.50) | 1.449 | 14.1% | 8.6% | -11.3% | 6.5 | 0.217 |
| binary gate ivol alloc 0.5 | 1.431 (1.37 / 1.57) | 1.470 | 13.9% | 8.3% | -11.1% | 7.1 | 0.217 |
| ramp span 5 eq (= cap 0.5 @ 1.0) | 1.352 (1.27 / 1.55) | 1.390 | 12.6% | 7.9% | -12.4% | 8.4 | 0.185 |
| ramp span 5 ivol | 1.366 (1.27 / 1.59) | 1.405 | 12.4% | 7.7% | -12.3% | 8.9 | 0.185 |
| vt_ew 0.06 ivol 1.0, throttle off | 1.406 (1.32 / 1.62) | 1.447 | 12.8% | 7.7% | -10.7% | 8.3 | 0.209 |
| vt_ew 0.06 ivol 1.0, throttle 5% / 0.5 | 1.430 (1.34 / 1.65) | 1.471 | 12.5% | 7.4% | -8.7% | 9.2 | 0.202 |
| vt_ew 0.06 eq 1.0, throttle off | 1.389 (1.33 / 1.52) | 1.429 | 13.0% | 7.9% | -10.8% | 7.6 | 0.209 |
| vt_ew 0.06 ivol 1.0, sigma window 10 | 1.402 (1.30 / 1.65) | 1.443 | 12.9% | 7.8% | -12.0% | 8.4 | 0.212 |
| vt_ew 0.06 ivol 1.0, window 40 | 1.383 (1.31 / 1.56) | 1.424 | 12.5% | 7.7% | -10.8% | 8.2 | 0.208 |
| vt_ew 0.06 ivol 1.0, window 60 | 1.380 (1.30 / 1.58) | 1.420 | 12.7% | 7.8% | -10.7% | 7.9 | 0.208 |
| vt_own 0.08 ivol 1.0 | 1.361 (1.26 / 1.59) | 1.400 | 13.2% | 8.3% | -10.5% | 7.0 | 0.223 |
| vt_own 0.10 ivol 1.0 | 1.328 (1.25 / 1.51) | 1.364 | 14.2% | 9.2% | -11.9% | 6.2 | 0.247 |

Product `alloc x target` sets the dollar scale (IS optimum ~0.05-0.06 of equity per unit of
sigma), `alloc` sets the cap; 0.06 @ 1.0 and 0.08 @ 0.75 are the same book except on
low-sigma days. The binary gate at 0.4 is the IS maximum (1.37) and matches the vol target
OOS (1.60 vs 1.62); it is not recommended because it flips the whole book on a 0.1 VIX
move (the design flaw reversal.md's ramp was built to avoid), holds a constant 0.4 of
equity in 7 stocks on a VIX-80 morning (vt holds ~0.12), and its sleeve worst day is
-5.6% at unit exposure vs -2.6%. Equal vs inverse-vol names: ivol is +0.01-0.03 full,
-0.02 IS, +0.10 OOS - kept, as in reversal.md.

### 1d. Gate smoothing and one-at-a-time sensitivity around the candidate (20 trials)

| variant | Sharpe (IS / OOS) | CAGR | Vol | MaxDD | kurt | avg expo | cost/yr |
|---|---|---|---|---|---|---|---|
| live growth | 1.324 (1.22 / 1.56) | 11.6% | 7.4% | -12.2% | 10.6 | 0.167 | 2.83% |
| vt_ew 0.06, ivol, alloc 1.0 (gate cliff at 18) | 1.399 (1.31 / 1.62) | 12.7% | 7.7% | -10.7% | 8.4 | 0.209 | 3.90% |
| same, gate ramp 18 -> 19 | 1.388 (1.28 / 1.63) | 12.3% | 7.5% | -10.7% | 8.7 | 0.200 | 3.66% |
| **same, gate ramp 18 -> 20 (RECOMMENDED)** | **1.404 (1.29 / 1.68)** | 12.1% | 7.3% | -10.9% | 9.4 | 0.191 | 3.45% |
| same, gate ramp 18 -> 22 | 1.352 (1.23 / 1.65) | 11.3% | 7.0% | -11.8% | 10.5 | 0.179 | 3.14% |
| target 0.04 | 1.378 (1.27 / 1.63) | 11.1% | 6.7% | -11.3% | 11.5 | 0.178 | 3.13% |
| target 0.05 | 1.395 (1.29 / 1.63) | 11.9% | 7.2% | -11.0% | 9.7 | 0.194 | 3.51% |
| target 0.07 | 1.395 (1.31 / 1.60) | 13.5% | 8.2% | -10.7% | 7.5 | 0.224 | 4.27% |
| target 0.08 | 1.360 (1.29 / 1.52) | 13.9% | 8.8% | -11.9% | 6.9 | 0.237 | 4.61% |
| target 0.10 | 1.303 (1.27 / 1.38) | 14.6% | 9.7% | -14.8% | 6.0 | 0.259 | 5.16% |
| reversal alloc 0.5 | 1.341 (1.22 / 1.61) | 10.3% | 6.4% | -11.5% | 13.9 | 0.163 | 2.74% |
| reversal alloc 0.75 | 1.388 (1.28 / 1.63) | 11.5% | 7.0% | -11.2% | 10.5 | 0.186 | 3.32% |
| reversal alloc 0.9 | 1.398 (1.30 / 1.62) | 12.2% | 7.4% | -10.9% | 9.1 | 0.200 | 3.67% |
| VIX gate 16 | 1.304 (1.44 / **1.03**) | 12.7% | 8.3% | -14.0% | 6.8 | 0.262 | 5.24% |
| VIX gate 20 | 1.360 (1.25 / 1.61) | 11.6% | 7.1% | -11.9% | 10.1 | 0.178 | 3.11% |
| VIX gate 22 | 1.184 (1.04 / 1.50) | 9.7% | 6.8% | -12.4% | 12.0 | 0.158 | 2.60% |
| eq names instead of ivol | 1.386 (1.33 / 1.52) | 12.9% | 7.9% | -10.8% | 7.6 | 0.209 | 3.90% |
| regime multiplier OFF | 1.363 (1.26 / 1.59) | 14.2% | 9.0% | **-20.5%** | 9.8 | 0.226 | 4.11% |
| throttle OFF | 1.406 (1.32 / 1.62) | 12.8% | 7.7% | -10.7% | 8.3 | 0.209 | 3.90% |
| throttle 5% / 0.5 | 1.430 (1.34 / 1.65) | 12.5% | 7.4% | -8.7% | 9.2 | 0.202 | 3.76% |
| throttle 15% / 0.5 | 1.406 (1.32 / 1.62) | 12.8% | 7.7% | -10.7% | 8.3 | 0.209 | 3.90% |
| QQQ instead of QLD in the overnight slot | 1.386 (1.29 / 1.60) | 11.1% | 6.7% | -8.5% | 7.0 | 0.209 | 3.49% |

Smooth everywhere except the two things the reversal note already flagged as cliffs (the
VIX gate: 16 is an IS-only mirage with OOS 1.03, the 14-18 bucket having flipped; 22
throws away the 18-22 bucket) - both are the sleeve's own parameters and were not
re-tuned. Target 0.04-0.07 and alloc 0.75-1.0 are a plateau (1.38-1.40); sigma window
10-60 is flat. The 18 -> 20 gate ramp is adopted for the operational reason (no cliff)
and because it is the most cost-robust of the vt variants (1e); its IS/OOS numbers are
within noise of the cliff version (18 -> 19 and the cliff are the same; 18 -> 22 starts to
look like the old ramp again).

### 1e. Cost robustness (the one real cost of the change)

Per-side cost on stocks varied (ETFs at their defaults); sleeve ex-cash / ensemble excess
Sharpe. BE = per-side cost at which the sleeve's mean net trading P&L is zero.

| candidate | 2.5 bp: sleeve / ens (IS / OOS) | 4.0 bp | 5.0 bp | 7.5 bp | sleeve BE bp/side |
|---|---|---|---|---|---|
| live ramp eq @0.5 | 0.77 / 1.32 (1.22 / 1.56) | 0.61 / 1.22 (1.12 / 1.46) | 0.51 / 1.16 (1.05 / 1.39) | 0.24 / 0.99 (0.89 / 1.21) | 9.7 |
| ramp ivol @0.5 | 0.80 / 1.34 (1.23 / 1.60) | 0.63 / 1.24 (1.13 / 1.49) | 0.52 / 1.17 (1.06 / 1.42) | 0.23 / 1.00 (0.89 / 1.23) | 9.5 |
| ramp span 5 ivol @1.0 | 0.86 / 1.37 (1.27 / 1.59) | 0.66 / 1.23 (1.14 / 1.44) | 0.52 / 1.14 (1.06 / 1.35) | 0.18 / 0.92 (0.84 / 1.10) | 8.8 |
| vt 0.06 ivol @1.0, gate cliff | 0.91 / 1.40 (1.31 / 1.62) | 0.63 / 1.22 (1.13 / 1.42) | 0.44 / 1.10 (1.02 / 1.30) | -0.03 / 0.80 (0.73 / 0.97) | 7.3 |
| **vt 0.06 ivol @1.0, gate ramp 18->20** | 0.92 / 1.40 (1.29 / 1.68) | 0.66 / 1.25 (1.14 / 1.52) | 0.49 / 1.15 (1.04 / 1.41) | 0.06 / 0.90 (0.79 / 1.13) | 7.9 |
| vt 0.06 ivol @1.0, gate 20 | 0.84 / 1.36 (1.25 / 1.61) | 0.62 / 1.23 (1.13 / 1.48) | 0.48 / 1.15 (1.04 / 1.40) | 0.11 / 0.94 (0.84 / 1.18) | 8.3 |
| binary ivol @0.4 | 0.97 / 1.43 (1.36 / 1.60) | 0.71 / 1.28 (1.21 / 1.42) | 0.54 / 1.17 (1.11 / 1.31) | 0.11 / 0.90 (0.86 / 1.01) | 8.1 |

The vol target moves exposure from the crash days (gross 25-75 bp/day, where 5 bp of cost
is irrelevant) to the ordinary VIX 18-25 days (gross ~15 bp/day), so it is more
cost-sensitive: breakeven 7.9 vs 9.7 bp, and the ensemble's edge over the live profile
is +0.08 at 2.5 bp, +0.03 at 4 bp, -0.01 at 5 bp, -0.09 at 7.5 bp. Both breakevens are
> 3x the assumed cost; the round-3 gate for new sleeves is 2x. The trade turns ~7.2
names/day (0.77 turnover/day for the ensemble vs 0.67), cost drag 3.45%/yr vs 2.83%.
Decision rule for the orchestrator: adopt at 2.5 bp; if paper fills on the mega-cap MOO
orders come in above ~4 bp/side effective, revert the sizing to the ramp (keep ivol).

## 2. Ensemble-level vol targeting (task 2, 34 trials) - negative

Whole book scaled by `min(1, (target / RV)^power)`, RV = trailing realised vol of the
pre-throttle book's own daily returns (20d / 60d, through the previous close, applied from
the 16:00 row), power 1 = target-vol, power 2 = Moreira-Muir. Live throttle on unless
stated. `hf_risk.ensemble_vol_scale`.

| variant | Sharpe (IS / OOS) | ex-cash (IS / OOS) | CAGR | Vol | MaxDD | MaxDD OOS | kurt | avg expo |
|---|---|---|---|---|---|---|---|---|
| **growth (live), no VT** | **1.324 (1.22 / 1.56)** | 1.362 (1.23 / 1.66) | 11.6% | 7.4% | -12.2% | -9.6% | 10.6 | 0.167 |
| VT p1 20d target 4% | 1.269 (1.18 / 1.49) | 1.308 (1.19 / 1.59) | 7.6% | 4.7% | -6.5% | -3.4% | 15.3 | 0.111 |
| VT p1 20d 5% | 1.267 (1.16 / 1.50) | 1.308 (1.18 / 1.60) | 8.5% | 5.4% | -7.0% | -4.3% | 14.0 | 0.128 |
| VT p1 20d 6% | 1.269 (1.15 / 1.53) | 1.310 (1.17 / 1.63) | 9.2% | 5.9% | -7.9% | -5.1% | 12.9 | 0.139 |
| VT p1 20d 7% | 1.271 (1.14 / 1.56) | 1.313 (1.16 / 1.66) | 9.7% | 6.3% | -8.9% | -6.0% | 12.2 | 0.147 |
| VT p1 20d 8% | 1.287 (1.16 / 1.57) | 1.328 (1.17 / 1.67) | 10.2% | 6.6% | -9.7% | -6.8% | 11.6 | 0.153 |
| VT p1 20d 10% | 1.310 (1.19 / 1.58) | 1.350 (1.20 / 1.68) | 10.9% | 6.9% | -10.8% | -8.0% | 11.0 | 0.160 |
| VT p1 60d 4% | 1.250 (1.15 / 1.50) | 1.288 (1.16 / 1.59) | 7.2% | 4.5% | -7.7% | -4.0% | 18.6 | 0.104 |
| VT p1 60d 5% | 1.243 (1.12 / 1.53) | 1.283 (1.14 / 1.63) | 8.3% | 5.3% | -9.2% | -5.0% | 16.3 | 0.124 |
| VT p1 60d 6% | 1.271 (1.14 / 1.57) | 1.311 (1.16 / 1.66) | 9.3% | 6.0% | -10.3% | -6.1% | 14.8 | 0.138 |
| VT p1 60d 7% | 1.301 (1.18 / 1.56) | 1.341 (1.20 / 1.66) | 10.1% | 6.4% | -10.8% | -7.1% | 12.7 | 0.148 |
| VT p1 60d 8% | 1.314 (1.21 / 1.55) | 1.354 (1.22 / 1.65) | 10.6% | 6.7% | -11.4% | -8.0% | 11.6 | 0.155 |
| VT p1 60d 10% | 1.314 (1.21 / 1.55) | 1.354 (1.22 / 1.65) | 11.2% | 7.1% | -12.2% | -9.1% | 10.9 | 0.162 |
| MM p2 20d 5% | 1.166 (1.09 / 1.35) | 1.204 (1.10 / 1.45) | 7.0% | 4.7% | -6.8% | -3.2% | 20.0 | 0.107 |
| MM p2 20d 6% | 1.183 (1.08 / 1.42) | 1.223 (1.09 / 1.52) | 7.9% | 5.3% | -7.4% | -3.6% | 16.8 | 0.124 |
| MM p2 20d 7% | 1.194 (1.05 / 1.51) | 1.236 (1.07 / 1.61) | 8.6% | 5.8% | -8.9% | -4.2% | 14.8 | 0.136 |
| MM p2 20d 8% | 1.229 (1.09 / 1.54) | 1.271 (1.10 / 1.64) | 9.3% | 6.2% | -9.1% | -5.2% | 13.4 | 0.145 |
| MM p2 20d 10% | 1.284 (1.16 / 1.57) | 1.325 (1.17 / 1.67) | 10.4% | 6.7% | -9.8% | -6.9% | 11.9 | 0.155 |
| MM p2 60d 5% | 1.104 (0.98 / 1.41) | 1.140 (1.00 / 1.50) | 6.5% | 4.4% | -7.4% | -2.7% | 25.6 | 0.099 |
| MM p2 60d 6% | 1.177 (1.03 / 1.52) | 1.216 (1.04 / 1.62) | 7.9% | 5.3% | -9.0% | -4.0% | 21.2 | 0.121 |
| MM p2 60d 7% | 1.253 (1.13 / 1.54) | 1.293 (1.14 / 1.64) | 9.1% | 5.9% | -9.8% | -5.3% | 15.8 | 0.136 |
| MM p2 60d 8% | 1.288 (1.18 / 1.53) | 1.329 (1.19 / 1.63) | 10.0% | 6.4% | -10.7% | -6.9% | 13.2 | 0.147 |
| MM p2 60d 10% | 1.299 (1.19 / 1.54) | 1.339 (1.20 / 1.64) | 10.8% | 7.0% | -12.2% | -8.6% | 11.5 | 0.159 |
| VT p1 20d 5%, throttle off | 1.276 (1.18 / 1.50) | 1.317 (1.19 / 1.60) | 8.5% | 5.4% | -6.8% | -4.3% | 13.9 | 0.128 |
| VT p1 20d 6%, throttle off | 1.278 (1.17 / 1.53) | 1.319 (1.18 / 1.63) | 9.2% | 5.9% | -7.7% | -5.1% | 12.9 | 0.140 |
| VT p1 20d 8%, throttle off | 1.295 (1.17 / 1.57) | 1.337 (1.19 / 1.67) | 10.3% | 6.6% | -9.2% | -6.8% | 11.5 | 0.154 |
| VT p1 60d 5%, throttle off | 1.250 (1.13 / 1.53) | 1.289 (1.15 / 1.63) | 8.3% | 5.3% | -9.0% | -5.0% | 16.2 | 0.124 |
| VT p1 60d 6%, throttle off | 1.278 (1.15 / 1.57) | 1.318 (1.17 / 1.66) | 9.4% | 6.0% | -10.1% | -6.1% | 14.7 | 0.139 |
| VT p1 60d 8%, throttle off | 1.321 (1.22 / 1.55) | 1.361 (1.23 / 1.65) | 10.7% | 6.8% | -11.1% | -8.0% | 11.5 | 0.156 |
| MM p2 20d 6%, throttle off | 1.191 (1.09 / 1.42) | 1.232 (1.10 / 1.52) | 8.0% | 5.3% | -7.4% | -3.6% | 16.7 | 0.124 |
| MM p2 20d 8%, throttle off | 1.238 (1.10 / 1.54) | 1.280 (1.12 / 1.64) | 9.4% | 6.2% | -9.1% | -5.2% | 13.3 | 0.145 |
| VT p1 20d 6%, reversal alloc 1.0 | 1.206 (1.07 / 1.52) | 1.245 (1.08 / 1.62) | 9.4% | 6.4% | -8.9% | -5.6% | 12.9 | 0.149 |
| VT p1 20d 8%, reversal alloc 1.0 | 1.190 (1.06 / 1.49) | 1.229 (1.07 / 1.58) | 10.4% | 7.3% | -10.5% | -6.9% | 11.3 | 0.169 |
| (reversal alloc 1.0, no VT) | 1.212 (1.13 / 1.40) | 1.241 (1.14 / 1.47) | 15.1% | 10.8% | -12.2% | -10.2% | 14.6 | 0.216 |

**No variant beats the untouched book in-sample or OOS.** Target-vol costs 0.01-0.08
Sharpe and the Moreira-Muir form 0.03-0.22; both *raise* kurtosis (the scaling removes
ordinary-vol days and leaves the jump days). The reason is the same as in section 1: the
book's realised vol is high exactly when the reversal sleeve is active and earning its
best returns, and the overnight sleeve is already scaled by the regime multiplier, so
ensemble-level scaling only de-risks the good days. MM works on unconditioned beta
(regime.md); it does not work on an already-conditioned book. It does what it says on
MaxDD (-12% -> -6.5% at 4%) at a proportional CAGR cost - a leverage choice, not a Sharpe
tool. Not recommended.

## 3. Drawdown throttle (task 3, 9 trials) - inert

Growth ensemble, throttle on the book's own causal drawdown:

| variant | Sharpe (IS / OOS) | ex-cash (IS / OOS) | CAGR | Vol | MaxDD | MaxDD OOS | avg expo |
|---|---|---|---|---|---|---|---|
| **off** | 1.332 (1.23 / 1.56) | 1.371 (1.24 / 1.66) | 11.72% | 7.43% | -11.76% | -9.6% | 0.167 |
| level 5% x0.5 | 1.320 (1.22 / 1.55) | 1.359 (1.23 / 1.64) | 11.15% | 7.09% | -9.33% | -8.5% | 0.163 |
| level 5% x0.25 | 1.298 (1.20 / 1.53) | 1.336 (1.21 / 1.62) | 10.86% | 7.00% | -9.45% | -8.0% | 0.161 |
| level 5% flat | 1.264 (1.16 / 1.50) | 1.303 (1.17 / 1.60) | 10.57% | 6.97% | -10.50% | -8.2% | 0.158 |
| **level 10% x0.5 (live)** | 1.324 (1.22 / 1.56) | 1.362 (1.23 / 1.66) | 11.64% | 7.41% | -12.19% | -9.6% | 0.167 |
| level 10% x0.25 | 1.319 (1.21 / 1.56) | 1.358 (1.22 / 1.66) | 11.59% | 7.40% | -12.40% | -9.6% | 0.166 |
| level 10% flat | 1.314 (1.20 / 1.56) | 1.352 (1.22 / 1.66) | 11.54% | 7.40% | -12.65% | -9.6% | 0.166 |
| level 15% x0.5 | 1.332 (1.23 / 1.56) | 1.371 (1.24 / 1.66) | 11.72% | 7.43% | -11.76% | -9.6% | 0.167 |
| level 15% x0.25 | 1.332 (1.23 / 1.56) | 1.371 (1.24 / 1.66) | 11.72% | 7.43% | -11.76% | -9.6% | 0.167 |

The live 10%/0.5 throttle is worth -0.008 Sharpe (ex-cash -0.009) and -0.08 pp CAGR and
makes MaxDD *worse* (-12.19% vs -11.76% off) because it halves exposure during the
recovery from the one drawdown that triggered it (2019, 98 sessions; REDTEAM 6). 15% never
triggers. 5% triggers on 6% of sessions (2019 54%, 2020 11%, 2026 42%), cuts MaxDD to
-9.3% for -0.004 Sharpe and -0.5 pp CAGR - a drawdown dial, not a Sharpe source. In the
recommended configuration the 10% throttle triggers on a handful of sessions (MaxDD is
-10.9%) and is worth -0.002; 5%/0.5 there shows +0.03 Sharpe and MaxDD -8.7%, but the
gain comes from the same three episodes (2019, 2020, 2026) and the identical change was
-0.004 in the live configuration - not robust, not adopted. Verdict: the throttle does not
add Sharpe; keep 10%/0.5 as the inert circuit-breaker REDTEAM wanted, or switch it off
(+0.008) - immaterial either way.

## 4. Allocation between the live sleeves (task 4, 8 trials)

Sleeve excess daily returns as they enter the ensemble (overnight incl. QLD slot and the
live regime multiplier; reversal with the live ramp), 2010-03 ->, T-bill cash:

| sleeve | Sharpe (IS / OOS) | vol | mean bp/day | kurt | worst |
|---|---|---|---|---|---|
| overnight x regime | 1.090 (0.951 / 1.394) | 5.8% | 2.5 | 19.4 | -3.8% |
| reversal (ramp) | 0.765 (0.778 / 0.735) | 9.3% | 2.8 | 29.8 | -4.9% |

Correlation -0.006 (OOS -0.008). Naive bound sqrt(1.09^2 + 0.765^2) = **1.331 (IS 1.228 /
OOS 1.576)**; the live ensemble at 1.324 is on the bound. IS tangency weights (all three
methods agree to 3 decimals because the correlation is zero): overnight 0.685 / reversal
0.315 = **reversal / overnight ratio 0.46** - the live 0.5 is the optimum.

| reversal alloc (overnight 1.0) | Sharpe (IS / OOS) | CAGR | Vol | MaxDD | kurt | avg expo |
|---|---|---|---|---|---|---|
| 0.25 | 1.284 (1.16 / 1.57) | 9.7% | 6.2% | -12.3% | 14.6 | 0.142 |
| 0.46 (IS Sharpe/vol ratio) | 1.322 (1.21 / 1.57) | 11.3% | 7.2% | -12.2% | 10.7 | 0.162 |
| 0.46 (IS mean-variance) | 1.322 (1.21 / 1.57) | 11.3% | 7.2% | -12.2% | 10.7 | 0.163 |
| **0.50 (live)** | **1.324 (1.22 / 1.56)** | 11.6% | 7.4% | -12.2% | 10.6 | 0.167 |
| 0.75 | 1.278 (1.19 / 1.49) | 13.4% | 9.0% | -12.4% | 12.3 | 0.192 |
| 1.00 | 1.212 (1.13 / 1.40) | 15.1% | 10.8% | -12.2% | 14.6 | 0.216 |
| overnight 0.75 / reversal 1.0 | 1.148 (1.09 / 1.29) | 13.4% | 10.2% | -11.1% | 18.2 | 0.188 |
| overnight 0.5 / reversal 1.0 | 1.047 (1.00 / 1.15) | 11.7% | 9.6% | -11.1% | 22.5 | 0.158 |

"Both could be 1.0 under the cash cap" is true but not Sharpe-optimal for the *ramp-sized*
sleeve: its vol is 1.6x the overnight sleeve's for 0.7x the Sharpe, so it should get ~half
the capital, which it does. The allocation only moves once the sleeve is re-sized (1c):
with the vol target the sleeve's vol halves and the tangency ratio becomes ~0.9-1.0.

## 5. Regime multiplier on the overnight sleeve (task 5, 78 trials)

Reproduction of regime.md 3a (overnight sleeve *without* QLD, ex-cash): published 1.13
(0.94 / 1.52), CAGR 6.9%, MaxDD -17.3% (note: 1.11 (0.94 / 1.46), 6.8%, -17%); x multiplier
1.16 (0.96 / 1.56), 5.3%, -9.9% (note: 1.13 (0.96 / 1.48), 5.2%, -10%); flat 4% cash, excess
Sharpe 0.98 -> 0.99 (note 0.96 -> 0.96). Mean multiplier 0.747 (IS 0.793 / OOS 0.630), 1.0
on 49% of days, < 0.5 on 25% (note: 0.75 / 0.79 / 0.63, 49%, 25%). Reproduced to the
precision the later data end allows.

Grid on the live sleeve (QLD in the QQQ slot). `sleeve` = overnight(QLD) x mult ex-cash,
`ens` = growth ensemble with that multiplier. T = trend_off_mult, floor = min_mult.

| variant | mean mult | sleeve (IS / OOS) | slv CAGR | slv DD | ensemble (IS / OOS) | ens CAGR | ens DD |
|---|---|---|---|---|---|---|---|
| regime OFF | 1.00 | 1.113 (0.94 / 1.47) | 8.9% | -24.3% | 1.295 (1.19 / 1.54) | 13.1% | **-22.3%** |
| **live (0.16, p2, T0.5, floor 0.1)** | 0.75 | 1.158 (0.99 / 1.50) | 6.9% | -12.7% | **1.324 (1.22 / 1.56)** | 11.6% | -12.2% |
| best IS: ref 0.25 p1 T0 floor 0 | 0.85 | 1.194 (1.13 / 1.33) | 8.8% | -14.8% | 1.352 (1.33 / 1.42) | 13.3% | -13.5% |
| best full: ref 0.12 p1 T0 floor 0 | 0.67 | 1.195 (1.07 / 1.48) | 6.5% | -12.4% | 1.347 (1.27 / 1.53) | 11.3% | -11.9% |
| best OOS: ref 0.12 p2 T1 floor 0.x | 0.59 | 1.150 (0.94 / 1.70) | 5.2% | -10.9% | 1.302 (1.18 / 1.61) | 10.1% | -10.0% |
| worst: ref 0.20 p2 T0 floor 0.25 | 0.84 | 1.124 (0.98 / 1.41) | 7.7% | -14.7% | 1.277 (1.19 / 1.48) | 12.0% | -16.0% |
| defaults + VIX term structure | 0.74 | 1.103 (0.94 / 1.44) | 6.4% | -12.9% | 1.282 (1.18 / 1.51) | 11.1% | -11.8% |
| defaults, vol_window 10 | 0.75 | 1.075 (0.92 / 1.40) | 6.4% | -10.9% | 1.264 (1.17 / 1.47) | 11.2% | -10.8% |
| defaults, vol_window 30 | 0.75 | 1.100 (0.92 / 1.50) | 6.8% | -14.7% | 1.267 (1.14 / 1.56) | 11.3% | -14.6% |
| defaults, vol_ticker SPY | 0.84 | 1.124 (0.99 / 1.40) | 8.0% | -14.5% | 1.279 (1.19 / 1.48) | 12.4% | -14.2% |

Full 72-point grid (vol_ref x vol_power x trend_off_mult x min_mult) in Appendix A. Range
of the ensemble Sharpe across all 72 combinations: **1.277-1.352**, i.e. +-0.04 around the
live 1.324; IS 1.17-1.33, OOS 1.42-1.63, and the IS and OOS rankings are anti-correlated
(the IS-best has the worst OOS and vice versa - lower vol_ref / higher power buys OOS at
IS cost). Answer to the question asked: on the *conditioned* overnight sleeve the
multiplier adds +0.03-0.05 ex-cash Sharpe (sleeve 1.11 -> 1.16, ensemble 1.30 -> 1.32) and
halves MaxDD (-22% -> -12%) for -1.5 pp CAGR; it is a drawdown controller with a small
positive Sharpe effect, exactly as regime.md said. Within the grid, power 1 edges power 2
by 0.01-0.03 in this sleeve-level context (not on unconditioned beta), the floor is
irrelevant, and trend_off_mult 0 vs 1 trades IS for OOS. Nothing here is distinguishable
from noise after 78 trials; the live defaults are mid-plateau and are kept.

## 6. Combination tool (task 6) - the orchestrator's table

`hf_risk.combination_report(series, rf_daily, split, how)` returns per-series Sharpe
(full / IS / OOS), the pairwise correlation matrix, the naive bound `sqrt(sum S_i^2)`, and
one row per combination rule with IS-fitted weights (gross 1) and the realised IS / OOS /
full Sharpe: `max_sharpe_noshort` (min w'Sw s.t. mu'w = 1, w >= 0; QP via SLSQP),
`max_sharpe_unconstrained` (S^-1 mu), `sharpe_over_vol` (w proportional to S_i / vol_i, the
uncorrelated-streams optimum), `inverse_vol` (equal risk), `equal_weight`. Inputs are
excess daily returns (`rf_daily`/252 subtracted); `how="inner"` uses common dates,
`how="zero"` treats missing days as flat. Run on everything in `/tmp/qb_shared` at the
time of writing (2026-09-16 15:35): `overnight`, `reversal` (reference CSV),
`overnight_alt`, `xs_overnight`, `ts_reversal`. No `intl_intraday` file existed.

Per-sleeve (align = zero, 2010-02 ->, 4179 days; inner alignment from 2011-01 gives the same
picture, overnight 1.09 / reversal 0.70 / bound 2.25):

| sleeve | Sharpe | IS | OOS | vol | mean bp/day | kurt | worst |
|---|---|---|---|---|---|---|---|
| overnight | 1.05 | 0.89 | 1.39 | 5.9% | 2.5 | 24.4 | -5.2% |
| reversal | 0.76 | 0.77 | 0.73 | 9.3% | 2.8 | 29.9 | -4.9% |
| overnight_alt | 0.63 | 0.81 | **0.44** | 8.1% | 2.0 | 19.7 | -5.4% |
| ts_reversal | 0.89 | 0.86 | 0.97 | 8.7% | 3.1 | 23.1 | -4.9% |
| xs_overnight | 1.43 | 1.68 | 1.01 | 14.6% | 8.3 | 10.2 | -8.4% |
| reversal_vt (this note's sizing) | 0.91 | 0.91 | 0.90 | 4.3% | 1.5 | 14.5 | -2.6% |

Correlation of daily excess returns (full; OOS in brackets where it differs by > 0.05):

| | overnight | reversal | overnight_alt | ts_reversal | xs_overnight |
|---|---|---|---|---|---|
| overnight | 1 | 0.00 | 0.04 | 0.16 | **0.50** |
| reversal | 0.00 | 1 | 0.00 | **0.43 (0.50)** | 0.00 |
| overnight_alt | 0.04 | 0.00 | 1 | 0.02 | 0.01 |
| ts_reversal | 0.16 | 0.43 | 0.02 | 1 | 0.12 |
| xs_overnight | 0.50 | 0.00 | 0.01 | 0.12 | 1 |

Naive bound (all five): full **2.22**, IS 2.37, OOS 2.15. Two live sleeves only: 1.30 (IS
1.19 / OOS 1.57).

| rule (weights fitted IS, gross 1) | IS | OOS | full | w overnight | w reversal | w overnight_alt | w ts_reversal | w xs_overnight |
|---|---|---|---|---|---|---|---|---|
| max_sharpe_noshort | 2.06 | **1.32** | 1.77 | 0.01 | 0.18 | 0.34 | 0.14 | 0.33 |
| max_sharpe_unconstrained | 2.06 | 1.32 | 1.77 | 0.01 | 0.18 | 0.34 | 0.14 | 0.33 |
| sharpe_over_vol | 1.95 | 1.57 | 1.80 | 0.27 | 0.14 | 0.21 | 0.17 | 0.21 |
| inverse_vol | 1.84 | 1.59 | 1.74 | 0.29 | 0.17 | 0.24 | 0.19 | 0.12 |
| equal_weight | 1.94 | 1.56 | 1.80 | 0.20 | 0.20 | 0.20 | 0.20 | 0.20 |
| *two live sleeves, max-Sharpe (0.66 / 0.34)* | 1.18 | 1.57 | 1.30 | | | | | |

Same with `reversal_vt` in place of `reversal`:

| rule | IS | OOS | full | w overnight | w overnight_alt | w ts_reversal | w xs_overnight | w reversal_vt |
|---|---|---|---|---|---|---|---|---|
| max_sharpe_noshort | 2.09 | 1.38 | 1.82 | 0.00 | 0.27 | 0.10 | 0.26 | 0.37 |
| sharpe_over_vol | 1.99 | 1.63 | 1.84 | 0.22 | 0.17 | 0.14 | 0.17 | 0.29 |
| inverse_vol | 1.88 | 1.65 | 1.79 | 0.24 | 0.20 | 0.16 | 0.10 | 0.30 |
| equal_weight | 1.98 | 1.57 | 1.82 | 0.20 | 0.20 | 0.20 | 0.20 | 0.20 |

What the table says, for the decision: (i) the five sleeves reach ~1.8 full-sample /
~2.0 in-sample with any sensible rule, but **OOS they reach 1.57-1.65 versus 1.57 for the
two live sleeves alone** - the new streams have added almost nothing out of sample so far,
because `overnight_alt` decayed (0.81 -> 0.44), `xs_overnight` is 0.5-correlated with the
overnight sleeve and halved OOS (1.68 -> 1.01), and `ts_reversal` is 0.43-0.50 correlated
with the gap fade. (ii) The IS-fitted mean-variance weights are the worst OOS (1.32): they
put 0.34 on `overnight_alt` and 0.01 on `overnight`, the OOS star. Use `sharpe_over_vol`
or `inverse_vol`, never the raw tangency solution, and shrink toward equal weight.
(iii) These are fixed-weight return combinations at gross 1; the live cash cap binds
between sleeves that hold in the *same* session (the two overnight sleeves at 16:00, the
two reversal sleeves at 09:30), so the implementable allocations are the ratios within
each session, not these absolute weights. (iv) With `reversal_vt` in the mix every rule is
+0.03-0.06 better OOS than with the ramp-sized sleeve.

## 7. RECOMMENDED CONFIGURATION

Everything as in `EnsembleParams.from_profile("growth")` and `RegimeParams()` today, with
three changes, all inside the reversal sleeve and its allocation:

| parameter | live | recommended |
|---|---|---|
| reversal exposure on day d | `clip((VIX[d-1] - 18) / 10, 0, 1)` | `clip((VIX[d-1] - 18) / 2, 0, 1) * min(1, 0.06 / sigma_EW20[d-1])` |
| `sigma_EW20[d-1]` | - | annualised std (x sqrt 252) of the last 20 sessions' equal-weight 70-stock 09:30->16:00 return, sessions d-20..d-1 (`hf_risk.trailing_vol(book_intraday_returns(EW book), 20, lag=1)`) |
| `ReversalParams.weighting` | `"eq"` | `"ivol"` (already implemented in `hf_reversal._leg`) |
| `PROFILES["growth"]["reversal_alloc"]` / `EnsembleParams.alloc["reversal"]` | 0.5 | 1.0 |
| everything else (n=7, mode long, residual, zscore, beta 60, vol 20, vix_floor 18; overnight sleeve; QLD slot; `RegimeParams()` 0.16 / p2 / T0.5 / floor 0.1; dd throttle 10% x0.5; max_exposure 1.5; cash cap 1.0) | unchanged | unchanged |

In `hf_risk` terms: `expo = ramp_exposure(vix_prev, 18, 2) * reversal_vol_sizing(vix_prev,
trailing_vol(book_intraday_returns(ew_book, md.open, md.close), 20, lag=1), target=0.06,
vix_gate=-inf)`, applied with `scale_by_date(unit_book, expo)` where `unit_book =
reversal_weights(md, ReversalParams(weighting="ivol", vix_floor=-1e9, vix_span=1.0))`.
Suggested wiring for the orchestrator (not done here; `hf_reversal.py` untouched): add
`sizing: str = "ramp"`, `vol_target: float | None = None`, `sigma_window: int = 20` to
`ReversalParams`, branch in `reversal_weights` where `scale` is computed, and set
`vix_span=2.0, sizing="voltarget", vol_target=0.06, weighting="ivol"` from the profile.
Defaults stay bit-identical (checked: unit book x live ramp == `reversal_weights(md)`
exactly). Every input is available at 09:30 of d (VIX close of d-1, opens/closes through
d-1); nothing new is fetched.

Scorecard (`report()`, daily timeline, T-bill cash, n_trials = 1200 + 356):

```
ens_risk           | CAGR  12.12% | Vol  7.29% | Sharpe  1.40 | Sortino  1.79 | MaxDD -10.87% | Calmar  1.12 | t  6.53 | PF 1.43 | exp L/S 0.19/0.00 | cost/yr 3.45% | days 4161
  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean 1.5% over the period)
  time in market 41.0% | turnover/day 0.77 | trades/day 7.21 | skew -0.08 | kurt 9.4 | best +3.34% | worst -3.81%
  Sharpe 95% bootstrap CI: [0.91, 1.91]
  Deflated Sharpe: P(SR > null max of 1556 trials = 0.83) = 0.989
  vs benchmark: corr 0.50 | beta 0.21
  In-sample / out-of-sample split at 2022-01-01:
                        days     cagr      vol   sharpe  sortino  max_drawdown   calmar
ens_risk in-sample      2981    0.098    0.071    1.286    1.586        -0.109    0.899
ens_risk out-of-sample  1180    0.183    0.078    1.680    2.304        -0.100    1.821
ens_risk full           4161    0.121    0.073    1.404    1.786        -0.109    1.115
```

Live, same evaluation: Sharpe 1.32 (IS 1.218 / OOS 1.564), CAGR 11.64%, Vol 7.41%, MaxDD
-12.19%, bootstrap CI [0.85, 1.79], deflated P 0.981, kurt 10.6, skew +0.27, cost 2.83%.

| | full | IS (< 2022) | OOS (2022+) |
|---|---|---|---|
| Sharpe live -> recommended | 1.324 -> **1.404** (+0.08) | 1.218 -> **1.286** (+0.07) | 1.564 -> **1.680** (+0.12) |
| CAGR | 11.64% -> 12.12% | 9.3% -> 9.8% | 17.7% -> 18.3% |
| MaxDD | -12.19% -> -10.87% | -12.2% -> -10.9% | -9.6% -> -10.0% |
| ex-cash Sharpe | 1.362 -> 1.45 | 1.23 -> 1.30 | 1.66 -> 1.79 |

Yearly, live vs recommended (return / excess Sharpe / MaxDD):

| year | live return | rec. return | live Sharpe | rec. Sharpe | live MaxDD | rec. MaxDD |
|---|---|---|---|---|---|---|
| 2010 | 8.9% | 14.6% | 1.42 | 2.03 | -4.0% | -3.0% |
| 2011 | 6.4% | 2.9% | 0.65 | 0.38 | -7.4% | -6.8% |
| 2012 | 12.1% | 17.1% | 1.94 | 2.22 | -4.3% | -5.6% |
| 2013 | 20.3% | 20.7% | 2.94 | 2.88 | -2.5% | -3.1% |
| 2014 | 10.9% | 10.4% | 2.00 | 1.79 | -2.6% | -2.8% |
| 2015 | 5.5% | 5.5% | 0.98 | 0.95 | -3.0% | -3.0% |
| 2016 | -0.1% | 1.2% | -0.05 | 0.20 | -5.8% | -6.5% |
| 2017 | 11.2% | 11.2% | 2.68 | 2.68 | -2.0% | -2.0% |
| 2018 | 8.3% | 5.6% | 0.90 | 0.59 | -3.7% | -3.3% |
| 2019 | -1.4% | 0.9% | -0.48 | -0.14 | -12.2% | -10.9% |
| 2020 | 18.0% | 12.7% | 1.44 | 1.26 | -6.7% | -7.6% |
| 2021 | 11.9% | 15.0% | 1.70 | 1.59 | -3.5% | -4.4% |
| 2022 | 9.5% | 5.4% | 0.89 | 0.56 | -5.0% | -4.0% |
| 2023 | 10.0% | 11.7% | 0.67 | 0.83 | -2.7% | -3.1% |
| 2024 | 34.7% | 39.7% | 3.54 | 4.00 | -3.3% | -3.3% |
| 2025 | 21.7% | 23.3% | 1.99 | 2.34 | -2.9% | -2.9% |
| 2026 | 8.7% | 8.2% | 0.88 | 0.75 | -9.6% | -10.0% |

The recommended book gives back part of 2011, 2018, 2020 and 2022 (the years the ramp was
sized *into* the crash and the crash paid) and gains in the ordinary elevated-VIX years
(2010, 2012, 2016, 2019, 2021, 2023-25). That is the intended exchange: less P&L
concentrated in the highest-variance mornings, more from the many VIX 18-25 mornings.

Re-sized sleeve standalone (ex-cash, alloc 1, from 2010-06): Sharpe 0.92 (IS 0.92 / OOS
0.93), CAGR 4.0%, vol 4.3%, MaxDD -5.9%, kurt 14.2, worst -2.64%, avg exposure 0.074
(active 40% of days, exposure on active days q10 0.24 / median 0.44 / q90 0.74),
bootstrap CI [0.47, 1.34], deflated P (340 trials) 0.77, breakeven 7.9 bp/side. Live
sleeve: 0.77 (0.79 / 0.75), MaxDD -12.3%, kurt 30.6, worst -4.87%, CI [0.38, 1.15], BE 9.7.

Files: `/tmp/qb_shared/ensemble_risk_daily.csv` (column `ensemble_risk`, 4161 rows,
2010-03-03 -> 2026-09-16, engine `daily_returns` with T-bill cash),
`/tmp/qb_shared/ensemble_risk_weights.parquet` (md5 of the rounded weights
`42ed415459f61d90a1b1fa2646400e48`).

### What I would NOT change, and why

- **The ensemble-level vol target / Moreira-Muir scaling: do not add it.** Every one of 34
  variants lowered the Sharpe in both periods (section 2). The book is already
  conditioned sleeve by sleeve, and its realised vol is high precisely when the reversal
  sleeve earns; scaling the whole book removes the good days. If the orchestrator wants
  a lower MaxDD, do it with the allocation or the QQQ/QLD choice (QQQ in the slot: 1.39,
  MaxDD -8.5%, CAGR 11.1%), not with a vol target.
- **The drawdown throttle: leave at 10% / 0.5 (or off).** It is inert (-0.008 Sharpe, one
  trigger in 16 years). The 5% level shows +0.03 in the new configuration and -0.004 in
  the live one from the same three episodes - that is noise, and a throttle that cuts
  exposure after a 5% dip in a 7%-vol book would be active a quarter of the time in a bad
  year. Do not tune it for Sharpe.
- **The overnight / reversal allocation logic is right as it stands.** The live 0.5 was the
  exact IS tangency ratio for the ramp-sized sleeve (0.46); 1.0 is the tangency ratio for
  the re-sized sleeve (~0.9). The allocation should follow the sleeve's vol, not the cash
  cap: "both can be 1.0" is a constraint, not a target.
- **The regime multiplier's parameters (0.16, power 2, T0.5, floor 0.1): keep.** The 72-point
  grid spans 1.28-1.35 with IS and OOS rankings anti-correlated; the live point is
  mid-plateau; power 1 vs 2 and the floor are indistinguishable. What matters is that it
  is *on*: off costs -0.03-0.04 Sharpe and doubles MaxDD (-22%). Do not add the VIX
  term-structure gate (-0.04), do not shorten the window (10d: -0.06), do not switch to SPY
  vol (-0.05).
- **The reversal sleeve's own signal and gate (n=7, residual z-scored gap, VIX floor 18):
  keep.** Gate 16 is an in-sample mirage (IS 1.44, OOS 1.03; the VIX 14-18 bucket flipped
  from +5.9 to -9.2 bp/day net) and gate 20-22 throws away the best bucket. The sizing
  change in this note is about *how much* to hold on gated days, not *which* days.
- **The binary gate at alloc 0.4, although it is the IS maximum (1.43).** Same OOS as the
  recommendation, a cliff at VIX 18.0, and constant 0.4-of-equity exposure in seven stocks
  on the worst mornings. The vol target's 0.03 of IS Sharpe is the premium for not doing
  that.

### Failure modes of the recommendation

- **Fill cost.** Breakeven 7.9 bp/side (vs 9.7); the ensemble's advantage over the live
  profile is gone at ~5 bp/side effective on the stock leg. Monitor realised MOO fill vs
  the 09:30 print in paper trading; above ~4 bp, revert to the ramp (keep ivol, alloc 0.5).
- **Crash-year underperformance.** By construction the book holds ~0.1-0.2 of equity in the
  fade on VIX-40+ mornings where the ramp held 0.5; 2011, 2020 and 2022 would have been
  3-5 pp worse than live. If the ex-post argument "the fade pays most in crashes" is what
  the orchestrator wants to own, the ramp is the better rule; the evidence (1b) is that
  return per unit of variance is *not* higher there.
- **Sigma estimate.** 20-day trailing vol of the EW-70 intraday return lags a vol jump by a
  week or two (day one of a crash is sized on calm-market sigma - the VIX gate, which
  reacts overnight, is what protects that morning). Window 10-60 was flat (1.38-1.40), so
  this is not a tuning knob.
- **More names traded.** 7.2 trades/day vs 7.2 but 0.77 vs 0.67 turnover/day; the
  reversal book reaches 1.0 of equity on ~10% of active days (sigma < 6%, VIX > 20). With
  $1,000 that is ~$140/name - fine with fractional shares (reversal.md 6.8).
- **Overlap with `ts_reversal`.** If the orchestrator adds `ts_reversal` (0.43-0.50
  correlated with the gap fade, same session), size the pair jointly - both at 1.0 would
  breach the intraday cash cap and be pro-rata scaled by `leverage_map`.

## 8. `hf_risk.py` API (pure functions, no side effects)

| function | what it returns |
|---|---|
| `realised_vol(r, window)` / `trailing_vol(r, window, lag)` | annualised rolling std; `lag=1` = known at 09:30 of d |
| `vol_target_scale(r, target, window, power, cap, lag, fill)` | `min(cap, (target / RV)^power)`, power 2 = Moreira-Muir |
| `ramp_exposure(vix_prev, floor, span)` | the sleeve's `clip((VIX - floor) / span, 0, 1)` |
| `reversal_vol_sizing(vix_prev, sigma_hat, target, vix_gate, cap)` | `min(cap, target / sigma)` where VIX > gate else 0 |
| `rv_tilt(exposure, rv, ref, power, cap)` | exposure x `(ref / rv)^power`, capped |
| `book_intraday_returns(book, open_, close)` | 09:30 -> 16:00 return of a per-date weight book |
| `scale_by_date(weights, factor_daily, fill)` | per-date factor applied to a session-timeline weight matrix |
| `daily_to_sessions(series, index)` | daily -> 09:30/16:00 stamps (value for d from 16:00 of d) |
| `book_daily_returns(weights, prices)` / `ensemble_vol_scale(weights, prices, target, window, power, cap)` | causal scale-down multiplier for a whole book |
| `sharpe_ratio`, `sharpe_table`, `naive_sharpe_bound` | per-series Sharpe full / IS / OOS, `sqrt(sum S^2)` |
| `max_sharpe_weights(excess_is, no_short)`, `inverse_vol_weights`, `sharpe_proportional_weights` | IS weights, gross 1 |
| `combine_max_sharpe`, `combine_fixed`, `align_excess`, `combination_report` | realised IS / OOS Sharpe of fixed-weight combinations; the decision table of section 6 |

## Appendix A. Full regime grid (task 5)

`ref` = vol_ref, `p` = vol_power, `T` = trend_off_mult, `floor` = min_mult. Sleeve = overnight(QLD) x mult, ex-cash.

| variant | mean mult | sleeve (IS / OOS) | slv CAGR | slv DD | ensemble (IS / OOS) | ens CAGR | ens DD |
|---|---|---|---|---|---|---|---|
| ref 0.12 p1 T0.0 floor 0.0 | 0.67 | 1.20 (1.07 / 1.48) | 6.5% | -12.4% | 1.35 (1.27 / 1.53) | 11.3% | -11.9% |
| ref 0.12 p1 T0.0 floor 0.1 | 0.69 | 1.19 (1.05 / 1.51) | 6.5% | -12.4% | 1.34 (1.25 / 1.55) | 11.3% | -12.0% |
| ref 0.12 p1 T0.0 floor 0.25 | 0.71 | 1.18 (1.02 / 1.54) | 6.5% | -12.4% | 1.34 (1.23 / 1.58) | 11.2% | -12.0% |
| ref 0.12 p1 T0.5 floor 0.0 | 0.70 | 1.20 (1.03 / 1.55) | 6.6% | -12.4% | 1.35 (1.24 / 1.59) | 11.3% | -12.0% |
| ref 0.12 p1 T0.5 floor 0.1 | 0.70 | 1.20 (1.03 / 1.55) | 6.6% | -12.4% | 1.35 (1.24 / 1.59) | 11.3% | -12.0% |
| ref 0.12 p1 T0.5 floor 0.25 | 0.71 | 1.18 (1.01 / 1.55) | 6.5% | -12.4% | 1.33 (1.23 / 1.59) | 11.2% | -12.0% |
| ref 0.12 p1 T1.0 floor 0.0 | 0.73 | 1.18 (0.99 / 1.61) | 6.6% | -12.5% | 1.33 (1.20 / 1.63) | 11.3% | -12.1% |
| ref 0.12 p1 T1.0 floor 0.1 | 0.73 | 1.18 (0.99 / 1.61) | 6.6% | -12.5% | 1.33 (1.20 / 1.63) | 11.3% | -12.1% |
| ref 0.12 p1 T1.0 floor 0.25 | 0.73 | 1.18 (0.99 / 1.61) | 6.6% | -12.5% | 1.33 (1.20 / 1.63) | 11.3% | -12.1% |
| ref 0.12 p2 T0.0 floor 0.0 | 0.56 | 1.14 (0.97 / 1.59) | 5.1% | -10.9% | 1.30 (1.20 / 1.54) | 10.0% | -10.0% |
| ref 0.12 p2 T0.0 floor 0.1 | 0.58 | 1.14 (0.95 / 1.63) | 5.1% | -10.9% | 1.30 (1.19 / 1.56) | 10.0% | -10.0% |
| ref 0.12 p2 T0.0 floor 0.25 | 0.61 | 1.15 (0.94 / 1.68) | 5.2% | -10.9% | 1.30 (1.18 / 1.59) | 10.1% | -10.0% |
| ref 0.12 p2 T0.5 floor 0.0 | 0.58 | 1.15 (0.96 / 1.65) | 5.2% | -10.9% | 1.30 (1.19 / 1.57) | 10.0% | -10.0% |
| ref 0.12 p2 T0.5 floor 0.1 | 0.58 | 1.14 (0.94 / 1.65) | 5.1% | -10.9% | 1.30 (1.19 / 1.57) | 10.0% | -10.0% |
| ref 0.12 p2 T0.5 floor 0.25 | 0.61 | 1.14 (0.94 / 1.68) | 5.2% | -10.9% | 1.30 (1.18 / 1.59) | 10.1% | -10.0% |
| ref 0.12 p2 T1.0 floor 0.0 | 0.59 | 1.15 (0.94 / 1.70) | 5.2% | -10.9% | 1.30 (1.18 / 1.61) | 10.1% | -10.0% |
| ref 0.12 p2 T1.0 floor 0.1 | 0.59 | 1.15 (0.93 / 1.70) | 5.2% | -10.9% | 1.30 (1.18 / 1.61) | 10.1% | -10.0% |
| ref 0.12 p2 T1.0 floor 0.25 | 0.61 | 1.14 (0.93 / 1.70) | 5.2% | -10.9% | 1.30 (1.17 / 1.61) | 10.1% | -10.0% |
| ref 0.16 p1 T0.0 floor 0.0 | 0.78 | 1.18 (1.08 / 1.40) | 7.7% | -13.6% | 1.34 (1.28 / 1.49) | 12.3% | -13.1% |
| ref 0.16 p1 T0.0 floor 0.1 | 0.79 | 1.18 (1.07 / 1.42) | 7.7% | -13.6% | 1.34 (1.27 / 1.50) | 12.3% | -13.1% |
| ref 0.16 p1 T0.0 floor 0.25 | 0.81 | 1.17 (1.04 / 1.45) | 7.7% | -13.7% | 1.33 (1.24 / 1.53) | 12.2% | -13.9% |
| ref 0.16 p1 T0.5 floor 0.0 | 0.82 | 1.18 (1.04 / 1.48) | 7.8% | -13.7% | 1.33 (1.24 / 1.55) | 12.3% | -13.2% |
| ref 0.16 p1 T0.5 floor 0.1 | 0.82 | 1.18 (1.04 / 1.48) | 7.8% | -13.7% | 1.33 (1.24 / 1.55) | 12.3% | -13.2% |
| ref 0.16 p1 T0.5 floor 0.25 | 0.82 | 1.18 (1.03 / 1.48) | 7.7% | -13.7% | 1.33 (1.23 / 1.55) | 12.3% | -13.9% |
| ref 0.16 p1 T1.0 floor 0.0 | 0.85 | 1.17 (0.99 / 1.54) | 7.8% | -15.1% | 1.32 (1.20 / 1.60) | 12.2% | -16.2% |
| ref 0.16 p1 T1.0 floor 0.1 | 0.85 | 1.17 (0.99 / 1.54) | 7.8% | -15.1% | 1.32 (1.20 / 1.60) | 12.2% | -16.2% |
| ref 0.16 p1 T1.0 floor 0.25 | 0.85 | 1.17 (0.99 / 1.54) | 7.8% | -15.1% | 1.32 (1.20 / 1.60) | 12.2% | -16.2% |
| ref 0.16 p2 T0.0 floor 0.0 | 0.72 | 1.15 (1.02 / 1.44) | 6.9% | -12.7% | 1.32 (1.24 / 1.51) | 11.6% | -12.2% |
| ref 0.16 p2 T0.0 floor 0.1 | 0.74 | 1.15 (1.01 / 1.46) | 6.9% | -12.7% | 1.32 (1.23 / 1.53) | 11.6% | -12.2% |
| ref 0.16 p2 T0.0 floor 0.25 | 0.76 | 1.14 (0.98 / 1.49) | 6.9% | -12.7% | 1.31 (1.20 / 1.56) | 11.6% | -12.2% |
| ref 0.16 p2 T0.5 floor 0.0 | 0.75 | 1.16 (1.00 / 1.50) | 6.9% | -12.7% | 1.33 (1.22 / 1.56) | 11.7% | -12.2% |
| **ref 0.16 p2 T0.5 floor 0.1 (live)** | 0.75 | 1.16 (0.99 / 1.50) | 6.9% | -12.7% | 1.32 (1.22 / 1.56) | 11.6% | -12.2% |
| ref 0.16 p2 T0.5 floor 0.25 | 0.76 | 1.14 (0.97 / 1.50) | 6.8% | -12.7% | 1.31 (1.20 / 1.56) | 11.6% | -12.2% |
| ref 0.16 p2 T1.0 floor 0.0 | 0.77 | 1.16 (0.97 / 1.56) | 7.0% | -12.8% | 1.32 (1.20 / 1.61) | 11.7% | -12.2% |
| ref 0.16 p2 T1.0 floor 0.1 | 0.77 | 1.16 (0.97 / 1.56) | 7.0% | -12.8% | 1.32 (1.20 / 1.61) | 11.7% | -12.2% |
| ref 0.16 p2 T1.0 floor 0.25 | 0.77 | 1.15 (0.95 / 1.56) | 7.0% | -12.8% | 1.31 (1.18 / 1.61) | 11.6% | -12.2% |
| ref 0.20 p1 T0.0 floor 0.0 | 0.82 | 1.17 (1.08 / 1.35) | 8.3% | -14.7% | 1.33 (1.29 / 1.44) | 12.8% | -13.5% |
| ref 0.20 p1 T0.0 floor 0.1 | 0.84 | 1.17 (1.07 / 1.37) | 8.3% | -14.7% | 1.31 (1.25 / 1.45) | 12.6% | -15.3% |
| ref 0.20 p1 T0.0 floor 0.25 | 0.86 | 1.16 (1.05 / 1.40) | 8.3% | -14.8% | 1.32 (1.25 / 1.47) | 12.6% | -15.5% |
| ref 0.20 p1 T0.5 floor 0.0 | 0.87 | 1.17 (1.04 / 1.44) | 8.4% | -14.9% | 1.32 (1.25 / 1.51) | 12.7% | -15.6% |
| ref 0.20 p1 T0.5 floor 0.1 | 0.87 | 1.17 (1.04 / 1.44) | 8.4% | -14.9% | 1.32 (1.25 / 1.51) | 12.7% | -15.6% |
| ref 0.20 p1 T0.5 floor 0.25 | 0.87 | 1.17 (1.04 / 1.44) | 8.4% | -15.0% | 1.32 (1.25 / 1.51) | 12.7% | -15.7% |
| ref 0.20 p1 T1.0 floor 0.0 | 0.92 | 1.15 (0.98 / 1.50) | 8.4% | -18.0% | 1.31 (1.20 / 1.56) | 12.7% | -18.3% |
| ref 0.20 p1 T1.0 floor 0.1 | 0.92 | 1.15 (0.98 / 1.50) | 8.4% | -18.0% | 1.31 (1.20 / 1.56) | 12.7% | -18.3% |
| ref 0.20 p1 T1.0 floor 0.25 | 0.92 | 1.15 (0.98 / 1.50) | 8.4% | -18.0% | 1.31 (1.20 / 1.56) | 12.7% | -18.3% |
| ref 0.20 p2 T0.0 floor 0.0 | 0.80 | 1.13 (1.02 / 1.36) | 7.7% | -14.7% | 1.29 (1.23 / 1.44) | 12.2% | -13.5% |
| ref 0.20 p2 T0.0 floor 0.1 | 0.81 | 1.13 (1.01 / 1.38) | 7.7% | -14.7% | 1.29 (1.21 / 1.46) | 12.1% | -14.2% |
| ref 0.20 p2 T0.0 floor 0.25 | 0.84 | 1.12 (0.98 / 1.41) | 7.7% | -14.7% | 1.28 (1.19 / 1.48) | 12.0% | -16.0% |
| ref 0.20 p2 T0.5 floor 0.0 | 0.84 | 1.14 (0.99 / 1.45) | 7.9% | -14.7% | 1.30 (1.20 / 1.51) | 12.3% | -14.4% |
| ref 0.20 p2 T0.5 floor 0.1 | 0.84 | 1.14 (0.99 / 1.45) | 7.9% | -14.7% | 1.30 (1.20 / 1.51) | 12.3% | -14.5% |
| ref 0.20 p2 T0.5 floor 0.25 | 0.84 | 1.13 (0.97 / 1.45) | 7.8% | -14.7% | 1.29 (1.19 / 1.51) | 12.1% | -15.3% |
| ref 0.20 p2 T1.0 floor 0.0 | 0.87 | 1.14 (0.96 / 1.51) | 8.0% | -14.8% | 1.31 (1.19 / 1.57) | 12.4% | -15.2% |
| ref 0.20 p2 T1.0 floor 0.1 | 0.87 | 1.14 (0.96 / 1.51) | 8.0% | -14.8% | 1.31 (1.19 / 1.57) | 12.4% | -15.2% |
| ref 0.20 p2 T1.0 floor 0.25 | 0.87 | 1.14 (0.95 / 1.51) | 8.0% | -15.0% | 1.31 (1.19 / 1.57) | 12.4% | -15.3% |
| ref 0.25 p1 T0.0 floor 0.0 | 0.85 | 1.19 (1.13 / 1.33) | 8.8% | -14.8% | 1.35 (1.33 / 1.42) | 13.3% | -13.5% |
| ref 0.25 p1 T0.0 floor 0.1 | 0.86 | 1.19 (1.12 / 1.35) | 8.8% | -14.8% | 1.34 (1.31 / 1.43) | 13.2% | -14.0% |
| ref 0.25 p1 T0.0 floor 0.25 | 0.88 | 1.19 (1.10 / 1.37) | 8.8% | -14.8% | 1.34 (1.30 / 1.45) | 13.2% | -15.1% |
| ref 0.25 p1 T0.5 floor 0.0 | 0.91 | 1.19 (1.08 / 1.43) | 8.9% | -15.7% | 1.35 (1.29 / 1.50) | 13.3% | -15.5% |
| ref 0.25 p1 T0.5 floor 0.1 | 0.91 | 1.19 (1.08 / 1.43) | 8.9% | -15.7% | 1.35 (1.29 / 1.50) | 13.3% | -15.5% |
| ref 0.25 p1 T0.5 floor 0.25 | 0.91 | 1.19 (1.08 / 1.43) | 8.9% | -15.7% | 1.35 (1.29 / 1.50) | 13.3% | -15.5% |
| ref 0.25 p1 T1.0 floor 0.0 | 0.96 | 1.16 (1.01 / 1.48) | 8.9% | -19.5% | 1.33 (1.23 / 1.54) | 13.2% | -19.1% |
| ref 0.25 p1 T1.0 floor 0.1 | 0.96 | 1.16 (1.01 / 1.48) | 8.9% | -19.5% | 1.33 (1.23 / 1.54) | 13.2% | -19.1% |
| ref 0.25 p1 T1.0 floor 0.25 | 0.96 | 1.16 (1.01 / 1.48) | 8.9% | -19.5% | 1.33 (1.23 / 1.54) | 13.2% | -19.1% |
| ref 0.25 p2 T0.0 floor 0.0 | 0.84 | 1.18 (1.12 / 1.33) | 8.6% | -14.8% | 1.34 (1.32 / 1.42) | 13.1% | -13.5% |
| ref 0.25 p2 T0.0 floor 0.1 | 0.85 | 1.18 (1.10 / 1.35) | 8.6% | -14.8% | 1.34 (1.30 / 1.43) | 13.1% | -13.6% |
| ref 0.25 p2 T0.0 floor 0.25 | 0.87 | 1.17 (1.08 / 1.38) | 8.6% | -14.8% | 1.32 (1.26 / 1.46) | 12.9% | -16.1% |
| ref 0.25 p2 T0.5 floor 0.0 | 0.89 | 1.19 (1.07 / 1.45) | 8.8% | -14.9% | 1.33 (1.25 / 1.52) | 13.1% | -15.7% |
| ref 0.25 p2 T0.5 floor 0.1 | 0.89 | 1.19 (1.07 / 1.45) | 8.8% | -14.9% | 1.33 (1.25 / 1.52) | 13.1% | -15.7% |
| ref 0.25 p2 T0.5 floor 0.25 | 0.90 | 1.19 (1.06 / 1.45) | 8.8% | -14.9% | 1.34 (1.26 / 1.52) | 13.1% | -15.0% |
| ref 0.25 p2 T1.0 floor 0.0 | 0.93 | 1.18 (1.04 / 1.48) | 8.9% | -16.4% | 1.34 (1.26 / 1.55) | 13.3% | -16.6% |
| ref 0.25 p2 T1.0 floor 0.1 | 0.93 | 1.18 (1.04 / 1.48) | 8.9% | -16.4% | 1.34 (1.26 / 1.55) | 13.3% | -16.6% |
| ref 0.25 p2 T1.0 floor 0.25 | 0.93 | 1.18 (1.04 / 1.48) | 8.9% | -16.4% | 1.35 (1.26 / 1.55) | 13.3% | -16.7% |

## Appendix B. Reproduction

```
export MPLCONFIGDIR=/tmp/mpl
python3 /tmp/qb_risk/pipeline.py                      # hash check: 59f06819cdf380d6a5cb841e84c54188 OK
python3 /tmp/qb_risk/task1_reversal_sizing.py         # 1a           (102 trials)
python3 /tmp/qb_risk/task2_3_voltarget_throttle.py    # 2, 3         (43)
python3 /tmp/qb_risk/task4_5_alloc_regime.py          # 4, 5, App. A (162)
python3 /tmp/qb_risk/task1b_diagnostics.py            # 1b           (diagnostics)
python3 /tmp/qb_risk/task1c_joint.py                  # 1c           (27)
python3 /tmp/qb_risk/task1d_final.py                  # 1d, scorecard (20)
python3 /tmp/qb_risk/task1e_costs.py                  # 1e           (2)
python3 /tmp/qb_risk/task6_combine.py                 # 6, saves /tmp/qb_shared/ensemble_risk_daily.csv
```
