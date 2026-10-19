/* 导航与侧栏：标签切换、会话列表、发送队列 */
  function switchTab(name) {
    el("qvq-nav").querySelectorAll(".qvq-nav-btn").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-tab") === name);
    });
    el("qvq-app").querySelectorAll(".qvq-tab").forEach(function (section) {
      section.classList.toggle("active", section.getAttribute("data-section") === name);
    });
    if (loaders[name]) loaders[name]();
    var navSessions = el("qvq-nav-sessions");
    if (navSessions) navSessions.classList.toggle("show", name === "chat");
    if (name === "chat") {
      var input = el("qvq-chat-input");
      if (input) input.focus();
    }
    closeDrawer();
  }


  function closeDrawer() {
    var side = el("qvq-side");
    var mask = el("qvq-mask");
    if (side) side.classList.remove("open");
    if (mask) mask.classList.remove("open");
  }

  (function initDrawer() {
    var side = el("qvq-side");
    var mask = el("qvq-mask");
    var burger = el("qvq-burger");
    if (!side || !mask || !burger) return;
    burger.onclick = function () {
      var open = !side.classList.contains("open");
      side.classList.toggle("open", open);
      mask.classList.toggle("open", open);
    };
    mask.onclick = closeDrawer;
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDrawer();
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth > 860) closeDrawer();
    });
  })();

  function loadOverview() {
    var heroEl = el("qvq-hero-title");
    if (heroEl) heroEl.textContent = heroTitle();
    api("/api/qvq/status").then(function (data) {
      var tools = data.tools || {};
      var total = 0;
      Object.keys(tools).forEach(function (k) { total += tools[k] || 0; });
      var mcpCount = (data.mcp || []).length;
      var extCount = (data.extensions || []).length;
      var cards = [
        { cap: t("stat_models"), num: data.models || 0, cls: "hl-red" },
        { cap: t("stat_tools"), num: total, cls: "hl-teal" },
        { cap: t("stat_eco"), num: tools.eco || 0, cls: "" },
        { cap: t("stat_extensions"), num: extCount, cls: "" },
        { cap: t("stat_sessions"), num: data.sessions || 0, cls: "" },
        { cap: t("stat_tasks"), num: data.tasks || 0, cls: "" },
        { cap: t("stat_mcp"), num: mcpCount, cls: "" },
        { cap: t("stat_security"), num: (data.trust_agent ? t("trust_on") : esc(data.security_level || "-")), cls: data.trust_agent ? "hl-red" : "" }
      ];
      el("qvq-stats").innerHTML = cards.map(function (c) {
        return '<div class="qvq-stat ' + c.cls + '"><div class="num">' + esc(c.num) + '</div><div class="cap">' + esc(c.cap) + "</div></div>";
      }).join("");
      var usage = data.usage_today || {};
      var tokens = usage.tokens || 0;
      var limit = usage.limit || 0;
      var heroSub = [];
      if (data.version) heroSub.push("v" + data.version);
      if (data.eco) heroSub.push(t("stat_eco") + " " + (data.eco.modules || 0) + " / " + (data.eco.tools || 0));
      heroSub.push(t("takeovers") + " " + (data.takeovers || 0));
      var sub = el("qvq-hero-sub");
      if (sub) sub.textContent = heroSub.join(" · ");
      var num = el("qvq-hero-tokens");
      if (num) num.textContent = tokens;
      var bar = el("qvq-hero-bar");
      if (bar) bar.style.width = limit ? Math.min(100, (tokens / limit) * 100) + "%" : "0%";
      var lim = el("qvq-hero-limit");
      if (lim) {
        lim.textContent = limit
          ? t("usage_limit") + " " + limit + " · " + Math.min(100, Math.round((tokens / limit) * 100)) + "%"
          : t("hero_no_limit");
      }
    });
    api("/api/qvq/usage").then(function (data) {
      renderUsageChart(data || {}, "qvq-home-chart");
    });
    api("/api/qvq/sessions").then(function (data) {
      var homeSessions = (data && data.sessions) || [];
      renderHomeList("qvq-home-sessions", homeSessions, function (s) {
        return { name: sessionDisplayName(s), badge: s.turns, desc: esc(chatSourceLabel(s.chat_key)) };
      });
      var listBox = el("qvq-home-sessions");
      if (listBox) {
        listBox.querySelectorAll(".qvq-tool-row").forEach(function (row, idx) {
          var item = homeSessions[idx];
          if (!item) return;
          row.style.cursor = "pointer";
          row.onclick = function () {
            switchTab("chat");
            if (item.chat_key !== chatSession) switchChatSession(item.chat_key);
          };
        });
      }
    });
    api("/api/qvq/tasks").then(function (data) {
      renderHomeList("qvq-home-tasks", (data && data.tasks) || [], function (task) {
        return {
          name: task.name || task.id,
          desc: task.next_run ? esc(fmtSmart(task.next_run)) : esc(task.schedule_raw || "-")
        };
      });
    });
  }

  function renderHomeList(boxId, items, map) {
    var box = el(boxId);
    if (!box) return;
    if (!items.length) {
      box.innerHTML = '<div class="qvq-empty">-</div>';
      return;
    }
    box.innerHTML = items.slice(0, 5).map(function (item) {
      var row = map(item);
      var badge = row.badge != null && row.badge !== ""
        ? "<span class='qvq-row-badge' title='" + esc(t("col_turns")) + "'>" + esc(row.badge) + "</span>"
        : "";
      return "<div class='qvq-tool-row'>" + badge + "<span class='qvq-tool-name'><span class='qvq-tool-nm'>" + esc(row.name) + "</span></span>" +
        "<span class='qvq-tool-desc'>" + row.desc + "</span></div>";
    }).join("");
  }

  function contentText(content) {
    if (typeof content === "string") return content;
    if (Array.isArray(content)) {
      return content
        .filter(function (p) { return p && p.type === "text"; })
        .map(function (p) { return p.text || ""; })
        .join("\n");
    }
    return String(content || "");
  }

  function sessionDisplayName(s) {
    return s.name || s.target_id || s.chat_key;
  }

  var chatShowArchived = false;

  var PIN_SVG = "<svg viewBox='0 0 24 24'><path d='M12 17v5M9 3h6l-1 7 3 2v2H7v-2l3-2z'/></svg>";
  var DEL_SVG = "<svg viewBox='0 0 24 24'><path d='M3 6h18M8 6V4h8v2m-9 0v14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6'/></svg>";
  var ARC_SVG = "<svg viewBox='0 0 24 24'><path d='M3 6h18v3H3zM5 9v11h14V9M9 13h6'/></svg>";

  function chatSessionTitle(key) {
    if (key === "dashboard:private:web") return t("chat_default_session");
    var m = /^dashboard:private:web(\d+)$/.exec(key || "");
    if (m) return t("chat_new_name").replace("{n}", m[1]);
    var found = null;
    chatMeta.sessions.forEach(function (s) { if (s.chat_key === key) found = s; });
    return found ? sessionDisplayName(found) : key;
  }

  function sessionRowsHtml(items) {
    return items.slice(0, 40).map(function (s) {
      var active = s.chat_key === chatSession;
      var pinned = !!s.pinned;
      var acts = '<span class="qvq-chat-sacts">' +
        '<button type="button" data-act="pin" data-key="' + esc(s.chat_key) + '" data-on="' + (pinned ? "1" : "0") + '" title="' + esc(t(pinned ? "chat_unpin" : "chat_pin")) + '">' + PIN_SVG + "</button>" +
        '<button type="button" data-act="archive" data-key="' + esc(s.chat_key) + '" data-on="' + (s.archived ? "1" : "0") + '" title="' + esc(t(s.archived ? "chat_unarchive" : "chat_archive")) + '">' + ARC_SVG + "</button>" +
        '<button type="button" data-act="delete" data-key="' + esc(s.chat_key) + '" title="' + esc(t("chat_delete")) + '">' + DEL_SVG + "</button>" +
        "</span>";
      var liveCls = s.live ? " liverun" : "";
      return '<div class="qvq-chat-srow' + (active ? " active" : "") + (pinned ? " pinned" : "") + liveCls + '" data-key="' + esc(s.chat_key) + '">' +
        '<span class="qvq-chat-sname">' + esc(chatSessionTitle(s.chat_key)) + "</span>" +
        '<span class="qvq-chat-stime">' + esc(fmtSmart(s.updated)) + "</span>" + acts + "</div>";
    }).join("");
  }

  function bindSessionRows(box, closeAfter) {
    box.querySelectorAll(".qvq-chat-srow").forEach(function (row) {
      row.onclick = function () {
        switchChatSession(row.getAttribute("data-key"));
        if (closeAfter) closeDrawer();
      };
    });
    box.querySelectorAll(".qvq-chat-sacts button").forEach(function (btn) {
      btn.onclick = function (e) {
        e.stopPropagation();
        var key = btn.getAttribute("data-key");
        var on = btn.getAttribute("data-on") === "1";
        var act = btn.getAttribute("data-act");
        var patch = { chat_key: key };
        patch[act === "pin" ? "pinned" : "archived"] = !on;
        if (act === "delete") {
          confirmDialog(t("session_delete_confirm")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/sessions/delete", "POST", { chat_key: key }).then(function () {
              if (key === chatSession) {
                var nextKey = chatMeta.sessions.filter(function (s3) { return !s3.archived && s3.chat_key !== key; })[0];
                chatSession = "pending";
                switchChatSession(nextKey ? nextKey.chat_key : "dashboard:private:web");
              }
              loadChatMeta();
              toast(t("session_deleted"));
            });
          });
          return;
        }
        api("/api/qvq/session/flags", "POST", patch).then(function () {

          if (act === "archive" && !on && key === chatSession) {
            var nextKey = chatMeta.sessions.filter(function (s3) { return !s3.archived && s3.chat_key !== key; })[0];
            switchChatSession(nextKey ? nextKey.chat_key : "dashboard:private:web");
          }
          loadChatMeta();
        });
      };
    });
  }

  function renderChatSessions() {
    var navBox = el("qvq-nav-sessions");
    var known = {};
    chatMeta.sessions.forEach(function (s) { known[s.chat_key] = s; });

    var items = chatMeta.sessions.slice();
    if (!known[chatSession]) {
      items.unshift({ chat_key: chatSession, updated: Date.now() / 1000 });
    }
    var archivedCount = chatMeta.sessions.filter(function (s) { return s.archived; }).length;
    if (navBox) {
      var shown = chatShowArchived
        ? items.filter(function (s) { return s.chat_key === chatSession || s.archived; })
        : items.filter(function (s) { return !s.archived || s.chat_key === chatSession; });
      var newBtn = '<div class="qvq-chat-srow qvq-nav-new" data-new="1"><span class="qvq-chat-sname">+ ' + esc(t("chat_new")) + "</span></div>";
      var foot = '<div class="qvq-chat-sfoot' + (chatShowArchived ? " on" : "") + '" data-archived-toggle="1">' +
        esc(t("chat_archived")) + (archivedCount ? " · " + archivedCount : "") + "</div>" +
        (archivedCount && chatShowArchived
          ? '<div class="qvq-chat-sfoot" data-purge-archived="1">' + esc(t("chat_purge_archived")) + "</div>"
          : "");

      var navHtml = '<div class="qvq-nav-srows" data-srows="1">' + newBtn + (sessionRowsHtml(shown) || "") + "</div>" + foot;
      if (navBox.getAttribute("data-html") !== navHtml) {
        navBox.setAttribute("data-html", navHtml);
        navBox.innerHTML = navHtml;
        bindSessionRows(navBox, true);
        var nb = navBox.querySelector("[data-new]");
        if (nb) nb.onclick = function () { newChat(); closeDrawer(); };
        var footEl = navBox.querySelector("[data-archived-toggle]");
        if (footEl) footEl.onclick = function () {
          chatShowArchived = !chatShowArchived;
          renderChatSessions();
        };
        var purgeEl = navBox.querySelector("[data-purge-archived]");
        if (purgeEl) purgeEl.onclick = function () {
          confirmDialog(t("session_delete_confirm")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/sessions/delete-archived", "POST", {}).then(function (data) {
              toast(t("session_deleted") + " × " + ((data && data.removed) || 0));
              if (chatMeta.sessions.some(function (s3) { return s3.archived && s3.chat_key === chatSession; })) {
                chatSession = "pending";
                switchChatSession("dashboard:private:web");
              }
              loadChatMeta();
            });
          });
        };
      }
    }
    var title = el("qvq-chat-title");
    if (title) title.textContent = chatSessionTitle(chatSession);
  }

  function syncPersonaSelect() {
    var psel = el("qvq-chat-persona");
    if (!psel) return;
    var popts = ['<option value="">' + esc(t("chat_follow")) + "</option>"];
    chatMeta.personas.forEach(function (p) {
      popts.push('<option value="' + esc(p.id) + '">' + esc(p.name || p.id) + "</option>");
    });
    psel.innerHTML = popts.join("");
    psel.value = chatPersona;
    if (psel.value !== chatPersona) { chatPersona = ""; }
  }

  function loadChatMeta() {
    Promise.all([
      api("/api/qvq/sessions"),
      api("/api/qvq/personas"),
      api("/api/qvq/models")
    ]).then(function (results) {
      chatMeta.sessions = (results[0] && results[0].sessions) || [];
      chatMeta.personas = (results[1] && results[1].personas) || [];
      chatMeta.uiDefaults = (results[0] && results[0].ui_defaults) || {};

      var exists = chatSession === "dashboard:private:web" ||
        /^dashboard:private:web\d+$/.test(chatSession) ||
        chatMeta.sessions.some(function (s) { return s.chat_key === chatSession; });
      if (!exists) chatSession = "dashboard:private:web";

      applyEffectiveSettings();
      renderChatSessions();
      syncPersonaSelect();
      updateMmLabel();
      loadChatHistory().then(function () {
        checkLive();
      });
    });
  }

  function effortShort() {
    if (chatEffort === "0.3") return t("effort_s_low");
    if (chatEffort === "0.7") return t("effort_s_mid");
    if (chatEffort === "1.0") return t("effort_s_high");
    return t("effort_s_auto");
  }

  function modelShort(id) {
    if (!id) return t("model_s_auto");
    var i = id.indexOf(":");
    return i >= 0 ? id.slice(i + 1) : id;
  }

  function updateMmLabel() {
    var label = el("qvq-chat-mm-label");
    if (!label) return;
    label.textContent = modelShort(chatModel) + " · " + effortShort();
    var btn = el("qvq-chat-mm");
    if (btn) btn.title = (chatModel || t("model_auto")) + " · " + (chatEffort ? chatEffort : t("effort_s_auto"));
  }

  function toggleMmMenu() {
    var old = el("qvq-mm-menu");
    if (old) { old.remove(); return; }
    var anchor = el("qvq-chat-mm");
    if (!anchor) return;
    api("/api/qvq/models").then(function (data) {
      var models = (data && data.models) || [];
      var existing = el("qvq-mm-menu");
      if (existing) { existing.remove(); return; }
      var menu = document.createElement("div");
      menu.className = "qvq-mm-menu";
      menu.id = "qvq-mm-menu";
      var opts = [{ id: "", label: t("model_auto") }].concat(models.map(function (m) { return { id: m.id, label: m.id }; }));
      var html = '<div class="qvq-mention-sec">' + esc(t("chat_model")) + "</div>";
      html += opts.map(function (o) {
        return '<div class="qvq-mention-opt' + (chatModel === o.id ? " sel" : "") + '" data-mm-model="' + esc(o.id) + '"><span>' + esc(o.label) + "</span>" + (chatModel === o.id ? DD_CHECK : "") + "</div>";
      }).join("");
      html += '<div class="qvq-mention-sec">' + esc(t("chat_effort")) + "</div>";
      [["", t("effort_s_auto")], ["0.3", t("effort_s_low")], ["0.7", t("effort_s_mid")], ["1.0", t("effort_s_high")]].forEach(function (pair) {
        html += '<div class="qvq-mention-opt' + (chatEffort === pair[0] ? " sel" : "") + '" data-mm-effort="' + pair[0] + '"><span>' + esc(pair[1]) + "</span>" + (chatEffort === pair[0] ? DD_CHECK : "") + "</div>";
      });
      menu.innerHTML = html;
      document.body.appendChild(menu);
      var rect = anchor.getBoundingClientRect();
      menu.style.right = Math.max(8, window.innerWidth - rect.right) + "px";
      menu.style.bottom = (window.innerHeight - rect.top + 8) + "px";
      menu.querySelectorAll("[data-mm-model]").forEach(function (opt) {
        opt.onclick = function () {
          chatModel = opt.getAttribute("data-mm-model");
          try { localStorage.setItem("qvq_chat_model", chatModel); } catch (e) {}
          saveSessionSettings({ model: chatModel });
          updateMmLabel();
          menu.remove();
        };
      });
      menu.querySelectorAll("[data-mm-effort]").forEach(function (opt) {
        opt.onclick = function () {
          chatEffort = opt.getAttribute("data-mm-effort");
          try { localStorage.setItem("qvq_chat_effort", chatEffort); } catch (e) {}
          saveSessionSettings({ effort: chatEffort });
          updateMmLabel();
          menu.remove();
        };
      });
      setTimeout(function () {
        document.addEventListener("click", function onDoc(e) {
          if (!menu.contains(e.target) && !anchor.contains(e.target)) {
            menu.remove();
            document.removeEventListener("click", onDoc);
          }
        });
      }, 0);
    });
  }

  function refreshMentionBadge() {
    var badge = el("qvq-mention-badge");
    if (!badge) return;
    var n = chatMentions.skills.length + chatMentions.mcp.length;
    badge.style.display = n ? "flex" : "none";
    badge.textContent = String(n);
  }


  function currentQueue() {
    var q = chatQueues[chatSession];
    if (!q) { q = []; chatQueues[chatSession] = q; }
    return q;
  }

  function renderQueue() {
    var box = el("qvq-chat-queue");
    if (!box) return;
    var queue = currentQueue();
    if (!queue.length) {
      box.style.display = "none";
      box.innerHTML = "";
      return;
    }
    box.style.display = "flex";
    box.innerHTML = queue.map(function (item, i) {
      var attsHtml = (item.atts || []).map(function (a) {
        return a.isImage
          ? '<img class="qvq-q-att" src="' + a.data + '" alt=""/>'
          : '<span class="qvq-q-att"><i class="qvq-file-ico">' + FILE_ICON_SVG + "</i>" + esc(a.name) + "</span>";
      }).join("");
      var editBox = item.editing
        ? '<div class="qvq-q-edit"><textarea class="qvq-textarea" rows="2">' + esc(item.text) + "</textarea>" +
          '<div class="qvq-actions"><button class="qvq-btn small" data-q-save="' + i + '">' + esc(t("save")) + "</button>" +
          '<button class="qvq-btn small ghost" data-q-cancel="' + i + '">' + esc(t("cancel")) + "</button></div></div>"
        : '<div class="qvq-q-text">' + esc(item.text) + "</div>" + attsHtml;
      return '<div class="qvq-q-card" draggable="true" data-qi="' + i + '">' +
        '<span class="qvq-q-badge">' + esc(t("queue_badge")) + "</span>" +
        '<div class="qvq-q-main">' + editBox + "</div>" +
        '<div class="qvq-q-ops">' +
        '<button type="button" class="qvq-btn small" data-q-now="' + i + '" title="' + esc(t("queue_send_now")) + '">' + esc(t("queue_send_now")) + "</button>" +
        '<button type="button" class="qvq-icon-btn" data-q-edit="' + i + '" title="' + esc(t("edit")) + '"><svg viewBox="0 0 24 24"><path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg></button>' +
        '<button type="button" class="qvq-icon-btn" data-q-del="' + i + '" title="' + esc(t("del")) + '"><svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2m-9 0v14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6"/></svg></button>' +
        '<span class="qvq-q-drag" title="⇅">⇅</span>' +
        "</div></div>";
    }).join("");
    box.querySelectorAll("[data-q-now]").forEach(function (btn) {
      btn.onclick = function () {
        if (chatBusy) return;
        var i = parseInt(btn.getAttribute("data-q-now"), 10);
        var item = queue.splice(i, 1)[0];
        renderQueue();
        dispatchMessage(item.text, item.atts);
      };
    });
    box.querySelectorAll("[data-q-edit]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-q-edit"), 10);
        queue[i].editing = true;
        renderQueue();
      };
    });
    box.querySelectorAll("[data-q-del]").forEach(function (btn) {
      btn.onclick = function () {
        queue.splice(parseInt(btn.getAttribute("data-q-del"), 10), 1);
        renderQueue();
      };
    });
    box.querySelectorAll("[data-q-save]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-q-save"), 10);
        var card = btn.closest(".qvq-q-card");
        queue[i].text = card.querySelector("textarea").value;
        queue[i].editing = false;
        renderQueue();
      };
    });
    box.querySelectorAll("[data-q-cancel]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-q-cancel"), 10);
        queue[i].editing = false;
        renderQueue();
      };
    });

    var dragIndex = null;
    box.querySelectorAll(".qvq-q-card").forEach(function (card) {
      card.addEventListener("dragstart", function (e) {
        dragIndex = parseInt(card.getAttribute("data-qi"), 10);
        if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
      });
      card.addEventListener("dragover", function (e) { e.preventDefault(); });
      card.addEventListener("drop", function (e) {
        e.preventDefault();
        var to = parseInt(card.getAttribute("data-qi"), 10);
        if (dragIndex === null || dragIndex === to) return;
        var moved = queue.splice(dragIndex, 1)[0];
        queue.splice(to, 0, moved);
        dragIndex = null;
        renderQueue();
      });
    });
  }

