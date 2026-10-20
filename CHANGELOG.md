# 更新日志

本文件记录 QvQChat 的显著变更。格式参考 Keep a Changelog，版本遵循语义化版本。

## 未发布

### 新增

- **模型健康度熔断**：连续失败 ≥3 次自动冷却（60s×2^n，上限 10 分钟），故障转移链跳过冷却模型，成功即清零；`GET /api/qvq/breakers` 供面板查询
- **成本统计**：模型价格来自 models.dev 目录（`{input, output}` 每百万 token），`record_usage` 按模型记录 `{tokens, in, out}`，`GET /api/qvq/costs` 换算每日与按模型成本
- **群聊 per-user 限频**：`user_rate_limit`（每用户每分钟滑动窗口，0 不限，管理员豁免），超限静默丢弃并至多提示一次
- **智能体编排页**（左侧新增）：模型链拖拽排序（自动保存）、运行状态、任务时间线（定时任务记录最近执行 `QvQChat:task_runs`）、能力开关（工具/技能/MCP 汇总开关）、模型健康徽章
- **成本可视化**：概览页新增成本估算卡（每日成本柱状 + 累计线 + 按模型分布）
- **知识库**：`conversation/knowledge.py` 全文存储 + 即时分块（约 400 字）+ 词面打分检索；`kb_auto_inject` 开启时相关片段自动注入系统提示；工具 `knowledge_search`（safe）/ `knowledge_add` / `knowledge_delete`（admin）；Dashboard 新增知识库管理页（增删查 + 统计）
- **群成员会话隔离**：`group_isolation` 开关（默认关），开启后群聊每位成员独立上下文/人格/记忆（chat_key 追加 `:u<成员>` 后缀，发送路径自动还原目标）
- **OpenAI 兼容端点**：`GET /v1/models` 与 `POST /v1/chat/completions`（含 SSE 流式），Bearer 令牌即 Dashboard 访问令牌；会话按 `user` 字段隔离（默认独立 API 会话）

### 优化

- 默认投递改为逐条分段发送（AI 每段直接发到聊天）；合并转发卡改为可选开关（`forward_enabled`，默认关），开启时工具任务回复打包为合并转发
- 合并转发节点去掉「【N/M】」编号前缀；节点身份改用机器人自己的账号与昵称（get_login_info / get_self_info），不再显示虚构的 QvQChat
- 分段发送不再区分工具任务与纯对话，统一按段落切分；`[[转发]]` / `[[直发]]` 标签仍可强制
- 全局区块垂直间距统一（`.qvq-tab` 内相邻块 14px）；自定义下拉菜单改为挂载 body 的固定定位浮层，不再被卡片滚动区裁剪或撑开
- 记忆页改为单列表：点击作用域打开模态窗查看/删除条目与会话记忆清空
- 会话页默认隐藏 0 轮空会话占位

## 4.0.2

### 新增

- **模型能力标注与编排**：模型条目支持 vision / files(pdf) / video / tool_call / reasoning 能力位，默认由 models.dev 目录自动富化，可在 Dashboard 或 `manage_models` 工具中人工覆盖；`ChatRequest.needs` 按能力路由，故障转移链自动跳过能力不足的模型
- **视觉代看**：主模型不具备视觉能力时，用户消息与工具返回的图片自动改由视觉模型描述后以文字交给主模型，支持「强模型不看图 + 小模型会看图」的组合；用量按模型维度统计
- **AI 自配置**：新增 `manage_models` / `manage_mcp` / `manage_config` 工具（仅管理员），用自然语言让智能体自己配置模型池、MCP 服务器与本模块设置；配套内置技能 `self-config`，`self_config` 开关一键下线
- **看图工具**：`view_image` 把本地图片作为视觉输入回灌给模型
- **长文本转图片**：检测到 Takumi 扩展时自动注册 `render_image` 工具（HTML/CSS → 图片，未安装不占工具位）
- **会话删除**：彻底删除任意会话（历史/记忆/人设绑定一并清除，运行中任务先取消），支持清空已归档；删除入口在侧边栏与会话管理
- **消息原地编辑**：点击编辑在原位展开为与 composer 同观感的编辑器（全宽），支持附件增删（图片缩略 chip、+ 添加、× 移除），保存后附件挂回消息并支持点击预览
- **分段回复**：纯对话长回复按空行/段落切段连发，模拟真人节奏（`reply_split` / `split_min_length` / `split_delay` 可配）；工具任务不受影响，`[[转发]]` 永远整卡
- **上下文压缩多层化**（`conversation/compactor.py`）：microcompact 旧工具输出瘦身（零成本）→ summarize/truncate 策略（按轮切分，tool_calls/tool 永不拆对）→ 触发器为每 N 轮预防性压缩（`compact_every_turns`）+ token 阈值（`context_compress_tokens`）+ 手动（`/qvq 压缩`、会话设置内按钮）；`keep_ratio`、`compact_model`、`context_strategy(auto/truncate/off)`、`max_context_turns`（发送级轮窗口）均可配置
- **开工收敛保护**：工具预算调大（50 轮 / 150 次），临近上限自动注入收敛提醒，不再中途强制收尾成半成品总结
- **主命令 `/qvq`**：`/agent` 保留为兼容别名；新增 `/qvq 压缩` 子命令
- **会话创建后端化**：新建会话序号由后端分配（`POST /api/qvq/sessions/create`）

### 优化

- **会话子系统收敛**：新建 `conversation/` 包，生命周期、内容、压缩、投递、记忆全部归口 `ConversationService`；平台/定时任务/Dashboard 三条运行管道的公共步骤统一走 `prepare()`/`finalize()`，删除 Main 中散落的会话方法
- **工具权限收敛**：权限唯一权威为 `Tool.access`（safe/admin），`safe_tools` / `admin_tools` 作为用户覆盖层；展示文案统一保留在 texts.py
- **回复投递收敛**：`delivery.py` 单一出口——recap 抑制 → 合并转发（按是否工具运行判定，不看长度）→ 分段/单条直发；`[[转发]]` / `[[直发]]` 标签可强制
- **合并转发的真实反馈**：`send_message` 转发尝试失败时如实回报回落（不再静默降级导致 AI 误报"已合并转发"）；OneBot11 式 `status=failed` 自动换下一个发送方式重试
- **主动任务防双发**：定时/后台任务中 AI 已用 send_message 向目标投递过内容时，不再自动补发最终总结
- **前端拆分**：view.js 按功能拆分为 chat/ 下八个文件（core/ui/nav/sessions/messages/stream/views/init），CSS 拆分为 css/ 四个文件，页面按序拼接输出，外观不变
- **样式**：发送按钮蓝底/暂停红底；暂存卡片虚线样式 + 「待发送」徽标 + 附件缩略增强；编辑器全宽（原尺寸）
- **输出规则**：提示词要求多步任务第一句话说明计划、关键节点主动用 send_message 播报（关键信息/主要步骤/阻碍），不让用户长时间无消息

### 修复

- 切换会话时的竞态：历史加载、实时流、同步轮询全部带代际令牌与会话校验，不再出现"点 A 显示 B"或加载卡死（loading 界面覆盖 data-html 防抖签名的问题已修）
- 会话运行态改为按会话记录（busySession），切走后流继续、可跨会话并行对话，切回自动重挂实时输出
- 待发送队列按会话各自暂存，不再串会话
- 图片附件现在持久化进对话历史（此前刷新即丢），图片落盘 uploads 并把路径告知 AI
- 中断提示（interrupted_note）此前因赋值时序从未生效，已修复并国际化
- `save_provider` 修复 api_key 留空（掩码回传）会清掉真实密钥的问题
- 定时任务权限随创建者；发送失败（status=failed）不再被当作成功

## 4.0.1

- 首个 4.x 公开版本：通用智能体（消息收发、生态服务、代码执行、电脑操作、定时任务、长期记忆、技能系统、网页工作台）
