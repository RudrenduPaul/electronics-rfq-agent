# Contributing to Electronics RFQ Agent

Thanks for considering a contribution. This document covers everything you need to go from zero to a merged PR.

## The fastest path to contribution

1. Clone the repo and run `make dev-setup` or `uv sync --extra dev && pre-commit install`
2. Pick an issue labeled `good first issue`
3. Open a draft PR early — we review drafts and can help you avoid wasted work
4. When tests pass and you've added/updated tests for your change, mark ready for review

We aim to review PRs within 72 hours (weekdays). If you've waited 5 days with no response, comment on the PR and @mention a maintainer.

## Development setup

```bash
git clone https://github.com/RudrenduPaul/electronics-rfq-agent
cd electronics-rfq-agent
pip install uv
uv sync --extra dev
pre-commit install
uv run pytest tests/ -q       # should pass on a clean clone
```

To run against the mock ERP backend (no real ERP needed):

```bash
ERFA_USE_MOCK=true uv run python examples/01-basic-quote/basic_quote.py
```

## Standards

Before every PR, run:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ --strict
uv run pytest tests/ --cov=src/ --cov-fail-under=80
```

## What makes a PR merge quickly

- Tests added for every behavior change (we will ask for them if missing)
- CHANGELOG entry for any user-facing change
- Docstring updated if you changed a public API
- No unrelated refactors — one thing per PR

## What we will not merge

- PRs that break existing tests without a documented reason
- Changes to public API without a deprecation path
- LLM-generated code submitted without running and validating the output
- Integration tests that use mocks instead of the official mock backends in `src/electronics_rfq_agent/mcp/mock/`

## Adding a new ERP integration

1. Add a new file `src/electronics_rfq_agent/mcp/<erp_name>.py`
2. Implement all methods from `ERPMCPServer` in `src/electronics_rfq_agent/mcp/base.py`
3. Add a mock backend in `src/electronics_rfq_agent/mcp/mock/`
4. Add integration tests in `tests/integration/test_<erp_name>_mock.py`
5. Add setup docs in `docs/erp-setup/<erp_name>.md`
6. Export from `src/electronics_rfq_agent/__init__.py`

## Benchmark PRs

If your contribution changes performance-sensitive code, include benchmark output in the PR description:

```bash
uv run python benchmarks/run.py
```

## Response SLAs

- Bug reports: acknowledge within 24 hours (weekdays)
- Feature requests: triage label within 72 hours
- PRs: first review within 72 hours
- Security reports: acknowledge within 48 hours (see SECURITY.md)

## Community

Discord: coming soon
GitHub Discussions: [Ask questions, share ideas](https://github.com/RudrenduPaul/electronics-rfq-agent/discussions)
