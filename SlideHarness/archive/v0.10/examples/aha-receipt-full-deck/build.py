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
from analyze_source import analyze as analyze_source
from compose_deck import compose
from design_continuity import build_continuity_plans, build_design_system, validate_continuity
from helpers import read_json, write_json
from image_pipeline import generate_images, validate_deck_image_coherence, validate_image_harmony
from layout_engine import plan_layouts
from planning import compile_plan_bundle, project_legacy_views, write_slide_plan_bundle
from render_source import render_selected_source_slides
from state import default_project_state, ensure_slide, save_state
from validate_deck import validate_deck
from validate_output import validate

VERSION = "0.10.0"
OUTPUT_STEM = f"aha-receipt-lite-golden-v{VERSION}"


def _dirs() -> list[str]:
    return [
        "inputs/assets", "analysis", "planning/slide_plans", "render/layout_plans",
        "render/source_renders", "render/generated_assets", "render/slide_renders",
        "qa/slide_qa", "decisions", "state", "output",
    ]


def _source_ids(project: Path, slide_no: int) -> list[str]:
    data = read_json(project / "analysis/source_slides.json", {})
    slide_id = f"SRC-S{slide_no:03d}"
    slide = next(s for s in data["slides"] if s["id"] == slide_id)
    return [o["source_object_id"] for o in slide.get("objects", []) if o.get("source_object_id")]


def _state(slide_ids: list[str]) -> dict:
    state = default_project_state()
    state["project"].update({"phase": "production", "ui_state": "page_review", "status": "APPROVED"})
    for sid in slide_ids:
        row = ensure_slide(state, sid)
        row["deck_plan"] = "APPROVED"
        row["slide_plan"] = "APPROVED"
        for phase in ("image", "layout", "render", "qa"):
            row[phase] = "DRAFT"
    state["deck_harmony"] = "DRAFT"
    return state


def _concept_image(path: Path, *, quiet_side: str, variant: int) -> None:
    """Create deterministic, text-free product visuals for local QA.

    These are not presented as OpenAI-generated production images.  They let the
    image recipe/crop/harmony path be validated without an API call.
    """
    width, height = 3328, 2080
    palettes = [
        ((242, 235, 224), (232, 118, 53), (48, 53, 50)),
        ((234, 239, 235), (226, 112, 58), (36, 43, 45)),
        ((242, 241, 236), (237, 145, 68), (38, 44, 42)),
    ]
    base, accent, ink = palettes[variant % len(palettes)]
    image = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(image, "RGBA")
    focal_left = quiet_side == "right"
    focal_x = 0.27 if focal_left else 0.73
    for radius in range(980, 90, -35):
        alpha = int(3 + 26 * (1 - radius / 980))
        cx = int(width * focal_x)
        cy = int(height * (0.50 + ((variant % 3) - 1) * 0.03))
        draw.ellipse((cx-radius, cy-radius*0.58, cx+radius, cy+radius*0.58), fill=(*accent, alpha))

    x0 = width * (0.07 if focal_left else 0.53)
    x1 = width * (0.47 if focal_left else 0.93)
    y0, y1 = height * 0.11, height * 0.89
    draw.rounded_rectangle((x0, y0, x1, y1), radius=72, fill=(*ink, 235))
    pad_x, pad_y = width * 0.034, height * 0.052
    draw.rounded_rectangle((x0+pad_x, y0+pad_y, x1-pad_x, y1-pad_y), radius=45, fill=(250, 249, 245, 255))
    inner_l, inner_r = x0 + pad_x * 1.65, x1 - pad_x * 1.65
    top = y0 + pad_y * 1.55

    if variant == 0:  # campaign dashboard
        draw.rounded_rectangle((inner_l, top, inner_r, top + height*.085), radius=18, fill=(*accent, 225))
        for idx, ratio in enumerate((0.80, 0.56, 0.89, 0.66)):
            yy = top + height * (0.145 + idx * 0.108)
            draw.rounded_rectangle((inner_l, yy, inner_l + (inner_r-inner_l)*ratio, yy+height*.032), radius=12, fill=(*ink, 70))
        for idx, value in enumerate((0.34, 0.66, 0.51, 0.79, 0.91)):
            bx = inner_l + (inner_r-inner_l)*(0.035 + idx*.19)
            by = y1 - pad_y * 1.8
            bw = (inner_r-inner_l)*0.10
            draw.rounded_rectangle((bx, by-height*.27*value, bx+bw, by), radius=10, fill=(*accent, 205))
    elif variant == 1:  # mobile form
        cx = (x0+x1)/2; cy = (y0+y1)/2
        draw.rounded_rectangle((cx-width*.13, cy-height*.30, cx+width*.13, cy+height*.30), radius=54, outline=(*ink, 135), width=8)
        draw.rounded_rectangle((cx-width*.105, cy-height*.23, cx+width*.105, cy-height*.14), radius=20, fill=(*accent, 225))
        for idx, ratio in enumerate((0.78, 0.58, 0.86, 0.68)):
            yy = cy - height*.065 + idx*height*.093
            draw.rounded_rectangle((cx-width*.10, yy, cx-width*.10 + width*.19*ratio, yy+height*.048), radius=15, fill=(*ink, 65))
        draw.ellipse((cx+width*.055, cy+height*.17, cx+width*.15, cy+height*.32), fill=(*accent, 215))
    else:  # admin settings / connected modules
        draw.rounded_rectangle((inner_l, top, inner_r, top + height*.07), radius=16, fill=(*accent, 225))
        card_w = (inner_r-inner_l)*.43
        card_h = height*.205
        for idx in range(4):
            col, row = idx % 2, idx // 2
            bx = inner_l + col * ((inner_r-inner_l)*.51)
            by = top + height*.13 + row * height*.255
            draw.rounded_rectangle((bx, by, bx+card_w, by+card_h), radius=22, fill=(255,255,255,255), outline=(*ink,55), width=4)
            draw.ellipse((bx+width*.018, by+height*.035, bx+width*.045, by+height*.078), fill=(*accent,220))
            draw.rounded_rectangle((bx+width*.058, by+height*.038, bx+card_w-width*.025, by+height*.065), radius=8, fill=(*ink,70))
            draw.rounded_rectangle((bx+width*.025, by+height*.11, bx+card_w-width*.04, by+height*.14), radius=8, fill=(*ink,45))
    image = image.filter(ImageFilter.GaussianBlur(radius=0.3))
    image.save(path, quality=95)


def _content_block(slide_id: str, message: str, chunks: list[str] | None = None) -> list[dict]:
    rendered = "\n".join(chunks or [message])
    return [{
        "id": f"CB-{slide_id}-TITLE",
        "role": "title",
        "source_text": message,
        "semantic_text": message,
        "render_text": rendered,
    }]


def _compact_plan(
    *, slide_id: str, message: str, relation: str, visual_type: str,
    source_page: int, family: str, fill: str, request: dict,
    chunks: list[str] | None = None, image: dict | None = None,
) -> dict:
    return {
        "slide_id": slide_id,
        "message": message,
        "semantic_chunks": chunks or [],
        "semantic_relation": relation,
        "visual": {"type": visual_type, "purpose": request.get("visual_purpose") or relation},
        "source": {"slide_id": f"SRC-S{source_page:03d}", "mode": "RECOMPOSE"},
        "layout": {
            "family": family,
            "density": request.get("density", "medium_low"),
            "fill_policy": fill,
            "request": request,
        },
        "content": {},
        "image": image or {},
        "runtime": {
            "content_blocks": _content_block(slide_id, message, chunks),
            "source_object_mutations": [],
            "composer_support": "layout_engine",
        },
        "status": "APPROVED",
        "origin": "human_calibrated_golden_sample",
    }


def _write_plans(project: Path) -> list[str]:
    slide_ids = [f"OUT-S{i:03d}" for i in range(1, 10)]
    deck_rows = [
        ("OUT-S001", 1, "cover", "レシートキャンペーンを、公開準備から抽選までひとつに", ["CU-001", "CU-002"]),
        ("OUT-S002", 2, "evidence", "必要な機能を標準化するから、導入しやすい", ["CU-003"]),
        ("OUT-S003", 3, "comparison", "Googleフォーム・Lite・フル版の違い", ["CU-004"]),
        ("OUT-S004", 4, "cause_effect", "20年間の知見を、導入しやすい標準機能へ", ["CU-005"]),
        ("OUT-S005", 5, "statement", "素材が揃えば、最短即日で公開可能", ["CU-006"]),
        ("OUT-S006", 6, "sequence", "公開・受付・確認・抽選を、一つの管理画面で", ["CU-007"]),
        ("OUT-S007", 7, "evidence", "公開後も、担当者が主要設定を変更できる", ["CU-008"]),
        ("OUT-S008", 8, "containment", "Liteから始め、必要な要件だけ拡張できる", ["CU-012"]),
        ("OUT-S009", 9, "closing", "デモ・見積・導入相談へ", ["CU-013"]),
    ]
    deck = {
        "schema_version": "0.10",
        "deck": {"goal": "Aha! レシート Liteの導入提案", "audience": "キャンペーン実施を検討する企業担当者"},
        "slides": [
            {"slide_id": sid, "order": order, "role": role, "primary_message": message, "content_units": units, "status": "APPROVED"}
            for sid, order, role, message, units in deck_rows
        ],
        "status": "APPROVED",
    }
    write_json(project / "planning/deck_plan.json", deck)

    def ids(n: int) -> list[str]:
        return _source_ids(project, n)

    plans = [
        _compact_plan(
            slide_id="OUT-S001", message=deck_rows[0][3], relation="statement", visual_type="conceptual_image",
            source_page=1, family="full_bleed", fill="full_bleed",
            chunks=["レシートキャンペーンを、", "公開準備から抽選までひとつに"],
            image={"recipe_id": "IMG-OUT-S001-01", "reuse_source_frame": False},
            request={
                "family": "full_bleed", "density": "medium_low",
                "title": "レシートキャンペーンを、\n公開準備から抽選までひとつに",
                "body": "Aha! レシート Lite\n必要十分な機能を、導入しやすい価格で。",
                "title_font_pt": 66, "body_font_pt": 22,
                "image_recipe_id": "IMG-OUT-S001-01", "bleed_to_slide": True,
                "reuse_source_image_frame": False,
                "overlay_position": "left", "overlay_panel": "solid", "overlay_color": "FFFFFF", "overlay_opacity": 0.91,
                "overlay_width_ratio": 0.60, "overlay_height_ratio": 0.62,
                "clear_region_object_ids": ids(1),
                "style_source_object_ids": {"title": "SRC-S001-O004", "item_body": "SRC-S001-O010"},
            },
        ),
        _compact_plan(
            slide_id="OUT-S002", message=deck_rows[1][3], relation="evidence", visual_type="screenshot",
            source_page=4, family="photo_text", fill="balanced",
            chunks=["必要な機能を標準化するから、", "導入しやすい"],
            image={"recipe_id": "IMG-OUT-S002-01", "position": "right", "text_side": "left", "ratio": 0.50, "source_object_id": "SRC-S004-O004", "reuse_source_frame": True},
            request={
                "family": "photo_text", "density": "medium_low",
                "title": "必要な機能を標準化するから、\n導入しやすい",
                "subtitle": "キャンペーン運用に必要な機能を、使いやすい形で標準搭載。",
                "body": "過剰な個別開発を抑え、\n導入コストと開始までの時間を減らします。",
                "title_font_pt": 48, "subtitle_font_pt": 21, "body_font_pt": 21,
                "image_recipe_id": "IMG-OUT-S002-01", "image_source_object_id": "SRC-S004-O004",
                "image_position": "right", "text_side": "left", "image_ratio": 0.50,
                "reuse_source_image_frame": True,
                "clear_region_object_ids": ids(4),
                "style_source_object_ids": {"title": "SRC-S004-O006", "subtitle": "SRC-S004-O007", "item_body": "SRC-S004-O011", "image": "SRC-S004-O004"},
            },
        ),
        _compact_plan(
            slide_id="OUT-S003", message=deck_rows[2][3], relation="comparison", visual_type="table",
            source_page=11, family="comparison_matrix", fill="content_filled",
            request={
                "family": "comparison_matrix", "density": "medium_low",
                "title": "Googleフォーム・Lite・フル版の違い",
                "subtitle": "○：標準対応　△：別作業が必要　×：標準では非対応",
                "title_font_pt": 42, "subtitle_font_pt": 18,
                "matrix": {
                    "row_labels": ["フォーム項目", "レシート応募", "デザイン変更", "応募検索", "データ出力", "抽選", "OCR"],
                    "columns": [
                        {"title": "Googleフォーム", "values": ["○", "△", "×", "△", "○", "△", "×"]},
                        {"title": "Lite", "values": ["○", "○", "○", "○", "○", "○", "×"]},
                        {"title": "フル版", "values": ["○", "○", "○", "○", "○", "○", "○"]},
                    ],
                    "highlight_column": 1,
                },
                "clear_region_object_ids": ids(11),
                "style_source_object_ids": {"title": "SRC-S011-O005", "subtitle": "SRC-S011-O006", "item_title": "SRC-S011-O012", "item_body": "SRC-S011-O011", "table": "SRC-S011-O010"},
            },
        ),
        _compact_plan(
            slide_id="OUT-S004", message=deck_rows[3][3], relation="cause_effect", visual_type="flow",
            source_page=14, family="process", fill="content_filled",
            request={
                "family": "process", "density": "medium_low",
                "title": "20年間の知見を、導入しやすい標準機能へ",
                "subtitle": "毎回ゼロから開発せず、よく使う運用をLiteに集約します。",
                "title_font_pt": 42, "subtitle_font_pt": 19,
                "items": [
                    {"number": "01", "title": "20年の知見", "body": "実例を蓄積"},
                    {"number": "02", "title": "機能を抽出", "body": "要件を整理"},
                    {"number": "03", "title": "Liteに標準化", "body": "標準機能に集約"},
                    {"number": "04", "title": "導入しやすく", "body": "価格と時間を抑える"},
                ],
                "clear_region_object_ids": ids(14),
                "style_source_object_ids": {"title": "SRC-S014-O004", "subtitle": "SRC-S014-O005", "item_title": "SRC-S014-O015", "item_body": "SRC-S014-O012", "number": "SRC-S014-O015"},
            },
        ),
        _compact_plan(
            slide_id="OUT-S005", message=deck_rows[4][3], relation="statement", visual_type="no_visual",
            source_page=2, family="statement", fill="intentional_whitespace",
            chunks=["素材が揃えば、", "最短即日で公開可能"],
            request={
                "family": "statement", "density": "airy",
                "title": "素材が揃えば、\n最短即日で公開可能",
                "subtitle": "素材・規約・実施条件の確定が前提。\n開始日は確認状況により異なります。",
                "title_font_pt": 62, "subtitle_font_pt": 22,
                "clear_region_object_ids": ids(2),
                "style_source_object_ids": {"title": "SRC-S002-O005", "subtitle": "SRC-S002-O006"},
            },
        ),
        _compact_plan(
            slide_id="OUT-S006", message=deck_rows[5][3], relation="sequence", visual_type="flow",
            source_page=14, family="process", fill="content_filled",
            request={
                "family": "process", "density": "medium_low",
                "title": "公開・受付・確認・抽選を、一つの管理画面で",
                "subtitle": "準備から終了後まで、同じ流れの中で進められます。",
                "title_font_pt": 42, "subtitle_font_pt": 19,
                "items": [
                    {"number": "01", "title": "公開する", "body": "LP・期間・規約を設定"},
                    {"number": "02", "title": "受け付ける", "body": "フォームと画像を受付"},
                    {"number": "03", "title": "確認する", "body": "応募状況と重複を確認"},
                    {"number": "04", "title": "抽選する", "body": "CSV出力と簡易抽選"},
                ],
                "clear_region_object_ids": ids(14),
                "style_source_object_ids": {"title": "SRC-S014-O004", "subtitle": "SRC-S014-O005", "item_title": "SRC-S014-O015", "item_body": "SRC-S014-O012", "number": "SRC-S014-O015"},
            },
        ),
        _compact_plan(
            slide_id="OUT-S007", message=deck_rows[6][3], relation="evidence", visual_type="screenshot",
            source_page=15, family="photo_text", fill="balanced",
            chunks=["公開後も、担当者が", "主要設定を変更できる"],
            image={"recipe_id": "IMG-OUT-S007-01", "position": "left", "text_side": "right", "ratio": 0.46, "source_object_id": "SRC-S015-O008", "reuse_source_frame": True},
            request={
                "family": "photo_text", "density": "medium_low",
                "title": "公開後も、担当者が\n主要設定を変更できる",
                "subtitle": "管理画面から、運用に必要な4領域を更新。",
                "body": "キャンペーン　商品・期間・規約\nフォーム　　　質問・必須設定\nビジュアル　　配色・画像・OGP\nメール・計測　自動返信・GA4・GTM",
                "title_font_pt": 44, "subtitle_font_pt": 20, "body_font_pt": 19,
                "image_recipe_id": "IMG-OUT-S007-01", "image_source_object_id": "SRC-S015-O008",
                "image_position": "left", "text_side": "right", "image_ratio": 0.46,
                "reuse_source_image_frame": True,
                "clear_region_object_ids": ids(15),
                "style_source_object_ids": {"title": "SRC-S015-O014", "subtitle": "SRC-S015-O015", "item_body": "SRC-S015-O020", "image": "SRC-S015-O008"},
            },
        ),
        _compact_plan(
            slide_id="OUT-S008", message=deck_rows[7][3], relation="containment", visual_type="flow",
            source_page=13, family="process", fill="content_filled",
            chunks=["Liteから始め、", "必要な要件だけ拡張できる"],
            request={
                "family": "process", "density": "medium_low",
                "title": "Liteから始め、必要な要件だけ拡張できる",
                "subtitle": "基本運用はLite。OCRや複雑な条件はフル版・個別対応へ。",
                "title_font_pt": 42, "subtitle_font_pt": 19,
                "items": [
                    {"number": "01", "title": "Lite 標準範囲", "body": "フォーム・画像受付\n検索・CSV・簡易抽選"},
                    {"number": "02", "title": "必要に応じて拡張", "body": "OCR・高度な条件\n外部連携・運用支援"},
                ],
                "clear_region_object_ids": ids(13),
                "style_source_object_ids": {"title": "SRC-S013-O005", "subtitle": "SRC-S013-O006", "item_title": "SRC-S013-O018", "item_body": "SRC-S013-O019", "number": "SRC-S013-O018"},
            },
        ),
        _compact_plan(
            slide_id="OUT-S009", message=deck_rows[8][3], relation="statement", visual_type="no_visual",
            source_page=17, family="closing", fill="intentional_whitespace",
            request={
                "family": "closing", "density": "airy",
                "title": "デモ・見積・導入相談へ",
                "subtitle": "キャンペーン内容と開始希望日をお知らせください。",
                "body": "必要な準備と標準範囲を整理し、開始までの流れをご案内します。",
                "title_font_pt": 52, "subtitle_font_pt": 21, "body_font_pt": 17,
                "items": [
                    {"number": "01", "title": "30分デモ", "body": "実際の画面と流れを確認"},
                    {"number": "02", "title": "見積依頼", "body": "条件に合わせて費用を整理"},
                    {"number": "03", "title": "導入相談", "body": "Lite／フル版を一緒に選定"},
                ],
                "clear_region_object_ids": ids(17),
                "style_source_object_ids": {"title": "SRC-S017-O002", "subtitle": "SRC-S017-O010", "item_title": "SRC-S017-O002", "item_body": "SRC-S017-O010", "number": "SRC-S017-O002"},
            },
        ),
    ]

    write_slide_plan_bundle(project, plans, status="APPROVED")
    project_legacy_views(project)
    build_continuity_plans(project)
    continuity = validate_continuity(project)
    if continuity.get("blocking_count"):
        raise RuntimeError(json.dumps(continuity, ensure_ascii=False, indent=2))
    compiled = compile_plan_bundle(project)
    if compiled.get("blocking_count"):
        raise RuntimeError(json.dumps(compiled, ensure_ascii=False, indent=2))
    return slide_ids


def prepare_project() -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    for rel in _dirs():
        (WORK / rel).mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "examples/test-case/inputs/source.pptx", WORK / "inputs/source.pptx")
    shutil.copy2(ROOT / "examples/test-case/inputs/manuscript.docx", WORK / "inputs/manuscript.docx")
    shutil.copy2(ROOT / "examples/test-case/design.md", WORK / "inputs/design.md")
    analyze_source(WORK / "inputs/manuscript.docx", WORK / "analysis/manuscript_analysis.json")
    analyze_ppt(WORK / "inputs/source.pptx", WORK / "analysis")
    render_selected_source_slides(WORK / "inputs/source.pptx", [1, 2, 4, 11, 13, 14, 15, 17], WORK / "render/source_renders")
    build_design_system(WORK)
    slide_ids = _write_plans(WORK)
    save_state(WORK, _state(slide_ids))
    planned = plan_layouts(WORK, slide_ids=slide_ids)
    if planned["errors"]:
        raise RuntimeError(json.dumps(planned, ensure_ascii=False, indent=2))

    asset_specs = {
        "IMG-OUT-S001-01": ("hero-campaign.jpg", "left", 1),
        "IMG-OUT-S002-01": ("standardized-operation.jpg", "left", 0),
        "IMG-OUT-S007-01": ("admin-settings.jpg", "right", 2),
    }
    manual_paths: dict[str, str] = {}
    for recipe_id, (name, quiet_side, variant) in asset_specs.items():
        path = WORK / "inputs/assets" / name
        _concept_image(path, quiet_side=quiet_side, variant=variant)
        manual_paths[recipe_id] = f"inputs/assets/{name}"
    generated = generate_images(WORK, provider="manual", recipe_ids=list(asset_specs), manual_paths=manual_paths)
    failed = [row for row in generated.get("results", []) if row.get("status") != "READY"]
    if failed:
        raise RuntimeError(json.dumps(generated, ensure_ascii=False, indent=2))
    return WORK


def _montage(slide_paths: list[Path], out: Path, *, cols: int = 3) -> None:
    thumbs = []
    for path in slide_paths:
        img = Image.open(path).convert("RGB")
        img.thumbnail((640, 360))
        canvas = Image.new("RGB", (640, 360), "white")
        canvas.paste(img, ((640-img.width)//2, (360-img.height)//2))
        thumbs.append(canvas)
    rows = (len(thumbs) + cols - 1) // cols
    montage = Image.new("RGB", (cols*640, rows*360), (245, 245, 245))
    for idx, img in enumerate(thumbs):
        montage.paste(img, ((idx % cols)*640, (idx // cols)*360))
    montage.save(out)


def build() -> dict:
    project = prepare_project()
    slide_ids = [f"OUT-S{i:03d}" for i in range(1, 10)]
    output_name = f"{OUTPUT_STEM}.pptx"
    composed = compose(project, slide_ids=slide_ids, output_name=output_name)
    compose_report = read_json(composed["report"], {})
    actual_errors = sum(len(row.get("errors") or []) for row in compose_report.get("slides", []))
    if actual_errors:
        raise RuntimeError(json.dumps({"compose": composed, "report": compose_report}, ensure_ascii=False, indent=2))

    image_qa = validate_image_harmony(project)
    image_coherence = validate_deck_image_coherence(project)
    qa = validate(project, f"output/{output_name}", kind="aha_receipt_v010_simplified")
    deck_qa = validate_deck(project)
    if qa["blocking_count"] or image_qa.get("blocking_count", 0):
        raise RuntimeError(json.dumps({"output_qa": qa, "image_qa": image_qa}, ensure_ascii=False, indent=2))

    pptx_out = EXAMPLE / output_name
    montage_out = EXAMPLE / f"{OUTPUT_STEM}-montage.png"
    shutil.copy2(project / "output" / output_name, pptx_out)
    shutil.copy2(project / "qa" / f"{OUTPUT_STEM}_qa.json", EXAMPLE / "output-qa.json")
    shutil.copy2(project / "qa/deck_harmony.json", EXAMPLE / "deck-qa.json")
    for src, dst in [
        (project / "qa/image_harmony.json", EXAMPLE / "image-harmony-qa.json"),
        (project / "qa/deck_image_coherence.json", EXAMPLE / "deck-image-coherence.json"),
        (project / "planning/image_recipes.json", EXAMPLE / "image-recipes.json"),
        (project / "render/generated_assets/manifest.json", EXAMPLE / "image-asset-manifest.json"),
        (project / "planning/slide_plans.json", EXAMPLE / "slide-plans.json"),
        (project / "qa/plan_validation.json", EXAMPLE / "plan-validation.json"),
    ]:
        if src.exists():
            shutil.copy2(src, dst)

    render_dir = project / "render/output_validation" / OUTPUT_STEM
    renders = sorted(render_dir.glob("SRC-S*.png"))
    for idx, render in enumerate(renders, 1):
        shutil.copy2(render, EXAMPLE / f"slide-{idx:02d}.png")
    if renders:
        _montage(renders, montage_out)
    for sid in slide_ids:
        source = project / f"render/layout_plans/{sid}.json"
        if source.exists():
            shutil.copy2(source, EXAMPLE / f"{sid.lower()}-layout-plan.json")

    summary = {
        "version": VERSION,
        "release_type": "simplification",
        "model_call_contract": {"normal_generation_calls": 2, "repair_call_limit_per_slide": 1},
        "deck": "Aha! レシート Lite 全9ページ",
        "pptx": str(pptx_out.relative_to(ROOT)),
        "montage": str(montage_out.relative_to(ROOT)),
        "blocking_count": qa["blocking_count"],
        "warning_count": qa["warning_count"],
        "category_counts": qa.get("category_counts", {}),
        "deck_harmony_warning_count": deck_qa.get("warning_count", 0),
        "image_blocking_count": image_qa.get("blocking_count", 0),
        "image_warning_count": image_qa.get("warning_count", 0),
        "image_coherence_warning_count": image_coherence.get("warning_count", 0),
        "slides": [],
    }
    for sid in slide_ids:
        plan = read_json(EXAMPLE / f"{sid.lower()}-layout-plan.json", {})
        summary["slides"].append({
            "slide_id": sid,
            "family": plan.get("family"),
            "renderer_group": plan.get("renderer_group"),
            "semantic_relation": plan.get("semantic_relation"),
            "fill_policy": (plan.get("fill_policy") or {}).get("mode"),
            "fit_score": (plan.get("quality") or {}).get("score"),
            "quality": (plan.get("quality") or {}).get("status"),
        })
    write_json(EXAMPLE / "summary.json", summary)
    shutil.rmtree(WORK, ignore_errors=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
