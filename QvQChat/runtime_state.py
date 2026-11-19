from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuntimeState:
    """进程内瞬态状态（Main.state）。

    收敛历史上散在 ``Main.__init__`` 的 ~20 个 dict/set：生命周期与进程同寿、
    不需持久化的运行时容器（锁表 / 限频 / 合并窗 / 缓存 / 缓冲）都集中在这里，
    mixin 与面板端点统一走 ``main.rt.<名>`` 访问，不再各自 getattr 兜底。
    """

# 跨账户同消息认领表：指纹 -> (账户, 时间戳, 是否@)，防多账户各跑一份
    msg_claims: dict = field(default_factory=dict)
# bot 连锁计数：chat_key -> 连续兄弟 bot 触发轮数（超限静默等真人）
    bot_chain: dict = field(default_factory=dict)
# 每会话处理锁（防同一会话并发处理）
    chat_locks: dict = field(default_factory=dict)
# 防抖窗：chat_key -> {"items", "event", "timer"}（合并短时间连发）
    pending: dict = field(default_factory=dict)
# 中断排队：chat_key -> [event, ...]（interrupt_mode=queue 时暂存）
    waiting: dict = field(default_factory=dict)
# 合并回复窗的定时器句柄：chat_key -> timer
    merge_timers: dict = field(default_factory=dict)
# 最近回复时间戳（回复间隔节流）
    last_reply_ts: dict = field(default_factory=dict)
# 主动发言近期记录：chat_key -> [(ts, 摘要), ...]（预算护栏与回显）
    proactive_recent: dict = field(default_factory=dict)
# 中断注记：被叫停任务做到哪（锁外写、锁内取）
    interrupted_notes: dict = field(default_factory=dict)
# 滑动限频窗：key -> [ts, ...]
    rate_window: dict = field(default_factory=dict)
# 限频提示已展示标记（一次限频只提示一次）
    rate_notice_shown: dict = field(default_factory=dict)
# 让渡状态 5s 进程内缓存：chat_key -> (ts, state)
    handover_cache: dict = field(default_factory=dict)
# 事件收件箱（通知/请求等非消息事件的未读缓存）：account -> [entry, ...]
    event_inbox: dict = field(default_factory=dict)
# 通知限频：chat_key -> [ts, ...]
    notice_rate: dict = field(default_factory=dict)
# 入群欢迎合并缓冲：chat_key -> {"events", "timer"}
    join_buffer: dict = field(default_factory=dict)
# 好友新增已欢迎表（10 分钟内不重复欢迎）：platform:user -> ts
    recent_friend_greeted: dict = field(default_factory=dict)
# 连发分段节奏记录："{chat_key}:{sender}" -> 上次分段发送时间戳（burst 打断护栏）
    burst_last: dict = field(default_factory=dict)
# 人工接管中的会话：chat_key -> 接管信息（bot 身份发言不进 AI 管线）
    takeover: dict = field(default_factory=dict)
# qvq_settings 归属标记：{module: title}（生态模块声明自己的设置组）
    plugin_settings_catalog: dict = field(default_factory=dict)
