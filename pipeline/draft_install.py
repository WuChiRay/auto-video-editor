"""Standalone portable Jianying draft installer. Python standard library only."""
import argparse
import json
import os
import shutil
import subprocess
import time
import uuid
import sys
from pathlib import Path


def default_draft_root():
    """Use an existing Mac store; never silently create a guessed Mac location."""
    if sys.platform == "darwin":
        candidates = [Path.home() / folder / app / "User Data/Projects/com.lveditor.draft"
                      for folder in ("Movies", "Library/Application Support")
                      for app in ("JianyingPro", "CapCut")]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        raise RuntimeError("未找到剪映草稿目录；请查看剪映设置中的草稿位置，并用 --draft-root / --root 指定")
    return Path(os.environ.get("LOCALAPPDATA", ".")) / "JianyingPro/User Data/Projects/com.lveditor.draft"


def ensure_editor_closed():
    if os.name == "nt":
        running = subprocess.check_output([
            "tasklist", "/FI", "IMAGENAME eq JianyingPro.exe", "/FO", "CSV", "/NH"
        ], errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
        active = '"JianyingPro.exe"' in running
    elif sys.platform == "darwin":
        running = subprocess.check_output(["ps", "-axo", "comm="], text=True, errors="replace")
        active = any(Path(line.strip()).name in {"JianyingPro", "Jianying", "CapCut", "剪映专业版", "剪映"}
                     for line in running.splitlines())
    else:
        active = False
    if active:
        raise RuntimeError("请先退出剪映/CapCut，再导入草稿，避免运行中的程序覆盖草稿索引")


def relocate(value, target):
    if isinstance(value, dict):
        return {k: relocate(v, target) for k, v in value.items()}
    if isinstance(value, list):
        return [relocate(v, target) for v in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        if "/assets/" in normalized:
            relative = normalized.rsplit("/assets/", 1)[1]
            path = (target / "assets" / relative).resolve()
            if not path.is_relative_to((target / "assets").resolve()) or not path.is_file():
                raise ValueError(f"素材路径无效：{relative}")
            return path.as_posix()
    return value


def install(source, root):
    source, root = source.resolve(), root.resolve()
    if not (source / "draft_content.json").is_file() or not (source / "draft_meta_info.json").is_file():
        raise ValueError("请选择包含 draft_content.json 和 draft_meta_info.json 的完整草稿目录")
    if root.is_relative_to(source):
        raise ValueError("草稿根目录不能位于待导入草稿内部")
    ensure_editor_closed()
    root.mkdir(parents=True, exist_ok=True)
    target = root / source.name
    if target.exists():
        target = root / (source.name + "_" + uuid.uuid4().hex[:8])
    index_path = root / "root_meta_info.json"
    index = json.loads(index_path.read_text(encoding="utf-8-sig")) if index_path.exists() else {
        "all_draft_store": [], "draft_ids": 0, "root_path": root.as_posix()}
    shutil.copytree(source, target)
    content_path = target / "draft_content.json"
    content = relocate(json.loads(content_path.read_text(encoding="utf-8")), target)
    identity = str(uuid.uuid4()).upper()
    content.update(id=identity, name=target.name)
    content_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    meta_path = target / "draft_meta_info.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    stamp = time.time_ns() // 1000
    meta.update(draft_id=identity, draft_name=target.name, draft_fold_path=target.as_posix(),
        draft_root_path=root.as_posix(), draft_json_file=content_path.as_posix(),
        tm_draft_create=stamp, tm_draft_modified=stamp)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    if index_path.exists():
        shutil.copy2(index_path, index_path.with_name(f"root_meta_info.backup-{stamp}.json"))
    index.setdefault("all_draft_store", []).insert(0, meta)
    index["draft_ids"] = len(index["all_draft_store"])
    temporary = index_path.with_name(f".draft-index-{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, index_path)
    return target


def main():
    parser = argparse.ArgumentParser(description="复制并注册剪映草稿，不覆盖已有项目")
    parser.add_argument("--root", type=Path, help="草稿根目录；Mac 优先识别已有目录")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        print(f"导入完成：{install(args.source, args.root or default_draft_root())}\n请打开剪映本地草稿。")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"导入失败：{exc}\n")


if __name__ == "__main__":
    main()
