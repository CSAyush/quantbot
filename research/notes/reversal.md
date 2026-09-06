# Cross-sectional short-term reversal in mega-caps (`quantbot/strategies/hf_reversal.py`)

Timeline: daily (`md.px_daily`). Universe: `md.stocks()` (70 mega/large caps, 2.5 bp/side).
Final rule: at 09:30, long the 7 names with the most negative beta-adjusted, vol-scaled
**overnight gap** (close[d-1] -> open[d]); flat at 16:00 the same day; exposure =
clip((VIX[d-1] - 18) / 10, 0, 1). Long-only by default (`mode="long"`); `"ls"` and
`"hedged"` variants are in the file. Tuned on < 2022-01-01. **`n_trials = 354`.**

All Sharpe ratios below are **in excess of the engine's 4% cash yield** (the current
`report()` convention). Sections 2a-2c were first run under the old rf = 0 convention;
those tables were re-generated after the shared-code change so everything here is
comparable. A sleeve that sits in cash 60-80% of the time looked ~1.0 Sharpe better under
the old convention (see 6, shared-code note).

**Headline:** classic close-to-close reversal does not clear 2.5 bp/side in this
universe (negative result, documented in 2a). The only reversal that does is the
*intraday fade of the overnight gap*, and only on elevated-VIX days. Ex-cash it is a
Sharpe ~0.75 / CAGR 7% / MaxDD -12% long-only sleeve that is stable across the 2022
split, has beta 0.27 to SPY and zero correlation with the overnight sleeve. The
market-neutral version has the better in-sample Sharpe (1.15) but its short leg died
out-of-sample (OOS 0.23). Suggested allocation: **0.10** (section 7).

## 1. Hypothesis and literature

Short-horizon reversal (Lehmann 1990; Jegadeesh 1990) is the best-documented
short-term anomaly, but Avramov, Chordia & Goyal (2006) show it is concentrated in
illiquid, high-turnover names, and Nagel (2012) interprets reversal profits as the
return to liquidity provision, which rises sharply with VIX and is ~zero in calm
markets. Blitz, Huij, Lansdorp & Verbeek (2013) find *residual* (beta-adjusted)
reversal is stronger and cheaper to trade than raw-return reversal. Bogousslavsky
(2021) and Lou, Polk & Skouras (2019) decompose returns into overnight and intraday:
reversal is an **intraday** phenomenon (losers rebound during the session), while
momentum/beta accrue overnight. Da, Liu & Schaumburg (2014) show that the reversal
comes from the liquidity component of a move, not the news component. Put together,
the prior for a 70-name mega-cap universe at 2.5 bp/side is: (i) raw close-to-close
reversal should *not* survive costs, (ii) if anything survives it is a residual,
vol-scaled signal traded intraday, and (iii) it should be conditioned on VIX. All
three were confirmed.

## 2. Everything tested

Conventions: net = default costs (2.5 bp/side stocks, 1 bp SPY) + 4% cash yield,
Sharpe in excess of 4%. Full = 2010-06 -> 2026-09, IS < 2022-01-01, OOS >= 2022.
"BE" = per-side cost (bp) at which mean net trading P&L (ex-cash) is zero. Every row is a
trial. Baselines (not trials): EW-70 buy & hold Sharpe 0.92 / CAGR 20.1% / DD -33%;
SPY B&H 0.66 / 14.9% / -34%; EW-70 held 09:30->16:00 only: gross 0.57, **net -0.40**
(12.6%/yr cost); EW-70 held 16:00->09:30 only: gross 0.77, net -0.38.

### 2a. Classic reversal: signal at 16:00, enter 16:00, exit next 16:00 (44 trials)

Long bottom-7 equal-weight (`L7`), or long bottom-7 / short top-7 at 0.5/0.5 (`L7S7`).
Signals: raw k-day return, residual (minus 60d beta x SPY), cross-sectionally demeaned
(`xs`), each optionally z-scored by 20d vol; plus the intraday-only and overnight-only
components of the 1d return.

| Signal | L7 net Sharpe (IS / OOS) | L7 CAGR | L7 MaxDD | L7 gross Sh | L7S7 net Sharpe (IS / OOS) | L7S7 gross Sh | L7S7 CAGR |
|---|---|---|---|---|---|---|---|
| raw 1d | 0.40 (0.57 / 0.01) | 11.6% | -49% | 0.84 | -0.94 (-0.82 / -1.18) | -0.02 | -7.5% |
| raw 1d, z | 0.09 (0.31 / -0.49) | 3.7% | -58% | 0.61 | -1.51 | -0.38 | -10.8% |
| raw 3d | **0.63** (0.84 / 0.11) | 17.9% | -44% | 0.89 | -0.58 (-0.26 / -1.22) | -0.01 | -3.4% |
| raw 3d, z | 0.46 | 12.2% | -46% | 0.78 | -0.88 | -0.19 | -5.2% |
| raw 5d | 0.57 (0.64 / 0.40) | 16.4% | -47% | 0.78 | -0.68 | -0.24 | -4.7% |
| raw 5d, z | 0.47 | 12.6% | -46% | 0.72 | -0.87 | -0.33 | -5.2% |
| resid 1d / 3d / 5d | 0.21 / 0.54 / 0.51 | 6-15% | -44..-53% | 0.65-0.82 | -1.37 / -0.75 / -0.83 | -0.40..-0.16 | -5..-11% |
| resid z 1d / 3d / 5d | 0.03 / 0.51 / 0.40 | 3-13% | -43..-53% | 0.56-0.83 | -1.68 / -0.88 / -0.99 | -0.55..-0.20 | -5..-12% |
| xs 1d / 3d / 5d (z) | 0.40 / 0.63 / 0.57 (0.16 / 0.58 / 0.51) | 12-18% | -44..-53% | 0.67-0.89 | -0.94 / -0.58 / -0.68 | ~0 | -3..-10% |
| intraday component 1d | 0.55 (0.72 / 0.13) | 15.6% | -46% | 0.98 | -0.81 | 0.13 | -5.9% |
| overnight component 1d | 0.14 (0.10 / 0.21) | 4.5% | -45% | 0.60 | -1.48 | -0.54 | -12.5% |
| intraday-resid / overnight-resid | 0.46 / 0.14 | 13% / 5% | -49% | 0.90 / 0.59 | -1.09 / -1.41 | -0.10 / -0.41 | -8..-11% |

**Verdict: negative.** The long-only loser portfolio is just a worse way to hold the
universe (0.40-0.63 vs 0.92 for EW buy & hold, with -45% drawdowns and 5-11%/yr of
costs). The market-neutral L/S book is ~zero **gross** (best gross Sharpe 0.13) and
strongly negative net; breakeven cost is < 1 bp/side. Avramov-Chordia-Goyal confirmed:
there is no close-to-close reversal to harvest in liquid mega-caps. Of the signal
components, the *intraday* part of yesterday's return is the only one with any
reversal information (gross 0.98 vs 0.60 for the overnight part) - the Bogousslavsky
sign is right, but the magnitude is too small for a 16:00 -> 16:00 trade.

### 2b. Timing variants of the same signals (58 trials)

| Timing | Signal at | Best long-only net Sharpe (IS / OOS) | Best L/S net Sharpe (IS / OOS) | L/S gross Sh | Comment |
|---|---|---|---|---|---|
| (c) 16:00 -> next 09:30 (overnight only) | 16:00 | 0.19 intraday-comp (0.36 / -0.26); raw 0.01 | -2.04 .. -2.74 | -0.86..-0.20 | Losers do **not** rebound overnight; L/S loses money gross. As predicted. |
| (b) 09:30 -> 16:00 with *yesterday's* close signal (1d/3d/5d raw, resid, xs, z) | 16:00 d-1 | all negative (-0.20 .. -0.64) | -0.83 .. -2.14 | -0.6..0.5 | Yesterday's close-to-close move carries no intraday reversal for today. |
| (b) 09:30 -> 16:00 with **today's overnight gap** (close d-1 -> open d) | 09:30 d | **0.72** raw (0.91 / 0.33); resid-z 0.81 (1.14 / 0.09) | 0.43 raw (0.93 / -0.49); resid-z 0.47 (1.16 / -0.84) | **1.72 / 2.04** | The one thing that works: the *gap* reverses during the session. |
| (b) 09:30 -> 16:00 with close d-2 -> open d | 09:30 d | -0.06 | -0.41 | 0.85 | Adding yesterday's move to the gap destroys it. |
| (b) gap z + yesterday's return z (continuation) / gap z - yesterday's z | 09:30 d | -0.24 / 0.03 | -0.86 | 0.6 | Same. The information is in the *gap*, not in the 2-day path. |
| (d) 3- and 5-day staggered holds | 16:00 | see 2a rows raw3/raw5 (that is what a k-day signal with 1-day rebalance of an equal-weight book is); explicit tranche versions not run separately because the 1-day-hold L/S book is already zero gross | | | |

**Verdict:** reversal in this universe is a **same-session gap fade**, nothing else.
Everything from here on is the 09:30 -> 16:00 gap trade. Note the L/S gross Sharpe of
2.0 against 12.6%/yr of costs (2 full round trips of a sum|w| = 1 book every day):
breakeven is 3.3-3.4 bp/side for L/S and 5.2-5.9 bp for long-only - net positive at 2.5 bp
but with no margin for slippage. Reducing turnover is the whole game (2d).

### 2c. Gap fade: construction (101 trials, all 09:30 -> 16:00, ungated)

Signals: `gap` raw; `gapz` = gap / 20d vol; `gapres` = gap - beta60 x mean universe gap;
`gapresz` = gapres / vol. N per leg in {5, 7, 10}; eq vs inverse-vol; long-only (sum
w = 1) vs L/S (0.5/0.5) vs long 0.5 / short SPY 0.5.

| Variant | net Sharpe (IS / OOS) | CAGR | MaxDD | gross Sh | cost/yr | BE bp |
|---|---|---|---|---|---|---|
| L7 eq gap | 0.72 (0.91 / 0.33) | 16.9% | -28% | 1.41 | 12.6% | 5.3 |
| L7 ivol gap | 0.86 (1.07 / 0.42) | 18.6% | -23% | 1.60 | 12.6% | 5.5 |
| L7 eq gapz | 0.62 (0.79 / 0.24) | 13.4% | -28% | 1.41 | | 4.6 |
| L7 eq gapres | 0.65 (0.95 / 0.02) | 15.4% | -41% | 1.34 | | 5.0 |
| L7 eq gapresz | 0.81 (1.14 / 0.09) | 16.9% | -32% | 1.61 | | 5.2 |
| **L7 ivol gapresz** | **0.96 (1.29 / 0.23)** | 18.4% | -23% | 1.82 | 12.6% | 5.4 |
| L5 ivol gapresz | 0.96 (1.38 / 0.08) | 19.7% | -35% | 1.76 | | 5.7 |
| L10 ivol gapresz | 0.89 (1.19 / 0.23) | 16.6% | -19% | 1.81 | | 5.1 |
| L7S7 eq gap | 0.43 (0.93 / -0.49) | 8.0% | -32% | 1.72 | 12.6% | 3.4 |
| L7S7 ivol gapresz | 0.59 (1.37 / -0.81) | 8.3% | -30% | **2.35** | | 3.4 |
| L10S10 ivol gapresz | 0.46 (1.21 / -0.83) | 6.9% | -28% | **2.52** | | 3.1 |
| L5S5 ivol gapresz | 0.66 (1.49 / -0.82) | 9.7% | -35% | 2.14 | | 3.7 |
| L7 gapresz, long 0.5 / short SPY 0.5 | 0.19 (0.73 / -0.86) | 5.0% | -22% | 1.95 | 8.8% | 2.0 |
| L10 gapresz hedged with SPY | 0.08 (0.59 / -0.93) | 4.3% | -20% | 2.14 | 8.8% | 1.9 |
| skip names with \|gap\| > 3% / 5% / 8% (L7 gapresz) | 0.81 / 0.86 / 0.80 | 16-18% | -32% | 1.6-1.7 | | 5.1-5.3 |
| skip \|gap\| > 3% / 5% / 8% (L7S7 gapresz) | 0.32 / 0.37 / 0.45 | 6-7% | -38% | 2.0-2.1 | | 3.0-3.3 |
| trade only names with gap z < -0.5 / -1 / -1.5 / -2 (L7) | 0.52 / 0.36 / 0.12 / 0.25 | 5-10% | -7..-17% | 1.1 / 0.7 / 0.3 / 0.4 | 7% / 3% / 1% / 1% | 4.9 / 5.3 / 4.0 / 6.2 |
| gapresz gate z < -0.5 .. -2 (L7) | 0.45 / 0.26 / -0.08 / -0.15 | | | | | |

Findings:
- **Residual + z-scoring helps ranking** (gross L/S 2.35 vs 1.72 raw), as in Blitz et al.
- **Inverse-vol weighting adds ~0.15 Sharpe and cuts MaxDD** (-23% vs -28..-32%).
- **The short leg is where the in-sample edge was and where it died.** L/S gross
  Sharpe is 2.0-2.5 but the IS/OOS split is 1.4 / -0.8; long-only is 1.3 / 0.2.
- The **outlier filter does nothing** (big gaps in mega-caps are mostly earnings and
  are already rare in the bottom-7).
- **Gating on signal strength does not work**: extreme gaps (z < -1.5) revert *less*
  (news), consistent with Da-Liu-Schaumburg. The fade is a liquidity effect on
  ordinary-sized gaps.
- Costs (12.6%/yr for a daily full round trip) are the binding constraint: breakeven
  5.4 bp for long-only, 3.4 bp for L/S. This is why 2d matters.

### 2d. Conditioning (Nagel): regime gates on the gap fade (74 trials, L7S7 and L7 gapresz, eq)

The cleanest evidence is the ungated L7S7 book's **gross** daily return by lagged VIX
bucket (this is the whole thesis in one table; t-stats on the gross mean):

| VIX(d-1) | days | gross bp/day (t) | net bp/day | IS gross bp | OOS gross bp |
|---|---|---|---|---|---|
| <= 14 | 1104 | 5.0 (4.2) | **0.0** | 5.9 | -0.1 |
| 14-18 | 1363 | 4.1 (3.1) | **-0.9** | 6.7 | -1.3 |
| 18-22 | 773 | 7.3 (3.8) | 2.3 | 10.2 | 2.3 |
| 22-28 | 525 | 10.8 (4.7) | 5.8 | 11.9 | 8.9 |
| 28-40 | 273 | 14.2 (4.1) | 9.2 | 17.2 | 8.0 |
| > 40 | 51 | 15.5 (0.9) | 10.5 | 21.1 | -50.6 (n = 3) |

The fade exists at all VIX levels but at VIX < 18 it is ~5 bp/day gross against a
5 bp round trip: exactly breakeven. It is monotonic in VIX in-sample and (weaker) OOS.

| Gate | active | L7S7 net Sharpe (IS / OOS) | L7S7 CAGR / DD | L7S7 BE | **L7 net Sharpe (IS / OOS)** | L7 CAGR / DD | L7 BE |
|---|---|---|---|---|---|---|---|
| none | 100% | 0.47 (1.16 / -0.84) | 7.7% / -35% | 3.3 | 0.81 (1.14 / 0.09) | 16.9% / -32% | 5.2 |
| VIX > 18 | 40% | 0.82 (1.24 / -0.01) | 8.9% / -11% | 4.9 | 0.92 (1.01 / 0.72) | 15.8% / -13% | 8.4 |
| VIX > 20 | 28% | **0.93 (1.24 / 0.23)** | 8.9% / -8% | 5.8 | 0.86 (0.93 / 0.70) | 14.1% / -13% | 9.5 |
| VIX > 22 | 21% | 0.84 (1.05 / 0.35) | 7.9% / -6% | 6.1 | 0.65 (0.66 / 0.62) | 10.7% / -11% | 9.0 |
| VIX > 25 | 13% | 0.80 (1.06 / 0.22) | 7.3% / -6% | 7.3 | 0.60 (0.61 / 0.58) | 9.5% / -13% | 11.0 |
| VIX > 30 | 6% | 0.48 (0.67 / -0.06) | 5.5% / -6% | 7.2 | 0.58 (0.62 / 0.45) | 8.2% / -11% | 16.2 |
| VIX/VIX3M > 0.95 / 1.0 / 1.05 | 19 / 7.5 / 2.7% | 0.84 / 0.71 / 0.49 (OOS -0.24 / -0.34 / -0.30) | | 6.3-10.7 | 0.62 / 0.56 / 0.54 (OOS 0.21 / 0.38 / 0.18) | | 9-25 |
| VIX up over 5d | 46% | 0.96 (1.46 / -0.05) | 9.6% / -13% | 4.9 | 0.94 (1.20 / 0.32) | 15.2% / -16% | 7.3 |
| VIX up 5d & > 18 | 22% | 0.82 (1.12 / 0.23) | | 5.8 | 0.87 (0.93 / 0.72) | 12.5% / -11% | 10.2 |
| x-sectional gap dispersion > 1.0 / 1.25 / 1.5% | 22 / 13 / 8% | 0.47 / 0.22 / 0.12 | | 3.6-4.8 | 0.46 / 0.24 / 0.21 | | 5.5-6.7 |
| gap dispersion / 60d mean > 1.2 / 1.5 | 25 / 15% | 0.36 / 0.42 | | 4.0-4.8 | 0.32 / -0.01 | | 2.6-5.1 |
| realised vol 10d > 15% / 20% | 34 / 17% | 0.86 / 0.76 (OOS 0.08 / 0.11) | | 5.2-6.2 | 0.75 / 0.70 (OOS 0.63 / 0.50) | | 7.9-10.5 |
| market gap < 0 / > 0 (long-only) | 44 / 56% | | | | 0.61 / 0.54 | | 5.7 / 4.8 |
| **ramp clip((VIX-18)/10)** | 40% (avg expo 20%) | 0.87 (1.15 / 0.23) | 7.6% / -5.9% | 6.0 | **0.76 (0.77 / 0.73)** | **11.2% / -11.8%** | **9.7** |
| ramp clip((VIX-15)/10) / (VIX-15)/15 / (VIX-20)/10 | | 0.89 / 0.86 / 0.80 (OOS 0.04 / 0.03 / 0.20) | | 5.1-6.5 | 0.83 / 0.81 / 0.69 (OOS 0.65 / 0.69 / 0.70) | | 8.1-10.6 |
| with VIX > 20: signal gap / gapz / gapres (L7S7) | 28% | 0.67 / 0.63 / 0.75 (OOS 0.50 / 0.52 / 0.30) | | 4.8-5.6 | 0.67 / 0.64 / 0.67 (OOS 0.93 / 0.83 / 0.71) | DD -28 / -17 / -24% | 7.7-8.8 |
| with VIX > 20: N = 5 / 10, eq / ivol (gapresz) | 28% | 0.96 / 0.75 (eq); 0.96 / 0.75 (ivol) | | 4.6-6.5 | 0.88 / 0.75 (eq); 0.90 / 0.76 (ivol) | | 8.1-10.0 |
| with VIX > 20: skip \|gap\| > 5% / 8% | 28% | 0.71 / 0.86 | | 4.9 / 5.4 | 0.80 / 0.82 | | 9.0 / 9.1 |
| with VIX > 20: long 0.5 / short SPY 0.5 | 28% | 0.65 (0.96 / -0.04) | 6.2% / -6% | 3.3 | | | |
| with VIX > 20: long-biased 0.7 / 0.3 | 28% | 1.05 (1.23 / 0.62) | 11.1% / -6% | 7.3 | | | |

Findings:
- **VIX level is the right conditioner** (Nagel). Every VIX-based gate improves OOS
  and cuts MaxDD by 2-5x and cost drag by 3-10x. The term-structure (VIX/VIX3M) and
  gap-dispersion gates are worse: too few days, and dispersion selects *news* days.
  Realised vol works but is a noisier VIX.
- **The gate costs in-sample Sharpe for the long-only book** (ungated 1.14-1.29 IS vs
  0.77-1.01 gated): the ramp keeps ~40% of days and gives up the small positive
  low-VIX P&L. This is a deliberate, prior-driven choice for cost robustness (breakeven
  9.7 bp vs 5.4 bp) and drawdown (-12% vs -23..-32%), not an in-sample optimum; the
  OOS improvement (0.73 vs 0.09-0.23) is therefore partly the gate being *right* and
  partly a choice informed by the VIX-bucket table above, which uses the full sample.
  Honest reading: the ungated ranking is a clean IS -> OOS test (and degrades sharply);
  the gate is well motivated but its OOS number is not a fully blind test.
- Ramp vs cliff: the linear ramp over VIX 18-28 is as good as any single threshold
  and avoids flipping the whole book on a 0.1 VIX move.
- **Market-neutral vs long-only:** L7S7 gated has the higher in-sample Sharpe (1.15 vs
  0.77), but its OOS is 0.23 vs 0.73 because the *short* (gap-up winners) leg stopped
  fading in 2022+ (hourly check in 2f: on VIX > 18 days since 2023-10 the winners
  returned +8.2 bp/day, same as the EW universe, i.e. zero fade). The long leg's edge
  over EW is stable: **losers +10.6 bp vs EW +8.6 bp per active day in 2023-26**
  (small), and 9.5%/yr gross vs 4.4%/yr for VIX-ramped EW over the full OOS. So:
  market-neutral was the better *historical* strategy, long-only is the one with
  evidence it still works. The brief prefers long-only, which settles it.

### 2e. Sensitivity and ablation around the final config (84 trials incl. re-runs; section 4)

### 2f. Hourly-panel checks (`md.px_intraday`, 2023-10 -> 2026-09, 730 days; not counted as trials)

Mean gross return (bp) of the L7 / S7 / EW books per intraday slot, VIX(d-1) > 18 days only (n = 239):

| slot | L7 losers | S7 winners (held long) | EW-70 |
|---|---|---|---|
| 09:30 -> 10:30 | **+6.3** | +0.3 | +4.0 |
| 10:30 -> 11:30 | -1.8 | +3.3 | -0.2 |
| 11:30 -> 12:30 | +2.6 | +3.7 | +1.8 |
| 12:30 -> 13:30 | +1.2 | +1.8 | +1.6 |
| 13:30 -> 14:30 | +1.8 | +5.2 | +3.3 |
| 14:30 -> 15:30 | +2.1 | -2.4 | -0.5 |
| 15:30 -> 16:00 | -1.6 | -3.7 | -1.3 |
| **cumulative** | **+10.6** | +8.2 | +8.6 |

On VIX <= 18 days (n = 491): losers -1.3, winners +4.0, EW +1.7 bp cumulative - the
losers *underperform* on calm days, which is what the gate removes. The whole L7 - S7
spread on high-VIX days is earned in the first hour (+6.0 bp) and then leaks back
(the L/S book was -3.6 bp from 10:30 to 16:00, +2.4 bp for the full session). Hourly-engine runs of the gated L7S7
book: enter 09:30 -> exit 10:30 Sharpe 0.84; 09:30 -> 16:00 -0.10; **10:30 -> 16:00
-1.34** (missing the first hour turns it negative). Intraday-panel and daily-panel gaps
agree (corr 0.991 per name).

Implications: (i) the fade is a first-hour liquidity effect (Nagel/Bogousslavsky);
(ii) a 09:30 -> 10:30 version would earn the same spread on 1/6 of the market exposure
but the round trip cost is identical, so at 2.5 bp the shorter hold only pays if the
first-hour edge is > 5 bp - it is on high-VIX days, marginally; (iii) **fill quality at
the open is the make-or-break implementation risk** (section 6).

### Trial count

2a 44 + 2b 58 + 2c 101 + 2d 74 + 2e 84 (38 robustness/sensitivity + 46 re-run
sensitivity under the excess-Sharpe convention, counted separately to be conservative)
+ 1 short-leg-alone = **354**. Cost-robustness runs, baselines, drop-2020 recomputations
and the hourly profile were not counted (they do not select anything).

## 3. Final scorecard

`ReversalParams()` defaults (n = 7, mode = "long", eq, residual, zscore, beta 60,
vol 20, vix_floor 18, vix_span 10). `report()` output, start 2010-06-01:

```
reversal           | CAGR  11.17% | Vol  9.24% | Sharpe  0.76 | Sortino  1.01 | MaxDD -11.82% | Calmar  0.95 | t  4.80 | PF 1.50 | exp L/S 0.10/0.00 | cost/yr 2.49% | days 4089
  (Sharpe/Sortino are excess of the 4.0% cash yield)
  time in market 19.8% | turnover/day 0.40 | trades/day 5.55 | skew 1.51 | kurt 30.5 | best +7.04% | worst -4.86%
  Sharpe 95% bootstrap CI: [0.37, 1.14]
  Deflated Sharpe: P(SR > null max of 354 trials = 0.73) = 0.546
  vs benchmark: corr 0.50 | beta 0.27

  Yearly:
       return      vol   sharpe   max_dd  days
2010    0.186    0.106    2.370   -0.077   150
2011    0.210    0.156    1.044   -0.109   252
2012    0.106    0.029    2.144   -0.019   250
2013    0.042    0.005    0.319   -0.003   252
2014    0.078    0.027    1.334   -0.006   252
2015    0.131    0.074    1.162   -0.049   252
2016    0.066    0.048    0.516   -0.036   252
2017    0.041    0.002    0.015    0.000   251
2018    0.148    0.105    0.993   -0.073   251
2019    0.071    0.025    1.167   -0.014   252
2020    0.209    0.198    0.848   -0.118   253
2021    0.024    0.061   -0.240   -0.051   252
2022    0.226    0.168    1.065   -0.101   251
2023    0.079    0.029    1.290   -0.015   250
2024    0.085    0.027    1.584   -0.016   252
2025    0.118    0.112    0.702   -0.062   250
2026    0.020    0.046   -0.201   -0.033   167

  In-sample / out-of-sample split at 2022-01-01:
                        days     cagr      vol   sharpe  sortino  max_drawdown   calmar
reversal in-sample      2919    0.112    0.091    0.771    1.030        -0.118    0.944
reversal out-of-sample  1170    0.112    0.097    0.733    0.981        -0.101    1.107
reversal full           4089    0.112    0.092    0.760    1.014        -0.118    0.945
```

Ex-cash (cash_yield_annual = 0, i.e. pure trading P&L): CAGR 6.97%, Sharpe 0.77
(IS 0.79 / OOS 0.75), MaxDD -12.3%, bootstrap CI [0.39, 1.15], deflated P = 0.57.
Gross of costs, ex-cash: Sharpe 1.04 (IS 1.04 / OOS 1.05), CAGR 9.7%.
Cost drag 2.5%/yr (2.3% IS, 2.9% OOS - the sleeve was active 48% of OOS days vs 36% IS).
**Breakeven cost: 9.7 bp/side full, 10.2 IS, 8.7 OOS** (vs 2.5 bp assumed): the
long-only sleeve survives a 3-4x cost miss. At 5 bp/side net Sharpe is 0.5, at 7.5 bp 0.2.
Active-day statistics: 1525 active days (38%), mean +7.2 bp, hit rate 55%, worst day
-4.9% (2025-04-09), best +7.0%.

Alternative modes with the same params (for the orchestrator):

| mode | net Sharpe (IS / OOS) | CAGR | MaxDD | cost/yr | BE bp (full / OOS) | corr SPY | deflated P |
|---|---|---|---|---|---|---|---|
| **long** (default) | 0.76 (0.77 / 0.73) | 11.2% | -11.8% | 2.5% | 9.7 / 8.7 | +0.50 | 0.55 |
| ls (0.5 / 0.5) | 0.87 (1.15 / 0.23) | 7.6% | -5.9% | 2.5% | 6.0 / 3.4 | -0.09 | 0.71 |
| hedged (0.5 stocks / -0.5 SPY) | 0.64 (0.87 / 0.13) | 5.7% | -4.7% | 1.75% | 3.3 / ~2 | -0.13 | 0.35 |

Ex-cash yearly returns, `ls`: 2010 +9.8, 2011 +16.8, 2012 +1.3, 2013 +0.3, 2014 +1.8,
2015 +4.7, 2016 +0.9, 2017 0.0, 2018 +7.9, 2019 -2.0, 2020 +16.4, 2021 -3.3, 2022 +5.4,
2023 -0.5, 2024 +2.7, 2025 -2.7, 2026 -0.5%. It paid in every stress year and has done
nothing since 2022. Dropping 2020 changes little (ls ex-cash 0.89 -> 0.85, IS 1.10 ->
1.14; long 0.77 -> 0.80): 2020 was not the source of the result.

## 4. Sensitivity (mode = long, one-at-a-time around defaults; net Sharpe excess of cash)

| param | value | IS | OOS | full | CAGR |
|---|---|---|---|---|---|
| n | 3 | 1.04 | 0.55 | 0.88 | 14% |
| | 5 | 0.85 | 0.80 | 0.84 | 12% |
| | **7** | **0.77** | **0.73** | **0.76** | 11% |
| | 10 | 0.65 | 0.68 | 0.66 | 10% |
| | 15 | 0.55 | 0.55 | 0.55 | 9% |
| vix_floor | 12 | 1.08 | 0.45 | 0.88 | 15% |
| | 14 | 0.97 | 0.58 | 0.85 | 14% |
| | 16 | 0.87 | 0.70 | 0.82 | 13% |
| | **18** | **0.77** | **0.73** | **0.76** | 11% |
| | 20 | 0.69 | 0.70 | 0.69 | 10% |
| | 22 | 0.63 | 0.70 | 0.65 | 9% |
| | 25 | 0.69 | 0.70 | 0.69 | 9% |
| vix_span | 1 (cliff) | 0.98 | 0.73 | 0.90 | 15% |
| | 5 | 0.86 | 0.74 | 0.82 | 13% |
| | **10** | **0.77** | **0.73** | **0.76** | 11% |
| | 15 | 0.77 | 0.77 | 0.77 | 10% |
| | 20 | 0.82 | 0.76 | 0.80 | 10% |
| beta_window | 20 | 0.58 | 0.58 | 0.58 | 9% |
| | 40 | 0.75 | 0.80 | 0.76 | 11% |
| | **60** | 0.77 | 0.73 | 0.76 | 11% |
| | 120 | 0.75 | 0.84 | 0.78 | 11% |
| vol_window | 10 | 0.79 | 0.82 | 0.80 | 11% |
| | **20** | 0.77 | 0.73 | 0.76 | 11% |
| | 40 | 0.77 | 0.86 | 0.80 | 12% |
| | 60 | 0.76 | 0.79 | 0.77 | 11% |
| weighting | eq | 0.77 | 0.73 | 0.76 | 11% |
| | ivol | 0.79 | 0.78 | 0.79 | 11% |
| residual | True | 0.77 | 0.73 | 0.76 | |
| | False | 0.48 | 0.89 | 0.60 | 10% |
| zscore | True | 0.77 | 0.73 | 0.76 | |
| | False | 0.52 | 0.67 | 0.57 | 10% |
| skip_abs_gap | None | 0.77 | 0.73 | 0.76 | |
| | 5% / 8% | 0.71 / 0.72 | 0.67 / 0.74 | 0.70 / 0.73 | |

Everything is a plateau: no parameter moves the full-sample Sharpe by more than ~0.2
except the two signal-construction switches (residual and z-score each add ~0.15-0.2)
and a beta window that is too short (20d). Concentration helps in-sample (n = 3: 1.04)
and hurts OOS (0.55); n = 5-7 is the balanced range. Lower VIX floors buy CAGR
in-sample and give it back OOS; anything from 16 to 25 is fine. For the `ls` mode the
same grid (old convention, exp4) was equally flat: full 1.7-2.1 for every value with
VIX floor 16-25, n 3-15, beta 40-120, vol 10-60. The one "cliff" is the *absence* of a
VIX gate: ungated OOS is 0.09-0.23 (long) and -0.8 (ls).

## 5. Correlations

- Daily returns vs SPY close-to-close: **+0.50** (beta 0.27), long mode. It is long
  equity beta 09:30-16:00 on ~40% of days, all of them high-VIX days. `ls` mode: -0.09;
  `hedged`: -0.13.
- vs the **overnight sleeve** (`hf_overnight.py`, run through the engine with its defaults):
  **0.03** (long) / 0.03 (ls); OOS 0.04 / -0.01. Zero by construction - different
  sessions - and the two sleeves are active in complementary regimes (overnight needs
  SPY/QQQ above the 200d MA and a run of weak nights; this needs VIX > 18, i.e. it is
  most active exactly when the overnight sleeve is flat: 2011, 2018 Q4, 2020, 2022).
- vs EW-70 held 09:30 -> 16:00 with the same VIX ramp (the "pure beta" version of this
  sleeve): the long book earned 9.65%/yr gross vs 4.4%/yr for ramped EW over the full
  sample (OOS 10.2% vs 4.4%), so roughly half of the long-only return is cross-sectional
  selection and half is intraday market exposure on high-VIX days. The ramped EW book
  itself is Sharpe 0.09 net ex-cash: buying the market at the open on scary days is not
  by itself a strategy.
- vs the other sleeves (each run through the engine with its defaults, ex-cash daily returns):

| | rev_long | rev_ls | overnight | regime | intraday_mom | SPY |
|---|---|---|---|---|---|---|
| rev_long (full 2010-26) | 1 | 0.34 | **0.00** | **0.20** | **0.09** (2023-10+) | 0.50 |
| rev_ls (full) | 0.34 | 1 | 0.03 | -0.04 | 0.01 | -0.09 |
| 2023-10+ only: rev_long | 1 | -0.03 | 0.01 | 0.14 | 0.09 | 0.53 |

  The long sleeve is uncorrelated with the overnight sleeve (0.00) and the intraday
  momentum sleeve (0.09, hourly window), and only 0.20 with the regime-timing sleeve
  despite both being long beta - the regime sleeve is long in calm uptrends, this one in
  stress. Its only meaningful correlation is with SPY itself (0.50) on its active days.
  Since 2023-10 the long and ls versions have been uncorrelated with each other (-0.03),
  which is another way of saying the short leg is now noise.

## 6. Failure modes / when to turn it off

1. **Fill at the open.** The signal is the 09:30 auction print and the backtest fills at
   that print. Live, the gap must be computed from the pre-market quote (~09:28) and
   sent as a market-on-open order, or computed at 09:30 and filled ~1 minute later.
   The hourly panel says the whole edge is in the first hour and turns *negative* if the
   entry slips to 10:30; a 1-minute slip is probably fine for mega-caps (deep pre-market
   books), but a 15-minute slip is not. This is the single biggest implementation risk;
   monitor realised fill vs open print in paper trading.
2. **The edge is thin and decaying.** Gross 9.7 bp/active-day long-only, ~2 bp/day of
   cross-sectional alpha over EW in 2023-26. Ex-cash OOS CAGR 7% on a book that is 20%
   invested on average is good, but the deflated-Sharpe probability is only 0.55
   (long) / 0.71 (ls) after 354 trials. Treat it as a stress-regime satellite, not a core sleeve.
3. **It is long beta on the worst days.** Worst days (long): 2015-08-25 -4.9%,
   2025-04-08 -4.7%, 2018-02-08 -4.4% - all mornings where the gap-down names kept
   falling into the close; (ls): 2025-04-09 -3.6%, 2020-03-18, 2020-03-17. Kurtosis 30. The VIX ramp *increases* exposure
   into crashes - that is the point (liquidity provision), but it means the sleeve's
   drawdowns coincide with everyone else's. Size it for that.
4. **Earnings / news gaps.** The ranking does not know why a stock gapped; a -6%
   earnings gap in the bottom 7 does not revert (Da-Liu-Schaumburg). The outlier filter
   did not help on average, but it means single-name risk on earnings mornings; with 7
   names at ~14% each, a further -10% move in one costs 1.4% of the sleeve.
5. **Short leg (`ls` mode):** do not use without re-checking. Gap-up winners stopped
   fading in 2022+ (OOS 0.23; hourly: winners +8.2 bp/day = EW). If the orchestrator
   wants the -0.1 SPY correlation, use `mode="hedged"` (short SPY, 1 bp) rather than
   shorting 7 stocks, and expect Sharpe ~0.6 with OOS ~0.1.
6. **Turn off / monitor rule:** trailing 250-active-day mean of (long book gross return
   - EW-70 09:30->16:00 return). If it drops below +2 bp/day the cross-sectional part is
   gone and the sleeve is a VIX-timed beta bet; set allocation to 0.
7. **Survivorship.** The universe is today's mega-caps applied to 2010. A long-only
   loser portfolio benefits (every name in it survived and grew). The market-neutral
   book is the fairer test of the anomaly and is the one with the weaker OOS.
8. **$1,000 account.** 7 names at allocation 0.10 is ~$14 per name; requires fractional
   shares (`min_trade_dollars` = 5 is met). If only whole shares are possible, use n = 3
   at allocation 0.15 or skip the sleeve.
9. Shared-code notes (not bugs): (i) `report()` now subtracts the 4% cash yield in
   Sharpe/Sortino; the *first* versions of my tables (rf = 0) showed the gated `ls` book
   at Sharpe 1.88 (IS 2.19 / OOS 1.19) purely from carry on idle cash - any low-exposure
   sleeve should be read ex-cash. (ii) `md.aux["^VIX"]` on the row for day d is d's
   close; at 09:30 it must be `.shift(1)`-ed (done). (iii) `bootstrap_sharpe_ci` and
   `deflated_sharpe` take raw daily returns; `report()` passes excess returns, my ex-cash
   numbers use `cash_yield_annual=0` runs, which agree to 0.02.

## 7. Recommended params and ensemble allocation

`ReversalParams()` defaults: `n=7, mode="long", weighting="eq", residual=True,
zscore=True, beta_window=60, vol_window=20, vix_floor=18.0, vix_span=10.0,
skip_abs_gap=None`. `weighting="ivol"` is marginally better (0.79 / OOS 0.78) and
lowers drawdown; `n=5` is equally good. Both left at the simpler setting.

**Suggested allocation: 0.10 of the ensemble's gross budget.** Rationale: ex-cash Sharpe
~0.75 that is *identical* in- and out-of-sample, breakeven cost 4x the assumed cost,
MaxDD -12%, zero correlation with the overnight sleeve, active only ~40% of days and
only during the day, so its capital is free overnight and on calm days. Against it:
beta 0.5 correlation with SPY when active, deflated-Sharpe 0.55, thin cross-sectional
alpha since 2023. That combination argues for a small, non-zero weight rather than
either 0 or a core allocation. If the ensemble already has a lot of intraday equity
beta, or wants strictly market-neutral sleeves, set it to **0**: the market-neutral
version does not have OOS evidence, and the sleeve is not worth running for its beta.

## 8. Insights for other sleeves

1. **Reversal in mega-caps is intraday and only intraday.** Losers held 16:00 -> 09:30
   earn nothing (long) or lose (L/S, gross Sharpe -0.9); the same losers held 09:30 ->
   16:00 earn 5-15 bp/day gross. This is the mirror image of the overnight sleeve's
   finding that momentum/beta accrue overnight: **the overnight session belongs to beta
   and momentum, the intraday session to mean reversion.** An overnight sleeve should
   never hold short-term losers; an intraday sleeve should never hold short-term winners.
2. **The overnight gap is the signal, not yesterday's return.** Any 09:30 sleeve should
   use close[d-1] -> open[d]; the close[d-2] -> close[d-1] move has no intraday
   predictive power in this universe (all variants negative net). Adding yesterday's
   return to the gap *destroys* the signal. For the intraday-momentum sleeve: a
   first-hour continuation signal should be tested *conditional on a small gap*; big
   gaps mean-revert in the first hour (+6 bp on the L7 book 09:30-10:30 on VIX > 18 days).
3. **Nagel's VIX dependence is real for intraday liquidity provision** and is monotonic
   (gross 5 -> 14 bp/day from VIX < 14 to VIX 28-40). The overnight note found VIX level
   useless for the overnight premium; both are right - VIX predicts *reversal* returns,
   not *beta* returns. Regime sleeve: use VIX to scale mean-reversion/liquidity sleeves,
   the 200d MA to scale beta sleeves.
4. **Residual + vol-scaled signals beat raw returns** for cross-sectional ranking
   (gross L/S Sharpe 2.35 vs 1.72 raw). Use beta-adjusted, z-scored returns for any
   cross-sectional sort in this universe.
5. **Costs: a daily full round trip in stocks is 12.6%/yr and no cross-sectional
   signal here has more than ~6 bp/day of gross edge on calm days.** The only way a
   stock sleeve clears 2.5 bp is to trade a minority of days. The breakeven table
   (gated 9.7 bp vs ungated 5.4 bp) is a template: any stock sleeve should report
   breakeven bp/side and target > 7.
6. **The short side of mega-cap anomalies is fragile.** Winners' gap fade was the
   stronger leg 2010-21 and vanished in 2022+; the long leg's edge shrank but survived.
   Prefer long-only or SPY-hedged designs; treat a stock short leg's in-sample Sharpe
   as an upper bound.
7. **Ex-cash everything.** Under the old rf = 0 Sharpe the gated L/S sleeve showed
   1.88 / OOS 1.19; ex-cash it is 0.87 / 0.23. A sleeve in cash 80% of the time gets
   ~+1.0 Sharpe of pure carry. The shared code now subtracts the cash yield; compare
   any older sleeve notes with that in mind.
8. **First-hour profile (hourly panel, 2023-26):** on VIX > 18 mornings the EW-70
   universe earns +4 bp in the first hour and the biggest gap-down names +6.3 bp; on
   VIX <= 18 mornings the gap-down names earn *nothing* all day. Intraday sleeves on
   stocks should probably not trade at all when VIX < 16-18.
