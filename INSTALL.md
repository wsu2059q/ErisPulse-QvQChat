# QvQChat 安装指南

## Docker 安装（推荐）

### 1. 克隆仓库

```bash
git clone https://github.com/wsu2059q/ErisPulse-QvQChat.git
cd ErisPulse-QvQChat
```

### 2. 准备 config.toml

```bash
cp config.example.toml config.toml
```

编辑 `config.toml`，填写机器人识别信息：

```toml
[QvQChat]
bot_nicknames = ["你的机器人昵称"]
bot_ids = ["你的机器人QQ号"]
```

`config.toml` 仅包含基础设置（速率限制、窥屏模式、消息长度限制等）。**AI 模型配置不在此文件中**，请通过 Dashboard 管理。

### 3. 启动容器

```bash
docker-compose up -d
```

容器基于 `erispulse/erispulse` 官方镜像构建，已内置 QvQChat 模块和常用适配器。

### 4. 安装适配器

进入容器安装需要的平台适配器：

```bash
docker exec -it qvqchat bash
epsdk install OneBot11    # QQ 适配器
epsdk install Yunhu       # 云湖适配器
epsdk install Telegram    # Telegram 适配器
exit
```

重启容器使适配器生效：

```bash
docker-compose restart qvqchat
```

适配器的连接配置（URL、Token 等）在 Dashboard 或 `config.toml` 的对应适配器小节中填写，请参考所选 OneBot 实现或平台文档。

### 5. 打开 Dashboard 配置 AI 模型和行为

容器启动后，浏览器访问 `http://<服务器IP>:8000` 进入 Dashboard Web 管理面板：

- **添加 AI 模型** — 填写 API 地址、密钥，勾选模型能力（对话、记忆、视觉、意图识别等）
- **分配模型到行为** — 将模型绑定到对应功能模块（对话 AI、记忆 AI、意图识别 AI 等）
- **配置高级功能** — 多智能体协作、知识库管理、MCP 工具调用、语音合成等

---

## 手动安装

### 1. 安装 ErisPulse 框架

```bash
pip install erispulse
```

### 2. 安装适配器

```bash
epsdk install OneBot11   # 或其他平台适配器
```

### 3. 安装 QvQChat

```bash
epsdk install QvQChat
```

### 4. 配置 config.toml

```bash
cp config.example.toml config.toml
```

编辑 `config.toml`，至少填写 `bot_nicknames` 和 `bot_ids`。如需配置适配器连接参数，在文件中对应的适配器小节填写。

### 5. 启动并打开 Dashboard

```bash
ep run
```

访问 `http://localhost:8000` 进入 Dashboard，添加 AI 模型并完成行为分配。

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

Docker：`docker-compose pull && docker-compose up -d`
手动：`epsdk update QvQChat`

**Q: 配置文件修改后需要重启吗？**

需要。`docker-compose restart qvqchat` 或手动重启 `ep run`。

**Q: 支持哪些 AI 服务商？**

OpenAI 及所有兼容 OpenAI API 格式的服务（SiliconFlow、DeepSeek 等），通过 Dashboard 添加即可。

**Q: 如何降低 API 成本？**

在 Dashboard 中为不同功能分配不同成本的模型；在 `config.toml` 中启用窥屏模式和速率限制。

**Q: 如何备份数据？**

Docker 部署的数据目录（`./data`、`./logs`）已挂载到宿主机，直接备份宿主机目录即可。手动部署备份 `data/` 和 `logs/` 目录。

**Q: 如何卸载？**

Docker：`docker-compose down`
手动：`epsdk uninstall QvQChat`

---

## 下一步

- [README.md](README.md) — 功能介绍和快速开始
- [config.example.toml](config.example.toml) — 完整配置选项
- [ARCHITECTURE.md](ARCHITECTURE.md) — 系统架构和技术细节

## 获取帮助

- GitHub Issues: https://github.com/wsu2059q/ErisPulse-QvQChat/issues
- 邮箱：wsu2059@qq.com
- QQ群：871684833
