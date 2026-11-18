/* 定时任务：列表 / 下次执行 / 手动触发 / 新建与编辑 / 最近运行 */
window.PageTasks = {
  name: "PageTasks",
  data() {
    return {
      tasks: [],
      runs: [],
      drawer: false,
      isNew: true,
      form: {
        id: "", name: "", schedule: "", platform: "dashboard", target_type: "private",
        target_id: "web", prompt: "", persona: "", model: "",
      },
      formErr: "",
      busy: false,
      loading: false,
    };
  },
  mounted() {
    this.load();
  },
  methods: {
    taskLabel(tk) {
      return QvQ.taskLabel(tk);
    },
    load() {
      var self = this;
      return QvQ.swr(self, "tasks", "/api/qvq/tasks", function (d) {
        self.tasks = (d && d.tasks) || [];
        self.runs = ((d && d.runs) || []).slice(0, 20);
      });
    },
    openNew() {
      this.isNew = true;
      this.form = {
        id: "", name: "", schedule: "0 9 * * *", platform: "dashboard",
        target_type: "private", target_id: "web", prompt: "", persona: "", model: "",
      };
      this.formErr = "";
      this.drawer = true;
    },
    openEdit(task) {
      this.isNew = false;
      this.form = {
        id: task.id || "",
        name: task.name || "",
        schedule: task.schedule_raw || "",
        platform: task.platform || "dashboard",
        target_type: task.target_type || "private",
        target_id: task.target_id || "",
        prompt: task.prompt || "",
        persona: task.persona || "",
        model: task.model || "",
      };
      this.formErr = "";
      this.drawer = true;
    },
    save() {
      var self = this;
      this.busy = true;
      api("/api/qvq/tasks/save", "POST", this.form).then(function (r) {
        self.busy = false;
        if (r && r.error) {
          self.formErr = r.error;
          return;
        }
        self.drawer = false;
        self.load();
      });
    },
    runNow(task) {
      api("/api/qvq/tasks/run", "POST", { id: task.id }).then(function () {
        setTimeout(function () { window.location.hash = "#tasks"; }, 50);
      });
    },
    del(task) {
      var self = this;
      api("/api/qvq/tasks/delete", "POST", { id: task.id }).then(function () { self.load(); });
    },
  },
  template: [
    '<div class="qvq-page-body">',
    '  <div class="qvq-page-head">',
    '    <div>',
    '      <div class="qvq-page-title">{{ t("nav_tasks") }}</div>',
    '      <div class="qvq-page-sub">{{ tasks.length }} {{ t("stat_tasks") }}</div>',
    '    </div>',
    '    <n-button size="small" type="primary" @click="openNew">{{ t("add_title") }}</n-button>',
    '  </div>',
    '  <div class="prov-grid">',
    '    <article v-for="tk in tasks" :key="tk.id" class="prov-card">',
    '      <header class="prov-head">',
    '        <div class="prov-title">',
    '          <span class="prov-name">{{ taskLabel(tk) }}</span>',
    '          <span class="prov-id">{{ tk.id }}</span>',
    '        </div>',
    '      </header>',
    '      <div class="tool-desc">{{ tk.prompt }}</div>',
    '      <div class="plat-meta">',
    '        <span><code>{{ tk.schedule_raw }}</code></span>',
    '        <span>{{ tk.next_formatted }}</span>',
    '      </div>',
    '      <footer class="prov-foot">',
    '        <span class="prov-count">{{ tk.platform || "-" }}</span>',
    '        <span class="prov-acts">',
    '          <button type="button" class="prov-act" @click="runNow(tk)">{{ t("tasks_run_now") }}</button>',
    '          <button type="button" class="prov-act" @click="openEdit(tk)">{{ t("edit") }}</button>',
    '          <button type="button" class="prov-act danger" @click="del(tk)">{{ t("chat_delete") }}</button>',
    '        </span>',
    '      </footer>',
    '    </article>',
    '  </div>',
    '  <div class="qvq-loading" v-if="loading"><i></i>{{ t("loading") }}</div>',
    '  <div v-if="!loading && !tasks.length" class="qvq-empty">-</div>',
    '  <h3 class="plat-sec">{{ t("tasks_recent_runs") }}</h3>',
    '  <div v-for="(r, i) in runs" :key="i" class="trash-row">',
    '    <span class="nm">{{ r.name || r.task_id }}</span>',
    '    <span class="qvq-meta-line">{{ r.at_formatted }} · {{ r.status || r.ok === false ? (r.error || "ok") : "ok" }}</span>',
    '  </div>',
    '  <div v-if="!runs.length" class="qvq-empty">-</div>',
    '  <n-drawer v-model:show="drawer" :width="480" placement="right">',
    '    <n-drawer-content :title="isNew ? t(\'add_title\') : t(\'edit\')" closable>',
    '      <div class="prov-form">',
    '        <div class="prov-field">',
    '          <label>{{ t("models_name") }}</label>',
    '          <n-input v-model:value="form.name"/>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>Cron</label>',
    '          <n-input v-model:value="form.schedule" placeholder="0 9 * * *"/>',
    '        </div>',
    '        <div class="prov-grid2">',
    '          <div class="prov-field">',
    '            <label>platform</label>',
    '            <n-input v-model:value="form.platform"/>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>target_id</label>',
    '            <n-input v-model:value="form.target_id"/>',
    '          </div>',
    '        </div>',
    '        <div class="prov-field">',
    '          <label>prompt</label>',
    '          <n-input v-model:value="form.prompt" type="textarea" :rows="4"/>',
    '        </div>',
    '        <div class="cf-error" v-if="formErr">{{ formErr }}</div>',
    '      </div>',
    '      <template #footer>',
    '        <div class="qvq-modal-foot">',
    '          <n-button size="small" @click="drawer = false">{{ t("cancel") }}</n-button>',
    '          <n-button size="small" type="primary" :loading="busy" @click="save">{{ t("save") }}</n-button>',
    '        </div>',
    '      </template>',
    '    </n-drawer-content>',
    '  </n-drawer>',
    '</div>',
  ].join(""),
};
