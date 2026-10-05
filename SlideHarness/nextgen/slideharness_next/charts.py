from __future__ import annotations

from typing import Any
import math
import re


SUPPORTED_CHART_TYPES = {
    "bar",
    "column",
    "stacked-bar",
    "stacked-column",
    "line",
    "area",
    "pie",
    "doughnut",
    "scatter",
}

ALIASES = {
    "bar-clustered": "bar",
    "column-clustered": "column",
    "stacked_bar": "stacked-bar",
    "stacked_column": "stacked-column",
    "donut": "doughnut",
    "xy": "scatter",
    "xy-scatter": "scatter",
}


def _looks_like_time_axis(categories: list[Any]) -> bool:
    if len(categories) < 2:
        return False
    pattern = re.compile(r"(?:\d{4}[年/-]\d{1,2}|\d{1,2}月|Q[1-4]|第[1-4]四半期)", re.IGNORECASE)
    return sum(bool(pattern.search(str(value))) for value in categories) >= max(2, len(categories) // 2)


def choose_chart_type(chart: dict[str, Any]) -> str:
    requested = str(chart.get("chart_type") or chart.get("type") or "auto").strip().lower()
    requested = ALIASES.get(requested, requested)
    if requested not in {"", "auto"}:
        if requested not in SUPPORTED_CHART_TYPES:
            raise ValueError(f"unsupported native chart type: {requested}")
        return requested
    series = list(chart.get("series") or [])
    categories = list(chart.get("categories") or [])
    intent = str(chart.get("intent") or "").strip().lower()
    if intent in {"correlation", "distribution", "relationship"} or any(item.get("x_values") is not None for item in series):
        return "scatter"
    if intent in {"composition", "share", "part-to-whole"}:
        return "doughnut"
    if intent in {"cumulative", "volume-over-time"}:
        return "area"
    if intent in {"trend", "time-series", "change-over-time"} or _looks_like_time_axis(categories):
        return "line"
    if chart.get("stacked") is True:
        return "stacked-bar" if chart.get("orientation") == "horizontal" else "stacked-column"
    return "bar" if chart.get("orientation") == "horizontal" else "column"


def validate_chart_content(chart: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        chart_type = choose_chart_type(chart)
    except ValueError as error:
        return [str(error)]
    series = list(chart.get("series") or [])
    categories = list(chart.get("categories") or [])
    if not series:
        errors.append("chart requires at least one series")
        return errors
    if chart_type == "scatter":
        for index, item in enumerate(series, start=1):
            x_values = list(item.get("x_values") or [])
            y_values = list(item.get("y_values") or item.get("values") or [])
            if not x_values or len(x_values) != len(y_values):
                errors.append(f"scatter series {index} requires equal non-empty x_values and y_values")
                continue
            try:
                if not all(math.isfinite(float(value)) for value in [*x_values, *y_values]):
                    errors.append(f"scatter series {index} values must be finite numbers")
            except (TypeError, ValueError):
                errors.append(f"scatter series {index} values must be numeric")
        return errors
    if not categories:
        errors.append("category chart requires at least one category")
    for index, item in enumerate(series, start=1):
        values = list(item.get("values") or [])
        if len(values) != len(categories):
            errors.append(f"series {index} value count must match category count")
        try:
            if not all(math.isfinite(float(value)) for value in values):
                errors.append(f"series {index} values must be finite numbers")
        except (TypeError, ValueError):
            errors.append(f"series {index} values must be numeric")
    if chart_type in {"pie", "doughnut"}:
        if len(series) != 1:
            errors.append(f"{chart_type} requires exactly one series")
        values = list(series[0].get("values") or []) if series else []
        try:
            numeric_values = [float(value) for value in values]
            if any(value < 0 for value in numeric_values):
                errors.append(f"{chart_type} values must be non-negative")
            if numeric_values and sum(numeric_values) <= 0:
                errors.append(f"{chart_type} values must have a positive total")
        except (TypeError, ValueError):
            pass
    return errors
