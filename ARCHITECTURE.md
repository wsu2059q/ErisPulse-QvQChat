# QvQChat 架构文档

## 包结构

```
QvQChat/
├── Core.py                  # 主编排器（消息处理+预测模式+记忆提取）
├── config.py                # 基础配置（无AI配置段）
├── utils.py                 # MessageSender + 工具函数
│
├── ai/                      # AI 引擎子系统
│   ├── engine.py            # AIEngine: 行为执行引擎（故障转移）
│   ├── client.py            # AIClient: 单模型客户端
│   ├── model_pool.py        # ModelPool: 模型池（chat/vision/tools能力）
│   └── behavior.py          # BehaviorManager: 行为中枢（提示词+模型分配+触发模式）
│
├── chat/                    # 对话处理子系统
│   ├── memory.py            # QvQMemory: 长期/短期记忆
│   └── session.py           # SessionManager: 会话+速率限制+活跃模式+回复判断+预测缓冲
│
├── agent/                   # 智能体管理子系统
│   ├── multi.py             # MultiAgentManager: 多智能体人格
│   ├── knowledge.py         # KnowledgeBase: 知识文档注入
│   └── tools.py             # MCPManager: 函数调用工具
│
└── dashboard/               # Dashboard 管理子系统
    ├── manager.py           # DashboardManager: 路由注册+视窗注册+21个API处理器
    ├── icons.py             # SVG图标常量
    ├── styles.py            # CSS样式
    ├── html.py              # 页面HTML（8个tab）
    └── scripts.py           # JavaScript（全部CRUD逻辑）
```

## 核心设计：模型池 + 行为绑定

```
┌─────────────────────────────────────────────┐
│                  Dashboard                    │
│  添加模型 ──→ ModelPool ──→ 模型列表           │
│  配置行为 ──→ BehaviorManager ──→ 行为列表      │
│  分配模型：行为.模型 ←── ModelPool.模型          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│               AIEngine                       │
│  execute_behavior("dialogue", messages)       │
│    ├─ 查行为 "dialogue" 的提示词+参数          │
│    ├─ 查行为分配的模型列表 [model_A, model_B]   │
│    ├─ 用 model_A 调用 OpenAI API              │
│    ├─ 失败 → 切换 model_B（故障转移）           │
│    └─ 返回 AI 回复                             │
└─────────────────────────────────────────────┘
```

**模型** 有3种能力标记：
- `chat` — 文本对话
- `vision` — 图片识别
- `tools` — 函数调用

**行为** 内置5种 + 可自定义：
- `dialogue` — 对话（能力: chat）
- `reply_judge` — 回复判断（能力: chat）
- `memory` — 记忆提取（能力: chat）
- `intent` — 意图识别（能力: chat）
- `vision` — 图片分析（能力: vision）

## 消息处理流程

```
消息到达
  │
  ├─ 跳过指令消息（/开头）
  ├─ 消息长度检查
  ├─ AI 启用检查
  ├─ 累积到短期记忆
  │
  ├─ _check_should_reply()
  │     ├─ 私聊 → 始终回复
  │     ├─ 被@ → 直接回复
  │     ├─ 活跃模式 → 直接回复
  │     ├─ 预测模式（低token）→ 累积N条→AI预测词→匹配触发词？
  │     └─ 标准模式 → 窥屏概率+AI判断
  │
  ├─ [回复] _generate_response()
  │     ├─ 构建系统提示词（行为[dialogue]+多智能体+知识库）
  │     ├─ 构建记忆上下文
  │     ├─ 图片处理（视觉分析 或 多模态）
  │     ├─ MCP 工具注入
  │     └─ AIEngine.dialogue() → AI 回复
  │
  ├─ 发送回复
  ├─ 保存回复到记忆
  └─ 异步提取记忆（并发锁+30s超时）
```

## 预测模式（低 token 模式）

```
群聊消息1 → 缓冲[1/5]
群聊消息2 → 缓冲[2/5]
群聊消息3 → 缓冲[3/5]
群聊消息4 → 缓冲[4/5]
群聊消息5 → 缓冲[5/5] → 触发预测
  │
  ├─ 批量消息 → AIEngine → reply_judge 行为
  ├─ AI 返回: "回复" → 进入对话流程
  └─ AI 返回: "跳过" → 不回复，清空缓冲
```

行为可配置：
- `trigger_mode: "prediction"` — 启用预测模式
- `prediction_interval: 5` — 每5条消息触发一次
- `trigger_words: ["回复","参与"]` — 命中才进入对话

## 记忆系统

```
对话历史（短期） ──→ 记忆提取行为 ──→ 长期记忆
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              用户长期记忆    群组发送者记忆   群共享上下文
```

- 仅在机器人回复后异步提取（不在观察时提取）
- 并发锁防止同一会话重复提取
- 30秒超时保护
- 群聊支持 mixed/sender_only 两种记忆模式

## Dashboard API

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 系统概览 |
| `/api/config` | GET/POST | 基础配置 |
| `/api/models` | GET/POST | 模型 CRUD |
| `/api/models/delete` | POST | 删除模型 |
| `/api/behaviors` | GET/POST | 行为 CRUD |
| `/api/behaviors/delete` | POST | 删除行为 |
| `/api/test-model` | POST | 测试模型连接 |
| `/api/agents` | GET/POST | 智能体 CRUD |
| `/api/agents/delete` | POST | 删除智能体 |
| `/api/knowledge` | GET/POST | 知识库 CRUD |
| `/api/knowledge/delete` | POST | 删除知识 |
| `/api/tools` | GET/POST | MCP 工具 CRUD |
| `/api/tools/delete` | POST | 删除工具 |
| `/api/groups` | GET/POST | 群组管理 |
