"""Command-line interface for Electronics RFQ Agent.

Usage:
    erfa quote rfq.xlsx
    erfa quote rfq.pdf --mock --output quote.json
    erfa audit quote.json
    ERFA_USE_MOCK=true erfa quote rfq.xlsx
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer

from electronics_rfq_agent.mcp.base import ERPMCPServer

app = typer.Typer(
    name="erfa",
    help=(
        "Electronics RFQ Agent: AI quoting agent for electronics distributors."
        " RFQ in, quote out."
    ),
    add_completion=False,
    no_args_is_help=True,
)


@app.callback()
def _callback() -> None:
    """AI quoting agent for electronics distributors. RFQ in, quote out."""


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
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Save quote JSON to this file"
    ),
) -> None:
    """Parse an RFQ document and print a draft quote."""
    from electronics_rfq_agent.agent import QuoteAgent  # noqa: PLC0415
    from electronics_rfq_agent.models import RFQParseError  # noqa: PLC0415

    erp = _build_erp(mock=mock)
    agent = QuoteAgent(erp=erp, margin_pct=margin)
    try:
        result = agent.run_sync(rfq)
    except FileNotFoundError:
        typer.echo(f"error: file not found: {rfq}", err=True)
        raise typer.Exit(code=1) from None
    except RFQParseError as exc:
        typer.echo(f"error: could not parse RFQ: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output is not None:
        output.write_text(json.dumps(result.to_dict(), indent=2))
        typer.echo(f"Quote saved to {output}", err=True)

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


@app.command()
def audit(
    quote_file: Path = typer.Argument(
        ..., help="Quote JSON file produced by `erfa quote --output`"
    ),
) -> None:
    """Print a full audit report for a saved quote.

    Shows every line: what was found, substituted, or missing and why.
    """
    if not quote_file.exists():
        typer.echo(f"error: file not found: {quote_file}", err=True)
        raise typer.Exit(code=1)

    try:
        data = json.loads(quote_file.read_text())
    except json.JSONDecodeError as exc:
        typer.echo(f"error: invalid JSON in {quote_file}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    lines = data.get("lines", [])
    rfq_source = data.get("rfq_source", "unknown")
    quote_id = data.get("id", "")[:8]
    total = data.get("total_price", "0.00")
    currency = data.get("currency", "USD")

    typer.echo(f"Audit Report - Quote {quote_id}")
    typer.echo(f"RFQ Source : {rfq_source}")
    typer.echo(f"Lines      : {len(lines)}")
    typer.echo(f"Total      : {currency} {total}")
    typer.echo("")

    found = [ln for ln in lines if ln["status"] == "found"]
    subst = [ln for ln in lines if ln["status"] == "substituted"]
    missing = [ln for ln in lines if ln["status"] == "not_found"]

    if found:
        typer.echo(f"FOUND ({len(found)})")
        typer.echo("-" * 60)
        for ln in found:
            rfq = ln["rfq_line"]
            typer.echo(
                f"  L{rfq['line_number']:>3}  {rfq['part_number']:<30}"
                f"  qty={rfq['quantity']}  unit={ln['unit_price']}"
                f"  ext={ln['extended_price']}"
            )

    if subst:
        typer.echo("")
        typer.echo(f"SUBSTITUTED ({len(subst)})")
        typer.echo("-" * 60)
        for ln in subst:
            rfq = ln["rfq_line"]
            erp_pn = ln.get("erp_result", {}) or {}
            erp_part = erp_pn.get("part_number", "?")
            typer.echo(
                f"  L{rfq['line_number']:>3}  {rfq['part_number']:<30}  → {erp_part}"
            )
            if ln.get("notes"):
                typer.echo(f"         Reason : {ln['notes']}")

    if missing:
        typer.echo("")
        typer.echo(f"NOT FOUND ({len(missing)})")
        typer.echo("-" * 60)
        for ln in missing:
            rfq = ln["rfq_line"]
            typer.echo(
                f"  L{rfq['line_number']:>3}  {rfq['part_number']:<30}"
                f"  {ln.get('notes', '')}"
            )

    typer.echo("")
    _summary_line(len(found), len(subst), len(missing))


def _summary_line(found: int, subst: int, missing: int) -> None:
    total = found + subst + missing
    fill_pct = round(100 * (found + subst) / total) if total else 0
    typer.echo(
        f"Fill rate: {fill_pct}%  "
        f"({found} found / {subst} substituted / {missing} not found)"
    )


def _build_erp(*, mock: bool) -> ERPMCPServer:
    from electronics_rfq_agent.mcp.mock import MockERP  # noqa: PLC0415

    if mock or os.environ.get("ERFA_USE_MOCK", "").lower() == "true":
        return MockERP()

    from electronics_rfq_agent.mcp.epicor import EpicorMCP  # noqa: PLC0415

    return EpicorMCP()


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
