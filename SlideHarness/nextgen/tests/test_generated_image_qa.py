from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest

from PIL import Image

from slideharness_next.generated_image_qa import inspect_generated_images


ROOT = Path(__file__).resolve().parents[2]
IMAGE = ROOT / "nextgen" / "examples" / "representative" / "assets" / "generated-template-system.png"


class GeneratedImageQATest(unittest.TestCase):
    def test_structured_visual_requires_declared_exact_text(self) -> None:
        report = inspect_generated_images([
            {"asset_id": "A1", "slide_id": "S001", "kind": "generated_image", "visual_kind": "flow", "status": "resolved", "resolved_path": str(IMAGE)}
        ])
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("generated_visual_missing_required_text", {item["code"] for item in report["findings"]})

    @unittest.skipUnless(shutil.which("tesseract"), "tesseract is unavailable")
    def test_required_text_is_checked_with_sparse_diagram_ocr(self) -> None:
        report = inspect_generated_images([
            {"asset_id": "A1", "slide_id": "S001", "kind": "generated_image", "visual_kind": "flow", "status": "resolved", "resolved_path": str(IMAGE), "required_text": ["Le"]}
        ])
        self.assertEqual(report["status"], "PASS", report)

    def test_small_blank_image_is_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "blank.png"
            Image.new("RGB", (200, 100), "white").save(image_path)
            report = inspect_generated_images([
                {"asset_id": "A1", "slide_id": "S001", "kind": "generated_image", "status": "resolved", "resolved_path": str(image_path)}
            ])
            codes = {item["code"] for item in report["findings"]}
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("generated_image_too_small", codes)
            self.assertIn("generated_image_nearly_blank", codes)

    def test_large_image_with_wrong_aspect_ratio_is_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "wrong-ratio.png"
            Image.effect_noise((1024, 1024), 80).convert("RGB").save(image_path)
            report = inspect_generated_images([
                {"asset_id": "A2", "slide_id": "S002", "kind": "generated_image", "status": "resolved", "resolved_path": str(image_path), "aspect_ratio": "16:9"}
            ])
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("generated_image_aspect_ratio_mismatch", {item["code"] for item in report["findings"]})


if __name__ == "__main__":
    unittest.main()
