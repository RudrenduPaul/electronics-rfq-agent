from __future__ import annotations

import json as _json
import os
import re
from decimal import Decimal
from typing import Any
from urllib.parse import quote as urlquote
from urllib.parse import urlparse

import httpx

from electronics_rfq_agent.mcp.base import ERPMCPServer, _sanitize
from electronics_rfq_agent.models import ERPConfig, ERPPartResult

_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
_COMPANY_RE = re.compile(r"^[A-Z0-9_-]{1,10}$")


class EpicorMCP(ERPMCPServer):
    """Epicor Kinetic REST API connector.

    Connects to /api/v2/odata/Company/ endpoints.
    Set ERFA_USE_MOCK=true to use the in-memory mock backend.

    Required env vars (or pass to constructor):
    - ERFA_EPICOR_URL: base URL, e.g. https://epicor.company.com
    - ERFA_EPICOR_API_KEY: base64-encoded user:password for Basic auth
    - ERFA_EPICOR_COMPANY: Epicor company code (default: EPIC)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        company: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        use_mock = os.environ.get("ERFA_USE_MOCK", "").lower() == "true"
        if use_mock:
            from electronics_rfq_agent.mcp.mock.backend import MockERP  # noqa: PLC0415

            self._mock: MockERP | None = MockERP()
        else:
            self._mock = None

        raw_url = (base_url or os.environ.get("ERFA_EPICOR_URL", "")).rstrip("/")
        raw_key = api_key or os.environ.get("ERFA_EPICOR_API_KEY", "")
        raw_company = company or os.environ.get("ERFA_EPICOR_COMPANY", "EPIC")

        if not use_mock:
            parsed = urlparse(raw_url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(
                    f"ERFA_EPICOR_URL must be an https:// URL, got: {raw_url!r}"
                )
            if not all(ord(c) >= 32 and ord(c) <= 126 for c in raw_key):  # noqa: PLR2004
                raise ValueError(
                    "ERFA_EPICOR_API_KEY must contain only printable ASCII characters"
                )
            if not _COMPANY_RE.match(raw_company):
                raise ValueError(
                    "ERFA_EPICOR_COMPANY must match ^[A-Z0-9_-]{1,10}$, "
                    f"got: {raw_company!r}"
                )

        self._base_url = raw_url
        self._api_key = raw_key
        self._company = raw_company

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
        safe_query = _sanitize(query).replace("'", "''")
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
        company_path = urlquote(self._company, safe="")
        response = await client.get(
            f"/api/v2/odata/{company_path}/Erp.BO.PartSvc/Parts",
            params=params,
        )
        response.raise_for_status()
        body = await response.aread()
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ValueError("Response too large")
        return [self._map_part(p) for p in _json.loads(body).get("value", [])]

    async def get_part(self, part_number: str) -> ERPPartResult | None:
        if self._mock is not None:
            return await self._mock.get_part(part_number)

        client = self._get_client()
        # OData: double single-quotes for string literal escaping; then
        # URL-encode to prevent / and other path chars from corrupting the
        # URL path while keeping the OData quote delimiters intact.
        safe_pn = _sanitize(part_number).replace("'", "''")
        encoded_pn = urlquote(safe_pn, safe="'")
        company_path = urlquote(self._company, safe="")
        safe_company = self._company.replace("'", "''")
        url = (
            f"/api/v2/odata/{company_path}/Erp.BO.PartSvc/Parts"
            f"(Company='{safe_company}',PartNum='{encoded_pn}')"
        )
        response = await client.get(url)
        if response.status_code == 404:  # noqa: PLR2004
            return None
        response.raise_for_status()
        body = await response.aread()
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ValueError("Response too large")
        return self._map_part(_json.loads(body))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _map_part(data: dict[str, Any]) -> ERPPartResult:
        return ERPPartResult(
            part_number=str(data.get("PartNum", "")),
            description=str(data.get("PartDescription", "")),
            unit_price=Decimal(str(data.get("UnitPrice") or "0")),
            available_qty=int(data.get("OnHandQty") or 0),
            lead_time_days=int(data.get("LeadTime") or 0),
            manufacturer=str(data.get("VendorName", "")),
        )
