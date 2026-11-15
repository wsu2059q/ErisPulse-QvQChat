# 联网与站点解析：生态模块扩展指南

QvQChat 内置的联网能力**只做到通用底座**：

| 工具 | 作用 | 访问级别 |
|---|---|---|
| `web_search` | DuckDuckGo HTML 搜索，返回标题/URL/摘要 | safe（所有成员） |
| `web_fetch` | URL → 文本/Markdown（优先 r.jina.ai 渲染，失败回退原页去标签） | safe（所有成员） |

站点专有解析（B 站视频、知乎问答、QQ 群历史消息等）**不放主模块**，由生态模块实现。
这样主模块不必跟随各站点反爬策略变化发版，装哪个模块就有哪个能力。

## 一、生态模块如何暴露能力

1. 在 `get_meta(services=[...])` 里声明服务（未声明会被 `sdk.module.call` 拒绝）：

```python
SERVICES = [
    {
        "name": "bili_video",
        "description": "读取 B 站视频信息与热门评论（传入 BV 号或视频链接）",
        "signature": "(bv: str, comments: int = 10) -> dict",
    },
    {
        "name": "qvq_schemas",  # 约定服务：提供参数级 schema
        "description": "给 QvQChat 生态桥提供参数级 schema",
        "signature": "() -> dict",
    },
    {
        "name": "qvq_settings",  # 可选：出现在 QvQChat 设置页
        "description": "设置页归属标记",
        "signature": "() -> dict",
    },
]
```

2. 实现 `qvq_schemas` 返回参数级说明（否则生态桥只能从签名推导，模型不知道参数含义）：

```python
async def qvq_schemas(self, **_):
    return {
        "bili_video": {
            "type": "object",
            "properties": {
                "bv": {"type": "string", "description": "BV 号或完整视频链接"},
                "comments": {"type": "integer", "description": "热门评论条数，默认 10"},
            },
            "required": ["bv"],
        }
    }
```

3. 重启后 QvQChat 的生态桥自动把它注册为工具 `eco_<模块名>_<服务名>`，
   例如 `eco_QvQBili_bili_video`，并写进系统提示的生态能力清单。

## 二、让普通成员也能用（权限）

eco 工具默认 **safe（所有成员可用）**，由 QvQChat 配置 `eco_default_access` 控制。
模块可用 `qvq_access()` 按服务自声明权限档（`"safe"` / `"admin"`，声明优先于默认值），
把涉及写操作/发消息的服务收归管理员：

```python
def qvq_access() -> dict:
    return {"bili_video": "safe", "bili_comment_post": "admin"}
```

注意：`qvq_access`/`qvq_schemas` 等约定服务必须同时登记进 `get_meta().services`
白名单（框架 RPC 白名单强校验，漏登记则生态桥调用被静默吞掉）。运营方也可用
`eco_admin`（强制仅管理员）/ `eco_safe`（强制放开，`模块:服务`，两侧支持通配）
覆盖模块的声明。

## 三、QvQChat 的能力边界（为什么不由主模块实现）

- 站点 API 易变（鉴权、风控、结构改版）：生态模块可独立发版、按需安装
- 不同部署想装不同站点：装什么有什么，主模块保持零额外依赖
- 反爬/登录态由各模块自行处理，主模块的 `web_fetch` 只做无登录的公开页面

## 四、和内置工具的关系

- 拿到视频链接想读正文 → 先 `web_fetch`
- 需要结构化字段（播放量、UP 主、评论列表）→ 用生态工具
- 两者都失败 → 明确告诉用户"抓不到"，不要编造内容
