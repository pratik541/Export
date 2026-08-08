"""AppTest harness: render the Export Tool page directly (no navigation
entry), so UI regression tests drive it independently of app.py's
st.navigation wiring."""
import ui_common
import page_export_tool

ui_common.init_state()
page_export_tool.render()
