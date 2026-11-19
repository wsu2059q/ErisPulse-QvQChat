/* 用量：token 消费去哪了——今日汇总 / 模型分布 / 会话分布 / 最近调用明细 */
window.PageUsage = {
  name: "PageUsage",
  data() {
    return {
      days: [],
      limit: 0,
      records: [],
      loading: true,
    };
  },
  computed: {
    today() {
      return this.days.length ? this.days[this.days.length - 1] : null;
    },
    byModel() {
      // 14 天累计 by_model：[{model, tokens, in, out}] 按 tokens 倒序
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
    chartBars() {
      // 14 天 tokens 柱状（高度按最大值归一）
      var days = this.days || [];
      var max = Math.max.apply(null, days.map(function (d) { return Number(d.tokens || 0); }).concat([1]));
      return days.map(function (d) {
        return { date: d.date, tokens: Number(d.tokens || 0), h: Math.max(2, Math.round(Number(d.tokens || 0) * 100 / max)) };
      });
    },
    donutStyle() {
      // 模型分布环形图：conic-gradient 按占比扇形铺色
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
      // 14 天累计 by_chat top 8：[{chat_key, tokens, pct}]
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
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      QvQ.swr(self, "usage_page", "/api/qvq/usage", function (d) {
        self.days = (d && d.days) || [];
        self.limit = (d && d.limit) || 0;
      });
      QvQ.swr(self, "usage_records", "/api/qvq/usage/records", function (d) {
        self.records = (d && d.items) || [];
      });
    },
    lgClass(m) {
      var idx = this.byModel.indexOf(m) % 5;
      return "c" + idx;
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
      var hit = this.records.filter(function (r) { return r.chat_key === key; })[0];
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
    '      <div class="qvq-card-title">{{ t("usage_records_title") }}</div>',
    '      <div v-if="!records.length" class="qvq-empty">{{ t("usage_records_empty") }}</div>',
    '      <div v-for="(x, i) in records" :key="i" class="us-rec">',
    '        <div class="r1">',
    '          <button type="button" class="nm" @click="openSession(x.chat_key)"',
    '                  :title="x.chat_key">{{ x.name }}</button>',
    '          <span class="meta">{{ x.model }} · {{ fmtNum(x.tokens) }} tok · {{ fmtTs(x.ts) }}</span>',
    '        </div>',
    '        <div class="r2">{{ x.preview }}</div>',
    '      </div>',
    '    </n-card>',
    '  </template>',
    '</div>',
  ].join(""),
};
