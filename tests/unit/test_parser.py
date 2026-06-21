from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from electronics_rfq_agent.models import RFQLineItem, RFQParseError
from electronics_rfq_agent.parser import RFQParser


@pytest.fixture
def parser() -> RFQParser:
    return RFQParser(model="claude-sonnet-4-6")


SAMPLE_JSON = json.dumps(
    [
        {
            "line_number": 1,
            "part_number": "RES-0402-10K",
            "quantity": 100,
            "required_date": None,
            "manufacturer": "Yageo",
            "customer_notes": None,
        },
        {
            "line_number": 2,
            "part_number": "CAP-100NF",
            "quantity": 50,
            "required_date": None,
            "manufacturer": None,
            "customer_notes": "blue tape",
        },
    ]
)


class TestRFQParserInit:
    def test_default_model(self) -> None:
        p = RFQParser()
        assert p.model == "claude-sonnet-4-6"

    def test_custom_model(self) -> None:
        p = RFQParser(model="claude-opus-4-5")
        assert p.model == "claude-opus-4-5"

    def test_env_model_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ERFA_MODEL", "claude-haiku-3")
        p = RFQParser()
        assert p.model == "claude-haiku-3"


class TestRFQParserJson:
    def test_parse_json_response_basic(self, parser: RFQParser) -> None:
        items = parser._parse_json_response(SAMPLE_JSON)
        assert len(items) == 2
        assert items[0].part_number == "RES-0402-10K"
        assert items[1].quantity == 50

    def test_parse_json_preserves_manufacturer(self, parser: RFQParser) -> None:
        items = parser._parse_json_response(SAMPLE_JSON)
        assert items[0].manufacturer == "Yageo"
        assert items[1].manufacturer is None

    def test_parse_json_preserves_notes(self, parser: RFQParser) -> None:
        items = parser._parse_json_response(SAMPLE_JSON)
        assert items[1].customer_notes == "blue tape"

    def test_parse_json_with_code_fence(self, parser: RFQParser) -> None:
        fenced = f"```json\n{SAMPLE_JSON}\n```"
        items = parser._parse_json_response(fenced)
        assert len(items) == 2

    def test_parse_json_with_plain_fence(self, parser: RFQParser) -> None:
        fenced = f"```\n{SAMPLE_JSON}\n```"
        items = parser._parse_json_response(fenced)
        assert len(items) == 2

    def test_parse_json_skips_invalid_rows(self, parser: RFQParser) -> None:
        bad_json = json.dumps(
            [
                {"line_number": 1, "quantity": 10},  # missing part_number
                {"line_number": 2, "part_number": "GOOD-PART", "quantity": 5},
            ]
        )
        items = parser._parse_json_response(bad_json)
        assert len(items) == 1
        assert items[0].part_number == "GOOD-PART"

    def test_parse_json_uses_index_for_missing_line_number(
        self, parser: RFQParser
    ) -> None:
        data = json.dumps(
            [
                {"part_number": "RES-001", "quantity": 10},
                {"part_number": "CAP-001", "quantity": 5},
            ]
        )
        items = parser._parse_json_response(data)
        assert items[0].line_number == 1
        assert items[1].line_number == 2

    def test_parse_json_defaults_quantity_to_1(self, parser: RFQParser) -> None:
        data = json.dumps([{"line_number": 1, "part_number": "TEST-001"}])
        items = parser._parse_json_response(data)
        assert items[0].quantity == 1

    def test_parse_json_empty_array(self, parser: RFQParser) -> None:
        items = parser._parse_json_response("[]")
        assert items == []

    def test_parse_json_invalid_json_raises_parse_error(
        self, parser: RFQParser
    ) -> None:
        with pytest.raises(RFQParseError, match="invalid JSON"):
            parser._parse_json_response("not valid json {{{")

    def test_parse_json_truncated_json_raises_parse_error(
        self, parser: RFQParser
    ) -> None:
        with pytest.raises(RFQParseError, match="invalid JSON"):
            parser._parse_json_response('[{"part_number": "RES-001"')  # truncated

    def test_parse_json_object_instead_of_array_raises_parse_error(
        self, parser: RFQParser
    ) -> None:
        """When the model returns a JSON object instead of an array (e.g.
        {"error": "..."} or {"line_items": [...]}), _parse_json_response must
        raise RFQParseError — not crash with AttributeError from iterating dict
        keys and calling .get() on strings."""
        with pytest.raises(RFQParseError, match="dict"):
            parser._parse_json_response('{"error": "could not parse this document"}')

    def test_parse_json_scalar_instead_of_array_raises_parse_error(
        self, parser: RFQParser
    ) -> None:
        with pytest.raises(RFQParseError, match="str"):
            parser._parse_json_response('"just a string"')


class TestFindHeaderRow:
    def test_find_header_row_with_part(self) -> None:
        rows: list[list[Any]] = [
            ["Company XYZ", None, None],
            ["RFQ Date: 2026-01-01", None, None],
            ["Part Number", "Qty", "Manufacturer"],
            ["RES-0402-10K", "100", "Yageo"],
        ]
        idx = RFQParser._find_header_row(rows)
        assert idx == 2

    def test_find_header_row_with_pn(self) -> None:
        rows: list[list[Any]] = [
            ["Header row with PN", "qty", "mfr"],
            ["actual data", "10", "Yageo"],
        ]
        idx = RFQParser._find_header_row(rows)
        assert idx == 0

    def test_find_header_row_no_header_returns_none(self) -> None:
        rows: list[list[Any]] = [
            ["Random data", "123", "abc"],
            ["More data", "456", "def"],
        ]
        idx = RFQParser._find_header_row(rows)
        assert idx is None

    def test_find_header_row_searches_first_10_rows(self) -> None:
        rows: list[list[Any]] = [["filler", None]] * 9 + [["Part Number", "Qty"]]
        idx = RFQParser._find_header_row(rows)
        assert idx == 9

    def test_find_header_row_with_quantity_keyword(self) -> None:
        rows: list[list[Any]] = [
            ["part number", "quantity", "notes"],
        ]
        idx = RFQParser._find_header_row(rows)
        assert idx == 0

    def test_find_header_row_with_description(self) -> None:
        rows: list[list[Any]] = [
            ["description", "item", "qty"],
        ]
        idx = RFQParser._find_header_row(rows)
        assert idx == 0


class TestMapColumns:
    def test_map_columns_standard(self) -> None:
        header = ["part number", "quantity", "manufacturer", "notes"]
        col = RFQParser._map_columns(header)
        assert col["part_number"] == 0
        assert col["quantity"] == 1
        assert col["manufacturer"] == 2
        assert col["notes"] == 3

    def test_map_columns_abbreviated(self) -> None:
        header = ["mpn", "qty", "mfr", "comment"]
        col = RFQParser._map_columns(header)
        assert col.get("part_number") == 0
        assert col.get("quantity") == 1
        assert col.get("manufacturer") == 2

    def test_map_columns_pn_keyword(self) -> None:
        header = ["pn", "qty", "brand"]
        col = RFQParser._map_columns(header)
        assert col.get("part_number") == 0
        assert col.get("manufacturer") == 2

    def test_map_columns_item_keyword(self) -> None:
        header = ["item", "amount", "vendor"]
        col = RFQParser._map_columns(header)
        assert col.get("part_number") == 0
        assert col.get("quantity") == 1
        assert col.get("manufacturer") == 2

    def test_map_columns_remark_keyword(self) -> None:
        header = ["part", "qty", "remark"]
        col = RFQParser._map_columns(header)
        assert col.get("notes") == 2

    def test_map_columns_no_match(self) -> None:
        header = ["col_a", "col_b", "col_c"]
        col = RFQParser._map_columns(header)
        assert "part_number" not in col
        assert "quantity" not in col

    def test_map_columns_first_match_wins(self) -> None:
        # Two part-like columns — first should win
        header = ["part number", "mpn", "qty"]
        col = RFQParser._map_columns(header)
        assert col["part_number"] == 0


class TestCell:
    def test_returns_value(self) -> None:
        row = ["a", "b", "c"]
        assert RFQParser._cell(row, 1) == "b"

    def test_none_idx_returns_empty(self) -> None:
        assert RFQParser._cell(["a"], None) == ""

    def test_out_of_range_returns_empty(self) -> None:
        assert RFQParser._cell(["a"], 5) == ""

    def test_strips_whitespace(self) -> None:
        row = ["  hello  ", "b"]
        assert RFQParser._cell(row, 0) == "hello"

    def test_none_value_returns_empty(self) -> None:
        row = [None, "b"]
        assert RFQParser._cell(row, 0) == ""

    def test_works_on_list_of_strings(self) -> None:
        lst = ["a", "b", "c"]
        assert RFQParser._cell(lst, 1) == "b"

    def test_list_out_of_range_returns_empty(self) -> None:
        assert RFQParser._cell(["a"], 5) == ""

    def test_list_strips_whitespace(self) -> None:
        lst = ["  hello  "]
        assert RFQParser._cell(lst, 0) == "hello"


class TestAsyncParsing:
    @pytest.mark.asyncio
    async def test_parse_text_calls_anthropic(self, parser: RFQParser) -> None:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_JSON)]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            items = await parser._parse_text("RES-0402-10K,100\nCAP-100NF,50")

        assert len(items) == 2
        mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_text_passes_system_prompt(self, parser: RFQParser) -> None:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="[]")]
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            await parser._parse_text("test content")

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs is not None
        # system prompt should be passed
        assert "system" in call_kwargs.kwargs or len(call_kwargs.args) > 0

    @pytest.mark.asyncio
    async def test_parse_routes_text_input(self, parser: RFQParser) -> None:
        """parse() with a non-existent file path should route to _parse_text."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=SAMPLE_JSON)]
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            items = await parser.parse("this is raw text not a file path")

        assert len(items) == 2


class TestWordParsing:
    def test_parse_word_from_fixture(
        self, fixtures_dir: Path, parser: RFQParser
    ) -> None:
        docx_path = fixtures_dir / "sample_rfq.docx"
        if not docx_path.exists():
            pytest.skip("sample_rfq.docx fixture not present")
        items = parser._parse_word(docx_path)
        assert isinstance(items, list)


class TestExcelParsing:
    def test_parse_excel_from_fixture(
        self, fixtures_dir: Path, parser: RFQParser
    ) -> None:
        excel_path = fixtures_dir / "sample_rfq.xlsx"
        if not excel_path.exists():
            pytest.skip("sample_rfq.xlsx fixture not present")
        items = parser._parse_excel(excel_path)
        assert len(items) >= 1
        assert all(isinstance(i, RFQLineItem) for i in items)


class TestMapColumnsBugFixes:
    """Regression tests for column mapping false-positive substring matches."""

    def test_line_item_column_not_mapped_to_part_number(self) -> None:
        # "line_item" contains "item" but should NOT be treated as a part-number column
        header = ["line_item", "part_number", "qty"]
        col = RFQParser._map_columns(header)
        assert col.get("part_number") == 1, (
            "part_number should map to 'part_number' column, not 'line_item'"
        )

    def test_total_amount_column_not_mapped_to_quantity(self) -> None:
        # "total amount" contains "amount" but is a price column, not a quantity column
        header = ["part_number", "qty", "total amount"]
        col = RFQParser._map_columns(header)
        assert col.get("quantity") == 1, (
            "quantity should map to 'qty' column, not 'total amount'"
        )
        assert col.get("part_number") == 0

    def test_bare_item_still_maps_to_part_number(self) -> None:
        # Bare "item" (exact column name) should still map to part_number
        header = ["item", "amount", "vendor"]
        col = RFQParser._map_columns(header)
        assert col.get("part_number") == 0
        assert col.get("quantity") == 1

    def test_item_number_maps_to_part_number(self) -> None:
        header = ["item number", "qty", "mfr"]
        col = RFQParser._map_columns(header)
        assert col.get("part_number") == 0

    def test_item_no_maps_to_part_number(self) -> None:
        header = ["item no", "quantity", "notes"]
        col = RFQParser._map_columns(header)
        assert col.get("part_number") == 0


class TestFenceStripping:
    """Regression tests for JSON fence-stripping edge cases."""

    def test_empty_fence_raises_rfq_parse_error(self, parser: RFQParser) -> None:
        # A lone opening fence with no content should raise a descriptive error
        with pytest.raises(RFQParseError, match="empty response"):
            parser._parse_json_response("```")

    def test_fence_with_only_closing_raises_rfq_parse_error(
        self, parser: RFQParser
    ) -> None:
        with pytest.raises(RFQParseError, match="empty response"):
            parser._parse_json_response("```\n```")

    def test_fence_with_json_keyword_and_empty_body(self, parser: RFQParser) -> None:
        with pytest.raises(RFQParseError, match="empty response"):
            parser._parse_json_response("```json\n```")


class TestSkippedRowsWarning:
    """Regression tests for logging.warning on skipped rows."""

    def test_skipped_rows_emit_warning(
        self, parser: RFQParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        bad_json = json.dumps(
            [
                {"line_number": 1, "quantity": 10},  # missing part_number → skipped
                {"line_number": 2, "part_number": "GOOD-PART", "quantity": 5},
            ]
        )
        with caplog.at_level(logging.WARNING, logger="electronics_rfq_agent.parser"):
            items = parser._parse_json_response(bad_json)

        assert len(items) == 1
        assert any("Skipped row" in msg for msg in caplog.messages), (
            "Expected a warning about the skipped row"
        )
