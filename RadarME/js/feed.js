/**
 * 推荐流：从 radar 服务拉真源（工作=信息找人，个人=休闲推荐）。
 */
const FeedModule = {
    _generating: false,
    _timerId: null,
    _startTime: 0,

    init() {
        this.bindEvents();
        this.tryRenderCache();
        this.loadFromServer();
    },

    bindEvents() {
        document.querySelectorAll(".feed-tab").forEach((tab) => {
            tab.addEventListener("click", () => {
                const feed = tab.dataset.feed;
                document.querySelectorAll(".feed-tab").forEach((t) => {
                    t.classList.toggle("active", t === tab);
                });
                document.querySelectorAll(".feed-stream").forEach((s) => {
                    s.classList.toggle("active", s.id === `${feed}-feed`);
                });
            });
        });

        document.getElementById("btn-refresh-feed").addEventListener("click", () => {
            const activeTab = document.querySelector(".feed-tab.active").dataset.feed;
            this.generate(activeTab);
        });
        const pushBtn = document.getElementById("btn-push-feishu");
        if (pushBtn) {
            pushBtn.addEventListener("click", () => this.pushFeishu());
        }
    },

    async loadFromServer() {
        try {
            const [work, personal] = await Promise.all([
                fetch(apiUrl("/api/feeds/work")).then((r) => r.json()),
                fetch(apiUrl("/api/feeds/personal")).then((r) => r.json()),
            ]);
            if (work.items && work.items.length) {
                Store.saveWorkFeed(work.items);
                this.render("work", work.items);
            }
            if (personal.items && personal.items.length) {
                Store.savePersonalFeed(personal.items);
                this.render("personal", personal.items);
            }
        } catch (_) {
            /* 服务未启动时沿用本地缓存 */
        }
    },

    tryRenderCache() {
        const work = Store.getWorkFeed();
        if (work && work.length) {
            this.render("work", work);
        } else {
            this.renderEmpty("work");
        }
        const personal = Store.getPersonalFeed();
        if (personal && personal.length) {
            this.render("personal", personal);
        } else {
            this.renderEmpty("personal");
        }
    },

    /** 从公开源拉取并按通道打分 */
    async generate(feedType) {
        if (this._generating) return;
        this._generating = true;

        const container = document.getElementById(`${feedType}-feed`);
        this._startTime = Date.now();
        this.showStreamingProgress(container);
        const status = container.querySelector(".stream-status span");
        if (status) status.textContent = "正在拉取 ArXiv / GitHub / RSS";

        this._timerId = setInterval(() => {
            const elapsed = ((Date.now() - this._startTime) / 1000).toFixed(1);
            const timerEl = container.querySelector(".stream-timer");
            if (timerEl) timerEl.textContent = elapsed + "s";
        }, 100);

        const channel = feedType === "work" ? "work" : "personal";
        const signal = LLM.createAbortController();
        const cancelBtn = container.querySelector(".stream-cancel");
        if (cancelBtn) {
            cancelBtn.onclick = () => {
                LLM.abort();
                this.stopTimer();
                this._generating = false;
                const cache = feedType === "work" ? Store.getWorkFeed() : Store.getPersonalFeed();
                if (cache && cache.length) this.render(feedType, cache);
                else this.renderEmpty(feedType);
                Toast.show("已取消");
            };
        }

        try {
            const resp = await fetch(apiUrl(`/api/feeds/${channel}/refresh`), {
                method: "POST",
                signal,
            });
            const data = await resp.json();
            this.stopTimer();
            if (!resp.ok) throw new Error(data.error || "刷新失败");
            const items = data.items || [];
            if (feedType === "work") Store.saveWorkFeed(items);
            else Store.savePersonalFeed(items);
            this.render(feedType, items);
            const elapsed = ((Date.now() - this._startTime) / 1000).toFixed(1);
            Toast.show(`真源 ${items.length} 条 · 抓取 ${data.fetched || "?"} · ${elapsed}s`);
        } catch (e) {
            this.stopTimer();
            if (e.name === "AbortError") return;
            console.error(e);
            this.showError(container, e.message || "无法连接 radar 服务，请先 python -m radar", feedType);
        } finally {
            this._generating = false;
        }
    },

    async pushFeishu() {
        try {
            const resp = await fetch(apiUrl("/api/push/feishu"), { method: "POST" });
            const data = await resp.json();
            if (data.ok) {
                Toast.show("已发到飞书");
                return;
            }
            if (data.text) {
                await navigator.clipboard.writeText(data.text).catch(() => {});
                Toast.show(data.reason === "FEISHU_WEBHOOK_URL not set" ? "未配 Webhook，已复制文案" : (data.reason || "未推送"));
                return;
            }
            Toast.show(data.reason || "推送失败");
        } catch (e) {
            Toast.show("推送失败：" + e.message);
        }
    },

    stopTimer() {
        if (this._timerId) {
            clearInterval(this._timerId);
            this._timerId = null;
        }
    },

    /**
     * 构建完整用户上下文：目标 + 习惯 + 待办 + 嗅探 + 知识库
     */
    buildFullContext() {
        const targets = Store.getTargets().filter((t) => !t.done);
        const habits = Store.getHabits();
        const todos = Store.getTodos().filter((t) => !t.done);
        const sniff = Store.getSniffKeywords();
        const knowledge = Store.getKnowledge();

        let ctx = "";

        if (targets.length) {
            ctx += "## 目标\n";
            targets.forEach((t) => {
                ctx += `- [${this.typeLabel(t.type)}] ${t.text}\n`;
            });
            ctx += "\n";
        }

        if (habits.length) {
            ctx += "## 习惯\n";
            habits.forEach((h) => {
                ctx += `- ${h.name}${h.desc ? `（${h.desc}）` : ""}\n`;
            });
            ctx += "\n";
        }

        if (todos.length) {
            ctx += "## 当前待办\n";
            todos.slice(0, 8).forEach((t) => {
                ctx += `- ${t.text}\n`;
            });
            ctx += "\n";
        }

        if (sniff.length) {
            ctx += `## 嗅探关键词\n${sniff.join("、")}\n\n`;
        }

        if (knowledge.length) {
            ctx += "## 已掌握知识\n";
            knowledge.forEach((k) => {
                ctx += `- ${k.topic}：${k.level}（${k.articles || 0}篇阅读）\n`;
            });
            ctx += "\n";
        }

        return ctx.trim() || "（暂无明确上下文，请基于通用 AI / 大模型 / 车载方向推荐）";
    },

    typeLabel(type) {
        return { today: "今日", short: "短期", long: "长期", casual: "不定期" }[type] || type;
    },

    /** 渲染推荐列表 */
    render(feedType, items) {
        const container = document.getElementById(`${feedType}-feed`);
        if (!items || !items.length) {
            this.renderEmpty(feedType);
            return;
        }

        const html = items.map((item, i) => `
            <article class="feed-item" data-id="${item.id}">
                <span class="feed-item-index">${String(i + 1).padStart(2, "0")}</span>
                <div class="feed-item-body">
                    <div class="feed-item-title">${escapeHTML(item.title)}</div>
                    <div class="feed-item-summary">${escapeHTML(item.summary || "")}</div>
                    <div class="feed-item-why">${escapeHTML(item.why || "")}</div>
                    <div class="feed-item-meta">
                        <span class="feed-item-score">相关度 ${escapeHTML(String(item.score ?? "—"))}%</span>
                        <span>${escapeHTML(item.source_name || "")}</span>
                        ${item.source_url ? `<a class="feed-item-link" href="${escapeHTML(item.source_url)}" target="_blank" rel="noopener">原文</a>` : ""}
                    </div>
                </div>
                <div class="feed-item-actions">
                    <button class="icon-btn" data-act="fav" data-id="${item.id}" data-feed="${feedType}">有用</button>
                    <button class="icon-btn" data-act="dismiss" data-id="${item.id}" data-feed="${feedType}">无用</button>
                </div>
            </article>
        `).join("");

        container.innerHTML = html;

        container.querySelectorAll(".icon-btn").forEach((btn) => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const act = btn.dataset.act;
                const id = btn.dataset.id;
                const feed = btn.dataset.feed;
                if (act === "fav") this.favorite(id, feed);
                else if (act === "dismiss") this.dismiss(id, feed);
            });
        });
    },

    renderEmpty(feedType) {
        const container = document.getElementById(`${feedType}-feed`);
        const label = feedType === "work" ? "工作推荐（信息找人）" : "个人推荐（休闲）";
        container.innerHTML = `
            <div class="feed-empty">
                <p>${label}还没有真源条目</p>
                <button class="btn-primary" data-gen="${feedType}">从公开源拉取</button>
            </div>`;
        const btn = container.querySelector('[data-gen]');
        if (btn) btn.addEventListener("click", () => this.generate(feedType));
    },

    /** 有用 → 带原链进库 */
    async favorite(id, feedType) {
        const cache = feedType === "work" ? Store.getWorkFeed() : Store.getPersonalFeed();
        const item = (cache || []).find((x) => x.id === id);
        if (!item) return;
        try {
            const resp = await fetch(apiUrl("/api/items/feedback"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id,
                    channel: feedType === "work" ? "work" : "personal",
                    action: "useful",
                }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || "入库失败");
        } catch (e) {
            Toast.show(e.message || "服务未启动，仅本地收藏");
        }
        const favs = Store.getFavorites();
        favs.unshift({
            title: item.title,
            summary: item.summary,
            source_url: item.source_url || "",
            savedAt: new Date().toISOString(),
        });
        Store.saveFavorites(favs);
        Toast.show("已记入个人库");
    },

    async dismiss(id, feedType) {
        try {
            await fetch(apiUrl("/api/items/feedback"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id,
                    channel: feedType === "work" ? "work" : "personal",
                    action: "dismiss",
                }),
            });
        } catch (_) { /* ignore */ }
        let cache = feedType === "work" ? Store.getWorkFeed() : Store.getPersonalFeed();
        cache = (cache || []).filter((x) => x.id !== id);
        if (feedType === "work") Store.saveWorkFeed(cache);
        else Store.savePersonalFeed(cache);
        this.render(feedType, cache);
        Toast.show("已去掉");
    },

    /** 流式生成进度 UI */
    showStreamingProgress(container) {
        container.innerHTML = `
            <div class="stream-progress">
                <div class="stream-header">
                    <div class="stream-status">
                        <div class="loading-spinner"></div>
                        <span>正在生成推荐</span>
                        <span class="stream-timer">0.0s</span>
                    </div>
                    <button class="btn-ghost btn-sm stream-cancel">取消</button>
                </div>
                <div class="stream-preview"></div>
            </div>`;
    },

    showError(container, msg, feedType) {
        container.innerHTML = `
            <div class="feed-empty">
                <p>生成失败：${escapeHTML(msg)}</p>
                <button class="btn-primary" id="retry-feed">重试</button>
            </div>`;
        const btn = container.querySelector("#retry-feed");
        if (btn) btn.addEventListener("click", () => this.generate(feedType));
    },
};
