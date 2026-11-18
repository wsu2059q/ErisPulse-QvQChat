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
});

QvQ.setLang = function (lang) {
  QvQ.store.lang = lang;
  try { localStorage.setItem("qvq_lang", lang); } catch (e) {}
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
