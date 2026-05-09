"""One-off backfill: extract market_cap/PER/PBR from past dashboards in git history.

Iterates every commit that touched output/dashboard.html, parses the breakout
table, and builds a {ticker -> [(commit_datetime, values)]} index. For each row
in data/breakout_history.csv, picks the earliest dashboard appearance whose
commit datetime is on or after the breakout date (i.e., the first scan that
detected the breakout) — this is robust to commits whose message isn't
"Daily scan: <date>" (e.g., bug-fix commits) and to breakouts retroactively
added by a later scan.

Pre-2026-03-01 breakouts predate the PER/PBR columns in dashboard.html, so
those rows remain N/A. Same for breakouts that were never displayed in any
committed dashboard's breakout-table (e.g., retroactively detected ones).
"""

import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_CSV = REPO_ROOT / "data" / "breakout_history.csv"
DASHBOARD_PATH = "output/dashboard.html"

TARGET_COLUMNS = {
    "market_cap": "時価総額（億）",
    "per": "PER",
    "pbr": "PBR",
}


def get_all_dashboard_commits() -> list[tuple[str, datetime]]:
    """All commits that touched dashboard.html, oldest first."""
    result = subprocess.run(
        ["git", "log", "--reverse", "--format=%H|%cI", "--", DASHBOARD_PATH],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        h, ts = line.split("|", 1)
        commits.append((h, datetime.fromisoformat(ts)))
    return commits


def get_dashboard_html(commit_hash: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit_hash}:{DASHBOARD_PATH}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def parse_breakout_table(html: str) -> dict[str, dict[str, float]]:
    """Map ticker -> {market_cap, per, pbr} parsed from breakout-table."""
    table_match = re.search(
        r'<table id="breakout-table">(.*?)</table>', html, re.DOTALL
    )
    if not table_match:
        return {}
    table_html = table_match.group(1)

    header_match = re.search(r"<thead>(.*?)</thead>", table_html, re.DOTALL)
    if not header_match:
        return {}
    headers = re.findall(r"<th[^>]*>(.*?)</th>", header_match.group(1), re.DOTALL)
    headers = [_strip_tags(h) for h in headers]

    col_idx: dict[str, int] = {}
    for key, header_name in TARGET_COLUMNS.items():
        if header_name in headers:
            col_idx[key] = headers.index(header_name)
    if len(col_idx) < len(TARGET_COLUMNS):
        return {}

    tbody_match = re.search(r"<tbody>(.*?)</tbody>", table_html, re.DOTALL)
    if not tbody_match:
        return {}
    rows = re.findall(r"<tr>(.*?)</tr>", tbody_match.group(1), re.DOTALL)

    result: dict[str, dict[str, float]] = {}
    for row_html in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) <= max(col_idx.values()):
            continue
        ticker = _strip_tags(cells[0])
        if not ticker.endswith(".T"):
            continue
        values: dict[str, float] = {}
        for key, idx in col_idx.items():
            cell = _strip_tags(cells[idx]).rstrip("%xX").replace(",", "").strip()
            if cell in ("N/A", "", "-"):
                values[key] = np.nan
            else:
                try:
                    values[key] = float(cell)
                except ValueError:
                    values[key] = np.nan
        result[ticker] = values
    return result


def build_ticker_index() -> dict[str, list[tuple[datetime, dict[str, float]]]]:
    """Walk all dashboard.html commits and build {ticker: [(dt, values), ...]}."""
    index: dict[str, list[tuple[datetime, dict[str, float]]]] = {}
    commits = get_all_dashboard_commits()
    logger.info("Scanning %d dashboard.html commits", len(commits))
    parseable = 0
    for commit, dt in commits:
        html = get_dashboard_html(commit)
        if not html:
            continue
        parsed = parse_breakout_table(html)
        if parsed:
            parseable += 1
        for ticker, values in parsed.items():
            index.setdefault(ticker, []).append((dt, values))
    logger.info(
        "Indexed %d unique tickers across %d parseable dashboards",
        len(index), parseable,
    )
    return index


def backfill_history() -> None:
    history = pd.read_csv(HISTORY_CSV, parse_dates=["date"])
    for col in ("market_cap", "per", "pbr"):
        if col not in history.columns:
            history[col] = np.nan

    index = build_ticker_index()
    filled = {"market_cap": 0, "per": 0, "pbr": 0}
    skipped: list[tuple[str, str]] = []

    for idx, row in history.iterrows():
        ticker = row["ticker"]
        breakout_date = row["date"].date()

        appearances = index.get(ticker, [])
        # Pick the earliest dashboard appearance whose commit datetime is on or
        # after the breakout date. That's the scan that first surfaced this
        # breakout in "本日のブレイクアウト".
        candidates = [
            (dt, vals) for dt, vals in appearances
            if dt.date() >= breakout_date
        ]
        if not candidates:
            skipped.append((ticker, breakout_date.isoformat()))
            continue
        _, values = min(candidates, key=lambda t: t[0])

        for col, val in values.items():
            if pd.isna(history.at[idx, col]):
                history.at[idx, col] = val
                if not pd.isna(val):
                    filled[col] += 1

    history.to_csv(HISTORY_CSV, index=False)
    logger.info(
        "Filled: market_cap=%d, per=%d, pbr=%d. Unmatched: %d rows",
        filled["market_cap"], filled["per"], filled["pbr"], len(skipped),
    )
    for ticker, date_str in skipped:
        logger.info("  unmatched: %s on %s", ticker, date_str)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )
    backfill_history()
