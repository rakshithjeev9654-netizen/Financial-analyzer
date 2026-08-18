"""
Financial Health Score
Calculates an analytical 0–100 financial health score from available ratios.
"""

from __future__ import annotations


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _score_current_ratio(value: float | None) -> float:
    if value is None:
        return 50.0
    if value >= 2.0:
        return 100.0
    if value >= 1.5:
        return 85.0
    if value >= 1.0:
        return 70.0
    if value >= 0.75:
        return 45.0
    return 20.0


def _score_quick_ratio(value: float | None) -> float:
    if value is None:
        return 50.0
    if value >= 1.5:
        return 100.0
    if value >= 1.0:
        return 85.0
    if value >= 0.75:
        return 60.0
    if value >= 0.5:
        return 40.0
    return 20.0


def _score_net_margin(value: float | None) -> float:
    if value is None:
        return 50.0
    if value >= 20:
        return 100.0
    if value >= 15:
        return 90.0
    if value >= 10:
        return 80.0
    if value >= 5:
        return 65.0
    if value >= 0:
        return 50.0
    if value >= -5:
        return 30.0
    return 10.0


def _score_roe(value: float | None) -> float:
    if value is None:
        return 50.0
    if value >= 20:
        return 100.0
    if value >= 15:
        return 90.0
    if value >= 10:
        return 80.0
    if value >= 5:
        return 65.0
    if value >= 0:
        return 50.0
    return 20.0


def _score_debt_to_equity(value: float | None) -> float:
    if value is None:
        return 50.0
    if value <= 0.5:
        return 100.0
    if value <= 1.0:
        return 85.0
    if value <= 1.5:
        return 70.0
    if value <= 2.0:
        return 50.0
    if value <= 3.0:
        return 30.0
    return 10.0


def _score_interest_coverage(value: float | None) -> float:
    if value is None:
        return 50.0
    if value >= 8:
        return 100.0
    if value >= 5:
        return 90.0
    if value >= 3:
        return 75.0
    if value >= 2:
        return 55.0
    if value >= 1:
        return 35.0
    return 10.0


def calculate_health_score(ratios) -> float:
    """
    Calculate an analytical 0–100 score.

    Accepts either:
      1. A dictionary of ratio categories containing RatioResult objects/dicts.
      2. A flat dictionary of ratio names -> numeric values.

    Missing ratios are given neutral weight and do not create fake values.
    """

    values = {}

    if isinstance(ratios, dict):
        for category_items in ratios.values():
            if isinstance(category_items, list):
                for item in category_items:
                    if hasattr(item, "name"):
                        name = item.name
                        value = item.value if getattr(item, "is_available", False) else None
                    elif isinstance(item, dict):
                        name = item.get("name")
                        value = item.get("value") if item.get("is_available", True) else None
                    else:
                        continue

                    if name:
                        values[name] = value
            elif isinstance(category_items, dict):
                for name, item in category_items.items():
                    if isinstance(item, (int, float)):
                        values[name] = item
                    elif isinstance(item, dict):
                        values[name] = item.get("value")

        # Support a flat dictionary too.
        for name, value in ratios.items():
            if isinstance(value, (int, float)):
                values[name] = value

    score_components = []

    component_map = [
        ("Current Ratio", _score_current_ratio),
        ("Quick Ratio", _score_quick_ratio),
        ("Net Profit Margin", _score_net_margin),
        ("Return on Equity (ROE)", _score_roe),
        ("Debt-to-Equity Ratio", _score_debt_to_equity),
        ("Interest Coverage", _score_interest_coverage),
    ]

    for name, scorer in component_map:
        if name in values:
            score_components.append(scorer(values[name]))

    if not score_components:
        return 50.0

    return round(_clamp(sum(score_components) / len(score_components)), 1)


def get_health_label(score: float) -> str:
    """Return a human-readable interpretation for the score."""
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Healthy"
    if score >= 40:
        return "Moderate"
    if score >= 20:
        return "Weak"
    return "Critical"