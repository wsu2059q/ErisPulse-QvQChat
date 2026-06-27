# QvQChat 安装指南

## Docker 安装（推荐，ghcr 镜像）

### 一行启动

```bash
docker run -d --name qvqchat -p 8000:8000 --restart unless-stopped ghcr.io/wsu2059q/erispulse-qvqchat:latest
```

容器基于 `erispulse/erispulse` 官方镜像构建，已内置 QvQChat 模块。

> 所有配置通过 Dashboard Web 面板管理，无需手动编辑配置文件。

### 安装适配器

在 Dashboard 中安装所需的平台适配器（OneBot11 / 云湖 / Telegram 等），连接配置一并填写

### 打开 Dashboard

浏览器访问 `http://<服务器IP>:8000` 进入 Dashboard Web 管理面板：

- **添加 AI 模型** — 填写 API 地址、密钥，勾选模型能力（对话、记忆、视觉、意图识别等）
- **分配模型到行为** — 将模型绑定到对应功能模块
- **配置高级功能** — 多智能体协作、知识库管理、MCP 工具调用、语音合成等

---

## 手动安装

```bash
pip install erispulse
pip install ErisPulse-QvQChat
ep run
```

启动后打开 `http://localhost:8000/Dashboard`，所有配置（适配器、AI 模型、行为等）均在 Dashboard 中完成。

---

## Dashboard 配置

所有 AI 相关配置均在 Dashboard Web 管理面板中完成：

| 配置项 | 说明 |
|--------|------|
| AI 模型 | 添加 API 地址、密钥，勾选对话/记忆/视觉/意图识别等能力 |
| 行为分配 | 为对话、记忆、意图识别、视觉理解等功能分别指定使用的模型 |
| 多智能体 | 启用并配置多个 Agent 协作 |
| 知识库 | 管理知识库内容，设置检索参数 |
| MCP 工具 | 管理 MCP 工具服务，自动注入工具调用指令 |
| 语音合成 | 配置语音合成服务和参数 |

修改 Dashboard 中的配置后即时生效，无需重启。

---

## 常见问题

**Q: Docker 安装后无法连接适配器？**

检查端口映射、适配器配置和网络连接。查看容器日志：`docker logs -f qvqchat`

**Q: 如何更新到最新版本？**

Docker：`docker pull ghcr.io/wsu2059q/erispulse-qvqchat:latest && docker restart qvqchat`
手动：`epsdk update QvQChat`

**Q: 支持哪些 AI 服务商？**

OpenAI 及所有兼容 OpenAI API 格式的服务（SiliconFlow、DeepSeek 等），通过 Dashboard 添加即可。

**Q: 如何降低 API 成本？**

在 Dashboard 中为不同功能分配不同成本的模型，配置窥屏模式和速率限制。

**Q: 如何备份数据？**

Docker 部署的数据目录（`./data`、`./logs`）已挂载到宿主机，直接备份宿主机目录即可。手动部署备份 `data/` 和 `logs/` 目录。

**Q: 如何卸载？**

Docker：`docker rm -f qvqchat`
手动：`epsdk uninstall QvQChat`

---

## 下一步

- [README.md](README.md) — 功能介绍和快速开始
- [ARCHITECTURE.md](ARCHITECTURE.md) — 系统架构和技术细节

## 获取帮助

- GitHub Issues: https://github.com/wsu2059q/ErisPulse-QvQChat/issues
- 邮箱：wsu2059@qq.com
- QQ群：871684833
