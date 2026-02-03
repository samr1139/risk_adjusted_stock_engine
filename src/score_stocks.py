"""Compute composite risk-adjusted scores per risk profile."""

from __future__ import annotations

import logging

import pandas as pd

from src.config import RISK_PROFILES
from src.db import get_connection, init_db, load_dataframe

logger = logging.getLogger(__name__)


def _score_profile(metrics: pd.DataFrame, profile: str) -> pd.DataFrame:
    """
    Apply scoring formula for a single risk profile.

    raw_score = annualized_return
                - α * volatility
                - β * |max_drawdown|
                - γ * downside_deviation
                + δ * momentum
    """
    weights = RISK_PROFILES[profile]
    alpha = weights["alpha"]
    beta = weights["beta"]
    gamma = weights["gamma"]
    delta = weights["delta"]

    df = metrics.copy()
    df["raw_score"] = (
        df["annualized_return"]
        - alpha * df["volatility"]
        - beta * df["max_drawdown"].abs()
        - gamma * df["downside_deviation"]
        + delta * df["momentum"]
    )

    # Percentile rank: 0 = worst, 1 = best
    df["normalized_score"] = df["raw_score"].rank(pct=True)
    df["rank"] = df["raw_score"].rank(ascending=False, method="min").astype(int)
    df["risk_profile"] = profile

    return df[["ticker", "as_of_date", "risk_profile", "raw_score",
               "normalized_score", "rank"]]


def score_all_profiles() -> pd.DataFrame:
    """Score all tickers across every configured risk profile."""
    metrics = load_dataframe(
        """
        SELECT ticker, as_of_date, annualized_return, volatility,
               downside_deviation, max_drawdown, momentum
        FROM metrics
        WHERE as_of_date = (SELECT MAX(as_of_date) FROM metrics)
        """
    )

    if metrics.empty:
        logger.warning("No metrics found in database")
        return pd.DataFrame()

    frames = []
    for profile in RISK_PROFILES:
        scored = _score_profile(metrics, profile)
        frames.append(scored)
        logger.info(
            "Profile '%s': scored %d tickers (top: %s)",
            profile,
            len(scored),
            scored.sort_values("rank").iloc[0]["ticker"] if len(scored) > 0 else "N/A",
        )

    return pd.concat(frames, ignore_index=True)


def refresh_scores() -> None:
    """Main entry point: compute scores and upsert into DB."""
    init_db()
    df = score_all_profiles()

    if df.empty:
        logger.warning("No scores to save")
        return

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO scores
                (ticker, as_of_date, risk_profile, raw_score,
                 normalized_score, rank)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            df[
                ["ticker", "as_of_date", "risk_profile", "raw_score",
                 "normalized_score", "rank"]
            ].values.tolist(),
        )

    logger.info("Saved scores for %d ticker-profile pairs", len(df))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    refresh_scores()
