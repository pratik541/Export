from unittest.mock import MagicMock

import db


def _fields(igi="809614206"):
    return {
        "igi_report_no": igi, "report_type": "CVD", "shape": "EMERALD",
        "carat": "3.01", "color": "E", "clarity": "VS1", "needs_review": False,
    }


def test_is_enabled_false_when_no_client(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.is_enabled() is False


def test_save_scan_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.save_scan(_fields(), "camera") is False


def test_save_scan_returns_false_without_igi_number(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, "get_client", lambda: client)
    fields = _fields(igi=None)
    assert db.save_scan(fields, "camera") is False
    client.table.assert_not_called()  # never even hit the DB


def test_save_scan_upserts_expected_payload_and_returns_true(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, "get_client", lambda: client)

    assert db.save_scan(_fields(), "camera") is True

    client.table.assert_called_once_with(db.TABLE)
    table = client.table.return_value
    args, kwargs = table.upsert.call_args
    payload = args[0]
    assert payload["igi_report_no"] == "809614206"
    assert payload["report_type"] == "CVD"
    assert payload["shape"] == "EMERALD"
    assert payload["carat"] == "3.01"
    assert payload["color"] == "E"
    assert payload["clarity"] == "VS1"
    assert payload["needs_review"] is False
    assert payload["source"] == "camera"
    assert kwargs.get("on_conflict") == "igi_report_no"
    table.upsert.return_value.execute.assert_called_once()


def test_save_scan_returns_false_on_client_error(monkeypatch):
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("network")
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.save_scan(_fields(), "camera") is False


def test_fetch_all_returns_rows_newest_first(monkeypatch):
    client = MagicMock()
    result = MagicMock()
    result.data = [{"igi_report_no": "1"}, {"igi_report_no": "2"}]
    client.table.return_value.select.return_value.order.return_value.execute.return_value = result
    monkeypatch.setattr(db, "get_client", lambda: client)

    rows = db.fetch_all()
    assert rows == [{"igi_report_no": "1"}, {"igi_report_no": "2"}]
    client.table.return_value.select.return_value.order.assert_called_once_with("scanned_at", desc=True)


def test_fetch_all_returns_empty_on_error(monkeypatch):
    client = MagicMock()
    client.table.return_value.select.return_value.order.return_value.execute.side_effect = RuntimeError("x")
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.fetch_all() == []


def test_fetch_all_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.fetch_all() == []


def test_delete_one_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.delete_one("809614206") is False


def test_delete_one_issues_eq_delete_and_returns_true(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.delete_one("809614206") is True
    client.table.assert_called_once_with(db.TABLE)
    table = client.table.return_value
    table.delete.return_value.eq.assert_called_once_with("igi_report_no", "809614206")
    table.delete.return_value.eq.return_value.execute.assert_called_once()


def test_delete_one_returns_false_on_client_error(monkeypatch):
    client = MagicMock()
    client.table.return_value.delete.return_value.eq.return_value.execute.side_effect = RuntimeError("x")
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.delete_one("809614206") is False


def test_delete_all_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.delete_all() is False


def test_delete_all_issues_matchall_delete_and_returns_true(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.delete_all() is True
    client.table.assert_called_once_with(db.TABLE)
    table = client.table.return_value
    # match-all filter on the PK so PostgREST accepts the delete
    table.delete.return_value.neq.assert_called_once_with("igi_report_no", "__none__")
    table.delete.return_value.neq.return_value.execute.assert_called_once()


def test_delete_all_returns_false_on_client_error(monkeypatch):
    client = MagicMock()
    client.table.return_value.delete.return_value.neq.return_value.execute.side_effect = RuntimeError("x")
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.delete_all() is False


def _jewelry_fields(report_no="J12345"):
    return {
        "report_no": report_no, "shape_cut": "ROUND", "est_weight": "1.20",
        "color": "F", "clarity": "VVS2", "style_no": "ST-001", "needs_review": False,
    }


def test_save_jewelry_scan_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.save_jewelry_scan(_jewelry_fields(), "camera") is False


def test_save_jewelry_scan_returns_false_without_report_no(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, "get_client", lambda: client)
    fields = _jewelry_fields(report_no=None)
    assert db.save_jewelry_scan(fields, "camera") is False
    client.table.assert_not_called()  # never even hit the DB


def test_save_jewelry_scan_upserts_expected_payload_and_returns_true(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, "get_client", lambda: client)

    assert db.save_jewelry_scan(_jewelry_fields(), "camera") is True

    client.table.assert_called_once_with(db.JEWELRY_TABLE)
    table = client.table.return_value
    args, kwargs = table.upsert.call_args
    payload = args[0]
    assert payload["report_no"] == "J12345"
    assert payload["shape_cut"] == "ROUND"
    assert payload["est_weight"] == "1.20"
    assert payload["color"] == "F"
    assert payload["clarity"] == "VVS2"
    assert payload["style_no"] == "ST-001"
    assert payload["needs_review"] is False
    assert payload["source"] == "camera"
    assert kwargs.get("on_conflict") == "report_no"
    table.upsert.return_value.execute.assert_called_once()


def test_save_jewelry_scan_returns_false_on_client_error(monkeypatch):
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("network")
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.save_jewelry_scan(_jewelry_fields(), "camera") is False


def test_fetch_all_jewelry_returns_rows_newest_first(monkeypatch):
    client = MagicMock()
    result = MagicMock()
    result.data = [{"report_no": "1"}, {"report_no": "2"}]
    client.table.return_value.select.return_value.order.return_value.execute.return_value = result
    monkeypatch.setattr(db, "get_client", lambda: client)

    rows = db.fetch_all_jewelry()
    assert rows == [{"report_no": "1"}, {"report_no": "2"}]
    client.table.return_value.select.return_value.order.assert_called_once_with("scanned_at", desc=True)


def test_fetch_all_jewelry_returns_empty_on_error(monkeypatch):
    client = MagicMock()
    client.table.return_value.select.return_value.order.return_value.execute.side_effect = RuntimeError("x")
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.fetch_all_jewelry() == []


def test_fetch_all_jewelry_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.fetch_all_jewelry() == []


def test_delete_one_jewelry_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.delete_one_jewelry("J12345") is False


def test_delete_one_jewelry_issues_eq_delete_and_returns_true(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.delete_one_jewelry("J12345") is True
    client.table.assert_called_once_with(db.JEWELRY_TABLE)
    table = client.table.return_value
    table.delete.return_value.eq.assert_called_once_with("report_no", "J12345")
    table.delete.return_value.eq.return_value.execute.assert_called_once()


def test_delete_one_jewelry_returns_false_on_client_error(monkeypatch):
    client = MagicMock()
    client.table.return_value.delete.return_value.eq.return_value.execute.side_effect = RuntimeError("x")
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.delete_one_jewelry("J12345") is False


def test_delete_all_jewelry_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)
    assert db.delete_all_jewelry() is False


def test_delete_all_jewelry_issues_matchall_delete_and_returns_true(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.delete_all_jewelry() is True
    client.table.assert_called_once_with(db.JEWELRY_TABLE)
    table = client.table.return_value
    # match-all filter on the PK so PostgREST accepts the delete
    table.delete.return_value.neq.assert_called_once_with("report_no", "__none__")
    table.delete.return_value.neq.return_value.execute.assert_called_once()


def test_delete_all_jewelry_returns_false_on_client_error(monkeypatch):
    client = MagicMock()
    client.table.return_value.delete.return_value.neq.return_value.execute.side_effect = RuntimeError("x")
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.delete_all_jewelry() is False
