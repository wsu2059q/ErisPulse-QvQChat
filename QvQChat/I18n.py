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
        en='History messages to retain',
        ja='保持する履歴メッセージ数',
        ru='Хранимые сообщения истории',
    )

    cfg_min_reply_interval: I18nKey = I18nKey(
        default="Minimum reply interval (seconds)",
        zh_CN="最小回复间隔(秒)",
        zh_TW="最小回覆間隔（秒）",
        en='Min reply interval (s)',
        ja='最小返信間隔（秒）',
        ru='Мин. интервал ответа (с)',
    )

    cfg_max_message_length: I18nKey = I18nKey(
        default="Maximum single message length",
        zh_CN="单条消息最大长度",
        zh_TW="單則訊息最大長度",
        en='Max single message length',
        ja='単一メッセージの最大長',
        ru='Макс. длина одного сообщения',
    )

    cfg_bot_nicknames: I18nKey = I18nKey(
        default="Bot nicknames (responds when called)",
        zh_CN="机器人昵称（被叫到时响应）",
        zh_TW="機器人暱稱（被叫到時回應）",
        en='Bot nicknames (comma-separated)',
        ja='ボットのニックネーム（カンマ区切り）',
        ru='Никнеймы бота (через запятую)',
    )

    cfg_pipeline: I18nKey = I18nKey(
        default="Prompt pipeline settings",
        zh_CN="注入管线设置",
        zh_TW="注入管線設定",
        en='Prompt pipeline settings',
        ja='プロンプトパイプライン設定',
        ru='Настройки пайплайна подсказок',
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

    tab_render: I18nKey = I18nKey(
        default='Rendering',
        zh_CN='渲染能力',
        zh_TW='渲染能力',
        en='Rendering',
        ja='Rendering',
        ru='Rendering',
    )

    render_available: I18nKey = I18nKey(
        default='Rendering enabled',
        zh_CN='渲染已启用',
        zh_TW='渲染已启用',
        en='Rendering enabled',
        ja='Rendering enabled',
        ru='Rendering enabled',
    )

    render_not_available: I18nKey = I18nKey(
        default='Rendering unavailable (Takumi module required)',
        zh_CN='渲染不可用（需安装 Takumi 模块）',
        zh_TW='渲染不可用（需安装 Takumi 模块）',
        en='Rendering unavailable (Takumi module required)',
        ja='Rendering unavailable (Takumi module required)',
        ru='Rendering unavailable (Takumi module required)',
    )



    btn_edit: I18nKey = I18nKey(
        default='Edit',
        zh_CN='编辑',
        zh_TW='编辑',
        en='Edit',
        ja='Edit',
        ru='Edit',
    )

    btn_delete: I18nKey = I18nKey(
        default='Delete',
        zh_CN='删除',
        zh_TW='删除',
        en='Delete',
        ja='Delete',
        ru='Delete',
    )

    toast_render_load_failed: I18nKey = I18nKey(
        default='Failed to load render config',
        zh_CN='加载渲染配置失败',
        zh_TW='加载渲染配置失败',
        en='Failed to load render config',
        ja='Failed to load render config',
        ru='Failed to load render config',
    )






    ov_mood: I18nKey = I18nKey(
        default='情绪',
        zh_CN='情绪',
        zh_TW='情绪',
        en='Mood',
        ja='気分',
        ru='Настроение',
    )

    ov_energy: I18nKey = I18nKey(
        default='精力',
        zh_CN='精力',
        zh_TW='精力',
        en='Energy',
        ja='精力',
        ru='Энергия',
    )

    toast_overview_failed: I18nKey = I18nKey(
        default='加载概览失败',
        zh_CN='加载概览失败',
        zh_TW='加载概览失败',
        en='Failed to load overview',
        ja='概要の読み込みに失敗しました',
        ru='Не удалось загрузить обзор',
    )

    toast_behavior_load_failed: I18nKey = I18nKey(
        default='加载行为失败',
        zh_CN='加载行为失败',
        zh_TW='加载行为失败',
        en='Failed to load behaviors',
        ja='行動の読み込みに失敗しました',
        ru='Не удалось загрузить поведение',
    )

    toast_model_load_failed: I18nKey = I18nKey(
        default='加载模型失败',
        zh_CN='加载模型失败',
        zh_TW='加载模型失败',
        en='Failed to load models',
        ja='モデルの読み込みに失敗しました',
        ru='Не удалось загрузить модели',
    )

    toast_agent_load_failed: I18nKey = I18nKey(
        default='加载智能体失败',
        zh_CN='加载智能体失败',
        zh_TW='加载智能体失败',
        en='Failed to load agents',
        ja='エージェントの読み込みに失敗しました',
        ru='Не удалось загрузить агентов',
    )

    toast_knowledge_load_failed: I18nKey = I18nKey(
        default='加载知识库失败',
        zh_CN='加载知识库失败',
        zh_TW='加载知识库失败',
        en='Failed to load knowledge',
        ja='知識の読み込みに失敗しました',
        ru='Не удалось загрузить знания',
    )

    toast_tool_load_failed: I18nKey = I18nKey(
        default='加载工具失败',
        zh_CN='加载工具失败',
        zh_TW='加载工具失败',
        en='Failed to load tools',
        ja='ツールの読み込みに失敗しました',
        ru='Не удалось загрузить инструменты',
    )


    modal_edit_model: I18nKey = I18nKey(
        default='编辑模型',
        zh_CN='编辑模型',
        zh_TW='编辑模型',
        en='Edit Model',
        ja='Edit Model',
        ru='Edit Model',
    )

    modal_add_model: I18nKey = I18nKey(
        default='添加模型',
        zh_CN='添加模型',
        zh_TW='添加模型',
        en='Add Model',
        ja='Add Model',
        ru='Add Model',
    )

    modal_edit_behavior: I18nKey = I18nKey(
        default='编辑行为',
        zh_CN='编辑行为',
        zh_TW='编辑行为',
        en='Edit Behavior',
        ja='Edit Behavior',
        ru='Edit Behavior',
    )

    modal_add_behavior: I18nKey = I18nKey(
        default='添加行为',
        zh_CN='添加行为',
        zh_TW='添加行为',
        en='Add Behavior',
        ja='Add Behavior',
        ru='Add Behavior',
    )

    modal_edit_agent: I18nKey = I18nKey(
        default='编辑智能体',
        zh_CN='编辑智能体',
        zh_TW='编辑智能体',
        en='Edit Agent',
        ja='Edit Agent',
        ru='Edit Agent',
    )

    modal_create_agent: I18nKey = I18nKey(
        default='创建智能体',
        zh_CN='创建智能体',
        zh_TW='创建智能体',
        en='Create Agent',
        ja='Create Agent',
        ru='Create Agent',
    )

    modal_edit_knowledge: I18nKey = I18nKey(
        default='编辑知识',
        zh_CN='编辑知识',
        zh_TW='编辑知识',
        en='Edit Knowledge',
        ja='Edit Knowledge',
        ru='Edit Knowledge',
    )

    modal_add_knowledge: I18nKey = I18nKey(
        default='添加知识',
        zh_CN='添加知识',
        zh_TW='添加知识',
        en='Add Knowledge',
        ja='Add Knowledge',
        ru='Add Knowledge',
    )

    modal_edit_tool: I18nKey = I18nKey(
        default='编辑工具',
        zh_CN='编辑工具',
        zh_TW='编辑工具',
        en='Edit Tool',
        ja='Edit Tool',
        ru='Edit Tool',
    )

    modal_add_tool: I18nKey = I18nKey(
        default='添加工具',
        zh_CN='添加工具',
        zh_TW='添加工具',
        en='Add Tool',
        ja='Add Tool',
        ru='Add Tool',
    )

    modal_edit_mcp_server: I18nKey = I18nKey(
        default='编辑 MCP 服务器',
        zh_CN='编辑 MCP 服务器',
        zh_TW='编辑 MCP 服务器',
        en='Edit MCP Server',
        ja='Edit MCP Server',
        ru='Edit MCP Server',
    )

    modal_add_mcp_server: I18nKey = I18nKey(
        default='添加 MCP 服务器',
        zh_CN='添加 MCP 服务器',
        zh_TW='添加 MCP 服务器',
        en='Add MCP Server',
        ja='Add MCP Server',
        ru='Add MCP Server',
    )

    modal__agent_id: I18nKey = I18nKey(
        default='绑定智能体',
        zh_CN='绑定智能体',
        zh_TW='绑定智能体',
        en='Agent ID',
        ja='Agent ID',
        ru='Agent ID',
    )

    modal__cap_chat: I18nKey = I18nKey(
        default='文本对话',
        zh_CN='文本对话',
        zh_TW='文本对话',
        en='Text Chat',
        ja='Text Chat',
        ru='Text Chat',
    )

    modal__cap_tools: I18nKey = I18nKey(
        default='工具调用',
        zh_CN='工具调用',
        zh_TW='工具调用',
        en='Tool Calling',
        ja='Tool Calling',
        ru='Tool Calling',
    )

    modal__cap_vision: I18nKey = I18nKey(
        default='图片识别',
        zh_CN='图片识别',
        zh_TW='图片识别',
        en='Image Recognition',
        ja='Image Recognition',
        ru='Image Recognition',
    )

    modal__catchphrases: I18nKey = I18nKey(
        default='口头禅（逗号分隔，如：嘿嘿,哎呀）',
        zh_CN='口头禅（逗号分隔，如：嘿嘿,哎呀）',
        zh_TW='口头禅（逗号分隔，如：嘿嘿,哎呀）',
        en='Catchphrases',
        ja='Catchphrases',
        ru='Catchphrases',
    )

    modal__headers: I18nKey = I18nKey(
        default='请求头 (JSON，可选)',
        zh_CN='请求头 (JSON，可选)',
        zh_TW='请求头 (JSON，可选)',
        en='Headers',
        ja='Headers',
        ru='Headers',
    )

    modal__html_extra: I18nKey = I18nKey(
        default='── 个性化设定 ──',
        zh_CN='── 个性化设定 ──',
        zh_TW='── 个性化设定 ──',
        en='Extra HTML',
        ja='Extra HTML',
        ru='Extra HTML',
    )

    modal__html_model: I18nKey = I18nKey(
        default='── 模型覆盖（留空使用默认）──',
        zh_CN='── 模型覆盖（留空使用默认）──',
        zh_TW='── 模型覆盖（留空使用默认）──',
        en='Model',
        ja='Model',
        ru='Model',
    )

    modal__html_traits: I18nKey = I18nKey(
        default='── 人格特质滑块（拖动调整，影响 AI 的性格倾向）──',
        zh_CN='── 人格特质滑块（拖动调整，影响 AI 的性格倾向）──',
        zh_TW='── 人格特质滑块（拖动调整，影响 AI 的性格倾向）──',
        en='Traits',
        ja='Traits',
        ru='Traits',
    )

    modal__knowledge_tags: I18nKey = I18nKey(
        default='知识库标签绑定（逗号分隔，仅注入匹配的知识）',
        zh_CN='知识库标签绑定（逗号分隔，仅注入匹配的知识）',
        zh_TW='知识库标签绑定（逗号分隔，仅注入匹配的知识）',
        en='Knowledge Tags',
        ja='Knowledge Tags',
        ru='Knowledge Tags',
    )

    modal__parameters: I18nKey = I18nKey(
        default='参数 JSON Schema',
        zh_CN='参数 JSON Schema',
        zh_TW='参数 JSON Schema',
        en='Parameters',
        ja='Parameters',
        ru='Parameters',
    )

    modal__t_activity: I18nKey = I18nKey(
        default='活跃度',
        zh_CN='活跃度',
        zh_TW='活跃度',
        en='Activity',
        ja='Activity',
        ru='Activity',
    )

    modal__t_curiosity: I18nKey = I18nKey(
        default='好奇心',
        zh_CN='好奇心',
        zh_TW='好奇心',
        en='Curiosity',
        ja='Curiosity',
        ru='Curiosity',
    )

    modal__t_formality: I18nKey = I18nKey(
        default='正式度',
        zh_CN='正式度',
        zh_TW='正式度',
        en='Formality',
        ja='Formality',
        ru='Formality',
    )

    modal__t_friendliness: I18nKey = I18nKey(
        default='友善度',
        zh_CN='友善度',
        zh_TW='友善度',
        en='Friendliness',
        ja='Friendliness',
        ru='Friendliness',
    )

    modal__t_humor: I18nKey = I18nKey(
        default='幽默感',
        zh_CN='幽默感',
        zh_TW='幽默感',
        en='Humor',
        ja='Humor',
        ru='Humor',
    )

    modal__tags: I18nKey = I18nKey(
        default='标签（逗号分隔）',
        zh_CN='标签（逗号分隔）',
        zh_TW='标签（逗号分隔）',
        en='Tags',
        ja='Tags',
        ru='Tags',
    )

    modal__template: I18nKey = I18nKey(
        default='从模板快速创建（选择后自动填充提示词）',
        zh_CN='从模板快速创建（选择后自动填充提示词）',
        zh_TW='从模板快速创建（选择后自动填充提示词）',
        en='Template',
        ja='Template',
        ru='Template',
    )

    modal__trigger_words: I18nKey = I18nKey(
        default='触发词（逗号分隔）',
        zh_CN='触发词（逗号分隔）',
        zh_TW='触发词（逗号分隔）',
        en='Trigger Words',
        ja='Trigger Words',
        ru='Trigger Words',
    )

    modal_api_key: I18nKey = I18nKey(
        default='API 密钥',
        zh_CN='API 密钥',
        zh_TW='API 密钥',
        en='API Key',
        ja='API Key',
        ru='API Key',
    )

    modal_base_url: I18nKey = I18nKey(
        default='API 地址',
        zh_CN='API 地址',
        zh_TW='API 地址',
        en='API URL',
        ja='API URL',
        ru='API URL',
    )

    modal_behavior_type: I18nKey = I18nKey(
        default='行为类型',
        zh_CN='行为类型',
        zh_TW='行为类型',
        en='Behavior Type',
        ja='Behavior Type',
        ru='Behavior Type',
    )

    modal_category: I18nKey = I18nKey(
        default='分类',
        zh_CN='分类',
        zh_TW='分类',
        en='Category',
        ja='Category',
        ru='Category',
    )

    modal_content: I18nKey = I18nKey(
        default='内容',
        zh_CN='内容',
        zh_TW='内容',
        en='Content',
        ja='Content',
        ru='Content',
    )

    modal_description: I18nKey = I18nKey(
        default='描述',
        zh_CN='描述',
        zh_TW='描述',
        en='Description',
        ja='Description',
        ru='Description',
    )

    modal_enable_ai: I18nKey = I18nKey(
        default='启用 AI',
        zh_CN='启用 AI',
        zh_TW='启用 AI',
        en='Enable AI',
        ja='Enable AI',
        ru='Enable AI',
    )

    modal_enable_memory: I18nKey = I18nKey(
        default='启用记忆',
        zh_CN='启用记忆',
        zh_TW='启用记忆',
        en='Enable Memory',
        ja='Enable Memory',
        ru='Enable Memory',
    )

    modal_enabled: I18nKey = I18nKey(
        default='启用',
        zh_CN='启用',
        zh_TW='启用',
        en='Enabled',
        ja='Enabled',
        ru='Enabled',
    )

    modal_endpoint: I18nKey = I18nKey(
        default='HTTP 端点（可选）',
        zh_CN='HTTP 端点（可选）',
        zh_TW='HTTP 端点（可选）',
        en='Endpoint',
        ja='Endpoint',
        ru='Endpoint',
    )

    modal_file: I18nKey = I18nKey(
        default='选择图片',
        zh_CN='选择图片',
        zh_TW='选择图片',
        en='File',
        ja='File',
        ru='File',
    )

    modal_files: I18nKey = I18nKey(
        default='选择图片文件（可多选）',
        zh_CN='选择图片文件（可多选）',
        zh_TW='选择图片文件（可多选）',
        en='Files',
        ja='Files',
        ru='Files',
    )

    modal_greeting: I18nKey = I18nKey(
        default='开场白（参考，AI 不一定每次使用）',
        zh_CN='开场白（参考，AI 不一定每次使用）',
        zh_TW='开场白（参考，AI 不一定每次使用）',
        en='Greeting',
        ja='Greeting',
        ru='Greeting',
    )

    modal_group_name: I18nKey = I18nKey(
        default='群名称',
        zh_CN='群名称',
        zh_TW='群名称',
        en='Group Name',
        ja='Group Name',
        ru='Group Name',
    )

    modal_max_tokens: I18nKey = I18nKey(
        default='最大 Tokens',
        zh_CN='最大 Tokens',
        zh_TW='最大 Tokens',
        en='Max Tokens',
        ja='Max Tokens',
        ru='Max Tokens',
    )

    modal_memory_mode: I18nKey = I18nKey(
        default='记忆模式',
        zh_CN='记忆模式',
        zh_TW='记忆模式',
        en='Memory Mode',
        ja='Memory Mode',
        ru='Memory Mode',
    )

    modal_method: I18nKey = I18nKey(
        default='请求方法',
        zh_CN='请求方法',
        zh_TW='请求方法',
        en='Method',
        ja='Method',
        ru='Method',
    )

    modal_model: I18nKey = I18nKey(
        default='指定模型 ID',
        zh_CN='指定模型 ID',
        zh_TW='指定模型 ID',
        en='Model ID',
        ja='Model ID',
        ru='Model ID',
    )

    modal_models: I18nKey = I18nKey(
        default='分配模型',
        zh_CN='分配模型',
        zh_TW='分配模型',
        en='Models',
        ja='Models',
        ru='Models',
    )

    modal_name: I18nKey = I18nKey(
        default='名称',
        zh_CN='名称',
        zh_TW='名称',
        en='Name',
        ja='Name',
        ru='Name',
    )

    modal_prediction_interval: I18nKey = I18nKey(
        default='预测间隔（消息数）',
        zh_CN='预测间隔（消息数）',
        zh_TW='预测间隔（消息数）',
        en='Prediction Interval',
        ja='Prediction Interval',
        ru='Prediction Interval',
    )

    modal_priority: I18nKey = I18nKey(
        default='优先级',
        zh_CN='优先级',
        zh_TW='优先级',
        en='Priority',
        ja='Priority',
        ru='Priority',
    )

    modal_required_capability: I18nKey = I18nKey(
        default='所需能力',
        zh_CN='所需能力',
        zh_TW='所需能力',
        en='Required Capability',
        ja='Required Capability',
        ru='Required Capability',
    )

    modal_response_template: I18nKey = I18nKey(
        default='输出模板（支持 {ai_response}/{at_user}/[img]url[/img]/[sticker]url[/sticker]）',
        zh_CN='输出模板（支持 {ai_response}/{at_user}/[img]url[/img]/[sticker]url[/sticker]）',
        zh_TW='输出模板（支持 {ai_response}/{at_user}/[img]url[/img]/[sticker]url[/sticker]）',
        en='Response Template',
        ja='Response Template',
        ru='Response Template',
    )

    modal_role: I18nKey = I18nKey(
        default='角色',
        zh_CN='角色',
        zh_TW='角色',
        en='Role',
        ja='Role',
        ru='Role',
    )

    modal_speaking_style: I18nKey = I18nKey(
        default='说话风格（如：活泼可爱、冷静理性）',
        zh_CN='说话风格（如：活泼可爱、冷静理性）',
        zh_TW='说话风格（如：活泼可爱、冷静理性）',
        en='Speaking Style',
        ja='Speaking Style',
        ru='Speaking Style',
    )

    modal_system_prompt: I18nKey = I18nKey(
        default='系统提示词',
        zh_CN='系统提示词',
        zh_TW='系统提示词',
        en='System Prompt',
        ja='System Prompt',
        ru='System Prompt',
    )

    modal_temperature: I18nKey = I18nKey(
        default='温度',
        zh_CN='温度',
        zh_TW='温度',
        en='Temperature',
        ja='Temperature',
        ru='Temperature',
    )

    modal_title: I18nKey = I18nKey(
        default='标题',
        zh_CN='标题',
        zh_TW='标题',
        en='Title',
        ja='Title',
        ru='Title',
    )

    modal_trigger_mode: I18nKey = I18nKey(
        default='触发模式',
        zh_CN='触发模式',
        zh_TW='触发模式',
        en='Trigger Mode',
        ja='Trigger Mode',
        ru='Trigger Mode',
    )

    modal_trigger_probability: I18nKey = I18nKey(
        default='触发概率 (0=从不, 1=总是)',
        zh_CN='触发概率 (0=从不, 1=总是)',
        zh_TW='触发概率 (0=从不, 1=总是)',
        en='Trigger Probability',
        ja='Trigger Probability',
        ru='Trigger Probability',
    )

    modal_url: I18nKey = I18nKey(
        default='图片 URL',
        zh_CN='图片 URL',
        zh_TW='图片 URL',
        en='URL',
        ja='URL',
        ru='URL',
    )


    toast_config_saved: I18nKey = I18nKey(
        default='配置已保存',
        zh_CN='配置已保存',
        zh_TW='配置已保存',
        en='Configuration saved',
        ja='設定を保存しました',
        ru='Настройки сохранены',
    )

    toast_model_saved: I18nKey = I18nKey(
        default='模型已保存',
        zh_CN='模型已保存',
        zh_TW='模型已保存',
        en='Model saved',
        ja='モデルを保存しました',
        ru='Модель сохранена',
    )

    toast_model_deleted: I18nKey = I18nKey(
        default='模型已删除',
        zh_CN='模型已删除',
        zh_TW='模型已删除',
        en='Model deleted',
        ja='モデルを削除しました',
        ru='Модель удалена',
    )

    toast_behavior_saved: I18nKey = I18nKey(
        default='行为已保存',
        zh_CN='行为已保存',
        zh_TW='行为已保存',
        en='Behavior saved',
        ja='行動を保存しました',
        ru='Поведение сохранено',
    )

    toast_behavior_deleted: I18nKey = I18nKey(
        default='行为已删除',
        zh_CN='行为已删除',
        zh_TW='行为已删除',
        en='Behavior deleted',
        ja='行動を削除しました',
        ru='Поведение удалено',
    )

    toast_agent_saved: I18nKey = I18nKey(
        default='智能体已保存',
        zh_CN='智能体已保存',
        zh_TW='智能体已保存',
        en='Agent saved',
        ja='エージェントを保存しました',
        ru='Агент сохранён',
    )

    toast_agent_deleted: I18nKey = I18nKey(
        default='智能体已删除',
        zh_CN='智能体已删除',
        zh_TW='智能体已删除',
        en='Agent deleted',
        ja='エージェントを削除しました',
        ru='Агент удалён',
    )

    toast_knowledge_saved: I18nKey = I18nKey(
        default='知识已保存',
        zh_CN='知识已保存',
        zh_TW='知识已保存',
        en='Knowledge saved',
        ja='知識を保存しました',
        ru='Знание сохранено',
    )

    toast_knowledge_deleted: I18nKey = I18nKey(
        default='知识已删除',
        zh_CN='知识已删除',
        zh_TW='知识已删除',
        en='Knowledge deleted',
        ja='知識を削除しました',
        ru='Знание удалено',
    )

    toast_tool_saved: I18nKey = I18nKey(
        default='工具已保存',
        zh_CN='工具已保存',
        zh_TW='工具已保存',
        en='Tool saved',
        ja='ツールを保存しました',
        ru='Инструмент сохранён',
    )

    toast_tool_deleted: I18nKey = I18nKey(
        default='工具已删除',
        zh_CN='工具已删除',
        zh_TW='工具已删除',
        en='Tool deleted',
        ja='ツールを削除しました',
        ru='Инструмент удалён',
    )

    toast_mcp_server_saved: I18nKey = I18nKey(
        default='MCP 服务器已保存',
        zh_CN='MCP 服务器已保存',
        zh_TW='MCP 服务器已保存',
        en='MCP server saved',
        ja='MCPサーバーを保存しました',
        ru='MCP-сервер сохранён',
    )

    toast_mcp_server_deleted: I18nKey = I18nKey(
        default='MCP 服务器已删除',
        zh_CN='MCP 服务器已删除',
        zh_TW='MCP 服务器已删除',
        en='MCP server deleted',
        ja='MCPサーバーを削除しました',
        ru='MCP-сервер удалён',
    )

    toast_save_failed: I18nKey = I18nKey(
        default='保存失败',
        zh_CN='保存失败',
        zh_TW='保存失败',
        en='Save failed',
        ja='保存に失敗しました',
        ru='Не удалось сохранить',
    )

    toast_delete_failed: I18nKey = I18nKey(
        default='删除失败',
        zh_CN='删除失败',
        zh_TW='删除失败',
        en='Delete failed',
        ja='削除に失敗しました',
        ru='Не удалось удалить',
    )

    toast_load_failed: I18nKey = I18nKey(
        default='加载失败',
        zh_CN='加载失败',
        zh_TW='加载失败',
        en='Load failed',
        ja='読み込みに失敗しました',
        ru='Не удалось загрузить',
    )

    toast_conn_failed: I18nKey = I18nKey(
        default='连接失败',
        zh_CN='连接失败',
        zh_TW='连接失败',
        en='Connection failed',
        ja='接続に失敗しました',
        ru='Не удалось подключиться',
    )

    toast_export_failed: I18nKey = I18nKey(
        default='导出失败',
        zh_CN='导出失败',
        zh_TW='导出失败',
        en='Export failed',
        ja='エクスポートに失敗しました',
        ru='Не удалось экспортировать',
    )

    toast_import_failed: I18nKey = I18nKey(
        default='导入失败',
        zh_CN='导入失败',
        zh_TW='导入失败',
        en='Import failed',
        ja='インポートに失敗しました',
        ru='Не удалось импортировать',
    )

    toast_reset_failed: I18nKey = I18nKey(
        default='重置失败',
        zh_CN='重置失败',
        zh_TW='重置失败',
        en='Reset failed',
        ja='リセットに失敗しました',
        ru='Не удалось сбросить',
    )

    toast_analyze_failed: I18nKey = I18nKey(
        default='分析失败',
        zh_CN='分析失败',
        zh_TW='分析失败',
        en='Analysis failed',
        ja='解析に失敗しました',
        ru='Не удалось проанализировать',
    )

    toast_unknown_error: I18nKey = I18nKey(
        default='未知错误',
        zh_CN='未知错误',
        zh_TW='未知错误',
        en='Unknown error',
        ja='不明なエラー',
        ru='Неизвестная ошибка',
    )



    cfg_message_aggregation_enabled: I18nKey = I18nKey(
        default='启用消息聚合（私聊连续发多条只回复一次）',
        zh_CN='启用消息聚合（私聊连续发多条只回复一次）',
        zh_TW='启用消息聚合（私聊连续发多条只回复一次）',
        en='Enable message aggregation (reply once for consecutive private messages)',
        ja='メッセージ集約を有効化（連続私信は一度だけ返信）',
        ru='Включить агрегацию сообщений',
    )

    cfg_message_aggregation_private_window: I18nKey = I18nKey(
        default='私聊聚合窗口(秒)',
        zh_CN='私聊聚合窗口(秒)',
        zh_TW='私聊聚合窗口(秒)',
        en='Private aggregation window (s)',
        ja='私信集約ウィンドウ（秒）',
        ru='Окно агрегации (сек)',
    )

    cfg_message_aggregation_group_window: I18nKey = I18nKey(
        default='群聊聚合窗口(秒,0=禁用)',
        zh_CN='群聊聚合窗口(秒,0=禁用)',
        zh_TW='群聊聚合窗口(秒,0=禁用)',
        en='Group aggregation window (s, 0=off)',
        ja='グループ集約ウィンドウ（秒、0=無効）',
        ru='Окно агрегации в группах (с, 0=выкл)',
    )

    cfg_message_aggregation_max_buffer: I18nKey = I18nKey(
        default='最大缓冲消息数',
        zh_CN='最大缓冲消息数',
        zh_TW='最大缓冲消息数',
        en='Max buffered messages',
        ja='最大バッファメッセージ数',
        ru='Макс. буферизуемых сообщений',
    )



    cfg_humanize_typing_delay: I18nKey = I18nKey(
        default='打字延迟（模拟输入时间）',
        zh_CN='打字延迟（模拟输入时间）',
        zh_TW='打字延迟（模拟输入时间）',
        en='Typing delay (simulate input time)',
        ja='入力時間を模したタイピング遅延',
        ru='Задержка набора (имитация ввода)',
    )

    cfg_humanize_multi_msg_enabled: I18nKey = I18nKey(
        default='多条消息分割',
        zh_CN='多条消息分割',
        zh_TW='多条消息分割',
        en='Split into multiple messages',
        ja='複数メッセージに分割',
        ru='Делить на несколько сообщений',
    )

    cfg_humanize_min_delay: I18nKey = I18nKey(
        default='最小延迟(秒)',
        zh_CN='最小延迟(秒)',
        zh_TW='最小延迟(秒)',
        en='Min delay (s)',
        ja='最小遅延（秒）',
        ru='Мин. задержка (с)',
    )

    cfg_humanize_max_delay: I18nKey = I18nKey(
        default='最大延迟(秒)',
        zh_CN='最大延迟(秒)',
        zh_TW='最大延迟(秒)',
        en='Max delay (s)',
        ja='最大遅延（秒）',
        ru='Макс. задержка (с)',
    )

    cfg_humanize_random_at_probability: I18nKey = I18nKey(
        default='群聊随机@对方概率',
        zh_CN='群聊随机@对方概率',
        zh_TW='群聊随机@对方概率',
        en='Random @ probability in groups',
        ja='グループでランダム@する確率',
        ru='Вероятность случайного @ в группах',
    )

    cfg_humanize_typo_probability: I18nKey = I18nKey(
        default='错字概率(0~1)',
        zh_CN='错字概率(0~1)',
        zh_TW='错字概率(0~1)',
        en='Typo probability (0~1)',
        ja='誤字確率（0〜1）',
        ru='Вероятность опечаток (0~1)',
    )

    cfg_humanize_half_send_probability: I18nKey = I18nKey(
        default='半句发出概率(0~1)',
        zh_CN='半句发出概率(0~1)',
        zh_TW='半句发出概率(0~1)',
        en='Half-send probability (0~1)',
        ja='半端送信確率（0〜1）',
        ru='Вероятность неполной отправки (0~1)',
    )

    cfg_humanize_read_receipt_skip: I18nKey = I18nKey(
        default='已读不回概率(0~1)',
        zh_CN='已读不回概率(0~1)',
        zh_TW='已读不回概率(0~1)',
        en='Read-receipt-skip probability (0~1)',
        ja='既読スキップ確率（0〜1）',
        ru='Вероятность пропуска прочтения (0~1)',
    )

    cfg_human_state_enabled: I18nKey = I18nKey(
        default='启用情绪/精力系统',
        zh_CN='启用情绪/精力系统',
        zh_TW='启用情绪/精力系统',
        en='Enable mood/energy system',
        ja='気分/精力システムを有効化',
        ru='Включить систему настроения/энергии',
    )

    cfg_humanize_mood_aware: I18nKey = I18nKey(
        default='将情绪状态注入提示词',
        zh_CN='将情绪状态注入提示词',
        zh_TW='将情绪状态注入提示词',
        en='Inject mood state into prompt',
        ja='プロンプトに気分状態を注入',
        ru='Внедрять состояние настроения в промпт',
    )

    cfg_human_state_mood: I18nKey = I18nKey(
        default='当前情绪',
        zh_CN='当前情绪',
        zh_TW='当前情绪',
        en='Current mood',
        ja='現在の気分',
        ru='Текущее настроение',
    )

    cfg_human_state_energy: I18nKey = I18nKey(
        default='当前精力',
        zh_CN='当前精力',
        zh_TW='当前精力',
        en='Current energy',
        ja='現在の精力',
        ru='Текущая энергия',
    )

    cfg_human_state_sleep_schedule_enabled: I18nKey = I18nKey(
        default='启用作息时间（深夜精力下降）',
        zh_CN='启用作息时间（深夜精力下降）',
        zh_TW='启用作息时间（深夜精力下降）',
        en='Enable sleep schedule (lower energy at night)',
        ja='睡眠スケジュールを有効化（夜は精力低下）',
        ru='Включить расписание сна',
    )

    cfg_human_state_sleep_schedule_sleep_time: I18nKey = I18nKey(
        default='睡觉时间(时)',
        zh_CN='睡觉时间(时)',
        zh_TW='睡觉时间(时)',
        en='Sleep time (hour)',
        ja='就寝時間（時）',
        ru='Время сна (час)',
    )

    cfg_human_state_sleep_schedule_wake_time: I18nKey = I18nKey(
        default='起床时间(时)',
        zh_CN='起床时间(时)',
        zh_TW='起床时间(时)',
        en='Wake time (hour)',
        ja='起床時間（時）',
        ru='Время подъёма (час)',
    )

    cfg_human_state_proactive_message_enabled: I18nKey = I18nKey(
        default='启用主动发起对话',
        zh_CN='启用主动发起对话',
        zh_TW='启用主动发起对话',
        en='Enable proactive messages',
        ja='積極的な発話を有効化',
        ru='Включить проактивные сообщения',
    )

    cfg_human_state_proactive_message_min_silence_hours: I18nKey = I18nKey(
        default='最小沉寂小时',
        zh_CN='最小沉寂小时',
        zh_TW='最小沉寂小时',
        en='Min silence hours',
        ja='最小沈黙時間（時間）',
        ru='Мин. часов тишины',
    )

    cfg_human_state_proactive_message_probability: I18nKey = I18nKey(
        default='主动发起概率(0~1)',
        zh_CN='主动发起概率(0~1)',
        zh_TW='主动发起概率(0~1)',
        en='Proactive probability (0~1)',
        ja='積極発話確率（0〜1）',
        ru='Вероятность проактивности (0~1)',
    )

    cfg_human_state_proactive_message_check_interval_minutes: I18nKey = I18nKey(
        default='检查间隔(分钟)',
        zh_CN='检查间隔(分钟)',
        zh_TW='检查间隔(分钟)',
        en='Check interval (minutes)',
        ja='チェック間隔（分）',
        ru='Интервал проверки (мин)',
    )

    cfg_human_state_proactive_message_max_per_day: I18nKey = I18nKey(
        default='每日上限',
        zh_CN='每日上限',
        zh_TW='每日上限',
        en='Daily limit',
        ja='1日の上限',
        ru='Дневной лимит',
    )

    cfg_stalker_mode_enabled: I18nKey = I18nKey(
        default='启用窥屏模式',
        zh_CN='启用窥屏模式',
        zh_TW='启用窥屏模式',
        en='Enable stalker mode',
        ja='ストーカーモードを有効化',
        ru='Включить режим наблюдения',
    )

    cfg_stalker_mode_default_probability: I18nKey = I18nKey(
        default='基础回复概率',
        zh_CN='基础回复概率',
        zh_TW='基础回复概率',
        en='Base reply probability',
        ja='基本返信確率',
        ru='Базовая вероятность ответа',
    )

    cfg_stalker_mode_question_probability: I18nKey = I18nKey(
        default='提问触发概率',
        zh_CN='提问触发概率',
        zh_TW='提问触发概率',
        en='Question trigger probability',
        ja='質問トリガー確率',
        ru='Вероятность ответа на вопрос',
    )

    cfg_stalker_mode_hot_topic_probability: I18nKey = I18nKey(
        default='热度触发概率',
        zh_CN='热度触发概率',
        zh_TW='热度触发概率',
        en='Hot topic trigger probability',
        ja='ホットトピック確率',
        ru='Вероятность горячей темы',
    )

    cfg_stalker_mode_sticker_emoji_probability: I18nKey = I18nKey(
        default='表情触发概率',
        zh_CN='表情触发概率',
        zh_TW='表情触发概率',
        en='Sticker/emoji trigger probability',
        ja='スタンプ/絵文字確率',
        ru='Вероятность стикера/эмодзи',
    )

    cfg_stalker_mode_night_mode_enabled: I18nKey = I18nKey(
        default='启用夜间窥屏',
        zh_CN='启用夜间窥屏',
        zh_TW='启用夜间窥屏',
        en='Enable night stalker mode',
        ja='夜間ストーカーを有効化',
        ru='Включить ночной режим',
    )

    cfg_stalker_mode_night_mode_begin: I18nKey = I18nKey(
        default='开始(时)',
        zh_CN='开始(时)',
        zh_TW='开始(时)',
        en='Start (hour)',
        ja='開始（時）',
        ru='Начало (час)',
    )

    cfg_stalker_mode_night_mode_end: I18nKey = I18nKey(
        default='结束(时)',
        zh_CN='结束(时)',
        zh_TW='结束(时)',
        en='End (hour)',
        ja='終了（時）',
        ru='Конец (час)',
    )

    cfg_continue_conversation_enabled: I18nKey = I18nKey(
        default='启用对话连续性',
        zh_CN='启用对话连续性',
        zh_TW='启用对话连续性',
        en='Enable conversation continuity',
        ja='会話継続を有効化',
        ru='Включить продолжение беседы',
    )

    cfg_continue_conversation_max_messages: I18nKey = I18nKey(
        default='最大监听消息数',
        zh_CN='最大监听消息数',
        zh_TW='最大监听消息数',
        en='Max listened messages',
        ja='最大リスン数',
        ru='Макс. прослушиваемых сообщений',
    )

    cfg_continue_conversation_max_duration: I18nKey = I18nKey(
        default='监听时长（秒）',
        zh_CN='监听时长（秒）',
        zh_TW='监听时长（秒）',
        en='Listen duration (s)',
        ja='リスン時間（秒）',
        ru='Длительность прослушивания (с)',
    )

    cfg_knowledge_base_enabled: I18nKey = I18nKey(
        default='启用知识库注入',
        zh_CN='启用知识库注入',
        zh_TW='启用知识库注入',
        en='Enable knowledge base injection',
        ja='知識ベース注入を有効化',
        ru='Включить инъекцию базы знаний',
    )

    cfg_knowledge_base_auto_search: I18nKey = I18nKey(
        default='自动搜索匹配',
        zh_CN='自动搜索匹配',
        zh_TW='自动搜索匹配',
        en='Auto search matching',
        ja='自動検索マッチング',
        ru='Автопоиск совпадений',
    )

    cfg_knowledge_base_max_context_tokens: I18nKey = I18nKey(
        default='最大上下文 Tokens',
        zh_CN='最大上下文 Tokens',
        zh_TW='最大上下文 Tokens',
        en='Max context tokens',
        ja='最大コンテキストトークン',
        ru='Макс. токенов контекста',
    )

    cfg_memory_dedup_enabled: I18nKey = I18nKey(
        default='记忆去重',
        zh_CN='记忆去重',
        zh_TW='记忆去重',
        en='Memory deduplication',
        ja='記憶の重複排除',
        ru='Дедупликация памяти',
    )

    cfg_memory_decay_enabled: I18nKey = I18nKey(
        default='记忆遗忘衰减',
        zh_CN='记忆遗忘衰减',
        zh_TW='记忆遗忘衰减',
        en='Memory decay',
        ja='記憶の減衰',
        ru='Забывание памяти',
    )

    cfg_memory_decay_days: I18nKey = I18nKey(
        default='衰减天数',
        zh_CN='衰减天数',
        zh_TW='衰减天数',
        en='Decay days',
        ja='減衰日数',
        ru='Дней до забывания',
    )

    cfg_memory_max_per_user: I18nKey = I18nKey(
        default='每用户最大记忆数',
        zh_CN='每用户最大记忆数',
        zh_TW='每用户最大记忆数',
        en='Max memories per user',
        ja='ユーザーごとの最大記憶数',
        ru='Макс. воспоминаний на пользователя',
    )

    cfg_mcp_enabled: I18nKey = I18nKey(
        default='启用 MCP 工具',
        zh_CN='启用 MCP 工具',
        zh_TW='启用 MCP 工具',
        en='Enable MCP tools',
        ja='MCPツールを有効化',
        ru='Включить MCP-инструменты',
    )

    cfg_mcp_auto_inject: I18nKey = I18nKey(
        default='自动注入工具定义',
        zh_CN='自动注入工具定义',
        zh_TW='自动注入工具定义',
        en='Auto-inject tool definitions',
        ja='ツール定義を自動注入',
        ru='Автовнедрение определений инструментов',
    )

    cfg_multi_agent_enabled: I18nKey = I18nKey(
        default='启用多智能体',
        zh_CN='启用多智能体',
        zh_TW='启用多智能体',
        en='Enable multi-agent',
        ja='マルチエージェントを有効化',
        ru='Включить мультиагентов',
    )

    cfg_stickers_enabled: I18nKey = I18nKey(
        default='启用表情包功能',
        zh_CN='启用表情包功能',
        zh_TW='启用表情包功能',
        en='Enable stickers',
        ja='スタンプを有効化',
        ru='Включить стикеры',
    )

    cfg_stickers_probability: I18nKey = I18nKey(
        default='表情包触发概率 (0~1)',
        zh_CN='表情包触发概率 (0~1)',
        zh_TW='表情包触发概率 (0~1)',
        en='Sticker trigger probability (0~1)',
        ja='スタンプ確率（0〜1）',
        ru='Вероятность стикера (0~1)',
    )

    cfg_stickers_max_per_session: I18nKey = I18nKey(
        default='每轮对话最多次数',
        zh_CN='每轮对话最多次数',
        zh_TW='每轮对话最多次数',
        en='Max per conversation round',
        ja='会話1回の最大回数',
        ru='Макс. за раунд беседы',
    )

    cfg_voice_enabled: I18nKey = I18nKey(
        default='启用语音合成',
        zh_CN='启用语音合成',
        zh_TW='启用语音合成',
        en='Enable voice synthesis',
        ja='音声合成を有効化',
        ru='Включить синтез речи',
    )

    cfg_voice_api_url: I18nKey = I18nKey(
        default='API 地址',
        zh_CN='API 地址',
        zh_TW='API 地址',
        en='API URL',
        ja='API URL',
        ru='API URL',
    )

    cfg_voice_model: I18nKey = I18nKey(
        default='模型',
        zh_CN='模型',
        zh_TW='模型',
        en='Model',
        ja='モデル',
        ru='Модель',
    )

    cfg_voice_api_key: I18nKey = I18nKey(
        default='API 密钥',
        zh_CN='API 密钥',
        zh_TW='API 密钥',
        en='API Key',
        ja='APIキー',
        ru='API-ключ',
    )

    cfg_voice_voice: I18nKey = I18nKey(
        default='音色',
        zh_CN='音色',
        zh_TW='音色',
        en='Voice',
        ja='音声',
        ru='Голос',
    )

    cfg_voice_speed: I18nKey = I18nKey(
        default='语速',
        zh_CN='语速',
        zh_TW='语速',
        en='Speed',
        ja='速度',
        ru='Скорость',
    )

    cfg_voice_sample_rate: I18nKey = I18nKey(
        default='采样率',
        zh_CN='采样率',
        zh_TW='采样率',
        en='Sample rate',
        ja='サンプルレート',
        ru='Частота дискретизации',
    )


    cfg_rate_limit_tokens: I18nKey = I18nKey(
        default='速率限制 Tokens',
        zh_CN='速率限制 Tokens',
        zh_TW='速率限制 Tokens',
        en='Rate limit tokens',
        ja='レート制限トークン',
        ru='Лимит токенов',
    )

    cfg_rate_limit_window: I18nKey = I18nKey(
        default='速率限制窗口(秒)',
        zh_CN='速率限制窗口(秒)',
        zh_TW='速率限制窗口(秒)',
        en='Rate limit window (s)',
        ja='レート制限ウィンドウ（秒）',
        ru='Окно лимита (с)',
    )

    section_robot_identity: I18nKey = I18nKey(
        default='机器人身份',
        zh_CN='机器人身份',
        zh_TW='机器人身份',
        en='Robot Identity',
        ja='ロボットのアイデンティティ',
        ru='Личность бота',
    )

    section_aggregation: I18nKey = I18nKey(
        default='消息聚合（对话窗口）',
        zh_CN='消息聚合（对话窗口）',
        zh_TW='消息聚合（对话窗口）',
        en='Message Aggregation (dialogue window)',
        ja='メッセージ集約（会話ウィンドウ）',
        ru='Агрегация сообщений',
    )

    section_message_limits: I18nKey = I18nKey(
        default='消息限制',
        zh_CN='消息限制',
        zh_TW='消息限制',
        en='Message Limits',
        ja='メッセージ制限',
        ru='Лимиты сообщений',
    )

    section_typing_pace: I18nKey = I18nKey(
        default='打字与回复节奏',
        zh_CN='打字与回复节奏',
        zh_TW='打字与回复节奏',
        en='Typing & Reply Pace',
        ja='タイピングと返信のペース',
        ru='Темп набора и ответов',
    )

    section_imperfect_input: I18nKey = I18nKey(
        default='不完美输入（错字/半句/已读不回）',
        zh_CN='不完美输入（错字/半句/已读不回）',
        zh_TW='不完美输入（错字/半句/已读不回）',
        en='Imperfect Input (typos/half-send/read-skip)',
        ja='不完全入力（誤字/半端/既読スキップ）',
        ru='Несовершенный ввод',
    )

    section_human_state: I18nKey = I18nKey(
        default='情绪/精力/作息/主动发起',
        zh_CN='情绪/精力/作息/主动发起',
        zh_TW='情绪/精力/作息/主动发起',
        en='Mood / Energy / Schedule / Proactive',
        ja='気分/精力/スケジュール/積極発話',
        ru='Настроение/энергия/расписание',
    )

    section_stalker: I18nKey = I18nKey(
        default='窥屏模式',
        zh_CN='窥屏模式',
        zh_TW='窥屏模式',
        en='Stalker Mode',
        ja='ストーカーモード',
        ru='Режим наблюдения',
    )

    section_reply_probs: I18nKey = I18nKey(
        default='回复触发概率',
        zh_CN='回复触发概率',
        zh_TW='回复触发概率',
        en='Reply Trigger Probabilities',
        ja='返信トリガー確率',
        ru='Вероятности ответа',
    )

    section_night_mode: I18nKey = I18nKey(
        default='夜间模式',
        zh_CN='夜间模式',
        zh_TW='夜间模式',
        en='Night Mode',
        ja='夜間モード',
        ru='Ночной режим',
    )

    section_continue_conversation: I18nKey = I18nKey(
        default='对话连续性',
        zh_CN='对话连续性',
        zh_TW='对话连续性',
        en='Conversation Continuity',
        ja='会話継続',
        ru='Продолжение беседы',
    )

    section_knowledge: I18nKey = I18nKey(
        default='知识库',
        zh_CN='知识库',
        zh_TW='知识库',
        en='Knowledge Base',
        ja='知識ベース',
        ru='База знаний',
    )

    section_memory: I18nKey = I18nKey(
        default='记忆系统',
        zh_CN='记忆系统',
        zh_TW='记忆系统',
        en='Memory System',
        ja='記憶システム',
        ru='Система памяти',
    )

    section_mcp: I18nKey = I18nKey(
        default='MCP 工具',
        zh_CN='MCP 工具',
        zh_TW='MCP 工具',
        en='MCP Tools',
        ja='MCPツール',
        ru='MCP-инструменты',
    )

    section_multi_agent: I18nKey = I18nKey(
        default='多智能体',
        zh_CN='多智能体',
        zh_TW='多智能体',
        en='Multi-Agent',
        ja='マルチエージェント',
        ru='Мультиагенты',
    )

    section_stickers: I18nKey = I18nKey(
        default='表情包',
        zh_CN='表情包',
        zh_TW='表情包',
        en='Stickers',
        ja='スタンプ',
        ru='Стикеры',
    )

    section_voice: I18nKey = I18nKey(
        default='语音合成',
        zh_CN='语音合成',
        zh_TW='语音合成',
        en='Voice Synthesis',
        ja='音声合成',
        ru='Синтез речи',
    )

    section_rate_limits: I18nKey = I18nKey(
        default='速率限制',
        zh_CN='速率限制',
        zh_TW='速率限制',
        en='Rate Limits',
        ja='レート制限',
        ru='Лимиты запросов',
    )

    settings_identity: I18nKey = I18nKey(
        default='身份与消息',
        zh_CN='身份与消息',
        zh_TW='身份与消息',
        en='Identity & Messages',
        ja='アイデンティティとメッセージ',
        ru='Личность и сообщения',
    )

    settings_humanize: I18nKey = I18nKey(
        default='拟人化',
        zh_CN='拟人化',
        zh_TW='拟人化',
        en='Humanization',
        ja='人間らしさ',
        ru='Очеловечивание',
    )

    settings_stalker: I18nKey = I18nKey(
        default='窥屏策略',
        zh_CN='窥屏策略',
        zh_TW='窥屏策略',
        en='Stalker Strategy',
        ja='ストーカー戦略',
        ru='Стратегия наблюдения',
    )

    settings_features: I18nKey = I18nKey(
        default='功能开关',
        zh_CN='功能开关',
        zh_TW='功能开关',
        en='Feature Toggles',
        ja='機能トグル',
        ru='Переключатели функций',
    )

    settings_advanced: I18nKey = I18nKey(
        default='高级',
        zh_CN='高级',
        zh_TW='高级',
        en='Advanced',
        ja='詳細設定',
        ru='Дополнительно',
    )

    opt_mode_conservative: I18nKey = I18nKey(
        default='保守（仅回复@/叫名字）',
        zh_CN='保守（仅回复@/叫名字）',
        zh_TW='保守（仅回复@/叫名字）',
        en='Conservative (only reply when @ or named)',
        ja='保守（@または名前時のみ）',
        ru='Консервативный',
    )

    opt_mode_balanced: I18nKey = I18nKey(
        default='均衡（默认）',
        zh_CN='均衡（默认）',
        zh_TW='均衡（默认）',
        en='Balanced (default)',
        ja='バランス（デフォルト）',
        ru='Сбалансированный',
    )

    opt_mode_active: I18nKey = I18nKey(
        default='积极（频繁参与）',
        zh_CN='积极（频繁参与）',
        zh_TW='积极（频繁参与）',
        en='Active (frequent participation)',
        ja='積極的（頻繁に参加）',
        ru='Активный',
    )


    btn_save: I18nKey = I18nKey(
        default='Save',
        zh_CN='保存',
        zh_TW='保存',
        en='Save',
        ja='保存',
        ru='保存',
    )

    btn_cancel: I18nKey = I18nKey(
        default='Cancel',
        zh_CN='取消',
        zh_TW='取消',
        en='Cancel',
        ja='取消',
        ru='取消',
    )

    btn_delete: I18nKey = I18nKey(
        default='Delete',
        zh_CN='删除',
        zh_TW='删除',
        en='Delete',
        ja='删除',
        ru='删除',
    )

    btn_clear: I18nKey = I18nKey(
        default='Clear',
        zh_CN='清空',
        zh_TW='清空',
        en='Clear',
        ja='清空',
        ru='清空',
    )

    btn_refresh: I18nKey = I18nKey(
        default='Refresh',
        zh_CN='刷新',
        zh_TW='刷新',
        en='Refresh',
        ja='刷新',
        ru='刷新',
    )

    btn_add: I18nKey = I18nKey(
        default='Add',
        zh_CN='添加',
        zh_TW='添加',
        en='Add',
        ja='添加',
        ru='添加',
    )

    btn_select_all: I18nKey = I18nKey(
        default='Select All',
        zh_CN='全选',
        zh_TW='全选',
        en='Select All',
        ja='全选',
        ru='全选',
    )

    btn_done: I18nKey = I18nKey(
        default='Done',
        zh_CN='完成',
        zh_TW='完成',
        en='Done',
        ja='完成',
        ru='完成',
    )

    ov_ai_models: I18nKey = I18nKey(
        default='AI Models',
        zh_CN='AI 模型',
        zh_TW='AI 模型',
        en='AI Models',
        ja='AI 模型',
        ru='AI 模型',
    )

    ov_behaviors: I18nKey = I18nKey(
        default='Behaviors',
        zh_CN='行为定义',
        zh_TW='行为定义',
        en='Behaviors',
        ja='行为定义',
        ru='行为定义',
    )

    ov_agents: I18nKey = I18nKey(
        default='Agents',
        zh_CN='智能体',
        zh_TW='智能体',
        en='Agents',
        ja='智能体',
        ru='智能体',
    )

    ov_knowledge: I18nKey = I18nKey(
        default='Knowledge Entries',
        zh_CN='知识条目',
        zh_TW='知识条目',
        en='Knowledge Entries',
        ja='知识条目',
        ru='知识条目',
    )

    ov_mcp_tools: I18nKey = I18nKey(
        default='MCP Tools',
        zh_CN='MCP 工具',
        zh_TW='MCP 工具',
        en='MCP Tools',
        ja='MCP 工具',
        ru='MCP 工具',
    )

    ov_stickers: I18nKey = I18nKey(
        default='Stickers',
        zh_CN='表情包',
        zh_TW='表情包',
        en='Stickers',
        ja='表情包',
        ru='表情包',
    )

    ov_active_groups: I18nKey = I18nKey(
        default='Active Groups',
        zh_CN='活跃群组',
        zh_TW='活跃群组',
        en='Active Groups',
        ja='活跃群组',
        ru='活跃群组',
    )

    ov_uptime: I18nKey = I18nKey(
        default='Uptime',
        zh_CN='运行时间',
        zh_TW='运行时间',
        en='Uptime',
        ja='运行时间',
        ru='运行时间',
    )

    ov_received: I18nKey = I18nKey(
        default='Messages Received',
        zh_CN='接收消息',
        zh_TW='接收消息',
        en='Messages Received',
        ja='接收消息',
        ru='接收消息',
    )

    ov_replied: I18nKey = I18nKey(
        default='Replies Sent',
        zh_CN='发送回复',
        zh_TW='发送回复',
        en='Replies Sent',
        ja='发送回复',
        ru='发送回复',
    )

    ov_reply_rate: I18nKey = I18nKey(
        default='Reply Rate',
        zh_CN='回复率',
        zh_TW='回复率',
        en='Reply Rate',
        ja='回复率',
        ru='回复率',
    )

    ov_est_tokens: I18nKey = I18nKey(
        default='Estimated Tokens',
        zh_CN='估算 Token',
        zh_TW='估算 Token',
        en='Estimated Tokens',
        ja='估算 Token',
        ru='估算 Token',
    )

    ov_dialogue: I18nKey = I18nKey(
        default='Dialogue',
        zh_CN='对话行为',
        zh_TW='对话行为',
        en='Dialogue',
        ja='对话行为',
        ru='对话行为',
    )

    ov_memory: I18nKey = I18nKey(
        default='Memory',
        zh_CN='记忆提取',
        zh_TW='记忆提取',
        en='Memory',
        ja='记忆提取',
        ru='记忆提取',
    )

    ov_intent: I18nKey = I18nKey(
        default='Intent',
        zh_CN='意图识别',
        zh_TW='意图识别',
        en='Intent',
        ja='意图识别',
        ru='意图识别',
    )

    ov_vision: I18nKey = I18nKey(
        default='Vision',
        zh_CN='图片分析',
        zh_TW='图片分析',
        en='Vision',
        ja='图片分析',
        ru='图片分析',
    )

    ov_reply_judge: I18nKey = I18nKey(
        default='Reply Judge',
        zh_CN='回复判断',
        zh_TW='回复判断',
        en='Reply Judge',
        ja='回复判断',
        ru='回复判断',
    )

    status_ok: I18nKey = I18nKey(
        default='OK',
        zh_CN='正常',
        zh_TW='正常',
        en='OK',
        ja='正常',
        ru='正常',
    )

    status_not_ready: I18nKey = I18nKey(
        default='Not Ready',
        zh_CN='未就绪',
        zh_TW='未就绪',
        en='Not Ready',
        ja='未就绪',
        ru='未就绪',
    )

    status_enabled: I18nKey = I18nKey(
        default='Enabled',
        zh_CN='已启用',
        zh_TW='已启用',
        en='Enabled',
        ja='已启用',
        ru='已启用',
    )

    status_disabled: I18nKey = I18nKey(
        default="Disabled",
        zh_CN="已关闭",
        zh_TW="已關閉",
        en="Disabled",
        ja="無効",
        ru="Выключено",
    )

    toggle_failed: I18nKey = I18nKey(
        default="Toggle failed",
        zh_CN="切换失败",
        zh_TW="切換失敗",
        en="Toggle failed",
        ja="切替に失敗しました",
        ru="Не удалось переключить",
    )

    feat_stalker: I18nKey = I18nKey(
        default='Stalker Mode',
        zh_CN='窥屏模式',
        zh_TW='窥屏模式',
        en='Stalker Mode',
        ja='窥屏模式',
        ru='窥屏模式',
    )

    feat_continue_conversation: I18nKey = I18nKey(
        default='Conversation Continuity',
        zh_CN='对话连续性',
        zh_TW='对话连续性',
        en='Conversation Continuity',
        ja='对话连续性',
        ru='对话连续性',
    )

    feat_knowledge: I18nKey = I18nKey(
        default='Knowledge Injection',
        zh_CN='知识库注入',
        zh_TW='知识库注入',
        en='Knowledge Injection',
        ja='知识库注入',
        ru='知识库注入',
    )

    feat_mcp: I18nKey = I18nKey(
        default='MCP Tool Calls',
        zh_CN='MCP 工具调用',
        zh_TW='MCP 工具调用',
        en='MCP Tool Calls',
        ja='MCP 工具调用',
        ru='MCP 工具调用',
    )

    feat_multi_agent: I18nKey = I18nKey(
        default='Multi-Agent',
        zh_CN='多智能体',
        zh_TW='多智能体',
        en='Multi-Agent',
        ja='多智能体',
        ru='多智能体',
    )

    feat_voice: I18nKey = I18nKey(
        default='Voice Synthesis',
        zh_CN='语音合成',
        zh_TW='语音合成',
        en='Voice Synthesis',
        ja='语音合成',
        ru='语音合成',
    )

    badge_enabled: I18nKey = I18nKey(
        default='Enabled',
        zh_CN='启用',
        zh_TW='启用',
        en='Enabled',
        ja='启用',
        ru='启用',
    )

    badge_disabled: I18nKey = I18nKey(
        default='Disabled',
        zh_CN='禁用',
        zh_TW='禁用',
        en='Disabled',
        ja='禁用',
        ru='禁用',
    )

    badge_builtin: I18nKey = I18nKey(
        default='Builtin',
        zh_CN='内置',
        zh_TW='内置',
        en='Builtin',
        ja='内置',
        ru='内置',
    )

    badge_default: I18nKey = I18nKey(
        default='Default',
        zh_CN='默认',
        zh_TW='默认',
        en='Default',
        ja='默认',
        ru='默认',
    )

    badge_connected: I18nKey = I18nKey(
        default='Connected',
        zh_CN='已连接',
        zh_TW='已连接',
        en='Connected',
        ja='已连接',
        ru='已连接',
    )

    badge_disconnected: I18nKey = I18nKey(
        default='Disconnected',
        zh_CN='未连接',
        zh_TW='未连接',
        en='Disconnected',
        ja='未连接',
        ru='未连接',
    )

    badge_ai_on: I18nKey = I18nKey(
        default='AI On',
        zh_CN='AI启用',
        zh_TW='AI启用',
        en='AI On',
        ja='AI启用',
        ru='AI启用',
    )

    badge_ai_off: I18nKey = I18nKey(
        default='AI Off',
        zh_CN='AI关闭',
        zh_TW='AI关闭',
        en='AI Off',
        ja='AI关闭',
        ru='AI关闭',
    )

    badge_mem_on: I18nKey = I18nKey(
        default='Memory',
        zh_CN='记忆',
        zh_TW='记忆',
        en='Memory',
        ja='记忆',
        ru='记忆',
    )

    badge_mem_off: I18nKey = I18nKey(
        default='No Memory',
        zh_CN='无记忆',
        zh_TW='无记忆',
        en='No Memory',
        ja='无记忆',
        ru='无记忆',
    )

    badge_text: I18nKey = I18nKey(
        default='Text',
        zh_CN='文本',
        zh_TW='文本',
        en='Text',
        ja='文本',
        ru='文本',
    )

    badge_vision: I18nKey = I18nKey(
        default='Vision',
        zh_CN='视觉',
        zh_TW='视觉',
        en='Vision',
        ja='视觉',
        ru='视觉',
    )

    badge_tools: I18nKey = I18nKey(
        default='Tools',
        zh_CN='工具',
        zh_TW='工具',
        en='Tools',
        ja='工具',
        ru='工具',
    )

    empty_no_models: I18nKey = I18nKey(
        default='No models yet. Click Add to create one.',
        zh_CN='暂无模型，点击右上角添加',
        zh_TW='暂无模型，点击右上角添加',
        en='No models yet. Click Add to create one.',
        ja='暂无模型，点击右上角添加',
        ru='暂无模型，点击右上角添加',
    )

    empty_no_behaviors: I18nKey = I18nKey(
        default='No behaviors defined',
        zh_CN='暂无行为定义',
        zh_TW='暂无行为定义',
        en='No behaviors defined',
        ja='暂无行为定义',
        ru='暂无行为定义',
    )

    empty_no_agents: I18nKey = I18nKey(
        default='No agents yet. Click Create to add one.',
        zh_CN='暂无智能体，点击右上角创建',
        zh_TW='暂无智能体，点击右上角创建',
        en='No agents yet. Click Create to add one.',
        ja='暂无智能体，点击右上角创建',
        ru='暂无智能体，点击右上角创建',
    )

    empty_no_knowledge: I18nKey = I18nKey(
        default='No knowledge entries',
        zh_CN='暂无知识条目',
        zh_TW='暂无知识条目',
        en='No knowledge entries',
        ja='暂无知识条目',
        ru='暂无知识条目',
    )

    empty_no_tools: I18nKey = I18nKey(
        default='No tools defined',
        zh_CN='暂无工具定义',
        zh_TW='暂无工具定义',
        en='No tools defined',
        ja='暂无工具定义',
        ru='暂无工具定义',
    )

    empty_no_stickers: I18nKey = I18nKey(
        default='No stickers. Click Upload to add.',
        zh_CN='暂无表情包。点击「上传表情包」添加。',
        zh_TW='暂无表情包。点击「上传表情包」添加。',
        en='No stickers. Click Upload to add.',
        ja='暂无表情包。点击「上传表情包」添加。',
        ru='暂无表情包。点击「上传表情包」添加。',
    )

    empty_no_memories: I18nKey = I18nKey(
        default='No memories stored',
        zh_CN='暂无存储的记忆',
        zh_TW='暂无存储的记忆',
        en='No memories stored',
        ja='暂无存储的记忆',
        ru='暂无存储的记忆',
    )

    empty_no_memories_match: I18nKey = I18nKey(
        default='No matching memories',
        zh_CN='未找到匹配的记忆',
        zh_TW='未找到匹配的记忆',
        en='No matching memories',
        ja='未找到匹配的记忆',
        ru='未找到匹配的记忆',
    )

    empty_no_sessions: I18nKey = I18nKey(
        default='No session records',
        zh_CN='暂无会话记录',
        zh_TW='暂无会话记录',
        en='No session records',
        ja='暂无会话记录',
        ru='暂无会话记录',
    )

    empty_no_sessions_match: I18nKey = I18nKey(
        default='No matching sessions',
        zh_CN='未找到匹配的会话',
        zh_TW='未找到匹配的会话',
        en='No matching sessions',
        ja='未找到匹配的会话',
        ru='未找到匹配的会话',
    )

    empty_no_groups: I18nKey = I18nKey(
        default='No groups (groups auto-register on first message)',
        zh_CN='暂无群组（群组在收到第一条消息后自动注册）',
        zh_TW='暂无群组（群组在收到第一条消息后自动注册）',
        en='No groups (groups auto-register on first message)',
        ja='暂无群组（群组在收到第一条消息后自动注册）',
        ru='暂无群组（群组在收到第一条消息后自动注册）',
    )

