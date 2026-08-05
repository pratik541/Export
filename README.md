# IGI Diamond Report Tag Scanner

A Streamlit app that batch-processes photos of IGI diamond grading report tags: it
decodes the barcode (authoritative IGI report number), OCRs the printed grading
fields (report type, shape, carat, color, clarity), lets you review/correct
results in an editable table, and exports them to an Excel file.

It also scans a second IGI document type, the Laboratory Grown Diamond Jewelry
Report card — see "Two card types" below.

Capture and OCR are separate steps. Each uploaded or camera-captured photo is
auto-cropped to the label around its decoded barcode and dropped into a
thumbnail gallery — nothing is OCR'd automatically the instant a photo
arrives. From the gallery you can accept the auto-crop, drag a manual crop
box instead if it missed (via `streamlit-cropper`), and then run OCR either
per item or on the whole batch at once with "Run OCR on all". See "How it
works" below for the full flow.

## Two pages: Manage and Scan

The app has two pages, reachable from the navigation menu (top-left on
desktop, the hamburger icon on mobile). **Manage** opens by default.

- **Manage** — the full desktop workflow: upload and/or camera capture into
  a gallery, manual re-crop, per-item or batch OCR, the editable results
  table, Excel export, and (if Supabase is configured) the shared
  saved-records view with delete. This is the page "How it works" below
  describes.
- **Scan** — a mobile-first page for one tag at a time: the rear-camera
  preview shows a green alignment box, and tapping the on-screen Capture
  button takes a tag photo and always crops it to that box at the camera's
  native resolution — so every
  Scan capture is framed the same way and contains the whole tag, whether or
  not a barcode is visible. (Manage, described below, still crops to the
  barcode position first — see "How it works".) The tag is then OCR'd and,
  if Supabase is configured, auto-saved immediately — there's no separate
  "Run OCR" step. The result shows as a compact card sized to fit a phone
  screen without scrolling; if a field is missing or flagged for review, an
  inline "Fix this reading" expander lets you correct it and save on the
  spot. A "Use basic camera" toggle swaps in the standard
  `st.camera_input()` widget, with the same green box, if the rear-camera
  component doesn't work on your device.

The Scan page's rear camera is an in-repo vendored custom component at
`rear_camera/` (static HTML/JS/CSS, no build step) — it replaced the
`streamlit-back-camera-input` pip dependency used earlier, so there's now
one less third-party package to track (no `packages.txt` change either way).
It asks the browser directly for the rear-facing camera (`facingMode:
environment`), rather than requiring a webcam or a Phone Link pairing (see
"Using a phone as the camera" below, which is a separate, Manage-page
mechanism), and draws the green guide box directly on the video preview. The
box's geometry (width, aspect ratio, vertical position) is defined once in
`imaging.GUIDE_BOX_*` and mirrored in the component's
`rear_camera/frontend/style.css`, kept in sync by convention and guarded by
a test.

Automatically capturing the instant a tag is framed ("auto-click") is
planned as a v2 enhancement — Android-first, using the browser's
`BarcodeDetector` API, falling back to today's one-tap capture where that
API isn't available. It is **not** part of this release; Scan always
requires the explicit tap.

## Two card types: diamond tag and jewelry card

Both **Manage** and **Scan** start with a "Card type" radio — **Diamond tag**
(default) or **Jewelry card** — that governs the rest of that page's flow:
which fields get read, how the green guide box is shaped, and which store a
saved scan lands in.

- **Diamond tag** is everything described elsewhere in this README —
  barcode-anchored crop, `ocr/pipeline.py`, the six tracked fields, `tag_scans`.
- **Jewelry card** targets the IGI Laboratory Grown Diamond Jewelry Report —
  a printed card with labeled fields (Report No., Shape and Cut, Est. Weight,
  Color, Clarity, Style#) and no usable barcode. Its guide box is bigger and
  closer to the card's own proportions (`imaging.JEWELRY_GUIDE_BOX_WIDTH_FRAC`
  / `_ASPECT` / `_CENTER_Y_FRAC`, vs. the diamond tag's `GUIDE_BOX_*`) so all
  six labels fit inside the frame — both the crop (`imaging.guide_box_crop`)
  and the box drawn on the camera preview (the rear-camera component's
  `box_width_pct`/`box_aspect`/`box_center_y_pct`, or `ui_common.guide_box_css`
  for the `st.camera_input()` fallback) take a `card_type` argument and stay
  matched by construction, not just by convention. There's no barcode/QR
  step for jewelry cards at all — `ocr/pipeline_jewelry.process_image` runs
  the same quality gate and PaddleOCR engine as the diamond pipeline, then
  reads fields with `ocr/parsing_jewelry.py`, a **verbatim, label-anchored
  parser**: each field is whatever text OCR printed immediately after its
  label, taken exactly as-is — no normalization, no format/whitelist
  validation, no fuzzy correction of the VALUE. (Clarity's label position is
  the one exception located with `rapidfuzz` fuzzy matching when misread —
  that only decides where to start reading, never touches what's stored.)
  `needs_review` is set only when a field came back blank,
  never because a value looked "wrong". Accepted jewelry scans are saved to
  their own `jewelry_scans` table, separate from `tag_scans` — see "Central
  database" below.

## How it works

1. **Capture** — upload one or more files, and/or take a photo with
   `st.camera_input()`. Both feed the same gallery.
2. **Auto-crop** — each photo is decoded, its barcode located, and the image
   cropped to the label region anchored on that barcode position
   (`imaging.crop_to_label`, called from `capture.build_item`). If no usable
   barcode box is found (undetected or a degenerate zero-size box), a camera
   capture falls back to cropping the on-screen guide-box region instead
   (`imaging.center_box_crop`) — a centered rectangle matching what the
   camera preview outlines on screen, so what the user framed in the box is
   what gets cropped. The on-screen box is a CSS overlay (`app.py`) sized to
   the same width/aspect/vertical-center fractions as `center_box_crop`, so
   it's a visual aid the two are meant to agree with, not a pixel-exact
   guarantee — it's approximate, and never blocks the shutter button. Uploads
   have no such guide box to fall back to, so an upload with no usable
   barcode keeps the full, uncropped photo instead of failing. Each item
   records how it was cropped in a `crop_method` field (`"barcode"`,
   `"guide_box"`, `"manual"`, or `None` for the uncropped fallback).
3. **Gallery** — every captured photo appears as a thumbnail (the cropped
   version) with a status: not yet scanned, OK, needs review, or failed, plus
   a note if auto-crop couldn't find a barcode. A metrics row above the
   gallery (Total tags / OK / Needs review / Not scanned) gives an at-a-glance
   batch summary, and toasts confirm actions like adding a photo or finishing
   OCR. Each thumbnail also has a per-item Delete button, and a "Clear all"
   action (with a confirm step) empties the whole gallery.
4. **Manual re-crop (optional)** — click "Re-crop" on any thumbnail to drag a
   box over the original photo yourself, using `streamlit-cropper`. This
   replaces the auto-crop (setting `crop_method` to `"manual"`) and clears any
   existing OCR result for that item, so a stale result is never shown as
   current.
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
5. Run the app: `streamlit run app.py`. Model weights are bundled in
   `ocr/models/` (not downloaded at runtime — see "OCR model files" below),
   so this starts in a couple of seconds with no internet access needed.

## OCR model files

`ocr/models/PP-OCRv6_tiny_det/` and `ocr/models/PP-OCRv6_tiny_rec/` are
PaddleOCR's detection/recognition model weights, committed directly into this
repo (~6.5MB total) rather than downloaded at runtime. This is deliberate, not
just a convenience: PaddleX (PaddleOCR's backing library) defaults to
resolving/downloading models from a remote hub (HuggingFace, ModelScope,
AIStudio, or Baidu's BOS) on every fresh environment, and that failed outright
on Streamlit Community Cloud with `No model source is available for model
'PP-OCRv6_tiny_det'` — its sandboxed network couldn't reach any of those
hosts. Bundling the files and pointing `ocr/__init__.py` at them via
`*_model_dir` avoids that lookup entirely; this has been verified to work
with the download cache completely removed, not just assumed.

If you ever need to re-fetch these (e.g. to switch to a different PaddleOCR
model), delete `ocr/models/PP-OCRv6_tiny_det/` and
`ocr/models/PP-OCRv6_tiny_rec/`, remove the `*_model_dir` arguments in
`ocr/__init__.py`'s `get_reader()`, and run the app once with internet access
— PaddleX will download to its own cache (`~/.paddlex/official_models/`)
that you can then copy back into `ocr/models/`.

`requirements.txt` pins every dependency to an exact version deliberately,
not just as a style choice: PP-OCRv6 (the model family bundled in
`ocr/models/`) was only introduced in `paddleocr` 3.7.0. An earlier deploy
with unpinned
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

## Central database — Supabase (disconnected, kept for reference)

**This app no longer calls Supabase.** It was switched over to Google Sheets
(below) as its sole central store. This section, `db.py`, and its tests are
kept in the codebase, fully working and fully tested, in case of a future
revert — but nothing in `page_manage.py`, `page_scan.py`, or `ui_common.py`
imports or calls `db.py` anymore. If you're setting this app up fresh, skip
straight to the "Google Sheets" section below.

The rest of this section is preserved as-was, describing how it worked while
it was connected:

By default this app has no database: everything lives in the browser session,
as described above. You can optionally connect it to a shared
[Supabase](https://supabase.com) table so that every accepted scan (one with
a readable IGI report number) is automatically saved centrally, and a "Saved
records" section in the app can read that shared table back and export all of
it to Excel. **This is entirely optional** — without it configured, the app
runs exactly as before, with no database section shown and no behavior
change.

### 1. Create the table

In your Supabase project's SQL editor, run:

```sql
create table if not exists tag_scans (
    igi_report_no text primary key,
    report_type text,
    shape text,
    carat text,
    color text,
    clarity text,
    needs_review boolean,
    source text,
    scanned_at timestamptz not null default now()
);

alter table tag_scans enable row level security;

-- Internal tool with a shared table: allow the anon role to read and write.
create policy "anon read"  on tag_scans for select using (true);
create policy "anon write" on tag_scans for insert with check (true);
create policy "anon update" on tag_scans for update using (true) with check (true);
create policy "anon delete" on tag_scans for delete using (true);
```

**The delete policy is required, not optional**, if you want deletes to work:
without it, Supabase's row-level security silently blocks the delete — the
API call itself doesn't error, so the app has no way to tell "deleted" apart
from "no rows matched" from a normal response alone. For per-row deletes this
can pass unnoticed; for "Delete all" the app double-checks by re-fetching the
table afterward, and shows a warning ("Delete had no effect...") if any rows
are still there, since that's the strongest signal that the delete policy is
missing.

Jewelry-card scans (see "Two card types" above) are saved to a **separate**
table, `jewelry_scans`, keyed on `report_no` instead of `igi_report_no`. If
you want to scan jewelry cards with central storage enabled, also run:

```sql
create table if not exists jewelry_scans (
    report_no text primary key,
    shape_cut text,
    est_weight text,
    color text,
    clarity text,
    style_no text,
    needs_review boolean,
    source text,
    scanned_at timestamptz default now()
);
alter table jewelry_scans enable row level security;
create policy "anon select" on jewelry_scans for select using (true);
create policy "anon insert" on jewelry_scans for insert with check (true);
create policy "anon update" on jewelry_scans for update using (true);
create policy "anon delete" on jewelry_scans for delete using (true);
```

Both tables share the same `[supabase]` secrets (below) — there's nothing
extra to configure beyond creating this second table. Diamond-tag scanning
works exactly as before whether or not `jewelry_scans` exists; the app only
touches it when the "Jewelry card" card type is selected.

### 2. Configure secrets

- **Local setup**: copy `.streamlit/secrets.toml.example` to
  `.streamlit/secrets.toml` and fill in your project's URL and anon key
  (Supabase dashboard → Project Settings → API). `.streamlit/secrets.toml` is
  gitignored — never commit real credentials.
- **Streamlit Cloud**: paste the same `[supabase]` block into the app's
  Settings → Secrets.

### Behavior notes

- Each accepted scan auto-upserts into `tag_scans` keyed on
  `igi_report_no` — one row per stone, so re-scanning the same tag updates
  its existing row instead of duplicating it.
- Rows without a readable IGI report number are kept local-only in that
  session's results table; they are never saved to the shared table (there's
  no key to upsert on).
- The "Saved records" section reads the shared table directly (not just this
  session's captures) and offers an export-all-to-Excel button.
- Each saved record can be deleted individually, and the whole table can be
  cleared with a "Yes, delete all" / "No, cancel" confirmation. Both are
  **permanent, shared deletes** — they remove data from the Supabase table
  for every device reading it, not just the current session, and there is
  no undo.
- The delete RLS policy above is required for either delete to actually take
  effect — without it, the request succeeds at the API level but removes
  nothing. The app can't detect this for a single-row delete, but "Delete
  all" re-checks afterward and warns ("Delete had no effect...") if rows
  remain, which is the signal to add the delete policy in Supabase.
- The local **"Restart / new batch"** button (in the gallery section) only
  clears this device's in-progress capture batch from the browser session —
  it never touches the shared Supabase table. Use per-row/"Delete all" in
  "Saved records" to actually remove data from the database.
- If Supabase isn't configured (no secrets present), the database features
  are simply hidden and the app behaves exactly as it did before this
  feature existed.
- Jewelry-card scans get their own "Saved jewelry records" section (Manage
  page), reading `jewelry_scans` and offering the same export-all-to-Excel /
  per-row delete / Yes-No-confirmed "Delete all" as the diamond-tag "Saved
  records" section above — just against the separate table, upserted on
  `report_no` instead of `igi_report_no`.

## Central database — Google Sheets (optional, currently connected)

**This is the app's active central store.** Every accepted scan (one with a
readable key) is automatically saved to a Google Sheet, and the "Saved
records" / "Saved jewelry records" sections in the app read that same sheet
back and export it to Excel. **This is entirely optional** — without
`[gsheets]` secrets configured, the app runs exactly as before, with no
database section shown and no behavior change.

(This started as an independent write-side shadow copy alongside Supabase,
evaluated risk-free before cutting over — see the Supabase section above for
that history. The app has since been switched to use Sheets exclusively.)

### 1. Create the spreadsheet and a service account

1. Create a new Google Sheet. Add two tabs (rename the default "Sheet1" and
   add a second): `tag_scans` and `jewelry_scans`.
2. Add a header row to each tab, in this exact column order:
   - `tag_scans`: `igi_report_no, report_type, shape, carat, color, clarity, needs_review, source, scanned_at`
   - `jewelry_scans`: `report_no, shape_cut, est_weight, color, clarity, style_no, needs_review, source, scanned_at`
3. In the [Google Cloud Console](https://console.cloud.google.com/), create
   (or reuse) a project, enable the **Google Sheets API**, then create a
   **Service Account** and download its JSON key.
4. Share the spreadsheet (the "Share" button, same as sharing with a person)
   with the service account's email address (looks like
   `something@project-id.iam.gserviceaccount.com`, found in the JSON key)
   with **Editor** access.
5. Copy the spreadsheet ID from its URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`.

### 2. Configure secrets

- **Local setup**: add a `[gsheets]` block to `.streamlit/secrets.toml`:
  ```toml
  [gsheets]
  spreadsheet_id = "your-spreadsheet-id"
  service_account = '''
  {...paste the full contents of the downloaded JSON key here...}
  '''
  ```
- **Streamlit Cloud**: paste the same `[gsheets]` block into the app's
  Settings → Secrets.

Until this is configured, nothing changes: `sheets_db.is_enabled()` is
`False` and every Sheets call is a no-op, exactly like Supabase's own
optional-by-default behavior.

### Behavior notes

- Each accepted scan auto-upserts into the `tag_scans` (or `jewelry_scans`)
  tab, keyed on `igi_report_no` / `report_no` — found by looking up the
  existing row and updating it in place, or appending a new one if not
  found (Sheets has no native upsert the way Postgres does).
- Rows without a readable key are kept local-only in that session's results
  table; they are never saved to the sheet (there's no key to upsert on).
- The "Saved records" section reads the sheet directly (not just this
  session's captures) and offers an export-all-to-Excel button.
- Each saved record can be deleted individually, and the whole tab can be
  cleared with a "Yes, delete all" / "No, cancel" confirmation. Both are
  **permanent, shared deletes** — they remove data from the sheet for
  everyone reading it, not just the current session, and there is no undo.
- Failures here are currently silent (no logging) — if `is_enabled()` is
  unexpectedly `False` after configuring secrets, or a save/delete doesn't
  seem to be landing, double check: the spreadsheet ID is correct, the tab
  names are exactly `tag_scans`/`jewelry_scans` (case-sensitive), the header
  row matches the column order above exactly, and the sheet has been shared
  with the service account's `client_email` with Editor access.
- Google Sheets' free-tier API quota (100 requests/100 seconds/user) is
  generous for this app's scan volume but not unlimited; an occasional
  transient quota error during heavy "OCR all" batches surfaces the same way
  any other failure here does — silently, with the scan itself unaffected
  (only the save to the sheet is skipped).
- If Google Sheets isn't configured (no `[gsheets]` secrets present), the
  database features are simply hidden and the app behaves exactly as it did
  before this feature existed.

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
- No login/auth. Persistence is optional: without Supabase configured, capture
  and review/export happen in one sitting in one browser session; with the
  optional Supabase store enabled (see "Central database"), accepted scans are
  saved centrally and shared across devices.
- Live phone-to-*separate*-desktop camera streaming is not supported — a phone
  can only participate as a camera device for the same session (see "Using a
  phone as the camera" above), not as a remote feed into someone else's session.
