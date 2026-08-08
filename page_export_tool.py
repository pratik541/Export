"""Export Tool page: upload a Packing List (.xls/.xlsx) + Jobsheet (.csv)
for one shipment, generate and download the Fantasy File. All parsing/
building logic lives in export_tool/; this module is presentation only,
following the pattern of page_working_sheet.py."""
import streamlit as st

from export_tool import fantasy_file, jobsheet, packing_list


def render():
    st.session_state.setdefault("export_tool_rows", None)
    st.session_state.setdefault("export_tool_warnings", [])
    st.session_state.setdefault("export_tool_batch", "")

    st.title(":material/inventory_2: Export Tool")
    st.caption(
        "Upload the Packing List and Jobsheet for one shipment to generate "
        "its Fantasy File."
    )

    pl_col, js_col = st.columns(2)
    packing_list_file = pl_col.file_uploader(
        "Packing List (.xls/.xlsx)", type=["xls", "xlsx"], key="export_tool_pl_upload",
    )
    jobsheet_file = js_col.file_uploader(
        "Jobsheet (.csv)", type=["csv"], key="export_tool_js_upload",
    )

    generate_clicked = st.button(
        ":material/bolt: Generate Fantasy File", type="primary",
        key="export_tool_generate",
        disabled=not (packing_list_file and jobsheet_file),
    )

    if generate_clicked:
        st.session_state.export_tool_rows = None
        st.session_state.export_tool_warnings = []
        items = None
        try:
            items, warnings = packing_list.parse_packing_list(packing_list_file.getvalue())
            jobsheet_index = jobsheet.parse_jobsheet(jobsheet_file.getvalue())
        except packing_list.PackingListParseError as exc:
            st.error(f"Could not parse the packing list: {exc}")
            items = None
        except Exception as exc:
            st.error(f"Could not read the uploaded files: {exc}")
            items = None

        if items is not None:
            rows, build_warnings = fantasy_file.build_rows(items, jobsheet_index)
            st.session_state.export_tool_warnings = warnings + build_warnings
            st.session_state.export_tool_rows = rows
            st.session_state.export_tool_batch = _extract_batch_code(packing_list_file.name)

    if st.session_state.export_tool_warnings:
        st.warning("\n".join(f"- {w}" for w in st.session_state.export_tool_warnings))

    if st.session_state.export_tool_rows:
        st.success(f"Generated {len(st.session_state.export_tool_rows)} rows.")
        excel_bytes = fantasy_file.write_xlsx(st.session_state.export_tool_rows)
        batch = st.session_state.export_tool_batch or "export"
        st.download_button(
            ":material/download: Download Fantasy File",
            data=excel_bytes,
            file_name=f"Fantasy File - {batch}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    elif not (packing_list_file and jobsheet_file):
        st.info("Upload both files to get started.")


def _extract_batch_code(filename: str) -> str:
    base = filename.rsplit(".", 1)[0].strip()
    parts = base.split()
    return parts[0] if parts else ""
