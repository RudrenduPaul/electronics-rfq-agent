from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import httpx

from openquote.mcp.base import ERPMCPServer
from openquote.models import ERPConfig, ERPPartResult


class EpicorMCP(ERPMCPServer):
    """Epicor Kinetic REST API connector.

    Connects to /api/v2/odata/Company/ endpoints.
    Set OPENQUOTE_USE_MOCK=true to use the in-memory mock backend.

    Required env vars (or pass to constructor):
    - OPENQUOTE_EPICOR_URL: base URL, e.g. https://epicor.company.com
    - OPENQUOTE_EPICOR_API_KEY: base64-encoded user:password for Basic auth
    - OPENQUOTE_EPICOR_COMPANY: Epicor company code (default: EPIC)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        company: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        use_mock = os.environ.get("OPENQUOTE_USE_MOCK", "").lower() == "true"
        if use_mock:
            from openquote.mcp.mock.backend import MockERP  # noqa: PLC0415

            self._mock: MockERP | None = MockERP()
        else:
            self._mock = None

        self._base_url = (
            base_url or os.environ.get("OPENQUOTE_EPICOR_URL", "")
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("OPENQUOTE_EPICOR_API_KEY", "")
        self._company = company or os.environ.get("OPENQUOTE_EPICOR_COMPANY", "EPIC")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_config(cls, cfg: ERPConfig) -> EpicorMCP:
        """Construct from an ERPConfig instance."""
        return cls(base_url=cfg.base_url, api_key=cfg.api_key)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Basic {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self._timeout,
                verify=True,
            )
        return self._client

    async def search_parts(self, query: str, limit: int = 20) -> list[ERPPartResult]:
        if self._mock is not None:
            return await self._mock.search_parts(query, limit)

        client = self._get_client()
        safe_query = query.replace("'", "''")
        params: dict[str, str | int] = {
            "$filter": (
                f"contains(PartNum, '{safe_query}') "
                f"or contains(PartDescription, '{safe_query}')"
            ),
            "$top": limit,
            "$select": (
                "PartNum,PartDescription,UnitPrice,OnHandQty,LeadTime,VendorName"
            ),
        }
        response = await client.get(
            f"/api/v2/odata/{self._company}/Erp.BO.PartSvc/Parts",
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        return [self._map_part(p) for p in data.get("value", [])]

    async def get_part(self, part_number: str) -> ERPPartResult | None:
        if self._mock is not None:
            return await self._mock.get_part(part_number)

        client = self._get_client()
        safe_pn = part_number.replace("'", "''")
        url = (
            f"/api/v2/odata/{self._company}/Erp.BO.PartSvc/Parts"
            f"(Company='{self._company}',PartNum='{safe_pn}')"
        )
        response = await client.get(url)
        if response.status_code == 404:  # noqa: PLR2004
            return None
        response.raise_for_status()
        return self._map_part(response.json())

    async def check_inventory(self, part_number: str, quantity: int) -> bool:
        if self._mock is not None:
            return await self._mock.check_inventory(part_number, quantity)

        part = await self.get_part(part_number)
        return part is not None and part.available_qty >= quantity

    async def get_price(self, part_number: str, quantity: int) -> Decimal | None:
        if self._mock is not None:
            return await self._mock.get_price(part_number, quantity)

        part = await self.get_part(part_number)
        return part.unit_price if part is not None else None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _map_part(data: dict[str, Any]) -> ERPPartResult:
        return ERPPartResult(
            part_number=str(data.get("PartNum", "")),
            description=str(data.get("PartDescription", "")),
            unit_price=Decimal(str(data.get("UnitPrice", "0"))),
            available_qty=int(data.get("OnHandQty", 0)),
            lead_time_days=int(data.get("LeadTime", 0)),
            manufacturer=str(data.get("VendorName", "")),
        )
