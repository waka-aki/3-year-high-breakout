"""Main orchestrator for 52-week high breakout screener."""

import argparse
import logging
import os
import sys
from datetime import datetime

# Add parent dir to path so we can run as `python src/main.py`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from ticker_manager import load_tickers, update_tickers
from data_fetcher import fetch_prices
from breakout_detector import detect_breakouts
from volume_filter import filter_by_volume
from performance_tracker import update_history, track_performance
from renderer import render_dashboard

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"run_{datetime.now():%Y%m%d_%H%M%S}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="3-Year High Breakout Screener")
    parser.add_argument(
        "--update-tickers",
        action="store_true",
        help="Force download of JPX ticker list",
    )
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== 3-Year High Breakout Screener ===")

    # 1. Ticker list
    if args.update_tickers:
        logger.info("Step 1: Updating ticker list from JPX...")
        tickers_df = update_tickers()
    else:
        logger.info("Step 1: Loading cached ticker list...")
        tickers_df = load_tickers()

    ticker_list = tickers_df["ticker"].tolist()
    logger.info("Working with %d tickers", len(ticker_list))

    # 2. Fetch/update price data
    logger.info("Step 2: Fetching price data...")
    prices = fetch_prices(ticker_list)

    # 3. Detect breakouts
    logger.info("Step 3: Detecting breakouts...")
    history_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "breakout_history.csv"
    )
    prior_history = pd.DataFrame()
    if os.path.exists(history_path):
        prior_history = pd.read_csv(history_path)
        logger.info("Loaded %d prior breakout records", len(prior_history))
    breakouts = detect_breakouts(prices, tickers_df, history=prior_history)

    # 4. Volume/liquidity filter
    if not breakouts.empty:
        logger.info("Step 4: Applying volume/liquidity filter...")
        breakouts = filter_by_volume(breakouts, prices)
    else:
        logger.info("Step 4: No breakouts to filter")

    # 5. Update performance tracking
    logger.info("Step 5: Updating performance tracking...")
    history = update_history(breakouts)
    performance = track_performance(history, prices, tickers_df)

    # 6. Render dashboard
    logger.info("Step 6: Rendering dashboard...")
    output_path = render_dashboard(breakouts, performance, len(ticker_list))

    logger.info("=== Done! Dashboard: %s ===", output_path)


if __name__ == "__main__":
    main()
