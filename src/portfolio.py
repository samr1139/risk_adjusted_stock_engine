"""Top-N stock selection and portfolio-level queries."""

from __future__ import annotations

import pandas as pd

from src.config import DEFAULT_TOP_N
from src.db import load_dataframe


def get_top_stocks(
    risk_profile: str = "medium",
    top_n: int = DEFAULT_TOP_N,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    """
    Return the top-N ranked stocks for a given risk profile.

    Joins scores with metrics to return a rich result set.
    """
    date_clause = (
        "s.as_of_date = ?"
        if as_of_date
        else "s.as_of_date = (SELECT MAX(as_of_date) FROM scores)"
    )
    params: tuple = (risk_profile, top_n)
    if as_of_date:
        params = (as_of_date, risk_profile, top_n)

    query = f"""
        SELECT
            s.rank,
            s.ticker,
            s.normalized_score,
            s.raw_score,
            m.annualized_return,
            m.volatility,
            m.max_drawdown,
            m.downside_deviation,
            m.momentum,
            m.trading_days
        FROM scores s
        JOIN metrics m
            ON s.ticker = m.ticker
            AND s.as_of_date = m.as_of_date
        WHERE {date_clause}
            AND s.risk_profile = ?
        ORDER BY s.rank ASC
        LIMIT ?
    """

    return load_dataframe(query, params)


def get_stock_detail(ticker: str) -> dict:
    """
    Return detailed metrics and scores across all risk profiles for a
    single ticker.
    """
    metrics = load_dataframe(
        """
        SELECT * FROM metrics
        WHERE ticker = ?
            AND as_of_date = (SELECT MAX(as_of_date) FROM metrics)
        """,
        (ticker,),
    )

    scores = load_dataframe(
        """
        SELECT risk_profile, raw_score, normalized_score, rank
        FROM scores
        WHERE ticker = ?
            AND as_of_date = (SELECT MAX(as_of_date) FROM scores)
        ORDER BY risk_profile
        """,
        (ticker,),
    )

    return {
        "ticker": ticker,
        "metrics": metrics.to_dict(orient="records"),
        "scores": scores.to_dict(orient="records"),
    }
