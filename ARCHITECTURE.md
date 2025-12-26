# QvQChat 架构文档

## 目录
- [系统架构](#系统架构)
- [核心组件](#核心组件)
- [数据流](#数据流)
- [配置系统](#配置系统)
- [贡献指南](#贡献指南)

---

## 系统架构

QvQChat 是一个基于多AI协同的智能对话模块，采用模块化设计，每个组件职责清晰，便于维护和扩展。

```
┌─────────────────────────────────────────────────────────────┐
│                    ErisPulse SDK                        │
│              (事件处理、消息路由、存储)                    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   QvQChat Main                       │
│              (模块入口、事件注册、协调)                    │
└────────┬────────────┬────────────┬──────────────┬─────┘
         │            │            │              │
         ▼            ▼            ▼              ▼
┌─────────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐
│QvQConfig  │ │QvQAIManager│ │QvQIntent│ │QvQHandler│
│(配置管理)   │ │ (AI客户端)  │ │(意图识别)│ │(意图处理)│
└─────────────┘ └─────┬─────┘ └─────┬────┘ └────┬────┘
                     │                │             │
                     ▼                ▼             ▼
              ┌──────────┐    ┌────────────┐ ┌──────────┐
              │QvQMemory│    │ QvQState    │ │          │
              │(记忆管理) │    │(状态管理)    │ │          │
              └──────────┘    └────────────┘ │          │
                     │                        │          │
                     └────────────────────────┴──────────┘
                                 ▲
                                 │
                        ErisPulse SDK Storage
```

### 设计原则

1. **单一职责**：每个类只负责一个核心功能
2. **依赖注入**：通过构造函数注入依赖，便于测试
3. **异步优先**：所有IO操作使用async/await
4. **模块化**：组件间通过接口通信，低耦合
5. **可扩展性**：易于添加新的AI类型、意图类型和处理器

---

## 核心组件

### 1. QvQChat/Main.py - 主入口

**职责**：
- 模块初始化和组件注册
- 消息事件监听和路由
- 窥屏模式（stalker mode）控制
- 回复时机判断

**关键方法**：
- `__init__()`: 初始化所有子模块
- `_handle_message()`: 消息处理主入口
- `_should_reply()`: 判断是否需要回复（私聊积极/群聊窥屏）
- `_get_session_key()`: 获取会话唯一标识
- `_get_reply_count_key()`: 获取回复计数器key

**核心逻辑**：
- 群聊使用 `group:{group_id}` 作为会话key（共享历史）
- 私聊使用 `user:{user_id}` 作为会话key（独立历史）
- 意图识别和回复判断并行执行（asyncio.gather）
- 窥屏模式：群聊默认3%回复率，被@时80%

**设计亮点**：
- 支持多消息延迟发送（模拟真人分句打字）
- 自动Markdown清理（移除加粗、代码等格式）
- 图片提取和视觉AI集成

---

### 2. QvQChat/config.py - 配置管理

**职责**：
- 加载和管理所有配置项
- 提供配置继承机制（未配置的AI复用dialogue配置）
- 群级和用户级配置管理
- 配置持久化（通过SDK Storage）

**关键方法**：
- `get_ai_config()`: 获取AI配置，支持配置继承
- `get_effective_system_prompt()`: 获取有效系统提示（群>用户>默认）
- `get_group_config()` / `set_group_config()`: 群配置管理
- `get_user_config()` / `set_user_config()`: 用户配置管理

**配置继承机制**：
```python
# 如果 memory AI 未配置 api_key
# 自动使用 dialogue 的配置，但调整参数：
if ai_type == "memory":
    ai_config["temperature"] = 0.3  # 降低温度
    ai_config["max_tokens"] = 1000  # 增加输出
```

**设计亮点**：
- 只需配置 dialogue 的 API 密钥，其他AI自动复用
- 支持群级系统提示词覆盖
- 支持用户级个性化配置

---

### 3. QvQChat/ai_client.py - AI客户端管理

**职责**：
- 管理多个OpenAI客户端（dialogue、memory、intent、vision等）
- 提供统一的AI调用接口
- AI连接测试和重载机制

**类结构**：
- `QvQAIClient`: 单个AI客户端封装
- `QvQAIManager`: 多AI管理器

**关键方法**（QvQAIManager）：
- `dialogue()`: 对话AI调用
- `identify_intent()`: 意图识别
- `execute_intent()`: 意图执行（系统操作）
- `memory_process()`: 记忆处理
- `analyze_image()`: 图片分析
- `should_reply()`: 回复判断（私聊用）

**支持的AI类型**：
- `dialogue`: 对话AI（必需）
- `intent`: 意图识别（必需）
- `intent_execution`: 意图执行（必需，替代命令系统）
- `memory`: 记忆提取（可选）
- `reply_judge`: 回复判断（可选）
- `vision`: 视觉分析（可选）

**设计亮点**：
- 自动重试和错误处理
- 支持流式输出（虽未使用）
- 统一的异常处理（RateLimitError、APITimeoutError、APIError）

---

### 4. QvQChat/intent.py - 意图识别

**职责**：
- 识别用户输入的意图类型
- 将意图路由到对应的处理器
- 意图处理器注册管理

**意图类型**：
- `dialogue`: 普通对话交流（包括询问记忆）
- `memory_add`: 用户主动要求记住信息（"记住这件事"）
- `memory_delete`: 用户主动要求删除记忆（"忘记这件事"）
- `intent_execution`: 系统操作指令（"切换模型"、"修改配置"等）

**关键方法**：
- `identify_intent()`: 使用AI识别意图
- `register_handler()`: 注册意图处理器
- `handle_intent()`: 路由到对应处理器

**识别逻辑**：
1. 调用 `ai_manager.identify_intent(user_input)`
2. AI返回意图类型（dialogue/memory_add/memory_delete/intent_execution）
3. 从 `intent_handlers` 字典查找处理器
4. 调用处理器并返回结果

**设计亮点**：
- 不再区分 memory_query，询问记忆作为普通对话处理
- 记忆自然融入对话，无需显式查询
- 支持处理器动态注册

---

### 5. QvQChat/handler.py - 意图处理器

**职责**：
- 实现各种意图的具体处理逻辑
- 对话处理（记忆自然融入）
- 记忆智能提取和保存
- 系统操作执行

**关键方法**：
- `handle_dialogue()`: 处理普通对话（记忆自然融入）
- `handle_memory_add()`: 处理添加记忆（用户主动要求）
- `handle_memory_delete()`: 处理删除记忆
- `handle_intent_execution()`: 处理系统操作
- `_extract_and_save_memory()`: 智能提取和保存记忆
- `_should_remember_dialogue()`: AI判断是否值得记忆

**记忆融合机制**（handle_dialogue）：
```python
# 获取用户的长时记忆
user_memory = await self.memory.get_user_memory(user_id)
long_term_memories = user_memory.get("long_term", [])

# 作为系统消息传递给AI
memory_text = "【用户长期记忆】\n" + "\n".join([...])
messages.append({"role": "system", "content": memory_text})

# AI根据记忆自然回答
# 用户：你记得我的生日吗？
# AI：是的，我记得你的生日是X月X日
```

**智能记忆提取**：
1. 使用 dialogue AI 判断对话是否值得记忆
2. 使用 memory AI 提取关键信息
3. 去重检查（避免重复记忆）
4. 保存到长期记忆

**设计亮点**：
- 记忆自然融入对话，无需显式查询
- AI自动判断记忆价值（去重、过滤）
- 支持图片描述合并（视觉AI分析结果）
- 支持多消息延迟发送

---

### 6. QvQChat/memory.py - 记忆管理

**职责**：
- 短期记忆管理（会话历史）
- 长期记忆管理（重要信息）
- 群记忆管理（sender_memory + shared_context）
- 记忆搜索和查询

**存储键设计**：
```
用户长期记忆: qvc:user:{user_id}:memory
群记忆:         qvc:group:{group_id}:memory
群上下文:       qvc:group:{group_id}:context
会话历史:       qvc:session:{chat_id}
```

**关键方法**：
- `get_user_memory()` / `set_user_memory()`: 用户记忆管理
- `get_group_memory()` / `set_group_memory()`: 群记忆管理
- `add_short_term_memory()`: 添加短期记忆（会话历史）
- `get_session_history()`: 获取会话历史
- `search_memory()`: 搜索记忆（简化版，不再用于对话）
- `add_long_term_memory()`: 添加长期记忆
- `add_group_memory()`: 添加群记忆

**会话历史策略**：
- 私聊：`user:{user_id}` - 每个用户独立
- 群聊：`group:{group_id}` - 群内所有用户共享
- 最多保留20条（可配置）
- 群聊中用户消息添加 `[user_id]` 前缀

**记忆结构**：
```python
# 用户记忆
{
    "short_term": [],  # 会话历史（已移至session storage）
    "long_term": [  # 长期记忆
        {
            "content": "用户生日是6月15日",
            "tags": ["auto"],
            "timestamp": "2025-01-01T00:00:00",
            "importance": 1.0
        }
    ],
    "semantic": [],
    "last_updated": "2025-01-01T00:00:00"
}

# 群记忆
{
    "sender_memory": {  # 发送者记忆
        "user_id_1": [...],
        "user_id_2": [...]
    },
    "shared_context": [  # 群共享上下文（群规则等）
        {
            "content": "群规则：禁止刷屏",
            "timestamp": "2025-01-01T00:00:00"
        }
    ],
    "last_updated": "2025-01-01T00:00:00"
}
```

**设计亮点**：
- 群聊会话历史共享（AI能看到所有对话）
- 群记忆支持两种模式（sender_only / mixed）
- 自动记忆压缩（超限时保留最近50条）
- 支持记忆导出

---

### 7. QvQChat/state.py - 状态管理

**职责**：
- 管理对话状态（主题、交互计数等）
- 跟踪用户情绪状态
- 上下文关键词管理

**状态结构**：
```python
{
    "current_topic": "当前对话主题",
    "last_topic": "上一个主题",
    "topic_start_time": "2025-01-01T00:00:00",
    "interaction_count": 10,
    "last_interaction": "2025-01-01T00:00:00",
    "mood": "happy",
    "context_keywords": ["关键词1", "关键词2"],
    "pending_actions": []
}
```

**关键方法**：
- `get_state()` / `update_state()`: 状态管理
- `increment_interaction()`: 增加交互计数
- `update_topic()`: 更新对话主题
- `add_context_keyword()`: 添加上下文关键词
- `update_mood()`: 更新情绪状态
- `should_change_topic()`: 判断是否应该切换主题

**设计亮点**：
- 支持主题切换检测（超过5分钟自动切换）
- 自动记录最后交互时间
- 关键词去重和限制（最多10个）

---

## 数据流

### 1. 消息处理流程

```
用户发送消息
    │
    ▼
Core._handle_message()
    │
    ├─→ 提取图片URL
    ├─→ 获取用户信息
    ├─→ 检查API配置
    │
    ├─→ [并行] intent.identify_intent()
    │           └─→ 返回意图类型（dialogue/memory_add等）
    │
    ├─→ [并行] _should_reply()
    │           └─→ 返回是否需要回复
    │
    ├─→ memory.add_short_term_memory()  # 保存用户消息到会话历史
    │
    └─→ 如果需要回复:
            │
            ▼
        intent.handle_intent()
            │
            ├─→ 根据 intent 路由到对应处理器
            │
            └─→ 例如：dialogue
                    │
                    ▼
                handler.handle_dialogue()
                    │
                    ├─→ 获取会话历史（含刚保存的用户消息）
                    ├─→ 获取用户长时记忆
                    │   └─→ 构建系统消息："【用户长期记忆】\n- ..."
                    │
                    ├─→ 构建messages列表：
                    │   - 系统提示词
                    │   - 上下文信息
                    │   - 用户记忆
                    │   - 场景提示
                    │   - 会话历史[-15:]
                    │
                    ├─→ [如果有多图] vision AI 分析
                    ├─→ dialogue AI 生成回复
                    ├─→ memory.add_short_term_memory()  # 保存AI回复
                    ├─→ handler._extract_and_save_memory()  # 智能提取记忆
                    │   └─→ [AI判断是否值得记忆]
                    │       └─→ [memory AI 提取关键信息]
                    │           └─→ 去重保存
                    │
                    └─→ 返回回复
```

### 2. 记忆提取流程

```
对话完成（用户消息 + AI回复）
    │
    ▼
handler._extract_and_save_memory()
    │
    ├─→ 获取最近15条对话
    ├─→ [第一步] dialogue AI 判断是否值得记忆
    │       Prompt: "判断这段对话是否值得记住？"
    │       Return: "值得" / "不值得"
    │
    └─→ 如果值得记忆:
            │
            ▼
        memory AI 提取关键信息
            │
            ├─→ Prompt: "从对话中提取值得记住的信息..."
            ├─→ 严格标准（个人偏好、重要日期、任务等）
            ├─→ 过滤无关信息（闲聊、问候、表情等）
            │
            ▼
        去重检查
            │
            ├─→ 对比现有记忆
            └─→ 只保存不重复的信息
```

### 3. 群聊 vs 私聊处理差异

| 特性 | 私聊 | 群聊 |
|------|--------|--------|
| 会话历史key | `user:{user_id}` | `group:{group_id}` |
| 历史共享范围 | 用户独立 | 群内所有用户共享 |
| 回复策略 | 积极回复（AI判断） | 窥屏模式（默认3%回复率） |
| 回复计数器 | 用户独立 | 群内共享 |
| 记忆存储 | 只存用户个人记忆 | 用户个人 + 群记忆（混合模式） |

---

## 配置系统

### 配置文件结构

```toml
[QvQChat]
# 基础配置
max_history_length = 20
min_reply_interval = 10
bot_nicknames = []
bot_ids = []

[QvQChat.stalker_mode]
# 窥屏模式配置
enabled = true
default_probability = 0.03
mention_probability = 0.8
keyword_probability = 0.5
question_probability = 0.4
min_messages_between_replies = 15
max_replies_per_hour = 8

[QvQChat.dialogue]
# 对话AI（必需）
base_url = "https://api.openai.com/v1"
api_key = "sk-..."
model = "gpt-4o"
temperature = 0.7
max_tokens = 500
system_prompt = "..."

[QvQChat.reply_judge]
# 回复判断AI（可选，不配置则复用dialogue）
base_url = "https://api.openai.com/v1"
api_key = ""  # 空则使用dialogue配置
model = "gpt-3.5-turbo"
temperature = 0.1
max_tokens = 100

[QvQChat.memory]
# 记忆AI（可选）
api_key = ""  # 空则使用dialogue配置
model = "gpt-3.5-turbo"
temperature = 0.3
max_tokens = 1000

[QvQChat.intent]
# 意图识别AI（必需）
api_key = ""  # 空则使用dialogue配置
model = "gpt-3.5-turbo"
temperature = 0.1
max_tokens = 500

[QvQChat.intent_execution]
# 意图执行AI（必需，替代命令）
api_key = ""  # 空则使用dialogue配置
model = "gpt-3.5-turbo"
temperature = 0.3
max_tokens = 1000

[QvQChat.vision]
# 视觉AI（可选）
api_key = ""  # 空则使用dialogue配置
model = "gpt-4o"
temperature = 0.3
max_tokens = 300
```

### 运行时配置（自动生成）

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

---

## 贡献指南

欢迎参与 QvQChat 的开发！以下是贡献指南。

### 开发环境设置

1. **Fork 项目**
   ```bash
   git clone https://github.com/your-username/ErisPulse-AIChat.git
   cd ErisPulse-AIChat
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   # 或使用 pip install -e .
   ```

3. **运行测试**
   ```bash
   # 确保配置好 config.toml
   python -m ErisPulse-AIChat
   ```

### 代码风格

1. **Python 版本**
   - 最低支持 Python 3.9
   - 推荐使用 Python 3.10+

2. **代码格式**
   - 使用 4 空格缩进
   - 行长度建议不超过 120 字符
   - 遵循 PEP 8 规范

3. **文档字符串**
   - 所有公开方法必须有详细的 docstring
   - 使用 Google 风格的 docstring
   ```python
   def method_name(self, param1: str, param2: int) -> str:
       """方法的简要描述。

       详细说明（可以多行）。

       Args:
           param1: 参数1的说明
           param2: 参数2的说明

       Returns:
           str: 返回值的说明

       Raises:
           ValueError: 在什么情况下抛出
       """
       pass
   ```

4. **注释规范**
   - 代码逻辑复杂处添加中文注释
   - 注释解释"为什么"而不是"是什么"
   - 移除无用的注释（如 `# TODO`、`# FIXME`）

### 测试

1. **单元测试**
   - 为核心逻辑添加单元测试
   - 测试文件命名：`test_<module_name>.py`
   - 使用 pytest 框架

2. **集成测试**
   - 测试 AI 调用（使用 mock）
   - 测试配置加载和持久化
   - 测试消息处理流程

3. **手动测试**
   - 在真实环境中测试
   - 测试各种场景（私聊、群聊、图片等）
   - 检查日志输出

### 提交 Pull Request

1. **分支命名**
   - 功能：`feature/功能名称`
   - 修复：`fix/问题描述`
   - 重构：`refactor/重构内容`

2. **Commit 信息**
   - 格式：`<类型>: <描述>`
   - 类型：feat, fix, docs, style, refactor, test, chore
   - 示例：`feat: 添加新的AI类型支持`

3. **PR 描述**
   - 说明修改的目的
   - 列出主要变更
   - 关联相关的 issue
   - 添加测试截图（如有）

### 文档

1. **更新 README**
   - 新功能添加使用说明
   - 更新配置示例
   - 添加故障排除条目

2. **更新文档**
   - 架构变更更新本文档
   - API 变更添加说明
   - 添加代码示例

### 常见开发任务

1. **添加新的 AI 类型**
   ```python
   # 1. 在 ai_client.py 添加客户端方法
   async def new_ai_method(self, input: str) -> str:
       client = self.get_client("new_ai_type")
       if not client:
           return "新AI未配置"
       return await client.chat([{"role": "user", "content": input}])

   # 2. 在 config.py 添加默认配置
   "new_ai_type": {
       "base_url": "https://api.openai.com/v1",
       "api_key": "",
       "model": "gpt-3.5-turbo",
       "temperature": 0.5,
       "max_tokens": 1000,
       "system_prompt": "..."
   }

   # 3. 在 ai_client._init_ai_clients() 添加初始化
   ai_types = ["dialogue", "memory", "intent", "new_ai_type", ...]
   ```

2. **添加新的意图类型**
   ```python
   # 1. 在 handler.py 实现处理器
   async def handle_new_intent(self, user_id, group_id, params, intent_data) -> str:
       # 处理逻辑
       return "处理结果"

   # 2. 在 Core._register_intent_handlers() 注册
   self.intent.register_handler("new_intent", self.handler.handle_new_intent)

   # 3. 在 intent.py 更新识别逻辑
   # AI 会自动识别新意图类型
   ```

3. **扩展记忆功能**
   ```python
   # 在 memory.py 添加新方法
   async def new_memory_method(self, user_id: str, data: Any) -> None:
       # 记忆处理逻辑
       pass

   # 在 handler.py 调用
   await self.memory.new_memory_method(user_id, data)
   ```

### 调试

1. **启用调试日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **查看日志**
   ```bash
   tail -f logs/qvqchat.log
   ```

3. **使用 pdb 调试**
   ```python
   import pdb; pdb.set_trace()
   ```

### 性能优化

1. **AI 调用优化**
   - 使用并行调用（asyncio.gather）
   - 缓存 AI 响应（如合适）
   - 设置合理的 timeout

2. **存储优化**
   - 定期清理过期数据
   - 压缩大段文本
   - 使用索引加速搜索

3. **内存优化**
   - 避免在内存中保存大量历史
   - 使用生成器处理大数据集
   - 及时释放不再需要的资源

### 常见问题

**Q: 如何测试 AI 调用而不消耗配额？**
A: 使用 mock 客户端：
   ```python
   from unittest.mock import AsyncMock
   ai_manager.get_client = AsyncMock(return_value=mock_client)
   ```

**Q: 如何添加新的平台支持？**
A: 在 Core._send_response() 添加平台特定的处理逻辑

**Q: 如何修改记忆提取标准？**
A: 在 handler._extract_and_save_memory() 修改提取 prompt

**Q: 如何添加新的配置项？**
A: 1. 在 config._get_default_config() 添加默认值
   2. 在 config.py 添加 getter/setter 方法
   3. 更新 config.example.toml 和 README.md

---

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 联系方式

- 作者：wsu2059q
- 邮箱：wsu2059@qq.com
- GitHub：https://github.com/wsu2059q/ErisPulse-AIChat
