# Research brief: short-horizon sleeves for quantbot

## Objective

Build one sleeve of a short-horizon (twice-daily + last-hour) US equity system
that will be paper-traded with **$1,000 of fake money** and monitored live.
The goal is the best *risk-adjusted, cost-robust, out-of-sample-credible* edge
you can find in your assigned area. We combine sleeves afterwards; a sleeve with
Sharpe 0.8 and low correlation to the others is more valuable than Sharpe 1.5
that only works in one year.

Non-negotiables:
- **No lookahead.** A weight stamped at timestamp t may only use data with
  timestamp <= t. On the daily timeline: at `16:00` of day d you may use day d's
  full OHLCV and aux (VIX) values; at `09:30` of day d you may use day d's
  **Open only** plus everything through day d-1. On the hourly timeline: at
  bar-end t you may use bars that ended at or before t.
- **Costs are real.** Default per-side costs: ETFs 1.0 bp, leveraged ETFs 2.0 bp,
  stocks 2.5 bp (`quantbot.config.cost_bps_for`). Always report net.
  Twice-daily round trips in stocks cost ~5 bp/day = ~12%/yr; a sleeve must
  clear that.
- **Count your trials.** Every parameter combination and variant you evaluate
  is a trial; report the total as `n_trials` so the deflated Sharpe is honest.
- **Report negative results.** "This doesn't work after costs" is a valid,
  useful deliverable. Do not torture parameters until something looks good.

## Account constraints (matter for design)

- $1,000 cash account: no margin. Gross **long** exposure <= 1.0 of equity.
  Leverage above 1x only via 2x/3x ETFs (SSO, QLD, UPRO, TQQQ are in the universe).
- Shorts are allowed in the paper account (weights < 0) but treat them as a
  luxury: prefer long-only or long-biased designs, and if you use shorts, show
  the long-only variant too.
- Executions: market-on-open (09:30 print), market-on-close (16:00 print), or a
  market order at an hourly bar end (e.g. 15:30). Nothing finer than hourly.

## Data & API (all in `quantbot/`)

```python
from quantbot.config import HFConfig, cost_bps_for
from quantbot.data import MarketData, session_dates
from quantbot.engine import run_session_backtest, combine_weights, yearly_returns
from quantbot.research import report
from quantbot.validation import split_stats, bootstrap_sharpe_ci, deflated_sharpe, sensitivity, yearly_table

md = MarketData(HFConfig(), refresh=False)   # ~5s from cache; do NOT pass refresh=True
md.tickers            # 94 tradables: 24 ETFs (md.etfs()) + 70 mega-caps (md.stocks())
md.daily["Open"|"High"|"Low"|"Close"|"Volume"|"AdjFactor"]   # DataFrame(date -> ticker), 2010-01 -> now, adjusted
md.close, md.open     # shortcuts
md.aux                # DataFrame(date -> ["^VIX","^VIX3M","^VIX9D"]), ^VIX3M/^VIX9D start ~2011
md.px_daily           # price panel, index = tz-aware ET timestamps at 09:30 and 16:00 each day (2010 ->)
md.intraday["Open"|...]  # hourly bars, index = bar START (09:30, 10:30, ..., 15:30 ET), ~2023-10 -> now
md.px_intraday        # price panel on hourly timeline: 09:30 (open), 10:30, ..., 15:30, 16:00 (close)
                      # NOTE: the 15:30 stamp is the price at 15:30; 16:00 is the closing print.
                      # Half days end at 12:30. Dividend-adjusted to match the daily panel.
```

Weights contract:

```python
def my_sleeve_weights(md: MarketData, p: MySleeveParams = MySleeveParams()) -> pd.DataFrame
```
- Returns a DataFrame indexed by a **subset of** `md.px_daily.index` (or
  `md.px_intraday.index` for intraday sleeves), columns = tickers, values =
  target weights *after* trading at that timestamp.
- The engine forward-fills targets: if you want to be flat at 09:30 you MUST
  emit an explicit 0.0 row at 09:30. Positions persist until you change them.
- Sum of |weights| should be <= 1.0 (the ensemble scales sleeves down later;
  do not pre-lever inside the sleeve except via leveraged ETFs).
- Put all tunables in a `@dataclass` `MySleeveParams` in the same file.

Backtest + scorecard:

```python
res = run_session_backtest(weights, md.px_daily, label="my sleeve")   # or md.px_intraday
report(res, split="2022-01-01", n_trials=<count>, benchmark_daily=md.close["SPY"].pct_change())
res.daily_returns, res.stats, res.weights, res.turnover, res.costs
```
Use split `2022-01-01` on the daily timeline and `2025-09-01` on the hourly
timeline (last ~12 months out-of-sample). Tune only on the in-sample part.

Baselines to beat (net of default costs, daily timeline 2010-2026):
- SPY buy & hold: CAGR 14.2%, vol 17.1%, Sharpe 0.86, MaxDD -34%
- QQQ overnight only (long 16:00 -> 09:30 every day): CAGR 8.1%, Sharpe 0.68,
  MaxDD -30%, costs 5%/yr; OOS (2022+) Sharpe 0.39
- SPY overnight only: Sharpe ~0.2 in this period; the plain overnight anomaly
  in SPY has been weak since 2010, so conditioning is where the value is.

## Deliverables

1. `quantbot/strategies/hf_<sleeve>.py` - clean, documented, causal
   implementation with a `<Sleeve>Params` dataclass and `<sleeve>_weights()`.
   Import only from `quantbot.*` and pandas/numpy/scipy. Must run in < 60 s.
2. `research/notes/<sleeve>.md` with, in this order:
   - Hypothesis and the literature it rests on (1 paragraph)
   - Everything you tested (table of variants -> net Sharpe, CAGR, MaxDD); state `n_trials`
   - Final scorecard (paste the `report()` output) incl. OOS split and yearly table
   - Sensitivity: does performance degrade smoothly around the chosen params?
   - Correlation of daily returns with SPY and, if available, with other
     sleeves' notes already in `research/notes/`
   - Failure modes / when this sleeve should be turned off
   - Recommended params and a suggested allocation weight in the ensemble
   - **Insights for other sleeves** (things you found that others should use)
3. Final message to the orchestrator: a <= 25-line summary of the above with
   the key numbers.

## Round 2 addendum (breadth & diversification)

Round 1 produced the live system: overnight sleeve (QQQ/SMH/IWM, 16:00->09:30)
+ gap-fade reversal (7 of 70 mega-caps, 09:30->16:00, VIX-gated), regime layer,
growth profile Sharpe 1.31 / CAGR 11.5% / MaxDD -12.2% (2010-2026, T-bill cash,
Sharpe excess of it), OOS 2022+ Sharpe 1.53. See `overnight.md`, `reversal.md`,
`regime.md`, `intraday_momentum.md` (negative), `REDTEAM.md` (audit).

Round 2 goal: raise the ensemble Sharpe by adding *independent bets*, not
speed. Changes since round 1 that you should know:
- `HFConfig.wide()` gives 300 stocks (`quantbot/universe_wide.py`, 300 largest
  S&P names, snapshot early 2026 => survivorship bias, state it) plus 16 extra
  ETFs (`HF_EXTRA_ETFS`: XLC XLRE XLB IEI TIP LQD USO UNG DBC VNQ FXI EWJ KRE XBI
  IBB ARKK). Data is already cached; `MarketData(HFConfig.wide(), refresh=False)`
  loads in ~5 s. Do NOT pass refresh=True.
- Cash yield: use `rf = md.cash_yield()` (historical ^IRX) and pass
  `cash_yield_annual=rf` to `run_session_backtest`; Sharpe is excess of it.
  `report()` handles this automatically.
- `HFConfig()` (core, 70 stocks + 24 ETFs) is what the LIVE paper account runs.
  If you modify an existing sleeve file, its default parameters on the core
  config MUST produce bit-identical weights to before (check with a diff).
- Correlation with the existing sleeves matters as much as standalone Sharpe.
  Compute daily-return correlation with `overnight_weights(md)` and
  `reversal_weights(md)` run through the engine, and report the ensemble Sharpe
  with your sleeve added at 0.25 / 0.5 / 1.0 allocation on top of the growth
  profile (`EnsembleParams.from_profile("growth")`, `hf_ensemble_weights`).

## Rules of engagement

- Only create/modify **your** two files. Do not edit `config.py`, `data.py`,
  `engine.py`, `metrics.py`, `validation.py`, `research.py`, `paper.py`,
  `run.py`, or another sleeve's files. If you find a bug in shared code,
  describe it precisely in your notes and work around it locally.
- Scratch scripts go in `/tmp/qb_<sleeve>/`, not in the repo.
- Set `export MPLCONFIGDIR=/tmp/mpl` before running python (matplotlib warning).
- Read other sleeves' notes in `research/notes/` as they appear; reuse insights.
- Be decisive. You have a fixed budget; a well-validated simple sleeve beats an
  unfinished complex one.

## Run Commands
python3 run.py hf status
