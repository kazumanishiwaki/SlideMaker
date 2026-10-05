from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from slideharness_next.architect import _short_heading, build_deterministic_deck, validate_deck_against_sources
from slideharness_next.content_modeler import build_coverage_requirements
from slideharness_next.ingest import ingest_sources
from slideharness_next.models import DeckSpec, SlideSpec


class ArchitectTest(unittest.TestCase):
    def test_fallback_headings_keep_the_semantic_noun_phrase_compact(self) -> None:
        self.assertEqual(_short_heading("標準ページの意味ある占有率は55〜85%とします。"), "意味ある占有率")
        self.assertEqual(_short_heading("説明できない連続空白が35%を超えるページは出力を停止します。"), "連続空白")
        self.assertEqual(_short_heading("未解決画像がある状態を完成として扱うことは禁止します。"), "未解決画像")
        self.assertEqual(_short_heading("内容量に合う具体的なSlide Recipeを選択します。"), "Slide Recipeを選択")

    def test_fallback_plan_covers_every_source_unit_and_exact_fact(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "brief.md"
            source.write_text(
                "# Product\n\nOverview text.\n\n## Flow\n\n1. Plan\n2. Build\n3. Review\n\n## Terms\n\n- 料金は10万円です。\n- 対象は3社です。\n",
                encoding="utf-8",
            )
            bundle = ingest_sources([source])
            requirements = build_coverage_requirements(bundle)
            deck = build_deterministic_deck(bundle)
            coverage, report = validate_deck_against_sources(deck, bundle, requirements)
            self.assertEqual(report["status"], "PASS", report["findings"])
            self.assertEqual(coverage["all_unit_coverage"], 1.0)
            self.assertIn("process", [slide.recipe for slide in deck.slides])

    def test_missing_required_unit_stops_content_validation(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "brief.md"
            source.write_text("# Product\n\n料金は10万円です。\n", encoding="utf-8")
            bundle = ingest_sources([source])
            requirements = build_coverage_requirements(bundle)
            root_id = bundle.units[0].unit_id
            deck = DeckSpec("Product", [SlideSpec("S001", "Product", "", "cover", [root_id], {})])
            _, report = validate_deck_against_sources(deck, bundle, requirements)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any(item["code"] == "missing_required_unit" for item in report["findings"]))


if __name__ == "__main__":
    unittest.main()
