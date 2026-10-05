from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class ThemeTokens:
    primary: str = "2F5597"
    secondary: str = "70AD47"
    accent: str = "ED7D31"
    background: str = "FFFFFF"
    surface: str = "F4F6F8"
    text: str = "1F2937"
    muted_text: str = "667085"
    heading_font: str = "Aptos Display"
    body_font: str = "Aptos"


@dataclass(frozen=True)
class SourceFile:
    source_id: str
    path: str
    filename: str
    media_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SourceUnit:
    unit_id: str
    source_id: str
    order: int
    kind: str
    section_path: list[str]
    source_text: str
    semantic_text: str
    classification: str
    facts: list[str] = field(default_factory=list)
    required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceBundle:
    schema_version: str
    files: list[SourceFile]
    units: list[SourceUnit]
    assets: list[dict[str, Any]] = field(default_factory=list)
    ocr_report: dict[str, Any] = field(default_factory=lambda: {"status": "PASS", "files": [], "findings": []})

    def manifest_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "files": [asdict(item) for item in self.files]}

    def units_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "units": [asdict(item) for item in self.units]}

    def assets_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "assets": self.assets}


@dataclass(frozen=True)
class ChromeElement:
    source_slide_index: int
    source_shape_index: int
    kind: str
    x: float
    y: float
    w: float
    h: float
    occurrence_ratio: float


@dataclass(frozen=True)
class LayoutEvidence:
    index: int
    name: str
    shape_count: int
    placeholder_count: int
    title_slots: int
    body_slots: int
    score_as_canvas: float


@dataclass(frozen=True)
class TemplateSystem:
    schema_version: str
    template_path: str
    template_sha256: str
    slide_width_in: float
    slide_height_in: float
    slide_count: int
    tokens: ThemeTokens
    chrome: list[ChromeElement] = field(default_factory=list)
    layouts: list[LayoutEvidence] = field(default_factory=list)
    pattern_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SlideSpec:
    slide_id: str
    title: str
    message: str
    recipe: str = "auto"
    source_unit_ids: list[str] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any], index: int) -> "SlideSpec":
        return cls(
            slide_id=str(value.get("slide_id") or f"S{index + 1:03d}"),
            title=str(value.get("title") or ""),
            message=str(value.get("message") or ""),
            recipe=str(value.get("recipe") or "auto"),
            source_unit_ids=[str(item) for item in value.get("source_unit_ids", [])],
            content=dict(value.get("content") or {}),
        )


@dataclass(frozen=True)
class DeckSpec:
    title: str
    slides: list[SlideSpec]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "DeckSpec":
        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        slides = [SlideSpec.from_dict(item, index) for index, item in enumerate(payload.get("slides", []))]
        if not slides:
            raise ValueError("deck spec must contain at least one slide")
        return cls(
            title=str(payload.get("title") or source.stem),
            slides=slides,
            metadata=dict(payload.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlannedElement:
    element_id: str
    kind: str
    x: float
    y: float
    w: float
    h: float
    role: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LayoutPlan:
    slide_id: str
    recipe: str
    source_unit_ids: list[str]
    elements: list[PlannedElement]
    expected_item_count: int
    asset_requests: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
