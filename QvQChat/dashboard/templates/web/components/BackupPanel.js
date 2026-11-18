/* 备份：全量/去隐私/zip 选择导出 + json/zip 导入（peek 探测 + 分段合并策略） */
window.BackupPanel = {
  name: "BackupPanel",
  data() {
    return {
      pickOpen: false,
      pickDomains: [],
      pickSanitize: true,
      busyExport: false,
      draft: null,
      strategies: {},
      fileStrategy: "overwrite",
      confirmOpen: false,
      busyImport: false,
      result: null,
      resultErr: "",
    };
  },
  computed: {
    domainGroups() {
      var sec = [
        ["config", "export_sec_config"], ["models", "export_sec_models"],
        ["personas", "export_sec_personas"], ["tasks", "export_sec_tasks"],
        ["memory", "export_sec_memory"], ["skills", "export_sec_skills"],
        ["mcp", "export_sec_mcp"],
      ];
      var stor = [
        ["sessions", "storage_d_sessions"], ["memories", "storage_d_memories"],
        ["profiles", "storage_d_profiles"], ["knowledge", "storage_d_knowledge"],
        ["audit", "storage_d_audit"], ["usage", "storage_d_usage"],
        ["participation", "storage_d_participation"], ["shares", "storage_d_shares"],
        ["recall", "storage_d_recall"], ["pending", "storage_d_pending"],
        ["trash", "storage_d_trash"], ["docs", "storage_d_docs"],
        ["settings", "storage_d_settings"], ["other", "storage_d_other"],
      ];
      var files = [
        ["uploads", "storage_d_uploads"], ["work", "storage_d_work"],
        ["docs_cache", "storage_d_docs_cache"],
      ];
      return [
        { label: t("export_grp_data"), items: sec },
        { label: t("export_grp_storage"), items: stor },
        { label: t("export_grp_files"), items: files },
      ];
    },
    sectionLabels() {
      var map = {
        models: "export_sec_models", personas: "export_sec_personas",
        tasks: "export_sec_tasks", memory: "export_sec_memory",
        skills: "export_sec_skills", mcp: "export_sec_mcp",
        config: "export_sec_config", storage: "export_sec_storage",
        files: "export_grp_files",
      };
      return map;
    },
    draftSections() {
      return (this.draft && this.draft.sections) || [];
    },
  },
  methods: {
    domainLabel(id) {
      for (var gi = 0; gi < this.domainGroups.length; gi++) {
        var g = this.domainGroups[gi];
        for (var i = 0; i < g.items.length; i++) {
          if (g.items[i][0] === id) return t(g.items[i][1]);
        }
      }
      return id;
    },
    sectionLabel(key) {
      var k = this.sectionLabels[key];
      return k ? t(k) : key;
    },
    stamp() {
      var d = new Date();
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return "" + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "-" +
        p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
    },
    saveBlob(blob, name) {
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
    },
    exportJson(sanitize) {
      var self = this;
      this.busyExport = true;
      apiBlob("/api/qvq/export?sanitize=" + (sanitize ? "1" : "0")).then(function (resp) {
        self.busyExport = false;
        if (!resp.ok) return;
        resp.blob().then(function (b) {
          self.saveBlob(b, "qvqchat-export-" + self.stamp() + (sanitize ? "-sanitized" : "") + ".json");
        });
      });
    },
    exportZip() {
      var self = this;
      if (!this.pickDomains.length) return;
      this.busyExport = true;
      var qs = "?format=zip&sanitize=" + (this.pickSanitize ? "1" : "0") +
        "&domains=" + this.pickDomains.map(encodeURIComponent).join(",");
      apiBlob("/api/qvq/export" + qs).then(function (resp) {
        self.busyExport = false;
        if (!resp.ok) return;
        self.pickOpen = false;
        resp.blob().then(function (b) {
          self.saveBlob(b, "qvqchat-export-" + self.stamp() +
            (self.pickSanitize ? "-sanitized" : "") + ".zip");
        });
      });
    },
    toggleDomain(id) {
      var i = this.pickDomains.indexOf(id);
      if (i >= 0) this.pickDomains.splice(i, 1);
      else this.pickDomains.push(id);
    },
    onPickFile(ev) {
      var self = this;
      var file = (ev.target.files || [])[0];
      ev.target.value = "";
      if (!file) return;
      this.result = null;
      this.resultErr = "";
      if ((file.name || "").toLowerCase().indexOf(".zip") >= 0) {
        var reader = new FileReader();
        reader.onload = function () {
          var b64 = String(reader.result || "").split(",")[1] || "";
          api("/api/qvq/import/zip", "POST", { data_b64: b64, peek: 1 }).then(function (d) {
            if (!d || d.error) {
              self.resultErr = (d && d.error) || t("import_failed");
              return;
            }
            var sections = (d.sections || []).concat(d.files && d.files.length ? ["files"] : []);
            if (!sections.length) {
              self.resultErr = t("import_nothing");
              return;
            }
            var st = {};
            sections.forEach(function (s) { st[s] = "overwrite"; });
            self.strategies = st;
            self.draft = {
              name: file.name, zip: true, b64: b64, sections: sections,
              files: d.files || [],
            };
          });
        };
        reader.readAsDataURL(file);
        return;
      }
      var reader2 = new FileReader();
      reader2.onload = function () {
        var data = null;
        try { data = JSON.parse(String(reader2.result || "")); } catch (e) { data = null; }
        if (!data || typeof data !== "object") {
          self.resultErr = t("import_failed");
          return;
        }
        var known = ["models", "personas", "tasks", "memory", "mcp", "skills", "config", "storage"];
        var sections = known.filter(function (k) {
          return Array.isArray(data[k]) ? data[k].length :
            (data[k] && typeof data[k] === "object" ? Object.keys(data[k]).length : false);
        });
        if (!sections.length) {
          self.resultErr = t("import_nothing");
          return;
        }
        var st = {};
        sections.forEach(function (s) { st[s] = "overwrite"; });
        self.strategies = st;
        self.draft = { name: file.name, zip: false, data: data, sections: sections };
      };
      reader2.readAsText(file);
    },
    resetDraft() {
      this.draft = null;
      this.strategies = {};
      this.fileStrategy = "overwrite";
      this.confirmOpen = false;
      this.result = null;
      this.resultErr = "";
    },
    confirmNames() {
      var self = this;
      return this.draftSections.map(function (s) { return self.sectionLabel(s); }).join(" · ");
    },
    applyImport() {
      var self = this;
      var d = this.draft;
      if (!d) return;
      this.busyImport = true;
      this.confirmOpen = false;
      var call = d.zip
        ? api("/api/qvq/import/zip", "POST", { data_b64: d.b64, strategies: this.strategies })
        : api("/api/qvq/import", "POST", { data: d.data, strategies: this.strategies });
      call.then(function (r) {
        self.busyImport = false;
        if (!r || r.error) {
          self.resultErr = (r && r.error) || t("import_failed");
          return;
        }
        var applied = (r.applied || []).filter(function (x) { return x !== "files"; });
        var n = applied.length + (r.files_restored ? 1 : 0);
        var parts = [t("import_done").replace("{n}", String(applied.length))];
        if (r.files_restored) parts.push(t("import_files_restored").replace("{n}", String(r.files_restored)));
        self.result = parts.join(" · ");
        if (r.errors && Object.keys(r.errors).length) {
          self.resultErr = Object.keys(r.errors).map(function (k) {
            return k + ": " + JSON.stringify(r.errors[k]).slice(0, 200);
          }).join("\n");
        }
        self.draft = null;
      });
    },
  },
  template: [
    '  <div class="backup-wrap">',
    '  <section class="doc-sec">',
    '    <h2 class="doc-sec-title"><span>{{ t("kb_export") }}</span></h2>',
    '    <div class="qvq-meta-line" style="margin-bottom:12px">{{ t("storage_export_hint") }}</div>',
    '    <div class="backup-acts">',
    '      <n-button size="small" type="primary" :loading="busyExport" @click="exportJson(false)">',
    '        {{ t("storage_export_full") }}</n-button>',
    '      <n-button size="small" :loading="busyExport" @click="exportJson(true)">',
    '        {{ t("storage_export_san") }}</n-button>',
    '      <n-button size="small" :loading="busyExport" @click="pickOpen = true; pickDomains = []">',
    '        {{ t("storage_export_pick") }}</n-button>',
    '    </div>',
    '  </section>',
    '  <section class="doc-sec">',
    '    <h2 class="doc-sec-title"><span>{{ t("import_apply") }}</span></h2>',
    '    <label class="backup-drop">',
    '      <input type="file" accept=".json,.zip" hidden @change="onPickFile"/>',
    '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">',
    '        <path d="M12 16V4M7.5 8.5L12 4l4.5 4.5"/><path d="M4 16v2a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-2"/></svg>',
    '      <span>{{ t("import_file_label") }}</span>',
    '    </label>',
    '    <div class="cf-error" v-if="resultErr" style="white-space:pre-wrap">{{ resultErr }}</div>',
    '    <div class="backup-draft" v-if="draft">',
    '      <div class="backup-draft-head">',
    '        <code>{{ draft.name }}</code>',
    '        <button type="button" class="prov-act danger" @click="resetDraft">×</button>',
    '      </div>',
    '      <div class="backup-sec" v-for="s in draftSections" :key="s">',
    '        <span class="nm">{{ sectionLabel(s) }}</span>',
    '        <n-select v-model:value="strategies[s]" size="tiny" style="width:110px"',
    '                  :options="[',
    '                    { label: t(\'strategy_overwrite\'), value: \'overwrite\' },',
    '                    { label: t(\'strategy_append\'), value: \'append\' },',
    '                    { label: t(\'strategy_skip\'), value: \'skip\' }]"/>',
    '      </div>',
    '      <div class="qvq-meta-line" style="margin-top:10px">{{ t("backup_import_confirm").replace("{sections}", confirmNames()) }}</div>',
    '      <n-button size="small" type="warning" :loading="busyImport" style="margin-top:10px"',
    '                @click="confirmOpen = true">{{ t("import_apply") }}</n-button>',
    '    </div>',
    '    <div class="backup-result" v-if="result">{{ result }}</div>',
    '  </section>',
    '  <n-modal v-model:show="pickOpen" preset="card" class="qvq-modal-card"',
    '           style="max-width:520px" :title="t(\'storage_export_pick\')" :bordered="false">',
    '    <div class="backup-pick">',
    '      <div v-for="g in domainGroups" :key="g.label" class="backup-pick-grp">',
    '        <div class="backup-pick-cat">{{ g.label }}</div>',
    '        <n-checkbox v-for="it in g.items" :key="it[0]" :checked="pickDomains.indexOf(it[0]) >= 0"',
    '                    :label="domainLabel(it[0])" @update:checked="toggleDomain(it[0])"/>',
    '      </div>',
    '      <div class="qvq-modal-row" style="margin-top:10px">',
    '        <div class="qvq-modal-row-tx">',
    '          <div class="qvq-modal-row-title">{{ t("storage_export_san") }}</div>',
    '        </div>',
    '        <n-switch v-model:value="pickSanitize"/>',
    '      </div>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <span class="qvq-meta-line" v-if="!pickDomains.length">{{ t("export_none_selected") }}</span>',
    '        <n-button size="small" @click="pickOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" :disabled="!pickDomains.length" :loading="busyExport"',
    '                  @click="exportZip">{{ t("confirm_yes") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="confirmOpen" preset="card" class="qvq-modal-card"',
    '           style="max-width:420px" :title="t(\'confirm_title\')" :bordered="false">',
    '    <div>{{ t("backup_import_confirm").replace("{sections}", confirmNames()) }}</div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="confirmOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="warning" @click="applyImport">{{ t("confirm_yes") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '</div>',
  ].join(""),
};
