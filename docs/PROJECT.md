# IGI Diamond Report Tag Scanner

## What this is

A Streamlit app for batch-digitizing IGI diamond grading report tags. A user
uploads photos (or captures them with a camera) of one or more tags, the app
extracts the report number, report type, shape, carat, color, and clarity
from each, shows the results in an editable table, and exports them to a
timestamped Excel file.

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

```
photo bytes
  -> decode to an image (reject if corrupt)
  -> quality gate: blur check, exposure check, text-presence check
     (reject with a retake message if any fail — never enters the batch)
  -> OpenCV preprocessing (grayscale, denoise, adaptive threshold)
     -- used only for barcode/QR decoding, not for OCR (see below)
  -> barcode/QR decode (pyzbar), tried on both the original and the
     preprocessed image
  -> OCR (PaddleOCR) on the original color image
  -> regex/whitelist field parsing
  -> per-field validation -> needs_review flag
  -> one row in the results table
```

### `needs_review`

Set to `True` if any of the six tracked fields is missing, or present but
not in its expected format/whitelist (e.g. a grade code that doesn't match
any known report type — usually a sign of an OCR misread, not a real value).
This is the app's primary signal for "check this row by hand before trusting
the export."

## Modules

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI: file upload + camera input, session-state batch tracking, results table, Excel download |
| `pipeline.py` | `process_image(image_bytes, filename)` — orchestrates one image through the full pipeline above |
| `quality.py` | The pre-OCR quality gate (blur/exposure/text-presence checks) |
| `imaging.py` | OpenCV preprocessing (grayscale, denoise, adaptive threshold) — used for barcode/QR decoding only |
| `decoding.py` | Barcode/QR decoding via `pyzbar` |
| `ocr.py` | OCR via PaddleOCR, plus the row-reconstruction logic that turns its per-text-box detections into printed lines |
| `parsing.py` | Regex/whitelist field extraction and validation |
| `excel_export.py` | Builds the downloadable `.xlsx` from the results table |

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

PaddleOCR returns one detection per text fragment (a bounding box + text +
confidence), not one continuous text block the way Tesseract does. `ocr.py`
reconstructs printed lines by grouping fragments whose vertical centers are
close together, sorted left-to-right — this is what lets the same line-based
`parsing.py` logic work regardless of engine.

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
- No database, login, or cross-device/cross-session persistence — capture and
  review/export happen in one sitting, in one browser session.
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
