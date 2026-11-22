/* 知识库：搜索 / 作用域视图（全部·全局·平台·会话）/ 条目卡片 / 新建编辑 / AI 整理 / 导入导出 / 批量管理
   作用域判定（对齐后端 knowledge.py owner 语义）：owner 空/"global"=全局；命中已知平台名=平台；其余=chat_key（会话私有）
   平台名来源：条目 owner 收集（无冒号裸值，chat_key 恒含冒号）∪ /api/qvq/sessions 的 accounts.adapters[].platform
   i18n（新键，待主线补入 i18n.js）: kb_scope_all=全部, kb_scope_global=全局, kb_scope_platform=平台,
     kb_scope_session=会话, kb_scope_group_platforms=平台作用域, kb_scope_group_sessions=会话作用域,
     kb_scope_left_all=全部, kb_scope_platform_ph=选择平台，可输入新平台名, kb_scope_session_ph=选择会话，可输入 chat_key,
     kb_scope_global_hint=对所有会话可见, kb_scope_empty=该作用域暂无条目
   样式（待主线补进 app.css）: .kb-scope-pill 条目卡作用域小徽标（现以内联样式兜底）；左列复用 .mem-sess 行样式 */
window.PageKnowledge = {
  name: "PageKnowledge",
  data() {
    return {
      q: "",
      entries: [],
      stats: {},
      scopeTab: "all",
      scopeSel: "",
      sessions: [],
      adapters: [],
      drawer: false,
      form: { id: "", title: "", content: "", source: "", triggers: "", scopeKind: "global", scopePlatform: "", scopeSession: "", priority: 0, isNew: true },
      formErr: "",
      busy: false,
      loading: false,
      organizing: false,
      batchMode: false,
      picked: [],
      batchBusy: false,
    };
  },
  computed: {
    allPicked() {
      return this.shownEntries.length > 0 && this.picked.length === this.shownEntries.length;
    },
    /* 已知平台名集合：条目 owner 无冒号裸值 ∪ adapters 的 platform（chat_key 恒含冒号，不会误收） */
    platforms() {
      var set = {};
      this.adapters.forEach(function (a) {
        var p = String((a && a.platform) || "").trim();
        if (p) set[p] = 1;
      });
      this.entries.forEach(function (e) {
        var o = String(e.owner || "");
        if (!o || o === "global") return;
        if (o.indexOf(":") < 0) set[o] = 1;
      });
      return Object.keys(set).sort();
    },
    sessMap() {
      var m = {};
      this.sessions.forEach(function (s) {
        if (s && s.chat_key) m[s.chat_key] = s.name || "";
      });
      return m;
    },
    shownEntries() {
      var self = this;
      var tab = this.scopeTab;
      var sel = this.scopeSel;
      if (tab === "all") return this.entries;
      return this.entries.filter(function (e) {
        var k = self.scopeKindOf(e.owner);
        if (tab === "global") return k === "global";
        if (tab === "platform") return k === "platform" && (!sel || e.owner === sel);
        if (tab === "session") return k === "session" && (!sel || e.owner === sel);
        return true;
      });
    },
    /* 左列分组行：仅当前 tab 有条目的作用域，头部一行"全部"清子过滤 */
    scopeGroups() {
      var self = this;
      var tab = this.scopeTab;
      if (tab !== "platform" && tab !== "session") return [];
      var counts = {};
      var total = 0;
      this.entries.forEach(function (e) {
        if (self.scopeKindOf(e.owner) !== tab) return;
        total += 1;
        counts[e.owner] = (counts[e.owner] || 0) + 1;
      });
      var rows = [{ key: "", n: total, label: t("kb_scope_left_all") }];
      Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; }).forEach(function (key) {
        rows.push({ key: key, n: counts[key], label: self.scopeLabelOf(key) });
      });
      return rows;
    },
    colsStyle() {
      if (this.scopeTab === "platform" || this.scopeTab === "session")
        return "display:grid;grid-template-columns:240px minmax(0,1fr);gap:16px;align-items:start";
      return "";
    },
    sideTitle() {
      return t(this.scopeTab === "platform" ? "kb_scope_group_platforms" : "kb_scope_group_sessions");
    },
    scopeKindOpts() {
      return [
        { v: "global", k: "kb_scope_global" },
        { v: "platform", k: "kb_scope_platform" },
        { v: "session", k: "kb_scope_session" },
      ];
    },
    platformOptions() {
      return this.platforms.map(function (p) { return { label: p, value: p }; });
    },
    sessionOptions() {
      return this.sessions.filter(function (s) { return s && s.chat_key; }).map(function (s) {
        return { label: s.name || s.chat_key, value: s.chat_key };
      });
    },
  },
  mounted() {
    this.load();
    this.loadScopes();
  },
  methods: {
    load() {
      var self = this;
      var url = "/api/qvq/kb";
      if (this.q.trim()) url += "?q=" + encodeURIComponent(this.q.trim());
      return QvQ.swr(self, "kb:" + this.q.trim(), url, function (d) {
        self.entries = (d && d.entries) || [];
        self.stats = (d && d.stats) || {};
        self.picked = self.picked.filter(function (id) {
          return self.entries.some(function (e) { return e.id === id; });
        });
      });
    },
    /* 一次请求拿会话名映射与平台名集合（同 PagePlatforms 的 accounts.adapters 通道） */
    loadScopes() {
      var self = this;
      api("/api/qvq/sessions?limit=200").then(function (d) {
        self.sessions = (d && d.sessions) || [];
        var accs = d && d.accounts && d.accounts.adapters;
        self.adapters = Array.isArray(accs) ? accs : [];
      });
    },
    scopeKindOf(owner) {
      var o = String(owner == null ? "" : owner);
      if (!o || o === "global") return "global";
      if (this.platforms.indexOf(o) >= 0) return "platform";
      return "session";
    },
    scopeLabelOf(owner) {
      var o = String(owner == null ? "" : owner);
      var kind = this.scopeKindOf(o);
      if (kind === "global") return t("kb_scope_global");
      if (kind === "platform") return o;
      return this.sessMap[o] || o;
    },
    pillStyle(kind) {
      var base = "display:inline-block;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:1px 8px;border:1px solid var(--qvq-bd);border-radius:999px;font-size:11px;line-height:16px;vertical-align:middle;";
      var tone = kind === "platform"
        ? "background:var(--qvq-accent-soft);color:var(--qvq-accent);"
        : kind === "session"
          ? "background:var(--qvq-bg-s);color:var(--qvq-tx-s);"
          : "background:transparent;color:var(--qvq-tx-t);";
      return base + tone;
    },
    setScopeTab(v) {
      this.scopeTab = v;
      this.scopeSel = "";
    },
    pickScope(key) {
      this.scopeSel = this.scopeSel === key ? "" : key;
    },
    blank() {
      return { id: "", title: "", content: "", source: "", triggers: "", scopeKind: "global", scopePlatform: "", scopeSession: "", priority: 0, isNew: true };
    },
    openNew() {
      this.form = this.blank();
      this.formErr = "";
      this.drawer = true;
    },
    openEdit(e) {
      var owner = String(e.owner != null ? e.owner : (e.scope || ""));
      var kind = this.scopeKindOf(owner);
      this.form = {
        id: e.id,
        title: e.title || "",
        content: e.content || "",
        source: e.source || "",
        triggers: (e.triggers || []).join(", "),
        scopeKind: kind,
        scopePlatform: kind === "platform" ? owner : "",
        scopeSession: kind === "session" ? owner : "",
        priority: Number(e.priority) || 0,
        isNew: false,
      };
      this.formErr = "";
      this.drawer = true;
    },
    save() {
      var self = this;
      this.busy = true;
      /* 提交映射：全局→""；平台→平台名；会话→chat_key（后端 scope 直通 owner） */
      var scope = "";
      if (this.form.scopeKind === "platform") scope = String(this.form.scopePlatform || "").trim();
      else if (this.form.scopeKind === "session") scope = String(this.form.scopeSession || "").trim();
      var payload = {
        title: this.form.title,
        content: this.form.content,
        source: this.form.source,
        scope: scope,
        triggers: this.form.triggers,
        priority: Number(this.form.priority) || 0,
      };
      var call = this.form.isNew
        ? api("/api/qvq/kb/add", "POST", payload)
        : api("/api/qvq/kb/update", "POST", Object.assign({ id: this.form.id }, payload));
      call.then(function (r) {
        self.busy = false;
        if (r && r.error) {
          self.formErr = r.error;
          return;
        }
        self.drawer = false;
        self.load();
      });
    },
    del(e) {
      var self = this;
      api("/api/qvq/kb/delete", "POST", { id: e.id }).then(function () { self.load(); });
    },
    /* AI 整理：cheap 模型分析条目 → 合并/补触发词/删冗余，后端直接应用并出报告 */
    organizeRun() {
      var self = this;
      this.organizing = true;
      QvQ.toast(t("organize_running"));
      api("/api/qvq/kb/organize", "POST", {}).then(function (r) {
        self.organizing = false;
        if (!r || r.error) {
          QvQ.toast(QvQ.fill("organize_fail", { error: (r && r.error) || "?" }));
          return;
        }
        if (r.report === "empty" || r.report === "noop" || !Number(r.actions)) {
          QvQ.toast(t("organize_noop"));
          return;
        }
        QvQ.toast(QvQ.fill("organize_done", { report: r.report }));
        self.load();
      }).catch(function () {
        self.organizing = false;
        QvQ.toast(QvQ.fill("organize_fail", { error: "network" }));
      });
    },
    /* 导出：后端返回 entries JSON，前端落文件 */
    exportKb() {
      apiBlob("/api/qvq/kb/export").then(function (r) {
        return r.json();
      }).then(function (d) {
        var blob = new Blob([JSON.stringify(d.entries || [], null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "qvqchat-kb-" + new Date().toISOString().slice(0, 10) + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
      });
    },
    pickImport() {
      if (this.$refs.importFile) this.$refs.importFile.click();
    },
    importKb(ev) {
      var self = this;
      var file = ev.target.files && ev.target.files[0];
      ev.target.value = "";
      if (!file) return;
      file.text().then(function (text) {
        var data = JSON.parse(text);
        var entries = Array.isArray(data) ? data : data.entries;
        if (!Array.isArray(entries)) throw new Error("bad");
        return api("/api/qvq/kb/import", "POST", { entries: entries });
      }).then(function (r) {
        QvQ.toast(QvQ.fill("import_done", { n: (r && r.added) || 0 }));
        self.load();
      }).catch(function () {
        QvQ.toast(t("import_failed"));
      });
    },
    togglePick(id) {
      var i = this.picked.indexOf(id);
      if (i >= 0) this.picked.splice(i, 1);
      else this.picked.push(id);
    },
    toggleAll(v) {
      this.picked = v ? this.shownEntries.map(function (e) { return e.id; }) : [];
    },
    batchDel() {
      var self = this;
      if (!this.picked.length) return;
      this.batchBusy = true;
      api("/api/qvq/kb/batch-delete", "POST", { ids: this.picked.slice() }).then(function (r) {
        self.batchBusy = false;
        QvQ.toast(QvQ.fill("storage_cleared", { n: (r && r.removed) || 0 }));
        self.picked = [];
        self.load();
      });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_knowledge") }}</div>',
    '      <div class="qvq-page-sub">{{ scopeTab === "all" ? entries.length : shownEntries.length + " / " + entries.length }} {{ t("kb_entries") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-input v-model:value="q" size="small" clearable :placeholder="t(\'search_ph\')"',
    '               style="width:200px" @update:value="load"/>',
    '      <n-button size="small" :loading="organizing" @click="organizeRun">{{ t("organize_run") }}</n-button>',
    '      <n-button size="small" @click="exportKb">{{ t("kb_export") }}</n-button>',
    '      <n-button size="small" @click="pickImport">{{ t("kb_import") }}</n-button>',
    '      <n-button size="small" :type="batchMode ? \'warning\' : \'default\'" @click="batchMode = !batchMode; picked = []">',
    '        {{ t("batch_manage") }}</n-button>',
    '      <n-button size="small" type="primary" @click="openNew">{{ t("kb_add") }}</n-button>',
    '      <input ref="importFile" type="file" accept=".json,application/json" style="display:none" @change="importKb"/>',
    '    </div>',
    '  </div>',
    '<settings-section group="kb" :title="t(&quot;ss_kb&quot;)"/>',
    '  <div class="kb-scope-bar" style="display:flex;align-items:center;gap:10px;margin:0 0 14px">',
    '    <div class="qvq-seg">',
    '      <button type="button" :class="{ on: scopeTab === \'all\' }" @click="setScopeTab(\'all\')">{{ t("kb_scope_all") }}</button>',
    '      <button type="button" :class="{ on: scopeTab === \'global\' }" @click="setScopeTab(\'global\')">{{ t("kb_scope_global") }}</button>',
    '      <button type="button" :class="{ on: scopeTab === \'platform\' }" @click="setScopeTab(\'platform\')">{{ t("kb_scope_platform") }}</button>',
    '      <button type="button" :class="{ on: scopeTab === \'session\' }" @click="setScopeTab(\'session\')">{{ t("kb_scope_session") }}</button>',
    '    </div>',
    '    <span class="qvq-meta-line" v-if="scopeSel">{{ scopeLabelOf(scopeSel) }}</span>',
    '  </div>',
    '  <div class="kb-batch-bar" v-if="batchMode">',
    '    <n-checkbox :checked="allPicked" @update:checked="toggleAll">{{ t("batch_select_all") }}</n-checkbox>',
    '    <span class="qvq-meta-line">{{ picked.length }} / {{ shownEntries.length }}</span>',
    '    <n-button size="tiny" type="error" :disabled="!picked.length" :loading="batchBusy" @click="batchDel">',
    '      {{ t("batch_delete") }}</n-button>',
    '    <span class="qvq-meta-line" v-if="!picked.length">{{ t("batch_none_selected") }}</span>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div v-if="!loading" :style="colsStyle">',
    '    <aside class="prov-card" v-if="scopeTab === \'platform\' || scopeTab === \'session\'" style="padding:10px 8px">',
    '      <div style="padding:2px 9px 6px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.9px;color:var(--qvq-tx-t)">{{ sideTitle }}</div>',
    '      <button v-for="g in scopeGroups" :key="g.key" type="button" class="mem-sess"',
    '              :class="{ on: scopeSel === g.key }" @click="pickScope(g.key)">',
    '        <span class="nm">{{ g.label }}</span>',
    '        <span class="mt">{{ g.n }}</span>',
    '      </button>',
    '    </aside>',
    '    <div>',
    '      <div class="prov-grid">',
    '        <article v-for="e in shownEntries" :key="e.id" class="prov-card"',
    '                 :class="{ \'is-picked\': batchMode && picked.indexOf(e.id) >= 0 }"',
    '                 @click="batchMode && togglePick(e.id)">',
    '          <header class="prov-head">',
    '            <div class="prov-title"><span class="prov-name">{{ e.title }}</span></div>',
    '            <n-checkbox v-if="batchMode" :checked="picked.indexOf(e.id) >= 0" @click.stop',
    '                        @update:checked="function(){ togglePick(e.id); }"/>',
    '          </header>',
    '          <div class="tool-desc">{{ (e.content || "").slice(0, 140) }}</div>',
    '          <footer class="prov-foot">',
    '            <span class="prov-count"><span class="kb-scope-pill" :style="pillStyle(scopeKindOf(e.owner))">{{ scopeLabelOf(e.owner) }}</span></span>',
    '            <span class="prov-acts">',
    '              <button type="button" class="prov-act" @click.stop="openEdit(e)">{{ t("edit") }}</button>',
    '              <button type="button" class="prov-act danger" @click.stop="del(e)">{{ t("chat_delete") }}</button>',
    '            </span>',
    '          </footer>',
    '        </article>',
    '      </div>',
    '      <div v-if="!shownEntries.length" class="qvq-empty">{{ scopeTab === "all" ? "-" : t("kb_scope_empty") }}</div>',
    '    </div>',
    '  </div>',
    '  <n-drawer v-model:show="drawer" :width="480" placement="right">',
    '    <n-drawer-content :title="form.isNew ? t(\'kb_add\') : t(\'kb_edit\')" closable>',
    '      <div class="prov-form">',
    '        <div class="prov-field">',
    '          <label>{{ t("kb_title_label") }}</label>',
    '          <n-input v-model:value="form.title"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("kb_content_label") }}</label>',
    '          <n-input v-model:value="form.content" type="textarea" :rows="8"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("kb_triggers_label") }}</label>',
    '          <n-input v-model:value="form.triggers" :placeholder="t(\'kb_triggers_ph\')"/>',
    '        </div>',
    '        <div class="prov-grid2">',
    '          <div class="prov-field">',
    '            <label>{{ t("kb_scope_label") }}</label>',
    '            <div class="qvq-seg" style="margin:2px 0 8px">',
    '              <button type="button" v-for="k in scopeKindOpts" :key="k.v"',
    '                      :class="{ on: form.scopeKind === k.v }" @click="form.scopeKind = k.v">{{ t(k.k) }}</button>',
    '            </div>',
    '            <n-select v-if="form.scopeKind === \'platform\'" v-model:value="form.scopePlatform" size="small"',
    '                      tag filterable clearable :options="platformOptions" :placeholder="t(\'kb_scope_platform_ph\')"/>',
    '            <n-select v-else-if="form.scopeKind === \'session\'" v-model:value="form.scopeSession" size="small"',
    '                      tag filterable :options="sessionOptions" :placeholder="t(\'kb_scope_session_ph\')"/>',
    '            <div class="qvq-meta-line" v-else>{{ t("kb_scope_global_hint") }}</div>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>{{ t("kb_priority_label") }}</label>',
    '            <n-input-number v-model:value="form.priority" size="small" style="width:100%"/>',
    '          </div>',
    '        </div>',
    '        <div class="cf-error" v-if="formErr">{{ formErr }}</div>',
    '      </div>',
    '      <template #footer>',
    '        <div class="qvq-modal-foot">',
    '          <n-button size="small" @click="drawer = false">{{ t("cancel") }}</n-button>',
    '          <n-button size="small" type="primary" :loading="busy" @click="save">{{ t("save") }}</n-button>',
    '        </div>',
    '      </template>',
    '    </n-drawer-content>',
    '  </n-drawer>',
    '</div>',
  ].join(""),
};
