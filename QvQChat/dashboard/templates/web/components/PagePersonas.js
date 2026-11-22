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
      pvOpen: false,
      pv: null,
      bindings: {},
      sessionNames: {},
    };
  },
  mounted() {
    this.load();
    this.loadNames();
  },
  computed: {
    bindGroups() {
      // 反查表：persona_id → [{key, level, label}]；level 由绑定键形态判定
      var names = this.sessionNames;
      var out = {};
      Object.keys(this.bindings).forEach(function (key) {
        var pid = this.bindings[key];
        var level = "chat";
        if (key.indexOf("@") === 0) level = "account";
        else if (/:\*$/.test(key)) level = "platform";
        var label = key;
        if (level === "platform") label = key.replace(/:\*$/, "");
        else if (names[key]) label = names[key];
        (out[pid] = out[pid] || []).push({ key: key, level: level, label: label });
      }, this);
      return out;
    },
  },
  methods: {
    load() {
      var self = this;
      return api("/api/qvq/personas").then(function (d) {
        self.personas = (d && d.personas) || [];
        self.bindings = (d && d.bindings) || {};
      });
    },
    loadNames() {
      var self = this;
      return api("/api/qvq/sessions?limit=200").then(function (d) {
        var map = {};
        ((d && d.sessions) || []).forEach(function (s) {
          map[s.chat_key] = s.name || s.chat_key;
        });
        self.sessionNames = map;
      });
    },
    bindLevelLabel(level) {
      return t(level === "platform" ? "bind_level_platform"
        : level === "account" ? "bind_level_account" : "bind_level_session");
    },
    openSession(key) {
      QvQ.store.pendingChat = key;
      QvQ.store.page = "chat";
    },
    chatWith(p) {
      // 试聊该人格：新建 dashboard 沙箱会话、命名并绑定，跳对话页
      var self = this;
      api("/api/qvq/sessions/create", "POST", {})
        .then(function (d) {
          var key = (d && d.chat_key) || "";
          if (!key) return;
          return api("/api/qvq/session/rename", "POST", {
            chat_key: key, name: t("sandbox_with").replace("{n}", p.name || p.id),
          }).then(function () {
            return api("/api/qvq/personas/bind", "POST", { chat_key: key, persona: p.id });
          }).then(function () {
            QvQ.store.pendingChat = key;
            QvQ.store.page = "chat";
          });
        });
    },
    openPreview(p) {
      this.pv = p;
      this.pvOpen = true;
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
    '<settings-section group="humanize,trigger,participation" :title="t(&quot;ss_persona&quot;)"/>',
    '  <div class="prov-grid">',
    '    <article v-for="p in personas" :key="p.id" class="prov-card persona-card" @click="openPreview(p)">',
    '      <header class="prov-head">',
    '        <div class="prov-title">',
    '          <span class="prov-name">{{ p.name || p.id }}</span>',
    '          <span class="prov-id">{{ p.id }}</span>',
    '        </div>',
    '        <span class="persona-open" :title="t(&quot;col_preview&quot;)">›</span>',
    '      </header>',
    '      <div class="tool-desc">{{ (p.system || "").slice(0, 120) }}</div>',
    '      <div class="persona-binds" v-if="(bindGroups[p.id] || []).length">',
    '        <button v-for="b in bindGroups[p.id]" :key="b.key" type="button" class="persona-bind"',
    '                :title="b.key" @click.stop="openSession(b.key)">',
    '          <i class="persona-bind-lv">{{ bindLevelLabel(b.level) }}</i>{{ b.label }}</button>',
    '      </div>',
    '      <div class="qvq-meta-line" v-else style="margin:0 0 8px">{{ t("persona_unbound") }}</div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click.stop="chatWith(p)">{{ t("persona_chat") }}</button>',
    '          <button type="button" class="prov-act" @click.stop="openEdit(p)">{{ t("edit") }}</button>',
    '          <button type="button" class="prov-act danger" @click.stop="del(p)">{{ t("chat_delete") }}</button>',
    '        </span>',
    '      </footer>',
    '    </article>',
    '  </div>',
    '  <div v-if="!personas.length" class="qvq-empty">-</div>',
    '  <n-drawer v-model:show="pvOpen" :width="440" placement="right">',
    '    <n-drawer-content :title="pv ? (pv.name || pv.id) : \'\'" closable>',
    '      <div class="prov-form" v-if="pv">',
    '        <div class="prov-field">',
    '          <label>System</label>',
    '          <pre class="stor-pre">{{ pv.system || "-" }}</pre>',
    '        </div>',
    '        <div class="prov-field" v-if="(pv.opening || []).length">',
    '          <label>{{ t("personas_prefill") }}</label>',
    '          <pre class="stor-pre">{{ (pv.opening || []).join("\\n") }}</pre>',
    '        </div>',
    '        <div class="prov-field" v-if="(pv.catchphrases || []).length">',
    '          <label>{{ t("personas_catchphrases") }}</label>',
    '          <pre class="stor-pre">{{ (pv.catchphrases || []).join("\\n") }}</pre>',
    '        </div>',
    '        <div class="prov-field" v-if="(pv.banned_words || []).length">',
    '          <label>{{ t("personas_banned") }}</label>',
    '          <pre class="stor-pre">{{ (pv.banned_words || []).join("\\n") }}</pre>',
    '        </div>',
    '      </div>',
    '      <template #footer>',
    '        <div class="qvq-modal-foot">',
    '          <n-button size="small" @click="pvOpen = false; openEdit(pv)">{{ t("edit") }}</n-button>',
    '        </div>',
    '      </template>',
    '    </n-drawer-content>',
    '  </n-drawer>',
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
