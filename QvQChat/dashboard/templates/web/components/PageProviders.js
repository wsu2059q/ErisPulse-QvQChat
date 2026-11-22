/* 模型池：提供商卡片 / 提供商编辑 / 模型编辑 / 远程拉取 / 连通测试 */
window.PageProviders = {
  name: "PageProviders",
  data() {
    return {
      loading: true,
      providers: [],
      chain: [],
      models: [],
      presets: [],
      defaultModel: "",
      drawer: false,
      isNew: false,
      form: {
        id: "", name: "", base_url: "", api_key: "", enabled: true,
        reasoning_effort: "", models: [],
      },
      formErr: "",
      saving: false,
      remote: false,
      remoteLoading: false,
      remoteList: [],
      remotePicked: [],
      remoteErr: "",
      modelDrawer: false,
      modelForm: null,
      detectBusy: false,
      modelProviderId: "",
      testState: {},
      brokenLogo: {},
      delOpen: false,
      delTarget: null,
      vw: typeof window === "undefined" ? 1024 : window.innerWidth,
    };
  },
  computed: {
    drawerWidth() {
      return Math.max(280, Math.min(520, this.vw - 12)) + "px";
    },
    defaultOptions() {
      return this.models.map(function (m) { return { label: m.id, value: m.id }; });
    },
    effortOptions() {
      return [
        { label: t("model_effort_follow"), value: "" },
        { label: "off", value: "off" },
        { label: "low", value: "low" },
        { label: "medium", value: "medium" },
        { label: "high", value: "high" },
      ];
    },
    prefillOptions() {
      return [
        { label: t("model_prefill_auto"), value: "auto" },
        { label: t("model_prefill_yes"), value: "yes" },
        { label: t("model_prefill_no"), value: "no" },
      ];
    },
    logoDomain() {
      var map = {};
      this.presets.forEach(function (p) { map[p.id] = p.domain || ""; });
      return map;
    },
    presetRenderer() {
      return this.renderPreset.bind(this);
    },
    presetOptions() {
      return this.presets.map(function (p) { return { label: p.name, value: p.id }; });
    },
    chainRank() {
      var map = {};
      this.chain.forEach(function (entry, i) {
        map[entry.provider + ":" + (entry.model && entry.model.id)] = i + 1;
      });
      return map;
    },
  },
  mounted() {
    var self = this;
    this.load();
    this._onResize = function () { self.vw = window.innerWidth; };
    window.addEventListener("resize", this._onResize);
  },
  beforeUnmount() {
    window.removeEventListener("resize", this._onResize);
  },
  methods: {
    load() {
      var self = this;
      return api("/api/qvq/models").then(function (d) {
        self.providers = (d && d.providers) || [];
        self.chain = (d && d.chain) || [];
        self.models = (d && d.models) || [];
        self.presets = (d && d.presets) || [];
        self.defaultModel = (d && d.default) || "";
        self.loading = false;
      });
    },
    rankOf(providerId, modelId) {
      return this.chainRank[providerId + ":" + modelId] || 0;
    },
    add() {
      this.isNew = true;
      this.form = {
        id: "p" + Date.now().toString(36), name: "", base_url: "", api_key: "",
        enabled: true, reasoning_effort: "", models: [],
      };
      this.formErr = "";
      this.drawer = true;
    },
    edit(p) {
      this.isNew = false;
      this.form = {
        id: p.id,
        name: p.name || "",
        base_url: p.base_url || "",
        api_key: "",
        enabled: p.enabled !== false,
        reasoning_effort: p.reasoning_effort || "",
        models: JSON.parse(JSON.stringify(p.models || [])),
      };
      this.formErr = "";
      this.drawer = true;
    },
    applyPreset(id) {
      var preset = this.presets.filter(function (p) { return p.id === id; })[0];
      if (!preset) return;
      this.form.id = preset.id;
      this.form.name = preset.name;
      this.form.base_url = preset.base_url;
    },
    matchPreset() {
      // base_url 与预设域名对上时自动应用（仅新增态；名字留空才回填）
      if (!this.isNew) return;
      var self = this;
      var host = this.hostOf(this.form.base_url);
      if (!host) return;
      var hit = this.presets.filter(function (pp) {
        return (pp.domain || "") === host || self.hostOf(pp.base_url) === host;
      })[0];
      if (hit) {
        this.form.id = hit.id;
        if (!this.form.name) this.form.name = hit.name;
      }
    },
    save() {
      var self = this;
      if (this.saving) return;
      this.saving = true;
      api("/api/qvq/providers/save", "POST", {
        id: this.form.id,
        name: this.form.name,
        base_url: this.form.base_url,
        api_key: this.form.api_key,
        enabled: this.form.enabled,
        reasoning_effort: this.form.reasoning_effort || "",
        models: this.form.models,
      }).then(function (r) {
        self.saving = false;
        if (r && r.error) {
          self.formErr = r.error;
          return;
        }
        self.drawer = false;
        self.load();
      });
    },
    removeProvider(p) {
      this.delTarget = p;
      this.delOpen = true;
    },
    confirmDelete() {
      var self = this;
      var target = this.delTarget;
      this.delOpen = false;
      if (!target) return;
      api("/api/qvq/providers/delete", "POST", { id: target.id }).then(function () {
        self.delTarget = null;
        self.load();
      });
    },
    toggle(p, value) {
      var self = this;
      api("/api/qvq/providers/toggle", "POST", { id: p.id, enabled: value }).then(function () {
        p.enabled = value;
        self.load();
      });
    },
    testProvider(p) {
      var self = this;
      var first = (p.models || [])[0];
      if (!first) return;
      var target = p.id + ":" + (first.id || first);
      self.testState = Object.assign({}, self.testState, { [p.id]: { busy: true, text: t("prov_testing") } });
      api("/api/qvq/models/test", "POST", { id: target }).then(function (r) {
        var state = r && r.ok
          ? { ok: true, text: t("model_test_ok") + " · " + r.ms + "ms" }
          : { ok: false, text: (r && r.error) || t("model_test_fail") };
        self.testState = Object.assign({}, self.testState, { [p.id]: state });
      });
    },
    openRemote() {
      var self = this;
      self.remote = true;
      self.remoteLoading = true;
      self.remotePicked = [];
      self.remoteErr = "";
      api("/api/qvq/providers/remote-models", "POST", {
        id: self.form.id,
        base_url: self.form.base_url,
        api_key: self.form.api_key,
      }).then(function (r) {
        self.remoteLoading = false;
        if (r && r.error) {
          self.remoteErr = r.error;
          self.remoteList = [];
          return;
        }
        var own = self.form.models.map(function (m) { return m.id || m; });
        self.remoteList = ((r && r.models) || []).filter(function (m) {
          return own.indexOf(m.id || m) < 0;
        });
      });
    },
    pickAll() {
      this.remotePicked = this.remoteList.map(function (m) { return m.id || m; });
    },
    applyRemote() {
      var self = this;
      var picked = this.remotePicked;
      this.remoteList.forEach(function (m) {
        if (picked.indexOf(m.id || m) < 0) return;
        self.form.models.push(typeof m === "string" ? { id: m } : m);
      });
      this.remote = false;
    },
    dropModel(index) {
      this.form.models.splice(index, 1);
    },
    detectMeta() {
      // 探测模型元数据（context_length/max_output_tokens）回填表单；密钥用当前供应商
      var self = this;
      var provider = this.providers.filter(function (p) { return p.id === self.modelProviderId; })[0];
      if (!provider || !this.modelForm || !this.modelForm.id) return;
      this.detectBusy = true;
      api("/api/qvq/models/detect", "POST", {
        model: this.modelForm.id,
        provider: { base_url: provider.base_url, api_key: provider.api_key },
      }).then(function (r) {
        self.detectBusy = false;
        if (!r || r.error) {
          QvQ.toast(QvQ.fill("organize_fail", { error: (r && r.error) || "?" }));
          return;
        }
        var m = r.meta || {};
        if (m.context_length) self.modelForm.context_length = m.context_length;
        if (m.max_output_tokens) self.modelForm.max_output_tokens = m.max_output_tokens;
        if (m.reasoning === true || m.reasoning === false) self.modelForm.reasoning = m.reasoning;
        if (m.vision === true || m.vision === false) self.modelForm.vision = m.vision;
        if (m.tool_call === true || m.tool_call === false) self.modelForm.tool_call = m.tool_call;
        QvQ.toast(t("models_detect_done"));
      }).catch(function () {
        self.detectBusy = false;
        QvQ.toast(QvQ.fill("organize_fail", { error: "network" }));
      });
    },
    openModel(p, m) {
      var copy = JSON.parse(JSON.stringify(m));
      this.modelProviderId = p.id;
      this.modelForm = {
        id: copy.id || "",
        enabled: copy.enabled !== false,
        temperature: copy.temperature,
        max_tokens: copy.max_tokens,
        context_length: copy.context_length,
        max_output_tokens: copy.max_output_tokens,
        reasoning_effort: copy.reasoning_effort || "",
        prefill_ok: copy.prefill_ok === true ? "yes" : (copy.prefill_ok === false ? "no" : "auto"),
        tool_call: !!copy.tool_call,
        reasoning: !!copy.reasoning,
        vision: !!copy.vision,
        files: !!copy.files,
        video: !!copy.video,
        cost_in: (copy.cost && copy.cost.input) || 0,
        cost_out: (copy.cost && copy.cost.output) || 0,
        notes: copy.notes || "",
        raw: copy,
      };
      this.modelDrawer = true;
    },
    saveModel() {
      var self = this;
      var provider = this.providers.filter(function (p) { return p.id === self.modelProviderId; })[0];
      var form = this.modelForm;
      if (!provider || !form) return;
      var prefill = form.prefill_ok === "yes" ? true : (form.prefill_ok === "no" ? false : null);
      var model = Object.assign({}, form.raw || {}, {
        id: form.id,
        enabled: !!form.enabled,
        temperature: form.temperature,
        max_tokens: form.max_tokens,
        context_length: form.context_length,
        max_output_tokens: form.max_output_tokens,
        reasoning_effort: form.reasoning_effort || "",
        prefill_ok: prefill,
        tool_call: !!form.tool_call,
        reasoning: !!form.reasoning,
        vision: !!form.vision,
        files: !!form.files,
        video: !!form.video,
        cost: { input: Number(form.cost_in) || 0, output: Number(form.cost_out) || 0 },
        notes: form.notes,
      });
      var oldId = (form.raw && form.raw.id) || form.id;
      var replaced = false;
      var models = (provider.models || []).map(function (m) {
        if ((m.id || "") === oldId) {
          replaced = true;
          return model;
        }
        return m;
      });
      if (!replaced) models.push(model);
      api("/api/qvq/providers/save", "POST", {
        id: provider.id,
        name: provider.name,
        base_url: provider.base_url,
        reasoning_effort: provider.reasoning_effort || "",
        enabled: provider.enabled !== false,
        models: models,
      }).then(function (r) {
        if (r && r.error) return;
        self.modelDrawer = false;
        self.load();
      });
    },
    setDefault(value) {
      var self = this;
      this.defaultModel = value;
      api("/api/qvq/config", "POST", { default_model: value }).then(function () {
        self.load();
      });
    },
    refreshMeta() {
      var self = this;
      api("/api/qvq/models/enrich", "POST", {}).then(function () { self.load(); });
    },
    hostOf(url) {
      var m = String(url || "").match(/^https?:\/\/([^/:]+)/);
      return m ? m[1].replace(/^api\./, "") : "";
    },
    domainOf(p) {
      return this.logoDomain[p.id] || this.hostOf(p.base_url);
    },
    logoSrc(p) {
      if (this.brokenLogo[p.id]) return "";
      var domain = this.domainOf(p);
      return domain ? "/QvQChat/api/qvq/logo?domain=" + encodeURIComponent(domain) : "";
    },
    dropLogo(id) {
      this.brokenLogo = Object.assign({}, this.brokenLogo, { [id]: true });
    },
    renderPreset(option) {
      var domain = this.logoDomain[option.value] || this.hostOf(option.base_url);
      var src = domain ? "/QvQChat/api/qvq/logo?domain=" + encodeURIComponent(domain) : "";
      var kids = [];
      if (src) {
        kids.push(Vue.h("img", {
          class: "prov-opt-logo",
          src: src,
          onError: function (e) { e.target.style.visibility = "hidden"; },
        }));
      }
      kids.push(Vue.h("span", null, option.label));
      return Vue.h("div", { class: "prov-opt" }, kids);
    },
    providerModels(p) {
      return p.models || [];
    },
    shownModels(p) {
      return (p.models || []).slice(0, 6);
    },
    hiddenCount(p) {
      return Math.max(0, (p.models || []).length - 6);
    },
    editModelInDrawer(m) {
      var provider = this.form;
      var copy = JSON.parse(JSON.stringify(m));
      this.modelProviderId = provider.id;
      this.modelForm = {
        id: copy.id || "",
        enabled: copy.enabled !== false,
        temperature: copy.temperature,
        max_tokens: copy.max_tokens,
        context_length: copy.context_length,
        max_output_tokens: copy.max_output_tokens,
        reasoning_effort: copy.reasoning_effort || "",
        prefill_ok: copy.prefill_ok === true ? "yes" : (copy.prefill_ok === false ? "no" : "auto"),
        tool_call: !!copy.tool_call,
        reasoning: !!copy.reasoning,
        vision: !!copy.vision,
        files: !!copy.files,
        video: !!copy.video,
        cost_in: (copy.cost && copy.cost.input) || 0,
        cost_out: (copy.cost && copy.cost.output) || 0,
        notes: copy.notes || "",
        raw: copy,
      };
      this.modelDrawer = true;
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_models") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <span class="prov-default-label">{{ t("models_default") }}</span>',
    '      <n-select :value="defaultModel" :options="defaultOptions" size="small" filterable',
    '                style="width:230px" :placeholder="t(\'models_default\')"',
    '                @update:value="setDefault"/>',
    '      <n-button size="small" @click="refreshMeta">{{ t("model_refresh") }}</n-button>',
    '      <n-button size="small" type="primary" @click="add">{{ t("prov_add") }}</n-button>',
    '    </div>',
    '  </div>',
    '<settings-section group="model" :title="t(&quot;ss_model&quot;)"/>',
    '  <div v-if="!loading && !providers.length" class="qvq-empty">{{ t("models_empty") }}</div>',
    '  <div class="prov-grid">',
    '    <article v-for="p in providers" :key="p.id" class="prov-card" :class="{ off: p.enabled === false }">',
    '      <header class="prov-head">',
    '        <div class="prov-title">',
    '          <img v-if="logoSrc(p)" class="prov-logo" :src="logoSrc(p)" alt="" loading="lazy" decoding="async"',
    '               @error="dropLogo(p.id)"/>',
    '          <span class="prov-name">{{ p.name || p.id }}</span>',
    '          <span class="prov-id">{{ p.id }}</span>',
    '        </div>',
    '        <n-switch :value="p.enabled !== false" size="small"',
    '                  @update:value="toggle(p, $event)"/>',
    '      </header>',
    '      <div class="prov-url" :title="p.base_url">{{ p.base_url }}</div>',
    '      <div class="prov-key">{{ p.api_key_masked || t("prov_key_empty") }}</div>',
    '      <div class="prov-models">',
    '        <button v-for="m in shownModels(p)" :key="m.id" type="button"',
    '                class="prov-chip" @click="openModel(p, m)">',
    '          <span class="prov-chip-id">{{ m.id }}</span>',
    '          <span class="prov-chip-rank" v-if="rankOf(p.id, m.id)">#{{ rankOf(p.id, m.id) }}</span>',
    '        </button>',
    '        <button v-if="hiddenCount(p)" type="button" class="prov-chip more"',
    '                @click="edit(p)">+{{ hiddenCount(p) }}</button>',
    '        <span class="prov-chip empty" v-if="!providerModels(p).length">{{ t("model_none") }}</span>',
    '      </div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-count">{{ providerModels(p).length }} {{ t("prov_models") }}</span>',
    '        <span class="prov-state" v-if="testState[p.id]"',
    '              :class="{ ok: testState[p.id].ok, err: testState[p.id].ok === false }">',
    '          {{ testState[p.id].text }}',
    '        </span>',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click="testProvider(p)">{{ t("prov_test") }}</button>',
    '          <button type="button" class="prov-act" @click="edit(p)">{{ t("edit") }}</button>',
    '          <button type="button" class="prov-act danger" @click="removeProvider(p)">{{ t("prov_delete") }}</button>',
    '        </span>',
    '      </footer>',
    '    </article>',
    '  </div>',
    '  <n-drawer v-model:show="drawer" :width="drawerWidth" placement="right">',
    '    <n-drawer-content :title="isNew ? t(\'prov_add\') : t(\'prov_edit\')" closable>',
    '      <div class="prov-form">',
    '        <div class="prov-field" v-if="isNew">',
    '          <label>{{ t("models_preset") }}</label>',
    '          <n-select :options="presetOptions" filterable :render-label="presetRenderer"',
    '                    @update:value="applyPreset"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("models_name") }}</label>',
    '          <n-input v-model:value="form.name"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("models_baseurl") }}</label>',
    '          <n-input v-model:value="form.base_url" placeholder="https://api.example.com/v1"',
    '                   @update:value="matchPreset"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("models_apikey") }}</label>',
    '          <n-input v-model:value="form.api_key" type="password" show-password-on="click"',
    '                   :placeholder="t(\'models_apikey\')"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("model_effort") }}</label>',
    '          <n-select v-model:value="form.reasoning_effort" :options="effortOptions"/>',
    '          <div class="qvq-meta-line">{{ t("model_effort_provider_hint") }}</div>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("model_manage") }}</label>',
    '          <div class="prov-model-list">',
    '            <div v-for="(m, i) in form.models" :key="m.id" class="prov-model-row">',
    '              <button type="button" class="prov-model-edit" @click="editModelInDrawer(m)">{{ m.id }}</button>',
    '              <button type="button" class="prov-act danger" @click="dropModel(i)">×</button>',
    '            </div>',
    '            <div class="prov-model-row" v-if="!form.models.length">',
    '              <span class="qvq-meta-line">{{ t("model_none") }}</span>',
    '            </div>',
    '          </div>',
    '          <n-button size="small" style="margin-top:8px" :loading="remoteLoading" @click="openRemote">',
    '            {{ t("models_fetch") }}',
    '          </n-button>',
    '        </div>',
    '        <div class="cf-error" v-if="formErr">{{ formErr }}</div>',
    '      </div>',
    '      <template #footer>',
    '        <div class="qvq-modal-foot">',
    '          <n-button size="small" @click="drawer = false">{{ t("cancel") }}</n-button>',
    '          <n-button size="small" type="primary" :loading="saving" @click="save">{{ t("save") }}</n-button>',
    '        </div>',
    '      </template>',
    '    </n-drawer-content>',
    '  </n-drawer>',
    '  <n-modal v-model:show="modelDrawer" preset="card" class="qvq-modal-card" style="max-width:520px"',
    '           :title="t(\'model_edit_title\')" :bordered="false">',
    '    <div class="prov-form" v-if="modelForm">',
    '      <div class="prov-field">',
    '        <label>{{ t("prov_model_id") }}',
    '          <n-button size="tiny" :loading="detectBusy" style="margin-left:8px" @click="detectMeta">',
    '            {{ t("models_detect") }}</n-button></label>',
    '        <n-input v-model:value="modelForm.id"/>',
    '      </div>',
    '      <div class="prov-field row">',
    '        <label>{{ t("model_enabled") }}</label>',
    '        <n-switch v-model:value="modelForm.enabled"/>',
    '      </div>',
    '      <div class="prov-grid2">',
    '        <div class="prov-field">',
    '          <label>{{ t("model_context") }}</label>',
    '          <n-input-number v-model:value="modelForm.context_length" :min="0"',
    '                          :show-button="false" style="width:100%"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("models_maxtok") }}</label>',
    '          <n-input-number v-model:value="modelForm.max_tokens" :min="0"',
    '                          :show-button="false" style="width:100%"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("model_max_output") }}</label>',
    '          <n-input-number v-model:value="modelForm.max_output_tokens" :min="0"',
    '                          :show-button="false" style="width:100%"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("models_temp") }}</label>',
    '          <n-input-number v-model:value="modelForm.temperature" :step="0.1" :min="0" :max="2"',
    '                          :show-button="false" style="width:100%"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("model_price_in") }}</label>',
    '          <n-input-number v-model:value="modelForm.cost_in" :min="0"',
    '                          :show-button="false" style="width:100%"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("model_price_out") }}</label>',
    '          <n-input-number v-model:value="modelForm.cost_out" :min="0"',
    '                          :show-button="false" style="width:100%"/>',
    '        </div>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("model_effort") }}</label>',
    '        <n-select v-model:value="modelForm.reasoning_effort" :options="effortOptions"/>',
    '        <div class="qvq-meta-line">{{ t("model_effort_hint") }}</div>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("model_prefill_ok") }}</label>',
    '        <n-select v-model:value="modelForm.prefill_ok" :options="prefillOptions"/>',
    '        <div class="qvq-meta-line">{{ t("model_prefill_hint") }}</div>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("model_caps") }}</label>',
    '        <div class="prov-caps">',
    '          <n-checkbox v-model:checked="modelForm.tool_call" :label="t(\'model_cap_tools\')"/>',
    '          <n-checkbox v-model:checked="modelForm.reasoning" :label="t(\'model_cap_reason\')"/>',
    '          <n-checkbox v-model:checked="modelForm.vision" :label="t(\'model_cap_vision\')"/>',
    '          <n-checkbox v-model:checked="modelForm.files" :label="t(\'model_input_pdf\')"/>',
    '          <n-checkbox v-model:checked="modelForm.video" :label="t(\'model_input_video\')"/>',
    '        </div>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("model_notes") }}</label>',
    '        <n-input v-model:value="modelForm.notes" :placeholder="t(\'model_notes_ph\')"/>',
    '      </div>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="modelDrawer = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" @click="saveModel">{{ t("save") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="delOpen" preset="card" class="qvq-modal-card" style="max-width:380px"',
    '           :title="t(\'prov_delete\')" :bordered="false">',
    '    <div class="qvq-modal-hint">{{ t("prov_delete_confirm") }}</div>',
    '    <div class="cf-confirm-keys"><code v-if="delTarget">{{ delTarget.name || delTarget.id }}</code></div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="delOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="error" @click="confirmDelete">{{ t("confirm_yes") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="remote" preset="card" class="qvq-modal-card" style="max-width:520px"',
    '           :title="t(\'prov_remote_pick\')" :bordered="false">',
    '    <div class="prov-remote-bar">',
    '      <n-button size="tiny" @click="pickAll">{{ t("prov_remote_all") }}</n-button>',
    '      <span class="qvq-meta-line">{{ remotePicked.length }} / {{ remoteList.length }}</span>',
    '    </div>',
    '    <div class="prov-remote-list">',
    '      <div v-if="remoteLoading" class="qvq-empty">{{ t("models_fetching") }}</div>',
    '      <div v-else-if="remoteErr" class="cf-error">{{ remoteErr }}</div>',
    '      <div v-else-if="!remoteList.length" class="qvq-empty">{{ t("models_remote_empty") }}</div>',
    '      <n-checkbox-group v-else v-model:value="remotePicked">',
    '        <div v-for="m in remoteList" :key="m.id || m" class="prov-remote-row">',
    '          <n-checkbox :value="m.id || m" :label="m.id || m"/>',
    '        </div>',
    '      </n-checkbox-group>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="remote = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" @click="applyRemote">{{ t("prov_remote_add") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '</div>',
  ].join(""),
};
