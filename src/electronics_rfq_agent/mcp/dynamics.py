from __future__ import annotations

import asyncio
import os
import re
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import httpx

from electronics_rfq_agent.mcp._oauth import fetch_client_credentials_token
from electronics_rfq_agent.mcp.base import ERPMCPServer, _sanitize
from electronics_rfq_agent.models import ERPConfig, ERPPartResult

_AZURE_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"  # noqa: S105
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class DynamicsMCP(ERPMCPServer):
    """Microsoft Dynamics 365 Sales connector via Graph API.

    Connects to Dynamics 365 for Sales product catalog and quote creation.
    Set ERFA_USE_MOCK=true to use the in-memory mock backend.

    Required env vars (or pass to constructor):
    - ERFA_DYNAMICS_TENANT_ID: Azure AD tenant ID
    - ERFA_DYNAMICS_CLIENT_ID: Azure AD app client ID
    - ERFA_DYNAMICS_CLIENT_SECRET: Azure AD app client secret
    - ERFA_DYNAMICS_BASE_URL: Dynamics instance URL, e.g. https://org.api.crm.dynamics.com
    """

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        use_mock = os.environ.get("ERFA_USE_MOCK", "").lower() == "true"
        if use_mock:
            from electronics_rfq_agent.mcp.mock.backend import MockERP  # noqa: PLC0415

            self._mock: MockERP | None = MockERP()
        else:
            self._mock = None

        self._tenant_id = tenant_id or os.environ.get("ERFA_DYNAMICS_TENANT_ID", "")
        self._client_id = client_id or os.environ.get("ERFA_DYNAMICS_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get(
            "ERFA_DYNAMICS_CLIENT_SECRET", ""
        )
        self._base_url = (
            base_url or os.environ.get("ERFA_DYNAMICS_BASE_URL", "")
        ).rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        # float("inf") means "never expires" — finite values set after a real fetch.
        self._token_expires_at: float = float("inf")
        self._token_lock = asyncio.Lock()
        if self._tenant_id and not _UUID_RE.match(self._tenant_id):
            raise ValueError(f"tenant_id must be a valid UUID; got {self._tenant_id!r}")
        if not use_mock:
            _parsed = urlparse(self._base_url)
            if _parsed.scheme != "https" or not _parsed.netloc:
                raise ValueError(
                    "DynamicsMCP base_url must be https:// with a non-empty host;"
                    f" got {self._base_url!r}"
                )

    @classmethod
    def from_config(cls, cfg: ERPConfig) -> DynamicsMCP:
        """Construct from an ERPConfig instance. Uses api_key as tenant_id."""
        return cls(
            tenant_id=cfg.api_key,
            client_id=cfg.username,
            base_url=cfg.base_url,
            client_secret=cfg.password,
        )

    @property
    def _token_url(self) -> str:
        return _AZURE_TOKEN_URL.format(tenant_id=self._tenant_id)

    async def _ensure_token(self) -> str:
        async with self._token_lock:
            cached = self._access_token
            if cached is not None and time.monotonic() < self._token_expires_at:
                return cached
            token, expires_at = await fetch_client_credentials_token(
                token_url=self._token_url,
                client_id=self._client_id,
                client_secret=self._client_secret,
                extra_fields={"scope": f"{self._base_url}/.default"},
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
                base_url=f"{self._base_url}/api/data/v9.2",
                headers={
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
        client = self._get_client()
        safe_query = _sanitize(query).replace("'", "''")
        response = await client.get(
            "/products",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "$filter": (
                    f"contains(productnumber, '{safe_query}') "
                    f"or contains(name, '{safe_query}')"
                ),
                "$top": limit,
                "$select": "productnumber,name,price,quantityonhand,suppliername",
            },
        )
        response.raise_for_status()
        content_length = int(response.headers.get("content-length", 0))
        if content_length > _MAX_RESPONSE_BYTES:
            raise ValueError(f"Dynamics 365 response too large: {content_length} bytes")
        body = response.content
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ValueError(f"Dynamics 365 response too large: {len(body)} bytes")
        import json as _json  # noqa: PLC0415

        return [self._map_product(p) for p in _json.loads(body).get("value", [])]

    async def get_part(self, part_number: str) -> ERPPartResult | None:
        if self._mock is not None:
            return await self._mock.get_part(part_number)

        token = await self._ensure_token()
        client = self._get_client()
        safe_pn = _sanitize(part_number).replace("'", "''")
        response = await client.get(
            "/products",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "$filter": f"productnumber eq '{safe_pn}'",
                "$top": 1,
                "$select": "productnumber,name,price,quantityonhand,suppliername",
            },
        )
        response.raise_for_status()
        content_length = int(response.headers.get("content-length", 0))
        if content_length > _MAX_RESPONSE_BYTES:
            raise ValueError(f"Dynamics 365 response too large: {content_length} bytes")
        body = response.content
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ValueError(f"Dynamics 365 response too large: {len(body)} bytes")
        import json as _json  # noqa: PLC0415

        values = _json.loads(body).get("value", [])
        return self._map_product(values[0]) if values else None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _map_product(data: dict[str, Any]) -> ERPPartResult:
        return ERPPartResult(
            part_number=str(data.get("productnumber", "")),
            description=str(data.get("name", "")),
            unit_price=Decimal(str(data.get("price") or "0")),
            available_qty=int(data.get("quantityonhand") or 0),
            lead_time_days=int(data.get("leadtime") or 0),
            manufacturer=str(data.get("suppliername", "")),
        )
