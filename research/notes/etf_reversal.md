# Cross-sectional reversal among equity ETFs (`quantbot/strategies/hf_etf_reversal.py`)

Timeline: daily (`md.px_daily`). Universe: 25 equity ETFs from `HFConfig.wide()` - sectors
XLK XLF XLE XLV XLY XLP XLI XLU XLC XLRE XLB, industries SMH KRE XBI IBB ARKK VNQ, regions
IWM DIA QQQ SPY EEM EFA FXI EWJ (ARKK from 2014-10, XLRE 2015-10, XLC 2018-06; no
leveraged, bond or commodity ETFs). Costs 1 bp/side. Tuned on < 2022-01-01. rf = `md.cash_yield()`
(T-bill, mean 1.5% over 2010-06 -> 2026-09); every Sharpe below is excess of it unless marked
"gross" (zero cost, zero cash yield). **`n_trials = 145`.**

**Headline: NEGATIVE RESULT.** There is no cross-sectional reversal to harvest among equity
ETFs at 1 bp/side. The dollar-neutral long-losers / short-winners book is **~0.0 gross Sharpe**
at every formation horizon (overnight gap, 1, 3, 5, 10, 20 days), every holding period (same
session, 1-20 days), in both sessions (overnight and intraday), for raw, beta-adjusted and
z-scored rankings, on the full universe, US-only and sectors-only, and no VIX or dispersion
gate finds a sub-sample with enough edge to pay for itself. The intraday gap fade that works in
mega-caps (`reversal.md`) does **not** carry to ETFs: gross 1.2 bp/day on the L/S book vs a
2 bp/day round trip, in-sample only (IS gross Sharpe 1.2, OOS -0.9). The long-only variants
are equity beta (corr 0.87 with SPY, MaxDD -38%) with a Sharpe below SPY buy & hold. Adding
the sleeve to the growth ensemble at any allocation lowers its Sharpe (1.32 -> 1.20 / 1.04 /
0.70 at 0.25 / 0.5 / 1.0). **Recommended allocation: 0.** The file is kept so the finding is
reproducible and can be re-checked (`etf_reversal_weights(md)`).

## 1. Hypothesis and literature

Short-horizon reversal (Lehmann 1990; Jegadeesh 1990) is strongest in illiquid, high-idiosyncratic-
volatility names (Avramov, Chordia & Goyal 2006) and is best understood as the return to liquidity
provision against uninformed order flow (Nagel 2012; Da, Liu & Schaumburg 2014 - the liquidity
component of a move reverts, the news component does not). Round 1 found exactly this in mega-caps:
only the *intraday fade of the overnight gap*, only on high-VIX days, clears 2.5 bp. The question here
was whether the same effect exists one level up, among sector/industry/region ETFs, where costs are
2.5x lower and a dollar-neutral book is natural. Two priors pull in opposite directions: (i) ETF
prices are arbitraged to their baskets, so an ETF's relative move is mostly *information* about its
sector, not inventory pressure - the Nagel mechanism should be weak; (ii) the industry-level
literature finds *momentum*, not reversal, at 1-12 month horizons (Moskowitz & Grinblatt 1999),
with only a weak 1-week/1-month reversal in some samples. The sector-rotation-reversal folklore at
weekly horizons therefore had to be tested rather than assumed. Prior (i) and (ii) both held: there is
no reversal at any horizon, and the sector book is mildly *negative* (momentum) at 5-20 days.

## 2. Everything tested

Conventions: k = ETFs per leg; "ls" = long losers 0.5 / short winners 0.5; "long" = long losers 1.0;
"hedged" = long losers 0.5 / short SPY 0.5. `rel` = return minus beta(60d) x SPY return, `relz` =
rel / trailing 20d vol (x sqrt(horizon)), `raw` = plain return, `xs` = cross-sectionally demeaned.
Net = 1 bp/side + T-bill on idle cash, Sharpe excess of T-bill; gross = 0 cost, 0 cash. Full =
2010-06 -> 2026-09, IS < 2022, OOS >= 2022. BE = per-side cost (bp) at which mean net trading P&L is
zero. Baselines (not trials): SPY B&H Sharpe 0.81 (IS 0.93 / OOS 0.52), CAGR 14.9%, MaxDD -34%;
EW-25 ETF B&H 0.72 (0.83 / 0.43), CAGR 13.4%, MaxDD -34%.

### 2a. H1 - intraday gap fade at the ETF level, 09:30 -> 16:00 (44 trials)

Signal at 09:30 of day d: overnight gap close[d-1] -> open[d], raw or relative to SPY's gap
(beta-adjusted), optionally z-scored. Explicit 0.0 row at 16:00.

The whole story in one table - gross return of the ungated L3S3 relz book by lagged VIX bucket
(compare `reversal.md` 2d, where the mega-cap book earns 5 -> 14 bp/day across the same buckets):

| VIX(d-1) | days | gross bp/day (t) | IS bp | OOS bp |
|---|---|---|---|---|
| <= 14 | 1104 | 0.8 (0.9) | 1.6 | -3.9 |
| 14-18 | 1364 | 0.7 (0.8) | 3.1 | -4.3 |
| 18-22 | 773 | 1.4 (1.0) | 3.6 | -2.4 |
| 22-28 | 525 | 2.0 (0.9) | 1.3 | 3.2 |
| 28-40 | 272 | 0.8 (0.3) | 2.0 | -1.6 |
| > 40 | 51 | 18.3 (1.5) | 24.8 | -58.4 (n=3) |
| all | 4089 | **1.2** | 2.8 | -2.6 |

A full L/S round trip costs 2 bp/day. Nothing to gate on.

| Variant (ungated) | net Sharpe (IS / OOS) | CAGR | MaxDD | gross Sh (IS / OOS) | cost/yr | BE bp |
|---|---|---|---|---|---|---|
| raw k2 / k3 / k4 ls | -0.63 / -0.76 / -0.84 (OOS -1.3..-1.6) | -4.6% | -65..-69% | 0.35 / 0.38 / 0.41 (0.8-0.95 / -0.4..-0.6) | 8.5-9.0% | 0.6 |
| raw k2 / k3 / k4 long | -0.09 / -0.15 / -0.16 | -2% | -66% | 0.41-0.44 | 8.5-8.9% | 1.3-1.5 |
| raw k2 / k3 / k4 hedged | -1.07 / -1.35 / -1.52 | -5% | -57..-60% | 0.05-0.14 | 6.8-7.0% | 0.0-0.2 |
| rel k2 / k3 / k4 ls | -0.87 / -0.99 / -1.09 | -5.4..-6.0% | -69..-74% | 0.24 / 0.29 / 0.31 (~1.0 / -1.0..-1.15) | 8.7-9.2% | 0.4 |
| rel k2 / k3 / k4 long | -0.21 / -0.21 / -0.26 | -3% | -70% | 0.33-0.37 | 8.6-9.1% | 1.0-1.2 |
| rel k2 / k3 / k4 hedged | -1.27 / -1.50 / -1.76 | -6% | -62..-64% | -0.11..0.00 | 6.8-7.1% | <= 0 |
| relz k2 / k3 / k4 ls | -0.75 / -0.87 / -1.11 (IS -0.2..-0.5, OOS -1.9..-2.4) | -4..-5% | -64..-67% | **0.47 / 0.51 / 0.39** (1.16-1.22 / -0.9..-1.1) | 8.3-8.6% | 0.4-0.7 |
| relz k2 / k3 / k4 long | -0.11 / -0.11 / -0.16 (IS +0.1..0.2, OOS -0.7..-0.8) | -1..-2% | -61..-64% | 0.45-0.50 (0.75-0.81 / -0.1..-0.2) | 8.2-8.5% | 1.2-1.4 |
| relz k2 / k3 / k4 hedged | -1.31 / -1.51 / -1.77 | -5% | -57..-59% | 0.05-0.13 | 6.6-6.8% | 0.0-0.1 |
| relz k3 ls ivol / long ivol | -0.75 / -0.04 | -2.9% / 0.0% | -59% / -57% | | 8.1-8.2% | |

VIX gates on relz k3 (ramp (floor, span); span 0 = cliff):

| Gate | active | ls net (IS / OOS) | ls gross | long net (IS / OOS) | long gross | long BE | hedged net |
|---|---|---|---|---|---|---|---|
| ramp (18, 10) | 20% | -0.15 (0.02 / -0.53) | 0.34 | 0.19 (0.18 / 0.21) | 0.38 | 3.4 | -0.45 |
| ramp (15, 10) | 32% | -0.29 (0.01 / -0.90) | 0.40 | 0.20 (0.26 / 0.08) | 0.48 | 3.0 | -0.59 |
| VIX > 18 | 20% | -0.29 (0.03 / -0.90) | 0.43 | 0.32 (0.43 / 0.10) | 0.62 | 3.6 | -0.57 |
| VIX > 20 | 14% | -0.17 (0.02 / -0.55) | 0.40 | 0.27 (0.28 / 0.25) | 0.50 | 3.7 | -0.48 |
| VIX > 22 | 10% | -0.11 (0.01 / -0.36) | 0.34 | 0.13 (0.07 / 0.27) | 0.31 | 3.0 | -0.36 |

**Verdict: negative.** The ETF gap does not fade intraday. The residual/z-scored ranking has the
best in-sample gross (1.2) and it is entirely gone OOS (-0.9); breakeven is < 1 bp/side. The
VIX-gated *long* book is positive net (0.19-0.32) only because it is long the market at the open
on high-VIX days: its correlation with the mega-cap reversal sleeve is 0.81 and with SPY 0.50, and
`reversal.md` already showed that ramped-EW-at-the-open is Sharpe ~0.1 ex-cash. Hourly-panel check
(2023-10 -> 2026-09, core ETFs only, not counted as trials): L3-S3 gap book earns -4.0 bp/day
cumulative over the session (VIX > 18 days: +4.1 bp in the first hour, then -2.9, net +1.5 for
the day; VIX <= 18 days: -6.7 bp). Versus the mega-cap book's +6 bp first-hour spread the ETF
version is noise.

### 2b. H2 - multi-day relative reversal at 16:00, held `h` days as `h` tranches (29 trials)

Signal at 16:00 of day d: L-day return relative to SPY (relz unless stated), k = 3.

| L | h | ls net (IS / OOS) | ls gross (IS / OOS) | ls BE | long net (IS / OOS) | long CAGR / DD | long gross | hedged net | hedged gross |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | -1.04 (-1.14 / -0.86) | -0.17 (-0.26 / 0.00) | < 0 | | | | | |
| 1 | 3 | -0.57 | -0.03 | < 0 | | | | | |
| 3 | 1 | -0.60 (-0.54 / -0.73) | -0.04 (0.00 / -0.12) | < 0 | 0.39 (0.57 / -0.05) | 7.9% / -42% | 0.66 | -0.59 | -0.11 |
| 3 | 3 | -0.41 (-0.27 / -0.69) | 0.00 (0.11 / -0.21) | 0.0 | 0.55 (0.71 / 0.16) | 11.4% / -40% | 0.75 | -0.43 | -0.05 |
| 3 | 5 | -0.26 (-0.18 / -0.43) | 0.07 (0.12 / -0.02) | 0.5 | 0.62 (0.76 / 0.29) | 12.5% / -37% | 0.77 | -0.40 | -0.07 |
| 5 | 1 | -0.46 (-0.47 / -0.45) | 0.00 (-0.03 / 0.07) | 0.0 | 0.55 (0.65 / 0.31) | 11.9% / -43% | 0.79 | -0.29 | 0.11 |
| 5 | 3 | -0.35 (-0.31 / -0.41) | -0.01 | 0.0 | 0.61 (0.70 / 0.39) | 12.7% / -40% | 0.78 | -0.30 | 0.02 |
| **5** | **5** | **-0.27 (-0.24 / -0.34)** | **0.03 (0.02 / 0.05)** | 0.3 | **0.61 (0.71 / 0.35)** | **12.4% / -38%** | 0.75 | -0.36 | -0.06 |
| 10 | 5 | -0.31 (-0.26 / -0.43) | -0.08 | < 0 | | | | | |
| 20 | 5 | -0.27 (-0.04 / -0.73) | -0.09 (0.09 / -0.45) | < 0 | | | | | |
| 5 | 5, raw | 0.02 (-0.04 / 0.13) | 0.27 (0.18 / 0.45) | | | | | | |
| 5 | 5, raw z | -0.17 | 0.13 | | | | | | |
| 5 | 5, xs z | -0.12 | 0.16 | | | | | | |
| 5 | 5, rel (no z) | -0.27 | 0.00 | | | | | | |
| 5 | 5, k = 2 / 4 / 6 | -0.32 / -0.28 / -0.24 | -0.04 / 0.04 / 0.11 | | | | | | |

**Verdict: negative.** The L/S book is zero gross everywhere; tranching cuts costs from 3.6-4.5%/yr
(h = 1) to 1.5%/yr (h = 5) but there is nothing underneath. The one row with a positive gross
(raw 5d sort, 0.27, OOS 0.45) is not reversal: a raw sort in a universe with betas from 0.5 (XLU,
XLP) to 1.5 (ARKK, SMH) is long low-beta / short high-beta after up-weeks and the reverse after
down-weeks, i.e. a market-timing bet; beta-adjusting it (rel) takes the gross to 0.00. The long-only
books are equity beta: Sharpe 0.55-0.62 vs 0.72 for EW-25 B&H and 0.81 for SPY, drawdowns -37 to
-43%. Long relative losers is a *worse* way to hold the ETF universe.

### 2c. H3 - overnight vs intraday decomposition (8 trials + diagnostic)

Mean next-day return (bp) of the k = 3 long-losers-minus-winners book formed at 16:00 (relz), by
session, 2010-06 -> 2026-09:

| L | 16:00 -> 09:30 (t) [IS / OOS] | 09:30 -> 16:00 (t) [IS / OOS] | close-to-close | c2c days +1..+5 |
|---|---|---|---|---|
| 1 | -0.9 (-1.7) [-1.4 / 0.5] | +0.3 (0.4) [0.6 / -0.5] | -0.6 | -0.5, 0.0, 0.6, 1.2, -0.2 |
| 3 | -0.6 (-1.1) [-1.1 / 0.7] | +0.6 (0.8) [1.3 / -1.2] | 0.0 | 0.0, 0.5, -0.1, 0.4, 0.7 |
| 5 | -0.3 (-0.5) [-0.8 / 1.1] | +0.4 (0.5) [0.8 / -0.8] | +0.1 | 0.1, 0.2, 0.0, 0.4, 0.4 |
| 10 | -0.2 (-0.4) [-0.7 / 1.2] | +0.4 (0.6) [0.8 / -0.4] | +0.2 | 0.3, -0.1, 0.0, -0.5, -0.4 |

Engine runs of the 1-day-hold book split by session (k = 3, relz):

| L | session | ls net (IS / OOS) | ls gross | long net (IS / OOS) | long gross | long BE |
|---|---|---|---|---|---|---|
| 3 | overnight only (16:00 -> 09:30) | -1.98 (-2.40 / -1.28) | -0.30 (-0.60 / 0.23) | -0.01 (0.13 / -0.34) | 0.69 | 1.9 |
| 5 | overnight only | -1.89 (-2.36 / -1.13) | -0.15 (-0.47 / 0.39) | 0.13 (0.20 / -0.06) | 0.83 | 2.3 |
| 3 | intraday only (09:30 d+1 -> 16:00) | -0.99 (-0.82 / -1.35) | 0.16 (0.42 / -0.33) | -0.26 | 0.29 | 0.9 |
| 5 | intraday only | -1.02 (-0.95 / -1.19) | 0.11 (0.27 / -0.20) | -0.20 | 0.34 | 1.1 |

The *sign* pattern from Round 1 is reproduced - relative losers keep losing overnight (momentum
accrues overnight, Lou-Polk-Skouras) and recover slightly intraday (Bogousslavsky) - but the
magnitudes are 0.3-0.9 bp/day, an order of magnitude below the mega-cap effect and well below the
2 bp/day cost of trading either session daily. There is no holding window to design around.

### 2d. H4 - gating and sizing (37 trials)

Gross bp/day of the L5 h1 k3 relz L/S book by cross-sectional dispersion quartile (dispersion =
std of the day's ETF returns; the reversal-needs-dispersion hypothesis):

| quartile | 1d disp: all / IS / OOS | 5d disp: all / IS / OOS | 5d disp / 60d mean: all / IS / OOS |
|---|---|---|---|
| q1 low | -0.4 / -1.0 / 5.2 | -0.7 / -0.5 / -9.4 | 0.4 / -0.4 / 2.4 |
| q2 | -0.8 / -1.7 / 2.6 | -0.7 / -1.1 / 1.5 | -1.6 / -1.5 / -1.6 |
| q3 | 1.6 / 1.7 / 1.5 | -0.5 / -2.7 / 2.7 | -0.5 / 0.9 / -4.0 |
| q4 high | 0.1 / 2.5 / -2.4 | 2.4 / 7.2 / -1.5 | 2.0 / 1.1 / 4.1 |

No monotone pattern that survives the split. Gated engine runs (k = 3, relz, tranched):

| Book | gate | active | ls net (IS / OOS) | ls gross | long net (IS / OOS) | long DD |
|---|---|---|---|---|---|---|
| L5 h5 | VIX ramp (18, 10) | 50% | 0.09 (0.20 / -0.11) | 0.20 | 0.54 (0.58 / 0.43) | -32% |
| L5 h5 | VIX > 20 | 38% | 0.02 (0.05 / -0.04) | 0.15 | 0.60 (0.66 / 0.44) | -32% |
| L5 h5 | VIX > 25 | 18% | 0.19 (0.28 / 0.03) | 0.26 | 0.46 (0.46 / 0.47) | -32% |
| L5 h5 | disp5 / 60d > 1.25 | 21% | 0.07 (0.15 / -0.10) | 0.16 | 0.31 | -32% |
| L5 h5 | disp5 / 60d > 1.5 | 6% | 0.19 (0.20 / 0.19) | 0.23 | 0.15 | -32% |
| L3 h5 | VIX ramp (18, 10) | 50% | 0.06 (0.32 / -0.39) | 0.17 | 0.53 (0.60 / 0.33) | -32% |
| L3 h5 | VIX > 20 / > 25 | 38 / 18% | 0.01 / 0.13 (OOS -0.25 / -0.40) | 0.15 / 0.21 | 0.60 / 0.45 | -32% |
| L3 h5 | disp > 1.25 / 1.5 | 21 / 6% | 0.10 / 0.16 (OOS -0.42 / -0.04) | 0.20 | 0.31 / 0.14 | -32% |
| L5 h5 / L3 h3 | inverse-vol weights | 100% | -0.36 / -0.53 | -0.03 / -0.09 | long ivol 0.59 | -37% |

Sub-universes (k = 2 for the 11 sectors, k = 3 for US-only = universe minus EEM EFA FXI EWJ):

| Universe | L / h | ls net (IS / OOS) | ls gross (IS / OOS) | hedged net | hedged gross |
|---|---|---|---|---|---|
| sectors | 5 / 5 | -0.40 (-0.38 / -0.45) | -0.12 (-0.16 / -0.03) | -0.59 | -0.27 |
| sectors | 5 / 1 | -0.62 | -0.20 | -0.66 | -0.27 |
| sectors | 10 / 5 | -0.46 | -0.23 | -0.66 | -0.40 |
| sectors | 20 / 5 | -0.33 | -0.15 | -0.57 | -0.35 |
| sectors | 20 / 20 | -0.19 (0.00 / -0.62) | -0.03 (0.09 / -0.31) | -0.67 | -0.46 |
| sectors | 5 / 5 raw / xs | -0.26 / -0.15 | 0.02 / 0.11 | | |
| US-only | 5 / 5 | -0.27 | 0.02 | | |
| US-only | 3 / 5 | -0.19 | 0.13 | | |

**Verdict: negative.** The VIX-gated L/S books at 0.1-0.2 gross are the best of 145 trials and are
consistent with zero (their OOS is 0.03 to -0.4). The sector-only book is *negative* gross at every
horizon from 1 to 20 days (sector momentum, Moskowitz-Grinblatt), and the SPY-hedged long-losers
book is negative gross everywhere: relative losers underperform SPY going forward. The international
ETFs are not the culprit (US-only is the same ~0).

### Trial count

2a 44 + 2b 29 + 2c 8 + 2d 37 = 118 selection trials, plus the 25 one-at-a-time sensitivity runs in
section 4 (counted conservatively although they mostly repeat 2b) + 2 extra scorecard variants
(hedged multiday, gated gap long) = **145**. Baselines, the VIX/dispersion bucket diagnostics, the
H3 return decomposition and the hourly-panel profile were not counted (they select nothing).

## 3. Final scorecard

There is no configuration to recommend; the defaults in `EtfReversalParams()` are the
*pre-specified* H2 design (L = 5, h = 5, k = 3, relz, dollar-neutral), not an in-sample optimum,
so the OOS column is a blind test. `report()` output, start 2010-06-01, `n_trials = 145`:

```
etf_rev ls         | CAGR  -0.71% | Vol  7.16% | Sharpe -0.27 | Sortino -0.39 | MaxDD -30.17% | Calmar -0.02 | t -0.26 | PF 0.99 | exp L/S 0.47/0.47 | cost/yr 1.47% | days 4090
  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean 1.5% over the period)
  time in market 100.0% | turnover/day 0.35 | trades/day 9.23 | skew -0.04 | kurt 4.4 | best +3.44% | worst -3.48%
  Sharpe 95% bootstrap CI: [-0.72, 0.18]
  Deflated Sharpe: P(SR > null max of 145 trials = 0.66) = 0.000
  vs benchmark: corr 0.17 | beta 0.07

  Yearly:
       return      vol   sharpe   max_dd  days
2010    0.017    0.040    0.689   -0.027   150
2011   -0.004    0.056   -0.044   -0.044   252
2012   -0.047    0.046   -1.045   -0.060   250
2013   -0.002    0.049   -0.017   -0.042   252
2014   -0.066    0.056   -1.210   -0.083   252
2015   -0.028    0.067   -0.399   -0.084   252
2016   -0.054    0.071   -0.797   -0.071   252
2017    0.009    0.047    0.022   -0.049   251
2018    0.011    0.060   -0.115   -0.033   251
2019    0.057    0.060    0.617   -0.044   252
2020   -0.003    0.107   -0.002   -0.116   253
2021   -0.031    0.086   -0.330   -0.069   252
2022   -0.052    0.110   -0.620   -0.093   251
2023   -0.090    0.079   -1.792   -0.104   250
2024    0.051    0.077    0.045   -0.079   252
2025    0.075    0.065    0.527   -0.043   250
2026    0.059    0.090    0.606   -0.044   168

  In-sample / out-of-sample split at 2022-01-01:
                          days     cagr      vol   sharpe  sortino  max_drawdown   calmar
etf_rev ls in-sample      2919   -0.013    0.065   -0.241   -0.346        -0.236   -0.054
etf_rev ls out-of-sample  1171    0.007    0.085   -0.341   -0.484        -0.165    0.042
etf_rev ls full           4090   -0.007    0.072   -0.273   -0.386        -0.302   -0.024
```

Gross ex-cash Sharpe **0.03** (IS 0.02 / OOS 0.05); net ex-cash -0.18, CAGR -1.5%; breakeven
0.3 bp/side. Cost drag 1.47%/yr on turnover 0.35/day.

Long-only (`mode="long"`, same params):

```
etf_rev long       | CAGR  12.42% | Vol 20.22% | Sharpe  0.61 | Sortino  0.79 | MaxDD -38.02% | Calmar  0.33 | t  2.74 | PF 1.13 | exp L/S 1.00/0.00 | cost/yr 1.49% | days 4090
  time in market 100.0% | turnover/day 0.35 | trades/day 5.09 | skew -0.33 | kurt 11.6 | best +10.44% | worst -13.08%
  Sharpe 95% bootstrap CI: [0.16, 1.08]
  Deflated Sharpe: P(SR > null max of 145 trials = 0.66) = 0.416
  vs benchmark: corr 0.87 | beta 1.03
  Yearly return: 2010 +21.7, 2011 -2.6, 2012 +10.2, 2013 +25.4, 2014 +6.6, 2015 -0.5, 2016 +8.9, 2017 +23.0,
                 2018 -5.6, 2019 +35.7, 2020 +23.1, 2021 +19.6, 2022 -14.1, 2023 -1.7, 2024 +16.6, 2025 +28.7, 2026 +20.3%
  In-sample 0.709 (CAGR 13.6%, MaxDD -38.0%) | out-of-sample 0.352 (CAGR 9.5%, MaxDD -27.6%)
```

vs SPY B&H over the same window: 0.81 (0.93 / 0.52), CAGR 14.9%, MaxDD -34%. The long book is beta
1.03 to SPY with a lower Sharpe, a deeper drawdown and 1.5%/yr of costs. Gross ex-cash 0.75, BE 17.5
bp/side - the "robustness" to costs is just that a buy-and-hold-like book has little turnover.

Other modes (same params): `hedged` -0.36 (IS -0.27 / OOS -0.53), CAGR -0.4%, MaxDD -19%, gross
-0.06, corr SPY 0.05; `signal="gap"` ls k3 -0.87 (-0.26 / -2.09), CAGR -4.0%, MaxDD -64%, cost
8.4%/yr, gross 0.51 (1.22 / -0.89); `signal="gap"` long k3 with VIX ramp (18, 10): 0.19 (0.18 / 0.21),
CAGR 2.8%, MaxDD -38%, corr 0.81 with the mega-cap reversal sleeve.

## 4. Sensitivity (ls mode, one-at-a-time around the defaults; net Sharpe full / IS / OOS)

| param | value | full | IS | OOS | CAGR | MaxDD |
|---|---|---|---|---|---|---|
| lookback | 1 / 3 / **5** / 10 / 20 | -0.36 / -0.26 / **-0.27** / -0.31 / -0.27 | -0.28 / -0.18 / -0.24 / -0.26 / -0.04 | -0.51 / -0.43 / -0.34 / -0.43 / -0.73 | -0.1..-1.3% | -15..-34% |
| hold | 1 / 3 / **5** / 10 | -0.46 / -0.35 / **-0.27** / -0.34 | -0.47 / -0.31 / -0.24 / -0.26 | -0.45 / -0.41 / -0.34 / -0.51 | -3.2..-0.6% | -50..-20% |
| k | 2 / **3** / 4 / 6 | -0.32 / **-0.27** / -0.28 / -0.24 | -0.30 / -0.24 / -0.27 / -0.24 | -0.35 / -0.34 / -0.31 / -0.23 | -1.4..0.1% | -38..-20% |
| beta_window | 40 / **60** / 120 | -0.24 / **-0.27** / -0.21 | -0.24 / -0.24 / -0.16 | -0.26 / -0.34 / -0.32 | | |
| vol_window | 10 / **20** / 40 | -0.20 / **-0.27** / -0.26 | -0.21 / -0.24 / -0.25 | -0.19 / -0.34 / -0.29 | | |
| weighting | **eq** / ivol | **-0.27** / -0.36 | -0.24 / -0.29 | -0.34 / -0.49 | | |
| residual | **True** / False | **-0.27** / -0.17 | -0.24 / -0.13 | -0.34 / -0.25 | | |
| zscore | **True** / False | **-0.27** / -0.27 | -0.24 / -0.29 | -0.34 / -0.22 | | |

A flat plateau of -0.2 to -0.5 net (= 0 gross minus costs) across every parameter. The only
systematic effect is mechanical: longer holds cut turnover and lift the net Sharpe toward zero. There
is no region of the grid worth investigating further; the sensitivity table confirms the absence of
an effect rather than a fragile one.

## 5. Correlations (daily net returns, 2010-06 -> 2026-09; OOS 2022+ in brackets)

| | SPY | overnight sleeve | mega-cap reversal sleeve | etf_rev ls | etf_rev long | etf_rev hedged | etf_gap ls |
|---|---|---|---|---|---|---|---|
| etf_rev ls (default) | **0.17** [0.11] | **0.07** [-0.04] | **0.06** [0.03] | 1 | 0.53 | 0.77 | 0.02 |
| etf_rev long | 0.87 [0.81] | 0.30 [0.18] | 0.41 [0.46] | 0.53 | 1 | 0.55 | 0.00 |
| etf_rev hedged | 0.05 [-0.09] | 0.06 [-0.05] | -0.02 [-0.08] | 0.77 | 0.55 | 1 | 0.00 |
| etf_gap ls | 0.01 [0.06] | -0.02 [0.01] | 0.13 [0.12] | 0.02 | 0.00 | 0.00 | 1 |
| etf_gap long, VIX-gated | 0.50 [0.58] | 0.00 [-0.02] | **0.81** [0.80] | 0.06 | 0.42 | 0.01 | 0.27 |

(`overnight_weights(md)` and `reversal_weights(md)` run on the core `HFConfig()` through the engine
with T-bill cash.) The dollar-neutral books are indeed uncorrelated with everything (0.02-0.17) -
which would have been valuable if they had a positive mean. The long-only book is SPY (0.87). The
VIX-gated long gap book is 0.81 correlated with the existing mega-cap reversal sleeve: it is the same
"buy the open on scary days" beta, so even its small positive Sharpe adds nothing new.

**Ensemble impact** (growth profile, daily timeline, `hf_ensemble_weights` + this sleeve x allocation,
gross-long capped at 1.0 pro-rata; Sharpe excess of T-bill, full (IS / OOS), CAGR, MaxDD):

| | Sharpe | CAGR | MaxDD |
|---|---|---|---|
| growth profile alone | **1.32 (1.23 / 1.53)** | 11.6% | -12.2% |
| + etf_rev ls x 0.25 | 1.20 (1.12 / 1.39) | 10.8% | -11.3% |
| + etf_rev ls x 0.5 | 1.04 (0.97 / 1.19) | 10.0% | -13.1% |
| + etf_rev ls x 1.0 | 0.70 (0.67 / 0.77) | 8.3% | -16.7% |
| + etf_rev long x 0.25 | 1.19 (1.16 / 1.25) | 14.1% | -16.2% |
| + etf_rev long x 0.5 | 1.01 (1.02 / 0.98) | 16.0% | -23.8% |
| + etf_rev long x 1.0 | 0.70 (0.78 / 0.52) | 14.4% | -36.5% |

Every allocation lowers the ensemble Sharpe in both periods. The L/S book adds zero-mean noise plus
1.5%/yr of costs; the long book adds unconditioned beta.

## 6. Failure modes / why this does not work

1. **No liquidity-provision return at the ETF level.** ETF prices are pinned to their baskets by
   APs; a sector ETF's relative gap or 5-day move is information about the sector, not inventory
   pressure on one name. Nagel's VIX dependence, which is the whole mega-cap result, is absent here
   (gross 0.7-2.0 bp/day flat across VIX buckets vs 5-14 bp for stocks).
2. **Sector/industry returns trend, they do not revert.** The 11-sector book is negative gross at
   1, 5, 10 and 20 days. Anyone wanting a sector sleeve should test *momentum* (Moskowitz-Grinblatt
   at 1-12 months) and the overnight session, not reversal.
3. **Diversification is worthless without a mean.** Corr 0.02-0.17 with SPY and the other sleeves,
   gross Sharpe 0.03: it cannot be sized into anything.
4. **Survivorship** is minor here (all 25 ETFs exist today; three start late) and cannot rescue the
   result - if anything ARKK's inclusion from 2014 adds a high-vol name that the z-score handles.
5. **Data:** Yahoo ETF opens are auction prints (mean gap +4 bp, consistent with the overnight
   premium; no obvious bad prints). The hourly cache holds only the 24 core ETFs, so the first-hour
   profile in 2a was run on 15 of the 25 names.
6. **Turn-on rule:** none. If a future check shows the L/S relz book's trailing 250-day gross mean
   above ~3 bp/day (it has never been above ~2 for a full year) the question could be reopened.

## 7. Recommended params and ensemble allocation

`EtfReversalParams()` defaults: `signal="multiday", lookback=5, hold=5, k=3, mode="ls",
weighting="eq", residual=True, zscore=True, beta_window=60, vol_window=20, vix_floor=None`.
These are the pre-registered design, kept so the negative result is reproducible.

**Suggested allocation: 0.** Do not add this sleeve to any profile. The code should not be wired into
`hf_ensemble.py` (I did not modify it); if the orchestrator wants a monitoring hook, run
`etf_reversal_weights(md)` through the engine periodically and re-read section 6, item 6.

## 8. Insights for other sleeves

1. **The mega-cap gap fade is a single-name liquidity effect and does not aggregate.** At the ETF
   level the same construction (relative gap, z-scored, k = 3 per leg) earns 1.2 bp/day gross vs
   5-15 bp for stocks, with no VIX dependence. Sleeves that want to scale the reversal edge should
   go *down* in liquidity (more names, mid-caps from `HFConfig.wide()`), not up to sectors.
2. **Sector relative returns trend at 1-20 days.** The long-losers / short-winners sector book is
   negative gross at every horizon tested; the mirror (long relative winners) is a weak sector
   momentum signal worth testing in the *overnight* session together with the Lou-Polk-Skouras
   finding in `overnight.md` 2d (winners earn their premium overnight).
3. **Relative losers underperform SPY going forward.** The SPY-hedged long-losers book (0.5 losers /
   -0.5 SPY) is negative gross for every L / h: after a bad relative week a sector does not catch up.
   A long-biased ETF sleeve should never tilt toward recent relative losers.
4. **Raw-return sorts in a mixed-beta ETF universe are beta bets, not reversal.** The only positive
   gross L/S row (raw 5d sort, 0.27) disappears once beta-adjusted. Any cross-sectional ETF signal
   must be residualised against SPY before it means anything (XLU/XLP beta ~0.5, ARKK/SMH ~1.5).
5. **Confirmation of Round 1's session split, with tiny magnitudes:** relative losers lose a further
   -0.3 to -0.9 bp overnight and gain +0.3 to +0.6 bp intraday. The sign pattern (beta/momentum
   overnight, reversal intraday) is universal, but for ETFs it is not tradable.
6. **Dispersion gates select nothing here** (as in `reversal.md`): cross-sectional dispersion
   quartiles show no monotone pattern that survives the 2022 split.
7. **Deflated-Sharpe housekeeping:** 145 trials in this note; the ensemble's `n_trials_total` should
   grow by that amount even though nothing was adopted - the search happened.
