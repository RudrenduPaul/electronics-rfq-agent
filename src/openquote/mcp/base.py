from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from types import TracebackType

from openquote.models import ERPPartResult


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

    @abstractmethod
    async def check_inventory(self, part_number: str, quantity: int) -> bool:
        """Return True if available_qty >= requested quantity."""
        ...

    @abstractmethod
    async def get_price(self, part_number: str, quantity: int) -> Decimal | None:
        """Return unit price at given quantity. Returns None if part not found."""
        ...

    async def __aenter__(self) -> ERPMCPServer:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Release resources. Override in subclasses that hold connections."""
        return  # default no-op; subclasses override when they hold connections
