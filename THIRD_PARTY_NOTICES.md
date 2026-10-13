# Third-party software

The project source is MIT licensed. Third-party components keep their own licenses.

- **FFmpeg / ffprobe:** installed separately and never included in the Windows release. FFmpeg may be LGPL or GPL depending on its build. Consult https://ffmpeg.org/legal.html and your distributor's license and source offer. This project invokes it as an external process.
- **pyJianYingDraft 0.3.0:** Apache-2.0, https://github.com/GuanYixuan/pyJianYingDraft. Used to generate independent editable drafts; not affiliated with or endorsed by Jianying/CapCut.
- **faster-whisper:** optional transcription dependency, MIT. Models are downloaded separately. It is not bundled in the Windows executable.
- **edge-tts 7.2.8:** LGPL-3.0, https://github.com/rany2/edge-tts. Used for optional online neural narration, bundled in Windows releases. Its unmodified Python source is included in `third_party/edge_tts/`, and license text in `licenses/`. Endpoint compatibility is implemented in this project's `pipeline/speech.py`. Rebuild with `scripts/build_release.py` to substitute a modified library; the renderer remains usable through source installation. Online speech access is subject to Microsoft's service terms and availability, independently of the library license.
- **Pillow:** HPND (PIL Software License), used for optional image overlays and bundled in Windows releases. System fonts are not redistributed.
- **Python:** Python Software Foundation License; the desktop build includes the Python runtime and Tcl/Tk, which retain their own notices.
- **PyInstaller:** build tool, GPL with an exception permitting distribution of bundled applications under other licenses. The application build is distributed under MIT.

Windows and Mac releases include dependency license files in `licenses/`; Mac apps also keep notices and edge-tts source in `Contents/Resources/distribution/`. Mac applications are ad-hoc signed and are not Apple notarized. Apple system fonts are used locally and not redistributed. Do not interpret the source-code license as permission to redistribute user videos, commercial music, fonts, or other media. No user media, third-party music or Jianying executable is included in this repository.
