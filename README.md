# 个人工作秘书 Agent

今天发布的不是又一个信息流，也不是又一个知识库。

这是一个会上班的个人智能体。

**Remember · Observe · Act**  
记住你，观察世界，然后在合适的时间主动把真正相关的信息送到你面前。

仓库根目录就是本项目。改推荐、记忆、推送，都在这里改。不要把整个 `company_agent` 工作区推上来。

---

## 产品一句话

大多数工具都在等你提问。你不搜，它就不工作。

个人工作秘书反过来：你告诉它「最近帮我重点关注 Agent Memory」，然后可以去开会。它仍在后台看 arXiv、GitHub、技术博客、官方动态和你指定的网站。

今天它替你看了 42 条。真正值得停下看的，只有 5 条。首页会直接告诉你这件事。

```text
主动感知 Observe
        ↓
信息理解 Understand
        ↓
长期记忆 Memory
        ↓
个性化判断 Recommendation
        ↓
主动推送 Push
        ↓
用户反馈 Feedback
        ↓
记忆更新 Memory Update
        ↓
推荐持续进化 Evolve
```

情报回答「世界发生了什么」。推荐回答「这件事此刻值不值得推给这个人」。两件事共用一个候选池，不是两套模块。

---

## 工作台

桌面端 SaaS 布局：顶栏搜索、左侧导航、主区、右侧上下文。不是新闻站，不是 CMS，不是纯 Chat 页。

左侧导航始终在：

- 首页
- 为你推荐
- 我的关注
- 目标管理
- 知识库
- 工具箱
- 个人中心
- 设置（个人信息 / 账号与安全 / 偏好设置 / 推送与通知 / 数据与隐私 / 成员与权限）

底部是记忆引擎状态：正常运行、已处理多少条、今日新增多少条。即使你没有和它对话，它也在后台替你观察。

| 路由 | 页面 | 演示什么 |
|---|---|---|
| `#/` | 首页 | 今天观察了多少、筛出多少；Why For You；当前目标 |
| `#/recommend` | 为你推荐 | 工作 / 个人推荐、相关度、本周主题、Daily Brief 预览 |
| `#/follows` | 我的关注 | 主题权重、产品、信息源；自然语言加关注 |
| `#/goals` | 目标管理 | 今日 / 短期 / 长期 / 不定期；Goal → Context → 推荐优先级 |
| `#/knowledge` | 知识库 | 点赞收藏沉淀、LLM 预分类、手动改分类 |
| `#/toolbox` | 工具箱 | Skills 入口占位，当前重点是 Recommendation Skill |
| `#/profile` | 个人中心 | 兴趣画像、偏好、Memory 摘要 |
| `#/settings/push` | 推送与通知 | Web / 飞书 / 对话、Morning Brief、高相关即时推送 |

每一条推荐都必须有：中文摘要、来源、相关度、**为什么推荐给你**、**与当前项目的关系**、原文 / 有用 / 收藏 / 减少此类推荐。

点赞之后不是「点赞成功」，而是：已记录你的偏好，将提高相关主题的推荐权重。

---

## 运行

```powershell
cd D:\working\company_agent\radar
copy env.example .env
# 按下面「环境变量」填好 .env
python -m radar serve
```

浏览器：http://127.0.0.1:8765/

首页数字在尚未采集时可能是占位。点 **刷新源** 后走完整链路：采集 → 理解 → 记忆匹配 → 为你排序。

```powershell
python -m radar ingest          # 拉源、排序，高相关则推飞书
python -m radar push            # 把当前「为你」第一条推到飞书
python -m radar feishu-test     # 只测飞书通道
python -m pytest -q
```

对外监听：

```powershell
$env:RADAR_HOST="0.0.0.0"
$env:PORT="8766"
python -m radar serve
```

---

## 环境变量（.env 配置）

**不要把填好密钥的 `.env` 提交到 GitHub。** 仓库只收录 `env.example` 作为模板。本机复制后填写：

```powershell
copy env.example .env
```

程序启动时会读取项目根目录 `.env` 或 `data/.env`，且不会覆盖已经存在的系统环境变量。

| 变量 | 含义 | 示例 |
|---|---|---|
| `LLM_BASE_URL` | OpenAI 兼容网关 | `http://127.0.0.1:8000/v1` |
| `LLM_API_KEY` | 模型密钥 | 留空则按网关要求 |
| `LLM_MODEL` | 模型名 | 按你的网关填写 |
| `RADAR_LLM=0` | 关掉模型，退回启发式 | `0` |
| `FEISHU_APP_ID` | 飞书自建应用 App ID | `cli_xxx` |
| `FEISHU_APP_SECRET` | 飞书自建应用 App Secret | **不要入库** |
| `FEISHU_RECEIVE_ID_TYPE` | 接收人类型 | `email` 或 `open_id` |
| `FEISHU_RECEIVE_ID` | 接收人 ID / 邮箱 | |
| `FEISHU_RECEIVE_MOBILE` | 手机号登录时换 open_id | |
| `FEISHU_WEBHOOK_URL` | 群自定义机器人 webhook | 一对一应用机器人优先时可不填 |
| `FEISHU_SECRET` | 群机器人签名密钥 | 未开签名则留空 |
| `RADAR_HOST` | HTTP 监听地址 | `127.0.0.1` 或 `0.0.0.0` |
| `PORT` | 端口 | `8765` |
| `RADAR_PUSH_THRESHOLD` | 自动推送分数阈值 | `85` |
| `RADAR_PUSH_LIMIT` | 每次刷新最多推几条 | `2` |
| `RADAR_PUSH_DRY_RUN=1` | 只生成文案，不真实发送 | `0` |
| `RADAR_OBSERVE_MINUTES` | 后台定时拉源间隔（分钟） | `180`；`0` 关闭 |
| `RADAR_OBSERVE_ON_START=1` | 启动后立刻采集一次 | 默认 `0` |
| `MEMORYOS_ENABLED` | 尝试官方 MemoryOS | `0` |

`ingest` 显示 `pushed=0` 时，通常不是飞书坏了，而是没有内容达到 `RADAR_PUSH_THRESHOLD`，或该条已在 `data/pushed.json` 里记过。

---

## 接入飞书

推荐「一对一应用机器人」做个人秘书私聊。群自定义机器人适合临时通知群。

### 一对一应用机器人

1. 飞书开放平台创建企业自建应用，开启机器人能力。
2. 权限至少包含 `im:message:send_as_bot`；手机号换 `open_id` 还需 `contact:user.id:readonly`。
3. 发布版本并通过审核。
4. 把 App ID / Secret 写进本机 `.env`：

```
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_RECEIVE_ID_TYPE=email
FEISHU_RECEIVE_ID=your.name@example.com
RADAR_PUSH_THRESHOLD=85
RADAR_PUSH_LIMIT=2
```

手机号登录、没有邮箱时：

```
FEISHU_RECEIVE_ID_TYPE=open_id
FEISHU_RECEIVE_ID=
FEISHU_RECEIVE_MOBILE=13800138000
```

```powershell
python -m radar feishu-test
```

### 群自定义机器人

```
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/...
FEISHU_SECRET=
```

未开启签名则 `FEISHU_SECRET` 留空。想先看文案：`RADAR_PUSH_DRY_RUN=1`。

---

## 代码结构

```text
Agent Core
├── Collector      radar/ingest.py + sources.json
├── Intelligence   radar/intelligence.py
├── Memory         radar/user_memory.py + radar/memory_os.py
├── Recommendation radar/recommender.py
├── Push           radar/feishu.py
├── Knowledge      收藏 → LLM 分类 → 知识库 → 手动调整
├── Workspace      radar/workspace.py（目标 / 关注产品 / 推送偏好 / 观察计数）
└── Skills         当前重点 Recommendation Skill；工具箱为后续预留
```

| 路径 | 职责 |
|---|---|
| `radar/ingest.py` | 采集与去重 |
| `radar/intelligence.py` | 中文摘要、分类、标签 |
| `radar/user_memory.py` | 画像、兴趣权重、项目、行为 |
| `radar/recommender.py` | 召回打分与 LLM 重排 |
| `radar/pipeline.py` | 串起整条链路 |
| `radar/workspace.py` | 工作台账本 |
| `radar/feishu.py` | 飞书中文卡片 |
| `radar/server.py` | HTTP 工作台 + API |
| `web/` | 前端工作台 |
| `sources.json` | 订阅源 |
| `env.example` | 环境变量模板 |
| `data/` | 本地画像与缓存，**不入库** |

---

## 反馈怎么进记忆

- **打开原文**：弱正反馈
- **有用**：升兴趣权重，进个人库
- **收藏**：更强，并由 LLM 预分类到知识库
- **忽略**：不等于讨厌
- **不相关**：降权，类似内容少推
- **手动改分类**：学习你的整理习惯

---

## 明确不做

全网爬登录墙、推荐模型训练、把内部文档丢给公网模型、把真实 `.env` 密钥推进 GitHub、未配置飞书时假装已经发出。
