from __future__ import annotations
import json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'engine'))
from analyze_ppt import analyze as analyze_ppt
from design_continuity import build_design_system
from render_source import render_pptx
from helpers import read_json, write_json
from layout_engine import plan_layouts
from compose_deck import compose
from validate_output import validate
from state import default_project_state, ensure_slide, save_state

EX=Path(__file__).resolve().parent
TEMPLATES={
 'miri': ROOT/'examples/generic-template-smoke/inputs/miri-template.pptx',
 'golden-v06': ROOT/'examples/generic-template-smoke/inputs/golden-sample-v06.pptx',
 'image-harmony-v05': ROOT/'examples/generic-template-smoke/inputs/image-harmony-v05.pptx',
}

def role(slide): return (slide.get('roles') or {}).get('primary')
def choose(slides, preferred):
 for r in preferred:
  for s in slides:
   if role(s)==r or r in ((s.get('roles') or {}).get('secondary') or []): return s
 return slides[0]

def clear_ids(slide, assets):
 asset_by={a.get('source_object_id'):a for a in assets}
 ids=[]
 for o in slide.get('objects',[]):
  oid=o.get('source_object_id'); txt=str(o.get('text') or '').strip(); a=asset_by.get(oid)
  if txt or (a and a.get('classification') in {'content_visual','unknown'}): ids.append(oid)
 return [x for x in ids if x]

def run_one(name, pptx):
 root=EX/'.work'/name
 if root.exists(): shutil.rmtree(root)
 for d in ['inputs','analysis','planning/slide_plans','render/layout_plans','render/generated_assets','render/source_renders','qa','decisions','state','output']:(root/d).mkdir(parents=True,exist_ok=True)
 shutil.copy2(pptx,root/'inputs/source.pptx')
 (root/'inputs/design.md').write_text('''# Generic compatibility\n- density: medium_low\n- default_fill_policy: balanced\n- preserve_source_whitespace: true\n- forbid_filler_content: true\n''')
 analyze_ppt(root/'inputs/source.pptx',root/'analysis'); render_pptx(root/'inputs/source.pptx', root/'render/source_renders'); build_design_system(root)
 slides=read_json(root/'analysis/source_slides.json',{}).get('slides',[]); assets=read_json(root/'analysis/source_assets.json',{}).get('assets',[])
 s1=choose(slides,['statement','cover','long_text','overview']); s2=choose(slides,['four_items','three_items','overview','table']); s3=choose(slides,['comparison','table','long_text','overview'])
 spec=[
  ('OUT-S001',s1,'statement',{'family':'statement','density':'airy','title':'一つの強いメッセージを、余白とともに見せる','subtitle':'元PPTのデザイン文法を保ちながら、新しい内容へ適応','title_font_pt':34}),
  ('OUT-S002',s2,'four_items',{'family':'grid','density':'medium_low','title':'4つの論点を、読みやすい密度で整理','subtitle':'情報量に応じてカードサイズを調整','items':[{'number':f'0{i}','title':t,'body':b} for i,(t,b) in enumerate([('構成','原稿を意味単位に分割'),('表現','適切なVisual Typeを選択'),('継承','元PPTのデザインDNAを保持'),('検査','実レンダリングでQA')],1)]}),
  ('OUT-S003',s3,'two_column',{'family':'two_column','density':'medium_low','title':'元のデザインと、新しい内容を両立','subtitle':'完全コピーでも完全新規でもなく、必要な範囲だけ再構成','items':[{'title':'元PPTから継承','body':'タイポグラフィ\n配色\n余白\n共通装飾','style':'card'},{'title':'今回の内容へ適応','body':'文章量\n項目数\n情報表現\nレイアウト','style':'card'}]})
 ]
 deck={'slides':[]}; matches={'slides':[]}
 for sid,src,r,req in spec:
  deck['slides'].append({'slide_id':sid,'order':len(deck['slides'])+1,'role':r,'primary_message':req['title'],'status':'APPROVED'})
  matches['slides'].append({'slide_id':sid,'selected':{'source_slide_id':src['id'],'page_number':src['page_number'],'recommended_mode':'RECOMPOSE'}})
  plan={'schema_version':'0.8','slide_id':sid,'source_slide_id':src['id'],'adaptation_mode':'RECOMPOSE','composer_support':'layout_engine','content_blocks':[],'source_object_mutations':[],'fill_policy':{'mode':'intentional_whitespace' if req['family']=='statement' else 'content_filled','source':'system','reason':['generic full-generation compatibility']},'layout_request':{**req,'clear_region_object_ids':clear_ids(src,assets)},'status':'APPROVED'}
  write_json(root/f'planning/slide_plans/{sid}.json',plan)
 write_json(root/'planning/deck_plan.json',deck); write_json(root/'planning/slide_matching.json',matches)
 st=default_project_state(); st['project'].update({'phase':'production','status':'APPROVED'})
 for sid,_,_,_ in spec:
  row=ensure_slide(st,sid)
  for p in ('deck_plan','visual_plan','source_match','slide_plan'): row[p]='APPROVED'
 save_state(root,st)
 plan_layouts(root)
 out=compose(root,output_name=f'{name}.pptx')
 qa=validate(root,f'output/{name}.pptx',kind=f'compat-{name}')
 return {'name':name,'slides':len(spec),'blocking':qa['blocking_count'],'warning':qa['warning_count'],'pptx':out['output']}

def main():
 results=[]
 for name,p in TEMPLATES.items():
  if not p.exists(): results.append({'name':name,'error':'missing template'}); continue
  try: results.append(run_one(name,p))
  except Exception as e: results.append({'name':name,'error':str(e)})
 write_json(EX/'summary.json',{'version':'0.8','results':results})
 print(json.dumps(results,ensure_ascii=False,indent=2))
 if any(r.get('error') or r.get('blocking',1) for r in results): raise SystemExit(1)
if __name__=='__main__': main()
