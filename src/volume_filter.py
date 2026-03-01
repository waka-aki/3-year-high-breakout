"""Filter breakout stocks by volume and liquidity criteria."""

import logging

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Filter thresholds
MIN_TRADING_VALUE = 1e8       # 1億円
MIN_MARKET_CAP = 1e10         # 100億円


def filter_by_volume(breakouts: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Filter breakouts by volume/liquidity criteria.

    Conditions (all must be met):
    A. Trading value >= 2億円
    B. Market cap >= 100億円
    C. 20-day avg volume > prior 20-day (days 21-40) avg volume

    Adds columns: volume_ratio, trading_value, market_cap
    """
    if breakouts.empty:
        return breakouts

    passed = []
    for _, row in breakouts.iterrows():
        ticker = row["ticker"]
        ticker_prices = prices[prices["ticker"] == ticker].sort_values("date")

        if len(ticker_prices) < 40:
            logger.debug("%s: insufficient history (%d days), skipped", ticker, len(ticker_prices))
            continue

        latest = ticker_prices.iloc[-1]
        recent_20 = ticker_prices.iloc[-20:]       # last 20 days
        prior_20 = ticker_prices.iloc[-40:-20]      # days 21-40

        # Condition A: trading value >= 2億円
        today_trading_value = latest["close"] * latest["volume"]
        if today_trading_value < MIN_TRADING_VALUE:
            logger.debug("%s: trading value %.0f < 1億, skipped", ticker, today_trading_value)
            continue

        # Condition B: market cap >= 100億円
        market_cap = _get_market_cap(ticker)
        if market_cap is None or market_cap < MIN_MARKET_CAP:
            logger.debug("%s: market cap insufficient, skipped", ticker)
            continue

        # Condition C: 20-day avg volume > prior 20-day avg volume
        avg_vol_recent = recent_20["volume"].mean()
        avg_vol_prior = prior_20["volume"].mean()
        if avg_vol_prior <= 0 or avg_vol_recent <= avg_vol_prior:
            logger.debug("%s: volume trend declining, skipped", ticker)
            continue

        # Calculate volume trend ratio (recent 20d avg / prior 20d avg)
        volume_ratio = round(avg_vol_recent / avg_vol_prior, 2) if avg_vol_prior > 0 else np.nan

        entry = row.to_dict()
        entry["volume_ratio"] = volume_ratio
        entry["trading_value"] = round(today_trading_value / 1e8, 1)   # 億円
        entry["market_cap"] = round(market_cap / 1e8, 0)               # 億円
        passed.append(entry)

    if not passed:
        logger.info("No breakouts passed volume filter")
        return pd.DataFrame()

    result = pd.DataFrame(passed)
    logger.info("Volume filter: %d / %d breakouts passed", len(result), len(breakouts))
    return result


def _get_market_cap(ticker: str) -> float | None:
    """Fetch market cap from yfinance."""
    try:
        info = yf.Ticker(ticker).info
        mc = info.get("marketCap")
        if mc and mc > 0:
            return float(mc)
    except Exception as e:
        logger.debug("Failed to get market cap for %s: %s", ticker, e)
    return None
