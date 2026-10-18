(function () {
  var I18N = {
    "zh-CN": {
      nav_group_core: "核心", nav_group_config: "能力", nav_group_data: "数据", nav_mcp: "MCP", mcp_desc: "MCP 服务器与工具接入", mcp_servers: "服务器", mcp_tools: "MCP 工具", mcp_connect_all: "连接全部", mcp_connect: "连接", mcp_disconnect: "断开", mcp_status_on: "已连接", mcp_status_off: "未连接", mcp_none: "尚未配置 MCP 服务器，点击此处添加", queue_send_now: "立即发送", queue_added: "已暂存，当前回复完成后自动发送", chat_stop: "停止生成", chat_cancelled: "（已停止生成）", chat_settings: "会话设置", settings_save_session: "保存到本会话", settings_apply_all: "应用到全局", share_export: "导出 Markdown", chat_persona_binding: "人格绑定", chat_export: "导出会话", chat_share: "分享会话", share_expires: "链接有效期", share_max_tokens: "最大允许 token（约可见的上下文预算）", share_create: "生成分享链接", share_url: "分享链接", share_hint: "任何人通过此链接可只读查看该会话（受 token 预算与有效期限制），可随时撤销。", role_user: "用户", model_s_auto: "自动", effort_s_auto: "默认", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "提名工具/技能（AI 优先使用）", chat_model: "切换模型", chat_effort: "思考强度", model_auto: "自动选择模型", effort_auto: "强度默认", effort_low: "强度低", effort_mid: "强度中", effort_high: "强度高", mention_ok: "完成", mention_none: "暂无可提名的技能或 MCP 工具", confirm_title: "确认操作", confirm_yes: "确定", chat_pasted: "已粘贴附件", chat_pin: "置顶", chat_unpin: "取消置顶", chat_archive: "归档", chat_unarchive: "取消归档", chat_archived: "已归档", chat_hero_sub: "有什么想聊的？或者从下面挑一个开始", chat_chip_1: "帮我写个 Python 小脚本", chat_chip_2: "把今天的聊天总结成周报", chat_chip_3: "解释一段报错信息", chat_chip_4: "每天晚上九点提醒我写日记", chat_new: "新对话", chat_new_name: "网页对话 {n}", chat_busy: "当前会话正在回复中", chat_density: "信息密度", density_brief: "简洁", density_detail: "详细", steps_count: "{n} 步工具调用", steps_running: "运行中…", copy: "复制", copied: "已复制", msgs_count: "{n} 条消息", session_summary: "上下文摘要",
      stat_usage: "今日用量", backup_export: "导出配置", backup_import: "导入配置", audit_filter: "过滤工具/用户…", col_preview: "最近消息",
      subtitle: "通用智能体",
      nav_overview: "概览", nav_chat: "对话", nav_models: "模型池", nav_personas: "人格",
      nav_tools: "工具", nav_extensions: "扩展", nav_tasks: "定时任务", nav_memory: "记忆", nav_sessions: "会话",
      nav_audit: "审计", nav_settings: "设置",
      overview_desc: "智能体运行一览", overview_detail: "运行详情",
      stat_models: "模型", stat_tools: "工具", stat_eco: "生态工具", stat_sessions: "会话",
      stat_tasks: "任务", stat_mcp: "MCP", stat_extensions: "扩展", stat_security: "安全",
      on: "开", off: "关", takeovers: "接管中会话", trust_on: "完全信任",
      chat_desc: "直接测试智能体", chat_placeholder: "说点什么…", chat_send: "发送",
      chat_thinking: "思考中…", chat_empty: "还没有对话",
      models_desc: "任意 OpenAI 兼容服务商，按顺序故障转移", models_add: "添加 / 更新模型",
      models_name: "名称", models_id: "模型名", models_temp: "温度", models_maxtok: "最大 token",
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
      sessions_desc: "会话与人格绑定", sessions_empty: "暂无会话",
      col_turns: "轮数", col_updated: "更新时间", reset_btn: "重置", col_persona: "人格",
      audit_desc: "操作与确认记录", audit_empty: "暂无审计记录",
      col_tool: "工具", col_detail: "详情",
      settings_desc: "运行时配置，保存即生效", settings_saved: "配置已保存",
      group_model: "模型", group_trigger: "触发", group_security: "安全", group_chat: "对话", group_memory: "记忆",
      group_tools: "工具", group_eco: "生态", group_mcp: "MCP", group_task: "任务", group_access: "权限", group_usage: "用量",
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
      loading: "加载中…"
    },
    "zh-TW": {
      nav_group_core: "核心", nav_group_config: "能力", nav_group_data: "資料", nav_mcp: "MCP", mcp_desc: "MCP 伺服器與工具接入", mcp_servers: "伺服器", mcp_tools: "MCP 工具", mcp_connect_all: "連接全部", mcp_connect: "連接", mcp_disconnect: "斷開", mcp_status_on: "已連接", mcp_status_off: "未連接", mcp_none: "尚未配置 MCP 伺服器，點擊此處新增", queue_send_now: "立即傳送", queue_added: "已暫存，目前回覆完成後自動傳送", chat_stop: "停止產生", chat_cancelled: "（已停止產生）", chat_settings: "會話設置", settings_save_session: "儲存到此會話", settings_apply_all: "套用到全域", share_export: "匯出 Markdown", chat_persona_binding: "人格綁定", chat_export: "匯出會話", chat_share: "分享會話", share_expires: "連結有效期", share_max_tokens: "最大允許 token（約可見的上下文預算）", share_create: "產生分享連結", share_url: "分享連結", share_hint: "任何人透過此連結可唯讀檢視該會話（受 token 預算與有效期限制），可隨時撤銷。", role_user: "使用者", model_s_auto: "自動", effort_s_auto: "預設", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "提名工具/技能（AI 優先使用）", chat_model: "切換模型", chat_effort: "思考強度", model_auto: "自動選擇模型", effort_auto: "強度預設", effort_low: "強度低", effort_mid: "強度中", effort_high: "強度高", mention_ok: "完成", mention_none: "暫無可提名的技能或 MCP 工具", confirm_title: "確認操作", confirm_yes: "確定", chat_pasted: "已貼上附件", chat_pin: "置頂", chat_unpin: "取消置頂", chat_archive: "歸檔", chat_unarchive: "取消歸檔", chat_archived: "已歸檔", chat_hero_sub: "有什麼想聊的？或從下面挑一個開始", chat_chip_1: "幫我寫個 Python 小腳本", chat_chip_2: "把今天的聊天整理成週報", chat_chip_3: "解釋一段錯誤訊息", chat_chip_4: "每天晚上九點提醒我寫日記", chat_new: "新對話", chat_new_name: "網頁對話 {n}", chat_busy: "目前會話正在回覆中", chat_density: "資訊密度", density_brief: "簡潔", density_detail: "詳細", steps_count: "{n} 次工具呼叫", steps_running: "執行中…", copy: "複製", copied: "已複製", msgs_count: "{n} 條訊息", session_summary: "上下文摘要",
      stat_usage: "今日用量", backup_export: "匯出配置", backup_import: "匯入配置", audit_filter: "過濾工具/使用者…", col_preview: "最近訊息",
      subtitle: "通用智慧代理",
      nav_overview: "概覽", nav_chat: "對話", nav_models: "模型池", nav_personas: "人格",
      nav_tools: "工具", nav_extensions: "擴展", nav_tasks: "定時任務", nav_memory: "記憶", nav_sessions: "會話",
      nav_audit: "審計", nav_settings: "設定",
      overview_desc: "智慧代理運行一覽", overview_detail: "運行詳情",
      stat_models: "模型", stat_tools: "工具", stat_eco: "生態工具", stat_sessions: "會話",
      stat_tasks: "任務", stat_mcp: "MCP", stat_extensions: "擴展", stat_security: "安全",
      on: "開", off: "關", takeovers: "接管中會話", trust_on: "完全信任",
      chat_desc: "直接測試智慧代理", chat_placeholder: "說點什麼…", chat_send: "傳送",
      chat_thinking: "思考中…", chat_empty: "還沒有對話",
      models_desc: "任意 OpenAI 相容服務商，依順序故障轉移", models_add: "新增 / 更新模型",
      models_name: "名稱", models_id: "模型名", models_temp: "溫度", models_maxtok: "最大 token",
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
      sessions_desc: "會話與人格綁定", sessions_empty: "暫無會話",
      col_turns: "輪數", col_updated: "更新時間", reset_btn: "重置", col_persona: "人格",
      audit_desc: "操作與確認記錄", audit_empty: "暫無審計記錄",
      col_tool: "工具", col_detail: "詳情",
      settings_desc: "運行時配置，儲存即生效", settings_saved: "配置已儲存",
      group_model: "模型", group_trigger: "觸發", group_security: "安全", group_chat: "對話", group_memory: "記憶",
      group_tools: "工具", group_eco: "生態", group_mcp: "MCP", group_task: "任務", group_access: "權限", group_usage: "用量",
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
      loading: "載入中…"
    },
    "en": {
      nav_group_core: "Core", nav_group_config: "Capabilities", nav_group_data: "Data", nav_mcp: "MCP", mcp_desc: "Model Context Protocol servers and tool access", mcp_servers: "Servers", mcp_tools: "MCP tools", mcp_connect_all: "Connect all", mcp_connect: "Connect", mcp_disconnect: "Disconnect", mcp_status_on: "connected", mcp_status_off: "disconnected", mcp_none: "No MCP servers yet — click here to add one", queue_send_now: "Send now", queue_added: "Queued — will send after the current reply", chat_stop: "Stop generating", chat_cancelled: "(generation stopped)", chat_settings: "Session settings", settings_save_session: "Save to this session", settings_apply_all: "Apply to all sessions", share_export: "Export Markdown", chat_persona_binding: "Persona binding", chat_export: "Export session", chat_share: "Share session", share_expires: "Link expires in", share_max_tokens: "Max tokens allowed (visible context budget)", share_create: "Create share link", share_url: "Share link", share_hint: "Anyone with this link can view the session read-only, limited by the token budget and expiry. Revoke anytime.", role_user: "User", model_s_auto: "auto", effort_s_auto: "Auto", effort_s_low: "Low", effort_s_mid: "Mid", effort_s_high: "High", chat_mention: "Mention tools/skills (AI prioritizes them)", chat_model: "Switch model", chat_effort: "Effort level", model_auto: "Auto model", effort_auto: "Effort auto", effort_low: "Effort low", effort_mid: "Effort mid", effort_high: "Effort high", mention_ok: "Done", mention_none: "No skills or MCP tools to mention yet", confirm_title: "Confirm", confirm_yes: "OK", chat_pasted: "Attachment pasted", chat_pin: "Pin", chat_unpin: "Unpin", chat_archive: "Archive", chat_unarchive: "Unarchive", chat_archived: "Archived", chat_hero_sub: "What shall we talk about? Or pick a starter below", chat_chip_1: "Write me a small Python script", chat_chip_2: "Summarize today's chat into a report", chat_chip_3: "Explain this error message", chat_chip_4: "Remind me to journal at 9pm daily", chat_new: "New chat", chat_new_name: "Web chat {n}", chat_busy: "This session is still replying", chat_density: "Detail level", density_brief: "Brief", density_detail: "Detailed", steps_count: "{n} tool calls", steps_running: "running…", copy: "Copy", copied: "Copied", msgs_count: "{n} messages", session_summary: "Context summary",
      stat_usage: "Today usage", backup_export: "Export config", backup_import: "Import config", audit_filter: "Filter tool/user…", col_preview: "Last message",
      subtitle: "universal agent",
      nav_overview: "Overview", nav_chat: "Chat", nav_models: "Models", nav_personas: "Personas",
      nav_tools: "Tools", nav_extensions: "Extensions", nav_tasks: "Tasks", nav_memory: "Memory", nav_sessions: "Sessions",
      nav_audit: "Audit", nav_settings: "Settings",
      overview_desc: "agent runtime at a glance", overview_detail: "Details",
      stat_models: "Models", stat_tools: "Tools", stat_eco: "Eco tools", stat_sessions: "Sessions",
      stat_tasks: "Tasks", stat_mcp: "MCP", stat_extensions: "Extensions", stat_security: "Security",
      on: "on", off: "off", takeovers: "Takeovers", trust_on: "Full trust",
      chat_desc: "test the agent directly", chat_placeholder: "Say something…", chat_send: "Send",
      chat_thinking: "thinking…", chat_empty: "No conversation yet",
      models_desc: "Any OpenAI-compatible provider, with failover", models_add: "Add / update model",
      models_name: "Name", models_id: "Model", models_temp: "Temperature", models_maxtok: "Max tokens",
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
      sessions_desc: "Sessions and persona bindings", sessions_empty: "No sessions",
      col_turns: "Turns", col_updated: "Updated", reset_btn: "Reset", col_persona: "Persona",
      audit_desc: "Operation and confirmation log", audit_empty: "No audit records",
      col_tool: "Tool", col_detail: "Detail",
      settings_desc: "runtime configuration, applied on save", settings_saved: "Config saved",
      group_model: "Model", group_trigger: "Trigger", group_security: "Security", group_chat: "Chat", group_memory: "Memory",
      group_tools: "Tools", group_eco: "Eco", group_mcp: "MCP", group_task: "Task", group_access: "Access", group_usage: "Usage",
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
      loading: "Loading…"
    },
    "ja": {
      nav_group_core: "コア", nav_group_config: "機能", nav_group_data: "データ", nav_mcp: "MCP", mcp_desc: "Model Context Protocol サーバーとツール接続", mcp_servers: "サーバー", mcp_tools: "MCP ツール", mcp_connect_all: "全て接続", mcp_connect: "接続", mcp_disconnect: "切断", mcp_status_on: "接続済", mcp_status_off: "未接続", mcp_none: "MCP サーバー未登録 — ここをクリックして追加", queue_send_now: "今すぐ送信", queue_added: "一時保存しました。現在の返信後に自動送信します", chat_stop: "生成を停止", chat_cancelled: "（生成を停止しました）", chat_settings: "セッション設定", settings_save_session: "このセッションに保存", settings_apply_all: "全セッションに適用", share_export: "Markdown をエクスポート", chat_persona_binding: "ペルソナ固定", chat_export: "セッションをエクスポート", chat_share: "セッションを共有", share_expires: "リンク有効期限", share_max_tokens: "最大トークン（見える文脈の予算）", share_create: "共有リンクを作成", share_url: "共有リンク", share_hint: "このリンクを知る人は誰でもセッションを読み取り専用で閲覧できます（トークン予算と有効期限で制限）。いつでも取り消せます。", role_user: "ユーザー", model_s_auto: "自動", effort_s_auto: "既定", effort_s_low: "低", effort_s_mid: "中", effort_s_high: "高", chat_mention: "ツール/スキルを指名（AI が優先使用）", chat_model: "モデル切替", chat_effort: "思考レベル", model_auto: "モデル自動選択", effort_auto: "レベル既定", effort_low: "レベル低", effort_mid: "レベル中", effort_high: "レベル高", mention_ok: "完了", mention_none: "指名できるスキルや MCP ツールがありません", confirm_title: "操作の確認", confirm_yes: "OK", chat_pasted: "添付を貼り付けました", chat_pin: "固定", chat_unpin: "固定解除", chat_archive: "アーカイブ", chat_unarchive: "アーカイブ解除", chat_archived: "アーカイブ済み", chat_hero_sub: "何を話す？下から選んでもいいよ", chat_chip_1: "Python の小さなスクリプトを書いて", chat_chip_2: "今日のチャットを日報にまとめて", chat_chip_3: "このエラーメッセージを解説して", chat_chip_4: "毎晩9時に日記をリマインドして", chat_new: "新しいチャット", chat_new_name: "ウェブチャット {n}", chat_busy: "このセッションは返信中です", chat_density: "表示密度", density_brief: "簡潔", density_detail: "詳細", steps_count: "ツール呼び出し {n}件", steps_running: "実行中…", copy: "コピー", copied: "コピーしました", msgs_count: "{n} 件のメッセージ", session_summary: "コンテキスト要約",
      stat_usage: "今日の使用量", backup_export: "設定をエクスポート", backup_import: "設定をインポート", audit_filter: "絞り込み…", col_preview: "最新メッセージ",
      subtitle: "汎用エージェント",
      nav_overview: "概要", nav_chat: "チャット", nav_models: "モデル", nav_personas: "ペルソナ",
      nav_tools: "ツール", nav_extensions: "拡張", nav_tasks: "タスク", nav_memory: "記憶", nav_sessions: "セッション",
      nav_audit: "監査", nav_settings: "設定",
      overview_desc: "エージェントの実行状況", overview_detail: "詳細",
      stat_models: "モデル", stat_tools: "ツール", stat_eco: "生態ツール", stat_sessions: "セッション",
      stat_tasks: "タスク", stat_mcp: "MCP", stat_extensions: "拡張", stat_security: "セキュリティ",
      on: "オン", off: "オフ", takeovers: "接管中のセッション", trust_on: "完全信頼",
      chat_desc: "エージェントを直接テスト", chat_placeholder: "何か話しかけて…", chat_send: "送信",

      chat_thinking: "思考中…", chat_empty: "まだ会話がありません",
      models_desc: "OpenAI 互換エンドポイント、プール順にフェイルオーバー", models_add: "モデル追加 / 更新",
      models_name: "名前", models_id: "モデル名", models_temp: "温度", models_maxtok: "最大トークン",
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
      sessions_desc: "会話ウィンドウとペルソナ binding", sessions_empty: "セッションなし",
      col_turns: "ターン", col_updated: "更新", reset_btn: "リセット", col_persona: "ペルソナ",
      audit_desc: "PC 操作と確認の記錄", audit_empty: "監査記錄なし",
      col_tool: "ツール", col_detail: "詳細",
      settings_desc: "實行時設定、保存で即反映", settings_saved: "設定を保存しました",
      group_model: "モデル", group_trigger: "トリガー", group_security: "セキュリティ", group_chat: "チャット", group_memory: "記憶",
      group_tools: "ツール", group_eco: "エコ", group_mcp: "MCP", group_task: "タスク", group_access: "アクセス", group_usage: "使用量",
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
      loading: "読み込み中…"
    },
    "ru": {
      nav_group_core: "Ядро", nav_group_config: "Возможности", nav_group_data: "Данные", nav_mcp: "MCP", mcp_desc: "Серверы и инструменты Model Context Protocol", mcp_servers: "Серверы", mcp_tools: "MCP-инструменты", mcp_connect_all: "Подключить все", mcp_connect: "Подключить", mcp_disconnect: "Отключить", mcp_status_on: "подключен", mcp_status_off: "отключен", mcp_none: "MCP-серверов пока нет — нажмите, чтобы добавить", queue_send_now: "Отправить сейчас", queue_added: "В очереди — отправится после текущего ответа", chat_stop: "Остановить генерацию", chat_cancelled: "(генерация остановлена)", chat_settings: "Настройки сессии", settings_save_session: "Сохранить в эту сессию", settings_apply_all: "Применить ко всем", share_export: "Экспорт Markdown", chat_persona_binding: "Привязка персоны", chat_export: "Экспорт сессии", chat_share: "Поделиться сессией", share_expires: "Срок действия ссылки", share_max_tokens: "Максимум токенов (бюджет видимого контекста)", share_create: "Создать ссылку", share_url: "Ссылка для обмена", share_hint: "Любой с этой ссылкой может читать сессию (лимиты: бюджет токенов и срок). Можно отозвать в любой момент.", role_user: "Пользователь", model_s_auto: "Авто", effort_s_auto: "Авто", effort_s_low: "Низк", effort_s_mid: "Сред", effort_s_high: "Высок", chat_mention: "Упомянуть инструменты/навыки (ИИ приоритизирует)", chat_model: "Сменить модель", chat_effort: "Уровень усилий", model_auto: "Авто-выбор модели", effort_auto: "Усилия: авто", effort_low: "Усилия: низкие", effort_mid: "Усилия: средние", effort_high: "Усилия: высокие", mention_ok: "Готово", mention_none: "Нет навыков или MCP-инструментов для упоминания", confirm_title: "Подтверждение", confirm_yes: "OK", chat_pasted: "Вложение вставлено", chat_pin: "Закрепить", chat_unpin: "Открепить", chat_archive: "В архив", chat_unarchive: "Из архива", chat_archived: "В архиве", chat_hero_sub: "О чём поболтаем? Или выбери тему ниже", chat_chip_1: "Напиши мне небольшой скрипт на Python", chat_chip_2: "Собери из чата отчёт за день", chat_chip_3: "Объясни эту ошибку", chat_chip_4: "Напоминай мне вести дневник в 21:00", chat_new: "Новый чат", chat_new_name: "Веб-чат {n}", chat_busy: "Эта сессия ещё отвечает", chat_density: "Детализация", density_brief: "Кратко", density_detail: "Подробно", steps_count: "{n} вызовов инструмента", steps_running: "выполняется…", copy: "Копировать", copied: "Скопировано", msgs_count: "{n} сообщений", session_summary: "Сводка контекста",
      stat_usage: "Расход сегодня", backup_export: "Экспорт конфига", backup_import: "Импорт конфига", audit_filter: "Фильтр инструмента/пользователя…", col_preview: "Последнее сообщение",
      subtitle: "универсальный агент",
      nav_overview: "Обзор", nav_chat: "Чат", nav_models: "Модели", nav_personas: "Личности",
      nav_tools: "Инструменты", nav_extensions: "Расширения", nav_tasks: "Задачи", nav_memory: "Память", nav_sessions: "Сессии",
      nav_audit: "Аудит", nav_settings: "Настройки",
      overview_desc: "Обзор состояния агента", overview_detail: "Подробности",
      stat_models: "Модели", stat_tools: "Инструменты", stat_eco: "Эко-инстр.", stat_sessions: "Сессии",
      stat_tasks: "Задачи", stat_mcp: "MCP", stat_extensions: "Расширения", stat_security: "Безопасность",
      on: "вкл", off: "выкл", takeovers: "Под контролем", trust_on: "Полное доверие",
      chat_desc: "прямой тест агента, инструменты доступны", chat_placeholder: "Скажите что-нибудь…", chat_send: "Отправить",
      chat_thinking: "думаю…", chat_empty: "Диалогов пока нет",
      models_desc: "OpenAI-совместимые endpoint'ы с failover по пулу", models_add: "Добавить / обновить модель",
      models_name: "Имя", models_id: "Модель", models_temp: "Температура", models_maxtok: "Макс. токенов",
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
      sessions_desc: "окна диалогов и привязки личностей", sessions_empty: "Сессий нет",
      col_turns: "Ходы", col_updated: "Обновлено", reset_btn: "Сброс", col_persona: "Личность",
      audit_desc: "операции на ПК и подтверждения", audit_empty: "Записей аудита нет",
      col_tool: "Инструмент", col_detail: "Детали",
      settings_desc: "конфигурация, применяется сразу", settings_saved: "Конфиг сохранен",
      group_model: "Модель", group_trigger: "Триггеры", group_security: "Безопасность", group_chat: "Чат", group_memory: "Память",
      group_tools: "Инструменты", group_eco: "Эко", group_mcp: "MCP", group_task: "Задачи", group_access: "Доступ", group_usage: "Расход",
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
      return resp.json().catch(function () { return {}; });
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
    return chain.then(function (ok) { return ok ? chosen : ""; });
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

  var chatHistory = [];
  var chatSession = (function () {
    try { return localStorage.getItem("qvq_chat_session") || "dashboard:private:web"; } catch (e) { return "dashboard:private:web"; }
  })();
  var chatPersona = (function () {
    try { return localStorage.getItem("qvq_chat_persona") || ""; } catch (e) { return ""; }
  })();
  var chatDensity = (function () {
    try { return localStorage.getItem("qvq_chat_density") || "detail"; } catch (e) { return "detail"; }
  })();
  var chatAtts = [];
  var chatMeta = { sessions: [], personas: [] };
  var chatBusy = false;
  var activeLive = null;
  var chatModel = (function () {
    try { return localStorage.getItem("qvq_chat_model") || ""; } catch (e) { return ""; }
  })();
  var chatEffort = (function () {
    try { return localStorage.getItem("qvq_chat_effort") || ""; } catch (e) { return ""; }
  })();
  var chatMentions = { skills: [], mcp: [] };
  var chatQueue = [];
  var chatSyncTimer = null;
  var modelPresets = [];
  var currentMemoryScope = "";
  var currentCategory = "";

  function applyI18n(root) {
    (root || el("qvq-app")).querySelectorAll("[data-i18n]").forEach(function (node) {
      node.textContent = t(node.getAttribute("data-i18n"));
    });
    (root || el("qvq-app")).querySelectorAll("[data-i18n-ph]").forEach(function (node) {
      node.setAttribute("placeholder", t(node.getAttribute("data-i18n-ph")));
    });
    (root || el("qvq-app")).querySelectorAll("[data-i18n-title]").forEach(function (node) {
      node.setAttribute("title", t(node.getAttribute("data-i18n-title")));
    });
  }

  // ── 模态框 ──
  function openModal(title, bodyHtml) {
    el("qvq-modal-title").textContent = title;
    el("qvq-modal-body").innerHTML = bodyHtml;
    el("qvq-modal").style.display = "flex";
  }
  function closeModal() {
    el("qvq-modal").style.display = "none";
    el("qvq-modal-body").innerHTML = "";
  }

  // ── 自定义组件：下拉选择（替换浏览器原生 select 弹层） ──
  var DD_CHECK = "<svg class='qvq-dd-check' viewBox='0 0 24 24'><path d='M5 12l5 5 9-10'/></svg>";

  function closeAllMenus() {
    document.querySelectorAll(".qvq-dd-menu.open").forEach(function (m) { m.classList.remove("open"); });
    document.querySelectorAll(".qvq-dd-btn.open").forEach(function (b) { b.classList.remove("open"); });
  }

  function enhanceSelects(root) {
    (root || document).querySelectorAll("select.qvq-select").forEach(function (sel) {
      if (sel.getAttribute("data-qvq-dd")) return;
      sel.setAttribute("data-qvq-dd", "1");
      var wrap = document.createElement("span");
      wrap.className = "qvq-dd-wrap";
      try {
        var mw = window.getComputedStyle(sel).maxWidth;
        if (mw && mw !== "none") wrap.style.maxWidth = mw;
      } catch (e) {}
      if (sel.parentNode) sel.parentNode.insertBefore(wrap, sel);
      else return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "qvq-dd-btn";
      var label = document.createElement("span");
      label.className = "qvq-dd-label";
      var chev = document.createElement("i");
      chev.className = "qvq-dd-chev";
      btn.appendChild(label);
      btn.appendChild(chev);
      var menu = document.createElement("span");
      menu.className = "qvq-dd-menu";
      wrap.appendChild(btn);
      wrap.appendChild(menu);
      wrap.appendChild(sel);
      function renderMenu() {
        var cur = sel.value;
        var opts = Array.prototype.slice.call(sel.options || []).map(function (o) {
          return '<span class="qvq-dd-opt' + (o.value === cur ? " sel" : "") + (o.disabled ? " dis" : "") + '" data-v="' + esc(o.value) + '">' +
            "<span>" + esc(o.textContent) + "</span>" + (o.value === cur ? DD_CHECK : "") + "</span>";
        }).join("");
        menu.innerHTML = opts;
        label.textContent = (sel.selectedOptions && sel.selectedOptions[0] && sel.selectedOptions[0].textContent) || cur || " ";
      }
      function close() { menu.classList.remove("open"); btn.classList.remove("open"); }
      btn.onclick = function (e) {
        e.stopPropagation();
        var willOpen = !menu.classList.contains("open");
        closeAllMenus();
        if (willOpen) {
          renderMenu();
          var r = btn.getBoundingClientRect();
          menu.classList.toggle("up", r.bottom + 280 > window.innerHeight && r.top > 300);
          menu.classList.add("open");
          btn.classList.add("open");
        }
      };
      menu.onclick = function (e) {
        var opt = e.target.closest(".qvq-dd-opt");
        if (!opt || opt.classList.contains("dis")) return;
        sel.value = opt.getAttribute("data-v");
        sel.dispatchEvent(new Event("change"));
        renderMenu();
        close();
        e.stopPropagation();
      };
      sel.addEventListener("change", renderMenu);
      if (window.MutationObserver) {
        new MutationObserver(function () { renderMenu(); }).observe(sel, { childList: true, attributes: true, subtree: true });
      }
      renderMenu();
    });
  }

  // ── 自定义组件：确认弹窗（替代浏览器原生 confirm） ──
  function confirmDialog(message) {
    return new Promise(function (resolve) {
      openModal(t("confirm_title"),
        "<div class='qvq-confirm-text'>" + esc(message) + "</div>" +
        "<div class='qvq-actions'><button class='qvq-btn' data-cf-ok>" + esc(t("confirm_yes")) + "</button>" +
        "<button class='qvq-btn ghost' data-cf-no>" + esc(t("cancel")) + "</button></div>");
      var body = el("qvq-modal-body");
      body.querySelector("[data-cf-ok]").onclick = function () { closeModal(); resolve(true); };
      body.querySelector("[data-cf-no]").onclick = function () { closeModal(); resolve(false); };
    });
  }

  (function watchSelects() {
    if (!window.MutationObserver) return;
    var timer = null;
    new MutationObserver(function () {
      if (timer) return;
      timer = setTimeout(function () {
        timer = null;
        try { enhanceSelects(); } catch (e) {}
      }, 80);
    }).observe(document.body, { childList: true, subtree: true });
  })();

  var loaders = {
    overview: loadOverview,
    chat: loadChatMeta,
    models: loadModels,
    personas: loadPersonas,
    skills: loadSkills,
    tools: loadTools,
    extensions: loadExtensions,
    mcp: loadMcp,
    tasks: loadTasks,
    memory: loadMemoryScopes,
    sessions: loadSessions,
    audit: loadAudit,
    settings: loadSettings
  };

  function switchTab(name) {
    el("qvq-nav").querySelectorAll(".qvq-nav-btn").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-tab") === name);
    });
    el("qvq-app").querySelectorAll(".qvq-tab").forEach(function (section) {
      section.classList.toggle("active", section.getAttribute("data-section") === name);
    });
    if (loaders[name]) loaders[name]();
    var navSessions = el("qvq-nav-sessions");
    if (navSessions) navSessions.classList.toggle("show", name === "chat");
    if (name === "chat") {
      var input = el("qvq-chat-input");
      if (input) input.focus();
    }
    closeDrawer();
  }

  // ── 移动端抽屉侧栏 ──
  function closeDrawer() {
    var side = el("qvq-side");
    var mask = el("qvq-mask");
    if (side) side.classList.remove("open");
    if (mask) mask.classList.remove("open");
  }

  (function initDrawer() {
    var side = el("qvq-side");
    var mask = el("qvq-mask");
    var burger = el("qvq-burger");
    if (!side || !mask || !burger) return;
    burger.onclick = function () {
      var open = !side.classList.contains("open");
      side.classList.toggle("open", open);
      mask.classList.toggle("open", open);
    };
    mask.onclick = closeDrawer;
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDrawer();
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth > 860) closeDrawer();
    });
  })();

  function loadOverview() {
    var heroEl = el("qvq-hero-title");
    if (heroEl) heroEl.textContent = heroTitle();
    api("/api/qvq/status").then(function (data) {
      var tools = data.tools || {};
      var total = 0;
      Object.keys(tools).forEach(function (k) { total += tools[k] || 0; });
      var mcpCount = (data.mcp || []).length;
      var extCount = (data.extensions || []).length;
      var cards = [
        { cap: t("stat_models"), num: data.models || 0, cls: "hl-red" },
        { cap: t("stat_tools"), num: total, cls: "hl-teal" },
        { cap: t("stat_eco"), num: tools.eco || 0, cls: "" },
        { cap: t("stat_extensions"), num: extCount, cls: "" },
        { cap: t("stat_sessions"), num: data.sessions || 0, cls: "" },
        { cap: t("stat_tasks"), num: data.tasks || 0, cls: "" },
        { cap: t("stat_mcp"), num: mcpCount, cls: "" },
        { cap: t("stat_security"), num: (data.trust_agent ? t("trust_on") : esc(data.security_level || "-")), cls: data.trust_agent ? "hl-red" : "" }
      ];
      el("qvq-stats").innerHTML = cards.map(function (c) {
        return '<div class="qvq-stat ' + c.cls + '"><div class="num">' + esc(c.num) + '</div><div class="cap">' + esc(c.cap) + "</div></div>";
      }).join("");
      var usage = data.usage_today || {};
      var tokens = usage.tokens || 0;
      var limit = usage.limit || 0;
      var heroSub = [];
      if (data.version) heroSub.push("v" + data.version);
      if (data.eco) heroSub.push(t("stat_eco") + " " + (data.eco.modules || 0) + " / " + (data.eco.tools || 0));
      heroSub.push(t("takeovers") + " " + (data.takeovers || 0));
      var sub = el("qvq-hero-sub");
      if (sub) sub.textContent = heroSub.join(" · ");
      var num = el("qvq-hero-tokens");
      if (num) num.textContent = tokens;
      var bar = el("qvq-hero-bar");
      if (bar) bar.style.width = limit ? Math.min(100, (tokens / limit) * 100) + "%" : "0%";
      var lim = el("qvq-hero-limit");
      if (lim) {
        lim.textContent = limit
          ? t("usage_limit") + " " + limit + " · " + Math.min(100, Math.round((tokens / limit) * 100)) + "%"
          : t("hero_no_limit");
      }
    });
    api("/api/qvq/usage").then(function (data) {
      renderUsageChart(data || {}, "qvq-home-chart");
    });
    api("/api/qvq/sessions").then(function (data) {
      var homeSessions = (data && data.sessions) || [];
      renderHomeList("qvq-home-sessions", homeSessions, function (s) {
        return { name: sessionDisplayName(s), badge: s.turns, desc: esc(chatSourceLabel(s.chat_key)) };
      });
      var listBox = el("qvq-home-sessions");
      if (listBox) {
        listBox.querySelectorAll(".qvq-tool-row").forEach(function (row, idx) {
          var item = homeSessions[idx];
          if (!item) return;
          row.style.cursor = "pointer";
          row.onclick = function () {
            switchTab("chat");
            if (item.chat_key !== chatSession) switchChatSession(item.chat_key);
          };
        });
      }
    });
    api("/api/qvq/tasks").then(function (data) {
      renderHomeList("qvq-home-tasks", (data && data.tasks) || [], function (task) {
        return {
          name: task.name || task.id,
          desc: task.next_run ? esc(fmtSmart(task.next_run)) : esc(task.schedule_raw || "-")
        };
      });
    });
  }

  function renderHomeList(boxId, items, map) {
    var box = el(boxId);
    if (!box) return;
    if (!items.length) {
      box.innerHTML = '<div class="qvq-empty">-</div>';
      return;
    }
    box.innerHTML = items.slice(0, 5).map(function (item) {
      var row = map(item);
      var badge = row.badge != null && row.badge !== ""
        ? "<span class='qvq-row-badge' title='" + esc(t("col_turns")) + "'>" + esc(row.badge) + "</span>"
        : "";
      return "<div class='qvq-tool-row'>" + badge + "<span class='qvq-tool-name'><span class='qvq-tool-nm'>" + esc(row.name) + "</span></span>" +
        "<span class='qvq-tool-desc'>" + row.desc + "</span></div>";
    }).join("");
  }

  function contentText(content) {
    if (typeof content === "string") return content;
    if (Array.isArray(content)) {
      return content
        .filter(function (p) { return p && p.type === "text"; })
        .map(function (p) { return p.text || ""; })
        .join("\n");
    }
    return String(content || "");
  }

  function sessionDisplayName(s) {
    return s.name || s.target_id || s.chat_key;
  }

  var chatShowArchived = false;

  var PIN_SVG = "<svg viewBox='0 0 24 24'><path d='M12 17v5M9 3h6l-1 7 3 2v2H7v-2l3-2z'/></svg>";
  var ARC_SVG = "<svg viewBox='0 0 24 24'><path d='M3 6h18v3H3zM5 9v11h14V9M9 13h6'/></svg>";

  function chatSessionTitle(key) {
    if (key === "dashboard:private:web") return t("chat_default_session");
    var m = /^dashboard:private:web(\d+)$/.exec(key || "");
    if (m) return t("chat_new_name").replace("{n}", m[1]);
    var found = null;
    chatMeta.sessions.forEach(function (s) { if (s.chat_key === key) found = s; });
    return found ? sessionDisplayName(found) : key;
  }

  function sessionRowsHtml(items) {
    return items.slice(0, 40).map(function (s) {
      var active = s.chat_key === chatSession;
      var pinned = !!s.pinned;
      var acts = '<span class="qvq-chat-sacts">' +
        '<button type="button" data-act="pin" data-key="' + esc(s.chat_key) + '" data-on="' + (pinned ? "1" : "0") + '" title="' + esc(t(pinned ? "chat_unpin" : "chat_pin")) + '">' + PIN_SVG + "</button>" +
        '<button type="button" data-act="archive" data-key="' + esc(s.chat_key) + '" data-on="' + (s.archived ? "1" : "0") + '" title="' + esc(t(s.archived ? "chat_unarchive" : "chat_archive")) + '">' + ARC_SVG + "</button>" +
        "</span>";
      var liveCls = s.live ? " liverun" : "";
      return '<div class="qvq-chat-srow' + (active ? " active" : "") + (pinned ? " pinned" : "") + liveCls + '" data-key="' + esc(s.chat_key) + '">' +
        '<span class="qvq-chat-sname">' + esc(chatSessionTitle(s.chat_key)) + "</span>" +
        '<span class="qvq-chat-stime">' + esc(fmtSmart(s.updated)) + "</span>" + acts + "</div>";
    }).join("");
  }

  function bindSessionRows(box, closeAfter) {
    box.querySelectorAll(".qvq-chat-srow").forEach(function (row) {
      row.onclick = function () {
        switchChatSession(row.getAttribute("data-key"));
        if (closeAfter) closeDrawer();
      };
    });
    box.querySelectorAll(".qvq-chat-sacts button").forEach(function (btn) {
      btn.onclick = function (e) {
        e.stopPropagation();
        var key = btn.getAttribute("data-key");
        var on = btn.getAttribute("data-on") === "1";
        var act = btn.getAttribute("data-act");
        var patch = { chat_key: key };
        patch[act === "pin" ? "pinned" : "archived"] = !on;
        api("/api/qvq/session/flags", "POST", patch).then(function () {
          // 归档当前会话：切到下一个可见会话（否则豁免逻辑让它看起来没归档）
          if (act === "archive" && !on && key === chatSession) {
            var next = chatMeta.sessions.filter(function (s3) { return !s3.archived && s3.chat_key !== key; })[0];
            chatSession = next ? next.chat_key : "dashboard:private:web";
            try { localStorage.setItem("qvq_chat_session", chatSession); } catch (e2) {}
            chatHistory = [];
            renderChat();
          }
          loadChatMeta();
        });
      };
    });
  }

  function renderChatSessions() {
    var navBox = el("qvq-nav-sessions");
    var known = {};
    chatMeta.sessions.forEach(function (s) { known[s.chat_key] = s; });
    // 当前会话可能尚未出现在服务端列表（刚新建），临时置顶
    var items = chatMeta.sessions.slice();
    if (!known[chatSession]) {
      items.unshift({ chat_key: chatSession, updated: Date.now() / 1000 });
    }
    var archivedCount = chatMeta.sessions.filter(function (s) { return s.archived; }).length;
    if (navBox) {
      var shown = chatShowArchived
        ? items.filter(function (s) { return s.chat_key === chatSession || s.archived; })
        : items.filter(function (s) { return !s.archived || s.chat_key === chatSession; });
      var newBtn = '<div class="qvq-chat-srow qvq-nav-new" data-new="1"><span class="qvq-chat-sname">+ ' + esc(t("chat_new")) + "</span></div>";
      var foot = '<div class="qvq-chat-sfoot' + (chatShowArchived ? " on" : "") + '" data-archived-toggle="1">' +
        esc(t("chat_archived")) + (archivedCount ? " · " + archivedCount : "") + "</div>";
      // 滚动区（行）与已归档按钮（独立占位）分离
      var navHtml = '<div class="qvq-nav-srows" data-srows="1">' + newBtn + (sessionRowsHtml(shown) || "") + "</div>" + foot;
      if (navBox.getAttribute("data-html") !== navHtml) {
        navBox.setAttribute("data-html", navHtml);
        navBox.innerHTML = navHtml;
        bindSessionRows(navBox, true);
        var nb = navBox.querySelector("[data-new]");
        if (nb) nb.onclick = function () { newChat(); closeDrawer(); };
        var footEl = navBox.querySelector("[data-archived-toggle]");
        if (footEl) footEl.onclick = function () {
          chatShowArchived = !chatShowArchived;
          renderChatSessions();
        };
      }
    }
    var title = el("qvq-chat-title");
    if (title) title.textContent = chatSessionTitle(chatSession);
  }

  function syncPersonaSelect() {
    var psel = el("qvq-chat-persona");
    if (!psel) return;
    var popts = ['<option value="">' + esc(t("chat_follow")) + "</option>"];
    chatMeta.personas.forEach(function (p) {
      popts.push('<option value="' + esc(p.id) + '">' + esc(p.name || p.id) + "</option>");
    });
    psel.innerHTML = popts.join("");
    psel.value = chatPersona;
    if (psel.value !== chatPersona) { chatPersona = ""; }
  }

  function loadChatMeta() {
    Promise.all([
      api("/api/qvq/sessions"),
      api("/api/qvq/personas"),
      api("/api/qvq/models")
    ]).then(function (results) {
      chatMeta.sessions = (results[0] && results[0].sessions) || [];
      chatMeta.personas = (results[1] && results[1].personas) || [];
      chatMeta.uiDefaults = (results[0] && results[0].ui_defaults) || {};
      // 恢复的会话已不存在时回到默认
      var exists = chatSession === "dashboard:private:web" ||
        /^dashboard:private:web\d+$/.test(chatSession) ||
        chatMeta.sessions.some(function (s) { return s.chat_key === chatSession; });
      if (!exists) chatSession = "dashboard:private:web";
      // 生效设置：会话级 > 全局默认 > localStorage 遗留值
      applyEffectiveSettings();
      renderChatSessions();
      syncPersonaSelect();
      updateMmLabel();
      loadChatHistory().then(function () {
        checkLive();
      });
    });
  }

  function effortShort() {
    if (chatEffort === "0.3") return t("effort_s_low");
    if (chatEffort === "0.7") return t("effort_s_mid");
    if (chatEffort === "1.0") return t("effort_s_high");
    return t("effort_s_auto");
  }

  function modelShort(id) {
    if (!id) return t("model_s_auto");
    var i = id.indexOf(":");
    return i >= 0 ? id.slice(i + 1) : id;
  }

  function updateMmLabel() {
    var label = el("qvq-chat-mm-label");
    if (!label) return;
    label.textContent = modelShort(chatModel) + " · " + effortShort();
    var btn = el("qvq-chat-mm");
    if (btn) btn.title = (chatModel || t("model_auto")) + " · " + (chatEffort ? chatEffort : t("effort_s_auto"));
  }

  function toggleMmMenu() {
    var old = el("qvq-mm-menu");
    if (old) { old.remove(); return; }
    var anchor = el("qvq-chat-mm");
    if (!anchor) return;
    api("/api/qvq/models").then(function (data) {
      var models = (data && data.models) || [];
      var existing = el("qvq-mm-menu");
      if (existing) { existing.remove(); return; }
      var menu = document.createElement("div");
      menu.className = "qvq-mm-menu";
      menu.id = "qvq-mm-menu";
      var opts = [{ id: "", label: t("model_auto") }].concat(models.map(function (m) { return { id: m.id, label: m.id }; }));
      var html = '<div class="qvq-mention-sec">' + esc(t("chat_model")) + "</div>";
      html += opts.map(function (o) {
        return '<div class="qvq-mention-opt' + (chatModel === o.id ? " sel" : "") + '" data-mm-model="' + esc(o.id) + '"><span>' + esc(o.label) + "</span>" + (chatModel === o.id ? DD_CHECK : "") + "</div>";
      }).join("");
      html += '<div class="qvq-mention-sec">' + esc(t("chat_effort")) + "</div>";
      [["", t("effort_s_auto")], ["0.3", t("effort_s_low")], ["0.7", t("effort_s_mid")], ["1.0", t("effort_s_high")]].forEach(function (pair) {
        html += '<div class="qvq-mention-opt' + (chatEffort === pair[0] ? " sel" : "") + '" data-mm-effort="' + pair[0] + '"><span>' + esc(pair[1]) + "</span>" + (chatEffort === pair[0] ? DD_CHECK : "") + "</div>";
      });
      menu.innerHTML = html;
      document.body.appendChild(menu);
      var rect = anchor.getBoundingClientRect();
      menu.style.right = Math.max(8, window.innerWidth - rect.right) + "px";
      menu.style.bottom = (window.innerHeight - rect.top + 8) + "px";
      menu.querySelectorAll("[data-mm-model]").forEach(function (opt) {
        opt.onclick = function () {
          chatModel = opt.getAttribute("data-mm-model");
          try { localStorage.setItem("qvq_chat_model", chatModel); } catch (e) {}
          saveSessionSettings({ model: chatModel });
          updateMmLabel();
          menu.remove();
        };
      });
      menu.querySelectorAll("[data-mm-effort]").forEach(function (opt) {
        opt.onclick = function () {
          chatEffort = opt.getAttribute("data-mm-effort");
          try { localStorage.setItem("qvq_chat_effort", chatEffort); } catch (e) {}
          saveSessionSettings({ effort: chatEffort });
          updateMmLabel();
          menu.remove();
        };
      });
      setTimeout(function () {
        document.addEventListener("click", function onDoc(e) {
          if (!menu.contains(e.target) && !anchor.contains(e.target)) {
            menu.remove();
            document.removeEventListener("click", onDoc);
          }
        });
      }, 0);
    });
  }

  function refreshMentionBadge() {
    var badge = el("qvq-mention-badge");
    if (!badge) return;
    var n = chatMentions.skills.length + chatMentions.mcp.length;
    badge.style.display = n ? "flex" : "none";
    badge.textContent = String(n);
  }

  // ── 导出 / 分享会话 ──
  function renderQueue() {
    var box = el("qvq-chat-queue");
    if (!box) return;
    if (!chatQueue.length) {
      box.style.display = "none";
      box.innerHTML = "";
      return;
    }
    box.style.display = "flex";
    box.innerHTML = chatQueue.map(function (item, i) {
      var attsHtml = (item.atts || []).map(function (a) {
        return a.isImage
          ? '<img class="qvq-q-att" src="' + a.data + '" alt=""/>'
          : '<span class="qvq-q-att"><i class="qvq-file-ico">' + FILE_ICON_SVG + "</i>" + esc(a.name) + "</span>";
      }).join("");
      var editBox = item.editing
        ? '<div class="qvq-q-edit"><textarea class="qvq-textarea" rows="2">' + esc(item.text) + "</textarea>" +
          '<div class="qvq-actions"><button class="qvq-btn small" data-q-save="' + i + '">' + esc(t("save")) + "</button>" +
          '<button class="qvq-btn small ghost" data-q-cancel="' + i + '">' + esc(t("cancel")) + "</button></div></div>"
        : '<div class="qvq-q-text">' + esc(item.text) + "</div>" + attsHtml;
      return '<div class="qvq-q-card" draggable="true" data-qi="' + i + '">' +
        '<div class="qvq-q-main">' + editBox + "</div>" +
        '<div class="qvq-q-ops">' +
        '<button type="button" class="qvq-btn small" data-q-now="' + i + '" title="' + esc(t("queue_send_now")) + '">' + esc(t("queue_send_now")) + "</button>" +
        '<button type="button" class="qvq-icon-btn" data-q-edit="' + i + '" title="' + esc(t("edit")) + '"><svg viewBox="0 0 24 24"><path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg></button>' +
        '<button type="button" class="qvq-icon-btn" data-q-del="' + i + '" title="' + esc(t("del")) + '"><svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2m-9 0v14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6"/></svg></button>' +
        '<span class="qvq-q-drag" title="⇅">⇅</span>' +
        "</div></div>";
    }).join("");
    box.querySelectorAll("[data-q-now]").forEach(function (btn) {
      btn.onclick = function () {
        if (chatBusy) return;
        var i = parseInt(btn.getAttribute("data-q-now"), 10);
        var item = chatQueue.splice(i, 1)[0];
        renderQueue();
        dispatchMessage(item.text, item.atts);
      };
    });
    box.querySelectorAll("[data-q-edit]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-q-edit"), 10);
        chatQueue[i].editing = true;
        renderQueue();
      };
    });
    box.querySelectorAll("[data-q-del]").forEach(function (btn) {
      btn.onclick = function () {
        chatQueue.splice(parseInt(btn.getAttribute("data-q-del"), 10), 1);
        renderQueue();
      };
    });
    box.querySelectorAll("[data-q-save]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-q-save"), 10);
        var card = btn.closest(".qvq-q-card");
        chatQueue[i].text = card.querySelector("textarea").value;
        chatQueue[i].editing = false;
        renderQueue();
      };
    });
    box.querySelectorAll("[data-q-cancel]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-q-cancel"), 10);
        chatQueue[i].editing = false;
        renderQueue();
      };
    });
    // 拖拽排序
    var dragIndex = null;
    box.querySelectorAll(".qvq-q-card").forEach(function (card) {
      card.addEventListener("dragstart", function (e) {
        dragIndex = parseInt(card.getAttribute("data-qi"), 10);
        if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
      });
      card.addEventListener("dragover", function (e) { e.preventDefault(); });
      card.addEventListener("drop", function (e) {
        e.preventDefault();
        var to = parseInt(card.getAttribute("data-qi"), 10);
        if (dragIndex === null || dragIndex === to) return;
        var moved = chatQueue.splice(dragIndex, 1)[0];
        chatQueue.splice(to, 0, moved);
        dragIndex = null;
        renderQueue();
      });
    });
  }

  function exportSession() {
    api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(chatSession)).then(function (data) {
      var msgs = (data && data.messages) || [];
      var lines = ["# " + chatSessionTitle(chatSession), ""];
      msgs.forEach(function (m) {
        if (!m || typeof m !== "object") return;
        var role = m.role === "user" ? t("role_user") : m.role === "assistant" ? "AI" : (m.role || "");
        lines.push("## " + role, "", contentText(m.content), "");
      });
      var blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = (chatSessionTitle(chatSession) || "session").replace(/[\\/:*?"<>|]+/g, "_") + ".md";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 200);
    });
  }

  function applyEffectiveSettings() {
    var curSess = null;
    chatMeta.sessions.forEach(function (s3) { if (s3.chat_key === chatSession) curSess = s3; });
    var ui = (curSess && curSess.ui) || {};
    var def = chatMeta.uiDefaults || {};
    if (ui.density) chatDensity = ui.density;
    else if (def.density) chatDensity = def.density;
    if (ui.model != null) chatModel = ui.model;
    else if (def.model != null) chatModel = def.model;
    if (ui.effort != null) chatEffort = ui.effort;
    else if (def.effort != null) chatEffort = def.effort;
    try {
      localStorage.setItem("qvq_chat_density", chatDensity);
      localStorage.setItem("qvq_chat_model", chatModel);
      localStorage.setItem("qvq_chat_effort", chatEffort);
    } catch (e) {}
    updateMmLabel();
  }

  function chatSourceLabel(key) {
    var parts = String(key || "").split(":");
    if (parts.length >= 3) return parts[0] + " · " + parts[2];
    return key || "-";
  }

  function saveSessionSettings(patch) {
    api("/api/qvq/session/settings", "POST", { chat_key: chatSession, settings: patch }).catch(function () {});
  }

  function openSessionSettings() {
    api("/api/qvq/models").then(function (data) {
      var models = (data && data.models) || [];
      var mOpts = ['<option value="">' + esc(t("model_auto")) + "</option>"].concat(models.map(function (m2) {
        return '<option value="' + esc(m2.id) + '">' + esc(m2.id) + "</option>";
      })).join("");
      var pOpts = ['<option value="">' + esc(t("chat_follow")) + "</option>"].concat(chatMeta.personas.map(function (p2) {
        return '<option value="' + esc(p2.id) + '">' + esc(p2.name || p2.id) + "</option>";
      })).join("");
      var html =
        "<label class='qvq-label'>" + esc(t("chat_density")) + "</label>" +
        "<select class='qvq-select' id='qs-density'><option value='detail'>" + esc(t("density_detail")) + "</option><option value='brief'>" + esc(t("density_brief")) + "</option></select>" +
        "<label class='qvq-label'>" + esc(t("chat_model")) + "</label>" +
        "<select class='qvq-select' id='qs-model'>" + mOpts + "</select>" +
        "<label class='qvq-label'>" + esc(t("chat_effort")) + "</label>" +
        "<select class='qvq-select' id='qs-effort'><option value=''>" + esc(t("effort_s_auto")) + "</option><option value='0.3'>" + esc(t("effort_s_low")) + "</option><option value='0.7'>" + esc(t("effort_s_mid")) + "</option><option value='1.0'>" + esc(t("effort_s_high")) + "</option></select>" +
        "<label class='qvq-label'>" + esc(t("chat_persona_binding")) + "</label>" +
        "<select class='qvq-select' id='qs-persona'>" + pOpts + "</select>" +
        "<div class='qvq-actions'><button class='qvq-btn' data-qs-save>" + esc(t("settings_save_session")) + "</button>" +
        "<button class='qvq-btn ghost' data-qs-all>" + esc(t("settings_apply_all")) + "</button></div>" +
        "<div class='qvq-settings-danger'><button type='button' class='qvq-quiet-danger' data-qs-clear>" + esc(t("chat_clear")) + "</button></div>";
      openModal(t("chat_settings"), html);
      var body = el("qvq-modal-body");
      body.querySelector("#qs-density").value = chatDensity;
      body.querySelector("#qs-model").value = chatModel;
      if (body.querySelector("#qs-model").value !== chatModel) body.querySelector("#qs-model").value = "";
      body.querySelector("#qs-effort").value = chatEffort;
      body.querySelector("#qs-persona").value = chatPersona;
      function collect() {
        return {
          density: body.querySelector("#qs-density").value,
          model: body.querySelector("#qs-model").value,
          effort: body.querySelector("#qs-effort").value,
        };
      }
      function applyLocal(vals) {
        chatDensity = vals.density;
        chatModel = vals.model;
        chatEffort = vals.effort;
        try {
          localStorage.setItem("qvq_chat_density", chatDensity);
          localStorage.setItem("qvq_chat_model", chatModel);
          localStorage.setItem("qvq_chat_effort", chatEffort);
        } catch (e) {}
        updateMmLabel();
      }
      body.querySelector("[data-qs-save]").onclick = function () {
        var vals = collect();
        applyLocal(vals);
        saveSessionSettings(vals);
        var persona = body.querySelector("#qs-persona").value;
        chatPersona = persona;
        api("/api/qvq/personas/bind", "POST", { chat_key: chatSession, persona: persona || null }).then(function () {
          toast(t("saved"));
          closeModal();
          loadChatMeta();
        });
      };
      body.querySelector("[data-qs-all]").onclick = function () {
        var vals = collect();
        applyLocal(vals);
        saveSessionSettings(vals);
        api("/api/qvq/settings/defaults", "POST", { settings: vals }).then(function () {
          toast(t("saved"));
          closeModal();
        });
      };
      body.querySelector("[data-qs-clear]").onclick = function () {
        confirmDialog(t("chat_clear_confirm")).then(function (ok) {
          if (!ok) return;
          api("/api/qvq/sessions/reset", "POST", { chat_key: chatSession }).then(function () {
            toast(t("saved"));
            closeModal();
            loadChatHistory();
            loadChatMeta();
          });
        });
      };
    });
  }

  function openShareModal() {
    var body = el("qvq-modal-body");
    var html =
      "<label class='qvq-label'>" + esc(t("share_expires")) + "</label>" +
      "<select class='qvq-select' id='qvq-share-exp'>" +
      "<option value='1'>1 h</option><option value='24' selected>24 h</option><option value='72'>72 h</option><option value='168'>7 d</option></select>" +
      "<label class='qvq-label'>" + esc(t("share_max_tokens")) + "</label>" +
      "<input class='qvq-input' id='qvq-share-tokens' type='number' min='200' max='200000' value='4000'/>" +
      "<div class='qvq-actions'><button class='qvq-btn' data-share-create>" + esc(t("share_create")) + "</button>" +
      "<button class='qvq-btn ghost' data-share-export>" + esc(t("share_export")) + "</button></div>" +
      "<div id='qvq-share-result' style='display:none'>" +
      "<label class='qvq-label'>" + esc(t("share_url")) + "</label>" +
      "<div class='qvq-share-url'><input class='qvq-input' id='qvq-share-url' readonly/><button class='qvq-btn small' id='qvq-share-copy'>" + esc(t("copy")) + "</button></div>" +
      "<div class='qvq-share-hint'>" + esc(t("share_hint")) + "</div></div>";
    openModal(t("chat_share"), html);
    body.querySelector("[data-share-export]").onclick = function () {
      closeModal();
      exportSession();
    };
    body.querySelector("[data-share-create]").onclick = function () {
      api("/api/qvq/session/share", "POST", {
        chat_key: chatSession,
        expires_hours: parseInt(fv(body, "qvq-share-exp"), 10) || 24,
        max_tokens: parseInt(fv(body, "qvq-share-tokens"), 10) || 4000,
      }).then(function (data) {
        if (!data || !data.url) {
          toast((data && data.error) || t("chat_err"), true);
          return;
        }
        var full = location.origin + data.url;
        body.querySelector("#qvq-share-result").style.display = "block";
        body.querySelector("#qvq-share-url").value = full;
        body.querySelector("#qvq-share-copy").onclick = function () {
          copyText(full);
          toast(t("copied"));
        };
      });
    };
  }

  function toggleMentionMenu() {
    var old = el("qvq-mention-menu");
    if (old) { old.remove(); return; }
    var anchor = el("qvq-chat-mention");
    if (!anchor) return;
    Promise.all([api("/api/qvq/skills"), api("/api/qvq/mcp")]).then(function (results) {
      var skills = (results[0] && results[0].skills) || [];
      var mcpTools = [];
      var clients = (results[1] && results[1].clients) || [];
      (Array.isArray(clients) ? clients : []).forEach(function (c) {
        (c.tool_names || []).forEach(function (name) {
          mcpTools.push({ name: name, server: c.name || "" });
        });
      });
      if (!skills.length && !mcpTools.length) {
        toast(t("mention_none"), true);
        return;
      }
      var menu = document.createElement("div");
      menu.className = "qvq-mention-menu";
      menu.id = "qvq-mention-menu";
      var html = "";
      if (skills.length) {
        html += '<div class="qvq-mention-sec">' + esc(t("nav_skills")) + "</div>";
        html += skills.map(function (sk) {
          var on = chatMentions.skills.indexOf(sk.name) >= 0;
          return '<label class="qvq-mention-opt"><input type="checkbox" data-kind="skill" data-name="' + esc(sk.name) + '"' + (on ? " checked" : "") + "/><span>" + esc(sk.name) + "</span></label>";
        }).join("");
      }
      if (mcpTools.length) {
        html += '<div class="qvq-mention-sec">MCP</div>';
        html += mcpTools.map(function (t2) {
          var on = chatMentions.mcp.indexOf(t2.name) >= 0;
          return '<label class="qvq-mention-opt"><input type="checkbox" data-kind="mcp" data-name="' + esc(t2.name) + '"' + (on ? " checked" : "") + "/><span>" + esc(t2.name) + ' <em>' + esc(t2.server) + "</em></span></label>";
        }).join("");
      }
      html += '<button type="button" class="qvq-btn small" data-mention-ok>' + esc(t("mention_ok")) + "</button>";
      menu.innerHTML = html;
      document.body.appendChild(menu);
      var rect = anchor.getBoundingClientRect();
      menu.style.left = Math.max(8, rect.left) + "px";
      menu.style.bottom = (window.innerHeight - rect.top + 8) + "px";
      menu.querySelectorAll("input[type=checkbox]").forEach(function (box) {
        box.onchange = function () {
          var kind = box.getAttribute("data-kind");
          var name = box.getAttribute("data-name");
          var list = kind === "skill" ? chatMentions.skills : chatMentions.mcp;
          var idx = list.indexOf(name);
          if (box.checked && idx < 0) list.push(name);
          if (!box.checked && idx >= 0) list.splice(idx, 1);
          refreshMentionBadge();
        };
      });
      menu.querySelector("[data-mention-ok]").onclick = function () { menu.remove(); };
      setTimeout(function () {
        document.addEventListener("click", function onDoc(e) {
          if (!menu.contains(e.target) && e.target !== anchor) {
            menu.remove();
            document.removeEventListener("click", onDoc);
          }
        });
      }, 0);
    });
  }

  function switchChatSession(key) {
    if (!key || key === chatSession) return;
    chatSession = key;
    // 待发送附件属于上一个会话的草稿，切换即清空
    if (chatAtts.length) {
      chatAtts = [];
      renderAttach();
    }
    try { localStorage.setItem("qvq_chat_session", chatSession); } catch (e) {}
    var bound = null;
    chatMeta.sessions.forEach(function (s) { if (s.chat_key === key) bound = s; });
    chatPersona = (bound && bound.persona) || "";
    try {
      if (chatPersona) localStorage.setItem("qvq_chat_persona", chatPersona);
      else localStorage.removeItem("qvq_chat_persona");
    } catch (e) {}
    syncPersonaSelect();
    applyEffectiveSettings();
    renderChatSessions();
    loadChatHistory().then(function () {
      checkLive();
    });
    var input = el("qvq-chat-input");
    if (input) input.focus();
  }

  function newChat() {
    var used = {};
    chatMeta.sessions.forEach(function (s) { used[s.chat_key] = true; });
    var n = 2;
    while (used["dashboard:private:web" + n]) n++;
    switchChatSession("dashboard:private:web" + n);
    api("/api/qvq/sessions").then(function (data) {
      chatMeta.sessions = (data && data.sessions) || [];
      renderChatSessions();
    });
  }

  // 平台侧新消息实时同步：对话页激活且空闲时轻量轮询
  function startChatSync() {
    if (chatSyncTimer) return;
    chatSyncTimer = setInterval(function () {
      if (chatBusy || chatQueue.length) return;
      var section = document.querySelector('.qvq-tab[data-section="chat"]');
      if (!section || !section.classList.contains("active")) return;
      var box = el("qvq-chat-box");
      if (!box) return;
      api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(chatSession)).then(function (data) {
        var msgs = (data && data.messages) || [];
        var fresh = [];
        msgs.forEach(function (m, idx) {
          if (!m || typeof m !== "object") return;
          if (m.role === "user" || m.role === "assistant") {
            var atts = (m.atts || []).map(function (a) {
              return { isImage: !!a.isImage, name: a.name || "image", data: a.data || "", mime: a.mime || "image/png" };
            });
            fresh.push({ role: m.role, text: contentText(m.content), idx: idx, steps: traceToSteps(m.trace), atts: atts });
          }
        });
        var sig = fresh.map(function (m) { return m.role + "\u0001" + m.text; }).join("\u0002");
        var curSig = chatHistory.map(function (m) { return m.role + "\u0001" + m.text; }).join("\u0002");
        if (sig !== curSig) {
          chatHistory = fresh;
          renderChat();
        }
      });
    }, 4000);
  }

  function checkLive() {
    if (chatBusy) return;
    api("/api/qvq/chat/live?session=" + encodeURIComponent(chatSession)).then(function (live) {
      if (!live || live.status === "idle") return;
      if (live.status === "running") {
        attachLive(live);
      } else if (live.reply != null || live.error) {
        // 离开期间已结束：服务端已写入最终回复，直接刷新历史
        loadChatHistory();
      }
    });
  }

  // ── mini-markdown 安全渲染：先转义再转换有限语法 ──
  function mdInline(s) {
    return s
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>")
      .replace(/(^|[\s(（>「])\*([^*\n]+)\*(?=[\s).,，。;；!？?」]|$)/g, "$1<i>$2</i>")
      .replace(/\[([^\]\n]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }

  function mdRender(src) {
    var text = String(src == null ? "" : src).replace(/\r\n/g, "\n").trim();
    if (!text) return "";
    var parts = text.split("```");
    var out = "";
    for (var pi = 0; pi < parts.length; pi++) {
      if (pi % 2 === 1) {
        var code = parts[pi];
        var nl = code.indexOf("\n");
        var lang = nl >= 0 ? code.slice(0, nl).trim() : "";
        var body = nl >= 0 ? code.slice(nl + 1) : code;
        out += '<div class="qvq-md-pre"><div class="qvq-md-lang"><span>' + esc(lang || "code") +
          '</span><button class="qvq-md-copy" type="button">' + esc(t("copy")) + "</button></div><pre>" +
          esc(body.replace(/\n$/, "")) + "</pre></div>";
        continue;
      }
      var lines = parts[pi].split("\n");
      var para = [], list = null, quote = [];
      var flush = function () {
        if (para.length) { out += "<p>" + para.map(mdInline).join("<br>") + "</p>"; para = []; }
      };
      var flushList = function () { if (list) { out += "</" + list + ">"; list = null; } };
      var flushQuote = function () {
        if (quote.length) { out += "<blockquote>" + quote.map(mdInline).join("<br>") + "</blockquote>"; quote = []; }
      };
      for (var li = 0; li < lines.length; li++) {
        var tline = lines[li].trim();
        if (!tline) { flush(); flushList(); flushQuote(); continue; }
        var hm = tline.match(/^(#{1,6})\s+(.*)$/);
        if (hm) {
          flush(); flushList(); flushQuote();
          out += "<h" + hm[1].length + ">" + mdInline(esc(hm[2])) + "</h" + hm[1].length + ">";
          continue;
        }
        if (/^(-{3,}|\*{3,})$/.test(tline)) { flush(); flushList(); flushQuote(); out += "<hr/>"; continue; }
        if (tline.indexOf("|") === 0 && li + 1 < lines.length && /^\|[\s:|-]+$/.test(lines[li + 1].trim())) {
          flush(); flushList(); flushQuote();
          var splitRow = function (line) {
            return line.replace(/^\||\|$/g, "").split("|").map(function (c) { return c.trim(); });
          };
          var headCells = splitRow(tline);
          li += 2;
          var bodyRows = [];
          while (li < lines.length && /^\|/.test(lines[li].trim())) { bodyRows.push(splitRow(lines[li].trim())); li++; }
          li--;
          out += "<table><thead><tr>" + headCells.map(function (c) { return "<th>" + mdInline(esc(c)) + "</th>"; }).join("") +
            "</tr></thead><tbody>" + bodyRows.map(function (r) {
              return "<tr>" + r.map(function (c) { return "<td>" + mdInline(esc(c)) + "</td>"; }).join("") + "</tr>";
            }).join("") + "</tbody></table>";
          continue;
        }
        if (tline.indexOf(">") === 0) { flush(); flushList(); quote.push(esc(tline.replace(/^>\s?/, ""))); continue; }
        var ulm = tline.match(/^[-*+]\s+(.*)$/);
        var olm = tline.match(/^\d+[.)]\s+(.*)$/);
        if (ulm || olm) {
          flush(); flushQuote();
          var want = ulm ? "ul" : "ol";
          if (list !== want) { flushList(); out += "<" + want + ">"; list = want; }
          out += "<li>" + mdInline(esc((ulm || olm)[1])) + "</li>";
          continue;
        }
        flushList(); flushQuote();
        para.push(esc(tline));
      }
      flush(); flushList(); flushQuote();
    }
    return out;
  }

  function copyText(s) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(s);
    var ta = document.createElement("textarea");
    ta.value = s;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    ta.remove();
  }

  function bindMdCopy(root) {
    root.querySelectorAll(".qvq-md-copy").forEach(function (btn) {
      btn.onclick = function () {
        var pre = btn.closest(".qvq-md-pre");
        copyText(pre && pre.querySelector("pre") ? pre.querySelector("pre").textContent : "");
        btn.textContent = t("copied");
        setTimeout(function () { btn.textContent = t("copy"); }, 1200);
      };
    });
  }

  // ── 工具步骤时间线 ──
  var STEP_ICON_SVG = "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='4' width='18' height='16' rx='2'/><path d='M7 9l3 3-3 3M13 15h4'/></svg>";

  function stepsHtml(steps, running) {
    var n = steps.length;
    if (!n) return "";
    if (chatDensity === "brief" && !running) return "";
    var rows = steps.map(function (s) {
      var name = s.start ? s.start.name : (s.end ? s.end.name : "?");
      var args = s.start ? String(s.start.arguments || "") : "";
      var runningStep = s.start && !s.end;
      var ms = s.end && s.end.ms != null ? s.end.ms : null;
      var output = s.end ? String(s.end.output || "") : "";
      var compact = args.replace(/\s+/g, " ");
      var short = compact && compact !== "{}" ? "(" + (compact.length > 52 ? compact.slice(0, 52) + "…" : compact) + ")" : "";
      var cost = runningStep ? t("steps_running") : (ms != null ? (ms >= 1000 ? (ms / 1000).toFixed(1) + "s" : ms + "ms") : "");
      return '<div class="qvq-step' + (runningStep ? " running" : "") + '">' +
        '<div class="qvq-step-row" data-step-toggle="1">' +
        '<span class="qvq-step-ico">' + STEP_ICON_SVG + "</span>" +
        '<span class="qvq-step-name">' + esc(name) + "</span>" +
        (short ? '<span class="qvq-step-args">' + esc(short) + "</span>" : "") +
        '<span class="qvq-step-ms">' + esc(cost) + "</span></div>" +
        (output ? '<pre class="qvq-step-detail">' + esc(output) + "</pre>" : "") +
        "</div>";
    }).join("");
    return '<div class="qvq-steps' + (running ? " running" : "") + '">' + rows + "</div>";
  }

  function bindStepToggles(root) {
    root.querySelectorAll("[data-step-toggle]").forEach(function (row) {
      row.onclick = function () { row.closest(".qvq-step").classList.toggle("exp"); };
    });
  }

  function renderSerial(items) {
    // items: [{type:"text",text} | {type:"tool",start,end}] → AI 消息内串行交错 HTML
    return items.map(function (seg) {
      if (seg.type === "text") {
        return '<div class="qvq-round-text">' + (mdRender(seg.text) || esc(seg.text)) + "</div>";
      }
      var runningStep = seg.start && !seg.end;
      var ms = seg.end && seg.end.ms != null ? seg.end.ms : null;
      var cost = runningStep ? t("steps_running") : (ms != null ? (ms >= 1000 ? (ms / 1000).toFixed(1) + "s" : ms + "ms") : "");
      var output = seg.end ? String(seg.end.output || "") : "";
      var args = seg.start ? String(seg.start.arguments || "") : "";
      var compact = args.replace(/\s+/g, " ");
      var short = compact && compact !== "{}" ? "(" + (compact.length > 52 ? compact.slice(0, 52) + "…" : compact) + ")" : "";
      return '<div class="qvq-step' + (runningStep ? " running" : "") + '"><div class="qvq-step-row" data-step-toggle="1">' +
        '<span class="qvq-step-ico">' + STEP_ICON_SVG + '</span>' +
        '<span class="qvq-step-name">' + esc(seg.start ? seg.start.name : "?") + "</span>" +
        (short ? '<span class="qvq-step-args">' + esc(short) + "</span>" : "") +
        '<span class="qvq-step-ms">' + esc(cost) + "</span></div>" +
        (output ? '<pre class="qvq-step-detail">' + esc(output) + "</pre>" : "") +
        "</div>";
    }).join("");
  }

  function roundsToItems(rounds) {
    var items = [];
    (rounds || []).forEach(function (r) {
      if (r.text) items.push({ type: "text", text: r.text });
      (r.tools || []).forEach(function (t2) {
        items.push({ type: "tool", start: { step_id: "r", name: t2.tool, arguments: t2.arguments }, end: { output: t2.output, ms: t2.ms } });
      });
    });
    return items;
  }

  function segmentsToRounds(segs) {
    var rounds = [];
    (segs || []).forEach(function (seg) {
      if (seg.type === "text") {
        if (rounds.length && !rounds[rounds.length - 1].tools.length && rounds[rounds.length - 1].text) {
          rounds[rounds.length - 1].text += seg.text;
        } else {
          rounds.push({ text: seg.text, tools: [] });
        }
      } else if (seg.end) {
        if (!rounds.length) rounds.push({ text: "", tools: [] });
        rounds[rounds.length - 1].tools.push({ tool: seg.start ? seg.start.name : "?", arguments: seg.start ? seg.start.arguments : "", output: seg.end.output || "", ms: seg.end.ms });
      }
    });
    return rounds;
  }

  function traceToSteps(trace) {
    if (!Array.isArray(trace) || !trace.length) return null;
    return trace.map(function (t, i) {
      return {
        start: { step_id: "t" + i, name: t.tool || "?", arguments: t.arguments || "" },
        end: { step_id: "t" + i, name: t.tool || "?", output: t.output || "", ms: t.ms },
      };
    });
  }

  var historySeq = 0;
  var chatLoading = false;
  function loadChatHistory() {
    var seq = ++historySeq;
    var sessionAtRequest = chatSession;
    chatLoading = true;
    renderChat();
    return api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(sessionAtRequest)).then(function (data) {
      // 竞态防护：期间已切换会话/发起新请求的过期响应直接丢弃
      if (seq !== historySeq || sessionAtRequest !== chatSession) return;
      chatLoading = false;
      var msgs = (data && data.messages) || [];
      chatHistory = [];
      msgs.forEach(function (m, idx) {
        if (!m || typeof m !== "object") return;
        if (m.role === "user" || m.role === "assistant") {
          var atts = (m.atts || []).map(function (a) {
            return { isImage: !!a.isImage, name: a.name || "image", data: a.data || "", mime: a.mime || "image/png" };
          });
          chatHistory.push({
            role: m.role, text: contentText(m.content), idx: idx,
            steps: traceToSteps(m.trace),
            rounds: Array.isArray(m.rounds) ? m.rounds : null,
            atts: atts,
          });
        }
      });
      renderChat();
    }, function () {
      if (seq !== historySeq) return;
      chatLoading = false;
      renderChat();
    }, function () {
      chatLoading = false;
      renderChat();
    });
  }

  var CHIP_KEYS = ["chat_chip_1", "chat_chip_2", "chat_chip_3", "chat_chip_4"];
  var HERO_SVG = "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><rect x='4' y='7' width='16' height='12' rx='3' stroke-dasharray='3 2'/><circle cx='9' cy='13' r='1.2' fill='currentColor'/><circle cx='15' cy='13' r='1.2' fill='currentColor'/><path d='M12 7V4'/><circle cx='12' cy='3' r='1' fill='currentColor'/></svg>";

  function renderChat() {
    var box = el("qvq-chat-box");
    var main = document.querySelector(".qvq-chat-main");
    var chips = el("qvq-chat-chips");
    if (!chatHistory.length) {
      if (main) main.classList.add("is-empty");
      if (chips) {
        chips.style.display = "flex";
        chips.innerHTML = CHIP_KEYS.map(function (k) {
          return '<button type="button" class="qvq-chat-chip">' + esc(t(k)) + "</button>";
        }).join("");
        chips.querySelectorAll(".qvq-chat-chip").forEach(function (chip, i) {
          chip.onclick = function () {
            var input = el("qvq-chat-input");
            if (!input || chatBusy) return;
            input.value = t(CHIP_KEYS[i]);
            input.dispatchEvent(new Event("input"));
            sendChat();
          };
        });
      }
      box.innerHTML = '<div class="qvq-chat-hero"><div class="qvq-chat-hero-ico">' + HERO_SVG + "</div>" +
        '<div class="qvq-chat-hero-title">' + esc(heroTitle()) + "</div>" +
        '<div class="qvq-chat-hero-sub">' + esc(t("chat_hero_sub")) + "</div></div>";
      return;
    }
    if (main) main.classList.remove("is-empty");
    if (chips) {
      chips.style.display = "none";
      chips.innerHTML = "";
    }
    if (chatLoading) {
      box.innerHTML = '<div class="qvq-chat-loading">' + HERO_SVG + '<span class="qvq-chat-loading-tx">QvQ Chat</span></div>';
      return;
    }
    var chatHtmlKey = chatSession + "::" + chatHistory.map(function (m) { return [m.role, m.text, m.steps ? m.steps.length : 0, (m.atts || []).length].join("\u0001"); }).join("\u0002");
    if (box.getAttribute("data-html") === chatHtmlKey) {
      bindMdCopy(box);
      return;
    }
    box.setAttribute("data-html", chatHtmlKey);
    box.innerHTML = chatHistory.map(function (m, i) {
      var inner = "";
      (m.atts || []).forEach(function (a) {
        if (a.isImage) {
          inner += '<img class="qvq-msg-img" data-idx="' + i + '" src="' + a.data + '" alt=""/>';
        } else {
          inner += '<span class="qvq-msg-file"><i class="qvq-file-ico">' + FILE_ICON_SVG + "</i>" + esc(a.name) + "</span>";
        }
      });
      var body;
      if (m.role === "assistant" && m.rounds && m.rounds.length) {
        body = '<div class="qvq-rounds">' + renderSerial(roundsToItems(m.rounds)) + "</div>";
      } else {
        body = m.role === "user" ? esc(m.text) : (mdRender(m.text) || esc(m.text));
      }
      var stepsBlock = m.role === "assistant" && !m.rounds && m.steps && m.steps.length ? stepsHtml(m.steps, false) : "";
      var acts = m.role === "user" && m.idx != null
        ? '<div class="qvq-msg-acts">' +
          '<button type="button" data-copy-msg="' + i + '" title="' + esc(t("copy")) + '"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg></button>' +
          '<button type="button" data-edit-msg="' + i + '" title="' + esc(t("edit")) + '"><svg viewBox="0 0 24 24"><path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg></button>' +
          "</div>"
        : "";
      var freshCls = m.fresh ? " qvq-msg-new" : "";
      if (m.role === "user") {
        // 气泡 + 下方独立操作行（hover 显示），气泡本身不动
        return '<div class="qvq-msg-wrap"><div class="qvq-msg me' + freshCls + '">' + inner + body + '</div>' + acts + "</div>";
      }
      return '<div class="qvq-msg bot' + freshCls + '">' + stepsBlock + inner + body + "</div>";
    }).join("");
    box.querySelectorAll(".qvq-msg-img").forEach(function (img) {
      img.onclick = function () {
        var m = chatHistory[parseInt(img.getAttribute("data-idx"), 10)] || {};
        var att = ((m.atts || []).filter(function (a) { return a.isImage; })[0]) || {};
        openModal(att.name || "image", '<img style="max-width:100%;border-radius:12px" src="' + att.data + '" alt=""/>');
      };
    });
    box.querySelectorAll("[data-copy-msg]").forEach(function (btn) {
      btn.onclick = function () {
        var m = chatHistory[parseInt(btn.getAttribute("data-copy-msg"), 10)] || {};
        copyText(m.text || "");
        var old = btn.getAttribute("title");
        btn.setAttribute("title", t("copied"));
        setTimeout(function () { btn.setAttribute("title", old); }, 1200);
      };
    });
    box.querySelectorAll("[data-edit-msg]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-edit-msg"), 10);
        var m = chatHistory[i];
        if (!m || m.idx == null) return;
        var wrapNode = btn.closest(".qvq-msg-wrap");
        var node = wrapNode ? wrapNode.querySelector(".qvq-msg") : null;
        if (!node || node.querySelector(".qvq-edit-box")) return;
        var box2 = document.createElement("div");
        box2.className = "qvq-edit-box";
        box2.innerHTML = '<textarea class="qvq-textarea" rows="3"></textarea>' +
          '<div class="qvq-actions"><button class="qvq-btn small" data-save>' + esc(t("save")) + "</button>" +
          '<button class="qvq-btn small ghost" data-cancel>' + esc(t("cancel")) + "</button></div>";
        box2.querySelector("textarea").value = m.text;
        node.appendChild(box2);
        box2.querySelector("[data-cancel]").onclick = function () { box2.remove(); };
        box2.querySelector("[data-save]").onclick = function () {
          var val = box2.querySelector("textarea").value;
          api("/api/qvq/session/context/edit", "POST", { chat_key: chatSession, index: m.idx, content: val }).then(function () {
            toast(t("saved"));
            loadChatHistory();
          });
        };
      };
    });
    bindStepToggles(box);
    bindMdCopy(box);
    chatHistory.forEach(function (m2) { if (m2.fresh) m2.fresh = false; });
    // 流式输出进行中时，把仍活跃的实时节点接回（切走再切回不丢画面）
    if (chatBusy && activeLive && activeLive.session === chatSession && !box.querySelector(".qvq-msg.live")) {
      box.appendChild(activeLive.els.root);
    }
    box.scrollTop = box.scrollHeight;
  }

  var FILE_ICON_SVG = "<svg viewBox='0 0 24 24'><path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><path d='M14 3v5h5'/></svg>";

  function isTextFile(file) {
    if (file.type && file.type.indexOf("text/") === 0) return true;
    if (file.type === "application/json") return true;
    return /\.(txt|md|markdown|json|csv|tsv|log|ya?ml|toml|ini|cfg|conf|py|js|ts|jsx|tsx|html?|css|scss|sh|bat|ps1|c|cpp|h|hpp|java|kt|go|rs|rb|php|sql|xml)$/i.test(file.name || "");
  }

  function handleFiles(files) {
    Array.prototype.slice.call(files).forEach(function (file) {
      if (!file) return;
      if (/^image\//.test(file.type)) {
        if (chatAtts.filter(function (a) { return a.isImage; }).length >= 3) {
          toast(t("chat_img_limit"), true);
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          toast(t("chat_file_bad") + " " + file.name + " (>5MB)", true);
          return;
        }
        var reader = new FileReader();
        reader.onload = function () {
          chatAtts.push({ name: file.name, mime: file.type, data: String(reader.result), isImage: true });
          renderAttach();
        };
        reader.readAsDataURL(file);
      } else if (isTextFile(file)) {
        if (file.size > 1024 * 1024) {
          toast(t("chat_file_bad") + " " + file.name, true);
          return;
        }
        var r2 = new FileReader();
        r2.onload = function () {
          chatAtts.push({ name: file.name, mime: file.type || "text/plain", data: String(r2.result), isImage: false });
          renderAttach();
        };
        r2.readAsText(file);
      } else {
        // 任意二进制文件（zip/pdf 等）：base64 上传，后端落盘交给 AI 自行处理
        if (file.size > 20 * 1024 * 1024) {
          toast(t("chat_file_big") + " " + file.name + " (>20MB)", true);
          return;
        }
        var r3 = new FileReader();
        r3.onload = function () {
          chatAtts.push({ name: file.name, mime: file.type || "application/octet-stream", data: String(r3.result), isImage: false });
          renderAttach();
        };
        r3.readAsDataURL(file);
      }
    });
  }

  function renderAttach() {
    var box = el("qvq-chat-attach");
    if (!box) return;
    box.innerHTML = chatAtts.map(function (a, i) {
      return '<div class="qvq-att">' + (a.isImage ? '<img src="' + a.data + '" alt=""/>' : '<span class="qvq-att-ico">' + FILE_ICON_SVG + "</span>") +
        "<span>" + esc(a.name) + "</span>" +
        '<button type="button" data-rm="' + i + '" aria-label="remove"><svg viewBox=\'0 0 24 24\'><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>';
    }).join("");
    box.querySelectorAll("button[data-rm]").forEach(function (btn) {
      btn.onclick = function () {
        chatAtts.splice(parseInt(btn.getAttribute("data-rm"), 10), 1);
        renderAttach();
      };
    });
  }

  function setSendStopping(stopping) {
    var btn = el("qvq-chat-send");
    if (!btn) return;
    btn.classList.toggle("stopping", stopping);
    btn.title = t(stopping ? "chat_stop" : "chat_send");
    btn.innerHTML = stopping
      ? '<svg class="ico-stop" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>'
      : '<svg class="ico-send" viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  }

  function renderWaitTimer(box, els, live) {
    if (live.status !== "running" || live.text) return;
    var secs = Math.max(0, Math.round((Date.now() - (live.started || Date.now())) / 1000));
    els.textEl.innerHTML = '<span class="qvq-live-wait">' + esc(t("steps_running")) + " " + secs + "s</span>";
  }

  function startWaitTimer(box, els, live) {
    var timer = setInterval(function () {
      if (!live.started || live.status !== "running" || live.text) { clearInterval(timer); return; }
      renderWaitTimer(box, els, live);
    }, 1000);
    return timer;
  }

  function cancelChat() {
    api("/api/qvq/chat/cancel", "POST", { session: chatSession }).catch(function () {});
  }

  // ── SSE 流式对话 + 后端流恢复 ──
  function streamChat(payload, onEvent) {
    var headers = { "Content-Type": "application/json" };
    var token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch("/QvQChat/api/qvq/chat/stream", {
      method: "POST",
      headers: headers,
      body: JSON.stringify(payload),
    }).then(function (resp) {
      if (resp.status === 409) return { __busy: true };
      if (!resp.ok || !resp.body) throw new Error("stream unavailable");
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buf = "";
      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) return;
          buf += decoder.decode(chunk.value, { stream: true });
          var idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            var block = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            var ev = "message", data = "";
            block.split("\n").forEach(function (line) {
              if (line.indexOf("event:") === 0) ev = line.slice(6).trim();
              else if (line.indexOf("data:") === 0) data += line.slice(5).trim();
            });
            if (!data) continue;
            try { onEvent(ev, JSON.parse(data)); } catch (e) { (window.__pumpErrs = window.__pumpErrs || []).push(String((e && e.stack) || e)); }
          }
          return pump();
        });
      }
      return pump();
    });
  }

  function nearBottom(box) {
    return box.scrollHeight - box.scrollTop - box.clientHeight < 120;
  }

  // 实时输出节点：发起与恢复共用（live = {status, text, steps, error}）
  function makeLiveNode() {
    var root = document.createElement("div");
    root.className = "qvq-msg bot live";
    root.innerHTML = '<div class="qvq-live-steps"></div><div class="qvq-live-text"><span class="qvq-cursor"></span></div>';
    return {
      root: root,
      stepsEl: root.querySelector(".qvq-live-steps"),
      textEl: root.querySelector(".qvq-live-text"),
      timer: null,
    };
  }

  function renderLiveNode(box, els, live) {
    var stick = nearBottom(box);
    els.stepsEl.innerHTML = stepsHtml(live.steps, true);
    bindStepToggles(els.stepsEl);
    if (live.segments.length) {
      els.textEl.innerHTML = '<div class="qvq-rounds">' + renderSerial(live.segments) + "</div>";
      bindStepToggles(els.textEl);
    } else if (!live.text && live.started) {
      var secs = Math.max(0, Math.round((Date.now() - live.started) / 1000));
      els.textEl.innerHTML = '<span class="qvq-live-wait">' + esc(t("steps_running")) + " " + secs + "s</span>";
    } else {
      els.textEl.innerHTML = mdRender(live.text) || '<span class="qvq-cursor"></span>';
    }
    if (stick) box.scrollTop = box.scrollHeight;
  }

  // 离开期间会话仍在输出：轮询快照恢复渲染，结束后落定
  function attachLive(snapshot) {
    if (chatBusy) return;
    var box = el("qvq-chat-box");
    var live = { status: snapshot.status || "running", text: snapshot.text || "", steps: snapshot.steps || [], error: snapshot.error || null };
    chatBusy = true;
    setSendStopping(true);
    var els = makeLiveNode();
    box.appendChild(els.root);
    activeLive = { els: els, session: snapshot.session };
    live.started = (snapshot.started || 0) * 1000 || Date.now();
    live.segments = snapshot.segments || [];
    renderLiveNode(box, els, live);
    var poll = setInterval(function () {
      if (chatSession !== snapshot.session) { clearInterval(poll); els.root.remove(); chatBusy = false; activeLive = null; setSendStopping(false); return; }
      api("/api/qvq/chat/live?session=" + encodeURIComponent(chatSession)).then(function (snap) {
        if (!snap || snap.status === "idle") {
          clearInterval(poll);
          els.root.remove();
          chatBusy = false;
          activeLive = null;
          setSendStopping(false);
          return;
        }
        live.status = snap.status;
        live.text = snap.text || "";
        live.steps = snap.steps || [];
        live.segments = snap.segments || [];
        live.error = snap.error || null;
        renderLiveNode(box, els, live);
        if (snap.status !== "running") {
          clearInterval(poll);
          setSendStopping(false);
          setTimeout(function () {
            els.root.remove();
            chatBusy = false;
            activeLive = null;
            loadChatHistory();
          }, 400);
        }
      });
    }, 800);
  }

  function sendChat() {
    if (chatBusy) { queueCurrent(); return; }
    var input = el("qvq-chat-input");
    var text = input.value.trim();
    if (!text && !chatAtts.length) return;
    var atts = chatAtts.slice();
    chatAtts = [];
    input.value = "";
    input.style.height = "auto";
    renderAttach();
    dispatchMessage(text, atts);
  }

  // AI 忙碌时点发送 → 暂存，待当前生成完毕按顺序继续
  function queueCurrent() {
    var input = el("qvq-chat-input");
    var text = input.value.trim();
    if (!text && !chatAtts.length) return;
    chatQueue.push({ text: text, atts: chatAtts.slice() });
    chatAtts = [];
    input.value = "";
    input.style.height = "auto";
    renderAttach();
    renderQueue();
    toast(t("queue_added"));
  }

  function pumpQueue() {
    if (chatBusy || !chatQueue.length) return;
    var item = chatQueue.shift();
    renderQueue();
    dispatchMessage(item.text, item.atts);
  }

  function dispatchMessage(text, atts) {
    chatBusy = true;
    chatHistory.push({ role: "user", text: text, atts: atts, fresh: true });
    renderChat();
    var box = el("qvq-chat-box");
    var live = { status: "running", text: "", steps: [], segments: [], error: null, started: Date.now() };
    var els = makeLiveNode();
    box.appendChild(els.root);
    activeLive = { els: els, session: chatSession };
    var waitTimer = startWaitTimer(box, els, live);
    renderWaitTimer(box, els, live);
    box.scrollTop = box.scrollHeight;
    var renderTimer = null;
    function scheduleText() {
      if (renderTimer) return;
      renderTimer = setTimeout(function () {
        renderTimer = null;
        renderLiveNode(box, els, live);
      }, 50);
    }
    function refreshSteps() {
      renderLiveNode(box, els, live);
    }
    var payload = {
      text: text,
      session: chatSession,
      persona: chatPersona,
      skills: chatMentions.skills.slice(),
      mcp_tools: chatMentions.mcp.slice(),
      model: chatModel,
      temperature: chatEffort === "" ? null : parseFloat(chatEffort),
      attachments: atts.map(function (a) { return { name: a.name, mime: a.mime, data: a.data }; }),
    };
    var finished = false;
    setSendStopping(true);
    function settle(reply, stepsOut, isErr) {
      if (finished) return;
      finished = true;
      if (renderTimer) { clearTimeout(renderTimer); renderTimer = null; }
      if (waitTimer) { clearInterval(waitTimer); waitTimer = null; }
      activeLive = null;
      els.root.remove();
      var roundsOut = segmentsToRounds((typeof live !== "undefined" && live && live.segments) ? live.segments : []);
      chatHistory.push({ role: "assistant", text: reply, steps: stepsOut, rounds: roundsOut.length ? roundsOut : null, err: !!isErr });
      renderChat();
      chatBusy = false;
      setSendStopping(false);
      loadChatMeta();
      pumpQueue();
    }
    // 正在输出的会话被接回（如另一标签页发起）：转恢复模式
    function reattach() {
      if (finished) return;
      api("/api/qvq/chat/live?session=" + encodeURIComponent(chatSession)).then(function (snap) {
        if (snap && snap.status === "running") {
          els.root.remove();
          chatBusy = false;
          attachLive(snap);
        } else {
          settle("", [], false);
          loadChatHistory();
        }
      });
    }
    streamChat(payload, function (ev, data) {
      if (ev === "delta" && data.t) {
        live.text += data.t;
        if (data.i != null) {
          while (live.segments.length <= data.i) live.segments.push({ type: "text", text: "" });
          if (live.segments[data.i].type !== "text") live.segments.splice(data.i, 0, { type: "text", text: "" });
          live.segments[data.i].text += data.t;
        } else {
          var lastSeg = live.segments[live.segments.length - 1];
          if (!lastSeg || lastSeg.type !== "text") live.segments.push({ type: "text", text: "" });
          live.segments[live.segments.length - 1].text += data.t;
        }
        scheduleText();
      } else if (ev === "reset") {
        live.text = "";
        live.steps = [];
        live.segments = [];
        if (renderTimer) { clearTimeout(renderTimer); renderTimer = null; }
        renderLiveNode(box, els, live);
      } else if (ev === "tool") {
        if (data.phase === "start") {
          live.steps.push({ start: data });
          live.segments.push({ type: "tool", start: data });
        } else {
          var match = null;
          for (var i = live.steps.length - 1; i >= 0; i--) {
            if (live.steps[i].start && live.steps[i].start.step_id === data.step_id && !live.steps[i].end) { match = live.steps[i]; break; }
          }
          if (!match) {
            for (var j = live.steps.length - 1; j >= 0; j--) { if (!live.steps[j].end) { match = live.steps[j]; break; } }
          }
          if (match) match.end = data;
          var segMatch = null;
          for (var k = live.segments.length - 1; k >= 0; k--) {
            var sg = live.segments[k];
            if (sg.type === "tool" && sg.start && sg.start.step_id === data.step_id && !sg.end) { segMatch = sg; break; }
          }
          if (!segMatch) {
            for (var m3 = live.segments.length - 1; m3 >= 0; m3--) {
              var sg2 = live.segments[m3];
              if (sg2.type === "tool" && !sg2.end) { segMatch = sg2; break; }
            }
          }
          if (segMatch) segMatch.end = data;
        }
        refreshSteps();
      } else if (ev === "error") {
        if (data.error === "cancelled") {
          settle(live.text || t("chat_cancelled"), live.steps, false);
        } else {
          settle(data.error || t("chat_err"), live.steps, true);
          toast(data.error || t("chat_err"), true);
        }
      } else if (ev === "done") {
        settle((data.reply != null ? data.reply : live.text) || "…", live.steps, false);
      }
    }).then(function (result) {
      if (result && result.__busy) {
        toast(t("chat_busy"), true);
        reattach();
        return;
      }
      if (!finished && result === undefined) {
        // 流意外中断且无 end 事件：以服务端快照为准收尾
        api("/api/qvq/chat/live?session=" + encodeURIComponent(chatSession)).then(function (snap) {
          if (snap && snap.reply != null) settle(snap.reply, snap.steps || live.steps, false);
          else if (snap && snap.error) settle(snap.error, snap.steps || live.steps, true);
          else settle(live.text || "…", live.steps, false);
        });
      }
    }).catch(function () {
      if (finished) return;
      api("/api/qvq/chat", "POST", payload).then(function (data) {
        if (data && data.error) {
          settle(data.error || t("chat_err"), [], true);
          toast(data.error || t("chat_err"), true);
        } else {
          settle((data && data.reply) || "…", [], false);
        }
      });
    });
  }

  // ── 通用模态表单 ──
  function fv(root, id) {
    var node = root.querySelector("#" + id);
    return node ? node.value.trim() : "";
  }

  function openForm(title, fieldsHtml, onSave) {
    var html = fieldsHtml +
      "<div class='qvq-actions'><button class='qvq-btn' data-form-save>" + esc(t("save")) + "</button>" +
      "<button class='qvq-btn ghost' data-form-cancel>" + esc(t("cancel")) + "</button></div>";
    openModal(title, html);
    var body = el("qvq-modal-body");
    body.querySelector("[data-form-cancel]").onclick = closeModal;
    body.querySelector("[data-form-save]").onclick = function () { onSave(body); };
  }

  function loadModels() {
    api("/api/qvq/models").then(function (data) {
      var providers = (data && data.providers) || [];
      modelPresets = (data && data.presets) || [];
      if (!providers.length) {
        el("qvq-models-list").innerHTML = '<div class="qvq-empty qvq-empty-cta">' + esc(t("models_empty")) + "</div>";
        var cta = el("qvq-models-list").querySelector(".qvq-empty-cta");
        if (cta) cta.onclick = function () { openModelModal(null); };
        return;
      }
      var rows = providers.map(function (p) {
        var enabled = (p.models || []).filter(function (m) { return m.enabled !== false; });
        var names = enabled.map(function (m) { return esc(m.id); }).join("<br>") || "-";
        var firstModel = enabled.length ? String(enabled[0].id) : "";
        return "<tr><td><b>" + esc(p.name) + "</b><div class='qvq-tool-desc'>" + esc(p.base_url || "") + "</div></td>" +
          "<td>" + names + "</td>" +
          "<td>" + esc(p.api_key_masked || "-") + "</td>" +
          "<td><button class='qvq-btn small ghost' data-act='edit' data-id='" + esc(p.id) + "'>" + esc(t("edit")) + "</button> " +
          (firstModel ? "<button class='qvq-btn small ghost' data-act='test' data-model='" + esc(firstModel) + "'>" + esc(t("test")) + "</button> " : "") +
          "<button class='qvq-btn small danger' data-act='pdel' data-id='" + esc(p.id) + "'>" + esc(t("del")) + "</button></td></tr>";
      }).join("");
      el("qvq-models-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("models_name")) + "</th><th>" +
        esc(t("models_id")) + "</th><th>key</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      el("qvq-models-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var pid = btn.getAttribute("data-id");
          var act = btn.getAttribute("data-act");
          if (act === "pdel") {
            confirmDialog(t("confirm_del")).then(function (ok) {
              if (!ok) return;
              api("/api/qvq/providers/delete", "POST", { id: pid }).then(function () { toast(t("deleted")); loadModels(); });
            });
          } else if (act === "test") {
            btn.disabled = true;
            api("/api/qvq/models/test", "POST", { id: btn.getAttribute("data-model") }).then(function (r) {
              btn.disabled = false;
              if (r && r.ok) toast(t("model_test_ok") + " · " + (r.model || "") + " · " + r.ms + "ms");
              else toast((r && r.error) || t("model_test_fail"), true);
            });
          } else {
            var provider = providers.filter(function (pv) { return pv.id === pid; })[0];
            if (provider) openModelModal(provider);
          }
        };
      });
    });
  }

  function openModelModal(provider) {
    var editingId = provider && provider.id ? provider.id : "";
    var fields =
      "<label class='qvq-label'>" + esc(t("models_preset")) + "</label>" +
      "<select class='qvq-select' id='qvq-mf-preset'></select>" +
      "<label class='qvq-label'>" + esc(t("models_name")) + "</label>" +
      "<input class='qvq-input' id='qvq-mf-name' placeholder='deepseek-main' />" +
      "<label class='qvq-label'>" + esc(t("models_baseurl")) + "</label>" +
      "<input class='qvq-input' id='qvq-mf-url' placeholder='https://api.deepseek.com/v1' />" +
      "<label class='qvq-label'>" + esc(t("models_apikey")) + "</label>" +
      "<input class='qvq-input' id='qvq-mf-key' type='password' placeholder='sk-…' />" +
      "<label class='qvq-label'>" + esc(t("models_id")) + "</label>" +
      "<input class='qvq-input' id='qvq-mf-id' placeholder='deepseek-chat' />" +
      "<div class='qvq-actions' style='margin-top:10px'><button class='qvq-btn small ghost' id='qvq-mf-fetch' type='button'>" + esc(t("models_fetch")) + "</button></div>" +
      "<div id='qvq-mf-remote'></div>";
    openForm(editingId ? (provider.name || editingId) : t("models_add"), fields, function (body) {
      var payload = {
        id: editingId || fv(body, "qvq-mf-name").toLowerCase().replace(/[^a-z0-9-]/g, "-"),
        name: fv(body, "qvq-mf-name"),
        base_url: fv(body, "qvq-mf-url"),
        api_key: fv(body, "qvq-mf-key"),
        models: fv(body, "qvq-mf-id").split(",").map(function (x) { return x.trim(); }).filter(Boolean)
          .map(function (id) { return { id: id, enabled: true }; })
      };
      if (!payload.name || !payload.base_url) {
        toast(t("models_fetch_fail"), true);
        return;
      }
      api("/api/qvq/providers/save", "POST", payload).then(function (data) {
        if (data && data.ok) {
          toast(t("saved"));
          closeModal();
          loadModels();
        } else {
          toast((data && data.error) || "error", true);
        }
      });
    });
    var body = el("qvq-modal-body");
    var presetSel = body.querySelector("#qvq-mf-preset");
    presetSel.innerHTML = modelPresets.map(function (p) {
      return "<option value='" + esc(p.id) + "'>" + esc(p.name) + "</option>";
    }).join("");
    presetSel.value = "custom";
    presetSel.onchange = function () {
      var preset = modelPresets.filter(function (x) { return x.id === presetSel.value; })[0];
      if (!preset || preset.id === "custom") return;
      if (!body.querySelector("#qvq-mf-name").value.trim()) body.querySelector("#qvq-mf-name").value = preset.name || "";
      body.querySelector("#qvq-mf-url").value = preset.base_url || "";
    };
    if (provider) {
      body.querySelector("#qvq-mf-name").value = provider.name || "";
      body.querySelector("#qvq-mf-url").value = provider.base_url || "";
      body.querySelector("#qvq-mf-id").value = (provider.models || []).filter(function (m) { return m.enabled !== false; }).map(function (m) { return m.id; }).join(", ");
    }
    body.querySelector("#qvq-mf-fetch").onclick = function () {
      var btn = this;
      var base_url = fv(body, "qvq-mf-url");
      var api_key = fv(body, "qvq-mf-key");
      var box = body.querySelector("#qvq-mf-remote");
      if (!base_url) {
        toast(t("models_fetch_fail"), true);
        return;
      }
      btn.disabled = true;
      btn.textContent = t("models_fetching");
      box.innerHTML = "";
      api("/api/qvq/providers/remote-models", "POST", { base_url: base_url, api_key: api_key, id: editingId }).then(function (data) {
        btn.disabled = false;
        btn.textContent = t("models_fetch");
        if (data && data.error) {
          toast(data.error, true);
          return;
        }
        var models = (data && data.models) || [];
        if (!models.length) {
          box.innerHTML = "<div class='qvq-remote-list'><span class='qvq-tool-desc'>" + esc(t("models_remote_empty")) + "</span></div>";
          return;
        }
        box.innerHTML = "<div class='qvq-remote-list'>" + models.map(function (m) {
          var meta = [];
          if (m.context_length) meta.push(m.context_length + " ctx");
          if (m.vision) meta.push("vision");
          if (m.tool_call) meta.push("tools");
          return "<label><input type='checkbox' data-mid='" + esc(m.id) + "'/> <span>" + esc(m.id) + "</span>" +
            (meta.length ? "<span class='meta'>" + esc(meta.join(" · ")) + "</span>" : "") + "</label>";
        }).join("") + "</div>";
        box.querySelectorAll("input[data-mid]").forEach(function (cb) {
          cb.onchange = function () {
            var ids = [];
            box.querySelectorAll("input[data-mid]").forEach(function (c2) {
              if (c2.checked) ids.push(c2.getAttribute("data-mid"));
            });
            if (ids.length) body.querySelector("#qvq-mf-id").value = ids.join(", ");
          };
        });
      });
    };
  }

  function loadPersonas() {
    api("/api/qvq/personas").then(function (data) {
      var personas = (data && data.personas) || [];
      var rows = personas.map(function (p) {
        var chip = p.builtin ? " <span class='qvq-chip'>" + esc(t("personas_builtin")) + "</span>" : "";
        if (p.modified) chip += " <span class='qvq-chip o-eco'>" + esc(t("personas_modified")) + "</span>";
        var btns = "<button class='qvq-btn small ghost' data-act='edit' data-id='" + esc(p.id) + "'>" + esc(t("edit")) + "</button> ";
        if (!p.builtin || p.modified) {
          var delLabel = p.builtin ? t("personas_reset") : t("del");
          btns += "<button class='qvq-btn small danger' data-act='del' data-id='" + esc(p.id) + "'>" + esc(delLabel) + "</button>";
        }
        return "<tr><td><b>" + esc(p.id) + "</b>" + chip + "<div class='qvq-tool-desc'>" + esc((p.system || "").slice(0, 80)) + "…</div></td>" +
          "<td>" + esc(p.name || "") + "</td><td>" + btns + "</td></tr>";
      }).join("");
      var table = rows
        ? "<table class='qvq-table'><thead><tr><th>" + esc(t("col_id")) + "</th><th>" + esc(t("personas_pname")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>"
        : '<div class="qvq-empty">' + esc(t("personas_empty")) + "</div>";
      var options = personas.map(function (p) {
        return "<option value='" + esc(p.id) + "'>" + esc(p.id) + "</option>";
      }).join("");
      el("qvq-personas-list").innerHTML = table +
        "<h3 class='qvq-card-title' style='margin-top:14px'>" + esc(t("bindings")) + "</h3>" +
        "<div class='qvq-field-row'><input class='qvq-input' id='qvq-bind-key' placeholder='" + esc(t("bind_hint")) + "' />" +
        "<select class='qvq-select' id='qvq-bind-persona'>" + options + "</select>" +
        "<button class='qvq-btn small' id='qvq-bind-btn'>" + esc(t("bind_btn")) + "</button></div>";
      el("qvq-personas-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var id = btn.getAttribute("data-id");
          if (btn.getAttribute("data-act") === "del") {
            var isBuiltin = id === "assistant";
            confirmDialog(isBuiltin ? t("personas_reset") : t("confirm_del")).then(function (ok) {
              if (!ok) return;
              api("/api/qvq/personas/delete", "POST", { id: id }).then(function () {
                toast(isBuiltin ? t("personas_reset") : t("deleted"));
                loadPersonas();
              });
            });
          } else {
            var persona = personas.filter(function (p) { return p.id === id; })[0];
            if (persona) openPersonaModal(persona);
          }
        };
      });
      var bindBtn = el("qvq-bind-btn");
      if (bindBtn) {
        bindBtn.onclick = function () {
          var key = el("qvq-bind-key").value.trim();
          if (!key) return;
          api("/api/qvq/personas/bind", "POST", { chat_key: key, persona: el("qvq-bind-persona").value }).then(function () {
            toast(t("saved"));
            el("qvq-bind-key").value = "";
          });
        };
      }
    });
  }

  function openPersonaModal(persona) {
    var isEdit = !!persona;
    var fields =
      "<label class='qvq-label'>" + esc(t("personas_pid")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-id' placeholder='my_persona'" + (isEdit ? " readonly" : "") + " />" +
      "<label class='qvq-label'>" + esc(t("personas_pname")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-name' placeholder='QvQ' />" +
      "<label class='qvq-label'>" + esc(t("personas_system")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-pf-system'></textarea>" +
      "<label class='qvq-label'>" + esc(t("personas_tools")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-tools' placeholder='send_message, eco_*, remember' />";
    openForm(isEdit ? (persona.name || persona.id) : t("personas_new"), fields, function (body) {
      var payload = {
        id: fv(body, "qvq-pf-id"),
        name: fv(body, "qvq-pf-name"),
        system: body.querySelector("#qvq-pf-system").value,
        tools: fv(body, "qvq-pf-tools").split(",").map(function (x) { return x.trim(); }).filter(Boolean)
      };
      if (!payload.id) {
        toast(t("personas_pid"), true);
        return;
      }
      api("/api/qvq/personas/save", "POST", payload).then(function (data) {
        if (data && data.ok) {
          toast(t("saved"));
          closeModal();
          loadPersonas();
        } else {
          toast((data && data.error) || "error", true);
        }
      });
    });
    if (isEdit) {
      var body = el("qvq-modal-body");
      body.querySelector("#qvq-pf-id").value = persona.id || "";
      body.querySelector("#qvq-pf-name").value = persona.name || "";
      body.querySelector("#qvq-pf-system").value = persona.system || "";
      body.querySelector("#qvq-pf-tools").value = (persona.tools || []).join(", ");
    }
  }

  function loadSkills() {
    api("/api/qvq/skills").then(function (data) {
      var skills = (data && data.skills) || [];
      if (!skills.length) {
        el("qvq-skills-list").innerHTML = '<div class="qvq-empty qvq-empty-cta">' + esc(t("skills_empty")) + "</div>";
        var cta = el("qvq-skills-list").querySelector(".qvq-empty-cta");
        if (cta) cta.onclick = function () { openSkillModal(null); };
        return;
      }
      var rows = skills.map(function (sk) {
        var src = sk.source === "file" ? ".md" : "dashboard";
        var chk = sk.enabled !== false ? " checked" : "";
        return "<tr><td><b>" + esc(sk.name) + "</b><div class='qvq-tool-desc'>" + esc((sk.description || "").slice(0, 100)) + "</div></td>" +
          "<td><span class='qvq-chip'>" + esc(src) + "</span></td>" +
          "<td><input type='checkbox' data-toggle='" + esc(sk.name) + "'" + chk + "/></td>" +
          "<td><button class='qvq-btn small ghost' data-act='edit' data-name='" + esc(sk.name) + "'>" + esc(t("edit")) + "</button> " +
          "<button class='qvq-btn small danger' data-act='del' data-name='" + esc(sk.name) + "'>" + esc(t("del")) + "</button></td></tr>";
      }).join("");
      el("qvq-skills-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("skills_name")) + "</th><th>" + esc(t("skills_source")) +
        "</th><th>" + esc(t("on")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      el("qvq-skills-list").querySelectorAll("input[data-toggle]").forEach(function (cb) {
        cb.onchange = function () {
          api("/api/qvq/skills/enabled", "POST", { name: cb.getAttribute("data-toggle"), enabled: cb.checked }).then(function () {
            loadSkills();
          });
        };
      });
      el("qvq-skills-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var name = btn.getAttribute("data-name");
          if (btn.getAttribute("data-act") === "del") {
            confirmDialog(t("confirm_del")).then(function (ok) {
              if (!ok) return;
              api("/api/qvq/skills/delete", "POST", { name: name }).then(function () {
                toast(t("deleted"));
                loadSkills();
              });
            });
          } else {
            var skill = skills.filter(function (x) { return x.name === name; })[0];
            if (skill) openSkillModal(skill);
          }
        };
      });
    });
  }

  function openSkillModal(skill) {
    var isEdit = !!skill;
    var fields =
      "<label class='qvq-label'>" + esc(t("skills_name")) + "</label>" +
      "<input class='qvq-input' id='qvq-sf-name' placeholder='translate' />" +
      "<label class='qvq-label'>" + esc(t("skills_description")) + "</label>" +
      "<input class='qvq-input' id='qvq-sf-desc' placeholder='…' />" +
      "<label class='qvq-label'>" + esc(t("skills_body")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-sf-body' style='min-height:180px'></textarea>";
    openForm(isEdit ? skill.name : t("skills_add"), fields, function (body) {
      var name = fv(body, "qvq-sf-name");
      if (!name) return;
      api("/api/qvq/skills/save", "POST", {
        name: name,
        description: fv(body, "qvq-sf-desc"),
        body: body.querySelector("#qvq-sf-body").value
      }).then(function (data) {
        if (data && data.ok) {
          toast(t("saved"));
          closeModal();
          loadSkills();
        } else {
          toast((data && data.error) || "error", true);
        }
      });
    });
    if (isEdit) {
      var body = el("qvq-modal-body");
      body.querySelector("#qvq-sf-name").value = skill.name || "";
      body.querySelector("#qvq-sf-desc").value = skill.description || "";
      body.querySelector("#qvq-sf-body").value = skill.body || "";
    }
  }

  function loadTools() {
    api("/api/qvq/tools").then(function (data) {
      var tools = (data && data.tools) || [];
      var riskLabel = (data && data.risk) || "risk";
      renderToolList(tools, "", riskLabel);
      var filter = el("qvq-tools-filter");
      filter.oninput = function () {
        renderToolList(tools, filter.value.trim().toLowerCase(), riskLabel);
      };
    });
  }

  function renderToolList(tools, keyword, riskLabel) {
    var shown = tools.filter(function (tool) {
      if (!keyword) return true;
      return tool.name.toLowerCase().indexOf(keyword) >= 0 || tool.label.toLowerCase().indexOf(keyword) >= 0 ||
        (tool.description || "").toLowerCase().indexOf(keyword) >= 0;
    });
    if (!shown.length) {
      el("qvq-tools-list").innerHTML = '<div class="qvq-empty">' + esc(t("tools_empty")) + "</div>";
      return;
    }
    el("qvq-tools-list").innerHTML = shown.map(function (tool) {
      var chips = "<span class='qvq-chip o-" + esc(tool.origin) + "'>" + esc(tool.origin_label || tool.origin) + "</span>" +
        (tool.danger ? "<span class='qvq-chip danger-chip'>" + esc(riskLabel) + "</span>" : "");
      return "<div class='qvq-tool-row'><span class='qvq-tool-name'>" + chips + " " + esc(tool.label) + "</span>" +
        "<span class='qvq-tool-desc'>" + esc(tool.description) + "</span></div>";
    }).join("");
  }

  function loadExtensions() {
    api("/api/qvq/extensions").then(function (data) {
      var exts = (data && data.extensions) || [];
      var body = exts.length
        ? "<table class='qvq-table'><thead><tr><th>" + esc(t("ext_module")) + "</th><th>" +
          esc(t("ext_personas_col")) + "</th><th>" + esc(t("ext_schemas_col")) + "</th></tr></thead><tbody>" +
          exts.map(function (e) {
            return "<tr><td><b>" + esc(e.module) + "</b></td><td>" + esc(e.personas) + "</td><td>" + esc(e.schemas) + "</td></tr>";
          }).join("") + "</tbody></table>"
        : '<div class="qvq-empty">' + esc(t("ext_none")) + "</div>";
      el("qvq-extensions-list").innerHTML = body;
    });
  }

  var mcpServers = [];

  function loadMcp() {
    api("/api/qvq/mcp").then(function (data) {
      mcpServers = (data && data.servers) || [];
      var clients = {};
      ((data && data.clients) || []).forEach(function (c) { clients[c.name] = c; });
      var body = mcpServers.length
        ? "<table class='qvq-table'><thead><tr><th>" + esc(t("models_name")) + "</th><th>" + esc(t("mcp_transport")) + "</th><th>" + esc(t("mcp_status_on")) +
          "</th><th>" + esc(t("tools")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" +
          mcpServers.map(function (srv) {
            var client = clients[srv.name];
            var status = client ? client.status : "disconnected";
            var tools = client ? (client.tools || 0) : 0;
            var connected = status === "connected";
            var detail = srv.transport === "http" ? (srv.url || "") : (srv.command || "");
            var action =
              "<button class='qvq-btn small " + (connected ? "danger" : "") + "' data-act='" + (connected ? "disc" : "conn") + "' data-name='" + esc(srv.name) + "'>" +
              esc(connected ? t("mcp_disconnect") : t("mcp_connect")) + "</button> " +
              "<button class='qvq-btn small ghost' data-act='medit' data-name='" + esc(srv.name) + "'>" + esc(t("edit")) + "</button> " +
              "<button class='qvq-btn small danger' data-act='mdel' data-name='" + esc(srv.name) + "'>" + esc(t("del")) + "</button>";
            return "<tr><td><b>" + esc(srv.name) + "</b><div class='qvq-tool-desc'>" + esc(detail) + "</div></td><td>" + esc(srv.transport || "-") + "</td>" +
              "<td><span class='qvq-chip " + (connected ? "o-eco" : "") + "'>" + esc(status) + "</span></td>" +
              "<td>" + tools + "</td><td>" + action + "</td></tr>";
          }).join("") + "</tbody></table>"
        : '<div class="qvq-empty qvq-empty-cta">' + esc(t("mcp_none")) + "</div>";
      el("qvq-mcp-list").innerHTML = body;
      if (!mcpServers.length) {
        var cta = el("qvq-mcp-list").querySelector(".qvq-empty-cta");
        if (cta) cta.onclick = function () { openMcpModal(null); };
      }
      el("qvq-mcp-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var act = btn.getAttribute("data-act");
          var name = btn.getAttribute("data-name");
          if (act === "conn" || act === "disc") {
            var path = act === "conn" ? "/api/qvq/mcp/connect" : "/api/qvq/mcp/disconnect";
            btn.disabled = true;
            api(path, "POST", { name: name }).then(function (r) {
              btn.disabled = false;
              if (r && r.error) { toast(r.error, true); }
              loadMcp();
            });
          } else if (act === "mdel") {
            confirmDialog(t("confirm_del")).then(function (ok) {
              if (!ok) return;
              api("/api/qvq/mcp/delete", "POST", { name: name }).then(function () {
                toast(t("deleted"));
                loadMcp();
              });
            });
          } else if (act === "medit") {
            var server = mcpServers.filter(function (srv) { return srv.name === name; })[0];
            if (server) openMcpModal(server);
          }
        };
      });
    });
    api("/api/qvq/tools").then(function (data) {
      var tools = ((data && data.tools) || []).filter(function (tl) { return tl.origin === "mcp"; });
      el("qvq-mcp-tools").innerHTML = tools.length
        ? tools.map(function (tool) {
            return "<div class='qvq-tool-row'><span class='qvq-tool-name'>" + esc(tool.name) + "</span>" +
              "<span class='qvq-tool-desc'>" + esc(tool.description) + "</span></div>";
          }).join("")
        : '<div class="qvq-empty">' + esc(t("tools_empty")) + "</div>";
    });
  }

  function openMcpModal(server) {
    var isEdit = !!server;
    var fields =
      "<label class='qvq-label'>" + esc(t("models_name")) + "</label>" +
      "<input class='qvq-input' id='qvq-cf-name' placeholder='filesystem' />" +
      "<label class='qvq-label'>" + esc(t("mcp_transport")) + "</label>" +
      "<select class='qvq-select' id='qvq-cf-transport'><option value='stdio'>stdio</option><option value='http'>http</option></select>" +
      "<div id='qvq-cf-stdio'>" +
      "<label class='qvq-label'>" + esc(t("mcp_command")) + "</label>" +
      "<input class='qvq-input' id='qvq-cf-command' placeholder='npx' />" +
      "<label class='qvq-label'>" + esc(t("mcp_args")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-cf-args' style='min-height:56px'></textarea>" +
      "</div>" +
      "<div id='qvq-cf-http'>" +
      "<label class='qvq-label'>URL</label>" +
      "<input class='qvq-input' id='qvq-cf-url' placeholder='http://127.0.0.1:9000/mcp' />" +
      "<label class='qvq-label'>" + esc(t("mcp_headers")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-cf-headers' style='min-height:56px'></textarea>" +
      "</div>" +
      "<label class='qvq-label'>timeout (s)</label>" +
      "<input class='qvq-input' id='qvq-cf-timeout' type='number' placeholder='30' />";
    openForm(isEdit ? server.name : t("mcp_add"), fields, function (body) {
      var name = fv(body, "qvq-cf-name");
      if (!name) {
        toast(t("mcp_name_required"), true);
        return;
      }
      var transport = fv(body, "qvq-cf-transport") || "stdio";
      var entry = { name: name, transport: transport };
      if (transport === "http") {
        entry.url = fv(body, "qvq-cf-url");
        var headersRaw = body.querySelector("#qvq-cf-headers").value.trim();
        if (headersRaw) {
          try { entry.headers = JSON.parse(headersRaw); } catch (e) { toast("invalid json", true); return; }
        }
      } else {
        entry.command = fv(body, "qvq-cf-command");
        entry.args = body.querySelector("#qvq-cf-args").value.split("\n").map(function (x) { return x.trim(); }).filter(Boolean);
      }
      var timeout = parseInt(fv(body, "qvq-cf-timeout"), 10);
      if (timeout > 0) entry.timeout = timeout;
      api("/api/qvq/mcp/save", "POST", entry).then(function (r) {
        if (r && r.error) toast(r.error, true);
        else toast(t("saved"));
        closeModal();
        loadMcp();
      });
    });
    var body = el("qvq-modal-body");
    var syncTransport = function () {
      var isHttp = body.querySelector("#qvq-cf-transport").value === "http";
      body.querySelector("#qvq-cf-stdio").style.display = isHttp ? "none" : "";
      body.querySelector("#qvq-cf-http").style.display = isHttp ? "" : "none";
    };
    body.querySelector("#qvq-cf-transport").onchange = syncTransport;
    if (isEdit) {
      body.querySelector("#qvq-cf-name").value = server.name || "";
      body.querySelector("#qvq-cf-transport").value = server.transport === "http" ? "http" : "stdio";
      body.querySelector("#qvq-cf-command").value = server.command || "";
      body.querySelector("#qvq-cf-args").value = (server.args || []).join("\n");
      body.querySelector("#qvq-cf-url").value = server.url || "";
      if (server.headers) body.querySelector("#qvq-cf-headers").value = JSON.stringify(server.headers, null, 2);
      if (server.timeout) body.querySelector("#qvq-cf-timeout").value = server.timeout;
    }
    syncTransport();
  }

  function loadTasks() {
    api("/api/qvq/tasks").then(function (data) {
      var tasks = (data && data.tasks) || [];
      if (!tasks.length) {
        el("qvq-tasks-list").innerHTML = '<div class="qvq-empty">' + esc(t("tasks_empty")) + "</div>";
        return;
      }
      var rows = tasks.map(function (task) {
        return "<tr><td><b>" + esc(task.name) + "</b><div class='qvq-tool-desc'>[" + esc(task.id) + "] " + esc(task.managed_by || "") + "</div></td>" +
          "<td>" + esc(task.schedule_raw) + "<div class='qvq-tool-desc'>" + esc(task.next_formatted || "") + "</div></td>" +
          "<td>" + esc(task.platform) + "/" + esc(task.target_type) + "/" + esc(task.target_id) + "</td>" +
          "<td>" + esc((task.prompt || "").slice(0, 60)) + "</td>" +
          "<td><button class='qvq-btn small danger' data-id='" + esc(task.id) + "'>" + esc(t("del")) + "</button></td></tr>";
      }).join("");
      el("qvq-tasks-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("models_name")) + "</th><th>" +
        esc(t("col_schedule")) + "</th><th>" + esc(t("col_target")) + "</th><th>" + esc(t("col_prompt")) + "</th><th>" +
        esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      el("qvq-tasks-list").querySelectorAll("button[data-id]").forEach(function (btn) {
        btn.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/tasks/delete", "POST", { id: btn.getAttribute("data-id") }).then(function () { toast(t("deleted")); loadTasks(); });
          });
        };
      });
    });
  }

  function loadMemoryScopes() {
    api("/api/qvq/memory").then(function (data) {
      var scopes = (data && data.scopes) || [];
      currentMemoryScope = "";
      el("qvq-memory-entries").innerHTML = '<div class="qvq-empty">' + esc(t("memory_pick")) + "</div>";
      if (!scopes.length) {
        el("qvq-memory-scopes").innerHTML = '<div class="qvq-empty">' + esc(t("memory_empty")) + "</div>";
        return;
      }
      el("qvq-memory-scopes").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("col_chatkey")) + "</th><th>" + esc(t("col_count")) + "</th></tr></thead><tbody>" +
        scopes.map(function (scope) {
          return "<tr style='cursor:pointer' data-scope='" + esc(scope.chat_key) + "'><td>" + esc(scope.chat_key) + "</td><td>" + esc(scope.count) + "</td></tr>";
        }).join("") + "</tbody></table>";
      el("qvq-memory-scopes").querySelectorAll("tr[data-scope]").forEach(function (row) {
        row.onclick = function () { loadMemoryEntries(row.getAttribute("data-scope")); };
      });
    });
  }

  function loadMemoryEntries(chatKey) {
    currentMemoryScope = chatKey;
    api("/api/qvq/memory?chat_key=" + encodeURIComponent(chatKey)).then(function (data) {
      var entries = (data && data.entries) || [];
      var body = entries.length
        ? "<table class='qvq-table'><tbody>" + entries.map(function (entry) {
            return "<tr><td>[" + esc(entry.category) + "/" + esc(entry.importance) + "] " + esc(entry.content) +
              " <button class='qvq-btn small danger' data-content='" + esc(entry.content) + "'><svg viewBox='0 0 24 24' class='qvq-btn-ico'><path d='M6 6l12 12M18 6L6 18'/></svg></button></td></tr>";
          }).join("") + "</tbody></table>"
        : '<div class="qvq-empty">' + esc(t("memory_empty")) + "</div>";
      el("qvq-memory-entries").innerHTML =
        "<h3 class='qvq-card-title'>" + esc(chatKey) +
        " <button class='qvq-btn small danger' id='qvq-memory-clear'>" + esc(t("memory_clear")) + "</button></h3>" + body;
      var clear = el("qvq-memory-clear");
      if (clear) {
        clear.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/memory/delete", "POST", { chat_key: chatKey }).then(function () { toast(t("deleted")); loadMemoryScopes(); });
          });
        };
      }
      el("qvq-memory-entries").querySelectorAll("button[data-content]").forEach(function (btn) {
        btn.onclick = function () {
          api("/api/qvq/memory/delete", "POST", { chat_key: chatKey, content: btn.getAttribute("data-content") }).then(function () {
            toast(t("deleted"));
            loadMemoryEntries(chatKey);
          });
        };
      });
    });
  }

  function loadSessions() {
    api("/api/qvq/sessions").then(function (data) {
      var sessions = (data && data.sessions) || [];
      if (!sessions.length) {
        el("qvq-sessions-list").innerHTML = '<div class="qvq-empty">' + esc(t("sessions_empty")) + "</div>";
        return;
      }
      var rows = sessions.map(function (session) {
        return "<tr><td><b>" + esc(sessionDisplayName(session)) + "</b><div class='qvq-tool-desc'>" + esc(session.chat_key) + "</div></td>" +
          "<td>" + esc(session.persona || "-") + "</td>" +
          "<td>" + esc(session.turns) + "</td><td class='qvq-tool-desc'>" + esc(session.preview || "-") + "</td>" +
          "<td class='qvq-col-time'>" + esc(fmtTime(session.updated)) + "</td>" +
          "<td><button class='qvq-btn small ghost' data-view='" + esc(session.chat_key) + "'>" + esc(t("sessions_msgs")) + "</button> " +
          "<button class='qvq-btn small danger' data-key='" + esc(session.chat_key) + "'>" + esc(t("reset_btn")) + "</button></td></tr>";
      }).join("");
      el("qvq-sessions-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("col_chatkey")) + "</th><th>" + esc(t("col_persona")) +
        "</th><th>" + esc(t("col_turns")) + "</th><th>" + esc(t("col_preview")) + "</th><th>" + esc(t("col_updated")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      el("qvq-sessions-list").querySelectorAll("button[data-key]").forEach(function (btn) {
        btn.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/sessions/reset", "POST", { chat_key: btn.getAttribute("data-key") }).then(function () { toast(t("saved")); loadSessions(); });
          });
        };
      });
      el("qvq-sessions-list").querySelectorAll("button[data-view]").forEach(function (btn) {
        btn.onclick = function () { showSessionMessages(btn.getAttribute("data-view")); };
      });
    });
  }

  function showSessionMessages(chatKey) {
    api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(chatKey)).then(function (data) {
      var msgs = (data && data.messages) || [];
      var summary = (data && data.summary) || "";
      var rows = [];
      if (summary) {
        rows.push('<details class="qvq-smsg summary"><summary>' + esc(t("session_summary")) +
          "</summary><div class='content'>" + esc(summary) + "</div></details>");
      }
      var count = 0;
      msgs.forEach(function (m, i) {
        if (!m || typeof m !== "object") return;
        count++;
        var role = m.role || "user";
        var raw = contentText(m.content);
        var ops = '<div class="ops">' +
          '<button class="qvq-btn small ghost" data-copy="' + i + '">' + esc(t("copy")) + "</button>" +
          '<button class="qvq-btn small ghost" data-edit="' + i + '">' + esc(t("edit")) + "</button>" +
          '<button class="qvq-btn small danger" data-del="' + i + '">' + esc(t("del")) + "</button></div>";
        if (role === "user") {
          rows.push('<div class="qvq-smsg me"><div class="content">' + esc(raw) + "</div>" + ops + "</div>");
        } else if (role === "assistant") {
          var serial = m.rounds && m.rounds.length ? '<div class="qvq-rounds">' + renderSerial(roundsToItems(m.rounds)) + "</div>" : "";
          if (!serial) {
            var steps = traceToSteps(m.trace);
            serial = steps && steps.length ? '<div class="qvq-steps">' + steps.map(function (st) {
              var ms2 = st.end && st.end.ms != null ? (st.end.ms >= 1000 ? (st.end.ms / 1000).toFixed(1) + "s" : st.end.ms + "ms") : "";
              return '<div class="qvq-step"><div class="qvq-step-row" data-step-toggle="1"><span class="qvq-step-ico">' + STEP_ICON_SVG + "</span>" +
                '<span class="qvq-step-name">' + esc(st.start.name) + '</span><span class="qvq-step-args">' +
                esc(String(st.start.arguments || "").replace(/\s+/g, " ").slice(0, 60)) + '</span><span class="qvq-step-ms">' + esc(ms2) + "</span></div>" +
                (st.end && st.end.output ? '<pre class="qvq-step-detail">' + esc(st.end.output) + "</pre>" : "") + "</div>";
            }).join("") + "</div>" : "";
          }
          rows.push('<div class="qvq-smsg bot"><div class="role-tag">AI</div>' + serial + '<div class="content">' +
            (mdRender(raw) || esc(raw)) + "</div>" + ops + "</div>");
        } else {
          rows.push('<details class="qvq-smsg ctx"><summary>' + esc(role) + " · " + raw.length + " chars</summary><pre>" +
            esc(raw) + "</pre>" + ops + "</details>");
        }
      });
      var head = '<div class="qvq-smsg-head">' + esc(chatKey) + " · " +
        esc(t("msgs_count").replace("{n}", String(count))) + "</div>";
      var html = head + (rows.join("") || '<div class="qvq-empty">' + esc(t("sessions_empty")) + "</div>");
      openModal(chatKey, html);
      var body = el("qvq-modal-body");
      bindMdCopy(body);
      bindStepToggles(body);
      body.querySelectorAll("button[data-copy]").forEach(function (btn) {
        btn.onclick = function () {
          var m = msgs[parseInt(btn.getAttribute("data-copy"), 10)];
          if (!m) return;
          copyText(contentText(m.content));
          var old = btn.textContent;
          btn.textContent = t("copied");
          setTimeout(function () { btn.textContent = old; }, 1200);
        };
      });
      body.querySelectorAll("button[data-del]").forEach(function (btn) {
        btn.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/session/messages/delete", "POST", { chat_key: chatKey, index: parseInt(btn.getAttribute("data-del"), 10) }).then(function () {
              showSessionMessages(chatKey);
              if (chatKey === chatSession) loadChatHistory();
            });
          });
        };
      });
      body.querySelectorAll("button[data-edit]").forEach(function (btn) {
        btn.onclick = function () {
          var idx = parseInt(btn.getAttribute("data-edit"), 10);
          var m = msgs[idx];
          var wrap = btn.closest(".qvq-smsg");
          if (!m || !wrap) return;
          var content = wrap.querySelector(".content, pre");
          if (!content) return;
          content.style.display = "none";
          btn.style.display = "none";
          wrap.querySelector(".ops").insertAdjacentHTML("afterbegin",
            "<textarea class='qvq-textarea' rows='3'>" + esc(contentText(m.content)) + "</textarea>" +
            "<button class='qvq-btn small' data-save='1'>" + esc(t("save")) + "</button>");
          wrap.querySelector("button[data-save]").onclick = function () {
            var val = wrap.querySelector("textarea").value;
            api("/api/qvq/session/context/edit", "POST", { chat_key: chatKey, index: idx, content: val }).then(function () {
              toast(t("saved"));
              showSessionMessages(chatKey);
              if (chatKey === chatSession) loadChatHistory();
            });
          };
        };
      });
    });
  }

  var AUDIT_SUMMARY_KEYS = ["command", "code", "path", "file", "action", "query", "content", "name", "endpoint", "tool", "error"];

  function auditSummary(entry) {
    var d = entry.detail;
    if (d == null) return "-";
    if (typeof d === "string") return d.slice(0, 200);
    if (typeof d !== "object") return String(d);
    for (var i = 0; i < AUDIT_SUMMARY_KEYS.length; i++) {
      var v = d[AUDIT_SUMMARY_KEYS[i]];
      if (v != null && v !== "") {
        var s = AUDIT_SUMMARY_KEYS[i] + ": " + (typeof v === "object" ? JSON.stringify(v) : String(v));
        return s.length > 200 ? s.slice(0, 200) + "…" : s;
      }
    }
    var first = "";
    Object.keys(d).some(function (k) {
      var v2 = d[k];
      if (v2 != null && v2 !== "") {
        first = k + ": " + (typeof v2 === "object" ? JSON.stringify(v2) : String(v2));
        return true;
      }
      return false;
    });
    if (first.length > 200) first = first.slice(0, 200) + "…";
    return first || "-";
  }

  function showAuditModal(entry) {
    var detail = entry.detail;
    var jsonText;
    try {
      jsonText = typeof detail === "string" ? detail : JSON.stringify(detail == null ? {} : detail, null, 2);
    } catch (e) {
      jsonText = String(detail);
    }
    var html =
      "<div class='qvq-kv'>" +
      "<div class='k'>" + esc(t("col_time")) + "</div><div class='v'>" + esc(fmtTimeFull(entry.ts)) + "</div>" +
      "<div class='k'>" + esc(t("col_tool")) + "</div><div class='v'><b>" + esc(entry.tool) + "</b></div>" +
      "<div class='k'>" + esc(t("col_user")) + "</div><div class='v'>" + esc(entry.user_id || "-") + "</div>" +
      "<div class='k'>" + esc(t("col_origin")) + "</div><div class='v'>" + esc(entry.origin || "-") + "</div>" +
      "<div class='k'>" + esc(t("col_chatkey")) + "</div><div class='v'>" + esc(entry.chat_key || "-") + "</div>" +
      "</div>" +
      "<pre class='qvq-json'>" + esc(jsonText) + "</pre>" +
      "<div class='qvq-actions'><button class='qvq-btn small' id='qvq-audit-copy'>" + esc(t("audit_copy")) + "</button></div>";
    openModal(t("col_detail") + " · " + (entry.tool || ""), html);
    el("qvq-audit-copy").onclick = function () {
      var text = typeof detail === "string" ? detail : JSON.stringify(detail == null ? {} : detail, null, 2);
      var done = function () { toast(t("audit_copied")); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
        done();
      }
    };
  }

  function loadAudit() {
    api("/api/qvq/audit?limit=500").then(function (data) {
      var entries = (data && data.entries) || [];
      var filter = el("qvq-audit-filter");
      var tools = {};
      var users = {};
      var last24 = 0;
      var cutoff = Date.now() / 1000 - 86400;
      entries.forEach(function (e) {
        if (e.tool) tools[e.tool] = (tools[e.tool] || 0) + 1;
        if (e.user_id) users[e.user_id] = (users[e.user_id] || 0) + 1;
        if ((e.ts || 0) >= cutoff) last24++;
      });
      var cards = [
        { cap: t("audit_total"), num: entries.length },
        { cap: t("audit_tools_n"), num: Object.keys(tools).length },
        { cap: t("audit_users_n"), num: Object.keys(users).length },
        { cap: t("audit_last24h"), num: last24 }
      ];
      el("qvq-audit-stats").innerHTML = cards.map(function (c) {
        return '<div class="qvq-stat"><div class="num">' + esc(c.num) + '</div><div class="cap">' + esc(c.cap) + "</div></div>";
      }).join("");
      var render = function (keyword) {
        var shown = entries.filter(function (e) {
          if (!keyword) return true;
          return (e.tool || "").toLowerCase().indexOf(keyword) >= 0 ||
            (e.user_id || "").indexOf(keyword) >= 0 ||
            (e.origin || "").toLowerCase().indexOf(keyword) >= 0 ||
            JSON.stringify(e.detail || {}).toLowerCase().indexOf(keyword) >= 0;
        });
        if (!shown.length) {
          el("qvq-audit-list").innerHTML = '<div class="qvq-empty">' + esc(t("audit_empty")) + "</div>";
          return;
        }
        var rows = shown.map(function (entry, idx) {
          return "<tr class='qvq-audit-row' data-idx='" + idx + "'>" +
            "<td class='qvq-col-time'>" + esc(fmtTime(entry.ts)) + "</td>" +
            "<td><b>" + esc(entry.tool) + "</b></td>" +
            "<td>" + esc(entry.user_id || "-") + "</td>" +
            "<td>" + esc(entry.origin || "-") + "</td>" +
            "<td class='qvq-tool-desc qvq-audit-detail'>" + esc(auditSummary(entry)) + "</td></tr>";
        }).join("");
        el("qvq-audit-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("col_time")) + "</th><th>" + esc(t("col_tool")) +
          "</th><th>" + esc(t("col_user")) + "</th><th>" + esc(t("col_origin")) + "</th><th>" + esc(t("col_detail")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
        el("qvq-audit-list").querySelectorAll("tr.qvq-audit-row").forEach(function (tr) {
          tr.onclick = function () {
            var entry = shown[parseInt(tr.getAttribute("data-idx"), 10)];
            if (entry) showAuditModal(entry);
          };
        });
      };
      filter.oninput = function () { render(filter.value.trim().toLowerCase()); };
      render(filter.value.trim().toLowerCase());
    });
  }

  var settingsFields = [];

  function loadSettings() {
    api("/api/qvq/config").then(function (data) {
      settingsFields = (data && data.fields) || [];
      renderSettingsCategories();
      renderSettingsForm();
      syncUsageChart();
    });
  }

  function settingsGroups() {
    var groups = [];
    settingsFields.forEach(function (f) {
      if (groups.indexOf(f.group) < 0) groups.push(f.group);
    });
    groups.sort(function (a, b) {
      function first(g) {
        var f = settingsFields.filter(function (x) { return x.group === g; })[0] || {};
        return f.order || 99;
      }
      return first(a) - first(b);
    });
    return groups;
  }

  function renderSettingsCategories() {
    var nav = el("qvq-settings-cats");
    var groups = settingsGroups();
    if (!currentCategory || groups.indexOf(currentCategory) < 0) currentCategory = groups[0] || "";
    nav.innerHTML = groups.map(function (g) {
      var label = t("group_" + g);
      if (label === "group_" + g) label = g;
      return "<button class='qvq-cat-btn" + (g === currentCategory ? " active" : "") + "' data-cat='" + esc(g) + "'>" + esc(label) + "</button>";
    }).join("");
    nav.querySelectorAll("button[data-cat]").forEach(function (btn) {
      btn.onclick = function () {
        currentCategory = btn.getAttribute("data-cat");
        renderSettingsCategories();
        renderSettingsForm();
        syncUsageChart();
      };
    });
  }

  function settingField(f) {
    var value = f.value;
    var input;
    if (f.widget === "lines") {
      var lines = Array.isArray(value) ? value.join("\n") : String(value == null ? "" : value);
      input = "<textarea class='qvq-textarea' style='min-height:80px' data-key='" + esc(f.key) + "' data-lines='1' placeholder='line1&#10;line2'>" + esc(lines) + "</textarea>";
    } else if (f.widget === "select" && f.options && f.options.length) {
      input = "<select class='qvq-select' data-key='" + esc(f.key) + "'>" + f.options.map(function (o) {
        return "<option value='" + esc(o) + "'" + (o === value ? " selected" : "") + ">" + esc(o) + "</option>";
      }).join("") + "</select>";
    } else if (typeof value === "boolean" || f.widget === "switch") {
      input = "<span class='qvq-switch'><input type='checkbox' data-key='" + esc(f.key) + "' data-switch='1'" + (value ? " checked" : "") + "/><i></i></span>";
    } else if (Array.isArray(value) || (value && typeof value === "object")) {
      input = "<textarea class='qvq-textarea' style='min-height:60px' data-key='" + esc(f.key) + "' data-json='1'>" + esc(JSON.stringify(value)) + "</textarea>";
    } else {
      input = "<input class='qvq-input' data-key='" + esc(f.key) + "' value='" + esc(value == null ? "" : value) + "' />";
    }
    return "<label class='qvq-label'>" + esc(f.description || f.key) +
      " <span style='color:var(--qvq-tx-t);font-weight:400'>(" + esc(f.key) + ")</span></label>" + input;
  }

  function renderSettingsForm() {
    var fields = settingsFields.filter(function (f) { return f.group === currentCategory; });
    fields.sort(function (a, b) { return (a.order || 99) - (b.order || 99); });
    el("qvq-settings-form").innerHTML = fields.map(settingField).join("") || '<div class="qvq-empty">-</div>';
  }

  function syncUsageChart() {
    var card = el("qvq-usage-card");
    if (!card) return;
    var show = currentCategory === "usage";
    card.style.display = show ? "" : "none";
    if (show) {
      api("/api/qvq/usage").then(function (data) {
        renderUsageChart(data || {}, "qvq-usage-chart");
      });
    }
  }

  function renderUsageChart(data, boxId) {
    var box = el(boxId || "qvq-usage-chart");
    if (!box) return;
    var days = data.days || [];
    var limit = data.limit || 0;
    var tokens = days.map(function (d) { return d.tokens || 0; });
    var calls = days.map(function (d) { return d.calls || 0; });
    var sum = function (arr) { return arr.reduce(function (a, b) { return a + b; }, 0); };
    var totalTokens = sum(tokens);
    var totalCalls = sum(calls);
    if (!totalTokens && !totalCalls) {
      box.innerHTML = '<div class="qvq-empty">' + esc(t("usage_empty")) + "</div>";
      return;
    }
    var W = 700, H = 170, padX = 4, top = 10, bottom = 46;
    var plotH = H - top - bottom;
    var n = days.length || 1;
    var maxTokens = Math.max.apply(null, tokens.concat([limit])) || 1;
    var maxCalls = Math.max.apply(null, calls) || 1;
    var x = function (i) { return n > 1 ? padX + (W - padX * 2) * (i / (n - 1)) : W / 2; };
    var yTok = function (v) { return top + plotH - (v / maxTokens) * plotH; };
    var barW = Math.max(6, (W - padX * 2) / n * 0.42);
    var barH = function (v) { return (v / maxCalls) * (plotH * 0.34); };

    var grid = "";
    [0.25, 0.5, 0.75].forEach(function (r) {
      var y = top + plotH * r;
      grid += "<line class='qvq-chart-grid' x1='0' y1='" + y + "' x2='" + W + "' y2='" + y + "' />";
    });

    var bars = calls.map(function (c, i) {
      if (!c) return "";
      var h = barH(c);
      return "<rect class='qvq-chart-calls' x='" + (x(i) - barW / 2) + "' y='" + (top + plotH - h) +
        "' width='" + barW + "' height='" + h + "' rx='2' />";
    }).join("");

    var points = tokens.map(function (v, i) { return x(i) + "," + yTok(v); });
    var area = "M" + points.join(" L") + " L" + x(n - 1) + "," + (top + plotH) + " L" + x(0) + "," + (top + plotH) + " Z";
    var line = "M" + points.join(" L");
    var limitLine = "";
    if (limit && limit <= maxTokens) {
      var ly = yTok(limit);
      limitLine = "<line class='qvq-chart-limit' x1='0' y1='" + ly + "' x2='" + W + "' y2='" + ly + "' />";
    }

    var axis = days.length
      ? [0, Math.floor((days.length - 1) / 3), Math.floor((days.length - 1) * 2 / 3), days.length - 1].map(function (i) {
        var d = days[i];
        return "<span>" + esc(d && d.date ? d.date.slice(5) : "") + "</span>";
      }).join("")
      : "";

    var today = tokens.length ? tokens[tokens.length - 1] : 0;
    var todayCalls = calls.length ? calls[calls.length - 1] : 0;
    var legend =
      "<div class='qvq-chart-legend'>" +
      "<span><i class='dot-line'></i>" + esc(t("usage_total")) + " <b>" + esc(totalTokens) + "</b> " + esc(t("usage_tokens")) + "</span>" +
      "<span><i class='dot-calls'></i>" + esc(t("usage_calls")) + " <b>" + esc(totalCalls) + "</b></span>" +
      "<span>" + esc(t("usage_avg")) + " <b>" + esc(Math.round(totalTokens / (days.length || 1))) + "</b></span>" +
      "<span>" + esc(t("usage_today")) + " <b>" + esc(today) + "</b> " + esc(t("usage_tokens")) + " / <b>" + esc(todayCalls) + "</b> " + esc(t("usage_calls")) + "</span>" +
      (limit ? "<span>" + esc(t("usage_limit")) + " <b>" + esc(limit) + "</b></span>" : "") +
      "</div>";

    var step = W / n;
    var hits = days.map(function (d, i) {
      return "<rect class='qvq-chart-hit' data-i='" + i + "' x='" + (i * step) + "' y='0' width='" + step + "' height='" + H + "' />";
    }).join("");

    box.innerHTML = legend +
      "<div class='qvq-chart-wrap'>" +
      "<svg class='qvq-chart' viewBox='0 0 " + W + " " + H + "' preserveAspectRatio='none' role='img'>" +
      grid + bars +
      "<path class='qvq-chart-area' d='" + area + "' />" +
      "<path class='qvq-chart-line' d='" + line + "' />" +
      limitLine +
      "<line class='qvq-chart-cross' y1='" + top + "' y2='" + (top + plotH) + "' x1='0' x2='0' />" +
      "<circle class='qvq-chart-dot' r='4' cx='0' cy='0' />" +
      hits +
      "</svg>" +
      "<div class='qvq-chart-tip'></div>" +
      "</div>" +
      "<div class='qvq-chart-axis'>" + axis + "</div>";

    var wrapEl = box.querySelector(".qvq-chart-wrap");
    var svgEl = wrapEl.querySelector(".qvq-chart");
    var crossEl = wrapEl.querySelector(".qvq-chart-cross");
    var dotEl = wrapEl.querySelector(".qvq-chart-dot");
    var tipEl = wrapEl.querySelector(".qvq-chart-tip");
    var hideTip = function () {
      tipEl.classList.remove("show");
      crossEl.style.opacity = 0;
      dotEl.style.opacity = 0;
    };
    svgEl.addEventListener("mousemove", function (ev) {
      var rect = svgEl.getBoundingClientRect();
      var ratio = rect.width ? (ev.clientX - rect.left) / rect.width : 0;
      var i = Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1))));
      var d = days[i];
      if (!d) { hideTip(); return; }
      var vx = x(i);
      var vy = yTok(tokens[i]);
      crossEl.setAttribute("x1", vx);
      crossEl.setAttribute("x2", vx);
      crossEl.style.opacity = 1;
      dotEl.setAttribute("cx", vx);
      dotEl.setAttribute("cy", vy);
      dotEl.style.opacity = 1;
      var px = (vx / W) * rect.width;
      var py = (vy / H) * rect.height;
      var pct = limit && (d.tokens || 0) ? Math.round(((d.tokens || 0) / limit) * 100) + "% " + t("usage_limit") : "";
      tipEl.innerHTML = "<div class='d'>" + esc(d.date || "") + "</div>" +
        esc(t("usage_tokens")) + " <b>" + esc(d.tokens || 0) + "</b><br>" +
        esc(t("usage_calls")) + " <b>" + esc(d.calls || 0) + "</b>" +
        (pct ? "<br>" + esc(pct) : "");
      tipEl.style.left = Math.max(75, Math.min(rect.width - 75, px)) + "px";
      tipEl.style.top = Math.max(10, py) + "px";
      tipEl.classList.add("show");
    });
    svgEl.addEventListener("mouseleave", hideTip);
  }

  function saveSettings() {
    var payload = {};
    el("qvq-settings-form").querySelectorAll("[data-key]").forEach(function (node) {
      var key = node.getAttribute("data-key");
      if (node.getAttribute("data-switch")) {
        payload[key] = node.checked;
        return;
      }
      var raw = node.value;
      if (node.getAttribute("data-lines")) {
        payload[key] = raw.split("\n").map(function (s) { return s.trim(); }).filter(Boolean);
      } else if (node.getAttribute("data-json")) {
        try { payload[key] = JSON.parse(raw); } catch (e) { payload[key] = raw; }
      } else if (raw === "true") {
        payload[key] = true;
      } else if (raw === "false") {
        payload[key] = false;
      } else if (raw !== "" && /^-?\d+(\.\d+)?$/.test(raw)) {
        payload[key] = parseFloat(raw);
      } else {
        payload[key] = raw;
      }
    });
    api("/api/qvq/config", "POST", payload).then(function () {
      toast(t("settings_saved"));
      loadSettings();
    });
  }

  function showLogin() {
    var box = el("qvq-login");
    if (box) box.style.display = "flex";
  }

  function hideLogin() {
    var box = el("qvq-login");
    if (box) box.style.display = "none";
  }

  function tryLogin() {
    var input = el("qvq-login-token");
    var token = input.value.trim();
    if (!token) return;
    authWith(token).then(function (ok) {
      if (ok) {
        activeToken = token;
        try { localStorage.setItem("qvq_token", token); } catch (e) {}
        hideLogin();
        el("qvq-login-err").textContent = "";
        initApp();
      } else {
        el("qvq-login-err").textContent = t("login_failed");
      }
    });
  }

  function initApp() {
    if (window.__qvq_inited__) return;
    window.__qvq_inited__ = true;
    applyI18n();

    var chatInput = el("qvq-chat-input");
    el("qvq-chat-send").onclick = function () {
      if (chatBusy) { cancelChat(); return; }
      sendChat();
    };
    chatInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChat();
      }
    });
    chatInput.addEventListener("input", function () {
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
    });
    chatInput.addEventListener("paste", function (e) {
      try {
        var items = (e.clipboardData && e.clipboardData.items) || [];
        var files = [];
        for (var i = 0; i < items.length; i++) {
          if (items[i].kind === "file") {
            var f = items[i].getAsFile();
            if (f && /^image\//.test(f.type)) files.push(f);
          }
        }
        if (files.length) {
          e.preventDefault();
          handleFiles(files);
          toast(t("chat_pasted") + " " + files.length);
        }
      } catch (err) {}
    });
    el("qvq-chat-attach-btn").onclick = function () { el("qvq-chat-file").click(); };
    el("qvq-chat-file").onchange = function () {
      handleFiles(this.files);
      this.value = "";
    };
    var newBtn = el("qvq-chat-new");
    if (newBtn) newBtn.onclick = function () { newChat(); };
    el("qvq-chat-persona").onchange = function () {
      chatPersona = this.value;
      try {
        if (chatPersona) localStorage.setItem("qvq_chat_persona", chatPersona);
        else localStorage.removeItem("qvq_chat_persona");
      } catch (e) {}
    };
    var densitySel = el("qvq-chat-density");
    if (densitySel) {
      densitySel.value = chatDensity;
      densitySel.onchange = function () {
        chatDensity = this.value;
        try { localStorage.setItem("qvq_chat_density", chatDensity); } catch (e) {}
        renderChat();
      };
    }
    var mmBtn = el("qvq-chat-mm");
    if (mmBtn) mmBtn.onclick = function (e) { e.stopPropagation(); toggleMmMenu(); };
    var mentionBtn = el("qvq-chat-mention");
    if (mentionBtn) mentionBtn.onclick = function (e) { e.stopPropagation(); toggleMentionMenu(); };
    startChatSync();
    var settingsBtn = el("qvq-chat-settings");
    if (settingsBtn) settingsBtn.onclick = openSessionSettings;
    var shareBtn = el("qvq-chat-share");
    if (shareBtn) shareBtn.onclick = openShareModal;
    el("qvq-modal-close").onclick = closeModal;
    el("qvq-modal-mask").onclick = closeModal;
    document.addEventListener("click", function () { closeAllMenus(); });
    enhanceSelects();
    // auth 完成后重跑当前页 loader：修复 auth 前点击导致的数据 401 空列表
    var activeNav = el("qvq-nav").querySelector(".qvq-nav-btn.active");
    if (activeNav) switchTab(activeNav.getAttribute("data-tab"));
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && el("qvq-modal").style.display !== "none") closeModal();
    });
    el("qvq-model-add").onclick = function () { openModelModal(null); };
    el("qvq-persona-add").onclick = function () { openPersonaModal(null); };
    el("qvq-skill-add").onclick = function () { openSkillModal(null); };
    el("qvq-mcp-add").onclick = function () { openMcpModal(null); };
    el("qvq-skill-export").onclick = function () {
      api("/api/qvq/skills/export").then(function (data) {
        var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "qvqchat-skills-" + new Date().toISOString().slice(0, 10) + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
      });
    };
    el("qvq-skill-import").onclick = function () { el("qvq-skill-file").click(); };
    el("qvq-skill-file").onchange = function () {
      var file = this.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var data;
        try { data = JSON.parse(reader.result); } catch (e) { toast("invalid json", true); return; }
        var skills = (data && data.skills) || [];
        if (!skills.length) {
          toast(t("skills_empty"), true);
          return;
        }
        var chain = Promise.resolve();
        skills.forEach(function (sk) {
          if (!sk || !sk.name) return;
          chain = chain.then(function () {
            return api("/api/qvq/skills/save", "POST", { name: sk.name, description: sk.description || "", body: sk.body || "" });
          });
        });
        chain.then(function () {
          toast(t("saved"));
          loadSkills();
        });
      };
      reader.readAsText(file);
      this.value = "";
    };
    el("qvq-tools-refresh").onclick = function () {
      api("/api/qvq/tools/refresh", "POST", {}).then(function (data) {
        var info = (data && data.info) || {};
        toast("eco: " + (info.modules || 0) + " → " + (info.tools || 0));
        loadTools();
      });
    };
    el("qvq-settings-save").onclick = saveSettings;
    el("qvq-mcp-connect-all").onclick = function () {
      api("/api/qvq/mcp").then(function (data) {
        var names = ((data && data.servers) || []).map(function (s) { return s.name; });
        var chain = Promise.resolve();
        names.forEach(function (name) {
          chain = chain.then(function () {
            return api("/api/qvq/mcp/connect", "POST", { name: name });
          });
        });
        chain.then(function () { loadMcp(); });
      });
    };
    el("qvq-backup-export").onclick = function () {
      api("/api/qvq/export").then(function (data) {
        var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "qvqchat-backup-" + new Date().toISOString().slice(0, 10) + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
      });
    };
    el("qvq-backup-import").onclick = function () { el("qvq-backup-file").click(); };
    el("qvq-backup-file").onchange = function () {
      var file = this.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var data;
        try { data = JSON.parse(reader.result); } catch (e) { toast("invalid json", true); return; }
        api("/api/qvq/import", "POST", { data: data }).then(function (r) {
          toast(r && r.ok ? t("saved") + ": " + (r.applied || []).join(", ") : ((r && r.error) || "error"), !(r && r.ok));
        });
      };
      reader.readAsText(file);
      this.value = "";
    };
    renderChat();
    loadOverview();
  }

  window.loadQvQChatView = function () {
    resolveToken().then(function (tk) {
      if (tk) {
        activeToken = tk;
        hideLogin();
        initApp();
      } else {
        showLogin();
      }
    });
  };

  var loginBtn = el("qvq-login-btn");
  var loginInput = el("qvq-login-token");
  if (loginBtn) loginBtn.onclick = tryLogin;
  if (loginInput) {
    loginInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") tryLogin();
    });
  }
  window.loadQvQChatView();
})();
