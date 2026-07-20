# IGI Diamond Report Tag OCR Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-session Streamlit app that batch-processes photos of IGI diamond grading report tags (upload or live camera capture), extracts the report number (barcode-first) plus diamond-grading fields via OpenCV+Tesseract OCR, lets the user review/correct results in an editable table, and exports them to a timestamped `.xlsx` file.

**Architecture:** Small, single-responsibility modules (`parsing`, `imaging`, `quality`, `ocr`, `decoding`, `excel_export`) are composed by one orchestration function (`pipeline.process_image`) that is fully unit-testable without Streamlit. `app.py` is thin UI glue: it collects images from `st.file_uploader` and `st.camera_input`, calls `pipeline.process_image` per image, and renders the running batch in `st.data_editor` with an Excel download button.

**Tech Stack:** Python 3.11 (see Global Constraints), Streamlit, OpenCV (`opencv-python-headless`), pytesseract, pyzbar, pandas, openpyxl, Pillow, pytest.

## Global Constraints

- Reference spec: `docs/superpowers/specs/2026-07-20-igi-tag-ocr-scanner-design.md` — read it if any task here seems ambiguous.
- **Use Python 3.11 for this project, not the machine's default Python 3.14.** This machine's default `python`/`py` resolves to 3.14.3, which is too new to trust for prebuilt `opencv-python-headless`/`pyzbar` wheels. A Python 3.11.15 interpreter is already installed at `C:\Users\HP\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe` (POSIX path in Git Bash: `/c/Users/HP/AppData/Roaming/uv/python/cpython-3.11.15-windows-x86_64-none/python.exe`). All tasks create/use a `.venv` built from that interpreter.
- All shell commands in this plan are written for Git Bash (the `Bash` tool), using `source .venv/Scripts/activate` to activate on Windows.
- No hardcoded Windows tesseract path anywhere in application code — `ocr.py` only reads it from the `TESSERACT_CMD` environment variable, and only if set.
- `requirements.txt` must contain exactly: `streamlit`, `pytesseract`, `opencv-python-headless`, `pyzbar`, `pandas`, `openpyxl`, `Pillow` (no extras — Streamlit Community Cloud installs from this file verbatim).
- Tesseract itself is **not installed on this dev machine**. Tests must not require the real `tesseract` binary or real barcode images — mock `pytesseract`/`pyzbar` calls at their module boundary in unit tests. A manual end-to-end check with the real binary is a separate, final task.
- No database, auth, or cross-session persistence. No live phone-to-separate-desktop streaming.

---

### Task 1: Project scaffolding (venv, dependency manifests, test config)

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `packages.txt`
- Create: `pytest.ini`
- Create: `.gitignore`

**Interfaces:**
- Produces: a `.venv` (Python 3.11.15) that every later task's `pip install` and `pytest` commands run inside.

- [ ] **Step 1: Create the virtual environment**

Run:
```bash
cd "/d/IGI_OCR" && "/c/Users/HP/AppData/Roaming/uv/python/cpython-3.11.15-windows-x86_64-none/python.exe" -m venv .venv
```
Expected: a `.venv/` directory is created with no error output.

- [ ] **Step 2: Verify activation and interpreter version**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && python --version
```
Expected: `Python 3.11.15`

- [ ] **Step 3: Write `requirements.txt`**

```
streamlit
pytesseract
opencv-python-headless
pyzbar
pandas
openpyxl
Pillow
```

- [ ] **Step 4: Write `requirements-dev.txt`**

```
-r requirements.txt
pytest
```

- [ ] **Step 5: Write `packages.txt`**

```
tesseract-ocr
libzbar0
```

- [ ] **Step 6: Install dependencies into the venv**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pip install -r requirements-dev.txt
```
Expected: exits 0; ends with something like `Successfully installed ... streamlit-... pytesseract-... opencv-python-headless-... pyzbar-... pandas-... openpyxl-... Pillow-... pytest-...`

- [ ] **Step 7: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 8: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.xlsx
```

- [ ] **Step 9: Verify pytest runs (no tests yet, should report 0 collected)**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest
```
Expected: `no tests ran` (exit code may be 5 — that's fine, there are no test files yet).

- [ ] **Step 10: Commit**

```bash
cd "/d/IGI_OCR" && git add requirements.txt requirements-dev.txt packages.txt pytest.ini .gitignore && git commit -m "chore: project scaffolding (venv deps, pytest config)"
```

---

### Task 2: `parsing.py` — regex/whitelist field parsing and validation

**Files:**
- Create: `parsing.py`
- Test: `tests/test_parsing.py`

**Interfaces:**
- Produces:
  - `parsing.CRITICAL_FIELDS: tuple[str, ...]`
  - `parsing.parse_fields(raw_text: str) -> dict` — keys: `lot_ref_no`, `igi_report_no`, `report_type`, `shape`, `carat`, `color`, `clarity`, `cut`, `polish`, `symmetry`, `fluorescence` (each `str | None`)
  - `parsing.validate_fields(fields: dict, barcode_value: str | None) -> dict` — returns a copy of `fields` with `igi_report_no` overridden by `barcode_value` when given, plus a `needs_review: bool` key.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_parsing.py`:
```python
import parsing


SAMPLE_RAW_TEXT = """C141619
IGI CERT - 809614206
REPORT
CVD
3.01
E VS1
EMERALD
Cut-VG Pol-EX
Sym-EX Fl-N
"""


def test_parse_fields_extracts_all_fields_from_sample_tag():
    fields = parsing.parse_fields(SAMPLE_RAW_TEXT)
    assert fields["lot_ref_no"] == "C141619"
    assert fields["igi_report_no"] == "809614206"
    assert fields["report_type"] == "CVD"
    assert fields["shape"] == "EMERALD"
    assert fields["carat"] == "3.01"
    assert fields["color"] == "E"
    assert fields["clarity"] == "VS1"
    assert fields["cut"] == "VG"
    assert fields["polish"] == "EX"
    assert fields["symmetry"] == "EX"
    assert fields["fluorescence"] == "N"


def test_parse_fields_accepts_svm_as_misread_of_sym_label():
    # IGI tags often OCR "Sym" as "Svm" due to font/glare (seen on the real sample tag).
    fields = parsing.parse_fields("Svm-EX")
    assert fields["symmetry"] == "EX"


def test_parse_fields_returns_none_for_missing_fields():
    fields = parsing.parse_fields("garbage unrelated text\nwith no matches")
    assert fields["igi_report_no"] is None
    assert fields["carat"] is None
    assert fields["shape"] is None


def test_validate_fields_prefers_barcode_value_over_ocr_value():
    fields = {
        "lot_ref_no": "C141619", "igi_report_no": "809614206", "report_type": "CVD",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
        "cut": "VG", "polish": "EX", "symmetry": "EX", "fluorescence": "N",
    }
    result = parsing.validate_fields(fields, barcode_value="999999999")
    assert result["igi_report_no"] == "999999999"
    assert result["needs_review"] is False


def test_validate_fields_falls_back_to_ocr_value_when_no_barcode():
    fields = {
        "lot_ref_no": "C141619", "igi_report_no": "809614206", "report_type": "CVD",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
        "cut": "VG", "polish": "EX", "symmetry": "EX", "fluorescence": "N",
    }
    result = parsing.validate_fields(fields, barcode_value=None)
    assert result["igi_report_no"] == "809614206"


def test_validate_fields_flags_needs_review_when_critical_field_missing():
    fields = {
        "lot_ref_no": None, "igi_report_no": None, "report_type": None,
        "shape": None, "carat": None, "color": None, "clarity": None,
        "cut": None, "polish": None, "symmetry": None, "fluorescence": None,
    }
    result = parsing.validate_fields(fields, barcode_value=None)
    assert result["needs_review"] is True


def test_validate_fields_flags_needs_review_on_invalid_grade_code():
    # "FX" is not a valid IGI grade code (real codes are EX/VG/G/F/P) — this is the
    # exact OCR misread ("EX" -> "FX") observed on the real sample tag.
    fields = {
        "lot_ref_no": "C141619", "igi_report_no": "809614206", "report_type": "CVD",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
        "cut": "VG", "polish": "FX", "symmetry": "FX", "fluorescence": "N",
    }
    result = parsing.validate_fields(fields, barcode_value="809614206")
    assert result["needs_review"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_parsing.py -v
```
Expected: `ModuleNotFoundError: No module named 'parsing'` (or collection error) — `parsing.py` doesn't exist yet.

- [ ] **Step 3: Write `parsing.py`**

```python
import re

SHAPE_WHITELIST = {
    "ROUND", "EMERALD", "OVAL", "PEAR", "CUSHION", "PRINCESS",
    "RADIANT", "HEART", "MARQUISE", "ASSCHER",
}
CLARITY_WHITELIST = {
    "FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "SI3", "I1", "I2", "I3",
}
GRADE_WHITELIST = {"EX", "VG", "G", "F", "P"}
FLUORESCENCE_WHITELIST = {"N", "F", "M", "S", "VS"}
REPORT_TYPE_WHITELIST = {"CVD", "NATURAL", "TREATED"}

CRITICAL_FIELDS = ("igi_report_no", "shape", "carat", "color", "clarity")

_CARAT_RE = re.compile(r"^\d+\.\d{2}$")
_COLOR_CLARITY_RE = re.compile(
    r"^([D-Z])\s+(FL|IF|VVS1|VVS2|VS1|VS2|SI1|SI2|SI3|I1|I2|I3)$"
)
_IGI_CERT_RE = re.compile(r"IGI\s*CERT\s*-?\s*(\d{8,10})", re.IGNORECASE)
_LOT_REF_RE = re.compile(r"^[A-Z]\d{5,7}$")
_REPORT_TYPE_RE = re.compile(r"REPORT\s+(CVD|NATURAL|TREATED)", re.IGNORECASE)
_GRADE_LABEL_RE = re.compile(
    r"\b(Cut|Pol|Sym|Svm|Sim|Fl)\s*[-:]\s*([A-Za-z]{1,3})\b", re.IGNORECASE
)
_GRADE_LABEL_MAP = {
    "CUT": "cut", "POL": "polish", "SYM": "symmetry", "SVM": "symmetry",
    "SIM": "symmetry", "FL": "fluorescence",
}

_FIELD_KEYS = (
    "lot_ref_no", "igi_report_no", "report_type", "shape", "carat",
    "color", "clarity", "cut", "polish", "symmetry", "fluorescence",
)


def parse_fields(raw_text: str) -> dict:
    """Parse raw OCR text from an IGI tag into structured fields via per-line and
    whole-text regex/keyword matching. Missing fields are None."""
    fields = {key: None for key in _FIELD_KEYS}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()

        if fields["carat"] is None and _CARAT_RE.match(line):
            fields["carat"] = line
            continue

        cc_match = _COLOR_CLARITY_RE.match(upper)
        if fields["color"] is None and cc_match:
            fields["color"], fields["clarity"] = cc_match.group(1), cc_match.group(2)
            continue

        if fields["shape"] is None and upper in SHAPE_WHITELIST:
            fields["shape"] = upper
            continue

        if fields["lot_ref_no"] is None and _LOT_REF_RE.match(upper):
            fields["lot_ref_no"] = upper
            continue

    igi_match = _IGI_CERT_RE.search(raw_text)
    if igi_match:
        fields["igi_report_no"] = igi_match.group(1)

    report_match = _REPORT_TYPE_RE.search(raw_text.upper())
    if report_match:
        fields["report_type"] = report_match.group(1)

    for label, value in _GRADE_LABEL_RE.findall(raw_text):
        key = _GRADE_LABEL_MAP.get(label.upper())
        if key and fields[key] is None:
            fields[key] = value.upper()

    return fields


def _valid_igi(value):
    return bool(value) and bool(re.fullmatch(r"\d{8,10}", value))


def _valid_shape(value):
    return value in SHAPE_WHITELIST


def _valid_carat(value):
    return bool(value) and bool(_CARAT_RE.match(value))


def _valid_color(value):
    return bool(value) and bool(re.fullmatch(r"[D-Z]", value))


def _valid_clarity(value):
    return value in CLARITY_WHITELIST


def _valid_optional_grade(value):
    return value is None or value in GRADE_WHITELIST


def _valid_optional_fluorescence(value):
    return value is None or value in FLUORESCENCE_WHITELIST


def _valid_optional_report_type(value):
    return value is None or value in REPORT_TYPE_WHITELIST


def validate_fields(fields: dict, barcode_value: str | None) -> dict:
    """Return a copy of `fields` with `igi_report_no` overridden by a decoded
    barcode value (authoritative) when available, plus a computed `needs_review`
    flag: True if any critical field is missing/invalid, or if ANY field
    (critical or not) fails its expected format/whitelist check."""
    result = dict(fields)
    if barcode_value:
        result["igi_report_no"] = barcode_value

    checks = {
        "igi_report_no": _valid_igi(result.get("igi_report_no")),
        "shape": _valid_shape(result.get("shape")),
        "carat": _valid_carat(result.get("carat")),
        "color": _valid_color(result.get("color")),
        "clarity": _valid_clarity(result.get("clarity")),
        "cut": _valid_optional_grade(result.get("cut")),
        "polish": _valid_optional_grade(result.get("polish")),
        "symmetry": _valid_optional_grade(result.get("symmetry")),
        "fluorescence": _valid_optional_fluorescence(result.get("fluorescence")),
        "report_type": _valid_optional_report_type(result.get("report_type")),
    }

    critical_missing = any(not checks[field] for field in CRITICAL_FIELDS)
    any_invalid = any(not ok for ok in checks.values())
    result["needs_review"] = bool(critical_missing or any_invalid)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_parsing.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/d/IGI_OCR" && git add parsing.py tests/test_parsing.py && git commit -m "feat: add IGI tag field parsing and validation"
```

---

### Task 3: `imaging.py` — OpenCV preprocessing

**Files:**
- Create: `imaging.py`
- Test: `tests/test_imaging.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `imaging.preprocess(image: numpy.ndarray) -> numpy.ndarray` — takes a BGR or grayscale image, returns a single-channel binarized (0/255) `uint8` array of the same height/width.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_imaging.py`:
```python
import numpy as np

import imaging


def _synthetic_bgr_image(height=120, width=200, seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def test_preprocess_returns_single_channel_same_size():
    image = _synthetic_bgr_image()
    result = imaging.preprocess(image)
    assert result.shape == (120, 200)
    assert result.dtype == np.uint8


def test_preprocess_output_is_binary():
    image = _synthetic_bgr_image()
    result = imaging.preprocess(image)
    unique_values = set(np.unique(result).tolist())
    assert unique_values.issubset({0, 255})


def test_preprocess_handles_already_grayscale_input():
    rng = np.random.default_rng(1)
    gray_image = rng.integers(0, 256, size=(80, 150), dtype=np.uint8)
    result = imaging.preprocess(gray_image)
    assert result.shape == (80, 150)


def test_preprocess_handles_blank_white_image_without_crashing():
    blank = np.full((100, 100, 3), 255, dtype=np.uint8)
    result = imaging.preprocess(blank)
    assert result.shape == (100, 100)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_imaging.py -v
```
Expected: `ModuleNotFoundError: No module named 'imaging'`

- [ ] **Step 3: Write `imaging.py`**

```python
import cv2
import numpy as np


def preprocess(image: np.ndarray) -> np.ndarray:
    """Grayscale -> denoise -> adaptive threshold -> deskew. Returns a binarized
    (0/255) single-channel uint8 image the same size as the input."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    binarized = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15,
    )
    return _deskew(binarized)


def _deskew(binary_image: np.ndarray) -> np.ndarray:
    dark_pixel_coords = np.column_stack(np.where(binary_image < 255))
    if dark_pixel_coords.size == 0:
        return binary_image

    angle = cv2.minAreaRect(dark_pixel_coords.astype(np.float32))[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return binary_image

    height, width = binary_image.shape[:2]
    center = (width // 2, height // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        binary_image, rotation_matrix, (width, height),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_imaging.py -v
```
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/d/IGI_OCR" && git add imaging.py tests/test_imaging.py && git commit -m "feat: add OpenCV preprocessing (grayscale, denoise, threshold, deskew)"
```

---

### Task 4: `ocr.py` — Tesseract configuration and wrapper

**Files:**
- Create: `ocr.py`
- Test: `tests/test_ocr.py`

**Interfaces:**
- Produces:
  - `ocr.configure_tesseract() -> None` — sets `pytesseract.pytesseract.tesseract_cmd` only if the `TESSERACT_CMD` env var is set; no-op otherwise.
  - `ocr.run_ocr(image) -> str` — thin wrapper around `pytesseract.image_to_string`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ocr.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_ocr.py -v
```
Expected: `ModuleNotFoundError: No module named 'ocr'`

- [ ] **Step 3: Write `ocr.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_ocr.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/d/IGI_OCR" && git add ocr.py tests/test_ocr.py && git commit -m "feat: add tesseract configuration and OCR wrapper"
```

---

### Task 5: `quality.py` — capture quality gate (blur, exposure, text presence)

**Files:**
- Create: `quality.py`
- Test: `tests/test_quality.py`

**Interfaces:**
- Consumes: nothing directly (takes an `ocr_func: Callable[[np.ndarray], str]` as a parameter so callers inject `ocr.run_ocr` — keeps this module testable without tesseract installed).
- Produces: `quality.assess_quality(image: np.ndarray, ocr_func) -> tuple[bool, str | None]` — `(True, None)` if usable, else `(False, "<user-facing reason>")`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_quality.py`:
```python
import numpy as np

import quality


def _sharp_random_gray_bgr(height=100, width=100, seed=0):
    rng = np.random.default_rng(seed)
    gray = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    return np.stack([gray, gray, gray], axis=-1)


def _flat_color_bgr(value, height=100, width=100):
    return np.full((height, width, 3), value, dtype=np.uint8)


def _ok_ocr(_image):
    return "IGI CERT - 809614206 3.01 E VS1 EMERALD"


def _empty_ocr(_image):
    return "   "


def test_check_blur_flags_flat_image_as_blurry():
    flat_gray = np.full((100, 100), 128, dtype=np.uint8)
    is_sharp, _variance = quality.check_blur(flat_gray)
    assert is_sharp is False


def test_check_blur_accepts_sharp_random_image():
    rng = np.random.default_rng(0)
    noisy_gray = rng.integers(0, 256, size=(100, 100), dtype=np.uint8)
    is_sharp, _variance = quality.check_blur(noisy_gray)
    assert is_sharp is True


def test_check_exposure_flags_overexposed_image():
    bright = np.full((100, 100), 250, dtype=np.uint8)
    ok, reason = quality.check_exposure(bright)
    assert ok is False
    assert "glare" in reason or "overexposed" in reason


def test_check_exposure_flags_underexposed_image():
    dark = np.full((100, 100), 10, dtype=np.uint8)
    ok, reason = quality.check_exposure(dark)
    assert ok is False
    assert "dark" in reason


def test_check_exposure_accepts_mid_range_image():
    rng = np.random.default_rng(0)
    mid_gray = rng.integers(80, 180, size=(100, 100), dtype=np.uint8)
    ok, reason = quality.check_exposure(mid_gray)
    assert ok is True
    assert reason is None


def test_check_text_presence_accepts_when_ocr_finds_enough_text():
    ok, count = quality.check_text_presence(np.zeros((10, 10), dtype=np.uint8), _ok_ocr)
    assert ok is True
    assert count > 0


def test_check_text_presence_rejects_when_ocr_finds_almost_nothing():
    ok, count = quality.check_text_presence(np.zeros((10, 10), dtype=np.uint8), _empty_ocr)
    assert ok is False
    assert count == 0


def test_assess_quality_rejects_blurry_image():
    ok, reason = quality.assess_quality(_flat_color_bgr(128), _ok_ocr)
    assert ok is False
    assert "blurry" in reason


def test_assess_quality_rejects_overexposed_image():
    ok, reason = quality.assess_quality(_flat_color_bgr(250), _ok_ocr)
    assert ok is False
    assert "please retake" in reason


def test_assess_quality_rejects_when_no_text_found():
    ok, reason = quality.assess_quality(_sharp_random_gray_bgr(), _empty_ocr)
    assert ok is False
    assert "No readable text" in reason


def test_assess_quality_accepts_good_image():
    ok, reason = quality.assess_quality(_sharp_random_gray_bgr(), _ok_ocr)
    assert ok is True
    assert reason is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_quality.py -v
```
Expected: `ModuleNotFoundError: No module named 'quality'`

- [ ] **Step 3: Write `quality.py`**

```python
import cv2
import numpy as np

BLUR_VARIANCE_THRESHOLD = 100.0
DARK_PIXEL_RATIO_THRESHOLD = 0.6
BRIGHT_PIXEL_RATIO_THRESHOLD = 0.4
MIN_OCR_CHARS = 10


def check_blur(gray_image: np.ndarray) -> tuple[bool, float]:
    variance = cv2.Laplacian(gray_image, cv2.CV_64F).var()
    return variance >= BLUR_VARIANCE_THRESHOLD, variance


def check_exposure(gray_image: np.ndarray) -> tuple[bool, str | None]:
    total_pixels = gray_image.size
    dark_ratio = np.count_nonzero(gray_image < 40) / total_pixels
    bright_ratio = np.count_nonzero(gray_image > 235) / total_pixels
    if dark_ratio >= DARK_PIXEL_RATIO_THRESHOLD:
        return False, "too dark"
    if bright_ratio >= BRIGHT_PIXEL_RATIO_THRESHOLD:
        return False, "glare/overexposed"
    return True, None


def check_text_presence(image: np.ndarray, ocr_func) -> tuple[bool, int]:
    text = ocr_func(image)
    char_count = len("".join(text.split()))
    return char_count >= MIN_OCR_CHARS, char_count


def assess_quality(image: np.ndarray, ocr_func) -> tuple[bool, str | None]:
    """Run the capture quality gate. `ocr_func` is injected (pass ocr.run_ocr in
    production) so this module never needs a real tesseract install to be tested."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    is_sharp, _ = check_blur(gray)
    if not is_sharp:
        return False, "Image too blurry — please retake."

    exposure_ok, reason = check_exposure(gray)
    if not exposure_ok:
        return False, f"Image {reason} — please retake."

    text_ok, _ = check_text_presence(gray, ocr_func)
    if not text_ok:
        return False, "No readable text detected — please retake."

    return True, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_quality.py -v
```
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/d/IGI_OCR" && git add quality.py tests/test_quality.py && git commit -m "feat: add capture quality gate (blur, exposure, text-presence checks)"
```

---

### Task 6: `decoding.py` — barcode/QR decoding

**Files:**
- Create: `decoding.py`
- Test: `tests/test_decoding.py`

**Interfaces:**
- Produces: `decoding.decode_barcodes(*images, decode_func=zbar_decode) -> dict` — returns `{"barcode_value": str | None, "qr_values": list[str]}`. `barcode_value` is the first purely-numeric decoded value found across all provided image variants (deduped); everything else goes into `qr_values`, in first-seen order. `decode_func` is injectable for testing without real barcode images.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_decoding.py`:
```python
from types import SimpleNamespace

import decoding


def _symbol(data: str):
    return SimpleNamespace(data=data.encode("utf-8"))


def test_decode_barcodes_returns_none_and_empty_when_nothing_found():
    def fake_decode(_image):
        return []

    result = decoding.decode_barcodes("image1", decode_func=fake_decode)
    assert result == {"barcode_value": None, "qr_values": []}


def test_decode_barcodes_picks_up_numeric_barcode_value():
    def fake_decode(image):
        return [_symbol("809614206")] if image == "original" else []

    result = decoding.decode_barcodes("original", "preprocessed", decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"
    assert result["qr_values"] == []


def test_decode_barcodes_separates_non_numeric_qr_values():
    def fake_decode(image):
        if image == "original":
            return [_symbol("809614206"), _symbol("https://cert.igi.org/809614206")]
        return []

    result = decoding.decode_barcodes("original", "preprocessed", decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"
    assert result["qr_values"] == ["https://cert.igi.org/809614206"]


def test_decode_barcodes_dedupes_across_multiple_image_variants():
    def fake_decode(_image):
        return [_symbol("809614206")]

    result = decoding.decode_barcodes("original", "preprocessed", decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"


def test_decode_barcodes_skips_none_images():
    def fake_decode(image):
        return [_symbol("809614206")] if image == "original" else []

    result = decoding.decode_barcodes("original", None, decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_decoding.py -v
```
Expected: `ModuleNotFoundError: No module named 'decoding'`

- [ ] **Step 3: Write `decoding.py`**

```python
from pyzbar.pyzbar import decode as zbar_decode


def decode_barcodes(*images, decode_func=zbar_decode) -> dict:
    """Decode barcodes/QR codes from one or more image variants (e.g. the original
    and the preprocessed version — barcode decoding is sometimes better on
    non-thresholded images) and merge the results.

    Returns {"barcode_value": <first purely-numeric value or None>,
             "qr_values": [<every other decoded value, in first-seen order>]}."""
    numeric_values = []
    other_values = []
    seen = set()

    for image in images:
        if image is None:
            continue
        for symbol in decode_func(image):
            value = symbol.data.decode("utf-8", errors="ignore").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            if value.isdigit():
                numeric_values.append(value)
            else:
                other_values.append(value)

    return {
        "barcode_value": numeric_values[0] if numeric_values else None,
        "qr_values": other_values,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_decoding.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/d/IGI_OCR" && git add decoding.py tests/test_decoding.py && git commit -m "feat: add barcode/QR decoding wrapper"
```

---

### Task 7: `excel_export.py` — build downloadable `.xlsx` bytes

**Files:**
- Create: `excel_export.py`
- Test: `tests/test_excel_export.py`

**Interfaces:**
- Produces: `excel_export.build_excel_bytes(dataframe: pandas.DataFrame) -> bytes`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_excel_export.py`:
```python
from io import BytesIO

import pandas as pd

import excel_export


def test_build_excel_bytes_roundtrips_dataframe_contents():
    df = pd.DataFrame({
        "filename": ["tag1.jpg", "tag2.jpg"],
        "igi_report_no": ["809614206", "123456789"],
        "carat": ["3.01", "1.25"],
        "needs_review": [False, True],
    })

    excel_bytes = excel_export.build_excel_bytes(df)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    roundtripped = pd.read_excel(BytesIO(excel_bytes))
    assert list(roundtripped["filename"]) == ["tag1.jpg", "tag2.jpg"]
    assert list(roundtripped["igi_report_no"]) == [809614206, 123456789]
    assert list(roundtripped["needs_review"]) == [False, True]


def test_build_excel_bytes_handles_empty_dataframe():
    df = pd.DataFrame(columns=["filename", "igi_report_no"])
    excel_bytes = excel_export.build_excel_bytes(df)
    roundtripped = pd.read_excel(BytesIO(excel_bytes))
    assert list(roundtripped.columns) == ["filename", "igi_report_no"]
    assert len(roundtripped) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_excel_export.py -v
```
Expected: `ModuleNotFoundError: No module named 'excel_export'`

- [ ] **Step 3: Write `excel_export.py`**

```python
from io import BytesIO

import pandas as pd


def build_excel_bytes(dataframe: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="tag_scan_results")
    return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_excel_export.py -v
```
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/d/IGI_OCR" && git add excel_export.py tests/test_excel_export.py && git commit -m "feat: add Excel export helper"
```

---

### Task 8: `pipeline.py` — per-image orchestration

**Files:**
- Create: `pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes:
  - `imaging.preprocess(image: np.ndarray) -> np.ndarray` (Task 3)
  - `ocr.run_ocr(image) -> str` (Task 4)
  - `quality.assess_quality(image, ocr_func) -> tuple[bool, str | None]` (Task 5)
  - `decoding.decode_barcodes(*images, decode_func=...) -> dict` (Task 6)
  - `parsing.parse_fields(raw_text) -> dict`, `parsing.validate_fields(fields, barcode_value) -> dict` (Task 2)
- Produces: `pipeline.process_image(image_bytes: bytes, filename: str) -> dict`. On rejection/failure: `{"filename", "accepted": False, "reason": str}`. On success: `{"filename", "accepted": True, "cert_link_qr": str | None, "video_link_qr": str | None, "raw_ocr_text": str, ...all parsing.validate_fields output including needs_review}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline.py`:
```python
import cv2
import numpy as np

import pipeline


def _encode_png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def _synthetic_image_bytes():
    rng = np.random.default_rng(0)
    image = rng.integers(0, 256, size=(150, 250, 3), dtype=np.uint8)
    return _encode_png(image)


def test_process_image_returns_rejected_for_corrupt_bytes():
    result = pipeline.process_image(b"not an image", "bad.jpg")
    assert result["accepted"] is False
    assert result["filename"] == "bad.jpg"
    assert "could not read" in result["reason"].lower()


def test_process_image_returns_rejected_when_quality_gate_fails(monkeypatch):
    monkeypatch.setattr(
        pipeline.quality, "assess_quality", lambda image, ocr_func: (False, "Image too blurry — please retake.")
    )
    result = pipeline.process_image(_synthetic_image_bytes(), "blurry.jpg")
    assert result["accepted"] is False
    assert result["reason"] == "Image too blurry — please retake."


def test_process_image_builds_full_row_on_success(monkeypatch):
    monkeypatch.setattr(pipeline.quality, "assess_quality", lambda image, ocr_func: (True, None))
    monkeypatch.setattr(
        pipeline.ocr, "run_ocr",
        lambda image: "IGI CERT - 809614206\n3.01\nE VS1\nEMERALD\nCut-VG Pol-EX\nSym-EX Fl-N",
    )
    monkeypatch.setattr(
        pipeline.decoding, "decode_barcodes",
        lambda *images, **kwargs: {
            "barcode_value": "809614206",
            "qr_values": ["https://cert.igi.org/x", "https://video.igi.org/y"],
        },
    )

    result = pipeline.process_image(_synthetic_image_bytes(), "tag1.jpg")

    assert result["accepted"] is True
    assert result["filename"] == "tag1.jpg"
    assert result["igi_report_no"] == "809614206"
    assert result["carat"] == "3.01"
    assert result["color"] == "E"
    assert result["clarity"] == "VS1"
    assert result["shape"] == "EMERALD"
    assert result["cert_link_qr"] == "https://cert.igi.org/x"
    assert result["video_link_qr"] == "https://video.igi.org/y"
    assert result["needs_review"] is False
    assert "IGI CERT" in result["raw_ocr_text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_pipeline.py -v
```
Expected: `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 3: Write `pipeline.py`**

```python
import cv2
import numpy as np

import decoding
import imaging
import ocr
import parsing
import quality


def _decode_image_bytes(image_bytes: bytes):
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def process_image(image_bytes: bytes, filename: str) -> dict:
    """Run the full extraction pipeline on one image's raw bytes."""
    image = _decode_image_bytes(image_bytes)
    if image is None:
        return {
            "filename": filename,
            "accepted": False,
            "reason": "Could not read image file — it may be corrupt.",
        }

    quality_ok, quality_reason = quality.assess_quality(image, ocr.run_ocr)
    if not quality_ok:
        return {"filename": filename, "accepted": False, "reason": quality_reason}

    preprocessed = imaging.preprocess(image)
    decoded = decoding.decode_barcodes(image, preprocessed)
    raw_text = ocr.run_ocr(preprocessed)
    fields = parsing.parse_fields(raw_text)
    validated = parsing.validate_fields(fields, decoded["barcode_value"])

    qr_values = decoded["qr_values"]
    row = {
        "filename": filename,
        "accepted": True,
        "cert_link_qr": qr_values[0] if len(qr_values) > 0 else None,
        "video_link_qr": qr_values[1] if len(qr_values) > 1 else None,
        "raw_ocr_text": raw_text,
    }
    row.update(validated)
    return row
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && pytest tests/test_pipeline.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/d/IGI_OCR" && git add pipeline.py tests/test_pipeline.py && git commit -m "feat: add per-image pipeline orchestration"
```

---

### Task 9: `app.py` — Streamlit UI

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `ocr.configure_tesseract()` (Task 4), `pipeline.process_image(image_bytes, filename) -> dict` (Task 8), `excel_export.build_excel_bytes(dataframe) -> bytes` (Task 7).

- [ ] **Step 1: Write `app.py`**

```python
import hashlib
from datetime import datetime

import pandas as pd
import streamlit as st

import excel_export
import ocr
import pipeline

st.set_page_config(page_title="IGI Tag Scanner", layout="wide")
ocr.configure_tesseract()

st.session_state.setdefault("rows", [])
st.session_state.setdefault("processed_keys", set())
st.session_state.setdefault("camera_shot_count", 0)

st.title("IGI Diamond Report Tag Scanner")
st.caption(
    "Upload tag photos or use the camera below. On desktop, the camera widget "
    "works with any camera the browser can see — including a phone connected as "
    "a webcam via Windows 11's Phone Link (see README)."
)

uploaded_files = st.file_uploader(
    "Upload tag photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True,
)
camera_photo = st.camera_input("Or take a photo")

candidates = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        candidates.append((uploaded_file.name, uploaded_file.getvalue()))
if camera_photo is not None:
    data = camera_photo.getvalue()
    if hashlib.md5(data).hexdigest() not in st.session_state.processed_keys:
        st.session_state.camera_shot_count += 1
        candidates.append((f"camera_capture_{st.session_state.camera_shot_count}.jpg", data))

new_items = []
for name, data in candidates:
    key = f"{name}:{hashlib.md5(data).hexdigest()}"
    if key not in st.session_state.processed_keys:
        new_items.append((key, name, data))

if new_items:
    progress = st.progress(0.0, text="Processing tag images...")
    for i, (key, name, data) in enumerate(new_items):
        try:
            result = pipeline.process_image(data, name)
        except Exception as exc:  # noqa: BLE001 - one bad file must never kill the batch
            result = {"filename": name, "accepted": False, "reason": f"Processing error: {exc}"}
        st.session_state.processed_keys.add(key)
        if not result["accepted"]:
            st.warning(f"{name}: {result['reason']}")
        else:
            st.session_state.rows.append(result)
        progress.progress((i + 1) / len(new_items), text=f"Processed {i + 1}/{len(new_items)}")
    progress.empty()

if st.session_state.rows:
    results_df = pd.DataFrame(st.session_state.rows).drop(columns=["accepted"], errors="ignore")
    results_df.insert(
        0, "review", results_df["needs_review"].map(lambda flagged: "⚠️ Review" if flagged else "✅ OK")
    )
    edited_df = st.data_editor(results_df, num_rows="dynamic", use_container_width=True)

    excel_bytes = excel_export.build_excel_bytes(edited_df)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        "Download results as Excel",
        data=excel_bytes,
        file_name=f"tag_scan_results_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Upload or capture tag photos to get started.")
```

- [ ] **Step 2: Install a real tesseract locally so the app can be run manually (one-time, not part of automated tests)**

This machine does not have tesseract installed. Before running the app locally end-to-end:
- Windows: install from https://github.com/UB-Mannheim/tesseract/wiki, then either add it to PATH or set `TESSERACT_CMD` to the installed `tesseract.exe` path (e.g. `export TESSERACT_CMD="/c/Program Files/Tesseract-OCR/tesseract.exe"` before launching).
- This step has no pass/fail check here — it's a prerequisite for Step 3, not something `pytest` verifies (per Global Constraints, tests never require the real binary).

- [ ] **Step 3: Manually smoke-test the app**

Run:
```bash
cd "/d/IGI_OCR" && source .venv/Scripts/activate && streamlit run app.py
```
Expected: app opens in a browser tab. Manually verify:
- Uploading a real IGI tag photo (or the sample tag) produces a row in the table.
- A deliberately blurry/dark photo gets rejected with an inline warning and does not appear in the table.
- The camera widget opens and a captured photo is added to the batch without duplicating on rerun.
- Editing a cell in the table and clicking "Download results as Excel" produces a valid, timestamped `.xlsx` file that opens correctly and reflects the edit.

Stop the app with Ctrl+C when done.

- [ ] **Step 4: Commit**

```bash
cd "/d/IGI_OCR" && git add app.py && git commit -m "feat: add Streamlit UI wiring upload/camera capture to the pipeline and Excel export"
```

---

### Task 10: `README.md`

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# IGI Diamond Report Tag Scanner

A Streamlit app that batch-processes photos of IGI diamond grading report tags: it
decodes the barcode (authoritative IGI report number), OCRs the printed grading
fields (carat, color, clarity, shape, cut/polish/symmetry, fluorescence, report
type), lets you review/correct results in an editable table, and exports them to
an Excel file.

## Local setup

1. Install Python 3.11 (this project targets 3.11 — very new Python versions may
   lack prebuilt wheels for opencv-python-headless/pyzbar).
2. Create and activate a virtual environment, then install dependencies:
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate   # Windows Git Bash; use .venv/bin/activate on Mac/Linux
   pip install -r requirements-dev.txt
   ```
3. Install the Tesseract OCR binary (required by `pytesseract`):
   - **Windows**: install from https://github.com/UB-Mannheim/tesseract/wiki. If it's
     not on your PATH, set an environment variable before launching the app:
     `export TESSERACT_CMD="/c/Program Files/Tesseract-OCR/tesseract.exe"`
   - **macOS**: `brew install tesseract`
   - **Linux (Debian/Ubuntu)**: `sudo apt-get install tesseract-ocr`
4. Install the zbar shared library (required by `pyzbar`) if barcode decoding
   fails to import on your platform — on Windows the `pyzbar` wheel bundles the
   required DLLs, so this is usually only needed on Linux
   (`sudo apt-get install libzbar0`).
5. Run the tests: `pytest`
6. Run the app: `streamlit run app.py`

## Using a phone as the camera (optional)

`st.camera_input()` uses whatever camera the browser can see — it doesn't have to
be a built-in or USB webcam. On Windows 11, pair your phone once via **Settings >
Bluetooth & devices > Phone Link**, enable its camera feature, and your phone's
camera becomes available as a regular webcam device that the app's camera widget
can select. No app configuration is needed for this.

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Create a new app on https://share.streamlit.io pointing at `app.py`.
3. Streamlit Cloud installs `requirements.txt` (Python deps) and `packages.txt`
   (system packages: `tesseract-ocr`, `libzbar0`) automatically — no manual
   server setup needed, and no `TESSERACT_CMD` override is required there since
   `tesseract` is already on `PATH` after the `packages.txt` install.

## Known limitations

- OCR accuracy depends on photo lighting, focus, and tag condition. Always review
  rows flagged `⚠️ Review` before trusting the export — that flag means either a
  critical field (report number, shape, carat, color, clarity) is missing, or
  some field's value didn't match its expected format (e.g. an invalid grade
  code), which usually indicates an OCR misread rather than a real value.
- QR codes on these tags ("Cert Link", "Video Link") are frequently unreadable in
  practice; the app decodes them best-effort but never depends on them — the IGI
  report number always comes from the barcode (or, if that fails, the printed
  "IGI CERT - ######" text).
- No database, login, or cross-device/cross-session persistence: capture and
  review/export must happen in one sitting in one browser session.
- Live phone-to-*separate*-desktop camera streaming is not supported — a phone
  can only participate as a camera device for the same session (see "Using a
  phone as the camera" above), not as a remote feed into someone else's session.
```

- [ ] **Step 2: Commit**

```bash
cd "/d/IGI_OCR" && git add README.md && git commit -m "docs: add README with setup, deployment, and limitations"
```

---

## Self-Review Notes

- **Spec coverage:** Data model/validation → Task 2. Capture (upload + camera, phone-as-webcam via README) → Tasks 9–10. Quality gate → Task 5. Pipeline (preprocessing, barcode-first with OCR fallback, OCR, parsing, validation) → Tasks 3, 4, 6, 8. UI/export → Task 9. Error handling → Task 8 (`process_image` returns a rejected dict for undecodable images) plus Task 9's `app.py` loop, which wraps each `pipeline.process_image` call in `try/except` so one bad file shows a warning and the rest of the batch still processes (an earlier draft of this plan left that `try/except` out — fixed during self-review). Testing → regex/whitelist test block folded into Task 2's tests (no separate "test block" needed — real pytest tests are stronger than comments). Deployment → Task 1 (`requirements.txt`/`packages.txt`) and Task 10 (README deploy steps).
- **Field list caveat:** Task 2's field set matches the spec's section 1 as currently written. If the user's team requests field changes after reviewing the spec, only Task 2 (and the corresponding parts of Tasks 8–9's row shape) need to change — every other task is independent of the exact field names.
- **Type consistency:** `parsing.parse_fields`/`validate_fields` field keys are used identically in Task 2 (definition), Task 8 (`pipeline.process_image`, via `fields.update`/`validated`), and Task 9 (`app.py`, via the resulting DataFrame columns) — verified consistent across tasks.
