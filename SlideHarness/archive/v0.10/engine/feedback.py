from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any

from helpers import append_jsonl, now_iso, read_json, write_json
from planning import compile_plan_bundle, load_slide_plan_bundle, project_legacy_views, write_slide_plan_bundle
from state import ensure_slide, load_state, save_state


def _stale(slide: dict[str, str], phases: list[str]) -> None:
    for phase in phases:
        slide[phase] = 'STALE_LOCKED' if slide.get(phase) == 'LOCKED' else 'STALE'


def _snapshot(root: Path, slide_id: str, kind: str, before: Any) -> None:
    append_jsonl(root / 'decisions/version_history.jsonl', {
        'version_id': f'VER-{now_iso()}', 'timestamp': now_iso(), 'slide_id': slide_id,
        'kind': kind, 'before': before,
    })


def _trace(root: Path, slide_id: str, kind: str, selected: Any, previous: Any, rerun: list[str]) -> None:
    # Compact trace: key decisions and user overrides only.  Geometry/font nudges are
    # intentionally excluded unless debug logging is enabled elsewhere.
    append_jsonl(root / 'decisions/decision_trace.jsonl', {
        'decision_id': f'USER-{now_iso()}', 'timestamp': now_iso(), 'phase': 'feedback',
        'target': {'type': 'slide', 'id': slide_id}, 'decision_type': kind,
        'selected': selected, 'previous': previous, 'origin': 'user', 'rerun_scope': rerun,
    })


def _bundle_row(root: Path, slide_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = load_slide_plan_bundle(root)
    row = next((x for x in bundle.get('slides', []) if x.get('slide_id') == slide_id), None)
    if not row:
        raise ValueError('slide not found in slide plan bundle')
    return bundle, row


def _save_bundle(root: Path, bundle: dict[str, Any]) -> None:
    write_slide_plan_bundle(root, bundle.get('slides', []), status=bundle.get('status') or 'DRAFT')
    project_legacy_views(root)
    compiled = compile_plan_bundle(root)
    if compiled.get('blocking_count'):
        raise ValueError('semantic layout validation failed after feedback')


def apply_feedback(project: str | Path, slide_id: str, kind: str, value: Any) -> dict[str, Any]:
    root = Path(project)
    state = load_state(root)
    ss = ensure_slide(state, slide_id)
    if any(v in {'LOCKED', 'STALE_LOCKED'} for v in ss.values()):
        raise ValueError('slide is locked')

    previous: Any
    phases: list[str]

    if kind == 'primary_message':
        deck = read_json(root / 'planning/deck_plan.json', {'slides': []})
        deck_row = next((x for x in deck.get('slides', []) if x.get('slide_id') == slide_id), None)
        if not deck_row:
            raise ValueError('slide not found in deck plan')
        bundle, row = _bundle_row(root, slide_id)
        previous = deck_row.get('primary_message')
        _snapshot(root, slide_id, kind, {'deck': deepcopy(deck_row), 'slide_plan': deepcopy(row)})
        text = str(value).strip()
        deck_row['primary_message'] = text
        deck_row['origin'] = 'user_override'
        row['message'] = text
        row['status'] = 'STALE'
        row['origin'] = 'user_override'
        write_json(root / 'planning/deck_plan.json', deck)
        _save_bundle(root, bundle)
        phases = ['slide_plan', 'image', 'layout', 'render', 'qa']

    elif kind == 'visual_type':
        bundle, row = _bundle_row(root, slide_id)
        previous = deepcopy(row.get('visual'))
        _snapshot(root, slide_id, kind, deepcopy(row))
        row.setdefault('visual', {})['type'] = str(value).strip()
        row['origin'] = 'user_override'
        _save_bundle(root, bundle)
        phases = ['slide_plan', 'image', 'layout', 'render', 'qa']

    elif kind == 'source_slide':
        bundle, row = _bundle_row(root, slide_id)
        previous = deepcopy(row.get('source'))
        _snapshot(root, slide_id, kind, deepcopy(row))
        row.setdefault('source', {})['slide_id'] = str(value).strip()
        row['origin'] = 'user_override'
        _save_bundle(root, bundle)
        phases = ['slide_plan', 'image', 'layout', 'render', 'qa']

    elif kind in {'layout_family', 'layout_density'}:
        bundle, row = _bundle_row(root, slide_id)
        previous = deepcopy(row.get('layout'))
        _snapshot(root, slide_id, kind, deepcopy(row))
        layout = row.setdefault('layout', {})
        if kind == 'layout_family':
            layout['family'] = str(value).strip()
        else:
            layout['density'] = str(value).strip()
        row['origin'] = 'user_override'
        _save_bundle(root, bundle)
        phases = (['image'] if kind == 'layout_family' else []) + ['layout', 'render', 'qa']

    elif kind == 'render_text':
        bundle, row = _bundle_row(root, slide_id)
        runtime = row.setdefault('runtime', {})
        blocks = runtime.setdefault('content_blocks', [])
        block_id = str(value.get('block_id') or '').strip()
        text = str(value.get('text') or '')
        block = next((x for x in blocks if x.get('id') == block_id), None)
        if not block:
            raise ValueError('content block not found')
        previous = block.get('render_text')
        _snapshot(root, slide_id, kind, deepcopy(block))
        # Presentation copy only.  Never promote it to semantic/source text.
        block['render_text'] = text
        block['render_adjustment'] = 'user_display_copy'
        row['origin'] = 'user_override'
        _save_bundle(root, bundle)
        phases = ['layout', 'render', 'qa']

    elif kind == 'semantic_chunks':
        bundle, row = _bundle_row(root, slide_id)
        previous = deepcopy(row.get('semantic_chunks'))
        _snapshot(root, slide_id, kind, deepcopy(row))
        chunks = value if isinstance(value, list) else str(value).splitlines()
        row['semantic_chunks'] = [str(x).strip() for x in chunks if str(x).strip()]
        row['origin'] = 'user_override'
        _save_bundle(root, bundle)
        phases = ['layout', 'render', 'qa']

    else:
        raise ValueError(f'unknown feedback kind: {kind}')

    _stale(ss, phases)
    state['deck_harmony'] = 'STALE'
    save_state(root, state)
    rerun = [f'{slide_id}:{p}' for p in phases] + ['deck_harmony']
    _trace(root, slide_id, kind, value, previous, rerun)
    return {
        'slide_id': slide_id,
        'kind': kind,
        'previous': previous,
        'selected': value,
        'rerun_scope': rerun,
        'state': state,
    }
