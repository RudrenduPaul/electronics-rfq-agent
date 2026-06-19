"""Epicor Kinetic integration example."""

from __future__ import annotations

import asyncio

from openquote import QuoteAgent
from openquote.mcp import EpicorMCP


async def main() -> None:
    erp = EpicorMCP()
    agent = QuoteAgent(erp=erp, margin_pct=0.15)

    async with erp:
        quote = await agent.run("path/to/rfq.xlsx")

    print(quote.summary())
    for line in quote.lines:
        if line.status == "found":
            print(
                f"{line.rfq_line.part_number}: "
                f"{line.erp_result.description if line.erp_result else ''} "
                f"@ {line.unit_price} x {line.rfq_line.quantity} "
                f"= {line.extended_price}"
            )


if __name__ == "__main__":
    asyncio.run(main())
