import os

import pytesseract


def configure_tesseract() -> None:
    """Point pytesseract at a specific tesseract binary only when TESSERACT_CMD is
    set (for local Windows dev where tesseract isn't on PATH). On Streamlit
    Community Cloud, tesseract-ocr from packages.txt is already on PATH, so this
    is a no-op there — never hardcode a path here."""
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def run_ocr(image) -> str:
    return pytesseract.image_to_string(image)
