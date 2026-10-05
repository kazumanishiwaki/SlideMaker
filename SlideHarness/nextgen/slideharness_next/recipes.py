from __future__ import annotations

from typing import Any, Callable

from .models import LayoutPlan, PlannedElement, SlideSpec
from .charts import choose_chart_type


TITLE_Y = 0.065
CONTENT_Y = 0.205
CONTENT_H = 0.68
MARGIN_X = 0.055
CONTENT_W = 0.89


def _element(element_id: str, kind: str, x: float, y: float, w: float, h: float, role: str, **data: Any) -> PlannedElement:
    return PlannedElement(element_id, kind, x, y, w, h, role, data)


def _title_elements(spec: SlideSpec) -> list[PlannedElement]:
    return [
        _element(f"{spec.slide_id}-title", "text", MARGIN_X, TITLE_Y, CONTENT_W, 0.09, "title", text=spec.title),
        _element(f"{spec.slide_id}-message", "text", MARGIN_X, 0.155, CONTENT_W, 0.045, "message", text=spec.message),
    ]


def cover(spec: SlideSpec) -> LayoutPlan:
    elements = [
        _element(f"{spec.slide_id}-panel", "cover_panel", 0.69, 0.18, 0.235, 0.62, "visual"),
        _element(f"{spec.slide_id}-title", "text", 0.075, 0.29, 0.62, 0.20, "cover_title", text=spec.title),
        _element(f"{spec.slide_id}-subtitle", "text", 0.08, 0.52, 0.55, 0.11, "cover_subtitle", text=spec.content.get("subtitle", spec.message)),
    ]
    return LayoutPlan(spec.slide_id, "cover", spec.source_unit_ids, elements, 1)


def section(spec: SlideSpec) -> LayoutPlan:
    elements = [
        _element(f"{spec.slide_id}-panel", "section_panel", MARGIN_X, 0.245, CONTENT_W, 0.49, "visual"),
        _element(f"{spec.slide_id}-title", "text", 0.105, 0.36, 0.78, 0.16, "section_title", text=spec.title),
        _element(f"{spec.slide_id}-message", "text", 0.11, 0.55, 0.70, 0.08, "section_message", text=spec.message),
    ]
    return LayoutPlan(spec.slide_id, "section", spec.source_unit_ids, elements, 1)


def statement(spec: SlideSpec) -> LayoutPlan:
    value = spec.content.get("statement", spec.message)
    elements = [
        _element(f"{spec.slide_id}-panel", "statement_panel", 0.105, 0.245, 0.79, 0.49, "visual"),
        _element(f"{spec.slide_id}-statement", "text", 0.16, 0.335, 0.68, 0.25, "statement", text=value),
        _element(f"{spec.slide_id}-label", "text", 0.18, 0.61, 0.64, 0.055, "statement_label", text=spec.title),
    ]
    return LayoutPlan(spec.slide_id, "statement", spec.source_unit_ids, elements, 1)


def title_body(spec: SlideSpec) -> LayoutPlan:
    elements = _title_elements(spec)
    elements.append(_element(f"{spec.slide_id}-body", "body", MARGIN_X, CONTENT_Y, CONTENT_W, CONTENT_H, "body", items=spec.content.get("bullets", [])))
    return LayoutPlan(spec.slide_id, "title_body", spec.source_unit_ids, elements, len(spec.content.get("bullets", [])))


def title_body_callout(spec: SlideSpec) -> LayoutPlan:
    elements = _title_elements(spec)
    elements.append(_element(f"{spec.slide_id}-body", "body", MARGIN_X, 0.235, 0.57, 0.62, "body", items=spec.content.get("bullets", [])))
    elements.append(_element(f"{spec.slide_id}-callout", "callout", 0.66, 0.235, 0.285, 0.62, "support", **spec.content.get("callout", {})))
    return LayoutPlan(spec.slide_id, "title_body_callout", spec.source_unit_ids, elements, len(spec.content.get("bullets", [])) + 1)


def two_column_equal(spec: SlideSpec) -> LayoutPlan:
    columns = list(spec.content.get("columns", []))[:2]
    elements = _title_elements(spec)
    gap = 0.035
    width = (CONTENT_W - gap) / 2
    for index, column in enumerate(columns):
        elements.append(_element(f"{spec.slide_id}-column-{index + 1}", "column_box", MARGIN_X + index * (width + gap), 0.255, width, 0.57, "support", **column))
    return LayoutPlan(spec.slide_id, "two_column_equal", spec.source_unit_ids, elements, len(columns))


def three_column(spec: SlideSpec) -> LayoutPlan:
    columns = list(spec.content.get("columns", []))[:3]
    elements = _title_elements(spec)
    gap = 0.022
    width = (CONTENT_W - gap * 2) / 3
    for index, column in enumerate(columns):
        elements.append(_element(f"{spec.slide_id}-column-{index + 1}", "column_box", MARGIN_X + index * (width + gap), 0.255, width, 0.57, "support", **column))
    return LayoutPlan(spec.slide_id, "three_column", spec.source_unit_ids, elements, len(columns))


def card_grid_2x2(spec: SlideSpec) -> LayoutPlan:
    cards = list(spec.content.get("cards", []))[:4]
    elements = _title_elements(spec)
    gap_x, gap_y = 0.025, 0.035
    card_w = (CONTENT_W - gap_x) / 2
    card_h = 0.265
    start_y = 0.255
    for index, card in enumerate(cards):
        row, col = divmod(index, 2)
        elements.append(_element(f"{spec.slide_id}-card-{index + 1}", "card", MARGIN_X + col * (card_w + gap_x), start_y + row * (card_h + gap_y), card_w, card_h, "support", **card))
    return LayoutPlan(spec.slide_id, "card_grid_2x2", spec.source_unit_ids, elements, len(cards))


def comparison(spec: SlideSpec) -> LayoutPlan:
    columns = list(spec.content.get("columns", []))[:2]
    elements = _title_elements(spec)
    gap = 0.035
    width = (CONTENT_W - gap) / 2
    for index, column in enumerate(columns):
        elements.append(_element(f"{spec.slide_id}-column-{index + 1}", "comparison_column", MARGIN_X + index * (width + gap), CONTENT_Y, width, CONTENT_H, "support", **column))
    return LayoutPlan(spec.slide_id, "comparison", spec.source_unit_ids, elements, len(columns))


def kpi_grid(spec: SlideSpec) -> LayoutPlan:
    metrics = list(spec.content.get("metrics", []))[:4]
    elements = _title_elements(spec)
    gap = 0.02
    width = (CONTENT_W - gap * max(0, len(metrics) - 1)) / max(1, len(metrics))
    for index, metric in enumerate(metrics):
        elements.append(_element(f"{spec.slide_id}-metric-{index + 1}", "metric", MARGIN_X + index * (width + gap), 0.275, width, 0.52, "data", **metric))
    return LayoutPlan(spec.slide_id, "kpi_grid", spec.source_unit_ids, elements, len(metrics))


def native_bar_chart(spec: SlideSpec) -> LayoutPlan:
    chart = dict(spec.content.get("chart", {}))
    chart.setdefault("chart_type", "column")
    elements = _title_elements(spec)
    elements.append(_element(f"{spec.slide_id}-chart", "native_chart", MARGIN_X, CONTENT_Y, 0.62, CONTENT_H, "data", **chart))
    elements.append(_element(f"{spec.slide_id}-insight", "callout", 0.71, CONTENT_Y, 0.235, CONTENT_H, "support", **spec.content.get("insight", {})))
    series = chart.get("series", [])
    return LayoutPlan(spec.slide_id, "native_bar_chart", spec.source_unit_ids, elements, len(series))


def native_chart(spec: SlideSpec) -> LayoutPlan:
    chart = dict(spec.content.get("chart", {}))
    chart["chart_type"] = choose_chart_type(chart)
    elements = _title_elements(spec)
    elements.append(_element(f"{spec.slide_id}-chart", "native_chart", MARGIN_X, CONTENT_Y, 0.62, CONTENT_H, "data", **chart))
    elements.append(_element(f"{spec.slide_id}-insight", "callout", 0.71, CONTENT_Y, 0.235, CONTENT_H, "support", **spec.content.get("insight", {})))
    return LayoutPlan(spec.slide_id, "native_chart", spec.source_unit_ids, elements, len(chart.get("series", [])))


def table(spec: SlideSpec) -> LayoutPlan:
    rows = list(spec.content.get("rows", []))
    elements = _title_elements(spec)
    elements.append(_element(f"{spec.slide_id}-table", "table", MARGIN_X, CONTENT_Y, CONTENT_W, CONTENT_H, "data", columns=spec.content.get("columns", []), rows=rows))
    return LayoutPlan(spec.slide_id, "table", spec.source_unit_ids, elements, len(rows))


def process(spec: SlideSpec) -> LayoutPlan:
    steps = list(spec.content.get("steps", []))[:5]
    elements = _title_elements(spec)
    gap = 0.018
    width = (CONTENT_W - gap * max(0, len(steps) - 1)) / max(1, len(steps))
    for index, step in enumerate(steps):
        elements.append(_element(f"{spec.slide_id}-step-{index + 1}", "process_step", MARGIN_X + index * (width + gap), 0.285, width, 0.50, "flow", number=index + 1, **step))
        if index < len(steps) - 1:
            elements.append(_element(f"{spec.slide_id}-arrow-{index + 1}", "process_arrow", MARGIN_X + (index + 1) * width + index * gap, 0.49, gap, 0.08, "connector"))
    return LayoutPlan(spec.slide_id, "process", spec.source_unit_ids, elements, len(steps))


def image_text(spec: SlideSpec) -> LayoutPlan:
    image = dict(spec.content.get("image") or {})
    request = {
        "asset_id": image.get("asset_id", f"{spec.slide_id}-hero"),
        "slide_id": spec.slide_id,
        "kind": "generated_image",
        "prompt": image.get("prompt", "Editorial presentation image matching the supplied template design system"),
        "aspect_ratio": "3:2",
        "resolved_path": image.get("path"),
        "source_url": image.get("source_url"),
        "source_urls": image.get("source_urls", []),
        "source_note": image.get("source_note") or image.get("source_citation"),
        "required_text": list(image.get("required_text") or []),
    }
    elements = _title_elements(spec)
    elements.append(_element(f"{spec.slide_id}-image", "image", MARGIN_X, CONTENT_Y, 0.55, CONTENT_H, "visual", asset_id=request["asset_id"], path=image.get("path")))
    elements.append(_element(f"{spec.slide_id}-caption", "callout", 0.635, CONTENT_Y, 0.31, CONTENT_H, "support", heading=spec.content.get("heading", ""), body=spec.content.get("body", "")))
    return LayoutPlan(spec.slide_id, "image_text", spec.source_unit_ids, elements, 2, [request])


def generated_visual(spec: SlideSpec) -> LayoutPlan:
    visual = dict(spec.content.get("visual") or {})
    visual_type = str(visual.get("type") or "flow")
    request = {
        "asset_id": visual.get("asset_id", f"{spec.slide_id}-structured-visual"),
        "slide_id": spec.slide_id,
        "kind": "generated_image",
        "visual_kind": visual_type,
        "purpose": visual.get("purpose", f"Rich {visual_type} visualization for the slide's exact facts and labels"),
        "prompt": visual.get(
            "prompt",
            f"Rich editorial {visual_type} visualization matching the supplied template design system; preserve all supplied labels and values exactly",
        ),
        "aspect_ratio": "16:9",
        "resolved_path": visual.get("path"),
        "source_url": visual.get("source_url"),
        "source_urls": visual.get("source_urls", []),
        "source_note": visual.get("source_note") or visual.get("source_citation"),
        "required_text": list(visual.get("required_text") or []),
    }
    elements = _title_elements(spec)
    elements.append(
        _element(
            f"{spec.slide_id}-generated-visual",
            "image",
            MARGIN_X,
            0.225,
            CONTENT_W,
            0.63,
            "structured_visual",
            asset_id=request["asset_id"],
            path=visual.get("path"),
        )
    )
    return LayoutPlan(spec.slide_id, "generated_visual", spec.source_unit_ids, elements, 1, [request])


def closing_cta(spec: SlideSpec) -> LayoutPlan:
    actions = list(spec.content.get("actions", []))[:3]
    elements = [
        _element(f"{spec.slide_id}-panel", "closing_panel", 0.09, 0.22, 0.82, 0.56, "visual"),
        _element(f"{spec.slide_id}-title", "text", 0.16, 0.31, 0.68, 0.13, "closing_title", text=spec.title),
        _element(f"{spec.slide_id}-body", "text", 0.19, 0.46, 0.62, 0.08, "closing_body", text=spec.content.get("body", spec.message)),
        _element(f"{spec.slide_id}-actions", "action_list", 0.22, 0.57, 0.56, 0.11, "support", items=actions),
    ]
    return LayoutPlan(spec.slide_id, "closing_cta", spec.source_unit_ids, elements, len(actions))


RECIPES: dict[str, Callable[[SlideSpec], LayoutPlan]] = {
    "cover": cover,
    "section": section,
    "statement": statement,
    "title_body": title_body,
    "title_body_callout": title_body_callout,
    "two_column_equal": two_column_equal,
    "three_column": three_column,
    "card_grid_2x2": card_grid_2x2,
    "comparison": comparison,
    "kpi_grid": kpi_grid,
    "native_bar_chart": native_bar_chart,
    "native_chart": native_chart,
    "table": table,
    "process": process,
    "image_text": image_text,
    "generated_visual": generated_visual,
    "closing_cta": closing_cta,
}


def choose_recipe(spec: SlideSpec) -> str:
    if spec.recipe != "auto":
        if spec.recipe not in RECIPES:
            raise ValueError(f"unknown recipe: {spec.recipe}")
        return spec.recipe
    content = spec.content
    if "image" in content:
        return "image_text"
    if "visual" in content:
        return "generated_visual"
    if "chart" in content:
        return "native_chart"
    if "steps" in content:
        return "process"
    if "metrics" in content:
        return "kpi_grid"
    if "columns" in content and "rows" in content:
        return "table"
    if "columns" in content:
        return "comparison"
    if "cards" in content:
        return "card_grid_2x2"
    return "title_body"


def plan_slide(spec: SlideSpec) -> LayoutPlan:
    recipe = choose_recipe(spec)
    return RECIPES[recipe](spec)
