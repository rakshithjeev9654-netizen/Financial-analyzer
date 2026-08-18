"""
modules/charts.py
=================
Pure-Python SVG chart generators — no JavaScript, no external libraries.
Vertical (column) bar charts + donut health gauge.
"""

from __future__ import annotations
import math

# Short labels for chart x-axis
SHORT_LABELS = {
    "Current Ratio":              "Curr Ratio",
    "Quick Ratio":                "Quick",
    "Cash Ratio":                 "Cash",
    "Gross Profit Margin":        "GP Margin",
    "Operating Profit Margin":    "Op Margin",
    "Net Profit Margin":          "Net Margin",
    "Return on Assets (ROA)":     "ROA",
    "Return on Equity (ROE)":     "ROE",
    "Debt-to-Equity Ratio":       "D/E",
    "Debt Ratio":                 "Debt Ratio",
    "Equity Ratio":               "Eq Ratio",
    "Interest Coverage Ratio":    "Int Cover",
    "Inventory Turnover":         "Inv Turn",
    "Asset Turnover":             "Asset Turn",
    "Receivables Turnover":       "Rec Turn",
    "Payables Turnover":          "Pay Turn",
    "Inventory Days":             "Inv Days",
    "Receivable Days":            "Rec Days",
    "Payable Days":               "Pay Days",
    "Cash Conversion Cycle":      "CCC",
}

def _short(name: str) -> str:
    return SHORT_LABELS.get(name, name[:10])


COLORS = {
    "liquidity":     "#1a56db",
    "profitability": "#059669",
    "solvency":      "#7c3aed",
    "efficiency":    "#0891b2",
}

HEALTH_COLORS = [
    (80, "#059669"),
    (60, "#d97706"),
    (40, "#e11d48"),
    (0,  "#9f1239"),
]

TINTS = {
    "liquidity":     "#dbeafe",
    "profitability": "#dcfce7",
    "solvency":      "#ede9fe",
    "efficiency":    "#cffafe",
}


def _esc(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _health_color(score: float) -> str:
    for threshold, color in HEALTH_COLORS:
        if score >= threshold:
            return color
    return "#9f1239"


# ── Donut ─────────────────────────────────────────────────────────────────

def donut_chart(score: float, label: str, size: int = 190) -> str:
    score  = max(0.0, min(100.0, float(score)))
    cx, cy = size // 2, size // 2
    r      = size // 2 - 24
    stroke = 16
    color  = _health_color(score)
    frac   = score / 100.0
    angle  = frac * 2 * math.pi
    sx     = cx + r * math.cos(-math.pi / 2)
    sy     = cy + r * math.sin(-math.pi / 2)
    ex     = cx + r * math.cos(-math.pi / 2 + angle)
    ey     = cy + r * math.sin(-math.pi / 2 + angle)
    large  = 1 if frac > 0.5 else 0
    bg     = f"M {sx:.2f} {sy:.2f} A {r} {r} 0 1 1 {sx-.001:.2f} {sy:.2f}"
    arc    = (f"M {sx:.2f} {sy:.2f} A {r} {r} 0 {large} 1 {ex:.2f} {ey:.2f}"
              if frac > 0 else "")

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" style="display:block;margin:0 auto;">'
        f'<path d="{_esc(bg)}" fill="none" stroke="#e2e8f0" stroke-width="{stroke}"/>'
    )
    if arc:
        svg += (f'<path d="{_esc(arc)}" fill="none" stroke="{color}" '
                f'stroke-width="{stroke}" stroke-linecap="round"/>')
    svg += (
        f'<text x="{cx}" y="{cy-4}" text-anchor="middle" '
        f'font-family="-apple-system,Segoe UI,sans-serif" font-size="30" '
        f'font-weight="900" fill="{color}">{int(score)}</text>'
        f'<text x="{cx}" y="{cy+16}" text-anchor="middle" '
        f'font-family="-apple-system,Segoe UI,sans-serif" font-size="11" fill="#94a3b8">/100</text>'
        f'<text x="{cx}" y="{cy+32}" text-anchor="middle" '
        f'font-family="-apple-system,Segoe UI,sans-serif" font-size="11.5" '
        f'font-weight="700" fill="{color}">{_esc(label)}</text>'
        f'</svg>'
    )
    return svg


# ── Vertical column chart ─────────────────────────────────────────────────

def bar_chart(items: list[dict], color: str = "#1a56db",
              width: int = 500, cat: str = "") -> str:
    """
    Vertical column chart. Each item: {"name", "value", "formatted"}.
    Columns are evenly spaced. Labels rotate 45° if long.
    No title — the section card header provides it.
    """
    if not items:
        return ""

    tint      = TINTS.get(cat, "#f1f5f9")
    pad_top   = 32     # space above tallest bar for value label
    pad_bot   = 80     # space below x-axis for rotated labels
    pad_l     = 46     # y-axis area
    pad_r     = 16
    chart_h   = 180    # height of the bar area
    height    = pad_top + chart_h + pad_bot

    n         = len(items)
    col_w     = max(36, min(80, (width - pad_l - pad_r) // n))
    total_w   = col_w * n
    # centre the group
    x_start   = pad_l + ((width - pad_l - pad_r) - total_w) // 2

    max_val   = max(abs(it["value"]) for it in items if it["value"] is not None) or 1.0

    gid = f"g{abs(hash(color)) % 99999}"

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="display:block;max-width:100%;">',
        # defs: gradient
        f'<defs>'
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.92"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.55"/>'
        f'</linearGradient>'
        f'</defs>',
        # card bg
        f'<rect width="{width}" height="{height}" fill="#ffffff" rx="10" '
        f'stroke="#e2e8f0" stroke-width="1"/>',
        # baseline
        f'<line x1="{pad_l}" y1="{pad_top + chart_h}" '
        f'x2="{width - pad_r}" y2="{pad_top + chart_h}" '
        f'stroke="#e2e8f0" stroke-width="1.5"/>',
        # gridlines (4 levels)
    ]

    for level in [0.25, 0.5, 0.75, 1.0]:
        gy = pad_top + chart_h - int(chart_h * level)
        gval = max_val * level
        lines.append(
            f'<line x1="{pad_l}" y1="{gy}" x2="{width - pad_r}" y2="{gy}" '
            f'stroke="#f1f5f9" stroke-width="1"/>'
        )
        # y-axis tick label
        label_txt = f"{gval:.0f}" if gval >= 10 else f"{gval:.1f}"
        lines.append(
            f'<text x="{pad_l - 4}" y="{gy + 4}" text-anchor="end" '
            f'font-family="-apple-system,Segoe UI,sans-serif" font-size="9" '
            f'fill="#94a3b8">{_esc(label_txt)}</text>'
        )

    for i, it in enumerate(items):
        val   = it["value"] if it["value"] is not None else 0.0
        neg   = val < 0
        bcol  = "#e11d48" if neg else f"url(#{gid})"
        btnt  = "#fee2e2" if neg else tint

        bar_h = max(int(abs(val) / max_val * chart_h * 0.92), 4)
        bx    = x_start + i * col_w + 4
        bw    = col_w - 8
        by    = pad_top + chart_h - bar_h

        # tint track (full height)
        lines.append(
            f'<rect x="{bx}" y="{pad_top}" width="{bw}" height="{chart_h}" '
            f'fill="{btnt}" rx="4" opacity="0.5"/>'
        )
        # filled bar
        lines.append(
            f'<rect x="{bx}" y="{by}" width="{bw}" height="{bar_h}" '
            f'fill="{bcol}" rx="4"/>'
        )

        # value label above bar
        val_str = _esc(it["formatted"])
        lines.append(
            f'<text x="{bx + bw//2}" y="{by - 4}" text-anchor="middle" '
            f'font-family="-apple-system,Segoe UI,sans-serif" font-size="10" '
            f'font-weight="700" fill="{"#e11d48" if neg else color}">{val_str}</text>'
        )

        # x-axis label — short form, horizontal, two lines if needed
        lbl   = _short(it["name"])
        cx    = bx + bw // 2
        ly    = pad_top + chart_h + 14
        words = lbl.split()
        mid   = (len(words) + 1) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        lines.append(
            f'<text x="{cx}" y="{ly}" text-anchor="middle" '
            f'font-family="-apple-system,Segoe UI,sans-serif" font-size="10.5" '
            f'font-weight="600" fill="#334155">{_esc(line1)}</text>'
        )
        if line2:
            lines.append(
                f'<text x="{cx}" y="{ly + 14}" text-anchor="middle" '
                f'font-family="-apple-system,Segoe UI,sans-serif" font-size="10.5" '
                f'font-weight="600" fill="#334155">{_esc(line2)}</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


# ── Overview vertical chart (all categories) ─────────────────────────────

def overview_bar_chart(ratio_categories: dict, width: int = 700) -> str:
    """
    All available ratios as a vertical column chart, colour-coded by category.
    Legend at top-left.
    """
    items = []
    for cat, ratios in ratio_categories.items():
        color = COLORS.get(cat, "#64748b")
        tint  = TINTS.get(cat, "#f1f5f9")
        for r in ratios:
            if r.get("is_available") and r.get("value") is not None:
                if r.get("unit") == "days":
                    continue
                items.append({
                    "name":      r["name"],
                    "value":     float(r["value"]),
                    "formatted": r["formatted_value"],
                    "color":     color,
                    "tint":      tint,
                    "cat":       cat,
                })

    if not items:
        return ""

    seen = {}
    for it in items:
        seen.setdefault(it["cat"], it["color"])
    legend_items = list(seen.items())

    legend_h  = 26
    pad_top   = legend_h + 34
    pad_bot   = 84
    pad_l     = 46
    pad_r     = 16
    chart_h   = 200
    height    = pad_top + chart_h + pad_bot

    n         = len(items)
    col_w     = max(28, min(56, (width - pad_l - pad_r) // n))
    total_w   = col_w * n
    x_start   = pad_l + ((width - pad_l - pad_r) - total_w) // 2
    max_val   = max(abs(it["value"]) for it in items) or 1.0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="display:block;max-width:100%;">',
        f'<rect width="{width}" height="{height}" fill="#ffffff" rx="10" '
        f'stroke="#e2e8f0" stroke-width="1"/>',
    ]

    # legend row
    lx = pad_l
    for cat_name, cat_color in legend_items:
        item_w = len(cat_name) * 6 + 24
        lines.append(
            f'<rect x="{lx}" y="8" width="10" height="10" fill="{cat_color}" rx="2"/>'
            f'<text x="{lx+14}" y="17" '
            f'font-family="-apple-system,Segoe UI,sans-serif" font-size="10.5" '
            f'fill="#64748b">{_esc(cat_name.title())}</text>'
        )
        lx += item_w

    # baseline
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_top + chart_h}" '
        f'x2="{width - pad_r}" y2="{pad_top + chart_h}" '
        f'stroke="#e2e8f0" stroke-width="1.5"/>'
    )

    # gridlines
    for level in [0.25, 0.5, 0.75, 1.0]:
        gy   = pad_top + chart_h - int(chart_h * level)
        gval = max_val * level
        lines.append(
            f'<line x1="{pad_l}" y1="{gy}" x2="{width - pad_r}" y2="{gy}" '
            f'stroke="#f1f5f9" stroke-width="1"/>'
        )
        label_txt = f"{gval:.0f}" if gval >= 10 else f"{gval:.1f}"
        lines.append(
            f'<text x="{pad_l - 4}" y="{gy + 4}" text-anchor="end" '
            f'font-family="-apple-system,Segoe UI,sans-serif" font-size="9" '
            f'fill="#94a3b8">{_esc(label_txt)}</text>'
        )

    # columns
    for i, it in enumerate(items):
        val   = it["value"]
        neg   = val < 0
        bcol  = "#e11d48" if neg else it["color"]
        btnt  = "#fee2e2" if neg else it["tint"]
        bar_h = max(int(abs(val) / max_val * chart_h * 0.92), 4)
        bx    = x_start + i * col_w + 3
        bw    = col_w - 6
        by    = pad_top + chart_h - bar_h

        lines.append(
            f'<rect x="{bx}" y="{pad_top}" width="{bw}" height="{chart_h}" '
            f'fill="{btnt}" rx="3" opacity="0.45"/>'
        )
        lines.append(
            f'<rect x="{bx}" y="{by}" width="{bw}" height="{bar_h}" '
            f'fill="{bcol}" rx="3" opacity="0.9"/>'
        )

        val_str = _esc(it["formatted"])
        lines.append(
            f'<text x="{bx + bw//2}" y="{by - 4}" text-anchor="middle" '
            f'font-family="-apple-system,Segoe UI,sans-serif" font-size="9.5" '
            f'font-weight="700" fill="{bcol}">{val_str}</text>'
        )

        # x-axis label — short form, horizontal
        lbl   = _short(it["name"])
        cx2   = bx + bw // 2
        ly2   = pad_top + chart_h + 14
        words = lbl.split()
        mid   = (len(words) + 1) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        lines.append(
            f'<text x="{cx2}" y="{ly2}" text-anchor="middle" '
            f'font-family="-apple-system,Segoe UI,sans-serif" font-size="10" '
            f'font-weight="600" fill="#334155">{_esc(line1)}</text>'
        )
        if line2:
            lines.append(
                f'<text x="{cx2}" y="{ly2 + 13}" text-anchor="middle" '
                f'font-family="-apple-system,Segoe UI,sans-serif" font-size="10" '
                f'font-weight="600" fill="#334155">{_esc(line2)}</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


# ── Public builder ────────────────────────────────────────────────────────

def build_charts(ratios: dict, health_score: dict) -> dict:
    charts = {}

    charts["health"] = donut_chart(
        score=health_score.get("score", 0),
        label=health_score.get("label", ""),
        size=190,
    )

    charts["overview"] = overview_bar_chart(ratios, width=700)

    for cat, ratio_list in ratios.items():
        color = COLORS.get(cat, "#64748b")
        items = [
            {
                "name":      r["name"],
                "value":     float(r["value"]),
                "formatted": r["formatted_value"],
            }
            for r in ratio_list
            if r.get("is_available") and r.get("value") is not None
            and r.get("unit") != "days"
        ]
        if items:
            charts[cat] = bar_chart(items, color=color, width=500, cat=cat)

    return charts
