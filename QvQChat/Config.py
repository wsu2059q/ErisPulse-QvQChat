from __future__ import annotations

from dataclasses import dataclass, field, fields as dc_fields

from ErisPulse.Core.Bases import BaseConfig

from . import texts

# 设置分组注册表：组 id → 展示顺序（替代"组内首字段 order 当组序"的错误语义）。
# 前端组标签键约定：group_{id}（core.js i18n）。
GROUP_META: dict[str, dict] = {
    "model": {"order": 1},
    "trigger": {"order": 2},
    "chat": {"order": 3},
    "tools": {"order": 4},
    "mcp": {"order": 5},
    "eco": {"order": 6},
    "memory": {"order": 7},
    "kb": {"order": 8},
    "skills": {"order": 9},
    "task": {"order": 10},
    "usage": {"order": 11},
    "security": {"order": 12},
    "participation": {"order": 13},
    "access": {"order": 14},
}


def _desc(
    key: str,
    text: str,
    group: str,
    order: int,
    widget: str = "text",
    options: list | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    step: float | None = None,
    placeholder: str = "",
    secret: bool = False,
    dangerous: bool = False,
    items: str = "",
) -> dict:
    ui: dict = {"widget": widget, "group": group, "order": order}
    if options is not None:
        ui["options"] = options
    if minimum is not None:
        ui["min"] = minimum
    if maximum is not None:
        ui["max"] = maximum
    if step is not None:
        ui["step"] = step
    if placeholder:
        ui["placeholder"] = placeholder
    if secret:
        ui["secret"] = True
    if dangerous:
        ui["dangerous"] = True
    if items:
# list 字段的已知枚举来源（"tools" / "skills"）：前端渲染 checkbox 多选
        ui["items"] = items
    return {"description": {"i18n": f"QvQChat.{key}", "default": text}, "ui": ui}


def annotation_kind(annotation) -> str:
    """把 dataclass 字段注解归为 bool/int/float/str/list/other 六类。

    `from __future__ import annotations` 下 f.type 是字符串，直接按文本判断。
    """
    text = str(annotation).strip().lower()
    if text.startswith("list") or text.startswith("tuple"):
        return "list"
    if "bool" in text:
        return "bool"
    if "float" in text:
        return "float"
    if "int" in text:
        return "int"
    if "str" in text:
        return "str"
    if "dict" in text:
        return "dict"
    return "other"


@dataclass
class QvQConfig(BaseConfig):

    default_model: str = field(default="", metadata=_desc("default_model", "默认模型（模型池 id），留空使用池中第一个", "model", 1, placeholder="provider:model"))
    temperature: float = field(default=0.7, metadata=_desc("temperature", "默认采样温度", "model", 2, "slider", minimum=0, maximum=2, step=0.1))
    max_tokens: int = field(default=0, metadata=_desc("max_tokens", "单次回复的最大生成 token 数，0 = 不限制（跟随模型上限）。长任务建议保持 0，截断会导致规划文本泄漏。", "model", 3, "number"))
    model_failover: bool = field(default=True, metadata=_desc("model_failover", "模型调用失败时按池顺序切换备用模型", "model", 4, "switch"))
    token_estimator: str = field(default="", metadata=_desc("token_estimator", "token 估算器：留空用启发式（中文≈1字1token、其余≈4字符1token）；tiktoken 按精确编码计数（需自行安装 tiktoken 依赖，未安装自动回退启发式）", "model", 5, "select", ["", "tiktoken"]))
    task_models: dict = field(default_factory=dict, metadata=_desc("task_models", "按任务类别指定模型（JSON，如 {\"compact\": \"provider:model\"}）；未命中时走能力过滤/成本偏好/池序", "model", 6, "json"))
    routing_enabled: bool = field(default=False, metadata=_desc("routing_enabled", "难度感知模型路由（实验性，默认关闭）：按本轮首条用户消息的难度自动选择便宜/均衡/高质量模型（寒暄短句走便宜、含代码或长分析走高质量）；仅对未显式指定模型/偏好/能力过滤的对话生效", "model", 7, "switch"))
    routing_ttl: int = field(default=300, metadata=_desc("routing_ttl", "难度分级结果的会话内缓存秒数：同会话短时间连续消息复用上次分级（0 表示不缓存，每条独立分级）", "model", 8, "number"))

    reply_private: bool = field(default=True, metadata=_desc("reply_private", "私聊消息触发智能体", "trigger", 1, "switch"))
    reply_at: bool = field(default=True, metadata=_desc("reply_at", "群聊被 @ 时触发智能体", "trigger", 2, "switch"))
    wake_prefixes: list[str] = field(default_factory=list, metadata=_desc("wake_prefixes", "群聊文本唤醒前缀", "trigger", 3, "list"))
    command_prefixes: list[str] = field(default_factory=lambda: ["#", "/"], metadata=_desc("command_prefixes", "命令消息前缀（命中即放行不处理）", "trigger", 4, "list"))

    admins: list[str] = field(default_factory=list, metadata=_desc("admins", "管理员用户 id 列表；为空时聊天侧无人拥有管理员权限（Dashboard/本地来源除外）", "security", 1, "list", dangerous=True))
    admin_tools: list[str] = field(default_factory=list, metadata=_desc("admin_tools", "强制仅管理员的工具覆盖名单（支持 eco_*/mcp_* 前缀通配）：写在这里的工具即便本身标记为 safe 也仅限管理员", "security", 2, "list"))
    safe_tools: list[str] = field(default_factory=list, metadata=_desc("safe_tools", "在基础安全集之外追加给所有人的工具（支持前缀通配，如让所有人可用生图扩展）", "security", 3, "list"))
    safe_commands: list[str] = field(default_factory=lambda: ["ping *"], metadata=_desc("safe_commands", "非管理员也允许执行的简单命令（通配匹配，如 ping *）", "security", 4, "list"))
    security_level: str = field(default="standard", metadata=_desc("security_level", "电脑操作安全级别：strict 只读+确认 / standard 白名单+危险确认 / permissive 放开但审计", "security", 5, "select", ["strict", "standard", "permissive"], dangerous=True))
    trust_agent: bool = field(default=False, metadata=_desc("trust_agent", "完全信任智能体：跳过所有危险操作确认（仍审计）", "security", 6, "switch", dangerous=True))
    work_dirs: list[str] = field(default_factory=list, metadata=_desc("work_dirs", "文件访问白名单目录，留空仅允许当前工作目录", "security", 7, "list", dangerous=True))
    command_timeout: int = field(default=60, metadata=_desc("command_timeout", "单条命令执行超时（秒）", "security", 8, "number"))
    blocked_patterns: list[str] = field(default_factory=list, metadata=_desc("blocked_patterns", "追加的命令黑名单正则", "security", 9, "list"))
    confirm_timeout: int = field(default=60, metadata=_desc("confirm_timeout", "危险操作聊天内确认超时（秒）", "security", 10, "number"))
    sensitive_paths: list[str] = field(default_factory=lambda: ["config", ".env", "*.key", "*.pem", "*.db", "*.sqlite*"], metadata=_desc("sensitive_paths", "敏感文件/目录匹配（非管理员不可读，支持通配）", "security", 11, "list", dangerous=True))
    self_config: bool = field(default=True, metadata=_desc("self_config", "允许智能体自我配置：注册 manage_models / manage_mcp / manage_config 工具（仅管理员可用），配套内置技能教它怎么用；关闭即全部下线", "security", 12, "switch", dangerous=True))

# chat 组 31 字段，order 1..31 无重复（语义分块见前端 settings 小节标题；24-31 为 A2 交接的上下文工程/事实键）
    context_limit: int = field(default=30, metadata=_desc("context_limit", "每会话携带对话上下文条数上限", "chat", 1, "number"))
    history_seed: int = field(default=20, metadata=_desc("history_seed", "冷启动时从会话收件箱回填的历史条数", "chat", 2, "number"))
    context_strategy: str = field(default="auto", metadata=_desc("context_strategy", "上下文压缩策略：auto 超限旧轮摘要为要点 / truncate 直接丢弃旧轮 / off 只做工具输出瘦身不压缩历史", "chat", 3, "select", ["auto", "truncate", "off"]))
    keep_ratio: float = field(default=0.25, metadata=_desc("keep_ratio", "压缩时保留最近对话的比例（0.1-0.5），其余轮次被摘要或丢弃", "chat", 4, "slider", minimum=0.1, maximum=0.5, step=0.05))
    compact_every_turns: int = field(default=10, metadata=_desc("compact_every_turns", "预防性压缩：每 N 轮对话主动压缩一次（0 关闭，仅超阈值时才压缩）", "chat", 5, "number"))
    compact_model: str = field(default="", metadata=_desc("compact_model", "压缩摘要使用的模型（模型池 id），留空用当前默认模型", "chat", 6, "text", placeholder="provider:model"))
    max_context_turns: int = field(default=0, metadata=_desc("max_context_turns", "每请求最多携带最近 N 轮对话（发送级裁剪，不修改存储历史），0 不限", "chat", 7, "number"))
    tool_output_keep: int = field(default=300, metadata=_desc("tool_output_keep", "历史中旧工具输出的保留字符数，超出截断瘦身（0 关闭）", "chat", 8, "number"))
    context_compress_tokens: int = field(default=128000, metadata=_desc("context_compress_tokens", "上下文压缩阈值（估算 token）：估算口径为中文≈1字1token（约为旧口径\"字符数/2\"的 2 倍），超过时自动把旧对话压缩为摘要后再请求，0 关闭。默认 128000 约对应 200k+ 上下文模型；小上下文模型可调低", "chat", 9, "number"))
    forward_platforms: list[str] = field(default_factory=lambda: ["*"], metadata=_desc("forward_platforms", "允许合并转发的平台（支持通配 * 与前缀，如 onebot*）；* 表示全部", "chat", 10, "list"))
    no_forward_platforms: list[str] = field(default_factory=list, metadata=_desc("no_forward_platforms", "禁止合并转发的平台黑名单（命中即使支持也不合并，优先级高于白名单）", "chat", 11, "list"))
    forward_min_messages: int = field(default=3, metadata=_desc("forward_min_messages", "合并转发的最小 AI 发言段数：本次运行中 AI 的回复达到该段数才打包合并卡（0 关闭自动合并，仍可用 [[转发]] 强制）", "chat", 12, "number"))
    forward_threshold: int = field(default=600, metadata=_desc("forward_threshold", "send_message 工具发送的文本超过该字符数自动打包合并转发（0 关闭）；回复是否打包不看长度，看 AI 发言段数", "chat", 13, "number"))
    reply_split: str = field(default="paragraph", metadata=_desc("reply_split", "纯对话分段回复：paragraph 按空行/段落切段连发模拟真人节奏 / off 单条发送；工具任务始终合并转发不分段", "chat", 14, "select", ["paragraph", "off"]))
    split_min_length: int = field(default=120, metadata=_desc("split_min_length", "分段回复的最小触发长度（字符），低于此值单条发送", "chat", 15, "number"))
    split_delay: float = field(default=1.2, metadata=_desc("split_delay", "分段回复每段之间的间隔秒数", "chat", 16, "number"))
    tool_notice_mode: str = field(default="brief", metadata=_desc("tool_notice_mode", "平台侧长任务播报：off 静默 / brief 发送 AI 的开场与阶段性发言（默认，不发工具明细）/ all 另加每轮工具明细", "chat", 17, "select", ["off", "brief", "all"]))
    interrupt_mode: str = field(default="queue", metadata=_desc("interrupt_mode", "任务运行中来新消息的处理：queue 新消息排队、当前任务后台继续（推荐）/ interrupt 取消当前任务、新消息带中断上下文重新开始", "chat", 18, "select", ["queue", "interrupt"]))
    aggregate_window: float = field(default=5.0, metadata=_desc("aggregate_window", "消息聚合窗口（秒）：窗口内的多条消息合并为一次请求，0 关闭", "chat", 19, "number"))
    extra_prompts: list[str] = field(default_factory=list, metadata=_desc("extra_prompts", "自定义注入提示词（每行一条，追加到系统提示词末尾）", "chat", 20, "lines"))
    owner_only: bool = field(default=False, metadata=_desc("owner_only", "仅框架主人可用：开启后非管理员用户的消息不触发智能体（Dashboard 不受限制）", "chat", 21, "switch"))
    user_rate_limit: int = field(default=0, metadata=_desc("user_rate_limit", "群聊每用户每分钟触发上限（滑动窗口，0 不限，管理员豁免），超限静默丢弃并至多提示一次", "chat", 22, "number"))
    group_isolation: bool = field(default=False, metadata=_desc("group_isolation", "群聊按成员隔离会话：每个成员独立上下文/人格/记忆，默认关闭", "chat", 23, "switch"))
    context_budget_mode: str = field(default="off", metadata=_desc("context_budget_mode", "上下文预算装填：auto 按选中模型的 context_length 装填 / tokens 按下方默认长度装填 / off 关闭（默认，功能灰度中）", "chat", 24, "select", ["auto", "tokens", "off"]))
    default_context_length: int = field(default=0, metadata=_desc("default_context_length", "预算模式=tokens 时的默认上下文长度（模型未上报 context_length 时兜底），0 不启用兜底", "chat", 25, "number"))
    context_reserve: float = field(default=0.85, metadata=_desc("context_reserve", "上下文预算保留比例：可用预算 = context_length × 该比例（预留给输出与安全边际）", "chat", 26, "number", minimum=0.5, maximum=0.95))
    summary_cap: int = field(default=1500, metadata=_desc("summary_cap", "每会话历史摘要的字符总量上限，超过时触发合并压缩", "chat", 27, "number"))
    compact_transcript_chars: int = field(default=400, metadata=_desc("compact_transcript_chars", "压缩时每条历史消息进入转写的最大字符数（0 不截断）", "chat", 28, "number"))
    compact_input_chars: int = field(default=12000, metadata=_desc("compact_input_chars", "压缩请求送入模型的转写最大字符数（0 不截断）", "chat", 29, "number"))
    facts_extract: bool = field(default=True, metadata=_desc("facts_extract", "对话中自动抽取长期事实要点（用户偏好/约定等），注入后续会话", "chat", 30, "switch"))
    facts_max: int = field(default=100, metadata=_desc("facts_max", "每会话保留的事实要点条数上限（超限保最新）", "chat", 31, "number"))

# 投递拟人化（rhythm.py / delivery.py）
    sentence_split: bool = field(default=False, metadata=_desc("sentence_split", "段内超长时按句切分（拟人节奏，关闭则仅按段落切分）", "chat", 32, "switch"))
    sentence_max: int = field(default=80, metadata=_desc("sentence_max", "句级切分时每段打包的字数上限", "chat", 33, "number"))
    typing_speed: int = field(default=25, metadata=_desc("typing_speed", "拟人打字速度（字/秒），决定段间延迟时长", "chat", 34, "number"))
    split_jitter: float = field(default=0.35, metadata=_desc("split_jitter", "段间延迟随机抖动幅度（0-1，模拟输入停顿）", "chat", 35, "number", minimum=0, maximum=1))
    min_delay: float = field(default=0.5, metadata=_desc("min_delay", "单段发送延迟下限（秒）", "chat", 36, "number"))
    max_delay: float = field(default=6.0, metadata=_desc("max_delay", "单段发送延迟上限（秒）", "chat", 37, "number"))
    total_delay_cap: int = field(default=20, metadata=_desc("total_delay_cap", "整条回复分段总延迟上限（秒），超出按比例压缩", "chat", 38, "number"))
    max_parts: int = field(default=6, metadata=_desc("max_parts", "分段发送条数上限（超出的段落合并）", "chat", 39, "number"))
    delivery_profiles: dict = field(default_factory=dict, metadata=_desc("delivery_profiles", "按平台覆盖投递参数（如 {\"onebot11\": {\"max_parts\": 3}}，支持前缀通配）", "chat", 40, "json"))
    forward_structure_aware: bool = field(default=False, metadata=_desc("forward_structure_aware", "结构感知合并转发：代码块/表格/列表占比达标的回复才打包转发，纯寒暄多段直发", "chat", 41, "switch"))
    send_retry: int = field(default=1, metadata=_desc("send_retry", "发送失败（超时/网络类错误）重试次数", "chat", 42, "number"))
    retry_delay: float = field(default=1.5, metadata=_desc("retry_delay", "重试退避基数（秒），指数递增", "chat", 43, "number"))
    pending_send_max: int = field(default=10, metadata=_desc("pending_send_max", "发送失败待重发队列每会话上限（FIFO 淘汰）", "chat", 44, "number"))

# 人格开场白
    opening_enabled: bool = field(default=True, metadata=_desc("opening_enabled", "新会话首次接触时自动发送人格开场白（随机一条；Dashboard 平台不触发）", "chat", 45, "switch"))
    opening_on_seed: bool = field(default=False, metadata=_desc("opening_on_seed", "冷启动历史回填发生时也发送开场白（默认关闭：回填说明已有过对话，不再打招呼）", "chat", 46, "switch"))
    opening_on_reset: bool = field(default=False, metadata=_desc("opening_on_reset", "/qvq reset 重置会话时同时清除开场白已发标记，下次对话重新发送开场白", "chat", 47, "switch"))
    opening_max_len: int = field(default=200, metadata=_desc("opening_max_len", "开场白单条最大字符数（超出截断）", "chat", 48, "number"))
    reply_narrate: bool = field(default=False, metadata=_desc("reply_narrate", "边做边说：工具任务的每一步先说一句要做什幺、拿到结果简短汇报、结束给简短结论（每句单独发到群里，像真人工作播报）", "chat", 49, "switch"))
    notify_on_passive_failure: bool = field(default=False, metadata=_desc("notify_on_passive_failure", "被动触发的任务（如插件插话）失败时也在群里回复错误详情；默认关闭只记日志，避免错误刷屏", "chat", 53, "switch"))

# 实例重启恢复（chat/recovery.py）
    recovery_enabled: bool = field(default=True, metadata=_desc("recovery_enabled", "实例重启后自动恢复被中断的回复", "chat", 50, "switch"))
    recovery_min_age: int = field(default=90, metadata=_desc("recovery_min_age", "标记距今超过该秒数才恢复（防误判正常在跑）", "chat", 51, "number"))
    replay_on_boot: bool = field(default=True, metadata=_desc("replay_on_boot", "启动时重放发送失败队列", "chat", 52, "switch"))

    memory_max: int = field(default=200, metadata=_desc("memory_max", "每会话长期记忆条数上限", "memory", 1, "number"))
    memory_recall: int = field(default=6, metadata=_desc("memory_recall", "每次对话注入的相关记忆条数上限", "memory", 2, "number"))

# 跨会话用户画像（conversation/profile.py：固化循环 + 注入）
    profile_enabled: bool = field(default=True, metadata=_desc("profile_enabled", "跨会话用户画像：定时聚合该用户各会话 facts/长期记忆，提炼为 traits/preferences 并注入系统提示", "memory", 3, "switch"))
    profile_consolidate_hours: int = field(default=6, metadata=_desc("profile_consolidate_hours", "画像固化定时任务间隔（小时），0 关闭定时固化", "memory", 4, "number"))
    profile_inject: int = field(default=8, metadata=_desc("profile_inject", "注入系统提示的画像条数上限", "memory", 5, "number"))
    profile_max: int = field(default=20, metadata=_desc("profile_max", "画像每类（特点/偏好/事实）条数上限，超限保最新", "memory", 6, "number"))
    profile_decay_days: int = field(default=30, metadata=_desc("profile_decay_days", "画像特点衰减天数：超过该天数未被任何会话新事实强化的条目淘汰（0 关闭衰减）", "memory", 7, "number"))

    tool_timeout: int = field(default=120, metadata=_desc("tool_timeout", "单次工具调用超时（秒）", "tools", 1, "number"))
    max_tool_rounds: int = field(default=50, metadata=_desc("max_tool_rounds", "工具循环最大轮数（硬上限；剩 3 轮时自动提醒模型收敛，不会中途强制收尾）", "tools", 2, "number"))
    max_tool_calls: int = field(default=150, metadata=_desc("max_tool_calls", "单次对话工具调用总次数上限", "tools", 3, "number"))
    disabled_tools: list[str] = field(default_factory=list, metadata=_desc("disabled_tools", "禁用的工具名列表（支持 eco_/mcp_/插件名. 前缀通配）", "tools", 4, "list", items="tools"))
    tools_fallback: str = field(default="strip", metadata=_desc("tools_fallback", "池中无支持工具调用的模型时的降级：strip 去掉工具并在提示词中说明（默认，保证必答）/ strict 直接报错 / off 照常携带工具", "tools", 5, "select", ["strip", "strict", "off"]))
    tool_self_heal: bool = field(default=True, metadata=_desc("tool_self_heal", "工具自愈：同一工具连续两次调用失败时向模型注入一条修正提示（含错误摘要），让它自行调整参数重试；调用成功即重置计数", "tools", 6, "switch"))
    skill_induct: bool = field(default=True, metadata=_desc("skill_induct", "技能自动习得：注册 save_skill 工具并在系统提示中说明——用户要求\"记住这个做法\"时把多步任务的做法保存为可复用技能", "tools", 7, "switch"))

    eco_exclude: list[str] = field(default_factory=lambda: ["QvQChat"], metadata=_desc("eco_exclude", "不桥接服务目录的模块名单", "eco", 1, "list"))
    eco_include: list[str] = field(default_factory=list, metadata=_desc("eco_include", "仅桥接这些模块的服务，留空表示全部", "eco", 2, "list"))

    mcp_timeout: int = field(default=30, metadata=_desc("mcp_timeout", "MCP 请求超时（秒）", "mcp", 1, "number"))

    task_check_interval: int = field(default=20, metadata=_desc("task_check_interval", "任务轮询间隔（秒）", "task", 1, "number"))
    task_use_cron_module: bool = field(default=True, metadata=_desc("task_use_cron_module", "装有 ErisPulse-Cron 时把 cron 任务交给它托管", "task", 2, "switch"))

    view_token: str = field(default="", metadata=_desc("view_token", "独立访问令牌，留空首次启动自动生成", "access", 1, secret=True))

    daily_token_limit: int = field(default=0, metadata=_desc("daily_token_limit", "单日模型 token 总量限额（0 不限），超出后非管理员对话被暂停，次日重置", "usage", 1, "number"))
    usage_retention_days: int = field(default=14, metadata=_desc("usage_retention_days", "用量统计数据保留天数", "usage", 2, "number"))

    kb_auto_inject: bool = field(default=True, metadata=_desc("kb_auto_inject", "对话时自动检索知识库相关片段注入系统提示", "kb", 1, "switch"))
    kb_top_k: int = field(default=2, metadata=_desc("kb_top_k", "自动注入的知识库片段数上限", "kb", 2, "number"))
    kb_chunk_size: int = field(default=400, metadata=_desc("kb_chunk_size", "知识库条目检索分块的目标字符数", "kb", 3, "number"))
    kb_chunk_overlap: int = field(default=50, metadata=_desc("kb_chunk_overlap", "知识库相邻分块的重叠字符数", "kb", 4, "number"))
# Lorebook 世界书（触发式注入）+ 语义检索（KB 侧向量层）
    kb_triggers_enabled: bool = field(default=True, metadata=_desc("kb_triggers_enabled", "世界书触发注入：条目配置 triggers 关键词后，最近对话命中即注入该条目（SillyTavern World Info 模式，与检索注入并存）", "kb", 5, "switch"))
    kb_trigger_window: int = field(default=6, metadata=_desc("kb_trigger_window", "世界书触发扫描的最近消息条数（含本次消息）", "kb", 6, "number"))
    kb_cooldown_min: int = field(default=30, metadata=_desc("kb_cooldown_min", "世界书条目新添加时的默认触发冷却分钟数（冷却期内不再注入，条目级 cooldown_min 可覆盖；0 不冷却）", "kb", 7, "number"))
    embedding_enabled: bool = field(default=False, metadata=_desc("embedding_enabled", "知识库语义检索：向量层可用时按余弦相似度检索（任何环节不可用自动回退词面打分，零配置行为不变）", "kb", 8, "switch"))
    embedding_model: str = field(default="", metadata=_desc("embedding_model", "向量模型名字符串（配合 embedding_provider，如 text-embedding-3-small；留空用 provider 内 model）", "kb", 9, "text"))
    embedding_provider: dict = field(default_factory=dict, metadata=_desc("embedding_provider", "embedding 服务提供者（JSON：{\"base_url\": \"https://…/v1\", \"api_key\": \"sk-…\", \"model\": \"text-embedding-3-small\"}，OpenAI 兼容 /v1/embeddings；api_key 为敏感信息）", "kb", 10, "json", secret=True))
    skills_dir: str = field(default="data/QvQChat/skills", metadata=_desc("skills_dir", "技能目录（每个 .md 文件一个技能，frontmatter 含 name/description）", "skills", 1))
    skills_disabled: list[str] = field(default_factory=list, metadata=_desc("skills_disabled", "禁用的技能名列表", "skills", 2, "list", items="skills"))

# 群聊参与决策（插件化扩展点；默认关闭：装插件≠放行）
    participation_enabled: bool = field(default=False, metadata=_desc("participation_enabled", "群聊参与决策：未被 @/前缀命中时问询生态插件的 qvq_decision 服务判断是否插话（默认关闭，需自行开启）", "participation", 1, "switch", dangerous=True))
    participation_groups: list[str] = field(default_factory=list, metadata=_desc("participation_groups", "参与决策生效的群白名单（群号或 platform:group:gid，支持通配），留空表示全部群", "participation", 2, "list"))
    participation_groups_exclude: list[str] = field(default_factory=list, metadata=_desc("participation_groups_exclude", "参与决策排除的群黑名单，优先级高于白名单", "participation", 3, "list"))
    participation_hourly_limit: int = field(default=8, metadata=_desc("participation_hourly_limit", "每群每小时机器人主动发言上限（插话+主动开口，0 不限），超出后本小时静默", "participation", 4, "number"))
    participation_cooldown_seconds: int = field(default=300, metadata=_desc("participation_cooldown_seconds", "同群两次发言的最小间隔秒数（0 不限），冷却期内不再插话", "participation", 5, "number"))
    participation_proactive_daily_limit: int = field(default=3, metadata=_desc("participation_proactive_daily_limit", "全局每日主动发言（speak 服务）上限（0 不限），插话不计入", "participation", 6, "number"))

# ===== 类型校验 seam：三个写入方（dashboard config_set / AI 工具 manage_config / 导入回灌）共用 =====

    @classmethod
    def field_map(cls) -> dict:
        cached = cls.__dict__.get("_FIELD_MAP")
        if cached is None:
            cached = {f.name: f for f in dc_fields(cls)}
            cls._FIELD_MAP = cached
        return cached

    @classmethod
    def type_of(cls, key: str) -> str:
        f = cls.field_map().get(key)
        return annotation_kind(f.type) if f is not None else "other"

    @classmethod
    def groups(cls) -> list[dict]:
        """设置分组表（含兜底：字段声明了 GROUP_META 外的组时按 order=99 追加）。"""
        known = {g: meta.get("order", 99) for g, meta in GROUP_META.items()}
        for f in dc_fields(cls):
            g = str(((f.metadata or {}).get("ui") or {}).get("group") or "other")
            known.setdefault(g, 99)
        return [{"id": g, "order": o} for g, o in sorted(known.items(), key=lambda kv: (kv[1], kv[0]))]

    @classmethod
    def coerce(cls, key: str, value):
        """按字段注解抝合并校验一个配置值。

        返回 ``(ok, coerced, err)``：ok=False 时 err 为可直接回显的原因，值不会被写入。
        规则：bool 仅收 bool；数字收数字与数字字符串（空串报错）；int 拒绝非整数值；
        list 收列表/元组（逐项转 str 去空）或多行字符串（按行拆分）；select 校验成员；
        声明了 min/max 的数字字段做区间校验。
        """
        f = cls.field_map().get(key)
        if f is None:
            return False, None, texts.t("config_err_unknown_key", name=key)
        ui = (f.metadata or {}).get("ui") or {}
        kind = annotation_kind(f.type)

        if kind == "bool":
            if isinstance(value, bool):
                return True, value, None
            return False, None, texts.t("config_err_bool", name=key)

        if kind in ("int", "float"):
            if isinstance(value, bool) or value is None:
                return False, None, texts.t("config_err_number", name=key)
            if isinstance(value, str):
                text = value.strip()
                if not text:
# 存量 bug 止血：清空数字字段不再落 ""（运行时 int("") 会崩）
                    return False, None, texts.t("config_err_number", name=key)
                try:
                    value = float(text)
                except ValueError:
                    return False, None, texts.t("config_err_number", name=key)
            if not isinstance(value, (int, float)):
                return False, None, texts.t("config_err_number", name=key)
            if kind == "int":
                if isinstance(value, float) and not value.is_integer():
                    return False, None, texts.t("config_err_int", name=key)
                coerced = int(value)
            else:
                coerced = float(value)
            lo, hi = ui.get("min"), ui.get("max")
            if (lo is not None and coerced < lo) or (hi is not None and coerced > hi):
                return False, None, texts.t("config_err_range", name=key, min=lo, max=hi)
            return True, coerced, None

        if kind == "list":
            if value is None:
                return True, [], None
            if isinstance(value, str):
                raw_items = value.split("\n")
            elif isinstance(value, (list, tuple)):
                raw_items = list(value)
            else:
                return False, None, texts.t("config_err_list", name=key)
            coerced = []
            for item in raw_items:
                text = str(item).strip()
                if text:
                    coerced.append(text)
            return True, coerced, None

        if kind == "dict":
            if isinstance(value, dict):
                return True, value, None
            return False, None, texts.t("config_err_dict", name=key)

# str（含 select：校验成员）
        if value is None:
            value = ""
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        options = ui.get("options")
        if options and value not in options:
            return False, None, texts.t("config_err_option", name=key, options=", ".join(str(o) for o in options))
        return True, value, None
