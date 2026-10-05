from __future__ import annotations

from typing import Any
import json
import re

from .ingest import extract_facts
from .models import DeckSpec, SlideSpec, SourceBundle, SourceUnit
from .recipes import RECIPES
from .charts import validate_chart_content


def _short_heading(text: str, limit: int = 24) -> str:
    candidate = re.split(r"[。:：、，,]", text, maxsplit=1)[0].strip()
    term_action = re.search(
        r"([A-Za-z][A-Za-z ]{2,}を(?:選択|分類|決定|確認|解析|生成|停止|禁止|実行))",
        candidate,
    )
    if term_action:
        candidate = term_action.group(1).strip()
    else:
        subject = re.match(r"^(.{2,30}?)(?:は|が)", candidate)
        if subject:
            candidate = re.sub(r"^(?:説明できない|解決できない)", "", subject.group(1)).strip()
            if "の" in candidate:
                suffix = candidate.split("の", 1)[1].strip()
                if len(suffix) >= 4:
                    candidate = suffix
    if len(candidate) <= limit:
        return candidate
    return candidate[: limit - 1].rstrip() + "…"


def _groups(bundle: SourceBundle) -> tuple[SourceUnit | None, list[tuple[SourceUnit | None, list[SourceUnit]]]]:
    root: SourceUnit | None = None
    groups: list[tuple[SourceUnit | None, list[SourceUnit]]] = []
    current_heading: SourceUnit | None = None
    current_units: list[SourceUnit] = []

    def flush() -> None:
        nonlocal current_heading, current_units
        if current_heading is not None or current_units:
            groups.append((current_heading, current_units))
        current_heading = None
        current_units = []

    for unit in bundle.units:
        level = int(unit.metadata.get("level", 0)) if unit.kind == "heading" else 0
        if unit.kind == "heading" and level == 1 and root is None:
            root = unit
            continue
        if unit.kind == "heading" and level in {1, 2}:
            flush()
            current_heading = unit
            continue
        current_units.append(unit)
    flush()
    return root, groups


def _chunks(units: list[SourceUnit], size: int = 4) -> list[list[SourceUnit]]:
    output: list[list[SourceUnit]] = []
    pending: list[SourceUnit] = []
    for unit in units:
        if unit.kind == "table":
            if pending:
                output.append(pending)
                pending = []
            output.append([unit])
            continue
        pending.append(unit)
        if len(pending) >= size:
            output.append(pending)
            pending = []
    if pending:
        output.append(pending)
    return output


def _recipe_for(title: str, units: list[SourceUnit]) -> str:
    if any(unit.kind == "table" for unit in units):
        return "table"
    if any(keyword in title for keyword in ("次のステップ", "お問い合わせ", "まとめ", "連絡先")):
        return "closing_cta"
    if units and sum(unit.kind == "numbered_item" for unit in units) >= max(2, len(units) - 1):
        return "process"
    if len(units) == 4:
        return "card_grid_2x2"
    if len(units) == 3:
        return "three_column"
    if len(units) == 2 and units[-1].classification in {"note", "condition"}:
        return "title_body_callout"
    if len(units) == 2:
        return "two_column_equal"
    if len(units) == 1 and len(units[0].semantic_text) <= 140:
        return "statement"
    return "title_body"


def _content_for(recipe: str, units: list[SourceUnit]) -> dict[str, Any]:
    if recipe == "table":
        unit = next(item for item in units if item.kind == "table")
        return {"columns": unit.metadata.get("columns", []), "rows": unit.metadata.get("rows", [])}
    if recipe == "process":
        return {"steps": [{"heading": _short_heading(unit.semantic_text, 16), "body": unit.semantic_text} for unit in units]}
    if recipe == "card_grid_2x2":
        return {"cards": [{"heading": _short_heading(unit.semantic_text), "body": unit.semantic_text} for unit in units]}
    if recipe in {"two_column_equal", "three_column"}:
        return {"columns": [{"heading": _short_heading(unit.semantic_text), "body": unit.semantic_text, "items": [unit.semantic_text]} for unit in units]}
    if recipe == "title_body_callout":
        return {
            "bullets": [unit.semantic_text for unit in units[:-1]],
            "callout": {"heading": _short_heading(units[-1].semantic_text), "body": units[-1].semantic_text},
        }
    if recipe == "closing_cta":
        return {"body": units[0].semantic_text if units else "", "actions": [unit.semantic_text for unit in units[1:]]}
    if recipe == "statement":
        return {"statement": units[0].semantic_text if units else ""}
    return {"bullets": [unit.semantic_text for unit in units]}


def build_deterministic_deck(bundle: SourceBundle) -> DeckSpec:
    root, groups = _groups(bundle)
    title = root.semantic_text if root else bundle.files[0].filename
    slides: list[SlideSpec] = []
    if root:
        slides.append(
            SlideSpec(
                "S001",
                root.semantic_text,
                "",
                "cover",
                [root.unit_id],
                {"subtitle": "", "meta": ""},
            )
        )
    slide_number = len(slides) + 1
    for heading, units in groups:
        if not units and heading:
            slides.append(
                SlideSpec(
                    f"S{slide_number:03d}",
                    heading.semantic_text,
                    "",
                    "section",
                    [heading.unit_id],
                    {},
                )
            )
            slide_number += 1
            continue
        section_title = heading.semantic_text if heading else "概要"
        chunks = _chunks(units)
        for chunk_index, chunk in enumerate(chunks):
            recipe = _recipe_for(section_title, chunk)
            source_ids = ([heading.unit_id] if heading and chunk_index == 0 else []) + [unit.unit_id for unit in chunk]
            suffix = f"（{chunk_index + 1}）" if len(chunks) > 1 else ""
            message = chunk[0].semantic_text if chunk and chunk[0].kind != "table" else ""
            slides.append(
                SlideSpec(
                    f"S{slide_number:03d}",
                    f"{section_title}{suffix}",
                    message,
                    recipe,
                    source_ids,
                    _content_for(recipe, chunk),
                )
            )
            slide_number += 1
    return DeckSpec(title, slides, {"planner": "deterministic_fallback", "source_count": len(bundle.files)})


def build_planning_request(bundle: SourceBundle, content_model: dict[str, Any], coverage_requirements: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": bundle.schema_version,
        "planning_surface": "signed_in_host_ai",
        "instructions": [
            "Use one primary message and 2-5 supporting units per normal slide.",
            "Use only the available recipe IDs.",
            "Reference source_unit_ids; preserve every required fact exactly.",
            "Do not invent facts, numbers, dates, prices, or conditions.",
            "Do not emit absolute coordinates.",
        ],
        "available_recipes": sorted(RECIPES),
        "content_model": content_model,
        "coverage_requirements": coverage_requirements,
        "expected_output": {
            "title": "string",
            "metadata": {"planner": "host_ai"},
            "slides": [
                {
                    "slide_id": "S001",
                    "title": "string",
                    "message": "string",
                    "recipe": "one available recipe ID",
                    "source_unit_ids": ["U-..."],
                    "content": "recipe-specific object",
                }
            ],
        },
    }


def _deck_strings(deck: DeckSpec) -> str:
    return json.dumps(deck.to_dict(), ensure_ascii=False)


def validate_deck_against_sources(deck: DeckSpec, bundle: SourceBundle, coverage_requirements: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    valid_ids = {unit.unit_id for unit in bundle.units}
    required_ids = set(coverage_requirements["required_unit_ids"])
    referenced_ids = {unit_id for slide in deck.slides for unit_id in slide.source_unit_ids}
    unknown_ids = sorted(referenced_ids - valid_ids)
    missing_required = sorted(required_ids - referenced_ids)
    missing_all = sorted(valid_ids - referenced_ids)
    deck_text = _deck_strings(deck)
    missing_facts = [item for item in coverage_requirements["required_facts"] if item["value"] not in deck_text]
    source_facts = {fact for unit in bundle.units for fact in unit.facts}
    output_facts = set(extract_facts(deck_text))
    unsupported_facts = sorted(output_facts - source_facts)
    invalid_recipes = sorted({slide.recipe for slide in deck.slides if slide.recipe not in RECIPES})
    duplicate_slide_ids = sorted({slide.slide_id for slide in deck.slides if sum(item.slide_id == slide.slide_id for item in deck.slides) > 1})
    recipe_content_errors: list[dict[str, Any]] = []
    for slide in deck.slides:
        content = slide.content
        count_rules = {
            "card_grid_2x2": ("cards", 3, 4),
            "two_column_equal": ("columns", 2, 2),
            "three_column": ("columns", 3, 3),
            "process": ("steps", 2, 5),
        }
        if slide.recipe in count_rules:
            field, minimum, maximum = count_rules[slide.recipe]
            count = len(content.get(field, []))
            if not minimum <= count <= maximum:
                recipe_content_errors.append({"slide_id": slide.slide_id, "recipe": slide.recipe, "field": field, "expected": [minimum, maximum], "actual": count})
        if slide.recipe == "table" and (not content.get("columns") or not content.get("rows")):
            recipe_content_errors.append({"slide_id": slide.slide_id, "recipe": slide.recipe, "field": "columns/rows", "expected": "non-empty", "actual": "empty"})
        if slide.recipe in {"native_bar_chart", "native_chart"}:
            chart = content.get("chart", {})
            chart_errors = validate_chart_content(chart)
            if chart_errors:
                recipe_content_errors.append({"slide_id": slide.slide_id, "recipe": slide.recipe, "field": "chart", "expected": "a supported editable native chart contract", "actual": chart, "errors": chart_errors})
        if slide.recipe == "generated_visual":
            visual = content.get("visual", {})
            required_text = visual.get("required_text")
            if visual.get("type") not in {"chart", "flow"} or not visual.get("prompt") or not isinstance(required_text, list) or not required_text:
                recipe_content_errors.append({"slide_id": slide.slide_id, "recipe": slide.recipe, "field": "visual", "expected": "type chart|flow, a concrete prompt, and non-empty required_text", "actual": visual})
    errors: list[dict[str, Any]] = []
    for code, values, message in (
        ("unknown_source_unit", unknown_ids, "slide plan references unknown source units"),
        ("missing_required_unit", missing_required, "required source units are not covered"),
        ("missing_exact_fact", missing_facts, "required exact facts are absent from display content"),
        ("unsupported_fact", unsupported_facts, "deck contains facts not found in the source"),
        ("invalid_recipe", invalid_recipes, "deck uses unsupported recipes"),
        ("duplicate_slide_id", duplicate_slide_ids, "deck contains duplicate slide IDs"),
        ("invalid_recipe_content", recipe_content_errors, "recipe-specific required content is invalid"),
    ):
        if values:
            errors.append({"category": "Content", "code": code, "severity": "blocking", "message": message, "items": values})
    coverage_map = {
        "schema_version": bundle.schema_version,
        "all_unit_ids": sorted(valid_ids),
        "required_unit_ids": sorted(required_ids),
        "covered_unit_ids": sorted(referenced_ids & valid_ids),
        "missing_unit_ids": missing_all,
        "missing_required_unit_ids": missing_required,
        "all_unit_coverage": round(len(referenced_ids & valid_ids) / max(1, len(valid_ids)), 4),
        "required_unit_coverage": round(len(required_ids & referenced_ids) / max(1, len(required_ids)), 4),
        "dispositions": [
            {
                "unit_id": unit.unit_id,
                "disposition": "adopted" if unit.unit_id in referenced_ids else "unassigned",
                "slide_ids": [slide.slide_id for slide in deck.slides if unit.unit_id in slide.source_unit_ids],
            }
            for unit in bundle.units
        ],
    }
    report = {
        "schema_version": bundle.schema_version,
        "status": "PASS" if not errors else "FAIL",
        "summary": {
            "error_count": len(errors),
            "required_unit_coverage": coverage_map["required_unit_coverage"],
            "all_unit_coverage": coverage_map["all_unit_coverage"],
            "missing_exact_fact_count": len(missing_facts),
            "unsupported_fact_count": len(unsupported_facts),
        },
        "findings": errors,
    }
    return coverage_map, report
