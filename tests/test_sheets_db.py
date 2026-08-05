from unittest.mock import MagicMock

import sheets_db


def _fields(igi="809614206"):
    return {
        "igi_report_no": igi, "report_type": "CVD", "shape": "EMERALD",
        "carat": "3.01", "color": "E", "clarity": "VS1", "needs_review": False,
    }


def test_is_enabled_false_when_no_client(monkeypatch):
    monkeypatch.setattr(sheets_db, "get_client", lambda: None)
    assert sheets_db.is_enabled() is False


def test_save_scan_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(sheets_db, "get_client", lambda: None)
    assert sheets_db.save_scan(_fields(), "camera") is False


def test_save_scan_returns_false_without_igi_number(monkeypatch):
    spreadsheet = MagicMock()
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    fields = _fields(igi=None)
    assert sheets_db.save_scan(fields, "camera") is False
    spreadsheet.worksheet.assert_not_called()  # never even opened the worksheet


def test_save_scan_appends_new_row_when_key_not_found(monkeypatch):
    spreadsheet = MagicMock()
    worksheet = spreadsheet.worksheet.return_value
    worksheet.col_values.return_value = ["igi_report_no", "111111111"]  # header + one other row
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)

    assert sheets_db.save_scan(_fields(), "camera") is True

    spreadsheet.worksheet.assert_called_once_with(sheets_db.TAG_TAB)
    worksheet.append_row.assert_called_once()
    row = worksheet.append_row.call_args[0][0]
    assert row[0] == "809614206"    # igi_report_no
    assert row[1] == "CVD"          # report_type
    assert row[2] == "EMERALD"      # shape
    assert row[3] == "3.01"         # carat
    assert row[4] == "E"            # color
    assert row[5] == "VS1"          # clarity
    assert row[6] is False          # needs_review
    assert row[7] == "camera"       # source
    worksheet.update.assert_not_called()


def test_save_scan_updates_existing_row_in_place_when_key_found(monkeypatch):
    spreadsheet = MagicMock()
    worksheet = spreadsheet.worksheet.return_value
    worksheet.col_values.return_value = ["igi_report_no", "111111111", "809614206", "222222222"]
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)

    assert sheets_db.save_scan(_fields(), "camera") is True

    worksheet.append_row.assert_not_called()
    worksheet.update.assert_called_once()
    args, kwargs = worksheet.update.call_args
    assert kwargs.get("range_name") == "A3"   # header=row1, "111111111"=row2, match=row3
    assert args[0][0][0] == "809614206"


def test_save_scan_returns_false_on_client_error(monkeypatch):
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value.col_values.side_effect = RuntimeError("network")
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    assert sheets_db.save_scan(_fields(), "camera") is False


def test_fetch_all_returns_rows_newest_first(monkeypatch):
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value.get_all_records.return_value = [
        {"igi_report_no": "1", "scanned_at": "2026-01-01T00:00:00+00:00"},
        {"igi_report_no": "2", "scanned_at": "2026-02-01T00:00:00+00:00"},
    ]
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    rows = sheets_db.fetch_all()
    assert [r["igi_report_no"] for r in rows] == ["2", "1"]


def test_fetch_all_returns_empty_on_error(monkeypatch):
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value.get_all_records.side_effect = RuntimeError("x")
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    assert sheets_db.fetch_all() == []


def test_fetch_all_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(sheets_db, "get_client", lambda: None)
    assert sheets_db.fetch_all() == []


def test_delete_one_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(sheets_db, "get_client", lambda: None)
    assert sheets_db.delete_one("809614206") is False


def test_delete_one_deletes_matching_row_and_returns_true(monkeypatch):
    spreadsheet = MagicMock()
    worksheet = spreadsheet.worksheet.return_value
    worksheet.col_values.return_value = ["igi_report_no", "111111111", "809614206"]
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    assert sheets_db.delete_one("809614206") is True
    worksheet.delete_rows.assert_called_once_with(3)


def test_delete_one_returns_true_when_no_matching_row(monkeypatch):
    spreadsheet = MagicMock()
    worksheet = spreadsheet.worksheet.return_value
    worksheet.col_values.return_value = ["igi_report_no", "111111111"]
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    assert sheets_db.delete_one("nonexistent") is True
    worksheet.delete_rows.assert_not_called()


def test_delete_one_returns_false_on_client_error(monkeypatch):
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value.col_values.side_effect = RuntimeError("x")
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    assert sheets_db.delete_one("809614206") is False


def test_delete_all_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(sheets_db, "get_client", lambda: None)
    assert sheets_db.delete_all() is False


def test_delete_all_resizes_to_header_row_and_returns_true(monkeypatch):
    spreadsheet = MagicMock()
    worksheet = spreadsheet.worksheet.return_value
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    assert sheets_db.delete_all() is True
    worksheet.resize.assert_called_once_with(rows=1)


def test_delete_all_returns_false_on_client_error(monkeypatch):
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value.resize.side_effect = RuntimeError("x")
    monkeypatch.setattr(sheets_db, "get_client", lambda: spreadsheet)
    assert sheets_db.delete_all() is False
