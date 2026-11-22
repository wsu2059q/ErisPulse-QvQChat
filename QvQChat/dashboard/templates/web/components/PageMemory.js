/* 记忆：会话列表为主，点击行开侧栏看该会话的记忆条目与用户画像 */
window.PageMemory = {
  name: "PageMemory",
  data() {
    return {
      sessions: [],
      sessQ: "",
      loadingSess: false,
      drawer: false,
      active: null,
      entries: [],
      profile: null,
      profileUser: "",
      editSec: null,
      editItems: [],
      loading: false,
    };
  },
  computed: {
    shownSessions() {
      var q = this.sessQ.trim().toLowerCase();
      var rows = this.sessions;
      if (!q) return rows;
      return rows.filter(function (s) {
        return ((s.name || "") + " " + (s.chat_key || "")).toLowerCase().indexOf(q) >= 0;
      });
    },
  },
  mounted() {
    var self = this;
    this.loadingSess = true;
    api("/api/qvq/sessions?limit=200").then(function (d) {
      self.loadingSess = false;
      var rows = (d && d.sessions) || [];
      // 概要注入：条数 / 最近一条 / 最后写入（GET /api/qvq/memory 无 chat_key 返回 scopes）
      api("/api/qvq/memory").then(function (m) {
        var byKey = {};
        ((m && m.scopes) || []).forEach(function (s) { byKey[s.chat_key] = s; });
        rows.forEach(function (s) {
          var sc = byKey[s.chat_key] || {};
          s.count = sc.count || 0;
          s.last_text = sc.last_text || "";
          s.last_ts = sc.last_ts || 0;
        });
        rows.sort(function (a, b) { return (b.last_ts || 0) - (a.last_ts || 0); });
        self.sessions = rows;
      });
    });
  },
  methods: {
    relTime(ts) {
      if (!ts) return "";
      var diff = Date.now() / 1000 - Number(ts);
      if (diff < 90) return t("ts_just_now");
      if (diff < 3600) return t("ts_min_ago").replace("{n}", String(Math.floor(diff / 60)));
      var d = new Date(Number(ts) * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return (d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
    },
    open(s) {
      var self = this;
      this.active = s;
      this.entries = [];
      this.profile = null;
      this.profileUser = "";
      this.drawer = true;
      this.loading = true;
      api("/api/qvq/memory?chat_key=" + encodeURIComponent(s.chat_key)).then(function (d) {
        self.loading = false;
        self.entries = (d && d.entries) || [];
        self.profile = (d && d.profile) || null;
        self.profileUser = (d && d.profile_user) || "";
      });
    },
    reload() {
      if (this.active) this.open(this.active);
    },
    del(e) {
      var self = this;
      api("/api/qvq/memory/delete", "POST", {
        chat_key: this.active.chat_key, content: e.content || e.text || "",
      }).then(function () { self.reload(); });
    },
    clearProfile() {
      var self = this;
      if (!this.profileUser) return;
      api("/api/qvq/profile/clear", "POST", { user_key: this.profileUser }).then(function () {
        self.reload();
      });
    },
    startEdit(sec) {
      // 画像纠错：整段进入编辑（每行一条），保存走 profile/edit 整段替换
      var items = this.profile && this.profile[sec] ? this.profile[sec] : [];
      this.editSec = sec;
      this.editItems = this.profileItems(items).map(function (x) { return x.text; });
    },
    cancelEdit() { this.editSec = null; this.editItems = []; },
    addEditRow() { this.editItems.push(""); },
    rmEditRow(i) { this.editItems.splice(i, 1); },
    saveEdit() {
      var self = this;
      var sec = this.editSec;
      api("/api/qvq/profile/edit", "POST", {
        user_key: this.profileUser, section: sec, items: this.editItems,
      }).then(function (r) {
        if (r && r.error) { QvQ.toast(r.error); return; }
        if (r && r.ok) {
          QvQ.toast(t("settings_saved"));
          self.profile = r.profile || self.profile;
          self.cancelEdit();
        }
      });
    },
    profileItems(list) {
      // 画像条目：{text, ts} 对象或纯字符串 → 统一为 {text, ts}
      return (list || []).map(function (x) {
        if (typeof x === "string") return { text: x, ts: 0 };
        return { text: String(x.text || ""), ts: Number(x.ts) || 0 };
      }).filter(function (x) { return x.text; });
    },
    fmtTs(ts) {
      if (!ts) return "";
      var d = new Date(ts * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return (d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_memory") }}</div>',
    '      <div class="qvq-page-sub">{{ sessions.length }} {{ t("stat_sessions") }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-input v-model:value="sessQ" size="small" clearable :placeholder="t(\'search_ph\')"',
    '               style="width:220px"/>',
    '    </div>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loadingSess"><i></i>{{ t("loading") }}</div>',
    '  <div class="qvq-table-wrap" v-if="!loadingSess">',
    '  <table class="qvq-table">',
    '    <thead><tr>',
    '      <th>{{ t("recent_sessions") }}</th>',
    '      <th style="width:70px">{{ t("mem_entries_n") }}</th>',
    '      <th style="width:110px"></th>',
    '    </tr></thead>',
    '    <tbody>',
    '      <tr v-for="s in shownSessions" :key="s.chat_key">',
    '        <td><button type="button" class="sess-name" @click="open(s)">',
    '          {{ s.name || s.chat_key }}<i>{{ s.chat_key }}</i>',
    '          <span class="mem-last" v-if="s.last_text">{{ s.last_text }}</span>',
    '          <span class="qvq-meta-line" v-if="s.last_ts">{{ relTime(s.last_ts) }}</span></button></td>',
    '        <td>{{ s.count || 0 }}</td>',
    '        <td class="sess-acts">',
    '          <button type="button" class="prov-act" @click="open(s)">{{ t("col_detail") }}</button>',
    '        </td>',
    '      </tr>',
    '    </tbody>',
    '  </table>',
    '  </div>',
    '  <div v-if="!loadingSess && !shownSessions.length" class="qvq-empty">-</div>',
    '  <n-drawer v-model:show="drawer" :width="460" placement="right">',
    '    <n-drawer-content :title="active ? (active.name || active.chat_key) : \'\'" closable>',
    '      <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '      <div class="prov-form" v-if="!loading">',
    '        <div class="prov-field">',
    '          <label>{{ t("nav_memory") }} · {{ entries.length }} {{ t("mem_entries_n") }}</label>',
    '          <div v-for="(e, i) in entries" :key="i" class="mem-row">',
    '            <div class="mem-tx">{{ e.content || e.text }}',
    '              <span class="mem-tags">',
    '                <i class="mem-imp" v-for="n in (e.importance || 0)" :key="n"></i>',
    '                <code v-if="e.category">{{ e.category }}</code>',
    '                <span class="qvq-meta-line" v-if="e.ts">{{ relTime(e.ts) }}</span>',
    '              </span></div>',
    '            <button type="button" class="prov-act danger" @click="del(e)">×</button>',
    '          </div>',
    '          <div v-if="!entries.length" class="qvq-empty">-</div>',
    '        </div>',
    '        <div class="prov-field" v-if="profile">',
    '          <label>{{ t("mem_profile") }} <code class="mem-user">{{ profileUser }}</code></label>',
    '          <div class="mem-sec" v-if="profileItems(profile.traits).length || editSec === \'traits\'">',
    '            <div class="mem-sec-head"><b>{{ t("mem_traits") }}</b>',
    '              <button type="button" class="prov-act" v-if="editSec !== \'traits\'" @click="startEdit(\'traits\')">{{ t("edit") }}</button>',
    '            </div>',
    '            <template v-if="editSec !== \'traits\'">',
    '              <div v-for="(x, i) in profileItems(profile.traits)" :key="\'t\' + i" class="mem-pitem">',
    '                <div class="mem-ptx">{{ x.text }}</div>',
    '                <div class="qvq-meta-line" v-if="x.ts">{{ fmtTs(x.ts) }}</div>',
    '              </div>',
    '            </template>',
    '            <template v-else>',
    '              <div v-for="(x, i) in editItems" :key="\'et\' + i" class="mem-editrow">',
    '                <n-input v-model:value="editItems[i]" size="small" :placeholder="t(\'mem_profile_item_ph\')"/>',
    '                <button type="button" class="prov-act danger" @click="rmEditRow(i)">×</button>',
    '              </div>',
    '              <div class="mem-edit-acts">',
    '                <n-button size="tiny" @click="addEditRow">{{ t("mem_profile_add") }}</n-button>',
    '                <n-button size="tiny" @click="cancelEdit">{{ t("cancel") }}</n-button>',
    '                <n-button size="tiny" type="primary" @click="saveEdit">{{ t("save") }}</n-button>',
    '              </div>',
    '            </template>',
    '          </div>',
    '          <div class="mem-sec" v-if="profileItems(profile.preferences).length || editSec === \'preferences\'">',
    '            <div class="mem-sec-head"><b>{{ t("mem_prefs") }}</b>',
    '              <button type="button" class="prov-act" v-if="editSec !== \'preferences\'" @click="startEdit(\'preferences\')">{{ t("edit") }}</button>',
    '            </div>',
    '            <template v-if="editSec !== \'preferences\'">',
    '              <div v-for="(x, i) in profileItems(profile.preferences)" :key="\'p\' + i" class="mem-pitem">',
    '                <div class="mem-ptx">{{ x.text }}</div>',
    '                <div class="qvq-meta-line" v-if="x.ts">{{ fmtTs(x.ts) }}</div>',
    '              </div>',
    '            </template>',
    '            <template v-else>',
    '              <div v-for="(x, i) in editItems" :key="\'ep\' + i" class="mem-editrow">',
    '                <n-input v-model:value="editItems[i]" size="small" :placeholder="t(\'mem_profile_item_ph\')"/>',
    '                <button type="button" class="prov-act danger" @click="rmEditRow(i)">×</button>',
    '              </div>',
    '              <div class="mem-edit-acts">',
    '                <n-button size="tiny" @click="addEditRow">{{ t("mem_profile_add") }}</n-button>',
    '                <n-button size="tiny" @click="cancelEdit">{{ t("cancel") }}</n-button>',
    '                <n-button size="tiny" type="primary" @click="saveEdit">{{ t("save") }}</n-button>',
    '              </div>',
    '            </template>',
    '          </div>',
    '          <div class="mem-sec" v-if="profileItems(profile.facts).length || editSec === \'facts\'">',
    '            <div class="mem-sec-head"><b>{{ t("mem_facts") }}</b>',
    '              <button type="button" class="prov-act" v-if="editSec !== \'facts\'" @click="startEdit(\'facts\')">{{ t("edit") }}</button>',
    '            </div>',
    '            <template v-if="editSec !== \'facts\'">',
    '              <div v-for="(x, i) in profileItems(profile.facts)" :key="\'f\' + i" class="mem-pitem">',
    '                <div class="mem-ptx">{{ x.text }}</div>',
    '                <div class="qvq-meta-line" v-if="x.ts">{{ fmtTs(x.ts) }}</div>',
    '              </div>',
    '            </template>',
    '            <template v-else>',
    '              <div v-for="(x, i) in editItems" :key="\'ef\' + i" class="mem-editrow">',
    '                <n-input v-model:value="editItems[i]" size="small" :placeholder="t(\'mem_profile_item_ph\')"/>',
    '                <button type="button" class="prov-act danger" @click="rmEditRow(i)">×</button>',
    '              </div>',
    '              <div class="mem-edit-acts">',
    '                <n-button size="tiny" @click="addEditRow">{{ t("mem_profile_add") }}</n-button>',
    '                <n-button size="tiny" @click="cancelEdit">{{ t("cancel") }}</n-button>',
    '                <n-button size="tiny" type="primary" @click="saveEdit">{{ t("save") }}</n-button>',
    '              </div>',
    '            </template>',
    '          </div>',
    '          <n-button size="tiny" type="error" style="margin-top:10px" @click="clearProfile">',
    '            {{ t("mem_profile_clear") }}</n-button>',
    '        </div>',
    '        <div class="prov-field" v-if="!profile">',
    '          <label>{{ t("mem_profile") }}</label>',
    '          <div class="qvq-empty">-</div>',
    '        </div>',
    '      </div>',
    '    </n-drawer-content>',
    '  </n-drawer>',
    '</div>',
  ].join(""),
};
