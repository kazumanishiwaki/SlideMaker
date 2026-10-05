import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from feedback import apply_feedback
from helpers import write_json
from planning import project_legacy_views, write_slide_plan_bundle
from state import PHASES, default_project_state, ensure_slide, save_state


class FeedbackTest(unittest.TestCase):
    def make(self, root: Path):
        for d in ["planning/slide_plans", "qa", "decisions", "state"]:
            (root / d).mkdir(parents=True, exist_ok=True)
        write_json(root / "planning/deck_plan.json", {
            "slides": [
                {"slide_id": "OUT-S001", "primary_message": "A"},
                {"slide_id": "OUT-S002", "primary_message": "B"},
            ]
        })
        rows = [
            {
                "slide_id": "OUT-S001", "message": "A", "semantic_chunks": [], "semantic_relation": "evidence",
                "visual": {"type": "photo"}, "source": {"slide_id": "SRC-S001", "mode": "RECOMPOSE"},
                "layout": {"family": "photo_text", "density": "medium", "fill_policy": "balanced", "request": {}},
                "content": {}, "image": {},
                "runtime": {"content_blocks": [{"id": "CB-1", "source_text": "source", "semantic_text": "semantic", "render_text": "render"}]},
                "status": "APPROVED", "origin": "test",
            },
            {
                "slide_id": "OUT-S002", "message": "B", "semantic_chunks": [], "semantic_relation": "comparison",
                "visual": {"type": "table"}, "source": {"slide_id": "SRC-S002", "mode": "RECOMPOSE"},
                "layout": {"family": "comparison_matrix", "density": "medium", "fill_policy": "content_filled", "request": {}},
                "content": {}, "image": {}, "runtime": {"content_blocks": []},
                "status": "APPROVED", "origin": "test",
            },
        ]
        write_slide_plan_bundle(root, rows, status="APPROVED")
        project_legacy_views(root)
        state = default_project_state()
        for sid in ["OUT-S001", "OUT-S002"]:
            row = ensure_slide(state, sid)
            for phase in PHASES:
                row[phase] = "APPROVED"
        state["deck_harmony"] = "APPROVED"
        save_state(root, state)

    def test_layout_change_does_not_touch_other_slide(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.make(root)
            before = json.loads((root / "planning/slide_plans/OUT-S002.json").read_text())
            out = apply_feedback(root, "OUT-S001", "layout_density", "airy")
            after = json.loads((root / "planning/slide_plans/OUT-S002.json").read_text())
            self.assertEqual(before, after)
            self.assertEqual(out["state"]["slides"]["OUT-S001"]["layout"], "STALE")
            self.assertEqual(out["state"]["slides"]["OUT-S002"]["layout"], "APPROVED")

    def test_render_text_never_changes_semantic_text(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.make(root)
            apply_feedback(root, "OUT-S001", "render_text", {"block_id": "CB-1", "text": "short"})
            bundle = json.loads((root / "planning/slide_plans.json").read_text())
            block = bundle["slides"][0]["runtime"]["content_blocks"][0]
            self.assertEqual(block["semantic_text"], "semantic")
            self.assertEqual(block["source_text"], "source")
            self.assertEqual(block["render_text"], "short")

    def test_message_stales_only_target_slide_plan_and_downstream(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.make(root)
            out = apply_feedback(root, "OUT-S001", "primary_message", "Changed")
            self.assertEqual(out["state"]["slides"]["OUT-S001"]["slide_plan"], "STALE")
            self.assertEqual(out["state"]["slides"]["OUT-S002"]["slide_plan"], "APPROVED")

    def test_user_semantic_chunks_keep_requested_break(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.make(root)
            chunks = ["必要な機能を標準化するから、", "導入しやすい"]
            apply_feedback(root, "OUT-S001", "semantic_chunks", chunks)
            runtime = json.loads((root / "planning/slide_plans/OUT-S001.json").read_text())
            self.assertEqual(runtime["layout_request"]["title"], "必要な機能を標準化するから、\n導入しやすい")


if __name__ == "__main__":
    unittest.main()
