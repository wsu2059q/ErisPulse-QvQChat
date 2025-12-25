# QvQChat 模块文档

## 简介
QvQChat 是一个智能对话模块，支持多AI协同、个性化记忆管理、视觉识别和上下文理解。

## 安装

```bash
ep install AIChat
```

## 快速配置

### 第一步：获取API密钥
访问 [OpenAI API Keys](https://platform.openai.com/api-keys) 创建API密钥。

### 第二步：配置文件
首次加载模块后，会在项目目录生成 `config.toml` 文件。或者参考 `config.example.toml` 创建配置文件。

### 最小配置（必需）
```toml
[QvQChat]
bot_nicknames = ["你的机器人名字"]  # 配置机器人昵称

[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-4"
```

### 完整配置（推荐）
```toml
[QvQChat]
clear_command = "/qvc clear"
max_history_length = 20

# 机器人识别配置
bot_nicknames = ["AI助手", "小B"]  # 机器人昵称列表，用于文本匹配
bot_ids = ["123456789"]  # 机器人ID列表，用于@匹配

[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-4"
temperature = 0.7
max_tokens = 500
system_prompt = "你是一个智能AI助手。回复要求：1. 简短精炼，通常1-2句话，不超过100字；2. 不要使用Markdown格式；3. 自然口语化，直接回答"

[QvQChat.vision]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-4-vision-preview"
temperature = 0.3
max_tokens = 300
system_prompt = "你是一个视觉描述助手。用简洁的语言描述图片内容，不超过50字。"

[QvQChat.reply_judge]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-3.5-turbo"
temperature = 0.1
max_tokens = 100
system_prompt = "你是一个对话分析助手。判断用户的最新消息是否需要AI回复。只回复true或false。"

[QvQChat.memory]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-3.5-turbo"
temperature = 0.3
max_tokens = 1000

[QvQChat.query]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-3.5-turbo"
temperature = 0.3
max_tokens = 1000

[QvQChat.intent]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-3.5-turbo"
temperature = 0.1
max_tokens = 500
```

## 故障排除

### 问题1：API错误 401 - Invalid token
**原因**: API密钥未配置或配置错误

**解决方法**:
1. 检查 `config.toml` 中 `[QvQChat.dialogue.api_key]` 是否已填入正确的API密钥
2. 确保API密钥格式为 `sk-...` 开头
3. 验证API密钥是否有效（访问 OpenAI 控制台检查）

### 问题2：所有AI均未配置API密钥
**原因**: 首次运行，未进行配置

**解决方法**:
1. 复制 `config.example.toml` 为 `config.toml`
2. 将其中的 `sk-your-api-key-here` 替换为实际API密钥
3. 配置 `bot_nicknames` 和 `bot_ids`
4. 重启程序

### 问题3：部分AI功能不可用
**原因**: 只配置了对话AI，其他AI未配置

**影响**:
- 仅对话AI配置: 基本对话功能正常，记忆查询会返回原始结果
- 未配置视觉AI: 无法识别和描述图片
- 未配置回复判断AI: 使用简单的规则判断（可能不够智能）
- 未配置意图识别AI: 使用规则匹配识别意图（可能不够精确）
- 未配置记忆AI: 无法使用记忆压缩功能

**解决方法**: 为对应AI配置API密钥，建议至少配置 dialogue、vision 和 reply_judge 三个AI

### 问题4：发送响应失败
**原因**: 消息发送到平台失败

**检查方法**:
1. 查看日志中具体的错误信息
2. 确认适配器配置正确
3. 检查网络连接

## 功能说明

### 0. 智能回复策略（核心特性）
QvQChat 采用**AI智能回复策略**，不会每条消息都回复，而是：

- **主动积累记忆**：所有消息都会被记录到短期和长期记忆
- **AI判断回复时机**：使用专门的AI分析对话上下文，智能判断是否需要回复
- **理解对话流程**：不是简单的消息计数，而是真正理解对话节奏
- **提升对话质量**：通过积累上下文，让回复更连贯自然

**AI判断标准**：
1. ✅ 明确的问题、请求、指令 → 需要回复
2. ✅ 被@机器人或叫机器人名字 → 需要回复
3. ✅ 对话中断后重新开始 → 需要回复
4. ✅ 情绪强烈的表达 → 需要回复
5. ❌ 纯表情或简单的打招呼 → 可以不回复
6. ❌ 对话中的简短回应（"嗯"、"好"） → 可以不回复
7. ❌ 只是消息分享，无互动意图 → 可以不回复

**配置示例**：
```toml
[QvQChat]
bot_nicknames = ["AI助手"]  # 用于昵称匹配
bot_ids = ["123456789"]  # 用于@匹配

[QvQChat.reply_strategy]
auto_reply = false  # AI智能判断
reply_on_mention = true  # 被@时回复
reply_on_keyword = ["小B", "机器人"]  # 关键词触发
message_threshold = 5  # 备用阈值
min_reply_interval = 5  # 最小间隔5秒
```

### 1. 多AI协同
- **对话AI (dialogue)**: 负责与用户直接交流（必需）
- **视觉AI (vision)**: 负责识别和描述图片（推荐）
- **回复判断AI (reply_judge)**: 智能判断是否需要回复（推荐）
- **记忆AI (memory)**: 负责整理和修剪记忆（可选）
- **查询AI (query)**: 负责检索相关记忆（推荐）
- **意图识别AI (intent)**: 识别用户意图（可选）

**说明**：vision 和 reply_judge 未配置时会自动复用 dialogue 的配置。

### 2. 记忆管理
- **分层记忆**:
  - 短期记忆：当前会话的最近消息（最多20条）
  - 长期记忆：经过整理的重要信息
- **记忆存储**:
  - 使用 `sdk.storage` 存储（而非config模块）
  - 用户配置: `QvQChat.users.{user_id}`
  - 群配置: `QvQChat.groups.{group_id}`
  - 记忆数据: `user:{user_id}:memory` 等
- **记忆隐私**:
  - 用户级记忆：独立的用户记忆空间
  - 群聊级记忆：每个群独立的记忆

### 3. 意图识别
- 对话: 普通交流
- 记忆查询: 查询历史信息
- 记忆管理: 添加/删除/修改记忆
- 系统控制: 切换模型、配置等
- 群配置: 群级设置

### 4. 群聊自定义
- 每个群可独立配置提示词、模型参数
- 群专属记忆空间
- 群角色设定

### 5. 视觉识别（新增）
- 自动识别消息中的图片
- 使用视觉AI描述图片内容
- 图片描述会作为上下文辅助对话
- 支持多种图片格式

## 命令列表

### 基础命令
- `/qvc clear` - 清除当前会话历史
- `/qvc help` - 显示帮助信息

### 记忆管理
- `/qvc memory list` - 查看记忆摘要
- `/qvc memory search <关键词>` - 搜索记忆
- `/qvc memory compress` - 压缩整理记忆
- `/qvc memory delete <索引>` - 删除指定记忆

### 系统控制
- `/qvc config` - 查看当前配置
- `/qvc model <类型>` - 切换AI模型（dialogue/memory/query）
- `/qvc export` - 导出记忆

### 群聊配置（仅在群聊中可用）
- `/qvc group info` - 查看群配置
- `/qvc group prompt <内容>` - 设置群提示词
- `/qvc group style <风格>` - 设置对话风格

### 个性化
- `/qvc prompt <内容>` - 自定义个人提示词
- `/qvc style <风格>` - 设置对话风格（友好/专业/幽默等）

## 使用示例

```bash
# 查询历史记忆
/qvc memory search 我昨天说过什么

# 设置群提示词
/qvc group prompt 你是一个专业的技术顾问

# 设置对话风格
/qvc style 幽默

# 切换对话模型
/qvc model dialogue

# 压缩记忆
/qvc memory compress
```

## 机器人识别配置

### bot_nicknames（昵称列表）
用于文本匹配，当消息中包含这些昵称时会被触发：
```toml
bot_nicknames = ["AI助手", "小B", "机器人"]
```

### bot_ids（ID列表）
用于@匹配，当机器人被@时直接回复：
```toml
bot_ids = ["123456789", "987654321"]
```

**说明**：不同平台的@机制可能不同，有些平台使用ID，有些使用昵称。

## 依赖
本模块依赖 OpenAI API，需要配置相应的 API 密钥。

## 参考链接
- https://github.com/ErisPulse/ErisPulse/
