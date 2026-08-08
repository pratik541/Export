"""Regression test: runs the real JNE016 sample packing list through
export_tool.packing_list.parse_packing_list and checks it parses cleanly
against the column headers configured in export_tool/config.py.

The sample file lives in Data/ and is intentionally NOT committed to git
(real shipment data). This test skips itself when it's absent, so the suite
still passes in a fresh clone or CI -- same pattern as
tests/test_working_sheet_real_sample.py."""
from pathlib import Path

import pytest

from export_tool import packing_list

DATA_DIR = Path(__file__).parent.parent / "Data"
PACKING_LIST_PATH = DATA_DIR / "JNE016 CR Packing List Export Report new.xlsx"

pytestmark = pytest.mark.skipif(
    not PACKING_LIST_PATH.exists(),
    reason="Real sample shipment file is local-only (not committed) -- skipped when absent.",
)


def test_real_packing_list_parses_with_no_missing_columns():
    items, warnings = packing_list.parse_packing_list(PACKING_LIST_PATH.read_bytes())

    assert warnings == []
    assert len(items) > 0
    assert all(item["sn"] for item in items)
    assert all(item["kt"] for item in items)


def test_real_packing_list_has_a_bracelet_item():
    # Confirms the real file exercises NO_SIDE_DIAMOND_CATEGORIES filtering
    # (applied downstream in fantasy_file.build_rows).
    items, _ = packing_list.parse_packing_list(PACKING_LIST_PATH.read_bytes())
    assert any((item["cat"] or "").upper() == "BRACELET" for item in items)
