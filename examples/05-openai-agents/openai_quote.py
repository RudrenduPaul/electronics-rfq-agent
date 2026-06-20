"""OpenAI Agents SDK example: Electronics RFQ Agent as a function tool.

The agent accepts a natural-language request that includes an RFQ and calls
generate_quote to produce a priced draft. The agent can answer follow-up
questions ("which parts are missing?", "what's the total?") or route the
quote to an approval workflow using additional tools.

Requirements:
    pip install 'electronics-rfq-agent[agents]'

Environment:
    OPENAI_API_KEY    — required for the OpenAI agent
    ANTHROPIC_API_KEY — required for RFQ document parsing
    ERFA_USE_MOCK=true is set automatically below (no real ERP needed)

Run:
    OPENAI_API_KEY=sk-...       \\
      ANTHROPIC_API_KEY=sk-...  \\
      uv run python examples/05-openai-agents/openai_quote.py
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("ERFA_USE_MOCK", "true")

try:
    from agents import Agent, Runner, function_tool
except ImportError as exc:
    raise ImportError(
        "OpenAI Agents SDK not installed. Run: pip install openai-agents"
    ) from exc

from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp.mock import MockERP

SAMPLE_RFQ = """
RFQ from Acme Electronics — 2026-06-19
Requested by: J. Smith

Part Number,Qty,Notes
RES-0402-10K-1PCT,1000,Tape and Reel
CAP-100NF-50V-X7R-0402,500,
IC-LM358-SOIC8,50,Confirm availability before quoting
XTAL-16MHZ-SMD,200,
MOSFET-NMOS-20V-3A-SOT23,100,
"""


@function_tool
async def generate_quote(rfq_text: str) -> str:
    """Parse an RFQ document and return a priced draft quote.

    Connects to the ERP catalog to look up prices and inventory, applies
    standard margin, and returns a structured text summary.

    Args:
        rfq_text: Full text content of the RFQ (CSV, plain text, or
                  pasted document content).
    """
    agent = QuoteAgent(erp=MockERP(), margin_pct=0.15)
    quote = await agent.run(rfq_text)

    found = [ln for ln in quote.lines if ln.status == "found"]
    substituted = [ln for ln in quote.lines if ln.status == "substituted"]
    not_found = [ln for ln in quote.lines if ln.status == "not_found"]

    line_details = "\n".join(
        f"  [{ln.status.upper()[:3]}] {ln.rfq_line.part_number}: "
        f"unit={ln.unit_price or 'N/A'}, qty={ln.rfq_line.quantity}, "
        f"extended={ln.extended_price or 'N/A'}"
        + (f" — {ln.notes}" if ln.notes else "")
        for ln in quote.lines
    )

    return (
        f"{quote.summary()}\n\n"
        f"Found: {len(found)} | Substituted: {len(substituted)} | "
        f"Not found: {len(not_found)}\n\n"
        f"Line items:\n{line_details}"
    )


quote_assistant = Agent(
    name="QuoteAssistant",
    instructions=(
        "You are a quoting assistant for an electronics distributor. "
        "When given an RFQ (request for quotation), call generate_quote with the "
        "full RFQ text to produce a priced draft quote. "
        "Present the result clearly: total price, which parts were found, "
        "any substitutions made, and any parts that could not be found in the catalog. "
        "If parts are missing, note that a sales engineer should follow up."
    ),
    tools=[generate_quote],
    model="gpt-4o",
)


async def main() -> None:
    result = await Runner.run(
        quote_assistant,
        input=(
            "Please generate a quote for the following RFQ "
            "and summarize what was found and what needs follow-up:\n\n" + SAMPLE_RFQ
        ),
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
