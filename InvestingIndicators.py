"""
InvestingIndicators — current readings for the currentmarketvaluation.com models.

Run it to print a snapshot of every implemented indicator grouped by category:

    .venv\\Scripts\\python.exe InvestingIndicators.py

Optionally pass indicator keys to run only a subset, e.g.:

    .venv\\Scripts\\python.exe InvestingIndicators.py vix yield_curve
"""
from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table

from cmv import Reading, run_all

# Colour the signal cell by how bullish/bearish it reads, loosely matching the
# site's red(over)/green(under) convention.
_BEARISH = {"Strongly Overvalued", "Overvalued", "Inverted (recession risk)",
            "Triggered", "Stressed (bearish)", "High fear", "Elevated"}
_BULLISH = {"Strongly Undervalued", "Undervalued", "Complacent (bullish)",
            "Calm", "Pessimistic", "Low"}


def _signal_style(signal: str) -> str:
    if signal in _BEARISH:
        return "bold red"
    if signal in _BULLISH:
        return "bold green"
    return "yellow"


def main(argv: list[str]) -> int:
    only = argv or None
    # Windows terminals often default to cp1252; force UTF-8 so the table's
    # box-drawing characters render regardless of the active code page.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001 - best effort
        pass
    console = Console()
    console.print("[bold]Current Market Valuation - indicator snapshot[/bold]\n")

    results = run_all(only)

    by_category: dict[str, list[Reading]] = {}
    errors: list[tuple[str, Exception]] = []
    for key, res in results:
        if isinstance(res, Exception):
            errors.append((key, res))
        else:
            by_category.setdefault(res.category, []).append(res)

    for category in ("Valuation", "Recession", "Sentiment"):
        readings = by_category.get(category)
        if not readings:
            continue
        table = Table(title=category, title_justify="left", expand=False)
        table.add_column("Indicator", style="cyan", no_wrap=True)
        table.add_column("As of", style="dim")
        table.add_column("Signal")
        table.add_column("Detail", style="dim")
        for r in readings:
            table.add_row(
                r.name,
                r.as_of.isoformat(),
                f"[{_signal_style(r.signal)}]{r.signal}[/]",
                r.detail,
            )
        console.print(table)
        console.print()

    if errors:
        console.print("[bold red]Failed to fetch:[/bold red]")
        for key, exc in errors:
            console.print(f"  - {key}: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
