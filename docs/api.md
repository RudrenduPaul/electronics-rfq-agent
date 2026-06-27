# API reference

## QuoteAgent

```python
QuoteAgent(
    erp: ERPMCPServer,
    model: str | None = None,        # Anthropic model for parsing (default: claude-sonnet-4-6)
    margin_pct: float = 0.15,        # margin added on top of ERP cost price
    max_concurrent: int = 10,        # max parallel ERP lookups
    telemetry: bool | TelemetryCollector = False,
)
```

| Method | Signature | Notes |
|---|---|---|
| `run` | `async run(rfq_source: str \| Path) -> Quote` | Async. Accepts file path or raw text. |
| `run_sync` | `run_sync(rfq_source: str \| Path) -> Quote` | Sync wrapper. Safe inside existing event loops. |

## ERP connector methods

All ERP connectors (`EpicorMCP`, `SAPMCP`, `OracleMCP`, `DynamicsMCP`, `MockERP`) implement:

```python
async def search_parts(query: str, limit: int = 20) -> list[ERPPartResult]
async def get_part(part_number: str) -> ERPPartResult | None
async def get_price(part_number: str, quantity: int) -> Decimal | None
async def check_inventory(part_number: str, quantity: int) -> bool
```

All connectors support the async context manager protocol, which ensures connections are closed cleanly:

```python
async with EpicorMCP(base_url="https://your-epicor.company.com", api_key="...") as erp:
    part = await erp.get_part("RES-0402-10K-1PCT")
    available = await erp.check_inventory("RES-0402-10K-1PCT", quantity=500)
    price = await erp.get_price("RES-0402-10K-1PCT", quantity=500)
```

## Quote output

```python
quote.lines          # list[QuoteLineItem]
quote.total_price    # Decimal
quote.summary()      # one-line string: id, counts, total
quote.to_dict()      # JSON-serializable dict (uses model_dump)

# Per line
line.status          # "found" | "substituted" | "not_found"
line.unit_price      # Decimal | None (sell price after margin)
line.extended_price  # Decimal | None (unit_price * quantity)
line.notes           # str | None — substitution reason, warnings, error detail
line.rfq_line        # original RFQLineItem from the document
line.erp_result      # ERPPartResult | None — raw ERP catalog data
```

## Error handling

`RFQParseError` and `ERPConnectionError` are importable from `electronics_rfq_agent`:

```python
from electronics_rfq_agent import QuoteAgent, RFQParseError
from electronics_rfq_agent.models import ERPConnectionError
from electronics_rfq_agent.mcp.mock import MockERP

agent = QuoteAgent(erp=MockERP())
try:
    quote = agent.run_sync("rfq.xlsx")
except RFQParseError as e:
    print(f"Could not parse RFQ: {e}")
except ERPConnectionError as e:
    print(f"ERP unreachable: {e}")
```

ERP connection errors during lookup do not raise at the `QuoteAgent` level — the affected line gets `status="not_found"` and the error detail is written to `line.notes`. Only a total parse failure raises `RFQParseError`.
