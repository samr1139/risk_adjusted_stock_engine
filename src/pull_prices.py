"""Fetch historical prices via yfinance and persist to SQLite."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from src.config import (
    CUSTOM_TICKERS,
    DEFAULT_TICKERS,
    HISTORY_YEARS,
    PRICE_INTERVAL,
)
from src.db import init_db, get_connection

logger = logging.getLogger(__name__)


def fetch_sp500_tickers() -> list[str]:
    """Scrape current S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        logger.info("Fetched %d S&P 500 tickers from Wikipedia", len(tickers))
        return sorted(set(tickers))
    except Exception as exc:
        logger.warning("Failed to fetch S&P 500 list: %s", exc)
        return []


def get_ticker_universe() -> list[str]:
    """Resolve ticker universe: custom > S&P 500 scrape > default fallback."""
    if CUSTOM_TICKERS:
        logger.info("Using %d custom tickers", len(CUSTOM_TICKERS))
        return CUSTOM_TICKERS

    sp500 = fetch_sp500_tickers()
    if sp500:
        return sp500

    logger.info("Falling back to %d default tickers", len(DEFAULT_TICKERS))
    return DEFAULT_TICKERS


def pull_prices(tickers: list[str]) -> pd.DataFrame:
    """
    Bulk-download adjusted daily prices via yfinance.

    Returns a long-format DataFrame with columns:
        ticker, date, adj_close, volume
    """
    end = datetime.today()
    start = end - timedelta(days=HISTORY_YEARS * 365)

    logger.info(
        "Downloading prices for %d tickers (%s to %s)",
        len(tickers),
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
    )

    raw = yf.download(
        tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval=PRICE_INTERVAL,
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    if raw.empty:
        logger.error("yfinance returned no data")
        return pd.DataFrame(columns=["ticker", "date", "adj_close", "volume"])

    # yf.download returns MultiIndex columns (metric, ticker) for multiple
    # tickers, or simple columns for a single ticker.
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
        volume = raw["Volume"].copy()
    else:
        # Single ticker — wrap into DataFrame with that ticker as column
        t = tickers[0]
        close = raw[["Close"]].rename(columns={"Close": t})
        volume = raw[["Volume"]].rename(columns={"Volume": t})

    # Melt to long format
    close_long = close.reset_index().melt(
        id_vars="Date", var_name="ticker", value_name="adj_close"
    )
    volume_long = volume.reset_index().melt(
        id_vars="Date", var_name="ticker", value_name="volume"
    )

    df = close_long.merge(volume_long, on=["Date", "ticker"])
    df = df.rename(columns={"Date": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["adj_close"])
    df["volume"] = df["volume"].astype("Int64")

    logger.info(
        "Downloaded %d price rows for %d tickers",
        len(df),
        df["ticker"].nunique(),
    )
    return df[["ticker", "date", "adj_close", "volume"]]


def refresh_prices() -> None:
    """Main entry point: resolve tickers, download prices, upsert into DB."""
    init_db()
    tickers = get_ticker_universe()
    df = pull_prices(tickers)

    if df.empty:
        logger.warning("No price data to save")
        return

    with get_connection() as conn:
        # Use INSERT OR REPLACE for upsert behavior
        conn.executemany(
            """
            INSERT OR REPLACE INTO prices (ticker, date, adj_close, volume)
            VALUES (?, ?, ?, ?)
            """,
            df[["ticker", "date", "adj_close", "volume"]].values.tolist(),
        )

    logger.info("Saved %d price rows to database", len(df))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    refresh_prices()
