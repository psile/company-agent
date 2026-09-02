# 个人工作秘书 Agent

今天发布的不是又一个信息流，也不是又一个知识库。

这是一个会上班的个人智能体。

**Remember · Observe · Act**  
记住你，观察世界，然后在合适的时间主动把真正相关的信息送到你面前。

仓库根目录就是本项目。改推荐、记忆、推送，都在这里改。不要把整个 `company_agent` 工作区推上来。

---

## 本轮更新

这次重点不是继续堆页面，而是把「主动感知 → 理解 → 推荐 → 推送 → 反馈学习」真正跑通。Agent 现在会持续观察真实外部信息，结合用户的兴趣、项目、目标和行为筛选内容，并在相关度足够高时主动发到飞书。

### 推荐与主动服务升级

| 能力 | 当前实现 |
|---|---|
| **真实内容源** | 接入 arXiv、GitHub Release、技术博客、行业新闻、知乎站内搜索和微信公众号文章搜索 + 国内源（量子位、36氪、极客公园、InfoQ、Solidot、少数派） |
| **来源真实性** | 所有推荐必须包含可访问的原文 URL；按允许域名校验，自动过滤 `example.com` 等占位地址，禁止用演示数据冒充线上内容 |
| **多主题观察** | 微信公众号按自动驾驶、世界模型、多模态大模型、智能座舱等主题分别检索，再跨查询去重，避免组合关键词过窄导致无结果 |
| **分层推荐** | 工作推荐聚焦当前项目和目标，个人推荐补充行业新闻、产品动态和值得一看的趣事；保留来源类型多样性 |
| **丰富中文理解** | 每条内容生成中文摘要、3 个要点、影响判断、后续观察点、标签、推荐理由以及与当前项目的关系 |
| **卡片与详情** | 列表先展示可快速浏览的紧凑卡片；点击后打开详情，再查看完整总结、作者、热度、关联和原文 |
| **主动观察与推送** | 后台按周期采集；高相关内容通过飞书应用机器人一对一推送，并记录已推送项防止重复打扰 |
| **反馈闭环** | 打开、有用、收藏、减少推荐等行为进入用户记忆，持续调整主题权重和推荐排序 |

### 工作秘书能力

| 能力 | 你怎么用 | 说明 |
|---|---|---|
| **工作记忆 Work Memory** | 对话里说待办，或在「我的工作」手动新建 / 编辑 | 每人一份任务 / 事件 / 备忘 / 提醒；支持周日历、安排时间和截止时间，存在 `data/users/<id>/`，互不串号 |
| **任务捕捉** | 「周五前把 PPT 做完，提醒我」 | 自动建成待办；有截止日期时会在截止前 24h / 3h 提醒 |
| **任务拆解** | 「帮我拆一下这个任务」 | 把一条待办拆成可执行的子步骤 |
| **智能提醒** | 「我等下三点要开交流会，提醒我一下」 | 听懂「三点 / 下午 / 等下」；到点推飞书私聊和站内通知；过了点再说会立刻补发 |
| **今日工作重点** | 「给我今天的工作重点」 | 按待办、截止和项目进度生成早报 |
| **工作总结 / 时间轴** | 打开「工作总结」，或「写日报」「生成本周总结」 | 基于 Task、WorkEvent、Goal、Knowledge 等工作数据形成按日期组织的工作时间轴，每日简报 + 周 / 月聚合，完整日报按需展开 |
| **项目记忆与跟踪** | 「这个项目现在进展怎么样？」或打开「项目」 | 多项目可创建、编辑和切换；长期保存项目内容、目标、验收标准和里程碑，并从任务、事件、知识中感知进度、风险和下一步 |
| **网页里配大模型** | 设置 → 大模型 | 网关、模型名、API Key 存本机 `data/llm.json`，优先于 `.env`，接口不回显完整密钥 |
| **网页里配知乎 API** | 设置 → 知乎 API | 知乎 Access Secret 存本机 `data/users/<id>/zhihu.json`，优先于 `.env`；不填则知乎/公众号源自动跳过 |
| **按问题检索记忆** | 对话里问「我最近在研究什么」；`GET /api/memory/search?q=` | 按当前问题召回画像、兴趣、项目、长中短记忆和待办，带同义词（如 长期记忆 ↔ Agent Memory） |
| **飞书里来回对话** | 给机器人发消息 | 长连接收消息，回复走同一套 Agent；主动提醒也会推回这条私聊（`open_id`） |

工具箱里仍占位、尚未实现的：研究助手、知识整理、会议助手、决策记忆、交付物生成。

### 改了什么

- **自然语言提醒**：以前「等下三点……提醒我」会被当成普通待办，只回「已记下……截止前会提醒你」，**没有定时记录**。现在会建成 15:00 的提醒；中文数字「三」能解析；当天已过点则马上发。
- **提醒扫描**：默认约 **1 分钟**一圈（`RADAR_REMIND_MINUTES`），启动后也会扫一次。未配飞书应用推送时，改走收件箱机器人的 `open_id`，不再只写网页通知。
- **推荐相关度**：兴趣 / 语义分不再只靠字面交集，会用文本相似和同义关系。
- **存盘**：用户 JSON 改为临时文件再 `replace`，降低写到一半断电留下坏文件的概率。
- **HTTP**：`server.py` 改为路由表（`radar/routes.py`），不再靠超长 if-elif 分发。
- **技能与记忆解耦**：办公 Skill 只通过 `RadarService` 写数据，不直接改 JSON 文件。

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
- 秘书对话
- 我的工作
- 项目
- 工作总结
- 为你推荐
- 我的关注
- 目标管理
- 知识库
- 工具箱
- 个人中心
- 设置（个人信息 / 账号与安全 / 大模型 / 知乎 API / 偏好设置 / 推送与通知 / 数据与隐私 / 成员与权限）

底部是记忆引擎状态：正常运行、已处理多少条、今日新增多少条。即使你没有和它对话，它也在后台替你观察。

| 路由 | 页面 | 演示什么 |
|---|---|---|
| `#/` | 首页 | 今天观察了多少、筛出多少；Why For You；今日工作重点 |
| `#/chat` | 秘书对话 | 意图识别后调 Tool / 办公 Skill；飞书私聊走同一套 |
| `#/work` | 我的工作 | 手动 / 对话统一任务、周日历、时间安排、截止提醒与工作事件 |
| `#/projects` | 项目 | Remember 项目约定、Observe 动态风险、Act 下一步行动 |
| `#/reports` | 工作总结 | 日期时间轴 + 每日简报 + 周 / 月聚合 + 完整日报展开 |
| `#/recommend` | 为你推荐 | 工作 / 个人推荐、相关度、本周主题、Daily Brief 预览 |
| `#/follows` | 我的关注 | 主题权重、产品、信息源；自然语言加关注 |
| `#/goals` | 目标管理 | 今日 / 短期 / 长期 / 不定期；Goal → Context → 推荐优先级 |
| `#/knowledge` | 知识库 | 点赞收藏沉淀、LLM 预分类、手动改分类 |
| `#/toolbox` | 工具箱 | 已上线办公 Skill + 后续占位 |
| `#/profile` | 个人中心 | 兴趣画像、偏好、Memory 摘要 |
| `#/settings/llm` | 大模型 | 网关 / 模型 / API Key（只留本机） |
| `#/settings/zhihu` | 知乎 API | Access Secret / API 地址（只留本机，可测试连接） |
| `#/settings/push` | 推送与通知 | Web / 飞书 / 对话、Morning Brief、高相关即时推送 |

每一条推荐都必须有：中文摘要、来源、相关度、**为什么推荐给你**、**与当前项目的关系**、原文 / 有用 / 收藏 / 减少此类推荐。

推荐列表采用「卡片摘要 + 详情抽屉」：列表负责快速扫描，点开后再查看完整要点、影响、观察点、作者与互动数据。系统不会为缺失来源的内容补造链接。

点赞之后不是「点赞成功」，而是：已记录你的偏好，将提高相关主题的推荐权重。

---

## 运行

```powershell
cd D:\hobby\AI_agent\memory\company-agent
copy env.example .env
# 按下面「环境变量」填好 .env
pip install -r requirements.txt
python -m radar serve
```

浏览器：http://127.0.0.1:8765/

登录后打开 `#/chat` 或点击左侧“秘书对话”。对话 Agent 会先判断意图，再通过 Tool Registry 调用现有 Memory、Workspace、关注、知识库和 Radar；请求体中的 `user_id` 不会被信任，用户身份始终来自登录 token。

### Conversation API

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/chat` | 持续对话；传入 `message` 和可选 `session_id` |
| `GET` | `/api/conversations` | 当前登录用户的历史会话 |
| `GET` | `/api/conversations/{session_id}` | 会话详情和消息 |
| `GET` | `/api/conversation-profile` | 获取回答风格与主动服务偏好 |
| `PUT` | `/api/conversation-profile` | 更新当前用户的对话偏好 |

每个用户的数据分别保存在：

```text
data/users/<user_id>/conversations/sessions.json
data/users/<user_id>/conversations/messages.json
data/users/<user_id>/conversation_profile.json
```

打开后先登录。可创建自己的账号，或试用 `alice / alice123`、`bob / bob123`。每个账号有一份私有 Memory。飞书 App ID / Secret 写在 **设置 → 账号与安全**，只作用于当前用户。

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

### 硅基流动 DeepSeek-V4-Flash

项目使用 OpenAI 兼容的 `/chat/completions` 接口，可直接接入硅基流动：

```env
RADAR_LLM=1
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_API_KEY=在硅基流动控制台创建的_API_Key
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash
```

登录后也可在 **设置 → 大模型** 里填写网关地址、模型名和 API Key，保存到本机 `data/llm.json`（已 gitignore）。系统里保存过的设置优先于 `.env`；接口不会把完整密钥再读出来。`.env` 仍可作为备选，改完后需重启进程。

启动后访问 `/api/health`，看到 `llm: true` 和对应模型名即表示配置已加载。API Key 只保存在本机，不要填写进 README、源码或提交记录。

| 变量 | 含义 | 示例 |
|---|---|---|
| `LLM_BASE_URL` | OpenAI 兼容网关 | `http://127.0.0.1:8000/v1` |
| `LLM_API_KEY` | 模型密钥 | 留空则按网关要求 |
| `LLM_MODEL` | 模型名 | 按你的网关填写 |
| `RADAR_LLM` | `1` 启用模型；`0` 退回启发式 | `1` |
| `FEISHU_APP_ID` | 飞书自建应用 App ID | `cli_xxx` |
| `FEISHU_APP_SECRET` | 飞书自建应用 App Secret | **不要入库** |
| `FEISHU_RECEIVE_ID_TYPE` | 接收人类型 | `email` 或 `open_id` |
| `FEISHU_RECEIVE_ID` | 接收人 ID / 邮箱 | |
| `FEISHU_RECEIVE_MOBILE` | 手机号登录时换 open_id | |
| `FEISHU_MODE` | 飞书通道：`mock` 只写站内通知；`developer` 才走真实飞书 | 默认 `mock` |
| `FEISHU_INBOX` | 飞书入站对话；配好 App ID/Secret 后默认开启 | `1`；`0` 关闭 |
| `FEISHU_INBOX_USER` | 匹配不到 open_id 时落到的内部账号 | `bob` |
| `FEISHU_PROGRESS_DELAY` | 飞书回复超过多少秒时先显示自然的处理中提示 | `1.2`；`0` 关闭 |
| `FEISHU_VERIFICATION_TOKEN` | HTTP 事件回调校验；长连接可不填 | |
| `FEISHU_WEBHOOK_URL` | 群自定义机器人 webhook | 一对一应用机器人优先时可不填 |
| `FEISHU_SECRET` | 群机器人签名密钥 | 未开签名则留空 |
| `RADAR_HOST` | HTTP 监听地址 | `127.0.0.1` 或 `0.0.0.0` |
| `PORT` | 端口 | `8765` |
| `RADAR_PUSH_THRESHOLD` | 自动推送分数阈值 | `78` |
| `RADAR_PUSH_LIMIT` | 单次刷新最多即时推送数 | `3` |
| `RADAR_FEED_LIMIT` | 每位用户保留的推荐条数 | `30` |
| `RADAR_OBSERVE_MINUTES` | 后台主动观察间隔（分钟） | `60` |
| `RADAR_OBSERVE_ON_START` | 启动后是否立即采集 | `1` |
| `ZHIHU_ACCESS_SECRET` | 知乎开放平台 Access Secret | 开启知乎站内搜索及微信公众号域名检索 |
| `ZHIHU_OPENAPI_BASE_URL` | 知乎开放平台地址 | 默认 `https://developer.zhihu.com` |
| `RADAR_PUSH_DRY_RUN=1` | 只生成文案，不真实发送 | `0` |
| `RADAR_REMIND_MINUTES` | 后台扫描到期提醒的间隔（分钟） | `1`；`0` 关闭循环（仍可按 `RADAR_REMIND_ON_START` 启动时扫一次） |
| `RADAR_REMIND_ON_START` | 启动数秒后立刻扫一遍提醒 | 默认 `1` |
| `MEMORYOS_ENABLED` | 尝试官方 MemoryOS | `0` |

`ingest` 显示 `pushed=0` 时，通常不是飞书坏了，而是没有内容达到 `RADAR_PUSH_THRESHOLD`，或该条已在 `data/pushed.json` 里记过。

---

## 接入知乎与微信公众号内容

项目通过知乎开放平台的授权 API 获取知乎内容，并使用开放平台全网搜索限定 `mp.weixin.qq.com` 域名获取微信公众号文章。项目不会抓取登录墙，也不会伪造文章或原文链接。

### 1. 获取 Access Secret

1. 打开 [知乎开放平台](https://developer.zhihu.com/)，创建应用并开通知乎搜索相关能力。
2. 在应用凭据页面取得 Access Secret。
3. 两种配置方式（任选其一）：
   - **.env 配置**：写入本机 `.env`，重启生效。
   - **界面配置**：登录后打开 **设置 → 知乎 API**，填入 Secret Key 并保存，即时生效。密钥保存在 `data/users/<id>/zhihu.json`，接口不回显完整密钥。

界面配置优先于 `.env`。两者均未配置时，知乎和公众号来源自动跳过。

```env
ZHIHU_ACCESS_SECRET=你的_Access_Secret
# 通常不需要修改
ZHIHU_OPENAPI_BASE_URL=https://developer.zhihu.com
```

### 2. 配置观察主题

知乎和公众号来源位于 `sources.json`：

- `kind: "zhihu_search"`：知乎站内搜索。
- `kind: "global_search"`：全网搜索；公众号来源必须保留 `filter: "host==\"mp.weixin.qq.com\""` 和 `allowed_hosts` 校验。
- `searches`：可配置多个独立主题。系统逐个查询、按真实 URL 去重，再限制最终条数。
- `max`：该来源一次最多进入候选池的条数。

### 3. 验证

```powershell
python -m radar ingest
```

成功时终端会显示本轮抓取数、工作/个人推荐数和飞书推送结果。页面「我的关注」可管理来源状态，「为你推荐」可按知乎、公众号、论文、GitHub、博客、产品动态和新闻筛选。

如果知乎或公众号为空，依次检查：Access Secret 是否有效、应用能力是否开通、查询词是否过窄、来源的 `allowed_hosts` 是否正确。不要用示例链接填充空结果。

---

## 网络代理（可选）

arXiv、HuggingFace 等源在国内可能无法直连。项目内置代理支持，在 `.env` 中配置即可：

```env
# 所有源都走代理
RADAR_PROXY=http://127.0.0.1:7890

# 或仅指定源走代理（逗号分隔源 id）
RADAR_PROXY=http://127.0.0.1:7890
RADAR_PROXY_SOURCES=arxiv-memory-agent,hf-blog
```

未配置代理时，被墙源会自动跳过，国内源（量子位、36氪等）正常工作。

---

## 接入飞书

推荐「一对一应用机器人」做个人秘书私聊。群自定义机器人适合临时通知群。

飞书接入分为两种能力：

| 模式 | 当前状态 | 说明 |
|---|---|---|
| Agent 主动推送到飞书 | 已支持 | 高相关内容、手动测试消息发送给指定用户 |
| 在飞书中向 Agent 发消息并获得回复 | 已支持 | `python -m radar serve` 会拉起飞书长连接；也可走 `POST /api/feishu/event` |

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
FEISHU_MODE=developer
RADAR_PUSH_THRESHOLD=78
RADAR_PUSH_LIMIT=3
RADAR_FEED_LIMIT=30
RADAR_OBSERVE_MINUTES=60
RADAR_OBSERVE_ON_START=1
# 在 https://developer.zhihu.com/ 申请，密钥只保存在本机，不提交 Git
ZHIHU_ACCESS_SECRET=
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

账号设置页不会回显已保存的 App Secret。点击“保存并验证”后，页面会真实校验 App ID、Secret 和接收人，并显示成功或具体失败原因。

### 飞书内与 Agent 对话

`serve` 启动后会用 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 建立飞书长连接。你在飞书里给机器人发「你好」，会走和网页工作台同一套对话（会话 id 为 `feishu`），回复发回同一条私聊。长连接依赖 `lark-oapi`：

```powershell
pip install -r requirements.txt
```

发件人按顺序匹配：已绑定的飞书 `open_id` → 账号设置里的接收邮箱 / open_id → `.env` 的 `FEISHU_RECEIVE_ID` → `FEISHU_INBOX_USER`。个人使用时建议在 `.env` 写上 `FEISHU_INBOX_USER=bob`（或你的登录名）。

权限管理页面先点击蓝色 **开通权限**，再搜索权限；页面顶部搜索框只过滤已经开通的权限。可通过“批量处理 → 批量导入权限”导入：

```json
{
  "scopes": {
    "tenant": [
      "im:message:send_as_bot",
      "im:message.p2p_msg:readonly",
      "contact:user.id:readonly"
    ],
    "user": []
  }
}
```

然后进入 **事件与回调**：

1. 选择“使用长连接接收事件”。本机开发推荐长连接，不需要公网 HTTPS 回调地址。
2. 添加事件 `im.message.receive_v1`（接收消息）。
3. 如果还要支持群聊 `@机器人`，增加 `im:message.group_at_msg:readonly`。
4. 创建新版本、发布，并确保应用可用范围包含目标用户。

配置完成后重启 `python -m radar serve`。日志出现 `[feishu-inbox] 长连接已启动` 即可在飞书里对话。没有公网 HTTPS 时用长连接；若走 HTTP 回调，把请求指到 `POST /api/feishu/event`（无需登录），并填写 `FEISHU_VERIFICATION_TOKEN`。

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
├── Conversation    radar/conversation.py + radar/agent.py
├── Tool Registry   radar/agent_tools.py
├── Chat Storage    radar/conversation_store.py + radar/conversation_profile.py
├── Retrieve        radar/retrieve.py（按问题召回记忆）
├── Proactive       radar/proactive.py
├── Collector       radar/ingest.py + sources.json
├── Intelligence    radar/intelligence.py
├── Memory          radar/user_memory.py + radar/memory_os.py
├── Work Memory     radar/work_memory.py（任务 / 备忘 / 提醒）
├── Office Skills   radar/skills/（捕捉、拆解、提醒、日报周报、项目跟踪）
├── Reminders       radar/reminders/（到点扫描、上下文文案、飞书投递）
├── Recommendation  radar/recommender.py
├── Push            radar/channels.py + radar/feishu.py + radar/feishu_inbox.py
├── Knowledge       收藏 → LLM 分类 → 知识库 → 手动调整
├── Workspace       radar/workspace.py
└── HTTP            radar/routes.py + radar/server.py
```

| 路径 | 职责 |
|---|---|
| `radar/ingest.py` | 采集与去重 |
| `radar/intelligence.py` | 中文摘要、分类、标签 |
| `radar/user_memory.py` | 画像、兴趣权重、项目、行为 |
| `radar/retrieve.py` | 按当前问题召回记忆，而不是整包塞进提示词 |
| `radar/recommender.py` | 召回打分与 LLM 重排 |
| `radar/pipeline.py` | 串起整条链路；Skill 只经这里写数据 |
| `radar/work_memory.py` | 待办、事件、备忘、提醒账本 |
| `radar/skills/` | 办公 Skill：捕捉 / 拆解 / 提醒 / 报告 / 项目跟踪 |
| `radar/reminders/` | 定时扫描、截止前提醒、飞书与站内投递 |
| `radar/workspace.py` | 工作台账本 |
| `radar/settings_zhihu.py` | 知乎 API 密钥管理（界面配置，存本机） |
| `radar/feishu.py` | 飞书推送（含按 `open_id` 私聊） |
| `radar/feishu_inbox.py` | 飞书长连接收消息并回同一会话 |
| `radar/routes.py` | HTTP 路由表 |
| `radar/server.py` | HTTP 工作台 + API |
| `web/` | 前端工作台 |
| `sources.json` | 订阅源 |
| `env.example` | 环境变量模板 |
| `data/` | 本地画像、工作记忆、`llm.json`，**不入库** |

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
