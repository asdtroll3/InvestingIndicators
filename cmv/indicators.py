"""
Indicator implementations.

Every indicator is a function decorated with @indicator(...) that returns a
`Reading`. The decorator records it in REGISTRY so the runner can iterate over
all of them. To add a new model, write one function and decorate it — nothing
else needs to change.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import pandas as pd

from .datasources import fred_series, multpl_series, yahoo_close
from .stats import (
    exponential_trend,
    historical_percentile,
    mean_std_bands,
    valuation_label,
)

VALUATION = "Valuation"
RECESSION = "Recession"
SENTIMENT = "Sentiment"


@dataclass
class Reading:
    """The current state of one indicator."""

    key: str
    name: str
    category: str
    as_of: date
    value: float
    unit: str
    signal: str
    detail: str
    zscore: float | None = None
    percentile: float | None = None


# --- registry plumbing ------------------------------------------------------

REGISTRY: dict[str, Callable[[], Reading]] = {}


def indicator(key: str):
    """Register an indicator function under `key`."""

    def wrap(fn: Callable[[], Reading]) -> Callable[[], Reading]:
        REGISTRY[key] = fn
        return fn

    return wrap


def _latest(series: pd.Series) -> tuple[date, float]:
    return series.index[-1].date(), float(series.iloc[-1])


# --- valuation models (log-linear trend deviation) --------------------------


@indicator("buffett")
def buffett_indicator() -> Reading:
    """Total US market cap / GDP, vs its long-run exponential trend.

    Market cap is the Fed Z.1 measure of corporate equities outstanding
    (NCBEILQ027S, in $millions) — close to Buffett's original "value of all
    publicly traded securities" definition and available quarterly back to 1945.
    The Wilshire 5000 series FRED previously hosted were discontinued. Both this
    and nominal GDP are quarterly, so they align directly.
    """
    equities_millions = fred_series("NCBEILQ027S")
    gdp_billions = fred_series("GDP")

    equities_billions = equities_millions / 1000.0
    gdp_aligned = gdp_billions.reindex(equities_billions.index, method="ffill")
    ratio = (equities_billions / gdp_aligned).dropna()

    trend = exponential_trend(ratio)
    as_of = trend.index[-1].date()
    z = float(trend["zscore"].iloc[-1])
    val = float(trend["value"].iloc[-1])
    fair = float(trend["trend"].iloc[-1])

    return Reading(
        key="buffett",
        name="Buffett Indicator",
        category=VALUATION,
        as_of=as_of,
        value=val,
        unit="ratio",
        signal=valuation_label(z),
        detail=f"{val:.2f} vs trend {fair:.2f} ({z:+.1f} sd)",
        zscore=z,
    )


@indicator("price_earnings")
def price_earnings() -> Reading:
    """Cyclically-adjusted P/E (Shiller CAPE) vs its modern-era mean.

    CAPE = price / average real earnings over the prior 10 years (sourced from
    Shiller's data via multpl.com). Unlike the trend-based models, the site rates
    this against a static "modern-era" mean with standard-deviation bands; that
    modern era is post-1950, whose average (~20.7) reproduces the site's baseline.
    """
    cape = multpl_series("shiller-pe")
    value, mean, std, z = mean_std_bands(cape, baseline_start="1950-01-01")
    as_of = cape.index[-1].date()

    return Reading(
        key="price_earnings",
        name="Price/Earnings (CAPE)",
        category=VALUATION,
        as_of=as_of,
        value=value,
        unit="CAPE",
        signal=valuation_label(z),
        detail=f"{value:.1f} vs 1950+ avg {mean:.1f} ({z:+.1f} sd)",
        zscore=z,
    )


@indicator("mean_reversion")
def mean_reversion() -> Reading:
    """Inflation-adjusted S&P 500 vs its long-run exponential trend."""
    sp500 = yahoo_close("^GSPC")
    cpi = fred_series("CPIAUCSL")

    cpi_daily = cpi.reindex(sp500.index, method="ffill").dropna()
    sp500 = sp500.reindex(cpi_daily.index)
    real = (sp500 / cpi_daily * cpi_daily.iloc[-1]).dropna()

    trend = exponential_trend(real)
    as_of = trend.index[-1].date()
    z = float(trend["zscore"].iloc[-1])
    val = float(trend["value"].iloc[-1])
    fair = float(trend["trend"].iloc[-1])

    return Reading(
        key="mean_reversion",
        name="Mean Reversion (real S&P 500)",
        category=VALUATION,
        as_of=as_of,
        value=val,
        unit="index (real)",
        signal=valuation_label(z),
        detail=f"real {val:,.0f} vs trend {fair:,.0f} ({z:+.1f} sd)",
        zscore=z,
    )


# --- recession indicators (direct FRED reads) -------------------------------


@indicator("yield_curve")
def yield_curve() -> Reading:
    """10-year minus 3-month Treasury spread (FRED publishes it directly)."""
    spread = fred_series("T10Y3M")
    as_of, val = _latest(spread)
    inverted = val < 0
    return Reading(
        key="yield_curve",
        name="Yield Curve (10y-3m)",
        category=RECESSION,
        as_of=as_of,
        value=val,
        unit="%",
        signal="Inverted (recession risk)" if inverted else "Normal",
        detail=f"spread {val:+.2f}%",
    )


@indicator("sahm")
def sahm_rule() -> Reading:
    """Sahm recession indicator (real-time release on FRED)."""
    sahm = fred_series("SAHMREALTIME")
    as_of, val = _latest(sahm)
    triggered = val >= 0.5
    return Reading(
        key="sahm",
        name="Sahm Rule",
        category=RECESSION,
        as_of=as_of,
        value=val,
        unit="pp",
        signal="Triggered" if triggered else "Not triggered",
        detail=f"{val:.2f} (triggers at >= 0.50)",
    )


# --- sentiment models (direct reads + historical percentile) ----------------


@indicator("junk_spreads")
def junk_bond_spreads() -> Reading:
    """ICE BofA US High Yield option-adjusted spread."""
    spread = fred_series("BAMLH0A0HYM2")
    as_of, val = _latest(spread)
    pct = historical_percentile(spread, val)
    # Wide spreads = fear/bearish; narrow = complacent/bullish.
    if pct >= 70:
        signal = "Stressed (bearish)"
    elif pct <= 30:
        signal = "Complacent (bullish)"
    else:
        signal = "Neutral"
    return Reading(
        key="junk_spreads",
        name="Junk Bond Spreads (HY OAS)",
        category=SENTIMENT,
        as_of=as_of,
        value=val,
        unit="%",
        signal=signal,
        detail=f"{val:.2f}% - {pct:.0f}th pct of history",
        percentile=pct,
    )


@indicator("vix")
def vix() -> Reading:
    """CBOE VIX (FRED VIXCLS)."""
    v = fred_series("VIXCLS")
    as_of, val = _latest(v)
    pct = historical_percentile(v, val)
    if val >= 30:
        signal = "High fear"
    elif val <= 15:
        signal = "Calm"
    else:
        signal = "Normal"
    return Reading(
        key="vix",
        name="VIX (fear index)",
        category=SENTIMENT,
        as_of=as_of,
        value=val,
        unit="",
        signal=signal,
        detail=f"{val:.1f} - {pct:.0f}th pct of history",
        percentile=pct,
    )


@indicator("epu")
def economic_policy_uncertainty() -> Reading:
    """US Economic Policy Uncertainty Index (daily, FRED USEPUINDXD)."""
    epu = fred_series("USEPUINDXD")
    # Daily EPU is very noisy; smooth to a 30-day average for the read.
    smoothed = epu.rolling(30).mean().dropna()
    as_of, val = _latest(smoothed)
    pct = historical_percentile(smoothed, val)
    signal = "Elevated" if pct >= 70 else "Low" if pct <= 30 else "Normal"
    return Reading(
        key="epu",
        name="Economic Policy Uncertainty",
        category=SENTIMENT,
        as_of=as_of,
        value=val,
        unit="index (30d avg)",
        signal=signal,
        detail=f"{val:.0f} - {pct:.0f}th pct of history",
        percentile=pct,
    )


@indicator("consumer_confidence")
def consumer_confidence() -> Reading:
    """University of Michigan Consumer Sentiment (FRED UMCSENT)."""
    umcsent = fred_series("UMCSENT")
    as_of, val = _latest(umcsent)
    pct = historical_percentile(umcsent, val)
    # Low sentiment = pessimistic (and, contrarily, often a bullish extreme).
    signal = "Pessimistic" if pct <= 30 else "Optimistic" if pct >= 70 else "Neutral"
    return Reading(
        key="consumer_confidence",
        name="Consumer Confidence (UMich)",
        category=SENTIMENT,
        as_of=as_of,
        value=val,
        unit="index",
        signal=signal,
        detail=f"{val:.1f} - {pct:.0f}th pct of history",
        percentile=pct,
    )


# --- runner -----------------------------------------------------------------


def run_all(only: list[str] | None = None) -> list[tuple[str, Reading | Exception]]:
    """Run every registered indicator (or a subset by key).

    Network failures are caught per-indicator so one bad fetch doesn't abort the
    whole run; the exception is returned alongside the key.
    """
    keys = only or list(REGISTRY)
    results: list[tuple[str, Reading | Exception]] = []
    for key in keys:
        try:
            results.append((key, REGISTRY[key]()))
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            results.append((key, exc))
    return results
