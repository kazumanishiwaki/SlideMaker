from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

from .models import SourceBundle


def build_content_model(bundle: SourceBundle) -> dict[str, Any]:
    classifications = Counter(unit.classification for unit in bundle.units)
    kinds = Counter(unit.kind for unit in bundle.units)
    return {
        "schema_version": bundle.schema_version,
        "source_ids": [item.source_id for item in bundle.files],
        "unit_count": len(bundle.units),
        "required_unit_count": sum(1 for unit in bundle.units if unit.required),
        "classification_counts": dict(sorted(classifications.items())),
        "kind_counts": dict(sorted(kinds.items())),
        "units": [
            {
                **asdict(unit),
                "disposition": "UNPLANNED",
                "display_constraints": {
                    "preserve_exact_facts": bool(unit.facts),
                    "may_paraphrase": not unit.required,
                },
            }
            for unit in bundle.units
        ],
    }


def build_coverage_requirements(bundle: SourceBundle) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    for unit in bundle.units:
        for fact in unit.facts:
            facts.append({"unit_id": unit.unit_id, "value": fact, "match": "exact"})
    return {
        "schema_version": bundle.schema_version,
        "all_unit_ids": [unit.unit_id for unit in bundle.units],
        "required_unit_ids": [unit.unit_id for unit in bundle.units if unit.required],
        "required_facts": facts,
        "rules": {
            "required_unit_coverage": 1.0,
            "exact_fact_coverage": 1.0,
            "unsupported_fact_count": 0,
            "every_unit_requires_disposition": True,
        },
    }
