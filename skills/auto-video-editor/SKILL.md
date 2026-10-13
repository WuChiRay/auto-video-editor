---
name: auto-video-editor
description: "Run the local automatic video editing pipeline for trimming, vertical rendering, subtitles, music, batch processing, and AI-generated clip plans."
---

# Auto Video Editor

Use this skill when the user asks Codex to automatically edit local videos, batch render, remove silence, produce vertical video, add subtitles/music, or create and execute a `plan.json`.

## Execution

1. Locate the workspace containing `pipeline/cli.py` and `pyproject.toml`, or a downloaded release containing `auto-edit.exe`.
2. Prefer `python -m pipeline` from a source workspace, `auto-edit.exe` from a Windows release, or `auto-edit` for an installed Python package. Run `--help` if available options are uncertain. The Windows executable includes draft support but not transcription.
3. Treat `input/` as the default source directory, `output/final.mp4` as the default result, and `work/` as temporary files. Create missing directories before running.
4. Use the simplest command that satisfies the request. The default pipeline removes longer silent sections, converts to 1080x1920, and writes an MP4 plus a manifest.
5. If the user supplies exact source ranges or asks an AI to select shots, create a `plan.json` with relative paths and seconds, then run with `--plan`. Do not claim semantic video understanding unless an actual analysis step was run.
6. For automatic subtitles, install/use the optional `faster-whisper` extra only when requested, and explain that the first run may download a model.
7. After rendering, verify the output file exists and inspect it with `ffprobe` when available. Report the absolute output path and the manifest path.
8. Treat duration, speed, dimensions and other editing parameters as instructions to the editor. Never add them as visible text unless the user explicitly requests it. Use `title` only for audience-facing labels.
9. For an editable Jianying project, install the optional `draft` extra in the Python version (already included in the Windows release) and add `--draft output/project-name`. Use `--draft-only` to export without rerendering. Include the entire folder and assets when sharing; import with `--install-draft PATH` after closing Jianying. Verify in the installed Jianying version when possible and report any compatibility limit.

## Boundaries

- The optional Jianying adapter creates independent video/text/music tracks. Draft import requires closing Jianying, running the bundled installer, then opening the new local draft. It does not automate desktop export. External SRT/transcription subtitles are not yet supported by this adapter.
- Keep local media local; do not upload it to an external service unless the user explicitly requests that destination.
- For music, copyrighted assets, and public publishing, ask the user to provide or confirm the source when that choice affects the result.
- If no video files are present, give the exact `input/` path and a one-command example instead of failing silently.

See [references/usage.md](references/usage.md) for command patterns and the plan schema.
