/* 存储：域/文件占用总览 + 键浏览（名称+大小+搜索）+ 维护操作 */
window.PageStorage = {
  name: "PageStorage",
  data() {
    return {
      domains: [],
      files: [],
      totalBytes: 0,
      active: "",
      activeLabel: "",
      keys: [],
      keyTotal: 0,
      keyQ: "",
      entryKey: "",
      entryBody: "",
      entryTruncated: false,
      busy: false,
      hint: "",
      clearOpen: false,
      pendingClear: "",
      clearDomainN: 0,
      loading: false,
    };
  },
  computed: {
    shownKeys() {
      var q = this.keyQ.trim().toLowerCase();
      if (!q) return this.keys;
      return this.keys.filter(function (k) { return k.key.toLowerCase().indexOf(q) >= 0; });
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    fmtSize(n) {
      n = Number(n) || 0;
      if (n > 1048576) return (n / 1048576).toFixed(1) + " MB";
      if (n > 1024) return (n / 1024).toFixed(1) + " KB";
      return n + " B";
    },
    shortKey(key) {
      return String(key || "").replace(/^QvQChat:/, "");
    },
    load() {
      var self = this;
      return QvQ.swr(self, "storage", "/api/qvq/storage", function (d) {
        self.domains = (d && d.domains) || [];
        self.files = (d && d.files) || [];
        self.totalBytes = (d && d.total_bytes) || 0;
      });
    },
    pickDomain(id) {
      var self = this;
      this.active = id;
      this.entryKey = "";
      this.entryBody = "";
      this.hint = "";
      this.keyQ = "";
      api("/api/qvq/storage/keys?domain=" + encodeURIComponent(id)).then(function (d) {
        self.keys = (d && d.keys) || [];
        self.keyTotal = (d && d.total) || self.keys.length;
      });
    },
    openKey(k) {
      var self = this;
      this.entryKey = k.key;
      this.entryTruncated = false;
      api("/api/qvq/storage/entry?key=" + encodeURIComponent(k.key)).then(function (d) {
        self.entryBody = (d && d.value) || "";
        self.entryTruncated = !!(d && d.truncated);
      });
    },
    delKey() {
      var self = this;
      if (!this.entryKey) return;
      api("/api/qvq/storage/delete", "POST", { keys: [this.entryKey] }).then(function () {
        self.entryKey = "";
        self.entryBody = "";
        self.pickDomain(self.active);
        self.load();
      });
    },
    domainLabel(id) {
      var map = {
        sessions: "storage_d_sessions", memories: "storage_d_memories",
        profiles: "storage_d_profiles", knowledge: "storage_d_knowledge",
        audit: "storage_d_audit", usage: "storage_d_usage",
        participation: "storage_d_participation", shares: "storage_d_shares",
        recall: "storage_d_recall", pending: "storage_d_pending",
        trash: "storage_d_trash", docs: "storage_d_docs",
        settings: "storage_d_settings", other: "storage_d_other",
        models: "storage_d_models", mcp: "storage_d_mcp",
        personas: "storage_d_personas", tasks: "storage_d_tasks",
        uploads: "storage_d_uploads", work: "storage_d_work",
        docs_cache: "storage_d_docs_cache",
      };
      return map[id] ? t(map[id]) : id;
    },
    askClear(id) {
      this.pendingClear = id;
      this.activeLabel = this.domainLabel(id);
      var dm = this.domains.find(function (d) { return d.id === id; });
      this.clearDomainN = dm ? Number(dm.keys || 0) : 0;
      this.clearOpen = true;
    },
    doClear() {
      var self = this;
      var id = this.pendingClear;
      this.clearOpen = false;
      this.busy = true;
      api("/api/qvq/storage/cleanup", "POST", { domains: [id] }).then(function (r) {
        self.busy = false;
        self.hint = t("storage_cleared").replace("{n}", String((r && r.removed) || 0));
        self.entryKey = "";
        self.entryBody = "";
        if (self.active === id) self.pickDomain(id);
        self.load();
      });
    },
    slim() {
      var self = this;
      this.busy = true;
      api("/api/qvq/storage/slim", "POST", {}).then(function () {
        self.busy = false;
        self.load();
      });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_storage") }}</div>',
    '      <div class="qvq-page-sub">{{ t("storage_total") }} {{ fmtSize(totalBytes) }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-button size="small" :loading="busy" @click="load">{{ t("refresh") }}</n-button>',
    '      <n-button size="small" :loading="busy" @click="slim">{{ t("storage_slim") }}</n-button>',
    '    </div>',
    '  </div>',
    '  <div class="qvq-meta-line" v-if="hint" style="margin-bottom:8px">{{ hint }}</div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div class="qvq-table-wrap" v-if="!loading">',
    '  <table class="qvq-table stor-table">',
    '    <thead><tr>',
    '      <th>{{ t("storage_domain") }}</th>',
    '      <th style="width:90px">{{ t("storage_count") }}</th>',
    '      <th style="width:110px">{{ t("storage_size") }}</th>',
    '      <th style="width:150px"></th>',
    '    </tr></thead>',
    '    <tbody>',
    '      <tr v-for="dm in domains" :key="dm.id" :class="{ hl: active === dm.id }">',
    '        <td><b>{{ domainLabel(dm.id) }}</b> <code class="stor-did">{{ dm.id }}</code></td>',
    '        <td>{{ dm.keys }}</td>',
    '        <td>{{ fmtSize(dm.bytes) }}</td>',
    '        <td class="stor-acts">',
    '          <button type="button" class="prov-act" @click="pickDomain(dm.id)">{{ t("storage_browse") }}</button>',
    '          <button type="button" class="prov-act danger" @click="askClear(dm.id)">{{ t("storage_clear") }}</button>',
    '        </td>',
    '      </tr>',
    '      <tr v-for="f in files" :key="f.id">',
    '        <td><b>{{ domainLabel(f.id) }}</b> <code class="stor-did">{{ f.id }}</code></td>',
    '        <td><span class="qvq-meta-line" :title="t(&quot;stor_files_hint&quot;)">{{ t("storage_files") }}</span></td>',
    '        <td>{{ fmtSize(f.bytes) }}</td>',
    '        <td class="stor-acts"></td>',
    '      </tr>',
    '    </tbody>',
    '  </table>',
    '  </div>',
    '  <div v-if="!loading && !domains.length" class="qvq-empty"><Mascot :size="30" mood="idle"/>{{ t("storage_empty") }}</div>',
    '  <section class="stor-browse" v-if="active">',
    '    <div class="stor-browse-head">',
    '      <h3 class="plat-sec" style="margin:0">{{ t("storage_keys_title") }} · {{ domainLabel(active) }}</h3>',
    '      <n-input v-model:value="keyQ" size="small" clearable :placeholder="t(\'search_ph\')"',
    '               style="width:200px"/>',
    '    </div>',
    '    <div class="stor-keys">',
    '      <button v-for="k in shownKeys" :key="k.key" type="button" class="stor-key-row"',
    '              :class="{ on: entryKey === k.key }" @click="openKey(k)">',
    '        <code class="nm">{{ shortKey(k.key) }}</code>',
    '        <span class="sz">{{ fmtSize(k.bytes) }}</span>',
    '      </button>',
    '      <div v-if="!shownKeys.length" class="qvq-empty">{{ t("storage_no_keys") }}</div>',
    '    </div>',
    '    <div class="stor-entry" v-if="entryKey">',
    '      <div class="stor-entry-head">',
    '        <code>{{ shortKey(entryKey) }}</code>',
    '        <span class="qvq-meta-line" v-if="entryTruncated">{{ t("storage_truncated") }}</span>',
    '        <n-button size="tiny" type="error" @click="delKey">{{ t("chat_delete") }}</n-button>',
    '      </div>',
    '      <pre class="stor-pre">{{ entryBody }}</pre>',
    '    </div>',
    '  </section>',
    '  <n-modal v-model:show="clearOpen" preset="card" class="qvq-modal-card"',
    '           style="max-width:400px" :title="t(\'confirm_title\')" :bordered="false">',
    '    <div class="qvq-modal-hint">{{ t("storage_confirm_clear").replace("{d}", activeLabel) }}</div>',
    '    <div class="qvq-modal-hint stor-clear-danger" v-if="clearDomainN > 0">',
    '      {{ t("storage_confirm_count").replace("{n}", String(clearDomainN)) }}</div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="clearOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="error" @click="doClear">{{ t("confirm_yes") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '</div>',
  ].join(""),
};
