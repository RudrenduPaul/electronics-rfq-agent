# openquote

[![CI](https://github.com/RudrenduPaul/openquote-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/RudrenduPaul/openquote-ai/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/openquote.svg)](https://badge.fury.io/py/openquote)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/openquote-ai/badge)](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/openquote-ai)

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

Measured using the in-memory mock backend (200 realistic parts, no ERP system required). Run it yourself in under 5 minutes:

```bash
git clone https://github.com/RudrenduPaul/openquote-ai
cd openquote-ai
docker compose up -d
python benchmarks/run.py
```

| RFQ size | ERP lookup P50 | ERP lookup P99 | Total time | vs. manual |
|---|---|---|---|---|
| 10 lines | 0.04ms | 0.18ms | 4.1s | ~1750x faster |
| 25 lines | 0.04ms | 0.18ms | 7.2s | ~1000x faster |
| 50 lines | 0.04ms | 0.18ms | 14.8s | ~500x faster |

*Mock backend numbers. Real ERP latency is network-dependent. Manual baseline: 2-4 hours per 50-line RFQ.*

## Why we built this

We were working with electronics distributors who had 3-5 sales engineers spending most of their day on quote entry. Every tool we found was either tied to one specific ERP or required a 6-month integration project. We wanted something that worked with what distributors already had, could be self-hosted (quote data is sensitive), and was actually extensible.

The MCP architecture means adding a new ERP is writing one file. The parser handles the document formats distributors actually send -- which includes hand-filled PDFs, multi-sheet Excel files, and the occasional scanned table.

## ERP support

| ERP | Status | Connection | Docs |
|---|---|---|---|
| Epicor Kinetic | Supported | REST API | [Setup](docs/erp-setup/epicor.md) |
| SAP ECC / S/4HANA | Supported | PyRFC (BAPI) | [Setup](docs/erp-setup/sap.md) |
| Oracle Cloud SCM | Supported | REST API | [Setup](docs/erp-setup/oracle.md) |
| Microsoft Dynamics 365 | Supported | Graph API | [Setup](docs/erp-setup/dynamics.md) |
| Mock backend | Built-in | In-memory | No config needed |

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
git clone https://github.com/RudrenduPaul/openquote-ai
cd openquote-ai
cp .env.example .env   # add your ERP credentials and Anthropic API key
docker compose up -d
```

Your quote data never leaves your environment.

## Integrations

openquote works with any agent framework that supports MCP:

| Framework | Install |
|---|---|
| Claude (built-in) | `pip install openquote` |
| LangGraph | `pip install openquote[langchain]` |
| OpenAI Agents SDK | `pip install openquote[openai]` |
| CrewAI | `pip install openquote[crewai]` |

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

GitHub Discussions: [Ask questions, share ideas](https://github.com/RudrenduPaul/openquote-ai/discussions)
Discord: coming soon
