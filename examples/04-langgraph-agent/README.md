# Example 4: LangGraph integration

Wraps `QuoteAgent` as a LangGraph `StateGraph` node. After the quote is
generated, a conditional edge routes:

- **High-value or incomplete quotes** → flagged for human review
- **Standard quotes** → auto-approved

This pattern lets you insert additional nodes between `generate_quote` and the
approval step — margin optimization, substitution rules, customer-specific
pricing overrides, or a human-in-the-loop checkpoint.

## Graph shape

```
[START]
   │
   ▼
generate_quote  ← QuoteAgent.run() — parse RFQ + ERP lookup
   │
   ▼
check_quote     ← flag if total > $5K or any parts missing
   │
   ├── needs_review=True  ──▶  flag_for_review ──▶ [END]
   └── needs_review=False ──▶  auto_approve    ──▶ [END]
```

## Install

```bash
pip install 'electronics-rfq-agent[langchain]' langgraph
```

## Run

```bash
ANTHROPIC_API_KEY=sk-...       \
  ERFA_USE_MOCK=true      \
  python examples/04-langgraph-agent/langgraph_quote.py
```

`ERFA_USE_MOCK=true` is set automatically in the script — you do not need
a real ERP system. `ANTHROPIC_API_KEY` is required for RFQ document parsing.

## Connect to a real ERP

Replace `MockERP()` in `generate_quote()` with any `ERPMCPServer` implementation:

```python
from electronics_rfq_agent.mcp import EpicorMCP

async def generate_quote(state: QuoteState) -> dict:
    erp = EpicorMCP(
        base_url=os.environ["EPICOR_URL"],
        api_key=os.environ["EPICOR_API_KEY"],
    )
    agent = QuoteAgent(erp=erp, margin_pct=0.15)
    quote = await agent.run(state["rfq_source"])
    return {"quote": quote}
```

## Extend the graph

Add a node between `generate_quote` and `check_quote` to apply custom pricing rules:

```python
def apply_customer_pricing(state: QuoteState) -> dict:
    quote = state["quote"]
    # apply customer-specific margin overrides, contract pricing, etc.
    return {"quote": modified_quote}

graph.add_node("apply_customer_pricing", apply_customer_pricing)
graph.add_edge("generate_quote", "apply_customer_pricing")
graph.add_edge("apply_customer_pricing", "check_quote")
```
