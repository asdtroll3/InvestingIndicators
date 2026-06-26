# Market Valuation Models

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A Python toolkit that reproduces the market-valuation, recession, and sentiment
models published on [currentmarketvaluation.com](https://www.currentmarketvaluation.com/)
from primary public data. Every indicator pulls **live data on each run** — no
manual updates, no stored datasets — and reports a current reading plus a
bullish/bearish/recession signal.

Data comes from [FRED](https://fred.stlouisfed.org/) (no API key required, via
`pandas-datareader`), Yahoo Finance (index prices), and Robert Shiller's dataset
(via multpl.com).

## Example

```text
Current Market Valuation - indicator snapshot

Valuation
┌───────────────────────────────┬────────────┬─────────────────┬────────────────┐
│ Indicator                     │ As of      │ Signal          │ Detail         │
├───────────────────────────────┼────────────┼─────────────────┼────────────────┤
│ Buffett Indicator             │ 2026-01-01 │ Overvalued      │ 2.18 vs trend  │
│                               │            │                 │ 1.46 (+1.2 sd) │
│ Price/Earnings (CAPE)         │ 2026-06-25 │ Strongly Over.. │ 41.0 vs 1950+  │
│                               │            │                 │ avg 20.8 (+2.4 │
│                               │            │                 │ sd)            │
│ Mean Reversion (real S&P 500) │ 2026-06-26 │ Overvalued      │ real 7,317 vs  │
│                               │            │                 │ trend 4,064    │
└───────────────────────────────┴────────────┴─────────────────┴────────────────┘

Recession
┌──────────────────────┬────────────┬───────────────┬───────────────┐
│ Yield Curve (10y-3m) │ 2026-06-25 │ Normal        │ spread +0.56% │
│ Sahm Rule            │ 2026-05-01 │ Not triggered │ 0.10          │
└──────────────────────┴────────────┴───────────────┴───────────────┘

Sentiment
┌─────────────────────────────┬────────────┬────────────────────┐
│ Junk Bond Spreads (HY OAS)  │ 2026-06-24 │ Complacent (bull.) │
│ VIX (fear index)            │ 2026-06-24 │ Normal             │
│ Economic Policy Uncertainty │ 2026-06-21 │ Elevated           │
│ Consumer Confidence (UMich) │ 2026-04-01 │ Pessimistic        │
└─────────────────────────────┴────────────┴────────────────────┘
```

The `As of` column reflects each series' own release cadence (daily market data
is current; macro series like GDP or unemployment are inherently lagged).

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install pandas numpy pandas-datareader yfinance requests lxml rich

# 3. Run
python InvestingIndicators.py            # all indicators
python InvestingIndicators.py vix sahm   # a subset, by key
```

**Dependencies:** `pandas` / `numpy` (data & numerics), `pandas-datareader`
(FRED, no API key), `yfinance` (Yahoo index prices), `requests` + `lxml`
(multpl.com Shiller CAPE scrape), `rich` (terminal table).

## Architecture

| File | Role |
|---|---|
| `InvestingIndicators.py` | CLI runner — prints the snapshot table (uses `rich`) |
| `cmv/datasources.py` | Cached FRED / Yahoo / multpl fetch helpers |
| `cmv/stats.py` | Trend & mean-reversion z-score bands, historical percentiles |
| `cmv/indicators.py` | One function per indicator, auto-registered in `REGISTRY` |

Indicators are decoupled from data access and from the runner. Each one is a
small function returning a `Reading` dataclass and decorated with
`@indicator("key")`; the runner discovers everything in the registry, so **adding
a model is a single self-contained function** — nothing else needs wiring.

## Methodology

- **Trend-based valuation** (Buffett, Mean Reversion) — fit an exponential
  (log-linear) trend over full history; rate the current level by its deviation
  from trend in standard deviations (`+1σ`/`+2σ` over, `-1σ`/`-2σ` under).
- **Mean-reverting valuation** (Price/Earnings / CAPE) — rate against a static
  historical mean ± standard deviations rather than a rising trend, matching the
  site's "modern-era" (post-1950) CAPE average of ~20.7.
- **Direct reads** (yield curve, Sahm, junk spreads, VIX, EPU, confidence) — the
  latest value plus either a fixed threshold (Sahm ≥ 0.50) or a historical
  percentile.

## Indicators

**Implemented (9 of 15)**

| Category | Indicator | Primary source |
|---|---|---|
| Valuation | Buffett Indicator | FRED `NCBEILQ027S` ÷ `GDP` |
| Valuation | Price/Earnings (CAPE) | multpl.com `shiller-pe` (Shiller data) |
| Valuation | Mean Reversion (real S&P 500) | Yahoo `^GSPC` + FRED `CPIAUCSL` |
| Recession | Yield Curve (10y-3m) | FRED `T10Y3M` |
| Recession | Sahm Rule | FRED `SAHMREALTIME` |
| Sentiment | Junk Bond Spreads | FRED `BAMLH0A0HYM2` |
| Sentiment | VIX | FRED `VIXCLS` |
| Sentiment | Economic Policy Uncertainty | FRED `USEPUINDXD` |
| Sentiment | Consumer Confidence | FRED `UMCSENT` |

**Roadmap**

| Indicator | Notes |
|---|---|
| Price/Sales | S&P aggregate sales (Damodaran / S&P datasets) |
| Interest Rate Model | Regress S&P valuation on the 10y yield |
| Earnings Yield Gap | S&P earnings yield − Treasury yield |
| Leading Economic Index | Conference Board LEI |
| State Coincidence | FRED per-state coincidence indexes, count declining |
| Margin Debt | FINRA monthly margin statistics |
| Charts | Plot each series with its valuation bands (text-only today) |

## Notes & caveats

- The Buffett market-cap proxy uses the Fed Z.1 corporate-equities series because
  FRED discontinued its Wilshire 5000 series. It's close to Buffett's original
  "all publicly traded securities" definition but not identical to the
  Wilshire-based number the site shows.
- The yield-curve signal is currently a simplified inverted/not-inverted read.
  The reference site rates recession risk by *time elapsed since the curve
  normalized* (highest 0–6 months after un-inversion), since recessions
  historically follow re-steepening — a planned upgrade.
- Trend/mean bands are fit on full history each run, so exact σ values drift
  slightly from the site, which may use a fixed lookback or anchor.

## Disclaimer

This project is for educational and informational purposes only. It is **not
investment advice** and makes no guarantee of data accuracy. Do your own research
before making any financial decision.

## License

[MIT](LICENSE)
