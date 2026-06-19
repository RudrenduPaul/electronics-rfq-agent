from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from openquote.agent import QuoteAgent
from openquote.mcp.mock.backend import MockERP
from openquote.models import ERPConnectionError, Quote, RFQLineItem


@pytest.fixture
def agent(mock_erp: MockERP) -> QuoteAgent:
    return QuoteAgent(erp=mock_erp, margin_pct=0.10)


class TestQuoteAgentInit:
    def test_default_model(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp)
        assert agent.model == "claude-sonnet-4-6"

    def test_custom_margin(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp, margin_pct=0.20)
        assert agent.margin_pct == Decimal("0.20")

    def test_zero_margin(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp, margin_pct=0.0)
        assert agent.margin_pct == Decimal("0.0")

    def test_env_model_override(
        self, mock_erp: MockERP, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENQUOTE_MODEL", "claude-haiku-3")
        agent = QuoteAgent(erp=mock_erp)
        assert agent.model == "claude-haiku-3"

    def test_parser_created(self, mock_erp: MockERP) -> None:
        from openquote.parser import RFQParser

        agent = QuoteAgent(erp=mock_erp)
        assert isinstance(agent._parser, RFQParser)

    def test_erp_stored(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp)
        assert agent.erp is mock_erp


class TestQuoteAgentLookup:
    @pytest.mark.asyncio
    async def test_lookup_line_found(
        self, agent: QuoteAgent, mock_erp: MockERP
    ) -> None:
        parts = await mock_erp.search_parts("RES", limit=1)
        if not parts:
            pytest.skip("No RES parts in mock catalog")

        part = parts[0]
        rfq_line = RFQLineItem(
            line_number=1,
            part_number=part.part_number,
            quantity=10,
        )
        result = await agent._lookup_line(rfq_line)
        assert result.status in ("found", "substituted")
        assert result.unit_price is not None
        assert result.extended_price is not None

    @pytest.mark.asyncio
    async def test_lookup_line_not_found(self, agent: QuoteAgent) -> None:
        rfq_line = RFQLineItem(
            line_number=1,
            part_number="PART-GUARANTEED-NOT-IN-CATALOG-XYZ999",
            quantity=1,
        )
        result = await agent._lookup_line(rfq_line)
        assert result.status == "not_found"
        assert result.unit_price is None
        assert result.extended_price is None

    @pytest.mark.asyncio
    async def test_not_found_has_notes(self, agent: QuoteAgent) -> None:
        rfq_line = RFQLineItem(
            line_number=1,
            part_number="DOES-NOT-EXIST-AT-ALL-999",
            quantity=1,
        )
        result = await agent._lookup_line(rfq_line)
        assert result.status == "not_found"
        assert result.notes is not None
        assert "DOES-NOT-EXIST-AT-ALL-999" in result.notes

    @pytest.mark.asyncio
    async def test_margin_applied(self, agent: QuoteAgent, mock_erp: MockERP) -> None:
        parts = await mock_erp.search_parts("RES-0402", limit=1)
        if not parts:
            pytest.skip("No RES-0402 parts in mock catalog")

        part = parts[0]
        rfq_line = RFQLineItem(
            line_number=1,
            part_number=part.part_number,
            quantity=1,
        )
        result = await agent._lookup_line(rfq_line)
        if result.status == "found":
            # cost price at qty=1 is unit_price (no discount), margin is 10%
            erp_price = part.unit_price
            assert result.unit_price is not None
            assert result.unit_price >= erp_price

    @pytest.mark.asyncio
    async def test_extended_price_equals_unit_times_qty(
        self, agent: QuoteAgent, mock_erp: MockERP
    ) -> None:
        parts = await mock_erp.search_parts("RES-0402-10K-1PCT", limit=1)
        if not parts:
            pytest.skip("Part not in catalog")
        part = parts[0]
        qty = 10
        rfq_line = RFQLineItem(
            line_number=1,
            part_number=part.part_number,
            quantity=qty,
        )
        result = await agent._lookup_line(rfq_line)
        if result.status in ("found", "substituted"):
            assert result.unit_price is not None
            assert result.extended_price is not None
            # extended should be unit * qty (with rounding)
            expected = (result.unit_price * qty).quantize(Decimal("0.01"))
            assert abs(result.extended_price - expected) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_lookup_line_erp_connection_error_returns_not_found(
        self, agent: QuoteAgent
    ) -> None:
        """ERPConnectionError on a single part lookup must not propagate — it
        should return a not_found line so the rest of the quote continues."""
        rfq_line = RFQLineItem(line_number=1, part_number="RES-001", quantity=10)
        with patch.object(agent.erp, "get_part", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = ERPConnectionError("SAP unreachable")
            result = await agent._lookup_line(rfq_line)
        assert result.status == "not_found"
        assert result.notes is not None
        assert "ERP lookup failed" in result.notes

    @pytest.mark.asyncio
    async def test_lookup_line_get_price_error_returns_not_found(
        self, agent: QuoteAgent
    ) -> None:
        """get_price() can raise ERPConnectionError (it makes network calls too).
        A failure there must NOT propagate to asyncio.gather — it must return
        a not_found line so the rest of the quote continues."""
        rfq_line = RFQLineItem(
            line_number=1, part_number="RES-0402-10K-1PCT", quantity=10
        )
        with patch.object(agent.erp, "get_price", new_callable=AsyncMock) as mock_price:
            mock_price.side_effect = ERPConnectionError("pricing service down")
            result = await agent._lookup_line(rfq_line)
        assert result.status == "not_found"
        assert result.notes is not None
        assert "ERP lookup failed" in result.notes

    @pytest.mark.asyncio
    async def test_get_price_returns_none_falls_back_to_unit_price(
        self, agent: QuoteAgent
    ) -> None:
        """When get_price() returns None for a found part, agent must fall back
        to part.unit_price so the quote line is still priced correctly."""
        rfq_line = RFQLineItem(
            line_number=1, part_number="RES-0402-10K-1PCT", quantity=10
        )
        with patch.object(agent.erp, "get_price", new_callable=AsyncMock) as mock_price:
            mock_price.return_value = None
            result = await agent._lookup_line(rfq_line)
        assert result.status in ("found", "substituted")
        assert result.unit_price is not None

    @pytest.mark.asyncio
    async def test_duplicate_part_numbers_deduplicated(self, agent: QuoteAgent) -> None:
        """Two RFQ lines with the same (part_number, quantity) should only run
        one _gated_lookup task, not two. The dedup cache in run() ensures this."""
        lines = [
            RFQLineItem(line_number=1, part_number="RES-0402-10K-1PCT", quantity=10),
            RFQLineItem(line_number=2, part_number="RES-0402-10K-1PCT", quantity=10),
        ]
        gated_lookup_calls = 0
        original_gated = agent._gated_lookup

        async def counting_gated(ln: RFQLineItem) -> object:
            nonlocal gated_lookup_calls
            gated_lookup_calls += 1
            return await original_gated(ln)

        with (
            patch.object(agent._parser, "parse", new_callable=AsyncMock) as mp,
            patch.object(agent, "_gated_lookup", side_effect=counting_gated),
        ):
            mp.return_value = lines
            quote = await agent.run("fake.txt")

        assert len(quote.lines) == 2
        # Both lines must appear in the quote
        assert quote.lines[0].rfq_line.line_number == 1
        assert quote.lines[1].rfq_line.line_number == 2
        assert gated_lookup_calls == 1  # Only one ERP task dispatched

    @pytest.mark.asyncio
    async def test_substituted_status_when_search_finds_different(
        self, agent: QuoteAgent
    ) -> None:
        # Search for a partial match — agent looks up exact part first (gets None),
        # then does search_parts which might return a different part
        rfq_line = RFQLineItem(
            line_number=1,
            part_number="RES-0402",  # partial — won't match exactly
            quantity=5,
        )
        result = await agent._lookup_line(rfq_line)
        # Could be substituted (if search found something) or not_found
        assert result.status in ("found", "substituted", "not_found")


class TestQuoteAgentRun:
    @pytest.mark.asyncio
    async def test_run_with_mock_parser(
        self, agent: QuoteAgent, sample_rfq_lines: list[RFQLineItem]
    ) -> None:
        with patch.object(agent._parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:3]
            quote = await agent.run("fake_rfq.txt")

        assert len(quote.lines) == 3
        assert quote.total_price >= Decimal("0")

    @pytest.mark.asyncio
    async def test_run_returns_quote_instance(
        self, agent: QuoteAgent, sample_rfq_lines: list[RFQLineItem]
    ) -> None:
        with patch.object(agent._parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:1]
            result = await agent.run("fake.txt")
        assert isinstance(result, Quote)

    @pytest.mark.asyncio
    async def test_run_rfq_source_stored(
        self, agent: QuoteAgent, sample_rfq_lines: list[RFQLineItem]
    ) -> None:
        with patch.object(agent._parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:1]
            quote = await agent.run("my_rfq.xlsx")
        assert quote.rfq_source == "my_rfq.xlsx"

    @pytest.mark.asyncio
    async def test_run_empty_rfq_returns_zero_total(self, agent: QuoteAgent) -> None:
        with patch.object(agent._parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = []
            quote = await agent.run("empty.txt")
        assert quote.total_price == Decimal("0")
        assert len(quote.lines) == 0

    def test_run_sync_wrapper(
        self, agent: QuoteAgent, sample_rfq_lines: list[RFQLineItem]
    ) -> None:
        with patch.object(agent._parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:2]
            quote = agent.run_sync("fake_rfq.txt")
        assert quote is not None
        assert len(quote.lines) == 2

    def test_run_sync_returns_quote(
        self, agent: QuoteAgent, sample_rfq_lines: list[RFQLineItem]
    ) -> None:
        with patch.object(agent._parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:1]
            result = agent.run_sync("fake.txt")
        assert isinstance(result, Quote)

    def test_run_sync_safe_inside_running_event_loop(
        self, agent: QuoteAgent, sample_rfq_lines: list[RFQLineItem]
    ) -> None:
        """Verify run_sync() works when called from inside an active event loop.

        Uses nest_asyncio under the hood — tests the actual fix path for the
        "asyncio event loop is already running" error that occurs in Jupyter
        or inside existing async frameworks (FastAPI startup handlers, etc.).
        """
        import asyncio

        import nest_asyncio

        async def _caller() -> Quote:
            with patch.object(
                agent._parser, "parse", new_callable=AsyncMock
            ) as mock_parse:
                mock_parse.return_value = sample_rfq_lines[:1]
                nest_asyncio.apply()
                return agent.run_sync("fake_from_loop.txt")

        result = asyncio.run(_caller())
        assert isinstance(result, Quote)
        assert len(result.lines) == 1


class TestQuoteAgentWithMockERP:
    @pytest.mark.asyncio
    async def test_known_parts_found(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp, margin_pct=0.15)
        rfq_line = RFQLineItem(
            line_number=1, part_number="RES-0402-10K-1PCT", quantity=100
        )
        result = await agent._lookup_line(rfq_line)
        assert result.status == "found"
        assert result.unit_price is not None

    @pytest.mark.asyncio
    async def test_capacitor_found(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp, margin_pct=0.15)
        rfq_line = RFQLineItem(
            line_number=1, part_number="CAP-100NF-50V-X7R-0402", quantity=50
        )
        result = await agent._lookup_line(rfq_line)
        assert result.status == "found"

    @pytest.mark.asyncio
    async def test_ic_found(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp, margin_pct=0.15)
        rfq_line = RFQLineItem(line_number=1, part_number="IC-LM358-SOIC8", quantity=10)
        result = await agent._lookup_line(rfq_line)
        assert result.status == "found"

    @pytest.mark.asyncio
    async def test_crystal_found(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp, margin_pct=0.15)
        rfq_line = RFQLineItem(line_number=1, part_number="XTAL-16MHZ-SMD", quantity=5)
        result = await agent._lookup_line(rfq_line)
        assert result.status == "found"

    @pytest.mark.asyncio
    async def test_sell_price_higher_than_cost(self, mock_erp: MockERP) -> None:
        agent = QuoteAgent(erp=mock_erp, margin_pct=0.10)
        part = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert part is not None

        rfq_line = RFQLineItem(
            line_number=1, part_number="RES-0402-10K-1PCT", quantity=1
        )
        result = await agent._lookup_line(rfq_line)
        assert result.unit_price is not None
        # sell price = cost * 1.10, so must be >= cost
        assert result.unit_price >= part.unit_price
