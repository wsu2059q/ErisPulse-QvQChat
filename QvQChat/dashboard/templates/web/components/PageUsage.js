/* 用量：token 消费去哪了——告警置顶 / KPI / 来源构成 / 趋势 / 模型分布（成本+下钻）/ 会话分布 / 预算（可改）/ 调用流水（可筛可导出） */
window.PageUsage = {
  name: "PageUsage",
  data() {
    return {
      days: [],
      limit: 0,
      userLimit: 0,
      flow: [],
      rangeDays: 14,
      budgets: [],
      costs: {},
      updatedAt: 0,
      loading: true,
      // 明细联动筛选（模型/来源分布行点击驱动）
      fModel: "",
      fOrigin: "",
      fToday: false,
      // 预算编辑弹窗（kind=global/session，session 行内联改限额）
      editOpen: false,
      editKind: "global",
      editChat: null,
      editValue: 0,
      editBusy: false,
    };
  },
  computed: {
    today() {
      return this.days.length ? this.days[this.days.length - 1] : null;
    },
    todayKey() {
      var d = new Date();
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
    },
    /* 超限告警（置顶）：会话/用户预算 >=80% 或全局 >=80%——看到问题第一眼 */
    alerts() {
      var out = [];
      var self = this;
      this.budgets.forEach(function (b) {
        if (b.pct >= 80) out.push({
          level: b.pct >= 100 ? "over" : "warn",
          label: b.name, pct: b.pct,
          kind: "session", chat: b,
        });
      });
      if (this.limit > 0 && this.limitPct >= 80) out.push({
        level: this.limitPct >= 100 ? "over" : "warn",
        label: t("usage_budget_global"), pct: this.limitPct, kind: "global",
      });
      out.sort(function (a, b) { return b.pct - a.pct; });
      return out;
    },
    byModel() {
      var acc = {};
      var self = this;
      (this.days || []).forEach(function (d) {
        var bm = d.by_model || {};
        Object.keys(bm).forEach(function (m) {
          var e = bm[m] || {};
          var row = acc[m] || (acc[m] = { model: m, tokens: 0, in: 0, out: 0 });
          row.tokens += Number(e.tokens || 0);
          row.in += Number(e.in || 0);
          row.out += Number(e.out || 0);
        });
      });
      var list = Object.keys(acc).map(function (m) { return acc[m]; });
      list.sort(function (a, b) { return b.tokens - a.tokens; });
      var total = list.reduce(function (s, x) { return s + x.tokens; }, 0) || 1;
      list.forEach(function (x) {
        x.pct = Math.round(x.tokens * 100 / total);
        x.cost = Number(self.costs[x.model] || 0);
      });
      return list;
    },
    costTotal() {
      return this.byModel.reduce(function (s, x) { return s + Number(x.cost || 0); }, 0);
    },
    byOrigin() {
      var acc = {};
      (this.days || []).forEach(function (d) {
        var bo = d.by_origin || {};
        Object.keys(bo).forEach(function (k) {
          var e = bo[k] || {};
          acc[k] = (acc[k] || 0) + Number(e.tokens || 0);
        });
      });
      var list = Object.keys(acc).map(function (k) { return { origin: k, tokens: acc[k] }; });
      list.sort(function (a, b) { return b.tokens - a.tokens; });
      var total = list.reduce(function (s, x) { return s + x.tokens; }, 0) || 1;
      list.forEach(function (x) { x.pct = Math.round(x.tokens * 100 / total); });
      return list;
    },
    originBar() {
      var colors = ["var(--qvq-accent)", "var(--qvq-cat-1)", "var(--qvq-cat-2)", "var(--qvq-cat-3)", "var(--qvq-cat-4)", "var(--qvq-tx-t)"];
      var segs = [];
      var acc = 0;
      var list = this.byOrigin;
      for (var i = 0; i < list.length; i++) {
        var pct = Number(list[i].pct || 0);
        segs.push(colors[i % colors.length] + " " + acc + "% " + (acc + pct) + "%");
        acc += pct;
      }
      if (acc < 100 && segs.length) segs.push("var(--qvq-bg-s) " + acc + "% 100%");
      return segs.length ? "conic-gradient(" + segs.join(", ") + ")" : "none";
    },
    originColor(i) {
      var colors = ["var(--qvq-accent)", "var(--qvq-cat-1)", "var(--qvq-cat-2)", "var(--qvq-cat-3)", "var(--qvq-cat-4)", "var(--qvq-tx-t)"];
      return colors[i % colors.length];
    },
    chartBars() {
      var days = this.days || [];
      var max = Math.max.apply(null, days.map(function (d) { return Number(d.tokens || 0); }).concat([1]));
      return days.map(function (d) {
        return { date: d.date, tokens: Number(d.tokens || 0), h: Math.max(2, Math.round(Number(d.tokens || 0) * 100 / max)) };
      });
    },
    donutStyle() {
      var colors = ["var(--qvq-accent)", "var(--qvq-warn)", "var(--qvq-ok)", "#9a7ade", "#5fa8d3"];
      var segs = [];
      var acc = 0;
      var list = this.byModel;
      for (var i = 0; i < list.length; i++) {
        var pct = Number(list[i].pct || 0);
        var c = colors[i % colors.length];
        segs.push(c + " " + acc + "% " + (acc + pct) + "%");
        acc += pct;
      }
      if (acc < 100 && segs.length) segs.push("var(--qvq-bg) " + acc + "% 100%");
      return segs.length ? "conic-gradient(" + segs.join(", ") + ")" : "none";
    },
    byChat() {
      var acc = {};
      (this.days || []).forEach(function (d) {
        var bc = d.by_chat || {};
        Object.keys(bc).forEach(function (k) {
          acc[k] = (acc[k] || 0) + Number(bc[k] || 0);
        });
      });
      var list = Object.keys(acc).map(function (k) { return { chat_key: k, tokens: acc[k] }; });
      list.sort(function (a, b) { return b.tokens - a.tokens; });
      list = list.slice(0, 8);
      var total = list.reduce(function (s, x) { return s + x.tokens; }, 0) || 1;
      list.forEach(function (x) { x.pct = Math.round(x.tokens * 100 / total); });
      return list;
    },
    byUserTop() {
      var acc = {};
      (this.days || []).forEach(function (d) {
        var bu = d.by_user || {};
        Object.keys(bu).forEach(function (k) {
          acc[k] = (acc[k] || 0) + Number(bu[k] || 0);
        });
      });
      var list = Object.keys(acc).map(function (k) { return { user: k, tokens: acc[k] }; });
      list.sort(function (a, b) { return b.tokens - a.tokens; });
      return list.slice(0, 5);
    },
    limitPct() {
      var today = this.today;
      return this.limit > 0 ? Math.min(100, Math.round(Number(today ? today.tokens : 0) * 100 / this.limit)) : 0;
    },
    userPct() {
      var top = this.byUserTop[0];
      return this.userLimit > 0 ? Math.min(100, Math.round(Number(top ? top.tokens : 0) * 100 / this.userLimit)) : 0;
    },
    /* 明细：联动筛选（模型/来源/仅今天）后倒序 */
    shownFlow() {
      var fModel = this.fModel;
      var fOrigin = this.fOrigin;
      var todayKey = this.todayKey;
      return (this.flow || []).filter(function (x) {
        if (fModel && x.model !== fModel) return false;
        if (fOrigin && x.origin !== fOrigin) return false;
        return true;
      }).sort(function (a, b) { return b.ts - a.ts; }).slice(0, 60);
    },
    flowFilterOn() {
      return !!(this.fModel || this.fOrigin);
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      QvQ.swr(self, "usage_page:" + this.rangeDays, "/api/qvq/usage?days=" + this.rangeDays + "&flow=7", function (d) {
        self.days = (d && d.days) || [];
        self.limit = (d && d.limit) || 0;
        self.userLimit = (d && d.user_limit) || 0;
        self.flow = (d && d.flow) || [];
        self.updatedAt = Date.now();
      });
      api("/api/qvq/costs").then(function (d) {
        self.costs = (d && d.by_model) || {};
      });
      api("/api/qvq/sessions?limit=200").then(function (d) {
        var today = self.today ? (self.today.by_chat || {}) : {};
        self.budgets = ((d && d.sessions) || [])
          .filter(function (s) { return s.policy && Number(s.policy.session_budget || 0) > 0; })
          .map(function (s) {
            var used = Number(today[s.chat_key] || 0);
            var cap = Number(s.policy.session_budget || 0);
            return { chat_key: s.chat_key, name: s.name || s.chat_key, used: used, cap: cap, pct: Math.min(100, Math.round(used * 100 / cap)) };
          })
          .sort(function (a, b) { return b.pct - a.pct; })
          .slice(0, 5);
      });
    },
    setRange(n) {
      this.rangeDays = n;
      this.load();
    },
    /* KPI 下钻：今日 tokens → 明细过滤今天（流水带 origin，滚到明细） */
    drillTodayTokens() {
      this.clearFilter();
      this.fOrigin = "chat";
      this.$nextTick(function () {
        var el = document.getElementById("us-flow");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    },
    /* 下钻联动：模型/来源分布行点击 → 明细过滤；再点同项取消 */
    drillModel(m) {
      this.fModel = this.fModel === m ? "" : m;
      this.fOrigin = "";
      this.$nextTick(function () {
        var el = document.getElementById("us-flow");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    },
    drillOrigin(o) {
      this.fOrigin = this.fOrigin === o ? "" : o;
      this.fModel = "";
      this.$nextTick(function () {
        var el = document.getElementById("us-flow");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    },
    clearFilter() {
      this.fModel = "";
      this.fOrigin = "";
    },
    /* KPI 可点：上限 → 直接改 */
    openEditGlobal() {
      this.editKind = "global";
      this.editChat = null;
      this.editValue = this.limit;
      this.editOpen = true;
    },
    openEditBudget(b) {
      this.editKind = "session";
      this.editChat = b;
      this.editValue = b.cap;
      this.editOpen = true;
    },
    saveBudget() {
      var self = this;
      this.editBusy = true;
      var done = function () {
        self.editBusy = false;
        self.editOpen = false;
        QvQ.toast(t("usage_budget_saved"));
        self.updatedAt = 0; // 失效 swr 缓存时间戳显示
        self.load();
      };
      if (this.editKind === "global") {
        api("/api/qvq/config", "POST", { daily_token_limit: Number(this.editValue) || 0 }).then(done);
      } else {
        api("/api/qvq/session/policy", "POST", {
          chat_key: this.editChat.chat_key, session_budget: Number(this.editValue) || 0,
        }).then(done);
      }
    },
    alertAct(a) {
      if (a.kind === "session") this.openEditBudget(a.chat);
      else this.openEditGlobal();
    },
    exportCsv() {
      var esc = function (v) {
        var s = String(v == null ? "" : v);
        return '"' + s.replace(/"/g, '""') + '"';
      };
      var head = ["ts", "chat_key", "origin", "model", "in", "out"];
      var rows = this.shownFlow.map(function (x) {
        return head.map(function (k) {
          return esc(k === "ts" ? new Date(Number(x.ts) * 1000).toISOString().slice(0, 19) : x[k]);
        }).join(",");
      });
      var blob = new Blob(["\ufeff" + [head.join(",")].concat(rows).join("\n")], { type: "text/csv;charset=utf-8" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "usage_flow.csv";
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
    },
    lgClass(m) {
      var idx = this.byModel.indexOf(m) % 5;
      return "c" + idx;
    },
    originLabel(o) {
      var keys = { chat: "usage_origin_chat", dashboard: "usage_origin_dashboard", task: "usage_origin_task", proactive: "usage_origin_proactive", subagent: "usage_origin_subagent", handover: "usage_origin_handover" };
      return t(keys[o] || o);
    },
    colTitle(b) {
      return b.date + " · " + this.fmtNum(b.tokens);
    },
    fmtTs(ts) {
      if (!ts) return "";
      var d = new Date(ts * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return (d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
    },
    fmtUpdated() {
      if (!this.updatedAt) return "";
      var d = new Date(this.updatedAt);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return p(d.getHours()) + ":" + p(d.getMinutes());
    },
    fmtNum(n) { return Number(n || 0).toLocaleString(); },
    fmtCost(n) { return "$" + Number(n || 0).toFixed(2); },
    chatName(key) {
      var hit = this.budgets.filter(function (r) { return r.chat_key === key; })[0];
      if (hit) return hit.name;
      var c = this.byChat.filter(function (r) { return r.chat_key === key; })[0];
      return (c && c.name) || key;
    },
    openSession(key) {
      QvQ.store.pendingChat = key;
      QvQ.store.page = "chat";
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_usage") }}',
    '        <span class="qvq-meta-line" v-if="fmtUpdated()">{{ t("usage_updated_at").replace("{t}", fmtUpdated()) }}</span></div>',
    '      <div class="qvq-page-sub">{{ t("usage_sub") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <div class="qvq-seg">',
    '        <button type="button" :class="{ on: rangeDays === 7 }" @click="setRange(7)">{{ t("usage_range_7d") }}</button>',
    '        <button type="button" :class="{ on: rangeDays === 14 }" @click="setRange(14)">{{ t("usage_range_14d") }}</button>',
    '        <button type="button" :class="{ on: rangeDays === 30 }" @click="setRange(30)">{{ t("usage_range_30d") }}</button>',
    '      </div>',
    '      <n-button size="small" @click="load">{{ t("refresh") }}</n-button>',
    '    </div>',
    '  </div>',
    '  <div class="us-alert" v-for="(a, i) in alerts" :key="i" :class="a.level">',
    '    <span class="us-alert-ico">!</span>',
    '    <span class="us-alert-tx"><b>{{ a.label }}</b> {{ t("usage_alert_over").replace("{p}", a.pct) }}</span>',
    '    <button type="button" class="prov-act" @click="alertAct(a)">{{ t("usage_alert_act") }}</button>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <template v-else>',
    '    <div class="us-kpis">',
    '      <button type="button" class="us-kpi us-kpi-btn" @click="drillTodayTokens">',
    '        <div class="v">{{ fmtNum(today ? today.tokens : 0) }}</div>',
    '        <div class="l">{{ t("usage_today_tokens") }} →</div>',
    '      </button>',
    '      <div class="us-kpi">',
    '        <div class="v">{{ fmtNum(today ? today.calls : 0) }}</div>',
    '        <div class="l">{{ t("usage_today_calls") }}</div>',
    '      </div>',
    '      <button type="button" class="us-kpi us-kpi-btn" :title="t(\'usage_edit_limit_tip\')" @click="openEditGlobal">',
    '        <div class="v">{{ fmtNum(limit) }}</div>',
    '        <div class="l">{{ t("usage_daily_limit") }} ✎</div>',
    '      </button>',
    '    </div>',
    '    <n-card size="small" class="qvq-glass-card" v-if="byOrigin.length">',
    '      <div class="qvq-card-title">{{ t("usage_origin_title") }}',
    '        <span class="qvq-meta-line">{{ t("usage_origin_hint") }}</span></div>',
    '      <div class="us-origin-bar" :style="{ background: originBar }"></div>',
    '      <div class="us-origin-legend">',
    '        <button v-for="(o, i) in byOrigin" :key="o.origin" type="button" class="lg"',
    '                :class="{ on: fOrigin === o.origin }" @click="drillOrigin(o.origin)">',
    '          <i :style="{ background: originColor(i) }"></i>{{ originLabel(o.origin) }} · {{ o.pct }}%</button>',
    '      </div>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card us-chart-card">',
    '      <div class="qvq-card-title">{{ t("usage_chart_title") }}</div>',
    '      <div class="us-chart">',
    '        <div v-for="b in chartBars" :key="b.date" class="us-col" :title="colTitle(b)">',
    '          <i :style="{ height: b.h + \'%\' }"></i>',
    '          <span>{{ b.date.slice(5) }}</span>',
    '        </div>',
    '      </div>',
    '    </n-card>',
    '    <div class="us-grid">',
    '      <n-card size="small" class="qvq-glass-card">',
    '        <div class="qvq-card-title">{{ t("usage_models_title") }}',
    '          <span class="qvq-meta-line" v-if="costTotal">{{ fmtCost(costTotal) }} · {{ t("usage_cost_est") }}</span></div>',
    '        <div class="us-donut-wrap" v-if="byModel.length">',
    '          <div class="us-donut" :style="{ background: donutStyle }"><i>{{ byModel.length }}</i></div>',
    '          <div class="us-donut-legend">',
    '            <span v-for="m in byModel" :key="m.model" class="lg"><i :class="lgClass(m)"></i>{{ m.model }} · {{ m.pct }}%</span>',
    '          </div>',
    '        </div>',
    '        <div v-if="!byModel.length" class="qvq-empty">{{ t("usage_empty") }}</div>',
    '        <button v-for="m in byModel" :key="m.model" type="button" class="us-row us-click us-drill"',
    '                :class="{ on: fModel === m.model }" @click="drillModel(m.model)" :title="t(\'usage_drill_tip\')">',
    '          <span class="nm" :title="m.model">{{ m.model }}</span>',
    '          <div class="us-bar"><i :style="{ width: m.pct + \'%\' }"></i></div>',
    '          <span class="v">{{ fmtNum(m.tokens) }}<i class="io">↑{{ fmtNum(m.in) }} ↓{{ fmtNum(m.out) }}</i><i v-if="m.cost" class="io cost">{{ fmtCost(m.cost) }}</i></span>',
    '        </button>',
    '      </n-card>',
    '      <n-card size="small" class="qvq-glass-card">',
    '        <div class="qvq-card-title">{{ t("usage_chats_title") }}</div>',
    '        <div v-if="!byChat.length" class="qvq-empty">{{ t("usage_empty") }}</div>',
    '        <button v-for="c in byChat" :key="c.chat_key" type="button" class="us-row us-click" @click="openSession(c.chat_key)" :title="c.chat_key">',
    '          <span class="nm">{{ chatName(c.chat_key) }}</span>',
    '          <div class="us-bar"><i :style="{ width: c.pct + \'%\' }"></i></div>',
    '          <span class="v">{{ fmtNum(c.tokens) }}</span>',
    '        </button>',
    '      </n-card>',
    '    </div>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-title">{{ t("usage_budget_title") }}',
    '        <button type="button" class="qvq-link" @click="openEditGlobal">{{ t("usage_budget_edit_global") }}</button></div>',
    '      <div v-if="!limit && !userLimit && !budgets.length" class="qvq-empty">{{ t("usage_budget_none") }}</div>',
    '      <template v-else>',
    '        <div class="us-row" v-if="limit">',
    '          <span class="nm">{{ t("usage_budget_global") }}</span>',
    '          <div class="us-bar"><i :class="{ warn: limitPct >= 80 }" :style="{ width: limitPct + \'%\' }"></i></div>',
    '          <span class="v">{{ limitPct }}%</span>',
    '        </div>',
    '        <div class="us-row" v-if="userLimit" :title="byUserTop.length ? byUserTop[0].user : \'\'">',
    '          <span class="nm">{{ t("usage_budget_user") }}<code v-if="byUserTop.length" class="us-io-user">{{ byUserTop[0].user }}</code></span>',
    '          <div class="us-bar"><i :class="{ warn: userPct >= 80 }" :style="{ width: userPct + \'%\' }"></i></div>',
    '          <span class="v">{{ userPct }}%</span>',
    '        </div>',
    '        <div class="us-row" v-for="b in budgets" :key="b.chat_key" :title="b.chat_key">',
    '          <span class="nm">{{ b.name }}</span>',
    '          <div class="us-bar"><i :class="{ warn: b.pct >= 80 }" :style="{ width: b.pct + \'%\' }"></i></div>',
    '          <span class="v">{{ fmtNum(b.used) }} / {{ fmtNum(b.cap) }}</span>',
    '          <button type="button" class="prov-act" @click="openEditBudget(b)">✎</button>',
    '        </div>',
    '      </template>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card" id="us-flow">',
    '      <div class="qvq-card-title">{{ t("usage_records_title") }}',
    '        <span class="us-flow-filter" v-if="flowFilterOn">',
    '          <code v-if="fModel">{{ fModel }}</code>',
    '          <code v-if="fOrigin">{{ originLabel(fOrigin) }}</code>',
    '          <button type="button" class="qvq-link" @click="clearFilter">{{ t("usage_filter_clear") }}</button>',
    '        </span></div>',
    '      <div v-if="!shownFlow.length" class="qvq-empty">{{ t("usage_records_empty") }}</div>',
    '      <div v-for="(x, i) in shownFlow" :key="i" class="us-rec">',
    '        <div class="r1">',
    '          <button type="button" class="nm" @click="openSession(x.chat_key)"',
    '                  :title="x.chat_key">{{ chatName(x.chat_key) }}</button>',
    '          <span class="us-origin-pill" :data-o="x.origin">{{ originLabel(x.origin) }}</span>',
    '          <span class="meta">{{ x.model }} · ↑{{ fmtNum(x.in) }} ↓{{ fmtNum(x.out) }} · {{ fmtTs(x.ts) }}</span>',
    '        </div>',
    '      </div>',
    '    </n-card>',
    '  </template>',
    '  <n-modal v-model:show="editOpen" preset="card" class="qvq-modal-card" style="max-width:380px"',
    '           :title="editKind === \'global\' ? t(\'usage_budget_edit_global\') : t(\'usage_budget_edit_one\').replace(\'{n}\', editChat ? editChat.name : \'\')" :bordered="false">',
    '    <div class="prov-form">',
    '      <div class="prov-field">',
    '        <label>{{ editKind === \'global\' ? t("limit_edit_label") : t("sess_policy_budget_prompt") }}</label>',
    '        <n-input-number v-model:value="editValue" :min="0" :step="10000" :show-button="false" style="width:100%"/>',
    '      </div>',
    '      <div class="qvq-meta-line">{{ t("usage_budget_edit_hint") }}</div>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="editOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" :loading="editBusy" @click="saveBudget">{{ t("save") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '</div>',
  ].join(""),
};
