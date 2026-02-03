"""Compute rolling financial metrics per ticker and persist to SQLite."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.config import (
    MIN_TRADING_DAYS,
    MOMENTUM_3M_WEIGHT,
    MOMENTUM_12M_WEIGHT,
    TRADING_DAYS_PER_YEAR,
    WINDOW_3M,
    WINDOW_12M,
)
from src.db import get_connection, init_db, load_dataframe

logger = logging.getLogger(__name__)


def _compute_ticker_metrics(
    prices: pd.DataFrame,
    window: int = WINDOW_12M,
) -> dict | None:
    """
    Compute rolling financial metrics for a single ticker.

    Parameters
    ----------
    prices : DataFrame with columns [date, adj_close], sorted by date ascending.
    window : rolling window in trading days.

    Returns a dict of metric values as of the latest date, or None if
    insufficient history.
    """
    if len(prices) < MIN_TRADING_DAYS:
        return None

    prices = prices.sort_values("date").reset_index(drop=True)
    close = prices["adj_close"].astype(float)

    # Daily returns with shift(1) to prevent look-ahead bias:
    # return on day T = (close_T - close_{T-1}) / close_{T-1}
    daily_returns = close.pct_change()

    # ── Mean daily return (rolling) ──────────────────────────────────────
    rolling_mean = daily_returns.rolling(window).mean()
    mean_daily = rolling_mean.iloc[-1]

    # ── Annualized return ────────────────────────────────────────────────
    annualized_return = (1 + mean_daily) ** TRADING_DAYS_PER_YEAR - 1

    # ── Volatility (annualized std dev) ──────────────────────────────────
    rolling_std = daily_returns.rolling(window).std()
    volatility = rolling_std.iloc[-1] * np.sqrt(TRADING_DAYS_PER_YEAR)

    # ── Downside deviation (annualized) ──────────────────────────────────
    negative_returns = daily_returns.copy()
    negative_returns[negative_returns > 0] = 0.0
    rolling_downside_std = negative_returns.rolling(window).std()
    downside_deviation = rolling_downside_std.iloc[-1] * np.sqrt(TRADING_DAYS_PER_YEAR)

    # ── Max drawdown (rolling window) ────────────────────────────────────
    # Use the trailing `window` days of close prices.
    trailing_close = close.iloc[-window:]
    cummax = trailing_close.cummax()
    drawdown = (trailing_close - cummax) / cummax
    max_drawdown = drawdown.min()  # most negative value

    # ── Momentum: blended 3-month and 12-month return ────────────────────
    def _period_return(n_days: int) -> float:
        if len(close) < n_days + 1:
            return 0.0
        return (close.iloc[-1] / close.iloc[-n_days - 1]) - 1.0

    ret_3m = _period_return(WINDOW_3M)
    ret_12m = _period_return(WINDOW_12M)
    momentum = MOMENTUM_3M_WEIGHT * ret_3m + MOMENTUM_12M_WEIGHT * ret_12m

    return {
        "mean_daily_return": mean_daily,
        "annualized_return": annualized_return,
        "volatility": volatility,
        "downside_deviation": downside_deviation,
        "max_drawdown": max_drawdown,
        "momentum": momentum,
        "trading_days": len(prices),
    }


def compute_all_metrics(window_months: int = 12) -> pd.DataFrame:
    """
    Compute metrics for every ticker in the prices table.

    Returns a DataFrame ready for insertion into the metrics table.
    """
    window = {12: WINDOW_12M, 6: 126, 3: 63}.get(window_months, WINDOW_12M)

    prices_df = load_dataframe(
        "SELECT ticker, date, adj_close FROM prices ORDER BY ticker, date"
    )

    if prices_df.empty:
        logger.warning("No price data found in database")
        return pd.DataFrame()

    as_of_date = prices_df["date"].max()
    rows: list[dict] = []
    skipped: list[str] = []

    for ticker, group in prices_df.groupby("ticker"):
        result = _compute_ticker_metrics(group, window=window)
        if result is None:
            skipped.append(ticker)
            continue

        rows.append({
            "ticker": ticker,
            "as_of_date": as_of_date,
            "window_months": window_months,
            **result,
        })

    if skipped:
        logger.info(
            "Skipped %d tickers with < %d trading days: %s",
            len(skipped),
            MIN_TRADING_DAYS,
            ", ".join(skipped[:10]) + ("..." if len(skipped) > 10 else ""),
        )

    logger.info("Computed metrics for %d tickers (as of %s)", len(rows), as_of_date)
    return pd.DataFrame(rows)


def refresh_metrics() -> None:
    """Main entry point: compute metrics and upsert into DB."""
    init_db()
    df = compute_all_metrics()

    if df.empty:
        logger.warning("No metrics to save")
        return

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO metrics
                (ticker, as_of_date, window_months, mean_daily_return,
                 annualized_return, volatility, downside_deviation,
                 max_drawdown, momentum, trading_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            df[
                [
                    "ticker", "as_of_date", "window_months",
                    "mean_daily_return", "annualized_return", "volatility",
                    "downside_deviation", "max_drawdown", "momentum",
                    "trading_days",
                ]
            ].values.tolist(),
        )

    logger.info("Saved metrics for %d tickers", len(df))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    refresh_metrics()
