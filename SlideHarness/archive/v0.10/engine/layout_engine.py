from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from copy import deepcopy
from functools import lru_cache
import math
import os
import re

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.chart.data import ChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR, MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
from PIL import Image

from helpers import now_iso, read_json, write_json, append_jsonl
from picture_ops import replace_picture, move_shape_to_back
from state import ensure_slide, load_state, save_state
from japanese_typography import fit_font_size, prepare_display_text, render_safety_factor
from planning import renderer_group, semantic_layout_issues

EMU_PER_INCH = 914400
OBJ_RE = re.compile(r'-O(\d+)$')

FILL_POLICY_MODES = {
    'preserve_source',
    'intentional_whitespace',
    'balanced',
    'content_filled',
    'full_bleed',
}

INTENTIONAL_WHITESPACE_ROLES = {
    'cover', 'section', 'statement', 'quote', 'closing', 'cta', 'single_kpi',
}
CONTENT_FILLED_ROLES = {
    'comparison', 'comparison_table', 'comparison_matrix', 'process', 'timeline', 'table', 'chart',
    'three_items', 'four_items', 'grid', 'organization', 'two_column', 'relationship', 'relationship_diagram',
}
PHOTO_LED_ROLES = {'photo', 'photo_text', 'photo_grid', 'case_study', 'product', 'full_bleed', 'visual', 'illustration', 'screenshot', 'conceptual_image'}
SUPPORTED_LAYOUT_FAMILIES = {
    'grid', 'process', 'statement', 'two_column', 'photo_text', 'full_bleed',
    'comparison_matrix', 'relationship', 'timeline', 'kpi', 'chart',
    'cover', 'section', 'closing',
}


def _sid(object_id: str | None) -> int | None:
    m = OBJ_RE.search(object_id or '')
    return int(m.group(1)) if m else None


def _in(emu: int | float) -> float:
    return float(emu) / EMU_PER_INCH


def _emu(inches: float) -> int:
    return int(round(float(inches) * EMU_PER_INCH))


def _hex_color(value: str | None, fallback: str) -> RGBColor:
    raw = (value or fallback).replace('#', '').strip()
    if len(raw) != 6:
        raw = fallback
    return RGBColor(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def as_dict(self) -> dict[str, float]:
        return {k: round(getattr(self, k), 4) for k in ('x', 'y', 'w', 'h')}


def _union(boxes: list[Box]) -> Box | None:
    if not boxes:
        return None
    x0 = min(b.x for b in boxes); y0 = min(b.y for b in boxes)
    x1 = max(b.right for b in boxes); y1 = max(b.bottom for b in boxes)
    return Box(x0, y0, x1-x0, y1-y0)


def _density_settings(density: str) -> dict[str, float]:
    return {
        'airy': {'gap': 0.34, 'body_fill': 0.78, 'card_pad': 0.28, 'target_area': 0.44},
        'medium_low': {'gap': 0.26, 'body_fill': 0.86, 'card_pad': 0.24, 'target_area': 0.54},
        'medium': {'gap': 0.20, 'body_fill': 0.88, 'card_pad': 0.20, 'target_area': 0.58},
        'dense': {'gap': 0.14, 'body_fill': 0.94, 'card_pad': 0.16, 'target_area': 0.64},
    }.get(density, {'gap': 0.26, 'body_fill': 0.80, 'card_pad': 0.24, 'target_area': 0.50})


def _parse_design(root: Path) -> dict[str, Any]:
    path = root / 'inputs/design.md'
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        text = ''

    def find(name: str, default: str) -> str:
        m = re.search(rf'(?im)^\s*[-*]?\s*{re.escape(name)}\s*:\s*([a-zA-Z0-9_-]+)', text)
        return m.group(1).strip() if m else default

    def find_bool(name: str, default: bool) -> bool:
        raw = find(name, 'true' if default else 'false').lower()
        return raw in {'true', 'yes', 'on', '1'}

    role_policy: dict[str, str] = {}
    for role in sorted(INTENTIONAL_WHITESPACE_ROLES | CONTENT_FILLED_ROLES | PHOTO_LED_ROLES | {'overview'}):
        value = find(role, '')
        if value in FILL_POLICY_MODES:
            role_policy[role] = value

    default_policy = find('default_fill_policy', 'balanced')
    if default_policy not in FILL_POLICY_MODES:
        default_policy = 'balanced'

    return {
        'density': find('density', 'medium_low'),
        'whitespace': find('whitespace', 'generous'),
        'default_fill_policy': default_policy,
        'allow_intentional_whitespace': find_bool('allow_intentional_whitespace', True),
        'preserve_source_whitespace': find_bool('preserve_source_whitespace', True),
        'forbid_filler_content': find_bool('forbid_filler_content', True),
        'fill_policy_by_role': role_policy,
    }


def _deck_role(root: Path, slide_id: str | None) -> str | None:
    if not slide_id:
        return None
    deck = read_json(root / 'planning/deck_plan.json', {})
    slide = next((x for x in deck.get('slides', []) if x.get('slide_id') == slide_id), None)
    role = slide.get('role') if slide else None
    return str(role).strip() if role else None


def _normalize_fill_policy(value: Any, *, source: str, reason: list[str] | None = None) -> dict[str, Any] | None:
    if isinstance(value, str):
        mode = value.strip()
        payload: dict[str, Any] = {}
    elif isinstance(value, dict):
        mode = str(value.get('mode') or '').strip()
        payload = dict(value)
    else:
        return None
    if mode not in FILL_POLICY_MODES:
        return None
    reasons = payload.get('reason')
    if isinstance(reasons, str):
        reasons = [reasons]
    if not isinstance(reasons, list):
        reasons = list(reason or [])
    return {
        'mode': mode,
        'source': str(payload.get('source') or source),
        'reason': [str(x) for x in reasons if str(x).strip()],
        'preserve_empty_zones': bool(payload.get('preserve_empty_zones', mode in {'preserve_source', 'intentional_whitespace'})),
    }


def _resolve_fill_policy(root: Path, slide_plan: dict[str, Any], request: dict[str, Any], family: str, design: dict[str, Any]) -> dict[str, Any]:
    role = _deck_role(root, slide_plan.get('slide_id'))

    def finalize(policy: dict[str, Any]) -> dict[str, Any]:
        mode = policy.get('mode') or 'balanced'
        if mode == 'intentional_whitespace' and not design.get('allow_intentional_whitespace', True):
            policy = {
                'mode': 'balanced', 'source': 'design_guard',
                'reason': list(policy.get('reason') or []) + ['design.md disables intentional whitespace'],
                'preserve_empty_zones': False,
            }
        elif mode == 'preserve_source' and not design.get('preserve_source_whitespace', True):
            policy = {
                'mode': 'balanced', 'source': 'design_guard',
                'reason': list(policy.get('reason') or []) + ['design.md disables source-whitespace preservation'],
                'preserve_empty_zones': False,
            }
        return {
            **policy,
            'role': role,
            'forbid_filler_content': bool(design.get('forbid_filler_content', True)),
        }

    explicit = _normalize_fill_policy(slide_plan.get('fill_policy'), source='slide_plan')
    if explicit is None:
        explicit = _normalize_fill_policy(request.get('fill_policy'), source='layout_request')
    if explicit is not None:
        return finalize(explicit)

    role_map = design.get('fill_policy_by_role') or {}
    if role and role_map.get(role) in FILL_POLICY_MODES:
        return finalize({
            'mode': role_map[role], 'source': 'design_role',
            'reason': [f'design.md policy for role: {role}'],
            'preserve_empty_zones': role_map[role] in {'preserve_source', 'intentional_whitespace'},
        })

    if family in {'statement','cover','section','closing'} or role in INTENTIONAL_WHITESPACE_ROLES:
        return finalize({
            'mode': 'intentional_whitespace', 'source': 'auto_role',
            'reason': [f'{role or family} is message-led and benefits from deliberate whitespace'],
            'preserve_empty_zones': True,
        })
    if family == 'full_bleed':
        return finalize({
            'mode': 'full_bleed', 'source': 'auto_role',
            'reason': ['the primary visual intentionally occupies the slide while template chrome remains above it'],
            'preserve_empty_zones': False,
        })
    if family == 'photo_text' or role in PHOTO_LED_ROLES:
        return finalize({
            'mode': 'balanced', 'source': 'auto_role',
            'reason': [f'{role or family} balances a primary visual with a readable text cluster'],
            'preserve_empty_zones': False,
        })
    if family in {'grid', 'process', 'two_column', 'comparison_matrix', 'relationship', 'timeline', 'kpi', 'chart'} or role in CONTENT_FILLED_ROLES:
        return finalize({
            'mode': 'content_filled', 'source': 'auto_role',
            'reason': [f'{role or family} requires overview and comparison across multiple elements'],
            'preserve_empty_zones': False,
        })

    mode = design.get('default_fill_policy') or 'balanced'
    return finalize({
        'mode': mode, 'source': 'design_default',
        'reason': ['default fill policy from design.md'],
        'preserve_empty_zones': mode in {'preserve_source', 'intentional_whitespace'},
    })



def _record_fill_policy_decision(
    root: Path,
    slide_plan: dict[str, Any],
    family: str,
    fill_policy: dict[str, Any],
    quality: dict[str, Any],
) -> None:
    """Append an idempotent effective fill-policy decision to the project trace.

    The Slide Plan remains the upstream source of truth. This record explains the
    effective policy used by the deterministic layout engine without promoting the
    rendered result back into planning data. Repeated composition with the same
    effective decision does not produce duplicate trace rows.
    """
    slide_id = str(slide_plan.get('slide_id') or '')
    if not slide_id:
        return
    # Compact mode records only user/design-guard decisions. Automatic fill
    # choices are reproducible from Slide Plan and do not need one trace row per
    # composition. Set SLIDEHARNESS_DEBUG_DECISIONS=1 to retain full diagnostics.
    if os.environ.get('SLIDEHARNESS_DEBUG_DECISIONS') != '1' and str(fill_policy.get('source') or '') not in {'user', 'design_guard'}:
        return
    mode = str(fill_policy.get('mode') or 'balanced')
    source = str(fill_policy.get('source') or 'system')
    role = fill_policy.get('role')
    quality_status = str(quality.get('status') or 'unknown')
    decision_key = f'layout-fill:{slide_id}:{family}:{role or "none"}:{mode}:{source}:{quality_status}'
    trace_path = root / 'decisions/decision_trace.jsonl'
    if trace_path.exists():
        try:
            # Trace files are intentionally append-only and small in the PoC. Reading
            # them here keeps composition idempotent without maintaining another index.
            for line in trace_path.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                try:
                    import json
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get('decision_key') == decision_key:
                    return
        except Exception:
            pass

    confidence_by_source = {
        'user': 1.0,
        'slide_plan': 0.98,
        'layout_request': 0.96,
        'design_role': 0.94,
        'design_guard': 0.99,
        'auto_role': 0.88,
        'design_default': 0.74,
        'system': 0.80,
    }
    append_jsonl(trace_path, {
        'decision_id': f'SYS-FILL-{slide_id}-{mode}-{quality_status}',
        'decision_key': decision_key,
        'timestamp': now_iso(),
        'phase': 'layout_planning',
        'target': {'type': 'slide', 'id': slide_id},
        'decision_type': 'effective_fill_policy',
        'selected': fill_policy,
        'alternatives': [
            {'value': candidate}
            for candidate in sorted(FILL_POLICY_MODES)
            if candidate != mode
        ],
        'reason_codes': list(quality.get('reason_codes') or []),
        'reason_text': ' / '.join(fill_policy.get('reason') or []) or 'effective policy resolved by layout engine',
        'confidence': confidence_by_source.get(source, 0.80),
        'origin': 'system',
        'quality': {
            'status': quality_status,
            'score': quality.get('score'),
            'intentional_whitespace': quality.get('intentional_whitespace'),
            'accidental_dead_space': quality.get('accidental_dead_space'),
        },
        'rerun_scope': [
            f'{slide_id}:layout',
            f'{slide_id}:render',
            f'{slide_id}:qa',
            'deck_harmony',
        ],
    })

def _clean_hex(value: str | None, fallback: str) -> str:
    raw = str(value or '').replace('#', '').strip().upper()
    return raw if re.fullmatch(r'[0-9A-F]{6}', raw) else fallback


def _theme(root: Path, source_slide_id: str | None = None) -> dict[str, str]:
    profile = read_json(root/'analysis/template_profile.json', {})
    fingerprint = read_json(root/'analysis/design_fingerprint.json', {})
    roles = fingerprint.get('color_roles') or {}
    colors = [x[0] for x in profile.get('visual_grammar',{}).get('text_colors',[]) if x and x[0]]
    observed_accent = next((c for c in colors if c not in {'000000','FFFFFF','111111'}), None)
    observed_dark = next((c for c in colors if c not in {'FFFFFF'}), None)
    accent = _clean_hex(roles.get('primary_accent') or observed_accent, 'FF9A42')
    dark = _clean_hex(roles.get('text_on_light') or observed_dark, '171717')
    light = _clean_hex(roles.get('text_on_dark'), 'FFFFFF')
    background_light = _clean_hex(roles.get('background_light'), 'FFFFFF')
    background_dark = _clean_hex(roles.get('background_dark'), '171717')
    tone = next((row for row in roles.get('source_slide_tones', []) if row.get('source_slide_id') == source_slide_id), None)
    page_background_dark = bool((tone or {}).get('background_is_dark'))
    page_background = _clean_hex((tone or {}).get('background_color'), background_dark if page_background_dark else background_light)
    return {
        'accent': accent,
        'secondary_accent': _clean_hex(roles.get('secondary_accent'), accent),
        'dark': dark,
        'light': light,
        'muted': 'A5A5A5',
        'line': 'D8D8D8',
        'background_light': background_light,
        'background_dark': background_dark,
        'page_background': page_background,
        'page_background_dark': page_background_dark,
        'page_text': light if page_background_dark else dark,
        'palette_source': str(roles.get('palette_source') or 'text_run_fallback'),
    }




def _project_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if path != root.resolve() and not str(path).startswith(str(root.resolve()) + os.sep):
        raise ValueError('asset path outside project')
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _image_documents(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        read_json(root / 'planning/image_recipes.json', {'schema_version': '0.2', 'recipes': []}),
        read_json(root / 'render/generated_assets/manifest.json', {'schema_version': '0.1', 'assets': [], 'selected_by_recipe': {}}),
    )


def _selected_image_asset(root: Path, recipe_id: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    recipes, manifest = _image_documents(root)
    recipe = next((row for row in recipes.get('recipes', []) if row.get('recipe_id') == recipe_id), None)
    if recipe is None:
        raise ValueError(f'image recipe not found: {recipe_id}')
    selected_id = recipe.get('selected_asset_id') or (manifest.get('selected_by_recipe') or {}).get(recipe_id)
    asset = next((row for row in manifest.get('assets', []) if row.get('asset_id') == selected_id), None)
    if not selected_id or asset is None:
        raise ValueError(f'image asset is not ready for layout slot: {recipe_id}')
    processed = asset.get('processed_path')
    if not processed:
        raise ValueError(f'processed image path missing for layout slot: {recipe_id}')
    return recipe, asset, _project_path(root, processed)


def _cover_crop(shape, image_path: Path, box: Box, focal_point: list[float] | tuple[float, float] | None = None) -> None:
    with Image.open(image_path) as image:
        iw, ih = image.size
    if iw <= 0 or ih <= 0 or box.w <= 0 or box.h <= 0:
        raise ValueError('invalid image or target box')
    try:
        fx = max(0.0, min(1.0, float((focal_point or [0.5, 0.5])[0])))
        fy = max(0.0, min(1.0, float((focal_point or [0.5, 0.5])[1])))
    except Exception:
        fx, fy = 0.5, 0.5
    target_ar = box.w / box.h
    image_ar = iw / ih
    shape.crop_left = shape.crop_right = 0.0
    shape.crop_top = shape.crop_bottom = 0.0
    if image_ar > target_ar:
        visible = max(0.001, min(1.0, target_ar / image_ar))
        start = max(0.0, min(1.0 - visible, fx - visible / 2))
        shape.crop_left = start
        shape.crop_right = max(0.0, 1.0 - (start + visible))
    elif image_ar < target_ar:
        visible = max(0.001, min(1.0, image_ar / target_ar))
        start = max(0.0, min(1.0 - visible, fy - visible / 2))
        shape.crop_top = start
        shape.crop_bottom = max(0.0, 1.0 - (start + visible))


def _move_shape_to_back(slide, shape) -> None:
    tree = slide.shapes._spTree
    element = shape.element
    tree.remove(element)
    # nvGrpSpPr and grpSpPr occupy the first two positions in p:spTree.
    tree.insert(min(2, len(tree)), element)


def _place_picture(
    slide,
    box: Box,
    image_path: Path,
    *,
    template_shape=None,
    focal_point: list[float] | tuple[float, float] | None = None,
    send_to_back: bool = False,
    add_border: bool = False,
    theme: dict[str, str] | None = None,
):
    """Place a visual into deterministic geometry.

    When a source Picture is supplied, keep the original PowerPoint picture
    element and replace its relationship in place. This preserves shape id,
    z-order, mask, outline, effect and rotation while allowing the layout
    engine to move the designed frame to a new semantic slot.
    """
    shape = template_shape if template_shape is not None and getattr(template_shape, 'shape_type', None) == MSO_SHAPE_TYPE.PICTURE else None
    if shape is not None:
        shape = replace_picture(
            slide, shape, image_path, fit_mode='cover',
            focal_point=focal_point, target_box=box,
        )
    else:
        shape = slide.shapes.add_picture(str(image_path), _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
        _cover_crop(shape, image_path, box, focal_point)
    if send_to_back:
        move_shape_to_back(shape)
    border = None
    if add_border:
        border = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
        border.fill.background()
        border.line.color.rgb = _hex_color((theme or {}).get('line'), 'D8D8D8')
        border.line.width = Pt(1.0)
    return shape, border


def _image_focal_point(asset: dict[str, Any]) -> list[float]:
    crop = ((asset.get('process') or {}).get('crop') or {})
    value = crop.get('focal_point') or [0.5, 0.5]
    try:
        return [max(0.0, min(1.0, float(value[0]))), max(0.0, min(1.0, float(value[1])))]
    except Exception:
        return [0.5, 0.5]

def _source_objects(root: Path, source_slide_id: str) -> dict[int, dict[str, Any]]:
    doc = read_json(root/'analysis/source_slides.json', {})
    slide = next((x for x in doc.get('slides',[]) if x.get('id') == source_slide_id), {})
    return {int(o['shape_id']): o for o in slide.get('objects',[]) if o.get('shape_id') is not None}


def _chrome_assets(root: Path, source_slide_id: str) -> list[dict[str, Any]]:
    assets = read_json(root/'analysis/source_assets.json', {})
    return [a for a in assets.get('assets',[]) if a.get('source_slide_id') == source_slide_id and a.get('classification') == 'template_chrome']


def _intersect(a: Box, b: Box) -> Box | None:
    x0=max(a.x,b.x); y0=max(a.y,b.y); x1=min(a.right,b.right); y1=min(a.bottom,b.bottom)
    if x1 <= x0 or y1 <= y0:
        return None
    return Box(x0,y0,x1-x0,y1-y0)


def _source_content_region(root: Path, source_slide_id: str, request: dict[str, Any], default_canvas: Box) -> Box | None:
    objects = _source_objects(root, source_slide_id)
    requested_ids = list(request.get('clear_region_object_ids') or [])
    chrome_ids = {_sid(a.get('source_object_id')) for a in _chrome_assets(root, source_slide_id)}
    boxes: list[Box] = []

    def add_object(obj: dict[str, Any]) -> None:
        bb=obj.get('bbox') or {}
        try:
            raw=Box(float(bb['x']),float(bb['y']),float(bb['w']),float(bb['h']))
        except Exception:
            return
        if raw.w <= 0 or raw.h <= 0:
            return
        clipped=_intersect(raw,default_canvas)
        if clipped and clipped.w*clipped.h >= default_canvas.w*default_canvas.h*0.002:
            boxes.append(clipped)

    if requested_ids:
        for oid in requested_ids:
            sid=_sid(oid)
            obj=objects.get(sid) if sid is not None else None
            if obj:
                add_object(obj)
    else:
        for sid,obj in objects.items():
            if sid in chrome_ids:
                continue
            # Prefer actual semantic/content objects; ignore tiny decorative fragments.
            if not (obj.get('text') or obj.get('picture') or obj.get('table') or obj.get('chart')):
                continue
            add_object(obj)

    union=_union(boxes)
    if union is None:
        return None
    if union.w*union.h < default_canvas.w*default_canvas.h*0.08:
        return None
    pad=min(0.22,max(0.08,min(default_canvas.w,default_canvas.h)*0.015))
    expanded=Box(union.x-pad,union.y-pad,union.w+2*pad,union.h+2*pad)
    return _intersect(expanded,default_canvas)


def _derive_canvas(root: Path, slide, source_slide_id: str, request: dict[str, Any], fill_policy: dict[str, Any] | None = None) -> Box:
    explicit = request.get('content_region')
    if isinstance(explicit, dict) and all(k in explicit for k in ('x','y','w','h')):
        return Box(*(float(explicit[k]) for k in ('x','y','w','h')))
    profile = read_json(root/'analysis/template_profile.json', {})
    pres = profile.get('presentation') or {}
    sw = float(pres.get('width_in') or 13.333)
    sh = float(pres.get('height_in') or 7.5)
    # The deck is unusually wide (26.67 x 15in in the reference file). Percent-based
    # margins scale better than hard-coded PowerPoint defaults.
    left = max(0.55, sw * 0.045); right = max(0.55, sw * 0.045)
    top = max(0.45, sh * 0.045); bottom = max(0.45, sh * 0.045)
    for a in _chrome_assets(root, source_slide_id):
        bb = a.get('bbox') or {}; x=float(bb.get('x',0)); y=float(bb.get('y',0)); w=float(bb.get('w',0)); h=float(bb.get('h',0))
        if w <= 0 or h <= 0: continue
        # Only reserve an edge when the chrome meaningfully spans that edge; tiny logos
        # should not shrink the entire usable canvas.
        if y < sh*0.09 and w > sw*0.30:
            top = max(top, y+h+max(0.12,sh*0.012))
        if y+h > sh*0.91 and w > sw*0.30:
            bottom = max(bottom, sh-y+max(0.12,sh*0.012))
        if x < sw*0.06 and h > sh*0.35:
            left = max(left, x+w+max(0.12,sw*0.008))
        if x+w > sw*0.94 and h > sh*0.35:
            right = max(right, sw-x+max(0.12,sw*0.008))
    if left + right > sw*0.72 or top + bottom > sh*0.72:
        raise ValueError('template chrome leaves insufficient content canvas')
    canvas=Box(left, top, sw-left-right, sh-top-bottom)
    if (fill_policy or {}).get('mode') == 'preserve_source':
        source_region=_source_content_region(root,source_slide_id,request,canvas)
        if source_region is not None:
            return source_region
    return canvas


def _style_from_shape(shape) -> dict[str, Any]:
    out = {'font_name': None, 'font_size_pt': None, 'bold': None, 'color': None, 'alignment': None}
    if shape is None or not getattr(shape, 'has_text_frame', False):
        return out
    for p in shape.text_frame.paragraphs:
        out['alignment'] = p.alignment
        for r in p.runs:
            if not r.text and r.font.name is None and r.font.size is None:
                continue
            out['font_name'] = r.font.name
            out['font_size_pt'] = r.font.size.pt if r.font.size else None
            out['bold'] = r.font.bold
            try:
                if r.font.color.rgb: out['color'] = str(r.font.color.rgb)
            except Exception:
                pass
            return out
    return out


def _font_candidates(slide) -> tuple[Any | None, Any | None]:
    texts=[]
    for sh in slide.shapes:
        if not getattr(sh,'has_text_frame',False) or not sh.text.strip(): continue
        style=_style_from_shape(sh); size=style.get('font_size_pt') or 0
        text=sh.text.strip()
        # Page numbers are often huge but very short. Exclude tiny numeric labels from title style.
        numeric_short=bool(re.fullmatch(r'[0-9０-９]{1,3}', text))
        texts.append((size, len(text), numeric_short, sh))
    title = max((x for x in texts if not x[2]), key=lambda x:(x[0],-x[1]), default=None)
    body = min((x for x in texts if x[0] >= 10 and x[1] >= 8), key=lambda x:abs(x[0]-20), default=None)
    return (title[3] if title else None, body[3] if body else (title[3] if title else None))


def _resolve_style_shapes(slide, request: dict[str,Any]) -> dict[str, Any]:
    by_id={s.shape_id:s for s in slide.shapes}
    auto_title, auto_body = _font_candidates(slide)
    src=request.get('style_source_object_ids') or {}
    def get(key, fallback):
        sid=_sid(src.get(key)); return by_id.get(sid) if sid is not None else fallback
    image_sid=_sid(src.get('image'))
    image_shape=by_id.get(image_sid) if image_sid is not None else None
    if image_shape is None:
        image_shape=next((shape for shape in slide.shapes if getattr(shape,'shape_type',None)==MSO_SHAPE_TYPE.PICTURE),None)
    return {
        'title': get('title',auto_title),
        'subtitle': get('subtitle',auto_body),
        'item_title': get('item_title',auto_title or auto_body),
        'item_body': get('item_body',auto_body),
        'number': get('number',auto_title or auto_body),
        'image': image_shape,
    }


def _apply_text_style(shape, text: str, source_shape, *, role: str, theme: dict[str,str], size_override: float | None=None, color_override: str | None=None, bold_override: bool | None=None, align=None, max_lines: int | None=None, min_font_pt: float | None=None):
    tf=shape.text_frame; tf.clear(); tf.word_wrap=True
    tf.margin_left=tf.margin_right=Inches(0)
    tf.margin_top=tf.margin_bottom=Inches(0)
    tf.vertical_anchor=MSO_ANCHOR.MIDDLE if role in {'number','kpi_value'} else MSO_ANCHOR.TOP
    p=tf.paragraphs[0]; p.alignment=align if align is not None else PP_ALIGN.LEFT
    r=p.add_run()
    snap=_style_from_shape(source_shape)
    f=r.font
    if snap.get('font_name'): f.name=snap['font_name']
    default_sizes={'title':38,'subtitle':20,'item_title':22,'item_body':17,'number':15,'kpi_value':42,'caption':12}
    preferred=float(size_override or snap.get('font_size_pt') or default_sizes.get(role,16))
    display_text=str(text)
    try:
        fit=fit_font_size(
            display_text, width_in=max(.2, _in(shape.width) * render_safety_factor(role)),
            height_in=_in(shape.height), preferred_pt=preferred, role=role,
            min_pt=min_font_pt, max_lines=max_lines,
        )
        resolved=fit.font_pt
        if fit.fits and role in {'title','subtitle','item_title','item_body','body','caption'}:
            display_text=prepare_display_text(
                display_text, width_in=_in(shape.width), font_pt=resolved,
                role=role, max_lines=fit.max_lines,
            )
    except Exception:
        resolved=preferred
    r.text=display_text
    f.size=Pt(float(resolved))
    f.bold=bold_override if bold_override is not None else (snap.get('bold') if snap.get('bold') is not None else role in {'title','item_title','number','kpi_value'})
    f.color.rgb=_hex_color(color_override or snap.get('color'), theme['dark'])


def _add_text(slide, box: Box, text: str, source_shape, role: str, theme: dict[str,str], **kw):
    sh=slide.shapes.add_textbox(_emu(box.x),_emu(box.y),_emu(box.w),_emu(box.h))
    _apply_text_style(sh,text,source_shape,role=role,theme=theme,**kw)
    return sh


def _add_rule(slide, x:float,y:float,w:float, theme:dict[str,str], width_pt=2.0):
    line=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,_emu(x),_emu(y),_emu(x+w),_emu(y))
    line.line.color.rgb=_hex_color(theme['accent'], 'FF9A42'); line.line.width=Pt(width_pt)
    return line


def _add_card(slide, box:Box, item:dict[str,Any], styles:dict[str,Any], theme:dict[str,str], pad:float, number_box=True) -> tuple[list[Any], list[Box]]:
    shapes=[]; boxes=[]
    bg=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,_emu(box.x),_emu(box.y),_emu(box.w),_emu(box.h))
    bg.fill.solid(); bg.fill.fore_color.rgb=_hex_color('FFFFFF','FFFFFF')
    bg.line.color.rgb=_hex_color(theme['line'],'D8D8D8'); bg.line.width=Pt(1.0)
    shapes.append(bg); boxes.append(box)
    title_y=box.y+pad; text_x=box.x+pad
    number=str(item.get('number','')).strip()
    if number and number_box:
        nb=min(0.55, max(0.38, box.h*0.11)); nbox=Box(text_x,title_y,nb,nb)
        nsh=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,_emu(nbox.x),_emu(nbox.y),_emu(nbox.w),_emu(nbox.h))
        nsh.fill.solid(); nsh.fill.fore_color.rgb=_hex_color(theme['accent'],'FF9A42'); nsh.line.fill.background()
        _apply_text_style(nsh,number,styles['number'],role='number',theme=theme,size_override=max(14,nb*21),color_override='FFFFFF',bold_override=True,align=PP_ALIGN.CENTER)
        shapes.append(nsh); boxes.append(nbox); title_y += nb + max(0.14,pad*0.6)
    title=str(item.get('title','')).strip()
    body=str(item.get('body','')).strip()
    if title:
        th=min(0.72,max(0.46,box.h*0.16)); tbox=Box(text_x,title_y,max(0.2,box.w-2*pad),th)
        tsh=_add_text(slide,tbox,title,styles['item_title'],'item_title',theme,size_override=max(22,min(28,th*31)),color_override=theme['dark'],bold_override=True)
        shapes.append(tsh); boxes.append(tbox); title_y += th + max(0.10,pad*0.45)
    if body:
        bbox=Box(text_x,title_y,max(0.2,box.w-2*pad),max(0.25,box.bottom-title_y-pad))
        bsh=_add_text(slide,bbox,body,styles['item_body'],'item_body',theme,size_override=max(17,min(22,bbox.h*7.8)),color_override=theme['dark'])
        shapes.append(bsh); boxes.append(bbox)
    _add_rule(slide,box.x+pad,box.y+box.h-min(pad*0.75,0.22),max(0.3,box.w-2*pad),theme,1.5)
    return shapes, boxes


def _add_open_column(
    slide, box: Box, item: dict[str, Any], styles: dict[str, Any],
    theme: dict[str, str], pad: float,
) -> tuple[list[Any], list[Box]]:
    """Render one editable comparison/explanation column.

    Open columns use a compact content cluster rather than a body textbox that
    extends to the bottom of the column. This makes short comparison copy feel
    intentionally placed instead of looking like an unfinished page, while the
    outer semantic columns still preserve the source deck's broad rhythm.
    """
    shapes: list[Any] = []
    boxes: list[Box] = []
    style = str(item.get('style') or 'open').lower()
    if style == 'card':
        panel = _add_panel(slide, box, theme, fill_color='FFF7F0', line_color='F1D2B8', opacity=1.0)
        shapes.append(panel); boxes.append(box)
    inner = Box(box.x + pad, box.y + pad, max(0.2, box.w - 2 * pad), max(0.2, box.h - 2 * pad))

    number = str(item.get('number') or '').strip()
    title = str(item.get('title') or '').strip()
    body = str(item.get('body') or '').strip()
    source_title_pt = float(_style_from_shape(styles['item_title']).get('font_size_pt') or 24.0)
    source_body_pt = float(_style_from_shape(styles['item_body']).get('font_size_pt') or 17.0)
    title_pt = max(22.0, min(36.0 if style == 'card' else 32.0, source_title_pt * (0.78 if style == 'card' else 0.68)))
    body_pt = max(16.0, min(24.0 if style == 'card' else 21.0, source_body_pt * (1.0 if style == 'card' else 0.90)))
    title_h = min(max(title_pt / 72.0 * 1.45, 0.58), inner.h * 0.24) if title else 0.0
    number_h = max(0.42, body_pt / 72.0 * 1.25) if number else 0.0
    # Estimate the visible body footprint from explicit and likely wrapped lines.
    # Real overflow remains guarded by PDF-bbox QA after PowerPoint rendering.
    explicit_lines = max(1, len(body.splitlines())) if body else 0
    compact_body = re.sub(r'\s+', '', body)
    approx_chars_per_line = max(8, int(inner.w * 4.8))
    wrapped_lines = math.ceil(len(compact_body) / approx_chars_per_line) if compact_body else 0
    body_lines = max(explicit_lines, wrapped_lines)
    line_height = body_pt / 72.0 * 1.42
    body_h = min(max(0.54, body_lines * line_height + 0.10), max(0.54, inner.h * 0.56)) if body else 0.0
    content_gap = 0.12
    cluster_h = 0.20  # accent rule + breathing room
    if number:
        cluster_h += number_h + 0.06
    if title:
        cluster_h += title_h + (content_gap if body else 0.0)
    if body:
        cluster_h += body_h
    cluster_h = min(inner.h, max(0.20, cluster_h))

    align = str(item.get('vertical_align') or 'center').lower()
    if align == 'bottom':
        y = inner.bottom - cluster_h
    elif align == 'center':
        y = inner.y + (inner.h - cluster_h) / 2
    else:
        y = inner.y

    rule = _add_rule(slide, inner.x, y, min(inner.w, max(1.2, inner.w * 0.42)), theme, 2.0)
    shapes.append(rule)
    y += 0.20
    if number:
        nbox = Box(inner.x, y, min(0.82, inner.w * 0.18), number_h)
        nsh = _add_text(
            slide, nbox, number, styles['number'], 'number', theme,
            size_override=max(13.0, body_pt * 0.78), color_override=theme['accent'], bold_override=True,
        )
        shapes.append(nsh); boxes.append(nbox); y = nbox.bottom + 0.06
    if title:
        tbox = Box(inner.x, y, inner.w, title_h)
        tsh = _add_text(
            slide, tbox, title, styles['item_title'], 'item_title', theme,
            size_override=title_pt, bold_override=True,
        )
        shapes.append(tsh); boxes.append(tbox); y = tbox.bottom + (content_gap if body else 0.0)
    if body:
        bbox = Box(inner.x, y, inner.w, min(body_h, max(0.28, inner.bottom - y)))
        bsh = _add_text(
            slide, bbox, body, styles['item_body'], 'item_body', theme,
            size_override=body_pt,
        )
        shapes.append(bsh); boxes.append(bbox)
    return shapes, boxes


def _choose_grid(n:int, body:Box, family:str) -> tuple[int,int]:
    if n <= 0: return (1,1)
    ratio=body.w/max(body.h,1e-6)
    if family == 'process' and n <= 5 and ratio >= 1.55:
        return (n,1)
    # Balanced complete grids are preferred for item layouts. A 3+1 composition for
    # four items creates an obvious dead quadrant, even when individual card aspect
    # ratios look numerically attractive.
    if family == 'grid':
        if n == 2: return (2,1)
        if n == 3: return (3,1) if ratio >= 1.55 else (2,2)
        if n == 4: return (4,1) if ratio >= 3.2 else (2,2)
        if n in {5,6}: return (3,2)
        if n in {7,8}: return (4,2)
    candidates=[]
    for cols in range(1,min(n,4)+1):
        rows=math.ceil(n/cols)
        card_w=body.w/cols; card_h=body.h/rows
        # Prefer readable wide-ish cards, while avoiding lonely last rows.
        aspect=card_w/max(card_h,1e-6)
        last=n-(rows-1)*cols
        ragged=(cols-last)/cols if rows>1 else 0
        score=-abs(math.log(max(aspect,0.05)/1.45))-ragged*0.35
        if card_w < 2.1: score -= (2.1-card_w)*2
        if card_h < 1.5: score -= (1.5-card_h)*2
        candidates.append((score,cols,rows))
    _,cols,rows=max(candidates,key=lambda x:x[0])
    return cols,rows


def _policy_scale(mode: str, family: str) -> tuple[float, float]:
    # width_scale, height_scale for the semantic body. These scales change actual
    # geometry, while fit-to-intent metrics decide whether the result is appropriate.
    table = {
        'content_filled': (1.00, 1.00),
        'balanced': (0.92, 0.88),
        'intentional_whitespace': (0.78, 0.72),
        'preserve_source': (1.00, 0.92),
        'full_bleed': (1.00, 1.00),
    }
    width_scale, height_scale = table.get(mode, table['balanced'])
    if family == 'process' and mode == 'intentional_whitespace':
        width_scale=max(width_scale,0.84)
    return width_scale,height_scale


def _header_boxes(canvas:Box, title:str, subtitle:str, density:str) -> tuple[Box|None,Box|None,Box]:
    gap=_density_settings(density)['gap']
    y=canvas.y
    title_box=None; subtitle_box=None
    if title:
        # Explicit semantic title lines are authored once in Slide Plan. Give them
        # enough vertical space rather than shrinking a meaningful two-line title.
        title_lines=max(1,min(2,len(str(title).splitlines())))
        title_h=min(max(0.70*title_lines,canvas.h*0.085*title_lines),1.18*title_lines)
        title_box=Box(canvas.x,y,canvas.w,title_h); y += title_h + min(0.16,gap*0.55)
    if subtitle:
        subtitle_h=min(max(0.38,canvas.h*0.045),0.62)
        subtitle_box=Box(canvas.x,y,canvas.w,subtitle_h); y += subtitle_h + min(0.24,gap*0.75)
    return title_box,subtitle_box,Box(canvas.x,y,canvas.w,max(0.1,canvas.bottom-y))


def _layout_grid(canvas:Box, request:dict[str,Any], density:str, fill_mode:str) -> dict[str,Any]:
    title=str(request.get('title','')).strip(); subtitle=str(request.get('subtitle','')).strip(); items=list(request.get('items') or [])
    tb,sb,body=_header_boxes(canvas,title,subtitle,density)
    settings=_density_settings(density); gap=settings['gap']
    cols,rows=_choose_grid(len(items),body,'grid')
    width_scale,height_scale=_policy_scale(fill_mode,'grid')
    work_w=body.w*width_scale; work_x=body.x+(body.w-work_w)/2
    # Fit card height to semantic content. content_filled means use the canvas well,
    # not inflate short copy into oversized empty cards.
    max_chars=max([len(str(i.get('title') or ''))+len(str(i.get('body') or '')) for i in items] or [0])
    semantic_fill=0.68 if max_chars <= 55 else 0.78 if max_chars <= 95 else settings['body_fill']
    body_h=body.h*min(settings['body_fill'],semantic_fill)*height_scale; body_y=body.y+(body.h-body_h)/2
    work=Box(work_x,body_y,work_w,body_h)
    cw=(work.w-gap*(cols-1))/cols; ch=(work.h-gap*(rows-1))/rows
    boxes=[]
    for i in range(len(items)):
        r=i//cols; c=i%cols
        # Center a ragged last row instead of leaving a large dead zone on one side.
        row_count=min(cols,len(items)-r*cols)
        row_w=row_count*cw+(row_count-1)*gap
        row_x=work.x+(work.w-row_w)/2
        boxes.append(Box(row_x+c*(cw+gap),work.y+r*(ch+gap),cw,ch))
    return {'title_box':tb,'subtitle_box':sb,'body':body,'item_boxes':boxes}


def _layout_process(canvas:Box, request:dict[str,Any], density:str, fill_mode:str) -> dict[str,Any]:
    title=str(request.get('title','')).strip(); subtitle=str(request.get('subtitle','')).strip(); items=list(request.get('items') or [])
    tb,sb,body=_header_boxes(canvas,title,subtitle,density)
    settings=_density_settings(density); gap=settings['gap']
    cols,rows=_choose_grid(len(items),body,'process')
    width_scale,height_scale=_policy_scale(fill_mode,'process')
    work_w=body.w*width_scale; work_x=body.x+(body.w-work_w)/2
    max_chars=max([len(str(i.get('title') or ''))+len(str(i.get('body') or '')) for i in items] or [0])
    if rows == 1:
        semantic_fill=0.36 if max_chars <= 45 else 0.50 if max_chars <= 80 else 0.64
        fill_factor=min(settings['body_fill'],semantic_fill)
    else:
        semantic_fill=0.70 if max_chars <= 55 else 0.80 if max_chars <= 95 else settings['body_fill']
        fill_factor=min(settings['body_fill'],semantic_fill)
    body_h=body.h*fill_factor*height_scale; body_y=body.y+(body.h-body_h)/2
    work=Box(work_x,body_y,work_w,body_h)
    cw=(work.w-gap*(cols-1))/cols; ch=(work.h-gap*(rows-1))/rows
    boxes=[]
    for i in range(len(items)):
        r=i//cols;c=i%cols
        row_count=min(cols,len(items)-r*cols); row_w=row_count*cw+(row_count-1)*gap; row_x=work.x+(work.w-row_w)/2
        boxes.append(Box(row_x+c*(cw+gap),work.y+r*(ch+gap),cw,ch))
    return {'title_box':tb,'subtitle_box':sb,'body':body,'item_boxes':boxes,'cols':cols,'rows':rows}


def _layout_statement(canvas:Box, request:dict[str,Any], density:str, fill_mode:str) -> dict[str,Any]:
    title=str(request.get('title','')).strip(); subtitle=str(request.get('subtitle','')).strip()
    # Statement slides may deliberately preserve whitespace. The policy changes the
    # message-cluster scale without ever adding filler content.
    width_ratio = {
        'intentional_whitespace': 0.68,
        'preserve_source': 0.72,
        'balanced': 0.78,
        'content_filled': 0.88,
        'full_bleed': 0.94,
    }.get(fill_mode,0.78)
    height_ratio = {
        'intentional_whitespace': 0.48 if subtitle else 0.36,
        'preserve_source': 0.50 if subtitle else 0.38,
        'balanced': 0.56 if subtitle else 0.44,
        'content_filled': 0.68 if subtitle else 0.56,
        'full_bleed': 0.76 if subtitle else 0.64,
    }.get(fill_mode,0.56 if subtitle else 0.44)
    width=canvas.w*width_ratio
    cluster_h=canvas.h*height_ratio
    x=canvas.x; y=canvas.y+(canvas.h-cluster_h)/2
    title_h=cluster_h*(0.55 if subtitle else 0.86)
    tb=Box(x,y,width,title_h)
    sb=Box(x,y+title_h+0.18,width*0.88,max(0.35,cluster_h-title_h-0.18)) if subtitle else None
    return {'title_box':tb,'subtitle_box':sb,'body':Box(x,y,width,cluster_h),'item_boxes':[]}




def _body_text(request: dict[str, Any]) -> str:
    body = str(request.get('body') or '').strip()
    bullets = request.get('bullets') or []
    if bullets:
        bullet_text = '\n'.join(f'• {str(item).strip()}' for item in bullets if str(item).strip())
        body = f'{body}\n{bullet_text}'.strip() if body else bullet_text
    return body


def _text_cluster(box: Box, request: dict[str, Any], density: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    body_text = _body_text(request)
    gap = _density_settings(density)['gap']
    y = box.y
    title_box = subtitle_box = body_box = None
    if title:
        title_h = min(max(0.72, box.h * (0.23 if body_text else 0.34)), max(0.72, box.h * 0.46))
        title_box = Box(box.x, y, box.w, title_h)
        y += title_h + min(0.18, gap * 0.60)
    if subtitle:
        subtitle_h = min(max(0.38, box.h * 0.105), max(0.38, box.h * 0.19))
        subtitle_box = Box(box.x, y, box.w, subtitle_h)
        y += subtitle_h + min(0.22, gap * 0.75)
    if body_text:
        body_box = Box(box.x, y, box.w, max(0.30, box.bottom - y))
    return {
        'title_box': title_box,
        'subtitle_box': subtitle_box,
        'body_box': body_box,
        'body_text': body_text,
        'body': box,
        'item_boxes': [],
    }


def _layout_photo_text(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    position = str(request.get('image_position') or 'right').lower()
    if position not in {'left', 'right', 'top', 'bottom'}:
        position = 'right'
    ratio = float(request.get('image_ratio') or (0.50 if position in {'left', 'right'} else 0.54))
    ratio = max(0.30, min(0.70, ratio))
    gap = max(0.18, float(request.get('column_gap') or _density_settings(density)['gap']))
    width_scale, height_scale = _policy_scale(fill_mode, 'photo_text')
    work_w = canvas.w * width_scale
    work_h = canvas.h * height_scale
    work = Box(canvas.x + (canvas.w - work_w) / 2, canvas.y + (canvas.h - work_h) / 2, work_w, work_h)
    if position in {'left', 'right'}:
        image_w = max(0.1, (work.w - gap) * ratio)
        text_w = max(0.1, work.w - gap - image_w)
        if position == 'left':
            image_box = Box(work.x, work.y, image_w, work.h)
            text_box = Box(image_box.right + gap, work.y, text_w, work.h)
        else:
            text_box = Box(work.x, work.y, text_w, work.h)
            image_box = Box(text_box.right + gap, work.y, image_w, work.h)
    else:
        image_h = max(0.1, (work.h - gap) * ratio)
        text_h = max(0.1, work.h - gap - image_h)
        if position == 'top':
            image_box = Box(work.x, work.y, work.w, image_h)
            text_box = Box(work.x, image_box.bottom + gap, work.w, text_h)
        else:
            text_box = Box(work.x, work.y, work.w, text_h)
            image_box = Box(work.x, text_box.bottom + gap, work.w, image_h)
    cluster = _text_cluster(text_box, request, density)
    return {
        **cluster,
        'image_box': image_box,
        'text_box': text_box,
        'image_position': position,
        'resolved_text_side': request.get('resolved_text_side') or {'left':'right','right':'left','top':'bottom','bottom':'top'}[position],
        'image_recipe_id': request.get('image_recipe_id'),
    }


def _layout_two_column(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    items = list(request.get('items') or [])
    if len(items) != 2:
        raise ValueError('two_column layout requires exactly two items')
    title_box, subtitle_box, body = _header_boxes(canvas, title, subtitle, density)
    gap = max(0.22, float(request.get('column_gap') or _density_settings(density)['gap']))
    width_scale, height_scale = _policy_scale(fill_mode, 'two_column')
    card_mode = all(str(item.get('style') or 'open').lower() == 'card' for item in items)
    if card_mode:
        # A panel is a semantic component, not a licence to paint the entire
        # content canvas. Short card pairs are height-fitted and centred.
        max_chars = max(
            len(str(item.get('title') or '')) + len(str(item.get('body') or ''))
            for item in items
        )
        semantic_height = 0.58 if max_chars <= 90 else 0.72 if max_chars <= 170 else 0.88
        height_scale = min(height_scale, semantic_height)
    work_w = body.w * width_scale
    work_h = body.h * height_scale
    work = Box(body.x + (body.w - work_w) / 2, body.y + (body.h - work_h) / 2, work_w, work_h)
    left_ratio = max(0.34, min(0.66, float(request.get('left_ratio') or 0.5)))
    left_w = (work.w - gap) * left_ratio
    right_w = work.w - gap - left_w
    boxes = [Box(work.x, work.y, left_w, work.h), Box(work.x + left_w + gap, work.y, right_w, work.h)]
    divider_x = work.x + left_w + gap / 2
    return {
        'title_box': title_box,
        'subtitle_box': subtitle_box,
        'body': body,
        'item_boxes': boxes,
        'divider_x': divider_x,
        'card_mode': card_mode,
    }

def _layout_full_bleed(slide_box: Box, canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    image_box = slide_box if bool(request.get('bleed_to_slide', True)) else canvas
    overlay_position = str(request.get('overlay_position') or 'left').lower()
    if overlay_position not in {'left', 'right', 'center', 'bottom_left', 'bottom_right'}:
        overlay_position = 'left'
    width_ratio = max(0.28, min(0.68, float(request.get('overlay_width_ratio') or 0.43)))
    height_ratio = max(0.24, min(0.78, float(request.get('overlay_height_ratio') or 0.56)))
    # Full-bleed text should not inherit an accidentally narrow content canvas
    # from the selected source page. Use a safe inset of the actual slide while
    # preserving source chrome above the background visual.
    if bool(request.get('bleed_to_slide', True)):
        margin=max(0.55,min(1.20,slide_box.w*0.045))
        panel_canvas=Box(slide_box.x+margin,slide_box.y+margin,slide_box.w-2*margin,slide_box.h-2*margin)
    else:
        panel_canvas=canvas
    panel_w = panel_canvas.w * width_ratio
    panel_h = panel_canvas.h * height_ratio
    if overlay_position == 'left':
        x = panel_canvas.x
        y = panel_canvas.y + (panel_canvas.h - panel_h) / 2
    elif overlay_position == 'right':
        x = panel_canvas.right - panel_w
        y = panel_canvas.y + (panel_canvas.h - panel_h) / 2
    elif overlay_position == 'center':
        x = panel_canvas.x + (panel_canvas.w - panel_w) / 2
        y = panel_canvas.y + (panel_canvas.h - panel_h) / 2
    elif overlay_position == 'bottom_right':
        x = panel_canvas.right - panel_w
        y = panel_canvas.bottom - panel_h
    else:
        x = panel_canvas.x
        y = panel_canvas.bottom - panel_h
    overlay_box = Box(x, y, panel_w, panel_h)
    panel_pad = max(0.24, min(0.52, float(request.get('overlay_padding') or min(panel_w, panel_h) * 0.065)))
    text_box = Box(overlay_box.x + panel_pad, overlay_box.y + panel_pad, overlay_box.w - 2 * panel_pad, overlay_box.h - 2 * panel_pad)
    cluster = _text_cluster(text_box, request, density)
    return {
        **cluster,
        'image_box': image_box,
        'overlay_box': overlay_box,
        'text_box': text_box,
        'overlay_position': overlay_position,
        'resolved_text_side': request.get('resolved_text_side') or overlay_position,
        'image_recipe_id': request.get('image_recipe_id'),
    }



def _layout_comparison_matrix(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    title_box, subtitle_box, body = _header_boxes(canvas, title, subtitle, density)
    width_scale, height_scale = _policy_scale(fill_mode, 'comparison_matrix')
    work_w = body.w * width_scale
    work_h = body.h * height_scale
    work = Box(body.x + (body.w - work_w) / 2, body.y + (body.h - work_h) / 2, work_w, work_h)
    return {
        'title_box': title_box,
        'subtitle_box': subtitle_box,
        'body': body,
        'matrix_box': work,
        'item_boxes': [],
    }


def _layout_relationship(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    title_box, subtitle_box, body = _header_boxes(canvas, title, subtitle, density)
    nodes = list(request.get('nodes') or [])
    if not nodes:
        nodes = [
            {'id': f'N{index:02d}', 'title': item.get('title') or item.get('number') or f'Node {index}', 'body': item.get('body') or ''}
            for index, item in enumerate(request.get('items') or [], start=1)
        ]
    if not nodes:
        raise ValueError('relationship layout requires nodes or items')
    width_scale, height_scale = _policy_scale(fill_mode, 'relationship')
    work_w = body.w * width_scale
    work_h = body.h * height_scale
    work = Box(body.x + (body.w - work_w) / 2, body.y + (body.h - work_h) / 2, work_w, work_h)
    n = len(nodes)
    node_w = min(work.w * 0.24, max(1.55, work.w / max(3.2, math.sqrt(n) * 2.25)))
    node_h = min(work.h * 0.22, max(0.92, work.h * (0.19 if n <= 5 else 0.15)))
    edges = list(request.get('edges') or [])
    degree = {str(node.get('id')): 0 for node in nodes}
    for edge in edges:
        a = str(edge.get('from') or '')
        b = str(edge.get('to') or '')
        if a in degree: degree[a] += 1
        if b in degree: degree[b] += 1
    preferred_hub = str(request.get('center_node_id') or request.get('hub_id') or '')
    hub_id = preferred_hub if preferred_hub in degree else (max(degree, key=degree.get) if degree else str(nodes[0].get('id')))
    hub_degree = degree.get(hub_id, 0)
    use_hub = n >= 3 and (preferred_hub in degree or hub_degree >= max(2, math.ceil((n - 1) * 0.55)))
    node_boxes: dict[str, Box] = {}
    cx = work.x + work.w / 2
    cy = work.y + work.h / 2
    if n == 1:
        node = nodes[0]
        node_boxes[str(node.get('id'))] = Box(cx - node_w / 2, cy - node_h / 2, node_w, node_h)
    elif n == 2:
        gap = max(0.35, work.w * 0.10)
        total = node_w * 2 + gap
        x0 = cx - total / 2
        for index, node in enumerate(nodes):
            node_boxes[str(node.get('id'))] = Box(x0 + index * (node_w + gap), cy - node_h / 2, node_w, node_h)
    elif use_hub:
        hub = next(node for node in nodes if str(node.get('id')) == hub_id)
        node_boxes[hub_id] = Box(cx - node_w / 2, cy - node_h / 2, node_w, node_h)
        outer = [node for node in nodes if str(node.get('id')) != hub_id]
        rx = max(node_w * 0.75, (work.w - node_w) * 0.39)
        ry = max(node_h * 0.85, (work.h - node_h) * 0.39)
        start = -math.pi / 2
        for index, node in enumerate(outer):
            angle = start + (2 * math.pi * index / len(outer))
            nx = cx + math.cos(angle) * rx - node_w / 2
            ny = cy + math.sin(angle) * ry - node_h / 2
            nx = max(work.x, min(work.right - node_w, nx))
            ny = max(work.y, min(work.bottom - node_h, ny))
            node_boxes[str(node.get('id'))] = Box(nx, ny, node_w, node_h)
    else:
        cols = min(3, max(2, math.ceil(math.sqrt(n))))
        rows = math.ceil(n / cols)
        gap_x = max(0.24, work.w * 0.035)
        gap_y = max(0.24, work.h * 0.06)
        cell_w = (work.w - gap_x * (cols - 1)) / cols
        cell_h = (work.h - gap_y * (rows - 1)) / rows
        node_w2 = min(node_w, cell_w * 0.82)
        node_h2 = min(node_h, cell_h * 0.72)
        for index, node in enumerate(nodes):
            row = index // cols
            col = index % cols
            count = min(cols, n - row * cols)
            row_width = count * cell_w + (count - 1) * gap_x
            row_x = work.x + (work.w - row_width) / 2
            bx = row_x + col * (cell_w + gap_x) + (cell_w - node_w2) / 2
            by = work.y + row * (cell_h + gap_y) + (cell_h - node_h2) / 2
            node_boxes[str(node.get('id'))] = Box(bx, by, node_w2, node_h2)
    return {
        'title_box': title_box,
        'subtitle_box': subtitle_box,
        'body': body,
        'relationship_box': work,
        'node_boxes': node_boxes,
        'nodes': nodes,
        'edges': edges,
        'hub_id': hub_id if use_hub else None,
        'item_boxes': list(node_boxes.values()),
    }



def _layout_cover(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    body_text = _body_text(request)
    width_ratio = max(0.54, min(0.90, float(request.get('title_width_ratio') or 0.76)))
    work_w = canvas.w * width_ratio
    align = str(request.get('alignment') or 'left').lower()
    x = canvas.x if align == 'left' else canvas.x + (canvas.w - work_w) / 2 if align == 'center' else canvas.right - work_w
    cluster_h = canvas.h * (0.58 if subtitle or body_text else 0.42)
    y = canvas.y + (canvas.h - cluster_h) * (0.46 if align == 'center' else 0.52)
    title_h = cluster_h * (0.54 if subtitle or body_text else 0.86)
    title_box = Box(x, y, work_w, title_h) if title else None
    cursor = title_box.bottom + 0.18 if title_box else y
    subtitle_box = None
    if subtitle:
        subtitle_box = Box(x, cursor, work_w * 0.88, min(0.72, cluster_h * 0.18))
        cursor = subtitle_box.bottom + 0.12
    body_box = Box(x, cursor, work_w * 0.78, max(0.28, y + cluster_h - cursor)) if body_text else None
    return {
        'title_box': title_box, 'subtitle_box': subtitle_box, 'body_box': body_box,
        'body_text': body_text, 'body': Box(x, y, work_w, cluster_h), 'item_boxes': [],
        'text_alignment': align,
    }


def _layout_section(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    kicker = str(request.get('kicker') or request.get('section_number') or '').strip()
    width = canvas.w * max(0.52, min(0.82, float(request.get('width_ratio') or 0.68)))
    block_h = canvas.h * (0.40 if subtitle else 0.30)
    y = canvas.y + (canvas.h - block_h) / 2
    x = canvas.x
    kicker_box = Box(x, y, width, min(0.42, block_h * 0.18)) if kicker else None
    cursor = kicker_box.bottom + 0.10 if kicker_box else y
    title_box = Box(x, cursor, width, block_h * (0.50 if subtitle else 0.74)) if title else None
    cursor = title_box.bottom + 0.12 if title_box else cursor
    subtitle_box = Box(x, cursor, width * 0.88, max(0.34, y + block_h - cursor)) if subtitle else None
    return {
        'kicker_box': kicker_box, 'kicker_text': kicker,
        'title_box': title_box, 'subtitle_box': subtitle_box,
        'body': Box(x, y, width, block_h), 'item_boxes': [],
    }


def _layout_closing(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    body_text = _body_text(request)
    items = list(request.get('items') or [])[:4]
    title_box, subtitle_box, body = _header_boxes(canvas, title, subtitle, density)
    gap = _density_settings(density)['gap']
    body_box = None
    y = body.y
    if body_text:
        body_h = min(max(0.48, body.h * 0.15), 0.90)
        body_box = Box(body.x, y, body.w * 0.82, body_h)
        y = body_box.bottom + gap
    item_boxes: list[Box] = []
    if items:
        work = Box(body.x, y, body.w, max(0.5, body.bottom - y))
        cols = len(items) if len(items) <= 3 else 2
        rows = math.ceil(len(items) / cols)
        card_gap = max(0.18, gap)
        card_w = (work.w - card_gap * (cols - 1)) / cols
        semantic_chars = max([len(str(item.get('title') or '')) + len(str(item.get('body') or '')) for item in items] or [0])
        target_h = min(work.h, max(1.05, 1.25 + semantic_chars / 90.0))
        card_h = min((target_h - card_gap * (rows - 1)) / rows, (work.h - card_gap * (rows - 1)) / rows)
        total_h = card_h * rows + card_gap * (rows - 1)
        y0 = work.y + (work.h - total_h) / 2
        for index in range(len(items)):
            row, col = divmod(index, cols)
            row_count = min(cols, len(items) - row * cols)
            row_w = row_count * card_w + (row_count - 1) * card_gap
            row_x = work.x + (work.w - row_w) / 2
            item_boxes.append(Box(row_x + col * (card_w + card_gap), y0 + row * (card_h + card_gap), card_w, card_h))
    return {
        'title_box': title_box, 'subtitle_box': subtitle_box,
        'body_box': body_box, 'body_text': body_text, 'body': body,
        'item_boxes': item_boxes,
    }


def _layout_timeline(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    items = list(request.get('items') or [])
    if not items:
        raise ValueError('timeline layout requires at least one item')
    title_box, subtitle_box, body = _header_boxes(canvas, title, subtitle, density)
    width_scale, height_scale = _policy_scale(fill_mode, 'timeline')
    work = Box(
        body.x + (body.w - body.w * width_scale) / 2,
        body.y + (body.h - body.h * height_scale) / 2,
        body.w * width_scale,
        body.h * height_scale,
    )
    n = len(items)
    orientation = str(request.get('orientation') or ('horizontal' if work.w / max(work.h, 0.01) >= 1.35 and n <= 6 else 'vertical')).lower()
    boxes: list[Box] = []
    markers: list[dict[str, float]] = []
    if orientation == 'horizontal':
        line_y = work.y + work.h * 0.52
        spacing = work.w / max(1, n)
        card_w = min(max(1.35, spacing * 0.82), max(1.35, work.w / min(n, 4) * 0.84))
        card_h = min(max(0.92, work.h * 0.34), 1.85)
        for index in range(n):
            cx = work.x + spacing * (index + 0.5)
            above = index % 2 == 0
            y = line_y - card_h - 0.34 if above else line_y + 0.34
            boxes.append(Box(max(work.x, min(work.right - card_w, cx - card_w / 2)), y, card_w, card_h))
            markers.append({'x': round(cx, 4), 'y': round(line_y, 4)})
        line_box = Box(work.x, line_y, work.w, 0.0)
    else:
        line_x = work.x + work.w * 0.23
        spacing = work.h / max(1, n)
        card_h = min(max(0.72, spacing * 0.76), 1.55)
        card_w = work.w * 0.66
        for index in range(n):
            cy = work.y + spacing * (index + 0.5)
            boxes.append(Box(line_x + 0.42, max(work.y, min(work.bottom - card_h, cy - card_h / 2)), card_w, card_h))
            markers.append({'x': round(line_x, 4), 'y': round(cy, 4)})
        line_box = Box(line_x, work.y, 0.0, work.h)
    return {
        'title_box': title_box, 'subtitle_box': subtitle_box, 'body': body,
        'timeline_box': work, 'timeline_line_box': line_box, 'timeline_markers': markers,
        'item_boxes': boxes, 'orientation': orientation,
    }


def _layout_kpi(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    items = list(request.get('items') or [])
    if not items:
        raise ValueError('kpi layout requires at least one item')
    title_box, subtitle_box, body = _header_boxes(canvas, title, subtitle, density)
    width_scale, height_scale = _policy_scale(fill_mode, 'kpi')
    work = Box(body.x + (body.w - body.w * width_scale) / 2, body.y + (body.h - body.h * height_scale) / 2, body.w * width_scale, body.h * height_scale)
    n = len(items)
    cols = min(3, n) if n <= 6 else min(4, n)
    rows = math.ceil(n / cols)
    gap = max(0.18, _density_settings(density)['gap'])
    cw = (work.w - gap * (cols - 1)) / cols
    ch = (work.h - gap * (rows - 1)) / rows
    boxes: list[Box] = []
    for index in range(n):
        row, col = divmod(index, cols)
        row_count = min(cols, n - row * cols)
        row_w = row_count * cw + (row_count - 1) * gap
        row_x = work.x + (work.w - row_w) / 2
        boxes.append(Box(row_x + col * (cw + gap), work.y + row * (ch + gap), cw, ch))
    return {'title_box': title_box, 'subtitle_box': subtitle_box, 'body': body, 'kpi_box': work, 'item_boxes': boxes}


def _layout_chart(canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    title_box, subtitle_box, body = _header_boxes(canvas, title, subtitle, density)
    width_scale, height_scale = _policy_scale(fill_mode, 'chart')
    work = Box(body.x + (body.w - body.w * width_scale) / 2, body.y + (body.h - body.h * height_scale) / 2, body.w * width_scale, body.h * height_scale)
    note = str(request.get('note') or '').strip()
    note_box = None
    if note:
        note_h = min(0.42, max(0.25, work.h * 0.07))
        note_box = Box(work.x, work.bottom - note_h, work.w, note_h)
        chart_box = Box(work.x, work.y, work.w, max(0.5, work.h - note_h - 0.10))
    else:
        chart_box = work
    return {
        'title_box': title_box, 'subtitle_box': subtitle_box, 'body': body,
        'chart_box': chart_box, 'note_box': note_box, 'note_text': note, 'item_boxes': [],
    }

def _geometry_for_family(slide_box: Box, canvas: Box, request: dict[str, Any], density: str, fill_mode: str) -> dict[str, Any]:
    family = str(request.get('family') or '')
    if family == 'grid':
        return _layout_grid(canvas, request, density, fill_mode)
    if family == 'process':
        return _layout_process(canvas, request, density, fill_mode)
    if family == 'statement':
        return _layout_statement(canvas, request, density, fill_mode)
    if family == 'two_column':
        return _layout_two_column(canvas, request, density, fill_mode)
    if family == 'photo_text':
        return _layout_photo_text(canvas, request, density, fill_mode)
    if family == 'full_bleed':
        return _layout_full_bleed(slide_box, canvas, request, density, fill_mode)
    if family == 'comparison_matrix':
        return _layout_comparison_matrix(canvas, request, density, fill_mode)
    if family == 'relationship':
        return _layout_relationship(canvas, request, density, fill_mode)
    if family == 'timeline':
        return _layout_timeline(canvas, request, density, fill_mode)
    if family == 'kpi':
        return _layout_kpi(canvas, request, density, fill_mode)
    if family == 'chart':
        return _layout_chart(canvas, request, density, fill_mode)
    if family == 'cover':
        return _layout_cover(canvas, request, density, fill_mode)
    if family == 'section':
        return _layout_section(canvas, request, density, fill_mode)
    if family == 'closing':
        return _layout_closing(canvas, request, density, fill_mode)
    raise ValueError(f'layout_engine family not supported: {family or "<missing>"}')


def _rgb_from_fill(shape) -> str | None:
    try:
        rgb = shape.fill.fore_color.rgb
        return str(rgb) if rgb else None
    except Exception:
        return None


def _rgb_from_line(shape) -> str | None:
    try:
        rgb = shape.line.color.rgb
        return str(rgb) if rgb else None
    except Exception:
        return None


def _set_shape_opacity(shape, opacity: float) -> None:
    """Set solid-fill opacity through DrawingML while keeping the shape editable."""
    opacity = max(0.0, min(1.0, float(opacity)))
    try:
        solid = shape.fill._xPr.find(qn('a:solidFill'))
        if solid is None or len(solid) == 0:
            return
        color = solid[0]
        for child in list(color):
            if child.tag == qn('a:alpha'):
                color.remove(child)
        alpha = OxmlElement('a:alpha')
        alpha.set('val', str(int(round(opacity * 100000))))
        color.append(alpha)
    except Exception:
        pass


def _add_panel(
    slide,
    box: Box,
    theme: dict[str, str],
    *,
    source_shape=None,
    fill_color: str | None = None,
    line_color: str | None = None,
    opacity: float = 1.0,
    rounded: bool = True,
):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    if source_shape is not None and getattr(source_shape, 'shape_type', None) == MSO_SHAPE_TYPE.AUTO_SHAPE:
        try:
            if source_shape.auto_shape_type is not None:
                shape_type = source_shape.auto_shape_type
        except Exception:
            pass
    panel = slide.shapes.add_shape(shape_type, _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
    panel.fill.solid()
    panel.fill.fore_color.rgb = _hex_color(fill_color or _rgb_from_fill(source_shape), theme['light'])
    _set_shape_opacity(panel, opacity)
    if line_color == 'none':
        panel.line.fill.background()
    else:
        panel.line.color.rgb = _hex_color(line_color or _rgb_from_line(source_shape), theme['line'])
        try:
            panel.line.width = source_shape.line.width if source_shape is not None and source_shape.line.width else Pt(1.0)
        except Exception:
            panel.line.width = Pt(1.0)
    return panel


def _source_frame_shape(root: Path, slide, source_slide_id: str, request: dict[str, Any]):
    styles = request.get('style_source_object_ids') or {}
    by_id = {shape.shape_id: shape for shape in slide.shapes}
    explicit = _sid(styles.get('panel') or styles.get('image_frame'))
    if explicit is not None and explicit in by_id:
        return by_id[explicit]
    assets = read_json(root / 'analysis/source_assets.json', {})
    candidates = [
        row for row in assets.get('assets', [])
        if row.get('source_slide_id') == source_slide_id and row.get('classification') == 'container_or_frame'
    ]
    candidates.sort(key=lambda row: float(row.get('area_ratio') or 0), reverse=True)
    for row in candidates:
        sid = _sid(row.get('source_object_id'))
        if sid is not None and sid in by_id:
            return by_id[sid]
    return None


def _resolve_image_context(
    root: Path, slide_plan: dict[str, Any], request: dict[str, Any],
    *, require_asset: bool = False,
) -> dict[str, Any] | None:
    family = str(request.get('family') or '')
    if family not in {'photo_text', 'full_bleed'}:
        return None
    recipes, manifest = _image_documents(root)
    default_id = f'IMG-{slide_plan.get("slide_id")}-01'
    recipe_id = str(request.get('image_recipe_id') or '').strip()
    recipe = None
    if recipe_id:
        recipe = next((row for row in recipes.get('recipes', []) if row.get('recipe_id') == recipe_id), None)
    else:
        recipe = next((row for row in recipes.get('recipes', []) if row.get('slide_id') == slide_plan.get('slide_id')), None)
        recipe_id = str((recipe or {}).get('recipe_id') or default_id)
    selected_id = (recipe or {}).get('selected_asset_id') or (manifest.get('selected_by_recipe') or {}).get(recipe_id)
    asset = next((row for row in manifest.get('assets', []) if row.get('asset_id') == selected_id), None)
    if require_asset and (recipe is None or not selected_id or asset is None):
        raise ValueError(f'image asset is not ready for layout slot: {recipe_id}')
    image_path = None
    if asset is not None:
        processed = asset.get('processed_path')
        if require_asset and not processed:
            raise ValueError(f'processed image path missing for layout slot: {recipe_id}')
        if processed:
            image_path = _project_path(root, processed)
    target = (recipe or {}).get('target') or {}
    style_ids = request.get('style_source_object_ids') or {}
    source_object_id = str(
        request.get('image_source_object_id')
        or target.get('source_object_id')
        or style_ids.get('image')
        or ''
    ).strip() or None
    negative_space = str(((recipe or {}).get('composition') or {}).get('negative_space') or 'none').lower()
    focal = _image_focal_point(asset or {})
    source_bbox = None
    if source_object_id:
        source_obj = _source_objects(root, slide_plan.get('source_slide_id')).get(_sid(source_object_id))
        bb = (source_obj or {}).get('bbox') or {}
        try:
            source_bbox = Box(float(bb['x']), float(bb['y']), float(bb['w']), float(bb['h']))
        except Exception:
            source_bbox = None
    return {
        'recipe_id': recipe_id,
        'recipe': recipe,
        'asset_id': selected_id,
        'asset': asset,
        'image_path': image_path,
        'source_object_id': source_object_id,
        'negative_space': negative_space,
        'focal_point': focal,
        'source_bbox': source_bbox,
        'ready': bool(recipe is not None and selected_id and asset is not None and image_path is not None),
    }


def _derive_photo_request(request: dict[str, Any], image_context: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(request)
    negative = str((image_context or {}).get('negative_space') or 'none')
    family = str(out.get('family') or '')
    text_side = str(out.get('text_side') or 'auto').lower()
    if family == 'photo_text':
        explicit_position = str(out.get('image_position') or '').lower()
        if explicit_position not in {'left', 'right', 'top', 'bottom'}:
            if text_side in {'left', 'right', 'top', 'bottom'}:
                explicit_position = {'left':'right','right':'left','top':'bottom','bottom':'top'}[text_side]
            elif negative in {'left', 'right', 'top', 'bottom'}:
                explicit_position = {'left':'right','right':'left','top':'bottom','bottom':'top'}[negative]
            else:
                explicit_position = 'right'
        out['image_position'] = explicit_position
        out['resolved_text_side'] = {'left':'right','right':'left','top':'bottom','bottom':'top'}[explicit_position]
        out['image_position_origin'] = (
            'explicit' if str(request.get('image_position') or '').lower() in {'left','right','top','bottom'}
            else 'text_side' if text_side in {'left','right','top','bottom'}
            else 'image_recipe_negative_space' if negative in {'left','right','top','bottom'}
            else 'default'
        )
    elif family == 'full_bleed':
        overlay = str(out.get('overlay_position') or '').lower()
        if overlay not in {'left', 'right', 'center', 'bottom_left', 'bottom_right'}:
            if text_side in {'left', 'right'}:
                overlay = text_side
            elif text_side == 'bottom':
                overlay = 'bottom_left'
            elif negative in {'left', 'right'}:
                overlay = negative
            elif negative == 'bottom':
                overlay = 'bottom_left'
            else:
                overlay = 'left'
        out['overlay_position'] = overlay
        out['resolved_text_side'] = overlay
        out['overlay_position_origin'] = (
            'explicit' if str(request.get('overlay_position') or '').lower() in {'left','right','center','bottom_left','bottom_right'}
            else 'text_side' if text_side in {'left','right','bottom'}
            else 'image_recipe_negative_space' if negative in {'left','right','bottom'}
            else 'default'
        )
    return out


def _add_body_text(slide, box: Box | None, text: str, source_shape, theme: dict[str, str], *, color_override: str | None = None, size: float | None = None):
    if box is None or not str(text).strip():
        return None
    return _add_text(
        slide, box, str(text).strip(), source_shape, 'item_body', theme,
        size_override=float(size or max(12, min(19, box.h * 6.4))), color_override=color_override,
    )


def _matrix_payload(request: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], int | None]:
    matrix = request.get('matrix') or {}
    row_labels = [str(x) for x in matrix.get('row_labels') or []]
    columns = [dict(x) for x in matrix.get('columns') or []]
    highlight = matrix.get('highlight_column')
    if not columns:
        items = list(request.get('items') or [])
        columns = []
        for item in items:
            body_lines = [line.strip('• ・\t') for line in str(item.get('body') or '').splitlines() if line.strip()]
            columns.append({'title': str(item.get('title') or item.get('number') or ''), 'values': body_lines or ['']})
        max_rows = max((len(col.get('values') or []) for col in columns), default=0)
        if not row_labels:
            row_labels = [f'項目 {index}' for index in range(1, max_rows + 1)]
    if len(columns) < 2:
        raise ValueError('comparison_matrix requires at least two columns')
    max_rows = max(len(row_labels), max((len(col.get('values') or []) for col in columns), default=0))
    if max_rows == 0:
        raise ValueError('comparison_matrix requires row_labels or column values')
    if len(row_labels) < max_rows:
        row_labels = row_labels + [f'項目 {index}' for index in range(len(row_labels) + 1, max_rows + 1)]
    for col in columns:
        values = [str(x) for x in col.get('values') or []]
        col['values'] = values + [''] * (max_rows - len(values))
    if highlight is not None:
        try:
            highlight = int(highlight)
        except Exception:
            highlight = None
    return row_labels, columns, highlight


def _set_cell_text(cell, text: str, source_shape, theme: dict[str, str], *, bold: bool = False, color: str | None = None, size: float = 15.0, align=PP_ALIGN.LEFT):
    tf = cell.text_frame
    tf.clear(); tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.10)
    tf.margin_top = tf.margin_bottom = Inches(0.06)
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = str(text)
    snap = _style_from_shape(source_shape)
    f = r.font
    if snap.get('font_name'): f.name = snap['font_name']
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = _hex_color(color or snap.get('color'), theme['dark'])


def _add_comparison_matrix(slide, box: Box, request: dict[str, Any], styles: dict[str, Any], theme: dict[str, str]):
    labels, columns, highlight = _matrix_payload(request)
    source_header_pt = float(_style_from_shape(styles['item_title']).get('font_size_pt') or 20.0)
    source_body_pt = float(_style_from_shape(styles['item_body']).get('font_size_pt') or 16.0)
    header_font_pt = max(18.0, min(26.0, source_header_pt * 0.55))
    body_font_pt = max(15.0, min(20.0, source_body_pt * 0.80))
    rows = len(labels) + 1
    cols = len(columns) + 1
    shape = slide.shapes.add_table(rows, cols, _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
    table = shape.table
    first_weight = max(0.72, min(1.35, float((request.get('matrix') or {}).get('label_column_weight') or 0.92)))
    total_weight = first_weight + len(columns)
    assigned = 0
    for index in range(cols):
        weight = first_weight if index == 0 else 1.0
        width = _emu(box.w) - assigned if index == cols - 1 else int(_emu(box.w) * weight / total_weight)
        table.columns[index].width = width
        assigned += width
    header_h = min(_emu(box.h) * 0.19, _emu(0.92))
    body_h = (_emu(box.h) - int(header_h)) / max(1, rows - 1)
    table.rows[0].height = int(header_h)
    for row in range(1, rows):
        table.rows[row].height = int(body_h)
    for row in range(rows):
        for col in range(cols):
            cell = table.cell(row, col)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _hex_color('F7F7F5' if row else theme['dark'], 'F7F7F5')
            cell.margin_left = cell.margin_right = Inches(0.10)
            cell.margin_top = cell.margin_bottom = Inches(0.05)
    _set_cell_text(table.cell(0, 0), '', styles['item_title'], theme, bold=True, color='FFFFFF', align=PP_ALIGN.CENTER)
    for col_index, column in enumerate(columns, start=1):
        header_color = theme['accent'] if highlight == col_index - 1 else theme['dark']
        table.cell(0, col_index).fill.fore_color.rgb = _hex_color(header_color, theme['dark'])
        _set_cell_text(table.cell(0, col_index), column.get('title') or '', styles['item_title'], theme, bold=True, color='FFFFFF', size=header_font_pt, align=PP_ALIGN.CENTER)
    for row_index, label in enumerate(labels, start=1):
        table.cell(row_index, 0).fill.fore_color.rgb = _hex_color('EFEFEB', 'EFEFEB')
        _set_cell_text(table.cell(row_index, 0), label, styles['item_body'], theme, bold=True, size=body_font_pt)
        for col_index, column in enumerate(columns, start=1):
            if highlight == col_index - 1:
                table.cell(row_index, col_index).fill.fore_color.rgb = _hex_color('FFF4E8', 'FFF4E8')
            value = (column.get('values') or [''])[row_index - 1]
            _set_cell_text(table.cell(row_index, col_index), value, styles['item_body'], theme, size=body_font_pt, align=PP_ALIGN.CENTER)
    return shape, len(labels)


def _add_relationship(slide, geom: dict[str, Any], request: dict[str, Any], styles: dict[str, Any], theme: dict[str, str], source_panel=None):
    node_boxes: dict[str, Box] = geom.get('node_boxes') or {}
    nodes = {str(node.get('id')): node for node in geom.get('nodes') or []}
    edges = geom.get('edges') or []
    generated = []
    # Connectors first so editable nodes remain above them.
    for edge in edges:
        a = node_boxes.get(str(edge.get('from') or ''))
        b = node_boxes.get(str(edge.get('to') or ''))
        if a is None or b is None:
            continue
        x1, y1 = a.x + a.w / 2, a.y + a.h / 2
        x2, y2 = b.x + b.w / 2, b.y + b.h / 2
        line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, _emu(x1), _emu(y1), _emu(x2), _emu(y2))
        line.line.color.rgb = _hex_color(theme['accent'], 'FF9A42')
        line.line.width = Pt(1.6)
        generated.append({
            'role':'relationship_edge',
            'from':str(edge.get('from') or ''),
            'to':str(edge.get('to') or ''),
            'output_shape_id':line.shape_id,
            'bbox':{'x':round(min(x1,x2),4),'y':round(min(y1,y2),4),'w':round(abs(x2-x1),4),'h':round(abs(y2-y1),4)},
        })
        label = str(edge.get('label') or '').strip()
        if label:
            lb = Box((x1 + x2) / 2 - 0.65, (y1 + y2) / 2 - 0.17, 1.3, 0.34)
            sh = _add_text(slide, lb, label, styles['item_body'], 'item_body', theme, size_override=11, align=PP_ALIGN.CENTER)
            generated.append({'role':'edge_label','output_shape_id':sh.shape_id,'bbox':lb.as_dict(),'render_text':label})
    for node_id, box in node_boxes.items():
        node = nodes.get(node_id, {})
        is_hub = node_id == geom.get('hub_id')
        panel = _add_panel(
            slide, box, theme, source_shape=source_panel,
            fill_color=theme['accent'] if is_hub else None,
            line_color='none' if is_hub else None,
            opacity=1.0,
        )
        title = str(node.get('title') or node_id)
        body = str(node.get('body') or '')
        source_title_pt = float(_style_from_shape(styles['item_title']).get('font_size_pt') or 20.0)
        source_body_pt = float(_style_from_shape(styles['item_body']).get('font_size_pt') or 15.0)
        node_title_pt = max(20.0, min(32.0, source_title_pt * 0.68))
        node_body_pt = max(14.0, min(20.0, source_body_pt * 0.82))
        pad = max(0.14, min(0.28, min(box.w, box.h) * 0.10))
        title_h = min(max(0.34, box.h * 0.33), box.h * 0.48)
        title_box = Box(box.x + pad, box.y + pad, box.w - 2 * pad, title_h)
        title_shape = _add_text(
            slide, title_box, title, styles['item_title'], 'item_title', theme,
            size_override=node_title_pt, bold_override=True,
            color_override='FFFFFF' if is_hub else None, align=PP_ALIGN.CENTER,
        )
        generated.append({'role':'relationship_node_title','node_id':node_id,'output_shape_id':title_shape.shape_id,'bbox':title_box.as_dict(),'render_text':title})
        if body:
            body_box = Box(box.x + pad, title_box.bottom + 0.05, box.w - 2 * pad, max(0.2, box.bottom - title_box.bottom - pad - 0.05))
            body_shape = _add_text(
                slide, body_box, body, styles['item_body'], 'item_body', theme,
                size_override=node_body_pt, color_override='FFFFFF' if is_hub else None,
                align=PP_ALIGN.CENTER,
            )
            generated.append({'role':'relationship_node_body','node_id':node_id,'output_shape_id':body_shape.shape_id,'bbox':body_box.as_dict(),'render_text':body})
        generated.append({'role':'relationship_node','node_id':node_id,'output_shape_id':panel.shape_id,'bbox':box.as_dict()})
    return generated



def _add_timeline(slide, geom: dict[str, Any], request: dict[str, Any], styles: dict[str, Any], theme: dict[str, str]) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    items = list(request.get('items') or [])
    line_box = geom.get('timeline_line_box')
    orientation = str(geom.get('orientation') or 'horizontal')
    if not isinstance(line_box, Box):
        raise ValueError('timeline geometry missing line')
    if orientation == 'horizontal':
        line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, _emu(line_box.x), _emu(line_box.y), _emu(line_box.right), _emu(line_box.y))
    else:
        line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, _emu(line_box.x), _emu(line_box.y), _emu(line_box.x), _emu(line_box.bottom))
    line.line.color.rgb = _hex_color(theme['accent'], 'FF9A42'); line.line.width = Pt(2.2)
    generated.append({'role':'timeline_axis','output_shape_id':line.shape_id,'bbox':line_box.as_dict()})

    markers = list(geom.get('timeline_markers') or [])
    for index, (item, box, marker) in enumerate(zip(items, geom.get('item_boxes') or [], markers), start=1):
        mx, my = float(marker['x']), float(marker['y'])
        size = 0.22
        marker_shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, _emu(mx - size / 2), _emu(my - size / 2), _emu(size), _emu(size))
        marker_shape.fill.solid(); marker_shape.fill.fore_color.rgb = _hex_color(theme['accent'], 'FF9A42'); marker_shape.line.fill.background()
        generated.append({'role':'timeline_marker','item_index':index-1,'output_shape_id':marker_shape.shape_id,'bbox':Box(mx-size/2,my-size/2,size,size).as_dict()})
        if orientation == 'horizontal':
            target_y = box.bottom if box.bottom < my else box.y
            connector = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, _emu(mx), _emu(my), _emu(mx), _emu(target_y))
        else:
            connector = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, _emu(mx), _emu(my), _emu(box.x), _emu(my))
        connector.line.color.rgb = _hex_color(theme['line'], 'D8D8D8'); connector.line.width = Pt(1.0)
        generated.append({'role':'timeline_connector','item_index':index-1,'output_shape_id':connector.shape_id,'bbox':Box(min(mx,box.x),min(my,box.y),abs(box.x-mx),abs(box.y-my)).as_dict()})

        panel = _add_panel(slide, box, theme, fill_color='FFFFFF', line_color=theme['line'], opacity=1.0)
        generated.append({'role':'timeline_item','item_index':index-1,'output_shape_id':panel.shape_id,'bbox':box.as_dict()})
        pad = max(0.12, min(0.24, min(box.w, box.h) * 0.10))
        date = str(item.get('date') or item.get('number') or item.get('label') or '').strip()
        title = str(item.get('title') or '').strip()
        body = str(item.get('body') or '').strip()
        y = box.y + pad
        if date:
            date_h = min(0.38, max(0.26, box.h * 0.16))
            date_box = Box(box.x + pad, y, box.w - 2*pad, date_h)
            sh = _add_text(slide,date_box,date,styles['number'],'number',theme,size_override=max(11,min(17,date_h*31)),color_override=theme['accent'],bold_override=True)
            generated.append({'role':'timeline_date','item_index':index-1,'output_shape_id':sh.shape_id,'bbox':date_box.as_dict(),'render_text':date})
            y = date_box.bottom + 0.04
        if title:
            title_h = min(0.54, max(0.34, box.h * 0.24))
            title_box = Box(box.x+pad,y,box.w-2*pad,title_h)
            sh = _add_text(slide,title_box,title,styles['item_title'],'item_title',theme,size_override=max(14,min(21,title_h*29)),bold_override=True)
            generated.append({'role':'timeline_title','item_index':index-1,'output_shape_id':sh.shape_id,'bbox':title_box.as_dict(),'render_text':title})
            y = title_box.bottom + 0.05
        if body and box.bottom - y - pad > 0.22:
            body_box = Box(box.x+pad,y,box.w-2*pad,box.bottom-y-pad)
            sh = _add_text(slide,body_box,body,styles['item_body'],'item_body',theme,size_override=max(11,min(16,body_box.h*7.0)))
            generated.append({'role':'timeline_body','item_index':index-1,'output_shape_id':sh.shape_id,'bbox':body_box.as_dict(),'render_text':body})
    return generated


def _add_kpi_cards(slide, boxes: list[Box], request: dict[str, Any], styles: dict[str, Any], theme: dict[str, str]) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    items = list(request.get('items') or [])
    for index, (item, box) in enumerate(zip(items, boxes), start=1):
        accent = bool(item.get('accent') or item.get('highlight'))
        panel = _add_panel(slide, box, theme, fill_color='FFF7F0' if accent else 'FFFFFF', line_color='none' if accent else theme['line'], opacity=1.0)
        generated.append({'role':'kpi_panel','item_index':index-1,'output_shape_id':panel.shape_id,'bbox':box.as_dict()})
        pad = max(0.14, min(0.30, min(box.w,box.h)*0.10))
        label = str(item.get('label') or item.get('title') or '').strip()
        value = str(item.get('value') or item.get('number') or '').strip()
        note = str(item.get('note') or item.get('body') or '').strip()
        y = box.y + pad
        if label:
            label_h = min(0.48, max(0.28, box.h*0.16))
            label_box = Box(box.x+pad,y,box.w-2*pad,label_h)
            sh=_add_text(slide,label_box,label,styles['item_title'],'item_title',theme,size_override=max(13,min(18,label_h*31)),bold_override=True,color_override=theme['accent'] if accent else None)
            generated.append({'role':'kpi_label','item_index':index-1,'output_shape_id':sh.shape_id,'bbox':label_box.as_dict(),'render_text':label})
            y=label_box.bottom+0.06
        if value:
            value_h=min(max(0.62,box.h*0.38),1.35)
            value_box=Box(box.x+pad,y,box.w-2*pad,value_h)
            sh=_add_text(slide,value_box,value,styles['title'],'kpi_value',theme,size_override=max(24,min(48,value_h*30)),bold_override=True,color_override=theme['accent'] if accent else theme['dark'])
            generated.append({'role':'kpi_value','item_index':index-1,'output_shape_id':sh.shape_id,'bbox':value_box.as_dict(),'render_text':value})
            y=value_box.bottom+0.05
        if note and box.bottom-y-pad>0.20:
            note_box=Box(box.x+pad,y,box.w-2*pad,box.bottom-y-pad)
            sh=_add_text(slide,note_box,note,styles['item_body'],'caption',theme,size_override=max(10,min(14,note_box.h*6.6)))
            generated.append({'role':'kpi_note','item_index':index-1,'output_shape_id':sh.shape_id,'bbox':note_box.as_dict(),'render_text':note})
    return generated


def _chart_payload(request: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], str]:
    categories = [str(x) for x in (request.get('categories') or [])]
    series = list(request.get('series') or [])
    if not categories or not series:
        raise ValueError('chart layout requires categories and series')
    for row in series:
        values = list(row.get('values') or [])
        if len(values) != len(categories):
            raise ValueError('chart series length must equal category count')
    chart_type = str(request.get('chart_type') or 'column').lower()
    return categories, series, chart_type


def _add_native_chart(slide, box: Box, request: dict[str, Any], theme: dict[str, str]) -> tuple[Any, int]:
    categories, series, chart_type = _chart_payload(request)
    mapping = {
        'column': XL_CHART_TYPE.COLUMN_CLUSTERED,
        'bar': XL_CHART_TYPE.BAR_CLUSTERED,
        'line': XL_CHART_TYPE.LINE_MARKERS,
        'area': XL_CHART_TYPE.AREA,
        'pie': XL_CHART_TYPE.PIE,
    }
    if chart_type not in mapping:
        raise ValueError(f'unsupported chart_type: {chart_type}')
    data = ChartData(); data.categories = categories
    for row in series:
        data.add_series(str(row.get('name') or ''), [float(v) for v in row.get('values') or []])
    frame = slide.shapes.add_chart(mapping[chart_type], _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h), data)
    chart = frame.chart
    chart.has_title = False
    chart.has_legend = bool(request.get('has_legend', len(series) > 1))
    if chart.has_legend:
        try: chart.legend.include_in_layout = False
        except Exception: pass
    try:
        chart.value_axis.has_major_gridlines = bool(request.get('major_gridlines', chart_type not in {'pie'}))
        chart.value_axis.minimum_scale = float(request['minimum_scale']) if request.get('minimum_scale') is not None else None
    except Exception:
        pass
    return frame, len(series)

def _metrics(
    canvas: Box,
    visual_boxes: list[Box],
    family: str,
    density: str,
    fill_policy: dict[str, Any],
    *,
    expected_items: int = 0,
    rendered_items: int = 0,
    expected_images: int = 0,
    rendered_images: int = 0,
    image_boxes: list[Box] | None = None,
) -> dict[str, Any]:
    mode=str(fill_policy.get('mode') or 'balanced')
    u=_union(visual_boxes)
    if u is None:
        return {
            'check':'LAYOUT_FIT_TO_INTENT',
            'status':'fail','score':0.0,'reason':'no_generated_content',
            'fill_policy':fill_policy,'intentional_whitespace':mode=='intentional_whitespace',
            'accidental_dead_space':True,'reason_codes':['NO_GENERATED_CONTENT'],
        }

    extent_w=min(1.0,u.w/max(canvas.w,1e-6)); extent_h=min(1.0,u.h/max(canvas.h,1e-6))
    area_sum=sum(max(0,b.w)*max(0,b.h) for b in visual_boxes)
    area_ratio=min(1.0,area_sum/max(canvas.w*canvas.h,1e-6))
    edge_left=max(0.0,(u.x-canvas.x)/max(canvas.w,1e-6))
    edge_top=max(0.0,(u.y-canvas.y)/max(canvas.h,1e-6))
    edge_right=max(0.0,(canvas.right-u.right)/max(canvas.w,1e-6))
    edge_bottom=max(0.0,(canvas.bottom-u.bottom)/max(canvas.h,1e-6))
    center_x=abs((u.x+u.w/2)-(canvas.x+canvas.w/2))/max(canvas.w,1e-6)
    center_y=abs((u.y+u.h/2)-(canvas.y+canvas.h/2))/max(canvas.h,1e-6)

    target_area=_density_settings(density)['target_area']
    thresholds={
        'content_filled': {'w':0.88,'h':0.62,'area':target_area*0.72,'max_edge_void':0.30,'max_center_x':0.38,'max_center_y':0.38},
        'balanced': {'w':0.70,'h':0.44,'area':max(0.16,target_area*0.44),'max_edge_void':0.43,'max_center_x':0.42,'max_center_y':0.42},
        'intentional_whitespace': {'w':0.46,'h':0.20,'area':0.07,'max_edge_void':0.72,'max_center_x':0.38,'max_center_y':0.42},
        'preserve_source': {'w':0.28,'h':0.14,'area':0.035,'max_edge_void':0.82,'max_center_x':0.52,'max_center_y':0.52},
        'full_bleed': {'w':0.94,'h':0.78,'area':0.62,'max_edge_void':0.12,'max_center_x':0.18,'max_center_y':0.18},
    }.get(mode, {'w':0.70,'h':0.44,'area':max(0.16,target_area*0.44),'max_edge_void':0.43,'max_center_x':0.42,'max_center_y':0.42})

    # A statement should have slightly stronger horizontal presence even when whitespace
    # is deliberate; this prevents a tiny sentence from becoming a decorative speck.
    if family in {'statement','cover','section','closing'} and mode == 'intentional_whitespace':
        thresholds = {**thresholds, 'w': max(thresholds['w'], 0.52)}
    # Relationship maps deliberately preserve whitespace between nodes and connectors.
    # Their semantic occupancy is the network, not a solid rectangular block.
    if family == 'relationship':
        thresholds = {
            **thresholds,
            'w': min(thresholds['w'], 0.72),
            'h': min(thresholds['h'], 0.50),
            'area': min(thresholds['area'], 0.12),
            'max_edge_void': max(thresholds['max_edge_void'], 0.38),
        }
    if family == 'photo_text':
        thresholds = {**thresholds, 'area': min(thresholds['area'], 0.24)}
    if family == 'timeline':
        thresholds = {**thresholds, 'area': min(thresholds['area'], 0.16), 'h': min(thresholds['h'], 0.48)}
    if family == 'chart':
        thresholds = {**thresholds, 'area': min(thresholds['area'], 0.30), 'h': min(thresholds['h'], 0.58)}
    if family == 'kpi':
        thresholds = {**thresholds, 'area': min(thresholds['area'], 0.22)}

    missing_items=bool(expected_items and rendered_items < expected_items)
    missing_images=bool(expected_images and rendered_images < expected_images)
    image_boxes=list(image_boxes or [])
    image_area_ratio=min(1.0,sum(max(0,b.w)*max(0,b.h) for b in image_boxes)/max(canvas.w*canvas.h,1e-6))
    # `content_filled` is for pages whose meaning comes from a set of items, a table,
    # a process, or another sufficiently rich visual structure. Enlarging one sentence
    # until it covers the canvas is not valid content fill; that page should use
    # `intentional_whitespace` or `balanced` instead.
    semantic_policy_mismatch = bool(
        mode == 'content_filled' and family in {'statement','cover','section'} and expected_items == 0
    )
    # The current v0.1 engine has no primary image slot. Do not pretend that text/cards
    # constitute a full-bleed visual.
    if mode == 'full_bleed' and family != 'full_bleed':
        semantic_policy_mismatch = True
    if family == 'full_bleed' and mode != 'full_bleed':
        semantic_policy_mismatch = True
    if family == 'photo_text' and expected_images and image_area_ratio < 0.22:
        semantic_policy_mismatch = True
    tiny_island=extent_w < thresholds['w'] or extent_h < thresholds['h'] or area_ratio < thresholds['area']
    off_balance=center_x > thresholds['max_center_x'] or center_y > thresholds['max_center_y']
    excessive_void=max(edge_left,edge_right,edge_top,edge_bottom) > thresholds['max_edge_void']

    if mode in {'intentional_whitespace','preserve_source'}:
        # Edge void is expected. Fail only when the focus becomes too small/off-balance,
        # or when semantic items disappeared.
        accidental_dead_space=missing_items or missing_images or tiny_island or off_balance or semantic_policy_mismatch
    else:
        accidental_dead_space=missing_items or missing_images or tiny_island or off_balance or excessive_void or semantic_policy_mismatch

    reason_codes=[]
    if missing_items: reason_codes.append('MISSING_SEMANTIC_ITEMS')
    if missing_images: reason_codes.append('MISSING_PRIMARY_VISUAL')
    if semantic_policy_mismatch: reason_codes.append('POLICY_SEMANTIC_MISMATCH')
    if tiny_island: reason_codes.append('CONTENT_ISLAND_TOO_SMALL')
    if off_balance: reason_codes.append('OPTICAL_FOCUS_OFF_BALANCE')
    if excessive_void and mode not in {'intentional_whitespace','preserve_source'}:
        reason_codes.append('UNINTENTIONAL_EDGE_VOID')
    if not reason_codes:
        reason_codes.append('FIT_TO_INTENT')

    presence=min(1.0,(min(1.0,extent_w/max(thresholds['w'],1e-6))*0.36 +
                      min(1.0,extent_h/max(thresholds['h'],1e-6))*0.30 +
                      min(1.0,area_ratio/max(thresholds['area'],1e-6))*0.34))
    balance=max(0.0,1.0-max(center_x/max(thresholds['max_center_x'],1e-6),center_y/max(thresholds['max_center_y'],1e-6)))
    if mode in {'content_filled','balanced','full_bleed'}:
        void_score=max(0.0,1.0-max(edge_left,edge_right,edge_top,edge_bottom)/max(thresholds['max_edge_void'],1e-6))
        score=0.72*presence+0.16*balance+0.12*void_score
    else:
        score=0.78*presence+0.22*balance
    if missing_items or missing_images:
        score*=0.25

    return {
        'check':'LAYOUT_FIT_TO_INTENT',
        'status':'fail' if accidental_dead_space else 'pass',
        'assessment':'要調整' if accidental_dead_space else '適正',
        'score':round(min(1.0,max(0.0,score)),3),
        'fill_policy':fill_policy,
        'intentional_whitespace':mode=='intentional_whitespace',
        'preserve_source_whitespace':mode=='preserve_source',
        'accidental_dead_space':bool(accidental_dead_space),
        'content_extent_width_ratio':round(extent_w,3),
        'content_extent_height_ratio':round(extent_h,3),
        'occupied_area_ratio':round(area_ratio,3),
        'left_void_ratio':round(edge_left,3),
        'right_void_ratio':round(edge_right,3),
        'top_void_ratio':round(edge_top,3),
        'bottom_void_ratio':round(edge_bottom,3),
        'center_offset_x_ratio':round(center_x,3),
        'center_offset_y_ratio':round(center_y,3),
        'expected_item_count':expected_items,
        'rendered_item_count':rendered_items,
        'expected_image_count':expected_images,
        'rendered_image_count':rendered_images,
        'image_area_ratio':round(image_area_ratio,3),
        'thresholds':{k:round(v,3) if isinstance(v,float) else v for k,v in thresholds.items()},
        'content_bbox':u.as_dict(),
        'reason_codes':reason_codes,
    }


def _remove_source_objects(slide, ids: list[str], *, exclude_ids: set[str] | None = None) -> list[str]:
    by = {shape.shape_id: shape for shape in slide.shapes}
    excluded = {str(value) for value in (exclude_ids or set())}
    removed: list[str] = []
    for oid in ids:
        if oid in excluded:
            continue
        sid = _sid(oid)
        shape = by.get(sid) if sid is not None else None
        if shape is None:
            continue
        element = shape.element
        if element.getparent() is not None:
            element.getparent().remove(element)
            removed.append(oid)
    return removed


@lru_cache(maxsize=32)
def _exact_presentation_size(source_path: str) -> tuple[float, float]:
    prs = Presentation(source_path)
    return float(prs.slide_width) / EMU_PER_INCH, float(prs.slide_height) / EMU_PER_INCH


def _slide_box(root: Path) -> Box:
    source = root / 'inputs/source.pptx'
    if source.exists():
        try:
            width, height = _exact_presentation_size(str(source.resolve()))
            return Box(0.0, 0.0, width, height)
        except Exception:
            pass
    profile = read_json(root / 'analysis/template_profile.json', {})
    pres = profile.get('presentation') or {}
    return Box(0.0, 0.0, float(pres.get('width_in') or 13.333), float(pres.get('height_in') or 7.5))


def _layout_context(
    root: Path, slide, slide_plan: dict[str, Any], *, require_image_asset: bool = False
) -> dict[str, Any]:
    raw_request = deepcopy(slide_plan.get('layout_request') or {})
    family = str(raw_request.get('family') or '').strip()
    if family not in SUPPORTED_LAYOUT_FAMILIES:
        raise ValueError(f'layout_engine family not supported: {family or "<missing>"}')
    semantic_issues = semantic_layout_issues(slide_plan)
    blocking_semantic = [x for x in semantic_issues if x.get('severity') == 'blocking']
    if blocking_semantic:
        issue = blocking_semantic[0]
        raise ValueError(f"semantic layout forbidden: {issue.get('relation')} -> {issue.get('family')}")
    source_slide_id = slide_plan.get('source_slide_id')
    if not source_slide_id:
        raise ValueError('layout_request requires source_slide_id')
    image_context = _resolve_image_context(
        root, slide_plan, raw_request, require_asset=require_image_asset
    )
    request = _derive_photo_request(raw_request, image_context)
    design = _parse_design(root)
    density = str(request.get('density') or design.get('density') or 'medium_low')
    fill_policy = _resolve_fill_policy(root, slide_plan, request, family, design)
    slide_box = _slide_box(root)
    canvas = _derive_canvas(root, slide, source_slide_id, request, fill_policy)
    geom = _geometry_for_family(slide_box, canvas, request, density, fill_policy['mode'])
    return {
        'request': request,
        'raw_request': raw_request,
        'family': family,
        'source_slide_id': source_slide_id,
        'design': design,
        'density': density,
        'fill_policy': fill_policy,
        'slide_box': slide_box,
        'canvas': canvas,
        'geometry': geom,
        'image_context': image_context,
        'semantic_issues': semantic_issues,
        'renderer_group': renderer_group(family),
    }


def _geometry_dict(geom: dict[str, Any]) -> dict[str, Any]:
    keys = [
        'title_box', 'subtitle_box', 'body_box', 'body', 'text_box', 'image_box',
        'overlay_box', 'matrix_box', 'relationship_box', 'timeline_box',
        'timeline_line_box', 'kpi_box', 'chart_box', 'note_box', 'kicker_box',
    ]
    out = {key: geom[key].as_dict() if isinstance(geom.get(key), Box) else None for key in keys}
    out.update({
        'item_boxes': [b.as_dict() for b in (geom.get('item_boxes') or [])],
        'node_boxes': {str(k): v.as_dict() for k, v in (geom.get('node_boxes') or {}).items() if isinstance(v, Box)},
        'columns': geom.get('cols'),
        'rows': geom.get('rows'),
        'divider_x': round(float(geom['divider_x']), 4) if geom.get('divider_x') is not None else None,
        'image_position': geom.get('image_position'),
        'resolved_text_side': geom.get('resolved_text_side'),
        'overlay_position': geom.get('overlay_position'),
        'hub_id': geom.get('hub_id'),
        'card_mode': geom.get('card_mode'),
        'orientation': geom.get('orientation'),
        'timeline_markers': geom.get('timeline_markers') or [],
        'note_text': geom.get('note_text'),
        'kicker_text': geom.get('kicker_text'),
    })
    return out


def _layout_image_slot(
    root: Path, slide_plan: dict[str, Any], geom: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    request = request or slide_plan.get('layout_request') or {}
    image_box = geom.get('image_box')
    if not isinstance(image_box, Box):
        return None
    recipe_id = str(request.get('image_recipe_id') or f'IMG-{slide_plan.get("slide_id")}-01')
    # Persist only the generated recipe id as a technical normalization. Geometry
    # and render choices remain downstream data.
    original_request = slide_plan.setdefault('layout_request', {})
    original_request.setdefault('image_recipe_id', recipe_id)
    family = str(request.get('family') or '')
    slot_id = str(request.get('image_slot_id') or f'{slide_plan.get("slide_id")}:primary_visual')
    style_ids = request.get('style_source_object_ids') or {}
    reuse_source = bool(request.get('reuse_source_image_frame', True))
    source_object_id = str(request.get('image_source_object_id') or style_ids.get('image') or '').strip() or None
    if source_object_id and reuse_source:
        source_obj = _source_objects(root, slide_plan.get('source_slide_id')).get(_sid(source_object_id))
        if not source_obj or not source_obj.get('picture'):
            source_object_id = None
    else:
        source_object_id = None
    return {
        'slot_id': slot_id,
        'recipe_id': recipe_id,
        'bbox': image_box.as_dict(),
        'aspect_ratio': round(image_box.w / max(image_box.h, 1e-6), 5),
        'role': 'background_visual' if family == 'full_bleed' else 'primary_visual',
        'position': geom.get('image_position') or geom.get('overlay_position') or 'background',
        'resolved_text_side': geom.get('resolved_text_side') or request.get('resolved_text_side'),
        'source_object_id': source_object_id,
        'reuse_source_image_frame': bool(source_object_id and reuse_source),
    }


def _bbox_changed(old: dict[str, Any] | None, new: dict[str, Any]) -> bool:
    if not old:
        return True
    try:
        old_ar = float(old['w']) / float(old['h'])
        new_ar = float(new['w']) / float(new['h'])
        area_ratio = (float(new['w']) * float(new['h'])) / max(1e-6, float(old['w']) * float(old['h']))
        return abs(math.log(max(1e-6, old_ar) / max(1e-6, new_ar))) > 0.018 or area_ratio < 0.72 or area_ratio > 1.38
    except Exception:
        return True


def _sync_layout_image_recipe(
    root: Path, slide_plan: dict[str, Any], slot: dict[str, Any] | None,
    request: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if slot is None:
        return None
    request = request or slide_plan.get('layout_request') or {}
    recipes_doc = read_json(root / 'planning/image_recipes.json', {'schema_version': '0.2', 'recipes': []})
    recipes = recipes_doc.setdefault('recipes', [])
    rid = slot['recipe_id']
    recipe = next((row for row in recipes if row.get('recipe_id') == rid), None)
    created = recipe is None
    art = read_json(root / 'planning/deck_art_direction.json', {})
    fingerprint = read_json(root / 'analysis/design_fingerprint.json', {})
    target_metrics = art.get('target_metrics') or (fingerprint.get('image_treatment') or {}).get('target_metrics') or {}
    family = str(request.get('family') or '')
    suggested_negative = str(slot.get('resolved_text_side') or 'none')
    if family == 'full_bleed':
        overlay = str(request.get('overlay_position') or slot.get('position') or 'left')
        suggested_negative = 'right' if overlay in {'right', 'bottom_right'} else 'left' if overlay in {'left', 'bottom_left'} else 'none'
    source_object_id = slot.get('source_object_id')
    source_asset = None
    if source_object_id:
        assets = read_json(root / 'analysis/source_assets.json', {})
        source_asset = next((
            row for row in assets.get('assets', [])
            if row.get('source_slide_id') == slide_plan.get('source_slide_id')
            and row.get('source_object_id') == source_object_id
        ), None)
    if recipe is None:
        recipe = {
            'recipe_id': rid,
            'slide_id': slide_plan.get('slide_id'),
            'slot_index': 1,
            'purpose': 'full_bleed_visual' if family == 'full_bleed' else 'photo_text_primary_visual',
            'message': request.get('title') or request.get('body') or '',
            'medium': str(request.get('image_medium') or ('conceptual_image' if family == 'full_bleed' else 'photo')),
            'provider': 'auto',
            'prompt_seed': str(request.get('image_prompt_seed') or request.get('title') or 'presentation visual'),
            'target': {},
            'composition': {
                'focal_point': 'auto',
                'negative_space': suggested_negative,
                'background_complexity': 'low_to_medium',
            },
            'treatment': {
                'preset': 'match_deck_art_direction_for_layout_slot',
                'fit': 'cover',
                'frame': 'preserve_source_picture_format' if source_object_id and slot.get('reuse_source_image_frame') else 'layout_generated_frame',
                'target_metrics': target_metrics,
            },
            'style_reference': {
                'primary_source_asset_id': (source_asset or {}).get('asset_id'),
                'deck_reference_asset_ids': (art.get('reference_asset_ids') or []),
                'lineage': 'source_picture_plus_layout_slot' if source_asset else 'layout_slot_plus_deck_art_direction',
            },
            'palette': 'derive_from_deck_art_direction',
            'quality': 'medium',
            'status': 'NEEDS_ASSET',
            'review_reason': None,
            'selected_asset_id': None,
            'origin': 'layout_engine_recipe_seed',
        }
        recipes.append(recipe)
    target = recipe.setdefault('target', {})
    old_bbox = target.get('bbox') if isinstance(target.get('bbox'), dict) else None
    old_slot = target.get('layout_slot_id')
    old_source_object_id = target.get('source_object_id')
    invalidated = bool(recipe.get('selected_asset_id') and (
        _bbox_changed(old_bbox, slot['bbox'])
        or old_slot != slot['slot_id']
        or old_source_object_id != source_object_id
    ))
    source_bbox = ((source_asset or {}).get('bbox') or {}) if source_asset else {}
    # The layout slot is authoritative. When the current plan stops reusing a
    # source Picture, clear old source-target lineage rather than carrying a stale
    # source_object_id forward from an earlier layout version. Style lineage may
    # remain in style_reference, but the mutable target must reflect the current
    # deterministic plan exactly.
    target.update({
        'source_slide_id': slide_plan.get('source_slide_id'),
        'source_object_id': source_object_id,
        'source_asset_id': (source_asset or {}).get('asset_id'),
        'layout_slot_id': slot['slot_id'],
        'bbox': slot['bbox'],
        'aspect_ratio': slot['aspect_ratio'],
        'frame_asset_ids': target.get('frame_asset_ids') or [],
        'source_media_path': (source_asset or {}).get('media_path'),
        'source_visual_metrics': (source_asset or {}).get('visual_metrics'),
        'source_display': {
            **(target.get('source_display') or {}),
            'original_bbox': source_bbox or None,
            'slot_aspect_ratio': slot['aspect_ratio'],
            'layout_generated': True,
            'shape_reuse_requested': bool(source_object_id and slot.get('reuse_source_image_frame')),
        },
    })
    if recipe.get('composition_origin') != 'user':
        recipe.setdefault('composition', {})['negative_space'] = suggested_negative
    recipe.setdefault('treatment', {})['frame'] = (
        'preserve_source_picture_format' if source_object_id and slot.get('reuse_source_image_frame') else 'layout_generated_frame'
    )
    style_ref = recipe.setdefault('style_reference', {})
    if source_asset:
        style_ref['primary_source_asset_id'] = source_asset.get('asset_id')
        style_ref['lineage'] = 'source_picture_plus_layout_slot'
    if invalidated:
        recipe['selected_asset_id'] = None
        recipe['status'] = 'NEEDS_ASSET'
        recipe['review_reason'] = 'The deterministic layout slot changed; regenerate or reselect the image for the new crop.'
    elif not recipe.get('selected_asset_id'):
        recipe['status'] = 'NEEDS_ASSET'
    recipes_doc['generated_at'] = now_iso()
    write_json(root / 'planning/image_recipes.json', recipes_doc)
    if created or invalidated or old_bbox != slot['bbox'] or old_slot != slot['slot_id'] or old_source_object_id != source_object_id:
        append_jsonl(root / 'decisions/decision_trace.jsonl', {
            'decision_id': f'LAYOUT-IMAGE-SLOT-{slide_plan.get("slide_id")}-{rid}-{now_iso().replace(":","").replace("-","").replace(".","")}',
            'timestamp': now_iso(),
            'phase': 'layout_planning',
            'target': {'type': 'slide', 'id': slide_plan.get('slide_id')},
            'decision_type': 'plan_image_layout_slot',
            'selected': slot,
            'reason_text': 'The image crop target is generated by the layout engine before image selection; the model does not choose coordinates.',
            'origin': 'system',
            'rerun_scope': [f'{slide_plan.get("slide_id")}:image', f'{slide_plan.get("slide_id")}:render', f'{slide_plan.get("slide_id")}:qa', 'deck_harmony'],
        })
    state = load_state(root)
    sid = slide_plan.get('slide_id')
    if sid:
        ss = ensure_slide(state, sid)
        if invalidated or not recipe.get('selected_asset_id'):
            if ss.get('image') not in {'LOCKED', 'STALE_LOCKED'}:
                ss['image'] = 'DRAFT'
            for phase in ('render', 'qa'):
                ss[phase] = 'STALE_LOCKED' if ss.get(phase) == 'LOCKED' else 'STALE'
        if ss.get('layout') not in {'LOCKED', 'STALE_LOCKED'}:
            ss['layout'] = 'APPROVED'
        state['deck_harmony'] = 'STALE'
        save_state(root, state)
    return recipe


def _planned_visual_boxes(geom: dict[str, Any]) -> list[Box]:
    boxes: list[Box] = []
    for key in (
        'title_box', 'subtitle_box', 'body_box', 'image_box', 'overlay_box',
        'matrix_box', 'relationship_box', 'timeline_box', 'kpi_box', 'chart_box',
        'kicker_box', 'note_box',
    ):
        value = geom.get(key)
        if isinstance(value, Box):
            boxes.append(value)
    boxes.extend(b for b in (geom.get('item_boxes') or []) if isinstance(b, Box))
    # `relationship_box` expresses the semantic diagram extent. Node boxes are
    # retained in geometry for QA but not double-counted in occupied-area metrics.
    return boxes


def _expected_item_count(family: str, request: dict[str, Any], geom: dict[str, Any]) -> int:
    if family in {'grid', 'process', 'two_column', 'timeline', 'kpi', 'closing'}:
        return len(request.get('items') or [])
    if family == 'comparison_matrix':
        labels, _columns, _highlight = _matrix_payload(request)
        return len(labels)
    if family == 'relationship':
        return len(geom.get('nodes') or request.get('nodes') or request.get('items') or [])
    return 0


def _build_layout_plan(
    root: Path,
    slide_plan: dict[str, Any],
    ctx: dict[str, Any],
    *,
    rendered: bool,
    generated: list[dict[str, Any]] | None = None,
    removed: list[str] | None = None,
    rendered_images: int = 0,
    rendered_items: int | None = None,
) -> dict[str, Any]:
    family = ctx['family']
    geom = ctx['geometry']
    canvas = ctx['canvas']
    fill_policy = ctx['fill_policy']
    request = ctx['request']
    image_context = ctx.get('image_context') or {}
    image_slot = _layout_image_slot(root, slide_plan, geom, request)
    if image_slot:
        synced_recipe = _sync_layout_image_recipe(root, slide_plan, image_slot, request)
        if synced_recipe and not image_context:
            image_context = {
                'recipe_id': synced_recipe.get('recipe_id'),
                'recipe': synced_recipe,
                'asset_id': synced_recipe.get('selected_asset_id'),
                'source_object_id': (synced_recipe.get('target') or {}).get('source_object_id'),
                'negative_space': (synced_recipe.get('composition') or {}).get('negative_space') or 'none',
                'source_bbox': None,
            }
    visual_boxes = _planned_visual_boxes(geom)
    expected_items = _expected_item_count(family, request, geom)
    actual_items = expected_items if not rendered else int(rendered_items if rendered_items is not None else expected_items)
    expected_images = 1 if image_slot else 0
    quality = _metrics(
        ctx['slide_box'] if family == 'full_bleed' else canvas,
        visual_boxes, family, ctx['density'], fill_policy,
        expected_items=expected_items,
        rendered_items=actual_items,
        expected_images=expected_images,
        rendered_images=rendered_images if rendered else expected_images,
        image_boxes=[geom['image_box']] if isinstance(geom.get('image_box'), Box) else [],
    )
    _record_fill_policy_decision(root, slide_plan, family, fill_policy, quality)

    allowed_regions: list[dict[str, float]] = []
    if family == 'full_bleed' and isinstance(geom.get('image_box'), Box):
        allowed_regions.append(geom['image_box'].as_dict())
    else:
        allowed_regions.append(quality.get('content_bbox') or canvas.as_dict())
        if isinstance(geom.get('image_box'), Box):
            allowed_regions.append(geom['image_box'].as_dict())
        source_bbox = image_context.get('source_bbox')
        if isinstance(source_bbox, Box):
            allowed_regions.append(source_bbox.as_dict())

    deduped_regions: list[dict[str, float]] = []
    seen_regions: set[tuple[float, float, float, float]] = set()
    for region in allowed_regions:
        key = tuple(round(float(region[k]), 4) for k in ('x', 'y', 'w', 'h'))
        if key in seen_regions:
            continue
        seen_regions.add(key)
        deduped_regions.append(region)

    image_lineage = None
    if image_slot:
        image_lineage = {
            'recipe_id': image_context.get('recipe_id') or image_slot.get('recipe_id'),
            'asset_id': image_context.get('asset_id'),
            'source_object_id': image_context.get('source_object_id'),
            'negative_space': image_context.get('negative_space') or 'none',
            'resolved_text_side': request.get('resolved_text_side'),
            'source_frame_reused': bool(
                image_context.get('source_object_id') and request.get('reuse_source_image_frame', True)
            ),
        }

    plan = {
        'schema_version': '0.3',
        'generated_at': now_iso(),
        'slide_id': slide_plan.get('slide_id'),
        'source_slide_id': ctx['source_slide_id'],
        'family': family,
        'renderer_group': ctx.get('renderer_group') or renderer_group(family),
        'semantic_relation': slide_plan.get('semantic_relation'),
        'semantic_layout_issues': ctx.get('semantic_issues') or [],
        'density': ctx['density'],
        'fill_policy': fill_policy,
        'planned_only': not rendered,
        'content_canvas': canvas.as_dict(),
        'removed_source_object_ids': list(removed or []),
        'allowed_regions': deduped_regions,
        'generated_objects': list(generated or []),
        'image_slots': [image_slot] if image_slot else [],
        'image_lineage': image_lineage,
        'layout_intent': {
            'family': family,
            'fill_policy': fill_policy.get('mode'),
            'resolved_text_side': request.get('resolved_text_side') or geom.get('resolved_text_side'),
            'image_position': geom.get('image_position'),
            'overlay_position': geom.get('overlay_position'),
        },
        'quality': quality,
        'geometry': _geometry_dict(geom),
        'notes': [
            'Layout geometry is deterministic. The model selects family, hierarchy, and priorities; coordinates are engine-generated.',
            'Photo-aware families plan image slots before image selection so crop, resolution, and negative-space QA use the actual target geometry.',
            'Existing picture relationships and source frames are reused when available; template chrome remains outside the mutation mask.',
            'LAYOUT_FIT_TO_INTENT distinguishes deliberate whitespace from accidental dead space. Filler content is never added merely to raise occupancy.',
        ],
    }
    out = root / 'render/layout_plans' / f'{slide_plan.get("slide_id")}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, plan)
    return plan

def plan_layouts(project: str | Path, *, slide_ids: list[str] | None = None) -> dict[str, Any]:
    root = Path(project).resolve()
    deck = read_json(root / 'planning/deck_plan.json', {'slides': []})
    wanted = set(slide_ids or [])
    plans: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    prs = Presentation(root / 'inputs/source.pptx')
    for slide_row in sorted(deck.get('slides', []), key=lambda row: row.get('order', 9999)):
        sid = slide_row.get('slide_id')
        if wanted and sid not in wanted:
            continue
        plan_path = root / f'planning/slide_plans/{sid}.json'
        slide_plan = read_json(plan_path, None)
        if not slide_plan or not slide_plan.get('layout_request'):
            continue
        source_id = slide_plan.get('source_slide_id')
        try:
            page = int(str(source_id).split('S')[-1])
            source_slide = prs.slides[page - 1]
            ctx = _layout_context(root, source_slide, slide_plan)
            plan = _build_layout_plan(root, slide_plan, ctx, rendered=False)
            # Normalizing a generated recipe id is a technical detail, not a semantic rewrite.
            write_json(plan_path, slide_plan)
            plans.append(plan)
        except Exception as exc:
            errors.append({'slide_id': sid, 'error': str(exc)})
    return {'schema_version': '0.1', 'generated_at': now_iso(), 'planned': len(plans), 'errors': errors, 'slides': plans}


def _hex_is_dark(value: str | None, fallback: str = '000000') -> bool:
    raw = str(value or fallback).replace('#', '').strip()
    if len(raw) != 6:
        raw = fallback
    try:
        r, g, b = (int(raw[index:index + 2], 16) for index in (0, 2, 4))
    except Exception:
        return True
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    return luminance < 0.52


def _dark_color(value: str | None) -> bool:
    raw = str(value or '').replace('#', '').strip()
    if len(raw) != 6:
        return False
    try:
        r, g, b = (int(raw[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return False
    # Relative-luminance approximation is sufficient for choosing editable text color.
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 128


def apply_layout(root: str | Path, slide, slide_plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    ctx = _layout_context(root, slide, slide_plan)
    request = ctx['request']; family = ctx['family']; geom = ctx['geometry']; theme = _theme(root, ctx['source_slide_id'])
    styles = _resolve_style_shapes(slide, request)
    image_context = _resolve_image_context(
        root, slide_plan, request, require_asset=family in {'photo_text', 'full_bleed'},
    )
    by_shape = {shape.shape_id: shape for shape in slide.shapes}
    image_sid = _sid((image_context or {}).get('source_object_id'))
    if image_sid is None:
        image_sid = _sid((request.get('style_source_object_ids') or {}).get('image'))
    template_image = by_shape.get(image_sid) if image_sid is not None else None
    if template_image is not None and getattr(template_image, 'shape_type', None) != MSO_SHAPE_TYPE.PICTURE:
        template_image = None
    reuse_picture = bool(request.get('reuse_source_image_frame', True) and template_image is not None)
    # Template chrome is a hard invariant. Even if a broad content-clear list
    # accidentally includes a repeated logo, page marker, or brand ornament, the
    # deterministic engine must keep it. This also prevents a newly added shape
    # from reusing the removed chrome shape id and appearing as a geometry change.
    protected_ids: set[str] = {
        str(asset.get('source_object_id'))
        for asset in _chrome_assets(root, ctx['source_slide_id'])
        if asset.get('source_object_id')
    }
    if reuse_picture and image_sid is not None:
        protected_ids.add(f'{ctx["source_slide_id"]}-O{image_sid:03d}')
    clear_ids = [oid for oid in list(request.get('clear_region_object_ids') or []) if oid not in protected_ids]
    removed = _remove_source_objects(slide, clear_ids)

    generated: list[dict[str, Any]] = []
    rendered_images = 0

    if family in {'photo_text', 'full_bleed'} and isinstance(geom.get('image_box'), Box):
        assert image_context is not None and image_context.get('image_path') is not None
        picture, border = _place_picture(
            slide, geom['image_box'], image_context['image_path'],
            template_shape=template_image if reuse_picture else None,
            focal_point=image_context.get('focal_point'),
            send_to_back=family == 'full_bleed',
            add_border=family == 'photo_text' and not reuse_picture,
            theme=theme,
        )
        rendered_images = 1
        generated.append({
            'role': 'background_visual' if family == 'full_bleed' else 'primary_visual',
            'recipe_id': image_context.get('recipe_id'),
            'asset_id': image_context.get('asset_id'),
            'source_object_id': image_context.get('source_object_id'),
            'output_shape_id': picture.shape_id,
            'bbox': geom['image_box'].as_dict(),
            'source_picture_reused': reuse_picture,
            'fit_mode': 'cover',
            'resolved_text_side': request.get('resolved_text_side'),
        })
        if border is not None:
            generated.append({'role': 'image_frame', 'output_shape_id': border.shape_id, 'bbox': geom['image_box'].as_dict()})

    panel_shape = None
    if family == 'full_bleed' and isinstance(geom.get('overlay_box'), Box) and str(request.get('overlay_panel') or 'solid') != 'none':
        overlay_color = str(request.get('overlay_color') or 'FFFFFF')
        panel_shape = _add_panel(
            slide, geom['overlay_box'], theme, source_shape=_source_frame_shape(root, slide, ctx['source_slide_id'], request),
            fill_color=overlay_color, line_color='none',
            opacity=float(request.get('overlay_opacity') if request.get('overlay_opacity') is not None else 0.88),
            rounded=bool(request.get('overlay_rounded', True)),
        )
        generated.append({'role': 'overlay_panel', 'output_shape_id': panel_shape.shape_id, 'bbox': geom['overlay_box'].as_dict(), 'opacity': float(request.get('overlay_opacity') if request.get('overlay_opacity') is not None else 0.88)})

    title = str(request.get('title') or '').strip()
    subtitle = str(request.get('subtitle') or '').strip()
    body_text = str(geom.get('body_text') or _body_text(request)).strip()
    kicker_text = str(geom.get('kicker_text') or '').strip()
    page_text_color = str(request.get('page_text_color') or theme.get('page_text') or theme['dark'])
    full_bleed_text_color = None
    if family == 'full_bleed':
        if str(request.get('overlay_panel') or 'solid') == 'none':
            full_bleed_text_color = str(request.get('overlay_text_color') or 'FFFFFF')
        else:
            overlay_color = str(request.get('overlay_color') or 'FFFFFF')
            full_bleed_text_color = str(request.get('overlay_text_color') or ('FFFFFF' if _dark_color(overlay_color) else theme['dark']))

    if kicker_text and isinstance(geom.get('kicker_box'), Box):
        box = geom['kicker_box']
        shape = _add_text(
            slide, box, kicker_text, styles['number'], 'number', theme,
            size_override=float(request.get('kicker_font_pt') or 15),
            color_override=theme['accent'], bold_override=True,
        )
        generated.append({'role': 'kicker', 'output_shape_id': shape.shape_id, 'bbox': box.as_dict(), 'render_text': kicker_text})
    if title and isinstance(geom.get('title_box'), Box):
        box = geom['title_box']
        default_title_pt = {
            'cover': 48, 'section': 42, 'closing': 40,
            'photo_text': 38, 'full_bleed': 38,
        }.get(family, 31)
        shape = _add_text(
            slide, box, title, styles['title'], 'title', theme,
            size_override=float(request.get('title_font_pt') or default_title_pt),
            color_override=full_bleed_text_color or page_text_color, bold_override=True,
        )
        generated.append({'role': 'title', 'output_shape_id': shape.shape_id, 'bbox': box.as_dict(), 'render_text': title})
    if subtitle and isinstance(geom.get('subtitle_box'), Box):
        box = geom['subtitle_box']
        shape = _add_text(
            slide, box, subtitle, styles['subtitle'], 'subtitle', theme,
            size_override=float(request.get('subtitle_font_pt') or 18), color_override=full_bleed_text_color or page_text_color,
        )
        generated.append({'role': 'subtitle', 'output_shape_id': shape.shape_id, 'bbox': box.as_dict(), 'render_text': subtitle})
    if body_text and isinstance(geom.get('body_box'), Box):
        box = geom['body_box']
        shape = _add_body_text(
            slide, box, body_text, styles['item_body'], theme,
            color_override=full_bleed_text_color or page_text_color,
            size=float(request.get('body_font_pt') or max(14, min(21, box.h * 5.2))),
        )
        if shape is not None:
            generated.append({'role': 'body', 'output_shape_id': shape.shape_id, 'bbox': box.as_dict(), 'render_text': body_text})

    items = list(request.get('items') or [])
    settings = _density_settings(ctx['density'])
    if family in {'grid', 'process'}:
        for idx, (item, box) in enumerate(zip(items, geom.get('item_boxes') or []), start=1):
            normalized = item if item.get('number') else {**item, 'number': f'{idx:02d}'}
            shapes, _boxes = _add_card(slide, box, normalized, styles, theme, settings['card_pad'])
            for shape in shapes:
                if not getattr(shape, 'has_text_frame', False) or not shape.text.strip():
                    continue
                role = 'item_body'
                if shape.text.strip() == str(normalized.get('number', '')).strip(): role = 'number'
                elif shape.text.strip() == str(normalized.get('title', '')).strip(): role = 'item_title'
                generated.append({'role': role, 'item_index': idx - 1, 'output_shape_id': shape.shape_id, 'bbox': Box(_in(shape.left), _in(shape.top), _in(shape.width), _in(shape.height)).as_dict(), 'render_text': shape.text})
    elif family == 'two_column':
        for idx, (item, box) in enumerate(zip(items, geom.get('item_boxes') or []), start=1):
            shapes, _boxes = _add_open_column(slide, box, item, styles, theme, settings['card_pad'])
            for shape in shapes:
                if not getattr(shape, 'has_text_frame', False) or not shape.text.strip():
                    continue
                generated.append({'role': 'column_text', 'item_index': idx - 1, 'output_shape_id': shape.shape_id, 'bbox': Box(_in(shape.left), _in(shape.top), _in(shape.width), _in(shape.height)).as_dict(), 'render_text': shape.text})
        if geom.get('divider_x') is not None:
            boxes = geom.get('item_boxes') or []
            if boxes:
                divider = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, _emu(geom['divider_x']), _emu(boxes[0].y), _emu(geom['divider_x']), _emu(boxes[0].bottom))
                divider.line.color.rgb = _hex_color(theme['line'], 'D8D8D8'); divider.line.width = Pt(1.0)
                generated.append({'role': 'column_divider', 'output_shape_id': divider.shape_id, 'bbox': {'x': round(geom['divider_x'], 4), 'y': round(boxes[0].y, 4), 'w': 0.0, 'h': round(boxes[0].h, 4)}})
    elif family == 'comparison_matrix':
        matrix_box = geom.get('matrix_box')
        if not isinstance(matrix_box, Box):
            raise ValueError('comparison_matrix geometry missing matrix_box')
        table_shape, row_count = _add_comparison_matrix(slide, matrix_box, request, styles, theme)
        generated.append({
            'role': 'comparison_matrix', 'output_shape_id': table_shape.shape_id,
            'bbox': matrix_box.as_dict(), 'editable': True, 'row_count': row_count,
            'column_count': len((request.get('matrix') or {}).get('columns') or items) + 1,
        })
    elif family == 'relationship':
        generated.extend(_add_relationship(
            slide, geom, request, styles, theme,
            source_panel=_source_frame_shape(root, slide, ctx['source_slide_id'], request),
        ))
    elif family == 'timeline':
        generated.extend(_add_timeline(slide, geom, request, styles, theme))
    elif family == 'kpi':
        generated.extend(_add_kpi_cards(slide, list(geom.get('item_boxes') or []), request, styles, theme))
    elif family == 'chart':
        chart_box = geom.get('chart_box')
        if not isinstance(chart_box, Box):
            raise ValueError('chart geometry missing chart_box')
        chart_shape, series_count = _add_native_chart(slide, chart_box, request, theme)
        generated.append({'role':'native_chart','output_shape_id':chart_shape.shape_id,'bbox':chart_box.as_dict(),'editable':True,'series_count':series_count,'chart_type':str(request.get('chart_type') or 'column')})
        note_text = str(geom.get('note_text') or '').strip()
        if note_text and isinstance(geom.get('note_box'), Box):
            note_box = geom['note_box']
            note_shape = _add_text(slide,note_box,note_text,styles['item_body'],'caption',theme,size_override=float(request.get('note_font_pt') or 11),color_override=page_text_color)
            generated.append({'role':'chart_note','output_shape_id':note_shape.shape_id,'bbox':note_box.as_dict(),'render_text':note_text})
    elif family == 'closing':
        for idx, (item, box) in enumerate(zip(items, geom.get('item_boxes') or []), start=1):
            closing_pad = min(settings['card_pad'], max(0.14, box.w * 0.055))
            shapes, _boxes = _add_card(slide, box, item, styles, theme, closing_pad, number_box=False)
            for shape in shapes:
                if not getattr(shape, 'has_text_frame', False) or not shape.text.strip():
                    continue
                generated.append({'role':'closing_item','item_index':idx-1,'output_shape_id':shape.shape_id,'bbox':Box(_in(shape.left),_in(shape.top),_in(shape.width),_in(shape.height)).as_dict(),'render_text':shape.text})

    if family == 'process' and len(geom.get('item_boxes') or []) >= 2:
        boxes = geom['item_boxes']
        for left, right in zip(boxes, boxes[1:]):
            if abs(left.y - right.y) > max(0.12, left.h * 0.25):
                continue
            y = left.y + left.h * 0.5; x1 = left.right + 0.05; x2 = right.x - 0.05
            if x2 <= x1:
                continue
            line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, _emu(x1), _emu(y), _emu(x2), _emu(y))
            line.line.color.rgb = _hex_color(theme['accent'], 'FF9A42'); line.line.width = Pt(1.7)
            generated.append({'role':'process_connector','output_shape_id':line.shape_id,'bbox':{'x':round(x1,4),'y':round(y,4),'w':round(x2-x1,4),'h':0.0}})

    plan = _build_layout_plan(
        root, slide_plan, ctx, rendered=True, generated=generated, removed=removed,
        rendered_images=rendered_images,
    )
    if plan['quality']['status'] != 'pass':
        raise ValueError(f'layout fit-to-intent failed for {slide_plan.get("slide_id")}: {plan["quality"]}')
    return plan

