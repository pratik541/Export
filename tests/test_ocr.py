import pytesseract

import ocr


def test_configure_tesseract_sets_cmd_when_env_var_present(monkeypatch):
    monkeypatch.setenv("TESSERACT_CMD", r"C:\fake\tesseract.exe")
    pytesseract.pytesseract.tesseract_cmd = "tesseract"
    ocr.configure_tesseract()
    assert pytesseract.pytesseract.tesseract_cmd == r"C:\fake\tesseract.exe"


def test_configure_tesseract_is_noop_when_env_var_absent(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    pytesseract.pytesseract.tesseract_cmd = "tesseract"
    ocr.configure_tesseract()
    assert pytesseract.pytesseract.tesseract_cmd == "tesseract"


def test_run_ocr_delegates_to_pytesseract(monkeypatch):
    captured = {}

    def fake_image_to_string(image):
        captured["image"] = image
        return "  some ocr text  "

    monkeypatch.setattr(pytesseract, "image_to_string", fake_image_to_string)
    result = ocr.run_ocr("fake-image-object")
    assert result == "  some ocr text  "
    assert captured["image"] == "fake-image-object"
