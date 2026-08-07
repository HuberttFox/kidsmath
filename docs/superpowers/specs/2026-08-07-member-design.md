# P-B 会员功能设计（错题本 / 间隔复习 / 计时 / 番茄钟）

日期：2026-08-07
前置：P-A 用户系统已完成（docs/superpowers/specs/2026-08-07-user-system-design.md）

## 1. 范围与定位

- **免费开放**，仅按 `/member/` 分区；不设付费墙。
- 5 项全做，一个 spec 一个计划：
  1. 错题本（收题 / 筛选 / 管理）
  2. 间隔重复复习（完整 SM-2）
  3. 错题重出 + 变式重出（PDF 合成卷）
  4. 做题计时器（纯前端）
  5. 番茄钟 + 本地提示音（Web Audio 合成，零文件零依赖）

## 2. 约束（贯穿全篇）

- 零新增 Python 依赖（sqlite3 内置；SM-2 纯函数；提示音 Web Audio 合成）。
- 全交互 form-encoded（隐藏字段 POST），浏览器原生下载 / 302 回跳，不引入 fetch/JS 表单。
- 登录墙模式：**FastAPI dependency `current_user(request) -> User | None`**：查 cookie → token SHA-256 → sessions → users（与 P-A spec §3 完全一致，依赖自包含）。新端点统一 `Depends(current_user)`。
  - 未登录行为：GET 页面 → `302 /login?next=<path>`；POST → `302 /login`。
- 门禁分布：
  - `/member/errors`、`/member/review` → 需登录（用户数据）
  - `/member/timer`、`/member/pomodoro` → 公开（纯本地功能）
  - `/member` 首页 → 公开
- topic 一律存内部键 `arithmetic | vertical | word_problem`（手动录入归一化），渲染走 i18n。
- sw.js v3 白名单（仅 `/`、`/product`、`/static/*` 缓存）已天然排除 `/member/*`（隐私 + 陈旧），不额外处理；**ASSETS 预缓存列表须加入 `timer.js`、`audio.js`**（否则离线首访 404）。

## 3. 数据模型

`db.py` 新增表 `mistakes`（P-A 四表不动）：

```
mistakes(
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  kind          TEXT NOT NULL,             -- 'sheet' | 'manual'
  topic         TEXT NOT NULL,             -- 内部键；manual 归一化
  problem       TEXT NOT NULL,             -- 题面快照（列表/复习展示）
  answer        TEXT NOT NULL,             -- 答案快照
  expression    TEXT,                      -- 规范化算式（答案页用）；manual 可为 NULL
  question_json TEXT,                      -- sheet: 完整 Question 序列化(asdict)；manual: NULL
  params        TEXT,                      -- sheet: 出题参数 JSON（含 seed）；manual: NULL
  q_index       INTEGER,                   -- sheet: 批内序号（变式重建）；manual: NULL
  note          TEXT,                      -- 家长备注（可空）
  wrong_at      TEXT NOT NULL,             -- 首次标错时间（due_at 初始 = wrong_at，立即到期）
  ease          REAL NOT NULL DEFAULT 2.5,
  interval      INTEGER NOT NULL DEFAULT 0, -- 天
  reps          INTEGER NOT NULL DEFAULT 0,
  due_at        TEXT NOT NULL,
  last_q        INTEGER,                   -- 上次复习自评档（1|3|5）
  mastered_at   TEXT                       -- 手动标记已掌握；NULL=未掌握
)
CREATE INDEX IF NOT EXISTS idx_mistakes_queue ON mistakes(user_id, due_at);
```

- `Question` 位于 `src/mathgen/core/question.py:7-14`：`statement/answer/expression/layout` dataclass。
- sheet 收题时服务端拥有完整 `Question`，整题 `asdict()` 序列化存 `question_json`——重出 `Question(**json.loads(question_json))` **零伪造零退化**（竖式 layout 完美还原）。
- 复习队列查询：`WHERE user_id=? AND mastered_at IS NULL AND due_at <= ? ORDER BY due_at ASC, id ASC`。

## 4. SM-2（src/mathgen/sm2.py，纯函数）

```
def sm2_update(q: int, ease: float, interval: int, reps: int) -> tuple[float, int, int]:
    # q ∈ {1, 3, 5}（UI 3 档映射：错=1 / 模糊=3 / 对=5）
    if q < 3:
        return (max(1.3, ease - 0.2), 1, 0)
    reps += 1
    interval = 1 if reps == 1 else 6 if reps == 2 else round(interval * ease)
    ease += 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    return (ease, interval, reps)
```

- ease 期望值（ease 初始 2.5）：q=1 → 2.30；q=3 → 2.36（-0.14，「模糊不算加强度」）；q=5 → 2.60。
- due = now + interval 天（ISO 文本比较一致，格式同 P-A `now_iso()`）。
- 简化版注记：q<3 固定 -0.2 偏离标准公式（q=1 标准 -0.54），温和化对儿童场景有意为之。
- 首次复习：reps=0 卡 q≥3 → reps=1 → interval=1 → 明天。

## 5. 端点（全 `Depends(current_user)`，form-encoded）

```
POST /api/mistakes                 收题（hidden: kind=sheet + problem/answer/expression/topic/question_json/params/q_index/note）
POST /api/mistakes/manual          手动录入（归一化 topic；expression 可为空）
GET  /member/errors                列表页（筛：全部 / 待复习 / 已掌握）
POST /api/mistakes/{id}/review     SM-2 提交（q=1|3|5）→ 更新 ease/interval/reps/due_at/last_q → 302 /member/review
POST /api/mistakes/{id}/mastered   标记已掌握 / 取消（toggle）
POST /api/mistakes/{id}/note       编辑备注（低优先，可后置）
POST /api/mistakes/{id}/delete     IDOR 限定 user_id → 302 /member/errors
POST /api/mistakes/{id}/export     单题出卷（mode=original|variant）→ PDF 下载
POST /api/mistakes/export-batch    合成卷（多 id + 布局参数）→ PDF 下载
GET  /member/review                复习页（due_at<=now 队列，排除 mastered）
```

- 重出（original）：`Question(**json.loads(question_json))` 直用；manual 题（question_json NULL）→ `Question(topic, problem, answer, expression=problem, layout=None)` 文本退化渲染（答案页经 answer.py 退化分支显示「题面 = 答案」）。
- 变式（variant）：`p = json.loads(params); p.pop("seed")`（**必须显式删 seed**——`_config_from_form` 对显式 seed 沿用快照值，config.py 仅 `if data["seed"] is None` 才随机），`_config_from_form(p)` → `resolve` → `generate(cfg)[q_index]`。
- manual 题**无变式**（无 params），前端不显示变式按钮。
- 合成卷：每题模式统一（全 original 或全 variant，前端单选）；布局参数取**第一个非 NULL 的 params**（batch 首项可能是 manual 题 params 为 NULL）；全 manual（全 NULL）→ 默认布局 `resolve(Config())` 后 `replace(count=N, title=「错题练习」)`；**batch 上限 100**，超限拒绝。
- 答案页：sheet/expression 非空 → `f"{expression} = {answer}"`；manual（expression NULL，防御直出场景）→ 退化 `f"{problem} = {answer}"`（answer.py 增加退化分支）。
- PDF 下载头：`Content-Disposition: attachment; filename="worksheet.pdf"; filename*=UTF-8''错题练习.pdf`（RFC 5987）。

## 6. 页面与交互

### /member/errors 错题本（登录）
- 顶部手动录入表单：题型下拉（归一化）+ 题面 + 答案 + 备注（算式可选留空）。
- 列表：题面 / 答案 / 错题日期 / 下次复习日期 / 状态（待复习、已掌握）；操作：重出 / 变式 / 已掌握(切换) / 删除（confirm）/ 编辑备注。
- 筛选：全部 / 待复习（`mastered_at IS NULL`）/ 已掌握。
- 批量：checkbox 多选 → 模式单选（原题/变式）→「合成一张练习卷」→ 下载 PDF。

### /member/review 复习页（登录）
- 队列：`due_at <= now` 且未掌握，单卡视图。
- 卡片翻面：显示题面 → 「显示答案」→ 翻面显示答案 + 3 档自评按钮（错/模糊/对）。
- 评完：SM-2 更新 → 下一张；队列空 → 「今日全部完成」；无到期卡 → 空态提示。

### /member/timer 做题计时器（公开，纯前端）
- 大数字 mm:ss；开始/暂停/重置；结束响 `playChime()`。
- 不落库（刷新即失）；不做分段记录。

### /member/pomodoro 番茄钟（公开，纯前端）
- 25/5 可调输入框；开始/暂停/重置；环形进度（JS `style.background` conic-gradient）。
- 工作计时归零：**停住 + 提示音 + title 闪动**，手动点「开始休息」（不做自动链）。
- 休息归零同样提示音停住。

### /member 首页
- 4 功能卡（做题计时 / 番茄钟 / 错题本 / 间隔复习）+ 🤖 AI 出题卡「即将上线」（保留，呼应 P-C）。

## 7. 前端资源

- `static/timer.js`：倒计时核心（`endTime = performance.now() + remaining` 防漂移，tick 差值计算；后台节流回前台时间仍准）+ mm:ss 格式化；不含文案（data-i18n 由 lang.js 机制）。
- `static/audio.js`：`playChime()`——`AudioContext || webkitAudioContext`；**用户手势内创建**（开始按钮点击），结束 `resume()` 兜底；两声短音（880Hz→660Hz 各 0.2s）；gain 包络 0.2s 渐入渐出防爆音；失败静默降级。
- sw.js v3 ASSETS 列表加 `timer.js`、`audio.js`（与 P-B 同批改；SW 脚本字节变化自动触发 install，无需 bump 版本号）。
- 预览页（登录态）：每题 statement 行尾「错」按钮 → POST `/api/mistakes`（data 属性带问题快照）→ 按钮变「已收 ✓」。
- 预览页每题快照来源：server 端 context 已有完整 questions（web.py 生成处），渲染时逐题输出 statement/answer/expression/topic/params/seed/index 到 data 属性（Jinja autoescape 处理引号）。

## 8. 错误处理

- 未登录：GET 302 /login?next=；POST 302 /login。
- 跨用户 IDOR：一律 `WHERE id=? AND user_id=?`；查无此行或跨用户 → 302 回列表，不泄露存在性。
- batch >100：拒绝并 302 /member/errors（列表带错误提示，可后置简化）。
- 坏 question_json / params：捕获 → 302 回列表（不 500）。
- 提示音失败：静默（无音）。

## 9. 测试

新增：
- `tests/test_sm2.py`：表驱动。q=1→(2.30, 1, 0)；q=3→(2.36, 1, 1)（reps=0 时）；q=5→(2.60, 1, 1)；reps 序列 1→1、2→6、3→round(interval×ease)；全 q≥3 连续 10 次 interval 单调不减；ease floor 1.3。
- `tests/test_mistakes.py`（TestClient）：收题 sheet（question_json/params/q_index 落库）、manual 归一化（"竖式"→vertical）、列表筛选三分组、SM-2 提交更新 due_at、mastered toggle、删除、**IDOR 跨用户**、门禁未登录 302、batch 101 拒绝。
- `tests/test_mistakes_export.py`：original → PDF 200 + `filename*=UTF-8''` 头 + 内容含题面文本；variant → **mock 随机源固定不同值**（monkeypatch，断言确定性非原题，杜绝 flake）；manual 题无变式按钮断言（HTML 渲染）；合成卷 N 题 PDF + 首项 params 布局。
- `tests/test_ui_playwright.py` 追加：
  - timer：开始 → 倒计时显示 → 暂停冻结 → 重置归零。
  - pomodoro：可注入短时长（1s）跑完 → stub `AudioContext` 断言 playChime 调用且不抛错 + title flash class 出现。
  - 复习全链路：登录 → 预览标错建卡 → /member/review → 显示答案 → 评「对」→ 卡片消失 → 完成态。

更新：
- `test_placeholder_pages`：/member/errors、/member/review 未登录 → 302 /login；timer/pomodoro 200 真实页；/member 首页 4 卡 + AI 卡。
- `test_all_data_i18n_keys_exist_in_both_langs`：新页键自动纳入（新页模板 data-i18n 全双语）。
- `test_pwa_assets`：ASSETS 断言含 timer.js/audio.js。
- Yozai 字体子集重生成（新文案字，scripts/download_ui_font.py）。

## 10. 部署文档（docs/deploy.md 补充）

- 后台标签页节流：提示音可能延迟至回前台才响，title 闪动为兜底。
- AudioContext 需用户手势激活（首次点击），iOS/桌面 autoplay 策略说明。
- 数据卷保留既有说明（P-A 已写）。

## 11. 明确不做（YAGNI）

- 付费墙 / 激活码 / 支付。
- 自动番茄链、Notification API、tick 声、计时历史落库、多计时器并行。
- SM-2 5 档自评、复习统计图表。
- 做题计时与卷子的绑定（题号分段）。

## 12. 实现顺序建议（供计划参考）

1. sm2.py + 单测
2. db.mistakes 表 + CRUD + 单测
3. current_user dependency（新端点统一）
4. 收题/手动录入/列表/筛选端点 + 页面
5. 预览页标错按钮（登录态）
6. 复习端点 + 复习页（卡片翻面）
7. 错题重出/变式/合成卷（PDF 链路 + 导出端点）
8. timer / pomodoro / audio.js + SW ASSETS
9. 首页改造 + 占位测试更新 + 字体重生成 + deploy 文档
10. 全量回归 + e2e 收尾
