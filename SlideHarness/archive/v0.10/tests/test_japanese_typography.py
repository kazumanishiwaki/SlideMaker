import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))

from japanese_typography import estimate_lines, fit_font_size, diagnose_rendered_lines, prepare_display_text


class JapaneseTypographyTests(unittest.TestCase):
    def test_title_fit_shrinks_to_two_lines_without_crossing_minimum(self):
        text = '公開準備から抽選までを一つの管理画面で安全に運用できます'
        result = fit_font_size(
            text, width_in=4.0, height_in=1.15,
            preferred_pt=38, role='title', min_pt=18, max_lines=2,
        )
        self.assertLess(result.font_pt, 38)
        self.assertGreaterEqual(result.font_pt, 18)
        self.assertTrue(result.fits)
        self.assertLessEqual(result.line_count, 2)

    def test_estimator_avoids_close_bracket_at_line_start(self):
        lines = estimate_lines('運用条件（素材・規約・実施条件）が確定している場合', 2.1, 18)
        self.assertFalse(any(line.startswith('）') for line in lines[1:]))

    def test_prepare_display_text_preserves_explicit_semantic_break(self):
        title = prepare_display_text(
            '必要な機能を標準化するから、\n導入しやすい',
            width_in=10.5914, font_pt=48, role='title', max_lines=2,
        )
        self.assertEqual(title.splitlines(), ['必要な機能を標準化するから、', '導入しやすい'])

    def test_render_diagnostics_detect_number_unit_and_kinsoku(self):
        lines = [
            [{'text': '導入費用は100'}],
            [{'text': '円です'}],
            [{'text': '）'}],
        ]
        codes = [code for code, _severity, _detail in diagnose_rendered_lines(lines, '導入費用は100 円です）', 'item_body')]
        self.assertIn('NUMBER_UNIT_SPLIT', codes)
        self.assertIn('JAPANESE_PROHIBITED_LINE_START', codes)

    def test_estimator_moves_noun_before_particle_line_start(self):
        lines = estimate_lines('テンプレートの個性を、内容に合わせて継承する', 4.5, 34)
        self.assertGreaterEqual(len(lines), 2)
        self.assertFalse(any(line.startswith('に') for line in lines[1:]))
        self.assertIn('内容に', ''.join(lines))

    def test_prepare_display_text_avoids_particle_start_and_short_body_orphan(self):
        title = prepare_display_text(
            '担当者が、同じ画面で状況を確認', width_in=4.05, font_pt=38,
            role='title', max_lines=2,
        )
        title_lines = title.splitlines()
        self.assertEqual(len(title_lines), 2)
        self.assertFalse(title_lines[1].startswith('で'))

        body = prepare_display_text(
            '情報を探し回らず、必要な内容へすぐアクセス。\n元PPTの写真処理と配色へ新しい画像を合わせます。',
            width_in=4.05, font_pt=18, role='item_body', max_lines=10,
        )
        self.assertFalse(any(len(line.replace(' ','')) <= 3 for line in body.splitlines() if line))


if __name__ == '__main__':
    unittest.main()
