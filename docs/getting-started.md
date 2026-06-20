# Getting started with Electronics RFQ Agent

## Prerequisites

- Python 3.10 or later
- An Anthropic API key (for RFQ parsing)
- An ERP system account (or use the built-in mock backend)

## Installation

```bash
pip install electronics-rfq-agent
```

For SAP connectivity:

```bash
pip install electronics-rfq-agent[sap]
# Also install SAP NetWeaver RFC Library -- see docs/erp-setup/sap.md
```

## Your first quote

### With the mock backend (no ERP needed)

```python
import asyncio
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp.mock import MockERP

async def main():
    agent = QuoteAgent(erp=MockERP())
    quote = await agent.run("path/to/rfq.xlsx")
    print(quote.summary())
    for line in quote.lines:
        print(f"  {line.rfq_line.part_number}: {line.status} @ {line.unit_price}")

asyncio.run(main())
```

Or synchronously:

```python
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp.mock import MockERP

agent = QuoteAgent(erp=MockERP())
quote = agent.run_sync("path/to/rfq.xlsx")
print(quote.summary())
```

### With Epicor Kinetic

```python
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp import EpicorMCP

erp = EpicorMCP(
    base_url="https://your-epicor.company.com",
    api_key="your-base64-encoded-credentials",
    company="EPIC",
)
agent = QuoteAgent(erp=erp, margin_pct=0.15)
quote = agent.run_sync("rfq.pdf")
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for PDF/text parsing) | -- | Anthropic API key |
| `ERFA_MODEL` | No | `claude-sonnet-4-6` | Anthropic model for parsing |
| `ERFA_USE_MOCK` | No | `false` | Force mock backend for all connectors |
| `ERFA_EPICOR_URL` | Epicor only | -- | Epicor base URL |
| `ERFA_EPICOR_API_KEY` | Epicor only | -- | Epicor Basic auth credentials |

See `.env.example` for the full list.

## Supported document formats

| Format | Parser |
|---|---|
| PDF | Claude vision API (reads tables and text) |
| Excel (.xlsx, .xls) | openpyxl (reads first sheet, auto-detects header row) |
| Word (.docx) | python-docx (reads all tables) |
| Plain text | Claude API (sends text directly) |

## Quote output

A `Quote` object contains:

```python
quote.id              # UUID
quote.rfq_source      # file path or "text"
quote.lines           # list[QuoteLineItem]
quote.total_price     # Decimal (sum of extended_price for found/substituted lines)
quote.currency        # "USD" (default)
quote.summary()       # one-line string summary
quote.to_dict()       # JSON-serializable dict
```

Each `QuoteLineItem` has:

```python
line.rfq_line         # original RFQLineItem
line.erp_result       # ERPPartResult | None
line.status           # "found" | "not_found" | "substituted"
line.unit_price       # Decimal | None (sell price including margin)
line.extended_price   # Decimal | None (unit_price x quantity)
line.notes            # str | None
```

## Margin configuration

The default margin is 15%. Adjust per agent:

```python
agent = QuoteAgent(erp=erp, margin_pct=0.20)  # 20% margin
```

### With Oracle Cloud SCM

```python
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp.oracle import OracleMCP

erp = OracleMCP(
    base_url="https://your-tenant.oraclecloud.com",
    client_id="your-oauth2-client-id",
    client_secret="your-oauth2-client-secret",
)
agent = QuoteAgent(erp=erp, margin_pct=0.15)
quote = agent.run_sync("rfq.xlsx")
```

Or load from environment variables:

```bash
export ERFA_ORACLE_BASE_URL="https://your-tenant.oraclecloud.com"
export ERFA_ORACLE_CLIENT_ID="your-client-id"
export ERFA_ORACLE_CLIENT_SECRET="your-client-secret"
```

```python
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp.oracle import OracleMCP

agent = QuoteAgent(erp=OracleMCP(), margin_pct=0.15)
quote = agent.run_sync("rfq.xlsx")
```

Oracle uses OAuth 2.0 client credentials flow. The token is fetched automatically on first use and cached for its lifetime.

### With Microsoft Dynamics 365

```python
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp.dynamics import DynamicsMCP

erp = DynamicsMCP(
    tenant_id="your-azure-ad-tenant-id",
    client_id="your-azure-app-client-id",
    client_secret="your-azure-app-client-secret",
    base_url="https://your-org.api.crm.dynamics.com",
)
agent = QuoteAgent(erp=erp, margin_pct=0.15)
quote = agent.run_sync("rfq.pdf")
```

Or from environment variables:

```bash
export ERFA_DYNAMICS_TENANT_ID="your-tenant-id"
export ERFA_DYNAMICS_CLIENT_ID="your-client-id"
export ERFA_DYNAMICS_CLIENT_SECRET="your-client-secret"
export ERFA_DYNAMICS_BASE_URL="https://your-org.api.crm.dynamics.com"
```

Dynamics uses OAuth 2.0 via Azure AD. Register an app in Azure Portal, grant it Dynamics CRM user_impersonation scope, and create a client secret. The connector fetches a token automatically and refreshes it on 401.

## Using ERPConfig for configuration management

`ERPConfig` is a Pydantic model that centralizes ERP credentials. All four connectors expose a `from_config()` classmethod:

```python
from electronics_rfq_agent.models import ERPConfig
from electronics_rfq_agent.mcp.epicor import EpicorMCP
from electronics_rfq_agent.mcp.oracle import OracleMCP
from electronics_rfq_agent.mcp.dynamics import DynamicsMCP

# Load from a config file, database, or secret manager
cfg = ERPConfig(
    erp_type="epicor",
    base_url="https://your-epicor.company.com",
    api_key="your-api-key",
)
erp = EpicorMCP.from_config(cfg)

# ERPConfig masks credentials in logs — safe to print
print(cfg)  # ERPConfig(erp_type='epicor', base_url='...', api_key='***', ...)
```

Supported `erp_type` values: `"epicor"`, `"oracle"`, `"dynamics"`, `"sap"`, `"mock"`.

## Troubleshooting

### Authentication errors (401 / 403)

**Epicor:** The `api_key` is a Base64-encoded `username:password` string. Generate it with:
```bash
echo -n "username:password" | base64
```

**Oracle / Dynamics:** OAuth 2.0 errors usually mean the client secret has expired or the app registration is missing the required scope. Check the Azure Portal / Oracle Identity Cloud console.

**SAP:** PyRFC connection errors surface as `ERPConnectionError`. Confirm the SAP hostname, system number, client, and user credentials are correct. The SAP NW RFC Library must be installed separately — see [docs/erp-setup/sap.md](erp-setup/sap.md).

### Timeout tuning

The default timeout for all HTTP connectors is 30 seconds. For slow ERP instances, increase it:

```python
erp = EpicorMCP(base_url="...", api_key="...", timeout=60.0)
erp = OracleMCP(base_url="...", client_id="...", client_secret="...", timeout=60.0)
```

### SSL / TLS errors

All connectors use `httpx` with `verify=True` (default). If your ERP has a self-signed certificate on an internal network, add the CA bundle:

```python
import httpx
import ssl

# Not recommended for production — use a proper CA bundle instead
ctx = ssl.create_default_context()
ctx.load_verify_locations("/path/to/internal-ca.crt")
# Pass via httpx.AsyncClient(verify=ctx) — requires subclassing the connector
```

For production deployments, install the internal CA in the system trust store instead of bypassing verification.

### "RFQParseError: Anthropic API returned no parseable text content"

This means the Claude API call succeeded but returned empty content. Common causes:
- The PDF is scanned image-only with no text layer — try a higher-quality scan
- The document is password-protected
- The Anthropic API key is valid but the account has hit rate limits

### "ERPConnectionError" on every lookup

This is raised for network or authentication failures, not for parts not found. Check:
- The ERP base URL is reachable from your host
- Credentials are correct
- Firewall rules allow outbound HTTPS to the ERP host

Parts not found in the catalog return `status="not_found"` silently — they do not raise an exception.

## Next steps

- [Epicor setup](erp-setup/epicor.md)
- [SAP setup](erp-setup/sap.md)
- [Oracle setup](erp-setup/oracle.md)
- [Dynamics 365 setup](erp-setup/dynamics.md)
- [Contributing a new ERP integration](../CONTRIBUTING.md#adding-a-new-erp-integration)
