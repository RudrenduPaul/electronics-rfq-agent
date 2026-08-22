"""MCP stdio server exposing Electronics RFQ Agent's core capabilities as tools.

Launch with `erfa mcp` (or `python -m electronics_rfq_agent.mcp_server`). Any
MCP-compatible agent client (Claude, GPT-4, Gemini, or a custom agent) can then
call quote_rfq, lookup_part, and audit_quote directly over stdio, without
shelling out to the CLI or screen-scraping human-formatted text.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from electronics_rfq_agent.cli import _build_erp
from electronics_rfq_agent.models import RFQParseError

mcp = FastMCP("electronics-rfq-agent")


@mcp.tool()
async def quote_rfq(
    rfq_path: str, mock: bool = False, margin: float = 0.15
) -> dict[str, Any]:
    """Parse an RFQ document (PDF, Excel, Word, or plain text) and return a draft quote.

    Args:
        rfq_path: Path to the RFQ file.
        mock: Use the in-memory mock ERP (200 parts, no credentials needed).
        margin: Margin percentage on top of ERP cost price (default 0.15 = 15%).
    """
    from electronics_rfq_agent.agent import QuoteAgent  # noqa: PLC0415

    erp = _build_erp(mock=mock)
    agent = QuoteAgent(erp=erp, margin_pct=margin)
    try:
        result = await agent.run(rfq_path)
    except FileNotFoundError:
        return {"error": f"file not found: {rfq_path}"}
    except RFQParseError as exc:
        return {"error": f"could not parse RFQ: {exc}"}
    return result.to_dict()


@mcp.tool()
async def lookup_part(part_number: str, mock: bool = False) -> dict[str, Any] | None:
    """Look up a single part in the ERP catalog by exact part number.

    Args:
        part_number: The exact part number to look up.
        mock: Use the in-memory mock ERP (200 parts, no credentials needed).
    """
    erp = _build_erp(mock=mock)
    async with erp:
        part = await erp.get_part(part_number)
    return part.model_dump(mode="json") if part is not None else None


@mcp.tool()
def audit_quote(quote_json_path: str) -> dict[str, Any]:
    """Read a saved quote JSON file and return a found/substituted/not-found breakdown.

    Args:
        quote_json_path: Path to a quote JSON file produced by quote_rfq
            or `erfa quote --output`.
    """
    path = Path(quote_json_path)
    if not path.exists():
        return {"error": f"file not found: {quote_json_path}"}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return {"error": f"invalid JSON in {quote_json_path}: {exc}"}
    if not isinstance(data, dict):
        return {
            "error": (
                f"expected a JSON object in {quote_json_path}, "
                f"got {type(data).__name__}"
            )
        }

    lines = data.get("lines", [])
    found = [ln for ln in lines if ln.get("status") == "found"]
    substituted = [ln for ln in lines if ln.get("status") == "substituted"]
    not_found = [ln for ln in lines if ln.get("status") == "not_found"]
    total = len(lines)
    fill_rate_pct = round(100 * (len(found) + len(substituted)) / total) if total else 0

    return {
        "quote_id": data.get("id", ""),
        "rfq_source": data.get("rfq_source", "unknown"),
        "total_price": data.get("total_price", "0.00"),
        "currency": data.get("currency", "USD"),
        "found": found,
        "substituted": substituted,
        "not_found": not_found,
        "fill_rate_pct": fill_rate_pct,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
