/* 核心：主题、鉴权令牌链与全局引导 */
(function () {
  var I18N = {
    "zh-CN": {
      load_older: "加载更早消息", load_more: "加载更多",
      nav_group_core: "核心", nav_group_config: "能力", nav_group_data: "数据", nav_mcp: "MCP", mcp_desc: "MCP 服务器与工具接入", mcp_servers: "服务器", mcp_tools: "MCP 工具", mcp_connect_all: "连接全部", mcp_connect: "连接", mcp_disconnect: "断开", mcp_status_on: "已连接", mcp_status_off: "未连接", mcp_none: "尚未配置 MCP 服务器，点击此处添加", queue_send_now: "立即发送", queue_added: "已暂存，当前回复完成后自动发送", queue_edit: "编辑回输入框", queue_badge: "待发", chat_delete: "删除", session_delete_confirm: "删除该会话？删除后不可恢复", session_deleted: "已删除", chat_purge_archived: "清空已归档", chat_stop: "停止生成", chat_cancelled: "（已停止生成）", chat_settings: "会话设置", settings_save_session: "保存到本会话", settings_apply_all: "应用到全局", share_export: "导出 Markdown", chat_persona_binding: "人格绑定", chat_export: "导出会话", chat_share: "分享会话", share_expires: "链接有效期", share_max_tokens: "最大允许 token（约可见的上下文预算）", share_create: "生成分享链接", share_url: "分享链接", share_hint: "任何人通过此链接可只读查看该会话（受 token 预算与有效期限制），可随时撤销。", role_user: "用户", model_s_auto: "自动", effort_s_auto: "默认", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "提名工具/技能（AI 优先使用）", chat_model: "切换模型", chat_effort: "思考强度", model_auto: "自动选择模型", effort_auto: "强度默认", effort_low: "强度低", effort_mid: "强度中", effort_high: "强度高", mention_ok: "完成", mention_none: "暂无可提名的技能或 MCP 工具", confirm_title: "确认操作", confirm_yes: "确定", chat_pasted: "已粘贴附件", chat_pin: "置顶", chat_unpin: "取消置顶", chat_archive: "归档", chat_unarchive: "取消归档", chat_archived: "已归档", chat_hero_sub: "有什么想聊的？或者从下面挑一个开始", chat_chip_1: "帮我写个 Python 小脚本", chat_chip_2: "把今天的聊天总结成周报", chat_chip_3: "解释一段报错信息", chat_chip_4: "每天晚上九点提醒我写日记", chat_new: "新对话", chat_new_name: "网页对话 {n}", chat_busy: "当前会话正在回复中", chat_density: "信息密度", density_brief: "简洁", density_detail: "详细", steps_count: "{n} 步工具调用", steps_running: "运行中…", copy: "复制", copied: "已复制", msgs_count: "{n} 条消息", session_summary: "上下文摘要",
      stat_usage: "今日用量", backup_export: "导出配置", backup_import: "导入配置", audit_filter: "过滤工具/用户…", col_preview: "最近消息",
      subtitle: "通用智能体",
      nav_overview: "概览", nav_chat: "对话", nav_models: "模型池", nav_personas: "人格",
      nav_tools: "工具", nav_extensions: "扩展", nav_tasks: "定时任务", nav_memory: "记忆", nav_sessions: "会话",
      nav_knowledge: "知识库", knowledge_desc: "共享资料库：相关片段会自动注入对话，也可用 knowledge_search 检索", kb_add: "添加条目", kb_search_ph: "检索…", kb_stats_line: "条目 {e} · 分块 {c}", kb_list_empty: "还没有条目，点上方按钮添加", kb_title_label: "标题", kb_source_label: "来源（可选）", kb_content_label: "内容", kb_need_title_content: "需要标题与内容", kb_triggers_label: "触发关键词（可选，世界书）", kb_triggers_ph: "如：魔王, 北塔（逗号分隔，命中即注入）", kb_priority_label: "触发优先级（大优先）", kb_cooldown_label: "触发冷却分钟（留空用默认，0 不冷却）",
      nav_audit: "审计", nav_settings: "设置",
      sess_members: "成员", sess_members_hint: "成员白名单（每行一个用户 ID，* 表示全员；留空恢复全员）", sess_sources_hint: "接受其它会话的输入（每行一个 chat_key，如 onebot11:group:123；这些会话的消息会路由到本会话）", kb_export: "导出", kb_import: "导入",
      nav_orchestrate: "编排", orchestrate_desc: "智能体总览：模型链 · 健康 · 运行状态 · 任务时间线", orch_model_chain: "模型链（故障转移顺序）", orch_chain_hint: "拖拽调整故障转移顺序，松手自动保存", orch_chain_saved: "链序已保存", orch_health: "模型健康", health_ok: "全部模型正常", health_cooldown: "冷却中", health_fails: "连续失败 {n} 次", health_left: "剩余 {s}s", orch_running: "运行状态", running_none: "暂无运行中的任务", orch_timeline: "任务时间线", timeline_empty: "暂无任务与执行记录", orch_capabilities: "能力开关", caps_tools: "工具", caps_skills: "技能", task_next: "下次", task_last: "最近", task_status_error: "上次失败", cost_title: "成本估算", cost_total: "14 天合计", cost_daily: "每日成本（柱）与累计（线）", cost_by_model: "按模型分布", cost_empty: "暂无带单价的用量数据（模型价格来自 models.dev 目录）",
      overview_desc: "智能体运行一览", overview_detail: "运行详情",
      stat_models: "模型", stat_tools: "工具", stat_eco: "生态工具", stat_sessions: "会话",
      stat_tasks: "任务", stat_mcp: "MCP", stat_extensions: "扩展", stat_security: "安全",
      on: "开", off: "关", takeovers: "接管中会话", trust_on: "完全信任",
      chat_desc: "直接测试智能体", chat_placeholder: "说点什么…", chat_send: "发送",
      chat_thinking: "思考中…", chat_empty: "还没有对话",
      models_desc: "任意 OpenAI 兼容服务商，按顺序故障转移", models_add: "添加 / 更新模型",
      models_name: "名称", models_id: "模型名", models_temp: "温度", models_maxtok: "最大 token", model_smart: "智能配置", model_smart_hint: "开启后从 models.dev 自动补全上下文、能力和价格", model_context: "上下文窗口", model_max_output: "最大输出 Token", model_detect: "从 models.dev 检测", model_detected: "已从 models.dev 补全元数据", model_detect_empty: "models.dev 未收录该模型，请手动填写", model_advanced: "高级配置", model_input_types: "输入类型", model_input_text: "文本", model_input_image: "图片", model_input_video: "视频", model_input_pdf: "PDF", model_caps: "模型能力", model_tool_call: "工具调用", model_reasoning: "推理", model_price: "单价（每百万 token）", model_price_in: "输入", model_price_out: "输出", model_enabled: "启用该模型", model_manage: "模型配置", model_refresh: "刷新能力与价格", model_refresh_done: "已更新 {n} 项", model_delete_confirm: "删除该模型？", model_cap_tools: "工具", model_cap_no_tools: "无工具", model_cap_vision: "视觉", model_cap_reason: "推理", model_unknown: "能力未知", orch_chain_top_no_tools: "链首模型未标记「工具调用」，启用工具的对话会跳过它；请到模型池补全能力或手动开启。", model_none: "还没有模型", model_add_title: "添加模型", model_edit_title: "编辑模型配置",
      save: "保存", actions: "操作", test: "测试", edit: "编辑", del: "删除",
      models_empty: "模型池为空，先添加一个吧", model_test_ok: "模型可用", model_test_fail: "模型不可用",
      saved: "已保存", deleted: "已删除", confirm_del: "确认删除？",
      personas_desc: "系统提示词 + 工具白名单", personas_edit: "编辑人格",
      personas_pid: "人格 id", personas_pname: "名称", personas_system: "系统提示词",
      personas_tools: "工具白名单（逗号分隔，留空全部可用，支持 eco_* 通配）",
      personas_builtin: "内置", personas_empty: "还没有自定义人格",
      bindings: "会话绑定", bind_btn: "绑定", bind_hint: "chat_key（如 onebot11:group:123）",
      tools_desc: "内置 + 生态桥 + MCP 工具", tools_refresh: "刷新生态桥",
      tools_filter: "过滤…", tools_empty: "没有匹配的工具",
      extensions_desc: "外部模块提供的工具与人格", ext_none: "暂无扩展模块：模块声明 meta.services 即自动接入", ext_personas_col: "人格", ext_schemas_col: "Schema",
      tasks_desc: "智能体创建的定时任务", tasks_empty: "当前没有定时任务",
      col_next: "下次触发", col_target: "目标", col_prompt: "内容", col_schedule: "计划",
      memory_desc: "长期记忆作用域", memory_pick: "点击作用域查看条目", memory_clear: "清空",
      memory_empty: "该作用域暂无记忆",
      profile_card_title: "用户画像", profile_card_user: "用户", profile_card_empty: "暂无画像",
      profile_card_clear: "清空画像", profile_card_confirm: "清空该用户的画像？",
      sessions_desc: "会话与人格绑定", sessions_empty: "暂无会话",
      col_turns: "轮数", col_updated: "更新时间", reset_btn: "重置", col_persona: "人格",
      audit_desc: "操作与确认记录", audit_empty: "暂无审计记录",
      col_tool: "工具", col_detail: "详情",
      settings_desc: "运行时配置，保存即生效", settings_saved: "配置已保存",
      group_model: "模型", group_trigger: "触发", group_security: "安全", group_chat: "对话", group_memory: "记忆",
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
      settings_search_ph: "搜索设置项…", settings_no_match: "没有匹配的设置项", settings_invalid_value: "值无效，请修正", settings_json_bad: "JSON 格式错误", settings_no_change: "没有修改，无需保存", settings_danger_confirm: "即将修改安全相关设置，确认继续？", settings_unsaved: "有未保存的设置修改，离开将丢失。确认离开？", settings_save_partial: "部分字段未通过校验，未保存", settings_dangerous: "高危", settings_show: "显示", settings_hide: "隐藏", settings_list_add: "添加一项", plugin_settings_empty: "暂无可配置的插件：插件提供 qvq_settings 服务后自动出现在这里",
      settings_sec_context: "上下文与压缩", settings_sec_forward: "合并转发", settings_sec_reply: "分段回复", settings_sec_flow: "运行策略", settings_sec_misc: "其它",
      backup_title: "数据备份", backup_desc: "导出包含模型池、人格、任务、记忆、MCP、技能与全部设置的完整备份；导入时逐项校验后应用。", backup_export_data: "导出数据备份", backup_import_data: "导入数据备份",
      orch_timeline_att: "仅显示运行中 / 异常的任务与执行记录",
      loading: "加载中…"
    },
    "zh-TW": {
      load_older: "載入更早訊息", load_more: "載入更多",
      nav_group_core: "核心", nav_group_config: "能力", nav_group_data: "資料", nav_mcp: "MCP", mcp_desc: "MCP 伺服器與工具接入", mcp_servers: "伺服器", mcp_tools: "MCP 工具", mcp_connect_all: "連接全部", mcp_connect: "連接", mcp_disconnect: "斷開", mcp_status_on: "已連接", mcp_status_off: "未連接", mcp_none: "尚未配置 MCP 伺服器，點擊此處新增", queue_send_now: "立即傳送", queue_added: "已暫存，目前回覆完成後自動傳送", queue_edit: "編輯回輸入框", queue_badge: "待發", chat_delete: "刪除", session_delete_confirm: "刪除該會話？刪除後無法復原", session_deleted: "已刪除", chat_purge_archived: "清空已歸檔", chat_stop: "停止產生", chat_cancelled: "（已停止產生）", chat_settings: "會話設置", settings_save_session: "儲存到此會話", settings_apply_all: "套用到全域", share_export: "匯出 Markdown", chat_persona_binding: "人格綁定", chat_export: "匯出會話", chat_share: "分享會話", share_expires: "連結有效期", share_max_tokens: "最大允許 token（約可見的上下文預算）", share_create: "產生分享連結", share_url: "分享連結", share_hint: "任何人透過此連結可唯讀檢視該會話（受 token 預算與有效期限制），可隨時撤銷。", role_user: "使用者", model_s_auto: "自動", effort_s_auto: "預設", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "提名工具/技能（AI 優先使用）", chat_model: "切換模型", chat_effort: "思考強度", model_auto: "自動選擇模型", effort_auto: "強度預設", effort_low: "強度低", effort_mid: "強度中", effort_high: "強度高", mention_ok: "完成", mention_none: "暫無可提名的技能或 MCP 工具", confirm_title: "確認操作", confirm_yes: "確定", chat_pasted: "已貼上附件", chat_pin: "置頂", chat_unpin: "取消置頂", chat_archive: "歸檔", chat_unarchive: "取消歸檔", chat_archived: "已歸檔", chat_hero_sub: "有什麼想聊的？或從下面挑一個開始", chat_chip_1: "幫我寫個 Python 小腳本", chat_chip_2: "把今天的聊天整理成週報", chat_chip_3: "解釋一段錯誤訊息", chat_chip_4: "每天晚上九點提醒我寫日記", chat_new: "新對話", chat_new_name: "網頁對話 {n}", chat_busy: "目前會話正在回覆中", chat_density: "資訊密度", density_brief: "簡潔", density_detail: "詳細", steps_count: "{n} 次工具呼叫", steps_running: "執行中…", copy: "複製", copied: "已複製", msgs_count: "{n} 條訊息", session_summary: "上下文摘要",
      stat_usage: "今日用量", backup_export: "匯出配置", backup_import: "匯入配置", audit_filter: "過濾工具/使用者…", col_preview: "最近訊息",
      subtitle: "通用智慧代理",
      nav_overview: "概覽", nav_chat: "對話", nav_models: "模型池", nav_personas: "人格",
      nav_tools: "工具", nav_extensions: "擴展", nav_tasks: "定時任務", nav_memory: "記憶", nav_sessions: "會話",
      nav_knowledge: "知識庫", knowledge_desc: "共享資料庫：相關片段會自動注入對話，也可用 knowledge_search 檢索", kb_add: "新增條目", kb_search_ph: "檢索…", kb_stats_line: "條目 {e} · 分塊 {c}", kb_list_empty: "還沒有條目，點上方按鈕新增", kb_title_label: "標題", kb_source_label: "來源（可選）", kb_content_label: "內容", kb_need_title_content: "需要標題與內容", kb_triggers_label: "觸發關鍵詞（可選，世界書）", kb_triggers_ph: "如：魔王, 北塔（逗號分隔，命中即注入）", kb_priority_label: "觸發優先級（大優先）", kb_cooldown_label: "觸發冷卻分鐘（留空用預設，0 不冷卻）",
      nav_audit: "審計", nav_settings: "設定",
      sess_members: "成員", sess_members_hint: "成員白名單（每行一個使用者 ID，* 表示全員；留空恢復全員）", sess_sources_hint: "接受其它會話的輸入（每行一個 chat_key，如 onebot11:group:123；這些會話的訊息會路由到本會話）", kb_export: "匯出", kb_import: "匯入",
      nav_orchestrate: "編排", orchestrate_desc: "智能體總覽：模型鏈 · 健康 · 執行狀態 · 任務時間線", orch_model_chain: "模型鏈（故障轉移順序）", orch_chain_hint: "拖曳調整故障轉移順序，鬆手自動儲存", orch_chain_saved: "鏈序已儲存", orch_health: "模型健康", health_ok: "全部模型正常", health_cooldown: "冷卻中", health_fails: "連續失敗 {n} 次", health_left: "剩餘 {s}s", orch_running: "執行狀態", running_none: "暫無執行中的任務", orch_timeline: "任務時間線", timeline_empty: "暫無任務與執行記錄", orch_capabilities: "能力開關", caps_tools: "工具", caps_skills: "技能", task_next: "下次", task_last: "最近", task_status_error: "上次失敗", cost_title: "成本估算", cost_total: "14 天合計", cost_daily: "每日成本（柱）與累計（線）", cost_by_model: "按模型分佈", cost_empty: "暫無帶單價的用量資料（模型價格來自 models.dev 目錄）",
      overview_desc: "智慧代理運行一覽", overview_detail: "運行詳情",
      stat_models: "模型", stat_tools: "工具", stat_eco: "生態工具", stat_sessions: "會話",
      stat_tasks: "任務", stat_mcp: "MCP", stat_extensions: "擴展", stat_security: "安全",
      on: "開", off: "關", takeovers: "接管中會話", trust_on: "完全信任",
      chat_desc: "直接測試智慧代理", chat_placeholder: "說點什麼…", chat_send: "傳送",
      chat_thinking: "思考中…", chat_empty: "還沒有對話",
      models_desc: "任意 OpenAI 相容服務商，依順序故障轉移", models_add: "新增 / 更新模型",
      models_name: "名稱", models_id: "模型名", models_temp: "溫度", models_maxtok: "最大 token", model_smart: "智慧設定", model_smart_hint: "開啟後從 models.dev 自動補全上下文、能力和價格", model_context: "上下文視窗", model_max_output: "最大輸出 Token", model_detect: "從 models.dev 偵測", model_detected: "已從 models.dev 補全中繼資料", model_detect_empty: "models.dev 未收錄該模型，請手動填寫", model_advanced: "進階設定", model_input_types: "輸入類型", model_input_text: "文字", model_input_image: "圖片", model_input_video: "影片", model_input_pdf: "PDF", model_caps: "模型能力", model_tool_call: "工具呼叫", model_reasoning: "推理", model_price: "單價（每百萬 token）", model_price_in: "輸入", model_price_out: "輸出", model_enabled: "啟用該模型", model_manage: "模型設定", model_refresh: "重新整理能力與價格", model_refresh_done: "已更新 {n} 項", model_delete_confirm: "刪除該模型？", model_cap_tools: "工具", model_cap_no_tools: "無工具", model_cap_vision: "視覺", model_cap_reason: "推理", model_unknown: "能力未知", orch_chain_top_no_tools: "鏈首模型未標記「工具呼叫」，啟用工具的對話會跳過它；請到模型池補全能力或手動開啟。", model_none: "還沒有模型", model_add_title: "新增模型", model_edit_title: "編輯模型設定",
      save: "儲存", actions: "操作", test: "測試", edit: "編輯", del: "刪除",
      models_empty: "模型池為空，先新增一個吧", model_test_ok: "模型可用", model_test_fail: "模型不可用",
      saved: "已儲存", deleted: "已刪除", confirm_del: "確認刪除？",
      personas_desc: "系統提示詞 + 工具白名單", personas_edit: "編輯人格",
      personas_pid: "人格 id", personas_pname: "名稱", personas_system: "系統提示詞",
      personas_tools: "工具白名單（逗號分隔，留空全部，支援 eco_* 萬用）",
      personas_builtin: "內建", personas_empty: "還沒有自訂人格",
      bindings: "會話綁定", bind_btn: "綁定", bind_hint: "chat_key（如 onebot11:group:123）",
      tools_desc: "內建 + 生態橋 + MCP 工具", tools_refresh: "重新整理生態橋",
      tools_filter: "過濾…", tools_empty: "沒有符合的工具",
      extensions_desc: "外部模組的工具與人格", ext_none: "暫無擴展模組：模組宣告 meta.services 即自動接入", ext_personas_col: "人格", ext_schemas_col: "Schema",
      tasks_desc: "智慧代理建立的定時任務", tasks_empty: "目前沒有定時任務",
      col_next: "下次觸發", col_target: "目標", col_prompt: "內容", col_schedule: "計畫",
      memory_desc: "長期記憶作用域", memory_pick: "點擊作用域查看條目", memory_clear: "清空",
      memory_empty: "該作用域暫無記憶",
      profile_card_title: "使用者畫像", profile_card_user: "使用者", profile_card_empty: "暫無畫像",
      profile_card_clear: "清空畫像", profile_card_confirm: "清空該使用者的畫像？",
      sessions_desc: "會話與人格綁定", sessions_empty: "暫無會話",
      col_turns: "輪數", col_updated: "更新時間", reset_btn: "重置", col_persona: "人格",
      audit_desc: "操作與確認記錄", audit_empty: "暫無審計記錄",
      col_tool: "工具", col_detail: "詳情",
      settings_desc: "運行時配置，儲存即生效", settings_saved: "配置已儲存",
      group_model: "模型", group_trigger: "觸發", group_security: "安全", group_chat: "對話", group_memory: "記憶",
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
      settings_search_ph: "搜尋設定項…", settings_no_match: "沒有符合的設定項", settings_invalid_value: "值無效，請修正", settings_json_bad: "JSON 格式錯誤", settings_no_change: "沒有修改，無需儲存", settings_danger_confirm: "即將修改安全相關設定，確認繼續？", settings_unsaved: "有未儲存的設定修改，離開將遺失。確認離開？", settings_save_partial: "部分欄位未通過校驗，未儲存", settings_dangerous: "高危", settings_show: "顯示", settings_hide: "隱藏", settings_list_add: "新增一項", plugin_settings_empty: "暫無可設定的外掛：外掛提供 qvq_settings 服務後自動出現在這裡",
      settings_sec_context: "上下文與壓縮", settings_sec_forward: "合併轉發", settings_sec_reply: "分段回覆", settings_sec_flow: "運行策略", settings_sec_misc: "其它",
      backup_title: "資料備份", backup_desc: "匯出包含模型池、人格、任務、記憶、MCP、技能與全部設定的完整備份；匯入時逐項校驗後套用。", backup_export_data: "匯出資料備份", backup_import_data: "匯入資料備份",
      orch_timeline_att: "僅顯示執行中 / 異常的任務與執行記錄",
      loading: "載入中…"
    },
    "en": {
      load_older: "Load earlier messages", load_more: "Load more",
      nav_group_core: "Core", nav_group_config: "Capabilities", nav_group_data: "Data", nav_mcp: "MCP", mcp_desc: "Model Context Protocol servers and tool access", mcp_servers: "Servers", mcp_tools: "MCP tools", mcp_connect_all: "Connect all", mcp_connect: "Connect", mcp_disconnect: "Disconnect", mcp_status_on: "connected", mcp_status_off: "disconnected", mcp_none: "No MCP servers yet — click here to add one", queue_send_now: "Send now", queue_added: "Queued — will send after the current reply", queue_edit: "Edit back to input", queue_badge: "Queued", chat_delete: "Delete", session_delete_confirm: "Delete this session? This cannot be undone", session_deleted: "Deleted", chat_purge_archived: "Purge archived", chat_stop: "Stop generating", chat_cancelled: "(generation stopped)", chat_settings: "Session settings", settings_save_session: "Save to this session", settings_apply_all: "Apply to all sessions", share_export: "Export Markdown", chat_persona_binding: "Persona binding", chat_export: "Export session", chat_share: "Share session", share_expires: "Link expires in", share_max_tokens: "Max tokens allowed (visible context budget)", share_create: "Create share link", share_url: "Share link", share_hint: "Anyone with this link can view the session read-only, limited by the token budget and expiry. Revoke anytime.", role_user: "User", model_s_auto: "auto", effort_s_auto: "Auto", effort_s_low: "Low", effort_s_mid: "Mid", effort_s_high: "High", chat_mention: "Mention tools/skills (AI prioritizes them)", chat_model: "Switch model", chat_effort: "Effort level", model_auto: "Auto model", effort_auto: "Effort auto", effort_low: "Effort low", effort_mid: "Effort mid", effort_high: "Effort high", mention_ok: "Done", mention_none: "No skills or MCP tools to mention yet", confirm_title: "Confirm", confirm_yes: "OK", chat_pasted: "Attachment pasted", chat_pin: "Pin", chat_unpin: "Unpin", chat_archive: "Archive", chat_unarchive: "Unarchive", chat_archived: "Archived", chat_hero_sub: "What shall we talk about? Or pick a starter below", chat_chip_1: "Write me a small Python script", chat_chip_2: "Summarize today's chat into a report", chat_chip_3: "Explain this error message", chat_chip_4: "Remind me to journal at 9pm daily", chat_new: "New chat", chat_new_name: "Web chat {n}", chat_busy: "This session is still replying", chat_density: "Detail level", density_brief: "Brief", density_detail: "Detailed", steps_count: "{n} tool calls", steps_running: "running…", copy: "Copy", copied: "Copied", msgs_count: "{n} messages", session_summary: "Context summary",
      stat_usage: "Today usage", backup_export: "Export config", backup_import: "Import config", audit_filter: "Filter tool/user…", col_preview: "Last message",
      subtitle: "universal agent",
      nav_overview: "Overview", nav_chat: "Chat", nav_models: "Models", nav_personas: "Personas",
      nav_tools: "Tools", nav_extensions: "Extensions", nav_tasks: "Tasks", nav_memory: "Memory", nav_sessions: "Sessions",
      nav_knowledge: "Knowledge", knowledge_desc: "Shared library: relevant passages are auto-injected into chats and searchable via knowledge_search", kb_add: "Add entry", kb_search_ph: "Search…", kb_stats_line: "{e} entries · {c} chunks", kb_list_empty: "No entries yet — use the button above to add one", kb_title_label: "Title", kb_source_label: "Source (optional)", kb_content_label: "Content", kb_need_title_content: "Title and content are required", kb_triggers_label: "Trigger keywords (optional, lorebook)", kb_triggers_ph: "e.g. demon king, north tower (comma separated)", kb_priority_label: "Trigger priority (higher first)", kb_cooldown_label: "Trigger cooldown minutes (blank = default, 0 = none)",
      nav_audit: "Audit", nav_settings: "Settings",
      sess_members: "Members", sess_members_hint: "Member allowlist (one user ID per line, * = everyone; empty resets to everyone)", sess_sources_hint: "Accept input from other chats (one chat_key per line, e.g. onebot11:group:123; their messages route into this chat)", kb_export: "Export", kb_import: "Import",
      nav_orchestrate: "Orchestration", orchestrate_desc: "Agent at a glance: model chain · health · runs · task timeline", orch_model_chain: "Model chain (failover order)", orch_chain_hint: "Drag to reorder the failover chain; saves automatically on drop", orch_chain_saved: "Chain order saved", orch_health: "Model health", health_ok: "All models healthy", health_cooldown: "Cooling down", health_fails: "{n} consecutive failures", health_left: "{s}s left", orch_running: "Running", running_none: "No running tasks", orch_timeline: "Task timeline", timeline_empty: "No tasks or runs yet", orch_capabilities: "Capability switches", caps_tools: "Tools", caps_skills: "Skills", task_next: "Next", task_last: "Last", task_status_error: "Last run failed", cost_title: "Cost estimate", cost_total: "14-day total", cost_daily: "Daily cost (bars) and cumulative (line)", cost_by_model: "By model", cost_empty: "No priced usage yet (model prices come from the models.dev catalog)",
      overview_desc: "agent runtime at a glance", overview_detail: "Details",
      stat_models: "Models", stat_tools: "Tools", stat_eco: "Eco tools", stat_sessions: "Sessions",
      stat_tasks: "Tasks", stat_mcp: "MCP", stat_extensions: "Extensions", stat_security: "Security",
      on: "on", off: "off", takeovers: "Takeovers", trust_on: "Full trust",
      chat_desc: "test the agent directly", chat_placeholder: "Say something…", chat_send: "Send",
      chat_thinking: "thinking…", chat_empty: "No conversation yet",
      models_desc: "Any OpenAI-compatible provider, with failover", models_add: "Add / update model",
      models_name: "Name", models_id: "Model", models_temp: "Temperature", models_maxtok: "Max tokens", model_smart: "Auto config", model_smart_hint: "Fill context, capabilities and pricing from models.dev", model_context: "Context window", model_max_output: "Max output tokens", model_detect: "Detect from models.dev", model_detected: "Metadata filled from models.dev", model_detect_empty: "Not found on models.dev; fill manually", model_advanced: "Advanced", model_input_types: "Input types", model_input_text: "Text", model_input_image: "Image", model_input_video: "Video", model_input_pdf: "PDF", model_caps: "Capabilities", model_tool_call: "Tool calling", model_reasoning: "Reasoning", model_price: "Price (per 1M tokens)", model_price_in: "Input", model_price_out: "Output", model_enabled: "Enable this model", model_manage: "Models", model_refresh: "Refresh capabilities & prices", model_refresh_done: "Updated {n} fields", model_delete_confirm: "Delete this model?", model_cap_tools: "tools", model_cap_no_tools: "no tools", model_cap_vision: "vision", model_cap_reason: "reasoning", model_unknown: "unknown", orch_chain_top_no_tools: "The first model is not marked for tool calling; tool-enabled chats will skip it. Fill its capabilities in Model Pool or enable it manually.", model_none: "No models yet", model_add_title: "Add model", model_edit_title: "Edit model config",
      save: "Save", actions: "Actions", test: "Test", edit: "Edit", del: "Delete",
      models_empty: "Model pool is empty, add one", model_test_ok: "model works", model_test_fail: "model failed",
      saved: "Saved", deleted: "Deleted", confirm_del: "Delete this?",
      personas_desc: "System prompt + tool whitelist", personas_edit: "Edit persona",
      personas_pid: "Persona id", personas_pname: "Name", personas_system: "System prompt",
      personas_tools: "Tool whitelist (comma separated, empty = all, eco_* allowed)",
      personas_builtin: "builtin", personas_empty: "No custom personas yet",
      bindings: "Session bindings", bind_btn: "Bind", bind_hint: "chat_key (e.g. onebot11:group:123)",
      tools_desc: "Built-in, eco bridge and MCP tools", tools_refresh: "Refresh eco bridge",
      tools_filter: "Filter…", tools_empty: "No matching tools",
      extensions_desc: "Tools and personas from external modules", ext_none: "No extensions yet: a module declaring meta.services is wired in automatically", ext_personas_col: "Personas", ext_schemas_col: "Schemas",
      tasks_desc: "Tasks created by the agent", tasks_empty: "No scheduled tasks",
      col_next: "Next run", col_target: "Target", col_prompt: "Prompt", col_schedule: "Schedule",
      memory_desc: "long-term memory scopes", memory_pick: "click a scope to list entries", memory_clear: "Clear",
      memory_empty: "No memories in this scope",
      profile_card_title: "User Profile", profile_card_user: "User", profile_card_empty: "No profile yet",
      profile_card_clear: "Clear Profile", profile_card_confirm: "Clear this user's profile?",
      sessions_desc: "Sessions and persona bindings", sessions_empty: "No sessions",
      col_turns: "Turns", col_updated: "Updated", reset_btn: "Reset", col_persona: "Persona",
      audit_desc: "Operation and confirmation log", audit_empty: "No audit records",
      col_tool: "Tool", col_detail: "Detail",
      settings_desc: "runtime configuration, applied on save", settings_saved: "Config saved",
      group_model: "Model", group_trigger: "Trigger", group_security: "Security", group_chat: "Chat", group_memory: "Memory",
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
      settings_search_ph: "Search settings…", settings_no_match: "No matching settings", settings_invalid_value: "Invalid value — please fix", settings_json_bad: "Invalid JSON", settings_no_change: "No changes to save", settings_danger_confirm: "You are about to change security-related settings. Continue?", settings_unsaved: "There are unsaved setting changes. Leave and discard them?", settings_save_partial: "Some fields failed validation and were not saved", settings_dangerous: "danger", settings_show: "Show", settings_hide: "Hide", settings_list_add: "Add item", plugin_settings_empty: "No plugins with settings yet: a plugin exposing the qvq_settings service appears here",
      settings_sec_context: "Context & compaction", settings_sec_forward: "Merged forward", settings_sec_reply: "Split replies", settings_sec_flow: "Runtime policy", settings_sec_misc: "Other",
      backup_title: "Data backup", backup_desc: "Export a full backup with providers, personas, tasks, memory, MCP, skills and all settings; imports are validated per item before applying.", backup_export_data: "Export data backup", backup_import_data: "Import data backup",
      orch_timeline_att: "Only running / failed tasks and runs are shown",
      loading: "Loading…"
    },
    "ja": {
      load_older: "以前のメッセージを読み込む", load_more: "さらに読み込む",
      nav_group_core: "コア", nav_group_config: "機能", nav_group_data: "データ", nav_mcp: "MCP", mcp_desc: "Model Context Protocol サーバーとツール接続", mcp_servers: "サーバー", mcp_tools: "MCP ツール", mcp_connect_all: "全て接続", mcp_connect: "接続", mcp_disconnect: "切断", mcp_status_on: "接続済", mcp_status_off: "未接続", mcp_none: "MCP サーバー未登録 — ここをクリックして追加", queue_send_now: "今すぐ送信", queue_added: "一時保存しました。現在の返信後に自動送信します", queue_edit: "入力欄に戻して編集", queue_badge: "待ち", chat_delete: "削除", session_delete_confirm: "このセッションを削除しますか？元に戻せません", session_deleted: "削除しました", chat_purge_archived: "アーカイブ済みを一括削除", chat_stop: "生成を停止", chat_cancelled: "（生成を停止しました）", chat_settings: "セッション設定", settings_save_session: "このセッションに保存", settings_apply_all: "全セッションに適用", share_export: "Markdown をエクスポート", chat_persona_binding: "ペルソナ固定", chat_export: "セッションをエクスポート", chat_share: "セッションを共有", share_expires: "リンク有効期限", share_max_tokens: "最大トークン（見える文脈の予算）", share_create: "共有リンクを作成", share_url: "共有リンク", share_hint: "このリンクを知る人は誰でもセッションを読み取り専用で閲覧できます（トークン予算と有効期限で制限）。いつでも取り消せます。", role_user: "ユーザー", model_s_auto: "自動", effort_s_auto: "既定", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "ツール/スキルを指名（AI が優先使用）", chat_model: "モデル切替", chat_effort: "思考レベル", model_auto: "モデル自動選択", effort_auto: "レベル既定", effort_low: "レベル低", effort_mid: "レベル中", effort_high: "レベル高", mention_ok: "完了", mention_none: "指名できるスキルや MCP ツールがありません", confirm_title: "操作の確認", confirm_yes: "OK", chat_pasted: "添付を貼り付けました", chat_pin: "固定", chat_unpin: "固定解除", chat_archive: "アーカイブ", chat_unarchive: "アーカイブ解除", chat_archived: "アーカイブ済み", chat_hero_sub: "何を話す？下から選んでもいいよ", chat_chip_1: "Python の小さなスクリプトを書いて", chat_chip_2: "今日のチャットを日報にまとめて", chat_chip_3: "このエラーメッセージを解説して", chat_chip_4: "毎晩9時に日記をリマインドして", chat_new: "新しいチャット", chat_new_name: "ウェブチャット {n}", chat_busy: "このセッションは返信中です", chat_density: "表示密度", density_brief: "簡潔", density_detail: "詳細", steps_count: "ツール呼び出し {n}件", steps_running: "実行中…", copy: "コピー", copied: "コピーしました", msgs_count: "{n} 件のメッセージ", session_summary: "コンテキスト要約",
      stat_usage: "今日の使用量", backup_export: "設定をエクスポート", backup_import: "設定をインポート", audit_filter: "絞り込み…", col_preview: "最新メッセージ",
      subtitle: "汎用エージェント",
      nav_overview: "概要", nav_chat: "チャット", nav_models: "モデル", nav_personas: "ペルソナ",
      nav_tools: "ツール", nav_extensions: "拡張", nav_tasks: "タスク", nav_memory: "記憶", nav_sessions: "セッション",
      nav_knowledge: "ナレッジ", knowledge_desc: "共有ライブラリ：関連する断片は会話に自動注入され、knowledge_search でも検索できます", kb_add: "項目を追加", kb_search_ph: "検索…", kb_stats_line: "項目 {e} · チャンク {c}", kb_list_empty: "まだ項目がありません。上のボタンから追加してください", kb_title_label: "タイトル", kb_source_label: "ソース（任意）", kb_content_label: "内容", kb_need_title_content: "タイトルと内容が必要です", kb_triggers_label: "トリガーキーワード（任意・ワールドブック）", kb_triggers_ph: "例：魔王, 北塔（カンマ区切り、一致で注入）", kb_priority_label: "トリガー優先度（大きい順）", kb_cooldown_label: "トリガークールダウン分（空欄でデフォルト、0 で無効）",
      nav_audit: "監査", nav_settings: "設定",
      sess_members: "メンバー", sess_members_hint: "メンバー許可リスト（1 行に 1 つのユーザー ID、* は全員。空で全員に戻す）", sess_sources_hint: "他のセッションの入力を受け入れる（1 行に 1 つの chat_key、例 onebot11:group:123。そのメッセージはこのセッションに転送されます）", kb_export: "エクスポート", kb_import: "インポート",
      nav_orchestrate: "オーケストレーション", orchestrate_desc: "エージェント一覧：モデルチェーン · 正常性 · 実行状態 · タスクタイムライン", orch_model_chain: "モデルチェーン（フェイルオーバー順）", orch_chain_hint: "ドラッグでフェイルオーバー順を変更、離すと自動保存", orch_chain_saved: "チェーン順を保存しました", orch_health: "モデル正常性", health_ok: "すべてのモデルは正常", health_cooldown: "クールダウン中", health_fails: "連続 {n} 回失敗", health_left: "残り {s} 秒", orch_running: "実行状態", running_none: "実行中のタスクはありません", orch_timeline: "タスクタイムライン", timeline_empty: "タスクと実行履歴はまだありません", orch_capabilities: "機能スイッチ", caps_tools: "ツール", caps_skills: "スキル", task_next: "次回", task_last: "前回", task_status_error: "前回失敗", cost_title: "コスト概算", cost_total: "14 日合計", cost_daily: "日次コスト（棒）と累積（線）", cost_by_model: "モデル別", cost_empty: "単価付きの使用量はまだありません（モデル価格は models.dev カタログより）",
      overview_desc: "エージェントの実行状況", overview_detail: "詳細",
      stat_models: "モデル", stat_tools: "ツール", stat_eco: "生態ツール", stat_sessions: "セッション",
      stat_tasks: "タスク", stat_mcp: "MCP", stat_extensions: "拡張", stat_security: "セキュリティ",
      on: "オン", off: "オフ", takeovers: "接管中のセッション", trust_on: "完全信頼",
      chat_desc: "エージェントを直接テスト", chat_placeholder: "何か話しかけて…", chat_send: "送信",

      chat_thinking: "思考中…", chat_empty: "まだ会話がありません",
      models_desc: "OpenAI 互換エンドポイント、プール順にフェイルオーバー", models_add: "モデル追加 / 更新",
      models_name: "名前", models_id: "モデル名", models_temp: "温度", models_maxtok: "最大トークン", model_smart: "自動設定", model_smart_hint: "models.dev からコンテキスト・能力・価格を自動補完", model_context: "コンテキスト長", model_max_output: "最大出力トークン", model_detect: "models.dev から取得", model_detected: "models.dev のメタデータを反映しました", model_detect_empty: "models.dev に未収録です。手動で入力してください", model_advanced: "詳細設定", model_input_types: "入力タイプ", model_input_text: "テキスト", model_input_image: "画像", model_input_video: "動画", model_input_pdf: "PDF", model_caps: "モデル能力", model_tool_call: "ツール呼び出し", model_reasoning: "推論", model_price: "単価（100万トークンあたり）", model_price_in: "入力", model_price_out: "出力", model_enabled: "このモデルを有効化", model_manage: "モデル設定", model_refresh: "能力と価格を更新", model_refresh_done: "{n} 項目を更新しました", model_delete_confirm: "このモデルを削除しますか？", model_cap_tools: "ツール", model_cap_no_tools: "ツール不可", model_cap_vision: "視覚", model_cap_reason: "推論", model_unknown: "能力不明", orch_chain_top_no_tools: "先頭モデルに「ツール呼び出し」の印がありません。ツール有効の会話ではスキップされます。モデルプールで能力を補完するか手動で有効にしてください。", model_none: "モデルがまだありません", model_add_title: "モデル追加", model_edit_title: "モデル設定を編集",
      save: "保存", actions: "操作", test: "テスト", edit: "編集", del: "削除",
      models_empty: "モデルプールが空です", model_test_ok: "モデル OK", model_test_fail: "モデル NG",
      saved: "保存しました", deleted: "削除しました", confirm_del: "削除しますか？",
      personas_desc: "ペルソナ = システムプロンプト + ツール白名單", personas_edit: "ペルソナ編集",
      personas_pid: "ペルソナ id", personas_pname: "名前", personas_system: "システムプロンプト",
      personas_tools: "ツール白名單（カンマ区切り、空 = 全部、eco_* 可）",
      personas_builtin: "內置", personas_empty: "カスタムペルソナはまだありません",
      bindings: "セッション binding", bind_btn: "binding", bind_hint: "chat_key（例 onebot11:group:123）",
      tools_desc: "內置 + 生態サービス橋 + MCP", tools_refresh: "生態橋を更新",
      tools_filter: "絞り込み…", tools_empty: "該当ツールなし",
      extensions_desc: "外部モジュールのツールとペルソナ", ext_none: "拡張モジュールなし：meta.services を宣言すれば自動接続", ext_personas_col: "ペルソナ", ext_schemas_col: "Schema",
      tasks_desc: "create_scheduled_task で作成", tasks_empty: "タスクはありません",
      col_next: "次回", col_target: "対象", col_prompt: "内容", col_schedule: "スケジュール",
      memory_desc: "長期記憶のスコープ", memory_pick: "スコープをクリックで表示", memory_clear: "クリア",
      memory_empty: "記憶がありません",
      profile_card_title: "ユーザープロファイル", profile_card_user: "ユーザー", profile_card_empty: "プロファイルなし",
      profile_card_clear: "プロファイルを消去", profile_card_confirm: "このユーザーのプロファイルを消去しますか？",
      sessions_desc: "会話ウィンドウとペルソナ binding", sessions_empty: "セッションなし",
      col_turns: "ターン", col_updated: "更新", reset_btn: "リセット", col_persona: "ペルソナ",
      audit_desc: "PC 操作と確認の記錄", audit_empty: "監査記錄なし",
      col_tool: "ツール", col_detail: "詳細",
      settings_desc: "實行時設定、保存で即反映", settings_saved: "設定を保存しました",
      group_model: "モデル", group_trigger: "トリガー", group_security: "セキュリティ", group_chat: "チャット", group_memory: "記憶",
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
      settings_search_ph: "設定項を検索…", settings_no_match: "一致する設定項はありません", settings_invalid_value: "値が無効です。修正してください", settings_json_bad: "JSON 形式エラー", settings_no_change: "変更はありません", settings_danger_confirm: "セキュリティ関連の設定を変更しようとしています。続行しますか？", settings_unsaved: "未保存の設定変更があります。破棄して離れますか？", settings_save_partial: "一部の項目が検証に失敗したため保存されませんでした", settings_dangerous: "危険", settings_show: "表示", settings_hide: "非表示", settings_list_add: "項目を追加", plugin_settings_empty: "設定可能なプラグインはまだありません：qvq_settings サービスを提供するとここに表示されます",
      settings_sec_context: "コンテキストと圧縮", settings_sec_forward: "まとめ転送", settings_sec_reply: "分割返信", settings_sec_flow: "実行ポリシー", settings_sec_misc: "その他",
      backup_title: "データバックアップ", backup_desc: "モデルプール・ペルソナ・タスク・記憶・MCP・スキル・全設定を含む完全バックアップをエクスポートします。インポートは項目ごとに検証されてから適用されます。", backup_export_data: "データバックアップをエクスポート", backup_import_data: "データバックアップをインポート",
      orch_timeline_att: "実行中 / 失敗のタスクと実行記録のみ表示",
      loading: "読み込み中…"
    },
    "ru": {
      nav_group_core: "Ядро", nav_group_config: "Возможности", nav_group_data: "Данные", nav_mcp: "MCP", mcp_desc: "Серверы и инструменты Model Context Protocol", mcp_servers: "Серверы", mcp_tools: "MCP-инструменты", mcp_connect_all: "Подключить все", mcp_connect: "Подключить", mcp_disconnect: "Отключить", mcp_status_on: "подключен", mcp_status_off: "отключен", mcp_none: "MCP-серверов пока нет — нажмите, чтобы добавить", queue_send_now: "Отправить сейчас", queue_added: "В очереди — отправится после текущего ответа", queue_edit: "Вернуть в поле ввода", queue_badge: "В очереди", chat_delete: "Удалить", session_delete_confirm: "Удалить эту сессию? Действие необратимо", session_deleted: "Удалено", chat_purge_archived: "Очистить архив", chat_stop: "Остановить генерацию", chat_cancelled: "(генерация остановлена)", chat_settings: "Настройки сессии", settings_save_session: "Сохранить в эту сессию", settings_apply_all: "Применить ко всем", share_export: "Экспорт Markdown", chat_persona_binding: "Привязка персоны", chat_export: "Экспорт сессии", chat_share: "Поделиться сессией", share_expires: "Срок действия ссылки", share_max_tokens: "Максимум токенов (бюджет видимого контекста)", share_create: "Создать ссылку", share_url: "Ссылка для обмена", share_hint: "Любой с этой ссылкой может читать сессию (лимиты: бюджет токенов и срок). Можно отозвать в любой момент.", role_user: "Пользователь", model_s_auto: "Авто", effort_s_auto: "Авто", effort_s_low: "Низк", effort_s_mid: "Сред", effort_s_high: "Высок", chat_mention: "Упомянуть инструменты/навыки (ИИ приоритизирует)", chat_model: "Сменить модель", chat_effort: "Уровень усилий", model_auto: "Авто-выбор модели", effort_auto: "Усилия: авто", effort_low: "Усилия: низкие", effort_mid: "Усилия: средние", effort_high: "Усилия: высокие", mention_ok: "Готово", mention_none: "Нет навыков или MCP-инструментов для упоминания", confirm_title: "Подтверждение", confirm_yes: "OK", chat_pasted: "Вложение вставлено", chat_pin: "Закрепить", chat_unpin: "Открепить", chat_archive: "В архив", chat_unarchive: "Из архива", chat_archived: "В архиве", chat_hero_sub: "О чём поболтаем? Или выбери тему ниже", chat_chip_1: "Напиши мне небольшой скрипт на Python", chat_chip_2: "Собери из чата отчёт за день", chat_chip_3: "Объясни эту ошибку", chat_chip_4: "Напоминай мне вести дневник в 21:00", chat_new: "Новый чат", chat_new_name: "Веб-чат {n}", chat_busy: "Эта сессия ещё отвечает", chat_density: "Детализация", density_brief: "Кратко", density_detail: "Подробно", steps_count: "{n} вызовов инструмента", steps_running: "выполняется…", copy: "Копировать", copied: "Скопировано", msgs_count: "{n} сообщений", session_summary: "Сводка контекста",
      stat_usage: "Расход сегодня", backup_export: "Экспорт конфига", backup_import: "Импорт конфига", audit_filter: "Фильтр инструмента/пользователя…", col_preview: "Последнее сообщение",
      subtitle: "универсальный агент",
      nav_overview: "Обзор", nav_chat: "Чат", nav_models: "Модели", nav_personas: "Личности",
      nav_tools: "Инструменты", nav_extensions: "Расширения", nav_tasks: "Задачи", nav_memory: "Память", nav_sessions: "Сессии",
      nav_knowledge: "База знаний", knowledge_desc: "Общая библиотека: подходящие фрагменты автоматически попадают в диалог, доступен поиск через knowledge_search", kb_add: "Добавить запись", kb_search_ph: "Поиск…", kb_stats_line: "Записей: {e} · Фрагментов: {c}", kb_list_empty: "Записей пока нет — добавьте через кнопку выше", kb_title_label: "Заголовок", kb_source_label: "Источник (необязательно)", kb_content_label: "Содержимое", kb_need_title_content: "Нужны заголовок и содержимое", kb_triggers_label: "Ключевые слова триггера (опционально, лорбук)", kb_triggers_ph: "напр.: демон, башня (через запятую)", kb_priority_label: "Приоритет триггера (выше — раньше)", kb_cooldown_label: "Кулдаун триггера, мин (пусто — по умолчанию, 0 — нет)",
      nav_audit: "Аудит", nav_settings: "Настройки",
      sess_members: "Участники", sess_members_hint: "Белый список участников (один ID в строке, * = все; пусто — вернуть всех)", sess_sources_hint: "Принимать ввод из других чатов (один chat_key в строке, напр. onebot11:group:123; их сообщения направляются в этот чат)", kb_export: "Экспорт", kb_import: "Импорт",
      nav_orchestrate: "Оркестрация", orchestrate_desc: "Обзор агента: цепочка моделей · здоровье · выполнение · время задач", orch_model_chain: "Цепочка моделей (порядок failover)", orch_chain_hint: "Перетащите, чтобы изменить порядок failover; сохраняется автоматически", orch_chain_saved: "Порядок цепочки сохранён", orch_health: "Здоровье моделей", health_ok: "Все модели исправны", health_cooldown: "Охлаждение", health_fails: "Подряд сбоев: {n}", health_left: "Осталось {s} с", orch_running: "Выполнение", running_none: "Нет запущенных задач", orch_timeline: "Время задач", timeline_empty: "Задач и запусков пока нет", orch_capabilities: "Переключатели возможностей", caps_tools: "Инструменты", caps_skills: "Навыки", task_next: "Далее", task_last: "Прошлый", task_status_error: "Прошлый запуск не удался", cost_title: "Оценка расходов", cost_total: "Сумма за 14 дней", cost_daily: "Расходы по дням (столбцы) и накопительно (линия)", cost_by_model: "По моделям", cost_empty: "Нет данных с ценами (цены моделей из каталога models.dev)",
      overview_desc: "Обзор состояния агента", overview_detail: "Подробности",
      stat_models: "Модели", stat_tools: "Инструменты", stat_eco: "Эко-инстр.", stat_sessions: "Сессии",
      stat_tasks: "Задачи", stat_mcp: "MCP", stat_extensions: "Расширения", stat_security: "Безопасность",
      on: "вкл", off: "выкл", takeovers: "Под контролем", trust_on: "Полное доверие",
      chat_desc: "прямой тест агента, инструменты доступны", chat_placeholder: "Скажите что-нибудь…", chat_send: "Отправить",
      chat_thinking: "думаю…", chat_empty: "Диалогов пока нет",
      models_desc: "OpenAI-совместимые endpoint'ы с failover по пулу", models_add: "Добавить / обновить модель",
      models_name: "Имя", models_id: "Модель", models_temp: "Температура", models_maxtok: "Макс. токенов", model_smart: "Автонастройка", model_smart_hint: "Заполнить контекст, возможности и цену из models.dev", model_context: "Контекстное окно", model_max_output: "Макс. выходных токенов", model_detect: "Определить из models.dev", model_detected: "Метаданные заполнены из models.dev", model_detect_empty: "Нет в models.dev — заполните вручную", model_advanced: "Дополнительно", model_input_types: "Типы ввода", model_input_text: "Текст", model_input_image: "Изображение", model_input_video: "Видео", model_input_pdf: "PDF", model_caps: "Возможности модели", model_tool_call: "Вызов инструментов", model_reasoning: "Рассуждение", model_price: "Цена (за 1M токенов)", model_price_in: "Ввод", model_price_out: "Вывод", model_enabled: "Включить модель", model_manage: "Модели", model_refresh: "Обновить возможности и цены", model_refresh_done: "Обновлено полей: {n}", model_delete_confirm: "Удалить эту модель?", model_cap_tools: "инструменты", model_cap_no_tools: "без инструментов", model_cap_vision: "зрение", model_cap_reason: "рассуждение", model_unknown: "неизвестно", orch_chain_top_no_tools: "У первой модели не отмечен вызов инструментов; диалоги с инструментами её пропустят. Заполните возможности в пуле моделей или включите вручную.", model_none: "Моделей пока нет", model_add_title: "Добавить модель", model_edit_title: "Настройка модели",
      save: "Сохранить", actions: "Действия", test: "Тест", edit: "Правка", del: "Удалить",
      models_empty: "Пул моделей пуст, добавьте", model_test_ok: "модель работает", model_test_fail: "модель недоступна",
      saved: "Сохранено", deleted: "Удалено", confirm_del: "Удалить?",
      personas_desc: "личность = system prompt + белый список инструментов", personas_edit: "Правка личности",
      personas_pid: "id личности", personas_pname: "Имя", personas_system: "System prompt",
      personas_tools: "Белый список инструментов (через запятую, пусто = все, eco_* можно)",
      personas_builtin: "встроенная", personas_empty: "Своих личностей пока нет",
      bindings: "Привязки сессий", bind_btn: "Привязать", bind_hint: "chat_key (напр. onebot11:group:123)",
      tools_desc: "встроенные + службы экосистемы + MCP", tools_refresh: "Обновить эко-мост",
      tools_filter: "Фильтр…", tools_empty: "Нет подходящих инструментов",
      extensions_desc: "Инструменты и личности внешних модулей", ext_none: "Расширений нет: модуль с meta.services подключается сам", ext_personas_col: "Личности", ext_schemas_col: "Схемы",
      tasks_desc: "создаются агентом через create_scheduled_task", tasks_empty: "Задач нет",
      col_next: "След. запуск", col_target: "Цель", col_prompt: "Промпт", col_schedule: "Расписание",
      memory_desc: "области долговременной памяти", memory_pick: "кликните область для списка", memory_clear: "Очистить",
      memory_empty: "В этой области памяти нет",
      profile_card_title: "Профиль пользователя", profile_card_user: "Пользователь", profile_card_empty: "Профиль пуст",
      profile_card_clear: "Очистить профиль", profile_card_confirm: "Очистить профиль этого пользователя?",
      sessions_desc: "окна диалогов и привязки личностей", sessions_empty: "Сессий нет",
      col_turns: "Ходы", col_updated: "Обновлено", reset_btn: "Сброс", col_persona: "Личность",
      audit_desc: "операции на ПК и подтверждения", audit_empty: "Записей аудита нет",
      col_tool: "Инструмент", col_detail: "Детали",
      settings_desc: "конфигурация, применяется сразу", settings_saved: "Конфиг сохранен",
      group_model: "Модель", group_trigger: "Триггеры", group_security: "Безопасность", group_chat: "Чат", group_memory: "Память",
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
      settings_search_ph: "Поиск настроек…", settings_no_match: "Нет подходящих настроек", settings_invalid_value: "Недопустимое значение — исправьте", settings_json_bad: "Неверный JSON", settings_no_change: "Нет изменений для сохранения", settings_danger_confirm: "Вы меняете настройки безопасности. Продолжить?", settings_unsaved: "Есть несохранённые изменения настроек. Покинуть и отбросить их?", settings_save_partial: "Часть полей не прошла проверку и не сохранена", settings_dangerous: "опасно", settings_show: "Показать", settings_hide: "Скрыть", settings_list_add: "Добавить", plugin_settings_empty: "Пока нет плагинов с настройками: плагин со службой qvq_settings появится здесь",
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

  function toast(msg, isErr) {
    var box = document.createElement("div");
    box.className = "qvq-toast" + (isErr ? " err" : "");
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

  function api(path, method, body) {
    var headers = { "Content-Type": "application/json" };
    var token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch("/QvQChat" + path, {
      method: method || "GET",
      headers: headers,
      body: body ? JSON.stringify(body) : undefined
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        data = data && typeof data === "object" ? data : {};
        // 显式携带 HTTP 状态：错误不再被吞成"空数据/空会话"
        data.__http = resp.status;
        if (resp.status === 401) {
          activeToken = "";
          try { localStorage.removeItem("qvq_token"); } catch (e) {}
          if (typeof showLogin === "function") showLogin();
        }
        return data;
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
        // 回写命中的令牌，令牌轮换后下次启动不再依赖已失效的候选
        try { localStorage.setItem("qvq_token", chosen); } catch (e) {}
      }
      return ok ? chosen : "";
    });
  }

  // 导航点击早期委托：不依赖 initApp 绑定时序，auth 链完成前的点击也不丢
  (function bindNavEarly() {
    var nav = document.getElementById("qvq-nav");
    if (!nav) return;
    nav.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".qvq-nav-btn") : null;
      if (btn) switchTab(btn.getAttribute("data-tab"));
    });
  })();

