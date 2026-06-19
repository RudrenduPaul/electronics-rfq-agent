# TODOS

Engineering review findings — 2026-06-19.
All items below passed the scope challenge (fix root cause, no scope creep).

---

## Priority 1 — Correctness / Credibility ✅ All done (0.1.1)

- [x] **A1: Fix `run_sync()` for existing event loops**
  Files: `src/openquote/agent.py:89`
  Fix: detect running loop, use `nest_asyncio`. Added `nest_asyncio` to core deps.

- [x] **A2: Add semaphore to `asyncio.gather()` in `agent.py:62`**
  Files: `src/openquote/agent.py:62`, `src/openquote/agent.py:29` (constructor)
  Fix: `asyncio.Semaphore(max_concurrent=10)` configurable via `QuoteAgent(max_concurrent=10)`.

- [x] **A3: Wrap SAP PyRFC calls in `asyncio.to_thread()`**
  Files: `src/openquote/mcp/sap.py` — all async methods
  Fix: each BAPI call wrapped in `asyncio.to_thread()`.

- [x] **A4: Guard `response.content[0].text` in `parser.py:88` and `parser.py:186`**
  Files: `src/openquote/parser.py`
  Fix: `RFQParseError` exception class; both call sites guarded with explicit check + raise.

- [x] **Q3: Refactor SAP get_price() double-BAPI-call**
  Files: `src/openquote/mcp/sap.py:~140`
  Fix: get_price() now uses direct BAPI call, does not re-call get_part().

- [x] **Q4: Distinguish SAP connection errors from part-not-found**
  Files: `src/openquote/mcp/sap.py:105-106`
  Fix: `ERPConnectionError` raised for connection/auth failures; `None` returned for part-not-found.

- [x] **P5: Fix Excel multi-sheet parsing**
  Files: `src/openquote/parser.py:95`
  Fix: iterates `wb.worksheets`, runs `_find_header_row()` on each, parses first valid sheet.

- [x] **README: Fix SAP "Supported" claim**
  Files: `README.md:58`
  Fix: `Beta (manual install required)` + SAP NW RFC Library note.

---

## Priority 2 — Code Quality / Honesty ✅ All done (0.1.1)

- [x] **Q1: Delete dead `_lookup_part()` method**
  Files: `src/openquote/agent.py`
  Fix: removed.

- [x] **Q2: Fix `datetime.utcnow` deprecation**
  Files: `src/openquote/models.py`
  Fix: `datetime.now(timezone.utc)`.

- [x] **Q3: Wire `ERPConfig` to connectors via `from_config()` classmethods**
  Files: `src/openquote/mcp/epicor.py`, `sap.py`, `oracle.py`, `dynamics.py`
  Fix: `@classmethod from_config(cls, cfg: ERPConfig)` on all four connectors.

- [x] **Q4b: Rename `bench_parse_accuracy()` and add real parse accuracy benchmark**
  Files: `benchmarks/run.py`
  Fix: renamed to `bench_json_deserialize()` with honest docstring.

- [x] **README: Fix benchmark framing**
  Files: `README.md`
  Fix: clarified benchmark measures ERP lookup + assembly only; AI parsing time noted separately.

---

## Priority 3 — Strategic / UX ✅ Done (0.1.1)

- [x] **S1: Add CLI entry point: `openquote quote rfq.xlsx`**
  Files: `src/openquote/cli.py`, `pyproject.toml`
  Fix: Typer CLI. `openquote quote rfq.xlsx [--mock] [--margin 0.15]`.

---

## Tests ✅ All done (0.1.1)

- [x] **T1: OAuth2 tests for Dynamics and Oracle**
  Files: `tests/integration/test_erp_http.py`
  Fix: respx-mocked `_ensure_token()` tests: fetch, cache, 401 raises.

- [x] **T2: Mock-pyrfc tests for SAP live paths**
  Files: `tests/unit/test_sap_mock_pyrfc.py`
  Fix: `sys.modules` patch, tests for `search_parts`, `get_part`, `check_inventory`, `get_price`, `ERPConnectionError`.

- [x] **T3: Tests for parser edge cases**
  Files: `tests/unit/test_parser_file.py`
  Fix: multi-sheet Excel, `RFQParseError` on empty API response.

- [x] **T4: Test `run_sync()` under running event loop**
  Files: `tests/unit/test_agent.py`
  Fix: `test_run_sync_safe_inside_running_event_loop` — calls `run_sync()` from inside `asyncio.run()`.

---

## Community / outreach

- [ ] Submit to `awesome-mcp-servers` — tracked in #9, draft PR text in that issue
- [ ] Post Show HN — draft written (post Tue–Thu 9–11am ET, reply to all early comments)
- [x] Enable GitHub Discussions — done
- [x] Create seeding issues tagged `good first issue` — issues #4 (CLI tests), #5 (docs), #6 (from_config tests), #7 (LangGraph), #8 (OpenAI Agents SDK)

## Engineering (next sprint)

- [ ] CLI tests — issue #4 (`tests/unit/test_cli.py`, Typer test runner)
- [x] LangGraph example — issue #7 (`examples/04-langgraph-agent/`) ✅
- [x] OpenAI Agents SDK example — issue #8 (`examples/05-openai-agents/`) ✅
- [ ] docs/getting-started.md full ERP walkthrough — issue #5

## v0.2 (deferred)

- [ ] Web UI / file drop for sales engineers
- [ ] Discord server
