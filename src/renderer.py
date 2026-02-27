"""Render HTML dashboard from Jinja2 template."""

import logging
import os
from datetime import datetime

import numpy as np
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
    breakout_records = breakouts.to_dict("records") if not breakouts.empty else []

    # Prepare performance data (last 30 days only)
    if not performance.empty:
        cutoff = pd.Timestamp(datetime.now()) - pd.Timedelta(days=30)
        perf_recent = performance[
            pd.to_datetime(performance["breakout_date"]) >= cutoff
        ]
        perf_records = perf_recent.to_dict("records")
    else:
        perf_records = []
        perf_recent = pd.DataFrame()

    # Market counts
    if not breakouts.empty:
        market_counts = breakouts["market"].value_counts()
    else:
        market_counts = pd.Series(dtype=int)

    # Average returns
    avg_return_5d = None
    avg_return_30d = None
    if not performance.empty:
        r5 = performance["return_5d"].dropna()
        r30 = performance["return_30d"].dropna()
        if len(r5) > 0:
            avg_return_5d = float(r5.mean())
        if len(r30) > 0:
            avg_return_30d = float(r30.mean())

    context = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_tickers": total_tickers,
        "breakout_count": len(breakouts),
        "breakouts": breakout_records,
        "performance": perf_records,
        "prime_count": int(market_counts.get("Prime", 0)),
        "standard_count": int(market_counts.get("Standard", 0)),
        "growth_count": int(market_counts.get("Growth", 0)),
        "avg_return_5d": avg_return_5d,
        "avg_return_30d": avg_return_30d,
    }

    html = template.render(**context)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard written to %s", output_path)
    return output_path
