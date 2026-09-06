# Cross-asset open-to-close gap continuation (`quantbot/strategies/hf_crossasset.py`)

Timeline: daily (`md.px_daily`). At 09:30 of day d: position = sign(gap_d) x inverse-vol
basket weight in each ETF whose |gap z-score| > k; explicit 0.0 row at 16:00. Universe
researched: the 16 non-equity ETFs of `HFConfig.wide()` (TLT IEF IEI TIP LQD HYG GLD SLV
USO UNG DBC VNQ EEM EFA FXI EWJ) plus 9 equity ETFs for comparison. Final basket:
**TLT + GLD**, k = 1.0, fixed size, inverse-vol weights, long *and* short. Tuned on
< 2022-01-01; OOS 2022-01 -> 2026-09. rf = `md.cash_yield()` (^IRX), all Sharpes are
excess of it. Costs 1 bp/side (2 bp per active day). **`n_trials = 310`.**

**Headline: marginal, not negative.** The gap-continuation effect in TLT is real at the
gross level (basket gross Sharpe 0.81, t 4.7, IS 0.83 / OOS 0.76, same sign in 13 of 17
years) but it is a ~4.3 bp/active-day effect (per unit of exposure) against a 2 bp round
trip. Net: **Sharpe 0.44
(IS 0.46 / OOS 0.39), ex-cash CAGR 1.8%, MaxDD -9.3%**, bootstrap CI [-0.01, 0.92],
deflated-Sharpe probability 0.13 at 310 trials (**fails** the multiple-testing bar).
Correlation with SPY -0.03, overnight sleeve +0.02, reversal sleeve -0.07, growth
ensemble -0.04. Adding it to the growth profile raises ensemble Sharpe 1.31 -> 1.37 /
1.40 / 1.40 at allocation 0.25 / 0.5 / 1.0 (MaxDD -12.2% -> -12.6 / -13.0 / -13.7%).
Recommended allocation **0.25** (monitoring size; conditions in section 7). The
long-only variant at k = 1 has no edge (0.04): the short (gap-down) leg carries the
result, so if shorts are not available live the allocation is **0**.

## 1. Hypothesis and literature

Intraday momentum (Gao, Han, Li & Zhou 2018 JFE; Baltussen, Da, Lammers & Martens 2021)
has left US equity index ETFs (round 1: `intraday_momentum.md`, sign(gap) -> open-to-close
= +0.3 bp in SPY over 16 years; 2025 was a gap-*fade* year). Round 1's 16-year daily panel
did find gap **continuation** in TLT (t 3.0) and GLD (t 2.1; 6.8 bp at |z| > 1). The
economic story: TLT and GLD open at 09:30 after their primary markets - Treasury futures
(open since 18:00 ET the prior day) and London gold - have already moved, so the ETF gap
is a *known* move rather than a US-session surprise, and the US-session flows that follow
(08:30 / 10:00 macro data digestion, asset-allocator and ETF-creation flows that are
slower than the equity gamma/leveraged-ETF crowd) continue it (cf. Moskowitz, Ooi &
Pedersen 2012 on time-series momentum in rates/commodities being the most persistent;
Lou, Polk & Skouras 2019 on the overnight/intraday split). For the Asia/Europe-traded
equity ETFs (EEM/EFA/FXI/EWJ) the gap is largely a stale-NAV catch-up to a home market
that is already closed (Japan) or closing (Europe); it could continue (if US flows follow)
or fade (if the gap overshoots) - tested both, found neither. Prediction to be tested:
sign(gap) predicts the same-day open-to-close return in TLT/GLD, monotonically in |gap|,
and does not in equity ETFs.

## 2. Everything tested

### 2a. Conditional edge, in-sample 2010-2021 only (25 screens)

gap = Open_d / Close_{d-1} - 1; oc = Close_d / Open_d - 1; z = gap / std(20 prior gaps).
"cont" = mean of sign(gap) x oc in bp/day (t-stat); |z| buckets show the same quantity on
those days. N = 3000 days per ticker. OOS 2022+ column recorded for reference (not used
to select anything).

| ETF | uncond oc | cont, all days | gap>0 oc / gap<0 oc | \|z\|<0.5 | 0.5-1 | 1-1.5 | >1.5 [n] | \|z\|>1 (t) | OOS 2022+ all / \|z\|>1 |
|---|---|---|---|---|---|---|---|---|---|
| **TLT** | 2.1 (1.8) | **3.9 (3.3)** | 5.9 / -1.8 | 3.0 | 2.3 | 5.0 | 8.0 (2.4) [435] | **6.3 (3.0)** | 0.8 / 1.6 (t 0.4 / 0.5) |
| IEF | 1.0 (2.2) | 1.5 (3.1) | 2.5 / -0.5 | 1.0 | 2.1 | 0.9 | 1.8 [451] | 1.4 (1.5) | 0.1 / 2.0 |
| IEI | 0.8 (3.2) | 0.4 (1.4) | 1.2 / 0.5 | 0.2 | 0.7 | 0.6 | -0.2 | 0.2 (0.4) | 0.1 / 0.2 |
| TIP | -0.2 | 0.3 (0.6) | 0.1 / -0.6 | 0.3 | 0.7 | 0.1 | 0.0 | 0.1 (0.1) | 1.6 (1.9) / 2.2 |
| LQD | 0.2 | 1.1 (1.9) | 1.2 / -1.0 | 1.1 | 1.5 | 0.2 | 1.5 | 0.8 (0.7) | -0.4 / -1.9 |
| HYG | 0.4 | 2.0 (2.9) | 2.1 / -1.9 | 2.1 | 1.0 | 2.3 | 3.1 | 2.7 (2.1) | 0.4 / -2.0 |
| **GLD** | -0.2 | **0.1 (0.05)** | -0.2 / -0.3 | -1.8 | 0.6 | -2.8 | **8.0 (2.2)** [424] | 2.5 (1.0) | **7.1 (3.5) / 7.9 (2.0)** |
| SLV | -1.7 | -0.2 | -1.6 / -1.5 | -2.3 | -5.2 | 7.6 | 8.7 | 8.2 (1.7) | 1.8 / 3.0 |
| USO | -0.3 | 3.1 (1.1) | 2.8 / -3.6 | 2.0 | -2.5 | 2.4 | 18.2 (2.2) | 10.0 (1.9) | -6.7 / -6.3 |
| UNG | -4.5 | 2.4 (0.7) | -1.8 / -6.4 | **-12.2 (-2.5)** | -2.7 | 25.8 (3.3) | 24.7 (2.8) | 25.3 (4.3) | 1.9 / 5.0 |
| DBC | -0.8 | 2.3 (1.7) | 1.4 / -3.2 | -0.7 | 6.1 (2.4) | -2.0 | 7.6 | 2.7 (1.0) | 0.5 / 2.3 |
| VNQ | 0.5 | **5.4 (2.8)** | 5.0 / -5.8 | 2.4 | 2.9 | 11.7 (2.2) | 12.3 (2.1) | 12.0 (3.1) | 0.4 / 2.8 (t 0.1 / 0.4) |
| EEM | 0.3 | **4.5 (3.1)** | 4.5 / -4.5 | -0.3 | 4.5 | 14.7 (4.4) | 7.3 | 11.2 (4.1) | **-2.1 / -4.7** (flips) |
| EFA | 3.1 (2.5) | 0.4 (0.3) | 3.4 / 2.8 | -1.1 | 2.1 | -3.6 | 5.9 | 0.9 (0.4) | -1.9 / -5.9 |
| FXI | 2.9 (2.0) | 2.5 (1.7) | 5.3 / 0.4 | 1.8 | 0.4 | 6.6 | 3.8 | 5.3 (1.9) | 3.1 / 10.6 |
| EWJ | **4.4 (4.1)** | 0.6 (0.6) | 5.0 / 3.8 | 1.4 | 1.3 | -0.2 | -2.1 | -1.1 (-0.5) | -1.6 / -2.0 |
| SPY | 2.2 (1.6) | 1.4 (1.0) | 3.2 / 1.0 | -2.4 | 1.2 | 5.3 | 8.6 (1.9) | 7.0 (2.5) | **-2.5 / -5.8** |
| QQQ | 2.9 (1.7) | 1.4 (0.8) | 3.7 / 1.7 | 1.9 | -1.9 | 5.7 | 2.0 | 3.8 (1.0) | -0.7 / -10.2 |
| IWM | 0.0 | 2.4 (1.2) | 2.1 / -2.7 | 5.8 (2.1) | -3.3 | 4.7 | 0.9 | 2.8 (0.7) | -4.4 / -10.6 |
| DIA | 1.6 | 1.3 (1.0) | 2.6 / 0.4 | -3.2 | 0.9 | 3.9 | 12.4 (2.8) | 8.2 (2.9) | -3.8 / -5.7 |
| XLE / XLU / SMH | -1.7 / 3.6 / 3.5 | 4.2 (1.8) / 3.3 (2.0) / 4.9 (2.2) | | | | | | 8.0 / 5.9 / 10.1 (t 1.7-2.2) | -5.7 / -1.5 / -2.1; \|z\|>1: **-17.7 (-2.2) / -12.6 (-2.1)** / 3.5 |

Per-year t of sign(gap) x oc, TLT: 2010 +2.0, 2011 +3.6, 2012 +0.1, 2013 -0.2, 2014 +0.3,
2015 +2.8, 2016 -0.9, 2017 +0.3, 2018 -0.7, 2019 +2.1, 2020 -0.4, 2021 +1.8, 2022 +0.4,
2023 +1.8, 2024 -0.9, 2025 -1.7, 2026 +0.8. GLD: 2010-21 all |t| < 1 except 2011 (+0.9),
then 2022 +1.1, 2023 +2.1, 2024 +2.5, 2025 +1.4, 2026 +1.1.

Read-out:
1. **TLT is the one clean case**: continuation on all days (t 3.3), monotone in |z|
   (3.0 -> 2.3 -> 5.0 -> 8.0 bp), both legs symmetric around the unconditional drift
   (gap-up days +5.9, gap-down -1.8 vs +2.1 unconditional). IEF is the same signal at
   half the bp (1.5, t 3.1) - proportional to its vol - which matters below.
2. **GLD has no in-sample effect on ordinary days** (0.1 bp, t 0.05) and 8 bp only at
   |z| > 1.5; its full-sample t of 2.1 in round 1 comes from **2022-2026** (7.1 bp/day,
   t 3.5). GLD is in the basket on the prior, not on the in-sample evidence.
3. **Equity ETFs showed continuation in-sample at |z| > 1 (SPY 7.0, DIA 8.2, XLE 8.0 bp,
   t 2-3) and all of it reversed OOS** (SPY -5.8, XLE -17.7, XLU -12.6). This is why round
   1's 16-year number is ~0: the equity effect is regime-dependent and flipped in 2022+.
   Excluded, as the brief expected.
4. EEM (4.5 bp, t 3.1; 11 bp at |z| > 1, t 4.1) and VNQ (5.4, t 2.8) look as good as
   TLT in-sample and **both vanish or flip OOS** (EEM -2.1 / -4.7). EFA/EWJ/FXI: no
   continuation and no fade at any |z| (the intl "stale NAV" story has nothing in it
   either way; EWJ has a strong *unconditional* intraday drift of 4.4 bp/day, t 4.1, and
   a negative gap beta t -2.9 - a different, un-traded effect). UNG/USO: huge bp at
   |z| > 1 (25 / 18) but on 3%-daily-vol instruments with -12 bp at small |z| -
   noise on broken instruments.
5. **Fixed-bp costs decide which of these are tradable.** The edge in bp scales with the
   instrument's vol (TLT 3.9 vs IEF 1.5 vs IEI 0.4) while the 2 bp round trip does not,
   so IEF/IEI/TIP/LQD/HYG are structurally untradable at 1 bp/side (section 2b) and only
   the high-vol expression of each theme (TLT for rates, GLD for gold) can pay.

### 2b. Strategy grid via the engine (72 single-asset + 123 basket trials), net, ex-cash Sharpe

Single assets, fixed size, L/S, k = 0 / 0.5 / 1.0 / 1.5 (full-sample net Sharpe; IS / OOS
for the best k; gross at k = 0):

| ETF | k=0 | k=0.5 | k=1.0 | k=1.5 | best k IS / OOS | gross k=0 |
|---|---|---|---|---|---|---|
| **TLT** | 0.22 | **0.42** | 0.39 | 0.37 | 0.44 / 0.36 (k=0.5) | 0.71 |
| IEF | -0.55 | -0.27 | -0.18 | -0.09 | | 0.60 |
| IEI / TIP / LQD | -4.8 / -2.5 / -2.0 | -3.6 / -1.8 / -1.7 | -2.6 / -1.3 / -1.2 | -1.7 / -0.8 / -0.6 | | 0.20 / 0.34 / 0.28 |
| HYG | -0.25 | -0.18 | -0.15 | -0.15 | | 0.60 |
| **GLD** | -0.02 | 0.20 | 0.21 | **0.52** | 0.44 / 0.70 (k=1.5); k=0: -0.49 / **1.12** | 0.46 |
| SLV | -0.22 | 0.03 | 0.25 | 0.21 | 0.35 / 0.04 | 0.02 |
| USO / UNG / DBC | -0.49 / -0.19 / -0.74 | -0.36 / 0.36 / -0.37 | -0.01 / 0.64 / -0.30 | 0.11 / 0.45 / -0.12 | UNG k=1: 0.99 / **0.00** | 0.02 / 0.19 / 0.31 |
| VNQ | -0.16 | 0.16 | 0.33 | 0.26 | 0.53 / -0.16 (k=1) | 0.60 |
| EEM | 0.10 | 0.41 | 0.47 | 0.16 | 0.96 / **-0.72** (k=1) | 0.49 |
| EFA / FXI / EWJ | -0.54 / -0.45 / -1.26 | -0.32 / -0.32 / -1.03 | -0.38 / 0.15 / -0.78 | -0.05 / 0.08 / -0.51 | | -0.08 / 0.47 / 0.00 |
| SPY / QQQ | -0.34 / -0.20 | 0.02 / -0.21 | 0.13 / -0.16 | 0.13 / -0.13 | SPY k=1: 0.50 / -0.68 | 0.05 / 0.11 |

Baskets (k x sizing x eq/ivol; selected rows, all L/S; full net Sharpe (IS / OOS), gross):

| Basket | k=0 fixed | k=0 z-scaled | k=0.5 fixed ivol | k=1.0 fixed ivol | k=1.5 fixed ivol | comment |
|---|---|---|---|---|---|---|
| **TLT+GLD** | 0.14 (0.01 / 0.45) | 0.37 (0.24 / 0.71) | **0.48 (0.32 / 0.89)**, gross 1.01 | **0.44 (0.46 / 0.39)**, gross 0.81 | 0.67 (0.75 / 0.49), gross 0.91 | chosen basket |
| TLT+IEF+GLD | -0.12 | 0.12 | 0.24 (0.18 / 0.38) | 0.21 (0.21 / 0.22) | 0.39 (0.47 / 0.21) | IEF's cost drag; ivol *over*-weights it |
| TLT+GLD+SLV | -0.07 | 0.22 | 0.33 (0.19 / 0.70) | 0.43 (0.49 / 0.26) | 0.54 (0.64 / 0.33) | SLV adds vol, not edge |
| TLT+IEF+GLD+SLV | -0.25 | 0.06 | 0.19 (0.12 / 0.33) | 0.27 (0.33 / 0.14) | 0.40 (0.50 / 0.16) | |
| IS-mined: TLT,IEF,HYG,VNQ,EEM (all IS t > 2.8) | -0.24 | 0.05 | 0.14 (0.42 / **-0.47**) | 0.23 (0.60 / **-0.57**) | 0.20 (0.52 / -0.45) | what naive selection on 2a buys you |
| TLT+GLD+VNQ+EEM | 0.01 | 0.42 | 0.52 (0.68 / 0.12) | 0.61 (**0.91 / -0.14**) | 0.58 (0.81 / 0.08) | best IS of anything; OOS ~0 |
| intl EEM+EFA+FXI+EWJ, continuation | -0.72 | -0.45 | -0.41 (-0.16 / -1.01) | -0.23 | -0.13 | no effect |
| intl, **fade** (eq) | -1.34 (k=0) | | -1.07 (k=0.5) | -0.85 (k=1) | | gross -0.36 to -0.38: fading loses too |
| all 16 non-equity, eq | -1.11 | -0.50 | -0.38 | 0.08 (0.41 / -0.58) | 0.19 (0.49 / -0.41) | the low-vol bond ETFs sink it |

Equal-weight vs inverse-vol for TLT+GLD differs by < 0.05 at every k (they have similar
vol). Z-scaled sizing (size = min(|z|, 1)) is a cost saver, not an edge improver: at k = 0
it lifts 0.14 -> 0.37 by trading small on small gaps, and at k >= 1 it is identical to
fixed sizing. The TLT and GLD legs have daily-return correlation **0.04**, so the basket's
gross Sharpe (~0.8-1.0) is above either leg's (0.7 / 0.5), which is the whole case for
holding both.

Long-only (drop the gap-down/short leg), TLT+GLD ivol: k=0 0.28 (0.20 / 0.47), **k=0.5
0.37 (0.30 / 0.52)**, k=0.75 0.11, k=1.0 **0.04 (0.06 / -0.01)**, k=1.5 0.14. Long-only
k=1 is dead: TLT's gap-up days at |z| > 1 continued in-sample (+3.8 bp net) and reversed
OOS (-3.9 bp net); GLD's long leg is -1.1 bp net over the full sample. The short legs are
where the money is: TLT short +4.2 bp net (IS 4.9 / OOS 2.6), GLD short +5.9 (IS 4.5 /
OOS 10.1). Section 6 discusses what this means for a cash account.

### 2c. Filters (24 trials) and the fine k grid (29 trials)

Conditional continuation, TLT and GLD, |z| > 0.5 days, IS bp (t) [n] | OOS bp (t):

| Condition | TLT IS | TLT OOS | GLD IS | GLD OOS | IEF IS |
|---|---|---|---|---|---|
| Mon / Tue / Wed / Thu / Fri | -4.4 (-1.2) / 5.1 / 3.3 / 7.6 (2.2) / **9.3 (3.1)** | 7.9 / 4.6 / 5.3 / 1.7 / **0.8** | 5.9 / -2.4 / -1.5 / 3.9 / 1.9 | 16.2 (3.1) / 10.3 / -0.1 / 3.0 / 9.3 | -1.5 / 2.7 / 1.4 / 2.0 / 3.7 (3.1) |
| VIX(d-1) > 20 / <= 20 | 3.9 (1.0) / **4.6 (3.2)** | **-1.3** / **6.9 (2.8)** | 1.4 / 1.6 | 8.5 / 7.2 | 1.3 / 1.9 (3.0) |
| close > 200d MA / below | 3.5 (1.7) / 5.6 (2.8) | 4.9 / 3.6 | 1.2 / 1.9 | 6.9 / 10.8 | 1.7 / 1.8 |
| gap with trend / against trend | 2.9 (1.3) / **5.7 (2.9)** | 1.3 / **6.6 (2.0)** | 1.5 / 1.6 | 7.7 / 7.6 | 0.0 / **3.4 (4.1)** |
| first Friday of month (NFP) | 7.3 (1.1) [98] | -4.0 | 6.9 | 21.8 | 3.6 |

Engine runs on TLT+GLD ivol L/S (full net Sharpe, IS / OOS):

| Filter | k = 0.5 | k = 1.0 | verdict |
|---|---|---|---|
| none | 0.48 (0.32 / 0.89) | 0.44 (0.46 / 0.39) | |
| only gaps *with* the 200d trend | 0.17 (0.07 / 0.42) | -0.04 (-0.04 / -0.03) | wrong way: counter-trend gaps continue more |
| VIX(d-1) <= 20 only | 0.54 (0.35 / 1.05) | **0.53 (0.52 / 0.56)** | consistent IS/OOS for TLT, MaxDD -9% -> -8%; +0.09 Sharpe |
| VIX > 20 only | 0.12 | 0.09 | no edge in stress |
| Mon-Thu / Tue-Fri / Fri only | 0.31 / 0.46 / 0.45 | 0.29 / 0.43 / 0.39 | weekday pattern flips IS -> OOS (TLT Mon -4 -> +8, Fri +9 -> +1) |
| gap_window 10 / 40 / 60 | 0.48 / 0.43 / 0.40 | 0.54 / 0.34 / 0.39 | plateau |
| vol_window 10 / 60 | 0.44 / 0.45 | 0.41 / 0.44 | plateau |

The only filter with a consistent sign in both halves is **VIX <= 20** for TLT (the
continuation is a calm-market phenomenon; in stress the Treasury gap is flight-to-quality
and does not continue). It is kept as an optional `vix_max` parameter, **off by default**:
+0.09 Sharpe is inside the noise, the overnight and reversal notes both found VIX-level
conditioners fragile, and the sleeve should stay simple. The counter-trend result (TLT 5.7
vs 2.9 bp, IEF 3.4 vs 0.0, holds OOS for TLT) is interesting - a gap against the 200d
trend is more likely a macro-data surprise than drift - but it is a post-hoc story and
GLD shows nothing, so it is reported, not used. Weekday/NFP effects do not replicate.

Fine k grid, TLT+GLD ivol L/S, fixed size (full / IS / OOS net; ex-cash CAGR; MaxDD; time in market):

| k | 0.25 | 0.5 | 0.75 | 1.0 | 1.25 | 1.5 | 1.75 | 2.0 | 2.5 |
|---|---|---|---|---|---|---|---|---|---|
| Sharpe | 0.25 | 0.48 | 0.34 | **0.44** | 0.68 | 0.67 | 0.74 | 0.46 | 0.43 |
| IS / OOS | 0.08 / 0.69 | 0.32 / 0.89 | 0.28 / 0.47 | 0.46 / 0.39 | 0.71 / 0.60 | 0.75 / 0.49 | 0.90 / 0.41 | 0.51 / 0.35 | 0.47 / 0.34 |
| CAGR ex-cash | 1.5% | 2.7% | 1.6% | 1.8% | 2.4% | 2.0% | 1.9% | 1.1% | 0.7% |
| MaxDD | -22% | -24% | -23% | -10% | -6% | -6% | -6% | -9% | -7% |
| time in mkt | 48% | 41% | 33% | 25% | 17% | 12% | 8% | 6% | 3% |
| gross Sharpe | 0.88 | 1.01 | 0.86 | 0.81 | 0.99 | 0.91 | 0.94 | 0.61 | 0.55 |

The grid is **not smooth** (0.48 -> 0.34 -> 0.44 -> 0.68) on a book that earns ~1 bp/day:
differences of 0.2-0.3 Sharpe between adjacent k are noise, and k = 1.25-1.75 (the
in-sample peak, 8-17% time in market) is the kind of choice I should not make. **k = 1.0
is the prior** (round 1's "|gap| > 1 vol" observation and the |z| > 1 bucket in 2a) and sits
in the middle of the grid with the most balanced IS / OOS (0.46 / 0.39); k = 0.5 has the
best OOS but that OOS is GLD's 2022-26 run (GLD-only k=0.5: IS -0.09 / OOS 0.95).

### Trial count

2a 25 screens + 2b 72 single-asset + 123 basket/long-only + 2c 24 filters + 29 fine-k /
cost / legs + 7 variant scorecards + 10 ensemble mixes + 20 sensitivity rows = **310**.
Baselines, the causality checks and the drop-one-year recomputations are not counted.

## 3. Final scorecard - `CrossAssetParams()` defaults

assets (TLT, GLD), k = 1.0, gap_window 20, sizing "fixed", long_only False, direction +1,
weighting "ivol", vol_window 20, vix_max None, max_gross 1.0. Runtime 0.01 s (weights),
2.3 s for the whole scorecard script. Weights are bit-identical on `HFConfig()` and
`HFConfig.wide()` (TLT and GLD are in both). Causality check: perturbing Close[d] leaves
the 09:30 row of day d unchanged and changes the 09:30 row of d+1 (via the gap and the
vol weights), as required.

`report()` output (net of 1 bp/side, cash at ^IRX, Sharpe excess of it):

```
==============================================================================================================
crossasset         | CAGR   3.29% | Vol  4.21% | Sharpe  0.44 | Sortino  0.56 | MaxDD  -9.26% | Calmar  0.36 | t  3.21 | PF 1.22 | exp L/S 0.08/0.07 | cost/yr 1.56% | days 4153
  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean 1.5% over the period)
  time in market 24.6% | turnover/day 0.62 | trades/day 1.22 | skew -0.18 | kurt 13.3 | best +1.97% | worst -2.41%
  Sharpe 95% bootstrap CI: [-0.01, 0.92]
  Deflated Sharpe: P(SR > null max of 310 trials = 0.72) = 0.133
  vs benchmark: corr -0.03 | beta -0.01

  Yearly:
       return      vol   sharpe   max_dd  days
2010    0.051    0.044    1.324   -0.023   213
2011    0.158    0.062    2.400   -0.023   252
2012   -0.022    0.038   -0.602   -0.029   250
2013    0.033    0.052    0.644   -0.045   252
2014    0.010    0.032    0.312   -0.036   252
2015    0.048    0.041    1.144   -0.030   252
2016   -0.027    0.035   -0.870   -0.050   252
2017   -0.027    0.029   -1.230   -0.046   251
2018    0.050    0.029    1.049   -0.018   251
2019    0.013    0.032   -0.218   -0.035   252
2020   -0.015    0.055   -0.307   -0.055   253
2021    0.023    0.038    0.600   -0.024   252
2022    0.019    0.055    0.013   -0.050   251
2023    0.115    0.042    1.422   -0.020   250
2024    0.051    0.034    0.020   -0.015   252
2025    0.036    0.040   -0.107   -0.026   250
2026    0.045    0.036    0.845   -0.019   168

  In-sample / out-of-sample split at 2022-01-01:
                          days     cagr      vol   sharpe  sortino  max_drawdown   calmar
crossasset in-sample      2982    0.024    0.042    0.461    0.590        -0.093    0.256
crossasset out-of-sample  1171    0.057    0.042    0.389    0.478        -0.050    1.132
crossasset full           4153    0.033    0.042    0.440    0.557        -0.093    0.355
==============================================================================================================
```

Ex-cash (`cash_yield_annual=0`): CAGR **1.82%**, Sharpe 0.45 (IS 0.47 / OOS 0.42), MaxDD
-10.0%, t 1.83, CI [-0.00, 0.93], deflated P 0.14. **Gross** (cost 0): Sharpe 0.81 (IS
0.83 / OOS 0.76), CAGR 4.9%, MaxDD -7.1%, t 4.7. 2051 active days (49% of days; TLT 1333,
GLD 1213), mean gross exposure on active days 0.63; per unit of exposure **+4.3 bp gross,
+2.3 bp net per active day** (book level: +2.8 gross / +1.5 net), hit rate 52.4%, worst
day -2.4% (2022-02-24, long both on the Ukraine-invasion morning), best +2.0%. Per-leg
net bp per active day: TLT +3.0 (t 1.7), GLD +2.0 (t 1.0). Yearly net
bp/active day, TLT: 2010 +8, **2011 +28**, 2012 -3, 2013 +2, 2014 +1, 2015 +12, 2016 -5,
2017 -3, 2018 +3, 2019 +3, 2020 -7, 2021 +10, 2022 +2, 2023 +8, 2024 -2, 2025 -10,
2026 +1; GLD: +12, +10, -8, +5, +2, 0, -5, -7, +2, -6, +4, -6, -3, +6, +3, +12, +12.

Robustness (not trials): **ex-2011 Sharpe 0.25** (IS 0.19 / OOS 0.39) - 2011 (the debt
ceiling / Operation Twist year, +15.8%) is a third of the in-sample P&L; ex-2023 0.38 (OOS
0.11). Rolling 3-year Sharpe ranges from -0.58 (window ending 2019-02) to +1.39 (2013-09)
and is **negative in 31% of 3-year windows**. This is a slow, low-conviction edge.

Variants at the default's parameters (net, excess of cash):

| Variant | Sharpe (IS / OOS) | CAGR | MaxDD | cost/yr | time in mkt | corr SPY |
|---|---|---|---|---|---|---|
| **default L/S k=1** | **0.44 (0.46 / 0.39)** | 3.3% | -9.3% | 1.6% | 25% | -0.03 |
| L/S k=0.5 | 0.48 (0.32 / 0.89) | 4.1% | -19.4% | 3.0% | 41% | -0.01 |
| L/S k=1.5 | 0.67 (0.75 / 0.49) | 3.5% | -4.9% | 0.7% | 12% | 0.01 |
| **long-only k=0.5** (the long-biased variant) | 0.37 (0.30 / 0.52) | 3.0% | -11.7% | 1.6% | 25% | -0.05 |
| long-only k=1 | 0.04 (0.06 / -0.01) | 1.6% | -11.4% | 0.8% | 14% | -0.06 |
| default + vix_max=20 | 0.53 (0.52 / 0.56) | 3.1% | -7.8% | 1.1% | 17% | -0.02 |
| TLT only k=1 (eq) | 0.39 (0.58 / -0.07) | 3.7% | -10.3% | 1.6% | 16% | -0.03 |
| GLD only k=1 (eq) | 0.21 (0.03 / 0.67) | 2.6% | -13.9% | 1.5% | 15% | -0.02 |

The two legs each work in one half of the sample (TLT in-sample, GLD out-of-sample) and
are uncorrelated (0.04), so the basket looks stable across the split while neither leg
does. That is a caution, not a feature: the OOS number is carried by a GLD effect that had
no in-sample support on ordinary days.

## 4. Sensitivity (one-at-a-time around the defaults; net Sharpe full / IS / OOS)

| Parameter | Value | full | IS | OOS | comment |
|---|---|---|---|---|---|
| k | 0.5 / **1.0** / 1.5 / 2.0 | 0.48 / **0.44** / 0.67 / 0.46 | 0.32 / 0.46 / 0.75 / 0.51 | 0.89 / 0.39 / 0.49 / 0.35 | non-monotone; see 2c |
| gap_window | 10 / **20** / 40 / 60 | 0.54 / **0.44** / 0.34 / 0.39 | 0.51 / 0.46 / 0.39 / 0.34 | 0.62 / 0.39 / 0.21 / 0.51 | all positive; shorter is slightly better |
| vol_window | 10 / **20** / 60 | 0.41 / **0.44** / 0.44 | 0.42 / 0.46 / 0.47 | 0.36 / 0.39 / 0.37 | irrelevant |
| weighting | **ivol** / eq | **0.44** / 0.42 | 0.46 / 0.42 | 0.39 / 0.42 | irrelevant for 2 similar-vol assets |
| sizing | **fixed k=1** / zscaled cap 1 (k=0.5) / zscaled cap 2 (k=0.5) | **0.44** / 0.47 / 0.57 | 0.46 / 0.34 / 0.48 | 0.39 / 0.80 / 0.78 | cap-2 scaling (size up to 2x on |z| > 1, renormalised to gross 1) is the best row but adds a parameter for +0.1 |
| assets | **TLT,GLD** / +IEF / +SLV / +IEF+SLV | **0.44** / 0.21 / 0.43 / 0.27 | 0.46 / 0.21 / 0.49 / 0.33 | 0.39 / 0.22 / 0.27 / 0.14 | every addition hurts; IEF via ivol gets the largest weight and the worst edge/cost |
| direction | **+1** / -1 (fade) | **0.44** / -1.20 | 0.46 / -1.21 | 0.39 / -1.19 | the sign is not in doubt |
| vix_max | **None** / 25 / 20 | **0.44** / 0.40 / 0.53 | 0.46 / 0.38 / 0.52 | 0.39 / 0.46 / 0.56 | see 2c |
| cost per side | 0 / 0.5 / **1.0** / 1.5 / 2.0 bp | 0.81 / 0.63 / **0.44** / 0.26 / 0.07 | 0.83 / 0.65 / 0.46 / 0.28 / 0.09 | 0.76 / 0.57 / 0.39 / 0.20 / 0.02 | **breakeven ~2.2 bp/side**; each 0.5 bp costs 0.18 Sharpe |

Degradation is smooth in everything except k, where the grid is jagged because the
sleeve's P&L per day is ~1 bp. No parameter produces a cliff, and none lifts the gross
edge - the gross Sharpe is 0.8-1.0 for every k from 0.25 to 1.75. The whole net result is
the cost line: at 0.5 bp/side (plausible for TLT/GLD with MOO/MOC fills - the brief's
cost model is "2-5x conservative" for ETFs) the sleeve is a 0.63; at 1.5 bp it is a 0.26.

## 5. Correlations (daily excess returns, 2010-03 -> 2026-09, all sleeves run on `HFConfig()` with defaults)

| | crossasset | xa long-only k=0.5 | overnight | reversal | growth ensemble | SPY | TLT c-c | GLD c-c |
|---|---|---|---|---|---|---|---|---|
| **crossasset (default)** | 1 | 0.53 | **0.02** | **-0.07** | **-0.04** | **-0.03** | -0.01 | -0.06 |
| xa long-only k=0.5 | 0.53 | 1 | 0.05 | -0.06 | -0.04 | -0.04 | 0.33 | 0.27 |
| overnight | 0.02 | 0.05 | 1 | 0.00 | 0.72 | 0.32 | -0.11 | 0.04 |
| reversal | -0.07 | -0.06 | 0.00 | 1 | 0.61 | 0.50 | -0.10 | 0.00 |

OOS (2022+) correlations of the default with overnight / reversal / ensemble / SPY: -0.04 /
-0.09 / -0.08 / -0.05. The L/S sleeve is orthogonal to everything, including TLT and GLD
themselves (it is long or short each with equal frequency). The long-only variant carries
0.3 beta to TLT and GLD buy-and-hold - it is partly a "long duration / long gold on gap-up
days" position, which is why it is the less attractive version for an ensemble that
already holds no bonds: its diversification is of a different (directional) kind.

Ensemble impact - growth profile (`EnsembleParams.from_profile("growth")`,
`hf_ensemble_weights(md, "daily")`) plus this sleeve at allocation a, gross-long capped at
1.0 as in the ensemble (net, excess of ^IRX, 2010-03 -> 2026-09):

| Addition | a | Sharpe (IS / OOS) | CAGR | Vol | MaxDD | cost/yr | max gross incl. shorts |
|---|---|---|---|---|---|---|---|
| none (growth as is) | 0 | **1.31 (1.22 / 1.53)** | 11.5% | 7.4% | -12.2% | 2.8% | 1.0 |
| **default L/S k=1** | **0.25** | **1.37 (1.28 / 1.58)** | 12.0% | 7.4% | -12.6% | 3.2% | 1.0 |
| | 0.5 | 1.40 (1.31 / 1.61) | 12.5% | 7.6% | -13.0% | 3.6% | 1.0 |
| | 1.0 | 1.40 (1.31 / 1.60) | 13.5% | 8.3% | -13.7% | 4.3% | 1.5 |
| long-only k=0.5 | 0.25 / 0.5 / 1.0 | 1.36 / 1.38 / 1.37 | 11.9 / 12.3 / 13.1% | | -11.6 / -11.6 / -12.9% | | 1.0 |
| L/S k=0.5 | 0.25 / 0.5 / 1.0 | 1.38 / 1.40 / 1.37 (OOS 1.67 / 1.75 / 1.80) | 12.3 / 13.0 / 14.4% | | -12.2 / -12.4 / -13.2% | | up to 1.5 |

+0.06 to +0.09 ensemble Sharpe, +0.5 to +2.0 pp CAGR, MaxDD 0.4-1.5 pp worse, for
0.4-1.5 pp/yr of extra cost. The gain is what an uncorrelated 0.45-Sharpe stream should
add in theory and no more; it plateaus at a = 0.5 because beyond that the sleeve's own
vol (4.2% at a = 1) starts to matter. Note the L/S sleeve's shorts push total gross to 1.5
at a = 1.0 while gross *long* stays <= 1.0 (the cash-account constraint is on longs);
at a <= 0.5 the ensemble's gross never exceeds 1.0. During 09:30-16:00 the growth
profile holds only the reversal sleeve (<= 0.5 long), so there is no capital conflict.

## 6. Failure modes / when to turn this sleeve off

1. **It is a short-leg sleeve.** Net bp per active day: TLT short +4.2 (IS 4.9 / OOS 2.6),
   GLD short +5.9 (IS 4.5 / OOS 10.1); TLT long +1.8 (IS +3.8 / **OOS -3.9**), GLD long -1.1.
   Long-only k=1 is 0.04 Sharpe. If the paper account cannot short ETFs (a real cash
   account cannot), this sleeve should not run at k=1; the long-only k=0.5 version (0.37,
   IS 0.30 / OOS 0.52) is the fallback and is a different, TLT/GLD-directional bet.
   The brief's "shorts are a luxury" applies squarely here.
2. **Thin edge, one big year.** Net +2.3 bp per unit exposure per active day; 2011 alone is a third of the
   in-sample P&L (ex-2011 Sharpe 0.25); 31% of rolling 3-year windows are negative and
   2016-17 lost 2.7%/yr for two years running. A 2-3 year flat stretch is the *normal*
   experience of this sleeve, not a signal to stop. Turn-off rule: trailing 500-active-day
   **gross** mean (per unit exposure) below +2.5 bp/active day (cost plus a small margin;
   the full-sample gross is +4.3 bp) means the effect has left; set allocation 0.
3. **Cost is the binding constraint.** Breakeven 2.2 bp/side; the backtest assumes 1 bp.
   TLT quotes ~1 cent on ~$82 (1.2 bp full spread, 0.6 bp half), GLD ~1-3 cents on ~$400
   (< 0.4 bp), and MOO/MOC fills pay no spread. If measured live slippage vs the 09:30 /
   16:00 prints exceeds 1 bp/side on either ETF, stop - at 1.5 bp the sleeve is 0.26.
4. **Fill at the open.** As with the reversal sleeve, the signal is the 09:30 print and the
   fill is assumed at it. Live: compute the gap from the pre-market quote at ~09:28 (TLT and
   GLD trade actively pre-market, so the gap is well known) and send a market-on-open order.
   TLT's z-score needs Open[d]; a 1-minute-late fill is fine, a 10:00 fill is a different
   trade (the 08:30 / 10:00 data window is part of the story).
5. **Stress regimes.** On VIX > 20 days the TLT continuation is ~0 in-sample and -1.3 bp
   OOS (flight-to-quality gaps reverse). The optional `vix_max=20` stops trading then (+0.09
   Sharpe, MaxDD -9% -> -8%); the orchestrator's regime layer could equivalently scale this
   sleeve down at high VIX. Worst days: 2022-02-24 -2.4% (long TLT and GLD into the
   invasion-morning reversal), 2020-03-13 -2.3% (long GLD in the liquidation), 2013-09-18
   -2.3% (short GLD into the no-taper FOMC) - all macro-event reversals, which is the
   risk this sleeve is paid for.
6. **Data.** Yahoo's TLT/GLD opens are auction prints (fine). GLD's gap also embeds the
   London AM fix at 10:30 London = 05:30 ET, so part of the "overnight" move is already
   3-4 hours old at 09:30; that is the mechanism, not a bug. The 2010-11 period includes
   the GLD/TLT crisis regime that flatters the in-sample.
7. **Do not add EEM / VNQ / HYG / IEF because they screened well in-sample.** All four had
   IS t > 2.8 on the 2a table and all four were ~0 or negative OOS (section 2b); the IS-mined
   basket is 0.6 IS / -0.5 OOS. IEF/IEI/TIP/LQD are structurally untradable at a fixed 2 bp
   round trip (edge 0.4-1.5 bp/day).
8. **Shared code:** no bugs found. `report()` yearly table now prints a `Date` index
   header (cosmetic). `md.aux["^VIX"]` used with `.shift(1)` for the optional filter.
   On `HFConfig.wide()` the reversal sleeve ranks 300 stocks instead of 70, so its
   correlation numbers in section 5 were computed on `HFConfig()` (what is live).

## 7. Recommended params and ensemble allocation

`CrossAssetParams()` defaults as in section 3: `assets=("TLT","GLD"), k=1.0,
gap_window=20, sizing="fixed", long_only=False, weighting="ivol", vol_window=20,
vix_max=None`.

**Suggested allocation: 0.25** of the ensemble's gross budget, in the paper account only
while shorts are permitted there, as a *monitoring* allocation: it adds +0.06 Sharpe and
+0.5 pp CAGR to the growth profile for +0.4 pp MaxDD, is uncorrelated with everything
(|rho| <= 0.07), holds only TLT and GLD which nothing else in the system touches, and
uses capital during 09:30-16:00 when only the reversal sleeve (<= 0.5) is invested. Raise
to 0.5 only if 6+ months of live fills show realised cost <= 0.5 bp/side (at which the
sleeve is a 0.63). Set to **0** if (a) shorts are unavailable - long-only k=1 has no edge,
and long-only k=0.5 is a directional TLT/GLD bet the ensemble has not asked for - or (b)
the orchestrator applies a strict deflated-Sharpe gate: this sleeve's P = 0.13 fails it,
and I am not claiming otherwise. The honest forward expectation is ex-cash Sharpe ~0.3
(ex-2011 in-sample) with CAGR ~1.5% at full allocation; at 0.25 the downside is a
0.4%/yr cost drag if the effect is gone.

## 8. Insights for other sleeves

1. **Fixed-bp costs make the *high-vol expression* of a theme the only tradable one.** The
   gap-continuation edge in bp scales with instrument vol (TLT 3.9, IEF 1.5, IEI 0.4
   bp/day, t ~3 for both TLT and IEF) while the 2 bp round trip does not. IEF/IEI/TIP/LQD/
   HYG day trades are -0.2 to -4.8 Sharpe *with a real signal*. Any daily sleeve in low-vol
   ETFs should first check edge-in-bp against 2 bp; inverse-vol weighting actively hurts
   here because it up-weights exactly the assets with the worst edge/cost ratio. For
   rates exposure, use TLT (or TMF if ever added), never IEF/IEI.
2. **In-sample gap continuation in equity ETFs at |z| > 1 was real and reversed wholesale
   OOS**: SPY +7.0 bp (t 2.5), DIA +8.2 (2.9), XLE +8.0, XLU +5.9 in 2010-21; 2022+ SPY
   -5.8, XLE -17.7 (t -2.2), XLU -12.6 (t -2.1). Round 1's "no equity gap effect over 16
   years" is two opposite regimes cancelling. Regime sleeve: the sign of the trailing
   250-day sign(gap) x open-to-close covariance in SPY is a regime variable (positive
   2010-21, negative 2022+), like the overnight-autocorrelation flip noted in
   `intraday_momentum.md`.
3. **EEM and VNQ are the textbook in-sample trap**: continuation t 3.1 / 2.8 on 3000 days,
   11-12 bp at |z| > 1 (t 3-4), then -2 / +0.4 bp OOS. Two significant, economically
   plausible screens on 12 years of data flipped. Anyone selecting assets on a t > 2.5
   screen should expect roughly half of them to be regime artefacts.
4. **Nothing in the Asia/Europe ETFs' open.** EEM/EFA/FXI/EWJ: continuation basket gross
   Sharpe 0.3, fade basket gross -0.4; the stale-NAV gap neither continues nor fades at the
   daily horizon. EWJ does have a large *unconditional* intraday drift (+4.4 bp/day, t 4.1,
   2010-21; also EFA +3.1, t 2.5) with a *negative* overnight return (overnight note: EFA
   overnight +0.2 bp) - the "Japan/Europe ETF earns its return during US hours" pattern is
   the mirror image of the US overnight premium and has not been examined as a sleeve.
5. **Counter-trend gaps continue more than with-trend gaps in Treasuries** (TLT 5.7 vs 2.9
   bp, IEF 3.4 vs 0.0, t 4.1; TLT holds OOS 6.6 vs 1.3). A gap against the 200d trend is
   more likely a macro surprise than drift. Untested elsewhere; might sharpen any
   gap-based signal in rates.
6. **Treasury gap continuation is a calm-market effect** (VIX <= 20: 4.6 bp t 3.2 IS, 6.9 t
   2.8 OOS; VIX > 20: 3.9 t 1.0 IS, -1.3 OOS). The reversal sleeve found the opposite for
   equity gap *fades* (they need VIX > 18). Consistent picture: high VIX = liquidity-driven
   gaps that revert; low VIX = information-driven gaps that continue.
7. **The short leg is where gap continuation pays in TLT/GLD** (gap-down -> short: +4.2 /
   +5.9 bp net; gap-up -> long: +1.8 / -1.1). Both ETFs have positive unconditional
   intraday drift so this is not a drift artefact; the asymmetry is that gap-down days in
   these assets are more often "the flow has more to go" days. Any long-only design
   here is fighting the sign of the edge.
8. **Trial accounting:** 310 trials for a 0.44 net Sharpe with deflated P 0.13. If the
   orchestrator pools trials, add 310.
