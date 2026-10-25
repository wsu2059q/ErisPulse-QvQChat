# Issue 4：入站 bot 自发消息回声被记为 user —— 污染收件箱归因

> 已提交（仓库 issue 模板版）：https://github.com/ErisPulse/ErisPulse/issues/470
> 建议标签：`bug` `core/adapter` `core/transcript`
> 影响版本：ErisPulse 2.8.x
> 关联：#1（meta 列承载 `self_id`/`self_echo` 标记）

## 背景

收件箱的入站自动记录（`Core/adapter.py:1852-1863`）对所有 `event_type == "message"` 一律记 `role="user"`、`sender=user_id`，**没有 bot self 过滤**。

部分平台/协议端会把 bot 自己发出的消息以 message 事件回显上报（典型：OneBot v11 的 `message_sent` 上报、Telegram outgoing message 事件、某些适配器的 echo 模式）。此时：

- bot 自己说的话被记成 `role="user"`——与"某个用户说了这句话"在收件箱里**完全无法区分**；
- 下游模块（会话回放、上下文回填、AI 归因）把机器人自发言当成用户输入，产生污染：
  - AI 误以为用户说了某些话并尝试回应；
  - 收件箱 `role` 统计失真（影子 diff / 审计按 role 分类时归错类）。

值得注意的是：**记录点之后十几行**（`adapter.py:1865` 起）框架就在处理 `data.get("self")` 做 bot 上下线自动发现——`self` 字段在记录时刻是可用的，只是记录逻辑没消费它。

## 期望行为

入站记录前识别回声：

```python
self_id = str((data.get("self") or {}).get("user_id") or "")
is_self_echo = bool(self_id) and self_id == str(data.get("user_id") or "")
```

命中回声时按配置处理（新增配置项 `transcript.self_echo`）：

| 取值 | 行为 | 适用 |
|---|---|---|
| `"bot"`（**默认建议**） | 仍记录，但 `role="bot"`、`sender=self_id`、`meta.self_echo=True` | 数据不丢，下游按 role 区分——与出站钩子记录（`message.sent`）可能形成双条，由下游按 `event_id`/时间去重 |
| `"skip"` | 不记录 | 下游确无需求、且适配器同时会触发 `message.sent`（天然有出站记录）时 |
| `"user"` | 现状行为（记为 user） | 兼容逃生口 |

## 方案设计

`Core/adapter.py:1852-1863` 改为：

```python
if event_type == "message":
    try:
        from .transcript import transcript as _transcript

        _alt = data.get("alt_message", "") or self._extract_message_text(data)
        if _alt:
            _role = "user"
            _meta = {
                "nickname": str(data.get("user_name") or data.get("user_nickname") or ""),
                "self_id": str((data.get("self") or {}).get("user_id") or ""),
                "sub_type": str(data.get("sub_type") or ""),
                "message_id": str(data.get("message_id") or ""),
            }   # meta 载荷随 Issue 1 落地；Issue 1 未合并时本 issue 可先只做 role/sender 改写
            _self_id = _meta["self_id"]
            if _self_id and _self_id == str(data.get("user_id") or ""):
                mode = str(cfg.get("self_echo", "bot"))   # transcript 配置面（enabled 同级）
                if mode == "skip":
                    pass  # 不记录
                elif mode == "user":
                    _transcript.append(data, "user", _alt, event_id=trace_id,
                                       sender=str(data.get("user_id") or ""), meta=_meta)
                else:
                    _meta["self_echo"] = True
                    _transcript.append(data, "bot", _alt, event_id=trace_id,
                                       sender=_self_id, meta=_meta)
            else:
                _transcript.append(data, "user", _alt, event_id=trace_id,
                                   sender=str(data.get("user_id") or ""), meta=_meta)
    except Exception as e:
        logger.warning(i18n.t("core.transcript.append_failed", error=e))
```

配置读取位置与 `transcript.enabled` 同源（`_get_retention`/config 的既有读取路径）。

## 平台差异说明（实现/测试时需知）

- **OneBot v11**：协议端开启 `report-self-message` 时 bot 自发消息以 `post_type=message` + `sub_type` 不同于普通消息上报——`self.user_id == user_id` 判定成立。
- **适配器主动回显**：若某适配器在发送后自行注入事件对象，同样走该判定。
- **不回显的平台**：`self.user_id != user_id` 恒成立，行为与现状完全一致（零影响）。

## 兼容性

- 默认 `"bot"` 改变了"回显平台"上的记录 role——但这正是修复目标；显式 `"user"` 可回到旧行为。
- 非回显平台零行为变化。
- `role="bot"` 的回声行与 `message.sent` 出站行可能重复（同一句话两条记录）：两行的 `event_id`（trace 链路）一致或时间近似，下游去重有据可依；docstring/文档注明该语义。若维护方希望框架侧去重，可在 `append` 前按 `(session_key, event_id, role=bot)` 探测近期重复——**不建议默认做**（查询成本进热路径），列为可选讨论。

## 测试建议

1. 伪造 `self.user_id == user_id` 的 message 事件 → 默认配置下记录 `role="bot"`、`sender=self_id`、`meta.self_echo=True`
2. `self_echo="skip"` → 无记录；`="user"` → 旧行为
3. 普通用户消息（self 缺失或不相等）→ `role="user"`，与现状逐字段一致（回归）
4. `self` 字段缺失的适配器 → 零影响

## 验收清单

- [ ] 记录点 self 判定 + 三模式配置 `transcript.self_echo`（默认 `"bot"`）
- [ ] 命中回声：role=bot / sender=self_id / meta.self_echo（随 Issue 1）
- [ ] 非回显平台回归测试
- [ ] 配置文档与 `transcript.enabled` 同节说明

## 下游影响

ErisPulse-QvQChat 回填归因器（`Main.py::_label_seed_rows`）当前对"来源不明的 user 行"统一标注"发言者未记录"。本 issue 落地后，回显平台的 bot 回声不再伪装成用户消息，AI 的"谁在说话"判断少一类污染源。
