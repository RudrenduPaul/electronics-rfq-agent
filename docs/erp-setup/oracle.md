# Oracle Cloud SCM Setup

## Prerequisites

- Oracle Fusion Cloud Supply Chain Management
- An Integration Service Account with OAuth2 credentials
- Your Oracle Cloud tenant URL

## OAuth2 setup

1. In Oracle Identity Cloud Service (IDCS), create a confidential application
2. Grant the following Oracle SCM API scopes:
   - `urn:opc:resource:consumer::all`
3. Note the Client ID and Client Secret

## Environment variables

```bash
OPENQUOTE_ORACLE_BASE_URL=https://your-tenant.oraclecloud.com
OPENQUOTE_ORACLE_CLIENT_ID=your_client_id
OPENQUOTE_ORACLE_CLIENT_SECRET=your_client_secret
```

## Endpoints used

| Method | Endpoint |
|---|---|
| Search items | `/fscmRestApi/resources/11.13.18.05/items` |
| Get item | `/fscmRestApi/resources/11.13.18.05/items/{ItemNumber}` |

## Usage

```python
from openquote import QuoteAgent
from openquote.mcp import OracleMCP

agent = QuoteAgent(erp=OracleMCP())
```
