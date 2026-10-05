from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree as ET
import zipfile

from .opc import (
    relationship_is_external,
    relationship_part_path,
    relationship_records,
    relationship_source_part,
)

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CHART_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"

REQUIRED_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "ppt/presentation.xml",
    "ppt/_rels/presentation.xml.rels",
}

ORPHAN_CANDIDATE_PREFIXES = (
    "ppt/slides/",
    "ppt/notesSlides/",
    "ppt/media/",
    "ppt/charts/",
    "ppt/embeddings/",
    "ppt/diagrams/",
    "ppt/drawings/",
    "ppt/comments/",
)


def _finding(
    code: str,
    message: str,
    *,
    part: str | None = None,
    detail: str = "",
    severity: str = "blocking",
) -> dict[str, Any]:
    return {
        "category": "Technical",
        "code": code,
        "severity": severity,
        "part": part,
        "message": message,
        "_fingerprint": "|".join((code, part or "", detail)),
    }


def _inspect_content_types(entries: dict[str, bytes]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    payload = entries.get("[Content_Types].xml")
    if payload is None:
        return findings
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return findings

    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    for item in root:
        label = item.tag.rsplit("}", 1)[-1]
        content_type = item.get("ContentType", "")
        if label == "Default":
            extension = item.get("Extension", "").casefold()
            if not extension or not content_type:
                findings.append(_finding("invalid_content_type_default", "Content type default is missing Extension or ContentType", part="[Content_Types].xml", detail=extension))
            elif extension in defaults:
                findings.append(_finding("duplicate_content_type_default", f"Duplicate default content type for .{extension}", part="[Content_Types].xml", detail=extension))
            else:
                defaults[extension] = content_type
        elif label == "Override":
            part_name = unquote(item.get("PartName", "")).lstrip("/")
            if not part_name or not content_type:
                findings.append(_finding("invalid_content_type_override", "Content type override is missing PartName or ContentType", part="[Content_Types].xml", detail=part_name))
            elif part_name in overrides:
                findings.append(_finding("duplicate_content_type_override", f"Duplicate content type override for {part_name}", part="[Content_Types].xml", detail=part_name))
            else:
                overrides[part_name] = content_type

    for part_name in sorted(entries):
        if part_name == "[Content_Types].xml" or part_name.endswith("/"):
            continue
        extension = "rels" if part_name.endswith(".rels") else PurePosixPath(part_name).suffix.removeprefix(".").casefold()
        if part_name not in overrides and extension not in defaults:
            findings.append(_finding("missing_content_type", f"No content type is registered for {part_name}", part=part_name, detail=part_name))
    for part_name in sorted(overrides):
        if part_name not in entries:
            findings.append(_finding("orphan_content_type_override", f"Content type override points to a missing part: {part_name}", part="[Content_Types].xml", detail=part_name))
    return findings


def _inspect_relationships(entries: dict[str, bytes]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, str]]]]:
    findings: list[dict[str, Any]] = []
    records_by_path: dict[str, list[dict[str, str]]] = {}
    for rels_path in sorted(name for name in entries if name.endswith(".rels")):
        source = relationship_source_part(rels_path)
        if source and source not in entries:
            findings.append(_finding("orphan_relationship_part", f"Relationship part has no source package part: {source}", part=rels_path, detail=source))
        try:
            records = relationship_records(entries[rels_path], rels_path)
        except ET.ParseError:
            continue
        records_by_path[rels_path] = records
        ids = [item["id"] for item in records]
        for relationship_id, count in Counter(ids).items():
            if not relationship_id:
                findings.append(_finding("missing_relationship_id", "Relationship is missing an Id", part=rels_path, detail="<missing>"))
            elif count > 1:
                findings.append(_finding("duplicate_relationship_id", f"Relationship Id {relationship_id} occurs {count} times", part=rels_path, detail=relationship_id))
        for item in records:
            if relationship_is_external(item):
                continue
            if not item["target"]:
                findings.append(_finding("missing_relationship_target", f"Relationship {item['id'] or '<missing>'} has no target", part=rels_path, detail=item["id"]))
            elif item["resolved"].startswith("../") or item["resolved"] == "..":
                findings.append(_finding("relationship_target_escapes_package", f"Relationship {item['id']} escapes the package: {item['target']}", part=rels_path, detail=item["target"]))
            elif item["resolved"] not in entries:
                findings.append(_finding("relationship_target_missing", f"Relationship {item['id']} points to a missing part: {item['resolved']}", part=rels_path, detail=f"{item['id']}:{item['resolved']}"))
    return findings, records_by_path


def _inspect_presentation(entries: dict[str, bytes], records_by_path: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    presentation_payload = entries.get("ppt/presentation.xml")
    if presentation_payload is None:
        return findings
    try:
        presentation = ET.fromstring(presentation_payload)
    except ET.ParseError:
        return findings
    relationships = {item["id"]: item for item in records_by_path.get("ppt/_rels/presentation.xml.rels", []) if item["id"]}
    slide_ids: list[str] = []
    relationship_ids: list[str] = []
    for item in presentation.findall(f".//{{{PRESENTATION_NS}}}sldId"):
        slide_id = item.get("id", "")
        relationship_id = item.get(f"{{{OFFICE_REL_NS}}}id", "")
        slide_ids.append(slide_id)
        relationship_ids.append(relationship_id)
        relationship = relationships.get(relationship_id)
        if not relationship_id or relationship is None:
            findings.append(_finding("presentation_slide_relationship_missing", f"Slide id {slide_id or '<missing>'} has no matching presentation relationship", part="ppt/presentation.xml", detail=f"{slide_id}:{relationship_id}"))
        elif not relationship["type"].endswith("/slide"):
            findings.append(_finding("presentation_slide_relationship_wrong_type", f"Slide id {slide_id} uses a non-slide relationship: {relationship['type']}", part="ppt/presentation.xml", detail=f"{slide_id}:{relationship_id}"))
    for slide_id, count in Counter(slide_ids).items():
        if not slide_id:
            findings.append(_finding("missing_presentation_slide_id", "A presentation slide entry has no numeric id", part="ppt/presentation.xml", detail="<missing>"))
        elif count > 1:
            findings.append(_finding("duplicate_presentation_slide_id", f"Presentation slide id {slide_id} occurs {count} times", part="ppt/presentation.xml", detail=slide_id))
    for relationship_id, count in Counter(relationship_ids).items():
        if relationship_id and count > 1:
            findings.append(_finding("duplicate_presentation_slide_relationship", f"Presentation slide relationship {relationship_id} is referenced {count} times", part="ppt/presentation.xml", detail=relationship_id))
    return findings


def _inspect_relationship_references(entries: dict[str, bytes], records_by_path: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for part_name, payload in sorted(entries.items()):
        if not part_name.endswith(".xml") or part_name == "[Content_Types].xml":
            continue
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            continue
        relationship_ids = {
            item["id"]
            for item in records_by_path.get(relationship_part_path(part_name), [])
            if item["id"]
        }
        for node in root.iter():
            for attribute, relationship_id in node.attrib.items():
                if not attribute.startswith(f"{{{OFFICE_REL_NS}}}"):
                    continue
                if relationship_id not in relationship_ids:
                    findings.append(
                        _finding(
                            "relationship_reference_missing",
                            f"{part_name} references missing relationship {relationship_id}",
                            part=part_name,
                            detail=f"{attribute}:{relationship_id}",
                        )
                    )
    return findings


def _inspect_orphan_package_parts(entries: dict[str, bytes], records_by_path: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    """Find slide-owned payloads that are unreachable from the OPC root graph."""

    reachable = {"[Content_Types].xml", "_rels/.rels"}
    pending = [""]
    visited_sources: set[str] = set()
    while pending:
        source = pending.pop()
        if source in visited_sources:
            continue
        visited_sources.add(source)
        rels_path = "_rels/.rels" if source == "" else relationship_part_path(source)
        if rels_path in entries:
            reachable.add(rels_path)
        for relationship in records_by_path.get(rels_path, []):
            if relationship_is_external(relationship):
                continue
            target = relationship["resolved"]
            if target not in entries or target in reachable:
                continue
            reachable.add(target)
            pending.append(target)

    findings: list[dict[str, Any]] = []
    for part_name in sorted(entries):
        if part_name.endswith(".rels") or not part_name.startswith(ORPHAN_CANDIDATE_PREFIXES):
            continue
        if part_name in reachable:
            continue
        findings.append(
            _finding(
                "orphan_package_part",
                f"Package payload is unreachable and should be removed: {part_name}",
                part=part_name,
                detail=part_name,
            )
        )
    return findings


def _inspect_empty_slide_placeholders(entries: dict[str, bytes]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for part_name, payload in sorted(entries.items()):
        if not part_name.startswith("ppt/slides/slide") or not part_name.endswith(".xml"):
            continue
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            continue
        for shape_index, shape in enumerate(root.findall(f".//{{{PRESENTATION_NS}}}sp"), start=1):
            placeholder = shape.find(f"./{{{PRESENTATION_NS}}}nvSpPr/{{{PRESENTATION_NS}}}nvPr/{{{PRESENTATION_NS}}}ph")
            if placeholder is None:
                continue
            text = "".join(node.text or "" for node in shape.findall(f".//{{{DRAWING_NS}}}t")).strip()
            if text:
                continue
            placeholder_type = placeholder.get("type", "body")
            placeholder_index = placeholder.get("idx", "")
            findings.append(
                _finding(
                    "empty_structural_placeholder",
                    f"Slide contains an empty {placeholder_type} placeholder; fill or delete it",
                    part=part_name,
                    detail=f"{shape_index}:{placeholder_type}:{placeholder_index}",
                )
            )
    return findings


def _cache_count(container: ET.Element | None) -> tuple[int | None, int]:
    if container is None:
        return None, 0
    cache = next(
        (
            node
            for node in container.iter()
            if node.tag
            in {
                f"{{{CHART_NS}}}strCache",
                f"{{{CHART_NS}}}numCache",
                f"{{{CHART_NS}}}strLit",
                f"{{{CHART_NS}}}numLit",
            }
        ),
        None,
    )
    if cache is None:
        return None, 0
    count_node = cache.find(f"{{{CHART_NS}}}ptCount")
    declared = None
    if count_node is not None:
        try:
            declared = int(count_node.get("val", ""))
        except ValueError:
            declared = None
    return declared, len(cache.findall(f"{{{CHART_NS}}}pt"))


def _inspect_charts(entries: dict[str, bytes]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    axis_tags = {f"{{{CHART_NS}}}{name}" for name in ("catAx", "valAx", "dateAx", "serAx")}
    for part_name, payload in sorted(entries.items()):
        if not part_name.startswith("ppt/charts/chart") or not part_name.endswith(".xml"):
            continue
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            continue
        plot_area = root.find(f".//{{{CHART_NS}}}plotArea")
        if plot_area is None:
            findings.append(_finding("chart_plot_area_missing", "Chart has no plotArea", part=part_name, detail=part_name))
            continue
        defined_axes: set[str] = set()
        for axis in (node for node in plot_area if node.tag in axis_tags):
            axis_id = axis.find(f"{{{CHART_NS}}}axId")
            if axis_id is not None and axis_id.get("val"):
                defined_axes.add(axis_id.get("val", ""))
        referenced_axes: set[str] = set()
        for chart in (node for node in plot_area if node.tag.endswith("Chart")):
            referenced_axes.update(node.get("val", "") for node in chart.findall(f"{{{CHART_NS}}}axId") if node.get("val"))
        for axis_id in sorted(referenced_axes - defined_axes):
            findings.append(
                _finding(
                    "chart_axis_definition_missing",
                    f"Chart references axis id {axis_id} without a matching axis definition",
                    part=part_name,
                    detail=axis_id,
                )
            )
        for axis in (node for node in plot_area if node.tag in axis_tags):
            cross_axis = axis.find(f"{{{CHART_NS}}}crossAx")
            if cross_axis is not None and cross_axis.get("val") not in defined_axes:
                findings.append(
                    _finding(
                        "chart_cross_axis_missing",
                        f"Chart axis crosses undefined axis id {cross_axis.get('val', '')}",
                        part=part_name,
                        detail=cross_axis.get("val", ""),
                    )
                )
        for series_index, series in enumerate(root.findall(f".//{{{CHART_NS}}}ser"), start=1):
            category_declared, category_actual = _cache_count(series.find(f"{{{CHART_NS}}}cat"))
            value_declared, value_actual = _cache_count(series.find(f"{{{CHART_NS}}}val"))
            for label, declared, actual in (
                ("category", category_declared, category_actual),
                ("value", value_declared, value_actual),
            ):
                if declared is not None and declared != actual:
                    findings.append(
                        _finding(
                            "chart_cache_count_mismatch",
                            f"Chart series {series_index} declares {declared} {label} points but contains {actual}",
                            part=part_name,
                            detail=f"{series_index}:{label}:{declared}:{actual}",
                        )
                    )
            if category_declared is not None and value_declared is not None and category_declared != value_declared:
                findings.append(
                    _finding(
                        "chart_series_length_mismatch",
                        f"Chart series {series_index} has {category_declared} categories and {value_declared} values",
                        part=part_name,
                        detail=f"{series_index}:{category_declared}:{value_declared}",
                    )
                )
    return findings


def _theme_parts(path: Path) -> dict[str, bytes]:
    if not path.is_file() or not zipfile.is_zipfile(path):
        return {}
    with zipfile.ZipFile(path) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("ppt/theme/theme") and name.endswith(".xml")
        }


def _inspect_theme_preservation(path: Path, original_path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    output_themes = _theme_parts(path)
    original_themes = _theme_parts(original_path)
    for part_name, payload in sorted(original_themes.items()):
        if part_name not in output_themes:
            findings.append(_finding("template_theme_missing", f"Template theme part is missing: {part_name}", part=part_name, detail=part_name))
        elif output_themes[part_name] != payload:
            findings.append(_finding("template_theme_changed", f"Template theme part changed byte-for-byte: {part_name}", part=part_name, detail=part_name))
    return findings


def _inspect(path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not path.is_file() or not zipfile.is_zipfile(path):
        return [_finding("invalid_pptx_zip", f"PPTX is not a readable ZIP package: {path}", detail=str(path))]
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            for name, count in Counter(names).items():
                if count > 1:
                    findings.append(_finding("duplicate_zip_entry", f"ZIP entry {name} occurs {count} times", part=name, detail=name))
            corrupt = archive.testzip()
            if corrupt:
                findings.append(_finding("zip_crc_error", f"ZIP CRC validation failed for {corrupt}", part=corrupt, detail=corrupt))
            entries = {name: archive.read(name) for name in names if not name.endswith("/")}
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        return [_finding("invalid_pptx_zip", f"PPTX ZIP package could not be read: {error}", detail=type(error).__name__)]

    for part in sorted(REQUIRED_PARTS - set(entries)):
        findings.append(_finding("missing_required_part", f"Required PPTX package part is missing: {part}", part=part, detail=part))
    for name, payload in sorted(entries.items()):
        if not (name.endswith(".xml") or name.endswith(".rels")):
            continue
        try:
            ET.fromstring(payload)
        except ET.ParseError as error:
            findings.append(_finding("malformed_xml", f"XML is malformed: {error}", part=name, detail=name))

    findings.extend(_inspect_content_types(entries))
    relationship_findings, records_by_path = _inspect_relationships(entries)
    findings.extend(relationship_findings)
    findings.extend(_inspect_presentation(entries, records_by_path))
    findings.extend(_inspect_relationship_references(entries, records_by_path))
    findings.extend(_inspect_orphan_package_parts(entries, records_by_path))
    findings.extend(_inspect_empty_slide_placeholders(entries))
    findings.extend(_inspect_charts(entries))
    return findings


def inspect_package(pptx_path: str | Path, original_pptx: str | Path | None = None) -> dict[str, Any]:
    """Validate OPC/PPTX package integrity and identify template-inherited findings."""

    path = Path(pptx_path).resolve()
    findings = _inspect(path)
    baseline_findings: list[dict[str, Any]] = []
    original_path: Path | None = None
    if original_pptx is not None:
        original_path = Path(original_pptx).resolve()
        baseline_findings = _inspect(original_path)
        findings.extend(_inspect_theme_preservation(path, original_path))
    baseline_fingerprints = {item["_fingerprint"] for item in baseline_findings}
    for item in findings:
        item["inherited_from_original"] = item["_fingerprint"] in baseline_fingerprints
        item.pop("_fingerprint", None)
    for item in baseline_findings:
        item.pop("_fingerprint", None)
    blocking = [item for item in findings if item["severity"] == "blocking"]
    inherited_count = sum(1 for item in findings if item["inherited_from_original"])
    return {
        "schema_version": "0.11-mvp.4",
        "status": "PASS" if not blocking else "FAIL",
        "pptx": str(path),
        "original": str(original_path) if original_path else None,
        "summary": {
            "finding_count": len(findings),
            "blocking_count": len(blocking),
            "inherited_count": inherited_count,
            "regression_count": len(findings) - inherited_count,
            "baseline_finding_count": len(baseline_findings),
        },
        "findings": findings,
    }
