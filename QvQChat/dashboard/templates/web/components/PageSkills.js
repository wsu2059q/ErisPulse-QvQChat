/* 技能：卡片列表 / 启停 / 新建与编辑（名称+描述+正文） */
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
    };
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      return QvQ.swr(self, "skills", "/api/qvq/skills", function (d) {
        self.skills = (d && d.skills) || [];
      });
    },
    openNew() {
      this.form = { name: "", description: "", body: "", isNew: true };
      this.formErr = "";
      this.drawer = true;
    },
    openEdit(sk) {
      var self = this;
      api("/api/qvq/skills").then(function () {
        self.form = {
          name: sk.name,
          description: sk.description || "",
          body: sk.body || "",
          isNew: false,
        };
        self.formErr = "";
        self.drawer = true;
      });
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
    '      <n-button size="small" type="primary" @click="openNew">{{ t("add_title") }}</n-button>',
    '    </div>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div class="prov-grid" v-if="!loading">',
    '    <article v-for="sk in skills" :key="sk.name" class="prov-card"',
    '             :class="{ off: sk.disabled }" v-show="!q || (sk.name + sk.description).toLowerCase().indexOf(q.toLowerCase()) >= 0">',
    '      <header class="prov-head">',
    '        <div class="prov-title"><span class="prov-name">{{ sk.name }}</span></div>',
    '        <n-switch size="small" :value="!sk.disabled" @update:value="toggle(sk)"/>',
    '      </header>',
    '      <div class="tool-desc">{{ sk.description }}</div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-count">{{ sk.origin || "" }}</span>',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click="openEdit(sk)">{{ t("edit") }}</button>',
    '          <button v-if="sk.origin !== \'external\'" type="button" class="prov-act danger" @click="del(sk)">',
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
