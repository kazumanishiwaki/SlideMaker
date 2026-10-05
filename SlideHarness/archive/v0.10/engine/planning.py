from __future__ import annotations

"""Compact planning model used by SlideHarness v0.10.

The public planning surface is intentionally small:

- deck_plan.json: deck order and one primary message per slide
- slide_plans.json: all slide-level decisions in one document

The deterministic runtime may still materialize per-slide files for compatibility
with the existing composer, but Visual Plan, Source Match, Fill Policy, Image
intent, and Layout Plan are not separate AI-authored phases anymore.
"""

from copy import deepcopy
from pathlib import Path
from typing import Any

from helpers import now_iso, read_json, write_json


LAYOUT_RENDERER_GROUPS: dict[str, str] = {
    # statement renderer
    "cover": "statement",
    "section": "statement",
    "statement": "statement",
    "closing": "statement",
    # grid renderer
    "grid": "grid",
    "two_column": "grid",
    "comparison_matrix": "grid",
    # media renderer
    "photo_text": "media",
    "full_bleed": "media",
    "photo_grid": "media",
    "screenshot": "media",
    # flow renderer
    "process": "flow",
    "timeline": "flow",
    "relationship": "flow",
    "cause_effect": "flow",
    "containment": "flow",
    # data renderer
    "kpi": "data",
    "chart": "data",
    "table": "data",
}

# Thin semantic-to-layout compatibility table.  It is intentionally declarative
# rather than another model or repair loop.
SEMANTIC_LAYOUT_ALLOWLIST: dict[str, set[str]] = {
    "statement": {"cover", "section", "statement", "closing", "photo_text", "full_bleed"},
    "sequence": {"process", "timeline"},
    "cause_effect": {"process", "timeline", "cause_effect"},
    "comparison": {"two_column", "comparison_matrix", "chart", "table"},
    "containment": {"containment", "process", "comparison_matrix"},
    "parallel_categories": {"grid", "two_column", "comparison_matrix"},
    "hierarchy": {"relationship", "containment"},
    "evidence": {"photo_text", "full_bleed", "screenshot", "chart", "table", "comparison_matrix"},
    "transformation": {"process", "timeline", "cause_effect"},
    "data": {"kpi", "chart", "table", "comparison_matrix"},
}

SEMANTIC_LAYOUT_EXPLICIT_FORBIDS: set[tuple[str, str]] = {
    ("cause_effect", "relationship"),
    ("sequence", "grid"),
    ("sequence", "two_column"),
    ("containment", "two_column"),
}

COMPACT_DECISION_KEYS = {
    "slide_id",
    "message",
    "semantic_chunks",
    "semantic_relation",
    "visual",
    "source",
    "layout",
    "content",
    "image",
    "runtime",
    "status",
    "origin",
}


def renderer_group(family: str | None) -> str:
    return LAYOUT_RENDERER_GROUPS.get(str(family or "").strip(), "unknown")


def semantic_layout_issues(plan: dict[str, Any]) -> list[dict[str, Any]]:
    relation = str(plan.get("semantic_relation") or "").strip()
    layout = plan.get("layout") or {}
    family = str(layout.get("family") or (plan.get("layout_request") or {}).get("family") or "").strip()
    if not relation or not family:
        return []

    issues: list[dict[str, Any]] = []
    if (relation, family) in SEMANTIC_LAYOUT_EXPLICIT_FORBIDS:
        issues.append({
            "check_id": "SEMANTIC_LAYOUT_FORBIDDEN",
            "category": "content",
            "severity": "blocking",
            "relation": relation,
            "family": family,
        })
        return issues

    allowed = SEMANTIC_LAYOUT_ALLOWLIST.get(relation)
    if allowed is not None and family not in allowed:
        issues.append({
            "check_id": "SEMANTIC_LAYOUT_MISMATCH",
            "category": "design",
            "severity": "review",
            "relation": relation,
            "family": family,
            "allowed_families": sorted(allowed),
        })
    return issues


def _fill_policy_from_layout(layout: dict[str, Any]) -> dict[str, Any] | None:
    value = layout.get("fill_policy")
    if isinstance(value, str) and value:
        return {"mode": value, "source": "slide_plan"}
    if isinstance(value, dict) and value.get("mode"):
        return deepcopy(value)
    return None


def normalize_compact_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Return one compact, stable slide decision object.

    Unknown debugging/runtime details are deliberately kept under ``runtime`` so
    the AI-facing surface does not grow whenever the deterministic composer gains
    an implementation detail.
    """
    slide_id = str(plan.get("slide_id") or "").strip()
    message = str(plan.get("message") or plan.get("primary_message") or "").strip()
    layout = deepcopy(plan.get("layout") or {})
    if not layout and plan.get("layout_request"):
        request = deepcopy(plan.get("layout_request") or {})
        layout = {
            "family": request.pop("family", None),
            "density": request.pop("density", None),
            "variant": request.pop("variant", None),
            "fill_policy": (plan.get("fill_policy") or {}).get("mode") if isinstance(plan.get("fill_policy"), dict) else plan.get("fill_policy"),
            "request": request,
        }
    source = deepcopy(plan.get("source") or {})
    if not source and plan.get("source_slide_id"):
        source = {
            "slide_id": plan.get("source_slide_id"),
            "mode": plan.get("adaptation_mode") or "RECOMPOSE",
        }
    visual = deepcopy(plan.get("visual") or {})
    content = deepcopy(plan.get("content") or {})
    image = deepcopy(plan.get("image") or {})
    runtime = deepcopy(plan.get("runtime") or {})

    # Preserve the deterministic payload without exposing it as a separate AI phase.
    if plan.get("layout_request"):
        runtime.setdefault("layout_request", deepcopy(plan.get("layout_request")))
    for key in ("content_blocks", "source_object_mutations", "composer_support", "source_object_ids"):
        if key in plan:
            runtime.setdefault(key, deepcopy(plan.get(key)))
    if plan.get("fill_policy"):
        layout.setdefault("fill_policy", (plan.get("fill_policy") or {}).get("mode") if isinstance(plan.get("fill_policy"), dict) else plan.get("fill_policy"))

    result = {
        "slide_id": slide_id,
        "message": message,
        "semantic_chunks": [str(x) for x in (plan.get("semantic_chunks") or []) if str(x).strip()],
        "semantic_relation": str(plan.get("semantic_relation") or "statement"),
        "visual": visual,
        "source": source,
        "layout": {k: v for k, v in layout.items() if v is not None},
        "content": content,
        "image": image,
        "runtime": runtime,
        "status": str(plan.get("status") or "DRAFT"),
        "origin": str(plan.get("origin") or "ai"),
    }
    return result


def compact_to_runtime(plan: dict[str, Any]) -> dict[str, Any]:
    """Compile a compact plan to the existing deterministic runtime contract."""
    compact = normalize_compact_plan(plan)
    runtime = deepcopy(compact.get("runtime") or {})
    source = compact.get("source") or {}
    layout = compact.get("layout") or {}
    content = compact.get("content") or {}
    visual = compact.get("visual") or {}
    image = compact.get("image") or {}

    request = deepcopy(runtime.get("layout_request") or layout.get("request") or {})
    if layout.get("family"):
        request["family"] = layout["family"]
    if layout.get("density"):
        request["density"] = layout["density"]
    if layout.get("variant"):
        request["variant"] = layout["variant"]

    # Common content fields are copied once.  More specialised payloads stay in
    # layout.request so the compact schema does not duplicate every renderer key.
    for key in (
        "title", "subtitle", "body", "items", "matrix", "nodes", "edges",
        "center_node_id", "categories", "series", "chart_type", "kpis",
        "kicker", "section_number", "note",
    ):
        if key in content and key not in request:
            request[key] = deepcopy(content[key])
    chunks = compact.get("semantic_chunks") or []
    if chunks and (not request.get("title") or request.get("title") == compact.get("message")):
        # Meaning boundaries are chosen once in Slide Plan. The renderer must not
        # rebalance these lines merely to equalise character counts.
        request["title"] = "\n".join(str(x) for x in chunks)
    elif not request.get("title") and compact.get("message"):
        request["title"] = compact["message"]
    if image.get("recipe_id") and not request.get("image_recipe_id"):
        request["image_recipe_id"] = image["recipe_id"]
    for key in ("position", "text_side", "ratio", "source_object_id", "reuse_source_frame"):
        if key not in image:
            continue
        mapping = {
            "position": "image_position",
            "ratio": "image_ratio",
            "source_object_id": "image_source_object_id",
            "reuse_source_frame": "reuse_source_image_frame",
        }
        request.setdefault(mapping.get(key, key), image[key])

    fill = _fill_policy_from_layout(layout)
    result = {
        "schema_version": "0.10",
        "slide_id": compact["slide_id"],
        "source_slide_id": source.get("slide_id"),
        "adaptation_mode": source.get("mode") or "RECOMPOSE",
        "composer_support": runtime.get("composer_support") or "layout_engine",
        "content_blocks": deepcopy(runtime.get("content_blocks") or []),
        "source_object_mutations": deepcopy(runtime.get("source_object_mutations") or []),
        "layout_request": request,
        "status": compact.get("status") or "DRAFT",
        "message": compact.get("message"),
        "semantic_chunks": compact.get("semantic_chunks") or [],
        "semantic_relation": compact.get("semantic_relation"),
        "visual": visual,
        "source": source,
        "layout": layout,
        "content": content,
        "image": image,
        "origin": compact.get("origin") or "ai",
        "renderer_group": renderer_group(layout.get("family")),
    }
    if fill:
        result["fill_policy"] = fill
    return result


def write_slide_plan_bundle(root: str | Path, slides: list[dict[str, Any]], *, status: str = "DRAFT") -> dict[str, Any]:
    root = Path(root)
    compact = [normalize_compact_plan(row) for row in slides]
    doc = {
        "schema_version": "0.10",
        "generated_at": now_iso(),
        "status": status,
        "model_call_contract": {
            "normal_generation_calls": 2,
            "repair_call_limit_per_slide": 1,
            "ai_authored_documents": ["deck_plan.json", "slide_plans.json"],
        },
        "slides": compact,
    }
    write_json(root / "planning/slide_plans.json", doc)
    per_slide = root / "planning/slide_plans"
    per_slide.mkdir(parents=True, exist_ok=True)
    for row in compact:
        write_json(per_slide / f"{row['slide_id']}.json", compact_to_runtime(row))
    return doc


def load_slide_plan_bundle(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    bundle = read_json(root / "planning/slide_plans.json", None)
    if bundle:
        return bundle
    slides: list[dict[str, Any]] = []
    for path in sorted((root / "planning/slide_plans").glob("OUT-S*.json")):
        raw = read_json(path, {})
        raw.setdefault("slide_id", path.stem)
        slides.append(normalize_compact_plan(raw))
    return {
        "schema_version": "0.10",
        "generated_at": now_iso(),
        "status": "DRAFT",
        "slides": slides,
    }


def compile_plan_bundle(root: str | Path) -> dict[str, Any]:
    """Compile the AI-authored compact bundle to deterministic per-slide files."""
    root = Path(root)
    bundle = load_slide_plan_bundle(root)
    issues: list[dict[str, Any]] = []
    for compact in bundle.get("slides", []):
        issues.extend({"slide_id": compact.get("slide_id"), **x} for x in semantic_layout_issues(compact))
        write_json(root / "planning/slide_plans" / f"{compact['slide_id']}.json", compact_to_runtime(compact))
    result = {
        "schema_version": "0.10",
        "generated_at": now_iso(),
        "slide_count": len(bundle.get("slides", [])),
        "issues": issues,
        "blocking_count": sum(1 for x in issues if x.get("severity") == "blocking"),
        "review_count": sum(1 for x in issues if x.get("severity") != "blocking"),
    }
    write_json(root / "qa/plan_validation.json", result)
    return result


def project_legacy_views(root: str | Path) -> dict[str, Any]:
    """Write read-only compatibility views for older UI/runtime code.

    These files are derived and must never be sent to the model as independent
    planning tasks.  They allow a staged simplification without a risky rewrite of
    every consumer in one release.
    """
    root = Path(root)
    bundle = load_slide_plan_bundle(root)
    visual_rows = []
    match_rows = []
    for row in bundle.get("slides", []):
        visual = row.get("visual") or {}
        source = row.get("source") or {}
        visual_rows.append({
            "slide_id": row.get("slide_id"),
            "visual_intent": {
                "selected_type": visual.get("type") or "no_visual",
                "variant": visual.get("variant"),
                "purpose": visual.get("purpose"),
            },
            "origin": "derived_from_slide_plans",
        })
        match_rows.append({
            "slide_id": row.get("slide_id"),
            "selected": {
                "source_slide_id": source.get("slide_id"),
                "recommended_mode": source.get("mode") or "RECOMPOSE",
                "origin": "derived_from_slide_plans",
            },
            "origin": "derived_from_slide_plans",
        })
    visual_doc = {"schema_version": "0.10-derived", "status": bundle.get("status"), "slides": visual_rows}
    match_doc = {"schema_version": "0.10-derived", "status": bundle.get("status"), "slides": match_rows}
    write_json(root / "planning/visual_plan.json", visual_doc)
    write_json(root / "planning/slide_matching.json", match_doc)
    return {"visual_plan": visual_doc, "slide_matching": match_doc}
