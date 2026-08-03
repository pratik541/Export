"""Unit tests for the vendored rear-camera component's Python wrapper. The
browser side (getUserMedia, tap capture, the guide box) can't run headless, so
we test the data-URL decode that turns the component's return value into bytes."""
import base64
import inspect

import rear_camera


def test_rear_camera_input_box_params_default_to_diamond_box():
    sig = inspect.signature(rear_camera.rear_camera_input)
    assert sig.parameters["box_width_pct"].default == 78
    assert sig.parameters["box_aspect"].default == 2.0
    assert sig.parameters["box_center_y_pct"].default == 42


def test_decode_data_url_returns_png_bytes():
    raw = b"\x89PNG\r\n\x1a\n and some fake payload"
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode()
    assert rear_camera._decode_data_url(data_url) == raw


def test_decode_data_url_none_when_empty():
    assert rear_camera._decode_data_url(None) is None
    assert rear_camera._decode_data_url("") is None


def test_decode_data_url_none_when_no_comma():
    assert rear_camera._decode_data_url("garbage-no-comma") is None
