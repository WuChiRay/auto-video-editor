from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


class PipelineError(RuntimeError):
    pass


@dataclass
class ClipSegment:
    source: str
    start: float
    end: float
    reason: str = "auto"
    speed: float = 1.0
    title: str = ""
    output_duration: float | None = None
    loop: bool = False
    filter: str = "none"
    effects: tuple[str, ...] = ()

    @property
    def duration(self) -> float:
        return self.output_duration if self.output_duration is not None else self.source_duration / self.speed

    @property
    def source_duration(self) -> float:
        return max(0.0, self.end - self.start)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            text=True,
            capture_output=capture,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        raise PipelineError(f"无法启动命令 {args[0]}：{exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise PipelineError(f"命令失败（{result.returncode}）：{' '.join(args)}\n{detail[-2000:]}")
    return result


def require_tools() -> None:
    # Portable releases can use separately obtained FFmpeg in a sibling bin folder.
    import sys
    folders = []
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
        folders.extend((base / "bin", base / "ffmpeg" / "bin"))
        if sys.platform == "darwin":
            app = next((p for p in Path(sys.executable).parents if p.suffix == ".app"), None)
            if app:
                folders.append(app.parent / "bin")
    if sys.platform == "darwin":
        # Finder-launched apps do not inherit the user's interactive shell PATH.
        folders.extend(Path(p) for p in ("/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin",
                                        "/opt/homebrew/bin", "/usr/local/bin"))
    present = [str(p) for p in folders if p.is_dir()]
    os.environ["PATH"] = os.pathsep.join(present + [os.environ.get("PATH", "")])
    missing = [x for x in ("ffmpeg", "ffprobe") if not command_exists(x)]
    if missing:
        hint = "Mac 可在终端执行 brew install ffmpeg-full。" if sys.platform == "darwin" else "请先安装 FFmpeg 并将 bin 加入 PATH。"
        raise PipelineError("缺少命令：" + ", ".join(missing) + "。" + hint)


def subtitle_font() -> str:
    import sys
    return "PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei" if os.name == "nt" else "Noto Sans CJK SC"


def require_subtitles() -> None:
    filters = run_command(["ffmpeg", "-hide_banner", "-filters"]).stdout
    if not re.search(r"\bsubtitles\s", filters):
        raise PipelineError("当前 FFmpeg 不含 subtitles/libass 字幕滤镜。Mac 请安装 brew install ffmpeg-full；其他平台请更换带 libass 的 FFmpeg 构建。")


def discover_videos(input_dir: Path) -> list[Path]:
    return sorted(
        (p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda p: p.name.lower(),
    )


def probe(path: Path) -> dict:
    result = run_command([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=index,codec_type,codec_name,width,height",
        "-of", "json", str(path)
    ])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PipelineError(f"ffprobe 返回了无法解析的数据：{path}") from exc


def duration_of(path: Path) -> float:
    value = probe(path).get("format", {}).get("duration")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise PipelineError(f"无法读取视频时长：{path}") from exc


def has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(path).get("streams", []))


def parse_silences(stderr: str) -> list[tuple[float, float]]:
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", stderr)]
    result: list[tuple[float, float]] = []
    for start, end in zip(starts, ends):
        if end > start:
            result.append((start, end))
    if len(starts) > len(ends):
        result.append((starts[-1], float("inf")))
    return result


def detect_keep_segments(path: Path, *, silence_db: float, silence_duration: float,
                         padding: float, min_duration: float = 0.25) -> list[ClipSegment]:
    total = duration_of(path)
    if not has_audio(path):
        return [ClipSegment(str(path), 0.0, total, "no-audio")]
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(path), "-af",
        f"silencedetect=noise={silence_db}dB:d={silence_duration}", "-f", "null", "-"
    ], text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    silences = parse_silences((result.stderr or "") + (result.stdout or ""))
    keep: list[ClipSegment] = []
    cursor = 0.0
    for silence_start, silence_end in silences:
        end = min(total, silence_start + padding)
        if end - cursor >= min_duration:
            keep.append(ClipSegment(str(path), cursor, end, "speech"))
        cursor = min(total, silence_end - padding if silence_end != float("inf") else total)
    if total - cursor >= min_duration:
        keep.append(ClipSegment(str(path), cursor, total, "speech"))
    return keep or [ClipSegment(str(path), 0.0, total, "fallback")]


def load_plan(path: Path, input_dir: Path) -> list[ClipSegment]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"无法读取 plan 文件：{path}") from exc
    if not isinstance(data, dict):
        raise PipelineError("plan 顶层必须是 JSON 对象")
    items = data.get("clips", data.get("segments", []))
    if not isinstance(items, list):
        raise PipelineError("plan 的 clips/segments 必须是列表")
    segments: list[ClipSegment] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("file", item.get("source")):
            raise PipelineError("每个片段必须指定 file/source")
        source = Path(str(item.get("file", item.get("source", ""))))
        if not source.is_absolute():
            source = input_dir / source
        if not source.exists():
            raise PipelineError(f"plan 中的素材不存在：{source}")
        if "keep" not in item and "end" not in item:
            raise PipelineError("每个片段必须指定 end 或 keep 范围")
        ranges = item["keep"] if "keep" in item else [[item.get("start", 0), item["end"]]]
        if not isinstance(ranges, list) or any(not isinstance(r, list) or len(r) != 2 for r in ranges):
            raise PipelineError("keep 必须是 [[start, end], ...] 格式")
        for start, end in ranges:
            seg = ClipSegment(str(source), float(start), float(end), "plan",
                              float(item.get("speed", 1)), str(item.get("title", "")),
                              float(item["output_duration"]) if "output_duration" in item else None,
                              bool(item.get("loop", False)))
            if not math.isfinite(seg.speed) or not .5 <= seg.speed <= 2:
                raise PipelineError("速度必须在 0.5–2 之间")
            from .enhancements import FILTERS, EFFECTS
            seg.filter = str(item.get("filter", "none"))
            effects = item.get("effects", [])
            if seg.filter not in FILTERS or not isinstance(effects, list) or any(not isinstance(x, str) or x not in EFFECTS for x in effects):
                raise PipelineError("未知滤镜或特效；请使用文档列出的预设")
            seg.effects = tuple(effects)
            values = [seg.start, seg.end, seg.speed, seg.duration]
            if not all(math.isfinite(x) for x in values) or seg.start < 0 or seg.end <= seg.start or seg.speed < 0.5 or seg.speed > 2 or seg.duration <= 0:
                raise PipelineError(f"无效片段（时间、速度或时长）：{source}")
            if seg.end > duration_of(source) + 0.04:
                raise PipelineError(f"片段超出源视频时长：{source}")
            if not seg.loop and seg.duration > seg.source_duration / seg.speed + 0.04:
                raise PipelineError("素材不够输出指定时长；请设置 loop=true 或缩短 output_duration")
            segments.append(seg)
    if not segments:
        raise PipelineError(f"plan 文件没有 clips/segments：{path}")
    return segments


def escape_subtitle_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def write_title_track(path: Path, seg: ClipSegment, index: int, total: int,
                      width: int, height: int, heading: str = "") -> None:
    """Create a local ASS title track timed to the rendered segment."""
    def clock(value: float) -> str:
        centis = round(value * 100)
        seconds, cs = divmod(centis, 100)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"

    def safe(value: str) -> str:
        return value.replace("\\", "").replace("{", "").replace("}", "").replace("\n", " ")

    path.write_text(
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Title,{subtitle_font()},{round(width*.057)},&H00FFFFFF,&H00FFFFFF,&H002A2318,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,8,30,30,{round(height*.10)},1\n"
        f"Style: Meta,{subtitle_font()},{round(width*.031)},&H0034E9FF,&H0034E9FF,&H002A2318,&H80000000,0,0,0,0,100,100,0,0,1,1,1,8,30,30,{round(height*.052)},1\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        f"Dialogue: 0,0:00:00.00,{clock(seg.duration)},Title,,0,0,0,,{safe(seg.title)}\n"
        f"Dialogue: 0,0:00:00.00,{clock(seg.duration)},Meta,,0,0,0,,{safe(heading)}  |  {index:02d}/{total:02d}\n",
        encoding="utf-8")


def render_segment(seg: ClipSegment, target: Path, *, width: int, height: int, fps: int,
                   crf: int, audio_bitrate: str, subtitle: Path | None = None,
                   mute_source: bool = False) -> None:
    vf = f"trim=start={seg.start}:end={seg.end},setpts=(PTS-STARTPTS)/{seg.speed},fps={fps}"
    if seg.loop:
        frames = max(1, round(seg.source_duration / seg.speed * fps))
        vf += f",loop=loop=-1:size={frames}:start=0,setpts=N/({fps}*TB)"
    vf += f",scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    from .enhancements import segment_filters
    vf += segment_filters(seg, width, height, fps)
    if subtitle:
        require_subtitles()
        vf += f",subtitles=filename='{escape_subtitle_path(subtitle)}'"
    source_has_audio = has_audio(Path(seg.source)) and not mute_source and not seg.loop
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", seg.source]
    if not source_has_audio:
        args.extend(["-f", "lavfi", "-t", f"{seg.duration:.3f}", "-i",
                     "anullsrc=channel_layout=stereo:sample_rate=48000"])
    if source_has_audio:
        args.extend(["-af", f"atrim=start={seg.start}:end={seg.end},asetpts=PTS-STARTPTS,atempo={seg.speed}"])
    args.extend(["-map", "0:v:0", "-map", "0:a:0" if source_has_audio else "1:a:0",
                 "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000",
                 "-ac", "2", "-t", f"{seg.duration:.6f}", "-movflags", "+faststart", str(target)])
    run_command(args)


def concat_segments(files: Iterable[Path], target: Path) -> None:
    list_file = target.with_suffix(".concat.txt")
    lines = ["file '" + p.resolve().as_posix().replace("'", "'\\''") + "'" for p in files]
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        run_command(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                     "-i", str(list_file), "-c", "copy", "-movflags", "+faststart", str(target)])
    finally:
        list_file.unlink(missing_ok=True)


def add_music(video: Path, music: Path, target: Path, *, volume: float) -> None:
    run_command(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-stream_loop", "-1",
                 "-i", str(music), "-filter_complex",
                 f"[0:a]volume=1[a0];[1:a]volume={volume}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                 "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                 "-shortest", "-movflags", "+faststart", str(target)])


def write_srt_placeholder(path: Path, segments: list[ClipSegment]) -> None:
    """Write a machine-readable placeholder when transcription is not enabled."""
    path.write_text("\n".join(f"{i}\n00:00:00,000 --> 00:00:00,000\n[待转写]\n" for i, _ in enumerate(segments, 1)), encoding="utf-8")


def _srt_time(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcribe_to_srt(video: Path, target: Path, *, model_name: str = "small") -> None:
    """Transcribe one file with the optional local faster-whisper package."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise PipelineError(
            "--transcribe 需要 faster-whisper；请执行 pip install -e .[transcribe]，或改用已有 --subtitle。"
        ) from exc
    print(f"[转写] {video.name}（模型 {model_name}，首次运行可能下载模型）")
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    parts, _ = model.transcribe(str(video), vad_filter=True)
    lines: list[str] = []
    for index, item in enumerate(parts, 1):
        text = item.text.strip()
        if not text:
            continue
        lines.extend([str(index), f"{_srt_time(item.start)} --> {_srt_time(item.end)}", text, ""])
    target.write_text("\n".join(lines), encoding="utf-8")


def manifest(segments: list[ClipSegment], output: Path) -> dict:
    return {"version": 1, "output": str(output), "segments": [asdict(x) | {"duration": x.duration} for x in segments]}
