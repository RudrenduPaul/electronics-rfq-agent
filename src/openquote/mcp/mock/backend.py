from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from openquote.mcp.base import ERPMCPServer
from openquote.models import ERPPartResult

_CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"


class MockERP(ERPMCPServer):
    """In-memory mock ERP backend for local development and testing.

    Loads 200 realistic electronics parts from catalog.json.
    Supports fuzzy search by part number or description substring.
    No external dependencies required.
    """

    def __init__(self, catalog_path: Path | None = None) -> None:
        path = catalog_path or _CATALOG_PATH
        with open(path) as f:
            raw: list[dict[str, Any]] = json.load(f)
        self._parts: dict[str, ERPPartResult] = {
            p["part_number"]: ERPPartResult(
                part_number=p["part_number"],
                description=p["description"],
                unit_price=Decimal(str(p["unit_price"])),
                available_qty=p["available_qty"],
                lead_time_days=p["lead_time_days"],
                manufacturer=p["manufacturer"],
            )
            for p in raw
        }

    async def search_parts(self, query: str, limit: int = 20) -> list[ERPPartResult]:
        q = query.lower().strip()
        results = [
            part
            for part in self._parts.values()
            if q in part.part_number.lower() or q in part.description.lower()
        ]
        return results[:limit]

    async def get_part(self, part_number: str) -> ERPPartResult | None:
        normalized = part_number.strip().upper()
        direct = self._parts.get(normalized)
        if direct:
            return direct
        for key, part in self._parts.items():
            if key.upper() == normalized:
                return part
        return None

    async def check_inventory(self, part_number: str, quantity: int) -> bool:
        part = await self.get_part(part_number)
        if part is None:
            return False
        return part.available_qty >= quantity

    async def get_price(self, part_number: str, quantity: int) -> Decimal | None:
        part = await self.get_part(part_number)
        if part is None:
            return None
        if quantity >= 1000:  # noqa: PLR2004
            return part.unit_price * Decimal("0.80")
        if quantity >= 100:  # noqa: PLR2004
            return part.unit_price * Decimal("0.90")
        if quantity >= 10:  # noqa: PLR2004
            return part.unit_price * Decimal("0.95")
        return part.unit_price

    def part_count(self) -> int:
        return len(self._parts)
