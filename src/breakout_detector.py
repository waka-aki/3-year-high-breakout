"""Detect multi-year high breakouts after a quiet period."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Use all available price history (~3 years) for the high calculation
LOOKBACK_DAYS = 756  # 252 trading days × 3 years

# Require no breakout in the last QUIET_DAYS trading days.
# This filters out stocks that have been continuously making new highs.
QUIET_DAYS = 60


def detect_breakouts(
    prices: pd.DataFrame,
    tickers_df: pd.DataFrame,
    history: pd.DataFrame = None,
) -> pd.DataFrame:
    """Find stocks breaking above multi-year highs for the first time in months.

    Filters:
    1. Today's close > prior LOOKBACK_DAYS high (3-year high breakout).
    2. Quiet period: in the past QUIET_DAYS trading days, no day had its close
       exceed its own rolling long-term high. This ensures the stock has NOT
       been making new highs recently.

    The ``history`` parameter is accepted for interface compatibility but is
    no longer used for cooldown filtering (the quiet-period check replaces it).

    Returns DataFrame with columns: ticker, name, market, close, high_3y,
    breakout_pct, date
    """
    if prices.empty:
        return pd.DataFrame()

    latest_date = prices["date"].max()
    logger.info("Detecting breakouts as of %s", latest_date.date())

    results = []
    for ticker, group in prices.groupby("ticker"):
        group = group.sort_values("date")
        if len(group) < QUIET_DAYS:
            continue

        today_row = group[group["date"] == latest_date]
        if today_row.empty:
            continue

        today_close = today_row["close"].iloc[0]

        # All days before today
        prior = group[group["date"] < latest_date]
        if len(prior) < QUIET_DAYS:
            continue

        # 3-year high (use up to LOOKBACK_DAYS prior trading days)
        lookback = prior.tail(LOOKBACK_DAYS)
        high_3y = lookback["high"].max()
        if pd.isna(high_3y) or high_3y <= 0:
            continue

        # Condition 1: today's close exceeds the 3-year high
        if today_close <= high_3y:
            continue

        # Condition 2: quiet period check
        # In the most recent QUIET_DAYS trading days (before today), check that
        # no day's close exceeded its own rolling long-term high.
        quiet_window = prior.tail(QUIET_DAYS)
        was_quiet = True
        for idx in range(len(quiet_window)):
            row = quiet_window.iloc[idx]
            day_close = row["close"]
            # All days strictly before this day
            days_before = group[group["date"] < row["date"]]
            if len(days_before) < 20:
                continue
            rolling_high = days_before.tail(LOOKBACK_DAYS)["high"].max()
            if pd.isna(rolling_high):
                continue
            if day_close > rolling_high:
                was_quiet = False
                break

        if not was_quiet:
            continue

        breakout_pct = (today_close - high_3y) / high_3y * 100
        results.append({
            "ticker": ticker,
            "close": today_close,
            "high_3y": high_3y,
            "breakout_pct": round(breakout_pct, 2),
            "date": latest_date,
        })

    if not results:
        logger.info("No breakouts detected")
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # Merge with ticker info
    name_map = tickers_df.set_index("ticker")[["name", "market"]]
    df = df.merge(name_map, left_on="ticker", right_index=True, how="left")

    logger.info("Detected %d breakouts", len(df))
    return df
