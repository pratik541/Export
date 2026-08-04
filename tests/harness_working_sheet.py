"""AppTest harness: render the Working Sheet page directly (no navigation
entry), so UI regression tests drive it independently of app.py's
st.navigation wiring."""
import ui_common
import page_working_sheet

ui_common.init_state()
page_working_sheet.render()
