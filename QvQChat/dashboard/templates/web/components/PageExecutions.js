/* 执行记录：跨会话 AI 活动流水（模型 / token / 摘要），点击跳对应会话 */
window.PageExecutions = {
  name: "PageExecutions",
  data() {
    return {
      items: [],
      loading: true,
      day: "",
    };
  },
  computed: {
    days() {
      var seen = [];
      this.items.forEach(function (x) {
        var d = new Date((x.ts || 0) * 1000);
        var k = d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
        if (seen.indexOf(k) < 0) seen.push(k);
      });
      return seen.slice(0, 7);
    },
    shown() {
      if (!this.day) return this.items;
      var want = this.day;
      return this.items.filter(function (x) {
        var d = new Date((x.ts || 0) * 1000);
        return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate() === want;
      });
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      return QvQ.swr(self, "executions", "/api/qvq/executions", function (d) {
        self.items = (d && d.items) || [];
      });
    },
    fmtTs(ts) {
      if (!ts) return "";
      var d = new Date(ts * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return (d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
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
    '      <div class="qvq-page-title">{{ t("nav_executions") }}</div>',
    '      <div class="qvq-page-sub">{{ t("exec_sub") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-button size="small" @click="load">{{ t("refresh") }}</n-button>',
    '    </div>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <template v-else>',
    '    <div class="exec-day-row" v-if="days.length > 1">',
    '      <button type="button" class="sess-acct-chip" :class="{ on: day === \'\' }" @click="day = \'\'">',
    '        {{ t("exec_all") }}</button>',
    '      <button v-for="d in days" :key="d" type="button" class="sess-acct-chip"',
    '              :class="{ on: day === d }" @click="day = d">{{ d }}</button>',
    '    </div>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div v-for="(x, i) in shown" :key="i" class="trash-row exec-row">',
    '        <button type="button" class="nm exec-name" @click="openSession(x.chat_key)"',
    '                :title="x.chat_key">{{ x.name }}</button>',
    '        <span class="qvq-meta-line exec-prev">{{ x.preview }}</span>',
    '        <span class="qvq-meta-line exec-meta">',
    '          <template v-if="x.model">{{ x.model }}</template>',
    '          <template v-if="x.tokens"> · {{ Number(x.tokens).toLocaleString() }} tok</template>',
    '          · {{ fmtTs(x.ts) }}</span>',
    '      </div>',
    '      <div v-if="!shown.length" class="qvq-empty">{{ t("exec_empty") }}</div>',
    '    </n-card>',
    '  </template>',
    '</div>',
  ].join(""),
};
