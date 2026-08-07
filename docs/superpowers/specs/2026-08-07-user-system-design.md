# kidsmath 用户系统 + SQLite + 参数导入导出（P-A）设计文档

- 日期: 2026-08-07
- 状态: 已确认（含两轮评审闭环）

## 1. 定位与目标

把现有占位页真实化：自建账号密码 + session 认证、历史配置自动记录、保存配置、参数 JSON 导入导出。数据存 SQLite（内置 sqlite3，零新依赖）。登录即全功能（无付费逻辑）。`/member/*` 保持占位公开（P-B 实现会员功能时再加门禁）。

## 2. 数据层 `src/mathgen/db.py`

sqlite3 内置，模块级连接 + WAL + busy_timeout，同步 def（FastAPI 线程池），SQL 全参数化。

```sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,          -- "pbkdf2_sha256$iter$salt$hash" 单串，迭代可升级
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,          -- cookie token 的 SHA-256 摘要
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS config_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  config_json TEXT NOT NULL,            -- 快照：_as_query(cfg) 去 seed 的 JSON
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saved_configs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  config_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

- **快照格式统一**：`config_json = _as_query(cfg)` 去 seed（与"换一批"一致，`web.py` `if k != "seed"` 逻辑）——重新生成出的是新题。历史/保存/导出三处共用。
- 历史**每用户上限 200 条**：插入后 `DELETE FROM config_history WHERE id NOT IN (SELECT id ... ORDER BY created_at DESC LIMIT 200) AND user_id=?`
- sessions 清理：登录时 `DELETE FROM sessions WHERE expires_at < now`（顺手清过期行）

连接：**模块单例连接 + `threading.Lock`**（sqlite3 默认 check_same_thread=False + WAL + busy_timeout）。

接口：`connect()`、`create_user/get_user_by_name`、`create_session/get_user_by_token/delete_session/cleanup_sessions`、`add_history/list_history/delete_history`、`add_saved/list_saved/delete_saved`、`get_saved`。所有按用户查询带 `user_id`。

## 3. 认证 `src/mathgen/auth.py` + web 集成

- 密码：`hashlib.pbkdf2_hmac('sha256', pw, salt, 200_000)`，存 `pbkdf2_sha256$200000$<salt hex>$<hash hex>`；校验用 `hmac.compare_digest`
- Session token：`secrets.token_urlsafe(32)`；cookie 值；**DB 存 token 的 SHA-256 摘要**（防 DB 泄露直接用 cookie）；**过期 30 天**（`expires_at = now + 30d`）
- Cookie：`kidsmath_session`，`HttpOnly` + `SameSite=Lax`；**`Secure` 仅当 `request.url.scheme == "https"`**（LAN http 可用）
- 端点：
  - `POST /api/register`（username/password）→ 校验：用户名 trim 后 2-32 字符、唯一；密码 ≥6 位；成功建用户 + 自动登录
  - `POST /api/login` → 统一文案"用户名或密码错误"（防枚举）；成功建 session + set cookie + **302 优先 next（仅白名单站内路径：`/`、`/user*`、`/member*` 前缀，防开放重定向），无 next 才回 `/?`**
  - `POST /api/logout` → 删 session + 清 cookie + 302
  - `GET /api/me` → `{"username": ...}` 或 401
- 页面：`GET /login`、`GET /register`（马卡龙表单页，复用 base.html，i18n 双语）；**失败渲染对应页 + error**（与导入失败一致），成功才 302
- 依赖 `current_user(request) -> User | None`：查 cookie → token SHA-256 → sessions → users
- **门禁：仅 `/user/*`**——未登录访问 `/user*` → 302 `/login?next=...`；`/member/*` 公开（占位）
- 未登录 POST `/api/saved`、`/api/history/*` → 302 `/login`（导出例外，见 §7）

## 4. CSRF 基础防护

中间件（或端点内检查）：非 GET/HEAD 请求：
- `Origin` 头缺失 → 放行（curl/测试/旧客户端）
- `Origin` 存在且 `origin.host != request.headers["host"]` → 403 中文
（反代场景 Host 头正确映射即可）

## 5. 历史配置

- `POST /generate` 成功后：登录用户 → `add_history`（**try/except 隔离**，DB 故障不影响出题主流程）
- `GET /user/history` 真实页：列表（时间 + 摘要：年级/题型/题数/运算符，从 config_json 渲染）+ 按钮：
  - "重新生成" → **302 `/?query`**（统一回填）
  - "删除" → `POST /api/history/{id}/delete`（`WHERE id=? AND user_id=?`，不存在 404 兜底）→ 302 回列表
- 未登录访问 `/user/history` → 302 `/login?next=/user/history`

## 6. 保存配置

- 预览页"保存配置"（登录后显示）：`<form method="post" action="/api/saved">` 复用 **cfg_fields 隐藏字段**（preview.html 已有，去 seed）+ 名称输入 → 302 回 `/user/saved`（未登录 → 302 /login）
- `GET /user/saved`：列表（名称 + 摘要 + 时间）+ 按钮：
  - "应用" → `POST /api/saved/{id}/apply` → **302 `/?query`**（统一回填）
  - "重命名"（名称 input + `POST /api/saved/{id}/rename`）
  - "删除" → `POST /api/saved/{id}/delete`（均 `WHERE id=? AND user_id=?` + 404）
- 全部表单零 JS（隐藏字段 POST + 302）

## 7. 参数导入导出（纯表单零 JS）

- **导出**（formaction 方案）：index 主表单内加 `<button type="submit" formaction="/api/config/export">导出配置</button>`——HTML5 formaction 让主表单直接 POST 导出端点，字段天然是**浏览器当前值**（服务端 `_config_from_form` 解析），零 JS 零复制 → 响应 `Content-Disposition: attachment; filename=kidsmath-config.json`，内容 `{"version": 1, "config": {<form 字段键值，去 seed>}}` → 浏览器直接下载。**导出允许未登录使用**（不涉个人数据）；仅保存/历史/导入保存路径门禁
- **导入**：index 高级参数区 `<input type="file" name="file">` + 隐藏 form 自动 submit 到 `POST /api/config/import` → 解析（版本/字段）→ `_config_from_form` + `resolve()` 校验：
  - **成功 → 302 `/?query`**（浏览器原生跟随，回填表单）
  - **失败 → 直接渲染 index.html + error**（与 `/generate` 错误路径一致，中文提示）
- 导出含全部可导出字段（grade/topic/operators/count/operand_count/ranges/result_range/carry/borrow/divisor_range/remainder/table/left_factor_range/right_factor_range/dividend_range/paren_weight/parentheses/columns/gap/answer_lines/answer_page/number_direction/show_numbers/lang/op_weights/sheets，去 seed）
- 导入字段格式 = 表单字段格式（`_as_query` 键名），天然 round-trip 对称

## 8. 前端集成

- `base.html`：userEntry（现有 `#userEntry` 链接）按登录态渲染——已登录显示用户名 + 登出；未登录显示"登录"。上下文加 `user`（current_user）
- 新页面（login/register/user/history/saved）全部走 base.html + i18n 双语（`auth.*`、`user.*` 键组）
- i18n 新增键：`auth.username`/`auth.password`/`auth.login`/`auth.register`/`auth.logout`/`auth.error_invalid`/`auth.error_username_taken`/`auth.error_password_short`/`auth.username_required`/`history.*`/`saved.*`/`config.export`/`config.import`/`config.import_error` 等 zh+en

## 9. 运维

- **Dockerfile**：`RUN mkdir -p /data && chown -R mathgen:mathgen /data`
- **compose.yaml**：`volumes: - mathgen-data:/data`（命名卷）
- **deploy.md**：改写"无数据落盘"→ 数据存 `/data` 卷（用户/历史/保存配置）；备份 = 备份卷
- **sw.js v3**：运行时缓存白名单化——仅缓存 `/`、`/product`、静态资源（css/js/fonts/icons）；排除 `/user/*`、`/login`、`/register`、`/api/*`、`/generate`、`/download.*`
- 数据库文件：env `KIDSMATH_DB` 可配置，默认 `data/kidsmath.db`（相对 CWD）
- **compose.yaml 必须显式 `environment: KIDSMATH_DB: /data/kidsmath.db`**（否则默认 `/app/data/` 与挂载的 `/data` 卷错位，docker compose down 数据即丢）

## 10. 测试

**更新**：
- `test_placeholder_pages`：`/user/history`、`/user/saved` 改为真实页断言（200 + 内容），`/user`、`/member` 等其余不变（/member 仍占位）
- `test_all_data_i18n_keys_exist_in_both_langs`：新页面键自动纳入（爬取页列表追加 /login、/user/history）
- SW 版本断言 v3；CSS/现有 197 条 pytest 记录（176 个 def test）保持绿

**新增**（`tests/test_auth.py`、`tests/test_userdata.py` 或并入 test_web.py）：
- 注册（成功/重复用户名/短密码/空白用户名）、登录（成功/错误密码统一文案）、登出、session cookie、/api/me
- 门禁：未登录 /user/* → 302 /login；/member/* 公开 200
- 历史：登录生成 → 自动记录；上限裁剪（>200）；删除（含跨用户 id → 404）；重新生成 302 回填
- 保存：增（含未登录跳转）、列表、应用 302、重命名、删除（跨用户 404）
- 导入导出：导出 POST 返回 JSON 附件（含全部字段、去 seed）；round-trip（导出→导入→_config_from_form 同值）；非法 JSON/字段 → 中文错误且不 500
- DB 故障容错：mock add_history 抛异常 → /generate 仍 200
- Playwright：注册→登录→生成→历史出现→保存→应用回填全链路；登出后 /user 跳登录

## 11. 非目标（YAGNI）

- 支付/订阅（登录即全功能）
- 邮箱验证、找回密码、多设备同步
- `/member/*` 门禁（P-B 再做）
- P-B 会员功能实现（各自 spec）

## 12. 影响面

- 新增：`src/mathgen/db.py`、`src/mathgen/auth.py`、`templates/login.html`、`templates/register.html`、`templates/user.html`（用户中心+历史+保存合一或分页——采用 `user.html` 带 section 参数复用）
- 修改：`web.py`（认证端点/依赖/门禁/generate 挂钩/导入导出/历史保存端点）、`i18n.py`（auth/history/saved/config 键组）、`base.html`（登录态导航）、`index.html`（导入导出按钮）、`preview.html`（保存配置按钮）、`templates/placeholder.html` 相关路由拆分、`sw.js`（v3 白名单）、`Dockerfile`、`compose.yaml`、`docs/deploy.md`、`tests/`
- 零新 Python 依赖
