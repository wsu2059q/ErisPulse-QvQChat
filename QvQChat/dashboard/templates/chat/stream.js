  // 通用 SSE 读取：POST 聊天流与 GET 直播订阅共用一套解析
  function readSSE(resp, onEvent) {
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
  }

  function authHeaders(extra) {
    var headers = extra || {};
    var token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    return headers;
  }

  function streamChat(payload, onEvent) {
    return fetch("/QvQChat/api/qvq/chat/stream", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    }).then(function (resp) {
      if (resp.status === 409) return { __busy: true };
      if (!resp.ok || !resp.body) throw new Error("stream unavailable");
      return readSSE(resp, onEvent);
    });
  }

  // 单条常驻 SSE 订阅服务端直播流：先收到 snapshot，再逐条收增量
  function streamLive(session, onEvent, signal) {
    var opts = { headers: authHeaders({}) };
    if (signal) opts.signal = signal;
    return fetch("/QvQChat/api/qvq/chat/live/subscribe?session=" + encodeURIComponent(session), opts).then(function (resp) {
      if (!resp.ok || !resp.body) throw new Error("live subscribe unavailable");
      return readSSE(resp, onEvent);
    });
  }

  function nearBottom(box) {
    return box.scrollHeight - box.scrollTop - box.clientHeight < 120;
  }


  function makeLiveNode() {
    var root = document.createElement("div");
    root.className = "qvq-msg bot live";
// 单容器：思考/工具/文本按消息流顺序内联渲染
    root.innerHTML = '<div class="qvq-live-text"><span class="qvq-cursor"></span></div>';
    return {
      root: root,
      stepsEl: root.querySelector(".qvq-live-text"),
      textEl: root.querySelector(".qvq-live-text"),
      timer: null,
    };
  }

  function segSignature(seg) {
    // segment 内容指纹：内容未变的段跳过重建
    if (seg.type === "text") {
      return "t" + String(seg.text || "").length + ":" + String(seg.text || "").slice(-48);
    }
    var endMark = seg.end
      ? "e" + (seg.end.ms != null ? seg.end.ms : "") + ":" + String(seg.end.output || "").length
      : "r";
    return "g" + (seg.start && seg.start.step_id ? seg.start.step_id : "") + endMark;
  }

  // 增量渲染文字/工具交错流：只重建内容变化的段
// 快照写入本地 live 状态（服务端为权威来源）
  function applySnapshot(live, snap) {
    live.status = snap.status || live.status;
    live.text = snap.text || "";
    live.reasoning = snap.reasoning || "";
    live.steps = snap.steps || [];
    live.segments = snap.segments || [];
    if ((!live.segments || !live.segments.length) && live.steps.length) {
      live.segments = live.steps.map(function (st) {
        return { type: "tool", start: st.start, end: st.end || null };
      });
    }
    live.error = snap.error || null;
  }

  // 思考原文的成串空行/首尾空白在 pre-wrap 下渲染为空白区域：合并空行并 trim
  function tidyThink(text) {
    return String(text || "").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  }

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
      if (seg.type === "think") {
        // 思考块增量追加文本，不整块重建
        var thinkBody = tidyThink(seg.text);
        var inProgress = !!seg.open;
        var bodyNode = el.querySelector(".qvq-think-body");
        if (!bodyNode) {
          el.innerHTML = '<details class="qvq-think"' + (inProgress ? " open" : "") +
            '><summary><span class="qvq-think-label">' + esc(inProgress ? t("chat_thinking") : t("chat_thought")) +
            '</span></summary><div class="qvq-think-body"></div></details>';
          bodyNode = el.querySelector(".qvq-think-body");
        }
        var details = el.querySelector("details.qvq-think");
        if (details && details.open !== inProgress) details.open = inProgress;
        var label = el.querySelector(".qvq-think-label");
        if (label) label.textContent = inProgress ? t("chat_thinking") : t("chat_thought");
        if (bodyNode && bodyNode.textContent !== thinkBody) bodyNode.textContent = thinkBody;
        continue; // 不能 return：think 之后的文本/工具段必须继续渲染
      }
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
    // 弱滚动：仅在底部附近时跟随，上翻后不再跟随
    var stick = nearBottom(box);
    var expMap = collectExpSteps(els.textEl);

// 统一段列表：服务端按轮 flush 的 think 段 + 进行中的思考（末尾块，随流增长）
    var segments = [];
    (live.segments || []).forEach(function (seg) { segments.push(seg); });
// 快照只有 steps 没有 segments 时：回退成工具段
    if (!live.segments || !live.segments.length) {
      (live.steps || []).forEach(function (st) {
        segments.push({ type: "tool", start: st.start, end: st.end || null });
      });
    }
    if (live.reasoning) segments.push({ type: "think", text: tidyThink(live.reasoning), open: true });

    if (segments.length) {
// 进行中的思考段（open:true）随流重建保持展开；已完成块静态保留用户展开态
      renderSegments(els.textEl, segments, expMap);
    } else if (!live.text && live.started && !live.reasoning) {
      var secs = Math.max(0, Math.round((Date.now() - live.started) / 1000));
      renderWaitRow(els, secs); // 复用同一行，不重建节点（避免呼吸动画反复重启）
    } else {
      var textHtml = mdRender(live.text);
      els.textEl.innerHTML = (textHtml || '<span class="qvq-cursor"></span>');
    }
    if (stick) box.scrollTop = box.scrollHeight; // 只在原本就在底部时跟随
  }

  // 切到正在运行的会话：挂一条常驻 SSE（snapshot + 增量）
  function attachLive(snapshot) {
    if (activeLive && activeLive.session === snapshot.session) return;
    var epochAtAttach = chatEpoch;
    var box = el("qvq-chat-box");
    var live = { status: snapshot.status || "running", text: "", reasoning: "", steps: [], segments: [], error: null };
/* 流式：SSE、实时输出节点、恢复挂载、消息派发 */
    setSessionBusy(snapshot.session, true);
    var els = makeLiveNode();
    box.appendChild(els.root);
    activeLive = { els: els, session: snapshot.session };
    live.started = (snapshot.started || 0) * 1000 || Date.now();
    applySnapshot(live, snapshot);
    renderLiveNode(box, els, live);

    var ctrl = (typeof AbortController !== "undefined") ? new AbortController() : null;
    var done = false;
    function cleanup(reload) {
      if (done) return;
      done = true;
      if (renderTimer) { clearTimeout(renderTimer); renderTimer = null; }
      if (ctrl) { try { ctrl.abort(); } catch (e) {} }
      els.root.remove();
      setSessionBusy(snapshot.session, false);
      activeLive = null;
      if (epochAtAttach === chatEpoch) {
        if (reload) loadChatHistory();
        pumpQueue();
      }
    }
    // 增量事件 60ms 合并渲染
    var renderTimer = null;
    function scheduleRender() {
      if (renderTimer) return;
      renderTimer = setTimeout(function () {
        renderTimer = null;
        if (!done) renderLiveNode(box, els, live);
      }, 60);
    }
    var retries = 0;
    function subscribe() {
      if (done) return;
      streamLive(snapshot.session, function (ev, data) {
        if (done) return;
        if (chatEpoch !== epochAtAttach || chatSession !== snapshot.session) { cleanup(false); return; }
        if (ev !== "done" && ev !== "end" && ev !== "error") retries = 0;
        if (ev === "snapshot") {
          applySnapshot(live, data);
          renderLiveNode(box, els, live);
        } else if (ev === "delta" && data.t) {
          live.text += data.t;
          var i = data.i;
          while (live.segments.length <= i) live.segments.push({ type: "text", text: "" });
          if (live.segments[i].type !== "text") live.segments[i] = { type: "text", text: "" };
          live.segments[i].text += data.t;
          scheduleRender();
        } else if (ev === "reasoning" && data.t) {
          live.reasoning += data.t;
          scheduleRender();
        } else if (ev === "reset") {
          live.text = ""; live.reasoning = ""; live.steps = []; live.segments = [];
          renderLiveNode(box, els, live);
        } else if (ev === "tool") {
          applyToolEvent(live, data);
          renderLiveNode(box, els, live);
        } else if (ev === "done" || ev === "end") {
          live.status = (data && data.status) || "done";
          setTimeout(function () { cleanup(true); }, 400);
        } else if (ev === "error") {
          live.error = data.error;
          setTimeout(function () { cleanup(true); }, 400);
        }
      }, ctrl ? ctrl.signal : undefined).then(function () {
// 流断开但没收到 end（代理空闲超时/网络抖动）：重订阅并以快照续播
        if (done || chatEpoch !== epochAtAttach || chatSession !== snapshot.session) return;
        if (++retries > 5) { cleanup(true); return; }
        setTimeout(subscribe, 1000);
      }).catch(function () {
// 订阅不可用（服务端无直播流/网络中断）：直接按服务端已落盘内容刷新
        if (done) return;
        setTimeout(function () { cleanup(true); }, 200);
      });
    }
    subscribe();
  }

  // 工具事件应用到本地 live（start/end 配对），SSE 与快照路径共用
  function applyToolEvent(live, data) {
    if (data.phase === "start") {
      live.steps.push({ start: data });
      live.segments.push({ type: "tool", start: data });
      return;
    }
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
      for (var m = live.segments.length - 1; m >= 0; m--) {
        var sg2 = live.segments[m];
        if (sg2.type === "tool" && !sg2.end) { segMatch = sg2; break; }
      }
    }
    if (segMatch) segMatch.end = data;
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
      loadChatMeta({ history: false, live: false }); // 只刷新会话清单：历史本地已增量追加，不再整段重拉
      pumpQueue();
    }

    function reattach() {
      if (finished) return;
      api("/api/qvq/chat/live?session=" + encodeURIComponent(sessionAtStart)).then(function (snap) {
        if (epochAtStart !== chatEpoch || finished) return;
        if (snap && snap.status === "running") {
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
    function flushThink() {
// 思考阶段结束（轮内出现文本/工具）：落成独立 think 段（每轮一块，不跨轮合并）
      if (!live.reasoning) return;
      var segs = live.segments;
      var last = segs[segs.length - 1];
      if (!last || last.type !== "think" || last.text) segs.push({ type: "think", text: "" });
      segs[segs.length - 1].text += live.reasoning;
      live.reasoning = "";
    }
    streamChat(payload, function (ev, data) {
      if (epochAtStart !== chatEpoch) return;
      if (ev !== "meta") gotEvent = true;
      if (ev === "delta" && data.t) {
        flushThink();
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
        flushThink();
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
      // gotEvent 为真：断流只做快照重挂
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

