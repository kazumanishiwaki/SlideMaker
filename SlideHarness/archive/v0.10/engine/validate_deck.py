from __future__ import annotations
from pathlib import Path
from typing import Any
import math
import re

from helpers import now_iso, read_json, write_json
from image_pipeline import validate_deck_image_coherence
from planning import load_slide_plan_bundle, renderer_group


def _runs(values: list[str], min_len: int):
    if not values:
        return []
    out=[]; start=0
    for i in range(1,len(values)+1):
        if i==len(values) or values[i] != values[start]:
            if i-start >= min_len:
                out.append((start,i,values[start]))
            start=i
    return out


def _norm(s: str) -> str:
    return re.sub(r'\s+','',str(s or '')).lower()


def _category(code: str) -> str:
    if code in {'DUPLICATE_PRIMARY_MESSAGE'}:
        return 'content'
    if code.startswith(('REPEATED_', 'HIGH_DENSITY_', 'DECK_VISUAL_EVIDENCE_', 'DECK_RENDERER_GROUP_')):
        return 'design'
    if code.startswith('DECK_IMAGE_'):
        return 'design'
    return 'technical'


def validate_deck(project: str | Path) -> dict[str,Any]:
    root=Path(project).resolve()
    deck=read_json(root/'planning/deck_plan.json',{})
    bundle=load_slide_plan_bundle(root)
    compact_by={x.get('slide_id'):x for x in bundle.get('slides',[])}
    slides=sorted(deck.get('slides',[]),key=lambda x:x.get('order',9999))
    checks=[]
    def add(code,result='fail',severity='warning',**kw):
        checks.append({'check_id':code,'result':result,'severity':severity,'category':_category(code),**kw})

    if not slides:
        add('DECK_HAS_SLIDES','fail','blocking')
    else:
        add('DECK_HAS_SLIDES','pass','info',actual=len(slides))

    visual_seq=[]; layout_seq=[]; group_seq=[]; density_seq=[]
    seen={}; evidence_count=0
    for s in slides:
        sid=s.get('slide_id'); msg=str(s.get('primary_message') or '')
        n=_norm(msg)
        if n:
            if n in seen:
                add('DUPLICATE_PRIMARY_MESSAGE','fail','warning',slide_ids=[seen[n],sid],message=msg)
            else:
                seen[n]=sid
        compact=compact_by.get(sid,{})
        visual=compact.get('visual') or {}
        vt=str(visual.get('type') or 'unknown')
        visual_seq.append(vt)
        layout=compact.get('layout') or {}
        family=str(layout.get('family') or 'unknown')
        layout_seq.append(family)
        group_seq.append(renderer_group(family))
        density=str(layout.get('density') or 'medium_low')
        density_seq.append(density)
        image=compact.get('image') or {}
        if image.get('required') or vt in {'photo','photo_grid','screenshot','illustration','conceptual_image','full_bleed'}:
            evidence_count += 1

    for a,b,val in _runs(layout_seq,3):
        add('REPEATED_LAYOUT_SEQUENCE','fail','warning',slide_ids=[slides[i].get('slide_id') for i in range(a,b)],layout_family=val,count=b-a)
    for a,b,val in _runs(group_seq,4):
        add('DECK_RENDERER_GROUP_SEQUENCE','fail','review',slide_ids=[slides[i].get('slide_id') for i in range(a,b)],renderer_group=val,count=b-a)
    for a,b,val in _runs(visual_seq,4):
        add('REPEATED_VISUAL_TYPE','fail','warning',slide_ids=[slides[i].get('slide_id') for i in range(a,b)],visual_type=val,count=b-a)
    for a,b,val in _runs(density_seq,3):
        if val=='dense':
            add('HIGH_DENSITY_SEQUENCE','fail','warning',slide_ids=[slides[i].get('slide_id') for i in range(a,b)],count=b-a)

    # This is a human-review signal, not an auto-repair trigger. Some decks are
    # intentionally text-only, so the check never blocks export.
    if len(slides) >= 6:
        target=max(2, math.ceil(len(slides)*0.33))
        add('DECK_VISUAL_EVIDENCE_COVERAGE', 'pass' if evidence_count >= target else 'fail',
            'info' if evidence_count >= target else 'review', actual=evidence_count, recommended_minimum=target,
            note='Meaningful screenshots/photos/illustrations; filler images are not counted.')

    image_coherence = validate_deck_image_coherence(root)
    for row in image_coherence.get('checks', []):
        row.setdefault('category','design')
        checks.append(row)

    blocking=[c for c in checks if c['result']=='fail' and c['severity']=='blocking']
    warnings=[c for c in checks if c['result']=='fail' and c['severity']!='blocking']
    category_counts={category:{
        'fail':sum(1 for c in checks if c.get('category')==category and c.get('result')=='fail'),
        'blocking':sum(1 for c in checks if c.get('category')==category and c.get('result')=='fail' and c.get('severity')=='blocking'),
    } for category in ('technical','content','design')}
    result={
        'schema_version':'0.10','generated_at':now_iso(),'status':'fail' if blocking else 'pass',
        'blocking_count':len(blocking),'warning_count':len(warnings),'checks':checks,
        'category_counts':category_counts,'image_coherence':image_coherence,
        'sequences':{'visual_types':visual_seq,'layout_families':layout_seq,'renderer_groups':group_seq,'density':density_seq},
        'notes':['Deck review is diagnostic. Design findings trigger at most one re-plan or user review; they never cause an unbounded automatic rewrite loop.']
    }
    write_json(root/'qa/deck_harmony.json',result)
    return result
