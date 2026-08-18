# Smart Extraction Engine — Plan

## Top-Level Overview

Replace the current "column name must match exactly" parser with a **Smart Extraction Engine** that can read financial data from any Excel or PDF layout, extract the 14 standard line items using fuzzy matching and accounting logic, and present an **Extraction Review** page where the user can verify and manually remap any field before ratio analysis runs.

**Scope:**
- New module: `modules/extractor.py` — smart multi-strategy extractor
- New route: `/review` — extraction review page
- New route: `/confirm-mapping` — user submits corrected mapping → runs ratios
- New template: `templates/review.html` — shows extracted fields, allows manual remapping
- Update: `app.py` — upload route redirects to `/review` instead of `/dashboard`
- Update: `modules/parser.py` — keep as raw file reader, extractor sits on top

**Non-goals:**
- No OCR for scanned PDFs (pdfplumber handles text-based PDFs already)
- No AI/LLM inference — all matching is deterministic and explainable

---

## Sub-Tasks

---

### Sub-Task 1 — Build `modules/extractor.py`

**Intent:**
Create the core smart extraction module that sits between the file parser and the ratio engine. It tries multiple strategies to locate the 14 standard fields in any file layout, then returns a structured result with confidence levels for each match.

**Expected Outcomes:**
- `extractor.py` exists with a single public function `extract_fields(df) -> ExtractionResult`
- Handles wide layout (rows = periods), transposed layout (rows = items, cols = periods), single-period, and multi-sheet
- Fuzzy name matching using the full alias list from `generate_financial_datasets.py`
- Number cleaning: strips `$`, `£`, `€`, commas, `(neg)`, `K`/`M`/`Cr` suffixes, detects scale
- Accounting cross-check: verifies `total_assets ≈ total_liabilities + shareholders_equity`
- Returns per-field: `{field: {value, raw_label_found, confidence, row_or_col, scale_applied}}`
- Fields not found return `{field: {value: None, confidence: 0, reason: "..."}}`

**Todo List:**
1. Define `ExtractionResult` dataclass with: `fields`, `periods`, `layout_detected`, `warnings`, `unmatched_labels`
2. Define full alias dict (copy from `generate_financial_datasets.py` ALIASES)
3. Implement `detect_layout(df)` → `"wide"` | `"transposed"` | `"unknown"`
4. Implement `clean_number(raw_str) -> float | None` — strips symbols, handles scale suffixes
5. Implement `fuzzy_match_label(label, aliases) -> (field, confidence)` — normalized string distance
6. Implement `extract_wide(df)` — rows=periods, cols=fields
7. Implement `extract_transposed(df)` — rows=fields, cols=periods
8. Implement `accounting_crosscheck(fields)` — warns if assets ≠ liab + equity by >5%
9. Implement `extract_fields(df) -> ExtractionResult` — orchestrates all strategies

**Relevant Context:**
- `modules/parser.py` — `parse_file()` already returns a normalized DataFrame; extractor receives this
- `generate_financial_datasets.py` — full ALIASES dict (copy verbatim, do not import)
- `modules/ratios.py` line 20 — `_col(*names, df=df)` pattern shows what column names ratios expect

**Status:** `[ ] pending`

---

### Sub-Task 2 — Add `/review` route and `templates/review.html`

**Intent:**
After upload, instead of going straight to the dashboard, show the user a review page that displays every field the extractor found (with the raw label it matched and the confidence), lets them correct wrong mappings via a dropdown, and lets them manually assign unrecognized columns to standard fields.

**Expected Outcomes:**
- `/review` GET route renders `review.html` with extraction results from session
- Review page shows a table: Standard Field | Raw Label Found | Extracted Value | Confidence | Dropdown to remap
- Green row = high confidence (≥ 0.85), amber = medium (0.60–0.84), red/strikethrough = low or missing
- Unmatched columns from the file are listed at the bottom as "Unmapped columns" — user can assign them
- "Confirm & Analyze" button submits to `/confirm-mapping`
- "Re-upload" link goes back to `/`

**Todo List:**
1. Add `/review` GET route in `app.py` — reads `_analysis_store[session_id]["extraction"]`
2. Write `templates/review.html` extending `base.html`
3. Review table: one row per standard field, columns: Field Name | Detected As | Sample Value | Confidence bar | Remap dropdown
4. Unmapped section: lists columns in file not matched to any standard field, with dropdown to assign
5. Period selector: if multiple periods detected, show which period values are displayed in review
6. "Confirm & Analyze" → POST to `/confirm-mapping` with hidden form of final mappings
7. Style: use existing CSS variables, green/amber/red confidence indicators

**Relevant Context:**
- `templates/upload.html` — existing upload form pattern to follow
- `templates/dashboard.html` — existing table/card pattern
- `static/css/style.css` — CSS variables (`--green`, `--amber`, `--rose`) for confidence colors

**Status:** `[ ] pending`

---

### Sub-Task 3 — Add `/confirm-mapping` route

**Intent:**
Receive the user's confirmed (and optionally corrected) field mappings from the review page, build a clean normalized DataFrame from the mapping, run ratio analysis, and redirect to the dashboard exactly as before.

**Expected Outcomes:**
- `/confirm-mapping` POST route accepts form data with field→column mappings
- Rebuilds a clean DataFrame using the user-confirmed mapping
- Calls `run_all_ratios()` and `generate_analysis()` exactly as the existing `/upload` route does
- Stores result in `_analysis_store` and redirects to `/dashboard`
- If user corrected a mapping, the corrected value is used

**Todo List:**
1. Add `/confirm-mapping` POST route in `app.py`
2. Parse form: `{standard_field: selected_raw_column_name}` for all 14 fields
3. Build normalized DataFrame: for each mapped field, pull the raw column from the stored raw DataFrame, clean numbers via `clean_number()`, rename to standard field name
4. Call `run_all_ratios(normalized_df)` → `ratios`
5. Call `generate_analysis(ratios)` → `analysis`
6. Store in `_analysis_store` and redirect to `/dashboard`

**Relevant Context:**
- `app.py` `/upload` route lines 83–139 — exact pattern to replicate for storage/redirect
- `modules/extractor.py` `clean_number()` — reuse for number cleaning
- `modules/ratios.py` `run_all_ratios(df)` — expects DataFrame with standard column names

**Status:** `[ ] pending`

---

### Sub-Task 4 — Update `/upload` route to use extractor

**Intent:**
Change the upload flow so that after parsing the file, the extractor runs and the result is stored in session, then the user is redirected to `/review` instead of directly to `/dashboard`.

**Expected Outcomes:**
- `/upload` POST route calls `extract_fields(df)` after `parse_file()`
- Stores raw DataFrame and `ExtractionResult` in `_analysis_store`
- Redirects to `/review` instead of `/dashboard`
- Existing direct-upload path (clean template files) still works — if all 14 fields extracted with high confidence, show a "looks perfect" banner on the review page

**Todo List:**
1. In `app.py`, after `parse_file()`, call `extract_fields(df)` from `modules/extractor.py`
2. Store `raw_df` (as dict of lists) and `extraction` result in `_analysis_store[analysis_id]`
3. Change redirect from `url_for("dashboard")` to `url_for("review")`
4. Pass `ExtractionResult` fields to the review template

**Relevant Context:**
- `app.py` lines 83–139 — current upload route
- `modules/extractor.py` — new module from Sub-Task 1

**Status:** `[ ] pending`

---

### Sub-Task 5 — Test with diverse real-world formats

**Intent:**
Validate the full pipeline works correctly for: clean template upload, transposed Excel, messy Excel with merged cells and currency symbols, and PDF.

**Expected Outcomes:**
- Upload `sample_data.csv` → review page shows all 14 fields green → confirm → dashboard works
- Upload a transposed Excel (items as rows) → extractor detects transposed layout → review shows correct values
- Upload Excel with `$1,234,567` numbers → extractor cleans them correctly
- Upload a missing-field file → review page shows those fields as red/unavailable

**Todo List:**
1. Run end-to-end test with `sample_data.csv`
2. Create a transposed test CSV and verify extraction
3. Create a currency-symbol test CSV and verify number cleaning
4. Verify dashboard still renders correctly after confirm-mapping flow

**Relevant Context:**
- `sample_data.csv` — existing clean test file at workspace root
- `datasets/sample_0000.csv` through `sample_0499.csv` — 500 diverse test files

**Status:** `[ ] pending`
