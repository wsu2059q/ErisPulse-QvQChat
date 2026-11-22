/* 平台机器人：适配器/机器人概览 + 账户人格绑定 + 身份迁移 */
window.PagePlatforms = {
  name: "PagePlatforms",
  data() {
    return {
      loading: true,
      adapters: [],
      accounts: [],
      personas: [],
      bindings: {},
      suggestions: [],
      migOpen: false,
      mig: { source: "", target: "", mode: "alias" },
      migBusy: false,
      allKeys: [],
      showOffAdapters: false,
      showOffAccounts: false,
      mergeOpen: false,
      merge: { platform: "", from: "", to: "", mode: "merge" },
      mergeBusy: false,
      mergeResult: null,
    };
  },
  computed: {
    keyOptions() {
      return this.allKeys.map(function (k) { return { label: k, value: k }; });
    },
    accountOptions() {
      return this.accounts.map(function (a) { return { label: a.account, value: a.account }; });
    },
    adapterCount() {
      var n = 0;
      this.adapters.forEach(function (a) { n += (a.bots || []).length; });
      return n;
    },
    activeAdapters() {
      var self = this;
      return this.adapters.filter(function (a) { return !self.adapterOff(a); });
    },
    offAdaptersN() {
      return this.adapters.length - this.activeAdapters.length;
    },
    shownAdapters() {
      return this.showOffAdapters ? this.adapters : this.activeAdapters;
    },
    offPlatSet() {
      var set = {};
      var self = this;
      this.adapters.forEach(function (a) {
        if (self.adapterOff(a)) set[a.platform] = true;
      });
      return set;
    },
    activeAccounts() {
      var self = this;
      return this.accounts.filter(function (a) { return !self.accountOff(a); });
    },
    offAccountsN() {
      return this.accounts.length - this.activeAccounts.length;
    },
    shownAccounts() {
      return this.showOffAccounts ? this.accounts : this.activeAccounts;
    },
    personaOptions() {
      var opts = [{ label: t("cf_inherit"), value: "" }];
      this.personas.forEach(function (p) {
        opts.push({ label: p.name || p.id, value: p.id });
      });
      return opts;
    },
    personaName() {
      var map = {};
      this.personas.forEach(function (p) { map[p.id] = p.name || p.id; });
      return function (id) { return map[id] || id || t("cf_unset"); };
    },
    bindingGroups() {
      // 绑定全表按层级分组：@开头=账户级，:*结尾=平台级，其余=会话精确键
      var self = this;
      var defs = [
        { key: "session", label: t("bind_level_session"),
          match: function (k) { return k.charAt(0) !== "@" && k.slice(-2) !== ":*"; } },
        { key: "account", label: t("bind_level_account"), match: function (k) { return k.charAt(0) === "@"; } },
        { key: "platform", label: t("bind_level_platform"), match: function (k) { return k.slice(-2) === ":*"; } },
      ];
      var groups = [];
      defs.forEach(function (d) {
        var items = Object.keys(self.bindings || {}).filter(d.match).sort()
          .map(function (k) { return { key: k, persona: String(self.bindings[k] || "") }; });
        if (items.length) groups.push({ key: d.key, label: d.label, items: items });
      });
      return groups;
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    platState(a) {
      if (a.enabled === false || a.status === "disabled") return t("plat_disabled");
      if (a.status === "started") return t("plat_running");
      return t("plat_stopped");
    },
    adapterOff(a) {
      // 未启用或未在运行的适配器归入「已停用」，默认折叠
      return a.enabled === false || a.status !== "started";
    },
    accountOff(a) {
      // 账户的全部平台都停用时同样折叠
      if (a.enabled === false) return true;
      var self = this;
      var ps = a.platforms || [];
      return ps.length > 0 && ps.every(function (p) { return !!self.offPlatSet[p]; });
    },
    load() {
      var self = this;
      api("/api/qvq/sessions?limit=200").then(function (d) {
        d = d || {};
        self.adapters = (d.accounts && d.accounts.adapters) || [];
        self.accounts = (d.accounts && d.accounts.accounts) || [];
        self.suggestions = d.identity_suggestions || [];
        self.allKeys = ((d.sessions || []).map(function (x) { return x.chat_key; })).filter(Boolean);
        self.loading = false;
      });
      api("/api/qvq/personas").then(function (d) {
        self.personas = (d && d.personas) || [];
        self.bindings = (d && d.bindings) || {};
      });
    },
    bindPersona(a, value) {
      var self = this;
      if ((a.persona || "") === (value || "")) return;
      a.persona = value || "";
      api("/api/qvq/personas/bind", "POST", {
        chat_key: "@" + a.account,
        persona: value || null,
      }).then(function (r) {
        if (r && r.error) { a.persona = ""; return; }
        self.load();
      });
    },
    bindPlatform(a, value) {
      // 平台级绑定：platform:* 键，该适配器全部无更精确绑定的会话生效
      var self = this;
      if ((a.persona || "") === (value || "")) return;
      a.persona = value || "";
      api("/api/qvq/personas/bind", "POST", {
        chat_key: a.platform + ":*",
        persona: value || null,
      }).then(function (r) {
        if (r && r.error) { a.persona = ""; return; }
        self.load();
      });
    },
    bindKey(key, value) {
      // 绑定管理：改绑 / 解绑（persona null 即删除，后端留回收站撤销）
      var self = this;
      api("/api/qvq/personas/bind", "POST", { chat_key: key, persona: value || null })
        .then(function (r) {
          if (r && r.error) { self.toast = r.error; return; }
          self.load();
        });
    },
    unbindKey(key) {
      this.bindKey(key, null);
    },
    openMerge(a) {
      this.merge = { platform: (a.platforms && a.platforms[0]) || "", from: a.account, to: "", mode: "merge" };
      this.mergeResult = null;
      this.mergeOpen = true;
    },
    runMerge() {
      var self = this;
      if (!this.merge.platform || !this.merge.from || !this.merge.to || this.merge.from === this.merge.to) return;
      this.mergeBusy = true;
      api("/api/qvq/identity/merge_account", "POST", this.merge).then(function (r) {
        self.mergeBusy = false;
        self.mergeResult = r || { error: "network" };
        if (r && !r.error && r.ok) self.load();
      });
    },
    openMig(pair) {
      this.mig = {
        source: (pair && pair.source) || "",
        target: (pair && pair.target) || "",
        mode: "alias",
      };
      this.migOpen = true;
    },
    runMig() {
      var self = this;
      this.migBusy = true;
      api("/api/qvq/identity/set", "POST", this.mig).then(function (r) {
        self.migBusy = false;
        if (!r || r.ok === false) {
          self.toast = (r && r.error) || "failed";
          return;
        }
        self.migOpen = false;
        self.load();
      });
    },
    removeMap(source) {
      var self = this;
      api("/api/qvq/identity/remove", "POST", { source: source }).then(function () {
        self.load();
      });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_platforms") }}</div>',
    '    </div>',
    '  </div>',
  '  <div class="plat-grid">',
  '    <n-card v-for="a in shownAdapters" :key="a.platform" size="small" class="qvq-glass-card"',
  '            :class="{ \'is-off\': adapterOff(a) }">',
    '      <div class="plat-head">',
    '        <span class="plat-name">{{ a.platform }}</span>',
    '        <span class="plat-state" :class="a.status">{{ platState(a) }}</span>',
    '      </div>',
    '      <div class="plat-bots">',
    '        <span v-for="b in a.bots" :key="b.id" class="plat-bot"',
    '                :class="{ off: b.status !== \'online\' }">',
    '          <span class="live-dot" v-if="b.status === \'online\'"></span>',
    '          <span class="plat-bot-tx">',
    '            <b>{{ b.nickname || b.id }}</b>',
    '            <i v-if="b.nickname">{{ b.id }}</i>',
    '          </span>',
    '        </span>',
    '        <span v-if="!(a.bots || []).length" class="qvq-meta-line">{{ t("plat_none") }}</span>',
    '      </div>',
    '      <footer class="prov-foot">',
    '        <n-select size="tiny" :value="a.persona || \'\'" :options="personaOptions"',
    '                 :placeholder="t(\'plat_persona_platform\')" style="width:100%"',
    '                 @update:value="v => bindPlatform(a, v)"/>',
    '      </footer>',
    '    </n-card>',
  '  </div>',
  '  <button v-if="offAdaptersN" type="button" class="plat-off-toggle" @click="showOffAdapters = !showOffAdapters">',
  '    <span>{{ showOffAdapters ? t("plat_off_hide") : t("plat_disabled") + " (" + offAdaptersN + ")" }}</span>',
  '    <i :class="{ open: showOffAdapters }"></i>',
  '  </button>',
  '  <div v-if="!loading && !adapters.length" class="qvq-empty">{{ t("plat_none") }}</div>',
  '  <h3 class="plat-sec">{{ t("plat_accounts") }}</h3>',
  '  <div class="prov-grid">',
  '    <article v-for="a in shownAccounts" :key="a.account" class="prov-card"',
  '             :class="{ \'is-off\': accountOff(a) }">',
    '      <header class="prov-head">',
    '        <div class="prov-title">',
    '          <span class="prov-name">{{ a.account }}</span>',
    '          <span class="prov-id">{{ a.platforms.join(" / ") }}</span>',
    '        </div>',
    '      </header>',
        '      <div class="plat-meta">',
    '        <span>{{ a.sessions }} {{ t("plat_sessions") }}</span>',
    '      </div>',
      '      <footer class="prov-foot">',
        '        <n-select size="tiny" :value="a.persona || \'\'" :options="personaOptions"',
        '                 :placeholder="t(\'plat_persona\')" :title="t(\'bind_inherit_hint\')" style="width:100%"',
        '                 @update:value="v => bindPersona(a, v)"/>',
        '      </footer>',
    '    </article>',
  '    <div v-if="!loading && !accounts.length" class="qvq-empty" style="grid-column:1/-1">-</div>',
  '  </div>',
  '  <button v-if="offAccountsN" type="button" class="plat-off-toggle" @click="showOffAccounts = !showOffAccounts">',
  '    <span>{{ showOffAccounts ? t("plat_off_hide") : t("plat_disabled") + " (" + offAccountsN + ")" }}</span>',
  '    <i :class="{ open: showOffAccounts }"></i>',
  '  </button>',
  '  <h3 class="plat-sec">{{ t("bind_mgmt") }}</h3>',
  '  <n-card size="small" class="qvq-glass-card">',
  '    <div v-for="g in bindingGroups" :key="g.key" class="bind-group">',
  '      <div class="mention-title">{{ g.label }} <i class="bind-n">{{ g.items.length }}</i></div>',
  '      <div v-for="row in g.items" :key="row.key" class="bind-row">',
  '        <code class="bind-key" :title="row.key">{{ row.key }}</code>',
  '        <n-select size="tiny" :value="row.persona" :options="personaOptions" style="width:220px"',
  '                 @update:value="v => bindKey(row.key, v)"/>',
  '        <button type="button" class="prov-act bind-del" @click="unbindKey(row.key)">{{ t("bind_remove") }}</button>',
  '      </div>',
  '    </div>',
  '    <div v-if="!bindingGroups.length" class="qvq-empty">{{ t("bind_empty") }}</div>',
  '  </n-card>',
  '  <h3 class="plat-sec">{{ t("ident_title") }}</h3>',
    '  <n-card size="small" class="qvq-glass-card">',
    '    <div v-if="suggestions.length" class="plat-suggest">',
    '      <div class="mention-title">{{ t("ident_suggest") }}</div>',
    '      <div v-for="(pair, i) in suggestions" :key="i" class="plat-sug-row">',
    '        <code>{{ pair.source }}</code> → <code>{{ pair.target }}</code>',
    '        <button type="button" class="prov-act" @click="openMig(pair)">{{ t("ident_run") }}</button>',
    '      </div>',
    '    </div>',
    '    <div class="plat-ident-foot">',
    '      <span class="qvq-meta-line" v-if="!suggestions.length">{{ t("ident_empty") }}</span>',
    '      <button type="button" class="prov-act" @click="openMig({ source: \'\', target: \'\' })">{{ t("ident_manual") }}</button>',
    '      <button type="button" class="prov-act" @click="mergeOpen = true">{{ t("merge_account") }}</button>',
    '    </div>',
    '  </n-card>',
    '  <n-modal v-model:show="mergeOpen" preset="card" class="qvq-modal-card" style="max-width:440px"',
    '           :title="t(\'merge_account\')" :bordered="false">',
    '    <div class="prov-form">',
    '      <div class="qvq-meta-line">{{ t("merge_account_hint") }}</div>',
    '      <div class="prov-field">',
    '        <label>{{ t("identity_source") }}</label>',
    '        <n-select v-model:value="merge.from" tag filterable :options="accountOptions"/>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("identity_target") }}</label>',
    '        <n-select v-model:value="merge.to" tag filterable :options="accountOptions"/>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("identity_mode") }}</label>',
    '        <n-radio-group v-model:value="merge.mode">',
    '          <n-radio value="merge">{{ t("ident_merge") }}</n-radio>',
    '          <n-radio value="overwrite">{{ t("ident_overwrite") }}</n-radio>',
    '        </n-radio-group>',
    '      </div>',
    '      <div class="cf-error" v-if="mergeResult && mergeResult.error">{{ mergeResult.error }}</div>',
    '      <div class="qvq-meta-line" v-if="mergeResult && mergeResult.ok !== undefined">',
    '        {{ t("merge_done").replace("{n}", String(mergeResult.migrated)) }}',
    '      </div>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="mergeOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" :loading="mergeBusy" @click="runMerge">{{ t("ident_run") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '  <n-modal v-model:show="migOpen" preset="card" class="qvq-modal-card" style="max-width:440px"',
    '           :title="t(\'ident_title\')" :bordered="false">',
    '    <div class="prov-form">',
    '      <div class="prov-field">',
    '        <label>{{ t("identity_source") }}</label>',
    '        <n-select v-model:value="mig.source" tag filterable clearable',
    '                  :options="keyOptions" placeholder="onebot11:group:123"/>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("identity_target") }}</label>',
    '        <n-select v-model:value="mig.target" tag filterable clearable',
    '                  :options="keyOptions" placeholder="telegram:group:456"/>',
    '      </div>',
    '      <div class="prov-field">',
    '        <label>{{ t("identity_mode") }}</label>',
    '        <n-radio-group v-model:value="mig.mode">',
    '          <n-radio value="alias">{{ t("ident_alias") }}</n-radio>',
    '          <n-radio value="merge">{{ t("ident_merge") }}</n-radio>',
    '          <n-radio value="overwrite">{{ t("ident_overwrite") }}</n-radio>',
    '        </n-radio-group>',
    '      </div>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="migOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" :loading="migBusy" @click="runMig">',
    '          {{ t("ident_run") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '</div>',
  ].join(""),
};
