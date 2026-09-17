# Cross-sectional momentum held overnight (`quantbot/strategies/hf_xs_overnight.py`)

Timeline: daily (`md.px_daily`). Long at 16:00, explicit 0.0 row at 09:30. Long-only. Universe:
the core 70 mega-caps (`HF_STOCKS`, 2.5 bp/side). Final rule: at 16:00 rank the 70 by the mean of
the cross-sectional z-scores of (a) 12-1 price momentum and (b) the trailing 63-day sum of the
stock's own overnight returns; hold the top 5 equal-weight overnight **iff** SPY close > its 200d
MA. Tuned on < 2022-01-01. **`n_trials = 95`.** Data: `MarketData(HFConfig.research())`, T-bill
cash (`md.cash_yield()`, mean 1.6%), Sharpe in excess of it, net of `cost_bps_for` costs.

**Headline.** Standalone the sleeve looks excellent - net Sharpe **1.47 (IS 1.74 / OOS 1.01)**,
CAGR 25%, MaxDD -16%, breakeven 3.2x the assumed cost - and the cross-sectional edge is real
(top-5 book earns 15.9 bp/night gross vs 5.1 for the equal-weight 70, t = 8; OOS 12.6 bp, t 3.4).
But (i) it is 0.50 correlated with the live ETF overnight sleeve and 0.39 with the growth
ensemble, because the momentum-overnight premium is concentrated on exactly the nights the ETF
sleeve is on (21 bp vs 11 bp on the other nights); (ii) the time-orthogonal and beta-hedged
variants that would make it independent do **not** clear costs (Sharpe 0.54 / OOS 0.16 and
~0); and (iii) **survivorship is severe**: the book is NVDA / NFLX / TSLA / AMD / AVGO for most
of its life (the five most-held names are in today's top-70 *because* of the runs the sleeve
"caught"); dropping the 12 names whose membership is a post-2010 event cuts the Sharpe to
**0.69 (0.76 / 0.56)** and turns the ensemble delta to zero / negative at every allocation.
**Verdict: SHADOW** (section 9): compute the book daily, log its P&L against the EW-70, allocate
0 until forward data replaces the survivorship-flattered history.

## 1. Hypothesis and literature

Lou, Polk & Skouras (2019, JFE, "A tug of war: overnight versus intraday expected returns")
show that the momentum premium (and most "institutional" anomalies) is earned entirely in the
overnight session and partly reversed intraday, and that a firm's overnight returns are
persistent cross-sectionally (the "overnight-return persistence" or LPS factor). Hendershott,
Livdan & Rosch (2020, JFE, "Asset pricing: a tale of night and day") show CAPM beta is priced
overnight and inverted intraday. `overnight.md` 2d confirmed the momentum half in this universe
(top-5 12-1 winners +12.9 bp/night vs +4.5 for the 70 and +3.6 for losers) and handed it over
as an unbuilt sleeve. The design prior: (i) long winners 16:00 -> 09:30, flat intraday; (ii) the
own-overnight-persistence signal should add to price momentum; (iii) the 200d gate transfers
from the ETF sleeve; (iv) the value to the ensemble is the *cross-sectional* part, since the
ensemble already owns the overnight index premium through QQQ/SMH/IWM - so the independence
tests (section 4) are the ones that matter.

## 2. Everything tested (net of default costs; Sharpe full (IS / OOS); gate = SPY > 200d unless stated)

Conventions: `gross bp` = mean gross overnight return of the book per held night; `net bp` = the same
after entry + exit costs; `BE` = multiple of the assumed cost at which the trading P&L is zero
(x2.5 bp/side = bp/side for a core-70 book); corr = with the shared `overnight` / `ensemble_growth`
excess-return series.

### 2a. Signals and portfolio, core 70 (26 trials)

| variant | Sharpe (IS / OOS) | CAGR | MaxDD | cost/yr | BE | gross / net bp | corr on / ens |
|---|---|---|---|---|---|---|---|
| mom (12-1) n=5 eq | 1.29 (1.59 / 0.77) | 21.1% | -18.2% | 10.7% | 2.8x | 14.2 / 9.2 | 0.50 / 0.39 |
| mom n=10 eq | 1.02 (1.24 / 0.60) | 13.2% | -19.6% | 10.7% | 2.2x | 10.9 / 5.9 | 0.54 / 0.43 |
| mom n=20 eq | 0.65 (0.84 / 0.22) | 7.2% | -21.8% | 10.7% | 1.6x | 8.2 / 3.2 | 0.58 / 0.46 |
| mom n=5 / 10 / 20 ivol | 1.19 / 0.84 / 0.43 | 18 / 10 / 5% | -18..-23% | 10.7% | 2.6 / 1.9 / 1.4x | | |
| mom / vol (vol-scaled) n=5 / 10 | 0.91 / 0.76 | 12 / 8% | -21 / -22% | | 2.1 / 1.7x | 10.3 / 5.3 | |
| LPS 21d n=5 / 10 / 20 | 0.76 / 0.61 / 0.49 (OOS 0.50 / 0.31 / 0.14) | 11 / 8 / 6% | -27 / -23 / -21% | | 2.0 / 1.7 / 1.5x | 10.2 / 5.2 | 0.41 / 0.34 |
| LPS 63d n=5 / 10 / 20 | 1.09 / 0.80 / 0.58 (OOS 0.55 / 0.28 / -0.11) | 18 / 10 / 7% | -24 / -22 / -21% | | 2.6 / 1.9 / 1.6x | 12.9 / 7.9 | 0.46 / 0.37 |
| **combo (z mom + z LPS63) n=5 eq** | **1.47 (1.74 / 1.01)** | **25.3%** | **-16.2%** | 10.7% | **3.2x** | **15.9 / 10.9** | 0.50 / 0.39 |
| combo n=10 eq | 1.18 (1.38 / 0.80) | 15.4% | -15.6% | 10.7% | 2.4x | 11.8 / 6.8 | 0.55 / 0.43 |
| own rule per stock (close > own 200d & own 5-night sum < 0), n=10 / 20 / all | **-0.43 / -0.45 / -0.49** | -3% | -50..-53% | 10.6% | 0.7x | 3.6 / -1.4 | 0.62 / 0.47 |
| mom n=5 / 10 + own 5-night sum < 0 filter | 0.63 / 0.25 (OOS 0.59 / 0.19) | 9 / 4% | -21 / -29% | | 1.8 / 1.3x | 9.0 / 4.0 | 0.58 / 0.44 |
| intraday residual losers held overnight, core n=5 / 10 | 0.60 / 0.46 (OOS 0.30 / -0.24) | 9 / 6% | -33 / -34% | 10.7% | 1.8 / 1.5x | 9.0 / 4.0 | 0.43 / 0.35 |
| mom n=5 / 10, **no gate** | 1.05 / 0.76 (OOS 0.62 / 0.38) | 20 / 12% | **-34 / -32%** | 12.6% | 2.6 / 2.0x | 12.9 / 7.9 | 0.48 / 0.33 |

Findings: concentration is the signal (Sharpe falls monotonically in n for every signal; the
premium is in the top handful of winners). Equal weight beats inverse-vol (ivol de-weights the
high-vol high-momentum names that carry the premium) and vol-scaling the momentum score hurts for
the same reason. LPS persistence works on its own at 63 days (1.09) but not at 21 (0.76), and
combining it with price momentum adds ~0.2 Sharpe and, more importantly, lifts OOS from 0.77 to
1.01 with a lower drawdown. **The ETF sleeve's per-asset rule does not transfer to single
stocks**: requiring a stock's own last-5 overnight sum to be negative is strongly negative
(-0.4), and as a filter on momentum it halves the Sharpe - stock-level overnight returns
*persist* (LPS), they do not mean-revert like index ETFs' do (`overnight.md` insight 3 is an
index effect). Intraday losers held overnight: positive gross but < cost and negative OOS at n=10
(4 trials, dropped, consistent with `reversal.md` 2b(c)). The SPY gate adds 0.25 Sharpe and
halves the drawdown, as in the ETF sleeve.

### 2b. Wide 297-name universe, 5 bp/side outside the core 70 (11 trials, incl. 2 intraday-loser rows)

| variant | Sharpe (IS / OOS) | CAGR | MaxDD | cost/yr | BE | gross / net bp |
|---|---|---|---|---|---|---|
| mom n=10 / 20 / 30 eq | 0.81 / 0.52 / 0.32 (OOS 0.86 / 0.52 / 0.37) | 14 / 8 / 5% | -20 / -23 / -26% | 18.7% | 1.7 / 1.4 / 1.2x | 15.3 / 6.5 |
| mom n=10 / 20 / 30 ivol | 0.70 / 0.37 / 0.10 | 11 / 5 / 2% | -22..-26% | 18.8% | 1.6 / 1.3 / 1.1x | 14.1 / 5.3 |
| LPS63 n=10 / 20 | 0.39 / 0.23 (OOS 0.02 / -0.06) | 7 / 4% | -39 / -34% | 18.2% | 1.4 / 1.2x | 11.8 / 3.3 |
| top-150 liquidity screen, mom n=10 / 20 | 0.79 / 0.45 (OOS 0.73 / 0.43) | 14 / 7% | -20 / -24% | 17.6% | 1.8 / 1.4x | 14.6 / 6.4 |
| intraday losers n=10 / 20 | -0.25 / -0.34 | -2% | -63% | 19.3% | 0.9x | 8.1 / -1.0 |

The wide universe adds only ~1 bp/night of gross edge (15.3 vs 14.2 for n=10 vs core n=5) and
pays 8 pp/yr more in costs; every wide row fails the breakeven gate (BE < 2x). The wide
momentum winners are the mid-cap names in the 5 bp tier (APP, PLTR, VST, ...), so the "5 bp
tail" is not a tail here, it is the whole book. Wide is out; the survivorship point in section 6
applies to it even more strongly.

### 2c. Independence variants (9 trials) - section 4.  2d. Ensemble runs (24) - section 5.  2e. Survivorship (8) and sensitivity (17) - sections 6, 7.

`n_trials` = 26 + 11 + 9 + 24 + 8 + 17 = **95** (ensemble evaluation runs counted, cost ladders and
decompositions not).

## 3. Final scorecard (`XSOvernightParams()` defaults, `report()` output)

```
xs_overnight       | CAGR  25.31% | Vol 15.05% | Sharpe  1.47 | Sortino  1.84 | MaxDD -16.18% | Calmar  1.56 | t  6.24 | PF 1.38 | exp L/S 0.42/0.00 | cost/yr 10.67% | days 3949
  (Sharpe/Sortino are excess of the cash yield: T-bill rate, mean 1.6% over the period)
  time in market 42.4% | turnover/day 1.69 | trades/day 8.47 | skew -0.21 | kurt 9.5 | best +7.36% | worst -8.33%
  Sharpe 95% bootstrap CI: [1.02, 1.92]
  Deflated Sharpe: P(SR > null max of 95 trials = 0.63) = 0.999
  vs benchmark: corr 0.31 | beta 0.27

  Yearly:
       return      vol   sharpe   max_dd  days
2011   -0.030    0.110   -0.224   -0.110   252
2012    0.070    0.101    0.720   -0.079   250
2013    0.814    0.142    4.261   -0.040   252
2014    0.398    0.121    2.832   -0.035   252
2015    0.338    0.113    2.627   -0.046   252
2016    0.202    0.117    1.607   -0.071   252
2017    0.296    0.127    2.037   -0.071   251
2018    0.269    0.140    1.643   -0.069   251
2019    0.119    0.123    0.805   -0.149   252
2020    0.564    0.227    2.068   -0.124   253
2021    0.081    0.140    0.625   -0.110   252
2022   -0.056    0.056   -1.368   -0.084   251
2023    0.060    0.113    0.127   -0.083   250
2024    0.781    0.198    2.767   -0.110   252
2025    0.343    0.185    1.481   -0.085   250
2026    0.088    0.291    0.433   -0.162   177

  In-sample / out-of-sample split at 2022-01-01:
                            days     cagr      vol   sharpe  sortino  max_drawdown   calmar
xs_overnight in-sample      2769    0.264    0.137    1.745    2.175        -0.149    1.769
xs_overnight out-of-sample  1180    0.227    0.178    1.014    1.295        -0.162    1.402
xs_overnight full           3949    0.253    0.151    1.472    1.835        -0.162    1.565
```

Ex-cash (cash yield 0) Sharpe 1.54; gross of costs 2.18 (IS 2.55 / OOS 1.55), CAGR 39%. Time in
market 42% of sessions = 81% of nights (every night SPY is above its 200d MA). Turnover 1.69/day:
a full round trip of a sum|w| = 1 book on 4 of 5 nights, i.e. ~205 round trips a year, cost
**10.7%/yr**. Cost ladder: 2.5 bp/side 1.47 (OOS 1.01); **5 bp 0.76 (OOS 0.47)**; 7.5 bp 0.05;
10 bp -0.66. Breakeven **8.0 bp/side** (3.2x). Per held night: gross 15.9 bp, net 10.9 bp; the
ranking itself is slow (0.39 of the 5 names change per night) - all of the turnover is the
overnight-only hold, none of it is signal churn.

Tails (earnings-night risk): kurtosis 9.5, skew -0.2. Worst 5 days, all gap-downs of the whole
book on macro nights rather than single-name earnings: 2024-08-05 -8.3% (NVDA -14%, AVGO -10%,
AMD -8%; SPY -4.0%), 2020-09-08 -7.5% (TSLA -15%), 2020-02-24 -6.9%, 2026-06-23 -6.3%,
2025-01-27 -5.8% (DeepSeek: NVDA -12.5%, AVGO -12.8%). Of 294k held name-nights, 0.03% gapped
below -5% and 0.01% below -10%; a -10% single-name earnings gap costs the sleeve 2% at 1/5
weight. With 5 names at 20% each the book is as concentrated as the reversal sleeve's 7 at 14%.

## 4. Independence (the key section)

### 4a. Where the edge lives: gross bp/night by state of the live ETF overnight sleeve (combo n=5)

| nights (SPY > 200d) | n | book | EW-70 | SPY | **xs = book - EW** (t) | IS xs | OOS xs (t) |
|---|---|---|---|---|---|---|---|
| all held | 3346 | 15.9 | 5.1 | 3.9 | **10.8 (8.0)** | 10.2 | 12.6 (3.4) |
| ETF sleeve ON (50%) | 1668 | **21.1** | 7.1 | 6.0 | **14.0 (7.2)** | 12.0 | 19.2 (3.7) |
| ETF sleeve OFF (50%) | 1678 | 10.7 | 3.0 | 1.8 | 7.7 (4.1) | 8.4 | 5.8 (1.1) |

(12-1 momentum alone: 14.2 / 19.8 / 8.7 bp; xs 9.2 / 12.7 / 5.7.) Two facts: the cross-sectional
part is large and significant (10.8 bp/night, t 8, and larger OOS than IS), **and it is itself
state-dependent in the same direction as the index premium**: after a run of weak nights (the
ETF sleeve's trigger) winners earn 21 bp and the spread over the market is 14 bp; on the other
half of the nights the spread is 6-8 bp gross, i.e. 1-3 bp net of a 5 bp round trip, and its
OOS t-stat is 1.1. This is why the sleeve is 0.50 correlated with the ETF sleeve: not because it
is "beta" (beta to SPY is only 0.27) but because both are paid on the same nights.

### 4b. Correlations of excess daily returns with `/tmp/qb_shared/reference_daily_returns.csv` (full / OOS)

| variant | overnight | reversal | ensemble_growth | spy |
|---|---|---|---|---|
| **long-only (default)** | **+0.50 (+0.51)** | 0.00 (0.00) | **+0.39 (+0.40)** | +0.31 (+0.29) |
| time-orthogonal | 0.00 (0.00) | +0.01 (+0.01) | 0.00 (+0.01) | +0.20 (+0.20) |
| beta-hedged, SH | +0.18 (+0.26) | +0.02 | +0.14 (+0.20) | +0.08 (+0.12) |
| beta-hedged, PSQ | +0.02 (+0.03) | +0.03 | +0.02 (+0.03) | +0.01 (-0.01) |
| half-hedged, SH 0.5 | +0.42 (+0.45) | +0.01 | +0.33 (+0.35) | +0.25 (+0.25) |

### 4c. The three implementations side by side (core 70, combo n=5, gate on)

| mode | Sharpe (IS / OOS) | CAGR | MaxDD | time in mkt | cost/yr | BE | gross / net bp | corr overnight / ensemble |
|---|---|---|---|---|---|---|---|---|
| **long-only** | **1.47 (1.74 / 1.01)** | 25.3% | -16.2% | 42% | 10.7% | 3.2x | 15.9 / 10.9 | 0.50 / 0.39 |
| time-orthogonal (ETF sleeve flat) | 0.54 (0.76 / **0.16**) | 6.8% | -15.6% | 21% | 5.4% | 2.1x | 10.7 / 5.7 | **0.00 / 0.00** |
| orthogonal, 12-1 mom / combo n=10 | 0.35 (0.54 / 0.01) / 0.30 (0.41 / 0.08) | 5 / 4% | -19 / -18% | 21% | 5.4% | 1.7 / 1.5x | 8.7 / 3.7 | 0.00 |
| beta-hedged, long SH = book beta (~1.2) | **-0.05** (0.03 / -0.20) | 1.2% | -17.2% | 42% | 9.5% | 1.1x | 4.8 / 0.4 | 0.18 / 0.14 |
| beta-hedged, long PSQ | -0.47 (-0.46 / -0.48) | -0.4% | -17.6% | 42% | 9.5% | 0.9x | 4.1 / -0.4 | 0.02 / 0.02 |
| beta-hedged, 12-1 mom, SH | -0.40 (-0.29 / -0.62) | -0.2% | -15.1% | 42% | 9.5% | 0.9x | 4.1 / -0.3 | 0.16 / 0.13 |
| half-hedged (SH 0.5 x stock leg) | 1.09 (1.31 / 0.75) | 11.0% | -12.1% | 42% | 10.0% | 2.0x | 9.5 / 4.8 | 0.42 / 0.33 |

Reading. (i) **Time-orthogonal** has zero correlation by construction but the edge on those
nights (10.7 bp gross, 5.7 net) is a Sharpe-0.5 sleeve with OOS 0.16: it fails gate 1. (ii)
**Beta-hedged** isolates the cross-sectional alpha and shows it is not tradable at these costs:
the hedge gives up the overnight index premium (SH loses SPY's 3.9 bp/night plus its 0.9% fee,
which accrues overnight), costs 2 bp/side on ~0.55 of the book, and the stock leg shrinks to
0.45 of the book to stay inside the 1.0 gross-long cap, so 10.8 bp of xs alpha per unit of
stock becomes 4.8 bp per unit of book against 4.4 bp of round-trip cost. PSQ (the better hedge
for tech-heavy winners, correlation 0.02 with everything) is worse because QQQ's overnight
premium is larger than SPY's. A half hedge is just a diluted long-only book (corr 0.42). (iii) So
the only version that clears costs is the long-only one, and its value to the ensemble depends
on whether the 21 bp/night it earns on the ETF sleeve's nights is worth displacing part of the
ETF book, which is what section 5 measures.

## 5. Ensemble delta (growth profile, reproduced by hand: `combine_weights`, regime multiplier on `overnight`, dd throttle 10%/0.5, exposure cap 1.5, `leverage_map` QQQ -> QLD, gross-long cap 1.0; base reproduces `/tmp/qb_shared` `ensemble_growth` with corr 1.000000, max |diff| 1e-16)

Base growth: Sharpe **1.324 (IS 1.218 / OOS 1.564)**, CAGR 11.6% (OOS 17.7%), MaxDD -12.2%, cost 2.83%/yr.
"rs" = the xs sleeve is regime-scaled like the ETF sleeve (trend x 1/RV^2 multiplier); otherwise it enters at its allocation.

| sleeve added | alloc | Sharpe (IS / OOS) | **delta (IS / OOS)** | CAGR (OOS) | MaxDD (OOS) | cost/yr |
|---|---|---|---|---|---|---|
| combo n=5 long | 0.25 | 1.603 (1.630 / 1.574) | +0.28 (+0.41 / **+0.01**) | 16.7% (21.7%) | -11.6% (-11.4%) | 5.1% |
| | 0.50 | 1.627 (1.738 / 1.448) | +0.30 (+0.52 / **-0.12**) | 20.5% (24.5%) | -12.6% (-12.0%) | 7.2% |
| | 1.00 | 1.470 (1.699 / 1.071) | +0.15 (+0.48 / -0.49) | 24.5% (23.6%) | -15.0% | 10.4% |
| **combo n=5 long, regime-scaled** | 0.25 | 1.576 (1.553 / 1.642) | +0.25 (+0.34 / **+0.08**) | 15.6% (21.3%) | -11.6% (-11.0%) | 4.7% |
| | **0.50** | **1.659 (1.690 / 1.616)** | **+0.34 (+0.47 / +0.05)** | 19.0% (24.1%) | -11.5% (-11.5%) | 6.5% |
| | 1.00 | 1.558 (1.674 / 1.340) | +0.23 (+0.46 / -0.22) | 22.6% (25.0%) | -14.1% | 9.2% |
| 12-1 mom n=5 long | 0.25 / 0.5 / 1.0 | 1.53 / 1.52 / 1.33 | +0.21 / +0.20 / +0.01 (OOS -0.07 / -0.23 / -0.66) | 16-21% | -11..-15% | |
| combo n=10 long | 0.25 / 0.5 / 1.0 | 1.47 / 1.47 / 1.30 | +0.14 / +0.15 / -0.02 (OOS -0.05 / -0.15 / -0.49) | 15-18% | -11..-13% | |
| combo n=5 time-orthogonal | 0.25 / 0.5 / 1.0 | 1.42 / 1.40 / 1.20 | +0.10 / +0.07 / -0.13 (OOS -0.04 / -0.22 / -0.63) | 13-17% | -12..-15% | |
| combo n=5 half-hedged SH | 0.25 / 0.5 / 1.0 | 1.45 / 1.49 / 1.31 | +0.13 / +0.16 / -0.01 (OOS -0.02 / -0.12 / -0.47) | 13-15% | -10..-11% | |
| **core-70 minus 12 risers (de-biased, section 6)** | 0.25 / 0.5 / 1.0 | 1.33 / 1.25 / 0.99 | **+0.00 / -0.08 / -0.34** (OOS -0.09 / -0.26 / -0.65) | 13% | -11..-13% | |
| minus 12 risers, regime-scaled | 0.25 / 0.5 / 1.0 | 1.31 / 1.24 / 1.04 | -0.02 / -0.08 / -0.28 (OOS -0.07 / -0.17 / -0.49) | 12-13% | -11..-13% | |

Cash-budget competition: at 16:00 the ETF sleeve is on 42% of nights and this sleeve 80%; they
overlap on 40% (the sleeve is alone on another 40%, the ETF sleeve alone on 2%). On overlap nights
the gross-long cap scales both pro rata: at allocation 0.5 the ETF book shrinks from 0.567 to
0.463 of equity and the xs book gets 0.436 (at 1.0: 0.340 vs 0.650). So the sleeve is partly a
*substitution* of five momentum stocks (21 bp/night gross, 16 net, idiosyncratic vol) for QLD/SMH/
IWM (which earn ~11-18 bp on those nights at 1-2 bp cost and OOS Sharpe 1.9), and partly an
*addition* of 40% more long-beta nights. The substitution is what costs OOS Sharpe at 0.5-1.0.
Regime-scaling helps OOS (2022's bear and the Aug-2024 / Apr-2025 vol spikes are exactly when
the 1/RV^2 term cuts it) and is how the sleeve should enter the ensemble if it enters at all.

On the headline universe the sleeve passes gate 3 at 0.25-0.5 regime-scaled (+0.05 to +0.08 OOS,
DD unchanged), with all of the large gain in-sample. **On the de-biased universe it adds nothing
at 0.25 and subtracts at 0.5 and above, in-sample and OOS.**

## 6. Survivorship (why the headline is not credible)

The core 70 are today's mega-caps. A long-only *winners* book on that list is the worst case
for survivorship: the names are in the list because they had the runs the sleeve holds. Most-held
names (nights): NVDA 1575, NFLX 1325, TSLA 1230, AMD 1215, AVGO 1063, META 750, GILD 672, PANW
634, AMZN 569, AAPL 563. The "12 recent risers" set is the red team's (`REDTEAM.md` 4): TSLA META
NVDA AMD AVGO NOW PANW CRM NFLX ISRG INTU ABBV.

| universe (combo n=5 unless stated) | Sharpe (IS / OOS) | CAGR | MaxDD | cost/yr | BE | gross / net bp |
|---|---|---|---|---|---|---|
| **core 70 (default)** | **1.47 (1.74 / 1.01)** | 25.3% | -16.2% | 10.7% | 3.2x | 15.9 / 10.9 |
| **core 70 minus 12 risers (58)** | **0.69 (0.76 / 0.56)** | 9.0% | -17.9% | 10.7% | **1.8x** | 9.1 / 4.1 |
| core 70 minus 12 risers, 12-1 mom | 0.63 (0.91 / 0.09) | 7.8% | -14.5% | 10.7% | 1.7x | 8.6 / 3.6 |
| "old economy" 2010 large caps (39, REDTEAM list) | 0.38 (0.38 / 0.40) | 5.2% | -29.6% | 10.7% | 1.5x | 7.4 / 2.4 |
| big-in-2010 150 (top-150 of the 297 by 2010-H2 $-volume) @ 2.5 / default cost | 1.28 (1.58 / 0.97) / 0.95 (1.15 / 0.74) | 25 / 18% | -20 / -29% | 10.7 / 16.4% | 3.2 / 2.1x | 15.8 / 10.8 |
| wide, rolling top-150 by 60d $-volume @ 2.5 / default cost | 1.33 (1.63 / 1.08) / 0.99 (1.20 / 0.83) | 29 / 21% | -20 / -29% | 10.7 / 17.2% | 3.5 / 2.2x | 17.6 / 12.6 |

Reading. The liquidity-based pseudo point-in-time universes from `reversal_wide.md` do *not*
de-bias a winners book: NVDA, NFLX, AMZN, AAPL were already liquid in 2010, so they stay in, and
the names that were liquid in 2010, had a momentum run, and then *left* the top-300 (which the
sleeve would also have bought) are simply not in the data. For a momentum sort the honest test is
to remove the names whose universe membership is itself the outcome; that cuts the gross edge
from 15.9 to 9.1 bp/night and the Sharpe by more than half, and the ensemble contribution to
zero (section 5). The two numbers bracket the truth. The least-biased window is 2022-26 (the
snapshot is close to the true top-70 then): standalone 1.01, xs 12.6 bp/night (t 3.4) on 906
nights - real, but 4.7 years, and it delivered +0.05-0.08 of ensemble Sharpe. The de-biased
2010-21 record says the same signal on a then-plausible universe was a 0.7-Sharpe sleeve that
does not clear 2x costs. Note also `overnight.md` 2d's 0.50 correlation and OOS 0.75-1.0 were
on this same flattered universe.

## 7. Sensitivity (one at a time around the defaults; net Sharpe full (IS / OOS))

| param | values -> Sharpe | comment |
|---|---|---|
| n | 3: 1.47 (1.80 / 0.90), **5: 1.47 (1.74 / 1.01)**, 7: 1.28 (1.54 / 0.80), 10: 1.18 (1.38 / 0.80) | monotone in n; n=3 has MaxDD -26%, kurt 13 |
| mom_long | 126: 1.31 (1.71 / 0.60), 189: 1.39 (1.82 / 0.65), **252: 1.47**, 378: 1.35 (1.69 / 0.77) | plateau; 12 months is best OOS |
| mom_skip | 0: 1.50 (1.72 / 1.11), 10: 1.47, **21: 1.47**, 42: 1.51 (1.85 / 0.93) | flat - skipping the last month does not matter overnight |
| lps_window | 21: 1.24 (1.40 / 0.95), 42: 1.29 (1.42 / 1.09), **63: 1.47**, 126: 1.43 (1.78 / 0.84) | smooth hump at 2-3 months |
| ma_window (gate) | 100: 1.37 (1.60 / 0.99), 150: 1.44, **200: 1.47**, 250: 1.41 (1.68 / 0.95) | flat plateau |
| gate ticker | **SPY 1.47**, QQQ 1.48 (1.68 / 1.12), none 1.05-1.29 (2a) | either index works; no gate = -34% DD |
| weighting | **eq 1.47**, ivol 1.41 (1.63 / 1.07), MaxDD -15% | wash |
| cost | 2.5 bp 1.47, 5 bp 0.76 (OOS 0.47), 7.5 bp 0.05, 10 bp -0.66 | -0.28 Sharpe per bp/side |

No cliffs in the signal parameters; the two cliffs are the ones that matter - **cost** (the sleeve
loses 0.28 Sharpe per bp of per-side cost and is a coin flip at 7.5 bp) and **universe**
(section 6).

## 8. Failure modes / when to turn it off

1. **Survivorship** (section 6) is the dominant risk: the historical record is mostly five names
   that are in the universe because they won. Expect forward performance closer to the de-biased
   0.7 than to 1.47, with 10.7%/yr of costs against it.
2. **Cost.** ~205 stock round trips a year; breakeven 8 bp/side on the headline, ~4.5 bp on the
   de-biased book. MOC/MOO auction fills in mega-caps should be inside 2.5 bp, but the live paper
   trader charges the assumed cost, so only real fills can test this (REDTEAM 5).
3. **Gap risk on macro nights**: the worst days are -6 to -8% when the whole book (NVDA/AVGO/AMD/
   TSLA) gaps down together (2024-08-05, 2025-01-27, 2020-02-24). Beta to SPY is only 0.27 but the
   book is five correlated high-beta names; kurtosis 9.5. Earnings-night gaps > 10% are rare
   (0.01% of name-nights) but cost 2% each at 1/5 weight. No earnings-calendar avoidance is
   implemented (no earnings data in the cache); with one it would skip ~20 name-nights a year.
4. **It shares its best nights with the ETF sleeve** (section 4a) and competes for the cash budget
   on 40% of nights; above allocation 0.5 it displaces a higher-Sharpe book.
5. **Regime**: 2022 (-5.6%, gate off most of the year), 2011 (-3%), 2019 (Sharpe 0.8), 2021 (0.6),
   2023 (0.1): the sleeve does nothing in years without a leadership trend.
6. **Turn-off / monitoring rule**: trailing 250-night mean of (book gross overnight return -
   EW-70 gross overnight return). By year: 2011 6.6, 2012 6.3, 2013 21, 2014 12, 2015 17, 2016 13,
   2017 8, 2018 10, 2019 3.1, 2020 15, 2021 0.1, 2022 5.6, 2023 5.7, 2024 21, 2025 14, 2026 9 bp;
   trailing-250 minimum since 2012 was -2.3 bp (2022-01). If it is below +5 bp (the round trip)
   the cross-sectional part is not paying for its costs.
7. **$1,000 account**: 5 names at allocation 0.25-0.5 is $50-100 per name; fractional shares
   required; GOOG and GOOGL are both eligible (same company, both can be picked).

## 9. Recommended params, allocation, and the Round 3 acceptance gate

`XSOvernightParams()` defaults: `signal="combo", mom_long=252, mom_skip=21, lps_window=63, n=5,
weighting="eq", gate_ticker="SPY", ma_window=200, universe=tuple(HF_STOCKS), mode="long"`. In the
ensemble it should be treated as a risk-on sleeve (`regime_scaled`) - the regime-scaled version
has the better OOS delta at every allocation. `mode="orthogonal"` and `mode="hedged"` are in the
file for reference and are not recommended (section 4c).

| gate | headline (core 70) | de-biased (minus 12 risers) |
|---|---|---|
| 1. standalone Sharpe >= 0.5 full and >= 0.4 OOS, same sign | **pass** 1.47 / 1.01 | pass 0.69 / 0.56 |
| 2. breakeven >= 2x assumed cost | **pass** 3.2x (8.0 bp) | **fail** 1.8x (4.5 bp) |
| 3. ensemble Sharpe up in-sample and OOS at the recommended allocation | pass at 0.25-0.5 regime-scaled (+0.34 / +0.08 and +0.47 / +0.05); **fail** un-scaled at 0.5 (OOS -0.12) | **fail** (0.00 / -0.09 at 0.25; negative above) |
| 4. smooth sensitivity | pass (no cliffs in signal params; cost and universe are the cliffs) | pass |

**Verdict: SHADOW, allocation 0.** The mechanical gate passes on the headline numbers, but the
headline is a survivorship artefact to a degree that the other sleeves' notes did not have to
worry about (a long-only *winners* book on a 2026 constituent list), the de-biased version fails
gates 2 and 3, the independent (time-orthogonal / hedged) versions fail gate 1, and the only
version that clears costs is 0.50 correlated with the live overnight sleeve and displaces it on
its best nights. The brief's own criterion settles it: a 1.5-Sharpe sleeve at correlation 0.5
that adds +0.05 OOS is worth less than a 0.6-Sharpe uncorrelated one, and the 1.5 is not real.

Shadow protocol: compute `xs_overnight_weights(md)` every 16:00 alongside the live book (0.2 s),
log (a) the book's gross overnight return minus EW-70 and (b) realised fills vs the 16:00 / 09:30
prints for the 5 names. **What would change my mind:** 250+ forward nights with xs >= 8 bp/night
gross (t >= 2) and fills within 2.5 bp - the forward record is survivorship-free by construction
and 250 nights at the historical dispersion is enough to distinguish 8 bp from 0. If that
happens, enter at **0.25, regime-scaled** (ensemble delta +0.25 full / +0.08 OOS on the
headline, MaxDD unchanged, 5% of equity per name), never above 0.5.

## 10. Insights for other sleeves

1. **Survivorship test for winners books**: the liquidity-screen pseudo point-in-time universes
   (`reversal_wide.md` insight 2) do not de-bias a *momentum* sort, because the names that were
   liquid in 2010 and then won are exactly what it buys and they are all still in the list. For
   any long-winners design, re-run with the names whose membership is a post-2010 event removed
   (REDTEAM's 12 risers) and treat the two numbers as a bracket. Here the bracket is 0.7-1.5.
2. **Stock-level overnight returns persist; index-level ones mean-revert.** The ETF sleeve's
   "5 weak nights -> buy" rule is *negative* applied per stock (-0.4 Sharpe), while the trailing
   63-day sum of a stock's own overnight returns is a positive ranking signal (Sharpe 1.1 alone,
   +0.2 on top of price momentum). Do not port the ETF rule to single names.
3. **The cross-sectional momentum-overnight premium is concentrated on the same nights as the
   index overnight premium** (14 bp/night xs after weak nights vs 6-8 bp otherwise). Any
   overnight stock sleeve will be ~0.5 correlated with the ETF sleeve unless it gives up those
   nights, and the residual nights do not pay 5 bp of round trip.
4. **Hedging overnight beta with inverse ETFs does not work at these costs**: SH/PSQ lose the
   index overnight premium plus their fee (which accrues overnight), cost 2 bp/side, and consume
   half the cash budget. A hedged overnight stock book needs > ~12 bp/night of cross-sectional
   alpha per unit of stock to break even; nothing found here has that.
5. **Wide universe + momentum = the 5 bp tier.** The winners of the 297 are the mid-caps outside
   the core 70; the wide book pays 18.7%/yr in costs for ~1 bp/night more gross edge. Breadth is
   a liquidity/cost trade for momentum just as `reversal_wide.md` found for reversal.
6. **Concentration is the signal**: Sharpe falls monotonically from n=3-5 to n=20 for every
   signal and universe here (as for the reversal sleeves). Overnight anomalies in mega-caps live
   in the extreme tail of the sort; diversifying to 20 names removes the edge, not the noise.
7. Trial count: 95 here; the ensemble's `n_trials_total` should grow by that even though nothing
   was adopted.

## 11. Implementation notes

`hf_xs_overnight.py` imports only from `quantbot.*` / numpy / pandas; builds in 0.2 s on the
research config and 0.5 s (incl. data load) on the core config, with identical weights on both.
Truncation test (data cut at 2020-03-16, 2024-08-05, 2025-04-08, 2026-06-23; weights recomputed
and compared to the full-sample matrix on all rows <= the cut): max |diff| 0.0 at every date.
The `orthogonal` mode imports `overnight_weights` from `hf_overnight.py` (defaults) so its
on/off nights are the live sleeve's by construction. Deliverables:
`/tmp/qb_shared/xs_overnight_daily.csv` (3949 days, 2011-01-03 -> 2026-09-16, column
`xs_overnight`, net, default params) and `/tmp/qb_shared/xs_overnight_weights.parquet`
(8402 x 70). Scratch: `/tmp/qb_xs_overnight/` (`common.py`, `exp1_signals.py` ...
`exp5_final.py`, `*.log`, `*_trials.csv`).
