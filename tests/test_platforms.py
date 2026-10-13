"""Mac store discovery and native Chinese overlays; no real user store mutations."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.draft_install import default_draft_root
from pipeline.enhancements import find_font, make_element


class PlatformTest(unittest.TestCase):
    def test_mac_store_discovery_uses_existing_store_or_requires_explicit_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch('pipeline.draft_install.sys.platform', 'darwin'), patch.object(Path, 'home', return_value=home):
                with self.assertRaisesRegex(RuntimeError, '指定'):
                    default_draft_root()
                self.assertFalse((home/'Movies').exists())
                store = home/'Movies/CapCut/User Data/Projects/com.lveditor.draft'
                store.mkdir(parents=True)
                self.assertEqual(default_draft_root(), store)
                preferred = home/'Movies/JianyingPro/User Data/Projects/com.lveditor.draft'
                preferred.mkdir(parents=True)
                self.assertEqual(default_draft_root(), preferred)

    @unittest.skipUnless(sys.platform == 'darwin', 'native Mac font test')
    def test_system_font_renders_chinese_label(self):
        self.assertTrue(Path(find_font('自动剪辑')).is_file())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'label.png'
            w, h = make_element({'type':'label','text':'自动剪辑','size':.8}, path, 320)
            self.assertGreater(w, 50)
            self.assertGreater(h, 15)
            from PIL import Image
            pixels = Image.open(path).convert('RGBA').getdata()
            self.assertGreater(sum(1 for r,g,b,a in pixels if r>200 and g>200 and b>200 and a>0), 40)

    @unittest.skipUnless(sys.platform == 'darwin', 'Mac process test')
    def test_running_mac_editor_blocks_import(self):
        from pipeline.draft_install import ensure_editor_closed
        with patch('pipeline.draft_install.subprocess.check_output', return_value='/Applications/剪映专业版.app/Contents/MacOS/JianyingPro\n'):
            with self.assertRaisesRegex(RuntimeError, '退出'):
                ensure_editor_closed()
