# SAP ECC / S/4HANA Setup

## Prerequisites

- SAP ECC 6.0+ or SAP S/4HANA
- SAP NetWeaver RFC Library (free download from SAP Support Portal)
- pyrfc Python package: `pip install openquote[sap]`

## SAP NetWeaver RFC Library installation

1. Download from SAP Support Portal (search "SAP NW RFC SDK")
2. Set environment variables:
   ```bash
   export SAPNWRFC_HOME=/path/to/nwrfcsdk
   export LD_LIBRARY_PATH=$SAPNWRFC_HOME/lib:$LD_LIBRARY_PATH  # Linux
   # macOS: export DYLD_LIBRARY_PATH=$SAPNWRFC_HOME/lib:$DYLD_LIBRARY_PATH
   ```
3. Install pyrfc: `pip install pyrfc`

## Environment variables

```bash
OPENQUOTE_SAP_HOST=your-sap-host.company.com
OPENQUOTE_SAP_SYSNR=00
OPENQUOTE_SAP_CLIENT=100
OPENQUOTE_SAP_USER=your_rfc_username
OPENQUOTE_SAP_PASSWORD=your_rfc_password
```

## Required SAP authorizations

| Authorization object | Field | Value |
|---|---|---|
| S_RFC | RFC_TYPE | FUGR |
| S_RFC | RFC_NAME | BAPI_MATERIAL_* |
| M_MATE_STA | MMSTA | all |
| M_MSEG_BWA | BWART | 101 |

## BAPIs used

| BAPI | Purpose |
|---|---|
| `BAPI_MATERIAL_GETLIST` | Search materials |
| `BAPI_MATERIAL_GET_DETAIL` | Get material details |
| `BAPI_MATERIAL_GETPRICINGINFO` | Get price data |

## Usage

```python
from openquote import QuoteAgent
from openquote.mcp import SAPMCP

agent = QuoteAgent(erp=SAPMCP(plant="0001"))
```

## Development without SAP access

```bash
OPENQUOTE_USE_MOCK=true python examples/01-basic-quote/basic_quote.py
```
