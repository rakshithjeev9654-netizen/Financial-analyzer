# 📊 Financial Report Analyzer

An AI-powered financial analysis web application built with Python and Flask.  
Upload a financial report (CSV, Excel, or PDF) and instantly get ratio analysis, health scoring, ML-based risk detection, and smart commentary — **no API key required**.

---

## 🚀 Features

| Feature | Description |
|---|---|
| 📂 **File Upload** | Supports CSV, XLSX, XLS, and PDF formats |
| 🔍 **Smart Extraction** | Auto-detects layout (wide/transposed) and maps 14 standard financial fields |
| ✏️ **Review & Remap** | Review extracted fields, remap columns, or override values manually before analysis |
| 📐 **20+ Financial Ratios** | Liquidity, Profitability, Solvency, and Efficiency ratios with interpretations |
| ❤️ **Health Score** | Analytical 0–100 score based on key ratio combinations |
| 🤖 **ML Anomaly Detection** | Unsupervised Isolation Forest model flags unusual ratio combinations |
| 📊 **SVG Charts** | Pure Python-generated vertical bar charts and donut gauge — no JavaScript |
| 💬 **Rule-based AI Commentary** | Detailed section-by-section analysis and Q&A without any API key |
| 🕓 **Session History** | View and reload all analyses done in the current session |
| 🖨️ **PDF Export** | Print-optimised layout via browser Ctrl+P → Save as PDF |

---

## 📁 Project Structure

```
Financial-analyzer/
├── app.py                  # Flask application & all routes
├── modules/
│   ├── parser.py           # CSV / Excel / PDF file parser
│   ├── extractor.py        # Smart field extraction engine
│   ├── ratios.py           # 20+ ratio calculators
│   ├── health_score.py     # 0–100 financial health score
│   ├── ml_risk.py          # Isolation Forest anomaly detection
│   ├── ai_analysis.py      # Rule-based commentary & Q&A
│   └── charts.py           # Pure Python SVG chart generator
├── templates/
│   ├── base.html           # Base layout with navbar
│   ├── upload.html         # File upload page
│   ├── review.html         # Field mapping review page
│   ├── dashboard.html      # Analysis dashboard
│   ├── history.html        # Session history
│   └── error.html          # Error page
├── static/
│   ├── css/style.css       # Full stylesheet
│   └── financial_template.xlsx  # Downloadable Excel template
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
└── README.md
```

---

## ⚙️ Setup & Run

### 1. Clone the repository
```bash
git clone https://github.com/rakshithjeev9654-netizen/Financial-analyzer.git
cd Financial-analyzer
```

### 2. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac / Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
```
Edit `.env` and set a secret key:
```
SECRET_KEY=your-random-secret-key
```

### 5. Run the app
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

---

## 📊 Supported Financial Fields

| Category | Fields |
|---|---|
| **Income Statement** | Revenue, COGS, Operating Income, Net Income, Interest Expense |
| **Balance Sheet** | Total Assets, Total Liabilities, Shareholders Equity, Current Assets, Current Liabilities, Inventory, Cash |
| **Working Capital** | Accounts Receivable, Accounts Payable |

---

## 📐 Ratios Calculated

**Liquidity** — Current Ratio, Quick Ratio, Cash Ratio  
**Profitability** — Gross/Operating/Net Profit Margin, ROA, ROE  
**Solvency** — Debt-to-Equity, Debt Ratio, Equity Ratio, Interest Coverage  
**Efficiency** — Inventory/Asset/Receivables/Payables Turnover, Days metrics, Cash Conversion Cycle  

---

## 🛠️ Tech Stack

- **Backend** — Python 3.11, Flask
- **Data** — Pandas, NumPy
- **ML** — Scikit-learn (Isolation Forest)
- **File Parsing** — OpenPyXL, pdfplumber
- **Charts** — Pure Python SVG (no JavaScript charting library)
- **Frontend** — HTML, CSS (no JavaScript frameworks)

---

## 📌 Notes

- Analysis history is session-based and resets when the server restarts
- The AI commentary is fully rule-based — no OpenAI API key or internet connection required
- This project is for **educational purposes only** — not financial advice

---

## 👨‍💻 Author

**Rakshith J**  
Internship Project — Financial Data Analysis with AI/ML  
