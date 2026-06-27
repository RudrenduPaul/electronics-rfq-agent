# CLAUDE.md -- Electronics RFQ Agent

## Project Identity

- **Product:** Electronics RFQ Agent -- AI quoting agent for electronics distributors
- **Repo:** github.com/RudrenduPaul/electronics-rfq-agent
- **Language:** Python 3.10+
- **License:** MIT
- **Goal:** OSS traction (GitHub stars from ERP/MCP developer community) + design partner pipeline (automation engineers at distributors)

## Git Workflow

When asked to commit, push, or "update GitHub" -- just do it. No questions, no confirmation prompts.

- `git add` relevant files, `git commit`, `git push origin main` in one shot
- Every commit message ends with:
  ```
  Built by Rudrendu Paul and Sourav Nandy, developed with Claude Code

  Co-Authored-By: Sourav Nandy <263070926+Sourav-Nandy-ai@users.noreply.github.com>
  ```

## Engineering Standards (block all tasks until these pass)

Before marking any task done, verify all of these:

1. **Lint:** `uv run ruff check . && uv run ruff format --check .`
2. **Types:** `uv run mypy src/ --strict` -- zero errors, zero `# type: ignore` without explaining comment
3. **Tests:** `uv run pytest tests/ --cov=src/ --cov-fail-under=80` -- 80% minimum
4. **Security:** `trivy fs .` -- no HIGH or CRITICAL unfixed CVEs
5. **Benchmarks:** if you changed any of `electronics_rfq_agent/agent.py`, `electronics_rfq_agent/parser.py`, or any `electronics_rfq_agent/mcp/` file, run `uv run pytest benchmarks/` and include the delta

Do NOT mark complete if any fail. Fix the root cause.

## Planning Rules

Enter plan mode for any task that:
- Touches more than 2 files
- Changes a public API surface (anything in `electronics_rfq_agent/__init__.py`)
- Adds a new ERP integration (new file in `electronics_rfq_agent/mcp/`)
- Modifies CI pipeline

Write the plan first. If something goes wrong mid-task, stop and re-plan.

## Anti-Sycophancy Rules (active every session)

1. Counter-evidence first. Before confirming any implementation choice, name what the evidence does NOT support.
2. No benchmark claims without the benchmark command that produced them.
3. When asked "does this look right?" -- read the code before answering.
4. OSS stars are not revenue. If a feature optimizes for stars over user value, say so.
5. Before implementing any core feature: could SAP Joule, Epicor Prism, or Microsoft Copilot ship this as a feature update in under 3 months? If yes, name it.
6. The design partner is the unit of validation, not the star. Every feature added should trace back to a specific distributor use case.

## What Claude Must Never Do

- Add features not explicitly requested
- Skip tests to make CI pass faster
- Use mocks in integration tests (real APIs only, or the official mock backends in `electronics_rfq_agent/mcp/mock/`)
- Commit with `--no-verify`
- Merge anything that regresses benchmarks without explicit approval
- Accept AI-generated code without running and validating it
- State a performance number without showing the benchmark command

## Key Files

| File | Purpose |
|---|---|
| `electronics_rfq_agent/mcp/` | MCP servers for SAP, Epicor, Oracle, Dynamics |
| `electronics_rfq_agent/mcp/mock/` | Mock ERP backends for local development |
| `electronics_rfq_agent/parser.py` | RFQ document parser |
| `electronics_rfq_agent/agent.py` | Quote generation agent |
| `electronics_rfq_agent/models.py` | Pydantic models: RFQLineItem, QuoteLineItem, Quote |
| `benchmarks/` | All benchmarks -- reproducible in under 5 minutes |
| `CONTRIBUTING.md` | Contribution guide |
| `SECURITY.md` | CVE disclosure policy |
| `CHANGELOG.md` | Updated on every PR that changes public behavior |
| `.github/workflows/ci.yml` | lint -> type-check -> test -> security -> benchmark |

## Session Start Checklist

1. Run `git status` and `git log --oneline -5`
2. Run `uv run pytest tests/ -q` to confirm baseline is green
3. Read the last CHANGELOG entry to understand recent changes
4. If a bug is reported: write a failing test first, then fix it
