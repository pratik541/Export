from streamlit.testing.v1 import AppTest


def test_export_tool_page_renders_with_no_files_uploaded():
    at = AppTest.from_file("tests/harness_export_tool.py", default_timeout=120)
    at.run()
    assert not at.exception
    all_info = " ".join(m.value for m in at.info) if at.get("info") else ""
    assert "Upload both files" in all_info


def test_export_tool_page_shows_generate_button_disabled_with_no_uploads():
    at = AppTest.from_file("tests/harness_export_tool.py", default_timeout=120)
    at.run()
    assert not at.exception
    button = at.button(key="export_tool_generate")
    assert button.proto.disabled is True


def test_generate_button_builds_rows_and_shows_a_download_button(monkeypatch):
    import export_tool.jobsheet as jobsheet_module
    import export_tool.packing_list as packing_list_module

    monkeypatch.setattr(
        packing_list_module, "parse_packing_list",
        lambda b: ([{
            "sr": 1, "sn": "STYLE1", "cat": "RING", "kt": "18KT WG",
            "qty": 1, "gw": 5.0, "tmw": 4.5, "mv": 200.0, "making": 30.0,
            "cert": None, "stones": [],
        }], []),
    )
    monkeypatch.setattr(jobsheet_module, "parse_jobsheet", lambda b: ({}, []))

    at = AppTest.from_file("tests/harness_export_tool.py", default_timeout=120)
    at.run()
    at.file_uploader(key="export_tool_pl_upload").upload(
        "JNE001 CR Packing List.xlsx", b"fake-xlsx-bytes",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    at.file_uploader(key="export_tool_js_upload").upload(
        "jobsheet.csv", b"fake-csv-bytes", "text/csv",
    )
    at.run()
    assert at.button(key="export_tool_generate").proto.disabled is False

    at.button(key="export_tool_generate").click().run()

    assert not at.exception
    assert len(at.session_state["export_tool_rows"]) == 1
    assert at.session_state["export_tool_batch"] == "JNE001"


def test_packing_list_parse_failure_shows_a_friendly_error_not_a_raw_traceback(monkeypatch):
    import export_tool.jobsheet as jobsheet_module
    import export_tool.packing_list as packing_list_module

    monkeypatch.setattr(
        packing_list_module, "parse_packing_list",
        lambda b: (_ for _ in ()).throw(packing_list_module.PackingListParseError("bad file")),
    )
    monkeypatch.setattr(jobsheet_module, "parse_jobsheet", lambda b: ({}, []))

    at = AppTest.from_file("tests/harness_export_tool.py", default_timeout=120)
    at.run()
    at.file_uploader(key="export_tool_pl_upload").upload(
        "pl.xlsx", b"fake-xlsx-bytes",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    at.file_uploader(key="export_tool_js_upload").upload(
        "jobsheet.csv", b"fake-csv-bytes", "text/csv",
    )
    at.run()
    at.button(key="export_tool_generate").click().run()

    assert not at.exception
    all_errors = " ".join(e.value for e in at.error) if at.get("error") else ""
    assert "Could not parse the packing list" in all_errors
