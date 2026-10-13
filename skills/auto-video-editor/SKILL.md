---
name: auto-video-editor
description: "Run the local video editing pipeline with clip plans, continuous narration, timed captions, music, transitions, overlays, filters, sound effects and Jianying drafts."
---

# Auto Video Editor

Use this skill when the user asks Codex to automatically edit local videos, batch render, remove silence, produce vertical video, add subtitles/music, or create and execute a `plan.json`.

## Execution

1. Locate the source workspace, a Windows release with `auto-edit.exe`, or a Mac app with `/Applications/AutoVideoEditor.app/Contents/MacOS/auto-edit` (or `./auto-edit` in its unpacked ZIP).
2. Prefer `python -m pipeline` from source, the platform's packaged CLI, or `auto-edit` for an installed Python package. Check `--version` and `--help` when options are uncertain; enhancements require 0.4.0+, native Mac apps require 0.4.1+. Desktop packages include narration, visuals and drafts but not Whisper transcription.
3. Treat `input/` as the default source directory, `output/final.mp4` as the default result, and `work/` as temporary files. Create missing directories before running.
4. Use the simplest command that satisfies the request. The default pipeline removes longer silent sections, converts to 1080x1920, and writes an MP4 plus a manifest.
5. If the user supplies exact source ranges or asks an AI to select shots, create a `plan.json` with relative paths and seconds, then run with `--plan`. Do not claim semantic video understanding unless an actual analysis step was run.
6. For automatic subtitles, install/use the optional `faster-whisper` extra only when requested, and explain that the first run may download a model.
7. After rendering, verify the output file exists and inspect it with `ffprobe` when available. Report the absolute output path and the manifest path.
8. Treat duration, speed, dimensions and other editing parameters as instructions to the editor. Never add them as visible text unless the user explicitly requests it. Use `title` only for audience-facing labels.
9. For an editable Jianying project, install the optional `draft` extra in Python (included in desktop packages) and add `--draft output/project-name`. Use `--draft-only` to omit the final MP4. Share the entire folder and assets; import with `--install-draft PATH` after closing Jianying. On Mac, use `--draft-root` when the store is custom or not detected; GUI import lets the user select it. Mac uses its CLI, not the draft's Windows `.cmd`. Verify actual Jianying compatibility when possible and report limits.
10. For voice-over, write a conversational whole-script TXT or `narration.text`; use continuous neural synthesis (`mature` is Yunjian), not separate subtitle snippets or a mechanical system voice. A preview can be generated with `--narration-text FILE --voice mature --voice-preview OUTPUT.mp3`. Listen when an audio playback/inspection capability exists; otherwise supply the preview and state that delivery has not been auditioned. Do not promise human expressiveness from technical checks alone. Narration sends only script text to Microsoft's online voice service; an existing recording plus SRT works offline. Do not upload video for speech synthesis.
11. For richer editing, use supported presets and timed elements from [references/enhancements.md](references/enhancements.md). Keep effects consistent with the content and the user's requested density. Element/SFX/caption times refer to the final timeline after transition overlaps. If narration outlasts video, extend the last frame or set `fit=error`; keep the chosen natural speech rate.

## Boundaries

- Basic drafts keep native action speed and separate titles/music. Enhanced drafts bake transitions, filters, icons, labels, clip titles and effects into the picture, with narration, global captions, music and SFX independently editable. Describe that distinction when delivering drafts. `--draft-only` still renders enhanced pictures locally. Legacy `--subtitle`/transcription draft support remains unavailable; use `narration.subtitles` for global SRT. Import requires closing Jianying; desktop export is not automated.
- Keep local media local; do not upload it to an external service unless the user explicitly requests that destination.
- For music, copyrighted assets, and public publishing, ask the user to provide or confirm the source when that choice affects the result.
- If no video files are present, give the exact `input/` path and a one-command example instead of failing silently.

See [references/usage.md](references/usage.md) for command patterns and the plan schema.
