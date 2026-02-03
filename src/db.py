"""SQLite schema, connection helpers, and data access utilities."""

import sqlite3
from contextlib import contextmanager
from typing import Any

import pandas as pd

from src.config import DATA_DIR, DB_PATH

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    adj_close REAL NOT NULL,
    volume INTEGER,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

CREATE TABLE IF NOT EXISTS metrics (
    ticker TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    window_months INTEGER NOT NULL,
    mean_daily_return REAL,
    annualized_return REAL,
    volatility REAL,
    downside_deviation REAL,
    max_drawdown REAL,
    momentum REAL,
    trading_days INTEGER,
    UNIQUE(ticker, as_of_date, window_months)
);

CREATE INDEX IF NOT EXISTS idx_metrics_ticker ON metrics(ticker);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(as_of_date);

CREATE TABLE IF NOT EXISTS scores (
    ticker TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    risk_profile TEXT NOT NULL,
    raw_score REAL,
    normalized_score REAL,
    rank INTEGER,
    UNIQUE(ticker, as_of_date, risk_profile)
);

CREATE INDEX IF NOT EXISTS idx_scores_profile ON scores(risk_profile);
CREATE INDEX IF NOT EXISTS idx_scores_date ON scores(as_of_date);
"""


@contextmanager
def get_connection():
    """Yield a SQLite connection with WAL mode and foreign keys enabled."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables and indexes if they don't exist."""
    with get_connection() as conn:
        conn.executescript(_SCHEMA_SQL)


def load_dataframe(query: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    """Run a SELECT and return results as a DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def save_dataframe(df: pd.DataFrame, table: str) -> int:
    """Insert-or-replace a DataFrame into the given table. Returns row count."""
    with get_connection() as conn:
        return df.to_sql(table, conn, if_exists="append", index=False,
                         method="multi")


def execute_query(query: str, params: tuple[Any, ...] = ()) -> list[Any]:
    """Execute arbitrary SQL and return fetchall() results."""
    with get_connection() as conn:
        cur = conn.execute(query, params)
        return cur.fetchall()


def get_latest_date(table: str, date_col: str = "date") -> str | None:
    """Return the most recent date string in the given table, or None."""
    rows = execute_query(
        f"SELECT MAX({date_col}) FROM {table}"  # noqa: S608
    )
    return rows[0][0] if rows and rows[0][0] else None
