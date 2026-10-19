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
    renderChat();
    var box = el("qvq-chat-box");
    var live = { status: "running", text: "", steps: [], segments: [], error: null, started: Date.now() };
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
      renderChat();
      loadChatMeta();
      pumpQueue();
    }

    function reattach() {
      if (finished) return;
      api("/api/qvq/chat/live?session=" + encodeURIComponent(sessionAtStart)).then(function (snap) {
        if (epochAtStart !== chatEpoch) return;
        if (snap && snap.status === "running") {
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
        live.steps = [];
        live.segments = [];
        if (renderTimer) { clearTimeout(renderTimer); renderTimer = null; }
        renderLiveNode(box, els, live);
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
          if (snap && snap.reply != null) settle(snap.reply, snap.steps || live.steps, false);
          else if (snap && snap.error) settle(snap.error, snap.steps || live.steps, true);
          else settle(live.text || "…", live.steps, false);
        });
      }
    }).catch(function () {
      if (finished) return;
      api("/api/qvq/chat", "POST", payload).then(function (data) {
        if (data && data.error) {
          settle(data.error || t("chat_err"), [], true);
          toast(data.error || t("chat_err"), true);
        } else {
          settle((data && data.reply) || "…", [], false);
        }
      });
    });
  }

