# Epicor Kinetic Setup

## Prerequisites

- Epicor Kinetic 2022 or later
- A service account with API access
- Base URL of your Epicor instance

## Authentication

Epicor uses HTTP Basic auth. Encode your credentials:

```bash
echo -n "username:password" | base64
```

Use the output as your `api_key`.

## Environment variables

```bash
ERFA_EPICOR_URL=https://your-epicor.company.com
ERFA_EPICOR_API_KEY=dXNlcm5hbWU6cGFzc3dvcmQ=  # base64(user:pass)
ERFA_EPICOR_COMPANY=EPIC  # your Epicor company code
```

## Usage

```python
from electronics_rfq_agent import QuoteAgent
from electronics_rfq_agent.mcp import EpicorMCP

agent = QuoteAgent(erp=EpicorMCP())  # reads from env vars
```

## Endpoints used

| Method | Endpoint |
|---|---|
| Search parts | `/api/v2/odata/{Company}/Erp.BO.PartSvc/Parts` |
| Get part | `/api/v2/odata/{Company}/Erp.BO.PartSvc/Parts(Company=...,PartNum=...)` |

## Required Epicor permissions

The service account needs:
- `BO:Part.GetRows` -- search parts
- `BO:Part.GetByID` -- get individual part
