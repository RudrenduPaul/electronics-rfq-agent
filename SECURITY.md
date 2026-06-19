# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| >= 0.1.x | Yes |

## Reporting a Vulnerability

Do NOT open a public GitHub issue for security vulnerabilities.

**Email:** security@openquote.ai
**Response SLA:** 48 hours acknowledgement, 7 days fix timeline

We follow responsible disclosure: public disclosure happens 90 days after report or after patch ships, whichever is first.

## Scope

This policy covers the core library (`src/`). Third-party integrations (SAP PyRFC, Epicor REST, Oracle, Dynamics) are covered on a best-effort basis — please identify the specific integration in your report.

## What We Consider a Vulnerability

- Credential exposure (API keys, passwords logged or transmitted insecurely)
- Path traversal in RFQ file parsing
- SSRF via ERP connector URLs
- Injection attacks via part number or query fields
- TLS bypass or certificate validation disabled

## What We Do NOT Consider a Vulnerability

- Denial of service via large RFQ files (rate limiting is the deployer's responsibility)
- Issues in dependencies that have no fix available (we track via Dependabot and Trivy)

## Security Practices

- All credentials via environment variables, never hardcoded
- TLS verification enforced on all HTTP clients (`verify=True`)
- Input validation on all part numbers and file paths
- Sensitive fields (`api_key`, `password`) masked in `__repr__` and logs
- Dependency updates via Dependabot (weekly patch, monthly minor/major)
- Trivy vulnerability scanning in CI (blocks on HIGH/CRITICAL)
- OpenSSF Scorecard monitored weekly
