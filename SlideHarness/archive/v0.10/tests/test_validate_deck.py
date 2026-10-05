import json, tempfile, unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from validate_deck import validate_deck


class ValidateDeckTests(unittest.TestCase):
    def test_reports_repeated_layout_without_auto_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            for d in ['planning/slide_plans','analysis','qa']:
                (p/d).mkdir(parents=True,exist_ok=True)
            slides=[]; visuals=[]; matches=[]
            for i in range(1,4):
                sid=f'OUT-S{i:03d}'
                slides.append({'slide_id':sid,'order':i,'primary_message':f'Message {i}'})
                visuals.append({'slide_id':sid,'visual_intent':{'selected_type':'photo'}})
                matches.append({'slide_id':sid,'selected':{'source_slide_id':'SRC-S001'}})
            (p/'planning/deck_plan.json').write_text(json.dumps({'slides':slides}))
            (p/'planning/visual_plan.json').write_text(json.dumps({'slides':visuals}))
            (p/'planning/slide_matching.json').write_text(json.dumps({'slides':matches}))
            (p/'analysis/source_slides.json').write_text(json.dumps({'slides':[{'id':'SRC-S001','layout_family':'photo_grid'}]}))
            result=validate_deck(p)
            self.assertEqual(result['status'],'pass')
            self.assertEqual(result['warning_count'],1)
            self.assertEqual(result['checks'][1]['check_id'],'REPEATED_LAYOUT_SEQUENCE')

    def test_prefers_generated_layout_plan_over_source_layout_family(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            for d in ['planning/slide_plans','render/layout_plans','analysis','qa']:
                (p/d).mkdir(parents=True,exist_ok=True)
            slides=[]; visuals=[]; matches=[]
            families=['cover','timeline','kpi']
            for i,family in enumerate(families,1):
                sid=f'OUT-S{i:03d}'
                slides.append({'slide_id':sid,'order':i,'primary_message':f'Message {i}'})
                visuals.append({'slide_id':sid,'visual_intent':{'selected_type':family}})
                matches.append({'slide_id':sid,'selected':{'source_slide_id':'SRC-S001'}})
                (p/f'planning/slide_plans/{sid}.json').write_text(json.dumps({'layout_request':{'family':family,'density':'medium_low'}}))
                (p/f'render/layout_plans/{sid}.json').write_text(json.dumps({'family':family,'density':'medium_low'}))
            (p/'planning/deck_plan.json').write_text(json.dumps({'slides':slides}))
            (p/'planning/visual_plan.json').write_text(json.dumps({'slides':visuals}))
            (p/'planning/slide_matching.json').write_text(json.dumps({'slides':matches}))
            (p/'analysis/source_slides.json').write_text(json.dumps({'slides':[{'id':'SRC-S001','layout_family':'statement'}]}))
            result=validate_deck(p)
            self.assertEqual(result['sequences']['layout_families'],families)
            self.assertFalse(any(c['check_id']=='REPEATED_LAYOUT_SEQUENCE' for c in result['checks']))


if __name__=='__main__': unittest.main()
