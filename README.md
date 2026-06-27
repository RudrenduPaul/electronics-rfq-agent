# Electronics RFQ Agent

**Your sales engineers are spending 2-4 hours turning RFQ documents into quotes. This does it in 30 seconds.**

Electronics RFQ Agent is a Python library that reads RFQ documents (PDF, Excel, Word), looks up every line item against your ERP catalog, and outputs a draft quote. It connects to SAP, Epicor, Oracle, and Microsoft Dynamics through MCP servers, so it works with Claude, GPT-4, or any agent framework that speaks MCP.

```bash
erfa quote rfq.xlsx --mock
```

[![CI](https://github.com/RudrenduPaul/electronics-rfq-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/RudrenduPaul/electronics-rfq-agent/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/electronics-rfq-agent.svg)](https://badge.fury.io/py/electronics-rfq-agent)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/electronics-rfq-agent/badge)](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/electronics-rfq-agent)

---

## Install

```bash
pip install electronics-rfq-agent
# or
uv add electronics-rfq-agent
```

## The problem this solves

We were working with electronics distributors who had 3-5 sales engineers spending most of their day on quote entry. Every tool we found was either tied to one specific ERP or required a 6-month integration project. We wanted something that worked with what distributors already had, could be self-hosted (quote data is sensitive), and was actually extensible.

The MCP architecture means adding a new ERP is writing one file. The parser handles the document formats distributors actually send: hand-filled PDFs, multi-sheet Excel files, and the occasional scanned table.

## Quickstart

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

Connect to a real ERP:

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

## How it differs from the alternatives

| | Electronics RFQ Agent | Manual process | SAP Joule | Generic AI (ChatGPT) |
|---|---|---|---|---|
| Multi-ERP support | SAP + Epicor + Oracle + Dynamics | N/A | SAP only | No ERP access |
| Quote time (50 lines) | ~15s | 2-4 hours | N/A | N/A |
| Self-hostable | Yes | N/A | No | No |
| Data stays local | Yes | Yes | No | No |
| Open source | MIT | N/A | No | No |
| Dev mock backend | Yes | N/A | No | N/A |
| MCP compatible | Yes | N/A | No | No |

## ERP support

| ERP | Status | Connection | Docs |
|---|---|---|---|
| Epicor Kinetic | Supported | REST API | [Setup](docs/erp-setup/epicor.md) |
| SAP ECC / S/4HANA | Beta (manual install) | PyRFC (BAPI) | [Setup](docs/erp-setup/sap.md) |
| Oracle Cloud SCM | Supported | REST API | [Setup](docs/erp-setup/oracle.md) |
| Microsoft Dynamics 365 | Supported | Graph API | [Setup](docs/erp-setup/dynamics.md) |
| Mock backend | Built-in | In-memory | No config needed |

> **SAP note:** pyrfc requires the SAP NetWeaver RFC Library, which is not on PyPI and must be downloaded manually from SAP's support portal (S-user required). See [docs/erp-setup/sap.md](docs/erp-setup/sap.md) for step-by-step instructions.

## Benchmarks

Measured using the in-memory mock backend (200 realistic parts, no ERP system required). Run it yourself:

```bash
git clone https://github.com/RudrenduPaul/electronics-rfq-agent
cd electronics-rfq-agent
uv run python benchmarks/run.py
```

**ERP lookup latency (100 individual lookups, mock backend):**

| P50 | P99 | Mean |
|---|---|---|
| 0.00025ms | 0.0023ms | 0.00032ms |

**Quote assembly time by RFQ size (parser mocked, no Anthropic API call):**

| RFQ size | Assembly time |
|---|---|
| 10 lines | 0.004s |
| 25 lines | 0.001s |
| 50 lines | 0.001s |

*These numbers cover ERP lookup and quote assembly only — the RFQ parser is mocked and no Anthropic API call is made. In production, AI document parsing adds 5–15s per document and real ERP lookups add 100–500ms per line (parallelised at up to `max_concurrent=10`), giving a realistic total of ~15s for a 50-line RFQ. Manual baseline: 2–4 hours.*

## Integration matrix

Electronics RFQ Agent works with any agent framework that supports MCP:

| Framework | Install | Example |
|---|---|---|
| Claude (built-in) | `pip install electronics-rfq-agent` | [01-basic-quote](examples/01-basic-quote/) |
| LangGraph | `pip install 'electronics-rfq-agent[langgraph]'` | [04-langgraph-agent](examples/04-langgraph-agent/) |
| OpenAI Agents SDK | `pip install electronics-rfq-agent[agents]` | [05-openai-agents](examples/05-openai-agents/) |
| CrewAI | `pip install electronics-rfq-agent[crewai]` | — |

## Try it in Docker

```bash
git clone https://github.com/RudrenduPaul/electronics-rfq-agent
cd electronics-rfq-agent
cp .env.example .env   # add your ERP credentials and Anthropic API key
docker compose up -d
```

Your quote data never leaves your environment.

## Security

- **Supply chain:** SLSA Level 2 via GitHub Actions provenance. All releases signed with Sigstore. SBOM attached to every GitHub Release.
- **Vulnerability scanning:** Trivy scans on every CI run (HIGH/CRITICAL only, exit on unfixed). CodeQL static analysis on every push.
- **Dependency pinning:** Dependabot keeps all GitHub Actions and Python dependencies current.
- **Disclosure:** [SECURITY.md](SECURITY.md) — report vulnerabilities privately via GitHub Security Advisories.

## Contributing

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR
- Good first issues are labeled in GitHub
- ERP adapters live in `electronics_rfq_agent/mcp/` — each is a self-contained file with no changes to core
- All PRs require 80% test coverage

GitHub Discussions: [Ask questions, share ideas](https://github.com/RudrenduPaul/electronics-rfq-agent/discussions)
Discord: coming soon

Full docs: [Getting started](docs/getting-started.md) · [API reference](docs/api.md) · [ERP setup: Epicor](docs/erp-setup/epicor.md) · [SAP](docs/erp-setup/sap.md) · [Oracle](docs/erp-setup/oracle.md) · [Dynamics 365](docs/erp-setup/dynamics.md) · [Changelog](CHANGELOG.md)

MIT. Contributions welcome.

## Cite this work

If you use Electronics RFQ Agent in research, please cite:

```bibtex
@software{paul2026electronicsrfq,
  author = {Paul, Rudrendu and Nandy, Sourav},
  title = {Electronics RFQ Agent: AI Quoting Agent for Electronics Distributors},
  year = {2026},
  url = {https://github.com/RudrenduPaul/electronics-rfq-agent},
  license = {MIT}
}
```

---

*Built by Rudrendu Paul and Sourav Nandy*
