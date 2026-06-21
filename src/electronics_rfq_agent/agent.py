from __future__ import annotations

import asyncio
import os
import sys
import time
import warnings
from decimal import Decimal
from pathlib import Path
from typing import Literal

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from electronics_rfq_agent.mcp.base import ERPMCPServer
from electronics_rfq_agent.models import (
    ERPConnectionError,
    Quote,
    QuoteLineItem,
    RFQLineItem,
)
from electronics_rfq_agent.parser import RFQParser
from electronics_rfq_agent.telemetry import (
    TelemetryCollector,
    TelemetryEvent,
    collector_from_env,
)

_console = Console(stderr=True)


class QuoteAgent:
    """Orchestrate RFQ parsing, ERP lookup, and draft quote generation.

    Args:
        erp: Any ERPMCPServer implementation (EpicorMCP, SAPMCP, MockERP, etc.)
        model: Anthropic model for RFQ parsing (default: claude-sonnet-4-6)
        margin_pct: Margin to add on top of ERP cost price (default: 0.15 = 15%)
        max_concurrent: Maximum parallel ERP lookups (default: 10)
    """

    def __init__(
        self,
        erp: ERPMCPServer,
        model: str | None = None,
        margin_pct: float = 0.15,
        max_concurrent: int = 10,
        telemetry: bool | TelemetryCollector = False,
    ) -> None:
        self.erp = erp
        self.model = model or os.environ.get("ERFA_MODEL", "claude-sonnet-4-6")
        self.margin_pct = Decimal(str(margin_pct))
        self._parser = RFQParser(model=self.model)
        self._max_concurrent = max_concurrent
        if isinstance(telemetry, TelemetryCollector):
            self._telemetry: TelemetryCollector | None = telemetry
        elif telemetry:
            self._telemetry = TelemetryCollector()
        else:
            self._telemetry = collector_from_env()

    async def run(self, rfq_source: str | Path) -> Quote:
        """Parse the RFQ and generate a draft quote.

        Args:
            rfq_source: File path (PDF/Excel/Word) or text string of the RFQ.

        Returns:
            A Quote with all line items looked up against the ERP.
        """
        semaphore = asyncio.Semaphore(self._max_concurrent)
        start = time.monotonic()
        is_tty = sys.stderr.isatty()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=_console,
            transient=True,
            disable=not is_tty,
        ) as progress:
            task_id = progress.add_task("Parsing RFQ...", total=None)
            rfq_lines = await self._parser.parse(rfq_source)
            progress.update(task_id, description=f"Parsed {len(rfq_lines)} line items")
            progress.update(task_id, description="Looking up parts in ERP...")
            # One asyncio Task per unique (part_number, quantity) pair.
            # Duplicate lines share the same Task -- ERP is called once, not N times.
            task_cache: dict[tuple[str, int], asyncio.Task[QuoteLineItem]] = {}

            async def _cached_lookup(ln: RFQLineItem) -> QuoteLineItem:
                key = (ln.part_number, ln.quantity)
                if key not in task_cache:
                    task_cache[key] = asyncio.create_task(
                        self._gated_lookup(ln, semaphore)
                    )
                result = await task_cache[key]
                if result.rfq_line is ln:
                    return result
                return result.model_copy(update={"rfq_line": ln})

            quote_lines = await asyncio.gather(
                *[_cached_lookup(line) for line in rfq_lines]
            )
            progress.update(task_id, description="Building quote...")

        total = sum(
            (ln.extended_price for ln in quote_lines if ln.extended_price is not None),
            Decimal("0"),
        )
        quote = Quote(
            rfq_source=str(rfq_source),
            lines=list(quote_lines),
            total_price=total,
        )

        elapsed = time.monotonic() - start
        if is_tty:
            _console.print(
                f"[green]Quote complete[/green]: "
                f"{len(rfq_lines)} lines in {elapsed:.1f}s"
            )
        if self._telemetry is not None:
            from electronics_rfq_agent import __version__  # noqa: PLC0415

            counts = {"found": 0, "not_found": 0, "substituted": 0}
            for ln in quote.lines:
                counts[ln.status] += 1
            self._telemetry.record(
                TelemetryEvent(
                    erp_type=type(self.erp).__name__,
                    line_count=len(quote.lines),
                    found_count=counts["found"],
                    not_found_count=counts["not_found"],
                    substituted_count=counts["substituted"],
                    duration_ms=int(elapsed * 1000),
                    erfa_version=__version__,
                )
            )
        return quote

    def run_sync(self, rfq_source: str | Path) -> Quote:
        """Synchronous wrapper for run(). Safe inside existing event loops."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(rfq_source))
        import nest_asyncio  # noqa: PLC0415

        warnings.filterwarnings(
            "ignore", category=DeprecationWarning, module="nest_asyncio"
        )
        nest_asyncio.apply()
        return loop.run_until_complete(self.run(rfq_source))

    async def _gated_lookup(
        self, line: RFQLineItem, semaphore: asyncio.Semaphore
    ) -> QuoteLineItem:
        async with semaphore:
            return await self._lookup_line(line)

    async def _lookup_line(self, line: RFQLineItem) -> QuoteLineItem:
        # All ERP calls are inside one try-except: get_price() also makes
        # network requests and can raise the same exceptions as get_part().
        try:
            part = await self.erp.get_part(line.part_number)
            if part is None:
                parts = await self.erp.search_parts(line.part_number, limit=1)
                part = parts[0] if parts else None
            if part is None:
                return QuoteLineItem(
                    rfq_line=line,
                    erp_result=None,
                    status="not_found",
                    notes=f"Part {line.part_number!r} not found in ERP catalog",
                )
            cost_price = await self.erp.get_price(part.part_number, line.quantity)
            if cost_price is None:
                cost_price = part.unit_price
        except (ERPConnectionError, httpx.HTTPError) as exc:
            return QuoteLineItem(
                rfq_line=line,
                erp_result=None,
                status="not_found",
                notes=f"ERP lookup failed for {line.part_number!r}: {exc}",
            )

        sell_price = (cost_price * (1 + self.margin_pct)).quantize(Decimal("0.0001"))
        extended = (sell_price * line.quantity).quantize(Decimal("0.01"))

        is_exact = part.part_number.upper() == line.part_number.upper()
        status: Literal["found", "substituted"] = "found" if is_exact else "substituted"

        notes_parts = []
        if not is_exact:
            notes_parts.append(
                f"Substituted {line.part_number!r} with {part.part_number!r}"
            )
        if cost_price == Decimal("0"):
            notes_parts.append(
                f"Part {part.part_number!r} has zero unit price in ERP"
                " — verify pricing manually"
            )
        notes = "; ".join(notes_parts) or None

        return QuoteLineItem(
            rfq_line=line,
            erp_result=part,
            status=status,
            unit_price=sell_price,
            extended_price=extended,
            notes=notes,
        )
