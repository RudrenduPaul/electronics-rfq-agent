# Changelog

All notable changes to Electronics RFQ Agent are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-06-19

### Changed
- Package renamed from `openquote` to `electronics-rfq-agent`; CLI command renamed from `openquote` to `erfa`; all import paths changed from `openquote` to `electronics_rfq_agent`

### Fixed (18 items)

**Architecture**
- `run_sync()` now safe inside running event loops via `nest_asyncio` (Jupyter, FastAPI startup handlers)
- `asyncio.gather()` capped at `Semaphore(max_concurrent=10)` (configurable) to prevent flooding ERP endpoints on large RFQs
- SAP BAPI calls wrapped in `asyncio.to_thread()` — no longer block the event loop
- `RFQParser` guards `response.content[0].text` and raises `RFQParseError` on empty Anthropic API responses
- Excel parser searches all worksheets for the BOM header row (fixes multi-sheet RFQs)

**Code quality**
- `SAPMCP.get_price()` uses its own direct BAPI call — no longer calls `get_part()` first (was 2 BAPI calls where 1 was needed)
- SAP bare `except Exception` replaced with typed handling: `ERPConnectionError` for connection/auth failures, `None` for part-not-found
- Dead `_lookup_part()` method deleted from `QuoteAgent`
- `datetime.utcnow()` → `datetime.now(timezone.utc)` (eliminates deprecation warnings)
- All four ERP connectors gained `from_config(cfg: ERPConfig)` classmethod
- `bench_parse_accuracy()` renamed to `bench_json_deserialize()` with accurate docstring
- README benchmark table corrected: removed fabricated timing column; clarified what the benchmark actually measures
- SAP README status changed from `Supported` → `Beta (manual install)`

### Added
- `ERPConnectionError` — public exception for ERP connection/auth failures
- `RFQParseError` — public exception for unparseable RFQ documents
- CLI: `erfa quote rfq.xlsx [--mock] [--margin 0.15]` (Typer)
- 18 new tests: OAuth2 token flows (Dynamics, Oracle), mock-pyrfc SAP paths, parser edge cases, `run_sync()` under active event loop

## [0.1.0] - 2026-06-19

### Added
- `RFQParser`: parse RFQ documents from PDF, Excel (.xlsx/.xls), and Word (.docx) into structured `RFQLineItem` objects using Claude claude-sonnet-4-6
- `QuoteAgent`: orchestrate RFQ parsing + ERP lookup + draft quote generation in a single `run()` call
- `ERPMCPServer`: abstract base class for ERP MCP server implementations
- `EpicorMCP`: Epicor Kinetic REST API connector (`/api/v2/odata/` endpoints)
- `SAPMCP`: SAP ECC/S4HANA connector via PyRFC BAPI calls (graceful degradation if pyrfc not installed)
- `OracleMCP`: Oracle Cloud SCM REST API connector
- `DynamicsMCP`: Microsoft Dynamics 365 Sales Quote connector via Graph API
- `MockERP`: in-memory mock ERP backend with 200 realistic electronics parts for local development
- Pydantic v2 models: `RFQLineItem`, `ERPPartResult`, `QuoteLineItem`, `Quote`, `ERPConfig`
- `ERPConfig.__repr__` masks `api_key` and `password` fields
- `docker-compose.yml` for self-hosted deployment (no ERP system required with `ERFA_USE_MOCK=true`)
- CI pipeline: lint (ruff) + type-check (mypy strict) + tests (pytest, 80% coverage) + security (trivy) across Python 3.10/3.11/3.12
- Reproducible benchmarks: `python benchmarks/run.py` completes in under 5 minutes using mock backend
- OpenSSF Scorecard workflow (weekly)
- Dependabot configuration (weekly pip patches, monthly GitHub Actions updates)

[Unreleased]: https://github.com/RudrenduPaul/electronics-rfq-agent/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/RudrenduPaul/electronics-rfq-agent/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/RudrenduPaul/electronics-rfq-agent/releases/tag/v0.1.0
