"""Observable timing, image composition, mix and portable draft behavior."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.cli import main
from pipeline.core import PipelineError, run_command
from pipeline.enhancements import assemble, settings, sound_track
from pipeline.speech import captions_from_words, synthesize


class CaptionTest(unittest.TestCase):
    def test_words_keep_original_punctuation_and_no_overlaps(self):
        text = "你好，AI！欢迎使用。"
        words = [{"text": s, "offset": i * 5_000_000, "duration": 3_000_000}
                 for i, s in enumerate(["你好", "AI", "欢迎", "使用"])]
        captions = captions_from_words(text, words)
        self.assertEqual("".join(c["text"] for c in captions), text)
        self.assertTrue(all(a["end"] <= b["start"] for a, b in zip(captions, captions[1:])))
        with self.assertRaises(PipelineError):
            captions_from_words("不同文字", words)
        with self.assertRaises(PipelineError):
            captions_from_words(text, [words[0], {**words[1], "offset": 0}, *words[2:]])

    @unittest.skipUnless(importlib.util.find_spec("edge_tts"), "optional voice extra")
    def test_one_full_text_request_and_no_robotic_fallback(self):
        text = "你好，欢迎使用。"
        calls = []
        words = [{"type": "WordBoundary", "text": s, "offset": i*5_000_000, "duration": 3_000_000}
                 for i, s in enumerate(["你好", "欢迎", "使用"])]
        class FakeVoice:
            silent = False
            def __init__(self, full_text, **options):
                calls.append((full_text, options))
            async def stream(self):
                if not self.silent:
                    yield {"type": "audio", "data": b"mock-audio"}
                for word in words:
                    yield word
        async def no_wait(_):
            pass
        with tempfile.TemporaryDirectory() as directory, patch("edge_tts.Communicate", FakeVoice), \
                patch("pipeline.speech.duration_of", return_value=2), patch("pipeline.speech.asyncio.sleep", no_wait):
            target = Path(directory) / "voice.mp3"
            _, srt = synthesize(text, target)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], text)
            self.assertEqual(calls[0][1]["voice"], "zh-CN-YunjianNeural")
            self.assertIn("你好", srt.read_text(encoding="utf-8"))
            FakeVoice.silent = True
            failed = Path(directory) / "failed.mp3"
            with self.assertRaisesRegex(PipelineError, "不会降级"):
                synthesize(text, failed)
            self.assertFalse(failed.exists())
            self.assertFalse(failed.with_suffix(".part").exists())


class EffectsTest(unittest.TestCase):
    def test_transition_has_blended_frame_and_exact_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = []
            for color in ("red", "blue"):
                file = root / f"{color}.mp4"
                run_command(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color={color}:s=64x64:r=30:d=1",
                             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "1", "-c:v", "libx264", "-c:a", "aac", str(file)])
                files.append(file)
            output = root / "fade.mp4"
            total = assemble(files, output, {"name": "fade", "duration": .4}, 30, 18)
            self.assertAlmostEqual(total, 1.6)
            info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=nb_frames", "-of", "json", str(output)]))
            self.assertEqual(int(info["streams"][0]["nb_frames"]), 48)
            pixels = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(output), "-vf", "select=eq(n\\,24),scale=1:1", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
            self.assertGreater(pixels[0], 60)
            self.assertGreater(pixels[2], 60)

    def test_local_sound_is_delayed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "sound.wav"
            sound_track([{"name": "ding", "start": .5, "volume": .4}], target, root, 1.5)
            import wave, array
            with wave.open(str(target)) as audio:
                samples = array.array("h", audio.readframes(audio.getnframes()))
                self.assertEqual(audio.getnframes(), 72000)
                self.assertEqual(max(abs(x) for x in samples[:int(.45*48000*2)]), 0)
                self.assertGreater(max(abs(x) for x in samples[int(.5*48000*2):]), 1000)

    @unittest.skipUnless(importlib.util.find_spec("pyJianYingDraft") and importlib.util.find_spec("PIL"), "optional draft/visual extras")
    def test_voice_extends_picture_and_rich_draft_keeps_captions_and_stems(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_command(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=blue:s=320x240:r=30:d=2", "-c:v", "libx264", str(root/"source.mp4")])
            run_command(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=3.4", str(root/"voice.wav")])
            (root/"captions.srt").write_text("1\n00:00:00,200 --> 00:00:02,800\nHello AI\n", encoding="utf-8")
            plan = {"clips": [{"file": "source.mp4", "end": 1, "filter": "warm", "effects": ["zoom_in", "vignette"]},
                              {"file": "source.mp4", "start": 1, "end": 2}],
                    "transition": {"name": "fade", "duration": .2},
                    "narration": {"audio": "voice.wav", "subtitles": "captions.srt"},
                    "elements": [{"type": "icon", "name": "check", "start": .1, "end": .9, "size": .3, "x": .1, "y": .1},
                                 {"type": "label", "text": "Auto edit", "start": 1, "end": 3, "x": .1, "y": .4}],
                    "sound_effects": [{"name": "pop", "start": 1.0}]}
            (root/"plan.json").write_text(json.dumps(plan), encoding="utf-8")
            code = main(["--input", str(root), "--plan", str(root/"plan.json"), "--output", str(root/"out.mp4"),
                         "--work", str(root/"work"), "--draft", str(root/"draft"), "--music", str(root/"voice.wav"),
                         "--mute-source", "--width", "320", "--height", "240"])
            self.assertEqual(code, 0)
            data = json.loads((root/"draft/draft_content.json").read_text(encoding="utf-8"))
            self.assertEqual(data["duration"], 3_400_000)
            self.assertEqual(len(data["tracks"]), 5)
            self.assertEqual(len(data["materials"]["texts"]), 1)
            self.assertTrue((root/"out.narration.wav").is_file())
            self.assertTrue((root/"out.srt").is_file())
            # Icon is present only at the scheduled first shot time.
            frame = root/"frame.rgb"
            run_command(["ffmpeg", "-y", "-v", "error", "-i", str(root/"out.mp4"), "-vf", "select=eq(n\\,15)",
                         "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", str(frame)])
            pixels = frame.read_bytes()
            self.assertGreater(sum(1 for i in range(0, len(pixels), 3) if min(pixels[i:i+3]) > 180), 100)
            from pipeline.draft_install import relocate
            import shutil
            moved = root/"moved"
            shutil.copytree(root/"draft", moved)
            relocated = relocate(data, moved)
            for kind in ("videos", "audios"):
                self.assertTrue(all(Path(m["path"]).resolve().is_relative_to(moved.resolve()) and Path(m["path"]).is_file() for m in relocated["materials"][kind]))

    def test_invalid_configuration_fails(self):
        for config in ({"transition": {"name": "unknown"}}, {"elements": [{"type": "icon", "name": "unknown"}]},
                       {"sound_effects": [{"name": "ding", "start": float("nan")}]},
                       {"narration": {"text": "a", "audio": "does-not-exist.wav"}}):
            with self.assertRaises(PipelineError):
                settings(config, Path.cwd())
