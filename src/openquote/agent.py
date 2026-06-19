from __future__ import annotations

import asyncio
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from openquote.mcp.base import ERPMCPServer
from openquote.models import Quote, QuoteLineItem, RFQLineItem
from openquote.parser import RFQParser

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
    ) -> None:
        self.erp = erp
        self.model = model or os.environ.get("OPENQUOTE_MODEL", "claude-sonnet-4-6")
        self.margin_pct = Decimal(str(margin_pct))
        self._parser = RFQParser(model=self.model)
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run(self, rfq_source: str | Path) -> Quote:
        """Parse the RFQ and generate a draft quote.

        Args:
            rfq_source: File path (PDF/Excel/Word) or text string of the RFQ.

        Returns:
            A Quote with all line items looked up against the ERP.
        """
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
            quote_lines = await asyncio.gather(
                *[self._gated_lookup(line) for line in rfq_lines]
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

        if is_tty:
            elapsed = time.monotonic() - start
            _console.print(
                f"[green]Quote complete[/green] — "
                f"{len(rfq_lines)} lines in {elapsed:.1f}s"
            )
        return quote

    def run_sync(self, rfq_source: str | Path) -> Quote:
        """Synchronous wrapper for run(). Safe inside existing event loops."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(rfq_source))
        import nest_asyncio  # noqa: PLC0415

        nest_asyncio.apply()
        return loop.run_until_complete(self.run(rfq_source))

    async def _gated_lookup(self, line: RFQLineItem) -> QuoteLineItem:
        async with self._semaphore:
            return await self._lookup_line(line)

    async def _lookup_line(self, line: RFQLineItem) -> QuoteLineItem:
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

        sell_price = (cost_price * (1 + self.margin_pct)).quantize(Decimal("0.0001"))
        extended = (sell_price * line.quantity).quantize(Decimal("0.01"))

        is_exact = part.part_number.upper() == line.part_number.upper()
        status: str = "found" if is_exact else "substituted"
        notes = (
            None
            if is_exact
            else f"Substituted {line.part_number!r} with {part.part_number!r}"
        )

        return QuoteLineItem(
            rfq_line=line,
            erp_result=part,
            status=status,  # type: ignore[arg-type]
            unit_price=sell_price,
            extended_price=extended,
            notes=notes,
        )
