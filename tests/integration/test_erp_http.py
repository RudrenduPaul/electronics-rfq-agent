"""HTTP-based ERP connector tests (Epicor, Oracle, Dynamics) using respx mocking."""

from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
import respx

from openquote.mcp.dynamics import DynamicsMCP
from openquote.mcp.epicor import EpicorMCP
from openquote.mcp.oracle import OracleMCP


# ---------------------------------------------------------------------------
# Epicor HTTP tests
# ---------------------------------------------------------------------------
class TestEpicorHTTP:
    @pytest.fixture
    def epicor(self) -> EpicorMCP:
        """Epicor instance pointing at a fake URL, no mock env var set."""
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "false"}):
            return EpicorMCP(
                base_url="https://epicor.test.local",
                api_key="dGVzdDp0ZXN0",
                company="EPIC",
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_parts_http(self, epicor: EpicorMCP) -> None:
        payload = {
            "value": [
                {
                    "PartNum": "RES-001",
                    "PartDescription": "Test Resistor",
                    "UnitPrice": "0.05",
                    "OnHandQty": 1000,
                    "LeadTime": 7,
                    "VendorName": "Yageo",
                }
            ]
        }
        respx.get(
            url__regex=r"https://epicor\.test\.local/api/v2/odata/EPIC/Erp\.BO\.PartSvc/Parts.*"
        ).mock(return_value=httpx.Response(200, json=payload))

        results = await epicor.search_parts("RES", limit=5)
        assert len(results) == 1
        assert results[0].part_number == "RES-001"
        assert results[0].unit_price == Decimal("0.05")
        await epicor.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_part_http(self, epicor: EpicorMCP) -> None:
        payload = {
            "PartNum": "RES-001",
            "PartDescription": "Test Resistor",
            "UnitPrice": "0.05",
            "OnHandQty": 500,
            "LeadTime": 7,
            "VendorName": "Yageo",
        }
        respx.get(
            url__regex=r"https://epicor\.test\.local/api/v2/odata/EPIC/Erp\.BO\.PartSvc/Parts.*"
        ).mock(return_value=httpx.Response(200, json=payload))

        result = await epicor.get_part("RES-001")
        assert result is not None
        assert result.part_number == "RES-001"
        await epicor.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_part_not_found_http(self, epicor: EpicorMCP) -> None:
        respx.get(
            url__regex=r"https://epicor\.test\.local/api/v2/odata/EPIC/Erp\.BO\.PartSvc/Parts.*"
        ).mock(return_value=httpx.Response(404))

        result = await epicor.get_part("ZZZNOMATCH")
        assert result is None
        await epicor.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_check_inventory_http(self, epicor: EpicorMCP) -> None:
        payload = {
            "PartNum": "RES-001",
            "PartDescription": "Test Resistor",
            "UnitPrice": "0.05",
            "OnHandQty": 500,
            "LeadTime": 7,
            "VendorName": "Yageo",
        }
        respx.get(
            url__regex=r"https://epicor\.test\.local/api/v2/odata/EPIC/Erp\.BO\.PartSvc/Parts.*"
        ).mock(return_value=httpx.Response(200, json=payload))

        result = await epicor.check_inventory("RES-001", 100)
        assert result is True
        await epicor.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_price_http(self, epicor: EpicorMCP) -> None:
        payload = {
            "PartNum": "RES-001",
            "PartDescription": "Test Resistor",
            "UnitPrice": "0.05",
            "OnHandQty": 500,
            "LeadTime": 7,
            "VendorName": "Yageo",
        }
        respx.get(
            url__regex=r"https://epicor\.test\.local/api/v2/odata/EPIC/Erp\.BO\.PartSvc/Parts.*"
        ).mock(return_value=httpx.Response(200, json=payload))

        price = await epicor.get_price("RES-001", 10)
        assert price == Decimal("0.05")
        await epicor.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_price_not_found_returns_none_http(
        self, epicor: EpicorMCP
    ) -> None:
        respx.get(
            url__regex=r"https://epicor\.test\.local/api/v2/odata/EPIC/Erp\.BO\.PartSvc/Parts.*"
        ).mock(return_value=httpx.Response(404))

        price = await epicor.get_price("ZZZNOMATCH", 1)
        assert price is None
        await epicor.close()

    def test_get_client_creates_once(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "false"}):
            epicor = EpicorMCP(
                base_url="https://epicor.test.local",
                api_key="key123",
            )
        c1 = epicor._get_client()
        c2 = epicor._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "true"}):
            async with EpicorMCP() as epicor:
                assert epicor is not None
        # After exit, client should be None
        assert epicor._client is None


# ---------------------------------------------------------------------------
# Oracle HTTP tests
# ---------------------------------------------------------------------------
class TestOracleMCPHTTP:
    @pytest.fixture
    def oracle(self) -> OracleMCP:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "false"}):
            return OracleMCP(
                base_url="https://oracle.test.local",
                client_id="client123",
                client_secret="secret456",
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_parts_http(self, oracle: OracleMCP) -> None:
        # Mock token endpoint
        respx.post("https://oracle.test.local/oauth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "test-token"})
        )
        # Mock items endpoint
        respx.get(
            url__regex=r"https://oracle\.test\.local/fscmRestApi/resources/.*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "ItemNumber": "CAP-001",
                            "Description": "Test Capacitor",
                            "ListPrice": "0.02",
                            "OnHandQuantity": 2000,
                            "LeadTime": 5,
                            "Manufacturer": "Murata",
                        }
                    ]
                },
            )
        )
        results = await oracle.search_parts("CAP", limit=5)
        assert len(results) == 1
        assert results[0].part_number == "CAP-001"
        await oracle.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_part_http(self, oracle: OracleMCP) -> None:
        oracle._access_token = "test-token"  # skip token fetch
        respx.get(
            url__regex=r"https://oracle\.test\.local/fscmRestApi/resources/.*/items/CAP-001"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ItemNumber": "CAP-001",
                    "Description": "Test Capacitor",
                    "ListPrice": "0.02",
                    "OnHandQuantity": 2000,
                    "LeadTime": 5,
                    "Manufacturer": "Murata",
                },
            )
        )
        result = await oracle.get_part("CAP-001")
        assert result is not None
        assert result.part_number == "CAP-001"
        await oracle.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_part_not_found_http(self, oracle: OracleMCP) -> None:
        oracle._access_token = "test-token"
        respx.get(
            url__regex=r"https://oracle\.test\.local/fscmRestApi/resources/.*/items/.*"
        ).mock(return_value=httpx.Response(404))

        result = await oracle.get_part("ZZZNOMATCH")
        assert result is None
        await oracle.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_check_inventory_http(self, oracle: OracleMCP) -> None:
        oracle._access_token = "test-token"
        respx.get(
            url__regex=r"https://oracle\.test\.local/fscmRestApi/resources/.*/items/.*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ItemNumber": "CAP-001",
                    "Description": "Test Cap",
                    "ListPrice": "0.02",
                    "OnHandQuantity": 500,
                    "LeadTime": 3,
                    "Manufacturer": "Murata",
                },
            )
        )
        result = await oracle.check_inventory("CAP-001", 100)
        assert result is True
        await oracle.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_price_http(self, oracle: OracleMCP) -> None:
        oracle._access_token = "test-token"
        respx.get(
            url__regex=r"https://oracle\.test\.local/fscmRestApi/resources/.*/items/.*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ItemNumber": "CAP-001",
                    "Description": "Test Cap",
                    "ListPrice": "0.025",
                    "OnHandQuantity": 500,
                    "LeadTime": 3,
                    "Manufacturer": "Murata",
                },
            )
        )
        price = await oracle.get_price("CAP-001", 10)
        assert price == Decimal("0.025")
        await oracle.close()

    def test_map_item_defaults(self) -> None:
        result = OracleMCP._map_item({})
        assert result.part_number == ""
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0

    def test_map_item_full(self) -> None:
        result = OracleMCP._map_item(
            {
                "ItemNumber": "IC-001",
                "Description": "Test IC",
                "ListPrice": "1.50",
                "OnHandQuantity": 100,
                "LeadTime": 14,
                "Manufacturer": "TI",
            }
        )
        assert result.part_number == "IC-001"
        assert result.unit_price == Decimal("1.50")
        assert result.lead_time_days == 14

    @pytest.mark.asyncio
    async def test_ensure_token_caches(self, oracle: OracleMCP) -> None:
        oracle._access_token = "cached-token"
        # Should return without any HTTP call
        token = await oracle._ensure_token()
        assert token == "cached-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_token_fetches_from_endpoint(self, oracle: OracleMCP) -> None:
        """Token is fetched from OAuth endpoint and cached when not already set."""
        respx.post("https://oracle.test.local/oauth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "fresh-token"})
        )
        token = await oracle._ensure_token()
        assert token == "fresh-token"
        assert oracle._access_token == "fresh-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_token_not_refetched_on_second_call(
        self, oracle: OracleMCP
    ) -> None:
        """Cached token is reused on subsequent calls without hitting the network."""
        respx.post("https://oracle.test.local/oauth/token").mock(
            return_value=httpx.Response(200, json={"access_token": "token-1"})
        )
        first = await oracle._ensure_token()
        # Second call should not trigger another request
        second = await oracle._ensure_token()
        assert first == second == "token-1"
        assert respx.calls.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_token_401_raises(self, oracle: OracleMCP) -> None:
        """401 from the token endpoint raises httpx.HTTPStatusError."""
        respx.post("https://oracle.test.local/oauth/token").mock(
            return_value=httpx.Response(401)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await oracle._ensure_token()


# ---------------------------------------------------------------------------
# Dynamics HTTP tests
# ---------------------------------------------------------------------------
class TestDynamicsMCPHTTP:
    @pytest.fixture
    def dynamics(self) -> DynamicsMCP:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "false"}):
            return DynamicsMCP(
                tenant_id="tenant123",
                client_id="client456",
                client_secret="secret789",
                base_url="https://org.test.crm.dynamics.com",
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_parts_http(self, dynamics: DynamicsMCP) -> None:
        dynamics._access_token = "test-token"
        respx.get(
            url__regex=r"https://org\.test\.crm\.dynamics\.com/api/data/v9\.2/products.*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "productnumber": "IND-001",
                            "name": "Test Inductor",
                            "price": "0.10",
                            "quantityonhand": 300,
                            "leadtime": 10,
                            "suppliername": "TDK",
                        }
                    ]
                },
            )
        )
        results = await dynamics.search_parts("IND", limit=5)
        assert len(results) == 1
        assert results[0].part_number == "IND-001"
        await dynamics.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_part_http(self, dynamics: DynamicsMCP) -> None:
        dynamics._access_token = "test-token"
        respx.get(
            url__regex=r"https://org\.test\.crm\.dynamics\.com/api/data/v9\.2/products.*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "productnumber": "IND-001",
                            "name": "Test Inductor",
                            "price": "0.10",
                            "quantityonhand": 300,
                            "leadtime": 10,
                            "suppliername": "TDK",
                        }
                    ]
                },
            )
        )
        result = await dynamics.get_part("IND-001")
        assert result is not None
        assert result.part_number == "IND-001"
        await dynamics.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_part_not_found_http(self, dynamics: DynamicsMCP) -> None:
        dynamics._access_token = "test-token"
        respx.get(
            url__regex=r"https://org\.test\.crm\.dynamics\.com/api/data/v9\.2/products.*"
        ).mock(return_value=httpx.Response(200, json={"value": []}))

        result = await dynamics.get_part("ZZZNOMATCH")
        assert result is None
        await dynamics.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_check_inventory_http(self, dynamics: DynamicsMCP) -> None:
        dynamics._access_token = "test-token"
        respx.get(
            url__regex=r"https://org\.test\.crm\.dynamics\.com/api/data/v9\.2/products.*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "productnumber": "IND-001",
                            "name": "Inductor",
                            "price": "0.10",
                            "quantityonhand": 1000,
                            "leadtime": 5,
                            "suppliername": "TDK",
                        }
                    ]
                },
            )
        )
        result = await dynamics.check_inventory("IND-001", 100)
        assert result is True
        await dynamics.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_price_http(self, dynamics: DynamicsMCP) -> None:
        dynamics._access_token = "test-token"
        respx.get(
            url__regex=r"https://org\.test\.crm\.dynamics\.com/api/data/v9\.2/products.*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "productnumber": "IND-001",
                            "name": "Inductor",
                            "price": "0.15",
                            "quantityonhand": 500,
                            "leadtime": 5,
                            "suppliername": "TDK",
                        }
                    ]
                },
            )
        )
        price = await dynamics.get_price("IND-001", 5)
        assert price == Decimal("0.15")
        await dynamics.close()

    def test_map_product_defaults(self) -> None:
        result = DynamicsMCP._map_product({})
        assert result.part_number == ""
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0

    def test_map_product_full(self) -> None:
        result = DynamicsMCP._map_product(
            {
                "productnumber": "MOSFET-001",
                "name": "N-Channel MOSFET",
                "price": "0.85",
                "quantityonhand": 200,
                "leadtime": 14,
                "suppliername": "Infineon",
            }
        )
        assert result.part_number == "MOSFET-001"
        assert result.unit_price == Decimal("0.85")
        assert result.manufacturer == "Infineon"

    @pytest.mark.asyncio
    async def test_ensure_token_caches(self, dynamics: DynamicsMCP) -> None:
        dynamics._access_token = "cached-token"
        token = await dynamics._ensure_token()
        assert token == "cached-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_token_fetches_from_endpoint(
        self, dynamics: DynamicsMCP
    ) -> None:
        """Token is fetched from Azure AD endpoint and cached when not already set."""
        token_url = "https://login.microsoftonline.com/tenant123/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=httpx.Response(200, json={"access_token": "dyn-token"})
        )
        token = await dynamics._ensure_token()
        assert token == "dyn-token"
        assert dynamics._access_token == "dyn-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_token_not_refetched_on_second_call(
        self, dynamics: DynamicsMCP
    ) -> None:
        """Cached token is reused on subsequent calls without hitting the network."""
        token_url = "https://login.microsoftonline.com/tenant123/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=httpx.Response(200, json={"access_token": "dyn-token-1"})
        )
        first = await dynamics._ensure_token()
        second = await dynamics._ensure_token()
        assert first == second == "dyn-token-1"
        assert respx.calls.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_token_401_raises(self, dynamics: DynamicsMCP) -> None:
        """401 from Azure AD token endpoint raises httpx.HTTPStatusError."""
        token_url = "https://login.microsoftonline.com/tenant123/oauth2/v2.0/token"
        respx.post(token_url).mock(return_value=httpx.Response(401))
        with pytest.raises(httpx.HTTPStatusError):
            await dynamics._ensure_token()

    def test_get_client_creates_once(self, dynamics: DynamicsMCP) -> None:
        c1 = dynamics._get_client("token")
        c2 = dynamics._get_client("token")
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_with_mock_env(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "true"}):
            dyn = DynamicsMCP()
        results = await dyn.search_parts("RES", limit=3)
        assert len(results) > 0
