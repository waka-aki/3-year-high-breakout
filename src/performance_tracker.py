"""Track post-breakout performance at 5d/30d/60d/90d intervals."""

import logging
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY_CSV = os.path.join(DATA_DIR, "breakout_history.csv")
PERF_CSV = os.path.join(DATA_DIR, "performance_tracking.csv")

TRACKING_DAYS = [5, 30, 60, 90]


def update_history(breakouts: pd.DataFrame) -> pd.DataFrame:
    """Append new breakouts to history, avoiding duplicates."""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(HISTORY_CSV):
        history = pd.read_csv(HISTORY_CSV, parse_dates=["date"])
    else:
        history = pd.DataFrame()

    if breakouts.empty:
        return history

    new_entries = breakouts[["ticker", "name", "market", "close", "breakout_pct", "date"]].copy()
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


def track_performance(history: pd.DataFrame) -> pd.DataFrame:
    """Calculate post-breakout returns for tracked stocks."""
    if history.empty:
        return pd.DataFrame()

    # Only track breakouts from last 120 days
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=120))
    recent = history[history["date"] >= cutoff].copy()

    if recent.empty:
        return pd.DataFrame()

    today = datetime.now().date()
    results = []

    for _, row in recent.iterrows():
        breakout_date = pd.Timestamp(row["date"]).date()
        breakout_price = row["breakout_price"]
        ticker = row["ticker"]

        perf = {
            "ticker": ticker,
            "name": row.get("name", ""),
            "market": row.get("market", ""),
            "breakout_date": breakout_date,
            "breakout_price": breakout_price,
        }

        # Fetch current price for return calculation
        days_since = (today - breakout_date).days
        try:
            current_data = yf.download(
                ticker,
                start=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
                end=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                progress=False,
            )
            if not current_data.empty:
                current_price = current_data["Close"].iloc[-1]
                if isinstance(current_price, pd.Series):
                    current_price = current_price.iloc[0]
                perf["current_price"] = float(current_price)
                perf["current_return"] = round(
                    (float(current_price) - breakout_price) / breakout_price * 100, 2
                )
            else:
                perf["current_price"] = np.nan
                perf["current_return"] = np.nan
        except Exception as e:
            logger.debug("Failed to fetch current price for %s: %s", ticker, e)
            perf["current_price"] = np.nan
            perf["current_return"] = np.nan

        # Mark which tracking periods have elapsed
        for d in TRACKING_DAYS:
            col = f"return_{d}d"
            if days_since >= d:
                perf[col] = perf.get("current_return", np.nan)
            else:
                perf[col] = np.nan

        results.append(perf)

    perf_df = pd.DataFrame(results)
    perf_df.to_csv(PERF_CSV, index=False)
    logger.info("Tracked performance for %d breakouts", len(perf_df))
    return perf_df
