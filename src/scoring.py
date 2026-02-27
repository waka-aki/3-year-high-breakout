"""Score breakout stocks with volume and volatility metrics."""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def score_breakouts(breakouts: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Add scoring metrics to breakout stocks.

    Adds columns:
    - trading_value_change: today's trading value vs 20-day average (ratio)
    - vol_adj_volume_ratio: volume change rate / 20-day return stddev
    - consec_volume_days: count of last 5 days where volume > 20-day avg
    - volume_star: ★ if consec_volume_days >= 3
    """
    if breakouts.empty:
        return breakouts

    metrics = []
    for _, row in breakouts.iterrows():
        ticker = row["ticker"]
        ticker_prices = prices[prices["ticker"] == ticker].sort_values("date")

        if len(ticker_prices) < 25:
            metrics.append(_empty_metrics())
            continue

        latest = ticker_prices.iloc[-1]
        prior_20 = ticker_prices.iloc[-21:-1]  # 20 days before today
        last_5 = ticker_prices.iloc[-5:]

        # Trading value change rate
        today_value = latest["close"] * latest["volume"]
        avg_value_20 = (prior_20["close"] * prior_20["volume"]).mean()
        if avg_value_20 > 0:
            trading_value_change = round(today_value / avg_value_20, 2)
        else:
            trading_value_change = np.nan

        # Volatility-adjusted volume ratio
        vol_20_avg = prior_20["volume"].mean()
        if vol_20_avg > 0:
            volume_change = latest["volume"] / vol_20_avg
        else:
            volume_change = np.nan

        returns_20 = prior_20["close"].pct_change().dropna()
        ret_std = returns_20.std()
        if ret_std > 0 and not np.isnan(volume_change):
            vol_adj_ratio = round(volume_change / ret_std, 2)
        else:
            vol_adj_ratio = np.nan

        # Consecutive volume increase days (last 5 days vs 20-day avg)
        consec = 0
        for _, day in last_5.iterrows():
            if day["volume"] > vol_20_avg:
                consec += 1

        metrics.append({
            "trading_value_change": trading_value_change,
            "vol_adj_volume_ratio": vol_adj_ratio,
            "consec_volume_days": consec,
            "volume_star": "★" if consec >= 3 else "",
        })

    metrics_df = pd.DataFrame(metrics)
    result = pd.concat([breakouts.reset_index(drop=True), metrics_df], axis=1)
    logger.info("Scored %d breakout stocks", len(result))
    return result


def _empty_metrics() -> dict:
    return {
        "trading_value_change": np.nan,
        "vol_adj_volume_ratio": np.nan,
        "consec_volume_days": 0,
        "volume_star": "",
    }
