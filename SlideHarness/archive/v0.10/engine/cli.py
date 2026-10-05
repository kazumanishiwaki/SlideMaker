from __future__ import annotations
import argparse
import shutil
import re
import os
from pathlib import Path

from helpers import now_iso, sha256_file, write_json, read_json
from analyze_source import analyze as analyze_source
from analyze_ppt import analyze as analyze_ppt
from render_source import render_pptx
from state import default_project_state, save_state, load_state, mark_stale
from seed_plan import seed as seed_plan
from build_skeleton import build as build_skeleton
from compose_deck import compose as compose_deck
from validate_output import validate as validate_output
from validate_deck import validate_deck
from design_continuity import build_design_system, build_continuity_plans, validate_continuity
from image_pipeline import generate_images, select_image_asset, update_image_recipe, validate_image_harmony, validate_deck_image_coherence
from layout_engine import plan_layouts
from feedback import apply_feedback
from planning import compile_plan_bundle, project_legacy_views


def init_project(args):
    root = Path(args.project).resolve()
    for rel in [
        "inputs/assets", "analysis", "planning/slide_plans", "render/layout_plans",
        "render/generated_assets", "render/slide_renders", "render/source_renders",
        "qa/slide_qa", "decisions", "state", "output"
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)
    mappings = []
    for kind, src, name in [
        ("pptx", args.ppt, "source.pptx"),
        ("manuscript", args.manuscript, "manuscript" + Path(args.manuscript).suffix.lower()),
        ("design", args.design, "design.md")
    ]:
        srcp = Path(src).resolve()
        dst = root / "inputs" / name
        shutil.copy2(srcp, dst)
        mappings.append({"type": kind, "path": str(dst), "sha256": sha256_file(dst), "immutable": True})
    for idx, src in enumerate(args.asset or [], start=1):
        srcp = Path(src).resolve()
        safe_base = re.sub(r"[^0-9A-Za-z._-]+", "-", srcp.name).strip("-") or f"asset-{idx:03d}{srcp.suffix.lower()}"
        dst = root / "inputs/assets" / f"{idx:03d}-{safe_base}"
        shutil.copy2(srcp, dst)
        mappings.append({"type": "asset", "path": str(dst), "sha256": sha256_file(dst), "immutable": True, "original_name": srcp.name})
    project = {
        "schema_version": "0.10",
        "project_id": root.name,
        "name": root.name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "review_mode": "detailed",
        "inputs": mappings,
    }
    write_json(root / "project.json", project)
    save_state(root, default_project_state())
    write_json(root / "state/dependency_graph.json", {
        "schema_version": "0.10",
        "template": [
            "content_unit -> deck_plan -> slide_plan -> image -> layout -> render -> qa -> deck_harmony"
        ],
        "ai_authored_documents": ["planning/deck_plan.json", "planning/slide_plans.json"],
        "normal_model_call_limit": 2
    })
    print(root)


def analyze_project(args):
    root = Path(args.project).resolve()
    manuscript = next((p for p in (root / "inputs").glob("manuscript.*")), None)
    if manuscript is None:
        raise SystemExit("manuscript not found")
    pptx = root / "inputs/source.pptx"
    analyze_source(manuscript, root / "analysis/manuscript_analysis.json")
    analyze_ppt(pptx, root / "analysis")
    # Render before design fingerprinting. Real templates frequently keep logos,
    # brand bars and photography in slide masters/backgrounds rather than editable
    # slide shapes, so actual source renders are the deterministic palette fallback.
    renders = render_pptx(pptx, root / "render/source_renders")
    build_design_system(root)
    seed_plan(root)
    build_continuity_plans(root)
    validate_continuity(root)
    state = load_state(root)
    state["project"]["phase"] = "analysis"
    state["project"]["ui_state"] = "structure_review"
    state["project"]["status"] = "REVIEW_REQUIRED"
    save_state(root, state)
    print(f"analyzed: {root}; source renders: {len(renders)}")


def status(args):
    root = Path(args.project).resolve()
    import json
    print(json.dumps(load_state(root), ensure_ascii=False, indent=2))


def stale(args):
    import json
    print(json.dumps(mark_stale(args.project, args.slide, args.from_phase, args.reason), ensure_ascii=False, indent=2))


def skeleton(args):
    import json
    print(json.dumps(build_skeleton(args.project), ensure_ascii=False, indent=2))


def compile_plans_cmd(args):
    import json
    result = compile_plan_bundle(args.project)
    result["derived_views"] = project_legacy_views(args.project)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def plan_layouts_cmd(args):
    import json
    slides = [x.strip() for x in args.slides.split(',') if x.strip()] if args.slides else None
    print(json.dumps(plan_layouts(args.project, slide_ids=slides), ensure_ascii=False, indent=2))


def compose(args):
    import json
    slides = [x.strip() for x in args.slides.split(',') if x.strip()] if args.slides else None
    print(json.dumps(compose_deck(args.project, slide_ids=slides, output_name=args.output), ensure_ascii=False, indent=2))


def validate_cmd(args):
    import json
    print(json.dumps(validate_output(args.project, args.pptx, kind=args.kind), ensure_ascii=False, indent=2))

def validate_deck_cmd(args):
    import json
    print(json.dumps(validate_deck(args.project), ensure_ascii=False, indent=2))



def generate_images_cmd(args):
    import json
    slides = [x.strip() for x in args.slides.split(',') if x.strip()] if args.slides else None
    recipes = [x.strip() for x in args.recipes.split(',') if x.strip()] if args.recipes else None
    manual = {}
    for row in args.manual or []:
        if '=' not in row:
            raise SystemExit('--manual requires RECIPE_ID=project-relative-path')
        key, value = row.split('=', 1)
        manual[key.strip()] = value.strip()
    result = generate_images(args.project, provider=args.provider, slide_ids=slides, recipe_ids=recipes, manual_paths=manual, quality=args.quality, model=args.model, allow_mock=args.allow_mock)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def select_image_cmd(args):
    import json
    print(json.dumps(select_image_asset(args.project, args.recipe, args.asset), ensure_ascii=False, indent=2))


def update_image_recipe_cmd(args):
    import json
    focal = None
    if args.focal_point is not None:
        focal = "auto" if args.focal_point == "auto" else [float(x.strip()) for x in args.focal_point.split(",", 1)]
    result = update_image_recipe(
        args.project, args.recipe, prompt_seed=args.prompt,
        negative_space=args.negative_space, focal_point=focal,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def validate_images_cmd(args):
    import json
    result = {
        'image_harmony': validate_image_harmony(args.project),
        'deck_image_coherence': validate_deck_image_coherence(args.project),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def refresh_continuity_cmd(args):
    import json
    root = Path(args.project).resolve()
    design = build_design_system(root)
    plans = build_continuity_plans(root)
    qa = validate_continuity(root)
    print(json.dumps({'design': design, 'plans': plans, 'qa': qa}, ensure_ascii=False, indent=2))



def feedback_cmd(args):
    import json
    value = json.loads(args.value) if args.json else args.value
    print(json.dumps(apply_feedback(args.project, args.slide, args.kind, value), ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(prog="slide-engine")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--project", required=True)
    p.add_argument("--ppt", required=True)
    p.add_argument("--manuscript", required=True)
    p.add_argument("--design", required=True)
    p.add_argument("--asset", action="append", default=[], help="optional image asset; may be repeated")
    p.set_defaults(func=init_project)

    p = sub.add_parser("analyze")
    p.add_argument("--project", required=True)
    p.set_defaults(func=analyze_project)

    p = sub.add_parser("status")
    p.add_argument("--project", required=True)
    p.set_defaults(func=status)

    p = sub.add_parser("mark-stale")
    p.add_argument("--project", required=True)
    p.add_argument("--slide", required=True)
    p.add_argument("--from", dest="from_phase", required=True)
    p.add_argument("--reason", default="upstream_changed")
    p.set_defaults(func=stale)

    p = sub.add_parser("build-skeleton")
    p.add_argument("--project", required=True)
    p.set_defaults(func=skeleton)

    p = sub.add_parser("compile-plans")
    p.add_argument("--project", required=True)
    p.set_defaults(func=compile_plans_cmd)

    p = sub.add_parser("plan-layouts")
    p.add_argument("--project", required=True)
    p.add_argument("--slides", default=None, help="comma-separated OUT-S ids; omit for all")
    p.set_defaults(func=plan_layouts_cmd)

    p = sub.add_parser("compose")
    p.add_argument("--project", required=True)
    p.add_argument("--slides", default=None, help="comma-separated OUT-S ids; omit for all")
    p.add_argument("--output", default="presentation_draft.pptx")
    p.set_defaults(func=compose)

    p = sub.add_parser("validate")
    p.add_argument("--project", required=True)
    p.add_argument("--pptx", required=True, help="project-relative pptx path")
    p.add_argument("--kind", default="draft")
    p.set_defaults(func=validate_cmd)

    p = sub.add_parser("validate-deck")
    p.add_argument("--project", required=True)
    p.set_defaults(func=validate_deck_cmd)

    p = sub.add_parser("generate-images")
    p.add_argument("--project", required=True)
    p.add_argument("--provider", choices=["auto", "local", "mock", "manual", "openai"], default="auto")
    p.add_argument("--slides", default=None, help="comma-separated OUT-S ids")
    p.add_argument("--recipes", default=None, help="comma-separated recipe ids")
    p.add_argument("--manual", action="append", default=[], help="RECIPE_ID=project-relative-path")
    p.add_argument("--quality", choices=["low", "medium", "high"], default=os.environ.get("OPENAI_IMAGE_QUALITY") or None)
    p.add_argument("--model", default=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"))
    p.add_argument("--allow-mock", action="store_true", help="allow deterministic placeholder generation for tests")
    p.set_defaults(func=generate_images_cmd)

    p = sub.add_parser("select-image")
    p.add_argument("--project", required=True)
    p.add_argument("--recipe", required=True)
    p.add_argument("--asset", required=True)
    p.set_defaults(func=select_image_cmd)

    p = sub.add_parser("update-image-recipe")
    p.add_argument("--project", required=True)
    p.add_argument("--recipe", required=True)
    p.add_argument("--prompt", default=None)
    p.add_argument("--negative-space", choices=["none", "left", "right", "top", "bottom"], default=None)
    p.add_argument("--focal-point", default=None, help="auto or X,Y in the 0..1 range")
    p.set_defaults(func=update_image_recipe_cmd)

    p = sub.add_parser("validate-images")
    p.add_argument("--project", required=True)
    p.set_defaults(func=validate_images_cmd)

    p = sub.add_parser("refresh-continuity")
    p.add_argument("--project", required=True)
    p.set_defaults(func=refresh_continuity_cmd)

    p = sub.add_parser("feedback")
    p.add_argument("--project", required=True)
    p.add_argument("--slide", required=True)
    p.add_argument("--kind", required=True, choices=["primary_message","visual_type","source_slide","layout_family","layout_density","render_text","semantic_chunks"])
    p.add_argument("--value", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=feedback_cmd)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
