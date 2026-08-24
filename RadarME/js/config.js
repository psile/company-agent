/**
 * RadarME 配置
 * 本地密钥请写在本文件，不要提交真实 key。也可改用环境变量 LLM_BASE_URL / LLM_API_KEY。
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
