from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
EX = Path(__file__).resolve().parent
WORK = EX / '.work'
sys.path.insert(0, str(ROOT / 'engine'))

from analyze_ppt import analyze as analyze_ppt
from compose_deck import compose
from design_continuity import build_design_system
from helpers import read_json, write_json
from layout_engine import plan_layouts
from render_source import render_selected_source_slides
from state import default_project_state, ensure_slide, save_state
from validate_output import validate


def _dirs() -> list[str]:
    return [
        'inputs', 'analysis', 'planning/slide_plans', 'render/layout_plans',
        'render/source_renders', 'render/generated_assets', 'qa', 'decisions',
        'state', 'versions', 'output',
    ]


def _clear_ids(project: Path, source_id: str) -> list[str]:
    slides = read_json(project / 'analysis/source_slides.json', {}).get('slides', [])
    assets = read_json(project / 'analysis/source_assets.json', {}).get('assets', [])
    protected = {
        row.get('source_object_id') for row in assets
        if row.get('source_slide_id') == source_id and row.get('classification') == 'template_chrome'
    }
    slide = next(row for row in slides if row.get('id') == source_id)
    return [
        str(row['source_object_id']) for row in slide.get('objects', [])
        if row.get('source_object_id') and row.get('source_object_id') not in protected
    ]


def _plan(slide_id: str, source_id: str, request: dict[str, Any], project: Path) -> dict[str, Any]:
    mode = 'intentional_whitespace' if request['family'] in {'cover', 'section', 'closing'} else 'content_filled'
    return {
        'schema_version': '0.9',
        'slide_id': slide_id,
        'source_slide_id': source_id,
        'adaptation_mode': 'RECOMPOSE',
        'composer_support': 'layout_engine',
        'content_blocks': [],
        'source_object_mutations': [],
        'fill_policy': {
            'mode': mode,
            'source': 'system',
            'reason': ['v0.9 layout-family deterministic validation'],
            'preserve_empty_zones': mode == 'intentional_whitespace',
        },
        'layout_request': {
            **request,
            'clear_region_object_ids': _clear_ids(project, source_id),
        },
        'status': 'APPROVED',
    }


def _montage(paths: list[Path], output: Path, cols: int = 3) -> None:
    thumbs: list[Image.Image] = []
    for path in paths:
        image = Image.open(path).convert('RGB')
        image.thumbnail((640, 360))
        canvas = Image.new('RGB', (640, 360), 'white')
        canvas.paste(image, ((640 - image.width) // 2, (360 - image.height) // 2))
        thumbs.append(canvas)
    rows = (len(thumbs) + cols - 1) // cols
    montage = Image.new('RGB', (cols * 640, rows * 360), (242, 242, 242))
    for index, image in enumerate(thumbs):
        montage.paste(image, ((index % cols) * 640, (index // cols) * 360))
    montage.save(output)


def build() -> dict[str, Any]:
    if WORK.exists():
        shutil.rmtree(WORK)
    for rel in _dirs():
        (WORK / rel).mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'examples/test-case/inputs/source.pptx', WORK / 'inputs/source.pptx')
    shutil.copy2(ROOT / 'examples/test-case/design.md', WORK / 'inputs/design.md')
    analyze_ppt(WORK / 'inputs/source.pptx', WORK / 'analysis')
    build_design_system(WORK)

    specs = [
        ('OUT-S001', 'cover', 'SRC-S001', {
            'family': 'cover', 'density': 'airy',
            'title': '元PPTの文法で再構成',
            'subtitle': 'SlideHarness v0.9.0',
            'body': '既存PowerPoint × 雑な原稿 × 決定論的レイアウト',
        }),
        ('OUT-S002', 'section', 'SRC-S002', {
            'family': 'section', 'density': 'airy', 'kicker': '01',
            'title': '原稿を、伝わる構造へ',
            'subtitle': '意味・表現・レイアウトを分けて設計します。',
        }),
        ('OUT-S003', 'timeline', 'SRC-S014', {
            'family': 'timeline', 'density': 'medium_low',
            'title': '原稿から完成までの流れ',
            'subtitle': '必要な工程だけを再実行し、承認済みページを守ります。',
            'items': [
                {'date': 'STEP 1', 'title': '原稿解析', 'body': 'メモを意味単位に分類'},
                {'date': 'STEP 2', 'title': '構成設計', 'body': '一ページ一メッセージへ整理'},
                {'date': 'STEP 3', 'title': 'PPT適応', 'body': 'デザイン文法を継承'},
                {'date': 'STEP 4', 'title': '品質検査', 'body': '実レンダリングで確認'},
            ],
        }),
        ('OUT-S004', 'kpi', 'SRC-S012', {
            'family': 'kpi', 'density': 'medium_low',
            'title': '品質を、検査できる状態にする',
            'subtitle': '編集可能性・組版・部分再生成を数値で確認',
            'items': [
                {'label': 'Blocking', 'value': '0件', 'note': '最終書き出し条件'},
                {'label': '実レンダリング', 'value': '100%', 'note': '全ページを画像で検証'},
                {'label': '再生成範囲', 'value': '1頁', 'note': '無関係なページは維持'},
            ],
        }),
        ('OUT-S005', 'chart', 'SRC-S005', {
            'family': 'chart', 'density': 'medium_low',
            'title': '調整を重ね、品質を安定させる',
            'subtitle': 'データがある場合のみ、編集可能なPowerPointグラフを生成',
            'categories': ['初期', '構成', '組版', '最終'],
            'series': [{'name': '品質スコア', 'values': [54, 72, 88, 96]}],
            'chart_type': 'line', 'has_legend': False,
            'note': 'レイアウトエンジン検証用のテストデータ',
        }),
        ('OUT-S006', 'closing', 'SRC-S017', {
            'family': 'closing', 'density': 'airy',
            'title': '良いページを守りながら、必要な箇所だけ直す',
            'subtitle': '構成確認・代表ページ確認・最終確認の3段階で進めます。',
            'items': [
                {'title': '別案', 'body': '同じメッセージで表現だけ変更'},
                {'title': '部分修正', 'body': '画像・文章・配置を限定して更新'},
                {'title': '履歴', 'body': '以前の承認版へ安全に戻す'},
            ],
        }),
    ]

    deck = {'schema_version': '0.9', 'slides': []}
    matching = {'schema_version': '0.9', 'slides': []}
    for order, (slide_id, role, source_id, request) in enumerate(specs, start=1):
        page = int(source_id.split('S')[-1])
        deck['slides'].append({
            'slide_id': slide_id, 'order': order, 'role': role,
            'primary_message': request.get('title', ''), 'status': 'APPROVED',
        })
        matching['slides'].append({
            'slide_id': slide_id,
            'selected': {'source_slide_id': source_id, 'page_number': page, 'recommended_mode': 'RECOMPOSE'},
        })
        write_json(WORK / f'planning/slide_plans/{slide_id}.json', _plan(slide_id, source_id, request, WORK))
    write_json(WORK / 'planning/deck_plan.json', deck)
    write_json(WORK / 'planning/slide_matching.json', matching)

    render_selected_source_slides(
        WORK / 'inputs/source.pptx',
        [int(source_id.split('S')[-1]) for _, _, source_id, _ in specs],
        WORK / 'render/source_renders',
    )
    state = default_project_state()
    state['project'].update({'phase': 'production', 'status': 'APPROVED'})
    for slide_id, *_ in specs:
        row = ensure_slide(state, slide_id)
        for phase in ('deck_plan', 'visual_plan', 'source_match', 'slide_plan'):
            row[phase] = 'APPROVED'
    save_state(WORK, state)

    planned = plan_layouts(WORK)
    if planned.get('errors'):
        raise RuntimeError(json.dumps(planned, ensure_ascii=False, indent=2))
    result = compose(WORK, output_name='layout-family-v0.9.0.pptx')
    if result.get('errors'):
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))
    qa = validate(WORK, 'output/layout-family-v0.9.0.pptx', kind='layout-family-v090')
    if qa.get('blocking_count') or qa.get('warning_count'):
        raise RuntimeError(json.dumps(qa, ensure_ascii=False, indent=2))

    pptx_out = EX / 'layout-family-v0.9.0.pptx'
    shutil.copy2(WORK / 'output/layout-family-v0.9.0.pptx', pptx_out)
    rendered = [Path(path) for path in qa.get('rendered_pages', []) if Path(path).exists()]
    for index, page in enumerate(rendered, start=1):
        shutil.copy2(page, EX / f'slide-{index:02d}.png')
    montage_out = EX / 'layout-family-v0.9.0-montage.png'
    _montage(rendered, montage_out)

    families: list[dict[str, Any]] = []
    for slide_id, family, *_ in specs:
        plan = read_json(WORK / f'render/layout_plans/{slide_id}.json', {})
        families.append({
            'slide_id': slide_id,
            'family': family,
            'fit_score': (plan.get('quality') or {}).get('score'),
            'fill_policy': (plan.get('fill_policy') or {}).get('mode'),
            'status': (plan.get('quality') or {}).get('status'),
        })
    summary = {
        'version': '0.9.0',
        'slides': len(specs),
        'blocking': qa.get('blocking_count'),
        'warning': qa.get('warning_count'),
        'pptx': 'examples/layout-family-v090/layout-family-v0.9.0.pptx',
        'montage': 'examples/layout-family-v090/layout-family-v0.9.0-montage.png',
        'families': families,
    }
    write_json(EX / 'summary.json', summary)
    shutil.rmtree(WORK, ignore_errors=True)
    return summary


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
