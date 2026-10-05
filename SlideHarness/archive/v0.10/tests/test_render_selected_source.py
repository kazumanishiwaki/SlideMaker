import shutil
import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from render_source import render_selected_source_slides


@unittest.skipUnless(shutil.which('libreoffice') or shutil.which('soffice'), 'LibreOffice not available')
class SelectedSourceRenderTests(unittest.TestCase):
    def test_renders_only_requested_pages_with_original_ids(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'renders'
            rows=render_selected_source_slides(ROOT/'examples/test-case/inputs/source.pptx',[2,14],out)
            self.assertEqual([Path(x).name for x in rows],['SRC-S002.png','SRC-S014.png'])
            self.assertFalse((out/'SRC-S001.png').exists())

if __name__=='__main__': unittest.main()
