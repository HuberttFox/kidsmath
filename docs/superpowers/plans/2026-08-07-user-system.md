# kidsmath 用户系统（P-A）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户系统真实化：自建账号密码 + session 认证、历史配置自动记录、保存配置、参数 JSON 导入导出（纯表单零 JS），SQLite 存储，登录即全功能。

**Architecture:** 新增 `db.py`（sqlite3 模块单例 + Lock，WAL）与 `auth.py`（pbkdf2 哈希 + session cookie）。FastAPI 中间件注入 `request.state.user`（模板零改动访问登录态），仅 `/user/*` 门禁。快照统一为 `_as_query(cfg)` 去 seed 的 JSON；保存应用/导入/历史重生成全部 302 到 `/?query`（index 已支持回填）。

**Tech Stack:** Python 3.11+、FastAPI、内置 sqlite3/hashlib/secrets（零新依赖）、Jinja2、Playwright（dev）。

## Global Constraints

- 零新 Python 依赖（认证用 hashlib/secrets，存储用内置 sqlite3）
- 门禁仅 `/user/*`；`/member/*` 占位公开；`/api/config/export` 允许未登录
- 快照 = `_as_query(cfg)` **去 seed**（与"换一批"一致）；`config_json` 同格式
- CSRF：非 GET/HEAD 请求 Origin 缺失放行、host 不匹配 403
- Cookie：HttpOnly + SameSite=Lax；**Secure 仅 `request.url.scheme == "https"`**；过期 30 天；DB 存 token SHA-256
- 登录错误统一文案"用户名或密码错误"（防枚举）；用户名 trim 后 2-32 字符；密码 ≥6
- IDOR：所有按 id 操作 `WHERE id=? AND user_id=?` + 404 兜底
- 历史每用户上限 200 条（插入裁剪）；sessions 登录时清过期
- `POST /generate` 历史记录 try/except 隔离（DB 故障不影响出题）
- 所有新页面/文案走 i18n zh+en（`auth.*`/`history.*`/`saved.*`/`config.*` 键组）
- sw.js 缓存版本 v3（白名单化：仅 `/`、`/product`、`/static/*` 运行时缓存，排除 `/user/*`、`/login`、`/register`、`/api/*`、`/generate`、`/download.*`）
- 现有 197 条 pytest 记录（176 个 def test）保持绿（2 处断言按 §10 更新）
- 每任务 TDD + commit

---

### Task 1: db.py 数据层

**Files:**
- Create: `src/mathgen/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `configure(path: str | None = None) -> None`（设置 DB 路径并重置连接，测试用）
  - `get_conn() -> sqlite3.Connection`（模块单例 + threading.Lock + WAL + busy_timeout=5000）
  - `create_user(username: str, password_hash: str) -> int`
  - `get_user_by_name(username: str) -> dict | None`
  - `get_user_by_id(uid: int) -> dict | None`
  - `create_session(token_hash: str, user_id: int, expires_at: str) -> None`
  - `get_user_by_token_hash(token_hash: str) -> dict | None`（含过期检查）
  - `delete_session(token_hash: str) -> None`
  - `cleanup_sessions(now: str) -> None`（删 expires_at < now）
  - `add_history(user_id: int, config_json: str) -> None`（含 200 条裁剪）
  - `list_history(user_id: int) -> list[dict]`
  - `delete_history(user_id: int, hid: int) -> bool`
  - `add_saved(user_id: int, name: str, config_json: str) -> int`
  - `list_saved(user_id: int) -> list[dict]`
  - `get_saved(user_id: int, sid: int) -> dict | None`
  - `rename_saved(user_id: int, sid: int, name: str) -> bool`
  - `delete_saved(user_id: int, sid: int) -> bool`

- [ ] **Step 1: 写失败测试** `tests/test_db.py`

```python
import sqlite3
import pytest
import mathgen.db as db


@pytest.fixture()
def d(tmp_path):
    db.configure(str(tmp_path / "t.db"))
    yield
    db.configure(None)


def test_configure_and_tables(d):
    conn = db.get_conn()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "sessions", "config_history", "saved_configs"} <= tables


def test_user_crud(d):
    uid = db.create_user("家长", "hash1")
    assert db.get_user_by_name("家长")["id"] == uid
    assert db.get_user_by_name("家长")["password_hash"] == "hash1"
    assert db.get_user_by_id(uid)["username"] == "家长"
    assert db.get_user_by_name("不存在") is None


def test_duplicate_username_raises(d):
    db.create_user("a", "h")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("a", "h")


def test_sessions(d):
    uid = db.create_user("u", "h")
    db.create_session("tokhash", uid, "2099-01-01T00:00:00")
    assert db.get_user_by_token_hash("tokhash")["username"] == "u"
    assert db.get_user_by_token_hash("bad") is None
    db.create_session("exp", uid, "2000-01-01T00:00:00")
    assert db.get_user_by_token_hash("exp") is None  # 过期
    db.delete_session("tokhash")
    assert db.get_user_by_token_hash("tokhash") is None
    db.cleanup_sessions("2001-01-01T00:00:00")
    assert db.get_user_by_token_hash("exp") is None


def test_history_cap_200(d):
    uid = db.create_user("u", "h")
    for i in range(205):
        db.add_history(uid, f'{{"n": {i}}}')
    rows = db.list_history(uid)
    assert len(rows) == 200
    assert rows[0]["config_json"] == '{"n": 204}'  # 最新优先


def test_history_delete_owner_scoped(d):
    uid1 = db.create_user("u1", "h")
    uid2 = db.create_user("u2", "h")
    hid = db.add_history(uid1, "{}")
    assert not db.delete_history(uid2, hid)  # 跨用户 404
    assert db.delete_history(uid1, hid)


def test_saved_ops(d):
    uid = db.create_user("u", "h")
    sid = db.add_saved(uid, "卷A", "{}")
    assert db.get_saved(uid, sid)["name"] == "卷A"
    assert db.rename_saved(uid, sid, "卷B")
    assert db.get_saved(uid, sid)["name"] == "卷B"
    assert not db.delete_saved(uid + 1, sid)
    assert db.delete_saved(uid, sid)
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_db.py -v` — FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 db.py**

```python
"""SQLite 数据层：用户/会话/历史配置/保存配置。模块单例连接 + Lock。"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_DB = Path("data/kidsmath.db")
HISTORY_CAP = 200
SESSION_DAYS = 30

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_path: str | None = None


def configure(path: str | None = None) -> None:
    """设置数据库路径并重建连接（None = 默认/重置）。测试隔离用。"""
    global _conn, _path
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
        _path = path
        if path is not None:
            get_conn()


def _resolve_path() -> str:
    env = os.environ.get("KIDSMATH_DB")
    if env:
        return env
    p = _path or str(DEFAULT_DB)
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    return p


def get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            conn = sqlite3.connect(_resolve_path(), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            _init_tables(conn)
            _conn = conn
        return _conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
      token_hash TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL REFERENCES users(id),
      expires_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS config_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      config_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS saved_configs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      config_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_history_user ON config_history(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_saved_user ON saved_configs(user_id);
    """)
    conn.commit()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_user(username: str, password_hash: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, now_iso()))
    conn.commit()
    return cur.lastrowid


def get_user_by_name(username: str) -> dict | None:
    row = get_conn().execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE username=?",
        (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(uid: int) -> dict | None:
    row = get_conn().execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE id=?",
        (uid,)).fetchone()
    return dict(row) if row else None


def create_session(token_hash: str, user_id: int, expires_at: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, expires_at))
    conn.commit()


def get_user_by_token_hash(token_hash: str) -> dict | None:
    row = get_conn().execute(
        "SELECT u.id, u.username, u.password_hash, u.created_at "
        "FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash=? AND s.expires_at > ?",
        (token_hash, now_iso())).fetchone()
    return dict(row) if row else None


def delete_session(token_hash: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
    conn.commit()


def cleanup_sessions(now: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    conn.commit()


def add_history(user_id: int, config_json: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO config_history (user_id, config_json, created_at) VALUES (?, ?, ?)",
        (user_id, config_json, now_iso()))
    conn.execute(
        "DELETE FROM config_history WHERE id NOT IN ("
        "SELECT id FROM config_history WHERE user_id=? "
        "ORDER BY created_at DESC, id DESC LIMIT ?) AND user_id=?",
        (user_id, HISTORY_CAP, user_id))
    conn.commit()


def list_history(user_id: int) -> list[dict]:
    rows = get_conn().execute(
        "SELECT id, config_json, created_at FROM config_history "
        "WHERE user_id=? ORDER BY created_at DESC, id DESC",
        (user_id,)).fetchall()
    return [dict(r) for r in rows]


def delete_history(user_id: int, hid: int) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM config_history WHERE id=? AND user_id=?", (hid, user_id))
    conn.commit()
    return cur.rowcount > 0


def add_saved(user_id: int, name: str, config_json: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO saved_configs (user_id, name, config_json, created_at) "
        "VALUES (?, ?, ?, ?)", (user_id, name, config_json, now_iso()))
    conn.commit()
    return cur.lastrowid


def list_saved(user_id: int) -> list[dict]:
    rows = get_conn().execute(
        "SELECT id, name, config_json, created_at FROM saved_configs "
        "WHERE user_id=? ORDER BY created_at DESC, id DESC",
        (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_saved(user_id: int, sid: int) -> dict | None:
    row = get_conn().execute(
        "SELECT id, name, config_json, created_at FROM saved_configs "
        "WHERE id=? AND user_id=?", (sid, user_id)).fetchone()
    return dict(row) if row else None


def rename_saved(user_id: int, sid: int, name: str) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "UPDATE saved_configs SET name=? WHERE id=? AND user_id=?",
        (name, sid, user_id))
    conn.commit()
    return cur.rowcount > 0


def delete_saved(user_id: int, sid: int) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM saved_configs WHERE id=? AND user_id=?", (sid, user_id))
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_db.py -v` — 全 PASS

- [ ] **Step 5: Commit**

`git add -A && git commit -m "feat: SQLite 数据层（用户/会话/历史/保存，200 条裁剪）"`

---

### Task 2: auth.py（哈希 + 会话 + cookie + CSRF）

**Files:**
- Create: `src/mathgen/auth.py`
- Modify: `src/mathgen/web.py`（中间件：注入 request.state.user + CSRF 检查）
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces:
  - `hash_password(pw: str) -> str`（`pbkdf2_sha256$200000$<salt hex>$<hash hex>`）
  - `verify_password(pw: str, stored: str) -> bool`（hmac.compare_digest）
  - `new_session_token() -> tuple[str, str]`（(cookie 值, sha256 摘要)）
  - `COOKIE_NAME = "kidsmath_session"`、`SESSION_DAYS = 30`
- web.py 中间件：`request.state.user`（None 或 dict）；非 GET/HEAD 且 Origin 存在且 host 不匹配 → 403

- [ ] **Step 1: 写失败测试** `tests/test_auth.py`

```python
import hashlib
import mathgen.auth as auth


def test_hash_roundtrip():
    h = auth.hash_password("secret123")
    assert h.startswith("pbkdf2_sha256$200000$")
    assert auth.verify_password("secret123", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("secret123", "garbage")


def test_hash_salted_unique():
    assert auth.hash_password("x") != auth.hash_password("x")


def test_token_pair():
    cookie, h = auth.new_session_token()
    assert len(cookie) >= 32
    assert h == hashlib.sha256(cookie.encode()).hexdigest()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_auth.py -v` — FAIL

- [ ] **Step 3: 实现 auth.py**

```python
"""认证：pbkdf2 密码哈希 + 会话 token。"""
from __future__ import annotations

import hashlib
import hmac
import secrets

ITERATIONS = 200_000
COOKIE_NAME = "kidsmath_session"
SESSION_DAYS = 30


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", pw.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def new_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()
```

- [ ] **Step 4: web.py 中间件（注入 user + CSRF）**

在 `app` 定义后追加：
```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import mathgen.auth as auth
from mathgen import db as db_mod


class UserAndCSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.user = None
        token = request.cookies.get(auth.COOKIE_NAME)
        if token:
            try:
                request.state.user = db_mod.get_user_by_token_hash(
                    hashlib.sha256(token.encode()).hexdigest())
            except Exception:
                request.state.user = None
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin:
                from urllib.parse import urlparse
                if urlparse(origin).hostname != request.url.hostname:
                    from fastapi.responses import PlainTextResponse
                    return PlainTextResponse("请求来源不合法", status_code=403)
        return await call_next(request)


app.add_middleware(UserAndCSRFMiddleware)
```
（import hashlib 加在 web.py 顶部；db 引用 db_mod 避免与 web 内局部名冲突）

- [ ] **Step 5: CSRF/中间件测试**

`tests/test_auth.py` 追加：
```python
from fastapi.testclient import TestClient
from mathgen.web import app

client = TestClient(app)


def test_csrf_origin_mismatch_blocked():
    r = client.post("/generate", data={"grade": "1"},
                    headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_csrf_missing_origin_allowed():
    r = client.post("/generate", data={"grade": "1", "count": "3"})
    assert r.status_code == 200


def test_csrf_same_origin_allowed():
    r = client.post("/generate", data={"grade": "1", "count": "3"},
                    headers={"origin": "http://testserver"})
    assert r.status_code == 200
```

- [ ] **Step 6: 回归 + 提交**

Run: `uv run pytest tests/test_auth.py tests/test_web.py -q` — 全绿（注意：现有 POST 测试不带 Origin → 放行 ✓）
Commit: `git add -A && git commit -m "feat: 认证基础（pbkdf2/会话 token/CSRF 中间件）"`

---

### Task 3: 认证端点 + 登录/注册页面 + 门禁 + 登录态导航

**Files:**
- Create: `src/mathgen/templates/login.html`、`register.html`
- Modify: `src/mathgen/web.py`、`src/mathgen/i18n.py`、`src/mathgen/templates/base.html`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: Task 1/2 全部接口；`db.get_user_by_name/create_user/create_session/delete_session/cleanup_sessions`
- Produces: `POST /api/register|login|logout`、`GET /api/me`、`GET /login|register`；门禁 helper；i18n `auth.*` 键组

- [ ] **Step 1: i18n 键组（zh+en）**

```python
# UI_ZH 追加：
"auth.login": "登录",
"auth.register": "注册",
"auth.logout": "退出登录",
"auth.username": "用户名",
"auth.password": "密码",
"auth.password2": "确认密码",
"auth.no_account": "还没有账号？去注册",
"auth.has_account": "已有账号？去登录",
"auth.error_invalid": "用户名或密码错误",
"auth.error_username_taken": "用户名已存在",
"auth.error_password_short": "密码至少 6 位",
"auth.error_username_invalid": "用户名需 2-32 个字符",
"auth.error_required": "请填写用户名和密码",
"auth.back": "返回首页",
# UI_EN 对应：
"auth.login": "Log in",
"auth.register": "Sign up",
"auth.logout": "Log out",
"auth.username": "Username",
"auth.password": "Password",
"auth.password2": "Confirm password",
"auth.no_account": "No account? Sign up",
"auth.has_account": "Have an account? Log in",
"auth.error_invalid": "Invalid username or password",
"auth.error_username_taken": "Username already exists",
"auth.error_password_short": "Password must be at least 6 characters",
"auth.error_username_invalid": "Username must be 2-32 characters",
"auth.error_required": "Please fill in username and password",
"auth.back": "Back to home",
```

- [ ] **Step 2: 写失败测试（追加 tests/test_auth.py）**

```python
def _register(username="家长", password="secret123"):
    return client.post("/api/register", data={"username": username, "password": password},
                       follow_redirects=False)


def test_register_and_me():
    r = _register()
    assert r.status_code == 302
    assert client.get("/api/me").json()["username"] == "家长"


def test_register_duplicate():
    _register()
    r = _register()
    assert r.status_code == 200
    assert "用户名已存在" in r.text


def test_register_short_password():
    r = _register(password="123")
    assert "密码至少 6 位" in r.text


def test_register_blank_username():
    r = _register(username="   ")
    assert "用户名需 2-32 个字符" in r.text


def test_login_logout():
    _register()
    r = client.post("/api/login", data={"username": "家长", "password": "secret123"},
                    follow_redirects=False)
    assert r.status_code == 302 and "kidsmath_session" in r.headers.get("set-cookie", "")
    r2 = client.post("/api/login", data={"username": "家长", "password": "wrong"})
    assert "用户名或密码错误" in r2.text  # 统一文案
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_gate_user_redirects_to_login():
    r = client.get("/user/history", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


def test_member_pages_public():
    assert client.get("/member/timer").status_code == 200


def test_login_next_consumed():
    _register()
    r = client.post("/api/login?next=/user/saved",
                    data={"username": "家长", "password": "secret123"},
                    follow_redirects=False)
    assert r.headers["location"] == "/user/saved"
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_auth.py -q` — FAIL（端点 404）

- [ ] **Step 4: web.py 端点实现**

```python
from urllib.parse import urlparse, urlencode, parse_qs
import hashlib
import mathgen.auth as auth
from mathgen import db as db_mod

SAFE_NEXT_PREFIXES = ("/", "/user", "/member")


def _safe_next(path: str | None) -> str | None:
    if path and path.startswith(SAFE_NEXT_PREFIXES) and not path.startswith("//"):
        return path
    return None


@app.post("/api/register", response_class=HTMLResponse)
async def api_register(request: Request):
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    if not (2 <= len(username) <= 32):
        return templates.TemplateResponse(request, "register.html",
            {"lang": _lang(request), "error": t("auth.error_username_invalid", _lang(request))})
    if len(password) < 6:
        return templates.TemplateResponse(request, "register.html",
            {"lang": _lang(request), "error": t("auth.error_password_short", _lang(request))})
    if db_mod.get_user_by_name(username):
        return templates.TemplateResponse(request, "register.html",
            {"lang": _lang(request), "error": t("auth.error_username_taken", _lang(request))})
    uid = db_mod.create_user(username, auth.hash_password(password))
    cookie, thash = auth.new_session_token()
    db_mod.create_session(thash, uid, _expires_iso())
    resp = RedirectResponse(_safe_next(request.query_params.get("next")) or "/", status_code=302)
    resp.set_cookie(auth.COOKIE_NAME, cookie, httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", max_age=60 * 60 * 24 * 30)
    return resp


def _expires_iso():
    from datetime import datetime, timedelta
    return (datetime.now() + timedelta(days=auth.SESSION_DAYS)).isoformat(timespec="seconds")


@app.post("/api/login", response_class=HTMLResponse)
async def api_login(request: Request):
    lang = _lang(request)
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    user = db_mod.get_user_by_name(username) if username else None
    if not user or not auth.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(request, "login.html",
            {"lang": lang, "error": t("auth.error_invalid", lang)})
    db_mod.cleanup_sessions(db_mod.now_iso())
    cookie, thash = auth.new_session_token()
    db_mod.create_session(thash, user["id"], _expires_iso())
    resp = RedirectResponse(_safe_next(request.query_params.get("next")) or "/", status_code=302)
    resp.set_cookie(auth.COOKIE_NAME, cookie, httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", max_age=60 * 60 * 24 * 30)
    return resp


@app.post("/api/logout")
async def api_logout(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        db_mod.delete_session(hashlib.sha256(token.encode()).hexdigest())
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/api/me")
async def api_me(request: Request):
    user = request.state.user
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse({"username": user["username"]})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(request, "login.html",
        {"lang": lang, "ui_json": _UI_JSON, "error": None})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(request, "register.html",
        {"lang": lang, "ui_json": _UI_JSON, "error": None})
```
（导入 RedirectResponse/JSONResponse：`from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response`）

- [ ] **Step 5: 门禁：/user 三个路由**

`/user`、`/user/history`、`/user/saved` 开头加：
```python
    user = request.state.user
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
```
（注意：占位版 /user 相关路由在 Task 4/5 重写为真实页；门禁先加，页面先保留占位渲染，Task 4/5 替换内容）

- [ ] **Step 6: login.html / register.html 模板**

`login.html`（extends base，nav 留空，内容：表单 username/password + error + 注册链接）：
```html
{% extends "base.html" %}
{% block title %}{{ t("auth.login", lang) }} - mathgen{% endblock %}
{% block nav %}{% endblock %}
{% block content %}
<section class="auth-card">
  <h1 data-i18n="auth.login">{{ t("auth.login", lang) }}</h1>
  {% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}
  <form method="post" action="/api/login">
    <label class="field-group"><span class="field-label" data-i18n="auth.username">{{ t("auth.username", lang) }}</span>
      <input type="text" name="username" required></label>
    <label class="field-group"><span class="field-label" data-i18n="auth.password">{{ t("auth.password", lang) }}</span>
      <input type="password" name="password" required></label>
    <div class="actions"><button class="btn" type="submit" data-i18n="auth.login">{{ t("auth.login", lang) }}</button></div>
  </form>
  <p class="hint"><a href="/register" data-i18n="auth.no_account">{{ t("auth.no_account", lang) }}</a></p>
</section>
{% endblock %}
```
`register.html` 同构（username/password/password2 + 校验提示 + 登录链接）。

- [ ] **Step 7: base.html 登录态导航**

header-controls 前替换 userEntry 为登录态：
```html
      {% if user %}
      <span class="user-chip">{{ user.username }}</span>
      <form method="post" action="/api/logout" class="inline-form">
        <button class="pill-toggle" type="submit" data-i18n="auth.logout">{{ t("auth.logout", lang) }}</button>
      </form>
      {% else %}
      <a class="pill-toggle" href="/login" data-i18n="auth.login">{{ t("auth.login", lang) }}</a>
      {% endif %}
```
（Jinja 里 `user` 从 `request.state.user` 取——模板中 base.html 用 `{% set user = request.state.user %}` 或直接 `{% if request.state.user %}`；Jinja 访问 request.state.user 可用 `request.state.user`）

- [ ] **Step 8: CSS .auth-card / .user-chip + 回归 + 提交**

```css
.auth-card { max-width: 400px; margin: 3em auto; background: var(--card-bg);
  border: 1.5px solid var(--border); border-radius: var(--radius-lg);
  padding: 1.6em; box-shadow: var(--shadow-sm); }
.auth-card h1 { text-align: center; margin-bottom: 1em; }
.user-chip { display: inline-flex; align-items: center; padding: .4em 1em;
  border-radius: var(--radius-md); background: var(--mint-soft);
  font-weight: 700; color: var(--text); }
```
Run: `uv run pytest tests/test_auth.py tests/test_web.py -q` — 全绿
Commit: `git add -A && git commit -m "feat: 认证端点/登录注册页/门禁/登录态导航"`

---

### Task 4: 历史配置（真实页 + generate 挂钩）

**Files:**
- Modify: `src/mathgen/web.py`（generate 挂钩、/user/history 真实化、删除端点）
- Modify: `src/mathgen/i18n.py`（history.* 键）
- Test: `tests/test_userdata.py`

**Interfaces:**
- Consumes: `db.add_history/list_history/delete_history`；`_snapshot_json(cfg)`
- Produces: web.py helper `_snapshot_json(cfg: Config) -> str`（`_as_query(cfg)` 去 seed → json.dumps，tuple→list 安全）；`POST /api/history/{hid}/delete`；302 回填 helper `_redirect_to_config(snapshot: dict) -> RedirectResponse`（`/?` + urlencode）

- [ ] **Step 1: i18n 键（zh+en）**

```python
# UI_ZH：
"history.title": "历史配置",
"history.empty": "还没有生成记录，去出题吧",
"history.regenerate": "重新生成",
"history.delete": "删除",
"history.summary": "{n} 题 · {ops} · {ranges}",
"history.time": "{time}",
"history.confirm_delete": "确定删除这条记录？",
# UI_EN：
"history.title": "History",
"history.empty": "No history yet — go generate!",
"history.regenerate": "Regenerate",
"history.delete": "Delete",
"history.summary": "{n} questions · {ops} · {ranges}",
"history.time": "{time}",
"history.confirm_delete": "Delete this record?",
```

- [ ] **Step 2: 写失败测试** `tests/test_userdata.py`

```python
import json
import re
from fastapi.testclient import TestClient
from mathgen.web import app

client = TestClient(app)


def _login():
    client.post("/api/register", data={"username": "家长", "password": "secret123"})
```

def test_generate_records_history():
    _login()
    client.post("/generate", data={"grade": "2", "count": "3"})
    r = client.get("/user/history")
    assert r.status_code == 200
    assert "重新生成" in r.text
    assert "grade" in r.text  # 摘要含配置


def test_history_regenerate_redirects_without_seed():
    _login()
    client.post("/generate", data={"grade": "2", "count": "3", "seed": "7"})
    r = client.get("/user/history")
    m = re.search(r'href="/user/history/(\d+)/delete"', r.text)
    assert m
    # 重新生成按钮在表单 POST /api/history/{id}/regenerate
    r2 = client.post(f"/api/history/{m.group(1)}/regenerate", follow_redirects=False)
    assert r2.status_code == 302
    assert "seed" not in r2.headers["location"]
    assert "grade=2" in r2.headers["location"]


def test_delete_history_owner_scoped():
    _login()
    client.post("/generate", data={"grade": "1"})
    r = client.get("/user/history")
    m = re.search(r'href="/user/history/(\d+)/delete"', r.text)
    hid = m.group(1)
    assert client.post(f"/api/history/{hid}/delete").status_code == 302
    assert "history" not in client.get("/user/history").text or "还没有生成记录" in client.get("/user/history").text


def test_anonymous_generate_no_record_and_gate():
    client.post("/api/logout")
    client.post("/generate", data={"grade": "1", "count": "3"})
    r = client.get("/user/history", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]


def test_history_db_failure_does_not_break_generate(monkeypatch):
    _login()
    import mathgen.db as db
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(db, "add_history", boom)
    r = client.post("/generate", data={"grade": "1", "count": "3"})
    assert r.status_code == 200  # 出题主流程不受影响
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_userdata.py -q` — FAIL

- [ ] **Step 4: web.py 实现**

helpers（放在 `_as_query` 后）：
```python
def _snapshot_json(cfg: Config) -> str:
    q = {k: v for k, v in _as_query(cfg).items() if k != "seed"}
    return json.dumps(q, ensure_ascii=False)


def _redirect_to_config(snapshot: dict) -> RedirectResponse:
    return RedirectResponse("/?" + urlencode(snapshot), status_code=302)
```
generate_page 成功分支（`questions = generate(resolved)` 之后）：
```python
    if request.state.user:
        try:
            db_mod.add_history(request.state.user["id"], _snapshot_json(cfg))
        except Exception:
            pass
```
`/user/history` 真实化（替换占位分支，保留门禁）：
```python
@app.get("/user/history", response_class=HTMLResponse)
async def user_history(request: Request):
    lang = _lang(request)
    user = request.state.user
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    rows = db_mod.list_history(user["id"])
    items = []
    for row in rows:
        try:
            cfg = json.loads(row["config_json"])
        except Exception:
            cfg = {}
        items.append({
            "id": row["id"], "time": row["created_at"][:16].replace("T", " "),
            "summary": ", ".join(f"{k}={v}" for k, v in list(cfg.items())[:6]),
        })
    return templates.TemplateResponse(request, "user_history.html", {
        "lang": lang, "ui_json": _UI_JSON, "items": items,
        "app_mode": _app_mode(request)})


@app.post("/api/history/{hid}/regenerate")
async def history_regenerate(request: Request, hid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    row = db_mod.get_history(user["id"], hid)
    if not row:
        return RedirectResponse("/user/history", status_code=302)
    return _redirect_to_config(json.loads(row["config_json"]))


@app.post("/api/history/{hid}/delete")
async def history_delete(request: Request, hid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    db_mod.delete_history(user["id"], hid)
    return RedirectResponse("/user/history", status_code=302)
```
（需在 db.py 增加 `get_history(user_id, hid)`——返回单条；Task 1 补：`SELECT ... WHERE id=? AND user_id=?`。若 Task 1 已提交，本任务在 db.py 追加该函数 + 测试。）

`user_history.html` 模板（复用占位卡样式）：
```html
{% extends "base.html" %}
{% block title %}{{ t("history.title", lang) }} - mathgen{% endblock %}
{% block nav %}<a href="/user" data-i18n="user.title">{{ t("user.title", lang) }}</a>{% endblock %}
{% block content %}
<section class="placeholder-hero">
  <h1 class="placeholder-title" data-i18n="history.title">{{ t("history.title", lang) }}</h1>
</section>
<section class="placeholder-grid">
  {% for item in items %}
  <div class="placeholder-card">
    <h2>{{ item.summary }}</h2>
    <p>{{ item.time }}</p>
    <form method="post" action="/api/history/{{ item.id }}/regenerate" class="inline-form">
      <button class="btn btn-secondary btn-small" type="submit" data-i18n="history.regenerate">{{ t("history.regenerate", lang) }}</button>
    </form>
    <form method="post" action="/api/history/{{ item.id }}/delete" class="inline-form"
          onsubmit="return confirm('{{ t("history.confirm_delete", lang) }}')">
      <button class="btn btn-secondary btn-small" type="submit" data-i18n="history.delete">{{ t("history.delete", lang) }}</button>
    </form>
  </div>
  {% else %}
  <p class="hint" style="text-align:center" data-i18n="history.empty">{{ t("history.empty", lang) }}</p>
  {% endfor %}
</section>
{% endblock %}
```
（/user 用户中心页后续 Task 5 一并真实化：放用户名 + 两个入口卡 + 导出/导入说明。）

- [ ] **Step 5: db.py 补 get_history**

追加：
```python
def get_history(user_id: int, hid: int) -> dict | None:
    row = get_conn().execute(
        "SELECT id, config_json, created_at FROM config_history "
        "WHERE id=? AND user_id=?", (hid, user_id)).fetchone()
    return dict(row) if row else None
```
+ tests/test_db.py 追加 `test_get_history_owner_scoped`。

- [ ] **Step 6: 回归 + 提交**

Run: `uv run pytest tests/test_db.py tests/test_userdata.py tests/test_auth.py -q` — 全绿
Commit: `git add -A && git commit -m "feat: 历史配置（自动记录/真实页/重生成/删除）"`

---

### Task 5: 保存配置

**Files:**
- Modify: `src/mathgen/web.py`、`src/mathgen/i18n.py`、`src/mathgen/templates/preview.html`、`src/mathgen/templates/user_saved.html`（新）、`src/mathgen/templates/user.html`（新，用户中心）
- Test: `tests/test_userdata.py`

**Interfaces:**
- Consumes: `db.add_saved/list_saved/rename_saved/delete_saved/get_saved`；`_snapshot_json`；`_redirect_to_config`
- Produces: `POST /api/saved`（cfg_fields 隐藏表单 + name）、`POST /api/saved/{sid}/apply|rename|delete`；`/user/saved` 真实页；预览页"保存配置"按钮

- [ ] **Step 1: i18n 键（zh+en）**

```python
# UI_ZH：
"saved.title": "保存配置",
"saved.empty": "还没有保存的配置",
"saved.name": "配置名称",
"saved.save": "保存配置",
"saved.apply": "应用",
"saved.rename": "重命名",
"saved.delete": "删除",
"saved.saved_ok": "已保存",
"saved.confirm_delete": "确定删除？",
"user.center": "用户中心",
"user.hi": "你好，{name}",
"user.history_go": "查看历史配置",
"user.saved_go": "查看保存配置",
# UI_EN：
"saved.title": "Saved configs",
"saved.empty": "No saved configs yet",
"saved.name": "Config name",
"saved.save": "Save config",
"saved.apply": "Apply",
"saved.rename": "Rename",
"saved.delete": "Delete",
"saved.saved_ok": "Saved",
"saved.confirm_delete": "Delete?",
"user.center": "Account",
"user.hi": "Hi, {name}",
"user.history_go": "View history",
"user.saved_go": "View saved configs",
```

- [ ] **Step 2: 写失败测试（追加 tests/test_userdata.py）**

```python
def test_save_from_preview_and_apply():
    _login()
    r = client.post("/generate", data={"grade": "2", "count": "3"})
    m = re.search(r'<form method="post" action="/api/saved" class="inline-form">(.*?)</form>',
                  r.text, re.S)
    assert m, "预览页应有保存配置表单"
    import html as _h
    data = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', _h.unescape(m.group(1))))
    data["name"] = "卷A"
    r2 = client.post("/api/saved", data=data, follow_redirects=False)
    assert r2.status_code == 302 and "/user/saved" in r2.headers["location"]
    page = client.get("/user/saved")
    assert "卷A" in page.text


def test_saved_apply_redirects():
    _login()
    client.post("/api/saved", data={"grade": "3", "count": "5", "name": "卷B"})
    page = client.get("/user/saved")
    m = re.search(r'action="/api/saved/(\d+)/apply"', page.text)
    assert m
    r = client.post(f"/api/saved/{m.group(1)}/apply", follow_redirects=False)
    assert r.status_code == 302 and "grade=3" in r.headers["location"]
    assert "seed" not in r.headers["location"]


def test_saved_anonymous_redirects_login():
    client.post("/api/logout")
    r = client.post("/api/saved", data={"grade": "1", "name": "x"}, follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]


def test_saved_rename_delete():
    _login()
    client.post("/api/saved", data={"grade": "1", "name": "旧名"})
    page = client.get("/user/saved")
    m = re.search(r'action="/api/saved/(\d+)/rename"', page.text)
    sid = m.group(1)
    client.post(f"/api/saved/{sid}/rename", data={"name": "新名"})
    assert "新名" in client.get("/user/saved").text
    client.post(f"/api/saved/{sid}/delete")
    assert "旧名" not in client.get("/user/saved").text
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_userdata.py -q` — FAIL

- [ ] **Step 4: web.py 端点**

```python
@app.post("/api/saved")
async def api_saved(request: Request):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    data = {k: v for k, v in form.items() if k != "name"}
    name = (form.get("name") or "未命名").strip() or "未命名"
    try:
        cfg = _config_from_form(data)
        resolve(cfg)
    except ConfigError as e:
        return templates.TemplateResponse(request, "index.html",
            _index_context(dict(form), error_text(e.code, e.params, _lang(request)),
                           _lang(request), _app_mode(request)))
    db_mod.add_saved(user["id"], name, _snapshot_json(cfg))
    return RedirectResponse("/user/saved", status_code=302)


@app.post("/api/saved/{sid}/apply")
async def saved_apply(request: Request, sid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    row = db_mod.get_saved(user["id"], sid)
    if not row:
        return RedirectResponse("/user/saved", status_code=302)
    return _redirect_to_config(json.loads(row["config_json"]))


@app.post("/api/saved/{sid}/rename")
async def saved_rename(request: Request, sid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    db_mod.rename_saved(user["id"], sid, (form.get("name") or "").strip() or "未命名")
    return RedirectResponse("/user/saved", status_code=302)


@app.post("/api/saved/{sid}/delete")
async def saved_delete(request: Request, sid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    db_mod.delete_saved(user["id"], sid)
    return RedirectResponse("/user/saved", status_code=302)
```

- [ ] **Step 5: 模板**

`preview.html` 操作区（换一批/修改参数前，登录时显示）：
```html
  {% if user %}
  <form method="post" action="/api/saved" class="inline-form">
    {% for k, v in cfg_fields.items() %}<input type="hidden" name="{{ k }}" value="{{ v }}">{% endfor %}
    <input type="text" name="name" placeholder="{{ t('saved.name', lang) }}" class="save-name">
    <button type="submit" class="btn btn-secondary btn-small" data-i18n="saved.save">{{ t("saved.save", lang) }}</button>
  </form>
  {% endif %}
```
（Jinja `user` = `request.state.user`；preview 上下文无需传 user——模板直接读 `request.state.user`。）

`user_saved.html`（与 user_history.html 同构：summary + 应用/重命名表单（inline name input + submit）/删除）。
`user.html`（用户中心：`user.hi` 问候 + 两张入口卡链接 history/saved + 导出说明链接回首页）。

- [ ] **Step 6: 回归 + 提交**

Run: `uv run pytest tests/test_userdata.py tests/test_auth.py -q` — 全绿
Commit: `git add -A && git commit -m "feat: 保存配置（预览保存/列表/应用/重命名/删除）"`

---

### Task 6: 参数导入导出（formaction + file）

**Files:**
- Modify: `src/mathgen/web.py`、`src/mathgen/i18n.py`、`src/mathgen/templates/index.html`
- Test: `tests/test_userdata.py`

**Interfaces:**
- Produces: `POST /api/config/export`（FormData → JSON 附件）、`POST /api/config/import`（file → 302 回填 / 失败渲染 error）；index 两个按钮

- [ ] **Step 1: i18n 键（zh+en）**

```python
# UI_ZH：
"config.export": "导出配置",
"config.import": "导入配置",
"config.import_ok": "配置已导入",
"config.import_error": "配置导入失败：{err}",
"config.import_format": "请选择 kidsmath-config.json 文件",
# UI_EN：
"config.export": "Export config",
"config.import": "Import config",
"config.import_ok": "Config imported",
"config.import_error": "Import failed: {err}",
"config.import_format": "Choose a kidsmath-config.json file",
```

- [ ] **Step 2: 写失败测试**

```python
def test_export_returns_json_attachment():
    r = client.post("/api/config/export", data={"grade": "2", "count": "3", "seed": "9"})
    assert r.status_code == 200
    assert 'attachment; filename="kidsmath-config.json"' in r.headers["content-disposition"]
    data = json.loads(r.text)
    assert data["version"] == 1
    assert data["config"]["grade"] == "2"
    assert "seed" not in data["config"]


def test_import_roundtrip_and_redirect():
    r = client.post("/api/config/export", data={"grade": "3", "count": "5",
                                                "left_factor_range": "10-99"})
    files = {"file": ("kidsmath-config.json", r.content, "application/json")}
    r2 = client.post("/api/config/import", files=files, follow_redirects=False)
    assert r2.status_code == 302
    assert "grade=3" in r2.headers["location"]
    assert "left_factor_range=10-99" in r2.headers["location"]


def test_import_invalid_json_errors():
    files = {"file": ("bad.json", b"not json", "application/json")}
    r = client.post("/api/config/import", files=files)
    assert r.status_code == 200
    assert "配置导入失败" in r.text


def test_import_invalid_field_errors():
    files = {"file": ("bad.json", json.dumps({"version": 1,
            "config": {"grade": "9"}}).encode(), "application/json")}
    r = client.post("/api/config/import", files=files)
    assert "年级" in r.text
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_userdata.py -q` — FAIL

- [ ] **Step 4: web.py 端点**

```python
@app.post("/api/config/export")
async def config_export(request: Request):
    form = dict(await request.form())
    cfg = _config_from_form(form)   # ConfigError 时？导出容错：失败回表单并提示
    q = _snapshot_json(cfg)
    return Response(q, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="kidsmath-config.json"'})


@app.post("/api/config/import", response_class=HTMLResponse)
async def config_import(request: Request):
    lang = _lang(request)
    form = await request.form()
    file = form.get("file")
    if file is None or not file.filename:
        return templates.TemplateResponse(request, "index.html",
            _index_context({}, t("config.import_format", lang), lang, _app_mode(request)))
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("config"), dict):
            raise ValueError("bad payload")
        cfg = _config_from_form(payload["config"])
        resolve(cfg)
    except (ValueError, ConfigError, UnicodeDecodeError) as e:
        msg = e.message if isinstance(e, ConfigError) else str(e)
        return templates.TemplateResponse(request, "index.html",
            _index_context({}, t("config.import_error", lang, err=msg), lang, _app_mode(request)))
    return _redirect_to_config({k: v for k, v in _as_query(cfg).items() if k != "seed"})
```

- [ ] **Step 5: index.html 按钮**

主表单 actions 区（生成按钮后）：
```html
    <button type="submit" formaction="/api/config/export" class="btn btn-secondary" data-i18n="config.export">{{ t("config.export", lang) }}</button>
```
高级参数区末尾独立导入表单：
```html
    <form method="post" action="/api/config/import" enctype="multipart/form-data" class="import-form">
      <label class="field-group">
        <span class="field-label" data-i18n="config.import">{{ t("config.import", lang) }}</span>
        <input type="file" name="file" accept="application/json,.json">
      </label>
      <button class="btn btn-secondary btn-small" type="submit" data-i18n="config.import">{{ t("config.import", lang) }}</button>
    </form>
```
CSS 补 `.import-form { display: flex; gap: .8em; align-items: center; flex-wrap: wrap; }`。

- [ ] **Step 6: 回归 + 提交**

Run: `uv run pytest tests/test_userdata.py tests/test_web.py -q` — 全绿
Commit: `git add -A && git commit -m "feat: 参数导入导出（formaction 导出/file 导入 302 回填）"`

---

### Task 7: 运维（Docker 卷 / SW v3 / 文档）

**Files:**
- Modify: `Dockerfile`、`compose.yaml`、`src/mathgen/static/sw.js`、`docs/deploy.md`、`README.md`
- Test: `tests/test_web.py`（SW 版本断言更新）

- [ ] **Step 1: Dockerfile**

`RUN useradd -m mathgen && chown -R mathgen:mathgen /app` 后追加：
```dockerfile
RUN mkdir -p /data && chown -R mathgen:mathgen /data
```

- [ ] **Step 2: compose.yaml**

```yaml
    environment:
      - KIDSMATH_DB=/data/kidsmath.db
    volumes:
      - mathgen-data:/data
...
volumes:
  mathgen-data:
```

- [ ] **Step 3: sw.js v3 白名单**

```js
const CACHE = 'kidsmath-v3';
const ASSETS = [ /* 原静态列表不变 */ ];
const CACHEABLE = ['/static/'];

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  const isStatic = CACHEABLE.some((p) => url.pathname.startsWith(p));
  if (url.pathname === '/' || url.pathname === '/product' || isStatic) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (res.ok && url.origin === location.origin) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    })));
  }
});
```

- [ ] **Step 4: 测试更新**

`tests/test_web.py::test_pwa_assets`：断言 `"kidsmath-v3" in sw`（原 v2 断言改）；`/user/history` 不缓存语义由 fetch 白名单保证（sw.js 文本断言 `CACHEABLE` 含 `/static/` 且无 `/user`）。

- [ ] **Step 5: docs + README**

deploy.md：改"无数据落盘"为数据说明（`/data/kidsmath.db` 卷；备份=备份卷）；补环境变量 `KIDSMATH_DB` 表；认证/历史/保存功能段。
README：功能清单追加用户系统/历史/保存/导入导出；Docker 段提卷。

- [ ] **Step 6: 回归 + 提交**

Run: `uv run pytest tests/test_web.py -q`
Commit: `git add -A && git commit -m "chore: Docker 数据卷/SW v3 白名单/文档更新"`

---

### Task 8: 测试收尾 + 全量验证

**Files:**
- Modify: `tests/test_web.py`（test_placeholder_pages、test_all_data_i18n_keys 更新）
- Test: 全量

- [ ] **Step 1: 更新 test_placeholder_pages**

`/user`、`/user/history`、`/user/saved` 从占位断言移除（已真实化）——改为：
```python
def test_placeholder_pages():
    for path in ("/member", "/member/timer", "/member/pomodoro",
                 "/member/errors", "/member/review"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "coming-soon" in r.text, path
    # /user 系已真实化：未登录 → 跳登录
    r = client.get("/user/history", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]
```

- [ ] **Step 2: 更新 test_all_data_i18n_keys_exist_in_both_langs**

pages 列表追加 `/login`、`/register`、登录后 `/user/history`、`/user/saved`（加一个 helper 先注册登录再取页）：
```python
    client.post("/api/register", data={"username": "t", "password": "secret123"})
    pages = [client.get("/").text, client.get("/product").text,
             client.get("/login").text, client.get("/register").text,
             client.get("/user/history").text, client.get("/user/saved").text,
             client.post("/generate", data={"grade": "1", "count": "3"}).text]
```

- [ ] **Step 3: 全量验证**

Run: `uv run pytest -q` — 全绿（197 记录 + 新增）
Run: `node /home/hubert/.config/opencode/skills/impeccable/scripts/detect.mjs --json src/mathgen/templates/*.html src/mathgen/static/style.css` — 零发现或记录
Run: `docker build -q -t mathgen:latest .` + 起容器：`curl /healthz`、`/login` 200、`/api/me` 401、`/member/timer` 200、生成后 `ls /data/kidsmath.db` 存在
Commit: `git add -A && git commit -m "test: 用户系统测试收尾与全量验证" && git push`

---

## Self-Review 记录

- Spec 覆盖：§2 数据层（T1）、§3 认证（T2/T3）、§4 CSRF（T2）、§5 历史（T4）、§6 保存（T5）、§7 导入导出（T6）、§8 前端集成（T3/T5）、§9 运维（T7）、§10 测试（各任务 + T8）、§12 影响面全覆盖。
- 命名一致性：`db_mod.*`/`auth.*` 跨任务统一；`_snapshot_json`/`_redirect_to_config` 在 T4 定义、T5/T6 复用；`request.state.user` 全站统一；i18n 键前缀 `auth.*/history.*/saved.*/config.*/user.*`。
- 已知依赖：T4 需 db.py 补 `get_history`（T1 后追加，标注）；T3 门禁先加占位保留、T4/T5 替换内容；模板里 `user` 一律从 `request.state.user` 读取（不新增上下文参数）。
