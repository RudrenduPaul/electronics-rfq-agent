from __future__ import annotations

import asyncio
import ipaddress
import os
import re
from decimal import Decimal
from typing import Any

from electronics_rfq_agent.mcp.base import ERPMCPServer, _sanitize
from electronics_rfq_agent.models import ERPConfig, ERPConnectionError, ERPPartResult

# pyrfc raises ABAPApplicationError for "material not found" responses.
# All other exceptions are treated as connection/auth failures.
_SAP_NOT_FOUND_EXCEPTIONS: frozenset[str] = frozenset({"ABAPApplicationError"})


class SAPMCP(ERPMCPServer):
    """SAP ECC / S/4HANA connector using PyRFC BAPI calls.

    Requires the SAP NetWeaver RFC Library and pyrfc to be installed.
    pyrfc is not available on PyPI -- see docs/erp-setup/sap.md for manual
    installation instructions.

    Required SAP authorizations:
    - S_RFC: RFC_TYPE=FUGR, RFC_NAME=BAPI_MATERIAL_*
    - M_MATE_STA: MMSTA (material status)
    - M_MSEG_BWA: BWART (movement type)

    Set ERFA_USE_MOCK=true to skip SAP and use in-memory mock instead.

    Required env vars (or pass to constructor):
    - ERFA_SAP_HOST: SAP application server hostname
    - ERFA_SAP_SYSNR: system number (e.g. "00")
    - ERFA_SAP_CLIENT: client (e.g. "100")
    - ERFA_SAP_USER: RFC username
    - ERFA_SAP_PASSWORD: RFC password
    """

    def __init__(  # noqa: PLR0913
        self,
        host: str | None = None,
        sysnr: str | None = None,
        client: str | None = None,
        user: str | None = None,
        password: str | None = None,
        plant: str = "0001",
    ) -> None:
        use_mock = os.environ.get("ERFA_USE_MOCK", "").lower() == "true"
        if use_mock:
            from electronics_rfq_agent.mcp.mock.backend import MockERP  # noqa: PLC0415

            self._mock: MockERP | None = MockERP()
        else:
            self._mock = None

        self._host = host or os.environ.get("ERFA_SAP_HOST", "")
        self._sysnr = sysnr or os.environ.get("ERFA_SAP_SYSNR", "00")
        self._client = client or os.environ.get("ERFA_SAP_CLIENT", "100")
        self._user = user or os.environ.get("ERFA_SAP_USER", "")
        self._password = password or os.environ.get("ERFA_SAP_PASSWORD", "")
        self._plant = plant
        if not use_mock:
            self._validate_connection_params()
        self._conn: Any | None = None
        # pyrfc connections are not thread-safe; serialise all BAPI calls.
        self._bapi_lock = asyncio.Lock()
        # Separate lock guards lazy connection initialisation.
        self._conn_lock = asyncio.Lock()

    def _validate_connection_params(self) -> None:
        if not self._host:
            raise ValueError("SAP host must not be empty")
        try:
            addr = ipaddress.ip_address(self._host)
            if addr.is_loopback or addr.is_link_local or addr.is_private:
                raise ValueError(
                    f"SAP host {self._host!r} resolves to a disallowed address range"
                )
        except ValueError as exc:
            if "disallowed address range" in str(exc):
                raise
            _hostname_re = r"[A-Za-z0-9]([A-Za-z0-9\-\.]{0,253}[A-Za-z0-9])?"
            if not re.fullmatch(_hostname_re, self._host):
                raise ValueError(
                    f"SAP host {self._host!r} is not a valid hostname or IP address"
                ) from exc
        if not re.fullmatch(r"\d{2}", self._sysnr):
            raise ValueError(
                f"SAP sysnr {self._sysnr!r} must be a 2-digit numeric string"
            )
        if not re.fullmatch(r"\d{3}", self._client):
            raise ValueError(
                f"SAP client {self._client!r} must be a 3-digit numeric string"
            )

    @classmethod
    def from_config(cls, cfg: ERPConfig) -> SAPMCP:
        """Construct from an ERPConfig instance."""
        return cls(host=cfg.base_url, user=cfg.username, password=cfg.password)

    async def _get_conn(self) -> Any:
        async with self._conn_lock:
            if self._conn is not None:
                return self._conn
            try:
                import pyrfc  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "pyrfc is required for SAP connectivity. "
                    "pyrfc is not available on PyPI -- the SAP NetWeaver RFC Library "
                    "must be installed manually. See docs/erp-setup/sap.md."
                ) from exc
            try:
                self._conn = await asyncio.to_thread(
                    pyrfc.Connection,
                    ashost=self._host,
                    sysnr=self._sysnr,
                    client=self._client,
                    user=self._user,
                    passwd=self._password,
                )
            except Exception as exc:
                raise ERPConnectionError(
                    f"SAP connection failed for host {self._host!r}: {exc}"
                ) from exc
            return self._conn

    async def search_parts(self, query: str, limit: int = 20) -> list[ERPPartResult]:
        if self._mock is not None:
            return await self._mock.search_parts(query, limit)

        conn = await self._get_conn()
        async with self._bapi_lock:
            result: dict[str, Any] = await asyncio.to_thread(
                conn.call,
                "BAPI_MATERIAL_GETLIST",
                MATNRSELECTION=[
                    {"SIGN": "I", "OPTION": "CP", "MATNR_LOW": f"*{_sanitize(query)}*"}
                ],
            )
        matnrs = [m["MATNR"] for m in result.get("MATNRLIST", [])[:limit]]
        parts = await asyncio.gather(*[self.get_part(m) for m in matnrs])
        return [p for p in parts if p is not None]

    async def get_part(self, part_number: str) -> ERPPartResult | None:
        if self._mock is not None:
            return await self._mock.get_part(part_number)

        detail = await self._bapi_material_detail(part_number)
        if detail is None:
            return None

        mat_general, mat_plant = detail
        price_data = await self._bapi_pricing(part_number)

        if price_data:
            unit_price: Decimal = Decimal(str(price_data.get("PRICE") or "0"))
        else:
            erp_price = mat_general.get("MOVING_PRICE") or mat_general.get(
                "STANDARD_PRICE"
            )
            unit_price = (
                Decimal(str(erp_price)) if erp_price is not None else Decimal("0")
            )

        return ERPPartResult(
            part_number=str(mat_general.get("MATERIAL", part_number)),
            description=str(mat_general.get("MATL_DESC", "")),
            unit_price=unit_price,
            available_qty=int(mat_plant.get("TOTAL_STOCK") or 0),
            lead_time_days=int(mat_plant.get("REPLENISHMENT_LEAD_TIME") or 0),
            manufacturer=str(mat_general.get("MANUFACTURER", "")),
        )

    async def get_price(self, part_number: str, quantity: int) -> Decimal | None:
        if self._mock is not None:
            return await self._mock.get_price(part_number, quantity)

        price_data = await self._bapi_pricing(part_number)
        if not price_data:
            return None
        return Decimal(str(price_data.get("PRICE") or "0"))

    async def close(self) -> None:
        async with self._bapi_lock:
            async with self._conn_lock:
                if self._conn is not None:
                    await asyncio.to_thread(self._conn.close)
                    self._conn = None

    async def _bapi_material_detail(
        self, part_number: str
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        conn = await self._get_conn()
        try:
            async with self._bapi_lock:
                result: dict[str, Any] = await asyncio.to_thread(
                    conn.call,
                    "BAPI_MATERIAL_GET_DETAIL",
                    MATERIAL=part_number,
                    PLANT=self._plant,
                )
        except Exception as exc:
            if type(exc).__name__ in _SAP_NOT_FOUND_EXCEPTIONS:
                return None
            raise ERPConnectionError(
                f"SAP BAPI call failed for {part_number!r}: {exc}"
            ) from exc

        mat_general: dict[str, Any] = result.get("MATERIAL_GENERAL_DATA", {})
        if not mat_general:
            return None
        mat_plant: dict[str, Any] = result.get("MATERIAL_PLANT_DATA", {})
        return mat_general, mat_plant

    async def _bapi_pricing(self, part_number: str) -> dict[str, Any]:
        conn = await self._get_conn()
        try:
            async with self._bapi_lock:
                result: dict[str, Any] = await asyncio.to_thread(
                    conn.call,
                    "BAPI_MATERIAL_GETPRICINGINFO",
                    MATERIAL=part_number,
                    PLANT=self._plant,
                )
        except Exception as exc:
            if type(exc).__name__ in _SAP_NOT_FOUND_EXCEPTIONS:
                return {}
            raise ERPConnectionError(
                f"SAP pricing BAPI failed for {part_number!r}: {exc}"
            ) from exc
        return dict(result.get("PRICINGDATA", {}))
