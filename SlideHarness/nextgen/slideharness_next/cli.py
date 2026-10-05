from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any
import json
import sys

from .architect import build_deterministic_deck, build_planning_request, validate_deck_against_sources
from .assets import load_asset_manifest, resolve_asset_requests
from .composer import compose_deck, extract_template_preview_image
from .content_modeler import build_content_model, build_coverage_requirements
from .generated_image_qa import inspect_generated_images
from .ingest import ingest_sources
from .models import DeckSpec, SourceBundle, write_json
from .native_chart_qa import inspect_native_charts
from .ocr import OCRConfig
from .package_qa import inspect_package
from .planner import build_coverage_map, plan_deck
from .provenance import build_source_notes, inspect_provenance
from .qa import inspect_pptx, render_pptx
from .regeneration import isolate_regenerated_slide
from .source_adapter import analyze_source_slides, select_source_slides, template_fidelity_qa
from .standardization import build_output_profile, inspect_output_contract
from .template_compiler import build_template_risk_report, compile_template
from .visual_qa import inspect_visual


def _qa_passes(report: dict[str, Any], allow_skip: bool = False) -> bool:
    status = report.get("status")
    return status == "PASS" or (status == "SKIP" and allow_skip)


def _ingest_with_options(args: Any) -> SourceBundle:
    config = OCRConfig.from_environment(
        enabled=not bool(getattr(args, "no_ocr", False)),
        languages=str(getattr(args, "ocr_languages", "jpn+eng")),
        native_text_min_chars=int(getattr(args, "ocr_native_text_min_chars", 24)),
        review_confidence=float(getattr(args, "ocr_review_confidence", 55.0)),
        blocking_confidence=float(getattr(args, "ocr_blocking_confidence", 25.0)),
        cache_dir=getattr(args, "ocr_cache_dir", None),
    )
    return ingest_sources(args.source, ocr_config=config)


def compile_command(args: Any) -> int:
    output_dir = Path(args.out_dir).resolve()
    system = compile_template(args.template)
    write_json(output_dir / "template_system.json", system.to_dict())
    write_json(output_dir / "template_risk_report.json", build_template_risk_report(system))
    print(output_dir / "template_system.json")
    return 0


def _run_build(
    args: Any,
    deck: DeckSpec,
    spec_path: Path,
    coverage: dict[str, Any],
    content_qa: dict[str, Any] | None = None,
    source_bundle: SourceBundle | None = None,
) -> int:
    template_path = Path(args.template).resolve()
    output_dir = Path(args.out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    system = compile_template(template_path)
    template_risk = build_template_risk_report(system)
    plans = plan_deck(deck)
    output_profile = build_output_profile()
    output_contract_qa = inspect_output_contract(deck, plans)
    allow_shadows = bool(args.allow_shadows or deck.metadata.get("allow_shadows") is True)
    information_density = str(getattr(args, "information_density", None) or deck.metadata.get("information_density") or "medium")
    decorativeness = str(getattr(args, "decorativeness", None) or deck.metadata.get("decorativeness") or "medium")
    structured_visual_mode = str(getattr(args, "structured_visual_mode", None) or deck.metadata.get("structured_visual_mode") or "native")
    slide_policies = dict(deck.metadata.get("slide_policies") or {})
    requested_mode = args.composition_mode
    composition_mode = "source-slides" if requested_mode == "auto" and template_risk["risk_level"] == "high" else requested_mode
    if composition_mode == "auto":
        composition_mode = "reconstruct"
    source_evidence = analyze_source_slides(template_path) if composition_mode == "source-slides" else None
    source_slide_report = select_source_slides(source_evidence, plans) if source_evidence is not None else None
    explicit_image = Path(args.image).resolve() if args.image else None
    manifest_assets = load_asset_manifest(args.asset_manifest)
    template_preview = None if args.no_template_preview else extract_template_preview_image(template_path, output_dir / "assets")
    assets, requests = resolve_asset_requests(plans, spec_path, output_dir, manifest_assets, explicit_image, template_preview)
    generated_image_qa = inspect_generated_images(requests)
    write_json(output_dir / "template_system.json", system.to_dict())
    write_json(output_dir / "output_profile.json", output_profile)
    write_json(output_dir / "qa-output-contract.json", output_contract_qa)
    write_json(output_dir / "template_risk_report.json", template_risk)
    write_json(
        output_dir / "deck_outline.json",
        {
            "title": deck.title,
            "metadata": deck.metadata,
            "slides": [
                {
                    "slide_id": slide.slide_id,
                    "title": slide.title,
                    "message": slide.message,
                    "recipe": plan.recipe,
                    "source_unit_ids": slide.source_unit_ids,
                }
                for slide, plan in zip(deck.slides, plans)
            ],
        },
    )
    write_json(output_dir / "coverage_map.json", coverage)
    write_json(output_dir / "layout_plans.json", [plan.to_dict() for plan in plans])
    write_json(output_dir / "asset_requests.json", requests)
    write_json(output_dir / "qa-generated-image.json", generated_image_qa)
    if source_slide_report is not None:
        write_json(output_dir / "source_slide_map.json", source_slide_report)
    awaiting_images = [item for item in requests if item.get("status") == "awaiting_image"]
    if awaiting_images:
        summary = {
            "status": "FAIL",
            "automated_qa_status": "FAIL",
            "artifact_state": "BLOCKED",
            "stage": "image_resolution",
            "deck": None,
            "template": str(template_path),
            "composition_mode": composition_mode,
            "information_density": information_density,
            "decorativeness": decorativeness,
            "structured_visual_mode": structured_visual_mode,
            "slide_count": len(plans),
            "recipes": [plan.recipe for plan in plans],
            "generated_image_qa": "FAIL",
            "image_generation_pending_count": len(awaiting_images),
            "message": "Composition is waiting for generated images.",
        }
        write_json(output_dir / "summary.json", summary)
        print(output_dir / "summary.json")
        return 2
    source_notes: dict[str, str] = {}
    if source_bundle is not None:
        source_notes, source_notes_report = build_source_notes(deck, source_bundle)
        write_json(output_dir / "source_notes.json", source_notes_report)
    pptx_path = compose_deck(
        template_path,
        deck,
        plans,
        system,
        output_dir / "deck.pptx",
        assets,
        composition_mode,
        source_slide_report,
        source_evidence,
        allow_shadows,
        decorativeness,
        source_notes=source_notes,
    )
    structural_qa = inspect_pptx(
        pptx_path,
        plans,
        composition_mode,
        allow_shadows,
        information_density,
        decorativeness,
        structured_visual_mode,
        slide_policies,
    )
    write_json(output_dir / "qa-structural.json", structural_qa)
    native_chart_qa = inspect_native_charts(pptx_path, plans)
    write_json(output_dir / "qa-native-chart.json", native_chart_qa)
    package_qa = inspect_package(pptx_path, template_path)
    write_json(output_dir / "qa-package.json", package_qa)
    provenance_qa = inspect_provenance(pptx_path, deck, source_bundle)
    write_json(output_dir / "qa-provenance.json", provenance_qa)
    render_qa = render_pptx(pptx_path, output_dir / "render") if not args.no_render else {"status": "SKIP", "reason": "--no-render", "images": []}
    write_json(output_dir / "qa-render.json", render_qa)
    visual_qa = inspect_visual(pptx_path, plans, render_qa, information_density)
    write_json(output_dir / "qa-visual.json", visual_qa)
    fidelity_qa = template_fidelity_qa(pptx_path, source_slide_report) if source_slide_report is not None else {"status": "SKIP", "reason": "reconstruct mode"}
    write_json(output_dir / "qa-template-fidelity.json", fidelity_qa)
    content_status = content_qa.get("status") if content_qa else "PASS"
    ocr_qa = source_bundle.ocr_report if source_bundle is not None else {"status": "SKIP", "review_count": 0}
    write_json(output_dir / "qa-ocr.json", ocr_qa)
    ocr_ok = ocr_qa.get("status") in {"PASS", "SKIP"}
    allow_render_skip = bool(getattr(args, "allow_render_skip", False))
    render_status = render_qa.get("status")
    render_ok = _qa_passes(render_qa, allow_render_skip)
    visual_status = visual_qa.get("status")
    visual_ok = _qa_passes(visual_qa, allow_render_skip)
    combined_status = "PASS" if content_status == "PASS" and ocr_ok and output_contract_qa.get("status") == "PASS" and generated_image_qa.get("status") in {"PASS", "SKIP"} and native_chart_qa.get("status") in {"PASS", "SKIP"} and structural_qa["status"] == "PASS" and package_qa["status"] == "PASS" and provenance_qa["status"] in {"PASS", "SKIP"} and render_ok and visual_ok and fidelity_qa.get("status") in {"PASS", "SKIP"} else "FAIL"
    summary = {
        "status": combined_status,
        "automated_qa_status": combined_status,
        "artifact_state": "REVIEW_REQUIRED" if combined_status == "PASS" else "BLOCKED",
        "human_review_required": combined_status == "PASS",
        "deck": str(pptx_path),
        "template": str(template_path),
        "template_risk": template_risk["risk_level"],
        "composition_mode": composition_mode,
        "shadow_policy": "explicitly_allowed" if allow_shadows else "disabled_by_default",
        "information_density": information_density,
        "decorativeness": decorativeness,
        "structured_visual_mode": structured_visual_mode,
        "slide_count": len(plans),
        "recipes": [plan.recipe for plan in plans],
        "structural_qa": structural_qa["status"],
        "package_qa": package_qa["status"],
        "provenance_qa": provenance_qa["status"],
        "content_qa": content_status,
        "ocr_qa": ocr_qa.get("status"),
        "ocr_review_findings": ocr_qa.get("review_count", 0),
        "generated_image_qa": generated_image_qa.get("status"),
        "generated_image_blocking_findings": generated_image_qa.get("summary", {}).get("blocking_count", 0),
        "native_chart_qa": native_chart_qa.get("status"),
        "output_contract_qa": output_contract_qa.get("status"),
        "render_qa": render_status,
        "visual_qa": visual_status,
        "visual_review_findings": visual_qa.get("summary", {}).get("review_count", 0),
        "render_policy": "skip_allowed" if allow_render_skip else "required",
        "template_fidelity_qa": fidelity_qa.get("status"),
        "montage": render_qa.get("montage"),
    }
    review_packet = {
        "schema_version": "0.11-mvp.4",
        "state": "SAMPLE_REVIEW" if len(plans) == 3 else "FINAL_REVIEW",
        "automated_qa_status": combined_status,
        "template_risk": template_risk,
        "composition_mode": composition_mode,
        "shadow_policy": "explicitly_allowed" if allow_shadows else "disabled_by_default",
        "information_density": information_density,
        "decorativeness": decorativeness,
        "structured_visual_mode": structured_visual_mode,
        "source_slide_map": str(output_dir / "source_slide_map.json") if source_slide_report is not None else None,
        "deck": str(pptx_path),
        "montage": render_qa.get("montage"),
        "checklist": [
            "template likeness and missing completed-slide ornament",
            "information density and unexplained whitespace",
            "font size and line breaks",
            "visual-QA review findings for rendered whitespace and borderline text size",
            "package integrity, relationships, and content-type registration",
            "speaker-note [Sources] coverage for every referenced source unit",
            "OCR review findings and page-level source metadata when scanned PDFs are used",
            "generated-image resolution, required label OCR, and blank-image checks",
            "generated chart or flow relationships and reading order",
            "native chart type, data contract, and PowerPoint editability",
            "selected native/generated-image policy for charts and flows; native editability of tables",
            "image tone and crop when image requests exist",
        ],
        "approval": {"status": "PENDING", "reviewer": None, "comment": None},
    }
    write_json(output_dir / "summary.json", summary)
    write_json(output_dir / "review_packet.json", review_packet)
    print(output_dir / "summary.json")
    return 0 if combined_status == "PASS" else 2


def build_command(args: Any) -> int:
    spec_path = Path(args.spec).resolve()
    output_dir = Path(args.out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    deck = DeckSpec.load(spec_path)
    plans = plan_deck(deck)
    coverage = build_coverage_map(deck, plans)
    write_json(output_dir / "content_model.json", deck.to_dict())
    write_json(output_dir / "deck_spec.json", deck.to_dict())
    return _run_build(args, deck, spec_path, coverage)


def _write_source_artifacts(output_dir: Path, bundle: Any, content_model: dict[str, Any], requirements: dict[str, Any], planning_request: dict[str, Any]) -> None:
    write_json(output_dir / "source_manifest.json", bundle.manifest_dict())
    write_json(output_dir / "source_units.json", bundle.units_dict())
    write_json(output_dir / "source_assets.json", bundle.assets_dict())
    write_json(output_dir / "content_model.json", content_model)
    write_json(output_dir / "coverage_requirements.json", requirements)
    write_json(output_dir / "planning_request.json", planning_request)
    write_json(output_dir / "qa-ocr.json", bundle.ocr_report)


def ingest_command(args: Any) -> int:
    output_dir = Path(args.out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = _ingest_with_options(args)
    content_model = build_content_model(bundle)
    requirements = build_coverage_requirements(bundle)
    planning_request = build_planning_request(bundle, content_model, requirements)
    _write_source_artifacts(output_dir, bundle, content_model, requirements, planning_request)
    print(output_dir / "source_units.json")
    return 0 if bundle.ocr_report.get("status") == "PASS" else 2


def plan_command(args: Any) -> int:
    output_dir = Path(args.out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = _ingest_with_options(args)
    content_model = build_content_model(bundle)
    requirements = build_coverage_requirements(bundle)
    planning_request = build_planning_request(bundle, content_model, requirements)
    _write_source_artifacts(output_dir, bundle, content_model, requirements, planning_request)
    deck = DeckSpec.load(args.plan) if args.plan else build_deterministic_deck(bundle)
    coverage, content_qa = validate_deck_against_sources(deck, bundle, requirements)
    write_json(output_dir / "deck_spec.json", deck.to_dict())
    write_json(output_dir / "coverage_map.json", coverage)
    write_json(output_dir / "qa-content.json", content_qa)
    print(output_dir / "deck_spec.json")
    return 0 if content_qa["status"] == "PASS" and bundle.ocr_report.get("status") == "PASS" else 2


def source_build_command(args: Any) -> int:
    output_dir = Path(args.out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = _ingest_with_options(args)
    content_model = build_content_model(bundle)
    requirements = build_coverage_requirements(bundle)
    planning_request = build_planning_request(bundle, content_model, requirements)
    _write_source_artifacts(output_dir, bundle, content_model, requirements, planning_request)
    if bundle.ocr_report.get("status") != "PASS":
        write_json(
            output_dir / "summary.json",
            {
                "status": "FAIL",
                "stage": "ocr",
                "ocr_qa": "FAIL",
                "deck": None,
                "message": "Composition stopped because OCR Blocking findings remain.",
            },
        )
        print(output_dir / "summary.json")
        return 2
    deck = DeckSpec.load(args.plan) if args.plan else build_deterministic_deck(bundle)
    coverage, content_qa = validate_deck_against_sources(deck, bundle, requirements)
    deck_spec_path = output_dir / "deck_spec.json"
    write_json(deck_spec_path, deck.to_dict())
    write_json(output_dir / "coverage_map.json", coverage)
    write_json(output_dir / "qa-content.json", content_qa)
    if content_qa["status"] != "PASS":
        write_json(
            output_dir / "summary.json",
            {
                "status": "FAIL",
                "stage": "content_validation",
                "content_qa": "FAIL",
                "deck": None,
                "message": "Composition stopped because Content Blocking findings remain.",
            },
        )
        print(output_dir / "summary.json")
        return 2
    return _run_build(args, deck, Path(args.plan).resolve() if args.plan else deck_spec_path, coverage, content_qa, bundle)


def isolate_slide_command(args: Any) -> int:
    report = isolate_regenerated_slide(args.base, args.candidate, args.slide_index, args.out, args.report)
    print(args.report or args.out)
    return 0 if report["status"] == "PASS" else 2


def verify_existing_command(args: Any) -> int:
    output_dir = Path(args.out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    deck = DeckSpec.load(args.plan)
    plans = plan_deck(deck)
    output_contract = inspect_output_contract(deck, plans)
    structural = inspect_pptx(
        args.pptx,
        plans,
        args.composition_mode,
        args.allow_shadows,
        args.information_density,
        args.decorativeness,
        args.structured_visual_mode,
        dict(deck.metadata.get("slide_policies") or {}),
    )
    package = inspect_package(args.pptx, args.template)
    native_chart = inspect_native_charts(args.pptx, plans)
    source_bundle = ingest_sources(args.source) if args.source else None
    ocr = source_bundle.ocr_report if source_bundle is not None else {"status": "SKIP", "review_count": 0}
    provenance = inspect_provenance(args.pptx, deck, source_bundle)
    render = render_pptx(args.pptx, output_dir / "render") if not args.no_render else {"status": "SKIP", "reason": "--no-render", "images": []}
    visual = inspect_visual(args.pptx, plans, render, args.information_density)
    asset_requests_path = output_dir / "asset_requests.json"
    try:
        asset_requests = json.loads(asset_requests_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        asset_requests = []
    generated_image = inspect_generated_images(asset_requests)
    allow_render_skip = bool(getattr(args, "allow_render_skip", False))
    render_status = render.get("status")
    render_ok = _qa_passes(render, allow_render_skip)
    visual_status = visual.get("status")
    visual_ok = _qa_passes(visual, allow_render_skip)
    status = "PASS" if ocr.get("status") in {"PASS", "SKIP"} and output_contract.get("status") == "PASS" and native_chart.get("status") in {"PASS", "SKIP"} and generated_image.get("status") in {"PASS", "SKIP"} and structural["status"] == "PASS" and package["status"] == "PASS" and provenance["status"] in {"PASS", "SKIP"} and render_ok and visual_ok else "FAIL"
    report = {
        "schema_version": "0.11-mvp.4",
        "status": status,
        "pptx": str(Path(args.pptx).resolve()),
        "slide_count": len(plans),
        "information_density": args.information_density,
        "decorativeness": args.decorativeness,
        "structured_visual_mode": args.structured_visual_mode,
        "shadow_policy": "explicitly_allowed" if args.allow_shadows else "disabled_by_default",
        "structural_qa": structural["status"],
        "package_qa": package["status"],
        "provenance_qa": provenance["status"],
        "ocr_qa": ocr.get("status"),
        "ocr_review_findings": ocr.get("review_count", 0),
        "generated_image_qa": generated_image.get("status"),
        "native_chart_qa": native_chart.get("status"),
        "output_contract_qa": output_contract.get("status"),
        "render_qa": render_status,
        "visual_qa": visual_status,
        "visual_review_findings": visual.get("summary", {}).get("review_count", 0),
        "render_policy": "skip_allowed" if allow_render_skip else "required",
        "montage": render.get("montage"),
    }
    write_json(output_dir / "qa-structural.json", structural)
    write_json(output_dir / "qa-package.json", package)
    write_json(output_dir / "qa-provenance.json", provenance)
    write_json(output_dir / "qa-ocr.json", ocr)
    write_json(output_dir / "qa-generated-image.json", generated_image)
    write_json(output_dir / "qa-native-chart.json", native_chart)
    write_json(output_dir / "output_profile.json", build_output_profile())
    write_json(output_dir / "qa-output-contract.json", output_contract)
    write_json(output_dir / "qa-render.json", render)
    write_json(output_dir / "qa-visual.json", visual)
    write_json(output_dir / "qa-final-regeneration.json", report)
    print(output_dir / "qa-final-regeneration.json")
    return 0 if status == "PASS" else 2


def _add_ocr_arguments(command: ArgumentParser) -> None:
    command.add_argument("--no-ocr", action="store_true", help="disable OCR and fail when a PDF page has insufficient native text")
    command.add_argument("--ocr-languages", default="jpn+eng", help="Tesseract language expression")
    command.add_argument("--ocr-cache-dir", help="shared cache root; OCR entries are stored under its ocr directory")
    command.add_argument("--ocr-native-text-min-chars", type=int, default=24)
    command.add_argument("--ocr-review-confidence", type=float, default=55.0)
    command.add_argument("--ocr-blocking-confidence", type=float, default=25.0)


def parser() -> ArgumentParser:
    root = ArgumentParser(prog="slideharness-next")
    subcommands = root.add_subparsers(dest="command", required=True)
    compile_parser = subcommands.add_parser("compile-template", help="compile an arbitrary PPTX into template_system.json")
    compile_parser.add_argument("--template", required=True)
    compile_parser.add_argument("--out-dir", required=True)
    compile_parser.set_defaults(handler=compile_command)
    ingest_parser = subcommands.add_parser("ingest", help="extract immutable source units and planning inputs")
    ingest_parser.add_argument("--source", required=True, nargs="+")
    ingest_parser.add_argument("--out-dir", required=True)
    _add_ocr_arguments(ingest_parser)
    ingest_parser.set_defaults(handler=ingest_command)
    plan_parser = subcommands.add_parser("plan-source", help="ingest a source and create or validate a deck spec")
    plan_parser.add_argument("--source", required=True, nargs="+")
    plan_parser.add_argument("--plan", help="host-authored deck spec JSON; deterministic fallback when omitted")
    plan_parser.add_argument("--out-dir", required=True)
    _add_ocr_arguments(plan_parser)
    plan_parser.set_defaults(handler=plan_command)
    build_parser = subcommands.add_parser("build", help="plan, compose, render, and QA a deck")
    build_parser.add_argument("--template", required=True)
    build_parser.add_argument("--spec", required=True)
    build_parser.add_argument("--out-dir", required=True)
    build_parser.add_argument("--image", help="resolve the first generated-image request with a local image")
    build_parser.add_argument("--asset-manifest", help="JSON manifest of host/generated assets keyed by asset_id")
    build_parser.add_argument("--no-template-preview", action="store_true", help="leave unresolved images blocking instead of using template imagery as a preview")
    build_parser.add_argument("--no-render", action="store_true")
    build_parser.add_argument("--allow-render-skip", action="store_true", help="draft-only: allow a build to pass when render QA is explicitly skipped or unavailable")
    build_parser.add_argument("--composition-mode", choices=["auto", "reconstruct", "source-slides"], default="auto")
    build_parser.add_argument("--information-density", choices=["low", "medium", "high"], default="medium")
    build_parser.add_argument("--decorativeness", choices=["low", "medium", "high"], default="medium")
    build_parser.add_argument("--structured-visual-mode", choices=["auto", "native", "generated-image"], default="native")
    build_parser.add_argument("--allow-shadows", action="store_true", help="preserve or allow drop shadows only when explicitly requested")
    build_parser.set_defaults(handler=build_command)
    source_parser = subcommands.add_parser("build-source", help="ingest, plan, compose, render, and QA source documents")
    source_parser.add_argument("--template", required=True)
    source_parser.add_argument("--source", required=True, nargs="+")
    source_parser.add_argument("--plan", help="host-authored deck spec JSON; deterministic fallback when omitted")
    source_parser.add_argument("--out-dir", required=True)
    source_parser.add_argument("--image", help="resolve the first generated-image request with a local image")
    source_parser.add_argument("--asset-manifest", help="JSON manifest of host/generated assets keyed by asset_id")
    source_parser.add_argument("--no-template-preview", action="store_true")
    source_parser.add_argument("--no-render", action="store_true")
    source_parser.add_argument("--allow-render-skip", action="store_true", help="draft-only: allow a build to pass when render QA is explicitly skipped or unavailable")
    source_parser.add_argument("--composition-mode", choices=["auto", "reconstruct", "source-slides"], default="auto")
    source_parser.add_argument("--information-density", choices=["low", "medium", "high"], default="medium")
    source_parser.add_argument("--decorativeness", choices=["low", "medium", "high"], default="medium")
    source_parser.add_argument("--structured-visual-mode", choices=["auto", "native", "generated-image"], default="native")
    source_parser.add_argument("--allow-shadows", action="store_true", help="preserve or allow drop shadows only when explicitly requested")
    _add_ocr_arguments(source_parser)
    source_parser.set_defaults(handler=source_build_command)
    isolate_parser = subcommands.add_parser("isolate-slide", help="replace one slide while proving every other page is unchanged")
    isolate_parser.add_argument("--base", required=True)
    isolate_parser.add_argument("--candidate", required=True)
    isolate_parser.add_argument("--slide-index", required=True, type=int)
    isolate_parser.add_argument("--out", required=True)
    isolate_parser.add_argument("--report")
    isolate_parser.set_defaults(handler=isolate_slide_command)
    verify_parser = subcommands.add_parser("verify-existing", help="run structural and render QA on an existing PPTX")
    verify_parser.add_argument("--pptx", required=True)
    verify_parser.add_argument("--plan", required=True)
    verify_parser.add_argument("--template", help="original template for theme-preservation QA")
    verify_parser.add_argument("--source", nargs="+", help="original source files for speaker-note provenance QA")
    verify_parser.add_argument("--out-dir", required=True)
    verify_parser.add_argument("--composition-mode", choices=["reconstruct", "source-slides"], required=True)
    verify_parser.add_argument("--information-density", choices=["low", "medium", "high"], default="medium")
    verify_parser.add_argument("--decorativeness", choices=["low", "medium", "high"], default="medium")
    verify_parser.add_argument("--structured-visual-mode", choices=["auto", "native", "generated-image"], default="native")
    verify_parser.add_argument("--allow-shadows", action="store_true")
    verify_parser.add_argument("--no-render", action="store_true")
    verify_parser.add_argument("--allow-render-skip", action="store_true", help="draft-only: allow verification to pass without an actual render")
    verify_parser.set_defaults(handler=verify_existing_command)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        if getattr(args, "debug", False):
            raise
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
