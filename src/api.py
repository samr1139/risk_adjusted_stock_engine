"""FastAPI application serving risk-adjusted stock rankings."""

from __future__ import annotations

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.config import API_HOST, API_PORT, DEFAULT_TOP_N, RISK_PROFILES
from src.db import execute_query, get_latest_date, init_db
from src.portfolio import get_stock_detail, get_top_stocks

STATIC_DIR = Path(__file__).resolve().parent / "static"


# ── Pydantic Response Models ─────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    ticker_count: int
    latest_price_date: str | None
    latest_metrics_date: str | None
    latest_scores_date: str | None


class RankedStock(BaseModel):
    rank: int
    ticker: str
    normalized_score: float
    raw_score: float
    annualized_return: float
    volatility: float
    max_drawdown: float
    downside_deviation: float
    momentum: float
    trading_days: int


class RankingsResponse(BaseModel):
    risk_profile: str
    as_of_date: str | None
    count: int
    stocks: list[RankedStock]


class ScoreEntry(BaseModel):
    risk_profile: str
    raw_score: float
    normalized_score: float
    rank: int


class MetricsEntry(BaseModel):
    as_of_date: str
    window_months: int
    mean_daily_return: float
    annualized_return: float
    volatility: float
    downside_deviation: float
    max_drawdown: float
    momentum: float
    trading_days: int


class StockDetailResponse(BaseModel):
    ticker: str
    metrics: list[MetricsEntry]
    scores: list[ScoreEntry]


class ProfileWeights(BaseModel):
    alpha: float
    beta: float
    gamma: float
    delta: float


class ProfileInfo(BaseModel):
    name: str
    description: str
    weights: ProfileWeights


class ProfilesResponse(BaseModel):
    profiles: list[ProfileInfo]


# ── App Setup ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Risk-Adjusted Stock Ranking Engine",
    description="Ranks stocks by risk-adjusted return across configurable profiles.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse, include_in_schema=False)
def dashboard():
    """Serve the single-page dashboard."""
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/health", response_model=HealthResponse)
def health():
    """Database status, ticker count, and latest dates."""
    rows = execute_query("SELECT COUNT(DISTINCT ticker) FROM prices")
    ticker_count = rows[0][0] if rows else 0

    return HealthResponse(
        status="ok",
        ticker_count=ticker_count,
        latest_price_date=get_latest_date("prices", "date"),
        latest_metrics_date=get_latest_date("metrics", "as_of_date"),
        latest_scores_date=get_latest_date("scores", "as_of_date"),
    )


@app.get("/rankings", response_model=RankingsResponse)
def rankings(
    risk_profile: str = Query("medium", description="Risk profile: low, medium, high"),
    top_n: int = Query(DEFAULT_TOP_N, ge=1, le=500, description="Number of stocks"),
):
    """Ranked stocks with scores and metrics for a risk profile."""
    if risk_profile not in RISK_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown risk_profile '{risk_profile}'. "
                   f"Choose from: {', '.join(RISK_PROFILES)}",
        )

    df = get_top_stocks(risk_profile=risk_profile, top_n=top_n)

    if df.empty:
        return RankingsResponse(
            risk_profile=risk_profile,
            as_of_date=None,
            count=0,
            stocks=[],
        )

    as_of = get_latest_date("scores", "as_of_date")
    stocks = [RankedStock(**row) for row in df.to_dict(orient="records")]

    return RankingsResponse(
        risk_profile=risk_profile,
        as_of_date=as_of,
        count=len(stocks),
        stocks=stocks,
    )


@app.get("/stock/{ticker}", response_model=StockDetailResponse)
def stock_detail(ticker: str):
    """Detailed metrics and scores across all profiles for a single stock."""
    ticker = ticker.upper()
    detail = get_stock_detail(ticker)

    if not detail["metrics"]:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")

    return StockDetailResponse(**detail)


@app.get("/profiles", response_model=ProfilesResponse)
def profiles():
    """Available risk profiles and their weight parameters."""
    descriptions = {
        "low": "Conservative - heavy risk penalties, favors stability.",
        "medium": "Balanced - equal weight on return and risk.",
        "high": "Aggressive - favors momentum, tolerates more risk.",
    }

    items = [
        ProfileInfo(
            name=name,
            description=descriptions.get(name, ""),
            weights=ProfileWeights(**weights),
        )
        for name, weights in RISK_PROFILES.items()
    ]

    return ProfilesResponse(profiles=items)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api:app", host=API_HOST, port=API_PORT, reload=True)
