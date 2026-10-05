from __future__ import annotations
import json, shutil, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
from analyze_ppt import analyze
from helpers import read_json, write_json

EX=Path(__file__).resolve().parent
WORK=EX/'.work'


def build():
    shutil.rmtree(WORK,ignore_errors=True); WORK.mkdir(parents=True)
    source=ROOT/'examples/test-case/inputs/source.pptx'
    analyze(source,WORK)
    assets=read_json(WORK/'source_assets.json',{}).get('assets',[])
    classes={}; roles={}; reason_counts={}
    for row in assets:
        cls=str(row.get('classification') or 'unknown'); classes[cls]=classes.get(cls,0)+1
        role=str(row.get('content_role') or 'unknown'); roles[role]=roles.get(role,0)+1
        for reason in row.get('reason_codes') or []: reason_counts[reason]=reason_counts.get(reason,0)+1
    total=len(assets); unknown=classes.get('unknown',0)
    report={
        'version':'0.9.0',
        'source':'examples/test-case/inputs/source.pptx',
        'total_picture_assets':total,
        'classification_counts':classes,
        'content_role_counts':roles,
        'unknown_rate':round(unknown/max(1,total),4),
        'review_required_count':sum(1 for row in assets if row.get('status')=='REVIEW_REQUIRED'),
        'geometry_repeated_count':sum(1 for row in assets if int(row.get('geometry_repeat_count') or 0)>=2),
        'top_reason_codes':sorted(reason_counts.items(),key=lambda item:(-item[1],item[0]))[:20],
        'acceptance':{
            'unknown_rate_max':0.30,
            'pass':unknown/max(1,total) <= 0.30,
        },
    }
    write_json(EX/'summary.json',report)
    return report

if __name__=='__main__': print(json.dumps(build(),ensure_ascii=False,indent=2))
