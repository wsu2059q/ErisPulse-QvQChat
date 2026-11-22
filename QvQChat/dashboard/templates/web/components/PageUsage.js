/* 用量：token 消费去哪了——KPI/来源构成 / 趋势 / 模型分布 / 会话分布 / 预算 / 调用流水 */
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
      loading: true,
    };
  },
  computed: {
    today() {
      return this.days.length ? this.days[this.days.length - 1] : null;
    },
    byModel() {
      // 区间累计 by_model：[{model, tokens, in, out}] 按 tokens 倒序
      var acc = {};
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
      list.forEach(function (x) { x.pct = Math.round(x.tokens * 100 / total); });
      return list;
    },
    byOrigin() {
      // 区间累计来源构成（对话/面板/定时任务/主动发言/子智能体/让渡）
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
      // 来源构成堆叠条：conic-gradient 五色（分类柔色板）
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
      // 区间 tokens 柱状（高度按最大值归一）
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
      // 区间累计 by_chat top 8：[{chat_key, tokens, pct}]
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
      // 用户消耗 top（user_daily_budget 进度数据源）
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
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      QvQ.swr(self, "usage_page:" + this.rangeDays, "/api/qvq/usage?days=" + this.rangeDays + "&flow=2", function (d) {
        self.days = (d && d.days) || [];
        self.limit = (d && d.limit) || 0;
        self.userLimit = (d && d.user_limit) || 0;
        self.flow = (d && d.flow) || [];
      });
      api("/api/qvq/sessions?limit=200").then(function (d) {
        // 会话预算进度：只列设了 session_budget 的会话（今日 by_chat 对比）
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
    fmtNum(n) { return Number(n || 0).toLocaleString(); },
    chatName(key) {
      var hit = this.budgets.filter(function (r) { return r.chat_key === key; })[0];
      return (hit && hit.name) || key;
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
    '      <div class="qvq-page-title">{{ t("nav_usage") }}</div>',
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
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <template v-else>',
    '    <div class="us-kpis">',
    '      <div class="us-kpi">',
    '        <div class="v">{{ fmtNum(today ? today.tokens : 0) }}</div>',
    '        <div class="l">{{ t("usage_today_tokens") }}</div>',
    '      </div>',
    '      <div class="us-kpi">',
    '        <div class="v">{{ fmtNum(today ? today.calls : 0) }}</div>',
    '        <div class="l">{{ t("usage_today_calls") }}</div>',
    '      </div>',
    '      <div class="us-kpi">',
    '        <div class="v">{{ fmtNum(limit) }}</div>',
    '        <div class="l">{{ t("usage_daily_limit") }}</div>',
    '      </div>',
    '    </div>',
    '    <n-card size="small" class="qvq-glass-card" v-if="byOrigin.length">',
    '      <div class="qvq-card-title">{{ t("usage_origin_title") }}</div>',
    '      <div class="us-origin-bar" :style="{ background: originBar }"></div>',
    '      <div class="us-origin-legend">',
    '        <span v-for="(o, i) in byOrigin" :key="o.origin" class="lg">',
    '          <i :style="{ background: originColor(i) }"></i>{{ originLabel(o.origin) }} · {{ o.pct }}%</span>',
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
    '        <div class="qvq-card-title">{{ t("usage_models_title") }}</div>',
    '        <div class="us-donut-wrap" v-if="byModel.length">',
    '          <div class="us-donut" :style="{ background: donutStyle }"><i>{{ byModel.length }}</i></div>',
    '          <div class="us-donut-legend">',
    '            <span v-for="m in byModel" :key="m.model" class="lg"><i :class="lgClass(m)"></i>{{ m.model }} · {{ m.pct }}%</span>',
    '          </div>',
    '        </div>',
    '        <div v-if="!byModel.length" class="qvq-empty">{{ t("usage_empty") }}</div>',
    '        <div v-for="m in byModel" :key="m.model" class="us-row">',
    '          <span class="nm" :title="m.model">{{ m.model }}</span>',
    '          <div class="us-bar"><i :style="{ width: m.pct + \'%\' }"></i></div>',
    '          <span class="v">{{ fmtNum(m.tokens) }} <i class="io">↑{{ fmtNum(m.in) }} ↓{{ fmtNum(m.out) }}</i></span>',
    '        </div>',
    '      </n-card>',
    '      <n-card size="small" class="qvq-glass-card">',
    '        <div class="qvq-card-title">{{ t("usage_chats_title") }}</div>',
    '        <div v-if="!byChat.length" class="qvq-empty">{{ t("usage_empty") }}</div>',
    '        <div v-for="c in byChat" :key="c.chat_key" class="us-row us-click" @click="openSession(c.chat_key)" :title="c.chat_key">',
    '          <span class="nm">{{ chatName(c.chat_key) }}</span>',
    '          <div class="us-bar"><i :style="{ width: c.pct + \'%\' }"></i></div>',
    '          <span class="v">{{ fmtNum(c.tokens) }}</span>',
    '        </div>',
    '      </n-card>',
    '    </div>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-title">{{ t("usage_budget_title") }}</div>',
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
    '        </div>',
    '      </template>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-title">{{ t("usage_records_title") }}</div>',
    '      <div v-if="!flow.length" class="qvq-empty">{{ t("usage_records_empty") }}</div>',
    '      <div v-for="(x, i) in flow" :key="i" class="us-rec">',
    '        <div class="r1">',
    '          <button type="button" class="nm" @click="openSession(x.chat_key)"',
    '                  :title="x.chat_key">{{ chatName(x.chat_key) }}</button>',
    '          <span class="us-origin-pill" :data-o="x.origin">{{ originLabel(x.origin) }}</span>',
    '          <span class="meta">{{ x.model }} · ↑{{ fmtNum(x.in) }} ↓{{ fmtNum(x.out) }} · {{ fmtTs(x.ts) }}</span>',
    '        </div>',
    '      </div>',
    '    </n-card>',
    '  </template>',
    '</div>',
  ].join(""),
};
