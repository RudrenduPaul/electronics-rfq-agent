# Changelog

All notable changes to openquote are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- `docker-compose.yml` for self-hosted deployment (no ERP system required with `OPENQUOTE_USE_MOCK=true`)
- CI pipeline: lint (ruff) + type-check (mypy strict) + tests (pytest, 80% coverage) + security (trivy) across Python 3.10/3.11/3.12
- Reproducible benchmarks: `python benchmarks/run.py` completes in under 5 minutes using mock backend
- OpenSSF Scorecard workflow (weekly)
- Dependabot configuration (weekly pip patches, monthly GitHub Actions updates)

[0.1.0]: https://github.com/RudrenduPaul/openquote-ai/releases/tag/v0.1.0
