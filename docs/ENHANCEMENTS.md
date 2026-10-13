# 连续配音与丰富元素（0.4.0）

## 一条命令

准备 `input/sample.mp4`，从项目根目录执行：

```powershell
python -m pip install '.[draft,voice,visual]'
python -m pipeline --input input --plan examples/enhanced-plan.json --output output/demo.mp4 --width 720 --height 1280 --mute-source --draft output/demo-draft
```

Windows 包已包含配音、图标和草稿依赖，把 `python -m pipeline` 换成 `auto-edit.exe` 即可。GUI 可选择口播 TXT、声音、转场和滤镜；标签、图标、逐段特效和提示音通过计划配置。

先试听，再渲染：

```powershell
auto-edit.exe --narration-text examples/narration.txt --voice mature --voice-preview output/preview.mp3
```

试听产生 MP3、SRT 和 `.words.json`。在 Codex 中可以直接说：“用 auto-video-editor 剪辑，使用成熟青年声音，整段连贯口播，加克制的转场和标签，先生成试听。”

## 配音

`narration` 为计划顶层对象，`text`（完整文本）、`text_file`（UTF-8 文件）、`audio`（已有录音）三选一：

```json
{"narration": {"text_file": "narration.txt", "voice": "mature", "rate": "+4%", "pitch": "+0Hz", "fit": "extend_last"}}
```

- `mature`：云健，成熟青年男声，已联网验证；`warm`：云希；`steady`：云扬；`female`：晓晓。其余声音预设可选择，但未逐一试听验收。也可填服务支持的神经声音 ID。
- 完整口播一次请求合成，保留语句的上下文和停连；不按字幕短句分别合成。不使用系统机械语音降级。
- 每段口播限 3000 UTF-8 字节（约 1000 个汉字），避免库在传输上限处分段。长节目按章节设计，不承诺无限长单次请求。
- 默认自然语速 `+4%`。文字应使用标点和口语表达，避免列表编号、参数堆砌和逐字停顿。声音的感染力仍需要试听判断，程序不能保证任意文案都像真人。
- 根据字词时间生成全片 SRT，检查与文本一致、时间单调且不重叠。服务失败明确报错，最多两次请求；不产生伪成功音频。
- `fit: "extend_last"` 默认在口播超过画面时定格延长最后一帧，保留原速；`"error"` 则报错。不会为迁就画面偷偷加速口播。`--voice-fit` 可覆盖。
- 可以使用 `{"narration":{"audio":"voice.wav","subtitles":"voice.srt"}}` 全本地运行。字幕可省略，此时仅加入配音，不自动转写录音。
- `--narration-text`、`--narration-audio`、`--narration-subtitle`、`--voice`、`--voice-rate` 可覆盖计划。负语速用 `--voice-rate=-4%`。
- 输出旁保存 `.narration.mp3` 或原录音格式、`.srt`、合成配音的 `.words.json`，方便试听和后续编辑。

配音依赖 Edge 在线语音服务，**只发送口播文本，视频仍在本机处理**。需要联网；服务可用性、声音和商业使用条件由服务提供方决定。无 SLA，也不等同于正式 Azure Speech 商业服务。正式收费服务宜接入有授权与服务协议的 TTS，或传入已有配音文件。

## 画面与音效配置

| 元素 | 已支持预设 | 配置位置 |
|---|---|---|
| 转场 | cut、fade、wipeleft、slideright、circleopen、dissolve | 顶层 `transition` |
| 滤镜 | none、warm、cool、mono、vivid、cinematic | 每个 clip 的 `filter` 或 CLI `--filter` |
| 特效 | zoom_in、vignette、fade | 每个 clip 的 `effects` 数组 |
| 图标 | check、play、bolt、heart、download、code | 顶层 `elements` |
| 标签 | 自动换行、颜色、背景、淡入淡出 | `elements` 的 label |
| 图片 | 自有 Logo/贴图，保留透明度 | `elements` 的 image |
| 音效 | whoosh、pop、click、ding，或自有音频 | 顶层 `sound_effects` |
| 混音 | 配音响度处理、配乐避让、音乐淡入淡出、总混音限幅 | 有配音/BGM 时自动启用 |

示例：

```json
{
  "clips": [
    {"file":"sample.mp4", "start":0, "end":4, "filter":"warm", "effects":["zoom_in"]},
    {"file":"sample.mp4", "start":4, "end":8, "filter":"vivid"}
  ],
  "transition":{"name":"fade", "duration":0.35},
  "elements":[
    {"type":"label", "text":"一句话，完成剪辑", "start":0.3, "end":3.5, "x":0.08, "y":0.2, "size":0.75, "color":"#ffffff", "background":"#173447dd"},
    {"type":"icon", "name":"check", "start":4, "end":6, "x":0.1, "y":0.4, "size":0.12},
    {"type":"image", "file":"logo.png", "start":4, "end":7, "x":0.7, "y":0.1, "size":0.15}
  ],
  "sound_effects":[{"name":"whoosh", "start":3.5, "volume":0.2}, {"file":"notify.wav", "start":6, "volume":0.15}]
}
```

图片/声音/TXT/SRT/字体路径以 **计划文件所在目录** 为基准；clip 素材仍以 `--input` 为基准。元素与音效时间为 **转场后的最终全片秒数**。`x/y` 是左上角相对画面的位置，`size` 是最大宽度占画面宽度的比例；图片高度也限制在该尺寸内。标签按宽度换行。越界元素报错，不会悄悄裁掉。

转场以相邻片段重叠实现，时长按帧率取整且必须小于各片段时长的一半。例如两段各 4 秒、0.4 秒转场，总画面时长约 7.6 秒。`cut` 不重叠。`--dry-run` 只验证计划并保存配置，最终时长在渲染后写入报告；口播尚未合成时不能预知准确时长。

内置图标为程序绘制，音效为本地信号合成，不抓取商业素材。中文标签在 Windows 使用系统微软雅黑；Linux 安装 `fonts-noto-cjk` 或在元素中指定 `font` 文件。字体不随程序分发。默认没有二维码、装饰元素或音效；显示的字只来自明确提供的标题、标签和口播，不自动显示时长/速度参数。

有配音时原片音量降至 15%；需要完全移除时加 `--mute-source`。BGM 使用 `--music`，默认音量 0.12，并按配音自动压低。音效默认音量 0.25，可逐项调整；密集效果可能干扰语音，建议在少量关键节点使用。

## 剪映草稿

基础计划继续导出独立动作片段、原生速度、标题和 BGM。启用丰富元素或配音时，导出 **合成画面 + 连续配音 + 口播字幕 + 配乐 + 提示音效**（存在时）的独立轨道。

丰富元素草稿的转场、滤镜、图标、标签、特效及 clip 标题已经合成在视频中，不能在剪映中直接修改其原始效果参数；修改计划重新生成即可。配乐包含已计算的语音避让；修改配音后需重新计算。MP4 的总混音有限幅，草稿导出仍应检查音量。`--draft-only` 的丰富计划也要本地渲染画面，才能创建草稿。

草稿结构、时长、素材路径与跨目录重定位有自动验证；本次丰富元素版本尚未在剪映 GUI 中逐项验收。不要把旧版基础草稿的实测情况当作所有新效果的兼容保证。

## 后续能力

运动跟踪、自动踩点、人物抠像、AI 自动生成贴纸、复杂粒子和模板商店尚未实现。当前通过 JSON 组合常用元素；未来可以沿着素材授权清晰的效果包和正式 TTS 适配器扩展。
