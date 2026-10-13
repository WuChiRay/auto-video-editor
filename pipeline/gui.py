"""Small local desktop UI for the same CLI pipeline."""
from __future__ import annotations

import contextlib
import io
import queue
import threading
import uuid
import sys
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__


class QueueWriter(io.TextIOBase):
    def __init__(self, events):
        self.events = events

    def write(self, text):
        if text:
            self.events.put(("log", text))
        return len(text)

    def flush(self):
        pass


def main(*, smoke_test: bool = False, smoke_report: Path | None = None) -> int:
    root = tk.Tk()
    root.title(f"Auto Video Editor {__version__}")
    root.geometry("860x820")
    root.minsize(720, 720)
    panel = ttk.Frame(root, padding=20)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="本地自动剪辑", font=("PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei", 18, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(panel, text="按剪辑计划输出成片；未选择计划时，自动去除较长静音段。").grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(8, 14))
    values = {name: tk.StringVar() for name in ("input", "plan", "music", "output", "heading", "narration-text")}
    values["output"].set(str(Path.home() / ("Movies" if sys.platform == "darwin" else "Videos") / "auto-edit" / "final.mp4"))
    busy = [False]
    events = queue.Queue()

    def choose(name):
        if name == "input":
            selected = filedialog.askdirectory(title="选择素材文件夹")
        elif name == "output":
            selected = filedialog.asksaveasfilename(title="成片保存位置", defaultextension=".mp4",
                filetypes=[("MP4", "*.mp4")])
        else:
            types = ([("剪辑计划", "*.json")] if name == "plan" else [("完整口播", "*.txt")]
                if name == "narration-text" else [("音频", "*.wav *.mp3 *.m4a *.aac"), ("所有文件", "*.*")])
            selected = filedialog.askopenfilename(title="选择文件", filetypes=types)
        if selected:
            values[name].set(selected)

    for row, (name, label) in enumerate([
        ("input", "素材文件夹"), ("plan", "剪辑计划（可选）"),
        ("music", "背景音乐（可选）"), ("output", "成片保存位置"), ("heading", "系列名称（可选）"),
        ("narration-text", "完整口播 TXT（可选）")
    ], 2):
        ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(panel, textvariable=values[name]).grid(row=row, column=1, sticky="ew", padx=8)
        if name != "heading":
            ttk.Button(panel, text="选择", command=lambda key=name: choose(key)).grid(row=row, column=2)
    panel.columnconfigure(1, weight=1)
    voice = tk.StringVar(value="mature 成熟青年男声")
    transition = tk.StringVar(value="使用计划")
    look = tk.StringVar(value="使用计划")
    for row, label, value, choices in [
        (8, "配音声音", voice, ["mature 成熟青年男声", "warm 温暖男声", "steady 沉稳男声", "female 女声"]),
        (9, "转场", transition, ["使用计划", "cut 直接切换", "fade 淡化", "wipeleft 左擦除", "slideright 右滑", "circleopen 圆形展开", "dissolve 溶解"]),
        (10, "滤镜", look, ["使用计划", "none 原色", "warm 暖色", "cool 冷色", "vivid 鲜明", "mono 黑白", "cinematic 电影色调"]),
    ]:
        ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Combobox(panel, textvariable=value, values=choices, state="readonly").grid(row=row, column=1, sticky="w", padx=8)
    size = tk.StringVar(value="720×1280 竖屏")
    ttk.Label(panel, text="画面尺寸").grid(row=11, column=0, sticky="w", pady=8)
    ttk.Combobox(panel, textvariable=size, state="readonly",
        values=["720×1280 竖屏", "1080×1920 竖屏", "1920×1080 横屏"]).grid(row=11, column=1, sticky="w", padx=8)
    mute = tk.BooleanVar(value=False)
    draft = tk.BooleanVar(value=False)
    options = ttk.Frame(panel)
    options.grid(row=12, column=0, columnspan=3, sticky="w", pady=8)
    ttk.Checkbutton(options, text="原片静音", variable=mute).pack(side="left")
    ttk.Checkbutton(options, text="同时生成可编辑剪映草稿", variable=draft).pack(side="left", padx=20)
    ttk.Label(panel, text="画面在本机处理；连续配音需联网，仅发送口播文本。图标/标签/音效可在计划中配置。").grid(
        row=13, column=0, columnspan=3, sticky="w", pady=(0, 8))
    actions = ttk.Frame(panel)
    actions.grid(row=14, column=0, columnspan=3, sticky="ew", pady=8)
    status = tk.StringVar(value="就绪")
    log = tk.Text(panel, height=12, wrap="word", state="disabled")
    log.grid(row=16, column=0, columnspan=3, sticky="nsew")
    panel.rowconfigure(16, weight=1)
    ttk.Label(panel, textvariable=status).grid(row=15, column=0, columnspan=3, sticky="w", pady=6)

    def launch(args):
        if busy[0]:
            return
        busy[0] = True
        start.configure(state="disabled")
        status.set("处理中…")
        def worker():
            from .cli import main as run_pipeline
            writer = QueueWriter(events)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    code = run_pipeline(args)
            except Exception as exc:
                events.put(("log", f"任务失败：{exc}\n"))
                code = 2
            events.put(("done", code))
        threading.Thread(target=worker, daemon=True).start()

    def render():
        if not values["input"].get().strip():
            messagebox.showinfo("选择素材", "请先选择素材文件夹。")
            return
        output = Path(values["output"].get())
        if output.exists() and not messagebox.askyesno("覆盖成片", "保存位置已有文件，是否覆盖？"):
            return
        dimensions = size.get().split()[0].split("×")
        args = ["--input", values["input"].get(), "--output", str(output),
            "--work", str(output.parent / "work"), "--width", dimensions[0], "--height", dimensions[1]]
        for name in ("plan", "music", "heading", "narration-text"):
            if values[name].get().strip():
                args += ["--" + name, values[name].get().strip()]
        if values["narration-text"].get().strip():
            args += ["--voice", voice.get().split()[0]]
        if transition.get() != "使用计划":
            args += ["--transition", transition.get().split()[0]]
        if look.get() != "使用计划":
            args += ["--filter", look.get().split()[0]]
        if mute.get():
            args.append("--mute-source")
        if draft.get():
            folder = output.parent / (output.stem + "_draft_" + uuid.uuid4().hex[:6])
            args += ["--draft", str(folder)]
        launch(args)

    def import_project():
        if busy[0]:
            return
        folder = filedialog.askdirectory(title="选择已生成的完整草稿文件夹（先退出剪映）")
        if folder:
            args = ["--install-draft", folder]
            if sys.platform == "darwin":
                from .draft_install import default_draft_root
                try:
                    initial = str(default_draft_root())
                except RuntimeError:
                    initial = str(Path.home() / "Movies")
                target = filedialog.askdirectory(title="确认剪映设置中的草稿保存目录", initialdir=initial)
                if not target:
                    return
                args += ["--draft-root", target]
            launch(args)

    start = ttk.Button(actions, text="开始剪辑", command=render)
    start.pack(side="left")
    def preview():
        if not values["narration-text"].get().strip():
            messagebox.showinfo("配音试听", "请先选择完整口播 TXT 文件。")
            return
        output = filedialog.asksaveasfilename(title="保存试听音频", defaultextension=".mp3", filetypes=[("MP3", "*.mp3")])
        if output:
            launch(["--narration-text", values["narration-text"].get(), "--voice", voice.get().split()[0], "--voice-preview", output])
    ttk.Button(actions, text="生成配音试听", command=preview).pack(side="left", padx=12)
    ttk.Button(actions, text="导入剪映草稿", command=import_project).pack(side="left", padx=12)

    def tick():
        while not events.empty():
            kind, value = events.get_nowait()
            if kind == "log":
                log.configure(state="normal")
                log.insert("end", value)
                log.see("end")
                log.configure(state="disabled")
            else:
                busy[0] = False
                start.configure(state="normal")
                status.set("完成，文件路径见日志。" if value == 0 else "任务失败，原因见日志。")
        root.after(100, tick)

    def close():
        if busy[0]:
            messagebox.showinfo("任务处理中", "请等待当前任务完成后关闭程序。")
        else:
            root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    tick()
    if smoke_test:
        def verify_window():
            root.update_idletasks()
            if smoke_report:
                smoke_report.write_text(json.dumps({"gui_ready": True,
                    "width": root.winfo_width(), "height": root.winfo_height()}), encoding="utf-8")
            print(f"GUI_SMOKE_OK size={root.winfo_width()}x{root.winfo_height()}", flush=True)
            root.destroy()
        root.after(500, verify_window)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
