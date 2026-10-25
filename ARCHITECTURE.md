# QvQChat 架构文档

技术架构与模块职责说明。使用与配置说明见 [README](README.md)。

## 包结构

```
QvQChat/
├── Main.py                  # 主编排器：事件入口、触发判定、限流与消息合批、合成上下文入口、命令、审计、用量统计
├── Config.py                # QvQConfig 声明式配置（BaseConfig dataclass）
├── I18n.py                  # 配置描述多语言键（五语言）
├── texts.py                 # 运行时文案注册（五语言）+ t() 助手
├── providers.py             # Provider 预设表（16 家厂商 id/name/base_url，供模型池一键添加）
├── version.py               # 版本号
├── utils.py                 # 签名解析、schedule/cron 解析、进程执行、回复分段与转发节点、通用工具
│
├── engine/                  # 模型引擎层
│   ├── base.py              # ChatRequest / ChatResponse / ToolCall / TaskSpec / EngineError
│   ├── openai.py            # OpenAI 兼容引擎（连续 system 合并、流式增量、思考过滤、工具调用解析）
│   ├── pool.py              # ModelPool：Provider/模型 CRUD、models.dev 目录、按 needs/prefer/池序分派、熔断与故障转移
│   └── tokens.py              # token 估算（CJK/ASCII 启发式，可选 tiktoken）——预算与压缩共用
│
├── agent/                   # 智能体层
│   ├── tools.py             # Tool / ToolContext / ToolRegistry（schema 生成、并发调用、超时）
│   ├── runner.py            # AgentRunner：工具循环（并发执行 → 回填 → 再推理 → 上限强制作答）
│   └── persona.py           # PersonaManager：人格 CRUD、默认人格、会话绑定、内置通用助手
│
├── conversation/            # 会话与上下文层
│   ├── service.py           # ConversationService：上下文存取/冷启动回填/发送窗口、prepare 组装、finalize 落账
│   ├── delivery.py          # Delivery：回复投递（[[转发]]/[[直发]] 标记、分段、平台合并、复述抑制）
│   ├── compactor.py         # Compactor：上下文压缩（微压缩 + 模型摘要）
│   ├── budget.py         # ContextPacker：按模型 context_length 的优先级预算装填（system 十类部件 + 历史从新到旧）
│   ├── memory.py            # MemoryStore：长期记忆（去重、bigram 相关性召回、遗忘）
│   ├── knowledge.py         # KnowledgeBase：知识库（全文分块 + 词面打分检索，零依赖）
│   └── visual.py            # 工具调用轮次可视化片段构建（Dashboard 对话页消费）
│
├── tools_builtin/           # 内置工具（每个文件暴露 register(registry, main)）
│   ├── erispulse.py         # send_message / send_dsl / call_adapter_api / call_module / 会话接管
│   ├── computer.py          # run_command / read_file / write_file / list_dir / view_image（沙箱+确认）
│   ├── code.py              # run_python / run_python_sdk（临时目录执行，确认提示带出代码）
│   ├── memory.py            # remember / recall / forget / list_memory
│   ├── knowledge.py         # knowledge_add / knowledge_search / knowledge_delete
│   ├── schedule.py          # create / list / cancel_scheduled_task
│   ├── skilltools.py        # load_skill / list_skills（技能正文注入 system）
│   ├── agent.py             # spawn_agent（子智能体，可限定工具集）
│   ├── selfconfig.py        # manage_models / manage_mcp / manage_personas / manage_config（自配置）
│   └── takumi.py            # render_image（HTML 渲染图片，依赖 Takumi 模块）
│
├── bridge/                  # 外部能力桥
│   ├── ecosystem.py         # 生态服务桥 + 扩展规范收集（工具/人格/Schema）
│   └── mcp.py               # MCP 客户端：stdio / Streamable HTTP，工具发现与调用
│
├── scheduler.py             # 定时任务：存储、轮询触发、运行记录、cron-lite 解析器、ErisPulse-Cron 托管
├── skills.py                # SkillManager：技能目录（内置+文件+自定义）、启用开关、正文注入
│
└── dashboard/
    ├── manager.py           # REST/SSE 路由（统一鉴权 guard）+ /QvQChat/view 独立页 + 会话分享页 + OpenAI 兼容端点
    ├── live.py              # LiveStream / LiveRegistry：会话级流式状态与 SSE 订阅（打断/排队）
    └── templates/           # view.html + chat/*.js + css/*.css + share.html（原生 JS，无构建步骤）
```

## 数据流

### 消息对话

```
适配器事件
  → message.on_message(priority=50)
      命令前缀放行 → 会话路由 → 触发判定
        （接管会话 ＞ 私聊 ＞ 群聊@/唤醒前缀 ＞ 成员白名单）
  → event.done() 认领 → 限流 → 短窗口合批
  → _process（按 chat_key 串行，占线时排队/打断）：
      prepare：按需压缩 → persona 解析 → system 组装
        （人格+时间+场景+早期摘要+技能/知识库注入）→ 记忆召回
      上下文（空则从 event.history 回填）→ AgentRunner.run
        工具循环：pool.chat → tool_calls 并发执行 → 回填 → 循环
      回复 → Delivery 投递（转发/直发标记、分段、复述抑制）
```

### 合成上下文（定时任务 / 主动开口 / Dashboard 对话 / RPC）

```
run_prompt(chat_key, prompt, origin)
  → 同一套 persona/system 组装与工具循环（persist=False 不落上下文）
  → 按需经 delivery.send_segments 发送到目标会话
```

定时任务到点由 scheduler 轮询触发；装有 ErisPulse-Cron 时注册到 Cron 托管（callback_data 携带任务 id，on_trigger 回调分发），Cron 卸载后自动回落到内置轮询。

### 工具的三个来源

| 来源 | 前缀 | 注册时机 |
|---|---|---|
| builtin | 无 | on_load，十个 register 函数 |
| eco | `eco_` | 启动时 `sdk.module.services()` 全量枚举；监听 `module.load`/`module.unload` 防抖热更新 |
| mcp | `mcp_` | 启动连接各 MCP 服务器，`tools/list` 发现 |

工具名冲突时自动追加序号；`disabled_tools` 支持前缀通配过滤。

### 扩展规范（外部模块即扩展）

扩展就是普通 ErisPulse 模块。第一层：`meta.services` 声明的服务自动映射为工具。第二层：模块可选实现两个约定服务，生态桥在每次刷新时经 `sdk.module.call` 逐个探测（未实现即跳过）：

| 约定服务 | 采集结果 |
|---|---|
| `qvq_schemas()` → `dict[服务名, JSON Schema]` | 覆盖签名推断的工具参数定义 |
| `qvq_personas()` → `list[{"id","name","system","opening"?,"tools"?}]` | 注册为 `ext.<模块>.<id>` 人格预设，模块卸载自动清理 |

模块无需声明这两个服务本身——它们是 QvQChat 侧的探测约定，不进入工具列表。

## 安全模型

- **路径**：`work_dirs` 白名单（空则仅当前工作目录），permissive 级解除
- **命令**：内置黑名单正则 + `blocked_patterns` 追加，命中即拒；standard 级危险命令走 `event.wait_reply` 聊天内确认，确认提示带出将执行的命令全文或代码（非聊天来源拒绝执行）
- **信任**：`trust_agent` 开启后跳过全部确认（仍审计）
- **权限**：`admins` 非空时，电脑操作/写文件/会话接管限管理员；dashboard 与 RPC 来源视为本机可信
- **审计**：computer/code 类工具全部落 `QvQChat:audit`（上限 500 条），Dashboard 审计页可查
- **执行**：命令走 shell 并有超时强杀；Python 在独立临时目录执行后清理
- **Web 鉴权**：全部 API 路由经统一 guard——装有 Dashboard 时复用其 `verify_request`（Bearer 头或 `?token=`），未装时校验自有令牌（`view_token` 配置或首次启动生成并打印日志）；`/QvQChat/view` 返回页面外壳，数据接口全部要求令牌

## 存储布局（sdk.storage KV，键全部用冒号避免点分嵌套）

| 键 | 内容 |
|---|---|
| `QvQChat:providers` | 模型池（Provider 及其模型；旧版 `QvQChat:models` 自动迁移） |
| `QvQChat:modelsdev` | models.dev 模型目录缓存（拉取远端模型列表用） |
| `QvQChat:personas` | 自定义人格 |
| `QvQChat:default_persona` | 默认人格 id |
| `QvQChat:binding:{chat_key}` | 会话人格绑定 |
| `QvQChat:conv:{chat_key}` | 对话上下文、persona 指针、早期摘要、置顶/归档标记、成员白名单 |
| `QvQChat:routes` | 跨会话路由（来源会话 → 目标会话） |
| `QvQChat:mem:{chat_key}` | 长期记忆（`global` 为全局作用域） |
| `QvQChat:kb` | 知识库条目 |
| `QvQChat:skills` | 用户自定义技能 |
| `QvQChat:tasks` | 定时任务 |
| `QvQChat:task_runs` | 定时任务运行记录（保留最近 50 条） |
| `QvQChat:usage:{date}` | 当日 token / 调用用量 |
| `QvQChat:nick:{platform}:{group_id}` | 群名片缓存 |
| `QvQChat:audit` | 操作审计 |
| `QvQChat:mcp_servers` | MCP 服务器配置 |
| `QvQChat:shares` | 会话分享记录 |
| `QvQChat:ui_defaults` | Dashboard 会话 UI 默认值 |
| `QvQChat:auth_token` | 独立访问令牌（`view_token` 未配置时生成） |

近期对话历史不重复存储：冷启动从框架会话收件箱（`event.history`）回填，之后由对话上下文承载。

## Dashboard

独立路由与侧边栏视窗同一页面：`manager.py` 经 `sdk.router` 注册 REST 路由与 `GET /QvQChat/view`（HTML 外壳，内联三模板），`register_view` 以 `iframe_url=/QvQChat/view` 挂进 Dashboard 侧边栏。前端为原生 JS，无构建步骤，内置 zh-CN / zh-TW / en / ja / ru 五语言词条，设置页按分类导航（模型/触发/安全/对话/记忆/工具/生态/MCP/任务/访问）。

鉴权：每个 API 路由包一层 guard——有 Dashboard 用它的 `verify_request`，没有则校验自有令牌（Bearer 头或 `?token=`，与 `localStorage.__ep_tk__` / `qvq_token` 对应）；令牌无效返回 401，前端弹出登录浮层。`/QvQChat/view` 外壳本身不拦，数据接口全部要求令牌。对话页直接调用 `run_prompt`。

## 运行时五语言

全部面向用户的运行时文案集中在 `texts.py`，on_load 时经 `i18n.register` 注册到框架（domain=QvQChat，卸载自动清理），覆盖 zh-CN / zh-TW / en / ja / ru；`t(key, **kw)` 按框架当前语言取词。工具层的终端输出（异常详情、进程输出等）保持英文中性文本，由模型在回复中自然转译。
