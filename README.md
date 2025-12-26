# QvQChat 模块文档

## 简介
QvQChat 是一个智能对话模块，支持多AI协同、个性化记忆管理、视觉识别和上下文理解。

## 核心特性：普通群友模式 ⭐

QvQChat 默认采用**普通群友模式**，像真人一样自然参与聊天：

### 🎯 AI智能决策
- **是否回复**：AI根据对话上下文判断，不会每条消息都回复
- **是否记忆**：AI自动判断什么值得记住，无需用户手动指定
- **是否看图**：AI判断是否需要使用视觉AI，而不是有图就看

### 🤖 真人感
- 回复自然随意，不机械化
- 适当参与，不刷屏
- 理解对话节奏和氛围

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
command_prefix = "/qvc"  # 命令前缀，可自定义（如 /ai）
bot_nicknames = ["你的机器人名字"]  # 配置机器人昵称

[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-4o"  # 建议使用支持视觉的模型
```

### 自定义命令前缀
默认命令前缀为 `/qvc`，你可以通过配置自定义为任意前缀：
```toml
[QvQChat]
command_prefix = "/ai"  # 改为 /ai
```
这样所有命令就会变成 `/ai clear`, `/ai help` 等等。

### 完整配置（推荐）
```toml
[QvQChat]
command_prefix = "/qvc"  # 命令前缀
min_reply_interval = 10  # 最小回复间隔（秒），避免频繁回复
max_history_length = 20

# 机器人识别配置（用于AI判断）
bot_nicknames = ["AI助手", "小B"]  # 机器人昵称列表
bot_ids = ["123456789"]  # 机器人ID列表，用于@判断

[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-4o"  # 建议使用支持视觉的模型
temperature = 0.7
max_tokens = 500
system_prompt = "你是一个智能AI助手。回复要求：1. 简短精炼，通常1-2句话，不超过100字；2. 不要使用Markdown格式；3. 自然口语化，直接回答；4. 如果有图片，根据图片内容自然回复"

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
- dialogue AI不支持视觉: 无法理解图片内容
- 未配置回复判断AI: 使用简单的规则判断（可能不够智能）
- 未配置意图识别AI: 使用规则匹配识别意图（可能不够精确）
- 未配置记忆AI: 无法使用记忆压缩功能

**解决方法**: 为对应AI配置API密钥，建议至少配置 dialogue 和 reply_judge。dialogue AI应使用支持视觉的模型（如gpt-4o）

### 问题4：发送响应失败
**原因**: 消息发送到平台失败

**检查方法**:
1. 查看日志中具体的错误信息
2. 确认适配器配置正确
3. 检查网络连接

## 功能说明

### 0. AI智能决策（普通群友模式）⭐

QvQChat 完全由AI进行所有决策，更像真正的群友：

#### 📊 两大决策
1. **是否回复** - AI根据对话上下文判断
2. **是否记忆** - AI自动判断什么值得记住

#### 🖼️ 图片处理
- **直接理解**：如果dialogue AI支持视觉功能（如gpt-4o），图片会直接传给AI理解
- **自动回退**：如果模型不支持视觉，会自动跳过图片，只处理文字
- **无需配置**：不需要单独的视觉AI，dialogue AI即可处理图片

#### 🔍 AI回复判断标准

**会回复的情况**：
- ✅ 用户在向你提问（直接或间接）
- ✅ 用户提到你的名字，需要回应
- ✅ 对话正在讨论你感兴趣或了解的话题
- ✅ 适当的幽默回应可以活跃气氛
- ✅ 之前提到的事情有更新或结论

**不会回复的情况**：
- ❌ 普通打招呼（"在吗"、"大家好"）
- ❌ 表情符号、纯表情回复
- ❌ 简单的"好的"、"嗯"、"收到"
- ❌ 与你无关的话题讨论
- ❌ 连续短时间内多次回复（显得不自然）

#### 📝 AI记忆判断标准

**会记住的情况**：
- ✅ 对方的个人信息：生日、重要日期、工作、学校
- ✅ 对方的喜好：爱吃的、不爱吃的、兴趣爱好
- ✅ 对方的习惯：作息时间、运动习惯、特殊习惯
- ✅ 对方的重要关系：家人、伴侣、好朋友
- ✅ 对方最近的状态：生病、忙碌、考试、搬家
- ✅ 对方的目标和计划：要考试、要旅行、要找工作

**不会记住的情况**：
- ❌ 日常闲聊："在吗"、"大家好"、"哈哈哈"
- ❌ 简单回应："好的"、"嗯"、"收到"、"知道了"
- ❌ 表情包、纯表情消息
- ❌ 一次性话题："今天天气不错"、"这菜不错"
- ❌ 纯粹吐槽、发泄（无具体信息）
- ❌ 对你的评价（除非重要）
- ❌ 已经说过很多次的事情

**配置示例**：
```toml
[QvQChat]
command_prefix = "/qvc"
min_reply_interval = 10  # 最小回复间隔（秒）
bot_nicknames = ["AI助手"]  # 用于AI判断
bot_ids = ["123456789"]  # 用于@判断
```

### 1. 多AI协同
- **对话AI (dialogue)**: 负责与用户直接交流，支持图片理解（必需，建议使用gpt-4o）
- **回复判断AI (reply_judge)**: 智能判断是否需要回复（推荐）
- **记忆AI (memory)**: 负责整理和修剪记忆（可选）
- **查询AI (query)**: 负责检索相关记忆（推荐）
- **意图识别AI (intent)**: 识别用户意图（可选）

**说明**：reply_judge 未配置时会自动复用 dialogue 的配置。dialogue AI应使用支持视觉的模型（如gpt-4o）才能理解图片。

### 2. 智能记忆管理（核心特性）

QvQChat 采用**多AI协同的智能记忆机制**，无需用户手动告诉AI，自动识别和保存重要信息。

#### 工作原理
```
用户发送消息
    ↓
[dialogue AI] 对话回复
    ↓
[多AI协同] 判断是否值得记忆
    ├─ 使用 dialogue AI 分析对话价值
    └─ 评估是否影响后续对话
    ↓
[memory AI] 提取关键信息
    ├─ 严格提取标准（个人偏好、重要日期、任务等）
    ├─ 过滤无关信息（闲聊、问候、表情等）
    └─ 去重检查（避免重复记忆）
    ↓
保存到长期记忆
```

#### 记忆标准
✅ **会自动记忆的信息**：
- 用户的个人偏好、喜好、习惯
- 重要日期（生日、纪念日、截止日期等）
- 用户正在进行的任务、计划、目标
- 重要人际关系、家庭信息
- 影响后续对话的关键信息

❌ **不会记忆的信息**：
- 日常闲聊、打招呼、"好的"、"嗯"
- 表情符号、纯表情消息
- 临时性话题讨论
- AI已经回答过的问题
- 一次性话题
- 天气、时间等通用信息

#### 多AI协同机制
1. **dialogue AI** - 分析对话上下文，判断是否值得记忆
2. **memory AI** - 提取关键信息，严格遵守记忆标准
3. **去重机制** - 自动检测重复信息，避免冗余记忆

#### 配置建议
```toml
[QvQChat.memory]
# 必须配置才能使用智能记忆
api_key = "sk-your-api-key"
model = "gpt-3.5-turbo"  # 建议使用较便宜的模型
temperature = 0.3  # 较低温度保证一致性
```

#### 记忆查询与使用
- 记忆会自动注入到对话上下文中
- AI会根据记忆提供更个性化的回复
- 可以通过命令查询和管理记忆：
  - `/qvc memory search <关键词>` - 搜索记忆
  - `/qvc memory list` - 查看记忆摘要
  - `/qvc memory delete <索引>` - 删除记忆

#### 记忆隐私
- 用户级记忆：每个用户独立的记忆空间
- 群聊级记忆：每个群独立的记忆
- 使用 `sdk.storage` 存储，数据持久化

### 2.1 分层记忆
- **短期记忆**：当前会话的最近消息（最多20条）
- **长期记忆**：经过AI智能提取和整理的重要信息

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

### 5. 图片理解
- **直接传递**：如果dialogue AI支持视觉功能（如gpt-4o），图片会直接传给AI理解
- **自动回退**：如果模型不支持视觉，会自动跳过图片，只处理文字
- **无需额外配置**：不需要单独的视觉AI，dialogue AI即可处理图片

**配置提示**：
- dialogue AI应使用支持视觉的模型（如gpt-4o）
- 如果图片理解失败，会自动回退到纯文字模式
```

## 命令列表

> **提示**: 默认命令前缀为 `/qvc`，可通过配置 `[QvQChat.command_prefix]` 自定义（如改为 `/ai`）

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

### 意图识别命令
除了使用命令，也可以直接对话，AI会自动识别意图：
- "删除第1条记忆" - 删除指定记忆
- "我昨天说过什么" - 查询历史记忆
- "记住这件事" - 添加新记忆
- "切换模型" - 切换AI模型

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
