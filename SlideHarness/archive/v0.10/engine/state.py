from __future__ import annotations
from pathlib import Path
from typing import Any
from helpers import now_iso, read_json, write_json, append_jsonl

# v0.10 collapses AI-authored visual/source-match decisions into Slide Plan.
PHASES = ["deck_plan", "slide_plan", "image", "layout", "render", "qa"]
LEGACY_PHASES = ["deck_plan", "visual_plan", "source_match", "slide_plan", "image", "layout", "render", "qa"]


def default_project_state() -> dict[str, Any]:
    return {
        "schema_version": "0.10",
        "updated_at": now_iso(),
        "project": {
            "phase": "input",
            "ui_state": "input",
            "status": "DRAFT",
            "thread_id": None,
            "planning_calls": {"normal_limit": 2, "repair_limit_per_slide": 1},
        },
        "slides": {},
        "deck_harmony": "DRAFT",
    }


def _migrate_state(state: dict[str, Any]) -> dict[str, Any]:
    state = dict(state or default_project_state())
    state["schema_version"] = "0.10"
    state.setdefault("project", {})
    state["project"].setdefault("planning_calls", {"normal_limit": 2, "repair_limit_per_slide": 1})
    slides = state.setdefault("slides", {})
    for sid, row in list(slides.items()):
        row = dict(row or {})
        # If older states had separate visual/source phases, preserve the most
        # conservative status in the single Slide Plan phase.
        derived = [row.get("slide_plan"), row.get("visual_plan"), row.get("source_match")]
        if "STALE_LOCKED" in derived:
            row["slide_plan"] = "STALE_LOCKED"
        elif "LOCKED" in derived:
            row["slide_plan"] = "LOCKED"
        elif "ERROR" in derived:
            row["slide_plan"] = "ERROR"
        elif "STALE" in derived:
            row["slide_plan"] = "STALE"
        elif "REVIEW_REQUIRED" in derived:
            row["slide_plan"] = "REVIEW_REQUIRED"
        elif "APPROVED" in derived:
            row["slide_plan"] = "APPROVED"
        else:
            row.setdefault("slide_plan", "DRAFT")
        for legacy in ("visual_plan", "source_match"):
            row.pop(legacy, None)
        for phase in PHASES:
            row.setdefault(phase, "DRAFT")
        slides[sid] = row
    return state


def load_state(project: str | Path) -> dict[str, Any]:
    project = Path(project)
    return _migrate_state(read_json(project / "state/project_state.json", default_project_state()))


def save_state(project: str | Path, state: dict[str, Any]) -> None:
    state = _migrate_state(state)
    state["updated_at"] = now_iso()
    write_json(Path(project) / "state/project_state.json", state)


def ensure_slide(state: dict[str, Any], slide_id: str) -> dict[str, str]:
    state = _migrate_state(state)
    if slide_id not in state["slides"]:
        state["slides"][slide_id] = {phase: "DRAFT" for phase in PHASES}
    return state["slides"][slide_id]


def mark_stale(project: str | Path, slide_id: str, from_phase: str, reason: str = "upstream_changed") -> dict[str, Any]:
    if from_phase in {"visual_plan", "source_match"}:
        from_phase = "slide_plan"
    if from_phase not in PHASES:
        raise ValueError(f"Unknown phase: {from_phase}")
    state = load_state(project)
    slide = ensure_slide(state, slide_id)
    idx = PHASES.index(from_phase)
    for phase in PHASES[idx:]:
        if slide.get(phase) == "LOCKED":
            slide[phase] = "STALE_LOCKED"
        else:
            slide[phase] = "STALE"
    state["deck_harmony"] = "STALE"
    save_state(project, state)
    # Only meaningful state transitions are logged in compact mode.
    append_jsonl(Path(project) / "decisions/decision_trace.jsonl", {
        "decision_id": f"STATE-{now_iso()}",
        "timestamp": now_iso(),
        "phase": "state",
        "target": {"type": "slide", "id": slide_id},
        "decision_type": "mark_stale",
        "selected": from_phase,
        "reason_codes": [str(reason)],
        "origin": "system",
    })
    return state


def set_slide_status(project: str | Path, slide_id: str, phase: str, status: str) -> dict[str, Any]:
    if phase in {"visual_plan", "source_match"}:
        phase = "slide_plan"
    state = load_state(project)
    slide = ensure_slide(state, slide_id)
    slide[phase] = status
    save_state(project, state)
    return state
