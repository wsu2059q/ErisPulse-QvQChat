# QvQChat
> 暂时存档，v2稳定后正式发布

基于行为系统的多模型 AI 智能对话模块，支持 Dashboard 全功能管理。

## 核心理念

**模型池 + 行为绑定**：用户添加 AI 模型（带能力标记），配置行为（对话/记忆/意图/自定义），为行为分配模型（多模型冗余备用）。所有配置通过 Dashboard Web 管理面板完成，弱化 config.toml 配置。

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

### Docker

```bash
git clone https://github.com/wsu2059q/ErisPulse-QvQChat.git
cd ErisPulse-QvQChat
cp config.example.toml config.toml
docker-compose pull
docker-compose up -d
```

### 手动

```bash
pip install erispulse
epsdk install OneBot11
pip install ErisPulse-QvQChat
```

启动后打开 `http://localhost:8000/Dashboard`，在 QvQChat 管理面板中配置 AI 模型和行为。

## 配置方式

**优先使用 Dashboard**：所有 AI 模型、行为、智能体、知识库、工具通过 Web 面板管理，数据持久化存储。

`config.toml` 仅保留基础设置：机器人识别、窥屏模式参数、速率限制等。AI 模型配置（API Key、模型名、提示词等）完全通过 Dashboard 管理。

## 项目结构

```
QvQChat/
├── Core.py                  # 主编排器
├── config.py                # 基础配置
├── utils.py                 # 工具函数
├── ai/                      # AI 引擎
│   ├── engine.py            # 行为执行（故障转移）
│   ├── client.py            # 模型客户端
│   ├── model_pool.py        # 模型池
│   └── behavior.py          # 行为管理
├── chat/                    # 对话处理
│   ├── memory.py            # 记忆系统
│   └── session.py           # 会话+速率+回复判断
├── agent/                   # 智能体
│   ├── multi.py             # 多智能体
│   ├── knowledge.py         # 知识库
│   └── tools.py             # MCP
└── dashboard/               # 管理面板
    ├── manager.py           # 路由+视窗
    ├── icons.py/styles.py   # 资源
    ├── html.py              # 页面
    └── scripts.py           # 逻辑
```

## 依赖

- Python >= 3.10
- ErisPulse SDK
- openai >= 1.0.0

## 文档

- [安装指南](INSTALL.md)
- [架构文档](ARCHITECTURE.md)

## 许可证

MIT
