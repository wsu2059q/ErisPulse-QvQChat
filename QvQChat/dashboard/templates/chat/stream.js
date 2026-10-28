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

  function segSignature(seg) {
    // segment 内容指纹：只有内容变化的段才重建 DOM，保住其余段的展开状态
    if (seg.type === "text") {
      return "t" + String(seg.text || "").length + ":" + String(seg.text || "").slice(-48);
    }
    var endMark = seg.end
      ? "e" + (seg.end.ms != null ? seg.end.ms : "") + ":" + String(seg.end.output || "").length
      : "r";
    return "g" + (seg.start && seg.start.step_id ? seg.start.step_id : "") + endMark;
  }

  // 增量渲染文字/工具交错流：只重建内容变化的段，用户点开的工具详情不再被流式顶掉
  function renderSegments(container, segments, expMap) {
    var host = container.querySelector(".qvq-rounds");
    if (!host) {
      container.innerHTML = '<div class="qvq-rounds"></div>';
      host = container.querySelector(".qvq-rounds");
    }
    while (host.children.length > segments.length) host.removeChild(host.lastChild);
    while (host.children.length < segments.length) {
      var wrap = document.createElement("div");
      wrap.className = "qvq-seg";
      host.appendChild(wrap);
    }
    for (var i = 0; i < segments.length; i++) {
      var el = host.children[i];
      var seg = segments[i];
      var sig = segSignature(seg);
      if (el.__qvqSig === sig) continue;
      el.__qvqSig = sig;
      if (seg.type === "text") {
        el.innerHTML = '<div class="qvq-round-text">' + (mdRender(seg.text) || esc(seg.text)) + "</div>";
      } else {
        el.innerHTML = toolSegHtml(seg);
        bindStepToggles(el);
        restoreExpSteps(el, expMap);
      }
    }
  }

  function renderLiveNode(box, els, live) {
    var stick = nearBottom(box);
    // 重建前收集用户点开的工具详情与思考折叠状态
    var expSteps = collectExpSteps(els.stepsEl);
    var expSegSteps = collectExpSteps(els.textEl);
    var thinkEl = els.stepsEl.querySelector(".qvq-think");
    var thinkOpen = thinkEl ? thinkEl.hasAttribute("open") : null;

    // 首次渲染跟随 running 状态；之后尊重用户手动收起（thinkOpen === false）
    var thinkAutoOpen = live.status !== "running" ? "" : " open";
    var thinkAttr = thinkOpen === false ? "" : thinkAutoOpen;
    var thinkBlock = live.reasoning
      ? '<details class="qvq-think"' + thinkAttr + '><summary>' + esc(t("chat_thinking")) + '</summary><div class="qvq-think-body"></div></details>'
      : "";
    els.stepsEl.innerHTML = (thinkBlock || "") + stepsHtml(live.steps, true);
    if (live.reasoning) {
      var thinkBody = els.stepsEl.querySelector(".qvq-think-body");
      if (thinkBody) thinkBody.textContent = live.reasoning;
    }
    if (thinkOpen) {
      var thinkNow = els.stepsEl.querySelector(".qvq-think");
      if (thinkNow) thinkNow.setAttribute("open", "");
    }
    restoreExpSteps(els.stepsEl, expSteps);
    bindStepToggles(els.stepsEl);

    if (live.segments.length) {
      renderSegments(els.textEl, live.segments, expSegSteps);
    } else if (!live.text && live.started && !live.reasoning) {
      var secs = Math.max(0, Math.round((Date.now() - live.started) / 1000));
      els.textEl.innerHTML = '<div class="qvq-live-wait-row"><span class="qvq-dots"><span></span><span></span><span></span></span><span class="qvq-live-wait">' + esc(t("steps_running")) + " " + secs + "s</span></div>";
    } else {
      els.textEl.innerHTML = mdRender(live.text) || '<span class="qvq-cursor"></span>';
    }
    if (stick) box.scrollTop = box.scrollHeight;
  }


  function attachLive(snapshot) {
    if (activeLive && activeLive.session === snapshot.session) return;
    var epochAtAttach = chatEpoch;
    var box = el("qvq-chat-box");
    var live = { status: snapshot.status || "running", text: snapshot.text || "", reasoning: snapshot.reasoning || "", steps: snapshot.steps || [], error: snapshot.error || null };
/* 流式：SSE、实时输出节点、恢复挂载、消息派发 */
    setSessionBusy(snapshot.session, true);
    var els = makeLiveNode();
    box.appendChild(els.root);
    activeLive = { els: els, session: snapshot.session };
    live.started = (snapshot.started || 0) * 1000 || Date.now();
    live.segments = snapshot.segments || [];
    renderLiveNode(box, els, live);
    var poll = setInterval(function () {
      if (chatEpoch !== epochAtAttach || chatSession !== snapshot.session) {
        clearInterval(poll);
        els.root.remove();
        setSessionBusy(snapshot.session, false);
        activeLive = null;
        return;
      }
      api("/api/qvq/chat/live?session=" + encodeURIComponent(chatSession)).then(function (snap) {
        if (!snap || snap.status === "idle") {
          clearInterval(poll);
          els.root.remove();
          setSessionBusy(snapshot.session, false);
          activeLive = null;
          return;
        }
        live.status = snap.status;
        live.text = snap.text || "";
        live.reasoning = snap.reasoning || "";
        live.steps = snap.steps || [];
        live.segments = snap.segments || [];
        live.error = snap.error || null;
        renderLiveNode(box, els, live);
        if (snap.status !== "running") {
          clearInterval(poll);
          setSessionBusy(snapshot.session, false);
          setTimeout(function () {
            els.root.remove();
            activeLive = null;
            if (chatEpoch === epochAtAttach) {
              loadChatHistory();
              pumpQueue();
            }
          }, 400);
        }
      });
    }, 800);
  }

  function sendChat() {
    if (chatBusy) { queueCurrent(); return; }
    var input = el("qvq-chat-input");
    var text = input.value.trim();
    if (!text && !chatAtts.length) return;
    var atts = chatAtts.slice();
    chatAtts = [];
    input.value = "";
    input.style.height = "auto";
    renderAttach();
    dispatchMessage(text, atts);
  }


  function queueCurrent() {
    var input = el("qvq-chat-input");
    var text = input.value.trim();
    if (!text && !chatAtts.length) return;
    currentQueue().push({ text: text, atts: chatAtts.slice() });
    chatAtts = [];
    input.value = "";
    input.style.height = "auto";
    renderAttach();
    renderQueue();
    toast(t("queue_added"));
  }

  function pumpQueue() {
    if (chatBusy) return;
    var queue = currentQueue();
    if (!queue.length) return;
    var item = queue.shift();
    renderQueue();
    dispatchMessage(item.text, item.atts);
  }

  function dispatchMessage(text, atts) {
    var sessionAtStart = chatSession;
    var epochAtStart = chatEpoch;
    setSessionBusy(sessionAtStart, true);
    chatHistory.push({ role: "user", text: text, atts: atts, fresh: true });
    chatHistoryVersion++;
    renderChat({ stick: true });
    var box = el("qvq-chat-box");
    var live = { status: "running", text: "", reasoning: "", steps: [], segments: [], error: null, started: Date.now() };
    var els = makeLiveNode();
    box.appendChild(els.root);
    activeLive = { els: els, session: sessionAtStart };
    var waitTimer = startWaitTimer(box, els, live);
    renderWaitTimer(box, els, live);
    box.scrollTop = box.scrollHeight;
    var renderTimer = null;
    function scheduleText() {
      if (renderTimer) return;
      renderTimer = setTimeout(function () {
        renderTimer = null;
        renderLiveNode(box, els, live);
      }, 50);
    }
    function refreshSteps() {
      renderLiveNode(box, els, live);
    }
    var payload = {
      text: text,
      session: sessionAtStart,
      persona: chatPersona,
      skills: chatMentions.skills.slice(),
      mcp_tools: chatMentions.mcp.slice(),
      model: chatModel,
      temperature: chatEffort === "" ? null : parseFloat(chatEffort),
      attachments: atts.map(function (a) { return { name: a.name, mime: a.mime, data: a.data }; }),
    };
    var finished = false;
    var gotEvent = false; // 收到过任一 SSE 事件（meta 除外）即认为流已建立
    setSendStopping(true);
    function settle(reply, stepsOut, isErr) {
      if (finished) return;
      finished = true;
      if (renderTimer) { clearTimeout(renderTimer); renderTimer = null; }
      if (waitTimer) { clearInterval(waitTimer); waitTimer = null; }
      if (activeLive && activeLive.session === sessionAtStart) activeLive = null;
      els.root.remove();
      setSessionBusy(sessionAtStart, false);

      if (epochAtStart !== chatEpoch) return;
      var roundsOut = segmentsToRounds((typeof live !== "undefined" && live && live.segments) ? live.segments : []);
      chatHistory.push({ role: "assistant", text: reply, steps: stepsOut, rounds: roundsOut.length ? roundsOut : null, err: !!isErr });
      chatHistoryVersion++;
      renderChat({ stick: true });
      loadChatMeta();
      pumpQueue();
    }

    function reattach() {
      if (finished) return;
      api("/api/qvq/chat/live?session=" + encodeURIComponent(sessionAtStart)).then(function (snap) {
        if (epochAtStart !== chatEpoch || finished) return;
        if (snap && snap.status === "running") {
          // 先清 activeLive 再移除节点，否则 attachLive 的防重守卫会拦截后续挂载
          if (activeLive && activeLive.session === sessionAtStart) activeLive = null;
          els.root.remove();
          setSessionBusy(sessionAtStart, false);
          attachLive(snap);
        } else {
          settle("", [], false);
          loadChatHistory();
        }
      });
    }
    streamChat(payload, function (ev, data) {
      if (epochAtStart !== chatEpoch) return;
      if (ev !== "meta") gotEvent = true;
      if (ev === "delta" && data.t) {
        live.text += data.t;
        if (data.i != null) {
          while (live.segments.length <= data.i) live.segments.push({ type: "text", text: "" });
          if (live.segments[data.i].type !== "text") live.segments.splice(data.i, 0, { type: "text", text: "" });
          live.segments[data.i].text += data.t;
        } else {
          var lastSeg = live.segments[live.segments.length - 1];
          if (!lastSeg || lastSeg.type !== "text") live.segments.push({ type: "text", text: "" });
          live.segments[live.segments.length - 1].text += data.t;
        }
        scheduleText();
      } else if (ev === "reset") {
        live.text = "";
        live.reasoning = "";
        live.steps = [];
        live.segments = [];
        if (renderTimer) { clearTimeout(renderTimer); renderTimer = null; }
        renderLiveNode(box, els, live);
      } else if (ev === "reasoning" && data.t) {
        live.reasoning += data.t;
        scheduleText();
      } else if (ev === "tool") {
        if (data.phase === "start") {
          live.steps.push({ start: data });
          live.segments.push({ type: "tool", start: data });
        } else {
          var match = null;
          for (var i = live.steps.length - 1; i >= 0; i--) {
            if (live.steps[i].start && live.steps[i].start.step_id === data.step_id && !live.steps[i].end) { match = live.steps[i]; break; }
          }
          if (!match) {
            for (var j = live.steps.length - 1; j >= 0; j--) { if (!live.steps[j].end) { match = live.steps[j]; break; } }
          }
          if (match) match.end = data;
          var segMatch = null;
          for (var k = live.segments.length - 1; k >= 0; k--) {
            var sg = live.segments[k];
            if (sg.type === "tool" && sg.start && sg.start.step_id === data.step_id && !sg.end) { segMatch = sg; break; }
          }
          if (!segMatch) {
            for (var m3 = live.segments.length - 1; m3 >= 0; m3--) {
              var sg2 = live.segments[m3];
              if (sg2.type === "tool" && !sg2.end) { segMatch = sg2; break; }
            }
          }
          if (segMatch) segMatch.end = data;
        }
        refreshSteps();
      } else if (ev === "error") {
        if (data.error === "cancelled") {
          settle(live.text || t("chat_cancelled"), live.steps, false);
        } else {
          settle(data.error || t("chat_err"), live.steps, true);
          toast(data.error || t("chat_err"), true);
        }
      } else if (ev === "done") {
        settle((data.reply != null ? data.reply : live.text) || "…", live.steps, false);
      }
    }).then(function (result) {
      if (result && result.__busy) {
        toast(t("chat_busy"), true);
        reattach();
        return;
      }
      if (!finished && result === undefined) {

        api("/api/qvq/chat/live?session=" + encodeURIComponent(sessionAtStart)).then(function (snap) {
          if (snap && snap.status === "running") { reattach(); return; }
          if (snap && snap.reply != null) settle(snap.reply, snap.steps || live.steps, false);
          else if (snap && snap.error) settle(snap.error, snap.steps || live.steps, true);
          else settle(live.text || "…", live.steps, false);
        });
      }
    }).catch(function () {
      if (finished) return;
      // 收到过事件说明服务端任务已在跑：断流只做快照重挂，绝不能重发造成双跑
      if (gotEvent) { reattach(); return; }
      api("/api/qvq/chat", "POST", payload).then(function (data) {
        if (data && data.__http === 409) { toast(t("chat_busy"), true); reattach(); return; }
        if (data && (data.error || data.__http === 401)) {
          settle((data && data.error) || t("chat_err"), [], true);
          toast((data && data.error) || t("chat_err"), true);
        } else if (data && data.reply != null) {
          settle(data.reply, [], false);
        } else {
          settle(live.text || t("chat_err"), [], true);
        }
      }, function () {
        settle(live.text || t("chat_err"), [], true);
      });
    });
  }

