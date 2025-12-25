# QvQChat 智能回复策略

## 说明

QvQChat 采用**AI智能回复策略**，不会每条消息都回复，而是主动积累记忆，利用专门的AI分析对话上下文，智能判断是否需要回复。

## 工作原理

### 核心特性
- ✅ 所有消息都会被记录到短期记忆和长期记忆（无论是否回复）
- ✅ 使用AI分析对话历史，理解对话流程
- ✅ 智能判断回复时机，不是简单的规则匹配
- ✅ 回复更加连贯自然，不会前言不搭后语
- ✅ 不会频繁刷屏，干扰正常聊天

### AI智能判断标准

回复判断AI会分析最近的对话历史（5条消息），根据以下标准判断：

1. ✅ **明确的问题、请求、指令** → 需要回复
2. ✅ **被@机器人或叫机器人名字** → 需要回复
3. ✅ **对话中断后重新开始** → 需要回复
4. ✅ **情绪强烈的表达** → 需要回复
5. ❌ **纯表情或简单的打招呼** → 可以不回复
6. ❌ **对话中的简短回应**（"嗯"、"好"、"收到"） → 可以不回复
7. ❌ **只是消息分享，无互动意图** → 可以不回复

### 回复触发条件（按优先级）

1. **命令优先** - 所有以 `/` 开头的命令总是回复
2. **@机器人** - 当机器人被@提及时回复（配置bot_ids）
3. **昵称触发** - 消息包含配置的昵称时回复（配置bot_nicknames）
4. **关键词触发** - 消息包含配置的关键词时回复
5. **AI智能判断** - 使用reply_judge AI分析对话后判断（核心机制）
6. **回复间隔保护** - 距离上次回复超过最小间隔后才可能回复（默认5秒）

## 配置示例

### 默认配置（推荐）
```toml
[QvQChat]
# 机器人识别配置
bot_nicknames = ["AI助手", "小B"]  # 昵称列表
bot_ids = ["123456789"]  # ID列表

[QvQChat.reply_strategy]
auto_reply = false  # AI智能判断
reply_on_mention = true
reply_on_keyword = []
message_threshold = 5
min_reply_interval = 5
ignore_commands = true
```

### 活跃模式（回复更多）
```toml
[QvQChat.reply_strategy]
auto_reply = false
reply_on_mention = true
reply_on_keyword = ["小B", "机器人", "AI"]
message_threshold = 3
min_reply_interval = 3
```

### 保守模式（回复更少）
```toml
[QvQChat.reply_strategy]
auto_reply = false
reply_on_mention = true
reply_on_keyword = []
message_threshold = 10
min_reply_interval = 10
```

### 仅响应模式（不主动回复）
```toml
[QvQChat.reply_strategy]
auto_reply = false
reply_on_mention = true
reply_on_keyword = []
message_threshold = 999
```

## 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|---------|------|----------|------|
| bot_nicknames | list | [] | 机器人昵称列表，用于文本匹配 |
| bot_ids | list | [] | 机器人ID列表，用于@匹配 |
| auto_reply | bool | false | 是否自动回复（建议false，让AI判断）|
| reply_on_mention | bool | true | 被@时是否回复 |
| reply_on_keyword | list | [] | 关键词触发列表 |
| message_threshold | int | 5 | 备用阈值（AI未配置时使用） |
| min_reply_interval | int | 5 | 最小回复间隔（秒） |
| ignore_commands | bool | true | 是否忽略命令判断（命令总是回复） |

## AI智能判断 vs 传统策略

### 传统策略（已废弃）
- ❌ 简单计数：累积N条消息后回复
- ❌ 固定概率：按配置的概率随机回复
- ❌ 不理解对话：无法区分是否需要互动

### AI智能判断（新策略）
- ✅ 上下文理解：分析对话历史，理解对话流程
- ✅ 语义分析：根据消息内容判断是否需要回复
- ✅ 自然流畅：像真人一样判断何时插话、何时倾听
- ✅ 智能决策：避免尴尬的回复时机

## 如何让机器人回复更多

1. 添加 `bot_nicknames` 和 `bot_ids` 配置（确保能被识别）
2. 添加 `reply_on_keyword` 列表
3. 减小 `min_reply_interval`（如改为3秒）
4. 如果回复判断AI不可用，降低 `message_threshold`

## 如何让机器人更安静

1. 增加 `min_reply_interval`（如改为10秒）
2. 确保 `auto_reply = false`
3. 清空 `reply_on_keyword` 列表
4. 如果回复判断AI可用，它会自动保持安静

## 记忆机制

- 所有消息都会被积累到短期记忆（无论是否回复）
- 短期记忆定期压缩到长期记忆
- 长期记忆会用于上下文注入
- 历史对话会保留用于多轮交流

这样即使机器人不回复，也在持续学习和积累上下文。

## 回复判断AI配置

reply_judge AI 是智能判断的核心，建议单独配置：

```toml
[QvQChat.reply_judge]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-api-key"
model = "gpt-3.5-turbo"
temperature = 0.1
max_tokens = 100
```

**说明**：
- 如果未配置 `reply_judge`，会自动复用 `dialogue` 的配置
- `temperature=0.1` 保证判断的一致性
- `max_tokens=100` 足够输出 true/false

## 常见问题

### Q: 为什么机器人不回复我的消息？
A: AI判断当前不需要回复。可以：
1. 直接@机器人或叫机器人昵称
2. 发送明确的问题或请求
3. 添加关键词触发

### Q: AI判断准确吗？
A: AI会分析最近5条对话，准确率较高。可以通过调整回复判断AI的提示词来优化。

### Q: 和传统策略有什么区别？
A: 传统策略是固定规则（计数、概率），新策略是AI分析上下文，更智能、更自然。

### Q: 可以回退到传统策略吗？
A: 可以。将 `reply_judge` 的 `api_key` 设为空，系统会使用传统策略。
