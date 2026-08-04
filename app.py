import streamlit as st

import ocr
import ui_common
import page_manage
import page_scan
import page_working_sheet

st.set_page_config(page_title="IGI Tag Scanner", page_icon="💎", layout="wide")

if "ocr_reader_ready" not in st.session_state:
    with st.spinner("Loading OCR model (first run may take a few minutes to download)..."):
        ocr.get_reader()
    st.session_state.ocr_reader_ready = True

ui_common.init_state()

st.navigation([
    st.Page(page_manage.render, title="Manage", icon="🗂️", url_path="manage", default=True),
    st.Page(page_scan.render, title="Scan", icon="📷", url_path="scan"),
    st.Page(page_working_sheet.render, title="Working Sheet", icon="📊", url_path="working-sheet"),
]).run()
