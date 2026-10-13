# 自动剪辑的共享与发布设计

## 先回答当前问题

别人默认不能连接你的本地电脑。现在的 `auto-video-editor` skill 和 `pipeline` CLI 都是在“调用者自己的电脑”上运行：

- 你在自己的 Codex 中使用时，Codex 调用你本机的 Python、FFmpeg 和本地素材；
- 别人在他的 Codex 中使用时，他需要安装同一个 skill 和 CLI，处理的是他自己的素材；
- 只有把流水线启动成网络服务，别人才可以把素材传到你的机器或云端处理。

因此，分享 skill 不等于把你的电脑变成远程剪辑服务器。

## 推荐路线：先做“可安装的本地工具”

第一阶段不需要部署服务器。把仓库发布到 GitHub、Gitee 或企业 Git，然后让使用者在自己的电脑上安装：

```text
仓库代码
  ├─ pipeline/                  CLI 实现
  ├─ skills/auto-video-editor/  Codex skill
  ├─ install_skill.ps1          Skill 安装脚本
  └─ pyproject.toml             Python 包入口
```

v0.3.0 已提供 Windows 图形程序、CLI、Python 包与 Skill。使用者可以选择：

1. Windows x64：下载 Releases 压缩包，解压并打开 `AutoVideoEditor.exe`，无需 Python；
2. Python 3.11+：安装源码或 wheel，剪映草稿需要 `draft` 扩展；
3. 两种方式都需要 FFmpeg 与 ffprobe；
4. 如需 Codex 自然语言调用，在下载目录运行 `install_skill.ps1`。

素材留在使用者电脑上。当前采用 MIT 许可证；云端服务、账户和计费尚未实现。安装与草稿兼容性说明以 README 为准。

## 三种共享形态

| 形态 | 别人如何使用 | 素材在哪里处理 | 复杂度 | 建议 |
|---|---|---|---:|---|
| 本地 CLI + Skill | 下载仓库，安装后运行 | 别人的电脑 | 低 | 当前首选 |
| 局域网服务 | 访问你的电脑地址或内网域名 | 你的工作机 | 中 | 团队内临时共享 |
| 云端服务 | 网页/API 上传素材并取回结果 | 云服务器/对象存储 | 高 | 面向大量用户或商业化 |

## 局域网服务的设计

如果团队需要把素材集中到一台工作机处理，可以在 CLI 外面增加 FastAPI 服务：

```text
客户端/Codex
      │ HTTPS 或内网 HTTP
      ▼
FastAPI API
      │ 创建 job_id、校验大小和格式
      ▼
本地任务队列（一次只跑有限任务）
      ▼
pipeline CLI
      ▼
jobs/<job_id>/input、work、output
```

最低要求：

- 每个任务使用独立目录，禁止多个任务共用 `input/`、`work/`、`output/`；
- 使用 token 或登录认证；
- 限制上传大小、视频时长、并发数和磁盘占用；
- 只返回任务状态和结果下载地址，不暴露任意本地路径；
- 默认只监听内网地址；需要公网访问时使用 HTTPS、反向代理和防火墙；
- 保留失败日志和自动清理策略。

这条路线适合 2～10 人内部使用。不要直接把 Python 开发服务器端口暴露到公网，也不要把整个素材目录做成网络共享盘。

## 云端服务的设计

面向外部用户时，建议把剪辑器拆成 API、队列、Worker 和对象存储：

```text
Web/Codex/API client
        │
        ▼
API + authentication ── PostgreSQL (job metadata)
        │
        ▼
Queue (Redis/RabbitMQ)
        │
        ▼
Video worker: FFmpeg + pipeline
        │
        ▼
Object storage: input/output files
```

需要另行决定：登录方式、计费、保留多久删除素材、并发 GPU/CPU、版权声明、失败重试和 CDN 下载。当前本地 CLI 可以作为 Worker 的核心，但需要把路径参数、任务状态和清理逻辑改成服务接口。

## Skill 的边界

Codex skill 是“如何调用工具的说明”，不是远程执行节点。给别人使用时有两种方式：

- 让每个人安装 skill 和 CLI，所有处理在个人电脑完成；
- 让 skill 调用一个已部署的 HTTPS API，此时 API 才是共享执行节点。

第二种方式需要在 skill 中写入 API 地址和认证方式，不能把你的 API key 写进公开 skill。应通过每个用户自己的环境变量或登录流程提供凭证。

## 发布顺序

建议按以下顺序推进：

1. 在 GitHub/Gitee 建立仓库，补充许可证、版本号和变更记录；
2. 发布一个 Windows 本地安装说明，先让另一台电脑完成 `input -> output/final.mp4`；
3. 将 CLI 打包成版本化 wheel 或安装包；
4. 再决定是否需要局域网 API；
5. 只有出现稳定的多人需求、上传存储和账号需求时，再建设云端服务。

不要一开始就部署公网服务。对当前流水线来说，先验证“别人能在自己的电脑上一键安装并完成一次渲染”比先做服务器更能发现真实问题。
