/* 会话管理：列表 / 搜索 / 归档 / 回收站 / 批量删除（会话级配置在对话页侧栏）
   可操作性：整行点击进对话；行内策略 chips（屏蔽开关 / 优先级三态 / 限额徽标改额）；
   归档视图行内「恢复」；列头点击按轮次 / 更新时间排序（再点切换方向，三次取消）。
   i18n（新键，待主线补入 i18n.js）:
     sess_pol_col=策略, sess_restore_done=已恢复该会话, sess_budget_title=会话每日限额 */
window.PageSessions = {
  name: "PageSessions",
  data() {
    return {
      q: "",
      view: "active",
      rows: [],
      total: 0,
      picked: [],
      picking: false,
      trash: [],
      confirmOpen: false,
      confirmText: "",
      confirmAction: null,
      loading: false,
      start: 0,
      observer: null,
      sortBy: "",
      sortDir: -1,
      budgetOpen: false,
      budgetKey: "",
      budgetVal: 0,
      budgetBusy: false,
    };
  },
  computed: {
    allPicked() {
      return this.rows.length > 0 && this.picked.length === this.rows.length;
    },
    sortedRows() {
      if (!this.sortBy) return this.rows;
      var key = this.sortBy;
      var dir = this.sortDir;
      return this.rows.slice().sort(function (a, b) {
        return ((Number(a[key]) || 0) - (Number(b[key]) || 0)) * dir;
      });
    },
  },
  mounted() {
    this.load();
  },
  beforeUnmount() {
    if (this.observer) this.observer.disconnect();
  },
  methods: {
    load() {
      var self = this;
      var url = "/api/qvq/sessions?limit=200";
      if (this.view === "archived") url += "&archived=1";
      if (this.q.trim()) url += "&q=" + encodeURIComponent(this.q.trim());
      this.start = 0;
      return QvQ.swr(self, "sessions:" + this.view + ":" + this.q.trim(), url, function (d) {
        self.rows = (d && d.sessions) || [];
        self.total = (d && d.total) || 0;
        self.picked = [];
        self.$nextTick(self.watchSentinel);
      });
    },
    more() {
      if (this.rows.length >= this.total || this.loading) return;
      var self = this;
      this.start += 200;
      var url = "/api/qvq/sessions?limit=200&start=" + this.start;
      if (this.view === "archived") url += "&archived=1";
      if (this.q.trim()) url += "&q=" + encodeURIComponent(this.q.trim());
      api(url).then(function (d) {
        var page = (d && d.sessions) || [];
        self.rows = self.rows.concat(page);
        self.$nextTick(self.watchSentinel);
      });
    },
    watchSentinel() {
      var self = this;
      if (this.observer || !("IntersectionObserver" in window)) return;
      var sentinel = this.$el.querySelector(".scroll-sentinel");
      if (!sentinel) return;
      this.observer = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting && self.rows.length < self.total && !self.loading) self.more();
      }, { root: this.$el.closest(".qvq-main"), rootMargin: "300px" });
      this.observer.observe(sentinel);
    },
    switchView(v) {
      this.view = v;
      this.picking = false;
      this.picked = [];
      if (v === "trash") return this.loadTrash();
      this.load();
    },
    exitPicking() {
      this.picking = false;
      this.picked = [];
    },
    loadTrash() {
      var self = this;
      return api("/api/qvq/trash/list").then(function (d) {
        self.trash = (d && d.items) || [];
      });
    },
    togglePick(key) {
      var i = this.picked.indexOf(key);
      if (i >= 0) this.picked.splice(i, 1);
      else this.picked.push(key);
    },
    toggleAll() {
      this.picked = this.allPicked ? [] : this.rows.map(function (r) { return r.chat_key; });
    },
    ask(text, fn) {
      this.confirmText = text;
      this.confirmAction = fn;
      this.confirmOpen = true;
    },
    delOne(key) {
      var self = this;
      this.ask(t("session_delete_trash"), function () {
        api("/api/qvq/sessions/delete", "POST", { chat_key: key }).then(function () { self.load(); });
      });
    },
    delPicked() {
      var self = this;
      if (!this.picked.length) return;
      this.ask(t("session_delete_trash") + " (" + this.picked.length + ")", function () {
        api("/api/qvq/sessions/batch-delete", "POST", { chat_keys: self.picked }).then(function () {
          self.load();
        });
      });
    },
    clearArchived() {
      var self = this;
      this.ask(t("chat_purge_archived"), function () {
        api("/api/qvq/sessions/delete-archived", "POST", {}).then(function () { self.load(); });
      });
    },
    restore(item) {
      var self = this;
      api("/api/qvq/trash/restore", "POST", { token: item.token }).then(function () {
        self.loadTrash();
      });
    },
    delTrash(item) {
      var self = this;
      this.ask(t("chat_delete"), function () {
        api("/api/qvq/trash/delete", "POST", { token: item.token }).then(function () {
          self.loadTrash();
        });
      });
    },
    open(key) {
      QvQ.store.pendingChat = key;
      QvQ.store.page = "chat";
    },
    /* 整行可点：批量模式点行=勾选，平时点行=进对话 */
    rowClick(r) {
      if (this.picking) this.togglePick(r.chat_key);
      else this.open(r.chat_key);
    },
    /* ---- 列头排序：降序 → 升序 → 取消 ---- */
    setSort(col) {
      if (this.sortBy !== col) {
        this.sortBy = col;
        this.sortDir = -1;
      } else if (this.sortDir < 0) {
        this.sortDir = 1;
      } else {
        this.sortBy = "";
        this.sortDir = -1;
      }
    },
    sortMark(col) {
      return this.sortBy === col ? (this.sortDir > 0 ? "▲" : "▼") : "";
    },
    /* ---- 行内策略 chips ---- */
    polOf(r) {
      return (r && r.policy) || {};
    },
    prioLabel(v) {
      return t(v === "high" ? "sess_policy_high" : v === "low" ? "sess_policy_low" : "sess_policy_normal");
    },
    prioOpts() {
      var self = this;
      return ["high", "normal", "low"].map(function (v) {
        return { key: v, label: self.prioLabel(v) };
      });
    },
    setPolicy(r, patch) {
      api("/api/qvq/session/policy", "POST", Object.assign({ chat_key: r.chat_key }, patch)).then(function (res) {
        r.policy = (res && res.policy) || Object.assign({}, r.policy || {}, patch);
        QvQ.toast(t("sess_policy_saved"));
      });
    },
    toggleMuted(r) {
      this.setPolicy(r, { muted: !this.polOf(r).muted });
    },
    setPrio(r, key) {
      if (!key || this.polOf(r).priority === key) return;
      this.setPolicy(r, { priority: key });
    },
    fmtBudget(n) {
      n = Number(n) || 0;
      if (n <= 0) return "";
      if (n >= 10000) {
        var w = Math.round((n / 10000) * 10) / 10;
        return (w % 1 ? w : Math.round(w)) + "万";
      }
      return String(n);
    },
    openBudget(r) {
      this.budgetKey = r.chat_key;
      this.budgetVal = Number(this.polOf(r).session_budget) || 0;
      this.budgetOpen = true;
    },
    saveBudget() {
      var self = this;
      var val = Number(this.budgetVal) || 0;
      var row = null;
      this.rows.forEach(function (r) { if (r.chat_key === self.budgetKey) row = r; });
      this.budgetBusy = true;
      api("/api/qvq/session/policy", "POST", { chat_key: this.budgetKey, session_budget: val }).then(function (res) {
        self.budgetBusy = false;
        self.budgetOpen = false;
        if (row) row.policy = (res && res.policy) || Object.assign({}, row.policy || {}, { session_budget: val });
        QvQ.toast(t("sess_policy_saved"));
      });
    },
    /* 归档视图：行内恢复（回活跃列表） */
    unarchive(r) {
      var self = this;
      api("/api/qvq/session/flags", "POST", { chat_key: r.chat_key, archived: false }).then(function () {
        QvQ.toast(t("sess_restore_done"));
        self.load();
      });
    },
    fmtUpdated(ts) {
      ts = Number(ts) || 0;
      if (!ts) return "-";
      var diff = Date.now() / 1000 - ts;
      if (diff < 90) return t("ts_just_now");
      if (diff < 3600) return t("ts_min_ago").replace("{n}", String(Math.floor(diff / 60)));
      if (diff < 86400) return Math.floor(diff / 3600) + "h";
      if (diff < 86400 * 30) return Math.floor(diff / 86400) + "d";
      var d = new Date(ts * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return (d.getMonth() + 1) + "-" + p(d.getDate());
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_sessions") }}</div>',
    '      <div class="qvq-page-sub">{{ total }} {{ t("stat_sessions") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-input v-model:value="q" size="small" clearable :placeholder="t(\'search_ph\')"',
    '               style="width:200px" @update:value="load"/>',
    '      <div class="qvq-seg">',
    '        <button type="button" :class="{ on: view === \'active\' }" @click="switchView(\'active\')">{{ t("nav_sessions") }}</button>',
    '        <button type="button" :class="{ on: view === \'archived\' }" @click="switchView(\'archived\')">{{ t("chat_archived") }}</button>',
    '        <button type="button" :class="{ on: view === \'trash\' }" @click="switchView(\'trash\')">{{ t("trash_title") }}</button>',
    '      </div>',
    '    </div>',
    '  </div>',
    '  <template v-if="view !== \'trash\'">',
    '    <div class="sess-bar" v-if="picking">',
    '      <span>{{ picked.length }}</span>',
    '      <n-button size="small" type="error" :disabled="!picked.length" @click="delPicked">{{ t("chat_delete") }}</n-button>',
    '      <n-button size="small" quaternary @click="exitPicking">{{ t("batch_exit") }}</n-button>',
    '    </div>',
    '    <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '    <div class="qvq-table-wrap" v-if="!loading">',
    '    <table class="qvq-table">',
    '      <thead><tr>',
    '        <th v-if="picking" style="width:34px"><n-checkbox :checked="allPicked" @update:checked="toggleAll"/></th>',
    '        <th>{{ t("recent_sessions") }}</th>',
    '        <th style="width:150px">{{ t("sess_pol_col") }}</th>',
    '        <th style="width:80px" class="th-sort" @click="setSort(\'turns\')">{{ t("col_turns") }}<i v-if="sortMark(\'turns\')">{{ sortMark("turns") }}</i></th>',
    '        <th style="width:90px" class="th-sort" @click="setSort(\'updated\')">{{ t("col_updated") }}<i v-if="sortMark(\'updated\')">{{ sortMark("updated") }}</i></th>',
    '        <th style="width:130px"></th>',
    '      </tr></thead>',
    '      <tbody>',
    '        <tr v-for="r in sortedRows" :key="r.chat_key" class="sess-tr" @click="rowClick(r)">',
    '          <td v-if="picking" @click.stop><n-checkbox :checked="picked.indexOf(r.chat_key) >= 0" @update:checked="togglePick(r.chat_key)"/></td>',
    '          <td><button type="button" class="sess-name" @click.stop="open(r.chat_key)">',
    '            {{ r.name || r.chat_key }}<i>{{ r.chat_key }}</i></button></td>',
    '          <td class="sess-pol" @click.stop>',
    '            <button type="button" class="sess-chip" :class="{ \'on er\': polOf(r).muted }"',
    '                    :title="t(\'sess_policy_muted\')" @click="toggleMuted(r)">{{ t("sess_policy_muted") }}</button>',
    '            <n-dropdown trigger="click" placement="bottom-start" size="small"',
    '                        :options="prioOpts()" @select="setPrio(r, $event)">',
    '              <button type="button" class="sess-chip" :class="{ on: polOf(r).priority === \'high\' || polOf(r).priority === \'low\' }"',
    '                      :title="t(\'sess_policy_priority\')">{{ prioLabel(polOf(r).priority) }}</button>',
    '            </n-dropdown>',
    '            <button v-if="fmtBudget(polOf(r).session_budget)" type="button" class="sess-chip budget"',
    '                    :title="t(\'sess_budget_title\')" @click="openBudget(r)">{{ fmtBudget(polOf(r).session_budget) }}/日</button>',
    '          </td>',
    '          <td>{{ r.turns || 0 }}</td>',
    '          <td class="qvq-meta-line">{{ fmtUpdated(r.updated) }}</td>',
    '          <td v-if="!picking" class="sess-acts" @click.stop>',
    '            <button v-if="view === \'archived\'" type="button" class="prov-act" @click="unarchive(r)">{{ t("trash_restore") }}</button>',
    '            <button type="button" class="prov-act danger" @click="delOne(r.chat_key)">{{ t("chat_delete") }}</button>',
    '          </td>',
    '        </tr>',
    '      </tbody>',
    '    </table>',
    '    </div>',
    '    <div v-if="!loading && !rows.length" class="qvq-empty">{{ t("sessions_empty") }}</div>',
    '    <div class="scroll-sentinel" v-if="rows.length && rows.length < total"></div>',
    '  </template>',
    '  <template v-else>',
    '    <div v-for="item in trash" :key="item.token" class="trash-row">',
    '      <span class="nm">[{{ item.kind }}] {{ item.summary }}</span>',
    '      <button type="button" class="prov-act" @click="restore(item)">{{ t("retry") }}</button>',
    '      <button type="button" class="prov-act danger" @click="delTrash(item)">{{ t("chat_delete") }}</button>',
    '    </div>',
    '    <div v-if="!trash.length" class="qvq-empty">-</div>',
    '  </template>',
    '  <n-modal v-model:show="confirmOpen" preset="card" class="qvq-modal-card" style="max-width:360px"',
    '           :title="t(\'confirm_title\')" :bordered="false">',
    '    <div class="qvq-modal-hint">{{ confirmText }}</div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="confirmOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="error" @click="confirmOpen = false; confirmAction && confirmAction()">',
    '          {{ t("confirm_yes") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="budgetOpen" preset="card" class="qvq-modal-card" style="max-width:360px"',
    '           :title="t(\'sess_budget_title\')" :bordered="false">',
    '    <div class="qvq-modal-hint">{{ t("sess_policy_budget_prompt") }}</div>',
    '    <n-input-number v-model:value="budgetVal" :min="0" :step="1000" size="small" style="width:100%;margin-top:8px"/>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="budgetOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" :loading="budgetBusy" @click="saveBudget">{{ t("save") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '</div>',
  ].join(""),
};
