import json, tempfile, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine'))
from design_continuity import build_design_system, build_continuity_plans, validate_continuity

def test_design_system_and_continuity_seed():
    with tempfile.TemporaryDirectory() as td:
        r=Path(td); (r/'analysis').mkdir(); (r/'planning').mkdir(); (r/'qa').mkdir()
        (r/'analysis/source_slides.json').write_text(json.dumps({'presentation':{'width_in':13.33,'height_in':7.5},'slides':[{'id':'SRC-S001','page_number':1,'roles':{'primary':'process'},'layout_family':'four_items','stats':{'shape_count':8,'picture_count':1,'text_shape_count':4},'objects':[{'source_object_id':'SRC-S001-O001','bbox':{'x':1,'y':.5,'w':5,'h':.5},'text':'Title'}]}]}))
        (r/'analysis/source_assets.json').write_text(json.dumps({'assets':[{'id':'AST-1','source_slide_id':'SRC-S001','source_object_id':'SRC-S001-O002','classification':'template_chrome','bbox':{'x':0,'y':0,'w':1,'h':.2}}]}))
        (r/'analysis/template_profile.json').write_text(json.dumps({'visual_grammar':{'fonts':[['Arial',10]],'font_sizes_pt':[[24,10]],'text_colors':[['000000',10]]}}))
        (r/'planning/deck_plan.json').write_text(json.dumps({'slides':[{'slide_id':'OUT-S001','role':'process'}]}))
        (r/'planning/visual_plan.json').write_text(json.dumps({'slides':[{'slide_id':'OUT-S001','visual_intent':{'selected_type':'flow'}}]}))
        (r/'planning/slide_matching.json').write_text(json.dumps({'slides':[{'slide_id':'OUT-S001','selected':{'source_slide_id':'SRC-S001','recommended_mode':'RECOMPOSE'}}]}))
        ds=build_design_system(r); cp=build_continuity_plans(r); qa=validate_continuity(r)
        assert ds['design_fingerprint']['typography']['preferred_fonts']==['Arial']
        assert cp['continuity_plan']['slides'][0]['inherited']['macro']
        assert qa['summary']['blocking']==0
