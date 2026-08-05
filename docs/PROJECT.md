# IGI Diamond Report Tag Scanner

## What this is

A Streamlit app for batch-digitizing IGI diamond grading report tags. A user
uploads photos (or captures them with a camera) of one or more tags; each
photo is auto-cropped to the label around its decoded barcode and placed in
a thumbnail gallery, where it can be manually re-cropped and then OCR'd —
per item or as a batch — to extract the report number, report type, shape,
carat, color, and clarity. Results are shown in an editable table and
exported to a timestamped Excel file.

Capture and OCR are deliberately separate steps: capture (upload/camera +
auto-crop) always happens immediately, but nothing is OCR'd until the user
asks for it (per-item "OCR" or "Run OCR on all"). This lets a user review
and fix a bad auto-crop *before* spending OCR time on it.

The tags themselves are a standardized IGI layout: a barcode, two QR codes
("Cert Link", "Video Link"), and printed text for the report number, report
type (e.g. `CVD`, `HPHT`, `NATURAL`), shape, carat, color, and clarity. Some
tags are lab-grown diamond reports; some are natural.

The app also scans a second IGI document type — the Laboratory Grown Diamond
Jewelry Report card — selected via a "Card type" radio (Diamond tag /
Jewelry card) present on both pages. That card has its own printed layout, no
usable barcode, and is read by a dedicated verbatim parser rather than the
regex/whitelist logic below; see "Jewelry cards" throughout this document for
where it diverges from the diamond-tag flow.

## Tracked fields

Only six fields are extracted and exported — nothing else:

| Field | Source | Notes |
|---|---|---|
| `igi_report_no` | Barcode (authoritative), falls back to the printed `IGI CERT - ######` text if the barcode doesn't decode | |
| `report_type` | Printed text following the `REPORT` label | e.g. `CVD`, `HPHT`, `NATURAL`, `TREATED` |
| `shape` | Printed text | e.g. `EMERALD`, `ROUND`, `OVAL`, `HEART`, `MARQUISE` |
| `carat` | Printed text | `\d+\.\d\d` |
| `color` | Printed text | single letter, `D`–`Z` |
| `clarity` | Printed text | e.g. `VS1`, `VVS2`, `FL` |

Every row also carries `raw_ocr_text` (the full OCR output, for manual
cross-checking) and `needs_review` (a computed flag — see below). QR codes are
decoded best-effort but not tracked in the output: they were frequently
unreadable on real photos, and the report number is already covered by the
barcode.

## Jewelry-card fields

The jewelry card (Card type = "Jewelry card") tracks six fields too, but read
**verbatim** — no regex/whitelist validation, no normalization:

| Field | Printed label | Notes |
|---|---|---|
| `report_no` | `Report No.` | No barcode on this card; this is the only source for the report number |
| `shape_cut` | `Shape and Cut` | e.g. `Oval Brilliant` |
| `est_weight` | `Est. Weight` | e.g. `0.56` |
| `color` | `Color` | whatever OCR reads after the label, verbatim |
| `clarity` | `Clarity` | e.g. `VS` |
| `style_no` | `Style#` | matched by its own `Style#` pattern anywhere in the OCR text, not the label-line scan the other five fields use |

`raw_ocr_text` is carried the same way as the diamond path. `needs_review` is
`True` if any of the six fields above is blank — never because a present
value looks malformed, since nothing about this card's values is validated
against a format or whitelist (see "Jewelry pipeline" below). QR codes are not
read for this card type at all (no barcode/QR decode step runs).

## Pipeline

Capture and OCR are two separate stages, connected by an auto-crop step —
not one continuous pipeline run the instant a photo arrives.

### 1. Capture (`capture.py` — `build_item`)

```
photo bytes (upload or camera)
  -> decode to an image (reject if corrupt)
  -> barcode/QR decode (pyzbar), on the original image
  -> crop fallback order:
       1. usable barcode box found -> crop to the label region anchored
          on that box (`imaging.crop_to_label` / `imaging.label_crop_box`)
          -> crop_method = "barcode"
       2. no usable box, but source == "camera" -> crop to the guide-box
          region instead (`imaging.center_box_crop`) — a centered
          landscape rectangle matching the on-screen camera guide box, so
          what the user framed in the box is what gets cropped
          -> crop_method = "guide_box"
       3. otherwise (e.g. an upload with no barcode) -> fall back to the
          full, uncropped image -> crop_method = None
     ("no usable box" means pyzbar found nothing, or returned a degenerate
     zero-width/zero-height box.)
  -> gallery item: {id, source, filename, original_bytes, cropped_bytes,
     crop_box, crop_method, auto_cropped, ocr_result=None}
```

The crop fallback order above is what `build_item` does by default
(`force_guide_box=False`) — the path Manage and uploads use. The **Scan**
page instead calls `build_item(..., force_guide_box=True)` (threaded through
`ui_common.add_image`), which skips barcode detection entirely and always
crops to the guide-box region (`crop_method = "guide_box"`) at the camera's
native resolution — so every Scan capture is cropped consistently
shot-to-shot and contains the whole tag, whether or not a barcode is
visible. Manage keeps the barcode-first behavior described above unchanged.

The item is now sitting in the gallery, cropped but **not yet OCR'd**
(`ocr_result` starts `None`). `crop_method` records how the crop happened
(`"barcode"`, `"guide_box"`, or `None`) and `auto_cropped` is just
`crop_method is not None`; consumers currently only branch on `auto_cropped`
and `ocr_result`, so `crop_method` is informational. The user can leave the
auto-crop as-is, or discard it and drag a manual box instead
(`streamlit-cropper`, in `page_manage.py`) — a manual re-crop sets
`crop_method` to `"manual"` and clears `ocr_result` so a stale result from
before the re-crop is never mistaken for current.

`build_item` also takes `card_type` (`"diamond"`, the default, or
`"jewelry"`), stamped onto the item as `item["card_type"]` and threaded from
the page's "Card type" radio through `ui_common.add_image`. For
`card_type="jewelry"`, both `imaging.crop_to_label`'s barcode path and the
guide-box fallback route through `imaging.guide_box_crop(image, card_type)`,
which picks the jewelry-sized box (see below) instead of the diamond one —
everything else in this capture flow (crop_method bookkeeping, manual re-crop,
gallery item shape) is identical between card types.

The green guide box itself is drawn in two places that must agree, both
sized to the same width/aspect/vertical-center fractions
(`imaging.GUIDE_BOX_WIDTH_FRAC`, `GUIDE_BOX_ASPECT`,
`GUIDE_BOX_CENTER_Y_FRAC`) as `imaging.center_box_crop` crops: the vendored
`rear_camera/frontend/style.css` (Scan's default rear-camera view) and
`ui_common.CAMERA_GUIDE_CSS` (the `st.camera_input()` fallback used by both
Manage's camera capture and Scan's "Use basic camera" toggle). Neither CSS
file can import from `imaging.py`, so this is a manually-kept-in-sync
convention, not an enforced one — if the constants change, both CSS files
must be updated to match by hand (`tests/test_ui_common.py` guards the
constants' current values as a reminder).

**Jewelry cards get a different box.** The jewelry card is bigger and closer
to square than the diamond tag, so its guide box uses its own geometry
(`imaging.JEWELRY_GUIDE_BOX_WIDTH_FRAC` = 0.92, `_ASPECT` = 1.5, `_CENTER_Y_FRAC`
= 0.45, vs. the diamond tag's 0.78 / 2.0 / 0.42) — wide and short enough that
all six printed labels (Report No. at top through Style# at bottom) fit
inside the frame. Unlike the diamond box, this one isn't duplicated into a
second CSS file: `imaging.guide_box_crop(image, card_type)` picks the geometry
for the crop, the vendored rear-camera component takes the same numbers as
call-time arguments (`box_width_pct`, `box_aspect`, `box_center_y_pct`, passed
by `page_scan.py` when `card_type == "jewelry"`), and the `st.camera_input()`
fallback box is generated by `ui_common.guide_box_css(card_type)` rather than
a static stylesheet — so the crop and the drawn box share one source of
numbers per surface instead of needing a second hand-synced CSS file per card
type.

### 2. OCR, on demand (`pipeline.process_image`)

Triggered per item ("OCR" button) or in a batch ("Run OCR on all", which
processes every item whose `ocr_result` is still `None`) — never
automatically:

```
item's cropped_bytes
  -> decode to an image (reject if corrupt)
  -> quality gate: blur check, exposure check, text-presence check
     (reject with a retake message if any fail — never enters the results table)
  -> OpenCV preprocessing (grayscale, denoise, adaptive threshold)
     -- used only for barcode/QR decoding, not for OCR (see below)
  -> barcode/QR decode (pyzbar), tried on both the original and the
     preprocessed image
  -> OCR (PaddleOCR) on the original color image
  -> regex/whitelist field parsing
  -> per-field validation -> needs_review flag
  -> one row in the results table
```

**Cropping measurably improves accuracy.** Feeding PaddleOCR a tightly
cropped label instead of a full frame removes background clutter that both
the quality gate and the detection model otherwise have to wade through: on
this project's tightly-cropped test fixtures, tracked-field accuracy
measured **~100%**, versus ~78–94% on full, uncropped frames across the
three OCR engines evaluated (see "OCR engine" below). This is the main
motivation for auto-cropping to the label before OCR rather than OCR'ing the
raw capture.

### 3. Jewelry pipeline (`pipeline_jewelry.process_image`)

Runs whenever `card_type == "jewelry"` (`ui_common.run_ocr` branches on it,
same trigger points — per-item "OCR" or "Run OCR on all", or automatically on
capture for Scan):

```
item's cropped_bytes
  -> decode to an image (reject if corrupt)
  -> quality gate: blur check, exposure check, text-presence check
     (same quality.assess_quality as the diamond pipeline)
  -> OCR (PaddleOCR) on the original color image
  -> parsing_jewelry.parse_jewelry: for each of five labels (Report No.,
     Shape and Cut, Est. Weight, Color, Clarity), scan OCR'd lines
     case-insensitively for that label at the start of the line, take
     everything after the line's ':' verbatim; Style# is matched by its own
     pattern anywhere in the OCR text instead of a label-line scan. Clarity
     is the one exception with no shape/position fallback of its own, so its
     label is located with `rapidfuzz` fuzzy string matching (tolerates
     misreads like "Clarity" -> "Clarty") when the exact spelling isn't
     found — this only decides where to start reading, the value itself is
     still taken verbatim, never fuzzy-matched or corrected
  -> parsing_jewelry.validate_jewelry_fields: needs_review = True if any of
     the six fields is still blank — no format/whitelist checks at all
  -> one row: {filename, accepted, raw_ocr_text, report_no, shape_cut,
     est_weight, color, clarity, style_no, needs_review}
```

There is **no barcode/QR decoding step** in this pipeline — the jewelry card
has no barcode, so `report_no` comes only from the printed "Report No." line.
Everything upstream of parsing (image decode, quality gate, OCR engine) is
shared with the diamond pipeline; only the field-extraction step differs, and
deliberately has no normalization or guessing — see "Jewelry-card fields"
above for why.

### `needs_review`

Set to `True` if any of the six tracked fields is missing, or present but
not in its expected format/whitelist (e.g. a grade code that doesn't match
any known report type — usually a sign of an OCR misread, not a real value).
This is the app's primary signal for "check this row by hand before trusting
the export."

## Modules

| File | Responsibility |
|---|---|
| `app.py` | `st.navigation` entry point: sets `st.set_page_config`, runs the one-time OCR model warmup, calls `ui_common.init_state()`, and registers the two pages (`page_manage.render` at `url_path="manage"`, default; `page_scan.render` at `url_path="scan"`) |
| `ui_common.py` | Shared, page-agnostic helpers and session-state used by both pages: `add_image`, `run_ocr` (routes to `ocr.pipeline` or `ocr.pipeline_jewelry` by `item["card_type"]`), `autosave` (routes to `db.save_scan` or `db.save_jewelry_scan`), `delete_item`, `item_status`, `FIELD_LABELS`/`JEWELRY_FIELD_LABELS`, the camera guide-box CSS (`CAMERA_GUIDE_CSS`, and `guide_box_css(card_type)` for the jewelry-aware variant) |
| `page_manage.py` | The **Manage** page (`render()`): "Card type" selector, file upload + camera input feeding a gallery, manual re-crop overlay (`streamlit-cropper`), per-item/"OCR all" triggers, results table, Excel download, and saved-records views/delete for **both** stores (`tag_scans`, `jewelry_scans`) |
| `page_scan.py` | The **Scan** page (`render()`): "Card type" selector, mobile rear camera with an on-screen Capture button (vendored `rear_camera` component, green alignment box sized per card type, falling back to `st.camera_input` with the same box) → always-crop-to-box auto-OCR (`ocr.pipeline` or `ocr.pipeline_jewelry`) → auto-save → a compact no-scroll result card with an inline "Fix this reading" expander |
| `rear_camera/` | In-repo vendored custom component (`rear_camera_input()`): static HTML/JS/CSS (no build step), no pip dependency. Shows the phone's rear camera with a green guide box drawn in `frontend/style.css`, sized via optional `box_width_pct`/`box_aspect`/`box_center_y_pct` arguments (used for the jewelry card's bigger box), captures at the camera's native resolution when the on-screen Capture button is tapped, and returns PNG bytes |
| `capture.py` | `build_item(image_bytes, filename, source, item_id, force_guide_box=False, card_type="diamond")` — turns raw capture bytes into a gallery item: decodes the barcode, auto-crops to the label when a usable box is found (else falls back to the full image); `force_guide_box=True` (used by Scan) skips barcode detection and always crops to the guide-box region instead; `card_type` selects the box geometry via `imaging.guide_box_crop`. Does **not** run OCR |
| `imaging.py` | OpenCV preprocessing (grayscale, denoise, adaptive threshold) — used for barcode/QR decoding only; also `crop_to_label`/`label_crop_box` (the barcode-anchored auto-crop), `center_box_crop` (the parameterized guide-box crop) and `guide_box_crop(image, card_type)` (picks diamond vs. jewelry geometry), and the `GUIDE_BOX_WIDTH_FRAC`/`GUIDE_BOX_ASPECT`/`GUIDE_BOX_CENTER_Y_FRAC` and `JEWELRY_GUIDE_BOX_WIDTH_FRAC`/`_ASPECT`/`_CENTER_Y_FRAC` constants defining each box's geometry — all used by `capture.py` |
| `decoding.py` | Barcode/QR decoding via `pyzbar` |
| `excel_export.py` | Builds the downloadable `.xlsx` from the results table (used for both the diamond and jewelry results/saved-records tables) |
| `db.py` | Supabase central store: upsert-save accepted scans, fetch shared records, `delete_one`/`delete_all` for `tag_scans`; `save_jewelry_scan`, `fetch_all_jewelry`, `delete_one_jewelry`/`delete_all_jewelry` for the separate `jewelry_scans` table; no-ops when unconfigured. **Disconnected**: kept in the codebase, fully tested, but no longer called from `page_manage.py`/`page_scan.py`/`ui_common.py` — the app now uses `sheets_db.py` instead |
| `sheets_db.py` | Google Sheets central store — **the app's active store**: `is_enabled()`, `save_scan`/`save_jewelry_scan` (upsert via find-row-then-update-or-append, since Sheets has no native upsert), `fetch_all`/`fetch_all_jewelry` (now the read source for the "Saved records" sections), `delete_one`/`delete_one_jewelry`, `delete_all`/`delete_all_jewelry` (resize to the header row). Same never-raises, degrades-safely contract as `db.py`; dormant until `st.secrets["gsheets"]` is configured |

### The `ocr/` package

Everything that's specifically about running and interpreting OCR (as opposed
to capture/UI/storage) lives in `ocr/`, a proper Python package — external
callers still just do `import ocr` / `from ocr import pipeline` etc., nothing
outside this package needed to change its calling convention:

| File | Responsibility |
|---|---|
| `ocr/__init__.py` | The former top-level `ocr.py`, unchanged in content: OCR via PaddleOCR (`get_reader`, `run_ocr`, `run_ocr_jewelry`), plus the row-reconstruction logic (`group_into_lines` for diamond, `group_into_lines_by_overlap` for jewelry) that turns per-text-box detections into printed lines. `import ocr; ocr.run_ocr(...)` works exactly as before the move |
| `ocr/models/` | Bundled PaddleOCR model weight files (`PP-OCRv6_tiny_det`/`_rec`), loaded via `_MODELS_DIR = Path(__file__).parent / "models"` in `ocr/__init__.py` — moved alongside it so that path still resolves unchanged |
| `ocr/pipeline.py` | `process_image(image_bytes, filename)` — orchestrates one (already-cropped) diamond-tag image through the OCR stage above |
| `ocr/pipeline_jewelry.py` | `process_image(image_bytes, filename)` — same quality gate + OCR engine as `ocr/pipeline.py`, no barcode/QR step, parses with `ocr/parsing_jewelry.py` |
| `ocr/parsing.py` | Regex/whitelist field extraction and validation for the diamond tag |
| `ocr/parsing_jewelry.py` | `parse_jewelry(raw_text)` / `validate_jewelry_fields(fields)` — the verbatim, label-anchored jewelry-card field extraction described in "Jewelry-card fields" above; no normalization or whitelist checks on VALUES. Clarity's label is the one exception, located via `rapidfuzz`-based fuzzy matching when misread (e.g. "Clarty"), since it has no shape/position fallback like the other fields |
| `ocr/quality.py` | The pre-OCR quality gate (blur/exposure/text-presence checks); shared by both pipelines |

`imaging.py`, `decoding.py`, and `capture.py` stay at the top level: they're
capture/crop/barcode concerns used *before* OCR runs, not OCR itself, and
`imaging.py`/`decoding.py` in particular are also used for barcode decoding
independent of the OCR engine.

## Two-page structure (Manage / Scan)

The app is `st.navigation`-based, with two pages:

- **Manage** (`page_manage.py`, default page) — the full desktop workflow
  described throughout this document: upload/camera capture into a gallery,
  manual re-crop, per-item/batch OCR, the results table, Excel export, and
  the optional Supabase saved-records view.
- **Scan** (`page_scan.py`) — a mobile-first page: the rear-camera preview
  shows a green alignment box, and tapping the on-screen Capture button takes
  a tag photo and always crops it to that box at the camera's native
  resolution
  (`force_guide_box=True`, unlike Manage's barcode-first crop), then gets
  OCR'd and (if Supabase is configured) auto-saved, with no separate
  "Run OCR" step. The result renders as a compact card sized to fit a phone
  screen without scrolling, and — if a field is missing or flagged for
  review — an inline "Fix this reading" expander lets that field be
  corrected and saved on the spot. A "Use basic camera" toggle swaps in the
  standard `st.camera_input()` widget, with the same green box, if the
  rear-camera component isn't available.

Both pages open with a "Card type" radio (`st.radio("Card type", ["Diamond
tag", "Jewelry card"], ...)`, keyed `manage_card_type` / `scan_card_type`)
that sets `st.session_state.card_type` and is threaded through every call in
that page's flow — capture (`card_type` passed to `add_image`/`build_item`),
OCR (`ui_common.run_ocr` branching between `pipeline` and `pipeline_jewelry`),
field labels shown (`FIELD_LABELS` vs. `JEWELRY_FIELD_LABELS`), the guide box
drawn/cropped, and which Supabase table a save lands in
(`autosave` → `db.save_scan` vs. `db.save_jewelry_scan`). It defaults to
`"diamond"` everywhere the value is read, so pre-existing diamond-only
behavior is unchanged unless "Jewelry card" is explicitly selected. See "Two
card types" in `README.md` and "Jewelry-card fields" / "Jewelry pipeline"
above for what changes per card type.

Wiring: `app.py` is the `st.navigation` entry point — it owns
`st.set_page_config` and the one-time OCR warmup (each must run exactly
once, before any page renders, not once per page), then calls
`ui_common.init_state()` and registers `st.Page(page_manage.render, ...,
url_path="manage", default=True)` and `st.Page(page_scan.render, ...,
url_path="scan")`. Both page modules expose their entry point as a function
named `render()`, so each `st.Page(...)` call passes an explicit
`url_path=` — `st.navigation` would otherwise have no way to distinguish
the two identically-named `render` callables. `ui_common.py` holds the
helpers and session-state both pages share (`add_image`, `run_ocr`,
`autosave`, `item_status`, `FIELD_LABELS`, the camera guide-box CSS), so
Manage and Scan behave identically for the parts of the pipeline they have
in common (auto-crop, OCR, autosave, status labels). Nothing about the OCR,
parsing, cropping, decoding, Excel, or Supabase-schema logic described
elsewhere in this document changed to support the split.

**Rear-camera component**: Scan's rear camera is `rear_camera/`, an in-repo
vendored custom component (static HTML/JS/CSS, no build step) — it replaced
the `streamlit-back-camera-input` pip dependency used earlier, so there's no
third-party package for this and no `packages.txt` change either way. It
requests the browser's rear-facing camera directly (`facingMode:
environment`), rather than needing a webcam or a Phone Link pairing (see
`README.md`), and draws the green guide box that Scan always crops to (see
"Pipeline" above for the box-geometry sync between `imaging.GUIDE_BOX_*`
and the component's CSS).

**Not in this release**: automatically capturing the instant a tag is
framed ("auto-click") is planned as a v2 enhancement — Android-first, using
the browser's `BarcodeDetector` API, falling back to today's one-tap
capture for devices/browsers without it. This release always requires the
explicit tap on Scan.

## OCR engine

The OCR engine went through three iterations, each one measured against the
same set of real tag photos (`tests/fixtures/`) rather than assumed:

1. **Tesseract** — the original choice (free, lightweight, no GPU). Real
   photos exposed several problems: a naive deskew step (correcting rotation
   based on every dark pixel in the photo, not just the tag) actively
   destroyed otherwise-readable images, since real photos are mostly plain
   background that dominates the angle estimate; the default page-segmentation
   mode skipped text sitting near the barcode/QR graphics; and short codes
   like `CVD` failed outright on a single-character misread. Final accuracy:
   ~78% of tracked fields correct across the real photo set, 0 ever wrong.
2. **EasyOCR** — tried for better accuracy. Text recognition was noticeably
   better, but at ~30-40 seconds per image on CPU — impractical for a batch
   tool — plus a much heavier dependency footprint (PyTorch).
3. **PaddleOCR (current)** — the PP-OCRv6 "tiny" detection/recognition
   models, with the tag-irrelevant preprocessing steps (document orientation
   classification, document unwarping, textline orientation) disabled since
   these tags are already flat and upright. ~5 seconds per image on CPU.
   Feeds on the original color photo, not the OpenCV-preprocessed one —
   PaddleOCR's detection model expects a natural image and cannot handle a
   single-channel thresholded array at all. Final accuracy: ~94% of tracked
   fields correct across the real photo set (9 photos, including 3 tightly
   cropped ones), 0 ever wrong.

   Two deployment-specific issues surfaced when actually pushing this to
   Streamlit Community Cloud, neither a bug in this project's own code:
   `paddlepaddle` only publishes wheels for Python 3.9–3.13, and the platform
   was observed defaulting new deployments to a newer version regardless of
   its documented default — fixed by explicitly setting Python 3.11 in the
   app's "Advanced settings" (see `README.md`). Separately, PaddleX (the
   library backing PaddleOCR) defaults to resolving/downloading models from a
   remote hub at runtime, which failed outright in that sandboxed environment
   (`No model source is available for model 'PP-OCRv6_tiny_det'`) — fixed by
   bundling the ~6.5MB model files directly in `ocr/models/` and loading them
   via `*_model_dir` instead, verified to work with no network access at all.

PaddleOCR returns one detection per text fragment (a bounding box + text +
confidence), not one continuous text block the way Tesseract does.
`ocr/__init__.py` reconstructs printed lines by grouping fragments whose
vertical centers (or, for jewelry, vertical extents) are close together,
sorted left-to-right — this is what lets the same line-based `ocr/parsing.py`
logic work regardless of engine.

## Central store (optional)

**Status: this section describes `db.py`/Supabase, which is currently
disconnected from the running app.** The app was switched over to
`sheets_db.py`/Google Sheets as its sole central store (same shape of
functions, same optional/degrades-safely contract, described in the Modules
table above). `db.py` is preserved here, unmodified and fully tested, in
case of a future revert — the description below remains accurate as a
description of `db.py` itself, just not of what the app currently calls.

`db.py` wraps an optional Supabase table (`tag_scans`) that, when configured,
gives the app a shared, cross-session store on top of the per-session flow
described above. Every accepted scan with a readable `igi_report_no`
auto-upserts into that table keyed on `igi_report_no` (one row per stone, so
re-scanning updates rather than duplicates); scans without a readable IGI
number are never sent there. Credentials live only in `st.secrets`
(`.streamlit/secrets.toml` locally, the app's Secrets settings on Streamlit
Cloud) — `db.py` never hardcodes or otherwise stores them.

The graceful-degradation contract is central to how this module is used
elsewhere: `db.is_enabled()`, `db.save_scan()`, `db.fetch_all()`,
`db.delete_one()`, and `db.delete_all()` never raise and never block the main
flow — if Supabase isn't configured (no `[supabase]` secrets) or a call fails
for any reason, they simply return `False`/`[]` and the app continues exactly
as it does with no database at all. See `README.md` for the table SQL and
secrets setup.

`db.delete_one(igi_report_no)` and `db.delete_all()` remove rows from the
shared table permanently, for every device reading it — not a local/session
action. `delete_all()` matches every row via a never-true exclusion filter on
the primary key (`neq igi_report_no "__none__"`), since PostgREST requires a
filter on delete. Both functions only report whether the API call itself
completed without error, which is a distinct question from whether a row was
actually removed: Supabase's row-level security silently blocks deletes if
the table lacks a `for delete` policy, and a blocked delete still returns a
normal (non-error) response. That's why the `tag_scans` table needs an
explicit delete policy (see `README.md`) — without it, `delete_one`/
`delete_all` return `True` but nothing is actually removed. The app can't
detect this for a single-row delete, but for "Delete all" it re-runs
`fetch_all()` immediately after and warns the user if rows are still present,
which is the practical signal that the delete policy is missing. The app's
local "Restart / new batch" control (`app.py`) is unrelated to any of this —
it only clears the current session's in-progress gallery state and never
calls into `db.py`.

**Jewelry-card scans get a second, separate table**, `jewelry_scans`, keyed
on `report_no` instead of `igi_report_no` — not a shared table with
`tag_scans`. `db.py` exposes the same shape of functions against it
(`save_jewelry_scan`, `fetch_all_jewelry`, `delete_one_jewelry`,
`delete_all_jewelry`), with the same graceful-degradation contract (never
raise; return `False`/`[]` if Supabase isn't configured or a call fails).
`ui_common.autosave` picks the table by `item["card_type"]`, and
`page_manage.py` renders a second "Saved jewelry records" section reading
`jewelry_scans`, alongside (not instead of) the diamond-tag "Saved records"
section. See `README.md`, "Central database", for the `jewelry_scans`
`CREATE TABLE` + RLS SQL.

## Known limitations

- **Deployment risk, unverified**: PaddleOCR's dependencies (`paddlepaddle` +
  `paddleocr`) run several hundred MB installed, on top of model weights
  downloaded on first use. This has not been tested against an actual
  Streamlit Community Cloud free-tier deployment and may not fit its
  build-size/memory limits.
- **Real capture limits, not fixable by parsing changes**: on a few real test
  photos, the barcode was too soft to decode and the OCR'd report number was
  also truncated/garbled — no software fix recovers a value that was never
  captured in the OCR output. `needs_review` exists specifically to catch
  these cases rather than silently exporting an incomplete row.
- No login/auth. Persistence is optional: by default capture and review/export
  happen in one sitting in one browser session; with the optional Supabase
  store configured (see "Central store"), accepted scans persist centrally and
  are shared across devices.
- No live phone-to-*separate*-desktop camera streaming. A phone can act as
  this session's camera (e.g. via Windows 11 Phone Link, see `README.md`),
  but not as a remote feed into someone else's session.

## Testing

`tests/` covers each module in isolation with mocked external dependencies
(no real OCR/barcode calls needed to run the suite), plus a real end-to-end
suite in `test_real_tag_integration.py` that runs actual photos through the
actual pipeline — no mocking — against fixtures in `tests/fixtures/`. That
real-photo suite is what caught most of the OCR issues described above; unit
tests alone would have missed them, since the bugs were in how real photos
actually behave, not in the code's logic in isolation.

Jewelry-card parsing/pipeline/UI wiring (`test_parsing_jewelry.py`,
`test_pipeline_jewelry.py`, plus jewelry cases added to `test_imaging.py`,
`test_capture.py`, `test_db.py`, `test_scan_page.py`, `test_app.py`) are
covered the same way, with mocked OCR — there is no real-photo jewelry
equivalent of `test_real_tag_integration.py` yet, since no jewelry-card
photo fixtures have been added to `tests/fixtures/` so far.

`notebooks/` holds standalone, disposable comparison notebooks (one per OCR
engine tried) used to evaluate accuracy/speed trade-offs before picking
PaddleOCR. They're sandboxes, not part of the app or its test suite.
