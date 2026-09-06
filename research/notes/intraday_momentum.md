# Market intraday momentum sleeve (`quantbot/strategies/hf_intraday_momentum.py`)

Timeline: hourly (`md.px_intraday`, 2023-10-04 -> 2026-09-01, 730 trading days, 723 full
days; 7 half days are skipped). Weight set at the 15:30 print, explicit 0.0 row at the
exit stamp. OOS split 2025-09-01 (252 OOS days). Long-only by default; L/S reported.
**n_trials = 525.** Costs: default 1 bp/side (ETFs), 2 bp/side (UPRO/TQQQ/SSO/QLD).

**Headline: the Gao-Han-Li-Zhou intraday-momentum effect is gone in US index ETFs in
2023-26 (sign(first hour) -> last half hour earns ~0 bp, net Sharpe -1.7 in SPY).** What
survives is a small *reversal* into the close (~2 bp/day gross, ~= the round-trip cost),
and an apparently strong "first-hour-up -> hold overnight" effect that the 16-year daily
panel shows to be a regime artefact. Recommended ensemble allocation: **0-5%** (monitor only).

## 1. Hypothesis and literature

Gao, Han, Li & Zhou (2018 JFE, "Market intraday momentum") report that SPY's first
half-hour return, measured from the previous close (so it includes the overnight gap),
positively predicts the last half-hour return (1993-2013), strongest on high-volatility,
high-volume and macro-news days. Baltussen, Da, Lammers & Martens (2021 JFE) confirm it
in global index futures and attribute it to end-of-day rebalancing of leveraged ETFs and
dealer gamma hedging, implying it should be strongest where leveraged-ETF AUM is large
(QQQ/TQQQ, SPY/UPRO, IWM/TNA, SMH/SOXL) and in high-vol regimes. Elaut, Frommel &
Lampaert (2018) document time-of-day return seasonality more broadly. Our hourly data
gives r_first = P(10:30)/P(prev 16:00)-1, r_open = P(10:30)/P(09:30)-1,
r_day_so_far = P(15:30)/P(prev 16:00)-1, r_intraday_so_far = P(15:30)/P(09:30)-1, and the
target r_last = P(16:00)/P(15:30)-1 (the closing auction vs the 15:30 print). Hypothesis:
sign(r_first) -> position at 15:30, flat at 16:00, earns > 2 bp/day.

## 2. Everything tested

### 2a. Predictor screen: sign(x) -> last-half-hour return, bp/day (t-stat), 15 ETFs x 8 predictors (120 trials)

Full sample; IS / OOS bp in parentheses where informative. Positive = continuation.

| Ticker | r_first (Gao et al.) | r_gap | r_open | r_day_so_far | r_intraday_so_far | 12:30-13:30 hr | 14:30-15:30 hr |
|---|---|---|---|---|---|---|---|
| SPY | -0.3 (-0.4) | +0.5 (0.7) | 0.0 (0.0) | **-1.9 (-2.3)** | **-1.8 (-2.2)** | +0.2 (0.3) | -0.9 (-1.0) |
| QQQ | -0.4 (-0.4) | +0.8 (0.8) | +0.8 (0.8) | -2.0 (-2.0) | -2.1 (-2.1) | +0.8 (0.8) | -0.8 (-0.8) |
| IWM | +0.5 (0.5) | -0.3 (-0.3) | +0.5 (0.5) | **-2.1 (-2.3)** | **-2.2 (-2.4)** | -0.9 (-1.0) | -1.2 (-1.3) |
| SMH | -0.1 (-0.1) | +0.1 (0.0) | -0.3 (-0.2) | -3.2 (-1.9) | -3.8 (-2.3) | -0.2 (-0.1) | -2.7 (-1.6) |
| DIA | -1.1 (-1.6) | -0.2 (-0.3) | -0.7 (-1.1) | -1.0 (-1.4) | -1.5 (-2.2) | 0.0 (0.0) | -0.6 (-0.9) |
| TQQQ | -1.6 (-0.5) | +1.9 (0.6) | +1.7 (0.6) | -5.9 (-1.9) | -5.3 (-1.8) | +0.7 (0.2) | -1.8 (-0.6) |
| UPRO | -0.4 (-0.2) | +2.2 (0.9) | +0.1 (0.0) | -5.5 (-2.2) | -6.0 (-2.5) | +0.9 (0.4) | -2.5 (-1.0) |
| TLT | **+1.0 (2.2)** | +0.5 (1.1) | 0.0 (0.0) | +0.9 (1.9) | +0.8 (1.8) | +0.2 (0.5) | +0.9 (2.1) |
| GLD | +0.8 (1.3) | **+1.9 (3.3)**; IS 0.6 / OOS 4.2 | -1.0 (-1.7) | +1.1 (1.9) | -0.1 (-0.1) | +0.5 (1.0) | -0.3 (-0.5) |
| EFA | +1.1 (2.0) | +0.8 (1.4) | +0.4 (0.8) | -0.1 (-0.2) | -1.0 (-1.8) | 0.0 (-0.1) | -0.7 (-1.3) |
| XLK / XLF / XLE / EEM / HYG | -0.2 / 0.0 / -0.7 / -0.3 / +0.1 | | | -2.4 / -0.5 / -1.8 / -0.5 / +0.3 | -2.3 / -0.4 / -1.9 / **-1.7 (-2.8)** / +0.3 | | |

Read-out: (i) first-half-hour -> last-half-hour continuation is **absent in every equity
index ETF** (|t| < 1.7, mostly wrong-signed); (ii) the only consistent equity effect is a
**reversal** of the day's move into the close, 1.5-3.8 bp/day, t -2 to -2.5, same sign in
all 5 index ETFs and both leveraged ETFs, IS and OOS (SPY -2.1 IS / -1.5 OOS; IWM -2.5 /
-1.4; SMH -2.5 / -4.6); (iii) genuine *momentum* into the close exists only in **TLT and
GLD** (and EFA), i.e. it has migrated out of the equity indices where it was published.
Unconditional SPY last-half-hour mean is +0.08 bp (std 22 bp): no drift to harvest.

### 2b. Conditioning the reversal (explore, 65 trials): threshold, vol regime, volume, weekday

| Filter (SPY unless noted) | n | bp/day | t |
|---|---|---|---|
| reversal of r_intraday_so_far, all days | 568 | 1.8 | 1.9 |
| ... only if |z| = |r|/vol20 > 0.5 | 262 | 2.7 | 1.7 |
| ... |z| > 1.0 | 110 | 0.5 | 0.2 |
| ... |z| > 1.5 | 31 | -4.5 | -0.8 |
| IWM, all / |z|>0.5 / >1.0 / >1.5 | 568/273/115/37 | 3.3 / 4.0 / 5.0 / 6.7 | 3.1 / 2.3 / 1.7 / 1.5 |
| QQQ |z| > 1.5 | 40 | -1.2 | -0.2 |
| SPY prev-day VIX > 20 / <= 20 | 131 / 592 | 0.5 / 2.2 | 0.2 / 2.9 |
| SPY 20d RV > expanding median / <= | 318 / 251 | 2.7 / 0.7 | 1.8 / 0.6 |
| IWM 20d RV > median / <= | 260 / 309 | 3.4 / 1.7 | 2.1 / 1.3 |
| SPY 14:30 bar volume > 20d mean / <= | 252 / 451 | 0.4 / 2.8 | 0.2 / 3.6 |
| QQQ / IWM volume ratio > 1.3 | 123 / 126 | 4.4 / 4.5 | 1.2 / 1.3 |
| SPY by weekday Mon..Fri | ~145 each | 3.9 / 0.5 / 0.4 / 3.4 / 1.6 | 2.4 / 0.3 / 0.2 / 1.9 / 1.0 |
| Alternative timing: signal at 14:30, hold 14:30 -> 16:00 (SPY / QQQ / IWM / SMH) | 715 | -0.9 / -1.2 / -0.4 / +4.1 | -0.8 / -0.8 / -0.3 / 1.8 |

Contrary to the paper, **large moves do not matter more**: the reversal is roughly
constant in bp across |z| (so it is a fixed-bp closing-auction effect, not a
proportional one), and the largest moves (|z| > 1.5, n ~ 30-80) *continue* in SPY/QQQ.
The volume and VIX splits go the "wrong" way (quiet days revert more), the opposite of
the leveraged-ETF-rebalancing story. None of these filters is used: they add parameters
without adding a consistent edge.

### 2c. Engine backtests (210 trials), **net of default costs, ex-cash** (`cash_yield_annual=0`)

Sharpe is excess of cash throughout this section; `report()`'s CAGR includes the 4% cash
carry, these CAGRs do not. Day trade = enter 15:30, flat 16:00. Cost = 4.9%/yr for a
daily L/S round trip, 2.3-2.9%/yr for long-only.

**Plan item 1 - baseline sign(r_first), day trade:**

| Ticker | gross L/S Sharpe | net L/S Sharpe (CAGR, MaxDD) | net long-only Sharpe | IS / OOS net L/S |
|---|---|---|---|---|
| SPY | -0.24 | -1.67 (-5.7%, -16.8%) | -1.37 | -1.39 / -2.52 |
| QQQ | -0.26 | -1.42 (-5.9%, -17.8%) | -0.97 | -1.55 / -1.14 |
| IWM | +0.32 | -0.96 (-3.7%, -12.2%) | -0.99 | -0.51 / -2.03 |
| SMH | -0.04 | -0.72 (-5.4%, -23.9%) | -0.34 | -0.74 / -0.70 |
| DIA | -0.96 | -2.66 (-7.5%, -20.7%) | -2.05 | -2.23 / -4.05 |
| TLT | **+1.30** | -1.36 (-2.5%) | -0.01 | -0.89 / -2.80 |
| GLD | +0.78 | -1.29 (-3.1%) | -0.80 | -2.86 / -0.01 |
| TQQQ | -0.31 | -1.08 (-13.6%, -38.8%) | -0.72 | -1.21 / -0.79 |
| UPRO | -0.10 | -1.05 (-10.8%, -34.4%) | -0.86 | -0.88 / -1.58 |

The paper's trade loses ~2 bp/day (its cost) everywhere. **Leveraged ETFs do not help**:
TQQQ/UPRO have the same ~0 gross Sharpe with 3x the drawdown and 2x the cost; leverage
is a sizing choice, not a signal improvement.

**Plan item 2 - signal variants, day trade L/S, momentum (+1) vs reversal (-1):**

| Signal | SPY +1 / -1 | QQQ +1 / -1 | IWM +1 / -1 | SMH +1 / -1 |
|---|---|---|---|---|
| first | -1.67 / -1.20 | -1.42 / -0.91 | -0.96 / -1.60 | -0.72 / -0.64 |
| open (ex gap) | -1.41 / -1.45 | -0.66 / -1.67 | -0.97 / -1.58 | -0.75 / -0.61 |
| gap | -1.05 / -1.83 | -0.71 / -1.62 | -1.46 / -1.09 | -0.66 / -0.71 |
| day_so_far | -2.81 / **-0.07** | -2.33 / **-0.01** | -2.62 / **+0.05** | -1.79 / +0.42 |
| intraday_so_far | -2.71 / **-0.17** | -2.33 / **-0.01** | -2.66 / **+0.10** | -1.97 / **+0.60** |
| 12:30-13:30 hour | -1.22 / -1.65 | -0.66 / -1.67 | -1.84 / -0.71 | -0.74 / -0.62 |

Gross Sharpe of the intraday_so_far reversal: SPY 1.0, QQQ 0.9, IWM 1.4, SMH 1.0 (gross
bp/day 1.8 / 2.1 / 2.1 / 3.7). After 2 bp it is ~0. Threshold |z| > 0.5 / 1.0 / 1.5 on the
reversal: SPY 0.25 / -0.36 / -0.72; IWM 0.68 / 0.58 / 0.66. Vol filters: SPY -0.4 to -0.7
(all three), IWM +0.25 to +1.07 (rv_above_median best, IS 0.80 / OOS 1.46 but only 521 days).

**Plan item 3 - sizing** (reversal, day trade, L/S): fixed vs |z|-scaled capped at
0.5 / 1.0 / 2.0: IWM 0.10 -> 0.56 / 0.59 / 0.67; SPY -0.17 -> 0.28 / 0.07 / -0.10. Scaling
by |z| mostly cuts cost (turnover 1.0 -> 0.5/day), it does not raise gross Sharpe.
Vol-targeting cannot help a 30-minute holding period (vol is ~3% annualised already).

**Plan item 4 - exit variants** (long-only; L/S in parentheses):

| Signal -> exit | SPY | QQQ | IWM | comment |
|---|---|---|---|---|
| first(+1) -> 16:00 | -1.37 | -0.97 | -0.99 | the paper's trade |
| **first(+1) -> next 09:30** | **2.01** (0.78) | **1.62** (0.28) | 1.00 (0.07) | IS 1.77 / OOS 2.51 for SPY |
| first(+1) -> next 10:30 | 1.86 (0.70) | 1.21 (0.08) | 0.96 (0.19) | first hour after the open costs ~-3 bp |
| gap(+1) -> next 09:30 | 1.99 (1.04) | 1.75 (0.76) | 1.46 (0.67) | IS 2.24 / OOS 1.47: the gap is doing the work |
| open(+1) -> next 09:30 | 0.89 | 1.07 | - | first hour *ex* gap adds little |
| intraday_so_far(-1) -> next 09:30 | 0.74 (-0.69) | 1.02 (-0.17) | 1.15 (0.18) | |
| day_so_far(-1) -> next 09:30 | 1.07 (-0.14) | 0.92 (-0.36) | 0.81 (-0.14) | |
| **reference: unconditional long 15:30 -> 09:30** | **1.19** | **1.32** | **0.92** | CAGR 12.1 / 18.6 / 13.3%, MaxDD -16 / -19 / -21% |
| reference: unconditional long 16:00 -> 09:30 | 1.23 | 1.29 | 1.03 | |

Holding overnight turns a losing day trade into Sharpe 2 - but note every "-> next 09:30"
row is a long-overnight trade, and the unconditional overnight already has Sharpe 1.2-1.3
in this window (SPY +23%/yr period). The conditioning adds ~+0.7 Sharpe by *skipping* ~42%
of nights (those after a down first hour: SPY 15:30->09:30 = +2.0 bp vs +10.6 bp after an up
first hour, t 4.4). The 2x2 by sign(first) x sign(day_so_far) for SPY: (+,-) 18.5 bp (n 99),
(+,+) 8.1 bp (n 313), (-,-) 5.6 bp (n 215), (-,+) -6.6 bp (n 88). Entering at 16:00
instead of 15:30 is slightly better (SPY 2.21 vs 2.01) because the last half hour is
~-0.2 bp on those days. Shorts (L/S rows) destroy it: shorting overnight fights the premium.

**Plan item 5 - multi-asset baskets** (equal weight, gross <= 1):

| Basket | reversal day-trade L/S | reversal day-trade LO | first -> next open LO |
|---|---|---|---|
| SPY+QQQ | -0.08 | 0.15 | 1.87 (IS 1.71 / OOS 2.16) |
| SPY+QQQ+IWM+SMH | **0.26** (IS 0.06 / OOS 0.71) | **0.33** (IS 0.25 / OOS 0.46) | 1.81 |
| SPY+QQQ+IWM+DIA | -0.11 | -0.03 | 1.51 |
| IWM+DIA | -0.13 | -0.25 | 0.90 |
| SPY+QQQ+SMH / XLK+SPY+QQQ / SPY+QQQ+IWM | - | - | 1.87 / 1.85 / 1.68 |
| UPRO / TQQQ / UPRO+TQQQ / SSO+QLD (first -> next open LO) | - | - | 1.84 / 1.57 / 1.77 / 1.59 (CAGR 36 / 44 / 40 / 23%, MaxDD -20 / -24 / -22 / -16%) |

Diversifying across four highly correlated index ETFs barely helps (basket gross Sharpe
1.5 vs 1.0-1.4 single); costs are unchanged per dollar so net stays ~0.3.

**Overnight-leg refinements (first -> next open, SPY+QQQ, 12 trials):** threshold z > 0.25 /
0.5 / 1.0: 1.69 / 1.54 / 1.23; vix_above_median / vix_above_20 / rv_above_median: 1.45 /
0.66 / 0.79; |z|-scaled cap 0.5 / 1.0 / 2.0: 1.68 / 1.68 / 1.61. Nothing beats the plain rule.

### 2d. The 16-year daily-panel check (42 trials): gap sign -> open-to-close, and -> next overnight

`md.daily` Open/Close 2010-01 -> 2026-08, n = 4188 days. gap = Open_t/Close_{t-1}-1;
oc = Close_t/Open_t-1; on_next = Open_{t+1}/Close_t-1. bp/day of sign(gap) x target (t).

| Ticker | uncond. oc bp (t) | sign(gap)->oc | gap>0 oc / gap<0 oc | |z|>1 | sign(gap)->on_next | gap>0 ON / gap<0 ON | OLS b_gap on on_next (t) | OLS b_ccprev on oc (t) |
|---|---|---|---|---|---|---|---|---|
| SPY | 2.2 (1.8) | +0.3 (0.2) | 2.2 / 2.3 | +0.9 (0.2) | **-1.7 (-1.6)** | 1.7 / 6.0 | **-0.088 (-5.7)** | -0.042 (-3.6) |
| QQQ | 2.6 (1.6) | +0.7 (0.5) | 2.9 / 2.1 | +0.1 (0.0) | -1.8 (-1.5) | 2.9 / 8.0 | -0.080 (-5.2) | -0.049 (-4.0) |
| IWM | -0.1 (-0.1) | +0.5 (0.3) | 0.4 / -0.7 | -4.7 (-0.6) | -0.6 (-0.5) | 4.2 / 6.6 | -0.047 (-3.1) | -0.038 (-3.1) |
| DIA | 1.9 (1.6) | -0.3 (-0.2) | 1.5 / 2.5 | +3.8 (0.9) | -0.9 (-0.9) | 2.2 / 4.7 | -0.090 (-5.8) | -0.053 (-4.7) |
| SMH | 3.0 (1.3) | +3.0 (1.4) | 5.4 / -0.1 | +5.7 (0.7) | -2.8 (-1.6) | 4.6 / 12.1 | -0.046 (-3.0) | -0.072 (-6.1) |
| **TLT** | 1.7 (1.7) | **+3.0 (3.0)** | 4.7 / -1.3 | +4.8 (1.8) | -0.3 (-0.3) | -0.6 / -0.1 | +0.017 (1.1) | -0.010 (-0.9) |
| **GLD** | 0.1 (0.1) | **+2.1 (2.1)** | 2.0 / -2.3 | **+6.8 (2.6)** | -1.2 (-1.0) | 2.3 / 5.1 | -0.023 (-1.5) | -0.009 (-1.0) |

Per-year sign(gap)->oc t-stats for SPY: 2010 +0.2, 2011 +1.4, 2012 -1.4, 2013 +0.4,
2014 +2.0, 2015 +0.1, 2016 +0.4, 2017 -0.8, 2018 -0.2, 2019 -0.1, 2020 0.0, 2021 +1.0,
2022 +0.4, 2023 -1.0, 2024 +0.5, **2025 -1.8** (QQQ -2.1, IWM -2.2), 2026 +0.2.

Findings: (a) **no gap continuation and no gap fade in SPY/QQQ/IWM over 16 years** - the
open-to-close return is unconditional on the gap sign (both ~2.2 bp in SPY); what the
intraday session *does* reverse is the previous close-to-close return (b = -0.04 to
-0.07, t -3 to -6, all equity ETFs); (b) 2025 was a pronounced **gap-fade** year in
equities (gap>0 -> oc -7 bp, gap<0 -> +20 bp in SPY; QQQ -12 / +24), the tariff-headline
regime; (c) **gap continuation is real in TLT (t 3.0) and GLD (t 2.1; 6.8 bp at |z|>1,
t 2.6)** - the same two assets that show last-half-hour momentum on the hourly panel -
consistent with intraday momentum having left the equity indices after publication and
persisting in bond/gold ETFs where leveraged-ETF/gamma flows are not the marginal
end-of-day trader but slower macro allocators are; (d) **gap>0 predicts a LOWER next
overnight return** in every equity ETF, b_gap t = -5.7 (SPY), i.e. overnight returns
mean-revert day to day over 2010-2023 - the *opposite* of the 2023-26 hourly-sample result
that motivated the "first-hour-up -> hold overnight" variant.

Sub-period check for SPY, gap>0 -> next overnight vs gap<0, and the long-only "hold
overnight iff gap>0" net Sharpe (2 bp round trip) vs unconditional overnight:

| Period | gap>0 ON bp | gap<0 ON bp | t(sign) | LO gap>0 net SR | uncond ON net SR |
|---|---|---|---|---|---|
| 2010-14 | 0.6 | 7.0 | -1.7 | -0.30 | 0.39 |
| 2015-19 | 2.2 | 4.9 | -0.7 | 0.04 | 0.42 |
| 2020-21 | -2.4 | 19.5 | -1.8 | -0.52 | 0.62 |
| 2022 | -9.9 | -1.3 | -0.7 | -1.46 | -1.33 |
| 2023-01..09 | -1.5 | 1.8 | -0.5 | -0.85 | -0.59 |
| **2023-10..2026** | **9.2** | **1.2** | **+2.2** | **1.71** | 1.03 |

QQQ is the same (LO gap>0 net SR -0.06 / 0.09 / 0.29 / -2.28 / -0.75 / 1.67). The overnight
variant's edge exists only in the last three years; over 2010-2023 it would have
*underperformed* the unconditional overnight in every sub-period. It is therefore reported
but **not** recommended.

## 3. Final scorecard - default params (long-only last-half-hour reversal, SPY+QQQ+IWM+SMH)

`IntradayMomentumParams()` = tickers (SPY, QQQ, IWM, SMH), signal="intraday_so_far",
direction=-1, entry="1530", exit="close", long_only=True, threshold_z=0, sizing="fixed",
vol_filter="none", max_gross=1.0. Runtime 2.4 s.

```
==============================================================================================================
idm rev LO         | CAGR   5.09% | Vol  3.14% | Sharpe  0.32 | Sortino  0.42 | MaxDD  -2.54% | Calmar  2.00 | t  2.72 | PF 1.45 | exp L/S 0.06/0.00 | cost/yr 2.35% | days 729
  (Sharpe/Sortino are excess of the 4.0% cash yield)
  time in market 8.2% | turnover/day 0.93 | trades/day 3.72 | skew 0.26 | kurt 12.9 | best +1.58% | worst -1.38%
  Sharpe 95% bootstrap CI: [-0.88, 1.53]
  Deflated Sharpe: P(SR > null max of 460 trials = 1.78) = 0.007      [with the final n_trials=525: 0.006, null max 1.80]
  vs benchmark: corr 0.12 | beta 0.03

  Yearly:
       return      vol   sharpe   max_dd  days
2023   -0.002    0.018   -2.695   -0.009    60
2024    0.031    0.029   -0.318   -0.017   252
2025    0.068    0.033    0.818   -0.012   250
2026    0.051    0.035    1.016   -0.025   167

  In-sample / out-of-sample split at 2025-09-01:
                          days     cagr      vol   sharpe  sortino  max_drawdown   calmar
idm rev LO in-sample       477    0.048    0.031    0.247    0.343        -0.017    2.779
idm rev LO out-of-sample   252    0.056    0.032    0.463    0.537        -0.025    2.202
idm rev LO full            729    0.051    0.031    0.325    0.420        -0.025    2.003
==============================================================================================================
```

Ex-cash (`cash_yield_annual=0`): CAGR 0.98%, Sharpe 0.33, MaxDD -4.4%, IS 0.25 / OOS 0.46,
t 0.56. Per half-year ex-cash returns: 2023H2 -1.2%, 2024H1 +2.4%, 2024H2 -3.3%,
2025H1 +3.9%, 2025H2 -1.1%, 2026H1 +4.3%, 2026H2 (44 d) -1.9% - it alternates sign
every half. Strong vs weak signal days (|z| of SPY's intraday move above / below median):
1.4 bp vs 0.5 bp per day, Sharpe 0.96 vs 0.45.

Other views of the same rule (ex-cash): L/S Sharpe 0.26 (CAGR 1.0%, MaxDD -6.0%, IS 0.06 /
OOS 0.71, corr SPY -0.01); **gross** LO 1.07 (CI [-0.11, 2.26]), gross L/S 1.52 (CI [0.50,
2.51], t 2.6); at 0.5 bp/side (= 1 bp entry at 15:30 + free MOC exit) LO 0.70 / L/S 0.89.
The edge is real at the gross level (t 2.6, same sign in all 5 index ETFs, IS and OOS) but
it is a ~2 bp/day effect and our cost is 2 bp/day.

**Statistical power.** 729 days, daily std 20 bp (LO) -> the standard error of the mean is
0.7 bp/day (~0.4 Sharpe units). A true Sharpe of 0.3 needs ~9 years of data to reach t = 2;
the bootstrap CI spans [-0.9, +1.5]. The OOS "improvement" (0.25 -> 0.46) is 0.2 Sharpe on
252 days and is noise. Deflated-Sharpe probability 0.006 with 525 trials: **this sleeve does
not pass a multiple-testing bar**, and I do not claim it does.

For the record, the overnight variant (`P(tickers=["SPY","QQQ"], signal="first",
direction=1, exit="next_open")`), `report()` net: CAGR 16.1%, Vol 6.9%, Sharpe 1.61 (ex-cash
1.87, CI [0.74, 2.95]), MaxDD -7.6%, IS 1.45 / OOS 1.91, time in market 15%, cost 2.8%/yr,
corr SPY 0.38, yearly Sharpe 2.75 / 1.61 / 1.51 / 1.54, deflated-Sharpe probability 0.545 at
525 trials. Versus unconditional 15:30->09:30 long SPY+QQQ: Sharpe 1.00 (ex-cash 1.35),
MaxDD -17%. Correlation with the overnight sleeve 0.28, with the regime sleeve 0.36. See
section 2d for why this is not the default.

## 4. Sensitivity (net, ex-cash Sharpe; full / IS / OOS)

| Parameter | Value | Sharpe full / IS / OOS | comment |
|---|---|---|---|
| tickers | **SPY+QQQ+IWM+SMH** | **0.33 / 0.25 / 0.46** | |
| | + DIA | 0.24 / 0.19 / 0.35 | |
| | IWM+SMH | 0.43 / 0.23 / 0.78 | |
| | SPY+QQQ | 0.15 / 0.26 / -0.07 | |
| | SMH only / IWM only / SPY only | 0.64 / -0.14 / 0.00 | single names are noise |
| signal | intraday_so_far / day_so_far | 0.33 / 0.32 | identical, as expected |
| threshold_z | 0 / 0.25 / 0.5 / 1.0 | 0.33 / 0.62 / 0.54 / 0.40 | all positive; the gain is cost saving |
| vol_lookback (with z>0.5) | 10 / 20 / 60 | -0.12 / 0.54 / 0.74 | 10d is too noisy |
| sizing | fixed / zscaled cap 0.5 / cap 1.0 | 0.33 / 0.64 / 0.58 | again cost saving, gross unchanged |
| vol_filter | none / rv_above_median / vix_above_median | 0.33 / 0.34 / 0.12 | no regime dependence |
| direction | -1 (reversal) / +1 (momentum) | 0.33 / **-1.91** | the paper's sign is firmly wrong here |
| cost per side | 0 / 0.5 / 1.0 bp | 1.07 / 0.70 / 0.33 | the whole story |

Degradation is smooth (every reversal row is between -0.1 and +0.7); there is no
parameter cliff, but there is also no parameter that lifts the gross edge - only ones that
trade less often. Adding a threshold or |z|-scaling would improve the backtest by 0.2-0.3
Sharpe; I left them off because 2b shows the per-trade edge is *not* larger on big-move
days, so the improvement is pure cost avoidance on ~half the days and within noise.

## 5. Correlations (daily returns, 2023-10 -> 2026-09, ex-cash)

| | idm default | idm overnight variant | overnight sleeve | reversal sleeve | regime sleeve | SPY |
|---|---|---|---|---|---|---|
| idm default (LO reversal into close) | 1 | 0.10 | **0.00** | 0.09 | 0.15 | **0.12** |
| idm overnight variant (first>0 -> next open) | 0.10 | 1 | 0.28 | 0.07 | 0.36 | 0.38 |
| overnight sleeve (`hf_overnight`, run on this window) | 0.00 | 0.28 | 1 | - | 0.34 | 0.30 |

The default sleeve is essentially orthogonal to everything (it is in the market 30 minutes
a day, long only when the market has fallen since the open). That is its one genuine
virtue.

## 6. Failure modes / when to turn this sleeve off

- **Cost.** At 1 bp/side it is breakeven; at anything worse it loses ~2.5%/yr with
  certainty. Live, the 15:30 entry pays a spread (SPY 0.15 bp, IWM/SMH 0.5-0.7 bp) and the
  16:00 exit should be a MOC order (no spread). If live slippage on the 15:30 fill is > 1
  bp, turn it off. Track realised gross bp/day on held days: if the trailing 120-day mean
  falls below +2 bp, the edge is gone.
- **Sign-flip risk.** The reversal is a 2023-26 phenomenon on 723 days. Gao et al. found
  the opposite sign on 1993-2013 data; the effect has already flipped once. Half-year
  returns alternate sign. Do not size this above a few percent.
- **Large moves.** On |z| > 1.5 days (~5%), SPY/QQQ continued rather than reversed
  (-4.5 bp/day in SPY, n 31). Crash days into the close are where a mean-reversion
  day-trade loses most; the worst day was -1.4% (basket, LO).
- **Half days / early closes** are skipped automatically (no 15:30 stamp). A 16:00 stamp
  missing from the feed would leave the position open overnight; `hf_paper` should
  hard-code a MOC exit.
- **The overnight variant** must be treated as a regime bet on the overnight premium
  being concentrated after up-mornings, which was false for 13 of the 16 years of daily
  data. If someone wants to run it anyway: stop when the trailing 250-day difference
  (gap>0 nights minus gap<0 nights) in SPY overnight return falls below 0.
- **Shared-code notes** (no bugs found): `^VIX3M/^VIX9D` are NaN at the end of the cache
  (also flagged by the overnight sleeve); `report()` now prints rf-adjusted Sharpe but CAGR
  still includes the 4% carry (5.1% vs 1.0% ex-cash here). The PDT rule does not apply
  to a cash account, but this sleeve's day trades tie up settled cash: at T+1 settlement
  the same $1,000 can be used every day, so it is compatible with the account.

## 7. Recommended params and ensemble allocation

`IntradayMomentumParams()` defaults as in section 3. Recommended allocation:
**0-5% of the ensemble's gross budget**, and only as a live-monitoring position to
collect real fill data on the 15:30 -> MOC round trip (which determines whether the
0.7-0.9 ex-cash Sharpe at half cost is attainable). The honest expected ex-cash Sharpe at
the brief's cost model is ~0.3 with a CI that includes zero; that is below the threshold
the brief sets ("Sharpe 0.8 and low correlation"), and I would rather report that than
tune it into passing. Its cash is free for the overnight sleeve (which enters at 16:00,
exactly when this sleeve exits) and for the daily sleeves.

Do **not** allocate to the overnight variant despite its 1.9 Sharpe; the overnight sleeve's
`ma200 & on5_dn` rule is the right way to condition the overnight premium (its 5-night
reversal rule agrees with the 16-year sign of the gap->next-overnight relationship; mine
disagrees with it).

## 8. Insights for other sleeves

1. **Intraday momentum (Gao et al.) is dead in US index ETFs** on 2023-26 hourly data:
   sign(first half hour) -> last half hour is 0 bp in SPY/QQQ/IWM/SMH/DIA and in
   TQQQ/UPRO. The leveraged-ETF-rebalancing channel predicts the effect should be
   *strongest* in QQQ/SMH; it is not there. Do not build a last-hour momentum sleeve.
2. **The last half hour reverses the intraday move (~2 bp/day, t 2-3, all index ETFs,
   IS and OOS, strongest in IWM/SMH).** It is a fixed-bp closing-auction effect, not
   proportional to the move, and it is *not* stronger in high-VIX or high-volume
   conditions. For the reversal / regime agents: if you are already going to be long at
   16:00 (e.g. the overnight sleeve), entering at 15:30 on down-days captures it for free
   (last half hour after a down 09:30->15:30: SPY +2.1, QQQ +2.7, IWM +1.8, SMH +5.1 bp;
   ~46% of days); entering at 15:30 on up-days *costs* 1.5-2.7 bp (SPY -1.6, QQQ -1.5,
   IWM -2.7, SMH -2.7 bp). So: enter at 15:30 only when the intraday move is down, else
   at 16:00. The overnight note's 15:30 -> 09:30 row (2.42 vs 2.63 at 16:00) is consistent:
   their rule fires after weak *nights*, not down days, so unconditional 15:30 entry hurts.
3. **16-year daily panel: the overnight gap does NOT predict the open-to-close return in
   SPY/QQQ/IWM/DIA** (sign(gap)->oc = +0.3 bp, t 0.2 in SPY) - neither continuation nor
   fade - so "gap-and-go" and "fade-the-gap" are both non-strategies in index ETFs at the
   daily horizon. What does predict the intraday session is the *previous close-to-close*
   return, negatively (b -0.04 to -0.07, t -3 to -6 in every equity ETF): the daily
   reversal sleeve should use yesterday's full-day return, not the gap. 2025 was an
   exceptional gap-fade year (SPY gap>0 -> -7 bp intraday, gap<0 -> +20 bp; t -1.8 to -2.2
   across SPY/QQQ/IWM) - a tariff-headline regime feature, not a base rate.
4. **Gap continuation exists in TLT (t 3.0, 16 years) and GLD (t 2.1; 6.8 bp/day at |z| >
   1, t 2.6)**, and the same two ETFs show last-half-hour momentum on the hourly panel
   (TLT r_first t 2.2; GLD gap-sign t 3.3, OOS t 3.2). Intraday momentum appears to have
   migrated from equity indices to rate/gold ETFs. A daily "hold TLT/GLD open-to-close
   when |gap| > 1 vol" is ~4-7 bp/day gross vs 2 bp cost - marginal alone, but a useful tilt
   for whoever runs the non-equity ETFs; it is uncorrelated with equity beta.
5. **Overnight returns mean-revert day to day over 2010-2023** (gap>0 -> next overnight
   1.7 bp vs gap<0 -> 6.0 bp in SPY, b_gap t -5.7), which supports the overnight sleeve's
   "sum of last 5 overnight returns < 0" rule, **but the sign flipped in 2023-10 -> 2026**
   (gap>0 -> 9.2 bp vs gap<0 -> 1.2 bp, t +2.2, both SPY and QQQ). Any hourly-panel-only
   result about overnight conditioning is being fit to the one regime in 16 years where
   overnight momentum, not reversal, held. Regime agent: the overnight-autocorrelation sign
   is itself a regime variable worth monitoring (trailing 250-day t-stat of
   sign(gap) x next overnight).
6. **The first hour after the open (09:30 -> 10:30) is a drag** on any position held from
   the prior afternoon: next_1030 exits lose 0.1-0.4 Sharpe vs next_open exits in every
   variant (SPY first->ON 2.01 -> 1.86, QQQ 1.62 -> 1.21), matching the overnight note's
   -2.8 bp first-hour finding. Exit at the open, not after it.
7. **Leverage is not a signal.** TQQQ/UPRO give the same gross Sharpe as QQQ/SPY (0 vs 0
   for the day trade, 1.6-1.8 vs 1.6-2.0 for the overnight variant) with 2x cost and 3x
   drawdown. Use them only to scale a filtered sleeve, as the overnight note also concludes.
8. **Trial accounting for the ensemble's deflated Sharpe:** this sleeve consumed 525
   trials for a 0.33 Sharpe result. If the orchestrator pools trials across sleeves, that
   is the number to add.
