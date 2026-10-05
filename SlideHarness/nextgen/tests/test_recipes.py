import unittest

from slideharness_next.models import SlideSpec
from slideharness_next.recipes import choose_recipe, plan_slide


class RecipeTest(unittest.TestCase):
    def test_auto_selection_uses_semantic_content(self) -> None:
        cases = [
            ({"cards": [{"heading": "A"}]}, "card_grid_2x2"),
            ({"steps": [{"heading": "A"}]}, "process"),
            ({"chart": {"categories": [], "series": []}}, "native_chart"),
            ({"image": {"prompt": "x"}}, "image_text"),
            ({"columns": ["A"], "rows": [["B"]]}, "table"),
        ]
        for content, expected in cases:
            with self.subTest(expected=expected):
                spec = SlideSpec("S001", "Title", "Message", content=content)
                self.assertEqual(choose_recipe(spec), expected)
                self.assertEqual(plan_slide(spec).recipe, expected)

    def test_unknown_explicit_recipe_is_rejected(self) -> None:
        spec = SlideSpec("S001", "Title", "Message", recipe="mystery")
        with self.assertRaises(ValueError):
            plan_slide(spec)


if __name__ == "__main__":
    unittest.main()
