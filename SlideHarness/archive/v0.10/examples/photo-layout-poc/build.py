from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
EXAMPLE = Path(__file__).resolve().parent
WORK = EXAMPLE / ".work"
sys.path.insert(0, str(ENGINE))

from analyze_ppt import analyze as analyze_ppt
from compose_deck import compose
from design_continuity import build_design_system, build_continuity_plans, validate_continuity
from helpers import write_json
from image_pipeline import generate_images, validate_deck_image_coherence, validate_image_harmony
from layout_engine import plan_layouts
from render_source import render_pptx
from state import default_project_state, ensure_slide, save_state
from validate_output import validate


def _project_dirs() -> list[str]:
    return [
        "inputs/assets", "analysis", "planning/slide_plans", "render/layout_plans",
        "render/source_renders", "render/generated_assets", "render/slide_renders",
        "qa/slide_qa", "decisions", "state", "output",
    ]


def _clear_ids(slide: int, values: list[int]) -> list[str]:
    return [f"SRC-S{slide:03d}-O{value:03d}" for value in values]


def _concept_image(path: Path, *, quiet_side: str, variant: int) -> None:
    """Create a coherent no-text editorial visual for an offline, deterministic PoC."""
    width, height = 3328, 2080
    base = [(239, 232, 222), (229, 235, 231)][variant % 2]
    accent = [(236, 122, 57), (225, 104, 54)][variant % 2]
    ink = (44, 49, 47)
    image = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(image, "RGBA")

    # A soft spatial gradient makes the image feel photographic without adding text.
    for radius in range(900, 80, -30):
        alpha = int(2 + 30 * (1 - radius / 900))
        center_x = int(width * (0.73 if quiet_side == "left" else 0.27))
        center_y = int(height * 0.50)
        draw.ellipse(
            (center_x - radius, center_y - radius * 0.62,
             center_x + radius, center_y + radius * 0.62),
            fill=(*accent, alpha),
        )

    focal_left = quiet_side == "right"
    x0 = width * (0.08 if focal_left else 0.54)
    x1 = width * (0.46 if focal_left else 0.92)
    y0, y1 = height * 0.14, height * 0.88
    draw.rounded_rectangle((x0, y0, x1, y1), radius=72, fill=(*ink, 232))
    pad_x, pad_y = width * 0.035, height * 0.055
    draw.rounded_rectangle((x0 + pad_x, y0 + pad_y, x1 - pad_x, y1 - pad_y), radius=45, fill=(250, 249, 245, 255))

    if variant == 0:
        # Campaign management dashboard motif.
        inner_l = x0 + pad_x * 1.8
        inner_r = x1 - pad_x * 1.8
        top = y0 + pad_y * 1.9
        draw.rounded_rectangle((inner_l, top, inner_r, top + height * .085), radius=18, fill=(*accent, 225))
        for idx, ratio in enumerate((0.76, 0.53, 0.84, 0.62)):
            yy = top + height * (0.14 + idx * 0.12)
            draw.rounded_rectangle((inner_l, yy, inner_l + (inner_r-inner_l) * ratio, yy + height*.036), radius=12, fill=(*ink, 72))
        for idx, value in enumerate((0.30, 0.58, 0.43, 0.74, 0.88)):
            bx = inner_l + (inner_r-inner_l) * (0.04 + idx*0.19)
            by = y1 - pad_y * 2.0
            bw = (inner_r-inner_l) * 0.10
            draw.rounded_rectangle((bx, by-height*.30*value, bx+bw, by), radius=10, fill=(*accent, 205))
    else:
        # Mobile-first experience motif with layered screens and a circular focal cue.
        cx = (x0+x1)/2
        cy = (y0+y1)/2
        draw.rounded_rectangle((cx-width*.13, cy-height*.28, cx+width*.13, cy+height*.28), radius=54, outline=(*ink, 135), width=8)
        draw.rounded_rectangle((cx-width*.105, cy-height*.21, cx+width*.105, cy-height*.12), radius=20, fill=(*accent, 220))
        for idx in range(3):
            yy = cy - height*.04 + idx*height*.105
            draw.rounded_rectangle((cx-width*.10, yy, cx+width*.08, yy+height*.055), radius=15, fill=(*ink, 65))
        draw.ellipse((cx+width*.07, cy+height*.14, cx+width*.16, cy+height*.29), fill=(*accent, 210))

    image = image.filter(ImageFilter.GaussianBlur(radius=0.35))
    image.save(path, quality=94)


def _state_for(slides: list[str]) -> dict:
    state = default_project_state()
    state["project"].update({"phase": "production", "ui_state": "sample_review", "status": "APPROVED"})
    for slide_id in slides:
        row = ensure_slide(state, slide_id)
        for phase in ("deck_plan", "visual_plan", "source_match", "slide_plan"):
            row[phase] = "APPROVED"
        row["image"] = "DRAFT"
        row["layout"] = "DRAFT"
        row["render"] = "DRAFT"
        row["qa"] = "DRAFT"
    state["deck_harmony"] = "DRAFT"
    return state


def prepare_project() -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    for rel in _project_dirs():
        (WORK / rel).mkdir(parents=True, exist_ok=True)

    shutil.copy2(ROOT / "examples/test-case/inputs/source.pptx", WORK / "inputs/source.pptx")
    shutil.copy2(ROOT / "examples/test-case/design.md", WORK / "inputs/design.md")
    analyze_ppt(WORK / "inputs/source.pptx", WORK / "analysis")
    build_design_system(WORK)
    render_pptx(WORK / "inputs/source.pptx", WORK / "render/source_renders")

    slide_ids = [f"OUT-S{idx:03d}" for idx in range(1, 6)]
    deck = {
        "schema_version": "0.2",
        "deck": {"goal": "Photo-aware Layout Engineの実レンダリング検証", "audience": "実装レビュー"},
        "slides": [
            {"slide_id": "OUT-S001", "order": 1, "role": "two_column", "primary_message": "必要な範囲に合わせて、Liteとフル版を選べる", "content_units": ["POC-TWO"], "status": "APPROVED"},
            {"slide_id": "OUT-S002", "order": 2, "role": "photo_text", "primary_message": "スマートフォンで見やすく、操作しやすい", "content_units": ["POC-PHOTO"], "status": "APPROVED"},
            {"slide_id": "OUT-S003", "order": 3, "role": "full_bleed", "primary_message": "公開から抽選までを、ひとつの管理画面で", "content_units": ["POC-BLEED"], "status": "APPROVED"},
            {"slide_id": "OUT-S004", "order": 4, "role": "comparison_matrix", "primary_message": "主要機能を、運用に合わせて比較できる", "content_units": ["POC-MATRIX"], "status": "APPROVED"},
            {"slide_id": "OUT-S005", "order": 5, "role": "relationship", "primary_message": "管理画面を中心に、運用全体がつながる", "content_units": ["POC-RELATION"], "status": "APPROVED"},
        ],
        "status": "APPROVED",
    }
    visual = {
        "schema_version": "0.2",
        "slides": [
            {"slide_id": "OUT-S001", "visual_intent": {"selected_type": "comparison", "purpose": "compare_options"}},
            {"slide_id": "OUT-S002", "visual_intent": {"selected_type": "photo", "purpose": "show_mobile_experience"}},
            {"slide_id": "OUT-S003", "visual_intent": {"selected_type": "conceptual_image", "purpose": "show_integrated_operation"}},
            {"slide_id": "OUT-S004", "visual_intent": {"selected_type": "table", "purpose": "compare_features"}},
            {"slide_id": "OUT-S005", "visual_intent": {"selected_type": "relationship_diagram", "purpose": "explain_system_relationship"}},
        ],
        "status": "APPROVED",
    }
    matches = {
        "schema_version": "0.2",
        "slides": [
            {"slide_id": "OUT-S001", "selected": {"source_slide_id": "SRC-S013", "page_number": 13, "recommended_mode": "RECOMPOSE"}},
            {"slide_id": "OUT-S002", "selected": {"source_slide_id": "SRC-S004", "page_number": 4, "recommended_mode": "RECOMPOSE"}},
            {"slide_id": "OUT-S003", "selected": {"source_slide_id": "SRC-S004", "page_number": 4, "recommended_mode": "RECOMPOSE"}},
            {"slide_id": "OUT-S004", "selected": {"source_slide_id": "SRC-S011", "page_number": 11, "recommended_mode": "RECOMPOSE"}},
            {"slide_id": "OUT-S005", "selected": {"source_slide_id": "SRC-S013", "page_number": 13, "recommended_mode": "RECOMPOSE"}},
        ],
        "status": "APPROVED",
    }
    write_json(WORK / "planning/deck_plan.json", deck)
    write_json(WORK / "planning/visual_plan.json", visual)
    write_json(WORK / "planning/slide_matching.json", matches)
    build_continuity_plans(WORK)
    validate_continuity(WORK)

    common_13 = _clear_ids(13, [3,4,5,6,10,11,12,13,14,15,16,17,18,19,20,21,22])
    common_4 = _clear_ids(4, [3,5,6,7,11,12])
    common_11 = _clear_ids(11, [3,4,5,6,10,11,12,13,14])

    plans = [
        {
            "schema_version": "0.3", "slide_id": "OUT-S001", "source_slide_id": "SRC-S013",
            "adaptation_mode": "RECOMPOSE", "composer_support": "layout_engine",
            "content_blocks": [], "source_object_mutations": [],
            "fill_policy": {"mode": "content_filled", "source": "system", "reason": ["二つの選択肢を同じ強さで比較する"], "preserve_empty_zones": False},
            "layout_request": {
                "family": "two_column", "density": "medium_low",
                "title": "必要な範囲に合わせて、Liteとフル版を選べる",
                "subtitle": "標準機能で始めるか、高度な要件まで対応するか。",
                "items": [
                    {"title": "Aha! レシート Lite", "body": "標準機能ですぐに開始\nシンプルな運用に対応\n導入コストを抑えやすい", "style": "card"},
                    {"title": "Aha! レシート", "body": "OCR・高度なカスタマイズ\n複雑な応募条件に対応\n外部連携や運用支援も相談可能", "style": "card"},
                ],
                "clear_region_object_ids": common_13,
                "style_source_object_ids": {"title": "SRC-S013-O005", "subtitle": "SRC-S013-O006", "item_title": "SRC-S013-O018", "item_body": "SRC-S013-O019"},
            }, "status": "APPROVED",
        },
        {
            "schema_version": "0.3", "slide_id": "OUT-S002", "source_slide_id": "SRC-S004",
            "adaptation_mode": "RECOMPOSE", "composer_support": "layout_engine",
            "content_blocks": [], "source_object_mutations": [],
            "fill_policy": {"mode": "balanced", "source": "system", "reason": ["写真と説明を同時に理解できる比率にする"], "preserve_empty_zones": False},
            "layout_request": {
                "family": "photo_text", "density": "medium_low",
                "title": "スマートフォンで見やすく、操作しやすい",
                "subtitle": "画面幅に合わせて、文字・画像・フォームを自動調整。",
                "body": "応募者が迷いにくい画面設計で、入力から送信までをスムーズにつなぎます。",
                "image_recipe_id": "IMG-OUT-S002-01", "image_source_object_id": "SRC-S004-O004",
                "image_position": "auto", "text_side": "right", "image_ratio": 0.53,
                "reuse_source_image_frame": True,
                "clear_region_object_ids": common_4,
                "style_source_object_ids": {"title": "SRC-S004-O006", "subtitle": "SRC-S004-O007", "item_body": "SRC-S004-O011", "image": "SRC-S004-O004"},
            }, "status": "APPROVED",
        },
        {
            "schema_version": "0.3", "slide_id": "OUT-S003", "source_slide_id": "SRC-S004",
            "adaptation_mode": "RECOMPOSE", "composer_support": "layout_engine",
            "content_blocks": [], "source_object_mutations": [],
            "fill_policy": {"mode": "full_bleed", "source": "system", "reason": ["統合された運用体験を一枚の主役ビジュアルで示す"], "preserve_empty_zones": False},
            "layout_request": {
                "family": "full_bleed", "density": "medium_low",
                "title": "公開から抽選までを\nひとつの管理画面で",
                "title_font_pt": 36,
                "body": "準備から終了後まで、同じ場所で流れを見失わずに進めます。",
                "image_recipe_id": "IMG-OUT-S003-01", "image_source_object_id": "SRC-S004-O004",
                "reuse_source_image_frame": True, "bleed_to_slide": True,
                "overlay_position": "left", "overlay_panel": "solid", "overlay_color": "FFFFFF", "overlay_opacity": 0.88,
                "overlay_width_ratio": 0.44, "overlay_height_ratio": 0.58,
                "clear_region_object_ids": common_4,
                "style_source_object_ids": {"title": "SRC-S004-O006", "item_body": "SRC-S004-O011", "image": "SRC-S004-O004"},
            }, "status": "APPROVED",
        },
        {
            "schema_version": "0.3", "slide_id": "OUT-S004", "source_slide_id": "SRC-S011",
            "adaptation_mode": "RECOMPOSE", "composer_support": "layout_engine",
            "content_blocks": [], "source_object_mutations": [],
            "fill_policy": {"mode": "content_filled", "source": "system", "reason": ["機能差を一覧で読み取れるようにする"], "preserve_empty_zones": False},
            "layout_request": {
                "family": "comparison_matrix", "density": "medium_low",
                "title": "主要機能の比較",
                "subtitle": "○：標準対応　△：別作業が必要　×：標準機能では非対応",
                "matrix": {
                    "row_labels": ["フォーム項目", "レシート応募", "デザイン変更", "応募検索", "データ出力", "抽選", "OCR"],
                    "columns": [
                        {"title": "Googleフォーム", "values": ["○", "△", "×", "△", "○", "△", "×"]},
                        {"title": "Lite", "values": ["○", "○", "○", "○", "○", "○", "×"]},
                        {"title": "フル版", "values": ["○", "○", "○", "○", "○", "○", "○"]},
                    ], "highlight_column": 1,
                },
                "clear_region_object_ids": common_11,
                "style_source_object_ids": {"title": "SRC-S011-O005", "subtitle": "SRC-S011-O006", "item_title": "SRC-S011-O012", "item_body": "SRC-S011-O011", "table": "SRC-S011-O010"},
            }, "status": "APPROVED",
        },
        {
            "schema_version": "0.3", "slide_id": "OUT-S005", "source_slide_id": "SRC-S013",
            "adaptation_mode": "RECOMPOSE", "composer_support": "layout_engine",
            "content_blocks": [], "source_object_mutations": [],
            "fill_policy": {"mode": "content_filled", "source": "system", "reason": ["中心機能と周辺工程の関係を一目で示す"], "preserve_empty_zones": False},
            "layout_request": {
                "family": "relationship", "density": "medium_low",
                "title": "管理画面を中心に、運用全体がつながる",
                "subtitle": "公開・受付・確認・抽選を一元管理。",
                "nodes": [
                    {"id": "CENTER", "title": "管理画面", "body": "一元管理"},
                    {"id": "LP", "title": "公開", "body": "LP・期間・規約"},
                    {"id": "ENTRY", "title": "受付", "body": "フォーム・画像"},
                    {"id": "CHECK", "title": "確認", "body": "応募・重複候補"},
                    {"id": "DRAW", "title": "抽選", "body": "CSV・簡易抽選"},
                ],
                "edges": [{"from": "CENTER", "to": node} for node in ["LP", "ENTRY", "CHECK", "DRAW"]],
                "center_node_id": "CENTER",
                "clear_region_object_ids": common_13,
                "style_source_object_ids": {"title": "SRC-S013-O005", "subtitle": "SRC-S013-O006", "item_title": "SRC-S013-O018", "item_body": "SRC-S013-O019", "panel": "SRC-S013-O003"},
            }, "status": "APPROVED",
        },
    ]
    for plan in plans:
        write_json(WORK / f"planning/slide_plans/{plan['slide_id']}.json", plan)

    save_state(WORK, _state_for(slide_ids))
    planned = plan_layouts(WORK, slide_ids=slide_ids)
    if planned["errors"]:
        raise RuntimeError(json.dumps(planned, ensure_ascii=False, indent=2))

    # Create two deterministic assets, then pass them through the real image pipeline.
    photo_asset = WORK / "inputs/assets/mobile-experience.jpg"
    bleed_asset = WORK / "inputs/assets/integrated-management.jpg"
    _concept_image(photo_asset, quiet_side="right", variant=1)
    _concept_image(bleed_asset, quiet_side="left", variant=0)
    import gc
    generated_rows = []
    for recipe_id, asset_path in (
        ("IMG-OUT-S002-01", "inputs/assets/mobile-experience.jpg"),
        ("IMG-OUT-S003-01", "inputs/assets/integrated-management.jpg"),
    ):
        generated = generate_images(
            WORK, provider="manual", recipe_ids=[recipe_id],
            manual_paths={recipe_id: asset_path},
        )
        generated_rows.extend(generated.get("results", []))
        gc.collect()
    if any(row.get("status") != "READY" for row in generated_rows):
        raise RuntimeError(json.dumps({"results": generated_rows}, ensure_ascii=False, indent=2))
    return WORK


def build() -> dict:
    project = prepare_project()
    slide_ids = [f"OUT-S{idx:03d}" for idx in range(1, 6)]
    composed = compose(project, slide_ids=slide_ids, output_name="photo-layout-poc.pptx")
    compose_report = json.loads(Path(composed["report"]).read_text(encoding="utf-8"))
    actual_compose_errors = sum(len(row.get("errors") or []) for row in compose_report.get("slides", []))
    if actual_compose_errors:
        raise RuntimeError(json.dumps({**composed, "actual_errors": actual_compose_errors}, ensure_ascii=False, indent=2))

    image_qa = validate_image_harmony(project)
    coherence = validate_deck_image_coherence(project)
    qa = validate(project, "output/photo-layout-poc.pptx", kind="photo_layout_poc")
    if image_qa["blocking_count"] or qa["blocking_count"]:
        raise RuntimeError(json.dumps({"image_qa": image_qa, "output_qa": qa}, ensure_ascii=False, indent=2))

    shutil.copy2(project / "output/photo-layout-poc.pptx", EXAMPLE / "photo-layout-poc.pptx")
    shutil.copy2(project / "qa/photo-layout-poc_qa.json", EXAMPLE / "output-qa.json")
    shutil.copy2(project / "qa/image_harmony.json", EXAMPLE / "image-harmony-qa.json")
    shutil.copy2(project / "qa/deck_image_coherence.json", EXAMPLE / "deck-image-coherence.json")
    shutil.copy2(project / "planning/image_recipes.json", EXAMPLE / "image-recipes.json")
    shutil.copy2(project / "render/generated_assets/manifest.json", EXAMPLE / "image-asset-manifest.json")

    for slide_id in slide_ids:
        src = project / f"render/layout_plans/{slide_id}.json"
        if src.exists():
            shutil.copy2(src, EXAMPLE / f"{slide_id.lower()}-layout-plan.json")

    render_dir = project / "render/output_validation/photo-layout-poc"
    renders = sorted(render_dir.glob("SRC-S*.png"))
    for index, render in enumerate(renders, start=1):
        shutil.copy2(render, EXAMPLE / f"slide-{index:02d}.png")

    summary = {
        "version": "0.6.0",
        "families": ["two_column", "photo_text", "full_bleed", "comparison_matrix", "relationship"],
        "pptx": "examples/photo-layout-poc/photo-layout-poc.pptx",
        "blocking_count": qa["blocking_count"],
        "warning_count": qa["warning_count"],
        "image_blocking_count": image_qa["blocking_count"],
        "image_warning_count": image_qa["warning_count"],
        "deck_image_blocking_count": coherence.get("blocking_count", 0),
        "deck_image_warning_count": coherence["warning_count"],
        "slides": [],
    }
    for slide_id in slide_ids:
        plan = json.loads((EXAMPLE / f"{slide_id.lower()}-layout-plan.json").read_text(encoding="utf-8"))
        summary["slides"].append({
            "slide_id": slide_id,
            "family": plan.get("family"),
            "fill_policy": (plan.get("fill_policy") or {}).get("mode"),
            "fit_score": (plan.get("quality") or {}).get("score"),
            "quality": (plan.get("quality") or {}).get("status"),
            "image_lineage": plan.get("image_lineage"),
        })
    write_json(EXAMPLE / "summary.json", summary)
    shutil.rmtree(WORK, ignore_errors=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
