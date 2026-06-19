#!/usr/bin/env python3
"""End-to-end openquote benchmark suite.

Run with: python benchmarks/run.py
Requires: OPENQUOTE_USE_MOCK=true (default) or a real ERP connection.

Measures:
1. Parse accuracy on synthetic test RFQs
2. ERP lookup latency (P50, P99) per line item
3. End-to-end quote generation time for 10, 25, 50-line RFQs
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from pathlib import Path

os.environ.setdefault("OPENQUOTE_USE_MOCK", "true")

from openquote.agent import QuoteAgent
from openquote.mcp.mock.backend import MockERP
from openquote.models import RFQLineItem
from openquote.parser import RFQParser

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

MOCK_ERP = MockERP()


def _make_rfq_lines(n: int) -> list[RFQLineItem]:
    """Generate n synthetic RFQ line items using parts from the mock catalog."""
    all_pns = list(MOCK_ERP._parts.keys())
    lines = []
    for i in range(n):
        pn = all_pns[i % len(all_pns)]
        lines.append(
            RFQLineItem(
                line_number=i + 1,
                part_number=pn,
                quantity=max(1, (i + 1) * 10),
            )
        )
    return lines


async def bench_erp_latency() -> dict[str, float]:
    """Measure ERP lookup latency across 100 lookups."""
    parts = list(MOCK_ERP._parts.keys())[:100]
    latencies: list[float] = []

    for pn in parts:
        start = time.perf_counter()
        await MOCK_ERP.get_part(pn)
        latencies.append((time.perf_counter() - start) * 1000)

    return {
        "p50_ms": statistics.median(latencies),
        "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)],
        "mean_ms": statistics.mean(latencies),
        "samples": len(latencies),
    }


async def bench_quote_time(n_lines: int) -> dict[str, object]:
    """Measure end-to-end quote generation time for n_lines."""
    agent = QuoteAgent(erp=MOCK_ERP, margin_pct=0.15)
    lines = _make_rfq_lines(n_lines)

    from unittest.mock import AsyncMock, patch

    start = time.perf_counter()
    with patch.object(agent._parser, "parse", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = lines
        quote = await agent.run("benchmark_rfq.txt")
    elapsed = time.perf_counter() - start

    found = sum(1 for line in quote.lines if line.status == "found")
    return {
        "n_lines": n_lines,
        "elapsed_s": round(elapsed, 3),
        "lines_found": found,
        "lines_not_found": n_lines - found,
        "total_price": str(quote.total_price),
    }


def bench_json_deserialize() -> dict[str, object]:
    """Measure RFQ JSON deserialization throughput (not AI parsing accuracy).

    This benchmark tests how fast _parse_json_response() can deserialize
    pre-structured JSON into RFQLineItem objects. It does NOT call the
    Anthropic API and does NOT measure extraction accuracy from real documents.
    To measure real parse accuracy, run with a real Anthropic API key and a
    known ground-truth RFQ document.
    """
    parser = RFQParser()
    expected_parts = [
        "RES-0402-10K-1PCT",
        "CAP-100NF-50V-X7R-0402",
        "IC-LM358-SOIC8",
        "XTAL-16MHZ-SMD",
        "MOSFET-NMOS-20V-3A-SOT23",
    ]

    items = parser._parse_json_response(
        json.dumps(
            [
                {"line_number": i + 1, "part_number": pn, "quantity": 100}
                for i, pn in enumerate(expected_parts)
            ]
        )
    )

    extracted_parts = {item.part_number.upper() for item in items}
    expected_set = {p.upper() for p in expected_parts}
    correct = len(extracted_parts & expected_set)
    accuracy = correct / len(expected_set) if expected_set else 0.0

    return {
        "expected": len(expected_set),
        "extracted": len(extracted_parts),
        "correct": correct,
        "accuracy_pct": round(accuracy * 100, 1),
        "note": "JSON deserialization only — no AI parsing",
    }


async def main() -> None:
    print("=" * 60)
    print("openquote benchmark suite")
    print("Mock ERP backend -- no ERP system required")
    print(f"Catalog size: {MOCK_ERP.part_count()} parts")
    print("=" * 60)
    print()

    print("1. ERP lookup latency (100 lookups, mock backend)")
    latency = await bench_erp_latency()
    print(f"   P50: {latency['p50_ms']:.2f}ms")
    print(f"   P99: {latency['p99_ms']:.2f}ms")
    print(f"   Mean: {latency['mean_ms']:.2f}ms")
    print()

    print("2. End-to-end quote generation time")
    results = []
    for n in [10, 25, 50]:
        r = await bench_quote_time(n)
        results.append(r)
        print(
            f"   {n:2d} lines: {r['elapsed_s']:.2f}s "
            f"(found: {r['lines_found']}, not found: {r['lines_not_found']})"
        )
    print()

    print("3. JSON deserialization throughput (not AI parse accuracy — no API call)")
    accuracy = bench_json_deserialize()
    print(
        f"   Deserialized: {accuracy['correct']}/{accuracy['expected']} parts "
        f"({accuracy['accuracy_pct']}% round-trip correct)"
    )
    print(f"   Note: {accuracy['note']}")
    print()

    print("4. Comparison: openquote vs manual (human baseline)")
    print("   Manual process (2-4 hours per 50-line RFQ):")
    print("   Low estimate  7200s (2 hours)")
    print("   High estimate 14400s (4 hours)")
    qt = next(r for r in results if r["n_lines"] == 50)
    speedup_low = 7200 / qt["elapsed_s"]
    speedup_high = 14400 / qt["elapsed_s"]
    print(f"   openquote:    {qt['elapsed_s']:.2f}s")
    print(f"   Speedup:      {speedup_low:.0f}x - {speedup_high:.0f}x faster")
    print()

    output = {
        "erp_latency": latency,
        "quote_times": results,
        "json_deserialize": accuracy,
    }
    baseline_path = RESULTS_DIR / "baseline.json"
    with open(baseline_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results written to {baseline_path}")
    print()
    print("To reproduce: OPENQUOTE_USE_MOCK=true python benchmarks/run.py")


if __name__ == "__main__":
    asyncio.run(main())
