"""SAP connector live-path tests using a mocked pyrfc module."""

from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Install a fake pyrfc module so SAPMCP._get_conn() can import it
# ---------------------------------------------------------------------------
_FAKE_PYRFC = MagicMock()
_FAKE_PYRFC.Connection = MagicMock
sys.modules.setdefault("pyrfc", _FAKE_PYRFC)

from electronics_rfq_agent.mcp.sap import SAPMCP  # noqa: E402


@pytest.fixture
def sap_live() -> tuple[SAPMCP, MagicMock]:
    """SAPMCP instance in live mode with a mocked pyrfc Connection."""
    with patch.dict("os.environ", {"ERFA_USE_MOCK": "false"}):
        from electronics_rfq_agent.mcp.sap import SAPMCP

        sap = SAPMCP(
            host="sap.test.local",
            sysnr="00",
            client="100",
            user="rfcuser",
            password="rfcpass",
        )
    mock_conn = MagicMock()
    sap._conn = mock_conn
    return sap, mock_conn


# ---------------------------------------------------------------------------
# BAPI response fixtures
# ---------------------------------------------------------------------------

_BAPI_MATERIAL_RESPONSE = {
    "MATERIAL_GENERAL_DATA": {
        "MATERIAL": "RES-0402-10K",
        "MATL_DESC": "10K Resistor 0402",
        "MANUFACTURER": "Yageo",
    },
    "MATERIAL_PLANT_DATA": {
        "TOTAL_STOCK": 5000,
        "REPLENISHMENT_LEAD_TIME": 7,
    },
}

_BAPI_PRICING_RESPONSE = {
    "PRICINGDATA": {
        "PRICE": "0.01",
    }
}

_BAPI_GETLIST_RESPONSE = {
    "MATNRLIST": [
        {"MATNR": "RES-0402-10K"},
    ]
}


class TestSAPLivePaths:
    @pytest.mark.asyncio
    async def test_get_part_found(self, sap_live: tuple[SAPMCP, MagicMock]) -> None:
        sap, mock_conn = sap_live

        def _call_side_effect(bapi: str, **kwargs: object) -> dict[str, object]:
            if bapi == "BAPI_MATERIAL_GET_DETAIL":
                return _BAPI_MATERIAL_RESPONSE
            if bapi == "BAPI_MATERIAL_GETPRICINGINFO":
                return _BAPI_PRICING_RESPONSE
            return {}

        mock_conn.call.side_effect = _call_side_effect

        result = await sap.get_part("RES-0402-10K")
        assert result is not None
        assert result.part_number == "RES-0402-10K"
        assert result.description == "10K Resistor 0402"
        assert result.unit_price == Decimal("0.01")
        assert result.available_qty == 5000
        assert result.lead_time_days == 7
        assert result.manufacturer == "Yageo"

    @pytest.mark.asyncio
    async def test_get_part_not_found_abap_error(
        self, sap_live: tuple[SAPMCP, MagicMock]
    ) -> None:
        sap, mock_conn = sap_live

        class ABAPApplicationError(Exception):
            pass

        mock_conn.call.side_effect = ABAPApplicationError("Material not found")

        result = await sap.get_part("ZZZNOMATCH")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_part_connection_error_raises(
        self, sap_live: tuple[SAPMCP, MagicMock]
    ) -> None:
        sap, mock_conn = sap_live

        from electronics_rfq_agent.models import ERPConnectionError

        mock_conn.call.side_effect = ConnectionError("SAP unreachable")

        with pytest.raises(ERPConnectionError, match="SAP BAPI call failed"):
            await sap.get_part("RES-001")

    @pytest.mark.asyncio
    async def test_get_part_empty_material_data_returns_none(
        self, sap_live: tuple[SAPMCP, MagicMock]
    ) -> None:
        sap, mock_conn = sap_live
        mock_conn.call.return_value = {"MATERIAL_GENERAL_DATA": {}}

        result = await sap.get_part("RES-001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_price_direct_bapi(
        self, sap_live: tuple[SAPMCP, MagicMock]
    ) -> None:
        """get_price() should NOT call get_part() -- uses the pricing BAPI directly."""
        sap, mock_conn = sap_live
        mock_conn.call.return_value = _BAPI_PRICING_RESPONSE

        price = await sap.get_price("RES-0402-10K", 100)
        assert price == Decimal("0.01")

        # Verify only the pricing BAPI was called, not BAPI_MATERIAL_GET_DETAIL
        call_args = [str(c) for c in mock_conn.call.call_args_list]
        assert not any("BAPI_MATERIAL_GET_DETAIL" in c for c in call_args)

    @pytest.mark.asyncio
    async def test_get_price_not_found_returns_none(
        self, sap_live: tuple[SAPMCP, MagicMock]
    ) -> None:
        sap, mock_conn = sap_live
        mock_conn.call.return_value = {"PRICINGDATA": {}}

        price = await sap.get_price("ZZZNOMATCH", 1)
        assert price is None

    @pytest.mark.asyncio
    async def test_check_inventory_sufficient(
        self, sap_live: tuple[SAPMCP, MagicMock]
    ) -> None:
        sap, mock_conn = sap_live

        def _call_side_effect(bapi: str, **kwargs: object) -> dict[str, object]:
            if bapi == "BAPI_MATERIAL_GET_DETAIL":
                return _BAPI_MATERIAL_RESPONSE
            if bapi == "BAPI_MATERIAL_GETPRICINGINFO":
                return _BAPI_PRICING_RESPONSE
            return {}

        mock_conn.call.side_effect = _call_side_effect

        assert await sap.check_inventory("RES-0402-10K", 100) is True

    @pytest.mark.asyncio
    async def test_check_inventory_insufficient(
        self, sap_live: tuple[SAPMCP, MagicMock]
    ) -> None:
        sap, mock_conn = sap_live

        def _call_side_effect(bapi: str, **kwargs: object) -> dict[str, object]:
            if bapi == "BAPI_MATERIAL_GET_DETAIL":
                return {
                    "MATERIAL_GENERAL_DATA": {"MATERIAL": "RES-001", "MATL_DESC": "R"},
                    "MATERIAL_PLANT_DATA": {"TOTAL_STOCK": 10},
                }
            if bapi == "BAPI_MATERIAL_GETPRICINGINFO":
                return _BAPI_PRICING_RESPONSE
            return {}

        mock_conn.call.side_effect = _call_side_effect

        assert await sap.check_inventory("RES-001", 10000) is False

    @pytest.mark.asyncio
    async def test_search_parts_calls_getlist(
        self, sap_live: tuple[SAPMCP, MagicMock]
    ) -> None:
        sap, mock_conn = sap_live

        def _call_side_effect(bapi: str, **kwargs: object) -> dict[str, object]:
            if bapi == "BAPI_MATERIAL_GETLIST":
                return _BAPI_GETLIST_RESPONSE
            if bapi == "BAPI_MATERIAL_GET_DETAIL":
                return _BAPI_MATERIAL_RESPONSE
            if bapi == "BAPI_MATERIAL_GETPRICINGINFO":
                return _BAPI_PRICING_RESPONSE
            return {}

        mock_conn.call.side_effect = _call_side_effect

        results = await sap.search_parts("RES", limit=5)
        assert len(results) == 1
        assert results[0].part_number == "RES-0402-10K"

    def test_from_config(self) -> None:
        from electronics_rfq_agent.mcp.sap import SAPMCP
        from electronics_rfq_agent.models import ERPConfig

        cfg = ERPConfig(erp_type="sap", username="rfcuser", password="rfcpass")
        with patch.dict("os.environ", {"ERFA_USE_MOCK": "true"}):
            sap = SAPMCP.from_config(cfg)
        assert sap._user == "rfcuser"
        assert sap._password == "rfcpass"

    @pytest.mark.asyncio
    async def test_get_conn_wraps_pyrfc_in_to_thread(self) -> None:
        """_get_conn() must call asyncio.to_thread(pyrfc.Connection, ...)."""
        with patch.dict("os.environ", {"ERFA_USE_MOCK": "false"}):
            sap = SAPMCP(
                host="sap.test.local",
                sysnr="00",
                client="100",
                user="rfcuser",
                password="rfcpass",
            )

        mock_conn = MagicMock()

        async def fake_to_thread(func: object, **kwargs: object) -> MagicMock:
            if func is _FAKE_PYRFC.Connection:
                return mock_conn
            return await asyncio.get_running_loop().run_in_executor(None, func)  # type: ignore[arg-type]

        target = "electronics_rfq_agent.mcp.sap.asyncio.to_thread"
        with patch(target, side_effect=fake_to_thread) as mock_to_thread:
            conn = await sap._get_conn()

        assert conn is mock_conn
        assert mock_to_thread.call_args[0][0] is _FAKE_PYRFC.Connection

    @pytest.mark.asyncio
    async def test_get_conn_import_error_when_pyrfc_missing(self) -> None:
        """_get_conn() raises ImportError when pyrfc is not installed."""
        saved = sys.modules.pop("pyrfc", None)
        try:
            with patch.dict("os.environ", {"ERFA_USE_MOCK": "false"}):
                sap = SAPMCP(
                    host="sap.test.local",
                    sysnr="00",
                    client="100",
                    user="rfcuser",
                    password="rfcpass",
                )
            with pytest.raises(ImportError, match="pyrfc is required"):
                await sap._get_conn()
        finally:
            if saved is not None:
                sys.modules["pyrfc"] = saved
