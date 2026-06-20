from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any

from electronics_rfq_agent.models import RFQLineItem, RFQParseError


class RFQParser:
    """Parse RFQ documents into structured line items.

    Handles PDF (Claude vision), Excel (.xlsx/.xls via openpyxl),
    Word (.docx via python-docx), and plain text (sent to Claude).

    Args:
        model: Anthropic model to use for AI-assisted parsing.
               Defaults to ERFA_MODEL env var or claude-sonnet-4-6.
    """

    _SYSTEM_PROMPT = (
        "You are an RFQ (Request for Quote) parser for electronics components. "
        "Extract all line items from the document. "
        "For each line item, identify: part_number, quantity, "
        "required_date (ISO format if present), "
        "manufacturer (if specified), and any customer_notes. "
        "Return a JSON array where each object has keys: "
        "line_number (int), part_number (str), quantity (int), "
        "required_date (str or null), manufacturer (str or null), "
        "customer_notes (str or null). "
        "If a field is not present in the document, set it to null. "
        "Return ONLY the JSON array, no other text."
    )

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("ERFA_MODEL", "claude-sonnet-4-6")

    async def parse(self, source: str | Path) -> list[RFQLineItem]:
        """Parse an RFQ from a file path or text string."""
        if isinstance(source, str) and not Path(source).exists():
            return await self._parse_text(source)

        path = Path(source)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return await self._parse_pdf(path)
        if suffix in (".xlsx", ".xls"):
            return await asyncio.to_thread(self._parse_excel, path)
        if suffix == ".docx":
            return await asyncio.to_thread(self._parse_word, path)
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError) as exc:
            raise RFQParseError(f"Cannot read {path}: {exc}") from exc
        return await self._parse_text(text)

    async def _parse_pdf(self, path: Path) -> list[RFQLineItem]:
        import anthropic  # noqa: PLC0415

        client = anthropic.AsyncAnthropic()
        pdf_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        response = await client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract all RFQ line items from this document.",
                        },
                    ],
                }
            ],
            system=self._SYSTEM_PROMPT,
        )
        if not response.content or not hasattr(response.content[0], "text"):
            raise RFQParseError(
                "Anthropic API returned no parseable text content for PDF"
            )
        # ContentBlock is a union type in the Anthropic SDK; .text only exists on
        # TextBlock. We guard with hasattr() above so the access is safe at runtime.
        text = response.content[0].text  # type: ignore[union-attr]
        return self._parse_json_response(text)

    def _parse_excel(self, path: Path) -> list[RFQLineItem]:
        import openpyxl  # noqa: PLC0415

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

        # Search all sheets for one with a recognizable BOM header.
        # Active sheet is often a cover/summary page; the BOM may be on another sheet.
        for ws in wb.worksheets:
            rows: list[list[Any]] = [list(row) for row in ws.values]  # type: ignore[arg-type]
            if not rows:
                continue
            header_idx = self._find_header_row(rows)
            if header_idx is None:
                continue

            header = [str(c).lower().strip() if c else "" for c in rows[header_idx]]
            col = self._map_columns(header)
            items: list[RFQLineItem] = []
            line_number = 1

            for row in rows[header_idx + 1 :]:
                part_num = self._cell(row, col.get("part_number"))
                if not part_num:
                    continue
                qty_raw = self._cell(row, col.get("quantity"))
                try:
                    qty = int(float(qty_raw)) if qty_raw else 1
                except ValueError:
                    qty = 1

                items.append(
                    RFQLineItem(
                        line_number=line_number,
                        part_number=part_num,
                        quantity=qty,
                        required_date=None,
                        manufacturer=self._cell(row, col.get("manufacturer")) or None,
                        customer_notes=self._cell(row, col.get("notes")) or None,
                    )
                )
                line_number += 1
            return items
        return []

    def _parse_word(self, path: Path) -> list[RFQLineItem]:
        from docx import Document  # noqa: PLC0415

        doc = Document(str(path))
        items: list[RFQLineItem] = []
        line_number = 1

        for table in doc.tables:
            if not table.rows:
                continue
            header_cells = [c.text.lower().strip() for c in table.rows[0].cells]
            col = self._map_columns(header_cells)
            if col.get("part_number") is None:
                continue

            for row in table.rows[1:]:
                cells = [c.text.strip() for c in row.cells]
                part_num = self._cell(cells, col.get("part_number"))
                if not part_num:
                    continue
                qty_raw = self._cell(cells, col.get("quantity"))
                try:
                    qty = int(float(qty_raw)) if qty_raw else 1
                except ValueError:
                    qty = 1

                items.append(
                    RFQLineItem(
                        line_number=line_number,
                        part_number=part_num,
                        quantity=qty,
                        required_date=None,
                        manufacturer=self._cell(cells, col.get("manufacturer")) or None,
                        customer_notes=self._cell(cells, col.get("notes")) or None,
                    )
                )
                line_number += 1
        return items

    async def _parse_text(self, text: str) -> list[RFQLineItem]:
        import anthropic  # noqa: PLC0415

        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self._SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        if not response.content or not hasattr(response.content[0], "text"):
            raise RFQParseError("Anthropic API returned no parseable text content")
        # Same Anthropic SDK union-attr caveat as _parse_pdf; hasattr guard above.
        raw = response.content[0].text  # type: ignore[union-attr]
        return self._parse_json_response(raw)

    def _parse_json_response(self, text: str) -> list[RFQLineItem]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # strip opening fence (```json, ``` etc.) and closing fence
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            cleaned = "\n".join(lines[start:end])

        try:
            raw = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RFQParseError(f"Model returned invalid JSON: {exc}") from exc
        # json.loads returns Any at runtime; guard against models returning a
        # JSON object or scalar instead of the expected array.
        if not isinstance(raw, list):
            raise RFQParseError(
                f"Model returned a JSON {type(raw).__name__}, expected an array"
            )
        items: list[RFQLineItem] = []
        for i, row in enumerate(raw, start=1):
            try:
                items.append(
                    RFQLineItem(
                        line_number=int(row.get("line_number", i)),
                        part_number=str(row["part_number"]),
                        quantity=int(row.get("quantity", 1)),
                        required_date=row.get("required_date"),
                        manufacturer=row.get("manufacturer"),
                        customer_notes=row.get("customer_notes"),
                    )
                )
            except (KeyError, ValueError, AttributeError, TypeError):
                continue
        return items

    @staticmethod
    def _find_header_row(rows: list[list[Any]]) -> int | None:
        keywords = {"part", "pn", "item", "qty", "quantity", "description"}
        for i, row in enumerate(rows[:10]):
            cells = [str(c).lower() for c in row if c is not None]
            if any(any(k in cell for k in keywords) for cell in cells):
                return i
        return None

    @staticmethod
    def _map_columns(header: list[str]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for i, col in enumerate(header):
            if any(k in col for k in ("part", "pn", "item", "mpn", "mfr part")):
                mapping.setdefault("part_number", i)
            elif any(k in col for k in ("qty", "quantity", "amount")):
                mapping.setdefault("quantity", i)
            elif any(k in col for k in ("mfr", "manufacturer", "brand", "vendor")):
                mapping.setdefault("manufacturer", i)
            elif any(k in col for k in ("note", "comment", "remark")):
                mapping.setdefault("notes", i)
        return mapping

    @staticmethod
    def _cell(row: Any, idx: int | None) -> str:
        """Return the string value at index `idx` in any subscriptable sequence."""
        if idx is None:
            return ""
        try:
            val = row[idx]
            return str(val).strip() if val is not None else ""
        except (IndexError, TypeError):
            return ""
