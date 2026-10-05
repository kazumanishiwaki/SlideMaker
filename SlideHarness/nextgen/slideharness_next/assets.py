from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def load_asset_manifest(path: str | Path | None) -> dict[str, Path]:
    """Load host-resolved image assets without coupling the core to a provider SDK."""
    if path is None:
        return {}
    source = Path(path).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    items = payload.get("assets", payload) if isinstance(payload, dict) else payload
    if isinstance(items, dict):
        items = [{"asset_id": key, "path": value} for key, value in items.items()]
    resolved: dict[str, Path] = {}
    for item in items or []:
        asset_id = str(item.get("asset_id", ""))
        value = item.get("path") or item.get("resolved_path")
        if not asset_id or not value:
            continue
        candidate = Path(value)
        candidate = candidate if candidate.is_absolute() else (source.parent / candidate).resolve()
        if candidate.is_file():
            resolved[asset_id] = candidate
    return resolved


def resolve_asset_requests(
    plans: list[Any],
    spec_path: Path,
    output_dir: Path,
    manifest_assets: dict[str, Path],
    explicit_image: Path | None,
    template_preview: Path | None,
) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    # Keep the candidate manifest separate from the paths returned to the
    # composer. Otherwise a request rejected for duplicate image reuse would
    # still be rendered because its manifest entry remained in ``assets``.
    assets: dict[str, Path] = {}
    used_paths: dict[Path, str] = {}
    requests: list[dict[str, Any]] = []
    for plan in plans:
        for request in plan.asset_requests:
            item = dict(request)
            asset_id = str(item["asset_id"])
            candidates: list[tuple[str, Path]] = []
            manifest_path = manifest_assets.get(asset_id)
            if manifest_path is not None:
                candidates.append(("asset_manifest", manifest_path))
            value = item.get("resolved_path")
            if value:
                candidate = Path(value)
                candidate = candidate if candidate.is_absolute() else (spec_path.parent / candidate).resolve()
                if candidate.is_file():
                    candidates.append(("slide_spec", candidate))
            if explicit_image and explicit_image.is_file():
                candidates.append(("explicit_image", explicit_image))
            if template_preview and template_preview.is_file():
                candidates.append(("template_preview", template_preview))

            resolved: Path | None = None
            duplicate_owner: str | None = None
            allow_reuse = item.get("allow_reuse") is True
            for source, candidate in candidates:
                candidate = candidate.resolve()
                owner = used_paths.get(candidate)
                if owner is not None and not allow_reuse:
                    duplicate_owner = owner
                    continue
                resolved = candidate
                item["resolution_source"] = source
                break
            if resolved:
                assets[asset_id] = resolved
                used_paths.setdefault(resolved, asset_id)
                item["resolved_path"] = str(resolved)
                item["status"] = "resolved"
            else:
                item["resolved_path"] = None
                item["status"] = "awaiting_image"
                if duplicate_owner is not None:
                    item["reason"] = "duplicate_image_reuse_blocked"
                    item["conflicts_with_asset_id"] = duplicate_owner
            requests.append(item)
    return assets, requests
