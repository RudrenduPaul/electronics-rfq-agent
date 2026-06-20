from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

import pytest

from electronics_rfq_agent.mcp.epicor import EpicorMCP
from electronics_rfq_agent.mcp.mock.backend import MockERP


class TestMockERPSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, mock_erp: MockERP) -> None:
        results = await mock_erp.search_parts("RES", limit=10)
        assert len(results) > 0
        assert all(r.part_number for r in results)

    @pytest.mark.asyncio
    async def test_search_fuzzy_case_insensitive(self, mock_erp: MockERP) -> None:
        lower = await mock_erp.search_parts("res", limit=5)
        upper = await mock_erp.search_parts("RES", limit=5)
        assert len(lower) == len(upper)

    @pytest.mark.asyncio
    async def test_search_limit_respected(self, mock_erp: MockERP) -> None:
        results = await mock_erp.search_parts("", limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_no_results_returns_empty(self, mock_erp: MockERP) -> None:
        results = await mock_erp.search_parts("ZZZNOMATCHXXX999", limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_by_description(self, mock_erp: MockERP) -> None:
        results = await mock_erp.search_parts("capacitor", limit=10)
        assert any("capacitor" in r.description.lower() for r in results)

    @pytest.mark.asyncio
    async def test_search_by_part_prefix(self, mock_erp: MockERP) -> None:
        results = await mock_erp.search_parts("CAP-", limit=10)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_empty_string_returns_all_up_to_limit(
        self, mock_erp: MockERP
    ) -> None:
        results = await mock_erp.search_parts("", limit=10)
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_search_results_have_required_fields(self, mock_erp: MockERP) -> None:
        results = await mock_erp.search_parts("RES", limit=5)
        for r in results:
            assert r.part_number
            assert r.description is not None
            assert r.unit_price >= Decimal("0")
            assert r.available_qty >= 0
            assert r.lead_time_days >= 0
            assert r.manufacturer


class TestMockERPGetPart:
    @pytest.mark.asyncio
    async def test_get_existing_part(self, mock_erp: MockERP) -> None:
        result = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert result is not None
        assert result.part_number == "RES-0402-10K-1PCT"

    @pytest.mark.asyncio
    async def test_get_all_required_parts(self, mock_erp: MockERP) -> None:
        for pn in [
            "RES-0402-10K-1PCT",
            "CAP-100NF-50V-X7R-0402",
            "IC-LM358-SOIC8",
            "XTAL-16MHZ-SMD",
        ]:
            result = await mock_erp.get_part(pn)
            assert result is not None, f"Part {pn} should be in catalog"

    @pytest.mark.asyncio
    async def test_get_nonexistent_part_returns_none(self, mock_erp: MockERP) -> None:
        result = await mock_erp.get_part("ZZZNOMATCH-XXYYZZ-999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_part_case_insensitive(self, mock_erp: MockERP) -> None:
        upper = await mock_erp.get_part("RES-0402-10K-1PCT")
        lower = await mock_erp.get_part("res-0402-10k-1pct")
        assert upper is not None
        assert lower is not None
        assert upper.part_number == lower.part_number

    @pytest.mark.asyncio
    async def test_get_part_strips_whitespace(self, mock_erp: MockERP) -> None:
        result = await mock_erp.get_part("  RES-0402-10K-1PCT  ")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_part_returns_erp_part_result(self, mock_erp: MockERP) -> None:
        from electronics_rfq_agent.models import ERPPartResult

        result = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert isinstance(result, ERPPartResult)


class TestMockERPInventory:
    @pytest.mark.asyncio
    async def test_check_inventory_sufficient(self, mock_erp: MockERP) -> None:
        # RES-0402-10K-1PCT has 5000 available
        result = await mock_erp.check_inventory("RES-0402-10K-1PCT", 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_inventory_exact_match(self, mock_erp: MockERP) -> None:
        part = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert part is not None
        result = await mock_erp.check_inventory("RES-0402-10K-1PCT", part.available_qty)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_inventory_insufficient(self, mock_erp: MockERP) -> None:
        result = await mock_erp.check_inventory("RES-0402-10K-1PCT", 9_999_999)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_inventory_nonexistent_returns_false(
        self, mock_erp: MockERP
    ) -> None:
        result = await mock_erp.check_inventory("ZZZNOMATCH", 1)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_inventory_zero_qty_always_true(
        self, mock_erp: MockERP
    ) -> None:
        # 0 requested <= any available qty
        result = await mock_erp.check_inventory("RES-0402-10K-1PCT", 0)
        assert result is True


class TestMockERPPrice:
    @pytest.mark.asyncio
    async def test_get_price_existing_part(self, mock_erp: MockERP) -> None:
        price = await mock_erp.get_price("RES-0402-10K-1PCT", 1)
        assert price is not None
        assert price > Decimal("0")

    @pytest.mark.asyncio
    async def test_get_price_qty_1_is_base_price(self, mock_erp: MockERP) -> None:
        part = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert part is not None
        price = await mock_erp.get_price("RES-0402-10K-1PCT", 1)
        assert price == part.unit_price

    @pytest.mark.asyncio
    async def test_get_price_qty_10_discount(self, mock_erp: MockERP) -> None:
        part = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert part is not None
        price = await mock_erp.get_price("RES-0402-10K-1PCT", 10)
        assert price == part.unit_price * Decimal("0.95")

    @pytest.mark.asyncio
    async def test_get_price_qty_100_discount(self, mock_erp: MockERP) -> None:
        part = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert part is not None
        price = await mock_erp.get_price("RES-0402-10K-1PCT", 100)
        assert price == part.unit_price * Decimal("0.90")

    @pytest.mark.asyncio
    async def test_get_price_qty_1000_discount(self, mock_erp: MockERP) -> None:
        part = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert part is not None
        price = await mock_erp.get_price("RES-0402-10K-1PCT", 1000)
        assert price == part.unit_price * Decimal("0.80")

    @pytest.mark.asyncio
    async def test_volume_discount_applied(self, mock_erp: MockERP) -> None:
        price_1 = await mock_erp.get_price("RES-0402-10K-1PCT", 1)
        price_1000 = await mock_erp.get_price("RES-0402-10K-1PCT", 1000)
        assert price_1 is not None
        assert price_1000 is not None
        assert price_1000 < price_1

    @pytest.mark.asyncio
    async def test_get_price_nonexistent_returns_none(self, mock_erp: MockERP) -> None:
        price = await mock_erp.get_price("ZZZNOMATCH-XYZ", 1)
        assert price is None

    @pytest.mark.asyncio
    async def test_price_qty_9_is_base(self, mock_erp: MockERP) -> None:
        # qty=9 is below threshold of 10, so base price
        part = await mock_erp.get_part("RES-0402-10K-1PCT")
        assert part is not None
        price = await mock_erp.get_price("RES-0402-10K-1PCT", 9)
        assert price == part.unit_price


class TestMockERPCount:
    def test_catalog_has_200_parts(self, mock_erp: MockERP) -> None:
        assert mock_erp.part_count() == 200


class TestMockERPContextManager:
    @pytest.mark.asyncio
    async def test_context_manager_enter_exit(self) -> None:
        async with MockERP() as erp:
            assert erp is not None
            results = await erp.search_parts("RES", limit=1)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_close_method_does_not_raise(self) -> None:
        erp = MockERP()
        await erp.close()  # Should not raise


class TestEpicorMCPWithMock:
    @pytest.fixture
    def epicor_mock(self) -> EpicorMCP:
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "true"}):
            return EpicorMCP()

    @pytest.mark.asyncio
    async def test_search_delegates_to_mock(self, epicor_mock: EpicorMCP) -> None:
        results = await epicor_mock.search_parts("RES", limit=5)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_get_part_delegates_to_mock(self, epicor_mock: EpicorMCP) -> None:
        result = await epicor_mock.get_part("RES-0402-10K-1PCT")
        assert result is not None
        assert result.part_number == "RES-0402-10K-1PCT"

    @pytest.mark.asyncio
    async def test_get_part_not_found(self, epicor_mock: EpicorMCP) -> None:
        result = await epicor_mock.get_part("ZZZNOMATCH")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_inventory_delegates(self, epicor_mock: EpicorMCP) -> None:
        result = await epicor_mock.check_inventory("RES-0402-10K-1PCT", 100)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_price_delegates(self, epicor_mock: EpicorMCP) -> None:
        price = await epicor_mock.get_price("RES-0402-10K-1PCT", 1)
        assert price is not None
        assert price > Decimal("0")

    @pytest.mark.asyncio
    async def test_close_releases_client(self, epicor_mock: EpicorMCP) -> None:
        await epicor_mock.close()
        assert epicor_mock._client is None

    def test_map_part_static_method(self) -> None:
        data = {
            "PartNum": "TEST-001",
            "PartDescription": "Test Part",
            "UnitPrice": "1.50",
            "OnHandQty": 100,
            "LeadTime": 7,
            "VendorName": "TestVendor",
        }
        result = EpicorMCP._map_part(data)
        assert result.part_number == "TEST-001"
        assert result.description == "Test Part"
        assert result.unit_price == Decimal("1.50")
        assert result.available_qty == 100
        assert result.lead_time_days == 7
        assert result.manufacturer == "TestVendor"

    def test_map_part_defaults_missing_fields(self) -> None:
        result = EpicorMCP._map_part({})
        assert result.part_number == ""
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0
