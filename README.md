# QvQChat

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![ErisPulse](https://img.shields.io/badge/ErisPulse-2.5.0+-orange.svg)](https://github.com/ErisPulse/ErisPulse)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/ghcr-erispulse--qvqchat-blue?logo=docker)](https://github.com/wsu2059q/ErisPulse-QvQChat/pkgs/container/erispulse-qvqchat)

基于行为系统的多模型 AI 智能对话模块，驱动于 [ErisPulse](https://github.com/ErisPulse/ErisPulse) 框架，支持 Dashboard 全功能管理。



## 核心理念

**模型池 + 行为绑定**：用户添加 AI 模型（带能力标记），配置行为（对话/记忆/意图/自定义），为行为分配模型（多模型冗余备用）。所有配置通过 Dashboard Web 管理面板完成。

## 功能

| 模块 | 说明 |
|------|------|
| 模型池 | 管理 AI 模型，标记能力（文本对话/图片识别/工具调用） |
| 行为管理 | 配置行为（对话/记忆提取/意图识别/回复判断/图片分析），分配模型 |
| 多智能体 | 多角色人格，可绑定到不同群/用户 |
| 知识库 | 知识文档注入对话上下文，支持分类、标签、自动搜索 |
| MCP 工具 | 函数调用工具定义，让 AI 调用外部 API |
| 窥屏模式 | 群聊默认默默观察，被@或活跃模式时积极响应 |
| 预测模式 | 低 token 模式：每 N 条消息做预测词判断，匹配才进入对话 |
| 记忆系统 | 自动提取长期记忆，支持群聊混合/仅发送者两种记忆模式 |
| Dashboard | 全功能 Web 管理面板，模型/行为/智能体/知识库/工具一站式管理 |

## 快速开始

### Docker（推荐）

```bash
docker run -d --name qvqchat -p 8000:8000 --restart unless-stopped ghcr.io/wsu2059q/erispulse-qvqchat:latest
```

启动后打开 `http://localhost:8000/Dashboard` 即可开始配置。

### 手动

```bash
pip install erispulse
ep install OneBot11, QvQChat
ep run
```

启动后打开 Dashboard，一切配置（适配器、AI 模型、行为等）均在 Web 面板中完成。

## 文档

- [安装指南](INSTALL.md)
- [架构文档](ARCHITECTURE.md)

## 许可证

MIT
