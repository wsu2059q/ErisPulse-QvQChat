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
