# Risk-Adjusted Stock Ranking Engine

A quantitative scoring system that ranks equities by risk-adjusted return across configurable risk profiles. Pulls daily prices from Yahoo Finance, computes rolling financial metrics, applies composite scoring with tunable penalty weights, and serves results through a FastAPI REST API with a live dashboard.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

<!-- Replace with an actual screenshot of the running dashboard -->
<!-- ![Dashboard Screenshot](docs/screenshot.png) -->

## What It Does

- **Scores stocks** using a composite formula that penalizes volatility, drawdowns, and downside deviation while rewarding return and momentum
- **Three risk profiles** (Conservative, Balanced, Aggressive) with different penalty weights — switch profiles and the entire ranking reorders
- **Full data pipeline** from raw Yahoo Finance prices to scored, ranked output in an SQLite database
- **Live web dashboard** with sortable tables, score visualizations, and per-ticker drill-down charts

## Architecture

```
config.py          Centralized parameters (tickers, windows, weights)
    │
pull_prices.py     Download 2 years of daily prices via yfinance
    │                 └─→ prices table
compute_metrics.py Compute rolling return, volatility, drawdown, momentum
    │                 └─→ metrics table
score_stocks.py    Apply risk-profile formula, percentile-normalize, rank
    │                 └─→ scores table
portfolio.py       Query layer (top-N, single-stock detail)
    │
api.py             FastAPI REST API + web dashboard
```

Each step is independently runnable: `python -m src.<module>`

## Scoring Formula

```
raw_score = annualized_return − α·volatility − β·|max_drawdown| − γ·downside_dev + δ·momentum
```

Raw scores are converted to **percentile ranks** (0–1). A normalized score of 0.85 means "beats 85% of the universe."

| Profile | α (volatility) | β (drawdown) | γ (downside) | δ (momentum) | Style |
|---------|---------------|--------------|--------------|--------------|-------|
| **Low** | 2.0 | 2.0 | 1.5 | 0.3 | Conservative — heavy risk penalties |
| **Medium** | 1.0 | 1.0 | 0.75 | 0.7 | Balanced — equal weight to return and risk |
| **High** | 0.5 | 0.5 | 0.3 | 1.5 | Aggressive — favors momentum |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full pipeline
make pipeline

# Or run steps individually
python -m src.pull_prices        # ~5-10 min for full S&P 500
python -m src.compute_metrics
python -m src.score_stocks

# Start the server
python -m src.api
```

Open **http://localhost:8000** for the dashboard, or **/docs** for the interactive API reference.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web dashboard |
| `GET` | `/health` | DB status — ticker count, latest data dates |
| `GET` | `/rankings?risk_profile=medium&top_n=10` | Top-N ranked stocks with scores and metrics |
| `GET` | `/stock/{ticker}` | Cross-profile metrics and scores for one ticker |
| `GET` | `/profiles` | Risk profile definitions and weight parameters |

Example — top 3 stocks, medium risk:
```json
{
  "risk_profile": "medium",
  "as_of_date": "2026-01-29",
  "count": 3,
  "stocks": [
    {
      "rank": 1,
      "ticker": "INTC",
      "normalized_score": 1.0,
      "annualized_return": 2.097,
      "volatility": 0.692,
      "max_drawdown": -0.338,
      "momentum": 0.686,
      "trading_days": 501
    }
  ]
}
```

## Dashboard

Dark-themed fintech UI built with vanilla JS, CSS, and Chart.js. No build tools.

- **Stats cards** — aggregate return, volatility, drawdown, ticker count
- **Profile selector** — switch risk profiles, table re-ranks live
- **Sortable rankings table** — gradient score bars, gold/silver/bronze rank badges, color-coded metrics
- **Slide-in detail panel** — per-ticker metrics + horizontal bar chart comparing scores across all profiles
- **Skeleton loading** — shimmer placeholders during API fetches

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **No look-ahead bias** | Rolling metrics use `pct_change()` — day T only uses data through T−1 |
| **Percentile normalization** | Robust to outliers; raw scores vary wildly across profiles |
| **Blended momentum** | 60% three-month + 40% twelve-month balances recency with persistence |
| **Minimum history filter** | Tickers with <200 trading days excluded for statistical reliability |
| **Idempotent upserts** | `INSERT OR REPLACE` makes every pipeline step safely re-runnable |
| **WAL mode SQLite** | Allows concurrent reads during pipeline writes |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Data ingestion | yfinance, pandas, numpy |
| Storage | SQLite (WAL mode, indexed) |
| API | FastAPI, Pydantic, uvicorn |
| Frontend | Vanilla JS, CSS custom properties, Chart.js 4 |
| Fonts | Inter (UI), JetBrains Mono (financial data) |

## Limitations

- **Survivorship bias** — only current index constituents are scored; delisted stocks are absent
- **Linear scoring** — the formula doesn't capture tail risk or non-linear factor interactions
- **No portfolio optimization** — ranks individual stocks but doesn't model correlation, rebalancing, or transaction costs
- **Data freshness** — depends on when the pipeline was last run

## License

[MIT](LICENSE)
