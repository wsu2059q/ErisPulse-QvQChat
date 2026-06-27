"""Dashboard JavaScript 常量"""

SCRIPTS = r"""
// ==================== 全局状态 ====================
var _qvcLoaded = {};
var _qvcModalCallback = null;
var _qvcModalFields = [];
var _qvcBasicConfig = {};

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
            agents: qvcLoadAgents,
            knowledge: qvcLoadKnowledge,
            tools: qvcLoadTools,
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

        var cards = [
            { num: modelStats.total || 0, label: 'AI 模型' },
            { num: behaviorStats.total || 0, label: '行为定义' },
            { num: agentStats.total || 0, label: '智能体' },
            { num: kbStats.total || 0, label: '知识条目' },
            { num: toolStats.total || 0, label: 'MCP 工具' },
            { num: data.active_groups || 0, label: '活跃群组' }
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
            { num: rt.uptime || '-', label: '运行时间' },
            { num: rt.total_messages || 0, label: '接收消息' },
            { num: rt.total_replies || 0, label: '发送回复' },
            { num: rt.reply_rate || '0%', label: '回复率' },
            { num: (rt.total_tokens_est || 0).toLocaleString(), label: '估算 Token' }
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
            { label: '对话行为', ok: aiStatus.dialogue },
            { label: '记忆提取', ok: aiStatus.memory },
            { label: '意图识别', ok: aiStatus.intent },
            { label: '图片分析', ok: aiStatus.vision },
            { label: '回复判断', ok: aiStatus.reply_judge }
        ];
        var aiHtml = '';
        rows.forEach(function(r) {
            var cls = r.ok ? 'qvc-badge-ok' : 'qvc-badge-off';
            var txt = r.ok ? '正常' : '未就绪';
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
            { key: 'stalker_mode', label: '窥屏模式', path: 'stalker_mode.enabled' },
            { key: 'continue_conversation', label: '对话连续性', path: 'continue_conversation.enabled' },
            { key: 'knowledge_base', label: '知识库注入', path: 'knowledge_base.enabled' },
            { key: 'mcp', label: 'MCP 工具调用', path: 'mcp.enabled' },
            { key: 'multi_agent', label: '多智能体', path: 'multi_agent.enabled' },
            { key: 'voice', label: '语音合成', path: 'voice.enabled' }
        ];
        featMap.forEach(function(f) {
            var on = features[f.key];
            var cls = on ? 'qvc-badge-ok' : 'qvc-badge-off';
            var txt = on ? '已启用' : '已关闭';
            featHtml += '<div class="qvc-list-item" style="cursor:pointer" onclick="qvcToggleFeature(\'' + f.path + '\', \'' + f.key + '\')">';
            featHtml += '<div class="qvc-list-item-info"><div class="qvc-list-item-title">' + qvcEsc(f.label) + '</div></div>';
            featHtml += '<span class="qvc-badge ' + cls + '" id="qvc-feat-' + f.key + '">' + txt + '</span>';
            featHtml += '</div>';
        });
        document.getElementById('qvc-overview-features').innerHTML = featHtml;
    } catch (e) {
        qvcToast('加载概览失败: ' + e.message, 'error');
    }
}

async function qvcToggleFeature(path, key) {
    try {
        var data = await qvcApi('/api/config', 'GET');
        var cfg = data.config || {};
        // 获取当前值
        var keys = path.split('.');
        var cur = cfg;
        for (var i = 0; i < keys.length; i++) {
            if (cur == null || typeof cur !== 'object') { cur = null; break; }
            cur = cur[keys[i]];
        }
        var newVal = !(cur === true || cur === 'true');
        // 发送单个键的切换
        var body = {};
        body[path] = newVal;
        await qvcApi('/api/config', 'POST', body);
        // 更新 UI
        var el = document.getElementById('qvc-feat-' + key);
        if (el) {
            el.className = 'qvc-badge ' + (newVal ? 'qvc-badge-ok' : 'qvc-badge-off');
            el.textContent = newVal ? '已启用' : '已关闭';
        }
        qvcToast((newVal ? '已启用' : '已关闭') + ': ' + key, 'ok');
    } catch (e) {
        qvcToast('切换失败: ' + e.message, 'error');
    }
}

// ==================== 基础设置 ====================
async function qvcLoadBasic() {
    try {
        var data = await qvcApi('/api/config', 'GET');
        _qvcBasicConfig = data.config || data || {};
        var cfg = _qvcBasicConfig;
        var html = '';

        // 机器人身份
        html += '<div class="qvc-section-title">机器人身份</div>';
        html += qvcArrayField('bot_nicknames', '机器人昵称（逗号分隔）', qvcGetPath(cfg, 'bot_nicknames', []));
        html += qvcArrayField('bot_ids', '机器人 ID（逗号分隔）', qvcGetPath(cfg, 'bot_ids', []));

        // 消息限制
        html += '<div class="qvc-section-title">消息限制</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('max_history_length', '最大历史长度', qvcGetPath(cfg, 'max_history_length', 20));
        html += qvcNumField('min_reply_interval', '最小回复间隔（秒）', qvcGetPath(cfg, 'min_reply_interval', 10));
        html += '</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('max_message_length', '最大消息长度', qvcGetPath(cfg, 'max_message_length', 1000));
        html += qvcNumField('rate_limit_tokens', '速率限制 Tokens', qvcGetPath(cfg, 'rate_limit_tokens', 20000));
        html += '</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('rate_limit_window', '速率限制窗口（秒）', qvcGetPath(cfg, 'rate_limit_window', 60));
        html += '</div>';
        html += qvcCheckField('ignore_command_messages', '忽略命令消息（以/开头）', qvcGetPath(cfg, 'ignore_command_messages', true));

        // 窥屏模式
        html += '<div class="qvc-section-title">窥屏模式</div>';
        html += qvcCheckField('stalker_mode.enabled', '启用窥屏模式', qvcGetPath(cfg, 'stalker_mode.enabled', true));
        html += '<div class="qvc-form-row">';
        html += qvcNumField('stalker_mode.default_probability', '默认回复概率', qvcGetPath(cfg, 'stalker_mode.default_probability', 0.03));
        html += qvcNumField('stalker_mode.mention_probability', '被@回复概率', qvcGetPath(cfg, 'stalker_mode.mention_probability', 0.8));
        html += '</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('stalker_mode.keyword_probability', '关键词回复概率', qvcGetPath(cfg, 'stalker_mode.keyword_probability', 0.5));
        html += qvcNumField('stalker_mode.min_messages_between_replies', '两次回复最小间隔消息数', qvcGetPath(cfg, 'stalker_mode.min_messages_between_replies', 15));
        html += '</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('stalker_mode.max_replies_per_hour', '每小时最大回复数', qvcGetPath(cfg, 'stalker_mode.max_replies_per_hour', 8));
        html += qvcNumField('stalker_mode.silence_threshold_minutes', '沉寂阈值（分钟）', qvcGetPath(cfg, 'stalker_mode.silence_threshold_minutes', 30));
        html += '</div>';

        // 对话连续性
        html += '<div class="qvc-section-title">对话连续性</div>';
        html += qvcCheckField('continue_conversation.enabled', '启用对话连续性', qvcGetPath(cfg, 'continue_conversation.enabled', true));
        html += '<div class="qvc-form-row">';
        html += qvcNumField('continue_conversation.max_messages', '最大监听消息数', qvcGetPath(cfg, 'continue_conversation.max_messages', 3));
        html += qvcNumField('continue_conversation.max_duration', '监听时长（秒）', qvcGetPath(cfg, 'continue_conversation.max_duration', 120));
        html += '</div>';

        // 知识库
        html += '<div class="qvc-section-title">知识库</div>';
        html += qvcCheckField('knowledge_base.enabled', '启用知识库注入', qvcGetPath(cfg, 'knowledge_base.enabled', true));
        html += '<div class="qvc-form-row">';
        html += qvcNumField('knowledge_base.max_context_tokens', '最大上下文 Tokens', qvcGetPath(cfg, 'knowledge_base.max_context_tokens', 2000));
        html += '</div>';
        html += qvcCheckField('knowledge_base.auto_search', '自动搜索匹配', qvcGetPath(cfg, 'knowledge_base.auto_search', true));

        // MCP 工具
        html += '<div class="qvc-section-title">MCP 工具</div>';
        html += qvcCheckField('mcp.enabled', '启用 MCP 工具', qvcGetPath(cfg, 'mcp.enabled', true));
        html += qvcCheckField('mcp.auto_inject', '自动注入工具定义', qvcGetPath(cfg, 'mcp.auto_inject', true));

        // 多智能体
        html += '<div class="qvc-section-title">多智能体</div>';
        html += qvcCheckField('multi_agent.enabled', '启用多智能体', qvcGetPath(cfg, 'multi_agent.enabled', true));

        // 语音合成
        html += '<div class="qvc-section-title">语音合成</div>';
        html += qvcCheckField('voice.enabled', '启用语音合成', qvcGetPath(cfg, 'voice.enabled', false));
        html += '<div class="qvc-form-row">';
        html += qvcTextField('voice.api_url', 'API 地址', qvcGetPath(cfg, 'voice.api_url', ''));
        html += qvcTextField('voice.model', '模型', qvcGetPath(cfg, 'voice.model', ''));
        html += '</div>';
        html += '<div class="qvc-form-row">';
        html += qvcTextField('voice.api_key', 'API 密钥', qvcGetPath(cfg, 'voice.api_key', ''));
        html += qvcTextField('voice.voice', '音色', qvcGetPath(cfg, 'voice.voice', ''));
        html += '</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('voice.speed', '语速', qvcGetPath(cfg, 'voice.speed', 1.0));
        html += qvcNumField('voice.sample_rate', '采样率', qvcGetPath(cfg, 'voice.sample_rate', 44100));
        html += '</div>';

        // 个体化设置
        html += '<div class="qvc-section-title">个体化设置</div>';
        html += '<div class="qvc-form-row">';
        html += qvcCheckField('humanize.typing_delay', '打字延迟', qvcGetPath(cfg, 'humanize.typing_delay', true));
        html += qvcNumField('humanize.random_at_probability', '随机@概率', qvcGetPath(cfg, 'humanize.random_at_probability', 0.15));
        html += '</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('humanize.min_delay', '最小延迟(秒)', qvcGetPath(cfg, 'humanize.min_delay', 0.5));
        html += qvcNumField('humanize.max_delay', '最大延迟(秒)', qvcGetPath(cfg, 'humanize.max_delay', 5.0));
        html += '</div>';

        // 夜间模式
        html += '<div class="qvc-section-title">夜间模式</div>';
        html += '<div class="qvc-form-row">';
        html += qvcCheckField('stalker_mode.night_mode.enabled', '启用夜间窥屏', qvcGetPath(cfg, 'stalker_mode.night_mode.enabled', true));
        html += qvcNumField('stalker_mode.night_mode.begin', '开始(时)', qvcGetPath(cfg, 'stalker_mode.night_mode.begin', 23));
        html += qvcNumField('stalker_mode.night_mode.end', '结束(时)', qvcGetPath(cfg, 'stalker_mode.night_mode.end', 7));
        html += '</div>';

        // 回复触发概率
        html += '<div class="qvc-section-title">回复触发概率</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('stalker_mode.question_probability', '提问触发', qvcGetPath(cfg, 'stalker_mode.question_probability', 0.6));
        html += qvcNumField('stalker_mode.hot_topic_probability', '热度触发', qvcGetPath(cfg, 'stalker_mode.hot_topic_probability', 0.3));
        html += '</div>';
        html += '<div class="qvc-form-row">';
        html += qvcNumField('stalker_mode.sticker_emoji_probability', '表情触发', qvcGetPath(cfg, 'stalker_mode.sticker_emoji_probability', 0.15));
        html += qvcNumField('stalker_mode.default_probability', '基础概率', qvcGetPath(cfg, 'stalker_mode.default_probability', 0.03));
        html += '</div>';

        document.getElementById('qvc-basic-form').innerHTML = html;
    } catch (e) {
        document.getElementById('qvc-basic-form').innerHTML = '<div class="qvc-empty">加载失败: ' + qvcEsc(e.message) + '</div>';
    }
}

function qvcTextField(path, label, val) {
    return '<div class="qvc-form-group">' +
        '<label>' + qvcEsc(label) + '</label>' +
        '<input type="text" class="qvc-input" data-path="' + qvcEsc(path) + '" value="' + qvcEsc(val) + '">' +
        '</div>';
}

function qvcNumField(path, label, val) {
    return '<div class="qvc-form-group">' +
        '<label>' + qvcEsc(label) + '</label>' +
        '<input type="number" step="any" class="qvc-input" data-path="' + qvcEsc(path) + '" value="' + qvcEsc(val) + '">' +
        '</div>';
}

function qvcCheckField(path, label, checked) {
    return '<label class="qvc-checkbox-row">' +
        '<input type="checkbox" data-path="' + qvcEsc(path) + '"' + (checked ? ' checked' : '') + '>' +
        qvcEsc(label) +
        '</label>';
}

function qvcArrayField(path, label, arr) {
    var str = Array.isArray(arr) ? arr.join(', ') : '';
    return '<div class="qvc-form-group">' +
        '<label>' + qvcEsc(label) + '</label>' +
        '<input type="text" class="qvc-input" data-array="' + qvcEsc(path) + '" value="' + qvcEsc(str) + '">' +
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
            } else if (el.type === 'number') {
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
        qvcToast('配置已保存', 'ok');
    } catch (e) {
        qvcToast('保存失败: ' + e.message, 'error');
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
            if (caps.chat) badges += '<span class="qvc-badge qvc-badge-ok">文本</span> ';
            if (caps.vision) badges += '<span class="qvc-badge qvc-badge-ok">视觉</span> ';
            if (caps.tools) badges += '<span class="qvc-badge qvc-badge-ok">工具</span> ';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(m.name || '未命名') + ' ' + badges + '</div>';
            html += '<div class="qvc-list-item-desc">' + qvcEsc(m.model || '') + ' / ' + qvcEsc(m.base_url || '') + '</div>';
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcModelEdit(' + JSON.stringify(m) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            html += '<button class="qvc-btn-sm danger" onclick="qvcModelDelete(' + JSON.stringify(qvcEsc(m.id)) + ')">' + '__ICON_TRASH__' + ' 删除</button>';
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
    qvcShowModal(model ? '编辑模型' : '添加模型', fields, async function(data) {
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
            qvcToast('模型已保存', 'ok');
            qvcLoadModels();
        } catch (e) {
            qvcToast('保存失败: ' + e.message, 'error');
        }
    });
}

async function qvcModelDelete(id) {
    if (!confirm('确定删除此模型？')) return;
    try {
        await qvcApi('/api/models/delete', 'POST', { id: id });
        qvcToast('模型已删除', 'ok');
        qvcLoadModels();
    } catch (e) {
        qvcToast('删除失败: ' + e.message, 'error');
    }
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
            badges += '<span class="qvc-badge ' + (b.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (b.enabled ? '启用' : '禁用') + '</span> ';
            if (b.is_builtin) badges += '<span class="qvc-badge qvc-badge-off">内置</span> ';
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
                html += '<button class="qvc-btn-sm danger" onclick="qvcBehaviorDelete(' + JSON.stringify(qvcEsc(b.id)) + ')">' + '__ICON_TRASH__' + ' 删除</button>';
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
        { name: 'response_template', label: '输出模板（可选，支持 {ai_response}/{at_user}）', type: 'textarea', value: b.response_template || '', placeholder: '例: {ai_response}\n[img]https://x.com/sticker.png[/img]' },
        { name: 'trigger_probability', label: '模板触发概率 (0=从不)', type: 'number', value: b.trigger_probability != null ? b.trigger_probability : 0 }
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
            qvcToast('行为已保存', 'ok');
            qvcLoadBehaviors();
        } catch (e) {
            qvcToast('保存失败: ' + e.message, 'error');
        }
    });
}

async function qvcBehaviorDelete(id) {
    if (!confirm('确定删除此行为？')) return;
    try {
        await qvcApi('/api/behaviors/delete', 'POST', { id: id });
        qvcToast('行为已删除', 'ok');
        qvcLoadBehaviors();
    } catch (e) {
        qvcToast('删除失败: ' + e.message, 'error');
    }
}

// ==================== 多智能体 ====================
async function qvcLoadAgents() {
    try {
        var data = await qvcApi('/api/agents', 'GET');
        var agents = data.agents || data || [];
        var el = document.getElementById('qvc-agents-list');
        if (!agents.length) {
            el.innerHTML = '<div class="qvc-empty">暂无智能体</div>';
            return;
        }
        var html = '';
        agents.forEach(function(a) {
            var badges = '';
            badges += '<span class="qvc-badge ' + (a.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (a.enabled ? '启用' : '禁用') + '</span> ';
            if (a.is_default) badges += '<span class="qvc-badge qvc-badge-off">默认</span> ';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(a.name || a.id) + ' ' + badges + '</div>';
            html += '<div class="qvc-list-item-desc">' + qvcEsc(a.description || '') + '</div>';
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcAgentEdit(' + JSON.stringify(a) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            if (!a.is_default) {
                html += '<button class="qvc-btn-sm danger" onclick="qvcAgentDelete(' + JSON.stringify(qvcEsc(a.id)) + ')">' + '__ICON_TRASH__' + ' 删除</button>';
            }
            html += '</div>';
            html += '</div>';
        });
        el.innerHTML = html;
    } catch (e) {
        qvcToast('加载智能体失败: ' + e.message, 'error');
    }
}

async function qvcAgentEdit(agent) {
    var a = agent || {};

    // 加载人格模板
    var templates = {};
    var templateOptions = [];
    try {
        var resp = await qvcApi('/api/templates', 'GET');
        templates = resp.templates || {};
        templateOptions = Object.keys(templates).map(function(name) {
            return { value: name, label: name };
        });
    } catch (e) {
        // 模板加载失败，使用空列表
    }

    var fields = [
        { name: '_template', label: '人格模板（选择后自动填充提示词）', type: 'select', value: '', options: templateOptions },
        { name: 'name', label: '名称', type: 'text', value: a.name || '' },
        { name: 'description', label: '描述', type: 'text', value: a.description || '' },
        { name: 'system_prompt', label: '系统提示词', type: 'textarea', value: a.system_prompt || '' },
        { name: 'model', label: '指定模型（留空使用默认）', type: 'text', value: a.model || '' },
        { name: 'temperature', label: '温度（留空使用默认）', type: 'number', value: a.temperature },
        { name: 'max_tokens', label: '最大 Tokens（留空使用默认）', type: 'number', value: a.max_tokens },
        { name: 'enabled', label: '启用', type: 'checkbox', value: a.enabled !== false }
    ];
    qvcShowModal(agent ? '编辑智能体' : '添加智能体', fields, async function(data) {
        var payload = {
            name: data.name,
            description: data.description,
            system_prompt: data.system_prompt,
            model: data.model,
            temperature: data.temperature,
            max_tokens: data.max_tokens,
            enabled: data.enabled
        };
        if (a.id) payload.id = a.id;
        try {
            await qvcApi('/api/agents', 'POST', payload);
            qvcHideModal();
            qvcToast('智能体已保存', 'ok');
            qvcLoadAgents();
        } catch (e) {
            qvcToast('保存失败: ' + e.message, 'error');
        }
    });

    // 模板选择后自动填充提示词
    var templateSelect = document.querySelector('[data-field="_template"]');
    if (templateSelect) {
        templateSelect.addEventListener('change', function() {
            var name = this.value;
            if (name && templates[name]) {
                var promptEl = document.querySelector('[data-field="system_prompt"]');
                if (promptEl) promptEl.value = templates[name];
            }
        });
    }
}

async function qvcAgentDelete(id) {
    if (!confirm('确定删除此智能体？')) return;
    try {
        await qvcApi('/api/agents/delete', 'POST', { id: id });
        qvcToast('智能体已删除', 'ok');
        qvcLoadAgents();
    } catch (e) {
        qvcToast('删除失败: ' + e.message, 'error');
    }
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
            badges += '<span class="qvc-badge ' + (e.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (e.enabled ? '启用' : '禁用') + '</span> ';
            if (e.category) badges += '<span class="qvc-badge qvc-badge-off">' + qvcEsc(e.category) + '</span> ';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(e.title || e.id) + ' ' + badges + '</div>';
            var preview = (e.content || '').substring(0, 80);
            html += '<div class="qvc-list-item-desc">' + qvcEsc(preview) + (e.content && e.content.length > 80 ? '...' : '') + '</div>';
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcKbEdit(' + JSON.stringify(e) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            html += '<button class="qvc-btn-sm danger" onclick="qvcKbDelete(' + JSON.stringify(qvcEsc(e.id)) + ')">' + '__ICON_TRASH__' + ' 删除</button>';
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
    if (!confirm('确定删除此知识条目？')) return;
    try {
        await qvcApi('/api/knowledge/delete', 'POST', { id: id });
        qvcToast('知识条目已删除', 'ok');
        qvcLoadKnowledge();
    } catch (e) {
        qvcToast('删除失败: ' + e.message, 'error');
    }
}

// ==================== MCP 工具 ====================
async function qvcLoadTools() {
    try {
        var data = await qvcApi('/api/tools', 'GET');
        var tools = data.tools || data || [];
        var el = document.getElementById('qvc-tools-list');
        if (!tools.length) {
            el.innerHTML = '<div class="qvc-empty">暂无工具定义</div>';
            return;
        }
        var html = '';
        tools.forEach(function(t) {
            var badges = '';
            badges += '<span class="qvc-badge ' + (t.enabled ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (t.enabled ? '启用' : '禁用') + '</span> ';
            if (t.endpoint) badges += '<span class="qvc-badge qvc-badge-off">HTTP</span> ';
            html += '<div class="qvc-list-item">';
            html += '<div class="qvc-list-item-info">';
            html += '<div class="qvc-list-item-title">' + qvcEsc(t.name || t.id) + ' ' + badges + '</div>';
            html += '<div class="qvc-list-item-desc">' + qvcEsc(t.description || '') + '</div>';
            html += '</div>';
            html += '<div class="qvc-list-item-actions">';
            html += '<button class="qvc-btn-sm" onclick=\'qvcToolEdit(' + JSON.stringify(t) + ')\'>' + '__ICON_EDIT__' + ' 编辑</button>';
            html += '<button class="qvc-btn-sm danger" onclick="qvcToolDelete(' + JSON.stringify(qvcEsc(t.id)) + ')">' + '__ICON_TRASH__' + ' 删除</button>';
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
    qvcShowModal(tool ? '编辑工具' : '添加工具', fields, async function(data) {
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
            qvcToast('工具已保存', 'ok');
            qvcLoadTools();
        } catch (err) {
            qvcToast('保存失败: ' + err.message, 'error');
        }
    });
}

async function qvcToolDelete(id) {
    if (!confirm('确定删除此工具？')) return;
    try {
        await qvcApi('/api/tools/delete', 'POST', { id: id });
        qvcToast('工具已删除', 'ok');
        qvcLoadTools();
    } catch (e) {
        qvcToast('删除失败: ' + e.message, 'error');
    }
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
            badges += '<span class="qvc-badge ' + (cfg.enable_ai !== false ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (cfg.enable_ai !== false ? 'AI启用' : 'AI关闭') + '</span> ';
            badges += '<span class="qvc-badge ' + (cfg.enable_memory !== false ? 'qvc-badge-ok' : 'qvc-badge-off') + '">' + (cfg.enable_memory !== false ? '记忆' : '无记忆') + '</span> ';
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
    var fields = [
        { name: 'group_name', label: '群名称', type: 'text', value: cfg.group_name || '' },
        { name: 'system_prompt', label: '群提示词', type: 'textarea', value: cfg.system_prompt || '' },
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
        var payload = { id: g.id, config: data };
        try {
            await qvcApi('/api/groups', 'POST', payload);
            qvcHideModal();
            qvcToast('群组配置已保存', 'ok');
            qvcLoadGroups();
        } catch (e) {
            qvcToast('保存失败: ' + e.message, 'error');
        }
    });
}

// ==================== 通用弹窗 ====================
function qvcShowModal(title, fields, callback) {
    document.getElementById('qvc-modal-title').textContent = title;
    var body = document.getElementById('qvc-modal-body');
    var html = '';
    fields.forEach(function(f) {
        if (f.type === 'checkbox-group') {
            html += '<div class="qvc-form-group">';
            html += '<label>' + qvcEsc(f.label) + '</label>';
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
            html += qvcEsc(f.label);
            html += '</label>';
        } else if (f.type === 'textarea') {
            html += '<div class="qvc-form-group">';
            html += '<label>' + qvcEsc(f.label) + '</label>';
            html += '<textarea class="qvc-textarea" data-field="' + qvcEsc(f.name) + '" placeholder="' + qvcEsc(f.placeholder || '') + '">' + qvcEsc(f.value != null ? String(f.value) : '') + '</textarea>';
            html += '</div>';
        } else if (f.type === 'select') {
            html += '<div class="qvc-form-group">';
            html += '<label>' + qvcEsc(f.label) + '</label>';
            html += '<select class="qvc-select" data-field="' + qvcEsc(f.name) + '">';
            (f.options || []).forEach(function(opt) {
                var sel = opt.value === f.value ? ' selected' : '';
                html += '<option value="' + qvcEsc(opt.value) + '"' + sel + '>' + qvcEsc(opt.label) + '</option>';
            });
            html += '</select>';
            html += '</div>';
        } else {
            // text / number
            html += '<div class="qvc-form-group">';
            html += '<label>' + qvcEsc(f.label) + '</label>';
            html += '<input type="' + f.type + '" step="any" class="qvc-input" data-field="' + qvcEsc(f.name) + '" value="' + qvcEsc(f.value != null ? String(f.value) : '') + '" placeholder="' + qvcEsc(f.placeholder || '') + '">';
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
        } else {
            data[f.name] = document.querySelector('[data-field="' + f.name + '"]').value;
        }
    });
    if (_qvcModalCallback) {
        _qvcModalCallback(data);
    }
}

// ==================== 重置 ====================
async function qvcResetAll() {
    if (!confirm('确定清除所有 QvQChat 数据？此操作不可恢复！\n\n包括：全部配置、模型、行为、智能体、知识库、MCP工具、记忆、会话历史。\n\n清除后请刷新页面并重启模块。')) return;
    try {
        var resp = await qvcApi('/api/reset', 'POST');
        qvcToast(resp.msg || '已清除所有数据', 'ok');
        // 重新加载概览
        setTimeout(function() { location.reload(); }, 2000);
    } catch (e) {
        qvcToast('重置失败: ' + e.message, 'error');
    }
}

// ==================== 初始化 ====================
function loadQvQChatView() {
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
