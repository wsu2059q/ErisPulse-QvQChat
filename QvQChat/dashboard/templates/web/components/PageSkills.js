/* 技能：卡片列表 / 启停 / 新建编辑 / AI 整理 / 导出 / 批量管理 */
window.PageSkills = {
  name: "PageSkills",
  data() {
    return {
      skills: [],
      q: "",
      drawer: false,
      form: { name: "", description: "", body: "", isNew: true },
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
    shownSkills() {
      var needle = this.q.trim().toLowerCase();
      var list = this.skills;
      if (needle) {
        list = list.filter(function (sk) {
          return (sk.name + " " + (sk.description || "")).toLowerCase().indexOf(needle) >= 0;
        });
      }
      return list;
    },
    allPicked() {
      return this.shownSkills.length > 0 && this.picked.length === this.shownSkills.length;
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      return QvQ.swr(self, "skills", "/api/qvq/skills", function (d) {
        self.skills = (d && d.skills) || [];
        self.picked = self.picked.filter(function (name) {
          return self.skills.some(function (s) { return s.name === name; });
        });
      });
    },
    openNew() {
      this.form = { name: "", description: "", body: "", isNew: true };
      this.formErr = "";
      this.drawer = true;
    },
    openEdit(sk) {
      this.form = {
        name: sk.name,
        description: sk.description || "",
        body: sk.body || "",
        isNew: false,
      };
      this.formErr = "";
      this.drawer = true;
    },
    save() {
      var self = this;
      this.busy = true;
      api("/api/qvq/skills/save", "POST", {
        name: this.form.name,
        description: this.form.description,
        body: this.form.body,
      }).then(function (r) {
        self.busy = false;
        if (r && r.error) {
          self.formErr = r.error;
          return;
        }
        self.drawer = false;
        self.load();
      });
    },
    toggle(sk) {
      api("/api/qvq/skills/enabled", "POST", { name: sk.name, enabled: !sk.disabled }).then(function () {
        sk.disabled = !sk.disabled;
      });
    },
    del(sk) {
      var self = this;
      api("/api/qvq/skills/delete", "POST", { name: sk.name }).then(function () { self.load(); });
    },
    /* AI 整理：仅动 dashboard 来源技能（合并近似/修描述/删陈旧） */
    organizeRun() {
      var self = this;
      this.organizing = true;
      QvQ.toast(t("organize_running"));
      api("/api/qvq/skills/organize", "POST", {}).then(function (r) {
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
    exportSkills() {
      apiBlob("/api/qvq/skills/export").then(function (r) {
        return r.json();
      }).then(function (d) {
        var blob = new Blob([JSON.stringify(d.skills || [], null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "qvqchat-skills-" + new Date().toISOString().slice(0, 10) + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
      });
    },
    togglePick(name) {
      var i = this.picked.indexOf(name);
      if (i >= 0) this.picked.splice(i, 1);
      else this.picked.push(name);
    },
    toggleAll(v) {
      this.picked = v ? this.shownSkills.map(function (s) { return s.name; }) : [];
    },
    batchDel() {
      var self = this;
      if (!this.picked.length) return;
      this.batchBusy = true;
      api("/api/qvq/skills/batch-delete", "POST", { names: this.picked.slice() }).then(function (r) {
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
    '      <div class="qvq-page-title">{{ t("nav_skills") }}</div>',
    '      <div class="qvq-page-sub">{{ skills.length }} {{ t("nav_skills") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-input v-model:value="q" size="small" clearable :placeholder="t(\'search_ph\')" style="width:180px"/>',
    '      <n-button size="small" :loading="organizing" @click="organizeRun">{{ t("organize_run") }}</n-button>',
    '      <n-button size="small" @click="exportSkills">{{ t("kb_export") }}</n-button>',
    '      <n-button size="small" :type="batchMode ? \'warning\' : \'default\'" @click="batchMode = !batchMode; picked = []">',
    '        {{ t("batch_manage") }}</n-button>',
    '      <n-button size="small" type="primary" @click="openNew">{{ t("add_title") }}</n-button>',
    '    </div>',
    '  </div>',
    '  <div class="kb-batch-bar" v-if="batchMode">',
    '    <n-checkbox :checked="allPicked" @update:checked="toggleAll">{{ t("batch_select_all") }}</n-checkbox>',
    '    <span class="qvq-meta-line">{{ picked.length }} / {{ shownSkills.length }}</span>',
    '    <n-button size="tiny" type="error" :disabled="!picked.length" :loading="batchBusy" @click="batchDel">',
    '      {{ t("batch_delete") }}</n-button>',
    '    <span class="qvq-meta-line" v-if="!picked.length">{{ t("batch_none_selected") }}</span>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div class="prov-grid" v-if="!loading">',
    '    <article v-for="sk in shownSkills" :key="sk.name" class="prov-card"',
    '             :class="{ off: sk.disabled, \'is-picked\': batchMode && picked.indexOf(sk.name) >= 0 }"',
    '             @click="batchMode && togglePick(sk.name)">',
    '      <header class="prov-head">',
    '        <div class="prov-title"><span class="prov-name">{{ sk.name }}</span></div>',
    '        <n-checkbox v-if="batchMode" :checked="picked.indexOf(sk.name) >= 0" @click.stop',
    '                    @update:checked="function(){ togglePick(sk.name); }"/>',
    '        <n-switch v-else size="small" :value="!sk.disabled" @update:value="toggle(sk)"/>',
    '      </header>',
    '      <div class="tool-desc">{{ sk.description }}</div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-count">{{ sk.origin || "" }}</span>',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click.stop="openEdit(sk)">{{ t("edit") }}</button>',
    '          <button v-if="sk.origin !== \'external\'" type="button" class="prov-act danger" @click.stop="del(sk)">',
    '            {{ t("chat_delete") }}</button>',
    '        </span>',
    '      </footer>',
    '    </article>',
    '  </div>',
    '  <div v-if="!skills.length" class="qvq-empty">-</div>',
    '  <n-drawer v-model:show="drawer" :width="480" placement="right">',
    '    <n-drawer-content :title="form.isNew ? t(\'add_title\') : t(\'edit\')" closable>',
    '      <div class="prov-form">',
    '        <div class="prov-field">',
    '          <label>{{ t("models_name") }}</label>',
    '          <n-input v-model:value="form.name" :disabled="!form.isNew"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("item_desc") }}</label>',
    '          <n-input v-model:value="form.description"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("skills_body") }}</label>',
    '          <n-input v-model:value="form.body" type="textarea" :rows="12" class="cf-mono"/>',
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
