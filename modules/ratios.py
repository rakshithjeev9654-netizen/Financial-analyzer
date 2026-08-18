"""
Financial Ratio Calculation Engine.

Every formula is documented as a comment immediately above its calculation.
Rules:
- Use average of beginning/ending balances where two periods exist.
- Fall back to period-end value when only one period is available,
  and note this in the interpretation text.
- Never compare against a fixed threshold unless a benchmark is in the data.
- Return a RatioResult for every ratio attempted, with is_available=False
  and a clear reason when data is missing.
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from modules.parser import get_numeric, latest_and_prev


def _col(*names, df):
    """Return the first non-None get_numeric result for a list of column names."""
    for name in names:
        result = get_numeric(df, name)
        if result is not None:
            return result
    return None


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RatioResult:
    name: str
    category: str                        # Liquidity | Profitability | Solvency | Efficiency
    value: Optional[float]               # None when not available
    prev_value: Optional[float]          # None when only one period
    is_available: bool
    unavailable_reason: str = ""         # Populated when is_available=False
    interpretation: str = ""             # Plain-English one-liner
    unit: str = "x"                      # "x", "%", "days"
    formula: str = ""                    # Human-readable formula string
    status: str = ""                     # Improving | Declining | Stable | ...

    @property
    def change_pct(self) -> Optional[float]:
        """Percentage change from prev to current. None if either is missing."""
        if self.value is None or self.prev_value is None:
            return None
        if self.prev_value == 0:
            return None
        return (self.value - self.prev_value) / abs(self.prev_value) * 100

    @property
    def formatted_value(self) -> str:
        if not self.is_available or self.value is None:
            return "N/A"
        if self.unit == "%":
            return f"{self.value:.1f}%"
        if self.unit == "days":
            return f"{self.value:.1f} days"
        return f"{self.value:.2f}x"

    @property
    def formatted_prev(self) -> str:
        if self.prev_value is None:
            return "—"
        if self.unit == "%":
            return f"{self.prev_value:.1f}%"
        if self.unit == "days":
            return f"{self.prev_value:.1f} days"
        return f"{self.prev_value:.2f}x"

    @property
    def formatted_change(self) -> str:
        c = self.change_pct
        if c is None:
            return "—"
        sign = "+" if c >= 0 else ""
        return f"{sign}{c:.1f}%"


def _status(value, prev, higher_is_better=True) -> str:
    """
    Determine status label from directional change only.
    Never applies a fixed threshold.
    """
    if value is None or prev is None:
        return "No prior period"
    diff = value - prev
    tolerance = abs(prev) * 0.005 if prev != 0 else 0.0001
    if abs(diff) <= tolerance:
        return "Stable"
    if higher_is_better:
        return "Improving" if diff > 0 else "Declining"
    else:  # lower is better (e.g. Debt-to-Equity, days)
        return "Improving" if diff < 0 else "Declining"


def _avg(a, b):
    """Average of two values; returns a if b is None."""
    if a is None:
        return None
    if b is None:
        return a
    return (a + b) / 2


def _pct(v):
    """Convert decimal to percentage string."""
    if v is None:
        return None
    return v * 100


# ---------------------------------------------------------------------------
# Liquidity Ratios
# ---------------------------------------------------------------------------

def calc_current_ratio(df) -> RatioResult:
    """
    Current Ratio = Current Assets / Current Liabilities
    Measures ability to cover short-term obligations with short-term assets.
    """
    ca = get_numeric(df, "current_assets")
    cl = get_numeric(df, "current_liabilities")
    curr_ca, prev_ca = latest_and_prev(ca)
    curr_cl, prev_cl = latest_and_prev(cl)

    if curr_ca is None or curr_cl is None:
        missing = []
        if curr_ca is None: missing.append("Current Assets")
        if curr_cl is None: missing.append("Current Liabilities")
        return RatioResult(
            name="Current Ratio", category="Liquidity",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Current Assets / Current Liabilities"
        )

    if curr_cl == 0:
        return RatioResult(
            name="Current Ratio", category="Liquidity",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Current Liabilities is zero — division not possible.",
            formula="Current Assets / Current Liabilities"
        )

    value = curr_ca / curr_cl
    prev = (prev_ca / prev_cl) if (prev_ca is not None and prev_cl not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=True)

    interp = (
        f"Short-term assets are approximately {value:.2f}x short-term liabilities, "
        f"indicating {'a comfortable' if value >= 1.5 else 'a tight'} short-term liquidity position."
    )
    if prev is None:
        interp += " (Period-end values used; no prior period available.)"

    return RatioResult(
        name="Current Ratio", category="Liquidity",
        value=value, prev_value=prev, is_available=True,
        interpretation=interp, unit="x", status=st,
        formula="Current Assets / Current Liabilities"
    )


def calc_quick_ratio(df) -> RatioResult:
    """
    Quick Ratio = (Current Assets - Inventories) / Current Liabilities
    Measures liquidity excluding inventory (less liquid asset).
    """
    ca = get_numeric(df, "current_assets")
    inv = _col("inventory", "inventories", df=df)
    cl = get_numeric(df, "current_liabilities")
    curr_ca, prev_ca = latest_and_prev(ca)
    curr_inv, prev_inv = latest_and_prev(inv)
    curr_cl, prev_cl = latest_and_prev(cl)

    if curr_ca is None or curr_cl is None:
        missing = []
        if curr_ca is None: missing.append("Current Assets")
        if curr_cl is None: missing.append("Current Liabilities")
        return RatioResult(
            name="Quick Ratio", category="Liquidity",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="(Current Assets − Inventory) / Current Liabilities"
        )

    inv_curr = curr_inv if curr_inv is not None else 0
    inv_prev = prev_inv if prev_inv is not None else 0

    if curr_cl == 0:
        return RatioResult(
            name="Quick Ratio", category="Liquidity",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Current Liabilities is zero — division not possible.",
            formula="(Current Assets − Inventory) / Current Liabilities"
        )

    value = (curr_ca - inv_curr) / curr_cl
    prev = ((prev_ca - inv_prev) / prev_cl) if (prev_ca is not None and prev_cl not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=True)

    note = "" if curr_inv is not None else " (Inventory not found; treated as 0.)"
    interp = (
        f"Excluding inventory, liquid assets cover short-term liabilities {value:.2f} times.{note}"
    )
    return RatioResult(
        name="Quick Ratio", category="Liquidity",
        value=value, prev_value=prev, is_available=True,
        interpretation=interp, unit="x", status=st,
        formula="(Current Assets − Inventory) / Current Liabilities"
    )


def calc_cash_ratio(df) -> RatioResult:
    """
    Cash Ratio = (Cash + Cash Equivalents) / Current Liabilities
    The most conservative liquidity measure — only the most liquid assets.
    """
    cash = _col("cash", "cash_and_cash_equivalents", df=df)
    cl = get_numeric(df, "current_liabilities")
    curr_cash, prev_cash = latest_and_prev(cash)
    curr_cl, prev_cl = latest_and_prev(cl)

    if curr_cash is None or curr_cl is None:
        missing = []
        if curr_cash is None: missing.append("Cash (or Cash and Cash Equivalents)")
        if curr_cl is None: missing.append("Current Liabilities")
        return RatioResult(
            name="Cash Ratio", category="Liquidity",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Cash / Current Liabilities"
        )

    if curr_cl == 0:
        return RatioResult(
            name="Cash Ratio", category="Liquidity",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Current Liabilities is zero — division not possible.",
            formula="Cash / Current Liabilities"
        )

    value = curr_cash / curr_cl
    prev = (prev_cash / prev_cl) if (prev_cash is not None and prev_cl not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=True)

    return RatioResult(
        name="Cash Ratio", category="Liquidity",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"Cash covers {value:.2f}x current liabilities — the most conservative liquidity view.",
        unit="x", status=st,
        formula="Cash / Current Liabilities"
    )


# ---------------------------------------------------------------------------
# Profitability Ratios
# ---------------------------------------------------------------------------

def calc_gross_profit_margin(df) -> RatioResult:
    """
    Gross Profit Margin = (Revenue - COGS) / Revenue × 100
    Shows the % of revenue retained after direct production costs.
    """
    rev = _col("revenue", "total_revenue", "sales", df=df)
    cogs = _col("cogs", "cost_of_goods_sold", "cost_of_sales", df=df)
    curr_rev, prev_rev = latest_and_prev(rev)
    curr_cogs, prev_cogs = latest_and_prev(cogs)

    if curr_rev is None or curr_cogs is None:
        missing = []
        if curr_rev is None: missing.append("Revenue")
        if curr_cogs is None: missing.append("COGS / Cost of Goods Sold")
        return RatioResult(
            name="Gross Profit Margin", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="(Revenue − COGS) / Revenue × 100"
        )

    if curr_rev == 0:
        return RatioResult(
            name="Gross Profit Margin", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Revenue is zero — division not possible.",
            formula="(Revenue − COGS) / Revenue × 100"
        )

    value = _pct((curr_rev - curr_cogs) / curr_rev)
    prev = _pct((prev_rev - prev_cogs) / prev_rev) if (prev_rev not in (None, 0) and prev_cogs is not None) else None
    st = _status(value, prev, higher_is_better=True)

    return RatioResult(
        name="Gross Profit Margin", category="Profitability",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"{value:.1f}% of revenue remains after direct production costs.",
        unit="%", status=st,
        formula="(Revenue − COGS) / Revenue × 100"
    )


def calc_operating_profit_margin(df) -> RatioResult:
    """
    Operating Profit Margin = Operating Income / Revenue × 100
    Shows operational efficiency before interest and taxes.
    """
    rev = _col("revenue", "total_revenue", "sales", df=df)
    op_inc = _col("operating_income", "operating_profit", "ebit", df=df)
    curr_rev, prev_rev = latest_and_prev(rev)
    curr_op, prev_op = latest_and_prev(op_inc)

    if curr_rev is None or curr_op is None:
        missing = []
        if curr_rev is None: missing.append("Revenue")
        if curr_op is None: missing.append("Operating Income / EBIT")
        return RatioResult(
            name="Operating Profit Margin", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Operating Income / Revenue × 100"
        )

    if curr_rev == 0:
        return RatioResult(
            name="Operating Profit Margin", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Revenue is zero — division not possible.",
            formula="Operating Income / Revenue × 100"
        )

    value = _pct(curr_op / curr_rev)
    prev = _pct(prev_op / prev_rev) if (prev_rev not in (None, 0) and prev_op is not None) else None
    st = _status(value, prev, higher_is_better=True)

    return RatioResult(
        name="Operating Profit Margin", category="Profitability",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"Operating profit represents {value:.1f}% of revenue.",
        unit="%", status=st,
        formula="Operating Income / Revenue × 100"
    )


def calc_net_profit_margin(df) -> RatioResult:
    """
    Net Profit Margin = Net Income / Revenue × 100
    Bottom-line profitability after all costs.
    """
    rev = _col("revenue", "total_revenue", "sales", df=df)
    ni = _col("net_income", "net_profit", "profit_after_tax", df=df)
    curr_rev, prev_rev = latest_and_prev(rev)
    curr_ni, prev_ni = latest_and_prev(ni)

    if curr_rev is None or curr_ni is None:
        missing = []
        if curr_rev is None: missing.append("Revenue")
        if curr_ni is None: missing.append("Net Income / Net Profit")
        return RatioResult(
            name="Net Profit Margin", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Net Income / Revenue × 100"
        )

    if curr_rev == 0:
        return RatioResult(
            name="Net Profit Margin", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Revenue is zero — division not possible.",
            formula="Net Income / Revenue × 100"
        )

    value = _pct(curr_ni / curr_rev)
    prev = _pct(prev_ni / prev_rev) if (prev_rev not in (None, 0) and prev_ni is not None) else None
    st = _status(value, prev, higher_is_better=True)

    trend_note = ""
    if prev is not None:
        trend_note = f", {'an improvement on' if value > prev else 'a decline from'} the previous period"

    return RatioResult(
        name="Net Profit Margin", category="Profitability",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"Net profit represents {value:.1f}% of revenue{trend_note}.",
        unit="%", status=st,
        formula="Net Income / Revenue × 100"
    )


def calc_roa(df) -> RatioResult:
    """
    Return on Assets (ROA) = Net Income / Average Total Assets × 100
    Uses average of beginning and ending total assets where two periods exist.
    Falls back to period-end total assets if only one period is available.
    """
    ni = _col("net_income", "net_profit", "profit_after_tax", df=df)
    ta = get_numeric(df, "total_assets")
    curr_ni, prev_ni = latest_and_prev(ni)
    curr_ta, prev_ta = latest_and_prev(ta)

    if curr_ni is None or curr_ta is None:
        missing = []
        if curr_ni is None: missing.append("Net Income")
        if curr_ta is None: missing.append("Total Assets")
        return RatioResult(
            name="Return on Assets (ROA)", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Net Income / Average Total Assets × 100"
        )

    avg_ta = _avg(curr_ta, prev_ta)
    if avg_ta == 0:
        return RatioResult(
            name="Return on Assets (ROA)", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Total Assets is zero — division not possible.",
            formula="Net Income / Average Total Assets × 100"
        )

    value = _pct(curr_ni / avg_ta)
    # Previous period ROA uses prev_ni over avg of (prev_ta, penultimate_ta) — but we only
    # have two data points max, so prev period ROA is computed as prev_ni / prev_ta.
    prev = _pct(prev_ni / prev_ta) if (prev_ni is not None and prev_ta not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=True)

    avg_note = " (Average of beginning/ending assets used.)" if prev_ta is not None else " (Period-end assets used; no prior period available.)"

    return RatioResult(
        name="Return on Assets (ROA)", category="Profitability",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"The company generated {value:.1f}% return on its asset base.{avg_note}",
        unit="%", status=st,
        formula="Net Income / Average Total Assets × 100"
    )


def calc_roe(df) -> RatioResult:
    """
    Return on Equity (ROE) = Net Income / Average Shareholders' Equity × 100
    Uses average equity where two periods exist; period-end otherwise.
    """
    ni = _col("net_income", "net_profit", "profit_after_tax", df=df)
    eq = _col("shareholders_equity", "total_equity", "equity", df=df)
    curr_ni, prev_ni = latest_and_prev(ni)
    curr_eq, prev_eq = latest_and_prev(eq)

    if curr_ni is None or curr_eq is None:
        missing = []
        if curr_ni is None: missing.append("Net Income")
        if curr_eq is None: missing.append("Shareholders' Equity / Total Equity")
        return RatioResult(
            name="Return on Equity (ROE)", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Net Income / Average Shareholders' Equity × 100"
        )

    avg_eq = _avg(curr_eq, prev_eq)
    if avg_eq == 0:
        return RatioResult(
            name="Return on Equity (ROE)", category="Profitability",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Shareholders' Equity is zero — division not possible.",
            formula="Net Income / Average Shareholders' Equity × 100"
        )

    value = _pct(curr_ni / avg_eq)
    prev = _pct(prev_ni / prev_eq) if (prev_ni is not None and prev_eq not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=True)
    avg_note = " (Average equity used.)" if prev_eq is not None else " (Period-end equity used; no prior period available.)"

    return RatioResult(
        name="Return on Equity (ROE)", category="Profitability",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"Shareholders earned {value:.1f}% return on equity.{avg_note}",
        unit="%", status=st,
        formula="Net Income / Average Shareholders' Equity × 100"
    )


# ---------------------------------------------------------------------------
# Solvency / Leverage Ratios
# ---------------------------------------------------------------------------

def calc_debt_to_equity(df) -> RatioResult:
    """
    Debt-to-Equity Ratio = Total Debt / Shareholders' Equity
    Measures financial leverage; lower generally indicates less risk.
    """
    td = _col("total_debt", "total_liabilities", df=df)
    eq = _col("shareholders_equity", "total_equity", "equity", df=df)
    curr_td, prev_td = latest_and_prev(td)
    curr_eq, prev_eq = latest_and_prev(eq)

    if curr_td is None or curr_eq is None:
        missing = []
        if curr_td is None: missing.append("Total Debt / Total Liabilities")
        if curr_eq is None: missing.append("Shareholders' Equity")
        return RatioResult(
            name="Debt-to-Equity Ratio", category="Solvency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Total Debt / Shareholders' Equity"
        )

    if curr_eq == 0:
        return RatioResult(
            name="Debt-to-Equity Ratio", category="Solvency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Shareholders' Equity is zero — division not possible.",
            formula="Total Debt / Shareholders' Equity"
        )

    value = curr_td / curr_eq
    prev = (prev_td / prev_eq) if (prev_td is not None and prev_eq not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=False)  # lower D/E = improving

    # Leverage label based on relative change, not fixed threshold
    if prev is not None:
        change = (value - prev) / abs(prev) * 100 if prev != 0 else 0
        if change > 10:
            leverage = "Higher than previous period"
        elif change < -10:
            leverage = "Lower than previous period"
        else:
            leverage = "Moderate — broadly in line with prior period"
    else:
        leverage = "Moderate"

    return RatioResult(
        name="Debt-to-Equity Ratio", category="Solvency",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"For every unit of equity, {value:.2f} units of debt are used. Leverage: {leverage}.",
        unit="x", status=st,
        formula="Total Debt / Shareholders' Equity"
    )


def calc_debt_ratio(df) -> RatioResult:
    """
    Debt Ratio = Total Liabilities / Total Assets
    Proportion of assets financed by debt.
    """
    tl = _col("total_liabilities", "total_debt", df=df)
    ta = get_numeric(df, "total_assets")
    curr_tl, prev_tl = latest_and_prev(tl)
    curr_ta, prev_ta = latest_and_prev(ta)

    if curr_tl is None or curr_ta is None:
        missing = []
        if curr_tl is None: missing.append("Total Liabilities")
        if curr_ta is None: missing.append("Total Assets")
        return RatioResult(
            name="Debt Ratio", category="Solvency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Total Liabilities / Total Assets"
        )

    if curr_ta == 0:
        return RatioResult(
            name="Debt Ratio", category="Solvency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Total Assets is zero — division not possible.",
            formula="Total Liabilities / Total Assets"
        )

    value = curr_tl / curr_ta
    prev = (prev_tl / prev_ta) if (prev_tl is not None and prev_ta not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=False)

    return RatioResult(
        name="Debt Ratio", category="Solvency",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"{value:.1%} of total assets are financed by liabilities.",
        unit="x", status=st,
        formula="Total Liabilities / Total Assets"
    )


def calc_equity_ratio(df) -> RatioResult:
    """
    Equity Ratio = Shareholders' Equity / Total Assets
    Proportion of assets financed by equity (complement of Debt Ratio).
    """
    eq = _col("shareholders_equity", "total_equity", "equity", df=df)
    ta = get_numeric(df, "total_assets")
    curr_eq, prev_eq = latest_and_prev(eq)
    curr_ta, prev_ta = latest_and_prev(ta)

    if curr_eq is None or curr_ta is None:
        missing = []
        if curr_eq is None: missing.append("Shareholders' Equity")
        if curr_ta is None: missing.append("Total Assets")
        return RatioResult(
            name="Equity Ratio", category="Solvency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Shareholders' Equity / Total Assets"
        )

    if curr_ta == 0:
        return RatioResult(
            name="Equity Ratio", category="Solvency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Total Assets is zero — division not possible.",
            formula="Shareholders' Equity / Total Assets"
        )

    value = curr_eq / curr_ta
    prev = (prev_eq / prev_ta) if (prev_eq is not None and prev_ta not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=True)

    return RatioResult(
        name="Equity Ratio", category="Solvency",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"{value:.1%} of total assets are financed by equity.",
        unit="x", status=st,
        formula="Shareholders' Equity / Total Assets"
    )


def calc_interest_coverage(df) -> RatioResult:
    """
    Interest Coverage Ratio = EBIT / Interest Expense
    Measures how comfortably earnings cover interest payments.
    """
    ebit = _col("ebit", "operating_income", "operating_profit", df=df)
    ie = _col("interest_expense", "interest_expenses", df=df)
    curr_ebit, prev_ebit = latest_and_prev(ebit)
    curr_ie, prev_ie = latest_and_prev(ie)

    if curr_ebit is None or curr_ie is None:
        missing = []
        if curr_ebit is None: missing.append("EBIT / Operating Income")
        if curr_ie is None: missing.append("Interest Expense")
        return RatioResult(
            name="Interest Coverage Ratio", category="Solvency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="EBIT / Interest Expense"
        )

    if curr_ie == 0:
        return RatioResult(
            name="Interest Coverage Ratio", category="Solvency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Interest Expense is zero — no interest obligations to cover.",
            formula="EBIT / Interest Expense"
        )

    value = curr_ebit / curr_ie
    prev = (prev_ebit / prev_ie) if (prev_ebit is not None and prev_ie not in (None, 0)) else None
    st = _status(value, prev, higher_is_better=True)

    return RatioResult(
        name="Interest Coverage Ratio", category="Solvency",
        value=value, prev_value=prev, is_available=True,
        interpretation=f"Earnings cover interest payments {value:.1f}x.",
        unit="x", status=st,
        formula="EBIT / Interest Expense"
    )


# ---------------------------------------------------------------------------
# Efficiency / Activity Ratios
# ---------------------------------------------------------------------------

def calc_inventory_turnover(df) -> RatioResult:
    """
    Inventory Turnover = COGS / Average Inventory
    How many times inventory is sold/replaced per period.
    Uses average inventory where two periods exist.
    """
    cogs = _col("cogs", "cost_of_goods_sold", "cost_of_sales", df=df)
    inv = _col("inventory", "inventories", df=df)
    curr_cogs, _ = latest_and_prev(cogs)
    curr_inv, prev_inv = latest_and_prev(inv)

    if curr_cogs is None or curr_inv is None:
        missing = []
        if curr_cogs is None: missing.append("COGS / Cost of Goods Sold")
        if curr_inv is None: missing.append("Inventory")
        return RatioResult(
            name="Inventory Turnover", category="Efficiency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="COGS / Average Inventory"
        )

    avg_inv = _avg(curr_inv, prev_inv)
    if avg_inv == 0:
        return RatioResult(
            name="Inventory Turnover", category="Efficiency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Average Inventory is zero — division not possible.",
            formula="COGS / Average Inventory"
        )

    value = curr_cogs / avg_inv
    avg_note = " (Average inventory used.)" if prev_inv is not None else " (Period-end inventory; no prior period.)"

    return RatioResult(
        name="Inventory Turnover", category="Efficiency",
        value=value, prev_value=None, is_available=True,
        interpretation=f"Inventory turned over {value:.1f}x during the period.{avg_note}",
        unit="x", status="No prior period",
        formula="COGS / Average Inventory"
    )


def calc_asset_turnover(df) -> RatioResult:
    """
    Asset Turnover = Revenue / Average Total Assets
    How efficiently the company uses its assets to generate revenue.
    """
    rev = _col("revenue", "total_revenue", "sales", df=df)
    ta = get_numeric(df, "total_assets")
    curr_rev, _ = latest_and_prev(rev)
    curr_ta, prev_ta = latest_and_prev(ta)

    if curr_rev is None or curr_ta is None:
        missing = []
        if curr_rev is None: missing.append("Revenue")
        if curr_ta is None: missing.append("Total Assets")
        return RatioResult(
            name="Asset Turnover", category="Efficiency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Revenue / Average Total Assets"
        )

    avg_ta = _avg(curr_ta, prev_ta)
    if avg_ta == 0:
        return RatioResult(
            name="Asset Turnover", category="Efficiency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Average Total Assets is zero.",
            formula="Revenue / Average Total Assets"
        )

    value = curr_rev / avg_ta
    avg_note = " (Average assets used.)" if prev_ta is not None else " (Period-end assets used.)"

    return RatioResult(
        name="Asset Turnover", category="Efficiency",
        value=value, prev_value=None, is_available=True,
        interpretation=f"Each unit of assets generated {value:.2f}x its value in revenue.{avg_note}",
        unit="x", status="No prior period",
        formula="Revenue / Average Total Assets"
    )


def calc_receivables_turnover(df) -> RatioResult:
    """
    Receivables Turnover = Revenue / Average Accounts Receivable
    How quickly the company collects payments from customers.
    """
    rev = _col("revenue", "total_revenue", "sales", df=df)
    ar = _col("accounts_receivable", "receivables", "trade_receivables", df=df)
    curr_rev, _ = latest_and_prev(rev)
    curr_ar, prev_ar = latest_and_prev(ar)

    if curr_rev is None or curr_ar is None:
        missing = []
        if curr_rev is None: missing.append("Revenue")
        if curr_ar is None: missing.append("Accounts Receivable")
        return RatioResult(
            name="Receivables Turnover", category="Efficiency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="Revenue / Average Accounts Receivable"
        )

    avg_ar = _avg(curr_ar, prev_ar)
    if avg_ar == 0:
        return RatioResult(
            name="Receivables Turnover", category="Efficiency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Average Accounts Receivable is zero.",
            formula="Revenue / Average Accounts Receivable"
        )

    value = curr_rev / avg_ar
    return RatioResult(
        name="Receivables Turnover", category="Efficiency",
        value=value, prev_value=None, is_available=True,
        interpretation=f"Receivables were collected {value:.1f}x during the period.",
        unit="x", status="No prior period",
        formula="Revenue / Average Accounts Receivable"
    )


def calc_payables_turnover(df) -> RatioResult:
    """
    Payables Turnover = COGS / Average Accounts Payable
    How quickly the company pays its suppliers.
    """
    cogs = _col("cogs", "cost_of_goods_sold", "cost_of_sales", df=df)
    ap = _col("accounts_payable", "payables", "trade_payables", df=df)
    curr_cogs, _ = latest_and_prev(cogs)
    curr_ap, prev_ap = latest_and_prev(ap)

    if curr_cogs is None or curr_ap is None:
        missing = []
        if curr_cogs is None: missing.append("COGS")
        if curr_ap is None: missing.append("Accounts Payable")
        return RatioResult(
            name="Payables Turnover", category="Efficiency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason=f"{' and '.join(missing)} data is required.",
            formula="COGS / Average Accounts Payable"
        )

    avg_ap = _avg(curr_ap, prev_ap)
    if avg_ap == 0:
        return RatioResult(
            name="Payables Turnover", category="Efficiency",
            value=None, prev_value=None, is_available=False,
            unavailable_reason="Average Accounts Payable is zero.",
            formula="COGS / Average Accounts Payable"
        )

    value = curr_cogs / avg_ap
    return RatioResult(
        name="Payables Turnover", category="Efficiency",
        value=value, prev_value=None, is_available=True,
        interpretation=f"Payables were turned over {value:.1f}x during the period.",
        unit="x", status="No prior period",
        formula="COGS / Average Accounts Payable"
    )


def calc_days(turnover_ratio: Optional[float], label: str, higher_is_better: bool = False) -> Optional[float]:
    """Days = 365 / Turnover Ratio."""
    if turnover_ratio is None or turnover_ratio == 0:
        return None
    return 365 / turnover_ratio


def calc_cash_conversion_cycle(inv_days, rec_days, pay_days) -> Optional[float]:
    """
    Cash Conversion Cycle = Inventory Days + Receivable Days - Payable Days
    Measures net days cash is tied up in operations.
    """
    if inv_days is None or rec_days is None or pay_days is None:
        return None
    return inv_days + rec_days - pay_days


# ---------------------------------------------------------------------------
# Master runner
# ---------------------------------------------------------------------------

def run_all_ratios(df) -> dict:
    """
    Run every ratio calculator against the DataFrame.
    Returns a dict with keys: liquidity, profitability, solvency, efficiency,
    each containing a list of RatioResult objects.
    """
    # Liquidity
    liquidity = [
        calc_current_ratio(df),
        calc_quick_ratio(df),
        calc_cash_ratio(df),
    ]

    # Profitability
    profitability = [
        calc_gross_profit_margin(df),
        calc_operating_profit_margin(df),
        calc_net_profit_margin(df),
        calc_roa(df),
        calc_roe(df),
    ]

    # Solvency
    solvency = [
        calc_debt_to_equity(df),
        calc_debt_ratio(df),
        calc_equity_ratio(df),
        calc_interest_coverage(df),
    ]

    # Efficiency — days and CCC depend on turnover values
    inv_turn = calc_inventory_turnover(df)
    asset_turn = calc_asset_turnover(df)
    rec_turn = calc_receivables_turnover(df)
    pay_turn = calc_payables_turnover(df)

    inv_days_val = calc_days(inv_turn.value, "Inventory Days")
    rec_days_val = calc_days(rec_turn.value, "Receivable Days")
    pay_days_val = calc_days(pay_turn.value, "Payable Days")
    ccc_val = calc_cash_conversion_cycle(inv_days_val, rec_days_val, pay_days_val)

    def _days_result(name, val, reason_base):
        if val is None:
            return RatioResult(
                name=name, category="Efficiency",
                value=None, prev_value=None, is_available=False,
                unavailable_reason=f"{reason_base} data is required to compute this.",
                formula=f"365 / {reason_base} Turnover"
            )
        return RatioResult(
            name=name, category="Efficiency",
            value=val, prev_value=None, is_available=True,
            interpretation=f"On average {val:.1f} days per cycle.",
            unit="days", status="No prior period",
            formula=f"365 / {reason_base} Turnover"
        )

    ccc_result = RatioResult(
        name="Cash Conversion Cycle", category="Efficiency",
        value=ccc_val, prev_value=None,
        is_available=ccc_val is not None,
        unavailable_reason="" if ccc_val is not None else
            "Inventory Days, Receivable Days, and Payable Days are all required.",
        interpretation=f"Net {ccc_val:.1f} days of cash tied up in operations." if ccc_val is not None else "",
        unit="days", status="No prior period",
        formula="Inventory Days + Receivable Days − Payable Days"
    )

    efficiency = [
        inv_turn, asset_turn, rec_turn, pay_turn,
        _days_result("Inventory Days", inv_days_val, "Inventory"),
        _days_result("Receivable Days", rec_days_val, "Receivable"),
        _days_result("Payable Days", pay_days_val, "Payable"),
        ccc_result,
    ]

    return {
        "liquidity": liquidity,
        "profitability": profitability,
        "solvency": solvency,
        "efficiency": efficiency,
    }
