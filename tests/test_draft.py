"""Check native editing and portable paths using real generated media."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from pipeline.core import ClipSegment
from pipeline.draft_install import relocate
from pipeline.jianying import export_draft


@unittest.skipUnless(importlib.util.find_spec('pyJianYingDraft'), 'optional draft extra')
class DraftExportTest(unittest.TestCase):
    def test_selected_media_native_speed_and_portable_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.mp4'
            subprocess.run([
                'ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=64x64:r=30:d=4',
                '-vf', "drawbox=color=blue:t=fill:enable='gte(t,2)*lt(t,3)'",
                '-c:v', 'libx264', '-g', '120', str(source)
            ], check=True)
            folder = export_draft([
                ClipSegment(str(source), 2, 3, speed=1.2, output_duration=2,
                            loop=True, title='动作标题')
            ], root / 'portable', width=64, height=64, fps=30, mute_source=True)
            data = json.loads((folder / 'draft_content.json').read_text(encoding='utf-8'))
            self.assertEqual(data['duration'], 2_000_000)
            video = data['tracks'][0]['segments']
            self.assertEqual(sum(s['target_timerange']['duration'] for s in video), 2_000_000)
            self.assertTrue(all(abs(s['speed'] - 1.2) < 1e-5 for s in video))
            self.assertEqual(len(data['materials']['texts']), 1)
            self.assertEqual(json.loads(data['materials']['texts'][0]['content'])['text'], '动作标题')
            asset = folder / 'assets/action_01.mp4'
            pixels = subprocess.check_output([
                'ffmpeg', '-v', 'error', '-i', str(asset), '-frames:v', '1',
                '-vf', 'scale=1:1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'
            ])
            self.assertGreater(pixels[2], pixels[0] + 100)
            import shutil
            moved = root / 'other-computer' / 'project'
            shutil.copytree(folder, moved)
            relocated = relocate(data, moved)
            for material in relocated['materials']['videos']:
                # Windows runner TEMP can use a junction/short path alias.
                self.assertTrue(Path(material['path']).resolve().is_relative_to(moved.resolve()),
                                (material['path'], str(moved.resolve())))
                self.assertTrue(Path(material['path']).is_file())
            self.assertIn(b'python install_draft.py', (folder / '双击导入.cmd').read_bytes())
