"""Detect 52-week high breakouts."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

COOLDOWN_DAYS = 30


def detect_breakouts(
    prices: pd.DataFrame,
    tickers_df: pd.DataFrame,
    history: pd.DataFrame = None,
) -> pd.DataFrame:
    """Find stocks that broke out above the 52-week high for the first time.

    Filters:
    1. Today's close > prior 252-day high AND yesterday's close <= yesterday's
       52-week high (i.e. the breakout just happened).
    2. Cooldown: skip tickers that already had a breakout within the last
       COOLDOWN_DAYS days (based on *history*).

    Returns DataFrame with columns: ticker, name, market, close, high_52w,
    breakout_pct, date
    """
    if prices.empty:
        return pd.DataFrame()

    latest_date = prices["date"].max()
    logger.info("Detecting breakouts as of %s", latest_date.date())

    # Build cooldown set from history
    cooldown_tickers: set = set()
    if history is not None and not history.empty:
        cutoff = latest_date - pd.Timedelta(days=COOLDOWN_DAYS)
        hist = history.copy()
        if not pd.api.types.is_datetime64_any_dtype(hist["date"]):
            hist["date"] = pd.to_datetime(hist["date"])
        recent = hist[hist["date"] >= cutoff]
        cooldown_tickers = set(recent["ticker"].unique())
        if cooldown_tickers:
            logger.info(
                "Cooldown: %d tickers had breakouts in last %d days, skipping",
                len(cooldown_tickers),
                COOLDOWN_DAYS,
            )

    results = []
    for ticker, group in prices.groupby("ticker"):
        if ticker in cooldown_tickers:
            continue

        group = group.sort_values("date")
        if len(group) < 20:  # need minimum history
            continue

        today_row = group[group["date"] == latest_date]
        if today_row.empty:
            continue

        today_close = today_row["close"].iloc[0]
        # Prior 252 trading days (exclude today)
        prior = group[group["date"] < latest_date].tail(252)
        if prior.empty:
            continue

        high_52w = prior["high"].max()
        if pd.isna(high_52w) or high_52w <= 0:
            continue

        if today_close > high_52w:
            # Filter 1: check that yesterday was NOT a breakout
            prior_days = group[group["date"] < latest_date].sort_values("date")
            if len(prior_days) < 2:
                # Not enough data to determine yesterday; treat as new breakout
                pass
            else:
                yesterday_row = prior_days.iloc[-1]
                yesterday_close = yesterday_row["close"]
                # 52-week high as of yesterday (exclude yesterday itself)
                prior_before_yesterday = prior_days.iloc[:-1].tail(252)
                if not prior_before_yesterday.empty:
                    high_52w_yesterday = prior_before_yesterday["high"].max()
                    if yesterday_close > high_52w_yesterday:
                        # Yesterday was also a breakout → not a new breakout
                        continue

            breakout_pct = (today_close - high_52w) / high_52w * 100
            results.append({
                "ticker": ticker,
                "close": today_close,
                "high_52w": high_52w,
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
