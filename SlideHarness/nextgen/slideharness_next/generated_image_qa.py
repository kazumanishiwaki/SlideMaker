from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import shutil
import subprocess

from PIL import Image, ImageStat


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u3040-\u30ff\u3400-\u9fff]+", "", value).lower()


def _requested_ratio(value: Any) -> float | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*", str(value or ""))
    if not match:
        return None
    width, height = float(match.group(1)), float(match.group(2))
    return width / height if height > 0 else None


def _ocr_text(path: Path, languages: str) -> tuple[str | None, str | None]:
    executable = shutil.which("tesseract")
    if not executable:
        return None, "tesseract is unavailable"
    result = subprocess.run(
        # Sparse-text mode is better suited to diagrams and chart labels than
        # the single-block mode used for scanned document pages.
        [executable, str(path), "stdout", "-l", languages, "--psm", "11"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        return None, result.stderr.strip() or "tesseract failed"
    return result.stdout, None


def inspect_generated_images(
    requests: list[dict[str, Any]],
    *,
    languages: str = "jpn+eng",
    minimum_width: int = 1024,
    minimum_height: int = 576,
) -> dict[str, Any]:
    generated = [item for item in requests if item.get("kind") == "generated_image"]
    if not generated:
        return {"schema_version": "0.4.0", "status": "SKIP", "reason": "no generated images", "assets": [], "summary": {"blocking_count": 0, "review_count": 0}}

    findings: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    for request in generated:
        asset_id = str(request.get("asset_id") or "")
        required_text = [str(item) for item in request.get("required_text") or [] if str(item).strip()]
        resolved = request.get("resolved_path")
        report: dict[str, Any] = {
            "asset_id": asset_id,
            "slide_id": request.get("slide_id"),
            "visual_kind": request.get("visual_kind"),
            "resolved_path": resolved,
            "required_text": required_text,
            "dimensions": None,
            "aspect_ratio": None,
            "aspect_ratio_error": None,
            "missing_text": [],
        }
        if request.get("status") != "resolved" or not resolved or not Path(resolved).is_file():
            findings.append({"category": "Content", "code": "generated_image_unresolved", "severity": "blocking", "asset_id": asset_id, "message": "generated image is unresolved"})
            assets.append(report)
            continue

        path = Path(resolved)
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path).convert("RGB") as image:
                width, height = image.size
                report["dimensions"] = [width, height]
                actual_ratio = width / height if height else 0.0
                report["aspect_ratio"] = actual_ratio
                extrema = ImageStat.Stat(image).extrema
                dynamic_range = max((maximum - minimum) for minimum, maximum in extrema)
                report["dynamic_range"] = dynamic_range
                grayscale = image.convert("L")
                entropy = grayscale.entropy()
                luminance_stddev = ImageStat.Stat(grayscale).stddev[0]
                report["entropy"] = entropy
                report["luminance_stddev"] = luminance_stddev
                if width < minimum_width or height < minimum_height:
                    findings.append({"category": "Technical", "code": "generated_image_too_small", "severity": "blocking", "asset_id": asset_id, "message": f"generated image is {width}x{height}; minimum is {minimum_width}x{minimum_height}"})
                if dynamic_range < 12 or entropy < 1.5 or luminance_stddev < 5:
                    findings.append({"category": "Design", "code": "generated_image_nearly_blank", "severity": "blocking", "asset_id": asset_id, "message": "generated image has insufficient visual variation"})
                expected_ratio = _requested_ratio(request.get("aspect_ratio"))
                if expected_ratio and actual_ratio:
                    ratio_error = abs(actual_ratio - expected_ratio) / expected_ratio
                    report["aspect_ratio_error"] = ratio_error
                    if ratio_error > 0.30:
                        findings.append({"category": "Design", "code": "generated_image_aspect_ratio_mismatch", "severity": "blocking", "asset_id": asset_id, "message": f"generated image ratio {actual_ratio:.3f} is too far from requested ratio {expected_ratio:.3f}"})
                    elif ratio_error > 0.12:
                        findings.append({"category": "Design", "code": "generated_image_requires_crop_review", "severity": "review", "asset_id": asset_id, "message": f"generated image ratio {actual_ratio:.3f} requires crop review for requested ratio {expected_ratio:.3f}"})
        except Exception as error:
            findings.append({"category": "Technical", "code": "generated_image_invalid", "severity": "blocking", "asset_id": asset_id, "message": str(error)})
            assets.append(report)
            continue

        if request.get("visual_kind") in {"chart", "flow"} and not required_text:
            findings.append({"category": "Content", "code": "generated_visual_missing_required_text", "severity": "blocking", "asset_id": asset_id, "message": "structured generated visuals must declare required_text"})
        if required_text:
            recognized, error = _ocr_text(path, languages)
            if error:
                findings.append({"category": "Technical", "code": "generated_image_text_qa_unavailable", "severity": "blocking", "asset_id": asset_id, "message": error})
            else:
                normalized_ocr = _normalize(recognized or "")
                missing = [label for label in required_text if _normalize(label) not in normalized_ocr]
                report["missing_text"] = missing
                report["recognized_text"] = recognized
                if missing:
                    findings.append({"category": "Content", "code": "generated_image_required_text_missing", "severity": "blocking", "asset_id": asset_id, "message": f"{len(missing)} required label(s) were not recognized", "items": missing})
        assets.append(report)

    blocking = [item for item in findings if item["severity"] == "blocking"]
    review = [item for item in findings if item["severity"] == "review"]
    return {
        "schema_version": "0.4.0",
        "status": "FAIL" if blocking else "PASS",
        "assets": assets,
        "findings": findings,
        "summary": {"asset_count": len(assets), "blocking_count": len(blocking), "review_count": len(review)},
    }
