"""Integration check for selecting, speeding and repeating only the chosen action."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from pipeline.core import ClipSegment, render_segment


class RangeRenderTest(unittest.TestCase):
    def test_loop_uses_selected_source_range_and_exact_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / 'source.mp4', root / 'out.mp4'
            subprocess.run([
                'ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=64x64:r=30:d=4',
                '-vf', "drawbox=color=blue:t=fill:enable='gte(t,2)*lt(t,3)'",
                '-c:v', 'libx264', '-g', '120', str(source)
            ], check=True)
            segment = ClipSegment(str(source), 2, 3, speed=1.2, output_duration=2, loop=True)
            render_segment(segment, output, width=64, height=64, fps=30, crf=20,
                           audio_bitrate='128k', mute_source=True)
            info = json.loads(subprocess.check_output([
                'ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries',
                'stream=duration,nb_frames', '-of', 'json', str(output)
            ]))['streams'][0]
            self.assertEqual(int(info['nb_frames']), 60)
            self.assertAlmostEqual(float(info['duration']), 2)
            pixels = subprocess.check_output([
                'ffmpeg', '-v', 'error', '-i', str(output), '-vf', 'scale=1:1',
                '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'
            ])
            for frame in (0, 28, 59):
                red, green, blue = pixels[frame*3:frame*3+3]
                self.assertGreater(blue, red + 100, f'wrong action at frame {frame}')


if __name__ == '__main__':
    unittest.main()
