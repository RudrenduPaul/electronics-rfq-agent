# Example 5: OpenAI Agents SDK integration

Wraps `QuoteAgent` as a `@function_tool` inside an OpenAI Agents SDK agent.
The agent accepts a natural-language request containing an RFQ, calls
`generate_quote` to produce a priced draft, and can answer follow-up questions
("which parts are missing?", "what's the total excluding tax?").

This is the entry point for building a full quoting assistant: add more tools
for sending quotes by email, creating CRM records, or routing to an approval
workflow.

## Install

```bash
pip install electronics-rfq-agent[openai] openai-agents
```

## Run

```bash
OPENAI_API_KEY=sk-...       \
  ANTHROPIC_API_KEY=sk-...  \
  python examples/05-openai-agents/openai_quote.py
```

`ERFA_USE_MOCK=true` is set automatically in the script.

- `OPENAI_API_KEY` — used by the OpenAI agent for reasoning (GPT-4o)
- `ANTHROPIC_API_KEY` — used by Electronics RFQ Agent's RFQ parser (Claude)
- No real ERP system needed with `ERFA_USE_MOCK=true`

## How it works

```
User message: "Please quote this RFQ: ..."
       │
       ▼
 OpenAI Agent (GPT-4o)
       │  calls
       ▼
 generate_quote(rfq_text)          ← @function_tool
       │
       ├── RFQParser (Claude)      ← extract line items from text
       └── MockERP (in-memory)     ← look up prices + inventory
       │
       ▼
 Quote summary returned to agent
       │
       ▼
 Agent formats response + flags missing parts
```

## Connect to a real ERP

Replace `MockERP()` in `generate_quote` with any `ERPMCPServer`:

```python
from electronics_rfq_agent.mcp import EpicorMCP

@function_tool
async def generate_quote(rfq_text: str) -> str:
    erp = EpicorMCP(
        base_url=os.environ["EPICOR_URL"],
        api_key=os.environ["EPICOR_API_KEY"],
    )
    agent = QuoteAgent(erp=erp, margin_pct=0.15)
    quote = await agent.run(rfq_text)
    ...
```

## Add more tools

Extend the agent with additional tools to build a complete quoting workflow:

```python
@function_tool
async def send_quote_email(quote_summary: str, recipient_email: str) -> str:
    """Email the draft quote to the customer for review."""
    ...

@function_tool
async def create_crm_opportunity(quote_id: str, customer: str) -> str:
    """Create a CRM opportunity from the quote."""
    ...

quote_assistant = Agent(
    name="QuoteAssistant",
    instructions="...",
    tools=[generate_quote, send_quote_email, create_crm_opportunity],
    model="gpt-4o",
)
```
