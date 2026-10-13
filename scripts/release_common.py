"""Public documentation and corresponding dependency sources for binary releases."""
import importlib.metadata
import shutil
import sys
from pathlib import Path


def copy_resources(root: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md", "install_skill.ps1", "install_skill.command"):
        shutil.copy2(root / name, destination / name)
    for folder in ("skills", "examples", "docs"):
        shutil.copytree(root / folder, destination / folder)
    import edge_tts
    shutil.copytree(Path(edge_tts.__file__).parent, destination / "third_party/edge_tts",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    licenses = destination / "licenses"
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
