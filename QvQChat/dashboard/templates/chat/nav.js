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


  // 快速跳转面板：搜会话 / 页面 / 设置项（Ctrl+K / Cmd+K）
  function openQuickPanel() {
    var old = el("qvq-quick-panel");
    if (old) { old.remove(); return; }
    var wrap = document.createElement("div");
    wrap.id = "qvq-quick-panel";
    wrap.innerHTML = '<div class="qvq-quick-card"><input class="qvq-input" id="qvq-quick-input" placeholder="' +
      esc(t("panel_ph")) + '" /><div class="qvq-quick-list" id="qvq-quick-list"></div></div>';
    document.body.appendChild(wrap);
    var input = wrap.querySelector("#qvq-quick-input");
    var list = wrap.querySelector("#qvq-quick-list");
    var items = [];
    el("qvq-nav").querySelectorAll(".qvq-nav-btn").forEach(function (btn) {
      items.push({ label: btn.querySelector(".qvq-nav-tx") ? btn.querySelector(".qvq-nav-tx").textContent : btn.textContent, tag: t("nav_group_core"), act: function () { switchTab(btn.getAttribute("data-tab")); } });
    });
    (chatMeta.sessions || []).forEach(function (s3) {
      items.push({ label: chatSessionTitle(s3.chat_key), tag: t("nav_chat"), act: function () { switchChatSession(s3.chat_key); } });
    });
    (typeof settingsFields !== "undefined" ? settingsFields : []).forEach(function (f) {
      if (!f) return;
      items.push({ label: (f.description || f.key), tag: t("nav_settings"), act: function () {
        switchTab("settings");
        setTimeout(function () {
          var node = document.querySelector('[data-field="' + f.key + '"]');
          if (node && node.scrollIntoView) node.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 120);
      } });
    });
    var picked = -1;
    function render(q) {
      q = (q || "").trim().toLowerCase();
      var shown = items.filter(function (it) { return !q || it.label.toLowerCase().indexOf(q) >= 0; }).slice(0, 30);
      picked = shown.length ? 0 : -1;
      if (!shown.length) { list.innerHTML = '<div class="qvq-empty">' + esc(t("panel_none")) + "</div>"; return; }
      list.innerHTML = shown.map(function (it, i) {
        return '<div class="qvq-quick-item' + (i === picked ? " on" : "") + '" data-i="' + i + '"><span>' + esc(it.label) + '</span><span class="qvq-chip">' + esc(it.tag) + "</span></div>";
      }).join("");
      list.querySelectorAll(".qvq-quick-item").forEach(function (node) {
        node.onclick = function () { close(); shown[parseInt(node.getAttribute("data-i"), 10)].act(); };
      });
      return shown;
    }
    function close() { wrap.remove(); document.removeEventListener("keydown", onKey, true); }
    function onKey(e) {
      var shown = render(input.value);
      if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!shown.length) return;
        picked = (picked + (e.key === "ArrowDown" ? 1 : shown.length - 1)) % shown.length;
        list.querySelectorAll(".qvq-quick-item").forEach(function (n, i) { n.classList.toggle("on", i === picked); });
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (picked >= 0 && shown[picked]) { close(); shown[picked].act(); }
      }
    }
    wrap.addEventListener("mousedown", function (e) { if (e.target === wrap) close(); });
    document.addEventListener("keydown", onKey, true);
    input.addEventListener("input", function () { render(input.value); });
    input.focus();
    render("");
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
    maybeOnboarding();
    api("/api/qvq/status").then(function (data) {
      var tools = data.tools || {};
      var total = 0;
      Object.keys(tools).forEach(function (k) { total += tools[k] || 0; });
      var mcpCount = (data.mcp || []).length;
      var extCount = (data.extensions || []).length;
      var cards = [
        { cap: t("stat_models"), num: data.models || 0, cls: "hl-red", tab: "models" },
        { cap: t("stat_tools"), num: total, cls: "hl-teal", tab: "tools" },
        { cap: t("stat_eco"), num: tools.eco || 0, cls: "", tab: "tools" },
        { cap: t("stat_extensions"), num: extCount, cls: "", tab: "tools" },
        { cap: t("stat_sessions"), num: data.sessions || 0, cls: "", tab: "sessions" },
        { cap: t("stat_tasks"), num: data.tasks || 0, cls: "", tab: "tasks" },
        { cap: t("stat_mcp"), num: mcpCount, cls: "", tab: "mcp" },
        { cap: t("stat_security"), num: (data.trust_agent ? t("trust_on") : esc(data.security_level || "-")), cls: data.trust_agent ? "hl-red" : "", tab: "settings" }
      ];
// 统计卡点击：跳转对应页
      el("qvq-stats").innerHTML = cards.map(function (c) {
        return '<div class="qvq-stat ' + c.cls + '" data-goto="' + esc(c.tab || "") + '" role="button" tabindex="0"><div class="num">' + esc(c.num) + '</div><div class="cap">' + esc(c.cap) + "</div></div>";
      }).join("");
      el("qvq-stats").querySelectorAll(".qvq-stat[data-goto]").forEach(function (card) {
        var go = function () {
          var tab = card.getAttribute("data-goto");
          if (tab) switchTab(tab);
        };
        card.onclick = go;
        card.onkeydown = function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); }
        };
      });
      var usage = data.usage_today || {};
      var tokens = usage.tokens || 0;
      var limit = usage.limit || 0;
      var heroSub = [];
      if (data.version) heroSub.push("v" + data.version);
      if (data.eco) heroSub.push((data.eco.modules || 0) + t("stat_eco_modules") + " · " + (data.eco.tools || 0) + t("stat_eco_tools"));
      heroSub.push(t("takeovers") + " " + (data.takeovers || 0));
      var sub = el("qvq-hero-sub");
      if (sub) sub.textContent = heroSub.join(" · ");
      var num = el("qvq-hero-tokens");
      if (num) num.textContent = tokens;
      var bar = el("qvq-hero-bar");
      var pct = limit ? Math.min(100, (tokens / limit) * 100) : 0;
      if (bar) {
        bar.style.width = pct + "%";
        bar.classList.toggle("warn", pct >= 80 && pct < 100);
        bar.classList.toggle("crit", pct >= 100);
      }
      var lim = el("qvq-hero-limit");
      if (lim) {
        lim.textContent = limit
          ? t("usage_limit") + " " + limit + " · " + Math.min(100, Math.round((tokens / limit) * 100)) + "%"
          : t("hero_no_limit");
        // 点击设置每日上限（0 = 不限制）
        lim.classList.add("editable");
        lim.title = t("limit_edit_hint");
        lim.onclick = function () {
          openForm(t("limit_edit_title"), "<label class='qvq-label'>" + esc(t("limit_edit_label")) + "</label>" +
            "<input class='qvq-input' id='qvq-limit-input' type='number' min='0' step='10000' value='" + (limit || 0) + "' placeholder='0' />" +
            "<div class='qvq-tool-desc'>" + esc(t("limit_edit_hint")) + "</div>", function (body) {
            var raw = fv(body, "qvq-limit-input");
            var value = Math.max(0, parseInt(raw, 10) || 0);
            api("/api/qvq/config", "POST", { daily_token_limit: value }).then(function (r) {
              if (r && (r.ok || r.__http === 200) && !(r.errors && Object.keys(r.errors).length)) {
                toast(t("saved"));
                closeModal();
                loadOverview();
              } else {
                toast((r && r.error) || "error", true);
              }
            });
          });
        };
      }
    });
    api("/api/qvq/usage").then(function (data) {
      renderUsageChart(data || {}, "qvq-home-chart");
    });
    api("/api/qvq/costs").then(function (data) {
      renderCostChart(data || {}, "qvq-home-cost");
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

  // 多账户隔离：chat_key 尾部的 @account 后缀 → 账户名（无后缀返回空）。
  // 显示时经 display_names 映射表还原可读账户名
  function accountOf(key) {
    var s = String(key || "");
    var i = s.lastIndexOf("@");
    var acct = i >= 0 ? s.slice(i + 1) : "";
    try {
      var names = (chatMeta.accounts_overview || {}).display_names || {};
      if (names[acct]) return names[acct];
    } catch (e) {}
    return acct;
  }

  // 人格绑定的层级判定与排序（回落链：会话 → 群 → 账户 → 平台 → 全局默认）
  function bindTierOf(key) {
    var s = String(key || "");
    if (s.indexOf(":*") >= 0) return "platform";
    if (s.charAt(0) === "@") return "account";
// 群级键：platform:group:gid，且不含 ":u" 隔离后缀
    var parts = s.split(":");
    if (parts.length >= 3 && parts[1] === "group" && s.indexOf(":u") < 0) return "group";
    return "session";
  }

  function bindTierRank(key) {
    var order = { session: 0, group: 1, account: 2, platform: 3 };
    return order[bindTierOf(key)];
  }

  var chatShowArchived = false;
  // 会话列表按页取，每页 chatSessLimit 条
  var chatSessPage = 0;
  var chatSessTotal = 0;
  var chatSessLimit = 80;

  var PIN_SVG = "<svg viewBox='0 0 24 24'><path d='M12 17v5M9 3h6l-1 7 3 2v2H7v-2l3-2z'/></svg>";
  var DEL_SVG = "<svg viewBox='0 0 24 24'><path d='M3 6h18M8 6V4h8v2m-9 0v14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6'/></svg>";
  var REN_SVG = "<svg viewBox='0 0 24 24'><path d='M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z'/></svg>";
  var ARC_SVG = "<svg viewBox='0 0 24 24'><path d='M3 6h18v3H3zM5 9v11h14V9M9 13h6'/></svg>";
  // 非图片附件的文件图标（messages/nav 共用的全局 SVG）
  var FILE_ICON_SVG = "<svg viewBox='0 0 24 24'><path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zm0 0v5h5'/></svg>";

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
        '<button type="button" data-act="rename" data-key="' + esc(s.chat_key) + '" title="' + esc(t("session_rename")) + '">' + REN_SVG + "</button>" +
        '<button type="button" data-act="delete" data-key="' + esc(s.chat_key) + '" title="' + esc(t("chat_delete")) + '">' + DEL_SVG + "</button>" +
        "</span>";
      var liveCls = s.live ? " liverun" : "";
      var acct = accountOf(s.chat_key);
      var fullTitle = (chatSessionTitle(s.chat_key) || s.chat_key) + (acct ? "  @" + acct : "") + "\n" + s.chat_key;
      return '<div class="qvq-chat-srow' + (active ? " active" : "") + (pinned ? " pinned" : "") + liveCls + '" data-key="' + esc(s.chat_key) + '" title="' + esc(fullTitle) + '">' +
        '<span class="qvq-chat-sname">' + esc(chatSessionTitle(s.chat_key)) + "</span>" +
        (acct ? '<span class="qvq-acct-badge" title="@' + esc(acct) + '">' + esc(acct) + "</span>" : "") +
        '<span class="qvq-chat-stime">' + esc(fmtSmart(s.updated)) + "</span>" + acts + "</div>";
    }).join("");
  }

  function sessionRename(key) {
    var cur = "";
    chatMeta.sessions.forEach(function (s) { if (s.chat_key === key) cur = s.name || ""; });
    openForm(t("session_rename"),
      "<label class='qvq-label'>" + esc(t("session_name_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-rename-input' value='" + esc(cur) + "' maxlength='60' placeholder='" + esc(t("session_rename_ph")) + "'/>",
      function (body) {
        var name = fv(body, "qvq-rename-input");
        api("/api/qvq/session/rename", "POST", { chat_key: key, name: name }).then(function (r) {
          if (r && r.ok) {
            toast(t("saved"));
            closeModal();
            loadChatMeta();
          } else {
            toast((r && r.error) || "error", true);
          }
        });
      });
    var input = el("qvq-rename-input");
    if (input) { input.focus(); input.select(); }
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
        if (act === "rename") {
          sessionRename(key);
          return;
        }
        var patch = { chat_key: key };
        patch[act === "pin" ? "pinned" : "archived"] = !on;
        if (act === "delete") {
// 删除会话并显示撤销提示
          api("/api/qvq/sessions/delete", "POST", { chat_key: key }).then(function (r) {
            if (key === chatSession) {
              var nextKey = chatMeta.sessions.filter(function (s3) { return !s3.archived && s3.chat_key !== key; })[0];
              chatSession = "pending";
              switchChatSession(nextKey ? nextKey.chat_key : "dashboard:private:web");
            }
            loadChatMeta();
            if (r && r.undo) {
              toastUndo(t("session_deleted"), function () {
                api("/api/qvq/trash/restore", "POST", { token: r.undo }).then(function () { loadChatMeta(); });
              });
            } else {
              toast(t("session_deleted"));
            }
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
    var sideBox = el("qvq-chat-side"); // 圣杯三栏：对话页左侧会话列表（宽屏显示）
    var known = {};
    chatMeta.sessions.forEach(function (s) { known[s.chat_key] = s; });

    var items = chatMeta.sessions.slice();
    if (!known[chatSession]) {
      items.unshift({ chat_key: chatSession, updated: Date.now() / 1000 });
    }
    var archivedCount = chatShowArchived ? chatSessTotal : chatMeta.sessions.filter(function (s) { return s.archived; }).length;
    var shown = chatShowArchived
      ? items.filter(function (s) { return s.chat_key === chatSession || s.archived; })
      : items.filter(function (s) { return !s.archived || s.chat_key === chatSession; });
    var newBtn = '<div class="qvq-chat-srow qvq-nav-new" data-new="1"><span class="qvq-chat-sname">+ ' + esc(t("chat_new")) + "</span></div>";
    var pages = Math.max(1, Math.ceil(chatSessTotal / chatSessLimit));
    var pager = "";
    if (pages > 1) {
      pager = '<div class="qvq-chat-sfoot" data-sess-pager="1">' +
        '<span class="qvq-chat-pg" data-pg="prev"' + (chatSessPage <= 0 ? ' style="opacity:.35"' : "") + '>‹</span>' +
        "<span>" + (chatSessPage + 1) + " / " + pages + "</span>" +
        '<span class="qvq-chat-pg" data-pg="next"' + (chatSessPage >= pages - 1 ? ' style="opacity:.35"' : "") + '>›</span></div>';
    }
    var foot = '<div class="qvq-chat-sfoot' + (chatShowArchived ? " on" : "") + '" data-archived-toggle="1">' +
      esc(t("chat_archived")) + (archivedCount ? " · " + archivedCount : "") + "</div>" +
      (archivedCount && chatShowArchived
        ? '<div class="qvq-chat-sfoot" data-purge-archived="1">' + esc(t("chat_purge_archived")) + "</div>"
        : "");

    var listHtml = '<div class="qvq-nav-srows" data-srows="1">' + newBtn + (sessionRowsHtml(shown) || "") + "</div>" + pager + foot;
// 浮层头部带关闭按钮（仅侧面板）
    var sideHtml = '<div class="qvq-chat-shead"><span class="qvq-chat-shead-t">' + esc(t("chat_sessions_panel")) +
      '</span><button class="qvq-icon-btn" data-side-close="1" title="' + esc(t("cancel")) + '">' +
      '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>' + listHtml;
    if (sideBox && sideBox.getAttribute("data-html") !== sideHtml) {
      sideBox.setAttribute("data-html", sideHtml);
      sideBox.innerHTML = sideHtml;
      bindSessionRows(sideBox, false);
      var sCloseBtn = sideBox.querySelector("[data-side-close]");
      if (sCloseBtn) sCloseBtn.onclick = function () { sideBox.classList.remove("open"); };
// 选中会话 / 新建后收起浮层
      sideBox.querySelectorAll(".qvq-chat-srow").forEach(function (row) {
        row.addEventListener("click", function () { sideBox.classList.remove("open"); });
      });
      var sb = sideBox.querySelector("[data-new]");
      if (sb) sb.onclick = function () { newChat(); };
      var sPager = sideBox.querySelector("[data-sess-pager]");
      if (sPager) {
        var sPrev = sPager.querySelector("[data-pg=prev]");
        var sNext = sPager.querySelector("[data-pg=next]");
        if (sPrev) sPrev.onclick = function () { loadChatMeta({ page: chatSessPage - 1, history: false }); };
        if (sNext) sNext.onclick = function () { loadChatMeta({ page: chatSessPage + 1, history: false }); };
      }
      var sFoot = sideBox.querySelector("[data-archived-toggle]");
      if (sFoot) sFoot.onclick = function () {
        chatShowArchived = !chatShowArchived;
        loadChatMeta({ resetPage: true, history: false });
      };
      var sPurge = sideBox.querySelector("[data-purge-archived]");
      if (sPurge) sPurge.onclick = function () {
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
    if (navBox) {
      var navHtml = listHtml;
      if (navBox.getAttribute("data-html") !== navHtml) {
        navBox.setAttribute("data-html", navHtml);
        navBox.innerHTML = navHtml;
        bindSessionRows(navBox, true);
        var nb = navBox.querySelector("[data-new]");
        if (nb) nb.onclick = function () { newChat(); closeDrawer(); };
        var nPager = navBox.querySelector("[data-sess-pager]");
        if (nPager) {
          var nPrev = nPager.querySelector("[data-pg=prev]");
          var nNext = nPager.querySelector("[data-pg=next]");
          if (nPrev) nPrev.onclick = function () { loadChatMeta({ page: chatSessPage - 1, history: false }); };
          if (nNext) nNext.onclick = function () { loadChatMeta({ page: chatSessPage + 1, history: false }); };
        }
        var footEl = navBox.querySelector("[data-archived-toggle]");
        if (footEl) footEl.onclick = function () {
          chatShowArchived = !chatShowArchived;
          loadChatMeta({ resetPage: true, history: false });
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

  // opts.history=false：只刷新会话/人格/模型清单，不重拉整段历史
  // 历史由本地增量维护
  function loadChatMeta(opts) {
    var withHistory = !(opts && opts.history === false);
    if (opts && opts.page != null) chatSessPage = Math.max(0, parseInt(opts.page, 10) || 0);
    if (opts && opts.resetPage) chatSessPage = 0;
    var sessUrl = "/api/qvq/sessions?limit=" + chatSessLimit + "&start=" + (chatSessPage * chatSessLimit) +
      (chatShowArchived ? "&archived=1" : "");
    Promise.all([
      api(sessUrl),
      api("/api/qvq/personas"),
      api("/api/qvq/models")
    ]).then(function (results) {
      chatMeta.sessions = (results[0] && results[0].sessions) || [];
      chatSessTotal = (results[0] && results[0].total) || chatMeta.sessions.length;
      chatMeta.personas = (results[1] && results[1].personas) || [];
      chatMeta.uiDefaults = (results[0] && results[0].ui_defaults) || {};
      chatMeta.accounts_overview = (results[0] && results[0].accounts) || {};

      var exists = chatSession === "dashboard:private:web" ||
        /^dashboard:private:web\d+$/.test(chatSession) ||
        chatMeta.sessions.some(function (s) { return s.chat_key === chatSession; });
      if (!exists) chatSession = "dashboard:private:web";

      applyEffectiveSettings();
      renderChatSessions();
      syncPersonaSelect();
      updateMmLabel();
      if (withHistory) {
        loadChatHistory().then(function () {
          checkLive();
        });
      } else {
        renderChat();
        // opts.live=false：调用方已自行 settle，不再触发 checkLive
        if (!(opts && opts.live === false)) checkLive();
      }
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
      return '<div class="qvq-q-card" draggable="true" data-qi="' + i + '">' +
        '<span class="qvq-q-badge">' + esc(t("queue_badge")) + "</span>" +
        '<div class="qvq-q-main"><div class="qvq-q-text">' + esc(item.text) + "</div>" + attsHtml + "</div>" +
        '<div class="qvq-q-ops">' +
        '<button type="button" class="qvq-btn small" data-q-now="' + i + '" title="' + esc(t("queue_send_now")) + '">' + esc(t("queue_send_now")) + "</button>" +
        '<button type="button" class="qvq-icon-btn" data-q-edit="' + i + '" title="' + esc(t("queue_edit")) + '" aria-label="' + esc(t("queue_edit")) + '"><svg viewBox="0 0 24 24"><path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg></button>' +
        '<button type="button" class="qvq-icon-btn" data-q-del="' + i + '" title="' + esc(t("del")) + '"><svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2m-9 0v14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6"/></svg></button>' +
        '<span class="qvq-q-drag" title="⇅">⇅</span>' +
        "</div></div>";
    }).join("");
    box.querySelectorAll("[data-q-now]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-q-now"), 10);
        var item = queue.splice(i, 1)[0];
        if (!item) { renderQueue(); return; }
        if (chatBusy) {
          // 立即发送（回复中）
          queue.unshift(item);
          renderQueue();
          cancelChat();
          return;
        }
        renderQueue();
        dispatchMessage(item.text, item.atts);
      };
    });
    box.querySelectorAll("[data-q-edit]").forEach(function (btn) {
      btn.onclick = function () {
        var i = parseInt(btn.getAttribute("data-q-edit"), 10);
        var item = queue.splice(i, 1)[0];
        if (!item) { renderQueue(); return; }
        // 编辑回输入框：文本与附件回填 composer，条目移出队列
        var input = el("qvq-chat-input");
        if (input) {
          input.value = input.value.trim() ? input.value.replace(/\s+$/, "") + "\n" + item.text : item.text;
          input.style.height = "auto";
          input.style.height = Math.min(input.scrollHeight, 160) + "px";
          input.focus();
        }
        chatAtts = chatAtts.concat(item.atts || []);
        renderAttach();
        renderQueue();
      };
    });
    box.querySelectorAll("[data-q-del]").forEach(function (btn) {
      btn.onclick = function () {
        queue.splice(parseInt(btn.getAttribute("data-q-del"), 10), 1);
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

