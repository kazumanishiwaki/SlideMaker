from __future__ import annotations

from typing import Any

from .charts import SUPPORTED_CHART_TYPES
from .recipes import RECIPES


def build_output_profile() -> dict[str, Any]:
    return {
        "schema_version": "0.4.0",
        "deck_spec": {
            "path": "plan/deck_spec.json",
            "slide_id_pattern": "S<zero-padded-number>",
            "recipes": sorted(RECIPES),
            "native_chart_types": sorted(SUPPORTED_CHART_TYPES),
        },
        "artifact_names": {
            "deck": "deck.pptx",
            "summary": "summary.json",
            "review_packet": "review_packet.json",
            "asset_requests": "asset_requests.json",
            "ocr_qa": "qa-ocr.json",
            "generated_image_qa": "qa-generated-image.json",
            "native_chart_qa": "qa-native-chart.json",
            "structural_qa": "qa-structural.json",
            "package_qa": "qa-package.json",
            "provenance_qa": "qa-provenance.json",
            "render_qa": "qa-render.json",
            "visual_qa": "qa-visual.json",
        },
        "route_invariant": "AI and deterministic routes use the same deck spec, recipes, composer, provenance, and QA gates",
    }


def inspect_output_contract(deck: Any, plans: list[Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    slide_ids = [slide.slide_id for slide in deck.slides]
    if len(slide_ids) != len(set(slide_ids)):
        findings.append({"code": "duplicate_slide_id", "severity": "blocking", "message": "slide IDs must be unique"})
    if len(deck.slides) != len(plans):
        findings.append({"code": "plan_count_mismatch", "severity": "blocking", "message": "every slide must have exactly one layout plan"})
    for slide, plan in zip(deck.slides, plans):
        if slide.slide_id != plan.slide_id:
            findings.append({"code": "plan_slide_id_mismatch", "severity": "blocking", "slide_id": slide.slide_id, "message": "deck and layout plan IDs differ"})
        if slide.recipe not in RECIPES or plan.recipe not in RECIPES:
            findings.append({"code": "nonstandard_recipe", "severity": "blocking", "slide_id": slide.slide_id, "message": "recipe is outside the common output profile"})
        invalid_names = [element.element_id for element in plan.elements if not element.element_id.startswith(f"{slide.slide_id}-")]
        if invalid_names:
            findings.append({"code": "nonstandard_element_name", "severity": "blocking", "slide_id": slide.slide_id, "message": "semantic element IDs must begin with their slide ID", "items": invalid_names})
    return {
        "schema_version": "0.4.0",
        "status": "FAIL" if findings else "PASS",
        "slide_count": len(deck.slides),
        "findings": findings,
    }

