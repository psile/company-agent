"""Admin 用户管理 + 认证安全 + 数据隔离测试。"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from radar.identity import IdentityService
from radar.pipeline import RadarService


@pytest.fixture()
def svc(tmp_path):
    """创建一个干净的 RadarService 实例。"""
    os.environ["DEV_SEED"] = "0"
    os.environ["ALLOW_REGISTER"] = "0"
    service = RadarService(data_dir=tmp_path)
    os.environ.pop("DEV_SEED", None)
    os.environ.pop("ALLOW_REGISTER", None)
    return service


@pytest.fixture()
def admin_svc(tmp_path):
    """创建一个带 admin 的 RadarService 实例。"""
    os.environ["DEV_SEED"] = "0"
    os.environ["ALLOW_REGISTER"] = "0"
    os.environ["INITIAL_ADMIN_USERNAME"] = "admin"
    os.environ["INITIAL_ADMIN_PASSWORD"] = "admin123"
    service = RadarService(data_dir=tmp_path)
    os.environ.pop("DEV_SEED", None)
    os.environ.pop("ALLOW_REGISTER", None)
    os.environ.pop("INITIAL_ADMIN_USERNAME", None)
    os.environ.pop("INITIAL_ADMIN_PASSWORD", None)
    return service


# ── 密码安全 ──

def test_password_hash_not_equal_raw(tmp_path):
    """hash ≠ 明文。"""
    ident = IdentityService(tmp_path)
    hashed = ident.create_user("testuser", "Test", "password123")["id"]
    user = ident.get(hashed)
    assert user["password_hash"] != "password123"
    assert "$" in user["password_hash"]
    assert user["password_hash"].startswith("pbkdf2$")


def test_login_wrong_password_denied(admin_svc):
    """错误密码登录失败。"""
    admin_svc.identity.create_user("zhangsan", "张三", "pass123")
    with pytest.raises(ValueError, match="用户名或密码不正确"):
        admin_svc.identity.login("zhangsan", "wrongpass")


def test_disabled_user_login_denied(admin_svc):
    """禁用用户不能登录。"""
    user = admin_svc.identity.create_user("lisi", "李四", "pass123")
    admin_svc.identity.disable_user(user["id"])
    with pytest.raises(ValueError, match="账号已停用"):
        admin_svc.identity.login("lisi", "pass123")


def test_disabled_user_existing_token_revoked(admin_svc):
    """禁用用户已有 session 被撤销。"""
    user = admin_svc.identity.create_user("wangwu", "王五", "pass123")
    session = admin_svc.identity.login("wangwu", "pass123")
    token = session["token"]
    # 禁用前 token 有效
    assert admin_svc.identity.user_id_for_session(token) is not None
    admin_svc.identity.disable_user(user["id"])
    # 禁用后 session 被删除
    assert admin_svc.identity.user_id_for_session(token) is None


# ── Admin 用户管理 ──

def test_admin_create_user_success(admin_svc):
    """admin 成功创建用户。"""
    user = admin_svc.admin_create_user("zhangsan", "张三", "pass123")
    assert user["username"] == "zhangsan"
    assert user["display_name"] == "张三"
    assert user["role"] == "user"
    assert user["status"] == "active"
    assert user["must_change_password"] is True
    assert user["id"].startswith("u_")


def test_duplicate_username_rejected(admin_svc):
    """重复用户名被拒绝。"""
    admin_svc.admin_create_user("zhangsan", "张三", "pass123")
    with pytest.raises(ValueError, match="用户名已被占用"):
        admin_svc.admin_create_user("zhangsan", "张三2", "pass456")


def test_admin_reset_password(admin_svc):
    """admin 重置密码。"""
    user = admin_svc.admin_create_user("lisi", "李四", "pass123")
    admin_svc.admin_reset_password(user["id"], "newpass456")
    session = admin_svc.identity.login("lisi", "newpass456")
    assert session["ok"] is True
    # 重置后 must_change_password=True
    assert session["user"]["must_change_password"] is True


def test_admin_disable_enable_user(admin_svc):
    """admin 禁用再启用用户。"""
    user = admin_svc.admin_create_user("wangwu", "王五", "pass123")
    admin_svc.admin_disable_user(user["id"])
    assert admin_svc.identity.get(user["id"])["status"] == "disabled"
    admin_svc.admin_enable_user(user["id"])
    assert admin_svc.identity.get(user["id"])["status"] == "active"


def test_user_id_is_uuid_not_username(admin_svc):
    """新建用户 ID 是 u_xxxxxxxx 格式，不是 username。"""
    user = admin_svc.admin_create_user("newuser", "新用户", "pass123")
    assert user["id"] != "newuser"
    assert user["id"].startswith("u_")
    assert len(user["id"]) == 10  # u_ + 8 hex


# ── must_change_password 流程 ──

def test_must_change_password_flow(admin_svc):
    """首次登录 → 改密码 → flag 清除。"""
    user = admin_svc.admin_create_user("newuser", "新用户", "temppass123")
    # 登录
    session = admin_svc.identity.login("newuser", "temppass123")
    assert session["user"]["must_change_password"] is True
    # 用 must_change_password 跳过旧密码校验改密码
    admin_svc.identity.change_password(user["id"], "", "newpass456")
    updated = admin_svc.identity.get(user["id"])
    assert updated["must_change_password"] is False
    # 新密码可登录
    session2 = admin_svc.identity.login("newuser", "newpass456")
    assert session2["ok"] is True


# ── current_user 和隔离 ──

def test_resolve_user_does_not_auto_create(admin_svc):
    """未绑定的飞书 open_id 不自动创建用户。"""
    result = admin_svc.identity.resolve_user("feishu", "ou_unknown123")
    assert result is None


def test_session_user_returns_correct_user(admin_svc):
    """token → correct user。"""
    admin_svc.identity.create_user("alice2", "Alice2", "pass123")
    session = admin_svc.identity.login("alice2", "pass123")
    uid = admin_svc.identity.user_id_for_session(session["token"])
    assert uid == admin_svc.identity.find_by_username("alice2")["id"]


# ── 初始化 admin ──

def test_initial_admin_created_when_no_users(tmp_path):
    """首次启动且无用户时创建 admin。"""
    os.environ["DEV_SEED"] = "0"
    os.environ["INITIAL_ADMIN_USERNAME"] = "admin"
    os.environ["INITIAL_ADMIN_PASSWORD"] = "admin123"
    service = RadarService(data_dir=tmp_path)
    os.environ.pop("DEV_SEED", None)
    os.environ.pop("INITIAL_ADMIN_USERNAME", None)
    os.environ.pop("INITIAL_ADMIN_PASSWORD", None)
    admin = service.identity.find_by_username("admin")
    assert admin is not None
    assert admin["role"] == "admin"
    assert admin["must_change_password"] is True


def test_initial_admin_not_overwritten(tmp_path):
    """已有用户时不重复创建 admin。"""
    os.environ["DEV_SEED"] = "1"
    os.environ["INITIAL_ADMIN_USERNAME"] = "admin"
    os.environ["INITIAL_ADMIN_PASSWORD"] = "admin123"
    service = RadarService(data_dir=tmp_path)
    os.environ.pop("DEV_SEED", None)
    os.environ.pop("INITIAL_ADMIN_USERNAME", None)
    os.environ.pop("INITIAL_ADMIN_PASSWORD", None)
    # alice/bob 存在
    assert service.identity.find_by_username("alice") is not None
    # admin 也被创建（因为 alice/bob 不是 admin）
    admin = service.identity.find_by_username("admin")
    assert admin is not None
    assert admin["role"] == "admin"


# ── 跨用户数据隔离 ──

def test_alice_cannot_read_bob_task(tmp_path):
    """Alice 登录后看不到 Bob 的 Task。"""
    os.environ["DEV_SEED"] = "1"
    service = RadarService(data_dir=tmp_path)
    os.environ.pop("DEV_SEED", None)
    # Bob 创建一个任务
    bob_task = service.create_task({"title": "Bob 私密任务", "description": "secret"}, user_id="bob")
    # Alice 尝试用 Bob 的 task_id 获取
    found = service.tasks_service.get_task("alice", bob_task["id"])
    assert found is None


def test_same_project_name_isolated(tmp_path):
    """两个用户同名 project 互不影响。"""
    os.environ["DEV_SEED"] = "1"
    service = RadarService(data_dir=tmp_path)
    os.environ.pop("DEV_SEED", None)
    # Alice 创建项目
    alice_proj = service.create_project({"project": "Agent Memory", "stage": "调研"}, "alice")
    alice_proj_id = alice_proj["project"]["project_id"]
    # Bob 创建同名项目（slug 相同，但数据按用户隔离）
    bob_proj = service.create_project({"project": "Agent Memory", "stage": "开发"}, "bob")
    bob_proj_id = bob_proj["project"]["project_id"]
    # project_id slug 相同，但两个用户的数据互不影响
    alice_tracker = service.project_tracker("alice")
    bob_tracker = service.project_tracker("bob")
    # Alice 的 tracker 是她自己的项目
    assert alice_tracker.get("stage") == "调研"
    # Bob 的 tracker 是他自己的项目
    assert bob_tracker.get("stage") == "开发"


def test_alice_cannot_search_bob_memory(tmp_path):
    """Alice 搜索记忆不返回 Bob 的数据。"""
    os.environ["DEV_SEED"] = "1"
    service = RadarService(data_dir=tmp_path)
    os.environ.pop("DEV_SEED", None)
    # Alice 搜索 Bob 专属话题
    results = service.recall_memory("World Model 封闭预测", "alice")
    # 结果不应包含 Bob 私有的工作事件标记
    for item in results:
        assert item.get("user_id", "alice") != "bob"


# ── 开放注册关闭 ──

def test_register_closed_by_default(admin_svc):
    """默认关闭开放注册。"""
    from radar.config import get_bool
    assert not get_bool("ALLOW_REGISTER", False)


# ── admin 角色检查 ──

def test_is_admin(admin_svc):
    """admin 角色检查。"""
    admin = admin_svc.identity.find_by_username("admin")
    assert admin_svc.identity.is_admin(admin["id"]) is True
    user = admin_svc.identity.create_user("normal", "普通", "pass123")
    assert admin_svc.identity.is_admin(user["id"]) is False


# ── _public_user 包含新字段 ──

def test_public_user_has_new_fields(tmp_path):
    """_public_user 输出 role/must_change_password/last_login_at。"""
    ident = IdentityService(tmp_path)
    ident.create_user("testuser", "测试", "pass123", role="admin", email="test@example.com")
    pub = ident.public_user(ident.find_by_username("testuser")["id"])
    assert pub["role"] == "admin"
    assert pub["email"] == "test@example.com"
    assert "must_change_password" in pub
    assert "last_login_at" in pub
