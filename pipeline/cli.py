from __future__ import annotations

import argparse
import json
import sys
import math
import uuid
import os
from pathlib import Path

from .core import (
    PipelineError, add_music, concat_segments, detect_keep_segments, discover_videos,
    has_audio, load_plan, manifest, render_segment, require_tools, transcribe_to_srt, write_title_track,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本地优先自动剪辑：静音粗剪、竖屏合成、BGM、字幕和 JSON 计划")
    from . import __version__
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--gui", action="store_true", help="打开图形界面")
    parser.add_argument("--install-draft", type=Path, help="把已生成草稿导入本机剪映，无需 FFmpeg")
    parser.add_argument("--draft-root", type=Path, help="导入草稿时自定义剪映草稿根目录")
    parser.add_argument("--input", "-i", type=Path, default=Path("input"), help="输入素材目录")
    parser.add_argument("--output", "-o", type=Path, default=Path("output/final.mp4"), help="最终 MP4")
    parser.add_argument("--work", type=Path, default=Path("work"), help="中间文件目录")
    parser.add_argument("--plan", type=Path, help="可选 JSON 计划；提供后跳过自动静音检测")
    parser.add_argument("--music", type=Path, help="可选背景音乐文件")
    parser.add_argument("--mute-source", action="store_true", help="移除原片声音，适合搭配运动 BGM")
    parser.add_argument("--subtitle", type=Path, help="可选 SRT 字幕；会烧录到画面")
    parser.add_argument("--heading", default="", help="动作标题上方的系列名称")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--silence-db", type=float, default=-35)
    parser.add_argument("--silence-duration", type=float, default=0.45)
    parser.add_argument("--keep-padding", type=float, default=0.12)
    parser.add_argument("--music-volume", type=float, default=0.12)
    parser.add_argument("--transcribe", action="store_true", help="使用可选 faster-whisper 生成字幕（首次会下载模型）")
    parser.add_argument("--whisper-model", default="small", help="faster-whisper 模型名，例如 tiny/base/small")
    parser.add_argument("--dry-run", action="store_true", help="只分析并写出 manifest，不渲染")
    parser.add_argument("--draft", type=Path, help="额外生成可编辑剪映草稿目录（需要 draft extra）")
    parser.add_argument("--draft-only", action="store_true", help="仅生成 --draft 指定的草稿，不渲染成片")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.gui:
            from .gui import main as gui_main
            return gui_main()
        if args.install_draft:
            from .draft_install import install
            root = args.draft_root or Path(os.environ.get("LOCALAPPDATA", ".")) / "JianyingPro/User Data/Projects/com.lveditor.draft"
            print(f"[导入] {install(args.install_draft, root)}")
            return 0
        if args.draft_only and not args.draft:
            raise PipelineError("--draft-only 需要 --draft 目录")
        if args.width < 2 or args.height < 2 or args.width % 2 or args.height % 2:
            raise PipelineError("画面宽高必须是大于零的偶数")
        if args.fps <= 0 or not 0 <= args.crf <= 51:
            raise PipelineError("帧率必须大于零，CRF 必须在 0–51 之间")
        if not math.isfinite(args.music_volume) or args.music_volume < 0:
            raise PipelineError("音乐音量必须是有限的非负数字")
        for asset in (args.music, args.subtitle):
            if asset and not asset.is_file():
                raise PipelineError(f"文件不存在：{asset}")
        require_tools()
        if not args.input.exists():
            raise PipelineError(f"输入目录不存在：{args.input.resolve()}（请先创建并放入视频）")
        videos = discover_videos(args.input)
        if not videos:
            raise PipelineError(f"输入目录没有视频文件：{args.input.resolve()}")
        args.work = args.work / ("job-" + uuid.uuid4().hex[:12])
        args.work.mkdir(parents=True, exist_ok=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.plan:
            segments = load_plan(args.plan, args.input)
        else:
            segments = []
            for video in videos:
                print(f"[分析] {video.name}")
                segments.extend(detect_keep_segments(video, silence_db=args.silence_db,
                                                     silence_duration=args.silence_duration,
                                                     padding=args.keep_padding))
        if not segments:
            raise PipelineError("没有可渲染的片段")
        if any(args.output.resolve() == Path(s.source).resolve() for s in segments):
            raise PipelineError("输出不能覆盖源视频，请选择其他输出路径")
        report = manifest(segments, args.output.resolve())
        report_path = args.output.with_suffix(".manifest.json")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[计划] {len(segments)} 个片段，预计 {sum(x.duration for x in segments):.1f}s")
        if args.dry_run:
            print(f"[完成] 分析报告：{report_path}")
            return 0
        if args.draft_only and not args.draft:
            raise PipelineError("--draft-only 需要 --draft 目录")
        if args.draft:
            if args.subtitle or args.transcribe:
                raise PipelineError("草稿导出暂支持 plan 动作标题；外部/转写字幕尚未适配。")
            from .jianying import export_draft
            folder = export_draft(segments, args.draft, width=args.width,
                height=args.height, fps=args.fps, heading=args.heading,
                music=args.music, music_volume=args.music_volume, mute_source=args.mute_source)
            print(f"[草稿] {folder}")
            if args.draft_only:
                return 0
        generated_subtitles: dict[str, Path] = {}
        if args.transcribe and not args.subtitle:
            for video in videos:
                subtitle_path = args.work / f"{video.stem}.srt"
                transcribe_to_srt(video, subtitle_path, model_name=args.whisper_model)
                generated_subtitles[str(video.resolve())] = subtitle_path
        rendered: list[Path] = []
        for index, segment in enumerate(segments, 1):
            target = args.work / f"segment_{index:04d}.mp4"
            print(f"[渲染] {index}/{len(segments)} {Path(segment.source).name} {segment.start:.2f}-{segment.end:.2f}")
            subtitle = args.subtitle or generated_subtitles.get(str(Path(segment.source).resolve()))
            if segment.title and not subtitle:
                subtitle = args.work / f"title_{index:04d}.ass"
                write_title_track(subtitle, segment, index, len(segments), args.width, args.height, args.heading)
            render_segment(segment, target, width=args.width, height=args.height, fps=args.fps,
                           crf=args.crf, audio_bitrate="128k", subtitle=subtitle, mute_source=args.mute_source)
            rendered.append(target)
        assembled = args.work / "assembled.mp4"
        concat_segments(rendered, assembled)
        final = args.output
        if args.music:
            if has_audio(assembled):
                add_music(assembled, args.music, final, volume=args.music_volume)
            else:
                print("[提示] 成片没有音轨，跳过 BGM 混音")
                assembled.replace(final)
        else:
            assembled.replace(final)
        print(f"[完成] {final.resolve()}")
        print(f"[报告] {report_path.resolve()}")
        return 0
    except (PipelineError, OSError, ValueError, RuntimeError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
