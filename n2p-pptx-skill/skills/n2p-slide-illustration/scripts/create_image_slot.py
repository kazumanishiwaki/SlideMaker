#!/usr/bin/env python3
"""Create an n2p slide illustration asset folder and starter files."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


def slug_slide(slide: str, suffix: str | None) -> str:
    raw = slide.strip().lower()
    if raw.isdigit():
        name = f"slide-{int(raw):02d}"
    elif raw.startswith("slide-"):
        name = raw
    else:
        name = raw.replace(" ", "-")
    if suffix:
        safe = suffix.strip().lower().replace(" ", "-")
        name = f"{name}-{safe}"
    return name


def next_version(folder: Path) -> int:
    versions = []
    for path in folder.glob("prompt-v*.md"):
        stem = path.stem
        try:
            versions.append(int(stem.split("-v", 1)[1]))
        except (IndexError, ValueError):
            continue
    return max(versions, default=0) + 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", required=True, help="Deck name used under generated-assets/")
    parser.add_argument("--slide", required=True, help="Slide number or slide-XX")
    parser.add_argument("--title", required=True, help="Slide title")
    parser.add_argument("--intent", required=True, help="Why the illustration helps")
    parser.add_argument("--type", required=True, help="Illustration type")
    parser.add_argument("--ratio", default="auto", help="Target aspect ratio")
    parser.add_argument("--suffix", default=None, help="Optional slot suffix")
    parser.add_argument("--root", default="generated-assets", help="Generated asset root")
    args = parser.parse_args()

    folder = Path(args.root) / args.deck / slug_slide(args.slide, args.suffix)
    folder.mkdir(parents=True, exist_ok=True)

    intent_path = folder / "intent.md"
    if not intent_path.exists():
        intent_path.write_text(
            "\n".join(
                [
                    f"# {args.title}",
                    "",
                    f"Slide: {args.slide}",
                    f"Illustration type: {args.type}",
                    f"Target ratio: {args.ratio}",
                    "",
                    "## Intent",
                    "",
                    args.intent,
                    "",
                    "## Placement",
                    "",
                    "TBD after reviewing the slide layout.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    version = next_version(folder)
    prompt_path = folder / f"prompt-v{version}.md"
    if not prompt_path.exists():
        prompt_path.write_text(
            "\n".join(
                [
                    f"# Prompt v{version}",
                    "",
                    f"Slide: {args.slide} - {args.title}",
                    f"Purpose: {args.intent}",
                    f"Image type: {args.type}",
                    f"Target ratio: {args.ratio}",
                    "",
                    "## Prompt",
                    "",
                    "<write the final gpt-image2 prompt here>",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    log_path = folder / "retake-log.md"
    if not log_path.exists():
        today = dt.date.today().isoformat()
        log_path.write_text(
            "\n".join(
                [
                    "# Retake Log",
                    "",
                    f"## v{version} - {today}",
                    "",
                    "Status: planned",
                    f"Initial intent: {args.intent}",
                    f"Prompt file: prompt-v{version}.md",
                    "Generated file: TBD",
                    "Adopted in PPTX: no",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    print(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
