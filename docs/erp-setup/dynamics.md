# Microsoft Dynamics 365 Setup

## Prerequisites

- Microsoft Dynamics 365 Sales or Supply Chain Management
- Azure Active Directory tenant
- An app registration with Dynamics 365 API permissions

## Azure AD app registration

1. Go to Azure Portal > Azure Active Directory > App registrations
2. Create a new registration
3. Add API permissions: Dynamics CRM > user_impersonation (or application permissions)
4. Create a client secret
5. Note: Tenant ID, Client ID, Client Secret

## Environment variables

```bash
OPENQUOTE_DYNAMICS_TENANT_ID=your-tenant-id
OPENQUOTE_DYNAMICS_CLIENT_ID=your-client-id
OPENQUOTE_DYNAMICS_CLIENT_SECRET=your-client-secret
OPENQUOTE_DYNAMICS_BASE_URL=https://your-org.api.crm.dynamics.com
```

## Endpoints used

| Method | Endpoint |
|---|---|
| Search products | `/api/data/v9.2/products` |
| Get product | `/api/data/v9.2/products?$filter=productnumber eq '...'` |

## Usage

```python
from openquote import QuoteAgent
from openquote.mcp import DynamicsMCP

agent = QuoteAgent(erp=DynamicsMCP())
```
