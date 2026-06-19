from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import httpx

from openquote.mcp.base import ERPMCPServer
from openquote.models import ERPConfig, ERPPartResult


class DynamicsMCP(ERPMCPServer):
    """Microsoft Dynamics 365 Sales connector via Graph API.

    Connects to Dynamics 365 for Sales product catalog and quote creation.
    Set OPENQUOTE_USE_MOCK=true to use the in-memory mock backend.

    Required env vars (or pass to constructor):
    - OPENQUOTE_DYNAMICS_TENANT_ID: Azure AD tenant ID
    - OPENQUOTE_DYNAMICS_CLIENT_ID: Azure AD app client ID
    - OPENQUOTE_DYNAMICS_CLIENT_SECRET: Azure AD app client secret
    - OPENQUOTE_DYNAMICS_BASE_URL: Dynamics instance URL, e.g. https://org.api.crm.dynamics.com
    """

    _TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"  # noqa: S105
    _SCOPE = "https://org.api.crm.dynamics.com/.default"

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        use_mock = os.environ.get("OPENQUOTE_USE_MOCK", "").lower() == "true"
        if use_mock:
            from openquote.mcp.mock.backend import MockERP  # noqa: PLC0415

            self._mock: MockERP | None = MockERP()
        else:
            self._mock = None

        self._tenant_id = tenant_id or os.environ.get(
            "OPENQUOTE_DYNAMICS_TENANT_ID", ""
        )
        self._client_id = client_id or os.environ.get(
            "OPENQUOTE_DYNAMICS_CLIENT_ID", ""
        )
        self._client_secret = client_secret or os.environ.get(
            "OPENQUOTE_DYNAMICS_CLIENT_SECRET", ""
        )
        self._base_url = (
            base_url or os.environ.get("OPENQUOTE_DYNAMICS_BASE_URL", "")
        ).rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None

    @classmethod
    def from_config(cls, cfg: ERPConfig) -> DynamicsMCP:
        """Construct from an ERPConfig instance. Uses api_key as tenant_id."""
        return cls(tenant_id=cfg.api_key, base_url=cfg.base_url)

    async def _ensure_token(self) -> str:
        if self._access_token is not None:
            return self._access_token
        token_url = self._TOKEN_URL.format(tenant_id=self._tenant_id)
        async with httpx.AsyncClient(timeout=self._timeout, verify=True) as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": f"{self._base_url}/.default",
                },
            )
            response.raise_for_status()
            self._access_token = str(response.json()["access_token"])
        return self._access_token

    def _get_client(self, token: str) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{self._base_url}/api/data/v9.2",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "OData-MaxVersion": "4.0",
                    "OData-Version": "4.0",
                },
                timeout=self._timeout,
                verify=True,
            )
        return self._client

    async def search_parts(self, query: str, limit: int = 20) -> list[ERPPartResult]:
        if self._mock is not None:
            return await self._mock.search_parts(query, limit)

        token = await self._ensure_token()
        client = self._get_client(token)
        response = await client.get(
            "/products",
            params={
                "$filter": (
                    f"contains(productnumber, '{query}') or contains(name, '{query}')"
                ),
                "$top": limit,
                "$select": "productnumber,name,price,quantityonhand,suppliername",
            },
        )
        response.raise_for_status()
        data = response.json()
        return [self._map_product(p) for p in data.get("value", [])]

    async def get_part(self, part_number: str) -> ERPPartResult | None:
        if self._mock is not None:
            return await self._mock.get_part(part_number)

        token = await self._ensure_token()
        client = self._get_client(token)
        response = await client.get(
            "/products",
            params={
                "$filter": f"productnumber eq '{part_number}'",
                "$top": 1,
                "$select": "productnumber,name,price,quantityonhand,suppliername",
            },
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        if not values:
            return None
        return self._map_product(values[0])

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
    def _map_product(data: dict[str, Any]) -> ERPPartResult:
        return ERPPartResult(
            part_number=str(data.get("productnumber", "")),
            description=str(data.get("name", "")),
            unit_price=Decimal(str(data.get("price", "0"))),
            available_qty=int(data.get("quantityonhand", 0)),
            lead_time_days=int(data.get("leadtime", 0)),
            manufacturer=str(data.get("suppliername", "")),
        )
