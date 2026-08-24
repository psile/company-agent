/**
 * 管理模块：AI 对话调优、知识库、嗅探关键词
 */
const ManagerModule = {
    init() {
        this.bindEvents();
        this.renderKnowledge();
        this.renderSniff();
        this.loadChatHistory();
    },

    bindEvents() {
        document.querySelectorAll(".manager-tab").forEach((tab) => {
            tab.addEventListener("click", () => {
                const mtab = tab.dataset.mtab;
                document.querySelectorAll(".manager-tab").forEach((t) => t.classList.remove("active"));
                tab.classList.add("active");
                document.querySelectorAll(".mtab-panel").forEach((p) => {
                    p.classList.toggle("active", p.id === `mtab-${mtab}`);
                });
            });
        });

        document.getElementById("btn-chat-send").addEventListener("click", () => this.sendChat());
        document.getElementById("chat-input").addEventListener("keydown", (e) => {
            if (e.key === "Enter") this.sendChat();
        });

        document.getElementById("btn-add-sniff").addEventListener("click", () => this.addSniff());
        document.getElementById("sniff-input").addEventListener("keydown", (e) => {
            if (e.key === "Enter") this.addSniff();
        });
    },

    // ====== AI 对话 ======
    async sendChat() {
        const input = document.getElementById("chat-input");
        const text = input.value.trim();
        if (!text) return;

        input.value = "";
        this.appendMsg("user", text);

        const history = Store.getChatHistory();
        history.push({ role: "user", content: text });

        const systemPrompt = this.buildSystemPrompt();
        this.showTyping();

        try {
            const messages = [
                { role: "system", content: systemPrompt },
                ...history.slice(-10).map((m) => ({
                    role: m.role === "ai" ? "assistant" : "user",
                    content: m.content,
                })),
            ];

            const reply = await LLM.chat(messages, { temperature: 0.6, maxTokens: 1500 });
            this.hideTyping();
            this.appendMsg("ai", reply);
            history.push({ role: "ai", content: reply });
            Store.saveChatHistory(history);
            this.maybeUpdateKnowledge(text);
        } catch (e) {
            this.hideTyping();
            this.appendMsg("ai", "出错了: " + e.message);
        }
    },

    buildSystemPrompt() {
        const targets = Store.getTargets().filter((t) => !t.done);
        const sniff = Store.getSniffKeywords();
        const knowledge = Store.getKnowledge();
        const habits = Store.getHabits();
        const todos = Store.getTodos().filter((t) => !t.done);

        let ctx = "你是 RadarME 的推荐管理助手，帮用户精调推荐流和管理计划。\n\n用户状态：\n";
        if (targets.length)
            ctx += "目标：\n" + targets.map((t) => `- [${t.type}] ${t.text}`).join("\n") + "\n";
        if (habits.length)
            ctx += `习惯：${habits.map((h) => h.name).join("、")}\n`;
        if (todos.length)
            ctx += `待办：${todos.slice(0, 5).map((t) => t.text).join("、")}\n`;
        if (sniff.length)
            ctx += `嗅探关键词：${sniff.join("、")}\n`;
        if (knowledge.length)
            ctx += "知识库：\n" + knowledge.map((k) => `- ${k.topic}：${k.level}`).join("\n") + "\n";
        ctx += "\n用中文简洁回复。";
        return ctx;
    },

    appendMsg(role, text) {
        const container = document.getElementById("chat-messages");
        const div = document.createElement("div");
        div.className = `chat-msg ${role === "user" ? "user" : "ai"}`;
        div.innerHTML = `<div class="msg-bubble">${escapeHTML(text)}</div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    },

    showTyping() {
        const container = document.getElementById("chat-messages");
        const div = document.createElement("div");
        div.className = "chat-msg ai";
        div.id = "typing-indicator";
        div.innerHTML = `<div class="msg-bubble chat-typing"><span></span><span></span><span></span></div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    },

    hideTyping() {
        document.getElementById("typing-indicator")?.remove();
    },

    loadChatHistory() {
        const history = Store.getChatHistory();
        history.forEach((m) => this.appendMsg(m.role === "ai" ? "ai" : "user", m.content));
    },

    /** 从对话中试探性更新知识库 */
    maybeUpdateKnowledge(userText) {
        const match = userText.match(/(?:我对|我在学|我最近在|我想学|关注)([^，。！？\s]{2,10})/);
        if (match) {
            const topic = match[1];
            const knowledge = Store.getKnowledge();
            if (!knowledge.find((k) => k.topic === topic)) {
                knowledge.push({ topic, level: "beginner", articles: 0, score: 10 });
                Store.saveKnowledge(knowledge);
                this.renderKnowledge();
            }
        }
    },

    // ====== 知识库 ======
    renderKnowledge() {
        const knowledge = Store.getKnowledge();
        const grid = document.getElementById("knowledge-grid");

        if (!knowledge.length) {
            grid.innerHTML = `<div class="kc-empty">知识库为空。在对话中表达兴趣，知识图谱会自动生长。</div>`;
            return;
        }

        const levelMap = {
            beginner: { label: "入门", pct: 25 },
            intermediate: { label: "进阶", pct: 55 },
            advanced: { label: "高级", pct: 80 },
            master: { label: "精通", pct: 100 },
        };

        grid.innerHTML = knowledge.map((k) => {
            const lv = levelMap[k.level] || levelMap.beginner;
            return `
            <div class="knowledge-card">
                <div class="kc-topic">${escapeHTML(k.topic)}</div>
                <div class="kc-level-bar"><div class="kc-level-fill" style="width:${lv.pct}%"></div></div>
                <div class="kc-level-text">
                    <span class="level-label">${lv.label}</span>
                    <span>${k.articles || 0} 篇</span>
                </div>
            </div>`;
        }).join("");
    },

    // ====== 嗅探关键词 ======
    renderSniff() {
        const keywords = Store.getSniffKeywords();
        const cloud = document.getElementById("sniff-cloud");

        if (!keywords.length) {
            cloud.innerHTML = `<div class="sniff-empty">没有追踪关键词。添加一些让雷达持续扫描。</div>`;
            return;
        }

        cloud.innerHTML = keywords.map((kw) => `
            <span class="sniff-tag tracked">
                ${escapeHTML(kw)}
                <button class="tag-remove" data-kw="${escapeHTML(kw)}">&times;</button>
            </span>
        `).join("");

        // 事件委托 —— 按 kw 值删除，修复 index 错位
        cloud.querySelectorAll(".tag-remove").forEach((btn) => {
            btn.addEventListener("click", () => this.removeSniff(btn.dataset.kw));
        });
    },

    addSniff() {
        const input = document.getElementById("sniff-input");
        const val = input.value.trim();
        if (!val) return;
        const keywords = Store.getSniffKeywords();
        if (keywords.includes(val)) {
            Toast.show("该关键词已存在");
            return;
        }
        keywords.push(val);
        Store.saveSniffKeywords(keywords);
        input.value = "";
        this.renderSniff();
        this.syncWorkKeywords(keywords);
        Toast.show("关键词已添加");
    },

    /** 按值删除，不再依赖 index */
    removeSniff(kw) {
        let keywords = Store.getSniffKeywords();
        keywords = keywords.filter((k) => k !== kw);
        Store.saveSniffKeywords(keywords);
        this.renderSniff();
        this.syncWorkKeywords(keywords);
        Toast.show("关键词已移除");
    },

    async syncWorkKeywords(keywords) {
        try {
            const profile = await fetch(apiUrl("/api/profile")).then((r) => r.json());
            profile.work_keywords = keywords;
            await fetch(apiUrl("/api/profile"), {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(profile),
            });
        } catch (_) { /* 服务未启动则只留在本地嗅探词 */ }
    },
};
