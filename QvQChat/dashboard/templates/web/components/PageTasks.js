/* 定时任务：列表 / 下次执行 / 手动触发 / 新建与编辑 / 最近运行 */
window.PageTasks = {
  name: "PageTasks",
  data() {
    return {
      tasks: [],
      runs: [],
      drawer: false,
      isNew: true,
      schedMode: "cron",
      schedTime: "09:00",
      schedWeekday: 1,
      schedEvery: 30,
      schedUnit: "minute",
      form: {
        id: "", name: "", schedule: "", platform: "dashboard", target_type: "private",
        target_id: "web", prompt: "", persona: "", model: "",
      },
      formErr: "",
      busy: false,
      loading: false,
    };
  },
  computed: {
    weekdayOptions() {
      return [
        { label: t("sched_mon"), value: 1 },
        { label: t("sched_tue"), value: 2 },
        { label: t("sched_wed"), value: 3 },
        { label: t("sched_thu"), value: 4 },
        { label: t("sched_fri"), value: 5 },
        { label: t("sched_sat"), value: 6 },
        { label: t("sched_sun"), value: 0 },
      ];
    },
    unitOptions() {
      return [
        { label: t("sched_unit_min"), value: "minute" },
        { label: t("sched_unit_hour"), value: "hour" },
      ];
    },
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
    /* cron 双向友好化：每天/每周/每 N 单位 三种常见模式 ⇄ 表达式；识别不了回退 Cron 手填 */
    parseSchedule(raw) {
      var parts = String(raw || "").trim().split(/\s+/);
      if (parts.length !== 5) { this.schedMode = "cron"; return; }
      var m = parts;
      var star = function (x) { return x === "*" || x === "*/1"; };
      var pad = function (x) { return x.length < 2 ? "0" + x : x; };
      if (/^\d+$/.test(m[0]) && /^\d+$/.test(m[1]) && star(m[2]) && star(m[3]) && star(m[4])) {
        this.schedMode = "daily";
        this.schedTime = pad(m[1]) + ":" + pad(m[0]);
        return;
      }
      if (/^\d+$/.test(m[0]) && /^\d+$/.test(m[1]) && star(m[2]) && star(m[3]) && /^\d+$/.test(m[4])) {
        this.schedMode = "weekly";
        this.schedWeekday = Number(m[4]) % 7;
        this.schedTime = pad(m[1]) + ":" + pad(m[0]);
        return;
      }
      if (star(m[0]) && star(m[1]) && star(m[2]) && star(m[3]) && m[4].indexOf("*/") === 0) {
        this.schedMode = "every";
        this.schedEvery = Number(m[4].slice(2)) || 30;
        this.schedUnit = "minute";
        return;
      }
      if (star(m[0]) && star(m[1]) && star(m[2]) && m[3].indexOf("*/") === 0 && star(m[4])) {
        this.schedMode = "every";
        this.schedEvery = Number(m[3].slice(2)) || 2;
        this.schedUnit = "hour";
        return;
      }
      this.schedMode = "cron";
    },
    buildSchedule() {
      if (this.schedMode === "every") {
        return this.schedUnit === "minute"
          ? "*/" + Math.max(1, this.schedEvery) + " * * * *"
          : "0 */" + Math.max(1, this.schedEvery) + " * * *";
      }
      var hm = String(this.schedTime || "09:00").split(":");
      var hh = parseInt(hm[0], 10) || 0, mm = parseInt(hm[1], 10) || 0;
      if (this.schedMode === "daily") return mm + " " + hh + " * * *";
      if (this.schedMode === "weekly") return mm + " " + hh + " * * " + ((Number(this.schedWeekday) + 1) % 7);
      return String(this.form.schedule || "").trim();
    },
    openNew() {
      this.isNew = true;
      this.form = {
        id: "", name: "", schedule: "0 9 * * *", platform: "dashboard",
        target_type: "private", target_id: "web", prompt: "", persona: "", model: "",
      };
      this.parseSchedule("0 9 * * *");
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
      this.parseSchedule(task.schedule_raw || "");
      this.formErr = "";
      this.drawer = true;
    },
    save() {
      var self = this;
      this.busy = true;
      this.form.schedule = this.buildSchedule();
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
    '          <label>{{ t("sched_label") }}</label>',
    '          <n-radio-group v-model:value="schedMode" size="small">',
    '            <n-radio-button value="daily">{{ t("sched_daily") }}</n-radio-button>',
    '            <n-radio-button value="weekly">{{ t("sched_weekly") }}</n-radio-button>',
    '            <n-radio-button value="every">{{ t("sched_every") }}</n-radio-button>',
    '            <n-radio-button value="cron">Cron</n-radio-button>',
    '          </n-radio-group>',
    '        </div>',
    '        <div class="prov-field" v-if="schedMode === \'daily\' || schedMode === \'weekly\'">',
    '          <label>{{ t("sched_time") }}</label>',
    '          <n-input v-model:value="schedTime" placeholder="09:00" style="width:140px"/>',
    '        </div>',
    '        <div class="prov-field" v-if="schedMode === \'weekly\'">',
    '          <label>{{ t("sched_weekday") }}</label>',
    '          <n-select v-model:value="schedWeekday" :options="weekdayOptions" style="width:140px"/>',
    '        </div>',
    '        <div class="prov-grid2" v-if="schedMode === \'every\'">',
    '          <div class="prov-field">',
    '            <label>{{ t("sched_interval") }}</label>',
    '            <n-input-number v-model:value="schedEvery" :min="1" style="width:100%"/>',
    '          </div>',
    '          <div class="prov-field">',
    '            <label>{{ t("sched_unit") }}</label>',
    '            <n-select v-model:value="schedUnit" :options="unitOptions" style="width:100%"/>',
    '          </div>',
    '        </div>',
    '        <div class="prov-field" v-if="schedMode === \'cron\'">',
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
