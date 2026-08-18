
import os
import json
import uuid
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import pandas as pd

from modules.parser import parse_file
from modules.extractor import extract_fields, build_normalized_df, clean_number, STANDARD_FIELDS, ExtractionResult
from modules.ratios import run_all_ratios
from modules.health_score import calculate_health_score
from modules.ai_analysis import generate_rule_based_analysis, generate_detailed_commentary, answer_financial_question
from modules.ml_risk import detect_ratio_anomalies
from modules.charts import build_charts

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", "uploads"))
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "pdf"}
_analysis_store = {}

FIELD_DISPLAY = {
    "revenue": ("Revenue", "Income Statement"),
    "cogs": ("Cost of Goods Sold", "Income Statement"),
    "operating_income": ("Operating Income", "Income Statement"),
    "net_income": ("Net Income", "Income Statement"),
    "current_assets": ("Current Assets", "Balance Sheet"),
    "current_liabilities": ("Current Liabilities", "Balance Sheet"),
    "inventory": ("Inventory", "Balance Sheet"),
    "cash": ("Cash & Equivalents", "Balance Sheet"),
    "total_assets": ("Total Assets", "Balance Sheet"),
    "total_liabilities": ("Total Liabilities", "Balance Sheet"),
    "shareholders_equity": ("Shareholders' Equity", "Balance Sheet"),
    "accounts_receivable": ("Accounts Receivable", "Working Capital"),
    "accounts_payable": ("Accounts Payable", "Working Capital"),
    "interest_expense": ("Interest Expense", "Income Statement"),
}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def _serialise_extraction(extraction):
    fields_out = {}
    for field_name, fe in extraction.fields.items():
        fields_out[field_name] = {
            "value": fe.value,
            "raw_label": fe.raw_label,
            "confidence": fe.confidence,
            "period_values": fe.period_values,
            "scale": fe.scale,
            "reason": fe.reason,
        }
    return {
        "fields": fields_out,
        "layout": extraction.layout,
        "periods": extraction.periods,
        "warnings": extraction.warnings,
        "unmatched_labels": extraction.unmatched_labels,
    }

def _ratio_list_to_dict(results):
    out = []
    for r in results:
        out.append({
            "name": r.name, "category": r.category, "value": r.value, "prev_value": r.prev_value,
            "is_available": r.is_available, "unavailable_reason": r.unavailable_reason,
            "interpretation": r.interpretation, "unit": r.unit, "formula": r.formula,
            "status": r.status, "formatted_value": r.formatted_value,
            "formatted_prev": r.formatted_prev, "formatted_change": r.formatted_change,
            "change_pct": r.change_pct,
        })
    return out

def _run_analysis_and_store(analysis_id, norm_df, company_name, period, parse_warnings):
    ratios = run_all_ratios(norm_df)
    health_float = calculate_health_score(ratios)
    from modules.health_score import get_health_label
    health = {"score": health_float, "label": get_health_label(health_float)}
    ml = detect_ratio_anomalies(ratios)
    # generate_rule_based_analysis expects RatioResult objects — call it before serialising
    rule_analysis = generate_rule_based_analysis(ratios, health, ml)
    ratios_dict = {cat: _ratio_list_to_dict(lst) for cat, lst in ratios.items()}
    _analysis_store[analysis_id].update({
        "company_name": company_name,
        "period": period,
        "parse_warnings": parse_warnings,
        "ratios": ratios_dict,
        "analysis": rule_analysis,
        "health_score": health,
        "ml_risk": ml,
        "norm_records": norm_df.to_dict(orient="records"),
        "ready": True,
        "genai": None,
    })

@app.route("/")
def index():
    return render_template("upload.html")

@app.route("/download-template")
def download_template():
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    template_path = os.path.join(static_dir, "financial_template.xlsx")
    if not os.path.exists(template_path):
        from create_template import make_template
        make_template()
    return send_from_directory(static_dir, "financial_template.xlsx", as_attachment=True, download_name="Financial_Analyzer_Template.xlsx")

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("index"))
    file = request.files["file"]
    company_name = request.form.get("company_name", "").strip() or "Unknown Company"
    period = request.form.get("period", "").strip() or "Current Period"
    if not file.filename or not allowed_file(file.filename):
        flash("Supported formats: CSV, XLSX, XLS, PDF.", "error")
        return redirect(url_for("index"))
    filename = secure_filename(file.filename)
    filepath = UPLOAD_FOLDER / f"{uuid.uuid4().hex}_{filename}"
    file.save(filepath)
    try:
        df, warnings = parse_file(str(filepath))
        extraction = extract_fields(df)
    except Exception as exc:
        flash(f"Could not process file: {exc}", "error")
        return redirect(url_for("index"))

    analysis_id = str(uuid.uuid4())
    _analysis_store[analysis_id] = {
        "company_name": company_name, "period": period, "parse_warnings": warnings,
        "extraction": _serialise_extraction(extraction),
        "raw_records": df.to_dict(orient="list"),
        "raw_columns": list(df.columns), "ready": False
    }
    session["analysis_id"] = analysis_id
    return redirect(url_for("review"))

@app.route("/review")
def review():
    analysis_id = session.get("analysis_id")
    if not analysis_id or analysis_id not in _analysis_store:
        flash("Please upload a file first.", "info")
        return redirect(url_for("index"))
    data = _analysis_store[analysis_id]
    ext = data["extraction"]
    fields = []
    for field_name in STANDARD_FIELDS:
        fe = ext["fields"][field_name]
        display_name, category = FIELD_DISPLAY[field_name]
        conf = fe["confidence"]
        fields.append({
            "field": field_name, "display_name": display_name, "category": category,
            "raw_label": fe["raw_label"], "value": fe["value"], "confidence": conf,
            "conf_class": "high" if conf >= .85 else "medium" if conf >= .60 else "low",
            "period_values": fe["period_values"], "reason": fe["reason"]
        })
    return render_template(
        "review.html", analysis_id=analysis_id, company_name=data["company_name"], period=data["period"],
        layout=ext["layout"], periods=ext["periods"], warnings=ext["warnings"] + data.get("parse_warnings", []),
        fields=fields, found_count=sum(1 for f in fields if f["value"] is not None),
        all_columns=data["raw_columns"], unmatched=ext["unmatched_labels"]
    )

@app.route("/confirm-mapping", methods=["POST"])
def confirm_mapping():
    analysis_id = request.form.get("analysis_id") or session.get("analysis_id")
    if not analysis_id or analysis_id not in _analysis_store:
        flash("Session expired. Please re-upload.", "error")
        return redirect(url_for("index"))
    data = _analysis_store[analysis_id]
    ext = data["extraction"]
    raw_df = pd.DataFrame(data["raw_records"])

    # Build a single-row dict of {field: value} for the normalized DataFrame
    row = {"period": data["period"]}
    for field_name in STANDARD_FIELDS:
        override = request.form.get(f"override_{field_name}", "").strip()
        choice = request.form.get(f"map_{field_name}", "__keep__")

        if override:
            val = clean_number(override)
            row[field_name] = val
            continue

        if choice == "__skip__":
            row[field_name] = None
        elif choice not in ("__keep__", "__skip__") and choice in raw_df.columns:
            # Use the latest non-null numeric value from the remapped column
            series = raw_df[choice].dropna()
            numeric_vals = [clean_number(v) for v in series]
            numeric_vals = [v for v in numeric_vals if v is not None]
            row[field_name] = numeric_vals[-1] if numeric_vals else None
        else:
            # Keep detected: use the extracted value
            row[field_name] = ext["fields"][field_name]["value"]

    norm_df = pd.DataFrame([row])
    _run_analysis_and_store(
        analysis_id, norm_df, data["company_name"], data["period"], data.get("parse_warnings", [])
    )
    session["analysis_id"] = analysis_id
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    analysis_id = session.get("analysis_id")
    if not analysis_id or analysis_id not in _analysis_store:
        return redirect(url_for("index"))
    data = _analysis_store[analysis_id]
    if not data.get("ready"):
        return redirect(url_for("review"))
    ratios = data["ratios"]
    kpis = []
    for cat, name in [
        ("profitability", "Net Profit Margin"),
        ("liquidity", "Current Ratio"),
        ("solvency", "Debt-to-Equity Ratio"),
        ("profitability", "Return on Equity (ROE)"),
    ]:
        r = next((x for x in ratios.get(cat, []) if x["name"] == name), None)
        if r and r["is_available"]:
            kpis.append(r)
    charts = build_charts(ratios, data["health_score"])
    return render_template(
        "dashboard.html",
        company_name=data["company_name"], period=data["period"],
        parse_warnings=data.get("parse_warnings", []), ratios=ratios, analysis=data["analysis"],
        kpis=kpis, health_score=data["health_score"], ml_risk=data["ml_risk"],
        genai=data.get("genai"), charts=charts,
    )

@app.route("/generate-ai", methods=["POST"])
def generate_ai():
    analysis_id = session.get("analysis_id")
    if not analysis_id or analysis_id not in _analysis_store or not _analysis_store[analysis_id].get("ready"):
        return redirect(url_for("index"))
    data = _analysis_store[analysis_id]
    text = generate_detailed_commentary(
        data["company_name"], data["period"],
        data["ratios"], data["health_score"], data["ml_risk"]
    )
    data["genai"] = {"status": "success", "text": text}
    return redirect(url_for("dashboard"))

@app.route("/ask-ai", methods=["POST"])
def ask_ai():
    analysis_id = session.get("analysis_id")
    if not analysis_id or analysis_id not in _analysis_store or not _analysis_store[analysis_id].get("ready"):
        return redirect(url_for("index"))
    q = request.form.get("question", "").strip()
    data = _analysis_store[analysis_id]
    if q:
        ans = answer_financial_question(
            q, data["company_name"], data["period"],
            data["ratios"], data["health_score"], data["ml_risk"]
        )
        data["genai"] = {"status": "success", "text": ans, "question": q}
    return redirect(url_for("dashboard"))

@app.route("/history")
def history():
    current_id = session.get("analysis_id")
    analyses = []
    for aid, d in _analysis_store.items():
        if not d.get("ready"):
            continue
        hs = d.get("health_score", {})
        analyses.append({
            "id":           aid,
            "company_name": d["company_name"],
            "period":       d["period"],
            "is_current":   aid == current_id,
            "health_score": hs.get("score") if isinstance(hs, dict) else hs,
        })
    return render_template("history.html", analyses=analyses)

@app.route("/load/<analysis_id>")
def load_analysis(analysis_id):
    if analysis_id not in _analysis_store:
        flash("Analysis not found.", "error")
        return redirect(url_for("history"))
    session["analysis_id"] = analysis_id
    return redirect(url_for("dashboard"))

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    import traceback
    tb = traceback.format_exc()
    traceback.print_exc()
    return f"<html><body><pre style='white-space:pre-wrap;word-break:break-all'>{tb}</pre></body></html>", 500

# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
