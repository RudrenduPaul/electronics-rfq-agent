"""CLI tests for `openquote quote`.

Uses Typer's CliRunner — no process spawning, no real ERP or Anthropic calls.
QuoteAgent is patched at the module level so run_sync() returns a fixture.
"""

from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from openquote.cli import app
from openquote.models import Quote, QuoteLineItem, RFQLineItem

runner = CliRunner()


def _make_quote(*part_numbers: str, status: str = "found") -> Quote:
    lines = [
        QuoteLineItem(
            rfq_line=RFQLineItem(
                line_number=i + 1,
                part_number=pn,
                quantity=100,
            ),
            status=status,  # type: ignore[arg-type]
            unit_price=Decimal("0.05") if status != "not_found" else None,
            extended_price=Decimal("5.00") if status != "not_found" else None,
        )
        for i, pn in enumerate(part_numbers)
    ]
    total = sum(
        (ln.extended_price for ln in lines if ln.extended_price),
        Decimal("0"),
    )
    return Quote(
        id="test-quote-id",
        rfq_source="test.txt",
        lines=lines,
        total_price=total,
    )


SIMPLE_QUOTE = _make_quote("RES-0402-10K-1PCT", "CAP-100NF-50V-X7R-0402")
MISSING_QUOTE = _make_quote("UNKNOWN-PART-XYZ", status="not_found")
SUBSTITUTED_QUOTE = _make_quote("RES-0402-10K-1PCT-ALT", status="substituted")


class TestCLIBasic:
    def test_quote_exits_zero_with_mock(self, tmp_path: pytest.TempdirFactory) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy content")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert result.exit_code == 0, result.output

    def test_quote_missing_file_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["quote", "/nonexistent/rfq.txt", "--mock"])
        assert result.exit_code != 0

    def test_quote_parse_error_exits_nonzero(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        from openquote.models import RFQParseError

        rfq = tmp_path / "bad.pdf"  # type: ignore[operator]
        rfq.write_bytes(b"not a real pdf")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.side_effect = RFQParseError(
                "Claude returned invalid JSON: ..."
            )
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert result.exit_code != 0

    def test_quote_output_contains_part_numbers(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert "RES-0402-10K-1PCT" in result.output
        assert "CAP-100NF-50V-X7R-0402" in result.output

    def test_quote_found_line_shows_plus_icon(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert "[+]" in result.output

    def test_quote_not_found_shows_minus_icon(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = MISSING_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert "[-]" in result.output

    def test_quote_substituted_shows_tilde_icon(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SUBSTITUTED_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert "[~]" in result.output


class TestCLIMargin:
    def test_custom_margin_passed_to_agent(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            runner.invoke(app, ["quote", str(rfq), "--mock", "--margin", "0.25"])
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("margin_pct") == pytest.approx(0.25)

    def test_default_margin_is_015(self, tmp_path: pytest.TempdirFactory) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            runner.invoke(app, ["quote", str(rfq), "--mock"])
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("margin_pct") == pytest.approx(0.15)


class TestCLIMockFlag:
    def test_env_var_triggers_mock(self, tmp_path: pytest.TempdirFactory) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "true"}):
                result = runner.invoke(app, ["quote", str(rfq)])
        assert result.exit_code == 0, result.output

    def test_mock_flag_uses_mock_erp(self, tmp_path: pytest.TempdirFactory) -> None:
        from openquote.mcp.mock.backend import MockERP

        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            runner.invoke(app, ["quote", str(rfq), "--mock"])
        erp_arg = mock_cls.call_args.kwargs.get("erp")
        assert isinstance(erp_arg, MockERP)

    def test_without_mock_flag_uses_epicor(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        from openquote.mcp.epicor import EpicorMCP

        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENQUOTE_USE_MOCK", None)
                runner.invoke(app, ["quote", str(rfq)])
        erp_arg = mock_cls.call_args.kwargs.get("erp")
        assert isinstance(erp_arg, EpicorMCP)


class TestCLISummary:
    def test_summary_line_appears_in_output(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        rfq = tmp_path / "rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        with patch("openquote.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert SIMPLE_QUOTE.summary() in result.output

    def test_run_sync_called_with_rfq_path(
        self, tmp_path: pytest.TempdirFactory
    ) -> None:
        rfq = tmp_path / "test_rfq.txt"  # type: ignore[operator]
        rfq.write_text("dummy")
        mock_agent = MagicMock()
        mock_agent.run_sync.return_value = SIMPLE_QUOTE
        with patch("openquote.agent.QuoteAgent", return_value=mock_agent):
            runner.invoke(app, ["quote", str(rfq), "--mock"])
        mock_agent.run_sync.assert_called_once_with(rfq)
