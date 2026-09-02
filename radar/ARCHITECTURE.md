# 架构文档

面向开发者的代码架构说明。快速理解模块关系和数据流。

---

## 项目定位

**One Agent · Multi-user · Private Memory**

一个会上班的个人智能体：记住你，观察世界，在合适的时间主动把真正相关的信息送到你面前。

```
主动感知 Observe → 信息理解 Understand → 长期记忆 Memory
→ 个性化判断 Recommendation → 主动推送 Push → 用户反馈 Feedback
→ 记忆更新 Memory Update → 推荐持续进化 Evolve
```

---

## 目录结构

```
radar/
├── radar/                    # Python 包
│   ├── __main__.py           # CLI 入口（serve / ingest / push / feishu-test / feishu-inbox）
│   ├── config.py             # .env 加载 + get_bool/get_int/get_str
│   ├── server.py             # HTTP 服务器 + 路由分发 + 认证中间件
│   ├── routes.py             # 表驱动路由匹配（auth: none/user/admin）
│   ├── pipeline.py           # RadarService 核心编排：采集→理解→排序→推送→反馈
│   │
│   ├── identity.py           # 用户账号 + 密码 + Session + 外部身份绑定
│   ├── store.py              # LocalMemory（用户私有 JSON） + ContentPool（全局候选池）
│   ├── models.py             # RawItem / ScoredItem 数据模型
│   │
│   ├── ingest.py             # 采集器：arXiv / GitHub / RSS / 知乎 / 微信公众号
│   ├── intelligence.py        # LLM 理解：中文摘要 + 要点 + 影响 + 标签
│   ├── recommender.py         # 多因子排序（6 维加权）+ 四通道打散
│   ├── score.py              # 关键词命中率打分
│   ├── proactive.py           # 主动推送决策（8 因子加权）
│   │
│   ├─ user_memory.py         # 个人记忆：画像 / 兴趣权重 / 项目 / 行为反馈
│   ├── work_memory.py         # 工作记忆：Task / Event / Note / Reminder / Report
│   ├── memory_os.py           # 三层分层记忆（短/中/长期）
│   ├── retrieve.py            # 按问题召回记忆（词法 + 同义词扩展）
│   ├── workspace.py           # 工作台：Goals / Products / Push Settings / User Sources
│   │
│   ├── conversation.py        # 对话编排：session 管理 + 消息存储
│   ├── conversation_store.py  # 对话持久化（bounded context = 16 条）
│   ├── conversation_profile.py # 对话风格偏好
│   ├── agent.py               # IntentRouter（24 意图）+ ConversationAgent
│   ├── agent_tools.py         # ToolRegistry（17 个工具）
│   │
│   ├── channels.py            # 统一推送入口（App Bot → Inbox → Mock）
│   ├── feishu.py              # 飞书推送（OAuth + token 缓存 + 签名）
│   ├── feishu_inbox.py        # 飞书入站（长连接 + webhook）
│   ├── notify.py              # 站内通知
│   ├── interest.py            # 交互意图提取 + LLM 推送筛选
│   │
│   ├── core/                  # 核心服务层
│   │   ├── repositories.py    # Repository 抽象 + JsonRepository（强制 user_id 隔离）
│   │   ├── services.py        # TaskService / WorkEventService / WorkNoteService / ReminderService
│   │   └── schemas.py         # 领域 Schema + 枚举 + public_* 投影函数
│   │
│   ├── skills/                # 办公 Skill
│   │   ├── base.py            # AgentSkill 协议（can_handle + execute）
│   │   ├── catalog.py         # 技能目录（8 enabled + 4 coming_soon）
│   │   ├── task_capture/      # 从对话提取待办
│   │   ├── reminder/          # 智能醒 Skill
│   │   ├── report/            # 日报 / 周报生成
│   │   ├── work_summary/      # 工作总结（时间轴聚合）
│   │   └── project_tracker/   # 项目跟踪（快照 + 风险 + 进度）
│   │
│   ├── reminders/             # 定时提醒
│   │   ├── scheduler.py       # 后台定时扫描线程
│   │   ├── service.py         # 提醒评估（deadline 24h/3h + 进度 + 风险 + 晨报）
│   │   ├── schemas.py         # 时间解析（CST + 中文数字 + 自然语言）
│   │   └── context_builder.py # 提醒文案构建
│   │
│   ├── llm.py                 # LLM 调用（OpenAI 兼容，三层配置优先级）
│   ├── seeds.py               # Demo 种子用户（alice / bob）
│   ├── settings_zhihu.py      # 知乎 API 密钥管理
│   └── memory_bridge.py       # 可选外部记忆系统
│
├── web/                      # 前端 SPA
│   ├── index.html            # 页面结构 + 登录页 + 弹窗
│   ├── app.js                # 路由 + 状态 + API 调用 + 渲染
│   └── styles.css            # 样式
│
├── tests/                    # 测试（126 个，全通过）
│   ├── test_radar.py          # 核心管线（采集 / 排序 / 推送 / 飞书）
│   ├── test_admin_auth.py     # 认证 + 用户管理 + 数据隔离（20 个）
│   ├── test_auth.py           # 登录 / 注册 / 会话
│   ├── test_conversation.py   # 对话意图
│   ├── test_multiuser.py      # 多用户隔离
│   └── ...                    # 其他模块测试
│
├── sources.json              # 订阅源配置
├── env.example               # 环境变量模板
├── requirements.txt          # Python 依赖（lark-oapi）
├── pytest.ini                # 测试配置
└── Dockerfile                # 部署
```

---

## 核心数据流

### 推荐链路

```
ingest.py 采集 → pool/items.json（全局候选池）
                    ↓
intelligence.py LLM 理解 → 写回 item（摘要/标签/要点/影响）
                    ↓
recommender.py 逐用户排序 → data/users/<uid>/feeds.json
    排序权重: 语义 0.11 + 兴趣 0.36 + 项目 0.23 + 新鲜 0.12 + 质量 0.10 + 反馈 0.08
    四通道打散: work / industry / discovery / personal
                    ↓
proactive.py 主动推送决策 → channels.py → feishu.py / notify.py
                    ↓
用户反馈 → user_memory.apply_feedback() → 更新兴趣权重
```

### 对话链路

```
POST /api/chat { message, session_id }
    ↓
server.py _user() → current_user.id（从 token 解析）
    ↓
ConversationService.chat(uid, message, session_id)
    ↓
IntentRouter.route(message) → 24 种意图
    ↓ 正则优先，LLM 兜底
ConversationAgent.respond(intent, message, uid)
    ↓
ToolRegistry 调用 17 个工具 / Skills
    ↓
存 conversation_store → data/users/<uid>/conversations/
```

### 飞书消息链路

```
飞书用户发消息 → 长连接 / webhook
    ↓
feishu_inbox.handle_incoming()
    ↓
resolve_inbox_user(service, open_id)
    ↓ 查 identities.json
internal user_id（未绑定则丢弃）
    ↓
ConversationService.chat(uid, message, session_id="feishu")
    ↓
回复推回同一飞书私聊（open_id）
```

---

## 数据存储

### 存储方式

纯 JSON 文件，无外部数据库。所有数据在 `data/` 目录下。

### 用户隔离

```
data/
├── identity/
│   ├── users.json            # 用户账号（id / username / password_hash / role / status）
│   ├── identities.json       # 外部身份绑定（provider + external_id → user_id）
│   ├── channels.json         # 推送渠道绑定
│   └─ sessions.json         # 登录 Session Token
│
├── pool/
│   └── items.json            # 全局候选池（所有用户共享，设计如此）
│
└── users/
    ├── tasks.json            # ← 共享文件，靠记录内 user_id 字段隔离
    ├── work_events.json      # ← 同上
    ├── work_notes.json       # ← 同上
    ├── reminders.json        # ← 同上
    │
    └── <user_id>/            # ← 用户私有目录
        ├── profile.json
        ├── cards.json        # 收藏卡片
        ├── feeds.json        # 推荐流
        ├── events.json       # 行为事件
        ├── pushed.json       # 已推送去重
        ├── feishu.json       # 飞书配置
        ├── goals.json        # 目标
        ├── products.json     # 关注产品
        ├── push_settings.json # 推送偏好
        ├── user_sources.json # 自定义信息源
        ├── conversations/
        │   ├── sessions.json
        │   └── messages.json
        ├── memory/
        │   ├── profile.json
        │   ├── interests.json
        │   ├── project.json
        │   ├── projects.json
        │   └── behavior.json
        ├── memoryos/
        │   ├── short_term.json
        │   ├── mid_term.json
        │   └── long_term_user.json
        └── work/
            └── reports.json
```

### 隔离机制

| 层 | 机制 | 位置 |
|----|------|------|
| **路由层** | user_id 来自 session token，不从请求体取 | `server.py:56 _user()` |
| **Service 层** | 所有方法强制传 user_id | `core/services.py` |
| **Repository 层** | 所有 CRUD 带 user_id 过滤 + 二次校验 | `core/repositories.py:63-109` |
| **文件层** | 用户私有数据在 `data/users/<uid>/` 子目录 | `pipeline.py:117` |
| **写入防护** | `data.pop("user_id", None)` 丢弃请求体中的 user_id | `pipeline.py` 多处 |

---

## 关键类

| 类 | 文件 | 职责 |
|----|------|------|
| `RadarService` | `pipeline.py:44` | 核心编排，串起全链路 |
| `UserScope` | `pipeline.py:33` | 用户作用域（memory + workspace + work + notify） |
| `IdentityService` | `identity.py:23` | 用户账号 + 密码 + Session + 身份绑定 |
| `LocalMemory` | `store.py` | 用户私有 JSON 读写（profile/cards/feeds/events） |
| `ContentPool` | `store.py` | 全局候选池 |
| `UserMemory` | `user_memory.py` | 画像 / 兴趣权重 / 项目 / 行为反馈 |
| `WorkMemory` | `work_memory.py` | Task / Event / Note / Reminder / Report CRUD |
| `HierarchicalMemory` | `memory_os.py` | 三层记忆（短/中/长期） |
| `ConversationService` | `conversation.py` | 对话编排 + session 管理 |
| `IntentRouter` | `agent.py` | 意图路由（正则 + LLM） |
| `ToolRegistry` | `agent_tools.py` | 17 个工具注册 |
| `Workspace` | `workspace.py` | Goals / Products / Push Settings |
| `JsonRepository` | `core/repositories.py` | JSON 文件仓库（强制 user_id） |
| `Router` | `routes.py:15` | HTTP 路由匹配 |

---

## 推荐排序权重

```
总分 = 语义 × 0.11
     + 兴趣 × 0.36
     + 项目 × 0.23
     + 新鲜 × 0.12
     + 质量 × 0.10
     + 反馈 × 0.08
```

四通道分类（`content_lane`）：
- **work** — 聚焦当前项目和目标
- **industry** — 行业新闻、产品动态
- **discovery** — 值得一看的趣事
- **personal** — 个人推荐

`diversify_feed` 按 lane 配额打散，避免工作情报独占推荐流。

---

## 添加新功能

### 新增 API 端点

```python
# 1. 在 server.py 的 make_handler 中注册路由
add("POST", "/api/my-feature", "user", lambda h, uid, _p, _q, body: h._json(200, service.my_feature(body, uid)))

# 2. 在 pipeline.py 的 RadarService 中实现
def my_feature(self, payload: dict, user_id: str) -> dict:
    uid = self.identity.require(user_id)
    scope = self._scope(uid)
    # 操作 scope.memory / scope.work / scope.workspace
    ...
```

### 新增办公 Skill

```python
# 1. 在 radar/skills/ 下创建目录
# 2. 实现 AgentSkill 协议
class MySkill:
    def can_handle(self, intent: str) -> bool: ...
    def execute(self, ctx) -> dict: ...
# 3. 在 skills/catalog.py 中注册
```

### 新增订阅源

在 `sources.json` 中添加：

```json
{
  "id": "my-source",
  "name": "我的源",
  "kind": "rss",
  "url": "https://example.com/feed.xml",
  "max": 5,
  "channel": "industry"
}
```

支持的 kind：`arxiv` / `github_release` / `rss` / `zhihu_search` / `global_search`

---

## 测试

```powershell
# 全部测试
python -m pytest radar/tests/ -q

# 只跑认证测试
python -m pytest radar/tests/test_admin_auth.py -v

# 只跑核心管线
python -m pytest radar/tests/test_radar.py -v
```

126 个测试，覆盖：多用户隔离、内容管线、对话意图、办公技能、认证安全、飞书集成、LLM 配置。
