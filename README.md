# Auto Video Editor

本地优先的 AI 辅助剪辑工具：图形界面、CLI 和 Codex Skill 共用一条流水线，输出 MP4 与可编辑剪映草稿。

**普通用户：从 [GitHub Releases](https://github.com/WuChiRay/auto-video-editor/releases/latest) 下载 Windows x64 压缩包，解压后打开 `AutoVideoEditor.exe`。**
程序不需要安装 Python，但需要单独安装 FFmpeg。源码与 Python 包适合开发者、其他平台和自动化调用。

## 能做什么

- 按 JSON 计划选片、排列片段、变速、循环、添加动作标题和系列名称。
- 自动删除较长静音段，统一尺寸与帧率，输出 MP4 和剪辑报告。
- 混入用户提供的 BGM，烧录外部 SRT；Python 版可选本地 Whisper 转写。
- 导出视频、标题、BGM 分轨的剪映草稿，并重定位素材后导入。
- 通过 Skill 让 Codex 理解要求、编制计划、调用本地程序。

**程序本身不调用大模型，不会独立识别动作或决定最佳镜头。** 语义分析由调用者的 AI 或人工完成，计划交给本程序执行。倍速和时长只作为剪辑参数；除非用户明确要求，画面不出现这些参数。

## Windows 程序

1. 从 GitHub Releases 下载 `auto-video-editor-<版本>-windows-x64.zip`，解压整个目录，保留 `_internal` 文件夹。
2. 安装 FFmpeg，使 `ffmpeg` 与 `ffprobe` 位于 PATH：

   ```powershell
   winget install --id Gyan.FFmpeg --exact
   ```

   或从 [FFmpeg 官方下载入口](https://ffmpeg.org/download.html) 获取 Windows 构建，把两个可执行文件放到程序旁的 `bin/`。本项目不捆绑 FFmpeg。
3. 双击 `AutoVideoEditor.exe`，选择素材文件夹和成片保存位置。可选剪辑计划、配乐、系列名称及草稿输出。
4. 没有计划时使用静音粗剪；运动示范、音乐视频等应使用计划。GUI 为基础工作流，所有参数可通过 CLI 调整。

命令行和 AI 可直接调用同目录内的程序：

```powershell
.\auto-edit.exe --help
.\auto-edit.exe --input input --plan examples/plan.json --output output/final.mp4 --width 720 --height 1280
```

Windows 包不包含 Whisper 模型与转写依赖；自动转写请使用 Python 版。程序目前未进行代码签名；遇到操作系统拦截可选源码安装方式。

## Python 安装

需要 Python 3.11+、FFmpeg 和 ffprobe。下载仓库源码后，在项目目录执行：

```powershell
python -m pip install '.[draft]'
auto-edit --version
auto-edit-gui
```

如果命令入口不在 PATH，也可以用 `python -m pipeline` 或 `python -m pipeline.gui`。
安装下载的 wheel：`python -m pip install "local_auto_editor-0.3.0-py3-none-any.whl[draft]"`。

基础剪辑：

```powershell
python -m pipeline --input input --output output/final.mp4
```

使用计划、音乐与草稿：

```powershell
python -m pipeline --input input --plan examples/plan.json --output output/final.mp4 --width 720 --height 1280 --heading '训练示范' --mute-source --music assets/bgm.wav --draft output/editable-project
```

`sample.mp4` 和 `assets/bgm.wav` 需要由使用者提供，仓库不含任何用户视频或商业音乐。

## 剪辑计划

```json
{
  "clips": [
    {"file": "sample.mp4", "start": 0, "end": 7.2, "speed": 1.2, "output_duration": 6, "title": "动作一"},
    {"file": "sample.mp4", "start": 8, "end": 12.5, "speed": 1.2, "output_duration": 6, "loop": true, "title": "动作二"}
  ]
}
```

- 相对素材路径以 `--input` 为基准；时间单位为秒，变速支持 0.5–2 倍。
- `output_duration` 是成片时长；素材不足时需要显式设置 `loop: true`。
- `title` 是观众可见的动作标题，`--heading` 是系列名称。
- `keep: [[0, 3], [7, 10]]` 可指定同一个文件的多个范围。
- `--dry-run` 只写计划报告；每次运行采用独立的中间文件目录。
- `--subtitle` 与动作标题同时提供时，外部字幕优先。外部字幕按渲染后片段时间使用；涉及复杂剪切或倍速时请预先校准时间。

## 可编辑剪映草稿

已在 **剪映专业版 11.5.0.14471 / Windows** 实测打开。其他版本需要自行验证。

`--draft 目录` 同时输出草稿；`--draft-only` 只生成草稿。目录包含截取后的 1x 视频素材、独立文字和 BGM，速度保留在剪映时间线上。素材已截取，草稿不能恢复被舍弃的源视频部分。

退出剪映后，使用以下任意一种方式导入：

- Windows GUI：“导入剪映草稿”按钮，选择完整草稿文件夹。
- Windows CLI：`auto-edit.exe --install-draft "草稿文件夹"`，无需 Python。
- Python CLI：`python -m pipeline --install-draft "草稿文件夹"`。
- 草稿包自带 `双击导入.cmd`：需要 Python；也可运行 `python install_draft.py --root "自定义草稿根目录"`。

默认位置为当前 Windows 用户的剪映本地草稿目录；CLI 可通过 `--draft-root` 指定其他位置。导入复制素材、备份索引并避免覆盖已有同名项目。重新打开剪映，在“本地草稿”中编辑；不要把 JSON 当作视频素材导入。

草稿适配器暂不支持外部 SRT 或自动转写字幕，不自动操作剪映导出。分享时必须包含整个草稿目录及 `assets/`，无需分享原视频或连接作者电脑。

## 在 Codex 中调用

从源码或 Windows 包的根目录安装 Skill：

```powershell
.\install_skill.ps1
```

安装后在 Codex 中说：

```text
$auto-video-editor 把 input 里的视频按 plan.json 剪成竖屏，添加动作标题和我提供的 BGM，同时输出剪映草稿。时长和倍速只作为剪辑参数。
```

Skill 是本地工具的调用说明，不包含云端服务或大模型账号。使用你自己的 AI 工具及凭证；默认不上传素材。

## 可选功能与开发

```powershell
python -m pip install '.[transcribe]'
python -m pipeline --input input --transcribe --whisper-model base
python -m pip install '.[music]'
python scripts/make_sport_bgm.py assets/sport.wav --duration 48
python -X utf8 -m unittest discover -s tests -v
```

转写模型首次使用会下载。合成音乐脚本生成本地鼓点、贝斯和琶音，不使用外部采样。音乐及素材授权由使用者确认。

构建 Python 包与 Windows 程序：

```powershell
python -m pip install '.[draft,dev]'
python -m build
python scripts/build_release.py
```

Windows 构建脚本需要在 Windows x64 / Python 3.11 环境运行。GitHub Actions 提供合成素材集成测试与版本标签构建；源码和可执行文件均不包含个人媒体。

共享/服务部署设计见 [docs/SHARING_DESIGN.md](docs/SHARING_DESIGN.md)。许可为 [MIT](LICENSE)，第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目与剪映、CapCut 及其厂商没有隶属关系。
