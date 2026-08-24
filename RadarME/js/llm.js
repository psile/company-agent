/**
 * LLM 调用封装
 *
 * 支持流式（SSE）与非流式两种模式。
 * 流式模式下通过 onChunk 回调实时推送增量文本，边生成边显示。
 */
const LLM = {
    /** 当前正在进行的请求，用于取消 */
    _abortController: null,

    /**
     * 非流式调用
     * @returns {Promise<string>}
     */
    async chat(messages, opts = {}) {
        const { temperature = 0.7, maxTokens = 2048 } = opts;
        const trimmed = messages.slice(-20);
        const body = {
            model: Config.llm.model,
            messages: trimmed,
            temperature,
            max_tokens: maxTokens,
        };

        const resp = await fetch(`${Config.llm.baseURL}/chat/completions`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${Config.llm.apiKey}`,
            },
            body: JSON.stringify(body),
        });

        if (!resp.ok) {
            const errText = await resp.text().catch(() => "");
            throw new Error(`LLM 请求失败 (${resp.status}): ${errText}`);
        }

        const data = await resp.json();
        const content = data?.choices?.[0]?.message?.content;
        if (!content) throw new Error("LLM 返回为空");
        return content.trim();
    },

    /**
     * 流式调用 —— SSE
     * @param {Array} messages
     * @param {Object} opts - { temperature, maxTokens, onChunk(chunkText), signal }
     *   onChunk: 每收到一段增量文本时回调
     *   signal:  AbortSignal，用于取消
     * @returns {Promise<string>} 完整文本
     */
    async chatStream(messages, opts = {}) {
        const { temperature = 0.7, maxTokens = 2048, onChunk = null, signal = null } = opts;
        const trimmed = messages.slice(-20);
        const body = {
            model: Config.llm.model,
            messages: trimmed,
            temperature,
            max_tokens: maxTokens,
            stream: true,
        };

        const resp = await fetch(`${Config.llm.baseURL}/chat/completions`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${Config.llm.apiKey}`,
            },
            body: JSON.stringify(body),
            signal,
        });

        if (!resp.ok) {
            const errText = await resp.text().catch(() => "");
            throw new Error(`LLM 请求失败 (${resp.status}): ${errText}`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let fullText = "";

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // SSE 按 \n\n 分隔事件
                const lines = buffer.split("\n");
                // 最后一段可能不完整，保留
                buffer = lines.pop();

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (!trimmedLine || !trimmedLine.startsWith("data:")) continue;

                    const data = trimmedLine.slice(5).trim();
                    if (data === "[DONE]") continue;

                    try {
                        const json = JSON.parse(data);
                        const delta = json?.choices?.[0]?.delta?.content;
                        if (delta) {
                            fullText += delta;
                            if (onChunk) onChunk(delta, fullText);
                        }
                    } catch (_) {
                        // JSON 解析失败，跳过不完整片段
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }

        if (!fullText.trim()) throw new Error("LLM 返回为空");
        return fullText.trim();
    },

    /**
     * 流式 + JSON 解析
     * 生成完成后从完整文本中提取 JSON
     */
    async chatJSONStream(messages, opts = {}) {
        const raw = await this.chatStream(messages, { temperature: 0.5, ...opts });
        return this.extractJSON(raw);
    },

    /**
     * 取消当前请求
     */
    abort() {
        if (this._abortController) {
            this._abortController.abort();
            this._abortController = null;
        }
    },

    /** 创建一个新的 AbortController 并记录 */
    createAbortController() {
        this._abortController = new AbortController();
        return this._abortController.signal;
    },

    /**
     * 从 LLM 文本中提取 JSON（兼容 ```json 包裹）
     */
    extractJSON(text) {
        const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (fenceMatch) {
            try { return JSON.parse(fenceMatch[1].trim()); } catch (_) {}
        }
        try { return JSON.parse(text.trim()); } catch (_) {}
        const braceMatch = text.match(/\{[\s\S]*\}/);
        if (braceMatch) {
            try { return JSON.parse(braceMatch[0]); } catch (_) {}
        }
        const arrMatch = text.match(/\[[\s\S]*\]/);
        if (arrMatch) {
            try { return JSON.parse(arrMatch[0]); } catch (_) {}
        }
        throw new Error("无法从 LLM 输出中解析 JSON");
    },
};
