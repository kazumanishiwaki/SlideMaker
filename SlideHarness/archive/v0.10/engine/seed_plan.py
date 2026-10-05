from __future__ import annotations
from pathlib import Path
from typing import Any

from helpers import now_iso, read_json, write_json
from planning import project_legacy_views, write_slide_plan_bundle

VISUAL_MAP = {
    "process": ("flow", "four_step"),
    "comparison": ("table", None),
    "numerical_data": ("kpi", None),
    "conditional_claim": ("text_statement", None),
    "customer_copy": ("text_statement", None),
}
ROLE_MAP = {
    "process": "process",
    "comparison": "comparison",
    "numerical_data": "kpi",
    "conditional_claim": "statement",
    "customer_copy": "statement",
}
RELATION_MAP = {
    "process": "sequence",
    "comparison": "comparison",
    "numerical_data": "data",
    "conditional_claim": "statement",
    "customer_copy": "statement",
}
FAMILY_MAP = {
    "process": "process",
    "comparison": "comparison_matrix",
    "numerical_data": "kpi",
    "conditional_claim": "statement",
    "customer_copy": "statement",
}


def choose_message(unit: dict[str, Any]) -> str:
    for item in unit.get("items", []):
        if item.get("classification", {}).get("primary") in {"customer_copy", "process", "comparison", "conditional_claim"}:
            text = item.get("source_text", "").strip()
            if text:
                return text[:90]
    return (unit.get("heading") or unit.get("source_text") or "Untitled")[:90]


def score_slide(target_role: str, source: dict[str, Any]) -> float:
    roles = source.get("roles", {})
    primary = roles.get("primary")
    secondary = roles.get("secondary", [])
    score = 0.20
    if primary == target_role:
        score += 0.62
    elif target_role in secondary:
        score += 0.42
    compat = {
        "process": {"timeline", "four_items", "three_items"},
        "comparison": {"table", "three_items", "four_items"},
        "statement": {"long_text", "overview", "three_items"},
        "kpi": {"chart", "table"},
    }
    if primary in compat.get(target_role, set()):
        score += 0.20
    if primary in {"cover", "closing", "qna"} and target_role not in {"cover", "closing"}:
        score -= 0.25
    return max(0.0, min(0.99, score))


def seed(project: str | Path) -> dict[str, Any]:
    root = Path(project)
    manuscript = read_json(root / "analysis/manuscript_analysis.json", {})
    source_slides = read_json(root / "analysis/source_slides.json", {})
    units = manuscript.get("content_units", [])
    candidates = source_slides.get("slides", [])

    deck_slides: list[dict[str, Any]] = []
    slide_plans: list[dict[str, Any]] = []
    out_index = 1
    for unit in units:
        primary = unit.get("classification", {}).get("primary")
        if primary in {"editorial_instruction", "visual_instruction"}:
            continue
        if not (unit.get("heading") or unit.get("source_text")):
            continue
        role = ROLE_MAP.get(primary, "overview")
        visual_type, variant = VISUAL_MAP.get(primary, ("no_visual", None))
        family = FAMILY_MAP.get(primary, "statement")
        relation = RELATION_MAP.get(primary, "statement")
        slide_id = f"OUT-S{out_index:03d}"
        message = choose_message(unit)
        scored = sorted([
            {
                "source_slide_id": s["id"],
                "page_number": s["page_number"],
                "total_score": round(score_slide(role, s), 3),
                "recommended_mode": "DIRECT" if score_slide(role, s) >= 0.78 else "ADAPT" if score_slide(role, s) >= 0.55 else "RECOMPOSE",
            }
            for s in candidates
        ], key=lambda x: x["total_score"], reverse=True)[:3]
        selected = scored[0] if scored else {"source_slide_id": "SRC-S001", "recommended_mode": "RECOMPOSE"}

        deck_slides.append({
            "slide_id": slide_id,
            "order": out_index,
            "role": role,
            "primary_message": message,
            "content_units": [unit["id"]],
            "importance": unit.get("importance", "secondary"),
            "optional": False,
            "status": "DRAFT",
            "origin": "deterministic_seed",
        })
        slide_plans.append({
            "slide_id": slide_id,
            "message": message,
            "semantic_chunks": [message],
            "semantic_relation": relation,
            "visual": {"type": visual_type, "variant": variant, "purpose": f"seed:{primary or 'unknown'}"},
            "source": {
                "slide_id": selected.get("source_slide_id"),
                "mode": selected.get("recommended_mode") or "RECOMPOSE",
                "candidates": scored,
            },
            "layout": {"family": family, "density": "medium_low", "fill_policy": "balanced"},
            "content": {"title": message},
            "image": {"required": visual_type in {"photo", "screenshot", "illustration"}},
            "runtime": {"composer_support": "layout_engine", "content_blocks": [], "source_object_mutations": []},
            "status": "DRAFT",
            "origin": "deterministic_seed",
        })
        out_index += 1

    deck = {
        "schema_version": "0.10",
        "generated_at": now_iso(),
        "deck": {"goal": None, "audience": None},
        "slides": deck_slides,
        "status": "DRAFT",
        "notes": ["Seed only. Codex should replace deck_plan.json and slide_plans.json in two planning calls before approval."],
    }
    write_json(root / "planning/deck_plan.json", deck)
    bundle = write_slide_plan_bundle(root, slide_plans, status="DRAFT")
    derived = project_legacy_views(root)
    return {"deck_plan": deck, "slide_plans": bundle, "derived_views": derived}
