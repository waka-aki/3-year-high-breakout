"""Render HTML dashboard from Jinja2 template."""

import logging
import os
from datetime import datetime

import pandas as pd
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def render_dashboard(
    breakouts: pd.DataFrame,
    performance: pd.DataFrame,
    total_tickers: int,
) -> str:
    """Render dashboard HTML and write to output directory."""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)
    template = env.get_template("dashboard.html.j2")

    # Prepare breakout data
    if not breakouts.empty:
        b = breakouts.copy()
        if "sector" in b.columns:
            b["sector"] = b["sector"].fillna("").astype(str)
        else:
            b["sector"] = ""
        breakout_records = b.to_dict("records")
    else:
        breakout_records = []

    # Prepare performance data (last 240 days)
    if not performance.empty:
        cutoff = pd.Timestamp(datetime.now()) - pd.Timedelta(days=240)
        perf_recent = performance[
            pd.to_datetime(performance["breakout_date"]) >= cutoff
        ].copy()
        if "sector" in perf_recent.columns:
            perf_recent["sector"] = perf_recent["sector"].fillna("").astype(str)
        else:
            perf_recent["sector"] = ""
        perf_records = perf_recent.to_dict("records")
    else:
        perf_records = []
        perf_recent = pd.DataFrame()

    # Market counts
    if not breakouts.empty:
        market_counts = breakouts["market"].value_counts()
    else:
        market_counts = pd.Series(dtype=int)

    context = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_tickers": total_tickers,
        "breakout_count": len(breakouts),
        "breakouts": breakout_records,
        "performance": perf_records,
        "prime_count": int(market_counts.get("Prime", 0)),
        "standard_count": int(market_counts.get("Standard", 0)),
        "growth_count": int(market_counts.get("Growth", 0)),
    }

    html = template.render(**context)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard written to %s", output_path)
    return output_path
