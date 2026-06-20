from __future__ import annotations

import json as _json
import time

import httpx

_MAX_TOKEN_RESPONSE_BYTES = 65_536


async def fetch_client_credentials_token(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    extra_fields: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[str, float]:
    """Fetch an OAuth 2.0 client-credentials token.

    Returns (access_token, expires_at_monotonic). The caller caches the token
    and calls this again when time.monotonic() >= expires_at.
    """
    data: dict[str, str] = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if extra_fields:
        data.update(extra_fields)
    async with httpx.AsyncClient(timeout=timeout, verify=True) as auth_client:
        response = await auth_client.post(token_url, data=data)
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if (
            content_length is not None
            and int(content_length) > _MAX_TOKEN_RESPONSE_BYTES
        ):
            raise ValueError(f"OAuth token response too large: {content_length} bytes")
        raw_body = response.content
        if len(raw_body) > _MAX_TOKEN_RESPONSE_BYTES:
            raise ValueError(f"OAuth token response too large: {len(raw_body)} bytes")
        payload: dict[str, object] = _json.loads(raw_body)
        access_token = str(payload["access_token"])
        raw_expiry = payload.get("expires_in", 3600)
        expires_in = (
            int(raw_expiry) if isinstance(raw_expiry, (int, float, str)) else 3600
        )
        expires_at = time.monotonic() + expires_in - 60
    return access_token, expires_at
