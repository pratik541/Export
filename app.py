import streamlit as st

import ocr
import ui_common
import page_manage

st.set_page_config(page_title="IGI Tag Scanner", page_icon="💎", layout="wide")

if "ocr_reader_ready" not in st.session_state:
    with st.spinner("Loading OCR model (first run may take a few minutes to download)..."):
        ocr.get_reader()
    st.session_state.ocr_reader_ready = True

ui_common.init_state()
page_manage.render()
