# Benchmarks

All benchmark numbers in the README are reproducible with this command:

```bash
docker compose up -d
python benchmarks/run.py
```

No ERP system required. The mock backend loads 200 realistic electronics parts.

## What is measured

| Metric | Description | Target |
|---|---|---|
| Parse accuracy | % of line items correctly extracted from synthetic RFQs | >95% |
| ERP lookup latency P50 | Median milliseconds per line item (mock backend) | <50ms |
| ERP lookup latency P99 | 99th percentile ms per line item | <200ms |
| End-to-end 10-line RFQ | Seconds from file to draft quote | <5s |
| End-to-end 25-line RFQ | Seconds from file to draft quote | <8s |
| End-to-end 50-line RFQ | Seconds from file to draft quote | <20s |

## Caveats

- Parse accuracy benchmarks are measured against synthetic test RFQs, not real customer documents
- ERP latency numbers use the in-memory mock backend; real ERP latency depends on network and system load
- End-to-end times include one Claude API call for parsing; latency varies by model and load
- All numbers are for single-threaded sequential processing; `asyncio.gather` parallelizes ERP lookups

## Running individual benchmarks

```bash
# ERP lookup latency only (no API calls needed)
OPENQUOTE_USE_MOCK=true uv run pytest benchmarks/ -k "erp_latency" -v

# Full suite
uv run python benchmarks/run.py
```
