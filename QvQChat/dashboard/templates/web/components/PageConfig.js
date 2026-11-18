/* 配置页：文档式 —— 左侧目录 / 右侧长列表，靠排版分层 */
window.PageConfig = {
  name: "PageConfig",
  data() {
    return {
      fields: [],
      groupOrder: [],
      draft: {},
      initial: {},
      errors: {},
      q: "",
      active: "",
      saving: false,
      savedHint: "",
      confirmOpen: false,
      dangerKeys: [],
      loading: true,
    };
  },
  mounted() {
    var self = this;
    this.load().then(function () {
      self.$nextTick(function () {
        self.scroller = self.$el.closest(".qvq-main");
        if (!self.scroller) return;
        self.onScroll = function () {
          if (self.tick) return;
          self.tick = true;
          requestAnimationFrame(function () {
            self.tick = false;
            self.spy();
          });
        };
        self.scroller.addEventListener("scroll", self.onScroll, { passive: true });
        self.spy();
      });
    });
  },
  beforeUnmount() {
    if (this.scroller && this.onScroll) {
      this.scroller.removeEventListener("scroll", this.onScroll);
    }
  },
  computed: {
    same() {
      return function (a, b) {
        if (a === b) return true;
        if (a && b && typeof a === "object" && typeof b === "object") {
          return JSON.stringify(a) === JSON.stringify(b);
        }
        return false;
      };
    },
    dirtyKeys() {
      var out = [];
      var self = this;
      this.fields.forEach(function (f) {
        if (!self.same(self.draft[f.key], self.initial[f.key])) out.push(f.key);
      });
      return out;
    },
    dirtyCount() { return this.dirtyKeys.length; },
    groups() {
      var q = this.q.trim().toLowerCase();
      var map = {};
      this.fields.forEach(function (f) {
        if (q && f.key.toLowerCase().indexOf(q) < 0 &&
            String(f.description || "").toLowerCase().indexOf(q) < 0) return;
        (map[f.group] = map[f.group] || []).push(f);
      });
      var self = this;
      return this.groupOrder
        .filter(function (g) { return map[g.id] && map[g.id].length; })
        .map(function (g) {
          var items = map[g.id].slice().sort(function (a, b) { return (a.order || 99) - (b.order || 99); });
          return {
            id: g.id,
            label: t("group_" + g.id),
            fields: items,
            dirty: self.groupDirty(items),
          };
        });
    },
  },
  methods: {
    toDraft(field, value) {
      var w = field.widget || "text";
      if (w === "model_map") {
        return value && typeof value === "object" ? JSON.parse(JSON.stringify(value)) : {};
      }
      if (w === "json") {
        if (value === null || value === undefined || value === "") return "";
        return typeof value === "string" ? value : JSON.stringify(value, null, 2);
      }
      if (w === "list" || w === "lines") {
        if (Array.isArray(value)) {
          return (field.choices || []).length ? value.slice() : value.join("\n");
        }
        return String(value === null || value === undefined ? "" : value);
      }
      if (value === null || value === undefined) return w === "number" || w === "slider" ? null : "";
      return value;
    },
    load() {
      var self = this;
      this.loading = true;
      return api("/api/qvq/config").then(function (data) {
        self.loading = false;
        var fields = (data && data.fields) || [];
        self.fields = Array.isArray(fields) ? fields : [];
        var rawGroups = (data && data.groups) || [];
        // groups 兼容：数组 [{id,label}] 为常规形态；字典 {id:...} 转数组
        if (Array.isArray(rawGroups)) {
          self.groupOrder = rawGroups;
        } else if (rawGroups && typeof rawGroups === "object") {
          self.groupOrder = Object.keys(rawGroups).map(function (k) {
            var v = rawGroups[k];
            return { id: k, label: typeof v === "string" ? v : k };
          });
        } else {
          self.groupOrder = [];
        }
        var draft = {};
        var initial = {};
        fields.forEach(function (f) {
          draft[f.key] = self.toDraft(f, f.value);
          initial[f.key] = draft[f.key];
        });
        self.draft = draft;
        self.initial = initial;
        self.errors = {};
      });
    },
    groupDirty(items) {
      var self = this;
      return items.some(function (f) { return !self.same(self.draft[f.key], self.initial[f.key]); });
    },
    isDirty(f) { return !this.same(this.draft[f.key], this.initial[f.key]); },
    titleOf(f) { return QvQ.fieldTitle(f.description, f.key); },
    isWide(f) {
      var w = f.widget || "text";
      return w === "json" || w === "lines" || w === "list" || w === "checks" || w === "model_map";
    },
    hintOf(f) {
      var text = QvQ.fieldDesc(f.description, f.key);
      if (f.choices && f.choices.length) {
        var extra = f.choices.length + " " + t("cf_options_n");
        text = text ? text + " · " + extra : extra;
      }
      return text;
    },
    navItems() {
      // 数组兜底：groups/groupOrder 数据异常（旧接口/缓存）时不至于抛 forEach not a function
      var items = Array.isArray(this.groups) ? this.groups.slice() : [];
      if (items.length) {
        items.push({ id: "backup", label: t("nav_backup"), fields: [], dirty: false });
      }
      return items;
    },
    spy() {
      if (!this.scroller) return;
      var top = this.scroller.scrollTop + 120;
      var current = "";
      var self = this;
      var items = Array.isArray(this.navItems) ? this.navItems : [];
      items.forEach(function (g) {
        var el = document.getElementById("doc-" + g.id);
        if (el && el.offsetTop <= top) current = g.id;
      });
      this.active = current || (items[0] && items[0].id) || "";
    },
    jump(id) {
      var el = document.getElementById("doc-" + id);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      this.active = id;
    },
    reset() {
      var draft = {};
      var self = this;
      this.fields.forEach(function (f) { draft[f.key] = self.initial[f.key]; });
      this.draft = draft;
      this.errors = {};
      this.savedHint = "";
    },
    revertField(f) {
      this.draft[f.key] = this.initial[f.key];
    },
    trySave() {
      if (!this.dirtyKeys.length || this.saving) return;
      var self = this;
      var dangerous = this.fields
        .filter(function (f) { return f.dangerous && !self.same(self.draft[f.key], self.initial[f.key]); })
        .map(function (f) { return f.key; });
      if (dangerous.length) {
        this.dangerKeys = dangerous;
        this.confirmOpen = true;
        return;
      }
      this.save();
    },
    save() {
      var body = {};
      var errors = {};
      var self = this;
      this.dirtyKeys.forEach(function (key) {
        var field = self.fields.filter(function (f) { return f.key === key; })[0];
        if (!field) return;
        var value = self.draft[key];
        if (field.widget === "model_map") {
          body[key] = value && typeof value === "object" ? value : {};
          return;
        }
        if (field.widget === "json") {
          try {
            value = value.trim() ? JSON.parse(value) : {};
          } catch (e) {
            errors[key] = "JSON: " + e.message;
            return;
          }
        }
        body[key] = value;
      });
      if (Object.keys(errors).length) {
        this.errors = errors;
        this.confirmOpen = false;
        return;
      }
      this.saving = true;
      this.errors = {};
      api("/api/qvq/config", "POST", body).then(function (r) {
        self.saving = false;
        self.confirmOpen = false;
        if (r && r.errors && Object.keys(r.errors).length) {
          self.errors = r.errors;
          return;
        }
        self.savedHint = t("settings_saved");
        setTimeout(function () { self.savedHint = ""; }, 2000);
        self.load();
      });
    },
  },
  template: [
    '<div class="qvq-page-body qvq-doc">',
    '  <header class="doc-head">',
    '    <div>',
    '      <h1 class="doc-title">{{ t("nav_settings") }}</h1>',
        '    </div>',
    '    <div class="doc-tools">',
    '      <span class="qvq-cfg-saved" v-if="savedHint">{{ savedHint }}</span>',
    '      <n-input v-model:value="q" size="small" clearable :placeholder="t(\'settings_search_ph\')"',
    '               style="width:180px"/>',
    '      <n-button size="small" :disabled="!dirtyCount" @click="reset">{{ t("settings_reset") }}</n-button>',
    '      <n-button size="small" type="primary" :loading="saving" :disabled="!dirtyCount"',
    '                @click="trySave">{{ t("save") }}</n-button>',
    '    </div>',
    '  </header>',
    '  <div class="doc-wrap">',
    '    <nav class="doc-nav">',
    '      <button v-for="g in navItems" :key="g.id" type="button" class="doc-navitem"',
    '              :class="{ on: active === g.id }" @click="jump(g.id)">',
    '        <span class="nm">{{ g.label }}</span>',
    '        <span class="cnt" v-if="g.fields.length">{{ g.fields.length }}</span>',
    '        <span class="dot" v-if="g.dirty"></span>',
    '      </button>',
    '    </nav>',
    '    <div class="doc-body" v-if="!loading">',
    '      <div class="qvq-loading"><i></i>{{ t("loading") }}</div>',
    '    </div>',
    '    <div class="doc-body" v-else>',
    '      <section v-for="g in groups" :key="g.id" :id="\'doc-\' + g.id" class="doc-sec">',
    '        <h2 class="doc-sec-title">',
    '          <span>{{ g.label }}</span>',
    '          <span class="cnt">{{ g.fields.length }}</span>',
    '          <span class="dot" v-if="g.dirty"></span>',
    '        </h2>',
    '        <div v-for="f in g.fields" :key="f.key" class="doc-row"',
    '             :class="{ dirty: isDirty(f), wide: isWide(f) }">',
    '          <div class="doc-label">',
    '            <div class="doc-row-title">',
    '              {{ titleOf(f) }}',
    '              <span class="doc-flag" v-if="f.dangerous">{{ t("settings_dangerous") }}</span>',
    '            </div>',
    '            <div class="doc-row-hint" v-if="hintOf(f)" :title="f.description">{{ hintOf(f) }}</div>',
    '          </div>',
    '          <div class="doc-ctl">',
    '            <schema-form :field="f" hide-head :model-value="draft[f.key]"',
    '                         :error="errors[f.key] || \'\'"',
    '                         @update:model-value="v => draft[f.key] = v"/>',
    '            <button v-if="isDirty(f)" type="button" class="doc-revert"',
    '                    :title="t(\'cf_revert\')" @click="revertField(f)">↺</button>',
    '          </div>',
    '        </div>',
    '      </section>',
    '      <section id="doc-backup" class="doc-sec cfg-backup">',
    '        <h2 class="doc-sec-title"><span>{{ t("nav_backup") }}</span></h2>',
    '        <backup-panel/>',
    '      </section>',
    '      <div v-if="!groups.length" class="qvq-empty">{{ t("settings_no_result") }}</div>',
    '    </div>',
    '  </div>',
    '  <transition name="doc-pop">',
    '    <div class="doc-save" v-if="dirtyCount">',
    '      <span class="doc-save-n">{{ dirtyCount }} {{ t("settings_unsaved_items") }}</span>',
    '      <button type="button" class="doc-save-btn" @click="reset">{{ t("settings_reset") }}</button>',
    '      <button type="button" class="doc-save-btn primary" :disabled="saving" @click="trySave">',
    '        {{ t("save") }}</button>',
    '    </div>',
    '  </transition>',
    '  <n-modal v-model:show="confirmOpen" preset="card" class="qvq-modal-card"',
    '           style="max-width:420px" :title="t(\'settings_confirm_title\')" :bordered="false">',
    '    <div class="qvq-modal-hint">{{ t("settings_confirm_body") }}</div>',
    '    <div class="cf-confirm-keys">',
    '      <code v-for="k in dangerKeys" :key="k">{{ k }}</code>',
    '    </div>',
    '    <template #footer>',
    '      <div class="qvq-modal-foot">',
    '        <n-button size="small" @click="confirmOpen = false">{{ t("cancel") }}</n-button>',
    '        <n-button size="small" type="primary" @click="save">{{ t("save") }}</n-button>',
    '      </div>',
    '    </template>',
    '  </n-modal>',
    '</div>',
  ].join(""),
};
