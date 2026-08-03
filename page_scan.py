"""Mobile Scan page: rear one-tap camera -> auto-OCR -> auto-save -> a compact
result card that fits on a phone screen without scrolling to verify the reading.
Falls back to a basic camera if the rear-camera component is unavailable."""
import streamlit as st

import db
import ui_common

try:
    from rear_camera import rear_camera_input
    _HAS_REAR_CAM = True
except Exception:  # noqa: BLE001 - component missing/broken -> basic-camera fallback
    rear_camera_input = None
    _HAS_REAR_CAM = False


def _capture_widget(card_type: str):
    """Show the camera and return captured image bytes, or None. Prefers the
    vendored rear-camera component (rear camera + built-in green guide box);
    falls back to st.camera_input (with the same guide-box overlay) if the
    component is unavailable or the user toggles it. The try/except also makes
    this safe under AppTest, which has no browser for the custom component."""
    use_basic = st.toggle(
        "Use basic camera", value=not _HAS_REAR_CAM,
        help="Switch this on if the rear camera doesn't work on your phone.",
    )
    key = f"cam_{st.session_state.camera_gen}"
    if _HAS_REAR_CAM and not use_basic:
        try:
            if card_type == "jewelry":
                return rear_camera_input(key=f"rear_{key}", box_width_pct=92,
                                         box_aspect=1.5, box_center_y_pct=45)
            return rear_camera_input(key=f"rear_{key}")  # bytes or None
        except Exception:  # noqa: BLE001
            st.warning("Rear camera unavailable here — turn on 'Use basic camera'.")
            return None
    # Fallback: native camera with the same green guide box as Manage.
    st.markdown(ui_common.guide_box_css(card_type), unsafe_allow_html=True)
    with st.container(key="camera_guide"):
        shot = st.camera_input("Point at the tag and shoot", key=f"basic_{key}",
                               label_visibility="collapsed")
    st.caption("Fit the whole tag inside the box · hold steady · avoid glare")
    return shot.getvalue() if shot is not None else None


def _render_result_card(item):
    labels = ui_common.JEWELRY_FIELD_LABELS if item.get("card_type") == "jewelry" else ui_common.FIELD_LABELS
    st.markdown(f"### {ui_common.item_status(item)}")
    st.image(item["cropped_bytes"], width="stretch")
    r = item.get("ocr_result")
    if r and r.get("accepted"):
        for field, label in labels:
            st.markdown(f"**{label}:** {r.get(field) or '—'}")
    if db.is_enabled():
        saved = item.get("saved_ok")
        if saved is True:
            st.caption("☁ saved to database")
        elif saved is False:
            st.caption("⚠ save failed — kept locally")
    if r and r.get("raw_ocr_text"):
        with st.expander("🔧 Raw OCR text (debug)"):
            st.code(r["raw_ocr_text"])


def _render_fix(item):
    """Editable fields for a review/failed read. Saving writes the corrected
    values back onto the item's ocr_result and re-runs autosave."""
    labels = ui_common.JEWELRY_FIELD_LABELS if item.get("card_type") == "jewelry" else ui_common.FIELD_LABELS
    r = item.get("ocr_result") or {}
    with st.expander("✏️ Fix this reading"):
        new_vals = {
            field: st.text_input(label, value=r.get(field) or "",
                                 key=f"fix_{item['id']}_{field}")
            for field, label in labels
        }
        if st.button("Save correction", type="primary", key=f"savefix_{item['id']}"):
            updated = dict(r)
            updated.update(new_vals)
            updated["accepted"] = True
            updated["needs_review"] = False
            item["ocr_result"] = updated
            ui_common.autosave(item)
            st.toast("Correction saved", icon=":material/check_circle:")
            st.rerun()


def render():
    st.header(":material/photo_camera: Scan a tag")

    card_type_choice = st.radio("Card type", ["Diamond tag", "Jewelry card"],
                                horizontal=True, key="scan_card_type")
    card_type = "jewelry" if card_type_choice == "Jewelry card" else "diamond"
    st.session_state.card_type = card_type

    data = _capture_widget(card_type)
    if data is not None:
        item = ui_common.add_image(data, f"scan_{st.session_state.next_id}.png",
                                   "camera", force_guide_box=True, card_type=card_type)
        if item is not None:
            with st.spinner("Reading tag..."):
                ui_common.run_ocr(item)
            ui_common.autosave(item)
            st.session_state.camera_gen += 1  # reset camera for the next tag
            st.rerun()

    items = st.session_state.gallery_items
    if not items:
        st.info("Snap a tag — its reading shows here.")
        return

    latest = items[-1]
    _render_result_card(latest)

    r = latest.get("ocr_result")
    if r is None or not r.get("accepted") or r.get("needs_review"):
        _render_fix(latest)

    if st.button(":material/photo_camera: Scan next", type="primary", key="scan_next"):
        st.session_state.camera_gen += 1
        st.rerun()

    st.caption("Open **Manage** (top-left menu) for the full table, export, and saved records.")
