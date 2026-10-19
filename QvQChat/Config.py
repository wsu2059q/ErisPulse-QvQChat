from __future__ import annotations

from dataclasses import dataclass, field

from ErisPulse.Core.Bases import BaseConfig


def _desc(key: str, text: str, group: str, order: int, widget: str = "text", options: list | None = None) -> dict:
    ui: dict = {"widget": widget, "group": group, "order": order}
    if options is not None:
        ui["options"] = options
    return {"description": {"i18n": f"QvQChat.{key}", "default": text}, "ui": ui}


@dataclass
class QvQConfig(BaseConfig):

    default_model: str = field(default="", metadata=_desc("default_model", "默认模型（模型池 id），留空使用池中第一个", "model", 1))
    temperature: float = field(default=0.7, metadata=_desc("temperature", "默认采样温度", "model", 2, "number"))
    max_tokens: int = field(default=0, metadata=_desc("max_tokens", "单次回复的最大生成 token 数，0 = 不限制（跟随模型上限）。长任务建议保持 0，截断会导致规划文本泄漏。", "model", 3, "number"))
    model_failover: bool = field(default=True, metadata=_desc("model_failover", "模型调用失败时按池顺序切换备用模型", "model", 4, "switch"))

    reply_private: bool = field(default=True, metadata=_desc("reply_private", "私聊消息触发智能体", "trigger", 1, "switch"))
    reply_at: bool = field(default=True, metadata=_desc("reply_at", "群聊被 @ 时触发智能体", "trigger", 2, "switch"))
    wake_prefixes: list[str] = field(default_factory=list, metadata=_desc("wake_prefixes", "群聊文本唤醒前缀", "trigger", 3, "list"))
    command_prefixes: list[str] = field(default_factory=lambda: ["#", "/"], metadata=_desc("command_prefixes", "命令消息前缀（命中即放行不处理）", "trigger", 4, "list"))

    admins: list[str] = field(default_factory=list, metadata=_desc("admins", "管理员用户 id 列表；为空时聊天侧无人拥有管理员权限（Dashboard/本地来源除外）", "security", 1, "list"))
    admin_tools: list[str] = field(default_factory=lambda: ["run_command", "run_python", "write_file", "call_adapter_api", "call_module", "takeover_session", "release_takeover", "eco_*", "mcp_*"], metadata=_desc("admin_tools", "仅管理员可用的工具（支持 eco_*/mcp_* 前缀通配）", "security", 2, "list"))
    safe_tools: list[str] = field(default_factory=list, metadata=_desc("safe_tools", "在基础安全集之外追加给所有人的工具（支持前缀通配，如让所有人可用生图扩展）", "security", 3, "list"))
    safe_commands: list[str] = field(default_factory=lambda: ["ping *"], metadata=_desc("safe_commands", "非管理员也允许执行的简单命令（通配匹配，如 ping *）", "security", 4, "list"))
    security_level: str = field(default="standard", metadata=_desc("security_level", "电脑操作安全级别：strict 只读+确认 / standard 白名单+危险确认 / permissive 放开但审计", "security", 5, "select", ["strict", "standard", "permissive"]))
    trust_agent: bool = field(default=False, metadata=_desc("trust_agent", "完全信任智能体：跳过所有危险操作确认（仍审计）", "security", 6, "switch"))
    work_dirs: list[str] = field(default_factory=list, metadata=_desc("work_dirs", "文件访问白名单目录，留空仅允许当前工作目录", "security", 7, "list"))
    command_timeout: int = field(default=60, metadata=_desc("command_timeout", "单条命令执行超时（秒）", "security", 8, "number"))
    blocked_patterns: list[str] = field(default_factory=list, metadata=_desc("blocked_patterns", "追加的命令黑名单正则", "security", 9, "list"))
    confirm_timeout: int = field(default=60, metadata=_desc("confirm_timeout", "危险操作聊天内确认超时（秒）", "security", 10, "number"))
    sensitive_paths: list[str] = field(default_factory=lambda: ["config", ".env", "*.key", "*.pem", "*.db", "*.sqlite*"], metadata=_desc("sensitive_paths", "敏感文件/目录匹配（非管理员不可读，支持通配）", "security", 11, "list"))
    self_config: bool = field(default=True, metadata=_desc("self_config", "允许智能体自我配置：注册 manage_models / manage_mcp / manage_config 工具（仅管理员可用），配套内置技能教它怎么用；关闭即全部下线", "security", 12, "switch"))

    context_limit: int = field(default=30, metadata=_desc("context_limit", "每会话携带对话上下文条数上限", "chat", 1, "number"))
    history_seed: int = field(default=20, metadata=_desc("history_seed", "冷启动时从会话收件箱回填的历史条数", "chat", 2, "number"))
    forward_enabled: bool = field(default=True, metadata=_desc("forward_enabled", "工具任务的回复/投递自动转为合并转发消息（需适配器实现 MergeForward）；纯对话一律普通发送", "chat", 3, "switch"))
    forward_threshold: int = field(default=600, metadata=_desc("forward_threshold", "send_message 工具发送的文本超过该字符数自动打包合并转发（0 关闭）；回复是否打包不看长度，看是否为工具任务", "chat", 4, "number"))
    context_summary: bool = field(default=True, metadata=_desc("context_summary", "上下文超限被裁剪时自动摘要旧对话（需模型可用）", "chat", 5, "switch"))
    context_compress_tokens: int = field(default=128000, metadata=_desc("context_compress_tokens", "上下文压缩阈值（估算 token，约为字符数/2，偏保守）：超过时自动把旧对话压缩为摘要后再请求，0 关闭。默认 128000（估算口径偏保守，实际约对应 200k+ 上下文）；小上下文模型可调低", "chat", 5, "number"))
    tool_notice_mode: str = field(default="brief", metadata=_desc("tool_notice_mode", "平台侧长任务播报：off 静默 / brief 发送 AI 的开场与阶段性发言（默认，不发工具明细）/ all 另加每轮工具明细", "chat", 6, "select", ["off", "brief", "all"]))
    aggregate_window: float = field(default=5.0, metadata=_desc("aggregate_window", "消息聚合窗口（秒）：窗口内的多条消息合并为一次请求，0 关闭", "chat", 7, "number"))
    extra_prompts: list[str] = field(default_factory=list, metadata=_desc("extra_prompts", "自定义注入提示词（每行一条，追加到系统提示词末尾）", "chat", 8, "lines"))
    owner_only: bool = field(default=False, metadata=_desc("owner_only", "仅框架主人可用：开启后非管理员用户的消息不触发智能体（Dashboard 不受限制）", "chat", 9, "switch"))

    memory_max: int = field(default=200, metadata=_desc("memory_max", "每会话长期记忆条数上限", "memory", 1, "number"))
    memory_recall: int = field(default=6, metadata=_desc("memory_recall", "每次对话注入的相关记忆条数上限", "memory", 2, "number"))

    tool_timeout: int = field(default=120, metadata=_desc("tool_timeout", "单次工具调用超时（秒）", "tools", 1, "number"))
    max_tool_rounds: int = field(default=15, metadata=_desc("max_tool_rounds", "工具循环最大轮数", "tools", 2, "number"))
    max_tool_calls: int = field(default=30, metadata=_desc("max_tool_calls", "单次对话工具调用总次数上限", "tools", 3, "number"))
    disabled_tools: list[str] = field(default_factory=list, metadata=_desc("disabled_tools", "禁用的工具名列表（支持 eco_/mcp_/插件名. 前缀通配）", "tools", 4, "list"))

    eco_exclude: list[str] = field(default_factory=lambda: ["QvQChat"], metadata=_desc("eco_exclude", "不桥接服务目录的模块名单", "eco", 1, "list"))
    eco_include: list[str] = field(default_factory=list, metadata=_desc("eco_include", "仅桥接这些模块的服务，留空表示全部", "eco", 2, "list"))

    mcp_timeout: int = field(default=30, metadata=_desc("mcp_timeout", "MCP 请求超时（秒）", "mcp", 2, "number"))

    task_check_interval: int = field(default=20, metadata=_desc("task_check_interval", "任务轮询间隔（秒）", "task", 1, "number"))
    task_use_cron_module: bool = field(default=True, metadata=_desc("task_use_cron_module", "装有 ErisPulse-Cron 时把 cron 任务交给它托管", "task", 2, "switch"))

    view_token: str = field(default="", metadata=_desc("view_token", "独立访问令牌，留空首次启动自动生成", "access", 1))

    daily_token_limit: int = field(default=0, metadata=_desc("daily_token_limit", "单日模型 token 总量限额（0 不限），超出后非管理员对话被暂停，次日重置", "usage", 1, "number"))
    usage_retention_days: int = field(default=14, metadata=_desc("usage_retention_days", "用量统计数据保留天数", "usage", 2, "number"))

    skills_dir: str = field(default="data/QvQChat/skills", metadata=_desc("skills_dir", "技能目录（每个 .md 文件一个技能，frontmatter 含 name/description）", "skills", 1))
    skills_disabled: list[str] = field(default_factory=list, metadata=_desc("skills_disabled", "禁用的技能名列表", "skills", 2, "list"))
