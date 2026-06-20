from __future__ import annotations

import asyncio
import os
import time
from decimal import Decimal
from typing import Any
from urllib.parse import quote as urlquote

import httpx

from electronics_rfq_agent.mcp._oauth import fetch_client_credentials_token
from electronics_rfq_agent.mcp.base import ERPMCPServer
from electronics_rfq_agent.models import ERPConfig, ERPPartResult


class OracleMCP(ERPMCPServer):
    """Oracle Cloud SCM REST API connector.

    Connects to Oracle Fusion Cloud Supply Chain Management REST APIs.
    Set ERFA_USE_MOCK=true to use the in-memory mock backend.

    Required env vars (or pass to constructor):
    - ERFA_ORACLE_BASE_URL: e.g. https://your-tenant.oraclecloud.com
    - ERFA_ORACLE_CLIENT_ID: OAuth2 client ID
    - ERFA_ORACLE_CLIENT_SECRET: OAuth2 client secret
    """

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        use_mock = os.environ.get("ERFA_USE_MOCK", "").lower() == "true"
        if use_mock:
            from electronics_rfq_agent.mcp.mock.backend import MockERP  # noqa: PLC0415

            self._mock: MockERP | None = MockERP()
        else:
            self._mock = None

        self._base_url = (
            base_url or os.environ.get("ERFA_ORACLE_BASE_URL", "")
        ).rstrip("/")
        self._client_id = client_id or os.environ.get("ERFA_ORACLE_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get(
            "ERFA_ORACLE_CLIENT_SECRET", ""
        )
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        # float("inf") means "never expires" — finite values set after a real fetch.
        self._token_expires_at: float = float("inf")
        self._token_lock = asyncio.Lock()

    @classmethod
    def from_config(cls, cfg: ERPConfig) -> OracleMCP:
        """Construct from an ERPConfig. Uses username/password as client_id/secret."""
        return cls(
            base_url=cfg.base_url,
            client_id=cfg.username,
            client_secret=cfg.password,
        )

    async def _ensure_token(self) -> str:
        async with self._token_lock:
            cached = self._access_token
            if cached is not None and time.monotonic() < self._token_expires_at:
                return cached
            token, expires_at = await fetch_client_credentials_token(
                token_url=f"{self._base_url}/oauth/token",
                client_id=self._client_id,
                client_secret=self._client_secret,
                timeout=self._timeout,
            )
            self._access_token, self._token_expires_at = token, expires_at
            return token

    def _get_client(self) -> httpx.AsyncClient:
        # Authorization header is NOT embedded here — tokens expire and the client
        # is cached, so embedding would send stale credentials after a refresh.
        # Pass the current token per-request via headers= instead.
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
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
        client = self._get_client()
        safe_query = query.replace("%", r"\%").replace("_", r"\_").replace("'", "''")
        response = await client.get(
            "/fscmRestApi/resources/11.13.18.05/items",
            headers={"Authorization": f"Bearer {token}"},
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
        client = self._get_client()
        encoded_pn = urlquote(part_number, safe="")
        response = await client.get(
            f"/fscmRestApi/resources/11.13.18.05/items/{encoded_pn}",
            headers={"Authorization": f"Bearer {token}"},
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
            unit_price=Decimal(str(data.get("ListPrice") or "0")),
            available_qty=int(data.get("OnHandQuantity") or 0),
            lead_time_days=int(data.get("LeadTime") or 0),
            manufacturer=str(data.get("Manufacturer", "")),
        )
