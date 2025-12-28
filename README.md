# QvQChat 智能对话模块

## 简介

QvQChat 是一个基于多AI协同的智能对话模块，采用"普通群友模式"，让AI像真人一样自然参与聊天。

## 核心特性 ⭐

- **AI自主决策**：无需命令格式，直接用自然语言交互
- **记忆自然融合**：询问"你记得我的生日吗"，AI根据记忆自然回答
- **配置简化**：只需配置dialogue的API密钥，其他AI自动复用
- **窥屏模式**：群聊默默观察，适时回复（默认3%回复率）
- **多模态支持**：支持图片理解（需要gpt-4o等视觉模型）

## 快速开始

### 第一步：克隆代码仓库

```bash
# 使用 HTTPS 克隆
git clone https://github.com/wsu2059q/ErisPulse-QvQChat.git

# 或使用 SSH 克隆（如果配置了 SSH 密钥）
git clone git@github.com:wsu2059q/ErisPulse-QvQChat.git

# 进入项目目录
cd ErisPulse-QvQChat
```

### 第二步：配置文件

复制 `config.example.toml` 为 `config.toml`，然后进行**最简配置**：

```toml
[QvQChat]
bot_nicknames = ["Amer"]  # 你的机器人昵称
bot_ids = ["123456789"]    # 你的机器人ID

[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"  # 或使用中转服务
api_key = "sk-your-actual-api-key-here"  # 填入你的API密钥
model = "gpt-4o"  # 建议使用支持视觉的模型
```

**详细配置**：查看 [config.example.toml](config.example.toml) 获取完整配置选项，包括：
- 窥屏模式参数调整
- 多AI独立配置
- 群聊和用户个性化设置
- 对话连续性和记忆管理等
- 安全防护配置

### 第三步：安装

**详细教程**：查看 [INSTALL.md](INSTALL.md) 获取完整的 Docker 安装和配置说明。
> 建议使用 **Docker 安装**（完整环境隔离，推荐生产环境）
> 或使用 **手动安装**（开发环境，需要自定义）

#### Docker 安装（推荐）

**快速开始**：
```bash
# 1. 准备配置文件
cp config.example.toml config.toml

# 2. 启动容器
docker-compose up -d
```

#### 手动安装

> 前提：已安装 Python 3.9+ 和 ErisPulse 框架

```bash
# 安装适配器（根据需要）
epsdk install OneBot11  # QQ 适配器（推荐）

# 安装 QvQChat 模块
epsdk install QvQChat

# 启动 ErisPulse
ep run
```

### 第四步：启动

配置完成后，启动服务即可：

- **Docker**：`docker-compose up -d`
- **手动**：`ep run`

查看日志确认 QvQChat 模块已正常加载。

## 功能简介

### 1. AI智能决策（普通群友模式）

AI会根据对话上下文智能判断：
- **是否回复**：AI判断何时需要回应
- **是否记忆**：AI自动判断什么值得记住

群聊使用窥屏模式，大部分时间保持安静，偶尔参与对话（默认3%回复率），被@时积极响应（80%回复率）。

### 2. 记忆管理

对话后AI会自动提取重要信息保存到长期记忆。支持：
- 自然询问记忆："你记得我的生日吗？"
- 主动添加记忆："记住这件事，我下周五生日"
- 删除记忆："忘记这件事"

### 3. 图片理解

支持图片内容理解，dialogue AI可直接分析图片（需要视觉模型）。

## 窥屏模式说明

群聊默认启用窥屏模式，让机器人更像真人：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| enabled | true | 启用窥屏模式 |
| default_probability | 0.03 | 默认回复概率（3%） |
| mention_probability | 0.8 | 被@时回复概率（80%） |
| keyword_probability | 0.5 | 匹配关键词时回复概率（50%） |
| question_probability | 0.4 | 提问时回复概率（40%） |
| min_messages_between_replies | 15 | 两次回复之间至少间隔消息数 |
| max_replies_per_hour | 8 | 每小时最多回复次数 |

可在 `config.toml` 的 `[QvQChat.stalker_mode]` 部分调整这些参数。

## 安全防护

QvQChat 提供多层防护机制，防止恶意刷屏和资源滥用：

### 1. 消息长度限制
忽略过长的消息，防止恶意刷屏。

```toml
[QvQChat]
max_message_length = 1000  # 忽略长度超过此值的消息（字符数）
```

### 2. 速率限制
限制短时间内允许的最大 token 数量，防止刷 API 配额。

```toml
[QvQChat]
rate_limit_tokens = 20000   # 时间窗口内允许的最大token数
rate_limit_window = 60         # 时间窗口（秒）
```

**工作原理**：
- 每次回复前，估算需要的 token 数（包括输入和输出）
- 在时间窗口内（默认60秒），累计 token 数不能超过限制
- 超过限制时记录日志并跳过处理

### 3. 窥屏模式限制
群聊默认使用低回复率（3%），并有额外的限制：

- 每小时最多回复 8 次（可配置）
- 两次回复之间至少间隔 15 条消息（可配置）

## 配置优化

### AI 配置智能合并

只需配置 `dialogue` 的 API 密钥，其他 AI 自动复用：

```toml
[QvQChat.dialogue]
base_url = "https://api.siliconflow.cn/v1"
api_key = "sk-xxx"
model = "moonshotai/Kimi-K2-Instruct-0905"
temperature = 0.7
max_tokens = 500

# memory 使用自己的模型，但复用 dialogue 的 API 密钥
[QvQChat.memory]
model = "inclusionAI/Ling-mini-2.0"
temperature = 0.3
max_tokens = 1000

# intent 使用自己的模型，但复用 dialogue 的 API 密钥
[QvQChat.intent]
model = "tencent/Hunyuan-A13B-Instruct"
temperature = 0.1
max_tokens = 500

# vision 也可以有独立的 API 密钥
[QvQChat.vision]
base_url = "https://api.siliconflow.cn/v1"
api_key = "sk-xxx"  # 或留空复用 dialogue 的
model = "Qwen/Qwen3-VL-8B-Instruct"
temperature = 0.3
max_tokens = 300
```

**配置继承规则**：
- 优先使用 AI 自己的配置（model、temperature、max_tokens 等）
- 如果 AI 没有配置 `api_key`，复用 dialogue 的 `api_key`
- 如果 AI 没有配置 `base_url`，复用 dialogue 的 `base_url`
- 其他参数使用 AI 自己的配置，没有才使用默认值

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
AI：是的，我记得你的生日是6月15日。[记忆自然融入]

用户：记住这件事，我下周五要考试
AI：好的，我会记住你下周五要考试。[主动记忆]
```

## 更多文档

- **配置详解**：查看 [config.example.toml](config.example.toml) 获取完整配置选项和详细说明
- **架构文档**：查看 [ARCHITECTURE.md](ARCHITECTURE.md) 了解系统架构、核心组件、数据流等技术细节

## 相关链接

- [ErisPulse SDK](https://github.com/ErisPulse/ErisPulse) - 底层框架
