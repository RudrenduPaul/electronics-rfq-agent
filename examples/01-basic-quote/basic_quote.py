"""Basic example: parse a text RFQ and generate a quote using the mock ERP."""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("OPENQUOTE_USE_MOCK", "true")

from openquote import QuoteAgent
from openquote.mcp.mock import MockERP

SAMPLE_RFQ = """
RFQ from Acme Electronics
Part Number,Qty,Notes
RES-0402-10K-1PCT,1000,Tape and Reel
CAP-100NF-50V-X7R-0402,500,
IC-LM358-SOIC8,50,Confirm availability
"""


async def main() -> None:
    agent = QuoteAgent(erp=MockERP(), margin_pct=0.15)
    quote = await agent.run(SAMPLE_RFQ)
    print(quote.summary())
    print()
    for line in quote.lines:
        status_icon = {"found": "OK", "not_found": "MISS", "substituted": "SUB"}.get(
            line.status, "?"
        )
        print(
            f"[{status_icon}] {line.rfq_line.part_number:30s} "
            f"qty={line.rfq_line.quantity:5d} "
            f"unit={line.unit_price or 'N/A'}"
        )


if __name__ == "__main__":
    asyncio.run(main())
