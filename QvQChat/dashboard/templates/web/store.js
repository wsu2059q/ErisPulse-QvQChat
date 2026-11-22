/* 全局命名空间与响应式状态 */
window.QvQ = window.QvQ || {};
const QvQ = window.QvQ;
QvQ.store = null;

QvQ.store = Vue.reactive({
  lang: detectLang(),
  loggedIn: false,
  page: "overview",
  drawerOpen: false,
  busy: false,
  status: {},
  toast: "",
  themeMode: (function () {
    try { return localStorage.getItem("qvq_theme") || "follow"; } catch (e) { return "follow"; }
  })(),
});

QvQ.setLang = function (lang) {
  QvQ.store.lang = lang;
  try { localStorage.setItem("qvq_lang", lang); } catch (e) {}
};

QvQ.setTheme = function (mode) {
  QvQ.store.themeMode = mode;
  try { localStorage.setItem("qvq_theme", mode); } catch (e) {}
  if (window.QvQ.syncThemeExternal) window.QvQ.syncThemeExternal();
};

/* hash 路由：#/page 与 store.page 双向同步（刷新保位 / 深链 / 浏览器后退） */
(function () {
  var PAGES = ("overview chat providers platforms personas config plugins skills tasks "
    + "memory knowledge sessions audit storage tools mcp orchestrate inbox usage").split(" ");
  var fromHash = function () {
    var h = (location.hash || "").replace(/^#\/?/, "").split(/[/?&]/)[0];
    return PAGES.indexOf(h) >= 0 ? h : "";
  };
  var apply = function () {
    var p = fromHash();
    if (p && QvQ.store.page !== p) QvQ.store.page = p;
  };
  apply();
  window.addEventListener("hashchange", apply);
  Vue.watch(function () { return QvQ.store.page; }, function (val) {
    if (PAGES.indexOf(val) < 0) return;
    if (fromHash() !== val) location.hash = "#/" + val;
  });
})();

/* 全局轻提示：任意页面 QvQ.toast("...")，4s 自动消失 */
QvQ.toastTimer = null;
QvQ.toast = function (msg) {
  QvQ.store.toast = String(msg || "");
  if (QvQ.toastTimer) clearTimeout(QvQ.toastTimer);
  QvQ.toastTimer = setTimeout(function () { QvQ.store.toast = ""; }, 4000);
};
QvQ.fill = function (key, vars) {
  var s = t(key);
  Object.keys(vars || {}).forEach(function (k) { s = s.replace("{" + k + "}", vars[k]); });
  return s;
};


QvQ.fieldTitle = function (text, key) {
  var raw = String(text || "").trim();
  if (!raw) return key;
  var cuts = [/[:：]/, /[。；;]/, /[，,]/];
  for (var i = 0; i < cuts.length; i++) {
    var idx = raw.search(cuts[i]);
    if (idx > 0 && idx <= 24) return raw.slice(0, idx);
  }
  return raw.length <= 24 ? raw : raw.slice(0, 24) + "…";
};

QvQ.fieldDesc = function (text, key) {
  var raw = String(text || "").trim();
  if (!raw) return "";
  var title = QvQ.fieldTitle(text, key);
  if (title === raw) return "";
  var at = raw.indexOf(title);
  return at < 0 ? raw : raw.slice(at + title.length).replace(/^[，,。；;：:\s]+/, "");
};

QvQ.store.pendingGroup = "";
