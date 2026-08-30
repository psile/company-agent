const ICONS = {
  home: '<svg viewBox="0 0 24 24"><path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z"/></svg>',
  star: '<svg viewBox="0 0 24 24"><path d="m12 3 2.4 6.6H21l-5.2 4 2 6.4L12 16.6 6.2 20l2-6.4L3 9.6h6.6z"/></svg>',
  heart: '<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2 4 4 0 0 1 7 2c0 5.6-7 10-7 10z"/></svg>',
  target: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/></svg>',
  book: '<svg viewBox="0 0 24 24"><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 0-3 3V4z"/><path d="M8 20V7"/></svg>',
  box: '<svg viewBox="0 0 24 24"><path d="M4 8 12 4l8 4-8 4z"/><path d="M4 8v8l8 4 8-4V8"/><path d="M12 12v8"/></svg>',
  user: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3.5"/><path d="M5 19a7 7 0 0 1 14 0"/></svg>',
  gear: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 3.5v2.2M12 18.3v2.2M4.7 7.2l1.9 1.1M17.4 15.7l1.9 1.1M4.7 16.8l1.9-1.1M17.4 8.3l1.9-1.1"/></svg>',
  chat: '<svg viewBox="0 0 24 24"><path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H10l-5 4v-4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/><path d="M8 10h8M8 13h5"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>',
  doc: '<svg viewBox="0 0 24 24"><path d="M7 3h8l4 4v14H7z"/><path d="M15 3v5h5M9 13h6M9 17h6"/></svg>',
  layers: '<svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/></svg>',
};

const ROUTES = [
  { id: "home", href: "#/", label: "首页", icon: "home" },
  { id: "chat", href: "#/chat", label: "秘书对话", icon: "chat" },
  { id: "work", href: "#/work", label: "我的工作", icon: "check" },
  { id: "projects", href: "#/projects", label: "项目", icon: "layers" },
  { id: "reports", href: "#/reports", label: "工作总结", icon: "doc" },
  { id: "recommend", href: "#/recommend", label: "为你推荐", icon: "star" },
  { id: "follows", href: "#/follows", label: "我的关注", icon: "heart" },
  { id: "goals", href: "#/goals", label: "目标管理", icon: "target" },
  { id: "knowledge", href: "#/knowledge", label: "知识库", icon: "book" },
  { id: "skills", href: "#/skills", label: "办公 Skills", icon: "box" },
];
const SETTINGS_ITEMS = [
  { href: "#/settings/profile", label: "个人信息" },
  { href: "#/settings/security", label: "账号与安全" },
  { href: "#/settings/llm", label: "大模型" },
  { href: "#/settings/prefs", label: "偏好设置" },
  { href: "#/settings/push", label: "推送与通知" },
  { href: "#/settings/privacy", label: "数据与隐私" },
  { href: "#/settings/members", label: "成员与权限" },
];
const CATS = ["Agent Memory", "Personal Agent", "Autonomous Driving", "VLM", "AI Coding", "工具实践", "产品动态", "待整理"];
const EXAMPLES = [
  "最近帮我重点关注 Agent Memory 和 Memory Skill。",
  "持续跟踪 Codex 和 Claude Code 的最新进展。",
  "帮我关注 RAG 和个性化推荐。",
];
const FOLLOW_TABS = [
  { id: "topic", label: "主题" },
  { id: "product", label: "产品/项目" },
  { id: "source", label: "信息源" },
  { id: "goal", label: "目标" },
];

const state = {
  dash: null,
  userId: "",
  token: localStorage.getItem("radar_session") || "",
  registerMode: false,
  route: "/",
  recTab: "all",
  recFilter: "all",
  recSort: "score",
  recDetailId: null,
  knowledgeCat: "全部",
  selectedCard: null,
  query: "",
  followKind: "topic",
  chatSessions: [],
  activeSessionId: null,
  chatMessages: [],
  conversationProfile: null,
  chatBusy: false,
  reportType: "daily",
  workSummary: null,
  summaryRange: "7",
  followsOverview: null,
  editingProduct: null,
  pendingChatExample: "",
  workDate: localDateKey(new Date()),
  workView: "day",
  taskEditorOpen: false,
  editingTaskId: null,
  pendingTaskProject: null,
  projectEditorOpen: false,
  editingProjectId: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const { headers: extraHeaders, ...rest } = options;
  const headers = {
    "Content-Type": "application/json",
    ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
    ...(extraHeaders || {}),
  };
  const res = await fetch(path, { credentials: "same-origin", ...rest, headers });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== "/api/me") {
    showAuth();
  }
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function showAuth() {
  state.dash = null;
  state.userId = "";
  if ($("appShell")) $("appShell").hidden = true;
  if ($("authGate")) $("authGate").hidden = false;
}

function hideAuth() {
  if ($("authGate")) $("authGate").hidden = true;
  if ($("appShell")) $("appShell").hidden = false;
}

function setAuthMode(register) {
  state.registerMode = register;
  $("authTitle").textContent = register ? "创建账户" : "登录";
  $("authLead").textContent = register
    ? "创建后立刻进入你自己的工作台。飞书接口可以稍后在账号设置里填写。"
    : "每个账号有一份私有 Memory。飞书 App ID / Secret 在登录后的「账号与安全」里填写。";
  $("nameField").hidden = !register;
  $("authSubmit").textContent = register ? "创建并进入" : "登录";
  $("authSwitch").textContent = register ? "已有账号？去登录" : "没有账号？创建账户";
  $("authPass").autocomplete = register ? "new-password" : "current-password";
  $("authError").hidden = true;
}

function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    el.hidden = true;
  }, 4200);
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function nameFromUser() {
  const account = (state.dash && state.dash.account && state.dash.account.user) || {};
  return account.display_name || account.username || state.userId || "我";
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 6) return "夜深了";
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function fmtTime(value) {
  if (!value) return "";
  const text = String(value);
  return text.slice(0, 16).replace("T", " ");
}

function relLabel(score) {
  const n = Number(score || 0);
  if (n >= 85) return "高度相关";
  if (n >= 70) return "中相关";
  return "可参考";
}

function dots(weight) {
  const n = Math.max(1, Math.min(5, Math.round(Number(weight || 0) * 5)));
  return `<span class="dots">${"●".repeat(n)}${"○".repeat(5 - n)}</span>`;
}

function tagsHtml(tags) {
  return (tags || [])
    .slice(0, 5)
    .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
    .join("");
}

function sourceKind(item) {
  const type = item.item_type || item.content_type || item.type || "";
  const name = String(item.source_name || item.name || "").toLowerCase();
  if (type === "paper" || name.includes("arxiv")) return "paper";
  if (type === "release" || name.includes("github")) return "github";
  if (type === "news") return "news";
  if (type === "blog") return "blog";
  return "other";
}

function matchQuery(item) {
  const q = state.query.trim().toLowerCase();
  if (!q) return true;
  const bag = [item.title, item.summary_zh, item.summary, item.source_name, ...(item.tags || [])]
    .join(" ")
    .toLowerCase();
  return bag.includes(q);
}

function recCard(item) {
  const score = Number(item.score || 0);
  const laneLabel = { work: "工作情报", industry: "行业动态", discovery: "轻松发现", personal: "兴趣延伸" }[item.lane] || "为你推荐";
  return `
    <article class="item rec-card" data-id="${escapeHtml(item.id)}">
      <div class="item-top">
        <div>
          <div class="rec-meta"><span class="tag">${laneLabel}</span><span>${escapeHtml(item.source_name || "")}</span>${item.author_name ? `<span>${escapeHtml(item.author_name)}</span>` : ""}<span>${escapeHtml(fmtTime(item.published_at))}</span></div>
          <h3>${escapeHtml(item.title)}</h3>
        </div>
        <div class="rel">
          <b>${score}%</b>
          <div class="tiny">${relLabel(score)}</div>
          <div class="meter"><span style="width:${score}%"></span></div>
        </div>
      </div>
      <p class="rec-summary">${escapeHtml(item.summary_zh || item.summary || "")}</p>
      <div class="tags rec-tags">${tagsHtml((item.tags || []).slice(0, 3))}${score >= 85 ? '<span class="tag green">高相关</span>' : ""}</div>
      ${item.why_you ? `<p class="rec-reason">${escapeHtml(item.why_you)}</p>` : ""}
      <div class="row-actions rec-actions">
        <button class="btn" data-rec-detail="${escapeHtml(item.id)}" type="button">阅读详情</button>
        <button class="btn-ghost" data-act="useful" data-id="${escapeHtml(item.id)}" type="button">有用</button>
        <button class="btn-ghost" data-act="collect" data-id="${escapeHtml(item.id)}" type="button">收藏</button>
        <button class="btn-ghost" data-act="dislike" data-id="${escapeHtml(item.id)}" type="button">减少此类推荐</button>
      </div>
    </article>`;
}

function recommendationDetailHtml() {
  if (!state.recDetailId || !state.dash) return "";
  const items = [...(state.dash.for_you || []), ...(state.dash.intel || [])];
  const item = items.find((row) => row.id === state.recDetailId);
  if (!item) return "";
  const score = Number(item.score || 0);
  const laneLabel = { work: "工作情报", industry: "行业动态", discovery: "轻松发现", personal: "兴趣延伸" }[item.lane] || "为你推荐";
  const points = (item.key_points || item.innovation || []).slice(0, 3);
  return `<div class="task-editor-backdrop rec-detail-backdrop" data-rec-backdrop>
    <aside class="task-editor rec-detail" role="dialog" aria-modal="true" aria-labelledby="recDetailTitle">
      <div class="task-editor-head">
        <div><span class="tiny">${laneLabel} · ${escapeHtml(item.source_name || "")}</span><h2 id="recDetailTitle">${escapeHtml(item.title || "")}</h2></div>
        <button class="icon-btn" id="recDetailClose" type="button" aria-label="关闭">×</button>
      </div>
      <div class="rec-detail-score"><b>${score}%</b><span>${relLabel(score)}</span><div class="meter"><span style="width:${score}%"></span></div></div>
      ${item.author_name ? `<div class="rec-author"><b>${escapeHtml(item.author_name)}</b>${item.author_badge_text ? `<span>${escapeHtml(item.author_badge_text)}</span>` : ""}<span>赞同 ${Number(item.vote_up_count || 0)} · 评论 ${Number(item.comment_count || 0)}</span></div>` : ""}
      <section class="rec-detail-section"><h3>简要总结</h3><p>${escapeHtml(item.summary_zh || item.summary || "")}</p></section>
      ${points.length ? `<section class="rec-detail-section"><h3>三点看懂</h3><ol>${points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ol></section>` : ""}
      ${item.impact ? `<section class="rec-detail-section"><h3>可能带来的影响</h3><p>${escapeHtml(item.impact)}</p></section>` : ""}
      ${item.interesting_point ? `<section class="rec-detail-section"><h3>有意思的是</h3><p>${escapeHtml(item.interesting_point)}</p></section>` : ""}
      ${item.why_you ? `<section class="rec-detail-section"><h3>为什么推荐给你</h3><p>${escapeHtml(item.why_you)}</p></section>` : ""}
      ${item.project_value ? `<section class="rec-detail-section"><h3>与你当前项目的关系</h3><p>${escapeHtml(item.project_value)}</p></section>` : ""}
      ${item.what_to_watch ? `<section class="rec-detail-section"><h3>接下来关注</h3><p>${escapeHtml(item.what_to_watch)}</p></section>` : ""}
      <div class="tags">${tagsHtml(item.tags || [])}</div>
      <div class="task-editor-actions">
        <button class="btn-ghost" data-act="collect" data-id="${escapeHtml(item.id)}" type="button">收藏</button>
        <button class="btn" data-open="${escapeHtml(item.id)}" type="button">打开原文</button>
      </div>
    </aside>
  </div>`;
}

function isActive(href) {
  const path = href.replace("#", "") || "/";
  if (path === "/") return state.route === "/";
  return state.route === path;
}

function inSettings() {
  return state.route === "/settings" || state.route.startsWith("/settings/");
}

function navHtml(items) {
  return items
    .map((item) => `<a class="nav-link${isActive(item.href) ? " is-on" : ""}" href="${item.href}">${ICONS[item.icon] || ""}${escapeHtml(item.label)}</a>`)
    .join("");
}

function settingsNavHtml() {
  const open = String(state.route || "").startsWith("/settings");
  return `
    <a class="nav-parent${open ? " is-on" : ""}" href="${open ? `#${state.route}` : "#/settings/push"}">${ICONS.gear}<span>设置</span><span class="chevron" aria-hidden="true">${open ? "▾" : "▸"}</span></a>
    <div class="nav-sub${open ? " is-open" : ""}">${SETTINGS_ITEMS.map((item) => `<a class="${isActive(item.href) ? "is-on" : ""}" href="${item.href}">${escapeHtml(item.label)}</a>`).join("")}</div>`;
}

function renderChrome() {
  if (!$("mainNav") || !$("accountNav") || !$("engineCard")) return;
  const dash = state.dash || {};
  const profile = dash.profile || {};
  const observe = dash.observe || {};
  const name = profile.display_name || nameFromUser();
  $("userName").textContent = name;
  $("avatar").textContent = name.slice(0, 1);
  $("mainNav").innerHTML = navHtml(ROUTES);
  $("accountNav").innerHTML = `
    <a class="nav-link${state.route === "/profile" ? " is-on" : ""}" href="#/profile">${ICONS.user}个人中心</a>
    ${settingsNavHtml()}`;
  const total = Number(observe.total || 0) || 2847;
  const fetched = Number(observe.fetched || 0) || 42;
  const llm = (dash.status && dash.status.llm) || {};
  const llmOn = !!llm.enabled;
  $("engineCard").innerHTML = `
    <div class="engine-head"><span>记忆引擎状态</span><span class="okdot">● 正常</span></div>
    <p>已处理信息 <b>${total.toLocaleString()}</b> 条</p>
    <div class="bar"><span style="width:${Math.min(100, 18 + (total % 80))}%"></span></div>
    <p>今日新增 ${fetched} 条</p>
    <p class="tiny">大模型 ${llmOn ? "已接通" : "未接通"}${llm.model ? " · " + escapeHtml(llm.model) : ""}</p>`;
  const notices = dash.notifications || dash.events || [];
  $("noticeBadge").hidden = notices.length === 0;
  $("noticeBadge").textContent = String(Math.min(9, notices.length));
  $("noticePop").innerHTML = notices.length
    ? notices.slice(0, 6).map((ev) => `<p>${escapeHtml(ev.title || ev.content || ev.action || "新动态")} · ${escapeHtml(fmtTime(ev.created_at || ev.at))}</p>`).join("")
    : "<p>暂无新通知。高相关内容会先出现在这里，再按设置推到飞书。</p>";
}

function pageChat() {
  const profile = state.conversationProfile || {};
  const messages = state.chatMessages || [];
  const sessions = state.chatSessions || [];
  const messageHtml = messages.length
    ? messages.map((message) => {
        const actions = (message.metadata && message.metadata.actions) || [];
        return `<div class="chat-message ${message.role === "user" ? "is-user" : "is-agent"}">
          <div class="chat-role">${message.role === "user" ? "你" : "秘书 Agent"}</div>
          <div class="chat-bubble">${escapeHtml(message.content).replaceAll("\n", "<br>")}</div>
          ${actions.length ? `<div class="chat-actions">${actions.map((action) => `<span>${action.status === "success" ? "已完成" : "未完成"} · ${escapeHtml(action.summary || action.tool || "操作")}</span>`).join("")}</div>` : ""}
        </div>`;
      }).join("")
    : `<div class="chat-empty"><h2>今天需要我做什么？</h2><p>直接告诉我你想关注的主题、最近在做的项目，或者询问最新推荐。</p>
        <div class="chat-starters">
          <button type="button" data-chat-example="周五前把 Personal Agent PPT 做完，提醒我。">记下待办</button>
          <button type="button" data-chat-example="明天下午提醒我发方案给老板。">约定提醒</button>
          <button type="button" data-chat-example="给我今天的工作重点。">今日重点</button>
          <button type="button" data-chat-example="这个项目现在进展怎么样？">项目进展</button>
          <button type="button" data-chat-example="生成今天日报。">今日日报</button>
          <button type="button" data-chat-example="帮我拆一下这个任务。">拆解任务</button>
          <button type="button" data-chat-example="最近帮我关注 Agent Memory、Mem0 和 MemOS，有重要论文再告诉我。">建立关注</button>
        </div></div>`;
  return `
    <div class="page-head chat-page-head">
      <div><h1>秘书对话</h1><p>持续对话，调用你的 Memory、目标、关注、知识库和 Radar。</p></div>
      <button class="btn" id="newChatBtn" type="button">＋ 新建对话</button>
    </div>
    <div class="chat-workbench">
      <aside class="chat-history">
        <div class="panel-title">历史会话</div>
        <div class="chat-session-list">${sessions.length ? sessions.map((session) => `<button type="button" data-chat-session="${escapeHtml(session.id)}" class="chat-session${session.id === state.activeSessionId ? " is-on" : ""}"><b>${escapeHtml(session.title || "新对话")}</b><span>${escapeHtml(fmtTime(session.updated_at))}</span></button>`).join("") : '<p class="tiny">还没有历史会话</p>'}</div>
      </aside>
      <section class="chat-main">
        <div class="chat-messages" id="chatMessages">${messageHtml}${state.chatBusy ? '<div class="chat-message is-agent"><div class="chat-role">秘书 Agent</div><div class="chat-bubble is-thinking">正在回复…</div></div>' : ""}</div>
        <form class="chat-compose" id="chatForm">
          <textarea id="chatInput" rows="3" placeholder="输入消息，Enter 发送，Shift + Enter 换行" ${state.chatBusy ? "disabled" : ""}></textarea>
          <button class="btn chat-send" type="submit" ${state.chatBusy ? "disabled" : ""}>发送</button>
        </form>
      </section>
      <aside class="chat-profile">
        <div class="panel-title">对话偏好</div>
        <div class="field"><label>回答长度</label><select id="cpVerbosity">
          ${profileOptions([["concise","简洁"],["balanced","适中"],["detailed","详细"]], profile.verbosity)}
        </select></div>
        <div class="field"><label>回答方式</label><select id="cpAnswerStyle">
          ${profileOptions([["conclusion_first","结论优先"],["step_by_step","逐步展开"]], profile.answer_style)}
        </select></div>
        <div class="field"><label>技术细节</label><select id="cpTechnical">
          ${profileOptions([["low","少"],["medium","适中"],["high","详细"]], profile.technical_detail)}
        </select></div>
        <div class="field"><label>主动程度</label><select id="cpProactive">
          ${profileOptions([["low","低"],["medium","中"],["high","高"]], profile.proactive_level)}
        </select></div>
        <div class="field"><label>操作确认</label><select id="cpConfirm">
          ${profileOptions([["important_actions","重要操作确认"],["always","总是确认"],["never","无需确认"]], profile.confirmation_policy)}
        </select></div>
        <button class="btn-ghost" id="saveConversationProfileBtn" type="button">保存偏好</button>
      </aside>
    </div>`;
}

function profileOptions(items, selected) {
  return items.map(([value, label]) => `<option value="${value}"${selected === value ? " selected" : ""}>${label}</option>`).join("");
}

function workDesk() {
  const memory = (state.dash || {}).work_memory;
  if (memory && typeof memory === "object" && !Array.isArray(memory)) return memory;
  return {};
}

function pageHome() {
  const dash = state.dash;
  const stats = dash.stats || {};
  const desk = workDesk();
  const openTasks = desk.open_tasks || desk.today || [];
  const brief = desk.brief || "";
  const items = (dash.for_you || []).filter(matchQuery).slice(0, 5);
  const goals = dash.goals || [];
  const today = goals.find((g) => g.kind === "today") || goals[0];
  const week = goals.find((g) => g.kind === "week");
  const quarter = goals.find((g) => g.kind === "quarter");
  const interests = (dash.interests || []).slice(0, 6);
  return `
    <div class="page-head">
      <div>
        ${pageHomeTaskBrief(dash) || `<h1>${greeting()}，今天有 ${openTasks.length || 0} 件工作值得优先关注。</h1>`}
        <p>${pageHomeTaskBrief(dash) ? "秘书会记住你的事项，结合截止日期和进度主动提醒，同时继续观察与当前项目相关的资料。" : "秘书会记住你的事项，结合截止日期和进度主动提醒，同时继续观察与当前项目相关的资料。"}</p>
      </div>
      <div class="actions">
        <button class="btn" id="refreshBtn" type="button">刷新源</button>
        <a class="btn-ghost" href="#/recommend">查看全部推荐</a>
      </div>
    </div>
    <div class="stats">
      ${stat("工作推荐", stats.work, "+工作上下文", "#/recommend?tab=work")}
      ${stat("个人推荐", stats.personal, "长期兴趣", "#/recommend?tab=personal")}
      ${stat("新增知识", stats.knowledge, "点赞/收藏沉淀", "#/knowledge")}
      ${stat("待处理反馈", stats.pending_feedback, "让它更懂你", "#/recommend?tab=feedback")}
    </div>
    <div class="layout">
      <section class="stack">
        ${brief ? `<div class="card work-brief"><div class="page-head" style="margin:0 0 12px"><h2 style="margin:0">今日工作重点</h2><a class="tiny" href="#/work">我的工作</a></div><pre class="brief-copy">${escapeHtml(brief)}</pre></div>` : ""}
        <div class="card">
          <div class="page-head" style="margin:0 0 12px">
            <h2 style="margin:0">今日待办</h2>
          </div>
          ${openTasks.length ? `<ol class="work-todo">${openTasks.slice(0, 5).map((task, index) => `<li><a href="#/work"><b>${index + 1}. ${escapeHtml(task.title || "")}</b></a><span>${escapeHtml(task.deadline ? "截止 " + task.deadline.slice(0, 10) : (task.priority || ""))} · ${escapeHtml(task.project || "当前项目")}</span></li>`).join("")}</ol>` : '<p class="tiny">还没有待办。在对话里说「周五前把 PPT 做完」就会记下来。</p>'}
        </div>
        <div class="card">
          <div class="page-head" style="margin:0 0 12px">
            <h2 style="margin:0">今日为你发现</h2>
            <button class="btn-ghost" id="refreshBtn2" type="button">刷新</button>
          </div>
          <div class="stack">${items.length ? items.map(recCard).join("") : emptyFeed()}</div>
        </div>
      </section>
      <aside class="stack">
        <section class="card">
          <div class="page-head" style="margin:0 0 8px"><h3 style="margin:0">你正在关注</h3><a href="#/follows">编辑</a></div>
          <div class="chips">${interests.map((row) => `<span class="chip">${escapeHtml(row.topic)}</span>`).join("")}<a class="chip" href="#/follows">+ 添加关注</a></div>
        </section>
        <section class="card">
          <h3>当前目标</h3>
          ${goalMini("今日目标", today)}
          ${goalMini("短期目标", week)}
          ${goalMini("长期目标", quarter)}
        </section>
        <section class="card">
          <h3>最近沉淀</h3>
          <p>新增 ${stats.knowledge || 0} 篇知识</p>
          <p>兴趣画像已随反馈更新</p>
          <p>收藏 ${stats.collects || 0} · 点赞 ${stats.likes || 0}</p>
        </section>
      </aside>
    </div>`;
}

function stat(label, value, hint, href) {
  if (!href) return `<section class="card stat"><span>${escapeHtml(label)}</span><b>${value || 0}</b><span class="up">${escapeHtml(hint)}</span></section>`;
  return `<section class="card stat" onclick="go('${href}'); return false;"><span>${escapeHtml(label)}</span><b>${value || 0}</b><a class="stat-link" href="${href}" style="pointer-events:none">${escapeHtml(hint)}</a></section>`;
}

function goalMini(label, goal) {
  if (!goal) return `<p class="tiny">${escapeHtml(label)} · 未设置</p>`;
  return `<div class="goal"><div class="tiny">${escapeHtml(label)}</div><b>${escapeHtml(goal.title)}</b><div class="barline"><span style="width:${goal.progress || 0}%"></span></div></div>`;
}

function emptyFeed() {
  return `<div class="empty">还没有筛出内容。点「刷新源」，Agent 会走采集 → 理解 → 记忆匹配 → 为你排序。</div>`;
}

// Task Card 组件（复用现有风格）
function taskCard(task) {
  const priorityColor = { urgent: "var(--danger)", high: "var(--warn)", medium: "var(--brand)", low: "var(--muted)" };
  const priorityStyle = `background:${priorityColor[task.priority] || priorityColor.medium}22;color:${priorityColor[task.priority] || priorityColor.medium}`;
  const deadlineText = task.deadline ? new Date(task.deadline).toLocaleDateString("zh-CN", { month: "short", day: "numeric" }) : "";
  
  return `<div class="card task-card" style="border-left:3px solid ${priorityColor[task.priority] || priorityColor.medium}">
    <div class="item-top">
      <div class="rel">
        <span class="chip">${escapeHtml(task.priority || "medium")}</span>
        ${deadlineText ? `<span class="tiny" style="margin-left:8px">${deadlineText}</span>` : ""}
      </div>
      <a class="tiny" href="#/work?task=${task.id}" aria-label="查看详情">详情</a>
    </div>
    <h3>${escapeHtml(task.title)}</h3>
    ${task.project ? `<p class="tiny" style="margin-top:4px">📁 ${escapeHtml(task.project)}</p>` : ""}
    ${task.description ? `<p class="task-desc">${escapeHtml(task.description.slice(0, 100))}${task.description.length > 100 ? "..." : ""}</p>` : ""}
  </div>`;
}

// 今日工作 Brief（替换纯推荐数字为今日建议优先处理）
function pageHomeTaskBrief(dash) {
  const tasks = (dash.work || {}).tasks || [];
  const openTasks = tasks.filter(t => t.status === "todo");
  const urgent = openTasks.filter(t => t.priority === "urgent" || t.priority === "high");
  const todayDeadlines = openTasks.filter(t => t.deadline && new Date(t.deadline).toDateString() === new Date().toDateString());
  const overdue = openTasks.filter(t => t.deadline && new Date(t.deadline) < new Date());
  
  if (!urgent.length && !todayDeadlines.length && !overdue.length) {
    return null;
  }
  
  let html = `<div class="card work-brief">`;
  html += `<div class="page-head" style="margin:0 0 12px"><h2 style="margin:0">今天建议优先处理</h2></div>`;
  
  if (urgent.length) {
    html += `<p><strong>紧急/高优先级：</strong>${urgent.map(t => escapeHtml(t.title)).join("；")}</p>`;
  }
  if (todayDeadlines.length) {
    html += `<p><strong>今天截止：</strong>${todayDeadlines.map(t => `${escapeHtml(t.title)}（${new Date(t.deadline).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}）`).join("；")}</p>`;
  }
  if (overdue.length) {
    html += `<p><strong>已过期未完成：</strong>${overdue.map(t => escapeHtml(t.title)).join("；")}</p>`;
  }
  
  html += `<div class="chips" style="margin-top:12px">`;
  html += `<a class="btn-ghost" href="#/work">查看全部待办</a>`;
  html += `<a class="btn-ghost" href="#/recommend?tab=work">查看工作相关推荐</a>`;
  html += `</div>`;
  html += `</div>`;
  
  return html;
}


function pageRecommend() {
  const dash = state.dash;
  const handledIds = new Set(
    (dash.events || [])
      .filter((row) => ["like", "useful", "collect", "star", "dislike", "skip", "dismiss"].includes(row.action))
      .map((row) => row.id)
  );
  const feedbackPool = Array.isArray(dash.pending_feedback)
    ? dash.pending_feedback
    : [...(dash.work || []), ...(dash.personal || [])]
      .filter((row, index, rows) => rows.findIndex((item) => item.id === row.id) === index)
      .filter((row) => !handledIds.has(row.id));
  const pool = state.recTab === "feedback"
    ? feedbackPool
    : state.recTab === "work" ? dash.work || []
      : state.recTab === "personal" ? dash.personal || []
        : dash.for_you || [];
  let items = pool.filter(matchQuery);
  if (state.recFilter === "high") items = items.filter((row) => Number(row.score || 0) >= 85);
  if (state.recFilter === "paper") items = items.filter((row) => sourceKind(row) === "paper");
  if (state.recFilter === "github") items = items.filter((row) => sourceKind(row) === "github");
  if (state.recFilter === "blog") items = items.filter((row) => sourceKind(row) === "blog");
  if (state.recFilter === "news") items = items.filter((row) => sourceKind(row) === "news");
  if (state.recFilter === "discovery") items = items.filter((row) => row.lane === "discovery");
  if (state.recFilter === "product") items = items.filter((row) => sourceKind(row) === "github" || /release|产品/.test(JSON.stringify(row)));
  items = [...items].sort((a, b) =>
    state.recSort === "new" ? String(b.published_at || "").localeCompare(String(a.published_at || "")) : Number(b.score || 0) - Number(a.score || 0)
  );
  const push = dash.push_settings || {};
  const brief = dash.brief || {};
  const weekly = dash.weekly_topics || [];
  return `
    <div class="page-head">
      <div>
        <h1>${state.recTab === "feedback" ? "待处理反馈" : "为你推荐"}</h1>
        <p>${state.recTab === "feedback" ? "告诉 Agent 哪些内容有用、值得收藏或不再需要，让后续推荐更准确。" : `本轮为你筛选 ${items.length} 条，先看简报，感兴趣再展开详情。`}</p>
      </div>
    </div>
    <div class="tabs">
      <button class="tab${state.recTab === "all" ? " is-on" : ""}" data-rectab="all" type="button">全部推荐 ${dash.for_you?.length || 0}</button>
      <button class="tab${state.recTab === "work" ? " is-on" : ""}" data-rectab="work" type="button">工作推荐</button>
      <button class="tab${state.recTab === "personal" ? " is-on" : ""}" data-rectab="personal" type="button">个人推荐</button>
      <button class="tab${state.recTab === "feedback" ? " is-on" : ""}" data-rectab="feedback" type="button">待处理反馈</button>
    </div>
    <div class="chips" style="margin:12px 0">
      ${[["all","全部"],["high","高相关"],["paper","论文"],["github","GitHub"],["blog","Blog"],["product","产品动态"],["news","行业新闻"],["discovery","轻松发现"]].map(([id,label]) => `<button class="chip${state.recFilter===id?" is-on":""}" data-filter="${id}" type="button">${label}</button>`).join("")}
      <select data-sort>
        <option value="score"${state.recSort==="score"?" selected":""}>排序：相关度</option>
        <option value="new"${state.recSort==="new"?" selected":""}>排序：最新</option>
      </select>
    </div>
    <div class="layout">
      <div class="recommend-grid">${items.length ? items.map(recCard).join("") : (state.recTab === "feedback" ? '<div class="empty">推荐反馈已经处理完了。新的推荐出现后会显示在这里。</div>' : emptyFeed())}</div>
      <aside class="stack">
        <section class="card">
          <h3>推荐偏好</h3>
          <p>兴趣领域：${(dash.interests || []).slice(0,4).map((r)=>r.topic).join("、") || "—"}</p>
          <p>内容来源：工作情报 / 行业新闻 / 产品动态 / 轻松发现</p>
          <p>推荐强度：${push.high_only ? "只推高相关" : "均衡"}</p>
          <p>推送频率：每天 ${escapeHtml(push.morning_time || "08:30")}</p>
          <a class="btn-ghost" href="#/settings/prefs">去设置</a>
        </section>
        <section class="card">
          <h3>本周关注主题</h3>
          ${weekly.map((row, i) => `<div class="goal"><div>${i+1}. ${escapeHtml(row.topic)} <span class="tiny">${row.count || 0} 篇</span></div><div class="barline"><span style="width:${Math.min(100,(row.count||1)*18)}%"></span></div></div>`).join("") || "<p class='tiny'>刷新源后会出现本周主题。</p>"}
        </section>
        <section class="card">
          <h3>Daily Brief 预览</h3>
          <p class="tiny">预计生成：${escapeHtml(brief.when || "明天 08:30")}</p>
          <p>观察 ${brief.observed || 0} 条 · 筛选 ${brief.filtered || 0} 条</p>
          <p>工作推荐 ${brief.work || 0} · 个人推荐 ${brief.personal || 0}</p>
          ${(brief.items || []).map((row) => `<p class="tiny">· ${escapeHtml(row.title || "")} ${row.score || 0}%</p>`).join("")}
          <button class="btn" id="briefBtn" type="button">立即生成预览</button>
        </section>
      </aside>
    </div>`;
}

function followForm() {
  if (state.followKind === "product") {
    return `
      <p class="tiny">持续跟踪一个产品或开源项目，Agent 会把它纳入观察名单。</p>
      <div class="field"><label>产品 / 项目名称</label><input id="productName" placeholder="Mem0 / Claude Code / Codex" /></div>
      <div class="field"><label>跟踪方式</label><select id="productStatus"><option>深度关注</option><option selected>持续跟踪</option></select></div>
      <button class="btn" id="addProductBtn" type="button">开始跟踪</button>`;
  }
  if (state.followKind === "source") {
    return `
    <p class="tiny">指定 RSS / Blog / GitHub 仓库，Agent 会在后台持续采集。微信公众号可填写自建 RSSHub 的真实订阅地址。</p>
    <div class="field"><label>信息源名称</label><input id="sourceName" placeholder="OpenAI Blog" /></div>
    <div class="field"><label>链接（RSS 地址或 GitHub 仓库）</label><input id="sourceUrl" placeholder="https://" /></div>
    <div class="field"><label>类型</label><select id="sourceType"><option value="blog">官方 Blog / RSS</option><option value="release">代码仓库 Releases</option><option value="news">行业新闻</option></select></div>
    <button class="btn" id="addSourceBtn" type="button">加入观察源</button>
    <p class="hint">添加后点首页「刷新源」立即生效；删除请到信息源列表。</p>`;
  }
  if (state.followKind === "goal") {
    return `
      <p class="tiny">把目标告诉 Agent，它会提高相关内容的推荐优先级。</p>
      <div class="field"><label>目标</label><input id="followGoalTitle" placeholder="本周完成个性化推荐 Demo" /></div>
      <div class="field"><label>类型</label><select id="followGoalKind"><option value="today">今日</option><option value="week" selected>短期</option><option value="quarter">长期</option><option value="open">不定期</option></select></div>
      <button class="btn" id="addFollowGoalBtn" type="button">纳入决策上下文</button>`;
  }
  return `
    <p class="tiny">支持自然语言。Agent 会解析成主题、权重和短期关注。</p>
    <div class="field">
      <label>用一句话说你想关注什么</label>
      <textarea id="followText" maxlength="100" placeholder="最近帮我重点关注 Agent Memory 和 Memory Skill。"></textarea>
      <div class="tiny"><span id="followCount">0</span>/100</div>
    </div>
    <div class="chips">${["LLM","Tool Use","RAG","Memory Skill","AI Coding"].map((t)=>`<button class="chip" data-topic="${t}" type="button">${t}</button>`).join("")}</div>
    <h3>自然语言示例</h3>
    <div class="examples">${EXAMPLES.map((t)=>`<button type="button" data-example="${escapeHtml(t)}">${escapeHtml(t)}</button>`).join("")}</div>
    <button class="btn" id="followBtn" type="button" style="margin-top:12px">让 Agent 开始观察</button>
    <p class="hint" style="margin-top:12px">Agent 会按你的偏好精确过滤信息，而不是把整个信息流都推给你。</p>`;
}

function briefLine(brief) {
  if (!brief || !brief.count) return "";
  const when = brief.latest_days_ago !== undefined && brief.latest_days_ago !== ""
    ? (brief.latest_days_ago === 0 ? "今天" : brief.latest_days_ago === 1 ? "昨天" : `${brief.latest_days_ago} 天前`)
    : (brief.latest_at || "");
  return `<div class="follow-brief"><b>最近</b>${escapeHtml(brief.latest_title || "")}<span class="tiny">${escapeHtml(when)} · 共 ${brief.count} 条</span></div>`;
}

function pageFollows() {
  const dash = state.dash;
  const overview = state.followsOverview || {};
  const interests = (overview.interests || dash.interests || []);
  const products = (overview.products || dash.products || []);
  const sources = (overview.sources || dash.sources || []);
  const focus = overview.focus || [];
  const typeMap = { paper: "学术论文", release: "代码发布", blog: "官方 Blog", news: "行业新闻", article: "中文内容", arxiv: "学术论文" };
  const editing = state.editingProduct;
  return `
    <div class="page-head">
      <div>
        <h1>我的关注</h1>
        <p>主题、产品和信息源都可以在这里直接编辑，每张卡片显示最近更新，一眼看到进展。</p>
      </div>
      <button class="btn" data-scroll="addFollow" type="button">+ 新增关注</button>
    </div>
    <div class="layout">
      <div class="stack">
        <section class="card">
          <h2>主题关注</h2>
          <div class="grid-cards">${interests.length ? interests.map((row) => `<div class="mini">
            <span class="tag">主题</span><b>${escapeHtml(row.topic)}</b>${dots(row.weight)}
            <div class="tiny">权重 ${Number(row.weight||0).toFixed(2)}</div>
            ${briefLine(row.brief)}
            <div class="row-actions">
              <button class="btn-ghost" data-interest-weight="${escapeHtml(row.topic)}" data-dir="up" type="button">调高权重</button>
              <button class="btn-ghost" data-interest-weight="${escapeHtml(row.topic)}" data-dir="down" type="button">调低</button>
              <button class="btn-ghost" data-interest-delete="${escapeHtml(row.topic)}" type="button">删除</button>
            </div>
          </div>`).join("") : '<p class="tiny">还没有主题关注。右侧添加，或在对话里说「重点关注 Agent Memory」。</p>'}</div>
        </section>
        <section class="card">
          <h2>产品 / 项目关注</h2>
          <div class="grid-cards">${products.length ? products.map((row) => {
            const isEditing = editing && editing.id === row.id;
            return `<div class="mini">
              ${isEditing ? `
                <div class="field"><label>名称</label><input id="editProductName" value="${escapeHtml(row.name)}" /></div>
                <div class="field"><label>跟踪方式</label><select id="editProductStatus">
                  ${["深度关注","持续跟踪","暂停观察"].map((s) => `<option${s === (row.status || "持续跟踪") ? " selected" : ""}>${s}</option>`).join("")}
                </select></div>
                <div class="field"><label>状态</label><select id="editProductRunning">
                  <option value="on"${row.running !== false ? " selected" : ""}>运行中</option>
                  <option value="off"${row.running === false ? " selected" : ""}>暂停</option>
                </select></div>
                <div class="row-actions">
                  <button class="btn" data-product-save="${escapeHtml(row.id)}" type="button">保存</button>
                  <button class="btn-ghost" data-product-cancel="1" type="button">取消</button>
                </div>` : `
                <b>${escapeHtml(row.name)}</b>
                <div class="tiny">${escapeHtml(row.status || "持续跟踪")}</div>
                <span class="tag ${row.running === false ? "" : "green"}">${row.running === false ? "暂停" : "运行中"}</span>
                ${briefLine(row.brief)}
                <div class="row-actions">
                  <button class="btn-ghost" data-product-edit="${escapeHtml(row.id)}" type="button">编辑</button>
                  <button class="btn-ghost" data-product-toggle="${escapeHtml(row.id)}" data-running="${row.running === false ? "on" : "off"}" type="button">${row.running === false ? "恢复运行" : "暂停"}</button>
                </div>`}
            </div>`;
          }).join("") : '<p class="tiny">还没有产品关注。右侧添加，例如 Mem0、vLLM。</p>'}</div>
        </section>
        <section class="card">
          <h2>信息源关注</h2>
          <table class="table">
            <thead><tr><th>信息源</th><th>类型</th><th>关注内容</th><th>最近采集</th><th>操作</th></tr></thead>
            <tbody>${sources.length ? sources.map((src) => `<tr>
              <td>${escapeHtml(src.name)}${src.custom ? ' <span class="tag">自定义</span>' : ""}${src.ready === false ? ' <span class="tag orange">待授权</span>' : ""}</td>
              <td>${escapeHtml(typeMap[src.type] || src.type || src.kind)}</td>
              <td class="tiny">${escapeHtml(src.search || src.repo || src.url || "—")}</td>
              <td class="tiny">${src.ready === false ? `需要配置 ${escapeHtml(src.credential_env || "平台凭证")}` : src.count ? `${escapeHtml(src.latest_title || "")}<br>${escapeHtml(src.latest_at || "")} · ${src.count} 条` : "暂无采集记录"}</td>
              <td class="tiny">${src.custom ? `<button class="btn-ghost" data-source-delete="${escapeHtml(src.id)}" type="button">删除</button>` : "内置源"}</td>
            </tr>`).join("") : '<tr><td colspan="5" class="tiny">还没有信息源。</td></tr>'}</tbody>
          </table>
          <p class="hint">自定义信息源会在下次「刷新源」时参与采集；内置源由系统维护。</p>
        </section>
        <section class="card">
          <h2>近期重点关注</h2>
          ${focus.length ? `<div class="stack">${focus.map((row) => `<p><b>${escapeHtml(row.topic)}</b>　${escapeHtml(row.brief.latest_title || "暂无新内容")}<span class="tiny">　${row.brief.count} 条相关</span></p>`).join("")}</div>` : "<p class='tiny'>采集到与你关注主题相关的内容后，这里会显示每个主题的最新进展。</p>"}
        </section>
      </div>
      <aside class="card" id="addFollow">
        <h2>添加关注</h2>
        <div class="tabs">
          ${FOLLOW_TABS.map((tab) => `<button class="tab${state.followKind===tab.id?" is-on":""}" data-followkind="${tab.id}" type="button">${tab.label}</button>`).join("")}
        </div>
        ${followForm()}
      </aside>
    </div>`;
}

function localDateKey(value) {
  if (!value) return "";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shiftDateKey(key, days) {
  const date = new Date(`${key || localDateKey(new Date())}T12:00:00`);
  date.setDate(date.getDate() + days);
  return localDateKey(date);
}

function workWeek(key) {
  const anchor = new Date(`${key || localDateKey(new Date())}T12:00:00`);
  const mondayOffset = (anchor.getDay() + 6) % 7;
  anchor.setDate(anchor.getDate() - mondayOffset);
  return Array.from({ length: 7 }, (_, index) => shiftDateKey(localDateKey(anchor), index));
}

function localDateTimeInput(value) {
  if (!value) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value}T18:00`;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function storedDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toISOString();
}

function pageWork() {
  const desk = workDesk();
  const tasks = desk.tasks || [];
  const notes = desk.notes || [];
  const reminders = desk.reminders || [];
  const roots = tasks.filter((task) => !task.parent_task_id);
  const childrenOf = {};
  for (const task of tasks) {
    if (!task.parent_task_id) continue;
    (childrenOf[task.parent_task_id] = childrenOf[task.parent_task_id] || []).push(task);
  }
  const pri = { urgent: "紧急", high: "高", medium: "中", low: "低" };
  const st = { todo: "待办", in_progress: "进行中", blocked: "阻塞", done: "完成", cancelled: "取消" };
  const source = { conversation: "对话收集", manual: "手动创建", seed: "初始化", system: "系统" };
  const rtype = { deadline: "截止", progress: "进度", morning: "晨间", risk: "风险", manual: "约定" };
  const rst = { pending: "待发送", sent: "已发送", cancelled: "已取消", skipped: "已跳过" };
  const today = localDateKey(new Date());
  const selected = state.workDate || today;
  const week = workWeek(selected);
  const taskDate = (task) => localDateKey(task.scheduled_at || task.deadline);
  const datedTasks = roots.filter((task) => taskDate(task) === selected);
  const unscheduled = roots.filter((task) => !taskDate(task) && !["done", "cancelled"].includes(task.status));
  const overdue = roots.filter((task) => task.deadline && localDateKey(task.deadline) < today && !["done", "cancelled"].includes(task.status));
  const timeLabel = (task) => {
    if (!task.scheduled_at) return "全天";
    return new Date(task.scheduled_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  };
  const taskRow = (task, compact = false) => {
    const kids = childrenOf[task.id] || [];
    return `<article class="work-task${task.status === "done" ? " is-done" : ""}">
      <div class="work-task-main">
        <div class="item-top"><b>${escapeHtml(task.title || "")}</b><span class="tag ${task.priority === "high" || task.priority === "urgent" ? "orange" : "gray"}">${pri[task.priority] || "中"}</span></div>
        ${!compact && task.description ? `<p class="work-task-desc">${escapeHtml(task.description)}</p>` : ""}
        <p class="tiny">${escapeHtml(task.project || "未关联项目")} · ${escapeHtml(st[task.status] || task.status)} · ${escapeHtml(source[task.source_type] || task.source_type || "手动创建")}${task.deadline ? ` · 截止 ${escapeHtml(new Date(task.deadline).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }))}` : ""}</p>
        ${!compact && kids.length ? `<ul class="task-kids">${kids.map((child) => `<li>${escapeHtml(child.title)} · ${escapeHtml(st[child.status] || "")}</li>`).join("")}</ul>` : ""}
      </div>
      <div class="task-actions">
        ${task.status !== "done" && task.status !== "cancelled" ? `<button class="btn-ghost" type="button" data-task-id="${escapeHtml(task.id)}" data-task-act="start">开始</button>` : ""}
        ${task.status !== "done" && task.status !== "cancelled" ? `<button class="btn-ghost" type="button" data-task-id="${escapeHtml(task.id)}" data-task-act="done">完成</button>` : ""}
        ${!compact ? `<button class="btn-ghost" type="button" data-task-id="${escapeHtml(task.id)}" data-task-act="breakdown">拆解</button>` : ""}
        <button class="btn-ghost" type="button" data-task-edit="${escapeHtml(task.id)}">编辑</button>
      </div>
    </article>`;
  };
  const orderedForDay = [...datedTasks].sort((a, b) => String(a.scheduled_at || "9999").localeCompare(String(b.scheduled_at || "9999")));
  const visibleTasks = state.workView === "all"
    ? [...roots].sort((a, b) => String(a.scheduled_at || a.deadline || "9999").localeCompare(String(b.scheduled_at || b.deadline || "9999")))
    : orderedForDay;
  const selectedDate = new Date(`${selected}T12:00:00`);
  const selectedTitle = selected === today ? "今日工作" : selectedDate.toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" });
  return `
    <div class="page-head">
      <div>
        <h1>我的工作</h1>
        <p>对话自动收集与手动安排使用同一份工作记忆，按时间推进并主动提醒。</p>
      </div>
      <div class="actions"><button class="btn" id="addWorkTaskBtn" type="button">新建任务</button></div>
    </div>
    <section class="work-calendar">
      <div class="work-calendar-head">
        <div class="actions"><button class="icon-btn" type="button" data-work-shift="-7" aria-label="上一周">‹</button><button class="btn-ghost" id="workTodayBtn" type="button">今天</button><button class="icon-btn" type="button" data-work-shift="7" aria-label="下一周">›</button></div>
        <b>${week[0].slice(0, 7).replace("-", " 年 ")} 月</b>
        <div class="segmented"><button type="button" data-work-view="day" class="${state.workView === "day" ? "is-on" : ""}">日程</button><button type="button" data-work-view="all" class="${state.workView === "all" ? "is-on" : ""}">全部</button></div>
      </div>
      <div class="work-week">${week.map((key) => {
        const day = new Date(`${key}T12:00:00`);
        const count = roots.filter((task) => taskDate(task) === key && !["cancelled"].includes(task.status)).length;
        return `<button type="button" data-work-date="${key}" class="work-day${key === selected ? " is-on" : ""}${key === today ? " is-today" : ""}"><span>${day.toLocaleDateString("zh-CN", { weekday: "short" })}</span><b>${day.getDate()}</b><i>${count || ""}</i></button>`;
      }).join("")}</div>
    </section>
    <div class="work-layout">
      <section class="work-surface">
        <div class="work-section-head"><div><h2>${state.workView === "all" ? "全部任务" : selectedTitle}</h2><p>${state.workView === "all" ? `${roots.length} 项任务` : `${visibleTasks.length} 项安排`}</p></div>${overdue.length ? `<span class="work-risk">${overdue.length} 项已逾期</span>` : ""}</div>
        ${visibleTasks.length ? `<div class="work-timeline">${visibleTasks.map((task) => `<div class="work-slot"><time>${state.workView === "all" ? (taskDate(task) || "未排期") : timeLabel(task)}</time>${taskRow(task)}</div>`).join("")}</div>` : `<div class="empty"><b>${state.workView === "all" ? "还没有任务" : "这一天还没有安排"}</b><p>可以新建任务，也可以在秘书对话里直接说出要做的事。</p><button class="btn-ghost" type="button" data-task-new>添加一项工作</button></div>`}
      </section>
      <aside class="stack">
        <section class="card work-unscheduled">
          <div class="item-top"><h3>未排期</h3><span class="tiny">${unscheduled.length}</span></div>
          ${unscheduled.length ? unscheduled.slice(0, 5).map((task) => taskRow(task, true)).join("") : '<p class="tiny">所有进行中的任务都已有时间安排。</p>'}
        </section>
        <section class="card">
          <h3>提醒</h3>
          ${reminders.length ? reminders.slice(0, 6).map((row) => `<article class="remind-item"><div class="item-top"><b>${escapeHtml(rtype[row.reminder_type] || "提醒")}</b><span class="tag ${row.status === "sent" ? "green" : "gray"}">${escapeHtml(rst[row.status] || row.status)}</span></div><p class="tiny">${escapeHtml((row.generated_content || row.trigger_at || "").slice(0, 120))}</p></article>`).join("") : '<p class="tiny">有截止日期的任务会在 24 小时和 3 小时前结合进度提醒你。</p>'}
        </section>
        <section class="card">
          <h3>工作记录</h3>
          ${notes.length ? notes.slice(0, 6).map((note) => `<p class="tiny">${escapeHtml(note.content || "")}</p>`).join("") : '<p class="tiny">还没有工作备忘。</p>'}
        </section>
        <section class="card">
          <h3>目标</h3>
          <p class="tiny">目标仍是推荐上下文，任务才是要推进的事项。</p>
          <a class="btn-ghost" href="#/goals">打开目标管理</a>
        </section>
      </aside>
    </div>
    ${taskEditor(tasks)}`;
}

function taskEditor(tasks) {
  if (!state.taskEditorOpen) return "";
  const task = (tasks || []).find((row) => row.id === state.editingTaskId) || {};
  const pendingProject = state.pendingTaskProject || {};
  const duration = String(task.estimated_duration || "").match(/\d+/)?.[0] || "";
  return `<div class="task-editor-backdrop" data-editor-backdrop>
    <aside class="task-editor" role="dialog" aria-modal="true" aria-labelledby="taskEditorTitle">
      <div class="task-editor-head"><div><span class="tiny">${task.id ? "修改工作安排" : "手动添加"}</span><h2 id="taskEditorTitle">${task.id ? "编辑任务" : "新建任务"}</h2></div><button class="icon-btn" id="taskEditorClose" type="button" aria-label="关闭">×</button></div>
      <form id="taskEditorForm">
        <div class="field"><label for="workTaskTitle">任务名称</label><input id="workTaskTitle" maxlength="160" required value="${escapeHtml(task.title || "")}" placeholder="例如：完成项目汇报初稿" /></div>
        <div class="field"><label for="workTaskDescription">补充说明</label><textarea id="workTaskDescription" rows="3" maxlength="800" placeholder="成果要求、相关材料或注意事项">${escapeHtml(task.description || "")}</textarea></div>
        <div class="form-grid">
          <div class="field"><label for="workTaskSchedule">安排时间</label><input id="workTaskSchedule" type="datetime-local" value="${escapeHtml(localDateTimeInput(task.scheduled_at || (task.id ? "" : `${state.workDate}T09:00`)))}" /></div>
          <div class="field"><label for="workTaskDeadline">截止时间</label><input id="workTaskDeadline" type="datetime-local" value="${escapeHtml(localDateTimeInput(task.deadline || ""))}" /></div>
          <div class="field"><label for="workTaskPriority">优先级</label><select id="workTaskPriority">${[["low","低"],["medium","中"],["high","高"],["urgent","紧急"]].map(([value,label]) => `<option value="${value}"${(task.priority || "medium") === value ? " selected" : ""}>${label}</option>`).join("")}</select></div>
          <div class="field"><label for="workTaskStatus">状态</label><select id="workTaskStatus">${[["todo","待办"],["in_progress","进行中"],["blocked","阻塞"],["done","完成"],["cancelled","取消"]].map(([value,label]) => `<option value="${value}"${(task.status || "todo") === value ? " selected" : ""}>${label}</option>`).join("")}</select></div>
          <div class="field"><label for="workTaskProject">所属项目</label><input id="workTaskProject" maxlength="100" value="${escapeHtml(task.project || pendingProject.name || "")}" placeholder="可选" /><input id="workTaskProjectId" type="hidden" value="${escapeHtml(task.project_id || pendingProject.id || "")}" /></div>
          <div class="field"><label for="workTaskDuration">预计时长（分钟）</label><input id="workTaskDuration" type="number" min="0" step="15" value="${escapeHtml(duration)}" placeholder="60" /></div>
        </div>
        ${task.id ? `<p class="editor-origin">来源：${escapeHtml(task.source_type === "conversation" ? "秘书对话自动收集" : task.source_type === "manual" ? "用户手动创建" : task.source_type || "未知")}</p>` : ""}
        <div class="task-editor-actions"><button class="btn-ghost" id="taskEditorCancel" type="button">取消</button><button class="btn" type="submit">${task.id ? "保存修改" : "创建任务"}</button></div>
      </form>
    </aside>
  </div>`;
}

function reportDayCard(day, reports) {
  const stats = day.stats || {};
  const metrics = [];
  if (stats.completed) metrics.push(`完成 ${stats.completed}`);
  if (stats.in_progress) metrics.push(`进行中 ${stats.in_progress}`);
  if (stats.knowledge) metrics.push(`知识 ${stats.knowledge}`);
  if (stats.decisions) metrics.push(`决策 ${stats.decisions}`);
  const items = [];
  (day.top_completed || []).forEach((t) => items.push(`<li class="day-item is-done">✓ ${escapeHtml(t)}</li>`));
  (day.top_in_progress || []).forEach((t) => items.push(`<li class="day-item is-doing">◉ ${escapeHtml(t)}</li>`));
  if (day.more_completed) items.push(`<li class="day-item is-more">还有 ${day.more_completed} 项已完成</li>`);
  if (day.more_in_progress) items.push(`<li class="day-item is-more">还有 ${day.more_in_progress} 项进行中</li>`);
  const dateObj = new Date(day.date + "T00:00:00");
  const monthDay = `${String(dateObj.getMonth() + 1).padStart(2, "0")}月${String(dateObj.getDate()).padStart(2, "0")}日`;
  const report = reports.find((row) => row.report_type === "daily" && (row.start_time || "").slice(0, 10) === day.date);
  const summary = day.summary || (day.date === new Date().toISOString().slice(0, 10) ? "今天还没有完成事项" : "当天没有工作记录");
  return `<section class="day-card" id="day-${day.date}">
    <div class="day-head">
      <b>${monthDay}${day.day_label ? ` · ${day.day_label}` : ""}</b>
      ${metrics.length ? `<span class="day-metrics">${metrics.map((m) => `<i>${escapeHtml(m)}</i>`).join("")}</span>` : ""}
    </div>
    <p class="day-summary">${escapeHtml(summary)}</p>
    ${items.length ? `<ul class="day-items">${items.join("")}</ul>` : ""}
    ${(day.decisions || []).length ? `<p class="day-decision"><b>关键决策</b>${escapeHtml(day.decisions[0])}</p>` : ""}
    ${(day.risks || []).length ? `<p class="day-risk"><b>风险</b>${escapeHtml(day.risks[0])}</p>` : ""}
    ${report ? `<details class="day-detail"><summary>查看完整日报</summary><pre class="report-copy">${escapeHtml(report.content || "")}</pre><div class="day-actions"><button class="btn-ghost" data-copy-report="${escapeHtml(report.id)}" type="button">复制</button><button class="btn-ghost" data-export-report="${escapeHtml(report.id)}" type="button">导出</button><button class="btn-ghost" data-regen-report="${escapeHtml(day.date)}" type="button">重新生成</button></div></details>` : `<button class="btn-ghost" data-regen-report="${escapeHtml(day.date)}" type="button">生成当天日报</button>`}
  </section>`;
}

function pageReports() {
  const desk = workDesk();
  const kind = state.reportType || "daily";
  const summary = state.workSummary;
  const reports = (desk.reports || []);
  const dailyReports = reports.filter((row) => row.report_type === "daily");
  const current = reports.filter((row) => row.report_type === kind)[0];
  const src = (current && current.sources) || {};
  const stats = (summary && summary.stats) || {};
  const days = (summary && summary.days) || [];
  const projects = (summary && summary.projects) || [];
  const period = (summary && summary.period) || {};
  const tabs = [
    ["daily", "今日"],
    ["weekly", "本周"],
    ["monthly", "本月"],
    ["project_summary", "项目"],
  ];
  const historyByMonth = {};
  dailyReports.forEach((row) => {
    const key = (row.start_time || "").slice(0, 7);
    if (!key) return;
    (historyByMonth[key] = historyByMonth[key] || []).push(row);
  });
  return `
    <div class="page-head">
      <div>
        <h1>工作总结</h1>
        <p>按日期回顾每天做了什么，需要时再展开完整日报。</p>
      </div>
      <div class="actions">
        <select id="summaryRange" class="input" style="width:auto">
          <option value="7"${state.summaryRange === "7" ? " selected" : ""}>最近 7 天</option>
          <option value="30"${state.summaryRange === "30" ? " selected" : ""}>最近 30 天</option>
        </select>
        <button class="btn" id="generateReportBtn" type="button">一键生成</button>
      </div>
    </div>
    <div class="tabs">
      ${tabs.map(([id, label]) => `<button class="tab${kind === id ? " is-on" : ""}" data-report-tab="${id}" type="button">${label}</button>`).join("")}
    </div>
    <div class="stats" style="margin-top:16px">
      ${stat("完成", stats.completed, period.start ? `${(period.start || "").slice(5)} 起` : "统计中")}
      ${stat("进行中", stats.in_progress, "持续推进")}
      ${stat("知识沉淀", stats.knowledge, "收藏与笔记")}
      ${stat("关键决策", stats.decisions, "方向性记录")}
    </div>
    <div class="layout" style="margin-top:16px">
      <section class="stack">
        ${summary ? `<section class="card ai-summary"><h3>AI 工作摘要</h3><p>${escapeHtml(summary.summary || "暂无足够数据生成摘要。")}</p></section>` : ""}
        ${kind === "daily" || kind === "weekly" || kind === "monthly" ? `
        <div class="timeline">
          ${days.length ? days.map((day) => reportDayCard(day, dailyReports)).join("") : `<section class="card"><p class="tiny">这段时间还没有工作记录。对话里说「周五前完成 PPT」就会开始积累。</p></section>`}
        </div>` : `
        <section class="card">
          <h3>${escapeHtml((current && current.title) || "项目总结")}</h3>
          ${current ? `<pre class="report-copy">${escapeHtml(current.content || "")}</pre>` : `<p class="tiny">还没有项目总结。点「一键生成」从任务和事件汇总。</p>`}
          ${(summary && summary.events || []).length ? `<h3 style="margin-top:16px">项目动态</h3><ul class="day-items">${summary.events.map((e) => `<li class="day-item"><span class="day-date">${escapeHtml(e.date)}</span>${escapeHtml(e.title || "")}</li>`).join("")}</ul>` : ""}
        </section>`}
        ${current && kind !== "project_summary" ? `<details class="card"><summary>完整${tabs.find((row) => row[0] === kind)?.[1] || ""}报告</summary><pre class="report-copy">${escapeHtml(current.content || "")}</pre><div class="field" style="margin-top:14px"><label>编辑</label><textarea id="reportEditor" rows="8">${escapeHtml(current.content || "")}</textarea></div><button class="btn-ghost" id="saveReportBtn" type="button" data-report-id="${escapeHtml(current.id)}">保存修改</button></details>` : ""}
      </section>
      <aside class="stack">
        <section class="card">
          <h3>本周主要项目</h3>
          ${projects.length ? projects.map((p) => `<p>${escapeHtml(p.project)} · ${p.events} 条动态</p>`).join("") : "<p class='tiny'>暂无项目动态。</p>"}
        </section>
        <details class="card">
          <summary><b>生成依据</b></summary>
          ${current ? `<p>Task ${src.tasks || 0}</p><p>WorkEvent ${src.events || 0}</p><p>WorkNote ${src.notes || 0}</p><p>Goal ${src.goals || 0}</p><p>Knowledge ${src.knowledge || 0}</p><p>Decision ${src.decisions || 0}</p>` : "<p class='tiny'>生成报告后显示。</p>"}
        </details>
        <section class="card">
          <h3>历史</h3>
          ${Object.keys(historyByMonth).length ? Object.keys(historyByMonth).sort().reverse().map((month) => `<div class="history-month"><b>${month.replace("-", "月")}月</b>${historyByMonth[month].map((row) => `<a class="tiny" href="#day-${(row.start_time || "").slice(0, 10)}" data-jump-day="${(row.start_time || "").slice(0, 10)}">${escapeHtml((row.start_time || "").slice(5, 10).replace("-", "/"))}</a>`).join("")}</div>`).join("") : "<p class='tiny'>生成日报后会按日期归档。</p>"}
        </section>
      </aside>
    </div>`;
}

function pageProjects() {
  const tracker = state.dash.tracker || {};
  const pack = state.dash.project_trackers || {};
  const projects = pack.items || (tracker.project ? [tracker] : []);
  const storedProjects = (pack.projects || []).map((meta) => projects.find((row) => row.project_id === meta.project_id) || meta);
  const progress = Number(tracker.estimated_progress || 0);
  const done = tracker.completed || [];
  const doing = tracker.in_progress || [];
  const risks = tracker.risks || [];
  const steps = tracker.next_steps || [];
  const goals = tracker.goals || [];
  const knowledge = tracker.knowledge || [];
  const events = tracker.events || [];
  const acceptance = tracker.acceptance_criteria || [];
  const milestones = tracker.milestones || [];
  const statusLabels = { planning: "准备中", active: "进行中", paused: "已暂停", done: "已完成" };
  return `
    <div class="project-switcher">
      <div class="project-tabs">${storedProjects.map((row) => `<button type="button" data-project-select="${escapeHtml(row.project_id || "")}" class="project-tab${row.project_id === tracker.project_id ? " is-on" : ""}"><b>${escapeHtml(row.project || "未命名项目")}</b><span>${escapeHtml(row.stage || statusLabels[row.status_code] || statusLabels[row.status] || row.status || "")}</span></button>`).join("")}</div>
      <button class="btn-ghost" id="newProjectBtn" type="button">新建项目</button>
    </div>
    <div class="page-head">
      <div>
        <h1>${escapeHtml(tracker.project || "当前项目")}</h1>
        <p>${escapeHtml(tracker.summary || "持续记住项目目标，感知任务与风险变化，并推动下一步行动。")}</p>
      </div>
      <div class="actions"><button class="btn-ghost" id="editProjectBtn" type="button">编辑项目</button><button class="btn" id="addProjectTaskBtn" type="button">添加项目任务</button></div>
    </div>
    <div class="stats">
      ${stat("状态", tracker.status || "进行中", escapeHtml(tracker.stage || "当前阶段"))}
      ${stat("综合进度", progress + "%", "任务 + 节点 + 工作记录")}
      ${stat("验收完成", (tracker.acceptance_progress || 0) + "%", `${acceptance.filter((row) => row.done).length}/${acceptance.length || 0} 项`)}
      ${stat("里程碑", (tracker.milestone_progress || 0) + "%", `${milestones.filter((row) => row.status === "done").length}/${milestones.length || 0} 个`)}
    </div>
    <div class="project-cycle">
      <section><span>记忆</span><b>${acceptance.length + milestones.length} 项项目约定</b><p>${escapeHtml(tracker.objective || tracker.target || "等待补充项目目标")}</p></section>
      <section><span>感知</span><b>${events.length + knowledge.length} 条动态信号</b><p>${risks.length ? `${risks.length} 项风险需要关注` : "当前未发现明确风险"}</p></section>
      <section><span>行动</span><b>${steps.length} 个下一步建议</b><p>${doing.length} 项工作正在推进</p></section>
    </div>
    <div class="project-workspace">
      <main class="project-main">
        <section class="project-band">
          <div class="project-band-head"><div><span class="project-kicker">Remember · 项目记忆</span><h2>目标与验收</h2></div><span class="tiny">${escapeHtml(tracker.start_date || "未设开始")} 至 ${escapeHtml(tracker.target_date || "未设完成时间")}</span></div>
          <div class="project-objective"><span>项目目标</span><p>${escapeHtml(tracker.objective || tracker.target || "还没有明确项目目标。")}</p></div>
          <div class="project-columns">
            <div><h3>验收标准</h3>${acceptance.length ? `<div class="project-checklist">${acceptance.map((row) => `<button type="button" data-project-accept="${escapeHtml(row.id)}" class="${row.done ? "is-done" : ""}"><i>${row.done ? "✓" : ""}</i><span>${escapeHtml(row.text)}</span></button>`).join("")}</div>` : '<p class="tiny">编辑项目并写下“做到什么才算完成”。</p>'}</div>
            <div><h3>时间节点</h3>${milestones.length ? `<div class="milestone-list">${milestones.map((row) => `<button type="button" data-project-milestone="${escapeHtml(row.id)}" class="${row.status === "done" ? "is-done" : ""}"><i></i><span><b>${escapeHtml(row.title)}</b><small>${escapeHtml(row.due_date || "未设日期")} · ${row.status === "done" ? "已完成" : row.status === "in_progress" ? "进行中" : "待推进"}</small></span></button>`).join("")}</div>` : '<p class="tiny">还没有时间节点。</p>'}</div>
          </div>
        </section>
        <section class="project-band">
          <div class="project-band-head"><div><span class="project-kicker">Observe · 动态感知</span><h2>进展与风险</h2></div><span class="tiny">来自任务、对话、知识与工作事件</span></div>
          <div class="project-progress"><div><b>${progress}%</b><span>综合估算进度</span></div><div class="barline"><span style="width:${progress}%"></span></div></div>
          <div class="project-columns">
            <div><h3>正在推进</h3>${doing.length ? `<ul class="track-list">${doing.map((row) => `<li>${escapeHtml(row.title || "")}</li>`).join("")}</ul>` : '<p class="tiny">没有进行中的任务。</p>'}${done.length ? `<p class="tiny">已完成 ${done.length} 项</p>` : ""}</div>
            <div><h3>风险信号</h3>${risks.length ? `<ul class="risk-list">${risks.map((row) => `<li>${escapeHtml(row)}</li>`).join("")}</ul>` : '<p class="tiny">当前没有检测到明确风险。</p>'}</div>
          </div>
        </section>
        <section class="project-band project-action-band">
          <div class="project-band-head"><div><span class="project-kicker">Act · 主动行动</span><h2>下一步</h2></div><button class="btn-ghost" id="addProjectTaskBtn2" type="button">添加任务</button></div>
          ${steps.length ? `<ol class="project-next">${steps.map((row, index) => `<li><span>${index + 1}</span><p>${escapeHtml(row)}</p></li>`).join("")}</ol>` : '<p class="tiny">补充里程碑或添加任务后，Agent 会给出下一步建议。</p>'}
        </section>
      </main>
      <aside class="project-aside">
        <section><h3>项目范围</h3><p>${escapeHtml(tracker.summary || "尚未补充项目说明。")}</p><div class="tags">${(tracker.topics || []).map((topic) => `<span class="tag">${escapeHtml(topic)}</span>`).join("")}</div></section>
        <section><h3>相关知识</h3>${knowledge.length ? knowledge.slice(0, 5).map((row) => `<p class="tiny">${escapeHtml(row.title || "")}</p>`).join("") : '<p class="tiny">还没有匹配到项目知识。</p>'}</section>
        <section><h3>最近感知</h3>${events.length ? events.slice(0, 6).map((row) => `<p class="tiny">${escapeHtml(row.title || row.event_type || "")}</p>`).join("") : '<p class="tiny">项目还没有工作事件。</p>'}</section>
        <section><h3>关联目标</h3>${goals.length ? goals.slice(0, 4).map((goal) => `<p class="tiny">${escapeHtml(goal.title || "")} · ${escapeHtml(String(goal.progress || 0))}%</p>`).join("") : '<p class="tiny">还没有关联目标。</p>'}</section>
      </aside>
    </div>
    ${projectEditor(projects)}`;
}

function projectEditor(projects) {
  if (!state.projectEditorOpen) return "";
  const project = (projects || []).find((row) => row.project_id === state.editingProjectId) || {};
  const acceptance = (project.acceptance_criteria || []).map((row) => `${row.done ? "[x]" : "[ ]"} ${row.text || row.title || ""}`).join("\n");
  const milestones = (project.milestones || []).map((row) => `${row.title || ""} | ${row.due_date || ""} | ${row.status === "done" ? "完成" : row.status === "in_progress" ? "进行中" : "待办"}`).join("\n");
  return `<div class="task-editor-backdrop">
    <aside class="task-editor project-editor" role="dialog" aria-modal="true" aria-labelledby="projectEditorTitle">
      <div class="task-editor-head"><div><span class="tiny">项目长期记忆</span><h2 id="projectEditorTitle">${project.project_id ? "编辑项目" : "新建项目"}</h2></div><button class="icon-btn" id="projectEditorClose" type="button" aria-label="关闭">×</button></div>
      <form id="projectEditorForm">
        <div class="field"><label for="projectName">项目名称</label><input id="projectName" maxlength="160" required value="${escapeHtml(project.project || "")}" placeholder="例如：Personal Agent 2.0" /></div>
        <div class="field"><label for="projectSummary">项目内容</label><textarea id="projectSummary" rows="3" maxlength="1200" placeholder="项目背景、范围和要解决的问题">${escapeHtml(project.summary || "")}</textarea></div>
        <div class="field"><label for="projectObjective">项目目标</label><textarea id="projectObjective" rows="2" maxlength="600" placeholder="最终希望交付什么结果">${escapeHtml(project.objective || "")}</textarea></div>
        <div class="form-grid">
          <div class="field"><label for="projectStage">当前阶段</label><input id="projectStage" maxlength="120" value="${escapeHtml(project.stage || "")}" placeholder="调研 / 开发 / 验收" /></div>
          <div class="field"><label for="projectStatus">状态</label><select id="projectStatus">${[["planning","准备中"],["active","进行中"],["paused","已暂停"],["done","已完成"]].map(([value,label]) => `<option value="${value}"${(project.status_code || project.status || "active") === value ? " selected" : ""}>${label}</option>`).join("")}</select></div>
          <div class="field"><label for="projectStartDate">开始日期</label><input id="projectStartDate" type="date" value="${escapeHtml(project.start_date || "")}" /></div>
          <div class="field"><label for="projectTargetDate">计划完成</label><input id="projectTargetDate" type="date" value="${escapeHtml(project.target_date || "")}" /></div>
          <div class="field"><label for="projectPriority">优先级</label><select id="projectPriority">${[["low","低"],["medium","中"],["high","高"],["urgent","紧急"]].map(([value,label]) => `<option value="${value}"${(project.priority || "medium") === value ? " selected" : ""}>${label}</option>`).join("")}</select></div>
          <div class="field"><label for="projectTopics">关注主题</label><input id="projectTopics" value="${escapeHtml((project.topics || []).join("、"))}" placeholder="Agent、Memory、评测" /></div>
        </div>
        <div class="field"><label for="projectAcceptance">验收标准（每行一项，可用 [x] 标记完成）</label><textarea id="projectAcceptance" rows="5" placeholder="[ ] 核心流程可以稳定运行&#10;[ ] 完成用户验收">${escapeHtml(acceptance)}</textarea></div>
        <div class="field"><label for="projectMilestones">时间节点（名称 | 日期 | 状态）</label><textarea id="projectMilestones" rows="5" placeholder="完成方案评审 | 2026-09-10 | 待办&#10;上线试运行 | 2026-09-30 | 待办">${escapeHtml(milestones)}</textarea></div>
        <div class="task-editor-actions"><button class="btn-ghost" id="projectEditorCancel" type="button">取消</button><button class="btn" type="submit">${project.project_id ? "保存项目" : "创建项目"}</button></div>
      </form>
    </aside>
  </div>`;
}

function pageGoals() {
  const goals = state.dash.goals || [];
  const editing = state.editingGoalId || null;
  const groups = [
    ["today", "今日目标", "把今天的任务变成推荐上下文"],
    ["week", "短期目标", "本周焦点"],
    ["quarter", "长期目标", "季度焦点"],
    ["open", "不定期目标", "持续方向"],
  ];
  const pri = { high: "高优先级", medium: "中优先级", low: "低优先级" };
  return `
    <div class="page-head">
      <div>
        <h1>目标管理</h1>
        <p>编辑、新增、删除目标，让 Agent 的推荐真正围绕你的真实工作展开。</p>
      </div>
    </div>
    <div class="layout">
      <div class="stack">${groups.map(([kind, title]) => {
        const rows = goals.filter((g) => g.kind === kind);
        const done = rows.filter((g) => g.done).length;
        return `<section class="card">
          <div class="page-head" style="margin:0 0 10px">
            <h2 style="margin:0">${title}</h2>
            <span class="tiny">${done}/${rows.length || 0}</span>
            ${!editing ? `<button class="btn-ghost" data-add-goal="${escapeHtml(kind)}" type="button">+ 新增</button>` : ""}
          </div>
          ${rows.map((g) => {
            const isEditing = editing === g.id;
            if (isEditing) {
              return `<div class="item edit-mode" data-edit-goal-id="${escapeHtml(g.id)}">
                <div class="field"><label>标题</label><input id="editGoalTitle-${g.id}" value="${escapeHtml(g.title)}" /></div>
                <div class="field"><label>类型</label><select id="editGoalKind-${g.id}">
                  ${["today","week","quarter","open"].map((k) => `<option${k === g.kind ? " selected" : ""}>${{"today":"今日","week":"短期","quarter":"长期","open":"不定期"}[k]}</option>`).join("")}
                </select></div>
                <div class="field"><label>优先级</label><select id="editGoalPriority-${g.id}">
                  ${Object.keys(pri).map((p) => `<option${p === g.priority ? " selected" : ""}>${pri[p]}</option>`).join("")}
                </select></div>
                <div class="row-actions">
                  <button class="btn" data-save-edit-goal="${escapeHtml(g.id)}" type="button">保存</button>
                  <button class="btn-ghost" data-cancel-edit-goal="1" type="button">取消</button>
                </div>
              </div>`;
            }
            return `<div class="item" data-goal-id="${escapeHtml(g.id)}">
              <div class="item-top">
                <b>${escapeHtml(g.title)}</b>
                <span class="tag ${g.priority==="high"?"orange":"gray"}">${pri[g.priority]||"中优先级"}</span>
              </div>
              <div class="barline"><span style="width:${g.progress||0}%"></span></div>
              <div class="goal-meta">
                <span class="tiny">进度 ${g.progress||0}% · 已关联 ${g.linked||0} 条推荐</span>
                <button class="btn-ghost" data-delete-goal="${escapeHtml(g.id)}" type="button">删除</button>
              </div>
            </div>`;
          }).join("") || "<p class='tiny'>还没有这类目标。点「+ 新增」添加一个。</p>"}
        </section>`;
      }).join("")}
        <details class="card" ${!editing ? "open" : ""}><summary>编辑模式提示</summary>
          <p class="hint">在目标卡片内直接修改标题/类型/优先级；点击任意目标进入编辑态；完成后点「保存」。</p>
        </details>
      </div>
      <aside class="stack">
        <section class="card">
          <h3>目标如何影响推荐</h3>
          <div class="flow">
            <div class="step">Goal</div>
            <div class="arrow">↓</div>
            <div class="step">Current Context<br><span class="tiny">任务 · 时间 · 工具 · 知识</span></div>
            <div class="arrow">↓</div>
            <div class="step">Recommendation Priority</div>
          </div>
          <p class="hint">目标不是普通 TODO，而是推荐系统的重要 Context。</p>
        </section>
        <section class="card">
          <h3>更多能力</h3>
          <div class="coming"><span>Task 自动关联</span><span class="tag" style="background:var(--ok-soft);color:var(--ok)">已上线</span></div>
          <div class="coming"><span>日报生成</span><span class="tag">即将推出</span></div>
          <div class="coming"><span>习惯打卡</span><span class="tag">即将推出</span></div>
        </section>
      </aside>
    </div>`;
}

function pageKnowledge() {
  const cards = (state.dash.cards || []).filter(matchQuery);
  const cat = state.knowledgeCat;
  const filtered = cat === "全部" ? cards : cat === "收藏夹" ? cards.filter((c) => c.favorite) : cards.filter((c) => c.category === cat);
  const counts = Object.fromEntries(CATS.map((name) => [name, cards.filter((c) => c.category === name).length]));
  const selected = state.selectedCard || filtered[0];
  if (selected && !state.selectedCard) state.selectedCard = selected;
  return `
    <div class="page-head">
      <div>
        <h1>知识库</h1>
        <p>你的阅读、点赞和收藏，正在沉淀为可复用的个人知识资产。</p>
      </div>
    </div>
    <div class="banner">LLM 已完成预分类，你也可以手动移动和调整分类。</div>
    <div class="layout-3">
      <aside class="card">
        <button class="btn-ghost" type="button" disabled>+ 新建分类</button>
        <div class="list" style="margin-top:10px">
          <button class="${cat==="全部"?"is-on":""}" data-cat="全部" type="button">全部条目 ${cards.length}</button>
          <button class="${cat==="收藏夹"?"is-on":""}" data-cat="收藏夹" type="button">收藏夹 ${cards.filter((c)=>c.favorite).length}</button>
          ${CATS.map((name) => `<button class="${cat===name?"is-on":""}" data-cat="${name}" type="button">${name} ${counts[name]||0}</button>`).join("")}
        </div>
      </aside>
      <section class="stack">
        ${filtered.map((card) => `
          <article class="item${selected && selected.source_url===card.source_url ? " is-on":""}" data-card="${escapeHtml(card.source_url)}">
            <h3>${escapeHtml(card.title)}</h3>
            <div class="tiny">来源: ${escapeHtml(card.source_name || "")} · 保存 ${escapeHtml(fmtTime(card.saved_at))}</div>
            <p class="muted" style="margin:0">${escapeHtml(card.summary || "")}</p>
            <div class="tags">${tagsHtml(card.tags)}${card.llm_classified ? '<span class="tag">LLM 预分类</span>' : '<span class="tag orange">已手动调整</span>'}</div>
          </article>`).join("") || "<div class='empty'>点赞或收藏推荐后，会自动沉淀到这里。</div>"}
      </section>
      <aside class="card">
        ${selected ? knowledgeDetail(selected) : "<p class='tiny'>选择一条知识查看详情。</p>"}
      </aside>
    </div>`;
}

function knowledgeDetail(card) {
  return `
    <div class="page-head" style="margin:0 0 8px"><h3 style="margin:0">条目详情</h3></div>
    <h2>${escapeHtml(card.title)}</h2>
    <div class="kv">
      <b>来源</b><span><a href="${escapeHtml(card.source_url)}" target="_blank">${escapeHtml(card.source_name || card.source_url)}</a></span>
      <b>保存时间</b><span>${escapeHtml(fmtTime(card.saved_at))}</span>
      <b>所在分类</b><span class="tag">${escapeHtml(card.category || "待整理")}</span>
    </div>
    <p>${escapeHtml(card.summary || "")}</p>
    <div class="field">
      <label>移动到分类</label>
      <select data-move="${escapeHtml(card.id || card.source_url)}">${CATS.map((name) => `<option${card.category===name?" selected":""}>${name}</option>`).join("")}</select>
    </div>
    <div class="row-actions">
      <a class="btn-ghost" href="${escapeHtml(card.source_url)}" target="_blank">打开原文</a>
      <button class="btn-ghost" disabled type="button">分享</button>
    </div>`;
}

function pageSkills() {
  const skills = state.dash.skills || [];
  const enabled = skills.filter((row) => row.status === "enabled");
  const soon = skills.filter((row) => row.status !== "enabled");
  const card = (row) => {
    const ready = row.status === "enabled";
    return `<article class="skill-card${ready ? "" : " is-soon"}" ${ready ? `data-skill="${escapeHtml(row.id)}"` : ""}>
      <div class="item-top"><b>${escapeHtml(row.title || row.name || "")}</b><span class="tag ${ready ? "green" : ""}">${ready ? "已启用" : "Coming Soon"}</span></div>
      <p class="tiny">${escapeHtml(row.name || "")}</p>
      <p>${escapeHtml(row.summary || "")}</p>
      ${ready ? `<button class="btn-ghost" type="button" data-skill="${escapeHtml(row.id)}">${row.example ? "在对话中试用" : "打开"}</button>` : ""}
    </article>`;
  };
  return `
    <div class="page-head">
      <div>
        <h1>办公 Skills</h1>
        <p>秘书能力按 Skill 接入。已启用的可以直接用，其余先占位，不会再做成日期计算器或打卡小工具。</p>
      </div>
    </div>
    <section class="card">
      <h2>已启用</h2>
      <div class="skill-grid">${enabled.map(card).join("")}</div>
    </section>
    <section class="card" style="margin-top:16px">
      <h2>即将推出</h2>
      <div class="skill-grid">${soon.map(card).join("")}</div>
    </section>`;
}

function pageToolbox() {
  return pageSkills();
}

function pageProfile() {
  const dash = state.dash;
  const profile = dash.profile || {};
  const interests = dash.interests || [];
  const push = dash.push_settings || {};
  const stats = dash.stats || {};
  const likes = (dash.cards || []).slice(0, 6);
  const ratio = Number(push.work_personal_ratio || 55);
  const types = ["技术文章","学术论文","GitHub","产品动态","行业资讯","轻松发现"];
  const selectedTypes = push.content_types || ["技术文章","行业资讯","产品动态","轻松发现"];
  return `
    <div class="page-head">
      <div>
        <h1>个人中心</h1>
        <p>管理你的兴趣、偏好和知识沉淀，让 Agent 越来越懂你。</p>
      </div>
      <a class="btn-ghost" href="#/settings/push">通知偏好</a>
    </div>
    <div class="stack">
      <section class="card">
        <div class="userchip" style="gap:14px">
          <span class="avatar" style="width:48px;height:48px;font-size:18px">${escapeHtml((profile.display_name||"张").slice(0,1))}</span>
          <div>
            <b>${escapeHtml(profile.display_name || nameFromUser())}</b>
            <div class="tiny">${escapeHtml(profile.role || "")} · ${escapeHtml(profile.team || "")}</div>
            <p>${escapeHtml(profile.bio || "")}</p>
          </div>
        </div>
      </section>
      <section class="card">
        <h2>兴趣画像</h2>
        <p class="hint">这些兴趣由 LLM 根据交互、阅读、点赞、收藏持续更新。</p>
        <div class="radar-wrap">
          ${radarSvg(interests)}
          <div class="chips">${interests.map((row) => `<span class="chip">${escapeHtml(row.topic)} ${Number(row.weight||0).toFixed(2)}</span>`).join("")}</div>
        </div>
      </section>
      <section class="card">
        <h2>最近点赞 / 收藏</h2>
        <div class="grid-cards">${likes.map((card) => `<div class="mini"><b>${escapeHtml(card.title)}</b><div class="tiny">${escapeHtml(card.source_name||"")} · ${escapeHtml(card.category||"")}</div></div>`).join("") || "<p class='tiny'>还没有收藏。</p>"}</div>
      </section>
      <section class="card">
        <h2>推荐偏好</h2>
        <div class="chips" id="typeChips">${types.map((t)=>`<button class="chip${selectedTypes.includes(t)?" is-on":""}" data-type="${t}" type="button">${t}</button>`).join("")}</div>
        <div class="field" style="margin-top:12px"><label>摘要长度</label>
          <select id="summaryLen">${["简洁","中等","详细"].map((x)=>`<option${(push.summary_length||"详细")===x?" selected":""}>${x}</option>`).join("")}</select>
        </div>
        <div class="field"><label>推送时间</label>
          <select id="pushClock">${["08:30","12:30","18:30"].map((x)=>`<option${(push.push_clock||push.morning_time||"12:30")===x?" selected":""}>${x}</option>`).join("")}</select>
        </div>
        <label>工作 ${ratio}% / 个人 ${100-ratio}%</label>
        <input class="range" id="ratio" type="range" min="20" max="90" value="${ratio}" />
        <button class="btn" id="savePrefBtn" type="button">保存偏好</button>
      </section>
      <section class="card">
        <h2>当前项目与长期目标</h2>
        <p><b>${escapeHtml((dash.project||{}).project || "")}</b></p>
        <p class="tiny">${escapeHtml((dash.project||{}).stage || "")}</p>
        ${goalMini("长期目标", (dash.goals||[]).find((g)=>g.kind==="quarter"))}
      </section>
      <section class="stats">
        ${stat("累计点赞", stats.likes, "行为反馈")}
        ${stat("收藏知识", stats.knowledge, "Knowledge Memory")}
        ${stat("活跃兴趣", interests.length, "Interest Memory")}
        ${stat("反馈记录", stats.feedback, "正在学习你")}
      </section>
    </div>`;
}

function radarSvg(interests) {
  const rows = (interests || []).slice(0, 6);
  const n = Math.max(rows.length, 3);
  const cx = 110;
  const cy = 110;
  const r = 86;
  const pts = rows.map((row, i) => {
    const ang = (Math.PI * 2 * i) / n - Math.PI / 2;
    const rr = r * Number(row.weight || 0.4);
    return [cx + rr * Math.cos(ang), cy + rr * Math.sin(ang)];
  });
  const axes = rows.map((row, i) => {
    const ang = (Math.PI * 2 * i) / n - Math.PI / 2;
    const x = cx + r * Math.cos(ang);
    const y = cy + r * Math.sin(ang);
    const lx = cx + (r + 16) * Math.cos(ang);
    const ly = cy + (r + 16) * Math.sin(ang);
    return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#e5e7eb"/><text x="${lx}" y="${ly}" font-size="10" text-anchor="middle" fill="#6b7280">${escapeHtml(row.topic)}</text>`;
  }).join("");
  return `<svg viewBox="0 0 220 220" width="220" height="220">${axes}<polygon points="${pts.map((p)=>p.join(",")).join(" ")}" fill="rgba(79,70,229,.18)" stroke="#4f46e5"/></svg>`;
}

function pageSettingsPush() {
  const push = state.dash.push_settings || {};
  const brief = state.dash.brief || {};
  const toggle = (key, on, title, desc, tag) => `
    <div class="toggle">
      <div><b>${title}${tag ? ` <span class="tag">${tag}</span>` : ""}</b><div class="tiny">${desc}</div></div>
      <button class="switch${on ? " is-on" : ""}" data-toggle="${key}" type="button"><i></i></button>
    </div>`;
  return `
    <div class="page-head">
      <div>
        <h1>推送与通知</h1>
        <p>在合适时间，通过合适渠道，把真正重要的信息主动送给你。</p>
      </div>
    </div>
    <div class="layout">
      <div class="stack">
        <section class="card">
          <h2>1. 选择接收渠道</h2>
          ${toggle("web", push.web, "Web 站内", "在工作台和右上角通知栏查看。", "推荐")}
          ${toggle("feishu", push.feishu, "飞书", "通过飞书机器人一对一推送。", "推荐")}
          ${toggle("chat", push.chat, "聊天对话", "在对话里主动推送推荐结果。", "可选")}
        </section>
        <section class="card">
          <h2>2. 推送策略</h2>
          ${toggle("morning_brief", push.morning_brief, "Morning Brief", "每天早上生成个性化日报")}
          <div class="field"><label>时间</label><input id="morningTime" value="${escapeHtml(push.morning_time || "08:30")}" /></div>
          ${toggle("instant", push.instant, "即时高相关推送", "发现与当前项目高度相关时立刻推")}
          <div class="field"><label>相关度</label><select id="instantTh"><option value="90"${Number(push.instant_threshold)===90?" selected":""}>高相关（默认）</option><option value="75"${Number(push.instant_threshold)===75?" selected":""}>相关度 ≥ 75%</option><option value="85"${Number(push.instant_threshold)===85?" selected":""}>相关度 ≥ 85%</option></select></div>
          ${toggle("weekly_brief", push.weekly_brief, "每周总结", "每周回顾进展、待办和关键观察")}
          <div class="field"><label>时间</label><input id="weeklyTime" value="${escapeHtml(push.weekly_time || "周一 09:00")}" /></div>
        </section>
        <section class="card">
          <h2>3. 通知规则</h2>
          ${toggle("work_first", push.work_first, "工作推荐优先", "当前工作目标相关内容提高优先级")}
          ${toggle("quiet_hours", push.quiet_hours, "休息时间降低打扰", "减少非紧急推送")}
          ${toggle("high_only", push.high_only, "只推高相关内容", `相关度 ≥ ${push.high_threshold || 75}%`)}
          <button class="btn" id="savePushBtn" type="button">保存推送设置</button>
        </section>
        <section class="card">
          <h2>5. 其他设置</h2>
          <div class="coming"><span>管理对话推送</span><span class="tag">可选</span></div>
          <div class="coming"><span>勿扰时段</span><span class="tiny">${escapeHtml(push.dnd || "22:00 - 08:00")} · 工作日与周末</span></div>
        </section>
      </div>
      <aside class="card">
        <h2>4. 推送预览</h2>
        <div class="feishu">
          <div class="from">个人工作秘书 Agent · 机器人 · ${escapeHtml(push.morning_time || "08:30")}</div>
          <b>你可能错过的 ${(brief.items || []).length || 3} 条重要信息</b>
          <p class="tiny">基于你最近关注的兴趣和当前项目精选。</p>
          ${(brief.items || []).map((row, i) => `<p>${i+1}. ${escapeHtml(row.title || "")}<br><span class="tiny">相关度 ${row.score || 0}% · ${escapeHtml(row.source_name || "")}</span></p>`).join("") || "<p class='tiny'>刷新源后可预览真实条目。</p>"}
          <p class="why"><strong>为什么推荐给你</strong>与你当前项目和近期兴趣高度相关。</p>
          <div class="row-actions">
            <button class="btn-ghost" type="button" disabled>有用</button>
            <button class="btn-ghost" type="button" disabled>收藏</button>
            <button class="btn-ghost" type="button" disabled>不相关</button>
          </div>
        </div>
        <button class="btn" id="pushNowBtn" type="button" style="margin-top:12px">立即推一条到飞书</button>
      </aside>
    </div>`;
}

function pageSettingsProfile() {
  const profile = state.dash.profile || {};
  return `
    <div class="page-head">
      <div>
        <h1>个人信息</h1>
        <p>这些资料会进入 Profile Memory，帮助 Agent 理解你是谁、现在在做什么。</p>
      </div>
    </div>
    <section class="card" style="max-width:640px">
      <div class="field"><label>姓名</label><input id="pName" value="${escapeHtml(profile.display_name || nameFromUser())}" /></div>
      <div class="field"><label>岗位</label><input id="pRole" value="${escapeHtml(profile.role || "")}" /></div>
      <div class="field"><label>团队</label><input id="pTeam" value="${escapeHtml(profile.team || "")}" /></div>
      <div class="field"><label>简介</label><textarea id="pBio">${escapeHtml(profile.bio || "")}</textarea></div>
      <div class="field"><label>时区</label><input id="pTz" value="${escapeHtml(profile.timezone || "GMT +8")}" /></div>
      <div class="field"><label>语言</label><input id="pLang" value="${escapeHtml(profile.languages || "中文 / English")}" /></div>
      <button class="btn" id="saveProfileBtn" type="button">保存到 Memory</button>
    </section>`;
}

function pageSettingsSecurity() {
  const account = (state.dash.account && state.dash.account.user) || {};
  const feishu = (state.dash.account && state.dash.account.feishu) || {};
  return `
    <div class="page-head">
      <div>
        <h1>账号与安全</h1>
        <p>登录账号只属于你。飞书 App ID / Secret 写在这里，推送时用你的应用，不会用别人的。</p>
      </div>
    </div>
    <section class="card" style="max-width:640px">
      <h2>登录账号</h2>
      <div class="field"><label>用户名</label><input value="${escapeHtml(account.username || state.userId)}" disabled /></div>
      <div class="field"><label>当前密码</label><input id="oldPass" type="password" autocomplete="current-password" /></div>
      <div class="field"><label>新密码</label><input id="newPass" type="password" autocomplete="new-password" /></div>
      <button class="btn" id="savePassBtn" type="button">更新密码</button>
    </section>
    <section class="card" style="max-width:640px;margin-top:16px">
      <h2>飞书应用</h2>
      <p class="tiny">在飞书开放平台创建企业自建应用后，把 App ID 和 App Secret 填在下面。Secret 只保存在本机该用户目录，接口不会再读出来。</p>
      <div class="field"><label>App ID</label><input id="fsAppId" value="${escapeHtml(feishu.app_id || "")}" placeholder="cli_xxx" /></div>
      <div class="field"><label>App Secret</label><input id="fsAppSecret" type="password" placeholder="${feishu.app_secret_set ? "已保存，留空则不修改" : "填写 App Secret"}" /></div>
      <div class="field"><label>接收人类型</label>
        <select id="fsReceiveType">
          <option value="email"${(feishu.receive_id_type || "email") === "email" ? " selected" : ""}>邮箱</option>
          <option value="open_id"${feishu.receive_id_type === "open_id" ? " selected" : ""}>open_id</option>
        </select>
      </div>
      <div class="field"><label>接收人 ID / 邮箱</label><input id="fsReceiveId" value="${escapeHtml(feishu.receive_id || "")}" placeholder="you@example.com 或 ou_xxx" /></div>
      <div class="field"><label>手机号（可选，用来换 open_id）</label><input id="fsMobile" value="${escapeHtml(feishu.receive_mobile || "")}" /></div>
      <p class="feishu-verify ${feishu.verification_status === "verified" ? "is-ok" : feishu.verification_status === "failed" ? "is-error" : ""}">
        ${feishu.verification_status === "verified" ? "验证成功：" : feishu.verification_status === "failed" ? "验证失败：" : "尚未验证："}${escapeHtml(feishu.verification_message || "保存后将自动校验 App ID、Secret 和接收人")}
      </p>
      <button class="btn" id="saveFeishuBtn" type="button">保存并验证</button>
    </section>`;
}

function pageSettingsLlm() {
  const llm = state.dash.llm_settings || (state.dash.status && state.dash.status.llm) || {};
  const sourceLabels = {
    settings: "系统设置",
    env: "环境变量",
    "data/llm.json": "系统设置",
    "RadarME/js/config.js": "RadarME 配置",
    none: "未配置",
  };
  const source = sourceLabels[llm.source] || llm.source || "未配置";
  const presets = llm.presets || [];
  return `
    <div class="page-head">
      <div>
        <h1>大模型</h1>
        <p>配置 OpenAI 兼容网关和 API Key。密钥只保存在本机 data/llm.json，接口不会把完整密钥再读出来。</p>
      </div>
    </div>
    <section class="card" style="max-width:640px">
      <div class="toggle">
        <div><b>启用大模型</b><div class="tiny">关闭后，对话路由、任务抽取和推荐重排会退回启发式。</div></div>
        <button class="switch${llm.enabled ? " is-on" : ""}" id="llmEnabledBtn" type="button"><i></i></button>
      </div>
      <p class="feishu-verify ${llm.active ? "is-ok" : ""}">${llm.active ? "当前已接通：" : "尚未接通："}${escapeHtml(llm.model || "未选择模型")} · 来源 ${escapeHtml(source)}</p>
      <div class="field"><label>快捷预设</label>
        <div class="chips">${presets.map((row) => `<button class="chip" data-llm-preset="${escapeHtml(row.id)}" type="button">${escapeHtml(row.label)}</button>`).join("")}</div>
      </div>
      <div class="field"><label>网关地址</label><input id="llmBaseUrl" value="${escapeHtml(llm.base_url || "")}" placeholder="https://api.siliconflow.cn/v1" /></div>
      <div class="field"><label>模型名</label><input id="llmModel" value="${escapeHtml(llm.model || "")}" placeholder="deepseek-ai/DeepSeek-V4-Flash" /></div>
      <div class="field"><label>API Key</label><input id="llmApiKey" type="password" autocomplete="off" placeholder="${llm.api_key_set ? "已保存，留空则不修改" : "填写 API Key；本地网关可留空"}" /></div>
      <p class="hint">支持硅基流动、OpenAI 以及任何 OpenAI 兼容网关。本地 127.0.0.1 / localhost 可不填 Key。</p>
      <div class="row-actions">
        <button class="btn" id="saveLlmBtn" type="button">保存</button>
        <button class="btn-ghost" id="testLlmBtn" type="button">测试连接</button>
      </div>
    </section>`;
}

function pageSettingsPrefs() {
  const dash = state.dash;
  const push = dash.push_settings || {};
  const ratio = Number(push.work_personal_ratio || 55);
  const types = ["技术文章","学术论文","GitHub","产品动态","行业资讯","轻松发现"];
  const selectedTypes = push.content_types || ["技术文章","行业资讯","产品动态","轻松发现"];
  return `
    <div class="page-head">
      <div>
        <h1>偏好设置</h1>
        <p>内容类型、摘要长度和工作/个人比例，会直接影响下一轮推荐排序。</p>
      </div>
    </div>
    <section class="card" style="max-width:640px">
      <h2>内容类型</h2>
      <div class="chips" id="typeChips">${types.map((t)=>`<button class="chip${selectedTypes.includes(t)?" is-on":""}" data-type="${t}" type="button">${t}</button>`).join("")}</div>
      <div class="field" style="margin-top:12px"><label>摘要长度</label>
        <select id="summaryLen">${["简洁","中等","详细"].map((x)=>`<option${(push.summary_length||"详细")===x?" selected":""}>${x}</option>`).join("")}</select>
      </div>
      <div class="field"><label>推送时间</label>
        <select id="pushClock">${["08:30","12:30","18:30"].map((x)=>`<option${(push.push_clock||push.morning_time||"12:30")===x?" selected":""}>${x}</option>`).join("")}</select>
      </div>
      <label>工作 ${ratio}% / 个人 ${100-ratio}%</label>
      <input class="range" id="ratio" type="range" min="20" max="90" value="${ratio}" />
      <button class="btn" id="savePrefBtn" type="button">保存偏好</button>
    </section>`;
}

function pageSettingsPrivacy() {
  const stats = state.dash.stats || {};
  return `
    <div class="page-head">
      <div>
        <h1>数据与隐私</h1>
        <p>Memory、收藏和反馈都存在本机 data/，不会默认同步到云端。</p>
      </div>
    </div>
    <section class="card" style="max-width:640px">
      <p>当前已沉淀知识 ${stats.knowledge || 0} 条，点赞 ${stats.likes || 0} 次，反馈 ${stats.feedback || 0} 条。</p>
      <div class="row-actions">
        <button class="btn-ghost" id="exportBtn" type="button">导出我的数据</button>
        <button class="btn-ghost" type="button" disabled>清除行为记录</button>
      </div>
      <p class="hint">导出为浏览器下载的 JSON，包含画像、目标、推送偏好和知识条目。</p>
    </section>`;
}

function pageSettingsMembers() {
  const name = (state.dash.profile || {}).display_name || nameFromUser();
  return `
    <div class="page-head">
      <div>
        <h1>成员与权限</h1>
        <p>当前是个人工作台。团队协作、角色权限会作为后续 Skills 接入。</p>
      </div>
    </div>
    <section class="card" style="max-width:640px">
      <div class="coming"><span>${escapeHtml(name)} · 所有者</span><span class="tag green">个人版</span></div>
      <div class="coming"><span>邀请成员</span><span class="tag">即将推出</span></div>
      <div class="coming"><span>只读访客</span><span class="tag">即将推出</span></div>
    </section>`;
}

// 全局路由跳转函数
function go(hash) {
  if (hash.startsWith("#")) hash = hash.slice(1);
  location.hash = hash;
}

// PAGES 映射表（页面路由）
const PAGES = {
  "/": pageHome,
  "/chat": pageChat,
  "/work": pageWork,
  "/projects": pageProjects,
  "/reports": pageReports,
  "/recommend": pageRecommend,
  "/follows": pageFollows,
  "/goals": pageGoals,
  "/knowledge": pageKnowledge,
  "/skills": pageSkills,
  "/toolbox": pageSkills,
  "/profile": pageProfile,
  "/settings": pageSettingsPush,
  "/settings/push": pageSettingsPush,
  "/settings/profile": pageSettingsProfile,
  "/settings/security": pageSettingsSecurity,
  "/settings/llm": pageSettingsLlm,
  "/settings/prefs": pageSettingsPrefs,
  "/settings/privacy": pageSettingsPrivacy,
  "/settings/members": pageSettingsMembers,
};

function currentRoute() {
  const path = hashLocation().path;
  if (path === "/settings") return "/settings/push";
  if (path === "/toolbox") return "/skills";
  if (path === "/feedback") return "/recommend";
  return PAGES[path] ? path : "/";
}

function hashLocation() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const queryAt = raw.indexOf("?");
  const path = queryAt >= 0 ? raw.slice(0, queryAt) : raw;
  const query = queryAt >= 0 ? raw.slice(queryAt + 1) : "";
  return { path: path || "/", params: new URLSearchParams(query) };
}

function syncRouteState() {
  const { path, params } = hashLocation();
  const tab = path === "/feedback" ? "feedback" : params.get("tab");
  if (["all", "work", "personal", "feedback"].includes(tab)) state.recTab = tab;
}

function render() {
  const { path } = hashLocation();
  if (path === "/settings") {
    location.hash = "#/settings/push";
    return;
  }
  if (path === "/toolbox") {
    location.hash = "#/skills";
    return;
  }
  syncRouteState();
  state.route = currentRoute();
  renderChrome();
  if (!state.dash) {
    $("page").innerHTML = `<div class="empty">正在连接记忆引擎…</div>`;
    return;
  }
  const view = PAGES[state.route] || pageHome;
  $("page").innerHTML = view() + recommendationDetailHtml();
  if (state.pendingChatExample && $("chatInput")) {
    $("chatInput").value = state.pendingChatExample;
    $("chatInput").focus();
    state.pendingChatExample = "";
  }
}

async function load() {
  state.dash = await api("/api/dashboard");
  state.userId = state.dash.current_user || state.userId;
  if (state.route === "/chat" && !state.chatSessions.length) await loadChatState(true);
  if (state.route === "/reports") {
    try {
      state.workSummary = await api(`/api/work/summary?days=${encodeURIComponent(state.summaryRange || "7")}`);
    } catch { state.workSummary = null; }
  }
  if (state.route === "/follows") {
    try {
      state.followsOverview = await api("/api/follows/overview");
    } catch { state.followsOverview = null; }
  }
  hideAuth();
  render();
}

async function loadChatState(selectLatest = false) {
  const [sessions, profile] = await Promise.all([
    api("/api/conversations"),
    api("/api/conversation-profile"),
  ]);
  state.chatSessions = sessions.items || [];
  state.conversationProfile = profile;
  if (!state.activeSessionId && selectLatest && state.chatSessions.length) {
    state.activeSessionId = state.chatSessions[0].id;
  }
  if (state.activeSessionId) {
    const detail = await api(`/api/conversations/${encodeURIComponent(state.activeSessionId)}`);
    state.chatMessages = detail.messages || [];
  } else {
    state.chatMessages = [];
  }
}

async function enterSession(session) {
  state.token = session.token || state.token;
  if (state.token) localStorage.setItem("radar_session", state.token);
  state.userId = (session.user && session.user.id) || state.userId;
  hideAuth();
  await load();
}

async function boot() {
  try {
    const me = await api("/api/me");
    state.userId = (me.user && me.user.id) || "";
    hideAuth();
    await load();
  } catch {
    showAuth();
    setAuthMode(false);
  }
}

async function act(id, action) {
  const item = [...(state.dash.for_you || []), ...(state.dash.intel || [])].find((row) => row.id === id);
  if (action === "open" && item?.source_url) window.open(item.source_url, "_blank");
  const out = await api("/api/events", { method: "POST", body: JSON.stringify({ id, action }) });
  toast(out.note || "已记下，Agent 正在学习你。");
  await load();
}

async function refreshFeeds(btn) {
  if (btn) btn.disabled = true;
  try {
    toast("正在采集并理解信息源…");
    await api("/api/refresh", { method: "POST", body: "{}" });
    await load();
    toast(`今天观察了 ${state.dash.observe?.fetched || 0} 条，筛出 ${state.dash.for_you?.length || 0} 条给你。`);
  } catch (err) {
    toast(err.message || "刷新失败");
  } finally {
    if (btn) btn.disabled = false;
  }
}

document.addEventListener("click", async (event) => {
  const t = event.target.closest("[data-act],[data-open],[data-rec-detail],[data-rec-backdrop],[data-rectab],[data-filter],[data-cat],[data-card],[data-topic],[data-example],[data-toggle],[data-move],[data-followkind],[data-chat-session],[data-chat-example],[data-task-act],[data-task-edit],[data-task-new],[data-work-date],[data-work-shift],[data-work-view],[data-project-select],[data-project-accept],[data-project-milestone],[data-report-tab],[data-skill],[data-llm-preset],[data-copy-report],[data-export-report],[data-regen-report],[data-jump-day],[data-interest-weight],[data-interest-delete],[data-product-edit],[data-product-cancel],[data-product-save],[data-product-toggle],[data-source-delete],[data-add-goal],[data-save-edit-goal],[data-cancel-edit-goal],[data-delete-goal],#recDetailClose,#newChatBtn,#saveConversationProfileBtn,#refreshBtn,#refreshBtn2,#followBtn,#addGoalBtn,#savePrefBtn,#savePushBtn,#pushNowBtn,#briefBtn,#noticeBtn,#saveProfileBtn,#exportBtn,#addProductBtn,#addSourceBtn,#addFollowGoalBtn,#logoutBtn,#savePassBtn,#saveFeishuBtn,#llmEnabledBtn,#saveLlmBtn,#testLlmBtn,#generateReportBtn,#copyReportBtn,#exportReportBtn,#saveReportBtn,#addWorkTaskBtn,#workTodayBtn,#taskEditorClose,#taskEditorCancel,#newProjectBtn,#editProjectBtn,#addProjectTaskBtn,#addProjectTaskBtn2,#projectEditorClose,#projectEditorCancel");
  if (!t) return;
  if (t.dataset.recDetail) {
    state.recDetailId = t.dataset.recDetail;
    return render();
  }
  if (t.id === "recDetailClose" || (t.dataset.recBackdrop !== undefined && t === event.target)) {
    state.recDetailId = null;
    return render();
  }
  if (t.dataset.chatSession) {
    state.activeSessionId = t.dataset.chatSession;
    const detail = await api(`/api/conversations/${encodeURIComponent(state.activeSessionId)}`);
    state.chatMessages = detail.messages || [];
    render();
    return;
  }
  if (t.dataset.chatExample) {
    if ($("chatInput")) $("chatInput").value = t.dataset.chatExample;
    $("chatInput")?.focus();
    return;
  }
  if (t.id === "newChatBtn") {
    state.activeSessionId = null;
    state.chatMessages = [];
    render();
    $("chatInput")?.focus();
    return;
  }
  if (t.id === "saveConversationProfileBtn") {
    state.conversationProfile = await api("/api/conversation-profile", { method: "PUT", body: JSON.stringify({
      verbosity: $("cpVerbosity").value,
      answer_style: $("cpAnswerStyle").value,
      technical_detail: $("cpTechnical").value,
      proactive_level: $("cpProactive").value,
      confirmation_policy: $("cpConfirm").value,
    }) });
    toast("对话偏好已保存，下一条回复开始生效。");
    render();
    return;
  }
  if (t.id === "noticeBtn") {
    $("noticePop").hidden = !$("noticePop").hidden;
    return;
  }
  if (t.dataset.reportTab) {
    state.reportType = t.dataset.reportTab;
    await load();
    return;
  }
  if (t.id === "summaryRange" || t.closest("#summaryRange")) {
    return;
  }
  if (t.dataset.copyReport) {
    const row = (workDesk().reports || []).find((r) => r.id === t.dataset.copyReport);
    const text = row ? row.content || "" : "";
    if (!text) return toast("还没有可复制的内容");
    await navigator.clipboard.writeText(text).catch(() => {});
    toast("已复制到剪贴板。");
    return;
  }
  if (t.dataset.exportReport) {
    const row = (workDesk().reports || []).find((r) => r.id === t.dataset.exportReport);
    const text = row ? row.content || "" : "";
    if (!text) return toast("还没有可导出的内容");
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `daily-${t.dataset.exportReport}.md`;
    a.click();
    toast("已导出 Markdown。");
    return;
  }
  if (t.dataset.regenReport) {
    await api("/api/work/reports/generate", { method: "POST", body: JSON.stringify({ report_type: "daily", start_time: `${t.dataset.regenReport}T00:00:00+08:00`, end_time: `${t.dataset.regenReport}T23:59:59+08:00` }) });
    toast("已重新生成当天日报。");
    return load();
  }
  if (t.dataset.jumpDay) {
    const target = document.getElementById(`day-${t.dataset.jumpDay}`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (t.dataset.interestWeight) {
    const topic = t.dataset.interestWeight;
    const interests = state.dash.interests || [];
    const row = interests.find((r) => r.topic === topic);
    if (!row) return toast("未找到该主题");
    const delta = t.dataset.dir === "up" ? 0.08 : -0.08;
    const weight = Math.max(0.05, Math.min(0.99, Number(row.weight || 0.5) + delta));
    const items = interests.map((r) => (r.topic === topic ? { ...r, weight: Number(weight.toFixed(2)) } : r));
    await api("/api/interests", { method: "PUT", body: JSON.stringify({ items }) });
    toast(`「${topic}」权重已调整为 ${weight.toFixed(2)}`);
    return load();
  }
  if (t.dataset.interestDelete) {
    const topic = t.dataset.interestDelete;
    if (!confirm(`删除主题关注「${topic}」？`)) return;
    const items = (state.dash.interests || []).filter((r) => r.topic !== topic);
    await api("/api/interests", { method: "PUT", body: JSON.stringify({ items }) });
    toast(`已删除「${topic}」`);
    return load();
  }
  if (t.dataset.productEdit) {
    const row = (state.dash.products || []).find((r) => r.id === t.dataset.productEdit);
    state.editingProduct = row ? { ...row } : null;
    return render();
  }
  if (t.dataset.productCancel) {
    state.editingProduct = null;
    return render();
  }
  if (t.dataset.productSave) {
    const id = t.dataset.productSave;
    const name = $("editProductName")?.value.trim();
    const status = $("editProductStatus")?.value || "持续跟踪";
    const running = ($("editProductRunning")?.value || "on") === "on";
    if (!name) return toast("名称不能为空");
    const items = (state.dash.products || []).map((r) => (r.id === id ? { ...r, name, status, running } : r));
    await api("/api/products", { method: "PUT", body: JSON.stringify({ items }) });
    state.editingProduct = null;
    toast("产品关注已更新。");
    return load();
  }
  if (t.dataset.productToggle) {
    const id = t.dataset.productToggle;
    const running = t.dataset.running === "on";
    const items = (state.dash.products || []).map((r) => (r.id === id ? { ...r, running } : r));
    await api("/api/products", { method: "PUT", body: JSON.stringify({ items }) });
    toast(running ? "已恢复跟踪。" : "已暂停跟踪。");
    return load();
  }
  if (t.dataset.sourceDelete) {
    if (!confirm("删除这个自定义信息源？")) return;
    await api(`/api/user-sources/${encodeURIComponent(t.dataset.sourceDelete)}`, { method: "DELETE" });
    toast("信息源已删除。");
    return load();
  }
  if (t.id === "generateReportBtn") {
    await api("/api/work/reports/generate", { method: "POST", body: JSON.stringify({ report_type: state.reportType || "daily" }) });
    toast("已根据当前工作记忆生成总结。");
    return load();
  }
  if (t.id === "copyReportBtn") {
    const text = $("reportContent")?.textContent || $("reportEditor")?.value || "";
    if (!text) return toast("还没有可复制的内容");
    await navigator.clipboard.writeText(text).catch(() => {});
    toast("已复制到剪贴板。");
    return;
  }
  if (t.id === "exportReportBtn") {
    const text = $("reportEditor")?.value || $("reportContent")?.textContent || "";
    if (!text) return toast("还没有可导出的内容");
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${state.reportType || "daily"}-report.md`;
    a.click();
    toast("已导出 Markdown。");
    return;
  }
  if (t.id === "saveReportBtn") {
    const id = t.dataset.reportId;
    const content = $("reportEditor")?.value || "";
    if (!id) return toast("没有可保存的报告");
    await api(`/api/work/reports/${id}`, { method: "PUT", body: JSON.stringify({ content }) });
    toast("已保存修改。");
    return load();
  }
  if (t.dataset.skill) {
    const skill = (state.dash.skills || []).find((row) => row.id === t.dataset.skill);
    if (!skill || skill.status !== "enabled") {
      toast("这个 Skill 即将推出。");
      return;
    }
    if (skill.report_type) state.reportType = skill.report_type;
    if (skill.example) {
      state.pendingChatExample = skill.example;
      if (location.hash === "#/chat") {
        render();
        return;
      }
      location.hash = "#/chat";
      return;
    }
    location.hash = skill.href || "#/skills";
    return;
  }
  if (t.id === "logoutBtn") {
    await api("/api/auth/logout", { method: "POST", body: "{}" }).catch(() => {});
    state.token = "";
    localStorage.removeItem("radar_session");
    showAuth();
    setAuthMode(false);
    toast("已退出");
    return;
  }
  if (t.id === "newProjectBtn") {
    state.editingProjectId = null;
    state.projectEditorOpen = true;
    render();
    requestAnimationFrame(() => $("projectName")?.focus());
    return;
  }
  if (t.id === "editProjectBtn") {
    state.editingProjectId = (state.dash.tracker || {}).project_id || null;
    state.projectEditorOpen = true;
    render();
    requestAnimationFrame(() => $("projectName")?.focus());
    return;
  }
  if (t.id === "projectEditorClose" || t.id === "projectEditorCancel") {
    state.projectEditorOpen = false;
    state.editingProjectId = null;
    render();
    return;
  }
  if (t.dataset.projectSelect) {
    await api(`/api/projects/${encodeURIComponent(t.dataset.projectSelect)}/activate`, { method: "POST", body: "{}" });
    await load();
    toast("已切换当前项目，后续对话和推荐会使用这份项目记忆。");
    return;
  }
  if (t.id === "addProjectTaskBtn" || t.id === "addProjectTaskBtn2") {
    const tracker = state.dash.tracker || {};
    state.pendingTaskProject = { id: tracker.project_id || "", name: tracker.project || "" };
    state.editingTaskId = null;
    state.taskEditorOpen = true;
    location.hash = "#/work";
    return;
  }
  if (t.dataset.projectAccept) {
    const tracker = state.dash.tracker || {};
    const criteria = (tracker.acceptance_criteria || []).map((row) => ({ ...row, done: row.id === t.dataset.projectAccept ? !row.done : !!row.done }));
    await api(`/api/projects/${encodeURIComponent(tracker.project_id)}`, { method: "PUT", body: JSON.stringify({ acceptance_criteria: criteria }) });
    await load();
    toast("验收状态已更新，项目记忆和进度已同步。");
    return;
  }
  if (t.dataset.projectMilestone) {
    const tracker = state.dash.tracker || {};
    const milestones = (tracker.milestones || []).map((row) => ({ ...row, status: row.id === t.dataset.projectMilestone ? (row.status === "done" ? "pending" : "done") : row.status }));
    await api(`/api/projects/${encodeURIComponent(tracker.project_id)}`, { method: "PUT", body: JSON.stringify({ milestones }) });
    await load();
    toast("时间节点已更新，风险和下一步建议会重新计算。");
    return;
  }
  if (t.id === "addWorkTaskBtn" || t.dataset.taskNew !== undefined) {
    state.pendingTaskProject = null;
    state.editingTaskId = null;
    state.taskEditorOpen = true;
    render();
    requestAnimationFrame(() => $("workTaskTitle")?.focus());
    return;
  }
  if (t.dataset.taskEdit) {
    state.editingTaskId = t.dataset.taskEdit;
    state.taskEditorOpen = true;
    render();
    requestAnimationFrame(() => $("workTaskTitle")?.focus());
    return;
  }
  if (t.id === "taskEditorClose" || t.id === "taskEditorCancel") {
    state.taskEditorOpen = false;
    state.editingTaskId = null;
    state.pendingTaskProject = null;
    render();
    return;
  }
  if (t.dataset.workDate) {
    state.workDate = t.dataset.workDate;
    state.workView = "day";
    render();
    return;
  }
  if (t.dataset.workShift) {
    state.workDate = shiftDateKey(state.workDate, Number(t.dataset.workShift));
    render();
    return;
  }
  if (t.id === "workTodayBtn") {
    state.workDate = localDateKey(new Date());
    state.workView = "day";
    render();
    return;
  }
  if (t.dataset.workView) {
    state.workView = t.dataset.workView;
    render();
    return;
  }
  if (t.dataset.taskAct && t.dataset.taskId) {
    const id = t.dataset.taskId;
    if (t.dataset.taskAct === "breakdown") {
      const out = await api(`/api/work/tasks/${id}/breakdown`, { method: "POST", body: "{}" });
      toast(`已拆成 ${(out.items || []).length} 步`);
      return load();
    }
    const status = t.dataset.taskAct === "done" ? "done" : "in_progress";
    await api(`/api/work/tasks/${id}`, { method: "PUT", body: JSON.stringify({ status }) });
    toast(status === "done" ? "已完成" : "已开始");
    return load();
  }
  if (t.dataset.act) return act(t.dataset.id, t.dataset.act);
  if (t.dataset.open) return act(t.dataset.open, "open");
  if (t.dataset.rectab) {
    state.recTab = t.dataset.rectab;
    return render();
  }
  if (t.dataset.filter) {
    state.recFilter = t.dataset.filter;
    return render();
  }
  if (t.dataset.followkind) {
    state.followKind = t.dataset.followkind;
    return render();
  }
  if (t.dataset.cat) {
    state.knowledgeCat = t.dataset.cat;
    state.selectedCard = null;
    return render();
  }
  if (t.dataset.card) {
    state.selectedCard = (state.dash.cards || []).find((c) => c.source_url === t.dataset.card);
    return render();
  }
  if (t.dataset.topic && $("followText")) $("followText").value = `帮我关注 ${t.dataset.topic}`;
  if (t.dataset.example && $("followText")) $("followText").value = t.dataset.example;
  if (t.id === "followBtn") {
    const text = $("followText")?.value || "";
    const out = await api("/api/follows", { method: "POST", body: JSON.stringify({ text }) });
    toast(out.note || "已创建关注");
    return load();
  }
  if (t.dataset.addGoal) {
    const kind = t.dataset.addGoal;
    $("goalTitle")?.focus();
    state.editingGoalId = null;
    return render(); // 会重新渲染，但 addGoalBtn 已消失，改为直接调用 API
    // 简化：直接调用 POST /api/goals
    const title = `新目标 (${kind})`;
    await api("/api/goals", { method: "POST", body: JSON.stringify({ title, kind }) });
    toast("已添加目标。点击卡片可编辑。");
    return load();
  }
  if (t.dataset.saveEditGoal) {
    const id = t.dataset.saveEditGoal;
    const title = $("editGoalTitle-" + id)?.value.trim();
    const kind = $("editGoalKind-" + id)?.value || "today";
    const priority = $("editGoalPriority-" + id)?.value || "medium";
    if (!title) return toast("标题不能为空");
    await api(`/api/goals/${id}`, { method: "PUT", body: JSON.stringify({ title, kind, priority }) });
    state.editingGoalId = null;
    toast("目标已更新。");
    return load();
  }
  if (t.dataset.cancelEditGoal) {
    state.editingGoalId = null;
    return render();
  }
  if (t.dataset.deleteGoal) {
    const id = t.dataset.deleteGoal;
    if (!confirm("删除这个目标？关联的推荐上下文不会被清除。")) return;
    await api(`/api/goals/${id}`, { method: "DELETE" });
    toast("目标已删除。");
    return load();
  }
  if (t.id === "savePrefBtn") {
    const types = [...document.querySelectorAll("#typeChips .chip.is-on")].map((el) => el.dataset.type);
    await api("/api/push-settings", { method: "PUT", body: JSON.stringify({
      content_types: types,
      summary_length: $("summaryLen").value,
      push_clock: $("pushClock").value,
      work_personal_ratio: Number($("ratio").value),
    }) });
    toast("已更新推荐偏好，后续排序会按这个比例倾斜。");
    return load();
  }
  if (t.id === "savePushBtn") {
    await api("/api/push-settings", { method: "PUT", body: JSON.stringify({
      morning_time: $("morningTime")?.value,
      weekly_time: $("weeklyTime")?.value,
      instant_threshold: Number($("instantTh")?.value || 90),
    }) });
    toast("推送设置已保存。超过阈值的内容会主动找你。");
    return load();
  }
  if (t.id === "pushNowBtn") {
    const out = await api("/api/push/feishu", { method: "POST", body: "{}" });
    toast(out.ok ? `已尝试推送：${out.title || ""}` : (out.reason || "当前没有达到推送阈值的内容"));
    return;
  }
  if (t.id === "saveProfileBtn") {
    await api("/api/memory/profile", { method: "PUT", body: JSON.stringify({
      display_name: $("pName").value,
      role: $("pRole").value,
      team: $("pTeam").value,
      bio: $("pBio").value,
      timezone: $("pTz").value,
      languages: $("pLang").value,
    }) });
    toast("已更新 Profile Memory。");
    return load();
  }
  if (t.id === "savePassBtn") {
    try {
      await api("/api/account/password", { method: "PUT", body: JSON.stringify({
        old_password: $("oldPass").value,
        new_password: $("newPass").value,
      }) });
      toast("密码已更新。");
      $("oldPass").value = "";
      $("newPass").value = "";
    } catch (err) {
      toast(err.message || "更新密码失败");
    }
    return;
  }
  if (t.id === "saveFeishuBtn") {
    try {
      const out = await api("/api/account/feishu", { method: "PUT", body: JSON.stringify({
        app_id: $("fsAppId").value,
        app_secret: $("fsAppSecret").value,
        receive_id_type: $("fsReceiveType").value,
        receive_id: $("fsReceiveId").value,
        receive_mobile: $("fsMobile").value,
      }) });
      toast(out.verification_status === "verified" ? "飞书设置已保存并验证成功。" : `设置已保存，但验证失败：${out.verification_message || "请检查配置"}`);
      return load();
    } catch (err) {
      toast(err.message || "保存飞书设置失败");
      return;
    }
  }
  if (t.id === "llmEnabledBtn") {
    t.classList.toggle("is-on");
    return;
  }
  if (t.dataset.llmPreset) {
    const llm = state.dash.llm_settings || {};
    const preset = (llm.presets || []).find((row) => row.id === t.dataset.llmPreset);
    if (!preset) return;
    if ($("llmBaseUrl")) $("llmBaseUrl").value = preset.base_url || "";
    if ($("llmModel")) $("llmModel").value = preset.model || "";
    return;
  }
  if (t.id === "saveLlmBtn") {
    try {
      await api("/api/settings/llm", { method: "PUT", body: JSON.stringify({
        enabled: $("llmEnabledBtn") ? $("llmEnabledBtn").classList.contains("is-on") : true,
        base_url: $("llmBaseUrl").value.trim(),
        model: $("llmModel").value.trim(),
        api_key: $("llmApiKey").value,
      }) });
      if ($("llmApiKey")) $("llmApiKey").value = "";
      toast("大模型设置已保存。");
      return load();
    } catch (err) {
      toast(err.message || "保存大模型设置失败");
      return;
    }
  }
  if (t.id === "testLlmBtn") {
    try {
      await api("/api/settings/llm", { method: "PUT", body: JSON.stringify({
        enabled: $("llmEnabledBtn") ? $("llmEnabledBtn").classList.contains("is-on") : true,
        base_url: $("llmBaseUrl").value.trim(),
        model: $("llmModel").value.trim(),
        api_key: $("llmApiKey").value,
      }) });
      if ($("llmApiKey")) $("llmApiKey").value = "";
      const out = await api("/api/settings/llm/test", { method: "POST", body: "{}" });
      toast(out.ok ? `连接成功：${out.reply || "ok"}` : (out.reason || "连接失败"));
      return load();
    } catch (err) {
      toast(err.message || "测试大模型连接失败");
      return;
    }
  }
  if (t.id === "exportBtn") {
    const blob = new Blob([JSON.stringify(state.dash, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "secretary-memory.json";
    a.click();
    toast("已导出本机 Memory 快照。");
    return;
  }
  if (t.id === "addProductBtn") {
    const name = $("productName").value.trim();
    if (!name) return toast("请填写产品名称");
    const items = [...(state.dash.products || []), { id: `p-${Date.now()}`, name, status: $("productStatus").value, running: true }];
    await api("/api/products", { method: "PUT", body: JSON.stringify({ items }) });
    toast(`已开始跟踪 ${name}，会纳入后续观察。`);
    return load();
  }
  if (t.id === "addSourceBtn") {
    const name = $("sourceName").value.trim();
    const url = $("sourceUrl").value.trim();
    if (!name) return toast("请填写信息源名称");
    if (!url) return toast("请填写链接或 RSS");
    const type = $("sourceType")?.value || "blog";
    const kind = type === "release" ? "github_releases" : "rss";
    try {
      await api("/api/user-sources", { method: "POST", body: JSON.stringify({
        name,
        url: kind === "rss" ? url : "",
        repo: type === "release" ? url.replace(/^https?:\/\/github\.com\//, "").replace(/\/releases$/, "") : "",
        kind,
        type,
        max: 5,
      }) });
    } catch (err) {
      return toast(err.message || "添加失败");
    }
    toast("信息源已加入，下次「刷新源」开始采集。");
    return load();
  }
  if (t.id === "addFollowGoalBtn") {
    const title = $("followGoalTitle").value.trim();
    if (!title) return toast("请填写目标");
    const items = [...(state.dash.goals || []), { id: `g-${Date.now()}`, kind: $("followGoalKind").value, title, priority: "medium", progress: 0, linked: 0, done: false }];
    await api("/api/goals", { method: "PUT", body: JSON.stringify({ items }) });
    toast("目标已进入推荐上下文。");
    return load();
  }
  if (t.dataset.toggle) {
    const key = t.dataset.toggle;
    const next = !(state.dash.push_settings || {})[key];
    await api("/api/push-settings", { method: "PUT", body: JSON.stringify({ [key]: next }) });
    return load();
  }
});

document.addEventListener("change", async (event) => {
  const t = event.target;
  if (t.dataset.sort) {
    state.recSort = t.value;
    return render();
  }
  if (t.id === "summaryRange") {
    state.summaryRange = t.value || "7";
    await load();
    return;
  }
  if (t.dataset.move) {
    const out = await api("/api/cards/move", { method: "POST", body: JSON.stringify({ id: t.dataset.move, category: t.value }) });
    toast(out.note || "已调整分类");
    return load();
  }
  if (t.id === "followText") return;
});

document.addEventListener("input", (event) => {
  if (event.target.id === "followText" && $("followCount")) $("followCount").textContent = String(event.target.value.length);
  if (event.target.id === "searchInput") {
    state.query = event.target.value;
    render();
  }
});

document.addEventListener("submit", async (event) => {
  if (event.target.id === "projectEditorForm") {
    event.preventDefault();
    const name = $("projectName")?.value.trim() || "";
    if (!name) return;
    const criteria = ($("projectAcceptance")?.value || "").split(/\r?\n/).map((line, index) => {
      const text = line.replace(/^\s*\[(?:x|X| )\]\s*/, "").trim();
      return text ? { id: `accept-${index + 1}`, text, done: /^\s*\[(?:x|X)\]/.test(line) } : null;
    }).filter(Boolean);
    const milestones = ($("projectMilestones")?.value || "").split(/\r?\n/).map((line, index) => {
      const [title, dueDate, rawStatus] = line.split("|").map((part) => part.trim());
      if (!title) return null;
      const status = /完成/.test(rawStatus || "") ? "done" : /进行/.test(rawStatus || "") ? "in_progress" : "pending";
      return { id: `milestone-${index + 1}`, title, due_date: dueDate || "", status };
    }).filter(Boolean);
    const payload = {
      project: name,
      summary: $("projectSummary")?.value.trim() || "",
      objective: $("projectObjective")?.value.trim() || "",
      stage: $("projectStage")?.value.trim() || "",
      status: $("projectStatus")?.value || "active",
      start_date: $("projectStartDate")?.value || "",
      target_date: $("projectTargetDate")?.value || "",
      priority: $("projectPriority")?.value || "medium",
      topics: ($("projectTopics")?.value || "").split(/[,，、\n]+/).map((item) => item.trim()).filter(Boolean),
      acceptance_criteria: criteria,
      milestones,
    };
    try {
      if (state.editingProjectId) {
        await api(`/api/projects/${encodeURIComponent(state.editingProjectId)}`, { method: "PUT", body: JSON.stringify(payload) });
        toast("项目记忆已更新，进度、风险和建议已重新计算。");
      } else {
        await api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
        toast("项目已创建，并设为当前项目。");
      }
      state.projectEditorOpen = false;
      state.editingProjectId = null;
      await load();
    } catch (err) {
      toast(err.message || "保存项目失败");
    }
    return;
  }
  if (event.target.id === "taskEditorForm") {
    event.preventDefault();
    const title = $("workTaskTitle")?.value.trim() || "";
    if (!title) return;
    const duration = $("workTaskDuration")?.value.trim() || "";
    const scheduledAt = storedDateTime($("workTaskSchedule")?.value || "");
    const payload = {
      title,
      description: $("workTaskDescription")?.value.trim() || "",
      project: $("workTaskProject")?.value.trim() || "",
      project_id: $("workTaskProjectId")?.value || "",
      scheduled_at: scheduledAt,
      deadline: storedDateTime($("workTaskDeadline")?.value || ""),
      priority: $("workTaskPriority")?.value || "medium",
      status: $("workTaskStatus")?.value || "todo",
      estimated_duration: duration ? `${duration}m` : "",
    };
    try {
      if (state.editingTaskId) {
        await api(`/api/work/tasks/${encodeURIComponent(state.editingTaskId)}`, { method: "PUT", body: JSON.stringify(payload) });
        toast("任务安排已更新，相关提醒也已重新同步。");
      } else {
        await api("/api/work/tasks", { method: "POST", body: JSON.stringify({ ...payload, source_type: "manual" }) });
        toast("任务已加入工作日程。");
      }
      if (scheduledAt) state.workDate = localDateKey(scheduledAt);
      state.workView = "day";
      state.taskEditorOpen = false;
      state.editingTaskId = null;
      state.pendingTaskProject = null;
      await load();
    } catch (err) {
      toast(err.message || "保存任务失败");
    }
    return;
  }
  if (event.target.id !== "chatForm") return;
  event.preventDefault();
  const input = $("chatInput");
  const message = input?.value.trim() || "";
  if (!message || state.chatBusy) return;
  state.chatBusy = true;
  state.chatMessages = [...state.chatMessages, { role: "user", content: message, metadata: {} }];
  render();
  try {
    const out = await api("/api/chat", { method: "POST", body: JSON.stringify({
      message,
      session_id: state.activeSessionId,
    }) });
    state.activeSessionId = out.session_id;
    if (out.intent === "create_task" || out.intent === "breakdown_task" || out.intent === "update_task" || out.intent === "create_reminder" || out.intent === "generate_report" || out.intent === "query_project") {
      state.dash = await api("/api/dashboard");
    }
    await loadChatState(false);
  } catch (err) {
    toast(err.message || "对话失败，请稍后重试。");
  } finally {
    state.chatBusy = false;
    render();
    requestAnimationFrame(() => {
      const box = $("chatMessages");
      if (box) box.scrollTop = box.scrollHeight;
      $("chatInput")?.focus();
    });
  }
});

document.addEventListener("keydown", (event) => {
  if (event.target.id === "chatInput" && event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    event.target.form?.requestSubmit();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    $("searchInput").focus();
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("#typeChips .chip")) {
    event.target.closest(".chip").classList.toggle("is-on");
  }
});

window.addEventListener("hashchange", async () => {
  syncRouteState();
  state.route = currentRoute();
  if (state.route === "/chat") await loadChatState(true);
  render();
});

$("authSwitch")?.addEventListener("click", () => setAuthMode(!state.registerMode));
$("authForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = $("authError");
  error.hidden = true;
  const username = $("authUser").value.trim();
  const password = $("authPass").value;
  const display_name = $("regName").value.trim();
  try {
    const path = state.registerMode ? "/api/auth/register" : "/api/auth/login";
    const session = await api(path, {
      method: "POST",
      body: JSON.stringify({ username, password, display_name }),
    });
    await enterSession(session);
    toast(state.registerMode ? "账号已创建。" : `欢迎回来，${session.user.display_name || session.user.username}`);
  } catch (err) {
    error.textContent = err.message || "登录失败";
    error.hidden = false;
  }
});

syncRouteState();
state.route = currentRoute();
boot();
