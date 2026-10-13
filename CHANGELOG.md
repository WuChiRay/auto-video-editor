# Changelog

## 0.4.0

- Continuous whole-script neural narration (default Yunjian mature male), preview MP3, word-aligned SRT, and explicit failure without a robotic voice fallback.
- October 2026 Edge speech endpoint compatibility; existing recording support for offline workflows.
- Narration loudness processing, music ducking, and optional last-frame extension without accelerating speech.
- Six transition modes, six filter presets, zoom/vignette/fade effects, timed labels/icons/images, and synthesized or custom sound effects.
- Enhanced Jianying drafts with baked visuals and separate narration/caption/music/SFX tracks; native basic drafts preserved.
- GUI controls, CLI flags, plan example, Codex skill, and synthetic integration tests covering timeline, blending, sound timing and portable draft paths.

Neural delivery remains subject to listening and online service availability. Enhanced drafts require opening in the user's Jianying version for visual acceptance.

## 0.3.0

- Windows desktop interface and standalone CLI packages.
- Editable Jianying drafts with video, action titles and music on separate tracks.
- Draft import from the GUI or `--install-draft`, including material relocation and index backup.
- Editing speed/duration remain parameters and are not automatically placed in the picture.
- Isolated work directories for each job; input overwrite protection and basic parameter validation.
- Installable Python package, Codex skill, synthetic-media integration tests and release workflow.

Draft opening was tested on Jianying Pro 11.5.0.14471. Compatibility with other versions is not guaranteed. Automated semantic shot selection is performed by the calling AI or a supplied plan, not by the renderer.
