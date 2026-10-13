# Usage reference

Run commands from the project root:

```powershell
python -m pipeline --input input --output output\final.mp4
```

Optional features:

```powershell
python -m pipeline --input input --music assets\bgm.mp3 --output output\final.mp4
python -m pipeline --input input --subtitle subtitles\main.srt --output output\final.mp4
python -m pip install -e '.[transcribe]'
python -m pipeline --input input --transcribe --whisper-model base --output output\final.mp4
python -m pipeline --input input --dry-run
python -m pip install -e '.[draft]'
python -m pipeline --input input --plan plan.json --draft output/editable-project
python -m pipeline --input input --plan plan.json --draft output/editable-project --draft-only
```

`plan.json` accepts either one range per clip or multiple ranges:

```json
{
  "clips": [
    {"file": "talk.mp4", "start": 1.2, "end": 5.8},
    {"file": "broll.mov", "keep": [[0, 3.1], [7.4, 12.0]]}
  ]
}
```

Paths in a plan are relative to `--input`. Passing `--plan` disables automatic silence detection and uses only the listed ranges.

Editing parameters are never automatic visible text. Use `title` for action labels and `--heading` for a series heading. Editable drafts include independently encoded 1x action assets with native timeline speeds, separate text tracks and a music track. Share the whole folder, close Jianying, run its bundled `双击导入.cmd`, then reopen Jianying. A custom draft root can be provided with `python 导入草稿.py --root PATH`.
