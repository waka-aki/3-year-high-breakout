"""Track post-breakout performance at 5d/30d/60d/90d intervals."""

import logging
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY_CSV = os.path.join(DATA_DIR, "breakout_history.csv")
PERF_CSV = os.path.join(DATA_DIR, "performance_tracking.csv")

TRACKING_DAYS = [5, 10, 21, 42, 63, 84, 126]
CUTOFF_DAYS = 240


def update_history(breakouts: pd.DataFrame) -> pd.DataFrame:
    """Append new breakouts to history, avoiding duplicates."""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(HISTORY_CSV):
        history = pd.read_csv(HISTORY_CSV, parse_dates=["date"])
    else:
        history = pd.DataFrame()

    if breakouts.empty:
        return history

    cols = ["ticker", "name", "market", "close", "breakout_pct", "date"]
    if "sector" in breakouts.columns:
        cols.insert(3, "sector")
    for col in ["market_cap", "per", "pbr"]:
        if col in breakouts.columns:
            cols.append(col)
    new_entries = breakouts[cols].copy()
    new_entries = new_entries.rename(columns={"close": "breakout_price"})

    if not history.empty:
        # Deduplicate on ticker+date
        existing = set(zip(history["ticker"], history["date"].dt.date))
        mask = [
            (row["ticker"], row["date"].date()) not in existing
            for _, row in new_entries.iterrows()
        ]
        new_entries = new_entries[mask]

    if new_entries.empty:
        logger.info("No new breakouts to add to history")
        return history

    history = pd.concat([history, new_entries], ignore_index=True)
    history.to_csv(HISTORY_CSV, index=False)
    logger.info("Added %d new breakouts to history (total: %d)", len(new_entries), len(history))
    return history


def track_performance(
    history: pd.DataFrame,
    prices: pd.DataFrame,
    tickers_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calculate post-breakout returns at fixed trading-day offsets.

    Tracking offsets (trading days): 5, 10, 21, 42, 63, 84, 126
    These map to calendar labels: 5営業日, 2週間, 1か月, 2か月, 3か月, 4か月, 6か月.

    Looks up prices in the OHLCV cache rather than refetching from yfinance.
    If tickers_df is provided, sector is backfilled from it for rows whose
    history entry predates the sector column.
    """
    if history.empty:
        return pd.DataFrame()

    # Only track breakouts from last CUTOFF_DAYS calendar days
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=CUTOFF_DAYS))
    recent = history[history["date"] >= cutoff].copy()

    if recent.empty:
        return pd.DataFrame()

    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices_by_ticker = {
        ticker: df.sort_values("date").reset_index(drop=True)
        for ticker, df in prices.groupby("ticker")
    }

    sector_lookup = {}
    if tickers_df is not None and "sector" in tickers_df.columns:
        sector_lookup = dict(zip(tickers_df["ticker"], tickers_df["sector"]))

    results = []

    for _, row in recent.iterrows():
        breakout_date = pd.Timestamp(row["date"]).normalize()
        breakout_price = row["breakout_price"]
        ticker = row["ticker"]

        sector = row.get("sector", "")
        if (not sector or pd.isna(sector)) and ticker in sector_lookup:
            sector = sector_lookup[ticker]

        perf = {
            "ticker": ticker,
            "name": row.get("name", ""),
            "market": row.get("market", ""),
            "sector": sector if sector and not pd.isna(sector) else "",
            "breakout_date": breakout_date.date(),
            "breakout_price": breakout_price,
            "market_cap": row.get("market_cap", np.nan),
            "per": row.get("per", np.nan),
            "pbr": row.get("pbr", np.nan),
        }

        ticker_prices = prices_by_ticker.get(ticker)
        if ticker_prices is None or ticker_prices.empty:
            logger.debug("%s: no price cache rows, skipping perf calc", ticker)
            perf["current_price"] = np.nan
            perf["current_return"] = np.nan
            for d in TRACKING_DAYS:
                perf[f"return_{d}d"] = np.nan
            results.append(perf)
            continue

        # Locate the breakout row in the cache
        breakout_rows = ticker_prices.index[ticker_prices["date"] == breakout_date]
        if len(breakout_rows) == 0:
            logger.debug("%s: breakout date %s not in cache", ticker, breakout_date.date())
            perf["current_price"] = np.nan
            perf["current_return"] = np.nan
            for d in TRACKING_DAYS:
                perf[f"return_{d}d"] = np.nan
            results.append(perf)
            continue

        breakout_idx = int(breakout_rows[0])
        last_idx = len(ticker_prices) - 1

        # Current price = latest cached close for this ticker
        current_price = float(ticker_prices.iloc[last_idx]["close"])
        perf["current_price"] = current_price
        perf["current_return"] = round(
            (current_price - breakout_price) / breakout_price * 100, 2
        )

        # Returns at fixed trading-day offsets
        for d in TRACKING_DAYS:
            target_idx = breakout_idx + d
            if target_idx <= last_idx:
                target_close = float(ticker_prices.iloc[target_idx]["close"])
                perf[f"return_{d}d"] = round(
                    (target_close - breakout_price) / breakout_price * 100, 2
                )
            else:
                perf[f"return_{d}d"] = np.nan

        results.append(perf)

    perf_df = pd.DataFrame(results)
    perf_df.to_csv(PERF_CSV, index=False)
    logger.info("Tracked performance for %d breakouts", len(perf_df))
    return perf_df
