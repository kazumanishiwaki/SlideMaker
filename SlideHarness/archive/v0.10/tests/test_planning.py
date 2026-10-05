import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from planning import (
    compact_to_runtime,
    compile_plan_bundle,
    project_legacy_views,
    renderer_group,
    semantic_layout_issues,
    write_slide_plan_bundle,
)


class PlanningTests(unittest.TestCase):
    def _plan(self, *, relation="evidence", family="photo_text"):
        return {
            "slide_id": "OUT-S001",
            "message": "必要な機能を標準化するから、導入しやすい",
            "semantic_chunks": ["必要な機能を標準化するから、", "導入しやすい"],
            "semantic_relation": relation,
            "visual": {"type": "screenshot"},
            "source": {"slide_id": "SRC-S004", "mode": "RECOMPOSE"},
            "layout": {"family": family, "density": "medium_low", "fill_policy": "balanced", "request": {}},
            "content": {},
            "image": {"recipe_id": "IMG-OUT-S001-01"},
            "runtime": {"content_blocks": []},
            "status": "APPROVED",
            "origin": "test",
        }

    def test_renderer_groups_collapse_public_families(self):
        self.assertEqual(renderer_group("cover"), "statement")
        self.assertEqual(renderer_group("comparison_matrix"), "grid")
        self.assertEqual(renderer_group("photo_text"), "media")
        self.assertEqual(renderer_group("process"), "flow")
        self.assertEqual(renderer_group("chart"), "data")

    def test_semantic_chunks_are_compiled_as_locked_display_lines(self):
        runtime = compact_to_runtime(self._plan())
        self.assertEqual(runtime["layout_request"]["title"], "必要な機能を標準化するから、\n導入しやすい")

    def test_cause_effect_rejects_relationship(self):
        issues = semantic_layout_issues(self._plan(relation="cause_effect", family="relationship"))
        self.assertEqual(issues[0]["check_id"], "SEMANTIC_LAYOUT_FORBIDDEN")
        self.assertEqual(issues[0]["severity"], "blocking")

    def test_bundle_compiles_and_projects_derived_compatibility_views(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ("planning/slide_plans", "qa"):
                (root / rel).mkdir(parents=True, exist_ok=True)
            write_slide_plan_bundle(root, [self._plan()], status="APPROVED")
            result = compile_plan_bundle(root)
            self.assertEqual(result["blocking_count"], 0)
            views = project_legacy_views(root)
            self.assertEqual(views["visual_plan"]["slides"][0]["origin"], "derived_from_slide_plans")
            self.assertEqual(views["slide_matching"]["slides"][0]["selected"]["source_slide_id"], "SRC-S004")
            runtime = json.loads((root / "planning/slide_plans/OUT-S001.json").read_text())
            self.assertEqual(runtime["renderer_group"], "media")


if __name__ == "__main__":
    unittest.main()
