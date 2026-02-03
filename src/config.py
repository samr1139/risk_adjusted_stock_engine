"""All configurable parameters for the stock risk engine."""

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "market.db"

# ── Ticker Universe ──────────────────────────────────────────────────────────
# Set to a non-empty list to override automatic S&P 500 fetch.
CUSTOM_TICKERS: list[str] = []

DEFAULT_TICKERS: list[str] = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "BRK-B",
    "JPM", "JNJ", "V", "UNH", "PG", "HD", "MA", "DIS", "BAC", "XOM",
    "PFE", "KO", "PEP", "CSCO", "INTC", "NFLX", "ADBE", "CRM", "ABT",
    "CVX", "WMT", "MRK",
]

# ── Price Data ───────────────────────────────────────────────────────────────
HISTORY_YEARS = 2
PRICE_INTERVAL = "1d"

# ── Rolling Windows ──────────────────────────────────────────────────────────
TRADING_DAYS_PER_YEAR = 252
WINDOW_12M = 252
WINDOW_6M = 126
WINDOW_3M = 63

# ── Minimum History ──────────────────────────────────────────────────────────
MIN_TRADING_DAYS = 200

# ── Momentum Weights ─────────────────────────────────────────────────────────
MOMENTUM_3M_WEIGHT = 0.6
MOMENTUM_12M_WEIGHT = 0.4

# ── Risk Profile Penalty Weights ─────────────────────────────────────────────
# raw_score = annualized_return - α*volatility - β*|max_drawdown|
#             - γ*downside_dev + δ*momentum
RISK_PROFILES: dict[str, dict[str, float]] = {
    "low": {
        "alpha": 2.0,   # volatility penalty
        "beta": 2.0,    # drawdown penalty
        "gamma": 1.5,   # downside deviation penalty
        "delta": 0.3,   # momentum bonus
    },
    "medium": {
        "alpha": 1.0,
        "beta": 1.0,
        "gamma": 0.75,
        "delta": 0.7,
    },
    "high": {
        "alpha": 0.5,
        "beta": 0.5,
        "gamma": 0.3,
        "delta": 1.5,
    },
}

# ── Portfolio & API ──────────────────────────────────────────────────────────
DEFAULT_TOP_N = 10
API_HOST = "0.0.0.0"
API_PORT = 8000
