from streamlit.testing.v1 import AppTest


def test_working_sheet_page_renders_with_no_files_uploaded():
    at = AppTest.from_file("tests/harness_working_sheet.py", default_timeout=120)
    at.run()
    assert not at.exception
    all_info = " ".join(m.value for m in at.info) if at.get("info") else ""
    assert "Upload both files" in all_info


def test_working_sheet_page_shows_generate_button_disabled_with_no_uploads():
    at = AppTest.from_file("tests/harness_working_sheet.py", default_timeout=120)
    at.run()
    assert not at.exception
    button = at.button(key="working_sheet_generate")
    assert button.proto.disabled is True


def test_generate_button_builds_rows_and_shows_them_in_a_table(monkeypatch):
    import working_sheet.invoice as invoice_module
    import working_sheet.packing_list as packing_list_module

    monkeypatch.setattr(
        packing_list_module, "parse_packing_list",
        lambda b: [{
            "number": 1, "ritc": "12345678", "description": "DESC",
            "gross_wt": 50.0, "net_wt": 45.0, "stone_wt": 0.5,
            "fob_value": 600.0, "unit_price": 12.0, "standard_qty": 0.05,
        }],
    )
    monkeypatch.setattr(
        invoice_module, "parse_invoice",
        lambda b: {
            "invoice_no": "TST001/26-27", "state_code": "27",
            "district_code": "483", "fta_code": "NCPTI",
            "igst_status": "LUT", "rodtep": "NO", "categories": [],
        },
    )

    at = AppTest.from_file("tests/harness_working_sheet.py", default_timeout=120)
    at.run()
    at.file_uploader(key="working_sheet_pl_upload").upload(
        "pl.xlsx", b"fake-xlsx-bytes",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    at.file_uploader(key="working_sheet_inv_upload").upload(
        "invoice.pdf", b"fake-pdf-bytes", "application/pdf",
    )
    at.run()
    assert at.button(key="working_sheet_generate").proto.disabled is False

    at.button(key="working_sheet_generate").click().run()

    assert not at.exception
    assert st_session_state_has_row_with_description(at, "DESC")


def st_session_state_has_row_with_description(at, description):
    rows = at.session_state["working_sheet_rows"]
    return any(row["Item Description"] == description for row in rows)
