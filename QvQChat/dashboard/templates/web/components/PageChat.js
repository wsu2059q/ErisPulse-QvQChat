/* 对话页：会话列表 / 消息流 / SSE 流式 / 附件 / 任务面板 / 会话操作 / 排队 / 分享 */
window.PageChat = {
  name: "PageChat",
  data() {
    return {
      sessions: [],
      q: "",
      activeKey: "",
      messages: [],
      total: 0,
      msgLimit: 40,
      loadingSessions: false,
      sessTimer: null,
      loadingMsgs: false,
      draft: "",
      attachments: [],
      sending: false,
      live: null,
      models: [],
      model: "",
      effort: "",
      personas: [],
      persona: "",
      toast: "",
      newOpen: false,
      newName: "",
      msgStart: 0,
      editing: null,
      skills: [],
      mcpTools: [],
      pickedSkills: [],
      pickedMcp: [],
      mentionOpen: false,
      mentionQ: "",
      atBottom: true,
      queue: [],
      todos: [],
      hv: null,
      todoOpen: false,
      todoDraft: "",
      todoTimer: null,
      sessMenuOpen: false,
      renaming: false,
      renameDraft: "",
      shareOpen: false,
      shareForm: { hours: 24, tokens: 4000, rounds: 0, chat_tokens: 20000 },
      shareUrl: "",
      promptOpen: false,
      promptData: null,
      promptBusy: false,
      shareToken: "",
      confirmOpen: false,
      confirmText: "",
      confirmCmd: "",
      confirmKey: "",
      collapsed: {},
      cfgOpen: false,
      cfgPol: { muted: false, low_token: false, priority: "normal", session_budget: 0 },
      cfgSet: { density: "", model: "", effort: "", trigger_mode: "", listen_off: false, persona: "" },
      cfgMembers: "",
      cfgSources: "",
      cfgBusy: false,
      cfgHint: "",
    };
  },
  computed: {
    active() {
      var key = this.activeKey;
      return this.sessions.filter(function (s) { return s.chat_key === key; })[0] || null;
    },
    activeName() {
      return this.active ? (this.active.name || this.active.chat_key) : "";
    },
    canSend() {
      return !this.sending && (!!this.draft.trim() || this.attachments.length > 0);
    },
    modelOptions() {
      return this.models.map(function (m) { return { label: m.id, value: m.id }; });
    },
    effortOptions() {
      return [
        { label: t("effort_auto"), value: "" },
        { label: t("effort_s_low"), value: "0.3" },
        { label: t("effort_s_mid"), value: "0.7" },
        { label: t("effort_s_high"), value: "1.0" },
      ];
    },
    personaOptions() {
      return [{ label: t("model_s_auto"), value: "" }].concat(this.personas.map(function (p) {
        return { label: p.name || p.id, value: p.id };
      }));
    },
    hasMore() {
      return this.messages.length < this.total;
    },
    mentionSkills() {
      var q = this.mentionQ.trim().toLowerCase();
      return this.skills.filter(function (s) {
        if (!q) return true;
        return (s.name + " " + (s.description || "")).toLowerCase().indexOf(q) >= 0;
      });
    },
    mentionTools() {
      var q = this.mentionQ.trim().toLowerCase();
      return this.mcpTools.filter(function (x) {
        if (!q) return true;
        return (x.name + " " + (x.description || "")).toLowerCase().indexOf(q) >= 0;
      });
    },
    mentionCount() { return this.pickedSkills.length + this.pickedMcp.length; },
    liveSegs() {
      // 过滤稀疏洞（历史事件乱序可能留 undefined 槽位），模板不再读 undefined.type
      return ((this.live && this.live.segments) || []).filter(Boolean);
    },
    subInfo() {
      // 当前会话本身是子会话（sub: 前缀）：显示内部查看横幅 + 返回主会话
      var key = this.activeKey;
      if (!key || String(key).indexOf("sub:") !== 0) return null;
      var s = this.sessions.filter(function (x) { return x.chat_key === key; })[0];
      if (s && s.kind) return s;
      // 会话还没入库（子智能体尚未首条回复）时从键回退解析：sub[:handover]:<父键>:<id8>
      var body = String(key).slice(4);
      var kind = "sub";
      if (body.indexOf("handover:") === 0) {
        kind = "handover";
        body = body.slice(9);
      }
      var cut = body.lastIndexOf(":");
      return { kind: kind, sub_of: cut > 0 ? body.slice(0, cut) : "" };
    },
    sessionOptions() {
      return this.sessions.map(function (s) {
        return { label: s.name || s.chat_key, value: s.chat_key };
      });
    },
    sessGroups() {
      // 侧栏分组（对齐旧版）：置顶 / 群聊 / 私聊 / 已归档，各自可折叠
      var groups = [
        { key: "pinned", label: t("sess_group_pinned"), items: [] },
        { key: "group", label: t("sess_group_group"), items: [] },
        { key: "private", label: t("sess_group_private"), items: [] },
        { key: "archived", label: t("chat_archived"), items: [] },
      ];
      this.sessions.forEach(function (s) {
        if (s.archived) groups[3].items.push(s);
        else if (s.pinned) groups[0].items.push(s);
        else (String(s.detail_type) === "group" ? groups[1] : groups[2]).items.push(s);
      });
      // 组内排序：正在对话的（live 流式中）最前，其余按最近回复时间倒序
      var byFresh = function (a, b) {
        if (!!a.live !== !!b.live) return a.live ? -1 : 1;
        return (b.updated || 0) - (a.updated || 0);
      };
      groups.forEach(function (g) { g.items.sort(byFresh); });
      return groups.filter(function (g) { return g.items.length; });
    },
    todoLeft() {
      return this.todos.filter(function (x) { return x.status !== "completed"; }).length;
    },
    sessMenuOptions() {
      var a = this.active || {};
      var opts = [{ label: t("session_rename"), key: "rename" }];
      opts.push({ label: a.pinned ? t("chat_unpin") : t("chat_pin"), key: "pin" });
      opts.push({ label: a.archived ? t("chat_unarchive") : t("chat_archive"), key: "archive" });
      opts.push({ label: t("chat_settings"), key: "cfg" });
      opts.push({ label: t("storage_compact_btn"), key: "compact" });
      opts.push({ label: t("chat_clear"), key: "reset" });
      opts.push({ label: t("chat_share"), key: "share" });
      return opts;
    },
    densityOptions() {
      return [
        { label: t("trigger_follow"), value: "" },
        { label: t("density_detail"), value: "detail" },
        { label: t("density_brief"), value: "brief" },
      ];
    },
    triggerModeOptions() {
      return [
        { label: t("trigger_follow"), value: "" },
        { label: t("trigger_all"), value: "all" },
        { label: t("trigger_at"), value: "at_only" },
        { label: t("trigger_lurk"), value: "lurk" },
        { label: t("trigger_off"), value: "off" },
      ];
    },
    cfgPriorityOptions() {
      return [
        { label: t("sess_policy_high"), value: "high" },
        { label: t("sess_policy_normal"), value: "normal" },
        { label: t("sess_policy_low"), value: "low" },
      ];
    },
  },
  mounted() {
    var self = this;
    try {
      var savedEffort = localStorage.getItem("qvq_chat_effort");
      if (savedEffort != null) this.effort = savedEffort;
    } catch (e) { /* 隐私模式等存不了就算了 */ }
    // pendingChat 先取局部：loadSessions 的默认打开首项会把它清掉
    var pending = QvQ.store.pendingChat;
    this.loadSessions().then(function () {
      if (pending) return self.open(pending);
      var running = self.sessions.filter(function (s) { return s.live; })[0];
      if (running && !self.activeKey) {
        self.open(running.chat_key);
        self.toast = t("resumed_running");
      }
    });
    this.startSessPoll();
    api("/api/qvq/models").then(function (d) {
      self.models = (d && d.models) || [];
    });
    api("/api/qvq/personas").then(function (d) {
      self.personas = (d && d.personas) || [];
    });
    api("/api/qvq/skills").then(function (d) {
      self.skills = (d && d.skills) || [];
    });
    api("/api/qvq/tools").then(function (d) {
      self.mcpTools = ((d && d.tools) || []).filter(function (x) { return x.origin === "mcp"; });
    });
  },
  beforeUnmount() {
    this.stopSessPoll();
    this.stopTodoPoll();
  },
  methods: {
    loadSessions() {
      var self = this;
      this.loadingSessions = true;
      var url = "/api/qvq/sessions?limit=200";
      if (this.q.trim()) url += "&q=" + encodeURIComponent(this.q.trim());
      return api(url).then(function (d) {
        self.sessions = (d && d.sessions) || [];
        self.loadingSessions = false;
        if (!self.activeKey && !QvQ.store.pendingChat && self.sessions.length) {
          self.open(self.sessions[0].chat_key);
        }
      });
    },
    open(key) {
      if (!key) return;
      this.activeKey = key;
      QvQ.store.pendingChat = "";
      this.messages = [];
      this.total = 0;
      this.live = null;
      this.todos = [];
      this.hv = null;
      this.loadMore();
      this.reattach(key);
      this.loadTodos();
      this.loadHandover();
    },
    loadMore() {
      var self = this;
      if (self.loadingMsgs || !self.activeKey) return;
      if (self.messages.length && !self.hasMore) return;
      self.loadingMsgs = true;
      var url = "/api/qvq/session/messages?chat_key=" + encodeURIComponent(self.activeKey) +
        "&limit=" + self.msgLimit;
      if (self.messages.length) {
        var start = Math.max(0, self.total - self.messages.length - self.msgLimit);
        url += "&start=" + start;
      }
      var box = this.$refs.thread;
      var prevH = box ? box.scrollHeight : 0;
      var anchor = this.atBottom;
      api(url).then(function (d) {
        self.loadingMsgs = false;
        var rows = (d && d.messages) || [];
        self.total = (d && d.total) || rows.length;
        self.msgStart = (d && d.start) || 0;
        self.messages = rows.concat(self.messages);
        self.$nextTick(function () {
          // 历史页向上拼接：补偿高度差保持视口；仅首屏定位到底部
          if (anchor) self.scrollBottom();
          else if (box) box.scrollTop = box.scrollHeight - prevH;
        });
      });
    },
    reload() {
      this.messages = [];
      this.total = 0;
      this.msgStart = 0;
      this.loadMore();
    },
    indexOf(i) { return this.msgStart + i; },

    /* ---- 消息级操作：编辑重发 / 仅保存 / 删除 / 重生成 ---- */
    startEdit(i) {
      var msg = this.messages[i];
      if (!msg) return;
      this.editing = { index: this.indexOf(i), text: String(msg.content || "") };
      this.draft = this.editing.text;
      var ta = this.$el.querySelector(".chat-ta");
      if (ta) ta.focus();
    },
    cancelEdit() {
      this.editing = null;
      this.draft = "";
    },
    saveOnly() {
      var self = this;
      if (!this.editing) return;
      api("/api/qvq/session/context/edit", "POST", {
        chat_key: this.activeKey, index: this.editing.index, content: this.draft,
      }).then(function (r) {
        if (r && r.error) {
          self.toast = r.error;
          return;
        }
        self.cancelEdit();
        self.reload();
      });
    },
    delMsg(i) {
      var self = this;
      api("/api/qvq/session/messages/delete", "POST", {
        chat_key: this.activeKey, index: this.indexOf(i),
      }).then(function () { self.reload(); });
    },
    msgSegs(m) {
      // 后端一直存着过程数据：assistant.rounds=[{text,tools:[{tool,arguments,output,ms}]}]，
      // 只有 trace 没有 rounds 时退回 trace。有 rounds 时正文已在段里，不再重复渲染 content。
      var items = [];
      (m.rounds || []).forEach(function (r) {
        if (r.think) items.push({ type: "think", text: r.think });
        if (r.text) items.push({ type: "text", text: r.text });
        (r.tools || []).forEach(function (t2) {
          items.push({
            type: "tool", name: t2.tool || t2.name || "?",
            args: t2.arguments || "", out: t2.output || "", ms: t2.ms,
          });
        });
      });
      if (!items.length && m.trace && m.trace.length) {
        m.trace.forEach(function (t2) {
          items.push({ type: "tool", name: t2.tool || "?", args: t2.arguments || "", out: t2.output || "", ms: t2.ms });
        });
      }
      return items.length ? items : null;
    },
    copyText(text) {
      var self = this;
      QvQ.copy(text, function (ok) { if (ok) self.toast = t("copied"); });
    },
    modelMetaTip(m) {
      // 消息出处悬浮提示：模型 + token 明细
      if (!m.meta) return "";
      var u = m.meta.usage || {};
      var parts = [];
      if (u.prompt_tokens != null) parts.push("in " + u.prompt_tokens);
      if (u.completion_tokens != null) parts.push("out " + u.completion_tokens);
      return t("chat_model_meta") + (parts.length ? "\n" + parts.join(" / ") : "");
    },
    regenerate() {
      var self = this;
      api("/api/qvq/session/regenerate", "POST", { chat_key: this.activeKey }).then(function (r) {
        if (!r || !r.ok) {
          self.toast = (r && r.error) || t("model_test_fail");
          return;
        }
        self.reload();
        if (r.text) self.sendText(r.text, []);
      });
    },

    /* ---- 会话操作：重命名 / 置顶 / 归档 / 压缩 / 清空 / 分享 ---- */
    onSessCmd(key) {
      var self = this;
      var a = this.active;
      if (!a && key !== "share") return;
      if (key === "rename") {
        this.renameDraft = this.activeName;
        this.renaming = true;
        return;
      }
      if (key === "pin") {
        api("/api/qvq/session/flags", "POST", { chat_key: this.activeKey, pinned: !a.pinned })
          .then(function () { self.loadSessions(); });
        return;
      }
      if (key === "archive") {
        api("/api/qvq/session/flags", "POST", { chat_key: this.activeKey, archived: !a.archived })
          .then(function () {
            self.toast = a.archived ? t("chat_unarchive") : t("chat_archived");
            self.loadSessions();
          });
        return;
      }
      if (key === "cfg") {
        this.openCfg();
        return;
      }
      if (key === "compact") {
        api("/api/qvq/session/compact", "POST", { chat_key: this.activeKey }).then(function (r) {
          self.toast = r && r.error ? r.error : t("storage_compact_done").replace("{n}", "1");
        });
        return;
      }
      if (key === "reset") {
        this.confirmText = t("chat_clear") + "？";
        this.confirmCmd = "reset";
        this.confirmOpen = true;
        return;
      }
      if (key === "share") {
        this.shareUrl = "";
        this.shareToken = "";
        this.shareOpen = true;
      }
    },
    doRename() {
      var self = this;
      var name = this.renameDraft.trim();
      this.renaming = false;
      if (!name) return;
      api("/api/qvq/session/rename", "POST", { chat_key: this.activeKey, name: name })
        .then(function () { self.loadSessions(); });
    },

    /* ---- 会话设置抽屉：策略 / 密度模型触发 / 监听 / 成员 / 跨会话路由 / 人格 ---- */
    openCfg() {
      var a = this.active || {};
      var pol = a.policy || {};
      var ui = a.ui || {};
      this.cfgPol = {
        muted: !!pol.muted,
        low_token: !!pol.low_token,
        priority: String(pol.priority || "normal"),
        session_budget: Number(pol.session_budget) || 0,
        full_access: !!pol.full_access,
      };
      this.cfgSet = {
        density: String(ui.density || ""),
        model: String(ui.model || ""),
        effort: String(ui.effort || ""),
        trigger_mode: String(ui.trigger_mode || ""),
        listen_off: !!a.listen_off,
        persona: String(a.persona || ""),
      };
      this.cfgMembers = (a.members || []).join("\n");
      this.cfgSources = (a.sources || []).join("\n");
      this.cfgHint = "";
      this.cfgOpen = true;
    },
    saveCfg() {
      var self = this;
      if (!this.activeKey) return;
      var key = this.activeKey;
      this.cfgBusy = true;
      var calls = [
        api("/api/qvq/session/policy", "POST", Object.assign({ chat_key: key }, this.cfgPol)),
        api("/api/qvq/session/settings", "POST", {
          chat_key: key,
          settings: {
            density: this.cfgSet.density, model: this.cfgSet.model, effort: this.cfgSet.effort,
            trigger_mode: this.cfgSet.trigger_mode, listen_off: this.cfgSet.listen_off,
            members: this.cfgMembers.split("\n").map(function (s) { return s.trim(); })
              .filter(function (s) { return s; }),
          },
        }),
        api("/api/qvq/session/routes", "POST", {
          target: key,
          sources: this.cfgSources.split("\n").map(function (s) { return s.trim(); })
            .filter(function (s) { return s; }),
        }),
      ];
      var a = this.active || {};
      var personaChanged = this.cfgSet.persona !== String(a.persona || "");
      if (personaChanged) {
        calls.push(api("/api/qvq/personas/bind", "POST", {
          chat_key: key, persona_id: this.cfgSet.persona,
        }));
      }
      Promise.all(calls).then(function () {
        self.cfgBusy = false;
        self.cfgHint = personaChanged ? t("settings_saved") : t("sess_policy_saved");
        self.loadSessions();
      });
    },
    loadPromptPreview() {
      // 提示词调试器：dry-run 组装链（不落库、无副作用），部件明细 + 全文
      var self = this;
      if (!this.activeKey) return;
      this.promptBusy = true;
      this.promptOpen = true;
      api("/api/qvq/prompt/preview?chat_key=" + encodeURIComponent(this.activeKey))
        .then(function (r) {
          self.promptBusy = false;
          if (r && r.error) { self.promptData = { error: r.error }; return; }
          self.promptData = r || { error: "?" };
        }).catch(function (e) {
          self.promptBusy = false;
          self.promptData = { error: String(e) };
        });
    },
    saveCfgDefaults() {
      // 把当前会话的密度/模型/力度存为全局默认（新会话继承）
      var self = this;
      this.cfgBusy = true;
      api("/api/qvq/settings/defaults", "POST", {
        settings: {
          density: this.cfgSet.density,
          model: this.cfgSet.model,
          effort: this.cfgSet.effort,
        },
      }).then(function (r) {
        self.cfgBusy = false;
        self.cfgHint = (r && !r.error) ? t("defaults_saved") : ((r && r.error) || "error");
      });
    },
    doConfirm() {
      var self = this;
      var cmd = this.confirmCmd;
      var key = this.confirmKey || this.activeKey;
      this.confirmOpen = false;
      this.confirmCmd = "";
      this.confirmKey = "";
      if (cmd === "reset" && key) {
        api("/api/qvq/sessions/reset", "POST", { chat_key: key }).then(function () {
          self.reload();
          self.loadSessions();
        });
        return;
      }
      if (cmd === "hvStop" && key) {
        api("/api/qvq/handover/stop", "POST", { chat_key: key }).then(function (r) {
          if (r && r.error) { self.toast = r.error; return; }
          self.toast = t("hv_exit");
          self.hv = null;
          self.loadSessions();
        });
        return;
      }
      if (cmd === "delSession" && key) {
        api("/api/qvq/sessions/delete", "POST", { chat_key: key }).then(function () {
          if (key === self.activeKey) {
            self.activeKey = "";
            self.messages = [];
            self.live = null;
          }
          self.loadSessions();
        });
      }
    },
    toggleGroup(key) {
      this.collapsed = Object.assign({}, this.collapsed, { [key]: !this.collapsed[key] });
    },
    sessRowMenu(s) {
      return [
        { label: s.pinned ? t("chat_unpin") : t("chat_pin"), key: "pin" },
        { label: s.archived ? t("chat_unarchive") : t("chat_archive"), key: "archive" },
        { label: t("session_rename"), key: "rename" },
        { label: t("chat_delete"), key: "del" },
      ];
    },
    sessAct(s, act) {
      var self = this;
      if (act === "pin") {
        api("/api/qvq/session/flags", "POST", { chat_key: s.chat_key, pinned: !s.pinned })
          .then(function () { self.loadSessions(); });
        return;
      }
      if (act === "archive") {
        api("/api/qvq/session/flags", "POST", { chat_key: s.chat_key, archived: !s.archived })
          .then(function () { self.loadSessions(); });
        return;
      }
      if (act === "rename") {
        this.activeKey = s.chat_key;
        this.renameDraft = s.name || s.chat_key;
        this.renaming = true;
        return;
      }
      if (act === "del") {
        this.confirmText = t("session_delete_confirm");
        this.confirmCmd = "delSession";
        this.confirmKey = s.chat_key;
        this.confirmOpen = true;
      }
    },
    createShare() {
      var self = this;
      api("/api/qvq/session/share", "POST", {
        chat_key: this.activeKey,
        expires_hours: Number(this.shareForm.hours) || 24,
        max_tokens: Number(this.shareForm.tokens) || 4000,
        rounds: Number(this.shareForm.rounds) || 0,
        chat_tokens: Number(this.shareForm.chat_tokens) || 20000,
      }).then(function (r) {
        if (r && r.url) {
          self.shareUrl = location.origin + r.url;
          self.shareToken = r.token || "";
        }
      });
    },
    revokeShare() {
      var self = this;
      if (!this.shareToken) return;
      api("/api/qvq/session/share/revoke", "POST", { token: this.shareToken }).then(function (r) {
        if (r && !r.error) {
          QvQ.toast(t("share_revoked"));
          self.shareUrl = "";
          self.shareToken = "";
        }
      });
    },

    /* ---- 任务面板（与 AI todo_* 同库） ---- */
    loadTodos() {
      var self = this;
      if (!this.activeKey) return;
      api("/api/qvq/todo?chat_key=" + encodeURIComponent(this.activeKey)).then(function (d) {
        self.todos = (d && d.todos) || [];
      });
    },
    loadHandover() {
      var self = this;
      var key = this.activeKey;
      if (!key || String(key).indexOf("sub:") === 0) { self.hv = null; return; }
      api("/api/qvq/handover?chat_key=" + encodeURIComponent(key)).then(function (d) {
        if (key !== self.activeKey) return;
        self.hv = (d && d.active) ? d : null;
      });
    },
    askHvStop() {
      this.confirmText = t("hv_exit") + "？";
      this.confirmCmd = "hvStop";
      this.confirmOpen = true;
    },
    toggleTodoPanel() {
      this.todoOpen = !this.todoOpen;
      if (this.todoOpen) this.loadTodos();
    },
    addTodo() {
      var self = this;
      var text = this.todoDraft.trim();
      if (!text) return;
      this.todoDraft = "";
      api("/api/qvq/todo/add", "POST", { chat_key: this.activeKey, content: text })
        .then(function () { self.loadTodos(); });
    },
    cycleTodo(x) {
      var self = this;
      var order = ["pending", "in_progress", "completed"];
      var next = order[(order.indexOf(x.status) + 1) % order.length];
      api("/api/qvq/todo/update", "POST", { chat_key: this.activeKey, id: x.id, status: next })
        .then(function () { self.loadTodos(); });
    },
    delTodo(x) {
      var self = this;
      api("/api/qvq/todo/delete", "POST", { chat_key: this.activeKey, id: x.id })
        .then(function () { self.loadTodos(); });
    },
    startTodoPoll() {
      var self = this;
      this.stopTodoPoll();
      this.todoTimer = setInterval(function () {
        if (self.todoOpen || self.todos.length) self.loadTodos();
      }, 4000);
    },
    stopTodoPoll() {
      if (this.todoTimer) {
        clearInterval(this.todoTimer);
        this.todoTimer = null;
      }
    },
    startSessPoll() {
      // 侧栏轻轮询：正在对话的会话（live）置顶、最近回复排序保持新鲜；静默刷新不动 loading/默认打开
      var self = this;
      this.stopSessPoll();
      this.sessTimer = setInterval(function () {
        var url = "/api/qvq/sessions?limit=200";
        if (self.q.trim()) url += "&q=" + encodeURIComponent(self.q.trim());
        api(url).then(function (d) {
          self.sessions = (d && d.sessions) || [];
        });
      }, 12000);
    },
    stopSessPoll() {
      if (this.sessTimer) {
        clearInterval(this.sessTimer);
        this.sessTimer = null;
      }
    },
    todoLabel(s) {
      return s === "completed" ? t("todo_s_completed")
        : s === "in_progress" ? t("todo_s_in_progress") : t("todo_s_pending");
    },

    /* ---- SSE / 发送 ---- */
    reattach(key) {
      var self = this;
      api("/api/qvq/chat/live?session=" + encodeURIComponent(key)).then(function (d) {
        if (!d || d.status !== "running") return;
        self.live = d;
        self.sending = true;
        self.startTodoPoll();
        self.subscribe(key);
      });
    },
    subscribe(key) {
      var self = this;
      var url = "/QvQChat/api/qvq/chat/live/subscribe?session=" + encodeURIComponent(key);
      var headers = {};
      if (getToken()) headers["Authorization"] = "Bearer " + getToken();
      fetch(url, { headers: headers }).then(function (resp) {
        if (!resp.ok || !resp.body) return;
        self.readStream(resp, function (evt, data) {
          if (evt === "snapshot") { self.live = data; return; }
          self.applyEvent(evt, data);
        });
      });
    },
    scrollBottom() {
      var box = this.$refs.thread;
      if (box) box.scrollTop = box.scrollHeight;
      this.atBottom = true;
    },
    onThreadScroll() {
      var box = this.$refs.thread;
      if (!box) return;
      this.atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
      // 无感加载：滚到顶部附近自动拉更早的消息
      if (box.scrollTop < 60 && this.hasMore && !this.loadingMsgs) this.loadMore();
    },
    onThreadClick(ev) {
      var btn = ev.target.closest ? ev.target.closest(".qvq-md-copy") : null;
      if (!btn) return;
      var block = btn.closest(".qvq-md-block");
      var code = block ? block.querySelector("pre") : null;
      if (code) QvQ.copy(code.innerText || "", this.copied);
    },
    copied() { this.toast = t("copied"); },
    applyEvent(evt, data) {
      if (evt === "delta") {
        if (!this.live) this.live = { segments: [], status: "running" };
        if (!this.live.segments) this.live.segments = [];
        var segs = this.live.segments;
        var seg = segs[data.i];
        if (!seg) {
          // 稀疏补洞：跳号到达时填空文本段，模板 seg.type 不会踩到 undefined
          while (segs.length < data.i) segs.push({ type: "text", text: "" });
          segs.push({ type: "text", text: data.t || "" });
        } else {
          seg.text = (seg.text || "") + (data.t || "");
        }
        if (this.atBottom) this.$nextTick(this.scrollBottom);
      } else if (evt === "reasoning") {
        if (!this.live) this.live = { segments: [], status: "running" };
        this.live.reasoning = (this.live.reasoning || "") + (data.t || "");
      } else if (evt === "tool") {
        if (!this.live) this.live = { segments: [], status: "running" };
        if (!this.live.segments) this.live.segments = [];
        if (data.phase === "start") this.live.segments.push({ type: "tool", start: data });
        else {
          for (var i = this.live.segments.length - 1; i >= 0; i--) {
            var s = this.live.segments[i];
            if (s && s.type === "tool" && !s.end) { s.end = data; break; }
          }
        }
      } else if (evt === "reset") {
        if (this.live) this.live.segments = [];
      } else if (evt === "done") {
        this.finishRun();
      } else if (evt === "error") {
        this.toast = (data && data.error) || "error";
        this.finishRun();
      } else if (evt === "end") {
        this.finishRun();
      }
    },
    finishRun() {
      var self = this;
      if (!self.sending) return;
      self.sending = false;
      self.stopTodoPoll();
      var key = self.activeKey;
      // 先取新消息、到手后再整体替换并撤 live：不出现「live 消失 → 空白 → 列表」的闪屏
      var url = "/api/qvq/session/messages?chat_key=" + encodeURIComponent(key) +
        "&limit=" + self.msgLimit;
      api(url).then(function (d) {
        var rows = (d && d.messages) || [];
        self.total = (d && d.total) || rows.length;
        self.msgStart = (d && d.start) || 0;
        self.messages = rows;
        self.live = null;
        self.$nextTick(function () { if (self.atBottom) self.scrollBottom(); });
        self.loadSessions();
        self.loadTodos();
        self.loadHandover();
        if (self.queue.length && key === self.activeKey) {
          var next = self.queue.shift();
          self.sendText(next.text, next.atts);
        }
      }).catch(function () {
        self.live = null;
        self.loadSessions();
      });
    },
    readStream(resp, onEvent) {
      var reader = resp.body.getReader();
      var dec = new TextDecoder();
      var buf = "";
      function parse(block) {
        var evt = "message";
        var data = "";
        block.split("\n").forEach(function (line) {
          if (line.indexOf("event:") === 0) evt = line.slice(6).trim();
          else if (line.indexOf("data:") === 0) data += line.slice(5).trim();
        });
        if (!data) return;
        var parsed;
        try { parsed = JSON.parse(data); } catch (e) { return; }
        onEvent(evt, parsed);
      }
      function pump() {
        return reader.read().then(function (res) {
          if (res.done) return;
          buf += dec.decode(res.value, { stream: true });
          var idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            var block = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            if (block.trim()) parse(block);
          }
          return pump();
        });
      }
      return pump();
    },
    send() {
      var self = this;
      if (!this.draft.trim() && !this.attachments.length) return;
      if (this.sending) {
        this.queue.push({ text: this.draft.trim(), atts: this.attachments.slice() });
        this.draft = "";
        this.attachments = [];
        this.toast = t("queue_added");
        return;
      }
      var text = this.draft.trim();
      var atts = this.attachments.slice();
      this.draft = "";
      this.attachments = [];
      var editing = this.editing;
      this.editing = null;
      if (!editing) {
        this.sendText(text, atts);
        return;
      }
      api("/api/qvq/session/rewind", "POST", {
        chat_key: this.activeKey, index: editing.index,
      }).then(function (r) {
        if (!r || !r.ok) {
          self.toast = (r && r.error) || "rewind failed";
          self.draft = text;
          return;
        }
        self.reload();
        self.sendText(text, atts);
      });
    },
    removeQueued(i) { this.queue.splice(i, 1); },
    sendText(text, atts) {
      var self = this;
      this.sending = true;
      this.live = { segments: [], status: "running" };
      this.$nextTick(this.autoGrow);
      this.messages.push({
        role: "user",
        content: text,
        atts: atts.map(function (a) { return { name: a.name, data: a.data }; }),
      });
      this.$nextTick(this.scrollBottom);
      this.startTodoPoll();
      var payload = {
        session: this.activeKey || "dashboard:private:web",
        text: text,
        attachments: atts.map(function (a) {
          return { name: a.name, mime: a.mime, data: a.data };
        }),
        model: this.model || "",
        persona: this.persona || "",
        skills: this.pickedSkills.slice(),
        mcp_tools: this.pickedMcp.slice(),
      };
      if (this.effort) payload.temperature = parseFloat(this.effort);
      var headers = { "Content-Type": "application/json" };
      if (getToken()) headers["Authorization"] = "Bearer " + getToken();
      fetch("/QvQChat/api/qvq/chat/stream", {
        method: "POST", headers: headers, body: JSON.stringify(payload),
      }).then(function (resp) {
        if (resp.status === 409) {
          self.sending = false;
          self.live = null;
          self.toast = t("chat_busy");
          return;
        }
        if (!resp.ok || !resp.body) {
          self.sending = false;
          self.live = null;
          self.toast = "HTTP " + resp.status;
          return;
        }
        self.readStream(resp, function (evt, data) { self.applyEvent(evt, data); });
      }).catch(function (e) {
        self.sending = false;
        self.live = null;
        self.toast = String(e);
      });
    },
    stop() {
      var self = this;
      api("/api/qvq/chat/cancel", "POST", { session: this.activeKey }).then(function () {
        self.toast = t("chat_cancelled");
      });
    },
    onKey(e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        this.send();
      } else if (e.key === "Escape" && this.editing) {
        e.preventDefault();
        this.cancelEdit();
      }
    },
    autoGrow() {
      var ta = this.$el.querySelector(".chat-ta");
      if (!ta) return;
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
    },
    onEffort(v) {
      this.effort = v || "";
      try { localStorage.setItem("qvq_chat_effort", this.effort); } catch (e) { /* 忽略 */ }
    },

    /* ---- 附件 ---- */
    pickFiles(ev) {
      var self = this;
      Array.prototype.forEach.call(ev.target.files || [], function (f) { self.addFile(f); });
      ev.target.value = "";
    },
    onPaste(ev) {
      var files = (ev.clipboardData && ev.clipboardData.files) || [];
      for (var i = 0; i < files.length; i++) this.addFile(files[i]);
    },
    addFile(file) {
      var self = this;
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) {
        this.toast = t("chat_file_too_big");
        return;
      }
      var reader = new FileReader();
      reader.onload = function () {
        self.attachments.push({
          name: file.name,
          mime: file.type || "application/octet-stream",
          data: String(reader.result || ""),
          image: (file.type || "").indexOf("image/") === 0,
        });
      };
      reader.readAsDataURL(file);
    },
    removeAttach(i) { this.attachments.splice(i, 1); },
    togglePick(list, name) {
      var idx = list.indexOf(name);
      if (idx >= 0) list.splice(idx, 1);
      else list.push(name);
    },
    toggleSkill(name) { this.togglePick(this.pickedSkills, name); },
    toggleMcp(name) { this.togglePick(this.pickedMcp, name); },
    newSession() {
      this.newName = t("chat_new_name").replace("{n}", String(this.sessions.length + 1));
      this.newOpen = true;
    },
    createSession() {
      var self = this;
      var name = this.newName.trim();
      api("/api/qvq/sessions/create", "POST", {}).then(function (d) {
        self.newOpen = false;
        var apply = function () {
          self.loadSessions().then(function () {
            if (d && d.chat_key) self.open(d.chat_key);
          });
        };
        if (name && d && d.chat_key) {
          api("/api/qvq/session/rename", "POST", { chat_key: d.chat_key, name: name }).then(apply);
        } else apply();
      });
    },
    fmtTime(ts) {
      if (!ts) return "";
      var d = new Date(Number(ts) * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return p(d.getHours()) + ":" + p(d.getMinutes());
    },
  },
  template: [
    '<div class="chat-wrap">',
    '  <aside class="chat-side">',
    '    <div class="chat-side-head">',
    '      <n-input v-model:value="q" size="small" clearable :placeholder="t(\'search_ph\')"',
    '               @update:value="loadSessions"/>',
    '      <button type="button" class="chat-new" :title="t(\'chat_new\')" @click="newSession">+</button>',
    '    </div>',
    '    <div class="chat-list">',
    '      <template v-for="g in sessGroups" :key="g.key">',
    '        <button type="button" class="chat-group" @click="toggleGroup(g.key)">',
    '          <span>{{ g.label }}</span>',
    '          <span class="chat-group-n">{{ g.items.length }}<i>{{ collapsed[g.key] ? "›" : "‹" }}</i></span>',
    '        </button>',
    '        <template v-if="!collapsed[g.key]">',
    '          <div v-for="s in g.items" :key="s.chat_key" class="chat-sitem-wrap">',
    '            <button type="button" class="chat-sitem" :class="{ on: s.chat_key === activeKey }"',
    '                    @click="open(s.chat_key)">',
    '              <span class="nm">{{ s.name || s.chat_key }}<i v-if="s.kind === \'handover\'" class="chat-subtag hv">{{ t("hv_badge") }}</i><i v-else-if="s.kind === \'sub\'" class="chat-subtag">{{ t("sub_badge") }}</i></span>',
    '              <span class="mt"><span class="live-dot" v-if="s.live"></span>{{ s.turns || 0 }}</span>',
    '            </button>',
    '            <div class="chat-sitem-acts">',
    '              <n-dropdown trigger="click" placement="bottom-end" size="small"',
    '                          :options="sessRowMenu(s)" @select="sessAct(s, $event)">',
    '                <button type="button" class="chat-sitem-more" @click.stop>⋯</button>',
    '              </n-dropdown>',
    '            </div>',
    '          </div>',
    '        </template>',
    '      </template>',
    '      <div v-if="!sessions.length" class="qvq-empty">-</div>',
    '    </div>',
    '  </aside>',
    '  <section class="chat-main">',
    '    <header class="chat-head">',
    '      <n-select class="chat-sess-pick" :value="activeKey" :options="sessionOptions"',
    '                size="small" filterable @update:value="open"/>',
    '      <div class="chat-head-tx">',
    '        <div class="chat-title">{{ activeName || t("nav_chat") }}</div>',
    '        <div class="chat-sub">{{ activeKey }}</div>',
    '      </div>',
    '      <div class="chat-head-ctl">',
    '        <n-select :value="model || null" :options="modelOptions" size="small" filterable clearable',
    '                  style="width:190px" :placeholder="t(\'model_auto\')" @update:value="model = $event || \'\'"/>',
    '        <n-select :value="effort" :options="effortOptions" size="small" style="width:116px"',
    '                  @update:value="onEffort"/>',
    '        <n-select v-model:value="persona" :options="personaOptions" size="small" style="width:128px"/>',
    '        <n-popover trigger="click" placement="bottom-end" :show="todoOpen" @update:show="todoOpen = $event">',
    '          <template #trigger>',
    '            <button type="button" class="chat-todo-btn" :class="{ on: todoOpen || todoLeft }"',
    '                    :title="t(\'todo_title\')" @click="toggleTodoPanel">',
    '              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"',
    '                   stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
    '              <i v-if="todoLeft" class="chat-todo-n">{{ todoLeft }}</i></button>',
    '          </template>',
    '          <div class="todo-panel">',
    '            <div class="todo-head">{{ t("todo_title") }}</div>',
    '            <div v-for="x in todos" :key="x.id" class="todo-item" :class="x.status">',
    '              <button type="button" class="todo-mark" :title="todoLabel(x.status)" @click="cycleTodo(x)">',
    '                {{ x.status === "completed" ? "✔" : x.status === "in_progress" ? "◐" : "○" }}</button>',
    '              <span class="todo-tx">{{ x.content }}</span>',
    '              <button type="button" class="todo-x" @click="delTodo(x)">×</button>',
    '            </div>',
    '            <div v-if="!todos.length" class="qvq-empty">{{ t("todo_empty") }}</div>',
    '            <div class="todo-add">',
    '              <input v-model="todoDraft" :placeholder="t(\'todo_new_ph\')"',
    '                     @keydown.enter.prevent="addTodo"/>',
    '              <button type="button" @click="addTodo">＋</button>',
    '            </div>',
    '          </div>',
    '        </n-popover>',
    '        <n-dropdown trigger="click" :options="sessMenuOptions" @select="onSessCmd">',
    '          <button type="button" class="chat-todo-btn" :title="t(\'chat_more\')">⋯</button>',
    '        </n-dropdown>',
    '      </div>',
    '    </header>',
    '    <div class="chat-hv" v-if="hv && hv.active">',
    '      <button type="button" class="chat-hv-main" @click="open(hv.sub_key)" :title="t(\'viewing_sub\')">',
    '        <span class="nm">{{ t("hv_active") }}</span>',
    '        <span class="mt">{{ hv.setup || hv.model || "" }} · {{ hv.turns || 0 }}/{{ hv.max_turns || "-" }}</span>',
    '      </button>',
    '      <button type="button" class="chat-hv-stop" @click="askHvStop">{{ t("hv_exit") }}</button>',
    '    </div>',
    '    <div class="chat-hv internal" v-else-if="subInfo">',
    '      <span class="nm">{{ subInfo.kind === "handover" ? t("hv_badge") : t("sub_badge") }} · {{ t("viewing_sub") }}</span>',
    '      <button v-if="subInfo.sub_of" type="button" class="chat-hv-stop" @click="open(subInfo.sub_of)">',
    '        {{ t("back_parent") }}</button>',
    '    </div>',
    '    <div class="chat-thread" ref="thread" @scroll="onThreadScroll" @click="onThreadClick">',
    '      <div class="chat-empty" v-if="!messages.length && !live">',
    '        <Mascot :size="44" mood="idle"/>',
    '        <div class="chat-empty-title">{{ t("chat_hero_sub") }}</div>',
    '        <div class="chat-chips">',
    '          <button v-for="n in 4" :key="n" type="button" @click="draft = t(\'chat_chip_\' + n)">',
    '            {{ t("chat_chip_" + n) }}</button>',
    '        </div>',
    '      </div>',
    '      <button v-if="hasMore" type="button" class="chat-more" @click="loadMore">',
    '        {{ loadingMsgs ? "…" : t("load_more") }}</button>',
    '      <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">',
    '        <div class="msg-body">',
    '          <div class="msg-atts" v-if="m.atts && m.atts.length">',
    '            <img v-for="(a, j) in m.atts" :key="j" class="msg-img" :src="a.data" :alt="a.name"/>',
    '          </div>',
    '          <div class="msg-text" v-if="m.role === \'assistant\' && !(m.rounds && m.rounds.length)" v-html="mdRender(m.content || \'\')"></div>',
    '          <div class="msg-text" v-else-if="m.role !== \'assistant\'">{{ m.content }}</div>',
    '          <template v-if="msgSegs(m)">',
    '            <template v-for="(sg, k) in msgSegs(m)" :key="\'sg\' + k">',
    '              <details v-if="sg.type === \'tool\'" class="msg-tool">',
    '                <summary><span class="sdot ok"></span>{{ sg.name }}<i v-if="sg.ms != null"> {{ sg.ms }}ms</i></summary>',
    '                <div class="msg-tool-io" v-if="sg.args"><b>→</b><pre>{{ sg.args }}</pre></div>',
    '                <div class="msg-tool-io" v-if="sg.out"><b>←</b><pre>{{ sg.out }}</pre></div>',
    '              </details>',
    '              <details v-else-if="sg.type === \'think\'" class="msg-think">',
    '                <summary>{{ t("chat_think") }}</summary>',
    '                <pre>{{ sg.text }}</pre>',
    '              </details>',
    '              <div v-else class="msg-text" v-html="mdRender(sg.text || \'\')"></div>',
    '            </template>',
    '          </template>',
    '        </div>',
    '        <div class="msg-acts">',
    '          <span v-if="m.meta && m.meta.model" class="msg-model"',
    '                :title="modelMetaTip(m)">{{ m.meta.model }}{{ m.meta.usage && m.meta.usage.total_tokens != null ? " · " + Number(m.meta.usage.total_tokens).toLocaleString() + " tok" : "" }}</span>',
    '          <button v-if="m.role === \'user\'" type="button" @click="startEdit(i)">{{ t("edit") }}</button>',
    '          <button type="button" @click="copyText(m.content)">{{ t("chat_copy") }}</button>',
    '          <button type="button" @click="delMsg(i)">{{ t("chat_delete") }}</button>',
    '          <button v-if="m.role === \'assistant\' && i === messages.length - 1 && !sending"',
    '                  type="button" @click="regenerate">{{ t("regen") }}</button>',
    '        </div>',
    '      </div>',
    '      <div class="msg assistant live" v-if="live">',
    '        <div class="msg-body">',
    '          <details class="live-think" v-if="live.reasoning">',
    '            <summary>{{ t("chat_think") }}</summary>',
    '            <pre>{{ live.reasoning }}</pre>',
    '          </details>',
    '          <template v-for="(seg, i) in liveSegs" :key="i">',
    '            <details class="live-tool" v-if="seg.type === \'tool\'">',
    '              <summary><span class="sdot" :class="{ ok: seg.end && !seg.end.error }"></span>',
    '                {{ (seg.start && seg.start.name) || "tool" }}',
    '                <i v-if="seg.end && seg.end.ms != null"> {{ seg.end.ms }}ms</i></summary>',
    '              <div class="msg-tool-io" v-if="seg.start && seg.start.arguments"><b>→</b><pre>{{ seg.start.arguments }}</pre></div>',
    '              <div class="msg-tool-io" v-if="seg.end && seg.end.output"><b>←</b><pre>{{ seg.end.output }}</pre></div>',
    '            </details>',
    '            <div class="live-seg think" v-else-if="seg.type === \'think\'">{{ seg.text }}</div>',
    '            <div class="live-seg text" v-else v-html="mdRender(seg.text || \'\', true)"></div>',
    '          </template>',
    '          <div class="live-typing" v-if="sending && !(live.segments && live.segments.length)">',
    '            <span></span><span></span><span></span>',
    '          </div>',
    '          <span class="live-caret" v-else-if="sending"></span>',
    '        </div>',
    '      </div>',
    '    </div>',
    '    <button v-if="!atBottom" type="button" class="chat-down" @click="scrollBottom">↓</button>',
    '    <footer class="chat-composer">',
    '      <div class="chat-queue" v-if="queue.length">',
    '        <div class="chat-queued" v-for="(it, i) in queue" :key="i">',
    '          <span class="nm">{{ it.text || t("chat_pasted") }}</span>',
    '          <button type="button" @click="removeQueued(i)">×</button>',
    '        </div>',
    '      </div>',
    '      <div class="chat-atts" v-if="attachments.length">',
    '        <div class="chat-att" v-for="(a, i) in attachments" :key="i">',
    '          <img v-if="a.image" :src="a.data" :alt="a.name"/>',
    '          <span v-else class="nm">{{ a.name }}</span>',
    '          <button type="button" class="x" @click="removeAttach(i)">×</button>',
    '        </div>',
    '      </div>',
    '      <div class="chat-editbar" v-if="editing">',
    '        <span>{{ t("chat_edit_on") }}</span>',
    '        <span class="chat-edit-acts">',
    '          <button type="button" @click="saveOnly">{{ t("msg_save_only") }}</button>',
    '          <button type="button" @click="cancelEdit">×</button>',
    '        </span>',
    '      </div>',
    '      <div class="chat-picks" v-if="mentionCount">',
    '        <span class="chat-pick" v-for="n in pickedSkills" :key="\'s\' + n">',
    '          {{ n }}<button type="button" @click="toggleSkill(n)">×</button></span>',
    '        <span class="chat-pick mcp" v-for="n in pickedMcp" :key="\'m\' + n">',
    '          {{ n }}<button type="button" @click="toggleMcp(n)">×</button></span>',
    '      </div>',
    '      <div class="chat-input">',
    '        <button type="button" class="chat-mention" :class="{ on: mentionCount }"',
    '                :title="t(\'chat_mention\')" @click="mentionOpen = true">@</button>',
    '        <label class="chat-clip" :title="t(\'chat_pasted\')">',
    '          <input type="file" multiple hidden @change="pickFiles"/>',
    '          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"',
    '               stroke-linecap="round"><path d="M21.4 11.05l-9.19 9.19a5 5 0 01-7.07-7.07l8.49-8.49a3.5 3.5 0 114.95 4.95l-8.49 8.49a2 2 0 01-2.83-2.83l7.78-7.78"/></svg>',
    '        </label>',
    '        <textarea v-model="draft" class="chat-ta" rows="1" :placeholder="t(\'chat_input_ph\')"',
    '                  @keydown="onKey" @paste="onPaste" @input="autoGrow"></textarea>',
    '        <div class="chat-input-side">',
    '          <span class="chat-queue-n" v-if="queue.length">{{ queue.length }}</span>',
    '          <button type="button" class="chat-send" :disabled="!draft.trim() && !attachments.length" @click="send">',
    '            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"',
    '                 stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M6 11l6-6 6 6"/></svg>',
    '          </button>',
    '          <button v-if="sending" type="button" class="chat-send stop" :title="t(\'chat_stop\')" @click="stop">',
    '            <svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>',
    '          </button>',
    '        </div>',
    '      </div>',
    '    </footer>',
    '  </section>',
    '  <n-modal v-model:show="newOpen" preset="card" class="qvq-modal-card"',
    '           style="max-width:380px" :title="t(\'chat_new\')" :bordered="false">',
    '    <n-input v-model:value="newName" :placeholder="t(\'chat_new_name\')"',
    '             @keydown.enter="createSession"/>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="newOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" @click="createSession">{{ t("confirm_yes") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="renaming" preset="card" class="qvq-modal-card"',
    '           style="max-width:380px" :title="t(\'rename\')" :bordered="false">',
    '    <n-input v-model:value="renameDraft" @keydown.enter="doRename"/>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="renaming = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" @click="doRename">{{ t("save") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="confirmOpen" preset="card" class="qvq-modal-card"',
    '           style="max-width:360px" :title="t(\'confirm_title\')" :bordered="false">',
    '    <div>{{ confirmText }}</div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="confirmOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="error" @click="doConfirm">{{ t("confirm_yes") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-drawer v-model:show="cfgOpen" :width="480" placement="right">',
    '    <n-drawer-content :title="activeName || t(\'chat_settings\')" closable>',
    '      <div class="prov-form">',
    '        <div class="prov-field">',
    '          <label>{{ t("sess_policy_muted") }}</label>',
    '          <n-switch v-model:value="cfgPol.muted"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("sess_policy_low_token") }}</label>',
    '          <n-switch v-model:value="cfgPol.low_token"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("sess_policy_full") }}</label>',
    '          <n-switch v-model:value="cfgPol.full_access"/>',
    '        </div>',
    '        <div class="prov-grid2">',
    '          <div class="prov-field">',
    '            <label>{{ t("sess_policy_priority") }}</label>',
    '            <n-select v-model:value="cfgPol.priority" :options="cfgPriorityOptions" size="small"/>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>{{ t("sess_policy_budget") }}</label>',
    '            <n-input-number v-model:value="cfgPol.session_budget" :min="0" size="small" style="width:100%"/>',
    '          </div>',
    '        </div>',
    '        <div class="prov-grid2">',
    '          <div class="prov-field">',
    '            <label>{{ t("chat_density") }}</label>',
    '            <n-select v-model:value="cfgSet.density" :options="densityOptions" size="small"/>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>{{ t("chat_trigger") }}</label>',
    '            <n-select v-model:value="cfgSet.trigger_mode" :options="triggerModeOptions" size="small"/>',
    '          </div>',
    '        </div>',
    '        <div class="prov-grid2">',
    '          <div class="prov-field">',
    '            <label>{{ t("chat_model") }}</label>',
    '            <n-select v-model:value="cfgSet.model" :options="modelOptions" size="small" filterable/>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>{{ t("chat_effort") }}</label>',
    '            <n-select v-model:value="cfgSet.effort" :options="effortOptions" size="small"/>',
    '          </div>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("chat_persona_binding") }}</label>',
    '          <n-select v-model:value="cfgSet.persona" :options="personaOptions" size="small" filterable/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("listen_off_toggle") }}</label>',
    '          <n-switch v-model:value="cfgSet.listen_off"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("sess_members") }}</label>',
    '          <n-input v-model:value="cfgMembers" type="textarea" :rows="3" :placeholder="t(\'sess_members_hint\')"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("sess_sources_hint") }}</label>',
    '          <n-input v-model:value="cfgSources" type="textarea" :rows="3" :placeholder="t(\'sess_sources_hint\')"/>',
    '        </div>',
    '        <div class="qvq-cfg-saved" v-if="cfgHint">{{ cfgHint }}</div>',
    '      </div>',
    '      <template #footer>',
    '        <div class="qvq-modal-foot">',
    '          <n-button size="small" :disabled="cfgBusy" @click="loadPromptPreview">{{ t("prompt_preview") }}</n-button>',
    '          <n-button size="small" :disabled="cfgBusy" @click="saveCfgDefaults">{{ t("save_as_default") }}</n-button>',
    '          <n-button size="small" :loading="cfgBusy" type="primary" @click="saveCfg">{{ t("save") }}</n-button>',
    '        </div>',
    '      </template>',
    '    </n-drawer-content>',
    '  </n-drawer>',
    '  <n-modal v-model:show="promptOpen" preset="card" class="qvq-modal-card" style="max-width:720px"',
    '           :title="t(\'prompt_preview\')" :bordered="false">',
    '    <div v-if="promptData && promptData.error" class="cf-error">{{ promptData.error }}</div>',
    '    <template v-else-if="promptData">',
    '      <div class="prompt-meta">',
    '        <span class="partic-chip">{{ promptData.persona || "-" }}</span>',
    '        <span class="partic-chip">{{ promptData.model || t("model_s_auto") }}</span>',
    '        <span class="partic-chip">{{ promptData.system_chars }} {{ t("prompt_chars") }}</span>',
    '        <span class="partic-chip">{{ promptData.history_turns }} {{ t("prompt_turns") }}</span>',
    '      </div>',
    '      <div class="prompt-parts">',
    '        <div v-for="(p, i) in (promptData.debug && promptData.debug.parts) || []" :key="i" class="prompt-part">',
    '          <code>{{ p.kind }}</code>',
    '          <span class="qvq-meta-line">{{ p.chars }} ch{{ p.required ? " · " + t("prompt_required") : "" }}</span>',
    '          <span class="qvq-meta-line prompt-prev">{{ p.preview }}</span>',
    '        </div>',
    '      </div>',
    '      <n-input :value="promptData.system" type="textarea" :rows="14" readonly class="cf-mono prompt-full"/>',
    '      <div class="qvq-meta-line" style="margin-top:6px">{{ t("prompt_scene_note") }}</div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="shareOpen" preset="card" class="qvq-modal-card"',
    '           style="max-width:460px" :title="t(\'chat_share\')" :bordered="false">',
    '    <div class="prov-form" v-if="!shareUrl">',
    '      <div class="prov-field">',
    '        <label>{{ t("share_expires") }}</label>',
    '        <n-input-number v-model:value="shareForm.hours" :min="1" :max="720" style="width:100%"/>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("share_max_tokens") }}</label>',
    '        <n-input-number v-model:value="shareForm.tokens" :min="200" :max="200000" :step="500" style="width:100%"/>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("share_rounds") }}</label>',
    '        <n-input-number v-model:value="shareForm.rounds" :min="0" :max="200" style="width:100%"/>',
    '      </div>',
    '      <div class="prov-field" v-if="shareForm.rounds > 0">',
    '        <label>{{ t("share_chat_tokens") }}</label>',
    '        <n-input-number v-model:value="shareForm.chat_tokens" :min="500" :max="500000" :step="1000" style="width:100%"/>',
    '      </div>',
    '      <div class="qvq-meta-line">{{ t("share_hint") }}</div>',
    '    </div>',
    '    <div v-else class="prov-form">',
    '      <div class="prov-field">',
    '        <label>{{ t("share_url") }}</label>',
    '        <n-input :value="shareUrl" readonly/>',
    '      </div>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button v-if="shareUrl" size="small" @click="copyText(shareUrl)">{{ t("chat_copy") }}</n-button>',
    '        <n-button v-if="shareUrl" size="small" type="error" @click="revokeShare">{{ t("share_revoke") }}</n-button>',
    '        <n-button v-if="!shareUrl" size="small" type="primary" @click="createShare">',
    '          {{ t("share_create") }}</n-button>',
    '        <n-button v-else size="small" type="primary" @click="shareOpen = false">{{ t("confirm_yes") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="mentionOpen" preset="card" class="qvq-modal-card"',
    '           style="max-width:440px" :title="t(\'chat_pick_tools\')" :bordered="false">',
    '    <n-input v-model:value="mentionQ" size="small" clearable :placeholder="t(\'search_ph\')"/>',
    '    <div class="mention-body">',
    '      <div class="mention-group" v-if="mentionSkills.length">',
    '        <div class="mention-title">{{ t("chat_skills") }}</div>',
    '        <n-checkbox v-for="sk in mentionSkills" :key="sk.name"',
    '                    :checked="pickedSkills.indexOf(sk.name) >= 0"',
    '                    :label="sk.name" @update:checked="toggleSkill(sk.name)"/>',
    '      </div>',
    '      <div class="mention-group" v-if="mentionTools.length">',
    '        <div class="mention-title">{{ t("chat_mcp_tools") }}</div>',
    '        <n-checkbox v-for="tool in mentionTools" :key="tool.name"',
    '                    :checked="pickedMcp.indexOf(tool.name) >= 0"',
    '                    :label="tool.name" @update:checked="toggleMcp(tool.name)"/>',
    '      </div>',
    '      <div v-if="!mentionSkills.length && !mentionTools.length" class="qvq-empty">',
    '        {{ t("mention_none") }}</div>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" type="primary" @click="mentionOpen = false">{{ t("mention_ok") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <transition name="doc-pop">',
    '    <div class="chat-toast" v-if="toast" @click="toast = \'\'">{{ toast }}</div>',
    '  </transition>',
    '</div>',
  ].join(""),
};
