# Scheduled macro announcements: the pre-FOMC overnight sleeve (round 4)

**Verdict: ACCEPT** the pre-FOMC eve-night sleeve (`hf_macro.py`, `MacroParams()`
defaults: FOMC only, QQQ, held through QLD in the live profile) at allocation
1.0. **Reject** employment / CPI / PPI eves and the "skip the reversal sleeve
on release mornings" rule. Ensemble (live `sharpe-lev`): Sharpe 1.505 ->
**1.666** (IS 1.373 -> 1.509, OOS 1.799 -> **2.013**), CAGR 21.6% -> 24.6%,
MaxDD unchanged -14.5%. `n_trials` this note: 8 sleeve variants + 4 event
types x 2 assets x 3 windows descriptive + 9 ensemble allocations + 5 placebo
= ~46; cumulative ~3,100.

Research conducted by the orchestrator after the round-4 agents failed on
infrastructure errors (no research output from them).

## 1. Hypothesis and literature

Savor & Wilson (2013, JFQA) report that US equity excess returns on days with
scheduled CPI / PPI / employment / FOMC announcements average ~11 bp against
~1 bp on other days. Lucca & Moench (2015, JF) document the pre-FOMC
announcement drift: ~+49 bp in the 24 hours before scheduled FOMC statements
(1994-2011). Both are compensation for bearing scheduled macro risk; the 08:30
ET releases land before the open, so their premium would accrue in the
16:00 (d-1) -> 09:30 (d) window the overnight sleeve already trades, but on a
different signal (a scheduled event, not recent overnight weakness). The
live book is flat on 48% of nights, so an event sleeve mostly fills dead time.

## 2. Dates (primary sources, fetched 2026-09-24; `quantbot/macro_calendar.py`)

| kind | source | 2010-2026 count | checks |
|---|---|---|---|
| FOMC decision days | federalreserve.gov `fomccalendars.htm` + `fomchistorical2010..2020.htm`; last day of each *scheduled* meeting | 133 (8/yr; 7 in 2020) | excluded 2020-03-03 and 2020-03-15 (unscheduled), 2020-03-17/18 (cancelled), 2025-08-22 (notation vote). All Tue-Thu. |
| Employment Situation | BLS archived-release filenames `empsit_MMDDYYYY` | 200 (12/yr) | Fridays except July-4th Thursdays, 2013-10-22 (shutdown), 2025 shutdown gap (Oct not published, Nov 20, Dec 16), 2026-02-11 |
| CPI | `cpi_MMDDYYYY` | 200 (12/yr) | mid-month weekdays; 2013-10-30 and 2025-10-24 shutdown delays |
| PPI | `ppi_MMDDYYYY` | 200 (12/yr) | mid-month weekdays |

Forward dates for the rest of 2026 (and the 2027 FOMC schedule) come from
the BLS/Fed schedule pages and are in the module for live trading. Six
employment and two CPI releases fell on Good Friday (market closed); the
sleeve maps a release to the trading day before it via the NYSE calendar.

## 3. Descriptive: session returns by event type (bp, t-stat; IS < 2022, OOS 2022+)

QQQ, overnight = 16:00 (d-1) -> 09:30 (d), stamped on the release day d:

| event day | n | overnight IS | overnight OOS | overnight full | intraday full | full-day full |
|---|---|---|---|---|---|---|
| **FOMC** | 133 | **+21.0 (3.1)** | **+33.9 (3.2)** | **+24.6 (4.3)** | -1.6 (-0.2) | +23.1 (2.0) |
| Employment | 194 | +5.4 (0.9) | -6.5 (-0.5) | +2.1 (0.4) | -4.9 (-0.6) | -2.8 (-0.3) |
| CPI | 198 | +4.5 (0.9) | +22.8 (1.2) | +9.7 (1.5) | +2.2 (0.3) | +11.9 (1.2) |
| PPI | 200 | -6.7 (-1.0) | +10.2 (1.1) | -1.9 (-0.3) | +2.3 (0.3) | +0.4 (0.0) |
| any release | 707 | +4.2 (1.3) | +13.5 (1.8) | +6.8 (2.2) | -1.0 (-0.2) | +5.9 (1.1) |
| no release | 3498 | +5.9 (3.8) | +2.0 (0.7) | +4.8 (3.6) | +3.4 (2.0) | +8.2 (3.8) |

SPY: FOMC overnight +12.6 (2.3) IS / +20.4 (2.9) OOS / +14.8 (3.4) full; the
other event types are as unremarkable as for QQQ. The Savor-Wilson "any
announcement" premium does **not** replicate here per night (4.2 vs 5.9 bp
in-sample); the Lucca-Moench pre-FOMC drift does, and it sits in the
overnight session (the 09:30 -> 16:00 leg of decision day, which contains the
14:00 statement, nets to ~0). CPI's OOS +22.8 is the 2022-23 inflation
scare - not present before 2022 and concentrated on nights the live
overnight sleeve was already on (+63 bp when on, -7 when off) - and PPI is
negative in-sample: neither is tradeable. FOMC pays whether or not the live
sleeve is on that night (+21/+21 IS, +12/+44 OOS on/off; the live sleeve is on
47% of FOMC eves).

Placebo (QQQ overnight, bp): two nights before decision -4.2 (t -0.6), night
into the eve +5.5 (0.8), **night into decision day +24.6 (4.3)**, night after
-0.5 (-0.1), two after +8.0 (1.2); unconditional +5.1. The premium is the
pre-announcement night only.

## 4. Sleeve variants (net, T-bill cash, excess Sharpe; ~8 nights/yr)

| variant | Sharpe (IS / OOS) | CAGR | vol | MaxDD | time in mkt | cost/yr |
|---|---|---|---|---|---|---|
| **FOMC eve, QQQ (default)** | **0.90 (0.77 / 1.22)** | 3.3% | 2.0% | -3.5% | 1.6% | 0.02% |
| FOMC eve, SPY | 0.68 (0.54 / 1.08) | 2.5% | 1.5% | -3.0% | 1.6% | 0.02% |
| FOMC eve, QQQ/SMH/IWM | 0.85 (0.61 / 1.34) | 3.3% | 2.1% | -4.0% | 1.6% | 0.02% |
| FOMC eve via QLD | 0.91 (0.78 / 1.21) | 5.1% | 3.9% | -6.7% | 1.6% | 0.03% |
| FOMC eve via TQQQ | 0.93 (0.81 / 1.21) | 7.1% | 5.9% | -10.2% | 1.6% | 0.03% |
| FOMC eve, QQQ, own-200d gate | 0.76 (0.78 / 0.74) | 2.9% | 1.8% | -3.2% | 1.4% | 0.01% |
| FOMC + CPI eves | 0.67 (0.56 / 0.89) | 4.0% | 3.7% | -5.2% | 3.9% | 0.04% |
| all four release eves | 0.33 (0.17 / 0.64) | 3.2% | 5.5% | -12.6% | 8.5% | 0.09% |

Default: yearly net return positive in 13 of 17 years (2014 -1.1%, 2016
-0.2%, 2021 -1.1%); breakeven cost ~12 bp/side (Sharpe 0.59 at 5 bp, 0.18 at
10 bp) against 1-2 bp assumed; kurtosis is huge (220) purely because the
series is zero on 98% of days. Correlation of excess daily returns with the
live sleeves: overnight 0.10, reversal 0.01, ts_reversal 0.06, ensemble 0.11,
SPY 0.08 (OOS 0.01 / 0.03 / 0.05 / 0.04). Trend gate: no (it removes 2022's
best nights). Leverage: standalone Sharpe-neutral, as it should be.

## 5. Ensemble (live profile `sharpe-lev`, reproduced through `hf_ensemble_weights`)

| addition | Sharpe (IS / OOS) | CAGR | vol | MaxDD |
|---|---|---|---|---|
| none (live) | 1.505 (1.373 / 1.799) | 21.6% | 12.5% | -14.5% |
| macro 1.0 via QQQ | 1.581 (1.426 / 1.923) | 22.7% | 12.5% | -14.5% |
| macro 0.5 via QLD | 1.603 (1.448 / 1.945) | 23.2% | 12.6% | -14.7% |
| **macro 1.0 via QLD (adopted: `sharpe2`)** | **1.666 (1.509 / 2.013)** | **24.6%** | 12.8% | **-14.5%** |
| macro 1.0 via TQQQ | 1.725 (1.565 / 2.079) | 26.4% | 13.2% | -14.5% |

With only eight nights a year the contribution scales almost linearly with
position size (the max-Sharpe weight for a 0.9-Sharpe, 2%-vol stream next to
a 1.5-Sharpe, 12.5%-vol book is several times the book's weight; the cash
account caps it). QLD is adopted rather than TQQQ because the worst FOMC-eve
gap in the sample is -2.9% in QQQ: -5.9% of equity through QLD is in line
with the book's existing worst day (-6.6%), -8.9% through TQQQ is not, on an
event bet with 133 observations. On the 47% of FOMC eves when the overnight
sleeve is also on, the cash cap scales both pro rata (overnight slots 1/6
each + QLD 0.5: ~2.2x exposure instead of 2.3x).

## 6. Reversal sleeve on release mornings (the skip rule): not adopted

Gap-fade sleeve (vol-targeted) active-day gross return: FOMC mornings +3.4 bp
IS (n 36) / -2.6 OOS (n 16) vs +5.3 / +4.5 on other mornings; all four release
types pooled +4.0 IS (t 1.1, n 186) / +1.2 OOS (n 96) vs +5.5 / +4.9. Release
mornings are somewhat worse for the fade, consistent with information gaps
not reverting, but the difference is within noise and the rule would be a
post-hoc tweak. Left as a monitoring item.

## 7. Causality and implementation

The FOMC schedule is published a year ahead (each date tentative until the
prior meeting confirms it; a change would show on the Fed page). At the
16:00 close of the eve the sleeve buys QLD (market-on-close); at 09:30 on
decision day it sells (market-on-open) - the same mechanics as the overnight
sleeve, so no trader changes. The eve is computed from the NYSE calendar,
not the price panel: the first version used the panel and marked its last
row as the eve of every future meeting (a live trader would have bought every
evening; the truncation test failed 18/40 and caught it). After the fix:
40/40 truncation tests identical. Next eves: 2026-10-27, 2026-12-08,
2027-01-26.

## 8. Failure modes

- The premium is a communication-regime phenomenon (it grew after the Fed
  began press conferences and forward guidance); a change in how decisions
  are communicated could remove it. Monitor the trailing 16-event mean; below
  +5 bp gross, drop the allocation to 0.
- Eight observations a year: a bad year is one or two bad nights. 2021 was
  -1.1% for the sleeve.
- A scheduled date moving (shutdown, emergency) means the sleeve holds a
  non-event night at ETF risk; the calendar module must be refreshed each
  December from the Fed page (2027 is loaded).
- Do not extend to other releases without new evidence: the same test that
  passes FOMC rejects the other three.
