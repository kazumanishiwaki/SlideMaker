from __future__ import annotations
from pathlib import Path
from collections import Counter, defaultdict
from statistics import median
from typing import Any
import colorsys
import re

from helpers import read_json, write_json, now_iso
from image_metrics import analyze_image




def _hex_rgb(value: str | None) -> tuple[int, int, int] | None:
    raw = str(value or '').replace('#', '').strip()
    if len(raw) != 6 or not re.fullmatch(r'[0-9A-Fa-f]{6}', raw):
        return None
    return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))


def _hex_luminance(value: str | None) -> float | None:
    rgb = _hex_rgb(value)
    if rgb is None:
        return None
    r, g, b = (channel / 255.0 for channel in rgb)
    return round(0.2126 * r + 0.7152 * g + 0.0722 * b, 4)


def _hex_saturation(value: str | None) -> float | None:
    rgb = _hex_rgb(value)
    if rgb is None:
        return None
    r, g, b = (channel / 255.0 for channel in rgb)
    return round(colorsys.rgb_to_hsv(r, g, b)[1], 4)


def _color_distance(a: str | None, b: str | None) -> float:
    ra = _hex_rgb(a); rb = _hex_rgb(b)
    if ra is None or rb is None:
        return 999.0
    return sum((x - y) ** 2 for x, y in zip(ra, rb)) ** 0.5


def _render_palette(root: Path) -> dict[str, Any]:
    """Extract deck color roles from actual rendered source slides.

    Many real-world templates keep all brand graphics in masters or raster slide
    backgrounds, leaving no editable text runs from which to infer a palette. The
    rendered slide is therefore the most faithful deterministic fallback.
    """
    render_dir = root / 'render/source_renders'
    paths = sorted(render_dir.glob('SRC-S*.png')) if render_dir.exists() else []
    if not paths:
        return {'source': 'unavailable', 'slides': [], 'weighted_colors': []}

    slide_rows: list[dict[str, Any]] = []
    weighted: dict[str, float] = {}
    for index, path in enumerate(paths, start=1):
        try:
            metrics = analyze_image(path)
        except Exception:
            continue
        colors = list(metrics.get('dominant_colors') or [])
        for row in colors:
            color = str(row.get('hex') or '').upper()
            if _hex_rgb(color) is None:
                continue
            weighted[color] = weighted.get(color, 0.0) + float(row.get('ratio') or 0.0)
        background = str((colors[0] if colors else {}).get('hex') or '#FFFFFF').upper()
        luminance = _hex_luminance(background)
        match = re.search(r'SRC-S(\d+)', path.stem)
        source_number = int(match.group(1)) if match else index
        slide_rows.append({
            'source_slide_id': f'SRC-S{source_number:03d}',
            'render_path': str(path.relative_to(root)),
            'background_color': background.replace('#', ''),
            'background_luminance': luminance,
            'background_is_dark': bool(luminance is not None and luminance < 0.46),
            'brightness': metrics.get('brightness'),
            'saturation': metrics.get('saturation'),
            'contrast': metrics.get('contrast'),
            'edge_density': metrics.get('edge_density'),
            'warmth': metrics.get('warmth'),
            'dominant_colors': colors,
        })

    ranked = sorted(weighted.items(), key=lambda pair: pair[1], reverse=True)
    accent_candidates: list[tuple[float, str, float, float]] = []
    for color, weight in ranked:
        lum = _hex_luminance(color)
        sat = _hex_saturation(color)
        if lum is None or sat is None:
            continue
        # Exclude near-neutral whites/blacks. Small high-saturation logo colors still
        # compete because the saturation term is deliberately strong.
        if sat < 0.20 or lum > 0.93 or lum < 0.035:
            continue
        score = weight * (0.42 + sat * 1.45)
        accent_candidates.append((score, color, lum, sat))
    accent_candidates.sort(reverse=True)
    primary = accent_candidates[0][1] if accent_candidates else None
    # Monochrome templates (for example a gray university master) may have no
    # saturated accent at all. Falling back to the product default orange would
    # invent a foreign brand color, so choose the most prevalent meaningful
    # mid/dark neutral from the actual render instead.
    if primary is None:
        neutral_candidates: list[tuple[float, str, float, float]] = []
        for color, weight in ranked:
            lum = _hex_luminance(color)
            sat = _hex_saturation(color)
            if lum is None or sat is None or lum < 0.045 or lum > 0.78:
                continue
            score = weight * (1.15 - abs(0.34 - lum))
            neutral_candidates.append((score, color, lum, sat))
        neutral_candidates.sort(reverse=True)
        primary = neutral_candidates[0][1] if neutral_candidates else None
    secondary = next((row[1] for row in accent_candidates if row[1] != primary and _color_distance(primary, row[1]) >= 72), None)

    light_colors = [(weight, color) for color, weight in ranked if (_hex_luminance(color) or 0) >= 0.80]
    dark_colors = [(weight, color) for color, weight in ranked if (_hex_luminance(color) or 1) <= 0.28]
    background_light = max(light_colors, default=(0.0, '#FFFFFF'))[1]
    background_dark = max(dark_colors, default=(0.0, primary or '#111111'))[1]

    render_target_metrics = {
        key: _median_metric(slide_rows, key)
        for key in ('brightness', 'saturation', 'contrast', 'edge_density', 'warmth')
    }
    render_target_metrics = {key: value for key, value in render_target_metrics.items() if value is not None}

    return {
        'source': 'actual_source_render',
        'slides': slide_rows,
        'target_metrics': render_target_metrics,
        'weighted_colors': [
            {'hex': color, 'weight': round(weight, 4), 'luminance': _hex_luminance(color), 'saturation': _hex_saturation(color)}
            for color, weight in ranked[:16]
        ],
        'primary_accent': (primary or '#FF9A42').replace('#', ''),
        'secondary_accent': (secondary or primary or '#FF9A42').replace('#', ''),
        'background_light': background_light.replace('#', ''),
        'background_dark': background_dark.replace('#', ''),
        'text_on_light': '171717',
        'text_on_dark': 'FFFFFF',
    }


def _round(v, n=3):
    try:
        return round(float(v), n)
    except Exception:
        return None


def _median_metric(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(r[key]) for r in rows if r and r.get(key) is not None]
    return round(median(values), 4) if values else None


def _aspect_from_bbox(bbox: dict[str, Any] | None) -> float | None:
    if not bbox:
        return None
    try:
        w, h = float(bbox.get('w') or 0), float(bbox.get('h') or 0)
        return round(w / h, 5) if h > 0 else None
    except Exception:
        return None


def _blend_metrics(primary: dict[str, Any] | None, deck: dict[str, Any] | None, primary_weight: float = .68) -> dict[str, float]:
    primary = primary or {}
    deck = deck or {}
    out: dict[str, float] = {}
    for key in ('brightness', 'saturation', 'contrast', 'edge_density', 'warmth'):
        p = primary.get(key)
        d = deck.get(key)
        if p is not None and d is not None:
            out[key] = round(float(p) * primary_weight + float(d) * (1.0 - primary_weight), 4)
        elif p is not None:
            out[key] = round(float(p), 4)
        elif d is not None:
            out[key] = round(float(d), 4)
    return out


def build_design_system(project: str | Path) -> dict[str, Any]:
    root = Path(project)
    slides_doc = read_json(root / 'analysis/source_slides.json', {})
    assets_doc = read_json(root / 'analysis/source_assets.json', {})
    template = read_json(root / 'analysis/template_profile.json', {})
    slides = slides_doc.get('slides', [])
    sw = slides_doc.get('presentation', {}).get('width_in', 13.333)
    sh = slides_doc.get('presentation', {}).get('height_in', 7.5)

    title_x = []
    title_y = []
    text_boxes = []
    align_axes = Counter()
    component_rows = []
    for slide in slides:
        texts = [o for o in slide.get('objects', []) if o.get('text')]
        if texts:
            substantive = [o for o in texts if len(o.get('text', '').strip()) >= 3]
            if substantive:
                title = sorted(substantive, key=lambda o: (o['bbox']['y'], -o['bbox']['w']))[0]
                title_x.append(title['bbox']['x'])
                title_y.append(title['bbox']['y'])
        for obj in texts:
            bbox = obj['bbox']
            text_boxes.append(bbox)
            align_axes[round(bbox['x'], 1)] += 1
        role = slide.get('roles', {}).get('primary', 'overview')
        component_rows.append({
            'component_id': f"CMP-{slide['id']}",
            'source_slide_id': slide['id'],
            'kind': 'layout_pattern',
            'role': role,
            'layout_family': slide.get('layout_family'),
            'signature': {
                'shape_count': slide.get('stats', {}).get('shape_count', 0),
                'picture_count': slide.get('stats', {}).get('picture_count', 0),
                'text_shape_count': slide.get('stats', {}).get('text_shape_count', 0),
            },
            'reuse_policy': 'reference_style_and_structure',
        })

    assets = assets_doc.get('assets', [])
    chrome = [a for a in assets if a.get('classification') == 'template_chrome']
    frames = [a for a in assets if a.get('classification') == 'container_or_frame']
    visuals = [a for a in assets if a.get('classification') == 'content_visual']
    raster_visuals = [a for a in visuals if a.get('visual_metrics')]
    metrics = [a.get('visual_metrics') or {} for a in raster_visuals]
    target_metrics = {
        key: _median_metric(metrics, key)
        for key in ('brightness', 'saturation', 'contrast', 'edge_density', 'warmth')
    }
    target_metrics = {k: v for k, v in target_metrics.items() if v is not None}
    aspect_ratios = sorted({round(float(a.get('visual_metrics', {}).get('aspect_ratio')), 3) for a in raster_visuals if a.get('visual_metrics', {}).get('aspect_ratio')})
    reference_asset_ids = [a['id'] for a in sorted(raster_visuals, key=lambda x: x.get('area_ratio', 0), reverse=True)[:6]]

    fonts = [x[0] for x in template.get('visual_grammar', {}).get('fonts', [])[:4]]
    sizes = [x[0] for x in template.get('visual_grammar', {}).get('font_sizes_pt', [])[:8]]
    colors = [x[0] for x in template.get('visual_grammar', {}).get('text_colors', [])[:8]]
    render_palette = _render_palette(root)
    if not target_metrics:
        target_metrics = dict(render_palette.get('target_metrics') or {})
    x_axes = [x for x, n in align_axes.most_common(8) if n >= 2]

    fingerprint = {
        'schema_version': '0.2',
        'generated_at': now_iso(),
        'composition': {
            'title_axis_x_in': _round(median(title_x)) if title_x else None,
            'title_axis_y_in': _round(median(title_y)) if title_y else None,
            'common_left_axes_in': x_axes,
            'slide_aspect_ratio': _round(sw / sh) if sh else None,
            'whitespace_character': 'generous' if len(text_boxes) and median([b['w'] * b['h'] for b in text_boxes]) < (sw * sh * .12) else 'balanced',
        },
        'typography': {
            'preferred_fonts': fonts,
            'common_sizes_pt': sizes,
            'hierarchy_source': 'observed_runs',
        },
        'color_roles': {
            'observed_text_colors': colors,
            'accent_policy': 'derive_from_template_not_generated_visual',
            'palette_source': render_palette.get('source'),
            'primary_accent': render_palette.get('primary_accent'),
            'secondary_accent': render_palette.get('secondary_accent'),
            'background_light': render_palette.get('background_light'),
            'background_dark': render_palette.get('background_dark'),
            'text_on_light': render_palette.get('text_on_light'),
            'text_on_dark': render_palette.get('text_on_dark'),
            'source_slide_tones': render_palette.get('slides', []),
            'weighted_render_colors': render_palette.get('weighted_colors', []),
        },
        'components': {
            'template_chrome_count': len(chrome),
            'frame_count': len(frames),
            'content_visual_count': len(visuals),
        },
        'image_treatment': {
            'preserve_existing_frames': True,
            'replacement_rule': 'crop_to_target_slot_then_grade_toward_source_visuals',
            'avoid_unstyled_raster_dropin': True,
            'target_metrics': target_metrics,
            'observed_aspect_ratios': aspect_ratios,
            'reference_asset_ids': reference_asset_ids,
            'minimum_effective_ppi': 120,
            'harmony_tolerance': {
                'brightness': 0.20,
                'saturation': 0.24,
                'contrast': 0.22,
                'edge_density': 0.16,
                'warmth': 0.18,
            },
        },
        'continuity_rules': [
            'inherit at least one macro, one middle, and one micro cue for RECOMPOSE when available',
            'template chrome is deck-wide continuity and must not be used as replacement content',
            'new images must be judged in rendered slide context, not as isolated assets',
            'generated images must be cropped for the actual target slot and graded before slide placement',
        ],
    }

    catalog = {
        'schema_version': '0.2',
        'generated_at': now_iso(),
        'components': component_rows,
        'asset_components': {
            'template_chrome': [
                {'asset_id': a['id'], 'source_slide_id': a['source_slide_id'], 'source_object_id': a['source_object_id'], 'bbox': a['bbox']}
                for a in chrome
            ],
            'frames': [
                {'asset_id': a['id'], 'source_slide_id': a['source_slide_id'], 'source_object_id': a['source_object_id'], 'bbox': a['bbox']}
                for a in frames
            ],
            'content_visuals': [
                {
                    'asset_id': a['id'],
                    'source_slide_id': a['source_slide_id'],
                    'source_object_id': a['source_object_id'],
                    'bbox': a['bbox'],
                    'media_path': a.get('media_path'),
                    'visual_metrics': a.get('visual_metrics'),
                    'source_display': a.get('source_display'),
                }
                for a in visuals
            ],
        },
        'mixing_policy': {'primary_source_max': 1, 'supporting_component_sources_max': 2, 'deck_chrome': 'global'},
    }
    write_json(root / 'analysis/design_fingerprint.json', fingerprint)
    write_json(root / 'analysis/component_catalog.json', catalog)
    return {'design_fingerprint': fingerprint, 'component_catalog': catalog}


def _negative_space_for_target(bbox: dict[str, Any] | None, slide_width: float) -> str:
    if not bbox or not slide_width:
        return 'none'
    x, w = float(bbox.get('x') or 0), float(bbox.get('w') or 0)
    # A large visual that spans most of the slide needs room for text. For a
    # separate right-hand visual slot, no internal negative-space requirement is needed.
    if w / slide_width >= 0.58:
        return 'left' if x + w / 2 >= slide_width / 2 else 'right'
    return 'none'


def build_continuity_plans(project: str | Path) -> dict[str, Any]:
    root = Path(project)
    deck = read_json(root / 'planning/deck_plan.json', {})
    visual = read_json(root / 'planning/visual_plan.json', {})
    matches = read_json(root / 'planning/slide_matching.json', {})
    source = read_json(root / 'analysis/source_slides.json', {})
    assets = read_json(root / 'analysis/source_assets.json', {})
    fingerprint = read_json(root / 'analysis/design_fingerprint.json', {})
    project_meta = read_json(root / 'project.json', {})
    source_continuity = ((project_meta.get('preferences') or {}).get('source_continuity') or 'balanced')
    match_by = {x['slide_id']: x for x in matches.get('slides', [])}
    visual_by = {x['slide_id']: x for x in visual.get('slides', [])}
    src_by = {x['id']: x for x in source.get('slides', [])}
    asset_by_slide = defaultdict(list)
    for asset in assets.get('assets', []):
        asset_by_slide[asset.get('source_slide_id')].append(asset)

    image_treatment = fingerprint.get('image_treatment', {})
    art = {
        'schema_version': '0.3',
        'generated_at': now_iso(),
        'primary_medium': 'editorial_photo_or_native_ppt_diagram',
        'tone': {'brightness': 'match_source', 'saturation': 'restrained', 'contrast': 'soft_to_medium'},
        'composition': {'background_complexity': 'low_to_medium', 'negative_space': 'layout_driven', 'subject_scale': 'medium'},
        'palette': {'source': 'design_fingerprint', 'accent_rule': 'reuse template accent roles'},
        'target_metrics': image_treatment.get('target_metrics', {}),
        'reference_asset_ids': image_treatment.get('reference_asset_ids', []),
        'harmony_tolerance': image_treatment.get('harmony_tolerance', {}),
        'native_visuals': ['table', 'chart', 'flow', 'timeline', 'relationship_diagram', 'infographic'],
        'image_postprocess': ['crop_to_recipe', 'align_focal_point', 'match_brightness', 'match_color_temperature', 'match_saturation', 'match_contrast', 'match_detail_density', 'apply_frame_geometry'],
        'avoid': ['generic_stock_photo', 'busy_background', 'random_style_switch', 'image_with_embedded_text', 'filler_visual'],
        'candidate_selection': {
            'minimum_auto_score': 0.44,
            'weights': {
                'slot_aspect': 0.30,
                'effective_resolution': 0.16,
                'source_harmony': 0.27,
                'filename_semantics': 0.12,
                'requested_negative_space': 0.15,
            },
            'low_confidence_action': 'review_required',
        },
    }

    plans = []
    previous_recipes_doc = read_json(root / 'planning/image_recipes.json', {})
    previous_recipes = {x.get('recipe_id'): x for x in previous_recipes_doc.get('recipes', []) if x.get('recipe_id')}
    recipes = []
    slide_width = float(source.get('presentation', {}).get('width_in') or 13.333)
    for slide in deck.get('slides', []):
        sid = slide['slide_id']
        match = match_by.get(sid, {})
        selected = match.get('selected') or {}
        srcid = selected.get('source_slide_id')
        src = src_by.get(srcid, {})
        mode = selected.get('recommended_mode', 'RECOMPOSE')
        role = slide.get('role', 'overview')
        src_assets = asset_by_slide.get(srcid, [])
        inherited_macro = ['title_axis', 'content_alignment'] if srcid else ['deck_grid']
        inherited_middle = []
        if src.get('layout_family'):
            inherited_middle.append(f"layout_family:{src.get('layout_family')}")
        if any(a.get('classification') == 'container_or_frame' for a in src_assets):
            inherited_middle.append('existing_visual_frame')
        inherited_micro = ['typography_hierarchy', 'template_color_roles']
        if any(a.get('classification') == 'template_chrome' for a in src_assets):
            inherited_micro.append('template_chrome')
        plan = {
            'slide_id': sid,
            'mode': mode,
            'source_lineage': ([{'source_slide_id': srcid, 'role': 'primary'}] if srcid else []),
            'inherited': {'macro': inherited_macro, 'middle': inherited_middle, 'micro': inherited_micro},
            'changed': ['content', 'content_visuals'] + (['content_geometry'] if mode in {'ADAPT', 'RECOMPOSE'} else []),
            'continuity_score_target': ({'strong': 0.84, 'balanced': 0.72, 'content_first': 0.60}.get(source_continuity, 0.72) if mode == 'RECOMPOSE' else {'strong': 0.90, 'balanced': 0.82, 'content_first': 0.72}.get(source_continuity, 0.82)),
            'source_continuity_mode': source_continuity,
            'status': 'DRAFT',
        }
        plans.append(plan)

        intent = (visual_by.get(sid, {}) or {}).get('visual_intent', {})
        visual_type = intent.get('selected_type', 'no_visual')
        if visual_type in {'photo', 'photo_grid', 'illustration', 'screenshot', 'conceptual_image'}:
            content_targets = sorted(
                [a for a in src_assets if a.get('classification') == 'content_visual'],
                key=lambda a: a.get('area_ratio', 0),
                reverse=True,
            )
            target_count = min(4, len(content_targets)) if visual_type == 'photo_grid' else min(1, len(content_targets))
            targets = content_targets[:target_count] if target_count else [None]
            frame_ids = [a['id'] for a in src_assets if a.get('classification') == 'container_or_frame']
            for recipe_index, target in enumerate(targets, start=1):
                target_bbox = target.get('bbox') if target else None
                target_aspect = _aspect_from_bbox(target_bbox)
                recipe_id = f'IMG-{sid}-{recipe_index:02d}'
                source_metrics = target.get('visual_metrics') if target else None
                target_doc = {
                    'source_slide_id': srcid,
                    'source_object_id': target.get('source_object_id') if target else None,
                    'source_asset_id': target.get('id') if target else None,
                    'source_media_path': target.get('media_path') if target else None,
                    'source_visual_metrics': source_metrics,
                    'source_display': target.get('source_display') if target else None,
                    'bbox': target_bbox,
                    'aspect_ratio': target_aspect or 'from_target_slot',
                    'frame_asset_ids': frame_ids,
                }
                slot_target_metrics = _blend_metrics(source_metrics, art.get('target_metrics', {}))
                previous = previous_recipes.get(recipe_id) or {}
                previous_target = previous.get('target') or {}
                same_target = (
                    previous_target.get('source_slide_id') == target_doc.get('source_slide_id')
                    and previous_target.get('source_object_id') == target_doc.get('source_object_id')
                )
                selected_asset_id = previous.get('selected_asset_id') if same_target else None
                previous_status = previous.get('status') if same_target else None
                recipes.append({
                    'recipe_id': recipe_id,
                    'slide_id': sid,
                    'slot_index': recipe_index,
                    'purpose': role,
                    'message': slide.get('primary_message'),
                    'medium': visual_type,
                    'provider': previous.get('provider', 'auto') if same_target else 'auto',
                    'prompt_seed': slide.get('primary_message') or role,
                    'target': target_doc,
                    'composition': {
                        'focal_point': (previous.get('composition') or {}).get('focal_point', 'auto') if same_target else 'auto',
                        'negative_space': _negative_space_for_target(target_bbox, slide_width),
                        'background_complexity': 'low_to_medium',
                    },
                    'treatment': {
                        'preset': 'match_source_slot_and_deck_art_direction',
                        'fit': 'cover',
                        'frame': 'preserve_source_picture_format',
                        'target_metrics': slot_target_metrics,
                        'deck_target_metrics': art.get('target_metrics', {}),
                    },
                    'style_reference': {
                        'primary_source_asset_id': target.get('id') if target else None,
                        'deck_reference_asset_ids': art.get('reference_asset_ids', []),
                        'lineage': 'source_slot_plus_deck_median',
                    },
                    'palette': 'derive_from_deck_art_direction',
                    'quality': previous.get('quality', 'medium') if same_target else 'medium',
                    'status': (previous_status if selected_asset_id else ('NEEDS_ASSET' if target else 'REVIEW_REQUIRED')),
                    'review_reason': None if target else 'No replaceable source content_visual slot was found.',
                    'selected_asset_id': selected_asset_id,
                    'manual_asset_path': previous.get('manual_asset_path') if same_target else None,
                    'composition_origin': previous.get('composition_origin') if same_target else None,
                    'prompt_origin': previous.get('prompt_origin') if same_target else None,
                    'origin': 'deterministic_recipe_seed',
                })

    continuity = {'schema_version': '0.2', 'generated_at': now_iso(), 'slides': plans}
    recipes_doc = {'schema_version': '0.2', 'generated_at': now_iso(), 'recipes': recipes}
    write_json(root / 'planning/continuity_plan.json', continuity)
    write_json(root / 'planning/deck_art_direction.json', art)
    write_json(root / 'planning/image_recipes.json', recipes_doc)
    return {'continuity_plan': continuity, 'deck_art_direction': art, 'image_recipes': recipes_doc}


def validate_continuity(project: str | Path) -> dict[str, Any]:
    root = Path(project)
    plans = read_json(root / 'planning/continuity_plan.json', {})
    results = []
    blocking = 0
    warning = 0
    for plan in plans.get('slides', []):
        inherited = plan.get('inherited', {})
        missing = [k for k in ('macro', 'middle', 'micro') if not inherited.get(k)]
        severity = 'pass'
        if plan.get('mode') == 'RECOMPOSE' and missing:
            severity = 'blocking'
            blocking += 1
        elif missing:
            severity = 'warning'
            warning += 1
        results.append({
            'slide_id': plan['slide_id'],
            'check_id': 'SOURCE_CONTINUITY',
            'result': severity,
            'missing_layers': missing,
            'target_score': plan.get('continuity_score_target'),
        })
    report = {
        'schema_version': '0.2',
        'generated_at': now_iso(),
        'status': 'fail' if blocking else 'pass',
        'summary': {'blocking': blocking, 'warning': warning},
        'checks': results,
    }
    write_json(root / 'qa/continuity_qa.json', report)
    return report
