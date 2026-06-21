#!/usr/bin/env python3
"""Generate an HTML benchmark report from benchmarks/results/baseline.json.

Usage: python benchmarks/generate_report.py [--output _site/index.html]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "results" / "baseline.json"
DEFAULT_OUTPUT = Path("_site") / "index.html"


def _row(cells: list[str], tag: str = "td") -> str:
    inner = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
    return f"<tr>{inner}</tr>"


def render(data: dict, commit_sha: str = "") -> str:
    lat = data.get("erp_latency", {})
    qt_rows = "".join(
        _row(
            [
                str(r["n_lines"]),
                f"{r['elapsed_s']:.3f}",
                str(r["lines_found"]),
                str(r["lines_not_found"]),
            ]
        )
        for r in data.get("quote_times", [])
    )
    jd = data.get("json_deserialize", {})
    sha_line = (
        f"<p class='sha'>Commit: <code>{commit_sha}</code></p>" if commit_sha else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Electronics RFQ Agent — Benchmarks</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.5rem; border-bottom: 2px solid #e2e8f0; padding-bottom: .5rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; color: #2d3748; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: .75rem; }}
  th, td {{ text-align: left; padding: .4rem .75rem; border: 1px solid #e2e8f0; }}
  th {{ background: #f7fafc; font-weight: 600; }}
  .stat {{ display: inline-block; margin-right: 2rem; }}
  .stat-val {{ font-size: 2rem; font-weight: 700; color: #2b6cb0; }}
  .stat-lbl {{ font-size: .75rem; color: #718096; text-transform: uppercase; }}
  .sha {{ font-size: .75rem; color: #a0aec0; margin-top: 2rem; }}
  .badge {{ display: inline-block; background: #c6f6d5; color: #276749; border-radius: 4px; padding: 2px 8px; font-size: .8rem; font-weight: 600; }}
</style>
</head>
<body>
<h1>Electronics RFQ Agent — Benchmark Results <span class="badge">mock backend</span></h1>

<h2>ERP Lookup Latency</h2>
<div>
  <span class="stat">
    <div class="stat-val">{lat.get("p50_ms", 0):.4f} ms</div>
    <div class="stat-lbl">P50</div>
  </span>
  <span class="stat">
    <div class="stat-val">{lat.get("p99_ms", 0):.4f} ms</div>
    <div class="stat-lbl">P99</div>
  </span>
  <span class="stat">
    <div class="stat-val">{lat.get("mean_ms", 0):.4f} ms</div>
    <div class="stat-lbl">Mean</div>
  </span>
  <span class="stat">
    <div class="stat-val">{lat.get("samples", 0)}</div>
    <div class="stat-lbl">Samples</div>
  </span>
</div>

<h2>End-to-End Quote Generation Time</h2>
<table>
  <thead>{_row(["Lines", "Elapsed (s)", "Found", "Not found"], "th")}</thead>
  <tbody>{qt_rows}</tbody>
</table>

<h2>JSON Deserialization Accuracy</h2>
<p>{jd.get("correct", 0)}/{jd.get("expected", 0)} parts correct ({jd.get("accuracy_pct", 0):.1f}%)</p>
<p style="color:#718096;font-size:.85rem">{jd.get("note", "")}</p>

{sha_line}
<p class="sha">To reproduce: <code>ERFA_USE_MOCK=true python benchmarks/run.py</code></p>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate benchmark HTML report")
    parser.add_argument(
        "--input", default=str(RESULTS_PATH), help="Path to baseline.json"
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT), help="Output HTML path"
    )
    parser.add_argument("--sha", default="", help="Git commit SHA to embed")
    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"ERROR: {src} not found — run benchmarks/run.py first", file=sys.stderr)
        sys.exit(1)

    data = json.loads(src.read_text())
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data, args.sha))
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
