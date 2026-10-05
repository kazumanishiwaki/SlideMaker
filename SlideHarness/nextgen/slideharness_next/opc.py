from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
import posixpath


RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def relationship_part_path(part_path: str) -> str:
    item = PurePosixPath(part_path)
    return str(item.parent / "_rels" / f"{item.name}.rels")


def relationship_source_part(rels_path: str) -> str:
    if rels_path == "_rels/.rels":
        return ""
    item = PurePosixPath(rels_path)
    return str(item.parent.parent / item.name.removesuffix(".rels"))


def resolve_relationship_target(source_part: str, target: str) -> str:
    target_path = unquote(urlsplit(target).path)
    if target_path.startswith("/"):
        return posixpath.normpath(target_path).lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target_path)).lstrip("/")


def relationship_is_external(record: dict[str, str]) -> bool:
    return record["target_mode"].casefold() == "external"


def relationship_records(payload: bytes, rels_path: str) -> list[dict[str, str]]:
    root = ET.fromstring(payload)
    source = relationship_source_part(rels_path)
    output: list[dict[str, str]] = []
    for relationship in root.findall(f"{{{RELATIONSHIPS_NS}}}Relationship"):
        target_mode = relationship.get("TargetMode", "Internal")
        target = relationship.get("Target", "")
        record = {
            "id": relationship.get("Id", ""),
            "type": relationship.get("Type", ""),
            "target_mode": target_mode,
            "target": target,
            "resolved": target,
        }
        if not relationship_is_external(record):
            record["resolved"] = resolve_relationship_target(source, target)
        output.append(record)
    return output


def package_relationships(entries: dict[str, bytes], rels_path: str) -> list[dict[str, str]]:
    payload = entries.get(rels_path)
    return relationship_records(payload, rels_path) if payload is not None else []
