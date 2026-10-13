"""Build redistributable Windows binaries, without shipping FFmpeg or user media."""
from pathlib import Path
import importlib.metadata
import shutil
import subprocess
import sys
import hashlib
import zipfile


def main():
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    from pipeline import __version__
    output = root / "release"
    output.mkdir(exist_ok=True)
    base = output / f"auto-video-editor-{__version__}-windows-x64"
    if base.exists():
        raise SystemExit(f"Release folder already exists: {base}; use a fresh build directory.")
    build = root / "build" / "windows"
    common = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--paths", str(root), "--collect-all", "pyJianYingDraft",
        "--collect-all", "edge_tts", "--collect-all", "certifi",
        "--add-data", str(root / "pipeline/draft_install.py") + ";pipeline",
        "--exclude-module", "faster_whisper", "--exclude-module", "torch",
        "--exclude-module", "cv2", "--specpath", str(build), "--workpath", str(build / "temp")]
    subprocess.run(common + ["--onedir", "--windowed", "--name", "AutoVideoEditor",
        "--distpath", str(build / "desktop"), str(root / "scripts/desktop_entry.py")], check=True, cwd=root)
    subprocess.run(common + ["--onefile", "--console", "--name", "auto-edit",
        "--distpath", str(build / "cli"), str(root / "scripts/cli_entry.py")], check=True, cwd=root)
    shutil.copytree(build / "desktop/AutoVideoEditor", base)
    shutil.copy2(build / "cli/auto-edit.exe", base / "auto-edit.exe")
    for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md", "install_skill.ps1"):
        shutil.copy2(root / name, base / name)
    shutil.copytree(root / "skills", base / "skills")
    shutil.copytree(root / "examples", base / "examples")
    shutil.copytree(root / "docs", base / "docs")
    # Supply the LGPL library's corresponding Python source and allow rebuilding.
    import edge_tts
    shutil.copytree(Path(edge_tts.__file__).parent, base / "third_party/edge_tts",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (base / "QUICK_START.txt").write_text(
        "Auto Video Editor\n\n1. Install FFmpeg separately (ffmpeg and ffprobe on PATH).\n"
        "Windows: winget install --id Gyan.FFmpeg --exact\n"
        "Or put both official FFmpeg executables in the bin folder next to this program.\n"
        "2. Double-click AutoVideoEditor.exe. No Python installation required.\n"
        "3. Select your input folder and output MP4. Optionally select a JSON plan, music and draft export.\n"
        "CLI: auto-edit.exe --help\n"
        "Draft import: auto-edit.exe --install-draft PATH_TO_DRAFT (close Jianying first).\n"
        "Automatic transcription is available in the Python version, not this executable.\n"
        "Neural narration and icons are included. Narration sends only script text to Microsoft's online speech service.\n"
        "MIT licensed source; dependencies keep their own licenses.\n", encoding="utf-8")
    licenses = base / "licenses"
    licenses.mkdir()
    for dist in importlib.metadata.distributions():
        for item in dist.files or []:
            if any(word in item.name.lower() for word in ("license", "copying", "copyright", "notice")):
                source = Path(dist.locate_file(item))
                if source.is_file() and source.suffix.lower() in ("", ".txt", ".md", ".rst"):
                    name = dist.metadata['Name'] + "-" + str(item).replace("/", "_").replace("\\", "_")
                    shutil.copy2(source, licenses / name)
    for source in [Path(sys.base_prefix) / "LICENSE.txt", *Path(sys.base_prefix).glob("tcl/*/license*")]:
        if source.is_file():
            shutil.copy2(source, licenses / ("runtime-" + source.parent.name + "-" + source.name))
    archive = output / (base.name + ".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(base.rglob("*")):
            if file.is_file():
                bundle.write(file, file.relative_to(base.parent))
    print(f"Built {archive} ({archive.stat().st_size / 1024**2:.1f} MiB)")
    print(hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
