"""Tests for the MCP stdio server's exposed tools.

Calls the tool functions directly (unwrapping FastMCP's decorator via .fn) --
no real stdio transport, no real Anthropic or ERP calls beyond MockERP.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from electronics_rfq_agent.mcp_server import audit_quote, lookup_part, quote_rfq
from electronics_rfq_agent.models import (
    Quote,
    QuoteLineItem,
    RFQLineItem,
    RFQParseError,
)


def _fn(tool: object) -> object:
    """Unwrap a FastMCP-decorated tool to its underlying callable."""
    return getattr(tool, "fn", tool)


def _make_quote() -> Quote:
    line = QuoteLineItem(
        rfq_line=RFQLineItem(
            line_number=1, part_number="RES-0402-1K-1PCT", quantity=100
        ),
        status="found",
        unit_price=Decimal("0.008"),
        extended_price=Decimal("0.80"),
    )
    return Quote(
        id="test-quote-id",
        rfq_source="test.xlsx",
        lines=[line],
        total_price=Decimal("0.80"),
    )


@pytest.mark.asyncio
async def test_quote_rfq_returns_dict() -> None:
    quote = _make_quote()
    with patch(
        "electronics_rfq_agent.agent.QuoteAgent.run", new=AsyncMock(return_value=quote)
    ):
        result = await _fn(quote_rfq)("rfq.xlsx", mock=True)  # type: ignore[operator]
    assert result["id"] == "test-quote-id"
    assert result["total_price"] == "0.80"


@pytest.mark.asyncio
async def test_quote_rfq_file_not_found() -> None:
    with patch(
        "electronics_rfq_agent.agent.QuoteAgent.run",
        new=AsyncMock(side_effect=FileNotFoundError()),
    ):
        result = await _fn(quote_rfq)("missing.xlsx", mock=True)  # type: ignore[operator]
    assert "error" in result
    assert "missing.xlsx" in result["error"]


@pytest.mark.asyncio
async def test_quote_rfq_parse_error() -> None:
    with patch(
        "electronics_rfq_agent.agent.QuoteAgent.run",
        new=AsyncMock(side_effect=RFQParseError("bad document")),
    ):
        result = await _fn(quote_rfq)("bad.xlsx", mock=True)  # type: ignore[operator]
    assert "error" in result
    assert "bad document" in result["error"]


@pytest.mark.asyncio
async def test_lookup_part_found() -> None:
    result = await _fn(lookup_part)("RES-0402-1K-1PCT", mock=True)  # type: ignore[operator]
    assert result is not None
    assert result["part_number"] == "RES-0402-1K-1PCT"
    assert result["manufacturer"] == "Yageo"


@pytest.mark.asyncio
async def test_lookup_part_not_found() -> None:
    result = await _fn(lookup_part)("NO-SUCH-PART-XYZ", mock=True)  # type: ignore[operator]
    assert result is None


def test_audit_quote_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    result = _fn(audit_quote)(str(missing))  # type: ignore[operator]
    assert "error" in result
    assert "not found" in result["error"]


def test_audit_quote_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    result = _fn(audit_quote)(str(bad))  # type: ignore[operator]
    assert "error" in result


def test_audit_quote_non_object_json(tmp_path: Path) -> None:
    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2, 3]")
    result = _fn(audit_quote)(str(arr))  # type: ignore[operator]
    assert "error" in result
    assert "list" in result["error"]


def test_audit_quote_full_breakdown(tmp_path: Path) -> None:
    quote_file = tmp_path / "quote.json"
    quote_file.write_text(
        json.dumps(
            {
                "id": "abcd1234efgh",
                "rfq_source": "test.xlsx",
                "total_price": "12.50",
                "currency": "USD",
                "lines": [
                    {"status": "found", "rfq_line": {"part_number": "A"}},
                    {"status": "substituted", "rfq_line": {"part_number": "B"}},
                    {"status": "not_found", "rfq_line": {"part_number": "C"}},
                ],
            }
        )
    )
    result = _fn(audit_quote)(str(quote_file))  # type: ignore[operator]
    assert result["quote_id"] == "abcd1234efgh"
    assert len(result["found"]) == 1
    assert len(result["substituted"]) == 1
    assert len(result["not_found"]) == 1
    assert result["fill_rate_pct"] == 67


def test_audit_quote_empty_lines(tmp_path: Path) -> None:
    quote_file = tmp_path / "empty.json"
    quote_file.write_text(json.dumps({"id": "x", "lines": []}))
    result = _fn(audit_quote)(str(quote_file))  # type: ignore[operator]
    assert result["fill_rate_pct"] == 0
