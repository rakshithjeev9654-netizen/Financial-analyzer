"""
File parser module.
Supports CSV, XLSX, and PDF (table extraction via pdfplumber).
Returns a pandas DataFrame and a list of parsing warnings/errors.
"""

import pandas as pd
import pdfplumber
import io
from pathlib import Path


def parse_file(filepath: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Parse the uploaded file into a DataFrame.
    Returns (df, warnings).
    On hard failure raises ValueError with a user-friendly message.
    """
    path = Path(filepath)
    suffix = path.suffix.lower()
    warnings = []

    if suffix == ".csv":
        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            raise ValueError(f"Could not read CSV file: {e}")

    elif suffix in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(filepath, engine="openpyxl")
        except Exception as e:
            raise ValueError(f"Could not read Excel file: {e}")

    elif suffix == ".pdf":
        df, warnings = _parse_pdf(filepath)

    else:
        raise ValueError(
            f"Unsupported file type '{suffix}'. Please upload a .csv, .xlsx, or .pdf file."
        )

    if df is None or df.empty:
        raise ValueError(
            "The uploaded file contained no usable tabular data. "
            "Please upload a file with rows and labelled columns."
        )

    # Normalise column names: strip whitespace, lower-case
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df, warnings


def _parse_pdf(filepath: str) -> tuple[pd.DataFrame, list[str]]:
    """Extract the first well-formed table found in a PDF."""
    warnings = []
    tables = []
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages):
            extracted = page.extract_tables()
            for tbl in extracted:
                if tbl and len(tbl) > 1:
                    tables.append(tbl)
            if tables:
                break  # use first page that has tables

    if not tables:
        raise ValueError(
            "No tables were found in the PDF. "
            "Please upload a PDF that contains financial statement tables, "
            "or use CSV/XLSX format instead."
        )

    # Use the largest table on the page
    best = max(tables, key=lambda t: len(t))
    header = [str(c).strip() if c else f"col_{i}" for i, c in enumerate(best[0])]
    rows = best[1:]
    df = pd.DataFrame(rows, columns=header)

    warnings.append(
        "Data was extracted from a PDF table. Please verify the values match "
        "your source document before relying on the analysis."
    )
    return df, warnings


def get_numeric(df: pd.DataFrame, col: str):
    """
    Safely coerce a DataFrame column to numeric.
    Returns a pandas Series or None if column doesn't exist / is all NaN.
    """
    if col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce")
    if s.isna().all():
        return None
    return s


def latest_and_prev(series) -> tuple:
    """
    Return (latest_value, prev_value) from a series.
    prev_value is None if series has only one non-null row.
    """
    if series is None:
        return None, None
    vals = series.dropna().tolist()
    if not vals:
        return None, None
    latest = vals[-1]
    prev = vals[-2] if len(vals) >= 2 else None
    return latest, prev
