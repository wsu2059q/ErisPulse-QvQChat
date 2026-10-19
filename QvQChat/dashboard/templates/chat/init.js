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
    startChatSync();
    var settingsBtn = el("qvq-chat-settings");
    if (settingsBtn) settingsBtn.onclick = openSessionSettings;
    var shareBtn = el("qvq-chat-share");
    if (shareBtn) shareBtn.onclick = openShareModal;
    el("qvq-modal-close").onclick = closeModal;
    el("qvq-modal-mask").onclick = closeModal;
    document.addEventListener("click", function () { closeAllMenus(); });
    enhanceSelects();

    var activeNav = el("qvq-nav").querySelector(".qvq-nav-btn.active");
    if (activeNav) switchTab(activeNav.getAttribute("data-tab"));
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && el("qvq-modal").style.display !== "none") closeModal();
    });
    el("qvq-model-add").onclick = function () { openModelModal(null); };
    el("qvq-persona-add").onclick = function () { openPersonaModal(null); };
    el("qvq-skill-add").onclick = function () { openSkillModal(null); };
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
        var chain = Promise.resolve();
        skills.forEach(function (sk) {
          if (!sk || !sk.name) return;
          chain = chain.then(function () {
            return api("/api/qvq/skills/save", "POST", { name: sk.name, description: sk.description || "", body: sk.body || "" });
          });
        });
        chain.then(function () {
          toast(t("saved"));
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
        var chain = Promise.resolve();
        names.forEach(function (name) {
          chain = chain.then(function () {
            return api("/api/qvq/mcp/connect", "POST", { name: name });
          });
        });
        chain.then(function () { loadMcp(); });
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
        api("/api/qvq/import", "POST", { data: data }).then(function (r) {
          toast(r && r.ok ? t("saved") + ": " + (r.applied || []).join(", ") : ((r && r.error) || "error"), !(r && r.ok));
        });
      };
      reader.readAsText(file);
      this.value = "";
    };
    renderChat();
    loadOverview();
  }

  window.loadQvQChatView = function () {
    resolveToken().then(function (tk) {
      if (tk) {
        activeToken = tk;
        hideLogin();
        initApp();
      } else {
        showLogin();
      }
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
  window.loadQvQChatView();
})();
