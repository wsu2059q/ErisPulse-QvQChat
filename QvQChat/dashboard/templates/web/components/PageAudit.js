/* 审计：倒序无限滚动 / 过滤 / 批量勾选删除 / 清空 / 行详情抽屉 */
window.PageAudit = {
  name: "PageAudit",
  data() {
    return {
      rows: [], total: 0, offset: 0, q: "", picked: [], picking: false,
      busy: false, loading: false,
      detailOpen: false, detailRow: null, observer: null,
      fTool: "", fKeyword: "", fSince: "", fUntil: "",
      toolNames: [],
    };
  },
  computed: {
    hasMore() {
      return this.rows.length < this.total;
    },
    toolOptions() {
      return [{ label: t("audit_tool_all"), value: "" }].concat(
        this.toolNames.map(function (n) { return { label: n, value: n }; })
      );
    },
  },
  mounted() {
    this.load();
  },
  beforeUnmount() {
    if (this.observer) this.observer.disconnect();
  },
  methods: {
    queryUrl(offset) {
      var u = "/api/qvq/audit?limit=200&offset=" + offset;
      if (this.fTool) u += "&tool=" + encodeURIComponent(this.fTool);
      if (this.fKeyword.trim()) u += "&keyword=" + encodeURIComponent(this.fKeyword.trim());
      if (this.fSince) u += "&since=" + Math.floor(new Date(this.fSince).getTime() / 1000);
      if (this.fUntil) u += "&until=" + Math.floor(new Date(this.fUntil).getTime() / 1000);
      return u;
    },
    load() {
      var self = this;
      if (!this.offset) this.loading = true;
      if (this.offset) {
        return api(this.queryUrl(this.offset)).then(function (d) { self.applyPage(d); });
      }
      return QvQ.swr(self, "audit:" + this.fTool + ":" + this.fKeyword + ":" + this.fSince + ":" + this.fUntil, this.queryUrl(0), function (d) { self.applyPage(d); });
    },
    applyFilters() {
      this.offset = 0;
      this.rows = [];
      this.total = 0;
      this.load();
    },
    refreshTools() {
      // 工具下拉选项：从当前累计行聚合（分页滚动后越用越全）
      var seen = {};
      this.rows.forEach(function (r) { if (r.tool) seen[r.tool] = 1; });
      this.toolNames = Object.keys(seen).sort();
    },
    exportCsv() {
      // 导出当前筛选下的首页数据（浏览器端拼 CSV；审计 API 无全量导出端点）
      var esc = function (v) {
        var s = String(v == null ? "" : v);
        return '"' + s.replace(/"/g, '""') + '"';
      };
      var head = ["ts", "tool", "user_id", "chat_key", "origin", "detail"];
      var lines = [head.join(",")].concat(this.rows.map(function (r) {
        return head.map(function (k) { return esc(k === "detail" ? JSON.stringify(r.detail || {}) : r[k]); }).join(",");
      }));
      var blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "audit_" + new Date().toISOString().slice(0, 10) + ".csv";
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
    },
    applyPage(d) {
      var self = this;
      var page = ((d && d.entries) || []).map(function (e, i) {
        e._n = self.offset + i;  // 最新在前序号（audit/delete 的 indexes 语义）
        return e;
      });
      self.rows = self.offset ? self.rows.concat(page) : page;
      self.total = (d && d.total) || 0;
      self.refreshTools();
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
    '      <n-select :value="fTool" :options="toolOptions" size="small" filterable tag clearable',
    '                style="width:150px" :placeholder="t(\'audit_tool_all\')" @update:value="fTool = $event || \'\'; applyFilters()"/>',
    '      <n-input v-model:value="fKeyword" size="small" clearable :placeholder="t(\'audit_filter\')"',
    '               style="width:170px" @keyup.enter="applyFilters" @clear="applyFilters"/>',
    '      <input type="date" class="audit-date" :value="fSince" :aria-label="t(\'audit_since\')"',
    '             @change="fSince = $event.target.value; applyFilters()"/>',
    '      <input type="date" class="audit-date" :value="fUntil" :aria-label="t(\'audit_until\')"',
    '             @change="fUntil = $event.target.value ? $event.target.value + \'T23:59:59\' : \'\'; applyFilters()"/>',
    '      <template v-if="!picking">',
    '        <n-button size="small" :disabled="!rows.length" @click="exportCsv">{{ t("audit_export") }}</n-button>',
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
