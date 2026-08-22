<div align="center">

# Electronics RFQ Agent

**Your sales engineers are spending 2-4 hours turning RFQ documents into quotes. This does it in seconds.**

Electronics RFQ Agent is a Python library and CLI that reads RFQ documents (PDF, Excel, Word), looks up every line item against your ERP catalog, and outputs a draft quote. It connects to SAP, Epicor, Oracle, and Microsoft Dynamics through MCP servers, so it works with Claude, GPT-4, or any agent framework that speaks MCP.

[![CI](https://github.com/RudrenduPaul/electronics-rfq-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/RudrenduPaul/electronics-rfq-agent/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/electronics-rfq-agent-cli.svg)](https://badge.fury.io/py/electronics-rfq-agent-cli)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/electronics-rfq-agent/badge)](https://api.securityscorecards.dev/projects/github.com/RudrenduPaul/electronics-rfq-agent)

</div>

---

![Terminal recording showing `erfa --help` listing the quote and audit subcommands, then `erfa audit` printing a full fill-rate report for a five-line RFQ against the mock ERP backend](docs/demo.gif)

## Table of contents

- [Install](#install)
- [The problem this solves](#the-problem-this-solves)
- [Quickstart](#quickstart)
- [Commands](#commands)
- [API reference](#api-reference)
- [How it differs from the alternatives](#how-it-differs-from-the-alternatives)
- [ERP support](#erp-support)
- [Benchmarks](#benchmarks)
- [Integration matrix](#integration-matrix)
- [Try it in Docker](#try-it-in-docker)
- [Security](#security)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

## Install

```bash
pip install electronics-rfq-agent-cli
# or
uv add electronics-rfq-agent-cli
```

To install from source instead:

```bash
git clone https://github.com/RudrenduPaul/electronics-rfq-agent
cd electronics-rfq-agent
pip install -e .
# or, with uv:
uv sync
```

Parsing RFQ documents (PDF, Excel, Word) calls the Anthropic API, so set `ANTHROPIC_API_KEY` before running anything that touches a real document:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

You don't need this key to run `erfa audit` against an existing quote file, or to explore the CLI with `--help`. Only document parsing calls out to Claude.

## The problem this solves

We were working with electronics distributors who had 3-5 sales engineers spending most of their day on quote entry. Every tool we found was either tied to one specific ERP or required a 6-month integration project. We wanted something that worked with what distributors already had, could be self-hosted (quote data is sensitive), and was actually extensible.

The MCP architecture means adding a new ERP is writing one file. The parser handles the document formats distributors actually send: hand-filled PDFs, multi-sheet Excel files, and the occasional scanned table.

## Quickstart

No ERP system required to try it out; the mock backend ships with 200 realistic electronics parts. You do need `ANTHROPIC_API_KEY` set, since parsing the RFQ document is still a real Claude call:

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

## Commands

`erfa` ships two subcommands. Every flag below is pulled straight from `erfa --help`.

| Command | Arguments | Flags | What it does |
|---|---|---|---|
| `erfa quote` | `rfq` (path, required) | `--mock`, `--margin <float>` (default `0.15`), `--output/-o <path>` | Parses an RFQ file and prints a draft quote. Needs `ANTHROPIC_API_KEY`; parsing always goes through Claude, `--mock` only swaps the ERP backend. |
| `erfa audit` | `quote_file` (path, required) | none | Prints a full audit report (found / substituted / not found, fill rate) for a quote JSON file saved with `erfa quote --output`. Reads a local file only, no API key needed. |

```bash
# Generate a quote from an RFQ file against the mock ERP
export ANTHROPIC_API_KEY="sk-ant-..."
erfa quote rfq.xlsx --mock

# Save the quote as JSON for later inspection
erfa quote rfq.xlsx --mock --output quote.json

# Audit what happened: what was found, substituted, or missing and why
erfa audit quote.json
```

**Audit output example** (real output from `erfa audit docs/example-quote.json`, generated by running the mock ERP's pricing logic against the sample RFQ in `tests/fixtures/sample_rfq.txt`):

```
Audit Report - Quote df9fd083
RFQ Source : tests/fixtures/sample_rfq.txt
Lines      : 5
Total      : USD 64.04

FOUND (4)
------------------------------------------------------------
  L  1  RES-0402-10K-1PCT               qty=1000  unit=0.0064  ext=6.40
  L  2  CAP-100NF-50V-X7R-0402          qty=500  unit=0.0104  ext=5.20
  L  3  IC-LM358-SOIC8                  qty=50  unit=0.7101  ext=35.50
  L  4  XTAL-16MHZ-SMD                  qty=25  unit=0.6774  ext=16.94

NOT FOUND (1)
------------------------------------------------------------
  L  5  MOSFET-NMOS-20V-3A-SOT23        Part 'MOSFET-NMOS-20V-3A-SOT23' not found in ERP catalog

Fill rate: 80%  (4 found / 0 substituted / 1 not found)
```

> **Zero-price parts:** If a part exists in the ERP catalog but has a unit price of $0.00, the agent quotes $0 rather than skipping the line, and sets `line.notes` to a message flagging the zero price so you catch it before quoting the customer. Check `line.notes` for any found or substituted line before sending a quote out.

## API reference

The full reference lives in [docs/api.md](docs/api.md): every `QuoteAgent` parameter, the shared ERP connector interface, `Quote`/`QuoteLineItem` field-by-field, and the exception hierarchy. The exports below are what `from electronics_rfq_agent import ...` actually gives you, grepped from `src/electronics_rfq_agent/__init__.py`, not guessed:

| Export | What it is |
|---|---|
| `QuoteAgent` | Orchestrates parsing + ERP lookup + quote assembly. `run()` (async) and `run_sync()`. |
| `EpicorMCP`, `SAPMCP`, `OracleMCP`, `DynamicsMCP` | ERP connectors, one per supported system. All implement the same `search_parts` / `get_part` / `get_price` / `check_inventory` interface. |
| `MockERP` (from `electronics_rfq_agent.mcp.mock`) | In-memory backend with 200 realistic parts. No credentials, no network. |
| `Quote`, `QuoteLineItem`, `RFQLineItem`, `ERPPartResult`, `ERPConfig` | Pydantic v2 models for the quote, each line, the parsed RFQ line, raw ERP data, and connector config. |
| `ERPConnectionError`, `RFQParseError` | The two exceptions `QuoteAgent` can raise: connection/auth failures and unparseable documents. Per-line ERP failures don't raise; they land in `line.notes` instead. |
| `TelemetryCollector`, `TelemetryEvent` | Opt-in local telemetry (`telemetry=True` on `QuoteAgent`), counts and timings only, no RFQ content. |

## How it differs from the alternatives

| | Electronics RFQ Agent | Manual process | SAP Joule | Generic AI (ChatGPT) |
|---|---|---|---|---|
| Multi-ERP support | SAP + Epicor + Oracle + Dynamics | N/A | SAP-centric (Joule Studio can reach non-SAP sources via SAP Integration Suite) | No ERP access |
| Quote time (50 lines) | ~15s | 2-4 hours | Not publicly documented | N/A |
| Self-hostable | Yes | N/A | No (SAP BTP cloud service) | No |
| Data stays local | Yes | Yes | No | No |
| Open source | MIT | N/A | No | No |
| Dev mock backend | Yes | N/A | Not publicly documented | N/A |
| MCP compatible | Yes | N/A | Not publicly documented | No |

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

*These numbers cover ERP lookup and quote assembly only. The RFQ parser is mocked and no Anthropic API call is made. In production, AI document parsing adds 5-15s per document and real ERP lookups add 100-500ms per line (parallelised at up to `max_concurrent=10`), giving a realistic total of ~15s for a 50-line RFQ. Manual baseline: 2-4 hours.*

## Integration matrix

Electronics RFQ Agent works with any agent framework that supports MCP:

| Framework | Install | Example |
|---|---|---|
| Claude (built-in) | `pip install electronics-rfq-agent-cli` | [01-basic-quote](examples/01-basic-quote/) |
| LangGraph | `pip install 'electronics-rfq-agent-cli[langgraph]'` | [04-langgraph-agent](examples/04-langgraph-agent/) |
| OpenAI Agents SDK | `pip install electronics-rfq-agent-cli[agents]` | [05-openai-agents](examples/05-openai-agents/) |
| CrewAI | `pip install electronics-rfq-agent-cli[crewai]` | n/a |

## Try it in Docker

```bash
git clone https://github.com/RudrenduPaul/electronics-rfq-agent
cd electronics-rfq-agent
cp .env.example .env   # add your ERP credentials and Anthropic API key
docker compose up -d
```

Your quote data never leaves your environment.

## Security

- **Vulnerability scanning:** Trivy scans every CI run (HIGH/CRITICAL severity, build fails on unfixed findings), results uploaded to the GitHub Security tab.
- **Release signing:** the release workflow signs built wheels and sdists with Sigstore and attaches a CycloneDX SBOM to each GitHub Release once a version is tagged.
- **Dependency pinning:** Dependabot keeps GitHub Actions and Python dependencies current (weekly patch updates, monthly Actions updates).
- **Disclosure:** [SECURITY.md](SECURITY.md). Report vulnerabilities privately via email or GitHub Security Advisories; 48-hour acknowledgement, 90-day responsible disclosure.

## FAQ

**What does Electronics RFQ Agent actually do?**
It takes an RFQ document (PDF, Excel, or Word) from a customer, extracts every line item with Claude, looks each part up against your ERP catalog through an MCP connector, and returns a priced draft quote with margin applied. A sales engineer reviews and sends it instead of building it from scratch.

**Is it production ready?**
It's Beta (v0.2.x). The core library, Epicor, Oracle, and Dynamics connectors are covered by CI (lint, mypy strict, pytest with an 80% coverage gate, Trivy scanning) across Python 3.10-3.12. SAP support is explicitly marked Beta and requires a manual install step (the SAP NetWeaver RFC Library isn't on PyPI).

**Do I need an ERP system to try it?**
No. `MockERP` ships with 200 realistic electronics parts and applies quantity-based pricing tiers, so you can run the full parse-lookup-quote flow with zero ERP credentials. You do still need `ANTHROPIC_API_KEY`, since document parsing is a real Claude call. Only `erfa audit` (reading an already-saved quote file) works with no key at all.

**How is this different from asking ChatGPT to read the RFQ?**
A generic chat model can read a document and even guess at prices, but it has no connection to your actual ERP catalog, inventory, or contract pricing, so it's making numbers up. Electronics RFQ Agent looks up every line item against your real catalog data and only quotes what's actually in stock at the actual cost price plus your configured margin.

**How is this different from SAP Joule?**
Joule is SAP's proprietary AI assistant suite, built into SAP's cloud platform (SAP BTP) and centered on SAP data. Electronics RFQ Agent is MIT-licensed, self-hosted, and works with SAP, Epicor, Oracle, and Dynamics through the same MCP interface. Your quote data never has to leave your environment, and you're not tied to one ERP vendor.

**Which document formats does it parse?**
PDF (including scanned tables, via Claude's vision capability), Excel (`.xlsx`/`.xls`, searches every worksheet for the line-item header row), and Word (`.docx`, reads all tables). Plain text RFQs work too.

**What happens to a line item that isn't in the ERP catalog?**
It's marked `not_found` with a note explaining why (rather than silently dropped or guessed at), and it's excluded from the quote total. Run `erfa audit` on the saved quote JSON to see exactly which lines were found, substituted, or missing, and why.

**Can I use this commercially?**
Yes. It's MIT licensed, so you can use it, modify it, and ship it commercially with no royalty and no obligation to open-source your changes. Attribution via the license file is all that's required.

**Is my RFQ and pricing data sent anywhere besides Anthropic?**
Only the RFQ document content goes to the Anthropic API for parsing. ERP lookups go directly from your machine to your ERP system over the connector you configure: there's no intermediary service, and nothing is stored outside your own environment unless you choose to persist quote JSON yourself.

**Is this published to PyPI?**
Yes, as `electronics-rfq-agent-cli` (`pip install electronics-rfq-agent-cli`). The publish pipeline (build, Sigstore signing, SBOM, trusted-publisher upload) lives in `.github/workflows/release.yml` and runs on every `v*` tag push. The Python import path (`electronics_rfq_agent`) and the `erfa` CLI command are unchanged; only the registry-facing package name carries the `-cli` suffix, matching this maintainer's naming convention for CLI tools.

## Contributing

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR
- Good first issues are labeled in GitHub
- ERP adapters live in `electronics_rfq_agent/mcp/`; each is a self-contained file with no changes to core
- All PRs require 80% test coverage

GitHub Discussions: [Ask questions, share ideas](https://github.com/RudrenduPaul/electronics-rfq-agent/discussions)
Discord: coming soon

Full docs: [Getting started](docs/getting-started.md) · [API reference](docs/api.md) · [ERP setup: Epicor](docs/erp-setup/epicor.md) · [SAP](docs/erp-setup/sap.md) · [Oracle](docs/erp-setup/oracle.md) · [Dynamics 365](docs/erp-setup/dynamics.md) · [Changelog](CHANGELOG.md)

MIT. Contributions welcome.

## License

MIT. See [LICENSE](LICENSE).

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
