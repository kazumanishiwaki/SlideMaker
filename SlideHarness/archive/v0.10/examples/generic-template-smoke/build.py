from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'engine'
EXAMPLE = Path(__file__).resolve().parent
WORK = EXAMPLE / '.work'
sys.path.insert(0, str(ENGINE))
from analyze_ppt import analyze as analyze_ppt
from design_continuity import build_design_system
from render_source import render_pptx
from helpers import read_json, write_json


def smoke_one(template: Path) -> dict:
    root = WORK / template.stem
    if root.exists(): shutil.rmtree(root)
    for rel in ['inputs','analysis','render/source_renders']:
        (root/rel).mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, root/'inputs/source.pptx')
    analyze_ppt(root/'inputs/source.pptx', root/'analysis')
    design = build_design_system(root)
    renders = render_pptx(root/'inputs/source.pptx', root/'render/source_renders')
    source = read_json(root/'analysis/source_slides.json', {})
    assets = read_json(root/'analysis/source_assets.json', {})
    roles = {}
    for slide in source.get('slides', []):
        role = (slide.get('roles') or {}).get('primary', 'unknown')
        roles[role] = roles.get(role, 0) + 1
    asset_classes = {}
    for asset in assets.get('assets', []):
        cls = asset.get('classification', 'unknown')
        asset_classes[cls] = asset_classes.get(cls, 0) + 1
    fingerprint = design.get('design_fingerprint') or {}
    status = 'PASS'
    blocking = []
    if not source.get('slides'):
        status='FAIL'; blocking.append('NO_SLIDES')
    if len(renders) != len(source.get('slides', [])):
        status='FAIL'; blocking.append('RENDER_COUNT_MISMATCH')
    if not (fingerprint.get('composition') or {}).get('slide_aspect_ratio'):
        status='FAIL'; blocking.append('NO_DESIGN_FINGERPRINT')
    return {
        'template': template.name,
        'status': status,
        'blocking': blocking,
        'slide_count': len(source.get('slides', [])),
        'render_count': len(renders),
        'roles': roles,
        'asset_classes': asset_classes,
        'title_axis_x_in': (fingerprint.get('composition') or {}).get('title_axis_x_in'),
        'source_chrome_count': (fingerprint.get('components') or {}).get('template_chrome_count'),
    }


def build():
    if WORK.exists(): shutil.rmtree(WORK)
    templates = sorted((EXAMPLE/'inputs').glob('*.pptx'))
    rows = [smoke_one(t) for t in templates]
    report = {
        'version':'0.7.0',
        'purpose':'generic_template_smoke',
        'template_count': len(rows),
        'pass_count': sum(1 for r in rows if r['status']=='PASS'),
        'fail_count': sum(1 for r in rows if r['status']!='PASS'),
        'templates': rows,
    }
    write_json(EXAMPLE/'generic-template-smoke-report.json', report)
    return report

if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
