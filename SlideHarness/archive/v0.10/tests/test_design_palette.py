import json
import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))

from design_continuity import build_design_system
from layout_engine import _theme


class DesignPaletteTests(unittest.TestCase):
    def _minimal_docs(self, root: Path):
        (root / 'analysis').mkdir(parents=True)
        (root / 'render/source_renders').mkdir(parents=True)
        (root / 'analysis/source_slides.json').write_text(json.dumps({
            'presentation': {'width_in': 13.333, 'height_in': 7.5},
            'slides': [
                {'id': 'SRC-S001', 'roles': {'primary': 'cover'}, 'layout_family': 'cover', 'stats': {}, 'objects': []},
                {'id': 'SRC-S002', 'roles': {'primary': 'statement'}, 'layout_family': 'statement', 'stats': {}, 'objects': []},
            ],
        }), encoding='utf-8')
        (root / 'analysis/source_assets.json').write_text(json.dumps({'assets': []}), encoding='utf-8')
        (root / 'analysis/template_profile.json').write_text(json.dumps({'visual_grammar': {'fonts': [], 'font_sizes_pt': [], 'text_colors': []}}), encoding='utf-8')

    def test_render_palette_finds_brand_accent_and_slide_tone(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._minimal_docs(root)
            maroon = (80, 0, 0)
            light = Image.new('RGB', (1200, 675), 'white')
            draw = ImageDraw.Draw(light)
            draw.rectangle((0, 0, 1200, 100), fill=maroon)
            light.save(root / 'render/source_renders/SRC-S001.png')
            dark = Image.new('RGB', (1200, 675), maroon)
            dark.save(root / 'render/source_renders/SRC-S002.png')

            result = build_design_system(root)
            roles = result['design_fingerprint']['color_roles']
            self.assertEqual(roles['primary_accent'], '500000')
            tones = {row['source_slide_id']: row for row in roles['source_slide_tones']}
            self.assertFalse(tones['SRC-S001']['background_is_dark'])
            self.assertTrue(tones['SRC-S002']['background_is_dark'])
            self.assertEqual(_theme(root, 'SRC-S001')['page_text'], '171717')
            self.assertEqual(_theme(root, 'SRC-S002')['page_text'], 'FFFFFF')
            self.assertTrue(result['design_fingerprint']['image_treatment']['target_metrics'])

    def test_selected_source_ids_and_neutral_brand_palette_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._minimal_docs(root)
            gray = (88, 92, 96)
            canvas = Image.new('RGB', (1200, 675), 'white')
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((0, 0, 1200, 120), fill=gray)
            draw.rectangle((0, 625, 1200, 675), fill=gray)
            canvas.save(root / 'render/source_renders/SRC-S014.png')

            result = build_design_system(root)
            roles = result['design_fingerprint']['color_roles']
            tones = {row['source_slide_id']: row for row in roles['source_slide_tones']}
            self.assertIn('SRC-S014', tones)
            self.assertNotIn('SRC-S001', tones)
            self.assertNotEqual(roles['primary_accent'], 'FF9A42')
            self.assertEqual(roles['primary_accent'], '585C60')


if __name__ == '__main__':
    unittest.main()
