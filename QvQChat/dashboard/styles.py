"""Dashboard CSS 样式常量"""

STYLES = r"""
/* ==================== 标签栏 ==================== */
.qvc-tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid var(--bd);
    padding: 0 0 0 4px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}

.qvc-tab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    font-size: 13px;
    color: var(--tx-s);
    cursor: pointer;
    border: 1px solid transparent;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    background: transparent;
    transition: all .15s;
    user-select: none;
}

.qvc-tab:hover {
    color: var(--tx-p);
    background: var(--bg-s);
}

.qvc-tab.active {
    color: var(--accent);
    background: var(--bg-t);
    border-color: var(--bd);
}

.qvc-tab svg {
    width: 16px;
    height: 16px;
    flex-shrink: 0;
}

/* ==================== 面板 ==================== */
.qvc-panel {
    display: none;
    animation: qvc-fade .15s ease;
}

.qvc-panel.active {
    display: block;
}

@keyframes qvc-fade {
    from { opacity: 0; }
    to { opacity: 1; }
}

/* ==================== 区块标题 ==================== */
.qvc-section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--tx-p);
    margin: 20px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--bd);
}

.qvc-section-title:first-child {
    margin-top: 0;
}

/* ==================== 表单 ==================== */
.qvc-form-row {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}

.qvc-form-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 12px;
    flex: 1;
    min-width: 200px;
}

.qvc-form-group > label {
    font-size: 12px;
    color: var(--tx-s);
    font-weight: 500;
}

.qvc-input,
.qvc-textarea,
.qvc-select {
    width: 100%;
    padding: 8px 10px;
    font-size: 13px;
    color: var(--tx-p);
    background: var(--bg-s);
    border: 1px solid var(--bd);
    border-radius: 6px;
    box-sizing: border-box;
    transition: border-color .15s;
    font-family: inherit;
}

.qvc-input:focus,
.qvc-textarea:focus,
.qvc-select:focus {
    outline: none;
    border-color: var(--accent);
}

.qvc-textarea {
    resize: vertical;
    min-height: 80px;
    line-height: 1.5;
}

.qvc-select {
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    padding-right: 30px;
}

/* ==================== 复选框行 ==================== */
.qvc-checkbox-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--tx-p);
    cursor: pointer;
    user-select: none;
}

.qvc-checkbox-row input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
    accent-color: var(--accent);
}

/* ==================== 列表项 ==================== */
.qvc-list-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    background: var(--bg-t);
    border: 1px solid var(--bd);
    border-radius: 8px;
    margin-bottom: 8px;
    transition: border-color .15s;
}

.qvc-list-item:hover {
    border-color: var(--accent);
}

.qvc-list-item-info {
    flex: 1;
    min-width: 0;
}

.qvc-list-item-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--tx-p);
    display: flex;
    align-items: center;
    gap: 8px;
}

.qvc-list-item-desc {
    font-size: 12px;
    color: var(--tx-s);
    margin-top: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.qvc-list-item-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
    margin-left: 12px;
}

/* ==================== 小按钮 ==================== */
.qvc-btn-sm {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 6px 10px;
    font-size: 12px;
    color: var(--tx-s);
    background: var(--bg-s);
    border: 1px solid var(--bd);
    border-radius: 6px;
    cursor: pointer;
    transition: all .15s;
    white-space: nowrap;
}

.qvc-btn-sm:hover {
    color: var(--accent);
    border-color: var(--accent);
}

.qvc-btn-sm svg {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
}

.qvc-btn-sm.danger:hover {
    color: var(--er-c);
    border-color: var(--er-c);
}

.qvc-btn-sm.primary {
    color: #fff;
    background: var(--accent);
    border-color: var(--accent);
}

.qvc-btn-sm.primary:hover {
    opacity: .9;
}

/* ==================== 徽章 ==================== */
.qvc-badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 11px;
    border-radius: 10px;
    font-weight: 500;
}

.qvc-badge-ok {
    color: var(--ok-c);
    background: color-mix(in srgb, var(--ok-c) 15%, transparent);
}

.qvc-badge-off {
    color: var(--tx-t);
    background: var(--bg-s);
}

/* ==================== 空状态 ==================== */
.qvc-empty {
    text-align: center;
    padding: 32px 16px;
    color: var(--tx-t);
    font-size: 13px;
}

/* ==================== 统计卡片 ==================== */
.qvc-stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}

.qvc-stat-card {
    padding: 16px;
    background: var(--bg-t);
    border: 1px solid var(--bd);
    border-radius: 8px;
    text-align: center;
}

.qvc-stat-num {
    font-size: 28px;
    font-weight: 700;
    color: var(--accent);
    line-height: 1.2;
}

.qvc-stat-label {
    font-size: 12px;
    color: var(--tx-s);
    margin-top: 4px;
}

/* ==================== 弹窗 ==================== */
.qvc-modal-bg {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, .5);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    backdrop-filter: blur(2px);
}

.qvc-modal-bg.show {
    display: flex;
}

.qvc-modal {
    background: var(--bg-p);
    border: 1px solid var(--bd);
    border-radius: 10px;
    width: 90%;
    max-width: 560px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, .2);
}

.qvc-modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--bd);
}

.qvc-modal-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--tx-p);
}

/* 修复后的关闭按钮：28x28px，内部 SVG 16x16px，居中 */
.qvc-modal-close {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    padding: 0;
    background: transparent;
    border: none;
    color: var(--tx-s);
    cursor: pointer;
    transition: all .15s;
    flex-shrink: 0;
}

.qvc-modal-close:hover {
    color: var(--tx-p);
    background: var(--bg-s);
}

.qvc-modal-close svg {
    width: 16px;
    height: 16px;
}

.qvc-modal-body {
    padding: 20px;
    overflow-y: auto;
    flex: 1;
}

.qvc-modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 16px 20px;
    border-top: 1px solid var(--bd);
}

/* ==================== Toast 提示 ==================== */
.qvc-toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 13px;
    z-index: 10001;
    animation: qvc-toast-in .2s ease;
    box-shadow: 0 4px 16px rgba(0, 0, 0, .15);
}

@keyframes qvc-toast-in {
    from { opacity: 0; transform: translate(-50%, 10px); }
    to { opacity: 1; transform: translate(-50%, 0); }
}

.qvc-toast-ok {
    color: #fff;
    background: var(--ok-c);
}

.qvc-toast-error {
    color: #fff;
    background: var(--er-c);
}

.qvc-toast-info {
    color: #fff;
    background: var(--accent);
}

/* ==================== 表情包网格 ==================== */
.qvc-sticker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
}

.qvc-sticker-card {
    border: 1px solid var(--bd);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: var(--bg-c);
    position: relative;
    min-height: 180px;
    cursor: default;
}

.qvc-sticker-card.qvc-select-mode {
    cursor: pointer;
}

.qvc-sticker-thumb {
    width: 100%;
    height: 100px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: var(--bg2, #f5f5f5);
}

.qvc-sticker-thumb img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

.qvc-sticker-thumb.qvc-sticker-noimg {
    color: var(--tx-s);
    font-size: 12px;
}

.qvc-sticker-name {
    font-weight: 600;
    font-size: 13px;
    padding: 6px 8px 2px;
    color: var(--tx-c);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.qvc-sticker-desc {
    font-size: 11px;
    color: var(--tx-s);
    padding: 0 8px 6px;
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.qvc-sticker-actions {
    display: flex;
    gap: 4px;
    padding: 4px 8px 8px;
}

.qvc-sticker-actions .qvc-btn-sm {
    flex: 1;
    justify-content: center;
    padding: 4px;
}

.qvc-sticker-check {
    position: absolute;
    top: 4px;
    left: 4px;
    z-index: 2;
    display: none;
}

.qvc-select-mode .qvc-sticker-check {
    display: block;
}

.qvc-sticker-check input {
    width: 16px;
    height: 16px;
    cursor: pointer;
    accent-color: var(--accent);
}
"""
