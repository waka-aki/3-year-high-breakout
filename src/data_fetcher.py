"""Fetch and cache OHLCV price data from yfinance with incremental updates."""

import logging
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PRICE_CACHE = os.path.join(DATA_DIR, "price_cache.csv")

BATCH_SIZE = 50
BATCH_SLEEP = 2  # seconds between batches
LOOKBACK_MONTHS = 37  # ~3 years of price history


def _cutoff_date() -> pd.Timestamp:
    """Return the earliest date to keep in cache (13 months ago)."""
    return pd.Timestamp(datetime.now() - timedelta(days=LOOKBACK_MONTHS * 30))


def load_cache() -> pd.DataFrame:
    """Load existing price cache if available."""
    if os.path.exists(PRICE_CACHE):
        df = pd.read_csv(PRICE_CACHE, parse_dates=["date"])
        logger.info("Loaded price cache: %d rows", len(df))
        return df
    return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "volume"])


def _fetch_batch(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Fetch OHLCV data for a batch of tickers."""
    try:
        data = yf.download(
            tickers,
            start=start,
            end=end,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as e:
        logger.error("Failed to download batch: %s", e)
        return pd.DataFrame()

    if data.empty:
        return pd.DataFrame()

    rows = []
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                ticker_data = data
            else:
                ticker_data = data[ticker]

            if ticker_data.empty:
                continue

            # yfinance 1.x returns MultiIndex columns with ("Price", ticker) pattern
            # or flat columns depending on version. Handle both.
            cols = ticker_data.columns
            if isinstance(cols, pd.MultiIndex):
                ticker_data = ticker_data.droplevel(level=1, axis=1)

            for date_val, row in ticker_data.iterrows():
                if pd.isna(row.get("Close")):
                    continue
                rows.append({
                    "ticker": ticker,
                    "date": pd.Timestamp(date_val),
                    "open": row.get("Open"),
                    "high": row.get("High"),
                    "low": row.get("Low"),
                    "close": row.get("Close"),
                    "volume": row.get("Volume"),
                })
        except Exception as e:
            logger.warning("Failed to parse data for %s: %s", ticker, e)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_prices(tickers: list[str]) -> pd.DataFrame:
    """Fetch/update price data for all tickers with incremental caching."""
    cache = load_cache()
    cutoff = _cutoff_date()
    today = pd.Timestamp(datetime.now().date())

    # Determine what needs fetching
    if cache.empty:
        tickers_to_fetch = {t: cutoff.strftime("%Y-%m-%d") for t in tickers}
    else:
        last_dates = cache.groupby("ticker")["date"].max()
        tickers_to_fetch = {}
        for t in tickers:
            if t in last_dates.index:
                last = last_dates[t]
                if last.date() < today.date() - timedelta(days=1):
                    tickers_to_fetch[t] = (last + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                tickers_to_fetch[t] = cutoff.strftime("%Y-%m-%d")

    if not tickers_to_fetch:
        logger.info("Price cache is up to date")
        return cache

    logger.info("Fetching prices for %d tickers", len(tickers_to_fetch))
    end_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # Group by start date for efficient batching
    by_start: dict[str, list[str]] = {}
    for t, start in tickers_to_fetch.items():
        by_start.setdefault(start, []).append(t)

    new_data = []
    for start, ticker_group in by_start.items():
        for i in range(0, len(ticker_group), BATCH_SIZE):
            batch = ticker_group[i:i + BATCH_SIZE]
            logger.info(
                "Batch %d-%d/%d (start=%s)",
                i + 1, min(i + BATCH_SIZE, len(ticker_group)),
                len(ticker_group), start,
            )
            df = _fetch_batch(batch, start, end_str)
            if not df.empty:
                new_data.append(df)
            if i + BATCH_SIZE < len(ticker_group):
                time.sleep(BATCH_SLEEP)

    if new_data:
        new_df = pd.concat(new_data, ignore_index=True)
        cache = pd.concat([cache, new_df], ignore_index=True)
        # Remove duplicates (same ticker+date)
        cache = cache.drop_duplicates(subset=["ticker", "date"], keep="last")

    # Trim old data
    cache = cache[cache["date"] >= cutoff].copy()

    # Save
    os.makedirs(DATA_DIR, exist_ok=True)
    cache.to_csv(PRICE_CACHE, index=False)
    logger.info("Saved price cache: %d rows", len(cache))
    return cache
