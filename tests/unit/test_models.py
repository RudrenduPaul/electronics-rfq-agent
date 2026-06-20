from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from electronics_rfq_agent.models import (
    ERPConfig,
    ERPPartResult,
    Quote,
    QuoteLineItem,
    RFQLineItem,
)


class TestRFQLineItem:
    def test_valid_basic(self) -> None:
        item = RFQLineItem(line_number=1, part_number="ABC-123", quantity=10)
        assert item.part_number == "ABC-123"
        assert item.quantity == 10

    def test_part_number_stripped(self) -> None:
        item = RFQLineItem(line_number=1, part_number="  ABC-123  ", quantity=1)
        assert item.part_number == "ABC-123"

    def test_part_number_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            RFQLineItem(line_number=1, part_number="   ", quantity=1)

    def test_quantity_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            RFQLineItem(line_number=1, part_number="ABC", quantity=0)

    def test_line_number_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            RFQLineItem(line_number=0, part_number="ABC", quantity=1)

    def test_optional_fields_none(self) -> None:
        item = RFQLineItem(line_number=1, part_number="ABC", quantity=1)
        assert item.required_date is None
        assert item.customer_notes is None
        assert item.manufacturer is None

    def test_with_date(self) -> None:
        item = RFQLineItem(
            line_number=1,
            part_number="ABC",
            quantity=5,
            required_date=date(2026, 9, 1),
        )
        assert item.required_date == date(2026, 9, 1)

    def test_part_number_with_special_chars(self) -> None:
        item = RFQLineItem(line_number=1, part_number="RES-0402-10K-1%", quantity=1)
        assert item.part_number == "RES-0402-10K-1%"

    def test_control_character_raises(self) -> None:
        with pytest.raises(ValidationError):
            RFQLineItem(line_number=1, part_number="ABC\x00DEF", quantity=1)

    def test_frozen_model_immutable(self) -> None:
        item = RFQLineItem(line_number=1, part_number="ABC", quantity=1)
        with pytest.raises(Exception):
            item.part_number = "NEW"  # type: ignore[misc]

    def test_negative_quantity_raises(self) -> None:
        with pytest.raises(ValidationError):
            RFQLineItem(line_number=1, part_number="ABC", quantity=-5)

    def test_customer_notes_stored(self) -> None:
        item = RFQLineItem(
            line_number=1, part_number="ABC", quantity=1, customer_notes="urgent"
        )
        assert item.customer_notes == "urgent"

    def test_manufacturer_stored(self) -> None:
        item = RFQLineItem(
            line_number=1, part_number="ABC", quantity=1, manufacturer="Yageo"
        )
        assert item.manufacturer == "Yageo"

    def test_large_quantity_valid(self) -> None:
        item = RFQLineItem(line_number=1, part_number="ABC", quantity=100_000)
        assert item.quantity == 100_000

    def test_negative_line_number_raises(self) -> None:
        with pytest.raises(ValidationError):
            RFQLineItem(line_number=-1, part_number="ABC", quantity=1)


class TestERPPartResult:
    def test_valid_construction(self) -> None:
        part = ERPPartResult(
            part_number="RES-0402-10K-1PCT",
            description="10K Resistor",
            unit_price=Decimal("0.01"),
            available_qty=5000,
            lead_time_days=7,
            manufacturer="Yageo",
        )
        assert part.part_number == "RES-0402-10K-1PCT"
        assert part.unit_price == Decimal("0.01")

    def test_zero_price_valid(self) -> None:
        part = ERPPartResult(
            part_number="FREEBIE",
            description="Sample",
            unit_price=Decimal("0"),
            available_qty=100,
            lead_time_days=0,
            manufacturer="Generic",
        )
        assert part.unit_price == Decimal("0")

    def test_negative_price_raises(self) -> None:
        with pytest.raises(ValidationError):
            ERPPartResult(
                part_number="BAD",
                description="Bad part",
                unit_price=Decimal("-1"),
                available_qty=0,
                lead_time_days=0,
                manufacturer="Test",
            )

    def test_zero_stock_valid(self) -> None:
        part = ERPPartResult(
            part_number="OOS",
            description="Out of stock",
            unit_price=Decimal("1.00"),
            available_qty=0,
            lead_time_days=30,
            manufacturer="Test",
        )
        assert part.available_qty == 0


class TestQuoteLineItem:
    def test_found_requires_prices(self, sample_erp_part: ERPPartResult) -> None:
        with pytest.raises(ValidationError):
            QuoteLineItem(
                rfq_line=RFQLineItem(line_number=1, part_number="ABC", quantity=10),
                erp_result=sample_erp_part,
                status="found",
                unit_price=None,
            )

    def test_found_requires_extended_price(
        self, sample_erp_part: ERPPartResult
    ) -> None:
        with pytest.raises(ValidationError):
            QuoteLineItem(
                rfq_line=RFQLineItem(line_number=1, part_number="ABC", quantity=10),
                erp_result=sample_erp_part,
                status="found",
                unit_price=Decimal("0.01"),
                extended_price=None,
            )

    def test_not_found_no_prices_required(self) -> None:
        line = QuoteLineItem(
            rfq_line=RFQLineItem(line_number=1, part_number="ABC", quantity=10),
            erp_result=None,
            status="not_found",
        )
        assert line.unit_price is None
        assert line.extended_price is None

    def test_found_with_prices(self, sample_erp_part: ERPPartResult) -> None:
        line = QuoteLineItem(
            rfq_line=RFQLineItem(line_number=1, part_number="ABC", quantity=10),
            erp_result=sample_erp_part,
            status="found",
            unit_price=Decimal("0.015"),
            extended_price=Decimal("0.15"),
        )
        assert line.status == "found"
        assert line.unit_price == Decimal("0.015")

    def test_substituted_status_requires_prices(
        self, sample_erp_part: ERPPartResult
    ) -> None:
        with pytest.raises(ValidationError):
            QuoteLineItem(
                rfq_line=RFQLineItem(line_number=1, part_number="ABC", quantity=10),
                erp_result=sample_erp_part,
                status="substituted",
                unit_price=None,
            )

    def test_substituted_with_prices(self, sample_erp_part: ERPPartResult) -> None:
        line = QuoteLineItem(
            rfq_line=RFQLineItem(line_number=1, part_number="ALT-PART", quantity=5),
            erp_result=sample_erp_part,
            status="substituted",
            unit_price=Decimal("0.02"),
            extended_price=Decimal("0.10"),
            notes="Substituted ALT-PART with RES-0402-10K-1PCT",
        )
        assert line.status == "substituted"
        assert line.notes is not None

    def test_not_found_can_have_notes(self) -> None:
        line = QuoteLineItem(
            rfq_line=RFQLineItem(line_number=1, part_number="MISSING", quantity=1),
            erp_result=None,
            status="not_found",
            notes="Part not found in ERP",
        )
        assert line.notes == "Part not found in ERP"


class TestQuote:
    def _make_line(
        self, line_num: int, part: str, qty: int, price: str, ext_price: str
    ) -> QuoteLineItem:
        rfq = RFQLineItem(line_number=line_num, part_number=part, quantity=qty)
        erp = ERPPartResult(
            part_number=part,
            description="Test part",
            unit_price=Decimal(price),
            available_qty=100,
            lead_time_days=7,
            manufacturer="Test",
        )
        return QuoteLineItem(
            rfq_line=rfq,
            erp_result=erp,
            status="found",
            unit_price=Decimal(price),
            extended_price=Decimal(ext_price),
        )

    def test_total_matches_lines(self) -> None:
        lines = [
            self._make_line(1, "P1", 10, "1.00", "10.00"),
            self._make_line(2, "P2", 5, "2.00", "10.00"),
        ]
        quote = Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("20.00"))
        assert quote.total_price == Decimal("20.00")

    def test_total_mismatch_raises(self) -> None:
        lines = [self._make_line(1, "P1", 10, "1.00", "10.00")]
        with pytest.raises(ValidationError):
            Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("999.00"))

    def test_total_near_match_allowed(self) -> None:
        # Difference of 0.005 is within the 0.01 tolerance, so no error raised
        lines = [self._make_line(1, "P1", 1, "1.00", "10.005")]
        # 10.005 vs 10.00: diff = 0.005 <= 0.01 -> allowed
        quote = Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("10.00"))
        assert quote.total_price == Decimal("10.00")

    def test_total_with_not_found_line(self) -> None:
        found_line = self._make_line(1, "P1", 10, "1.00", "10.00")
        not_found_line = QuoteLineItem(
            rfq_line=RFQLineItem(line_number=2, part_number="MISSING", quantity=1),
            erp_result=None,
            status="not_found",
        )
        quote = Quote(
            rfq_source="test.xlsx",
            lines=[found_line, not_found_line],
            total_price=Decimal("10.00"),
        )
        assert quote.total_price == Decimal("10.00")

    def test_summary_counts(self) -> None:
        line1 = self._make_line(1, "P1", 10, "1.00", "10.00")
        line2 = QuoteLineItem(
            rfq_line=RFQLineItem(line_number=2, part_number="P2", quantity=1),
            erp_result=None,
            status="not_found",
        )
        quote = Quote(
            rfq_source="test.txt",
            lines=[line1, line2],
            total_price=Decimal("10.00"),
        )
        summary = quote.summary()
        assert "Found: 1" in summary
        assert "Not found: 1" in summary

    def test_summary_includes_total(self) -> None:
        lines = [self._make_line(1, "P1", 1, "5.00", "5.00")]
        quote = Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("5.00"))
        summary = quote.summary()
        assert "5.00" in summary
        assert "USD" in summary

    def test_summary_includes_quote_id(self) -> None:
        lines = [self._make_line(1, "P1", 1, "5.00", "5.00")]
        quote = Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("5.00"))
        summary = quote.summary()
        assert quote.id[:8] in summary

    def test_to_dict_serializable(self) -> None:
        lines = [self._make_line(1, "P1", 1, "5.00", "5.00")]
        quote = Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("5.00"))
        d = quote.to_dict()
        assert isinstance(d, dict)
        assert "id" in d
        assert d["currency"] == "USD"

    def test_to_dict_lines_present(self) -> None:
        lines = [
            self._make_line(1, "P1", 1, "5.00", "5.00"),
            self._make_line(2, "P2", 2, "2.50", "5.00"),
        ]
        quote = Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("10.00"))
        d = quote.to_dict()
        assert len(d["lines"]) == 2

    def test_to_dict_total_is_serialized(self) -> None:
        lines = [self._make_line(1, "P1", 1, "5.00", "5.00")]
        quote = Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("5.00"))
        d = quote.to_dict()
        # model_dump with mode="json" converts Decimal to string or float
        assert "total_price" in d

    def test_default_currency_usd(self) -> None:
        lines = [self._make_line(1, "P1", 1, "1.00", "1.00")]
        quote = Quote(rfq_source="test.xlsx", lines=lines, total_price=Decimal("1.00"))
        assert quote.currency == "USD"

    def test_unique_ids(self) -> None:
        lines = [self._make_line(1, "P1", 1, "1.00", "1.00")]
        q1 = Quote(rfq_source="a.xlsx", lines=lines, total_price=Decimal("1.00"))
        lines2 = [self._make_line(1, "P1", 1, "1.00", "1.00")]
        q2 = Quote(rfq_source="b.xlsx", lines=lines2, total_price=Decimal("1.00"))
        assert q1.id != q2.id

    def test_summary_with_substituted(self) -> None:
        rfq = RFQLineItem(line_number=1, part_number="ALT", quantity=1)
        erp = ERPPartResult(
            part_number="ALT",
            description="Alt part",
            unit_price=Decimal("1.00"),
            available_qty=10,
            lead_time_days=0,
            manufacturer="Test",
        )
        sub_line = QuoteLineItem(
            rfq_line=rfq,
            erp_result=erp,
            status="substituted",
            unit_price=Decimal("1.10"),
            extended_price=Decimal("1.10"),
        )
        quote = Quote(
            rfq_source="test.xlsx",
            lines=[sub_line],
            total_price=Decimal("1.10"),
        )
        summary = quote.summary()
        assert "Substituted: 1" in summary


class TestERPConfig:
    def test_masks_api_key_in_repr(self) -> None:
        cfg = ERPConfig(
            erp_type="epicor",
            base_url="https://epicor.example.com",
            api_key="super-secret-key-12345",
        )
        r = repr(cfg)
        assert "super-secret-key-12345" not in r
        assert "***" in r

    def test_masks_password_in_repr(self) -> None:
        cfg = ERPConfig(
            erp_type="sap",
            username="rfcuser",
            password="my-sap-password",
        )
        r = repr(cfg)
        assert "my-sap-password" not in r
        assert "***" in r

    def test_none_secrets_show_none(self) -> None:
        cfg = ERPConfig(erp_type="mock")
        r = repr(cfg)
        assert "None" in r

    def test_valid_erp_types(self) -> None:
        for etype in ("epicor", "sap", "oracle", "dynamics", "mock"):
            cfg = ERPConfig(erp_type=etype)  # type: ignore[arg-type]
            assert cfg.erp_type == etype

    def test_invalid_erp_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            ERPConfig(erp_type="unknown_erp")  # type: ignore[arg-type]

    def test_api_key_none_masked_as_none(self) -> None:
        cfg = ERPConfig(erp_type="epicor")
        r = repr(cfg)
        # When api_key is None, masked_key is None, so repr shows None
        assert "api_key=None" in r

    def test_password_none_masked_as_none(self) -> None:
        cfg = ERPConfig(erp_type="sap")
        r = repr(cfg)
        assert "password=None" in r

    def test_base_url_preserved_in_repr(self) -> None:
        cfg = ERPConfig(erp_type="epicor", base_url="https://my-erp.com")
        r = repr(cfg)
        assert "https://my-erp.com" in r

    def test_username_preserved_in_repr(self) -> None:
        cfg = ERPConfig(erp_type="sap", username="myuser")
        r = repr(cfg)
        assert "myuser" in r
