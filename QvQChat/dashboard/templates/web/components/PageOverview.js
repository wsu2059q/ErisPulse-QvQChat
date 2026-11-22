/* 概览：运行指标 / 用量与成本趋势 / 最近会话 / 即将执行 */
window.PageOverview = {
  name: "PageOverview",
  data() {
    return {
      status: null,
      usage: null,
      costs: null,
      sessions: [],
      tasks: [],
      chartMode: "usage",
      mascotMood: "",
      greetIdx: 0,
      limitOpen: false,
      costModelsOpen: false,
      limitDraft: 0,
      budgetAuto: false,
      flagsLoaded: false,
      savedHint: "",
      auditTotal: 0,
      onboard: null,
      onboardOpen: true,
      runningCount: 0,
      runningRows: [],
      coolingCount: 0,
      inbox: null,
      inboxOpen: false,
      busyOps: false,
      tip: null,
      ecoPanels: [],
    };
  },
  computed: {
    eco() { return (this.status && this.status.eco) || {}; },
    toolsTotal() {
      var tools = (this.status && this.status.tools) || {};
      var n = 0;
      Object.keys(tools).forEach(function (k) { n += Number(tools[k]) || 0; });
      return n;
    },
    takeovers() { return (this.status && this.status.takeovers) || 0; },
    ecoCards() {
      // 生态卡区：模块 panel.cards 平铺（只读展示）
      var out = [];
      (this.ecoPanels || []).forEach(function (m) {
        (m.cards || []).forEach(function (c) {
          out.push({ module: m.module, title: c.title, text: c.text, icon: c.icon || "" });
        });
      });
      return out;
    },
    slot() {
      var h = new Date().getHours();
      if (h < 6) return "late";
      if (h < 9) return "dawn";
      if (h < 11) return "morning";
      if (h < 14) return "noon";
      if (h < 18) return "afternoon";
      if (h < 23) return "evening";
      return "late";
    },
    greeting() {
      return t("hero_" + this.slot + "_" + ((this.greetIdx % 3) + 1));
    },
    baseMood() {
      if (this.slot === "late") return "sleep";
      if (this.slot === "dawn") return "dawn";
      if (this.slot === "afternoon") return "think";
      return "idle";
    },
    heroSub() {
      var s = this.status || {};
      var parts = [];
      if (s.version) parts.push("v" + s.version);
      parts.push((this.eco.modules || 0) + t("stat_eco_modules"));
      if (this.toolsTotal) parts.push(this.toolsTotal + t("stat_eco_tools"));
      parts.push(t("takeovers") + " " + this.takeovers);
      return parts.join(" · ");
    },
    usageToday() { return (this.status && this.status.usage_today) || {}; },
    usagePct() {
      var u = this.usageToday;
      if (!u || !u.limit) return 0;
      return Math.min(100, Math.round(((u.tokens || 0) / u.limit) * 100));
    },
    tokensText() { return Number(this.usageToday.tokens || 0).toLocaleString(); },
    limitText() {
      var u = this.usageToday;
      if (!u || !u.limit) return t("hero_no_limit");
      return t("usage_limit") + " " + Number(u.limit).toLocaleString();
    },
    kpis() {
      var s = this.status || {};
      var mcp = s.mcp;
      return [
        { num: s.models || 0, label: t("stat_models"), go: "providers", group: "model" },
        { num: this.toolsTotal, label: t("stat_tools"), go: "tools" },
        { num: ((s.tools || {}).eco) || 0, label: t("stat_eco"), go: "tools" },
        { num: ((s.extensions || []).length), label: t("stat_extensions"), go: "tools" },
        { num: s.sessions || 0, label: t("stat_sessions"), go: "sessions" },
        { num: s.tasks || 0, label: t("stat_tasks"), go: "tasks" },
        { num: Array.isArray(mcp) ? mcp.length : 0, label: t("stat_mcp"), go: "mcp" },
        {
          num: s.trust_agent ? t("trust_on") : t("sec_level_" + (s.security_level || "standard")),
          label: t("stat_security"),
          go: "config",
          group: "security",
          warn: !!s.trust_agent,
        },
      ];
    },
    recent() { return this.sessions.slice(0, 5); },
    upcoming() { return this.tasks.slice(0, 5); },
    inboxEvents() { return ((this.inbox && this.inbox.events) || []).slice(0, 6); },
    inboxUnread() { return (this.inbox && this.inbox.unread) || 0; },
    chart() {
      return this.chartMode === "cost" ? this.costChart() : this.usageChart();
    },
    chartMeta() {
      if (this.chartMode === "cost") {
        return {
          limit: 0,
          rows: ((this.costs && this.costs.daily) || []).map(function (d) {
            return { date: d.date, tokens: 0, calls: 0, cost: Number(d.cost) || 0 };
          }),
        };
      }
      var days = (this.usage && this.usage.days) || [];
      var limit = (this.usage && this.usage.limit) || 0;
      return {
        limit: limit,
        rows: days.map(function (d) {
          return { date: d.date, tokens: Number(d.tokens) || 0, calls: Number(d.calls) || 0, cost: 0 };
        }),
      };
    },
    exceedDays() {
      var limit = (this.usage && this.usage.limit) || 0;
      if (!limit) return 0;
      return ((this.usage && this.usage.days) || []).filter(function (d) {
        return (Number(d.tokens) || 0) > limit;
      }).length;
    },
    limitLegend() {
      var limit = (this.usage && this.usage.limit) || 0;
      return t("chart_limit_legend")
        .replace("{n}", Number(limit).toLocaleString())
        .replace("{d}", String(this.exceedDays));
    },
    modelCosts() {
      // 成本按模型分布（后端 costs.by_model 已按金额降序）
      var by = (this.costs && this.costs.by_model) || {};
      var total = Number((this.costs && this.costs.total) || 0) || 0;
      return Object.keys(by).map(function (id) {
        var c = Number(by[id]) || 0;
        return {
          id: id, cost: c, text: c.toFixed(4),
          pct: total > 0 ? Math.max(2, Math.round((c / total) * 100)) : 0,
        };
      });
    },
    costTotalText() {
      return Number((this.costs && this.costs.total) || 0).toFixed(4);
    },
  },
  mounted() {
    this.load();
    this.loadOnboarding();
  },
  methods: {
    /* 首启引导：生态模块的「使用建议」注入开关（localStorage 只记折叠，不记选择） */
    loadOnboarding() {
      var self = this;
      try {
        if (localStorage.getItem("qvq_onboard_done")) { this.onboardOpen = false; }
      } catch (e) {}
      api("/api/qvq/eco_panel").then(function (d) {
        self.ecoPanels = (d && d.panels) || [];
      });
      api("/api/qvq/onboarding").then(function (d) {
        var mods = (d && d.modules) || [];
        if (!mods.length) { self.onboard = null; return; }
        self.onboard = {
          modules: mods.map(function (m) {
            return { module: m.module, count: m.count || 0, preview: m.preview || "", injected: !!m.injected };
          }),
        };
      });
    },
    onboardToggle(m) { m.injected = !m.injected; },
    onboardSave() {
      var choices = {};
      this.onboard.modules.forEach(function (m) { choices[m.module] = m.injected; });
      api("/api/qvq/onboarding", "POST", { choices: choices }).then(function () {
        QvQ.toast(t("settings_saved"));
      });
      try { localStorage.setItem("qvq_onboard_done", "1"); } catch (e) {}
      this.onboardOpen = false;
    },
    onboardDismiss() {
      try { localStorage.setItem("qvq_onboard_done", "1"); } catch (e) {}
      this.onboardOpen = false;
    },
    loadFlags() {
      var self = this;
      api("/api/qvq/config").then(function (d) {
        var fields = (d && d.fields) || [];
        fields.forEach(function (f) {
          if (f.key === "budget_auto_on_limit") self.budgetAuto = !!f.value;
        });
        self.flagsLoaded = true;
      });
    },
    load() {
      var self = this;
      self.loadFlags();
      api("/api/qvq/status").then(function (d) { self.status = d; });
      api("/api/qvq/usage").then(function (d) { self.usage = d; });
      api("/api/qvq/costs").then(function (d) { self.costs = d; });
      api("/api/qvq/sessions").then(function (d) {
        self.sessions = (d && d.sessions) || [];
      });
      api("/api/qvq/tasks").then(function (d) {
        self.tasks = (d && d.tasks) || [];
      });
      api("/api/qvq/audit?limit=1").then(function (d) {
        self.auditTotal = (d && d.total) || 0;
      });
      api("/api/qvq/running").then(function (d) {
        self.runningRows = (d && d.running) || [];
        self.runningCount = self.runningRows.length;
      });
      api("/api/qvq/breakers").then(function (d) {
        self.coolingCount = ((d && d.breakers) || []).length;
      });
      api("/api/qvq/inbox?limit=6").then(function (d) {
        self.inbox = d || null;
      });
    },
    inboxText(e) {
      return String(e.summary || e.text || e.preview || e.id || "");
    },
    inboxKind(e) {
      return String(e.kind || "") === "request" ? t("inbox_kind_request") : t("inbox_kind_notice");
    },
    toggleInbox() {
      var self = this;
      this.inboxOpen = !this.inboxOpen;
      if (this.inboxOpen) {
        api("/api/qvq/inbox?limit=6").then(function (d) { self.inbox = d || null; });
      }
    },
    clearInbox() {
      var self = this;
      this.busyOps = true;
      api("/api/qvq/inbox/clear", "POST", {}).then(function () {
        self.busyOps = false;
        self.load();
      });
    },
    poke() {
      var self = this;
      self.greetIdx += 1;
      self.mascotMood = "happy";
      clearTimeout(self._pokeTimer);
      self._pokeTimer = setTimeout(function () { self.mascotMood = ""; }, 1300);
    },
    go(item) {
      // 兼容字符串与对象两种入参（传字符串时跳 group 逻辑）
      QvQ.store.pendingGroup = (item && item.group) || "";
      QvQ.store.page = (item && item.go) || item;
    },
    openSession(key) {
      QvQ.store.pendingChat = key;
      QvQ.store.page = "chat";
    },
    taskLabel(tk) {
      return QvQ.taskLabel(tk);
    },
    isOverdue(tk) {
      var ts = Number(tk && tk.next_run || 0);
      return ts > 0 && ts * 1000 < Date.now();
    },
    openLimit() {
      this.limitDraft = Number(this.usageToday.limit || 0);
      this.limitOpen = true;
    },
    saveLimit() {
      var self = this;
      var value = Math.max(0, Math.round(Number(self.limitDraft) || 0));
      var body = { daily_token_limit: value };
      if (self.flagsLoaded) body.budget_auto_on_limit = !!self.budgetAuto;
      api("/api/qvq/config", "POST", body).then(function (r) {
        var ok = r && (r.ok || r.__http === 200) && !(r.errors && Object.keys(r.errors).length);
        if (!ok) {
          self.savedHint = (r && r.error) || "error";
          return;
        }
        self.limitOpen = false;
        self.savedHint = t("saved");
        setTimeout(function () { self.savedHint = ""; }, 2000);
        self.load();
      });
    },
    fmtDate(ts) {
      if (!ts) return "-";
      var d = new Date(Number(ts) * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return (d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
    },
    fmtDay(s) {
      var m = String(s || "").match(/(\d{4})-(\d{2})-(\d{2})/);
      return m ? m[2] + "-" + m[3] : String(s || "");
    },
    chartHover(ev) {
      var meta = this.chartMeta;
      var n = meta.rows.length;
      if (!n) return;
      var rect = ev.currentTarget.getBoundingClientRect();
      if (!rect.width) return;
      var W = 720, padX = 12;
      var vx = ((ev.clientX - rect.left) / rect.width) * W;
      var x = function (i) { return padX + (W - padX * 2) * (n > 1 ? i / (n - 1) : 0.5); };
      var best = 0, bd = Infinity;
      for (var i = 0; i < n; i++) {
        var d = Math.abs(x(i) - vx);
        if (d < bd) { bd = d; best = i; }
      }
      var row = meta.rows[best];
      var lines = ["<b>" + this.fmtDay(row.date) + "</b>"];
      if (this.chartMode === "usage") {
        lines.push(Number(row.tokens).toLocaleString() + " tokens");
        if (row.calls) lines.push(t("chart_tip_calls") + " " + row.calls);
        if (meta.limit) {
          var pct = Math.round((row.tokens / meta.limit) * 100);
          lines.push(t("chart_tip_pct") + " " + pct + "%");
        }
      } else {
        lines.push("$" + row.cost.toFixed(4));
      }
      this.tip = {
        left: Math.min(Math.max((x(best) / W) * rect.width, 70), rect.width - 70),
        html: lines.join("<br>"),
      };
    },
    usageChart() {
      var days = (this.usage && this.usage.days) || [];
      var limit = (this.usage && this.usage.limit) || 0;
      if (!days.length) return { svg: "", empty: true };
      var W = 720, H = 200, padX = 12, top = 16, bottom = 32;
      var plotH = H - top - bottom;
      var n = days.length;
      var tok = days.map(function (d) { return Number(d.tokens) || 0; });
      var calls = days.map(function (d) { return Number(d.calls) || 0; });
      var maxTok = Math.max.apply(null, tok.concat([1]));
      var maxCalls = Math.max.apply(null, calls.concat([1]));
      var x = function (i) { return padX + (W - padX * 2) * (n > 1 ? i / (n - 1) : 0.5); };
      var yT = function (v) { return top + plotH - (v / maxTok) * plotH; };
      var barW = Math.max(4, ((W - padX * 2) / n) * 0.34);
      var bars = calls.map(function (c, i) {
        if (!c) return "";
        var h = (c / maxCalls) * plotH * 0.34;
        return "<rect class='qvq-chart-calls' x='" + (x(i) - barW / 2).toFixed(1) +
          "' y='" + (top + plotH - h).toFixed(1) + "' width='" + barW.toFixed(1) +
          "' height='" + h.toFixed(1) + "' rx='2'><title>" +
          this.fmtDay(days[i].date) + " · " + c + "</title></rect>";
      }, this).join("");
      var pts = tok.map(function (v, i) { return x(i).toFixed(1) + "," + yT(v).toFixed(1); });
      var line = "M" + pts.join(" L");
      var area = line + " L" + x(n - 1).toFixed(1) + "," + (top + plotH) +
        " L" + x(0).toFixed(1) + "," + (top + plotH) + " Z";
      var grid = [0.25, 0.5, 0.75].map(function (r) {
        var y = top + plotH * r;
        return "<line class='qvq-chart-grid' x1='0' y1='" + y + "' x2='" + W + "' y2='" + y + "'/>";
      }).join("");
      var limitLine = "";
      if (limit) {
        // 上限线常驻：高于最大值时钳制到绘图区顶端（配合悬停浮层读占比）
        var ly = Math.max(top + 2, Math.min(yT(limit), top + plotH));
        limitLine = "<line class='qvq-chart-limit' x1='0' y1='" + ly.toFixed(1) + "' x2='" + W +
          "' y2='" + ly.toFixed(1) + "'/>";
      }
      var dots = tok.map(function (v, i) {
        return "<circle class='qvq-chart-dot' cx='" + x(i).toFixed(1) + "' cy='" + yT(v).toFixed(1) +
          "' r='2.4'><title>" + this.fmtDay(days[i].date) + " · " +
          Number(v).toLocaleString() + "</title></circle>";
      }, this).join("");
      var labels = days.map(function (d, i) {
        if (n > 7 && i % 3 !== 0 && i !== n - 1) return "";
        return "<text class='qvq-chart-label' x='" + x(i).toFixed(1) + "' y='" + (H - 10) +
          "' text-anchor='middle'>" + this.fmtDay(d.date) + "</text>";
      }, this).join("");
      var svg = "<svg viewBox='0 0 " + W + " " + H + "'>" +
        grid + bars + "<path class='qvq-chart-area' d='" + area + "'/>" +
        limitLine + "<path class='qvq-chart-line' d='" + line + "'/>" + dots + labels + "</svg>";
      return { svg: svg, empty: false };
    },
    costChart() {
      var daily = (this.costs && this.costs.daily) || [];
      if (!daily.length) return { svg: "", empty: true };
      var W = 720, H = 200, padX = 12, top = 16, bottom = 32;
      var plotH = H - top - bottom;
      var n = daily.length;
      var cost = daily.map(function (d) { return Number(d.cost) || 0; });
      var maxC = Math.max.apply(null, cost.concat([0.0001]));
      var x = function (i) { return padX + (W - padX * 2) * (n > 1 ? i / (n - 1) : 0.5); };
      var y = function (v) { return top + plotH - (v / maxC) * plotH; };
      var pts = cost.map(function (v, i) { return x(i).toFixed(1) + "," + y(v).toFixed(1); });
      var line = "M" + pts.join(" L");
      var area = line + " L" + x(n - 1).toFixed(1) + "," + (top + plotH) +
        " L" + x(0).toFixed(1) + "," + (top + plotH) + " Z";
      var grid = [0.25, 0.5, 0.75].map(function (r) {
        var gy = top + plotH * r;
        return "<line class='qvq-chart-grid' x1='0' y1='" + gy + "' x2='" + W + "' y2='" + gy + "'/>";
      }).join("");
      var dots = cost.map(function (v, i) {
        return "<circle class='qvq-chart-dot' cx='" + x(i).toFixed(1) + "' cy='" + y(v).toFixed(1) +
          "' r='2.4'><title>" + this.fmtDay(daily[i].date) + " · $" + v.toFixed(4) + "</title></circle>";
      }, this).join("");
      var labels = daily.map(function (d, i) {
        if (n > 7 && i % 3 !== 0 && i !== n - 1) return "";
        return "<text class='qvq-chart-label' x='" + x(i).toFixed(1) + "' y='" + (H - 10) +
          "' text-anchor='middle'>" + this.fmtDay(d.date) + "</text>";
      }, this).join("");
      var svg = "<svg viewBox='0 0 " + W + " " + H + "'>" +
        grid + "<path class='qvq-chart-area qvq-chart-area-cost' d='" + area + "'/>" +
        "<path class='qvq-chart-line qvq-chart-line-cost' d='" + line + "'/>" + dots + labels + "</svg>";
      return { svg: svg, empty: false };
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="ov-brand-wrap">',
    '    <div class="ov-brand">QvQ<i>.</i></div>',
    '    <div class="ov-brand-sub">{{ t("home_sub") }}</div>',
    '  </div>',
    '  <n-card v-if="onboard && onboardOpen" size="small" class="qvq-glass-card ov-onboard">',
    '    <div class="ov-onboard-head">',
    '      <div>',
    '        <div class="ov-onboard-title">{{ t("onboard_title") }}</div>',
    '        <div class="qvq-meta-line">{{ t("onboard_desc") }}</div>',
    '      </div>',
    '      <button type="button" class="qvq-drawer-x" @click="onboardDismiss">×</button>',
    '    </div>',
    '    <div v-for="m in onboard.modules" :key="m.module" class="ov-onboard-row">',
    '      <div class="ov-onboard-mod">',
    '        <b>{{ m.module }}</b>',
    '        <i>{{ m.count }} prompt · {{ m.preview }}</i>',
    '      </div>',
    '      <n-switch size="small" :value="m.injected" @update:value="onboardToggle(m)"/>',
    '    </div>',
    '    <div class="qvq-modal-foot" style="margin-top:10px">',
    '      <n-button size="small" @click="onboardDismiss">{{ t("onboard_skip") }}</n-button>',
    '      <n-button size="small" type="primary" @click="onboardSave">{{ t("save") }}</n-button>',
    '    </div>',
    '  </n-card>',
    '  <div class="qvq-hero">',
    '    <button type="button" class="qvq-hero-face" @click="poke" :title="t(\'home_sub\')">',
    '      <Mascot :size="30" :mood="mascotMood || baseMood"/>',
    '    </button>',
    '    <div class="qvq-hero-main">',
    '      <div class="qvq-hero-title">{{ greeting }}</div>',
    '      <div class="qvq-hero-sub">{{ heroSub }}</div>',
    '    </div>',
    '    <button type="button" class="qvq-hero-usage" @click="openLimit" :title="t(\'limit_edit_hint\')">',
    '      <div class="num">{{ tokensText }}</div>',
    '      <div class="cap">{{ t("home_usage_today") }} · {{ usagePct }}%</div>',
    '      <div class="cap-sub"><u>{{ limitText }}</u></div>',
    '      <n-progress type="line" :percentage="usagePct" :show-indicator="false" :height="6"',
    '                  :status="usagePct >= 100 ? \'error\' : (usagePct >= 80 ? \'warning\' : \'default\')"/>',
    '      <div class="qvq-hint-inline" v-if="savedHint">{{ savedHint }}</div>',
    '    </button>',
    '  </div>',
    '  <div class="qvq-stats">',
    '    <button v-for="k in kpis" :key="k.label" type="button"',
    '            class="qvq-kpi" :class="{ warn: k.warn }" @click="go(k)">',
    '      <div class="qvq-kpi-num">{{ k.num }}</div>',
    '      <div class="qvq-kpi-cap">{{ k.label }}</div>',
    '    </button>',
    '  </div>',
    '  <div class="qvq-ops">',
    '    <button type="button" class="qvq-op" @click="go({go: \'audit\'})">',
    '      <span class="nm">{{ t("nav_audit") }}</span>',
    '      <span class="num">{{ auditTotal }}</span>',
    '    </button>',
    '    <button type="button" class="qvq-op" :class="{ warn: runningCount > 0 }" @click="go({go: \'orchestrate\'})">',
    '      <span class="nm">{{ t("orch_running") }}</span>',
    '      <span class="num">{{ runningCount }}</span>',
    '    </button>',
    '    <button type="button" class="qvq-op" :class="{ warn: coolingCount > 0 }" @click="go({go: \'orchestrate\'})">',
    '      <span class="nm">{{ t("health_cooldown") }}</span>',
    '      <span class="num">{{ coolingCount }}</span>',
    '    </button>',
    '    <button type="button" class="qvq-op" :class="{ warn: inboxUnread > 0 }" @click="toggleInbox">',
    '      <span class="nm">{{ t("inbox_title") }}</span>',
    '      <span class="num">{{ inboxUnread }}</span>',
    '    </button>',
    '  </div>',
    '  <n-card size="small" class="qvq-glass-card" style="margin-top:14px" v-if="inboxOpen">',
    '    <div class="qvq-card-head">',
    '      <span class="qvq-card-title">{{ t("inbox_title") }}',
    '        <span class="qvq-meta-line" style="margin-left:8px">{{ t("inbox_count").replace("{n}", String((inbox && inbox.total) || 0)).replace("{u}", String(inboxUnread)) }}</span>',
    '      </span>',
    '      <button type="button" class="qvq-link" @click="clearInbox">{{ t("inbox_clear") }}</button>',
    '    </div>',
    '    <div v-if="!inboxEvents.length" class="qvq-empty">{{ t("inbox_empty") }}</div>',
    '    <div v-for="(e, i) in inboxEvents" :key="i" class="qvq-row static">',
    '      <span class="qvq-row-name">{{ inboxText(e) }}</span>',
    '      <span class="qvq-row-meta">{{ inboxKind(e) }} · {{ fmtDate(e.ts) }}</span>',
    '    </div>',
    '  </n-card>',
    '    <n-card size="small" class="qvq-glass-card" v-if="ecoCards.length">',
    '      <div class="qvq-card-head"><span class="qvq-card-title">{{ t("eco_cards_title") }}</span></div>',
    '      <div class="eco-card-row">',
    '        <div v-for="(c, i) in ecoCards" :key="i" class="eco-card">',
    '          <div class="eco-card-title"><code>{{ c.module }}</code><b>{{ c.title }}</b></div>',
    '          <div class="eco-card-text" v-if="c.text">{{ c.text }}</div>',
    '        </div>',
    '      </div>',
    '    </n-card>',
    '  <div class="qvq-home-grid">',
    '    <n-card size="small" class="qvq-glass-card qvq-chart-card">',
    '      <div class="qvq-card-head">',
    '        <span class="qvq-card-title"><button type="button" class="qvq-link" @click="go({ go: \'usage\' })">{{ chartMode === \'cost\' ? t("cost_title") : t("usage_title") }} →</button></span>',
    '        <div class="qvq-seg">',
    '          <button type="button" :class="{ on: chartMode === \'usage\' }" @click="chartMode = \'usage\'">{{ t("chart_usage") }}</button>',
    '          <button type="button" :class="{ on: chartMode === \'cost\' }" @click="chartMode = \'cost\'">{{ t("chart_cost") }}</button>',
    '        </div>',
    '      </div>',
    '      <div v-if="chart.empty" class="qvq-empty">{{ t("usage_empty") }}</div>',
    '      <div v-else class="qvq-chart-wrap" @mousemove="chartHover" @mouseleave="tip = null">',
    '        <div class="qvq-chart" v-html="chart.svg"></div>',
    '        <div class="qvq-chart-tip" v-if="tip" :style="{ left: tip.left + \'px\' }" v-html="tip.html"></div>',
    '      </div>',
    '      <div class="qvq-chart-legend" v-if="chartMode === \'usage\' && (usage && usage.limit)">{{ limitLegend }}</div>',
    '      <div class="qvq-chart-legend qvq-cost-toggle" v-if="chartMode === \'cost\' && modelCosts.length">',
    '        <button type="button" class="qvq-link" @click="costModelsOpen = !costModelsOpen">',
    '          {{ t("cost_by_model") }} · ${{ costTotalText }} {{ costModelsOpen ? "▾" : "▸" }}</button>',
    '      </div>',
    '      <div class="cost-models" v-if="chartMode === \'cost\' && costModelsOpen">',
    '        <div v-for="m in modelCosts" :key="m.id" class="cost-model-row">',
    '          <span class="nm" :title="m.id">{{ m.id }}</span>',
    '          <span class="cost-model-bar"><i :style="{ width: m.pct + \'%\' }"></i></span>',
    '          <span class="amt">${{ m.text }}<i class="pct">{{ m.pct }}%</i></span>',
    '        </div>',
    '      </div>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-head">',
    '        <span class="qvq-card-title">{{ t("home_recent") }}</span>',
    '        <button type="button" class="qvq-link" @click="go(\'sessions\')">{{ t("nav_sessions") }}</button>',
    '      </div>',
    '      <div v-if="!recent.length" class="qvq-empty">-</div>',
    '      <button v-for="s in recent" :key="s.chat_key" type="button" class="qvq-row"',
    '              @click="openSession(s.chat_key)">',
    '        <span class="qvq-row-name">{{ s.name || s.chat_key }}</span>',
    '        <span class="qvq-row-meta">{{ s.turns || 0 }}</span>',
    '      </button>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-head">',
    '        <span class="qvq-card-title">{{ t("home_upcoming") }}</span>',
    '        <button type="button" class="qvq-link" @click="go({ go: \'tasks\' })">{{ t("nav_tasks") }}</button>',
    '      </div>',
    '      <div v-if="!upcoming.length" class="qvq-empty">{{ t("home_upcoming_empty") }}</div>',
    '      <button v-for="task in upcoming" :key="task.id" type="button" class="qvq-row"',
    '              @click="go({ go: \'tasks\' })">',
    '        <span class="qvq-row-name">{{ taskLabel(task) }}</span>',
    '        <span class="qvq-row-meta task-next" :class="{ overdue: isOverdue(task) }">',
    '          {{ isOverdue(task) ? t("task_overdue") + " " : t("task_next") + " " }}{{ task.next_formatted || task.schedule_raw || "-" }}</span>',
    '      </button>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-head">',
    '        <span class="qvq-card-title">{{ t("orch_running") }}</span>',
    '        <button type="button" class="qvq-link" @click="go({ go: \'orchestrate\' })">{{ t("nav_orchestrate") }}</button>',
    '      </div>',
    '      <div v-if="!runningRows.length" class="qvq-empty">{{ t("running_none") }}</div>',
    '      <button v-for="(r, i) in runningRows" :key="r.session || i" type="button" class="qvq-row"',
    '              @click="openSession(r.session)">',
    '        <span class="qvq-row-name"><span class="live-dot" :class="{ idle: r.status !== \'running\' }"></span> {{ r.session }}<i v-if="r.agent === \'sub\'" class="chat-subtag hv">{{ t("sub_badge") }}</i></span>',
    '        <span class="qvq-row-meta">{{ r.status }}</span>',
    '      </button>',
    '    </n-card>',
    '  </div>',
    '  <n-modal v-model:show="limitOpen" preset="card" class="qvq-modal-card" style="max-width:380px"',
    '           :title="t(\'limit_edit_title\')" :bordered="false">',
    '    <div class="qvq-modal-label">{{ t("limit_edit_label") }}</div>',
    '    <n-input-number v-model:value="limitDraft" :min="0" :step="10000" style="width:100%"',
    '                    :show-button="false"/>',
    '    <div class="qvq-modal-hint">{{ t("limit_edit_hint") }}</div>',
    '    <div class="qvq-modal-row">',
    '      <div class="qvq-modal-row-tx">',
    '        <div class="qvq-modal-row-title">{{ t("limit_auto_budget") }}</div>',
    '        <div class="qvq-modal-hint" style="margin-top:2px">{{ t("limit_auto_budget_hint") }}</div>',
    '      </div>',
    '      <n-switch v-model:value="budgetAuto"/>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="limitOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" @click="saveLimit">{{ t("save") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '</div>',
  ].join(""),
};
