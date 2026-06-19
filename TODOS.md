# TODOS

Engineering review findings — 2026-06-19.
All items below passed the scope challenge (fix root cause, no scope creep).

---

## Priority 1 — Correctness / Credibility (ship before any outreach)

- [ ] **A1: Fix `run_sync()` for existing event loops**
  Files: `src/openquote/agent.py:89`
  Fix: detect running loop, use `nest_asyncio` or `anyio.from_thread`. Add `nest_asyncio` to optional dev deps.
  Chosen: nest_asyncio / anyio.from_thread approach

- [ ] **A2: Add semaphore to `asyncio.gather()` in `agent.py:62`**
  Files: `src/openquote/agent.py:62`, `src/openquote/agent.py:29` (constructor)
  Fix: `asyncio.Semaphore(max_concurrent=10)` configurable via `QuoteAgent(max_concurrent=10)`.

- [ ] **A3: Wrap SAP PyRFC calls in `asyncio.to_thread()`**
  Files: `src/openquote/mcp/sap.py` — all async methods
  Fix: each BAPI call wrapped in `asyncio.to_thread()` to not block the event loop.

- [ ] **A4: Guard `response.content[0].text` in `parser.py:88` and `parser.py:186`**
  Files: `src/openquote/parser.py`
  Fix: add `RFQParseError` exception class; guard both call sites with explicit check + raise.

- [ ] **Q3: Refactor SAP get_price() double-BAPI-call**
  Files: `src/openquote/mcp/sap.py:~140`
  Fix: get_price() should not re-call get_part(). Accept the already-fetched part price, apply volume discounts locally.

- [ ] **Q4: Distinguish SAP connection errors from part-not-found**
  Files: `src/openquote/mcp/sap.py:105-106`
  Fix: catch pyrfc exception types separately; re-raise connection/auth as `ERPConnectionError`. Add `ERPConnectionError` to `__init__.py` exports.

- [ ] **P5: Fix Excel multi-sheet parsing**
  Files: `src/openquote/parser.py:95`
  Fix: iterate `wb.worksheets`, run `_find_header_row()` on each, parse the first with a valid header.

- [ ] **README: Fix SAP "Supported" claim**
  Files: `README.md:58`
  Fix: Change to `Beta (manual install required)` + link to `docs/erp-setup/sap.md`. Add install instructions in sap.md covering NW RFC Library download.

---

## Priority 2 — Code Quality / Honesty

- [ ] **Q1: Delete dead `_lookup_part()` method**
  Files: `src/openquote/agent.py:129-130`
  Fix: remove the 2-line method entirely (never called, duplicates `_lookup_line` logic).

- [ ] **Q2: Fix `datetime.utcnow` deprecation**
  Files: `src/openquote/models.py:67`
  Fix: `datetime.now(timezone.utc)` — eliminates 14 test DeprecationWarnings.

- [ ] **Q3: Wire `ERPConfig` to connectors via `from_config()` classmethods**
  Files: `src/openquote/mcp/epicor.py`, `sap.py`, `oracle.py`, `dynamics.py`
  Fix: add `@classmethod from_config(cls, cfg: ERPConfig)` to each connector. No constructor changes needed.

- [ ] **Q4b: Rename `bench_parse_accuracy()` and add real parse accuracy benchmark**
  Files: `benchmarks/run.py`
  Fix: rename to `bench_json_deserialize()`; add `bench_parse_accuracy()` that mocks the Anthropic call and validates line item extraction from a fixture RFQ string.

- [ ] **README: Fix benchmark "1750x faster" framing**
  Files: `README.md:41-45`
  Fix: clarify the comparison is mock-backend ERP lookup time vs. total manual time. The numbers are honest; the column header "vs. manual" next to `0.04ms` ERP lookups creates a false implied comparison. Reframe as "Total time per quote" vs "manual baseline: 2-4h."

---

## Priority 3 — Strategic / UX

- [ ] **S1: Add CLI entry point: `openquote quote rfq.xlsx`**
  Files: `src/openquote/cli.py` (new), `pyproject.toml`
  Fix: Typer CLI, `[project.scripts] openquote = "openquote.cli:app"`. Single command: quote, print summary, exit.

---

## Tests to add (complement to code fixes)

- [ ] **T1: OAuth2 tests for Dynamics and Oracle**
  Files: `tests/integration/test_erp_http.py`
  Fix: respx-mocked tests for `_ensure_token()`: (1) token fetched and cached, (2) token reused on second call, (3) 401 raises.

- [ ] **T2: Mock-pyrfc tests for SAP live paths**
  Files: `tests/unit/test_sap_mock.py` (new)
  Fix: `sys.modules` patch for pyrfc, test `search_parts()`, `get_part()`, `check_inventory()`, `get_price()` with realistic BAPI response dicts.

- [ ] **T3: Tests for parser edge cases**
  Files: `tests/unit/test_parser_file.py`
  Fix: `ws is None` path; qty ValueError path; Word table with no part_number column; multi-sheet Excel.

- [ ] **T4: Test `run_sync()` under running event loop**
  Files: `tests/unit/test_agent.py`
  Fix: once A1 is implemented, add a test that calls `run_sync()` from inside an `asyncio.run()` context.

---

## Deferred (not blocking v0.1.0)

- Submit to `awesome-mcp-servers`
- Post Show HN
- Tag first 20 GitHub issues as `good first issue`
- Enable GitHub Discussions
- Ship LangGraph and OpenAI Agents SDK integrations
- Write `docs/getting-started.md` full tutorial
- Discord server
- Web UI / file drop (v0.2 target)
