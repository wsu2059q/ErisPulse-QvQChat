/* 管理视图：模型池/人格/技能/MCP/配置/用量等页面 */
  
  function fv(root, id) {
    var node = root.querySelector("#" + id);
    return node ? node.value.trim() : "";
  }

  function openForm(title, fieldsHtml, onSave) {
    var html = fieldsHtml +
      "<div class='qvq-actions'><button class='qvq-btn' data-form-save>" + esc(t("save")) + "</button>" +
      "<button class='qvq-btn ghost' data-form-cancel>" + esc(t("cancel")) + "</button></div>";
    openModal(title, html);
    var body = el("qvq-modal-body");
    body.querySelector("[data-form-cancel]").onclick = closeModal;
    body.querySelector("[data-form-save]").onclick = function () { onSave(body); };
  }

  /* ===== 编排页：模型链拖拽 / 健康面板 / 运行状态 / 任务时间线 / 能力开关 ===== */

  var orchChain = [];

  function loadOrchestrate() {
    api("/api/qvq/models").then(function (data) {
      orchChain = flattenChain(data || {});
      renderOrchChain();
    });
    api("/api/qvq/breakers").then(function (data) {
      renderModelHealth("qvq-orch-health", (data && data.breakers) || []);
    });
    api("/api/qvq/running").then(function (data) {
      renderRunning((data && data.running) || []);
    });
    api("/api/qvq/tasks").then(function (data) {
      renderTaskTimeline((data && data.tasks) || [], (data && data.runs) || [], "qvq-orch-timeline", true);
    });
    Promise.all([
      api("/api/qvq/tools"),
      api("/api/qvq/skills"),
      api("/api/qvq/mcp")
    ]).then(function (results) {
      renderOrchCaps(results[0] || {}, results[1] || {}, results[2] || {});
    });
  }

  // 链序是跨 provider 的全局顺序：优先后端 chain；旧数据回退到按 provider 展平
  function flattenChain(data) {
    if (data && Array.isArray(data.chain) && data.chain.length) {
      return data.chain.map(function (item) {
        return { provider: item.provider, name: item.name, base_url: item.base_url, model: item.model };
      });
    }
    var chain = [];
    ((data && data.providers) || []).forEach(function (p) {
      (p.models || []).forEach(function (m) {
        chain.push({ provider: p.id, name: p.name, base_url: p.base_url, model: m });
      });
    });
    return chain;
  }

  function renderOrchChain() {
    var box = el("qvq-orch-chain");
    if (!box) return;
    if (!orchChain.length) {
      box.innerHTML = '<div class="qvq-empty">' + esc(t("models_empty")) + "</div>";
      return;
    }
    box.innerHTML = '<div class="qvq-chain-list">' + orchChain.map(function (item, i) {
      var off = item.model.enabled === false;
      return '<div class="qvq-chain-row' + (off ? " off" : "") + '" draggable="true" data-ci="' + i + '">' +
        '<span class="qvq-chain-seq">' + (i + 1) + "</span>" +
        '<span class="qvq-chain-name">' + esc(item.provider + ":" + item.model.id) + "</span>" +
        (off ? "<span class='qvq-chip'>" + esc(t("off")) + "</span>" : "") +
        '<span class="qvq-q-drag" title="⇅">⇅</span></div>';
    }).join("") + "</div>";
    bindChainDrag(box);
  }

  function bindChainDrag(box) {
    var dragIndex = null;
    box.querySelectorAll(".qvq-chain-row").forEach(function (row) {
      row.addEventListener("dragstart", function (e) {
        dragIndex = parseInt(row.getAttribute("data-ci"), 10);
        if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
      });
      row.addEventListener("dragover", function (e) { e.preventDefault(); });
      row.addEventListener("drop", function (e) {
        e.preventDefault();
        var to = parseInt(row.getAttribute("data-ci"), 10);
        if (dragIndex === null || dragIndex === to) return;
        var moved = orchChain.splice(dragIndex, 1)[0];
        orchChain.splice(to, 0, moved);
        dragIndex = null;
        renderOrchChain();
        saveChainOrder();
      });
    });
  }

  // 整体链序一次提交；连续拖动时合并保存，避免并发请求乱序覆盖
  var chainSaveBusy = false;
  var chainSaveQueued = false;

  function saveChainOrder() {
    if (chainSaveBusy) {
      chainSaveQueued = true;
      return;
    }
    chainSaveBusy = true;
    var payload = {
      chain: orchChain.map(function (item) { return { provider: item.provider, model: item.model.id }; })
    };
    api("/api/qvq/chain/save", "POST", payload).then(function (data) {
      if (data && data.ok) {
        if (!chainSaveQueued) toast(t("orch_chain_saved"));
      } else {
        toast((data && data.error) || "error", true);
      }
    }, function () {
      toast("error", true);
    }).then(function () {
      chainSaveBusy = false;
      if (chainSaveQueued) {
        chainSaveQueued = false;
        saveChainOrder();
      }
    });
  }

  // 健康状态徽章：正常为右上角小绿标；有熔断时红标并附明细列表
  function renderModelHealth(boxId, breakers) {
    var box = el(boxId);
    if (!box) return;
    if (!breakers.length) {
      box.innerHTML = '<span class="qvq-health-badge ok"><i></i>' + esc(t("health_ok")) + "</span>";
      return;
    }
    box.innerHTML = '<span class="qvq-health-badge bad"><i></i>' + esc(t("health_cooldown")) + " × " + breakers.length + "</span>" +
      '<div class="qvq-health-list">' + breakers.map(function (b) {
        return '<div class="qvq-health-row"><b>' + esc(b.model) + "</b>" +
          "<span class='qvq-tool-desc'>" + esc(t("health_fails").replace("{n}", b.fails)) + " · " +
          esc(t("health_left").replace("{s}", b.cooldown_left)) + "</span></div>";
      }).join("") + "</div>";
  }

  function renderRunning(items) {
    var box = el("qvq-orch-running");
    if (!box) return;
    var live = items.filter(function (r) { return r.status === "running"; });
    if (!live.length) {
      box.innerHTML = '<div class="qvq-empty">' + esc(t("running_none")) + "</div>";
      return;
    }
    box.innerHTML = live.map(function (r) {
      return '<div class="qvq-tool-row"><span class="qvq-tool-name"><span class="qvq-chip o-eco">' + esc(t("steps_running")) + "</span> " +
        esc(r.session) + "</span><span class='qvq-tool-desc'>" + esc(r.text_head || "-") + "</span></div>";
    }).join("");
  }

  // 上半部分为定时任务（下次执行 + 最近状态），下半部分为最近执行记录
  // attentionOnly=true（编排页）：只显示需要关注的——上次失败/运行中的任务与出错的执行
  function renderTaskTimeline(tasks, runs, boxId, attentionOnly) {
    var box = el(boxId);
    if (!box) return;
    if (attentionOnly) {
      tasks = tasks.filter(function (task) {
        return task.last_status === "error" || task.last_status === "running";
      });
      runs = runs.filter(function (run) { return run.status === "error"; }).slice(0, 10);
    }
    var lines = tasks.map(function (task) {
      var status = task.last_status || "";
      var dot = status === "error" ? "err" : (status ? "ok" : "");
      var extra = "";
      if (status === "error") extra = " · <span class='qvq-tl-err'>" + esc(t("task_status_error")) + "</span>";
      else if (status === "running") extra = " · " + esc(t("steps_running"));
      return '<div class="qvq-tl-row"><span class="qvq-tl-dot ' + dot + '"></span>' +
        '<div class="qvq-tl-main"><b>' + esc(task.name || task.id) + "</b>" +
        "<div class='qvq-tool-desc'>" + esc(task.schedule_raw || "") +
        " · " + esc(t("task_next")) + " " + esc(task.next_formatted || "-") +
        (task.last_formatted ? " · " + esc(t("task_last")) + " " + esc(task.last_formatted) : "") +
        extra + "</div></div></div>";
    }).join("");
    var recent = runs.slice(0, 10).map(function (run) {
      return '<div class="qvq-tl-row mini"><span class="qvq-tl-dot ' + (run.status === "error" ? "err" : "ok") + '"></span>' +
        '<div class="qvq-tl-main"><span>' + esc(run.name || run.task_id) + "</span>" +
        "<div class='qvq-tool-desc'>" + esc(run.at_formatted || "") +
        (run.status === "error" && run.error ? " · " + esc(run.error) : "") + "</div></div></div>";
    }).join("");
    if (!lines && !recent) {
      box.innerHTML = '<div class="qvq-empty">' + esc(t("timeline_empty")) + "</div>";
      return;
    }
    box.innerHTML = '<div class="qvq-timeline">' + (lines || "") + (recent || "") + "</div>";
  }

  function renderOrchCaps(toolsData, skillsData, mcpData) {
    var box = el("qvq-orch-caps");
    if (!box) return;
    var tools = toolsData.tools || [];
    var disabled = toolsData.disabled || [];
    var skills = skillsData.skills || [];
    var servers = mcpData.servers || [];
    var clients = {};
    (mcpData.clients || []).forEach(function (c) { clients[c.name] = c; });

    var capRows = function (rows) {
      return '<div class="qvq-cap-flow">' + (rows || '<span class="qvq-tool-desc">-</span>') + "</div>";
    };
    var toolRows = tools.map(function (tool) {
      var off = disabled.indexOf(tool.name) >= 0;
      return '<label class="qvq-cap-chip' + (off ? " off" : "") + '">' +
        '<input type="checkbox" data-cap-tool="' + esc(tool.name) + '"' + (off ? "" : " checked") + "/>" +
        "<span>" + esc(tool.label || tool.name) + "</span></label>";
    }).join("");
    var skillRows = skills.map(function (sk) {
      return '<label class="qvq-cap-chip' + (sk.enabled === false ? " off" : "") + '">' +
        '<input type="checkbox" data-cap-skill="' + esc(sk.name) + '"' + (sk.enabled !== false ? " checked" : "") + "/>" +
        "<span>" + esc(sk.name) + "</span></label>";
    }).join("");
    var mcpRows = servers.map(function (srv) {
      var client = clients[srv.name];
      var connected = client && client.status === "connected";
      return '<label class="qvq-cap-chip' + (connected ? "" : " off") + '">' +
        '<input type="checkbox" data-cap-mcp="' + esc(srv.name) + '"' + (connected ? " checked" : "") + "/>" +
        "<span>" + esc(srv.name) + "</span></label>";
    }).join("");

    box.innerHTML =
      "<div class='qvq-cap-group'><div class='qvq-cap-head'>" + esc(t("caps_tools")) + " · " + tools.length + "</div>" +
      capRows(toolRows) + "</div>" +
      "<div class='qvq-cap-group'><div class='qvq-cap-head'>" + esc(t("caps_skills")) + " · " + skills.length + "</div>" +
      capRows(skillRows) + "</div>" +
      "<div class='qvq-cap-group'><div class='qvq-cap-head'>MCP · " + servers.length + "</div>" +
      capRows(mcpRows) + "</div>";

    box.querySelectorAll("input[data-cap-tool]").forEach(function (cb) {
      cb.onchange = function () {
        var name = cb.getAttribute("data-cap-tool");
        var set = disabled.slice();
        var idx = set.indexOf(name);
        if (cb.checked && idx >= 0) set.splice(idx, 1);
        if (!cb.checked && idx < 0) set.push(name);
        api("/api/qvq/config", "POST", { disabled_tools: set }).then(function (r) {
          if (r && r.errors && Object.keys(r.errors).length) {
            toast(t("settings_save_partial"), true);
          } else if (r && r.ok) {
            toast(t("saved"));
          } else {
            toast((r && r.error) || "error", true);
          }
        });
      };
    });
    box.querySelectorAll("input[data-cap-skill]").forEach(function (cb) {
      cb.onchange = function () {
        api("/api/qvq/skills/enabled", "POST", { name: cb.getAttribute("data-cap-skill"), enabled: cb.checked });
      };
    });
    box.querySelectorAll("input[data-cap-mcp]").forEach(function (cb) {
      cb.onchange = function () {
        var path = cb.checked ? "/api/qvq/mcp/connect" : "/api/qvq/mcp/disconnect";
        api(path, "POST", { name: cb.getAttribute("data-cap-mcp") });
      };
    });
  }

  function loadModels() {
    api("/api/qvq/breakers").then(function (data) {
      renderModelHealth("qvq-models-health", (data && data.breakers) || []);
    });
    api("/api/qvq/models").then(function (data) {
      var providers = (data && data.providers) || [];
      modelPresets = (data && data.presets) || [];
      if (!providers.length) {
        el("qvq-models-list").innerHTML = '<div class="qvq-empty qvq-empty-cta">' + esc(t("models_empty")) + "</div>";
        var cta = el("qvq-models-list").querySelector(".qvq-empty-cta");
        if (cta) cta.onclick = function () { openModelModal(null); };
        return;
      }
      var rows = providers.map(function (p) {
        var enabled = (p.models || []).filter(function (m) { return m.enabled !== false; });
        var names = enabled.map(function (m) { return esc(m.id); }).join("<br>") || "-";
        var firstModel = enabled.length ? String(enabled[0].id) : "";
        return "<tr><td><b>" + esc(p.name) + "</b><div class='qvq-tool-desc'>" + esc(p.base_url || "") + "</div></td>" +
          "<td>" + names + "</td>" +
          "<td>" + esc(p.api_key_masked || "-") + "</td>" +
          "<td><button class='qvq-btn small ghost' data-act='edit' data-id='" + esc(p.id) + "'>" + esc(t("edit")) + "</button> " +
          (firstModel ? "<button class='qvq-btn small ghost' data-act='test' data-model='" + esc(firstModel) + "'>" + esc(t("test")) + "</button> " : "") +
          "<button class='qvq-btn small danger' data-act='pdel' data-id='" + esc(p.id) + "'>" + esc(t("del")) + "</button></td></tr>";
      }).join("");
      el("qvq-models-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("models_name")) + "</th><th>" +
        esc(t("models_id")) + "</th><th>key</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      el("qvq-models-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var pid = btn.getAttribute("data-id");
          var act = btn.getAttribute("data-act");
          if (act === "pdel") {
            confirmDialog(t("confirm_del")).then(function (ok) {
              if (!ok) return;
              api("/api/qvq/providers/delete", "POST", { id: pid }).then(function () { toast(t("deleted")); loadModels(); });
            });
          } else if (act === "test") {
            btn.disabled = true;
            api("/api/qvq/models/test", "POST", { id: btn.getAttribute("data-model") }).then(function (r) {
              btn.disabled = false;
              if (r && r.ok) toast(t("model_test_ok") + " · " + (r.model || "") + " · " + r.ms + "ms");
              else toast((r && r.error) || t("model_test_fail"), true);
            });
          } else {
            var provider = providers.filter(function (pv) { return pv.id === pid; })[0];
            if (provider) openModelModal(provider);
          }
        };
      });
    });
  }

  function openModelModal(provider) {
    var editingId = provider && provider.id ? provider.id : "";
    var fields =
      "<label class='qvq-label'>" + esc(t("models_preset")) + "</label>" +
      "<select class='qvq-select' id='qvq-mf-preset'></select>" +
      "<label class='qvq-label'>" + esc(t("models_name")) + "</label>" +
      "<input class='qvq-input' id='qvq-mf-name' placeholder='deepseek-main' />" +
      "<label class='qvq-label'>" + esc(t("models_baseurl")) + "</label>" +
      "<input class='qvq-input' id='qvq-mf-url' placeholder='https://api.deepseek.com/v1' />" +
      "<label class='qvq-label'>" + esc(t("models_apikey")) + "</label>" +
      "<input class='qvq-input' id='qvq-mf-key' type='password' placeholder='sk-…' />" +
      "<label class='qvq-label'>" + esc(t("models_id")) + "</label>" +
      "<input class='qvq-input' id='qvq-mf-id' placeholder='deepseek-chat' />" +
      "<div class='qvq-actions' style='margin-top:10px'><button class='qvq-btn small ghost' id='qvq-mf-fetch' type='button'>" + esc(t("models_fetch")) + "</button></div>" +
      "<div id='qvq-mf-remote'></div>";
    openForm(editingId ? (provider.name || editingId) : t("models_add"), fields, function (body) {
      var payload = {
        id: editingId || fv(body, "qvq-mf-name").toLowerCase().replace(/[^a-z0-9-]/g, "-"),
        name: fv(body, "qvq-mf-name"),
        base_url: fv(body, "qvq-mf-url"),
        api_key: fv(body, "qvq-mf-key"),
        models: fv(body, "qvq-mf-id").split(",").map(function (x) { return x.trim(); }).filter(Boolean)
          .map(function (id) { return { id: id, enabled: true }; })
      };
      if (!payload.name || !payload.base_url) {
        toast(t("models_fetch_fail"), true);
        return;
      }
      api("/api/qvq/providers/save", "POST", payload).then(function (data) {
        if (data && data.ok) {
          toast(t("saved"));
          closeModal();
          loadModels();
        } else {
          toast((data && data.error) || "error", true);
        }
      });
    });
    var body = el("qvq-modal-body");
    var presetSel = body.querySelector("#qvq-mf-preset");
    presetSel.innerHTML = modelPresets.map(function (p) {
      return "<option value='" + esc(p.id) + "'>" + esc(p.name) + "</option>";
    }).join("");
    presetSel.value = "custom";
    presetSel.onchange = function () {
      var preset = modelPresets.filter(function (x) { return x.id === presetSel.value; })[0];
      if (!preset || preset.id === "custom") return;
      if (!body.querySelector("#qvq-mf-name").value.trim()) body.querySelector("#qvq-mf-name").value = preset.name || "";
      body.querySelector("#qvq-mf-url").value = preset.base_url || "";
    };
    if (provider) {
      body.querySelector("#qvq-mf-name").value = provider.name || "";
      body.querySelector("#qvq-mf-url").value = provider.base_url || "";
      body.querySelector("#qvq-mf-id").value = (provider.models || []).filter(function (m) { return m.enabled !== false; }).map(function (m) { return m.id; }).join(", ");
    }
    body.querySelector("#qvq-mf-fetch").onclick = function () {
      var btn = this;
      var base_url = fv(body, "qvq-mf-url");
      var api_key = fv(body, "qvq-mf-key");
      var box = body.querySelector("#qvq-mf-remote");
      if (!base_url) {
        toast(t("models_fetch_fail"), true);
        return;
      }
      btn.disabled = true;
      btn.textContent = t("models_fetching");
      box.innerHTML = "";
      api("/api/qvq/providers/remote-models", "POST", { base_url: base_url, api_key: api_key, id: editingId }).then(function (data) {
        btn.disabled = false;
        btn.textContent = t("models_fetch");
        if (data && data.error) {
          toast(data.error, true);
          return;
        }
        var models = (data && data.models) || [];
        if (!models.length) {
          box.innerHTML = "<div class='qvq-remote-list'><span class='qvq-tool-desc'>" + esc(t("models_remote_empty")) + "</span></div>";
          return;
        }
        box.innerHTML = "<div class='qvq-remote-list'>" + models.map(function (m) {
          var meta = [];
          if (m.context_length) meta.push(m.context_length + " ctx");
          if (m.vision) meta.push("vision");
          if (m.tool_call) meta.push("tools");
          return "<label><input type='checkbox' data-mid='" + esc(m.id) + "'/> <span>" + esc(m.id) + "</span>" +
            (meta.length ? "<span class='meta'>" + esc(meta.join(" · ")) + "</span>" : "") + "</label>";
        }).join("") + "</div>";
        box.querySelectorAll("input[data-mid]").forEach(function (cb) {
          cb.onchange = function () {
            var ids = [];
            box.querySelectorAll("input[data-mid]").forEach(function (c2) {
              if (c2.checked) ids.push(c2.getAttribute("data-mid"));
            });
            if (ids.length) body.querySelector("#qvq-mf-id").value = ids.join(", ");
          };
        });
      });
    };
  }

  function loadPersonas() {
    api("/api/qvq/personas").then(function (data) {
      var personas = (data && data.personas) || [];
      var rows = personas.map(function (p) {
        var chip = p.builtin ? " <span class='qvq-chip'>" + esc(t("personas_builtin")) + "</span>" : "";
        if (p.modified) chip += " <span class='qvq-chip o-eco'>" + esc(t("personas_modified")) + "</span>";
        var btns = "<button class='qvq-btn small ghost' data-act='edit' data-id='" + esc(p.id) + "'>" + esc(t("edit")) + "</button> ";
        if (!p.builtin || p.modified) {
          var delLabel = p.builtin ? t("personas_reset") : t("del");
          btns += "<button class='qvq-btn small danger' data-act='del' data-id='" + esc(p.id) + "'>" + esc(delLabel) + "</button>";
        }
        return "<tr><td><b>" + esc(p.id) + "</b>" + chip + "<div class='qvq-tool-desc'>" + esc((p.system || "").slice(0, 80)) + "…</div></td>" +
          "<td>" + esc(p.name || "") + "</td><td>" + btns + "</td></tr>";
      }).join("");
      var table = rows
        ? "<table class='qvq-table'><thead><tr><th>" + esc(t("col_id")) + "</th><th>" + esc(t("personas_pname")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>"
        : '<div class="qvq-empty">' + esc(t("personas_empty")) + "</div>";
      var options = personas.map(function (p) {
        return "<option value='" + esc(p.id) + "'>" + esc(p.id) + "</option>";
      }).join("");
      el("qvq-personas-list").innerHTML = table +
        "<h3 class='qvq-card-title' style='margin-top:14px'>" + esc(t("bindings")) + "</h3>" +
        "<div class='qvq-field-row'><input class='qvq-input' id='qvq-bind-key' placeholder='" + esc(t("bind_hint")) + "' />" +
        "<select class='qvq-select' id='qvq-bind-persona'>" + options + "</select>" +
        "<button class='qvq-btn small' id='qvq-bind-btn'>" + esc(t("bind_btn")) + "</button></div>";
      el("qvq-personas-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var id = btn.getAttribute("data-id");
          if (btn.getAttribute("data-act") === "del") {
            var isBuiltin = id === "assistant";
            confirmDialog(isBuiltin ? t("personas_reset") : t("confirm_del")).then(function (ok) {
              if (!ok) return;
              api("/api/qvq/personas/delete", "POST", { id: id }).then(function () {
                toast(isBuiltin ? t("personas_reset") : t("deleted"));
                loadPersonas();
              });
            });
          } else {
            var persona = personas.filter(function (p) { return p.id === id; })[0];
            if (persona) openPersonaModal(persona);
          }
        };
      });
      var bindBtn = el("qvq-bind-btn");
      if (bindBtn) {
        bindBtn.onclick = function () {
          var key = el("qvq-bind-key").value.trim();
          if (!key) return;
          api("/api/qvq/personas/bind", "POST", { chat_key: key, persona: el("qvq-bind-persona").value }).then(function () {
            toast(t("saved"));
            el("qvq-bind-key").value = "";
          });
        };
      }
    });
  }

  function openPersonaModal(persona) {
    var isEdit = !!persona;
    var fields =
      "<label class='qvq-label'>" + esc(t("personas_pid")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-id' placeholder='my_persona'" + (isEdit ? " readonly" : "") + " />" +
      "<label class='qvq-label'>" + esc(t("personas_pname")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-name' placeholder='QvQ' />" +
      "<label class='qvq-label'>" + esc(t("personas_system")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-pf-system'></textarea>" +
      "<label class='qvq-label'>" + esc(t("personas_tools")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-tools' placeholder='send_message, eco_*, remember' />";
    openForm(isEdit ? (persona.name || persona.id) : t("personas_new"), fields, function (body) {
      var payload = {
        id: fv(body, "qvq-pf-id"),
        name: fv(body, "qvq-pf-name"),
        system: body.querySelector("#qvq-pf-system").value,
        tools: fv(body, "qvq-pf-tools").split(",").map(function (x) { return x.trim(); }).filter(Boolean)
      };
      if (!payload.id) {
        toast(t("personas_pid"), true);
        return;
      }
      api("/api/qvq/personas/save", "POST", payload).then(function (data) {
        if (data && data.ok) {
          toast(t("saved"));
          closeModal();
          loadPersonas();
        } else {
          toast((data && data.error) || "error", true);
        }
      });
    });
    if (isEdit) {
      var body = el("qvq-modal-body");
      body.querySelector("#qvq-pf-id").value = persona.id || "";
      body.querySelector("#qvq-pf-name").value = persona.name || "";
      body.querySelector("#qvq-pf-system").value = persona.system || "";
      body.querySelector("#qvq-pf-tools").value = (persona.tools || []).join(", ");
    }
  }

  function loadSkills() {
    api("/api/qvq/skills").then(function (data) {
      var skills = (data && data.skills) || [];
      if (!skills.length) {
        el("qvq-skills-list").innerHTML = '<div class="qvq-empty qvq-empty-cta">' + esc(t("skills_empty")) + "</div>";
        var cta = el("qvq-skills-list").querySelector(".qvq-empty-cta");
        if (cta) cta.onclick = function () { openSkillModal(null); };
        return;
      }
      var rows = skills.map(function (sk) {
        var src = sk.source === "file" ? ".md" : "dashboard";
        var chk = sk.enabled !== false ? " checked" : "";
        return "<tr><td><b>" + esc(sk.name) + "</b><div class='qvq-tool-desc'>" + esc((sk.description || "").slice(0, 100)) + "</div></td>" +
          "<td><span class='qvq-chip'>" + esc(src) + "</span></td>" +
          "<td><input type='checkbox' data-toggle='" + esc(sk.name) + "'" + chk + "/></td>" +
          "<td><button class='qvq-btn small ghost' data-act='edit' data-name='" + esc(sk.name) + "'>" + esc(t("edit")) + "</button> " +
          "<button class='qvq-btn small danger' data-act='del' data-name='" + esc(sk.name) + "'>" + esc(t("del")) + "</button></td></tr>";
      }).join("");
      el("qvq-skills-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("skills_name")) + "</th><th>" + esc(t("skills_source")) +
        "</th><th>" + esc(t("on")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      el("qvq-skills-list").querySelectorAll("input[data-toggle]").forEach(function (cb) {
        cb.onchange = function () {
          api("/api/qvq/skills/enabled", "POST", { name: cb.getAttribute("data-toggle"), enabled: cb.checked }).then(function () {
            loadSkills();
          });
        };
      });
      el("qvq-skills-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var name = btn.getAttribute("data-name");
          if (btn.getAttribute("data-act") === "del") {
            confirmDialog(t("confirm_del")).then(function (ok) {
              if (!ok) return;
              api("/api/qvq/skills/delete", "POST", { name: name }).then(function () {
                toast(t("deleted"));
                loadSkills();
              });
            });
          } else {
            var skill = skills.filter(function (x) { return x.name === name; })[0];
            if (skill) openSkillModal(skill);
          }
        };
      });
    });
  }

  function openSkillModal(skill) {
    var isEdit = !!skill;
    var fields =
      "<label class='qvq-label'>" + esc(t("skills_name")) + "</label>" +
      "<input class='qvq-input' id='qvq-sf-name' placeholder='translate' />" +
      "<label class='qvq-label'>" + esc(t("skills_description")) + "</label>" +
      "<input class='qvq-input' id='qvq-sf-desc' placeholder='…' />" +
      "<label class='qvq-label'>" + esc(t("skills_body")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-sf-body' style='min-height:180px'></textarea>";
    openForm(isEdit ? skill.name : t("skills_add"), fields, function (body) {
      var name = fv(body, "qvq-sf-name");
      if (!name) return;
      api("/api/qvq/skills/save", "POST", {
        name: name,
        description: fv(body, "qvq-sf-desc"),
        body: body.querySelector("#qvq-sf-body").value
      }).then(function (data) {
        if (data && data.ok) {
          toast(t("saved"));
          closeModal();
          loadSkills();
        } else {
          toast((data && data.error) || "error", true);
        }
      });
    });
    if (isEdit) {
      var body = el("qvq-modal-body");
      body.querySelector("#qvq-sf-name").value = skill.name || "";
      body.querySelector("#qvq-sf-desc").value = skill.description || "";
      body.querySelector("#qvq-sf-body").value = skill.body || "";
    }
  }

  function loadTools() {
    api("/api/qvq/tools").then(function (data) {
      tools = (data && data.tools) || [];
      var riskLabel = (data && data.risk) || "risk";
      renderToolList(tools, "", riskLabel);
      var filter = el("qvq-tools-filter");
      filter.oninput = function () {
        renderToolList(tools, filter.value.trim().toLowerCase(), riskLabel);
      };
    });
    // 扩展模块小节并入工具页底部（原独立 tab 移除）
    loadExtensions();
  }

  function renderToolList(tools, keyword, riskLabel) {
    var shown = tools.filter(function (tool) {
      if (!keyword) return true;
      return tool.name.toLowerCase().indexOf(keyword) >= 0 || tool.label.toLowerCase().indexOf(keyword) >= 0 ||
        (tool.description || "").toLowerCase().indexOf(keyword) >= 0;
    });
    if (!shown.length) {
      el("qvq-tools-list").innerHTML = '<div class="qvq-empty">' + esc(t("tools_empty")) + "</div>";
      return;
    }
    el("qvq-tools-list").innerHTML = shown.map(function (tool) {
      var chips = "<span class='qvq-chip o-" + esc(tool.origin) + "'>" + esc(tool.origin_label || tool.origin) + "</span>" +
        (tool.danger ? "<span class='qvq-chip danger-chip'>" + esc(riskLabel) + "</span>" : "");
      return "<div class='qvq-tool-row'><span class='qvq-tool-name'>" + chips + " " + esc(tool.label) + "</span>" +
        "<span class='qvq-tool-desc'>" + esc(tool.description) + "</span></div>";
    }).join("");
  }

  function loadExtensions() {
    api("/api/qvq/extensions").then(function (data) {
      var exts = (data && data.extensions) || [];
      var body = exts.length
        ? "<table class='qvq-table'><thead><tr><th>" + esc(t("ext_module")) + "</th><th>" +
          esc(t("ext_personas_col")) + "</th><th>" + esc(t("ext_schemas_col")) + "</th></tr></thead><tbody>" +
          exts.map(function (e) {
            return "<tr><td><b>" + esc(e.module) + "</b></td><td>" + esc(e.personas) + "</td><td>" + esc(e.schemas) + "</td></tr>";
          }).join("") + "</tbody></table>"
        : '<div class="qvq-empty">' + esc(t("ext_none")) + "</div>";
      el("qvq-extensions-list").innerHTML = body;
    });
  }

  var mcpServers = [];

  function loadMcp() {
    api("/api/qvq/mcp").then(function (data) {
      mcpServers = (data && data.servers) || [];
      var clients = {};
      ((data && data.clients) || []).forEach(function (c) { clients[c.name] = c; });
      var body = mcpServers.length
        ? "<table class='qvq-table'><thead><tr><th>" + esc(t("models_name")) + "</th><th>" + esc(t("mcp_transport")) + "</th><th>" + esc(t("mcp_status_on")) +
          "</th><th>" + esc(t("tools")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" +
          mcpServers.map(function (srv) {
            var client = clients[srv.name];
            var status = client ? client.status : "disconnected";
            var tools = client ? (client.tools || 0) : 0;
            var connected = status === "connected";
            var detail = srv.transport === "http" ? (srv.url || "") : (srv.command || "");
            var action =
              "<button class='qvq-btn small " + (connected ? "danger" : "") + "' data-act='" + (connected ? "disc" : "conn") + "' data-name='" + esc(srv.name) + "'>" +
              esc(connected ? t("mcp_disconnect") : t("mcp_connect")) + "</button> " +
              "<button class='qvq-btn small ghost' data-act='medit' data-name='" + esc(srv.name) + "'>" + esc(t("edit")) + "</button> " +
              "<button class='qvq-btn small danger' data-act='mdel' data-name='" + esc(srv.name) + "'>" + esc(t("del")) + "</button>";
            return "<tr><td><b>" + esc(srv.name) + "</b><div class='qvq-tool-desc'>" + esc(detail) + "</div></td><td>" + esc(srv.transport || "-") + "</td>" +
              "<td><span class='qvq-chip " + (connected ? "o-eco" : "") + "'>" + esc(status) + "</span></td>" +
              "<td>" + tools + "</td><td>" + action + "</td></tr>";
          }).join("") + "</tbody></table>"
        : '<div class="qvq-empty qvq-empty-cta">' + esc(t("mcp_none")) + "</div>";
      el("qvq-mcp-list").innerHTML = body;
      if (!mcpServers.length) {
        var cta = el("qvq-mcp-list").querySelector(".qvq-empty-cta");
        if (cta) cta.onclick = function () { openMcpModal(null); };
      }
      el("qvq-mcp-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var act = btn.getAttribute("data-act");
          var name = btn.getAttribute("data-name");
          if (act === "conn" || act === "disc") {
            var path = act === "conn" ? "/api/qvq/mcp/connect" : "/api/qvq/mcp/disconnect";
            btn.disabled = true;
            api(path, "POST", { name: name }).then(function (r) {
              btn.disabled = false;
              if (r && r.error) { toast(r.error, true); }
              loadMcp();
            });
          } else if (act === "mdel") {
            confirmDialog(t("confirm_del")).then(function (ok) {
              if (!ok) return;
              api("/api/qvq/mcp/delete", "POST", { name: name }).then(function () {
                toast(t("deleted"));
                loadMcp();
              });
            });
          } else if (act === "medit") {
            var server = mcpServers.filter(function (srv) { return srv.name === name; })[0];
            if (server) openMcpModal(server);
          }
        };
      });
    });
    api("/api/qvq/tools").then(function (data) {
      var tools = ((data && data.tools) || []).filter(function (tl) { return tl.origin === "mcp"; });
      el("qvq-mcp-tools").innerHTML = tools.length
        ? tools.map(function (tool) {
            return "<div class='qvq-tool-row'><span class='qvq-tool-name'>" + esc(tool.name) + "</span>" +
              "<span class='qvq-tool-desc'>" + esc(tool.description) + "</span></div>";
          }).join("")
        : '<div class="qvq-empty">' + esc(t("tools_empty")) + "</div>";
    });
  }

  function openMcpModal(server) {
    var isEdit = !!server;
    var fields =
      "<label class='qvq-label'>" + esc(t("models_name")) + "</label>" +
      "<input class='qvq-input' id='qvq-cf-name' placeholder='filesystem' />" +
      "<label class='qvq-label'>" + esc(t("mcp_transport")) + "</label>" +
      "<select class='qvq-select' id='qvq-cf-transport'><option value='stdio'>stdio</option><option value='http'>http</option></select>" +
      "<div id='qvq-cf-stdio'>" +
      "<label class='qvq-label'>" + esc(t("mcp_command")) + "</label>" +
      "<input class='qvq-input' id='qvq-cf-command' placeholder='npx' />" +
      "<label class='qvq-label'>" + esc(t("mcp_args")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-cf-args' style='min-height:56px'></textarea>" +
      "</div>" +
      "<div id='qvq-cf-http'>" +
      "<label class='qvq-label'>URL</label>" +
      "<input class='qvq-input' id='qvq-cf-url' placeholder='http://127.0.0.1:9000/mcp' />" +
      "<label class='qvq-label'>" + esc(t("mcp_headers")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-cf-headers' style='min-height:56px'></textarea>" +
      "</div>" +
      "<label class='qvq-label'>timeout (s)</label>" +
      "<input class='qvq-input' id='qvq-cf-timeout' type='number' placeholder='30' />";
    openForm(isEdit ? server.name : t("mcp_add"), fields, function (body) {
      var name = fv(body, "qvq-cf-name");
      if (!name) {
        toast(t("mcp_name_required"), true);
        return;
      }
      var transport = fv(body, "qvq-cf-transport") || "stdio";
      var entry = { name: name, transport: transport };
      if (transport === "http") {
        entry.url = fv(body, "qvq-cf-url");
        var headersRaw = body.querySelector("#qvq-cf-headers").value.trim();
        if (headersRaw) {
          try { entry.headers = JSON.parse(headersRaw); } catch (e) { toast("invalid json", true); return; }
        }
      } else {
        entry.command = fv(body, "qvq-cf-command");
        entry.args = body.querySelector("#qvq-cf-args").value.split("\n").map(function (x) { return x.trim(); }).filter(Boolean);
      }
      var timeout = parseInt(fv(body, "qvq-cf-timeout"), 10);
      if (timeout > 0) entry.timeout = timeout;
      api("/api/qvq/mcp/save", "POST", entry).then(function (r) {
        if (r && r.error) toast(r.error, true);
        else toast(t("saved"));
        closeModal();
        loadMcp();
      });
    });
    var body = el("qvq-modal-body");
    var syncTransport = function () {
      var isHttp = body.querySelector("#qvq-cf-transport").value === "http";
      body.querySelector("#qvq-cf-stdio").style.display = isHttp ? "none" : "";
      body.querySelector("#qvq-cf-http").style.display = isHttp ? "" : "none";
    };
    body.querySelector("#qvq-cf-transport").onchange = syncTransport;
    if (isEdit) {
      body.querySelector("#qvq-cf-name").value = server.name || "";
      body.querySelector("#qvq-cf-transport").value = server.transport === "http" ? "http" : "stdio";
      body.querySelector("#qvq-cf-command").value = server.command || "";
      body.querySelector("#qvq-cf-args").value = (server.args || []).join("\n");
      body.querySelector("#qvq-cf-url").value = server.url || "";
      if (server.headers) body.querySelector("#qvq-cf-headers").value = JSON.stringify(server.headers, null, 2);
      if (server.timeout) body.querySelector("#qvq-cf-timeout").value = server.timeout;
    }
    syncTransport();
  }

  function loadTasks() {
    api("/api/qvq/tasks").then(function (data) {
      var tasks = (data && data.tasks) || [];
      renderTaskTimeline(tasks, (data && data.runs) || [], "qvq-tasks-timeline");
      if (!tasks.length) {
        el("qvq-tasks-list").innerHTML = '<div class="qvq-empty">' + esc(t("tasks_empty")) + "</div>";
        return;
      }
      var rows = tasks.map(function (task) {
        return "<tr><td><b>" + esc(task.name) + "</b><div class='qvq-tool-desc'>[" + esc(task.id) + "] " + esc(task.managed_by || "") + "</div></td>" +
          "<td>" + esc(task.schedule_raw) + "<div class='qvq-tool-desc'>" + esc(task.next_formatted || "") + "</div></td>" +
          "<td>" + esc(task.platform) + "/" + esc(task.target_type) + "/" + esc(task.target_id) + "</td>" +
          "<td>" + esc((task.prompt || "").slice(0, 60)) + "</td>" +
          "<td><button class='qvq-btn small danger' data-id='" + esc(task.id) + "'>" + esc(t("del")) + "</button></td></tr>";
      }).join("");
      el("qvq-tasks-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("models_name")) + "</th><th>" +
        esc(t("col_schedule")) + "</th><th>" + esc(t("col_target")) + "</th><th>" + esc(t("col_prompt")) + "</th><th>" +
        esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      el("qvq-tasks-list").querySelectorAll("button[data-id]").forEach(function (btn) {
        btn.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/tasks/delete", "POST", { id: btn.getAttribute("data-id") }).then(function () { toast(t("deleted")); loadTasks(); });
          });
        };
      });
    });
  }

  /* ===== 知识库：列表 / 检索 / 添加 / 删除 ===== */

  function loadKnowledge() {
    var query = (el("qvq-kb-search") || {}).value || "";
    api("/api/qvq/kb?q=" + encodeURIComponent(query.trim())).then(function (data) {
      var entries = (data && data.entries) || [];
      var stats = (data && data.stats) || {};
      var statsEl = el("qvq-kb-stats");
      if (statsEl) statsEl.textContent = t("kb_stats_line").replace("{e}", stats.entries || 0).replace("{c}", stats.chunks || 0);
      var box = el("qvq-kb-list");
      if (!box) return;
      if (!entries.length) {
        box.innerHTML = '<div class="qvq-empty">' + esc(t("kb_list_empty")) + "</div>";
        return;
      }
      box.innerHTML = entries.map(function (entry) {
        return '<div class="qvq-tool-row" data-kb="' + esc(entry.id) + '"><span class="qvq-tool-name">' + esc(entry.title) +
          (entry.source ? " <span class='qvq-chip'>" + esc(entry.source) + "</span>" : "") +
          (entry.triggers && entry.triggers.length ? " <span class='qvq-chip'>@" + esc(entry.triggers.join(", ")) + "</span>" : "") + "</span>" +
          "<span class='qvq-tool-desc'>" + esc((entry.content || "").slice(0, 160)) + "</span>" +
          "<button class='qvq-btn small danger' data-kb-del='" + esc(entry.id) + "'>" + esc(t("del")) + "</button></div>";
      }).join("");
      box.querySelectorAll("button[data-kb-del]").forEach(function (btn) {
        btn.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/kb/delete", "POST", { id: btn.getAttribute("data-kb-del") }).then(function () {
              toast(t("deleted"));
              loadKnowledge();
            });
          });
        };
      });
    });
    var search = el("qvq-kb-search");
    if (search && !search.dataset.bound) {
      search.dataset.bound = "1";
      var timer = null;
      search.oninput = function () {
        if (timer) clearTimeout(timer);
        timer = setTimeout(loadKnowledge, 300);
      };
    }
  }

  function openKnowledgeModal() {
    var fields =
      "<label class='qvq-label'>" + esc(t("kb_title_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbf-title' placeholder='…' />" +
      "<label class='qvq-label'>" + esc(t("kb_source_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbf-source' placeholder='doc / url / note' />" +
      "<label class='qvq-label'>" + esc(t("kb_triggers_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbf-triggers' placeholder='" + esc(t("kb_triggers_ph")) + "' />" +
      "<label class='qvq-label'>" + esc(t("kb_priority_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbf-priority' type='number' value='0' />" +
      "<label class='qvq-label'>" + esc(t("kb_cooldown_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbf-cooldown' type='number' min='0' value='' placeholder='30' />" +
      "<label class='qvq-label'>" + esc(t("kb_content_label")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-kbf-content' style='min-height:180px'></textarea>";
    openForm(t("kb_add"), fields, function (body) {
      var title = fv(body, "qvq-kbf-title");
      var content = body.querySelector("#qvq-kbf-content").value;
      if (!title.trim() || !content.trim()) {
        toast(t("kb_need_title_content"), true);
        return;
      }
      // 世界书：triggers 逗号/顿号/空白分隔，priority 数字（大优先），cooldown 空则用配置默认
      var triggers = fv(body, "qvq-kbf-triggers").split(/[,，、\s]+/).filter(Boolean);
      var priority = parseInt(fv(body, "qvq-kbf-priority"), 10) || 0;
      var cdRaw = parseInt(fv(body, "qvq-kbf-cooldown"), 10);
      var cooldownMin = isNaN(cdRaw) ? null : Math.max(0, cdRaw);
      api("/api/qvq/kb/add", "POST", { title: title, content: content, source: fv(body, "qvq-kbf-source"), triggers: triggers, priority: priority, cooldown_min: cooldownMin }).then(function (r) {
        if (r && r.ok) {
          toast(t("saved"));
          closeModal();
          loadKnowledge();
        } else {
          toast((r && r.error) || "error", true);
        }
      });
    });
  }

  function loadMemoryScopes() {
    api("/api/qvq/memory").then(function (data) {
      loadMemoryProfile(data);
      var scopes = (data && data.scopes) || [];
      var box = el("qvq-memory-scopes");
      if (!scopes.length) {
        box.innerHTML = '<div class="qvq-empty">' + esc(t("memory_empty")) + "</div>";
        return;
      }
      box.innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("col_chatkey")) + "</th><th>" + esc(t("col_count")) + "</th></tr></thead><tbody>" +
        scopes.map(function (scope) {
          return "<tr style='cursor:pointer' data-scope='" + esc(scope.chat_key) + "'><td>" + esc(scope.chat_key) + "</td><td>" + esc(scope.count) + "</td></tr>";
        }).join("") + "</tbody></table>";
      box.querySelectorAll("tr[data-scope]").forEach(function (row) {
        row.onclick = function () { openMemoryModal(row.getAttribute("data-scope")); };
      });
    });
  }

  // 用户画像卡（只读展示 + 清空按钮；数据随 /api/qvq/memory 响应返回）
  function loadMemoryProfile(data) {
    var section = document.querySelector(".qvq-tab[data-section='memory']");
    if (!section) return;
    var card = el("qvq-profile-card");
    if (!card) {
      var scopesCard = el("qvq-memory-scopes");
      var anchor = (scopesCard && scopesCard.parentElement) ? scopesCard.parentElement : null;
      card = document.createElement("div");
      card.className = "qvq-card";
      card.id = "qvq-profile-card";
      if (anchor && anchor.parentElement) {
        anchor.insertAdjacentElement("afterend", card);
      } else {
        section.appendChild(card);
      }
    }
    var user = (data && data.profile_user) || "";
    var profile = (data && data.profile) || {};
    var rows = [];
    [["traits", "T"], ["preferences", "P"], ["facts", "F"]].forEach(function (pair) {
      (profile[pair[0]] || []).forEach(function (item) {
        rows.push("<tr><td><span class='qvq-chip'>" + pair[1] + "</span> " + esc(item.text || "") + "</td></tr>");
      });
    });
    card.innerHTML = "<h2 class='qvq-h2'>" + esc(t("profile_card_title")) +
      (user ? " <span class='qvq-tool-desc'>" + esc(t("profile_card_user")) + ": " + esc(user) + "</span>" : "") + "</h2>" +
      "<div class='qvq-actions'><button class='qvq-btn small danger' id='qvq-profile-clear'>" + esc(t("profile_card_clear")) + "</button></div>" +
      (rows.length
        ? "<table class='qvq-table'><tbody>" + rows.join("") + "</tbody></table>"
        : '<div class="qvq-empty">' + esc(t("profile_card_empty")) + "</div>");
    var clearBtn = el("qvq-profile-clear");
    if (clearBtn) {
      clearBtn.onclick = function () {
        if (!user) return;
        confirmDialog(t("profile_card_confirm")).then(function (ok) {
          if (!ok) return;
          api("/api/qvq/profile/clear", "POST", { user_key: user }).then(function () {
            toast(t("deleted"));
            loadMemoryScopes();
          });
        });
      };
    }
  }

  function openMemoryModal(chatKey) {
    openModal(chatKey,
      '<div class="qvq-actions"><button class="qvq-btn small danger" id="qvq-memory-clear">' + esc(t("memory_clear")) + "</button></div>" +
      '<div id="qvq-memory-modal-list"><div class="qvq-empty">…</div></div>');
    el("qvq-memory-clear").onclick = function () {
      confirmDialog(t("confirm_del")).then(function (ok) {
        if (!ok) return;
        api("/api/qvq/memory/delete", "POST", { chat_key: chatKey }).then(function () {
          toast(t("deleted"));
          closeModal();
          loadMemoryScopes();
        });
      });
    };
    api("/api/qvq/memory?chat_key=" + encodeURIComponent(chatKey)).then(function (data) {
      var entries = (data && data.entries) || [];
      var list = el("qvq-memory-modal-list");
      if (!list) return;
      list.innerHTML = entries.length
        ? "<table class='qvq-table'><tbody>" + entries.map(function (entry) {
            return "<tr><td>[" + esc(entry.category) + "/" + esc(entry.importance) + "] " + esc(entry.content) +
              " <button class='qvq-btn small danger' data-content='" + esc(entry.content) + "'><svg viewBox='0 0 24 24' class='qvq-btn-ico'><path d='M6 6l12 12M18 6L6 18'/></svg></button></td></tr>";
          }).join("") + "</tbody></table>"
        : '<div class="qvq-empty">' + esc(t("memory_empty")) + "</div>";
      list.querySelectorAll("button[data-content]").forEach(function (btn) {
        btn.onclick = function () {
          api("/api/qvq/memory/delete", "POST", { chat_key: chatKey, content: btn.getAttribute("data-content") }).then(function () {
            toast(t("deleted"));
            openMemoryModal(chatKey);
            loadMemoryScopes();
          });
        };
      });
    });
  }

  function loadSessions() {
    api("/api/qvq/sessions").then(function (data) {
      var sessions = ((data && data.sessions) || []).filter(function (s) {
        return (s.turns || 0) > 0 || s.preview;
      });
      if (!sessions.length) {
        el("qvq-sessions-list").innerHTML = '<div class="qvq-empty">' + esc(t("sessions_empty")) + "</div>";
        return;
      }
      var rows = sessions.map(function (session) {
        return "<tr><td><b>" + esc(sessionDisplayName(session)) + "</b><div class='qvq-tool-desc'>" + esc(session.chat_key) + "</div></td>" +
          "<td>" + esc(session.persona || "-") + "</td>" +
          "<td>" + esc(session.turns) + "</td><td class='qvq-tool-desc'>" + esc(session.preview || "-") + "</td>" +
          "<td class='qvq-col-time'>" + esc(fmtTime(session.updated)) + "</td>" +
          "<td><button class='qvq-btn small ghost' data-view='" + esc(session.chat_key) + "'>" + esc(t("sessions_msgs")) + "</button> " +
          "<button class='qvq-btn small ghost' data-access='" + esc(session.chat_key) + "'>" + esc(t("sess_members")) + "</button> " +
          "<button class='qvq-btn small danger' data-key='" + esc(session.chat_key) + "'>" + esc(t("reset_btn")) + "</button></td></tr>";
      }).join("");
      el("qvq-sessions-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("col_chatkey")) + "</th><th>" + esc(t("col_persona")) +
        "</th><th>" + esc(t("col_turns")) + "</th><th>" + esc(t("col_preview")) + "</th><th>" + esc(t("col_updated")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      el("qvq-sessions-list").querySelectorAll("button[data-key]").forEach(function (btn) {
        btn.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/sessions/reset", "POST", { chat_key: btn.getAttribute("data-key") }).then(function () { toast(t("saved")); loadSessions(); });
          });
        };
      });
      el("qvq-sessions-list").querySelectorAll("button[data-view]").forEach(function (btn) {
        btn.onclick = function () { showSessionMessages(btn.getAttribute("data-view")); };
      });
      el("qvq-sessions-list").querySelectorAll("button[data-access]").forEach(function (btn) {
        btn.onclick = function () { openSessionAccessModal(btn.getAttribute("data-access")); };
      });
    });
  }

  // 会话准入：成员白名单（* 全员）+ 接受哪些其它会话的输入（跨会话共享）
  function openSessionAccessModal(chatKey) {
    var session = chatMeta.sessions.filter(function (s) { return s.chat_key === chatKey; })[0] || {};
    var fields =
      "<label class='qvq-label'>" + esc(t("sess_members_hint")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-saf-members' style='min-height:88px'>" + esc((session.members || ["*"]).join("\n")) + "</textarea>" +
      "<label class='qvq-label'>" + esc(t("sess_sources_hint")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-saf-sources' style='min-height:88px'>" + esc((session.sources || []).join("\n")) + "</textarea>";
    openForm(sessionDisplayName(session) || chatKey, fields, function (body) {
      var splitList = function (raw) {
        return raw.split(/[\n,，;；]+/).map(function (x) { return x.trim(); }).filter(Boolean);
      };
      var members = splitList(fv(body, "qvq-saf-members"));
      var sources = splitList(fv(body, "qvq-saf-sources"));
      api("/api/qvq/session/settings", "POST", { chat_key: chatKey, settings: { members: members } }).then(function () {
        return api("/api/qvq/session/routes", "POST", { target: chatKey, sources: sources });
      }).then(function () {
        toast(t("saved"));
        closeModal();
        loadSessions();
      });
    });
  }

  function showSessionMessages(chatKey) {
    var PAGE = 30;
    var rendered = 0;
    var total = 0;
    var msgs = [];
    openModal(chatKey, '<div class="qvq-chat-loading">' + HERO_SVG + '<span class="qvq-chat-loading-tx">QvQ Chat</span></div>');
    var body = el("qvq-modal-body");

    function rowHtml(m, i) {
      if (!m || typeof m !== "object") return "";
      var role = m.role || "user";
      var raw = contentText(m.content);
      var ops = '<div class="ops">' +
        '<button class="qvq-btn small ghost" data-copy="' + i + '">' + esc(t("copy")) + "</button>" +
        '<button class="qvq-btn small ghost" data-edit="' + i + '">' + esc(t("edit")) + "</button>" +
        '<button class="qvq-btn small danger" data-del="' + i + '">' + esc(t("del")) + "</button></div>";
      if (role === "user") {
        return '<div class="qvq-smsg me"><div class="content">' + esc(raw) + "</div>" + ops + "</div>";
      }
      if (role === "assistant") {
        var serial = m.rounds && m.rounds.length ? '<div class="qvq-rounds">' + renderSerial(roundsToItems(m.rounds)) + "</div>" : "";
        if (!serial) {
          var steps = traceToSteps(m.trace);
          serial = steps && steps.length ? '<div class="qvq-steps">' + steps.map(function (st) {
            var ms2 = st.end && st.end.ms != null ? (st.end.ms >= 1000 ? (st.end.ms / 1000).toFixed(1) + "s" : st.end.ms + "ms") : "";
            return '<div class="qvq-step"><div class="qvq-step-row" data-step-toggle="1"><span class="qvq-step-ico">' + STEP_ICON_SVG + "</span>" +
              '<span class="qvq-step-name">' + esc(st.start.name) + '</span><span class="qvq-step-args">' +
              esc(String(st.start.arguments || "").replace(/\s+/g, " ").slice(0, 60)) + '</span><span class="qvq-step-ms">' + esc(ms2) + "</span></div>" +
              (st.end && st.end.output ? '<pre class="qvq-step-detail">' + esc(st.end.output) + "</pre>" : "") + "</div>";
          }).join("") + "</div>" : "";
        }
        return '<div class="qvq-smsg bot"><div class="role-tag">AI</div>' + serial + '<div class="content">' +
          (mdRender(raw) || esc(raw)) + "</div>" + ops + "</div>";
      }
      return '<details class="qvq-smsg ctx"><summary>' + esc(role) + " · " + raw.length + " chars</summary><pre>" +
        esc(raw) + "</pre>" + ops + "</details>";
    }

    function bindRows() {
      bindMdCopy(body);
      bindStepToggles(body);
      body.querySelectorAll("button[data-copy]").forEach(function (btn) {
        btn.onclick = function () {
          var m = msgs[parseInt(btn.getAttribute("data-copy"), 10)];
          if (!m) return;
          copyText(contentText(m.content));
          var old = btn.textContent;
          btn.textContent = t("copied");
          setTimeout(function () { btn.textContent = old; }, 1200);
        };
      });
      body.querySelectorAll("button[data-del]").forEach(function (btn) {
        btn.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/session/messages/delete", "POST", { chat_key: chatKey, index: parseInt(btn.getAttribute("data-del"), 10) }).then(function () {
              showSessionMessages(chatKey);
              if (chatKey === chatSession) loadChatHistory();
            });
          });
        };
      });
      body.querySelectorAll("button[data-edit]").forEach(function (btn) {
        btn.onclick = function () {
          var idx = parseInt(btn.getAttribute("data-edit"), 10);
          var m = msgs[idx];
          var wrap = btn.closest(".qvq-smsg");
          if (!m || !wrap) return;
          var content = wrap.querySelector(".content, pre");
          if (!content) return;
          content.style.display = "none";
          btn.style.display = "none";
          wrap.querySelector(".ops").insertAdjacentHTML("afterbegin",
            "<textarea class='qvq-textarea' rows='3'>" + esc(contentText(m.content)) + "</textarea>" +
            "<button class='qvq-btn small' data-save='1'>" + esc(t("save")) + "</button>");
          wrap.querySelector("button[data-save]").onclick = function () {
            var val = wrap.querySelector("textarea").value;
            api("/api/qvq/session/context/edit", "POST", { chat_key: chatKey, index: idx, content: val }).then(function () {
              toast(t("saved"));
              showSessionMessages(chatKey);
              if (chatKey === chatSession) loadChatHistory();
            });
          };
        };
      });
    }

    function bindMore() {
      if (rendered >= total) return;
      body.addEventListener("scroll", function () {
        if (body.scrollTop + body.clientHeight >= body.scrollHeight - 80) {
          if (rendered < total) fetchPage(rendered);
        }
      });
    }

    function fetchPage(start) {
      api("/api/qvq/session/messages?chat_key=" + encodeURIComponent(chatKey) + "&start=" + start + "&limit=" + PAGE).then(function (data) {
        if ((data && data.error) || !data) {
          body.innerHTML = '<div class="qvq-empty">' + esc(data.error || "error") + "</div>";
          return;
        }
        total = (data && data.total) || 0;
        var batch = (data && data.messages) || [];
        if (start === 0) msgs = [];
        batch.forEach(function (m) { msgs.push(m); });
        rendered = msgs.length;
        var rowsHtml = msgs.map(function (m, i) { return rowHtml(m, i); }).join("");
        var summary = start === 0 ? ((data && data.summary) || "") : "";
        var summaryHtml = summary
          ? '<details class="qvq-smsg summary"><summary>' + esc(t("session_summary")) + "</summary><div class='content'>" + esc(summary) + "</div></details>"
          : "";
        var head = '<div class="qvq-smsg-head">' + esc(chatKey) + " · " +
          esc(t("msgs_count").replace("{n}", String(total))) + "</div>";
        var prevTop = body.scrollTop;
        body.innerHTML = head + summaryHtml + '<div data-smsg-rows>' + rowsHtml + "</div>";
        body.scrollTop = start === 0 ? 0 : prevTop;
        bindRows();
        bindMore();
      });
    }

    fetchPage(0);
  }

  var AUDIT_SUMMARY_KEYS = ["command", "code", "path", "file", "action", "query", "content", "name", "endpoint", "tool", "error"];

  function auditSummary(entry) {
    var d = entry.detail;
    if (d == null) return "-";
    if (typeof d === "string") return d.slice(0, 200);
    if (typeof d !== "object") return String(d);
    for (var i = 0; i < AUDIT_SUMMARY_KEYS.length; i++) {
      var v = d[AUDIT_SUMMARY_KEYS[i]];
      if (v != null && v !== "") {
        var s = AUDIT_SUMMARY_KEYS[i] + ": " + (typeof v === "object" ? JSON.stringify(v) : String(v));
        return s.length > 200 ? s.slice(0, 200) + "…" : s;
      }
    }
    var first = "";
    Object.keys(d).some(function (k) {
      var v2 = d[k];
      if (v2 != null && v2 !== "") {
        first = k + ": " + (typeof v2 === "object" ? JSON.stringify(v2) : String(v2));
        return true;
      }
      return false;
    });
    if (first.length > 200) first = first.slice(0, 200) + "…";
    return first || "-";
  }

  function showAuditModal(entry) {
    var detail = entry.detail;
    var jsonText;
    try {
      jsonText = typeof detail === "string" ? detail : JSON.stringify(detail == null ? {} : detail, null, 2);
    } catch (e) {
      jsonText = String(detail);
    }
    var html =
      "<div class='qvq-kv'>" +
      "<div class='k'>" + esc(t("col_time")) + "</div><div class='v'>" + esc(fmtTimeFull(entry.ts)) + "</div>" +
      "<div class='k'>" + esc(t("col_tool")) + "</div><div class='v'><b>" + esc(entry.tool) + "</b></div>" +
      "<div class='k'>" + esc(t("col_user")) + "</div><div class='v'>" + esc(entry.user_id || "-") + "</div>" +
      "<div class='k'>" + esc(t("col_origin")) + "</div><div class='v'>" + esc(entry.origin || "-") + "</div>" +
      "<div class='k'>" + esc(t("col_chatkey")) + "</div><div class='v'>" + esc(entry.chat_key || "-") + "</div>" +
      "</div>" +
      "<pre class='qvq-json'>" + esc(jsonText) + "</pre>" +
      "<div class='qvq-actions'><button class='qvq-btn small' id='qvq-audit-copy'>" + esc(t("audit_copy")) + "</button></div>";
    openModal(t("col_detail") + " · " + (entry.tool || ""), html);
    el("qvq-audit-copy").onclick = function () {
      var text = typeof detail === "string" ? detail : JSON.stringify(detail == null ? {} : detail, null, 2);
      var done = function () { toast(t("audit_copied")); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
        done();
      }
    };
  }

  function loadAudit() {
    api("/api/qvq/audit?limit=500").then(function (data) {
      var entries = (data && data.entries) || [];
      var filter = el("qvq-audit-filter");
      var tools = {};
      var users = {};
      var last24 = 0;
      var cutoff = Date.now() / 1000 - 86400;
      entries.forEach(function (e) {
        if (e.tool) tools[e.tool] = (tools[e.tool] || 0) + 1;
        if (e.user_id) users[e.user_id] = (users[e.user_id] || 0) + 1;
        if ((e.ts || 0) >= cutoff) last24++;
      });
      var cards = [
        { cap: t("audit_total"), num: entries.length },
        { cap: t("audit_tools_n"), num: Object.keys(tools).length },
        { cap: t("audit_users_n"), num: Object.keys(users).length },
        { cap: t("audit_last24h"), num: last24 }
      ];
      el("qvq-audit-stats").innerHTML = cards.map(function (c) {
        return '<div class="qvq-stat"><div class="num">' + esc(c.num) + '</div><div class="cap">' + esc(c.cap) + "</div></div>";
      }).join("");
      var render = function (keyword) {
        var shown = entries.filter(function (e) {
          if (!keyword) return true;
          return (e.tool || "").toLowerCase().indexOf(keyword) >= 0 ||
            (e.user_id || "").indexOf(keyword) >= 0 ||
            (e.origin || "").toLowerCase().indexOf(keyword) >= 0 ||
            JSON.stringify(e.detail || {}).toLowerCase().indexOf(keyword) >= 0;
        });
        if (!shown.length) {
          el("qvq-audit-list").innerHTML = '<div class="qvq-empty">' + esc(t("audit_empty")) + "</div>";
          return;
        }
        var rows = shown.map(function (entry, idx) {
          return "<tr class='qvq-audit-row' data-idx='" + idx + "'>" +
            "<td class='qvq-col-time'>" + esc(fmtTime(entry.ts)) + "</td>" +
            "<td><b>" + esc(entry.tool) + "</b></td>" +
            "<td>" + esc(entry.user_id || "-") + "</td>" +
            "<td>" + esc(entry.origin || "-") + "</td>" +
            "<td class='qvq-tool-desc qvq-audit-detail'>" + esc(auditSummary(entry)) + "</td></tr>";
        }).join("");
        el("qvq-audit-list").innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("col_time")) + "</th><th>" + esc(t("col_tool")) +
          "</th><th>" + esc(t("col_user")) + "</th><th>" + esc(t("col_origin")) + "</th><th>" + esc(t("col_detail")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
        el("qvq-audit-list").querySelectorAll("tr.qvq-audit-row").forEach(function (tr) {
          tr.onclick = function () {
            var entry = shown[parseInt(tr.getAttribute("data-idx"), 10)];
            if (entry) showAuditModal(entry);
          };
        });
      };
      filter.oninput = function () { render(filter.value.trim().toLowerCase()); };
      render(filter.value.trim().toLowerCase());
    });
  }

  var settingsFields = [];
  var settingsGroupsTable = [];
  var settingsOriginal = {};   // key → 加载时的规范化值（dirty 基准）
  var settingsDraft = {};      // key → 当前编辑值（跨分类切换/搜索重绘保留）
  var settingsEnums = { tools: [], skills: [] };
  var settingsEventsBound = false;
  // 插件设置（qvq_settings 注册项）：独立拉取后并入统一 schema（key 加前缀防跨插件撞名）
  var settingsConfigFields = [];
  var settingsPluginFields = [];
  var PLUGIN_KEY_PREFIX = "plugin:";

  // chat 组语义分块（字段 order 上界 → 小节标题键）
  var CHAT_SECTIONS = [
    { max: 9, key: "settings_sec_context" },
    { max: 13, key: "settings_sec_forward" },
    { max: 16, key: "settings_sec_reply" },
    { max: 19, key: "settings_sec_flow" },
    { max: 999, key: "settings_sec_misc" }
  ];

  function settingsSchemaOf(key) {
    for (var i = 0; i < settingsFields.length; i++) {
      if (settingsFields[i].key === key) return settingsFields[i];
    }
    return null;
  }

  function loadSettings() {
    bindSettingsSearch();
    bindSettingsFormEvents();
    api("/api/qvq/config").then(function (data) {
      if (!data || data.error || !Array.isArray(data.fields)) return;
      settingsConfigFields = data.fields;
      settingsGroupsTable = data.groups || [];
      applySettingsState();
      loadSettingsEnums();
    });
    api("/api/qvq/plugin_settings").then(function (data) {
      settingsPluginFields = mapPluginSettings((data && data.modules) || []);
      applySettingsState();
    });
  }

  // 合并 QvQChat 配置字段与插件设置字段为统一 schema（draft/dirty/保存机制共用）
  function applySettingsState() {
    settingsFields = settingsConfigFields.concat(settingsPluginFields);
    settingsOriginal = {};
    settingsFields.forEach(function (f) {
      settingsOriginal[f.key] = settingsNormalize(f, f.value);
    });
    settingsDraft = {};
    Object.keys(settingsOriginal).forEach(function (k) {
      settingsDraft[k] = settingsOriginal[k];
    });
    renderSettingsCategories();
    renderSettingsForm();
  }

  // 插件设置字段映射为 settingField 现有形状：{key,type,widget,options,secret,placeholder,dangerous,description,value}
  // 数据源为框架 resolve_config_schema 输出：schema.fields[name] = {type(integer/float/boolean/array/table/string),
  // description, required, secret, default, widget?, group?, order?, options?, placeholder?}；values = sdk.config 现值
  function mapPluginSettings(modules) {
    var TYPE_MAP = { integer: "int", float: "float", boolean: "bool", array: "list", table: "dict", string: "str" };
    var fields = [];
    (modules || []).forEach(function (m, mi) {
      var schemaFields = (m.schema && m.schema.fields) || {};
      var values = m.values || {};
      var names = Object.keys(schemaFields).map(function (n) {
        return { name: n, fs: schemaFields[n] };
      });
      names.sort(function (a, b) {
        var oa = a.fs && a.fs.order != null ? a.fs.order : 999;
        var ob = b.fs && b.fs.order != null ? b.fs.order : 999;
        return oa - ob;
      });
      names.forEach(function (pair, i) {
        var it = pair.fs || {};
        var opts = null;
        if (Array.isArray(it.options) && it.options.length) {
          opts = it.options.map(function (o) { return (o && typeof o === "object") ? o.value : o; });
        }
        fields.push({
          key: PLUGIN_KEY_PREFIX + m.module + ":" + pair.name,
          plugin_module: m.module,
          plugin_title: m.title || m.module,
          type: TYPE_MAP[it.type] || "str",
          widget: it.widget || "text",
          options: opts,
          secret: !!it.secret,
          required: !!it.required,
          placeholder: it.placeholder || null,
          dangerous: false,
          description: it.description || pair.name,
          value: values[pair.name],
          group: "plugin",
          order: mi * 1000 + (it.order != null ? it.order : i + 1)
        });
      });
    });
    return fields;
  }

  // disabled_tools / skills_disabled 的 checkbox 多选数据源
  function loadSettingsEnums() {
    var need = { tools: false, skills: false };
    settingsFields.forEach(function (f) {
      if (f.items && f.items in need) need[f.items] = true;
    });
    if (need.tools) {
      api("/api/qvq/tools").then(function (data) {
        settingsEnums.tools = ((data && data.tools) || []).map(function (tl) { return tl.name; });
        refreshSettingsChecks("tools");
      });
    }
    if (need.skills) {
      api("/api/qvq/skills").then(function (data) {
        settingsEnums.skills = ((data && data.skills) || []).map(function (sk) { return sk.name; });
        refreshSettingsChecks("skills");
      });
    }
  }

  function refreshSettingsChecks(source) {
    var box = el("qvq-settings-form");
    if (!box) return;
    box.querySelectorAll("[data-checks]").forEach(function (node) {
      var f = settingsSchemaOf(node.getAttribute("data-key"));
      if (f && f.items === source) {
        node.innerHTML = settingsChecksHtml(f, settingsDraft[f.key]);
      }
    });
  }

  function settingsNormalize(f, value) {
    var type = f.type || "str";
    if (type === "int" || type === "float") {
      var n = Number(value);
      return value === null || value === "" || value === undefined || isNaN(n) ? String(value == null ? "" : value) : n;
    }
    if (type === "list") {
      return Array.isArray(value)
        ? value.map(function (x) { return String(x).trim(); }).filter(Boolean)
        : String(value == null ? "" : value);
    }
    if (type === "bool") return !!value;
    if (type === "dict") return value && typeof value === "object" ? value : {};
    return String(value == null ? "" : value);
  }

  function settingsGroups() {
    // 优先用后端 GROUP_META 组表（组序与字段 order 解耦），无则回退字段推导
    var groups;
    if (settingsGroupsTable.length) {
      groups = settingsGroupsTable.map(function (g) { return g.id; });
    } else {
      groups = [];
      settingsFields.forEach(function (f) {
        if (groups.indexOf(f.group) < 0) groups.push(f.group);
      });
    }
    // "插件"分区恒置末位（有插件注册项才出现）
    if (settingsPluginFields.length && groups.indexOf("plugin") < 0) groups.push("plugin");
    return groups;
  }

  function renderSettingsCategories() {
    var nav = el("qvq-settings-cats");
    if (!nav) return;
    var groups = settingsGroups();
    if (!currentCategory || groups.indexOf(currentCategory) < 0) currentCategory = groups[0] || "";
    nav.innerHTML = groups.map(function (g) {
      var label = t("group_" + g);
      if (label === "group_" + g) label = g;
      return "<button class='qvq-cat-btn" + (g === currentCategory ? " active" : "") + "' data-cat='" + esc(g) + "'>" + esc(label) + "</button>";
    }).join("");
    nav.querySelectorAll("button[data-cat]").forEach(function (btn) {
      btn.onclick = function () { switchSettingsCategory(btn.getAttribute("data-cat")); };
    });
  }

  function switchSettingsCategory(g) {
    if (g === currentCategory) return;
    var apply = function () {
      currentCategory = g;
      renderSettingsCategories();
      renderSettingsForm();
    };
    if (settingsDirtyKeys().length) {
      confirmDialog(t("settings_unsaved")).then(function (ok) { if (ok) apply(); });
    } else {
      apply();
    }
  }

  function bindSettingsSearch() {
    var search = el("qvq-settings-search");
    if (!search || search.dataset.bound) return;
    search.dataset.bound = "1";
    var timer = null;
    search.oninput = function () {
      if (timer) clearTimeout(timer);
      timer = setTimeout(renderSettingsForm, 200);
    };
  }

  function settingsSearchQuery() {
    var node = el("qvq-settings-search");
    return node ? node.value.trim().toLowerCase() : "";
  }

  function settingsChecksHtml(f, value) {
    var current = Array.isArray(value) ? value.slice() : [];
    var known = (settingsEnums[f.items] || []).slice();
    // 枚举外的存量值（如 eco_* 通配）同样列出，取消勾选即可移除
    current.forEach(function (v) {
      if (known.indexOf(v) < 0) known.push(v);
    });
    if (!known.length) return "<span class='qvq-tool-desc'>-</span>";
    return known.map(function (name) {
      var on = current.indexOf(name) >= 0;
      return "<label class='qvq-check-row'><input type='checkbox' data-val='" + esc(name) + "'" + (on ? " checked" : "") + "/><span>" + esc(name) + "</span></label>";
    }).join("");
  }

  function settingsListEditorHtml(key, value) {
    var items = Array.isArray(value) ? value : (value == null || value === "" ? [] : [String(value)]);
    var rows = items.map(function (item) {
      return "<div class='qvq-list-row'><input class='qvq-input' data-item='1' value='" + esc(item) + "' />" +
        "<button type='button' class='qvq-btn small ghost' data-list-del='1' title='" + esc(t("del")) + "'>×</button></div>";
    }).join("");
    return "<div class='qvq-list-editor' data-key='" + esc(key) + "' data-list='1'>" + rows +
      "<button type='button' class='qvq-btn small ghost' data-list-add='1'>+ " + esc(t("settings_list_add")) + "</button></div>";
  }

  // T3 表单分发：按 schema 类型/_widget 渲染，值取 settingsDraft（保留编辑中状态）
  function settingField(f) {
    var key = esc(f.key);
    var value = (f.key in settingsDraft) ? settingsDraft[f.key] : f.value;
    var widget = f.widget || "text";
    var type = f.type || "str";
    var head = "<label class='qvq-label'>" + esc(f.description || f.key) +
      " <span class='qvq-key-tag'>" + esc(f.key) + "</span>" +
      (f.dangerous ? " <span class='qvq-danger-tag'>" + esc(t("settings_dangerous")) + "</span>" : "") +
      "</label>";
    var input;

    if (type === "bool" || widget === "switch") {
      input = "<span class='qvq-switch' data-key='" + key + "' data-bool='1'><input type='checkbox'" + (value ? " checked" : "") + "/><i></i></span>";
    } else if (widget === "select" && f.options && f.options.length) {
      input = "<select class='qvq-select' data-key='" + key + "'>" + f.options.map(function (o) {
        return "<option value='" + esc(o) + "'" + (o === value ? " selected" : "") + ">" + esc(o) + "</option>";
      }).join("") + "</select>";
    } else if (widget === "lines") {
      var lines = Array.isArray(value) ? value.join("\n") : String(value == null ? "" : value);
      input = "<textarea class='qvq-textarea' style='min-height:80px' data-key='" + key + "' data-lines='1' placeholder='line1&#10;line2'>" + esc(lines) + "</textarea>";
    } else if (type === "list") {
      input = f.items
        ? "<div class='qvq-list-checks' data-key='" + key + "' data-list='1' data-checks='1'>" + settingsChecksHtml(f, value) + "</div>"
        : settingsListEditorHtml(f.key, value);
    } else if (widget === "slider" && (type === "int" || type === "float")) {
      var sv = Number(value);
      var svOk = value !== "" && value != null && !isNaN(sv);
      var sAttrs = "min='" + esc(f.min != null ? f.min : 0) + "' max='" + esc(f.max != null ? f.max : 100) + "' step='" + esc(f.step != null ? f.step : (type === "int" ? 1 : 0.1)) + "'";
      input = "<div class='qvq-slider-row' data-key='" + key + "' data-slider-wrap='1'>" +
        "<input type='range' data-slider='1' value='" + esc(svOk ? sv : (f.min != null ? f.min : 0)) + "' " + sAttrs + "/>" +
        "<input class='qvq-input' type='number' data-num='1' value='" + esc(svOk ? sv : "") + "' " + sAttrs + "/>" +
        "</div>" +
        (svOk ? "" : "<div class='qvq-field-err show'>" + esc(t("settings_invalid_value")) + "</div>");
    } else if (type === "int" || type === "float" || widget === "number") {
      var nv = Number(value);
      var nvOk = value !== "" && value != null && typeof value !== "boolean" && !isNaN(nv);
      if (nvOk) {
        var nAttrs = "";
        if (f.min != null) nAttrs += " min='" + esc(f.min) + "'";
        if (f.max != null) nAttrs += " max='" + esc(f.max) + "'";
        if (f.step != null) nAttrs += " step='" + esc(f.step) + "'";
        input = "<input class='qvq-input' type='number' data-key='" + key + "' value='" + esc(nv) + "'" + nAttrs + " />";
      } else {
        // 存量已写坏的数字字段：容错显示原文 + 红字提示，保存由后端校验拒收
        input = "<input class='qvq-input qvq-input-bad' type='text' data-key='" + key + "' value='" + esc(value == null ? "" : value) + "' />" +
          "<div class='qvq-field-err show'>" + esc(t("settings_invalid_value")) + "</div>";
      }
    } else if (f.secret || widget === "password") {
      input = "<div class='qvq-pw-row' data-key='" + key + "' data-pw-row='1'>" +
        "<input class='qvq-input' type='password' data-pw-input='1' value='" + esc(value == null ? "" : value) + "' autocomplete='new-password' />" +
        "<button type='button' class='qvq-btn small ghost' data-pw-toggle='1'>" + esc(t("settings_show")) + "</button></div>";
    } else if (type === "dict" || (value && typeof value === "object")) {
      var jsonText;
      try {
        jsonText = JSON.stringify(value == null ? {} : value, null, 2);
      } catch (e) {
        jsonText = String(value);
      }
      input = "<textarea class='qvq-textarea qvq-mono' style='min-height:90px' data-key='" + key + "' data-json='1'>" + esc(jsonText) + "</textarea>";
    } else {
      var ph = f.placeholder ? " placeholder='" + esc(f.placeholder) + "'" : "";
      input = "<input class='qvq-input' data-key='" + key + "' value='" + esc(value == null ? "" : value) + "'" + ph + " />";
    }
    return "<div class='qvq-field' data-field='" + key + "'>" + head + input +
      "<div class='qvq-field-err' data-err='" + key + "'></div></div>";
  }

  function renderSettingsForm() {
    settingsCaptureDraft();  // 重绘前收编当前 DOM 值进 draft，编辑不因切换/搜索丢失
    var box = el("qvq-settings-form");
    if (!box) return;
    var q = settingsSearchQuery();
    var fields;
    if (q) {
      fields = settingsFields.filter(function (f) {
        return f.key.toLowerCase().indexOf(q) >= 0 || String(f.description || "").toLowerCase().indexOf(q) >= 0;
      });
    } else {
      fields = settingsFields.filter(function (f) { return f.group === currentCategory; });
      fields.sort(function (a, b) { return (a.order || 99) - (b.order || 99); });
    }
    if (!fields.length) {
      var emptyText = q ? t("settings_no_match")
        : (currentCategory === "plugin" ? t("plugin_settings_empty") : "-");
      box.innerHTML = '<div class="qvq-empty">' + esc(emptyText) + "</div>";
      settingsUpdateSaveBtn();
      return;
    }
    var html = "";
    var lastSec = -1;
    var lastPlugin = "";
    fields.forEach(function (f) {
      if (q) {
        html += "<div class='qvq-settings-hit'><span class='qvq-chip'>" + esc(t("group_" + f.group)) + "</span>" + settingField(f) + "</div>";
        return;
      }
      if (f.group === "chat") {
        for (var si = 0; si < CHAT_SECTIONS.length; si++) {
          if ((f.order || 99) <= CHAT_SECTIONS[si].max) {
            if (si !== lastSec) {
              html += "<div class='qvq-settings-sec'>" + esc(t(CHAT_SECTIONS[si].key)) + "</div>";
              lastSec = si;
            }
            break;
          }
        }
      }
      if (f.group === "plugin" && f.plugin_module !== lastPlugin) {
        html += "<div class='qvq-settings-sec'>" + esc(f.plugin_title || f.plugin_module) + "</div>";
        lastPlugin = f.plugin_module;
      }
      html += settingField(f);
    });
    box.innerHTML = html;
    settingsUpdateSaveBtn();
  }

  // 按字段 schema 类型从 DOM 读值（保存与 dirty 检测共用）
  function settingsSerializeField(node, f) {
    if (f.type === "bool") {
      var cb = node.querySelector("input[type='checkbox']");
      return !!(cb && cb.checked);
    }
    if (node.hasAttribute("data-list")) {
      if (node.hasAttribute("data-checks")) {
        var checked = [];
        node.querySelectorAll("input[data-val]").forEach(function (c) {
          if (c.checked) checked.push(c.getAttribute("data-val"));
        });
        return checked;
      }
      var items = [];
      node.querySelectorAll("input[data-item]").forEach(function (inp) {
        var v = inp.value.trim();
        if (v) items.push(v);
      });
      return items;
    }
    var raw;
    if (node.hasAttribute("data-slider-wrap")) {
      raw = node.querySelector("[data-num]").value;
    } else if (node.hasAttribute("data-pw-row")) {
      raw = node.querySelector("[data-pw-input]").value;
    } else {
      raw = node.value != null ? node.value : "";
    }
    if (f.type === "int" || f.type === "float") {
      var n = parseFloat(raw);
      // 非数字原文上送：由后端 coerce 拒收并回字段级红字（不再前端猜测类型）
      return raw.trim() === "" || isNaN(n) ? raw : n;
    }
    if (node.hasAttribute("data-json")) {
      if (raw.trim() === "") return {};
      try {
        return JSON.parse(raw);
      } catch (e) {
        return raw;
      }
    }
    if (node.hasAttribute("data-lines")) {
      return raw.split("\n").map(function (s) { return s.trim(); }).filter(Boolean);
    }
    return raw;
  }

  function settingsCaptureDraft() {
    var box = el("qvq-settings-form");
    if (!box || !settingsFields.length) return;
    box.querySelectorAll("[data-key]").forEach(function (node) {
      var f = settingsSchemaOf(node.getAttribute("data-key"));
      if (f) settingsDraft[f.key] = settingsSerializeField(node, f);
    });
    settingsUpdateSaveBtn();
  }

  function settingsDirtyKeys() {
    settingsCaptureDraft();
    var dirty = [];
    Object.keys(settingsDraft).forEach(function (k) {
      if (JSON.stringify(settingsDraft[k]) !== JSON.stringify(settingsOriginal[k])) dirty.push(k);
    });
    return dirty;
  }

  function settingsUpdateSaveBtn() {
    var btn = el("qvq-settings-save");
    if (!btn) return;
    var dirty = 0;
    Object.keys(settingsDraft).forEach(function (k) {
      if (JSON.stringify(settingsDraft[k]) !== JSON.stringify(settingsOriginal[k])) dirty++;
    });
    btn.textContent = t("save") + (dirty ? " (" + dirty + ")" : "");
  }

  function settingsErrorBox(key) {
    var form = el("qvq-settings-form");
    return form ? form.querySelector("[data-err='" + key + "']") : null;
  }

  function settingsShowError(key, msg) {
    var box = settingsErrorBox(key);
    if (box) {
      box.textContent = msg;
      box.classList.add("show");
      box.setAttribute("data-sticky", "1");
      var wrap = box.closest(".qvq-field");
      var input = wrap && wrap.querySelector(".qvq-input, .qvq-textarea, .qvq-select");
      if (input) input.classList.add("qvq-input-bad");
    }
  }

  function settingsClearStickyErrors() {
    var form = el("qvq-settings-form");
    if (!form) return;
    form.querySelectorAll(".qvq-field-err[data-sticky]").forEach(function (node) {
      node.removeAttribute("data-sticky");
      node.classList.remove("show");
      node.textContent = "";
      var wrap = node.closest(".qvq-field");
      var input = wrap && wrap.querySelector(".qvq-input-bad");
      if (input) input.classList.remove("qvq-input-bad");
    });
  }

  function settingsValidateJsonField(node) {
    var key = node.getAttribute("data-key");
    if (node.value.trim() === "") {
      node.classList.remove("qvq-input-bad");
      return true;
    }
    try {
      JSON.parse(node.value);
      node.classList.remove("qvq-input-bad");
      var errBox = settingsErrorBox(key);
      if (errBox && !errBox.getAttribute("data-sticky")) errBox.classList.remove("show");
      return true;
    } catch (err) {
      node.classList.add("qvq-input-bad");
      settingsShowError(key, t("settings_json_bad"));
      return false;
    }
  }

  // 表单容器事件委托一次绑定（innerHTML 重绘不丢）
  function bindSettingsFormEvents() {
    if (settingsEventsBound) return;
    var box = el("qvq-settings-form");
    if (!box) return;
    settingsEventsBound = true;
    box.addEventListener("input", function (e) {
      var node = e.target;
      if (!(node && node.getAttribute)) return;
      if (node.getAttribute("data-slider")) {
        var wrap = node.closest("[data-slider-wrap]");
        if (wrap) wrap.querySelector("[data-num]").value = node.value;
      } else if (node.getAttribute("data-num")) {
        var wrap2 = node.closest("[data-slider-wrap]");
        if (wrap2) wrap2.querySelector("[data-slider]").value = node.value;
      }
      settingsCaptureDraft();
    });
    box.addEventListener("change", function () { settingsCaptureDraft(); });
    box.addEventListener("focusout", function (e) {
      var node = e.target;
      if (node && node.getAttribute && node.getAttribute("data-json")) {
        settingsValidateJsonField(node);
      }
    });
    box.addEventListener("click", function (e) {
      var target = e.target;
      if (!target || !target.closest) return;
      var addBtn = target.closest("[data-list-add]");
      if (addBtn) {
        var root = addBtn.closest("[data-list]");
        var row = document.createElement("div");
        row.className = "qvq-list-row";
        row.innerHTML = "<input class='qvq-input' data-item='1' />" +
          "<button type='button' class='qvq-btn small ghost' data-list-del='1' title='" + esc(t("del")) + "'>×</button>";
        root.insertBefore(row, addBtn);
        row.querySelector("input").focus();
        settingsCaptureDraft();
        return;
      }
      var delBtn = target.closest("[data-list-del]");
      if (delBtn) {
        var rowEl = delBtn.closest(".qvq-list-row");
        if (rowEl) rowEl.remove();
        settingsCaptureDraft();
        return;
      }
      var pwBtn = target.closest("[data-pw-toggle]");
      if (pwBtn) {
        var pwWrap = pwBtn.closest("[data-pw-row]");
        var inp = pwWrap && pwWrap.querySelector("[data-pw-input]");
        if (inp) {
          var show = inp.type === "password";
          inp.type = show ? "text" : "password";
          pwBtn.textContent = t(show ? "settings_hide" : "settings_show");
        }
      }
    });
  }

  // T1/T3 类型化保存：只送 dirty 字段，dangerous 变更先确认，错误回填字段级红字
  function saveSettings() {
    settingsCaptureDraft();
    settingsClearStickyErrors();
    var jsonBad = false;
    el("qvq-settings-form").querySelectorAll("[data-json]").forEach(function (node) {
      if (!settingsValidateJsonField(node)) jsonBad = true;
    });
    if (jsonBad) {
      toast(t("settings_json_bad"), true);
      return;
    }
    var dirty = settingsDirtyKeys();
    if (!dirty.length) {
      toast(t("settings_no_change"));
      return;
    }
    var dangerKeys = dirty.filter(function (k) {
      var f = settingsSchemaOf(k);
      return f && f.dangerous;
    });
    var go = function () {
      saveConfigSettings(dirty);
      savePluginSettings(dirty);
    };
    if (dangerKeys.length) {
      confirmDialog(t("settings_danger_confirm") + "\n" + dangerKeys.join(", ")).then(function (ok) {
        if (ok) go();
      });
    } else {
      go();
    }
  }

  // QvQChat 自身配置：只送 dirty 字段到 /api/qvq/config
  function saveConfigSettings(dirty) {
    var keys = dirty.filter(function (k) { return k.indexOf(PLUGIN_KEY_PREFIX) !== 0; });
    if (!keys.length) return;
    var payload = {};
    keys.forEach(function (k) { payload[k] = settingsDraft[k]; });
    api("/api/qvq/config", "POST", payload).then(function (r) {
      if (r && r.errors && Object.keys(r.errors).length) {
        Object.keys(r.errors).forEach(function (k) { settingsShowError(k, r.errors[k]); });
        (r.applied || []).forEach(function (k) { settingsOriginal[k] = settingsDraft[k]; });
        toast(t("settings_save_partial"), true);
      } else if (r && r.ok) {
        keys.forEach(function (k) { settingsOriginal[k] = settingsDraft[k]; });
        toast(t("settings_saved"));
      } else {
        toast((r && r.error) || "error", true);
      }
      settingsUpdateSaveBtn();
    });
  }

  // 插件设置：按模块分组 POST /api/qvq/plugin_settings/save，错误回填沿用字段级红字
  function savePluginSettings(dirty) {
    var byModule = {};
    dirty.forEach(function (k) {
      if (k.indexOf(PLUGIN_KEY_PREFIX) !== 0) return;
      var rest = k.slice(PLUGIN_KEY_PREFIX.length);
      var sep = rest.indexOf(":");
      if (sep <= 0) return;
      var mod = rest.slice(0, sep);
      var rawKey = rest.slice(sep + 1);
      if (!byModule[mod]) byModule[mod] = {};
      byModule[mod][rawKey] = settingsDraft[k];
    });
    Object.keys(byModule).forEach(function (mod) {
      api("/api/qvq/plugin_settings/save", "POST", { module: mod, values: byModule[mod] }).then(function (r) {
        var full = function (rk) { return PLUGIN_KEY_PREFIX + mod + ":" + rk; };
        if (r && r.errors && Object.keys(r.errors).length) {
          Object.keys(r.errors).forEach(function (rk) { settingsShowError(full(rk), r.errors[rk]); });
          (r.applied || []).forEach(function (rk) { settingsOriginal[full(rk)] = settingsDraft[full(rk)]; });
          toast(t("settings_save_partial"), true);
        } else if (r && r.ok) {
          Object.keys(byModule[mod]).forEach(function (rk) { settingsOriginal[full(rk)] = settingsDraft[full(rk)]; });
          toast(t("settings_saved"));
        } else {
          toast((r && r.error) || "error", true);
        }
        settingsUpdateSaveBtn();
      });
    });
  }

  // T4：设置页有未保存修改时，切 tab（捕获阶段拦截导航点击）/ 关页给出离开提示
  (function initSettingsLeaveGuard() {
    var nav = document.getElementById("qvq-nav");
    if (nav) {
      nav.addEventListener("click", function (e) {
        if (!window.__qvq_inited__ || !settingsFields.length) return;
        var btn = e.target && e.target.closest ? e.target.closest(".qvq-nav-btn") : null;
        if (!btn) return;
        var active = document.querySelector(".qvq-nav-btn.active");
        if (active && active.getAttribute("data-tab") === btn.getAttribute("data-tab")) return;
        if (!settingsDirtyKeys().length) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        confirmDialog(t("settings_unsaved")).then(function (ok) {
          if (ok) switchTab(btn.getAttribute("data-tab"));
        });
      }, true);
    }
    window.addEventListener("beforeunload", function (e) {
      if (settingsFields.length && settingsDirtyKeys().length) {
        e.preventDefault();
        e.returnValue = "";
      }
    });
  })();

  /* ===== 成本可视化：每日成本柱 + 累计线 + 按模型分布 ===== */

  function renderCostChart(data, boxId) {
    var box = el(boxId || "qvq-home-cost");
    if (!box) return;
    var days = data.daily || [];
    var byModel = data.by_model || {};
    var total = data.total || 0;
    if (!Object.keys(byModel).length) {
      box.innerHTML = '<div class="qvq-empty">' + esc(t("cost_empty")) + "</div>";
      return;
    }
    var costs = days.map(function (d) { return d.cost || 0; });
    var W = 700, H = 150, top = 10, bottom = 30;
    var plotH = H - top - bottom;
    var n = days.length || 1;
    var maxC = Math.max.apply(null, costs) || 1;
    var x = function (i) { return n > 1 ? W * (i / (n - 1)) : W / 2; };
    var y = function (v) { return top + plotH - (v / maxC) * plotH; };
    var grid = "";
    [0.5].forEach(function (r) {
      grid += "<line class='qvq-chart-grid' x1='0' y1='" + (top + plotH * r) + "' x2='" + W + "' y2='" + (top + plotH * r) + "' />";
    });
    var bw = Math.max(5, W / n * 0.4);
    var bars = costs.map(function (c, i) {
      if (!c) return "";
      var h = (c / maxC) * plotH;
      return "<rect class='qvq-chart-calls' x='" + (x(i) - bw / 2) + "' y='" + (top + plotH - h) +
        "' width='" + bw + "' height='" + h + "' rx='2' />";
    }).join("");
    var cum = 0;
    var cumMax = costs.reduce(function (a, b) { return a + b; }, 0) || 1;
    var cumPoints = costs.map(function (c, i) {
      cum += c;
      return x(i) + "," + (top + plotH - (cum / cumMax) * plotH);
    });
    var axis = [0, n - 1].map(function (i) {
      return "<span>" + esc(((days[i] && days[i].date) || "").slice(5)) + "</span>";
    }).join("");
    var dist = Object.keys(byModel).slice(0, 6).map(function (mid) {
      var v = byModel[mid];
      var pct = total ? Math.round((v / total) * 100) : 0;
      return '<div class="qvq-cost-row"><span class="qvq-cost-name">' + esc(mid) + "</span>" +
        '<span class="qvq-cost-bar"><i style="width:' + pct + '%"></i></span>' +
        '<span class="qvq-cost-val">$' + Number(v).toFixed(4) + " · " + pct + "%</span></div>";
    }).join("");
    box.innerHTML =
      "<div class='qvq-chart-legend'><span>" + esc(t("cost_total")) + " <b>$" + Number(total).toFixed(4) + "</b></span>" +
      "<span>" + esc(t("cost_daily")) + "</span><span>" + esc(t("cost_by_model")) + "</span></div>" +
      "<div class='qvq-chart-wrap'><svg class='qvq-chart' viewBox='0 0 " + W + " " + H + "' preserveAspectRatio='none' role='img'>" +
      grid + bars +
      "<path class='qvq-chart-line' d='M" + cumPoints.join(" L") + "' />" +
      "</svg><div class='qvq-chart-axis'>" + axis + "</div></div>" + dist;
  }

  function renderUsageChart(data, boxId) {    var box = el(boxId || "qvq-usage-chart");
    if (!box) return;
    var days = data.days || [];
    var limit = data.limit || 0;
    var tokens = days.map(function (d) { return d.tokens || 0; });
    var calls = days.map(function (d) { return d.calls || 0; });
    var sum = function (arr) { return arr.reduce(function (a, b) { return a + b; }, 0); };
    var totalTokens = sum(tokens);
    var totalCalls = sum(calls);
    if (!totalTokens && !totalCalls) {
      box.innerHTML = '<div class="qvq-empty">' + esc(t("usage_empty")) + "</div>";
      return;
    }
    var W = 700, H = 170, padX = 4, top = 10, bottom = 46;
    var plotH = H - top - bottom;
    var n = days.length || 1;
    var maxTokens = Math.max.apply(null, tokens.concat([limit])) || 1;
    var maxCalls = Math.max.apply(null, calls) || 1;
    var x = function (i) { return n > 1 ? padX + (W - padX * 2) * (i / (n - 1)) : W / 2; };
    var yTok = function (v) { return top + plotH - (v / maxTokens) * plotH; };
    var barW = Math.max(6, (W - padX * 2) / n * 0.42);
    var barH = function (v) { return (v / maxCalls) * (plotH * 0.34); };

    var grid = "";
    [0.25, 0.5, 0.75].forEach(function (r) {
      var y = top + plotH * r;
      grid += "<line class='qvq-chart-grid' x1='0' y1='" + y + "' x2='" + W + "' y2='" + y + "' />";
    });

    var bars = calls.map(function (c, i) {
      if (!c) return "";
      var h = barH(c);
      return "<rect class='qvq-chart-calls' x='" + (x(i) - barW / 2) + "' y='" + (top + plotH - h) +
        "' width='" + barW + "' height='" + h + "' rx='2' />";
    }).join("");

    var points = tokens.map(function (v, i) { return x(i) + "," + yTok(v); });
    var area = "M" + points.join(" L") + " L" + x(n - 1) + "," + (top + plotH) + " L" + x(0) + "," + (top + plotH) + " Z";
    var line = "M" + points.join(" L");
    var limitLine = "";
    if (limit && limit <= maxTokens) {
      var ly = yTok(limit);
      limitLine = "<line class='qvq-chart-limit' x1='0' y1='" + ly + "' x2='" + W + "' y2='" + ly + "' />";
    }

    var axis = days.length
      ? [0, Math.floor((days.length - 1) / 3), Math.floor((days.length - 1) * 2 / 3), days.length - 1].map(function (i) {
        var d = days[i];
        return "<span>" + esc(d && d.date ? d.date.slice(5) : "") + "</span>";
      }).join("")
      : "";

    var today = tokens.length ? tokens[tokens.length - 1] : 0;
    var todayCalls = calls.length ? calls[calls.length - 1] : 0;
    var legend =
      "<div class='qvq-chart-legend'>" +
      "<span><i class='dot-line'></i>" + esc(t("usage_total")) + " <b>" + esc(totalTokens) + "</b> " + esc(t("usage_tokens")) + "</span>" +
      "<span><i class='dot-calls'></i>" + esc(t("usage_calls")) + " <b>" + esc(totalCalls) + "</b></span>" +
      "<span>" + esc(t("usage_avg")) + " <b>" + esc(Math.round(totalTokens / (days.length || 1))) + "</b></span>" +
      "<span>" + esc(t("usage_today")) + " <b>" + esc(today) + "</b> " + esc(t("usage_tokens")) + " / <b>" + esc(todayCalls) + "</b> " + esc(t("usage_calls")) + "</span>" +
      (limit ? "<span>" + esc(t("usage_limit")) + " <b>" + esc(limit) + "</b></span>" : "") +
      "</div>";

    var step = W / n;
    var hits = days.map(function (d, i) {
      return "<rect class='qvq-chart-hit' data-i='" + i + "' x='" + (i * step) + "' y='0' width='" + step + "' height='" + H + "' />";
    }).join("");

    box.innerHTML = legend +
      "<div class='qvq-chart-wrap'>" +
      "<svg class='qvq-chart' viewBox='0 0 " + W + " " + H + "' preserveAspectRatio='none' role='img'>" +
      grid + bars +
      "<path class='qvq-chart-area' d='" + area + "' />" +
      "<path class='qvq-chart-line' d='" + line + "' />" +
      limitLine +
      "<line class='qvq-chart-cross' y1='" + top + "' y2='" + (top + plotH) + "' x1='0' x2='0' />" +
      "<circle class='qvq-chart-dot' r='4' cx='0' cy='0' />" +
      hits +
      "</svg>" +
      "<div class='qvq-chart-tip'></div>" +
      "</div>" +
      "<div class='qvq-chart-axis'>" + axis + "</div>";

    var wrapEl = box.querySelector(".qvq-chart-wrap");
    var svgEl = wrapEl.querySelector(".qvq-chart");
    var crossEl = wrapEl.querySelector(".qvq-chart-cross");
    var dotEl = wrapEl.querySelector(".qvq-chart-dot");
    var tipEl = wrapEl.querySelector(".qvq-chart-tip");
    var hideTip = function () {
      tipEl.classList.remove("show");
      crossEl.style.opacity = 0;
      dotEl.style.opacity = 0;
    };
    svgEl.addEventListener("mousemove", function (ev) {
      var rect = svgEl.getBoundingClientRect();
      var ratio = rect.width ? (ev.clientX - rect.left) / rect.width : 0;
      var i = Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1))));
      var d = days[i];
      if (!d) { hideTip(); return; }
      var vx = x(i);
      var vy = yTok(tokens[i]);
      crossEl.setAttribute("x1", vx);
      crossEl.setAttribute("x2", vx);
      crossEl.style.opacity = 1;
      dotEl.setAttribute("cx", vx);
      dotEl.setAttribute("cy", vy);
      dotEl.style.opacity = 1;
      var px = (vx / W) * rect.width;
      var py = (vy / H) * rect.height;
      var pct = limit && (d.tokens || 0) ? Math.round(((d.tokens || 0) / limit) * 100) + "% " + t("usage_limit") : "";
      tipEl.innerHTML = "<div class='d'>" + esc(d.date || "") + "</div>" +
        esc(t("usage_tokens")) + " <b>" + esc(d.tokens || 0) + "</b><br>" +
        esc(t("usage_calls")) + " <b>" + esc(d.calls || 0) + "</b>" +
        (pct ? "<br>" + esc(pct) : "");
      tipEl.style.left = Math.max(75, Math.min(rect.width - 75, px)) + "px";
      tipEl.style.top = Math.max(10, py) + "px";
      tipEl.classList.add("show");
    });
    svgEl.addEventListener("mouseleave", hideTip);
  }

  function showLogin() {
    var box = el("qvq-login");
    if (box) box.style.display = "flex";
  }

  function hideLogin() {
    var box = el("qvq-login");
    if (box) box.style.display = "none";
  }

  function tryLogin() {
    var input = el("qvq-login-token");
    var token = input.value.trim();
    if (!token) return;
    authWith(token).then(function (ok) {
      if (ok) {
        activeToken = token;
        try { localStorage.setItem("qvq_token", token); } catch (e) {}
        hideLogin();
        el("qvq-login-err").textContent = "";
        initApp();
      } else {
        el("qvq-login-err").textContent = t("login_failed");
      }
    });
  }

