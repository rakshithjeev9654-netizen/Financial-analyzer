"""
modules/ai_analysis.py
======================
Smart rule-based financial commentary — no OpenAI API key required.
Produces detailed, ratio-aware narrative analysis from the calculated data.
"""

import json


def _json_payload(company_name, period, ratios, health, ml):
    return json.dumps({
        "company": company_name, "period": period, "health_score": health,
        "ml_risk": ml, "ratios": ratios
    }, default=str)[:18000]


def _get_ratio(ratios, category, name):
    """Safely fetch a ratio dict by category and name."""
    for r in ratios.get(category, []):
        if r.get("name") == name and r.get("is_available"):
            return r
    return None


def _val(ratios, category, name):
    r = _get_ratio(ratios, category, name)
    return r["value"] if r else None


def generate_rule_based_analysis(ratios, health, ml):
    """
    Works with both RatioResult objects (called before serialisation)
    and plain dicts (called after). Returns {"summary": str, "insights": [str]}.
    """
    insights = []

    # Normalise: support both RatioResult objects and dicts
    def is_avail(r):
        return r.is_available if hasattr(r, "is_available") else r.get("is_available", False)

    def rval(r):
        return r.value if hasattr(r, "value") else r.get("value")

    def rname(r):
        return r.name if hasattr(r, "name") else r.get("name", "")

    for cat, items in ratios.items():
        for r in items:
            if not is_avail(r):
                continue
            v = rval(r)
            n = rname(r)
            if v is None:
                continue
            if n == "Current Ratio" and v < 1:
                insights.append("⚠️ Liquidity is tight — Current Ratio below 1.0x means current liabilities exceed current assets.")
            if n == "Quick Ratio" and v < 0.8:
                insights.append("⚠️ Quick Ratio is low — the company may struggle to meet short-term obligations without selling inventory.")
            if n == "Net Profit Margin" and v < 0:
                insights.append("⚠️ The company is reporting a net loss this period.")
            if n == "Net Profit Margin" and v >= 15:
                insights.append(f"✅ Strong Net Profit Margin of {v:.1f}% — well above typical thresholds.")
            if n == "Gross Profit Margin" and v >= 40:
                insights.append(f"✅ High Gross Profit Margin ({v:.1f}%) indicates strong pricing power or low production costs.")
            if n == "Gross Profit Margin" and v < 20:
                insights.append(f"⚠️ Gross Profit Margin is slim at {v:.1f}% — monitor cost of goods sold closely.")
            if n == "Debt-to-Equity Ratio" and v > 2:
                insights.append(f"⚠️ High leverage — Debt-to-Equity of {v:.2f}x increases financial risk.")
            if n == "Debt-to-Equity Ratio" and v <= 0.5:
                insights.append(f"✅ Conservative leverage — Debt-to-Equity of {v:.2f}x signals a strong balance sheet.")
            if n == "Interest Coverage Ratio" and v < 1.5:
                insights.append("⚠️ Interest Coverage is weak — earnings barely cover interest obligations.")
            if n == "Interest Coverage Ratio" and v >= 8:
                insights.append(f"✅ Excellent Interest Coverage of {v:.1f}x — the company comfortably services its debt.")
            if n == "Return on Equity (ROE)" and v >= 20:
                insights.append(f"✅ Strong ROE of {v:.1f}% — shareholders are getting good returns on their equity.")
            if n == "Return on Equity (ROE)" and v < 5:
                insights.append(f"⚠️ Low ROE of {v:.1f}% — equity is not generating sufficient returns.")
            if n == "Return on Assets (ROA)" and v >= 15:
                insights.append(f"✅ High ROA of {v:.1f}% — assets are being used very efficiently.")
            if n == "Cash Conversion Cycle" and v > 90:
                insights.append(f"⚠️ Cash Conversion Cycle of {v:.0f} days is high — cash is tied up in operations for a long time.")
            if n == "Cash Conversion Cycle" and v < 30:
                insights.append(f"✅ Efficient Cash Conversion Cycle of {v:.0f} days — cash flows back quickly.")
            if n == "Inventory Turnover" and v > 10:
                insights.append(f"✅ High Inventory Turnover of {v:.1f}x — stock is moving quickly with minimal holding costs.")

    if ml.get("flagged_ratios"):
        flagged = ", ".join(ml["flagged_ratios"])
        insights.append(f"🔍 ML anomaly screen flagged unusual values for: {flagged}. Review these ratios carefully.")

    if not insights:
        insights.append("✅ No major warnings triggered — all monitored ratios are within normal ranges.")

    return {"summary": " | ".join(insights), "insights": insights}


def generate_detailed_commentary(company_name, period, ratios, health, ml):
    """
    Produces a full multi-section text commentary — replaces GenAI output.
    Covers: overview, liquidity, profitability, solvency, efficiency, risk, recommendations.
    """
    lines = []
    score = health.get("score", 0) if isinstance(health, dict) else health
    label = health.get("label", "") if isinstance(health, dict) else ""

    def v(cat, name):
        return _val(ratios, cat, name)

    # ── Overview ────────────────────────────────────────────────────────
    lines.append(f"FINANCIAL ANALYSIS REPORT")
    lines.append(f"Company: {company_name}  |  Period: {period}")
    lines.append(f"Overall Health Score: {score}/100 — {label}")
    lines.append("")

    # ── Liquidity ───────────────────────────────────────────────────────
    cr  = v("liquidity", "Current Ratio")
    qr  = v("liquidity", "Quick Ratio")
    csr = v("liquidity", "Cash Ratio")
    lines.append("── LIQUIDITY ──")
    if cr is not None:
        if cr >= 2:
            lines.append(f"• Current Ratio of {cr:.2f}x is strong — short-term obligations are well covered.")
        elif cr >= 1:
            lines.append(f"• Current Ratio of {cr:.2f}x is adequate but leaves limited buffer.")
        else:
            lines.append(f"• Current Ratio of {cr:.2f}x is below 1 — immediate liquidity risk. Consider improving working capital.")
    if qr is not None:
        lines.append(f"• Quick Ratio: {qr:.2f}x {'— liquid assets comfortably cover short-term liabilities.' if qr >= 1 else '— excluding inventory, liquidity is tight.'}")
    if csr is not None:
        lines.append(f"• Cash Ratio: {csr:.2f}x — {'strong' if csr >= 0.5 else 'limited'} immediate cash coverage.")
    lines.append("")

    # ── Profitability ───────────────────────────────────────────────────
    npm = v("profitability", "Net Profit Margin")
    gpm = v("profitability", "Gross Profit Margin")
    opm = v("profitability", "Operating Profit Margin")
    roe = v("profitability", "Return on Equity (ROE)")
    roa = v("profitability", "Return on Assets (ROA)")
    lines.append("── PROFITABILITY ──")
    if gpm is not None:
        lines.append(f"• Gross Profit Margin: {gpm:.1f}% — {'strong pricing power.' if gpm >= 40 else 'moderate margin, watch cost of sales.' if gpm >= 20 else 'thin margin — cost control is critical.'}")
    if opm is not None:
        lines.append(f"• Operating Profit Margin: {opm:.1f}% — {'efficient operations.' if opm >= 15 else 'moderate operating efficiency.' if opm >= 8 else 'low — review operating cost structure.'}")
    if npm is not None:
        lines.append(f"• Net Profit Margin: {npm:.1f}% — {'excellent bottom-line profitability.' if npm >= 15 else 'healthy.' if npm >= 8 else 'low — check interest, tax, and other below-the-line costs.' if npm >= 0 else 'company is loss-making this period.'}")
    if roe is not None:
        lines.append(f"• Return on Equity: {roe:.1f}% — {'excellent shareholder returns.' if roe >= 20 else 'decent returns.' if roe >= 10 else 'low returns on equity — consider capital efficiency improvements.'}")
    if roa is not None:
        lines.append(f"• Return on Assets: {roa:.1f}% — {'assets are highly productive.' if roa >= 15 else 'moderate asset utilisation.' if roa >= 8 else 'assets are underperforming — review asset deployment strategy.'}")
    lines.append("")

    # ── Solvency ─────────────────────────────────────────────────────────
    dte = v("solvency", "Debt-to-Equity Ratio")
    dr  = v("solvency", "Debt Ratio")
    ic  = v("solvency", "Interest Coverage Ratio")
    lines.append("── SOLVENCY & LEVERAGE ──")
    if dte is not None:
        lines.append(f"• Debt-to-Equity: {dte:.2f}x — {'conservative leverage.' if dte <= 0.5 else 'moderate leverage.' if dte <= 1.5 else 'high leverage — monitor debt servicing capacity.'}")
    if dr is not None:
        lines.append(f"• Debt Ratio: {dr:.2f}x — {dr*100:.0f}% of assets are debt-financed.")
    if ic is not None:
        lines.append(f"• Interest Coverage: {ic:.1f}x — {'very comfortable debt servicing.' if ic >= 5 else 'adequate coverage.' if ic >= 2 else 'weak — earnings barely cover interest payments.'}")
    lines.append("")

    # ── Efficiency ───────────────────────────────────────────────────────
    it  = v("efficiency", "Inventory Turnover")
    at  = v("efficiency", "Asset Turnover")
    ccc = v("efficiency", "Cash Conversion Cycle")
    rd  = v("efficiency", "Receivable Days")
    pd  = v("efficiency", "Payable Days")
    lines.append("── EFFICIENCY ──")
    if it is not None:
        lines.append(f"• Inventory Turnover: {it:.1f}x — {'fast-moving stock.' if it >= 8 else 'moderate inventory management.' if it >= 4 else 'slow inventory movement — risk of obsolescence.'}")
    if at is not None:
        lines.append(f"• Asset Turnover: {at:.2f}x — each unit of assets generates {at:.2f}x in revenue.")
    if rd is not None:
        lines.append(f"• Receivable Days: {rd:.0f} days — {'fast collections.' if rd <= 30 else 'acceptable.' if rd <= 60 else 'slow collections — review credit policy.'}")
    if pd is not None:
        lines.append(f"• Payable Days: {pd:.0f} days — {'good supplier payment terms.' if pd >= 30 else 'paying suppliers quickly.'}")
    if ccc is not None:
        lines.append(f"• Cash Conversion Cycle: {ccc:.0f} days — {'efficient cash cycle.' if ccc <= 45 else 'moderate.' if ccc <= 90 else 'long cash cycle — cash tied up in operations.'}")
    lines.append("")

    # ── ML Risk ──────────────────────────────────────────────────────────
    lines.append("── ML ANOMALY SCREEN ──")
    lines.append(f"• Model: {ml.get('model', 'Isolation Forest')}")
    lines.append(f"• Status: {ml.get('status', 'N/A')}")
    if ml.get("flagged_ratios"):
        lines.append(f"• Flagged: {', '.join(ml['flagged_ratios'])}")
        lines.append("  These ratios show unusual combinations compared to the overall dataset. Investigate further.")
    else:
        lines.append("• No anomalies flagged — ratio values are consistent with each other.")
    lines.append("")

    # ── Recommendations ──────────────────────────────────────────────────
    lines.append("── RECOMMENDATIONS ──")
    rec_n = 1
    if cr is not None and cr < 1.2:
        lines.append(f"{rec_n}. Improve working capital — consider faster receivables collection or renegotiating payables terms.")
        rec_n += 1
    if npm is not None and npm < 5:
        lines.append(f"{rec_n}. Review cost structure — low net margin suggests room to reduce expenses or improve pricing.")
        rec_n += 1
    if dte is not None and dte > 1.5:
        lines.append(f"{rec_n}. Reduce debt exposure — high leverage increases vulnerability to interest rate changes.")
        rec_n += 1
    if ccc is not None and ccc > 60:
        lines.append(f"{rec_n}. Shorten the cash conversion cycle — faster inventory turnover and receivables collection will free up cash.")
        rec_n += 1
    if rec_n == 1:
        lines.append("1. Maintain current performance — key ratios are healthy.")
        lines.append("2. Continue monitoring liquidity and leverage as the business grows.")
    lines.append("")
    lines.append("Note: This is an automated analytical report for educational purposes only.")
    lines.append("It is not financial advice or an investment recommendation.")

    return "\n".join(lines)


def answer_financial_question(question, company_name, period, ratios, health, ml):
    """Rule-based Q&A — answers common financial questions from the ratio data."""
    q = question.lower()
    score = health.get("score", 0) if isinstance(health, dict) else health

    def v(cat, name):
        return _val(ratios, cat, name)

    # Liquidity questions
    if any(w in q for w in ["liquid", "current ratio", "short term", "short-term", "pay bills"]):
        cr = v("liquidity", "Current Ratio")
        qr = v("liquidity", "Quick Ratio")
        parts = []
        if cr: parts.append(f"Current Ratio is {cr:.2f}x ({'healthy' if cr >= 1.5 else 'tight' if cr >= 1 else 'concerning'}).")
        if qr: parts.append(f"Quick Ratio is {qr:.2f}x.")
        return " ".join(parts) or "Liquidity data not available."

    # Profitability questions
    if any(w in q for w in ["profit", "margin", "earning", "roe", "roa", "return"]):
        npm = v("profitability", "Net Profit Margin")
        roe = v("profitability", "Return on Equity (ROE)")
        roa = v("profitability", "Return on Assets (ROA)")
        parts = []
        if npm is not None: parts.append(f"Net Profit Margin: {npm:.1f}%.")
        if roe is not None: parts.append(f"Return on Equity: {roe:.1f}%.")
        if roa is not None: parts.append(f"Return on Assets: {roa:.1f}%.")
        return " ".join(parts) or "Profitability data not available."

    # Debt / solvency questions
    if any(w in q for w in ["debt", "leverage", "solvency", "loan", "borrow", "interest"]):
        dte = v("solvency", "Debt-to-Equity Ratio")
        ic  = v("solvency", "Interest Coverage Ratio")
        parts = []
        if dte is not None: parts.append(f"Debt-to-Equity: {dte:.2f}x ({'low leverage' if dte <= 1 else 'moderate' if dte <= 2 else 'high leverage'}).")
        if ic  is not None: parts.append(f"Interest Coverage: {ic:.1f}x ({'strong' if ic >= 3 else 'weak'}).")
        return " ".join(parts) or "Solvency data not available."

    # Efficiency questions
    if any(w in q for w in ["efficien", "turnover", "inventory", "receivable", "cash cycle", "collection"]):
        it  = v("efficiency", "Inventory Turnover")
        ccc = v("efficiency", "Cash Conversion Cycle")
        rd  = v("efficiency", "Receivable Days")
        parts = []
        if it  is not None: parts.append(f"Inventory Turnover: {it:.1f}x.")
        if rd  is not None: parts.append(f"Receivable Days: {rd:.0f} days.")
        if ccc is not None: parts.append(f"Cash Conversion Cycle: {ccc:.0f} days.")
        return " ".join(parts) or "Efficiency data not available."

    # Health / overall questions
    if any(w in q for w in ["health", "overall", "summary", "how is", "performance", "risk"]):
        return generate_detailed_commentary(company_name, period, ratios, health, ml)

    # Fallback
    return (
        f"{company_name} ({period}) — Health Score: {score}/100. "
        "Ask about liquidity, profitability, debt, efficiency, or overall performance for a detailed answer."
    )
