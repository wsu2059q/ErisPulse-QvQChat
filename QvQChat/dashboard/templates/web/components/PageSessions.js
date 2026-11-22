/* 会话管理：列表 / 搜索 / 归档 / 回收站 / 批量删除（会话级配置在对话页侧栏） */
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
    };
  },
  computed: {
    allPicked() {
      return this.rows.length > 0 && this.picked.length === this.rows.length;
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
      this.ask(t("session_delete_confirm"), function () {
        api("/api/qvq/sessions/delete", "POST", { chat_key: key }).then(function () { self.load(); });
      });
    },
    delPicked() {
      var self = this;
      if (!this.picked.length) return;
      this.ask(t("session_delete_confirm") + " (" + this.picked.length + ")", function () {
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
    '        <th style="width:90px">{{ t("col_count") }}</th>',
    '        <th style="width:120px"></th>',
    '      </tr></thead>',
    '      <tbody>',
    '        <tr v-for="r in rows" :key="r.chat_key">',
    '          <td v-if="picking"><n-checkbox :checked="picked.indexOf(r.chat_key) >= 0" @update:checked="togglePick(r.chat_key)"/></td>',
    '          <td><button type="button" class="sess-name" @click="open(r.chat_key)">',
    '            {{ r.name || r.chat_key }}<i>{{ r.chat_key }}</i></button></td>',
    '          <td>{{ r.turns || 0 }}</td>',
    '          <td v-if="!picking"><button type="button" class="prov-act danger" @click="delOne(r.chat_key)">{{ t("chat_delete") }}</button></td>',
    '        </tr>',
      '      </tbody>',
    '    </table>',
    '    </div>',
    '    <div v-if="!loading && !rows.length" class="qvq-empty">-</div>',
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
    '</div>',
  ].join(""),
};
