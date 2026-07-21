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
3. Install the zbar shared library (required by `pyzbar`) if barcode decoding
   fails to import on your platform — on Windows the `pyzbar` wheel bundles the
   required DLLs, so this is usually only needed on Linux
   (`sudo apt-get install libzbar0`).
4. Run the tests: `pytest`
5. Run the app: `streamlit run app.py`. Model weights are bundled in `models/`
   (not downloaded at runtime — see "OCR model files" below), so this starts
   in a couple of seconds with no internet access needed.

## OCR model files

`models/PP-OCRv6_tiny_det/` and `models/PP-OCRv6_tiny_rec/` are PaddleOCR's
detection/recognition model weights, committed directly into this repo
(~6.5MB total) rather than downloaded at runtime. This is deliberate, not
just a convenience: PaddleX (PaddleOCR's backing library) defaults to
resolving/downloading models from a remote hub (HuggingFace, ModelScope,
AIStudio, or Baidu's BOS) on every fresh environment, and that failed outright
on Streamlit Community Cloud with `No model source is available for model
'PP-OCRv6_tiny_det'` — its sandboxed network couldn't reach any of those
hosts. Bundling the files and pointing `ocr.py` at them via `*_model_dir`
avoids that lookup entirely; this has been verified to work with the download
cache completely removed, not just assumed.

If you ever need to re-fetch these (e.g. to switch to a different PaddleOCR
model), delete `models/PP-OCRv6_tiny_det/` and `models/PP-OCRv6_tiny_rec/`,
remove the `*_model_dir` arguments in `ocr.py`'s `get_reader()`, and run the
app once with internet access — PaddleX will download to its own cache
(`~/.paddlex/official_models/`) that you can then copy back into `models/`.

## Using a phone as the camera (optional)

`st.camera_input()` uses whatever camera the browser can see — it doesn't have to
be a built-in or USB webcam. On Windows 11, pair your phone once via **Settings >
Bluetooth & devices > Phone Link**, enable its camera feature, and your phone's
camera becomes available as a regular webcam device that the app's camera widget
can select. No app configuration is needed for this.

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Create a new app on https://share.streamlit.io pointing at `app.py`.
3. **Set the Python version explicitly to 3.11** in the app's "Advanced
   settings" (Python version dropdown) before first deploying — do this
   whether creating the app or editing an existing one's settings. This
   matters because `paddlepaddle` only publishes wheels for Python 3.9–3.13,
   and Streamlit Community Cloud has been observed defaulting new apps to a
   newer version than that regardless of the platform's documented default,
   which fails the build with `Could not find a version that satisfies the
   requirement paddlepaddle (from versions: none)`. This is not something
   `runtime.txt` controls on Streamlit Community Cloud — the Python version
   is set via that "Advanced settings" dropdown only.
4. Streamlit Cloud installs `requirements.txt` (Python deps, including
   `paddlepaddle`/`paddleocr`) and `packages.txt` (system package: `libzbar0`)
   automatically — no manual server setup needed.
5. **Deployment risk still worth knowing about:** `paddlepaddle` is a full
   deep learning framework — installed, it and its dependencies run several
   hundred MB. That's a real risk of exceeding Streamlit Community Cloud's
   free-tier build size / memory limits. If the build itself fails or the app
   crashes/hangs after installing successfully, that's the next thing to
   suspect; the fallback is a paid tier, a different host with more headroom,
   or reverting to the lighter (but less accurate) Tesseract-based approach
   from an earlier point in this project's history.

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
