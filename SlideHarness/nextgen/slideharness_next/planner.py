from __future__ import annotations

from .models import DeckSpec, LayoutPlan
from .recipes import plan_slide


def plan_deck(deck: DeckSpec) -> list[LayoutPlan]:
    plans = [plan_slide(slide) for slide in deck.slides]
    seen: set[str] = set()
    for plan in plans:
        if plan.slide_id in seen:
            raise ValueError(f"duplicate slide_id: {plan.slide_id}")
        seen.add(plan.slide_id)
    return plans


def build_coverage_map(deck: DeckSpec, plans: list[LayoutPlan]) -> dict:
    covered = {unit for plan in plans for unit in plan.source_unit_ids}
    declared = {unit for slide in deck.slides for unit in slide.source_unit_ids}
    return {
        "declared_source_unit_ids": sorted(declared),
        "covered_source_unit_ids": sorted(covered),
        "uncovered_source_unit_ids": sorted(declared - covered),
        "coverage_ratio": round(len(covered) / max(1, len(declared)), 3),
        "slides": [
            {"slide_id": plan.slide_id, "recipe": plan.recipe, "source_unit_ids": plan.source_unit_ids}
            for plan in plans
        ],
    }
