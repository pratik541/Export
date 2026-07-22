# IGI Diamond Report Tag Scanner

A Streamlit app that batch-processes photos of IGI diamond grading report tags: it
decodes the barcode (authoritative IGI report number), OCRs the printed grading
fields (report type, shape, carat, color, clarity), lets you review/correct
results in an editable table, and exports them to an Excel file.

Capture and OCR are separate steps. Each uploaded or camera-captured photo is
auto-cropped to the label around its decoded barcode and dropped into a
thumbnail gallery — nothing is OCR'd automatically the instant a photo
arrives. From the gallery you can accept the auto-crop, drag a manual crop
box instead if it missed (via `streamlit-cropper`), and then run OCR either
per item or on the whole batch at once with "Run OCR on all". See "How it
works" below for the full flow.

## How it works

1. **Capture** — upload one or more files, and/or take a photo with
   `st.camera_input()`. Both feed the same gallery.
2. **Auto-crop** — each photo is decoded, its barcode located, and the image
   cropped to the label region anchored on that barcode position
   (`imaging.crop_to_label`, called from `capture.build_item`). If no usable
   barcode box is found (undetected or a degenerate zero-size box), the item
   falls back to the full, uncropped photo instead of failing.
3. **Gallery** — every captured photo appears as a thumbnail (the cropped
   version) with a status: not yet scanned, OK, needs review, or failed, plus
   a note if auto-crop couldn't find a barcode.
4. **Manual re-crop (optional)** — click "Re-crop" on any thumbnail to drag a
   box over the original photo yourself, using `streamlit-cropper`. This
   replaces the auto-crop and clears any existing OCR result for that item,
   so a stale result is never shown as current.
5. **OCR, on demand** — click "OCR" on an individual thumbnail, or "Run OCR
   on all" to process every item that hasn't been OCR'd yet. Only OCR'd,
   accepted items appear in the results table below the gallery.

Cropping tightly to the label also measurably improves OCR accuracy — see
`docs/PROJECT.md` for the numbers.

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

`requirements.txt` pins every dependency to an exact version deliberately,
not just as a style choice: PP-OCRv6 (the model family bundled in `models/`)
was only introduced in `paddleocr` 3.7.0. An earlier deploy with unpinned
versions installed correctly but resolved an older `paddlex` that had never
heard of `PP-OCRv6_tiny_det` (`ClassNotFoundException: 'PP-OCRv6_tiny_det' is
not registered on BasePredictor`), despite the exact same `pip install`
working fine locally. Exact pins keep what deploys identical to what's been
tested. If you deliberately want to move to a newer `paddleocr` release later
(e.g. for a newer/better model), re-verify locally first the same way this
was verified — a fresh, no-cache environment installing only from
`requirements.txt`, then real inference against `tests/fixtures/` — before
changing the pins.

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
4. Streamlit Cloud installs `requirements.txt` (Python deps) and `packages.txt`
   (system packages: `libzbar0` for barcode decoding, `libgl1` +
   `libglib2.0-0t64` for OpenCV — see next point for why) automatically — no
   manual server setup needed.
5. **`libgl1`/`libglib2.0-0t64` are required even though this project only
   specifies `opencv-python-headless`** (deliberately, to avoid exactly this).
   `paddlex`'s `ocr-core` extra (required by `paddleocr`) hard-pins
   `opencv-contrib-python` — the *non*-headless build, which needs graphics
   libraries a minimal container doesn't have — regardless of what this
   project's own `requirements.txt` says. There's no way to override that
   from here; `paddlex` requires that exact package by name. Without them the
   app fails at import time, first with `ImportError: libGL.so.1: cannot open
   shared object file` (fixed by `libgl1`), then `ImportError:
   libgthread-2.0.so.0: cannot open shared object file` (fixed by
   `libglib2.0-0t64`).

   Specifically **`libglib2.0-0t64`, not `libglib2.0-0`**: Streamlit
   Community Cloud's current base image runs Debian trixie, where this
   package was renamed with a `t64` suffix (part of Debian's 64-bit time_t
   migration) and now depends on `libffi8`. The old name `libglib2.0-0`
   still exists as a leftover bullseye-security package that depends on the
   unavailable `libffi7` instead, and requesting it by that name fails the
   *entire* `packages.txt` install (including `libzbar0` and `libgl1` along
   with it) with `Depends: libffi7 ... but it is not installable`.
6. **Deployment risk still worth knowing about:** `paddlepaddle` is a full
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
