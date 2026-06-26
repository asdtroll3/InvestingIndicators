"""
Statistical helpers shared across indicators.

The currentmarketvaluation.com valuation models (Buffett Indicator, Mean
Reversion) fit an exponential — i.e. log-linear — trend through history and then
express "how stretched are we right now" as the deviation of the latest point
from that trend, measured in standard deviations of the residual. The direct
sentiment/recession reads instead use a historical percentile.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# z-score thresholds -> human label, matching the site's 5-band colouring.
_VALUATION_BANDS = [
    (2.0, "Strongly Overvalued"),
    (1.0, "Overvalued"),
    (-1.0, "Fair Value"),
    (-2.0, "Undervalued"),
    (float("-inf"), "Strongly Undervalued"),
]


def exponential_trend(series: pd.Series) -> pd.DataFrame:
    """Fit a log-linear trend over time and return value/trend/residual/zscore.

    The independent variable is years elapsed since the first observation, so the
    slope is a continuous-compounding growth rate. The z-score is the residual
    (log value minus log trend) standardised over the full history.
    """
    s = series.dropna()
    s = s[s > 0]
    if len(s) < 30:
        raise ValueError("Need at least 30 positive observations to fit a trend")

    years = np.asarray((s.index - s.index[0]).days, dtype=float) / 365.25
    log_y = np.log(s.to_numpy())
    slope, intercept = np.polyfit(years, log_y, 1)

    log_fit = intercept + slope * years
    resid = log_y - log_fit
    zscore = (resid - resid.mean()) / resid.std(ddof=0)

    return pd.DataFrame(
        {
            "value": s.to_numpy(),
            "trend": np.exp(log_fit),
            "resid": resid,
            "zscore": zscore,
        },
        index=s.index,
    )


def mean_std_bands(
    series: pd.Series, baseline_start: str | None = None
) -> tuple[float, float, float, float]:
    """Standard-deviation bands around a flat historical mean.

    Returns (latest_value, mean, std, zscore). Used by models that revert to a
    historical average rather than growing along a trend (e.g. CAPE). The mean
    and std are computed over `baseline_start`..now if given, else full history;
    the z-score is always for the most recent observation.
    """
    s = series.dropna()
    baseline = s if baseline_start is None else s[s.index >= baseline_start]
    mean = float(baseline.mean())
    std = float(baseline.std(ddof=0))
    value = float(s.iloc[-1])
    zscore = (value - mean) / std
    return value, mean, std, zscore


def valuation_label(zscore: float) -> str:
    """Map a trend-deviation z-score to the site's valuation band label."""
    for threshold, label in _VALUATION_BANDS:
        if zscore >= threshold:
            return label
    return "Strongly Undervalued"


def historical_percentile(series: pd.Series, value: float | None = None) -> float:
    """Percentile rank (0-100) of `value` (default: latest) within the series."""
    s = series.dropna()
    if value is None:
        value = s.iloc[-1]
    return float((s <= value).mean() * 100.0)
