# Issue 3：`message.sent` 出站消息缺发送模块归属 —— 接线现成的 `current_owner` 机制

> 已提交（仓库 issue 模板版）：https://github.com/ErisPulse/ErisPulse/issues/469
> 建议标签：`enhancement` `core/adapter` `core/transcript`
> 影响版本：ErisPulse 2.8.x
> 关联：#1（transcript meta 列）——本 issue 的 `module` 字段经 meta 落库

## 背景

同一 ErisPulse 实例上多个模块都会通过 `adapter.Send` 发消息（聊天模块、管理模块、定时提醒、框架自身通知）。收件箱把所有出站记为 `role="bot"`（`transcript.py:754-772`），**无法区分"是哪个模块发的"**。

下游真实需求（ErisPulse-QvQChat 案例）：AI 聊天模块在回放群收件箱时，需要区分：

- "这是**我（聊天模块）**之前的发言" → 可作为自我记忆
- "这是**本实例其它模块**（如框架更新播报）代发的" → 不应据以回应、也不该当成自己的话

没有归属信息，AI 无法建立正确的自我认知（实测：模块把实例里其它模块的通知当成自己说的话并据此回复用户）。

## 关键发现：归属机制已存在，只是没接线

`runtime/context.py:28-50` 已定义两个 ContextVar，且 **docstring 明言其用途就是出站发送归属**：

```python
#: 当前资源归属者（模块名或适配器平台名）。
current_owner: ContextVar[str | None] = ContextVar("current_owner", default=None)

#: 当前跨模块调用的调用方身份。由 Core/module.py:ModuleManager.call 在执行目标模块
#: 方法期间注入：……目标方法执行期间 current_owner 归因到目标模块
#: （日志/出站发送归属谁的代码归因谁）……
current_caller: ContextVar[str | None] = ContextVar("current_caller", default=None)
```

即：**经 `sdk.module.call(...)` 执行的模块代码里发出的消息，`current_owner` 已经是目标模块名**——但发送侧的 `send_ctx`（`Bases/adapter.py:313-322`）没有读取它：

```python
send_ctx = {
    "platform": platform,
    "method": method_name,
    "detail_type": send_dsl._target_type or "",
    "target_id": send_dsl._target_id or "",
    "bot_id": send_dsl._account_id or "",
    "trace_id": _trace_id,
    "preview": _preview,
    # ← 没有 module
}
```

## 期望行为

1. `message.sent` / `message.sending` 钩子载荷（send_ctx）增加 `"module": "QvQChat"` 字段（订阅审计/统计类模块同步受益）
2. 收件箱出站记录带归属（经 Issue 1 的 `meta.module` 落库），查询可区分"我发的 vs 其它模块发的"
3. 覆盖矩阵：

| 发送场景 | 期望 module 值 | 现状可行性 |
|---|---|---|
| 模块代码经 `sdk.module.call` 被调用期间 | 目标模块名 | ✅ `current_owner` 已注入，直接读取 |
| 模块的事件处理器内直接发送 | 注册该处理器的模块名 | ⚠️ 需补：分发期间注入 owner（见方案 b） |
| 定时任务/调度器回调内发送 | 调度发起模块名 | ⚠️ 需调度器在回调上下文 set owner |
| 框架自身发送 | `"core"` 或 `""` | 自然兜底 |
| 交互式/未知上下文 | `""` | 自然兜底 |

## 方案设计

### a. send_ctx 接线（核心改动，一行语义）

`Bases/adapter.py:313-322`：

```python
from ...runtime.context import current_caller, current_owner   # current_trace_id 已在同文件引入

send_ctx = {
    ...,
    "module": (current_owner.get() or current_caller.get() or ""),
}
```

> 用 `current_owner or current_caller` 与 `Core/connections.py:138` 的既有回退顺序保持一致。

### b. 事件处理器分发期间注入 owner（补覆盖矩阵第二行）

`Core/adapter.py` 已有"注册期间记录处理器归属"的数据：中间件归属映射 `id(func) → owner`（:115 注释，:1605/:1626 注册处读 `current_owner` 记名）。缺的是**分发执行期间**反向查表注入。建议在消息分发入口（执行 handler 前）：

```python
owner = self._middleware_owner.get(id(handler)) or ""   # 注册期归属表
token = current_owner.set(owner) if owner else None
try:
    await handler(event)
finally:
    if token is not None:
        current_owner.reset(token)
```

> 适配器自身分发的平台事件（`adapter.py:652/:1180` 已在适配器生命周期 set `current_owner=platform`）与此不冲突：处理器查表优先，查不到保持外层上下文。

### c. transcript 落库

依赖 Issue 1 的 `meta` 列：`transcript.py:_on_message_sent` 的 `meta` 里带 `"module": data.get("module") or ""`。（Issue 1 未合并时也可先行独立加 `module TEXT` 列，迁移照抄 `_migrate_add_sender`——实现时二选一，推荐随 Issue 1 的 meta 走，少一列。）

### d. 调度/定时路径

框架调度器执行模块注册的回调前 set `current_owner`（若该路径目前未注入）。此项可并入本 issue 或单独小 issue，按维护方节奏定。

## 兼容性

- send_ctx 增字段：`message.sent`/`message.sending` 订阅方按 key 取值，零影响。
- ContextVar 在同步/异步任务间随 context 传播；`spawn_background` fire-and-forget 的钩子 emit（`Bases/adapter.py:344-350`）在任务创建时快照上下文——**module 取值在 send_ctx 构造时已固化**，不受后台调度影响。
- 无存储格式破坏（meta 新列已在 Issue 1 迁移）。

## 测试建议

1. 模块 A 经 `sdk.module.call("A", "svc")` 内发送 → send_ctx/收件箱 `module == "A"`
2. 模块 B 注册 `message.on_message` 处理器内发送 → `module == "B"`（覆盖方案 b）
3. 无任何模块上下文（框架直发）→ `module == ""` 不抛错
4. 嵌套：A call B，B 内再 call C，C 内发送 → `module == "C"`、`current_caller == "B"`（回归 `module.py` 既有语义）

## 验收清单

- [ ] send_ctx 增加 `module` 字段（owner > caller > ""）
- [ ] 事件处理器分发期间按注册归属表注入 current_owner
- [ ] `_on_message_sent` 落 `meta.module`（随 Issue 1）或独立 `module` 列
- [ ] 调度器回调路径注入 owner（或另开 issue 跟踪）
- [ ] 覆盖矩阵 4 场景测试
- [ ] 文档：模块开发文档补"出站归属规则"一节（module.call / 处理器 / 调度 / core 四种来源）
