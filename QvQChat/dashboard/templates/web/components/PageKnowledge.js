/* 知识库：搜索 / 条目卡片 / 新建编辑 / AI 整理 / 导入导出 / 批量管理 */
window.PageKnowledge = {
  name: "PageKnowledge",
  data() {
    return {
      q: "",
      entries: [],
      stats: {},
      drawer: false,
      form: { id: "", title: "", content: "", source: "", triggers: "", scope: "", priority: 0, isNew: true },
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
      return this.entries.length > 0 && this.picked.length === this.entries.length;
    },
  },
  mounted() {
    this.load();
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
    blank() {
      return { id: "", title: "", content: "", source: "", triggers: "", scope: "", priority: 0, isNew: true };
    },
    openNew() {
      this.form = this.blank();
      this.formErr = "";
      this.drawer = true;
    },
    openEdit(e) {
      this.form = {
        id: e.id,
        title: e.title || "",
        content: e.content || "",
        source: e.source || "",
        triggers: (e.triggers || []).join(", "),
        scope: e.scope || e.owner || "",
        priority: Number(e.priority) || 0,
        isNew: false,
      };
      this.formErr = "";
      this.drawer = true;
    },
    save() {
      var self = this;
      this.busy = true;
      var payload = {
        title: this.form.title,
        content: this.form.content,
        source: this.form.source,
        scope: this.form.scope,
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
      this.picked = v ? this.entries.map(function (e) { return e.id; }) : [];
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
    '      <div class="qvq-page-sub">{{ entries.length }} {{ t("kb_entries") }}</div>',
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
    '  <div class="kb-batch-bar" v-if="batchMode">',
    '    <n-checkbox :checked="allPicked" @update:checked="toggleAll">{{ t("batch_select_all") }}</n-checkbox>',
    '    <span class="qvq-meta-line">{{ picked.length }} / {{ entries.length }}</span>',
    '    <n-button size="tiny" type="error" :disabled="!picked.length" :loading="batchBusy" @click="batchDel">',
    '      {{ t("batch_delete") }}</n-button>',
    '    <span class="qvq-meta-line" v-if="!picked.length">{{ t("batch_none_selected") }}</span>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div class="prov-grid" v-if="!loading">',
    '    <article v-for="e in entries" :key="e.id" class="prov-card"',
    '             :class="{ \'is-picked\': batchMode && picked.indexOf(e.id) >= 0 }"',
    '             @click="batchMode && togglePick(e.id)">',
    '      <header class="prov-head">',
    '        <div class="prov-title"><span class="prov-name">{{ e.title }}</span></div>',
    '        <n-checkbox v-if="batchMode" :checked="picked.indexOf(e.id) >= 0" @click.stop',
    '                    @update:checked="function(){ togglePick(e.id); }"/>',
    '      </header>',
    '      <div class="tool-desc">{{ (e.content || "").slice(0, 140) }}</div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-count">{{ e.scope || "global" }}</span>',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click.stop="openEdit(e)">{{ t("edit") }}</button>',
    '          <button type="button" class="prov-act danger" @click.stop="del(e)">{{ t("chat_delete") }}</button>',
    '        </span>',
    '      </footer>',
    '    </article>',
    '  </div>',
    '  <div v-if="!entries.length" class="qvq-empty">-</div>',
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
    '            <n-input v-model:value="form.scope" :placeholder="t(\'kb_scope_ph\')"/>',
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
