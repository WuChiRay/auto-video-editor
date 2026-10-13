"""Build native .app, CLI, ZIP and DMG on each Mac architecture."""
from pathlib import Path
import hashlib
import platform
import plistlib
import shutil
import subprocess
import sys

from release_common import copy_resources


def run(command, root):
    subprocess.run(command, check=True, cwd=root)


def main():
    if sys.platform != "darwin":
        raise SystemExit("Run this builder on macOS (one native build per CPU architecture).")
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    from pipeline import __version__
    machine = platform.machine()
    if machine not in {"arm64", "x86_64"}:
        raise SystemExit(f"Unsupported architecture: {machine}")
    arch = "arm64" if machine == "arm64" else "x64"
    release = root / "release"
    release.mkdir(exist_ok=True)
    base = release / f"auto-video-editor-{__version__}-macos-{arch}"
    if base.exists():
        raise SystemExit(f"Release directory exists: {base}")
    build = root / "build" / f"macos-{arch}"
    common = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--paths", str(root), "--target-architecture", machine,
        "--collect-all", "pyJianYingDraft", "--collect-all", "pymediainfo",
        "--collect-all", "edge_tts", "--collect-all", "certifi",
        "--add-data", str(root / "pipeline/draft_install.py") + ":pipeline",
        "--exclude-module", "faster_whisper", "--exclude-module", "torch", "--exclude-module", "cv2",
        "--exclude-module", "uiautomation", "--exclude-module", "comtypes",
        "--specpath", str(build), "--workpath", str(build / "temp")]
    run(common + ["--onedir", "--windowed", "--name", "AutoVideoEditor",
        "--osx-bundle-identifier", "io.github.WuChiRay.auto-video-editor",
        "--distpath", str(build / "desktop"), str(root / "scripts/desktop_entry.py")], root)
    run(common + ["--onefile", "--console", "--name", "auto-edit",
        "--distpath", str(build / "cli"), str(root / "scripts/cli_entry.py")], root)
    base.mkdir()
    app = base / "AutoVideoEditor.app"
    shutil.copytree(build / "desktop/AutoVideoEditor.app", app, symlinks=True)
    # The CLI travels with the app when dragged into /Applications.
    shutil.copy2(build / "cli/auto-edit", app / "Contents/MacOS/auto-edit")
    (base / "auto-edit").symlink_to("AutoVideoEditor.app/Contents/MacOS/auto-edit")
    copy_resources(root, base)
    copy_resources(root, app / "Contents/Resources/distribution")
    plist_path = app / "Contents/Info.plist"
    with plist_path.open("rb") as stream:
        plist = plistlib.load(stream)
    plist.update(CFBundleShortVersionString=__version__, CFBundleVersion=__version__,
                 NSHighResolutionCapable=True, LSMinimumSystemVersion="15.0")
    with plist_path.open("wb") as stream:
        plistlib.dump(plist, stream)
    run(["codesign", "--force", "--deep", "--sign", "-", str(app)], root)
    run(["codesign", "--verify", "--deep", "--strict", str(app)], root)
    (base / "QUICK_START.txt").write_text(
        f"Auto Video Editor {__version__} / macOS 15+ / {arch}\n"
        "1. Install FFmpeg separately: brew install ffmpeg\n"
        "2. Drag AutoVideoEditor.app into Applications, then open it. Python is included.\n"
        "3. This release is ad-hoc signed, not Apple notarized. If blocked, use System Settings > Privacy & Security > Open Anyway after verifying the download source.\n"
        "4. CLI: /Applications/AutoVideoEditor.app/Contents/MacOS/auto-edit --help\n"
        "5. Install Codex skill with install_skill.command or the copy inside the app's distribution resources.\n"
        "Mac GUI draft import asks for the draft store directory. Close Jianying/CapCut first.\n"
        "See docs/MACOS.md for Chinese instructions and tested limits.\n", encoding="utf-8")
    (base / "install_skill.command").chmod(0o755)
    (app / "Contents/Resources/distribution/install_skill.command").chmod(0o755)
    # chmod alters signed resources, so sign after final edits as well.
    run(["codesign", "--force", "--deep", "--sign", "-", str(app)], root)
    run(["codesign", "--verify", "--deep", "--strict", str(app)], root)
    archive = release / (base.name + ".zip")
    run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(base), str(archive)], root)
    (base / "Applications").symlink_to("/Applications")
    dmg = release / (base.name + ".dmg")
    run(["hdiutil", "create", "-volname", "Auto Video Editor", "-srcfolder", str(base),
         "-format", "UDZO", "-ov", str(dmg)], root)
    (base / "Applications").unlink()
    checksums = release / f"SHA256SUMS-macos-{arch}.txt"
    lines = [hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name for p in (archive, dmg)]
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
