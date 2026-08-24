# 个人秘书 · 情报与推荐

这是个人工作秘书里，**技术情报**和**个性化推荐**这一条链路的代码。

仓库根目录就是 `radar/`。后面改推荐、记忆、推送，都在这里改，不要把整个 `company_agent` 工作区推上来。

## 做什么

情报回答「世界发生了什么」，推荐回答「这件事此刻值不值得推给这个人」。两件事共用一个候选池，不是两套模块。

```text
采集（arXiv / GitHub / RSS / 指定网址）
    → 去重（必须有原文链接）
    → LLM 结构化理解（中文摘要、tag、价值）
    → Memory（带权兴趣 / 当前项目 / 行为与负反馈）
    → 规则排序 + LLM 重排
    → 页面展示 / 飞书主动推送
    → 有用、收藏、不相关
    → 写回 Memory
```

每条推送给用户看的内容用中文：总结、tag、为什么推给你、和当前项目的关系。tag 是为了让人扫一眼就知道感不感兴趣。

## 目录

| 路径 | 职责 |
|---|---|
| `radar/ingest.py` | 采集与去重 |
| `radar/intelligence.py` | 理解：摘要、分类、价值，不做推不推 |
| `radar/user_memory.py` | 画像、兴趣权重、项目、行为 |
| `radar/recommender.py` | 召回打分与 LLM 重排 |
| `radar/pipeline.py` | 串起整条链路 |
| `radar/feishu.py` | 飞书文案（中文总结 + tag） |
| `web/` | 情报 / 为你 / 记忆 |
| `sources.json` | 订阅源 |
| `data/` | 本地画像与缓存，**不入库** |

更细的产品拆解见 `FEATURES.md`。

## 运行

```powershell
cd D:\working\company_agent\radar
python -m radar serve
```

浏览器：http://127.0.0.1:8765/

对外监听：

```powershell
$env:RADAR_HOST="0.0.0.0"
$env:PORT="8766"
python -m radar serve
```

或：`python deploy/simulate_cloud.py`

```powershell
python -m pytest -q
```

## 配置

复制 `env.example`，用环境变量填，不要把密钥写进仓库。

| 变量 | 含义 |
|---|---|
| `LLM_BASE_URL` | OpenAI 兼容网关 |
| `LLM_API_KEY` | 密钥 |
| `LLM_MODEL` | 模型名 |
| `FEISHU_WEBHOOK_URL` | 飞书自定义机器人；不配则只准备文案 |
| `RADAR_LLM=0` | 关掉模型，退回启发式 |
| `MEMORYOS_ENABLED=1` | 尝试官方 MemoryOS（需自备依赖） |

本机若旁边还有 `RadarME/js/config.js`，会当作网关兜底，那不是本仓库的一部分。

## 反馈怎么进记忆

- **打开原文**：弱正反馈
- **有用**：升兴趣权重，进个人库
- **收藏**：比有用更强
- **忽略**：不等于讨厌
- **不相关**：降权，类似内容少推

## 明确不做

全网爬登录墙、推荐模型训练、把内部文档丢给公网模型、未配 webhook 时假装已经发到飞书。
