"""HTTP-based ERP connector tests (Epicor, Oracle, Dynamics) using respx mocking."""

from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
import respx

from electronics_rfq_agent.mcp.dynamics import DynamicsMCP
from electronics_rfq_agent.mcp.epicor import EpicorMCP
from electronics_rfq_agent.mcp.oracle import OracleMCP


# ---------------------------------------------------------------------------
# Epicor HTTP tests
# ---------------------------------------------------------------------------
class TestEpicorHTTP:
    @pytest.fixture
    def epicor(self) -> EpicorMCP:
        """Epicor instance pointing at a fake URL, no mock env var set."""
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "false"}):
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
    async def test_get_part_url_encodes_slash_in_part_number(
        self, epicor: EpicorMCP
    ) -> None:
        """Part numbers containing '/' must be percent-encoded so they don't
        corrupt the OData URL path (A/B-001 would otherwise be split at '/')."""
        payload = {
            "PartNum": "A/B-001",
            "PartDescription": "Slash Part",
            "UnitPrice": "1.00",
            "OnHandQty": 10,
            "LeadTime": 0,
            "VendorName": "Acme",
        }
        respx.get(
            url__regex=r"https://epicor\.test\.local/api/v2/odata/EPIC/Erp\.BO\.PartSvc/Parts.*"
        ).mock(return_value=httpx.Response(200, json=payload))

        result = await epicor.get_part("A/B-001")
        assert result is not None
        assert result.part_number == "A/B-001"
        # Verify the actual request URL percent-encoded the slash
        last_request = respx.calls.last.request
        assert "%2F" in str(last_request.url)
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
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "false"}):
            epicor = EpicorMCP(
                base_url="https://epicor.test.local",
                api_key="key123",
            )
        c1 = epicor._get_client()
        c2 = epicor._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self) -> None:
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "true"}):
            epicor = EpicorMCP()
        assert epicor is not None
        await epicor.close()
        assert epicor._client is None

    def test_map_part_defaults(self) -> None:
        result = EpicorMCP._map_part({})
        assert result.part_number == ""
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0

    def test_map_part_with_null_fields(self) -> None:
        result = EpicorMCP._map_part(
            {"UnitPrice": None, "OnHandQty": None, "LeadTime": None}
        )
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0


# ---------------------------------------------------------------------------
# Oracle HTTP tests
# ---------------------------------------------------------------------------
class TestOracleMCPHTTP:
    @pytest.fixture
    def oracle(self) -> OracleMCP:
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "false"}):
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

    @pytest.mark.asyncio
    async def test_get_price_http_returns_none(self, oracle: OracleMCP) -> None:
        # Oracle SCM REST API has no separate volume-pricing endpoint; get_price()
        # returns None so the agent falls back to unit_price from get_part().
        price = await oracle.get_price("CAP-001", 10)
        assert price is None
        await oracle.close()

    def test_map_item_defaults(self) -> None:
        result = OracleMCP._map_item({})
        assert result.part_number == ""
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0

    def test_map_item_with_null_fields(self) -> None:
        result = OracleMCP._map_item(
            {
                "ItemNumber": "X",
                "ListPrice": None,
                "OnHandQuantity": None,
                "LeadTime": None,
            }
        )
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0
        assert result.lead_time_days == 0

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

    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_token_refreshes_on_expiry(self, oracle: OracleMCP) -> None:
        """Expired token (token_expires_at in the past) triggers a new fetch."""
        oracle._access_token = "old-token"
        oracle._token_expires_at = 0.0  # force expired
        respx.post("https://oracle.test.local/oauth/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "refreshed-token", "expires_in": 3600}
            )
        )
        token = await oracle._ensure_token()
        assert token == "refreshed-token"
        assert oracle._access_token == "refreshed-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_call_uses_refreshed_token(self, oracle: OracleMCP) -> None:
        """After a token refresh, search_parts must send the NEW token — not the
        stale one that was embedded in a cached httpx.AsyncClient header."""
        # First call: token fetch + search
        respx.post("https://oracle.test.local/oauth/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "first-token", "expires_in": 3600}
            )
        )
        respx.get(url__regex=r"https://oracle\.test\.local/fscmRestApi/.*").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        await oracle.search_parts("RES")

        # Expire the token and refresh to a new one
        oracle._token_expires_at = 0.0
        respx.post("https://oracle.test.local/oauth/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "second-token", "expires_in": 3600}
            )
        )
        await oracle.search_parts("CAP")

        # The second API request must carry the NEW token, not the old one
        last_api_call = respx.calls[-1].request
        assert last_api_call.headers["Authorization"] == "Bearer second-token"
        await oracle.close()


# ---------------------------------------------------------------------------
# Dynamics HTTP tests
# ---------------------------------------------------------------------------
class TestDynamicsMCPHTTP:
    @pytest.fixture
    def dynamics(self) -> DynamicsMCP:
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "false"}):
            return DynamicsMCP(
                tenant_id="12345678-1234-1234-1234-123456789abc",
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

    @pytest.mark.asyncio
    async def test_get_price_http_returns_none(self, dynamics: DynamicsMCP) -> None:
        # Dynamics 365 Sales has no volume-pricing API endpoint;
        # get_price() returns None so agent falls back to unit_price from get_part().
        price = await dynamics.get_price("IND-001", 5)
        assert price is None
        await dynamics.close()

    def test_map_product_defaults(self) -> None:
        result = DynamicsMCP._map_product({})
        assert result.part_number == ""
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0

    def test_map_product_with_null_fields(self) -> None:
        result = DynamicsMCP._map_product(
            {
                "productnumber": "X",
                "price": None,
                "quantityonhand": None,
                "leadtime": None,
            }
        )
        assert result.unit_price == Decimal("0")
        assert result.available_qty == 0
        assert result.lead_time_days == 0

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
        token_url = "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789abc/oauth2/v2.0/token"
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
        token_url = "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789abc/oauth2/v2.0/token"
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
        token_url = "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789abc/oauth2/v2.0/token"
        respx.post(token_url).mock(return_value=httpx.Response(401))
        with pytest.raises(httpx.HTTPStatusError):
            await dynamics._ensure_token()

    def test_get_client_creates_once(self, dynamics: DynamicsMCP) -> None:
        c1 = dynamics._get_client()
        c2 = dynamics._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_with_mock_env(self) -> None:
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "true"}):
            dyn = DynamicsMCP()
        results = await dyn.search_parts("RES", limit=3)
        assert len(results) > 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_token_refreshes_on_expiry(
        self, dynamics: DynamicsMCP
    ) -> None:
        """Expired token triggers a new Azure AD fetch."""
        dynamics._access_token = "old-token"
        dynamics._token_expires_at = 0.0  # force expired
        token_url = "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789abc/oauth2/v2.0/token"
        respx.post(token_url).mock(
            return_value=httpx.Response(
                200, json={"access_token": "refreshed-token", "expires_in": 3600}
            )
        )
        token = await dynamics._ensure_token()
        assert token == "refreshed-token"
        assert dynamics._access_token == "refreshed-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_call_uses_refreshed_token(self, dynamics: DynamicsMCP) -> None:
        """After a token refresh, search_parts must send the NEW token — not the
        stale one embedded in a cached httpx.AsyncClient header."""
        token_url = "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789abc/oauth2/v2.0/token"

        # First call: token fetch + search
        respx.post(token_url).mock(
            return_value=httpx.Response(
                200, json={"access_token": "first-token", "expires_in": 3600}
            )
        )
        respx.get(
            url__regex=r"https://org\.test\.crm\.dynamics\.com/api/data/v9\.2/products.*"
        ).mock(return_value=httpx.Response(200, json={"value": []}))
        await dynamics.search_parts("RES")

        # Expire the token and refresh to a new one
        dynamics._token_expires_at = 0.0
        respx.post(token_url).mock(
            return_value=httpx.Response(
                200, json={"access_token": "second-token", "expires_in": 3600}
            )
        )
        await dynamics.search_parts("CAP")

        # The second API request must carry the NEW token, not the old one
        last_api_call = respx.calls[-1].request
        assert last_api_call.headers["Authorization"] == "Bearer second-token"
        await dynamics.close()


# ---------------------------------------------------------------------------
# Regression tests for bug fixes
# ---------------------------------------------------------------------------


class TestDynamicsMCPValidation:
    def test_empty_tenant_id_raises_in_non_mock_mode(self) -> None:
        """Empty tenant_id must raise ValueError immediately."""
        with pytest.raises(ValueError, match="tenant_id must not be empty"):
            DynamicsMCP(
                tenant_id="",
                client_id="client-id",
                client_secret="secret",
                base_url="https://org.test.crm.dynamics.com",
            )

    def test_none_tenant_id_raises_in_non_mock_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No tenant_id and no env var must raise ValueError immediately."""
        monkeypatch.delenv("ERFA_DYNAMICS_TENANT_ID", raising=False)
        with pytest.raises(ValueError, match="tenant_id must not be empty"):
            DynamicsMCP(
                client_id="client-id",
                client_secret="secret",
                base_url="https://org.test.crm.dynamics.com",
            )

    def test_invalid_uuid_tenant_id_raises(self) -> None:
        """Non-UUID tenant_id must raise ValueError."""
        with pytest.raises(ValueError, match="valid UUID"):
            DynamicsMCP(
                tenant_id="not-a-uuid",
                client_id="client-id",
                client_secret="secret",
                base_url="https://org.test.crm.dynamics.com",
            )


class TestOAuthExpiresIn:
    """Regression tests for the expires_in floor clamp in _oauth.py."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_short_expires_in_does_not_put_token_in_past(self) -> None:
        """expires_in=30 (< 60s buffer) must not produce a past expires_at."""
        import time

        from electronics_rfq_agent.mcp._oauth import fetch_client_credentials_token

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "tok", "expires_in": 30}
            )
        )
        before = time.monotonic()
        _, expires_at = await fetch_client_credentials_token(
            token_url="https://auth.example.com/token",
            client_id="cid",
            client_secret="sec",
        )
        assert expires_at > before, (
            "expires_at must be in the future even when expires_in < 60"
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_zero_expires_in_does_not_put_token_in_past(self) -> None:
        """expires_in=0 must not produce a past expires_at."""
        import time

        from electronics_rfq_agent.mcp._oauth import fetch_client_credentials_token

        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "tok", "expires_in": 0}
            )
        )
        before = time.monotonic()
        _, expires_at = await fetch_client_credentials_token(
            token_url="https://auth.example.com/token",
            client_id="cid",
            client_secret="sec",
        )
        assert expires_at > before, (
            "expires_at must be in the future even when expires_in=0"
        )


# ---------------------------------------------------------------------------
# get_price() override regression tests
# (Bug: base class called get_part() a second time for Oracle/Dynamics HTTP path)
# ---------------------------------------------------------------------------


class TestOracleGetPriceHTTPPath:
    """OracleMCP.get_price() must return None for non-mock HTTP path.

    Prior to the fix, OracleMCP inherited ERPMCPServer.get_price() which
    called get_part() again — one redundant API call per line item.
    """

    @pytest.fixture
    def oracle(self) -> OracleMCP:
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "false"}):
            return OracleMCP(
                base_url="https://oracle.test.local",
                client_id="cid",
                client_secret="sec",
            )

    @pytest.mark.asyncio
    async def test_get_price_returns_none_for_http_path(
        self, oracle: OracleMCP
    ) -> None:
        """Non-mock get_price() must return None (no extra API call)."""
        price = await oracle.get_price("RES-001", 100)
        assert price is None

    @pytest.mark.asyncio
    async def test_get_price_mock_path_still_returns_value(self) -> None:
        """Mock path must still provide tier pricing."""
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "true"}):
            oracle = OracleMCP(
                base_url="https://oracle.test.local",
                client_id="cid",
                client_secret="sec",
            )
        # Mock catalog has RES-0402-10K-1PCT; qty=1000 gets 20% discount tier
        price = await oracle.get_price("RES-0402-10K-1PCT", 1000)
        assert price is not None
        await oracle.close()


class TestDynamicsGetPriceHTTPPath:
    """DynamicsMCP.get_price() must return None for non-mock HTTP path."""

    @pytest.fixture
    def dynamics(self) -> DynamicsMCP:
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "false"}):
            return DynamicsMCP(
                tenant_id="12345678-1234-1234-1234-123456789abc",
                client_id="cid",
                client_secret="sec",
                base_url="https://org.test.crm.dynamics.com",
            )

    @pytest.mark.asyncio
    async def test_get_price_returns_none_for_http_path(
        self, dynamics: DynamicsMCP
    ) -> None:
        """Non-mock get_price() must return None (no extra API call)."""
        price = await dynamics.get_price("PROD-001", 50)
        assert price is None

    @pytest.mark.asyncio
    async def test_get_price_mock_path_still_returns_value(self) -> None:
        """Mock path must still provide tier pricing."""
        with patch.dict(os.environ, {"ERFA_USE_MOCK": "true"}):
            dynamics = DynamicsMCP(
                tenant_id="12345678-1234-1234-1234-123456789abc",
                client_id="cid",
                client_secret="sec",
                base_url="https://org.test.crm.dynamics.com",
            )
        price = await dynamics.get_price("RES-0402-10K-1PCT", 1000)
        assert price is not None
        await dynamics.close()
