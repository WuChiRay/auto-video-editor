# Enhanced plans, 0.4.0+

Python dependencies: `pip install '.[draft,voice,visual]'`. Windows release includes these. FFmpeg remains separately installed.

```json
{
  "clips": [
    {"file":"sample.mp4","start":0,"end":4,"filter":"warm","effects":["zoom_in"]},
    {"file":"sample.mp4","start":4,"end":8,"filter":"vivid"}
  ],
  "narration":{"text":"把想法告诉 AI，让它帮你完成剪辑。","voice":"mature","rate":"+4%","fit":"extend_last"},
  "transition":{"name":"fade","duration":0.35},
  "elements":[
    {"type":"label","text":"AI 自动剪辑","start":0.4,"end":3,"x":0.08,"y":0.2,"size":0.75},
    {"type":"icon","name":"check","start":4,"end":6,"x":0.1,"y":0.3,"size":0.12}
  ],
  "sound_effects":[{"name":"whoosh","start":3.6,"volume":0.2}]
}
```

`clips[].file` is input-relative. Auxiliary text/audio/SRT/image/font paths are plan-relative. Global element/SFX/caption times use the final, overlapping timeline; each transition reduces total duration by its duration (frame-rounded). Transition duration must be smaller than half of every clip. `--dry-run` cannot determine narration duration before synthesis.

Narration: choose one of `text`, `text_file`, `audio`; optional `subtitles` for a globally timed SRT. Voices: mature/warm/steady/female or a supported neural voice ID. Default mature Yunjian was live verified; other presets need auditioning. Rate/pitch default +4%/+0Hz. Limit whole-script synthesis to 3000 UTF-8 bytes to avoid transport chunking. `fit=extend_last` freezes the final frame if needed; `error` stops instead. Failures stop after two provider attempts without a robotic fallback. Output retains preview audio, SRT and generated word timings.

Available transitions: cut/fade/wipeleft/slideright/circleopen/dissolve. Filters: none/warm/cool/mono/vivid/cinematic. Clip effects: zoom_in/vignette/fade. Built-in icons: check/play/bolt/heart/download/code. Sounds: whoosh/pop/click/ding or `file` plus `start`/`volume`.

Elements: `type=label` with `text`, `type=icon` with `name`, or `type=image` with `file`. Positions `x/y` are top-left fractions of the frame; `size` is a maximum width fraction (images also have bounded height). Labels wrap; optional CSS `color`/`background` and font path. Chinese labels need system Microsoft YaHei or Linux Noto CJK/custom font. Out-of-frame elements and out-of-timeline timestamps fail visibly. Elements fade in/out automatically. No elements are automatically added.

`--music` selects BGM; voice automatically ducks the music. Source audio is reduced to 15% when narration is used; `--mute-source` removes it. Source/music/narration/SFX mix has a limiter. Built-in SFX and icons are generated locally; custom assets require the user's appropriate rights.

Render:

```powershell
auto-edit.exe --input input --plan plan.json --output output/demo.mp4 --mute-source --draft output/demo-draft
```

Enhanced drafts have one baked picture track and separate available audio/caption tracks. Changes to baked visual parameters require rerendering the plan. Music ducking is already computed and needs regeneration if voice timing changes. Draft GUI compatibility and perceptual speech quality cannot be proven by JSON/timecode checks alone.
