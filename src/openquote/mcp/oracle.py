from __future__ import annotations

import os
from decimal import Decimal
from typing import Any
from urllib.parse import quote as urlquote

import httpx

from openquote.mcp.base import ERPMCPServer
from openquote.models import ERPConfig, ERPPartResult


class OracleMCP(ERPMCPServer):
    """Oracle Cloud SCM REST API connector.

    Connects to Oracle Fusion Cloud Supply Chain Management REST APIs.
    Set OPENQUOTE_USE_MOCK=true to use the in-memory mock backend.

    Required env vars (or pass to constructor):
    - OPENQUOTE_ORACLE_BASE_URL: e.g. https://your-tenant.oraclecloud.com
    - OPENQUOTE_ORACLE_CLIENT_ID: OAuth2 client ID
    - OPENQUOTE_ORACLE_CLIENT_SECRET: OAuth2 client secret
    """

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        use_mock = os.environ.get("OPENQUOTE_USE_MOCK", "").lower() == "true"
        if use_mock:
            from openquote.mcp.mock.backend import MockERP  # noqa: PLC0415

            self._mock: MockERP | None = MockERP()
        else:
            self._mock = None

        self._base_url = (
            base_url or os.environ.get("OPENQUOTE_ORACLE_BASE_URL", "")
        ).rstrip("/")
        self._client_id = client_id or os.environ.get("OPENQUOTE_ORACLE_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get(
            "OPENQUOTE_ORACLE_CLIENT_SECRET", ""
        )
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None

    @classmethod
    def from_config(cls, cfg: ERPConfig) -> OracleMCP:
        """Construct from an ERPConfig. Uses username/password as client_id/secret."""
        return cls(
            base_url=cfg.base_url,
            client_id=cfg.username,
            client_secret=cfg.password,
        )

    async def _ensure_token(self) -> str:
        if self._access_token is not None:
            return self._access_token
        async with httpx.AsyncClient(timeout=self._timeout, verify=True) as client:
            response = await client.post(
                f"{self._base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            response.raise_for_status()
            self._access_token = str(response.json()["access_token"])
        return self._access_token

    def _get_client(self, token: str) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {token}",
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

        token = await self._ensure_token()
        client = self._get_client(token)
        safe_query = query.replace("'", "''")
        response = await client.get(
            "/fscmRestApi/resources/11.13.18.05/items",
            params={
                "q": (
                    f"ItemNumber LIKE '%{safe_query}%' "
                    f"OR Description LIKE '%{safe_query}%'"
                ),
                "limit": limit,
                "fields": "ItemNumber,Description,ListPrice,PrimaryUOMCode",
            },
        )
        response.raise_for_status()
        return [self._map_item(item) for item in response.json().get("items", [])]

    async def get_part(self, part_number: str) -> ERPPartResult | None:
        if self._mock is not None:
            return await self._mock.get_part(part_number)

        token = await self._ensure_token()
        client = self._get_client(token)
        encoded_pn = urlquote(part_number, safe="")
        response = await client.get(
            f"/fscmRestApi/resources/11.13.18.05/items/{encoded_pn}",
        )
        if response.status_code == 404:  # noqa: PLR2004
            return None
        response.raise_for_status()
        return self._map_item(response.json())

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _map_item(data: dict[str, Any]) -> ERPPartResult:
        return ERPPartResult(
            part_number=str(data.get("ItemNumber", "")),
            description=str(data.get("Description", "")),
            unit_price=Decimal(str(data.get("ListPrice", "0"))),
            available_qty=int(data.get("OnHandQuantity", 0)),
            lead_time_days=int(data.get("LeadTime", 0)),
            manufacturer=str(data.get("Manufacturer", "")),
        )
