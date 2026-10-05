from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
import math

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _open_image(source: str | Path | bytes) -> Image.Image:
    if isinstance(source, bytes):
        im = Image.open(BytesIO(source))
    else:
        im = Image.open(source)
    return ImageOps.exif_transpose(im)


def _analysis_copy(im: Image.Image, max_side: int = 320) -> Image.Image:
    out = im.convert("RGBA")
    if max(out.size) > max_side:
        out.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return out


def _dominant_colors(rgb: Image.Image, count: int = 5) -> list[dict[str, Any]]:
    small = rgb.copy()
    small.thumbnail((128, 128), Image.Resampling.LANCZOS)
    # MEDIANCUT is deterministic and works well for source-deck palette extraction.
    q = small.quantize(colors=max(2, count), method=Image.Quantize.MEDIANCUT)
    palette = q.getpalette() or []
    counts = q.getcolors(maxcolors=128 * 128) or []
    total = max(1, sum(n for n, _ in counts))
    rows = []
    for n, idx in sorted(counts, reverse=True)[:count]:
        base = idx * 3
        if base + 2 >= len(palette):
            continue
        r, g, b = palette[base : base + 3]
        rows.append({"hex": f"#{r:02X}{g:02X}{b:02X}", "ratio": round(n / total, 4)})
    return rows


def average_hash(im: Image.Image, size: int = 8) -> str:
    gray = ImageOps.grayscale(im).resize((size, size), Image.Resampling.LANCZOS)
    values = list(gray.get_flattened_data() if hasattr(gray, "get_flattened_data") else gray.getdata())
    avg = sum(values) / max(1, len(values))
    bits = 0
    for value in values:
        bits = (bits << 1) | int(value >= avg)
    width = math.ceil(size * size / 4)
    return f"{bits:0{width}x}"


def hamming_distance(hash_a: str | None, hash_b: str | None) -> int | None:
    if not hash_a or not hash_b or len(hash_a) != len(hash_b):
        return None
    try:
        return (int(hash_a, 16) ^ int(hash_b, 16)).bit_count()
    except Exception:
        return None


def analyze_image(source: str | Path | bytes) -> dict[str, Any]:
    """Return deterministic visual metrics normalized to 0..1.

    The metrics are deliberately simple. They are not used to judge aesthetics in
    isolation; they provide stable guards for deck-wide grading and coherence.
    """
    with _open_image(source) as original:
        im = _analysis_copy(original)
        rgba = im.convert("RGBA")
        rgb = Image.new("RGB", rgba.size, (255, 255, 255))
        rgb.paste(rgba, mask=rgba.getchannel("A"))
        gray = ImageOps.grayscale(rgb)
        hsv = rgb.convert("HSV")

        gray_stat = ImageStat.Stat(gray)
        brightness = _clamp(gray_stat.mean[0] / 255.0)
        # Normalize stddev to a practical photographic range rather than the
        # theoretical maximum, keeping values interpretable for QA thresholds.
        contrast = _clamp(gray_stat.stddev[0] / 96.0)
        saturation = _clamp(ImageStat.Stat(hsv.getchannel("S")).mean[0] / 255.0)
        mean_rgb_raw = ImageStat.Stat(rgb).mean[:3]
        mean_rgb = [round(float(channel) / 255.0, 4) for channel in mean_rgb_raw]
        # Positive values are warmer (red-weighted), negative values are cooler
        # (blue-weighted). This simple metric is intentionally stable rather than
        # perceptually exhaustive; it is used only for restrained deck-wide grading.
        warmth = max(-1.0, min(1.0, (float(mean_rgb_raw[0]) - float(mean_rgb_raw[2])) / 255.0))

        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_hist = edges.histogram()
        edge_pixels = sum(edge_hist[36:])
        edge_density = _clamp(edge_pixels / max(1, gray.width * gray.height))

        alpha = rgba.getchannel("A")
        alpha_hist = alpha.histogram()
        transparent = sum(alpha_hist[:250])
        transparent_ratio = _clamp(transparent / max(1, rgba.width * rgba.height))

        return {
            "width_px": int(original.width),
            "height_px": int(original.height),
            "aspect_ratio": round(original.width / original.height, 5) if original.height else None,
            "brightness": round(brightness, 4),
            "saturation": round(saturation, 4),
            "contrast": round(contrast, 4),
            "edge_density": round(edge_density, 4),
            "warmth": round(warmth, 4),
            "mean_rgb": mean_rgb,
            "transparent_ratio": round(transparent_ratio, 4),
            "dominant_colors": _dominant_colors(rgb),
            "average_hash": average_hash(rgb),
        }


def metric_distance(actual: dict[str, Any], target: dict[str, Any]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key in ("brightness", "saturation", "contrast", "edge_density", "warmth"):
        a = actual.get(key)
        t = target.get(key)
        out[key] = round(abs(float(a) - float(t)), 4) if a is not None and t is not None else None
    return out


def grade_toward(
    im: Image.Image,
    target: dict[str, Any] | None,
    *,
    max_brightness_factor: tuple[float, float] = (0.72, 1.36),
    max_saturation_factor: tuple[float, float] = (0.65, 1.40),
    max_contrast_factor: tuple[float, float] = (0.72, 1.32),
) -> tuple[Image.Image, dict[str, Any]]:
    """Apply restrained grading toward a source-deck metric target."""
    out = im.convert("RGB")
    before = analyze_image(_image_bytes(out))
    target = target or {}
    factors: dict[str, float] = {}

    def factor_for(key: str, bounds: tuple[float, float]) -> float:
        current = max(0.03, float(before.get(key) or 0.03))
        wanted = target.get(key)
        if wanted is None:
            return 1.0
        return max(bounds[0], min(bounds[1], float(wanted) / current))

    brightness_factor = factor_for("brightness", max_brightness_factor)
    if abs(brightness_factor - 1.0) > 0.01:
        out = ImageEnhance.Brightness(out).enhance(brightness_factor)
    factors["brightness"] = round(brightness_factor, 4)

    # Match color temperature with a deliberately restrained channel balance.
    # The transformation is bounded so a supplied image remains recognizable.
    target_warmth = target.get("warmth")
    current_warmth = before.get("warmth")
    warmth_delta = 0.0
    if target_warmth is not None and current_warmth is not None:
        warmth_delta = max(-0.22, min(0.22, float(target_warmth) - float(current_warmth)))
        if abs(warmth_delta) > 0.015:
            r, g, b = out.split()
            red_factor = max(0.92, min(1.08, 1.0 + warmth_delta * 0.32))
            blue_factor = max(0.92, min(1.08, 1.0 - warmth_delta * 0.32))
            r = r.point(lambda value: max(0, min(255, round(value * red_factor))))
            b = b.point(lambda value: max(0, min(255, round(value * blue_factor))))
            out = Image.merge("RGB", (r, g, b))
    factors["warmth_delta"] = round(warmth_delta, 4)

    saturation_factor = factor_for("saturation", max_saturation_factor)
    if abs(saturation_factor - 1.0) > 0.01:
        out = ImageEnhance.Color(out).enhance(saturation_factor)
    factors["saturation"] = round(saturation_factor, 4)

    contrast_factor = factor_for("contrast", max_contrast_factor)
    if abs(contrast_factor - 1.0) > 0.01:
        out = ImageEnhance.Contrast(out).enhance(contrast_factor)
    factors["contrast"] = round(contrast_factor, 4)

    # Edge density captures how visually busy or soft source images feel. A small
    # blur or unsharp pass lets new images join the same photographic family without
    # inventing content or applying a conspicuous filter.
    interim = analyze_image(_image_bytes(out))
    target_edges = target.get("edge_density")
    detail_action = "none"
    detail_amount = 0.0
    if target_edges is not None and interim.get("edge_density") is not None:
        edge_delta = float(target_edges) - float(interim["edge_density"])
        if edge_delta < -0.035:
            detail_amount = min(1.15, max(0.25, abs(edge_delta) * 5.0))
            out = out.filter(ImageFilter.GaussianBlur(radius=detail_amount))
            detail_action = "soften"
        elif edge_delta > 0.045:
            detail_amount = min(70.0, max(20.0, edge_delta * 260.0))
            out = out.filter(ImageFilter.UnsharpMask(radius=1.15, percent=round(detail_amount), threshold=3))
            detail_action = "sharpen"
    factors["detail_action"] = detail_action
    factors["detail_amount"] = round(detail_amount, 4)

    return out, {"before": before, "factors": factors, "after": analyze_image(_image_bytes(out))}


def _image_bytes(im: Image.Image, fmt: str = "PNG") -> bytes:
    buf = BytesIO()
    im.save(buf, format=fmt)
    return buf.getvalue()


def crop_cover(
    im: Image.Image,
    target_aspect: float,
    focal_point: tuple[float, float] = (0.5, 0.5),
) -> tuple[Image.Image, dict[str, Any]]:
    if target_aspect <= 0:
        raise ValueError("target_aspect must be positive")
    src = ImageOps.exif_transpose(im).convert("RGB")
    sw, sh = src.size
    if not sw or not sh:
        raise ValueError("invalid image size")
    source_aspect = sw / sh
    fx = _clamp(focal_point[0]); fy = _clamp(focal_point[1])

    if source_aspect > target_aspect:
        crop_h = sh
        crop_w = max(1, round(sh * target_aspect))
        center_x = fx * sw
        left = round(center_x - crop_w / 2)
        left = max(0, min(sw - crop_w, left))
        top = 0
    else:
        crop_w = sw
        crop_h = max(1, round(sw / target_aspect))
        center_y = fy * sh
        top = round(center_y - crop_h / 2)
        top = max(0, min(sh - crop_h, top))
        left = 0
    box = (left, top, left + crop_w, top + crop_h)
    return src.crop(box), {
        "source_size": [sw, sh],
        "source_aspect": round(source_aspect, 5),
        "target_aspect": round(target_aspect, 5),
        "focal_point": [round(fx, 4), round(fy, 4)],
        "crop_box": list(box),
    }


def side_complexity(im: Image.Image, side: str) -> float | None:
    side = str(side or "").lower()
    if side not in {"left", "right", "top", "bottom"}:
        return None
    rgb = im.convert("RGB")
    w, h = rgb.size
    if side == "left": box = (0, 0, max(1, w // 2), h)
    elif side == "right": box = (w // 2, 0, w, h)
    elif side == "top": box = (0, 0, w, max(1, h // 2))
    else: box = (0, h // 2, w, h)
    return float(analyze_image(_image_bytes(rgb.crop(box))).get("edge_density") or 0.0)
