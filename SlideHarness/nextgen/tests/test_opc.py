import unittest

from slideharness_next.opc import (
    relationship_is_external,
    relationship_part_path,
    relationship_records,
    relationship_source_part,
    resolve_relationship_target,
)


class OpcRelationshipTest(unittest.TestCase):
    def test_relationship_part_paths_round_trip(self) -> None:
        part = "ppt/slides/slide1.xml"
        rels = "ppt/slides/_rels/slide1.xml.rels"
        self.assertEqual(relationship_part_path(part), rels)
        self.assertEqual(relationship_source_part(rels), part)
        self.assertEqual(relationship_source_part("_rels/.rels"), "")

    def test_target_resolution_handles_encoded_and_absolute_paths(self) -> None:
        self.assertEqual(
            resolve_relationship_target("ppt/slides/slide1.xml", "../media/image%201.png"),
            "ppt/media/image 1.png",
        )
        self.assertEqual(
            resolve_relationship_target("ppt/slides/slide1.xml", "/ppt/theme/theme1.xml"),
            "ppt/theme/theme1.xml",
        )

    def test_external_mode_is_case_insensitive_and_not_resolved(self) -> None:
        payload = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="hyperlink" Target="https://example.com/a%20b" TargetMode="external"/>
</Relationships>'''
        records = relationship_records(payload, "ppt/slides/_rels/slide1.xml.rels")
        self.assertEqual(records[0]["resolved"], "https://example.com/a%20b")
        self.assertTrue(relationship_is_external(records[0]))


if __name__ == "__main__":
    unittest.main()
