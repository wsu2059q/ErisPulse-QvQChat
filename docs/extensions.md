# 扩展 QvQChat：约定服务与生命周期事件（开发者指南）

QvQChat 的扩展哲学：**生态模块实现"简单几个约定服务"，就能拓展智能体的大部分能力**。不需要继承、不需要注册中心、不需要协议握手——模块在 `get_meta(services=[...])` 里声明一个约定服务，QvQChat 的生态桥（`bridge/ecosystem.py`）会在模块加载后自动收集，卸载时自动回收。

**影响面速查表**（实现哪个接口 → 用户/AI/面板会看到什么）：

| 接口 | 开发者提供 | AI 会怎样 | 用户会看到 |
|---|---|---|---|
| 工具 service | 任意 service + `qvq_schemas` 参数说明 | 自动注册为新工具（`eco_` 前缀豁免工具剪枝） | bot 直接获得新能力 |
| `qvq_access` | `{service: "safe"/"admin"}` | 工具访问级别自声明 | 谁能触发由你决定 |
| `qvq_extensions.prompts` | `[{text, priority?}]` | 使用建议注入系统提示 | AI 更懂何时用你的模块 |
| `qvq_extensions.skills` | `[{name, description, body}]` | 技能清单出现，AI 按 `load_skill` 加载 | 人格页/技能页出现条目 |
| `qvq_extensions.knowledge` | `[{title, content, triggers?}]` | 知识检索与 Lorebook 触发 | 知识页出现（只读） |
| `qvq_extensions.memory` | `[{content, importance?, category?, ts?}]` | 记忆召回合并外部条目 | 记忆页可见（只读，不落库） |
| `qvq_extensions.panel` | `{cards: [{title, text?, icon?}], actions: [{label, kind: "url"/"page", target}]}` | — | 概览页生态卡区 + Ctrl+K 快捷动作（只读，卸载即消失） |
| `qvq_personas` | 人格字段全量 | 人格可被绑定/切换 | 人格页出现（卸载即删） |
| `qvq_settings` | `{title}` | — | 设置页插件分区归属标记 |
| lifecycle 事件 | `sdk.lifecycle.register` | — | 消息/回复/任务事件流可订阅 |

---

## 一、最小示例：贡献一个工具

```python
class MyModule(BaseModule):
    @staticmethod
    def get_meta():
        return dict(
            name="MyModule",
            services=[
                {"name": "get_weather", "description": "查城市天气",
                 "signature": "(city: str) -> dict"},
                {"name": "qvq_schemas", "description": "参数级说明",
                 "signature": "() -> dict"},
            ],
        )

    async def get_weather(self, city: str) -> dict:
        return {"city": city, "temp": 25, "sunny": True}

    async def qvq_schemas(self, **_) -> dict:
        return {"get_weather": {"city": "城市名，如 北京"}}

    def on_load(self, event) -> bool:
        return True
```

装上后 bot 立刻能用 `eco_get_weather` 工具——**AI 自动获得新能力，用户无感知**。

## 二、qvq_extensions：一站式贡献软资源

一个服务提交全部软资源（prompts/skills/knowledge/memory），只读、随模块卸载消失：

```python
async def qvq_extensions(self, **_) -> dict:
    return {
        "prompts": [{"text": "用户问起服务器监控时优先用本模块的工具", "priority": 5}],
        "skills": [{"name": "check-server", "description": "检查服务器健康",
                    "body": "1. eco_get_status 查状态\n2. eco_restart 按需重启"}],
        "knowledge": [{"title": "我们的服务器", "content": "主服务器 ip 1.2.3.4 ...",
                       "triggers": ["服务器", "宕机"]}],
        "memory": [{"content": "主人偏好用 Markdown 收报告", "importance": 4}],
        "panel": {"cards": [{"title": "服务器状态", "text": "3 台在线 · 最近巡检通过"}],
                  "actions": [{"label": "打开监控面板", "kind": "url", "target": "https://..."}]},
    }
```

各字段的影响：

- **prompts**：注入系统提示（`eco_prompt` 部件），AI 自行判断时机。用户可在首启引导面板排除某模块的注入（`eco_prompt_exclude`）。
- **skills**：进入技能清单（`<skills>` 块），AI 命中任务时 `load_skill` 加载正文。同名内置技能优先。
- **knowledge**：参与被动检索（`kb_auto_inject`）与 Lorebook 触发（`triggers` 命中最近 5 条消息时自动注入）。只读：不落库、冷却不回写。
- **memory**：**每回合召回时与内置记忆合并打分**（同 `-天数*0.05` 时间惩罚）。只读：不落库、不衰减、用户 forget 不可删外部条目。
- **panel**：面板展示层——`cards` 渲染在概览页「生态模块」卡区，`actions` 进入 Ctrl+K 快速跳转的动作组（`kind: "url"` 外开链接 / `kind: "page"` 跳面板页面，target 为页面 id）。只读展示，不改变 AI 行为。

## 三、qvq_personas：贡献人格

```python
async def qvq_personas(self, **_) -> dict:
    return {"personas": [{"id": "server_admin", "name": "运维管家",
                          "system": "你是运维管家...", "owner_title": "MyModule"}]}
```

人格页出现（id 为 `ext.<module>.<base_id>`），用户可绑定到任意会话；**模块卸载即删**。

## 四、生命周期事件：订阅任务状态

`sdk.lifecycle.register(event, handler)` 订阅——**事件总线是唯一通知通道**，生态模块据此自建任务面板/通知链：

| 事件 | 载荷 | 时机 |
|---|---|---|
| `qvq.message` | chat_key/platform/sender_id/text/is_group/merged | 每条进入 AI 管线的消息 |
| `qvq.replied` | chat_key/reply/tools | bot 完成一轮回复 |
| `qvq.subagent_started` | sub_key/parent_chat_key/task/tools | 后台子智能体启动 |
| `qvq.subagent_progress` | sub_key/parent_chat_key/task/steps | 后台任务里程碑（`subagent_progress_on` 开启时） |
| `qvq.subagent_done` | sub_key/parent_chat_key/task/answer/status/error/ms | 后台任务终态（done/error/cancelled） |

```python
def on_load(self, event) -> bool:
    self.sdk.lifecycle.register("qvq.subagent_done", self._on_task_done)
    return True

async def _on_task_done(self, data: dict) -> None:
    if data.get("status") == "done":
        # 自建通知链：推送到你的渠道 / 更新你的面板
        ...
```

## 五、qvq_access 与 qvq_settings

- `qvq_access`：返回 `{"get_weather": "safe"}`——声明哪些服务对普通群友开放（未声明默认 admin，仅管理员触发）。
- `qvq_settings`：返回 `{"title": "服务器管理"}`——设置页插件分区的归属标记（模块的 qvq_schemas 项会归到你的分区）。

## 六、设计约定（为什么这样开放）

1. **只读贡献**：模块提供的 skills/knowledge/memory 是"投喂"而非"接管"——QvQChat 的存储仍是唯一权威，模块卸载不留下脏数据。
2. **同名内置优先**：生态技能与内置同名时内置赢——生态永远不能劫持核心行为。
3. **失败隔离**：模块贡献的条目任何异常都被生态桥吞掉（收集阶段过滤），坏模块不影响主模块运行。
4. **影响面即文档**：上表就是承诺——实现某接口产生的效果仅限该行列出的范围，不做隐式行为变更。

更多专题：[联网与站点解析扩展](ecosystem-web.md)（站点专有解析由生态模块实现的分工示例）。
