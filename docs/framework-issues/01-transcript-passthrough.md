# Issue 1（主 issue）：会话收件箱查询 API 丢失消息归因 —— 透传 sender 与事件元数据

> 已提交（仓库 issue 模板版）：https://github.com/ErisPulse/ErisPulse/issues/467
> 建议标签：`bug` `enhancement` `core/transcript` `breaking-no`（纯增量，不破坏兼容）
> 影响版本：ErisPulse 2.8.x（以下行号基于当前 main 源码 `src/ErisPulse/`）
> 关联 issue：#2（recent 会话过滤）、#3（message.sent 模块归属）、#4（入站 bot 回声）

## 背景（真实用户案例）

ErisPulse-QvQChat 4.0.3 开启 `group_isolation`（群聊按成员隔离会话，写键 `platform:group:<gid>:u<uid>`）。成员隔离会话冷启动时经 `event.history()` 回填**群级**收件箱（框架按事件推导键 `platform:group:<gid>`，这是设计内行为）。实测 bug：

1. 群主 @机器人："更新框架到 2.11.0" → 机器人回复"📢 框架更新情况说明：已是 2.11.0 无需更新"
2. 另一成员（"2B活塞头"）@机器人："捏"
3. 机器人回复："**刚才不都说了嘛**，框架就是最新的 2.11.0"——**把活塞头误认成了群主**

根因不在模块：`event.history()` 返回的每条记录只有 `role/text/ts/event_id`，**群主的消息和任何成员的消息在 API 层不可区分**，AI 无从知道"上一轮对话者是 A、当前发言者是 B"。

收件箱的存储层其实**已经保存了 `sender`**（2.8.0 加列时注释即写"回放时还原消息来源"），但查询 API 把它丢了——属实现疏漏，不是设计取舍。

## 当前行为

| API | 返回字段 | 问题 |
|---|---|---|
| `transcript.get(session, n)` | `role/text/ts/event_id` | Select（`transcript.py:632`）与返回构造（`transcript.py:643-652`）均**不含 sender** |
| `event.history(n)`（`Event/wrapper.py:1911-1928`，直接转发 get） | 同上 | 同上；docstring 声称"含用户与机器人双方"却无法区分归因 |
| `transcript.get_by_trace(trace_id, limit)` | `role/text/ts/event_id` | 同上（`transcript.py:792, :803-807`） |
| `transcript.recent(seconds, limit)` | `role/text/ts/sender/session_key` | 唯一带 sender 的接口，但语义是**跨会话全局查询**，模块只能"全局拉大窗口再客户端过滤"（QvQChat 目前的临时方案：`recent(7天, 500+)` 然后逐条比对 `session_key`） |

此外，入站自动记录（`Core/adapter.py:1852-1863`）只落 `alt_message` 与 `user_id`，**丢弃了当时事件里的昵称等元数据**——即使透传 sender，回放时也只能拿到裸 id（昵称需另行反查，且事后反查到的是"现在的昵称"而非"当时的昵称"）。

## 期望行为

所有收件箱查询接口（`get` / `recent` / `get_by_trace` / `event.history`）统一返回完整归因：

```python
{
    "role": "user" | "bot",
    "text": "...",
    "ts": 1760000000.0,
    "event_id": "...",
    "sender": "u12345",          # 已有列，直接透传
    "meta": {                    # 新增：记录时刻的事件元数据（白名单）
        "nickname": "小王",       # 入站：当时的昵称；出站：bot 名或空
        "self_id": "bot10001",   # 入站：平台 self.user_id（识别 bot 回声用，见 Issue 4）
        "sub_type": "normal",    # 入站：消息子类型
        "message_id": "...",     # 入站：平台消息 id（可选）
        "module": "QvQChat",     # 出站：发送归属模块（见 Issue 3，先行占位可为 ""）
    },
}
```

## 方案设计

### 1. 存储层：新增 `meta` 列

- 建表 DDL（`transcript.py` `_ensure_table`/`_aensure_table`，:297-330）补 `"meta": "TEXT DEFAULT '{}'"`。
- 新增 `_migrate_add_meta`（同步 + 异步双路径），**完全照抄 `_migrate_add_sender` 的探测+ALTER 模式**（:343-364）：先 `Select("meta").Limit(1).Execute()` 探测，缺列则 `AlterTable(...).AddColumn("meta", "TEXT DEFAULT '{}'")`，后端不支持 ALTER 时静默降级（meta 仅回放增强，与 sender 列降级策略一致）。

### 2. 写入层：`append()` 增加 meta 参数

```python
def append(self, session, role, text, event_id="", sender="", meta: dict | None = None) -> bool:
```
- 内存缓冲行（`transcript.py:566-573` `_buffer.append`）与落盘 flusher 同步携带 `meta`（序列化 `json.dumps(meta or {}, ensure_ascii=False)`）。

### 3. 入站记录：归档白名单元数据

`Core/adapter.py:1852-1863` 记录点改为：

```python
_transcript.append(
    data, "user", _alt, event_id=trace_id,
    sender=str(data.get("user_id") or ""),
    meta={
        "nickname": str(data.get("user_name") or data.get("user_nickname") or ""),
        "self_id": str((data.get("self") or {}).get("user_id") or ""),
        "sub_type": str(data.get("sub_type") or ""),
        "message_id": str(data.get("message_id") or ""),
    },
)
```

### 4. 出站记录：`_on_message_sent` 落 send_ctx 元数据

`transcript.py:754-772` 在现有参数基础上传 `meta=dict(data)`（send_ctx 本身就是小 dict：platform/method/detail_type/target_id/bot_id/trace_id/preview，见 `Bases/adapter.py:313-322`；`module` 字段由 Issue 3 补充）。

### 5. 查询层：三个接口统一补 `sender` + `meta`

- `get()`（:632 Select 补 `"sender", "meta"`；:643-652 返回补两字段）
- `get_by_trace()`（:792, :803-807 同上）
- `recent()` 已有 sender，返回补 `meta`
- `meta` 反序列化容错：`json.loads(r.get("meta") or "{}")`，解析失败回退 `{}`（旧数据/降级库无该列时自然得到 `{}`）
- `Event/wrapper.py:1911-1928` `history()` docstring 更新为含 `sender/meta` 的完整结构

## 为什么是 meta 白名单，而不是透传完整 raw event

- **体积**：收件箱每条消息都记，`alt_message` 已做截断（`TRANSCRIPT_TEXT_MAX_CHARS`）；完整 raw event（平台私有字段、CQ 码、附件 base64）会让表膨胀数个量级。
- **隐私**：raw 里可能含平台 token 回显、私聊内容冗余字段。
- **schema 稳定性**：白名单字段是框架可控契约；raw 透传等于把各适配器的 schema 波动写进存储。

> 备选方案（供讨论）：加 `transcript.raw_events = False` 配置项，开启时 meta 额外存 `raw`（截断至如 4096 字符）。默认关闭。若维护方认为有必要可作为后续增强，不阻塞本 issue。

## 兼容性与迁移

- 返回 dict **只增字段**：现有按 key 取值的调用方（模块、影子 diff、`get_load_strategy(replay=...)`）零影响。
- 旧数据：`sender` 列已有数据直接可用；`meta` 为 `{}`（调用方 `meta.get("nickname", "")` 自然降级）。
- 后端不支持 ALTER：meta 恒 `{}`，静默降级，与 sender 列策略一致。

## 测试建议

1. `append` 带 meta → `get`/`recent`/`get_by_trace` 均能读回 sender+meta（含未落盘缓冲行的 read-your-writes 路径）
2. 旧表迁移：无 meta 列的表 → `_migrate_add_meta` 自动补列；不支持 ALTER 的后端 → 查询返回 `meta={}` 不抛错
3. meta JSON 损坏（手工写坏数据）→ 返回 `{}` 不抛错
4. 入站记录后 `get()` 能拿到 nickname（QvQChat 侧将移除自建的昵称缓存反查，直接消费该字段——可作为下游验收）

## 验收清单

- [ ] 表结构与迁移：`meta` 列（同步/异步双路径探测+ALTER+降级）
- [ ] `append(meta=...)` 签名与缓冲/落盘贯穿
- [ ] 入站记录归档 nickname/self_id/sub_type/message_id
- [ ] `get`/`get_by_trace`/`recent`/`event.history` 统一返回 `sender` + `meta`
- [ ] docstring（append/get/recent/get_by_trace/history）同步更新
- [ ] 测试覆盖上述 4 点

## 下游影响（供参考）

ErisPulse-QvQChat 已在本轮修复中用 `recent(7*24*3600, 500).filter(session_key)` 作为**不依赖本 issue 的临时方案**（见 QvQChat `Main.py::_transcript_rows`）。本 issue 落地后模块可回退为 `get()` 直查（更精确、免全局扫描），并删除自建昵称缓存。
