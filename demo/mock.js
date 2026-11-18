/* QvQChat 面板演示 mock 层：拦截 fetch，返回内置假数据；
 * 对话走脚本化 SSE（思考流 → 工具调用 → 分段正文），按用户消息关键词选择场景。
 * 纯静态可用：demo/index.html 双击（file://）或任意静态托管（wrangler pages）即可演示。
 */
(function () {
  'use strict';

  var NOW = Math.floor(Date.now() / 1000);
  function r(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
  function pick(arr) { return arr[r(0, arr.length - 1)]; }

  function json(data, status) {
    return Promise.resolve(new Response(JSON.stringify(data), {
      status: status || 200,
      headers: { "Content-Type": "application/json" },
    }));
  }

  /* ---------------- 基础数据 ---------------- */

  var VERSION = "4.7.0-demo";

  function dayKey(offset) {
    var d = new Date(NOW * 1000 - offset * 86400000);
    return d.toISOString().slice(0, 10);
  }
  var usageDays = [];
  [4.1, 12.7, 18.5, 0.3, 0.2, 0.1, 0.26, 0, 0, 0, 0, 0, 0.4, 1.1].forEach(function (m, i) {
    usageDays.push({ date: dayKey(13 - i), tokens: Math.round(m * 1e6), calls: Math.round(m * 47) });
  });

  var CONFIG_DRAFT = {
    bot_name: "小喵", language: "zh-CN", daily_token_limit: 10000000,
    trigger_mode: "follow", max_tool_rounds: 50, tool_select: "auto",
    tool_select_threshold: 50, reply_split: "paragraph", typing_speed: 1.0,
    handover_enabled: true, multi_agent: true, trust_agent: false,
    security_level: "standard", memory_enabled: true, audit_limit: 5000,
  };

  var CONFIG_FIELDS = [
    ["bot_name", "bot 名字（人格自我介绍用）", "text", "chat", 1],
    ["language", "界面与回复语言", "select", "chat", 2, ["zh-CN", "zh-TW", "en", "ja", "ru"]],
    ["trigger_mode", "群聊触发方式", "select", "chat", 3, ["follow", "all", "at_only", "lurk", "off"]],
    ["reply_split", "长回复分段投递", "select", "chat", 4, ["paragraph", "off"]],
    ["typing_speed", "分段打字速度倍率", "number", "chat", 5],
    ["max_tool_rounds", "单回合工具轮数上限", "number", "agent", 1],
    ["multi_agent", "多智能体（spawn_agent 后台派单）", "switch", "agent", 2],
    ["subjob_timeout", "后台子智能体超时秒数", "number", "agent", 3],
    ["tool_select", "动态工具注入", "select", "tools", 1, ["auto", "on", "off"]],
    ["tool_select_threshold", "注入触发工具数阈值", "number", "tools", 2],
    ["trust_agent", "完全信任（跳过危险操作确认）", "switch", "security", 1, null, true],
    ["security_level", "run_command 安全级别", "select", "security", 2, ["strict", "standard", "permissive"]],
    ["handover_enabled", "会话让渡（角色扮演切换）", "switch", "chat", 6],
    ["memory_enabled", "跨会话记忆", "switch", "chat", 7],
    ["daily_token_limit", "日 token 限额", "number", "chat", 8],
    ["audit_limit", "审计留存条数", "number", "security", 3],
  ].map(function (f) {
    return {
      key: f[0], description: f[1], widget: f[2], group: f[3], order: f[4],
      choices: f[5] || null, dangerous: !!f[6], value: CONFIG_DRAFT[f[0]],
    };
  });
  var CONFIG_GROUPS = ["chat", "agent", "tools", "security"];

  var PROVIDERS = [
    { id: "deepseek", name: "DeepSeek", base_url: "https://api.deepseek.com/v1", api_key_masked: "********c3f9", enabled: true, models: [
      { id: "deepseek-chat", tool_call: true, context_length: 65536, cost: { input: 0.27, output: 1.1 } },
      { id: "deepseek-reasoner", reasoning: true, tool_call: true, context_length: 65536, cost: { input: 0.55, output: 2.19 } },
    ] },
    { id: "siliconflow", name: "SiliconFlow", base_url: "https://api.siliconflow.cn/v1", api_key_masked: "********8a21", enabled: true, models: [
      { id: "Qwen/Qwen2.5-72B-Instruct", tool_call: true, context_length: 32768 },
      { id: "deepseek-ai/DeepSeek-V3", tool_call: true, context_length: 65536 },
      { id: "Qwen/Qwen2.5-VL-72B-Instruct", vision: true, context_length: 32768 },
    ] },
    { id: "openai", name: "OpenAI", base_url: "https://api.openai.com/v1", api_key_masked: "", enabled: false, models: [] },
  ];
  var CHAIN = [
    { provider: "deepseek", model: { id: "deepseek-chat" } },
    { provider: "deepseek", model: { id: "deepseek-reasoner" } },
    { provider: "siliconflow", model: { id: "Qwen/Qwen2.5-72B-Instruct" } },
  ];

  var PERSONAS = [
    { id: "sakura", name: "小樱", style: "元气猫娘" },
    { id: "helper", name: "助手", style: "简洁高效" },
  ];

  var SKILLS = [
    { id: "weekly", name: "周报生成", description: "抓取仓库动态汇总成周报", enabled: true },
    { id: "rename", name: "批量重命名", description: "按序号批量重命名文件", enabled: true },
    { id: "stalker", name: "追更速报", description: "监控发布源并推送", enabled: false },
  ];

  var TOOLS = [
    ["send_message", "发送平台消息", "builtin"], ["run_command", "执行 shell 命令", "builtin"],
    ["run_python", "执行 Python 代码", "builtin"], ["web_search", "联网搜索", "builtin"],
    ["web_fetch", "抓取网页正文", "builtin"], ["knowledge_search", "知识库检索", "builtin"],
    ["memory_write", "写入长期记忆", "builtin"], ["todo_write", "维护任务清单", "builtin"],
    ["spawn_agent", "派发后台子智能体", "builtin"], ["handover_session", "会话让渡（角色扮演）", "builtin"],
    ["schedule_create", "创建定时任务", "builtin"], ["image_gen", "生成图片", "skill"],
    ["stalker_check", "检查发布源更新", "skill"], ["search_erispulse_docs", "框架文档检索", "builtin"],
  ].map(function (t) {
    return { name: t[0], label: t[1], origin: t[2], description: t[1] + "。", danger: t[0] === "run_command" };
  });

  var SESSIONS = [
    { chat_key: "onebot11:group:1049", name: "ErisPulse 丨 喵之领域已展开", turns: 128, detail_type: "group", pinned: true, archived: false, platform: "onebot11", members: ["*"], sources: [], policy: { muted: false, low_token: false, priority: "normal", session_budget: 0 }, ui: {} },
    { chat_key: "onebot11:private:643319481", name: "小樱", turns: 76, detail_type: "private", pinned: false, archived: false, platform: "onebot11", members: [], sources: [], policy: { muted: false, low_token: true, priority: "high", session_budget: 20000 }, ui: {} },
    { chat_key: "dashboard:private:web", name: "网页对话", turns: 12, detail_type: "private", pinned: false, archived: false, platform: "dashboard", members: [], sources: [], policy: { muted: false, low_token: false, priority: "normal", session_budget: 0 }, ui: {} },
    { chat_key: "onebot11:group:8871", name: "开发组", turns: 41, detail_type: "group", pinned: false, archived: false, platform: "onebot11", members: [], sources: [], policy: { muted: true, low_token: false, priority: "low", session_budget: 0 }, ui: {} },
    { chat_key: "onebot11:group:2210", name: "闲聊灌水区", turns: 19, detail_type: "group", pinned: false, archived: false, platform: "onebot11", members: [], sources: [], policy: { muted: false, low_token: false, priority: "normal", session_budget: 0 }, ui: {} },
    { chat_key: "sub:onebot11:group:1049:9f8e7d6c", name: "抓取 GitHub trending 并汇总", turns: 4, detail_type: "group", pinned: false, archived: false, platform: "sub", kind: "sub", sub_of: "onebot11:group:1049", members: [], sources: [], policy: { muted: false, low_token: false, priority: "normal", session_budget: 0 }, ui: {} },
  ];

  /* 多账户页：适配器（运行中/已停用折叠演示）+ 账户（平台/会话数/人格绑定） */
  var ADAPTERS = [
    { platform: "onebot11", status: "started", enabled: true, bots: [
      { id: "3864258723", status: "online", last_active: NOW - 35, nickname: "小喵" },
    ] },
    { platform: "yunhu", status: "started", enabled: true, bots: [
      { id: "740318", status: "online", last_active: NOW - 62, nickname: "小喵" },
    ] },
    { platform: "oopz", status: "started", enabled: true, bots: [
      { id: "9f8e2c1d", status: "online", last_active: NOW - 240, nickname: "SnowOvO" },
    ] },
    { platform: "qqbot", status: "", enabled: false, bots: [] },
    { platform: "telegram", status: "", enabled: false, bots: [] },
  ];
  var MOCK_ACCOUNTS = [
    { account: "default", platforms: ["onebot11", "yunhu"], sessions: 5, persona: "sakura", enabled: true },
    { account: "web", platforms: ["dashboard"], sessions: 1, persona: "helper", enabled: true },
    { account: "backup", platforms: ["oopz"], sessions: 2, persona: "", enabled: true },
    { account: "legacy", platforms: ["telegram"], sessions: 3, persona: "", enabled: true },
  ];

  var ROUNDS_PING = [
    { text: "收到，这就去测喵。", tools: [] },
    { text: "容器里没 ping 命令，换个方式测连通性。", tools: [
      { tool: "run_command", arguments: "curl -o /dev/null -s -w \"DNS:%{time_namelookup} TCP:%{time_connect}\" https://bilibili.com", output: "DNS:0.004 TCP:0.027\nHTTP/2 200", ms: 4 },
    ] },
    { text: "B 站通的，状态很健康喵：\n\n- **DNS** 114.230.222.142，10ms\n- **TCP** 27ms，TLS 39ms，总连接 76ms\n- **HTTP** 200，首字节 164ms\n\n全程不到 0.2 秒，头发丝都测不到卡。", tools: [
      { tool: "run_python", arguments: "import urllib.request\nprint(urllib.request.urlopen(\"https://bilibili.com\").status)", output: "200", ms: 429 },
    ] },
  ];
  var MESSAGES = {
    "dashboard:private:web": [
      { role: "user", content: "ping一下bilibili" },
      { role: "assistant", content: "", rounds: ROUNDS_PING },
      { role: "user", content: "帮我写个批量重命名的小脚本" },
      { role: "assistant", content: "好喵，给你个常用的：批量重命名文件小脚本。\n\n```python\nimport os\n\ndef batch_rename(folder, prefix=\"file_\", ext_filter=None):\n    files = sorted(os.listdir(folder))\n    for i, name in enumerate(files, 1):\n        path = os.path.join(folder, name)\n        if not os.path.isfile(path):\n            continue\n        ext = os.path.splitext(name)[1]\n        os.rename(path, os.path.join(folder, f\"{prefix}{i:03d}{ext}\"))\n\nbatch_rename(\"D:/图片\", prefix=\"照片_\", ext_filter=(\".jpg\", \".png\"))\n```\n\n改下文件夹路径就能跑，会把文件重命名成 `照片_001.jpg` 这种带序号的格式。" },
    ],
    "onebot11:group:1049": [
      { role: "user", content: "今天有什么打算？" },
      { role: "assistant", content: "守着群等你们来找我玩喵。有事直接说～" },
    ],
  };
  MESSAGES["sub:onebot11:group:1049:9f8e7d6c"] = [
    { role: "user", content: "抓取 GitHub trending 并汇总" },
    { role: "assistant", content: "trending 前三：eryajf/ThankStars、codecrafters-io/build-your-own-x、xitanggg/open-resume，均为开发工具类。" },
  ];

  var TODOS = [
    { id: "t1", content: "整理 4.7.0 发布清单", status: "completed", created: NOW - 3600, updated: NOW },
    { id: "t2", content: "给 demo 页补 handover 场景", status: "in_progress", created: NOW - 1800, updated: NOW },
    { id: "t3", content: "重拍 README 截图", status: "pending", created: NOW - 900, updated: NOW - 600 },
  ];

  var SUBJOBS = [
    { sub_key: "sub:onebot11:group:1049:9f8e7d6c", status: "done", ms: 45230, task: "抓取 GitHub trending 并汇总", parent_chat_key: "onebot11:group:1049", started: NOW - 7200, finished: NOW - 7150 },
  ];
  var HANDOVER = null;  // {active, sub_key, setup, turns, max_turns, model, listen}

  var AUDIT = [
    ["run_command", "dashboard", { command: "uv run pytest -q", exit: 0 }],
    ["spawn_agent", "onebot11:group:1049", { task: "抓取 GitHub trending", steps: 4 }],
    ["handover_stop", "dashboard", { chat_key: "onebot11:group:1049" }],
    ["knowledge_search", "onebot11:643319481", { query: "周报", hits: 3 }],
    ["memory_write", "onebot11:643319481", { bytes: 391, scope: "chat" }],
    ["schedule_create", "dashboard", { name: "日报提醒", cron: "0 21 * * *" }],
    ["session_full_access", "dashboard", { chat_key: "onebot11:group:8871", value: true }],
    ["subjob_cancel", "dashboard", { sub_key: "sub:onebot11:group:1049:aa11bb22" }],
    ["todo_write", "dashboard", { items: 3 }],
    ["image_gen", "onebot11:private:512777", { prompt: "赛博朋克城市夜景", ms: 4310 }],
    ["mcp_fetch", "onebot11:group:8871", { server: "docs", ms: 812 }],
    ["storage_slim", "dashboard", { freed: "1.8 MB" }],
  ].map(function (a, i) {
    return { ts: NOW - (i + 1) * 617, tool: a[0], user_id: a[1], detail: a[2], chat_key: a[1].startsWith("dashboard") ? "dashboard:private:web" : a[1], origin: a[1].startsWith("dashboard") ? "dashboard" : "chat" };
  });

  var KB = [
    { id: "k1", title: "ErisPulse 适配器开发要点", content: "adapter 需实现 on_message 与 send 系列……", source: "docs", scope: "global", triggers: ["适配器"] },
    { id: "k2", title: "群规速记", content: "禁止未脱敏日志截图", source: "群规", scope: "onebot11:group:8871", triggers: ["群规"] },
  ];

  var TASKS = [
    { id: "qvq:profile_consolidate", name: "画像整理", next_formatted: "明天 05:40", kind: "profile_consolidate" },
    { id: "qvq:storage_maintain", name: "存储维护", next_formatted: "11-20 03:00", kind: "storage_maintain" },
    { id: "daily-report", name: "日报提醒", next_formatted: "今天 21:00", kind: "chat" },
    { id: "weekly-share", name: "空间日常分享", next_formatted: "11-24 20:23", kind: "chat" },
  ];

  var MCP = { servers: [], clients: [] };
  var INBOX = {
    total: 3, unread: 2, offset: 0, limit: 200, events: [
      { id: "e1", kind: "request", request_id: "req_9", summary: "好友请求：阿澈", detail_type: "friend", account: "default", ts: NOW - 600, read: false },
      { id: "e2", kind: "notice", summary: "群 8871 迎新提示已发送", detail_type: "group", account: "default", ts: NOW - 1200, read: false },
      { id: "e3", kind: "notice", summary: "适配器 onebot11 重连成功", account: "default", ts: NOW - 3000, read: true },
    ],
  };

  /* ---------------- 对话场景脚本 ---------------- */

  function chunks(text, size) {
    var out = [];
    for (var i = 0; i < text.length; i += size) out.push(text.slice(i, i + size));
    return out;
  }

  function scenario(text) {
    text = String(text || "");
    if (/ping|测速|连通|bilibili|github/i.test(text)) return {
      reasoning: "用户要我测网络连通性。先用 curl 拿 DNS/TCP 耗时，再用 Python 确认 HTTP 状态，最后汇总成几条结论。",
      steps: [
        { tool: "run_command", arguments: "curl -o /dev/null -s -w \"DNS:%{time_namelookup} TCP:%{time_connect} TTFB:%{time_starttransfer}\" https://bilibili.com", output: "DNS:0.004 TCP:0.027 TTFB:0.164", ms: 260 },
        { tool: "run_python", arguments: "import urllib.request, time\nt = time.time()\nr = urllib.request.urlopen(\"https://bilibili.com\")\nprint(r.status, round((time.time()-t)*1000), \"ms\")", output: "200 171 ms", ms: 429 },
      ],
      reply: "B 站通的，状态很健康喵：\n\n- **DNS** 114.230.222.142，10ms\n- **TCP** 27ms，TLS 39ms，总连接 76ms\n- **HTTP** 200，首字节 164ms\n\n全程不到 0.2 秒，头发丝都测不到卡。",
    };
    if (/后台|派|抓取|子智能体|agent/i.test(text)) return {
      reasoning: "这是个长任务：抓取要几分钟，应该后台派单，自己先回复用户，完成后自动回报。",
      steps: [
        { tool: "spawn_agent", arguments: { task: "抓取 GitHub trending 并汇总成中文周报", background: true }, output: "已在后台启动：sub:onebot11:group:1049:cafe1234", ms: 120, background: true },
      ],
      reply: "已把抓取任务交给后台智能体了喵，本喵先盯着群～完成后会自动来汇报结果。",
    };
    if (/扮演|让渡|病人|医生|剧本/i.test(text)) return {
      reasoning: "用户想玩角色扮演。这属于让渡场景：把对话窗口交给设定角色，主会话不沾剧情。",
      steps: [
        { tool: "handover_session", arguments: { setup: "你是急诊科医生，接诊一位肚子疼的病人（由用户扮演），语气专业但温和", listen: "inherit" }, output: "让渡已开启：sub:handover:dashboard:private:web:feed1234", ms: 90, handover: true },
      ],
      reply: "好呀～现在开始我是急诊科医生。哪里不舒服？疼了多久了？",
    };
    if (/写|脚本|代码|python/i.test(text)) return {
      reasoning: "用户要批量重命名脚本。写一个带前缀/扩展名过滤的小函数，给出示例调用。",
      steps: [],
      reply: "好喵，给你个常用的：批量重命名文件小脚本。\n\n```python\nimport os\n\ndef batch_rename(folder, prefix=\"file_\", ext_filter=None):\n    files = sorted(os.listdir(folder))\n    for i, name in enumerate(files, 1):\n        path = os.path.join(folder, name)\n        if not os.path.isfile(path):\n            continue\n        ext = os.path.splitext(name)[1]\n        os.rename(path, os.path.join(folder, f\"{prefix}{i:03d}{ext}\"))\n\nbatch_rename(\"D:/图片\", prefix=\"照片_\", ext_filter=(\".jpg\", \".png\"))\n```\n\n改下文件夹路径就能跑，会把文件重命名成 `照片_001.jpg` 这种带序号的格式。",
    };
    return {
      reasoning: pick([
        "日常闲聊，简短接住话头就好，别啰嗦。",
        "这句没有明确任务，用轻松的语气回一句，顺便留个话头。",
      ]),
      steps: [],
      reply: pick([
        "喵？听起来不错呀，然后呢？",
        "收到收到～本喵记下了，还有别的要交代吗？",
        "好呀好呀，就按你说的办喵。\n\n需要我顺手把相关的事也安排上吗？",
      ]),
    };
  }

  function sseBlock(event, data) {
    return "event: " + event + "\ndata: " + JSON.stringify(data) + "\n\n";
  }

  function mockChatStream(body) {
    var chatKey = String(body.session || body.chat_key || "dashboard:private:web");
    var text = String(body.text || body.prompt || "");
    var sc = scenario(text);
    var stream = new ReadableStream({
      start: function (controller) {
        var enc = new TextEncoder();
        var closed = false;
        function push(s) {
          if (!closed) { controller.enqueue(enc.encode(s)); }
        }
        function later(fn, ms) { setTimeout(function () { try { fn(); } catch (e) { /* 客户端可能已断开 */ } }, ms); }
        var segIdx = 0;

        // 历史：先落 user 消息
        var history = MESSAGES[chatKey] = MESSAGES[chatKey] || [];
        history.push({ role: "user", content: text });

        // 1) 思考流
        var think = chunks(sc.reasoning, 6);
        think.forEach(function (c, i) {
          later(function () { push(sseBlock("reasoning", { t: c })); }, 220 + i * 55);
        });
        var t0 = 300 + think.length * 55;

        // 2) 工具序列
        var ms = t0 + 240;
        (sc.steps || []).forEach(function (st) {
          var stepId = "s" + ms;
          later(function () {
            push(sseBlock("tool", { phase: "start", step_id: stepId, name: st.tool, arguments: typeof st.arguments === "string" ? st.arguments : JSON.stringify(st.arguments) }));
          }, ms);
          ms += Math.max(200, (st.ms || 300) - 80);
          later(function () {
            push(sseBlock("tool", { phase: "end", step_id: stepId, name: st.tool, output: st.output, ms: st.ms || 300 }));
            if (st.background) {
              SUBJOBS.unshift({ sub_key: "sub:" + chatKey + ":cafe" + r(1000, 9999), status: "running", task: "抓取 GitHub trending 并汇总成中文周报", parent_chat_key: chatKey, started: NOW });
            }
            if (st.handover) {
              HANDOVER = { active: true, sub_key: "sub:handover:" + chatKey + ":feed" + r(1000, 9999), setup: "急诊科医生接诊肚子疼的病人", turns: 0, max_turns: 30, model: "", listen: "inherit" };
            }
          }, ms);
          ms += 320;
        });

        // 3) 正文分段（按空行拆段，段内按小块流式）
        // 含代码块的回复整段连续流（真实引擎按 token 连续，不在 ``` 内拆段）
        var paras = sc.reply.indexOf("```") >= 0 ? [sc.reply] : sc.reply.split(/\n{2,}/);
        var delay = ms + 260;
        paras.forEach(function (para, pi) {
          var segI = segIdx++;
          var pieces = chunks(para, 7);
          if (pi) delay += 260;  // 段间停顿，模拟真人打字
          pieces.forEach(function (c, i) {
            later(function () { push(sseBlock("delta", { t: (i === 0 && pi ? "\n\n" : "") + c, i: segI })); }, delay);
            delay += r(26, 60);
          });
        });

        // 4) 收尾：done + 落历史（rounds 带全量工具明细）
        var tools = (sc.steps || []).map(function (st) {
          return { tool: st.tool, arguments: typeof st.arguments === "string" ? st.arguments : JSON.stringify(st.arguments), output: st.output, ms: st.ms || 300 };
        });
        later(function () {
          push(sseBlock("done", {}));
          history.push({ role: "assistant", content: "", rounds: [{ text: sc.reply, tools: tools }] });
          controller.close();
          closed = true;
        }, delay + 240);
      },
    });
    return Promise.resolve(new Response(stream, { headers: { "Content-Type": "text/event-stream" } }));
  }

  /* ---------------- fetch 拦截 ---------------- */

  var realFetch = window.fetch;
  window.fetch = function (url, opts) {
    opts = opts || {};
    var u = String(url);
    var path = u.replace(/^.*\/api\/qvq/, "/api/qvq").split("?")[0];
    var query = {};
    try {
      (u.split("?")[1] || "").split("&").forEach(function (kv) {
        if (!kv) return;
        var p = kv.split("=");
        query[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || "");
      });
    } catch (e) { /* 忽略 */ }
    var method = (opts.method || "GET").toUpperCase();

    if (path === "/api/qvq/auth") return json({ ok: true });
    if (path === "/api/qvq/chat/stream" && method === "POST") {
      var body = {};
      try { body = JSON.parse(opts.body || "{}"); } catch (e) { /* 忽略 */ }
      return mockChatStream(body);
    }
    if (path === "/api/qvq/chat/live" || path === "/api/qvq/chat/live/subscribe") {
      if (path.endsWith("/subscribe")) {
        return Promise.resolve(new Response("event: end\ndata: {}\n\n", { headers: { "Content-Type": "text/event-stream" } }));
      }
      return json({ status: "idle" });
    }
    if (path === "/api/qvq/chat/cancel") return json({ ok: true });

    if (method === "GET") {
      switch (path) {
        case "/api/qvq/status": return json({
          version: VERSION, models: 9, tools: { builtin: 61, skill: 3, mcp: 0, eco: 57 },
          sessions: 412, tasks: TASKS.length, eco: { modules: 6, tools: 57 },
          extensions: [{ name: "QvQMemes" }, { name: "QvQStalker" }, { name: "MyServer" }], mcp: [],
          security_level: "standard", trust_agent: false, takeovers: 0,
          usage_today: { tokens: 1106792, limit: 10000000, calls: 52 },
        });
        case "/api/qvq/usage": return json({ days: usageDays, limit: 10000000 });
        case "/api/qvq/costs": return json({
          daily: usageDays.map(function (d) { return { date: d.date, cost: round4(d.tokens / 1e6 * 0.42) }; }),
          by_model: { "custom:glm-5.3-flash": 1.9753, "deepseek:deepseek-chat": 1.2841, "siliconflow:Qwen/Qwen3.5-35B-A3B": 0.6411, "scnet:GLM-5.3-Flash": 0.0756 },
          total: 3.9761,
        });
        case "/api/qvq/models": return json({ providers: PROVIDERS, chain: CHAIN, models: CHAIN.map(function (c) { return { id: c.provider + ":" + c.model.id }; }), default: "deepseek:deepseek-chat", presets: [] });
        case "/api/qvq/sessions": return json({ sessions: SESSIONS, total: SESSIONS.length, start: 0, limit: 200, live_sessions: [], ui_defaults: {}, accounts: { adapters: ADAPTERS, accounts: MOCK_ACCOUNTS }, identity_map: {}, identity_suggestions: [] });
        case "/api/qvq/session/messages": {
          var msgs = MESSAGES[query.chat_key] || [];
          try {
            window.__msgLog = window.__msgLog || [];
            window.__msgLog.push({ key: query.chat_key, n: msgs.length });
          } catch (e) { /* 忽略 */ }
          return json({ messages: msgs.slice(-24), total: msgs.length, start: Math.max(0, msgs.length - 24), limit: 24 });
        }
        case "/api/qvq/todo": return json({ todos: TODOS });
        case "/api/qvq/personas": return json({ personas: PERSONAS });
        case "/api/qvq/skills": return json({ skills: SKILLS });
        case "/api/qvq/tools": return json({ tools: TOOLS, disabled: [] });
        case "/api/qvq/mcp": return json(MCP);
        case "/api/qvq/kb": return json({ entries: KB, total: KB.length });
        case "/api/qvq/tasks": return json({ tasks: TASKS, runs: TASKS.slice(0, 3).map(function (t, i) { return { name: t.name || t.id, at_formatted: "11-0" + (7 - i) + " 21:1" + i, error: "" }; }) });
        case "/api/qvq/running": return json({ running: [
          { session: "onebot11:group:1049", status: "running", agent: "" },
          { session: "sub:onebot11:group:1049:9f8e7d6c", status: "running", agent: "sub" },
          { session: "onebot11:group:8871", status: "done", agent: "" },
          { session: "dashboard:private:web", status: "done", agent: "" },
        ] });
        case "/api/qvq/subjobs": return json({ jobs: SUBJOBS, total: SUBJOBS.length });
        case "/api/qvq/breakers": return json({ breakers: [] });
        case "/api/qvq/audit": return json({ entries: AUDIT.slice(0, 12), total: AUDIT.length + 686 });
        case "/api/qvq/inbox": return json(INBOX);
        case "/api/qvq/handover": return json(HANDOVER ? Object.assign({}, HANDOVER) : { active: false });
        case "/api/qvq/memory": return json({
          entries: [
            { content: "主人常用 Windows + uv，跑测试用 uv run pytest", ts: NOW - 86400 },
            { content: "喜欢回复带点猫娘语气，但技术内容要准确", ts: NOW - 172800 },
          ],
          profile: [
            { text: "主语言 Python，技术栈 ErisPulse 生态", ts: NOW - 259200 },
            { text: "偏好简洁直接的回复风格", ts: NOW - 172800 },
          ],
        });
        case "/api/qvq/config": return json({ fields: CONFIG_FIELDS, groups: CONFIG_GROUPS });
        case "/api/qvq/plugin_settings": return json({ plugins: [] });
        case "/api/qvq/extensions": return json({ extensions: [
          { name: "QvQMemes", title: "表情包收录", details: { schemas: ["qvq_media"], skills: [], knowledge: [], prompts: [{ text: "用户发图时自动收录新梗图", priority: 2 }], personas: [] } },
          { name: "QvQStalker", title: "发布追更", details: { schemas: [], skills: [{ name: "stalker_check", description: "检查发布源更新" }], knowledge: [], prompts: [], personas: [] } },
        ] });
        case "/api/qvq/storage": return json({
          total_bytes: 23172889,
          domains: [
            { id: "sessions", keys: 412, bytes: 7025458 }, { id: "models", keys: 2, bytes: 6606023 },
            { id: "profiles", keys: 645, bytes: 2411724 }, { id: "memories", keys: 79, bytes: 382406 },
            { id: "audit", keys: 1, bytes: 180942 },
          ],
          files: [{ id: "uploads", bytes: 2726297 }, { id: "work", bytes: 2411520 }],
        });
        case "/api/qvq/storage/keys": return json({ domain: query.domain || "sessions", total: 2, keys: [
          { key: "QvQChat:conv:" + (query.domain === "sessions" ? "onebot11:group:1049" : "demo"), bytes: 2750075 },
          { key: "QvQChat:conv_index", bytes: 88023 },
        ] });
        case "/api/qvq/storage/entry": return json({ key: query.key || "QvQChat:demo", value: "{\"demo\": true}", truncated: false, bytes: 15 });
        case "/api/qvq/trash/list": return json({ items: [] });
        case "/api/qvq/export": return json({ exported: true, note: "演示环境不导出真实数据" });
        case "/api/qvq/settings/defaults": return json({ density: "detail" });
        case "/api/qvq/onboarding": return json({ modules: [] });
        case "/api/qvq/participation": return json({ rules: [] });
        case "/api/qvq/session/share": return json({ url: "/share?token=demo-token" });
        default:
          if (path.indexOf("/api/qvq/") === 0) return json({ ok: true });
          return realFetch(url, opts);
      }
    }

    // POST/DELETE：写操作统一 ok；特殊端点维护 mock 状态
    switch (path) {
      case "/api/qvq/handover/stop": HANDOVER = null; return json({ ok: true });
      case "/api/qvq/subjobs/cancel": {
        var sk = "";
        try { sk = JSON.parse(opts.body || "{}").sub_key || ""; } catch (e) { /* 忽略 */ }
        SUBJOBS.forEach(function (j) { if (j.sub_key === sk) j.status = "cancelled"; });
        return json({ ok: true });
      }
      case "/api/qvq/todo/add": TODOS.push({ id: "t" + NOW, content: parseBody(opts).content || "", status: "pending", created: NOW, updated: NOW }); return json({ ok: true });
      case "/api/qvq/todo/update": {
        var b = parseBody(opts);
        TODOS.forEach(function (t) { if (t.id === b.id) t.status = b.status; });
        return json({ ok: true });
      }
      case "/api/qvq/todo/delete": {
        var b2 = parseBody(opts);
        var i2 = TODOS.findIndex(function (t) { return t.id === b2.id; });
        if (i2 >= 0) TODOS.splice(i2, 1);
        return json({ ok: true });
      }
      case "/api/qvq/config": {
        var cfg = parseBody(opts);
        Object.keys(cfg).forEach(function (k) { CONFIG_DRAFT[k] = cfg[k]; });
        return json({ ok: true });
      }
      case "/api/qvq/chain/save": {
        var c = parseBody(opts).chain || [];
        CHAIN = c.length ? c : CHAIN;
        return json({ ok: true });
      }
      case "/api/qvq/inbox/clear": INBOX.events = []; INBOX.unread = 0; INBOX.total = 0; return json({ ok: true });
      case "/api/qvq/inbox/delete": {
        var b3 = parseBody(opts);
        INBOX.events = INBOX.events.filter(function (e) { return e.id !== b3.id; });
        INBOX.total = INBOX.events.length;
        return json({ ok: true });
      }
      case "/api/qvq/personas/bind": {
        var pb = parseBody(opts);
        var ck = String(pb.chat_key || "");
        var pid = pb.persona || "";
        MOCK_ACCOUNTS.forEach(function (a) {
          if (ck === "@" + a.account) a.persona = pid;
          else if ((a.platforms || []).indexOf(ck.replace(/:\*$/, "")) >= 0 && /:\*$/.test(ck)) a.persona = pid;
        });
        return json({ ok: true });
      }
      default: return json({ ok: true });
    }
  };

  function parseBody(opts) {
    try { return JSON.parse(opts.body || "{}") || {}; } catch (e) { return {}; }
  }
  function round4(v) { return Math.round(v * 10000) / 10000; }

  // 演示态：自动登录
  window.addEventListener("load", function () {
    setTimeout(function () {
      try {
        if (window.QvQ && window.QvQ.store) window.QvQ.store.loggedIn = true;
      } catch (e) { /* 面板未挂载完就算了 */ }
    }, 200);
  });
})();
