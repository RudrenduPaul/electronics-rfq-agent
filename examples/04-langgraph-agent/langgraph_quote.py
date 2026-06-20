"""LangGraph example: RFQ-to-quote workflow with conditional approval routing.

Wraps QuoteAgent as a LangGraph StateGraph node. After quote generation, a
conditional edge routes high-value or incomplete quotes to a review flag,
and standard quotes to auto-approval. Extend by inserting more nodes between
generate_quote and the approval step (margin optimization, substitution rules,
customer-specific pricing, human-in-the-loop review, etc.).

Run:
    ANTHROPIC_API_KEY=sk-... \\
      ERFA_USE_MOCK=true \\
      uv run python examples/04-langgraph-agent/langgraph_quote.py
"""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from typing import Any, TypedDict

os.environ.setdefault("ERFA_USE_MOCK", "true")

try:
    from langgraph.graph import END, StateGraph
except ImportError as exc:
    raise ImportError(
        "LangGraph not installed. "
        "Run: pip install 'electronics-rfq-agent[langchain]' langgraph"
    ) from exc

from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp.mock import MockERP
from electronics_rfq_agent.models import Quote

SAMPLE_RFQ = """
RFQ from Acme Electronics — 2026-06-19
Requested by: J. Smith | Terms: Net 30

Part Number,Qty,Required Date,Notes
RES-0402-10K-1PCT,1000,2026-07-15,Tape and Reel preferred
CAP-100NF-50V-X7R-0402,500,2026-07-15,
IC-LM358-SOIC8,50,2026-07-30,Confirm availability before quoting
XTAL-16MHZ-SMD,200,2026-07-15,
MOSFET-NMOS-20V-3A-SOT23,100,2026-07-30,
"""

REVIEW_THRESHOLD = Decimal("5000.00")


class QuoteState(TypedDict):
    rfq_source: str
    quote: Quote | None
    needs_review: bool
    review_reason: str
    output: str


# ── nodes ──────────────────────────────────────────────────────────────────────


async def generate_quote(state: QuoteState) -> dict[str, Any]:
    """Parse the RFQ and generate a draft quote via the ERP."""
    agent = QuoteAgent(erp=MockERP(), margin_pct=0.15)
    quote = await agent.run(state["rfq_source"])
    return {"quote": quote}


def check_quote(state: QuoteState) -> dict[str, Any]:
    """Flag for human review if any parts are missing or total exceeds threshold."""
    quote = state["quote"]
    if quote is None:
        return {"needs_review": True, "review_reason": "Quote generation failed"}

    missing = [ln for ln in quote.lines if ln.status == "not_found"]
    if missing:
        parts = ", ".join(ln.rfq_line.part_number for ln in missing)
        return {"needs_review": True, "review_reason": f"Parts not in ERP: {parts}"}

    if quote.total_price >= REVIEW_THRESHOLD:
        return {
            "needs_review": True,
            "review_reason": (
                f"Total ${quote.total_price:,.2f} exceeds "
                f"${REVIEW_THRESHOLD:,.2f} auto-approve threshold"
            ),
        }

    return {"needs_review": False, "review_reason": ""}


def auto_approve(state: QuoteState) -> dict[str, Any]:
    quote = state["quote"]
    assert quote is not None
    line_summary = "\n".join(
        f"  [{ln.status.upper()[:3]}] {ln.rfq_line.part_number:<32s} "
        f"qty={ln.rfq_line.quantity:<6d} unit={ln.unit_price or 'N/A':<12} "
        f"ext={ln.extended_price or 'N/A'}"
        for ln in quote.lines
    )
    return {
        "output": (
            f"QUOTE AUTO-APPROVED\n"
            f"{'─' * 60}\n"
            f"{quote.summary()}\n\n"
            f"Line items:\n{line_summary}"
        )
    }


def flag_for_review(state: QuoteState) -> dict[str, Any]:
    quote = state["quote"]
    assert quote is not None
    return {
        "output": (
            f"QUOTE FLAGGED FOR REVIEW\n"
            f"{'─' * 60}\n"
            f"Reason: {state['review_reason']}\n\n"
            f"{quote.summary()}"
        )
    }


# ── routing ────────────────────────────────────────────────────────────────────


def route_after_check(state: QuoteState) -> str:
    return "flag_for_review" if state["needs_review"] else "auto_approve"


# ── graph ──────────────────────────────────────────────────────────────────────


def build_graph() -> Any:  # returns langgraph.graph.CompiledGraph
    graph: StateGraph = StateGraph(QuoteState)
    graph.add_node("generate_quote", generate_quote)
    graph.add_node("check_quote", check_quote)
    graph.add_node("auto_approve", auto_approve)
    graph.add_node("flag_for_review", flag_for_review)

    graph.set_entry_point("generate_quote")
    graph.add_edge("generate_quote", "check_quote")
    graph.add_conditional_edges("check_quote", route_after_check)
    graph.add_edge("auto_approve", END)
    graph.add_edge("flag_for_review", END)

    return graph.compile()


async def main() -> None:
    app = build_graph()
    result: QuoteState = await app.ainvoke(
        {
            "rfq_source": SAMPLE_RFQ,
            "quote": None,
            "needs_review": False,
            "review_reason": "",
            "output": "",
        }
    )
    print(result["output"])


if __name__ == "__main__":
    asyncio.run(main())
