本版提供 Windows，以及 Apple Silicon 和 Intel Mac 的桌面应用和 CLI。下载包包含 Python 运行时、连续神经配音、丰富元素和剪映草稿依赖；无需连接作者电脑。

Mac 用户选择 `macos-arm64.dmg`（M 系列）或 `macos-x64.dmg`（Intel），拖入“应用程序”。支持 macOS 15+，先单独安装 `brew install ffmpeg-full`。也提供带 Skill 和使用说明的 ZIP。

Mac 适配包括系统中文字体、Finder 启动的 FFmpeg 路径查找、Movies 默认输出目录、已有剪映/CapCut 草稿目录识别，以及 CLI/GUI 草稿导入。

Windows 用户使用 `windows-x64.zip`，仍需单独安装 FFmpeg。Python 用户可安装 wheel 的 `[draft,voice,visual]` extras。

验证：Windows 与 Mac 的源代码测试、实际打包程序剪辑和草稿测试通过；两种 Mac 架构的解压应用验证了 GUI 启动、中文标签、Finder 环境下渲染和 DMG 镜像。发布仅在全部构建检查通过后进行。

Mac 包使用临时签名（ad-hoc），没有 Apple Developer ID 签名或苹果公证，首次打开可能需要系统“隐私与安全性”中的“仍要打开”。签名验证不等于苹果认证。

草稿时间、素材和分轨有自动验证，但 Mac 剪映桌面中的实际打开、编辑和导出仍需用户验收。丰富视觉效果已合成在画面，配音、字幕、音乐与音效分轨。在线配音仅发送口播文本，声音的自然与情感仍需试听。

详见仓库的 `docs/MACOS.md` 和 `docs/ENHANCEMENTS.md`。源码、应用及草稿格式适配不代表剪映、CapCut 或苹果官方认可。
