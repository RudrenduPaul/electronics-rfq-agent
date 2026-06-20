# openquote

[![CI](https://github.com/RudrenduPaul/electronics-rfq-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/RudrenduPaul/electronics-rfq-agent/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/openquote.svg)](https://badge.fury.io/py/openquote)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/electronics-rfq-agent/badge)](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/electronics-rfq-agent)

Your sales engineers are spending 2-4 hours turning RFQ documents into quotes. This does it in 30 seconds.

openquote is a Python library that reads RFQ documents (PDF, Excel, Word), looks up every line item against your ERP catalog, and outputs a draft quote. It connects to SAP, Epicor, Oracle, and Microsoft Dynamics through MCP servers, so it works with Claude, GPT-4, or any agent framework that speaks MCP.

```bash
pip install openquote
```

```python
from openquote import QuoteAgent
from openquote.mcp import EpicorMCP

agent = QuoteAgent(
    erp=EpicorMCP(base_url="https://your-epicor.company.com", api_key="..."),
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

*These numbers reflect the ERP lookup and quote assembly portion only — the benchmark mocks the RFQ parser so no Anthropic API call is made. In a real run, AI document parsing (one Claude API call per document) adds 5–15s depending on document size and API latency. Real ERP latency adds 100–500ms per line item over the network. Manual baseline for a 50-line RFQ: 2–4 hours.*

## Why we built this

We were working with electronics distributors who had 3-5 sales engineers spending most of their day on quote entry. Every tool we found was either tied to one specific ERP or required a 6-month integration project. We wanted something that worked with what distributors already had, could be self-hosted (quote data is sensitive), and was actually extensible.

The MCP architecture means adding a new ERP is writing one file. The parser handles the document formats distributors actually send -- which includes hand-filled PDFs, multi-sheet Excel files, and the occasional scanned table.

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

| | openquote | Manual process | SAP Joule | Generic AI (ChatGPT) |
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
openquote quote rfq.xlsx --mock

# Save the quote as JSON for later inspection
openquote quote rfq.xlsx --mock --output quote.json

# Audit what happened: what was found, substituted, or missing and why
openquote audit quote.json
```

**Audit output example:**

```
Audit Report — Quote a1b2c3d4
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
  L  3  RES-0402-1K-5PCT                → RES-0402-1K-1PCT
         Reason : Substituted 'RES-0402-1K-5PCT' with 'RES-0402-1K-1PCT'

NOT FOUND (1)
------------------------------------------------------------
  L  5  CUSTOM-CONNECTOR-DB9-M          Part 'CUSTOM-CONNECTOR-DB9-M' not found in ERP catalog

Fill rate: 80%  (3 found / 1 substituted / 1 not found)
```

## Integrations

openquote works with any agent framework that supports MCP:

| Framework | Install | Example |
|---|---|---|
| Claude (built-in) | `pip install openquote` | [01-basic-quote](examples/01-basic-quote/) |
| LangGraph | `pip install 'openquote[langgraph]'` | [04-langgraph-agent](examples/04-langgraph-agent/) |
| OpenAI Agents SDK | `pip install openquote[agents]` | [05-openai-agents](examples/05-openai-agents/) |
| CrewAI | `pip install openquote[crewai]` | — |

## Quick start with mock ERP

No ERP system required to try openquote:

```python
from openquote import QuoteAgent
from openquote.mcp.mock import MockERP

agent = QuoteAgent(erp=MockERP())
quote = agent.run_sync("path/to/rfq.xlsx")

for line in quote.lines:
    print(f"{line.rfq_line.part_number}: {line.status} @ {line.unit_price}")

print(quote.summary())
```

## Design partner telemetry (opt-in)

Design partners can enable anonymized usage telemetry to share aggregate data — no part numbers, prices, or customer information is ever recorded.

```bash
OPENQUOTE_TELEMETRY=true openquote quote rfq.xlsx --mock
```

Or in Python:

```python
from openquote import QuoteAgent, TelemetryCollector
from openquote.mcp.mock import MockERP

agent = QuoteAgent(erp=MockERP(), telemetry=True)
```

Data written to `~/.openquote/telemetry.jsonl`. Each record contains only: ERP type, line count, found/substituted/not-found counts, duration in ms, and openquote version. To push to a custom endpoint: `OPENQUOTE_TELEMETRY_ENDPOINT=https://your-endpoint/ingest`.

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
