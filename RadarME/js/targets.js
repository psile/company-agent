/**
 * 目标模块
 */
const TargetsModule = {
    init() {
        this.bindEvents();
        this.render();
    },

    bindEvents() {
        document.getElementById("btn-add-target").addEventListener("click", () => {
            this.openModal();
        });
    },

    openModal(id = null, presetType = "today") {
        const list = Store.getTargets();
        const target = id ? list.find((t) => t.id === id) : null;

        document.getElementById("target-edit-id").value = id || "";
        document.getElementById("target-edit-type").value = target ? target.type : presetType;
        document.getElementById("target-edit-text").value = target ? target.text : "";
        document.getElementById("modal-target-title").textContent = target ? "编辑目标" : "新建目标";
        App.showModal("modal-target");
        setTimeout(() => document.getElementById("target-edit-text").focus(), 100);
    },

    saveFromModal() {
        const id = document.getElementById("target-edit-id").value;
        const type = document.getElementById("target-edit-type").value;
        const text = document.getElementById("target-edit-text").value.trim();

        if (!text) {
            Toast.show("请输入目标内容");
            return;
        }

        const list = Store.getTargets();
        if (id) {
            const idx = list.findIndex((t) => t.id === id);
            if (idx >= 0) {
                list[idx].type = type;
                list[idx].text = text;
                list[idx].updatedAt = new Date().toISOString();
            }
        } else {
            list.push({
                id: "tg_" + Date.now(),
                type,
                text,
                done: false,
                createdAt: new Date().toISOString(),
            });
        }
        Store.saveTargets(list);
        App.hideModal("modal-target");
        this.render();
        Toast.show(id ? "目标已更新" : "目标已创建");
    },

    toggleDone(id) {
        const list = Store.getTargets();
        const t = list.find((x) => x.id === id);
        if (t) {
            t.done = !t.done;
            Store.saveTargets(list);
            this.render();
        }
    },

    deleteTarget(id) {
        let list = Store.getTargets();
        list = list.filter((t) => t.id !== id);
        Store.saveTargets(list);
        this.render();
        Toast.show("目标已删除");
    },

    render() {
        const list = Store.getTargets();
        const types = ["today", "short", "long", "casual"];

        types.forEach((type) => {
            const container = document.getElementById(`list-${type}`);
            const items = list.filter((t) => t.type === type);
            document.getElementById(`count-${type}`).textContent = items.length;

            let html = items.map((t) => `
                <div class="target-card ${t.done ? "done" : ""}" data-id="${t.id}">
                    <div class="target-text">${escapeHTML(t.text)}</div>
                    <div class="target-meta">
                        <time>${this.timeAgo(t.createdAt)}</time>
                        <div class="target-actions">
                            <button class="tgt-action" data-act="toggle" data-id="${t.id}">${t.done ? "恢复" : "完成"}</button>
                            <button class="tgt-action" data-act="edit" data-id="${t.id}">编辑</button>
                            <button class="tgt-action delete" data-act="delete" data-id="${t.id}">删除</button>
                        </div>
                    </div>
                </div>
            `).join("");

            html += `<button class="add-target-btn" data-type="${type}">+ 添加</button>`;

            container.innerHTML = html;
        });

        // 事件委托
        document.querySelectorAll(".target-list").forEach((listEl) => {
            listEl.addEventListener("click", (e) => {
                const btn = e.target.closest("[data-act], .add-target-btn");
                if (!btn) return;
                if (btn.classList.contains("add-target-btn")) {
                    this.openModal(null, btn.dataset.type);
                    return;
                }
                const act = btn.dataset.act;
                const id = btn.dataset.id;
                if (act === "toggle") this.toggleDone(id);
                else if (act === "edit") this.openModal(id);
                else if (act === "delete") this.deleteTarget(id);
            });
        });
    },

    timeAgo(iso) {
        const diff = Date.now() - new Date(iso).getTime();
        const min = Math.floor(diff / 60000);
        if (min < 1) return "刚刚";
        if (min < 60) return `${min}分钟前`;
        const hr = Math.floor(min / 60);
        if (hr < 24) return `${hr}小时前`;
        const day = Math.floor(hr / 24);
        return `${day}天前`;
    },
};
