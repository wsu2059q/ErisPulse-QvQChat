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
    api("/api/qvq/sessions").then(function (data) {
      // 并行取人格列表：账户卡显示/换绑该账户当前人格
      api("/api/qvq/personas").then(function (pdata) {
        renderOrchAccounts((data && data.accounts) || {}, (pdata && pdata.personas) || []);
      });
    });
  }

  // 适配器账户卡：各平台在线 bot + 已隔离账户的会话数 + 该账户当前人格（可内联换绑）
  function renderOrchAccounts(accounts, personas) {
    var box = el("qvq-orch-accounts");
    if (!box) return;
    var adapters = accounts.adapters || [];
    var accts = accounts.accounts || [];
    if (!adapters.length) {
      box.innerHTML = '<div class="qvq-empty">' + esc(t("orch_accounts_empty")) + "</div>";
      return;
    }
    var popts = (personas || []).map(function (p) {
      return '<option value="' + esc(p.id) + '">' + esc(p.name || p.id) + "</option>";
    }).join("");

    function personaSelect(acct, current) {
      // 内联换绑：select 直改 POST personas/bind @account；空值=清除账户级绑定
      return '<select class="qvq-select qvq-input-sm" data-persona-acct="' + esc(acct) + '" data-current="' + esc(current || "") + '" title="' + esc(t("chat_persona_binding")) + '">' +
        '<option value="">' + esc(t("personas_follow_model")) + "</option>" + popts + "</select>";
    }

    function bindPersonaSelects(root) {
      root.querySelectorAll("select[data-persona-acct]").forEach(function (sel) {
        sel.value = sel.getAttribute("data-current") || "";
        sel.onchange = function () {
          api("/api/qvq/personas/bind", "POST", { chat_key: "@" + sel.getAttribute("data-persona-acct"), persona: sel.value }).then(function (r) {
            toast(r && r.ok ? t("saved") : ((r && r.error) || "error"), !(r && r.ok));
          });
        };
      });
    }

    var html = adapters.map(function (ad) {
      var bots = ad.bots || [];
      var botChips = bots.length
        ? bots.map(function (b) {
            var info = accts.filter(function (a) { return a.account === b; })[0];
            var persona = info ? (info.persona || "") : "";
            var cnt = info ? info.sessions : 0;
            return '<span class="qvq-acct-bot">' +
              '<span class="qvq-acct-badge' + (info ? " iso" : "") + '" title="' + esc(ad.platform) + (cnt ? " · " + cnt + " " + esc(t("acct_sessions_unit")) : "") + '">' + esc(b) +
              (cnt ? " · " + cnt : "") + "</span>" +
              '<span class="qvq-acct-persona">' + personaSelect(b, persona) + "</span></span>";
          }).join("")
        : '<span class="qvq-tool-desc">-</span>';
      return '<div class="qvq-acct-row"><span class="qvq-acct-platform">' + esc(ad.platform) + "</span>" +
        '<span class="qvq-acct-bots">' + botChips + "</span>" +
        (bots.length > 1 ? '<span class="qvq-chip">' + esc(t("acct_multi")) + "</span>" : "") + "</div>";
    }).join("");
    // 会话里存在但不在适配器在线列表中的账户
    var known = {};
    adapters.forEach(function (ad) { (ad.bots || []).forEach(function (b) { known[b] = 1; }); });
    var stale = accts.filter(function (a) { return !known[a.account]; });
    if (stale.length) {
      html += '<div class="qvq-acct-row stale"><span class="qvq-acct-platform">' + esc(t("acct_offline")) + '</span><span class="qvq-acct-bots">' +
        stale.map(function (a) {
          return '<span class="qvq-acct-bot">' +
            '<span class="qvq-acct-badge iso" title="' + esc(a.platforms.join(", ")) + '">@' + esc(a.account) + " · " + a.sessions + "</span>" +
            '<span class="qvq-acct-persona">' + personaSelect(a.account, a.persona || "") + "</span></span>";
        }).join("") + "</span></div>";
    }
    box.innerHTML = html;
    bindPersonaSelects(box);
  }

  // 链序是跨 provider 的全局顺序：取后端 chain，无则按 provider 展平
  // chain 条目不携带 provider 停用状态，单独记 orchProviderOff
  var orchProviderOff = {};

  function flattenChain(data) {
    orchProviderOff = {};
    ((data && data.providers) || []).forEach(function (p) {
      if (p.enabled === false) orchProviderOff[p.id] = true;
    });
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
    // 链首挑选同样跳过 provider 停用的模型
    var firstEnabled = orchChain.filter(function (x) {
      return x.model.enabled !== false && !orchProviderOff[x.provider];
    })[0];
    var warn = firstEnabled && firstEnabled.model.tool_call !== true
      ? '<div class="qvq-chain-warn">' + esc(t("orch_chain_top_no_tools")) + "</div>"
      : "";
    box.innerHTML = warn + '<div class="qvq-chain-list">' + orchChain.map(function (item, i) {
      var pOff = !!orchProviderOff[item.provider];
      var mOff = item.model.enabled === false;
      // 停用的 provider/模型灰显，仍可拖拽
      var offChip = pOff ? esc(t("provider_disabled")) : (mOff ? esc(t("off")) : "");
      return '<div class="qvq-chain-row' + (offChip ? " off" : "") + '" draggable="true" data-ci="' + i + '">' +
        '<span class="qvq-chain-seq">' + (i + 1) + "</span>" +
        '<span class="qvq-chain-name">' + esc(item.provider + ":" + item.model.id) + "</span>" +
        '<span class="qvq-chain-caps">' + modelsModelChips(item.model) + "</span>" +
        (offChip ? "<span class='qvq-chip danger-chip'>" + offChip + "</span>" : "") +
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

  // 整体链序一次提交；连续拖动时合并保存
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
          esc(t("health_left").replace("{s}", b.cooldown_left)) + "</span>" +
          '<button type="button" class="qvq-btn small ghost" data-breaker-reset="' + esc(b.model) + '">' + esc(t("health_reset")) + "</button></div>";
      }).join("") + "</div>";
    box.querySelectorAll("button[data-breaker-reset]").forEach(function (btn) {
      btn.onclick = function () {
        api("/api/qvq/breakers/reset", "POST", { model: btn.getAttribute("data-breaker-reset") }).then(function (r) {
          toast(r && r.ok ? t("saved") : "error", !(r && r.ok));
          loadOrchestrate();
        });
      };
    });
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
      // 运行项两行布局：
      // 头行 chip + 会话键（超长省略），摘要独占次行限两行截断
      return '<div class="qvq-run-item"><div class="qvq-run-head">' +
        '<span class="qvq-chip o-eco">' + esc(t("steps_running")) + '</span>' +
        '<span class="qvq-run-session">' + esc(r.session) + '</span></div>' +
        '<div class="qvq-run-desc">' + esc(r.text_head || "-") + '</div></div>';
    }).join("");
  }

  // 上半部分为定时任务（下次执行 + 最近状态），下半部分为最近执行记录
  // attentionOnly=true（编排页）：只显示上次失败/运行中的任务与出错的执行
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
        optimisticToggle(cb, "/api/qvq/config", { disabled_tools: set }, function (r) {
          return r && r.ok && !(r.errors && Object.keys(r.errors).length);
        });
      };
    });
    box.querySelectorAll("input[data-cap-skill]").forEach(function (cb) {
      cb.onchange = function () {
        optimisticToggle(cb, "/api/qvq/skills/enabled", { name: cb.getAttribute("data-cap-skill"), enabled: cb.checked });
      };
    });
    box.querySelectorAll("input[data-cap-mcp]").forEach(function (cb) {
      cb.onchange = function () {
        var path = cb.checked ? "/api/qvq/mcp/connect" : "/api/qvq/mcp/disconnect";
        optimisticToggle(cb, path, { name: cb.getAttribute("data-cap-mcp") });
      };
    });
  }

  // 乐观开关：请求期间禁用；失败回滚勾选并提示
  function optimisticToggle(cb, path, body, okWhen) {
    var wanted = cb.checked;
    cb.disabled = true;
    api(path, "POST", body).then(function (r) {
      cb.disabled = false;
      var ok = okWhen ? !!okWhen(r) : !!(r && r.ok);
      if (ok) {
        toast(t("saved"));
      } else {
        cb.checked = !wanted;
        toast((r && r.error) || "error", true);
      }
    }, function () {
      cb.disabled = false;
      cb.checked = !wanted;
      toast("error", true);
    });
  }

  var modelsCache = [];

  function fmtNum(v) {
    var n = Number(v);
    if (!isFinite(n) || n <= 0) return "-";
    return n >= 10000 ? Math.round(n / 1000) + "k" : (n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(n));
  }

  function numAttr(v) {
    return v === 0 || v ? String(v) : "";
  }

  function intOrNull(v) {
    if (v === "" || v == null) return null;
    var n = Number(v);
    return isFinite(n) ? Math.max(0, Math.round(n)) : null;
  }

  function modelsModelChips(model) {
    var out = "";
    if (model.tool_call === true) out += "<span class='qvq-chip o-eco'>" + esc(t("model_cap_tools")) + "</span>";
    else if (model.tool_call === false) out += "<span class='qvq-chip'>" + esc(t("model_cap_no_tools")) + "</span>";
    else out += "<span class='qvq-chip o-mcp'>?</span>";
    if (model.vision === true) out += "<span class='qvq-chip'>" + esc(t("model_cap_vision")) + "</span>";
    if (model.reasoning === true) out += "<span class='qvq-chip'>" + esc(t("model_cap_reason")) + "</span>";
    return out;
  }

  function modelPriceLabel(model) {
    var cost = model.cost;
    if (!cost || typeof cost !== "object") return "-";
    var inp = Math.round(Number(cost.input || 0) * 10000) / 10000;
    var outp = Math.round(Number(cost.output || 0) * 10000) / 10000;
    if (!inp && !outp) return "-";
    return "$" + inp + " / $" + outp;
  }

  function findProvider(id) {
    for (var i = 0; i < modelsCache.length; i++) {
      if (modelsCache[i].id === id) return modelsCache[i];
    }
    return null;
  }

  function reloadModels(cb) {
    api("/api/qvq/models").then(function (data) {
      modelsCache = (data && data.providers) || [];
      modelPresets = (data && data.presets) || [];
      renderModelsTable();
      if (cb) cb();
    });
  }

  function modelsSearchText() {
    var node = el("qvq-models-search");
    return node ? node.value.trim().toLowerCase() : "";
  }

  function providerMatches(p, q) {
    if (!q) return true;
    if ((p.name || "").toLowerCase().indexOf(q) >= 0 || (p.id || "").toLowerCase().indexOf(q) >= 0) return true;
    return (p.models || []).some(function (m) { return (m.id || "").toLowerCase().indexOf(q) >= 0; });
  }

  function bindModelsSearch() {
    var node = el("qvq-models-search");
    if (!node || node.dataset.bound) return;
    node.dataset.bound = "1";
    node.oninput = function () { renderModelsTable(); };
  }

  function renderModelsTable() {
    bindModelsSearch();
    var q = modelsSearchText();
    var providers = q ? modelsCache.filter(function (p) { return providerMatches(p, q); }) : modelsCache;
    var box = el("qvq-models-list");
    if (!box) return;
    if (!providers.length) {
      box.innerHTML = '<div class="qvq-empty qvq-empty-cta">' + esc(t("models_empty")) + "</div>";
      var cta = box.querySelector(".qvq-empty-cta");
      if (cta) cta.onclick = function () { openModelModal(null); };
      return;
    }
// 提供商卡片：头部（名称/URL/操作 + 右侧 provider 级开关）+ 可折叠模型网格，
    // 每行模型 chip 右侧内联启停开关（qvSwitch；隐藏原生 checkbox 仍是数据源）
    var cards = providers.map(function (p) {
      var models = p.models || [];
      var enabled = models.filter(function (m) { return m.enabled !== false; });
      var firstModel = enabled.length ? String(enabled[0].id) : "";
      var collapsible = models.length > 8;
      var chips = models.map(function (m) {
        var off = m.enabled === false;
        return "<div class='qvq-model-chip" + (off ? " off" : "") + "' title='" + esc(m.id) + "'>" +
          "<span class='qvq-model-chip-main'>" +
          "<span class='qvq-model-chip-id'>" + esc(m.id) + (off ? " · " + esc(t("off")) : "") + "</span>" +
          "<span class='qvq-model-chip-meta'>" + modelsModelChips(m) + "</span></span>" +
          "<input type='checkbox' data-mswitch='" + esc(m.id) + "'" + (off ? "" : " checked") + "/></div>";
      }).join("") || "<span class='qvq-tool-desc'>" + esc(t("model_none")) + "</span>";
      var modelsHtml = collapsible
        ? "<details class='qvq-provider-fold'><summary>" + esc(t("models_id")) + " · " + models.length + "</summary><div class='qvq-model-grid'>" + chips + "</div></details>"
        : "<div class='qvq-model-grid'>" + chips + "</div>";
      var pOff = p.enabled === false;
      return "<div class='qvq-provider-card" + (pOff ? " provider-off" : "") + "' data-id='" + esc(p.id) + "'>" +
        "<div class='qvq-provider-head'><div class='qvq-provider-title'><b>" + esc(p.name) + "</b>" +
        "<span class='qvq-chip'>" + enabled.length + "/" + models.length + "</span>" +
        (pOff ? "<span class='qvq-chip danger-chip'>" + esc(t("provider_disabled")) + "</span>" : "") +
        "<span class='qvq-tool-desc'>" + esc(p.base_url || "") + "</span>" +
        "<span class='qvq-tool-desc mono'>" + esc(p.api_key_masked || "-") + "</span></div>" +
        "<div class='qvq-actions'>" +
        "<button class='qvq-btn small ghost' data-act='models' data-id='" + esc(p.id) + "'>" + esc(t("model_manage")) + "</button> " +
        "<button class='qvq-btn small ghost' data-act='edit' data-id='" + esc(p.id) + "'>" + esc(t("edit")) + "</button> " +
        (firstModel ? "<button class='qvq-btn small ghost' data-act='test' data-model='" + esc(firstModel) + "'>" + esc(t("test")) + "</button> " : "") +
        "<button class='qvq-btn small danger' data-act='pdel' data-id='" + esc(p.id) + "'>" + esc(t("del")) + "</button>" +
        "</div>" +
        "<input type='checkbox' data-ptoggle='" + esc(p.id) + "'" + (pOff ? "" : " checked") + "/></div>" +
        modelsHtml + "</div>";
    }).join("");
    box.innerHTML = "<div class='qvq-provider-list'>" + cards + "</div>";
    box.querySelectorAll("button[data-act]").forEach(function (btn) {
      btn.onclick = function () {
        var pid = btn.getAttribute("data-id");
        var act = btn.getAttribute("data-act");
        var provider = findProvider(pid);
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
        } else if (act === "models") {
          if (provider) openModelsModal(provider);
        } else if (provider) {
          openModelModal(provider);
        }
      };
    });
    // provider 级启停：头部右侧 qvSwitch 走 providers/toggle
    box.querySelectorAll("input[data-ptoggle]").forEach(function (cb) {
      qvSwitch.wrap(cb);
      cb.addEventListener("change", function () {
        api("/api/qvq/providers/toggle", "POST", { id: cb.getAttribute("data-ptoggle"), enabled: cb.checked }).then(function (r) {
          if (r && r.ok) {
            toast(t("saved"));
          } else {
            cb.checked = !cb.checked; // 失败先拨回，loadModels 重渲染后以缓存为准
            toast((r && r.error) || "error", true);
          }
          loadModels();
        });
      });
    });
    // 模型快捷开关：chip 行内 qvSwitch，翻转 enabled 后走 providers/save 整卡保存
    box.querySelectorAll("input[data-mswitch]").forEach(function (cb) {
      qvSwitch.wrap(cb);
      cb.addEventListener("change", function () {
        var card = cb.closest(".qvq-provider-card");
        var provider = findProvider(card ? card.getAttribute("data-id") : "");
        if (!provider) return;
        var mid = cb.getAttribute("data-mswitch");
        var models = (provider.models || []).slice();
        for (var i = 0; i < models.length; i++) {
          if (String(models[i].id) === mid) {
            var next = {};
            for (var k in models[i]) next[k] = models[i][k];
            next.enabled = cb.checked;
            models[i] = next;
            break;
          }
        }
        var wanted = cb.checked;
        saveProviderModels(provider, models, null, function () {
          cb.checked = !wanted; // 保存失败：开关拨回（缓存未变）
        });
      });
    });
    try { cardifyTables(box); } catch (e) {}
  }

  function loadModels() {
    api("/api/qvq/breakers").then(function (data) {
      renderModelHealth("qvq-models-health", (data && data.breakers) || []);
    });
    loadInto("qvq-models-list", function () {
      return api("/api/qvq/models").then(function (data) {
        modelsCache = (data && data.providers) || [];
        modelPresets = (data && data.presets) || [];
        return data;
      });
    }, function (box, data) {
      renderModelsTable();
    });
    var enrichBtn = el("qvq-model-enrich");
    if (enrichBtn && !enrichBtn.onclick) {
      enrichBtn.onclick = function () {
        enrichBtn.disabled = true;
        api("/api/qvq/models/enrich", "POST", {}).then(function (data) {
          enrichBtn.disabled = false;
          if (data && data.ok) {
            toast(t("model_refresh_done").replace("{n}", data.updated || 0));
            loadModels();
          } else {
            toast((data && data.error) || "error", true);
          }
        }, function () {
          enrichBtn.disabled = false;
          toast("error", true);
        });
      };
    }
  }

  function saveProviderModels(provider, models, cb, onFail) {
    api("/api/qvq/providers/save", "POST", {
      id: provider.id, name: provider.name, base_url: provider.base_url,
      api_key: "", models: models
    }).then(function (data) {
      if (data && data.ok) {
        toast(t("saved"));
        reloadModels(cb);
      } else {
        if (onFail) try { onFail(); } catch (e) {}
        toast((data && data.error) || "error", true);
      }
    });
  }

  function openModelsModal(provider) {
    var rows = (provider.models || []).map(function (m, i) {
      var off = m.enabled === false;
      return "<tr" + (off ? " class='qvq-row-off'" : "") + "><td><b>" + esc(m.id) + "</b><div class='qvq-tool-desc'>" + modelsModelChips(m) + "</div></td>" +
        "<td>" + fmtNum(m.context_length) + "</td>" +
        "<td>" + fmtNum(m.max_output_tokens) + "</td>" +
        "<td>" + esc(modelPriceLabel(m)) + "</td>" +
        "<td><button class='qvq-btn small ghost' data-medit='" + i + "'>" + esc(t("edit")) + "</button> " +
        "<button class='qvq-btn small danger' data-mdel='" + i + "'>" + esc(t("del")) + "</button></td></tr>";
    }).join("");
    var table = rows
      ? "<table class='qvq-table'><thead><tr><th>" + esc(t("models_id")) + "</th><th>" + esc(t("model_context")) + "</th><th>" + esc(t("model_max_output")) + "</th><th>" + esc(t("model_price")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>"
      : '<div class="qvq-empty">' + esc(t("model_none")) + "</div>";
    var html = "<div class='qvq-toolbar'><button class='qvq-btn small' data-madd type='button'>+ " + esc(t("model_add_title")) + "</button>" +
      "<button class='qvq-btn small ghost' data-mrefresh type='button'>" + esc(t("model_refresh")) + "</button></div>" + table;
    openModal(provider.name + " · " + t("model_manage"), html);
    var body = el("qvq-modal-body");
    body.querySelector("[data-madd]").onclick = function () { openModelEditor(provider, null); };
    body.querySelector("[data-mrefresh]").onclick = function () {
      api("/api/qvq/models/enrich", "POST", {}).then(function (data) {
        if (data && data.ok) {
          toast(t("model_refresh_done").replace("{n}", data.updated || 0));
          reloadModels(function () {
            var p = findProvider(provider.id);
            if (p) openModelsModal(p);
          });
        } else {
          toast((data && data.error) || "error", true);
        }
      });
    };
    body.querySelectorAll("[data-medit]").forEach(function (btn) {
      btn.onclick = function () {
        openModelEditor(provider, provider.models[Number(btn.getAttribute("data-medit"))]);
      };
    });
    body.querySelectorAll("[data-mdel]").forEach(function (btn) {
      btn.onclick = function () {
        var idx = Number(btn.getAttribute("data-mdel"));
        var removed = provider.models[idx];
        var models = provider.models.slice();
        models.splice(idx, 1);
        saveProviderModels(provider, models, function () {
          toastUndo(t("deleted"), function () {
            var p = findProvider(provider.id);
            if (!p) return;
            var back = p.models.slice();
            back.push(removed);
            saveProviderModels(p, back);
          });
          var p2 = findProvider(provider.id);
          if (p2) openModelsModal(p2);
        });
      };
    });
  }

  function openModelEditor(provider, model) {
    var editing = !!model;
    var m = model || {};
    var fields =
      "<div class='qvq-field-row' style='align-items:center;justify-content:space-between'>" +
        "<label class='qvq-label' style='margin:0'>" + esc(t("model_smart")) + "</label>" +
        "<span class='qvq-switch'><input type='checkbox' id='qvq-me-smart'" + (m.manual === true ? "" : " checked") + "/><i></i></span>" +
      "</div>" +
      "<div class='qvq-tool-desc'>" + esc(t("model_smart_hint")) + "</div>" +
      "<label class='qvq-label'>" + esc(t("models_id")) + "</label>" +
      "<input class='qvq-input' id='qvq-me-id' value='" + esc(m.id || "") + "' placeholder='glm-5.3-flash'/>" +
      "<label class='qvq-label'>" + esc(t("model_context")) + "</label>" +
      "<input class='qvq-input' id='qvq-me-ctx' type='number' min='0' value='" + numAttr(m.context_length) + "' placeholder='262144'/>" +
      "<label class='qvq-label'>" + esc(t("model_max_output")) + "</label>" +
      "<input class='qvq-input' id='qvq-me-maxout' type='number' min='0' value='" + numAttr(m.max_output_tokens) + "' placeholder='65536'/>" +
      "<div class='qvq-actions' style='margin-top:10px'><button class='qvq-btn small ghost' id='qvq-me-detect' type='button'>" + esc(t("model_detect")) + "</button></div>" +
      "<div class='qvq-tool-desc' id='qvq-me-status'></div>" +
      "<details style='margin-top:14px'><summary class='qvq-label' style='cursor:pointer'>" + esc(t("model_advanced")) + "</summary>" +
        "<label class='qvq-label'>" + esc(t("model_input_types")) + "</label>" +
        "<label class='qvq-check-row'><input type='checkbox' checked disabled/><span>" + esc(t("model_input_text")) + "</span></label>" +
        "<label class='qvq-check-row'><input type='checkbox' id='qvq-me-image'" + (m.vision === true ? " checked" : "") + "/><span>" + esc(t("model_input_image")) + "</span></label>" +
        "<label class='qvq-check-row'><input type='checkbox' id='qvq-me-video'" + (m.video === true ? " checked" : "") + "/><span>" + esc(t("model_input_video")) + "</span></label>" +
        "<label class='qvq-check-row'><input type='checkbox' id='qvq-me-pdf'" + (m.files === true ? " checked" : "") + "/><span>" + esc(t("model_input_pdf")) + "</span></label>" +
        "<label class='qvq-label'>" + esc(t("model_caps")) + "</label>" +
        "<label class='qvq-check-row'><input type='checkbox' id='qvq-me-tool'" + (m.tool_call !== false ? " checked" : "") + "/><span>" + esc(t("model_tool_call")) + "</span></label>" +
        "<label class='qvq-check-row'><input type='checkbox' id='qvq-me-reason'" + (m.reasoning === true ? " checked" : "") + "/><span>" + esc(t("model_reasoning")) + "</span></label>" +
        "<label class='qvq-label'>" + esc(t("models_temp")) + "</label>" +
        "<input class='qvq-input' id='qvq-me-temp' type='number' step='0.1' min='0' value='" + numAttr(m.temperature) + "' placeholder='0.7'/>" +
        "<label class='qvq-label'>" + esc(t("model_price")) + "</label>" +
        "<div class='qvq-field-row'><input class='qvq-input' id='qvq-me-price-in' type='number' step='0.0001' min='0' value='" + numAttr(m.cost && m.cost.input) + "' placeholder='" + esc(t("model_price_in")) + "'/>" +
        "<input class='qvq-input' id='qvq-me-price-out' type='number' step='0.0001' min='0' value='" + numAttr(m.cost && m.cost.output) + "' placeholder='" + esc(t("model_price_out")) + "'/></div>" +
        "<label class='qvq-label'>" + esc(t("model_prefill_ok")) + "</label>" +
        "<select class='qvq-select' id='qvq-me-prefill'>" +
        "<option value=''" + (m.prefill_ok == null ? " selected" : "") + ">" + esc(t("model_prefill_auto")) + "</option>" +
        "<option value='yes'" + (m.prefill_ok === true ? " selected" : "") + ">" + esc(t("model_prefill_yes")) + "</option>" +
        "<option value='no'" + (m.prefill_ok === false ? " selected" : "") + ">" + esc(t("model_prefill_no")) + "</option></select>" +
        "<div class='qvq-tool-desc'>" + esc(t("model_prefill_hint")) + "</div>" +
        "<label class='qvq-label'>" + esc(t("model_effort")) + "</label>" +
        "<select class='qvq-select' id='qvq-me-effort'>" +
        "<option value=''" + (!m.reasoning_effort ? " selected" : "") + ">" + esc(t("model_effort_follow")) + "</option>" +
        "<option value='off'" + (m.reasoning_effort === "off" ? " selected" : "") + ">off</option>" +
        "<option value='low'" + (m.reasoning_effort === "low" ? " selected" : "") + ">low</option>" +
        "<option value='medium'" + (m.reasoning_effort === "medium" ? " selected" : "") + ">medium</option>" +
        "<option value='high'" + (m.reasoning_effort === "high" ? " selected" : "") + ">high</option></select>" +
        "<div class='qvq-tool-desc'>" + esc(t("model_effort_hint")) + "</div>" +
        "<label class='qvq-label'>" + esc(t("model_notes")) + "</label>" +
        "<textarea class='qvq-textarea' id='qvq-me-notes' rows='3' placeholder='" + esc(t("model_notes_ph")) + "'>" + esc(m.notes || "") + "</textarea>" +
        "<label class='qvq-check-row' style='margin-top:14px'><input type='checkbox' id='qvq-me-enabled'" + (m.enabled !== false ? " checked" : "") + "/><span>" + esc(t("model_enabled")) + "</span></label>" +
      "</details>";
    openForm(editing ? t("model_edit_title") : t("model_add_title"), fields, function (body) {
      var mid = fv(body, "qvq-me-id");
      if (!mid) {
        toast(t("models_fetch_fail"), true);
        return;
      }
      var next = {};
      if (model) { for (var k in model) next[k] = model[k]; }
      next.id = mid;
      next.manual = !body.querySelector("#qvq-me-smart").checked;
      next.enabled = body.querySelector("#qvq-me-enabled").checked;
      next.context_length = intOrNull(fv(body, "qvq-me-ctx"));
      next.max_output_tokens = intOrNull(fv(body, "qvq-me-maxout"));
      next.vision = body.querySelector("#qvq-me-image").checked;
      next.video = body.querySelector("#qvq-me-video").checked;
      next.files = body.querySelector("#qvq-me-pdf").checked;
      next.tool_call = body.querySelector("#qvq-me-tool").checked;
      next.reasoning = body.querySelector("#qvq-me-reason").checked;
      var temp = fv(body, "qvq-me-temp");
      next.temperature = temp === "" ? null : Number(temp);
      var pin = fv(body, "qvq-me-price-in");
      var pout = fv(body, "qvq-me-price-out");
      next.cost = (pin === "" && pout === "") ? null : { input: Number(pin || 0), output: Number(pout || 0) };
      var pfill = fv(body, "qvq-me-prefill");
      next.prefill_ok = pfill === "yes" ? true : (pfill === "no" ? false : null);
      next.reasoning_effort = fv(body, "qvq-me-effort");
      next.notes = fv(body, "qvq-me-notes");
      var models = (provider.models || []).slice();
      var idx = -1;
      if (model) {
        for (var i = 0; i < models.length; i++) {
          if (String(models[i].id) === String(model.id)) { idx = i; break; }
        }
      }
      if (idx >= 0) models[idx] = next; else models.push(next);
      saveProviderModels(provider, models, function () {
        var p = findProvider(provider.id);
        if (p) openModelsModal(p);
      });
    });
    var body = el("qvq-modal-body");
    var cancel = body.querySelector("[data-form-cancel]");
    if (cancel) cancel.onclick = function () { openModelsModal(provider); };
    // 自有组件接管：单个布尔勾选 → 开关（qvSwitch.wrap），输入类型多选 → qvMulti.wrap；
    // 原生控件隐藏保留，保存/detect 回填（setCheck）仍读写同一批控件
    qvSwitch.wrap(body.querySelector("#qvq-me-tool"));
    qvSwitch.wrap(body.querySelector("#qvq-me-reason"));
    qvSwitch.wrap(body.querySelector("#qvq-me-enabled"));
    qvMulti.wrap([
      body.querySelector("#qvq-me-image"),
      body.querySelector("#qvq-me-video"),
      body.querySelector("#qvq-me-pdf")
    ]);
    var smart = body.querySelector("#qvq-me-smart");
    function setVal(id, value) {
      var node = body.querySelector(id);
      if (node) node.value = value == null ? "" : value;
    }
    function setCheck(id, value) {
      var node = body.querySelector(id);
      if (node) node.checked = !!value;
    }
    function detect(auto) {
      if (auto && !smart.checked) return;
      var mid = fv(body, "qvq-me-id");
      if (!mid) return;
      var status = body.querySelector("#qvq-me-status");
      if (status) status.textContent = t("models_fetching");
      api("/api/qvq/models/detect", "POST", {
        provider: { id: provider.id, name: provider.name, base_url: provider.base_url },
        model: mid
      }).then(function (data) {
        var meta = (data && data.ok && data.meta) || {};
        if (!Object.keys(meta).length) {
          if (status) status.textContent = t("model_detect_empty");
          return;
        }
        if (meta.context_length != null) setVal("#qvq-me-ctx", meta.context_length);
        if (meta.max_output_tokens != null) setVal("#qvq-me-maxout", meta.max_output_tokens);
        setCheck("#qvq-me-image", meta.vision === true);
        setCheck("#qvq-me-video", meta.video === true);
        setCheck("#qvq-me-pdf", meta.files === true);
        setCheck("#qvq-me-tool", meta.tool_call !== false);
        setCheck("#qvq-me-reason", meta.reasoning === true);
        if (meta.cost) {
          if (meta.cost.input != null) setVal("#qvq-me-price-in", meta.cost.input);
          if (meta.cost.output != null) setVal("#qvq-me-price-out", meta.cost.output);
        }
        if (status) status.textContent = t("model_detected");
      }, function () {
        if (status) status.textContent = t("model_detect_empty");
      });
    }
    body.querySelector("#qvq-me-detect").onclick = function () { detect(false); };
    body.querySelector("#qvq-me-id").onblur = function () { detect(true); };
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
      "<input class='qvq-input' id='qvq-mf-key' type='password' placeholder='sk-…' />";
    if (!editingId) {
      fields +=
        "<label class='qvq-label'>" + esc(t("models_id")) + "</label>" +
        "<input class='qvq-input' id='qvq-mf-id' placeholder='deepseek-chat' />" +
        "<div class='qvq-tool-desc'>" + esc(t("models_auto_enrich_note")) + "</div>" +
        "<div class='qvq-actions' style='margin-top:10px'><button class='qvq-btn small ghost' id='qvq-mf-fetch' type='button'>" + esc(t("models_fetch")) + "</button></div>" +
        "<div id='qvq-mf-remote'></div>";
    } else {
      fields +=
        "<label class='qvq-label'>" + esc(t("model_effort")) + "</label>" +
        "<select class='qvq-select' id='qvq-mf-effort'>" +
        "<option value=''" + (!provider.reasoning_effort ? " selected" : "") + ">" + esc(t("model_effort_follow")) + "</option>" +
        "<option value='off'" + (provider.reasoning_effort === "off" ? " selected" : "") + ">off</option>" +
        "<option value='low'" + (provider.reasoning_effort === "low" ? " selected" : "") + ">low</option>" +
        "<option value='medium'" + (provider.reasoning_effort === "medium" ? " selected" : "") + ">medium</option>" +
        "<option value='high'" + (provider.reasoning_effort === "high" ? " selected" : "") + ">high</option></select>" +
        "<div class='qvq-tool-desc'>" + esc(t("model_effort_provider_hint")) + "</div>" +
        "<div class='qvq-tool-desc'>" + esc(t("models_meta_note")) + "</div>" +
        "<div class='qvq-actions'><button class='qvq-btn small ghost' id='qvq-mf-manage' type='button'>" + esc(t("model_manage")) + "</button></div>";
    }
    openForm(editingId ? (provider.name || editingId) : t("models_add"), fields, function (body) {
      var payload = {
        id: editingId || fv(body, "qvq-mf-name").toLowerCase().replace(/[^a-z0-9-]/g, "-"),
        name: fv(body, "qvq-mf-name"),
        base_url: fv(body, "qvq-mf-url"),
        api_key: fv(body, "qvq-mf-key")
      };
      var effortSel = fv(body, "qvq-mf-effort");
      if (effortSel != null) payload.reasoning_effort = effortSel;
      if (!editingId) {
        payload.models = fv(body, "qvq-mf-id").split(",").map(function (x) { return x.trim(); }).filter(Boolean)
          .map(function (id) { return { id: id, enabled: true }; });
      }
      if (!payload.name || !payload.base_url) {
        toast(t("models_fetch_fail"), true);
        return;
      }
      api("/api/qvq/providers/save", "POST", payload).then(function (data) {
        if (data && data.ok) {
          toast(t("saved"));
          var pid = (data.provider && data.provider.id) || payload.id;
          reloadModels(function () {
            var p = findProvider(pid);
            if (p) openModelsModal(p); else closeModal();
          });
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
    }
    if (editingId) {
      var manage = body.querySelector("#qvq-mf-manage");
      if (manage) manage.onclick = function () { openModelsModal(provider); };
      return;
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
      api("/api/qvq/providers/remote-models", "POST", { base_url: base_url, api_key: api_key }).then(function (data) {
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
          if (m.context_length) meta.push(fmtNum(m.context_length) + " ctx");
          if (m.max_output_tokens) meta.push(fmtNum(m.max_output_tokens) + " out");
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
    bindListSearch("qvq-personas-search", function () { loadPersonas(); });
    loadInto("qvq-personas-list", function () { return api("/api/qvq/personas"); }, function (box, data) {
      var q = listSearchText("qvq-personas-search");
      var all = (data && data.personas) || [];
      var bindings = (data && data.bindings) || {};
      var personas = q ? all.filter(function (p) {
        return (p.id || "").toLowerCase().indexOf(q) >= 0 ||
          (p.name || "").toLowerCase().indexOf(q) >= 0 ||
          (p.system || "").toLowerCase().indexOf(q) >= 0;
      }) : all;
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
      var nameOf = {};
      personas.forEach(function (p) { nameOf[p.id] = p.name || p.id; });
      var options = personas.map(function (p) {
        return "<option value='" + esc(p.id) + "'>" + esc(p.name || p.id) + " (" + esc(p.id) + ")</option>";
      }).join("");
      // 现有绑定：层级徽标 + 可读名称（人设名），可一键解绑
      var bindRows = Object.keys(bindings || {}).sort(function (a, b) {
        return bindTierRank(bindings[a] && a) - bindTierRank(b);
      }).map(function (key) {
        var pid = bindings[key];
        var tier = bindTierOf(key);
        return "<tr><td><span class='qvq-chip'>" + esc(t("bind_tier_" + tier)) + "</span> <code class='qvq-bind-key'>" + esc(key) + "</code></td>" +
          "<td><b>" + esc(nameOf[pid] || pid) + "</b><div class='qvq-tool-desc'>" + esc(pid) + "</div></td>" +
          "<td class='qvq-col-acts'><button class='qvq-btn small danger' data-unbind='" + esc(key) + "'>" + esc(t("unbind")) + "</button></td></tr>";
      }).join("");
      var bindTable = bindRows
        ? "<table class='qvq-table'><thead><tr><th>" + esc(t("bind_key_col")) + "</th><th>" + esc(t("col_persona")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + bindRows + "</tbody></table>"
        : '<div class="qvq-empty">' + esc(t("bind_none")) + "</div>";
      // 绑定表单：作用范围用快捷选项填充，下方实时预览最终 key
      var cur = chatSession || "";
      var curAcct = accountOf(cur);
      var curPlat = cur.split(":")[0] || "";
      var curGroup = cur.replace(/@[^:@]*$/, "").replace(/:u[^:@]+$/, "");
      el("qvq-personas-list").innerHTML = table +
        "<h3 class='qvq-card-title' style='margin-top:14px'>" + esc(t("bindings")) + "</h3>" +
        "<div class='qvq-tool-desc'>" + esc(t("bind_tiers_hint")) + "</div>" + bindTable +
        "<div class='qvq-bind-form'>" +
        '<div class="qvq-bind-scopes">' +
        '<button type="button" class="qvq-chip-btn" data-bind-fill="' + esc(cur) + '">' + esc(t("bind_scope_chat")) + "</button>" +
        (curGroup && curGroup !== cur ? '<button type="button" class="qvq-chip-btn" data-bind-fill="' + esc(curGroup) + '">' + esc(t("bind_scope_group")) + "</button>" : "") +
        (curAcct ? '<button type="button" class="qvq-chip-btn" data-bind-fill="@' + esc(curAcct) + '">' + esc(t("bind_scope_account")) + " @" + esc(curAcct) + "</button>" : "") +
        (curPlat ? '<button type="button" class="qvq-chip-btn" data-bind-fill="' + esc(curPlat) + ':*">' + esc(t("bind_scope_platform")) + "</button>" : "") +
        '<button type="button" class="qvq-chip-btn" data-bind-fill="">' + esc(t("bind_scope_custom")) + "</button>" +
        "</div>" +
        "<div class='qvq-field-row'><input class='qvq-input' id='qvq-bind-key' placeholder='" + esc(t("bind_hint")) + "' />" +
        "<select class='qvq-select' id='qvq-bind-persona'>" + options + "</select>" +
        "<button class='qvq-btn small' id='qvq-bind-btn'>" + esc(t("bind_btn")) + "</button></div>" +
        "<div class='qvq-bind-preview' id='qvq-bind-preview'>" + esc(t("bind_preview_hint")) + "</div>" +
        "</div>";
      el("qvq-personas-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var id = btn.getAttribute("data-id");
          if (btn.getAttribute("data-act") === "del") {
            var isBuiltin = id === "assistant";
            var doDelete = function () {
              api("/api/qvq/personas/delete", "POST", { id: id }).then(function (r) {
                if (r && r.undo) {
                  toastUndo(t("deleted"), function () {
                    api("/api/qvq/trash/restore", "POST", { token: r.undo }).then(function () { loadPersonas(); });
                  });
                } else {
                  toast(isBuiltin ? t("personas_reset") : t("deleted"));
                }
                loadPersonas();
              });
            };
// 内置人格删除 = 重置（需确认）；自定义人格直接删除（可撤销）
            if (isBuiltin) confirmDialog(t("personas_reset")).then(function (ok) { if (ok) doDelete(); });
            else doDelete();
          } else {
            var persona = personas.filter(function (p) { return p.id === id; })[0];
            if (persona) openPersonaModal(persona);
          }
        };
      });
      var bindKeyInput = el("qvq-bind-key");
      var bindPreview = el("qvq-bind-preview");
      function refreshBindPreview() {
        if (!bindPreview) return;
        var key = bindKeyInput ? bindKeyInput.value.trim() : "";
        var pid = el("qvq-bind-persona") ? el("qvq-bind-persona").value : "";
        if (!key) { bindPreview.textContent = t("bind_preview_hint"); return; }
        var tier = bindTierOf(key);
        bindPreview.innerHTML = esc(t("bind_preview"))
          .replace("{tier}", esc(t("bind_tier_" + tier)))
          .replace("{key}", esc(key))
          .replace("{persona}", esc(nameOf[pid] || pid || "-"));
      }
      el("qvq-personas-list").querySelectorAll("button[data-bind-fill]").forEach(function (chip) {
        chip.onclick = function () {
          if (bindKeyInput) bindKeyInput.value = chip.getAttribute("data-bind-fill") || "";
          el("qvq-personas-list").querySelectorAll("button[data-bind-fill]").forEach(function (c) { c.classList.remove("on"); });
          chip.classList.add("on");
          refreshBindPreview();
        };
      });
      if (bindKeyInput) bindKeyInput.oninput = refreshBindPreview;
      var bindPersonaSel = el("qvq-bind-persona");
      if (bindPersonaSel) bindPersonaSel.onchange = refreshBindPreview;
      refreshBindPreview();
      var bindBtn = el("qvq-bind-btn");
      if (bindBtn) {
        bindBtn.onclick = function () {
          var key = bindKeyInput ? bindKeyInput.value.trim() : "";
          if (!key) { toast(t("bind_need_target"), true); return; }
          api("/api/qvq/personas/bind", "POST", { chat_key: key, persona: el("qvq-bind-persona").value }).then(function () {
            toast(t("saved"));
            loadPersonas();
          });
        };
      }
      // 解绑：persona 传 null 删除绑定
      el("qvq-personas-list").querySelectorAll("button[data-unbind]").forEach(function (btn) {
        btn.onclick = function () {
          var key = btn.getAttribute("data-unbind");
          confirmDialog(key).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/personas/bind", "POST", { chat_key: key, persona: null }).then(function () {
              toast(t("deleted"));
              loadPersonas();
            });
          });
        };
      });
    });
  }

  function _examplesEncode(examples) {
    // [{user, assistant}] → 「用户: …\n助手: …\n\n」段式文本（编辑器往返用）
    return (examples || []).map(function (ex) {
      return "用户: " + (ex.user || "") + "\n助手: " + (ex.assistant || "");
    }).join("\n\n");
  }

  function _examplesDecode(text) {
    // 段式文本 → [{user, assistant}]；段内按 行首 用户:/user: 与 助手:/assistant: 归类
    var out = [];
    String(text || "").split(/\n\s*\n/).forEach(function (block) {
      var user = "", assistant = "";
      block.split("\n").forEach(function (line) {
        var t = line.trim();
        if (!t) return;
        if (/^(用户|user)\s*[:：]/i.test(t)) user += (user ? "\n" : "") + t.replace(/^(用户|user)\s*[:：]\s*/i, "");
        else if (/^(助手|assistant|ai)\s*[:：]/i.test(t)) assistant += (assistant ? "\n" : "") + t.replace(/^(助手|assistant|ai)\s*[:：]\s*/i, "");
        else if (!user) user += (user ? "\n" : "") + t;
        else assistant += (assistant ? "\n" : "") + t;
      });
      if (user || assistant) out.push({ user: user, assistant: assistant });
    });
    return out;
  }

  function openPersonaModal(persona) {
    var isEdit = !!persona;
    var p = persona || {};
    var fields =
      "<label class='qvq-label'>" + esc(t("personas_pid")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-id' placeholder='my_persona'" + (isEdit ? " readonly" : "") + " />" +
      "<label class='qvq-label'>" + esc(t("personas_pname")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-name' placeholder='QvQ' />" +
      "<label class='qvq-label'>" + esc(t("personas_system")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-pf-system'></textarea>" +
      "<label class='qvq-label'>" + esc(t("personas_tools")) + "</label>" +
      "<input class='qvq-input' id='qvq-pf-tools' placeholder='send_message, eco_*, remember' />" +
      "<details style='margin-top:14px'><summary class='qvq-label' style='cursor:pointer'>" + esc(t("personas_behavior")) + "</summary>" +
        "<label class='qvq-label'>" + esc(t("personas_nickname")) + "</label>" +
        "<input class='qvq-input' id='qvq-pf-nickname' placeholder='小IQ' />" +
        "<label class='qvq-label'>" + esc(t("personas_avatar")) + "</label>" +
        "<input class='qvq-input' id='qvq-pf-avatar' placeholder='https://…/avatar.png' />" +
        "<label class='qvq-label'>" + esc(t("personas_owner_title")) + "</label>" +
        "<input class='qvq-input' id='qvq-pf-owner' placeholder='" + esc(t("personas_owner_ph")) + "' />" +
        "<label class='qvq-label'>" + esc(t("personas_prefill")) + "</label>" +
        "<input class='qvq-input' id='qvq-pf-prefill' placeholder='喵呜~ / 诶—— / 嗯哼？' />" +
        "<div class='qvq-tool-desc'>" + esc(t("personas_prefill_hint")) + "</div>" +
        "<label class='qvq-label'>" + esc(t("personas_catchphrases")) + "</label>" +
        "<textarea class='qvq-textarea' id='qvq-pf-catch' rows='2' placeholder='口头禅1&#10;口头禅2'></textarea>" +
        "<label class='qvq-label'>" + esc(t("personas_banned")) + "</label>" +
        "<textarea class='qvq-textarea' id='qvq-pf-banned' rows='2' placeholder='禁语1&#10;禁语2'></textarea>" +
        "<label class='qvq-label'>" + esc(t("personas_style")) + "</label>" +
        "<div class='qvq-field-row'>" +
          "<input class='qvq-input' id='qvq-pf-style-emoji' placeholder='emoji 密度 low/mid/high' value='" + esc((p.style || {}).emoji_density || "") + "'/>" +
          "<input class='qvq-input' id='qvq-pf-style-verb' placeholder='话多 short/normal/long' value='" + esc((p.style || {}).verbosity || "") + "'/>" +
          "<input class='qvq-input' id='qvq-pf-style-form' placeholder='语气 casual/formal' value='" + esc((p.style || {}).formality || "") + "'/>" +
        "</div>" +
        "<label class='qvq-label'>" + esc(t("personas_examples")) + "</label>" +
        "<textarea class='qvq-textarea' id='qvq-pf-examples' rows='5' placeholder='用户: …&#10;助手: …&#10;&#10;用户: …&#10;助手: …'></textarea>" +
        "<div class='qvq-tool-desc'>" + esc(t("personas_examples_hint")) + "</div>" +
      "</details>" +
      "<details style='margin-top:10px'><summary class='qvq-label' style='cursor:pointer'>" + esc(t("personas_model_params")) + "</summary>" +
        "<div class='qvq-tool-desc' style='margin-bottom:6px'>" + esc(t("personas_model_hint")) + "</div>" +
        "<label class='qvq-label'>" + esc(t("models_temp")) + "</label>" +
        "<input class='qvq-input' id='qvq-pf-temp' type='number' step='0.1' min='0' max='2' placeholder='" + esc(t("personas_follow_model")) + "'/>" +
        "<label class='qvq-label'>" + esc(t("model_max_tokens")) + "</label>" +
        "<input class='qvq-input' id='qvq-pf-maxtok' type='number' step='1' min='1' placeholder='" + esc(t("personas_follow_model")) + "'/>" +
      "</details>";
    openForm(isEdit ? (persona.name || persona.id) : t("personas_new"), fields, function (body) {
      var payload = {
        id: fv(body, "qvq-pf-id"),
        name: fv(body, "qvq-pf-name"),
        system: body.querySelector("#qvq-pf-system").value,
        tools: fv(body, "qvq-pf-tools").split(",").map(function (x) { return x.trim(); }).filter(Boolean),
        nickname: fv(body, "qvq-pf-nickname"),
        avatar: fv(body, "qvq-pf-avatar"),
        owner_title: fv(body, "qvq-pf-owner"),
        prefill: fv(body, "qvq-pf-prefill"),
        catchphrases: fv(body, "qvq-pf-catch").split("\n").map(function (x) { return x.trim(); }).filter(Boolean),
        banned_words: fv(body, "qvq-pf-banned").split("\n").map(function (x) { return x.trim(); }).filter(Boolean),
        examples: _examplesDecode(body.querySelector("#qvq-pf-examples").value),
        temperature: fv(body, "qvq-pf-temp") === "" ? null : Number(fv(body, "qvq-pf-temp")),
        max_tokens: fv(body, "qvq-pf-maxtok") === "" ? null : Number(fv(body, "qvq-pf-maxtok")),
      };
      var style = {};
      ["emoji_density|qvq-pf-style-emoji", "verbosity|qvq-pf-style-verb", "formality|qvq-pf-style-form"].forEach(function (pair) {
        var kv = pair.split("|");
        var v = fv(body, kv[1]);
        if (v) style[kv[0]] = v;
      });
      payload.style = style;
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
      body.querySelector("#qvq-pf-nickname").value = persona.nickname || "";
      body.querySelector("#qvq-pf-avatar").value = persona.avatar || "";
      body.querySelector("#qvq-pf-owner").value = persona.owner_title || "";
      body.querySelector("#qvq-pf-prefill").value = persona.prefill || "";
      body.querySelector("#qvq-pf-catch").value = (persona.catchphrases || []).join("\n");
      body.querySelector("#qvq-pf-banned").value = (persona.banned_words || []).join("\n");
      body.querySelector("#qvq-pf-examples").value = _examplesEncode(persona.examples);
      if (persona.temperature != null) body.querySelector("#qvq-pf-temp").value = persona.temperature;
      if (persona.max_tokens != null) body.querySelector("#qvq-pf-maxtok").value = persona.max_tokens;
    }
  }

  function loadSkills() {
    bindListSearch("qvq-skills-search", function () { loadSkills(); });
    loadInto("qvq-skills-list", function () { return api("/api/qvq/skills"); }, function (box, data) {
      var q = listSearchText("qvq-skills-search");
      var all = (data && data.skills) || [];
      var skills = q ? all.filter(function (sk) {
        return (sk.name || "").toLowerCase().indexOf(q) >= 0 ||
          (sk.description || "").toLowerCase().indexOf(q) >= 0;
      }) : all;
      if (!skills.length) {
        el("qvq-skills-list").innerHTML = '<div class="qvq-empty qvq-empty-cta">' + esc(t("skills_empty")) + "</div>";
        var cta = el("qvq-skills-list").querySelector(".qvq-empty-cta");
        if (cta) cta.onclick = function () { openSkillModal(null); };
        return;
      }
      var rows = skills.map(function (sk) {
        var src = sk.source === "file" ? ".md" : (sk.source || "dashboard");
        var chk = sk.enabled !== false ? " checked" : "";
        var skCheck = skillsBatchMode ? "<td class='qvq-col-check'><input type='checkbox' class='qvq-skill-check' data-check-name='" + esc(sk.name) + "'/></td>" : "";
        return "<tr>" + skCheck +
          "<td><b>" + esc(sk.name) + "</b><div class='qvq-tool-desc'>" + esc((sk.description || "").slice(0, 100)) + "</div></td>" +
          "<td><span class='qvq-chip'>" + esc(src) + "</span></td>" +
          "<td><input type='checkbox' data-toggle='" + esc(sk.name) + "'" + chk + "/></td>" +
          "<td><button class='qvq-btn small ghost' data-act='edit' data-name='" + esc(sk.name) + "'>" + esc(t("edit")) + "</button> " +
          "<button class='qvq-btn small danger' data-act='del' data-name='" + esc(sk.name) + "'>" + esc(t("del")) + "</button></td></tr>";
      }).join("");
      var skillBatch = '<div class="qvq-actions qvq-batch-bar">' +
        (skillsBatchMode
          ? '<label class="qvq-check-inline"><input type="checkbox" id="qvq-skills-all"/> ' + esc(t("batch_select_all")) + "</label>" +
            '<button type="button" class="qvq-btn small danger" id="qvq-skills-batch">' + esc(t("batch_delete")) + "</button>" +
            '<button type="button" class="qvq-btn small ghost" id="qvq-skills-batch-exit">' + esc(t("batch_exit")) + "</button>"
          : '<button type="button" class="qvq-btn small ghost" id="qvq-skills-batch-enter">' + esc(t("batch_delete")) + "…</button>") +
        '<button type="button" class="qvq-btn small ghost" id="qvq-skills-organize">' + esc(t("organize_run")) + "</button></div>";
      var skHeadCheck = skillsBatchMode ? "<th></th>" : "";
      el("qvq-skills-list").innerHTML = skillBatch + "<table class='qvq-table'><thead><tr>" + skHeadCheck + "<th>" + esc(t("skills_name")) + "</th><th>" + esc(t("skills_source")) +
        "</th><th>" + esc(t("on")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      bindSkillBatch(skills);
      el("qvq-skills-list").querySelectorAll("input[data-toggle]").forEach(function (cb) {
        cb.onchange = function () {
          optimisticToggle(cb, "/api/qvq/skills/enabled", { name: cb.getAttribute("data-toggle"), enabled: cb.checked });
        };
      });
      el("qvq-skills-list").querySelectorAll("button[data-act]").forEach(function (btn) {
        btn.onclick = function () {
          var name = btn.getAttribute("data-name");
          if (btn.getAttribute("data-act") === "del") {
            api("/api/qvq/skills/delete", "POST", { name: name }).then(function (r) {
              if (r && r.undo) {
                toastUndo(t("deleted"), function () {
                  api("/api/qvq/trash/restore", "POST", { token: r.undo }).then(function () { loadSkills(); });
                });
              } else {
                toast(t("deleted"));
              }
              loadSkills();
            });
          } else {
            var skill = skills.filter(function (x) { return x.name === name; })[0];
            if (skill) openSkillModal(skill);
          }
        };
      });
    });
  }

  function bindSkillBatch(skills) {
    var list = el("qvq-skills-list");
    if (!list) return;
    var skEnter = list.querySelector("#qvq-skills-batch-enter");
    if (skEnter) skEnter.onclick = function () { skillsBatchMode = true; loadSkills(); return; };
    var skExit = list.querySelector("#qvq-skills-batch-exit");
    if (skExit) skExit.onclick = function () { skillsBatchMode = false; loadSkills(); return; };
    var all = list.querySelector("#qvq-skills-all");
    var batch = list.querySelector("#qvq-skills-batch");
    var organize = list.querySelector("#qvq-skills-organize");
    if (all) all.onchange = function () {
      list.querySelectorAll(".qvq-skill-check").forEach(function (cb) { cb.checked = all.checked; });
    };
    if (batch) batch.onclick = function () {
      var picked = [];
      list.querySelectorAll(".qvq-skill-check:checked").forEach(function (cb) { picked.push(cb.getAttribute("data-check-name")); });
      if (!picked.length) { toast(t("batch_none_selected"), true); return; }
      confirmDialog(t("batch_confirm").replace("{n}", picked.length)).then(function (ok) {
        if (!ok) return;
        api("/api/qvq/skills/batch-delete", "POST", { names: picked }).then(function (r) {
          var doneSkills = function () { toast(t("batch_deleted").replace("{n}", (r && r.removed) || 0)); loadSkills(); };
          if (r && r.undo) toastUndo(t("deleted"), function () {
            api("/api/qvq/trash/restore", "POST", { token: r.undo }).then(function () { doneSkills(); });
          }); else doneSkills();
          loadSkills();
        });
      });
    };
    if (organize) organize.onclick = function () {
      organize.disabled = true;
      organize.textContent = t("organize_running");
      api("/api/qvq/skills/organize", "POST", {}).then(function (r) {
        organize.disabled = false;
        organize.textContent = t("organize_run");
        if (r && r.ok) {
          toast(r.report === "noop" ? t("organize_noop") : t("organize_done").replace("{report}", r.report || ""));
          loadSkills();
        } else {
          toast(t("organize_fail").replace("{error}", (r && r.error) || "error"), true);
        }
      }, function () {
        organize.disabled = false;
        organize.textContent = t("organize_run");
        toast(t("organize_fail").replace("{error}", "network"), true);
      });
    };
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
    loadInto("qvq-tools-list", function () { return api("/api/qvq/tools"); }, function (box, data) {
      tools = (data && data.tools) || [];
      var riskLabel = (data && data.risk) || "risk";
      renderToolList(tools, "", riskLabel);
      var filter = el("qvq-tools-filter");
      filter.oninput = function () {
        renderToolList(tools, filter.value.trim().toLowerCase(), riskLabel);
      };
    });
    // 扩展模块小节并入工具页底部
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
    bindListSearch("qvq-mcp-search", function () { loadMcp(); });
    loadInto("qvq-mcp-list", function () { return api("/api/qvq/mcp"); }, function (box, data) {
      var q = listSearchText("qvq-mcp-search");
      var allServers = (data && data.servers) || [];
      mcpServers = q ? allServers.filter(function (srv) {
        var hay = (srv.name || "") + " " + (srv.command || "") + " " + (srv.url || "");
        return hay.toLowerCase().indexOf(q) >= 0;
      }) : allServers;
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
    loadInto("qvq-tasks-timeline", function () { return api("/api/qvq/tasks"); }, function (box, data) {
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
          "<td><button class='qvq-btn small' data-run='" + esc(task.id) + "'>" + esc(t("nav_group_run")) + "</button> " +
          "<button class='qvq-btn small danger' data-id='" + esc(task.id) + "'>" + esc(t("del")) + "</button></td></tr>";
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
      el("qvq-tasks-list").querySelectorAll("button[data-run]").forEach(function (btn) {
        btn.onclick = function () {
          api("/api/qvq/tasks/run", "POST", { id: btn.getAttribute("data-run") }).then(function (r) {
            toast(r && r.ok ? t("nav_group_run") + ": " + (r.name || "") : ((r && r.error) || "error"), !(r && r.ok));
            setTimeout(loadTasks, 800);
          });
        };
      });
    });
  }

  /* ===== 知识库：列表 / 检索 / 添加 / 删除 ===== */

  function loadKnowledge() {
    var query = (el("qvq-kb-search") || {}).value || "";
    loadInto("qvq-kb-list", function () { return api("/api/qvq/kb?q=" + encodeURIComponent(query.trim())); }, function (box, data) {
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
      var kbBatch = (kbBatchMode
        ? '<div class="qvq-actions qvq-batch-bar">' +
          '<label class="qvq-check-inline"><input type="checkbox" id="qvq-kb-all"/> ' + esc(t("batch_select_all")) + "</label>" +
          '<button type="button" class="qvq-btn small danger" id="qvq-kb-batch">' + esc(t("batch_delete")) + "</button>" +
          '<button type="button" class="qvq-btn small ghost" id="qvq-kb-batch-exit">' + esc(t("batch_exit")) + "</button>"
        : '<div class="qvq-actions qvq-batch-bar"><button type="button" class="qvq-btn small ghost" id="qvq-kb-batch-enter">' + esc(t("batch_delete")) + "…</button>") +
        '<button type="button" class="qvq-btn small ghost" id="qvq-kb-organize">' + esc(t("organize_run")) + "</button></div>";
// 三行结构：标题+标签 / 内容摘要 / 操作按钮独立列
      box.innerHTML = kbBatch + entries.map(function (entry) {
        var chips = (entry.source ? " <span class='qvq-chip qvq-kb-chip'>" + esc(entry.source) + "</span>" : "") +
          (entry.triggers && entry.triggers.length ? " <span class='qvq-chip qvq-kb-chip'>@" + esc(entry.triggers.join(", ")) + "</span>" : "") +
          (entry.priority ? " <span class='qvq-chip qvq-kb-chip'>P" + esc(entry.priority) + "</span>" : "") +
          (entry.owner ? " <span class='qvq-chip qvq-kb-chip'>" + esc(t("kb_scope_chip_private")) + ": " + esc(entry.owner) + "</span>" : "");
        var full = String(entry.content || "");
        return '<div class="qvq-kb-row" data-kb="' + esc(entry.id) + '">' +
          (kbBatchMode ? '<input type="checkbox" class="qvq-kb-check" data-check-id="' + esc(entry.id) + '"/>' : "") +
          '<div class="qvq-kb-main">' +
          '<div class="qvq-kb-head"><span class="qvq-kb-title" title="' + esc(entry.title) + '">' + esc(entry.title) + "</span>" + chips + "</div>" +
          '<div class="qvq-kb-desc" title="' + esc(full.slice(0, 500)) + '">' + esc(full.slice(0, 240)) + "</div>" +
          "</div>" +
          '<div class="qvq-kb-acts">' +
          "<button class='qvq-btn small' data-kb-edit='" + esc(entry.id) + "'>" + esc(t("kb_edit")) + "</button>" +
          "<button class='qvq-btn small danger' data-kb-del='" + esc(entry.id) + "'>" + esc(t("del")) + "</button>" +
          "</div></div>";
      }).join("");
      bindKbBatch();
      box.querySelectorAll("button[data-kb-del]").forEach(function (btn) {
        btn.onclick = function () {
          confirmDialog(t("confirm_del")).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/kb/delete", "POST", { id: btn.getAttribute("data-kb-del") }).then(function (r) {
              if (r && r.undo) {
                toastUndo(t("deleted"), function () {
                  api("/api/qvq/trash/restore", "POST", { token: r.undo }).then(function () { loadKnowledge(); });
                });
              } else {
                toast(t("deleted"));
              }
              loadKnowledge();
            });
          });
        };
      });
      box.querySelectorAll("button[data-kb-edit]").forEach(function (btn) {
        btn.onclick = function () {
          var id = btn.getAttribute("data-kb-edit");
          api("/api/qvq/kb").then(function (data) {
            var entry = ((data && data.entries) || []).filter(function (e) { return e.id === id; })[0];
            if (entry) openKbEditModal(entry);
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

  function bindKbBatch() {
    var box = el("qvq-kb-list");
    if (!box) return;
    var kbEnter = box.querySelector("#qvq-kb-batch-enter");
    if (kbEnter) kbEnter.onclick = function () { kbBatchMode = true; loadKnowledge(); return; };
    var kbExit = box.querySelector("#qvq-kb-batch-exit");
    if (kbExit) kbExit.onclick = function () { kbBatchMode = false; loadKnowledge(); return; };
    var all = box.querySelector("#qvq-kb-all");
    var batch = box.querySelector("#qvq-kb-batch");
    var organize = box.querySelector("#qvq-kb-organize");
    if (all) all.onchange = function () {
      box.querySelectorAll(".qvq-kb-check").forEach(function (cb) { cb.checked = all.checked; });
    };
    if (batch) batch.onclick = function () {
      var picked = [];
      box.querySelectorAll(".qvq-kb-check:checked").forEach(function (cb) { picked.push(cb.getAttribute("data-check-id")); });
      if (!picked.length) { toast(t("batch_none_selected"), true); return; }
      confirmDialog(t("batch_confirm").replace("{n}", picked.length)).then(function (ok) {
        if (!ok) return;
        api("/api/qvq/kb/batch-delete", "POST", { ids: picked }).then(function (r) {
          var doneKb = function () { toast(t("batch_deleted").replace("{n}", (r && r.removed) || 0)); loadKnowledge(); };
          if (r && r.undo) toastUndo(t("deleted"), function () {
            api("/api/qvq/trash/restore", "POST", { token: r.undo }).then(function () { doneKb(); });
          }); else doneKb();
          loadKnowledge();
        });
      });
    };
    if (organize) organize.onclick = function () {
      organize.disabled = true;
      organize.textContent = t("organize_running");
      api("/api/qvq/kb/organize", "POST", {}).then(function (r) {
        organize.disabled = false;
        organize.textContent = t("organize_run");
        if (r && r.ok) {
          toast(r.report === "noop" || r.report === "empty" ? t("organize_noop") : t("organize_done").replace("{report}", r.report || ""));
          loadKnowledge();
        } else {
          toast(t("organize_fail").replace("{error}", (r && r.error) || "error"), true);
        }
      }, function () {
        organize.disabled = false;
        organize.textContent = t("organize_run");
        toast(t("organize_fail").replace("{error}", "network"), true);
      });
    };
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

  // 知识库编辑：全部字段回填；scope 空=全局
  function openKbEditModal(entry) {
    var fields =
      "<label class='qvq-label'>" + esc(t("kb_title_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbe-title' value='" + esc(entry.title || "") + "' />" +
      "<label class='qvq-label'>" + esc(t("kb_source_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbe-source' value='" + esc(entry.source || "") + "' />" +
      "<label class='qvq-label'>" + esc(t("kb_triggers_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbe-triggers' value='" + esc((entry.triggers || []).join(", ")) + "' placeholder='" + esc(t("kb_triggers_ph")) + "' />" +
      "<label class='qvq-label'>" + esc(t("kb_scope_label")) + "</label>" +
      "<input class='qvq-input' id='qvq-kbe-scope' value='" + esc(entry.owner || "") + "' placeholder='" + esc(t("kb_scope_ph")) + "' />" +
      "<div class='qvq-hint'>" + esc(t("kb_scope_chat")) + "</div>" +
      "<label class='qvq-label'>" + esc(t("kb_content_label")) + "</label>" +
      "<textarea class='qvq-textarea' id='qvq-kbe-content' style='min-height:180px'>" + esc(entry.content || "") + "</textarea>";
    openForm(t("kb_edit"), fields, function (body) {
      var title = fv(body, "qvq-kbe-title");
      var content = body.querySelector("#qvq-kbe-content").value;
      if (!title.trim() || !content.trim()) {
        toast(t("kb_need_title_content"), true);
        return;
      }
      var triggers = fv(body, "qvq-kbe-triggers").split(/[,，、\s]+/).filter(Boolean);
      api("/api/qvq/kb/update", "POST", {
        id: entry.id,
        title: title,
        content: content,
        source: fv(body, "qvq-kbe-source"),
        triggers: triggers,
        scope: fv(body, "qvq-kbe-scope").trim()
      }).then(function (r) {
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

  // 用户画像卡：卡片头（标题左 + 清空右）+ 三类分节展示（含时间戳与更新时间）
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
    var sections = ["traits", "preferences", "facts"].map(function (cat) {
      var items = profile[cat] || [];
      if (!items.length) return "";
      var rows = items.map(function (item) {
        return "<tr><td>" + esc(item.text || "") + "</td><td class='qvq-col-time'>" +
          (item.ts ? esc(fmtSmart(item.ts)) : "") + "</td></tr>";
      }).join("");
      return "<h3 class='qvq-profile-sec'>" + esc(t("profile_sec_" + cat)) + " <span class='qvq-chip'>" + items.length + "</span></h3>" +
        "<table class='qvq-table'><tbody>" + rows + "</tbody></table>";
    }).join("");
    card.innerHTML =
      "<div class='qvq-card-head'><h2 class='qvq-h2'>" + esc(t("profile_card_title")) +
      (user ? " <span class='qvq-tool-desc'>" + esc(user) + "</span>" : "") + "</h2>" +
      (profile.updated ? "<span class='qvq-tool-desc'>" + esc(t("profile_updated")) + ": " + esc(fmtSmart(profile.updated)) + "</span>" : "") +
      "<button class='qvq-btn small danger' id='qvq-profile-clear'>" + esc(t("profile_card_clear")) + "</button></div>" +
      (sections
        ? sections
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
      '<div class="qvq-actions head"><button class="qvq-btn small danger" id="qvq-memory-clear">' + esc(t("memory_clear")) + "</button></div>" +
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
            return "<tr><td><span class='qvq-chip'>" + esc(entry.category || "-") + "</span> " +
              "<span class='qvq-chip' title='" + esc(t("memory_importance")) + "'>I" + esc(entry.importance) + "</span> " +
              esc(entry.content) + "</td>" +
              "<td class='qvq-col-acts'><button class='qvq-btn small danger' data-content='" + esc(entry.content) + "'><svg viewBox='0 0 24 24' class='qvq-btn-ico'><path d='M6 6l12 12M18 6L6 18'/></svg></button></td></tr>";
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

  // 会话页账户筛选（多账户隔离：@account 后缀）；空串 = 全部
  var sessionsAcctFilter = "";
  var sessionsBatchMode = false;  // 批量选择模式：点「批量删除」进入，复选框/全选栏只在该模式下显示
  var kbBatchMode = false;      // 知识库批量模式
  var skillsBatchMode = false;  // 技能批量模式

  function loadSessions() {
    api("/api/qvq/sessions").then(function (data) {
      var all = ((data && data.sessions) || []).filter(function (s) {
        return (s.turns || 0) > 0 || s.preview;
      });
      var accounts = (data && data.accounts && data.accounts.accounts) || [];
      if (sessionsAcctFilter && !accounts.some(function (a) { return a.account === sessionsAcctFilter; })) {
        sessionsAcctFilter = "";
      }
      var sessions = sessionsAcctFilter
        ? all.filter(function (s) { return accountOf(s.chat_key) === sessionsAcctFilter; })
        : all;
      if (!all.length) {
        el("qvq-sessions-list").innerHTML = '<div class="qvq-empty">' + esc(t("sessions_empty")) + "</div>";
        return;
      }
      var filterBar = accounts.length
        ? '<div class="qvq-acct-filter">' +
          '<button type="button" class="qvq-chip-btn' + (sessionsAcctFilter ? "" : " on") + '" data-acct="">' + esc(t("acct_filter_all")) + " (" + all.length + ")</button>" +
          accounts.map(function (a) {
            return '<button type="button" class="qvq-chip-btn' + (sessionsAcctFilter === a.account ? " on" : "") + '" data-acct="' + esc(a.account) + '">@' + esc(a.account) + " (" + a.sessions + ")</button>";
          }).join("") + "</div>"
        : "";
      if (!sessions.length) {
        el("qvq-sessions-list").innerHTML = filterBar + '<div class="qvq-empty">' + esc(t("sessions_empty")) + "</div>";
      } else {
      var rows = sessions.map(function (session) {
        var acct = accountOf(session.chat_key);
        var pol = sessionPolicyOf(session);
        var flags = "";
        if (session.pinned) flags += ' <span class="qvq-chip">' + esc(t("chat_pin_s")) + "</span>";
        if (session.archived) flags += ' <span class="qvq-chip">' + esc(t("chat_archived")) + "</span>";
        if (session.live) flags += ' <span class="qvq-chip live">' + esc(t("orch_running")) + "</span>";
        var checkCell = sessionsBatchMode
          ? "<td class='qvq-col-check'><input type='checkbox' class='qvq-session-check' data-check-key='" + esc(session.chat_key) + "'/></td>"
          : "";
        // muted 会话整行灰化；策略控件（屏蔽/省流/优先级）放操作列最前
        return "<tr" + (pol.muted ? " class='qvq-sess-muted'" : "") + ">" + checkCell +
          "<td><b>" + esc(sessionDisplayName(session)) + "</b>" +
          (acct ? ' <span class="qvq-acct-badge" title="@' + esc(acct) + '">@' + esc(acct) + "</span>" : "") +
          flags +
          '<div class="qvq-tool-desc">' + esc(session.chat_key) + "</div></td>" +
          "<td>" + esc(session.persona || "-") + "</td>" +
          "<td>" + esc(session.turns) + "</td><td class='qvq-tool-desc'>" + esc(session.preview || "-") + "</td>" +
          "<td class='qvq-col-time'>" + esc(fmtTime(session.updated)) + "</td>" +
          "<td>" + sessPolicyCellHtml(session.chat_key) +
          "<button class='qvq-btn small ghost' data-view='" + esc(session.chat_key) + "'>" + esc(t("sessions_msgs")) + "</button> " +
          "<button class='qvq-btn small ghost' data-access='" + esc(session.chat_key) + "'>" + esc(t("sess_members")) + "</button> " +
          "<button class='qvq-btn small danger' data-key='" + esc(session.chat_key) + "'>" + esc(t("reset_btn")) + "</button></td></tr>";
      }).join("");
      var sessionBatch = sessionsBatchMode
        ? '<div class="qvq-actions qvq-batch-bar">' +
          '<label class="qvq-check-inline"><input type="checkbox" id="qvq-sessions-all"/> ' + esc(t("batch_select_all")) + "</label>" +
          '<button type="button" class="qvq-btn small danger" id="qvq-sessions-batch">' + esc(t("batch_delete")) + "</button>" +
          '<button type="button" class="qvq-btn small ghost" id="qvq-sessions-batch-exit">' + esc(t("batch_exit")) + "</button></div>"
        : '<div class="qvq-actions qvq-batch-bar"><button type="button" class="qvq-btn small ghost" id="qvq-sessions-batch-enter">' + esc(t("batch_delete")) + "…</button></div>";
      var headCheck = sessionsBatchMode ? "<th></th>" : "";
      el("qvq-sessions-list").innerHTML = filterBar + sessionBatch + "<table class='qvq-table'><thead><tr>" + headCheck + "<th>" + esc(t("col_chatkey")) + "</th><th>" + esc(t("col_persona")) +
        "</th><th>" + esc(t("col_turns")) + "</th><th>" + esc(t("col_preview")) + "</th><th>" + esc(t("col_updated")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
      }
      el("qvq-sessions-list").querySelectorAll(".qvq-acct-filter .qvq-chip-btn").forEach(function (chip) {
        chip.onclick = function () {
          sessionsAcctFilter = chip.getAttribute("data-acct") || "";
          loadSessions();
        };
      });
      bindSessionBatch();
      bindSessionPolicyControls(el("qvq-sessions-list"), sessions);
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

  function bindSessionBatch() {
    var box = el("qvq-sessions-list");
    if (!box) return;
    var enter = box.querySelector("#qvq-sessions-batch-enter");
    if (enter) enter.onclick = function () { sessionsBatchMode = true; loadSessions(); return; };
    var exit = box.querySelector("#qvq-sessions-batch-exit");
    if (exit) exit.onclick = function () { sessionsBatchMode = false; loadSessions(); return; };
    var all = box.querySelector("#qvq-sessions-all");
    var batch = box.querySelector("#qvq-sessions-batch");
    if (all) all.onchange = function () {
      box.querySelectorAll(".qvq-session-check").forEach(function (cb) { cb.checked = all.checked; });
    };
    if (batch) batch.onclick = function () {
      var picked = [];
      box.querySelectorAll(".qvq-session-check:checked").forEach(function (cb) { picked.push(cb.getAttribute("data-check-key")); });
      if (!picked.length) { toast(t("batch_none_selected"), true); return; }
      confirmDialog(t("batch_confirm").replace("{n}", picked.length)).then(function (ok) {
        if (!ok) return;
        api("/api/qvq/sessions/batch-delete", "POST", { chat_keys: picked }).then(function (r) {
          toast(t("batch_deleted").replace("{n}", (r && r.removed) || 0));
          loadSessions();
          loadChatMeta();
        });
      });
    };
  }

  // ===== 存储管理：全库浏览 / 分域清理 / 一键重置 =====

  function fmtBytes(n) {
    n = Number(n) || 0;
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    if (n < 1024 * 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
    return (n / 1024 / 1024 / 1024).toFixed(2) + " GB";
  }

  function storageDomainLabel(id) {
    return t("storage_d_" + id);
  }

  var storageDomainOpen = "";

  function loadStorage() {
    api("/api/qvq/storage").then(function (data) {
      var total = el("qvq-storage-total");
      if (total) total.innerHTML = esc(t("storage_total")) + " <b>" + esc(fmtBytes((data && data.total_bytes) || 0)) + "</b>";
      var box = el("qvq-storage-domains");
      if (!box) return;
      var domains = (data && data.domains) || [];
      var files = (data && data.files) || [];
      if (!domains.length && !files.length) {
        box.innerHTML = '<div class="qvq-empty">' + esc(t("storage_empty")) + "</div>";
        return;
      }
      var rows = domains.map(function (d) {
        return "<tr><td><b>" + esc(storageDomainLabel(d.id)) + "</b><div class='qvq-tool-desc'>" + esc(d.id) + "</div></td>" +
          "<td>" + esc(d.keys) + "</td><td><b>" + esc(fmtBytes(d.bytes)) + "</b></td>" +
          "<td><button class='qvq-btn small ghost' data-keys='" + esc(d.id) + "'>" + esc(t("storage_browse")) + "</button> " +
          "<button class='qvq-btn small danger' data-clear='" + esc(d.id) + "'>" + esc(t("storage_clear")) + "</button></td></tr>";
      });
      rows = rows.concat(files.map(function (f) {
        return "<tr><td><b>" + esc(storageDomainLabel(f.id)) + "</b><div class='qvq-tool-desc'>" + esc(f.path) + "</div></td>" +
          "<td>" + esc(f.files) + " 文件</td><td><b>" + esc(fmtBytes(f.bytes)) + "</b></td>" +
          "<td><button class='qvq-btn small danger' data-clear='" + esc(f.id) + "'>" + esc(t("storage_clear")) + "</button></td></tr>";
      }));
      box.innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("storage_domain")) + "</th><th>" + esc(t("storage_count")) +
        "</th><th>" + esc(t("storage_size")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" + rows.join("") + "</tbody></table>";
      // 回收站节：列出可撤销项，支持恢复/彻底删除
      api("/api/qvq/trash/list").then(function (tl) {
        var items = (tl && tl.items) || [];
        var card = el("qvq-trash-card");
        if (!card) return;
        if (!items.length) {
          card.innerHTML = '<div class="qvq-empty">' + esc(t("trash_empty")) + "</div>";
          return;
        }
        card.innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("bind_key_col")) + "</th><th>" + esc(t("storage_domain")) +
          "</th><th>" + esc(t("trash_expires")) + "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" +
          items.map(function (it) {
            return "<tr><td>" + esc(it.summary) + "</td><td><span class='qvq-chip'>" + esc(it.kind) + "</span></td>" +
              "<td>" + (it.expires_in >= 0 ? Math.ceil(it.expires_in / 86400) + " " + esc(t("trash_days")) : "-") + "</td>" +
              "<td><button class='qvq-btn small ghost' data-trash-restore='" + esc(it.token) + "'>" + esc(t("trash_restore")) + "</button> " +
              "<button class='qvq-btn small danger' data-trash-drop='" + esc(it.token) + "'>" + esc(t("del")) + "</button></td></tr>";
          }).join("") + "</tbody></table>";
        card.querySelectorAll("button[data-trash-restore]").forEach(function (btn) {
          btn.onclick = function () {
            api("/api/qvq/trash/restore", "POST", { token: btn.getAttribute("data-trash-restore") }).then(function (r) {
              toast(r && r.ok ? t("saved") : ((r && r.error) || "error"), !(r && r.ok));
              loadStorage();
            });
          };
        });
        card.querySelectorAll("button[data-trash-drop]").forEach(function (btn) {
          btn.onclick = function () {
            api("/api/qvq/trash/delete", "POST", { token: btn.getAttribute("data-trash-drop") }).then(function () {
              toast(t("deleted"));
              loadStorage();
            });
          };
        });
      });
      box.querySelectorAll("button[data-clear]").forEach(function (btn) {
        btn.onclick = function () {
          var id = btn.getAttribute("data-clear");
          confirmDialog(t("storage_confirm_clear").replace("{d}", storageDomainLabel(id))).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/storage/cleanup", "POST", { domains: [id] }).then(function (r) {
              toast(t("storage_cleared").replace("{n}", (r && r.removed) || 0) + " · " + fmtBytes((r && r.freed) || 0));
              loadStorage();
            });
          });
        };
      });
      box.querySelectorAll("button[data-keys]").forEach(function (btn) {
        btn.onclick = function () { loadStorageKeys(btn.getAttribute("data-keys")); };
      });
      var section = document.querySelector(".qvq-tab[data-section='storage']");
      var trashCard = el("qvq-trash-card");
      if (!trashCard && section) {
        trashCard = document.createElement("div");
        trashCard.className = "qvq-card";
        trashCard.id = "qvq-trash-card";
        trashCard.innerHTML = "<h3 class='qvq-card-title'>" + esc(t("trash_page")) + "</h3><div class='qvq-tool-desc'>" + esc(t("trash_hint")) + "</div><div class='qvq-empty'>…</div>";
        section.appendChild(trashCard);
      }
    });
    var refresh = el("qvq-storage-refresh");
    if (refresh) refresh.onclick = loadStorage;
    var slim = el("qvq-storage-slim");
    if (slim) slim.onclick = function () {
      api("/api/qvq/storage/slim", "POST", {}).then(function (r) {
        toast(t("storage_slim_done").replace("{n}", (r && r.sessions) || 0) + " · " + fmtBytes((r && r.freed) || 0));
        loadStorage();
      });
    };
    // 批量压缩：全部会话历史浓缩为摘要
    var compactBtn = el("qvq-storage-compact");
    if (compactBtn) compactBtn.onclick = function () {
      confirmDialog(t("storage_compact_confirm")).then(function (ok) {
        if (!ok) return;
        compactBtn.disabled = true;
        api("/api/qvq/storage/compact-sessions", "POST", {}).then(function (r) {
          compactBtn.disabled = false;
          if (r && r.ok) {
            toast(t("storage_compact_done").replace("{n}", (r.sessions) || 0) + " · -" + fmtBytes((r.freed_chars) || 0));
            loadStorage();
          } else {
            toast((r && r.error) || "error", true);
          }
        }).catch(function () { compactBtn.disabled = false; });
      });
    };
    var reset = el("qvq-storage-reset");
    if (reset) reset.onclick = openStorageReset;
    var exportBtns = [["qvq-export-san", true], ["qvq-export-full", false]];
    exportBtns.forEach(function (pair) {
      var btn = el(pair[0]);
      if (!btn) return;
      btn.onclick = function () {
        downloadExport("/api/qvq/export?format=zip&sanitize=" + (pair[1] ? "1" : "0"),
          "qvqchat-export-" + new Date().toISOString().slice(0, 10) + (pair[1] ? "-sanitized" : "") + ".zip", btn);
      };
    });
    var pickBtn = el("qvq-export-pick");
    if (pickBtn) pickBtn.onclick = openExportModal;
    var importBtn = el("qvq-import-btn");
    if (importBtn) importBtn.onclick = openImportModal;
    if (storageDomainOpen) loadStorageKeys(storageDomainOpen);
  }

  function downloadExport(url, filename, btn) {
    if (btn) btn.disabled = true;
    apiBlob(url).then(function (blob) {
      if (btn) btn.disabled = false;
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      toast(t("saved"));
    }).catch(function (e) {
      if (btn) btn.disabled = false;
      toast((e && e.message) || "error", true);
    });
  }

  // ===== 导出/导入：内容选择 + 合并策略（覆盖 / 追加 / 跳过）=====

  var EXPORT_GROUPS = [
    ["export_grp_data", [["config", "export_sec_config"], ["models", "export_sec_models"], ["personas", "export_sec_personas"],
      ["tasks", "export_sec_tasks"], ["memory", "export_sec_memory"], ["skills", "export_sec_skills"], ["mcp", "export_sec_mcp"]]],
    ["export_grp_storage", [["sessions", "storage_d_sessions"], ["memories", "storage_d_memories"], ["profiles", "storage_d_profiles"],
      ["personas", "storage_d_personas"], ["knowledge", "storage_d_knowledge"], ["audit", "storage_d_audit"], ["usage", "storage_d_usage"],
      ["tasks", "storage_d_tasks"], ["participation", "storage_d_participation"], ["shares", "storage_d_shares"],
      ["recall", "storage_d_recall"], ["pending", "storage_d_pending"], ["trash", "storage_d_trash"],
      ["docs", "storage_d_docs"], ["settings", "storage_d_settings"], ["other", "storage_d_other"]]],
    ["export_grp_files", [["uploads", "storage_d_uploads"], ["work", "storage_d_work"], ["docs_cache", "storage_d_docs_cache"]]],
  ];

  var STRATEGIES = [["overwrite", "strategy_overwrite"], ["append", "strategy_append"], ["skip", "strategy_skip"]];

  function strategySelect(id) {
    var html = "<select class='qvq-input' id='" + id + "'>";
    STRATEGIES.forEach(function (pair) {
      html += "<option value='" + pair[0] + "'>" + esc(t(pair[1])) + "</option>";
    });
    return html + "</select>";
  }

  function openExportModal() {
    var html = "";
    EXPORT_GROUPS.forEach(function (group) {
      html += "<div class='qvq-label'>" + esc(t(group[0])) + "</div><div style='display:flex;flex-wrap:wrap;gap:8px 14px;margin-bottom:6px'>";
      group[1].forEach(function (p) {
        html += "<label style='display:flex;align-items:center;gap:5px'><input type='checkbox' data-exp-sec='" + p[0] + "' checked /> " + esc(t(p[1])) + "</label>";
      });
      html += "</div>";
    });
    html += "<label style='display:flex;align-items:center;gap:6px;margin-top:10px'><input type='checkbox' id='qvq-exp-san' checked /> " +
      esc(t("storage_export_hint")) + "</label>";
    openForm(t("storage_export_pick"), html, function (body) {
      var secs = [];
      body.querySelectorAll("input[data-exp-sec]:checked").forEach(function (input) {
        if (secs.indexOf(input.getAttribute("data-exp-sec")) === -1) secs.push(input.getAttribute("data-exp-sec"));
      });
      if (!secs.length) {
        toast(t("export_none_selected"), true);
        return;
      }
      var san = body.querySelector("#qvq-exp-san").checked;
      closeModal();
      downloadExport("/api/qvq/export?format=zip&sanitize=" + (san ? "1" : "0") +
        "&domains=" + encodeURIComponent(secs.join(",")),
        "qvqchat-export-" + new Date().toISOString().slice(0, 10) + (san ? "-sanitized" : "") + ".zip");
    });
  }

  function openImportModal() {
    var html =
      "<label class='qvq-label'>" + esc(t("import_file_label")) + "</label>" +
      "<input type='file' id='qvq-imp-file' accept='.json,.zip' class='qvq-input' />" +
      "<div id='qvq-imp-body' style='margin-top:10px'></div>" +
      "<div class='qvq-actions'><button class='qvq-btn' data-imp-apply disabled>" + esc(t("import_apply")) + "</button>" +
      "<button class='qvq-btn ghost' data-imp-cancel>" + esc(t("cancel")) + "</button></div>";
    openModal(t("storage_import"), html);
    var body = el("qvq-modal-body");
    body.querySelector("[data-imp-cancel]").onclick = closeModal;
    var pending = null; // {kind: json|zip, data|b64}
    var fileInput = body.querySelector("#qvq-imp-file");
    fileInput.onchange = function () {
      var file = this.files[0];
      if (!file) return;
      pending = null;
      var applyBtn = body.querySelector("[data-imp-apply]");
      applyBtn.disabled = true;
      var box = body.querySelector("#qvq-imp-body");
      if (/.zip$/i.test(file.name)) {
        var reader = new FileReader();
        reader.onload = function () {
          var bytes = new Uint8Array(reader.result);
          var bin = "";
          for (var i = 0; i < bytes.length; i += 0x8000) {
            bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
          }
          var b64 = btoa(bin);
          api("/api/qvq/import/zip", "POST", { data_b64: b64, peek: true }).then(function (info) {
            if (info && info.error) {
              box.innerHTML = '<div class="qvq-empty">' + esc(info.error) + "</div>";
              return;
            }
            pending = { kind: "zip", b64: b64, sections: info.sections || [], files: info.files || [] };
            renderImportSections(body, pending, applyBtn);
          });
        };
        reader.readAsArrayBuffer(file);
      } else {
        var textReader = new FileReader();
        textReader.onload = function () {
          var parsed;
          try {
            parsed = JSON.parse(textReader.result);
          } catch (e) {
            box.innerHTML = '<div class="qvq-empty">' + esc(t("import_failed")) + "</div>";
            return;
          }
          pending = { kind: "json", data: parsed, sections: detectedSections(parsed), files: [] };
          renderImportSections(body, pending, applyBtn);
        };
        textReader.readAsText(file);
      }
    };
    body.querySelector("[data-imp-apply]").onclick = function () {
      if (!pending) return;
      var sections = [];
      body.querySelectorAll("input[data-imp-sec]:checked").forEach(function (input) {
        sections.push(input.getAttribute("data-imp-sec"));
      });
      var strategies = {};
      body.querySelectorAll("select[data-imp-strategy]").forEach(function (sel) {
        strategies[sel.getAttribute("data-imp-strategy")] = sel.value;
      });
      if (pending.kind === "json") {
        api("/api/qvq/import", "POST", { data: pending.data, sections: sections, strategies: strategies }).then(function (r) {
          if (r && r.ok) {
            toast(t("import_done").replace("{n}", (r.applied || []).length));
            closeModal();
          } else {
            toast((r && r.error) || t("import_failed"), true);
          }
        });
      } else {
        api("/api/qvq/import/zip", "POST", { data_b64: pending.b64, sections: sections, strategies: strategies }).then(function (r) {
          if (r && r.ok) {
            toast(t("import_done").replace("{n}", (r.applied || []).length + (r.files_restored || 0)));
            closeModal();
            loadStorage();
          } else {
            toast((r && r.error) || t("import_failed"), true);
          }
        });
      }
    };
  }

  function detectedSections(data) {
    var order = ["models", "personas", "tasks", "memory", "mcp", "skills", "config", "storage"];
    var found = [];
    order.forEach(function (key) {
      var value = data && data[key];
      if (Array.isArray(value) ? value.length : (value && typeof value === "object" && Object.keys(value).length)) {
        found.push(key);
      }
    });
    return found;
  }

  var SECTION_LABELS = {
    models: "export_sec_models", personas: "export_sec_personas", tasks: "export_sec_tasks",
    memory: "export_sec_memory", mcp: "export_sec_mcp", skills: "export_sec_skills",
    config: "export_sec_config", storage: "export_sec_storage", files: "storage_d_uploads"
  };

  function renderImportSections(body, pending, applyBtn) {
    var box = body.querySelector("#qvq-imp-body");
    var names = (pending.sections || []).slice();
    if (pending.kind === "zip" && (pending.files || []).length) names.push("files");
    if (!names.length) {
      box.innerHTML = '<div class="qvq-empty">' + esc(t("import_nothing")) + "</div>";
      return;
    }
    var html = "";
    names.forEach(function (name) {
      html += "<div style='display:flex;align-items:center;gap:10px;margin-bottom:6px'>" +
        "<label style='display:flex;align-items:center;gap:5px;flex:1'><input type='checkbox' data-imp-sec='" + esc(name) + "' checked /> " +
        esc(t(SECTION_LABELS[name] || name)) + "</label>" + strategySelect("strat-" + name).replace("<select ", "<select data-imp-strategy='" + esc(name) + "' ") + "</div>";
    });
    box.innerHTML = html;
    applyBtn.disabled = false;
  }

  function loadStorageKeys(domain) {
    storageDomainOpen = domain;
    var box = el("qvq-storage-keys");
    if (!box) return;
    box.innerHTML = '<div class="qvq-chat-loading">' + HERO_SVG + '<span class="qvq-chat-loading-tx">' + esc(storageDomainLabel(domain)) + "</span></div>";
    api("/api/qvq/storage/keys?domain=" + encodeURIComponent(domain)).then(function (data) {
      if (storageDomainOpen !== domain) return;
      var keys = (data && data.keys) || [];
      if (!keys.length) {
        box.innerHTML = '<div class="qvq-empty">' + esc(t("storage_no_keys")) + "</div>";
        return;
      }
      box.innerHTML = "<table class='qvq-table'><thead><tr><th>" + esc(t("storage_key_col")) + "</th><th>" + esc(t("storage_size")) +
        "</th><th>" + esc(t("actions")) + "</th></tr></thead><tbody>" +
        keys.map(function (k) {
          return "<tr><td class='qvq-storage-key'>" + esc(k.key) + "</td><td>" + esc(fmtBytes(k.bytes)) + "</td>" +
            "<td><button class='qvq-btn small ghost' data-entry='" + esc(k.key) + "'>" + esc(t("view")) + "</button> " +
            "<button class='qvq-btn small danger' data-del='" + esc(k.key) + "'>" + esc(t("del")) + "</button></td></tr>";
        }).join("") + "</tbody></table>";
      box.querySelectorAll("button[data-entry]").forEach(function (btn) {
        btn.onclick = function () { viewStorageEntry(btn.getAttribute("data-entry")); };
      });
      box.querySelectorAll("button[data-del]").forEach(function (btn) {
        btn.onclick = function () {
          var key = btn.getAttribute("data-del");
          confirmDialog(key).then(function (ok) {
            if (!ok) return;
            api("/api/qvq/storage/delete", "POST", { keys: [key] }).then(function () {
              toast(t("deleted"));
              loadStorageKeys(domain);
              loadStorage();
            });
          });
        };
      });
    });
  }

  function viewStorageEntry(key) {
    openModal(key, '<div class="qvq-chat-loading">' + HERO_SVG + '<span class="qvq-chat-loading-tx">QvQ Chat</span></div>');
    api("/api/qvq/storage/entry?key=" + encodeURIComponent(key)).then(function (data) {
      var body = el("qvq-modal-body");
      if (!body) return;
      if (!data || data.__http >= 400) { body.innerHTML = '<div class="qvq-empty">' + esc((data && data.error) || "error") + "</div>"; return; }
      body.innerHTML = (data.truncated ? '<div class="qvq-tool-desc">' + esc(t("storage_truncated")) + "</div>" : "") +
        '<pre class="qvq-step-detail qvq-storage-entry">' + esc(data.value || "") + "</pre>";
    }, function () {
      var body = el("qvq-modal-body");
      if (body) body.innerHTML = '<div class="qvq-empty">error</div>';
    });
  }

  function openStorageReset() {
    var ids = ["sessions", "memories", "profiles", "personas", "knowledge", "audit", "usage", "tasks",
      "participation", "shares", "trash", "recall", "pending", "models", "mcp", "docs", "docs_cache", "uploads", "work", "settings"];
    var html = '<div class="qvq-tool-desc">' + esc(t("storage_reset_hint")) + "</div>" +
      ids.map(function (id) {
        return '<label class="qvq-check-inline"><input type="checkbox" class="qvq-reset-keep" value="' + esc(id) + '"/> ' + esc(storageDomainLabel(id)) + "</label>";
      }).join(" ") +
      '<div class="qvq-settings-danger" style="margin-top:10px">' + esc(t("storage_reset_warn")) + "</div>";
    openModal(t("storage_reset"), html);
    var body = el("qvq-modal-body");
    var actions = document.createElement("div");
    actions.className = "qvq-actions";
    actions.innerHTML = '<button class="qvq-btn danger" id="qvq-reset-go">' + esc(t("storage_reset")) + "</button>";
    body.appendChild(actions);
    actions.querySelector("#qvq-reset-go").onclick = function () {
      var keep = [];
      body.querySelectorAll(".qvq-reset-keep:checked").forEach(function (cb) { keep.push(cb.value); });
      confirmDialog(t("storage_reset_confirm")).then(function (ok) {
        if (!ok) return;
        api("/api/qvq/storage/cleanup", "POST", { reset: true, keep: keep }).then(function (r) {
          toast(t("storage_cleared").replace("{n}", (r && r.removed) || 0) + " · " + fmtBytes((r && r.freed) || 0));
          closeModal();
          storageDomainOpen = "";
          loadStorage();
        });
      });
    };
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

  function listSearchText(id) {
    var node = el(id);
    return node ? node.value.trim().toLowerCase() : "";
  }

  function bindListSearch(id, refresh) {
    var node = el(id);
    if (!node || node.dataset.bound) return;
    node.dataset.bound = "1";
    var timer = null;
    node.oninput = function () {
      if (timer) clearTimeout(timer);
      timer = setTimeout(refresh, 200);
    };
  }

  var auditLoaded = { entries: [], total: 0 };

  function loadAudit() {
    auditLoaded.entries = [];
    loadInto("qvq-audit-list", function () { return fetchAuditPage(0); }, function (box, data) {
      auditLoaded.entries = (data && data.entries) || [];
      auditLoaded.total = (data && data.total) || auditLoaded.entries.length;
      renderAudit();
    });
  }

  function fetchAuditPage(offset) {
    return api("/api/qvq/audit?limit=200&offset=" + offset);
  }

  function renderAudit() {
    var entries = auditLoaded.entries;
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
      { cap: t("audit_total"), num: auditLoaded.total },
      { cap: t("audit_tools_n"), num: Object.keys(tools).length },
      { cap: t("audit_users_n"), num: Object.keys(users).length },
      { cap: t("audit_last24h"), num: last24 }
    ];
    el("qvq-audit-stats").innerHTML = cards.map(function (c) {
      return '<div class="qvq-stat"><div class="num">' + esc(c.num) + '</div><div class="cap">' + esc(c.cap) + "</div></div>";
    }).join("");
    var render = function (keyword) {
      entries.forEach(function (e, gi) { e.global_index = gi; });
      var shown = entries.filter(function (e) {
        if (!keyword) return true;
        return (e.tool || "").toLowerCase().indexOf(keyword) >= 0 ||
          (e.user_id || "").indexOf(keyword) >= 0 ||
          (e.origin || "").toLowerCase().indexOf(keyword) >= 0 ||
          (e.chat_key || "").toLowerCase().indexOf(keyword) >= 0 ||
          JSON.stringify(e.detail || {}).toLowerCase().indexOf(keyword) >= 0;
      });
      if (!shown.length) {
        el("qvq-audit-list").innerHTML = '<div class="qvq-empty">' + esc(t("audit_empty")) + "</div>";
        return;
      }
      var rows = shown.map(function (entry, idx) {
        return "<tr class='qvq-audit-row' data-idx='" + idx + "'>" +
          "<td class='qvq-col-check'><input type='checkbox' class='qvq-audit-check' data-check-idx='" + idx + "'/></td>" +
          "<td class='qvq-col-time'>" + esc(fmtTime(entry.ts)) + "</td>" +
          "<td><b>" + esc(entry.tool) + "</b></td>" +
          "<td>" + esc(entry.user_id || "-") + "</td>" +
          "<td>" + esc(entry.origin || "-") + "</td>" +
          "<td class='qvq-tool-desc qvq-audit-detail'>" + esc(auditSummary(entry)) + "</td></tr>";
      }).join("");
      var more = "";
      if (entries.length < auditLoaded.total) {
        more = '<div class="qvq-actions" style="justify-content:center"><button type="button" class="qvq-btn small ghost" id="qvq-audit-more">' +
          esc(t("load_more")) + " (" + entries.length + "/" + auditLoaded.total + ")</button></div>";
      }
      var batchBar = '<div class="qvq-actions qvq-batch-bar">' +
        '<label class="qvq-check-inline"><input type="checkbox" id="qvq-audit-all"/> ' + esc(t("batch_select_all")) + "</label>" +
        '<button type="button" class="qvq-btn small danger" id="qvq-audit-batch">' + esc(t("batch_delete")) + "</button>" +
        '<button type="button" class="qvq-btn small ghost" id="qvq-audit-clear">' + esc(t("audit_clear")) + "</button></div>";
      el("qvq-audit-list").innerHTML = batchBar + "<table class='qvq-table'><thead><tr><th></th><th>" + esc(t("col_time")) + "</th><th>" + esc(t("col_tool")) +
        "</th><th>" + esc(t("col_user")) + "</th><th>" + esc(t("col_origin")) + "</th><th>" + esc(t("col_detail")) + "</th></tr></thead><tbody>" + rows + "</tbody></table>" + more;
      bindAuditBatch(shown);
      el("qvq-audit-list").querySelectorAll("tr.qvq-audit-row").forEach(function (tr) {
        tr.onclick = function (ev) {
          if (ev.target && ev.target.classList && ev.target.classList.contains("qvq-audit-check")) return;
          var entry = shown[parseInt(tr.getAttribute("data-idx"), 10)];
          if (entry) showAuditModal(entry);
        };
      });
      var moreBtn = el("qvq-audit-more");
      if (moreBtn) {
        moreBtn.onclick = function () {
          moreBtn.disabled = true;
          fetchAuditPage(auditLoaded.entries.length).then(function (data) {
            if (data && Array.isArray(data.entries)) {
              auditLoaded.entries = auditLoaded.entries.concat(data.entries);
              auditLoaded.total = data.total || auditLoaded.total;
            }
            renderAudit();
          }, function () { renderAudit(); });
        };
      }
    };
    filter.oninput = function () { render(filter.value.trim().toLowerCase()); };
    render(filter.value.trim().toLowerCase());
  }

  function bindAuditBatch(shown) {
    var list = el("qvq-audit-list");
    if (!list) return;
    var all = list.querySelector("#qvq-audit-all");
    var batch = list.querySelector("#qvq-audit-batch");
    var clear = list.querySelector("#qvq-audit-clear");
    if (all) all.onchange = function () {
      list.querySelectorAll(".qvq-audit-check").forEach(function (cb) { cb.checked = all.checked; });
    };
    if (batch) batch.onclick = function () {
      var picked = [];
      list.querySelectorAll(".qvq-audit-check:checked").forEach(function (cb) {
        var idx = parseInt(cb.getAttribute("data-check-idx"), 10);
        var entry = shown[idx];
        if (entry && entry.global_index != null) picked.push(entry.global_index);
      });
      if (!picked.length) { toast(t("batch_none_selected"), true); return; }
      confirmDialog(t("batch_confirm").replace("{n}", picked.length)).then(function (ok) {
        if (!ok) return;
        api("/api/qvq/audit/delete", "POST", { indexes: picked }).then(function (r) {
          toast(t("batch_deleted").replace("{n}", (r && r.removed) || 0));
          loadAudit();
        });
      });
    };
    if (clear) clear.onclick = function () {
      confirmDialog(t("audit_clear_confirm")).then(function (ok) {
        if (!ok) return;
        api("/api/qvq/audit/delete", "POST", { clear: true }).then(function () {
          toast(t("audit_cleared"));
          loadAudit();
        });
      });
    };
  }

  var settingsFields = [];
  var settingsGroupsTable = [];
  var settingsOriginal = {};   // key → 加载时的规范化值（dirty 基准）
  var settingsDraft = {};      // key → 当前编辑值（跨分类切换/搜索重绘保留）
  var settingsEnums = { tools: [], skills: [] };
  var settingsEventsBound = false;
  // 插件设置（qvq_settings 注册项）：独立拉取后并入统一 schema
  var settingsConfigFields = [];
  var settingsPluginFields = [];
  var PLUGIN_KEY_PREFIX = "plugin:";

  // chat 组语义分块（字段 order 上界 → 小节标题键）
  var CHAT_SECTIONS = [
    { max: 18, key: "settings_sec_context" },
    { max: 30, key: "settings_sec_forward" },
    { max: 42, key: "settings_sec_reply" },
    { max: 51, key: "settings_sec_flow" },
    { max: 58, key: "settings_sec_opening" },
    { max: 68, key: "settings_sec_access" },
    { max: 76, key: "settings_sec_output" },
    { max: 80, key: "settings_sec_send" },
    { max: 999, key: "settings_sec_misc" }
  ];

// 全分组语义小节：组 id → [(order 上界, 标题键)]；命中即插入小节标题
  var GROUP_SECTIONS = {
    model: [[3, "settings_sec_model_basic"], [6, "settings_sec_model_reliable"], [999, "settings_sec_model_routing"]],
    trigger: [[2, "settings_sec_trigger_reply"], [999, "settings_sec_trigger_prefix"]],
    tools: [[3, "settings_sec_tools_limits"], [7, "settings_sec_tools_behavior"], [13, "settings_sec_tools_select"], [999, "settings_sec_tools_web"]],
    mcp: [[1, "settings_sec_mcp_conn"], [999, "settings_sec_mcp_docs"]],
    eco: [[2, "settings_sec_eco_scope"], [999, "settings_sec_eco_access"]],
    memory: [[2, "settings_sec_memory_basic"], [999, "settings_sec_memory_profile"]],
    kb: [[4, "settings_sec_kb_inject"], [7, "settings_sec_kb_lore"], [999, "settings_sec_kb_embed"]],
    skills: [[2, "settings_sec_skills_manage"], [999, "settings_sec_skills_dev"]],
    humanize: [[3, "settings_sec_hu_debounce"], [7, "settings_sec_hu_filter"], [999, "settings_sec_hu_more"]],
    security: [[4, "settings_sec_sec_admin"], [999, "settings_sec_sec_danger"]]
  };

  function groupSectionHeader(group, order) {
    var table = group === "chat" ? null : GROUP_SECTIONS[group];
    if (!table) return "";
    for (var i = 0; i < table.length; i++) {
      if ((order || 99) <= table[i][0]) return table[i][1];
    }
    return "";
  }

  function settingsSchemaOf(key) {
    for (var i = 0; i < settingsFields.length; i++) {
      if (settingsFields[i].key === key) return settingsFields[i];
    }
    return null;
  }

  function loadSettings() {
    bindSettingsSearch();
    bindSettingsFormEvents();
    var keysBtn = el("qvq-settings-keys");
    if (keysBtn && !keysBtn.dataset.bound) {
      keysBtn.dataset.bound = "1";
      try {
        if (localStorage.getItem("qvq_show_keys") === "1") document.body.classList.add("qvq-show-keys");
      } catch (e) {}
      keysBtn.onclick = function () {
        var on = document.body.classList.toggle("qvq-show-keys");
        try { localStorage.setItem("qvq_show_keys", on ? "1" : "0"); } catch (e) {}
      };
    }
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
  var SETTINGS_DRAFT_KEY = "qvq_settings_draft";

  function settingsLoadPersistedDraft() {
// 本地草稿：刷新后恢复未保存的编辑（仅收编当前 schema 存在的键）
    try {
      var saved = JSON.parse(localStorage.getItem(SETTINGS_DRAFT_KEY) || "null");
      if (saved && typeof saved === "object") return saved;
    } catch (e) {}
    return null;
  }

  function settingsPersistDraft() {
    try { localStorage.setItem(SETTINGS_DRAFT_KEY, JSON.stringify(settingsDraft)); } catch (e) {}
  }

  function settingsClearPersistedDraft() {
    try { localStorage.removeItem(SETTINGS_DRAFT_KEY); } catch (e) {}
  }

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
    var saved = settingsLoadPersistedDraft();
    if (saved) {
      Object.keys(settingsDraft).forEach(function (k) {
        if (k in saved) settingsDraft[k] = saved[k];
      });
    }
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

  // 列表勾选组（动态工具注入/权限覆盖等 list 字段）接管为 qvMulti 多选下拉：
  // 原生 checkbox 隐藏保留在 .qvq-list-checks 容器内，序列化仍读 :checked，change 冒泡照常收草稿
  function enhanceSettingsChecks(scope) {
    (scope || el("qvq-settings-form")).querySelectorAll(".qvq-list-checks").forEach(function (div) {
      if (div.getAttribute("data-qvq-multi")) return;
      div.setAttribute("data-qvq-multi", "1");
      div.classList.add("qvq-multi-host");
      qvMulti.wrap(div.querySelectorAll("input[data-val]"));
    });
  }

  function refreshSettingsChecks(source) {
    var box = el("qvq-settings-form");
    if (!box) return;
    box.querySelectorAll("[data-checks]").forEach(function (node) {
      var f = settingsSchemaOf(node.getAttribute("data-key"));
      if (f && f.items === source) {
        // 重绘前先摘 data-qvq-multi 标记，重建后重新接管
        node.removeAttribute("data-qvq-multi");
        node.innerHTML = settingsChecksHtml(f, settingsDraft[f.key]);
        enhanceSettingsChecks(); // 全表扫描（node 自身即宿主，后代查询匹配不到）
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
// 单字符串/多行字符串统一收成数组；序列化端永远输出数组
      var arr = Array.isArray(value) ? value : String(value == null ? "" : value).split("\n");
      return arr.map(function (x) { return String(x).trim(); }).filter(Boolean);
    }
    if (type === "bool") return !!value;
    if (type === "dict") return value && typeof value === "object" ? value : {};
    return String(value == null ? "" : value);
  }

  // dirty 比较：数组忽略顺序（多选框按枚举顺序渲染，与存储顺序无关），标量走 JSON
  function settingsSameValue(a, b) {
    if (Array.isArray(a) && Array.isArray(b)) {
      if (a.length !== b.length) return false;
      var ka = a.slice().sort();
      var kb = b.slice().sort();
      for (var i = 0; i < ka.length; i++) {
        if (String(ka[i]) !== String(kb[i])) return false;
      }
      return true;
    }
    return JSON.stringify(a) === JSON.stringify(b);
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
      var n = settingsFields.filter(function (f) { return f.group === g; }).length;
      return "<button class='qvq-cat-btn" + (g === currentCategory ? " active" : "") + "' data-cat='" + esc(g) + "'>" + esc(label) +
        (n ? "<i class='qvq-cat-n'>" + n + "</i>" : "") + "</button>";
    }).join("");
    nav.querySelectorAll("button[data-cat]").forEach(function (btn) {
      btn.onclick = function () { switchSettingsCategory(btn.getAttribute("data-cat")); };
    });
  }

  function switchSettingsCategory(g) {
    if (g === currentCategory) return;
// 草稿跨分类保留（重绘前收编 DOM 值），切换不阻断
    currentCategory = g;
    renderSettingsCategories();
    renderSettingsForm();
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
    var known = (settingsEnums[f.items] && settingsEnums[f.items].length ? settingsEnums[f.items] : (f.options || [])).slice();
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

  // 表单分发：按 schema 类型/widget 渲染，值取 settingsDraft
  function settingField(f, q) {
    var key = esc(f.key);
    var value = (f.key in settingsDraft) ? settingsDraft[f.key] : f.value;
    var widget = f.widget || "text";
    var type = f.type || "str";
    var head = "<label class='qvq-label'>" + markHits(f.description || f.key, q) +
      " <span class='qvq-key-tag'>" + markHits(f.key, q) + "</span>" +
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
        // 非数字值：显示原文 + 红字提示，保存由后端校验拒收
        input = "<input class='qvq-input qvq-input-bad' type='text' data-key='" + key + "' value='" + esc(value == null ? "" : value) + "' />" +
          "<div class='qvq-field-err show'>" + esc(t("settings_invalid_value")) + "</div>";
      }
    } else if (type === "dict" || (value && typeof value === "object")) {
      var jsonText;
      try {
        jsonText = JSON.stringify(value == null ? {} : value, null, 2);
      } catch (e) {
        jsonText = String(value);
      }
      // dict（JSON 编辑器）分支优先于 secret：值按 JSON 文本上送
      input = "<textarea class='qvq-textarea qvq-mono' style='min-height:90px' data-key='" + key + "' data-json='1'>" + esc(jsonText) + "</textarea>";
    } else if (f.secret || widget === "password") {
      input = "<div class='qvq-pw-row' data-key='" + key + "' data-pw-row='1'>" +
        "<input class='qvq-input' type='password' data-pw-input='1' value='" + esc(value == null ? "" : value) + "' autocomplete='new-password' />" +
        "<button type='button' class='qvq-btn small ghost' data-pw-toggle='1'>" + esc(t("settings_show")) + "</button></div>";
    } else {
      var ph = f.placeholder ? " placeholder='" + esc(f.placeholder) + "'" : "";
      input = "<input class='qvq-input' data-key='" + key + "' value='" + esc(value == null ? "" : value) + "'" + ph + " />";
    }
    return "<div class='qvq-field" + (f.dangerous ? " dangerous" : "") + "' data-field='" + key + "'>" + head + input +
      "<div class='qvq-field-err' data-err='" + key + "'></div></div>";
  }

  function markHits(text, q) {
    var safe = esc(String(text == null ? "" : text));
    if (!q) return safe;
    try {
      return safe.replace(new RegExp("(" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi"), "<mark>$1</mark>");
    } catch (e) {
      return safe;
    }
  }

  function renderSettingsForm() {
    settingsCaptureDraft();  // 重绘前收编当前 DOM 值进 draft
    var box = el("qvq-settings-form");
    if (!box) return;
    var q = settingsSearchQuery();
    var fields;
    if (q) {
      fields = settingsFields.filter(function (f) {
        return f.key.toLowerCase().indexOf(q) >= 0 || String(f.description || "").toLowerCase().indexOf(q) >= 0;
      });
// 键名命中排前，同级保持 order
      fields.sort(function (a, b) {
        var ak = a.key.toLowerCase().indexOf(q) >= 0 ? 0 : 1;
        var bk = b.key.toLowerCase().indexOf(q) >= 0 ? 0 : 1;
        if (ak !== bk) return ak - bk;
        return (a.order || 99) - (b.order || 99);
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
    var lastGroupSec = "";
    var lastPlugin = "";
    fields.forEach(function (f) {
      if (q) {
        html += "<div class='qvq-settings-hit'><span class='qvq-chip'>" + esc(t("group_" + f.group)) + "</span>" + settingField(f, q) + "</div>";
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
      } else {
// 其它分组同样按语义小节分块
        var secKey = groupSectionHeader(f.group, f.order);
        if (secKey && secKey !== lastGroupSec) {
          html += "<div class='qvq-settings-sec'>" + esc(t(secKey)) + "</div>";
          lastGroupSec = secKey;
        }
      }
      if (f.group === "plugin" && f.plugin_module !== lastPlugin) {
        html += "<div class='qvq-settings-sec'>" + esc(f.plugin_title || f.plugin_module) + "</div>";
        lastPlugin = f.plugin_module;
      }
      html += settingField(f);
    });
    box.innerHTML = html;
    enhanceSettingsChecks(box);
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
      // 非数字原文上送：由后端 coerce 拒收并回字段级红字
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
    settingsPersistDraft();
  }

  function settingsDirtyKeys() {
    settingsCaptureDraft();
    var dirty = [];
    Object.keys(settingsDraft).forEach(function (k) {
      if (!settingsSameValue(settingsDraft[k], settingsOriginal[k])) dirty.push(k);
    });
    return dirty;
  }

  function settingsUpdateSaveBtn() {
    var btn = el("qvq-settings-save");
    if (!btn) return;
    var dirty = 0;
    Object.keys(settingsDraft).forEach(function (k) {
      if (!settingsSameValue(settingsDraft[k], settingsOriginal[k])) dirty++;
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

  // 类型化保存：只送 dirty 字段，dangerous 变更先确认，错误回填字段级红字
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


  // 保存失败：toast 列出具体字段与原因，并把第一个出错字段滚进视野
  function settingsReportErrors(errors) {
    var lines = Object.keys(errors || {}).map(function (k) {
      return k + "： " + (errors[k] || "invalid");
    });
    toast(t("settings_save_partial") + "\n" + lines.join("\n"), true);
    var first = document.querySelector("#qvq-settings-form .qvq-field-err.show");
    if (first && first.scrollIntoView) {
      first.scrollIntoView({ behavior: "smooth", block: "center" });
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
        settingsReportErrors(r.errors);
      } else if (r && r.ok) {
        keys.forEach(function (k) { settingsOriginal[k] = settingsDraft[k]; });
        toast(t("settings_saved"));
        settingsClearPersistedDraft();
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
          settingsReportErrors(r.errors);
        } else if (r && r.ok) {
          Object.keys(byModule[mod]).forEach(function (rk) { settingsOriginal[full(rk)] = settingsDraft[full(rk)]; });
          toast(t("settings_saved"));
          settingsClearPersistedDraft();
        } else {
          toast((r && r.error) || "error", true);
        }
        settingsUpdateSaveBtn();
      });
    });
  }

  // 设置页有未保存修改时只拦"离开页面"，站内切换不打断——
  // switchTab 仅切换显示，表单 DOM 与 settingsDraft 都保留
  (function initSettingsLeaveGuard() {
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
        stripUrlToken();
        hideLogin();
        el("qvq-login-err").textContent = "";
        bootData();
      } else {
        el("qvq-login-err").textContent = t("login_failed");
      }
    });
  }

