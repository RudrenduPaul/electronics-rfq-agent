# TODOS

Engineering review findings — 2026-06-19.
All items below passed the scope challenge (fix root cause, no scope creep).

---

## Priority 1 — Correctness / Credibility ✅ All done (0.1.1)

- [x] **A1: Fix `run_sync()` for existing event loops**
  Files: `src/electronics_rfq_agent/agent.py:89`
  Fix: detect running loop, use `nest_asyncio`. Added `nest_asyncio` to core deps.

- [x] **A2: Add semaphore to `asyncio.gather()` in `agent.py:62`**
  Files: `src/electronics_rfq_agent/agent.py:62`, `src/electronics_rfq_agent/agent.py:29` (constructor)
  Fix: `asyncio.Semaphore(max_concurrent=10)` configurable via `QuoteAgent(max_concurrent=10)`.

- [x] **A3: Wrap SAP PyRFC calls in `asyncio.to_thread()`**
  Files: `src/electronics_rfq_agent/mcp/sap.py` — all async methods
  Fix: each BAPI call wrapped in `asyncio.to_thread()`.

- [x] **A4: Guard `response.content[0].text` in `parser.py:88` and `parser.py:186`**
  Files: `src/electronics_rfq_agent/parser.py`
  Fix: `RFQParseError` exception class; both call sites guarded with explicit check + raise.

- [x] **Q3: Refactor SAP get_price() double-BAPI-call**
  Files: `src/electronics_rfq_agent/mcp/sap.py:~140`
  Fix: get_price() now uses direct BAPI call, does not re-call get_part().

- [x] **Q4: Distinguish SAP connection errors from part-not-found**
  Files: `src/electronics_rfq_agent/mcp/sap.py:105-106`
  Fix: `ERPConnectionError` raised for connection/auth failures; `None` returned for part-not-found.

- [x] **P5: Fix Excel multi-sheet parsing**
  Files: `src/electronics_rfq_agent/parser.py:95`
  Fix: iterates `wb.worksheets`, runs `_find_header_row()` on each, parses first valid sheet.

- [x] **README: Fix SAP "Supported" claim**
  Files: `README.md:58`
  Fix: `Beta (manual install required)` + SAP NW RFC Library note.

---

## Priority 2 — Code Quality / Honesty ✅ All done (0.1.1)

- [x] **Q1: Delete dead `_lookup_part()` method**
  Files: `src/electronics_rfq_agent/agent.py`
  Fix: removed.

- [x] **Q2: Fix `datetime.utcnow` deprecation**
  Files: `src/electronics_rfq_agent/models.py`
  Fix: `datetime.now(timezone.utc)`.

- [x] **Q3: Wire `ERPConfig` to connectors via `from_config()` classmethods**
  Files: `src/electronics_rfq_agent/mcp/epicor.py`, `sap.py`, `oracle.py`, `dynamics.py`
  Fix: `@classmethod from_config(cls, cfg: ERPConfig)` on all four connectors.

- [x] **Q4b: Rename `bench_parse_accuracy()` and add real parse accuracy benchmark**
  Files: `benchmarks/run.py`
  Fix: renamed to `bench_json_deserialize()` with honest docstring.

- [x] **README: Fix benchmark framing**
  Files: `README.md`
  Fix: clarified benchmark measures ERP lookup + assembly only; AI parsing time noted separately.

---

## Priority 3 — Strategic / UX ✅ Done (0.1.1)

- [x] **S1: Add CLI entry point: `erfa quote rfq.xlsx`**
  Files: `src/electronics_rfq_agent/cli.py`, `pyproject.toml`
  Fix: Typer CLI. `erfa quote rfq.xlsx [--mock] [--margin 0.15]`.

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

- [x] CLI tests — issue #4 (`tests/unit/test_cli.py`, 13 tests, cli.py at 98%) ✅
- [x] LangGraph example — issue #7 (`examples/04-langgraph-agent/`) ✅
- [x] OpenAI Agents SDK example — issue #8 (`examples/05-openai-agents/`) ✅
- [x] docs/getting-started.md full ERP walkthrough — Oracle, Dynamics, ERPConfig.from_config(), troubleshooting ✅
- [x] Extras-compat CI job — langchain + agents imports verified on Python 3.12 ✅
- [x] CLI bug fix — single-command Typer routing via @app.callback() ✅

## Engineering (session 2026-06-19) ✅ All done

- [x] **B1: Extract shared OAuth2 helper to eliminate DRY violation**
  Files: `src/electronics_rfq_agent/mcp/_oauth.py` (new), `oracle.py`, `dynamics.py`
  Fix: `fetch_client_credentials_token()` shared helper; Oracle + Dynamics each keep own token state.
  Commit: d5280ed

- [x] **B2: Deduplicate ERP lookups for repeated part numbers per run**
  Files: `src/electronics_rfq_agent/agent.py:68-83`
  Fix: `asyncio.Task` cache keyed on `(part_number, quantity)`; duplicate lines share one ERP call.
  Commit: c43157a

- [x] **B3: Prevent concurrent token refreshes; validate tenant_id UUID format**
  Files: `src/electronics_rfq_agent/mcp/oracle.py`, `dynamics.py`
  Fix: `asyncio.Lock` per connector instance guards the token check-and-refresh; `DynamicsMCP.__init__`
  validates `tenant_id` against UUID regex at construction time.
  Commit: a990b61

---

## v0.2 (deferred)

- [ ] Web UI / file drop for sales engineers
- [ ] Discord server
