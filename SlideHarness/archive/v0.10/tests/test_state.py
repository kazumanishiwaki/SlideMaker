import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from state import PHASES, default_project_state, mark_stale, save_state


class StateTests(unittest.TestCase):
    def test_stale_is_scoped_and_locked_is_preserved_as_stale_locked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "state").mkdir(); (root / "decisions").mkdir()
            state = default_project_state()
            state["slides"] = {
                "OUT-S001": {phase: "APPROVED" for phase in PHASES},
                "OUT-S002": {phase: "APPROVED" for phase in PHASES},
            }
            state["slides"]["OUT-S001"]["layout"] = "LOCKED"
            save_state(root, state)
            out = mark_stale(root, "OUT-S001", "slide_plan", "test")
            self.assertEqual(out["slides"]["OUT-S001"]["deck_plan"], "APPROVED")
            self.assertEqual(out["slides"]["OUT-S001"]["slide_plan"], "STALE")
            self.assertEqual(out["slides"]["OUT-S001"]["layout"], "STALE_LOCKED")
            self.assertTrue(all(value == "APPROVED" for value in out["slides"]["OUT-S002"].values()))
            self.assertEqual(out["deck_harmony"], "STALE")

    def test_legacy_visual_and_source_states_migrate_into_slide_plan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "state").mkdir(); (root / "decisions").mkdir()
            state = default_project_state()
            state["slides"] = {"OUT-S001": {
                "deck_plan": "APPROVED", "visual_plan": "STALE", "source_match": "APPROVED", "slide_plan": "APPROVED",
                "image": "APPROVED", "layout": "APPROVED", "render": "APPROVED", "qa": "APPROVED",
            }}
            save_state(root, state)
            saved = __import__("json").loads((root / "state/project_state.json").read_text())
            self.assertEqual(saved["slides"]["OUT-S001"]["slide_plan"], "STALE")
            self.assertNotIn("visual_plan", saved["slides"]["OUT-S001"])
            self.assertNotIn("source_match", saved["slides"]["OUT-S001"])


if __name__ == "__main__":
    unittest.main()
