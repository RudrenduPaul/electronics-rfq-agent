"""Command-line interface for openquote.

Usage:
    openquote quote rfq.xlsx
    openquote quote rfq.pdf --mock
    OPENQUOTE_USE_MOCK=true openquote quote rfq.xlsx
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from openquote.mcp.base import ERPMCPServer

app = typer.Typer(
    name="openquote",
    help="AI quoting agent for electronics distributors. RFQ in, quote out.",
    add_completion=False,
)


@app.command()
def quote(
    rfq: Path = typer.Argument(..., help="RFQ file (PDF, Excel, Word, or plain text)"),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Use in-memory mock ERP (200 parts, no credentials needed)",
    ),
    margin: float = typer.Option(
        0.15, "--margin", help="Margin percentage (default 15%)"
    ),
) -> None:
    """Parse an RFQ document and print a draft quote."""
    from openquote.agent import QuoteAgent  # noqa: PLC0415

    erp = _build_erp(mock=mock)
    agent = QuoteAgent(erp=erp, margin_pct=margin)
    result = agent.run_sync(rfq)

    typer.echo(result.summary())
    typer.echo("")
    for line in result.lines:
        if line.status == "found":
            icon = "+"
            detail = (
                f"@ {line.unit_price} x {line.rfq_line.quantity}"
                f" = {line.extended_price}"
            )
        elif line.status == "substituted":
            icon = "~"
            detail = f"@ {line.unit_price} ({line.notes})"
        else:
            icon = "-"
            detail = "not found in ERP"
        typer.echo(f"  [{icon}] {line.rfq_line.part_number}  {detail}")


def _build_erp(*, mock: bool) -> ERPMCPServer:
    from openquote.mcp.mock import MockERP  # noqa: PLC0415

    if mock or os.environ.get("OPENQUOTE_USE_MOCK", "").lower() == "true":
        return MockERP()

    from openquote.mcp.epicor import EpicorMCP  # noqa: PLC0415

    return EpicorMCP()


def main() -> None:
    app()
