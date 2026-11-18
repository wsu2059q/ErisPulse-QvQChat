/* 收件箱：平台事件流（通知/请求），请求可直接同意/拒绝 */
window.PageInbox = {
  name: "PageInbox",
  data() {
    return {
      events: [],
      total: 0,
      unread: 0,
      offset: 0,
      kind: "",
      busy: false,
      loading: false,
      observer: null,
    };
  },
  computed: {
    kindOptions() {
      return [
        { label: t("inbox_filter_all"), value: "" },
        { label: t("inbox_kind_notice"), value: "notice" },
        { label: t("inbox_kind_request"), value: "request" },
      ];
    },
    countText() {
      return t("inbox_count")
        .replace("{n}", String(this.events.length))
        .replace("{u}", String(this.unread));
    },
    pageText() {
      if (!this.events.length) return "";
      return (this.offset + 1) + "-" + (this.offset + this.events.length) + " / " + this.total;
    },
    hasPrev() { return this.offset > 0; },
    hasNext() { return this.offset + this.events.length < this.total; },
  },
  mounted() {
    this.load();
  },
  beforeUnmount() {
    if (this.observer) this.observer.disconnect();
  },
  methods: {
    load() {
      var self = this;
      this.busy = true;
      var url = "/api/qvq/inbox?limit=200&offset=" + this.offset;
      if (this.kind) url += "&kind=" + encodeURIComponent(this.kind);
      if (self.offset) {
        self.loading = true;
        api(url).then(function (d) {
          self.loading = false;
          self.busy = false;
          self.applyPage(d);
        });
        return;
      }
      QvQ.swr(self, "inbox:" + self.kind + ":0", url, function (d) { self.applyPage(d); });
    },
    applyPage(d) {
      var self = this;
      self.busy = false;
      self.events = (d && d.events) || [];
      self.total = (d && d.total) || 0;
      self.unread = (d && d.unread) || 0;
      self.$nextTick(self.watchSentinel);
    },
    watchSentinel() {
      var self = this;
      if (this.observer || !("IntersectionObserver" in window)) return;
      var sentinel = this.$el.querySelector(".scroll-sentinel");
      if (!sentinel) return;
      this.observer = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting && self.hasNext && !self.loading && !self.busy) self.page(1);
      }, { root: this.$el.closest(".qvq-main"), rootMargin: "200px" });
      this.observer.observe(sentinel);
    },
    setKind(v) {
      this.kind = v || "";
      this.offset = 0;
      this.load();
    },
    page(delta) {
      this.offset = Math.max(0, this.offset + delta * 200);
      this.load();
    },
    fmtTime(ts) {
      if (!ts) return "-";
      var d = new Date(Number(ts) * 1000);
      var p = function (n) { return (n < 10 ? "0" : "") + n; };
      return (d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
    },
    kindOf(e) {
      var label = e.kind === "request" ? t("inbox_kind_request") : t("inbox_kind_notice");
      var detail = e.detail_type || "";
      if (e.sub_type) detail += ":" + e.sub_type;
      return detail ? label + " · " + detail : label;
    },
    handle(e, action) {
      var self = this;
      api("/api/qvq/inbox/handle", "POST", { id: e.id, action: action }).then(function (r) {
        if (r && r.ok) self.load();
      });
    },
    del(e) {
      var self = this;
      api("/api/qvq/inbox/delete", "POST", { id: e.id, account: e.account || "" })
        .then(function () { self.load(); });
    },
    clearAll() {
      var self = this;
      this.busy = true;
      api("/api/qvq/inbox/clear", "POST", {}).then(function () {
        self.busy = false;
        self.offset = 0;
        self.load();
      });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("inbox_title") }}</div>',
    '      <div class="qvq-page-sub">{{ countText }}</div>',
    '    </div>',
    '    <div class="qvq-cfg-tools">',
    '      <n-select :value="kind" :options="kindOptions" size="small" style="width:120px"',
    '                @update:value="setKind"/>',
    '      <n-button size="small" :loading="busy" @click="load">{{ t("refresh") }}</n-button>',
    '      <n-button size="small" type="error" ghost :loading="busy" @click="clearAll">',
    '        {{ t("inbox_clear") }}</n-button>',
    '    </div>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div v-for="e in events" :key="e.id" class="inbox-row" :class="{ unread: !e.read }" v-if="!loading">',
    '    <div class="inbox-main">',
    '      <div class="inbox-summary">{{ e.summary || e.id }}</div>',
    '      <div class="inbox-meta">{{ kindOf(e) }} · {{ e.account || "-" }} · {{ fmtTime(e.ts) }}</div>',
    '    </div>',
    '    <div class="inbox-acts">',
    '      <span class="inbox-badge" v-if="!e.read">{{ t("inbox_unread") }}</span>',
    '      <template v-if="e.kind === \'request\' && e.request_id">',
    '        <button type="button" class="prov-act" @click="handle(e, \'accept\')">{{ t("inbox_accept") }}</button>',
    '        <button type="button" class="prov-act danger" @click="handle(e, \'reject\')">{{ t("inbox_reject") }}</button>',
    '      </template>',
    '      <button type="button" class="prov-act danger" @click="del(e)">{{ t("del") }}</button>',
    '    </div>',
    '  </div>',
    '  <div v-if="!loading && !events.length" class="qvq-empty">{{ t("inbox_empty") }}</div>',
    '  <div class="scroll-sentinel" v-if="events.length && hasNext"></div>',
    '</div>',
  ].join(""),
};
