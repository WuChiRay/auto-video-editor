"""Export portable, editable Jianying drafts with optional pyJianYingDraft."""
from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from .core import ClipSegment, PipelineError, duration_of, run_command


def export_draft(segments: list[ClipSegment], destination: Path, *, width: int,
                 height: int, fps: int, heading: str = "", music: Path | None = None,
                 music_volume: float = .12, mute_source: bool = False) -> Path:
    try:
        import pyJianYingDraft as draft
    except ImportError as exc:
        raise PipelineError("剪映草稿需要 pip install -e '.[draft]'。") from exc
    destination = destination.resolve()
    if destination.exists():
        raise PipelineError(f"草稿目录已存在，请选择新目录：{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    script = draft.DraftFolder(str(destination.parent)).create_draft(
        destination.name, width, height, fps)
    assets = destination / "assets"
    assets.mkdir()
    script.append_tracks([
        draft.TrackSpec(draft.TrackType.video, "动作视频"),
        draft.TrackSpec(draft.TrackType.audio, "运动BGM"),
        draft.TrackSpec(draft.TrackType.text, "动作标题"),
        draft.TrackSpec(draft.TrackType.text, "系列名称"),
    ])
    cursor = 0
    for index, seg in enumerate(segments, 1):
        print(f"[草稿素材] {index}/{len(segments)} {seg.title}")
        asset = assets / f"action_{index:02d}.mp4"
        # Re-encode using full decode, so problematic source indexes cannot change shots.
        # Keep source speed at 1x and text separate for native timeline editing.
        run_command([
            "ffmpeg", "-y", "-v", "error", "-i", seg.source, "-vf",
            f"trim=start={seg.start}:end={seg.end},setpts=PTS-STARTPTS,fps={fps},"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-af", f"atrim=start={seg.start}:end={seg.end},asetpts=PTS-STARTPTS",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart", str(asset)])
        material = draft.VideoMaterial(str(asset))
        total = round(seg.duration * 1_000_000)
        cycle = round(seg.source_duration / seg.speed * 1_000_000)
        used = 0
        while used < total:
            duration = min(cycle, total - used)
            source_duration = round(duration * seg.speed)
            video = draft.VideoSegment(material, draft.Timerange(cursor + used, duration),
                source_timerange=draft.Timerange(0, source_duration),
                volume=0 if mute_source else 1)
            script.add_segment(video, "动作视频")
            used += duration
        timerange = draft.Timerange(cursor, total)
        if seg.title:
            script.add_segment(draft.TextSegment(seg.title, timerange,
                style=draft.TextStyle(size=7, bold=True, align=1),
                border=draft.TextBorder(width=20),
                clip_settings=draft.ClipSettings(transform_y=.76)), "动作标题")
            if heading:
                script.add_segment(draft.TextSegment(
                    f"{heading}  |  {index:02d}/{len(segments):02d}", timerange,
                    style=draft.TextStyle(size=4, color=(1, .91, .20), align=1),
                    border=draft.TextBorder(width=15),
                    clip_settings=draft.ClipSettings(transform_y=.875)), "系列名称")
        cursor += total
    if music:
        bgm = assets / ("bgm" + music.suffix.lower())
        shutil.copy2(music, bgm)
        material = draft.AudioMaterial(str(bgm))
        music_length = round(duration_of(bgm) * 1_000_000)
        position = 0
        while position < cursor:
            length = min(music_length, cursor - position)
            script.add_segment(draft.AudioSegment(material,
                draft.Timerange(position, length), volume=music_volume / 2), "运动BGM")
            position += length
    script.save()
    return _finish_draft(destination, cursor)


def export_composed_draft(picture: Path, stems: dict[str, Path], captions: list[dict],
                          destination: Path, *, width: int, height: int, fps: int,
                          total: float, source_volume: float = 1) -> Path:
    """Bake visual composition; keep timed narration, captions and mix stems editable."""
    try:
        import pyJianYingDraft as draft
    except ImportError as exc:
        raise PipelineError("剪映草稿需要 pip install '.[draft]'。") from exc
    destination = destination.resolve()
    if destination.exists():
        raise PipelineError(f"草稿目录已存在，请选择新目录：{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    script = draft.DraftFolder(str(destination.parent)).create_draft(destination.name, width, height, fps)
    assets = destination / "assets"
    assets.mkdir()
    script.append_tracks([draft.TrackSpec(draft.TrackType.video, "合成画面")])
    video = assets / "picture.mp4"
    shutil.copy2(picture, video)
    cursor = round(total * 1e6)
    script.add_segment(draft.VideoSegment(draft.VideoMaterial(str(video)),
                       draft.Timerange(0, cursor), volume=source_volume), "合成画面")
    for i, (name, file) in enumerate(stems.items()):
        script.append_tracks([draft.TrackSpec(draft.TrackType.audio, name)])
        audio = assets / f"audio-{i}.wav"
        # Frame-rounded video can exceed raw speech by a few milliseconds.
        run_command(["ffmpeg", "-y", "-v", "error", "-i", str(file), "-af", "apad",
                     "-t", f"{cursor/1e6:.6f}", "-ar", "48000", "-ac", "2", str(audio)])
        script.add_segment(draft.AudioSegment(draft.AudioMaterial(str(audio)),
                           draft.Timerange(0, cursor)), name)
    if captions:
        script.append_tracks([draft.TrackSpec(draft.TrackType.text, "口播字幕")])
        for item in captions:
            start, end = round(item["start"] * 1e6), min(cursor, round(item["end"] * 1e6))
            script.add_segment(draft.TextSegment(item["text"], draft.Timerange(start, end - start),
                style=draft.TextStyle(size=4.2, bold=True, align=1, auto_wrapping=True, max_line_width=.88),
                border=draft.TextBorder(width=6), clip_settings=draft.ClipSettings(transform_y=-.85)), "口播字幕")
    script.save()
    _finish_draft(destination, cursor)
    (destination / "使用说明.txt").write_text(
        "丰富元素剪映草稿\n退出剪映，保持 assets 与 JSON 在完整目录中，\n"
        "使用 Auto Video Editor 的导入按钮或 --install-draft 导入。\n"
        "双击导入.cmd 需要 Python。导入复制素材、重定位路径并备份索引。\n"
        "画面已经合成；配音、口播字幕、配乐、音效分轨。详细限制见 效果说明.txt。\n",
        encoding="utf-8")
    (destination / "效果说明.txt").write_text(
        "转场、滤镜、图标、标签、片段标题和特效已合成在画面轨道中。\n"
        "配音、口播字幕、配乐、提示音效可分别编辑。\n"
        "配乐已做语音避让；修改配音后需重新生成音乐避让效果。\n"
        "MP4 最终混音有限幅保护；剪映导出时请检查总音量。\n"
        "此类草稿已验证结构与素材，尚需在使用者的剪映版本中打开验收。\n", encoding="utf-8")
    return destination


def _finish_draft(destination: Path, cursor: int) -> Path:
    assets = destination / "assets"
    content_path = destination / "draft_content.json"
    content = json.loads(content_path.read_text(encoding="utf-8"))
    identity = str(uuid.uuid4()).upper()
    content.update(id=identity, name=destination.name)
    content_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    meta_path = destination / "draft_meta_info.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    stamp = time.time_ns() // 1000
    meta.update(draft_id=identity, draft_name=destination.name,
        draft_fold_path=destination.as_posix(), draft_root_path=destination.parent.as_posix(),
        draft_json_file=content_path.as_posix(), tm_duration=cursor,
        tm_draft_create=stamp, tm_draft_modified=stamp,
        draft_timeline_materials_size=sum(p.stat().st_size for p in assets.iterdir()))
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    shutil.copy2(Path(__file__).with_name("draft_install.py"), destination / "导入草稿.py")
    shutil.copy2(Path(__file__).with_name("draft_install.py"), destination / "install_draft.py")
    (destination / "双击导入.cmd").write_text(
        '@echo off\r\ncd /d "%~dp0"\r\npython install_draft.py\r\npause\r\n', encoding="ascii")
    (destination / "使用说明.txt").write_text(
        "剪映可编辑草稿（视频、标题、BGM 为独立轨道）\n"
        "1. 安装 Python 3.11+，退出剪映专业版。\n"
        "2. 解压整个文件夹，双击 双击导入.cmd。\n"
        "   自定义草稿位置：python 导入草稿.py --root \"你的草稿根目录\"\n"
        "3. 打开剪映，在本地草稿中找到本项目。不要使用媒体导入。\n"
        "导入脚本会复制素材、重定位路径、备份草稿索引，并避免覆盖同名项目。\n"
        "仅截取的动作素材保留在包中；速度在剪映里设置，文字可以单独编辑。\n"
        "新版本剪映可能迁移工程格式，不保证所有版本均兼容。\n",
        encoding="utf-8")
    return destination
