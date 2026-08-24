/**
 * 本地存储封装（localStorage + JSON）
 */
const Store = {
    get(key, fallback = null) {
        try {
            const raw = localStorage.getItem(key);
            return raw ? JSON.parse(raw) : fallback;
        } catch (_) {
            return fallback;
        }
    },

    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) {
            console.error("存储失败:", e);
        }
    },

    remove(key) {
        localStorage.removeItem(key);
    },

    // === 目标 ===
    getTargets() {
        return this.get(Config.storage.targets, []);
    },
    saveTargets(list) {
        this.set(Config.storage.targets, list);
    },

    // === 待办 ===
    getTodos() {
        return this.get(Config.storage.todos, []);
    },
    saveTodos(list) {
        this.set(Config.storage.todos, list);
    },

    // === 习惯 ===
    getHabits() {
        return this.get(Config.storage.habits, []);
    },
    saveHabits(list) {
        this.set(Config.storage.habits, list);
    },

    // === 收藏 ===
    getFavorites() {
        return this.get(Config.storage.favorites, []);
    },
    saveFavorites(list) {
        this.set(Config.storage.favorites, list);
    },

    // === 知识库 ===
    getKnowledge() {
        return this.get(Config.storage.knowledge, []);
    },
    saveKnowledge(list) {
        this.set(Config.storage.knowledge, list);
    },

    // === 嗅探关键词 ===
    getSniffKeywords() {
        return this.get(Config.storage.sniffKeywords, [
            "大模型", "AI Agent", "车载", "推理优化", "RAG",
        ]);
    },
    saveSniffKeywords(list) {
        this.set(Config.storage.sniffKeywords, list);
    },

    // === 聊天历史 ===
    getChatHistory() {
        return this.get(Config.storage.chatHistory, []);
    },
    saveChatHistory(list) {
        this.set(Config.storage.chatHistory, list.slice(-50));
    },

    // === 推荐流缓存 ===
    getWorkFeed() {
        return this.get(Config.storage.workFeed, null);
    },
    saveWorkFeed(data) {
        this.set(Config.storage.workFeed, data);
    },
    getPersonalFeed() {
        return this.get(Config.storage.personalFeed, null);
    },
    savePersonalFeed(data) {
        this.set(Config.storage.personalFeed, data);
    },
};
