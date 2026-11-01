# QvQChat 批次计划 2026-11（前端打磨 + 拟人化改造）

> 两部分：A 前端打磨批次（承接 2026-10 审计两轮结论，全部编入）；B《拟人化改造总纲 v2.2.1》可行性核对与工单。
> 量级：S=半天 / M=1-2 天 / L=3 天以上。每张工单独立可交付可测试。
> 配套：[optimization-tickets.md](./optimization-tickets.md)（2026-10 批次，T 系列继续有效）。

> **状态（2026-11-01，随 4.1.0 发布）**：F1-F5、H1-H7 已全部完成并发布（F5 的"列表分页"落地为审计页加载更多；记忆页多卡结构与"删除可撤销"未做，见下方遗留）。
> 遗留：H8 few-shot 双池（插件侧，独立仓库）；删除 undo toast；更多列表页搜索；移动端表格已做横向滚动，卡片化未做。

---

## A. 前端打磨批次（F 系列）

### F1 卫生批 ⭐S
- 鉴权成功后 `history.replaceState` 剥掉 URL 中的 `?token=`（不再留在浏览器历史）
- 批量链（技能导入 / MCP 连接全部 / 逐条 POST 链）统计失败数并在 toast 中回显，成功文案不再无视失败
- 导入备份前 `confirmDialog` 列出将影响的区段（providers/人格/任务/记忆/MCP/技能/配置/链序）
- 回归：`tests/test_settings_schema.py`；手测导入导出

### F2 聊天体验批 M
- AI 消息 hover 操作条：复制（复用 `copyText`）+ 重新生成（最后一条 AI 消息，重放其前一条 user 消息并走原发送路径）
- 图片查看器：modal 内缩放（wheel/双指）+ 旋转按钮
- 会话手动改名（`sessions` 存储 `name` 字段已有，补 `/api/qvq/session/rename` + 列表编辑入口）
- 消息时间戳：后端 `contexts` 条目补 `ts`（写入点：`append_user`/`finalize`），前端 hover 显示——存储链路单独小节，先落后端字段

### F3 可达性批 M
- 下拉键盘化：`enhanceSelects` 改回保留原生 `<select>`（视觉用自绘按钮，`tabindex` 与键盘事件转发回原生控件，方向键/字母定位/Esc 免费获得）
- 确认框默认焦点移到"取消"，Enter 不再默认触发删除；危险确认按钮红色已具备
- modal 打开时焦点圈禁（focus trap）+ 关闭时焦点返还触发元素
- toast 加 `role="status" aria-live="polite"`（错误类 `role="alert"`）

### F4 概览与分享批 S-M
- 概览 8 张统计卡点击跳转对应页（`switchTab`）
- share.html：代码块复制按钮（对齐主站 `bindMdCopy`）、ja/ru/zh-TW 文案、跟随系统主题（`prefers-color-scheme`）
- 浏览器标签未读提示：轮询发现新消息时 `document.title = "(n) QvQChat"`，聚焦清零

### F5 系统性三态批 M-L（承接 10 月审计 P1）
- `withListState(box, loader)` 工具：统一骨架屏/空态（图标+一句话+CTA）/错误横幅（含重试按钮，消费 `__http`）
- 各列表页接入：models/personas/skills/tools/mcp/tasks/memory/knowledge/sessions/audit
- 设置页：sticky 底部保存条；`qvq-key-tag` 默认隐藏（悬停/高级模式显示）；草稿写 localStorage（刷新恢复，`beforeunload` 提示随之取消）
- 表格分页/虚拟滚动：audit 先行（服务端 limit+offset 已有雏形），sessions 次之

---

## B. 拟人化总纲 v2.2.1 可行性核对

结论先行：**总纲的四层里，决策层（13-15）与输出层的节奏部分已被现有架构覆盖大半**——`aggregate_window`（防抖 5s）、`rhythm.py`（打字延迟/分段/结构感知）、`participation` 体系（`qvq.observe` 全量旁听 + `qvq_decision` 提供者 + `SpeechBudget` 每群小时上限/300s 基础冷却，与总纲"划小船保底 5 分钟/次"精确吻合）、开场白 4 配置、persona examples。**真正的增量集中在：时间逻辑统一（回声过滤/响应预算/打断）、语气层过滤器、若干提示词条款。**

| 总纲条目 | 现状 | 可行性 | 落点 | 量级 |
|---|---|---|---|---|
| 1 开场白重做 | `opening_*` 4 配置已有；潜水接话题=参与决策范畴 | 私聊超短句=人格 opening 文案；潜水=插件 | 人格文案/插件 | S(文案)/插件 |
| 2 forward 硬边界 | `forward_structure_aware`+`reply_split=paragraph` 已有（纯寒暄已直发） | 缺"卡片不掺工具 trace"开关 | 核心 H7 | S |
| 3 打字节奏 | `rhythm.py` typing_speed/jitter/cap + `delivery_profiles` 按平台覆写 | 已有；参数口径并入 humanize 表单 | 已有 | - |
| 4 撤回拟人 | 无 | onebot11 `delete_msg` 经 `call_adapter_api` 可用；需要撤回重发编排 | 核心 H5 | M |
| 5 已读不回（表情包回应） | QvQMemes `send_sticker` 已有 | 核心无需改 | 插件 | - |
| 6 提示词硬规则 | 输出规则文案已有任务版 | 补聊天版三条禁令 | 核心 H1 | S |
| 7 few-shot 双池 | persona `examples` 单池已有 | 双池+5 分钟反响准入需消息回应关联（transcript 对照），存储与轮换 | 插件（依赖 observe 流） | L |
| 8 输出过滤器 | 无 | 后处理 hook：复述检测（与上条 user 相似度）/疑问句占比/句数截断 | 核心 H4 | S-M |
| 8.5 记忆钩子 | `memory_recall` 注入已有 | 缺"回捞型记忆"的 72h/用户限频与仅对方先开口触发 | 核心 H6 | M |
| 9 身份行 bug | **已修**（4.0.4 发言者归因：无条件标注+「当前正在和你说话的是 X（uid）」） | 无需再做 | - | ✅ |
| 10 scene 平台前缀 | `scene_group` 文案无平台 | 一条文案 + 开关 | 核心 H1 | S |
| 11 摘要保留标注 | 标注为内联文本，压缩天然保留 | 无需再做 | - | ✅ |
| 12 其他智能体≠自己 | 无此条款 | 一条系统提示 + 开关 | 核心 H1 | S |
| 13 注入最近 15 条 | 群聊 contexts 已带标注历史；插件侧有 `qvq.observe` 全量流 | 已满足（核心）；阈值可调属插件 | 已有/插件 | - |
| 13.5 防抖合并+回环丢弃 | `aggregate_window=5s` 已有；回环丢弃未做 | 分级窗口（@压 1s）+ self_id 出站回环丢弃（坑 7 统一） | 核心 H2 | M |
| 13.6 响应预算 7s | `total_delay_cap` 静态上限已有；无首 token 动态重算 | 生成回调链已有 on_delta（可取首 token 时戳），发送层降级链：延迟减半→归零→合并单条 | 核心 H3 | M-L |
| 13.7 打断机制 | 待发队列已有；无取消钩子 | 硬打断=窗口/队列期收到强信号取消未发段（S-M）；软打断=极短 LLM 调用，护栏照总纲 | 核心 H3 硬；软打断走决策提供者 | M(+插件) |
| 14 接不上就沉默 | 决策数据面齐（observe 流+budget） | 关键词门控+@/戳/引用豁免+短消息"回应历史"豁免 | 插件（Stalker），核心无阻塞 | 插件 |
| 15 冷却参数化 | `participation_cooldown_seconds=300`+小时上限=基础冷却已落地 | 增量概率/衰减系数属决策策略 | 插件（Stalker） | 插件 |
| 坑1 身份行 | 已修（同 9） | - | - | ✅ |
| 坑2 view_image 白名单 | `_resolve_allowed` 走 work_dirs，默认不含 `data/QvQChat/uploads` | view_image 对 uploads 目录常直放行（或 work_dirs 默认含） | 核心 H1 顺带 | S |
| 坑4 JSON 卡片占位 | `Converter.py` 属于**各适配器自带文件**（非框架核心） | **外部依赖（适配器侧）**：onebot11/12 适配器的 Converter 在 json 段→标准消息转换时提取 onebot12 常见字段（title/prompt/preview/desc 等）拼可读文本；框架不解析业务 JSON。适配器仓库不在本工作区 | onebot 适配器仓库 | 外部 |
| 坑5 WS 重连 notice | SDK/适配器 | **外部依赖** | SDK | 外部 |
| 坑6 /epsdk -help | SDK | **外部依赖** | SDK | 外部 |
| 坑7 回声过滤 | 同 13.5 | 与 H2 同批（总纲要求必须同批改） | 核心 H2 | M |
| 坑8 file.dat 文件名 | 已修（pip 升级覆盖需重打） | 已知事项 | SDK | ✅ |

施工顺序（按总纲）：H1（提示词/身份/白名单，最快见效）→ H2（防抖+回声+分级窗口，一批改）→ H4（输出过滤器）→ H3（预算+打断，依赖 H2 的时间逻辑）→ H5/H6/H7 → 插件侧（7/14/15）。

---

## C. 拟人化工单（H 系列）

### H1 提示词与身份批 ⭐S
- texts 新增：聊天版输出规则（禁复述上条/禁结尾硬造提问/没把握只回「？」「6」或不接/群聊单段）
- 「用户提到的其他智能体不是你」条款 + `identity_note_other_agents` 开关
- `scene_group/scene_private` 加平台名 + `scene_platform_prefix` 开关
- view_image 对 `data/QvQChat/uploads` 直放行
- 测试：`tests/test_persona_texts.py` 扩展

### H2 回声过滤与防抖分级 M（坑7+13.5，同批）
- inbox：聚合窗口内丢弃 sender==self 的入站事件（`sdk.adapter` bot id 探测，拿不到则退化为 message_id 忽略列表）
- 窗口分级：`debounce_mention_seconds`（@/前缀命中，默认 1s）/ `debounce_group_seconds`（普通群消息，默认 2s）；私聊沿用 `aggregate_window`
- 测试：回环丢弃/窗口分级/触发源合并

### H3 响应预算与打断 M-L（13.6+13.7，依赖 H2）
- on_delta 首字时戳 → 发送层实时预算重算；降级链：打字延迟 80→40→0ms/字 → 未发短句合并单条
- 硬打断：防抖窗口或队列未清空时命中 `humanize_interrupt_signals` → 取消未发段、新消息并入重跑
- 软打断（可选，默认关）：极短 LLM 判定，护栏=仅队列未清空触发/单会话 30s 一次/超时 1.5s 默认不打断
- 测试：预算降级路径/打断取消/合并兜底（参考 `tests/test_rhythm.py` 纯函数风格）

### H4 输出过滤器 S-M（8）
- 生成后发送前：与上条 user 的 bigram 相似度（复用 `utils.overlap_score`）超阈值→重 roll 一次；疑问句占比>50%→去尾问句；超 3 句按句号截断（语义残缺才重 roll，禁止硬发第 4 句）
- 全部受 `humanize_filter_enabled` 门控，失败不阻塞发送

### H5 撤回拟人 M（4）
- `delivery` 撤回工具：onebot11 `delete_msg`（`call_adapter_api`）；嘴瓢检测=H4 重 roll 场景复用：重 roll 命中时先撤回已发条目再发修正版
- 平台无撤回能力时静默跳过

### H6 记忆钩子限频 M（8.5）
- memory 注入拆分"回捞型"（显式「记得你」叙述）与"背景型"；回捞型按 `humanize_recall_interval_hours`（默认 72h/用户）限频，且仅对方先发起对话的回合触发
- 存储：`QvQChat:recall_last:{uid}` 时间戳

### H7 转发卡净化 S（2）
- `build_sections` 支持 `forward_exclude_trace`：不生成「执行过程」节点（纯结论卡）
- 测试：`tests/test_visual.py` 扩展

### H8 few-shot 双池 L（7，插件侧）
- Stalker/独立插件消费 `qvq.observe`：bot 发言 5 分钟内非自己回应≥1 条 → 进入基准池（20 条固定）；增量池 30 条按群风格每周轮换
- 经人格 `examples` 动态注入（或 persona 扩展字段），核心无需改

---

## D. 配置表单（具体字段）

新增设置组 `humanize`（`GROUP_META` 追加 `{"order": 15}`，标签键 `group_humanize`）。字段按 widget 列出，即设置页实际渲染形态。

### D1 新增字段（humanize 组）

| key | 类型 | 默认 | widget | 说明 |
|---|---|---|---|---|
| humanize_enabled | bool | false | switch | 拟人化输出总开关：短句连发+打字延迟+输出过滤统一入口 |
| humanize_sentence_max | int | 25 | number (min 8, max 120) | 单条短句最大字数，超长按句号边界切分 |
| humanize_max_parts | int | 3 | number (min 1, max 6) | 单次回复最多拆几条短句，超出并入最后一条 |
| humanize_typing_ms | int | 80 | number (min 0) | 打字延迟（毫秒/字），0 关闭 |
| humanize_jitter_ms | int | 600 | number (min 0) | 发送抖动随机上限（毫秒），叠加在打字延迟上 |
| humanize_budget_seconds | float | 7.0 | number (min 3, max 30) | 总响应预算（防抖+生成+延迟）；超时按 延迟减半→归零→合并单条 降级 |
| humanize_interrupt | bool | true | switch | 硬打断：队列未清空/防抖窗口内收到强信号时取消未发短句 |
| humanize_interrupt_signals | list | ["mention","poke","reply","burst","urge"] | checks（mention=@ / poke=戳一戳 / reply=引用 / burst=连发≥2条 / urge=催促词） | 硬打断信号集合 |
| humanize_soft_interrupt | bool | false | switch (dangerous) | 软打断：规则未命中时一次极短 LLM 调用判断是否需立即响应（仅队列未清空触发；单会话 30s 一次；超时 1.5s 默认不打断） |
| humanize_filter_enabled | bool | false | switch | 输出过滤器：复述拦截/疑问句占比/句数截断（失败不阻塞发送） |
| humanize_filter_max_sentences | int | 3 | number (min 1, max 6) | 输出过滤器：单次回复句数上限，超出按句号截断 |
| humanize_recall_interval_hours | int | 72 | number (min 0) | 「记得你」回捞型记忆的最小间隔（小时/用户，0 不限） |
| humanize_recall_on_cold_only | bool | true | switch | 回捞仅在本会话对方先开口的回合触发（禁止沉默期翻旧账） |
| humanize_echo_filter | bool | true | switch | 防抖窗口内丢弃自己发出的回环消息 |
| debounce_mention_seconds | float | 1.0 | number (min 0) | 被@/前缀命中时的防抖窗口（秒） |
| debounce_group_seconds | float | 2.0 | number (min 0) | 普通群消息聚合窗口（秒；0 回退 aggregate_window） |

### D2 新增字段（散落各组）

| key | 类型 | 默认 | widget | 组 | 说明 |
|---|---|---|---|---|---|
| forward_exclude_trace | bool | false | switch | chat | 合并转发卡不生成「执行过程」工具节点（纯结论卡） |
| scene_platform_prefix | bool | true | switch | chat | 会话场景说明带平台名 |
| identity_note_other_agents | bool | true | switch | chat | 系统提示注入「用户提到的其他智能体不是你」条款 |
| chat_output_rules | bool | true | switch | chat | 聊天版输出规则（禁复述/禁硬造提问/没把握可只回「？」） |

### D3 复用字段（不新增，表单仅呈现联动）

| key | 现值语义 | 与新表单的关系 |
|---|---|---|
| aggregate_window (chat) | 私聊/默认聚合窗口 5s | 群聊被 `debounce_group_seconds` 覆盖 |
| delivery_profiles (chat) | 按平台投递参数（含 typing） | humanize 开启时 typing 取 `humanize_typing_ms` 口径 |
| participation_cooldown_seconds (participation) | 同群最小发言间隔 300s | 即总纲"基础冷却 5 分钟/次"，已落地 |
| participation_hourly_limit / proactive_daily_limit | 输出护栏 | 总纲冷却结构化的保底参数 |
| opening_* (chat, 4 项) | 开场白行为 | 总纲条 1 的私聊部分靠人格 opening 文案 |
| memory_recall (memory) | 注入条数 | 回捞型限频由 H6 叠加 |
| forward_structure_aware / forward_min_messages (chat) | 结构感知转发 | 与 forward_exclude_trace 正交组合 |

### D4 前端呈现注意
- `humanize_interrupt_signals` 需要 checks 枚举：`settingsEnums` 增加 `interrupt_signals` 数据源（后端 config_get 附 options）
- `humanize_soft_interrupt` 标 dangerous（额外 LLM 调用成本）
- D3 复用字段在 humanize 组页尾加"相关参数"只读小节，避免用户在两组间找不到联动项
