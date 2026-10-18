# QvQChat 架构文档

技术架构与模块职责说明。使用与配置说明见 [README](README.md)。

## 包结构

```
QvQChat/
├── Main.py                  # 主编排器：事件入口、触发判定、合成上下文入口、命令、审计
├── Config.py                # QvQConfig 声明式配置（BaseConfig dataclass）
├── I18n.py                  # 配置描述多语言键（五语言）
├── texts.py                 # 运行时文案注册（五语言）+ t() 助手
├── version.py               # 版本号
├── utils.py                 # 签名解析、schedule/cron 解析、进程执行、通用工具
│
├── engine/                  # 模型引擎层
│   ├── base.py              # ChatRequest / ChatResponse / ToolCall / EngineError
│   ├── openai.py            # OpenAI 兼容引擎（连续 system 合并、工具调用解析）
│   └── pool.py              # ModelPool：模型池 CRUD + 按池顺序故障转移
│
├── agent/                   # 智能体层
│   ├── tools.py             # Tool / ToolContext / ToolRegistry（schema 生成、并发调用、超时）
│   ├── runner.py            # AgentRunner：工具循环（并发执行 → 回填 → 再推理 → 上限强制作答）
│   └── persona.py           # PersonaManager：人格 CRUD、会话绑定、内置通用助手
│
├── session/                 # 会话层
│   ├── manager.py           # SessionManager：会话(窗口)/对话(上下文)两级模型
│   └── store.py             # MemoryStore：长期记忆（去重、bigram 相关性召回、遗忘）
│
├── tools_builtin/           # 内置工具（每个文件暴露 register(registry, main)）
│   ├── erispulse.py         # send_message / call_adapter_api / call_module / 接管
│   ├── computer.py          # run_command / read_file / write_file / list_dir（沙箱+确认）
│   ├── code.py              # run_python（临时目录执行，确认提示带出代码）
│   ├── memory.py            # remember / recall / forget / list_memory
│   └── schedule.py          # create / list / cancel_scheduled_task
│
├── bridge/                  # 外部能力桥
│   ├── ecosystem.py         # 生态服务桥 + 扩展规范收集（工具/提示词/人格/Schema）
│   └── mcp.py               # MCP 客户端：stdio / Streamable HTTP，工具发现与调用
│
├── scheduler.py             # 定时任务：存储、轮询触发、cron-lite 解析器、ErisPulse-Cron 托管
│
└── dashboard/
    ├── manager.py           # REST 路由（统一鉴权 guard）+ /QvQChat/view 独立页 + iframe 视窗
    └── templates/           # view.html / view.js / view.css（玻璃拟态风，五语言 UI，含登录页）
```

## 数据流

### 消息对话

```
适配器事件
  → message.on_message(priority=50)
      命令前缀放行 → 触发判定
        （接管会话 ＞ 私聊 ＞ 群聊@/唤醒前缀）
  → event.done() 认领
  → _process：
      persona 解析 → system 组装（人格+时间+扩展提示词+记忆召回）
      上下文（空则从 event.history 回填）→ AgentRunner.run
        工具循环：pool.chat → tool_calls 并发执行 → 回填 → 循环
      回复 → event.reply
```

### 合成上下文（定时任务 / 主动开口 / Dashboard 对话 / RPC）

```
run_prompt(chat_key, prompt, origin)
  → 同一套 persona + system + 工具循环
  → 按需经 SendDSL 发送到目标会话
```

定时任务到点由 scheduler 轮询触发；装有 ErisPulse-Cron 时注册到 Cron 托管（callback_data 携带任务 id，on_trigger 回调分发），Cron 卸载后自动回落到内置轮询。

### 工具的三个来源

| 来源 | 前缀 | 注册时机 |
|---|---|---|
| builtin | 无 | on_load，五个 register 函数 |
| eco | `eco_` | 启动时 `sdk.module.services()` 全量枚举；监听 `module.load`/`module.unload` 防抖热更新 |
| mcp | `mcp_` | 启动连接各 MCP 服务器，`tools/list` 发现 |

工具名冲突时自动追加序号；`disabled_tools` 支持前缀通配过滤。

### 扩展规范（外部模块即扩展）

扩展就是普通 ErisPulse 模块。第一层：`meta.services` 声明的服务自动映射为工具。第二层：模块可选实现三个约定服务，生态桥在每次刷新时经 `sdk.module.call` 逐个探测（未实现即跳过）：

| 约定服务 | 采集结果 |
|---|---|
| `qvq_schemas()` → `dict[服务名, JSON Schema]` | 覆盖签名推断的工具参数定义 |
| `qvq_prompts()` → `list[str \| {"text","priority"}]` | 注入系统提示词，按 priority 升序随每轮对话下发 |
| `qvq_personas()` → `list[{"id","name","system","tools"?}]` | 注册为 `ext.<模块>.<id>` 人格预设，模块卸载自动清理 |

模块无需声明这三个服务本身——它们是 QvQChat 侧的探测约定，不进入工具列表。

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
| `QvQChat:models` | 模型池 |
| `QvQChat:personas` | 自定义人格 |
| `QvQChat:binding:{chat_key}` | 会话人格绑定 |
| `QvQChat:conv:{chat_key}` | 对话上下文与 persona 指针 |
| `QvQChat:mem:{chat_key}` | 长期记忆（`global` 为全局作用域） |
| `QvQChat:tasks` | 定时任务 |
| `QvQChat:audit` | 操作审计 |
| `QvQChat:auth_token` | 独立访问令牌（`view_token` 未配置时生成） |

近期对话历史不重复存储：冷启动从框架会话收件箱（`event.history`）回填，之后由对话上下文承载。

## Dashboard

独立路由与侧边栏视窗同一页面：`manager.py` 经 `sdk.router` 注册 REST 路由与 `GET /QvQChat/view`（HTML 外壳，内联三模板），`register_view` 以 `iframe_url=/QvQChat/view` 挂进 Dashboard 侧边栏。前端为原生 JS，无构建步骤，内置 zh-CN / zh-TW / en / ja / ru 五语言词条，设置页按分类导航（模型/触发/安全/对话/记忆/工具/生态/MCP/任务/访问）。

鉴权：每个 API 路由包一层 guard——有 Dashboard 用它的 `verify_request`，没有则校验自有令牌（Bearer 头或 `?token=`，与 `localStorage.__ep_tk__` / `qvq_token` 对应）；令牌无效返回 401，前端弹出登录浮层。`/QvQChat/view` 外壳本身不拦，数据接口全部要求令牌。对话页直接调用 `run_prompt`。

## 运行时五语言

全部面向用户的运行时文案集中在 `texts.py`，on_load 时经 `i18n.register` 注册到框架（domain=QvQChat，卸载自动清理），覆盖 zh-CN / zh-TW / en / ja / ru；`t(key, **kw)` 按框架当前语言取词。工具层的终端输出（异常详情、进程输出等）保持英文中性文本，由模型在回复中自然转译。
