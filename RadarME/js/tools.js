/**
 * 工具模块：打卡计算、日报/周报、习惯、收藏、待办
 */
const ToolsModule = {
    init() {
        this.bindEvents();
    },

    bindEvents() {
        document.querySelectorAll(".tool-entry").forEach((card) => {
            card.addEventListener("click", () => {
                this.openTool(card.dataset.tool);
            });
        });
        document.getElementById("btn-close-panel").addEventListener("click", () => {
            this.closePanel();
        });
    },

    openTool(tool) {
        const panel = document.getElementById("tool-panel");
        const content = document.getElementById("tool-panel-content");
        panel.style.display = "block";

        const renderers = {
            clock: () => this.renderClock(),
            report: () => this.renderReport(),
            habit: () => this.renderHabit(),
            favorites: () => this.renderFavorites(),
            todo: () => this.renderTodo(),
        };

        content.innerHTML = renderers[tool] ? renderers[tool]() : "<p>未知工具</p>";

        const binders = {
            clock: () => this.bindClock(),
            report: () => this.bindReport(),
            habit: () => this.bindHabit(),
            favorites: () => {},
            todo: () => this.bindTodo(),
        };
        if (binders[tool]) binders[tool]();

        panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    },

    closePanel() {
        document.getElementById("tool-panel").style.display = "none";
    },

    // ====== 打卡计算 ======
    renderClock() {
        const now = new Date();
        const timeStr = now.toTimeString().slice(0, 5);
        return `
        <h2>打卡计算</h2>
        <p class="hint">输入上下班时间，自动计算工时与建议下班时间。</p>
        <div class="clock-tool">
            <div class="clock-row">
                <div class="clock-field">
                    <label>上班</label>
                    <input type="time" id="clock-in" value="09:00">
                </div>
                <div class="clock-field">
                    <label>下班</label>
                    <input type="time" id="clock-out" value="${timeStr}">
                </div>
                <div class="clock-field">
                    <label>午休(分)</label>
                    <input type="number" id="clock-lunch" value="60" min="0" max="180" style="width:100px">
                </div>
            </div>
            <button class="btn-primary" id="btn-clock-calc">计算</button>
            <div class="clock-result" id="clock-result" style="display:none;"></div>
        </div>`;
    },

    bindClock() {
        document.getElementById("btn-clock-calc").addEventListener("click", () => {
            const inTime = document.getElementById("clock-in").value;
            const outTime = document.getElementById("clock-out").value;
            const lunch = parseInt(document.getElementById("clock-lunch").value) || 0;
            if (!inTime || !outTime) return;

            const [inH, inM] = inTime.split(":").map(Number);
            const [outH, outM] = outTime.split(":").map(Number);
            let totalMin = (outH * 60 + outM) - (inH * 60 + inM) - lunch;
            if (totalMin < 0) totalMin += 24 * 60;

            const hours = Math.floor(totalMin / 60);
            const mins = totalMin % 60;
            const totalHours = (totalMin / 60).toFixed(1);

            const overtime = totalMin - 8 * 60;
            let otText, otClass;
            if (overtime > 0) {
                otText = `+${Math.floor(overtime / 60)}h ${overtime % 60}m`;
                otClass = "warning";
            } else if (overtime < 0) {
                otText = `差 ${Math.abs(overtime)} 分钟`;
                otClass = "warning";
            } else {
                otText = "刚好 8 小时";
                otClass = "ok";
            }

            const suggestOut = inH * 60 + inM + 8 * 60 + lunch;
            const sH = Math.floor(suggestOut / 60) % 24;
            const sM = suggestOut % 60;
            const suggestStr = `${String(sH).padStart(2, "0")}:${String(sM).padStart(2, "0")}`;

            const result = document.getElementById("clock-result");
            result.style.display = "block";
            result.innerHTML = `
                <div class="clock-result-row">
                    <span class="label">实际工时</span>
                    <span class="value accent">${hours}h ${mins}m (${totalHours}h)</span>
                </div>
                <div class="clock-result-row">
                    <span class="label">与 8 小时标准</span>
                    <span class="value ${otClass}">${otText}</span>
                </div>
                <div class="clock-result-row">
                    <span class="label">建议下班时间</span>
                    <span class="value">${suggestStr}</span>
                </div>
            `;
        });
        document.getElementById("btn-clock-calc").click();
    },

    // ====== 日报/周报 ======
    renderReport() {
        return `
        <h2>日报 / 周报</h2>
        <p class="hint">输入要点，AI 生成规范汇报。</p>
        <div class="report-tool">
            <div class="report-type-tabs">
                <button class="report-type-tab active" data-rtype="daily">日报</button>
                <button class="report-type-tab" data-rtype="weekly">周报</button>
            </div>
            <label class="report-label">工作要点（每行一条）</label>
            <textarea class="report-bullets" id="report-input" placeholder="完成了推荐流模块开发&#10;调研了 vLLM 部署方案&#10;修复了3个bug"></textarea>
            <div class="report-actions">
                <button class="btn-primary" id="btn-report-gen">生成</button>
                <button class="btn-secondary" id="btn-report-copy">复制</button>
            </div>
            <div class="report-output" id="report-output" style="display:none;"></div>
        </div>`;
    },

    bindReport() {
        let rtype = "daily";
        document.querySelectorAll(".report-type-tab").forEach((tab) => {
            tab.addEventListener("click", () => {
                document.querySelectorAll(".report-type-tab").forEach((t) => t.classList.remove("active"));
                tab.classList.add("active");
                rtype = tab.dataset.rtype;
            });
        });

        const genBtn = document.getElementById("btn-report-gen");
        const copyBtn = document.getElementById("btn-report-copy");

        genBtn.addEventListener("click", async () => {
            const input = document.getElementById("report-input").value.trim();
            if (!input) {
                Toast.show("请先输入工作要点");
                return;
            }
            genBtn.disabled = true;
            const output = document.getElementById("report-output");
            output.style.display = "block";
            output.innerHTML = `<div class="loading-block"><div class="loading-spinner"></div><p>正在生成${rtype === "daily" ? "日报" : "周报"}...</p></div>`;

            const prompt = rtype === "daily"
                ? `请将以下工作要点整理成一份规范、简洁的工作日报。格式包含：今日完成、问题与风险、明日计划。要点：\n${input}`
                : `请将以下工作要点整理成一份规范的工作周报。格式包含：本周完成、进展与成果、问题与风险、下周计划。要点：\n${input}`;

            try {
                const result = await LLM.chat([
                    { role: "system", content: "你是工作汇报撰写助手，输出简洁、专业、条理清晰。始终用中文回复。" },
                    { role: "user", content: prompt },
                ], { temperature: 0.3, maxTokens: 1500 });
                output.textContent = result;
                Toast.show("生成完成");
            } catch (e) {
                output.textContent = "生成失败: " + e.message;
            } finally {
                genBtn.disabled = false;
            }
        });

        copyBtn.addEventListener("click", () => {
            const text = document.getElementById("report-output").textContent;
            if (!text || text.startsWith("生成失败") || text.startsWith("正在")) return;
            navigator.clipboard.writeText(text).then(() => {
                Toast.show("已复制");
            }).catch(() => {
                Toast.show("复制失败");
            });
        });
    },

    // ====== 习惯 ======
    renderHabit() {
        const habits = Store.getHabits();
        const listHTML = habits.length
            ? habits.map((h) => `
                <div class="habit-card">
                    <div class="habit-info">
                        <div class="habit-name">${escapeHTML(h.name)}</div>
                        <div class="habit-desc">${escapeHTML(h.desc || "")}</div>
                    </div>
                    <span class="habit-streak">${h.streak || 0} 天</span>
                    <button class="habit-delete" data-id="${h.id}">删除</button>
                </div>
            `).join("")
            : `<p class="habit-empty">还没有习惯，添加一个开始坚持。</p>`;

        return `
        <h2>习惯</h2>
        <p class="hint">设定习惯，RadarME 会每天推送相关内容。</p>
        <div class="habit-tool">
            <div class="habit-add-area">
                <input type="text" id="habit-name-input" placeholder="习惯名称（如：学英语）">
                <input type="text" id="habit-desc-input" placeholder="描述（可选）" style="flex:0.7;">
                <button class="btn-primary btn-sm" id="btn-habit-add">添加</button>
            </div>
            <div class="habit-list" id="habit-list">${listHTML}</div>
        </div>`;
    },

    updateHabitDOM() {
        document.getElementById("tool-panel-content").innerHTML = this.renderHabit();
        this.bindHabit();
    },

    bindHabit() {
        document.getElementById("btn-habit-add").addEventListener("click", () => this.addHabit());
        document.getElementById("habit-name-input").addEventListener("keydown", (e) => {
            if (e.key === "Enter") this.addHabit();
        });
        // 事件委托删除
        document.getElementById("habit-list").addEventListener("click", (e) => {
            const delBtn = e.target.closest(".habit-delete");
            if (delBtn) this.deleteHabit(delBtn.dataset.id);
        });
    },

    addHabit() {
        const name = document.getElementById("habit-name-input").value.trim();
        const desc = document.getElementById("habit-desc-input").value.trim();
        if (!name) {
            Toast.show("请输入习惯名称");
            return;
        }
        const habits = Store.getHabits();
        habits.push({
            id: "hb_" + Date.now(),
            name, desc, streak: 0,
            createdAt: new Date().toISOString(),
        });
        Store.saveHabits(habits);
        this.updateHabitDOM();
        Toast.show("习惯已添加");
    },

    deleteHabit(id) {
        let habits = Store.getHabits();
        habits = habits.filter((h) => h.id !== id);
        Store.saveHabits(habits);
        this.updateHabitDOM();
        Toast.show("习惯已删除");
    },

    // ====== 收藏 ======
    renderFavorites() {
        const favs = Store.getFavorites();
        const listHTML = favs.length
            ? favs.map((f) => `
                <div class="fav-card">
                    <div class="fav-title">${escapeHTML(f.title || "无标题")}</div>
                    <div class="fav-summary">${escapeHTML(f.summary || "")}</div>
                    <div class="fav-meta">${new Date(f.savedAt).toLocaleDateString("zh-CN")}${f.source_url ? ` · <a href="${escapeHTML(f.source_url)}" target="_blank" rel="noopener">原文</a>` : ""}</div>
                </div>
            `).join("")
            : `<div class="fav-empty">还没有收藏内容。在推荐流中点击「收藏」即可。</div>`;

        return `
        <h2>收藏</h2>
        <p class="hint">你收藏的有价值内容。</p>
        <div class="favorites-tool">
            <div class="fav-list">${listHTML}</div>
        </div>`;
    },

    // ====== 待办 ======
    renderTodo() {
        const todos = Store.getTodos();
        const listHTML = todos.length
            ? todos.map((t) => `
                <div class="todo-item ${t.done ? "done" : ""}" data-id="${t.id}">
                    <div class="todo-check ${t.done ? "done" : ""}" data-id="${t.id}"></div>
                    <span class="todo-text">${escapeHTML(t.text)}</span>
                    <button class="todo-delete" data-id="${t.id}">删除</button>
                </div>
            `).join("")
            : `<p class="todo-empty">暂无待办。</p>`;

        return `
        <h2>待办</h2>
        <p class="hint">快速记录待办事项。</p>
        <div class="todo-tool">
            <div class="todo-input-area">
                <input type="text" id="todo-input" placeholder="输入待办，回车添加...">
                <button class="btn-primary btn-sm" id="btn-todo-add">添加</button>
            </div>
            <div class="todo-list" id="todo-list">${listHTML}</div>
        </div>`;
    },

    updateTodoDOM() {
        document.getElementById("tool-panel-content").innerHTML = this.renderTodo();
        this.bindTodo();
    },

    bindTodo() {
        document.getElementById("btn-todo-add").addEventListener("click", () => this.addTodo());
        document.getElementById("todo-input").addEventListener("keydown", (e) => {
            if (e.key === "Enter") this.addTodo();
        });
        const listEl = document.getElementById("todo-list");
        listEl.addEventListener("click", (e) => {
            const check = e.target.closest(".todo-check");
            const del = e.target.closest(".todo-delete");
            if (check) this.toggleTodo(check.dataset.id);
            else if (del) this.deleteTodo(del.dataset.id);
        });
    },

    addTodo() {
        const text = document.getElementById("todo-input").value.trim();
        if (!text) return;
        const todos = Store.getTodos();
        todos.push({
            id: "td_" + Date.now(),
            text, done: false,
            createdAt: new Date().toISOString(),
        });
        Store.saveTodos(todos);
        this.updateTodoDOM();
        document.getElementById("todo-input").focus();
    },

    toggleTodo(id) {
        const todos = Store.getTodos();
        const t = todos.find((x) => x.id === id);
        if (t) {
            t.done = !t.done;
            Store.saveTodos(todos);
            this.updateTodoDOM();
        }
    },

    deleteTodo(id) {
        let todos = Store.getTodos();
        todos = todos.filter((t) => t.id !== id);
        Store.saveTodos(todos);
        this.updateTodoDOM();
    },
};
