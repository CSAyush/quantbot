# Red-team review of the HF ensemble (growth profile) before paper trading

Reviewer stance: adversarial. Everything below was checked by running code against the
cached data (`data_cache/ohlcv_1d.parquet` through 2026-09-01, `ohlcv_1h.parquet`
2023-10-04 -> 2026-09-01). Scratch scripts: `/tmp/qb_redteam/t*.py` (`common.py` has the
`truncate()` helper; scripts are self-contained apart from that). Nothing in the repo was
modified except this file.

Headline reproduced exactly: `python3 run.py hf backtest --profile growth --sleeves` ->
**Sharpe 1.21 (ex 4% cash), CAGR 15.57%, MaxDD -12.10%, OOS(2022+) Sharpe 1.46, 17/17
calendar years positive**; standalone overnight (QLD/SMH/IWM) Sharpe 0.99 / CAGR 12.2% /
MaxDD -22.3%; reversal 0.75 / 11.2% / -11.8%.

## Overall verdict: PASS WITH CAVEATS

The backtest is honest: no lookahead was found by truncation/masking (0 differing weights
across 19 dates x 2 modes x 5 objects), the engine's accounting is exactly right on
synthetic panels, dividends are handled consistently, and the result survives one-day
staleness, dropping 2020, and 3-year block splits. What is *not* proven is that the
reversal sleeve is executable at the assumed price; the headline CAGR and "every year
positive" lean on a flat 4% cash yield; the cost margin is ~2.8x; and the live trader still
has a data-outage path that holds the 2x overnight book through the day (two worse
live/backtest divergences in the version I started with were fixed by an edit made during
the review). Details and numbers follow; the ranked list is at the end.

| # | Check | Verdict |
|---|---|---|
| 1 | Lookahead (truncation + 09:30 masking, all sleeves, regime mult, dd throttle) | **PASS** |
| 2 | Engine accounting (synthetic panels) | **PASS** (one cosmetic nit) |
| 3 | Data quality | **PASS WITH CAVEATS** (open-print ambiguity for stocks) |
| 4 | Survivorship / universe | **PASS WITH CAVEATS** (universe size matters more than survivorship; x-sectional alpha has decayed) |
| 5 | Cost realism | **PASS WITH CAVEATS** (Sharpe 0.5 at 2.8x costs; Sharpe 0 at 4.2x) |
| 6 | Robustness | **PASS WITH CAVEATS** ("every year positive" and 3.6 pp of CAGR are the 4% cash assumption) |
| 7 | Paper-trader logic vs backtest | **PASS WITH CAVEATS** on the current file (the version read at 02:11 FAILED two edge cases — missing daily row at 09:30, half days — fixed by the 02:16 rewrite; a data-outage path still leaves the 2x book on all day, and the MOO fill assumption is untestable in paper) |

---

## 1. Lookahead — PASS

Method (`t1_lookahead.py`): for 19 dates D (13 hand-picked stress/ordinary days incl.
2020-03-16, 2025-04-08/09, 2026-08-31, plus 6 random) build a `MarketData` copy truncated at
D in two modes: (a) *eod* — drop every row after D from `md.daily[*]`, `md.aux`,
`md.px_daily`; (b) *blank_open* — keep D's row but NaN out `High/Low/Close/Volume` and
`aux` on D and cut `px_daily` at D 09:30, i.e. exactly `hf_paper._mask_for_session` at the
open. Recompute `overnight_weights(leverage_map={"QQQ":"QLD"})`, `reversal_weights`,
`regime_multiplier`, the ensemble's drawdown-throttle flag, and
`hf_ensemble_weights(timeline="daily")`, and compare every row <= D 16:00 (eod) or
<= D 09:30 (blank_open) to the full-sample matrices with tolerance 1e-12.

Result: **0 differing rows** in all 19 x 2 x 5 = 190 comparisons.

Same test on the *hourly* path the paper trader actually runs (`t7_live_path.py`, 26
sampled 09:30/15:30/16:00 stamps, masked exactly as `_mask_for_session`): live-path row ==
backtest row at every stamp, and all history rows identical. Hourly-path and daily-path
weights agree at all 1,453 shared stamps (2023-10 -> 2026-09); P&L over that window:
daily path Sharpe 1.88 / CAGR 22.7%, hourly path 1.84 / 22.2% (difference = hourly-bar
prints vs daily prints, see 3a).

Repro (eod mode, one date):

```python
from common import load_md, truncate            # /tmp/qb_redteam/common.py
from quantbot.strategies.hf_ensemble import EnsembleParams, hf_ensemble_weights
md = load_md(); p = EnsembleParams.from_profile("growth")
full = hf_ensemble_weights(md, "daily", p)
m, ts = truncate(md, "2025-04-08", blank_open_day=True)   # mimics hf_paper at 09:30
part = hf_ensemble_weights(m, "daily", p)
print((full.loc[:ts] - part.reindex(columns=full.columns).fillna(0).loc[:ts]).abs().max().max())  # 0.0
```

Caveat that truncation *cannot* catch: both sleeves use the price they fill at as a signal
input (reversal: Open[d] ranks and fills at 09:30; overnight: Close[d] gates and fills at
16:00). That is a same-timestamp execution assumption, not lookahead; it is quantified in 7.

## 2. Engine accounting — PASS

`t2_engine.py` builds 3-4 stamp panels with hand-computed answers (all match to 1e-12):

- Weight set at t earns the return t -> t+1 (buy at Fri 16:00 100 -> Mon 09:30 102 gives
  +2% on the Mon 09:30 row; the entry row shows 0, never the t-1 -> t return).
- Cost = |dw| x bp on every row including exits; exit turnover of a fully-invested book is
  exactly 1.0; drift-adjusted pre-trade weight `w_prev(1+r_i)/(1+r_p)` verified
  (0.5/0.5 book with +10%/-10% legs -> turnover 0.10; 0.5 slot after +2%/+1% -> 0.50495).
- Cash carry is pro-rata by wall clock: 6.5 h intraday = 6.5/24/365.25 yr, Fri 16:00 ->
  Mon 09:30 = 65.5 h. Cash fraction = 1 - long exposure (short proceeds earn 0).
- Shorts: -1 weight on 100 -> 105 gives -5%; borrow charged as `short_expo x bps x dt`; short
  drift `-1.05/0.95` verified.
- Assets without a price are forced to weight 0; daily compounding by session date correct.
- `net.iloc[0] = 0` trims the warm-up **and drops the very first trade's entry cost**
  (one-off, ~2 bp of equity once in 2010 — cosmetic).
- Nit: `metrics.sharpe` subtracts a flat 4%/252 per trading day while carry accrues on
  calendar days and only on the idle fraction, so a strategy that is 19% invested is charged
  ~0.8%/yr more rf than it earns. The "excess of 4%" Sharpe (1.21) is therefore slightly
  *conservative* relative to a rf-0 run with no carry (1.30). Not a bug.

## 3. Data — PASS WITH CAVEATS

`t3_data.py`, `t3b_open_quality.py`.

**3a. Which print is "the open"?** Daily `Open` vs the 09:30 1h-bar `Open` (both Yahoo,
730 shared days):

| ticker | median abs diff | p90 | p99 | frac > 5 bp |
|---|---|---|---|---|
| SPY | 0.0 bp | 0.1 | 10.5 | 5% |
| QQQ | 0.3 | 2.6 | 16.2 | 6% |
| IWM | 0.0 | 0.3 | 28.9 | 8% |
| SMH | 1.4 | 10.8 | 31.4 | 25% |
| AAPL | 0.9 | 10.3 | 43.1 | 21% |
| NVDA | 1.1 | 12.3 | 65.4 | 19% |
| TSLA | 1.2 | 11.9 | 70.4 | 21% |

For index ETFs the two prints agree (MOO fills at the daily Open are plausible). For single
stocks the "open" is ambiguous at the ~10 bp level on 1 in 5 days, against a reversal edge
of ~7 bp/active day gross. Filling the reversal sleeve at the 1h-bar open instead of the
daily Open (signal unchanged) over 2023-10+: Sharpe 0.54 -> 0.48, mean 3.10 -> 2.94 bp/day.
The 16:00 prints agree to ~1 bp median for all ETFs; the overnight sleeve is unaffected
(2.13 vs 2.12).

**3b. Integrity.** No duplicated dates or stamps; `px_daily` monotonic; 4,191 SPY days with
156 missing weekdays = 9.4/yr (holidays), no gap runs > 2 days; no Open outside [Low, High];
2 O=H=L=C rows in 293k. Late starters handled: TQQQ 2010-02-11, TSLA 2010-06, META 2012-05,
NOW/PANW 2012, ABBV 2013 — all NaN before listing and excluded from ranks. **QLD/SSO/UPRO
have data from 2010-01-04 (funds launched 2006/2009), no NaN inside; the overnight sleeve
puts 0 on QLD before its first price (verified, 0 rows).** Large jumps are all real events
(AMD +52% 2016-04-22, NFLX +42% 2013-01-24, TQQQ +35% 2025-04-09).

**Fabricated opens:** 846 stock rows have `Open == previous Close` exactly (AMD 214, PANW 95,
ADBE 94, ISRG 77, BRK-B 73, NOW 69, TSLA 54, NFLX 44; ETFs: QQQ 1, SMH 1, IWM/QLD 0). These
are Yahoo placeholder opens (gap = 0 by construction). Impact on the reversal sleeve: 17 of
11,564 selected name-days (0.15%), P&L contribution -0.4% of gross. Negligible, but the
data are not clean.

**3d. Dividends.** `AdjFactor = AdjClose/Close` is applied to O/H/L/C of the same day, which
is the correct total-return convention. Verified on ex-div dates: adjusted-minus-raw
overnight return equals the implied dividend (QQQ 21 bp, SMH 116 bp, IWM 34 bp, SPY 44 bp,
QLD 9 bp) and is 0.00-0.01 bp on non-ex-div days (0.59 bp for QLD, i.e. one rounding
artefact). Consistent. Side note: the paper trader never credits dividends to cash, so
live P&L on ex-div nights held will lag the backtest by the dividend (~0.1%/yr expected).

**Cache quirk:** `ohlcv_1d.parquet` contains a `2026-09-02` row holding only a pre-market
`^VIX` print. `MarketData` drops it (`valid` mask), so no effect.

## 4. Survivorship / universe — PASS WITH CAVEATS

`t4_survivorship.py`. Reversal sleeve standalone (from 2010-06) and the full growth ensemble
with the stock universe swapped:

| universe | n | reversal Sharpe (IS / OOS) | CAGR | MaxDD | ensemble Sharpe / OOS / CAGR / MaxDD |
|---|---|---|---|---|---|
| all 70 (as shipped) | 70 | 0.76 (0.77 / 0.73) | 11.2% | -11.8% | 1.21 / 1.46 / 15.6% / -12.1% |
| 70 minus 12 recent risers* | 58 | 0.73 (0.65 / 0.93) | 10.5% | -15.6% | 1.19 / 1.62 / 15.0% / -12.0% |
| 40-ticker `config.UNIVERSE` | 38 | 0.50 (0.45 / 0.60) | 8.5% | -12.5% | 1.01 / 1.36 / 13.5% / -11.8% |
| `UNIVERSE` minus risers | 32 | 0.50 (0.42 / 0.68) | 8.3% | -12.4% | 1.02 / 1.44 / 13.3% / -11.6% |
| "old economy" 2010 large caps** | 39 | 0.55 (0.59 / 0.43) | 8.6% | -18.6% | 1.05 / 1.29 / 13.4% / -11.4% |
| 12 recent risers only | 12 | 0.24 | 6.5% | -23.0% | 0.70 / 0.92 / 11.8% / -14.8% |

\* dropped: TSLA, META, NVDA, AMD, AVGO, NOW, PANW, CRM, NFLX, ISRG, INTU, ABBV.
\** GE INTC T VZ PFE IBM CSCO BA DIS WFC CMCSA BMY MDT GILD XOM CVX MRK PG KO PEP JNJ ABT
MCD HON UNP CAT BAC GS MS AXP RTX SBUX NKE LOW TXN QCOM AMGN WMT ORCL.

Reading: survivorship per se is small (removing the 12 big winners costs 0.03 Sharpe and
*raises* OOS). What matters is **universe breadth**: a 38-40 name universe drops the
reversal sleeve to ~0.5 and the ensemble to ~1.0. A bottom-7-of-70 sort is a more extreme
selection than bottom-7-of-38; the ensemble's 1.21 is specific to the 70-name list.

Decomposition (all 70): L7 book Sharpe 0.76 / ex-cash CAGR 7.0%; the equal-weight universe
held with the *same* VIX ramp: Sharpe 0.07 / ex-cash CAGR 0.4%. The cross-sectional part
(L7 minus EW) is 2.5 bp/day, Sharpe 1.36 full, but **IS 1.54 -> OOS 0.97 -> 2023-10+ 0.59**
and by year (bp/day): 2010 10.6, 2011 8.2, 2012-19 avg ~1.0, 2020 9.0, 2021 -0.5, 2022 6.8,
2023 0.0, 2024 1.3, 2025 1.0, 2026 0.0. The reversal alpha lives in 2010-11, 2020, 2022; in
calm years it is ~1 bp/day against 5 bp/day of round-trip cost (the VIX gate is what keeps
it alive).

Also: GOOG and GOOGL are both in the universe and are both selected on 105 days (of 161
where either is) -> 2/7 of the book on one company those days.

## 5. Cost realism — PASS WITH CAVEATS

`t56_costs_robustness.py`. Per-side costs scaled (base ETF 1 / leveraged 2 / stock 2.5 bp):

| multiplier | Sharpe | OOS Sharpe | CAGR | MaxDD | cost/yr | worst year | # neg years |
|---|---|---|---|---|---|---|---|
| 0x (gross) | 1.59 | 1.82 | 19.6% | -11.5% | 0.0% | +2.1% | 0 |
| 1x (as reported) | 1.21 | 1.46 | 15.6% | -12.1% | 3.5% | +0.5% | 0 |
| 1.5x | 1.01 | 1.28 | 13.6% | -12.4% | 5.2% | -0.2% | 1 |
| **2x** (ETF 2 / lev 4 / stock 5) | **0.82** | 1.09 | **11.6%** | -12.7% | 6.9% | -1.0% | 1 |
| 2.5x | 0.63 | 0.91 | 9.7% | -12.9% | 8.6% | -1.8% | 2 |
| **3x** (ETF 3 / lev 6 / stock 7.5) | **0.44** | 0.72 | **7.9%** | -13.2% | 10.4% | -2.5% | 2 |
| 4x | 0.06 | 0.36 | 4.2% | -14.2% | 13.8% | -4.4% | 5 |
| 5x | -0.33 | -0.01 | 0.7% | -29.7% | 17.3% | -10.3% | 9 |

**Breakeven for Sharpe 0.5: 2.84x** (ETF 2.8 / leveraged 5.7 / stock 7.1 bp per side).
Sharpe 0 at 4.15x. Standalone: overnight x1 0.99, x2 0.74, x3 0.50; reversal x1 0.75,
x2 0.48, x3 0.21, x4 -0.06 (consistent with the note's 9.7 bp breakeven). Sharpe falls
~0.38 per 1x of cost: the result is a cost-margin story, not a signal-margin story.

Important consequence: **the paper trader charges the *assumed* costs**
(`cost_bps_for`) and fills at the panel print, so paper trading cannot detect a cost
misestimate. Only real fills can.

## 6. Robustness — PASS WITH CAVEATS

**6a. Stale signals** (`weights.shift(k)` on the 09:30/16:00 timeline):

| shift | Sharpe | OOS | CAGR | MaxDD |
|---|---|---|---|---|
| 0 | 1.21 | 1.46 | 15.6% | -12.1% |
| 2 rows (1 day stale, same sessions) | **0.68** | 1.54 | 10.4% | -12.4% |
| 4 rows (2 days) | 0.54 | 0.91 | 8.8% | -14.8% |
| 1 row (session-inverted: overnight book held intraday) | -0.39 | -0.50 | -0.5% | -40.6% |

Per sleeve at shift 2: overnight 0.99 -> 0.73 (CAGR 12.2 -> 10.0%), reversal 0.75 -> 0.21
(11.2 -> 5.7%). Decays but survives -> consistent with a real, short-lived edge, not a
lookahead artefact (an artefact collapses to ~0). Note the reversal cannot be expected to
survive this test: a one-day-old gap is a different (and, per the notes, dead) signal.

**6b. Drop years:** drop 2020 -> Sharpe 1.23 (2020 is not the source); drop 2024-25 -> 1.03;
drop 2020 + 2024-25 -> 1.03 (CAGR 12.9%); drop 2010-11 -> 1.25; drop 2020 + 2022 -> 1.27.

**6c. 3-year blocks** (Sharpe ex 4% | ex-cash Sharpe rf 0 | ann. return | ex-cash ann. return):
2010-12 1.18 | 1.27 | 16.9% | 13.3%; 2013-15 1.84 | 2.01 | 16.6% | 13.2%;
2016-18 0.89 | 1.02 | 10.0% | 6.6%; 2019-21 0.83 | 0.90 | 13.3% | 9.8%;
2022-24 1.57 | 1.65 | 20.1% | 16.3%; 2025-26 1.28 | 1.36 | 18.0% | 14.3%. Every block
positive; the weakest six years (2016-21) are ~0.85.

**6d. Cash yield.** `cash_yield_annual`: 4% -> CAGR 15.57%; 2% -> 13.77%; **0% -> 11.99%**.
So 3.6 pp of the 15.6% CAGR is the assumed 4% on idle cash (81% of equity on average),
which did not exist 2010-21. With an approximate realised T-bill path (0.1% 2010-15 ...
5% 2023-24, 3.8% 2026): CAGR 13.35%, Sharpe (excess of actual T-bill) 1.27, MaxDD -12.5%.
**"Every calendar year positive" is false ex-cash: 2019 -2.9% (-1.1% with realised
T-bills), 2016 +0.3%, 2023 +6.9% (vs 10.2% reported).** The Sharpe itself is robust to
the convention (1.21 / 1.25 / 1.30 / 1.27).

**Allocation grid** (`t8_misc.py`): reversal alloc {0, .25, .5, .75, 1} x QQQ-slot
{QQQ, QLD, TQQQ} gives full-sample Sharpe 0.96-1.30 with 0.75/QLD at 1.21 — a plateau, the
profile was not cherry-picked off a spike. Ex-cash attribution: overnight x mult Sharpe(rf0)
1.14 (IS 0.99 / OOS 1.45 / 2023-10+ 2.05), reversal x0.75 0.77 (0.78 / 0.75 / 0.55);
daily correlation between the two -0.006. The drawdown throttle was active only in 2019
(98 sessions) and costs 0.01 Sharpe; it is inert.

**Not blind:** the reversal note admits the VIX gate was chosen from a full-sample VIX-bucket
table, and `PROFILES` comments quote full-sample and OOS stats for each profile, so the
"OOS 1.46" is a holdout for the *signal parameters* only, not for gate/allocation design.

## 7. Paper trader logic — PASS WITH CAVEATS (was FAIL on the version read at the start)

**Version note.** `hf_paper.py` was modified *during* this review (mtime 02:16, after I read
it at 02:11; `paper_state/hf/` was also created by a `trade` run at 02:14 that was not
mine). The first version ran the ensemble on the **hourly** timeline
(`hf_ensemble_weights(md, params=params)` default) with `MarketData(intraday=True)`; on that
version I reproduced two silent divergences (7.1/7.2 below, kept for the record). The current
version runs `timeline="daily"` when no intraday sleeve is funded, loads no hourly data,
and adds `_inject_live_prints` (rebuilds today's Open/Close from 1-minute bars if the daily
row lags). That removes both code paths; the re-test against the current file is below.

What is fine (both versions): masking is correct and verified numerically (Section 1; on the
current daily path the *blank_open* mode of `t1_lookahead.py` is exactly `trade()` at
09:30, 0 diffs at 19 dates); the live trader recomputes the same ensemble function on the
same data and fills at the same panel print as the backtest; costs charged are the backtest
costs; carry is pro-rata like the engine. The paper trader's "decide on the close, fill on
the close" is *mild* hindsight — re-deciding the overnight book from the 15:30 print (what
a real MOC order must do) changes weights on 39% of nights (83 gate flips, 205 size changes
in 730) but Sharpe 1.88 -> 1.77 and MaxDD improves (`t9_execution.py`). The overnight
sleeve is executable as designed.

**7.1 Missing daily row at 09:30.**
*Old (hourly) version — FAIL:* `overnight_weights` builds its 09:30 zero rows from
`md.close.index`; with no daily row for today, `combine_weights` forward-filled the 16:00
targets onto the hourly 09:30 stamp and `trade()` saw a **nonzero** target: reproduced on 5
recent nights, backtest gross 0.000 vs live 0.20-0.51 in QLD/SMH/IWM (`t8_misc.py`).
*Current (daily) version — CAVEAT:* `_inject_live_prints` fetches 1m bars and injects the
Open, so the row normally exists. If that also fails (network), `_resolve_session("auto")`
at 09:32 returns **yesterday's 16:00**, `"open"` returns **yesterday's 09:30**, both are
"already processed" and the run exits without trading: the overnight 2x book is held
through the day until the 16:00 run (verified: on 2026-08-21 the book carried would be
IWM/QLD/SMH 0.162 each). Different mechanism, same exposure. Fix: for a 09:30 session,
`trade()` should abort **loudly** (non-zero exit / alert) if `md.close.index[-1]` is not
today, and the ops runbook should treat "already processed" at 09:3x as an alarm, not a
no-op. Note also that the injected open is the first 1m bar's `Open` (first trade), which
differs from Yahoo's daily Open by >5 bp on ~20% of stock days (3a).

**7.2 Half days.**
*Old (hourly) version — FAIL:* no 16:00 stamp on half days (7 in 2y) -> overnight never
entered (backtest held 0.667 gross into 2023-11-24 and 2024-07-03), and an active reversal
book would be carried into the holiday. *Current (daily) version — PASS:* `px_daily` stamps
the half-day close at 16:00, `auto` at 16:02 resolves to it, weights match the backtest.
Residual nit: the 13:00 close is treated as a 16:00 fill (3 h of hindsight on the close
print; the `[warn] running N min after` message will fire).

**7.3 (UNTESTABLE with this data, highest economic importance) The reversal sleeve assumes
you can rank on the 09:30 print and fill at that print.** Real MOO orders are committed
before 09:28 on pre-market indications; the alternative is a market order after the open.
Bounds from the hourly panel (2023-10+): fill at the 1h-bar open (a different "09:30"
print) costs 0.06 Sharpe; **fill at 10:30 turns the sleeve from Sharpe 0.49 / 2.95 bp/day
into -0.30 / 0.83 bp/day.** The whole edge is inside the first hour and the daily data cannot
say how much is inside the first minute. The paper trader will *not* reveal this: it fills at
the same print it decides on. Treat the reversal sleeve's live P&L as unproven until fills
are compared against the official opening print.

**7.4 Operational.** Any missed session (cron failure, Yahoo outage, rate limit) leaves the
previous session's book on until the next successful run — the backtest never misses a
session. The `last-hour` session now raises `RuntimeError("no last-hour session available
yet")` on the daily path (harmless, but the launchd job will log failures every day).

**7.5 Minor.** Dividends never credited to cash (ex-div nights held lose the dividend vs
the backtest, ~0.1%/yr). Fractional shares are assumed (7 names x ~$14 at alloc 0.75 x
1/7 x 13% average VIX scaling). `_inject_live_prints` leaves today's `AdjFactor`/`aux`
NaN (harmless for the current sleeves). At 15:30 `_mask_for_session` does not blank
today's partial Close/High/Low (only at 09:30); harmless today because no sleeve reads the
daily Close for a 15:30 row, but a future intraday sleeve would silently see a partial-day
close. The 16:00 injected close is the last 1m-bar trade, not the closing-auction print
the backtest uses (ETF median gap ~1 bp, p99 5-15 bp per 3a).

## Ranked issues

1. **Reversal execution assumption (7.3).** Signal print == fill print for single stocks;
   fill one hour late -> negative; fill at the "other" open print -> -0.06 Sharpe; ~20% of
   stock days have >5 bp ambiguity in what the open even was. Paper trading as coded
   cannot test this. Recommend: log the 09:28 pre-market mid, the official open, and the
   assumed fill for every reversal order and settle the question with real data before
   trusting the sleeve's P&L; or move to pre-committed MOO orders on the 09:28 gap and
   backtest *that*.
2. **Live-path fragility at 09:30 (7.1).** If Yahoo's daily row *and* the 1m fallback are
   both unavailable at 09:32, the run exits "already processed" and the overnight 2x book is
   held all day. Make that a loud failure before paper trading starts. (The pre-02:16
   version produced a *nonzero* 09:30 target in this case — worse; now fixed.)
3. **Cost margin (5).** Sharpe 0.5 at 2.84x assumed costs, 0 at 4.15x; the paper trader
   charges the assumed costs so it cannot detect a miss. Real-fill slippage on QLD/SMH at
   the close and on 7 stocks at the open is the number to measure.
4. **Headline dressing (6d).** 3.6 pp of the 15.6% CAGR and the "17/17 positive years" come
   from a flat 4% cash yield that did not exist 2010-21; ex-cash 2019 is -2.9%. Report the
   ex-cash or T-bill-path numbers alongside.
5. **Universe dependence and alpha decay (4).** Ensemble Sharpe 1.21 -> 1.01 on the 38-name
   `config.UNIVERSE`; cross-sectional reversal alpha ~1 bp/day since 2023 versus
   5 bp/day round trip; edge concentrated in 2010-11 / 2020 / 2022. The reversal sleeve is a
   stress-regime satellite and should be sized as one (its own note says 0.10; growth uses
   0.75).
6. **Missed-session behaviour (7.4)**: any cron/data failure holds positions the backtest
   never holds; there is no reconciliation step. (Half days, 7.2, are fixed by the daily
   timeline.)
7. **OOS is not blind (6)** for the VIX gate and the profile/allocation choice; the 1.46 OOS
   Sharpe should be read as "parameters held fixed", not "design held fixed".
8. Cosmetics: `net.iloc[0]=0` drops the first entry cost; GOOG+GOOGL double count; 846
   placeholder opens in Yahoo stock data (0.15% of selections).

What did **not** break: causality (190/190 truncation comparisons identical, live-path masking
identical at 26/26 stamps), engine arithmetic, dividend adjustment, leveraged-ETF
availability, one-day-stale decay (1.21 -> 0.68, not -> 0), 2020 dependence (none), 3-year
blocks (all positive), profile mining (plateau).

## Reproduction

```bash
export MPLCONFIGDIR=/tmp/mpl; cd /tmp/qb_redteam
python3 t0_baseline.py          # headline: Sharpe 1.21 / CAGR 15.57% / MaxDD -12.10% / OOS 1.46
python3 t1_lookahead.py         # 190 truncation/masking comparisons -> 0 diffs
python3 t2_engine.py            # synthetic-panel accounting -> ALL ENGINE CHECKS PASS
python3 t3_data.py; python3 t3b_open_quality.py   # open-print discrepancies, fabricated opens, dividends
python3 t4_survivorship.py      # universe swaps
python3 t56_costs_robustness.py # cost multipliers, shift, drop-years, blocks, cash yield
python3 t7_live_path.py         # hourly (live) path vs daily path, half days, masking test
python3 t8_misc.py              # dd throttle, missing-daily-row fragility, allocation grid, attribution
python3 t9_execution.py         # decide@15:30/fill@16:00; reversal fill at 10:30
```

Key inline snippets:

```python
# 7.1 missing daily row at 09:30 (current daily-path trade()): session resolves to yesterday -> skipped
import datetime as dt, zoneinfo; TZ = zoneinfo.ZoneInfo("America/New_York")
m = copy.deepcopy(md); day = pd.Timestamp("2026-08-21")
for f in m.daily: m.daily[f] = m.daily[f].loc[:day - pd.Timedelta(days=1)]
m.px_daily = m.px_daily.loc[:(day - pd.Timedelta(days=1) + pd.Timedelta(hours=16)).tz_localize(TZ)]
from quantbot.hf_paper import _resolve_session
print(_resolve_session(m, "auto", dt.datetime(2026, 8, 21, 9, 32, tzinfo=TZ)))   # 2026-08-20 16:00 -> "already processed"
# (pre-02:16 hourly version: hf_ensemble_weights(m, params=p).loc[09:30] was IWM/QLD/SMH 0.162 each instead of 0)

# 5 cost multiplier
from quantbot.config import cost_bps_for
cb = {t: cost_bps_for(t) * 2.0 for t in w.columns}
run_session_backtest(w, md.px_daily, cost_bps=cb).stats["sharpe"]        # 0.82

# 6d ex-cash
run_session_backtest(w, md.px_daily, cash_yield_annual=0.0).stats["cagr"]  # 0.1199; yearly 2019 = -0.029
```
