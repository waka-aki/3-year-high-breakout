"""Fetch financial data (revenue growth, operating margin) from yfinance."""

import logging

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_financials(breakouts: pd.DataFrame) -> pd.DataFrame:
    """Add revenue growth YoY and operating margin to breakout stocks.

    Returns N/A for missing data (common for Japanese stocks).
    """
    if breakouts.empty:
        return breakouts

    rev_growths = []
    op_margins = []

    for _, row in breakouts.iterrows():
        ticker = row["ticker"]
        try:
            info = yf.Ticker(ticker)
            financials = info.financials

            rev_growth = _calc_revenue_growth(financials)
            op_margin = _calc_operating_margin(financials)
        except Exception as e:
            logger.debug("Failed to fetch financials for %s: %s", ticker, e)
            rev_growth = np.nan
            op_margin = np.nan

        rev_growths.append(rev_growth)
        op_margins.append(op_margin)

    breakouts = breakouts.copy()
    breakouts["revenue_growth_yoy"] = rev_growths
    breakouts["operating_margin"] = op_margins
    logger.info("Fetched financials for %d stocks", len(breakouts))
    return breakouts


def _calc_revenue_growth(financials: pd.DataFrame) -> float:
    """Calculate YoY revenue growth from financials DataFrame."""
    if financials is None or financials.empty:
        return np.nan

    try:
        revenue_row = None
        for label in ["Total Revenue", "Operating Revenue"]:
            if label in financials.index:
                revenue_row = financials.loc[label]
                break

        if revenue_row is None or len(revenue_row) < 2:
            return np.nan

        recent = revenue_row.iloc[0]
        prior = revenue_row.iloc[1]
        if pd.isna(recent) or pd.isna(prior) or prior == 0:
            return np.nan

        return round((recent - prior) / abs(prior) * 100, 1)
    except Exception:
        return np.nan


def _calc_operating_margin(financials: pd.DataFrame) -> float:
    """Calculate operating margin from financials DataFrame."""
    if financials is None or financials.empty:
        return np.nan

    try:
        op_income = None
        for label in ["Operating Income", "EBIT"]:
            if label in financials.index:
                op_income = financials.loc[label].iloc[0]
                break

        revenue = None
        for label in ["Total Revenue", "Operating Revenue"]:
            if label in financials.index:
                revenue = financials.loc[label].iloc[0]
                break

        if pd.isna(op_income) or pd.isna(revenue) or revenue == 0:
            return np.nan

        return round(op_income / revenue * 100, 1)
    except Exception:
        return np.nan
