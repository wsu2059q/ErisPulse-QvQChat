/* 编排：模型链拖拽排序 / 健康 / 运行状态 / 任务时间线 */
/* i18n: 本文件新增文案键（i18n.js 各语言待补，zh-CN 建议值如下）
 * orch_test_tip=测试该模型连通性
 * orch_cool_reset_tip=熔断冷却中 · 点击立即重置
 * breakers_reset_done=已重置熔断
 * subjob_open_parent=父会话
 * subjob_cancelled=已取消后台任务
 * partic_budget_go_tip=点击前往用量页调整预算
 */
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
      particip: null,
      dragIndex: -1,
      savedHint: "",
      testState: {},
    };
  },
  mounted() {
    this.load();
    this.loadParticip();
  },
  methods: {
    /* 参与决策观测：预算现状 + 最近决策环形日志（后端环形缓冲 100 条） */
    loadParticip() {
      var self = this;
      api("/api/qvq/participation").then(function (d) {
        self.particip = d || null;
      });
    },
    participText(d) {
      if (!d) return "";
      var what = d.decision === "speak" ? t("partic_speak") : t("partic_silent");
      var prov = d.provider ? " · " + d.provider : "";
      return what + prov + (d.reason ? " · " + d.reason : "");
    },
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
    openParent(j) {
      if (!j.parent_chat_key) return;
      QvQ.store.pendingChat = j.parent_chat_key;
      QvQ.store.page = "chat";
    },
    cancelJob(j) {
      var self = this;
      api("/api/qvq/subjobs/cancel", "POST", { sub_key: j.sub_key }).then(function (r) {
        if (r && r.error) { QvQ.toast(r.error); return; }
        QvQ.toast(t("subjob_cancelled"));
        self.load();
      });
    },
    /* 链上模型即时连通测试：本页自持 state（键 provider:model），行内显示 ms / 失败 */
    testChain(id) {
      var self = this;
      self.testState = Object.assign({}, self.testState, { [id]: { busy: true, text: t("prov_testing") } });
      api("/api/qvq/models/test", "POST", { id: id }).then(function (r) {
        var state = r && r.ok
          ? { ok: true, text: t("model_test_ok") + " · " + r.ms + "ms" }
          : { ok: false, text: (r && r.error) || t("model_test_fail") };
        self.testState = Object.assign({}, self.testState, { [id]: state });
      });
    },
    goUsageBudget() {
      QvQ.store.page = "usage";
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
    moveItem(i, delta) {
      var j = i + delta;
      if (j < 0 || j >= this.chain.length) return;
      var item = this.chain.splice(i, 1)[0];
      this.chain.splice(j, 0, item);
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
      api("/api/qvq/breakers/reset", "POST", { model: id }).then(function (r) {
        if (r && r.error) { QvQ.toast(r.error); return; }
        QvQ.toast(t("breakers_reset_done"));
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
    '          <span class="orch-idx" :class="{ first: i === 0 }" :title="t(\'orch_idx_tip\')">{{ i + 1 }}</span>',
    '          <span class="orch-id" :class="{ cooldown: !!breakerOf(id) }">{{ nameOf(id) }}</span>',
    '          <button type="button" class="prov-act orch-test" :title="t(\'orch_test_tip\')" @click.stop="testChain(id)">',
    '            {{ (testState[id] && testState[id].busy) ? t("prov_testing") : t("prov_test") }}',
    '          </button>',
    '          <span v-if="testState[id] && !testState[id].busy" class="orch-test-res"',
    '                :class="{ ok: testState[id].ok, err: testState[id].ok === false }" :title="testState[id].text">',
    '            {{ testState[id].text }}</span>',
    '          <span class="orch-move">',
    '            <button type="button" class="prov-act" :disabled="i === 0" :aria-label="t(\'orch_move_up\')" @click.stop="moveItem(i, -1)">↑</button>',
    '            <button type="button" class="prov-act" :disabled="i === chain.length - 1" :aria-label="t(\'orch_move_down\')" @click.stop="moveItem(i, 1)">↓</button>',
    '          </span>',
    '          <button v-if="breakerOf(id)" type="button" class="orch-cool"',
    '                  :title="t(\'orch_cool_reset_tip\')" @click.stop="resetBreaker(id)"><i></i>{{ t("health_cooldown") }}</button>',
    '          <button v-if="breakerOf(id)" type="button" class="qvq-link"',
    '                  @click="resetBreaker(id)">{{ t("breakers_reset") }}</button>',
    '        </div>',
    '        <div v-if="!chain.length" class="qvq-empty"><Mascot :size="30" mood="idle"/>{{ t("model_none") }}</div>',
    '      </div>',
    '    </n-card>',
    '    <n-card size="small" class="qvq-glass-card">',
    '      <div class="qvq-card-head"><span class="qvq-card-title">{{ t("orch_running") }}</span>',
    '        <button type="button" class="qvq-link" @click="QvQ.store.page = \'overview\'">{{ t("nav_overview") }}</button></div>',
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
    '        <button v-if="j.parent_chat_key" type="button" class="prov-act" :title="j.parent_chat_key"',
    '                @click="openParent(j)">{{ t("subjob_open_parent") }}</button>',
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
    '  <h3 class="plat-sec">{{ t("partic_title") }}</h3>',
    '  <n-card size="small" class="qvq-glass-card">',
    '    <div class="qvq-card-head">',
    '      <button type="button" class="qvq-link" @click="loadParticip">{{ t("refresh") }}</button>',
    '    </div>',
    '    <div class="qvq-meta-line" v-if="!particip">{{ t("loading") }}</div>',
    '    <template v-else>',
    '      <div class="qvq-meta-line">{{ t("partic_hint") }}</div>',
    '      <div class="partic-stats">',
    '        <span class="partic-chip" :class="{ on: particip.enabled }">{{ particip.enabled ? t("partic_on") : t("partic_off") }}</span>',
    '        <span class="partic-chip">{{ t("partic_strategy") }}: {{ particip.strategy }}</span>',
    '        <button type="button" class="partic-chip partic-chip-go" :title="t(\'partic_budget_go_tip\')"',
    '                @click="goUsageBudget">{{ t("partic_hourly") }} {{ (particip.budget.limits || {}).hourly_limit ?? "-" }}</button>',
    '        <button type="button" class="partic-chip partic-chip-go" :title="t(\'partic_budget_go_tip\')"',
    '                @click="goUsageBudget">{{ t("partic_today") }} {{ particip.budget.proactive_today ?? 0 }}/{{ (particip.budget.limits || {}).proactive_daily_limit ?? "-" }}</button>',
    '      </div>',
    '      <div v-for="(d, i) in (particip.decisions || []).slice(0, 12)" :key="i" class="trash-row">',
    '        <span class="nm">{{ d.chat_key }}</span>',
    '        <span class="qvq-meta-line">{{ participText(d) }}</span>',
    '      </div>',
    '      <div v-if="!(particip.decisions || []).length" class="qvq-empty">{{ t("partic_empty") }}</div>',
    '    </template>',
    '  </n-card>',
    '</div>',
  ].join(""),
};
