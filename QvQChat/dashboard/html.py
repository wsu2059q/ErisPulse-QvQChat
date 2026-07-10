"""Dashboard HTML 常量"""

HTML = """
<div class="qvc-wrap">
    <div style="display:flex;justify-content:space-between;align-items:center">
        <h1 class="page-title" style="margin:0">QvQChat 管理面板</h1>
        <div style="display:flex;gap:8px">
            <button class="qvc-btn-sm" onclick="qvcExport('desensitize')">脱敏导出</button>
            <button class="qvc-btn-sm" onclick="qvcExport('migrate')">迁移导出</button>
            <button class="qvc-btn-sm" onclick="qvcImport()">导入</button>
            <button class="qvc-btn-sm danger" onclick="qvcResetAll()">重置全部</button>
        </div>
    </div>

    <!-- 标签栏 -->
    <div class="qvc-tabs">
        <div class="qvc-tab active" data-tab="overview" onclick="qvcTab('overview')">
            __ICON_OVERVIEW__ <span>概览</span>
        </div>
        <div class="qvc-tab" data-tab="basic" onclick="qvcTab('basic')">
            __ICON_SETTINGS__ <span>基础设置</span>
        </div>
        <div class="qvc-tab" data-tab="models" onclick="qvcTab('models')">
            __ICON_MODELS__ <span>模型管理</span>
        </div>
        <div class="qvc-tab" data-tab="behaviors" onclick="qvcTab('behaviors')">
            __ICON_BEHAVIORS__ <span>行为管理</span>
        </div>
        <div class="qvc-tab" data-tab="agents" onclick="qvcTab('agents')">
            __ICON_AGENTS__ <span>多智能体</span>
        </div>
        <div class="qvc-tab" data-tab="knowledge" onclick="qvcTab('knowledge')">
            __ICON_BOOK__ <span>知识库</span>
        </div>
        <div class="qvc-tab" data-tab="tools" onclick="qvcTab('tools')">
            __ICON_TOOL__ <span>MCP工具</span>
        </div>
        <div class="qvc-tab" data-tab="stickers" onclick="qvcTab('stickers')">
            __ICON_BOOK__ <span>表情包</span>
        </div>
        <div class="qvc-tab" data-tab="groups" onclick="qvcTab('groups')">
            __ICON_GROUP__ <span>群组管理</span>
        </div>
    </div>

    <!-- 概览面板 -->
    <div class="qvc-panel active" id="qvc-panel-overview">
        <div class="qvc-section-title">运行状态</div>
        <div class="qvc-stat-grid" id="qvc-overview-stats"></div>

        <div class="qvc-section-title">运行统计</div>
        <div class="qvc-stat-grid" id="qvc-overview-runtime"></div>

        <div class="qvc-section-title">AI 子系统状态</div>
        <div id="qvc-overview-ai"></div>

        <div class="qvc-section-title">功能开关</div>
        <div id="qvc-overview-features"></div>
    </div>

    <!-- 基础设置面板 -->
    <div class="qvc-panel" id="qvc-panel-basic">
        <div id="qvc-basic-form">
            <div class="qvc-empty">正在加载配置...</div>
        </div>
        <div style="margin-top:16px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcSaveBasic()">
                __ICON_SAVE__ 保存配置
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

    <!-- 多智能体面板 -->
    <div class="qvc-panel" id="qvc-panel-agents">
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcAgentEdit(null)">
                __ICON_PLUS__ 添加智能体
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
        <div style="margin-bottom:12px;text-align:right">
            <button class="qvc-btn-sm primary" onclick="qvcStickerUpload()">
                __ICON_PLUS__ 上传表情包
            </button>
            <button class="qvc-btn-sm" onclick="qvcStickerAddUrl()">通过 URL 添加</button>
        </div>
        <div id="qvc-stickers-list" class="qvc-sticker-grid">
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
            <button class="qvc-btn-sm primary" onclick="qvcModalSave()">__ICON_SAVE__ 保存</button>
        </div>
    </div>
</div>
"""
