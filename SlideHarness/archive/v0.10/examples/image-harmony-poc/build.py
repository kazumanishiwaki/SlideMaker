from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = Path(__file__).resolve().parent
WORK = EXAMPLE / "workspace"
sys.path.insert(0, str(ROOT / "engine"))

from compose_deck import compose
from design_continuity import build_continuity_plans, validate_continuity
from image_pipeline import generate_images, validate_deck_image_coherence, validate_image_harmony
from state import default_project_state, save_state
from validate_output import validate


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def candidate_image(path: Path, index: int, size=(1500, 1000)) -> None:
    """Create four coherent no-text visual candidates for the offline PoC."""
    w, h = size
    bg = [(235, 226, 214), (229, 234, 230), (239, 229, 221), (228, 232, 235)][index]
    accent = [(230, 101, 49), (216, 120, 58), (234, 91, 60), (204, 111, 57)][index]
    ink = (38, 44, 42)
    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image, "RGBA")
    # Quiet left side for nearby copy; focal composition lives at center/right.
    draw.rounded_rectangle((w * .48, h * .13, w * .90, h * .88), radius=55, fill=(*ink, 238))
    draw.rounded_rectangle((w * .52, h * .19, w * .86, h * .79), radius=34, fill=(250, 249, 246, 255))
    if index == 0:  # campaign controls
        for y, ratio in [(0.30, .70), (0.43, .52), (0.56, .78), (0.69, .42)]:
            draw.rounded_rectangle((w*.57, h*y, w*(.57 + .24*ratio), h*(y+.035)), radius=12, fill=(*accent, 220))
        draw.ellipse((w*.74, h*.62, w*.81, h*.72), fill=(*accent, 215))
    elif index == 1:  # form fields
        for y in (.29, .42, .55, .68):
            draw.rounded_rectangle((w*.57, h*y, w*.81, h*(y+.07)), radius=14, outline=(*ink, 85), width=4)
        draw.ellipse((w*.58, h*.72, w*.64, h*.78), fill=(*accent, 220))
    elif index == 2:  # visual palette
        for x, y, r, color in [(.61,.34,.08,accent),(.75,.34,.07,(242,184,125)),(.61,.57,.07,(102,121,115)),(.75,.58,.09,(245,239,226))]:
            draw.ellipse((w*(x-r),h*(y-r),w*(x+r),h*(y+r)),fill=(*color,240),outline=(*ink,45),width=3)
        draw.rounded_rectangle((w*.56,h*.72,w*.80,h*.755),radius=10,fill=(*ink,100))
    else:  # measurement / analytics
        base_y=h*.73
        for j, value in enumerate((.28,.47,.38,.66,.78)):
            x0=w*(.56+j*.055)
            draw.rounded_rectangle((x0,base_y-h*value*.5,x0+w*.035,base_y),radius=8,fill=(*accent,205))
        draw.line((w*.55,h*.74,w*.83,h*.74),fill=(*ink,110),width=5)
        draw.arc((w*.69,h*.24,w*.83,h*.43),20,330,fill=(*accent,230),width=16)
    # Shared translucent accent creates a deck-level visual family.
    draw.ellipse((w*.36,h*.28,w*.58,h*.62), fill=(*accent, 55))
    image = image.filter(ImageFilter.GaussianBlur(radius=0.35))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=94)


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    for file in EXAMPLE.glob("image-candidate-*.jpg"):
        file.unlink()
    subprocess.run([
        sys.executable, str(ROOT / "engine/cli.py"), "init", "--project", str(WORK),
        "--ppt", str(ROOT / "examples/test-case/inputs/source.pptx"),
        "--manuscript", str(ROOT / "examples/test-case/inputs/manuscript.docx"),
        "--design", str(ROOT / "examples/test-case/design.md"),
    ], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(ROOT / "engine/cli.py"), "analyze", "--project", str(WORK)], check=True, stdout=subprocess.DEVNULL)

    deck = {
        "schema_version": "0.2",
        "deck": {"goal": "image harmony proof", "audience": "campaign manager"},
        "slides": [{
            "slide_id": "OUT-S001", "order": 1, "role": "photo_grid",
            "primary_message": "管理画面から変更できる4つの領域",
            "content_units": [], "importance": "primary", "optional": False, "status": "APPROVED",
        }],
    }
    visual = {"schema_version": "0.2", "slides": [{
        "slide_id": "OUT-S001",
        "visual_intent": {"purpose": "explain editable areas", "selected_type": "photo_grid", "variant": "four_images", "priority": "primary"},
        "alternatives": [],
    }]}
    matching = {"schema_version": "0.2", "slides": [{
        "slide_id": "OUT-S001",
        "candidates": [{"source_slide_id": "SRC-S008", "page_number": 8, "total_score": .94, "recommended_mode": "ADAPT"}],
        "selected": {"source_slide_id": "SRC-S008", "page_number": 8, "total_score": .94, "recommended_mode": "ADAPT"},
    }]}
    write_json(WORK / "planning/deck_plan.json", deck)
    write_json(WORK / "planning/visual_plan.json", visual)
    write_json(WORK / "planning/slide_matching.json", matching)
    continuity = build_continuity_plans(WORK)
    validate_continuity(WORK)
    recipes = continuity["image_recipes"]["recipes"]
    if len(recipes) != 4:
        raise RuntimeError(f"Expected four image recipes, got {len(recipes)}")

    # Adapt both labels and body copy. Some source text frames visually overflow
    # their declared XML boxes. Each body mutation therefore declares its whole
    # semantic row as the allowed replacement region: the image, heading, number,
    # copy, rule and card background may change together, while everything outside
    # that row remains protected by pixel-diff QA.
    text_values = {
        "SRC-S008-O003": ("CB-TITLE", "title", "管理画面から変更できる4つの領域"),
        "SRC-S008-O004": ("CB-SUB", "subtitle", "元PPTの写真枠を保ち、画像のトーンと内容を更新します。"),
        "SRC-S008-O011": ("CB-H1", "heading", "キャンペーン"),
        "SRC-S008-O013": ("CB-B1", "body", "商品、店舗、応募方法、期間、規約、問い合わせ先"),
        "SRC-S008-O017": ("CB-H2", "heading", "フォーム"),
        "SRC-S008-O019": ("CB-B2", "body", "追加質問、回答形式、必須設定、レシート枚数"),
        "SRC-S008-O023": ("CB-H3", "heading", "ビジュアル"),
        "SRC-S008-O025": ("CB-B3", "body", "テンプレート、フォント、配色、画像、OGP、favicon"),
        "SRC-S008-O029": ("CB-H4", "heading", "メール・計測"),
        "SRC-S008-O031": ("CB-B4", "body", "自動返信メール、GA4、Google Tag Manager"),
    }
    row_regions = {
        "SRC-S008-O013": ["SRC-S008-O008", "SRC-S008-O009", "SRC-S008-O010", "SRC-S008-O011", "SRC-S008-O012", "SRC-S008-O013"],
        "SRC-S008-O019": ["SRC-S008-O014", "SRC-S008-O015", "SRC-S008-O016", "SRC-S008-O017", "SRC-S008-O018", "SRC-S008-O019"],
        "SRC-S008-O025": ["SRC-S008-O020", "SRC-S008-O021", "SRC-S008-O022", "SRC-S008-O023", "SRC-S008-O024", "SRC-S008-O025"],
        "SRC-S008-O031": ["SRC-S008-O026", "SRC-S008-O027", "SRC-S008-O028", "SRC-S008-O029", "SRC-S008-O030", "SRC-S008-O031"],
    }
    content_blocks = []
    mutations = []
    for object_id, (block_id, role, value) in text_values.items():
        content_blocks.append({"id": block_id, "role": role, "source_text": "", "semantic_text": value, "render_text": value, "priority": 1 if role == "title" else 2})
        mutation={"source_object_id": object_id, "action": "replace_text", "content_block_id": block_id, "render_text": value, "reason": "Image harmony PoC content adaptation"}
        if object_id in row_regions:
            mutation["replace_region_object_ids"] = row_regions[object_id]
        mutations.append(mutation)
    for recipe in recipes:
        mutations.append({"source_object_id": recipe["target"]["source_object_id"], "action": "keep", "reason": "Image pipeline will replace this semantic content slot"})
    plan = {
        "schema_version": "0.2", "slide_id": "OUT-S001", "source_slide_id": "SRC-S008",
        "adaptation_mode": "ADAPT", "composer_support": "supported", "content_blocks": content_blocks,
        "source_object_mutations": mutations, "status": "APPROVED",
    }
    write_json(WORK / "planning/slide_plans/OUT-S001.json", plan)

    state = default_project_state()
    state["project"].update({"phase": "production", "ui_state": "sample_review", "status": "DRAFT"})
    state["slides"]["OUT-S001"] = {
        "deck_plan": "APPROVED", "visual_plan": "APPROVED", "source_match": "APPROVED",
        "slide_plan": "APPROVED", "image": "DRAFT", "layout": "APPROVED", "render": "DRAFT", "qa": "DRAFT",
    }
    save_state(WORK, state)

    # Give each recipe a semantic seed, then let the deterministic local selector
    # choose among all uploaded candidates. This demonstrates the same automatic
    # path used by the UI before an OpenAI generation fallback is considered.
    semantic_rows = [
        ("キャンペーン管理", "キャンペーンの基本情報・期間・規約を管理する抽象的な編集画面"),
        ("フォーム設定", "入力項目・必須設定・回答形式を編集するフォーム画面"),
        ("ビジュアル設定", "配色・画像・フォントを調整するビジュアル設定画面"),
        ("メール計測", "自動返信メールとアクセス計測を確認する分析画面"),
    ]
    for index, (recipe, (filename_seed, prompt_seed)) in enumerate(zip(recipes, semantic_rows)):
        recipe["prompt_seed"] = prompt_seed
        recipe["message"] = filename_seed
        candidate = WORK / f"inputs/assets/{filename_seed}.jpg"
        candidate_image(candidate, index)
        shutil.copy2(candidate, EXAMPLE / f"image-candidate-{index + 1}.jpg")
    write_json(WORK / "planning/image_recipes.json", continuity["image_recipes"])
    generated = generate_images(WORK, provider="auto", recipe_ids=[r["recipe_id"] for r in recipes])
    image_qa = validate_image_harmony(WORK, output_ids=["OUT-S001"])
    coherence = validate_deck_image_coherence(WORK)

    composed = compose(WORK, slide_ids=["OUT-S001"], output_name="image-harmony-poc.pptx")
    qa = validate(WORK, "output/image-harmony-poc.pptx", kind="image-harmony-poc")
    if qa["blocking_count"]:
        raise RuntimeError(f"PoC blocking QA: {qa['blocking_count']}")

    shutil.copy2(WORK / "output/image-harmony-poc.pptx", EXAMPLE / "image-harmony-poc.pptx")
    rendered = [Path(x) for x in qa.get("rendered_pages", [])]
    if rendered:
        shutil.copy2(rendered[0], EXAMPLE / "image-harmony-poc.png")
    manifest = json.loads((WORK / "render/generated_assets/manifest.json").read_text())
    for index, recipe in enumerate(recipes, start=1):
        asset_id = recipe.get("selected_asset_id") or manifest.get("selected_by_recipe", {}).get(recipe["recipe_id"])
        asset = next(x for x in manifest["assets"] if x["asset_id"] == asset_id)
        shutil.copy2(WORK / asset["processed_path"], EXAMPLE / f"processed-image-{index}.png")
    write_json(EXAMPLE / "image-harmony-qa.json", image_qa)
    write_json(EXAMPLE / "deck-image-coherence.json", coherence)
    shutil.copy2(WORK / "planning/image_recipes.json", EXAMPLE / "image-recipes.json")
    shutil.copy2(WORK / "planning/deck_art_direction.json", EXAMPLE / "deck-art-direction.json")
    shutil.copy2(WORK / "analysis/design_fingerprint.json", EXAMPLE / "design-fingerprint.json")
    shutil.copy2(WORK / "render/generated_assets/manifest.json", EXAMPLE / "image-asset-manifest.json")
    shutil.copy2(WORK / "render/source_renders/SRC-S008.png", EXAMPLE / "source-page-8.png")
    write_json(EXAMPLE / "output-qa.json", qa)
    for index, recipe in enumerate(recipes, start=1):
        source_rel = (recipe.get("target") or {}).get("source_media_path")
        if source_rel and (WORK / source_rel).exists():
            shutil.copy2(WORK / source_rel, EXAMPLE / f"source-reference-{index}.png")
    write_json(EXAMPLE / "summary.json", {
        "generated_assets": len(generated["results"]),
        "selection_provider": "auto_local",
        "image_harmony": {"blocking": image_qa["blocking_count"], "warnings": image_qa["warning_count"]},
        "deck_image_coherence": {"warnings": coherence["warning_count"]},
        "output_qa": {"blocking": qa["blocking_count"], "warnings": qa["warning_count"]},
        "pptx": "image-harmony-poc.pptx",
        "source_render": "source-page-8.png",
        "render": "image-harmony-poc.png",
        "recipes": "image-recipes.json",
        "manifest": "image-asset-manifest.json",
        "output_qa_file": "output-qa.json",
    })
    print(json.dumps(json.loads((EXAMPLE / "summary.json").read_text()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
