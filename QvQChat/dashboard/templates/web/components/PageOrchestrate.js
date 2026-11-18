/* 编排：模型链拖拽排序 / 健康 / 运行状态 / 任务时间线 */
window.PageOrchestrate = {
  name: "PageOrchestrate",
  data() {
    return {
      chain: [],
      models: [],
      breakers: [],
      running: [],
      tasks: [],
      runs: [],
      subjobs: [],
      dragIndex: -1,
      savedHint: "",
    };
  },
  mounted() {
    this.load();
  },
  methods: {
    load() {
      var self = this;
      api("/api/qvq/models").then(function (d) {
        self.models = (d && d.models) || [];
        var known = {};
        self.models.forEach(function (m) { known[m.id] = true; });
        self.chain = ((d && d.chain) || [])
          .map(function (c) { return c.provider + ":" + (c.model && c.model.id); })
          .filter(function (id) { return known[id]; });
        self.models.forEach(function (m) {
          if (self.chain.indexOf(m.id) < 0) self.chain.push(m.id);
        });
      });
      api("/api/qvq/breakers").then(function (d) {
        self.breakers = (d && d.breakers) || [];
      });
      api("/api/qvq/running").then(function (d) {
        self.running = (d && d.running) || [];
      });
      api("/api/qvq/tasks").then(function (d) {
        self.tasks = (d && d.tasks) || [];
        self.runs = ((d && d.runs) || []).slice(0, 10);
      });
      api("/api/qvq/subjobs").then(function (d) {
        self.subjobs = (d && d.jobs) || [];
      });
    },
    taskLabel(tk) {
      return QvQ.taskLabel(tk);
    },
    openSub(j) {
      QvQ.store.pendingChat = j.sub_key;
      QvQ.store.page = "chat";
    },
    cancelJob(j) {
      var self = this;
      api("/api/qvq/subjobs/cancel", "POST", { sub_key: j.sub_key }).then(function (r) {
        if (r && r.error) { self.savedHint = r.error; return; }
        self.load();
      });
    },
    nameOf(id) {
      var m = this.models.filter(function (x) { return x.id === id; })[0];
      return m ? id : id;
    },
    dragStart(i) { this.dragIndex = i; },
    drop(i) {
      if (this.dragIndex < 0 || this.dragIndex === i) return;
      var item = this.chain.splice(this.dragIndex, 1)[0];
      this.chain.splice(i, 0, item);
      this.dragIndex = -1;
      this.saveChain();
    },
    saveChain() {
      var self = this;
      var chain = this.chain.map(function (id) {
        var parts = id.split(":");
        return { provider: parts[0], model: parts.slice(1).join(":") };
      });
      api("/api/qvq/chain/save", "POST", { chain: chain }).then(function () {
        self.savedHint = t("orch_chain_saved");
        setTimeout(function () { self.savedHint = ""; }, 2000);
      });
    },
    breakerOf(id) {
      return this.breakers.filter(function (b) { return b.id === id || b.model === id; })[0] || null;
    },
    resetBreaker(id) {
      var self = this;
      api("/api/qvq/breakers/reset", "POST", { model: id }).then(function () {
        self.load();
      });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_orchestrate") }}</div>',
    '    </div>',
    '    <span class="qvq-cfg-saved" v-if="savedHint">{{ savedHint }}</span>',
    '  </div>',
    '  <div class="orch-stack">',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-head"><span class="qvq-card-title">{{ t("orch_model_chain") }}</span></div>',
    '      <div class="qvq-meta-line" style="margin-bottom:10px">{{ t("orch_chain_hint") }}</div>',
    '      <div class="orch-chain">',
    '        <div v-for="(id, i) in chain" :key="id" class="orch-item"',
    '             :class="{ dragging: dragIndex === i }"',
    '             draggable="true" @dragstart="dragStart(i)" @dragend="dragIndex = -1"',
    '             @dragover.prevent @drop="drop(i)">',
    '          <span class="orch-idx" :class="{ first: i === 0 }">{{ i + 1 }}</span>',
    '          <span class="orch-id" :class="{ cooldown: !!breakerOf(id) }">{{ nameOf(id) }}</span>',
    '          <span v-if="breakerOf(id)" class="orch-cool"><i></i>{{ t("health_cooldown") }}</span>',
    '          <button v-if="breakerOf(id)" type="button" class="qvq-link"',
    '                  @click="resetBreaker(id)">{{ t("breakers_reset") }}</button>',
    '        </div>',
    '        <div v-if="!chain.length" class="qvq-empty"><Mascot :size="30" mood="idle"/>{{ t("model_none") }}</div>',
    '      </div>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-head"><span class="qvq-card-title">{{ t("orch_running") }}</span></div>',
    '      <div v-if="!running.length" class="qvq-empty"><Mascot :size="30" mood="sleep"/>{{ t("running_none") }}</div>',
    '      <div v-for="(r, i) in running" :key="i" class="trash-row">',
    '        <span class="nm">{{ r.session }}<i v-if="r.agent === \'sub\'" class="chat-subtag hv">{{ t("sub_badge") }}</i></span>',
    '        <span class="qvq-meta-line">{{ r.status }}</span>',
    '      </div>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-head">',
    '        <span class="qvq-card-title">{{ t("orch_subjobs") }}</span>',
    '        <button type="button" class="qvq-link" @click="load">{{ t("refresh") }}</button>',
    '      </div>',
    '      <div v-if="!subjobs.length" class="qvq-empty">{{ t("subjobs_none") }}</div>',
    '      <div v-for="j in subjobs" :key="j.sub_key" class="trash-row">',
    '        <button type="button" class="nm orch-sub-open" @click="openSub(j)" :title="j.parent_chat_key">',
    '          {{ j.task || j.sub_key }}</button>',
    '        <span class="qvq-meta-line">{{ j.status }}<template v-if="j.ms"> · {{ j.ms }}ms</template></span>',
    '        <button v-if="j.status === \'running\'" type="button" class="prov-act danger"',
    '                @click="cancelJob(j)">{{ t("cancel") }}</button>',
    '      </div>',
    '    </n-card>',
    '  </div>',
    '  <h3 class="plat-sec">{{ t("orch_timeline") }}</h3>',
    '  <n-card size="small" class="qvq-glass-card">',
    '    <div v-if="!tasks.length && !runs.length" class="qvq-empty"><Mascot :size="30" mood="idle"/>{{ t("timeline_empty") }}</div>',
    '    <div v-for="tk in tasks" :key="tk.id" class="trash-row">',
    '      <span class="nm">{{ taskLabel(tk) }}</span>',
    '      <span class="qvq-meta-line">{{ t("task_next") }} {{ tk.next_formatted }}</span>',
    '    </div>',
    '    <div v-for="(r, i) in runs" :key="\'r\' + i" class="trash-row">',
    '      <span class="nm">{{ taskLabel(r) }}</span>',
    '      <span class="qvq-meta-line">{{ r.at_formatted }} · {{ r.error || "ok" }}</span>',
    '    </div>',
    '  </n-card>',
    '</div>',
  ].join(""),
};
