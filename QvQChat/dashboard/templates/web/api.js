/* API 封装：Bearer 鉴权 / 401 转登录 / 超时 */
var API_TIMEOUT_MS = 25000;
var activeToken = "";
var urlToken = new URLSearchParams(location.search).get("token") || "";

function getToken() {
  if (activeToken) return activeToken;
  try {
    return localStorage.getItem("__ep_tk__") || urlToken || localStorage.getItem("qvq_token") || "";
  } catch (e) {
    return urlToken;
  }
}

function api(path, method, body) {
  var headers = { "Content-Type": "application/json" };
  var token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
  var timer = ctrl ? setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, API_TIMEOUT_MS) : null;
  var opts = { method: method || "GET", headers: headers, body: body ? JSON.stringify(body) : undefined };
  if (ctrl) opts.signal = ctrl.signal;
  return fetch("/QvQChat" + path, opts).then(function (resp) {
    if (timer) clearTimeout(timer);
    return resp.json().catch(function () { return {}; }).then(function (data) {
      data = data && typeof data === "object" ? data : {};
      data.__http = resp.status;
      if (resp.status === 401) {
        activeToken = "";
        try { localStorage.removeItem("qvq_token"); } catch (e) {}
        QvQ.store.loggedIn = false;
      }
      return data;
    });
  });
}

function apiBlob(path) {
  var headers = {};
  var token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  return fetch("/QvQChat" + path, { headers: headers });
}

function authWith(token) {
  var headers = {};
  if (token) headers["Authorization"] = "Bearer " + token;
  return fetch("/QvQChat/api/qvq/auth", { headers: headers }).then(function (r) {
    return r.status === 200;
  }).catch(function () { return false; });
}

function stripUrlToken() {
  if (!window.history || !window.history.replaceState) return;
  try {
    var clean = window.location.search.replace(/([?&])token=[^&]*&?/i, "$1").replace(/[?&]$/, "");
    window.history.replaceState(null, "", window.location.pathname + clean + window.location.hash);
  } catch (e) {}
}

function resolveToken() {
  var candidates = [];
  try {
    var ep = localStorage.getItem("__ep_tk__");
    if (ep) candidates.push(ep);
  } catch (e) {}
  if (urlToken) candidates.push(urlToken);
  try {
    var qt = localStorage.getItem("qvq_token");
    if (qt) candidates.push(qt);
  } catch (e) {}
  var chain = Promise.resolve(false);
  var chosen = "";
  candidates.forEach(function (tk) {
    chain = chain.then(function (ok) {
      if (ok) return true;
      chosen = tk;
      return authWith(tk);
    });
  });
  return chain.then(function (ok) {
    if (ok && chosen) {
      try { localStorage.setItem("qvq_token", chosen); } catch (e) {}
      stripUrlToken();
    }
    return ok ? chosen : "";
  });
}


/* SWR：会话内缓存。旧数据先上屏（loading 不出现），后台请求完成后覆盖并写回缓存。 */
QvQ.pageCache = QvQ.pageCache || {};
QvQ.swr = function (self, key, url, apply) {
  var cached = QvQ.pageCache[key];
  if (cached && typeof apply === "function") apply(cached, true);
  if ("loading" in self) self.loading = !cached;
  return api(url).then(function (d) {
    if ("loading" in self) self.loading = false;
    if (d && d.__http !== undefined && d.__http >= 400) return d;
    QvQ.pageCache[key] = d;
    if (typeof apply === "function") apply(d, false);
    return d;
  }).catch(function () {
    if ("loading" in self) self.loading = false;
  });
};

/* 复制：HTTP（非安全上下文）没有 navigator.clipboard，降级 execCommand */
QvQ.copy = function (text, done) {
  var s = String(text == null ? "" : text);
  if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
    navigator.clipboard.writeText(s).then(function () { if (done) done(true); }, function () {
      QvQ._copyFallback(s, done);
    });
    return;
  }
  QvQ._copyFallback(s, done);
};
QvQ._copyFallback = function (s, done) {
  try {
    var ta = document.createElement("textarea");
    ta.value = s;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, s.length);
    var ok = document.execCommand("copy");
    document.body.removeChild(ta);
    if (done) done(!!ok);
  } catch (e) {
    if (done) done(false);
  }
};

/* 内置定时任务友好名（qvq:profile_consolidate / qvq:storage_maintain） */
QvQ.taskLabel = function (tk) {
  var id = String((tk && (tk.id || tk.name)) || "");
  if (id.indexOf("qvq:profile_consolidate") === 0) return t("task_profile");
  if (id.indexOf("qvq:storage_maintain") === 0) return t("task_maintain");
  return (tk && (tk.name || tk.id)) || id;
};
