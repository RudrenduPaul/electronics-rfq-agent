"""Electronics RFQ Agent: AI quoting agent for electronics distributors.

Quick start:

    from electronics_rfq_agent import QuoteAgent
    from electronics_rfq_agent.mcp.mock import MockERP

    agent = QuoteAgent(erp=MockERP())
    quote = agent.run_sync("path/to/rfq.xlsx")
    print(quote.summary())
"""

from electronics_rfq_agent.agent import QuoteAgent
from electronics_rfq_agent.mcp.base import ERPMCPServer
from electronics_rfq_agent.mcp.dynamics import DynamicsMCP
from electronics_rfq_agent.mcp.epicor import EpicorMCP
from electronics_rfq_agent.mcp.mock.backend import MockERP
from electronics_rfq_agent.mcp.oracle import OracleMCP
from electronics_rfq_agent.mcp.sap import SAPMCP
from electronics_rfq_agent.models import (
    ERPConfig,
    ERPConnectionError,
    ERPPartResult,
    Quote,
    QuoteLineItem,
    RFQLineItem,
    RFQParseError,
)
from electronics_rfq_agent.telemetry import TelemetryCollector, TelemetryEvent

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
    "TelemetryCollector",
    "TelemetryEvent",
    "__version__",
]
