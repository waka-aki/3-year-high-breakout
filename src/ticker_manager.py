"""Download and manage JPX listed company tickers."""

import logging
import os

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TICKERS_CSV = os.path.join(DATA_DIR, "tickers.csv")
JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"


def download_ticker_list() -> pd.DataFrame:
    """Download JPX listed companies XLS and parse to DataFrame."""
    logger.info("Downloading JPX listed companies from %s", JPX_URL)
    resp = requests.get(JPX_URL, timeout=30)
    resp.raise_for_status()

    tmp_path = os.path.join(DATA_DIR, "data_j.xls")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.write(resp.content)

    df = pd.read_excel(tmp_path, engine="xlrd")
    logger.info("Downloaded %d rows from JPX", len(df))
    return df


def filter_ordinary_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to ordinary stocks only, excluding ETF/REIT/infrastructure funds."""
    # JPX XLS columns (Japanese): 日付, コード, 銘柄名, 市場・商品区分, 33業種コード, etc.
    # Market column typically contains: プライム, スタンダード, グロース, ETF, REIT, etc.
    market_col = [c for c in df.columns if "市場" in str(c)]
    if not market_col:
        logger.warning("Could not find market column, using all rows")
        return df

    market_col = market_col[0]
    valid_markets = ["プライム（内国株式）", "スタンダード（内国株式）", "グロース（内国株式）"]
    filtered = df[df[market_col].isin(valid_markets)].copy()
    logger.info("Filtered to %d ordinary stocks (from %d)", len(filtered), len(df))
    return filtered


def build_ticker_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Build clean ticker CSV with .T suffix for yfinance."""
    code_col = [c for c in df.columns if "コード" in str(c) and "業種" not in str(c) and "規模" not in str(c)][0]
    name_col = [c for c in df.columns if "銘柄名" in str(c)][0]
    market_col = [c for c in df.columns if "市場" in str(c)][0]
    sector_col_candidates = [c for c in df.columns if "33業種区分" in str(c)]
    sector_col = sector_col_candidates[0] if sector_col_candidates else None

    market_map = {
        "プライム（内国株式）": "Prime",
        "スタンダード（内国株式）": "Standard",
        "グロース（内国株式）": "Growth",
    }

    result = pd.DataFrame({
        "ticker": df[code_col].astype(str) + ".T",
        "name": df[name_col],
        "market": df[market_col].map(market_map),
        "sector": df[sector_col] if sector_col else "",
    })

    os.makedirs(DATA_DIR, exist_ok=True)
    result.to_csv(TICKERS_CSV, index=False)
    logger.info("Saved %d tickers to %s", len(result), TICKERS_CSV)
    return result


def update_tickers() -> pd.DataFrame:
    """Download, filter, and save ticker list."""
    df = download_ticker_list()
    df = filter_ordinary_stocks(df)
    return build_ticker_csv(df)


def load_tickers() -> pd.DataFrame:
    """Load tickers from cache, or download if not present.

    If the cache exists but is missing the ``sector`` column (i.e. it was
    written by an older version of this module), regenerate it.
    """
    if os.path.exists(TICKERS_CSV):
        df = pd.read_csv(TICKERS_CSV)
        if "sector" not in df.columns:
            logger.info("Cached tickers missing 'sector' column, regenerating...")
            return update_tickers()
        logger.info("Loaded %d tickers from cache", len(df))
        return df
    logger.info("No cached tickers found, downloading...")
    return update_tickers()
