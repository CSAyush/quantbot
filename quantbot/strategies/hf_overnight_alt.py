"""Non-equity (precious-metals) overnight sleeve (daily timeline: long at
16:00, flat at 09:30). Status: SHADOW candidate, not for live capital - see
research/notes/overnight_alt.md for the verdict and the numbers behind it.

Hypothesis
----------
The overnight premium is not only an equity-beta phenomenon. Gold's return
accrues largely outside London/New York trading hours (Caminschi & Heaney
2014, "Fixing a leaky fixing"), and the ETF overnight literature (Lou, Polk &
Skouras 2019; Bogousslavsky 2021) finds a positive close-to-open drift in
most liquid ETFs. In this data set GLD, SLV, GDX, XLE, XOP earn 3.5-9 bp per
night gross with ~zero or negative intraday return (research/notes/
overnight.md 2a and overnight_alt.md 2.1), but unconditionally they carry
-35% to -70% drawdowns and net Sharpes of 0.2-0.5.

What was tested and what survived
---------------------------------
The pre-registered plan applied the live equity sleeve's two gates (own
close > 200d MA AND own last-5-nights overnight sum < 0) to each commodity
ETF's own series. That rule does NOT transfer: it selects nights no better
than average for GLD/SLV/GDX/USO/DBC, and the two assets that passed the
in-sample selection screen (XLE, XOP) reversed out-of-sample (IS Sharpe 0.69,
OOS -0.28) and lowered the ensemble Sharpe. `OvernightAltParams.preregistered()`
reproduces that configuration.

The pre-registered gold-specific question - does GLD's overnight return
depend on the sign of the same day's US-session (open->close) return? - had
a clear answer: it *continues* rather than reverses. GLD above its 200d MA
earns +6.4 bp/night after an up session (t 3.0; IS +5.2, OOS +8.4) versus
+1.6 bp (t 0.7) after a down session; SLV +14.4 bp vs +9.4 bp; GDX +13.0 vs
-4.4. QQQ shows no such asymmetry (6.2 vs 5.7 bp), so this is a commodity
feature, not a generic one. Defining "up" on the close-to-close or on the
previous overnight gap instead of the US session destroys the effect
(Sharpe 0.65 -> 0.38 -> 0.18), i.e. the information is specifically the
London/New-York session move carrying into the Asian session.

Default rule (evaluated at the 16:00 close of day d)
----------------------------------------------------
Hold 1/len(assets) of each of GLD, SLV that night iff
1. close[d] > own `ma_window`-day simple MA (trend gate), and
2. close[d] / open[d] - 1 > 0 (today's US session was up; `intraday_sign`).
Explicit 0.0 row at 09:30. Gross long capped at `max_gross`. Nothing here
uses data stamped after the 16:00 decision timestamp.

Honest caveats: the variant was chosen after the pre-registered default
failed (67 trials in total); 48% of its full-sample excess return comes from
2011 (silver bubble) and the 2012-2019 Sharpe is -0.02; it earns money only
in precious-metals bull markets (2011, 2016, 2020, 2025-26).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantbot.data import MarketData

ET = "America/New_York"


@dataclass
class OvernightAltParams:
    # ETFs held overnight; each gets 1/len(assets) of the sleeve when its
    # signal is on. GLD + SLV: the two pure precious-metal ETFs (1 bp/side).
    # GDX (miners, 2 bp/side, equity beta) adds nothing (see notes 2.4).
    assets: tuple[str, ...] = ("GLD", "SLV")
    # Trend gate on the asset's OWN close vs its `ma_window`-day simple MA.
    require_own_trend: bool = True
    ma_window: int = 200
    # Optional additional gate on the equity market trend (SPY > its MA).
    # Off by default: metals' overnight returns do not depend on the equity
    # trend (adding it changes the Sharpe by -0.01) and the ensemble's regime
    # multiplier is an equity-vol construct that should not scale this sleeve.
    require_spy_trend: bool = False
    spy_ticker: str = "SPY"
    # Overnight-reversal gate (the live equity sleeve's second gate): trailing
    # sum of the asset's last `on_window` overnight returns must be
    # < on_threshold. OFF by default: it does not transfer to commodities.
    require_on_reversal: bool = False
    on_window: int = 5
    on_threshold: float = 0.0
    # Same-day US-session sign filter: "up" = hold only when today's
    # open->close return > 0 (default; the continuation effect), "down" =
    # only when < 0, None = off.
    intraday_sign: str | None = "up"
    # "equal": 1/len(assets) per active slot (default, like the live sleeve).
    # "inverse_vol": slot * min(vol_target / realised vol, vol_cap). Lowers
    # MaxDD (-13% vs -17%) at a lower Sharpe (0.57 vs 0.65); off.
    weighting: str = "equal"
    vol_target: float = 0.15
    vol_window: int = 20
    vol_cap: float = 1.0
    # Hard cap on gross long exposure (cash account).
    max_gross: float = 1.0

    @classmethod
    def preregistered(cls) -> "OvernightAltParams":
        """The pre-registered configuration from the research plan: the live
        equity sleeve's two gates on each asset's own series, assets chosen
        in-sample by 'IS net Sharpe > 0.3 and c2c corr with QQQ < 0.5'
        (-> XLE, XOP). Kept for reproducibility; it failed the gate
        (Sharpe 0.32, IS 0.69, OOS -0.28)."""
        return cls(assets=("XLE", "XOP"), require_own_trend=True, ma_window=200,
                   require_on_reversal=True, on_window=5, on_threshold=0.0,
                   intraday_sign=None)


def _signals(md: MarketData, ticker: str, p: OvernightAltParams) -> pd.Series:
    """Boolean Series (date -> hold tonight?) using only data through that
    day's 16:00 close."""
    c = md.close[ticker]
    o = md.open[ticker]
    ok = c.notna()
    if p.require_own_trend:
        ma = c.rolling(p.ma_window, min_periods=p.ma_window).mean()
        ok &= c > ma
    if p.require_spy_trend:
        s = md.close[p.spy_ticker]
        sma = s.rolling(p.ma_window, min_periods=p.ma_window).mean()
        ok &= s > sma
    if p.require_on_reversal:
        # Overnight return that *ended* at today's open: close[d-1] -> open[d].
        on_prev = o / c.shift(1) - 1.0
        trail = on_prev.rolling(p.on_window, min_periods=p.on_window).sum()
        ok &= trail < p.on_threshold
    if p.intraday_sign is not None:
        intra = c / o - 1.0          # today's open -> close, known at 16:00
        if p.intraday_sign == "down":
            ok &= intra < 0
        elif p.intraday_sign == "up":
            ok &= intra > 0
        else:
            raise ValueError(f"intraday_sign must be None, 'down' or 'up', got {p.intraday_sign!r}")
    return ok.fillna(False)


def overnight_alt_weights(md: MarketData, p: OvernightAltParams = OvernightAltParams()) -> pd.DataFrame:
    """Target weights on md.px_daily's timeline.

    16:00 rows: 1/len(assets) in each ETF whose signal is on (0 otherwise),
    09:30 rows: explicit 0.0 (flat during the day).
    """
    dates = pd.DatetimeIndex(md.close.index)
    slot = 1.0 / len(p.assets)
    held: dict[str, pd.Series] = {}
    for t in p.assets:
        if t not in md.close.columns:
            raise KeyError(f"{t} not in market data")
        w = _signals(md, t, p).astype(float) * slot
        if p.weighting == "inverse_vol":
            rv = md.close[t].pct_change().rolling(p.vol_window, min_periods=p.vol_window).std() * np.sqrt(252)
            scale = (p.vol_target / rv).clip(upper=p.vol_cap)
            w = (w * scale).fillna(0.0)
        elif p.weighting != "equal":
            raise ValueError(f"weighting must be 'equal' or 'inverse_vol', got {p.weighting!r}")
        held[t] = held.get(t, 0.0) + w
    w_close = pd.DataFrame(held, index=dates).fillna(0.0)

    gross = w_close.sum(axis=1)
    over = gross > p.max_gross
    if over.any():
        w_close.loc[over] = w_close.loc[over].div(gross[over], axis=0) * p.max_gross

    close_idx = (dates + pd.Timedelta(hours=16)).tz_localize(ET)
    open_idx = (dates + pd.Timedelta(hours=9, minutes=30)).tz_localize(ET)
    w_close.index = close_idx
    w_open = pd.DataFrame(0.0, index=open_idx, columns=w_close.columns)
    out = pd.concat([w_close, w_open]).sort_index()
    # Only rows that exist on the price panel (guards against calendar drift).
    return out.reindex(out.index.intersection(md.px_daily.index))
