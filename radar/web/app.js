const state = {
  tab: "intel",
  intel: [],
  for_you: [],
  seen: new Set(),
};

const $ = (id) => document.getElementById(id);

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
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

function tagsHtml(tags) {
  return (tags || [])
    .slice(0, 5)
    .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
    .join("");
}

function cardHtml(item, view) {
  const innov = (item.innovation || [])
    .slice(0, 3)
    .map((row) => `<li>${escapeHtml(row)}</li>`)
    .join("");
  const kicker = view === "intel" ? "世界在发生" : "为你发现";
  return `
    <article class="card ${view}" data-id="${item.id}">
      <div class="card-top">
        <span>${escapeHtml(kicker)} · ${escapeHtml(item.source_name)}</span>
        <span class="score">${item.score || 0}</span>
      </div>
      <div class="tags">${tagsHtml(item.tags)}</div>
      <h2><a href="${escapeHtml(item.source_url)}" data-open="${item.id}">${escapeHtml(item.title)}</a></h2>
      <p class="summary-line">${escapeHtml(item.summary_zh || item.summary || "")}</p>
      ${item.why_you ? `<p class="why"><strong>为什么推给你</strong> ${escapeHtml(item.why_you)}</p>` : ""}
      ${item.project_value ? `<p class="why"><strong>和当前项目</strong> ${escapeHtml(item.project_value)}</p>` : ""}
      ${innov ? `<ul class="points">${innov}</ul>` : ""}
      <div class="actions">
        <button class="btn ghost" data-open="${item.id}" type="button">原文</button>
        <button class="btn ghost" data-act="like" data-id="${item.id}" type="button">有用</button>
        <button class="btn ghost" data-act="collect" data-id="${item.id}" type="button">收藏</button>
        <button class="btn ghost" data-act="dislike" data-id="${item.id}" type="button">不相关</button>
      </div>
    </article>`;
}

function renderFeed() {
  const pane = $("feedPane");
  if (state.tab === "memory") {
    pane.innerHTML = `<div class="empty">记忆在右侧。情报看世界上发生了什么；为你看这件事此刻值不值得推给你。</div>`;
    return;
  }
  const items = state.tab === "intel" ? state.intel : state.for_you;
  if (!items.length) {
    pane.innerHTML = `<div class="empty">这一路还空着。点刷新源，会走采集 → 理解 → 记忆匹配。</div>`;
    return;
  }
  pane.innerHTML = items.map((item) => cardHtml(item, state.tab)).join("");
  observeCards();
}

async function loadAll() {
  const [intel, forYou, memory, health] = await Promise.all([
    api("/api/feeds/intel"),
    api("/api/feeds/for-you"),
    api("/api/memory"),
    api("/api/health"),
  ]);
  state.intel = intel.items || [];
  state.for_you = forYou.items || [];
  paintMemory(memory);
  const bits = [
    health.llm ? "模型已接" : "模型未接",
    health.feishu ? "飞书已配" : "飞书未配 webhook",
  ];
  $("statusLine").textContent = bits.join(" · ");
  renderFeed();
}

function paintMemory(memory) {
  const user = memory.user || {};
  const project = user.project || {};
  $("projectLine").textContent = project.project
    ? `${project.project} · ${project.stage || ""}`
    : "还没有当前项目";
  const interests = user.interests || [];
  $("interestChips").innerHTML = interests
    .slice(0, 10)
    .map((row) => `<span class="chip">${escapeHtml(row.topic)} ${Number(row.weight).toFixed(2)}</span>`)
    .join("") || `<span class="hint">还没有兴趣权重</span>`;
  const disliked = (user.behavior || {}).disliked_topics || [];
  $("dislikeChips").innerHTML = disliked
    .slice(0, 8)
    .map((row) => `<span class="chip">${escapeHtml(row)}</span>`)
    .join("") || `<span class="hint">还没有负反馈</span>`;
  const short = memory.short_term || [];
  $("shortMemory").innerHTML = short
    .slice()
    .reverse()
    .slice(0, 8)
    .map((row) => `<li>${escapeHtml(row.user_input || "")}</li>`)
    .join("") || "<li>还没有交互</li>";
}

async function refresh() {
  const btn = $("refreshBtn");
  btn.disabled = true;
  btn.textContent = "理解中";
  try {
    const result = await api("/api/refresh", { method: "POST", body: "{}" });
    state.intel = result.intel || result.work || [];
    state.for_you = result.for_you || result.personal || [];
    renderFeed();
    const pushed = result.pushed || [];
    if (pushed.length) {
      $("pushPanel").hidden = false;
      $("pushLog").innerHTML = pushed
        .map((row) => {
          const ok = row.ok ? "已推飞书" : row.reason === "FEISHU_WEBHOOK_URL not set" ? "文案已备好" : row.reason;
          const tags = (row.tags || []).join(" · ");
          return `<li>${escapeHtml(row.title)} · ${escapeHtml(tags)} · ${escapeHtml(ok)}</li>`;
        })
        .join("");
      toast(pushed[0].ok ? "已按当前兴趣推到飞书" : "已写好中文总结和标签，飞书 webhook 未配");
    } else {
      toast(`拉到 ${result.fetched || 0} 条 · 情报 ${state.intel.length} · 为你 ${state.for_you.length}`);
    }
    paintMemory(await api("/api/memory"));
  } catch (err) {
    toast(err.message || "刷新失败");
  } finally {
    btn.disabled = false;
    btn.textContent = "刷新源";
  }
}

async function track(id, action, extra = {}) {
  await api("/api/events", {
    method: "POST",
    body: JSON.stringify({ id, action, ...extra }),
  });
  paintMemory(await api("/api/memory"));
  if (action === "dislike" || action === "skip") {
    state.for_you = state.for_you.filter((row) => row.id !== id);
    if (action === "dislike") renderFeed();
    else renderFeed();
  }
}

function observeCards() {
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const id = entry.target.getAttribute("data-id");
        if (!id || state.seen.has(id)) return;
        state.seen.add(id);
        setTimeout(() => {
          const still = document.querySelector(`[data-id="${id}"]`);
          if (still) track(id, "dwell", { dwell_ms: 8000 }).catch(() => {});
        }, 8000);
      });
    },
    { threshold: 0.7 }
  );
  document.querySelectorAll(".card").forEach((el) => io.observe(el));
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.tab = btn.dataset.tab;
    document.querySelectorAll(".tab").forEach((el) => el.classList.toggle("is-on", el === btn));
    renderFeed();
  });
});

$("refreshBtn").addEventListener("click", refresh);

$("feedPane").addEventListener("click", async (ev) => {
  const open = ev.target.closest("[data-open]");
  const act = ev.target.closest("[data-act]");
  try {
    if (open) {
      const id = open.getAttribute("data-open");
      const item = [...state.intel, ...state.for_you].find((row) => row.id === id);
      await track(id, "open");
      if (item?.source_url) window.open(item.source_url, "_blank", "noopener");
      return;
    }
    if (act) {
      const action = act.getAttribute("data-act");
      await track(act.getAttribute("data-id"), action);
      toast({ like: "已记进兴趣和个人库", collect: "已收藏，权重加得更多", dislike: "已记成不相关" }[action] || "已记下");
    }
  } catch (err) {
    toast(err.message || "记录失败");
  }
});

loadAll().catch((err) => {
  $("statusLine").textContent = "服务未接通";
  toast(err.message || "无法加载");
});
