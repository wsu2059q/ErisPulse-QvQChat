/* 会话操作：导出/分享、会话设置、模型与强度菜单、提名 */
  function exportSession() {
    api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(chatSession)).then(function (data) {
      var msgs = (data && data.messages) || [];
      var lines = ["# " + chatSessionTitle(chatSession), ""];
      msgs.forEach(function (m) {
        if (!m || typeof m !== "object") return;
        var role = m.role === "user" ? t("role_user") : m.role === "assistant" ? "AI" : (m.role || "");
        lines.push("## " + role, "", contentText(m.content), "");
      });
      var blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = (chatSessionTitle(chatSession) || "session").replace(/[\\/:*?"<>|]+/g, "_") + ".md";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 200);
    });
  }

  function applyEffectiveSettings() {
    var curSess = null;
    chatMeta.sessions.forEach(function (s3) { if (s3.chat_key === chatSession) curSess = s3; });
    var ui = (curSess && curSess.ui) || {};
    var def = chatMeta.uiDefaults || {};
    if (ui.density) chatDensity = ui.density;
    else if (def.density) chatDensity = def.density;
    if (ui.model != null) chatModel = ui.model;
    else if (def.model != null) chatModel = def.model;
    if (ui.effort != null) chatEffort = ui.effort;
    else if (def.effort != null) chatEffort = def.effort;
    try {
      localStorage.setItem("qvq_chat_density", chatDensity);
      localStorage.setItem("qvq_chat_model", chatModel);
      localStorage.setItem("qvq_chat_effort", chatEffort);
    } catch (e) {}
    updateMmLabel();
  }

  function chatSourceLabel(key) {
    var parts = String(key || "").split(":");
    if (parts.length >= 3) return parts[0] + " · " + parts[2];
    return key || "-";
  }

  function saveSessionSettings(patch) {
    api("/api/qvq/session/settings", "POST", { chat_key: chatSession, settings: patch }).catch(function () {});
  }

  function openSessionSettings() {
    api("/api/qvq/models").then(function (data) {
      var models = (data && data.models) || [];
      var mOpts = ['<option value="">' + esc(t("model_auto")) + "</option>"].concat(models.map(function (m2) {
        return '<option value="' + esc(m2.id) + '">' + esc(m2.id) + "</option>";
      })).join("");
      var pOpts = ['<option value="">' + esc(t("chat_follow")) + "</option>"].concat(chatMeta.personas.map(function (p2) {
        return '<option value="' + esc(p2.id) + '">' + esc(p2.name || p2.id) + "</option>";
      })).join("");
      var html =
        "<label class='qvq-label'>" + esc(t("chat_density")) + "</label>" +
        "<select class='qvq-select' id='qs-density'><option value='detail'>" + esc(t("density_detail")) + "</option><option value='brief'>" + esc(t("density_brief")) + "</option></select>" +
        "<label class='qvq-label'>" + esc(t("chat_model")) + "</label>" +
        "<select class='qvq-select' id='qs-model'>" + mOpts + "</select>" +
        "<label class='qvq-label'>" + esc(t("chat_effort")) + "</label>" +
        "<select class='qvq-select' id='qs-effort'><option value=''>" + esc(t("effort_s_auto")) + "</option><option value='0.3'>" + esc(t("effort_s_low")) + "</option><option value='0.7'>" + esc(t("effort_s_mid")) + "</option><option value='1.0'>" + esc(t("effort_s_high")) + "</option></select>" +
        "<label class='qvq-label'>" + esc(t("chat_persona_binding")) + "</label>" +
        "<select class='qvq-select' id='qs-persona'>" + pOpts + "</select>" +
        "<div class='qvq-actions'><button class='qvq-btn' data-qs-save>" + esc(t("settings_save_session")) + "</button>" +
        "<button class='qvq-btn ghost' data-qs-all>" + esc(t("settings_apply_all")) + "</button></div>" +
        "<div class='qvq-actions'><button class='qvq-btn ghost' data-qs-compact>" + esc(t("chat_compact")) + "</button></div>" +
      "<div class='qvq-settings-danger'><button type='button' class='qvq-quiet-danger' data-qs-clear>" + esc(t("chat_clear")) + "</button></div>";
      openModal(t("chat_settings"), html);
      var body = el("qvq-modal-body");
      body.querySelector("#qs-density").value = chatDensity;
      body.querySelector("#qs-model").value = chatModel;
      if (body.querySelector("#qs-model").value !== chatModel) body.querySelector("#qs-model").value = "";
      body.querySelector("#qs-effort").value = chatEffort;
      body.querySelector("#qs-persona").value = chatPersona;
      function collect() {
        return {
          density: body.querySelector("#qs-density").value,
          model: body.querySelector("#qs-model").value,
          effort: body.querySelector("#qs-effort").value,
        };
      }
      function applyLocal(vals) {
        chatDensity = vals.density;
        chatModel = vals.model;
        chatEffort = vals.effort;
        try {
          localStorage.setItem("qvq_chat_density", chatDensity);
          localStorage.setItem("qvq_chat_model", chatModel);
          localStorage.setItem("qvq_chat_effort", chatEffort);
        } catch (e) {}
        updateMmLabel();
      }
      body.querySelector("[data-qs-save]").onclick = function () {
        var vals = collect();
        applyLocal(vals);
        saveSessionSettings(vals);
        var persona = body.querySelector("#qs-persona").value;
        chatPersona = persona;
        api("/api/qvq/personas/bind", "POST", { chat_key: chatSession, persona: persona || null }).then(function () {
          toast(t("saved"));
          closeModal();
          loadChatMeta();
        });
      };
      body.querySelector("[data-qs-all]").onclick = function () {
        var vals = collect();
        applyLocal(vals);
        saveSessionSettings(vals);
        api("/api/qvq/settings/defaults", "POST", { settings: vals }).then(function () {
          toast(t("saved"));
          closeModal();
        });
      };
      body.querySelector("[data-qs-compact]").onclick = function () {
        api("/api/qvq/session/compact", "POST", { chat_key: chatSession }).then(function (data) {
          toast(t("compact_done_short") + ": " + (((data || {}).report || {}).actions || ["noop"]).join(", "));
        });
      };
      body.querySelector("[data-qs-clear]").onclick = function () {
        confirmDialog(t("chat_clear_confirm")).then(function (ok) {
          if (!ok) return;
          api("/api/qvq/sessions/reset", "POST", { chat_key: chatSession }).then(function () {
            toast(t("saved"));
            closeModal();
            loadChatHistory();
            loadChatMeta();
          });
        });
      };
    });
  }

  function openShareModal() {
    var body = el("qvq-modal-body");
    var html =
      "<label class='qvq-label'>" + esc(t("share_expires")) + "</label>" +
      "<select class='qvq-select' id='qvq-share-exp'>" +
      "<option value='1'>1 h</option><option value='24' selected>24 h</option><option value='72'>72 h</option><option value='168'>7 d</option></select>" +
      "<label class='qvq-label'>" + esc(t("share_max_tokens")) + "</label>" +
      "<input class='qvq-input' id='qvq-share-tokens' type='number' min='200' max='200000' value='4000'/>" +
      "<div class='qvq-actions'><button class='qvq-btn' data-share-create>" + esc(t("share_create")) + "</button>" +
      "<button class='qvq-btn ghost' data-share-export>" + esc(t("share_export")) + "</button></div>" +
      "<div id='qvq-share-result' style='display:none'>" +
      "<label class='qvq-label'>" + esc(t("share_url")) + "</label>" +
      "<div class='qvq-share-url'><input class='qvq-input' id='qvq-share-url' readonly/><button class='qvq-btn small' id='qvq-share-copy'>" + esc(t("copy")) + "</button></div>" +
      "<div class='qvq-share-hint'>" + esc(t("share_hint")) + "</div></div>";
    openModal(t("chat_share"), html);
    body.querySelector("[data-share-export]").onclick = function () {
      closeModal();
      exportSession();
    };
    body.querySelector("[data-share-create]").onclick = function () {
      api("/api/qvq/session/share", "POST", {
        chat_key: chatSession,
        expires_hours: parseInt(fv(body, "qvq-share-exp"), 10) || 24,
        max_tokens: parseInt(fv(body, "qvq-share-tokens"), 10) || 4000,
      }).then(function (data) {
        if (!data || !data.url) {
          toast((data && data.error) || t("chat_err"), true);
          return;
        }
        var full = location.origin + data.url;
        body.querySelector("#qvq-share-result").style.display = "block";
        body.querySelector("#qvq-share-url").value = full;
        body.querySelector("#qvq-share-copy").onclick = function () {
          copyText(full);
          toast(t("copied"));
        };
      });
    };
  }

  function toggleMentionMenu() {
    var old = el("qvq-mention-menu");
    if (old) { old.remove(); return; }
    var anchor = el("qvq-chat-mention");
    if (!anchor) return;
    Promise.all([api("/api/qvq/skills"), api("/api/qvq/mcp")]).then(function (results) {
      var skills = (results[0] && results[0].skills) || [];
      var mcpTools = [];
      var clients = (results[1] && results[1].clients) || [];
      (Array.isArray(clients) ? clients : []).forEach(function (c) {
        (c.tool_names || []).forEach(function (name) {
          mcpTools.push({ name: name, server: c.name || "" });
        });
      });
      if (!skills.length && !mcpTools.length) {
        toast(t("mention_none"), true);
        return;
      }
      var menu = document.createElement("div");
      menu.className = "qvq-mention-menu";
      menu.id = "qvq-mention-menu";
      var html = "";
      if (skills.length) {
        html += '<div class="qvq-mention-sec">' + esc(t("nav_skills")) + "</div>";
        html += skills.map(function (sk) {
          var on = chatMentions.skills.indexOf(sk.name) >= 0;
          return '<label class="qvq-mention-opt"><input type="checkbox" data-kind="skill" data-name="' + esc(sk.name) + '"' + (on ? " checked" : "") + "/><span>" + esc(sk.name) + "</span></label>";
        }).join("");
      }
      if (mcpTools.length) {
        html += '<div class="qvq-mention-sec">MCP</div>';
        html += mcpTools.map(function (t2) {
          var on = chatMentions.mcp.indexOf(t2.name) >= 0;
          return '<label class="qvq-mention-opt"><input type="checkbox" data-kind="mcp" data-name="' + esc(t2.name) + '"' + (on ? " checked" : "") + "/><span>" + esc(t2.name) + ' <em>' + esc(t2.server) + "</em></span></label>";
        }).join("");
      }
      html += '<button type="button" class="qvq-btn small" data-mention-ok>' + esc(t("mention_ok")) + "</button>";
      menu.innerHTML = html;
      document.body.appendChild(menu);
      var rect = anchor.getBoundingClientRect();
      menu.style.left = Math.max(8, rect.left) + "px";
      menu.style.bottom = (window.innerHeight - rect.top + 8) + "px";
      menu.querySelectorAll("input[type=checkbox]").forEach(function (box) {
        box.onchange = function () {
          var kind = box.getAttribute("data-kind");
          var name = box.getAttribute("data-name");
          var list = kind === "skill" ? chatMentions.skills : chatMentions.mcp;
          var idx = list.indexOf(name);
          if (box.checked && idx < 0) list.push(name);
          if (!box.checked && idx >= 0) list.splice(idx, 1);
          refreshMentionBadge();
        };
      });
      menu.querySelector("[data-mention-ok]").onclick = function () { menu.remove(); };
      setTimeout(function () {
        document.addEventListener("click", function onDoc(e) {
          if (!menu.contains(e.target) && e.target !== anchor) {
            menu.remove();
            document.removeEventListener("click", onDoc);
          }
        });
      }, 0);
    });
  }

  // 会话切换的唯一入口：代际自增 → 过期异步回调全部失效；
  // 正在运行的旧会话流留在后台继续（服务端不停），切回时经 checkLive 重挂
  function switchChatSession(key) {
    if (!key || key === chatSession) return;
    chatEpoch++;
    historySeq++;
    chatSession = key;
    chatHistory = [];
    chatLoading = true;
    loadingOlder = false;
    // 待发送附件属于上一个会话的草稿，切换即清空
    if (chatAtts.length) {
      chatAtts = [];
      renderAttach();
    }
    try { localStorage.setItem("qvq_chat_session", chatSession); } catch (e) {}
    var bound = null;
    chatMeta.sessions.forEach(function (s) { if (s.chat_key === key) bound = s; });
    chatPersona = (bound && bound.persona) || "";
    try {
      if (chatPersona) localStorage.setItem("qvq_chat_persona", chatPersona);
      else localStorage.removeItem("qvq_chat_persona");
    } catch (e) {}
    chatBusy = busySession === key;
    setSendStopping(chatBusy);
    syncPersonaSelect();
    applyEffectiveSettings();
    renderChatSessions();
    renderQueue();
    renderChat();
    loadChatHistory().then(function () {
      checkLive();
    });
    var input = el("qvq-chat-input");
    if (input) input.focus();
  }

  function newChat() {
    api("/api/qvq/sessions/create", "POST", { platform: "dashboard" }).then(function (data) {
      if (!data || !data.chat_key) return;
      switchChatSession(data.chat_key);
      loadChatMeta();
    });
  }

  // 平台侧新消息实时同步：对话页激活且空闲时轻量轮询
  function startChatSync() {
    if (chatSyncTimer) return;
    chatSyncTimer = setInterval(function () {
      if (chatBusy || currentQueue().length) return;
      var section = document.querySelector('.qvq-tab[data-section="chat"]');
      if (!section || !section.classList.contains("active")) return;
      var box = el("qvq-chat-box");
      if (!box) return;
      // 过期防护：请求发出后会话可能已切走，响应只作用于发出时的会话
      var sessionAtPoll = chatSession;
      var epochAtPoll = chatEpoch;
      var versionAtPoll = chatHistoryVersion;
      api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(sessionAtPoll) + "&limit=30").then(function (data) {
        if (epochAtPoll !== chatEpoch || sessionAtPoll !== chatSession) return;
        if (versionAtPoll !== chatHistoryVersion) return;
        if (chatLoading || loadingOlder) return; // 本地加载在途，不覆盖
        var start = (data && data.start) || 0;
        if (chatWindowStart > 0 && start > chatWindowStart) {
          // 用户上翻加载过更早消息（窗口错位）：增量拉取新尾部并追加，而不是整窗替换
          var newTotal = (data && data.total) || 0;
          if (newTotal <= chatTotal) return;
          var tail = [];
          api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(sessionAtPoll) + "&start=" + chatTotal + "&limit=" + (newTotal - chatTotal)).then(function (d2) {
            if (epochAtPoll !== chatEpoch || sessionAtPoll !== chatSession) return;
            if (versionAtPoll !== chatHistoryVersion) return;
            ((d2 && d2.messages) || []).forEach(function (m, idx) {
              if (m && typeof m === "object" && (m.role === "user" || m.role === "assistant")) tail.push(mapServerMessage(m, (d2 && d2.start) || chatTotal, idx));
            });
            if (!tail.length) return;
            var tailSig = tail.map(function (m) { return m.role + "\u0001" + m.text; }).join("\u0002");
            var curTailSig = chatHistory.slice(-tail.length).map(function (m) { return m.role + "\u0001" + m.text; }).join("\u0002");
            if (tailSig === curTailSig) return;
            var stickTail = nearBottom(box);
            chatHistory = chatHistory.concat(tail);
            chatTotal = newTotal;
            renderChat({ stick: stickTail });
          });
          return;
        }
        var msgs = (data && data.messages) || [];
        var fresh = [];
        msgs.forEach(function (m, idx) {
          if (!m || typeof m !== "object") return;
          if (m.role === "user" || m.role === "assistant") fresh.push(mapServerMessage(m, start, idx));
        });
        var sig = fresh.map(function (m) { return m.role + "\u0001" + m.text; }).join("\u0002");
        var curSig = chatHistory.map(function (m) { return m.role + "\u0001" + m.text; }).join("\u0002");
        if (sig !== curSig) {
          // 上翻阅读时不拽到底部；rounds/idx 经 mapServerMessage 统一映射不再丢失
          var stick = nearBottom(box);
          chatHistory = fresh;
          chatWindowStart = start;
          chatTotal = (data && data.total) || fresh.length;
          renderChat({ stick: stick });
        }
      });
    }, 4000);
  }

  function checkLive() {
    // 切回一个正在输出的会话时 chatBusy 为真恰恰是常态，不在此拦截；
    // 已有该会话的活跃节点则无需重复挂
    if (activeLive && activeLive.session === chatSession) return;
    var sessionAtCall = chatSession;
    var epochAtCall = chatEpoch;
    api("/api/qvq/chat/live?session=" + encodeURIComponent(sessionAtCall)).then(function (live) {
      if (epochAtCall !== chatEpoch || sessionAtCall !== chatSession) return;
      if (!live || live.status === "idle") return;
      if (live.status === "running") {
        attachLive(live);
      } else if (live.reply != null || live.error) {
        // 离开期间已结束：服务端已写入最终回复，直接刷新历史
        loadChatHistory();
      }
    });
  }

  // ── mini-markdown 安全渲染：先转义再转换有限语法 ──
  function mdInline(s) {
    return s
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>")
      .replace(/(^|[\s(（>「])\*([^*\n]+)\*(?=[\s).,，。;；!？?」]|$)/g, "$1<i>$2</i>")
      .replace(/\[([^\]\n]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }

  function mdRender(src) {
    var text = String(src == null ? "" : src).replace(/\r\n/g, "\n").trim();
    if (!text) return "";
    var parts = text.split("```");
    var out = "";
    for (var pi = 0; pi < parts.length; pi++) {
      if (pi % 2 === 1) {
        var code = parts[pi];
        var nl = code.indexOf("\n");
        var lang = nl >= 0 ? code.slice(0, nl).trim() : "";
        var body = nl >= 0 ? code.slice(nl + 1) : code;
        out += '<div class="qvq-md-pre"><div class="qvq-md-lang"><span>' + esc(lang || "code") +
          '</span><button class="qvq-md-copy" type="button">' + esc(t("copy")) + "</button></div><pre>" +
          esc(body.replace(/\n$/, "")) + "</pre></div>";
        continue;
      }
      var lines = parts[pi].split("\n");
      var para = [], list = null, quote = [];
      var flush = function () {
        if (para.length) { out += "<p>" + para.map(mdInline).join("<br>") + "</p>"; para = []; }
      };
      var flushList = function () { if (list) { out += "</" + list + ">"; list = null; } };
      var flushQuote = function () {
        if (quote.length) { out += "<blockquote>" + quote.map(mdInline).join("<br>") + "</blockquote>"; quote = []; }
      };
      for (var li = 0; li < lines.length; li++) {
        var tline = lines[li].trim();
        if (!tline) { flush(); flushList(); flushQuote(); continue; }
        var hm = tline.match(/^(#{1,6})\s+(.*)$/);
        if (hm) {
          flush(); flushList(); flushQuote();
          out += "<h" + hm[1].length + ">" + mdInline(esc(hm[2])) + "</h" + hm[1].length + ">";
          continue;
        }
        if (/^(-{3,}|\*{3,})$/.test(tline)) { flush(); flushList(); flushQuote(); out += "<hr/>"; continue; }
        if (tline.indexOf("|") === 0 && li + 1 < lines.length && /^\|[\s:|-]+$/.test(lines[li + 1].trim())) {
          flush(); flushList(); flushQuote();
          var splitRow = function (line) {
            return line.replace(/^\||\|$/g, "").split("|").map(function (c) { return c.trim(); });
          };
          var headCells = splitRow(tline);
          li += 2;
          var bodyRows = [];
          while (li < lines.length && /^\|/.test(lines[li].trim())) { bodyRows.push(splitRow(lines[li].trim())); li++; }
          li--;
          out += "<table><thead><tr>" + headCells.map(function (c) { return "<th>" + mdInline(esc(c)) + "</th>"; }).join("") +
            "</tr></thead><tbody>" + bodyRows.map(function (r) {
              return "<tr>" + r.map(function (c) { return "<td>" + mdInline(esc(c)) + "</td>"; }).join("") + "</tr>";
            }).join("") + "</tbody></table>";
          continue;
        }
        if (tline.indexOf(">") === 0) { flush(); flushList(); quote.push(esc(tline.replace(/^>\s?/, ""))); continue; }
        var ulm = tline.match(/^[-*+]\s+(.*)$/);
        var olm = tline.match(/^\d+[.)]\s+(.*)$/);
        if (ulm || olm) {
          flush(); flushQuote();
          var want = ulm ? "ul" : "ol";
          if (list !== want) { flushList(); out += "<" + want + ">"; list = want; }
          out += "<li>" + mdInline(esc((ulm || olm)[1])) + "</li>";
          continue;
        }
        flushList(); flushQuote();
        para.push(esc(tline));
      }
      flush(); flushList(); flushQuote();
    }
    return out;
  }

  function copyText(s) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(s);
    var ta = document.createElement("textarea");
    ta.value = s;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    ta.remove();
  }

  function bindMdCopy(root) {
    root.querySelectorAll(".qvq-md-copy").forEach(function (btn) {
      btn.onclick = function () {
        var pre = btn.closest(".qvq-md-pre");
        copyText(pre && pre.querySelector("pre") ? pre.querySelector("pre").textContent : "");
        btn.textContent = t("copied");
        setTimeout(function () { btn.textContent = t("copy"); }, 1200);
      };
    });
  }

  // ── 工具步骤时间线 ──
  var STEP_ICON_SVG = "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='4' width='18' height='16' rx='2'/><path d='M7 9l3 3-3 3M13 15h4'/></svg>";

  function stepsHtml(steps, running) {
    var n = steps.length;
    if (!n) return "";
    if (chatDensity === "brief" && !running) return "";
    var rows = steps.map(function (s) {
      var name = s.start ? s.start.name : (s.end ? s.end.name : "?");
      var args = s.start ? String(s.start.arguments || "") : "";
      var runningStep = s.start && !s.end;
      var ms = s.end && s.end.ms != null ? s.end.ms : null;
      var output = s.end ? String(s.end.output || "") : "";
      var compact = args.replace(/\s+/g, " ");
      var short = compact && compact !== "{}" ? "(" + (compact.length > 52 ? compact.slice(0, 52) + "…" : compact) + ")" : "";
      var cost = runningStep ? t("steps_running") : (ms != null ? (ms >= 1000 ? (ms / 1000).toFixed(1) + "s" : ms + "ms") : "");
      return '<div class="qvq-step' + (runningStep ? " running" : "") + '">' +
        '<div class="qvq-step-row" data-step-toggle="1">' +
        '<span class="qvq-step-ico">' + STEP_ICON_SVG + "</span>" +
        '<span class="qvq-step-name">' + esc(name) + "</span>" +
        (short ? '<span class="qvq-step-args">' + esc(short) + "</span>" : "") +
        '<span class="qvq-step-ms">' + esc(cost) + "</span></div>" +
        (output ? '<pre class="qvq-step-detail">' + esc(output) + "</pre>" : "") +
        "</div>";
    }).join("");
    return '<div class="qvq-steps' + (running ? " running" : "") + '">' + rows + "</div>";
  }

  function bindStepToggles(root) {
    root.querySelectorAll("[data-step-toggle]").forEach(function (row) {
      row.onclick = function () { row.closest(".qvq-step").classList.toggle("exp"); };
    });
  }

  function renderSerial(items) {
    // items: [{type:"text",text} | {type:"tool",start,end}] → AI 消息内串行交错 HTML
    return items.map(function (seg) {
      if (seg.type === "text") {
        return '<div class="qvq-round-text">' + (mdRender(seg.text) || esc(seg.text)) + "</div>";
      }
      var runningStep = seg.start && !seg.end;
      var ms = seg.end && seg.end.ms != null ? seg.end.ms : null;
      var cost = runningStep ? t("steps_running") : (ms != null ? (ms >= 1000 ? (ms / 1000).toFixed(1) + "s" : ms + "ms") : "");
      var output = seg.end ? String(seg.end.output || "") : "";
      var args = seg.start ? String(seg.start.arguments || "") : "";
      var compact = args.replace(/\s+/g, " ");
      var short = compact && compact !== "{}" ? "(" + (compact.length > 52 ? compact.slice(0, 52) + "…" : compact) + ")" : "";
      return '<div class="qvq-step' + (runningStep ? " running" : "") + '"><div class="qvq-step-row" data-step-toggle="1">' +
        '<span class="qvq-step-ico">' + STEP_ICON_SVG + '</span>' +
        '<span class="qvq-step-name">' + esc(seg.start ? seg.start.name : "?") + "</span>" +
        (short ? '<span class="qvq-step-args">' + esc(short) + "</span>" : "") +
        '<span class="qvq-step-ms">' + esc(cost) + "</span></div>" +
        (output ? '<pre class="qvq-step-detail">' + esc(output) + "</pre>" : "") +
        "</div>";
    }).join("");
  }

  function roundsToItems(rounds) {
    var items = [];
    (rounds || []).forEach(function (r) {
      if (r.text) items.push({ type: "text", text: r.text });
      (r.tools || []).forEach(function (t2) {
        items.push({ type: "tool", start: { step_id: "r", name: t2.tool, arguments: t2.arguments }, end: { output: t2.output, ms: t2.ms } });
      });
    });
    return items;
  }

  function segmentsToRounds(segs) {
    var rounds = [];
    (segs || []).forEach(function (seg) {
      if (seg.type === "text") {
        var piece = String(seg.text || "");
        if (!piece) return; // 跳过空段，避免无排版硬拼
        if (rounds.length && !rounds[rounds.length - 1].tools.length && rounds[rounds.length - 1].text) {
          rounds[rounds.length - 1].text += "\n\n" + piece;
        } else {
          rounds.push({ text: piece, tools: [] });
        }
      } else if (seg.type === "tool") {
        // 未收到 end 的工具段（中断/取消）也保留，不再静默丢弃中间步骤
        if (!rounds.length) rounds.push({ text: "", tools: [] });
        rounds[rounds.length - 1].tools.push({
          tool: seg.start ? seg.start.name : "?",
          arguments: seg.start ? String(seg.start.arguments || "") : "",
          output: (seg.end && seg.end.output) || "",
          ms: seg.end ? seg.end.ms : null,
        });
      }
    });
    return rounds;
  }

  function traceToSteps(trace) {
    if (!Array.isArray(trace) || !trace.length) return null;
    return trace.map(function (t, i) {
      return {
        start: { step_id: "t" + i, name: t.tool || "?", arguments: t.arguments || "" },
        end: { step_id: "t" + i, name: t.tool || "?", output: t.output || "", ms: t.ms },
      };
    });
  }

