from __future__ import annotations

from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET
import zipfile

from pptx import Presentation

from .models import write_json
from .opc import (
    package_relationships,
    relationship_is_external,
    relationship_part_path,
    relationship_source_part,
)
from .package_qa import inspect_package


OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
CONTENT_TYPE_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def _slide_paths(entries: dict[str, bytes]) -> list[str]:
    presentation = ET.fromstring(entries["ppt/presentation.xml"])
    rels = {
        item["id"]: item
        for item in package_relationships(entries, "ppt/_rels/presentation.xml.rels")
    }
    output: list[str] = []
    for slide in presentation.findall(f".//{{{PRESENTATION_NS}}}sldId"):
        relationship_id = slide.get(f"{{{OFFICE_REL_NS}}}id", "")
        if relationship_id not in rels:
            raise ValueError(f"presentation slide relationship {relationship_id} is missing")
        output.append(rels[relationship_id]["resolved"])
    return output


def _closure(entries: dict[str, bytes], root_part: str) -> set[str]:
    visited: set[str] = set()
    pending = [root_part]
    while pending:
        part = pending.pop()
        if part in visited:
            continue
        if part not in entries:
            raise ValueError(f"relationship target is missing: {part}")
        visited.add(part)
        rels_path = relationship_part_path(part)
        if rels_path not in entries:
            continue
        visited.add(rels_path)
        for relationship in package_relationships(entries, rels_path):
            if not relationship_is_external(relationship):
                pending.append(relationship["resolved"])
    return visited


def _reverse_references(entries: dict[str, bytes]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {}
    for rels_path in (name for name in entries if name.endswith(".rels")):
        source = relationship_source_part(rels_path)
        for relationship in package_relationships(entries, rels_path):
            if relationship_is_external(relationship):
                continue
            reverse.setdefault(relationship["resolved"], set()).add(source)
    return reverse


def _owner_part(entry: str) -> str:
    return relationship_source_part(entry) if entry.endswith(".rels") else entry


def _fingerprint(entries: dict[str, bytes], slide_path: str) -> str:
    digest = sha256()
    for name in sorted(_closure(entries, slide_path)):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entries[name])
        digest.update(b"\0")
    return digest.hexdigest()


def _merge_content_types(base: bytes, candidate: bytes, added: set[str]) -> bytes:
    if not added:
        return base
    base_root = ET.fromstring(base)
    candidate_root = ET.fromstring(candidate)
    existing_defaults = {item.get("Extension") for item in base_root.findall(f"{{{CONTENT_TYPE_NS}}}Default")}
    existing_overrides = {item.get("PartName") for item in base_root.findall(f"{{{CONTENT_TYPE_NS}}}Override")}
    added_extensions = {PurePosixPath(name).suffix.lstrip(".") for name in added}
    added_part_names = {f"/{name}" for name in added}
    for item in candidate_root:
        tag = item.tag.rsplit("}", 1)[-1]
        if tag == "Default" and item.get("Extension") in added_extensions and item.get("Extension") not in existing_defaults:
            base_root.append(item)
            existing_defaults.add(item.get("Extension"))
        elif tag == "Override" and item.get("PartName") in added_part_names and item.get("PartName") not in existing_overrides:
            base_root.append(item)
            existing_overrides.add(item.get("PartName"))
    ET.register_namespace("", CONTENT_TYPE_NS)
    return ET.tostring(base_root, encoding="utf-8", xml_declaration=True)


def _prune_content_types(payload: bytes, removed: set[str]) -> bytes:
    if not removed:
        return payload
    root = ET.fromstring(payload)
    removed_part_names = {f"/{name}" for name in removed}
    for item in list(root):
        if item.tag.rsplit("}", 1)[-1] != "Override":
            continue
        if item.get("PartName") in removed_part_names:
            root.remove(item)
    ET.register_namespace("", CONTENT_TYPE_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def isolate_regenerated_slide(
    base_pptx: str | Path,
    candidate_pptx: str | Path,
    slide_index: int,
    output_pptx: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Replace exactly one slide package subtree and prove every other page is unchanged."""

    if slide_index < 0:
        raise ValueError("slide index must be zero or greater")
    base_path = Path(base_pptx).resolve()
    candidate_path = Path(candidate_pptx).resolve()
    output_path = Path(output_pptx).resolve()
    with zipfile.ZipFile(base_path) as archive:
        base_entries = {name: archive.read(name) for name in archive.namelist()}
        base_infos = {item.filename: item for item in archive.infolist()}
        base_comment = archive.comment
    with zipfile.ZipFile(candidate_path) as archive:
        candidate_entries = {name: archive.read(name) for name in archive.namelist()}
        candidate_infos = {item.filename: item for item in archive.infolist()}

    base_slides = _slide_paths(base_entries)
    candidate_slides = _slide_paths(candidate_entries)
    if len(base_slides) != len(candidate_slides):
        raise ValueError("candidate slide count differs from the current deck")
    if slide_index >= len(base_slides):
        raise ValueError(f"slide index {slide_index} is out of range")
    base_target = base_slides[slide_index]
    candidate_target = candidate_slides[slide_index]
    if PurePosixPath(base_target).parent != PurePosixPath(candidate_target).parent:
        raise ValueError("candidate uses an incompatible slide package path")

    before = {
        index: _fingerprint(base_entries, slide_path)
        for index, slide_path in enumerate(base_slides)
        if index != slide_index
    }
    base_target_closure = _closure(base_entries, base_target)
    candidate_target_closure = _closure(candidate_entries, candidate_target)
    reverse = _reverse_references(base_entries)
    replacements: dict[str, bytes] = {
        base_target: candidate_entries[candidate_target],
        relationship_part_path(base_target): candidate_entries.get(
            relationship_part_path(candidate_target), b""
        ),
    }
    added: set[str] = set()
    removed: set[str] = set()
    changed_dependencies: list[str] = []

    for candidate_entry in sorted(candidate_target_closure):
        if candidate_entry in {candidate_target, relationship_part_path(candidate_target)}:
            continue
        destination = candidate_entry
        candidate_bytes = candidate_entries[candidate_entry]
        if destination not in base_entries:
            replacements[destination] = candidate_bytes
            added.add(destination)
            changed_dependencies.append(destination)
            continue
        if base_entries[destination] == candidate_bytes:
            continue
        owner = _owner_part(destination)
        external_sources = reverse.get(owner, set()) - {
            _owner_part(item) for item in base_target_closure
        }
        if external_sources:
            sources = ", ".join(sorted(external_sources)[:5])
            raise ValueError(f"target slide would change shared package part {destination} referenced by {sources}")
        replacements[destination] = candidate_bytes
        changed_dependencies.append(destination)

    base_target_owners = {_owner_part(item) for item in base_target_closure}
    for base_entry in sorted(base_target_closure - candidate_target_closure):
        if base_entry in {base_target, relationship_part_path(base_target)}:
            continue
        owner = _owner_part(base_entry)
        external_sources = reverse.get(owner, set()) - base_target_owners
        if not external_sources:
            removed.add(base_entry)

    base_relationships_path = relationship_part_path(base_target)
    if base_relationships_path not in base_entries and not replacements[base_relationships_path]:
        replacements.pop(base_relationships_path, None)
    if added:
        replacements["[Content_Types].xml"] = _merge_content_types(
            base_entries["[Content_Types].xml"],
            candidate_entries["[Content_Types].xml"],
            added,
        )
    if removed:
        replacements["[Content_Types].xml"] = _prune_content_types(
            replacements.get("[Content_Types].xml", base_entries["[Content_Types].xml"]),
            removed,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w") as archive:
        archive.comment = base_comment
        for name, info in base_infos.items():
            if name in removed:
                continue
            archive.writestr(info, replacements.get(name, base_entries[name]))
        for name in sorted(added - set(base_infos)):
            archive.writestr(candidate_infos.get(name, name), replacements[name])

    with zipfile.ZipFile(output_path) as archive:
        final_entries = {name: archive.read(name) for name in archive.namelist()}
    final_slides = _slide_paths(final_entries)
    after = {
        index: _fingerprint(final_entries, slide_path)
        for index, slide_path in enumerate(final_slides)
        if index != slide_index
    }
    changed_non_targets = [index for index in before if before[index] != after.get(index)]
    if changed_non_targets:
        raise ValueError(f"page isolation failed; non-target slides changed: {changed_non_targets}")
    # Fail closed if PowerPoint cannot open the isolated package.
    if len(Presentation(str(output_path)).slides) != len(base_slides):
        raise ValueError("isolated presentation is unreadable or has an invalid slide count")
    package_qa = inspect_package(output_path, base_path)
    if package_qa["status"] != "PASS":
        codes = ", ".join(item["code"] for item in package_qa["findings"][:5])
        raise ValueError(f"isolated presentation failed package QA: {codes}")

    report: dict[str, Any] = {
        "schema_version": "0.4.0",
        "status": "PASS",
        "target_slide_index": slide_index,
        "target_slide_number": slide_index + 1,
        "target_slide_path": base_target,
        "non_target_slide_count": len(before),
        "non_target_unchanged": True,
        "non_target_fingerprints_before": {str(index + 1): value for index, value in before.items()},
        "non_target_fingerprints_after": {str(index + 1): value for index, value in after.items()},
        "changed_dependencies": changed_dependencies,
        "added_dependencies": sorted(added),
        "removed_dependencies": sorted(removed),
        "package_qa": {"status": package_qa["status"], "summary": package_qa["summary"]},
    }
    if report_path:
        write_json(report_path, report)
    return report
