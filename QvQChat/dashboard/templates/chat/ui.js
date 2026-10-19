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
  var currentMemoryScope = "";
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


  function openModal(title, bodyHtml) {
    el("qvq-modal-title").textContent = title;
    el("qvq-modal-body").innerHTML = bodyHtml;
    el("qvq-modal").style.display = "flex";
  }
  function closeModal() {
    el("qvq-modal").style.display = "none";
    el("qvq-modal-body").innerHTML = "";
  }


  var DD_CHECK = "<svg class='qvq-dd-check' viewBox='0 0 24 24'><path d='M5 12l5 5 9-10'/></svg>";

  function closeAllMenus() {
    document.querySelectorAll(".qvq-dd-menu.open").forEach(function (m) { m.classList.remove("open"); });
    document.querySelectorAll(".qvq-dd-btn.open").forEach(function (b) { b.classList.remove("open"); });
  }

  function enhanceSelects(root) {
    (root || document).querySelectorAll("select.qvq-select").forEach(function (sel) {
      if (sel.getAttribute("data-qvq-dd")) return;
      sel.setAttribute("data-qvq-dd", "1");
      var wrap = document.createElement("span");
      wrap.className = "qvq-dd-wrap";
      try {
        var mw = window.getComputedStyle(sel).maxWidth;
        if (mw && mw !== "none") wrap.style.maxWidth = mw;
      } catch (e) {}
      if (sel.parentNode) sel.parentNode.insertBefore(wrap, sel);
      else return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "qvq-dd-btn";
      var label = document.createElement("span");
      label.className = "qvq-dd-label";
      var chev = document.createElement("i");
      chev.className = "qvq-dd-chev";
      btn.appendChild(label);
      btn.appendChild(chev);
      var menu = document.createElement("span");
      menu.className = "qvq-dd-menu";
      wrap.appendChild(btn);
      wrap.appendChild(menu);
      wrap.appendChild(sel);
      function renderMenu() {
        var cur = sel.value;
        var opts = Array.prototype.slice.call(sel.options || []).map(function (o) {
          return '<span class="qvq-dd-opt' + (o.value === cur ? " sel" : "") + (o.disabled ? " dis" : "") + '" data-v="' + esc(o.value) + '">' +
            "<span>" + esc(o.textContent) + "</span>" + (o.value === cur ? DD_CHECK : "") + "</span>";
        }).join("");
        menu.innerHTML = opts;
        label.textContent = (sel.selectedOptions && sel.selectedOptions[0] && sel.selectedOptions[0].textContent) || cur || " ";
      }
      function close() { menu.classList.remove("open"); btn.classList.remove("open"); }
      btn.onclick = function (e) {
        e.stopPropagation();
        var willOpen = !menu.classList.contains("open");
        closeAllMenus();
        if (willOpen) {
          renderMenu();
          var r = btn.getBoundingClientRect();
          menu.classList.toggle("up", r.bottom + 280 > window.innerHeight && r.top > 300);
          menu.classList.add("open");
          btn.classList.add("open");
        }
      };
      menu.onclick = function (e) {
        var opt = e.target.closest(".qvq-dd-opt");
        if (!opt || opt.classList.contains("dis")) return;
        sel.value = opt.getAttribute("data-v");
        sel.dispatchEvent(new Event("change"));
        renderMenu();
        close();
        e.stopPropagation();
      };
      sel.addEventListener("change", renderMenu);
      if (window.MutationObserver) {
        new MutationObserver(function () { renderMenu(); }).observe(sel, { childList: true, attributes: true, subtree: true });
      }
      renderMenu();
    });
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
    chat: loadChatMeta,
    models: loadModels,
    personas: loadPersonas,
    skills: loadSkills,
    tools: loadTools,
    extensions: loadExtensions,
    mcp: loadMcp,
    tasks: loadTasks,
    memory: loadMemoryScopes,
    sessions: loadSessions,
    audit: loadAudit,
    settings: loadSettings
  };

