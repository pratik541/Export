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

The item is now sitting in the gallery, cropped but **not yet OCR'd**
(`ocr_result` starts `None`). `crop_method` records how the crop happened
(`"barcode"`, `"guide_box"`, or `None`) and `auto_cropped` is just
`crop_method is not None`; consumers currently only branch on `auto_cropped`
and `ocr_result`, so `crop_method` is informational. The user can leave the
auto-crop as-is, or discard it and drag a manual box instead
(`streamlit-cropper`, in `app.py`) — a manual re-crop sets `crop_method` to
`"manual"` and clears `ocr_result` so a stale result from before the re-crop
is never mistaken for current.

The on-screen guide box (camera preview only) is a CSS overlay in `app.py`
sized to the same width/aspect/vertical-center fractions as
`imaging.center_box_crop` (`imaging.GUIDE_BOX_WIDTH_FRAC`,
`GUIDE_BOX_ASPECT`, `GUIDE_BOX_CENTER_Y_FRAC`) — the two are meant to agree
so the crop matches what's visually framed, but the CSS can't import from
`imaging.py`, so this is a manually-kept-in-sync convention, not an enforced
one: if the constants change, the CSS must be updated to match by hand.

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

### `needs_review`

Set to `True` if any of the six tracked fields is missing, or present but
not in its expected format/whitelist (e.g. a grade code that doesn't match
any known report type — usually a sign of an OCR misread, not a real value).
This is the app's primary signal for "check this row by hand before trusting
the export."

## Modules

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI: file upload + camera input feeding a gallery, manual re-crop overlay (`streamlit-cropper`), per-item/"OCR all" triggers, results table, Excel download |
| `capture.py` | `build_item(image_bytes, filename, source, item_id)` — turns raw capture bytes into a gallery item: decodes the barcode, auto-crops to the label when a usable box is found (else falls back to the full image), does **not** run OCR |
| `pipeline.py` | `process_image(image_bytes, filename)` — orchestrates one (already-cropped) image through the OCR stage above |
| `quality.py` | The pre-OCR quality gate (blur/exposure/text-presence checks) |
| `imaging.py` | OpenCV preprocessing (grayscale, denoise, adaptive threshold) — used for barcode/QR decoding only; also `crop_to_label`/`label_crop_box` (the barcode-anchored auto-crop) and `center_box_crop` (the guide-box crop fallback for camera captures), both used by `capture.py` |
| `decoding.py` | Barcode/QR decoding via `pyzbar` |
| `ocr.py` | OCR via PaddleOCR, plus the row-reconstruction logic that turns its per-text-box detections into printed lines |
| `parsing.py` | Regex/whitelist field extraction and validation |
| `excel_export.py` | Builds the downloadable `.xlsx` from the results table |
| `db.py` | Optional Supabase central store: upsert-save accepted scans, fetch shared records, `delete_one`/`delete_all` to remove saved records; no-ops when unconfigured |

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
   bundling the ~6.5MB model files directly in `models/` and loading them via
   `*_model_dir` instead, verified to work with no network access at all.

PaddleOCR returns one detection per text fragment (a bounding box + text +
confidence), not one continuous text block the way Tesseract does. `ocr.py`
reconstructs printed lines by grouping fragments whose vertical centers are
close together, sorted left-to-right — this is what lets the same line-based
`parsing.py` logic work regardless of engine.

## Central store (optional)

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

`notebooks/` holds standalone, disposable comparison notebooks (one per OCR
engine tried) used to evaluate accuracy/speed trade-offs before picking
PaddleOCR. They're sandboxes, not part of the app or its test suite.
