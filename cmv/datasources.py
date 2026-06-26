"""
Data access helpers.

FRED is reachable through pandas-datareader with no API key, which covers the
large majority of the currentmarketvaluation.com series. Yahoo Finance (yfinance)
supplies long-history index prices for the mean-reversion model.

All fetches are cached in-process for the life of a run so that multiple
indicators sharing a series (e.g. the 10y yield) only hit the network once.
"""
from __future__ import annotations

import datetime as dt
import io
from functools import lru_cache

import pandas as pd
import requests
from pandas_datareader import data as pdr

_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# FRED's earliest data varies per series; a very early start is harmless because
# the API simply returns whatever history exists.
DEFAULT_START = dt.date(1900, 1, 1)


@lru_cache(maxsize=128)
def fred_series(series_id: str, start: dt.date = DEFAULT_START) -> pd.Series:
    """Download a single FRED series as a clean, NaN-dropped Series.

    No API key required. Result is memoised for the process lifetime.
    """
    df = pdr.DataReader(series_id, "fred", start, dt.date.today())
    series = df[series_id].dropna()
    series.name = series_id
    series.index = pd.to_datetime(series.index)
    return series


@lru_cache(maxsize=32)
def yahoo_close(ticker: str, start: str = "1927-01-01") -> pd.Series:
    """Download a Yahoo Finance close-price series (unadjusted) as a Series.

    Handles the MultiIndex columns that recent yfinance returns for a single
    ticker download.
    """
    import yfinance as yf

    df = yf.download(
        ticker,
        start=start,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"No data returned from Yahoo for {ticker!r}")

    close = df["Close"]
    if isinstance(close, pd.DataFrame):  # single-ticker MultiIndex case
        close = close.iloc[:, 0]
    close = close.dropna()
    close.name = ticker
    close.index = pd.to_datetime(close.index)
    return close


@lru_cache(maxsize=8)
def multpl_series(slug: str) -> pd.Series:
    """Scrape a monthly data table from multpl.com into a Series.

    multpl publishes Robert Shiller's data (e.g. the Shiller PE / CAPE) as HTML
    tables with a Date and Value column, most-recent first; the top row is the
    current live estimate. `slug` is the path segment, e.g. "shiller-pe".
    FRED no longer hosts a clean CAPE series, so this is the cleanest free source.
    """
    url = f"https://www.multpl.com/{slug}/table/by-month"
    resp = requests.get(url, headers={"User-Agent": _BROWSER_UA}, timeout=30)
    resp.raise_for_status()

    # pandas 3.0 needs HTML wrapped in StringIO; a bare string is read as a path.
    table = pd.read_html(io.StringIO(resp.text))[0]
    table.columns = ["date", "value"]
    table["date"] = pd.to_datetime(table["date"])
    # Values may carry an "estimate" suffix or stray characters; keep digits/dot.
    table["value"] = pd.to_numeric(
        table["value"].astype(str).str.replace(r"[^0-9.]", "", regex=True),
        errors="coerce",
    )
    series = table.dropna().sort_values("date").set_index("date")["value"]
    series.name = slug
    return series
