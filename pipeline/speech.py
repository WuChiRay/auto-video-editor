"""Continuous neural narration and captions from provider word timestamps."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from .core import PipelineError, _srt_time, duration_of, subtitle_font

VOICES = {
    "mature": "zh-CN-YunjianNeural",
    "warm": "zh-CN-YunxiNeural",
    "steady": "zh-CN-YunyangNeural",
    "female": "zh-CN-XiaoxiaoNeural",
}


def normalize(text: str) -> str:
    return "".join(c.lower() for c in text if c.isalnum())


def captions_from_words(text: str, words: list[dict]) -> list[dict]:
    """Keep punctuation while grouping complete words into readable captions."""
    if not words or normalize(text) != normalize("".join(w["text"] for w in words)):
        raise PipelineError("配音字词时间与口播不匹配，停止生成字幕；请重试或提供人工校准字幕")
    positions = [i for i, c in enumerate(text) if c.isalnum()]
    result, cursor, group, previous_end = [], 0, None, 0.0
    for i, word in enumerate(words):
        count = len(normalize(word["text"]))
        if not count:
            continue
        start, end = word["offset"] / 1e7, (word["offset"] + word["duration"]) / 1e7
        if start < previous_end - .002 or end <= start:
            raise PipelineError("配音字词时间无效或重叠")
        previous_end = end
        left = positions[cursor] if cursor else 0
        cursor += count
        right = positions[cursor] if cursor < len(positions) else len(text)
        fragment = text[left:right]
        if group is None:
            group = {"start": start, "end": end, "text": ""}
        group["text"] += fragment
        group["end"] = end
        if len(normalize(group["text"])) >= 22 or re.search(r"[。！？；.!?;]", fragment) or i == len(words) - 1:
            result.append(group)
            group = None
    if group:
        result.append(group)
    # Avoid flashing a tiny leftover phrase for less than a second.
    merged = []
    for item in result:
        if merged and item["end"] - item["start"] < 1 and len(normalize(item["text"])) < 7 and not re.search(r"[。！？.!?]$", merged[-1]["text"].strip()):
            merged[-1]["text"] += item["text"]
            merged[-1]["end"] = item["end"]
        else:
            merged.append(item)
    result = merged
    for i, item in enumerate(result):
        next_start = result[i + 1]["start"] if i + 1 < len(result) else item["end"] + .18
        item["end"] = min(item["end"] + .18, next_start)
        item["text"] = item["text"].strip()
    return result


def write_captions(path: Path, captions: list[dict]) -> None:
    path.write_text("\n\n".join(
        f"{i}\n{_srt_time(c['start'])} --> {_srt_time(c['end'])}\n{c['text']}"
        for i, c in enumerate(captions, 1)) + "\n", encoding="utf-8")


def write_voice_ass(path: Path, captions: list[dict], width: int, height: int) -> None:
    def clock(t):
        cs = round(t * 100)
        h, cs = divmod(cs, 360000)
        m, cs = divmod(cs, 6000)
        s, cs = divmod(cs, 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
    size = max(12, round(min(width * .043, height * .065)))
    lines = [
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Voice,{subtitle_font()},{size},&H00FFFFFF,&H00FFFFFF,&H00202020,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,{round(width*.08)},{round(width*.08)},{round(height*.065)},1",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for c in captions:
        safe = c["text"].replace("\\", "").replace("{", "").replace("}", "").replace("\n", r"\N")
        lines.append(f"Dialogue: 0,{clock(c['start'])},{clock(c['end'])},Voice,,0,0,0,,{safe}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_captions(path: Path) -> list[dict]:
    def seconds(value):
        h, m, s = value.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    result = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        if not lines:
            continue
        if len(lines) < 3 or " --> " not in lines[1]:
            raise PipelineError("全片字幕必须为标准 UTF-8 SRT")
        a, b = lines[1].split(" --> ")
        start, end = seconds(a), seconds(b)
        if start < 0 or end <= start or (result and start < result[-1]["end"]):
            raise PipelineError("字幕时间必须递增且不重叠")
        result.append({"start": start, "end": end, "text": "\n".join(lines[2:])})
    if not result:
        raise PipelineError("字幕文件为空")
    return result


async def _synthesize(text: str, target: Path, voice: str, rate: str, pitch: str) -> list[dict]:
    try:
        import edge_tts
        import edge_tts.communicate as communicate
        from edge_tts.constants import TRUSTED_CLIENT_TOKEN
    except ImportError as exc:
        raise PipelineError("连续配音需要 pip install '.[voice]'，或使用 --narration-audio") from exc
    # Endpoint migration in October 2026 (upstream edge-tts PR #491).
    # Process-local compatibility shim; no credentials or installed files changed.
    if "speech.platform.bing.com" in communicate.WSS_URL:
        communicate.WSS_URL = (
            "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
            "?Ocp-Apim-Subscription-Key=" + TRUSTED_CLIENT_TOKEN)
    for attempt in range(2):
        words = []
        partial = target.with_suffix(".part")
        try:
            tts = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch,
                                       boundary="WordBoundary", receive_timeout=45)
            with partial.open("wb") as stream:
                async for item in tts.stream():
                    if item["type"] == "audio":
                        stream.write(item["data"])
                    elif item["type"] == "WordBoundary":
                        words.append(item)
            captions_from_words(text, words)
            if partial.stat().st_size == 0 or duration_of(partial) <= 0:
                raise PipelineError("服务未返回有效配音")
            partial.replace(target)
            return words
        except Exception as exc:
            partial.unlink(missing_ok=True)
            if attempt == 1:
                raise PipelineError(
                    f"连续神经配音失败：{exc}。请检查网络、稍后重试或提供录音；不会降级为机械系统声音。") from exc
            await asyncio.sleep(1)
    raise AssertionError("unreachable")


def synthesize(text: str, target: Path, *, voice: str = "mature", rate: str = "+4%",
               pitch: str = "+0Hz") -> tuple[Path, Path]:
    if not normalize(text):
        raise PipelineError("口播文本为空")
    # edge-tts itself chunks texts over its transport limit; forbid that here.
    if len(text.encode("utf-8")) > 3000 or len(escape(text).encode("utf-8")) > 4000:
        raise PipelineError("一段连续口播最多 3000 UTF-8 字节；长视频请人工划分章节配音")
    if not re.fullmatch(r"[+-]\d{1,2}%", rate) or not re.fullmatch(r"[+-]\d{1,2}Hz", pitch):
        raise PipelineError("语速/音高格式应为 +4% / +0Hz，范围不超过两位数")
    target.parent.mkdir(parents=True, exist_ok=True)
    words = asyncio.run(_synthesize(text, target, VOICES.get(voice, voice), rate, pitch))
    captions = captions_from_words(text, words)
    srt = target.with_suffix(".srt")
    write_captions(srt, captions)
    target.with_suffix(".words.json").write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, srt
