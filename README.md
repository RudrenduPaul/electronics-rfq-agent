# Electronics RFQ Agent

[![CI](https://github.com/RudrenduPaul/electronics-rfq-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/RudrenduPaul/electronics-rfq-agent/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/electronics-rfq-agent.svg)](https://badge.fury.io/py/electronics-rfq-agent)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/electronics-rfq-agent/badge)](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/electronics-rfq-agent)

Your sales engineers are spending 2-4 hours turning RFQ documents into quotes. This does it in 30 seconds.

Electronics RFQ Agent is a Python library that reads RFQ documents (PDF, Excel, Word), looks up every line item against your ERP catalog, and outputs a draft quote. It connects to SAP, Epicor, Oracle, and Microsoft Dynamics through MCP servers, so it works with Claude, GPT-4, or any agent framework that speaks MCP.

```bash
pip install electronics-rfq-agent
```

```python
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp import EpicorMCP

agent = QuoteAgent(
    erp=EpicorMCP(base_url="https://your-epicor.company.com", api_key="..."),
    max_concurrent=10,  # parallel ERP lookups (default: 10)
)
quote = agent.run_sync("rfq_2026_0619.xlsx")
print(quote.summary())
```

## Benchmark

Measured using the in-memory mock backend (200 realistic parts, no ERP system required). Run it yourself:

```bash
git clone https://github.com/RudrenduPaul/electronics-rfq-agent
cd electronics-rfq-agent
uv run python benchmarks/run.py
```

**ERP lookup + quote assembly (parser mocked, no Anthropic API call):**

| RFQ size | ERP lookup P50 | ERP lookup P99 | Assembly time |
|---|---|---|---|
| 10 lines | <0.1ms | <0.1ms | <0.1s |
| 25 lines | <0.1ms | <0.1ms | <0.1s |
| 50 lines | <0.1ms | <0.1ms | <0.1s |

*Benchmark covers ERP lookup and quote assembly only. The RFQ parser is mocked, so no Anthropic API call is made. In production, AI document parsing adds 5-15s per document and real ERP lookups add 100-500ms per line. Manual baseline for a 50-line RFQ: 2-4 hours.*

## Why we built this

We were working with electronics distributors who had 3-5 sales engineers spending most of their day on quote entry. Every tool we found was either tied to one specific ERP or required a 6-month integration project. We wanted something that worked with what distributors already had, could be self-hosted (quote data is sensitive), and was actually extensible.

The MCP architecture means adding a new ERP is writing one file. The parser handles the document formats distributors actually send: hand-filled PDFs, multi-sheet Excel files, and the occasional scanned table.

## ERP support

| ERP | Status | Connection | Docs |
|---|---|---|---|
| Epicor Kinetic | Supported | REST API | [Setup](docs/erp-setup/epicor.md) |
| SAP ECC / S/4HANA | Beta (manual install) | PyRFC (BAPI) | [Setup](docs/erp-setup/sap.md) |
| Oracle Cloud SCM | Supported | REST API | [Setup](docs/erp-setup/oracle.md) |
| Microsoft Dynamics 365 | Supported | Graph API | [Setup](docs/erp-setup/dynamics.md) |
| Mock backend | Built-in | In-memory | No config needed |

> **SAP note:** pyrfc requires the SAP NetWeaver RFC Library, which is not on PyPI and must be downloaded manually from SAP's support portal (S-user required). See [docs/erp-setup/sap.md](docs/erp-setup/sap.md) for step-by-step instructions.

## vs. alternatives

| | Electronics RFQ Agent | Manual process | SAP Joule | Generic AI (ChatGPT) |
|---|---|---|---|---|
| Multi-ERP support | SAP + Epicor + Oracle + Dynamics | N/A | SAP only | No ERP access |
| Quote time (50 lines) | ~15s | 2-4 hours | N/A | N/A |
| Self-hostable | Yes | N/A | No | No |
| Data stays local | Yes | Yes | No | No |
| Open source | MIT | N/A | No | No |
| Dev mock backend | Yes | N/A | No | N/A |
| MCP compatible | Yes | N/A | No | No |

## Self-host in 60 seconds

```bash
git clone https://github.com/RudrenduPaul/electronics-rfq-agent
cd electronics-rfq-agent
cp .env.example .env   # add your ERP credentials and Anthropic API key
docker compose up -d
```

Your quote data never leaves your environment.

## CLI

```bash
# Generate a quote from an RFQ file
erfa quote rfq.xlsx --mock

# Save the quote as JSON for later inspection
erfa quote rfq.xlsx --mock --output quote.json

# Audit what happened: what was found, substituted, or missing and why
erfa audit quote.json
```

**Audit output example:**

```
Audit Report - Quote a1b2c3d4
RFQ Source : rfq.xlsx
Lines      : 5
Total      : USD 42.30

FOUND (3)
------------------------------------------------------------
  L  1  RES-0402-10K-1PCT               qty=100  unit=0.0055  ext=0.55
  L  2  CAP-100NF-50V-X7R-0402          qty=50   unit=0.0121  ext=0.61
  L  4  IC-LM358-SOIC8                  qty=10   unit=1.6500  ext=16.50

SUBSTITUTED (1)
------------------------------------------------------------
  L  3  RES-0402-1K-5PCT                -> RES-0402-1K-1PCT
         Reason : Substituted 'RES-0402-1K-5PCT' with 'RES-0402-1K-1PCT'

NOT FOUND (1)
------------------------------------------------------------
  L  5  CUSTOM-CONNECTOR-DB9-M          Part 'CUSTOM-CONNECTOR-DB9-M' not found in ERP catalog

Fill rate: 80%  (3 found / 1 substituted / 1 not found)
```

> **Zero-price parts:** If a part exists in the ERP catalog but has a unit price of $0.00, the agent quotes $0 rather than skipping the line, and sets `line.notes` to `"Part '<number>' has zero unit price in ERP — verify pricing manually"`. Check `line.notes` for any found or substituted line before sending a quote to a customer.

## Integrations

Electronics RFQ Agent works with any agent framework that supports MCP:

| Framework | Install | Example |
|---|---|---|
| Claude (built-in) | `pip install electronics-rfq-agent` | [01-basic-quote](examples/01-basic-quote/) |
| LangGraph | `pip install 'electronics-rfq-agent[langgraph]'` | [04-langgraph-agent](examples/04-langgraph-agent/) |
| OpenAI Agents SDK | `pip install electronics-rfq-agent[agents]` | [05-openai-agents](examples/05-openai-agents/) |
| CrewAI | `pip install electronics-rfq-agent[crewai]` | -- |

## Quick start with mock ERP

No ERP system required to try it out:

```python
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp.mock import MockERP

agent = QuoteAgent(erp=MockERP())
quote = agent.run_sync("path/to/rfq.xlsx")

for line in quote.lines:
    print(f"{line.rfq_line.part_number}: {line.status} @ {line.unit_price}")

print(quote.summary())
```

MockERP applies quantity-based pricing tiers automatically: qty >= 1000 gets 20% off, qty >= 100 gets 10% off, qty >= 10 gets 5% off. List price applies below qty 10. This mirrors real-world volume pricing so benchmarks and integration tests reflect realistic cost curves.

## API reference

### QuoteAgent

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

### ERP connector methods

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

### Quote output

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

### Error handling

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

## Design partner telemetry (opt-in)

If you are a design partner, you can turn on anonymized telemetry. No part numbers, prices, or customer data is ever recorded.

```bash
ERFA_TELEMETRY=true erfa quote rfq.xlsx --mock
```

Or in Python:

```python
from electronics_rfq_agent import QuoteAgent, TelemetryCollector
from electronics_rfq_agent.mcp.mock import MockERP

agent = QuoteAgent(erp=MockERP(), telemetry=True)
```

Data is written to `~/.erfa/telemetry.jsonl`. Each record contains only: ERP type, line count, found/substituted/not-found counts, duration in ms, and package version. To push to a custom endpoint: `ERFA_TELEMETRY_ENDPOINT=https://your-endpoint/ingest`.

## Documentation

- [Getting started](docs/getting-started.md)
- [ERP setup: Epicor](docs/erp-setup/epicor.md)
- [ERP setup: SAP](docs/erp-setup/sap.md)
- [ERP setup: Oracle](docs/erp-setup/oracle.md)
- [ERP setup: Dynamics 365](docs/erp-setup/dynamics.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Community

GitHub Discussions: [Ask questions, share ideas](https://github.com/RudrenduPaul/electronics-rfq-agent/discussions)
Discord: coming soon
