"""
cmv — Python replications of the indicators on currentmarketvaluation.com.

Each indicator is a small, self-contained function that pulls public data
(mostly FRED via pandas-datareader, plus Yahoo Finance for index prices) and
returns a `Reading` describing the current state and a valuation/sentiment
signal. Indicators are registered so new ones can be added without touching the
runner.
"""

from .indicators import REGISTRY, Reading, run_all  # noqa: F401

__all__ = ["REGISTRY", "Reading", "run_all"]
