# Getting started with openquote

## Prerequisites

- Python 3.10 or later
- An Anthropic API key (for RFQ parsing)
- An ERP system account (or use the built-in mock backend)

## Installation

```bash
pip install openquote
```

For SAP connectivity:

```bash
pip install openquote[sap]
# Also install SAP NetWeaver RFC Library -- see docs/erp-setup/sap.md
```

## Your first quote

### With the mock backend (no ERP needed)

```python
import asyncio
from openquote import QuoteAgent
from openquote.mcp.mock import MockERP

async def main():
    agent = QuoteAgent(erp=MockERP())
    quote = await agent.run("path/to/rfq.xlsx")
    print(quote.summary())
    for line in quote.lines:
        print(f"  {line.rfq_line.part_number}: {line.status} @ {line.unit_price}")

asyncio.run(main())
```

Or synchronously:

```python
from openquote import QuoteAgent
from openquote.mcp.mock import MockERP

agent = QuoteAgent(erp=MockERP())
quote = agent.run_sync("path/to/rfq.xlsx")
print(quote.summary())
```

### With Epicor Kinetic

```python
from openquote import QuoteAgent
from openquote.mcp import EpicorMCP

erp = EpicorMCP(
    base_url="https://your-epicor.company.com",
    api_key="your-base64-encoded-credentials",
    company="EPIC",
)
agent = QuoteAgent(erp=erp, margin_pct=0.15)
quote = agent.run_sync("rfq.pdf")
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for PDF/text parsing) | -- | Anthropic API key |
| `OPENQUOTE_MODEL` | No | `claude-sonnet-4-6` | Anthropic model for parsing |
| `OPENQUOTE_USE_MOCK` | No | `false` | Force mock backend for all connectors |
| `OPENQUOTE_EPICOR_URL` | Epicor only | -- | Epicor base URL |
| `OPENQUOTE_EPICOR_API_KEY` | Epicor only | -- | Epicor Basic auth credentials |

See `.env.example` for the full list.

## Supported document formats

| Format | Parser |
|---|---|
| PDF | Claude vision API (reads tables and text) |
| Excel (.xlsx, .xls) | openpyxl (reads first sheet, auto-detects header row) |
| Word (.docx) | python-docx (reads all tables) |
| Plain text | Claude API (sends text directly) |

## Quote output

A `Quote` object contains:

```python
quote.id              # UUID
quote.rfq_source      # file path or "text"
quote.lines           # list[QuoteLineItem]
quote.total_price     # Decimal (sum of extended_price for found/substituted lines)
quote.currency        # "USD" (default)
quote.summary()       # one-line string summary
quote.to_dict()       # JSON-serializable dict
```

Each `QuoteLineItem` has:

```python
line.rfq_line         # original RFQLineItem
line.erp_result       # ERPPartResult | None
line.status           # "found" | "not_found" | "substituted"
line.unit_price       # Decimal | None (sell price including margin)
line.extended_price   # Decimal | None (unit_price x quantity)
line.notes            # str | None
```

## Margin configuration

The default margin is 15%. Adjust per agent:

```python
agent = QuoteAgent(erp=erp, margin_pct=0.20)  # 20% margin
```

## Next steps

- [Epicor setup](erp-setup/epicor.md)
- [SAP setup](erp-setup/sap.md)
- [Contributing a new ERP integration](../CONTRIBUTING.md#adding-a-new-erp-integration)
