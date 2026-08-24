/**
 * App 主入口：路由、导航、全局工具
 */
const App = {
    init() {
        this.bindNav();
        this.bindGlobalEvents();
        FeedModule.init();
        TargetsModule.init();
        ToolsModule.init();
        ManagerModule.init();
    },

    bindNav() {
        document.querySelectorAll(".nav-item").forEach((item) => {
            item.addEventListener("click", () => {
                this.switchPage(item.dataset.page);
            });
        });
    },

    switchPage(pageName) {
        document.querySelectorAll(".nav-item").forEach((el) => {
            el.classList.toggle("active", el.dataset.page === pageName);
        });
        document.querySelectorAll(".page").forEach((el) => {
            el.classList.toggle("active", el.id === `page-${pageName}`);
        });
    },

    bindGlobalEvents() {
        document.getElementById("btn-target-cancel").addEventListener("click", () => {
            App.hideModal("modal-target");
        });
        document.getElementById("btn-target-save").addEventListener("click", () => {
            TargetsModule.saveFromModal();
        });
        document.getElementById("modal-target").addEventListener("click", (e) => {
            if (e.target.id === "modal-target") App.hideModal("modal-target");
        });
    },

    showModal(id) {
        document.getElementById(id).classList.add("show");
    },

    hideModal(id) {
        document.getElementById(id).classList.remove("show");
    },
};

/** Toast 通知 —— 右下角，小而克制 */
const Toast = {
    show(msg, duration = 2200) {
        const el = document.getElementById("toast");
        el.textContent = msg;
        el.classList.add("show");
        clearTimeout(this._timer);
        this._timer = setTimeout(() => {
            el.classList.remove("show");
        }, duration);
    },
};

/** HTML 转义防 XSS */
function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = String(str ?? "");
    return div.innerHTML;
}

function apiUrl(path) {
    const base = location.protocol === "file:" ? "http://127.0.0.1:8765" : "";
    return base + path;
}
