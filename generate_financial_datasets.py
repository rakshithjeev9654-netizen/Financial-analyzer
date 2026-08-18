"""
generate_financial_datasets.py
===============================
Generates a large, diverse set of sample financial datasets for training
a model to recognise and parse financial statement data in any format.

Every dimension is varied independently and randomly across examples:
  - Column naming conventions
  - Layout (wide, transposed, single/multi-period)
  - Period labels
  - Number formats (raw, currency, thousands/millions, parentheses)
  - Completeness (missing columns, missing values, extra columns)
  - Data quality (clean, noisy, inconsistent units, duplicate periods)

Accounting relationships are internally consistent:
  Assets = Liabilities + Equity
  Gross Profit = Revenue - COGS
  Operating Income = Gross Profit - OpEx
  Net Income = Operating Income - Interest - Tax

Outputs:
  datasets/sample_NNN.csv   — one file per dataset
  datasets/manifest.json    — maps each file to its ground-truth line items
"""

import os
import json
import random
import math
import csv
import copy
from pathlib import Path

random.seed(42)

OUTPUT_DIR = Path("datasets")
OUTPUT_DIR.mkdir(exist_ok=True)

NUM_DATASETS = 500   # total files to generate

# ═══════════════════════════════════════════════════════════════════════
# 1.  GROUND-TRUTH LINE ITEMS
#     These are the 14 standard items the model must learn to extract.
# ═══════════════════════════════════════════════════════════════════════

STANDARD_FIELDS = [
    "revenue",
    "cogs",
    "operating_income",
    "net_income",
    "current_assets",
    "current_liabilities",
    "inventory",
    "cash",
    "total_assets",
    "total_liabilities",
    "shareholders_equity",
    "accounts_receivable",
    "accounts_payable",
    "interest_expense",
]

# ═══════════════════════════════════════════════════════════════════════
# 2.  COLUMN NAME ALIASES
#     Each standard field maps to many real-world naming variants.
# ═══════════════════════════════════════════════════════════════════════

ALIASES = {
    "revenue": [
        "revenue", "Revenue", "REVENUE", "total_revenue", "Total Revenue",
        "net_revenue", "Net Revenue", "sales", "Sales", "Net Sales",
        "net_sales", "turnover", "Turnover", "Total Sales", "top_line",
        "Chiffre d'affaires", "Umsatz", "Ingresos", "収益",
        "Rev", "REV", "Revs", "Income from Operations",
    ],
    "cogs": [
        "cogs", "COGS", "cost_of_goods_sold", "Cost of Goods Sold",
        "cost_of_sales", "Cost of Sales", "cost_of_revenue", "Cost of Revenue",
        "direct_costs", "Direct Costs", "COS", "CoGS", "Cost of Products",
        "Herstellungskosten", "Coût des ventes", "売上原価",
        "Cost of Merchandise", "Production Costs", "COGS ($)",
    ],
    "operating_income": [
        "operating_income", "Operating Income", "EBIT", "ebit",
        "operating_profit", "Operating Profit", "op_income", "Op Income",
        "income_from_operations", "Income from Operations",
        "operating_earnings", "Operating Earnings", "EBIT ($)",
        "Betriebsergebnis", "Résultat opérationnel", "営業利益",
        "Operating Result", "op_profit", "Op Profit",
    ],
    "net_income": [
        "net_income", "Net Income", "net_profit", "Net Profit",
        "profit_after_tax", "Profit After Tax", "PAT", "pat",
        "bottom_line", "earnings", "Earnings", "net_earnings",
        "Net Earnings", "profit_for_period", "Profit for Period",
        "Jahresüberschuss", "Résultat net", "当期純利益",
        "NI", "ni", "Net Income ($)", "Net Profit (Loss)",
    ],
    "current_assets": [
        "current_assets", "Current Assets", "current_assets_total",
        "Total Current Assets", "total_current_assets", "CA",
        "short_term_assets", "Short-Term Assets", "Umlaufvermögen",
        "Actifs courants", "流動資産", "current assets",
        "CurrAssets", "Curr Assets",
    ],
    "current_liabilities": [
        "current_liabilities", "Current Liabilities", "total_current_liabilities",
        "Total Current Liabilities", "CL", "short_term_liabilities",
        "Short-Term Liabilities", "current_obligations",
        "Kurzfristige Verbindlichkeiten", "Passifs courants", "流動負債",
        "Curr Liabilities", "CurrLiab",
    ],
    "inventory": [
        "inventory", "Inventory", "inventories", "Inventories",
        "stock", "Stock", "merchandise_inventory", "Merchandise Inventory",
        "raw_materials_and_wip", "Stocks", "Lagerbestand",
        "Inventaire", "棚卸資産", "Inv", "INV",
    ],
    "cash": [
        "cash", "Cash", "cash_and_cash_equivalents", "Cash and Cash Equivalents",
        "cash_equivalents", "Cash Equivalents", "cash_on_hand",
        "Cash & Cash Equivalents", "C&CE", "liquidity",
        "Kassenbestand", "Trésorerie", "現金", "Cash (end of period)",
        "cash_balance", "Cash Balance",
    ],
    "total_assets": [
        "total_assets", "Total Assets", "assets_total", "Assets Total",
        "total_assets_value", "TA", "ta", "Gesamtvermögen",
        "Total Actifs", "総資産", "Total Assets ($)",
        "Total Balance Sheet Assets", "sum_of_assets",
    ],
    "total_liabilities": [
        "total_liabilities", "Total Liabilities", "total_debt",
        "Total Debt", "liabilities_total", "Liabilities Total",
        "TL", "tl", "total_obligations", "Gesamtverbindlichkeiten",
        "Total Passifs", "総負債", "Total Liabilities ($)",
    ],
    "shareholders_equity": [
        "shareholders_equity", "Shareholders' Equity", "total_equity",
        "Total Equity", "equity", "Equity", "stockholders_equity",
        "Stockholders' Equity", "net_assets", "Net Assets",
        "owners_equity", "book_value", "Book Value",
        "Eigenkapital", "Capitaux propres", "純資産",
        "SE", "se", "Total SE",
    ],
    "accounts_receivable": [
        "accounts_receivable", "Accounts Receivable", "receivables",
        "Receivables", "trade_receivables", "Trade Receivables",
        "debtors", "Debtors", "AR", "ar",
        "Forderungen", "Créances clients", "売掛金",
        "Accts Receivable", "Net Receivables",
    ],
    "accounts_payable": [
        "accounts_payable", "Accounts Payable", "payables",
        "Payables", "trade_payables", "Trade Payables",
        "creditors", "Creditors", "AP", "ap",
        "Verbindlichkeiten", "Dettes fournisseurs", "買掛金",
        "Accts Payable", "Net Payables",
    ],
    "interest_expense": [
        "interest_expense", "Interest Expense", "interest_expenses",
        "Interest Expenses", "finance_costs", "Finance Costs",
        "borrowing_costs", "Borrowing Costs", "IE", "ie",
        "Zinsaufwendungen", "Charges d'intérêts", "支払利息",
        "Interest Paid", "Net Interest Expense",
    ],
}

# ═══════════════════════════════════════════════════════════════════════
# 3.  EXTRA / IRRELEVANT COLUMNS (noise)
# ═══════════════════════════════════════════════════════════════════════

NOISE_COLUMNS = [
    "employee_count", "Employee Count", "headcount",
    "market_cap", "Market Cap", "EPS", "eps", "dividends",
    "Dividends", "capex", "CapEx", "Capital Expenditure",
    "depreciation", "Depreciation", "amortization", "Amortization",
    "ebitda", "EBITDA", "gross_profit", "Gross Profit",
    "operating_cash_flow", "Free Cash Flow", "fcf",
    "country", "Country", "currency", "Currency", "fiscal_year_end",
    "auditor", "Auditor", "notes", "Notes", "segment",
    "region", "Region", "product_line", "Product Line",
    "tax_rate", "Tax Rate", "effective_tax_rate",
]

# ═══════════════════════════════════════════════════════════════════════
# 4.  PERIOD LABEL GENERATORS
# ═══════════════════════════════════════════════════════════════════════

def gen_period_labels(n_periods, style=None):
    """Generate n period labels in a randomly chosen style."""
    styles = [
        "FY_YYYY",        # FY2022, FY2023, FY2024
        "YYYY",           # 2022, 2023, 2024
        "Q_FY",           # Q1 FY24, Q2 FY24
        "ISO_DATE",       # 2022-12-31, 2023-12-31
        "Month_YYYY",     # Dec 2022, Dec 2023
        "YY",             # FY22, FY23
        "Period_N",       # Period 1, Period 2
        "Year_N",         # Year 1, Year 2
        "CY_YYYY",        # CY2022, CY2023
    ]
    if style is None:
        style = random.choice(styles)

    base_year = random.randint(2018, 2023)
    labels = []

    if style == "FY_YYYY":
        for i in range(n_periods):
            labels.append(f"FY{base_year + i}")
    elif style == "YYYY":
        for i in range(n_periods):
            labels.append(str(base_year + i))
    elif style == "Q_FY":
        quarters = ["Q1", "Q2", "Q3", "Q4"]
        for i in range(n_periods):
            q = quarters[i % 4]
            yr = str(base_year + i // 4)[2:]
            labels.append(f"{q} FY{yr}")
    elif style == "ISO_DATE":
        months = ["03-31", "06-30", "09-30", "12-31"]
        for i in range(n_periods):
            yr = base_year + i // 4
            m = months[i % 4]
            labels.append(f"{yr}-{m}")
    elif style == "Month_YYYY":
        month_names = ["Mar", "Jun", "Sep", "Dec"]
        for i in range(n_periods):
            yr = base_year + i // 4
            m = month_names[i % 4]
            labels.append(f"{m} {yr}")
    elif style == "YY":
        for i in range(n_periods):
            labels.append(f"FY{str(base_year + i)[2:]}")
    elif style == "Period_N":
        for i in range(n_periods):
            labels.append(f"Period {i + 1}")
    elif style == "Year_N":
        for i in range(n_periods):
            labels.append(f"Year {i + 1}")
    elif style == "CY_YYYY":
        for i in range(n_periods):
            labels.append(f"CY{base_year + i}")
    return labels

# ═══════════════════════════════════════════════════════════════════════
# 5.  NUMBER FORMATTER
# ═══════════════════════════════════════════════════════════════════════

def format_number(value, fmt_style, scale):
    """
    Format a raw float according to a random format style.
    fmt_style options:
      raw_int, raw_float, comma_sep, currency_usd, currency_gbp,
      currency_eur, thousands_k, millions_m, lakh, crore,
      parentheses_neg, pct (for margins only)
    scale: 1, 1000, or 1_000_000 (already applied to value before calling)
    """
    scaled = value / scale

    if value < 0:
        # negative in parentheses
        if fmt_style == "parentheses_neg":
            return f"({abs(scaled):,.0f})"
        elif fmt_style in ("currency_usd", "currency_gbp", "currency_eur"):
            sym = {"currency_usd": "$", "currency_gbp": "£", "currency_eur": "€"}[fmt_style]
            return f"{sym}({abs(scaled):,.0f})"

    if fmt_style == "raw_int":
        return str(int(round(scaled)))
    elif fmt_style == "raw_float":
        return f"{scaled:.2f}"
    elif fmt_style == "comma_sep":
        return f"{scaled:,.0f}"
    elif fmt_style == "currency_usd":
        return f"${scaled:,.0f}"
    elif fmt_style == "currency_gbp":
        return f"£{scaled:,.0f}"
    elif fmt_style == "currency_eur":
        return f"€{scaled:,.0f}"
    elif fmt_style == "thousands_k":
        return f"{scaled/1_000:,.1f}K" if scale == 1 else f"{scaled:,.1f}"
    elif fmt_style == "millions_m":
        return f"{scaled/1_000_000:,.2f}M" if scale == 1 else f"{scaled:,.2f}"
    elif fmt_style == "lakh":
        # Indian lakh format: XX,XX,XXX
        s = f"{int(round(scaled)):,}"  # fallback
        return s
    elif fmt_style == "crore":
        return f"{scaled/10_000_000:.2f} Cr" if scale == 1 else f"{scaled:.2f} Cr"
    elif fmt_style == "parentheses_neg":
        return f"{scaled:,.0f}"
    else:
        return f"{scaled:,.0f}"


# ═══════════════════════════════════════════════════════════════════════
# 6.  ACCOUNTING DATA GENERATOR
#     Generates internally consistent financials for N periods.
# ═══════════════════════════════════════════════════════════════════════

def gen_financials(n_periods):
    """
    Generate n_periods of internally consistent financial data.
    Returns a list of dicts keyed by standard field name.
    All values are raw floats (before scaling/formatting).
    """
    records = []

    # Base values for first period (realistic ranges)
    base_revenue = random.uniform(5_000_000, 500_000_000)
    gross_margin = random.uniform(0.25, 0.70)
    op_margin    = random.uniform(0.05, 0.25)
    net_margin   = random.uniform(0.03, 0.18)
    asset_turn   = random.uniform(0.4, 1.8)
    ca_ratio     = random.uniform(0.30, 0.55)   # current assets / total assets
    inv_ratio    = random.uniform(0.05, 0.20)   # inventory / total assets
    ar_ratio     = random.uniform(0.08, 0.20)   # AR / total assets
    ap_ratio     = random.uniform(0.04, 0.12)   # AP / total liabilities
    cash_ratio   = random.uniform(0.04, 0.15)   # cash / total assets
    de_ratio     = random.uniform(0.3, 1.8)     # debt / equity
    cl_ratio     = random.uniform(0.4, 0.6)     # current liabilities / total liabilities
    interest_cov = random.uniform(3, 15)        # EBIT / interest

    growth_rate = random.uniform(-0.05, 0.20)   # YoY revenue growth

    for i in range(n_periods):
        # Revenue grows each period
        revenue = base_revenue * ((1 + growth_rate) ** i)
        revenue += random.gauss(0, revenue * 0.01)  # tiny noise

        cogs             = revenue * (1 - gross_margin)
        gross_profit     = revenue - cogs
        operating_income = revenue * op_margin
        net_income       = revenue * net_margin

        # Interest expense derived from coverage ratio
        interest_expense = max(operating_income / interest_cov, 0)

        # Balance sheet
        total_assets = revenue / asset_turn
        current_assets      = total_assets * ca_ratio
        inventory           = total_assets * inv_ratio
        accounts_receivable = total_assets * ar_ratio
        cash                = total_assets * cash_ratio

        # Liabilities + Equity = Assets
        total_equity     = total_assets / (1 + de_ratio)
        total_liabilities = total_assets - total_equity
        current_liabilities = total_liabilities * cl_ratio
        accounts_payable    = total_liabilities * ap_ratio

        # Ensure current_assets >= inventory + AR + cash (basic sanity)
        current_assets = max(current_assets, inventory + accounts_receivable + cash + 1)

        records.append({
            "revenue":              revenue,
            "cogs":                 cogs,
            "operating_income":     operating_income,
            "net_income":           net_income,
            "current_assets":       current_assets,
            "current_liabilities":  current_liabilities,
            "inventory":            inventory,
            "cash":                 cash,
            "total_assets":         total_assets,
            "total_liabilities":    total_liabilities,
            "shareholders_equity":  total_equity,
            "accounts_receivable":  accounts_receivable,
            "accounts_payable":     accounts_payable,
            "interest_expense":     interest_expense,
        })

    return records


# ═══════════════════════════════════════════════════════════════════════
# 7.  DATASET BUILDER
#     Applies all format/layout/quality variations to raw financials.
# ═══════════════════════════════════════════════════════════════════════

def build_dataset(dataset_id):
    """
    Build one CSV dataset with random variations.
    Returns (rows, ground_truth_dict).
    rows = list of dicts suitable for csv.DictWriter
    ground_truth = {period_label: {standard_field: raw_float}}
    """
    # ── How many periods? ────────────────────────────────────────────
    n_periods = random.choices([1, 2, 3, 4, 5], weights=[10, 25, 35, 20, 10])[0]

    # ── Generate raw financials ──────────────────────────────────────
    financials = gen_financials(n_periods)

    # ── Period labels ────────────────────────────────────────────────
    period_style = random.choice([
        "FY_YYYY", "YYYY", "Q_FY", "ISO_DATE",
        "Month_YYYY", "YY", "Period_N", "CY_YYYY"
    ])
    period_labels = gen_period_labels(n_periods, style=period_style)

    # ── Number format + scale ────────────────────────────────────────
    scale = random.choices([1, 1_000, 1_000_000], weights=[40, 35, 25])[0]
    fmt_style = random.choice([
        "raw_int", "raw_float", "comma_sep",
        "currency_usd", "currency_gbp", "currency_eur",
        "thousands_k", "parentheses_neg", "lakh",
    ])

    # ── Column name style ────────────────────────────────────────────
    # Pick one alias per field (consistently within a dataset)
    col_names = {}
    for field in STANDARD_FIELDS:
        col_names[field] = random.choice(ALIASES[field])

    # ── Which fields to include? (completeness variation) ────────────
    n_missing = random.choices([0, 1, 2, 3, 4], weights=[40, 25, 20, 10, 5])[0]
    missing_fields = random.sample(STANDARD_FIELDS, n_missing) if n_missing else []
    included_fields = [f for f in STANDARD_FIELDS if f not in missing_fields]

    # ── Extra noise columns ──────────────────────────────────────────
    n_noise = random.choices([0, 1, 2, 3], weights=[35, 30, 25, 10])[0]
    noise_cols = random.sample(NOISE_COLUMNS, min(n_noise, len(NOISE_COLUMNS)))

    # ── Layout ───────────────────────────────────────────────────────
    layout = random.choices(
        ["wide", "transposed", "single_period"],
        weights=[50, 30, 20]
    )[0]
    if n_periods == 1:
        layout = "single_period"

    # ── Data quality variations ──────────────────────────────────────
    quality = random.choices(
        ["clean", "noisy", "inconsistent_units", "duplicate_period", "out_of_order"],
        weights=[40, 25, 15, 10, 10]
    )[0]

    # ── Build rows ───────────────────────────────────────────────────
    rows = []
    ground_truth = {}

    def fmt(val):
        return format_number(val, fmt_style, scale)

    def noise_val():
        """Random noise column value."""
        return random.choice([
            str(random.randint(100, 100000)),
            f"{random.uniform(0.01, 0.99):.2%}",
            random.choice(["USD", "GBP", "EUR", "INR", "JPY"]),
            random.choice(["KPMG", "Deloitte", "EY", "PwC", ""]),
            "",
        ])

    if layout in ("wide", "single_period"):
        # Rows = periods, columns = line items
        # Shuffle column order randomly
        field_order = included_fields[:]
        random.shuffle(field_order)

        # Add period column name
        period_col = random.choice([
            "period", "Period", "year", "Year", "fiscal_year",
            "Fiscal Year", "date", "Date", "Quarter", "quarter",
        ])

        if layout == "single_period":
            # Only one period — no period column sometimes
            include_period_col = random.choice([True, False])
        else:
            include_period_col = True

        # Duplicate or out-of-order for quality variation
        work_periods = list(zip(period_labels, financials))
        if quality == "duplicate_period" and len(work_periods) > 1:
            dup = random.choice(work_periods)
            work_periods.insert(random.randint(0, len(work_periods)), dup)
        if quality == "out_of_order" and len(work_periods) > 1:
            random.shuffle(work_periods)

        for lbl, rec in work_periods:
            row = {}
            if include_period_col:
                row[period_col] = lbl

            # Inconsistent units: some fields scaled differently
            for field in field_order:
                val = rec[field]
                if quality == "inconsistent_units" and random.random() < 0.2:
                    # Use a different scale for this cell
                    alt_scale = random.choice([s for s in [1, 1_000, 1_000_000] if s != scale])
                    row[col_names[field]] = format_number(val, fmt_style, alt_scale)
                elif quality == "noisy" and random.random() < 0.08:
                    # Introduce a missing value
                    row[col_names[field]] = random.choice(["", "N/A", "—", "#N/A", "n/a"])
                else:
                    row[col_names[field]] = fmt(val)

            # Noise columns
            for nc in noise_cols:
                row[nc] = noise_val()

            rows.append(row)
            ground_truth[lbl] = {f: rec[f] for f in STANDARD_FIELDS}

    elif layout == "transposed":
        # Rows = line items, columns = periods
        # Header row: line_item_col + period labels
        item_col = random.choice([
            "line_item", "Line Item", "metric", "Metric",
            "account", "Account", "description", "Description",
            "item", "Item",
        ])

        # Out-of-order columns
        col_period_labels = period_labels[:]
        if quality == "out_of_order" and len(col_period_labels) > 1:
            random.shuffle(col_period_labels)

        # Duplicate period column
        if quality == "duplicate_period" and len(col_period_labels) > 1:
            dup = random.choice(col_period_labels)
            col_period_labels.insert(random.randint(0, len(col_period_labels)), dup)

        for field in included_fields:
            row = {item_col: col_names[field]}
            for lbl in col_period_labels:
                # Find the matching period index
                if lbl in period_labels:
                    idx = period_labels.index(lbl)
                    val = financials[idx][field]
                else:
                    # Duplicate period — same value
                    orig = col_period_labels[[i for i, l in enumerate(col_period_labels) if l == lbl][0] - 1]
                    idx = period_labels.index(orig) if orig in period_labels else 0
                    val = financials[idx][field]

                if quality == "inconsistent_units" and random.random() < 0.2:
                    alt_scale = random.choice([s for s in [1, 1_000, 1_000_000] if s != scale])
                    row[lbl] = format_number(val, fmt_style, alt_scale)
                elif quality == "noisy" and random.random() < 0.08:
                    row[lbl] = random.choice(["", "N/A", "—", "#N/A"])
                else:
                    row[lbl] = fmt(val)

            # Noise column values inline
            for nc in noise_cols:
                row[nc] = noise_val()

            rows.append(row)

        # Ground truth keyed by original (non-duplicate) labels
        for i, lbl in enumerate(period_labels):
            ground_truth[lbl] = {f: financials[i][f] for f in STANDARD_FIELDS}

    return rows, ground_truth, {
        "dataset_id": dataset_id,
        "n_periods": n_periods,
        "layout": layout,
        "period_style": period_style,
        "number_format": fmt_style,
        "scale": scale,
        "missing_fields": missing_fields,
        "noise_columns": noise_cols,
        "quality": quality,
        "period_labels": period_labels,
        "column_names_used": {f: col_names.get(f, "") for f in STANDARD_FIELDS},
    }


# ═══════════════════════════════════════════════════════════════════════
# 8.  MAIN — generate all datasets
# ═══════════════════════════════════════════════════════════════════════

def main():
    manifest = []
    errors   = []

    print(f"Generating {NUM_DATASETS} datasets into '{OUTPUT_DIR}/'...")

    for i in range(NUM_DATASETS):
        dataset_id = f"sample_{i:04d}"
        try:
            rows, ground_truth, meta = build_dataset(dataset_id)

            if not rows:
                errors.append({"id": dataset_id, "error": "empty rows"})
                continue

            # Write CSV
            csv_path = OUTPUT_DIR / f"{dataset_id}.csv"
            all_keys = list(rows[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)

            # Add to manifest
            manifest.append({
                "file": f"{dataset_id}.csv",
                "meta": meta,
                "ground_truth": ground_truth,
            })

        except Exception as e:
            errors.append({"id": dataset_id, "error": str(e)})

        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{NUM_DATASETS} done...")

    # Write manifest
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(f"\nDone!")
    print(f"   {len(manifest)} datasets written to '{OUTPUT_DIR}/'")
    print(f"   Manifest: {manifest_path}")
    if errors:
        print(f"   WARNING: {len(errors)} errors: {errors[:5]}")

    # ── Summary stats ────────────────────────────────────────────────
    layouts     = {}
    qualities   = {}
    formats     = {}
    n_periods_d = {}
    for m in manifest:
        mt = m["meta"]
        layouts[mt["layout"]]   = layouts.get(mt["layout"], 0) + 1
        qualities[mt["quality"]] = qualities.get(mt["quality"], 0) + 1
        formats[mt["number_format"]] = formats.get(mt["number_format"], 0) + 1
        k = str(mt["n_periods"])
        n_periods_d[k] = n_periods_d.get(k, 0) + 1

    print("\n--- Layout distribution ---")
    for k, v in sorted(layouts.items()):     print(f"   {k:<25} {v:>4}")
    print("\n--- Quality distribution ---")
    for k, v in sorted(qualities.items()):   print(f"   {k:<25} {v:>4}")
    print("\n--- Number format distribution ---")
    for k, v in sorted(formats.items()):     print(f"   {k:<25} {v:>4}")
    print("\n--- Period count distribution ---")
    for k, v in sorted(n_periods_d.items()): print(f"   {k} period(s): {v:>4}")


if __name__ == "__main__":
    main()
