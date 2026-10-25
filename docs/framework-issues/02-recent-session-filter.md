# Issue 2：`transcript.recent()` 增加会话过滤参数

> 已提交（仓库 issue 模板版）：https://github.com/ErisPulse/ErisPulse/issues/468
> 建议标签：`enhancement` `core/transcript` `api`
> 影响版本：ErisPulse 2.8.x
> 关联：#1（归因透传，主 issue）——本 issue 独立可先行

## 背景

`recent()` 是目前唯一返回 `sender` 的查询接口（`transcript.py:654-696`），但语义是**跨会话全局时间窗**查询：

```python
def recent(self, seconds: float, limit: int = 200) -> list[dict[str, Any]]:
```

模块想要"某会话最近 N 条带 sender 的消息"时只能：

```python
rows = transcript.recent(7 * 24 * 3600, limit=500)   # 全局拉大窗口
picked = [r for r in rows if r.get("session_key") == my_key]  # 客户端过滤
```

问题：
1. **性能**：全局 `OrderBy ts DESC LIMIT N` + 客户端过滤——多群部署时窗口里大量无关会话的行被拉出又丢弃；`limit` 给小了会漏目标会话（只能调大），给大了浪费。
2. **read-your-writes 语义偏差**：`_merged`（`transcript.py:580-608`）在全局合并后才由调用方过滤，缓冲行多的实例上返回条数不可控。

而 `get()`（按会话过滤）又**不返回 sender**（Issue 1 修复前），逼模块二选一。

## 期望行为

```python
def recent(self, seconds: float, limit: int = 200, session_key: str | None = None) -> list[dict[str, Any]]:
    """查询最近一段时间内的消息（可选：限定会话键过滤）。
    session_key=None 时保持现有跨会话语义（冷启动回放等现有调用方不变）。
    """
```

## 方案设计

`transcript.py:666-682` 处的查询构造改为条件式：

```python
query = (
    storage.Table(TRANSCRIPT_TABLE)
    .Select("role", "text", "ts", "sender", "session_key")   # Issue 1 落地后加 "meta"
    .Where("ts > ?", cutoff)
)
if session_key is not None:
    query = query.Where("session_key = ?", session_key)
result = query.OrderBy("ts", desc=True).Limit(max(1, int(limit))).ToDict().Execute()
```

> 注：若 storage 查询构建器不支持多次 `Where` 链式 AND，则改为条件拼接（`Where("ts > ? AND session_key = ?", cutoff, session_key)`）——实现时按构建器实际能力二选一。

末段 `_merged` 调用把过滤参数传下去（**`_merged` 已原生支持 `session_key` 过滤**，`transcript.py:583-605`，缓冲行合并路径零新逻辑）：

```python
return [... for r in self._merged(rows, session_key=session_key, since_ts=cutoff, limit=...)]
```

异步路径若存在（与 `_aensure_table` 对应的查询封装）同步修改。

## 兼容性

- 新增**尾参带默认值**：现有调用方（冷启动回放 `get_load_strategy(replay=...)`、模块代码）零影响。
- `session_key` 参数直接接受 `session_key_from_event()` 产出的键格式（`platform:detail_type:target_id`），与返回值里的 `session_key` 字段一致，无新概念。

## 测试建议

1. 多会话写入 → `recent(60, session_key="onebot11:group:1")` 只返回该会话行，且含 sender
2. `session_key=None` 行为与现状逐字节一致（回归保护）
3. 过滤 + 未落盘缓冲行：先 `append`（仅入缓冲）再按 session_key 查询能读到（read-your-writes）
4. `session_key` 传空串 `""`：与 `None` 语义区分——`""` 视为过滤条件（匹配不到任何键，返回空）还是当作 None？建议：`None` 不过滤、`""` 等价不过滤（容错），docstring 写明

## 验收清单

- [ ] `recent(seconds, limit, session_key=None)` 尾参 + docstring
- [ ] SQL 条件过滤 + `_merged(session_key=...)` 缓冲行路径
- [ ] `session_key=None` 现行为回归测试
- [ ] 下游示例：QvQChat `Main.py::_transcript_rows` 将从"recent(全局 500) + 客户端过滤"改为一次调用

## 下游影响

ErisPulse-QvQChat 当前临时实现（`Main.py::_transcript_rows`：`recent(7*24*3600, max(500, limit*25))` 后逐条比对 `session_key`）可直接简化为一行，并消除多群部署下的无效扫描。
