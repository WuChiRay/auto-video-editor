# Mac 版使用说明（0.4.1+）

## 选择下载包

在 [GitHub Releases](https://github.com/WuChiRay/auto-video-editor/releases/latest) 选择：

- **M1 / M2 / M3 / M4 等 Apple Silicon**：`macos-arm64.dmg`。
- **Intel Mac**：`macos-x64.dmg`。

也提供同架构 ZIP，方便携带 CLI、文档与 Skill。支持范围为 **macOS 15 及以上**；两种架构分别在 GitHub 的 macOS 15 环境构建和验证。更老版本尚未验证，不建议直接作为受支持系统。

## 安装与打开

1. 先安装 FFmpeg。已安装 [Homebrew](https://brew.sh/) 的用户在终端执行：

   ```bash
   brew install ffmpeg-full
   ```

   需要含 `subtitles/libass` 的完整 FFmpeg；当前 Homebrew 的精简 `ffmpeg` 缺少字幕支持，因此使用 `ffmpeg-full`。它是单独安装的外部工具，不包含在应用包中。程序支持 Finder 启动时查找两种架构的 Homebrew 路径和 `opt/ffmpeg-full/bin`；也可把自有完整 FFmpeg/ffprobe 放在应用旁的 `bin/`。
2. 打开 DMG，把 `AutoVideoEditor.app` 拖入“应用程序”。Python 与剪辑、配音、图像叠加、草稿依赖已包含，无需单独安装 Python。
3. 从“应用程序”打开，选择素材文件夹、剪辑计划（可选）、保存位置和口播 TXT（可选）。默认输出到 `~/Movies/auto-edit/`，可先点“生成配音试听”。
4. 本包使用临时签名（ad-hoc），**没有 Apple Developer ID 签名或苹果公证**。下载后可能被 Gatekeeper 阻止；确认来自本仓库的发布页后，按系统“隐私与安全性”中的“仍要打开”流程处理。不要把临时签名理解为苹果安全认证。

## CLI 与 Codex

应用内部包含 CLI，即使只把 `.app` 拖入“应用程序”，仍可使用：

```bash
/Applications/AutoVideoEditor.app/Contents/MacOS/auto-edit --version
/Applications/AutoVideoEditor.app/Contents/MacOS/auto-edit --input ./input --plan ./plan.json --output ./output/final.mp4 --mute-source --draft ./output/editable-project
```

ZIP 解压目录还提供 `./auto-edit` 入口；不要把这个符号链接单独移动出去。

安装 Codex Skill：在解压目录执行 `bash install_skill.command`。若只保留了应用，可执行：

```bash
bash /Applications/AutoVideoEditor.app/Contents/Resources/distribution/install_skill.command
```

在 Codex 中使用 `$auto-video-editor`，并告知上面的 CLI 路径。技能安装到 `${CODEX_HOME:-~/.codex}/skills/auto-video-editor`。

## 字体、字幕和草稿

- 中文标签自动查找苹方、黑体或宋体系统字体；新 macOS 的字体资源位置也参与查找。不分发苹果字体，仍支持在元素中指定自有 `font`。
- 字幕使用 Mac 中文字体族，避免强制引用 Windows 微软雅黑。
- GUI 的“导入剪映草稿”会先选择完整草稿包，再确认 **剪映设置中的草稿保存目录**。导入前退出剪映/CapCut，程序检测常见运行进程并阻止继续写索引。
- CLI 自动识别已有的 `~/Movies/JianyingPro/...`、`~/Movies/CapCut/...` 等草稿目录；未找到时明确报错。自定义位置用：

  ```bash
  /Applications/AutoVideoEditor.app/Contents/MacOS/auto-edit --install-draft ./output/editable-project --draft-root '/你在剪映设置里看到的草稿目录'
  ```

导入仍会复制素材、重定位路径、备份索引、避免覆盖同名工程。分享整个草稿目录即可，不必连接作者电脑。草稿里的 `.cmd` 是 Windows 入口；Mac 使用应用导入按钮或上述 CLI。

基础草稿保留原生速度与独立标题；丰富效果草稿的视觉效果已合成，配音/字幕/音乐/音效分轨。**自动检查通过不等于在 Mac 剪映桌面里打开验收通过**，剪映版本兼容与实际导出效果仍需使用者检查。

## 验证范围

发布流程在 Apple Silicon 和 Intel 环境执行源代码测试；对解压后的应用验证临时签名、GUI 启动、无 Homebrew shell PATH 时的 FFmpeg 查找、基础/丰富剪辑、中文标签、草稿时长与分轨，并校验 DMG 镜像。

未包含 Whisper 转写模型。连续配音仍需要联网且只发送口播文本；已有录音可全本地处理。配音的自然度需试听，在线服务条件与 v0.4.0 相同。

开发者从源码使用：安装 Python 3.11+（GUI 还需可用 Tk）、FFmpeg，建立虚拟环境后安装 `.[draft,voice,visual]`。Mac 原生打包用 `python scripts/build_macos.py`，每种架构各自构建；不在 Windows 上伪造 Mac 可执行文件。
