/* MCP：服务器列表 / 连接状态 / 增删改连断 */
window.PageMcp = {
  name: "PageMcp",
  data() {
    return {
      servers: [],
      clients: [],
      drawer: false,
      isNew: true,
      form: { name: "", transport: "stdio", command: "", url: "", env: "", enabled: true },
      formErr: "",
      busy: false,
      toast: "",
    };
  },
  computed: {
    clientByName() {
      var map = {};
      this.clients.forEach(function (c) { map[c.name] = c; });
      return map;
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      return api("/api/qvq/mcp").then(function (d) {
        self.servers = (d && d.servers) || [];
        self.clients = (d && d.clients) || [];
      });
    },
    add() {
      this.isNew = true;
      this.form = { name: "", transport: "stdio", command: "", url: "", env: "", enabled: true };
      this.formErr = "";
      this.drawer = true;
    },
    edit(sv) {
      this.isNew = false;
      this.form = {
        name: sv.name || "",
        transport: sv.transport || "stdio",
        command: sv.command || "",
        url: sv.url || "",
        env: sv.env ? JSON.stringify(sv.env, null, 2) : "",
        enabled: sv.enabled !== false,
      };
      this.formErr = "";
      this.drawer = true;
    },
    save() {
      var self = this;
      this.busy = true;
      var body = {
        name: this.form.name,
        transport: this.form.transport,
        command: this.form.command,
        url: this.form.url,
        enabled: this.form.enabled,
      };
      try {
        body.env = this.form.env.trim() ? JSON.parse(this.form.env) : {};
      } catch (e) {
        this.formErr = "env JSON: " + e.message;
        this.busy = false;
        return;
      }
      api("/api/qvq/mcp/save", "POST", body).then(function (r) {
        self.busy = false;
        if (r && r.error) {
          self.formErr = r.error;
          return;
        }
        self.drawer = false;
        self.load();
      });
    },
    connect(name) {
      var self = this;
      api("/api/qvq/mcp/connect", "POST", { name: name }).then(function (r) {
        self.toast = r && r.ok ? t("mcp_status_on") : (r && r.error) || "failed";
        self.load();
      });
    },
    disconnect(name) {
      var self = this;
      api("/api/qvq/mcp/disconnect", "POST", { name: name }).then(function () {
        self.load();
      });
    },
    del(sv) {
      var self = this;
      api("/api/qvq/mcp/delete", "POST", { name: sv.name }).then(function () { self.load(); });
    },
    stateOf(sv) {
      var c = this.clientByName[sv.name];
      return c && c.status === "connected" ? "on" : "off";
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_mcp") }}</div>',
    '      <div class="qvq-page-sub">{{ servers.length }} {{ t("mcp_servers") }}</div>',
    '    </div>',
    '    <n-button size="small" type="primary" @click="add">{{ t("add_title") }}</n-button>',
    '  </div>',
    '  <div class="prov-grid">',
    '    <article v-for="sv in servers" :key="sv.name" class="prov-card">',
    '      <header class="prov-head">',
    '        <div class="prov-title">',
    '          <span class="prov-name">{{ sv.name }}</span>',
    '          <span class="prov-id">{{ sv.transport }}</span>',
    '        </div>',
    '        <span class="plat-state" :class="stateOf(sv) === \'on\' ? \'started\' : \'disabled\'">',
    '          {{ stateOf(sv) === "on" ? t("mcp_status_on") : t("mcp_status_off") }}</span>',
    '      </header>',
    '      <div class="prov-url">{{ sv.command || sv.url }}</div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-acts">',
    '          <button v-if="stateOf(sv) !== \'on\'" type="button" class="prov-act" @click="connect(sv.name)">{{ t("mcp_connect") }}</button>',
    '          <button v-else type="button" class="prov-act" @click="disconnect(sv.name)">{{ t("mcp_disconnect") }}</button>',
    '          <button type="button" class="prov-act" @click="edit(sv)">{{ t("edit") }}</button>',
    '          <button type="button" class="prov-act danger" @click="del(sv)">{{ t("chat_delete") }}</button>',
    '        </span>',
    '      </footer>',
    '    </article>',
    '  </div>',
    '  <button v-if="!servers.length" type="button" class="qvq-empty mcp-empty-cta" @click="add">{{ t("mcp_none") }}</button>',
    '  <n-drawer v-model:show="drawer" :width="440" placement="right">',
    '    <n-drawer-content :title="isNew ? t(\'add_title\') : t(\'edit\')" closable>',
    '      <div class="prov-form">',
    '        <div class="prov-field">',
    '          <label>{{ t("models_name") }}</label>',
    '          <n-input v-model:value="form.name" :disabled="!isNew"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>{{ t("mcp_transport") }}</label>',
    '          <n-select v-model:value="form.transport" :options="[{ label: \'stdio\', value: \'stdio\' }, { label: \'sse\', value: \'sse\' }, { label: \'http\', value: \'http\' }]"/>',
    '        </div>',
    '        <div class="prov-field" v-if="form.transport === \'stdio\'">',
    '          <label>command</label>',
    '          <n-input v-model:value="form.command" placeholder="npx -y @modelcontextprotocol/server-xxx"/>',
    '        </div>',
    '        <div class="prov-field" v-else>',
    '          <label>URL</label>',
    '          <n-input v-model:value="form.url" placeholder="http://127.0.0.1:9000/sse"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>env (JSON)</label>',
    '          <n-input v-model:value="form.env" type="textarea" :rows="4" class="cf-mono"/>',
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
    '  <transition name="doc-pop">',
    '    <div class="chat-toast" v-if="toast" @click="toast = \'\'">{{ toast }}</div>',
    '  </transition>',
    '</div>',
  ].join(""),
};
