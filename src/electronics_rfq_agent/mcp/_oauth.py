from __future__ import annotations

import time

import httpx


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
        payload: dict[str, object] = response.json()
        access_token = str(payload["access_token"])
        raw_expiry = payload.get("expires_in", 3600)
        expires_in = (
            int(raw_expiry) if isinstance(raw_expiry, (int, float, str)) else 3600
        )
        expires_at = time.monotonic() + expires_in - 60
    return access_token, expires_at
