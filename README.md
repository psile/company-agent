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
cd D:\hobby\AI_agent\memory\company-agent
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

主动推送有两个命令：

```powershell
# 拉取订阅源，重新排序，并把高相关内容自动推到飞书
python -m radar ingest

# 不刷新订阅源，直接把当前“为你”列表第一条推到飞书
python -m radar push

# 只测试飞书通道
python -m radar feishu-test
```

如果 `python -m radar ingest` 显示 `pushed=0`，通常不是飞书坏了，而是没有内容达到 `RADAR_PUSH_THRESHOLD`。可以临时把 `.env` 里的阈值调低，例如：

```powershell
RADAR_PUSH_THRESHOLD=70
```

## 配置

复制 `env.example`，用环境变量填，不要把密钥写进仓库。也可以在项目根目录创建 `.env`，或创建 `data/.env`；程序启动时会自动读取，且不会覆盖已存在的系统环境变量。

| 变量 | 含义 |
|---|---|
| `LLM_BASE_URL` | OpenAI 兼容网关 |
| `LLM_API_KEY` | 密钥 |
| `LLM_MODEL` | 模型名 |
| `FEISHU_WEBHOOK_URL` | 飞书自定义机器人；不配则只准备文案 |
| `FEISHU_SECRET` | 飞书机器人签名密钥；机器人未开启签名可不填 |
| `FEISHU_APP_ID` | 飞书自建应用 App ID；配置后优先走一对一应用机器人 |
| `FEISHU_APP_SECRET` | 飞书自建应用 App Secret |
| `FEISHU_RECEIVE_ID_TYPE` | 接收人类型，个人推送建议先用 `email` |
| `FEISHU_RECEIVE_ID` | 接收人 ID；`email` 模式下填你的飞书登录邮箱 |
| `FEISHU_RECEIVE_MOBILE` | 手机号登录时可填绑定手机号，系统会先换取 `open_id` |
| `RADAR_PUSH_THRESHOLD` | 自动飞书推送分数阈值，默认 85 |
| `RADAR_PUSH_LIMIT` | 每次刷新最多主动推送几条，默认 2 |
| `RADAR_PUSH_DRY_RUN=1` | 只生成飞书文案，不真实发送 |
| `RADAR_LLM=0` | 关掉模型，退回启发式 |
| `MEMORYOS_ENABLED=1` | 尝试官方 MemoryOS（需自备依赖） |

本机若旁边还有 `RadarME/js/config.js`，会当作网关兜底，那不是本仓库的一部分。

## 接入飞书

推荐优先用「一对一应用机器人」做个人秘书私聊推送；群自定义机器人更适合临时通知群或只有自己的小群。

### 一对一应用机器人

适合个人秘书私聊推送。需要飞书自建应用开启机器人能力，并申请 `im:message:send_as_bot` 权限。

管理后台流程：

1. 打开飞书开放平台，创建企业自建应用。
2. 在「应用能力」里开启机器人能力。
3. 在「权限管理」里批量导入权限：

```json
{
  "scopes": {
    "tenant": [
      "im:message:send_as_bot",
      "contact:user.id:readonly",
      "docx:document:readonly"
    ],
    "user": [
      "docx:document:readonly"
    ]
  }
}
```

4. 在「版本管理与发布」里创建版本并提交发布，等待管理员审核通过。
5. 在「凭证与基础信息」复制 `App ID` 和 `App Secret`。
6. 确认应用可用范围包含接收人本人。

在本机创建 `.env`：

```powershell
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_RECEIVE_ID_TYPE=email
FEISHU_RECEIVE_ID=your.name@example.com
RADAR_PUSH_THRESHOLD=85
RADAR_PUSH_LIMIT=2
```

只要这组配置完整，系统会优先发一对一应用机器人消息。

如果飞书账号是手机号登录，没有邮箱，可以改成：

```powershell
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_RECEIVE_ID_TYPE=open_id
FEISHU_RECEIVE_ID=
FEISHU_RECEIVE_MOBILE=13800138000
```

手机号换取 `open_id` 需要额外权限：`contact:user.id:readonly`。导入权限后同样要发布版本并通过审核。

测试一对一推送：

```powershell
python -m radar feishu-test
```

如果测试成功但刷新源没有推送，通常是没有内容达到 `RADAR_PUSH_THRESHOLD`，或该条内容已经在 `data/pushed.json` 中标记为推过。

### 群自定义机器人

1. 在飞书群里添加「自定义机器人」，复制 webhook 地址。
2. 如果机器人开启了签名校验，同时复制签名密钥。
3. 在 `.env` 里写：

```powershell
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/...
FEISHU_SECRET=
RADAR_PUSH_THRESHOLD=85
RADAR_PUSH_LIMIT=2
```

如果机器人没有开启签名，`FEISHU_SECRET` 留空即可。想先看文案、不真实发送，可以设：

```powershell
RADAR_PUSH_DRY_RUN=1
```

刷新源时，系统只会把高相关、未推过的「为你」内容推到飞书；未配置 webhook 时只返回中文推送文案，不会假装已发送。

## 反馈怎么进记忆

- **打开原文**：弱正反馈
- **有用**：升兴趣权重，进个人库
- **收藏**：比有用更强
- **忽略**：不等于讨厌
- **不相关**：降权，类似内容少推

## 明确不做

全网爬登录墙、推荐模型训练、把内部文档丢给公网模型、未配 webhook 时假装已经发到飞书。
