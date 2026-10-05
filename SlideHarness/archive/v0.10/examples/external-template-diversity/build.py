from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine'))

from analyze_ppt import analyze as analyze_ppt
from compose_deck import compose
from design_continuity import build_design_system
from helpers import read_json, write_json
from layout_engine import plan_layouts
from render_source import render_pptx, render_selected_source_slides
from state import default_project_state, ensure_slide, save_state
from validate_output import validate

EX = Path(__file__).resolve().parent
WORK = EX / '.work'
OUTPUTS = EX / 'outputs'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def choose_slide(slides: list[dict[str, Any]], preferred: list[str], fallback_index: int = 0) -> dict[str, Any]:
    for wanted in preferred:
        for slide in slides:
            roles = slide.get('roles') or {}
            if roles.get('primary') == wanted or wanted in (roles.get('secondary') or []):
                return slide
    return slides[max(0, min(fallback_index, len(slides) - 1))]


def clear_ids(slide: dict[str, Any], assets: list[dict[str, Any]]) -> list[str]:
    asset_by_object = {row.get('source_object_id'): row for row in assets}
    rows: list[str] = []
    for obj in slide.get('objects') or []:
        object_id = obj.get('source_object_id')
        if not object_id:
            continue
        asset = asset_by_object.get(object_id)
        if asset and asset.get('classification') == 'template_chrome':
            continue
        if str(obj.get('text') or '').strip() or asset:
            rows.append(str(object_id))
    return rows


def make_plan(slide_id: str, source: dict[str, Any], request: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    mode = 'intentional_whitespace' if request['family'] in {'cover', 'section', 'closing'} else 'content_filled'
    return {
        'schema_version': '0.9',
        'slide_id': slide_id,
        'source_slide_id': source['id'],
        'adaptation_mode': 'RECOMPOSE',
        'composer_support': 'layout_engine',
        'content_blocks': [],
        'source_object_mutations': [],
        'fill_policy': {
            'mode': mode,
            'source': 'system',
            'reason': ['independent real-template deterministic validation'],
            'preserve_empty_zones': mode == 'intentional_whitespace',
        },
        'layout_request': {**request, 'clear_region_object_ids': clear_ids(source, assets)},
        'status': 'APPROVED',
    }


def montage(paths: list[Path], output: Path, cols: int = 3) -> None:
    thumbs: list[Image.Image] = []
    for path in paths:
        image = Image.open(path).convert('RGB')
        image.thumbnail((640, 360))
        canvas = Image.new('RGB', (640, 360), 'white')
        canvas.paste(image, ((640 - image.width) // 2, (360 - image.height) // 2))
        thumbs.append(canvas)
    rows = max(1, (len(thumbs) + cols - 1) // cols)
    sheet = Image.new('RGB', (cols * 640, rows * 360), (242, 242, 242))
    for index, image in enumerate(thumbs):
        sheet.paste(image, ((index % cols) * 640, (index // cols) * 360))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def build_project(name: str, template: Path) -> dict[str, Any]:
    project = WORK / name
    if project.exists():
        shutil.rmtree(project)
    for rel in [
        'inputs', 'analysis', 'planning/slide_plans', 'render/layout_plans',
        'render/generated_assets', 'render/source_renders', 'qa', 'decisions',
        'state', 'versions', 'output',
    ]:
        (project / rel).mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, project / 'inputs/source.pptx')
    (project / 'inputs/design.md').write_text(
        '# External template diversity\n'
        '- density: medium_low\n'
        '- default_fill_policy: balanced\n'
        '- preserve_source_whitespace: true\n'
        '- forbid_filler_content: true\n'
        '- template_reuse: preferred\n',
        encoding='utf-8',
    )

    analyze_ppt(project / 'inputs/source.pptx', project / 'analysis')
    design = build_design_system(project)
    slides = read_json(project / 'analysis/source_slides.json', {}).get('slides', [])
    assets = read_json(project / 'analysis/source_assets.json', {}).get('assets', [])
    if not slides:
        raise RuntimeError('template has no readable slides')

    selected = {
        'cover': choose_slide(slides, ['cover', 'statement', 'section', 'overview'], 0),
        'timeline': choose_slide(slides, ['timeline', 'process', 'overview', 'long_text'], min(1, len(slides) - 1)),
        'kpi': choose_slide(slides, ['kpi', 'chart', 'table', 'overview'], min(2, len(slides) - 1)),
        'chart': choose_slide(slides, ['chart', 'kpi', 'table', 'overview'], min(3, len(slides) - 1)),
        'closing': choose_slide(slides, ['closing', 'statement', 'section', 'cover'], len(slides) - 1),
    }
    specs = [
        ('OUT-S001', 'cover', selected['cover'], {
            'family': 'cover', 'density': 'airy',
            'title': '元PPTの個性を継承',
            'subtitle': 'SlideHarness 外部PPT互換性テスト',
            'body': '元PPTのデザイン文法で、内容に合わせて再構成。',
        }),
        ('OUT-S002', 'timeline', selected['timeline'], {
            'family': 'timeline', 'density': 'medium_low',
            'title': '原稿から完成までの流れ',
            'subtitle': '意味・表現・レイアウトを分離し、必要な範囲だけ更新',
            'items': [
                {'date': 'STEP 1', 'title': '原稿解析', 'body': 'メモを意味別に整理'},
                {'date': 'STEP 2', 'title': '表現設計', 'body': '伝え方を選ぶ'},
                {'date': 'STEP 3', 'title': 'レイアウト', 'body': '元PPTに適応'},
                {'date': 'STEP 4', 'title': '品質検査', 'body': '画面で品質確認'},
            ],
        }),
        ('OUT-S003', 'kpi', selected['kpi'], {
            'family': 'kpi', 'density': 'medium_low',
            'title': '品質を数値で確認',
            'subtitle': '編集可能性と見た目の両方を検査',
            'items': [
                {'label': '構造QA', 'value': '0件', 'note': 'Blocking issue'},
                {'label': '画像比率', 'value': '100%', 'note': '縦横比を保持'},
                {'label': '部分修正', 'value': '1頁', 'note': '最小再実行範囲'},
            ],
        }),
        ('OUT-S004', 'chart', selected['chart'], {
            'family': 'chart', 'density': 'medium_low',
            'title': '反復改善で品質を安定化',
            'subtitle': 'データがある場合だけ、編集可能なPowerPointグラフを生成',
            'categories': ['初期', '構成調整', '組版調整', '最終'],
            'series': [{'name': '品質スコア', 'values': [58, 74, 88, 96]}],
            'chart_type': 'line', 'has_legend': False,
            'note': '数値はレイアウトエンジン検証用のテストデータ',
        }),
        ('OUT-S005', 'closing', selected['closing'], {
            'family': 'closing', 'density': 'airy',
            'title': '必要なページだけ、安心して直せる',
            'subtitle': '元PPTらしさを保ち、完成後も他ページを不用意に変更しません。',
            'items': [
                {'title': '別案', 'body': '表現だけ変更'},
                {'title': '部分修正', 'body': '変更範囲を限定'},
                {'title': '履歴', 'body': '以前の案へ戻す'},
            ],
        }),
    ]

    deck = {'schema_version': '0.9', 'slides': []}
    matches = {'schema_version': '0.9', 'slides': []}
    for index, (slide_id, role, source, request) in enumerate(specs, start=1):
        deck['slides'].append({
            'slide_id': slide_id, 'order': index, 'role': role,
            'primary_message': request['title'], 'status': 'APPROVED',
        })
        matches['slides'].append({
            'slide_id': slide_id,
            'selected': {
                'source_slide_id': source['id'], 'page_number': source['page_number'],
                'recommended_mode': 'RECOMPOSE',
            },
        })
        write_json(project / f'planning/slide_plans/{slide_id}.json', make_plan(slide_id, source, request, assets))
    write_json(project / 'planning/deck_plan.json', deck)
    write_json(project / 'planning/slide_matching.json', matches)

    render_selected_source_slides(
        project / 'inputs/source.pptx',
        [int(source['page_number']) for _, _, source, _ in specs],
        project / 'render/source_renders',
    )
    state = default_project_state()
    state['project'].update({'phase': 'production', 'status': 'APPROVED'})
    for slide_id, *_ in specs:
        row = ensure_slide(state, slide_id)
        for phase in ('deck_plan', 'visual_plan', 'source_match', 'slide_plan'):
            row[phase] = 'APPROVED'
    save_state(project, state)

    planned = plan_layouts(project)
    if planned.get('errors'):
        raise RuntimeError(json.dumps(planned, ensure_ascii=False, indent=2))
    result = compose(project, output_name=f'{name}.pptx')
    if result.get('errors'):
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))
    qa = validate(project, f'output/{name}.pptx', kind=f'external-{name}')
    rendered = [Path(row) for row in (qa.get('rendered_pages') or []) if Path(row).exists()]
    if not rendered:
        rendered = [Path(row) for row in render_pptx(project / f'output/{name}.pptx', project / 'render/final')]

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    output_pptx = OUTPUTS / f'{name}.pptx'
    montage_path = OUTPUTS / f'{name}-montage.png'
    shutil.copy2(project / f'output/{name}.pptx', output_pptx)
    montage(rendered, montage_path)
    shutil.copy2(project / 'qa' / f'{name}_qa.json', OUTPUTS / f'{name}-qa.json')

    fingerprint = design.get('design_fingerprint') or {}
    asset_classes: dict[str, int] = {}
    content_roles: dict[str, int] = {}
    for asset in assets:
        classification = str(asset.get('classification') or 'unknown')
        asset_classes[classification] = asset_classes.get(classification, 0) + 1
        content_role = str(asset.get('content_role') or 'unknown')
        content_roles[content_role] = content_roles.get(content_role, 0) + 1
    return {
        'name': name,
        'template_filename': template.name,
        'template_sha256': sha256(template),
        'source_slide_count': len(slides),
        'generated_slide_count': len(specs),
        'render_count': len(rendered),
        'blocking': qa.get('blocking_count'),
        'warning': qa.get('warning_count'),
        'asset_classes': asset_classes,
        'content_roles': content_roles,
        'title_axis_x_in': (fingerprint.get('composition') or {}).get('title_axis_x_in'),
        'template_chrome_count': (fingerprint.get('components') or {}).get('template_chrome_count'),
        'output': str(output_pptx.relative_to(ROOT)),
        'montage': str(montage_path.relative_to(ROOT)),
    }




def combined_montage(results: list[dict[str, Any]], output: Path) -> None:
    """Create one compact review sheet from each fixture's generated montage."""
    label_map = {
        'miri': 'MIRI template',
        'chorakukan': 'Chorakukan editorial deck',
        'utokyo': 'UTokyo leaflet deck',
        'sample': 'Minimal sample template',
        'agent': 'Agent Skills promotion deck',
    }
    rows: list[Image.Image] = []
    target_w, target_h, header_h = 1280, 480, 34
    from PIL import ImageDraw
    for row in results:
        montage_rel = row.get('montage')
        if not montage_rel:
            continue
        path = ROOT / str(montage_rel)
        if not path.exists():
            continue
        source = Image.open(path).convert('RGB')
        source.thumbnail((target_w, target_h))
        canvas = Image.new('RGB', (target_w, target_h + header_h), 'white')
        canvas.paste(source, ((target_w - source.width) // 2, header_h + (target_h - source.height) // 2))
        draw = ImageDraw.Draw(canvas)
        draw.text((12, 9), label_map.get(str(row.get('name')), str(row.get('name') or 'Template')), fill=(25, 25, 25))
        rows.append(canvas)
    if not rows:
        return
    sheet = Image.new('RGB', (target_w, len(rows) * (target_h + header_h)), (238, 238, 238))
    for index, image in enumerate(rows):
        sheet.paste(image, (0, index * (target_h + header_h)))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)

def parse_templates(values: list[str]) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for value in values:
        if '=' not in value:
            raise SystemExit(f'--template must use name=/absolute/path: {value}')
        name, raw_path = value.split('=', 1)
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f'template does not exist: {path}')
        rows.append((name.strip(), path))
    return rows


def _run_child(name: str, path: Path, timeout: int = 360) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix='slideharness-diversity-result-') as td:
        result_path = Path(td) / 'result.json'
        command = [sys.executable, str(Path(__file__).resolve()), '--single-template', f'{name}={path}', '--result', str(result_path)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = proc.communicate()
            return {'name': name, 'template_filename': path.name, 'error': f'child timed out after {timeout}s', 'stderr': stderr[-1000:]}
        if result_path.exists():
            try:
                return json.loads(result_path.read_text(encoding='utf-8'))
            except Exception as exc:
                return {'name': name, 'template_filename': path.name, 'error': f'invalid child result: {exc}', 'stdout': stdout[-1000:], 'stderr': stderr[-1000:]}
        return {'name': name, 'template_filename': path.name, 'error': f'child exited {proc.returncode} without result', 'stdout': stdout[-1000:], 'stderr': stderr[-1000:]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--template', action='append', default=[], help='name=/absolute/path; repeat for each independent PPT')
    parser.add_argument('--single-template', help=argparse.SUPPRESS)
    parser.add_argument('--result', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--child-timeout', type=int, default=360)
    args = parser.parse_args()

    if args.single_template:
        name, path = parse_templates([args.single_template])[0]
        try:
            row = build_project(name, path)
        except Exception as exc:
            row = {'name': name, 'template_filename': path.name, 'error': f'{type(exc).__name__}: {exc}'}
        if args.result:
            write_json(args.result, row)
        print(json.dumps(row, ensure_ascii=False, indent=2))
        raise SystemExit(1 if row.get('error') or row.get('blocking') not in {0, None} else 0)

    templates = parse_templates(args.template)
    if not templates:
        raise SystemExit('provide at least one --template name=/path')
    if WORK.exists():
        shutil.rmtree(WORK)
    if OUTPUTS.exists():
        shutil.rmtree(OUTPUTS)
    results = [_run_child(name, path, timeout=args.child_timeout) for name, path in templates]
    report = {
        'version': '0.9.0',
        'purpose': 'independent_real_ppt_full_generation',
        'process_isolation': True,
        'execution_note': (
            'Each independent template is analyzed, recomposed, rendered, and validated in an isolated child process. '
            'Source PPT bytes are runtime inputs and are not bundled.'
        ),
        'template_count': len(results),
        'pass_count': sum(1 for row in results if not row.get('error') and row.get('blocking') == 0),
        'fail_count': sum(1 for row in results if row.get('error') or row.get('blocking') != 0),
        'total_source_slides': sum(int(row.get('source_slide_count') or 0) for row in results),
        'total_generated_slides': sum(int(row.get('generated_slide_count') or 0) for row in results),
        'combined_montage': 'examples/external-template-diversity/external-diversity-montage.png',
        'results': results,
    }
    combined_montage(results, EX / 'external-diversity-montage.png')
    write_json(EX / 'summary.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report['fail_count']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
