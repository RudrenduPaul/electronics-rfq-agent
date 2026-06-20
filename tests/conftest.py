from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from electronics_rfq_agent.mcp.mock.backend import MockERP
from electronics_rfq_agent.models import ERPPartResult, RFQLineItem


@pytest.fixture
def mock_erp() -> MockERP:
    return MockERP()


@pytest.fixture
def sample_rfq_lines() -> list[RFQLineItem]:
    return [
        RFQLineItem(line_number=1, part_number="RES-0402-10K-1PCT", quantity=100),
        RFQLineItem(line_number=2, part_number="CAP-100NF-50V-X7R-0402", quantity=50),
        RFQLineItem(line_number=3, part_number="IC-LM358-SOIC8", quantity=10),
        RFQLineItem(line_number=4, part_number="XTAL-16MHZ-SMD", quantity=5),
        RFQLineItem(line_number=5, part_number="PART-DOES-NOT-EXIST-XYZ", quantity=1),
    ]


@pytest.fixture
def sample_erp_part() -> ERPPartResult:
    return ERPPartResult(
        part_number="RES-0402-10K-1PCT",
        description="10K Ohm 1% 0402 Resistor",
        unit_price=Decimal("0.01"),
        available_qty=5000,
        lead_time_days=7,
        manufacturer="Yageo",
    )


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
