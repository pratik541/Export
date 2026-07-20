# IGI Diamond Report Tag Scanner

A Streamlit app that batch-processes photos of IGI diamond grading report tags: it
decodes the barcode (authoritative IGI report number), OCRs the printed grading
fields (report type, shape, carat, color, clarity), lets you review/correct
results in an editable table, and exports them to an Excel file.

## Local setup

1. Install [Miniconda/Anaconda](https://docs.conda.io/en/latest/miniconda.html)
   if you don't already have `conda` available (this project targets Python
   3.11 — very new Python versions may lack prebuilt wheels for
   opencv-python-headless/pyzbar).
2. Create and activate the conda environment, then install dependencies:
   ```bash
   conda create -n igi-ocr python=3.11 -y
   source "$(conda info --base)/etc/profile.d/conda.sh" && conda activate igi-ocr   # Git Bash; on Windows cmd/PowerShell use `conda activate igi-ocr` directly
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
  rows flagged `⚠️ Review` before trusting the export — that flag means one of
  the tracked fields (report number, report type, shape, carat, color, clarity)
  is missing or didn't match its expected format, which usually indicates an
  OCR misread rather than a real value.
- QR codes on these tags ("Cert Link", "Video Link") are not used — they were
  frequently unreadable in practice, and the IGI report number is already
  covered by the barcode (or, if that fails, the printed "IGI CERT - ######"
  text), so the app doesn't track them.
- No database, login, or cross-device/cross-session persistence: capture and
  review/export must happen in one sitting in one browser session.
- Live phone-to-*separate*-desktop camera streaming is not supported — a phone
  can only participate as a camera device for the same session (see "Using a
  phone as the camera" above), not as a remote feed into someone else's session.
