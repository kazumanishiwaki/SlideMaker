from __future__ import annotations
from pathlib import Path
from typing import Any
import json

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / 'skill' / 'schemas'


def validate_json(instance: Any, schema_name: str) -> None:
    """Validate Codex-authored intermediate JSON before deterministic code consumes it."""
    schema_path = SCHEMA_ROOT / schema_name
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    try:
        from jsonschema import Draft202012Validator
    except ImportError as e:
        raise RuntimeError('jsonschema is required to validate Codex-authored planning files') from e
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    rendered=[]
    for e in errors[:12]:
        loc='.'.join(str(x) for x in e.absolute_path) or '<root>'
        rendered.append(f'{loc}: {e.message}')
    more=f' (+{len(errors)-12} more)' if len(errors)>12 else ''
    raise ValueError(f'{schema_name} validation failed: ' + '; '.join(rendered) + more)


def validate_slide_plan(plan: dict[str, Any]) -> None:
    validate_json(plan, 'slide_plan.schema.json')


def validate_slide_plans(document: dict[str, Any]) -> None:
    validate_json(document, 'slide_plans.schema.json')


def validate_image_recipes(document: dict[str, Any]) -> None:
    validate_json(document, 'image_recipe.schema.json')


def validate_deck_art_direction(document: dict[str, Any]) -> None:
    validate_json(document, 'deck_art_direction.schema.json')


def validate_image_manifest(document: dict[str, Any]) -> None:
    validate_json(document, 'image_asset_manifest.schema.json')
