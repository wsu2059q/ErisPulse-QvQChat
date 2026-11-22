/* 主题桥：镜像外壳 data-theme/data-oled 与 accent；壁纸镜像或兜底渐变 */
(function () {
  var parentDoc = null;
  try {
    parentDoc = window.parent && window.parent !== window ? window.parent.document : null;
  } catch (e) { parentDoc = null; }

  function syncAttrs() {
    var mode = "";
    try { mode = (window.QvQ && QvQ.store && QvQ.store.themeMode) || ""; } catch (e) {}
    if (mode === "light" || mode === "dark") {
      document.documentElement.setAttribute("data-theme", mode);
      document.documentElement.removeAttribute("data-oled");
      return;
    }
    if (!parentDoc) return;
    ["data-theme", "data-oled"].forEach(function (name) {
      var value = parentDoc.documentElement.getAttribute(name);
      if (value === null || value === "auto") {
        document.documentElement.removeAttribute(name);
      } else {
        document.documentElement.setAttribute(name, value);
      }
    });
  }

  function syncBackdrop() {
    var layer = document.getElementById("qvq-bg-layer");
    if (!layer) return;
    var inline = "";
    var shellBgImage = false;
    try {
      inline = parentDoc && parentDoc.body ? parentDoc.body.style.backgroundImage || "" : "";
      shellBgImage = parentDoc ? parentDoc.documentElement.classList.contains("bg-image") : false;
    } catch (e) {}
    if (inline && shellBgImage) {
      layer.classList.remove("qvq-bg-fallback");
      var light = document.documentElement.getAttribute("data-theme") === "light";
      var mask = light
        ? "linear-gradient(rgba(246,247,249,0.82), rgba(246,247,249,0.82))"
        : "linear-gradient(rgba(13,15,19,0.72), rgba(13,15,19,0.72))";
      layer.style.backgroundImage = mask + ", " + inline;
    } else {
      layer.classList.add("qvq-bg-fallback");
      layer.style.backgroundImage = "";
    }
    document.documentElement.classList.add("qvq-bg-image");
  }

  syncAttrs();
  syncBackdrop();
  if (parentDoc) {
    try {
      new MutationObserver(syncAttrs).observe(parentDoc.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-oled"] });
      new MutationObserver(syncBackdrop).observe(parentDoc.body, { attributes: true, attributeFilter: ["style"] });
    } catch (e) {}
  }
  window.QvQ.syncThemeExternal = syncAttrs;
})();

function naiveTheme() {
  var mode = "";
  try { mode = (window.QvQ && QvQ.store && QvQ.store.themeMode) || ""; } catch (e) {}
  var ui = window.naive || window.NaiveUi;
  if (mode === "dark") return ui ? ui.darkTheme : null;
  if (mode === "light") return null;
  var dark = document.documentElement.getAttribute("data-theme") === "dark"
    || (!document.documentElement.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
  return dark && ui ? ui.darkTheme : null;
}

function naiveOverrides() {
  var accent = getComputedStyle(document.documentElement).getPropertyValue("--qvq-accent") || "#3aa5dc";
  return {
    common: {
      primaryColor: accent,
      primaryColorHover: accent,
      primaryColorPressed: accent,
      bodyColor: "transparent",
      cardColor: "color-mix(in srgb, var(--qvq-surface, #1c2027) 82%, transparent)",
      modalColor: "var(--qvq-surface, #1c2027)",
      popoverColor: "var(--qvq-solid, #1c2027)",
      borderColor: "var(--qvq-bd)",
      borderRadius: "10px",
      fontWeightStrong: "600",
    },
    Slider: {
      fillColor: accent,
      fillColorHover: accent,
      handleColor: accent,
    },
    Switch: {
      railColorActive: accent,
      loadingColor: accent,
    },
    Checkbox: {
      colorChecked: accent,
      borderChecked: "1px solid " + accent,
    },
  };
}

function naiveLocale(date) {
  var ui = window.naive || window.NaiveUi;
  if (!ui) return null;
  var map = {
    "zh-CN": "zhCN", "zh-TW": "zhTW", "en": "enUS",
    "ja": "jaJP", "ru": "ruRU",
  };
  var lang = (window.QvQ && QvQ.store && QvQ.store.lang) || "zh-CN";
  var key = map[lang] || "zhCN";
  return date ? ui["date" + key] || null : ui[key] || null;
}
