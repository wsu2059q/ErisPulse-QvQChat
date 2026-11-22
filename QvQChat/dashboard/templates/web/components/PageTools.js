/* 工具：来源分组 / 禁用开关 / 危险标记 / 搜索 */
window.PageTools = {
  name: "PageTools",
  data() {
    return { q: "", tools: [], disabled: [], busy: false, expanded: {} };
  },
  computed: {
    groups() {
      var q = this.q.trim().toLowerCase();
      var map = {};
      this.tools.forEach(function (x) {
        if (q && (x.name + " " + x.label + " " + x.description).toLowerCase().indexOf(q) < 0) return;
        (map[x.origin] = map[x.origin] || []).push(x);
      });
      return Object.keys(map).sort().map(function (origin) {
        return { origin: origin, items: map[origin] };
      });
    },
    disabledCount() { return this.disabled.length; },
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      return QvQ.swr(self, "tools", "/api/qvq/tools", function (d) {
        self.tools = (d && d.tools) || [];
        self.disabled = (d && d.disabled) || [];
      });
    },
    isOff(name) {
      var self = this;
      return this.disabled.some(function (d) { return d === name || name.indexOf(d) === 0; });
    },
    toggle(tool, on) {
      var self = this;
      var next = this.disabled.filter(function (d) { return d !== tool.name; });
      if (!on) next.push(tool.name);
      this.busy = true;
      api("/api/qvq/config", "POST", { disabled_tools: next }).then(function (r) {
        self.busy = false;
        if (r && r.errors) return;
        self.disabled = next;
      });
    },
    refresh() {
      var self = this;
      this.busy = true;
      api("/api/qvq/tools/refresh", "POST", {}).then(function () {
        self.busy = false;
        self.load();
      });
    },
    toggleExpand(name) {
      this.expanded[name] = !this.expanded[name];
    },
    paramRows(x) {
      var schema = x.parameters || {};
      var props = schema.properties || {};
      var req = schema.required || [];
      return Object.keys(props).map(function (k) {
        var p = props[k] || {};
        var type = Array.isArray(p.type) ? p.type.join("|") : (p.type || "any");
        return { name: k, type: type, desc: p.description || "", req: req.indexOf(k) >= 0 };
      });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_tools") }}</div>',
    '      <div class="qvq-page-sub">{{ tools.length }} {{ t("stat_tools") }} · {{ disabledCount }} {{ t("tools_disabled_n") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-input v-model:value="q" size="small" clearable :placeholder="t(\'audit_filter\')"',
    '               style="width:200px"/>',
    '      <n-button size="small" :loading="busy" @click="refresh">{{ t("tools_refresh") }}</n-button>',
    '    </div>',
    '  </div>',
    '  <section v-for="g in groups" :key="g.origin" class="tools-sec">',
    '    <h2 class="doc-sec-title">',
    '      <span>{{ g.origin }}</span>',
    '      <span class="cnt">{{ g.items.length }}</span>',
    '      <button v-if="g.origin === \'mcp\'" type="button" class="qvq-link"',
    '              @click="QvQ.store.page = \'mcp\'">{{ t("mcp_manage") }}</button>',
    '    </h2>',
    '    <div v-for="x in g.items" :key="x.name" class="tool-row tool-expandable"',
    '         :class="{ open: expanded[x.name] }" @click="toggleExpand(x.name)">',
    '      <div class="tool-main">',
    '        <div class="tool-name">{{ x.label || x.name }}',
    '          <code>{{ x.name }}</code>',
    '          <span v-if="x.danger" class="cf-badge">{{ t("settings_dangerous") }}</span>',
    '          <span class="tool-expand-ico">▸</span>',
    '        </div>',
    '        <div class="tool-desc">{{ x.description }}</div>',
    '        <div class="tool-params" v-if="expanded[x.name]" @click.stop>',
    '          <div class="qvq-meta-line" v-if="x.access">{{ t("tools_access") }}: {{ x.access }}</div>',
    '          <div v-for="pr in paramRows(x)" :key="pr.name" class="tool-param-row">',
    '            <code>{{ pr.name }}</code><i v-if="pr.req" class="tool-param-req">*</i>',
    '            <span class="tool-param-type">{{ pr.type }}</span>',
    '            <span class="qvq-meta-line" v-if="pr.desc">{{ pr.desc }}</span>',
    '          </div>',
    '          <div class="qvq-empty" v-if="!paramRows(x).length">{{ t("tools_no_params") }}</div>',
    '        </div>',
    '      </div>',
    '      <n-switch size="small" :value="!isOff(x.name)" @update:value="toggle(x, $event)"/>',
    '    </div>',
    '  </section>',
    '  <div v-if="!tools.length" class="qvq-empty">-</div>',
    '</div>',
  ].join(""),
};
