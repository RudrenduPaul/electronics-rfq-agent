"""openquote — AI quoting agent for electronics distributors.

Quick start:

    from openquote import QuoteAgent
    from openquote.mcp.mock import MockERP

    agent = QuoteAgent(erp=MockERP())
    quote = agent.run_sync("path/to/rfq.xlsx")
    print(quote.summary())
"""

from openquote.agent import QuoteAgent
from openquote.mcp.base import ERPMCPServer
from openquote.mcp.dynamics import DynamicsMCP
from openquote.mcp.epicor import EpicorMCP
from openquote.mcp.mock.backend import MockERP
from openquote.mcp.oracle import OracleMCP
from openquote.mcp.sap import SAPMCP
from openquote.models import (
    ERPConfig,
    ERPConnectionError,
    ERPPartResult,
    Quote,
    QuoteLineItem,
    RFQLineItem,
    RFQParseError,
)

__version__ = "0.1.0"
__all__ = [
    "SAPMCP",
    "DynamicsMCP",
    "ERPConfig",
    "ERPConnectionError",
    "ERPMCPServer",
    "ERPPartResult",
    "EpicorMCP",
    "MockERP",
    "OracleMCP",
    "Quote",
    "QuoteAgent",
    "QuoteLineItem",
    "RFQLineItem",
    "RFQParseError",
    "__version__",
]
