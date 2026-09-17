# International-ETF intraday drift ("mirror-image overnight premium") (`quantbot/strategies/hf_intl_intraday.py`)

Timeline: daily (`md.px_daily`). Long at 09:30, explicit 0.0 row at 16:00 (flat overnight),
long-only. Data: `MarketData(HFConfig.research(), refresh=False, intraday=False)`, 2010-01 ->
2026-09-16 (4201 days). Tuned on < 2022-01-01; OOS 2022-01 -> 2026-09. rf = `md.cash_yield()`
(^IRX); every Sharpe below is **excess of it**. Costs `cost_bps_for`: 1 bp/side for EWJ, EFA,
EEM, FXI, XLP/XLV/XLU, SPY/QQQ; 2 bp/side for the round-3 single-country / factor ETFs.
Default params: `IntlIntradayParams()` = EWJ only, equal weight, no gate. **`n_trials = 204`.**

**Headline: REJECT (clean negative).** The session decomposition confirms the hypothesis
*qualitatively* for every Asia/Europe ETF: overnight ~0 bp (EWJ -0.7, EFA +0.2, EWT +1.9,
EWG +0.5), intraday +2.4 to +4.8 bp/day, the exact mirror of SPY/QQQ (overnight +3.6/+5.1,
intraday +2.2/+2.6). But the *level* of the intraday drift is only 1-2.5 bp/day above SPY's
own intraday drift, and at a fixed 2-4 bp round trip only **EWJ** (+4.3 bp/day, t 4.4 full;
IS 4.4 t 4.2, OOS 3.9 t 1.8) clears cost with any margin. The pre-registered five-name basket
(EWJ, EWT, EFA, XLP, XLU) is **net Sharpe 0.20 (IS 0.39 / OOS -0.24)**, gross 0.83; the
EWJ-only sleeve (the file's default) is **net Sharpe 0.55 (IS 0.65 / OOS 0.35), CAGR 6.6%,
MaxDD -18.5%, cost 5.0%/yr, breakeven 2.1 bp/side** (IS 2.2 / OOS 1.8), deflated-Sharpe P
0.30. It is **not an independent stream**: correlation 0.59 with SPY, **0.51 with the live
reversal sleeve** (0.62 on VIX > 18 days, where all of its net P&L is earned), and its net
excess return regressed on SPY + reversal has intercept -0.1 bp/day (t 0.0, R^2 0.40).
Adding it to the growth profile **lowers** the ensemble Sharpe (1.32 -> 1.31 / 1.23 / 1.13 at
allocation 0.25 / 0.5 / 1.0; OOS 1.56 -> 1.45 / 1.30 / 1.05). Recommended allocation **0**.

## 1. Hypothesis and literature

The US equity premium accrues overnight (Cooper, Cliff & Gulen 2008; Lou, Polk & Skouras
2019; Bogousslavsky 2021), which the live overnight sleeve harvests in QQQ/SMH/IWM. The mirror
image: a US-listed ETF on a market that is *closed* during New York hours (EWJ - Tokyo closes
02:00 ET; EWY, EWT, EWH, EWA, INDA, FXI) spends the US session 09:30-16:00 in its *home
market's overnight*, so if the overnight premium is a property of the underlying market (as
the Nikkei-futures night-session literature suggests) it should show up as US-hours drift in
the wrapper, with ~zero US-overnight return (that window is the home market's trading day,
whose intraday return is ~0 by the same literature). Europe (EWG, EWU, VGK, EFA) overlaps
until ~11:30 ET, so it should be a weaker version; the Americas (EWZ, EWC) overlap fully and
should show nothing. Two supporting mechanisms were listed: stale-NAV catch-up to US-hours
information and US-investor flow, and Hendershott, Livdan & Rosch (2020) - low-beta assets
earn their premium intraday (defensives XLP/XLV/XLU: intraday +3.1/+2.7/+1.9 bp in
`overnight.md` 2a). `crossasset.md` 8.4 had already noted EWJ +4.4 bp/day intraday (t 4.1,
2010-21) and `overnight.md` 2a EFA overnight +0.2 bp; neither had been examined as a sleeve.
Prediction: a long-only 09:30 -> 16:00 basket of closed-market ETFs is a positive-Sharpe stream
that is ~0-correlated with the overnight sleeve (different session) and only modestly
correlated with the reversal sleeve.

## 2. Everything tested

### 2a. Session decomposition, all 22 tickers (22 screens). bp/day (t); IS 2010-21, OOS 2022+

Cost = per side (bp). "net margin" = IS intraday mean - 2 x cost (what a daily round trip leaves).

| Ticker | group | cost | ON IS (t) | **IN IS (t)** | ON OOS (t) | IN OOS (t) | IN full (t) | net margin IS | IN vol bp | net Sharpe uncond (IS / OOS) |
|---|---|---|---|---|---|---|---|---|---|---|
| **EWJ** | Asia | 1 | -1.4 (-0.8) | **4.4 (4.2)** | 0.9 (0.3) | 3.9 (1.8) | **4.3 (4.4)** | **+2.4** | 63 | **0.55 (0.65 / 0.35)** |
| EWY | Asia | 2 | 1.1 (0.5) | 2.2 (1.6) | 4.8 (0.9) | 5.1 (1.4) | 3.0 (2.1) | -1.8 | 92 | -0.19 (-0.38 / 0.11) |
| EWT | Asia | 2 | 0.1 (0.0) | 4.8 (4.0) | 6.6 (1.8) | 1.9 (0.7) | 4.0 (3.4) | +0.8 | 76 | -0.02 (0.19 / -0.39) |
| EWH | Asia | 2 | 1.1 (0.6) | 2.1 (1.9) | -1.3 (-0.4) | 3.3 (1.8) | 2.4 (2.6) | -1.9 | 61 | -0.45 |
| EWA | Asia | 2 | 0.1 (0.0) | 3.0 (2.1) | 0.8 (0.3) | 2.6 (1.1) | 2.9 (2.3) | -1.0 | 80 | -0.24 |
| INDA | Asia | 2 | 6.1 (2.4) | -2.3 (-1.5) | 1.0 (0.4) | -0.1 (-0.1) | -1.6 (-1.4) | -6.3 | 70 | -1.30 |
| FXI | Asia | 1 | -1.1 (-0.5) | 2.7 (1.9) | 0.3 (0.1) | 1.8 (0.6) | 2.5 (1.9) | +0.7 | 86 | 0.07 |
| EWG | Europe | 2 | 0.7 (0.3) | 2.4 (1.6) | -0.2 (-0.1) | 4.3 (1.8) | 2.9 (2.3) | -1.6 | 81 | -0.23 |
| EWU | Europe | 2 | 0.2 (0.1) | 2.2 (1.6) | 0.1 (0.1) | 4.9 (2.5) | 2.9 (2.6) | -1.8 | 72 | -0.26 |
| VGK | Europe | 2 | 0.9 (0.5) | 2.4 (1.7) | 1.3 (0.5) | 2.9 (1.3) | 2.5 (2.1) | -1.6 | 77 | -0.32 |
| **EFA** | Europe | 1 | 0.0 (0.0) | **3.0 (2.4)** | 0.8 (0.3) | 3.4 (1.7) | 3.1 (2.9) | +1.0 | 69 | 0.23 (0.22 / 0.26) |
| EWZ | Americas | 2 | 5.1 (1.8) | -4.8 (-1.8) | 1.5 (0.5) | 5.1 (1.4) | -2.0 (-0.9) | -8.8 | 139 | -0.70 |
| EWC | Americas | 2 | 2.5 (1.7) | 0.3 (0.2) | 0.8 (0.4) | 4.4 (1.7) | 1.4 (1.0) | -3.7 | 88 | -0.48 |
| VWO | EM | 2 | 2.9 (1.5) | -0.5 (-0.3) | 1.3 (0.5) | 2.0 (1.0) | 0.2 (0.2) | -4.5 | 76 | -0.81 |
| EEM | EM | 1 | 2.0 (1.0) | 0.2 (0.1) | 1.1 (0.4) | 3.2 (1.4) | 1.0 (0.8) | -1.8 | 80 | -0.22 |
| **XLP** | Defensive | 1 | 1.4 (1.5) | **3.6 (2.9)** | 0.5 (0.4) | 1.6 (0.7) | 3.0 (2.8) | +1.6 | 72 | 0.21 (0.36 / -0.15) |
| XLV | Defensive | 1 | 3.9 (3.5) | 2.3 (1.5) | -1.1 (-0.7) | 3.7 (1.5) | 2.7 (2.1) | +0.3 | 83 | 0.11 |
| **XLU** | Defensive | 1 | 1.3 (1.4) | **3.5 (2.1)** | 5.4 (3.7) | -2.4 (-0.8) | 1.8 (1.3) | +1.5 | 94 | -0.05 (0.25 / -0.74) |
| USMV | Defensive | 2 | 5.8 (4.7) | -0.1 (-0.1) | -2.0 (-1.7) | 4.6 (2.3) | 1.4 (1.2) | -4.1 | 70 | -0.61 |
| SPLV | Defensive | 2 | 3.8 (3.5) | 1.3 (1.0) | 1.3 (1.3) | 0.4 (0.2) | 1.0 (0.9) | -2.7 | 72 | -0.68 |
| SPY | control | 1 | 3.9 (3.1) | 2.2 (1.5) | 2.6 (1.4) | 2.5 (0.9) | 2.2 (1.8) | +0.2 | 81 | - |
| QQQ | control | 1 | 5.6 (4.0) | 2.6 (1.5) | 3.7 (1.5) | 2.5 (0.7) | 2.6 (1.6) | +0.6 | 102 | - |

Read-out:
1. **The decomposition is as predicted for every closed/overlapping market.** All 11
   Asia/Europe ETFs have overnight means within +-1.4 bp of zero (|t| < 1) and positive
   intraday means of 2.1-4.8 bp (t 1.6-4.2) in-sample; 10 of 11 stay positive OOS. The
   Americas (EWZ, EWC), broad EM (VWO, EEM) and INDA (whose Mumbai session runs to 06:00 ET
   and whose ADR-heavy basket trades US hours) show the opposite or nothing - also as
   predicted for markets that *overlap* US hours. The pattern is real; it is a session
   *re-labelling* of where the home-market premium lands, not new return.
2. **The level is the problem.** The intl intraday drift (2.4-4.3 bp) is only 0.2-2.1 bp above
   SPY's own intraday drift (2.2 bp), and SPY intraday is itself untradable at 2 bp/round
   trip. Against a fixed 2 bp (EWJ/EFA/FXI) or 4 bp (2 bp/side names) round trip, only EWJ
   keeps >= 2 bp/day net; EFA/XLP/XLU keep ~1-1.6 bp, the 2 bp-cost names are all negative.
   `crossasset.md` 8.1 ("fixed-bp costs make the high-vol expression of a theme the only
   tradable one") applies in full.
3. **Defensives are a different animal.** XLV/USMV/SPLV earn their premium *overnight* (t
   3.5-4.7), contradicting the Hendershott-Livdan-Rosch prior in this sample; XLP and XLU are
   split ~1:3 overnight:intraday in-sample and XLU's intraday flipped OOS (-2.4 bp). Not usable.
4. **OOS re-ranking.** EWT's intraday drift fell from 4.8 to 1.9 bp, EFA's rose 3.0 -> 3.4,
   EWU's 2.2 -> 4.9. The rank order of the IS screen did not persist - the usual half-of-them
   are-regime-artefacts warning from `crossasset.md` 8.3.

### 2b. Pre-registered selection and unconditional baskets (engine, net; 27 trials incl. per-ticker)

Rule (fixed before looking at OOS): keep tickers with IS intraday t > 2.0 AND IS intraday mean
> 2 x per-side cost AND IS overnight mean < IS intraday mean; controls excluded. **Selected:
EWJ, EWT, EFA, XLP, XLU.** Equal-weight, long 09:30 -> 16:00 every day.

| Basket | net Sharpe (IS / OOS) | gross Sharpe (IS / OOS) | CAGR | MaxDD | cost/yr |
|---|---|---|---|---|---|
| **pre-registered 5 (EWJ, EWT, EFA, XLP, XLU)** | **0.20 (0.39 / -0.24)** | 0.83 (1.05 / 0.34) | 2.9% | -16.5% | 6.1% |
| same, inverse-vol | 0.19 (0.40 / -0.28) | | 2.9% | -16.0% | 5.8% |
| **EWJ only** (the only name with >= 2 bp/day net margin) | **0.55 (0.65 / 0.35)** | 1.05 (1.19 / 0.79) | 6.6% | -18.5% | 5.0% |
| EWJ + EFA (the two 1-bp intl names) | 0.40 (0.44 / 0.31) | | 5.1% | -19.8% | 5.0% |
| EWJ + EWT + EFA (intl members of the rule) | 0.25 (0.37 / 0.03) | | 3.6% | -22.9% | 6.7% |
| EWJ + FXI (1-bp Asia) | 0.30 (0.38 / 0.12) | | 4.2% | -18.4% | 5.0% |
| Asia 7 EW | -0.22 (-0.22 / -0.23) | | -1.4% | -39% | 8.6% |
| Europe 4 EW | -0.16 (-0.23 / 0.02) | | -1.0% | -42% | 8.8% |
| Americas 2 / EM 2 / Defensive 5 EW | -0.69 / -0.51 / -0.19 | | -10 / -5 / -1% | -87 / -68 / -29% | 7-10% |

Intraday correlations among the selected names: EWJ-EFA 0.87, EWJ-EWT 0.77, EWJ-XLP 0.50,
EWJ-XLU 0.38, everything 0.5-0.9 with SPY intraday. The basket buys no diversification and
dilutes the one name with margin; every addition to EWJ lowers both IS and OOS Sharpe
(section 4). The pre-registered basket fails on its own terms (OOS negative). The
"2 x cost" bar in the rule was too lenient - it admits names that net ~1 bp/day, i.e. Sharpe
~0.2; a "net margin >= 2 bp/day" bar (one extra trial) keeps only EWJ, which becomes the
sleeve's default and the object of everything below.

### 2c. Conditioning, one family at a time (87 engine trials + 12 conditional-mean tables)

EWJ conditional intraday mean, bp/day (t) [n], IS 2010-21 | OOS 2022+ (signals known at 09:30 of d):

| Condition | IS bp (t) [n] | OOS bp (t) [n] | verdict |
|---|---|---|---|
| all days | 4.4 (4.2) [3021] | 3.9 (1.8) [1180] | |
| close[d-1] > 200d MA / below | **5.2 (4.6)** / 2.1 (0.9) | 3.2 (1.6) / **5.9 (1.1)** | trend gate helps IS, reverses OOS |
| open[d] > 200d MA | 5.5 (5.0) | 2.7 (1.3) | same |
| own gap < 0 / > 0 | 3.8 (2.4) / 5.0 (3.6) | 5.6 (1.7) / 2.3 (0.9) | gap-*up* continues IS, gap-*down* bought back OOS: flips |
| own gap z < -1 / -1..0 / 0..1 / > 1 | 4.9 / 3.4 / 5.8 / 2.7 | 6.1 / 5.3 / 2.3 / 2.3 | no monotone pattern in either half |
| SPY gap < 0 / > 0 | 4.5 (2.6) / 4.3 (3.3) | 6.4 (1.8) / 1.9 (0.7) | flat IS, gap-down OOS |
| SPY gap z > 1 | 9.4 (3.8) [500] | -0.1 (0.0) [186] | IS continuation gone OOS (cf. `crossasset.md` 8.2) |
| VIX(d-1) <= 15 / 15-18 / 18-22 / 22-28 / > 28 | 4.6 / 2.7 / **8.5** / 2.7 / 2.1 | -0.6 / -2.1 / **10.4** / 2.9 / 21.3 | IS: drift at all levels; OOS: only above 18 |
| VIX <= 18 / > 18 | 3.9 (3.8) / 5.3 (2.3) | **-1.4 (-0.7)** / **9.7 (2.6)** | OOS edge is entirely a VIX > 18 phenomenon |
| own RV20 < 20% / >= 20% | 4.2 (4.2) / 5.1 (1.4) | 1.8 (0.8) / 9.3 (1.8) | same as VIX: OOS edge in high vol |
| last session (d-1) down / up | 5.0 (2.9) / 3.7 (2.6) | **8.3 (2.5)** / 0.9 (0.3) | session-return mean reversion; IS gap 1.3 bp (t ~0.6) |
| last 5 sessions sum < 0 / > 0 | 4.4 (2.4) / 4.3 (3.4) | 8.8 (2.5) / 0.2 (0.1) | no IS effect, large OOS effect |
| last 5 gaps sum < 0 / > 0 | 3.5 (2.1) / 5.2 (3.9) | 5.3 (1.5) / 2.6 (1.1) | flips |

Engine runs, EWJ (and EWJ+EFA / prereg5 / intl-3 - same ordering, lower levels), net Sharpe full (IS / OOS):

| Gate on EWJ | Sharpe (IS / OOS) | CAGR | MaxDD | cost/yr | time in mkt | comment |
|---|---|---|---|---|---|---|
| **none (default)** | **0.55 (0.65 / 0.35)** | 6.6% | -18.5% | 5.0% | 50% | |
| own trend, close > 200d MA | 0.60 (**0.84** / 0.19) | 5.6% | -12.8% | 3.4% | 34% | best IS family -> worst OOS |
| own trend, open > 200d MA | 0.62 (0.94 / 0.09) | 5.6% | -12.5% | 3.4% | 34% | |
| SPY > 200d MA | 0.56 (0.72 / 0.19) | 5.8% | -17.8% | 4.3% | 43% | |
| own gap < 0 / > 0 | 0.36 (0.32 / 0.46) / 0.41 (0.61 / 0.00) | 4.0 / 4.0% | -19 / -14% | 2.5% | 25% | neither sign is robust |
| own gap z < -0.5 | 0.30 (0.21 / 0.52) | 3.2% | -16% | 1.5% | 15% | |
| SPY gap < 0 / > 0 | 0.45 (0.41 / 0.54) / 0.31 (0.50 / -0.08) | 4.6 / 3.4% | -19 / -17% | 2.2 / 2.8% | 22 / 28% | |
| **VIX <= 18 only (time-orthogonal to reversal)** | **0.12 (0.52 / -0.84)** | 2.0% | -20.9% | 3.0% | 30% | dead OOS |
| VIX > 18 only | 0.57 (0.41 / **0.91**) | 6.0% | -17.0% | 2.0% | 20% | = the reversal sleeve's regime |
| VIX <= 25 | 0.55 (0.75 / 0.10) | 5.8% | -18.5% | 4.4% | 43% | |
| own RV scale (16%/RV)^2, cap 1 | 0.48 (0.70 / 0.00) | 4.8% | -16.9% | 4.2% | 50% | Moreira-Muir hurts: OOS edge is in high vol |
| own RV scale (20%/RV)^2 | 0.51 (0.69 / 0.13) | 5.6% | -18.9% | 4.7% | 50% | |
| SPY RV scale (16%/RV)^2 | 0.58 (0.79 / 0.12) | 6.0% | -15.2% | 4.4% | 50% | |
| last session down (`session_down`, 1) | 0.61 (0.50 / **0.83**) | 5.5% | -15.1% | 2.1% | 21% | IS below unconditional; OOS carries it |
| last 5 sessions down | 0.53 (0.37 / 0.85) | 5.1% | -19.6% | 2.1% | 20% | |
| last session up | 0.23 (0.51 / -0.38) | 2.9% | -22.3% | 3.0% | 30% | |
| trend & 5 sessions down | 0.35 (0.54 / 0.00) | 3.1% | -7.5% | 1.3% | 12% | |
| trend & own gap < 0 | 0.45 (0.53 / 0.29) | 3.8% | -12.2% | 1.7% | 17% | |
| inverse-vol weighting (multi-asset baskets) | prereg5 0.19, EWJ+EFA 0.39, intl-3 0.28 | | | | | irrelevant |

Findings:
- **No gate improves EWJ in both halves.** Every family that raises the IS Sharpe (trend gates
  0.84-1.01 IS, RV scaling 0.70-0.79, VIX <= 25 0.75) is at 0.0-0.25 OOS, and every family
  with a strong OOS (VIX > 18 0.91, session_down 0.83-0.85, own/SPY gap-down 0.46-0.54) has
  an IS Sharpe *below* the unconditional 0.65. Picking any of the OOS winners would be
  selecting on the test set; the default therefore stays unconditional.
- **The OOS edge lives on high-VIX days.** 2022+: VIX <= 18 days -1.4 bp/day (t -0.7), VIX
  > 18 days +9.7 bp (t 2.6); in-sample both buckets were positive (3.9 / 5.3). Net of cost
  over the full sample the sleeve earns **+0.4 bp/day on VIX <= 18 days and +4.6 bp on VIX >
  18 days** (40% of days). That is exactly the regime in which the live reversal sleeve is
  long US mega-caps intraday, so the "time-orthogonal" version (VIX <= 18 only, 0.12 net, OOS
  -0.84) has nothing in it and the version with an edge is the one that overlaps.
- **Asia vs Europe.** The Europe group (EFA/EWG/EWU/VGK) has the same shape at a lower level
  and, for the 2 bp names, negative net; only EFA (1 bp) is marginally positive. The
  overlap-until-11:30 prediction (weaker than Asia) holds for the means (2.5-3.1 vs 2.4-4.3)
  but the difference is within noise, and it does not matter after costs.
- **Own-gap direction (stale-NAV question).** In-sample a gap *up* in EWJ continued (5.0 vs
  3.8 bp) - consistent with US-hours information not yet in the Tokyo close being extended;
  OOS a gap *down* was bought back (5.6 vs 2.3). The `crossasset.md` finding (EWJ gap neither
  continues nor fades) is the average of two opposite regimes. Not usable.

### 2d. Correlations and ensemble (24 ensemble mixes; section 5)

### 2e. Sensitivity and cost (32 sensitivity + 7 cost rows; section 4)

### Trial count

2a 22 screens + 2b 27 (1 basket net, 1 ivol, 5 groups, 20 per-ticker) + 2c 87 engine trials
+ 13 variant scorecards through the sleeve file + 24 ensemble mixes + 32 sensitivity rows =
**204** (the 12 conditional-mean tables, cost rows, causality check, drop-one-year and
regression diagnostics do not select anything and are not counted).

## 3. Final scorecard - `IntlIntradayParams()` defaults (EWJ, eq, gate none)

Runtime 0.04 s for the weights. Causality check: perturbing Close[d] of EWJ leaves the 09:30
row of day d unchanged and first changes the 09:30 row of d+1 (gate none / trend) or d+2
(session_down, via the shifted session return), as required. Row sums: exactly 1.0 at 09:30,
0.0 at 16:00.

`report()` output (net of 1 bp/side, cash at ^IRX, Sharpe excess of it; n_trials rounded):

```
==============================================================================================================
intl_intraday      | CAGR   6.63% | Vol  9.96% | Sharpe  0.55 | Sortino  0.75 | MaxDD -18.47% | Calmar  0.36 | t  2.83 | PF 1.14 | exp L/S 0.50/0.00 | cost/yr 5.04% | days 4201
  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean 1.5% over the period)
  time in market 50.0% | turnover/day 2.00 | trades/day 2.00 | skew 0.66 | kurt 15.1 | best +8.14% | worst -4.19%
  Sharpe 95% bootstrap CI: [0.09, 0.98]
  Deflated Sharpe: P(SR > null max of 200 trials = 0.68) = 0.296
  vs benchmark: corr 0.58 | beta 0.34

  Yearly:
       return      vol   sharpe   max_dd  days
2010    0.165    0.099    1.577   -0.075   252
2011   -0.008    0.147    0.016   -0.170   252
2012    0.076    0.074    1.024   -0.046   250
2013    0.251    0.096    2.386   -0.082   252
2014    0.030    0.079    0.416   -0.066   252
2015    0.077    0.091    0.853   -0.060   252
2016    0.039    0.085    0.454   -0.057   252
2017    0.092    0.041    1.935   -0.021   251
2018   -0.145    0.102   -1.670   -0.185   251
2019    0.096    0.069    1.071   -0.060   252
2020   -0.029    0.113   -0.234   -0.086   253
2021    0.160    0.078    1.936   -0.050   252
2022   -0.053    0.129   -0.517   -0.131   251
2023    0.174    0.085    1.348   -0.068   250
2024   -0.022    0.098   -0.679   -0.090   252
2025    0.126    0.129    0.672   -0.058   250
2026    0.152    0.129    1.338   -0.069   177

  In-sample / out-of-sample split at 2022-01-01:
                             days     cagr      vol   sharpe  sortino  max_drawdown   calmar
intl_intraday in-sample      3021    0.063    0.093    0.646    0.853        -0.185    0.339
intl_intraday out-of-sample  1180    0.076    0.115    0.350    0.529        -0.131    0.581
intl_intraday full           4201    0.066    0.100    0.547    0.753        -0.185    0.359
==============================================================================================================
```

Ex-cash (`cash_yield_annual=0`): CAGR 5.4%, Sharpe 0.57 (IS 0.66 / OOS 0.41), MaxDD -19.6%.
**Gross** (cost 0): Sharpe 1.05 (IS 1.19 / OOS 0.79), CAGR 12.1%, MaxDD -15.3%. Mean net
+2.7 bp/day (gross +4.7), hit rate 53.6%, 2.0 trades/day (one round trip in one ETF).

EWJ per year - gross intraday bp/day (t) | overnight bp/day | net sleeve return | SPY intraday bp/day:
2010 8.2 (2.1) | -3.1 | +16.6% | 3.0; 2011 2.1 | -7.2 | -0.8% | -0.7; 2012 5.0 | -1.1 | +7.7% | 3.8;
2013 11.1 (2.9) | -1.0 | +25.1% | 6.0; 2014 3.3 | -5.4 | +3.1% | 1.1; 2015 5.1 | -0.9 | +7.7% | -0.2;
2016 3.6 | -1.8 | +3.9% | 6.0; 2017 5.2 (3.2) | 3.6 | +9.2% | 2.3; **2018 -4.7 (-1.1) | -0.9 | -14.5% |
-6.8**; 2019 5.1 | 2.2 | +9.6% | 5.4; 2020 1.0 | 6.1 | -2.9% | 2.1; 2021 8.0 (2.6) | -7.1 | +16.0% | 3.8;
2022 -0.5 | -6.5 | -5.4% | -1.5; 2023 6.9 (2.0) | 0.9 | +17.4% | 7.3; 2024 -0.3 | 3.7 | -2.2% | 0.5;
2025 5.7 | 4.3 | +12.6% | 3.9; 2026 9.1 | 2.8 | +15.2% | 2.0. The EWJ and SPY intraday columns
move together (the sleeve's bad years are the US intraday's bad years: 2018, 2022, 2024).

Robustness (not trials): drop-one-year Sharpe 0.44 (ex-2013) to 0.69 (ex-2018); rolling
3-year Sharpe from -0.54 (window ending 2020-11) to +1.57 (2015-11), **negative in 16% of
windows**. Stress years: 2011 -0.8% (MaxDD -17%), **2018 -14.5%** (the only year with a
negative gross drift, -1.67 Sharpe), 2020 -2.9% (Feb 15 - Apr 15 2020: +0.9%; it was not the
crash but the choppy Apr-Jun recovery that lost), 2022 -5.3%, 2024 -2.2%.

Worst 5 days (net): 2025-04-08 -4.19% (SPY intraday -4.9%, VIX 47), 2020-04-07 -3.58% (SPY
-3.3%, VIX 45), 2015-08-25 -3.52% (SPY -4.2%, VIX 41), 2026-03-20 -3.20% (SPY -1.2%),
2011-08-08 -3.18% (SPY -4.0%, VIX 32). Best: 2025-04-09 +8.14%, 2011-03-15 +7.60% (the
post-Tohoku rebound), 2024-08-05 +4.40%. All tail days are high-VIX US-session moves:
**this is an intraday beta position**, skew +0.66 / kurtosis 15 because the biggest
intraday moves of the last 16 years were rebounds.

## 4. Sensitivity (one-at-a-time around the defaults; net Sharpe full / IS / OOS)

| Parameter | Value | full | IS | OOS | CAGR | MaxDD | comment |
|---|---|---|---|---|---|---|---|
| assets | **EWJ** / +EFA / +EWT / +FXI / +EFA+EWT / prereg 5 / EFA alone / EWT alone | **0.55** / 0.40 / 0.25 / 0.30 / 0.25 / 0.20 / 0.23 / -0.02 | 0.65 / 0.44 / 0.44 / 0.38 / 0.37 / 0.39 / 0.22 / 0.19 | 0.35 / 0.31 / -0.08 / 0.12 / 0.03 / -0.24 / 0.26 / -0.39 | 6.6 -> 0.5% | -18 -> -42% | monotone dilution; every addition hurts both halves |
| weighting | **eq** / ivol | **0.55** / 0.54 | 0.65 / 0.64 | 0.35 / 0.35 | | | irrelevant |
| gate | **none** / trend / session_down | **0.55** / 0.60 / 0.61 | 0.65 / 0.84 / 0.50 | 0.35 / 0.19 / 0.83 | 6.6 / 5.6 / 5.5% | -18 / -13 / -15% | IS and OOS disagree on which gate |
| ma_window (gate=trend) | 100 / 150 / **200** / 250 | 0.59 / 0.64 / 0.60 / 0.73 | 0.91 / 0.94 / 0.84 / 1.01 | 0.02 / 0.11 / 0.19 / 0.25 | 5.3-6.6% | -13 to -16% | smooth; OOS < 0.25 everywhere |
| trail_window (gate=session_down) | **1** / 2 / 3 / 5 / 10 | 0.61 / 0.48 / 0.52 / 0.53 / 0.50 | 0.50 / 0.42 / 0.39 / 0.37 / 0.51 | 0.83 / 0.61 / 0.78 / 0.85 / 0.49 | 4.7-5.5% | -11 to -20% | plateau 0.5-0.6; IS always below unconditional |
| vix_min | **None** / 15 / 18 / 20 / 25 | 0.55 / 0.44 / 0.57 / 0.50 / 0.16 | 0.65 / 0.40 / 0.41 / 0.30 / 0.01 | 0.35 / 0.53 / 0.91 / 0.89 / 0.44 | 6.6 / 5.3 / 6.0 / 5.1 / 2.3% | | 25 is a cliff only because time in market drops to 7% |
| rv_ref | **None** / 0.12 / 0.16 / 0.20 / 0.25 | 0.55 / 0.54 / 0.48 / 0.51 / 0.51 | 0.65 / 0.79 / 0.70 / 0.69 / 0.67 | 0.35 / -0.06 / 0.00 / 0.13 / 0.21 | 4.3-6.6% | -13 to -19% | flat full-sample; kills OOS |
| cost per side | 0 / 0.5 / **1.0** / 1.5 / 2.0 / 2.5 bp | 1.05 / 0.80 / **0.55** / 0.29 / 0.04 / -0.21 | 1.19 / 0.92 / 0.65 / 0.37 / 0.10 / -0.17 | 0.79 / 0.57 / 0.35 / 0.13 / -0.09 / -0.31 | 12.1 -> -1.1% | -15 -> -43% | **breakeven 2.08 bp/side** (IS 2.19 / OOS 1.80); each 0.5 bp costs 0.25 Sharpe |

No parameter produces a cliff in the full-sample number (0.44-0.73 for everything except
vix_min 25 and the multi-asset baskets, both of which are explained by exposure/cost rather
than by fragility). The problem is not roughness; it is that *within every family the IS and
OOS orderings are reversed*, which is what a beta position with regime-dependent conditioning
looks like, not what a stable anomaly looks like.

## 5. Correlations and ensemble impact

Daily *excess* returns vs `/tmp/qb_shared/reference_daily_returns.csv` (2010-03 -> 2026-09; OOS 2022+ in parentheses):

| Sleeve variant | overnight | reversal | ensemble_growth | SPY |
|---|---|---|---|---|
| **default (EWJ, unconditional)** | **-0.02 (-0.06)** | **0.51 (0.58)** | **0.31 (0.31)** | **0.59 (0.66)** |
| EWJ session_down | -0.01 (-0.04) | 0.46 (0.52) | 0.29 (0.28) | 0.44 (0.51) |
| EWJ trend 200 | 0.01 (-0.03) | 0.15 (0.11) | 0.11 (0.04) | 0.36 (0.38) |
| EWJ VIX > 18 | -0.04 (-0.05) | 0.62 (0.68) | 0.37 (0.38) | 0.50 (0.60) |
| EWJ + EFA | -0.02 (-0.07) | 0.56 (0.61) | 0.34 (0.32) | 0.64 (0.68) |
| pre-registered 5 | 0.00 (-0.05) | 0.59 (0.63) | 0.37 (0.34) | 0.67 (0.69) |

Default vs SPY intraday (09:30 -> 16:00) 0.81, vs SPY overnight -0.04, vs SPY close-to-close
0.58, beta 0.34. The zero correlation with the overnight sleeve is by construction (different
session) and holds. The 0.5 with the reversal sleeve is the finding: **on VIX > 18 days
(40% of days) the correlation is 0.62 and the sleeve earns +4.6 bp/day net; on VIX <= 18 days
the correlation is 0.03 and it earns +0.4 bp/day net** - the sleeve's P&L is concentrated in
the sessions in which the reversal sleeve is already long US intraday beta. Regression of
the sleeve's net excess return on SPY excess alone: alpha +0.3 bp/day, t 0.4; on SPY + the
reversal sleeve: **intercept -0.1 bp/day, t 0.0, R^2 0.40, loadings 0.26 SPY / 0.31
reversal**. Net of costs there is no return here that the ensemble does not already hold.

Growth ensemble (`EnsembleParams.from_profile("growth")`: overnight QQQ->QLD/SMH/IWM at 1.0
with the regime multiplier, reversal core-70 at 0.5, dd throttle 10%/0.5, `leverage_map`,
gross-long cap 1.0), reproduced in a scratch script and verified **identical** to the shared
reference (daily-return correlation 1.000000, max weight difference 0.0). Sleeve summed in via
`combine_weights` at allocation a, either unscaled or scaled by the same regime multiplier as
the overnight sleeve. Net, excess of ^IRX, 2010-03 -> 2026-09:

| Addition | a | Sharpe (IS / OOS) | dSharpe full (IS / OOS) | CAGR | MaxDD | cost/yr | 09:30 budget conflicts |
|---|---|---|---|---|---|---|---|
| none (growth as is) | 0 | **1.32 (1.22 / 1.56)** | | 11.6% | -12.2% | 2.8% | |
| **default, unscaled** | **0.25** | 1.31 (1.25 / 1.45) | **-0.02 (+0.03 / -0.11)** | 13.0% | -12.2% | 4.1% | 0% |
| | 0.5 | 1.23 (1.21 / 1.30) | -0.09 (-0.01 / -0.27) | 14.3% | -13.2% | 5.3% | 0% |
| | 1.0 | 1.13 (1.18 / 1.05) | -0.19 (-0.04 / -0.52) | 15.1% | -21.1% | 7.1% | 38% of days |
| default, regime-scaled | 0.25 / 0.5 / 1.0 | 1.38 / 1.38 / 1.30 | +0.06 / +0.06 / -0.02 (IS +0.10 / +0.14 / +0.14; **OOS -0.05 / -0.15 / -0.38**) | 12.6-15.6% | -12.2 to -15.2% | 3.7-6.5% | 0 / 0 / 10% |
| EWJ + EFA, unscaled | 0.25 / 0.5 / 1.0 | 1.25 / 1.13 / 1.01 | -0.07 / -0.19 / -0.31 | | | | |
| EWJ session_down, regime-scaled | 0.25 / 0.5 / 1.0 | 1.37 / 1.40 / 1.37 | +0.05 / +0.07 / +0.05 (IS +0.04 / +0.07 / +0.04; OOS +0.06 / +0.09 / +0.07) | 12.3-14.1% | -12.3 to -14.4% | 3.2-4.3% | 0 / 0 / 5% |
| EWJ VIX > 18, regime-scaled | 0.25 / 0.5 / 1.0 | 1.37 / 1.39 / 1.39 | +0.04 / +0.07 / +0.07 (IS +0.03 / +0.04 / +0.03; OOS +0.08 / +0.13 / +0.17) | 12.3-14.5% | -11.3 / -9.7 / -9.3% | 3.1-3.8% | 0 / 0 / 10% |

The default sleeve **lowers** the ensemble Sharpe at every allocation and fails OOS badly
(-0.11 to -0.52): it adds 1.2-4.3 pp/yr of cost and 1-4 pp of vol that is 0.6-correlated
with what the ensemble already holds during the day. Regime-scaling it (it is a long-beta
sleeve, so the `regime_multiplier` logic applies to it as it does to the overnight sleeve)
rescues the full-sample delta (+0.06) but not OOS (-0.05 to -0.38): 2022 and 2024 were
negative years for EWJ's intraday drift and the multiplier only halves the damage. The two
gated variants that do pass the ensemble test in both halves (+0.05 to +0.09) are the two
variants selected by their OOS performance (section 2c), so their OOS delta is not a test.
Capital: during 09:30-16:00 the growth profile holds only the reversal sleeve (<= 0.5 long,
active 39% of days). At a <= 0.5 there is never a conflict (0.5 + 0.5 = the 1.0 cash budget);
at a = 1.0 the pro-rata scale-down triggers on 38% of days (10% regime-scaled), i.e. on every
reversal-active day, which are exactly the days this sleeve wants to be full size.

## 6. Failure modes / when this sleeve should be turned off

1. **It is an intraday beta position, not an anomaly.** Beta 0.34 to SPY, 0.81 correlation
   with SPY's own 09:30-16:00 return, all five worst days are -3% to -5% US sessions at VIX
   32-47, and the alpha net of costs versus SPY + reversal is zero. Any US intraday selloff
   is its selloff; 2018 (-14.5%, the one year with a negative gross drift) is what a bad year
   looks like.
2. **Costs are 2 bp/day against a 4.3 bp/day gross drift.** Breakeven 2.1 bp/side full sample
   and 1.8 bp OOS; the acceptance gate wants >= 2x the assumed 1 bp, which it meets over the
   full sample and misses OOS. EWJ quotes ~1 cent on ~$70-80 (1.3 bp full spread, 0.7 bp half)
   and has deep MOO/MOC auctions, so 1 bp/side is realistic but not conservative; at 1.5 bp the
   sleeve is a 0.29, at 2 bp it is 0.04.
3. **The OOS edge is a VIX > 18 phenomenon.** 2022+: -1.4 bp/day on VIX <= 18 days vs +9.7 bp on
   VIX > 18 days. If this persists the unconditional sleeve pays 2 bp/day of cost on 60% of
   days for nothing, and the days it earns are the days the reversal sleeve is already long.
   A version gated on VIX > 18 (0.57, OOS 0.91) is *more* correlated with reversal (0.62).
4. **Conditioning is regime-dependent in both directions.** The own-200d-MA gate, the one
   conditioner validated for beta sleeves in `overnight.md`, raised the IS Sharpe to 0.84-1.01
   and delivered 0.02-0.25 OOS (below the MA EWJ earned +5.9 bp/day in 2022+, the highest
   bucket). Realised-variance scaling (`regime.md` insight 1) does the same (IS 0.70-0.79,
   OOS -0.06 to +0.21). Neither of the two validated regime tools transfers to this sleeve.
5. **Single-ETF concentration.** The default holds one ETF; Japan-specific US-hours shocks
   (2011-03-15: +7.6% intraday; BoJ announcements land during US hours, e.g. 2024-08-05 +4.4%)
   move it 3-8% in a session. Adding any second name (EFA, EWT, FXI) lowered both IS and OOS
   Sharpe because none of them clears its own cost.
6. **Turn-off / monitoring rule if it is ever run:** trailing 500-day gross intraday mean of
   EWJ below +2.5 bp/day (cost plus a small margin; full-sample 4.7) => allocation 0. It was
   below that level in 2011, 2014, 2016, 2018, 2020, 2022 and 2024.
7. **Shared code:** no bugs found. `md.aux["^VIX"]` used with `.shift(1)` for the optional
   gate; `reversal_weights` on the research config ranks 300+ stocks, so the ensemble
   reproduction used `ReversalParams(universe=tuple(HF_STOCKS))` to restrict it to the live
   core-70 universe (bit-identical to the reference). The reference `reversal` column in
   `reference_daily_returns.csv` is non-zero on 90% of days because it includes cash carry;
   use `md.aux["^VIX"].shift(1) > 18` (not `|return| > 0`) to identify its active days.

## 7. Recommended params and ensemble allocation

`IntlIntradayParams()` defaults: `assets=("EWJ",), weighting="eq", gate="none",
vix_min=None, rv_ref=None, max_gross=1.0`. The file keeps the gates as options so the
sensitivity tables are reproducible; none is recommended.

**Suggested allocation: 0.** Do not wire it into any profile. Round 3 acceptance gate:
1. Standalone net Sharpe >= 0.5 full **and** OOS >= 0.4: 0.55 full **pass**, 0.35 OOS **fail**
   (same sign of edge in both halves: yes).
2. Breakeven >= 2x assumed cost: 2.08 bp vs 1.0 **pass (marginal)**; OOS 1.80 bp fails.
3. Raises the growth ensemble Sharpe IS and OOS at 0.25 / 0.5 / 1.0: **fail** - unscaled
   -0.02 / -0.09 / -0.19 (OOS -0.11 / -0.27 / -0.52); regime-scaled +0.06 / +0.06 / -0.02 but
   OOS -0.05 / -0.15 / -0.38.
4. Smooth one-at-a-time sensitivity: **pass** (no cliffs), with the caveat that IS and OOS
   orderings reverse inside every family.
Fails two of four; deflated-Sharpe P 0.30 at 204 trials. **Verdict: REJECT.**

What would change my mind: (a) six months of live MOO/MOC fills on EWJ showing realised cost
<= 0.5 bp/side (the sleeve is a 0.80 at 0.5 bp, gross 1.05) - but even then its 0.5
correlation with the reversal sleeve caps its ensemble value at roughly +0.05; (b) the
`session_down` or `VIX > 18` conditioning continuing to hold on 2026-27 data that nobody has
looked at (IS support for both is weak: +1.3 bp/day, t ~0.6); (c) a cheaper wrapper for the
Japan overnight premium (e.g. Nikkei futures' night session directly, or a US-listed product
with a sub-1 bp spread), since the gross effect (t 4.4 over 16 years, 15 of 17 years
positive) is real and the round trip is what kills it. If the orchestrator wants a monitoring
position anyway, the least bad choice is `gate="session_down"` at allocation 0.25 (net 0.61,
IS 0.50 / OOS 0.83, cost 2.1%/yr, ensemble +0.05 in both halves when regime-scaled) - stated
as a SHADOW candidate, not a recommendation, because its selection rests on OOS data.

## 8. Insights for other sleeves

1. **The overnight/intraday split is a home-market clock, not a US phenomenon.** Every
   Asia/Europe ETF earns ~0 in the US overnight (its home market's trading day) and +2.4 to
   +4.8 bp in US hours (its home market's night). EWJ, whose home market is fully closed
   09:30-16:00 ET, is the cleanest (+4.3 bp, t 4.4, 15 of 17 years positive); the overlapping
   markets (EWZ, EWC, INDA) show the opposite. Anyone holding EFA/EEM/EWJ *overnight* in a
   US-overnight sleeve is holding the wrong session: `overnight.md` 2a's EFA/EEM overnight
   ~0 is this effect, and the same applies to any ex-US ETF added to the overnight sleeve.
2. **Session-relabelled beta is still beta.** The EWJ intraday drift is 0.81-correlated with
   SPY's intraday return and 0.5-correlated with the live reversal sleeve; its net alpha vs
   SPY + reversal is zero. A stream that is "in a different session" from the overnight sleeve
   is only diversifying if it is not in the *same* session as the reversal sleeve. Any new
   09:30 -> 16:00 long-only design should report its correlation with `reversal` first and
   its standalone Sharpe second.
3. **The US-hours drift in closed-market ETFs is a high-VIX phenomenon out of sample** (2022+:
   -1.4 bp on VIX <= 18 days, +9.7 bp on VIX > 18), the same Nagel-type pattern the reversal
   sleeve found for stocks (`reversal.md` 8.3), and the *opposite* of the overnight premium
   (which survives high vol but not downtrends, `regime.md` 8.3). Consistent picture across
   three notes: **buying the US open earns a premium in stress regimes; buying the US close
   earns a premium in calm uptrends.** Sizing the reversal-type daytime book up when VIX > 18
   and the overnight book on the 200d trend is the right division of labour; do not apply
   `regime_multiplier` (1/RV^2) to daytime long-beta sleeves - it removed exactly the days
   that paid here (OOS 0.35 -> 0.00).
4. **The validated conditioners do not transfer across sessions.** Own-200d-MA gate: +0.2 to
   +0.4 IS Sharpe on EWJ intraday, -0.2 to -0.3 OOS (below the MA was the *best* bucket in
   2022+). RV scaling: the same. Stop treating the 200d gate as a free option for any
   long-biased sleeve; it is validated for *overnight* beta, and here it selected against the
   stress days that carry the intraday drift.
5. **Cost arithmetic for the round-3 ETFs.** At 2 bp/side the single-country ETFs (EWY EWT EWH
   EWA INDA EWG EWU VGK EWZ EWC) need > 4 bp/day of gross edge for a daily round trip; the
   best of them (EWT, 4.8 bp IS) nets 0.8 bp and flipped OOS. Nothing in this set is
   day-tradable at the brief's cost model; their only role is multi-day holds where the 4 bp is
   amortised. USMV/SPLV earn their premium overnight (t 4.7 / 3.5) at 2 bp/side = the same
   problem as the unconditional SPY overnight (5.8 / 3.8 bp gross vs 4 bp cost).
6. **Low-vol / defensive sectors do not earn their premium intraday in this sample**
   (Hendershott-Livdan-Rosch did not replicate): XLV, USMV, SPLV overnight t 3.5-4.7, intraday
   t < 1.5; XLU's intraday flipped sign OOS. A "defensives intraday" sleeve is not worth a run.
7. **Regime flag for the daytime book:** the 250-day rolling mean of EWJ's intraday return is a
   cheap read on whether "buy the US open" is paying (it was negative through 2018, 2022 and
   2024, the reversal sleeve's three weakest OOS-era years after 2021). Untested as a gate for
   the reversal sleeve; reported, not used.
8. **Trial accounting:** 204 trials for a 0.55 net Sharpe with deflated P 0.30 and a REJECT
   verdict. If the orchestrator pools trials, add 204.
