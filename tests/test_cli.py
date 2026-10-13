import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.cli import main


class CliValidationTest(unittest.TestCase):
    def test_invalid_resolution_fails_before_loading_media(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--width', '721']), 2)

    def test_source_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'sample.mp4'
            source.write_bytes(b'original-video')
            plan = root / 'plan.json'
            plan.write_text(json.dumps({'clips':[{'file':'sample.mp4','start':0,'end':1}]}))
            with patch('pipeline.core.duration_of', return_value=5), contextlib.redirect_stderr(io.StringIO()):
                result = main(['--input', str(root), '--plan', str(plan), '--output', str(source),
                               '--work', str(root / 'work')])
            self.assertEqual(result, 2)
            self.assertEqual(source.read_bytes(), b'original-video')
