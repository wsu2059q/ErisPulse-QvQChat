# QvQChat 架构文档

## 目录
- [系统架构](#系统架构)
- [核心组件](#核心组件)
- [数据流](#数据流)
- [配置系统](#配置系统)
- [命令系统](#命令系统)

---

## 系统架构

QvQChat 是一个基于多AI协同的智能对话模块，采用模块化设计，每个组件职责清晰，便于维护和扩展。

```
┌─────────────────────────────────────────────────────────────┐
│                   QvQChat 主模块                 │
│              (模块生命周期、事件注册、协调)                    │
└────────┬────────────┬────────────┬──────────────┬──────┘
         │            │            │              │
         ▼            ▼            ▼              ▼
┌─────────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐
│ConfigMgr    │ │AIManager  │ │IntentMgr │ │Handler  │
│(配置管理)   │ │ (AI客户端)  │ │(意图识别)│ │(意图处理)│
└─────────────┘ └─────┬─────┘ └─────┬────┘ └────┬────┘
                     │                │             │
                     ▼                ▼             ▼
              ┌──────────┐    ┌────────────┐ ┌──────────┐
              │MemoryMgr │    │StateMgr    │ │Utils     │
              │(记忆管理) │    │(状态管理)    │ │(公共工具)│
              └──────────┘    └────────────┘ └──────────┘
                     │                │
                     ▼                ▼
              ┌──────────┐    ┌────────────┐
              │Commands  │  │SessionMgr  │
              │(命令系统) │  │(会话管理)   │
              └──────────┘    └────────────┘
                     │                │
                     ▼                ▼
              ┌─────────────────────────────┐
              │ActiveModeMgr + ReplyJudge  │
              │(活跃模式 + 回复判断)       │
              └─────────────────────────────┘
                     │
                     └────────────────────────┴──────────┘
                                 ▲
                                 │
                        底层框架存储服务
```

### 设计原则

1. **单一职责**：每个类/模块只负责一个核心功能
2. **依赖注入**：通过构造函数注入依赖，便于测试
3. **异步优先**：所有IO操作使用async/await
4. **模块化**：组件间通过接口通信，低耦合
5. **可扩展性**：易于添加新的AI类型、意图类型和处理器
6. **DRY原则**：避免代码重复，公共功能抽取到utils模块
7. **命令优先**：命令系统与AI处理分离，确保命令始终可用
8. **安全第一**：多层防护机制，防止恶意刷屏和资源滥用

---

## 核心组件

### 1. Core.py - 主模块

**职责**：
- 模块生命周期管理（`on_load`/`on_unload`）
- 消息事件监听和路由
- 对话连续性监听
- 协调各管理器完成消息处理

**关键方法**：
- `should_eager_load()`: 是否需要立即加载
- `on_load()`: 模块加载时初始化
  - 初始化管理器
  - 注册意图处理器
  - 注册命令系统
  - 注册消息事件监听
- `on_unload()`: 模块卸载时清理资源
- `_handle_message()`: 消息处理主入口
- `_continue_conversation_if_needed()`: 对话连续性监听

**核心逻辑**：
- 群聊使用 `group:{group_id}` 作为会话key（共享历史）
- 私聊使用 `user:{user_id}` 作为会话key（独立历史）
- 意图识别和回复判断并行执行（asyncio.gather）
- 对话连续性：AI回复后监听后续3条消息，持续关注

---

### 2. session_manager.py - 会话管理器

**职责**：
- 会话历史管理
- 消息计数和回复时间跟踪
- 图片缓存机制（等待可能的文本消息）
- 群沉寂检测

**关键方法**：
- `get_session_key()`: 获取会话唯一标识
- `add_message_to_history()`: 添加消息到会话历史
- `get_session_history()`: 获取会话历史
- `increment_reply_count()`: 增加回复计数
- `get_reply_count()`: 获取当前回复计数
- `should_limit_replies()`: 判断是否需要限制回复
- `record_reply_time()`: 记录回复时间
- `time_since_last_reply()`: 计算距离上次回复的时间
- `update_message_count()`: 更新消息计数
- `should_reply_based_on_interval()`: 基于消息间隔判断是否回复
- `cache_image()`: 缓存图片
- `get_cached_image()`: 获取缓存的图片
- `clear_image_cache()`: 清除图片缓存
- `track_group_silence()`: 跟踪群沉寂状态
- `is_group_silent()`: 判断群是否处于沉寂状态
- `reset_silence_tracker()`: 重置沉寂跟踪器

---

### 3. active_mode_manager.py - 活跃模式管理器

**职责**：
- 活跃模式启用/禁用管理
- 活跃模式状态查询
- 活跃模式过期检测

**关键方法**：
- `enable_active_mode()`: 启用活跃模式
- `disable_active_mode()`: 禁用活跃模式
- `is_active_mode()`: 判断是否处于活跃模式
- `get_active_mode_info()`: 获取活跃模式信息

---

### 4. reply_judge.py - 回复判断器

**职责**：
- 速率限制检查
- 消息长度检查
- 窥屏模式回复概率判断
- AI智能回复判断

**关键方法**：
- `should_reply()`: 判断是否需要回复（综合判断）
- `check_message_length()`: 检查消息长度是否超过限制
- `check_rate_limit()`: 检查是否超过速率限制
- `estimate_tokens()`: 估算文本的token数量
- `check_stalker_mode_reply()`: 窥屏模式回复判断
- `check_active_mode_reply()`: 活跃模式回复判断
- `is_ai_enabled()`: 判断AI是否启用

**窥屏模式回复策略**：
- 被@时：高概率回复（80%）
- 匹配关键词时：中概率回复（50%）
- 群沉寂时：AI智能判断
- 其他情况：低概率回复（3%）

---

### 5. config.py - 配置管理

**职责**：
- 加载和管理所有配置项
- 提供配置继承机制（未配置的AI复用dialogue配置）
- 群级和用户级配置管理
- 配置持久化

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

---

### 6. ai_client.py - AI客户端管理

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
- `memory`: 记忆提取（可选，默认复用dialogue）
- `reply_judge`: 回复判断（可选，默认复用dialogue）
- `vision`: 视觉分析（可选，默认复用dialogue）

---

### 7. intent.py - 意图识别

**职责**：
- 识别用户输入的意图类型
- 将意图路由到对应的处理器
- 意图处理器注册管理

**意图类型**：
- `dialogue`: 普通对话交流（包括询问记忆）
- `memory_add`: 用户主动要求记住信息（"记住这件事"）
- `memory_delete`: 用户主动要求删除记忆（"忘记这件事"）

**关键方法**：
- `identify_intent()`: 使用AI识别意图
- `register_handler()`: 注册意图处理器
- `handle_intent()`: 路由到对应处理器

---

### 8. handler.py - 意图处理器

**职责**：
- 实现各种意图的具体处理逻辑
- 对话处理（记忆自然融入）
- 记忆智能提取和保存

**关键方法**：
- `handle_dialogue()`: 处理普通对话（记忆自然融入）
- `handle_memory_add()`: 处理添加记忆（用户主动要求）
- `handle_memory_delete()`: 处理删除记忆
- `_extract_and_save_memory()`: 智能提取和保存记忆
- `_should_remember_dialogue()`: AI判断是否值得记忆
- `_build_context_prompt()`: 构建上下文提示信息

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

**智能记忆提取流程**：
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

---

### 9. memory.py - 记忆管理

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
- `search_memory()`: 搜索记忆
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

---

### 10. state.py - 状态管理

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

---

### 11. utils.py - 公共工具

**职责**：
- 提供跨模块共享的工具函数和类
- 统一处理文本格式化和消息解析
- 封装消息发送逻辑（文本、语音、延迟）
- 语音合成（SiliconFlow API）

**公共函数**：
- `get_session_description()`: 获取会话描述字符串（用于日志）
- `truncate_message()`: 截断消息字符串用于日志
- `parse_multi_messages()`: 解析多条消息（支持延迟分隔符）
- `parse_speak_tags()`: 解析语音标签，提取文本和语音内容
- `record_voice()`: 生成语音（使用SiliconFlow API）

**公共类**：
- `MessageSender`: 统一的消息发送处理器

**parse_multi_messages() 功能**：
- 解析格式：
  - 新格式：`消息1\n<|wait time="3"|>\n消息2`
  - 老格式：`消息1\n[间隔:3]\n消息2` 或 `[间隔：3]`
- 返回消息列表，每条消息包含 `content` 和 `delay`
- 最多返回3条消息
- 支持语音标签，自动跳过语音标签内的分隔符

**MessageSender 类**：
- `send()`: 统一的消息发送接口
- `_send_single_message()`: 发送单条消息（可能包含文本和语音）
- `_send_text_and_voice()`: 发送文本和语音
- `_send_voice_file()`: 发送语音文件（尝试base64和本地路径）

**支持格式**：
- `<|wait time="N"|>`：多消息分隔符（N为延迟秒数，1-5秒，最多3条）
- `[间隔:N]` 或 `[间隔：N]`：兼容老格式的间隔标签
- `<|voice style="...">...</|voice>`：语音标签（每条消息可包含一个）

---

### 12. commands.py - 命令系统

**职责**：
- 注册和管理 QvQChat 的所有命令
- 提供丰富的命令接口（会话、记忆、配置、活跃模式等）
- 管理员权限控制
- 确保命令始终可用（即使AI被禁用）

**命令组划分**：
- 会话管理：会话管理命令
- 记忆管理：记忆管理命令
- 配置查看：配置查看命令
- 活跃模式：活跃模式命令
- AI控制：AI启用/禁用命令
- 群管理：群管理命令（仅管理员或群主）
- 管理员：管理员命令（需要管理员权限）

**关键方法**：
- `_is_admin()`: 检查用户是否为管理员
- `_is_group_admin()`: 检查用户是否为群管理员或系统管理员
- `register_all()`: 注册所有命令
- `_send_reply()`: 发送回复消息

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
    ├─→ [安全检查1] ReplyJudge.check_message_length()
    │           └─→ 消息长度是否超过限制
    │                   └─→ 超过则直接返回，不处理
    │
    ├─→ [安全检查2] ReplyJudge.is_ai_enabled()
    │           └─→ AI是否启用（AI禁用时不处理，命令仍可用）
    │
    ├─→ [图片处理] SessionMgr.cache_image()（等待可能的文本消息）
    │
    ├─→ SessionMgr.add_message_to_history()
    │
    ├─→ [回复判断] ReplyJudge.should_reply()
    │           │
    │           ├─→ 私聊场景：AI智能判断
    │           │
    │           ├─→ 群聊场景：
    │           │       │
    │           │       ├─→ ActiveModeMgr.is_active_mode()
    │           │       │       ├─→ 是：AI智能判断
    │           │       │       └─→ 否：窥屏模式
    │           │       │
    │           │       └─→ ReplyJudge.check_stalker_mode_reply()
    │           │               ├─→ 被@时：高概率回复（80%）
    │           │               ├─→ 匹配关键词：中概率回复（50%）
    │           │               ├─→ SessionMgr.is_group_silent()
    │           │               │       └─→ 群沉寂：AI智能判断
    │           │               └─→ SessionMgr.should_reply_based_on_interval()
    │           │                       └─→ 消息间隔：低概率回复（3%）
    │           │
    │           └─→ SessionMgr.should_limit_replies()
    │                   └─→ 检查每小时回复限制
    │
    ├─→ [窥屏优化] 不回复时直接返回（不进行意图识别，节省AI请求）
    │
    └─→ 如果需要回复:
            │
            ├─→ [安全检查3] ReplyJudge.check_rate_limit()
            │           └─→ 估算token数量
            │           └─→ 检查是否超过速率限制
            │                   └─→ 超过则直接返回，不处理
            │
            ├─→ IntentMgr.identify_intent()
            │           └─→ AI识别意图类型（dialogue/memory_add/memory_delete）
            │
            ├─→ 构建上下文信息（包含@、用户昵称、群信息等）
            │
            ▼
        IntentMgr.handle_intent()
            │
            └─→ 例如：dialogue
                    │
                    ▼
                Handler.handle_dialogue()
                    │
                    ├─→ SessionMgr.get_session_history()
                    ├─→ MemoryMgr 获取长期记忆
                    │
                    ├─→ 构建messages列表：
                    │   - 系统提示词
                    │   - 上下文信息（场景、发送者、机器人信息、时间、@等）
                    │   - 用户记忆
                    │   - 场景提示（私聊/群聊、语音功能、多消息格式）
                    │   - 会话历史[-15:]
                    │
                    ├─→ [如果有多图] AIManager.analyze_image()
                    ├─→ AIManager.dialogue() 生成回复
                    ├─→ SessionMgr.add_message_to_history()  # 保存AI回复
                    ├─→ Handler._extract_and_save_memory()  # 智能提取记忆
                    │   └─→ [AI判断是否值得记忆]
                    │       └─→ [AIManager.memory_process() 提取关键信息]
                    │           └─→ MemoryMgr 去重保存（用户记忆+群记忆）
                    │
                    └─→ 返回回复
                        │
                        ▼
                    Utils.MessageSender.send() 统一处理
                        │   └─→ parse_multi_messages() 解析多消息
                        │           └─→ 支持文本、语音、延迟
                        │           └─→ 逐条发送（带延迟）
                        │
                        ▼
                    SessionMgr.record_reply_time() + SessionMgr.clear_image_cache()
                        │
                        ▼
                    [群聊] 对话连续性监听
                        └─→ Core._continue_conversation_if_needed()
                                └─→ 监听后续3条消息，判断是否继续
```

### 2. 记忆提取流程

```
对话完成（用户消息 + AI回复）
    │
    ▼
Handler._extract_and_save_memory()
    │
    ├─→ 获取最近15条对话
    ├─→ [第一步] AIManager.dialogue() 判断是否值得记忆
    │       Prompt: "判断这段对话是否值得记住？"
    │       Return: "值得" / "不值得"
    │
    └─→ 如果值得记忆:
            │
            ▼
        AIManager.memory_process() 提取关键信息
            │
            ├─→ Prompt: "从对话中提取值得记住的信息..."
            ├─→ 严格标准（个人偏好、重要日期、任务等）
            ├─→ 过滤无关信息（闲聊、问候、表情等）
            │
            ▼
        MemoryMgr 去重检查
            │
            ├─→ 对比现有记忆
            └─→ 只保存不重复的信息
```

### 3. 对话连续性监听流程

```
AI回复发送成功
    │
    ▼
Core._continue_conversation_if_needed()
    │
    ├─→ 记录当前时间戳和回复内容
    ├─→ 启动监听任务（如启用）
    │
    └─→ 监听后续消息：
            │
            ├─→ [条件1] 未超过max_messages（默认3条）
            ├─→ [条件2] 未超过max_duration（默认120秒）
            ├─→ [条件3] 消息是回复给AI的或与对话相关
            │
            └─→ 满足条件则：
                    │
                    ├─→ AIManager.should_reply() 判断是否需要补全回应
                    ├─→ 如需要则生成后续回复
                    ├─→ 更新监听计数
                    └─→ 检查是否继续监听
```

### 4. 群聊 vs 私聊处理差异

| 特性 | 私聊 | 群聊 |
|------|--------|--------|
| 会话历史key | `user:{user_id}` | `group:{group_id}` |
| 历史共享范围 | 用户独立 | 群内所有用户共享 |
| 回复策略 | 积极回复（AI判断） | 窥屏模式（默认3%回复率） |
| 活跃模式 | 支持（临时切换为AI判断） | 支持（临时切换为AI判断） |
| 回复计数器 | 用户独立 | 群内共享 |
| 每小时回复限制 | 无 | 有（默认8次/小时） |
| 记忆存储 | 只存用户个人记忆 | 用户个人 + 群记忆（混合模式） |
| 对话连续性 | 启用，监听3条后续消息 | 启用，监听3条后续消息 |
| 群沉寂检测 | 不适用 | 启用（沉寂后AI智能判断） |
| 消息间隔限制 | 不适用 | 有（默认15条消息） |
| 被@处理 | 无特殊处理 | 高概率回复（80%） |

### 5. 活跃模式流程

```
用户发送 /活跃模式 命令
    |
    ▼
Core.enable_active_mode()
    |
    ├─→ ActiveModeMgr.enable_active_mode()
    |
    ▼
后续消息处理：
    |
    ├─→ ReplyJudge.should_reply()
    |       |
    |       ├─→ ActiveModeMgr.is_active_mode()
    |       |       ├─→ 是：使用AI智能判断（积极参与聊天）
    |       |       └─→ 否：使用窥屏模式
    |       |
    └─→ 活跃模式到期后自动切换回窥屏模式
```

---

## 配置系统

### 配置文件结构

```toml
[QvQChat]
# 基础配置
max_history_length = 20
memory_cleanup_interval = 86400
enable_vector_search = false
max_memory_tokens = 10000
memory_compression_threshold = 5
bot_nicknames = []
bot_ids = []

# 安全防护配置
max_message_length = 1000  # 忽略长度超过此值的消息（防止恶意刷屏）
rate_limit_tokens = 20000  # 短时间内允许的最大token数（防止刷token）
rate_limit_window = 60     # 时间窗口（秒）
ignore_command_messages = true  # 忽略以指令前缀开头的消息

[QvQChat.admin]
# 管理员配置
admins = []  # 管理员用户ID列表

[QvQChat.stalker_mode]
# 窥屏模式配置
enabled = true
default_probability = 0.03
mention_probability = 0.8
keyword_probability = 0.5
question_probability = 0.4
min_messages_between_replies = 15
max_replies_per_hour = 8
silence_threshold_minutes = 30  # 群内沉寂阈值（分钟）
continue_conversation_enabled = true  # 启用对话连续性分析
continue_max_messages = 3  # 最多监听多少条后续消息
continue_max_duration = 120  # 监听时长限制（秒）

[QvQChat.reply_strategy]
# 回复策略配置
reply_on_keyword = []  # 匹配关键词时回复概率

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
# 意图识别AI（可选，默认复用dialogue）
api_key = ""  # 空则使用dialogue配置
model = "gpt-3.5-turbo"
temperature = 0.1
max_tokens = 500

[QvQChat.vision]
# 视觉AI（可选）
api_key = ""  # 空则使用dialogue配置
model = "gpt-4o"
temperature = 0.3
max_tokens = 300

[QvQChat.voice]
# 语音合成配置（可选）
enabled = false
api_url = "https://api.siliconflow.cn/v1/audio/speech"
api_key = ""
model = "FunAudioLLM/CosyVoice2-0.5B"
voice = "speech:amer:nu5h6ye36m:ahldwvelhofwpcqcxoky"
speed = 1.0
gain = 0.0
sample_rate = 44100
platforms = ["qq", "onebot11"]
```

### 自定义`群聊`/`用户`配置

```toml
# 群配置
[QvQChat.groups."123456789"]
system_prompt = "这个群是技术交流群"
memory_mode = "mixed"  # mixed | sender_only
enable_memory = true
enable_ai = true  # AI启用状态
model_overrides = {}

# 用户配置
[QvQChat.users."user_id"]
style = "友好"
preferences = {}
```

---

## 命令系统

### 命令组划分

QvQChat 提供了丰富的命令系统，分为以下命令组：

#### 1. 会话管理命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/清除会话` | 清空会话、清空对话历史、清除对话 | 清除对话历史（短期记忆） |
| `/查看会话` | 对话历史、历史记录 | 查看对话历史（最近20条） |

#### 2. 记忆管理命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/查看记忆` | 我的记忆、记忆列表 | 查看长期记忆（最近30条） |
| `/清除记忆` | 清空记忆、删除所有记忆 | 清除所有长期记忆 |

#### 3. 配置查看命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/群配置` | 群设定、群模式、群提示词 | 查看群配置（群聊专用） |
| `/状态` | 机器人状态、系统状态 | 查看系统状态（AI配置、窥屏模式、记忆统计） |

#### 4. 活跃模式命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/活跃模式 [分钟]` | 开启活跃、活跃起来、取消窥屏 | 启用活跃模式（默认10分钟） |
| `/关闭活跃` | 结束活跃、恢复窥屏 | 关闭活跃模式 |
| `/活跃状态` | 当前模式、是否活跃 | 查看当前模式状态 |

#### 5. AI控制命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/启用AI` | 开启AI、激活AI | 启用AI回复功能 |
| `/禁用AI` | 关闭AI、停用AI | 禁用AI回复功能（命令仍可用） |
| `/AI状态` | 查看AI、AI开关 | 查看AI启用状态 |

#### 6. 群管理命令（管理员或群主）

| 命令 | 别名 | 说明 |
|------|------|------|
| `/清除群上下文` | 清空群上下文、删除群上下文 | 清除群公共上下文 |
| `/清除群记忆` | 清空群记忆、删除群记忆 | 清除群记忆 |

#### 7. 管理员命令（需要管理员权限）

| 命令 | 别名 | 说明 |
|------|------|------|
| `/admin.add [用户ID]` | 添加管理员 | 添加管理员 |
| `/admin.remove [用户ID]` | 移除管理员 | 移除管理员 |
| `/admin.list` | 管理员列表、查看管理员 | 查看管理员列表 |
| `/admin.reload` | 重载配置、重新加载配置 | 重新加载配置 |
| `/admin.clear_all_memory` | 清空所有记忆、清除全部记忆 | 清除所有用户记忆（需确认） |
| `/admin.clear_all_sessions` | 清空所有会话、清除全部会话 | 清除所有用户会话历史（需确认） |
| `/admin.clear_all_groups` | 清空所有群聊、清除全部群 | 清除所有群记忆和上下文（需确认） |
