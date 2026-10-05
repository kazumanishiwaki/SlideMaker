from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
sys.path.insert(0, str(ENGINE))

from analyze_ppt import analyze as analyze_ppt
from compose_deck import compose
from render_source import render_pptx
from validate_output import validate
from helpers import write_json

EXAMPLE = Path(__file__).resolve().parent
WORK = EXAMPLE / ".work"


def prepare_project() -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    for rel in [
        "inputs", "analysis", "planning/slide_plans", "render/layout_plans",
        "render/source_renders", "render/generated_assets", "qa", "decisions",
        "state", "output",
    ]:
        (WORK / rel).mkdir(parents=True, exist_ok=True)

    shutil.copy2(ROOT / "examples/test-case/inputs/source.pptx", WORK / "inputs/source.pptx")
    shutil.copy2(ROOT / "examples/test-case/design.md", WORK / "inputs/design.md")
    analyze_ppt(WORK / "inputs/source.pptx", WORK / "analysis")
    render_pptx(WORK / "inputs/source.pptx", WORK / "render/source_renders")

    deck = {
        "schema_version": "0.1",
        "deck": {"goal": "レイアウト意図の検証", "audience": "実装レビュー"},
        "slides": [
            {
                "slide_id": "OUT-S001", "order": 1, "role": "statement",
                "primary_message": "素材が揃えば、最短即日で公開可能。",
                "content_units": ["DEMO-STATEMENT"], "status": "APPROVED",
            },
            {
                "slide_id": "OUT-S002", "order": 2, "role": "four_items",
                "primary_message": "公開後も、主要設定を担当者が変更できる。",
                "content_units": ["DEMO-FOUR-ITEMS"], "status": "APPROVED",
            },
        ],
        "status": "APPROVED",
    }
    matches = {
        "schema_version": "0.1",
        "slides": [
            {
                "slide_id": "OUT-S001",
                "selected": {
                    "source_slide_id": "SRC-S002", "page_number": 2,
                    "recommended_mode": "RECOMPOSE",
                },
            },
            {
                "slide_id": "OUT-S002",
                "selected": {
                    "source_slide_id": "SRC-S015", "page_number": 15,
                    "recommended_mode": "RECOMPOSE",
                },
            },
        ],
        "status": "APPROVED",
    }
    write_json(WORK / "planning/deck_plan.json", deck)
    write_json(WORK / "planning/slide_matching.json", matches)

    statement = {
        "schema_version": "0.1",
        "slide_id": "OUT-S001",
        "source_slide_id": "SRC-S002",
        "adaptation_mode": "RECOMPOSE",
        "composer_support": "layout_engine",
        "content_blocks": [],
        "source_object_mutations": [],
        "fill_policy": {
            "mode": "intentional_whitespace",
            "source": "system",
            "reason": [
                "一つの強い訴求を印象づけるページ",
                "補足は条件注記のみで、情報を追加すると主張が弱くなる",
            ],
            "preserve_empty_zones": True,
        },
        "layout_request": {
            "family": "statement",
            "density": "airy",
            "title": "素材が揃えば、最短即日で公開可能。",
            "subtitle": "キャンペーン素材・規約・実施条件が確定している場合。",
            "title_font_pt": 50,
            "subtitle_font_pt": 23,
            "clear_region_object_ids": ["SRC-S002-O004", "SRC-S002-O005", "SRC-S002-O006"],
            "style_source_object_ids": {
                "title": "SRC-S002-O005", "subtitle": "SRC-S002-O006",
            },
        },
        "status": "APPROVED",
    }
    grid = {
        "schema_version": "0.1",
        "slide_id": "OUT-S002",
        "source_slide_id": "SRC-S015",
        "adaptation_mode": "RECOMPOSE",
        "composer_support": "layout_engine",
        "content_blocks": [],
        "source_object_mutations": [],
        "fill_policy": {
            "mode": "content_filled",
            "source": "system",
            "reason": [
                "4領域を同時に比較・把握するページ",
                "一覧性を優先し、意味のない空白象限を残さない",
            ],
            "preserve_empty_zones": False,
        },
        "layout_request": {
            "family": "grid",
            "density": "medium_low",
            "title": "公開後も、主要設定を担当者が変更できる",
            "subtitle": "管理画面から変更できる4つの領域",
            "items": [
                {"number": "01", "title": "キャンペーン", "body": "商品・店舗・応募方法\n期間・規約・問い合わせ先"},
                {"number": "02", "title": "フォーム", "body": "追加質問・回答形式\n必須設定・レシート枚数"},
                {"number": "03", "title": "ビジュアル", "body": "テンプレート・フォント・配色\n画像・OGP・favicon"},
                {"number": "04", "title": "メール・計測", "body": "自動返信メール・GA4\nGoogle Tag Manager"},
            ],
            "clear_region_object_ids": [
                *[f"SRC-S015-O{x:03d}" for x in range(3, 16)],
                *[f"SRC-S015-O{x:03d}" for x in range(19, 34)],
            ],
            "style_source_object_ids": {
                "title": "SRC-S015-O014", "subtitle": "SRC-S015-O015",
                "item_title": "SRC-S015-O022", "item_body": "SRC-S015-O020",
                "number": "SRC-S015-O023",
            },
        },
        "status": "APPROVED",
    }
    write_json(WORK / "planning/slide_plans/OUT-S001.json", statement)
    write_json(WORK / "planning/slide_plans/OUT-S002.json", grid)
    return WORK


def build() -> dict:
    project = prepare_project()
    composed = compose(project, slide_ids=["OUT-S001", "OUT-S002"], output_name="layout-intent-poc.pptx")
    if composed["errors"]:
        raise RuntimeError(json.dumps(composed, ensure_ascii=False, indent=2))
    qa = validate(project, "output/layout-intent-poc.pptx", kind="layout_intent_poc")
    if qa["blocking_count"]:
        raise RuntimeError(json.dumps(qa, ensure_ascii=False, indent=2))

    shutil.copy2(project / "output/layout-intent-poc.pptx", EXAMPLE / "layout-intent-poc.pptx")
    shutil.copy2(project / "qa/layout-intent-poc_qa.json", EXAMPLE / "qa.json")
    shutil.copy2(project / "render/layout_plans/OUT-S001.json", EXAMPLE / "statement-layout-plan.json")
    shutil.copy2(project / "render/layout_plans/OUT-S002.json", EXAMPLE / "grid-layout-plan.json")
    trace = project / "decisions/decision_trace.jsonl"
    if trace.exists():
        shutil.copy2(trace, EXAMPLE / "decision-trace.jsonl")

    render_dir = project / "render/output_validation/layout-intent-poc"
    renders = sorted(render_dir.glob("SRC-S*.png"))
    if len(renders) >= 2:
        shutil.copy2(renders[0], EXAMPLE / "statement-intentional-whitespace.png")
        shutil.copy2(renders[1], EXAMPLE / "grid-content-filled.png")

    summary = {
        "pptx": str(EXAMPLE / "layout-intent-poc.pptx"),
        "qa": str(EXAMPLE / "qa.json"),
        "blocking_count": qa["blocking_count"],
        "warning_count": qa["warning_count"],
        "statement": json.loads((EXAMPLE / "statement-layout-plan.json").read_text(encoding="utf-8"))["quality"],
        "grid": json.loads((EXAMPLE / "grid-layout-plan.json").read_text(encoding="utf-8"))["quality"],
    }
    write_json(EXAMPLE / "summary.json", summary)
    shutil.rmtree(WORK, ignore_errors=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
