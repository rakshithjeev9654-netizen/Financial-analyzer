"""
modules/extractor.py
====================
Smart Financial Data Extraction Engine.

Reads a pandas DataFrame (any layout/format) and extracts the 14 standard
financial line items needed for ratio analysis.

Strategies tried in order:
  1. Wide layout  — rows = periods, columns = line items
  2. Transposed   — rows = line items, columns = periods
  3. Single-value — single-period flat file

For each field it returns:
  - value         : float or None
  - raw_label     : the column/row header it matched
  - confidence    : 0.0 – 1.0
  - period_values : {period_label: float} for all detected periods
  - scale         : scale factor applied (1, 1000, 1_000_000)
  - reason        : why it's None (if not found)

Number cleaning handles:
  $, £, €, ₹, commas, spaces, K/M/B/Cr/L suffixes,
  (negative) parentheses, negative signs.
"""

from __future__ import annotations
import re
import math
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np

# ═══════════════════════════════════════════════════════════════════════
# 1. Standard field aliases
# ═══════════════════════════════════════════════════════════════════════

STANDARD_FIELDS = [
    "revenue", "cogs", "operating_income", "net_income",
    "current_assets", "current_liabilities", "inventory", "cash",
    "total_assets", "total_liabilities", "shareholders_equity",
    "accounts_receivable", "accounts_payable", "interest_expense",
]

ALIASES: dict[str, list[str]] = {
    "revenue": [
        "revenue", "total revenue", "net revenue", "sales", "net sales",
        "total sales", "turnover", "top line", "income from operations",
        "chiffre d affaires", "umsatz", "ingresos", "rev", "revs",
        "gross revenue", "operating revenue", "total turnover",
    ],
    "cogs": [
        "cogs", "cost of goods sold", "cost of sales", "cost of revenue",
        "direct costs", "cos", "cost of products", "herstellungskosten",
        "cout des ventes", "production costs", "cost of merchandise",
        "cost of services", "cost of goods",
    ],
    "operating_income": [
        "operating income", "ebit", "operating profit", "op income",
        "income from operations", "operating earnings", "operating result",
        "betriebsergebnis", "resultat operationnel", "op profit",
        "earnings before interest and tax", "earnings before interest tax",
        "profit from operations",
    ],
    "net_income": [
        "net income", "net profit", "profit after tax", "pat",
        "bottom line", "earnings", "net earnings", "profit for period",
        "profit for the year", "jahresuberschuss", "resultat net",
        "ni", "net income loss", "net profit loss", "profit loss",
        "income after tax", "net earnings loss",
    ],
    "current_assets": [
        "current assets", "total current assets", "ca",
        "short term assets", "umlaufvermogen", "actifs courants",
        "current assets total",
    ],
    "current_liabilities": [
        "current liabilities", "total current liabilities", "cl",
        "short term liabilities", "current obligations",
        "kurzfristige verbindlichkeiten", "passifs courants",
        "current liabilities total",
    ],
    "inventory": [
        "inventory", "inventories", "stock", "stocks",
        "merchandise inventory", "raw materials", "finished goods",
        "lagerbestand", "inventaire", "inv",
    ],
    "cash": [
        "cash", "cash and cash equivalents", "cash equivalents",
        "cash on hand", "cash and equivalents", "c ce",
        "kassenbestand", "tresorerie", "cash balance",
        "cash end of period", "cash and short term investments",
    ],
    "total_assets": [
        "total assets", "assets total", "ta", "gesamtvermogen",
        "total actifs", "total balance sheet assets", "sum of assets",
        "total asset", "balance sheet total",
    ],
    "total_liabilities": [
        "total liabilities", "total debt", "liabilities total", "tl",
        "total obligations", "gesamtverbindlichkeiten",
        "total liabilities and debt", "total debt and liabilities",
    ],
    "shareholders_equity": [
        "shareholders equity", "stockholders equity", "total equity",
        "equity", "net assets", "owners equity", "book value",
        "eigenkapital", "capitaux propres", "se",
        "total shareholders equity", "total stockholders equity",
        "shareholders funds", "net worth",
    ],
    "accounts_receivable": [
        "accounts receivable", "receivables", "trade receivables",
        "debtors", "ar", "forderungen", "creances clients",
        "net receivables", "trade and other receivables",
    ],
    "accounts_payable": [
        "accounts payable", "payables", "trade payables",
        "creditors", "ap", "verbindlichkeiten", "dettes fournisseurs",
        "net payables", "trade and other payables",
    ],
    "interest_expense": [
        "interest expense", "interest expenses", "finance costs",
        "borrowing costs", "ie", "zinsaufwendungen",
        "charges d interets", "interest paid", "net interest expense",
        "finance charges", "interest cost",
    ],
}

# Pre-compute normalized alias sets for fast lookup
def _norm(s: str) -> str:
    """Normalize a label for matching: lowercase, remove punctuation/extra spaces."""
    s = s.lower()
    s = re.sub(r"['\u2019\u2018\(\)\[\]{}_\-/\\,\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

_NORM_ALIASES: dict[str, list[str]] = {
    field: [_norm(a) for a in aliases]
    for field, aliases in ALIASES.items()
}


# ═══════════════════════════════════════════════════════════════════════
# 2. Data structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class FieldExtraction:
    field: str
    value: Optional[float]              # Latest period value (or only period)
    raw_label: str                      # Header text that matched
    confidence: float                   # 0.0–1.0
    period_values: dict                 # {period_label: float}
    scale: int                          # 1, 1000, or 1_000_000
    reason: str                         # Why None if not found
    all_raw_values: dict                # {period_label: raw_string}


@dataclass
class ExtractionResult:
    fields: dict[str, FieldExtraction]  # standard_field → FieldExtraction
    layout: str                         # "wide" | "transposed" | "unknown"
    periods: list[str]                  # Detected period labels in order
    warnings: list[str]
    unmatched_labels: list[str]         # Labels in file not matched to any field
    raw_df: pd.DataFrame                # Original parsed DataFrame


# ═══════════════════════════════════════════════════════════════════════
# 3. Number cleaner
# ═══════════════════════════════════════════════════════════════════════

_SCALE_PATTERNS = [
    (r"(\d[\d,\.]*)\s*crore", 10_000_000),
    (r"(\d[\d,\.]*)\s*cr\.?", 10_000_000),
    (r"(\d[\d,\.]*)\s*lakh", 100_000),
    (r"(\d[\d,\.]*)\s*l\.?",  100_000),
    (r"(\d[\d,\.]*)\s*billion", 1_000_000_000),
    (r"(\d[\d,\.]*)\s*b\.?",   1_000_000_000),
    (r"(\d[\d,\.]*)\s*million", 1_000_000),
    (r"(\d[\d,\.]*)\s*mm\.?",  1_000_000),
    (r"(\d[\d,\.]*)\s*m\.?",   1_000_000),
    (r"(\d[\d,\.]*)\s*thousand", 1_000),
    (r"(\d[\d,\.]*)\s*k\.?",   1_000),
]


def clean_number(raw) -> Optional[float]:
    """
    Convert any raw financial number representation to a float.
    Returns None if not parseable.
    Handles: currency symbols, commas, spaces, K/M/B/Cr/L suffixes,
             parentheses for negatives, plain negatives.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s in ("", "-", "—", "N/A", "n/a", "#N/A", "NA", "nil", "Nil", "—"):
        return None

    negative = False

    # Parentheses = negative  e.g. (1,234)
    if re.match(r"^\(.*\)$", s):
        s = s[1:-1]
        negative = True

    # Leading minus
    if s.startswith("-"):
        negative = True
        s = s[1:]

    # Strip currency symbols and whitespace
    s = re.sub(r"[£$€₹₩¥\s]", "", s)

    # Try scale suffix patterns first
    s_lower = s.lower()
    for pattern, multiplier in _SCALE_PATTERNS:
        m = re.match(pattern, s_lower)
        if m:
            num_str = m.group(1).replace(",", "")
            try:
                val = float(num_str) * multiplier
                return -val if negative else val
            except ValueError:
                continue

    # Strip trailing % (ignore percentages — not direct values)
    if s.endswith("%"):
        return None

    # Remove commas (thousands separator)
    s = s.replace(",", "")

    # Try plain float
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════════════
# 4. Label matcher
# ═══════════════════════════════════════════════════════════════════════

def _jaccard(a: str, b: str) -> float:
    """Jaccard similarity between word sets of two strings."""
    wa = set(a.split())
    wb = set(b.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def match_label(label: str) -> tuple[Optional[str], float]:
    """
    Match a column/row label to a standard field.
    Returns (field_name, confidence) or (None, 0.0).

    Confidence levels:
      1.0  — exact normalized match
      0.9  — label is fully contained in alias or alias in label
      0.7+  — high Jaccard similarity
      0.0  — no match
    """
    norm = _norm(label)
    if not norm:
        return None, 0.0

    best_field = None
    best_conf  = 0.0

    for field_name, aliases in _NORM_ALIASES.items():
        for alias in aliases:
            # Exact match
            if norm == alias:
                return field_name, 1.0

            # Containment
            if alias in norm or norm in alias:
                conf = 0.9
                if conf > best_conf:
                    best_conf  = conf
                    best_field = field_name

            # Word-level Jaccard
            j = _jaccard(norm, alias)
            if j > 0.65 and j > best_conf:
                best_conf  = j * 0.95  # slight penalty vs containment
                best_field = field_name

    return best_field, best_conf


# ═══════════════════════════════════════════════════════════════════════
# 5. Layout detector
# ═══════════════════════════════════════════════════════════════════════

def _count_matches(labels: list[str]) -> int:
    """Count how many labels match any standard field."""
    return sum(1 for lbl in labels if match_label(str(lbl))[0] is not None)


def detect_layout(df: pd.DataFrame) -> str:
    """
    Decide whether the DataFrame is:
      "wide"       — rows = periods, cols = fields  (normal)
      "transposed" — rows = fields, cols = periods
      "unknown"    — can't determine
    """
    if df.empty:
        return "unknown"

    col_matches = _count_matches([str(c) for c in df.columns])
    # Check first column as potential field-name column
    first_col_matches = _count_matches([str(v) for v in df.iloc[:, 0].dropna()])

    # Wide: many column headers match field names
    if col_matches >= 3:
        return "wide"

    # Transposed: first column values match field names
    if first_col_matches >= 3:
        return "transposed"

    # Fallback: try wide
    return "wide"


# ═══════════════════════════════════════════════════════════════════════
# 6. Period label detector
# ═══════════════════════════════════════════════════════════════════════

_PERIOD_PATTERNS = [
    r"\b(FY|CY|Q[1-4])\s*\d{2,4}\b",
    r"\b\d{4}\b",
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}\b",
    r"\b(Q[1-4])\b",
    r"\bPeriod\s*\d+\b",
    r"\bYear\s*\d+\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
]
_PERIOD_RE = re.compile("|".join(_PERIOD_PATTERNS), re.IGNORECASE)


def looks_like_period(label: str) -> bool:
    return bool(_PERIOD_RE.search(str(label)))


def _detect_period_columns(df: pd.DataFrame) -> list[str]:
    """Return column names that look like period labels (for transposed layout)."""
    return [str(c) for c in df.columns if looks_like_period(str(c))]


# ═══════════════════════════════════════════════════════════════════════
# 7. Extract wide layout
# ═══════════════════════════════════════════════════════════════════════

def _find_period_col(df: pd.DataFrame) -> Optional[str]:
    """Find the column that contains period labels (e.g. 'period', 'year', 'date')."""
    period_col_names = {
        "period", "year", "fiscal year", "date", "quarter",
        "fy", "cy", "reporting period", "financial year",
    }
    for col in df.columns:
        if _norm(str(col)) in period_col_names:
            return str(col)
    # Fallback: check if first col has period-like values
    if not df.empty:
        first_col_vals = df.iloc[:, 0].dropna().astype(str).tolist()
        if sum(looks_like_period(v) for v in first_col_vals) >= len(first_col_vals) * 0.5:
            return str(df.columns[0])
    return None


def extract_wide(df: pd.DataFrame) -> tuple[dict, list[str], list[str]]:
    """
    Extract from wide layout: rows = periods, columns = fields.
    Returns (field_extractions, periods, unmatched_labels).
    field_extractions = {field: FieldExtraction}
    """
    period_col = _find_period_col(df)

    # Determine period labels
    if period_col:
        periods = [str(v) for v in df[period_col].dropna().tolist()]
    else:
        # Use row index or generic labels
        periods = [f"Period {i+1}" for i in range(len(df))]

    extractions: dict[str, FieldExtraction] = {}
    unmatched: list[str] = []

    for col in df.columns:
        if period_col and str(col) == period_col:
            continue

        field_name, confidence = match_label(str(col))

        raw_series = df[col]
        period_values: dict[str, Optional[float]] = {}
        all_raw: dict[str, str] = {}

        for idx, (period, raw_val) in enumerate(zip(periods, raw_series)):
            all_raw[period] = str(raw_val)
            period_values[period] = clean_number(raw_val)

        # Latest non-null value
        numeric_vals = [(p, v) for p, v in period_values.items() if v is not None]
        latest_value = numeric_vals[-1][1] if numeric_vals else None

        if field_name and confidence >= 0.6:
            # Only keep the best match per field
            existing = extractions.get(field_name)
            if existing is None or confidence > existing.confidence:
                extractions[field_name] = FieldExtraction(
                    field=field_name,
                    value=latest_value,
                    raw_label=str(col),
                    confidence=confidence,
                    period_values={p: v for p, v in period_values.items() if v is not None},
                    scale=1,
                    reason="" if latest_value is not None else "No numeric values found in column",
                    all_raw_values=all_raw,
                )
        else:
            if str(col).strip():
                unmatched.append(str(col))

    return extractions, periods, unmatched


# ═══════════════════════════════════════════════════════════════════════
# 8. Extract transposed layout
# ═══════════════════════════════════════════════════════════════════════

def extract_transposed(df: pd.DataFrame) -> tuple[dict, list[str], list[str]]:
    """
    Extract from transposed layout: rows = fields, columns = periods.
    First column = item labels, remaining columns = period values.
    Returns (field_extractions, periods, unmatched_labels).
    """
    label_col = str(df.columns[0])
    period_cols = [str(c) for c in df.columns[1:] if str(c).strip()]

    extractions: dict[str, FieldExtraction] = {}
    unmatched: list[str] = []

    for _, row in df.iterrows():
        row_label = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
        if not row_label.strip():
            continue

        field_name, confidence = match_label(row_label)

        period_values: dict[str, Optional[float]] = {}
        all_raw: dict[str, str] = {}

        for period_col in period_cols:
            raw_val = row.get(period_col, "")
            all_raw[period_col] = str(raw_val)
            period_values[period_col] = clean_number(raw_val)

        numeric_vals = [(p, v) for p, v in period_values.items() if v is not None]
        latest_value = numeric_vals[-1][1] if numeric_vals else None

        if field_name and confidence >= 0.6:
            existing = extractions.get(field_name)
            if existing is None or confidence > existing.confidence:
                extractions[field_name] = FieldExtraction(
                    field=field_name,
                    value=latest_value,
                    raw_label=row_label,
                    confidence=confidence,
                    period_values={p: v for p, v in period_values.items() if v is not None},
                    scale=1,
                    reason="" if latest_value is not None else "No numeric values found in row",
                    all_raw_values=all_raw,
                )
        else:
            if row_label.strip():
                unmatched.append(row_label)

    return extractions, period_cols, unmatched


# ═══════════════════════════════════════════════════════════════════════
# 9. Accounting cross-check
# ═══════════════════════════════════════════════════════════════════════

def accounting_crosscheck(extractions: dict[str, FieldExtraction]) -> list[str]:
    """
    Verify: Total Assets ≈ Total Liabilities + Shareholders' Equity.
    Returns list of warning strings.
    """
    warnings = []
    ta  = extractions.get("total_assets")
    tl  = extractions.get("total_liabilities")
    seq = extractions.get("shareholders_equity")

    if ta and tl and seq:
        if ta.value and tl.value and seq.value:
            lhs = ta.value
            rhs = tl.value + seq.value
            if lhs != 0:
                diff_pct = abs(lhs - rhs) / abs(lhs) * 100
                if diff_pct > 5:
                    warnings.append(
                        f"Accounting check: Total Assets ({lhs:,.0f}) ≠ "
                        f"Total Liabilities + Equity ({rhs:,.0f}) — "
                        f"difference is {diff_pct:.1f}%. "
                        f"Please verify the extracted values."
                    )
    return warnings


# ═══════════════════════════════════════════════════════════════════════
# 10. Build normalized DataFrame for ratio engine
# ═══════════════════════════════════════════════════════════════════════

def build_normalized_df(
    extractions: dict[str, FieldExtraction],
    mapping_overrides: dict[str, str] | None = None,
    raw_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build a clean DataFrame with standard column names, suitable for run_all_ratios().
    Each row = one period, each column = one standard field name.

    mapping_overrides: {standard_field: raw_column_or_label} from the review page.
    """
    # Collect all periods
    all_periods: set[str] = set()
    for fe in extractions.values():
        all_periods.update(fe.period_values.keys())

    if not all_periods:
        # Single-period fallback
        all_periods = {"Current Period"}

    periods = sorted(all_periods)
    rows = []

    for period in periods:
        row = {"period": period}
        for field_name in STANDARD_FIELDS:
            fe = extractions.get(field_name)
            if fe and period in fe.period_values:
                row[field_name] = fe.period_values[period]
            elif fe and fe.value is not None and len(fe.period_values) == 1:
                # Single-value field — use it for all periods
                row[field_name] = fe.value
            else:
                row[field_name] = None
        rows.append(row)

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════
# 11. Main entry point
# ═══════════════════════════════════════════════════════════════════════

def extract_fields(df: pd.DataFrame) -> ExtractionResult:
    """
    Main extraction function.
    Receives a parsed DataFrame (from parser.parse_file) and returns
    an ExtractionResult with all 14 standard fields extracted or marked missing.
    """
    warnings_out: list[str] = []

    if df is None or df.empty:
        return ExtractionResult(
            fields={f: FieldExtraction(
                field=f, value=None, raw_label="", confidence=0.0,
                period_values={}, scale=1,
                reason="File contained no data.",
                all_raw_values={},
            ) for f in STANDARD_FIELDS},
            layout="unknown", periods=[], warnings=["File contained no data."],
            unmatched_labels=[], raw_df=df,
        )

    layout = detect_layout(df)

    if layout == "transposed":
        extractions, periods, unmatched = extract_transposed(df)
    else:
        extractions, periods, unmatched = extract_wide(df)

    # Fill in missing fields as unavailable
    for field_name in STANDARD_FIELDS:
        if field_name not in extractions:
            extractions[field_name] = FieldExtraction(
                field=field_name,
                value=None,
                raw_label="",
                confidence=0.0,
                period_values={},
                scale=1,
                reason=f"No column matching '{field_name}' was found in the file.",
                all_raw_values={},
            )

    # Accounting cross-check
    xcheck_warnings = accounting_crosscheck(extractions)
    warnings_out.extend(xcheck_warnings)

    return ExtractionResult(
        fields=extractions,
        layout=layout,
        periods=periods,
        warnings=warnings_out,
        unmatched_labels=unmatched,
        raw_df=df,
    )
