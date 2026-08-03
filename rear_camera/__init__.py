"""In-repo rear-camera custom component with a green alignment guide box.

Vendored (and adapted) from streamlit-back-camera-input so we control the
frontend: it shows the phone's REAR camera, captures on a single tap at the
camera's native resolution, and overlays a green guide box. The box geometry in
frontend/style.css MUST match imaging.GUIDE_BOX_* so what the user frames equals
what capture.center_box_crop crops. Static files only — no build step."""
import base64
from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components

_frontend_dir = (Path(__file__).parent / "frontend").absolute()
_component_func = components.declare_component("rear_camera", path=str(_frontend_dir))


def _decode_data_url(data_url: Optional[str]) -> Optional[bytes]:
    """Decode a 'data:image/png;base64,...' URL to raw PNG bytes; None if falsy
    or malformed (no comma separator)."""
    if not data_url:
        return None
    parts = data_url.split(",", 1)
    if len(parts) != 2:
        return None
    return base64.b64decode(parts[1])


def rear_camera_input(height: int = 460, key: Optional[str] = None,
                      box_width_pct: float = 78, box_aspect: float = 2.0,
                      box_center_y_pct: float = 42) -> Optional[bytes]:
    """Show the rear camera with a green guide box; return the tapped capture as
    PNG bytes (native resolution), or None if nothing captured yet. box_width_pct,
    box_aspect, and box_center_y_pct control the guide box geometry (defaults are
    the diamond box) and are forwarded to the frontend for #guidebox."""
    value = _component_func(height=height, key=key, default=None,
                            box_width_pct=box_width_pct, box_aspect=box_aspect,
                            box_center_y_pct=box_center_y_pct)
    return _decode_data_url(value)
