"""
QvQChat i18n 键声明

使用 ErisPulse 声明式 i18n 系统（v2.7.0+）。
框架在模块加载时自动注册所有翻译键。
"""

from ErisPulse.Core.Bases import BaseI18n, I18nKey


class QvQI18n(BaseI18n):
    """QvQChat 国际化翻译键集合"""

    # ==================== 模块生命周期 ====================

    module_init_done: I18nKey = I18nKey(
        default="QvQChat module initialized",
        zh_CN="QvQChat 模块初始化完成",
        zh_TW="QvQChat 模組初始化完成",
        en="QvQChat module initialized",
        ja="QvQChat モジュールの初期化が完了しました",
        ru="Модуль QvQChat инициализирован",
    )

    module_loaded: I18nKey = I18nKey(
        default="QvQChat module loaded",
        zh_CN="QvQChat 模块已加载",
        zh_TW="QvQChat 模組已載入",
        en="QvQChat module loaded",
        ja="QvQChat モジュールを読み込みました",
        ru="Модуль QvQChat загружен",
    )

    module_unloaded: I18nKey = I18nKey(
        default="QvQChat module unloaded",
        zh_CN="QvQChat 模块已卸载",
        zh_TW="QvQChat 模組已卸載",
        en="QvQChat module unloaded",
        ja="QvQChat モジュールを解除しました",
        ru="Модуль QvQChat выгружен",
    )

    module_load_failed: I18nKey = I18nKey(
        default="QvQChat module load failed: {error}",
        zh_CN="QvQChat 模块加载失败: {error}",
        zh_TW="QvQChat 模組載入失敗: {error}",
        en="QvQChat module load failed: {error}",
        ja="QvQChat モジュールの読み込みに失敗しました: {error}",
        ru="Ошибка загрузки модуля QvQChat: {error}",
    )

    module_unload_failed: I18nKey = I18nKey(
        default="QvQChat module unload failed: {error}",
        zh_CN="QvQChat 模块卸载失败: {error}",
        zh_TW="QvQChat 模組卸載失敗: {error}",
        en="QvQChat module unload failed: {error}",
        ja="QvQChat モジュールの解除に失敗しました: {error}",
        ru="Ошибка выгрузки модуля QvQChat: {error}",
    )

    # ==================== 配置引导 ====================

    no_models_configured: I18nKey = I18nKey(
        default="No AI models configured. Add models in Dashboard > Model Management, then assign them in Behavior Management.",
        zh_CN="尚未配置任何 AI 模型。请在 Dashboard 的「模型管理」中添加模型，然后在「行为管理」中为行为分配模型。",
        zh_TW="尚未設定任何 AI 模型。請在 Dashboard 的「模型管理」中新增模型，然後在「行為管理」中為行為分配模型。",
        en="No AI models configured. Add models in Dashboard > Model Management, then assign them in Behavior Management.",
        ja="AIモデルが設定されていません。Dashboardの「モデル管理」でモデルを追加し、「行動管理」で割り当ててください。",
        ru="AI модели не настроены. Добавьте модели в Dashboard > Управление моделями, затем назначьте их в Управлении поведением.",
    )

    behaviors_unassigned: I18nKey = I18nKey(
        default="Behaviors without model assignment: {behaviors}. Please assign in Dashboard > Behavior Management.",
        zh_CN="以下行为未分配模型: {behaviors}。请在 Dashboard 的「行为管理」中分配。",
        zh_TW="以下行為未分配模型: {behaviors}。請在 Dashboard 的「行為管理」中分配。",
        en="Behaviors without model assignment: {behaviors}. Please assign in Dashboard > Behavior Management.",
        ja="モデルが割り当てられていない行動: {behaviors}。Dashboardの「行動管理」で割り当ててください。",
        ru="Поведению не назначены модели: {behaviors}. Назначьте в Dashboard > Управление поведением.",
    )

    # ==================== 记忆系统 ====================

    memory_fallback_to_dialogue: I18nKey = I18nKey(
        default="Memory behavior has no model assigned, falling back to dialogue model for extraction",
        zh_CN="memory 行为未分配模型，自动复用 dialogue 模型进行记忆提取",
        zh_TW="memory 行為未分配模型，自動複用 dialogue 模型進行記憶提取",
        en="Memory behavior has no model assigned, falling back to dialogue model for extraction",
        ja="memory 行動にモデルが割り当てられていないため、dialogue モデルを使用して記憶抽出を行います",
        ru="Поведению memory не назначена модель, используется модель dialogue для извлечения памяти",
    )

    memory_extract_done: I18nKey = I18nKey(
        default="Memory extraction done - {count} item(s) extracted",
        zh_CN="行为[memory]完成 - 提取{count}条记忆",
        zh_TW="行為[memory]完成 - 提取{count}條記憶",
        en="Memory extraction done - {count} item(s) extracted",
        ja="行動[memory]完了 - {count}件の記憶を抽出しました",
        ru="Извлечение памяти завершено - извлечено {count} записей",
    )

    memory_extract_none: I18nKey = I18nKey(
        default="Memory extraction done - nothing worth remembering",
        zh_CN="行为[memory]完成 - 无值得记忆的内容",
        zh_TW="行為[memory]完成 - 無值得記憶的內容",
        en="Memory extraction done - nothing worth remembering",
        ja="行動[memory]完了 - 記憶する価値のある内容はありません",
        ru="Извлечение памяти завершено - нет заслуживающего внимания",
    )

    memory_extract_timeout: I18nKey = I18nKey(
        default="Memory extraction timeout ({seconds}s), skipped",
        zh_CN="行为[memory]超时({seconds}s)，跳过",
        zh_TW="行為[memory]逾時（{seconds}s），跳過",
        en="Memory extraction timeout ({seconds}s), skipped",
        ja="行動[memory]タイムアウト（{seconds}秒）、スキップしました",
        ru="Тайм-аут извлечения памяти ({seconds}s), пропущено",
    )

    # ==================== 回复判断 ====================

    reply_mentioned: I18nKey = I18nKey(
        default="Mentioned or called by name in group, replying directly",
        zh_CN="群聊被@或叫名字，直接回复",
        zh_TW="群聊被@或叫名字，直接回覆",
        en="Mentioned or called by name in group, replying directly",
        ja="グループで@または名前で呼ばれました、直接返信します",
        ru="Упомянут в группе, прямой ответ",
    )

    reply_active_mode: I18nKey = I18nKey(
        default="Active mode enabled, replying directly",
        zh_CN="活跃模式生效中，直接回复",
        zh_TW="活躍模式生效中，直接回覆",
        en="Active mode enabled, replying directly",
        ja="アクティブモード有効中、直接返信します",
        ru="Активный режим включён, прямой ответ",
    )

    reply_topic_hot: I18nKey = I18nKey(
        default="Topic heat high ({heat:.2f}), using AI judgment",
        zh_CN="话题热度高 ({heat:.2f})，走AI判断",
        zh_TW="話題熱度高 ({heat:.2f})，走AI判斷",
        en="Topic heat high ({heat:.2f}), using AI judgment",
        ja="話題の熱度高（{heat:.2f}）、AI判断に進みます",
        ru="Высокая активность темы ({heat:.2f}), AI-оценка",
    )

    # ==================== 显式记忆指令 ====================

    memory_explicit_saved: I18nKey = I18nKey(
        default="Remembered: {content}",
        zh_CN="记住了：{content}",
        zh_TW="記住了：{content}",
        en="Remembered: {content}",
        ja="覚えました：{content}",
        ru="Запомнено: {content}",
    )

    memory_explicit_duplicate: I18nKey = I18nKey(
        default="I already have this noted",
        zh_CN="这条我已经记过了",
        zh_TW="這條我已經記過了",
        en="I already have this noted",
        ja="それは既に覚えています",
        ru="Это уже записано",
    )

    memory_explicit_deleted: I18nKey = I18nKey(
        default="Forgot {count} memory item(s) about \"{content}\"",
        zh_CN="已忘记{count}条关于「{content}」的记忆",
        zh_TW="已忘記{count}條關於「{content}」的記憶",
        en="Forgot {count} memory item(s) about \"{content}\"",
        ja="「{content}」に関する記憶を{count}件忘れました",
        ru="Забыто {count} записей о «{content}»",
    )

    memory_explicit_not_found: I18nKey = I18nKey(
        default="No memory found about \"{content}\"",
        zh_CN="没有找到关于「{content}」的记忆",
        zh_TW="沒有找到關於「{content}」的記憶",
        en="No memory found about \"{content}\"",
        ja="「{content}」に関する記憶は見つかりませんでした",
        ru="Память о «{content}» не найдена",
    )

    # ==================== 配置字段描述 ====================

    cfg_enabled: I18nKey = I18nKey(
        default="Enable module",
        zh_CN="是否启用模块",
        zh_TW="是否啟用模組",
        en="Enable module",
        ja="モジュールを有効化",
        ru="Включить модуль",
    )

    cfg_max_history_length: I18nKey = I18nKey(
        default="Number of history messages to retain",
        zh_CN="历史消息保留条数",
        zh_TW="歷史訊息保留條數",
        en="Number of history messages to retain",
        ja="保持する履歴メッセージ数",
        ru="Количество сохраняемых сообщений истории",
    )

    cfg_min_reply_interval: I18nKey = I18nKey(
        default="Minimum reply interval (seconds)",
        zh_CN="最小回复间隔(秒)",
        zh_TW="最小回覆間隔（秒）",
        en="Minimum reply interval (seconds)",
        ja="最小返信間隔（秒）",
        ru="Минимальный интервал ответа (сек)",
    )

    cfg_max_message_length: I18nKey = I18nKey(
        default="Maximum single message length",
        zh_CN="单条消息最大长度",
        zh_TW="單則訊息最大長度",
        en="Maximum single message length",
        ja="単一メッセージの最大長",
        ru="Максимальная длина одного сообщения",
    )

    cfg_bot_nicknames: I18nKey = I18nKey(
        default="Bot nicknames (responds when called)",
        zh_CN="机器人昵称（被叫到时响应）",
        zh_TW="機器人暱稱（被叫到時回應）",
        en="Bot nicknames (responds when called)",
        ja="ボットのニックネーム（呼ばれた時に応答）",
        ru="Никнеймы бота (отвечает при обращении)",
    )

    cfg_pipeline: I18nKey = I18nKey(
        default="Prompt pipeline settings",
        zh_CN="注入管线设置",
        zh_TW="注入管線設定",
        en="Prompt pipeline settings",
        ja="プロンプトパイプライン設定",
        ru="Настройки пайплайна подсказок",
    )

    # ==================== Dashboard 注入管线 ====================

    pipeline_title: I18nKey = I18nKey(
        default="Prompt Injectors",
        zh_CN="提示词注入器",
        zh_TW="提示詞注入器",
        en="Prompt Injectors",
        ja="プロンプト注入器",
        ru="Инъекторы подсказок",
    )

    pipeline_desc: I18nKey = I18nKey(
        default="Injectors are concatenated by priority to build the system prompt. Toggle or reorder them.",
        zh_CN="注入器按优先级顺序拼接系统提示词。可开关、调整顺序。",
        zh_TW="注入器按優先級順序拼接系統提示詞。可開關、調整順序。",
        en="Injectors are concatenated by priority to build the system prompt. Toggle or reorder them.",
        ja="インジェクターは優先度順に連結されシステムプロンプトを構成します。切り替え・並べ替え可能です。",
        ru="Инъекторы объединяются по приоритету для построения системного промпта. Включайте/исключайте и меняйте порядок.",
    )

    pipeline_time_settings: I18nKey = I18nKey(
        default="Time narration settings",
        zh_CN="时间叙述设置",
        zh_TW="時間敘述設定",
        en="Time narration settings",
        ja="時間ナレーション設定",
        ru="Настройки временного повествования",
    )

    pipeline_time_prob: I18nKey = I18nKey(
        default="Time injection probability (0~1, 1=always)",
        zh_CN="时间注入概率 (0~1，1=总是注入)",
        zh_TW="時間注入機率 (0~1，1=總是注入)",
        en="Time injection probability (0~1, 1=always)",
        ja="時間注入確率（0〜1、1=常に注入）",
        ru="Вероятность инъекции времени (0~1, 1=всегда)",
    )

    pipeline_time_ttl: I18nKey = I18nKey(
        default="Time narration cache (seconds)",
        zh_CN="时间叙述缓存 (秒)",
        zh_TW="時間敘述快取（秒）",
        en="Time narration cache (seconds)",
        ja="時間ナレーションキャッシュ（秒）",
        ru="Кэш временного повествования (сек)",
    )

    pipeline_save: I18nKey = I18nKey(
        default="Save",
        zh_CN="保存",
        zh_TW="保存",
        en="Save",
        ja="保存",
        ru="Сохранить",
    )

    pipeline_saved: I18nKey = I18nKey(
        default="Pipeline saved",
        zh_CN="注入管线已保存",
        zh_TW="注入管線已保存",
        en="Pipeline saved",
        ja="パイプラインを保存しました",
        ru="Пайплайн сохранён",
    )

    pipeline_save_failed: I18nKey = I18nKey(
        default="Save failed",
        zh_CN="保存失败",
        zh_TW="保存失敗",
        en="Save failed",
        ja="保存に失敗しました",
        ru="Не удалось сохранить",
    )

    pipeline_load_failed: I18nKey = I18nKey(
        default="Failed to load pipeline",
        zh_CN="加载注入管线失败",
        zh_TW="載入注入管線失敗",
        en="Failed to load pipeline",
        ja="パイプラインの読み込みに失敗しました",
        ru="Не удалось загрузить пайплайн",
    )

    pipeline_empty: I18nKey = I18nKey(
        default="No injectors",
        zh_CN="无注入器",
        zh_TW="無注入器",
        en="No injectors",
        ja="インジェクターがありません",
        ru="Нет инъекторов",
    )

    pipeline_move_up: I18nKey = I18nKey(
        default="Move up",
        zh_CN="上移",
        zh_TW="上移",
        en="Move up",
        ja="上へ移動",
        ru="Вверх",
    )

    pipeline_move_down: I18nKey = I18nKey(
        default="Move down",
        zh_CN="下移",
        zh_TW="下移",
        en="Move down",
        ja="下へ移動",
        ru="Вниз",
    )

    page_title: I18nKey = I18nKey(
        default="QvQChat",
        zh_CN="QvQChat 管理面板",
        zh_TW="QvQChat 管理面板",
        en="QvQChat",
        ja="QvQChat 管理パネル",
        ru="QvQChat панель управления",
    )

    page_desc: I18nKey = I18nKey(
        default="Smart dialogue module · Manage AI models, behaviors, agents, knowledge base and memory",
        zh_CN="智能对话模块 · 管理 AI 模型、行为、智能体、知识库与记忆",
        zh_TW="智慧對話模組 · 管理 AI 模型、行為、智慧體、知識庫與記憶",
        en="Smart dialogue module · Manage AI models, behaviors, agents, knowledge base and memory",
        ja="スマート対話モジュール · AIモデル、行動、エージェント、知識ベース、記憶を管理",
        ru="Интеллектуальный чат-модуль · Управление моделями, поведением, агентами, базой знаний и памятью",
    )

    # ==================== Dashboard 标签页 ====================

    tab_overview: I18nKey = I18nKey(
        default="Overview",
        zh_CN="概览",
        zh_TW="概覽",
        en="Overview",
        ja="概要",
        ru="Обзор",
    )

    tab_basic: I18nKey = I18nKey(
        default="Basic Settings",
        zh_CN="基础设置",
        zh_TW="基礎設定",
        en="Basic Settings",
        ja="基本設定",
        ru="Основные настройки",
    )

    tab_models: I18nKey = I18nKey(
        default="Models",
        zh_CN="模型管理",
        zh_TW="模型管理",
        en="Models",
        ja="モデル管理",
        ru="Модели",
    )

    tab_behaviors: I18nKey = I18nKey(
        default="Behaviors",
        zh_CN="行为管理",
        zh_TW="行為管理",
        en="Behaviors",
        ja="行動管理",
        ru="Поведение",
    )

    tab_pipeline: I18nKey = I18nKey(
        default="Pipeline",
        zh_CN="注入管线",
        zh_TW="注入管線",
        en="Pipeline",
        ja="パイプライン",
        ru="Пайплайн",
    )

    tab_agents: I18nKey = I18nKey(
        default="Agents",
        zh_CN="多智能体",
        zh_TW="多智慧體",
        en="Agents",
        ja="マルチエージェント",
        ru="Агенты",
    )

    tab_knowledge: I18nKey = I18nKey(
        default="Knowledge Base",
        zh_CN="知识库",
        zh_TW="知識庫",
        en="Knowledge Base",
        ja="知識ベース",
        ru="База знаний",
    )

    tab_tools: I18nKey = I18nKey(
        default="MCP Tools",
        zh_CN="MCP工具",
        zh_TW="MCP工具",
        en="MCP Tools",
        ja="MCPツール",
        ru="MCP-инструменты",
    )

    tab_stickers: I18nKey = I18nKey(
        default="Stickers",
        zh_CN="表情包",
        zh_TW="表情包",
        en="Stickers",
        ja="スタンプ",
        ru="Стикеры",
    )

    tab_memories: I18nKey = I18nKey(
        default="Memories",
        zh_CN="记忆管理",
        zh_TW="記憶管理",
        en="Memories",
        ja="記憶管理",
        ru="Память",
    )

    tab_sessions: I18nKey = I18nKey(
        default="Sessions",
        zh_CN="会话管理",
        zh_TW="會話管理",
        en="Sessions",
        ja="セッション管理",
        ru="Сессии",
    )

    tab_groups: I18nKey = I18nKey(
        default="Groups",
        zh_CN="群组管理",
        zh_TW="群組管理",
        en="Groups",
        ja="グループ管理",
        ru="Группы",
    )

    # ==================== Dashboard 按钮 ====================

    btn_export_desensitize: I18nKey = I18nKey(
        default="Desensitized Export",
        zh_CN="脱敏导出",
        zh_TW="脫敏匯出",
        en="Desensitized Export",
        ja="匿名化エクスポート",
        ru="Экспорт с десенсибилизацией",
    )

    btn_export_migrate: I18nKey = I18nKey(
        default="Migrate Export",
        zh_CN="迁移导出",
        zh_TW="遷移匯出",
        en="Migrate Export",
        ja="移行エクスポート",
        ru="Миграционный экспорт",
    )

    btn_import: I18nKey = I18nKey(
        default="Import",
        zh_CN="导入",
        zh_TW="匯入",
        en="Import",
        ja="インポート",
        ru="Импорт",
    )

    btn_reset: I18nKey = I18nKey(
        default="Reset All",
        zh_CN="重置全部",
        zh_TW="重設全部",
        en="Reset All",
        ja="全てリセット",
        ru="Сбросить всё",
    )

    btn_save_config: I18nKey = I18nKey(
        default="Save Config",
        zh_CN="保存配置",
        zh_TW="保存設定",
        en="Save Config",
        ja="設定を保存",
        ru="Сохранить настройки",
    )

    # ==================== Dashboard 概览区块 ====================

    overview_runtime: I18nKey = I18nKey(
        default="Runtime Status",
        zh_CN="运行状态",
        zh_TW="運行狀態",
        en="Runtime Status",
        ja="実行状態",
        ru="Статус",
    )

    overview_stats: I18nKey = I18nKey(
        default="Runtime Statistics",
        zh_CN="运行统计",
        zh_TW="運行統計",
        en="Runtime Statistics",
        ja="実行統計",
        ru="Статистика",
    )

    overview_ai: I18nKey = I18nKey(
        default="AI Subsystem Status",
        zh_CN="AI 子系统状态",
        zh_TW="AI 子系統狀態",
        en="AI Subsystem Status",
        ja="AIサブシステム状態",
        ru="Статус AI-подсистемы",
    )

    overview_features: I18nKey = I18nKey(
        default="Feature Toggles",
        zh_CN="功能开关",
        zh_TW="功能開關",
        en="Feature Toggles",
        ja="機能トグル",
        ru="Переключатели функций",
    )

    overview_human: I18nKey = I18nKey(
        default="Human State",
        zh_CN="人类状态",
        zh_TW="人類狀態",
        en="Human State",
        ja="人間状態",
        ru="Состояние человека",
    )
