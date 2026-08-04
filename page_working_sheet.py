"""Working Sheet page: upload a Packing List (.xlsx) + Export Invoice
(.pdf) for one shipment, review the computed rows, download the generated
Working Sheet .xlsx. All parsing/building logic lives in working_sheet/;
this module is presentation only, following the pattern of page_manage.py
and page_scan.py."""
from datetime import datetime

import pandas as pd
import streamlit as st

import excel_export
from working_sheet import builder, invoice as invoice_parser, packing_list


def render():
    st.session_state.setdefault("working_sheet_rows", None)
    st.session_state.setdefault("working_sheet_warnings", [])

    st.title(":material/receipt_long: Working Sheet generator")
    st.caption(
        "Upload the Packing List and Export Invoice for one shipment to "
        "generate its Working Sheet."
    )

    pl_col, inv_col = st.columns(2)
    packing_list_file = pl_col.file_uploader(
        "Packing List (.xlsx)", type=["xlsx"], key="working_sheet_pl_upload",
    )
    invoice_file = inv_col.file_uploader(
        "Export Invoice (.pdf)", type=["pdf"], key="working_sheet_inv_upload",
    )

    generate_clicked = st.button(
        ":material/bolt: Generate Working Sheet", type="primary",
        key="working_sheet_generate",
        disabled=not (packing_list_file and invoice_file),
    )

    if generate_clicked:
        st.session_state.working_sheet_rows = None
        st.session_state.working_sheet_warnings = []
        try:
            categories = packing_list.parse_packing_list(packing_list_file.getvalue())
            invoice_data = invoice_parser.parse_invoice(invoice_file.getvalue())
        except packing_list.PackingListParseError as exc:
            st.error(f"Could not parse the packing list: {exc}")
            categories = None
        except Exception as exc:
            st.error(f"Could not read the uploaded files: {exc}")
            categories = None

        if categories is not None:
            rows = builder.build_rows(categories, invoice_data)
            if not rows:
                st.error("No category blocks found — is this the right Packing List?")
            else:
                st.session_state.working_sheet_warnings = builder.cross_validate(categories, invoice_data)
                st.session_state.working_sheet_rows = rows

    if st.session_state.working_sheet_warnings:
        st.warning("\n".join(f"- {w}" for w in st.session_state.working_sheet_warnings))

    if st.session_state.working_sheet_rows:
        with st.container(border=True):
            st.subheader(":material/table_view: Working Sheet rows")
            df = pd.DataFrame(
                st.session_state.working_sheet_rows, columns=builder.WORKING_SHEET_COLUMNS,
            )
            edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")

            excel_bytes = excel_export.build_working_sheet_bytes(edited_df)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                ":material/download: Download Working Sheet",
                data=excel_bytes,
                file_name=f"working_sheet_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    elif not (packing_list_file and invoice_file):
        st.info("Upload both files to get started.")
