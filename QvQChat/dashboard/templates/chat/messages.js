  var historySeq = 0;
  var chatLoading = false;

  var chatHistoryVersion = 0;
  function loadChatHistory() {
    var seq = ++historySeq;
    var sessionAtRequest = chatSession;
    var epochAtRequest = chatEpoch;
    var versionAtRequest = chatHistoryVersion;
    chatLoading = true;
    renderChat();
    return api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(sessionAtRequest)).then(function (data) {

      if (seq !== historySeq || epochAtRequest !== chatEpoch || sessionAtRequest !== chatSession) return;
      if (versionAtRequest !== chatHistoryVersion) return;
      chatLoading = false;
      var msgs = (data && data.messages) || [];
      chatHistory = [];
      msgs.forEach(function (m, idx) {
        if (!m || typeof m !== "object") return;
        if (m.role === "user" || m.role === "assistant") {
          var atts = (m.atts || []).map(function (a) {
            return { isImage: !!a.isImage, name: a.name || "image", data: a.data || "", mime: a.mime || "image/png" };
          });
          chatHistory.push({
            role: m.role, text: contentText(m.content), idx: idx,
            steps: traceToSteps(m.trace),
            rounds: Array.isArray(m.rounds) ? m.rounds : null,
            atts: atts,
          });
        }
      });
      renderChat();
    }, function () {
      if (seq !== historySeq) return;
      chatLoading = false;
      renderChat();
    }, function () {
      chatLoading = false;
      renderChat();
    });
  }

  var CHIP_KEYS = ["chat_chip_1", "chat_chip_2", "chat_chip_3", "chat_chip_4"];
  var HERO_SVG = "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><rect x='4' y='7' width='16' height='12' rx='3' stroke-dasharray='3 2'/><circle cx='9' cy='13' r='1.2' fill='currentColor'/><circle cx='15' cy='13' r='1.2' fill='currentColor'/><path d='M12 7V4'/><circle cx='12' cy='3' r='1' fill='currentColor'/></svg>";

  function renderChat() {
    var box = el("qvq-chat-box");
    var main = document.querySelector(".qvq-chat-main");
    var chips = el("qvq-chat-chips");
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
    if (chatLoading) {
      box.removeAttribute("data-html");
      box.innerHTML = '<div class="qvq-chat-loading">' + HERO_SVG + '<span class="qvq-chat-loading-tx">QvQ Chat</span></div>';
      return;
    }
    var chatHtmlKey = chatSession + "::" + chatHistory.map(function (m) { return [m.role, m.text, m.steps ? m.steps.length : 0, (m.atts || []).length].join("\u0001"); }).join("\u0002");
    if (box.getAttribute("data-html") === chatHtmlKey) {
      bindMdCopy(box);
      return;
    }
    box.setAttribute("data-html", chatHtmlKey);
    box.innerHTML = chatHistory.map(function (m, i) {
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
      if (m.role === "user") {

        return '<div class="qvq-msg-wrap"><div class="qvq-msg me' + freshCls + '">' + inner + body + '</div>' + acts + "</div>";
      }
      return '<div class="qvq-msg bot' + freshCls + '">' + stepsBlock + inner + body + "</div>";
    }).join("");
    box.querySelectorAll(".qvq-msg-img").forEach(function (img) {
      img.onclick = function () {
        var m = chatHistory[parseInt(img.getAttribute("data-idx"), 10)] || {};
        var att = ((m.atts || []).filter(function (a) { return a.isImage; })[0]) || {};
        openModal(att.name || "image", '<img style="max-width:100%;border-radius:12px" src="' + att.data + '" alt=""/>');
      };
    });
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
    chatHistory.forEach(function (m2) { if (m2.fresh) m2.fresh = false; });

    if (chatBusy && activeLive && activeLive.session === chatSession && !box.querySelector(".qvq-msg.live")) {
      box.appendChild(activeLive.els.root);
    }
    box.scrollTop = box.scrollHeight;
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
      '<span class="qvq-composer-spacer"></span>' +
      '<button type="button" class="qvq-icon-btn" data-ed-cancel title="' + esc(t("cancel")) + '"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>' +
      '<button type="button" class="qvq-composer-send" data-ed-save title="' + esc(t("save")) + '"><svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>' +
      "</div>";
    var ta = ed.querySelector("textarea");
    ta.value = m.text;
    ta.addEventListener("input", function () {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 220) + "px";
    });
    ta.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save(); }
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
    function save() {
      var payload = {
        chat_key: chatSession,
        index: m.idx,
        content: ta.value,

        attachments: atts.map(function (a) {
          return { name: a.name, mime: a.mime || (a.isImage ? "image/png" : "application/octet-stream"), data: a.data };
        }),
      };
      api("/api/qvq/session/context/edit", "POST", payload).then(function (data) {
        if (data && data.error) { toast(data.error, true); return; }
        toast(t("saved"));
        close();
        loadChatHistory();
      });
    }
    ed.querySelector("[data-ed-save]").onclick = save;

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

  function renderWaitTimer(box, els, live) {
    if (live.status !== "running" || live.text) return;
    var secs = Math.max(0, Math.round((Date.now() - (live.started || Date.now())) / 1000));
    els.textEl.innerHTML = '<span class="qvq-live-wait">' + esc(t("steps_running")) + " " + secs + "s</span>";
  }

  function startWaitTimer(box, els, live) {
    var timer = setInterval(function () {
      if (!live.started || live.status !== "running" || live.text) { clearInterval(timer); return; }
      renderWaitTimer(box, els, live);
    }, 1000);
    return timer;
  }

  function cancelChat() {
    api("/api/qvq/chat/cancel", "POST", { session: chatSession }).catch(function () {});
  }


  function streamChat(payload, onEvent) {
    var headers = { "Content-Type": "application/json" };
    var token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch("/QvQChat/api/qvq/chat/stream", {
      method: "POST",
      headers: headers,
      body: JSON.stringify(payload),
    }).then(function (resp) {
      if (resp.status === 409) return { __busy: true };
      if (!resp.ok || !resp.body) throw new Error("stream unavailable");
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buf = "";
      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) return;
          buf += decoder.decode(chunk.value, { stream: true });
          var idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            var block = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            var ev = "message", data = "";
            block.split("\n").forEach(function (line) {
              if (line.indexOf("event:") === 0) ev = line.slice(6).trim();
              else if (line.indexOf("data:") === 0) data += line.slice(5).trim();
            });
            if (!data) continue;
            try { onEvent(ev, JSON.parse(data)); } catch (e) { (window.__pumpErrs = window.__pumpErrs || []).push(String((e && e.stack) || e)); }
          }
          return pump();
        });
      }
      return pump();
    });
  }

  function nearBottom(box) {
    return box.scrollHeight - box.scrollTop - box.clientHeight < 120;
  }


  function makeLiveNode() {
    var root = document.createElement("div");
    root.className = "qvq-msg bot live";
    root.innerHTML = '<div class="qvq-live-steps"></div><div class="qvq-live-text"><span class="qvq-cursor"></span></div>';
    return {
      root: root,
      stepsEl: root.querySelector(".qvq-live-steps"),
      textEl: root.querySelector(".qvq-live-text"),
      timer: null,
    };
  }

  function renderLiveNode(box, els, live) {
    var stick = nearBottom(box);
    els.stepsEl.innerHTML = stepsHtml(live.steps, true);
    bindStepToggles(els.stepsEl);
    if (live.segments.length) {
      els.textEl.innerHTML = '<div class="qvq-rounds">' + renderSerial(live.segments) + "</div>";
      bindStepToggles(els.textEl);
    } else if (!live.text && live.started) {
      var secs = Math.max(0, Math.round((Date.now() - live.started) / 1000));
      els.textEl.innerHTML = '<span class="qvq-live-wait">' + esc(t("steps_running")) + " " + secs + "s</span>";
    } else {
      els.textEl.innerHTML = mdRender(live.text) || '<span class="qvq-cursor"></span>';
    }
    if (stick) box.scrollTop = box.scrollHeight;
  }


  function attachLive(snapshot) {
    if (activeLive && activeLive.session === snapshot.session) return;
    var epochAtAttach = chatEpoch;
    var box = el("qvq-chat-box");
    var live = { status: snapshot.status || "running", text: snapshot.text || "", steps: snapshot.steps || [], error: snapshot.error || null };
