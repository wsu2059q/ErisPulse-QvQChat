/* 基础组件：i18n 应用、模态框、下拉/确认组件 */
  var chatHistory = [];
  var chatSession = (function () {
    try { return localStorage.getItem("qvq_chat_session") || "dashboard:private:web"; } catch (e) { return "dashboard:private:web"; }
  })();
  var chatPersona = (function () {
    try { return localStorage.getItem("qvq_chat_persona") || ""; } catch (e) { return ""; }
  })();
  var chatDensity = (function () {
    try { return localStorage.getItem("qvq_chat_density") || "detail"; } catch (e) { return "detail"; }
  })();
  var chatAtts = [];
  var chatMeta = { sessions: [], personas: [] };
  var chatBusy = false;
  var activeLive = null;

  var chatEpoch = 0;

  var busySession = null;
  function setSessionBusy(session, busy) {
    if (busy) busySession = session;
    else if (busySession === session) busySession = null;
    chatBusy = busySession === chatSession;
    setSendStopping(chatBusy);
  }
  var chatModel = (function () {
    try { return localStorage.getItem("qvq_chat_model") || ""; } catch (e) { return ""; }
  })();
  var chatEffort = (function () {
    try { return localStorage.getItem("qvq_chat_effort") || ""; } catch (e) { return ""; }
  })();
  var chatMentions = { skills: [], mcp: [] };

  var chatQueues = {};
  var chatSyncTimer = null;
  var modelPresets = [];
  var currentCategory = "";

  function applyI18n(root) {
    (root || el("qvq-app")).querySelectorAll("[data-i18n]").forEach(function (node) {
      node.textContent = t(node.getAttribute("data-i18n"));
    });
    (root || el("qvq-app")).querySelectorAll("[data-i18n-ph]").forEach(function (node) {
      node.setAttribute("placeholder", t(node.getAttribute("data-i18n-ph")));
    });
    (root || el("qvq-app")).querySelectorAll("[data-i18n-title]").forEach(function (node) {
      node.setAttribute("title", t(node.getAttribute("data-i18n-title")));
    });
  }


  var modalReturnFocus = null;

  function tryFocus(node) {
    try { node.focus(); } catch (e) {}
  }

  function openModal(title, bodyHtml) {
    el("qvq-modal-title").textContent = title;
    el("qvq-modal-body").innerHTML = bodyHtml;
    el("qvq-modal").style.display = "flex";
    // F3 焦点管理：记住触发元素并把焦点移入模态（Tab 圈禁在 init.js 全局处理）
    modalReturnFocus = document.activeElement;
    var first = el("qvq-modal-body").querySelector("input, textarea, select, button");
    if (first) tryFocus(first);
  }
  function closeModal() {
    el("qvq-modal").style.display = "none";
    el("qvq-modal-body").innerHTML = "";
    // 焦点返还触发元素，键盘/读屏用户不会"失焦"
    if (modalReturnFocus && modalReturnFocus.focus) tryFocus(modalReturnFocus);
    modalReturnFocus = null;
  }


  var DD_CHECK = "<svg class='qvq-dd-check' viewBox='0 0 24 24'><path d='M5 12l5 5 9-10'/></svg>";

  function closeAllMenus() {
    document.querySelectorAll(".qvq-dd-menu.open").forEach(function (m) { m.classList.remove("open"); });
    document.querySelectorAll(".qvq-dd-btn.open").forEach(function (b) { b.classList.remove("open"); });
  }

  // 浮层挂 body：滚动/缩放时关闭，避免卡片内滚动条把菜单"顶开"
  window.addEventListener("scroll", closeAllMenus, true);
  window.addEventListener("resize", closeAllMenus);

  function enhanceSelects(root) {
    // F3 无障碍：改用原生 <select>（.qvq-select 已有完整样式）——键盘方向键/字母定位/
    // Esc 与移动端系统选择器全部免费获得；旧自绘浮层不再启用（代码已移除）
    void root;
  }


  function confirmDialog(message) {
    return new Promise(function (resolve) {
      openModal(t("confirm_title"),
        "<div class='qvq-confirm-text'>" + esc(message) + "</div>" +
        "<div class='qvq-actions'><button class='qvq-btn' data-cf-ok>" + esc(t("confirm_yes")) + "</button>" +
        "<button class='qvq-btn ghost' data-cf-no>" + esc(t("cancel")) + "</button></div>");
      var body = el("qvq-modal-body");
      body.querySelector("[data-cf-ok]").onclick = function () { closeModal(); resolve(true); };
      body.querySelector("[data-cf-no]").onclick = function () { closeModal(); resolve(false); };
      // F3 破坏性确认默认落在"取消"：Enter 不会误触确定
      tryFocus(body.querySelector("[data-cf-no]"));
    });
  }

  (function watchSelects() {
    if (!window.MutationObserver) return;
    var timer = null;
    new MutationObserver(function () {
      if (timer) return;
      timer = setTimeout(function () {
        timer = null;
        try { enhanceSelects(); } catch (e) {}
      }, 80);
    }).observe(document.body, { childList: true, subtree: true });
  })();

  var loaders = {
    overview: loadOverview,
    orchestrate: loadOrchestrate,
    chat: loadChatMeta,
    models: loadModels,
    personas: loadPersonas,
    skills: loadSkills,
    tools: loadTools,
    extensions: loadExtensions,
    mcp: loadMcp,
    tasks: loadTasks,
    memory: loadMemoryScopes,
    knowledge: loadKnowledge,
    sessions: loadSessions,
    audit: loadAudit,
    settings: loadSettings
  };

