/**
 * RadarME 配置
 * 密钥不要写进仓库。复制本文件为 config.js 后填写，或改用环境变量。
 */
const Config = {
    llm: {
        baseURL: "",
        apiKey: "",
        model: "Qwen3.8-27B",
    },
    storage: {
        targets: "radar_targets",
        todos: "radar_todos",
        habits: "radar_habits",
        favorites: "radar_favorites",
        knowledge: "radar_knowledge",
        sniffKeywords: "radar_sniff_keywords",
        chatHistory: "radar_chat_history",
        workFeed: "radar_work_feed",
        personalFeed: "radar_personal_feed",
    },
};
