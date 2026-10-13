from __future__ import annotations

import argparse
import json
import sys
import math
import uuid
import os
import shutil
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
    parser.add_argument("--draft-only", action="store_true", help="仅生成草稿；丰富效果计划仍需渲染草稿画面")
    parser.add_argument("--narration-text", type=Path, help="UTF-8 完整口播文件；一次连续合成并生成全片字幕")
    parser.add_argument("--narration-audio", type=Path, help="使用已有配音音频，无需联网")
    parser.add_argument("--narration-subtitle", type=Path, help="与已有配音对齐的全片 SRT")
    parser.add_argument("--voice", help="mature/warm/steady/female 或 Edge 神经声音 ID；默认 mature")
    parser.add_argument("--voice-rate", help="自然语速，默认 +4%%；负值请用 --voice-rate=-4%%")
    parser.add_argument("--voice-fit", choices=["extend_last", "error"], help="口播过长时延长最后画面或报错")
    parser.add_argument("--voice-preview", type=Path, help="只生成试听 MP3、字幕和字词时间，需 --narration-text")
    parser.add_argument("--transition", choices=["cut", "fade", "wipeleft", "slideright", "circleopen", "dissolve"])
    parser.add_argument("--transition-duration", type=float, help="转场重叠秒数，默认 0.35；会缩短总时长")
    parser.add_argument("--filter", choices=["none", "warm", "cool", "mono", "vivid", "cinematic"], help="全片滤镜预设")
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
            from .draft_install import install, default_draft_root
            root = args.draft_root or default_draft_root()
            print(f"[导入] {install(args.install_draft, root)}")
            return 0
        from .enhancements import settings, assemble, extend_picture, overlays, mix_narration
        from .speech import synthesize, read_captions, write_voice_ass
        from .core import duration_of
        if args.voice_preview:
            require_tools()
            if not args.narration_text or args.voice_preview.suffix.lower() != ".mp3":
                raise PipelineError("试听需要 --narration-text 文本文件，--voice-preview 输出必须为 .mp3")
            audio, srt = synthesize(args.narration_text.read_text(encoding="utf-8-sig"), args.voice_preview,
                voice=args.voice or "mature", rate=args.voice_rate or "+4%")
            print(f"[试听] {audio.resolve()}\n[字幕] {srt.resolve()}")
            return 0
        if args.draft_only and not args.draft:
            raise PipelineError("--draft-only 需要 --draft 目录")
        if args.draft and args.draft.exists():
            raise PipelineError("草稿目录已存在，请选择新目录")
        if args.width < 2 or args.height < 2 or args.width % 2 or args.height % 2:
            raise PipelineError("画面宽高必须是大于零的偶数")
        if args.fps <= 0 or not 0 <= args.crf <= 51:
            raise PipelineError("帧率必须大于零，CRF 必须在 0–51 之间")
        if not math.isfinite(args.music_volume) or args.music_volume < 0:
            raise PipelineError("音乐音量必须是有限的非负数字")
        for asset in (args.music, args.subtitle, args.narration_text, args.narration_audio, args.narration_subtitle):
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
        data = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else {}
        config = settings(data, args.plan.resolve().parent if args.plan else Path.cwd())
        if args.transition:
            config["transition"]["name"] = args.transition
        if args.transition_duration is not None:
            from .enhancements import number
            config["transition"]["duration"] = number(args.transition_duration, "转场时长", .05, 2)
        narration = config["narration"]
        if args.narration_text and args.narration_audio:
            raise PipelineError("--narration-text 和 --narration-audio 只能选一个")
        if args.narration_text or args.narration_audio:
            for key in ("text", "text_file", "audio"):
                narration.pop(key, None)
        if args.narration_text:
            narration["text_file"] = str(args.narration_text)
        if args.narration_audio:
            narration["audio"] = str(args.narration_audio)
        for value, key in [(args.narration_subtitle, "subtitles"), (args.voice, "voice"),
                           (args.voice_rate, "rate"), (args.voice_fit, "fit")]:
            if value is not None:
                narration[key] = str(value)
        if args.filter:
            for seg in segments:
                seg.filter = args.filter
        rich = bool(narration or config["elements"] or config["sound_effects"] or
                    config["transition"]["name"] != "cut" or any(s.filter != "none" or s.effects for s in segments))
        if narration and (args.subtitle or args.transcribe):
            raise PipelineError("配音字幕请用 --narration-subtitle；不能与旧版 --subtitle/--transcribe 混用")
        if any(args.output.resolve() == Path(s.source).resolve() for s in segments):
            raise PipelineError("输出不能覆盖源视频，请选择其他输出路径")
        input_assets = [s.source for s in segments] + [x for x in (args.music, args.subtitle, args.plan) if x]
        input_assets += [narration[k] for k in ("audio", "text_file", "subtitles") if narration.get(k)]
        input_assets += [x[k] for x in config["elements"] + config["sound_effects"] for k in ("file", "font") if x.get(k)]
        if any(args.output.resolve() == Path(x).resolve() for x in input_assets):
            raise PipelineError("输出不能覆盖计划或输入素材")
        report = manifest(segments, args.output.resolve())
        report["enhancements"] = config
        report_path = args.output.with_suffix(".manifest.json")
        if any(report_path.resolve() == Path(x).resolve() for x in input_assets):
            raise PipelineError("剪辑报告不能覆盖计划或输入素材")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[计划] {len(segments)} 个片段，预计 {sum(x.duration for x in segments):.1f}s")
        if args.dry_run:
            print(f"[完成] 分析报告：{report_path}")
            return 0
        if args.draft_only and not args.draft:
            raise PipelineError("--draft-only 需要 --draft 目录")
        if args.draft and not rich:
            if args.subtitle or args.transcribe:
                raise PipelineError("草稿导出暂支持 plan 动作标题；外部/转写字幕尚未适配。")
            from .jianying import export_draft
            folder = export_draft(segments, args.draft, width=args.width,
                height=args.height, fps=args.fps, heading=args.heading,
                music=args.music, music_volume=args.music_volume, mute_source=args.mute_source)
            print(f"[草稿] {folder}")
            if args.draft_only:
                return 0
        if args.draft and rich and (args.subtitle or args.transcribe):
            raise PipelineError("丰富效果草稿请使用 narration.subtitles 全片字幕；旧版片段字幕尚不支持分轨")
        voice, global_subtitle, captions = None, None, []
        if narration.get("audio"):
            voice = Path(narration["audio"])
        elif narration.get("text") or narration.get("text_file"):
            text = str(narration.get("text", "")) or Path(narration["text_file"]).read_text(encoding="utf-8-sig")
            print("[配音] 完整口播连续合成（仅口播文本发送至微软在线语音服务）")
            voice, global_subtitle = synthesize(text, args.work / "narration.mp3",
                voice=narration.get("voice", "mature"), rate=narration.get("rate", "+4%"), pitch=narration.get("pitch", "+0Hz"))
        if narration.get("subtitles"):
            global_subtitle = Path(narration["subtitles"])
        if global_subtitle:
            captions = read_captions(global_subtitle)
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
        total = assemble(rendered, assembled, config["transition"], args.fps, args.crf)
        if voice and duration_of(voice) > total + .04:
            if narration.get("fit", "extend_last") == "error":
                raise PipelineError("口播长于画面；请延长计划，或设置 narration.fit=extend_last")
            total = math.ceil(duration_of(voice) * args.fps) / args.fps
            extended = args.work / "extended.mp4"
            extend_picture(assembled, extended, total, args.fps, args.crf)
            assembled = extended
            print(f"[时间线] 最后画面延长至 {total:.2f}s，保持配音自然语速")
        if captions and captions[-1]["end"] > total + .04:
            raise PipelineError("全片字幕超出最终时间线；请校准字幕或延长画面")
        if config["elements"]:
            decorated = args.work / "decorated.mp4"
            overlays(assembled, decorated, config["elements"], args.work, args.width, args.height, total, args.crf)
            assembled = decorated
        final = args.output
        if rich:
            target = args.work / "draft-preview.mp4" if args.draft_only else final
            burned_subtitle = None
            if captions:
                burned_subtitle = args.work / "narration.ass"
                write_voice_ass(burned_subtitle, captions, args.width, args.height)
            stems = mix_narration(assembled, target, args.work, total, voice=voice, music=args.music,
                music_volume=args.music_volume, sounds=config["sound_effects"], subtitles=burned_subtitle, crf=args.crf)
            if args.draft:
                from .jianying import export_composed_draft
                folder = export_composed_draft(assembled, stems, captions, args.draft,
                    width=args.width, height=args.height, fps=args.fps, total=total,
                    source_volume=.15 if voice else 1)
                print(f"[草稿] {folder}（视觉效果已合成，配音/字幕/音乐/音效独立）")
            if voice:
                preview = final.with_name(final.stem + ".narration" + voice.suffix)
                if preview.resolve() != voice.resolve():
                    shutil.copy2(voice, preview)
                print(f"[试听] {preview.resolve()}")
                words = voice.with_suffix(".words.json")
                if words.is_file():
                    shutil.copy2(words, final.with_suffix(".words.json"))
            if global_subtitle:
                destination = final.with_suffix(".srt")
                if destination.resolve() != global_subtitle.resolve():
                    shutil.copy2(global_subtitle, destination)
        elif args.music:
            if has_audio(assembled):
                add_music(assembled, args.music, final, volume=args.music_volume)
            else:
                print("[提示] 成片没有音轨，跳过 BGM 混音")
                assembled.replace(final)
        else:
            assembled.replace(final)
        report.update(final_duration=duration_of(final) if not args.draft_only else total,
                      narration_duration=duration_of(voice) if voice else None,
                      visual_effects_baked_in_draft=rich and bool(args.draft))
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.draft_only:
            print(f"[完成] {final.resolve()}")
        print(f"[报告] {report_path.resolve()}")
        return 0
    except (PipelineError, OSError, ValueError, RuntimeError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
