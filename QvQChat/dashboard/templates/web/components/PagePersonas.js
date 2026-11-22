/* 人格：卡片列表 / 编辑（system/行为/参数）/ 删除 */
window.PagePersonas = {
  name: "PagePersonas",
  data() {
    return {
      personas: [],
      drawer: false,
      isNew: false,
      form: {
        id: "", name: "", system: "", nickname: "", owner: "",
        opening: "", banned: "", catchphrases: "",
        temperature: null, max_tokens: null,
      },
      formErr: "",
      busy: false,
    };
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      return api("/api/qvq/personas").then(function (d) {
        self.personas = (d && d.personas) || [];
      });
    },
    openNew() {
      this.isNew = true;
      this.form = {
        id: "p" + Date.now().toString(36), name: "", system: "", nickname: "", owner: "",
        opening: "", banned: "", catchphrases: "", temperature: null, max_tokens: null,
      };
      this.formErr = "";
      this.drawer = true;
    },
    openEdit(p) {
      this.isNew = false;
      this.form = {
        id: p.id,
        name: p.name || "",
        system: p.system || "",
        nickname: p.nickname || "",
        owner: p.owner || "",
        opening: (p.opening || []).join("\n"),
        banned: (p.banned_words || []).join("\n"),
        catchphrases: (p.catchphrases || []).join("\n"),
        temperature: p.temperature != null ? p.temperature : null,
        max_tokens: p.max_tokens != null ? p.max_tokens : null,
      };
      this.formErr = "";
      this.drawer = true;
    },
    save() {
      var self = this;
      var lines = function (text) {
        return String(text || "").split("\n").map(function (x) { return x.trim(); }).filter(Boolean);
      };
      this.busy = true;
      api("/api/qvq/personas/save", "POST", {
        id: this.form.id,
        name: this.form.name,
        system: this.form.system,
        nickname: this.form.nickname,
        owner: this.form.owner,
        opening: lines(this.form.opening),
        banned_words: lines(this.form.banned),
        catchphrases: lines(this.form.catchphrases),
        temperature: this.form.temperature,
        max_tokens: this.form.max_tokens,
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
    del(p) {
      var self = this;
      api("/api/qvq/personas/delete", "POST", { id: p.id }).then(function () { self.load(); });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_personas") }}</div>',
    '      <div class="qvq-page-sub">{{ personas.length }} {{ t("nav_personas") }}</div>',
    '    </div>',
    '    <n-button size="small" type="primary" @click="openNew">{{ t("add_title") }}</n-button>',
    '  </div>',
    '<settings-section group="persona" :title="t(&quot;ss_persona&quot;)"/>',
    '  <div class="prov-grid">',
    '    <article v-for="p in personas" :key="p.id" class="prov-card">',
    '      <header class="prov-head">',
    '        <div class="prov-title">',
    '          <span class="prov-name">{{ p.name || p.id }}</span>',
    '          <span class="prov-id">{{ p.id }}</span>',
    '        </div>',
    '      </header>',
    '      <div class="tool-desc">{{ (p.system || "").slice(0, 120) }}</div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-count">{{ (p.opening || []).length ? "opening ✓" : "" }}</span>',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click="openEdit(p)">{{ t("edit") }}</button>',
    '          <button type="button" class="prov-act danger" @click="del(p)">{{ t("chat_delete") }}</button>',
    '        </span>',
    '      </footer>',
    '    </article>',
    '  </div>',
    '  <n-drawer v-model:show="drawer" :width="520" placement="right">',
    '    <n-drawer-content :title="isNew ? t(\'add_title\') : t(\'edit\')" closable>',
    '      <div class="prov-form">',
    '        <div class="prov-field">',
    '          <label>{{ t("models_name") }}</label>',
    '          <n-input v-model:value="form.name"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>System</label>',
    '          <n-input v-model:value="form.system" type="textarea" :rows="6"/>',
    '        </div>',
    '        <div class="prov-grid2">',
    '          <div class="prov-field">',
    '            <label>{{ t("personas_nickname") }}</label>',
    '            <n-input v-model:value="form.nickname"/>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>{{ t("personas_owner_title") }}</label>',
    '            <n-input v-model:value="form.owner" :placeholder="t(\'personas_owner_ph\')"/>',
    '          </div>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("personas_prefill") }}</label>',
    '          <n-input v-model:value="form.opening" type="textarea" :rows="2" :placeholder="t(\'personas_prefill_hint\')"/>',
    '        </div>',
    '        <div class="prov-grid2">',
    '          <div class="prov-field">',
    '            <label>{{ t("personas_catchphrases") }}</label>',
    '            <n-input v-model:value="form.catchphrases" type="textarea" :rows="3"/>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>{{ t("personas_banned") }}</label>',
    '            <n-input v-model:value="form.banned" type="textarea" :rows="3"/>',
    '          </div>',
    '        </div>',
    '        <div class="prov-grid2">',
    '          <div class="prov-field">',
    '            <label>{{ t("models_temp") }}</label>',
    '            <n-input-number v-model:value="form.temperature" :min="0" :max="2" :step="0.1"',
    '                            :show-button="false" style="width:100%"/>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>{{ t("models_maxtok") }}</label>',
    '            <n-input-number v-model:value="form.max_tokens" :min="0" :show-button="false" style="width:100%"/>',
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
