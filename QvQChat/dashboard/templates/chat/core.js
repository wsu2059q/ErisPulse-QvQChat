/* 核心：主题、鉴权令牌链与全局引导 */
(function () {
  var I18N = {
    "zh-CN": {
      load_older: "加载更早消息", load_more: "加载更多", undo: "撤销", search_ph: "搜索…",
      nav_group_core: "核心", nav_group_config: "能力", nav_group_data: "数据", nav_mcp: "MCP", mcp_desc: "MCP 服务器与工具接入", mcp_servers: "服务器", mcp_tools: "MCP 工具", mcp_connect_all: "连接全部", mcp_connect: "连接", mcp_disconnect: "断开", mcp_status_on: "已连接", mcp_status_off: "未连接", mcp_none: "尚未配置 MCP 服务器，点击此处添加", queue_send_now: "立即发送", queue_added: "已暂存，当前回复完成后自动发送", queue_edit: "编辑回输入框", queue_badge: "待发", chat_delete: "删除", session_delete_confirm: "删除该会话？删除后不可恢复", session_deleted: "已删除", chat_purge_archived: "清空已归档", chat_stop: "停止生成", chat_cancelled: "（已停止生成）", chat_settings: "会话设置", settings_save_session: "保存到本会话", settings_apply_all: "应用到全局", share_export: "导出 Markdown", chat_persona_binding: "人格绑定", chat_export: "导出会话", chat_share: "分享会话", share_expires: "链接有效期", share_max_tokens: "最大允许 token（约可见的上下文预算）", share_create: "生成分享链接", share_url: "分享链接", share_hint: "任何人通过此链接可只读查看该会话（受 token 预算与有效期限制），可随时撤销。", share_rounds: "允许访问者继续对话的轮数（0 = 仅只读）", share_rounds_hint: "访问者以非管理员纯文本方式继续对话，不能调用工具；轮数或额度用完自动停止", share_chat_tokens: "续聊可消耗的 token 上限", role_user: "用户", model_s_auto: "自动", effort_s_auto: "默认", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "提名工具/技能（AI 优先使用）", chat_model: "切换模型", chat_effort: "思考强度", model_auto: "自动选择模型", effort_auto: "强度默认", effort_low: "强度低", effort_mid: "强度中", effort_high: "强度高", mention_ok: "完成", mention_none: "暂无可提名的技能或 MCP 工具", confirm_title: "确认操作", confirm_yes: "确定", chat_pasted: "已粘贴附件", chat_pin: "置顶", chat_unpin: "取消置顶", chat_archive: "归档", chat_unarchive: "取消归档", chat_archived: "已归档", chat_hero_sub: "有什么想聊的？或者从下面挑一个开始", chat_chip_1: "帮我写个 Python 小脚本", chat_chip_2: "把今天的聊天总结成周报", chat_chip_3: "解释一段报错信息", chat_chip_4: "每天晚上九点提醒我写日记", chat_new: "新对话", chat_new_name: "网页对话 {n}", chat_busy: "当前会话正在回复中", chat_trigger: "触发规则", trigger_follow: "跟随全局", trigger_all: "全部", trigger_at: "仅艾特", trigger_lurk: "窥屏（只看不回）", trigger_off: "关闭", listen_off_toggle: "隐私：停止监听本群（旁听与插话不再接收本群消息）", chat_density: "信息密度", density_brief: "简洁", density_detail: "详细", steps_count: "{n} 步工具调用", steps_running: "运行中…", copy: "复制", copied: "已复制", msgs_count: "{n} 条消息", session_summary: "上下文摘要",
      stat_usage: "今日用量", backup_export: "导出配置", backup_import: "导入配置", audit_filter: "过滤工具/用户…", col_preview: "最近消息",
      subtitle: "通用智能体",
      nav_overview: "概览", nav_chat: "对话", nav_models: "模型池", nav_personas: "人格",
      nav_tools: "工具", nav_extensions: "扩展", nav_tasks: "定时任务", nav_memory: "记忆", nav_sessions: "会话",
      nav_knowledge: "知识库", knowledge_desc: "共享资料库：相关片段会自动注入对话，也可用 knowledge_search 检索", kb_add: "添加条目", kb_search_ph: "检索…", kb_stats_line: "条目 {e} · 分块 {c}", kb_list_empty: "还没有条目，点上方按钮添加", kb_title_label: "标题", kb_source_label: "来源（可选）", kb_content_label: "内容", kb_need_title_content: "需要标题与内容", kb_triggers_label: "触发关键词（可选，世界书）", kb_triggers_ph: "如：魔王, 北塔（逗号分隔，命中即注入）", kb_priority_label: "触发优先级（大优先）", kb_cooldown_label: "触发冷却分钟（留空用默认，0 不冷却）", kb_edit: "编辑条目", kb_scope_label: "可见域", kb_scope_chat: "会话/平台（填 chat_key 或平台名，如 bilibili）", kb_scope_ph: "留空=全局", kb_scope_chip_private: "私有",
      nav_audit: "审计", nav_settings: "设置",
      sess_members: "成员", sess_members_hint: "成员白名单（每行一个用户 ID，* 表示全员；留空恢复全员）", sess_sources_hint: "接受其它会话的输入（每行一个 chat_key，如 onebot11:group:123；这些会话的消息会路由到本会话）", kb_export: "导出", kb_import: "导入",
      nav_orchestrate: "编排", orchestrate_desc: "智能体总览：模型链 · 健康 · 运行状态 · 任务时间线", orch_model_chain: "模型链（故障转移顺序）", orch_chain_hint: "拖拽调整故障转移顺序，松手自动保存", orch_chain_saved: "链序已保存", orch_health: "模型健康", health_ok: "全部模型正常", health_cooldown: "冷却中", health_fails: "连续失败 {n} 次", health_left: "剩余 {s}s", orch_running: "运行状态", running_none: "没有正在运行的任务：发消息或创建定时任务后可在这里看到实时状态", orch_timeline: "任务时间线", timeline_empty: "暂无任务与执行记录：到「定时任务」创建一个试试", orch_capabilities: "能力开关", caps_tools: "工具", caps_skills: "技能", task_next: "下次", task_last: "最近", task_status_error: "上次失败", cost_title: "成本估算", cost_total: "14 天合计", cost_daily: "每日成本（柱）与累计（线）", cost_by_model: "按模型分布", cost_empty: "暂无带单价的用量数据（模型价格来自 models.dev 目录）", orch_accounts: "适配器账户", orch_accounts_hint: "各平台登录的 bot 账户；同平台多账户时会话按 @账户 隔离", orch_accounts_empty: "没有已连接的适配器", acct_filter_all: "全部账户", acct_sessions_unit: "个会话", acct_multi: "多账户隔离", acct_offline: "已离线的隔离账户", nav_storage: "存储", storage_desc: "全部数据库内容：查看 / 清理 / 重置", storage_total: "总占用", storage_slim: "瘦身", storage_reset: "一键重置…", storage_empty: "存储为空：正常现象，对话/记忆/审计产生数据后会出现在这里", storage_domain: "数据域", storage_count: "条目", storage_size: "大小", storage_browse: "浏览键", storage_clear: "清空", storage_confirm_clear: "清空「{d}」？该域全部数据将被删除", storage_cleared: "已清理 {n} 项", storage_keys_title: "键浏览", storage_keys_hint: "展开一个域后，这里列出它的全部键，可查看内容或删除", storage_no_keys: "该域没有键", storage_key_col: "键", storage_truncated: "内容过长，已截断", storage_reset_hint: "勾选要【保留】的域，未勾选的将被清空", storage_reset_warn: "一键重置不可撤销；保留模型配置可避免重新填 API Key", storage_reset_confirm: "确定执行一键重置？", storage_slim_done: "已瘦身 {n} 个会话", storage_d_sessions: "会话上下文", storage_d_memories: "记忆", storage_d_profiles: "用户画像", storage_d_personas: "人格与绑定", storage_d_knowledge: "知识库", storage_d_audit: "审计日志", storage_d_usage: "用量记录", storage_d_tasks: "定时任务", storage_d_participation: "参与决策", storage_d_shares: "会话分享", storage_d_trash: "回收站", storage_d_recall: "召回索引", storage_d_pending: "待发队列", storage_d_models: "模型配置", storage_d_mcp: "MCP 配置", storage_d_docs: "文档缓存", storage_d_docs_cache: "文档缓存目录", storage_d_uploads: "上传文件", storage_d_work: "文件工作区", storage_d_settings: "界面设置", storage_d_other: "其它",
      overview_desc: "智能体运行一览", overview_detail: "运行详情",
      stat_models: "模型", stat_tools: "工具", stat_eco: "生态工具", stat_sessions: "会话",
      stat_tasks: "任务", stat_mcp: "MCP", stat_extensions: "扩展", stat_security: "安全",
      on: "开", off: "关", takeovers: "接管中会话", trust_on: "完全信任",
      chat_desc: "直接测试智能体", chat_placeholder: "说点什么…", chat_send: "发送",
      chat_thinking: "思考中…", chat_thought: "已思考", subagent_chip: "子智能体", chat_resumed_running: "已恢复仍在进行的回复", chat_edit_only: "仅保存", chat_edit_send: "保存并发送", chat_edit_hint: "保存只改这一条；保存并发送会丢弃这条之后的回复，用新内容重新提问", chat_edit_cut: "删除此条及之后", chat_edit_cut_confirm: "删除这条消息及其之后的所有内容？", chat_empty_send: "内容不能为空", chat_empty: "还没有对话",
      settings_sec_model_basic: "基础",
      settings_sec_model_reliable: "可靠性与任务分派",
      settings_sec_model_routing: "难度路由",
      settings_sec_trigger_reply: "触发方式",
      settings_sec_trigger_prefix: "唤醒前缀",
      settings_sec_tools_limits: "执行限额",
      settings_sec_tools_behavior: "行为与自愈",
      settings_sec_tools_select: "动态工具注入",
      settings_sec_tools_web: "联网工具",
      settings_sec_mcp_conn: "连接",
      settings_sec_mcp_docs: "内置文档",
      settings_sec_eco_scope: "桥接范围",
      settings_sec_eco_access: "权限覆盖",
      settings_sec_memory_basic: "长期记忆",
      settings_sec_memory_profile: "用户画像",
      settings_sec_kb_inject: "检索注入",
      settings_sec_kb_lore: "世界书触发",
      settings_sec_kb_embed: "语义检索",
      settings_sec_skills_manage: "技能管理",
      settings_sec_skills_dev: "开发能力",
      settings_sec_hu_debounce: "防抖与回声",
      settings_sec_hu_filter: "输出过滤与回捞",
      settings_sec_hu_more: "打断与预算",
      settings_sec_sec_admin: "管理员与命令",
      settings_sec_sec_danger: "危险操作",
      batch_select_all: "全选",
      batch_delete: "批量删除",
      batch_none_selected: "先勾选要删除的条目",
      batch_deleted: "已删除 {n} 项",
      batch_confirm: "确认删除选中的 {n} 项？",
      organize_run: "AI 整理",
      organize_running: "AI 正在分析…",
      organize_done: "整理完成：{report}",
      organize_fail: "整理失败：{error}",
      organize_noop: "内容良好，无需调整",
      audit_clear: "清空审计",
      audit_clear_confirm: "确认清空全部审计记录？（不可恢复）",
      audit_cleared: "审计已清空",
      models_desc: "任意 OpenAI 兼容服务商，按顺序故障转移", models_add: "添加 / 更新模型",
      models_name: "名称", models_id: "模型名", models_temp: "温度", models_maxtok: "最大 token", model_smart: "智能配置", model_smart_hint: "开启后从 models.dev 自动补全上下文、能力和价格", model_context: "上下文窗口", model_max_output: "最大输出 Token", model_detect: "从 models.dev 检测", model_detected: "已从 models.dev 补全元数据", model_detect_empty: "models.dev 未收录该模型，请手动填写", model_advanced: "高级配置", model_input_types: "输入类型", model_input_text: "文本", model_input_image: "图片", model_input_video: "视频", model_input_pdf: "PDF", model_caps: "模型能力", model_tool_call: "工具调用", model_reasoning: "推理", model_price: "单价（每百万 token）", model_price_in: "输入", model_price_out: "输出", model_enabled: "启用该模型", model_manage: "模型配置", model_refresh: "刷新能力与价格", model_refresh_done: "已更新 {n} 项", model_delete_confirm: "删除该模型？", model_cap_tools: "工具", model_cap_no_tools: "无工具", model_cap_vision: "视觉", model_cap_reason: "推理", model_unknown: "能力未知", orch_chain_top_no_tools: "链首模型未标记「工具调用」，启用工具的对话会跳过它；请到模型池补全能力或手动开启。", model_none: "还没有模型", model_add_title: "添加模型", model_edit_title: "编辑模型配置", models_key_col: "key", models_auto_enrich_note: "保存后会自动从 models.dev 补全能力与价格，可在「模型配置」里逐个调整", models_meta_note: "模型能力/价格请在「模型配置」里编辑；这里保存不会改动模型列表。", batch_result: "成功 {ok} 项，失败 {fail} 项", backup_import_confirm: "导入将合并/覆盖以下数据：{sections}。确定继续？", regen: "重新生成", session_rename: "重命名会话", session_name_label: "会话名称", session_rename_ph: "留空恢复默认显示", list_load_failed: "加载失败", retry: "重试", settings_show_keys: "显示字段名", load_more: "加载更多",
      save: "保存", actions: "操作", test: "测试", edit: "编辑", del: "删除",
      models_empty: "模型池为空，先添加一个吧", model_test_ok: "模型可用", model_test_fail: "模型不可用",
      saved: "已保存", deleted: "已删除", confirm_del: "确认删除？",
      personas_desc: "系统提示词 + 工具白名单", personas_edit: "编辑人格",
      personas_pid: "人格 id", personas_pname: "名称", personas_system: "系统提示词",
      personas_tools: "工具白名单（逗号分隔，留空全部可用，支持 eco_* 通配）",
      personas_builtin: "内置", personas_empty: "还没有自定义人格：点上方按钮创建，或用 /qvq persona 让 AI 自己写",
      bindings: "会话绑定", bind_btn: "绑定", bind_hint: "chat_key（如 onebot11:group:123）", bind_tiers_hint: "绑定层级（从具体到宽泛，首个命中生效）：会话 chat_key → 群（onebot11:group:123）→ @账户 → 平台（onebot11:*）→ 全局默认", bind_key_col: "绑定对象", bind_none: "暂无绑定（未绑定的会话用全局默认人格）", unbind: "解绑", bind_tier_session: "会话", bind_tier_account: "账户", bind_tier_platform: "平台", bind_scope_chat: "本会话", bind_scope_group: "整个群", bind_scope_account: "当前账户", bind_scope_platform: "整个平台", bind_scope_custom: "自定义", bind_preview: "将在【{tier}】{key} 上使用「{persona}」", bind_preview_hint: "选一个范围或用上面的快捷按钮，绑定会对该范围内所有未单独绑定的会话生效", bind_need_target: "请先选择绑定范围",
      tools_desc: "内置 + 生态桥 + MCP 工具", tools_refresh: "刷新生态桥",
      tools_filter: "过滤…", tools_empty: "没有匹配的工具",
      extensions_desc: "外部模块提供的工具与人格", ext_none: "暂无扩展模块：模块声明 meta.services 即自动接入", ext_personas_col: "人格", ext_schemas_col: "Schema",
      tasks_desc: "智能体创建的定时任务", tasks_empty: "当前没有定时任务：点上方按钮创建（如每天早上推送天气）",
      col_next: "下次触发", col_target: "目标", col_prompt: "内容", col_schedule: "计划",
      memory_desc: "长期记忆作用域", memory_pick: "点击作用域查看条目", memory_clear: "清空",
      memory_empty: "该作用域暂无记忆",
      profile_card_title: "用户画像", profile_card_user: "用户", profile_card_empty: "暂无画像",
      profile_card_clear: "清空画像", profile_card_confirm: "清空该用户的画像？", memory_importance: "重要度", health_reset: "重置", trash_page: "回收站", trash_hint: "删除操作的撤销期限内的暂存；过期自动清理", trash_expires: "剩余", trash_days: "天", trash_restore: "恢复", trash_empty: "回收站为空", panel_title: "快速跳转", panel_ph: "搜会话 / 页面 / 设置项…", panel_none: "没有匹配项", profile_sec_traits: "特征", chat_pin_s: "置顶", profile_sec_preferences: "偏好", profile_sec_facts: "事实", profile_updated: "更新于",
      sessions_desc: "会话与人格绑定", sessions_empty: "还没有会话：去聊天页发一条消息，或等平台消息进来",
      col_turns: "轮数", col_updated: "更新时间", reset_btn: "重置", col_persona: "人格",
      audit_desc: "操作与确认记录", audit_empty: "还没有审计记录：AI 每次调用工具都会在这里留痕",
      col_tool: "工具", col_detail: "详情",
      settings_desc: "运行时配置，保存即生效", settings_saved: "配置已保存",
      group_model: "模型", group_trigger: "触发", group_security: "安全", group_chat: "对话", group_humanize: "拟人化", group_memory: "记忆",
      group_tools: "工具", group_eco: "生态", group_mcp: "MCP", group_task: "任务", group_access: "权限", group_usage: "用量", group_plugin: "插件",
      usage_title: "用量趋势", usage_tokens: "token", usage_calls: "调用", usage_total: "14 天总量",
      usage_avg: "日均", usage_today: "今日", usage_limit: "日上限", usage_empty: "最近 14 天没有用量数据",
      hero_title: "嗨，我在", hero_no_limit: "未设置每日上限",
      recent_sessions: "最近会话", upcoming_tasks: "即将执行",
      login_hint: "输入访问令牌", login_placeholder: "access token", login_btn: "进入", login_failed: "令牌无效",
      col_time: "时间", col_user: "用户", col_origin: "来源", col_chatkey: "会话", col_count: "条数", col_id: "ID",
      ext_module: "模块", mcp_transport: "传输",
      audit_total: "审计记录", audit_tools_n: "工具种类", audit_users_n: "涉及用户", audit_last24h: "近 24 小时",
      audit_copy: "复制 JSON", audit_copied: "已复制",
      chat_attach: "上传附件", chat_skills: "技能", chat_mcp: "指定 MCP 工具", chat_clear: "清空会话",
      chat_clear_confirm: "清空当前会话的上下文？", chat_file_bad: "文件无法读取：", chat_file_big: "文件过大：", chat_img_limit: "图片最多 3 张",
      chat_err: "发送失败", chat_follow: "跟随会话绑定", chat_default_session: "网页对话",
      models_preset: "接入商预设", models_baseurl: "Base URL", models_apikey: "API Key",
      models_fetch: "拉取模型列表", models_fetching: "拉取中…", models_fetch_fail: "拉取失败", models_remote_empty: "未获取到模型",
      nav_skills: "技能", skills_desc: "可复用指令模板：对话中可手动选用，任务匹配时智能体自动加载",
      skills_add: "新建技能", skills_edit: "编辑技能", skills_name: "名称", skills_description: "描述", skills_body: "内容",
      skills_export: "导出", skills_import: "导入", skills_empty: "还没有技能，新建一个或把 .md 放入技能目录",
      skills_source: "来源",
      personas_reset: "恢复默认", personas_modified: "已自定义", sessions_msgs: "消息", yesterday: "昨天", tomorrow: "明天",
      personas_new: "新建人格", mcp_add: "添加服务器", cancel: "取消", mcp_command: "命令", mcp_args: "参数（每行一个）", mcp_headers: "请求头（JSON）", mcp_server: "服务器", hero_dawn_1: "早呀，今天从点什么开始？", hero_dawn_2: "早安，我已就位", hero_dawn_3: "刚醒就来找我聊？", hero_morning_1: "上午好，有什么想聊的？", hero_morning_2: "在的，随时开聊", hero_morning_3: "今天有什么打算？说给我听听", hero_noon_1: "中午好，吃饭了吗？", hero_noon_2: "午休一下，我盯着呢", hero_noon_3: "吃饱了才有力气干活", hero_afternoon_1: "下午好，有点困就聊聊天", hero_afternoon_2: "下午茶时间，歇会儿？", hero_afternoon_3: "别硬撑，累了就歇", hero_evening_1: "晚上好，今天过得怎么样？", hero_evening_2: "回来啦，辛苦了", hero_evening_3: "夜聊模式，随时开麦", hero_late_1: "还没睡呀？", hero_late_2: "夜深了，早点休息", hero_late_3: "睡不着就聊会儿天",
      nav_group_run: "运行", group_kb: "知识库", group_skills: "技能", group_other: "其它",
      settings_search_ph: "搜索设置项…", settings_no_match: "没有匹配的设置项", settings_invalid_value: "值无效，请修正", settings_json_bad: "JSON 格式错误", settings_no_change: "没有修改，无需保存", settings_danger_confirm: "即将修改安全相关设置，确认继续？", settings_unsaved: "有未保存的设置修改，离开将丢失。确认离开？", settings_save_partial: "以下字段未通过校验，未保存", settings_dangerous: "高危", settings_show: "显示", settings_hide: "隐藏", settings_list_add: "添加一项", plugin_settings_empty: "暂无可配置的插件：插件提供 qvq_settings 服务后自动出现在这里",
      settings_sec_context: "上下文与压缩", settings_sec_forward: "合并转发", settings_sec_reply: "分段回复", settings_sec_flow: "运行策略", settings_sec_misc: "其它",
      backup_title: "数据备份", backup_desc: "导出包含模型池、人格、任务、记忆、MCP、技能与全部设置的完整备份；导入时逐项校验后应用。", backup_export_data: "导出数据备份", backup_import_data: "导入数据备份",
      orch_timeline_att: "仅显示运行中 / 异常的任务与执行记录",
      loading: "加载中…"
    },
    "zh-TW": {
      load_older: "載入更早訊息", load_more: "載入更多", undo: "撤銷", search_ph: "搜尋…",
      nav_group_core: "核心", nav_group_config: "能力", nav_group_data: "資料", nav_mcp: "MCP", mcp_desc: "MCP 伺服器與工具接入", mcp_servers: "伺服器", mcp_tools: "MCP 工具", mcp_connect_all: "連接全部", mcp_connect: "連接", mcp_disconnect: "斷開", mcp_status_on: "已連接", mcp_status_off: "未連接", mcp_none: "尚未配置 MCP 伺服器，點擊此處新增", queue_send_now: "立即傳送", queue_added: "已暫存，目前回覆完成後自動傳送", queue_edit: "編輯回輸入框", queue_badge: "待發", chat_delete: "刪除", session_delete_confirm: "刪除該會話？刪除後無法復原", session_deleted: "已刪除", chat_purge_archived: "清空已歸檔", chat_stop: "停止產生", chat_cancelled: "（已停止產生）", chat_settings: "會話設置", settings_save_session: "儲存到此會話", settings_apply_all: "套用到全域", share_export: "匯出 Markdown", chat_persona_binding: "人格綁定", chat_export: "匯出會話", chat_share: "分享會話", share_expires: "連結有效期", share_max_tokens: "最大允許 token（約可見的上下文預算）", share_create: "產生分享連結", share_url: "分享連結", share_hint: "任何人透過此連結可唯讀檢視該會話（受 token 預算與有效期限制），可隨時撤銷。", share_rounds: "允許訪問者繼續對話的輪數（0 = 僅唯讀）", share_rounds_hint: "訪問者以非管理員純文字方式繼續對話，不能呼叫工具；輪數或額度用完自動停止", share_chat_tokens: "續聊可消耗的 token 上限", role_user: "使用者", model_s_auto: "自動", effort_s_auto: "預設", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "提名工具/技能（AI 優先使用）", chat_model: "切換模型", chat_effort: "思考強度", model_auto: "自動選擇模型", effort_auto: "強度預設", effort_low: "強度低", effort_mid: "強度中", effort_high: "強度高", mention_ok: "完成", mention_none: "暫無可提名的技能或 MCP 工具", confirm_title: "確認操作", confirm_yes: "確定", chat_pasted: "已貼上附件", chat_pin: "置頂", chat_unpin: "取消置頂", chat_archive: "歸檔", chat_unarchive: "取消歸檔", chat_archived: "已歸檔", chat_hero_sub: "有什麼想聊的？或從下面挑一個開始", chat_chip_1: "幫我寫個 Python 小腳本", chat_chip_2: "把今天的聊天整理成週報", chat_chip_3: "解釋一段錯誤訊息", chat_chip_4: "每天晚上九點提醒我寫日記", chat_new: "新對話", chat_new_name: "網頁對話 {n}", chat_busy: "目前會話正在回覆中", chat_trigger: "觸發規則", trigger_follow: "跟隨全域", trigger_all: "全部", trigger_at: "僅艾特", trigger_lurk: "窺屏（只看不回）", trigger_off: "關閉", listen_off_toggle: "隱私：停止監聽本群（旁聽與插話不再接收本群訊息）", chat_density: "資訊密度", density_brief: "簡潔", density_detail: "詳細", steps_count: "{n} 次工具呼叫", steps_running: "執行中…", copy: "複製", copied: "已複製", msgs_count: "{n} 條訊息", session_summary: "上下文摘要",
      stat_usage: "今日用量", backup_export: "匯出配置", backup_import: "匯入配置", audit_filter: "過濾工具/使用者…", col_preview: "最近訊息",
      subtitle: "通用智慧代理",
      nav_overview: "概覽", nav_chat: "對話", nav_models: "模型池", nav_personas: "人格",
      nav_tools: "工具", nav_extensions: "擴展", nav_tasks: "定時任務", nav_memory: "記憶", nav_sessions: "會話",
      nav_knowledge: "知識庫", knowledge_desc: "共享資料庫：相關片段會自動注入對話，也可用 knowledge_search 檢索", kb_add: "新增條目", kb_search_ph: "檢索…", kb_stats_line: "條目 {e} · 分塊 {c}", kb_list_empty: "還沒有條目，點上方按鈕新增", kb_title_label: "標題", kb_source_label: "來源（可選）", kb_content_label: "內容", kb_need_title_content: "需要標題與內容", kb_triggers_label: "觸發關鍵詞（可選，世界書）", kb_triggers_ph: "如：魔王, 北塔（逗號分隔，命中即注入）", kb_priority_label: "觸發優先級（大優先）", kb_cooldown_label: "觸發冷卻分鐘（留空用預設，0 不冷卻）", kb_edit: "編輯條目", kb_scope_label: "可見域", kb_scope_chat: "會話/平台（填 chat_key 或平台名，如 bilibili）", kb_scope_ph: "留空=全域", kb_scope_chip_private: "私有",
      nav_audit: "審計", nav_settings: "設定",
      sess_members: "成員", sess_members_hint: "成員白名單（每行一個使用者 ID，* 表示全員；留空恢復全員）", sess_sources_hint: "接受其它會話的輸入（每行一個 chat_key，如 onebot11:group:123；這些會話的訊息會路由到本會話）", kb_export: "匯出", kb_import: "匯入",
      nav_orchestrate: "編排", orchestrate_desc: "智能體總覽：模型鏈 · 健康 · 執行狀態 · 任務時間線", orch_model_chain: "模型鏈（故障轉移順序）", orch_chain_hint: "拖曳調整故障轉移順序，鬆手自動儲存", orch_chain_saved: "鏈序已儲存", orch_health: "模型健康", health_ok: "全部模型正常", health_cooldown: "冷卻中", health_fails: "連續失敗 {n} 次", health_left: "剩餘 {s}s", orch_running: "執行狀態", running_none: "暫無執行中的任務", orch_timeline: "任務時間線", timeline_empty: "暫無任務與執行記錄", orch_capabilities: "能力開關", caps_tools: "工具", caps_skills: "技能", task_next: "下次", task_last: "最近", task_status_error: "上次失敗", cost_title: "成本估算", cost_total: "14 天合計", cost_daily: "每日成本（柱）與累計（線）", cost_by_model: "按模型分佈", cost_empty: "暫無帶單價的用量資料（模型價格來自 models.dev 目錄）", orch_accounts: "介面卡帳戶", orch_accounts_hint: "各平台登入的 bot 帳戶；同平台多帳戶時會話按 @帳戶 隔離", orch_accounts_empty: "沒有已連線的介面卡", acct_filter_all: "全部帳戶", acct_sessions_unit: "個會話", acct_multi: "多帳戶隔離", acct_offline: "已離線的隔離帳戶", nav_storage: "儲存", storage_desc: "全部資料庫內容：查看 / 清理 / 重置", storage_total: "總佔用", storage_slim: "瘦身", storage_reset: "一鍵重置…", storage_empty: "儲存為空", storage_domain: "資料域", storage_count: "條目", storage_size: "大小", storage_browse: "瀏覽鍵", storage_clear: "清空", storage_confirm_clear: "清空「{d}」？該域全部資料將被刪除", storage_cleared: "已清理 {n} 項", storage_keys_title: "鍵瀏覽", storage_keys_hint: "展開一個域後，這裡列出它的全部鍵，可查看內容或刪除", storage_no_keys: "該域沒有鍵", storage_key_col: "鍵", storage_truncated: "內容過長，已截斷", storage_reset_hint: "勾選要【保留】的域，未勾選的將被清空", storage_reset_warn: "一鍵重置不可撤銷；保留模型設定可避免重新填 API Key", storage_reset_confirm: "確定執行一鍵重置？", storage_slim_done: "已瘦身 {n} 個會話", storage_d_sessions: "會話上下文", storage_d_memories: "記憶", storage_d_profiles: "使用者畫像", storage_d_personas: "人格與綁定", storage_d_knowledge: "知識庫", storage_d_audit: "稽核日誌", storage_d_usage: "用量記錄", storage_d_tasks: "定時任務", storage_d_participation: "參與決策", storage_d_shares: "會話分享", storage_d_trash: "回收站", storage_d_recall: "召回索引", storage_d_pending: "待發佇列", storage_d_models: "模型設定", storage_d_mcp: "MCP 設定", storage_d_docs: "文件快取", storage_d_docs_cache: "文件快取目錄", storage_d_uploads: "上傳檔案", storage_d_work: "檔案工作區", storage_d_settings: "介面設定", storage_d_other: "其它",
      overview_desc: "智慧代理運行一覽", overview_detail: "運行詳情",
      stat_models: "模型", stat_tools: "工具", stat_eco: "生態工具", stat_sessions: "會話",
      stat_tasks: "任務", stat_mcp: "MCP", stat_extensions: "擴展", stat_security: "安全",
      on: "開", off: "關", takeovers: "接管中會話", trust_on: "完全信任",
      chat_desc: "直接測試智慧代理", chat_placeholder: "說點什麼…", chat_send: "傳送",
      chat_thinking: "思考中…", chat_thought: "已思考", subagent_chip: "子智慧體", chat_resumed_running: "已恢復仍在進行的回覆", chat_edit_only: "僅儲存", chat_edit_send: "儲存並傳送", chat_edit_hint: "僅儲存只改這一條；儲存並傳送會丟棄這條之後的回覆，用新內容重新提問", chat_edit_cut: "刪除此條及之後", chat_edit_cut_confirm: "刪除這則訊息及其之後的所有內容？", chat_empty_send: "內容不能為空", chat_empty: "還沒有對話",
      settings_sec_model_basic: "基礎",
      settings_sec_model_reliable: "可靠與任務分派",
      settings_sec_model_routing: "難度路由",
      settings_sec_trigger_reply: "觸發方式",
      settings_sec_trigger_prefix: "喚醒前綴",
      settings_sec_tools_limits: "執行限額",
      settings_sec_tools_behavior: "行為與自癒",
      settings_sec_tools_select: "動態工具注入",
      settings_sec_tools_web: "聯網工具",
      settings_sec_mcp_conn: "連接",
      settings_sec_mcp_docs: "內建文件",
      settings_sec_eco_scope: "橋接範圍",
      settings_sec_eco_access: "權限覆寫",
      settings_sec_memory_basic: "長期記憶",
      settings_sec_memory_profile: "用戶畫像",
      settings_sec_kb_inject: "檢索注入",
      settings_sec_kb_lore: "世界書觸發",
      settings_sec_kb_embed: "語義檢索",
      settings_sec_skills_manage: "技能管理",
      settings_sec_skills_dev: "開發能力",
      settings_sec_hu_debounce: "防抖與回聲",
      settings_sec_hu_filter: "輸出過濾與回撈",
      settings_sec_hu_more: "打斷與預算",
      settings_sec_sec_admin: "管理員與命令",
      settings_sec_sec_danger: "危險操作",
      batch_select_all: "全選",
      batch_delete: "批量刪除",
      batch_none_selected: "先勾選要刪除的條目",
      batch_deleted: "已刪除 {n} 項",
      batch_confirm: "確認刪除選中的 {n} 項？",
      organize_run: "AI 整理",
      organize_running: "AI 正在分析…",
      organize_done: "整理完成：{report}",
      organize_fail: "整理失敗：{error}",
      organize_noop: "內容良好，無需調整",
      audit_clear: "清空審計",
      audit_clear_confirm: "確認清空全部審計記錄？（不可恢復）",
      audit_cleared: "審計已清空",
      models_desc: "任意 OpenAI 相容服務商，依順序故障轉移", models_add: "新增 / 更新模型",
      models_name: "名稱", models_id: "模型名", models_temp: "溫度", models_maxtok: "最大 token", model_smart: "智慧設定", model_smart_hint: "開啟後從 models.dev 自動補全上下文、能力和價格", model_context: "上下文視窗", model_max_output: "最大輸出 Token", model_detect: "從 models.dev 偵測", model_detected: "已從 models.dev 補全中繼資料", model_detect_empty: "models.dev 未收錄該模型，請手動填寫", model_advanced: "進階設定", model_input_types: "輸入類型", model_input_text: "文字", model_input_image: "圖片", model_input_video: "影片", model_input_pdf: "PDF", model_caps: "模型能力", model_tool_call: "工具呼叫", model_reasoning: "推理", model_price: "單價（每百萬 token）", model_price_in: "輸入", model_price_out: "輸出", model_enabled: "啟用該模型", model_manage: "模型設定", model_refresh: "重新整理能力與價格", model_refresh_done: "已更新 {n} 項", model_delete_confirm: "刪除該模型？", model_cap_tools: "工具", model_cap_no_tools: "無工具", model_cap_vision: "視覺", model_cap_reason: "推理", model_unknown: "能力未知", orch_chain_top_no_tools: "鏈首模型未標記「工具呼叫」，啟用工具的對話會跳過它；請到模型池補全能力或手動開啟。", model_none: "還沒有模型", model_add_title: "新增模型", model_edit_title: "編輯模型設定", models_key_col: "key", models_auto_enrich_note: "儲存後會自動從 models.dev 補全能力與價格，可在「模型設定」裡逐個調整", models_meta_note: "模型能力/價格請在「模型設定」裡編輯；這裡儲存不會改動模型列表。", batch_result: "成功 {ok} 項，失敗 {fail} 項", backup_import_confirm: "匯入將合併/覆蓋以下資料：{sections}。確定繼續？", regen: "重新生成", session_rename: "重新命名會話", session_name_label: "會話名稱", session_rename_ph: "留空恢復預設顯示", list_load_failed: "載入失敗", retry: "重試", settings_show_keys: "顯示欄位名", load_more: "載入更多",
      save: "儲存", actions: "操作", test: "測試", edit: "編輯", del: "刪除",
      models_empty: "模型池為空，先新增一個吧", model_test_ok: "模型可用", model_test_fail: "模型不可用",
      saved: "已儲存", deleted: "已刪除", confirm_del: "確認刪除？",
      personas_desc: "系統提示詞 + 工具白名單", personas_edit: "編輯人格",
      personas_pid: "人格 id", personas_pname: "名稱", personas_system: "系統提示詞",
      personas_tools: "工具白名單（逗號分隔，留空全部，支援 eco_* 萬用）",
      personas_builtin: "內建", personas_empty: "還沒有自訂人格",
      bindings: "會話綁定", bind_btn: "綁定", bind_hint: "chat_key（如 onebot11:group:123）", bind_tiers_hint: "綁定層級（從具體到寬泛，首個命中生效）：會話 chat_key → 群（onebot11:group:123）→ @帳戶 → 平台（onebot11:*）→ 全域預設", bind_key_col: "綁定對象", bind_none: "暫無綁定（未綁定的會話用全域預設人格）", unbind: "解綁", bind_tier_session: "會話", bind_tier_account: "帳戶", bind_tier_platform: "平台", bind_scope_chat: "本會話", bind_scope_group: "整個群", bind_scope_account: "目前帳戶", bind_scope_platform: "整個平台", bind_scope_custom: "自訂", bind_preview: "將在【{tier}】{key} 上使用「{persona}」", bind_preview_hint: "選一個範圍或用上面的快捷按鈕，綁定會對該範圍內所有未單獨綁定的會話生效", bind_need_target: "請先選擇綁定範圍",
      tools_desc: "內建 + 生態橋 + MCP 工具", tools_refresh: "重新整理生態橋",
      tools_filter: "過濾…", tools_empty: "沒有符合的工具",
      extensions_desc: "外部模組的工具與人格", ext_none: "暫無擴展模組：模組宣告 meta.services 即自動接入", ext_personas_col: "人格", ext_schemas_col: "Schema",
      tasks_desc: "智慧代理建立的定時任務", tasks_empty: "目前沒有定時任務",
      col_next: "下次觸發", col_target: "目標", col_prompt: "內容", col_schedule: "計畫",
      memory_desc: "長期記憶作用域", memory_pick: "點擊作用域查看條目", memory_clear: "清空",
      memory_empty: "該作用域暫無記憶",
      profile_card_title: "使用者畫像", profile_card_user: "使用者", profile_card_empty: "暫無畫像",
      profile_card_clear: "清空畫像", profile_card_confirm: "清空該使用者的畫像？", memory_importance: "重要度", health_reset: "重置", trash_page: "回收站", trash_hint: "刪除操作的撤銷期限內的暫存；過期自動清理", trash_expires: "剩餘", trash_days: "天", trash_restore: "恢復", trash_empty: "回收站為空", panel_title: "快速跳轉", panel_ph: "搜會話 / 頁面 / 設定項…", panel_none: "沒有匹配項", profile_sec_traits: "特徵", chat_pin_s: "置頂", profile_sec_preferences: "偏好", profile_sec_facts: "事實", profile_updated: "更新於",
      sessions_desc: "會話與人格綁定", sessions_empty: "暫無會話",
      col_turns: "輪數", col_updated: "更新時間", reset_btn: "重置", col_persona: "人格",
      audit_desc: "操作與確認記錄", audit_empty: "暫無審計記錄",
      col_tool: "工具", col_detail: "詳情",
      settings_desc: "運行時配置，儲存即生效", settings_saved: "配置已儲存",
      group_model: "模型", group_trigger: "觸發", group_security: "安全", group_chat: "對話", group_humanize: "擬人化", group_memory: "記憶",
      group_tools: "工具", group_eco: "生態", group_mcp: "MCP", group_task: "任務", group_access: "權限", group_usage: "用量", group_plugin: "外掛",
      usage_title: "用量趨勢", usage_tokens: "token", usage_calls: "呼叫", usage_total: "14 天總量",
      usage_avg: "日均", usage_today: "今日", usage_limit: "日上限", usage_empty: "最近 14 天沒有用量資料",
      hero_title: "嗨，我在", hero_no_limit: "未設定每日上限",
      recent_sessions: "最近会话", upcoming_tasks: "即將執行",
      login_hint: "輸入存取令牌", login_placeholder: "access token", login_btn: "進入", login_failed: "令牌無效",
      col_time: "時間", col_user: "使用者", col_origin: "來源", col_chatkey: "會話", col_count: "條數", col_id: "ID",
      ext_module: "模組", mcp_transport: "傳輸",
      audit_total: "審計記錄", audit_tools_n: "工具種類", audit_users_n: "涉及使用者", audit_last24h: "近 24 小時",
      audit_copy: "複製 JSON", audit_copied: "已複製",
      chat_attach: "上傳附件", chat_skills: "技能", chat_mcp: "指定 MCP 工具", chat_clear: "清空會話",
      chat_clear_confirm: "清空目前會話的上下文？", chat_file_bad: "檔案無法讀取：", chat_file_big: "檔案過大：", chat_img_limit: "圖片最多 3 張",
      chat_err: "傳送失敗", chat_follow: "跟隨會話綁定", chat_default_session: "網頁對話",
      models_preset: "接入商預設", models_baseurl: "Base URL", models_apikey: "API Key",
      models_fetch: "拉取模型列表", models_fetching: "拉取中…", models_fetch_fail: "拉取失敗", models_remote_empty: "未取得模型",
      nav_skills: "技能", skills_desc: "可複用指令範本：對話中可手動選用，任務匹配時智慧代理自動載入",
      skills_add: "新增技能", skills_edit: "編輯技能", skills_name: "名稱", skills_description: "描述", skills_body: "內容",
      skills_export: "匯出", skills_import: "匯入", skills_empty: "還沒有技能，新增一個或把 .md 放入技能目錄",
      skills_source: "來源",
      personas_reset: "恢復預設", personas_modified: "已自訂", sessions_msgs: "訊息", yesterday: "昨天", tomorrow: "明天",
      personas_new: "新增人格", mcp_add: "新增伺服器", cancel: "取消", mcp_command: "命令", mcp_args: "參數（每行一個）", mcp_headers: "請求頭（JSON）", mcp_server: "伺服器", hero_dawn_1: "早啊，今天從哪開始？", hero_dawn_2: "早安，我已就位", hero_dawn_3: "剛醒就來找我聊？", hero_morning_1: "上午好，有什麼想聊的？", hero_morning_2: "在的，隨時開聊", hero_morning_3: "今天有什麼計畫？說給我聽聽", hero_noon_1: "中午好，吃飯了嗎？", hero_noon_2: "午休一下，我盯著呢", hero_noon_3: "吃飽了才有力氣做事", hero_afternoon_1: "下午好，有點睏就聊聊天", hero_afternoon_2: "下午茶時間，歇會兒？", hero_afternoon_3: "別硬撐，累了就休息", hero_evening_1: "晚上好，今天過得怎樣？", hero_evening_2: "回來啦，辛苦了", hero_evening_3: "夜聊模式，隨時開麥", hero_late_1: "還沒睡呀？", hero_late_2: "夜深了，早點休息", hero_late_3: "睡不著就聊會兒天",
      nav_group_run: "運行", group_kb: "知識庫", group_skills: "技能", group_other: "其它",
      settings_search_ph: "搜尋設定項…", settings_no_match: "沒有符合的設定項", settings_invalid_value: "值無效，請修正", settings_json_bad: "JSON 格式錯誤", settings_no_change: "沒有修改，無需儲存", settings_danger_confirm: "即將修改安全相關設定，確認繼續？", settings_unsaved: "有未儲存的設定修改，離開將遺失。確認離開？", settings_save_partial: "以下欄位未通過校驗，未儲存", settings_dangerous: "高危", settings_show: "顯示", settings_hide: "隱藏", settings_list_add: "新增一項", plugin_settings_empty: "暫無可設定的外掛：外掛提供 qvq_settings 服務後自動出現在這裡",
      settings_sec_context: "上下文與壓縮", settings_sec_forward: "合併轉發", settings_sec_reply: "分段回覆", settings_sec_flow: "運行策略", settings_sec_misc: "其它",
      backup_title: "資料備份", backup_desc: "匯出包含模型池、人格、任務、記憶、MCP、技能與全部設定的完整備份；匯入時逐項校驗後套用。", backup_export_data: "匯出資料備份", backup_import_data: "匯入資料備份",
      orch_timeline_att: "僅顯示執行中 / 異常的任務與執行記錄",
      loading: "載入中…"
    },
    "en": {
      load_older: "Load earlier messages", load_more: "Load more", undo: "Undo", search_ph: "Search…",
      nav_group_core: "Core", nav_group_config: "Capabilities", nav_group_data: "Data", nav_mcp: "MCP", mcp_desc: "Model Context Protocol servers and tool access", mcp_servers: "Servers", mcp_tools: "MCP tools", mcp_connect_all: "Connect all", mcp_connect: "Connect", mcp_disconnect: "Disconnect", mcp_status_on: "connected", mcp_status_off: "disconnected", mcp_none: "No MCP servers yet — click here to add one", queue_send_now: "Send now", queue_added: "Queued — will send after the current reply", queue_edit: "Edit back to input", queue_badge: "Queued", chat_delete: "Delete", session_delete_confirm: "Delete this session? This cannot be undone", session_deleted: "Deleted", chat_purge_archived: "Purge archived", chat_stop: "Stop generating", chat_cancelled: "(generation stopped)", chat_settings: "Session settings", settings_save_session: "Save to this session", settings_apply_all: "Apply to all sessions", share_export: "Export Markdown", chat_persona_binding: "Persona binding", chat_export: "Export session", chat_share: "Share session", share_expires: "Link expires in", share_max_tokens: "Max tokens allowed (visible context budget)", share_create: "Create share link", share_url: "Share link", share_hint: "Anyone with this link can view the session read-only, limited by the token budget and expiry. Revoke anytime.", role_user: "User", model_s_auto: "auto", effort_s_auto: "Auto", effort_s_low: "Low", effort_s_mid: "Mid", effort_s_high: "High", chat_mention: "Mention tools/skills (AI prioritizes them)", chat_model: "Switch model", chat_effort: "Effort level", model_auto: "Auto model", effort_auto: "Effort auto", effort_low: "Effort low", effort_mid: "Effort mid", effort_high: "Effort high", mention_ok: "Done", mention_none: "No skills or MCP tools to mention yet", confirm_title: "Confirm", confirm_yes: "OK", chat_pasted: "Attachment pasted", chat_pin: "Pin", chat_unpin: "Unpin", chat_archive: "Archive", chat_unarchive: "Unarchive", chat_archived: "Archived", chat_hero_sub: "What shall we talk about? Or pick a starter below", chat_chip_1: "Write me a small Python script", chat_chip_2: "Summarize today's chat into a report", chat_chip_3: "Explain this error message", chat_chip_4: "Remind me to journal at 9pm daily", chat_new: "New chat", chat_new_name: "Web chat {n}", chat_busy: "This session is still replying", chat_trigger: "Trigger rule", trigger_follow: "Follow global", trigger_all: "All", trigger_at: "Mention only", trigger_lurk: "Lurk (no replies)", trigger_off: "Off", listen_off_toggle: "Privacy: stop listening to this chat (observers and interjections no longer receive its messages)", chat_density: "Detail level", density_brief: "Brief", density_detail: "Detailed", steps_count: "{n} tool calls", steps_running: "running…", copy: "Copy", copied: "Copied", msgs_count: "{n} messages", session_summary: "Context summary",
      stat_usage: "Today usage", backup_export: "Export config", backup_import: "Import config", audit_filter: "Filter tool/user…", col_preview: "Last message",
      subtitle: "universal agent",
      nav_overview: "Overview", nav_chat: "Chat", nav_models: "Models", nav_personas: "Personas",
      nav_tools: "Tools", nav_extensions: "Extensions", nav_tasks: "Tasks", nav_memory: "Memory", nav_sessions: "Sessions",
      nav_knowledge: "Knowledge", knowledge_desc: "Shared library: relevant passages are auto-injected into chats and searchable via knowledge_search", kb_add: "Add entry", kb_search_ph: "Search…", kb_stats_line: "{e} entries · {c} chunks", kb_list_empty: "No entries yet — use the button above to add one", kb_title_label: "Title", kb_source_label: "Source (optional)", kb_content_label: "Content", kb_need_title_content: "Title and content are required", kb_triggers_label: "Trigger keywords (optional, lorebook)", kb_triggers_ph: "e.g. demon king, north tower (comma separated)", kb_priority_label: "Trigger priority (higher first)", kb_cooldown_label: "Trigger cooldown minutes (blank = default, 0 = none)", kb_edit: "Edit entry", kb_scope_label: "Visibility", kb_scope_chat: "Session/platform (chat_key or platform name, e.g. bilibili)", kb_scope_ph: "blank = global", kb_scope_chip_private: "private",
      nav_audit: "Audit", nav_settings: "Settings",
      sess_members: "Members", sess_members_hint: "Member allowlist (one user ID per line, * = everyone; empty resets to everyone)", sess_sources_hint: "Accept input from other chats (one chat_key per line, e.g. onebot11:group:123; their messages route into this chat)", kb_export: "Export", kb_import: "Import",
      nav_orchestrate: "Orchestration", orchestrate_desc: "Agent at a glance: model chain · health · runs · task timeline", orch_model_chain: "Model chain (failover order)", orch_chain_hint: "Drag to reorder the failover chain; saves automatically on drop", orch_chain_saved: "Chain order saved", orch_health: "Model health", health_ok: "All models healthy", health_cooldown: "Cooling down", health_fails: "{n} consecutive failures", health_left: "{s}s left", orch_running: "Running", running_none: "No running tasks", orch_timeline: "Task timeline", timeline_empty: "No tasks or runs yet", orch_capabilities: "Capability switches", caps_tools: "Tools", caps_skills: "Skills", task_next: "Next", task_last: "Last", task_status_error: "Last run failed", cost_title: "Cost estimate", cost_total: "14-day total", cost_daily: "Daily cost (bars) and cumulative (line)", cost_by_model: "By model", cost_empty: "No priced usage yet (model prices come from the models.dev catalog)", orch_accounts: "Adapter accounts", orch_accounts_hint: "Bots logged in per platform; with multiple accounts on one platform, sessions are isolated per @account", orch_accounts_empty: "No connected adapters", acct_filter_all: "All accounts", acct_sessions_unit: "sessions", acct_multi: "multi-account isolation", acct_offline: "Offline isolated accounts", nav_storage: "Storage", storage_desc: "Everything in the database: browse / clean / reset", storage_total: "Total", storage_slim: "Slim", storage_reset: "Reset all…", storage_empty: "Storage is empty", storage_domain: "Domain", storage_count: "Entries", storage_size: "Size", storage_browse: "Browse keys", storage_clear: "Clear", storage_confirm_clear: "Clear \"{d}\"? All data in this domain will be deleted", storage_cleared: "Cleaned {n} items", storage_keys_title: "Key browser", storage_keys_hint: "Expand a domain above; its keys are listed here — view content or delete", storage_no_keys: "No keys in this domain", storage_key_col: "Key", storage_truncated: "Content too long, truncated", storage_reset_hint: "Check the domains to KEEP; unchecked ones will be wiped", storage_reset_warn: "Reset cannot be undone; keep model config to avoid re-entering API keys", storage_reset_confirm: "Run the full reset?", storage_slim_done: "Slimmed {n} sessions", storage_d_sessions: "Session contexts", storage_d_memories: "Memories", storage_d_profiles: "User profiles", storage_d_personas: "Personas & bindings", storage_d_knowledge: "Knowledge base", storage_d_audit: "Audit log", storage_d_usage: "Usage records", storage_d_tasks: "Scheduled tasks", storage_d_participation: "Participation", storage_d_shares: "Session shares", storage_d_trash: "Trash", storage_d_recall: "Recall index", storage_d_pending: "Pending sends", storage_d_models: "Model config", storage_d_mcp: "MCP config", storage_d_docs: "Docs cache", storage_d_docs_cache: "Docs cache dir", storage_d_uploads: "Uploads", storage_d_work: "Work sandbox", storage_d_settings: "UI settings", storage_d_other: "Other",
      overview_desc: "agent runtime at a glance", overview_detail: "Details",
      stat_models: "Models", stat_tools: "Tools", stat_eco: "Eco tools", stat_sessions: "Sessions",
      stat_tasks: "Tasks", stat_mcp: "MCP", stat_extensions: "Extensions", stat_security: "Security",
      on: "on", off: "off", takeovers: "Takeovers", trust_on: "Full trust",
      chat_desc: "test the agent directly", chat_placeholder: "Say something…", chat_send: "Send",
      chat_thinking: "thinking…", chat_thought: "Thought", subagent_chip: "sub-agent", chat_resumed_running: "Reattached to the reply still running", chat_edit_only: "Save only", chat_edit_send: "Save & send", chat_edit_hint: "Save only edits this message; Save & send drops everything after it and asks again with the new content", chat_edit_cut: "Delete from here", chat_edit_cut_confirm: "Delete this message and everything after it?", chat_empty_send: "Content cannot be empty", chat_empty: "No conversation yet",
      settings_sec_model_basic: "Basic",
      settings_sec_model_reliable: "Reliability & task routing",
      settings_sec_model_routing: "Difficulty routing",
      settings_sec_trigger_reply: "Triggers",
      settings_sec_trigger_prefix: "Wake prefixes",
      settings_sec_tools_limits: "Limits",
      settings_sec_tools_behavior: "Behavior & self-heal",
      settings_sec_tools_select: "Dynamic tool injection",
      settings_sec_tools_web: "Web tools",
      settings_sec_mcp_conn: "Connection",
      settings_sec_mcp_docs: "Built-in docs",
      settings_sec_eco_scope: "Bridging scope",
      settings_sec_eco_access: "Access overrides",
      settings_sec_memory_basic: "Long-term memory",
      settings_sec_memory_profile: "User profile",
      settings_sec_kb_inject: "Retrieval injection",
      settings_sec_kb_lore: "Lorebook triggers",
      settings_sec_kb_embed: "Semantic search",
      settings_sec_skills_manage: "Skill management",
      settings_sec_skills_dev: "Development",
      settings_sec_hu_debounce: "Debounce & echo",
      settings_sec_hu_filter: "Output filter & recall",
      settings_sec_hu_more: "Interrupt & budget",
      settings_sec_sec_admin: "Admins & commands",
      settings_sec_sec_danger: "Dangerous ops",
      batch_select_all: "Select all",
      batch_delete: "Delete selected",
      batch_none_selected: "Select items first",
      batch_deleted: "Deleted {n}",
      batch_confirm: "Delete {n} selected?",
      organize_run: "AI organize",
      organize_running: "AI analyzing…",
      organize_done: "Done: {report}",
      organize_fail: "Failed: {error}",
      organize_noop: "Already tidy",
      audit_clear: "Clear audit",
      audit_clear_confirm: "Clear ALL audit entries?",
      audit_cleared: "Audit cleared",
      models_desc: "Any OpenAI-compatible provider, with failover", models_add: "Add / update model",
      models_name: "Name", models_id: "Model", models_temp: "Temperature", models_maxtok: "Max tokens", model_smart: "Auto config", model_smart_hint: "Fill context, capabilities and pricing from models.dev", model_context: "Context window", model_max_output: "Max output tokens", model_detect: "Detect from models.dev", model_detected: "Metadata filled from models.dev", model_detect_empty: "Not found on models.dev; fill manually", model_advanced: "Advanced", model_input_types: "Input types", model_input_text: "Text", model_input_image: "Image", model_input_video: "Video", model_input_pdf: "PDF", model_caps: "Capabilities", model_tool_call: "Tool calling", model_reasoning: "Reasoning", model_price: "Price (per 1M tokens)", model_price_in: "Input", model_price_out: "Output", model_enabled: "Enable this model", model_manage: "Models", model_refresh: "Refresh capabilities & prices", model_refresh_done: "Updated {n} fields", model_delete_confirm: "Delete this model?", model_cap_tools: "tools", model_cap_no_tools: "no tools", model_cap_vision: "vision", model_cap_reason: "reasoning", model_unknown: "unknown", orch_chain_top_no_tools: "The first model is not marked for tool calling; tool-enabled chats will skip it. Fill its capabilities in Model Pool or enable it manually.", model_none: "No models yet", model_add_title: "Add model", model_edit_title: "Edit model config", models_key_col: "key", models_auto_enrich_note: "Capabilities and pricing are auto-filled from models.dev after saving; fine-tune each model in Models", models_meta_note: "Edit capabilities/pricing under Models; saving here won't touch the model list.", batch_result: "{ok} ok, {fail} failed", backup_import_confirm: "Import will merge/overwrite: {sections}. Continue?", regen: "Regenerate", session_rename: "Rename session", session_name_label: "Session name", session_rename_ph: "empty = default", list_load_failed: "Failed to load", retry: "Retry", settings_show_keys: "Show field keys", load_more: "Load more",
      save: "Save", actions: "Actions", test: "Test", edit: "Edit", del: "Delete",
      models_empty: "Model pool is empty, add one", model_test_ok: "model works", model_test_fail: "model failed",
      saved: "Saved", deleted: "Deleted", confirm_del: "Delete this?",
      personas_desc: "System prompt + tool whitelist", personas_edit: "Edit persona",
      personas_pid: "Persona id", personas_pname: "Name", personas_system: "System prompt",
      personas_tools: "Tool whitelist (comma separated, empty = all, eco_* allowed)",
      personas_builtin: "builtin", personas_empty: "No custom personas yet",
      bindings: "Session bindings", bind_btn: "Bind", bind_hint: "chat_key (e.g. onebot11:group:123)", bind_tiers_hint: "Binding tiers (most specific first, first match wins): session chat_key → group (onebot11:group:123) → @account → platform (onebot11:*) → global default", bind_key_col: "Bound to", bind_none: "No bindings (sessions without a binding use the global default persona)", unbind: "Unbind", bind_tier_session: "session", bind_tier_account: "account", bind_tier_platform: "platform", bind_scope_chat: "This chat", bind_scope_group: "Whole group", bind_scope_account: "This account", bind_scope_platform: "Whole platform", bind_scope_custom: "Custom", bind_preview: "Will use \"{persona}\" for [{tier}] {key}", bind_preview_hint: "Pick a scope or use the shortcuts above; the binding applies to every chat in that scope without its own binding", bind_need_target: "Choose a binding target first",
      tools_desc: "Built-in, eco bridge and MCP tools", tools_refresh: "Refresh eco bridge",
      tools_filter: "Filter…", tools_empty: "No matching tools",
      extensions_desc: "Tools and personas from external modules", ext_none: "No extensions yet: a module declaring meta.services is wired in automatically", ext_personas_col: "Personas", ext_schemas_col: "Schemas",
      tasks_desc: "Tasks created by the agent", tasks_empty: "No scheduled tasks",
      col_next: "Next run", col_target: "Target", col_prompt: "Prompt", col_schedule: "Schedule",
      memory_desc: "long-term memory scopes", memory_pick: "click a scope to list entries", memory_clear: "Clear",
      memory_empty: "No memories in this scope",
      profile_card_title: "User Profile", profile_card_user: "User", profile_card_empty: "No profile yet",
      profile_card_clear: "Clear Profile", profile_card_confirm: "Clear this user's profile?", memory_importance: "Importance", health_reset: "Reset", trash_page: "Trash", trash_hint: "Staged deletes awaiting undo; auto-purged after retention", trash_expires: "Expires in", trash_days: "d", trash_restore: "Restore", trash_empty: "Trash is empty", panel_title: "Quick jump", panel_ph: "Search sessions / pages / settings…", panel_none: "No matches", profile_sec_traits: "Traits", chat_pin_s: "Pinned", profile_sec_preferences: "Preferences", profile_sec_facts: "Facts", profile_updated: "Updated",
      sessions_desc: "Sessions and persona bindings", sessions_empty: "No sessions",
      col_turns: "Turns", col_updated: "Updated", reset_btn: "Reset", col_persona: "Persona",
      audit_desc: "Operation and confirmation log", audit_empty: "No audit records",
      col_tool: "Tool", col_detail: "Detail",
      settings_desc: "runtime configuration, applied on save", settings_saved: "Config saved",
      group_model: "Model", group_trigger: "Trigger", group_security: "Security", group_chat: "Chat", group_humanize: "Humanize", group_memory: "Memory",
      group_tools: "Tools", group_eco: "Eco", group_mcp: "MCP", group_task: "Task", group_access: "Access", group_usage: "Usage", group_plugin: "Plugins",
      usage_title: "Usage trend", usage_tokens: "tokens", usage_calls: "Calls", usage_total: "Total (14d)",
      usage_avg: "Daily avg", usage_today: "Today", usage_limit: "Daily limit", usage_empty: "No usage data in the last 14 days",
      hero_title: "Hey, I'm here", hero_no_limit: "No daily limit set",
      recent_sessions: "Recent sessions", upcoming_tasks: "Upcoming tasks",
      login_hint: "Enter the access token", login_placeholder: "access token", login_btn: "Enter", login_failed: "Invalid token",
      col_time: "Time", col_user: "User", col_origin: "Origin", col_chatkey: "Session", col_count: "Count", col_id: "ID",
      ext_module: "Module", mcp_transport: "Transport",
      audit_total: "Records", audit_tools_n: "Tools", audit_users_n: "Users", audit_last24h: "Last 24h",
      audit_copy: "Copy JSON", audit_copied: "Copied",
      chat_attach: "Attach files", chat_skills: "Skills", chat_mcp: "Pick MCP tools", chat_clear: "Clear session",
      chat_clear_confirm: "Clear the context of this session?", chat_file_bad: "File could not be read:", chat_file_big: "File too large:", chat_img_limit: "Up to 3 images",
      chat_err: "Send failed", chat_follow: "Follow session binding", chat_default_session: "Web chat",
      models_preset: "Provider preset", models_baseurl: "Base URL", models_apikey: "API Key",
      models_fetch: "Fetch models", models_fetching: "Fetching…", models_fetch_fail: "Fetch failed", models_remote_empty: "No models found",
      nav_skills: "Skills", skills_desc: "Reusable instruction templates: pick them in chat, auto-loaded when a task matches",
      skills_add: "New skill", skills_edit: "Edit skill", skills_name: "Name", skills_description: "Description", skills_body: "Body",
      skills_export: "Export", skills_import: "Import", skills_empty: "No skills yet — create one or drop .md files into the skills dir",
      skills_source: "Source",
      personas_reset: "Reset to default", personas_modified: "customized", sessions_msgs: "Messages", yesterday: "Yesterday", tomorrow: "Tomorrow", personas_new: "New persona", mcp_add: "Add server", cancel: "Cancel", mcp_command: "Command", mcp_args: "Arguments (one per line)", mcp_headers: "Headers (JSON)", mcp_server: "Server",
      hero_dawn_1: "Morning! Where shall we start today?", hero_dawn_2: "Good morning, I'm all set", hero_dawn_3: "Up early — want to chat?", hero_morning_1: "Good morning! What's on your mind?", hero_morning_2: "I'm here whenever you're ready", hero_morning_3: "Any plans today? Tell me about them", hero_noon_1: "Lunch yet? Don't skip it", hero_noon_2: "Take a break, I'll hold the fort", hero_noon_3: "Good food, good mood, good work", hero_afternoon_1: "Afternoon! A little chat beats more coffee", hero_afternoon_2: "Tea time? You've earned it", hero_afternoon_3: "Don't push too hard — pause when you need", hero_evening_1: "Evening! How was your day?", hero_evening_2: "You're back — good work today", hero_evening_3: "Night mode: thoughts unloading welcome", hero_late_1: "Still up?", hero_late_2: "It's late — rest soon, okay?", hero_late_3: "Can't sleep? Talk to me",
      nav_group_run: "Runtime", group_kb: "Knowledge", group_skills: "Skills", group_other: "Other",
      settings_search_ph: "Search settings…", settings_no_match: "No matching settings", settings_invalid_value: "Invalid value — please fix", settings_json_bad: "Invalid JSON", settings_no_change: "No changes to save", settings_danger_confirm: "You are about to change security-related settings. Continue?", settings_unsaved: "There are unsaved setting changes. Leave and discard them?", settings_save_partial: "These fields failed validation and were not saved", settings_dangerous: "danger", settings_show: "Show", settings_hide: "Hide", settings_list_add: "Add item", plugin_settings_empty: "No plugins with settings yet: a plugin exposing the qvq_settings service appears here",
      settings_sec_context: "Context & compaction", settings_sec_forward: "Merged forward", settings_sec_reply: "Split replies", settings_sec_flow: "Runtime policy", settings_sec_misc: "Other",
      backup_title: "Data backup", backup_desc: "Export a full backup with providers, personas, tasks, memory, MCP, skills and all settings; imports are validated per item before applying.", backup_export_data: "Export data backup", backup_import_data: "Import data backup",
      orch_timeline_att: "Only running / failed tasks and runs are shown",
      loading: "Loading…"
    },
    "ja": {
      load_older: "以前のメッセージを読み込む", load_more: "さらに読み込む", undo: "元に戻す", search_ph: "検索…",
      nav_group_core: "コア", nav_group_config: "機能", nav_group_data: "データ", nav_mcp: "MCP", mcp_desc: "Model Context Protocol サーバーとツール接続", mcp_servers: "サーバー", mcp_tools: "MCP ツール", mcp_connect_all: "全て接続", mcp_connect: "接続", mcp_disconnect: "切断", mcp_status_on: "接続済", mcp_status_off: "未接続", mcp_none: "MCP サーバー未登録 — ここをクリックして追加", queue_send_now: "今すぐ送信", queue_added: "一時保存しました。現在の返信後に自動送信します", queue_edit: "入力欄に戻して編集", queue_badge: "待ち", chat_delete: "削除", session_delete_confirm: "このセッションを削除しますか？元に戻せません", session_deleted: "削除しました", chat_purge_archived: "アーカイブ済みを一括削除", chat_stop: "生成を停止", chat_cancelled: "（生成を停止しました）", chat_settings: "セッション設定", settings_save_session: "このセッションに保存", settings_apply_all: "全セッションに適用", share_export: "Markdown をエクスポート", chat_persona_binding: "ペルソナ固定", chat_export: "セッションをエクスポート", chat_share: "セッションを共有", share_expires: "リンク有効期限", share_max_tokens: "最大トークン（見える文脈の予算）", share_create: "共有リンクを作成", share_url: "共有リンク", share_hint: "このリンクを知る人は誰でもセッションを読み取り専用で閲覧できます（トークン予算と有効期限で制限）。いつでも取り消せます。", share_rounds: "訪問者が会話を続けられる回数（0 = 閲覧のみ）", share_rounds_hint: "訪問者はツールなしのテキストのみ・非管理者として続行します。回数または残高を使い切ると停止", share_chat_tokens: "続きに使えるトークン上限", role_user: "ユーザー", model_s_auto: "自動", effort_s_auto: "既定", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "ツール/スキルを指名（AI が優先使用）", chat_model: "モデル切替", chat_effort: "思考レベル", model_auto: "モデル自動選択", effort_auto: "レベル既定", effort_low: "レベル低", effort_mid: "レベル中", effort_high: "レベル高", mention_ok: "完了", mention_none: "指名できるスキルや MCP ツールがありません", confirm_title: "操作の確認", confirm_yes: "OK", chat_pasted: "添付を貼り付けました", chat_pin: "固定", chat_unpin: "固定解除", chat_archive: "アーカイブ", chat_unarchive: "アーカイブ解除", chat_archived: "アーカイブ済み", chat_hero_sub: "何を話す？下から選んでもいいよ", chat_chip_1: "Python の小さなスクリプトを書いて", chat_chip_2: "今日のチャットを日報にまとめて", chat_chip_3: "このエラーメッセージを解説して", chat_chip_4: "毎晩9時に日記をリマインドして", chat_new: "新しいチャット", chat_new_name: "ウェブチャット {n}", chat_busy: "このセッションは返信中です", chat_trigger: "トリガールール", trigger_follow: "グローバルに従う", trigger_all: "すべて", trigger_at: "メンションのみ", trigger_lurk: "覗き見（返信なし）", trigger_off: "オフ", listen_off_toggle: "プライバシー：このチャットの監視を停止（傍受と割り込みを受け取らなくなります）", chat_density: "表示密度", density_brief: "簡潔", density_detail: "詳細", steps_count: "ツール呼び出し {n}件", steps_running: "実行中…", copy: "コピー", copied: "コピーしました", msgs_count: "{n} 件のメッセージ", session_summary: "コンテキスト要約",
      stat_usage: "今日の使用量", backup_export: "設定をエクスポート", backup_import: "設定をインポート", audit_filter: "絞り込み…", col_preview: "最新メッセージ",
      subtitle: "汎用エージェント",
      nav_overview: "概要", nav_chat: "チャット", nav_models: "モデル", nav_personas: "ペルソナ",
      nav_tools: "ツール", nav_extensions: "拡張", nav_tasks: "タスク", nav_memory: "記憶", nav_sessions: "セッション",
      nav_knowledge: "ナレッジ", knowledge_desc: "共有ライブラリ：関連する断片は会話に自動注入され、knowledge_search でも検索できます", kb_add: "項目を追加", kb_search_ph: "検索…", kb_stats_line: "項目 {e} · チャンク {c}", kb_list_empty: "まだ項目がありません。上のボタンから追加してください", kb_title_label: "タイトル", kb_source_label: "ソース（任意）", kb_content_label: "内容", kb_need_title_content: "タイトルと内容が必要です", kb_triggers_label: "トリガーキーワード（任意・ワールドブック）", kb_triggers_ph: "例：魔王, 北塔（カンマ区切り、一致で注入）", kb_priority_label: "トリガー優先度（大きい順）", kb_cooldown_label: "トリガークールダウン分（空欄でデフォルト、0 で無効）", kb_edit: "項目を編集", kb_scope_label: "公開範囲", kb_scope_chat: "セッション/プラットフォーム（chat_key またはプラットフォーム名、例: bilibili）", kb_scope_ph: "空欄=グローバル", kb_scope_chip_private: "非公開",
      nav_audit: "監査", nav_settings: "設定",
      sess_members: "メンバー", sess_members_hint: "メンバー許可リスト（1 行に 1 つのユーザー ID、* は全員。空で全員に戻す）", sess_sources_hint: "他のセッションの入力を受け入れる（1 行に 1 つの chat_key、例 onebot11:group:123。そのメッセージはこのセッションに転送されます）", kb_export: "エクスポート", kb_import: "インポート",
      nav_orchestrate: "オーケストレーション", orchestrate_desc: "エージェント一覧：モデルチェーン · 正常性 · 実行状態 · タスクタイムライン", orch_model_chain: "モデルチェーン（フェイルオーバー順）", orch_chain_hint: "ドラッグでフェイルオーバー順を変更、離すと自動保存", orch_chain_saved: "チェーン順を保存しました", orch_health: "モデル正常性", health_ok: "すべてのモデルは正常", health_cooldown: "クールダウン中", health_fails: "連続 {n} 回失敗", health_left: "残り {s} 秒", orch_running: "実行状態", running_none: "実行中のタスクはありません", orch_timeline: "タスクタイムライン", timeline_empty: "タスクと実行履歴はまだありません", orch_capabilities: "機能スイッチ", caps_tools: "ツール", caps_skills: "スキル", task_next: "次回", task_last: "前回", task_status_error: "前回失敗", cost_title: "コスト概算", cost_total: "14 日合計", cost_daily: "日次コスト（棒）と累積（線）", cost_by_model: "モデル別", cost_empty: "単価付きの使用量はまだありません（モデル価格は models.dev カタログより）", orch_accounts: "アダプターアカウント", orch_accounts_hint: "各プラットフォームのログイン bot；同一プラットフォームで複数アカウントの場合は @アカウント で分離", orch_accounts_empty: "接続中のアダプターはありません", acct_filter_all: "すべてのアカウント", acct_sessions_unit: "セッション", acct_multi: "複数アカウント分離", acct_offline: "オフラインの分離アカウント", nav_storage: "ストレージ", storage_desc: "データベースの全内容：閲覧 / クリーン / リセット", storage_total: "合計", storage_slim: "スリム化", storage_reset: "全リセット…", storage_empty: "ストレージは空です", storage_domain: "ドメイン", storage_count: "件数", storage_size: "サイズ", storage_browse: "キー一覧", storage_clear: "クリア", storage_confirm_clear: "「{d}」をクリア？このドメインの全データが削除されます", storage_cleared: "{n} 件をクリーン", storage_keys_title: "キーブラウザ", storage_keys_hint: "ドメインを展開すると全キーがここに表示されます。内容の閲覧・削除が可能", storage_no_keys: "このドメインにキーはありません", storage_key_col: "キー", storage_truncated: "内容が長いため切り詰めました", storage_reset_hint: "【保持する】ドメインにチェック。未チェックのものは消去されます", storage_reset_warn: "全リセットは取り消せません。モデル設定を保持すれば API Key の再入力は不要です", storage_reset_confirm: "全リセットを実行しますか？", storage_slim_done: "{n} セッションをスリム化", storage_d_sessions: "セッション履歴", storage_d_memories: "メモリ", storage_d_profiles: "ユーザープロファイル", storage_d_personas: "ペルソナとバインド", storage_d_knowledge: "ナレッジベース", storage_d_audit: "監査ログ", storage_d_usage: "使用量", storage_d_tasks: "定期タスク", storage_d_participation: "参加判断", storage_d_shares: "セッション共有", storage_d_trash: "ごみ箱", storage_d_recall: "リコール索引", storage_d_pending: "送信待ち", storage_d_models: "モデル設定", storage_d_mcp: "MCP 設定", storage_d_docs: "ドキュメントキャッシュ", storage_d_docs_cache: "ドキュメントキャッシュディレクトリ", storage_d_uploads: "アップロード", storage_d_work: "作業サンドボックス", storage_d_settings: "UI 設定", storage_d_other: "その他",
      overview_desc: "エージェントの実行状況", overview_detail: "詳細",
      stat_models: "モデル", stat_tools: "ツール", stat_eco: "生態ツール", stat_sessions: "セッション",
      stat_tasks: "タスク", stat_mcp: "MCP", stat_extensions: "拡張", stat_security: "セキュリティ",
      on: "オン", off: "オフ", takeovers: "接管中のセッション", trust_on: "完全信頼",
      chat_desc: "エージェントを直接テスト", chat_placeholder: "何か話しかけて…", chat_send: "送信",

      chat_thinking: "思考中…", chat_thought: "思考済み", subagent_chip: "サブエージェント", chat_resumed_running: "実行中の返信に再接続しました", chat_edit_only: "保存のみ", chat_edit_send: "保存して送信", chat_edit_hint: "保存のみはこの1件だけ変更。保存して送信はこれ以降の返信を破棄して、新しい内容で再質問します", chat_edit_cut: "ここから削除", chat_edit_cut_confirm: "このメッセージと以降をすべて削除しますか？", chat_empty_send: "内容を入力してください", chat_empty: "まだ会話がありません",
      settings_sec_model_basic: "基本",
      settings_sec_model_reliable: "信頼性とタスク振分",
      settings_sec_model_routing: "難易度ルーティング",
      settings_sec_trigger_reply: "トリガー",
      settings_sec_trigger_prefix: "起床プレフィックス",
      settings_sec_tools_limits: "実行上限",
      settings_sec_tools_behavior: "挙動と自己修復",
      settings_sec_tools_select: "動的ツール注入",
      settings_sec_tools_web: "Web ツール",
      settings_sec_mcp_conn: "接続",
      settings_sec_mcp_docs: "内蔵ドキュメント",
      settings_sec_eco_scope: "ブリッジ範囲",
      settings_sec_eco_access: "権限上書き",
      settings_sec_memory_basic: "長期記憶",
      settings_sec_memory_profile: "ユーザープロファイル",
      settings_sec_kb_inject: "検索注入",
      settings_sec_kb_lore: "ロアブック",
      settings_sec_kb_embed: "意味検索",
      settings_sec_skills_manage: "スキル管理",
      settings_sec_skills_dev: "開発",
      settings_sec_hu_debounce: "デバウンスとエコー",
      settings_sec_hu_filter: "出力フィルタと想起",
      settings_sec_hu_more: "割込と予算",
      settings_sec_sec_admin: "管理者とコマンド",
      settings_sec_sec_danger: "危険操作",
      batch_select_all: "全選択",
      batch_delete: "選択削除",
      batch_none_selected: "先に選択してください",
      batch_deleted: "{n} 件削除",
      batch_confirm: "選択した {n} 件を削除？",
      organize_run: "AI 整理",
      organize_running: "AI 分析中…",
      organize_done: "完了：{report}",
      organize_fail: "失敗：{error}",
      organize_noop: "すでに整っています",
      audit_clear: "監査クリア",
      audit_clear_confirm: "全ての監査記録を削除？",
      audit_cleared: "クリアしました",
      models_desc: "OpenAI 互換エンドポイント、プール順にフェイルオーバー", models_add: "モデル追加 / 更新",
      models_name: "名前", models_id: "モデル名", models_temp: "温度", models_maxtok: "最大トークン", model_smart: "自動設定", model_smart_hint: "models.dev からコンテキスト・能力・価格を自動補完", model_context: "コンテキスト長", model_max_output: "最大出力トークン", model_detect: "models.dev から取得", model_detected: "models.dev のメタデータを反映しました", model_detect_empty: "models.dev に未収録です。手動で入力してください", model_advanced: "詳細設定", model_input_types: "入力タイプ", model_input_text: "テキスト", model_input_image: "画像", model_input_video: "動画", model_input_pdf: "PDF", model_caps: "モデル能力", model_tool_call: "ツール呼び出し", model_reasoning: "推論", model_price: "単価（100万トークンあたり）", model_price_in: "入力", model_price_out: "出力", model_enabled: "このモデルを有効化", model_manage: "モデル設定", model_refresh: "能力と価格を更新", model_refresh_done: "{n} 項目を更新しました", model_delete_confirm: "このモデルを削除しますか？", model_cap_tools: "ツール", model_cap_no_tools: "ツール不可", model_cap_vision: "視覚", model_cap_reason: "推論", model_unknown: "能力不明", orch_chain_top_no_tools: "先頭モデルに「ツール呼び出し」の印がありません。ツール有効の会話ではスキップされます。モデルプールで能力を補完するか手動で有効にしてください。", model_none: "モデルがまだありません", model_add_title: "モデル追加", model_edit_title: "モデル設定を編集", models_key_col: "key", models_auto_enrich_note: "保存後、models.dev から能力と価格を自動補完します。詳細は「モデル設定」で調整できます", models_meta_note: "能力/価格は「モデル設定」で編集してください。ここでの保存はモデル一覧を変更しません。", batch_result: "{ok} 件成功、{fail} 件失敗", backup_import_confirm: "インポートは以下のデータを統合/上書きします：{sections}。続行しますか？", regen: "再生成", session_rename: "セッション名変更", session_name_label: "セッション名", session_rename_ph: "空欄で既定表示に戻す", list_load_failed: "読み込みに失敗", retry: "再試行", settings_show_keys: "キー名を表示", load_more: "さらに読み込む",
      save: "保存", actions: "操作", test: "テスト", edit: "編集", del: "削除",
      models_empty: "モデルプールが空です", model_test_ok: "モデル OK", model_test_fail: "モデル NG",
      saved: "保存しました", deleted: "削除しました", confirm_del: "削除しますか？",
      personas_desc: "ペルソナ = システムプロンプト + ツール白名單", personas_edit: "ペルソナ編集",
      personas_pid: "ペルソナ id", personas_pname: "名前", personas_system: "システムプロンプト",
      personas_tools: "ツール白名單（カンマ区切り、空 = 全部、eco_* 可）",
      personas_builtin: "內置", personas_empty: "カスタムペルソナはまだありません",
      bindings: "セッション binding", bind_btn: "binding", bind_hint: "chat_key（例 onebot11:group:123）", bind_tiers_hint: "バインド階層（具体的なもの順、先頭一致が優先）：セッション chat_key → グループ（onebot11:group:123）→ @アカウント → プラットフォーム（onebot11:*）→ グローバル既定", bind_key_col: "バインド先", bind_none: "バインドなし（未バインドのセッションはグローバル既定ペルソナ）", unbind: "解除", bind_tier_session: "セッション", bind_tier_account: "アカウント", bind_tier_platform: "プラットフォーム", bind_scope_chat: "このセッション", bind_scope_group: "グループ全体", bind_scope_account: "このアカウント", bind_scope_platform: "プラットフォーム全体", bind_scope_custom: "カスタム", bind_preview: "【{tier}】{key} で「{persona}」を使用します", bind_preview_hint: "範囲を選ぶか上のショートカットを使用。その範囲内で個別バインドのないセッションに適用されます", bind_need_target: "先にバインド範囲を選択してください",
      tools_desc: "內置 + 生態サービス橋 + MCP", tools_refresh: "生態橋を更新",
      tools_filter: "絞り込み…", tools_empty: "該当ツールなし",
      extensions_desc: "外部モジュールのツールとペルソナ", ext_none: "拡張モジュールなし：meta.services を宣言すれば自動接続", ext_personas_col: "ペルソナ", ext_schemas_col: "Schema",
      tasks_desc: "create_scheduled_task で作成", tasks_empty: "タスクはありません",
      col_next: "次回", col_target: "対象", col_prompt: "内容", col_schedule: "スケジュール",
      memory_desc: "長期記憶のスコープ", memory_pick: "スコープをクリックで表示", memory_clear: "クリア",
      memory_empty: "記憶がありません",
      profile_card_title: "ユーザープロファイル", profile_card_user: "ユーザー", profile_card_empty: "プロファイルなし",
      profile_card_clear: "プロファイルを消去", profile_card_confirm: "このユーザーのプロファイルを消去しますか？", memory_importance: "重要度", health_reset: "リセット", trash_page: "ゴミ箱", trash_hint: "削除の取り消し期間中の一時保管。期限を過ぎると自動削除", trash_expires: "残り", trash_days: "日", trash_restore: "復元", trash_empty: "ゴミ箱は空です", panel_title: "クイックジャンプ", panel_ph: "セッション / ページ / 設定を検索…", panel_none: "該当なし", profile_sec_traits: "特徴", chat_pin_s: "ピン留め", profile_sec_preferences: "好み", profile_sec_facts: "事実", profile_updated: "最終更新",
      sessions_desc: "会話ウィンドウとペルソナ binding", sessions_empty: "セッションなし",
      col_turns: "ターン", col_updated: "更新", reset_btn: "リセット", col_persona: "ペルソナ",
      audit_desc: "PC 操作と確認の記錄", audit_empty: "監査記錄なし",
      col_tool: "ツール", col_detail: "詳細",
      settings_desc: "實行時設定、保存で即反映", settings_saved: "設定を保存しました",
      group_model: "モデル", group_trigger: "トリガー", group_security: "セキュリティ", group_chat: "チャット", group_humanize: "擬人化", group_memory: "記憶",
      group_tools: "ツール", group_eco: "エコ", group_mcp: "MCP", group_task: "タスク", group_access: "アクセス", group_usage: "使用量", group_plugin: "プラグイン",
      usage_title: "使用量の推移", usage_tokens: "token", usage_calls: "呼び出し", usage_total: "14 日間の合計",
      usage_avg: "1 日平均", usage_today: "今日", usage_limit: "1 日の上限", usage_empty: "直近 14 日間の使用量データはありません",
      hero_title: "やあ、ここにいるよ", hero_no_limit: "1 日の上限は未設定",
      recent_sessions: "最近のセッション", upcoming_tasks: "実行予定のタスク",
      login_hint: "アクセストークンを入力", login_placeholder: "access token", login_btn: "進入", login_failed: "トークンが無効です",
      col_time: "時刻", col_user: "ユーザー", col_origin: "発信元", col_chatkey: "セッション", col_count: "件数", col_id: "ID",
      ext_module: "モジュール", mcp_transport: "トランスポート",
      audit_total: "監査レコード", audit_tools_n: "ツール種別", audit_users_n: "ユーザー数", audit_last24h: "直近 24 時間",
      audit_copy: "JSON をコピー", audit_copied: "コピーしました",
      chat_attach: "添付ファイル", chat_skills: "スキル", chat_mcp: "MCP ツールを指定", chat_clear: "セッション消去",
      chat_clear_confirm: "このセッションのコンテキストを消去しますか？", chat_file_bad: "ファイルを読み込めません：", chat_file_big: "ファイルが大きすぎます：", chat_img_limit: "画像は最大 3 枚",
      chat_err: "送信失敗", chat_follow: "セッション binding に従う", chat_default_session: "ウェブチャット",
      models_preset: "プロバイダ プリセット", models_baseurl: "Base URL", models_apikey: "API Key",
      models_fetch: "モデル一覧を取得", models_fetching: "取得中…", models_fetch_fail: "取得失敗", models_remote_empty: "モデルが見つかりません",
      nav_skills: "スキル", skills_desc: "再利用可能な指示テンプレート：チャットで選択可能、タスク一致時に自動読込",
      skills_add: "スキル追加", skills_edit: "スキル編集", skills_name: "名前", skills_description: "説明", skills_body: "内容",
      skills_export: "エクスポート", skills_import: "インポート", skills_empty: "スキルがありません。作成するか .md をスキルディレクトリへ",
      skills_source: "提供元",
      personas_reset: "デフォルトに戻す", personas_modified: "変更済み", sessions_msgs: "メッセージ", yesterday: "昨日", tomorrow: "明日", personas_new: "ペルソナ追加", mcp_add: "サーバー追加", cancel: "キャンセル", mcp_command: "コマンド", mcp_args: "引数（1行ずつ）", mcp_headers: "ヘッダー（JSON）", mcp_server: "サーバー",
      hero_dawn_1: "おはよう！今日は何から始める？", hero_dawn_2: "おはよう、もう準備できてるよ", hero_dawn_3: "早起だね、話でもする？", hero_morning_1: "おはよう！何か話したいことある？", hero_morning_2: "いつでも付き合うよ", hero_morning_3: "今日の予定、聞かせて", hero_noon_1: "昼ごはん食べた？", hero_noon_2: "少し休んで、ここは任せて", hero_noon_3: "昼寝の時間かもね", hero_afternoon_1: "やあ！眠い時はおしゃべりが一番", hero_afternoon_2: "お茶でも飲む？", hero_afternoon_3: "無理しないでね", hero_evening_1: "こんばんは、今日どうだった？", hero_evening_2: "おかえり、お疲れさま", hero_evening_3: "夜トーク、始めようか", hero_late_1: "まだ起きてるの？", hero_late_2: "もう遅いよ、そろそろ寝よう", hero_late_3: "眠れないなら話相手になるよ",
      nav_group_run: "実行", group_kb: "ナレッジ", group_skills: "スキル", group_other: "その他",
      settings_search_ph: "設定項を検索…", settings_no_match: "一致する設定項はありません", settings_invalid_value: "値が無効です。修正してください", settings_json_bad: "JSON 形式エラー", settings_no_change: "変更はありません", settings_danger_confirm: "セキュリティ関連の設定を変更しようとしています。続行しますか？", settings_unsaved: "未保存の設定変更があります。破棄して離れますか？", settings_save_partial: "以下の項目が検証に失敗したため保存されませんでした", settings_dangerous: "危険", settings_show: "表示", settings_hide: "非表示", settings_list_add: "項目を追加", plugin_settings_empty: "設定可能なプラグインはまだありません：qvq_settings サービスを提供するとここに表示されます",
      settings_sec_context: "コンテキストと圧縮", settings_sec_forward: "まとめ転送", settings_sec_reply: "分割返信", settings_sec_flow: "実行ポリシー", settings_sec_misc: "その他",
      backup_title: "データバックアップ", backup_desc: "モデルプール・ペルソナ・タスク・記憶・MCP・スキル・全設定を含む完全バックアップをエクスポートします。インポートは項目ごとに検証されてから適用されます。", backup_export_data: "データバックアップをエクスポート", backup_import_data: "データバックアップをインポート",
      orch_timeline_att: "実行中 / 失敗のタスクと実行記録のみ表示",
      loading: "読み込み中…"
    },
    "ru": {
      nav_group_core: "Ядро", nav_group_config: "Возможности", nav_group_data: "Данные", nav_mcp: "MCP", mcp_desc: "Серверы и инструменты Model Context Protocol", mcp_servers: "Серверы", mcp_tools: "MCP-инструменты", mcp_connect_all: "Подключить все", mcp_connect: "Подключить", mcp_disconnect: "Отключить", mcp_status_on: "подключен", mcp_status_off: "отключен", mcp_none: "MCP-серверов пока нет — нажмите, чтобы добавить", queue_send_now: "Отправить сейчас", queue_added: "В очереди — отправится после текущего ответа", queue_edit: "Вернуть в поле ввода", queue_badge: "В очереди", chat_delete: "Удалить", session_delete_confirm: "Удалить эту сессию? Действие необратимо", session_deleted: "Удалено", chat_purge_archived: "Очистить архив", chat_stop: "Остановить генерацию", chat_cancelled: "(генерация остановлена)", chat_settings: "Настройки сессии", settings_save_session: "Сохранить в эту сессию", settings_apply_all: "Применить ко всем", share_export: "Экспорт Markdown", chat_persona_binding: "Привязка персоны", chat_export: "Экспорт сессии", chat_share: "Поделиться сессией", share_expires: "Срок действия ссылки", share_max_tokens: "Максимум токенов (бюджет видимого контекста)", share_create: "Создать ссылку", share_url: "Ссылка для обмена", share_hint: "Любой с этой ссылкой может читать сессию (лимиты: бюджет токенов и срок). Можно отозвать в любой момент.", share_rounds: "Сколько раундов гость может продолжить чат (0 = только чтение)", share_rounds_hint: "Гость продолжает чат обычным текстом без инструментов и прав администратора; при исчерпании раундов или лимита — стоп", share_chat_tokens: "Лимит токенов на продолжение", role_user: "Пользователь", model_s_auto: "Авто", effort_s_auto: "Авто", effort_s_low: "Низк", effort_s_mid: "Сред", effort_s_high: "Высок", chat_mention: "Упомянуть инструменты/навыки (ИИ приоритизирует)", chat_model: "Сменить модель", chat_effort: "Уровень усилий", model_auto: "Авто-выбор модели", effort_auto: "Усилия: авто", effort_low: "Усилия: низкие", effort_mid: "Усилия: средние", effort_high: "Усилия: высокие", mention_ok: "Готово", mention_none: "Нет навыков или MCP-инструментов для упоминания", confirm_title: "Подтверждение", confirm_yes: "OK", chat_pasted: "Вложение вставлено", chat_pin: "Закрепить", chat_unpin: "Открепить", chat_archive: "В архив", chat_unarchive: "Из архива", chat_archived: "В архиве", chat_hero_sub: "О чём поболтаем? Или выбери тему ниже", chat_chip_1: "Напиши мне небольшой скрипт на Python", chat_chip_2: "Собери из чата отчёт за день", chat_chip_3: "Объясни эту ошибку", chat_chip_4: "Напоминай мне вести дневник в 21:00", chat_new: "Новый чат", chat_new_name: "Веб-чат {n}", chat_busy: "Эта сессия ещё отвечает", chat_trigger: "Правило отклика", trigger_follow: "Как в глобальных", trigger_all: "Все", trigger_at: "Только упоминания", trigger_lurk: "Наблюдать (без ответов)", trigger_off: "Выключено", listen_off_toggle: "Приватность: не слушать этот чат (наблюдатели и реплики больше не получают его сообщения)", chat_density: "Детализация", density_brief: "Кратко", density_detail: "Подробно", steps_count: "{n} вызовов инструмента", steps_running: "выполняется…", copy: "Копировать", copied: "Скопировано", msgs_count: "{n} сообщений", session_summary: "Сводка контекста",
      stat_usage: "Расход сегодня", backup_export: "Экспорт конфига", backup_import: "Импорт конфига", audit_filter: "Фильтр инструмента/пользователя…", col_preview: "Последнее сообщение",
      subtitle: "универсальный агент",
      nav_overview: "Обзор", nav_chat: "Чат", nav_models: "Модели", nav_personas: "Личности",
      nav_tools: "Инструменты", nav_extensions: "Расширения", nav_tasks: "Задачи", nav_memory: "Память", nav_sessions: "Сессии",
      nav_knowledge: "База знаний", knowledge_desc: "Общая библиотека: подходящие фрагменты автоматически попадают в диалог, доступен поиск через knowledge_search", kb_add: "Добавить запись", kb_search_ph: "Поиск…", kb_stats_line: "Записей: {e} · Фрагментов: {c}", kb_list_empty: "Записей пока нет — добавьте через кнопку выше", kb_title_label: "Заголовок", kb_source_label: "Источник (необязательно)", kb_content_label: "Содержимое", kb_need_title_content: "Нужны заголовок и содержимое", kb_triggers_label: "Ключевые слова триггера (опционально, лорбук)", kb_triggers_ph: "напр.: демон, башня (через запятую)", kb_priority_label: "Приоритет триггера (выше — раньше)", kb_cooldown_label: "Кулдаун триггера, мин (пусто — по умолчанию, 0 — нет)", kb_edit: "Изменить запись", kb_scope_label: "Область видимости", kb_scope_chat: "Сессия/платформа (chat_key или имя платформы, напр. bilibili)", kb_scope_ph: "пусто = глобально", kb_scope_chip_private: "приватно",
      nav_audit: "Аудит", nav_settings: "Настройки",
      sess_members: "Участники", sess_members_hint: "Белый список участников (один ID в строке, * = все; пусто — вернуть всех)", sess_sources_hint: "Принимать ввод из других чатов (один chat_key в строке, напр. onebot11:group:123; их сообщения направляются в этот чат)", kb_export: "Экспорт", kb_import: "Импорт",
      nav_orchestrate: "Оркестрация", orchestrate_desc: "Обзор агента: цепочка моделей · здоровье · выполнение · время задач", orch_model_chain: "Цепочка моделей (порядок failover)", orch_chain_hint: "Перетащите, чтобы изменить порядок failover; сохраняется автоматически", orch_chain_saved: "Порядок цепочки сохранён", orch_health: "Здоровье моделей", health_ok: "Все модели исправны", health_cooldown: "Охлаждение", health_fails: "Подряд сбоев: {n}", health_left: "Осталось {s} с", orch_running: "Выполнение", running_none: "Нет запущенных задач", orch_timeline: "Время задач", timeline_empty: "Задач и запусков пока нет", orch_capabilities: "Переключатели возможностей", caps_tools: "Инструменты", caps_skills: "Навыки", task_next: "Далее", task_last: "Прошлый", task_status_error: "Прошлый запуск не удался", cost_title: "Оценка расходов", cost_total: "Сумма за 14 дней", cost_daily: "Расходы по дням (столбцы) и накопительно (линия)", cost_by_model: "По моделям", cost_empty: "Нет данных с ценами (цены моделей из каталога models.dev)", orch_accounts: "Аккаунты адаптеров", orch_accounts_hint: "Боты, вошедшие на платформах; при нескольких аккаунтах на одной платформе сессии изолируются по @аккаунту", orch_accounts_empty: "Нет подключённых адаптеров", acct_filter_all: "Все аккаунты", acct_sessions_unit: "сессий", acct_multi: "изоляция аккаунтов", acct_offline: "Оффлайн-аккаунты с изоляцией", nav_storage: "Хранилище", storage_desc: "Всё содержимое базы: просмотр / очистка / сброс", storage_total: "Всего", storage_slim: "Сжать", storage_reset: "Полный сброс…", storage_empty: "Хранилище пусто", storage_domain: "Домен", storage_count: "Записей", storage_size: "Размер", storage_browse: "Ключи", storage_clear: "Очистить", storage_confirm_clear: "Очистить «{d}»? Все данные домена будут удалены", storage_cleared: "Очищено: {n}", storage_keys_title: "Браузер ключей", storage_keys_hint: "Раскройте домен — здесь появятся все его ключи: просмотр и удаление", storage_no_keys: "В домене нет ключей", storage_key_col: "Ключ", storage_truncated: "Содержимое слишком длинное, обрезано", storage_reset_hint: "Отметьте домены для 【сохранения】; неотмеченные будут стёрты", storage_reset_warn: "Сброс необратим; сохраните конфигурацию моделей, чтобы не вводить API-ключи заново", storage_reset_confirm: "Выполнить полный сброс?", storage_slim_done: "Сжато сессий: {n}", storage_d_sessions: "Контексты сессий", storage_d_memories: "Память", storage_d_profiles: "Профили пользователей", storage_d_personas: "Персонажи и привязки", storage_d_knowledge: "База знаний", storage_d_audit: "Журнал аудита", storage_d_usage: "Использование", storage_d_tasks: "Задачи", storage_d_participation: "Участие", storage_d_shares: "Ссылки сессий", storage_d_trash: "Корзина", storage_d_recall: "Индекс напоминаний", storage_d_pending: "Очередь отправки", storage_d_models: "Конфиг моделей", storage_d_mcp: "Конфиг MCP", storage_d_docs: "Кэш документации", storage_d_docs_cache: "Каталог кэша док.", storage_d_uploads: "Загрузки", storage_d_work: "Рабочая песочница", storage_d_settings: "Настройки интерфейса", storage_d_other: "Другое",
      overview_desc: "Обзор состояния агента", overview_detail: "Подробности",
      stat_models: "Модели", stat_tools: "Инструменты", stat_eco: "Эко-инстр.", stat_sessions: "Сессии",
      stat_tasks: "Задачи", stat_mcp: "MCP", stat_extensions: "Расширения", stat_security: "Безопасность",
      on: "вкл", off: "выкл", takeovers: "Под контролем", trust_on: "Полное доверие",
      chat_desc: "прямой тест агента, инструменты доступны", chat_placeholder: "Скажите что-нибудь…", chat_send: "Отправить",
      chat_thinking: "думаю…", chat_thought: "Подумал", subagent_chip: "субагент", chat_resumed_running: "Переподключено к выполняющемуся ответу", chat_edit_only: "Только сохранить", chat_edit_send: "Сохранить и отправить", chat_edit_hint: "«Только сохранить» меняет одно сообщение; «Сохранить и отправить» удаляет всё после него и повторяет запрос с новым текстом", chat_edit_cut: "Удалить отсюда", chat_edit_cut_confirm: "Удалить это сообщение и всё после него?", chat_empty_send: "Содержимое не может быть пустым", chat_empty: "Диалогов пока нет",
      settings_sec_model_basic: "Базовое",
      settings_sec_model_reliable: "Надёжность и задачи",
      settings_sec_model_routing: "Маршрутизация по сложности",
      settings_sec_trigger_reply: "Триггеры",
      settings_sec_trigger_prefix: "Префиксы пробуждения",
      settings_sec_tools_limits: "Лимиты",
      settings_sec_tools_behavior: "Поведение и самолечение",
      settings_sec_tools_select: "Динамическая инъекция",
      settings_sec_tools_web: "Веб-инструменты",
      settings_sec_mcp_conn: "Соединение",
      settings_sec_mcp_docs: "Встроенная документация",
      settings_sec_eco_scope: "Область моста",
      settings_sec_eco_access: "Переопределение прав",
      settings_sec_memory_basic: "Долгая память",
      settings_sec_memory_profile: "Профиль пользователя",
      settings_sec_kb_inject: "Инъекция поиска",
      settings_sec_kb_lore: "Триггеры лорбука",
      settings_sec_kb_embed: "Семантический поиск",
      settings_sec_skills_manage: "Управление навыками",
      settings_sec_skills_dev: "Разработка",
      settings_sec_hu_debounce: "Антидребезг и эхо",
      settings_sec_hu_filter: "Фильтр и припоминание",
      settings_sec_hu_more: "Прерывание и бюджет",
      settings_sec_sec_admin: "Админы и команды",
      settings_sec_sec_danger: "Опасные операции",
      batch_select_all: "Выбрать все",
      batch_delete: "Удалить выбранное",
      batch_none_selected: "Сначала выберите элементы",
      batch_deleted: "Удалено: {n}",
      batch_confirm: "Удалить выбранные ({n})?",
      organize_run: "AI-организация",
      organize_running: "AI анализирует…",
      organize_done: "Готово: {report}",
      organize_fail: "Ошибка: {error}",
      organize_noop: "Всё уже в порядке",
      audit_clear: "Очистить аудит",
      audit_clear_confirm: "Очистить ВСЕ записи?",
      audit_cleared: "Аудит очищен",
      models_desc: "OpenAI-совместимые endpoint'ы с failover по пулу", models_add: "Добавить / обновить модель",
      models_name: "Имя", models_id: "Модель", models_temp: "Температура", models_maxtok: "Макс. токенов", model_smart: "Автонастройка", model_smart_hint: "Заполнить контекст, возможности и цену из models.dev", model_context: "Контекстное окно", model_max_output: "Макс. выходных токенов", model_detect: "Определить из models.dev", model_detected: "Метаданные заполнены из models.dev", model_detect_empty: "Нет в models.dev — заполните вручную", model_advanced: "Дополнительно", model_input_types: "Типы ввода", model_input_text: "Текст", model_input_image: "Изображение", model_input_video: "Видео", model_input_pdf: "PDF", model_caps: "Возможности модели", model_tool_call: "Вызов инструментов", model_reasoning: "Рассуждение", model_price: "Цена (за 1M токенов)", model_price_in: "Ввод", model_price_out: "Вывод", model_enabled: "Включить модель", model_manage: "Модели", model_refresh: "Обновить возможности и цены", model_refresh_done: "Обновлено полей: {n}", model_delete_confirm: "Удалить эту модель?", model_cap_tools: "инструменты", model_cap_no_tools: "без инструментов", model_cap_vision: "зрение", model_cap_reason: "рассуждение", model_unknown: "неизвестно", orch_chain_top_no_tools: "У первой модели не отмечен вызов инструментов; диалоги с инструментами её пропустят. Заполните возможности в пуле моделей или включите вручную.", model_none: "Моделей пока нет", model_add_title: "Добавить модель", model_edit_title: "Настройка модели", models_key_col: "key", models_auto_enrich_note: "После сохранения возможности и цены автоматически заполняются из models.dev; точная настройка — в разделе «Модели»", models_meta_note: "Возможности и цены редактируются в разделе «Модели»; сохранение здесь не меняет список моделей.", batch_result: "Успешно: {ok}, с ошибками: {fail}", backup_import_confirm: "Импорт объединит/перезапишет: {sections}. Продолжить?", regen: "Перегенерировать", session_rename: "Переименовать", session_name_label: "Название сессии", session_rename_ph: "пусто = по умолчанию", list_load_failed: "Не удалось загрузить", retry: "Повторить", settings_show_keys: "Показывать ключи", load_more: "Показать ещё", undo: "Отменить", search_ph: "Поиск…",
      save: "Сохранить", actions: "Действия", test: "Тест", edit: "Правка", del: "Удалить",
      models_empty: "Пул моделей пуст, добавьте", model_test_ok: "модель работает", model_test_fail: "модель недоступна",
      saved: "Сохранено", deleted: "Удалено", confirm_del: "Удалить?",
      personas_desc: "личность = system prompt + белый список инструментов", personas_edit: "Правка личности",
      personas_pid: "id личности", personas_pname: "Имя", personas_system: "System prompt",
      personas_tools: "Белый список инструментов (через запятую, пусто = все, eco_* можно)",
      personas_builtin: "встроенная", personas_empty: "Своих личностей пока нет",
      bindings: "Привязки сессий", bind_btn: "Привязать", bind_hint: "chat_key (напр. onebot11:group:123)", bind_tiers_hint: "Уровни привязки (от частного к общему, срабатывает первый): сессия chat_key → группа (onebot11:group:123) → @аккаунт → платформа (onebot11:*) → глобальный по умолчанию", bind_key_col: "Привязано к", bind_none: "Нет привязок (сессии без привязки используют глобальный персонаж по умолчанию)", unbind: "Отвязать", bind_tier_session: "сессия", bind_tier_account: "аккаунт", bind_tier_platform: "платформа", bind_scope_chat: "Эта сессия", bind_scope_group: "Вся группа", bind_scope_account: "Этот аккаунт", bind_scope_platform: "Вся платформа", bind_scope_custom: "Вручную", bind_preview: "Будет использоваться «{persona}» для [{tier}] {key}", bind_preview_hint: "Выберите область или используйте кнопки выше; привязка действует на все сессии области без собственной привязки", bind_need_target: "Сначала выберите область привязки",
      tools_desc: "встроенные + службы экосистемы + MCP", tools_refresh: "Обновить эко-мост",
      tools_filter: "Фильтр…", tools_empty: "Нет подходящих инструментов",
      extensions_desc: "Инструменты и личности внешних модулей", ext_none: "Расширений нет: модуль с meta.services подключается сам", ext_personas_col: "Личности", ext_schemas_col: "Схемы",
      tasks_desc: "создаются агентом через create_scheduled_task", tasks_empty: "Задач нет",
      col_next: "След. запуск", col_target: "Цель", col_prompt: "Промпт", col_schedule: "Расписание",
      memory_desc: "области долговременной памяти", memory_pick: "кликните область для списка", memory_clear: "Очистить",
      memory_empty: "В этой области памяти нет",
      profile_card_title: "Профиль пользователя", profile_card_user: "Пользователь", profile_card_empty: "Профиль пуст",
      profile_card_clear: "Очистить профиль", profile_card_confirm: "Очистить профиль этого пользователя?", memory_importance: "Важность", health_reset: "Сброс", trash_page: "Корзина", trash_hint: "Удаления ожидают отмены; очищается автоматически", trash_expires: "Осталось", trash_days: "д", trash_restore: "Восстановить", trash_empty: "Корзина пуста", panel_title: "Быстрый переход", panel_ph: "Поиск сессий / страниц / настроек…", panel_none: "Нет совпадений", profile_sec_traits: "Черты", chat_pin_s: "Закреплено", profile_sec_preferences: "Предпочтения", profile_sec_facts: "Факты", profile_updated: "Обновлено",
      sessions_desc: "окна диалогов и привязки личностей", sessions_empty: "Сессий нет",
      col_turns: "Ходы", col_updated: "Обновлено", reset_btn: "Сброс", col_persona: "Личность",
      audit_desc: "операции на ПК и подтверждения", audit_empty: "Записей аудита нет",
      col_tool: "Инструмент", col_detail: "Детали",
      settings_desc: "конфигурация, применяется сразу", settings_saved: "Конфиг сохранен",
      group_model: "Модель", group_trigger: "Триггеры", group_security: "Безопасность", group_chat: "Чат", group_humanize: "Живость", group_memory: "Память",
      group_tools: "Инструменты", group_eco: "Эко", group_mcp: "MCP", group_task: "Задачи", group_access: "Доступ", group_usage: "Расход", group_plugin: "Плагины",
      usage_title: "Расход", usage_tokens: "токенов", usage_calls: "Вызовы", usage_total: "Всего за 14 дн.",
      usage_avg: "В среднем", usage_today: "Сегодня", usage_limit: "Дневной лимит", usage_empty: "Нет данных о расходе за 14 дней",
      hero_title: "Привет, я здесь", hero_no_limit: "Дневной лимит не задан",
      recent_sessions: "Последние сессии", upcoming_tasks: "Ближайшие задачи",
      login_hint: "Введите токен доступа", login_placeholder: "access token", login_btn: "Войти", login_failed: "Неверный токен",
      col_time: "Время", col_user: "Пользователь", col_origin: "Источник", col_chatkey: "Сессия", col_count: "Кол-во", col_id: "ID",
      ext_module: "Модуль", mcp_transport: "Транспорт",
      audit_total: "Записей", audit_tools_n: "Инструментов", audit_users_n: "Пользователей", audit_last24h: "За 24 часа",
      audit_copy: "Копировать JSON", audit_copied: "Скопировано",
      chat_attach: "Прикрепить файлы", chat_skills: "Навыки", chat_mcp: "Выбрать MCP-инструменты", chat_clear: "Очистить сессию",
      chat_clear_confirm: "Очистить контекст этой сессии?", chat_file_bad: "Не удалось прочитать файл:", chat_file_big: "Файл слишком большой:", chat_img_limit: "Максимум 3 изображения",
      chat_err: "Ошибка отправки", chat_follow: "Как в привязке сессии", chat_default_session: "Веб-чат",
      models_preset: "Провайдер", models_baseurl: "Base URL", models_apikey: "API Key",
      models_fetch: "Получить модели", models_fetching: "Получение…", models_fetch_fail: "Не удалось получить", models_remote_empty: "Модели не найдены",
      nav_skills: "Навыки", skills_desc: "Многоразовые шаблоны инструкций: выбираются в чате, подключаются при совпадении задачи",
      skills_add: "Новый навык", skills_edit: "Правка навыка", skills_name: "Имя", skills_description: "Описание", skills_body: "Содержимое",
      skills_export: "Экспорт", skills_import: "Импорт", skills_empty: "Навыков пока нет — создайте или положите .md в каталог навыков",
      skills_source: "Источник",
      personas_reset: "Сбросить к стандартной", personas_modified: "изменена", sessions_msgs: "Сообщения", yesterday: "Вчера", tomorrow: "Завтра", personas_new: "Новая личность", mcp_add: "Добавить сервер", cancel: "Отмена", mcp_command: "Команда", mcp_args: "Аргументы (по одному в строке)", mcp_headers: "Заголовки (JSON)", mcp_server: "Сервер",
      hero_dawn_1: "Доброе утро! С чего начнём?", hero_dawn_2: "Утро! Я уже тут", hero_dawn_3: "Рано встал — поболтаем?", hero_morning_1: "Привет! О чём подумаем?", hero_morning_2: "Я на связи, как всегда", hero_morning_3: "Какие планы? Расскажи", hero_noon_1: "Обедал? Не пропускай", hero_noon_2: "Отдохни, я присмотрю", hero_noon_3: "Пора на маленький перерыв", hero_afternoon_1: "Добрый день! Разговор лучше кофе", hero_afternoon_2: "Чаю? Ты заслужил", hero_afternoon_3: "Не перегибай — отдыхай, когда надо", hero_evening_1: "Добрый вечер! Как день прошёл?", hero_evening_2: "С возвращением, ты молодец", hero_evening_3: "Вечерний разговор — святое дело", hero_late_1: "Ещё не спишь?", hero_late_2: "Уже поздно — пойди отдохни", hero_late_3: "Не спится? Поболтаем",
      nav_group_run: "Выполнение", group_kb: "База знаний", group_skills: "Навыки", group_other: "Другое",
      settings_search_ph: "Поиск настроек…", settings_no_match: "Нет подходящих настроек", settings_invalid_value: "Недопустимое значение — исправьте", settings_json_bad: "Неверный JSON", settings_no_change: "Нет изменений для сохранения", settings_danger_confirm: "Вы меняете настройки безопасности. Продолжить?", settings_unsaved: "Есть несохранённые изменения настроек. Покинуть и отбросить их?", settings_save_partial: "Эти поля не прошли проверку и не сохранены", settings_dangerous: "опасно", settings_show: "Показать", settings_hide: "Скрыть", settings_list_add: "Добавить", plugin_settings_empty: "Пока нет плагинов с настройками: плагин со службой qvq_settings появится здесь",
      settings_sec_context: "Контекст и сжатие", settings_sec_forward: "Пересылка", settings_sec_reply: "Разделение ответов", settings_sec_flow: "Политика выполнения", settings_sec_misc: "Другое",
      backup_title: "Резервная копия", backup_desc: "Экспорт полной копии: провайдеры, личности, задачи, память, MCP, навыки и все настройки; импорт применяется после проверки каждой записи.", backup_export_data: "Экспортировать копию", backup_import_data: "Импортировать копию",
      orch_timeline_att: "Показаны только выполняющиеся / упавшие задачи и запуски",
      loading: "Загрузка…"
    }
  };

  var lang = (function () {
    try {
      var stored = localStorage.getItem("ep_lang");
      if (stored && I18N[stored]) return stored;
    } catch (e) {}
    if (window.lang && I18N[window.lang]) return window.lang;
    var nav = (navigator.language || "en").toLowerCase();
    if (nav.indexOf("zh") === 0) return (nav.indexOf("tw") >= 0 || nav.indexOf("hk") >= 0 || nav.indexOf("hant") >= 0) ? "zh-TW" : "zh-CN";
    if (nav.indexOf("ja") === 0) return "ja";
    if (nav.indexOf("ru") === 0) return "ru";
    return "en";
  })();

  function t(k) {
    return (I18N[lang] && I18N[lang][k]) || I18N.en[k] || k;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmtTime(ts) {
    if (!ts) return "-";
    var d = new Date(ts * 1000);
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  function fmtTimeFull(ts) {
    var d = new Date(ts * 1000);
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }

  // 今天只显示时间；昨天/明天显示「昨天 HH:MM」；更早/更晚显示日期
  function fmtSmart(ts) {
    if (!ts) return "-";
    var d = new Date(ts * 1000);
    var now = new Date();
    function p(n) { return (n < 10 ? "0" : "") + n; }
    var hm = p(d.getHours()) + ":" + p(d.getMinutes());
    var todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    var thatStart = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    var diffDays = Math.round((todayStart - thatStart) / 86400000);
    if (diffDays === 0) return hm;
    if (diffDays === 1) return t("yesterday") + " " + hm;
    if (diffDays === -1) return t("tomorrow") + " " + hm;
    return (d.getMonth() + 1) + "-" + p(d.getDate()) + " " + hm;
  }

  // hero 文案：按时间段随机
  function heroTitle() {
    var h = new Date().getHours();
    var bucket = h < 5 ? "late" : h < 9 ? "dawn" : h < 12 ? "morning" : h < 14 ? "noon" : h < 18 ? "afternoon" : h < 23 ? "evening" : "late";
    var pool = [];
    for (var i = 1; i <= 3; i++) {
      var key = "hero_" + bucket + "_" + i;
      var v = t(key);
      if (v !== key) pool.push(v);
    }
    if (!pool.length) pool.push(t("hero_title"));
    return pool[Math.floor(Math.random() * pool.length)];
  }

  // 撤销型提示：toast 附带 8 秒内可点的「撤销」按钮
  function toastUndo(msg, onUndo) {
    var box = document.createElement("div");
    box.className = "qvq-toast undo";
    box.setAttribute("role", "status");
    var span = document.createElement("span");
    span.textContent = msg;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "qvq-toast-undo-btn";
    btn.textContent = t("undo");
    box.appendChild(span);
    box.appendChild(btn);
    document.body.appendChild(box);
    var done = false;
    btn.onclick = function () {
      if (done) return;
      done = true;
      try { onUndo(); } catch (e) {}
      box.remove();
    };
    setTimeout(function () { box.remove(); }, 8000);
  }

  function toast(msg, isErr) {
    var box = document.createElement("div");
    box.className = "qvq-toast" + (isErr ? " err" : "");
    box.setAttribute("role", isErr ? "alert" : "status");
    box.setAttribute("aria-live", isErr ? "assertive" : "polite");
    box.textContent = msg;
    document.body.appendChild(box);
    setTimeout(function () { box.remove(); }, 2600);
  }

  var urlToken = (function () {
    try {
      return new URLSearchParams(window.location.search).get("token") || "";
    } catch (e) {
      return "";
    }
  })();

  function getToken() {
    if (activeToken) return activeToken;
    try {
      return localStorage.getItem("__ep_tk__") || urlToken || localStorage.getItem("qvq_token") || "";
    } catch (e) {
      return urlToken;
    }
  }

  (function syncTheme() {
    try {
      var parentDoc = window.parent && window.parent.document;
      if (!parentDoc || !parentDoc.documentElement) return;
      var attrs = ["data-theme", "data-oled"];
      var apply = function () {
        attrs.forEach(function (name) {
          var value = parentDoc.documentElement.getAttribute(name);
          if (value === null || value === "auto") {
            document.documentElement.removeAttribute(name);
          } else {
            document.documentElement.setAttribute(name, value);
          }
        });
      };
      apply();
      new MutationObserver(apply).observe(parentDoc.documentElement, {
        attributes: true,
        attributeFilter: attrs,
      });
    } catch (e) {}
  })();

  // 鉴权链在途标记：resolveToken 完成前的 api 调用先排队
  var bootWaiters = [];
  var bootSettled = false;

  function waitBoot() {
    if (bootSettled) return Promise.resolve();
    return new Promise(function (resolve) { bootWaiters.push(resolve); });
  }

  window.__qvqBootDone__ = function () {
    bootSettled = true;
    var waiters = bootWaiters;
    bootWaiters = [];
    waiters.forEach(function (fn) { fn(); });
  };

  // 请求超时上限
  
  var API_TIMEOUT_MS = 25000;

  function api(path, method, body) {
    return waitBoot().then(function () {
      var headers = { "Content-Type": "application/json" };
      var token = getToken();
      if (token) headers["Authorization"] = "Bearer " + token;
      var ctrl = (typeof AbortController !== "undefined") ? new AbortController() : null;
      var timer = ctrl ? setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, API_TIMEOUT_MS) : null;
      var opts = {
        method: method || "GET",
        headers: headers,
        body: body ? JSON.stringify(body) : undefined
      };
      if (ctrl) opts.signal = ctrl.signal;
      return fetch("/QvQChat" + path, opts).then(function (resp) {
        if (timer) clearTimeout(timer);
        return resp.json().catch(function () { return {}; }).then(function (data) {
          data = data && typeof data === "object" ? data : {};
          // 显式携带 HTTP 状态
          data.__http = resp.status;
          if (resp.status === 401) {
            activeToken = "";
            try { localStorage.removeItem("qvq_token"); } catch (e) {}
            if (typeof showLogin === "function") showLogin();
          }
          return data;
        });
      }, function (err) {
        if (timer) clearTimeout(timer);
        throw err;
      });
    });
  }

  var activeToken = "";

  function authWith(token) {
    var headers = {};
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch("/QvQChat/api/qvq/auth", { headers: headers }).then(function (r) {
      return r.status === 200;
    }).catch(function () { return false; });
  }

  // 鉴权成功后把 ?token= 从地址栏剥掉
  function stripUrlToken() {
    if (!window.history || !window.history.replaceState) return;
    try {
      var clean = window.location.search.replace(/([?&])token=[^&]*&?/i, "$1").replace(/[?&]$/, "");
      window.history.replaceState(null, "", window.location.pathname + clean + window.location.hash);
    } catch (e) {}
  }

  // 依次尝试 __ep_tk__ → url ?token= → qvq_token，取第一个能通过鉴权的
  function resolveToken() {
    var candidates = [];
    try {
      var ep = localStorage.getItem("__ep_tk__");
      if (ep) candidates.push(ep);
    } catch (e) {}
    if (urlToken) candidates.push(urlToken);
    try {
      var qt = localStorage.getItem("qvq_token");
      if (qt) candidates.push(qt);
    } catch (e) {}
    var chain = Promise.resolve(false);
    var chosen = "";
    candidates.forEach(function (tk) {
      chain = chain.then(function (ok) {
        if (ok) return true;
        chosen = tk;
        return authWith(tk);
      });
    });
    return chain.then(function (ok) {
      if (ok && chosen) {
        // 回写命中的令牌
        try { localStorage.setItem("qvq_token", chosen); } catch (e) {}
        stripUrlToken();
      }
      return ok ? chosen : "";
    });
  }

  // 导航点击委托
  (function bindNavEarly() {
    var nav = document.getElementById("qvq-nav");
    if (!nav) return;
    nav.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".qvq-nav-btn") : null;
      if (btn) switchTab(btn.getAttribute("data-tab"));
    });
  })();

