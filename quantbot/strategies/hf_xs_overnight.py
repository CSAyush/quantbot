"""Cross-sectional momentum held overnight (daily timeline: long at 16:00, flat at 09:30).

Hypothesis
----------
Lou, Polk & Skouras (2019, "A tug of war: overnight versus intraday expected
returns") and Hendershott, Livdan & Rosch (2020, "Asset pricing: a tale of
night and day") show that the momentum premium accrues almost entirely in the
overnight session and is partly given back intraday, and that firm-level
overnight returns are persistent. research/notes/overnight.md 2d confirmed
the first part in this universe: the top-5 12-1 momentum mega-caps earned
+12.9 bp/night gross 16:00 -> 09:30 vs +4.5 bp for the equal-weight 70 and
+3.6 bp for the bottom-10 losers. This sleeve is the built-out version of
that finding, with three implementation modes that differ in how much
overnight *market* beta they carry (the ensemble is already long equity beta
overnight through the QQQ/SMH/IWM sleeve; the new information here is the
cross-sectional part):

  mode="long"        long the top-n names, 16:00 -> 09:30, gated on SPY > 200d MA.
  mode="orthogonal"  same, but only on nights when the live ETF overnight sleeve
                     (hf_overnight defaults) is flat. Time-orthogonal to it by
                     construction (zero return overlap), so the ensemble never
                     has to split the 1.0 cash budget between the two.
  mode="hedged"      stock leg plus a long position in an inverse index ETF
                     (SH / PSQ, 2 bp/side) sized to the book's trailing beta,
                     within the gross-long cap. Isolates the cross-sectional
                     alpha; pays the hedge's cost and gives up the overnight
                     market premium.

Signals (all evaluated at the 16:00 close of day d from data through d)
------------------------------------------------------------------------
  "mom"            12-1 price momentum: close[d-mom_skip] / close[d-mom_long] - 1
                   (optionally divided by trailing daily vol, `mom_scaled`).
  "lps"            Lou-Polk-Skouras persistence: trailing `lps_window`-day sum
                   of the stock's own overnight returns (close[k-1] -> open[k]),
                   the last of which ended at today's open.
  "combo"          mean of the cross-sectional z-scores of "mom" and "lps".
  "ownrule"        the live ETF rule per stock: hold names whose close is above
                   their own 200d MA and whose last-5 overnight sum is < 0,
                   ranked by the most negative 5-night sum.
  "intraday_loser" today's beta-adjusted open -> close return, ascending
                   (tug-of-war reversal: long tonight what lost today).

Optional per-name masks: `own_trend` (close > own MA), `own_on_reversal`
(own 5-night overnight sum < 0), `top_liquidity` (K most liquid names by
trailing median dollar volume, a pseudo point-in-time screen against the
survivorship bias of a 2026 constituent snapshot).

Weights are equal (or inverse-vol) across the n names, sum to <= max_gross;
an explicit 0.0 row is emitted at every 09:30 so nothing is held intraday.
Nothing uses data stamped after the 16:00 decision timestamp.

See research/notes/xs_overnight.md for the research trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quantbot.config import HF_STOCKS
from quantbot.data import MarketData

ET = "America/New_York"


@dataclass
class XSOvernightParams:
    # --- ranking signal ---
    signal: str = "combo"          # "mom" | "lps" | "combo" | "ownrule" | "intraday_loser"
    mom_long: int = 252            # 12-1 momentum: close[d-mom_skip] / close[d-mom_long] - 1
    mom_skip: int = 21
    mom_scaled: bool = False       # divide momentum by trailing daily vol
    lps_window: int = 63           # trailing window (days) for the own-overnight persistence signal
    n: int = 5                     # names held
    weighting: str = "eq"          # "eq" | "ivol"
    vol_window: int = 20           # trailing std window for ivol / scaling
    # --- per-name masks ---
    own_trend: bool = False        # require close > own `own_ma_window`-day MA
    own_on_reversal: bool = False  # require own last-`own_on_window` overnight sum < 0
    own_ma_window: int = 200
    own_on_window: int = 5
    # --- market gate (validated in overnight.md: no overnight premium below the 200d MA) ---
    gate_ticker: str | None = "SPY"
    ma_window: int = 200
    # --- universe: the core 70 mega-caps (2.5 bp/side) whatever config md was built with;
    #     None = every name in md.stocks() (300 on the wide config, 5 bp/side outside the 70) ---
    universe: tuple[str, ...] | None = field(default_factory=lambda: tuple(HF_STOCKS))
    top_liquidity: int | None = None           # keep only the K most liquid names each day
    liq_window: int = 60                       #   (trailing median Close*Volume through d)
    # --- independence modes ---
    mode: str = "long"             # "long" | "orthogonal" | "hedged"
    hedge_ticker: str = "SH"       # inverse ETF for mode="hedged"
    hedge_ratio: float | None = None   # None -> trailing beta of the book to SPY; else fixed
    beta_window: int = 120         # days of daily returns for the beta estimate
    hedge_cap: float = 1.5         # cap on the beta estimate
    # --- sizing ---
    max_gross: float = 1.0
    start: str | None = None       # optional first date of weights


def _universe(md: MarketData, p: XSOvernightParams) -> list[str]:
    st = md.stocks()
    if p.universe is not None:
        keep = set(p.universe)
        st = [s for s in st if s in keep]
    return st


def _scores(md: MarketData, p: XSOvernightParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(score, vol) indexed by trading day, columns = stocks. Higher score =
    buy first. Every value on row d is computable at the 16:00 close of d."""
    st = _universe(md, p)
    close, open_ = md.close[st], md.open[st]
    r1 = close.pct_change(fill_method=None)
    vol = r1.rolling(p.vol_window, min_periods=int(p.vol_window * 0.75)).std()
    # Overnight return that ended at today's open: close[d-1] -> open[d].
    on = open_ / close.shift(1) - 1.0

    if p.signal == "mom":
        score = close.shift(p.mom_skip) / close.shift(p.mom_long) - 1.0
        if p.mom_scaled:
            score = score / vol
    elif p.signal == "lps":
        score = on.rolling(p.lps_window, min_periods=int(p.lps_window * 0.75)).sum()
    elif p.signal == "combo":
        mom = close.shift(p.mom_skip) / close.shift(p.mom_long) - 1.0
        lps = on.rolling(p.lps_window, min_periods=int(p.lps_window * 0.75)).sum()
        z = lambda x: x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)  # noqa: E731
        score = (z(mom) + z(lps)) / 2.0
    elif p.signal == "ownrule":
        score = -on.rolling(p.own_on_window, min_periods=p.own_on_window).sum()
    elif p.signal == "intraday_loser":
        rid = close / open_ - 1.0
        rspy = md.close["SPY"].pct_change(fill_method=None)
        mp = int(p.beta_window * 0.66)
        beta = r1.rolling(p.beta_window, min_periods=mp).cov(rspy).div(
            rspy.rolling(p.beta_window, min_periods=mp).var(), axis=0).shift(1)
        spy_id = md.close["SPY"] / md.open["SPY"] - 1.0
        score = -(rid.sub(beta.mul(spy_id, axis=0)))     # biggest loser -> highest score
    else:
        raise ValueError(f"unknown signal {p.signal!r}")

    if p.own_trend or p.signal == "ownrule":
        ma = close.rolling(p.own_ma_window, min_periods=p.own_ma_window).mean()
        score = score.where(close > ma)
    if p.own_on_reversal or p.signal == "ownrule":
        on_k = on.rolling(p.own_on_window, min_periods=p.own_on_window).sum()
        score = score.where(on_k < 0.0)
    if p.top_liquidity is not None:
        dvol = (close * md.daily["Volume"][st]).rolling(
            p.liq_window, min_periods=int(p.liq_window * 0.75)).median()
        liquid = dvol.rank(axis=1, ascending=False) <= p.top_liquidity
        score = score.where(liquid)
    # Never rank a name on the day it has no close (delisted / not yet listed).
    score = score.where(close.notna())
    return score, vol


def _etf_sleeve_on(md: MarketData) -> pd.Series:
    """Boolean by trading day: does the live ETF overnight sleeve hold anything tonight?"""
    from quantbot.strategies.hf_overnight import overnight_weights
    ow = overnight_weights(md)
    ow = ow[ow.index.hour == 16]
    on = ow.abs().sum(axis=1) > 0
    on.index = pd.DatetimeIndex(on.index).tz_convert(ET).tz_localize(None).normalize()
    return on


def xs_overnight_weights(md: MarketData, p: XSOvernightParams = XSOvernightParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline.

    16:00 rows: the sleeve's book for the night (stocks, plus the inverse ETF in
    "hedged" mode); 09:30 rows: explicit 0.0 (flat during the day).
    """
    score, vol = _scores(md, p)
    dates = pd.DatetimeIndex(score.index)

    picks = score.rank(axis=1, ascending=False, method="first").le(p.n)
    m = picks.astype(float)
    if p.weighting == "ivol":
        m = m * (1.0 / vol).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    w = m.div(m.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)

    # Night-level gate(s).
    hold = pd.Series(True, index=dates)
    if p.gate_ticker is not None:
        g = md.close[p.gate_ticker]
        ma = g.rolling(p.ma_window, min_periods=p.ma_window).mean()
        hold &= (g > ma).reindex(dates).fillna(False)
    if p.mode == "orthogonal":
        etf_on = _etf_sleeve_on(md).reindex(dates).fillna(False)
        hold &= ~etf_on
    w = w.mul(hold.astype(float), axis=0)

    if p.mode == "hedged":
        if p.hedge_ticker not in md.close.columns:
            raise KeyError(f"{p.hedge_ticker} not in market data")
        if p.hedge_ratio is None:
            st = list(w.columns)
            r1 = md.close[st].pct_change(fill_method=None)
            rspy = md.close["SPY"].pct_change(fill_method=None)
            mp = int(p.beta_window * 0.66)
            beta = r1.rolling(p.beta_window, min_periods=mp).cov(rspy).div(
                rspy.rolling(p.beta_window, min_periods=mp).var(), axis=0)
            book_beta = (w * beta.fillna(1.0)).sum(axis=1)          # w sums to 1 on active nights
            ratio = book_beta.clip(lower=0.0, upper=p.hedge_cap).where(w.sum(axis=1) > 0, 0.0)
        else:
            ratio = pd.Series(p.hedge_ratio, index=dates).where(w.sum(axis=1) > 0, 0.0)
        # Stock leg s, hedge leg s*ratio, s*(1+ratio) <= max_gross.
        s = (p.max_gross / (1.0 + ratio)).clip(upper=p.max_gross)
        hedge = (s * ratio).where(md.close[p.hedge_ticker].reindex(dates).notna(), 0.0)
        w = w.mul(s, axis=0)
        w[p.hedge_ticker] = hedge
    else:
        gross = w.sum(axis=1)
        over = gross > p.max_gross
        if over.any():
            w.loc[over] = w.loc[over].div(gross[over], axis=0) * p.max_gross

    if p.start is not None:
        w = w.loc[pd.Timestamp(p.start):]
        dates = pd.DatetimeIndex(w.index)

    close_idx = (dates + pd.Timedelta(hours=16)).tz_localize(ET)
    open_idx = (dates + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    w_close = w.copy()
    w_close.index = close_idx
    w_open = pd.DataFrame(0.0, index=open_idx, columns=w.columns)
    out = pd.concat([w_close, w_open]).sort_index().fillna(0.0)
    return out.reindex(out.index.intersection(md.px_daily.index))
