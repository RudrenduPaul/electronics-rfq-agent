"""CLI tests for `erfa quote`.

Uses Typer's CliRunner -- no process spawning, no real ERP or Anthropic calls.
QuoteAgent is patched at the module level so run_sync() returns a fixture.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from electronics_rfq_agent.cli import app
from electronics_rfq_agent.models import Quote, QuoteLineItem, RFQLineItem

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
    def test_quote_exits_zero_with_mock(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy content")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert result.exit_code == 0, result.output

    def test_quote_missing_file_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["quote", "/nonexistent/rfq.txt", "--mock"])
        assert result.exit_code != 0

    def test_quote_parse_error_exits_nonzero(self, tmp_path: Path) -> None:
        from electronics_rfq_agent.models import RFQParseError

        rfq = tmp_path / "bad.pdf"
        rfq.write_bytes(b"not a real pdf")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.side_effect = RFQParseError(
                "Claude returned invalid JSON: ..."
            )
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert result.exit_code != 0

    def test_quote_output_contains_part_numbers(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert "RES-0402-10K-1PCT" in result.output
        assert "CAP-100NF-50V-X7R-0402" in result.output

    def test_quote_found_line_shows_plus_icon(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert "[+]" in result.output

    def test_quote_not_found_shows_minus_icon(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = MISSING_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert "[-]" in result.output

    def test_quote_substituted_shows_tilde_icon(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SUBSTITUTED_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert "[~]" in result.output


class TestCLIMargin:
    def test_custom_margin_passed_to_agent(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            runner.invoke(app, ["quote", str(rfq), "--mock", "--margin", "0.25"])
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("margin_pct") == pytest.approx(0.25)

    def test_default_margin_is_015(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            runner.invoke(app, ["quote", str(rfq), "--mock"])
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("margin_pct") == pytest.approx(0.15)


class TestCLIMockFlag:
    def test_env_var_triggers_mock(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            with patch.dict(os.environ, {"ERFA_USE_MOCK": "true"}):
                result = runner.invoke(app, ["quote", str(rfq)])
        assert result.exit_code == 0, result.output

    def test_mock_flag_uses_mock_erp(self, tmp_path: Path) -> None:
        from electronics_rfq_agent.mcp.mock.backend import MockERP

        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            runner.invoke(app, ["quote", str(rfq), "--mock"])
        erp_arg = mock_cls.call_args.kwargs.get("erp")
        assert isinstance(erp_arg, MockERP)

    def test_without_mock_flag_uses_epicor(self, tmp_path: Path) -> None:
        from electronics_rfq_agent.mcp.epicor import EpicorMCP

        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        env_overrides = {
            "ERFA_EPICOR_URL": "https://epicor.test.example.com",
            "ERFA_EPICOR_API_KEY": "dGVzdDp0ZXN0",
        }
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            with patch.dict(os.environ, env_overrides, clear=False):
                os.environ.pop("ERFA_USE_MOCK", None)
                runner.invoke(app, ["quote", str(rfq)])
        erp_arg = mock_cls.call_args.kwargs.get("erp")
        assert isinstance(erp_arg, EpicorMCP)


class TestCLISummary:
    def test_summary_line_appears_in_output(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(app, ["quote", str(rfq), "--mock"])
        assert SIMPLE_QUOTE.summary() in result.output

    def test_run_sync_called_with_rfq_path(self, tmp_path: Path) -> None:
        rfq = tmp_path / "test_rfq.txt"
        rfq.write_text("dummy")
        mock_agent = MagicMock()
        mock_agent.run_sync.return_value = SIMPLE_QUOTE
        with patch("electronics_rfq_agent.agent.QuoteAgent", return_value=mock_agent):
            runner.invoke(app, ["quote", str(rfq), "--mock"])
        mock_agent.run_sync.assert_called_once_with(rfq)


class TestCLIOutput:
    def test_output_flag_saves_json_file(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        out = tmp_path / "quote.json"
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            result = runner.invoke(
                app, ["quote", str(rfq), "--mock", "--output", str(out)]
            )
        assert result.exit_code == 0, result.output
        assert out.exists()
        import json

        data = json.loads(out.read_text())
        assert "lines" in data
        assert "total_price" in data

    def test_output_flag_json_is_valid(self, tmp_path: Path) -> None:
        rfq = tmp_path / "rfq.txt"
        rfq.write_text("dummy")
        out = tmp_path / "q.json"
        with patch("electronics_rfq_agent.agent.QuoteAgent") as mock_cls:
            mock_cls.return_value.run_sync.return_value = SIMPLE_QUOTE
            runner.invoke(app, ["quote", str(rfq), "--mock", "--output", str(out)])
        import json

        data = json.loads(out.read_text())
        assert data["rfq_source"] == "test.txt"


class TestCLIAudit:
    def _write_quote_json(self, path: Path) -> None:
        import json

        data = SIMPLE_QUOTE.to_dict()
        path.write_text(json.dumps(data))

    def test_audit_exits_zero_on_valid_file(self, tmp_path: Path) -> None:
        f = tmp_path / "q.json"
        self._write_quote_json(f)
        result = runner.invoke(app, ["audit", str(f)])
        assert result.exit_code == 0, result.output

    def test_audit_shows_found_section(self, tmp_path: Path) -> None:
        f = tmp_path / "q.json"
        self._write_quote_json(f)
        result = runner.invoke(app, ["audit", str(f)])
        assert "FOUND" in result.output

    def test_audit_shows_fill_rate(self, tmp_path: Path) -> None:
        f = tmp_path / "q.json"
        self._write_quote_json(f)
        result = runner.invoke(app, ["audit", str(f)])
        assert "Fill rate" in result.output

    def test_audit_missing_file_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["audit", "/no/such/file.json"])
        assert result.exit_code != 0

    def test_audit_invalid_json_exits_nonzero(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        result = runner.invoke(app, ["audit", str(f)])
        assert result.exit_code != 0

    def test_audit_shows_not_found_section(self, tmp_path: Path) -> None:
        import json

        f = tmp_path / "q.json"
        data = MISSING_QUOTE.to_dict()
        f.write_text(json.dumps(data))
        result = runner.invoke(app, ["audit", str(f)])
        assert "NOT FOUND" in result.output

    def test_audit_shows_substituted_section(self, tmp_path: Path) -> None:
        import json

        f = tmp_path / "q.json"
        data = SUBSTITUTED_QUOTE.to_dict()
        f.write_text(json.dumps(data))
        result = runner.invoke(app, ["audit", str(f)])
        assert "SUBSTITUTED" in result.output

    def test_audit_json_array_exits_nonzero_with_clean_message(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "array.json"
        f.write_text("[1, 2, 3]")
        result = runner.invoke(app, ["audit", str(f)])
        assert result.exit_code != 0
        combined = result.output.lower() + (result.stderr or "").lower()
        assert "error" in combined

    def test_audit_malformed_line_missing_status_exits_nonzero(
        self, tmp_path: Path
    ) -> None:
        """Missing 'status' key must produce a clean error, not a Python traceback."""
        import json

        bad_data = {
            "id": "00000000-0000-0000-0000-000000000001",
            "rfq_source": "test.txt",
            "total_price": "0.00",
            "currency": "USD",
            "created_at": "2026-01-01T00:00:00Z",
            "lines": [{"rfq_line": {"line_number": 1, "part_number": "X"}}],
        }
        f = tmp_path / "bad_line.json"
        f.write_text(json.dumps(bad_data))
        result = runner.invoke(app, ["audit", str(f)])
        assert result.exit_code != 0
        combined = result.output + (result.stderr or "")
        assert "error" in combined.lower()
        assert "Traceback" not in combined

    def test_audit_malformed_rfq_line_shows_placeholder(self, tmp_path: Path) -> None:
        """Missing 'rfq_line' key must show [malformed line] placeholder, not crash."""
        import json

        bad_data = {
            "id": "00000000-0000-0000-0000-000000000001",
            "rfq_source": "test.txt",
            "total_price": "0.00",
            "currency": "USD",
            "created_at": "2026-01-01T00:00:00Z",
            "lines": [
                {"status": "found", "unit_price": "1.00", "extended_price": "1.00"}
            ],
        }
        f = tmp_path / "bad_rfq_line.json"
        f.write_text(json.dumps(bad_data))
        result = runner.invoke(app, ["audit", str(f)])
        assert "malformed line" in result.output.lower()


class TestTelemetry:
    def test_collector_writes_to_local_file(self, tmp_path: Path) -> None:
        from electronics_rfq_agent.telemetry import TelemetryCollector, TelemetryEvent

        log = tmp_path / "tel.jsonl"
        col = TelemetryCollector(log_path=log)  # type: ignore[arg-type]
        col.record(
            TelemetryEvent(
                erp_type="MockERP",
                line_count=5,
                found_count=4,
                not_found_count=1,
                substituted_count=0,
                duration_ms=250,
            )
        )
        import json

        lines = log.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["erp_type"] == "MockERP"
        assert data["line_count"] == 5

    def test_collector_appends_multiple_events(self, tmp_path: Path) -> None:
        from electronics_rfq_agent.telemetry import TelemetryCollector, TelemetryEvent

        log = tmp_path / "tel.jsonl"
        col = TelemetryCollector(log_path=log)  # type: ignore[arg-type]
        ev = TelemetryEvent(
            erp_type="EpicorMCP",
            line_count=2,
            found_count=2,
            not_found_count=0,
            substituted_count=0,
            duration_ms=100,
        )
        col.record(ev)
        col.record(ev)
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_collector_from_env_returns_none_by_default(self) -> None:
        from electronics_rfq_agent.telemetry import collector_from_env

        with patch.dict(os.environ, {"ERFA_TELEMETRY": "false"}):
            assert collector_from_env() is None

    def test_collector_from_env_returns_collector_when_enabled(self) -> None:
        from electronics_rfq_agent.telemetry import (
            TelemetryCollector,
            collector_from_env,
        )

        with patch.dict(os.environ, {"ERFA_TELEMETRY": "true"}):
            col = collector_from_env()
        assert isinstance(col, TelemetryCollector)

    def test_http_failure_is_silent(self, tmp_path: Path) -> None:
        from electronics_rfq_agent.telemetry import TelemetryCollector, TelemetryEvent

        log = tmp_path / "tel.jsonl"
        col = TelemetryCollector(
            log_path=log,  # type: ignore[arg-type]
            endpoint="http://127.0.0.1:1/nonexistent",
        )
        ev = TelemetryEvent(
            erp_type="MockERP",
            line_count=1,
            found_count=1,
            not_found_count=0,
            substituted_count=0,
            duration_ms=10,
        )
        col.record(ev)
        assert log.read_text().strip() != ""
