/* 知识库：搜索 / 条目卡片 / 新建编辑 / 统计 */
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
    };
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
    '      <n-button size="small" type="primary" @click="openNew">{{ t("kb_add") }}</n-button>',
    '    </div>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div class="prov-grid" v-if="!loading">',
    '    <article v-for="e in entries" :key="e.id" class="prov-card">',
    '      <header class="prov-head">',
    '        <div class="prov-title"><span class="prov-name">{{ e.title }}</span></div>',
    '      </header>',
    '      <div class="tool-desc">{{ (e.content || "").slice(0, 140) }}</div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-count">{{ e.scope || "global" }}</span>',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click="openEdit(e)">{{ t("edit") }}</button>',
    '          <button type="button" class="prov-act danger" @click="del(e)">{{ t("chat_delete") }}</button>',
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
    '          <n-input-number v-model:value="form.priority" size="small" style="width:100%"/>',
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
