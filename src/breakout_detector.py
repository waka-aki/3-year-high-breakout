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
    1. Today's close > reference high (3-year high from before the quiet window).
       The reference high uses the ``high`` column (intraday highs) but is
       calculated from data older than QUIET_DAYS to exclude recent spikes.
    2. Quiet period: every close in the most recent QUIET_DAYS trading days
       must be at or below the reference high.  Using closes (not intraday
       highs) for this check provides a natural buffer — a stock can touch the
       level intraday as long as it consistently closes below it.

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

        # Reference high: 3-year high from data OLDER than the quiet window.
        # This prevents recent intraday spikes from setting an unreachable bar.
        older = prior.iloc[:-QUIET_DAYS]
        if len(older) < 1:
            continue
        ref_high = older.tail(LOOKBACK_DAYS)["high"].max()
        if pd.isna(ref_high) or ref_high <= 0:
            continue

        # Condition 1: today's close exceeds the reference high
        if today_close <= ref_high:
            continue

        # Condition 2: quiet period check
        # Every close in the quiet window must be at or below ref_high.
        quiet_window = prior.tail(QUIET_DAYS)
        if (quiet_window["close"] > ref_high).any():
            continue

        breakout_pct = (today_close - ref_high) / ref_high * 100
        results.append({
            "ticker": ticker,
            "close": today_close,
            "high_3y": ref_high,
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
