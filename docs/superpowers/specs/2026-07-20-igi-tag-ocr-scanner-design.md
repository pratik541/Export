# IGI Diamond Report Tag OCR Scanner — Design

Status: approved by user 2026-07-20; field list (section 1) still pending final sign-off from user's team.

## Background

Internal Streamlit tool to batch-process photos of **IGI diamond grading report tags** (not
generic gold jewelry tags — an early draft of this plan assumed purity/weight-in-grams/price
fields, which do not apply here). Each tag is a standardized IGI layout containing a barcode,
two QR codes ("CERT Link", "Video Link"), and printed diamond-grading text: report number,
report type (CVD/Natural), shape, carat, color, clarity, and cut/polish/symmetry/fluorescence
grades. A user uploads and/or photographs multiple tags in one sitting, reviews/corrects the
extracted data in an editable table, and downloads an Excel file. No database, auth, or
cross-session persistence.

## 1. Data model (per tag row)

| Column | Source | Validation (drives `needs_review`) |
|---|---|---|
| `filename` | upload/capture | — |
| `lot_ref_no` | OCR (e.g. `C141619`, printed above the barcode) | letter+digits pattern, optional, not critical |
| `igi_report_no` | **barcode decode (pyzbar) — authoritative.** Falls back to OCR-parsed `IGI CERT - ######` text if barcode fails to decode. | digits only, 8–10 digits — **critical** |
| `report_type` | OCR (`REPORT` label followed by `CVD` / `NATURAL` / `TREATED`) | must be one of known set |
| `shape` | OCR (a line matching a known shape word) | must match whitelist: Round, Emerald, Oval, Pear, Cushion, Princess, Radiant, Heart, Marquise, Asscher, etc. — **critical** |
| `carat` | OCR (a standalone line matching `\d+\.\d{2}`) | numeric pattern — **critical** |
| `color` | OCR (paired with clarity on one line) | single letter D–Z (or "Fancy...") — **critical** |
| `clarity` | OCR (paired with color on one line) | one of FL/IF/VVS1/VVS2/VS1/VS2/SI1/SI2/SI3/I1/I2/I3 — **critical** |
| `cut` | OCR (`Cut-XX` label) | one of EX/VG/G/F/P |
| `polish` | OCR (`Pol-XX` label) | one of EX/VG/G/F/P |
| `symmetry` | OCR (`Sym-XX` label) | one of EX/VG/G/F/P |
| `fluorescence` | OCR (`Fl-XX` label) | one of N/F/M/S/VS |
| `cert_link_qr`, `video_link_qr` | pyzbar (best-effort) | none required — QR is frequently unreadable on these tags; leave blank rather than block on it |
| `raw_ocr_text` | full OCR dump | always included, fallback for manual cross-check |
| `needs_review` | computed | `True` if any **critical** field (`igi_report_no`, `shape`, `carat`, `color`, `clarity`) is missing, OR any field (critical or not) fails its whitelist/pattern check — e.g. a grade OCR'd as `FX` (not a valid code; likely a misread of `EX`) flags the row even though a value is present |

Note: field list is provisional pending confirmation from the user's team. If the team
requests changes, only this section needs to change — the pipeline/UI/validation mechanics
below are independent of the exact field names.

## 2. Capture

- **Batch upload**: `st.file_uploader(accept_multiple_files=True)`, common image formats
  (jpg, jpeg, png).
- **Live capture**: `st.camera_input()`. This works with whatever camera device the browser
  can see — a laptop's built-in webcam, a USB webcam, or a phone's camera exposed as a
  virtual webcam via **Windows 11's built-in Phone Link "Camera" feature** (Bluetooth-assisted
  pairing, then Wi-Fi). No custom code is needed to support this — it is a one-time OS-level
  setup documented in the README, not app logic. `camera_input` normally only holds the most
  recent shot; accepted captures are appended to a list in `st.session_state` so repeated
  snaps build up one batch instead of overwriting each other.
- **Explicitly out of scope**: live phone-to-*separate*-desktop-session streaming (e.g. via
  `streamlit-webrtc` + TURN server). The app always runs as a single desktop session; a phone
  only participates as a virtual webcam device for that same session, never as an independent
  client streaming into someone else's session.

## 3. Quality gate

Runs immediately on every captured/uploaded image, before it's accepted into the batch —
distinct from and prior to the full extraction pipeline:

- **Blur check** — Laplacian variance (OpenCV); below threshold → reject
- **Exposure check** — fraction of blown-out (glare) or too-dark pixels; too high → reject
- **Text-presence check** — a quick OCR pass; near-zero characters detected → reject

On rejection: show an inline message (e.g. "⚠️ Image unclear — please retake") and do not add
the image to the batch or table. For camera captures, the user simply retakes. For uploads,
only that file is skipped (with a per-file error) — the rest of the batch still processes.

## 4. Pipeline (per accepted image)

```
Image → quality gate (already passed)
  → OpenCV preprocessing (grayscale → adaptive threshold → deskew → denoise)
  → pyzbar decode on BOTH preprocessed and original image
      → numeric barcode value = igi_report_no (authoritative)
  → pytesseract OCR on preprocessed image → raw text
  → line-based regex/keyword parsing (see section 1 "Source" column)
      → if barcode decode failed, fall back to OCR-parsed "IGI CERT - ######"
  → per-field whitelist/pattern validation → needs_review flag
  → row appended to st.session_state results list
```

Whole-tag OCR + line-based regex parsing was chosen over fixed-ROI cropping: IGI tags use a
consistent template, but photos vary in tilt/zoom/crop, so matching by line content is more
robust than depending on precise corner detection and fixed pixel regions.

## 5. UI/UX & export

- Single page. File uploader and camera input both feed one running batch held in
  `st.session_state`.
- Progress indicator (spinner/progress bar) while a batch processes.
- `st.data_editor()` (editable) showing all rows; `needs_review` rows visually highlighted.
- Thumbnail column next to each row (nice-to-have).
- `st.download_button()` exporting the current (possibly edited) table to `.xlsx` via
  `openpyxl`, filename `tag_scan_results_YYYYMMDD_HHMMSS.xlsx`.

## 6. Error handling

- Per-image try/except around the full pipeline; a failure shows an inline error badge for
  that file/capture and the rest of the batch continues unaffected.
- Quality-gate rejections (section 3) and pipeline-level failures are reported separately —
  rejected images never entered the batch at all, whereas pipeline failures are for images
  that passed the quality gate but still errored during processing (e.g. unexpected format).

## 7. Testing

- Regex test block (inline test cases, run without needing real tag photos) covering:
  carat (`3.01` → `3.01`), color+clarity (`E VS1` → `E`, `VS1`), shape whitelist matching,
  grade-label parsing (`Cut-VG` → `VG`), and the `IGI CERT - 809614206` fallback pattern for
  `igi_report_no`.
- Manual validation against real tag photos (including tilted/glare photos like the sample
  used to derive this design) before considering the pipeline done.

## 8. Deployment

- `requirements.txt`: streamlit, pytesseract, opencv-python-headless, pyzbar, pandas,
  openpyxl, Pillow
- `packages.txt`: tesseract-ocr, libzbar0
- No hardcoded Windows tesseract path in main logic; conditional env-var-based
  `pytesseract.pytesseract.tesseract_cmd` override for local Windows dev only.
- README covers: local run instructions (including local tesseract install per OS), Streamlit
  Community Cloud deployment steps, the optional Windows 11 Phone Link phone-as-webcam setup,
  and known limitations (OCR accuracy depends on photo quality; user should review
  `needs_review` rows before trusting the export).

## Out of scope

- No database, auth/login, or user accounts
- No cross-session/cross-device persistence (capture and review/export always happen in one
  sitting on one device)
- No live phone-to-separate-desktop camera streaming
- No cloud AI vision APIs — Tesseract only
