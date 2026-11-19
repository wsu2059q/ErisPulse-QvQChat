/* 入口：注册组件 / 挂载 / 鉴权启动 */
(function () {
  var app = Vue.createApp(AppShell);
  app.use(window.naive || window.NaiveUi);
  app.config.globalProperties.t = t;
  app.config.globalProperties.esc = esc;
  app.config.globalProperties.mdRender = mdRender;
  var names = [
    "LoginPage", "PageOverview", "PageChat", "PageProviders", "PagePlatforms",
    "PagePersonas", "PageConfig", "PagePlugins", "PageSkills", "PageTasks",
    "PageMemory", "PageKnowledge", "PageSessions", "PageAudit", "PageStorage",
    "PageTools", "PageMcp", "PageOrchestrate", "BackupPanel", "PageInbox",
    "PageUsage", "SchemaForm", "QuickPanel", "Mascot",
  ];
  names.forEach(function (name) {
    if (window[name]) app.component(name, window[name]);
  });
  app.mount("#app");

  resolveToken().then(function (token) {
    if (token) {
      activeToken = token;
      QvQ.store.loggedIn = true;
    }
  });
})();
