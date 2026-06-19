from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

import pytest

from openquote.mcp.sap import SAPMCP


@pytest.fixture
def sap_mock() -> SAPMCP:
    with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "true"}):
        return SAPMCP()


class TestSAPMCPInit:
    def test_uses_mock_when_env_set(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "true"}):
            sap = SAPMCP()
        assert sap._mock is not None

    def test_no_mock_when_env_not_set(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "false"}):
            sap = SAPMCP()
        assert sap._mock is None

    def test_accepts_constructor_params(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "false"}):
            sap = SAPMCP(
                host="sap.test",
                sysnr="00",
                client="100",
                user="rfcuser",
                password="secret",
            )
        assert sap._host == "sap.test"
        assert sap._sysnr == "00"
        assert sap._client == "100"
        assert sap._user == "rfcuser"
        assert sap._password == "secret"

    def test_default_plant(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "true"}):
            sap = SAPMCP()
        assert sap._plant == "0001"

    def test_custom_plant(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "true"}):
            sap = SAPMCP(plant="1000")
        assert sap._plant == "1000"


class TestSAPMCPWithMock:
    @pytest.mark.asyncio
    async def test_search_delegates_to_mock(self, sap_mock: SAPMCP) -> None:
        results = await sap_mock.search_parts("RES", limit=5)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_empty_returns_results(self, sap_mock: SAPMCP) -> None:
        results = await sap_mock.search_parts("", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_get_part_delegates_to_mock(self, sap_mock: SAPMCP) -> None:
        result = await sap_mock.get_part("RES-0402-10K-1PCT")
        assert result is not None
        assert result.part_number == "RES-0402-10K-1PCT"

    @pytest.mark.asyncio
    async def test_get_part_not_found_returns_none(self, sap_mock: SAPMCP) -> None:
        result = await sap_mock.get_part("ZZZNOMATCH-XXYYZZ")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_inventory_delegates_to_mock(self, sap_mock: SAPMCP) -> None:
        result = await sap_mock.check_inventory("RES-0402-10K-1PCT", 100)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_inventory_delegates_not_found(self, sap_mock: SAPMCP) -> None:
        result = await sap_mock.check_inventory("ZZZNOMATCH", 999999)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_price_delegates_to_mock(self, sap_mock: SAPMCP) -> None:
        price = await sap_mock.get_price("RES-0402-10K-1PCT", 1)
        assert price is not None
        assert price > Decimal("0")

    @pytest.mark.asyncio
    async def test_get_price_not_found_returns_none(self, sap_mock: SAPMCP) -> None:
        price = await sap_mock.get_price("ZZZNOMATCH-XYZ", 1)
        assert price is None

    @pytest.mark.asyncio
    async def test_close_resets_conn(self, sap_mock: SAPMCP) -> None:
        from unittest.mock import MagicMock

        mock_conn = MagicMock()
        sap_mock._conn = mock_conn
        await sap_mock.close()
        assert sap_mock._conn is None
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_when_no_conn(self, sap_mock: SAPMCP) -> None:
        # Should not raise when conn is None
        await sap_mock.close()


class TestSAPMCPGetConn:
    def test_pyrfc_import_error_message(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "false"}):
            sap = SAPMCP(
                host="sap.test", sysnr="00", client="100", user="u", password="p"
            )
        with patch.dict("sys.modules", {"pyrfc": None}):
            with pytest.raises(ImportError) as exc_info:
                sap._get_conn()
            assert (
                "pyrfc" in str(exc_info.value).lower()
                or "sap" in str(exc_info.value).lower()
            )

    def test_returns_existing_conn_if_set(self) -> None:
        with patch.dict(os.environ, {"OPENQUOTE_USE_MOCK": "false"}):
            sap = SAPMCP()
        mock_conn = object()
        sap._conn = mock_conn
        # Should return existing conn without trying to import pyrfc
        conn = sap._get_conn()
        assert conn is mock_conn
