"""Central configuration for the quantbot system."""
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data_cache"
STATE_DIR = PROJECT_ROOT / "paper_state"

# Liquid, large-cap universe across sectors. Survivorship bias caveat: this is
# today's list applied historically, which flatters backtest results somewhat.
UNIVERSE = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AVGO", "CRM", "ADBE", "ORCL",
    # Financials
    "JPM", "BAC", "GS", "V", "MA", "BRK-B",
    # Healthcare
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO",
    # Consumer
    "WMT", "COST", "PG", "KO", "PEP", "MCD", "HD", "NKE",
    # Industrials / Energy / Utilities
    "CAT", "HON", "UNP", "GE", "XOM", "CVX", "NEE",
    # Communications / Other
    "DIS", "NFLX", "TMUS",
]

BENCHMARK = "SPY"

# ---------------------------------------------------------------------------
# Short-horizon ("hf") system universe. Everything here trades with sub-2bp
# spreads and has MOO/MOC auction liquidity, which is what makes twice-daily
# (and last-hour) trading survivable on a small account.
# ---------------------------------------------------------------------------
HF_INDEX_ETFS = ["SPY", "QQQ", "IWM", "DIA"]
HF_SECTOR_ETFS = ["SMH", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU"]
HF_OTHER_ETFS = ["TLT", "IEF", "GLD", "SLV", "HYG", "EEM", "EFA"]
# 2x/3x funds: the only way a $1k cash account gets >1x exposure without margin.
HF_LEVERAGED_ETFS = ["SSO", "QLD", "UPRO", "TQQQ"]
HF_ETFS = HF_INDEX_ETFS + HF_SECTOR_ETFS + HF_OTHER_ETFS + HF_LEVERAGED_ETFS

HF_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "AVGO", "TSLA", "BRK-B",
    "JPM", "V", "MA", "UNH", "XOM", "LLY", "JNJ", "PG", "HD", "COST",
    "MRK", "ABBV", "CVX", "PEP", "KO", "WMT", "BAC", "CRM", "NFLX", "AMD",
    "ADBE", "ORCL", "TMO", "CSCO", "ACN", "MCD", "ABT", "LIN", "DIS", "WFC",
    "TXN", "INTC", "INTU", "CAT", "IBM", "GE", "QCOM", "AMGN", "CMCSA", "VZ",
    "PFE", "NKE", "HON", "UNP", "LOW", "BA", "GS", "MS", "SPGI", "BLK",
    "AXP", "RTX", "SBUX", "T", "MDT", "BMY", "GILD", "ISRG", "NOW", "PANW",
]

# Wide universe (300 largest S&P 500 names) for breadth research; opt in via
# HFConfig(stocks=HF_STOCKS_WIDE) or HFConfig.wide().
from .universe_wide import HF_STOCKS_WIDE  # noqa: E402

# Additional liquid ETFs used by the cross-asset / sector sleeves research.
HF_EXTRA_ETFS = ["XLC", "XLRE", "XLB", "IEI", "TIP", "LQD", "USO", "UNG", "DBC", "VNQ", "FXI", "EWJ", "KRE", "XBI", "IBB", "ARKK"]

# Non-tradable auxiliary series (regime signals + the 13-week T-bill yield,
# which is what idle cash actually earned in each year of the backtest).
HF_AUX = ["^VIX", "^VIX3M", "^VIX9D", "^IRX"]

# Per-side cost assumptions in bps (half-spread + slippage; commissions are 0).
# Reference: SPY quotes a $0.01 spread on a ~$700 price (0.15 bp full spread);
# QQQ/IWM/SMH 0.3-0.7 bp; mega-caps 0.5-3 bp; TQQQ ~1.2 bp. MOO/MOC auction
# fills pay no spread at all. These defaults are therefore 2-5x conservative.
COST_BPS_ETF = 1.0
COST_BPS_LEVERAGED_ETF = 2.0
COST_BPS_STOCK = 2.5          # the 70 mega-caps in HF_STOCKS
COST_BPS_STOCK_WIDE = 5.0     # anything outside them (mid-liquidity S&P names)


def cost_bps_for(ticker: str) -> float:
    if ticker in HF_LEVERAGED_ETFS:
        return COST_BPS_LEVERAGED_ETF
    if ticker in HF_ETFS or ticker in HF_EXTRA_ETFS:
        return COST_BPS_ETF
    if ticker in HF_STOCKS:
        return COST_BPS_STOCK
    return COST_BPS_STOCK_WIDE


@dataclass
class Config:
    universe: list[str] = field(default_factory=lambda: list(UNIVERSE))
    benchmark: str = BENCHMARK

    # --- Transaction cost model (paid on turnover) ---
    commission_bps: float = 1.0   # per side, generous for a zero-commission era
    slippage_bps: float = 5.0     # market impact + spread for liquid large caps

    # --- Portfolio construction ---
    max_weight: float = 0.10          # max 10% in any single name
    target_vol: float = 0.18          # annualized portfolio vol target
    vol_lookback: int = 20            # days used to estimate current vol
    max_leverage: float = 1.0         # long-only, no margin
    cash_yield_annual: float = 0.03   # T-bill yield earned on uninvested cash

    # --- Risk management ---
    regime_ma: int = 200              # SPY below this MA => defensive mode
    defensive_exposure: float = 0.5   # gross exposure multiplier in defensive mode
    dd_throttle: float = 0.12         # strategy drawdown that triggers de-risking
    dd_exposure: float = 0.5          # exposure multiplier while throttled

    # --- Strategy ensemble weights ---
    w_momentum: float = 0.45
    w_trend: float = 0.40
    w_meanrev: float = 0.15
    rebalance_days: int = 5           # slow sleeves rebalance weekly

    # --- Momentum params ---
    mom_lookback: int = 126           # ~6 months
    mom_skip: int = 21                # skip most recent month (reversal effect)
    mom_top_n: int = 10

    # --- Trend params ---
    trend_fast: int = 50
    trend_slow: int = 200

    # --- Mean reversion params ---
    mr_lookback: int = 5
    mr_zscore_entry: float = -1.5
    mr_zscore_exit: float = -0.25    # exit once the stretch has largely closed
    mr_max_hold: int = 10            # days; time-stop if reversion never comes
    mr_top_n: int = 8                # max concurrent positions

    # --- Paper trading ---
    starting_cash: float = 100_000.0


@dataclass
class HFConfig:
    """Configuration for the short-horizon (twice-daily + last-hour) system."""
    etfs: list[str] = field(default_factory=lambda: list(HF_ETFS))
    stocks: list[str] = field(default_factory=lambda: list(HF_STOCKS))
    aux: list[str] = field(default_factory=lambda: list(HF_AUX))
    benchmark: str = "SPY"

    # Cash account, so no margin: gross long exposure <= 1.0 in cash terms.
    # Leverage beyond that comes only from 2x/3x ETFs. Shorts are allowed in
    # paper trading (they would need a margin account for real).
    max_gross: float = 1.0
    # Backtests use the historical 13-week T-bill yield (^IRX) for idle cash;
    # this flat rate is the fallback when ^IRX is unavailable and is what the
    # paper account accrues going forward.
    cash_yield_annual: float = 0.04
    borrow_bps_annual: float = 50.0     # stock-loan fee on short positions

    # Session timeline
    intraday_interval: str = "1h"        # yfinance interval for intraday bars
    history_start: str = "2010-01-01"    # daily history start

    # Paper trading
    starting_cash: float = 1_000.0
    min_trade_dollars: float = 5.0

    @property
    def tradable(self) -> list[str]:
        return self.etfs + self.stocks

    @classmethod
    def wide(cls) -> "HFConfig":
        """Research config: 300-name stock universe plus extra ETFs."""
        return cls(etfs=list(HF_ETFS) + list(HF_EXTRA_ETFS),
                   stocks=sorted(set(HF_STOCKS) | set(HF_STOCKS_WIDE)))
