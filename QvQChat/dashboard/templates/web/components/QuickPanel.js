/* 全局命令面板（Ctrl/Cmd+K）：页面 / 会话 / 知识 / 技能 / 动作 五组结果，键盘流优先。
   样式不进 app.css（本次只动两个文件），由此文件在加载时注入一次 <style>。
   新文案键（未入 i18n.js，页面用 t(key) 即可）：
   i18n: quick_open=快速跳转
   i18n: quick_placeholder=搜索页面、会话、知识与技能…
   i18n: quick_group_pages=页面
   i18n: quick_group_sessions=会话
   i18n: quick_group_knowledge=知识
   i18n: quick_group_skills=技能
   i18n: quick_group_actions=动作
   i18n: quick_act_new_chat=新建试聊
   i18n: quick_act_theme=切换主题
   i18n: quick_act_lang=切换语言
   i18n: quick_hint=↑↓ 选择 · Enter 打开 · Esc 关闭
   i18n: quick_no_result=没有匹配的结果
   i18n: quick_turns={n} 轮
*/
(function () {
  if (document.getElementById("qvq-quick-style")) return;
  var css = [
    ".qvq-quick{position:fixed;inset:0;z-index:90;display:flex;align-items:flex-start;justify-content:center;",
    "padding:12vh 16px 16px;background:rgba(6,8,12,.45)}",
    ".qvq-quick-card{width:100%;max-width:560px;max-height:68vh;display:flex;flex-direction:column;",
    "background:color-mix(in srgb,var(--qvq-surface) 88%,transparent);border:1px solid var(--qvq-bd);",
    "border-radius:var(--qvq-radius-xl);box-shadow:var(--qvq-shadow);overflow:hidden}",
    ".qvq-quick-head{display:flex;align-items:center;gap:10px;padding:13px 16px;border-bottom:1px solid var(--qvq-bd);flex:none}",
    ".qvq-quick-head-ico{width:17px;height:17px;flex:none;color:var(--qvq-tx-t);display:inline-flex}",
    ".qvq-quick-ico svg{width:100%;height:100%;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}",
    ".qvq-quick-input{flex:1;min-width:0;border:none;outline:none;background:transparent;color:var(--qvq-tx);",
    "font-size:15px;font-family:var(--qvq-font)}",
    ".qvq-quick-input::placeholder{color:var(--qvq-tx-t)}",
    ".qvq-quick-list{flex:1;min-height:0;overflow-y:auto;padding:6px}",
    ".qvq-quick-cat{font-size:11px;font-weight:600;letter-spacing:.4px;text-transform:uppercase;",
    "color:var(--qvq-tx-t);padding:10px 10px 4px}",
    ".qvq-quick-row{display:flex;align-items:center;gap:10px;width:100%;padding:9px 10px;border:none;",
    "border-radius:var(--qvq-r-ctl);background:transparent;color:var(--qvq-tx);cursor:pointer;",
    "text-align:left;font-family:var(--qvq-font);font-size:13.5px}",
    ".qvq-quick-row.on{background:var(--qvq-accent-soft);color:var(--qvq-accent)}",
    ".qvq-quick-row-ico{width:16px;height:16px;flex:none;color:var(--qvq-tx-s);display:inline-flex}",
    ".qvq-quick-row.on .qvq-quick-row-ico{color:var(--qvq-accent)}",
    ".qvq-quick-row-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px}",
    ".qvq-quick-row-label{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".qvq-quick-row-sub{font-size:11.5px;color:var(--qvq-tx-s);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".qvq-quick-empty{padding:30px 0;text-align:center;color:var(--qvq-tx-t);font-size:13px}",
    ".qvq-quick-foot{flex:none;border-top:1px solid var(--qvq-bd);padding:8px 14px;font-size:11.5px;",
    "color:var(--qvq-tx-t);display:flex;justify-content:flex-end}",
    "@media (max-width:760px){.qvq-quick{padding:8vh 12px 12px}.qvq-quick-card{max-height:74vh}}",
  ].join("");
  var style = document.createElement("style");
  style.id = "qvq-quick-style";
  style.textContent = css;
  document.head.appendChild(style);
})();

window.QuickPanel = {
  name: "QuickPanel",
  emits: ["close"],
  data() {
    return {
      q: "",
      sessions: [],
      kb: [],
      skills: [],
      active: 0,
      seq: 0,
      timer: null,
      docKey: null,
    };
  },
  computed: {
    st() { return QvQ.store; },
    icons() {
      var A = window.AppShell;
      try { return (A && A.computed && A.computed.ICONS) ? A.computed.ICONS() : {}; }
      catch (e) { return {}; }
    },
    /* 页面静态表：直接派生自 AppShell navGroups（19 页），保证与侧边栏零漂移 */
    pages() {
      var A = window.AppShell;
      var groups = [];
      if (A && A.computed && A.computed.navGroups) {
        try { groups = A.computed.navGroups.call({ ICONS: this.icons }) || []; }
        catch (e) { groups = []; }
      }
      var out = [];
      groups.forEach(function (g) {
        (g.items || []).forEach(function (it) {
          out.push({ id: it.id, labelKey: it.labelKey, ico: it.ico });
        });
      });
      return out;
    },
    actions() {
      var ICONS = this.icons;
      var st = QvQ.store;
      var themeOrder = ["light", "dark", "follow"];
      var nextTheme = themeOrder[(themeOrder.indexOf(st.themeMode || "follow") + 1) % themeOrder.length];
      var langs = ["zh-CN", "zh-TW", "en", "ja", "ru"];
      var langNames = { "zh-CN": "简体中文", "zh-TW": "繁體中文", "en": "English", "ja": "日本語", "ru": "Русский" };
      var nextLang = langs[(langs.indexOf(st.lang) + 1) % langs.length];
      return [
        {
          key: "act:new_chat", ico: ICONS.chat || "",
          label: t("quick_act_new_chat"), sub: "",
          run() {
            api("/api/qvq/sessions/create", "POST", {}).then(function (d) {
              if (d && d.chat_key) {
                QvQ.store.pendingChat = d.chat_key;
                QvQ.store.page = "chat";
              }
            });
          },
        },
        {
          key: "act:theme", ico: this.themeIco(),
          label: t("quick_act_theme"), sub: t("theme_" + nextTheme),
          run() {
            QvQ.setTheme(nextTheme);
            QvQ.toast(t("theme_title").replace("{mode}", t("theme_" + nextTheme)));
          },
        },
        {
          key: "act:lang", ico: "",
          label: t("quick_act_lang"), sub: langNames[nextLang] || nextLang,
          run() { QvQ.setLang(nextLang); },
        },
      ];
    },
    /* 扁平化结果：↑↓ 跨组连续移动 / Enter 执行都基于它 */
    flat() {
      var self = this;
      var out = [];
      var raw = this.q.trim();
      var q = raw.toLowerCase();
      var push = function (header, items) {
        items.forEach(function (it, idx) {
          var row = Object.assign({}, it);
          if (idx === 0) row.header = header;
          out.push(row);
        });
      };
      var hit = function (text) {
        return !q || String(text || "").toLowerCase().indexOf(q) >= 0;
      };
      // 页面（空输入 = 快捷入口语义，全部展示）
      push(t("quick_group_pages"), this.pages.filter(function (p) {
        return hit(p.id) || hit(t(p.labelKey));
      }).map(function (p) {
        return {
          key: "page:" + p.id, ico: p.ico,
          label: t(p.labelKey), sub: "",
          run() { QvQ.store.page = p.id; },
        };
      }));
      // 会话 / 知识 / 技能：仅有关键词时出现（会话与知识由后端内容级搜索）
      if (raw) {
        push(t("quick_group_sessions"), this.sessions.map(function (s) {
          var key = s.chat_key || "";
          return {
            key: "session:" + key, ico: self.icons.chat || "",
            label: s.name || key, sub: QvQ.fill("quick_turns", { n: s.turns || 0 }),
            run() { QvQ.store.pendingChat = key; QvQ.store.page = "chat"; },
          };
        }));
        push(t("quick_group_knowledge"), this.kb.map(function (e) {
          var sub = String(e.content || "").replace(/\s+/g, " ").trim();
          if (sub.length > 60) sub = sub.slice(0, 60) + "…";
          return {
            key: "kb:" + (e.id || e.title), ico: self.icons.knowledge || "",
            label: e.title || String(e.id || ""), sub: sub,
            run() { QvQ.store.page = "knowledge"; },
          };
        }));
        push(t("quick_group_skills"), this.skills.filter(function (s) {
          return hit((s.name || "") + " " + (s.description || ""));
        }).slice(0, 3).map(function (s) {
          return {
            key: "skill:" + s.name, ico: self.icons.skills || "",
            label: s.name || "", sub: String(s.description || ""),
            run() { QvQ.store.page = "skills"; },
          };
        }));
      }
      // 动作
      push(t("quick_group_actions"), this.actions.filter(function (a) {
        return hit(a.label);
      }).map(function (a) {
        return { key: a.key, ico: a.ico, label: a.label, sub: a.sub, run: a.run };
      }));
      return out;
    },
  },
  watch: {
    /* 输入防抖 250ms 后再发搜索 */
    q() {
      var self = this;
      if (this.timer) clearTimeout(this.timer);
      this.timer = setTimeout(function () { self.search(); }, 250);
    },
    /* 结果集变化时高亮回到首项 */
    flat() { this.active = 0; },
    /* 高亮项保持在可视区 */
    active() { this.scrollActive(); },
  },
  mounted() {
    var self = this;
    this.$nextTick(function () {
      if (self.$refs.qin) self.$refs.qin.focus();
    });
    api("/api/qvq/skills").then(function (d) {
      self.skills = (d && d.skills) || [];
    }).catch(function () {});
    /* 面板打开期间接管按键：即使焦点落在 body 也能 Esc / ↑↓ / Enter */
    this.docKey = function (e) {
      var k = e.key;
      if (k === "Escape") { e.preventDefault(); self.close(); return; }
      if (k === "ArrowDown") { e.preventDefault(); self.move(1); return; }
      if (k === "ArrowUp") { e.preventDefault(); self.move(-1); return; }
      if (k === "Enter") { e.preventDefault(); self.exec(self.active); }
    };
    document.addEventListener("keydown", this.docKey, true);
  },
  beforeUnmount() {
    if (this.timer) clearTimeout(this.timer);
    if (this.docKey) document.removeEventListener("keydown", this.docKey, true);
  },
  methods: {
    close() { this.$emit("close"); },
    themeIco() {
      var A = window.AppShell;
      try {
        return (A && A.methods && A.methods.themeIcon)
          ? A.methods.themeIcon.call({ st: QvQ.store }) : "";
      } catch (e) { return ""; }
    },
    move(d) {
      var n = this.flat.length;
      if (!n) return;
      this.active = (this.active + d + n) % n;
    },
    exec(i) {
      var row = this.flat[i];
      if (!row) return;
      this.close();
      if (row.run) row.run();
    },
    search() {
      var self = this;
      var kw = this.q.trim();
      if (!kw) { this.sessions = []; this.kb = []; return; }
      var seq = ++this.seq;
      api("/api/qvq/sessions?q=" + encodeURIComponent(kw)).then(function (d) {
        if (seq !== self.seq) return;
        self.sessions = ((d && d.sessions) || []).slice(0, 5);
      });
      api("/api/qvq/kb?q=" + encodeURIComponent(kw)).then(function (d) {
        if (seq !== self.seq) return;
        self.kb = ((d && d.entries) || []).slice(0, 3);
      });
    },
    scrollActive() {
      var self = this;
      this.$nextTick(function () {
        var list = self.$refs.list;
        if (!list) return;
        var rows = list.querySelectorAll(".qvq-quick-row");
        var el = rows[self.active];
        if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
      });
    },
  },
  template: [
    '<div class="qvq-quick" @click.self="close">',
    '  <div class="qvq-quick-card qvq-glass-card" role="dialog" aria-modal="true" :aria-label="t(\'quick_open\')">',
    '    <div class="qvq-quick-head">',
    '      <span class="qvq-quick-head-ico qvq-quick-ico">',
    '        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
    '      </span>',
    '      <input ref="qin" v-model="q" class="qvq-quick-input" type="text"',
    '             :placeholder="t(\'quick_placeholder\')" :aria-label="t(\'quick_open\')"/>',
    '    </div>',
    '    <div class="qvq-quick-list" ref="list">',
    '      <template v-for="(r, i) in flat" :key="r.key">',
    '        <div v-if="r.header" class="qvq-quick-cat">{{ r.header }}</div>',
    '        <button type="button" class="qvq-quick-row" :class="{ on: i === active }"',
    '                @click="exec(i)" @mousemove="active = i">',
    '          <span v-if="r.ico" class="qvq-quick-row-ico qvq-quick-ico" v-html="r.ico"></span>',
    '          <span class="qvq-quick-row-main">',
    '            <span class="qvq-quick-row-label">{{ r.label }}</span>',
    '            <span v-if="r.sub" class="qvq-quick-row-sub">{{ r.sub }}</span>',
    '          </span>',
    '        </button>',
    '      </template>',
    '      <div v-if="!flat.length" class="qvq-quick-empty">{{ t("quick_no_result") }}</div>',
    '    </div>',
    '    <div class="qvq-quick-foot">{{ t("quick_hint") }}</div>',
    '  </div>',
    '</div>',
  ].join(""),
};
