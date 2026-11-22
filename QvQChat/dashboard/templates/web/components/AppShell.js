/* 根组件：导航 / 路由 / 登录卡 */
window.AppShell = {
  name: "AppShell",
  data() {
    return { drawerOpen: false, quickOpen: false };
  },
  computed: {
    ICONS() {
      return {
        overview: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></svg>',
        chat: '<svg viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z"/></svg>',
        providers: '<svg viewBox="0 0 24 24"><path d="M12 2.5l9 5-9 5-9-5 9-5z"/><path d="M3 12l9 5 9-5"/><path d="M3 17l9 5 9-5"/></svg>',
        platforms: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/></svg>',
        personas: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8.5 14.2a4.6 4.6 0 0 0 7 0"/><path d="M9 9.6h.01M15 9.6h.01"/></svg>',
        config: '<svg viewBox="0 0 24 24"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/></svg>',
        plugins: '<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>',
        skills: '<svg viewBox="0 0 24 24"><path d="M13 2L4.5 13.5H11L9.5 22 19 9.5h-6.5L13 2z"/></svg>',
        tasks: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.4 2"/></svg>',
        memory: '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
        knowledge: '<svg viewBox="0 0 24 24"><path d="M4 19V6a2 2 0 0 1 2-2h13v13H6a2 2 0 0 0-2 2zm0 0a2 2 0 0 0 2 2h13"/><path d="M9 8h6"/></svg>',
        sessions: '<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
        audit: '<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        usage: '<svg viewBox="0 0 24 24"><path d="M13 3l7 7-9 9H4v-7l9-9z"/><path d="M16 5l3 3"/></svg>',
        storage: '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg>',
        tools: '<svg viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9l-3.8 3.8z"/></svg>',
        mcp: '<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>',
        orchestrate: '<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M6 8.5v1.5a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8.5M12 12.5v3"/></svg>',
        inbox: '<svg viewBox="0 0 24 24"><path d="M4 13l2.4-7.2A2 2 0 0 1 8.3 4.5h7.4a2 2 0 0 1 1.9 1.3L20 13"/><path d="M4 13v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/><path d="M4 13h4.5a3.5 3.5 0 0 0 7 0H20"/></svg>',
      };
    },
    st() { return QvQ.store; },
    loggedIn() { return this.st.loggedIn; },
    page() { return this.st.page; },
    theme() { return naiveTheme(); },
    locale() { return naiveLocale(false); },
    dateLocale() { return naiveLocale(true); },
    overrides() { return naiveOverrides(); },
    pageComp() {
      var map = {
        overview: "PageOverview", chat: "PageChat",
        providers: "PageProviders", platforms: "PagePlatforms", personas: "PagePersonas",
        config: "PageConfig", plugins: "PagePlugins", skills: "PageSkills", tasks: "PageTasks",
        memory: "PageMemory", knowledge: "PageKnowledge", sessions: "PageSessions",
        audit: "PageAudit", storage: "PageStorage", tools: "PageTools", mcp: "PageMcp",
        orchestrate: "PageOrchestrate", inbox: "PageInbox",
        usage: "PageUsage",
      };
      return map[this.page] || "PageOverview";
    },
    pageTitle() {
      // 移动端顶栏：当前页面名（与标签标题同一映射）
      var labels = {
        overview: t("nav_overview"), chat: t("nav_chat"),
        providers: t("nav_models"), platforms: t("nav_platforms"), personas: t("nav_personas"),
        config: t("nav_settings"), plugins: t("nav_plugins"), skills: t("nav_skills"),
        tasks: t("nav_tasks"), memory: t("nav_memory"), knowledge: t("nav_knowledge"),
        sessions: t("nav_sessions"), audit: t("nav_audit"), storage: t("nav_storage"),
        tools: t("nav_tools"), mcp: t("nav_mcp"), orchestrate: t("nav_orchestrate"),
        inbox: t("nav_inbox"), usage: t("nav_usage"),
      };
      return labels[this.page] || "QvQChat";
    },
    navGroups() {
      var self = this;
      var item = function (id, labelKey) {
        return { id: id, labelKey: labelKey, ico: self.ICONS[id] || "" };
      };
      return [
        {
          key: "core", label: t("nav_group_core"),
          items: [item("overview", "nav_overview"), item("chat", "nav_chat")],
        },
        {
          key: "access", label: t("nav_group_config"),
          items: [item("providers", "nav_models"), item("platforms", "nav_platforms"), item("personas", "nav_personas")],
        },
        {
          key: "data", label: t("nav_group_data"),
          items: [
            item("memory", "nav_memory"), item("knowledge", "nav_knowledge"),
            item("sessions", "nav_sessions"), item("audit", "nav_audit"),
            item("usage", "nav_usage"), item("inbox", "nav_inbox"), item("storage", "nav_storage"),
          ],
        },
        {
          key: "run", label: t("nav_group_run"),
          items: [item("tasks", "nav_tasks"), item("orchestrate", "nav_orchestrate")],
        },
        {
          key: "sys", label: t("nav_group_sys"),
          items: [
            item("tools", "nav_tools"), item("skills", "nav_skills"),
            item("mcp", "nav_mcp"), item("plugins", "nav_plugins"),
            item("config", "nav_settings"),
          ],
        },
      ];
    },
  },
  watch: {
    // 动态标签标题：浏览器标签页随当前页面/会话更新
    page: {
      immediate: true,
      handler(val) {
        var labels = {
          overview: t("nav_overview"), chat: t("nav_chat"),
          providers: t("nav_models"), platforms: t("nav_platforms"), personas: t("nav_personas"),
          config: t("nav_settings"), plugins: t("nav_plugins"), skills: t("nav_skills"),
          tasks: t("nav_tasks"), memory: t("nav_memory"), knowledge: t("nav_knowledge"),
          sessions: t("nav_sessions"), audit: t("nav_audit"), storage: t("nav_storage"),
          tools: t("nav_tools"), mcp: t("nav_mcp"), orchestrate: t("nav_orchestrate"),
          inbox: t("nav_inbox"), usage: t("nav_usage"),
        };
        document.title = "QvQChat · " + (labels[val] || "QvQChat");
      },
    },
  },
  mounted() {
    // 全局 Ctrl/Cmd+K 呼出命令面板；输入框/文本域聚焦时不劫持
    var self = this;
    this._quickKey = function (e) {
      if (!(e.ctrlKey || e.metaKey) || String(e.key || "").toLowerCase() !== "k") return;
      var el = e.target;
      var editable = el && (el.isContentEditable ||
        el.tagName === "INPUT" || el.tagName === "TEXTAREA");
      if (editable) return;
      e.preventDefault();
      self.quickOpen = !self.quickOpen;
    };
    window.addEventListener("keydown", this._quickKey, true);
  },
  beforeUnmount() {
    window.removeEventListener("keydown", this._quickKey, true);
  },
  methods: {
    go(key) {
      QvQ.store.page = key;
      this.drawerOpen = false;
    },
    login() { QvQ.store.loggedIn = true; },
    cycleTheme() {
      var order = ["follow", "light", "dark"];
      var cur = this.st.themeMode || "follow";
      var next = order[(order.indexOf(cur) + 1) % order.length];
      QvQ.setTheme(next);
      QvQ.toast(t("theme_title").replace("{mode}", t("theme_" + next)));
    },
    themeIcon() {
      var m = this.st.themeMode || "follow";
      if (m === "light") return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
      if (m === "dark") return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none"/></svg>';
    },
    themeTitle() {
      var m = this.st.themeMode || "follow";
      return t("theme_title").replace("{mode}", t("theme_" + m));
    },
  },
  template: [
    '<n-config-provider :theme="theme" :theme-overrides="overrides" :locale="locale"',
    '                    :date-locale="dateLocale" style="height:100%">',
    '  <n-message-provider>',
    '    <div v-if="!loggedIn" class="qvq-login-wrap">',
    '      <LoginPage @done="login"/>',
    '    </div>',
    '    <div v-else class="qvq-shell">',
    '      <header class="qvq-appbar">',
    '        <button type="button" class="qvq-appbar-burger" :aria-label="t(\'aria_menu\')" :title="t(\'aria_menu\')" @click="drawerOpen = true">',
    '          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">',
    '            <path d="M4 7h16M4 12h16M4 17h16"/></svg>',
    '        </button>',
    '        <span class="qvq-appbar-title">{{ pageTitle }}</span>',
    '        <button type="button" class="qvq-theme-btn" :aria-label="themeTitle()" :title="themeTitle()" @click="cycleTheme">',
    '          <span v-html="themeIcon()"></span>',
    '        </button>',
    '      </header>',
    '      <button type="button" class="qvq-burger" :aria-label="t(\'aria_menu\')" :title="t(\'aria_menu\')" @click="drawerOpen = true">',
    '        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">',
    '          <path d="M4 7h16M4 12h16M4 17h16"/></svg>',
    '      </button>',
    '      <transition name="qvq-fade">',
    '        <div v-if="drawerOpen" class="qvq-mask" @click="drawerOpen = false"></div>',
    '      </transition>',
    '      <transition name="qvq-slide">',
    '        <aside v-if="drawerOpen" class="qvq-nav qvq-nav-drawer">',
    '          <div class="qvq-nav-drawer-head">',
    '            <span class="qvq-logo">QvQ<span>Chat</span></span>',
    '            <button type="button" class="qvq-theme-btn" :aria-label="themeTitle()" :title="themeTitle()" @click="cycleTheme">',
    '              <span v-html="themeIcon()"></span>',
    '            </button>',
    '            <button type="button" class="qvq-drawer-x" :aria-label="t(\'aria_close\')" :title="t(\'aria_close\')" @click="drawerOpen = false">×</button>',
    '          </div>',
    '          <div class="qvq-nav-scroll">',
    '            <div v-for="g in navGroups" :key="g.key" class="qvq-nav-group">',
    '              <div class="qvq-nav-cat">{{ g.label }}</div>',
    '              <button v-for="it in g.items" :key="it.id" type="button"',
    '                      class="qvq-nav-item" :class="{ active: page === it.id }"',
    '                      @click="go(it.id)">',
    '                <span class="qvq-nav-ico" v-html="it.ico"></span>',
    '                <span class="qvq-nav-label">{{ t(it.labelKey) }}</span>',
    '              </button>',
    '            </div>',
    '          </div>',
    '        </aside>',
    '      </transition>',
    '      <aside class="qvq-nav qvq-nav-desk">',
    '        <div class="qvq-logo">QvQ<span>Chat</span></div>',
    '        <div class="qvq-nav-scroll">',
    '        <div v-for="g in navGroups" :key="g.key" class="qvq-nav-group">',
    '          <div class="qvq-nav-cat">{{ g.label }}</div>',
    '          <button v-for="it in g.items" :key="it.id" type="button"',
    '                  class="qvq-nav-item" :class="{ active: page === it.id }"',
    '                  @click="go(it.id)">',
    '            <span class="qvq-nav-ico" v-html="it.ico"></span>',
    '            <span class="qvq-nav-label">{{ t(it.labelKey) }}</span>',
    '          </button>',
    '        </div>',
    '        </div>',
    '        <div class="qvq-nav-foot">',
    '          <button type="button" class="qvq-theme-btn" :aria-label="themeTitle()" :title="themeTitle()" @click="cycleTheme">',
    '            <span v-html="themeIcon()"></span>',
    '          </button>',
    '        </div>',
    '      </aside>',
    '      <main class="qvq-main" :class="{ \'chat-mode\': page === \'chat\' }">',
    '        <transition name="qvq-page">',
    '          <component :is="pageComp" :key="page"/>',
    '        </transition>',
    '      </main>',
    '    </div>',
    '    <transition name="qvq-fade">',
    '      <quick-panel v-if="quickOpen" @close="quickOpen = false"/>',
    '    </transition>',
    '    <div class="chat-toast qvq-toast" v-if="st.toast" @click="st.toast = \'\'">{{ st.toast }}</div>',
    '  </n-message-provider>',
    '</n-config-provider>',
  ].join(""),
};
