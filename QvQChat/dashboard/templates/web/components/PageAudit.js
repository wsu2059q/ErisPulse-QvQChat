/* 审计：倒序无限滚动 / 过滤 / 批量勾选删除 / 清空 / 行详情抽屉 */
window.PageAudit = {
  name: "PageAudit",
  data() {
    return {
      rows: [], total: 0, offset: 0, q: "", picked: [], picking: false,
      busy: false, loading: false,
      detailOpen: false, detailRow: null, observer: null,
    };
  },
  computed: {
    shown() {
      var q = this.q.trim().toLowerCase();
      if (!q) return this.rows;
      return this.rows.filter(function (r) {
        return ((r.tool || "") + " " + (r.user_id || "") + " " + JSON.stringify(r.detail || {})).toLowerCase().indexOf(q) >= 0;
      });
    },
    hasMore() {
      return this.rows.length < this.total;
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
      if (!this.offset) this.loading = true;
      if (this.offset) {
        return api("/api/qvq/audit?limit=200&offset=" + this.offset).then(function (d) { self.applyPage(d); });
      }
      return QvQ.swr(self, "audit:0", "/api/qvq/audit?limit=200&offset=0", function (d) { self.applyPage(d); });
    },
    applyPage(d) {
      var self = this;
      var page = ((d && d.entries) || []).map(function (e, i) {
        e._n = self.offset + i;  // 最新在前序号（audit/delete 的 indexes 语义）
        return e;
      });
      self.rows = self.offset ? self.rows.concat(page) : page;
      self.total = (d && d.total) || 0;
      self.$nextTick(self.watchSentinel);
    },
    watchSentinel() {
      var self = this;
      if (this.observer || !("IntersectionObserver" in window)) return;
      var sentinel = this.$el.querySelector(".scroll-sentinel");
      if (!sentinel) return;
      this.observer = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting && self.hasMore && !self.loading && !self.busy) self.more();
      }, { root: this.$el.closest(".qvq-main"), rootMargin: "200px" });
      this.observer.observe(sentinel);
    },
    more() {
      if (!this.hasMore || this.loading) return;
      this.offset += 200;
      this.load();
    },
    fmt(t) {
      if (!t) return "";
      var d = new Date(Number(t) * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return (d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
    },
    detailKvs(d) {
      // 详情键值化（行内展示前 4 个键）；完整内容点行开抽屉
      var out = [];
      for (var k in (d || {})) {
        if (!Object.prototype.hasOwnProperty.call(d, k)) continue;
        var v = d[k];
        var text = typeof v === "string" ? v : JSON.stringify(v);
        if (text.length > 60) text = text.slice(0, 60) + "…";
        out.push({ k: k, v: text });
        if (out.length >= 4) break;
      }
      return out;
    },
    detailCount(d) {
      var n = 0;
      for (var k in (d || {})) n += 1;
      return n;
    },
    prettyDetail(d) {
      try { return JSON.stringify(d || {}, null, 2); } catch (e) { return String(d); }
    },
    openDetail(r) {
      if (this.picking) return;
      this.detailRow = r;
      this.detailOpen = true;
    },
    togglePick(r) {
      var i = this.picked.indexOf(r._n);
      if (i >= 0) this.picked.splice(i, 1);
      else this.picked.push(r._n);
    },
    exitPicking() {
      this.picking = false;
      this.picked = [];
    },
    delPicked() {
      var self = this;
      if (!this.picked.length) return;
      this.busy = true;
      api("/api/qvq/audit/delete", "POST", { indexes: this.picked.slice().sort(function (a, b) { return b - a; }) })
        .then(function () {
          self.busy = false;
          self.offset = 0;
          self.rows = [];
          self.exitPicking();
          self.load();
        });
    },
    clearAll() {
      var self = this;
      this.busy = true;
      api("/api/qvq/audit/delete", "POST", { clear: true }).then(function () {
        self.busy = false;
        self.offset = 0;
        self.rows = [];
        self.total = 0;
        self.exitPicking();
      });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_audit") }}</div>',
    '      <div class="qvq-page-sub">{{ total }} {{ t("audit_total") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-input v-model:value="q" size="small" clearable :placeholder="t(\'audit_filter\')" style="width:200px"/>',
    '      <template v-if="!picking">',
    '        <n-button size="small" :disabled="!rows.length" @click="picking = true">{{ t("batch_manage") }}</n-button>',
    '        <n-button size="small" type="error" ghost :loading="busy" @click="clearAll">{{ t("audit_clear") }}</n-button>',
    '      </template>',
    '    </div>',
    '  </div>',
    '  <div class="sess-bar" v-if="picking">',
    '    <span>{{ t("batch_manage") }} · {{ picked.length }}</span>',
    '    <span class="sess-bar-acts">',
    '      <n-button size="tiny" type="error" :disabled="!picked.length" :loading="busy"',
    '                @click="delPicked">{{ t("chat_delete") }}</n-button>',
    '      <n-button size="tiny" @click="exitPicking">{{ t("batch_exit") }}</n-button>',
    '    </span>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div class="qvq-table-wrap" v-if="!loading">',
    '  <table class="qvq-table">',
    '    <thead><tr>',
    '      <th v-if="picking" style="width:34px"></th>',
    '      <th style="width:130px">{{ t("col_time") }}</th>',
    '      <th style="width:150px">{{ t("col_tool") }}</th>',
    '      <th style="width:120px">{{ t("col_user") }}</th>',
    '      <th>{{ t("col_detail") }}</th>',
    '    </tr></thead>',
    '    <tbody>',
    '      <tr v-for="r in shown" :key="r._n" class="audit-row"',
    '          :class="{ dim: picking && picked.indexOf(r._n) < 0 }" @click="openDetail(r)">',
    '        <td v-if="picking" @click.stop><n-checkbox :checked="picked.indexOf(r._n) >= 0" @update:checked="togglePick(r)"/></td>',
    '        <td>{{ fmt(r.ts) }}</td>',
    '        <td><code>{{ r.tool }}</code></td>',
    '        <td>{{ r.user_id || "-" }}</td>',
    '        <td class="audit-detail">',
    '          <span class="audit-kvs">',
    '            <span v-for="(kv, i) in detailKvs(r.detail)" :key="i" class="audit-kv">',
    '              <b>{{ kv.k }}</b><code>{{ kv.v }}</code></span>',
    '            <span class="qvq-meta-line" v-if="detailCount(r.detail) > 4">+{{ detailCount(r.detail) - 4 }}</span>',
    '          </span>',
    '        </td>',
    '      </tr>',
    '    </tbody>',
    '  </table>',
    '  </div>',
    '  <div v-if="!loading && !shown.length" class="qvq-empty">-</div>',
    '  <div class="scroll-sentinel" ref="sentinel" v-if="hasMore && !picking"></div>',
    '  <n-drawer v-model:show="detailOpen" :width="440" placement="right">',
    '    <n-drawer-content :title="detailRow ? detailRow.tool : \'\'" closable>',
    '      <div class="prov-form" v-if="detailRow">',
    '        <div class="prov-field">',
    '          <label>{{ t("col_time") }} · {{ t("col_user") }}</label>',
    '          <div>{{ fmt(detailRow.ts) }} · {{ detailRow.user_id || "-" }}</div>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("col_detail") }}</label>',
    '          <pre class="stor-pre">{{ prettyDetail(detailRow.detail) }}</pre>',
    '        </div>',
    '      </div>',
    '    </n-drawer-content>',
    '  </n-drawer>',
    '</div>',
  ].join(""),
};
