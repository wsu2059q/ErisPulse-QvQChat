/* 启动：登录与 initApp 装配 */
  function initApp() {
    if (window.__qvq_inited__) return;
    window.__qvq_inited__ = true;
    applyI18n();

    var chatInput = el("qvq-chat-input");
    el("qvq-chat-send").onclick = function () {
      if (chatBusy) { cancelChat(); return; }
      sendChat();
    };
    chatInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChat();
      }
    });
    chatInput.addEventListener("input", function () {
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
    });
    chatInput.addEventListener("paste", function (e) {
      try {
        var items = (e.clipboardData && e.clipboardData.items) || [];
        var files = [];
        for (var i = 0; i < items.length; i++) {
          if (items[i].kind === "file") {
            var f = items[i].getAsFile();
            if (f && /^image\//.test(f.type)) files.push(f);
          }
        }
        if (files.length) {
          e.preventDefault();
          handleFiles(files);
          toast(t("chat_pasted") + " " + files.length);
        }
      } catch (err) {}
    });
    el("qvq-chat-attach-btn").onclick = function () { el("qvq-chat-file").click(); };
    el("qvq-chat-box").addEventListener("scroll", function () {
      if (el("qvq-chat-box").scrollTop < 60) loadOlderMessages();
    });
    el("qvq-chat-file").onchange = function () {
      handleFiles(this.files);
      this.value = "";
    };
    var newBtn = el("qvq-chat-new");
    if (newBtn) newBtn.onclick = function () { newChat(); };
    el("qvq-chat-persona").onchange = function () {
      chatPersona = this.value;
      try {
        if (chatPersona) localStorage.setItem("qvq_chat_persona", chatPersona);
        else localStorage.removeItem("qvq_chat_persona");
      } catch (e) {}
    };
    var densitySel = el("qvq-chat-density");
    if (densitySel) {
      densitySel.value = chatDensity;
      densitySel.onchange = function () {
        chatDensity = this.value;
        try { localStorage.setItem("qvq_chat_density", chatDensity); } catch (e) {}
        renderChat();
      };
    }
    var mmBtn = el("qvq-chat-mm");
    if (mmBtn) mmBtn.onclick = function (e) { e.stopPropagation(); toggleMmMenu(); };
    var mentionBtn = el("qvq-chat-mention");
    if (mentionBtn) mentionBtn.onclick = function (e) { e.stopPropagation(); toggleMentionMenu(); };
    var settingsBtn = el("qvq-chat-settings");
    if (settingsBtn) settingsBtn.onclick = openSessionSettings;
    var shareBtn = el("qvq-chat-share");
    if (shareBtn) shareBtn.onclick = openShareModal;
    el("qvq-modal-close").onclick = closeModal;
    el("qvq-modal-mask").onclick = closeModal;
    document.addEventListener("click", function () { closeAllMenus(); });
    enhanceSelects();

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && el("qvq-modal").style.display !== "none") closeModal();
// 焦点圈禁：模态打开时 Tab 循环留在模态内
      if (e.key === "Tab" && el("qvq-modal").style.display !== "none") {
        var focusables = el("qvq-modal").querySelectorAll(
          "button, input, select, textarea, [tabindex]:not([tabindex='-1'])"
        );
        if (!focusables.length) return;
        var first = focusables[0];
        var last = focusables[focusables.length - 1];
        var active = document.activeElement;
        if (e.shiftKey && (active === first || !el("qvq-modal").contains(active))) {
          e.preventDefault();
          tryFocus(last);
        } else if (!e.shiftKey && (active === last || !el("qvq-modal").contains(active))) {
          e.preventDefault();
          tryFocus(first);
        }
      }
    });
    el("qvq-model-add").onclick = function () { openModelModal(null); };
    el("qvq-persona-add").onclick = function () { openPersonaModal(null); };
    el("qvq-skill-add").onclick = function () { openSkillModal(null); };
    el("qvq-kb-add").onclick = function () { openKnowledgeModal(); };
    el("qvq-kb-export").onclick = function () {
      api("/api/qvq/kb/export").then(function (data) {
        var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "qvqchat-kb-" + new Date().toISOString().slice(0, 10) + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
      });
    };
    el("qvq-kb-import").onclick = function () { el("qvq-kb-file").click(); };
    el("qvq-kb-file").onchange = function () {
      var file = this.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var data;
        try { data = JSON.parse(reader.result); } catch (e) { toast("invalid json", true); return; }
        api("/api/qvq/kb/import", "POST", { entries: (data && data.entries) || [] }).then(function (r) {
          toast(t("saved") + " × " + ((r && r.added) || 0));
          loadKnowledge();
        });
      };
      reader.readAsText(file);
      this.value = "";
    };
    el("qvq-mcp-add").onclick = function () { openMcpModal(null); };
    el("qvq-skill-export").onclick = function () {
      api("/api/qvq/skills/export").then(function (data) {
        var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "qvqchat-skills-" + new Date().toISOString().slice(0, 10) + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
      });
    };
    el("qvq-skill-import").onclick = function () { el("qvq-skill-file").click(); };
    el("qvq-skill-file").onchange = function () {
      var file = this.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var data;
        try { data = JSON.parse(reader.result); } catch (e) { toast("invalid json", true); return; }
        var skills = (data && data.skills) || [];
        if (!skills.length) {
          toast(t("skills_empty"), true);
          return;
        }
        var ok = 0, fail = 0;
        var chain = Promise.resolve();
        skills.forEach(function (sk) {
          if (!sk || !sk.name) return;
          chain = chain.then(function () {
            return api("/api/qvq/skills/save", "POST", { name: sk.name, description: sk.description || "", body: sk.body || "" }).then(function (r) {
              if (r && r.ok) ok++; else fail++;
            });
          });
        });
        chain.then(function () {
          toast(t("batch_result").replace("{ok}", ok).replace("{fail}", fail), fail > 0);
          loadSkills();
        });
      };
      reader.readAsText(file);
      this.value = "";
    };
    el("qvq-tools-refresh").onclick = function () {
      api("/api/qvq/tools/refresh", "POST", {}).then(function (data) {
        var info = (data && data.info) || {};
        toast("eco: " + (info.modules || 0) + " → " + (info.tools || 0));
        loadTools();
      });
    };
    el("qvq-settings-save").onclick = saveSettings;
    el("qvq-mcp-connect-all").onclick = function () {
      api("/api/qvq/mcp").then(function (data) {
        var names = ((data && data.servers) || []).map(function (s) { return s.name; });
        var ok = 0, fail = 0;
        var chain = Promise.resolve();
        names.forEach(function (name) {
          chain = chain.then(function () {
            return api("/api/qvq/mcp/connect", "POST", { name: name }).then(function (r) {
              if (r && r.ok) ok++; else fail++;
            });
          });
        });
        chain.then(function () {
          toast(t("batch_result").replace("{ok}", ok).replace("{fail}", fail), fail > 0);
          loadMcp();
        });
      });
    };
    el("qvq-backup-export").onclick = function () {
      api("/api/qvq/export").then(function (data) {
        var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "qvqchat-backup-" + new Date().toISOString().slice(0, 10) + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
      });
    };
    el("qvq-backup-import").onclick = function () { el("qvq-backup-file").click(); };
    el("qvq-backup-file").onchange = function () {
      var file = this.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var data;
        try { data = JSON.parse(reader.result); } catch (e) { toast("invalid json", true); return; }
        // 导入是破坏性操作
        var sections = ["providers", "chain", "personas", "tasks", "memory", "mcp", "skills", "config", "models"].filter(function (k) { return data && data[k]; });
        confirmDialog(t("backup_import_confirm").replace("{sections}", sections.join(", ") || "-")).then(function (yes) {
          if (!yes) return;
          api("/api/qvq/import", "POST", { data: data }).then(function (r) {
            toast(r && r.ok ? t("saved") + ": " + (r.applied || []).join(", ") : ((r && r.error) || "error"), !(r && r.ok));
          });
        });
      };
      reader.readAsText(file);
      this.value = "";
    };
  }

  // 数据引导：鉴权就绪后才拉取/触发加载
  function bootData() {
    if (window.__qvq_booted__) return;
    window.__qvq_booted__ = true;
    startChatSync();
    var activeNav = el("qvq-nav").querySelector(".qvq-nav-btn.active");
    if (activeNav) switchTab(activeNav.getAttribute("data-tab"));
    renderChat();
    loadOverview();
  }

  // iOS 软键盘不改变 100vh/100dvh：按 visualViewport 实际高度收缩应用容器
  (function fitAppToViewport() {
    var vv = window.visualViewport;
    var app = el("qvq-app");
    if (!vv || !app) return;
    var pending = false;
    function fit() {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        app.style.height = Math.round(vv.height) + "px";
      });
    }
    vv.addEventListener("resize", fit);
    fit();
  })();

  window.loadQvQChatView = function () {
    initApp();
    var bar = el("qvq-bootbar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "qvq-bootbar";
      document.body.appendChild(bar);
    }
    bar.classList.add("on");
    resolveToken().then(function (tk) {
      if (tk) {
        activeToken = tk;
        hideLogin();
        bootData();
      } else {
        showLogin();
      }
      bar.classList.remove("on");
      if (window.__qvqBootDone__) window.__qvqBootDone__();
    });
  };

  var loginBtn = el("qvq-login-btn");
  var loginInput = el("qvq-login-token");
  if (loginBtn) loginBtn.onclick = tryLogin;
  if (loginInput) {
    loginInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") tryLogin();
    });
  }
  // ===== 玻璃拟态外观（透感方案）：背景图/透明度/磨砂，localStorage 持久化 =====
  var APPEAR_KEY = "qvq_appearance";
  var appearState = { url: "", alpha: "mid", blur: "on", on: false };

  function appearLoad() {
    try {
      var raw = localStorage.getItem(APPEAR_KEY);
      if (raw) {
        var data = JSON.parse(raw);
        if (data && typeof data === "object") {
          appearState.url = String(data.url || "");
          appearState.alpha = ["low", "mid", "high"].indexOf(data.alpha) >= 0 ? data.alpha : "mid";
          appearState.blur = data.blur === "off" ? "off" : "on";
          appearState.on = !!data.on;
        }
      }
    } catch (e) {}
  }

  function appearSave() {
    try { localStorage.setItem(APPEAR_KEY, JSON.stringify(appearState)); } catch (e) {}
  }

  function appearApply() {
    var body = document.body;
    if (!appearState.on) {
      body.classList.remove("qvq-glass-on", "qvq-glass-low", "qvq-glass-mid", "qvq-glass-high");
      body.style.removeProperty("--qvq-glass-image");
      return;
    }
    body.classList.add("qvq-glass-on", "qvq-glass-" + appearState.alpha);
    body.classList.remove(appearState.alpha === "low" ? "qvq-glass-mid" : "qvq-glass-low");
    body.classList.remove(appearState.alpha === "high" ? "qvq-glass-mid" : "qvq-glass-high");
    body.style.setProperty("--qvq-glass-image", appearState.url ? 'url("' + appearState.url + '")' : "none");
    body.style.setProperty("--qvq-glass-blur", appearState.blur === "off" ? "0px" : "14px");
  }

  function appearSyncPanel() {
    var panel = document.getElementById("qvq-appear-panel");
    if (!panel) return;
    panel.querySelector("#qvq-appear-url").value = appearState.url;
    panel.querySelectorAll("[data-alpha]").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-alpha") === appearState.alpha);
    });
    panel.querySelectorAll("[data-blur]").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-blur") === appearState.blur);
    });
  }

  function appearBind() {
    var fab = document.getElementById("qvq-appear-fab");
    var panel = document.getElementById("qvq-appear-panel");
    if (!fab || !panel || fab.dataset.bound) return;
    fab.dataset.bound = "1";
    fab.onclick = function () {
      panel.classList.toggle("open");
      appearSyncPanel();
    };
    panel.querySelector("#qvq-appear-url").onchange = function () {
      appearState.url = this.value.trim();
      appearState.on = !!appearState.url;
      appearSave();
      appearApply();
    };
    var fileInput = panel.querySelector("#qvq-appear-file");
    panel.querySelector("#qvq-appear-file-btn").onclick = function () { fileInput.click(); };
    fileInput.onchange = function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) return;
      // 压缩到最长边 1600px 的 JPEG dataURL，避免 localStorage 爆容量
      var reader = new FileReader();
      reader.onload = function () {
        var img = new Image();
        img.onload = function () {
          var scale = Math.min(1, 1600 / Math.max(img.width, img.height));
          var canvas = document.createElement("canvas");
          canvas.width = Math.round(img.width * scale);
          canvas.height = Math.round(img.height * scale);
          canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
          try {
            appearState.url = canvas.toDataURL("image/jpeg", 0.82);
            appearState.on = true;
            appearSave();
            appearApply();
            appearSyncPanel();
          } catch (e) {
            alert("图片过大，无法保存");
          }
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
      fileInput.value = "";
    };
    panel.querySelector("#qvq-appear-clear").onclick = function () {
      appearState.url = "";
      appearState.on = false;
      appearSave();
      appearApply();
      appearSyncPanel();
    };
    panel.querySelectorAll("[data-alpha]").forEach(function (b) {
      b.onclick = function () {
        appearState.alpha = b.getAttribute("data-alpha");
        appearState.on = true;
        appearSave();
        appearApply();
        appearSyncPanel();
      };
    });
    panel.querySelectorAll("[data-blur]").forEach(function (b) {
      b.onclick = function () {
        appearState.blur = b.getAttribute("data-blur");
        appearSave();
        appearApply();
        appearSyncPanel();
      };
    });
  }

  appearLoad();
  appearApply();
  appearBind();
  window.loadQvQChatView();
})();
