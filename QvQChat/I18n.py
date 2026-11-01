from __future__ import annotations

from ErisPulse.Core.Bases import BaseI18n, I18nKey


def _key(zh: str, tw: str, en: str, ja: str, ru: str) -> I18nKey:
    return I18nKey(default=en, zh_CN=zh, zh_TW=tw, en=en, ja=ja, ru=ru)


class QvQI18n(BaseI18n):

    default_model = _key("默认模型（模型池 id），留空使用池中第一个", "預設模型（模型池 id），留空使用池中第一個", "Default model id from the pool, empty for the first one", "デフォルトモデル（プールの id）。空欄で最初のモデルを使用", "Модель по умолчанию (id из пула), пусто — первая в пуле")
    temperature = _key("默认采样温度", "預設取樣溫度", "Default sampling temperature", "デフォルトのサンプリング温度", "Температура сэмплирования по умолчанию")
    max_tokens = _key(
        "单次回复的最大生成 token 数，0 = 不限制（跟随模型上限）。长任务建议保持 0，截断会导致规划文本泄漏。",
        "單次回覆的最大生成 token 數，0 = 不限制（跟隨模型上限）。長任務建議保持 0，截斷會導致規劃文本洩漏。",
        "Max generation tokens per reply; 0 = unlimited (model default). Keep 0 for long tasks — truncation leaks planning text.",
        "1 回答の最大生成トークン数。0 = 無制限（モデル上限）。長いタスクでは 0 推奨。途切れると計画テキストが漏れます。",
        "Максимум токенов на ответ; 0 = без лимита (по модели). Для длинных задач держите 0 — обрыв приводит к утечке текста планирования.",
    )
    model_failover = _key("模型调用失败时按池顺序切换备用模型", "模型呼叫失敗時按池順序切換備用模型", "Fail over to next pool model on failure", "呼び出し失敗時にプール内の次のモデルへ切替", "При сбое переключаться на следующую модель пула")

    reply_private = _key("私聊消息触发智能体", "私聊訊息觸發智慧代理", "Trigger the agent on private messages", "私聊メッセージでエージェントを起動", "Запускать агента на личные сообщения")
    reply_at = _key("群聊被 @ 时触发智能体", "群聊被 @ 時觸發智慧代理", "Trigger the agent when mentioned in groups", "グループでメンションされた際に起動", "Запускать агента при упоминании в группах")
    wake_prefixes = _key("群聊文本唤醒前缀", "群聊文字喚醒前綴", "Group text wake prefixes", "グループのテキスト起床プレフィックス", "Префиксы пробуждения в группах")
    command_prefixes = _key("命令消息前缀（命中即放行不处理）", "命令訊息前綴（命中即放行不處理）", "Command prefixes passed through untouched", "コマンドプレフィックス（一致時は素通し）", "Префиксы команд (совпадение — пропустить)")

    trust_agent = _key("完全信任智能体：跳过所有危险操作确认（仍审计）", "完全信任智慧代理：跳過所有危險操作確認（仍審計）", "Fully trust the agent: skip all danger confirmations (still audited)", "エージェントを完全に信頼：危険操作の確認を全てスキップ（監査は記錄）", "Полностью доверять агенту: без подтверждений (аудит ведётся)")
    admins = _key("管理员用户 id 列表；为空时聊天侧无人拥有管理员权限（Dashboard/本地来源除外）", "管理員使用者 id 列表；為空時聊天側無人擁有管理員權限（Dashboard/本地來源除外）", "Admin user ids; when empty nobody has admin on chat (Dashboard/local excepted)", "管理者ユーザー id 一覧。空欄ではチャット側に管理者なし（Dashboard/ローカル除く）", "id администраторов; пусто — на уровне чата админов нет (кроме Dashboard/локально)")
    admin_tools = _key("仅管理员可用的工具（支持 eco_*/mcp_* 前缀通配）", "僅管理員可用的工具（支援 eco_*/mcp_* 前綴萬用）", "Tools restricted to admins (eco_*/mcp_* prefix wildcards allowed)", "管理者専用ツール（eco_*/mcp_* 接頭辞ワイルドカード可）", "Инструменты только для админов (префиксы eco_*/mcp_*)")
    safe_tools = _key("在基础安全集之外追加给所有人的工具（支持前缀通配，如让所有人可用生图扩展）", "在基礎安全集之外追加給所有人的工具（支援前綴萬用，如讓所有人可用生圖擴展）", "Extra tools allowed for everyone beyond the base safe set (prefix wildcards, e.g. the image extension)", "全員に追加許可するツール（接頭辞ワイルドカード可）", "Доп. инструменты для всех (префиксы-маски)")
    safe_commands = _key("非管理员也允许执行的简单命令（通配匹配，如 ping *）", "非管理員也允許執行的簡單命令（萬用匹配，如 ping *）", "Simple commands allowed for non-admins (wildcard, e.g. ping *)", "非管理者も実行可能な簡易コマンド（ワイルドカード）", "Простые команды для не-админов (маски, напр. ping *)")
    security_level = _key("电脑操作安全级别：strict 只读+确认 / standard 白名单+危险确认 / permissive 放开但审计", "電腦操作安全級別：strict 唯讀+確認 / standard 白名單+危險確認 / permissive 放開但審計", "Computer level: strict read-only+confirm / standard allowlist+confirm / permissive audited", "PC 操作の安全レベル：strict / standard / permissive", "Уровень доступа к ПК: strict / standard / permissive")
    work_dirs = _key("文件访问白名单目录，留空仅允许当前工作目录", "檔案存取白名單目錄，留空僅允許目前工作目錄", "Allowed file directories, empty for current working dir only", "ファイルアクセス許可ディレクトリ。空欄で作業ディレクトリのみ", "Разрешённые каталоги; пусто — только рабочая папка")
    command_timeout = _key("单条命令执行超时（秒）", "單條命令執行逾時（秒）", "Per-command timeout in seconds", "コマンドごとのタイムアウト（秒）", "Тайм-аут команды (сек)")
    blocked_patterns = _key("追加的命令黑名单正则", "追加的命令黑名單正則", "Extra blocked command regexes", "追加のブロック正規表現", "Доп. блокирующие регулярные выражения")
    confirm_timeout = _key("危险操作聊天内确认超时（秒）", "危險操作聊天內確認逾時（秒）", "In-chat confirmation timeout in seconds", "危険操作の確認タイムアウト（秒）", "Тайм-аут подтверждения (сек)")

    context_limit = _key("每会话携带对话上下文条数上限", "每會話攜帶對話上下文條數上限", "Max context messages per session", "セッションあたりのコンテキスト上限", "Лимит сообщений контекста на сессию")
    history_seed = _key("冷启动时从会话收件箱回填的历史条数", "冷啟動時從會話收件匣回填的歷史條數", "History entries seeded from the transcript inbox", "コールドスタート時に受信箱から補完する履歴数", "История из входящей ленты при холодном старте")
    forward_enabled = _key("长回复自动转为合并转发消息（需平台支持 Raw_ob12）", "長回覆自動轉為合併轉發訊息（需平台支援 Raw_ob12）", "Auto-convert long replies to forward messages (requires Raw_ob12 support)", "長い返信を転送メッセージへ自動変換（Raw_ob12 必須）", "Длинные ответы — пересылкой (нужен Raw_ob12)")
    forward_threshold = _key("任务类回复超过该字符数转为合并转发；纯对话需两倍长度（0 关闭）", "任務類回覆超過該字元數轉為合併轉發；純對話需兩倍長度（0 關閉）", "Task replies over this length become forward messages; plain chat needs double (0 disables)", "タスク系返信の変換閾値（会話は2倍、0 で無効）", "Порог для задач; обычный чат — вдвое больше (0 — выкл)")

    memory_max = _key("每会话长期记忆条数上限", "每會話長期記憶條數上限", "Max long-term memory entries per session", "セッションあたりの長期記憶上限", "Лимит долговременной памяти на сессию")
    memory_recall = _key("每次对话注入的相关记忆条数上限", "每次對話注入的相關記憶條數上限", "Max relevant memories injected per turn", "毎ターン注入する関連記憶の上限", "Лимит релевантных воспоминаний за ход")

    tool_timeout = _key("单次工具调用超时（秒）", "單次工具呼叫逾時（秒）", "Per tool-call timeout in seconds", "ツール呼び出しのタイムアウト（秒）", "Тайм-аут вызова инструмента (сек)")
    max_tool_rounds = _key("工具循环最大轮数", "工具循環最大輪數", "Max tool-loop rounds", "ツールループの最大回数", "Макс. раундов цикла инструментов")
    max_tool_calls = _key("单次对话工具调用总次数上限", "單次對話工具呼叫總次數上限", "Max total tool calls per conversation", "1 回の会話でのツール呼び出し上限", "Макс. вызовов инструментов за диалог")
    disabled_tools = _key("禁用的工具名列表（支持 eco_/mcp_ 前缀通配）", "停用的工具名列表（支援 eco_/mcp_ 前綴萬用）", "Disabled tool names, prefix wildcards allowed", "無効化ツール名一覧（eco_/mcp_ 接頭辞ワイルドカード可）", "Отключённые инструменты (допустимы префиксы eco_/mcp_)")

    eco_exclude = _key("不桥接服务目录的模块名单", "不橋接服務目錄的模組名單", "Modules excluded from the service bridge", "サービスブリッジから除外するモジュール", "Модули, исключённые из моста служб")
    eco_include = _key("仅桥接这些模块的服务，留空表示全部", "僅橋接這些模組的服務，留空表示全部", "Only bridge these modules, empty for all", "これらのモジュールのみブリッジ。空欄で全て", "Мостить только эти модули; пусто — все")

    mcp_timeout = _key("MCP 请求超时（秒）", "MCP 請求逾時（秒）", "MCP request timeout in seconds", "MCP リクエストのタイムアウト（秒）", "Тайм-аут запроса MCP (сек)")

    task_check_interval = _key("任务轮询间隔（秒）", "任務輪詢間隔（秒）", "Task polling interval in seconds", "タスクのポーリング間隔（秒）", "Интервал опроса задач (сек)")
    task_use_cron_module = _key("装有 ErisPulse-Cron 时把 cron 任务交给它托管", "裝有 ErisPulse-Cron 時把 cron 任務交給它託管", "Delegate cron tasks to ErisPulse-Cron when installed", "ErisPulse-Cron 導入時に cron タスクを委譲", "Передавать cron-задачи ErisPulse-Cron при наличии")

    plugins_dir = _key("用户插件目录", "使用者插件目錄", "User plugins directory", "ユーザープラグインディレクトリ", "Каталог пользовательских плагинов")
    plugins_disabled = _key("禁用的插件名列表", "停用的插件名列表", "Disabled plugin names", "無効化したプラグイン名一覧", "Список отключённых плагинов")

    view_token = _key("独立访问令牌，留空首次启动自动生成", "獨立存取令牌，留空首次啟動自動生成", "Standalone access token, generated on first start when empty", "単独アクセストークン。空欄なら初回起動時に自動生成", "Автономный токен доступа; пусто — создаётся при первом запуске")

    context_compress_tokens = _key(
        "上下文压缩阈值（估算 token，约为字符数/2，偏保守）：超过时自动把旧对话压缩为摘要后再请求，0 关闭。默认 128000（估算口径偏保守，实际约对应 200k+ 上下文）；小上下文模型可调低",
        "上下文壓縮閾值（估算 token，約為字元數/2，偏保守）：超過時自動把舊對話壓縮為摘要後再請求，0 關閉。預設 128000（估算口徑偏保守，實際約對應 200k+ 上下文）；小上下文模型可調低",
        "Context compression threshold (estimated tokens, roughly chars/2, conservative): older messages are auto-summarized before the request when exceeded; 0 disables. Default 128000 (conservative estimate, roughly 200k+ real context); lower it for small-context models",
        "コンテキスト圧縮しきい値（推定トークン、約文字数/2、保守的）：超過で古い対話を要約してからリクエスト。0 で無効。既定 128000（保守的な推定で、実質 200k+ 相当）。小さいモデルでは下げてください",
        "Порог сжатия контекста (оценка токенов, ~символов/2, консервативно): при превышении старые сообщения сжимаются в сводку; 0 — выкл. По умолчанию 128000 (консервативная оценка, ~200k+ реального контекста); для маленьких контекстов снизьте",
    )
    context_summary = _key("上下文超限被裁剪时自动摘要旧对话（需模型可用）", "上下文超限被裁剪時自動摘要舊對話（需模型可用）", "Auto-summarize trimmed context when over the limit (requires a model)", "コンテキスト超過時に古い対話を自動要約", "Автосводка обрезанного контекста при переполнении")
    extra_prompts = _key("自定义注入提示词（每行一条，追加到系统提示词末尾）", "自訂注入提示詞（每行一條，附加到系統提示詞末尾）", "Custom injected prompts (one per line, appended to the system prompt)", "カスタム注入プロンプト（1行ずつ、システムプロンプト末尾に追加）", "Свои промпты (по одному в строке, добавляются в конец system prompt)")
    owner_only = _key(
        "仅框架主人可用：开启后非管理员用户的消息不触发智能体（Dashboard 不受限制）",
        "僅框架主人可用：開啟後非管理員使用者的訊息不觸發智能體（Dashboard 不受限制）",
        "Owner-only: when enabled, messages from non-admin users do not trigger the agent (Dashboard unaffected)",
        "オーナー限定：有効にすると非管理者のメッセージはエージェントを起こさない（Dashboard は影響なし）",
        "Только для владельца: сообщения не-админов не запускают агента (Dashboard не затронут)",
    )
    tool_notice_mode = _key(
        "平台侧长任务播报：off 静默 / brief 发送 AI 的开场与阶段性发言（默认，不发工具明细）/ all 另加每轮工具明细",
        "平台側長任務播報：off 靜默 / brief 發送 AI 的開場與階段性發言（預設，不發工具明細）/ all 另加每輪工具明細",
        "Long-task announcements on chat platforms: off silent / brief post the AI's opening and milestone messages (default, no tool details) / all also post per-round tool details",
        "長時間タスクの通知：off サイレント / brief AI の開場と経過発言を送信（既定、ツール詳細なし）/ all 加えて每回のツール詳細も送信",
        "Оповещения о длинных задачах: off тихо / brief присылать вступление и промежуточные сообщения ИИ (по умолчанию, без деталей инструментов) / all ещё и детали каждого раунда",
    )
    aggregate_window = _key("消息聚合窗口（秒）：窗口内的多条消息合并为一次请求，0 关闭", "訊息聚合視窗（秒）：視窗內的多條訊息合併為一次請求，0 關閉", "Message aggregation window in seconds; messages within merge into one request (0 disables)", "メッセージ集約ウィンドウ（秒）。0 で無効", "Окно агрегации сообщений (сек), 0 — выкл")

    sensitive_paths = _key("敏感文件/目录匹配（非管理员不可读，支持通配）", "敏感檔案/目錄匹配（非管理員不可讀，支援萬用）", "Sensitive file/dir patterns (admin-only read, wildcards allowed)", "機密ファイル/ディレクトリのパターン（管理者のみ読取可）", "Шаблоны чувствительных файлов (чтение только админам)")

    daily_token_limit = _key("单日模型 token 总量限额（0 不限），超出后非管理员对话被暂停，次日重置", "單日模型 token 總量限額（0 不限），超出後非管理員對話被暫停，次日重置", "Daily model token limit (0 unlimited); non-admin chat pauses when exceeded, resets next day", "1日のトークン上限（0 無制限）。超過で非管理者の会話を一時停止", "Дневной лимит токенов (0 — без лимита); при превышении чат не-админов пауза до следующего дня")
    usage_retention_days = _key("用量统计数据保留天数", "用量統計資料保留天數", "Usage stats retention in days", "使用量統計の保持日数", "Хранение статистики использования (дней)")

    skills_dir = _key("技能目录（每个 .md 文件一个技能，frontmatter 含 name/description）", "技能目錄（每個 .md 檔案一個技能，frontmatter 含 name/description）", "Skills directory (one .md per skill, frontmatter with name/description)", "スキルディレクトリ（.md ごとに1スキル）", "Каталог навыков (один .md на навык)")
    skills_disabled = _key("禁用的技能名列表", "停用的技能名列表", "Disabled skill names", "無効なスキル名一覧", "Список отключённых навыков")

# ── 以下为声明式配置描述补齐（与 Config.py 字段一一对应；default 中文兜底见 Config._desc）──
    token_estimator = _key(
        "token 估算器：留空用启发式（中文≈1字1token、其余≈4字符1token）；tiktoken 按精确编码计数（需自行安装 tiktoken 依赖，未安装自动回退启发式）",
        "token 估算器：留空用启发式（中文≈1字1token、其余≈4字符1token）；tiktoken 按精确编码计数（需自行安装 tiktoken 依赖，未安装自動回退启发式）",
        "Token estimator: estimate / tiktoken / cjk",
        "Token estimator: estimate / tikトークン / cjk（詳細はドキュメント参照）",
        "Token estimator: estimate / tikтокены / cjk (см. документацию)",
    )

    task_models = _key(
        "按任务类别指定模型（JSON，如 {\\",
        "按任务类别指定模型（JSON，如 {\\",
        "Per-task model override (JSON, e.g. {'compact': 'provider:model'}); falls back to capability filter / cost preference / pool order",
        "Per-task モデル override (JSON, e.g. {'compact': 'provider:モデル'}); falls back to 上限ability フィルタ / cost preference / pool order（詳細はドキュメント参照）",
        "Per-task модель override (JSON, e.g. {'compact': 'provider:модель'}); falls back to лимитability фильтр / cost preference / pool order (см. документацию)",
    )

    routing_enabled = _key(
        "难度感知模型路由（实验性，默认关闭）：按本轮首条用户消息的难度自动选择便宜/均衡/高质量模型（寒暄短句走便宜、含代码或长分析走高质量）；仅对未显式指定模型/偏好/能力过滤的对话生效",
        "难度感知模型路由（实验性，預設关闭）：按本轮首条用户訊息的难度自動选择便宜/均衡/高质量模型（寒暄短句走便宜、含代码或长分析走高质量）；仅对未显式指定模型/偏好/能力過濾的对话生效",
        "Difficulty-aware model routing (experimental, off by default): picks cheap/balanced/strong models by the first user message; applies only to chats without explicit model/preference/capability filter",
        "Difficulty-aware モデル routing (experimental, off by default): picks cheap/balanced/strong モデルs by the first user message; applies only to chats without explicit モデル/preference/上限ability フィルタ（詳細はドキュメント参照）",
        "Difficulty-aware модель routing (experimental, off by default): picks cheap/balanced/strong модельs by the first user message; applies only to chats without explicit модель/preference/лимитability фильтр (см. документацию)",
    )

    routing_ttl = _key(
        "难度分级结果的会话内缓存秒数：同会话短时间连续消息复用上次分级（0 表示不缓存，每条独立分级）",
        "难度分级结果的会话内快取秒数：同会话短时间连续訊息复用上次分级（0 表示不快取，每条独立分级）",
        "Seconds a difficulty grade is cached per session (0 = grade every message)",
        "Seconds a difficulty grade is キャッシュd per session (0 = grade every message)（詳細はドキュメント参照）",
        "Seconds a difficulty grade is кэшd per session (0 = grade every message) (см. документацию)",
    )

    self_config = _key(
        "允许智能体自我配置：注册 manage_models / manage_mcp / manage_config 工具（仅管理员可用），配套内置技能教它怎么用；关闭即全部下线",
        "允許智能体自我設定：注册 manage_models / manage_mcp / manage_config 工具（仅管理员可用），配套内置技能教它怎么用；关闭即全部下线",
        "Let the agent manage its own model pool, MCP servers and settings via admin-only tools",
        "Let the agent manage its own モデル pool, MCP servers and settings via admin-only ツールs（詳細はドキュメント参照）",
        "Let the agent manage its own модель pool, MCP servers and settings via admin-only инструментыs (см. документацию)",
    )

    context_strategy = _key(
        "上下文压缩策略：auto 超限旧轮摘要为要点 / truncate 直接丢弃旧轮 / off 只做工具输出瘦身不压缩历史",
        "上下文壓縮策略：auto 超限旧轮摘要为要点 / truncate 直接丢弃旧轮 / off 只做工具輸出瘦身不壓縮歷史",
        "Context strategy: compress / truncate / off",
        "Context strategy: compress / truncate / off（詳細はドキュメント参照）",
        "Context strategy: compress / truncate / off (см. документацию)",
    )

    keep_ratio = _key(
        "压缩时保留最近对话的比例（0.1-0.5），其余轮次被摘要或丢弃",
        "壓縮时保留最近对话的比例（0.1-0.5），其余轮次被摘要或丢弃",
        "Compression keep ratio (0-1): how much recent context to retain when compressing",
        "Compression keep ratio (0-1): how much recent context to retain when compressing（詳細はドキュメント参照）",
        "Compression keep ratio (0-1): how much recent context to retain when compressing (см. документацию)",
    )

    compact_every_turns = _key(
        "预防性压缩：每 N 轮对话主动压缩一次（0 关闭，仅超阈值时才压缩）",
        "预防性壓縮：每 N 轮对话主动壓縮一次（0 关闭，仅超閾值时才壓縮）",
        "Compact every N turns (0 = auto by token budget)",
        "Compact every N turns (0 = auto by トークン budget)（詳細はドキュメント参照）",
        "Compact every N turns (0 = auto by токены budget) (см. документацию)",
    )

    compact_model = _key(
        "压缩摘要使用的模型（模型池 id），留空用当前默认模型",
        "壓縮摘要使用的模型（模型池 id），留空用当前預設模型",
        "Model for background compaction (pool id); empty = auto pick",
        "Model for background compaction (pool id); empty = auto pick（詳細はドキュメント参照）",
        "Model for background compaction (pool id); empty = auto pick (см. документацию)",
    )

    max_context_turns = _key(
        "每请求最多携带最近 N 轮对话（发送级裁剪，不修改存储历史），0 不限",
        "每请求最多携带最近 N 轮对话（发送级裁剪，不修改存储歷史），0 不限",
        "Max recent turns carried into the prompt (0 = all)",
        "Max recent turns carried into the prompt (0 = all)（詳細はドキュメント参照）",
        "Max recent turns carried into the prompt (0 = all) (см. документацию)",
    )

    tool_output_keep = _key(
        "历史中旧工具输出的保留字符数，超出截断瘦身（0 关闭）",
        "歷史中旧工具輸出的保留字符数，超出截断瘦身（0 关闭）",
        "Characters of tool output kept in history (older content truncated)",
        "Characters of ツール output kept in history (older content truncated)（詳細はドキュメント参照）",
        "Characters of инструменты output kept in history (older content truncated) (см. документацию)",
    )

    forward_platforms = _key(
        "允许合并转发的平台（支持通配 * 与前缀，如 onebot*）；* 表示全部",
        "允許合并转发的平台（支持通配 * 与前缀，如 onebot*）；* 表示全部",
        "Platforms allowed to merge-forward (wildcard * or prefix, e.g. onebot*); * = all",
        "Platforms allowed to merge-転送 (wildcard * or prefix, e.g. onebot*); * = all（詳細はドキュメント参照）",
        "Platforms allowed to merge-пересылка (wildcard * or prefix, e.g. onebot*); * = all (см. документацию)",
    )

    no_forward_platforms = _key(
        "禁止合并转发的平台黑名单（命中即使支持也不合并，优先级高于白名单）",
        "禁止合并转发的平台黑名單（命中即使支持也不合并，优先级高于白名單）",
        "Platforms banned from merge-forward (overrides the whitelist)",
        "Platforms banned from merge-転送 (overrides the ホワイトリスト)（詳細はドキュメント参照）",
        "Platforms banned from merge-пересылка (overrides the белый список) (см. документацию)",
    )

    forward_min_messages = _key(
        "合并转发的最小 AI 发言段数：本次运行中 AI 的回复达到该段数才打包合并卡（0 关闭自动合并，仍可用 [[转发]] 强制）",
        "合并转发的最小 AI 發言段数：本次运行中 AI 的回覆达到该段数才打包合并卡（0 关闭自動合并，仍可用 [[转发]] 强制）",
        "Minimum AI segments before a reply is packed as merged-forward (0 disables auto-pack)",
        "Minimum AI segments before a 返信 is packed as merged-転送 (0 disables auto-pack)（詳細はドキュメント参照）",
        "Minimum AI segments before a ответ is packed as merged-пересылка (0 disables auto-pack) (см. документацию)",
    )

    reply_split = _key(
        "纯对话分段回复：paragraph 按空行/段落切段连发模拟真人节奏 / off 单条发送；工具任务始终合并转发不分段",
        "纯对话分段回覆：paragraph 按空行/段落切段连发模拟真人节奏 / off 单条发送；工具任务始终合并转发不分段",
        "Plain-chat splitting: paragraph = split by blank lines to mimic human rhythm / off = single message; tool tasks always merge-forward",
        "Plain-chat splitting: paragraph = split by blank lines to mimic human rhythm / off = single message; ツール tasks always merge-転送（詳細はドキュメント参照）",
        "Plain-chat splitting: paragraph = split by blank lines to mimic human rhythm / off = single message; инструменты tasks always merge-пересылка (см. документацию)",
    )

    split_min_length = _key(
        "分段回复的最小触发长度（字符），低于此值单条发送",
        "分段回覆的最小觸發长度（字符），低于此值单条发送",
        "Minimum total length before splitting kicks in",
        "Minimum total length before splitting kicks in（詳細はドキュメント参照）",
        "Minimum total length before splitting kicks in (см. документацию)",
    )

    split_delay = _key(
        "分段回复每段之间的间隔秒数",
        "分段回覆每段之间的间隔秒数",
        "Base delay between split segments (seconds)",
        "Base 遅延 between split segments (seconds)（詳細はドキュメント参照）",
        "Base задержка between split segments (seconds) (см. документацию)",
    )

    interrupt_mode = _key(
        "任务运行中来新消息的处理：queue 新消息排队、当前任务后台继续（推荐）/ interrupt 取消当前任务、新消息带中断上下文重新开始",
        "任务运行中来新訊息的处理：queue 新訊息排队、当前任务後台继续（推荐）/ interrupt 取消当前任务、新訊息带中斷上下文重新开始",
        "Behavior when a new message arrives mid-reply: queue / cancel",
        "Behavior when a new message arrives mid-返信: キュー / cancel（詳細はドキュメント参照）",
        "Behavior when a new message arrives mid-ответ: очередь / cancel (см. документацию)",
    )

    user_rate_limit = _key(
        "群聊每用户每分钟触发上限（滑动窗口，0 不限，管理员豁免），超限静默丢弃并至多提示一次",
        "群聊每用户每分钟觸發上限（滑动窗口，0 不限，管理员豁免），超限静默丢弃并至多提示一次",
        "Per-user messages per minute in groups (0 = unlimited; admins exempt)",
        "Per-user messages per minute in グループs (0 = unlimited; admins exempt)（詳細はドキュメント参照）",
        "Per-user messages per minute in группаs (0 = unlimited; admins exempt) (см. документацию)",
    )

    group_isolation = _key(
        "群聊按成员隔离会话：每个成员独立上下文/人格/记忆，默认关闭",
        "群聊按成员隔离会话：每个成员独立上下文/人格/记忆，預設关闭",
        "Isolate group chats per member: each member gets a private context of group history",
        "Isolate グループ chats per member: each member gets a private context of グループ history（詳細はドキュメント参照）",
        "Isolate группа chats per member: each member gets a private context of группа history (см. документацию)",
    )

    context_budget_mode = _key(
        "上下文预算装填：auto 按选中模型的 context_length 装填 / tokens 按下方默认长度装填 / off 关闭（默认，功能灰度中）",
        "上下文預算装填：auto 按选中模型的 context_length 装填 / tokens 按下方預設长度装填 / off 关闭（預設，功能灰度中）",
        "Context budget loading: pack system parts and history by model context window with priority; overflow triggers compaction (0 = off)",
        "Context budget loading: pack system parts and history by モデル context window with priority; overflow triggers compaction (0 = off)（詳細はドキュメント参照）",
        "Context budget loading: pack system parts and history by модель context window with priority; overflow triggers compaction (0 = off) (см. документацию)",
    )

    default_context_length = _key(
        "预算模式=tokens 时的默认上下文长度（模型未上报 context_length 时兜底），0 不启用兜底",
        "預算模式=tokens 时的預設上下文长度（模型未上报 context_length 时兜底），0 不启用兜底",
        "Assumed context length when a model has none on file (tokens)",
        "Assumed context length when a モデル has none on file (トークンs)（詳細はドキュメント参照）",
        "Assumed context length when a модель has none on file (токеныs) (см. документацию)",
    )

    context_reserve = _key(
        "上下文预算保留比例：可用预算 = context_length × 该比例（预留给输出与安全边际）",
        "上下文預算保留比例：可用預算 = context_length × 该比例（预留给輸出与安全边际）",
        "Fraction of the context window reserved for the prompt (0-1)",
        "Fraction of the context window reserved for the prompt (0-1)（詳細はドキュメント参照）",
        "Fraction of the context window reserved for the prompt (0-1) (см. документацию)",
    )

    summary_cap = _key(
        "每会话历史摘要的字符总量上限，超过时触发合并压缩",
        "每会话歷史摘要的字符总量上限，超过时觸發合并壓縮",
        "Max characters of a session summary",
        "Max characters of a session summary（詳細はドキュメント参照）",
        "Max characters of a session summary (см. документацию)",
    )

    compact_transcript_chars = _key(
        "压缩时每条历史消息进入转写的最大字符数（0 不截断）",
        "壓縮时每条歷史訊息进入轉寫的最大字符数（0 不截断）",
        "Max chars of transcript sent to the summarizer",
        "Max chars of transcript sent to the summarizer（詳細はドキュメント参照）",
        "Max chars of transcript sent to the summarizer (см. документацию)",
    )

    compact_input_chars = _key(
        "压缩请求送入模型的转写最大字符数（0 不截断）",
        "壓縮请求送入模型的轉寫最大字符数（0 不截断）",
        "Max chars for merging two summaries",
        "Max chars for merging two summaries（詳細はドキュメント参照）",
        "Max chars for merging two summaries (см. документацию)",
    )

    facts_extract = _key(
        "对话中自动抽取长期事实要点（用户偏好/约定等），注入后续会话",
        "对话中自動抽取长期事实要点（用户偏好/约定等），注入后续会话",
        "Facts extracted per compaction (0 = off)",
        "Facts extracted per compaction (0 = off)（詳細はドキュメント参照）",
        "Facts extracted per compaction (0 = off) (см. документацию)",
    )

    facts_max = _key(
        "每会话保留的事实要点条数上限（超限保最新）",
        "每会话保留的事实要点条数上限（超限保最新）",
        "Max stored facts per session",
        "Max stored facts per session（詳細はドキュメント参照）",
        "Max stored facts per session (см. документацию)",
    )

    sentence_split = _key(
        "段内超长时按句切分（拟人节奏，关闭则仅按段落切分）",
        "段内超长时按句切分（拟人节奏，关闭则仅按段落切分）",
        "Split replies into short sentences like a real person",
        "Split replies into short sentences like a real person（詳細はドキュメント参照）",
        "Split replies into short sentences like a real person (см. документацию)",
    )

    sentence_max = _key(
        "句级切分时每段打包的字数上限",
        "句级切分时每段打包的字数上限",
        "Max characters per sentence segment",
        "Max characters per sentence segment（詳細はドキュメント参照）",
        "Max characters per sentence segment (см. документацию)",
    )

    typing_speed = _key(
        "拟人打字速度（字/秒），决定段间延迟时长",
        "拟人打字速度（字/秒），决定段间延遲时长",
        "Typing delay per character (seconds); 0 disables pacing",
        "Typing 遅延 per character (seconds); 0 disables pacing（詳細はドキュメント参照）",
        "Typing задержка per character (seconds); 0 disables pacing (см. документацию)",
    )

    split_jitter = _key(
        "段间延迟随机抖动幅度（0-1，模拟输入停顿）",
        "段间延遲随机抖动幅度（0-1，模拟輸入停顿）",
        "Random jitter ratio for split delays (0-1)",
        "Random jitter ratio for split 遅延s (0-1)（詳細はドキュメント参照）",
        "Random jitter ratio for split задержкаs (0-1) (см. документацию)",
    )

    min_delay = _key(
        "单段发送延迟下限（秒）",
        "单段发送延遲下限（秒）",
        "Minimum delay between segments (seconds)",
        "Minimum 遅延 between segments (seconds)（詳細はドキュメント参照）",
        "Minimum задержка between segments (seconds) (см. документацию)",
    )

    max_delay = _key(
        "单段发送延迟上限（秒）",
        "单段发送延遲上限（秒）",
        "Maximum delay between segments (seconds)",
        "Maximum 遅延 between segments (seconds)（詳細はドキュメント参照）",
        "Maximum задержка between segments (seconds) (см. документацию)",
    )

    total_delay_cap = _key(
        "整条回复分段总延迟上限（秒），超出按比例压缩",
        "整条回覆分段总延遲上限（秒），超出按比例壓縮",
        "Total pacing delay cap per reply (seconds)",
        "Total pacing 遅延 上限 per 返信 (seconds)（詳細はドキュメント参照）",
        "Total pacing задержка лимит per ответ (seconds) (см. документацию)",
    )

    max_parts = _key(
        "分段发送条数上限（超出的段落合并）",
        "分段发送条数上限（超出的段落合并）",
        "Max segments per reply",
        "Max segments per 返信（詳細はドキュメント参照）",
        "Max segments per ответ (см. документацию)",
    )

    delivery_profiles = _key(
        "按平台覆盖投递参数（如 {\\",
        "按平台覆盖投递参数（如 {\\",
        "Per-platform delivery overrides (e.g. {'onebot11': {'max_parts': 3}}; supports prefix wildcards)",
        "Per-platform delivery overrides (e.g. {'onebot11': {'max_parts': 3}}; supports prefix wildcards)（詳細はドキュメント参照）",
        "Per-platform delivery overrides (e.g. {'onebot11': {'max_parts': 3}}; supports prefix wildcards) (см. документацию)",
    )

    forward_structure_aware = _key(
        "结构感知合并转发：代码块/表格/列表占比达标的回复才打包转发，纯寒暄多段直发",
        "結構感知合并转发：代码塊/表格/列表占比达标的回覆才打包转发，纯寒暄多段直发",
        "Structure-aware merge-forward: only pack replies with enough code/tables/lists; plain chats are sent directly",
        "Structure-aware merge-転送: only pack replies with enough code/tables/lists; plain chats are sent directly（詳細はドキュメント参照）",
        "Structure-aware merge-пересылка: only pack replies with enough code/tables/lists; plain chats are sent directly (см. документацию)",
    )

    send_retry = _key(
        "发送失败（超时/网络类错误）重试次数",
        "发送失敗（逾時/网络类错误）重试次数",
        "Retries for failed sends (timeout/network errors)",
        "Retries for failed sends (タイムアウト/network errors)（詳細はドキュメント参照）",
        "Retries for failed sends (тайм-аут/network errors) (см. документацию)",
    )

    retry_delay = _key(
        "重试退避基数（秒），指数递增",
        "重试退避基数（秒），指数递增",
        "Retry backoff base in seconds (exponential)",
        "Retry backoff base in seconds (exponential)（詳細はドキュメント参照）",
        "Retry backoff base in seconds (exponential) (см. документацию)",
    )

    pending_send_max = _key(
        "发送失败待重发队列每会话上限（FIFO 淘汰）",
        "发送失敗待重发佇列每会话上限（FIFO 淘汰）",
        "Max entries per session in the failed-send queue (FIFO eviction)",
        "Max entries per session in the failed-send キュー (FIFO eviction)（詳細はドキュメント参照）",
        "Max entries per session in the failed-send очередь (FIFO eviction) (см. документацию)",
    )

    opening_enabled = _key(
        "新会话首次接触时自动发送人格开场白（随机一条；Dashboard 平台不触发）",
        "新会话首次接触时自動发送人格开场白（随机一条；Dashboard 平台不觸發）",
        "Send a persona opening line on first contact of a new session (random one; never on Dashboard)",
        "Send a persona opening line on first contact of a new session (random one; never on Dashboard)（詳細はドキュメント参照）",
        "Send a persona opening line on first contact of a new session (random one; never on Dashboard) (см. документацию)",
    )

    opening_on_seed = _key(
        "冷启动历史回填发生时也发送开场白（默认关闭：回填说明已有过对话，不再打招呼）",
        "冷啟動歷史回填发生时也发送开场白（預設关闭：回填说明已有过对话，不再打招呼）",
        "Also send the opening when cold-start history backfill happens (off by default)",
        "Also send the opening when cold-start history backfill happens (off by default)（詳細はドキュメント参照）",
        "Also send the opening when cold-start history backfill happens (off by default) (см. документацию)",
    )

    opening_on_reset = _key(
        "/qvq reset 重置会话时同时清除开场白已发标记，下次对话重新发送开场白",
        "/qvq reset 重置会话时同时清除开场白已发標記，下次对话重新发送开场白",
        "/qvq reset also clears the opening-sent flag so the opening is sent again next turn",
        "/qvq reset also clears the opening-sent flag so the opening is sent again next turn（詳細はドキュメント参照）",
        "/qvq reset also clears the opening-sent flag so the opening is sent again next turn (см. документацию)",
    )

    opening_max_len = _key(
        "开场白单条最大字符数（超出截断）",
        "开场白单条最大字符数（超出截断）",
        "Max characters per opening line (truncated beyond)",
        "Max characters per opening line (truncated beyond)（詳細はドキュメント参照）",
        "Max characters per opening line (truncated beyond) (см. документацию)",
    )

    reply_narrate = _key(
        "边做边说：工具任务的每一步先说一句要做什幺、拿到结果简短汇报、结束给简短结论（每句单独发到群里，像真人工作播报）",
        "边做边说：工具任务的每一步先说一句要做什幺、拿到结果简短汇报、结束给简短结论（每句单独发到群里，像真人工作播报）",
        "Work out loud: announce each tool step, report results briefly, close with a short summary",
        "Work out loud: announce each ツール step, report results briefly, close with a short summary（詳細はドキュメント参照）",
        "Work out loud: announce each инструменты step, report results briefly, close with a short summary (см. документацию)",
    )

    notify_on_passive_failure = _key(
        "被动触发的任务（如插件插话）失败时也在群里回复错误详情；默认关闭只记日志，避免错误刷屏",
        "被动觸發的任务（如外掛插話）失敗时也在群里回覆错误详情；預設关闭只记日志，避免错误刷屏",
        "Also reply error details when passively triggered tasks fail; off by default (log only)",
        "Also 返信 error details when passively triggered tasks fail; off by default (log only)（詳細はドキュメント参照）",
        "Also ответ error details when passively triggered tasks fail; off by default (log only) (см. документацию)",
    )

    forward_exclude_trace = _key(
        "合并转发卡不生成「执行过程」工具节点（纯结论卡片，过程仍可在网页端查看）",
        "合并转发卡不生成「执行过程」工具节点（纯结论卡片，过程仍可在网页端查看）",
        "Merged-forward cards skip the execution-trace node (conclusion-only cards; trace still on the web)",
        "Merged-転送 cards skip the execution-trace node (conclusion-only cards; trace still on the web)（詳細はドキュメント参照）",
        "Merged-пересылка cards skip the execution-trace node (conclusion-only cards; trace still on the web) (см. документацию)",
    )

    chat_output_rules = _key(
        "闲聊输出规则：禁复述对方上条、禁结尾硬造反问、没把握可只回「？」、群聊短段输出（任务/工具场景不受限）",
        "闲聊輸出规则：禁复述对方上条、禁结尾硬造反问、没把握可只回「？」、群聊短段輸出（任务/工具场景不受限）",
        "Casual-chat output rules: no restating, no forced follow-up questions, brief replies in groups (tasks/tools unaffected)",
        "Casual-chat output rules: no restating, no forced follow-up questions, brief replies in グループs (tasks/ツールs unaffected)（詳細はドキュメント参照）",
        "Casual-chat output rules: no restating, no forced follow-up questions, brief replies in группаs (tasks/инструментыs unaffected) (см. документацию)",
    )

    identity_note_other_agents = _key(
        "系统提示注入「群内其他智能体不是你」认知条款，防止认领别人的发言",
        "系统提示注入「群内其他智能体不是你」认知条款，防止认领别人的發言",
        "System note that other bots/agents in the group are not you, so their messages are not claimed",
        "System note that other bots/agents in the グループ are not you, so their messages are not claimed（詳細はドキュメント参照）",
        "System note that other bots/agents in the группа are not you, so their messages are not claimed (см. документацию)",
    )

    scene_platform_prefix = _key(
        "会话场景说明附带平台名（如 平台：onebot11）",
        "会话场景说明附带平台名（如 平台：onebot11）",
        "Prefix the scene description with the platform name",
        "Prefix the scene description with the platform name（詳細はドキュメント参照）",
        "Prefix the scene description with the platform name (см. документацию)",
    )

    recovery_enabled = _key(
        "实例重启后自动恢复被中断的回复",
        "实例重啟后自動恢復被中斷的回覆",
        "Auto-resume interrupted replies after a restart",
        "Auto-再開 中断ed replies after a 再起動（詳細はドキュメント参照）",
        "Auto-возобновить прерванныеed replies after a перезапуск (см. документацию)",
    )

    recovery_min_age = _key(
        "标记距今超过该秒数才恢复（防误判正常在跑）",
        "標記距今超过该秒数才恢復（防误判正常在跑）",
        "Only marks older than this many seconds are recovered (guards against false positives)",
        "Only marks older than this many seconds are recovered (guards against false positives)（詳細はドキュメント参照）",
        "Only marks older than this many seconds are recovered (guards against false positives) (см. документацию)",
    )

    replay_on_boot = _key(
        "启动时重放发送失败队列",
        "啟動时重放发送失敗佇列",
        "Replay the failed-send queue on startup",
        "Replay the failed-send キュー on startup（詳細はドキュメント参照）",
        "Replay the failed-send очередь on startup (см. документацию)",
    )

    debounce_mention_seconds = _key(
        "被 @/前缀命中触发时的防抖窗口（秒）：窗口内后续消息并入本次请求；0 使用群聊窗口",
        "被 @/前缀命中觸發时的防抖窗口（秒）：窗口内后续訊息并入本次请求；0 使用群聊窗口",
        "Debounce window in seconds when @-mentioned or prefix-triggered; 0 = use group window",
        "Debounce window in seconds when @-mentioned or prefix-triggered; 0 = use グループ window（詳細はドキュメント参照）",
        "Debounce window in seconds when @-mentioned or prefix-triggered; 0 = use группа window (см. документацию)",
    )

    debounce_group_seconds = _key(
        "普通群消息的聚合窗口（秒）；0 使用 aggregate_window",
        "普通群訊息的聚合窗口（秒）；0 使用 aggregate_window",
        "Aggregation window in seconds for normal group messages; 0 = use aggregate_window",
        "Aggregation window in seconds for normal グループ messages; 0 = use aggregate_window（詳細はドキュメント参照）",
        "Aggregation window in seconds for normal группа messages; 0 = use aggregate_window (см. документацию)",
    )

    humanize_echo_filter = _key(
        "丢弃适配器回投的自身出站消息（防回声在防抖窗口内触发二次决策）",
        "丢弃適配器回投的自身出站訊息（防回聲在防抖窗口内觸發二次决策）",
        "Drop the adapter echoing back our own outbound messages (prevents self-triggering)",
        "Drop the adapter echoing back our own outbound messages (prevents self-triggering)（詳細はドキュメント参照）",
        "Drop the adapter echoing back our own outbound messages (prevents self-triggering) (см. документацию)",
    )

    humanize_filter_enabled = _key(
        "输出过滤器：复述对方上条时重答一次；句数超限按句号截断；结尾硬造反问去掉（失败不阻塞发送）",
        "輸出過濾器：复述对方上条时重答一次；句数超限按句号截断；结尾硬造反问去掉（失敗不阻塞发送）",
        "Reply filter: re-answer once when restating the user, trim long replies, strip forced trailing questions",
        "Reply フィルタ: re-answer once when restating the user, trim long replies, strip forced trailing questions（詳細はドキュメント参照）",
        "Reply фильтр: re-answer once when restating the user, trim long replies, strip forced trailing questions (см. документацию)",
    )

    humanize_filter_max_sentences = _key(
        "输出过滤器：单次回复句数上限，超出按句号边界截断（0 关闭句数与复述检测）",
        "輸出過濾器：單次回覆句数上限，超出按句号边界截断（0 关闭句数与复述检测）",
        "Max sentences per reply in the filter (0 disables sentence and parrot checks)",
        "Max sentences per 返信 in the フィルタ (0 disables sentence and parrot checks)（詳細はドキュメント参照）",
        "Max sentences per ответ in the фильтр (0 disables sentence and parrot checks) (см. документацию)",
    )

    humanize_recall_interval_hours = _key(
        "「记得你」记忆回捞提示的最小间隔（小时/用户，0 关闭该提示；相关记忆本身仍正常注入）",
        "「记得你」记忆回捞提示的最小间隔（小时/用户，0 关闭该提示；相关记忆本身仍正常注入）",
        "Minimum hours between memory callbacks per user (0 disables the hint)",
        "Minimum hours between memory callbacks per user (0 disables the hint)（詳細はドキュメント参照）",
        "Minimum hours between memory callbacks per user (0 disables the hint) (см. документацию)",
    )

    humanize_recall_on_cold_only = _key(
        "回捞提示仅在对方先发起对话的回合出现，任务/定时触发的回合不提旧事",
        "回捞提示仅在对方先发起对话的回合出现，任务/定时觸發的回合不提旧事",
        "Recall hints only on user-initiated turns — never on tasks or scheduled runs",
        "Recall hints only on user-initiated turns — never on tasks or scheduled runs（詳細はドキュメント参照）",
        "Recall hints only on user-initiated turns — never on tasks or scheduled runs (см. документацию)",
    )

    humanize_budget_seconds = _key(
        "单次回复总响应预算（秒，防抖+生成+打字延迟）：超时按 延迟减半→归零→多条合并为一条 降级，话一定说完只是放弃节奏；0 关闭",
        "單次回覆总响应預算（秒，防抖+生成+打字延遲）：逾時按 延遲减半→归零→多条合并为一条 降级，话一定说完只是放弃节奏；0 关闭",
        "Total response budget per reply in seconds; on overrun degrade typing delay then merge segments; 0 disables",
        "Total response budget per 返信 in seconds; on overrun degrade typing 遅延 then merge segments; 0 disables（詳細はドキュメント参照）",
        "Total response budget per ответ in seconds; on overrun degrade typing задержка then merge segments; 0 disables (см. документацию)",
    )

    humanize_interrupt = _key(
        "硬打断：上一轮回复还没发完时，收到强信号立即丢弃未发短句，新消息优先处理（已发出的句子不撤）",
        "硬打断：上一轮回覆还没发完时，收到强信号立即丢弃未发短句，新訊息优先处理（已发出的句子不撤）",
        "Hard interrupt: strong signals cancel unsent segments mid-send; the new message is handled first",
        "Hard 中断: strong signals cancel unsent segments mid-send; the new message is handled first（詳細はドキュメント参照）",
        "Hard прерванные: strong signals cancel unsent segments mid-send; the new message is handled first (см. документацию)",
    )

    humanize_interrupt_signals = _key(
        "硬打断信号：mention=被@ reply=引用回复 burst=同一人10秒内连发 urge=催促词",
        "硬打断信号：mention=被@ reply=引用回覆 burst=同一人10秒内连发 urge=催促词",
        "Interrupt signals: mention / reply / burst / urge",
        "Interrupt signals: mention / 返信 / burst / urge（詳細はドキュメント参照）",
        "Interrupt signals: mention / ответ / burst / urge (см. документацию)",
    )

    humanize_recall_message = _key(
        "打断信号含纠错词（撤回/说错/发错）时，主动撤回机器人上一条消息（平台需支持 delete_msg，失败静默）",
        "打断信号含纠错词（撤回/说错/发错）时，主动撤回机器人上一条訊息（平台需支持 delete_msg，失敗静默）",
        "Correction words (recall/typo/wrong) also delete the bot's previous message when supported",
        "Correction words (recall/typo/wrong) also delete the bot's previous message when supported（詳細はドキュメント参照）",
        "Correction words (recall/typo/wrong) also delete the bot's previous message when supported (см. документацию)",
    )

    profile_enabled = _key(
        "跨会话用户画像：定时聚合该用户各会话 facts/长期记忆，提炼为 traits/preferences 并注入系统提示",
        "跨会话用户畫像：定时聚合该用户各会话 facts/长期记忆，提炼为 traits/preferences 并注入系统提示",
        "Cross-session user profile: aggregates facts into traits/preferences injected into the system prompt",
        "Cross-session user プロフィール: aggregates facts into traits/preferences injected into the system prompt（詳細はドキュメント参照）",
        "Cross-session user профиль: aggregates facts into traits/preferences injected into the system prompt (см. документацию)",
    )

    profile_consolidate_hours = _key(
        "画像固化定时任务间隔（小时），0 关闭定时固化",
        "畫像固化定时任务间隔（小时），0 关闭定时固化",
        "Profile consolidation interval in hours (0 disables)",
        "Profile consolidation interval in hours (0 disables)（詳細はドキュメント参照）",
        "Profile consolidation interval in hours (0 disables) (см. документацию)",
    )

    profile_inject = _key(
        "注入系统提示的画像条数上限",
        "注入系统提示的畫像条数上限",
        "Max profile lines injected into the system prompt",
        "Max プロフィール lines injected into the system prompt（詳細はドキュメント参照）",
        "Max профиль lines injected into the system prompt (см. документацию)",
    )

    profile_max = _key(
        "画像每类（特点/偏好/事实）条数上限，超限保最新",
        "畫像每类（特点/偏好/事实）条数上限，超限保最新",
        "Max entries per profile category (oldest dropped beyond)",
        "Max entries per プロフィール category (oldest dropped beyond)（詳細はドキュメント参照）",
        "Max entries per профиль category (oldest dropped beyond) (см. документацию)",
    )

    profile_decay_days = _key(
        "画像特点衰减天数：超过该天数未被任何会话新事实强化的条目淘汰（0 关闭衰减）",
        "畫像特点衰減天数：超过该天数未被任何会话新事实强化的條目淘汰（0 关闭衰減）",
        "Trait decay days: unreinforced entries are dropped after this many days (0 disables)",
        "Trait decay days: unreinforced entries are dropped after this many days (0 disables)（詳細はドキュメント参照）",
        "Trait decay days: unreinforced entries are dropped after this many days (0 disables) (см. документацию)",
    )

    tools_fallback = _key(
        "池中无支持工具调用的模型时的降级：strip 去掉工具并在提示词中说明（默认，保证必答）/ strict 直接报错 / off 照常携带工具",
        "池中无支持工具调用的模型时的降级：strip 去掉工具并在提示词中说明（預設，保证必答）/ strict 直接报错 / off 照常携带工具",
        "When no model supports tool calls: strip = remove tools and note it / strict = raise / off = send tools anyway",
        "When no モデル supports ツール calls: strip = remove ツールs and note it / strict = raise / off = send ツールs anyway（詳細はドキュメント参照）",
        "When no модель supports инструменты calls: strip = remove инструментыs and note it / strict = raise / off = send инструментыs anyway (см. документацию)",
    )

    tool_self_heal = _key(
        "工具自愈：同一工具连续两次调用失败时向模型注入一条修正提示（含错误摘要），让它自行调整参数重试；调用成功即重置计数",
        "工具自愈：同一工具连续两次调用失敗时向模型注入一条修正提示（含错误摘要），让它自行调整参数重试；调用成功即重置计数",
        "Inject an error digest after the same tool fails twice so the model can fix arguments and retry",
        "Inject an error digest after the same ツール fails twice so the モデル can fix arguments and 再試行（詳細はドキュメント参照）",
        "Inject an error digest after the same инструменты fails twice so the модель can fix arguments and повтор (см. документацию)",
    )

    skill_induct = _key(
        "技能自动习得：注册 save_skill 工具并在系统提示中说明——用户要求\\",
        "技能自動习得：注册 save_skill 工具并在系统提示中说明——用户要求\\",
        "After novel multi-step tasks, the model may save the approach as a reusable skill on request",
        "After novel multi-step tasks, the モデル may save the approach as a reusable スキル on request（詳細はドキュメント参照）",
        "After novel multi-step tasks, the модель may save the approach as a reusable навыки on request (см. документацию)",
    )

    kb_auto_inject = _key(
        "对话时自动检索知识库相关片段注入系统提示",
        "对话时自動檢索知識庫相关片段注入系统提示",
        "Auto-inject relevant knowledge base entries into the system prompt",
        "Auto-inject relevant ナレッジ base entries into the system prompt（詳細はドキュメント参照）",
        "Auto-inject relevant база знаний base entries into the system prompt (см. документацию)",
    )

    kb_top_k = _key(
        "自动注入的知识库片段数上限",
        "自動注入的知識庫片段数上限",
        "Max semantic-search hits injected per turn",
        "Max semantic-search hits injected per turn（詳細はドキュメント参照）",
        "Max semantic-search hits injected per turn (см. документацию)",
    )

    kb_chunk_size = _key(
        "知识库条目检索分块的目标字符数",
        "知識庫條目檢索分塊的目标字符数",
        "Knowledge base chunk size in characters",
        "Knowledge base chunk size in characters（詳細はドキュメント参照）",
        "Knowledge base chunk size in characters (см. документацию)",
    )

    kb_chunk_overlap = _key(
        "知识库相邻分块的重叠字符数",
        "知識庫相邻分塊的重疊字符数",
        "Overlap between adjacent chunks in characters",
        "Overlap between adjacent chunks in characters（詳細はドキュメント参照）",
        "Overlap between adjacent chunks in characters (см. документацию)",
    )

    kb_triggers_enabled = _key(
        "世界书触发注入：条目配置 triggers 关键词后，最近对话命中即注入该条目（SillyTavern World Info 模式，与检索注入并存）",
        "世界书觸發注入：條目設定 triggers 关键词后，最近对话命中即注入该條目（SillyTavern World Info 模式，与檢索注入并存）",
        "Lorebook trigger injection on (keywords appearing in chat inject entries)",
        "Lorebook trigger injection on (keywords appearing in chat inject entries)（詳細はドキュメント参照）",
        "Lorebook trigger injection on (keywords appearing in chat inject entries) (см. документацию)",
    )

    kb_trigger_window = _key(
        "世界书触发扫描的最近消息条数（含本次消息）",
        "世界书觸發扫描的最近訊息条数（含本次訊息）",
        "Recent messages scanned for lorebook triggers",
        "Recent messages scanned for lorebook triggers（詳細はドキュメント参照）",
        "Recent messages scanned for lorebook triggers (см. документацию)",
    )

    kb_cooldown_min = _key(
        "世界书条目新添加时的默认触发冷却分钟数（冷却期内不再注入，条目级 cooldown_min 可覆盖；0 不冷却）",
        "世界书條目新添加时的預設觸發冷卻分钟数（冷卻期内不再注入，條目级 cooldown_min 可覆盖；0 不冷卻）",
        "Default cooldown minutes between two injections of the same entry",
        "Default クールダウン minutes between two injections of the same entry（詳細はドキュメント参照）",
        "Default кулдаун minutes between two injections of the same entry (см. документацию)",
    )

    embedding_enabled = _key(
        "知识库语义检索：向量层可用时按余弦相似度检索（任何环节不可用自动回退词面打分，零配置行为不变）",
        "知識庫語義檢索：向量层可用时按余弦相似度檢索（任何环节不可用自動回退词面打分，零設定行为不变）",
        "Semantic retrieval via OpenAI-compatible embeddings; falls back to keyword search",
        "Semantic retrieval via OpenAI-compatible 埋め込みs; falls back to keyword search（詳細はドキュメント参照）",
        "Semantic retrieval via OpenAI-compatible эмбеддингиs; falls back to keyword search (см. документацию)",
    )

    embedding_model = _key(
        "向量模型名字符串（配合 embedding_provider，如 text-embedding-3-small；留空用 provider 内 model）",
        "向量模型名字符串（配合 embedding_provider，如 text-embedding-3-small；留空用 provider 内 model）",
        "Embedding model id",
        "Embedding モデル id（詳細はドキュメント参照）",
        "Embedding модель id (см. документацию)",
    )

    embedding_provider = _key(
        "embedding 服务提供者（JSON：{\\",
        "embedding 服务提供者（JSON：{\\",
        "Embedding provider config (JSON: base_url/api_key/model)",
        "Embedding provider config (JSON: base_url/api_key/モデル)（詳細はドキュメント参照）",
        "Embedding provider config (JSON: base_url/api_key/модель) (см. документацию)",
    )

    participation_enabled = _key(
        "群聊参与决策：未被 @/前缀命中时问询生态插件的 qvq_decision 服务判断是否插话（默认关闭，需自行开启）",
        "群聊參與决策：未被 @/前缀命中时问询生态外掛的 qvq_decision 服务判断是否插話（預設关闭，需自行开启）",
        "Group participation: ask ecosystem plugins whether to chime in when not @-ed (off by default)",
        "Group participation: ask ecosystem plugins whether to chime in when not @-ed (off by default)（詳細はドキュメント参照）",
        "Group participation: ask ecosystem plugins whether to chime in when not @-ed (off by default) (см. документацию)",
    )

    participation_groups = _key(
        "参与决策生效的群白名单（群号或 platform:group:gid，支持通配），留空表示全部群",
        "參與决策生效的群白名單（群号或 platform:group:gid，支持通配），留空表示全部群",
        "Group whitelist for participation decisions (empty = all groups)",
        "Group ホワイトリスト for participation decisions (empty = all グループs)（詳細はドキュメント参照）",
        "Group белый список for participation decisions (empty = all группаs) (см. документацию)",
    )

    participation_groups_exclude = _key(
        "参与决策排除的群黑名单，优先级高于白名单",
        "參與决策排除的群黑名單，优先级高于白名單",
        "Groups excluded from participation decisions (overrides whitelist)",
        "Groups excluded from participation decisions (overrides ホワイトリスト)（詳細はドキュメント参照）",
        "Groups excluded from participation decisions (overrides белый список) (см. документацию)",
    )

    participation_hourly_limit = _key(
        "每群每小时机器人主动发言上限（插话+主动开口，0 不限），超出后本小时静默",
        "每群每小时机器人主动發言上限（插話+主动开口，0 不限），超出后本小时静默",
        "Max bot speeches per group per hour (0 = unlimited)",
        "Max bot speeches per グループ per hour (0 = unlimited)（詳細はドキュメント参照）",
        "Max bot speeches per группа per hour (0 = unlimited) (см. документацию)",
    )

    participation_cooldown_seconds = _key(
        "同群两次发言的最小间隔秒数（0 不限），冷却期内不再插话",
        "同群两次發言的最小间隔秒数（0 不限），冷卻期内不再插話",
        "Minimum seconds between speeches in the same group (0 = unlimited)",
        "Minimum seconds between speeches in the same グループ (0 = unlimited)（詳細はドキュメント参照）",
        "Minimum seconds between speeches in the same группа (0 = unlimited) (см. документацию)",
    )

    participation_proactive_daily_limit = _key(
        "全局每日主动发言（speak 服务）上限（0 不限），插话不计入",
        "全局每日主动發言（speak 服务）上限（0 不限），插話不计入",
        "Global daily cap for proactive speak (interjections don't count)",
        "Global daily 上限 for proactive speak (interjections don't count)（詳細はドキュメント参照）",
        "Global daily лимит for proactive speak (interjections don't count) (см. документацию)",
    )
