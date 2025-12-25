# QvQChat 智能回复策略

## 说明

QvQChat 现在采用智能回复策略，不会每条消息都回复，而是主动积累记忆，根据条件智能判断是否回复。

## 工作原理

### 默认行为
- ✅ 所有消息都会被记录到短期记忆和长期记忆
- ✅ 积累足够的上下文后再回复
- ✅ 回复更加连贯，不会前言不搭后语
- ✅ 不会频繁刷屏，干扰聊天

### 回复触发条件（按优先级）

1. **命令优先** - 所有以 `/` 开头的命令总是回复
2. **被@触发** - 当机器人被@提及时回复
3. **关键词触发** - 消息包含配置的关键词时回复
4. **概率回复** - 按配置的概率随机回复（默认10%）
5. **消息阈值** - 累积N条消息后回复（默认5条）
6. **时间间隔** - 距离上次回复超过N秒后可能回复（默认30秒）

## 配置示例

### 默认配置（推荐）
```toml
[QvQChat.reply_strategy]
auto_reply = false
reply_on_mention = true
reply_on_keyword = []
reply_probability = 0.1
message_threshold = 5
min_reply_interval = 30
ignore_commands = true
```

### 活跃模式（回复更多）
```toml
[QvQChat.reply_strategy]
auto_reply = false
reply_on_mention = true
reply_on_keyword = ["小B", "机器人", "AI"]
reply_probability = 0.3
message_threshold = 3
min_reply_interval = 15
```

### 保守模式（回复更少）
```toml
[QvQChat.reply_strategy]
auto_reply = false
reply_on_mention = true
reply_on_keyword = []
reply_probability = 0.05
message_threshold = 8
min_reply_interval = 60
```

### 仅响应模式（不主动回复）
```toml
[QvQChat.reply_strategy]
auto_reply = false
reply_on_mention = true
reply_on_keyword = []
reply_probability = 0.0
message_threshold = 999
```

## 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|---------|------|----------|------|
| auto_reply | bool | false | 是否自动回复（建议false，让其他策略控制）|
| reply_on_mention | bool | true | 被@时是否回复 |
| reply_on_keyword | list | [] | 关键词触发列表 |
| reply_probability | float | 0.1 | 概率回复（0-1，0.1=10%） |
| message_threshold | int | 5 | 累积多少条消息后回复 |
| min_reply_interval | int | 30 | 最小回复间隔（秒） |
| ignore_commands | bool | true | 是否忽略命令判断（命令总是回复） |

## 如何让机器人回复更多

1. 降低 `message_threshold`（如改为3）
2. 增加 `reply_probability`（如改为0.3）
3. 减小 `min_reply_interval`（如改为15）
4. 添加 `reply_on_keyword` 列表

## 如何让机器人更安静

1. 增加 `message_threshold`（如改为10）
2. 减小 `reply_probability`（如改为0.05）
3. 增大 `min_reply_interval`（如改为60）
4. 确保 `auto_reply = false`

## 记忆机制

- 所有消息都会被积累到短期记忆（无论是否回复）
- 短期记忆定期压缩到长期记忆
- 长期记忆会用于上下文注入
- 历史对话会保留用于多轮交流

这样即使机器人不回复，也在持续学习和积累上下文。
