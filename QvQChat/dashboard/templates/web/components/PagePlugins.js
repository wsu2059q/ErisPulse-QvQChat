/* 插件：生态模块卡 + 声明式配置抽屉（复用 SchemaForm） */
window.PagePlugins = {
  name: "PagePlugins",
  data() {
    return {
      modules: [],
      extensions: [],
      drawer: false,
      active: null,
      draft: {},
      busy: false,
      savedHint: "",
      extOpen: false,
      extActive: null,
    };
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      QvQ.swr(self, "plugins:settings", "/api/qvq/plugin_settings", function (d) {
        self.modules = (d && d.modules) || [];
      });
      QvQ.swr(self, "plugins:extensions", "/api/qvq/extensions", function (d) {
        self.extensions = (d && d.extensions) || [];
      });
    },
    open(mod) {
      this.active = mod;
      this.draft = JSON.parse(JSON.stringify(mod.values || {}));
      this.savedHint = "";
      this.drawer = true;
    },
    schemaFields(mod) {
      // resolve_config_schema.fields 是 {键: 定义} 映射；旧格式数组也兼容
      var schema = mod.schema || {};
      var raw = schema.fields || [];
      var list = Array.isArray(raw)
        ? raw.map(function (f) { return Object.assign({ key: f.key || f.name }, f); })
        : Object.keys(raw).map(function (k) {
            return Object.assign({ key: k }, typeof raw[k] === "object" && raw[k] ? raw[k] : {});
          });
      return list.map(function (f) {
        return {
          key: f.key || f.name,
          description: typeof f.description === "string" ? f.description : "",
          widget: f.widget || f.type || "text",
          options: f.options || null,
          min: f.min, max: f.max, step: f.step,
          placeholder: f.placeholder || "",
          secret: !!f.secret,
          dangerous: false,
          value: (mod.values || {})[f.key || f.name],
        };
      });
    },
    fieldCount(mod) {
      return this.schemaFields(mod).length;
    },
    openExt(e) {
      this.extActive = e || null;
      this.extOpen = !!e;
    },
    extDetailGroups(e) {
      var d = (e && e.details) || {};
      var groups = [];
      if ((d.schemas || []).length) {
        groups.push({ label: t("plugin_ext_schemas"), items: d.schemas.map(function (s) { return { title: s }; }) });
      }
      if ((d.skills || []).length) {
        groups.push({ label: t("caps_skills"), items: d.skills.map(function (s) { return { title: s.name, sub: s.description }; }) });
      }
      if ((d.knowledge || []).length) {
        groups.push({ label: t("nav_knowledge"), items: d.knowledge.map(function (k) { return { title: k.title, sub: (k.triggers || []).join(" / ") }; }) });
      }
      if ((d.prompts || []).length) {
        groups.push({ label: "Prompts", items: d.prompts.map(function (x) { return { title: x.text, sub: "priority " + x.priority }; }) });
      }
      if ((d.personas || []).length) {
        groups.push({ label: t("nav_personas"), items: d.personas.map(function (x) { return { title: x }; }) });
      }
      return groups;
    },
    save() {
      var self = this;
      this.busy = true;
      api("/api/qvq/plugin_settings/save", "POST", {
        module: this.active.module,
        values: this.draft,
      }).then(function (r) {
        self.busy = false;
        if (r && r.error) return;
        self.savedHint = t("settings_saved");
        setTimeout(function () { self.savedHint = ""; }, 2000);
        self.load();
      });
    },
    extName(e) {
      return typeof e === "string" ? e : String(e.module || e.name || "");
    },
    extParts(e) {
      // 生态扩展贡献计数（拆成独立徽标渲染，不再用 · 串成一长条）
      if (typeof e === "string") return [];
      var parts = [];
      if (Number(e.schemas)) parts.push(e.schemas + " schema");
      if (Number(e.skills)) parts.push(e.skills + " " + t("caps_skills"));
      if (Number(e.knowledge)) parts.push(e.knowledge + " " + t("nav_knowledge"));
      if (Number(e.personas)) parts.push(e.personas + " " + t("nav_personas"));
      if (Number(e.prompts)) parts.push(e.prompts + " prompt");
      return parts;
    },
    extLabel(e) {
      // 抽屉标题等纯文本场合仍用单行摘要
      var parts = this.extParts(e);
      return this.extName(e) + (parts.length ? " · " + parts.join(" · ") : "");
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_plugins") }}</div>',
    '      <div class="qvq-page-sub">{{ modules.length }} {{ t("nav_plugins") }}</div>',
    '    </div>',
    '  </div>',
    '  <div class="prov-grid">',
    '    <article v-for="m in modules" :key="m.module" class="prov-card">',
    '      <header class="prov-head">',
    '        <div class="prov-title">',
    '          <span class="prov-name">{{ m.title }}</span>',
    '          <span class="prov-id">{{ m.module }}</span>',
    '        </div>',
    '      </header>',
    '      <div class="plat-meta">',
    '        <span>{{ fieldCount(m) }} {{ t("cf_group_config") }}</span>',
    '      </div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click="open(m)">{{ t("settings") }}</button>',
    '        </span>',
    '      </footer>',
    '    </article>',
    '  </div>',
    '  <div v-if="!modules.length" class="qvq-empty">-</div>',
  '  <h3 class="plat-sec">{{ t("stat_extensions") }}</h3>',
  '  <div class="ext-row">',
  '    <button v-for="(e, i) in extensions" :key="i" type="button" class="ext-chip"',
  '            :title="extLabel(e)" @click="openExt(e)">',
  '      <b class="nm">{{ extName(e) }}</b>',
  '      <span v-for="(p, j) in extParts(e)" :key="j" class="cnt">{{ p }}</span>',
  '      <i class="go">›</i>',
  '    </button>',
  '    <span v-if="!extensions.length" class="qvq-meta-line">-</span>',
  '  </div>',
    '  <n-drawer v-model:show="drawer" :width="520" placement="right">',
    '    <n-drawer-content :title="active ? active.title : \'\'" closable>',
    '      <div class="qvq-empty" v-if="active && !fieldCount(active)">{{ t("plugin_no_settings") }}</div>',
    '      <div class="prov-form" v-if="active && fieldCount(active)">',
    '        <template v-for="f in schemaFields(active)" :key="f.key">',
    '          <schema-form :field="f" :model-value="draft[f.key]"',
    '                       @update:model-value="v => draft[f.key] = v"/>',
    '        </template>',
    '      </div>',
    '      <template #footer>',
    '        <div class="qvq-modal-foot">',
    '          <span class="qvq-cfg-saved" v-if="savedHint">{{ savedHint }}</span>',
    '          <n-button size="small" :loading="busy" type="primary" @click="save">{{ t("save") }}</n-button>',
    '        </div>',
    '      </template>',
    '    </n-drawer-content>',
    '  </n-drawer>',
    '  <n-drawer v-model:show="extOpen" :width="420" placement="right">',
    '    <n-drawer-content :title="extActive ? extLabel(extActive) : \'\'" closable>',
    '      <div class="prov-form" v-if="extActive">',
    '        <template v-for="g in extDetailGroups(extActive)">',
    '          <div class="prov-field" :key="g.label">',
    '            <label>{{ g.label }}</label>',
    '            <div class="ext-detail-list">',
    '              <div v-for="(item, i) in g.items" :key="i" class="ext-detail-item">',
    '                <b>{{ item.title }}</b>',
    '                <span class="qvq-meta-line" v-if="item.sub">{{ item.sub }}</span>',
    '              </div>',
    '            </div>',
    '          </div>',
    '        </template>',
    '        <div class="qvq-empty" v-if="!extDetailGroups(extActive).length">-</div>',
    '      </div>',
    '    </n-drawer-content>',
    '  </n-drawer>',
    '</div>',
  ].join(""),
};
