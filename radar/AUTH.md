# 认证与用户管理

正式的用户账号体系：管理员创建账号 → 用户登录 → 全链路 user_id 隔离。

---

## 快速开始

### 1. 开发模式（带 alice / bob 种子）

```env
DEV_SEED=1
ALLOW_REGISTER=1
```

启动后自动创建 `alice / alice123`、`bob / bob123`，可直接登录体验。

### 2. 生产模式（管理员创建账号）

```env
DEV_SEED=0
ALLOW_REGISTER=0
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=<你的初始密码>
```

首次启动自动创建管理员账号。登录后会提示修改初始密码。

---

## 认证流程

```
用户名 + 密码
    ↓
IdentityService.login()
    ↓ PBKDF2-HMAC-SHA256 校验（120,000 轮）
    ↓ 检查 status != disabled
    ↓ 更新 last_login_at
    ↓
Session Token（secrets.token_urlsafe(32)，14 天有效）
    ↓
返回 { token, user }
    ↓
前端存 localStorage("radar_session")
后续请求: Authorization: Bearer <token>
```

### Token 传递方式

| 方式 | 场景 |
|------|------|
| `Authorization: Bearer <token>` | 前端 SPA（主要方式） |
| `Cookie: radar_session=<token>` | 浏览器自动携带（HttpOnly, SameSite=Lax） |

后端 `_session_token()` 两种方式都认。

---

## 用户数据模型

```python
{
    "id": "u_xxxxxxxx",           # 系统内部稳定 ID（UUID）
    "username": "zhangsan",       # UNIQUE, 3-32 位, 字母开头
    "display_name": "张三",
    "email": "",                  # 可选
    "password_hash": "pbkdf2$...", # PBKDF2, 不存明文
    "avatar_url": "",
    "role": "user",               # admin | user
    "status": "active",           # active | disabled
    "must_change_password": false, # 首次登录强制改密码
    "last_login_at": "2026-...",
    "created_at": "2026-...",
    "updated_at": "2026-..."
}
```

存储位置：`data/identity/users.json`

---

## 密码安全

| 项目 | 实现 |
|------|------|
| 算法 | PBKDF2-HMAC-SHA256 |
| 迭代 | 120,000 轮 |
| 盐 | 16 字节随机 hex（每用户独立） |
| 存储 | `pbkdf2${salt}${digest}` |
| 校验 | `hmac.compare_digest()` 防时序攻击 |
| 日志 | 不输出密码、hash、token |

---

## API

### 认证 API

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/auth/login` | 无 | 登录，返回 token + user |
| `POST` | `/api/auth/logout` | 无 | 登出，清除 session |
| `GET` | `/api/auth/me` | user | 获取当前用户信息（含 role） |
| `POST` | `/api/auth/register` | 无 | 注册（`ALLOW_REGISTER=1` 时开放） |
| `PUT` | `/api/account/password` | user | 修改密码 |

### Admin 用户管理 API

所有 Admin API 需要 `role == "admin"`，普通用户访问返回 403。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/admin/users` | 列出所有用户 |
| `POST` | `/api/admin/users` | 创建用户 |
| `PATCH` | `/api/admin/users/{user_id}` | 更新用户信息 |
| `POST` | `/api/admin/users/{user_id}/reset-password` | 重置密码 |
| `POST` | `/api/admin/users/{user_id}/disable` | 禁用用户 |
| `POST` | `/api/admin/users/{user_id}/enable` | 启用用户 |

### 创建用户

```json
POST /api/admin/users
{
  "username": "zhangsan",
  "display_name": "张三",
  "password": "initial123",
  "email": "zhangsan@example.com",
  "role": "user"
}
```

创建后 `must_change_password=true`，用户首次登录需修改密码。

### 禁用用户

禁用后：
- 已有 session token 全部撤销
- 不能再登录
- 不删除任何数据（Task / Memory / Knowledge 保留）

---

## 路由鉴权级别

```python
routes.py 中 Match(auth, fn, params)

auth="none"  → 公开接口（登录、注册、飞书回调、健康检查）
auth="user"  → 需要登录（所有业务 API）
auth="admin" → 需要管理员（用户管理 API）
```

server.py 中的认证逻辑：

```python
def _user(self) -> str:
    # 从 token 解析 user_id，检查 status != disabled
    ...

def _admin(self) -> str:
    uid = self._user()
    if not service.identity.is_admin(uid):
        raise PermissionError("admin required")
    return uid
```

---

## user_id 隔离原则

**所有 API 的 user_id 来自 session token，不来自请求体。**

```
请求 → Authorization: Bearer <token>
     → _session_token() → user_id_for_session()
     → current_user.id
     → handler(uid) → Service(uid) → Repository(uid)
```

创建/更新操作中的 `body.user_id` 字段会被 `data.pop("user_id", None)` 丢弃。Repository 层有二次校验：`data.get("user_id") != user_id` 时抛异常。

---

## 飞书身份映射

```
飞书消息入站
    ↓
sender.open_id
    ↓
IdentityService.resolve_user("feishu", open_id)
    ↓ 查 identities.json
    ↓
internal user_id  (或 None → 消息被丢弃)
    ↓
Agent Core → Private Memory
```

- **不自动创建用户**：未绑定的 open_id 返回 None，消息被丢弃
- 一个 open_id 只能绑定一个 internal user
- 一个 internal user 可以绑定多个 open_id
- 管理员可在用户管理中手动绑定

---

## 前端

| 元素 | 说明 |
|------|------|
| 登录页 | 用户名 + 密码，无 alice/bob 切换按钮 |
| 首次改密码弹窗 | `must_change_password=true` 时显示 |
| 用户菜单 | 头像 + 姓名 + 退出 |
| 用户管理页 | 仅 admin 可见，在 设置 → 用户管理 |
| 401 处理 | 自动跳回登录页 |
| 403 处理 | 提示"需要管理员权限" |
| demo 提示 | `DEV_USER_SWITCHER=1` 时显示 alice/bob 提示 |

---

## 测试

```powershell
python -m pytest radar/tests/test_admin_auth.py -v
```

覆盖场景：密码安全、登录失败、禁用用户、admin CRUD、重复用户名、UUID ID、must_change_password 流程、跨用户数据隔离、飞书身份映射。
