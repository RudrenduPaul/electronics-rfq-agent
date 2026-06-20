from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from types import TracebackType

from electronics_rfq_agent.models import ERPPartResult


class ERPMCPServer(ABC):
    """Abstract base for all ERP MCP server implementations.

    Concrete implementations: EpicorMCP, SAPMCP, OracleMCP, DynamicsMCP, MockERP.
    """

    @abstractmethod
    async def search_parts(self, query: str, limit: int = 20) -> list[ERPPartResult]:
        """Search the ERP catalog by part number, description, or manufacturer."""
        ...

    @abstractmethod
    async def get_part(self, part_number: str) -> ERPPartResult | None:
        """Retrieve a specific part by exact part number. Returns None if not found."""
        ...

    async def check_inventory(self, part_number: str, quantity: int) -> bool:
        """Return True if available_qty >= requested quantity."""
        part = await self.get_part(part_number)
        return part is not None and part.available_qty >= quantity

    async def get_price(self, part_number: str, quantity: int) -> Decimal | None:
        """Return unit price at given quantity. Returns None if part not found."""
        part = await self.get_part(part_number)
        return part.unit_price if part is not None else None

    async def __aenter__(self) -> ERPMCPServer:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:  # noqa: B027
        """Release resources. Override in subclasses that hold connections."""


def _sanitize(value: str) -> str:
    """Strip ASCII control characters from user-supplied ERP query strings.

    Prevents newline-hash injection where \\n# in an OData predicate hides
    trailing arguments from path validation.
    """
    return "".join(c for c in value if ord(c) >= 32 and ord(c) != 127)  # noqa: PLR2004
