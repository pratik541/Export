"""AppTest harness: render the Manage page directly (no navigation entry), so
UI regression tests drive it independently of app.py's st.navigation wiring."""
import ui_common
import page_manage

ui_common.init_state()
page_manage.render()
