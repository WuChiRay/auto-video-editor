"""Validated presets, timed overlays and locally generated sound effects."""
from __future__ import annotations

import math
import os
import struct
import wave
import sys
from pathlib import Path

from .core import PipelineError, concat_segments, duration_of, escape_subtitle_path, run_command, require_subtitles

FILTERS = {
    "none": "", "warm": "colorbalance=rs=.06:bs=-.04",
    "cool": "colorbalance=rs=-.04:bs=.06", "mono": "hue=s=0",
    "vivid": "eq=saturation=1.25:contrast=1.06",
    "cinematic": "eq=saturation=.85:contrast=1.08:brightness=-.015",
}
EFFECTS = {"zoom_in", "vignette", "fade"}
TRANSITIONS = {"cut", "fade", "wipeleft", "slideright", "circleopen", "dissolve"}
ICONS = {"check", "play", "bolt", "heart", "download", "code"}
SOUNDS = {"whoosh", "pop", "click", "ding"}


def number(value, name, low=0, high=1e9):
    try:
        value = float(value)
    except (ValueError, TypeError) as exc:
        raise PipelineError(f"{name} 必须是数字") from exc
    if not math.isfinite(value) or not low <= value <= high:
        raise PipelineError(f"{name} 必须在 {low}–{high} 之间")
    return value


def asset_path(value, base: Path) -> Path:
    path = Path(str(value))
    path = path if path.is_absolute() else base / path
    if not path.is_file():
        raise PipelineError(f"素材不存在：{path}")
    return path.resolve()


def settings(data: dict, base: Path) -> dict:
    """Auxiliary paths are plan-relative, independently of video input paths."""
    transition = data.get("transition", {})
    if not isinstance(transition, dict):
        raise PipelineError("transition 必须为对象")
    name = transition.get("name", "cut")
    if name not in TRANSITIONS:
        raise PipelineError("未知转场预设")
    transition = {"name": name, "duration": number(transition.get("duration", .35), "转场时长", .05, 2)}
    elements = data.get("elements", [])
    sounds = data.get("sound_effects", [])
    if not isinstance(elements, list) or not isinstance(sounds, list):
        raise PipelineError("elements / sound_effects 必须为列表")
    if any(not isinstance(x, dict) for x in elements + sounds):
        raise PipelineError("每个元素或音效必须为对象")
    elements, sounds = [dict(x) for x in elements], [dict(x) for x in sounds]
    for item in elements:
        kind = item.get("type", "label")
        if kind not in {"label", "icon", "image"}:
            raise PipelineError("元素 type 仅支持 label/icon/image")
        item["type"] = kind
        item["start"] = number(item.get("start", 0), "元素开始时间")
        item["end"] = number(item.get("end", 3), "元素结束时间", item["start"] + .01)
        item["x"] = number(item.get("x", .08), "元素 x", 0, 1)
        item["y"] = number(item.get("y", .20), "元素 y", 0, 1)
        item["size"] = number(item.get("size", .12 if kind == "icon" else .75), "元素 size", .02, 1)
        if kind == "icon" and item.get("name") not in ICONS:
            raise PipelineError("未知图标预设")
        if kind == "label" and not str(item.get("text", "")).strip():
            raise PipelineError("标签缺少 text")
        if kind == "image":
            item["file"] = str(asset_path(item.get("file", ""), base))
        if item.get("font"):
            item["font"] = str(asset_path(item["font"], base))
    for item in sounds:
        if "file" in item:
            item["file"] = str(asset_path(item["file"], base))
        elif item.get("name") not in SOUNDS:
            raise PipelineError("未知音效预设")
        item["start"] = number(item.get("start", 0), "音效开始时间")
        item["volume"] = number(item.get("volume", .25), "音效音量", 0, 1)
    narration = data.get("narration", {})
    if not isinstance(narration, dict):
        raise PipelineError("narration 必须为对象")
    narration = dict(narration)
    for key in ("text_file", "audio", "subtitles"):
        if narration.get(key):
            narration[key] = str(asset_path(narration[key], base))
    if narration.get("fit", "extend_last") not in {"extend_last", "error"}:
        raise PipelineError("narration.fit 仅支持 extend_last/error")
    if sum(bool(narration.get(k)) for k in ("text", "text_file", "audio")) > 1:
        raise PipelineError("narration 的 text/text_file/audio 只能选一个")
    return {"transition": transition, "elements": elements, "sound_effects": sounds, "narration": narration}


def segment_filters(seg, width, height, fps):
    filters = [FILTERS[seg.filter]] if FILTERS[seg.filter] else []
    if "zoom_in" in seg.effects:
        # One output frame per input frame; start centered, grow to 1.08x.
        frames = max(1, round(seg.duration * fps))
        filters.append(f"zoompan=z='1+0.08*min(on/{frames},1)':x='iw/2-iw/zoom/2':"
                       f"y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps}")
    if "vignette" in seg.effects:
        filters.append("vignette=PI/5")
    if "fade" in seg.effects:
        d = min(.25, seg.duration / 4)
        filters.extend([f"fade=t=in:st=0:d={d}", f"fade=t=out:st={seg.duration-d}:d={d}"])
    return "".join("," + f for f in filters)


def assemble(files: list[Path], target: Path, transition: dict, fps: int, crf: int) -> float:
    if len(files) == 1 or transition["name"] == "cut":
        concat_segments(files, target)
        return duration_of(target)
    d = round(transition["duration"] * fps) / fps
    durations = [round(duration_of(p) * fps) / fps for p in files]
    if d <= 0 or any(2 * d >= length for length in durations):
        raise PipelineError("转场须至少一帧，且小于每个片段时长的一半")
    args = ["ffmpeg", "-y", "-v", "error"]
    for file in files:
        args.extend(["-i", str(file)])
    filters = []
    for i, length in enumerate(durations):
        filters.extend([f"[{i}:v]settb=1/{fps},setpts=PTS-STARTPTS[v{i}]",
                        f"[{i}:a]apad,atrim=duration={length},asetpts=PTS-STARTPTS[a{i}]"])
    total, v, a = durations[0], "v0", "a0"
    for i in range(1, len(files)):
        filters.append(f"[{v}][v{i}]xfade=transition={transition['name']}:duration={d}:offset={total-d}[vt{i}]")
        filters.append(f"[{a}][a{i}]acrossfade=d={d}:c1=tri:c2=tri[at{i}]")
        v, a, total = f"vt{i}", f"at{i}", total + durations[i] - d
    args.extend(["-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
                 "-map", f"[{v}]", "-map", f"[{a}]", "-t", str(total), "-r", str(fps),
                 "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(target)])
    run_command(args)
    return total


def extend_picture(source: Path, target: Path, total: float, fps: int, crf: int):
    run_command(["ffmpeg", "-y", "-v", "error", "-i", str(source),
                 "-vf", f"tpad=stop_mode=clone:stop_duration={total},fps={fps}",
                 "-af", "apad", "-t", str(total), "-c:v", "libx264", "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-c:a", "aac", str(target)])


def find_font(text: str, custom=None):
    candidates = [Path(custom)] if custom else [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    if not custom and sys.platform == "darwin":
        candidates = [Path("/System/Library/Fonts") / name for name in (
            "PingFang.ttc", "STHeiti Light.ttc", "STHeiti Medium.ttc",
            "Supplemental/Songti.ttc", "Supplemental/Arial Unicode.ttf")] + candidates
        # New macOS versions may store PingFang in system font assets.
        if not any(p.is_file() for p in candidates[:5]):
            candidates = list(Path("/System/Library/AssetsV2").glob("com_apple_MobileAsset_Font*/**/PingFang.ttc")) + candidates
    for path in candidates:
        if path.is_file():
            if any("\u3400" <= c <= "\u9fff" for c in text) and "DejaVu" in path.name:
                continue
            return str(path)
    if any("\u3400" <= c <= "\u9fff" for c in text):
        raise PipelineError("标签需要中文字体；Mac 请启用系统中文字体，Linux 安装 fonts-noto-cjk，或指定元素 font 文件")
    return None


def make_element(item: dict, path: Path, width: int):
    try:
        from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
    except ImportError as exc:
        raise PipelineError("图标/标签需要 pip install '.[visual]'（Windows 程序已包含）") from exc
    size = max(16, round(width * item["size"]))
    try:
        color = ImageColor.getcolor(item.get("color", "#ffffff"), "RGBA")
        background = ImageColor.getcolor(item.get("background", "#173447dd"), "RGBA")
    except ValueError as exc:
        raise PipelineError("元素颜色须为 CSS 颜色或 #RRGGBBAA") from exc
    kind = item["type"]
    if kind == "image":
        with Image.open(item["file"]) as original:
            image = original.convert("RGBA")
            image.thumbnail((size, size))
    elif kind == "label":
        text = str(item["text"])
        fontpath = find_font(text, item.get("font"))
        fontsize = max(12, round(width * .043))
        font = ImageFont.truetype(fontpath, fontsize) if fontpath else ImageFont.load_default(size=fontsize)
        # Wrap labels to the explicitly requested maximum width.
        lines, current = [], ""
        for char in text:
            if char == "\n" or (current and font.getlength(current + char) > size - fontsize):
                lines.append(current)
                current = ""
            if char != "\n":
                current += char
        if current:
            lines.append(current)
        text = "\n".join(lines)
        bbox = ImageDraw.Draw(Image.new("RGBA", (1, 1))).multiline_textbbox((0, 0), text, font=font, spacing=6)
        w, h = bbox[2] - bbox[0] + fontsize, bbox[3] - bbox[1] + fontsize
        image = Image.new("RGBA", (w, h))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=fontsize // 2, fill=background)
        draw.multiline_text((fontsize / 2 - bbox[0], fontsize / 2 - bbox[1]), text, font=font, fill=color, spacing=6)
    else:
        image = Image.new("RGBA", (size, size))
        draw = ImageDraw.Draw(image)
        def points(coords):
            return [(round(x * size), round(y * size)) for x, y in coords]
        line = max(2, round(size * .07))
        name = item["name"]
        if name == "check":
            draw.line(points([(.18, .52), (.4, .74), (.84, .25)]), fill=color, width=line)
        elif name == "play":
            draw.polygon(points([(.24, .15), (.85, .5), (.24, .85)]), fill=color)
        elif name == "bolt":
            draw.polygon(points([(.55, .06), (.19, .56), (.47, .56), (.39, .94), (.83, .40), (.55, .40)]), fill=color)
        elif name == "download":
            draw.line(points([(.5, .14), (.5, .68)]), fill=color, width=line)
            draw.line(points([(.25, .46), (.5, .71), (.75, .46)]), fill=color, width=line)
            draw.line(points([(.17, .67), (.17, .87), (.83, .87), (.83, .67)]), fill=color, width=line)
        elif name == "code":
            for coords in ([ (.34, .23), (.1, .5), (.34, .77)], [(.66, .23), (.9, .5), (.66, .77)], [(.58, .16), (.42, .84)]):
                draw.line(points(coords), fill=color, width=line)
        else:
            draw.ellipse((size * .10, size * .16, size * .56, size * .63), fill=color)
            draw.ellipse((size * .44, size * .16, size * .90, size * .63), fill=color)
            draw.polygon(points([(.12, .48), (.5, .9), (.88, .48)]), fill=color)
    image.save(path)
    return image.size


def overlays(source: Path, target: Path, elements: list[dict], work: Path,
             width: int, height: int, total: float, crf: int):
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(source)]
    filters, last = [], "0:v"
    for i, item in enumerate(elements, 1):
        if item["end"] > total + .04:
            raise PipelineError("元素结束时间超出最终时间线")
        path = work / f"element-{i}.png"
        w, h = make_element(item, path, width)
        x, y = round(width * item["x"]), round(height * item["y"])
        if x + w > width or y + h > height:
            raise PipelineError("图标/标签超出画面；请减小 size 或调整 x/y")
        args.extend(["-loop", "1", "-i", str(path)])
        fade = min(.15, (item["end"] - item["start"]) / 3)
        filters.append(f"[{i}:v]format=rgba,fade=t=in:st={item['start']}:d={fade}:alpha=1,"
                       f"fade=t=out:st={item['end']-fade}:d={fade}:alpha=1[el{i}]")
        filters.append(f"[{last}][el{i}]overlay=x={x}:y={y}:enable='between(t,{item['start']},{item['end']})'[o{i}]")
        last = f"o{i}"
    args.extend(["-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
                 "-map", f"[{last}]", "-map", "0:a", "-t", str(total), "-c:v", "libx264", "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-c:a", "copy", str(target)])
    run_command(args)


def generate_sound(name: str, target: Path):
    """Own synthesized signals, no external recordings or random samples."""
    seconds = {"whoosh": .45, "pop": .16, "click": .07, "ding": .8}[name]
    rate, phase = 48000, 0.0
    samples = []
    seed = 42
    for i in range(round(rate * seconds)):
        t = i / rate
        if name == "whoosh":
            seed = (1664525 * seed + 1013904223) & 0xffffffff
            noise = seed / 2**31 - 1
            value = noise * math.sin(math.pi * t / seconds) ** 2 * .3
        else:
            f = {"pop": 500 - 1800 * t, "click": 1800, "ding": 1046}[name]
            phase += 2 * math.pi * max(80, f) / rate
            value = (math.sin(phase) + .2 * math.sin(phase * 2)) * math.exp(-t * (8 if name == "ding" else 40)) * .5
        value *= min(1, t / .004)  # Avoid an initial hard edge.
        samples.append(struct.pack("<h", round(max(-1, min(1, value)) * 32767)))
    with wave.open(str(target), "wb") as stream:
        stream.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        stream.writeframes(b"".join(samples))


def sound_track(items: list[dict], target: Path, work: Path, total: float):
    args = ["ffmpeg", "-y", "-v", "error"]
    filters, names = [], []
    for i, item in enumerate(items):
        if item["start"] >= total:
            raise PipelineError("音效开始时间超出最终时间线")
        file = Path(item["file"]) if "file" in item else work / f"sfx-{i}.wav"
        if "file" not in item:
            generate_sound(item["name"], file)
        args.extend(["-i", str(file)])
        filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,volume={item['volume']},"
                       f"adelay={round(item['start']*1000)}:all=1,apad,atrim=duration={total}[s{i}]")
        names.append(f"[s{i}]")
    filters.append("".join(names) + f"amix=inputs={len(items)}:normalize=0,alimiter=limit=.9:latency=1[out]")
    args.extend(["-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
                 "-map", "[out]", "-t", str(total), "-ar", "48000", "-c:a", "pcm_s16le", str(target)])
    run_command(args)


def mix_narration(picture: Path, target: Path, work: Path, total: float, *,
                  voice: Path | None, music: Path | None, music_volume: float,
                  sounds: list[dict], subtitles: Path | None, crf: int) -> dict[str, Path]:
    stems = {}
    if voice:
        normalized = work / "voice.wav"
        run_command(["ffmpeg", "-y", "-v", "error", "-i", str(voice), "-af",
                     f"highpass=f=75,loudnorm=I=-16:TP=-1.8:LRA=8,apad,atrim=duration={total}",
                     "-ar", "48000", "-ac", "2", str(normalized)])
        stems["连续配音"] = normalized
    if music:
        bg = work / "music.wav"
        args = ["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(music)]
        bgfilter = f"atrim=duration={total},asetpts=PTS-STARTPTS,volume={music_volume},afade=t=in:d={min(.7,total/4)},afade=t=out:st={max(0,total-1.4)}:d={min(1.4,total)}"
        if voice:
            args.extend(["-i", str(stems["连续配音"]), "-filter_complex",
                         f"[0:a]{bgfilter}[bg];[bg][1:a]sidechaincompress=threshold=.018:ratio=6:attack=15:release=240[out]", "-map", "[out]"])
        else:
            args.extend(["-af", bgfilter])
        args.extend(["-t", str(total), "-ar", "48000", "-ac", "2", str(bg)])
        run_command(args)
        stems["背景音乐（配音避让）"] = bg
    if sounds:
        fx = work / "sound-effects.wav"
        sound_track(sounds, fx, work, total)
        stems["提示音效"] = fx
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(picture)]
    filters = [f"[0:a]volume={.15 if voice else 1},apad,atrim=duration={total}[source]"]
    names = ["[source]"]
    for i, file in enumerate(stems.values(), 1):
        args.extend(["-i", str(file)])
        names.append(f"[{i}:a]")
    filters.append("".join(names) + f"amix=inputs={len(names)}:normalize=0,alimiter=limit=.95:latency=1[a]")
    # Mix audio independently: FFmpeg 8 can stall when an apad/amix graph and
    # subtitle video filter share the same demuxer in a single encode.
    master = work / "master.wav"
    args.extend(["-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
                 "-map", "[a]", "-t", str(total), "-ar", "48000", "-ac", "2", str(master)])
    run_command(args)
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(picture), "-i", str(master),
            "-filter_threads", "1", "-map", "0:v", "-map", "1:a"]
    if subtitles:
        require_subtitles()
        args.extend(["-vf", f"subtitles=filename='{escape_subtitle_path(subtitles)}'", "-c:v", "libx264", "-crf", str(crf)])
    else:
        args.extend(["-c:v", "copy"])
    args.extend(["-t", str(total), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)])
    run_command(args)
    return stems
