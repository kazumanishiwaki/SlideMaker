from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from slideharness_next.composer import compose_deck
from slideharness_next.models import DeckSpec, SlideSpec
from slideharness_next.planner import plan_deck
from slideharness_next.qa import inspect_pptx
from slideharness_next.template_compiler import compile_template


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "nextgen" / "examples" / "test-case" / "inputs" / "source.pptx"
IMAGE = ROOT / "nextgen" / "examples" / "representative" / "assets" / "generated-template-system.png"


class StructuredVisualModeTest(unittest.TestCase):
    def test_generated_visual_requests_and_places_one_rich_image(self) -> None:
        deck = DeckSpec(
            "Generated flow",
            [
                SlideSpec(
                    "S001",
                    "生成フロー",
                    "3段階で処理します",
                    "generated_visual",
                    ["U1"],
                    {
                        "visual": {
                            "type": "flow",
                            "asset_id": "S001-flow",
                            "purpose": "Rich flow diagram",
                            "prompt": "Show the exact labels: 解析, 構成, 生成",
                            "required_text": ["解析", "構成", "生成"],
                            "source_url": "https://assets.example/flow-reference",
                            "source_note": "licensed reference artwork",
                        }
                    },
                )
            ],
        )
        plans = plan_deck(deck)
        self.assertEqual(plans[0].recipe, "generated_visual")
        self.assertEqual(plans[0].asset_requests[0]["visual_kind"], "flow")
        self.assertEqual(plans[0].asset_requests[0]["required_text"], ["解析", "構成", "生成"])
        self.assertEqual(
            plans[0].asset_requests[0]["source_url"],
            "https://assets.example/flow-reference",
        )
        self.assertEqual(
            plans[0].asset_requests[0]["source_note"],
            "licensed reference artwork",
        )
        with TemporaryDirectory() as directory:
            output = Path(directory) / "generated-flow.pptx"
            compose_deck(
                TEMPLATE,
                deck,
                plans,
                compile_template(TEMPLATE),
                output,
                {"S001-flow": IMAGE},
            )
            generated_report = inspect_pptx(
                output,
                plans,
                structured_visual_mode="generated-image",
            )
            self.assertEqual(generated_report["status"], "PASS", generated_report["findings"])
            native_report = inspect_pptx(output, plans, structured_visual_mode="native")
            self.assertEqual(native_report["status"], "FAIL")
            self.assertIn("structured_visual_not_native", {item["code"] for item in native_report["findings"]})


if __name__ == "__main__":
    unittest.main()
