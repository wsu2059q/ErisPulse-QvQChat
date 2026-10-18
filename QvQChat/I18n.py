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

