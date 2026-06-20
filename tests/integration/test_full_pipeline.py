from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from electronics_rfq_agent.agent import QuoteAgent
from electronics_rfq_agent.mcp.mock.backend import MockERP
from electronics_rfq_agent.models import Quote, RFQLineItem


@pytest.fixture
def agent_with_mock() -> QuoteAgent:
    erp = MockERP()
    return QuoteAgent(erp=erp, margin_pct=0.15)


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_with_5_lines(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:5]
            quote = await agent_with_mock.run("fake.xlsx")

        assert isinstance(quote, Quote)
        assert len(quote.lines) == 5
        assert quote.total_price >= Decimal("0")

    @pytest.mark.asyncio
    async def test_all_statuses_represented(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        # sample_rfq_lines[4] has PART-DOES-NOT-EXIST-XYZ — will be not_found
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = sample_rfq_lines
            quote = await agent_with_mock.run("fake.txt")

        statuses = {line.status for line in quote.lines}
        assert "not_found" in statuses

    @pytest.mark.asyncio
    async def test_known_parts_are_found(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        # First 4 lines have parts that exist in the catalog
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:4]
            quote = await agent_with_mock.run("fake.xlsx")

        found_count = sum(
            1 for line in quote.lines if line.status in ("found", "substituted")
        )
        assert found_count == 4

    @pytest.mark.asyncio
    async def test_found_lines_have_prices(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:4]
            quote = await agent_with_mock.run("fake.pdf")

        for line in quote.lines:
            if line.status in ("found", "substituted"):
                assert line.unit_price is not None
                assert line.extended_price is not None
                assert line.extended_price > Decimal("0")

    @pytest.mark.asyncio
    async def test_total_matches_line_sum(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:3]
            quote = await agent_with_mock.run("fake.xlsx")

        computed = sum(
            line.extended_price
            for line in quote.lines
            if line.extended_price is not None
        )
        assert abs(computed - quote.total_price) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_quote_summary_format(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:3]
            quote = await agent_with_mock.run("fake.xlsx")

        summary = quote.summary()
        assert "Quote" in summary
        assert "USD" in summary
        assert "lines" in summary

    @pytest.mark.asyncio
    async def test_to_dict_roundtrip(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = sample_rfq_lines[:2]
            quote = await agent_with_mock.run("fake.xlsx")

        d = quote.to_dict()
        assert "id" in d
        assert "lines" in d
        assert len(d["lines"]) == 2

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        async with MockERP() as erp:
            assert erp is not None
            results = await erp.search_parts("RES", limit=1)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_margin_reflected_in_prices(
        self,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        erp = MockERP()
        agent = QuoteAgent(erp=erp, margin_pct=0.20)

        part = await erp.get_part("RES-0402-10K-1PCT")
        assert part is not None

        with patch.object(agent._parser, "parse", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = [sample_rfq_lines[0]]  # RES-0402-10K-1PCT qty=100
            quote = await agent.run("fake.xlsx")

        found = [ln for ln in quote.lines if ln.status == "found"]
        assert found, "RES-0402-10K-1PCT should be found"

        # Cost price at qty=100 gets 10% discount
        cost = part.unit_price * Decimal("0.90")
        expected_sell = (cost * Decimal("1.20")).quantize(Decimal("0.0001"))
        assert found[0].unit_price is not None
        assert abs(found[0].unit_price - expected_sell) < Decimal("0.001")

    @pytest.mark.asyncio
    async def test_not_found_line_has_zero_price(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = [sample_rfq_lines[4]]  # PART-DOES-NOT-EXIST-XYZ
            quote = await agent_with_mock.run("fake.txt")

        assert len(quote.lines) == 1
        assert quote.lines[0].status == "not_found"
        assert quote.lines[0].unit_price is None
        assert quote.lines[0].extended_price is None
        assert quote.total_price == Decimal("0")

    @pytest.mark.asyncio
    async def test_pipeline_with_single_line(self, agent_with_mock: QuoteAgent) -> None:
        line = RFQLineItem(line_number=1, part_number="RES-0402-10K-1PCT", quantity=1)
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = [line]
            quote = await agent_with_mock.run("single.txt")

        assert len(quote.lines) == 1
        assert quote.total_price > Decimal("0")

    @pytest.mark.asyncio
    async def test_pipeline_concurrency_safe(
        self,
        agent_with_mock: QuoteAgent,
        sample_rfq_lines: list[RFQLineItem],
    ) -> None:
        """All 5 lines looked up concurrently — results must be consistent."""
        with patch.object(
            agent_with_mock._parser, "parse", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = sample_rfq_lines
            quote = await agent_with_mock.run("fake.xlsx")

        assert len(quote.lines) == 5
        # Line ordering should be preserved by gather
        for i, line in enumerate(quote.lines):
            assert line.rfq_line.line_number == i + 1
