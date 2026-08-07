"""Dashboard HTML 常量"""

HTML = """
<div class="qvc-wrap">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px">
        <div>
            <h1 class="page-title" id="qvc-page-title">QvQChat</h1>
            <p style="color:var(--tx-s);font-size:13px;margin-bottom:16px" id="qvc-page-desc">智能对话模块 · 管理 AI 模型、行为、智能体、知识库与记忆</p>
        </div>
        <div style="display:flex;gap:8px;flex-shrink:0">
            <button class="qvc-btn-sm" id="qvc-btn-export-desensitize" onclick="qvcExport('desensitize')">脱敏导出</button>
            <button class="qvc-btn-sm" id="qvc-btn-export-migrate" onclick="qvcExport('migrate')">迁移导出</button>
            <button class="qvc-btn-sm" id="qvc-btn-import" onclick="qvcImport()">导入</button>
            <button class="qvc-btn-sm danger" id="qvc-btn-reset" onclick="qvcResetAll()">重置全部</button>
        </div>
    </div>

    <!-- 标签栏 -->
    <div class="qvc-tabs">
        <div class="qvc-tab active" data-tab="overview" onclick="qvcTab('overview')">
            __ICON_OVERVIEW__ <span id="qvc-tab-overview">概览</span>
        </div>
        <div class="qvc-tab" data-tab="basic" onclick="qvcTab('basic')">
            __ICON_SETTINGS__ <span id="qvc-tab-basic">基础设置</span>
        </div>
        <div class="qvc-tab" data-tab="models" onclick="qvcTab('models')">
            __ICON_MODELS__ <span id="qvc-tab-models">模型管理</span>
        </div>
        <div class="qvc-tab" data-tab="behaviors" onclick="qvcTab('behaviors')">
            __ICON_BEHAVIORS__ <span id="qvc-tab-behaviors">行为管理</span>
        </div>
        <div class="qvc-tab" data-tab="pipeline" onclick="qvcTab('pipeline')">
            __ICON_SETTINGS__ <span id="qvc-tab-pipeline">注入管线</span>
        </div>
        <div class="qvc-tab" data-tab="render" onclick="qvcTab('render')">
            __ICON_TOOL__ <span id="qvc-tab-render">渲染能力</span>
        </div>
        <div class="qvc-tab" data-tab="agents" onclick="qvcTab('agents')">
            __ICON_AGENTS__ <span id="qvc-tab-agents">多智能体</span>
        </div>
        <div class="qvc-tab" data-tab="knowledge" onclick="qvcTab('knowledge')">
            __ICON_BOOK__ <span id="qvc-tab-knowledge">知识库</span>
        </div>
        <div class="qvc-tab" data-tab="tools" onclick="qvcTab('tools')">
            __ICON_TOOL__ <span id="qvc-tab-tools">MCP工具</span>
        </div>
        <div class="qvc-tab" data-tab="stickers" onclick="qvcTab('stickers')">
            __ICON_BOOK__ <span id="qvc-tab-stickers">表情包</span>
        </div>
        <div class="qvc-tab" data-tab="memories" onclick="qvcTab('memories')">
            __ICON_GROUP__ <span id="qvc-tab-memories">记忆管理</span>
        </div>
        <div class="qvc-tab" data-tab="sessions" onclick="qvcTab('sessions')">
            __ICON_GROUP__ <span id="qvc-tab-sessions">会话管理</span>
        </div>
        <div class="qvc-tab" data-tab="groups" onclick="qvcTab('groups')">
            __ICON_GROUP__ <span id="qvc-tab-groups">群组管理</span>
        </div>
    </div>

    <!-- 概览面板 -->
    <div class="qvc-panel active" id="qvc-panel-overview">
        <div class="qvc-section-title" id="qvc-ov-title-runtime">运行状态</div>
        <div class="qvc-stat-grid" id="qvc-overview-stats"></div>

        <div class="qvc-section-title" id="qvc-ov-title-stats">运行统计</div>
        <div class="qvc-stat-grid" id="qvc-overview-runtime"></div>

        <div class="qvc-section-title" id="qvc-ov-title-ai">AI 子系统状态</div>
        <div id="qvc-overview-ai"></div>

        <div class="qvc-section-title" id="qvc-ov-title-features">功能开关</div>
        <div id="qvc-overview-features"></div>

        <div class="qvc-section-title" id="qvc-ov-title-human">人类状态</div>
        <div id="qvc-overview-human-state"></div>
    </div>

    <!-- 基础设置面板 -->
    <div class="qvc-panel" id="qvc-panel-basic">
        <div id="qvc-basic-form">
            <div class="qvc-empty">正在加载配置...</div>
        </div>
        <div style="margin-top:16px;text-align:right">
            <button class="qvc-btn-sm primary" id="qvc-btn-save-basic" onclick="qvcSaveBasic()">
                __ICON_SAVE__ <span id="qvc-btn-save-basic-label">保存配置</span>
            </button>
        </div>
    </div>

    <!-- 模型管理面板 -->
    <div class="qvc-panel" id="qvc-panel-models">
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcModelEdit(null)">
                __ICON_PLUS__ 添加模型
            </button>
        </div>
        <div id="qvc-models-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- 行为管理面板 -->
    <div class="qvc-panel" id="qvc-panel-behaviors">
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcBehaviorEdit(null)">
                __ICON_PLUS__ 添加行为
            </button>
        </div>
        <div id="qvc-behaviors-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- 注入管线面板 -->
    <div class="qvc-panel" id="qvc-panel-pipeline">
        <div class="qvc-section-title" id="qvc-pipeline-title">提示词注入器</div>
        <div class="qvc-desc" id="qvc-pipeline-desc">注入器按优先级顺序拼接系统提示词。可开关、调整顺序。</div>
        <div id="qvc-pipeline-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
        <div class="qvc-section-title" style="margin-top:20px" id="qvc-pipeline-time-title">时间叙述设置</div>
        <div class="qvc-form-group">
            <label id="qvc-pipeline-time-prob-label">时间注入概率 (0~1，1=总是注入)</label>
            <input type="range" class="qvc-range" id="qvc-pipeline-time-prob" min="0" max="1" step="0.05" value="0.7"
                oninput="document.getElementById('qvc-pipeline-time-prob-val').textContent=this.value">
            <span class="qvc-slider-val" id="qvc-pipeline-time-prob-val">0.7</span>
        </div>
        <div class="qvc-form-group">
            <label id="qvc-pipeline-time-ttl-label">时间叙述缓存 (秒)</label>
            <input type="number" class="qvc-input" id="qvc-pipeline-time-ttl" value="3600">
        </div>
        <div style="margin-top:16px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcSavePipeline()">__ICON_SAVE__ <span id="qvc-pipeline-save-label">保存</span></button>
        </div>
    </div>

    <!-- 渲染能力面板 -->
    <div class="qvc-panel" id="qvc-panel-render">
        <div class="qvc-section-title">渲染模板</div>
        <div class="qvc-desc">AI 可用 <span style="font-family:monospace">&lt;|render|&gt;</span> 标签渲染模板或自由 HTML 图片。需要已安装 Takumi 模块。</div>
        <div id="qvc-render-status"></div>
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcRenderTemplateEdit(null)">__ICON_PLUS__ 添加模板</button>
        </div>
        <div id="qvc-render-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- 多智能体面板 -->
    <div class="qvc-panel" id="qvc-panel-agents">
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm" onclick="qvcAgentQuickCreate()">__ICON_PLUS__ 从模板创建</button>
            <button class="qvc-btn-sm primary" onclick="qvcAgentEdit(null)">
                __ICON_PLUS__ 自定义智能体
            </button>
        </div>
        <div id="qvc-agents-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- 知识库面板 -->
    <div class="qvc-panel" id="qvc-panel-knowledge">
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcKbEdit(null)">
                __ICON_PLUS__ 添加知识
            </button>
        </div>
        <div id="qvc-knowledge-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- MCP 工具面板 -->
    <div class="qvc-panel" id="qvc-panel-tools">
        <div class="qvc-section-title">MCP 服务器（stdio）</div>
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcMcpServerEdit(null)">
                __ICON_PLUS__ 添加 MCP 服务器
            </button>
            <button class="qvc-btn-sm" onclick="qvcMcpConnectAll()">连接全部</button>
        </div>
        <div id="qvc-mcp-servers-list">
            <div class="qvc-empty">正在加载...</div>
        </div>

        <div class="qvc-section-title" style="margin-top:20px">手动工具定义（HTTP 端点）</div>
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcToolEdit(null)">
                __ICON_PLUS__ 添加工具
            </button>
        </div>
        <div id="qvc-tools-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- 群组管理面板 -->
    <div class="qvc-panel" id="qvc-panel-groups">
        <div id="qvc-groups-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- 表情包面板 -->
    <div class="qvc-panel" id="qvc-panel-stickers">
        <div style="margin-bottom:12px">
            <div style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
                <button class="qvc-btn-sm primary" onclick="qvcStickerUpload()">__ICON_PLUS__ 上传表情包</button>
                <button class="qvc-btn-sm" onclick="qvcStickerUploadBatch()">批量上传</button>
                <button class="qvc-btn-sm" onclick="qvcStickerAddUrl()">通过 URL 添加</button>
                <span style="flex:1"></span>
                <button class="qvc-btn-sm" id="qvc-sticker-select-btn" onclick="qvcStickerToggleSelect()">选择</button>
            </div>
            <div id="qvc-sticker-toolbar" class="qvc-sticker-toolbar" style="display:none">
                <span id="qvc-sticker-selcount" class="qvc-sticker-count" style="display:none"></span>
                <button class="qvc-btn-sm" onclick="qvcStickerSelectAll()">全选</button>
                <button class="qvc-btn-sm" onclick="qvcStickerDeselect()">取消选择</button>
                <button class="qvc-btn-sm" onclick="qvcStickerBatchGenerate()">AI 分析</button>
                <button class="qvc-btn-sm danger" onclick="qvcStickerBatchDelete()">删除</button>
                <button class="qvc-btn-sm" onclick="qvcStickerToggleSelect()" style="margin-left:auto">完成</button>
            </div>
        </div>
        <div id="qvc-stickers-list" class="qvc-sticker-grid">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- 记忆管理面板 -->
    <div class="qvc-panel" id="qvc-panel-memories">
        <div id="qvc-memory-hint" style="margin-bottom:8px"></div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <input type="text" class="qvc-input" id="qvc-memory-search" placeholder="搜索用户/群组 ID..." style="max-width:240px" oninput="qvcFilterMemories()">
            <button class="qvc-btn-sm danger" onclick="qvcClearAllMemories()">清空全部记忆</button>
        </div>
        <div id="qvc-memories-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>

    <!-- 会话管理面板 -->
    <div class="qvc-panel" id="qvc-panel-sessions">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <input type="text" class="qvc-input" id="qvc-session-search" placeholder="搜索会话..." style="max-width:240px" oninput="qvcFilterSessions()">
            <button class="qvc-btn-sm" onclick="qvcLoadSessions()">__ICON_REFRESH__ 刷新</button>
        </div>
        <div id="qvc-sessions-list">
            <div class="qvc-empty">正在加载...</div>
        </div>
    </div>
</div>

<!-- 通用弹窗 -->
<div class="qvc-modal-bg" id="qvc-modal-bg">
    <div class="qvc-modal">
        <div class="qvc-modal-header">
            <span class="qvc-modal-title" id="qvc-modal-title">标题</span>
            <button class="qvc-modal-close" onclick="qvcHideModal()">__ICON_CLOSE__</button>
        </div>
        <div class="qvc-modal-body" id="qvc-modal-body"></div>
        <div class="qvc-modal-footer">
            <button class="qvc-btn-sm" onclick="qvcHideModal()">取消</button>
            <button class="qvc-btn-sm primary" onclick="qvcModalSave()">__ICON_SAVE__ 确定</button>
        </div>
    </div>
</div>
"""
