from pathlib import Path
import re
import unittest

from slideharness_next.template_compiler import build_template_risk_report, compile_template


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "nextgen" / "examples" / "test-case" / "inputs" / "source.pptx"


class TemplateCompilerTest(unittest.TestCase):
    def test_compiles_real_template_into_tokens_layouts_and_patterns(self) -> None:
        system = compile_template(TEMPLATE)
        self.assertGreater(system.slide_count, 0)
        self.assertGreater(system.slide_width_in, 0)
        self.assertTrue(re.fullmatch(r"[0-9A-F]{6}", system.tokens.primary))
        self.assertTrue(system.tokens.heading_font)
        self.assertGreater(len(system.layouts), 0)
        self.assertIn("native_bar_chart", system.pattern_evidence["supported_recipes"])
        report = build_template_risk_report(system)
        self.assertIn(report["risk_level"], {"low", "medium", "high"})
        self.assertIn(report["template_mode"], {"completed_slide_heavy", "master_layout_led"})


if __name__ == "__main__":
    unittest.main()
