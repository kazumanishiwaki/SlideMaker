from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from slideharness_next.assets import resolve_asset_requests


class AssetResolutionTest(unittest.TestCase):
    def test_fallback_images_are_not_reused_by_default(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            spec = root / "deck_spec.json"
            spec.write_text("{}", encoding="utf-8")
            explicit = root / "explicit.png"
            preview = root / "preview.png"
            explicit.write_bytes(b"explicit")
            preview.write_bytes(b"preview")
            plans = [
                SimpleNamespace(
                    asset_requests=[
                        {"asset_id": "A-1"},
                        {"asset_id": "A-2"},
                        {"asset_id": "A-3"},
                    ]
                )
            ]

            assets, requests = resolve_asset_requests(plans, spec, root, {}, explicit, preview)

            self.assertEqual(assets, {"A-1": explicit.resolve(), "A-2": preview.resolve()})
            self.assertEqual([item["status"] for item in requests], ["resolved", "resolved", "awaiting_image"])
            self.assertEqual(requests[2]["reason"], "duplicate_image_reuse_blocked")
            self.assertIn(requests[2]["conflicts_with_asset_id"], {"A-1", "A-2"})

    def test_reuse_requires_an_explicit_request_flag(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "shared.png"
            image.write_bytes(b"shared")
            plans = [
                SimpleNamespace(
                    asset_requests=[
                        {"asset_id": "A-1"},
                        {"asset_id": "A-2", "allow_reuse": True},
                    ]
                )
            ]

            assets, requests = resolve_asset_requests(
                plans,
                root / "deck_spec.json",
                root,
                {"A-1": image, "A-2": image},
                None,
                None,
            )

            self.assertEqual(set(assets), {"A-1", "A-2"})
            self.assertTrue(all(item["status"] == "resolved" for item in requests))


if __name__ == "__main__":
    unittest.main()
