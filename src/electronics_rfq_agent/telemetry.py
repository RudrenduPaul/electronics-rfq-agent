"""Opt-in, anonymized telemetry for design-partner usage tracking.

Enable by setting ERFA_TELEMETRY=true or passing telemetry=True to
QuoteAgent.  No part numbers, prices, or customer data are ever recorded.

Data written to: ~/.erfa/telemetry.jsonl  (one JSON object per line)
Optional HTTP push: ERFA_TELEMETRY_ENDPOINT=https://your-endpoint/ingest
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TelemetryEvent:
    """Anonymized record of a single quote run."""

    erp_type: str
    line_count: int
    found_count: int
    not_found_count: int
    substituted_count: int
    duration_ms: int
    erfa_version: str = field(default="")
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "erp_type": self.erp_type,
            "line_count": self.line_count,
            "found": self.found_count,
            "not_found": self.not_found_count,
            "substituted": self.substituted_count,
            "duration_ms": self.duration_ms,
            "version": self.erfa_version,
        }


class TelemetryCollector:
    """Writes anonymized events to a local JSONL file and optionally an HTTP endpoint.

    Failures are silently swallowed — telemetry must never break a quote run.
    """

    def __init__(
        self,
        log_path: Path | None = None,
        endpoint: str | None = None,
    ) -> None:
        self._log_path = log_path or Path.home() / ".erfa" / "telemetry.jsonl"
        self._endpoint = endpoint or os.environ.get("ERFA_TELEMETRY_ENDPOINT", "")
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._tasks_lock = threading.Lock()

    def record(self, event: TelemetryEvent) -> None:
        self._write_local(event)
        if self._endpoint:
            try:
                loop = asyncio.get_running_loop()
                _task = loop.create_task(self._push_http_async(event))
                with self._tasks_lock:
                    self._background_tasks.add(_task)

                def _remove_task(t: asyncio.Task[None]) -> None:
                    with self._tasks_lock:
                        self._background_tasks.discard(t)

                _task.add_done_callback(_remove_task)
            except RuntimeError:
                self._push_http_sync(event)

    def _write_local(self, event: TelemetryEvent) -> None:
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
        except Exception:  # noqa: S110 — telemetry must never crash a quote run
            pass

    async def _push_http_async(self, event: TelemetryEvent) -> None:
        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient() as client:
                await client.post(
                    self._endpoint,
                    json=event.to_dict(),
                    timeout=5.0,
                )
        except Exception:  # noqa: S110 — telemetry must never crash a quote run
            pass

    def _push_http_sync(self, event: TelemetryEvent) -> None:
        try:
            import httpx  # noqa: PLC0415

            httpx.post(
                self._endpoint,
                json=event.to_dict(),
                timeout=5.0,
            )
        except Exception:  # noqa: S110 — telemetry must never crash a quote run
            pass


def collector_from_env() -> TelemetryCollector | None:
    """Return a TelemetryCollector if ERFA_TELEMETRY=true, else None."""
    if os.environ.get("ERFA_TELEMETRY", "").lower() == "true":
        return TelemetryCollector()
    return None
