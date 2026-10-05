from __future__ import annotations

import base64
import io
import hashlib
import json
import os
import re
import math
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from helpers import append_jsonl, now_iso, read_json, write_json
from image_metrics import (
    analyze_image,
    crop_cover,
    grade_toward,
    hamming_distance,
    metric_distance,
    side_complexity,
)
from state import ensure_slide, load_state, save_state
from schema_validation import validate_deck_art_direction, validate_image_manifest, validate_image_recipes


VISUAL_IMAGE_TYPES = {"photo", "photo_grid", "illustration", "screenshot", "conceptual_image"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


def _safe_rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _resolve_project_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not str(path).startswith(str(root.resolve()) + os.sep):
        raise ValueError("asset path must be inside project")
    return path


def _hex_color(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 6:
        try:
            return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except Exception:
            pass
    return fallback




def _mix_rgb(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, float(amount)))
    return tuple(round(x * (1.0 - amount) + y * amount) for x, y in zip(a, b))  # type: ignore[return-value]


def _palette_treatment(
    image: Image.Image, target: dict[str, Any], fingerprint: dict[str, Any]
) -> tuple[Image.Image, dict[str, Any]]:
    """Apply a deck-aware palette treatment before metric grading.

    Metric-only enhancement cannot turn a neutral photograph into a deliberate
    low-key duotone master, nor can bounded saturation reduction make a photo join
    a near-monochrome gray template. This deterministic step is used only when the
    rendered source deck strongly signals one of those art directions.
    """
    out = image.convert("RGB")
    try:
        brightness = float(target.get("brightness"))
    except Exception:
        brightness = .5
    try:
        saturation = float(target.get("saturation"))
    except Exception:
        saturation = .35
    roles = fingerprint.get("color_roles") or {}
    accent = _hex_color(roles.get("primary_accent"), (100, 52, 42))
    dark = _hex_color(roles.get("background_dark"), (28, 28, 28))

    if saturation >= .50 and brightness <= .38:
        # Strongly branded low-key templates benefit from a true duotone rather
        # than simply darkening an unrelated full-color image.
        gray = ImageOps.grayscale(out)
        shadow = _mix_rgb(dark, (0, 0, 0), .28)
        highlight = _mix_rgb(accent, (238, 229, 226), .48)
        out = ImageOps.colorize(gray, black=shadow, white=highlight).convert("RGB")
        return out, {
            "mode": "deck_duotone",
            "shadow": list(shadow),
            "highlight": list(highlight),
        }

    if saturation <= .14:
        # Master-only gray templates often intentionally avoid color. Retain a
        # little source chroma so the image still reads naturally, but make the
        # overall treatment clearly belong to the monochrome deck.
        gray = ImageOps.grayscale(out).convert("RGB")
        color_share = max(.05, min(.28, saturation * 1.6))
        out = Image.blend(gray, out, color_share)
        return out, {"mode": "restrained_monochrome", "source_color_share": round(color_share, 4)}

    return out, {"mode": "metric_grade_only"}


def _generation_size(aspect: float) -> tuple[int, int]:
    if aspect >= 1.22:
        return 1536, 1024
    if aspect <= 0.82:
        return 1024, 1536
    return 1024, 1024


def _target_aspect(recipe: dict[str, Any]) -> float:
    target = recipe.get("target") or {}
    value = target.get("aspect_ratio")
    if isinstance(value, (int, float)) and float(value) > 0:
        return float(value)
    if isinstance(value, str) and ":" in value:
        try:
            a, b = value.split(":", 1)
            return float(a) / float(b)
        except Exception:
            pass
    bbox = target.get("bbox") or {}
    try:
        return float(bbox["w"]) / float(bbox["h"])
    except Exception:
        return 16 / 9


def _focal_point(recipe: dict[str, Any]) -> tuple[float, float]:
    value = (recipe.get("composition") or {}).get("focal_point") or [0.5, 0.5]
    try:
        return max(0.0, min(1.0, float(value[0]))), max(0.0, min(1.0, float(value[1])))
    except Exception:
        return 0.5, 0.5


def _target_metrics(recipe: dict[str, Any], art: dict[str, Any], fingerprint: dict[str, Any]) -> dict[str, Any]:
    return (
        (recipe.get("treatment") or {}).get("target_metrics")
        or art.get("target_metrics")
        or (fingerprint.get("image_treatment") or {}).get("target_metrics")
        or {}
    )


def _metric_style_phrase(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "match the supplied deck references"
    brightness = float(metrics.get("brightness") or .5)
    saturation = float(metrics.get("saturation") or .35)
    contrast = float(metrics.get("contrast") or .45)
    warmth = float(metrics.get("warmth") or 0.0)
    edge = float(metrics.get("edge_density") or .12)
    parts = [
        "high-key and bright" if brightness >= .67 else "mid-key" if brightness >= .43 else "low-key",
        "restrained color" if saturation <= .34 else "moderate color" if saturation <= .58 else "vivid color",
        "soft contrast" if contrast <= .38 else "moderate contrast" if contrast <= .68 else "crisp contrast",
        "warm-neutral color temperature" if warmth >= .05 else "cool-neutral color temperature" if warmth <= -.05 else "neutral color temperature",
        "quiet detail" if edge <= .10 else "moderate visual detail" if edge <= .22 else "high visual detail",
    ]
    return ", ".join(parts)


def _prompt_for(recipe: dict[str, Any], art: dict[str, Any]) -> str:
    tone = art.get("tone") or {}
    composition = recipe.get("composition") or {}
    avoid = art.get("avoid") or []
    medium = recipe.get("medium") or "editorial photo"
    message = recipe.get("prompt_seed") or recipe.get("message") or recipe.get("purpose") or "presentation visual"
    negative = composition.get("negative_space") or "none"
    target_metrics = (recipe.get("treatment") or {}).get("target_metrics") or art.get("target_metrics") or {}
    return "\n".join([
        f"Create a {medium} for a professional presentation slide.",
        f"Core idea: {message}",
        f"Match this source-deck photographic character: {_metric_style_phrase(target_metrics)}.",
        f"Visual tone: brightness {tone.get('brightness','match source deck')}; saturation {tone.get('saturation','restrained')}; contrast {tone.get('contrast','soft to medium')}.",
        f"Composition: low-to-medium background complexity, medium subject scale, negative space on {negative} when applicable.",
        "Keep the primary subject clearly readable after a presentation-slot crop.",
        "No embedded words, labels, logos, watermarks, UI text, charts, or typography.",
        "The image must feel editorial and specific rather than generic stock photography.",
        f"Avoid: {', '.join(str(x) for x in avoid)}.",
    ])


def _mock_generate(prompt: str, size: tuple[int, int], palette: list[str], seed_text: str) -> Image.Image:
    """Deterministic no-text visual used for tests and offline demos."""
    width, height = size
    seed = int(hashlib.sha256((prompt + seed_text).encode("utf-8")).hexdigest()[:16], 16)
    base = _hex_color(palette[0] if palette else None, (239, 235, 226))
    accent = _hex_color(palette[1] if len(palette) > 1 else None, (230, 101, 49))
    dark = _hex_color(palette[2] if len(palette) > 2 else None, (35, 39, 37))
    image = Image.new("RGB", size, base)
    px = image.load()
    # Soft deck-compatible gradient.
    for y in range(height):
        mix = y / max(1, height - 1)
        for x in range(width):
            side = x / max(1, width - 1)
            warm = 0.08 + 0.12 * side + 0.05 * mix
            px[x, y] = tuple(int(c * (1 - warm) + 255 * warm) for c in base)
    draw = ImageDraw.Draw(image, "RGBA")
    # Deliberately avoid text. Shapes emulate a restrained editorial composition.
    for i in range(5):
        token = (seed >> (i * 9)) & 0x1FF
        cx = int(width * (0.16 + 0.68 * ((token % 97) / 96)))
        cy = int(height * (0.18 + 0.64 * (((token // 7) % 89) / 88)))
        rw = int(width * (0.12 + 0.08 * ((token % 13) / 12)))
        rh = int(height * (0.18 + 0.12 * (((token // 11) % 17) / 16)))
        color = accent if i % 3 == 0 else dark
        alpha = 42 if i % 2 else 28
        draw.rounded_rectangle((cx - rw, cy - rh, cx + rw, cy + rh), radius=min(rw, rh) // 3, fill=(*color, alpha))
    # One clear focal shape, leaving quieter edge space.
    focal_x = int(width * (0.38 + 0.25 * ((seed % 100) / 99)))
    focal_y = int(height * 0.52)
    radius = int(min(width, height) * 0.18)
    draw.ellipse((focal_x - radius, focal_y - radius, focal_x + radius, focal_y + radius), fill=(*accent, 105))
    return image


def _openai_generate(prompt: str, size: tuple[int, int], quality: str, model: str = "gpt-image-2") -> tuple[Image.Image, dict[str, Any]]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for provider=openai")
    endpoint = os.environ.get("OPENAI_IMAGE_ENDPOINT", "https://api.openai.com/v1/images/generations")
    payload = {
        "model": model,
        "prompt": prompt,
        "size": f"{size[0]}x{size[1]}",
        "quality": quality,
        "n": 1,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    row = (result.get("data") or [{}])[0]
    if row.get("b64_json"):
        raw = base64.b64decode(row["b64_json"])
    elif row.get("url"):
        with urllib.request.urlopen(row["url"], timeout=180) as response:
            raw = response.read()
    else:
        raise RuntimeError("image API returned no image payload")
    image = Image.open(io.BytesIO(raw))
    return ImageOps.exif_transpose(image).convert("RGB"), {
        "model": model,
        "request_id": result.get("id"),
        "usage": result.get("usage"),
    }


def _palette_from_fingerprint(fingerprint: dict[str, Any]) -> list[str]:
    values = (fingerprint.get("color_roles") or {}).get("observed_text_colors") or []
    out = []
    for value in values:
        if isinstance(value, str):
            out.append("#" + value.lstrip("#"))
        elif isinstance(value, (list, tuple)) and value:
            out.append("#" + str(value[0]).lstrip("#"))
    return out




def _text_tokens(value: str | None) -> set[str]:
    text = str(value or "").lower()
    return {
        token
        for token in re.findall(r"[a-z0-9]+|[一-龯ぁ-んァ-ヶー]{2,}", text)
        if len(token) >= 2
    }


def _scan_local_assets(root: Path) -> list[dict[str, Any]]:
    asset_dir = root / "inputs/assets"
    rows: list[dict[str, Any]] = []
    if not asset_dir.exists():
        return rows
    for path in sorted(asset_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            metrics = analyze_image(path)
        except Exception:
            continue
        rows.append({
            "path": path,
            "relative_path": _safe_rel(root, path),
            "filename": path.name,
            "tokens": sorted(_text_tokens(path.stem)),
            "metrics": metrics,
        })
    return rows


def _candidate_score(
    recipe: dict[str, Any],
    candidate: dict[str, Any],
    art: dict[str, Any],
    fingerprint: dict[str, Any],
) -> dict[str, Any]:
    metrics = candidate.get("metrics") or {}
    target_aspect = _target_aspect(recipe)
    actual_aspect = float(metrics.get("aspect_ratio") or target_aspect)
    aspect_score = math.exp(-abs(math.log(max(.001, actual_aspect) / max(.001, target_aspect))) * 1.35)

    bbox = (recipe.get("target") or {}).get("bbox") or {}
    try:
        ppi = min(float(metrics["width_px"]) / float(bbox["w"]), float(metrics["height_px"]) / float(bbox["h"]))
    except Exception:
        ppi = None
    minimum_ppi = float((fingerprint.get("image_treatment") or {}).get("minimum_effective_ppi") or 120)
    resolution_score = 1.0 if ppi is None else min(1.0, ppi / max(1.0, minimum_ppi))

    target_metrics = _target_metrics(recipe, art, fingerprint)
    tolerances = art.get("harmony_tolerance") or (fingerprint.get("image_treatment") or {}).get("harmony_tolerance") or {}
    harmony_score, harmony_detail = _image_harmony_score(metrics, target_metrics, tolerances)

    query_tokens = _text_tokens(" ".join([
        str(recipe.get("message") or ""),
        str(recipe.get("prompt_seed") or ""),
        str(recipe.get("purpose") or ""),
    ]))
    candidate_tokens = set(candidate.get("tokens") or [])
    semantic_score = len(query_tokens & candidate_tokens) / max(1, len(query_tokens)) if query_tokens else .5

    negative_space = (recipe.get("composition") or {}).get("negative_space")
    negative_score = .75
    if negative_space in {"left", "right", "top", "bottom"}:
        try:
            with Image.open(candidate["path"]) as im:
                requested = side_complexity(im, negative_space)
                opposite_name = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}[negative_space]
                opposite = side_complexity(im, opposite_name)
            if requested is not None and opposite is not None:
                negative_score = max(0.0, min(1.0, .5 + (opposite - requested) * 2.2))
        except Exception:
            negative_score = .5

    configured = (art.get("candidate_selection") or {}).get("weights") or {}
    weights = {
        "aspect": float(configured.get("slot_aspect") or .30),
        "resolution": float(configured.get("effective_resolution") or .16),
        "harmony": float(configured.get("source_harmony") or .27),
        "semantic": float(configured.get("filename_semantics") or .12),
        "negative_space": float(configured.get("requested_negative_space") or .15),
    }
    weight_sum = max(.001, sum(weights.values()))
    total = (
        aspect_score * weights["aspect"]
        + resolution_score * weights["resolution"]
        + harmony_score * weights["harmony"]
        + semantic_score * weights["semantic"]
        + negative_score * weights["negative_space"]
    ) / weight_sum
    return {
        "total": round(total, 4),
        "aspect": round(aspect_score, 4),
        "resolution": round(resolution_score, 4),
        "harmony": round(harmony_score, 4),
        "semantic": round(semantic_score, 4),
        "negative_space": round(negative_score, 4),
        "effective_ppi": round(ppi, 1) if ppi is not None else None,
        "harmony_detail": harmony_detail,
    }


def _choose_local_candidate(
    recipe: dict[str, Any],
    candidates: list[dict[str, Any]],
    art: dict[str, Any],
    fingerprint: dict[str, Any],
    used_paths: set[str] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    scored: list[dict[str, Any]] = []
    used_paths = used_paths or set()
    for candidate in candidates:
        score = _candidate_score(recipe, candidate, art, fingerprint)
        if candidate["relative_path"] in used_paths and len(candidates) > 1:
            score["reuse_penalty"] = 0.22
            score["total"] = round(max(0.0, score["total"] - 0.22), 4)
        else:
            score["reuse_penalty"] = 0.0
        scored.append({
            "path": candidate["relative_path"],
            "filename": candidate["filename"],
            "metrics": candidate.get("metrics"),
            "score": score,
            "_candidate": candidate,
        })
    scored.sort(key=lambda row: row["score"]["total"], reverse=True)
    best = scored[0]["_candidate"] if scored else None
    public = [{k: v for k, v in row.items() if k != "_candidate"} for row in scored[:8]]
    return best, public


def _next_version(manifest: dict[str, Any], recipe_id: str) -> int:
    versions = [int(x.get("version") or 0) for x in manifest.get("assets", []) if x.get("recipe_id") == recipe_id]
    return max(versions or [0]) + 1


def _load_manifest(root: Path) -> dict[str, Any]:
    return read_json(root / "render/generated_assets/manifest.json", {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "assets": [],
        "selected_by_recipe": {},
    })


def _save_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest["generated_at"] = now_iso()
    validate_image_manifest(manifest)
    write_json(root / "render/generated_assets/manifest.json", manifest)



def _edge_focal_point(image: Image.Image) -> tuple[float, float]:
    sample = image.convert("L")
    sample.thumbnail((320, 320), Image.Resampling.LANCZOS)
    edges = sample.filter(ImageFilter.FIND_EDGES)
    w, h = edges.size
    pixels = edges.load()
    total = sx = sy = 0.0
    for y in range(h):
        for x in range(w):
            value = max(0.0, float(pixels[x, y]) - 20.0) ** 1.25
            total += value
            sx += value * ((x + 0.5) / max(1, w))
            sy += value * ((y + 0.5) / max(1, h))
    if total <= 1e-6:
        return 0.5, 0.5
    return max(0.22, min(0.78, sx / total)), max(0.22, min(0.78, sy / total))


def _crop_for_recipe(raw: Image.Image, recipe: dict[str, Any], aspect: float) -> tuple[Image.Image, dict[str, Any]]:
    composition = recipe.get("composition") or {}
    requested = str(composition.get("negative_space") or "none").lower()
    raw_focal = composition.get("focal_point")
    if raw_focal == "auto" or raw_focal is None:
        base = _edge_focal_point(raw)
    else:
        base = _focal_point(recipe)
    opposite = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
    if requested not in opposite:
        cropped, info = crop_cover(raw, aspect, base)
        info["negative_space"] = {"requested": requested, "strategy": "focal_only"}
        return cropped, info

    # Try a restrained range of focal offsets. This is intentionally not object
    # recognition; it preserves the declared focal region while choosing the crop
    # whose requested text side is visually quieter.
    offsets = (-0.18, -0.10, 0.0, 0.10, 0.18)
    candidates = []
    for offset in offsets:
        fx, fy = base
        if requested in {"left", "right"}:
            fx = max(0.12, min(0.88, fx + offset))
        else:
            fy = max(0.12, min(0.88, fy + offset))
        cropped, info = crop_cover(raw, aspect, (fx, fy))
        quiet = side_complexity(cropped, requested)
        other = side_complexity(cropped, opposite[requested])
        quiet = float(quiet or 0.0)
        other = float(other or 0.0)
        focal_penalty = abs(fx - base[0]) + abs(fy - base[1])
        score = quiet - 0.30 * other + 0.14 * focal_penalty
        candidates.append((score, cropped, info, quiet, other))
    score, cropped, info, quiet, other = min(candidates, key=lambda row: row[0])
    info["negative_space"] = {
        "requested": requested,
        "strategy": "candidate_crop_search",
        "requested_side_edge_density": round(quiet, 4),
        "opposite_side_edge_density": round(other, 4),
        "selection_score": round(score, 4),
        "base_focal_point": [round(base[0], 4), round(base[1], 4)],
    }
    return cropped, info

def _process_image(root: Path, recipe: dict[str, Any], raw: Image.Image, out_path: Path, art: dict[str, Any], fingerprint: dict[str, Any]) -> dict[str, Any]:
    aspect = _target_aspect(recipe)
    cropped, crop_info = _crop_for_recipe(raw, recipe, aspect)
    target_bbox = (recipe.get("target") or {}).get("bbox") or {}
    try:
        # Render visual assets at a presentation-aware resolution instead of a
        # fixed 2048px ceiling. A 26.67-inch full-bleed source deck needs at
        # least 3200px to meet the default 120 effective PPI requirement. Keep
        # the deterministic target near 180 PPI and cap the longest edge at
        # 3328px so a 26.67-inch canvas stays above 120 PPI while App Server memory use remains bounded.
        target_ppi = 150.0
        target_w = max(640, round(float(target_bbox.get("w") or 6) * target_ppi))
        target_h = max(360, round(float(target_bbox.get("h") or (target_w / target_ppi / aspect)) * target_ppi))
        # The recipe aspect ratio is authoritative; normalize any rounded bbox
        # mismatch before applying the bounded maximum dimension.
        target_h = max(360, round(target_w / aspect))
        longest = max(target_w, target_h)
        if longest > 3328:
            scale = 3328.0 / longest
            target_w = max(640, round(target_w * scale))
            target_h = max(360, round(target_h * scale))
    except Exception:
        target_w, target_h = _generation_size(aspect)
    processed = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
    target = _target_metrics(recipe, art, fingerprint)
    palette_adjusted, palette_info = _palette_treatment(processed, target, fingerprint)
    graded, grade_info = grade_toward(
        palette_adjusted, target,
        max_brightness_factor=(0.56, 1.52) if palette_info.get("mode") == "deck_duotone" else (0.68, 1.42),
        max_saturation_factor=(0.55, 1.72),
        max_contrast_factor=(0.62, 1.45),
    )
    grade_info.setdefault("factors", {})["palette_treatment"] = palette_info
    out_path.parent.mkdir(parents=True, exist_ok=True)
    graded.save(out_path, format="PNG", compress_level=4)
    return {
        "crop": crop_info,
        "target_size": [target_w, target_h],
        "target_metrics": target,
        "grading": grade_info,
        "metrics": analyze_image(out_path),
    }


def _update_slide_plan(root: Path, recipe: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any] | None:
    sid = recipe.get("slide_id")
    target = recipe.get("target") or {}
    target_id = target.get("source_object_id")
    layout_slot_id = target.get("layout_slot_id")
    if not sid:
        return None
    path = root / f"planning/slide_plans/{sid}.json"
    plan = read_json(path, None)
    if not plan:
        return None
    # Layout Engine-owned image slots are rendered from the manifest inside
    # apply_layout(). They must not also create a source-object mutation, even when
    # a source picture is used as a style/frame reference. Otherwise the image is
    # applied twice and a non-picture style object could be mutated accidentally.
    if layout_slot_id:
        mutations = plan.setdefault("source_object_mutations", [])
        filtered = [m for m in mutations if m.get("image_recipe_id") != recipe.get("recipe_id")]
        if filtered != mutations:
            plan["source_object_mutations"] = filtered
            write_json(path, plan)
        return plan
    if not target_id:
        return None
    mutation = {
        "source_object_id": target_id,
        "action": "replace_image",
        "asset_path": asset["processed_path"],
        "asset_id": asset["asset_id"],
        "image_recipe_id": recipe["recipe_id"],
        "fit_mode": "preserve_format",
        "focal_point": ((asset.get("process") or {}).get("crop") or {}).get("focal_point") or [0.5, 0.5],
        "frame_asset_ids": (recipe.get("target") or {}).get("frame_asset_ids") or [],
        "reason": "Generated or selected image processed to the source visual slot and deck art direction.",
    }
    mutations = plan.setdefault("source_object_mutations", [])
    replaced = False
    for idx, existing in enumerate(mutations):
        if existing.get("source_object_id") == target_id and existing.get("action") in {"replace_image", "keep", "remove"}:
            mutations[idx] = mutation
            replaced = True
            break
    if not replaced:
        mutations.append(mutation)
    plan["status"] = "APPROVED"
    write_json(path, plan)
    return plan


def generate_images(
    project: str | Path,
    *,
    provider: str = "auto",
    slide_ids: list[str] | None = None,
    recipe_ids: list[str] | None = None,
    manual_paths: dict[str, str] | None = None,
    quality: str | None = None,
    model: str = "gpt-image-2",
    allow_mock: bool = False,
) -> dict[str, Any]:
    root = Path(project).resolve()
    recipes_doc = read_json(root / "planning/image_recipes.json", {})
    art = read_json(root / "planning/deck_art_direction.json", {})
    validate_image_recipes(recipes_doc)
    validate_deck_art_direction(art)
    fingerprint = read_json(root / "analysis/design_fingerprint.json", {})
    manifest = _load_manifest(root)
    selected_slides = set(slide_ids or [])
    selected_recipes = set(recipe_ids or [])
    manual_paths = manual_paths or {}
    palette = _palette_from_fingerprint(fingerprint)
    local_candidates = _scan_local_assets(root)
    used_local_paths: set[str] = set()
    results = []

    for recipe in recipes_doc.get("recipes", []):
        rid = recipe.get("recipe_id")
        sid = recipe.get("slide_id")
        if selected_slides and sid not in selected_slides:
            continue
        if selected_recipes and rid not in selected_recipes:
            continue
        target = recipe.get("target") or {}
        has_target = bool((target.get("source_object_id") or target.get("layout_slot_id")) and target.get("bbox"))
        if not has_target:
            recipe["status"] = "REVIEW_REQUIRED"
            results.append({"recipe_id": rid, "slide_id": sid, "status": "REVIEW_REQUIRED", "reason": "No source-object or deterministic layout-slot target"})
            continue

        aspect = _target_aspect(recipe)
        version = _next_version(manifest, rid)
        asset_id = f"GAST-{rid}-V{version:03d}"
        out_dir = root / f"render/generated_assets/{rid}/v{version:03d}"
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = out_dir / "raw.png"
        processed_path = out_dir / "processed.png"
        prompt = _prompt_for(recipe, art)
        size = _generation_size(aspect)
        provider_meta: dict[str, Any] = {}

        recipe_provider = str(recipe.get("provider") or "auto").lower()
        effective_provider = recipe_provider if provider == "auto" and recipe_provider != "auto" else provider
        source_value = manual_paths.get(rid) or recipe.get("manual_asset_path")
        candidate_ranking: list[dict[str, Any]] = []
        local_candidate = None

        if effective_provider == "auto":
            if source_value:
                effective_provider = "manual"
            elif local_candidates:
                local_candidate, candidate_ranking = _choose_local_candidate(recipe, local_candidates, art, fingerprint, used_local_paths)
                minimum = float((art.get("candidate_selection") or {}).get("minimum_auto_score") or .44)
                best_score = float(((candidate_ranking or [{}])[0].get("score") or {}).get("total") or 0.0)
                if local_candidate is not None and best_score >= minimum:
                    effective_provider = "local"
                else:
                    local_candidate = None
                    if os.environ.get("OPENAI_API_KEY"):
                        effective_provider = "openai"
                    elif allow_mock or os.environ.get("IMAGE_OFFLINE_MOCK", "").lower() in {"1", "true", "yes"}:
                        effective_provider = "mock"
                    else:
                        recipe["status"] = "REVIEW_REQUIRED"
                        recipe["review_reason"] = f"Uploaded images did not reach the auto-selection threshold ({best_score:.3f} < {minimum:.3f})."
                        recipe["candidate_ranking"] = candidate_ranking
                        results.append({"recipe_id": rid, "slide_id": sid, "status": "REVIEW_REQUIRED", "reason": recipe["review_reason"], "candidate_ranking": candidate_ranking})
                        continue
            elif os.environ.get("OPENAI_API_KEY"):
                effective_provider = "openai"
            elif allow_mock or os.environ.get("IMAGE_OFFLINE_MOCK", "").lower() in {"1", "true", "yes"}:
                effective_provider = "mock"
            else:
                recipe["status"] = "REVIEW_REQUIRED"
                recipe["review_reason"] = "No uploaded image candidate and OPENAI_API_KEY is not configured."
                results.append({"recipe_id": rid, "slide_id": sid, "status": "REVIEW_REQUIRED", "reason": recipe["review_reason"]})
                continue

        if effective_provider == "manual":
            if not source_value:
                raise ValueError(f"manual provider requires a path for {rid}")
            source_path = _resolve_project_path(root, source_value)
            with Image.open(source_path) as im:
                raw = ImageOps.exif_transpose(im).convert("RGB")
            source_rel = _safe_rel(root, source_path)
            recipe["manual_asset_path"] = source_rel
            provider_meta = {"source_path": source_rel, "selection_rule": "user_selected_manual_asset"}
        elif effective_provider == "local":
            if local_candidate is None:
                local_candidate, candidate_ranking = _choose_local_candidate(recipe, local_candidates, art, fingerprint, used_local_paths)
            if local_candidate is None:
                recipe["status"] = "REVIEW_REQUIRED"
                recipe["review_reason"] = "No compatible local image candidate was found."
                results.append({"recipe_id": rid, "slide_id": sid, "status": "REVIEW_REQUIRED", "reason": recipe["review_reason"]})
                continue
            source_path = Path(local_candidate["path"])
            with Image.open(source_path) as im:
                raw = ImageOps.exif_transpose(im).convert("RGB")
            used_local_paths.add(local_candidate["relative_path"])
            provider_meta = {
                "source_path": local_candidate["relative_path"],
                "candidate_ranking": candidate_ranking,
                "selected_score": ((candidate_ranking or [{}])[0].get("score") or {}).get("total"),
                "selection_rule": "aspect_resolution_harmony_semantics_negative_space",
            }
        elif effective_provider == "openai":
            raw, provider_meta = _openai_generate(prompt, size, quality or recipe.get("quality") or "medium", model=model)
        elif effective_provider == "mock":
            raw = _mock_generate(prompt, size, palette, f"{rid}:{version}")
            provider_meta = {"offline": True, "warning": "Deterministic placeholder for tests; not a production image."}
        else:
            raise ValueError(f"unsupported image provider: {effective_provider}")

        raw.save(raw_path, format="PNG", compress_level=4)
        raw_metrics = analyze_image(raw_path)
        process_info = _process_image(root, recipe, raw, processed_path, art, fingerprint)
        asset = {
            "asset_id": asset_id,
            "recipe_id": rid,
            "slide_id": sid,
            "version": version,
            "provider": effective_provider,
            "provider_meta": provider_meta,
            "model": model if effective_provider == "openai" else None,
            "quality": quality or recipe.get("quality") or "medium",
            "prompt": prompt,
            "raw_path": _safe_rel(root, raw_path),
            "processed_path": _safe_rel(root, processed_path),
            "target": recipe.get("target"),
            "composition": recipe.get("composition"),
            "lineage": {
                "source_slide_id": (recipe.get("target") or {}).get("source_slide_id"),
                "source_object_id": (recipe.get("target") or {}).get("source_object_id"),
                "layout_slot_id": (recipe.get("target") or {}).get("layout_slot_id"),
                "source_asset_id": (recipe.get("target") or {}).get("source_asset_id"),
                "source_media_path": (recipe.get("target") or {}).get("source_media_path"),
                "style_reference": recipe.get("style_reference"),
                "treatment_preset": (recipe.get("treatment") or {}).get("preset"),
            },
            "raw_metrics": raw_metrics,
            "process": process_info,
            "metrics": process_info.get("metrics"),
            "status": "READY",
            "created_at": now_iso(),
        }
        manifest.setdefault("assets", []).append(asset)
        manifest.setdefault("selected_by_recipe", {})[rid] = asset_id
        recipe["selected_asset_id"] = asset_id
        recipe["status"] = "READY"
        recipe["review_reason"] = None
        plan = _update_slide_plan(root, recipe, asset)

        state = load_state(root)
        if sid:
            slide_state = ensure_slide(state, sid)
            slide_state["image"] = "APPROVED"
            if plan:
                slide_state["slide_plan"] = "APPROVED"
            for phase in ("render", "qa"):
                slide_state[phase] = "STALE_LOCKED" if slide_state.get(phase) == "LOCKED" else "STALE"
            state["deck_harmony"] = "STALE"
            save_state(root, state)
        append_jsonl(root / "decisions/decision_trace.jsonl", {
            "decision_id": f"IMAGE-{asset_id}",
            "timestamp": now_iso(),
            "phase": "image",
            "target": {"type": "slide", "id": sid},
            "decision_type": "generate_or_select_image",
            "selected": {"asset_id": asset_id, "provider": effective_provider, "processed_path": asset["processed_path"]},
            "reason_text": "Image was cropped to the target source slot and graded toward the deck art direction before placement.",
            "origin": "ai" if effective_provider == "openai" else "user" if effective_provider == "manual" else "system",
            "alternatives": provider_meta.get("candidate_ranking", [])[:5],
            "rerun_scope": [f"{sid}:render", f"{sid}:qa", "deck_harmony"],
        })
        results.append({"recipe_id": rid, "slide_id": sid, "asset_id": asset_id, "status": "READY", "processed_path": asset["processed_path"]})

    write_json(root / "planning/image_recipes.json", recipes_doc)
    _save_manifest(root, manifest)
    qa = validate_image_harmony(root)
    coherence = validate_deck_image_coherence(root)
    return {"results": results, "manifest": manifest, "qa": qa, "coherence": coherence}


def update_image_recipe(
    project: str | Path,
    recipe_id: str,
    *,
    prompt_seed: str | None = None,
    negative_space: str | None = None,
    focal_point: list[float] | str | None = None,
) -> dict[str, Any]:
    """Apply a user override and invalidate the minimum affected descendants.

    Negative-space changes can alter a photo-aware layout's text/image side, so those
    pages also invalidate layout. Prompt and focal-point changes remain image-local.
    """
    root = Path(project).resolve()
    recipes_doc = read_json(root / "planning/image_recipes.json", {})
    recipe = next((row for row in recipes_doc.get("recipes", []) if row.get("recipe_id") == recipe_id), None)
    if not recipe:
        raise ValueError("recipe not found")
    before = {
        "prompt_seed": recipe.get("prompt_seed"),
        "negative_space": (recipe.get("composition") or {}).get("negative_space"),
        "focal_point": (recipe.get("composition") or {}).get("focal_point"),
        "selected_asset_id": recipe.get("selected_asset_id"),
    }
    changed: list[str] = []
    if prompt_seed is not None:
        value = str(prompt_seed).strip()
        if not value:
            raise ValueError("prompt_seed cannot be empty")
        if value != recipe.get("prompt_seed"):
            recipe["prompt_seed"] = value
            recipe["prompt_origin"] = "user"
            changed.append("prompt_seed")
    if negative_space is not None:
        value = str(negative_space).lower()
        if value not in {"none", "left", "right", "top", "bottom"}:
            raise ValueError("invalid negative_space")
        composition = recipe.setdefault("composition", {})
        if composition.get("negative_space") != value:
            composition["negative_space"] = value
            recipe["composition_origin"] = "user"
            changed.append("negative_space")
    if focal_point is not None:
        if focal_point == "auto":
            value_fp: list[float] | str = "auto"
        else:
            if not isinstance(focal_point, (list, tuple)) or len(focal_point) != 2:
                raise ValueError("focal_point must be 'auto' or [x,y]")
            value_fp = [max(0.0, min(1.0, float(focal_point[0]))), max(0.0, min(1.0, float(focal_point[1])))]
        composition = recipe.setdefault("composition", {})
        if composition.get("focal_point") != value_fp:
            composition["focal_point"] = value_fp
            recipe["composition_origin"] = "user"
            changed.append("focal_point")
    if not changed:
        return {"recipe": recipe, "changed": [], "status": recipe.get("status")}

    previous_asset = recipe.get("selected_asset_id")
    recipe["selected_asset_id"] = None
    target = recipe.get("target") or {}
    recipe["status"] = "NEEDS_ASSET" if ((target.get("source_object_id") or target.get("layout_slot_id")) and target.get("bbox")) else "REVIEW_REQUIRED"
    recipe["review_reason"] = "Image recipe changed; regenerate or select a candidate."
    write_json(root / "planning/image_recipes.json", recipes_doc)

    manifest = _load_manifest(root)
    manifest.setdefault("selected_by_recipe", {}).pop(recipe_id, None)
    _save_manifest(root, manifest)

    sid = recipe.get("slide_id")
    plan_path = root / f"planning/slide_plans/{sid}.json"
    plan = read_json(plan_path, None)
    if plan:
        plan["source_object_mutations"] = [
            mutation for mutation in plan.get("source_object_mutations", [])
            if mutation.get("image_recipe_id") != recipe_id
        ]
        write_json(plan_path, plan)

    layout_family = str(((plan or {}).get("layout_request") or {}).get("family") or "")
    invalidates_layout = bool("negative_space" in changed and layout_family in {"photo_text", "full_bleed"})
    state = load_state(root)
    if sid:
        slide = ensure_slide(state, sid)
        slide["image"] = "DRAFT"
        phases = (["layout"] if invalidates_layout else []) + ["render", "qa"]
        for phase in phases:
            slide[phase] = "STALE_LOCKED" if slide.get(phase) == "LOCKED" else "STALE"
        state["deck_harmony"] = "STALE"
        save_state(root, state)
    rerun_scope = ([f"{sid}:layout"] if invalidates_layout else []) + [f"{sid}:image", f"{sid}:render", f"{sid}:qa", "deck_harmony"]
    append_jsonl(root / "decisions/decision_trace.jsonl", {
        "decision_id": f"IMAGE-RECIPE-{now_iso()}",
        "timestamp": now_iso(),
        "phase": "image",
        "target": {"type": "image_recipe", "id": recipe_id, "slide_id": sid},
        "decision_type": "user_override_image_recipe",
        "before": before,
        "selected": {
            "prompt_seed": recipe.get("prompt_seed"),
            "negative_space": (recipe.get("composition") or {}).get("negative_space"),
            "focal_point": (recipe.get("composition") or {}).get("focal_point"),
        },
        "changed_fields": changed,
        "previous_asset_id": previous_asset,
        "origin": "user",
        "rerun_scope": rerun_scope,
        "layout_invalidated": invalidates_layout,
    })
    return {
        "recipe": recipe, "changed": changed, "previous_asset_id": previous_asset,
        "status": recipe.get("status"), "layout_invalidated": invalidates_layout,
    }


def select_image_asset(project: str | Path, recipe_id: str, asset_id: str) -> dict[str, Any]:
    root = Path(project).resolve()
    manifest = _load_manifest(root)
    asset = next((x for x in manifest.get("assets", []) if x.get("asset_id") == asset_id and x.get("recipe_id") == recipe_id), None)
    if not asset:
        raise ValueError("asset not found for recipe")
    recipes = read_json(root / "planning/image_recipes.json", {})
    recipe = next((x for x in recipes.get("recipes", []) if x.get("recipe_id") == recipe_id), None)
    if not recipe:
        raise ValueError("recipe not found")
    manifest.setdefault("selected_by_recipe", {})[recipe_id] = asset_id
    recipe["selected_asset_id"] = asset_id
    recipe["status"] = "READY"
    _update_slide_plan(root, recipe, asset)
    _save_manifest(root, manifest)
    write_json(root / "planning/image_recipes.json", recipes)
    sid = recipe.get("slide_id")
    state = load_state(root)
    if sid:
        slide = ensure_slide(state, sid)
        slide["image"] = "APPROVED"
        for phase in ("render", "qa"):
            slide[phase] = "STALE_LOCKED" if slide.get(phase) == "LOCKED" else "STALE"
        state["deck_harmony"] = "STALE"
        save_state(root, state)
    append_jsonl(root / "decisions/decision_trace.jsonl", {
        "decision_id": f"IMAGE-SELECT-{now_iso()}",
        "timestamp": now_iso(),
        "phase": "image",
        "target": {"type": "slide", "id": sid},
        "decision_type": "select_image_candidate",
        "selected": asset_id,
        "origin": "user",
        "rerun_scope": [f"{sid}:render", f"{sid}:qa", "deck_harmony"],
    })
    return {"recipe": recipe, "asset": asset}


def _selected_assets(
    root: Path,
    slide_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    recipes = read_json(root / "planning/image_recipes.json", {})
    manifest = _load_manifest(root)
    by_id = {x.get("asset_id"): x for x in manifest.get("assets", [])}
    rows = []
    for recipe in recipes.get("recipes", []):
        if slide_ids is not None and recipe.get("slide_id") not in slide_ids:
            continue
        asset_id = recipe.get("selected_asset_id") or manifest.get("selected_by_recipe", {}).get(recipe.get("recipe_id"))
        asset = by_id.get(asset_id)
        if asset:
            rows.append({"recipe": recipe, "asset": asset})
    return rows, recipes, manifest


def _image_harmony_score(metrics: dict[str, Any], target: dict[str, Any], tolerances: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    weights = {"brightness": 0.23, "saturation": 0.20, "contrast": 0.20, "edge_density": 0.21, "warmth": 0.16}
    distances = metric_distance(metrics, target)
    score = 0.0
    weight_sum = 0.0
    normalized = {}
    for key, weight in weights.items():
        diff = distances.get(key)
        tol = float(tolerances.get(key) or {"brightness": .20, "saturation": .24, "contrast": .22, "edge_density": .16, "warmth": .18}[key])
        if diff is None:
            continue
        component = max(0.0, 1.0 - float(diff) / max(0.001, tol * 2.0))
        normalized[key] = round(component, 4)
        score += component * weight
        weight_sum += weight
    return round(score / weight_sum, 4) if weight_sum else 1.0, {"distances": distances, "components": normalized}


def validate_image_harmony(
    project: str | Path,
    *,
    output_ids: list[str] | None = None,
    rendered_files: list[str | Path] | None = None,
) -> dict[str, Any]:
    root = Path(project).resolve()
    scope = set(output_ids) if output_ids else None
    rows, recipes_doc, manifest = _selected_assets(root, scope)
    active_slide_ids = set(output_ids or []) if output_ids else None
    if active_slide_ids is not None:
        rows = [row for row in rows if row["recipe"].get("slide_id") in active_slide_ids]
    art = read_json(root / "planning/deck_art_direction.json", {})
    fingerprint = read_json(root / "analysis/design_fingerprint.json", {})
    target_default = art.get("target_metrics") or (fingerprint.get("image_treatment") or {}).get("target_metrics") or {}
    tolerances = art.get("harmony_tolerance") or (fingerprint.get("image_treatment") or {}).get("harmony_tolerance") or {}
    active_recipes = [r for r in recipes_doc.get("recipes", []) if active_slide_ids is None or r.get("slide_id") in active_slide_ids]
    recipes_by_slide: dict[str, list[dict[str, Any]]] = {}
    for recipe in active_recipes:
        recipes_by_slide.setdefault(recipe.get("slide_id"), []).append(recipe)
    checks: list[dict[str, Any]] = []

    def add(code: str, result: str, severity: str = "info", **extra: Any) -> None:
        checks.append({"check_id": code, "result": result, "severity": severity, **extra})

    selected_recipe_ids = {row["recipe"].get("recipe_id") for row in rows}
    for recipe in active_recipes:
        rid, sid = recipe.get("recipe_id"), recipe.get("slide_id")
        if rid not in selected_recipe_ids:
            add("IMAGE_ASSET_READY", "fail", "blocking", recipe_id=rid, slide_id=sid, reason=recipe.get("review_reason") or "No selected image asset")

    for row in rows:
        recipe, asset = row["recipe"], row["asset"]
        rid, sid = recipe.get("recipe_id"), recipe.get("slide_id")
        processed = _resolve_project_path(root, asset["processed_path"])
        if not processed.exists():
            add("IMAGE_ASSET_READY", "fail", "blocking", recipe_id=rid, slide_id=sid, asset_id=asset.get("asset_id"))
            continue
        add("IMAGE_ASSET_READY", "pass", "info", recipe_id=rid, slide_id=sid, asset_id=asset.get("asset_id"))
        if asset.get("provider") == "mock":
            add("IMAGE_PROVIDER_PLACEHOLDER", "fail", "warning", recipe_id=rid, slide_id=sid, asset_id=asset.get("asset_id"), reason="Offline mock imagery is for layout verification only and should be replaced before production delivery.")
        lineage = asset.get("lineage") or {}
        target_info = recipe.get("target") or {}
        source_lineage = bool(lineage.get("source_object_id") and (lineage.get("source_asset_id") or target_info.get("source_visual_metrics")))
        layout_lineage = bool(target_info.get("layout_slot_id") and target_info.get("source_slide_id") and (lineage.get("style_reference") or recipe.get("style_reference") or (recipe.get("treatment") or {}).get("target_metrics")))
        lineage_ok = source_lineage or layout_lineage
        add("IMAGE_SOURCE_LINEAGE", "pass" if lineage_ok else "fail", "info" if lineage_ok else "warning", recipe_id=rid, slide_id=sid, source_slide_id=lineage.get("source_slide_id") or target_info.get("source_slide_id"), source_object_id=lineage.get("source_object_id"), source_asset_id=lineage.get("source_asset_id"), layout_slot_id=target_info.get("layout_slot_id"), lineage_mode="source_object" if source_lineage else "layout_slot" if layout_lineage else "unknown")
        process = asset.get("process") or {}
        treatment_ok = bool(process.get("crop") and process.get("grading") and process.get("target_metrics") is not None)
        add("IMAGE_TREATMENT_APPLIED", "pass" if treatment_ok else "fail", "info" if treatment_ok else "blocking", recipe_id=rid, slide_id=sid, preset=(recipe.get("treatment") or {}).get("preset"), grading=(process.get("grading") or {}).get("factors"))
        metrics = analyze_image(processed)
        expected_aspect = _target_aspect(recipe)
        aspect_diff = abs(float(metrics.get("aspect_ratio") or 0) - expected_aspect) / max(0.001, expected_aspect)
        add("IMAGE_SLOT_ASPECT", "pass" if aspect_diff <= .015 else "fail", "info" if aspect_diff <= .015 else "blocking", recipe_id=rid, slide_id=sid, expected=round(expected_aspect, 5), actual=metrics.get("aspect_ratio"), relative_difference=round(aspect_diff, 5))

        bbox = (recipe.get("target") or {}).get("bbox") or {}
        try:
            ppi = min(float(metrics["width_px"]) / float(bbox["w"]), float(metrics["height_px"]) / float(bbox["h"]))
        except Exception:
            ppi = None
        min_ppi = float((fingerprint.get("image_treatment") or {}).get("minimum_effective_ppi") or 120)
        add("IMAGE_EFFECTIVE_RESOLUTION", "pass" if ppi is None or ppi >= min_ppi else "fail", "info" if ppi is None or ppi >= min_ppi else "warning", recipe_id=rid, slide_id=sid, effective_ppi=round(ppi, 1) if ppi is not None else None, minimum_ppi=min_ppi)

        target = (recipe.get("treatment") or {}).get("target_metrics") or target_default
        harmony_score, detail = _image_harmony_score(metrics, target, tolerances)
        if harmony_score >= .70:
            result, severity = "pass", "info"
        elif harmony_score >= .52:
            result, severity = "fail", "warning"
        else:
            result, severity = "fail", "blocking"
        add("IMAGE_TEMPLATE_HARMONY", result, severity, recipe_id=rid, slide_id=sid, score=harmony_score, metrics=metrics, target_metrics=target, **detail)

        negative_space = (recipe.get("composition") or {}).get("negative_space")
        if negative_space in {"left", "right", "top", "bottom"}:
            with Image.open(processed) as im:
                side = side_complexity(im, negative_space)
                opposite_name = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}[negative_space]
                opposite = side_complexity(im, opposite_name)
            okay = side is None or opposite is None or side <= max(.18, opposite * 1.05)
            add("IMAGE_NEGATIVE_SPACE", "pass" if okay else "fail", "info" if okay else "warning", recipe_id=rid, slide_id=sid, requested_side=negative_space, side_edge_density=round(side, 4) if side is not None else None, opposite_edge_density=round(opposite, 4) if opposite is not None else None)

        plan = read_json(root / f"planning/slide_plans/{sid}.json", {})
        target_info = recipe.get("target") or {}
        expected_object = target_info.get("source_object_id")
        layout_slot_id = target_info.get("layout_slot_id")
        mutation = next((m for m in plan.get("source_object_mutations", []) if expected_object and m.get("source_object_id") == expected_object and m.get("action") == "replace_image" and m.get("asset_id") == asset.get("asset_id")), None)
        layout_plan = read_json(root / f"render/layout_plans/{sid}.json", {})
        planned_slot = next((slot for slot in layout_plan.get("image_slots", []) if slot.get("slot_id") == layout_slot_id and slot.get("recipe_id") == rid), None) if layout_slot_id else None
        rendered_slot = next((obj for obj in layout_plan.get("generated_objects", []) if obj.get("recipe_id") == rid and obj.get("asset_id") == asset.get("asset_id") and obj.get("role") in {"primary_visual", "background_visual"}), None)
        frame_ok = bool(mutation or (planned_slot and (layout_plan.get("planned_only") or rendered_slot)))
        add("IMAGE_FRAME_APPLICATION", "pass" if frame_ok else "fail", "info" if frame_ok else "blocking", recipe_id=rid, slide_id=sid, source_object_id=expected_object, layout_slot_id=layout_slot_id, frame_asset_ids=target_info.get("frame_asset_ids") or [], application_mode="source_picture_relationship" if mutation else "layout_generated_slot" if frame_ok else "missing")

    # After compose/render, verify that the expected slot actually changed. Pixel-diff
    # outside mutation masks remains handled by validate_output.py.
    if output_ids and rendered_files:
        source_doc = read_json(root / "analysis/source_slides.json", {})
        sw = float(source_doc.get("presentation", {}).get("width_in") or 13.333)
        sh = float(source_doc.get("presentation", {}).get("height_in") or 7.5)
        rendered_by_slide = {sid: Path(rendered_files[idx]) for idx, sid in enumerate(output_ids) if idx < len(rendered_files)}
        for sid, slide_recipes in recipes_by_slide.items():
            output = rendered_by_slide.get(sid)
            for recipe in slide_recipes:
                source_id = (recipe.get("target") or {}).get("source_slide_id")
                source_png = root / f"render/source_renders/{source_id}.png" if source_id else None
                bbox = (recipe.get("target") or {}).get("bbox") or {}
                if not output or not output.exists() or not source_png or not source_png.exists() or not bbox:
                    continue
                with Image.open(output).convert("RGB") as out_im, Image.open(source_png).convert("RGB") as src_im:
                    if src_im.size != out_im.size:
                        src_im = src_im.resize(out_im.size, Image.Resampling.LANCZOS)
                    x0 = max(0, round(float(bbox["x"]) / sw * out_im.width))
                    y0 = max(0, round(float(bbox["y"]) / sh * out_im.height))
                    x1 = min(out_im.width, round((float(bbox["x"]) + float(bbox["w"])) / sw * out_im.width))
                    y1 = min(out_im.height, round((float(bbox["y"]) + float(bbox["h"])) / sh * out_im.height))
                    out_crop = out_im.crop((x0, y0, x1, y1))
                    src_crop = src_im.crop((x0, y0, x1, y1))
                    diff = ImageOps.grayscale(ImageChops.difference(out_crop, src_crop))
                    histogram = diff.histogram()
                    changed = sum(histogram[12:])
                    ratio = changed / max(1, out_crop.width * out_crop.height)
                add("IMAGE_RENDERED_IN_TARGET_SLOT", "pass" if ratio >= .015 else "fail", "info" if ratio >= .015 else "blocking", recipe_id=recipe.get("recipe_id"), slide_id=sid, changed_ratio=round(ratio, 5), source_object_id=(recipe.get("target") or {}).get("source_object_id"))

    blocking = [c for c in checks if c["result"] == "fail" and c["severity"] == "blocking"]
    warnings = [c for c in checks if c["result"] == "fail" and c["severity"] != "blocking"]
    report = {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "status": "fail" if blocking else "pass",
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "checks": checks,
    }
    write_json(root / "qa/image_harmony.json", report)
    return report


def validate_deck_image_coherence(project: str | Path) -> dict[str, Any]:
    root = Path(project).resolve()
    rows, _, _ = _selected_assets(root)
    checks: list[dict[str, Any]] = []

    def add(code: str, result: str, severity: str = "info", **extra: Any) -> None:
        checks.append({"check_id": code, "result": result, "severity": severity, **extra})

    if len(rows) <= 1:
        add("DECK_IMAGE_COHERENCE", "pass", "info", image_count=len(rows), reason="At least two selected images are required for cross-image comparison.")
    else:
        metrics = [(row["recipe"].get("slide_id"), row["asset"].get("metrics") or {}) for row in rows]
        ranges = {}
        thresholds = {"brightness": .28, "saturation": .30, "contrast": .30, "edge_density": .24, "warmth": .30}
        score_parts = []
        for key, threshold in thresholds.items():
            values = [float(m.get(key)) for _, m in metrics if m.get(key) is not None]
            value_range = max(values) - min(values) if values else 0.0
            ranges[key] = round(value_range, 4)
            score_parts.append(max(0.0, 1.0 - value_range / max(.001, threshold * 2)))
            if value_range > threshold:
                add("DECK_IMAGE_METRIC_RANGE", "fail", "warning", metric=key, value_range=round(value_range, 4), threshold=threshold)
        duplicate_pairs = []
        shared_series_pairs = []
        for idx, left in enumerate(rows):
            for right in rows[idx + 1 :]:
                left_hash = (left["asset"].get("metrics") or {}).get("average_hash")
                right_hash = (right["asset"].get("metrics") or {}).get("average_hash")
                distance = hamming_distance(left_hash, right_hash)
                if distance is None:
                    continue
                left_slide = left["recipe"].get("slide_id")
                right_slide = right["recipe"].get("slide_id")
                detail = {
                    "slide_ids": [left_slide, right_slide],
                    "recipe_ids": [left["recipe"].get("recipe_id"), right["recipe"].get("recipe_id")],
                    "asset_ids": [left["asset"].get("asset_id"), right["asset"].get("asset_id")],
                    "hash_distance": distance,
                }
                # A four-image series on one page is expected to share composition
                # and grading. Only exact perceptual matches are suspicious there;
                # across slides, a slightly looser threshold catches repeated stock
                # imagery that makes a deck feel templated.
                if left_slide == right_slide:
                    if distance == 0:
                        duplicate_pairs.append(detail)
                    elif distance <= 3:
                        shared_series_pairs.append(detail)
                elif distance <= 4:
                    duplicate_pairs.append(detail)
        if duplicate_pairs:
            add("DECK_IMAGE_NEAR_DUPLICATE", "fail", "warning", pairs=duplicate_pairs)
        if shared_series_pairs:
            add("DECK_IMAGE_SHARED_SERIES_STYLE", "pass", "info", pairs=shared_series_pairs,
                reason="Images on the same slide share a coherent composition without being exact duplicates.")
        score = round(sum(score_parts) / max(1, len(score_parts)), 4)
        add("DECK_IMAGE_COHERENCE", "pass" if score >= .62 else "fail", "info" if score >= .62 else "warning", image_count=len(rows), score=score, metric_ranges=ranges)

    warnings = [c for c in checks if c["result"] == "fail"]
    report = {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "status": "pass",
        "blocking_count": 0,
        "warning_count": len(warnings),
        "checks": checks,
        "notes": ["Deck image coherence is diagnostic; it never regenerates the deck automatically."],
    }
    write_json(root / "qa/deck_image_coherence.json", report)
    return report
