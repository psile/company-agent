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
};

const ROUTES = [
  { id: "home", href: "#/", label: "首页", icon: "home" },
  { id: "chat", href: "#/chat", label: "秘书对话", icon: "chat" },
  { id: "recommend", href: "#/recommend", label: "为你推荐", icon: "star" },
  { id: "follows", href: "#/follows", label: "我的关注", icon: "heart" },
  { id: "goals", href: "#/goals", label: "目标管理", icon: "target" },
  { id: "knowledge", href: "#/knowledge", label: "知识库", icon: "book" },
  { id: "toolbox", href: "#/toolbox", label: "工具箱", icon: "box" },
];
const SETTINGS_ITEMS = [
  { href: "#/settings/profile", label: "个人信息" },
  { href: "#/settings/security", label: "账号与安全" },
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
  recTab: "work",
  recFilter: "all",
  recSort: "score",
  knowledgeCat: "全部",
  selectedCard: null,
  query: "",
  followKind: "topic",
  chatSessions: [],
  activeSessionId: null,
  chatMessages: [],
  conversationProfile: null,
  chatBusy: false,
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
  return `
    <article class="item" data-id="${escapeHtml(item.id)}">
      <div class="item-top">
        <div>
          <div class="tiny">${escapeHtml(item.source_name || "")} · ${escapeHtml(fmtTime(item.published_at))}</div>
          <h3>${escapeHtml(item.title)}</h3>
        </div>
        <div class="rel">
          <b>${score}%</b>
          <div class="tiny">${relLabel(score)}</div>
          <div class="meter"><span style="width:${score}%"></span></div>
        </div>
      </div>
      <p class="muted" style="margin:0">${escapeHtml(item.summary_zh || item.summary || "")}</p>
      <div class="tags">${tagsHtml(item.tags)}${score >= 85 ? '<span class="tag green">高相关</span>' : ""}</div>
      ${item.why_you ? `<p class="why"><strong>为什么推荐给你</strong>${escapeHtml(item.why_you)}</p>` : ""}
      ${item.project_value ? `<p class="proj"><strong>与你当前项目的关系</strong>${escapeHtml(item.project_value)}</p>` : ""}
      <div class="row-actions">
        <button class="btn-ghost" data-open="${escapeHtml(item.id)}" type="button">查看原文</button>
        <button class="btn-ghost" data-act="useful" data-id="${escapeHtml(item.id)}" type="button">有用</button>
        <button class="btn-ghost" data-act="collect" data-id="${escapeHtml(item.id)}" type="button">收藏</button>
        <button class="btn-ghost" data-act="dislike" data-id="${escapeHtml(item.id)}" type="button">减少此类推荐</button>
      </div>
    </article>`;
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
  $("engineCard").innerHTML = `
    <div class="engine-head"><span>记忆引擎状态</span><span class="okdot">● 正常</span></div>
    <p>已处理信息 <b>${total.toLocaleString()}</b> 条</p>
    <div class="bar"><span style="width:${Math.min(100, 18 + (total % 80))}%"></span></div>
    <p>今日新增 ${fetched} 条</p>`;
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
          <button type="button" data-chat-example="最近帮我关注 Agent Memory、Mem0 和 MemOS，有重要论文再告诉我。">建立关注</button>
          <button type="button" data-chat-example="最近 Agent Memory 有什么值得看的？">查询推荐</button>
          <button type="button" data-chat-example="我最近主要在做个人 AI 秘书和 Agent Memory。">记住我的工作</button>
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
        <div class="chat-messages" id="chatMessages">${messageHtml}${state.chatBusy ? '<div class="chat-message is-agent"><div class="chat-role">秘书 Agent</div><div class="chat-bubble is-thinking">正在理解并调用工具…</div></div>' : ""}</div>
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

function pageHome() {
  const dash = state.dash;
  const observe = dash.observe || {};
  const stats = dash.stats || {};
  const items = (dash.for_you || []).filter(matchQuery).slice(0, 5);
  const goals = dash.goals || [];
  const today = goals.find((g) => g.kind === "today") || goals[0];
  const week = goals.find((g) => g.kind === "week");
  const quarter = goals.find((g) => g.kind === "quarter");
  const interests = (dash.interests || []).slice(0, 6);
  return `
    <div class="page-head">
      <div>
        <h1>${greeting()}，今天我替你关注了 ${observe.fetched || 0} 条信息，为你筛选出 ${dash.for_you?.length || 0} 条真正值得关注的内容。</h1>
        <p>Agent 在后台持续观察世界，再按你的项目、目标和兴趣决定推什么。</p>
      </div>
      <div class="actions">
        <button class="btn" id="refreshBtn" type="button">刷新源</button>
        <a class="btn-ghost" href="#/recommend">查看全部推荐</a>
      </div>
    </div>
    <div class="stats">
      ${stat("工作推荐", stats.work, "+工作上下文")}
      ${stat("个人推荐", stats.personal, "长期兴趣")}
      ${stat("新增知识", stats.knowledge, "点赞/收藏沉淀")}
      ${stat("待处理反馈", stats.pending_feedback, "让它更懂你")}
    </div>
    <div class="layout">
      <section class="stack">
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

function stat(label, value, hint) {
  return `<section class="card stat"><span>${escapeHtml(label)}</span><b>${value || 0}</b><span class="up">${escapeHtml(hint)}</span></section>`;
}

function goalMini(label, goal) {
  if (!goal) return `<p class="tiny">${escapeHtml(label)} · 未设置</p>`;
  return `<div class="goal"><div class="tiny">${escapeHtml(label)}</div><b>${escapeHtml(goal.title)}</b><div class="barline"><span style="width:${goal.progress || 0}%"></span></div></div>`;
}

function emptyFeed() {
  return `<div class="empty">还没有筛出内容。点「刷新源」，Agent 会走采集 → 理解 → 记忆匹配 → 为你排序。</div>`;
}

function pageRecommend() {
  const dash = state.dash;
  const pool = state.recTab === "work" ? dash.work || [] : dash.personal || [];
  let items = pool.filter(matchQuery);
  if (state.recFilter === "high") items = items.filter((row) => Number(row.score || 0) >= 85);
  if (state.recFilter === "paper") items = items.filter((row) => sourceKind(row) === "paper");
  if (state.recFilter === "github") items = items.filter((row) => sourceKind(row) === "github");
  if (state.recFilter === "blog") items = items.filter((row) => sourceKind(row) === "blog");
  if (state.recFilter === "news") items = items.filter((row) => sourceKind(row) === "news");
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
        <h1>为你推荐</h1>
        <p>基于你的兴趣、当前项目、目标和行为，为你筛选真正值得关注的内容。</p>
      </div>
    </div>
    <div class="tabs">
      <button class="tab${state.recTab === "work" ? " is-on" : ""}" data-rectab="work" type="button">工作推荐</button>
      <button class="tab${state.recTab === "personal" ? " is-on" : ""}" data-rectab="personal" type="button">个人推荐</button>
    </div>
    <div class="chips" style="margin:12px 0">
      ${[["all","全部"],["high","高相关"],["paper","论文"],["github","GitHub"],["blog","Blog"],["product","产品动态"],["news","新闻"]].map(([id,label]) => `<button class="chip${state.recFilter===id?" is-on":""}" data-filter="${id}" type="button">${label}</button>`).join("")}
      <select data-sort>
        <option value="score"${state.recSort==="score"?" selected":""}>排序：相关度</option>
        <option value="new"${state.recSort==="new"?" selected":""}>排序：最新</option>
      </select>
    </div>
    <div class="layout">
      <div class="stack">${items.length ? items.map(recCard).join("") : emptyFeed()}</div>
      <aside class="stack">
        <section class="card">
          <h3>推荐偏好</h3>
          <p>兴趣领域：${(dash.interests || []).slice(0,4).map((r)=>r.topic).join("、") || "—"}</p>
          <p>内容来源：Blog / GitHub / 论文</p>
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
      <p class="tiny">指定网站、RSS 或官方 Blog，Agent 会在后台持续采集。</p>
      <div class="field"><label>信息源名称</label><input id="sourceName" placeholder="OpenAI Blog" /></div>
      <div class="field"><label>链接或 RSS</label><input id="sourceUrl" placeholder="https://" /></div>
      <div class="field"><label>类型</label><select id="sourceType"><option value="blog">官方 Blog</option><option value="paper">学术论文</option><option value="news">行业新闻</option><option value="release">代码仓库</option></select></div>
      <button class="btn" id="addSourceBtn" type="button">加入观察源</button>
      <p class="hint">当前 Demo 的采集清单仍以 sources.json 为准，这里会先记入关注，后续接入自定义源。</p>`;
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

function pageFollows() {
  const dash = state.dash;
  const interests = dash.interests || [];
  const products = dash.products || [];
  const sources = dash.sources || [];
  const typeMap = { paper: "学术论文", release: "代码发布", blog: "官方 Blog", news: "行业新闻", arxiv: "学术论文" };
  return `
    <div class="page-head">
      <div>
        <h1>我的关注</h1>
        <p>告诉 Agent 你希望持续关注什么，它会替你观察世界。</p>
      </div>
      <button class="btn" data-scroll="addFollow" type="button">+ 新增关注</button>
    </div>
    <div class="layout">
      <div class="stack">
        <section class="card">
          <h2>主题关注</h2>
          <div class="grid-cards">${interests.map((row) => `<div class="mini"><span class="tag">主题</span><b>${escapeHtml(row.topic)}</b>${dots(row.weight)}<div class="tiny">权重 ${Number(row.weight||0).toFixed(2)}</div></div>`).join("")}</div>
        </section>
        <section class="card">
          <h2>产品 / 项目关注</h2>
          <div class="grid-cards">${products.map((row) => `<div class="mini"><b>${escapeHtml(row.name)}</b><div class="tiny">${escapeHtml(row.status || "持续跟踪")}</div><span class="tag green">${row.running === false ? "暂停" : "运行中"}</span></div>`).join("")}</div>
        </section>
        <section class="card">
          <h2>信息源关注</h2>
          <table class="table">
            <thead><tr><th>信息源</th><th>类型</th><th>关注内容</th><th>频率</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>${sources.map((src) => `<tr><td>${escapeHtml(src.name)}</td><td>${escapeHtml(typeMap[src.type] || src.type || src.kind)}</td><td>${escapeHtml(src.search || src.repo || src.url || "—")}</td><td>${src.kind==="arxiv"?"实时":"每日"}</td><td><span class="tag green">运行中</span></td><td class="tiny">暂停 · 编辑 · 删除</td></tr>`).join("")}</tbody>
          </table>
        </section>
        <section class="card">
          <h2>近期重点关注</h2>
          <p>由当前目标 / 项目自动生成：本周重点关注 ${(interests.slice(0,3).map((r)=>r.topic).join("、")) || "你的核心主题"}。</p>
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

function pageGoals() {
  const goals = state.dash.goals || [];
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
        <p>将今日、短期和长期目标纳入 Agent 决策，让推荐真正服务当前任务。</p>
      </div>
    </div>
    <div class="layout">
      <div class="stack">${groups.map(([kind, title]) => {
        const rows = goals.filter((g) => g.kind === kind);
        const done = rows.filter((g) => g.done).length;
        return `<section class="card"><div class="page-head" style="margin:0 0 10px"><h2 style="margin:0">${title}</h2><span class="tiny">${done}/${rows.length || 0}</span></div>${
          rows.map((g) => `<div class="item"><div class="item-top"><b>${escapeHtml(g.title)}</b><span class="tag ${g.priority==="high"?"orange":"gray"}">${pri[g.priority]||"中优先级"}</span></div><div class="barline"><span style="width:${g.progress||0}%"></span></div><div class="tiny">进度 ${g.progress||0}% · 已关联推荐 ${g.linked||0} 条 · 对推荐影响：${g.priority==="high"?"高相关":"中相关"}</div></div>`).join("") || "<p class='tiny'>还没有这类目标。</p>"
        }</section>`;
      }).join("")}
        <section class="card">
          <h2>新增目标</h2>
          <div class="field"><label>名称</label><input id="goalTitle" placeholder="本周完成个性化推荐 Demo" /></div>
          <div class="field"><label>类型</label><select id="goalKind"><option value="today">今日</option><option value="week" selected>短期</option><option value="quarter">长期</option><option value="open">不定期</option></select></div>
          <button class="btn" id="addGoalBtn" type="button">加入 Agent 决策</button>
        </section>
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
          <div class="coming"><span>待办关联</span><span class="tag">即将推出</span></div>
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

function pageToolbox() {
  const tools = ["日报生成","待办事项","日期计算","习惯打卡","收藏管理","文章摘要","论文阅读"];
  return `
    <div class="page-head">
      <div>
        <h1>工具箱</h1>
        <p>当前 Demo 重点是 Recommendation Skill。这些入口为未来 Skills 预留。</p>
      </div>
    </div>
    <div class="grid-cards">${tools.map((name) => `<div class="mini"><b>${name}</b><div class="tiny">Skill 即将接入</div><span class="tag">Coming soon</span></div>`).join("")}</div>
    <section class="card" style="margin-top:16px">
      <h3>Skill 架构预留</h3>
      <p>Personal Agent → Recommendation / Research / Planning / Daily Report / Feishu / Future Skills</p>
    </section>`;
}

function pageProfile() {
  const dash = state.dash;
  const profile = dash.profile || {};
  const interests = dash.interests || [];
  const push = dash.push_settings || {};
  const stats = dash.stats || {};
  const likes = (dash.cards || []).slice(0, 6);
  const ratio = Number(push.work_personal_ratio || 80);
  const types = ["技术文章","学术论文","GitHub","产品动态","行业资讯"];
  const selectedTypes = push.content_types || ["技术文章","行业资讯"];
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
          <select id="summaryLen">${["简洁","中等","详细"].map((x)=>`<option${(push.summary_length||"中等")===x?" selected":""}>${x}</option>`).join("")}</select>
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

function pageSettingsPrefs() {
  const dash = state.dash;
  const push = dash.push_settings || {};
  const ratio = Number(push.work_personal_ratio || 80);
  const types = ["技术文章","学术论文","GitHub","产品动态","行业资讯"];
  const selectedTypes = push.content_types || ["技术文章","行业资讯"];
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
        <select id="summaryLen">${["简洁","中等","详细"].map((x)=>`<option${(push.summary_length||"中等")===x?" selected":""}>${x}</option>`).join("")}</select>
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

const PAGES = {
  "/": pageHome,
  "/chat": pageChat,
  "/recommend": pageRecommend,
  "/follows": pageFollows,
  "/goals": pageGoals,
  "/knowledge": pageKnowledge,
  "/toolbox": pageToolbox,
  "/profile": pageProfile,
  "/settings": pageSettingsPush,
  "/settings/push": pageSettingsPush,
  "/settings/profile": pageSettingsProfile,
  "/settings/security": pageSettingsSecurity,
  "/settings/prefs": pageSettingsPrefs,
  "/settings/privacy": pageSettingsPrivacy,
  "/settings/members": pageSettingsMembers,
};

function currentRoute() {
  const hash = location.hash.replace("#", "") || "/";
  if (hash === "/settings") return "/settings/push";
  return PAGES[hash] ? hash : "/";
}

function render() {
  if ((location.hash.replace("#", "") || "/") === "/settings") {
    location.hash = "#/settings/push";
    return;
  }
  state.route = currentRoute();
  renderChrome();
  if (!state.dash) {
    $("page").innerHTML = `<div class="empty">正在连接记忆引擎…</div>`;
    return;
  }
  const view = PAGES[state.route] || pageHome;
  $("page").innerHTML = view();
}

async function load() {
  state.dash = await api("/api/dashboard");
  state.userId = state.dash.current_user || state.userId;
  if (state.route === "/chat" && !state.chatSessions.length) await loadChatState(true);
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
  const t = event.target.closest("[data-act],[data-open],[data-rectab],[data-filter],[data-cat],[data-card],[data-topic],[data-example],[data-toggle],[data-move],[data-followkind],[data-chat-session],[data-chat-example],#newChatBtn,#saveConversationProfileBtn,#refreshBtn,#refreshBtn2,#followBtn,#addGoalBtn,#savePrefBtn,#savePushBtn,#pushNowBtn,#briefBtn,#noticeBtn,#saveProfileBtn,#exportBtn,#addProductBtn,#addSourceBtn,#addFollowGoalBtn,#logoutBtn,#savePassBtn,#saveFeishuBtn");
  if (!t) return;
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
  if (t.id === "logoutBtn") {
    await api("/api/auth/logout", { method: "POST", body: "{}" }).catch(() => {});
    state.token = "";
    localStorage.removeItem("radar_session");
    showAuth();
    setAuthMode(false);
    toast("已退出");
    return;
  }
  if (t.id === "refreshBtn" || t.id === "refreshBtn2" || t.id === "briefBtn") return refreshFeeds(t);
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
  if (t.id === "addGoalBtn") {
    const title = $("goalTitle").value.trim();
    if (!title) return toast("请填写目标名称");
    const items = [...(state.dash.goals || []), { id: `g-${Date.now()}`, kind: $("goalKind").value, title, priority: "medium", progress: 0, linked: 0, done: false }];
    await api("/api/goals", { method: "PUT", body: JSON.stringify({ items }) });
    toast("目标已进入推荐上下文。");
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
    if (!name) return toast("请填写信息源名称");
    await api("/api/follows", { method: "POST", body: JSON.stringify({ topic: name, text: `关注信息源 ${name} ${$("sourceUrl").value}` }) });
    toast("已记下这个信息源。当前采集仍以订阅清单为准，自定义源会进入关注记忆。");
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

state.route = currentRoute();
boot();
