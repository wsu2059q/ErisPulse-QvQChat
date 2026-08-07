"""Dashboard JavaScript 常量"""

SCRIPTS = r"""
// ==================== 全局状态 ====================
var _qvcLoaded = {};
var _qvcModalCallback = null;
var _qvcModalFields = [];
var _qvcBasicConfig = {};
var _qvcPipelineList = [];

// ==================== API 辅助 ====================
async function qvcApi(path, method, body) {
    var token = localStorage.getItem('__ep_tk__');
    var opts = {
        method: method || 'GET',
        headers: {
            'Authorization': 'Bearer ' + (token || ''),
            'Content-Type': 'application/json'
        }
    };
    if (body !== undefined && method !== 'GET') {
        opts.body = JSON.stringify(body);
    }
    var resp = await fetch('/QvQChat' + path, opts);
    var data = await resp.json();
    if (!resp.ok || data.error) {
        throw new Error(data.error || ('HTTP ' + resp.status));
    }
    return data;
}

// ==================== 工具函数 ====================
// i18n 翻译辅助（翻译字典由后端注入 _qvcI18n）
function qvcT(key, fallback) {
    if (typeof _qvcI18n !== 'undefined' && _qvcI18n && _qvcI18n[key]) {
        return _qvcI18n[key];
    }
    return fallback || key;
}

// 统一应用页面级 i18n（标题/副标题/标签/按钮）
var _qvcI18nMap = {
    'qvc-page-title': 'page.title',
    'qvc-page-desc': 'page.desc',
    'qvc-tab-overview': 'tab.overview',
    'qvc-tab-basic': 'tab.basic',
    'qvc-tab-models': 'tab.models',
    'qvc-tab-behaviors': 'tab.behaviors',
    'qvc-tab-pipeline': 'tab.pipeline',
    'qvc-tab-agents': 'tab.agents',
    'qvc-tab-knowledge': 'tab.knowledge',
    'qvc-tab-tools': 'tab.tools',
    'qvc-tab-stickers': 'tab.stickers',
    'qvc-tab-memories': 'tab.memories',
    'qvc-tab-sessions': 'tab.sessions',
    'qvc-tab-groups': 'tab.groups',
    'qvc-btn-export-desensitize': 'btn.export_desensitize',
    'qvc-btn-export-migrate': 'btn.export_migrate',
    'qvc-btn-import': 'btn.import',
    'qvc-btn-reset': 'btn.reset',
    'qvc-btn-save-basic-label': 'btn.save_config',
    'qvc-ov-title-runtime': 'overview.runtime',
    'qvc-ov-title-stats': 'overview.stats',
    'qvc-ov-title-ai': 'overview.ai',
    'qvc-ov-title-features': 'overview.features',
    'qvc-ov-title-human': 'overview.human'
};

function qvcApplyI18n() {
    for (var eid in _qvcI18nMap) {
        var el = document.getElementById(eid);
        if (el) el.textContent = qvcT(_qvcI18nMap[eid], el.textContent);
    }
}

// 实时拉取 i18n 翻译（跟随框架语言切换），拉取后重新应用
async function qvcLoadI18n() {
    try {
        var data = await qvcApi('/api/i18n', 'GET');
        if (data && typeof data === 'object') {
            _qvcI18n = data;
            qvcApplyI18n();
            return true;
        }
    } catch (e) {
        // 拉取失败时保留注入的快照
    }
    return false;
}

function qvcToast(msg, type) {
    var existing = document.querySelector('.qvc-toast');
    if (existing) existing.remove();
    var el = document.createElement('div');
    el.className = 'qvc-toast qvc-toast-' + (type || 'info');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function() {
        el.style.opacity = '0';
        el.style.transition = 'opacity .3s';
        setTimeout(function() { el.remove(); }, 300);
    }, 2500);
}

function qvcEsc(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function qvcSetPath(obj, path, value) {
    var keys = path.split('.');
    var cur = obj;
    for (var i = 0; i < keys.length - 1; i++) {
        if (!cur[keys[i]] || typeof cur[keys[i]] !== 'object') {
            cur[keys[i]] = {};
        }
        cur = cur[keys[i]];
    }
    cur[keys[keys.length - 1]] = value;
}

function qvcGetPath(obj, path, def) {
    var keys = path.split('.');
    var cur = obj;
    for (var i = 0; i < keys.length; i++) {
        if (cur == null || typeof cur !== 'object') return def;
        cur = cur[keys[i]];
    }
    return cur !== undefined ? cur : def;
}

// ==================== 标签切换 ====================
function qvcTab(name) {
    document.querySelectorAll('.qvc-tab').forEach(function(t) {
        t.classList.toggle('active', t.getAttribute('data-tab') === name);
    });
    document.querySelectorAll('.qvc-panel').forEach(function(p) {
        p.classList.toggle('active', p.id === 'qvc-panel-' + name);
    });
    if (!_qvcLoaded[name]) {
        _qvcLoaded[name] = true;
        var loaders = {
            overview: qvcLoadOverview,
            basic: qvcLoadBasic,
            models: qvcLoadModels,
            behaviors: qvcLoadBehaviors,
            pipeline: qvcLoadPipeline,
            agents: qvcLoadAgents,
            knowledge: qvcLoadKnowledge,
            tools: qvcLoadTools,
            stickers: qvcLoadStickers,
            memories: qvcLoadMemories,
            sessions: qvcLoadSessions,
            groups: qvcLoadGroups
        };
        if (loaders[name]) loaders[name]();
    }
}

// ==================== 概览 ====================
async function qvcLoadOverview() {
    try {
        var data = await qvcApi('/api/status', 'GET');
        // 统计卡片
        var stats = data.stats || {};
        var modelStats = stats.models || {};
        var behaviorStats = stats.behaviors || {};
        var kbStats = stats.knowledge || {};
        var toolStats = stats.tools || {};
        var agentStats = stats.agents || {};
        var stickerStats = stats.stickers || {};

        var cards = [
            { num: modelStats.total || 0, label: qvcT('ov.ai_models', 'AI 模型') },
            { num: behaviorStats.total || 0, label: qvcT('ov.behaviors', '行为定义') },
            { num: agentStats.total || 0, label: qvcT('ov.agents', '智能体') },
            { num: kbStats.total || 0, label: qvcT('ov.knowledge', '知识条目') },
            { num: toolStats.total || 0, label: qvcT('ov.mcp_tools', 'MCP 工具') },
            { num: stickerStats.total || 0, label: qvcT('ov.stickers', '表情包') },
            { num: data.active_groups || 0, label: qvcT('ov.active_groups', '活跃群组') }
        ];

        var html = '';
        cards.forEach(function(c) {
            html += '<div class="qvc-stat-card">';
            html += '<div class="qvc-stat-num">' + c.num + '</div>';
            html += '<div class="qvc-stat-label">' + qvcEsc(c.label) + '</div>';
            html += '</div>';
        });
        document.getElementById('qvc-overview-stats').innerHTML = html;

        // 运行统计
        var rt = data.runtime || {};
        var rtCards = [
            { num: rt.uptime || '-', label: qvcT('ov.uptime', '运行时间') },
            { num: rt.total_messages || 0, label: qvcT('ov.received', '接收消息') },
            { num: rt.total_replies || 0, label: qvcT('ov.replied', '发送回复') },
            { num: rt.reply_rate || '0%', label: qvcT('ov.reply_rate', '回复率') },
            { num: (rt.total_tokens_est || 0).toLocaleString(), label: qvcT('ov.est_tokens', '估算 Token') }
        ];
        var rtHtml = '';
        rtCards.forEach(function(c) {
            rtHtml += '<div class="qvc-stat-card">';
            rtHtml += '<div class="qvc-stat-num" style="font-size:20px">' + qvcEsc(c.num) + '</div>';
            rtHtml += '<div class="qvc-stat-label">' + qvcEsc(c.label) + '</div>';
            rtHtml += '</div>';
        });
        var rtEl = document.getElementById('qvc-overview-runtime');
        if (rtEl) rtEl.innerHTML = rtHtml;

        // AI 子系统状态
        var aiStatus = data.ai_status || {};
        var rows = [
            { label: qvcT('ov.dialogue', '对话行为'), ok: aiStatus.dialogue },
            { label: qvcT('ov.memory', '记忆提取'), ok: aiStatus.memory },
            { label: qvcT('ov.intent', '意图识别'), ok: aiStatus.intent },
            { label: qvcT('ov.vision', '图片分析'), ok: aiStatus.vision },
            { label: qvcT('ov.reply_judge', '回复判断'), ok: aiStatus.reply_judge }
        ];
        var aiHtml = '';
        rows.forEach(function(r) {
            var cls = r.ok ? 'qvc-badge-ok' : 'qvc-badge-off';
            var txt = r.ok ? qvcT('status.ok', '正常') : qvcT('status.not_ready', '未就绪');
            aiHtml += '<div class="qvc-list-item">';
            aiHtml += '<div class="qvc-list-item-info"><div class="qvc-list-item-title">' + qvcEsc(r.label) + '</div></div>';
            aiHtml += '<span class="qvc-badge ' + cls + '">' + txt + '</span>';
            aiHtml += '</div>';
        });
        document.getElementById('qvc-overview-ai').innerHTML = aiHtml;

        // 功能开关（可交互）
        var features = data.features || {};
        var featHtml = '';
        var featMap = [
            { key: 'stalker_mode', label: qvcT('feat.stalker', '窥屏模式'), path: 'stalker_mode.enabled' },
            { key: 'continue_conversation', label: qvcT('feat.continue_conversation', '对话连续性'), path: 'continue_conversation.enabled' },
            { key: 'knowledge_base', label: qvcT('feat.knowledge', '知识库注入'), path: 'knowledge_base.enabled' },
            { key: 'mcp', label: qvcT('feat.mcp', 'MCP 工具调用'), path: 'mcp.enabled' },
            { key: 'multi_agent', label: qvcT('feat.multi_agent', '多智能体'), path: 'multi_agent.enabled' },
            { key: 'voice', label: qvcT('feat.voice', '语音合成'), path: 'voice.enabled' }
        ];
        featMap.forEach(function(f) {
            var on = features[f.key];
            var cls = on ? 'qvc-badge-ok' : 'qvc-badge-off';
            var txt = on ? qvcT('status.enabled', '已启用') : qvcT('status.disabled', '已关闭');
            featHtml += '<div class="qvc-list-item" style="cursor:pointer" onclick="qvcToggleFeature(\'' + f.path + '\', \'' + f.key + '\')">';
            featHtml += '<div class="qvc-list-item-info"><div class="qvc-list-item-title">' + qvcEsc(f.label) + '</div></div>';
            featHtml += '<span class="qvc-badge ' + cls + '" id="qvc-feat-' + f.key + '">' + txt + '</span>';
            featHtml += '</div>';
        });
        document.getElementById('qvc-overview-features').innerHTML = featHtml;

        // 人类状态（情绪/精力）
        var hs = data.human_state || {};
        var hsHtml = '';
        var moodPct = Math.round((hs.mood || 0.6) * 100);
        var energyPct = Math.round((hs.energy || 0.8) * 100);
        hsHtml += '<div class="qvc-list-item">';
        hsHtml += '<div class="qvc-list-item-info"><div class="qvc-list-item-title">' + qvcT('ov.mood', '情绪') + '</div></div>';
        hsHtml += '<div style="width:120px;height:8px;background:rgba(255,255,255,0.1);border-radius:4px;overflow:hidden;margin-right:8px"><div style="width:' + moodPct + '%;height:100%;background:linear-gradient(90deg,#f44336,#ffc107,#4caf50);border-radius:4px"></div></div>';
        hsHtml += '<span class="qvc-badge">' + (hs.mood_text || '') + ' (' + moodPct + '%)</span>';
        hsHtml += '</div>';
        hsHtml += '<div class="qvc-list-item">';
        hsHtml += '<div class="qvc-list-item-info"><div class="qvc-list-item-title">' + qvcT('ov.energy', '精力') + '</div></div>';
        hsHtml += '<div style="width:120px;height:8px;background:rgba(255,255,255,0.1);border-radius:4px;overflow:hidden;margin-right:8px"><div style="width:' + energyPct + '%;height:100%;background:linear-gradient(90deg,#9c27b0,#2196f3,#00bcd4);border-radius:4px"></div></div>';
        hsHtml += '<span class="qvc-badge">' + (hs.energy_text || '') + ' (' + energyPct + '%)</span>';
        hsHtml += '</div>';
        var hsEl = document.getElementById('qvc-overview-human-state');
        if (hsEl) hsEl.innerHTML = hsHtml;
    } catch (e) {
        qvcToast(qvcT('toast.overview_failed', '加载概览失败') + ': ' + e.message, 'error');
    }
}

async function qvcToggleFeature(path, key) {
    try {
        // 从当前 badge 的 class 读取真实当前值（避免读缓存拿到延迟 flush 前的旧值）
        var el = document.getElementById('qvc-feat-' + key);
        var cur = el ? el.classList.contains('qvc-badge-ok') : true;
        var newVal = !cur;
        var body = {};
        body[path] = newVal;
        await qvcApi('/api/config', 'POST', body);
        // 更新 UI
        if (el) {
            el.className = 'qvc-badge ' + (newVal ? 'qvc-badge-ok' : 'qvc-badge-off');
            el.textContent = newVal ? qvcT('status.enabled', '已启用') : qvcT('status.disabled', '已关闭');
        }
        qvcToast((newVal ? qvcT('status.enabled', '已启用') : qvcT('status.disabled', '已关闭')) + ': ' + key, 'ok');
    } catch (e) {
        qvcToast(qvcT('toggle.failed', '切换失败') + ': ' + e.message, 'error');
    }
}

// ==================== 基础设置（子标签页） ====================
function qvcToggleCollapse(header) {
    var card = header.parentElement;
    card.classList.toggle('expanded');
}

function qvcSettingsTab(name) {
    document.querySelectorAll('.qvc-subtab').forEach(function(t) {
        t.classList.toggle('active', t.getAttribute('data-subtab') === name);
    });
    document.querySelectorAll('.qvc-subpanel').forEach(function(p) {
        p.classList.toggle('active', p.id === 'qvc-settings-' + name);
    });
}

function qvcSlider(path, label, val, min, max, step) {
    var v = val != null ? val : (min + max) / 2;
    return '<div class="qvc-slider-group">' +
        '<div class="qvc-slider-label"><span>' + qvcEsc(qvcFieldLabel(path, label)) + '</span>' +
        '<span class="qvc-slider-val" id="slider-val-' + path.replace(/\./g, '-') + '">' + v + '</span></div>' +
        '<input type="range" class="qvc-range" data-path="' + qvcEsc(path) + '" min="' + min + '" max="' + max + '" step="' + (step || 1) + '" value="' + v + '"' +
        ' oninput="document.getElementById(\'slider-val-' + path.replace(/\./g, '-') + '\').textContent=this.value">' +
        '</div>';
}

// 折叠区块标题翻译映射
var _qvcSectionLabels = {
    '机器人身份': 'section.robot_identity',
    '消息聚合（对话窗口）': 'section.aggregation',
    '消息限制': 'section.message_limits',
    '打字与回复节奏': 'section.typing_pace',
    '不完美输入（错字/半句/已读不回）': 'section.imperfect_input',
    '情绪/精力/作息/主动发起': 'section.human_state',
    '窥屏模式': 'section.stalker',
    '回复触发概率': 'section.reply_probs',
    '夜间模式': 'section.night_mode',
    '对话连续性': 'section.continue_conversation',
    '知识库': 'section.knowledge',
    '记忆系统': 'section.memory',
    'MCP 工具': 'section.mcp',
    '多智能体': 'section.multi_agent',
    '表情包': 'section.stickers',
    '语音合成': 'section.voice',
    '速率限制': 'section.rate_limits'
};

function qvcSectionLabel(title) {
    var key = _qvcSectionLabels[title];
    return key ? qvcT(key, title) : title;
}

function qvcCollapse(title, innerHtml, expanded) {
    var cls = expanded ? ' expanded' : '';
    return '<div class="qvc-collapse' + cls + '">' +
        '<div class="qvc-collapse-header" onclick="qvcToggleCollapse(this)">' +
        '<span>' + qvcEsc(qvcSectionLabel(title)) + '</span>' +
        '<span class="qvc-collapse-arrow">▶</span></div>' +
        '<div class="qvc-collapse-body">' + innerHtml + '</div></div>';
}

async function qvcLoadBasic() {
    try {
        var data = await qvcApi('/api/config', 'GET');
        _qvcBasicConfig = data.config || data || {};
        var cfg = _qvcBasicConfig;
        var html = '';

        // 子标签栏
        html += '<div class="qvc-subtabs">';
        html += '<div class="qvc-subtab active" data-subtab="identity" onclick="qvcSettingsTab(\'identity\')">' + qvcT('settings.identity', '身份与消息') + '</div>';
        html += '<div class="qvc-subtab" data-subtab="humanize" onclick="qvcSettingsTab(\'humanize\')">' + qvcT('settings.humanize', '拟人化') + '</div>';
        html += '<div class="qvc-subtab" data-subtab="stalker" onclick="qvcSettingsTab(\'stalker\')">' + qvcT('settings.stalker', '窥屏策略') + '</div>';
        html += '<div class="qvc-subtab" data-subtab="features" onclick="qvcSettingsTab(\'features\')">' + qvcT('settings.features', '功能开关') + '</div>';
        html += '<div class="qvc-subtab" data-subtab="advanced" onclick="qvcSettingsTab(\'advanced\')">' + qvcT('settings.advanced', '高级') + '</div>';
        html += '</div>';

        // ===== 子面板1: 身份与消息 =====
        var identityHtml = '';
        identityHtml += qvcCollapse('机器人身份', 
            qvcArrayField('bot_nicknames', '机器人昵称（逗号分隔）', qvcGetPath(cfg, 'bot_nicknames', [])),
            true);
        var aggHtml = qvcCheckField('message_aggregation.enabled', '启用消息聚合（私聊连续发多条只回复一次）', qvcGetPath(cfg, 'message_aggregation.enabled', true));
        aggHtml += '<div class="qvc-form-row">';
        aggHtml += qvcNumField('message_aggregation.private_window', '私聊聚合窗口(秒)', qvcGetPath(cfg, 'message_aggregation.private_window', 3.0));
        aggHtml += qvcNumField('message_aggregation.group_window', '群聊聚合窗口(秒,0=禁用)', qvcGetPath(cfg, 'message_aggregation.group_window', 0));
        aggHtml += '</div>';
        aggHtml += qvcNumField('message_aggregation.max_buffer', '最大缓冲消息数', qvcGetPath(cfg, 'message_aggregation.max_buffer', 8));
        identityHtml += qvcCollapse('消息聚合（对话窗口）', aggHtml, true);
        var limitHtml = '<div class="qvc-form-row">';
        limitHtml += qvcNumField('max_message_length', '单条消息最大长度', qvcGetPath(cfg, 'max_message_length', 1000));
        limitHtml += qvcNumField('max_history_length', '历史消息保留条数', qvcGetPath(cfg, 'max_history_length', 20));
        limitHtml += '</div>';
        identityHtml += qvcCollapse('消息限制', limitHtml, false);

        html += '<div class="qvc-subpanel active" id="qvc-settings-identity">' + identityHtml + '</div>';

        // ===== 子面板2: 拟人化 =====
        var humHtml = '';
        var delayHtml = qvcCheckField('humanize.typing_delay', '打字延迟（模拟输入时间）', qvcGetPath(cfg, 'humanize.typing_delay', true));
        delayHtml += qvcCheckField('humanize.multi_msg_enabled', '多条消息分割', qvcGetPath(cfg, 'humanize.multi_msg_enabled', true));
        delayHtml += '<div class="qvc-form-row">';
        delayHtml += qvcNumField('humanize.min_delay', '最小延迟(秒)', qvcGetPath(cfg, 'humanize.min_delay', 0.5));
        delayHtml += qvcNumField('humanize.max_delay', '最大延迟(秒)', qvcGetPath(cfg, 'humanize.max_delay', 5.0));
        delayHtml += '</div>';
        delayHtml += qvcNumField('humanize.random_at_probability', '群聊随机@对方概率', qvcGetPath(cfg, 'humanize.random_at_probability', 0.15));
        humHtml += qvcCollapse('打字与回复节奏', delayHtml, true);

        var typoHtml = '<p style="font-size:12px;color:var(--tx-s);margin:0 0 10px">模拟真人的不完美输入行为。概率值越高，出现频率越高。</p>';
        typoHtml += '<div class="qvc-form-row">';
        typoHtml += qvcNumField('humanize.typo_probability', '错字概率(0~1)', qvcGetPath(cfg, 'humanize.typo_probability', 0.08));
        typoHtml += qvcNumField('humanize.half_send_probability', '半句发出概率(0~1)', qvcGetPath(cfg, 'humanize.half_send_probability', 0.06));
        typoHtml += '</div>';
        typoHtml += qvcNumField('humanize.read_receipt_skip', '已读不回概率(0~1)', qvcGetPath(cfg, 'humanize.read_receipt_skip', 0.05));
        humHtml += qvcCollapse('不完美输入（错字/半句/已读不回）', typoHtml, false);

        var moodHtml = qvcCheckField('human_state.enabled', '启用情绪/精力系统', qvcGetPath(cfg, 'human_state.enabled', true));
        moodHtml += qvcCheckField('humanize.mood_aware', '将情绪状态注入提示词', qvcGetPath(cfg, 'humanize.mood_aware', true));
        moodHtml += '<div class="qvc-form-row">';
        moodHtml += qvcSlider('human_state.mood', '当前情绪', qvcGetPath(cfg, 'human_state.mood', 0.6), 0, 1, 0.05);
        moodHtml += qvcSlider('human_state.energy', '当前精力', qvcGetPath(cfg, 'human_state.energy', 0.8), 0, 1, 0.05);
        moodHtml += '</div>';
        moodHtml += qvcCheckField('human_state.sleep_schedule.enabled', '启用作息时间（深夜精力下降）', qvcGetPath(cfg, 'human_state.sleep_schedule.enabled', false));
        moodHtml += '<div class="qvc-form-row">';
        moodHtml += qvcNumField('human_state.sleep_schedule.sleep_time', '睡觉时间(时)', qvcGetPath(cfg, 'human_state.sleep_schedule.sleep_time', 2));
        moodHtml += qvcNumField('human_state.sleep_schedule.wake_time', '起床时间(时)', qvcGetPath(cfg, 'human_state.sleep_schedule.wake_time', 8));
        moodHtml += '</div>';
        moodHtml += qvcCheckField('human_state.proactive_message.enabled', '启用主动发起对话', qvcGetPath(cfg, 'human_state.proactive_message.enabled', false));
        moodHtml += '<div class="qvc-form-row">';
        moodHtml += qvcNumField('human_state.proactive_message.min_silence_hours', '最小沉寂小时', qvcGetPath(cfg, 'human_state.proactive_message.min_silence_hours', 6));
        moodHtml += qvcNumField('human_state.proactive_message.probability', '主动发起概率(0~1)', qvcGetPath(cfg, 'human_state.proactive_message.probability', 0.1));
        moodHtml += '</div>';
        moodHtml += '<div class="qvc-form-row">';
        moodHtml += qvcNumField('human_state.proactive_message.check_interval_minutes', '检查间隔(分钟)', qvcGetPath(cfg, 'human_state.proactive_message.check_interval_minutes', 30));
        moodHtml += qvcNumField('human_state.proactive_message.max_per_day', '每日上限', qvcGetPath(cfg, 'human_state.proactive_message.max_per_day', 1));
        moodHtml += '</div>';
        humHtml += qvcCollapse('情绪/精力/作息/主动发起', moodHtml, false);

        html += '<div class="qvc-subpanel" id="qvc-settings-humanize">' + humHtml + '</div>';

        // ===== 子面板3: 窥屏策略 =====
        var stalkHtml = '';
        var modeHtml = '<div class="qvc-form-row">';
        modeHtml += qvcSelectField('stalker_mode.mode', '回复策略', qvcGetPath(cfg, 'stalker_mode.mode', 'balanced'), [
            { label: '保守（仅回复@/叫名字）', i18nKey: 'opt.mode.conservative', value: 'conservative' },
            { label: '均衡（默认）', i18nKey: 'opt.mode.balanced', value: 'balanced' },
            { label: '积极（频繁参与）', i18nKey: 'opt.mode.active', value: 'active' }
        ]);
        modeHtml += qvcCheckField('stalker_mode.enabled', '启用窥屏模式', qvcGetPath(cfg, 'stalker_mode.enabled', true));
        modeHtml += '</div>';
        stalkHtml += qvcCollapse('窥屏模式', modeHtml, true);

        var probHtml = '<div class="qvc-form-row">';
        probHtml += qvcSlider('stalker_mode.default_probability', '基础回复概率', qvcGetPath(cfg, 'stalker_mode.default_probability', 0.03), 0, 1, 0.01);
        probHtml += qvcSlider('stalker_mode.question_probability', '提问触发概率', qvcGetPath(cfg, 'stalker_mode.question_probability', 0.6), 0, 1, 0.05);
        probHtml += '</div>';
        probHtml += '<div class="qvc-form-row">';
        probHtml += qvcSlider('stalker_mode.hot_topic_probability', '热度触发概率', qvcGetPath(cfg, 'stalker_mode.hot_topic_probability', 0.3), 0, 1, 0.05);
        probHtml += qvcSlider('stalker_mode.sticker_emoji_probability', '表情触发概率', qvcGetPath(cfg, 'stalker_mode.sticker_emoji_probability', 0.15), 0, 1, 0.05);
        probHtml += '</div>';
        stalkHtml += qvcCollapse('回复触发概率', probHtml, false);

        var nightHtml = '<div class="qvc-form-row">';
        nightHtml += qvcCheckField('stalker_mode.night_mode.enabled', '启用夜间窥屏', qvcGetPath(cfg, 'stalker_mode.night_mode.enabled', true));
        nightHtml += qvcNumField('stalker_mode.night_mode.begin', '开始(时)', qvcGetPath(cfg, 'stalker_mode.night_mode.begin', 23));
        nightHtml += qvcNumField('stalker_mode.night_mode.end', '结束(时)', qvcGetPath(cfg, 'stalker_mode.night_mode.end', 7));
        nightHtml += '</div>';
        stalkHtml += qvcCollapse('夜间模式', nightHtml, false);

        var contHtml = qvcCheckField('continue_conversation.enabled', '启用对话连续性', qvcGetPath(cfg, 'continue_conversation.enabled', true));
        contHtml += '<div class="qvc-form-row">';
        contHtml += qvcNumField('continue_conversation.max_messages', '最大监听消息数', qvcGetPath(cfg, 'continue_conversation.max_messages', 3));
        contHtml += qvcNumField('continue_conversation.max_duration', '监听时长（秒）', qvcGetPath(cfg, 'continue_conversation.max_duration', 120));
        contHtml += '</div>';
        stalkHtml += qvcCollapse('对话连续性', contHtml, false);

        html += '<div class="qvc-subpanel" id="qvc-settings-stalker">' + stalkHtml + '</div>';

        // ===== 子面板4: 功能开关 =====
        var featHtml = '';
        var kbHtml = qvcCheckField('knowledge_base.enabled', '启用知识库注入', qvcGetPath(cfg, 'knowledge_base.enabled', true));
        kbHtml += qvcCheckField('knowledge_base.auto_search', '自动搜索匹配', qvcGetPath(cfg, 'knowledge_base.auto_search', true));
        kbHtml += qvcNumField('knowledge_base.max_context_tokens', '最大上下文 Tokens', qvcGetPath(cfg, 'knowledge_base.max_context_tokens', 2000));
        featHtml += qvcCollapse('知识库', kbHtml, false);

        var memHtml = qvcCheckField('memory.dedup_enabled', '记忆去重', qvcGetPath(cfg, 'memory.dedup_enabled', true));
        memHtml += qvcCheckField('memory.decay_enabled', '记忆遗忘衰减', qvcGetPath(cfg, 'memory.decay_enabled', true));
        memHtml += '<div class="qvc-form-row">';
        memHtml += qvcNumField('memory.decay_days', '衰减天数', qvcGetPath(cfg, 'memory.decay_days', 30));
        memHtml += qvcNumField('memory.max_per_user', '每用户最大记忆数', qvcGetPath(cfg, 'memory.max_per_user', 100));
        memHtml += '</div>';
        featHtml += qvcCollapse('记忆系统', memHtml, false);

        var mcpHtml = qvcCheckField('mcp.enabled', '启用 MCP 工具', qvcGetPath(cfg, 'mcp.enabled', true));
        mcpHtml += qvcCheckField('mcp.auto_inject', '自动注入工具定义', qvcGetPath(cfg, 'mcp.auto_inject', true));
        featHtml += qvcCollapse('MCP 工具', mcpHtml, false);

        featHtml += qvcCollapse('多智能体', qvcCheckField('multi_agent.enabled', '启用多智能体', qvcGetPath(cfg, 'multi_agent.enabled', true)), false);

        var stickerHtml = qvcCheckField('stickers.enabled', '启用表情包功能', qvcGetPath(cfg, 'stickers.enabled', true));
        stickerHtml += '<div class="qvc-form-row">';
        stickerHtml += qvcNumField('stickers.probability', '表情包触发概率 (0~1)', qvcGetPath(cfg, 'stickers.probability', 0.3));
        stickerHtml += qvcNumField('stickers.max_per_session', '每轮对话最多次数', qvcGetPath(cfg, 'stickers.max_per_session', 2));
        stickerHtml += '</div>';
        featHtml += qvcCollapse('表情包', stickerHtml, false);

        var voiceHtml = qvcCheckField('voice.enabled', '启用语音合成', qvcGetPath(cfg, 'voice.enabled', false));
        voiceHtml += '<div class="qvc-form-row">';
        voiceHtml += qvcTextField('voice.api_url', 'API 地址', qvcGetPath(cfg, 'voice.api_url', ''));
        voiceHtml += qvcTextField('voice.model', '模型', qvcGetPath(cfg, 'voice.model', ''));
        voiceHtml += '</div>';
        voiceHtml += '<div class="qvc-form-row">';
        voiceHtml += qvcTextField('voice.api_key', 'API 密钥', qvcGetPath(cfg, 'voice.api_key', ''));
        voiceHtml += qvcTextField('voice.voice', '音色', qvcGetPath(cfg, 'voice.voice', ''));
        voiceHtml += '</div>';
        voiceHtml += '<div class="qvc-form-row">';
        voiceHtml += qvcNumField('voice.speed', '语速', qvcGetPath(cfg, 'voice.speed', 1.0));
        voiceHtml += qvcNumField('voice.sample_rate', '采样率', qvcGetPath(cfg, 'voice.sample_rate', 44100));
        voiceHtml += '</div>';
        featHtml += qvcCollapse('语音合成', voiceHtml, false);

        html += '<div class="qvc-subpanel" id="qvc-settings-features">' + featHtml + '</div>';

        // ===== 子面板5: 高级 =====
        var advHtml = '';
        var rateHtml = '<div class="qvc-form-row">';
        rateHtml += qvcNumField('min_reply_interval', '最小回复间隔(秒)', qvcGetPath(cfg, 'min_reply_interval', 10));
        rateHtml += qvcNumField('rate_limit_tokens', '速率限制 Tokens', qvcGetPath(cfg, 'rate_limit_tokens', 20000));
        rateHtml += '</div>';
        rateHtml += qvcNumField('rate_limit_window', '速率限制窗口(秒)', qvcGetPath(cfg, 'rate_limit_window', 60));
        advHtml += qvcCollapse('速率限制', rateHtml, false);
        advHtml += '<p style="font-size:12px;color:var(--tx-s);margin-top:14px">提示：这些参数控制全局速率限制，防止 API 过度调用。</p>';

        html += '<div class="qvc-subpanel" id="qvc-settings-advanced">' + advHtml + '</div>';

        document.getElementById('qvc-basic-form').innerHTML = html;
    } catch (e) {
        document.getElementById('qvc-basic-form').innerHTML = '<div class="qvc-empty">' + qvcT('toast.load_failed', '加载失败') + ': ' + qvcEsc(e.message) + '</div>';
    }
}

// 字段标签按配置路径自动翻译（cfg.<path>），无翻译时回退到中文标签
function qvcFieldLabel(path, label) {
    return qvcT('cfg.' + path, label);
}

function qvcTextField(path, label, val) {
    return '<div class="qvc-form-group">' +
        '<label>' + qvcEsc(qvcFieldLabel(path, label)) + '</label>' +
        '<input type="text" class="qvc-input" data-path="' + qvcEsc(path) + '" value="' + qvcEsc(val) + '">' +
        '</div>';
}

function qvcNumField(path, label, val) {
    return '<div class="qvc-form-group">' +
        '<label>' + qvcEsc(qvcFieldLabel(path, label)) + '</label>' +
        '<input type="number" step="any" class="qvc-input" data-path="' + qvcEsc(path) + '" value="' + qvcEsc(val) + '">' +
        '</div>';
}

function qvcCheckField(path, label, checked) {
    return '<label class="qvc-checkbox-row">' +
        '<input type="checkbox" data-path="' + qvcEsc(path) + '"' + (checked ? ' checked' : '') + '>' +
        qvcEsc(qvcFieldLabel(path, label)) +
        '</label>';
}

function qvcArrayField(path, label, arr) {
    var str = Array.isArray(arr) ? arr.join(', ') : '';
    return '<div class="qvc-form-group">' +
        '<label>' + qvcEsc(qvcFieldLabel(path, label)) + '</label>' +
        '<input type="text" class="qvc-input" data-array="' + qvcEsc(path) + '" value="' + qvcEsc(str) + '">' +
        '</div>';
}

function qvcSelectField(path, label, val, options) {
    var opts = '';
    (options || []).forEach(function(o) {
        var sel = o.value === val ? ' selected' : '';
        var olabel = o.i18nKey ? qvcT(o.i18nKey, o.label) : o.label;
        opts += '<option value="' + qvcEsc(o.value) + '"' + sel + '>' + qvcEsc(olabel) + '</option>';
    });
    return '<div class="qvc-form-group">' +
        '<label>' + qvcEsc(qvcFieldLabel(path, label)) + '</label>' +
        '<select class="qvc-input" data-path="' + qvcEsc(path) + '">' + opts + '</select>' +
        '</div>';
}

async function qvcSaveBasic() {
    try {
        var container = document.getElementById('qvc-basic-form');
        // 普通字段
        container.querySelectorAll('[data-path]').forEach(function(el) {
            var path = el.getAttribute('data-path');
            var val;
            if (el.type === 'checkbox') {
                val = el.checked;
            } else if (el.type === 'number' || el.type === 'range') {
                val = el.value === '' ? null : Number(el.value);
            } else {
                val = el.value;
            }
            qvcSetPath(_qvcBasicConfig, path, val);
        });
        // 数组字段
        container.querySelectorAll('[data-array]').forEach(function(el) {
            var path = el.getAttribute('data-array');
            var val = el.value.split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s.length > 0; });
            qvcSetPath(_qvcBasicConfig, path, val);
        });

        await qvcApi('/api/config', 'POST', { config: _qvcBasicConfig });
        qvcToast(qvcT('toast.config_saved', '配置已保存'), 'ok');
    } catch (e) {
        qvcToast(qvcT('toast.save_failed', '保存失败') + ': ' + e.message, 'error');
    }
}

// ==================== 模型管理 ====================
async function qvcLoadModels() {
    try {
        var data = await qvcApi('/api/models', 'GET');
        var models = data.models || data || [];
        var el = document.getElementById('qvc-models-list');
        if (!models.length) {
            el.innerHTML = '<div class="qvc-empty">暂无模型，点击右上角添加</div>';
            return;
        }
        var html = '';
        models.forEach(function(m) {
            var caps = m.capabilities || {};
            var badges = '';
            if (caps.chat) badges += '<span class="qvc-badge qvc-badge-ok">' + qvcT('badge.text','文本') + '</span> ';
            if (caps.vision) badges += '<span class="qvc-badge qvc-badge-ok">' + qvcT('badge.vision','视觉') + '</span> ';
            if (caps.tools) badges += '<span class="qvc-badge qvc-badge-ok">' + qvcT('badge.tools','工具') + '</span> ';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(m.name || '未命名') + ' ' + badges + '</div>';
            html += '<div class="qvc-list-item-desc">' + qvcEsc(m.model || '') + ' / ' + qvcEsc(m.base_url || '') + '</div>';
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcModelEdit(' + JSON.stringify(m) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            html += '<button class="qvc-btn-sm danger" onclick=\'qvcModelDelete(' + JSON.stringify(qvcEsc(m.id)) + ')\'>__ICON_TRASH__ 删除</button>';
            html += '</div>';
            html += '</div>';
        });
        el.innerHTML = html;
    } catch (e) {
        qvcToast('加载模型失败: ' + e.message, 'error');
    }
}

function qvcModelEdit(model) {
    var m = model || {};
    var caps = m.capabilities || {};
    var fields = [
        { name: 'name', label: '名称', type: 'text', value: m.name || '' },
        { name: 'base_url', label: 'API 地址', type: 'text', value: m.base_url || '' },
        { name: 'api_key', label: 'API 密钥', type: 'text', value: m.api_key || '', placeholder: 'sk-...' },
        { name: 'model', label: '模型标识', type: 'text', value: m.model || '', placeholder: 'gpt-4o' },
        { name: '_cap_chat', label: '文本对话', type: 'checkbox', value: caps.chat !== false },
        { name: '_cap_vision', label: '图片识别', type: 'checkbox', value: !!caps.vision },
        { name: '_cap_tools', label: '工具调用', type: 'checkbox', value: !!caps.tools },
        { name: 'temperature', label: '温度', type: 'number', value: m.temperature != null ? m.temperature : 0.7 },
        { name: 'max_tokens', label: '最大 Tokens', type: 'number', value: m.max_tokens != null ? m.max_tokens : 2000 }
    ];
    qvcShowModal(model ? qvcT('modal.edit_model','编辑模型') : qvcT('modal.add_model','添加模型'), fields, async function(data) {
        var payload = {
            name: data.name,
            base_url: data.base_url,
            api_key: data.api_key,
            model: data.model,
            capabilities: {
                chat: data._cap_chat,
                vision: data._cap_vision,
                tools: data._cap_tools
            },
            temperature: data.temperature,
            max_tokens: data.max_tokens
        };
        if (m.id) payload.id = m.id;
        try {
            await qvcApi('/api/models', 'POST', payload);
            qvcHideModal();
            qvcToast(qvcT('toast.model_saved', '模型已保存'), 'ok');
            qvcLoadModels();
        } catch (e) {
            qvcToast(qvcT('toast.save_failed', '保存失败') + ': ' + e.message, 'error');
        }
    });
}

async function qvcModelDelete(id) {
    qvcConfirm('确定删除此模型？', async function() {
        try {
            await qvcApi('/api/models/delete', 'POST', { id: id });
            qvcToast(qvcT('toast.model_deleted', '模型已删除'), 'ok');
            qvcLoadModels();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

// ==================== 行为管理 ====================
async function qvcLoadBehaviors() {
    try {
        var data = await qvcApi('/api/behaviors', 'GET');
        var behaviors = data.behaviors || data || [];
        var el = document.getElementById('qvc-behaviors-list');
        if (!behaviors.length) {
            el.innerHTML = '<div class="qvc-empty">暂无行为定义</div>';
            return;
        }
        // 获取模型名映射
        var modelData = await qvcApi('/api/models', 'GET');
        var modelList = modelData.models || modelData || [];
        var modelMap = {};
        modelList.forEach(function(m) { modelMap[m.id] = m.name; });

        var html = '';
        behaviors.forEach(function(b) {
            var badges = '';
            badges += '<span class="qvc-badge ' + (b.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (b.enabled ? qvcT('badge.enabled','启用') : qvcT('badge.disabled','禁用')) + '</span> ';
            if (b.is_builtin) badges += '<span class="qvc-badge qvc-badge-off">' + qvcT('badge.builtin','内置') + '</span> ';
            var modelNames = (b.models || []).map(function(mid) {
                return modelMap[mid] || mid;
            });
            var modelStr = modelNames.length ? modelNames.join(', ') : '未分配模型';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(b.name || b.id) + ' ' + badges + '</div>';
            html += '<div class="qvc-list-item-desc">' + qvcEsc(b.description || '') + ' / 模型: ' + qvcEsc(modelStr) + '</div>';
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcBehaviorEdit(' + JSON.stringify(b) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            if (!b.is_builtin) {
                html += '<button class="qvc-btn-sm danger" onclick=\'qvcBehaviorDelete(' + JSON.stringify(qvcEsc(b.id)) + ')\'>__ICON_TRASH__ 删除</button>';
            }
            html += '</div>';
            html += '</div>';
        });
        el.innerHTML = html;
    } catch (e) {
        qvcToast('加载行为失败: ' + e.message, 'error');
    }
}

async function qvcBehaviorEdit(behavior) {
    var b = behavior || {};
    // 先获取可用模型列表
    var modelOptions = [];
    try {
        var modelData = await qvcApi('/api/models', 'GET');
        var modelList = modelData.models || modelData || [];
        modelOptions = modelList.map(function(m) {
            return { label: m.name + ' (' + (m.model || '') + ')', value: m.id };
        });
    } catch (e) { /* 忽略，模型列表为空 */ }

    var triggerWords = b.trigger_words || [];
    var fields = [
        { name: 'name', label: '名称', type: 'text', value: b.name || '' },
        { name: 'description', label: '描述', type: 'text', value: b.description || '' },
        {
            name: 'behavior_type',
            label: '行为类型',
            type: 'select',
            value: b.behavior_type || 'ai',
            options: [
                { label: 'AI 行为（需要模型）', value: 'ai' },
                { label: '场景行为（提示词注入）', value: 'scene' },
                { label: '输出行为（表情包/图片，不消耗 AI）', value: 'output' }
            ]
        },
        {
            name: 'required_capability',
            label: '所需能力',
            type: 'select',
            value: b.required_capability || 'chat',
            options: [
                { label: '文本对话', value: 'chat' },
                { label: '图片识别', value: 'vision' },
                { label: '工具调用', value: 'tools' }
            ]
        },
        { name: 'system_prompt', label: '系统提示词', type: 'textarea', value: b.system_prompt || '' },
        { name: 'temperature', label: '温度', type: 'number', value: b.temperature != null ? b.temperature : null },
        { name: 'max_tokens', label: '最大 Tokens', type: 'number', value: b.max_tokens != null ? b.max_tokens : null },
        {
            name: 'trigger_mode',
            label: '触发模式',
            type: 'select',
            value: b.trigger_mode || 'always',
            options: [
                { label: '始终触发', value: 'always' },
                { label: '预测模式', value: 'prediction' }
            ]
        },
        { name: 'prediction_interval', label: '预测间隔（消息数）', type: 'number', value: b.prediction_interval != null ? b.prediction_interval : 5 },
        { name: '_trigger_words', label: '触发词（逗号分隔）', type: 'text', value: triggerWords.join(', ') },
        { name: 'enabled', label: '启用此行为', type: 'checkbox', value: b.enabled !== false },
        { name: 'response_template', label: '输出模板（支持 {ai_response}/{at_user}/[img]url[/img]/[sticker]url[/sticker]）', type: 'textarea', value: b.response_template || '', placeholder: '例: [sticker]https://x.com/cat.png[/sticker]\n或: {ai_response}\n[img]https://x.com/meme.jpg[/img]' },
        { name: 'trigger_probability', label: '触发概率 (0=从不, 1=总是)', type: 'number', value: b.trigger_probability != null ? b.trigger_probability : 0 }
    ];

    // 添加模型选择（checkbox-group）
    if (modelOptions.length > 0) {
        fields.push({
            name: 'models',
            label: '分配模型',
            type: 'checkbox-group',
            value: b.models || [],
            options: modelOptions
        });
    }

    qvcShowModal(behavior ? '编辑行为' : '添加行为', fields, async function(data) {
        var payload = {
            name: data.name,
            description: data.description,
            behavior_type: data.behavior_type || 'ai',
            required_capability: data.required_capability,
            system_prompt: data.system_prompt,
            temperature: data.temperature,
            max_tokens: data.max_tokens,
            trigger_mode: data.trigger_mode,
            prediction_interval: data.prediction_interval,
            trigger_words: (data._trigger_words || '').split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s.length > 0; }),
            enabled: data.enabled,
            models: data.models || [],
            response_template: data.response_template || '',
            trigger_probability: data.trigger_probability || 0,
        };
        if (b.id) payload.id = b.id;
        try {
            await qvcApi('/api/behaviors', 'POST', payload);
            qvcHideModal();
            qvcToast(qvcT('toast.behavior_saved', '行为已保存'), 'ok');
            qvcLoadBehaviors();
        } catch (e) {
            qvcToast(qvcT('toast.save_failed', '保存失败') + ': ' + e.message, 'error');
        }
    });
}

async function qvcBehaviorDelete(id) {
    qvcConfirm('确定删除此行为？', async function() {
        try {
            await qvcApi('/api/behaviors/delete', 'POST', { id: id });
            qvcToast(qvcT('toast.behavior_deleted', '行为已删除'), 'ok');
            qvcLoadBehaviors();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

// ==================== 注入管线 ====================
async function qvcLoadPipeline() {
    try {
        // 应用 i18n 标签
        var i18nEls = {
            'qvc-pipeline-title': 'pipeline.title',
            'qvc-pipeline-desc': 'pipeline.desc',
            'qvc-pipeline-time-title': 'pipeline.time_settings',
            'qvc-pipeline-time-prob-label': 'pipeline.time_prob',
            'qvc-pipeline-time-ttl-label': 'pipeline.time_ttl',
            'qvc-pipeline-save-label': 'pipeline.save'
        };
        for (var eid in i18nEls) {
            var el = document.getElementById(eid);
            if (el) el.textContent = qvcT(i18nEls[eid], el.textContent);
        }

        var data = await qvcApi('/api/pipeline', 'GET');
        var injectors = data.injectors || [];
        var cfg = data.config || {};
        _qvcPipelineList = injectors.map(function(i) { return { id: i.id, priority: i.priority, enabled: !!i.enabled }; });
        var el = document.getElementById('qvc-pipeline-list');
        if (!injectors.length) {
            el.innerHTML = '<div class="qvc-empty">' + qvcT('pipeline.empty', '无注入器') + '</div>';
        } else {
            qvcRenderPipelineList();
        }
        var prob = document.getElementById('qvc-pipeline-time-prob');
        var ttl = document.getElementById('qvc-pipeline-time-ttl');
        if (prob) { prob.value = cfg.time_inject_probability != null ? cfg.time_inject_probability : 0.7; prob.oninput(); }
        if (ttl) { ttl.value = cfg.time_cache_ttl != null ? cfg.time_cache_ttl : 3600; }
    } catch (e) {
        qvcToast(qvcT('pipeline.load_failed', '加载注入管线失败') + ': ' + e.message, 'error');
    }
}

function qvcPipelineToggle(cb) {
    var id = cb.getAttribute('data-id');
    var inj = _qvcPipelineList.filter(function(i) { return i.id === id; })[0];
    if (inj) inj.enabled = cb.checked;
}

function qvcPipelineMove(id, dir) {
    var idx = _qvcPipelineList.findIndex(function(i) { return i.id === id; });
    if (idx < 0) return;
    var target = idx + dir;
    if (target < 0 || target >= _qvcPipelineList.length) return;
    var tmp = _qvcPipelineList[idx];
    _qvcPipelineList[idx] = _qvcPipelineList[target];
    _qvcPipelineList[target] = tmp;
    _qvcPipelineList.forEach(function(i, n) { i.priority = (n + 1) * 10; });
    qvcRenderPipelineList();
}

function qvcRenderPipelineList() {
    var el = document.getElementById('qvc-pipeline-list');
    if (!el) return;
    var html = '';
    _qvcPipelineList.forEach(function(inj) {
        html += '<div class="qvc-pipeline-item" data-id="' + qvcEsc(inj.id) + '">' +
            '<div class="qvc-pipeline-order">' +
                '<button class="qvc-btn-icon" onclick="qvcPipelineMove(\'' + inj.id + '\', -1)" title="' + qvcT('pipeline.move_up', '上移') + '">↑</button>' +
                '<button class="qvc-btn-icon" onclick="qvcPipelineMove(\'' + inj.id + '\', 1)" title="' + qvcT('pipeline.move_down', '下移') + '">↓</button>' +
            '</div>' +
            '<div class="qvc-pipeline-info">' +
                '<div class="qvc-pipeline-name">' + qvcEsc(inj.id) +
                    ' <span class="qvc-pipeline-priority">priority=' + inj.priority + '</span></div>' +
            '</div>' +
            '<label class="qvc-switch">' +
                '<input type="checkbox" data-id="' + qvcEsc(inj.id) + '"' + (inj.enabled ? ' checked' : '') + ' onchange="qvcPipelineToggle(this)">' +
                '<span class="qvc-switch-slider"></span>' +
            '</label>' +
        '</div>';
    });
    el.innerHTML = html;
}

async function qvcSavePipeline() {
    try {
        var list = [];
        document.querySelectorAll('#qvc-pipeline-list .qvc-pipeline-item').forEach(function(item) {
            var id = item.getAttribute('data-id');
            var cb = item.querySelector('input[type="checkbox"]');
            var inj = _qvcPipelineList.filter(function(i) { return i.id === id; })[0];
            list.push({
                id: id,
                enabled: cb ? cb.checked : true,
                priority: inj ? inj.priority : 50
            });
        });
        var config = {
            time_inject_probability: parseFloat(document.getElementById('qvc-pipeline-time-prob').value),
            time_cache_ttl: parseInt(document.getElementById('qvc-pipeline-time-ttl').value) || 3600
        };
        var resp = await qvcApi('/api/pipeline', 'POST', { injectors: list, config: config });
        if (resp.ok) {
            qvcToast(qvcT('pipeline.saved', '注入管线已保存'), 'ok');
            qvcLoadPipeline();
        } else {
            qvcToast(qvcT('pipeline.save_failed', '保存失败') + ': ' + (resp.error || '未知错误'), 'error');
        }
    } catch (e) {
        qvcToast(qvcT('pipeline.save_failed', '保存失败') + ': ' + e.message, 'error');
    }
}

// ==================== 多智能体 ====================
async function qvcLoadAgents() {
    try {
        var data = await qvcApi('/api/agents', 'GET');
        var agents = data.agents || data || [];
        var bindings = {};
        // 获取绑定信息
        try {
            var groupsData = await qvcApi('/api/groups', 'GET');
            (groupsData.groups || []).forEach(function(g) {
                var sk = 'group:' + g.id;
                if (g.config && g.config._agent_id) bindings[sk] = g.config._agent_id;
            });
        } catch (e) {}

        var el = document.getElementById('qvc-agents-list');
        if (!agents.length) {
            el.innerHTML = '<div class="qvc-empty">暂无智能体，点击右上角创建</div>';
            return;
        }
        var html = '';
        agents.forEach(function(a) {
            var traits = a.traits || {};
            var catchphrases = a.catchphrases || [];
            var traitTags = '';
            var traitMap = {
                friendliness: ['冷淡', '友善'],
                activity: ['安静', '活跃'],
                formality: ['随意', '正式'],
                humor: ['严肃', '幽默'],
                curiosity: ['漠然', '好奇']
            };
            Object.keys(traitMap).forEach(function(key) {
                var val = traits[key];
                if (val != null) {
                    var label = val >= 0.6 ? traitMap[key][1] : (val <= 0.4 ? traitMap[key][0] : null);
                    if (label) traitTags += '<span class="qvc-trait-tag">' + qvcEsc(label) + '</span>';
                }
            });

            html += '<div class="qvc-agent-card">';
            html += '<div class="qvc-agent-card-header">';
            html += '<div>';
            html += '<span class="qvc-agent-card-title">' + qvcEsc(a.name || a.id) + '</span> ';
            var badges = '';
            badges += '<span class="qvc-badge ' + (a.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (a.enabled ? qvcT('badge.enabled','启用') : qvcT('badge.disabled','禁用')) + '</span> ';
            if (a.is_default) badges += '<span class="qvc-badge qvc-badge-off">' + qvcT('badge.default','默认') + '</span> ';
            html += badges;
            html += '</div>';
            html += '<div style="display:flex;gap:4px;flex-wrap:wrap">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcAgentEdit(' + JSON.stringify(a) + ')\'>__ICON_EDIT__ 编辑</button>';
            html += '<button class="qvc-btn-sm" onclick=\'qvcAgentTest(' + JSON.stringify(qvcEsc(a.id)) + ')\'>测试</button>';
            if (!a.is_default) {
                html += '<button class="qvc-btn-sm" onclick=\'qvcAgentClone(' + JSON.stringify(qvcEsc(a.id)) + ')\'>克隆</button>';
                html += '<button class="qvc-btn-sm danger" onclick=\'qvcAgentDelete(' + JSON.stringify(qvcEsc(a.id)) + ')\'>__ICON_TRASH__</button>';
            }
            html += '</div>';
            html += '</div>';
            if (a.description) {
                html += '<div class="qvc-list-item-desc">' + qvcEsc(a.description) + '</div>';
            }
            if (a.speaking_style) {
                html += '<div style="font-size:12px;color:var(--tx-s);margin-top:4px">说话风格: ' + qvcEsc(a.speaking_style) + '</div>';
            }
            if (catchphrases.length) {
                html += '<div style="font-size:12px;color:var(--tx-s);margin-top:2px">口头禅: ' + catchphrases.map(function(c) { return qvcEsc(c); }).join('、') + '</div>';
            }
            if (traitTags) {
                html += '<div class="qvc-agent-traits">' + traitTags + '</div>';
            }
            html += '</div>';
        });
        el.innerHTML = html;
    } catch (e) {
        qvcToast('加载智能体失败: ' + e.message, 'error');
    }
}

async function qvcAgentEdit(agent) {
    var a = agent || {};
    var traits = a.traits || {};

    // 加载人格模板
    var templateOptions = [];
    try {
        var resp = await qvcApi('/api/templates', 'GET');
        var templates = resp.templates || {};
        templateOptions = Object.keys(templates).map(function(name) {
            return { value: name, label: name };
        });
    } catch (e) {}

    var fields = [
        { name: '_template', label: '从模板快速创建（选择后自动填充提示词）', type: 'select', value: '', options: templateOptions },
        { name: 'name', label: '名称', type: 'text', value: a.name || '' },
        { name: 'description', label: '描述', type: 'text', value: a.description || '' },
        { name: 'system_prompt', label: '系统提示词（核心人格设定）', type: 'textarea', value: a.system_prompt || '' },
        { name: '_html_traits', label: '── 人格特质滑块（拖动调整，影响 AI 的性格倾向）──', type: 'html', value: '' },
        { name: '_t_friendliness', label: '友善度', type: 'range', value: traits.friendliness != null ? traits.friendliness : 0.5, min: 0, max: 1, step: 0.05 },
        { name: '_t_activity', label: '活跃度', type: 'range', value: traits.activity != null ? traits.activity : 0.5, min: 0, max: 1, step: 0.05 },
        { name: '_t_formality', label: '正式度', type: 'range', value: traits.formality != null ? traits.formality : 0.3, min: 0, max: 1, step: 0.05 },
        { name: '_t_humor', label: '幽默感', type: 'range', value: traits.humor != null ? traits.humor : 0.5, min: 0, max: 1, step: 0.05 },
        { name: '_t_curiosity', label: '好奇心', type: 'range', value: traits.curiosity != null ? traits.curiosity : 0.5, min: 0, max: 1, step: 0.05 },
        { name: '_html_extra', label: '── 个性化设定 ──', type: 'html', value: '' },
        { name: 'speaking_style', label: '说话风格（如：活泼可爱、冷静理性）', type: 'text', value: a.speaking_style || '' },
        { name: '_catchphrases', label: '口头禅（逗号分隔，如：嘿嘿,哎呀）', type: 'text', value: (a.catchphrases || []).join(', ') },
        { name: 'greeting', label: '开场白（参考，AI 不一定每次使用）', type: 'text', value: a.greeting || '' },
        { name: '_knowledge_tags', label: '知识库标签绑定（逗号分隔，仅注入匹配的知识）', type: 'text', value: (a.knowledge_tags || []).join(', ') },
        { name: '_html_model', label: '── 模型覆盖（留空使用默认）──', type: 'html', value: '' },
        { name: 'model', label: '指定模型 ID', type: 'text', value: a.model || '' },
        { name: 'temperature', label: '温度', type: 'number', value: a.temperature },
        { name: 'max_tokens', label: '最大 Tokens', type: 'number', value: a.max_tokens },
        { name: 'enabled', label: '启用', type: 'checkbox', value: a.enabled !== false }
    ];
    qvcShowModal(agent ? qvcT('modal.edit_agent','编辑智能体') : qvcT('modal.create_agent','创建智能体'), fields, async function(data) {
        var payload = {
            name: data.name,
            description: data.description,
            system_prompt: data.system_prompt,
            speaking_style: data.speaking_style,
            greeting: data.greeting,
            model: data.model,
            temperature: data.temperature,
            max_tokens: data.max_tokens,
            enabled: data.enabled,
            traits: {
                friendliness: data._t_friendliness,
                activity: data._t_activity,
                formality: data._t_formality,
                humor: data._t_humor,
                curiosity: data._t_curiosity
            },
            catchphrases: (data._catchphrases || '').split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s.length > 0; }),
            knowledge_tags: (data._knowledge_tags || '').split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s.length > 0; })
        };
        if (a.id) payload.id = a.id;
        try {
            await qvcApi('/api/agents', 'POST', payload);
            qvcHideModal();
            qvcToast(qvcT('toast.agent_saved', '智能体已保存'), 'ok');
            qvcLoadAgents();
        } catch (e) {
            qvcToast(qvcT('toast.save_failed', '保存失败') + ': ' + e.message, 'error');
        }
    });

    // 模板选择后自动填充提示词
    var templateSelect = document.querySelector('[data-field="_template"]');
    if (templateSelect) {
        templateSelect.addEventListener('change', async function() {
            var name = this.value;
            if (!name) return;
            try {
                var resp = await qvcApi('/api/templates', 'GET');
                var templates = resp.templates || {};
                if (templates[name]) {
                    var promptEl = document.querySelector('[data-field="system_prompt"]');
                    if (promptEl) promptEl.value = templates[name];
                    var nameEl = document.querySelector('[data-field="name"]');
                    if (nameEl && !nameEl.value) nameEl.value = name;
                }
            } catch (e) {}
        });
    }
}

async function qvcAgentQuickCreate() {
    try {
        var resp = await qvcApi('/api/templates', 'GET');
        var templates = resp.templates || {};
        var templateNames = Object.keys(templates);
        if (!templateNames.length) {
            qvcToast('暂无模板', 'error');
            return;
        }

        var html = '<p style="font-size:13px;color:var(--tx-s);margin-bottom:12px">选择一个人格模板快速创建智能体，创建后可自由编辑：</p>';
        html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px">';
        templateNames.forEach(function(name) {
            var preview = templates[name].substring(0, 80).replace(/\n/g, ' ');
            html += '<div class="qvc-agent-card" style="cursor:pointer;padding:12px" onclick=\'qvcAgentCreateFromTemplate(' + JSON.stringify(name) + ')\'>';
            html += '<div style="font-weight:600;font-size:14px;color:var(--accent);margin-bottom:4px">' + qvcEsc(name) + '</div>';
            html += '<div style="font-size:11px;color:var(--tx-s);line-height:1.4">' + qvcEsc(preview) + '...</div>';
            html += '</div>';
        });
        html += '</div>';

        document.getElementById('qvc-modal-title').textContent = '从模板创建智能体';
        document.getElementById('qvc-modal-body').innerHTML = html;
        var footer = document.querySelector('.qvc-modal-footer');
        if (footer) footer.style.display = 'none';
        document.getElementById('qvc-modal-bg').classList.add('show');
        _qvcModalCallback = null;
    } catch (e) {
        qvcToast('加载模板失败: ' + e.message, 'error');
    }
}

async function qvcAgentCreateFromTemplate(templateName) {
    qvcHideModal();
    try {
        var resp = await qvcApi('/api/templates', 'GET');
        var templates = resp.templates || {};
        var prompt = templates[templateName] || '';
        // 直接创建智能体
        var createResp = await qvcApi('/api/agents', 'POST', {
            name: templateName,
            description: templateName + '人格模板',
            system_prompt: prompt,
            enabled: true
        });
        if (createResp.ok) {
            qvcToast('已从模板创建: ' + templateName, 'ok');
            qvcLoadAgents();
            // 打开编辑器让用户进一步自定义
            if (createResp.agent) {
                qvcAgentEdit(createResp.agent);
            }
        }
    } catch (e) {
        qvcToast('创建失败: ' + e.message, 'error');
    }
}

async function qvcAgentDelete(id) {
    qvcConfirm('确定删除此智能体？', async function() {
        try {
            await qvcApi('/api/agents/delete', 'POST', { id: id });
            qvcToast(qvcT('toast.agent_deleted', '智能体已删除'), 'ok');
            qvcLoadAgents();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

async function qvcAgentClone(id) {
    qvcConfirm('确定克隆此智能体？', async function() {
        try {
            var resp = await qvcApi('/api/agents/clone', 'POST', { id: id });
            if (resp.ok) {
                qvcToast('智能体已克隆: ' + (resp.agent ? resp.agent.name : ''), 'ok');
                qvcLoadAgents();
            } else {
                qvcToast(resp.error || '克隆失败', 'error');
            }
        } catch (e) {
            qvcToast('克隆失败: ' + e.message, 'error');
        }
    });
}

var _qvcTestHistory = [];

async function qvcAgentTest(agentId) {
    _qvcTestHistory = [];
    var agents = [];
    try {
        var data = await qvcApi('/api/agents', 'GET');
        agents = data.agents || data || [];
    } catch (e) {}

    var agent = agents.find(function(a) { return a.id === agentId; });
    var agentName = agent ? agent.name : agentId;

    var html = '<div class="qvc-playground">';
    html += '<div style="padding:8px 12px;font-size:12px;color:var(--tx-s);border-bottom:1px solid var(--bd)">';
    html += '正在测试: <strong>' + qvcEsc(agentName) + '</strong> — 发送消息查看 AI 回复';
    html += '</div>';
    html += '<div class="qvc-playground-log" id="qvc-playground-log"></div>';
    html += '<div class="qvc-playground-input">';
    html += '<input type="text" class="qvc-input" id="qvc-playground-input" placeholder="输入测试消息..." onkeydown="if(event.key===\'Enter\')qvcAgentTestSend(\'' + agentId + '\')">';
    html += '<button class="qvc-btn-sm primary" onclick="qvcAgentTestSend(\'' + agentId + '\')">发送</button>';
    html += '<button class="qvc-btn-sm" onclick="_qvcTestHistory=[];document.getElementById(\'qvc-playground-log\').innerHTML=\'\'">清空</button>';
    html += '</div>';
    html += '</div>';

    document.getElementById('qvc-modal-title').textContent = '智能体测试 - ' + agentName;
    document.getElementById('qvc-modal-body').innerHTML = html;
    document.getElementById('qvc-modal-bg').classList.add('show');
    _qvcModalCallback = null;
    // 隐藏底部确定按钮
    var footer = document.querySelector('.qvc-modal-footer');
    if (footer) footer.style.display = 'none';
    
    setTimeout(function() {
        var input = document.getElementById('qvc-playground-input');
        if (input) input.focus();
    }, 100);
}

async function qvcAgentTestSend(agentId) {
    var input = document.getElementById('qvc-playground-input');
    if (!input || !input.value.trim()) return;
    var msg = input.value.trim();
    input.value = '';
    var logEl = document.getElementById('qvc-playground-log');

    // 显示用户消息
    var userHtml = '<div class="qvc-playground-msg user">' + qvcEsc(msg) + '</div>';
    logEl.innerHTML += userHtml;
    logEl.scrollTop = logEl.scrollHeight;

    // 显示加载中
    var loadingId = '_loading_' + Date.now();
    logEl.innerHTML += '<div class="qvc-playground-msg assistant" id="' + loadingId + '">思考中...</div>';
    logEl.scrollTop = logEl.scrollHeight;

    _qvcTestHistory.push({ role: 'user', content: msg });

    try {
        var resp = await qvcApi('/api/agents/test', 'POST', {
            id: agentId,
            message: msg,
            history: _qvcTestHistory
        });
        var loadingEl = document.getElementById(loadingId);
        if (resp.ok && resp.reply) {
            if (loadingEl) loadingEl.textContent = resp.reply;
            _qvcTestHistory.push({ role: 'assistant', content: resp.reply });
        } else {
            if (loadingEl) loadingEl.textContent = '错误: ' + (resp.error || '未知错误');
        }
    } catch (e) {
        var el2 = document.getElementById(loadingId);
        if (el2) el2.textContent = '请求失败: ' + e.message;
    }
    logEl.scrollTop = logEl.scrollHeight;
}

// ==================== 知识库 ====================
async function qvcLoadKnowledge() {
    try {
        var data = await qvcApi('/api/knowledge', 'GET');
        var entries = data.entries || data || [];
        var el = document.getElementById('qvc-knowledge-list');
        if (!entries.length) {
            el.innerHTML = '<div class="qvc-empty">暂无知识条目</div>';
            return;
        }
        var html = '';
        entries.forEach(function(e) {
            var badges = '';
            badges += '<span class="qvc-badge ' + (e.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (e.enabled ? qvcT('badge.enabled','启用') : qvcT('badge.disabled','禁用')) + '</span> ';
            if (e.category) badges += '<span class="qvc-badge qvc-badge-off">' + qvcEsc(e.category) + '</span> ';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(e.title || e.id) + ' ' + badges + '</div>';
            var preview = (e.content || '').substring(0, 80);
            html += '<div class="qvc-list-item-desc">' + qvcEsc(preview) + (e.content && e.content.length > 80 ? '...' : '') + '</div>';
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcKbEdit(' + JSON.stringify(e) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            html += '<button class="qvc-btn-sm danger" onclick=\'qvcKbDelete(' + JSON.stringify(qvcEsc(e.id)) + ')\'>__ICON_TRASH__ 删除</button>';
            html += '</div>';
            html += '</div>';
        });
        el.innerHTML = html;
    } catch (e) {
        qvcToast('加载知识库失败: ' + e.message, 'error');
    }
}

function qvcKbEdit(entry) {
    var e = entry || {};
    var tags = e.tags || [];
    var fields = [
        { name: 'title', label: '标题', type: 'text', value: e.title || '' },
        { name: 'category', label: '分类', type: 'text', value: e.category || '通用' },
        { name: 'content', label: '内容', type: 'textarea', value: e.content || '' },
        { name: '_tags', label: '标签（逗号分隔）', type: 'text', value: tags.join(', ') },
        { name: 'priority', label: '优先级', type: 'number', value: e.priority != null ? e.priority : 0 },
        { name: 'enabled', label: '启用', type: 'checkbox', value: e.enabled !== false }
    ];
    qvcShowModal(entry ? '编辑知识条目' : '添加知识条目', fields, async function(data) {
        var payload = {
            title: data.title,
            category: data.category,
            content: data.content,
            tags: (data._tags || '').split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s.length > 0; }),
            priority: data.priority,
            enabled: data.enabled
        };
        if (e.id) payload.id = e.id;
        try {
            await qvcApi('/api/knowledge', 'POST', payload);
            qvcHideModal();
            qvcToast('知识条目已保存', 'ok');
            qvcLoadKnowledge();
        } catch (err) {
            qvcToast('保存失败: ' + err.message, 'error');
        }
    });
}

async function qvcKbDelete(id) {
    qvcConfirm('确定删除此知识条目？', async function() {
        try {
            await qvcApi('/api/knowledge/delete', 'POST', { id: id });
            qvcToast('知识条目已删除', 'ok');
            qvcLoadKnowledge();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

// ==================== MCP 工具 ====================
async function qvcLoadTools() {
    try {
        // 同时加载 MCP 服务器和手动工具
        var serversPromise = qvcApi('/api/mcp-servers', 'GET').catch(function() { return { servers: [] }; });
        var toolsPromise = qvcApi('/api/tools', 'GET').catch(function() { return { tools: [] }; });
        var results = await Promise.all([serversPromise, toolsPromise]);

        // 渲染 MCP 服务器
        var servers = (results[0].servers || []);
        var serversEl = document.getElementById('qvc-mcp-servers-list');
        if (!servers.length) {
            serversEl.innerHTML = '<div class="qvc-empty">暂无 MCP 服务器配置</div>';
        } else {
            var serversHtml = '';
            servers.forEach(function(s) {
                var badges = '';
                badges += '<span class="qvc-badge ' + (s.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (s.enabled ? qvcT('badge.enabled','启用') : qvcT('badge.disabled','禁用')) + '</span> ';
                badges += '<span class="qvc-badge ' + (s.connected ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (s.connected ? qvcT('badge.connected','已连接') : qvcT('badge.disconnected','未连接')) + '</span> ';
                if (s.connected) badges += '<span class="qvc-badge qvc-badge-off">' + (s.tool_count || 0) + ' 工具</span> ';
                serversHtml += '<div class="qvc-list-item">';
                serversHtml += '<div class="qvc-list-item-info">';
                serversHtml += '<div class="qvc-list-item-title">' + qvcEsc(s.name) + ' ' + badges + '</div>';
                serversHtml += '<div class="qvc-list-item-desc">' + qvcEsc(s.url || '') + '</div>';
                serversHtml += '</div>';
                serversHtml += '<div class="qvc-list-item-actions">';
                if (!s.connected) serversHtml += '<button class="qvc-btn-sm" onclick=\'qvcMcpConnect("' + qvcEsc(s.name) + '")\'>连接</button> ';
                serversHtml += '<button class="qvc-btn-sm" onclick=\'qvcMcpServerEdit(' + JSON.stringify(s) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
                serversHtml += '<button class="qvc-btn-sm danger" onclick=\'qvcMcpServerDelete("' + qvcEsc(s.name) + '")\'>' + '__ICON_TRASH__' + ' 删除</button>';
                serversHtml += '</div>';
                serversHtml += '</div>';
            });
            serversEl.innerHTML = serversHtml;
        }

        // 渲染手动工具
        var tools = results[1].tools || results[1] || [];
        var el = document.getElementById('qvc-tools-list');
        if (!tools.length) {
            el.innerHTML = '<div class="qvc-empty">暂无工具定义</div>';
            return;
        }
        var html = '';
        tools.forEach(function(t) {
            var badges = '';
            badges += '<span class="qvc-badge ' + (t.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (t.enabled ? qvcT('badge.enabled','启用') : qvcT('badge.disabled','禁用')) + '</span> ';
            if (t.endpoint) badges += '<span class="qvc-badge qvc-badge-off">HTTP</span> ';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(t.name || t.id) + ' ' + badges + '</div>';
            html += '<div class="qvc-list-item-desc">' + qvcEsc(t.description || '') + '</div>';
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcToolEdit(' + JSON.stringify(t) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            html += '<button class="qvc-btn-sm danger" onclick=\'qvcToolDelete(' + JSON.stringify(qvcEsc(t.id)) + ')\'>__ICON_TRASH__ 删除</button>';
            html += '</div>';
            html += '</div>';
        });
        el.innerHTML = html;
    } catch (e) {
        qvcToast('加载工具失败: ' + e.message, 'error');
    }
}

function qvcToolEdit(tool) {
    var t = tool || {};
    var paramStr = '';
    if (t.parameters && typeof t.parameters === 'object') {
        try { paramStr = JSON.stringify(t.parameters, null, 2); } catch (_) {}
    }
    var fields = [
        { name: 'name', label: '工具名称', type: 'text', value: t.name || '', placeholder: 'get_weather' },
        { name: 'description', label: '描述', type: 'text', value: t.description || '' },
        { name: '_parameters', label: '参数 JSON Schema', type: 'textarea', value: paramStr, placeholder: '{"type":"object","properties":{},"required":[]}' },
        { name: 'endpoint', label: 'HTTP 端点（可选）', type: 'text', value: t.endpoint || '' },
        {
            name: 'method',
            label: '请求方法',
            type: 'select',
            value: t.method || 'POST',
            options: [
                { label: 'POST', value: 'POST' },
                { label: 'GET', value: 'GET' }
            ]
        },
        { name: 'enabled', label: '启用', type: 'checkbox', value: t.enabled !== false }
    ];
    qvcShowModal(tool ? qvcT('modal.edit_tool','编辑工具') : qvcT('modal.add_tool','添加工具'), fields, async function(data) {
        var params = {};
        try {
            params = data._parameters ? JSON.parse(data._parameters) : {};
        } catch (_) {
            qvcToast('参数 JSON 格式错误', 'error');
            return;
        }
        var payload = {
            name: data.name,
            description: data.description,
            parameters: params,
            endpoint: data.endpoint,
            method: data.method,
            enabled: data.enabled
        };
        if (t.id) payload.id = t.id;
        try {
            await qvcApi('/api/tools', 'POST', payload);
            qvcHideModal();
            qvcToast(qvcT('toast.tool_saved', '工具已保存'), 'ok');
            qvcLoadTools();
        } catch (err) {
            qvcToast('保存失败: ' + err.message, 'error');
        }
    });
}

async function qvcToolDelete(id) {
    qvcConfirm('确定删除此工具？', async function() {
        try {
            await qvcApi('/api/tools/delete', 'POST', { id: id });
            qvcToast(qvcT('toast.tool_deleted', '工具已删除'), 'ok');
            qvcLoadTools();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

// ----- MCP 服务器管理 -----
function qvcMcpServerEdit(server) {
    var s = server || {};
    var headersStr = '';
    if (s.headers && typeof s.headers === 'object') {
        try { headersStr = JSON.stringify(s.headers, null, 2); } catch (_) {}
    }
    var fields = [
        { name: 'name', label: '服务器名称', type: 'text', value: s.name || '', placeholder: 'erispulse' },
        { name: 'url', label: '服务器 URL', type: 'text', value: s.url || '', placeholder: 'https://mcp.erisdev.com/' },
        { name: '_headers', label: '请求头 (JSON，可选)', type: 'textarea', value: headersStr, placeholder: '{"Authorization": "Bearer xxx"}' },
        { name: 'enabled', label: '启用', type: 'checkbox', value: s.enabled !== false }
    ];
    qvcShowModal(server ? qvcT('modal.edit_mcp_server','编辑 MCP 服务器') : qvcT('modal.add_mcp_server','添加 MCP 服务器'), fields, async function(data) {
        var headers = {};
        try {
            headers = data._headers ? JSON.parse(data._headers) : {};
        } catch (_) {
            qvcToast('请求头 JSON 格式错误', 'error');
            return;
        }
        var payload = {
            name: data.name,
            url: data.url,
            headers: headers,
            enabled: data.enabled
        };
        try {
            await qvcApi('/api/mcp-servers', 'POST', payload);
            qvcHideModal();
            qvcToast(qvcT('toast.mcp_server_saved', 'MCP 服务器已保存'), 'ok');
            qvcLoadTools();
        } catch (err) {
            qvcToast('保存失败: ' + err.message, 'error');
        }
    });
}

async function qvcMcpServerDelete(name) {
    qvcConfirm('确定删除 MCP 服务器「' + name + '」？', async function() {
        try {
            await qvcApi('/api/mcp-servers/delete', 'POST', { name: name });
            qvcToast(qvcT('toast.mcp_server_deleted', 'MCP 服务器已删除'), 'ok');
            qvcLoadTools();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

async function qvcMcpConnect(name) {
    try {
        qvcToast('正在连接...', 'info');
        var resp = await qvcApi('/api/mcp-servers/connect', 'POST', { name: name });
        if (resp.ok) {
            qvcToast('MCP 服务器已连接', 'ok');
        } else {
            qvcToast('连接失败', 'error');
        }
        qvcLoadTools();
    } catch (e) {
        qvcToast(qvcT('toast.conn_failed', '连接失败') + ': ' + e.message, 'error');
    }
}

async function qvcMcpConnectAll() {
    try {
        qvcToast('正在连接所有服务器...', 'info');
        await qvcApi('/api/mcp-servers/connect', 'POST', { connect_all: true });
        qvcToast('连接完成', 'ok');
        qvcLoadTools();
    } catch (e) {
        qvcToast(qvcT('toast.conn_failed', '连接失败') + ': ' + e.message, 'error');
    }
}

// ==================== 表情包 ====================
async function qvcLoadStickers() {
    try {
        var data = await qvcApi('/api/stickers', 'GET');
        var stickers = data.stickers || [];
        var el = document.getElementById('qvc-stickers-list');
        if (!stickers.length) {
            el.innerHTML = '<div class="qvc-empty">暂无表情包。点击「上传表情包」添加。</div>';
            return;
        }
        var html = '';
        stickers.forEach(function(s) {
            var imgSrc = s.is_url ? s.file : ('/QvQChat/stickers/img/' + s.id);
            if (!s.is_url && !s.file) imgSrc = '';
            html += '<div class="qvc-sticker-card">';
            html += '<label class="qvc-sticker-check"><input type="checkbox" class="qvc-sticker-cb" value="' + qvcEsc(s.id) + '"></label>';
            html += '<div class="qvc-sticker-actions-hover">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcStickerEdit(' + JSON.stringify(s) + ')\'>' + '__ICON_EDIT__' + '</button>';
            html += '<button class="qvc-btn-sm danger" onclick=\'qvcStickerDelete("' + qvcEsc(s.id) + '")\'>' + '__ICON_TRASH__' + '</button>';
            html += '</div>';
            if (imgSrc) {
                html += '<div class="qvc-sticker-thumb"><img src="' + qvcEsc(imgSrc) + '"></div>';
            } else {
                html += '<div class="qvc-sticker-thumb qvc-sticker-noimg">无预览</div>';
            }
            html += '<div class="qvc-sticker-name">' + qvcEsc(s.name) + '</div>';
            if (s.description) {
                html += '<div class="qvc-sticker-desc">' + qvcEsc(s.description) + '</div>';
            }
            html += '</div>';
        });
        el.innerHTML = html;
        // 如果当前在选择模式，恢复事件绑定
        if (_qvcSelectMode) {
            var grid = document.getElementById('qvc-stickers-list');
            if (grid) {
                grid.classList.add('qvc-select-mode');
                grid.onclick = function(e) {
                    var card = e.target.closest('.qvc-sticker-card');
                    if (!card) return;
                    if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') return;
                    var cb = card.querySelector('.qvc-sticker-cb');
                    if (cb) cb.checked = !cb.checked;
                    qvcStickerUpdateToolbar();
                };
            }
        }
    } catch (e) {
        qvcToast('加载表情包失败: ' + e.message, 'error');
    }
}

function qvcStickerUpload() {
    var fields = [
        { name: 'name', label: '表情包名称', type: 'text', value: '', placeholder: '开心猫猫' },
        { name: 'description', label: '描述/用途（供 AI 参考）', type: 'text', value: '', placeholder: '表达开心、得意的场景' },
        { name: 'file', label: '选择图片', type: 'file', value: '' }
    ];
    qvcShowModal('上传表情包', fields, async function(data) {
        if (!data.name || !data.name.trim()) {
            qvcToast('请填写名称', 'error');
            return;
        }
        var fileInput = document.querySelector('[data-field="file"]');
        if (!fileInput || !fileInput.files || !fileInput.files[0]) {
            qvcToast('请选择图片文件', 'error');
            return;
        }
        var formData = new FormData();
        formData.append('name', data.name);
        formData.append('description', data.description || '');
        formData.append('file', fileInput.files[0]);
        try {
            var token = localStorage.getItem('__ep_tk__');
            var resp = await fetch('/QvQChat/api/stickers/upload', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + (token || '') },
                body: formData
            });
            var result = await resp.json();
            if (!resp.ok || result.error) throw new Error(result.error || '上传失败');
            qvcHideModal();
            qvcToast('表情包已上传', 'ok');
            qvcLoadStickers();
        } catch (err) {
            qvcToast('上传失败: ' + err.message, 'error');
        }
    });
}

function qvcStickerAddUrl() {
    var fields = [
        { name: 'name', label: '表情包名称', type: 'text', value: '', placeholder: '狗狗头' },
        { name: 'description', label: '描述/用途（供 AI 参考）', type: 'text', value: '', placeholder: '表达疑惑、无奈' },
        { name: 'url', label: '图片 URL', type: 'text', value: '', placeholder: 'https://example.com/doge.png' }
    ];
    qvcShowModal('通过 URL 添加表情包', fields, async function(data) {
        if (!data.name || !data.name.trim()) {
            qvcToast('请填写名称', 'error');
            return;
        }
        if (!data.url) {
            qvcToast('请填写 URL', 'error');
            return;
        }
        try {
            await qvcApi('/api/stickers', 'POST', data);
            qvcHideModal();
            qvcToast('表情包已添加', 'ok');
            qvcLoadStickers();
        } catch (err) {
            qvcToast('添加失败: ' + err.message, 'error');
        }
    });
}

function qvcStickerEdit(sticker) {
    var s = sticker || {};
    var fields = [
        { name: 'name', label: '名称', type: 'text', value: s.name || '' },
        { name: 'description', label: '描述/用途', type: 'text', value: s.description || '' }
    ];
    qvcShowModal('编辑表情包', fields, async function(data) {
        data.id = s.id;
        try {
            await qvcApi('/api/stickers', 'POST', data);
            qvcHideModal();
            qvcToast('已保存', 'ok');
            qvcLoadStickers();
        } catch (err) {
            qvcToast('保存失败: ' + err.message, 'error');
        }
    });
}

async function qvcStickerDelete(id) {
    qvcConfirm('确定删除此表情包？', async function() {
        try {
            await qvcApi('/api/stickers/delete', 'POST', { id: id });
            qvcToast('已删除', 'ok');
            qvcLoadStickers();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

async function qvcStickerAutofill(id) {
    try {
        qvcToast('正在用视觉模型分析...', 'info');
        var resp = await qvcApi('/api/stickers/autofill', 'POST', { id: id });
        if (resp.ok) {
            qvcToast('描述已自动填充: ' + (resp.description || '').slice(0, 30), 'ok');
            qvcLoadStickers();
        } else {
            qvcToast(resp.error || '填充失败', 'error');
        }
    } catch (e) {
        qvcToast('填充失败: ' + e.message, 'error');
    }
}

// ==================== 记忆管理 ====================
var _qvcMemData = null;

async function qvcLoadMemories() {
    try {
        var [userMemData, groupMemData] = await Promise.all([
            qvcApi('/api/memories', 'GET'),
            qvcApi('/api/memories/group', 'GET')
        ]);
        _qvcMemData = { users: userMemData.memories || [], groups: groupMemData.memories || [] };
        
        // 记忆提取状态提示
        var hintEl = document.getElementById('qvc-memory-hint');
        if (hintEl) {
            if (userMemData.hint) {
                hintEl.innerHTML = '<div style="padding:8px 12px;background:rgba(255,193,7,0.15);border:1px solid rgba(255,193,7,0.3);border-radius:6px;font-size:13px">' + qvcEsc(userMemData.hint) + '</div>';
            } else {
                hintEl.innerHTML = '';
            }
        }
        
        qvcRenderMemories();
    } catch (e) {
        document.getElementById('qvc-memories-list').innerHTML = '<div class="qvc-empty">' + qvcT('toast.load_failed', '加载失败') + ': ' + qvcEsc(e.message) + '</div>';
    }
}

function qvcFilterMemories() {
    qvcRenderMemories();
}

function qvcRenderMemories() {
    if (!_qvcMemData) return;
    var search = (document.getElementById('qvc-memory-search') || {}).value || '';
    search = search.trim().toLowerCase();
    var el = document.getElementById('qvc-memories-list');
    var userMemories = _qvcMemData.users;
    var groupMemories = _qvcMemData.groups;
    
    if (search) {
        userMemories = userMemories.filter(function(m) { return (m.user_id || '').toLowerCase().indexOf(search) >= 0; });
        groupMemories = groupMemories.filter(function(m) { return (m.group_id || '').toLowerCase().indexOf(search) >= 0; });
    }
    
    if (!userMemories.length && !groupMemories.length) {
        el.innerHTML = '<div class="qvc-empty">' + (search ? qvcT('empty.no_memories_match','未找到匹配的记忆') : qvcT('empty.no_memories','暂无存储的记忆')) + '</div>';
        return;
    }
    var html = '';
    if (userMemories.length) {
        html += '<div class="qvc-section-title">用户记忆 (' + userMemories.length + ')</div>';
        userMemories.forEach(function(m) { html += qvcRenderMemoryCard(m, 'user'); });
    }
    if (groupMemories.length) {
        html += '<div class="qvc-section-title" style="margin-top:16px">群组记忆 (' + groupMemories.length + ')</div>';
        groupMemories.forEach(function(m) { html += qvcRenderMemoryCard(m, 'group'); });
    }
    el.innerHTML = html;
}

function qvcRenderMemoryCard(m, type) {
    var id = type === 'user' ? m.user_id : m.group_id;
    var title = type === 'user' ? '用户: ' + id : '群组: ' + id;
    var html = '<div class="qvc-list-item" style="flex-wrap:wrap">';
    html += '<div class="qvc-list-item-info" style="flex:1;min-width:200px">';
    html += '<div class="qvc-list-item-title">' + qvcEsc(title);
    html += ' <span class="qvc-badge qvc-badge-ok">' + m.count + ' 长期</span>';
    if (m.short_term_count !== undefined) html += ' <span class="qvc-badge">' + m.short_term_count + ' 短期</span>';
    if (m.sender_count !== undefined && m.sender_count > 0) html += ' <span class="qvc-badge">' + m.sender_count + ' 发送者</span>';
    html += '</div>';
    if (m.updated) {
        html += '<div class="qvc-list-item-desc">更新于: ' + qvcEsc(m.updated) + '</div>';
    }
    if (m.latest && m.latest.length) {
        html += '<div style="margin-top:4px;font-size:12px;color:#999">最近内容:</div>';
        html += '<div style="font-size:12px;max-height:80px;overflow-y:auto">';
        m.latest.forEach(function(c) {
            html += '<div style="padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.05)">- ' + qvcEsc(c) + '</div>';
        });
        html += '</div>';
    }
    html += '</div>';
    html += '<div class="qvc-list-item-actions" style="align-self:flex-start">';
    if (m.count > 0) {
        html += '<button class="qvc-btn-sm" onclick=\'qvcViewMemoryDetail(' + JSON.stringify(id) + ', "' + type + '")\'>查看详情</button>';
    }
    html += '<button class="qvc-btn-sm danger" onclick=\'qvcDeleteMemory(' + JSON.stringify(id) + ', "' + type + '")\'>__ICON_TRASH__ 删除</button>';
    html += '</div>';
    html += '</div>';
    return html;
}

async function qvcViewMemoryDetail(id, type) {
    try {
        var resp = await qvcApi('/api/memories/detail?user_id=' + encodeURIComponent(id) + '&type=' + type, 'GET');
        if (!resp.ok) { qvcToast(resp.error || '加载失败', 'error'); return; }
        var longTerm = resp.long_term || [];
        var html = '<div style="max-height:60vh;overflow-y:auto">';
        longTerm.forEach(function(entry, i) {
            var content = entry.content || '';
            var tags = (entry.tags || []).join(', ');
            var ts = entry.timestamp || '';
            html += '<div class="qvc-list-item" style="flex-wrap:wrap;border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:8px;margin-bottom:4px">';
            html += '<div style="flex:1;min-width:200px">';
            html += '<div style="font-size:13px;white-space:pre-wrap">' + qvcEsc(content) + '</div>';
            if (tags) html += '<div style="font-size:11px;color:#999;margin-top:2px">标签: ' + qvcEsc(tags) + '</div>';
            if (ts) html += '<div style="font-size:11px;color:#666">' + qvcEsc(ts) + '</div>';
            html += '</div>';
            html += '<div style="display:flex;gap:4px;margin-top:4px">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcEditMemoryEntry(' + JSON.stringify(id) + ', "' + type + '", ' + i + ', ' + JSON.stringify(content) + ')\'>__ICON_EDIT__</button>';
            html += '<button class="qvc-btn-sm danger" onclick=\'qvcDeleteMemoryEntry(' + JSON.stringify(id) + ', "' + type + '", ' + i + ')\'>__ICON_TRASH__</button>';
            html += '</div>';
            html += '</div>';
        });
        html += '</div>';
        
        // 用自定义弹窗展示
        document.getElementById('qvc-modal-title').textContent = (type === 'user' ? '用户' : '群组') + '记忆详情 - ' + id;
        document.getElementById('qvc-modal-body').innerHTML = html;
        document.getElementById('qvc-modal-bg').classList.add('show');
        // 隐藏确定按钮（只展示）
        _qvcModalCallback = null;
    } catch (e) {
        qvcToast(qvcT('toast.load_failed', '加载失败') + ': ' + e.message, 'error');
    }
}

function qvcEditMemoryEntry(id, type, index, oldContent) {
    var fields = [
        { name: 'content', label: '记忆内容', type: 'textarea', value: oldContent }
    ];
    qvcShowModal('编辑记忆', fields, async function(data) {
        try {
            await qvcApi('/api/memories/edit', 'POST', { user_id: id, type: type, index: index, content: data.content, action: 'edit' });
            qvcToast('记忆已更新', 'ok');
            qvcHideModal();
            qvcViewMemoryDetail(id, type);
            qvcLoadMemories();
        } catch (e) {
            qvcToast('更新失败: ' + e.message, 'error');
        }
    });
}

async function qvcDeleteMemoryEntry(id, type, index) {
    qvcConfirm('确定删除这条记忆？', async function() {
        try {
            await qvcApi('/api/memories/edit', 'POST', { user_id: id, type: type, index: index, action: 'delete' });
            qvcToast('记忆已删除', 'ok');
            qvcHideModal();
            qvcViewMemoryDetail(id, type);
            qvcLoadMemories();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

async function qvcDeleteMemory(id, type) {
    var label = type === 'user' ? '用户' : '群组';
    qvcConfirm('确定删除此' + label + '的全部记忆？', async function() {
        try {
            await qvcApi('/api/memories/delete', 'POST', { user_id: id, type: type });
            qvcToast('记忆已删除', 'ok');
            qvcLoadMemories();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

async function qvcClearAllMemories() {
    qvcConfirm('确定清空全部记忆（包括用户和群组）？此操作不可恢复！', async function() {
        try {
            await qvcApi('/api/memories/clear-all', 'POST');
            qvcToast('已清空全部记忆', 'ok');
            qvcLoadMemories();
        } catch (e) {
            qvcToast('清空失败: ' + e.message, 'error');
        }
    });
}

// ==================== 会话管理 ====================
var _qvcSessionData = null;

async function qvcLoadSessions() {
    try {
        var data = await qvcApi('/api/sessions', 'GET');
        _qvcSessionData = data.sessions || [];
        qvcRenderSessions();
    } catch (e) {
        document.getElementById('qvc-sessions-list').innerHTML = '<div class="qvc-empty">' + qvcT('toast.load_failed', '加载失败') + ': ' + qvcEsc(e.message) + '</div>';
    }
}

function qvcFilterSessions() {
    qvcRenderSessions();
}

function qvcRenderSessions() {
    if (!_qvcSessionData) return;
    var search = (document.getElementById('qvc-session-search') || {}).value || '';
    search = search.trim().toLowerCase();
    var sessions = _qvcSessionData;
    if (search) {
        sessions = sessions.filter(function(s) {
            return (s.id || '').toLowerCase().indexOf(search) >= 0 || (s.session_key || '').toLowerCase().indexOf(search) >= 0;
        });
    }
    var el = document.getElementById('qvc-sessions-list');
    if (!sessions.length) {
        el.innerHTML = '<div class="qvc-empty">' + (search ? qvcT('empty.no_sessions_match','未找到匹配的会话') : qvcT('empty.no_sessions','暂无会话记录')) + '</div>';
        return;
    }
    var html = '';
    sessions.forEach(function(s) {
        var typeLabel = s.type === 'group' ? '群聊' : '私聊';
        var typeBadge = s.type === 'group' ? 'qvc-badge-ok' : '';
        html += '<div class="qvc-list-item">';
        html += '<div class="qvc-list-item-info">';
        html += '<div class="qvc-list-item-title">' + qvcEsc(typeLabel) + ' ' + qvcEsc(s.id);
        html += ' <span class="qvc-badge ' + typeBadge + '">' + s.message_count + ' 条消息</span></div>';
        html += '<div class="qvc-list-item-desc">预览: ' + qvcEsc((s.preview || '').substring(0, 50)) + '</div>';
        if (s.last_time) html += '<div class="qvc-list-item-desc">最后活跃: ' + qvcEsc(s.last_time) + '</div>';
        html += '</div>';
        html += '<div class="qvc-list-item-actions">';
        html += '<button class="qvc-btn-sm" onclick=\'qvcViewSession(' + JSON.stringify(s.session_key) + ', ' + JSON.stringify(s.id) + ', "' + s.type + '")\'>查看/编辑</button>';
        html += '<button class="qvc-btn-sm danger" onclick=\'qvcClearSession(' + JSON.stringify(s.session_key) + ')\'>清空</button>';
        html += '</div>';
        html += '</div>';
    });
    el.innerHTML = html;
}

async function qvcViewSession(sessionKey, id, type) {
    try {
        var resp = await qvcApi('/api/sessions/history?session_key=' + encodeURIComponent(sessionKey), 'GET');
        var history = resp.history || [];
        var typeLabel = type === 'group' ? '群聊' : '私聊';
        var html = '<div style="margin-bottom:8px;display:flex;gap:8px">';
        html += '<button class="qvc-btn-sm primary" onclick=\'qvcAddSessionMessage(' + JSON.stringify(sessionKey) + ')\'>__ICON_PLUS__ 添加消息</button>';
        html += '<span style="flex:1"></span>';
        html += '<span class="qvc-badge">' + history.length + ' 条</span>';
        html += '</div>';
        html += '<div style="max-height:55vh;overflow-y:auto">';
        history.forEach(function(msg, i) {
            var roleLabel = msg.role === 'assistant' ? 'AI' : (msg.role === 'user' ? '用户' : msg.role);
            var roleColor = msg.role === 'assistant' ? '#4fc3f7' : '#81c784';
            html += '<div class="qvc-list-item" style="flex-wrap:wrap;border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:8px;margin-bottom:4px">';
            html += '<div style="flex:1;min-width:180px">';
            html += '<div style="font-size:12px;color:' + roleColor + ';font-weight:bold">' + qvcEsc(roleLabel) + (msg.nickname ? ' (' + qvcEsc(msg.nickname) + ')' : '') + '</div>';
            html += '<div style="font-size:13px;white-space:pre-wrap;margin:2px 0">' + qvcEsc(msg.content || '') + '</div>';
            if (msg.timestamp) html += '<div style="font-size:11px;color:#666">' + qvcEsc(msg.timestamp) + '</div>';
            html += '</div>';
            html += '<div style="display:flex;gap:4px">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcEditSessionMsg(' + JSON.stringify(sessionKey) + ', ' + i + ', ' + JSON.stringify(msg.content || '') + ')\'>__ICON_EDIT__</button>';
            html += '<button class="qvc-btn-sm danger" onclick=\'qvcDeleteSessionMsg(' + JSON.stringify(sessionKey) + ', ' + i + ')\'>__ICON_TRASH__</button>';
            html += '</div>';
            html += '</div>';
        });
        html += '</div>';
        
        document.getElementById('qvc-modal-title').textContent = typeLabel + '会话 - ' + id;
        document.getElementById('qvc-modal-body').innerHTML = html;
        document.getElementById('qvc-modal-bg').classList.add('show');
        _qvcModalCallback = null;
    } catch (e) {
        qvcToast(qvcT('toast.load_failed', '加载失败') + ': ' + e.message, 'error');
    }
}

function qvcEditSessionMsg(sessionKey, index, oldContent) {
    var fields = [
        { name: 'content', label: '消息内容', type: 'textarea', value: oldContent }
    ];
    qvcShowModal('编辑消息', fields, async function(data) {
        try {
            await qvcApi('/api/sessions/edit', 'POST', { session_key: sessionKey, index: index, content: data.content });
            qvcToast('消息已更新', 'ok');
            qvcHideModal();
            // 重新打开会话视图
            var sk = sessionKey;
            var id = sk.replace(/^(group|user):/, '');
            var type = sk.startsWith('group:') ? 'group' : 'user';
            qvcViewSession(sk, id, type);
        } catch (e) {
            qvcToast('更新失败: ' + e.message, 'error');
        }
    });
}

async function qvcDeleteSessionMsg(sessionKey, index) {
    qvcConfirm('确定删除这条消息？', async function() {
        try {
            await qvcApi('/api/sessions/delete', 'POST', { session_key: sessionKey, index: index });
            qvcToast('消息已删除', 'ok');
            qvcHideModal();
            var id = sessionKey.replace(/^(group|user):/, '');
            var type = sessionKey.startsWith('group:') ? 'group' : 'user';
            qvcViewSession(sessionKey, id, type);
            qvcLoadSessions();
        } catch (e) {
            qvcToast(qvcT('toast.delete_failed', '删除失败') + ': ' + e.message, 'error');
        }
    });
}

function qvcAddSessionMessage(sessionKey) {
    var fields = [
        { name: 'role', label: '角色', type: 'select', value: 'user', options: [
            { label: '用户 (user)', value: 'user' },
            { label: 'AI (assistant)', value: 'assistant' }
        ]},
        { name: 'content', label: '消息内容', type: 'textarea', value: '' }
    ];
    qvcShowModal('添加消息', fields, async function(data) {
        try {
            await qvcApi('/api/sessions/add', 'POST', { session_key: sessionKey, role: data.role, content: data.content });
            qvcToast('消息已添加', 'ok');
            qvcHideModal();
            var id = sessionKey.replace(/^(group|user):/, '');
            var type = sessionKey.startsWith('group:') ? 'group' : 'user';
            qvcViewSession(sessionKey, id, type);
            qvcLoadSessions();
        } catch (e) {
            qvcToast('添加失败: ' + e.message, 'error');
        }
    });
}

async function qvcClearSession(sessionKey) {
    qvcConfirm('确定清空此会话的全部历史消息？', async function() {
        try {
            await qvcApi('/api/sessions/clear', 'POST', { session_key: sessionKey });
            qvcToast('会话已清空', 'ok');
            qvcLoadSessions();
        } catch (e) {
            qvcToast('清空失败: ' + e.message, 'error');
        }
    });
}

function qvcStickerUploadBatch() {
    var fields = [
        { name: 'files', label: '选择图片文件（可多选）', type: 'file', value: '', attrs: 'multiple accept="image/*"' }
    ];
    qvcShowModal('批量上传表情包', fields, async function(data) {
        var fileInput = document.querySelector('[data-field="files"]');
        if (!fileInput || !fileInput.files || !fileInput.files.length) {
            qvcToast('请选择至少一个图片文件', 'error');
            return;
        }
        var files = fileInput.files;
        var total = files.length;
        var success = 0;
        var fail = 0;
        var token = localStorage.getItem('__ep_tk__');
        for (var i = 0; i < total; i++) {
            var formData = new FormData();
            var name = files[i].name;
            var dotIdx = name.lastIndexOf('.');
            if (dotIdx > 0) name = name.substring(0, dotIdx);
            formData.append('name', name);
            formData.append('description', '');
            formData.append('file', files[i]);
            try {
                var resp = await fetch('/QvQChat/api/stickers/upload', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + (token || '') },
                    body: formData
                });
                var result = await resp.json();
                if (resp.ok && !result.error) {
                    success++;
                } else {
                    fail++;
                }
            } catch (e) {
                fail++;
            }
            qvcToast('批量上传进度: ' + (i + 1) + '/' + total, 'info');
        }
        qvcHideModal();
        qvcToast('批量上传完成: ' + success + ' 成功, ' + fail + ' 失败', fail > 0 ? 'error' : 'ok');
        qvcLoadStickers();
    });
}

// ==================== 群组管理 ====================
async function qvcLoadGroups() {
    try {
        var data = await qvcApi('/api/groups', 'GET');
        var groups = data.groups || data || [];
        var el = document.getElementById('qvc-groups-list');
        if (!groups.length) {
            el.innerHTML = '<div class="qvc-empty">暂无群组（群组在收到第一条消息后自动注册）</div>';
            return;
        }
        var html = '';
        groups.forEach(function(g) {
            var cfg = g.config || {};
            var displayName = cfg.group_name || g.id;
            var badges = '';
            badges += '<span class="qvc-badge ' + (cfg.enable_ai !== false ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (cfg.enable_ai !== false ? qvcT('badge.ai_on','AI启用') : qvcT('badge.ai_off','AI关闭')) + '</span> ';
            badges += '<span class="qvc-badge ' + (cfg.enable_memory !== false ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (cfg.enable_memory !== false ? qvcT('badge.mem_on','记忆') : qvcT('badge.mem_off','无记忆')) + '</span> ';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(displayName) + ' ' + badges + '</div>';
            html += '<div class="qvc-list-item-desc">ID: ' + qvcEsc(g.id) + ' / 记忆: ' + qvcEsc(cfg.memory_mode || 'mixed') + '</div>';
            if (cfg.system_prompt) {
                html += '<div class="qvc-list-item-desc">提示词: ' + qvcEsc(cfg.system_prompt.substring(0, 60)) + '...</div>';
            }
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcGroupEdit(' + JSON.stringify(g) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            html += '</div>';
            html += '</div>';
        });
        el.innerHTML = html;
    } catch (e) {
        qvcToast('加载群组失败: ' + e.message, 'error');
    }
}

function qvcGroupEdit(group) {
    var g = group || {};
    var cfg = g.config || {};
    // 获取可用智能体列表
    var agentOptions = [{ label: '默认（自动选择）', value: '' }];
    // 异步加载智能体列表后追加选项
    (async function() {
        try {
            var agentData = await qvcApi('/api/agents', 'GET');
            var agents = agentData.agents || agentData || [];
            var selectEl = document.querySelector('[data-field="_agent_id"]');
            agents.forEach(function(a) {
                if (a.enabled !== false) {
                    var opt = document.createElement('option');
                    opt.value = a.id;
                    opt.textContent = a.name + (a.is_default ? ' (默认)' : '');
                    if (cfg._agent_id === a.id) opt.selected = true;
                    if (selectEl) selectEl.appendChild(opt);
                }
            });
        } catch (e) {}
    })();

    var fields = [
        { name: 'group_name', label: '群名称', type: 'text', value: cfg.group_name || '' },
        { name: '_agent_id', label: '绑定智能体', type: 'select', value: cfg._agent_id || '', options: agentOptions },
        { name: 'system_prompt', label: '群专属提示词（覆盖智能体设定）', type: 'textarea', value: cfg.system_prompt || '' },
        {
            name: 'memory_mode',
            label: '记忆模式',
            type: 'select',
            value: cfg.memory_mode || 'mixed',
            options: [
                { label: '混合模式（推荐）', value: 'mixed' },
                { label: '仅发送者模式', value: 'sender_only' }
            ]
        },
        { name: 'enable_memory', label: '启用记忆', type: 'checkbox', value: cfg.enable_memory !== false },
        { name: 'enable_ai', label: '启用 AI', type: 'checkbox', value: cfg.enable_ai !== false }
    ];
    qvcShowModal('编辑群组', fields, async function(data) {
        var agentId = data._agent_id;
        var payload = { id: g.id, config: data };
        delete payload.config._agent_id;
        if (agentId) payload.config._agent_id = agentId;
        try {
            await qvcApi('/api/groups', 'POST', payload);
            // 绑定智能体
            var sessionKey = 'group:' + g.id;
            if (agentId) {
                await qvcApi('/api/agents/bind', 'POST', { agent_id: agentId, session_key: sessionKey });
            } else {
                await qvcApi('/api/agents/bind', 'POST', { action: 'unbind', session_key: sessionKey });
            }
            qvcHideModal();
            qvcToast('群组配置已保存', 'ok');
            qvcLoadGroups();
        } catch (e) {
            qvcToast(qvcT('toast.save_failed', '保存失败') + ': ' + e.message, 'error');
        }
    });
}

// ==================== 通用弹窗 ====================
function qvcShowModal(title, fields, callback) {
    document.getElementById('qvc-modal-title').textContent = title;
    var body = document.getElementById('qvc-modal-body');
    var html = '';
    // 字段标签按 field.name 翻译（modal.<name>），无翻译时回退中文
    var tlabel = function(f) { return qvcT('modal.' + f.name, f.label); };
    fields.forEach(function(f) {
        if (f.type === 'checkbox-group') {
            html += '<div class="qvc-form-group">';
            html += '<label>' + qvcEsc(tlabel(f)) + '</label>';
            var selected = f.value || [];
            (f.options || []).forEach(function(opt) {
                var checked = selected.indexOf(opt.value) >= 0 ? 'checked' : '';
                html += '<label class="qvc-checkbox-row">';
                html += '<input type="checkbox" data-group="' + qvcEsc(f.name) + '" value="' + qvcEsc(opt.value) + '"' + (checked ? ' checked' : '') + '>';
                html += qvcEsc(opt.label);
                html += '</label>';
            });
            html += '</div>';
        } else if (f.type === 'checkbox') {
            html += '<label class="qvc-checkbox-row">';
            html += '<input type="checkbox" data-field="' + qvcEsc(f.name) + '"' + (f.value ? ' checked' : '') + '>';
            html += qvcEsc(tlabel(f));
            html += '</label>';
        } else if (f.type === 'textarea') {
            html += '<div class="qvc-form-group">';
            html += '<label>' + qvcEsc(tlabel(f)) + '</label>';
            html += '<textarea class="qvc-textarea" data-field="' + qvcEsc(f.name) + '" placeholder="' + qvcEsc(f.placeholder || '') + '">' + qvcEsc(f.value != null ? String(f.value) : '') + '</textarea>';
            html += '</div>';
        } else if (f.type === 'select') {
            html += '<div class="qvc-form-group">';
            html += '<label>' + qvcEsc(tlabel(f)) + '</label>';
            html += '<select class="qvc-select" data-field="' + qvcEsc(f.name) + '">';
            (f.options || []).forEach(function(opt) {
                var sel = opt.value === f.value ? ' selected' : '';
                html += '<option value="' + qvcEsc(opt.value) + '"' + sel + '>' + qvcEsc(opt.label) + '</option>';
            });
            html += '</select>';
            html += '</div>';
        } else if (f.type === 'html') {
            html += '<div class="qvc-form-group">';
            html += '<p style="white-space:pre-wrap;line-height:1.6;color:var(--tx-c);margin:8px 0">' + qvcEsc(f.label) + '</p>';
            html += '</div>';
        } else if (f.type === 'range') {
            var min = f.min != null ? f.min : 0;
            var max = f.max != null ? f.max : 1;
            var step = f.step != null ? f.step : 0.05;
            var rval = f.value != null ? f.value : (min + max) / 2;
            html += '<div class="qvc-slider-group">';
            html += '<div class="qvc-slider-label"><span>' + qvcEsc(tlabel(f)) + '</span>';
            html += '<span class="qvc-slider-val" id="modal-slider-' + qvcEsc(f.name) + '">' + rval + '</span></div>';
            html += '<input type="range" class="qvc-range" data-field="' + qvcEsc(f.name) + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + rval + '"';
            html += ' oninput="document.getElementById(\'modal-slider-' + qvcEsc(f.name) + '\').textContent=this.value">';
            html += '</div>';
        } else {
            // text / number / file
            var extraAttr = f.attrs || '';
            html += '<div class="qvc-form-group">';
            html += '<label>' + qvcEsc(tlabel(f)) + '</label>';
            html += '<input type="' + f.type + '" step="any" class="qvc-input" data-field="' + qvcEsc(f.name) + '" value="' + qvcEsc(f.value != null ? String(f.value) : '') + '" placeholder="' + qvcEsc(f.placeholder || '') + '" ' + extraAttr + '>';
            html += '</div>';
        }
    });
    body.innerHTML = html;
    _qvcModalCallback = callback;
    _qvcModalFields = fields;
    document.getElementById('qvc-modal-bg').classList.add('show');
}

function qvcHideModal() {
    document.getElementById('qvc-modal-bg').classList.remove('show');
    _qvcModalCallback = null;
    _qvcModalFields = [];
    // 恢复底部按钮（Playground 可能隐藏了）
    var footer = document.querySelector('.qvc-modal-footer');
    if (footer) footer.style.display = '';
}

function qvcModalSave() {
    var data = {};
    _qvcModalFields.forEach(function(f) {
        if (f.type === 'checkbox-group') {
            var checked = document.querySelectorAll('[data-group="' + f.name + '"]:checked');
            data[f.name] = Array.prototype.slice.call(checked).map(function(el) { return el.value; });
        } else if (f.type === 'checkbox') {
            data[f.name] = document.querySelector('[data-field="' + f.name + '"]').checked;
        } else if (f.type === 'number') {
            var el = document.querySelector('[data-field="' + f.name + '"]');
            var val = el.value;
            data[f.name] = val === '' ? null : Number(val);
        } else if (f.type === 'range') {
            var el = document.querySelector('[data-field="' + f.name + '"]');
            data[f.name] = el ? Number(el.value) : null;
        } else if (f.type === 'html') {
            // 纯展示字段，不收集数据
        } else {
            data[f.name] = document.querySelector('[data-field="' + f.name + '"]').value;
        }
    });
    if (_qvcModalCallback) {
        _qvcModalCallback(data);
    }
}

// ==================== 导出/导入 ====================
async function qvcExport(mode) {
    try {
        qvcToast('正在导出...', 'info');
        var token = localStorage.getItem('__ep_tk__');
        var resp = await fetch('/QvQChat/api/export', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + (token || ''),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ mode: mode })
        });
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return { error: 'HTTP ' + resp.status }; });
            throw new Error(err.error || '导出失败');
        }
        var blob = await resp.blob();
        var a = document.createElement('a');
        var filename = 'qvqchat_export_' + mode + '.zip';
        var cd = resp.headers.get('Content-Disposition') || '';
        var m = cd.match(/filename="?(.+?)"?$/);
        if (m) filename = m[1];
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
        qvcToast('导出成功', 'ok');
    } catch (e) {
        qvcToast(qvcT('toast.export_failed', '导出失败') + ': ' + e.message, 'error');
    }
}

function qvcImport() {
    var fields = [
        { name: 'file', label: '选择导出文件 (.zip)', type: 'file', value: '' }
    ];
    qvcShowModal('导入配置', fields, function(data) {
        var fileInput = document.querySelector('[data-field="file"]');
        if (!fileInput || !fileInput.files || !fileInput.files[0]) {
            qvcToast('请选择文件', 'error');
            return;
        }
        qvcConfirm('导入将覆盖当前所有配置，确定继续？', async function() {
            var formData = new FormData();
            formData.append('file', fileInput.files[0]);
            try {
                var token = localStorage.getItem('__ep_tk__');
                var resp = await fetch('/QvQChat/api/import', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + (token || '') },
                    body: formData
                });
                var result = await resp.json();
                if (!resp.ok || result.error) throw new Error(result.error || '导入失败');
                qvcHideModal();
                qvcToast(result.msg || '导入成功', 'ok');
            } catch (err) {
                qvcToast('导入失败: ' + err.message, 'error');
            }
        });
    });
}

// ==================== 通用确认对话框 ====================
function qvcConfirm(msg, callback) {
    var fields = [
        { name: '_msg', label: msg, type: 'html', value: '' }
    ];
    qvcShowModal('确认操作', fields, function(data) {
        qvcHideModal();
        if (callback) callback();
    });
}

// ==================== 批量操作 ====================
var _qvcSelectMode = false;

function qvcStickerToggleSelect() {
    _qvcSelectMode = !_qvcSelectMode;
    var grid = document.getElementById('qvc-stickers-list');
    var toolbar = document.getElementById('qvc-sticker-toolbar');
    var btn = document.getElementById('qvc-sticker-select-btn');
    if (_qvcSelectMode) {
        grid.classList.add('qvc-select-mode');
        btn.textContent = '取消';
        // 清空选择
        document.querySelectorAll('.qvc-sticker-cb').forEach(function(cb) { cb.checked = false; });
        // 展开工具栏（重新触发动画）
        toolbar.style.display = 'flex';
        toolbar.style.animation = 'none';
        void toolbar.offsetHeight;
        toolbar.style.animation = 'qvcSlideDown 0.2s ease-out';
        document.getElementById('qvc-sticker-selcount').style.display = 'none';
        // 卡片点击选择
        grid.onclick = function(e) {
            var card = e.target.closest('.qvc-sticker-card');
            if (!card) return;
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') return;
            var cb = card.querySelector('.qvc-sticker-cb');
            if (cb) cb.checked = !cb.checked;
            qvcStickerUpdateToolbar();
        };
    } else {
        grid.classList.remove('qvc-select-mode');
        grid.onclick = null;
        btn.textContent = '选择';
        toolbar.style.display = 'none';
    }
}

function qvcStickerUpdateToolbar() {
    if (!_qvcSelectMode) return;
    var checked = [];
    document.querySelectorAll('.qvc-sticker-cb').forEach(function(cb) { if (cb.checked) checked.push(cb.value); });
    var count = document.getElementById('qvc-sticker-selcount');
    if (checked.length) {
        count.style.display = '';
        count.textContent = '已选 ' + checked.length + ' 个';
    } else {
        count.style.display = 'none';
    }
}

function qvcStickerSelectAll() {
    document.querySelectorAll('.qvc-sticker-cb').forEach(function(cb) { cb.checked = true; });
    qvcStickerUpdateToolbar();
}

function qvcStickerDeselect() {
    document.querySelectorAll('.qvc-sticker-cb').forEach(function(cb) { cb.checked = false; });
    qvcStickerUpdateToolbar();
}

function qvcStickerBatchDelete() {
    var checked = [];
    document.querySelectorAll('.qvc-sticker-cb').forEach(function(cb) { if (cb.checked) checked.push(cb.value); });
    if (!checked.length) { qvcToast('请先选择要删除的表情包', 'info'); return; }
    qvcConfirm('确定删除选中的 ' + checked.length + ' 个表情包？', async function() {
        var done = 0;
        for (var i = 0; i < checked.length; i++) {
            try {
                await qvcApi('/api/stickers/delete', 'POST', { id: checked[i] });
                done++;
            } catch (_) {}
        }
        document.querySelectorAll('.qvc-sticker-cb').forEach(function(cb) { cb.checked = false; });
        qvcStickerUpdateToolbar();
        qvcToast('已删除 ' + done + ' 个表情包', 'ok');
        qvcLoadStickers();
    });
}

function qvcStickerBatchGenerate() {
    var checked = [];
    document.querySelectorAll('.qvc-sticker-cb').forEach(function(cb) { if (cb.checked) checked.push(cb.value); });
    if (!checked.length) { qvcToast('请先选择要分析的表情包', 'info'); return; }
    qvcConfirm('将用视觉模型分析选中的 ' + checked.length + ' 个表情包，确定继续？', async function() {
        var done = 0, fail = 0;
        for (var i = 0; i < checked.length; i++) {
            try {
                var resp = await qvcApi('/api/stickers/autofill', 'POST', { id: checked[i] });
                if (resp.ok) done++; else fail++;
            } catch (_) { fail++; }
            qvcToast('AI 分析进度: ' + (i + 1) + '/' + checked.length, 'info');
        }
        document.querySelectorAll('.qvc-sticker-cb').forEach(function(cb) { cb.checked = false; });
        qvcStickerUpdateToolbar();
        qvcToast('AI 分析完成: 成功' + done + '，失败' + fail, fail > 0 ? 'error' : 'ok');
        qvcLoadStickers();
    });
}

// ==================== 重置 ====================
function qvcResetAll() {
    qvcConfirm(
        '确定清除所有 QvQChat 数据？此操作不可恢复！包括：全部配置、模型、行为、智能体、知识库、MCP工具、MCP服务器、表情包、记忆、会话历史。清除后请刷新页面并重启模块。',
        async function() {
            try {
                var resp = await qvcApi('/api/reset', 'POST');
                qvcToast(resp.msg || '已清除所有数据', 'ok');
                setTimeout(function() { location.reload(); }, 2000);
            } catch (e) {
                qvcToast(qvcT('toast.reset_failed', '重置失败') + ': ' + e.message, 'error');
            }
        }
    );
}

// ==================== 初始化 ====================
function loadQvQChatView() {
    // 实时拉取 i18n 翻译（跟随框架语言切换），然后应用页面级 i18n
    qvcLoadI18n().then(function() {
        qvcApplyI18n();
    });
    // 点击背景关闭弹窗
    var bg = document.getElementById('qvc-modal-bg');
    if (bg) {
        bg.addEventListener('click', function(e) {
            if (e.target === bg) qvcHideModal();
        });
    }
    // ESC 关闭弹窗
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') qvcHideModal();
    });
    // 加载概览
    qvcLoadOverview();
}
"""
