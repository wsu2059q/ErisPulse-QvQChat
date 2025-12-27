# QvQChat 智能对话模块

## 简介

QvQChat 是一个基于多AI协同的智能对话模块，采用"普通群友模式"，让AI像真人一样自然参与聊天。

### 核心特性 ⭐

- **AI自主决策**：无需命令格式，直接用自然语言交互
- **记忆自然融合**：询问"你记得我的生日吗"，AI根据记忆自然回答
- **配置简化**：只需配置dialogue的API密钥，其他AI自动复用
- **窥屏模式**：群聊默默观察，适时回复（默认3%回复率）
- **多模态支持**：支持图片理解（需要gpt-4o等视觉模型）

### 与传统AI助手的区别

| 特性 | 传统AI助手 | QvQChat |
|------|-------------|----------|
| 回复方式 | 积极回复每条消息 | AI智能判断，适当回复 |
| 记忆方式 | 用户显式查询 | 记忆自然融入对话 |
| 对话风格 | 正式、格式化 | 随意、无格式 |
| 群聊行为 | 积极参与 | 窥屏模式，更像真人 |

## 快速开始

### 第一步：获取API密钥

访问 [OpenAI API Keys](https://platform.openai.com/api-keys) 创建API密钥。

### 第二步：配置文件

首次运行后会自动生成 `config.toml`，或者参考 `config.example.toml` 创建配置。

**最小配置（必需）**：
```toml
[QvQChat]
bot_nicknames = ["你的机器人名字"]
bot_ids = ["你的机器人ID"]

[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-4o"  # 建议使用支持视觉的模型
```

### 第三步：安装

```bash
ep install QvQChat
```

### 第四步：配置机器人识别

编辑 `config.toml`：
```toml
[QvQChat]
bot_nicknames = ["AI助手", "小B"]  # 文本匹配
bot_ids = ["123456789"]  # @匹配
```

## 功能说明

### 1. AI智能决策（普通群友模式）⭐

QvQChat 完全由AI进行所有决策，更像真正的群友：

#### 📊 两大决策
1. **是否回复** - AI根据对话上下文判断
2. **是否记忆** - AI自动判断什么值得记住

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

### 2. 多AI协同

| AI类型 | 用途 | 必需 | 默认复用dialogue |
|--------|--------|--------|-----------------|
| dialogue | 对话AI | ✅ | - |
| intent | 意图识别 | ✅ | ✅ |
| intent_execution | 意图执行（系统操作） | ✅ | ✅ |
| memory | 记忆提取 | ❌ | ✅ |
| reply_judge | 回复判断（私聊） | ❌ | ✅ |
| vision | 图片分析 | ❌ | ✅ |

**说明**：未配置API密钥的AI会自动复用dialogue的配置。

### 3. 智能记忆管理

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

#### 记忆使用

**自然融入对话**（推荐）：
```
用户：你记得我的生日吗？
AI：是的，我记得你的生日是6月15日。
```

**用户主动要求记忆**：
```
用户：记住这件事，我下周五生日
AI：好的，我会记住你下周五生日。✅
```

**删除记忆**：
```
用户：忘记这件事
AI：我会帮你删除相关记忆。
```

#### 记忆存储

- **私聊**：只存用户个人记忆
- **群聊**：用户个人记忆 + 群记忆（混合模式）
- **群记忆模式**：
  - `mixed`：保存发送者记忆 + 群公共上下文（默认）
  - `sender_only`：只保存发送者的个人记忆

### 4. 意图执行（自然语言操作）

无需命令格式，直接用自然语言描述操作：

| 操作 | 示例 |
|------|--------|
| 添加记忆 | "记住这件事" |
| 删除记忆 | "忘记这件事"、"删掉这条记忆" |
| 修改群提示词 | "把群提示词改成XX" |
| 修改群记忆模式 | "群记忆模式改成混合模式" |
| 清除会话 | "清除会话"、"清空对话历史" |
| 导出记忆 | "导出我的记忆" |

### 5. 图片理解

- **直接传递**：dialogue AI支持视觉功能（如gpt-4o）时，图片直接传给AI
- **自动回退**：模型不支持视觉时，自动跳过图片，只处理文字
- **视觉AI备用**：如果配置了vision AI，先用vision分析再传给dialogue

### 6. 窥屏模式（群聊）

群聊默认启用窥屏模式，更像真人参与：

| 参数 | 默认值 | 说明 |
|------|----------|------|
| enabled | true | 启用窥屏模式 |
| default_probability | 0.03 | 默认回复概率（3%） |
| mention_probability | 0.8 | 被@时回复概率（80%） |
| keyword_probability | 0.5 | 匹配关键词时回复概率（50%） |
| question_probability | 0.4 | 提问时回复概率（40%） |
| min_messages_between_replies | 15 | 两次回复之间至少间隔多少条消息 |
| max_replies_per_hour | 8 | 每小时最多回复次数 |

## 配置说明

### 完整配置

```toml
[QvQChat]
# 基础配置
max_history_length = 20
min_reply_interval = 10
bot_nicknames = ["AI助手"]
bot_ids = ["123456789"]

# 窥屏模式配置
[QvQChat.stalker_mode]
enabled = true
default_probability = 0.03
mention_probability = 0.8
keyword_probability = 0.5
question_probability = 0.4
min_messages_between_replies = 15
max_replies_per_hour = 8

# 对话AI（必需）
[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
model = "gpt-4o"
temperature = 0.7
max_tokens = 500

# 意图识别AI（必需，会自动复用dialogue配置）
[QvQChat.intent]
api_key = ""  # 留空则使用dialogue配置
model = "gpt-3.5-turbo"
temperature = 0.1
max_tokens = 500

# 意图执行AI（必需，会自动复用dialogue配置）
[QvQChat.intent_execution]
api_key = ""
model = "gpt-3.5-turbo"
temperature = 0.3
max_tokens = 1000

# 记忆AI（可选，会自动复用dialogue配置）
[QvQChat.memory]
api_key = ""
model = "gpt-3.5-turbo"
temperature = 0.3
max_tokens = 1000

# 回复判断AI（可选，会自动复用dialogue配置）
[QvQChat.reply_judge]
api_key = ""
model = "gpt-3.5-turbo"
temperature = 0.1
max_tokens = 100

# 视觉AI（可选，会自动复用dialogue配置）
[QvQChat.vision]
api_key = ""
model = "gpt-4o"
temperature = 0.3
max_tokens = 300
```

### 运行时配置

运行时自动生成群和用户配置（无需手动配置）：

```toml
# 群配置
[QvQChat.groups."123456789"]
system_prompt = "这个群是技术交流群"
memory_mode = "mixed"  # mixed | sender_only
enable_memory = true
model_overrides = {}

# 用户配置
[QvQChat.users."user_id"]
style = "友好"
preferences = {}
```

## 使用示例

### 日常对话

```
用户：在吗？
AI：[不回复，保持安静]

用户：你觉得这个怎么样？
AI：我觉得挺好的。[偶尔回复，自然参与]

用户：@机器人 今天的天气怎么样？
AI：今天天气不错，适合出去玩。[被@时高概率回复]
```

### 记忆相关

```
用户：你记得我的生日吗？
AI：是的，我记得你的生日是6月15日。[记忆自然融入对话]

用户：记住这件事，我下周五要考试
AI：好的，我会记住你下周五要考试。[用户主动要求记忆]

用户：忘记这件事
AI：我会帮你删除相关记忆。
```

### 图片理解

```
用户：[发送图片] 这是什么？
AI：这是一张猫的照片，看起来很可爱。[dialogue AI直接理解图片]
```

### 系统操作

```
用户：清除会话
AI：好的，已清除当前会话历史。[intent_execution AI执行]

用户：把群提示词改成你是一个专业的技术顾问
AI：已将群提示词更新为：你是一个专业的技术顾问。

用户：群记忆模式改成sender_only
AI：已将群记忆模式更改为仅发送者模式。
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
- 仅对话AI配置: 基本对话功能正常，记忆会使用dialogue AI
- dialogue AI不支持视觉: 无法理解图片内容

**解决方法**: 为对应AI配置API密钥，或留空自动复用dialogue配置。

### 问题4：AI不回复任何消息

**可能原因**:
1. 窥屏模式概率过低（可调高 default_probability）
2. bot_ids/bot_nicknames 未正确配置
3. API密钥无效或过期

**检查方法**:
1. 查看日志中的AI判断结果
2. 确认机器人ID和昵称正确
3. 测试API连接

### 问题5：记忆不准确或过多

**解决方法**:
1. 调整记忆AI的temperature（降低会更严格）
2. 清理冗余记忆（通过意图执行删除）
3. 检查记忆提取标准（在handler._extract_and_save_memory中）

## 架构文档

详细的架构说明、组件设计和数据流请查看 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 开发与贡献

欢迎参与 QvQChat 的开发！详细的贡献指南请查看 [ARCHITECTURE.md](ARCHITECTURE.md) 中的"贡献指南"章节。

### 快速开发设置

```bash
# 1. Fork 项目
git clone https://github.com/your-username/ErisPulse-QvQChat.git
cd ErisPulse-QvQChat

# 2. 安装依赖
pip install -e .

# 3. 运行测试
python -m ErisPulse-QvQChat
```

### 核心组件

| 组件 | 文件 | 职责 |
|------|--------|------|
| Main | Core.py | 模块入口、事件处理、消息路由 |
| Config | config.py | 配置管理、配置继承 |
| AI Manager | ai_client.py | AI客户端管理、统一调用接口 |
| Intent | intent.py | 意图识别、意图路由 |
| Handler | handler.py | 意图处理、对话处理、记忆提取 |
| Memory | memory.py | 记忆管理、会话历史 |
| State | state.py | 状态管理、主题跟踪 |

详细组件设计请查看 [ARCHITECTURE.md](ARCHITECTURE.md)。
ErisPulse SDK(https://github.com/ErisPulse/ErisPulse)