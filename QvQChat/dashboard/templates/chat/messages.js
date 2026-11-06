/* 消息流：历史按需加载（尾部窗口 + 上滚补更早）、渲染、原地编辑与附件 */
  var historySeq = 0;
  var chatLoading = false;
  var loadingSession = ""; // 正在加载的会话（防同会话重复请求叠加）
  // 重渲染期间屏蔽 scroll 监听的"上翻加载"判定（innerHTML 替换会瞬时归零 scrollTop）
  var suppressScrollLoad = false;
  // 最近一次已加载历史的会话
  var lastHistorySession = "";
  // 首屏/上翻步长（条）：历史单条可能含图片 base64 与工具明细（几十 KB）
  var HISTORY_PAGE = 12;
  // 已加载窗口在服务端历史中的绝对起点与总数（>0 表示上方还有更早消息）
  var chatWindowStart = 0;
  var chatTotal = 0;

  var chatHistoryVersion = 0;

  function mapServerMessage(m, start, i) {
    // 服务端消息 → 本地条目的唯一映射：idx 必须是绝对索引，rounds 必须透传
    var atts = (m.atts || []).map(function (a) {
      return { isImage: !!a.isImage, name: a.name || "image", data: a.data || "", mime: a.mime || "image/png" };
    });
    return {
      role: m.role, text: contentText(m.content), idx: start + i,
      ts: m.ts || 0,
      steps: traceToSteps(m.trace),
      rounds: Array.isArray(m.rounds) ? m.rounds : null,
      atts: atts,
    };
  }

  function applyHistoryWindow(data) {
    var msgs = (data && data.messages) || [];
    var start = (data && data.start) || 0;
    chatTotal = (data && data.total) || msgs.length;
    chatWindowStart = start;
    chatHistory = [];
    msgs.forEach(function (m, i) {
      if (!m || typeof m !== "object") return;
      if (m.role === "user" || m.role === "assistant") chatHistory.push(mapServerMessage(m, start, i));
    });
  }

  function loadChatHistory() {
// 同一会话已有加载在飞：直接返回，不再叠加请求
    if (chatLoading && loadingSession === chatSession) return Promise.resolve();
    var seq = ++historySeq;
    var sessionAtRequest = chatSession;
    var epochAtRequest = chatEpoch;
    var versionAtRequest = chatHistoryVersion;
    chatLoading = true;
    loadingSession = sessionAtRequest;
    renderChat();
    return api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(sessionAtRequest) + "&limit=" + HISTORY_PAGE).then(function (data) {
      if (seq !== historySeq) return; // 新请求已接管本会话的加载
      chatLoading = false;
      loadingSession = "";
      if (data && data.__http >= 400) {
        toast(data.error || ("HTTP " + data.__http), true);
        renderChat();
        return;
      }
      if (epochAtRequest !== chatEpoch || sessionAtRequest !== chatSession || versionAtRequest !== chatHistoryVersion) {
        renderChat();
        return;
      }
      applyHistoryWindow(data);
      lastHistorySession = sessionAtRequest; // 记录已加载会话：再次进入同一会话不必重拉
      renderChat({ stick: true });
    }, function () {
      if (seq !== historySeq) return;
      chatLoading = false;
      loadingSession = "";
      renderChat();
    });
  }

  var loadingOlder = false;
  function loadOlderMessages() {
    if (chatWindowStart <= 0 || chatLoading || loadingOlder) return;
    loadingOlder = true;
    var seq = historySeq;
    var sessionAtRequest = chatSession;
    var epochAtRequest = chatEpoch;
    var versionAtRequest = chatHistoryVersion;
    var box = el("qvq-chat-box");
    var prevH = box ? box.scrollHeight : 0;
    var prevTop = box ? box.scrollTop : 0;
    var start = Math.max(0, chatWindowStart - HISTORY_PAGE);
    api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(sessionAtRequest) + "&start=" + start + "&limit=" + (chatWindowStart - start)).then(function (data) {
      loadingOlder = false;
      if (seq !== historySeq || epochAtRequest !== chatEpoch || sessionAtRequest !== chatSession) return;
      if (versionAtRequest !== chatHistoryVersion) return;
      var msgs = (data && data.messages) || [];
      var prepend = [];
      msgs.forEach(function (m, i) {
        if (!m || typeof m !== "object") return;
        if (m.role === "user" || m.role === "assistant") prepend.push(mapServerMessage(m, (data && data.start) || start, i));
      });
      if (prepend.length) {
        chatHistory = prepend.concat(chatHistory);
        chatWindowStart = (data && data.start) || start;
        renderChat();
        if (box) box.scrollTop = box.scrollHeight - prevH + prevTop;
      }
    }, function () {
      loadingOlder = false;
    });
  }

  var unreadCount = 0;
  var titleBase = document.title || "QvQChat";

  function updateUnreadTitle() {
    document.title = unreadCount > 0 ? "(" + unreadCount + ") " + titleBase : titleBase;
  }

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      unreadCount = 0;
      updateUnreadTitle();
    }
  });

  var CHIP_KEYS = ["chat_chip_1", "chat_chip_2", "chat_chip_3", "chat_chip_4"];
  var HERO_SVG = "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><rect x='4' y='7' width='16' height='12' rx='3' stroke-dasharray='3 2'/><circle cx='9' cy='13' r='1.2' fill='currentColor'/><circle cx='15' cy='13' r='1.2' fill='currentColor'/><path d='M12 7V4'/><circle cx='12' cy='3' r='1' fill='currentColor'/></svg>";

  

  function renderChat(opts) {
    var stick = !!(opts && opts.stick);
    var box = el("qvq-chat-box");
    var main = document.querySelector(".qvq-chat-main");
    var chips = el("qvq-chat-chips");
    // 加载中且历史为空、无活跃直播：显示加载态
    // 已有历史内容时保留现有 DOM，不替换
    if (chatLoading && !chatHistory.length && !(activeLive && activeLive.session === chatSession)) {
      box.removeAttribute("data-html");
      if (main) main.classList.remove("is-empty");
      if (chips) { chips.style.display = "none"; chips.innerHTML = ""; }
      box.innerHTML = '<div class="qvq-chat-loading">' + HERO_SVG + '<span class="qvq-chat-loading-tx">QvQ Chat</span></div>';
      return;
    }
    if (!chatHistory.length) {

      
      box.removeAttribute("data-html");
      if (main) main.classList.add("is-empty");
      if (chips) {
        chips.style.display = "flex";
        chips.innerHTML = CHIP_KEYS.map(function (k) {
          return '<button type="button" class="qvq-chat-chip">' + esc(t(k)) + "</button>";
        }).join("");
        chips.querySelectorAll(".qvq-chat-chip").forEach(function (chip, i) {
          chip.onclick = function () {
            var input = el("qvq-chat-input");
            if (!input || chatBusy) return;
            input.value = t(CHIP_KEYS[i]);
            input.dispatchEvent(new Event("input"));
            sendChat();
          };
        });
      }
      box.innerHTML = '<div class="qvq-chat-hero"><div class="qvq-chat-hero-ico">' + HERO_SVG + "</div>" +
        '<div class="qvq-chat-hero-title">' + esc(heroTitle()) + "</div>" +
        '<div class="qvq-chat-hero-sub">' + esc(t("chat_hero_sub")) + "</div></div>";
      return;
    }
    if (main) main.classList.remove("is-empty");
    if (chips) {
      chips.style.display = "none";
      chips.innerHTML = "";
    }
    var chatHtmlKey = chatSession + "::" + chatWindowStart + "::" + chatHistory.map(function (m) {
      return [m.role, m.text, m.steps ? m.steps.length : 0, (m.atts || []).length,
        m.rounds ? m.rounds.map(function (r) { return (r.text || "").length + "." + (r.tools || []).length; }).join(",") : "-",
        m.fresh ? 1 : 0, m.err ? 1 : 0].join("");
    }).join("");
    if (box.getAttribute("data-html") === chatHtmlKey) {
      bindMdCopy(box);
      return;
    }
    box.setAttribute("data-html", chatHtmlKey);
    var build = chatHistory.map(function (m, i) {
      var inner = "";
      (m.atts || []).forEach(function (a) {
        if (a.isImage) {
          inner += '<img class="qvq-msg-img" data-idx="' + i + '" src="' + a.data + '" alt=""/>';
        } else {
          inner += '<span class="qvq-msg-file"><i class="qvq-file-ico">' + FILE_ICON_SVG + "</i>" + esc(a.name) + "</span>";
        }
      });
      var body;
      if (m.role === "assistant" && m.rounds && m.rounds.length) {
        body = '<div class="qvq-rounds">' + renderSerial(roundsToItems(m.rounds)) + "</div>";
      } else {
        body = m.role === "user" ? esc(m.text) : (mdRender(m.text) || esc(m.text));
      }
      var stepsBlock = m.role === "assistant" && !m.rounds && m.steps && m.steps.length ? stepsHtml(m.steps, false) : "";
      var acts = m.role === "user" && m.idx != null
        ? '<div class="qvq-msg-acts">' +
          '<button type="button" data-copy-msg="' + i + '" title="' + esc(t("copy")) + '"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg></button>' +
          '<button type="button" data-edit-msg="' + i + '" title="' + esc(t("edit")) + '"><svg viewBox="0 0 24 24"><path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg></button>' +
          "</div>"
        : "";
      var freshCls = m.fresh ? " qvq-msg-new" : "";
      var timeAttr = m.ts ? ' title="' + esc(new Date(m.ts * 1000).toLocaleString()) + '"' : "";
      if (m.role === "user") {

        return '<div class="qvq-msg-wrap"' + timeAttr + '><div class="qvq-msg me' + freshCls + '">' + inner + body + '</div>' + acts + "</div>";
      }
// AI 消息操作条：复制所有；重新生成仅最后一条
      var lastBot = -1;
      for (var bi = 0; bi < chatHistory.length; bi++) {
        if (chatHistory[bi].role === "assistant") lastBot = bi;
      }
      var botActs = '<div class="qvq-msg-acts bot">' +
        '<button type="button" data-copy-msg="' + i + '" title="' + esc(t("copy")) + '"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg></button>' +
        (i === lastBot && !chatBusy ? '<button type="button" data-regen="1" title="' + esc(t("regen")) + '"><svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 3v6h-6"/></svg></button>' : "") +
        "</div>";
      return '<div class="qvq-msg-wrap bot"' + timeAttr + '><div class="qvq-msg bot' + freshCls + '">' + stepsBlock + inner + body + "</div>" + botActs + "</div>";
    });
    var prevTop = stick ? 0 : box.scrollTop;
    suppressScrollLoad = true; // 重建 DOM 前屏蔽"到底部即加载更早"的误判
    box.innerHTML = build.join("");
    box.querySelectorAll(".qvq-msg-img").forEach(function (img) {
      img.onclick = function () {
        var m = chatHistory[parseInt(img.getAttribute("data-idx"), 10)] || {};
        var att = ((m.atts || []).filter(function (a) { return a.isImage; })[0]) || {};
        openImageViewer(att.name || "image", att.data);
      };
    });
    var regenBtn = box.querySelector("[data-regen]");
    if (regenBtn) {
      regenBtn.onclick = function () {
        regenBtn.disabled = true;
        api("/api/qvq/session/regenerate", "POST", { chat_key: chatSession }).then(function (r) {
          regenBtn.disabled = false;
          if (r && r.ok && r.text) {
            loadChatHistory();
            var input = el("qvq-chat-input");
            if (input) { input.value = r.text; input.dispatchEvent(new Event("input")); }
            sendChat();
          } else if (r && r.__http === 409) {
            toast((r && r.error) || "busy", true);
          } else {
            toast((r && r.error) || "error", true);
          }
        }, function () { regenBtn.disabled = false; });
      };
    }
    box.querySelectorAll("[data-copy-msg]").forEach(function (btn) {
      btn.onclick = function () {
        var m = chatHistory[parseInt(btn.getAttribute("data-copy-msg"), 10)] || {};
        copyText(m.text || "");
        var old = btn.getAttribute("title");
        btn.setAttribute("title", t("copied"));
        setTimeout(function () { btn.setAttribute("title", old); }, 1200);
      };
    });
    box.querySelectorAll("[data-edit-msg]").forEach(function (btn) {
      btn.onclick = function () { openMsgEditor(btn); };
    });
    bindStepToggles(box);
    bindMdCopy(box);
    var freshNow = 0;
    chatHistory.forEach(function (m2) { if (m2.fresh) { freshNow++; m2.fresh = false; } });
    if (freshNow > 0 && document.hidden) {
      unreadCount += freshNow;
      updateUnreadTitle();
    }

    if (chatBusy && activeLive && activeLive.session === chatSession && !box.querySelector(".qvq-msg.live")) {
      box.appendChild(activeLive.els.root);
    }
    // 只在显式要求贴底、或首屏（原本是空的）时跳底；用户向上翻阅时保留位置
    if (stick || !prevTop) box.scrollTop = box.scrollHeight;
    else box.scrollTop = prevTop;
    // 下一帧再恢复监听（挂载后浏览器可能补发一次 scroll）
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(function () { suppressScrollLoad = false; });
    } else {
      suppressScrollLoad = false;
    }
  }


  // 图片查看器：滚轮缩放/双击复位/旋转
  function openImageViewer(name, src) {
    openModal(name, "<div class='qvq-img-viewer'>" +
      "<div class='qvq-img-stage'><img src='" + src + "' alt=''/></div>" +
      "<div class='qvq-img-bar'>" +
      "<button type='button' data-z='in' title='+'>+</button>" +
      "<button type='button' data-z='out' title='-'>−</button>" +
      "<button type='button' data-rot='1' title='↻'>↻</button>" +
      "<button type='button' data-z='reset' title='⤾'>⤾</button>" +
      "</div></div>");
    var body = el("qvq-modal-body");
    var img = body.querySelector(".qvq-img-stage img");
    var scale = 1, rotate = 0;
    function apply() {
      img.style.transform = "scale(" + scale + ") rotate(" + rotate + "deg)";
    }
    body.querySelectorAll("[data-z]").forEach(function (btn) {
      btn.onclick = function () {
        var z = btn.getAttribute("data-z");
        if (z === "in") scale = Math.min(6, scale * 1.25);
        else if (z === "out") scale = Math.max(0.2, scale / 1.25);
        else { scale = 1; rotate = 0; }
        apply();
      };
    });
    var rotBtn = body.querySelector("[data-rot]");
    if (rotBtn) rotBtn.onclick = function () { rotate = (rotate + 90) % 360; apply(); };
    img.onwheel = function (e) {
      e.preventDefault();
      scale = Math.min(6, Math.max(0.2, scale * (e.deltaY < 0 ? 1.12 : 0.89)));
      apply();
    };
    img.ondblclick = function () { scale = 1; rotate = 0; apply(); };
  }

  function closeMsgEditor() {
    document.querySelectorAll(".qvq-msg-wrap.editing").forEach(function (w) {
      w.classList.remove("editing");
      var ed = w.querySelector(".qvq-msg-editor");
      if (ed) ed.remove();
    });
  }

  function openMsgEditor(btn) {
    var i = parseInt(btn.getAttribute("data-edit-msg"), 10);
    var m = chatHistory[i];
    if (!m || m.idx == null) return;
    var wrapNode = btn.closest(".qvq-msg-wrap");
    if (!wrapNode) return;
    if (wrapNode.classList.contains("editing")) { closeMsgEditor(); return; }
    closeMsgEditor();
    wrapNode.classList.add("editing");
    var atts = (m.atts || []).slice();
    var ed = document.createElement("div");
    ed.className = "qvq-msg-editor";
    ed.innerHTML =
      '<div class="qvq-ed-atts"></div>' +
      '<textarea class="qvq-chat-text" rows="2"></textarea>' +
      '<div class="qvq-composer-bar">' +
      '<button type="button" class="qvq-icon-btn" data-ed-add title="' + esc(t("chat_attach")) + '"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg></button>' +
      '<input type="file" multiple style="display:none"/>' +
      '<button type="button" class="qvq-icon-btn danger" data-ed-trunc title="' + esc(t("chat_edit_cut")) + '"><svg viewBox="0 0 24 24"><path d="M12 4v11"/><path d="M7 11l5 5 5-5"/><path d="M5 20h14"/></svg></button>' +
      '<span class="qvq-composer-spacer"></span>' +
      '<button type="button" class="qvq-btn small ghost" data-ed-save>' + esc(t("chat_edit_only")) + "</button>" +
      '<button type="button" class="qvq-btn small" data-ed-send>' + esc(t("chat_edit_send")) + "</button>" +
      '<button type="button" class="qvq-icon-btn" data-ed-cancel title="' + esc(t("cancel")) + '"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>' +
      "</div>";
    var ta = ed.querySelector("textarea");
    ta.value = m.text;
    ta.addEventListener("input", function () {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 220) + "px";
    });
    ta.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      // Ctrl/Cmd+Enter = 保存并重新发送；仅保存用左侧文字按钮
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); saveAndSend(); }
    });

    function renderAtts() {
      var row = ed.querySelector(".qvq-ed-atts");
      row.style.display = atts.length ? "flex" : "none";
      row.innerHTML = atts.map(function (a, k) {
        var body = a.isImage ? '<img src="' + a.data + '" alt=""/>' : '<i class="qvq-file-ico">' + FILE_ICON_SVG + "</i><span>" + esc(a.name) + "</span>";
        return '<span class="qvq-ed-att">' + body +
          '<button type="button" data-ed-rm="' + k + '" title="' + esc(t("del")) + '"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></span>';
      }).join("");
      row.querySelectorAll("[data-ed-rm]").forEach(function (b) {
        b.onclick = function () {
          atts.splice(parseInt(b.getAttribute("data-ed-rm"), 10), 1);
          renderAtts();
        };
      });
    }

    var fileInput = ed.querySelector("input[type=file]");
    ed.querySelector("[data-ed-add]").onclick = function () { fileInput.click(); };
    fileInput.onchange = function () {
      handleFiles(fileInput.files, atts, renderAtts);
      fileInput.value = "";
    };

    function close() {
      wrapNode.classList.remove("editing");
      ed.remove();
    }
    ed.querySelector("[data-ed-cancel]").onclick = close;

    function payloadOf() {
      return {
        chat_key: chatSession,
        index: m.idx,
        content: ta.value,
        attachments: atts.map(function (a) {
          return { name: a.name, mime: a.mime || (a.isImage ? "image/png" : "application/octet-stream"), data: a.data };
        }),
      };
    }

    // ① 仅保存：只改这条消息的文本/附件，不动后续对话
    function saveOnly() {
      api("/api/qvq/session/context/edit", "POST", payloadOf()).then(function (data) {
        if (data && data.error) { toast(data.error, true); return; }
        m.text = ta.value;
        chatHistoryVersion++;
        close();
        renderChat();
        toast(t("saved"));
      });
    }

    // ② 保存并重新发送：丢弃这条及其之后的消息，用新内容重跑
    function saveAndSend() {
      var text = ta.value.trim();
      if (!text && !atts.length) { toast(t("chat_empty_send"), true); return; }
      api("/api/qvq/session/rewind", "POST", { chat_key: chatSession, index: m.idx }).then(function (r) {
        if (!r || r.error) { toast((r && r.error) || "error", true); return; }
        var localIdx = m.idx - chatWindowStart;
        chatHistory = chatHistory.slice(0, Math.max(0, localIdx));
        chatTotal = chatHistory.length + chatWindowStart;
        chatHistoryVersion++;
        close();
        renderChat({ stick: true });
        chatAtts = atts.map(function (a) {
          return { isImage: !!a.isImage, name: a.name, data: a.data, mime: a.mime };
        });
        renderAttach();
        var input = el("qvq-chat-input");
        if (input) { input.value = text; input.dispatchEvent(new Event("input")); }
        sendChat();
      });
    }

    // ③ 删除这条及之后（不重发）
    function cutFromHere() {
      confirmDialog(t("chat_edit_cut_confirm")).then(function (ok) {
        if (!ok) return;
        api("/api/qvq/session/rewind", "POST", { chat_key: chatSession, index: m.idx }).then(function (r) {
          if (!r || r.error) { toast((r && r.error) || "error", true); return; }
          var localIdx = m.idx - chatWindowStart;
          chatHistory = chatHistory.slice(0, Math.max(0, localIdx));
          chatTotal = chatHistory.length + chatWindowStart;
          chatHistoryVersion++;
          close();
          renderChat({ stick: true });
          toast(t("deleted"));
        });
      });
    }

    ed.querySelector("[data-ed-save]").onclick = saveOnly;
    ed.querySelector("[data-ed-send]").onclick = saveAndSend;
    ed.querySelector("[data-ed-trunc]").onclick = cutFromHere;

    wrapNode.appendChild(ed);
    renderAtts();
    ta.focus();
    ta.style.height = Math.min(ta.scrollHeight, 220) + "px";
  }

  function isTextFile(file) {
    if (file.type && file.type.indexOf("text/") === 0) return true;
    if (file.type === "application/json") return true;
    return /\.(txt|md|markdown|json|csv|tsv|log|ya?ml|toml|ini|cfg|conf|py|js|ts|jsx|tsx|html?|css|scss|sh|bat|ps1|c|cpp|h|hpp|java|kt|go|rs|rb|php|sql|xml)$/i.test(file.name || "");
  }


  function handleFiles(files, targetList, onDone) {
    var list = targetList || chatAtts;
    var after = onDone || renderAttach;
    Array.prototype.slice.call(files).forEach(function (file) {
      if (!file) return;
      if (/^image\//.test(file.type)) {
        if (list.filter(function (a) { return a.isImage; }).length >= 3) {
          toast(t("chat_img_limit"), true);
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          toast(t("chat_file_bad") + " " + file.name + " (>5MB)", true);
          return;
        }
        var reader = new FileReader();
        reader.onload = function () {
          list.push({ name: file.name, mime: file.type, data: String(reader.result), isImage: true });
          after();
        };
        reader.readAsDataURL(file);
      } else if (isTextFile(file)) {
        if (file.size > 1024 * 1024) {
          toast(t("chat_file_bad") + " " + file.name, true);
          return;
        }
        var r2 = new FileReader();
        r2.onload = function () {
          list.push({ name: file.name, mime: file.type || "text/plain", data: String(r2.result), isImage: false });
          after();
        };
        r2.readAsText(file);
      } else {

        if (file.size > 20 * 1024 * 1024) {
          toast(t("chat_file_big") + " " + file.name, true);
          return;
        }
        var r3 = new FileReader();
        r3.onload = function () {
          list.push({ name: file.name, mime: file.type || "application/octet-stream", data: String(r3.result), isImage: false });
          after();
        };
        r3.readAsDataURL(file);
      }
    });
  }

  function renderAttach() {
    var box = el("qvq-chat-attach");
    if (!box) return;
    box.innerHTML = chatAtts.map(function (a, i) {
      return '<div class="qvq-att">' + (a.isImage ? '<img src="' + a.data + '" alt=""/>' : '<span class="qvq-att-ico">' + FILE_ICON_SVG + "</span>") +
        "<span>" + esc(a.name) + "</span>" +
        '<button type="button" data-rm="' + i + '" aria-label="remove"><svg viewBox=\'0 0 24 24\'><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>';
    }).join("");
    box.querySelectorAll("button[data-rm]").forEach(function (btn) {
      btn.onclick = function () {
        chatAtts.splice(parseInt(btn.getAttribute("data-rm"), 10), 1);
        renderAttach();
      };
    });
  }

  function setSendStopping(stopping) {
    var btn = el("qvq-chat-send");
    if (!btn) return;
    btn.classList.toggle("stopping", stopping);
    btn.title = t(stopping ? "chat_stop" : "chat_send");
    btn.innerHTML = stopping
      ? '<svg class="ico-stop" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>'
      : '<svg class="ico-send" viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  }

  // 有可见内容（正文/思考/工具段）时返回 true，不显示等待行
  function hasLiveContent(live) {
    return !!(live.text || live.reasoning || (live.segments && live.segments.length));
  }

  // 等待行只更新秒数文本，不重建整块
  function renderWaitRow(els, secs) {
    var row = els.textEl.querySelector(".qvq-live-wait-row");
    if (!row) {
      els.textEl.innerHTML = '<div class="qvq-live-wait-row"><span class="qvq-dots"><span></span><span></span><span></span></span><span class="qvq-live-wait"></span></div>';
      row = els.textEl.querySelector(".qvq-live-wait-row");
    }
    var label = row ? row.querySelector(".qvq-live-wait") : null;
    if (label) label.textContent = t("steps_running") + " " + secs + "s";
  }

  function renderWaitTimer(box, els, live) {
    if (live.status !== "running" || hasLiveContent(live)) return;
    var secs = Math.max(0, Math.round((Date.now() - (live.started || Date.now())) / 1000));
    renderWaitRow(els, secs);
  }

  function startWaitTimer(box, els, live) {
    var timer = setInterval(function () {
      if (!live.started || live.status !== "running" || hasLiveContent(live)) { clearInterval(timer); return; }
      renderWaitTimer(box, els, live);
    }, 1000);
    return timer;
  }

  function cancelChat() {
    api("/api/qvq/chat/cancel", "POST", { session: chatSession }).catch(function () {});
  }


