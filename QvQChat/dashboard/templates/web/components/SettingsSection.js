/* SettingsSection：功能页内的「相关设置」区块（设置就近化）。
   props.group 取 Config schema 的分组 id；读 /api/qvq/config 过滤本组字段渲染，
   保存只提交本组已改键。供人格/知识库/模型池等页就近放各自的开关，硬核设置仍留设置页。 */
window.SettingsSection = {
  name: "SettingsSection",
  props: {
    group: { type: String, required: true },
    title: { type: String, default: "" },
  },
  data() {
    return {
      fields: [],
      draft: {},
      saved: "",
      loading: true,
      saving: false,
      open: false,
    };
  },
  computed: {
    shown() {
      return this.fields.filter(function (f) { return f.group === this.group; }.bind(this));
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      return QvQ.swr(this, "cfg_group_" + this.group, "/api/qvq/config", function (data) {
        var fields = ((data && data.fields) || []).filter(function (f) { return f.group === self.group; });
        self.fields = fields;
        var draft = {};
        fields.forEach(function (f) { draft[f.key] = f.value; });
        self.draft = draft;
      });
    },
    titleOf(f) { return QvQ.fieldTitle(f.description, f.key); },
    hintOf(f) {
      var text = QvQ.fieldDesc(f.description, f.key);
      var cut = text ? text.search(/[。！?]/) : -1;
      if (cut >= 0 && cut + 1 < text.length) return text.slice(0, cut + 1);
      return text;
    },
    isDirty(f) {
      return JSON.stringify(this.draft[f.key]) !== JSON.stringify(f.value);
    },
    save() {
      var self = this;
      var body = {};
      this.shown.forEach(function (f) {
        if (JSON.stringify(self.draft[f.key]) !== JSON.stringify(f.value)) body[f.key] = self.draft[f.key];
      });
      if (!Object.keys(body).length) return;
      this.saving = true;
      api("/api/qvq/config", "POST", body).then(function (r) {
        self.saving = false;
        self.saved = (r && r.errors && Object.keys(r.errors).length)
          ? JSON.stringify(r.errors)
          : t("settings_saved");
        setTimeout(function () { self.saved = ""; }, 2000);
        this.load && this.load();
      }.bind(this));
    },
  },
  template: [
    '<n-card size="small" class="qvq-glass-card ss-card">',
    '  <div class="ss-head">',
    '    <div class="qvq-card-title">{{ title || group }}</div>',
    '    <button type="button" class="ss-toggle" @click="open = !open">{{ open ? "▾" : "▸" }}</button>',
    '  </div>',
    '  <div v-if="open" class="ss-body">',
    '    <div v-if="loading" class="qvq-loading"><i></i>{{ t("loading") }}</div>',
    '    <template v-else>',
    '      <div v-for="f in shown" :key="f.key" class="doc-row" :class="{ dirty: isDirty(f) }">',
    '        <div class="doc-label">',
    '          <div class="doc-row-title">{{ titleOf(f) }}</div>',
    '          <div class="doc-row-hint" v-if="hintOf(f)" :title="f.description">{{ hintOf(f) }}</div>',
    '        </div>',
    '        <div class="doc-ctl">',
    '          <schema-form :field="f" hide-head :model-value="draft[f.key]"',
    '                       @update:model-value="v => draft[f.key] = v"/>',
    '        </div>',
    '      </div>',
    '      <div class="ss-foot">',
    '        <n-button size="small" type="primary" :loading="saving" @click="save">{{ t("save") }}</n-button>',
    '        <span class="ss-saved" v-if="saved">{{ saved }}</span>',
    '      </div>',
    '    </template>',
    '  </div>',
    '</n-card>',
  ].join(""),
};
