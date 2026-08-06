# kidsmath 产品化扩展实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有出题工具上完成产品化扩展：括号权重、分区 SVG 图标、预览单页题数与跳页、整体马卡龙配色、产品页、PWA 可安装、用户/会员占位页面群。

**Architecture:** 复用现有 FastAPI + Jinja2 + macaron 体系。新页面全部走通用占位模板（`placeholder.html` + 路由传参），不新增重复模板；PWA 用静态 manifest + service worker；括号权重贯穿 config→engine→CLI→表单→回传。

**Tech Stack:** Python 3.11+、FastAPI、Jinja2、reportlab（不动）、Playwright（dev 测试）。

## Global Constraints

- 占位页仅结构与 UI，不实现用户系统/会员功能后端
- 产品页不进入 PWA 离线缓存
- 全 CSS 无纯白/纯黑 hex（#ffffff / #000 / #fff）；dark 用深马卡龙 token
- 括号权重 1-10 相对权重，默认 5（=50% 基线）
- i18n 所有新文案 zh+en 双语
- 全量 pytest 保持绿（当前 176）；每任务 TDD + commit

---

### Task 1: 括号出现权重（paren_weight）

**Files:**
- Modify: `src/mathgen/config.py`
- Modify: `src/mathgen/topics/arithmetic.py`
- Modify: `src/mathgen/i18n.py`
- Modify: `src/mathgen/cli.py`
- Modify: `src/mathgen/web.py`
- Modify: `src/mathgen/templates/index.html`
- Test: `tests/test_config.py`、`tests/test_arithmetic.py`、`tests/test_web.py`

**Interfaces:**
- Consumes: 现有 `Config`/`resolve()`/`_gen_multi`
- Produces: `Config.paren_weight: int | None = None`；`ResolvedConfig.paren_weight: int`（默认 5）；错误码 `invalid_paren_weight`；CLI `--paren-weight`；表单字段 `paren_weight`；`_as_query` 在非 5 时回传 `paren_weight`

- [ ] **Step 1: 写失败测试（config）**

`tests/test_config.py` 追加：
```python
def test_paren_weight_default_and_validation():
    assert resolve(Config(grade=2)).paren_weight == 5
    r = resolve(Config(grade=2, paren_weight=8))
    assert r.paren_weight == 8
    with pytest.raises(ConfigError, match="括号权重"):
        resolve(Config(paren_weight=0))
    with pytest.raises(ConfigError, match="括号权重"):
        resolve(Config(paren_weight=11))
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_config.py::test_paren_weight_default_and_validation -v`
Expected: FAIL（字段不存在）

- [ ] **Step 3: config.py 实现**

```python
# Config 加字段（show_numbers 附近）：
    paren_weight: int | None = None
# ResolvedConfig 加字段：
    paren_weight: int
# None-sentinel 循环加 "paren_weight"；默认物化元组加 ("paren_weight", 5)
# 校验段（answer_lines 校验后）：
    if data["paren_weight"] < 1 or data["paren_weight"] > 10:
        raise ConfigError("invalid_paren_weight", v=data["paren_weight"])
```

- [ ] **Step 4: i18n 错误码 + UI 键**

`src/mathgen/i18n.py`：
```python
# ERRORS_ZH / ERRORS_EN 各加：
# zh: "invalid_paren_weight": "括号权重必须在 1-10 之间，当前 {v}。"
# en: "invalid_paren_weight": "Parenthesis weight must be 1-10, got {v}."
# UI_ZH 加：
# "f.paren_weight": "括号权重",
# "tip.paren_weight": "括号题出现比重（1-10，默认 5）；权重越大括号越多",
# UI_EN 加：
# "f.paren_weight": "Parenthesis weight",
# "tip.paren_weight": "How often parentheses appear (1-10, default 5); higher = more",
```

- [ ] **Step 5: 引擎接入 + 统计测试**

`src/mathgen/topics/arithmetic.py` `_gen_multi` 括号条件改为：
```python
        groups = (_paren_groups(ops)
                  if cfg.parentheses and n >= 3 and rng.random() < cfg.paren_weight / 10
                  else None)
```
`tests/test_arithmetic.py` 追加：
```python
def test_paren_weight_statistics():
    hi = resolve(Config(grade=5, count=200, seed=51, paren_weight=10))
    lo = resolve(Config(grade=5, count=200, seed=52, paren_weight=1))
    hi_n = sum(1 for q in generate(hi) if "(" in q.expression)
    lo_n = sum(1 for q in generate(lo) if "(" in q.expression)
    assert hi_n > 100, f"weight=10 括号率过低: {hi_n}/200"
    assert lo_n < 80, f"weight=1 括号率过高: {lo_n}/200"
```

- [ ] **Step 6: CLI + web + 表单**

`cli.py`：`gen.add_argument("--paren-weight", type=int, choices=range(1, 11), default=None, help="括号权重 1-10")`；overrides 加 `"paren_weight": ns.paren_weight`。

`web.py` `_config_from_form` 加 `paren_weight=i(form.get("paren_weight"))`；`_as_query` 加：
```python
    if cfg.paren_weight not in (None, 5):
        q["paren_weight"] = str(cfg.paren_weight)
```

`index.html` 数值与运算区（括号 checkbox 后）加：
```html
        <label class="field-group" for="paren_weight">
          <span class="field-label">
            <span data-i18n="f.paren_weight">{{ t("f.paren_weight", lang) }}</span>{{ tip("tip.paren_weight") }}
          </span>
          {{ input("paren_weight", form, "5", "number", min="1", max="10") }}
        </label>
```

`tests/test_web.py` 追加：
```python
def test_paren_weight_roundtrip():
    r = client.post("/generate", data={"grade": "1", "count": "4", "paren_weight": "8"})
    m = re.search(r'href="(/download\.pdf\?[^"]+)"', r.text)
    href = unescape(m.group(1))
    assert "paren_weight=8" in href
    r2 = client.post("/generate", data={"grade": "1", "count": "4"})
    m2 = re.search(r'href="(/download\.pdf\?[^"]+)"', r2.text)
    assert "paren_weight" not in unescape(m2.group(1))
```

- [ ] **Step 7: 全量回归 + 提交**

Run: `uv run pytest -q` — 全部绿
Commit: `git add -A && git commit -m "feat: 括号出现权重 paren_weight（1-10）"`

---

### Task 2: 主页分区 SVG 图标

**Files:**
- Create: `src/mathgen/static/icons/settings.svg`、`calculator.svg`、`layout.svg`、`batch.svg`
- Modify: `src/mathgen/templates/index.html`
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: 4 个 SVG 静态文件（24 视口描边风格）；index legend 图标圆引用 `topic_icons`-风格映射

- [ ] **Step 1: 写失败测试**

`tests/test_web.py` 追加：
```python
def test_section_icons_exist_and_used():
    for name in ("settings", "calculator", "layout", "batch"):
        r = client.get(f"/static/icons/{name}.svg")
        assert r.status_code == 200, name
        assert r.text.startswith("<svg")
    r2 = client.get("/")
    assert "/static/icons/settings.svg" in r2.text
    assert "/static/icons/calculator.svg" in r2.text
    assert "/static/icons/layout.svg" in r2.text
    assert "/static/icons/batch.svg" in r2.text
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_web.py::test_section_icons_exist_and_used -v` — FAIL

- [ ] **Step 3: 写 4 个 SVG**

`settings.svg`（滑块）：
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#6b4c3b" stroke-width="2" stroke-linecap="round">
  <line x1="4" y1="7" x2="20" y2="7"/><circle cx="9" cy="7" r="2.5" fill="#fffdf7"/>
  <line x1="4" y1="17" x2="20" y2="17"/><circle cx="15" cy="17" r="2.5" fill="#fffdf7"/>
</svg>
```
`calculator.svg`：
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#6b4c3b" stroke-width="2" stroke-linecap="round">
  <rect x="5" y="3" width="14" height="18" rx="3"/>
  <line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="9.01" y2="11"/>
  <line x1="13" y1="11" x2="13.01" y2="11"/><line x1="9" y1="15" x2="9.01" y2="15"/>
  <line x1="13" y1="15" x2="15" y2="17"/><line x1="15" y1="15" x2="13" y2="17"/>
</svg>
```
`layout.svg`（页面网格）：
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#6b4c3b" stroke-width="2" stroke-linecap="round">
  <rect x="4" y="4" width="16" height="16" rx="3"/>
  <line x1="4" y1="10" x2="20" y2="10"/><line x1="12" y1="10" x2="12" y2="20"/>
</svg>
```
`batch.svg`（层叠）：
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#6b4c3b" stroke-width="2" stroke-linecap="round">
  <rect x="4" y="8" width="14" height="12" rx="3"/>
  <path d="M8 4h12v12" transform="translate(1 -2)"/>
</svg>
```

- [ ] **Step 4: index.html legend 换图标**

`src/mathgen/templates/index.html` 四个 legend 的 `<img src="/static/math-icon.svg" ...>` 分别替换为：
- 基础设置 → `/static/icons/settings.svg`
- 数值与运算 → `/static/icons/calculator.svg`
- 卷面排版 → `/static/icons/layout.svg`
- 批量 → `/static/icons/batch.svg`

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest tests/test_web.py -q`
Commit: `git add -A && git commit -m "feat: 主页分区 SVG 图标"`

---

### Task 3: 预览单页题数 + 跳页

**Files:**
- Modify: `src/mathgen/templates/preview.html`
- Modify: `src/mathgen/i18n.py`
- Test: `tests/test_ui_playwright.py`

**Interfaces:**
- Produces: 分页区新增 `#perPage` select（6/12/18/24/30）与 `#jumpInput`+`#jumpBtn`；JS `render()` 读 `#perPage` 值；i18n 键 `preview.per_page`/`preview.jump`

- [ ] **Step 1: i18n 键**

```python
# UI_ZH：
# "preview.per_page": "每页题数",
# "preview.jump": "跳到第 N 页",
# "preview.jump_placeholder": "页码",
# UI_EN：
# "preview.per_page": "Per page",
# "preview.jump": "Jump to page",
# "preview.jump_placeholder": "Page",
```

- [ ] **Step 2: 写失败 Playwright 测试**

`tests/test_ui_playwright.py` 追加：
```python
def test_preview_per_page_and_jump(page):
    page.goto(BASE + "/")
    page.locator('label.grade-btn:has-text("2 年级")').click()
    page.locator('#count').fill("30")
    page.locator('button[type="submit"]').click()
    expect(page.locator('#pager')).to_be_visible()
    expect(page.locator('.cell')).to_have_count(12)  # 默认 2 列 × 6 行
    page.locator('#perPage').select_option("6")
    expect(page.locator('.cell')).to_have_count(6)
    expect(page.locator('#pageLabel')).to_contain_text("5")  # 30/6=5 页
    page.locator('#jumpInput').fill("3")
    page.locator('#jumpBtn').click()
    expect(page.locator('#pageLabel')).to_contain_text("3")
    page.locator('#jumpInput').fill("99")
    page.locator('#jumpBtn').click()
    expect(page.locator('#pageLabel')).to_contain_text("5")  # 越界钳制
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_ui_playwright.py::test_preview_per_page_and_jump -v`
Expected: FAIL（#perPage 不存在）

- [ ] **Step 4: preview.html 实现**

分页区（`#pager` 内）改：
```html
<div class="pager" id="pager" hidden>
  <label class="pager-per" for="perPage">
    <span data-i18n="preview.per_page">{{ t("preview.per_page", lang) }}</span>
    <select id="perPage">
      <option value="6">6</option><option value="12" selected>12</option>
      <option value="18">18</option><option value="24">24</option><option value="30">30</option>
    </select>
  </label>
  <button type="button" class="btn btn-secondary" id="pagePrev" data-i18n="pager.prev">{{ t("pager.prev", lang) }}</button>
  <span class="pager-page" id="pageLabel"></span>
  <button type="button" class="btn btn-secondary" id="pageNext" data-i18n="pager.next">{{ t("pager.next", lang) }}</button>
  <input id="jumpInput" type="number" min="1" placeholder="{{ t('preview.jump_placeholder', lang) }}">
  <button type="button" class="btn btn-secondary" id="jumpBtn" data-i18n="preview.jump">{{ t("preview.jump", lang) }}</button>
</div>
```
JS 修改：
```js
    var perSelect = document.getElementById('perPage');
    function perPage() { return parseInt(perSelect.value, 10) || (ncols * 6); }
    function recompute() {
      pages = Math.max(1, Math.ceil(cells.length / perPage()));
      if (cur > pages - 1) cur = pages - 1;
      render();
    }
    perSelect.addEventListener('change', recompute);
    document.getElementById('jumpBtn').addEventListener('click', function () {
      var n = parseInt(document.getElementById('jumpInput').value, 10);
      if (!n) return;
      cur = Math.min(Math.max(n - 1, 0), pages - 1);
      render();
    });
    // render() 内 cells 显隐判断改用 perPage()
    // pager 显示条件：cells.length > perPage()（原 ncols*6）
```
注意：原 `if (cells.length <= per) return;` 改为基于 perPage()；`per` 变量移除或保持默认。

- [ ] **Step 5: CSS 小样式 + 回归**

`style.css` 加：
```css
.pager-per { display: inline-flex; align-items: center; gap: .4em; font-weight: 700; color: var(--text-soft); }
.pager-per select, #jumpInput {
  padding: .4em .6em; border: 1.5px solid var(--input-border);
  border-radius: var(--radius-sm); background: var(--input-bg);
  font: inherit; color: var(--text); width: 72px;
}
```
Run: `uv run pytest tests/test_ui_playwright.py -q`
Commit: `git add -A && git commit -m "feat: 预览单页题数配置与跳页"`

---

### Task 4: 整体马卡龙配色（禁纯白纯黑）

**Files:**
- Modify: `src/mathgen/static/style.css`
- Test: `tests/test_web.py`

- [ ] **Step 1: 写失败测试**

`tests/test_web.py` 追加：
```python
def test_no_pure_white_black_in_css():
    css = client.get("/static/style.css").text
    assert "#ffffff" not in css and "#FFFFFF" not in css
    assert "#000" not in css
    assert "#fff" not in css.replace("#fffdf7", "")  # 暖白除外
    assert "--white: #fffdf7" in css
    assert "--bg: #2b211a" in css  # dark 深马卡龙
    assert "--card-bg: #382a20" in css
    assert "--input-bg: #3f2f23" in css
    assert "rgba(0, 0, 0" not in css
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_web.py::test_no_pure_white_black_in_css -v` — FAIL

- [ ] **Step 3: style.css 配色替换**

`:root` 块：
- `--white: #ffffff` → `--white: #fffdf7`

`@media (prefers-color-scheme: dark)` 与 `html[data-theme="dark"]` 两个 dark 块同时改：
- `--cream: #221f1b` → `--cream: #2b211a`
- `--white: #2b2823` → `--white: #3a2d22`
- `--card-bg: #2f2b26` → `--card-bg: #382a20`
- `--input-bg: #38332d` → `--input-bg: #3f2f23`
- `--shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3)` → `rgba(48, 32, 20, 0.35)`
- `--shadow-md: 0 4px 16px rgba(0, 0, 0, 0.35)` → `rgba(48, 32, 20, 0.4)`
- 边框 `rgba(230, 221, 207, 0.14/0.18)` → `rgba(244, 210, 178, 0.18)`（两处）

按钮文字：`.btn` 等处 `color: #fff` → `color: #fffdf7`（grep 全部替换）。

- [ ] **Step 4: 全组件核对**

Run: `rg -n "#fff\b|#000|#ffffff|#2b2823|#2f2b26|#38332d|#221f1b" src/mathgen/static/style.css`
Expected: 无输出（除注释）；若有残留逐一替换为对应 token/深马卡龙值。

- [ ] **Step 5: 回归 + impeccable 复核 + 提交**

Run: `uv run pytest -q`
Run: `node /home/hubert/.config/opencode/skills/impeccable/scripts/detect.mjs --json src/mathgen/static/style.css` — 零发现或仅记录
Commit: `git add -A && git commit -m "style: 整体马卡龙配色（light 暖白/dark 深马卡龙，禁纯白纯黑）"`

---

### Task 5: 产品页 `/product`

**Files:**
- Create: `src/mathgen/templates/product.html`
- Modify: `src/mathgen/web.py`
- Modify: `src/mathgen/i18n.py`
- Modify: `src/mathgen/static/style.css`
- Modify: `src/mathgen/templates/base.html`（nav 加产品入口）
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: `GET /product`（HTML）；nav 链接 `href="/product"`；CSS `.landing-*` 段；i18n `product.*`

- [ ] **Step 1: i18n 键（zh/en）**

```python
# UI_ZH：
"product.title": "产品介绍",
"product.hero_badge": "完全免费 · 开源 · 离线出题",
"product.hero_title": "给孩子出数学题，像做游戏一样简单",
"product.hero_tagline": "选参数、点生成，一张漂亮的练习卷就出来了",
"product.cta": "去生成练习卷",
"product.f1_title": "多题型覆盖",
"product.f1_desc": "口算、竖式、应用题，1-6 年级一键预设",
"product.f2_title": "参数精细可控",
"product.f2_desc": "数值范围、进位借位、乘法表、括号权重、题间距随意调",
"product.f3_title": "一键 PDF 打印",
"product.f3_desc": "A4 排版 + 答案页，直接打印给孩子做",
"product.f4_title": "中英双语",
"product.f4_desc": "界面与题目支持中英文切换",
"product.f5_title": "明暗主题",
"product.f5_desc": "自动跟随系统，也可手动切换",
"product.f6_title": "家长友好",
"product.f6_desc": "可安装为应用，手机上也能随时出题",
"product.step1_t": "选参数",
"product.step1_d": "选年级或自定义范围",
"product.step2_t": "生成预览",
"product.step2_d": "即时预览，可换一批",
"product.step3_t": "下载打印",
"product.step3_d": "PDF 下载，答案页随附",
"product.member_title": "会员功能（即将上线）",
"product.member_timer": "在线计时",
"product.member_pomodoro": "番茄钟",
"product.member_errors": "错题本",
"product.member_review": "间隔复习",
"product.pwa_title": "安装为应用",
"product.pwa_desc": "在浏览器菜单中选择「安装应用」，像 App 一样使用",
# UI_EN 对应翻译：
"product.title": "Product",
"product.hero_badge": "Free · Open Source · Offline",
"product.hero_title": "Math worksheets for kids, as easy as a game",
"product.hero_tagline": "Pick parameters, click generate, get a lovely worksheet",
"product.cta": "Generate worksheets",
"product.f1_title": "Multiple topics",
"product.f1_desc": "Arithmetic, vertical, word problems with grade presets 1-6",
"product.f2_title": "Fine-grained control",
"product.f2_desc": "Ranges, carry/borrow, times table, parenthesis weight, gaps",
"product.f3_title": "One-click PDF",
"product.f3_desc": "A4 layout with answer page, ready to print",
"product.f4_title": "Bilingual",
"product.f4_desc": "UI and questions in Chinese and English",
"product.f5_title": "Light & dark",
"product.f5_desc": "Follows the system, switchable manually",
"product.f6_title": "Parent friendly",
"product.f6_desc": "Installable as an app, works on phones",
"product.step1_t": "Pick parameters",
"product.step1_d": "Choose a grade or customize ranges",
"product.step2_t": "Preview",
"product.step2_d": "Instant preview, regenerate anytime",
"product.step3_t": "Download & print",
"product.step3_d": "Download PDF with the answer page",
"product.member_title": "Membership features (coming soon)",
"product.member_timer": "Online timer",
"product.member_pomodoro": "Pomodoro",
"product.member_errors": "Mistake book",
"product.member_review": "Spaced review",
"product.pwa_title": "Install as an app",
"product.pwa_desc": "Choose “Install app” in your browser menu to use it like an app",
```

- [ ] **Step 2: 写失败测试**

`tests/test_web.py` 追加：
```python
def test_product_page():
    r = client.get("/product")
    assert r.status_code == 200
    assert 'class="landing-hero"' in r.text
    assert 'class="feature-card' in r.text
    assert "coming-soon" in r.text
    assert 'href="/"' in r.text  # CTA
```

- [ ] **Step 3: web.py 路由**

```python
@app.get("/product", response_class=HTMLResponse)
async def product_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(
        request, "product.html",
        {"lang": lang, "ui_json": _UI_JSON, "version": __version__})
```

- [ ] **Step 4: product.html 模板**

`src/mathgen/templates/product.html`：extends base；nav block 加产品/生成链接；内容：landing-hero（badge+h1+tagline+CTA btn）、features-grid（6 张 feature-card 复用现有样式）、steps（3 步）、member-preview（4 卡 + coming-soon 徽章，链接到 /member/*）、pwa 指引、页脚由 base 提供。全部文案用 `{{ t("product.xxx", lang) }}` + data-i18n。

- [ ] **Step 5: CSS .landing-* 段**

`style.css` 追加（复用现有 hero/feature-card/steps 样式，补 landing 专属）：
```css
/* ---- 产品页 ---- */
.landing-hero { text-align: center; padding: 3em var(--gap) 2em; position: relative; overflow: hidden; }
.landing-hero::before { content: ''; position: absolute; top: -120px; left: 50%;
  transform: translateX(-50%); width: 480px; height: 480px; border-radius: 50%;
  background: radial-gradient(circle, var(--mint-soft) 0%, transparent 65%); opacity: .5; pointer-events: none; }
.landing-section { max-width: var(--container-max); margin: 0 auto; padding: 1.6em var(--gap); }
.landing-section h2 { text-align: center; font-size: 1.4rem; margin-bottom: 1em; color: var(--text); }
.features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1em; }
.feature-card { background: var(--card-bg); border: 1.5px solid var(--border);
  border-radius: var(--radius-lg); padding: 1.2em 1.1em; text-align: center; box-shadow: var(--shadow-sm); }
.feature-card h3 { font-size: 1.02rem; margin-bottom: .4em; }
.feature-card p { font-size: .88rem; color: var(--text-soft); }
.steps { display: flex; gap: 1.2em; justify-content: center; flex-wrap: wrap; }
.step { flex: 1; min-width: 180px; text-align: center; }
.step-number { width: 48px; height: 48px; margin: 0 auto .6em; border-radius: 50%;
  background: linear-gradient(135deg, var(--yellow) 0%, var(--peach) 100%);
  display: flex; align-items: center; justify-content: center; font-weight: 800; box-shadow: var(--shadow-sm); }
.member-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1em; }
.coming-soon { display: inline-block; margin-top: .5em; padding: .2em .8em; border-radius: 999px;
  background: var(--yellow-soft); border: 1.5px solid var(--yellow); font-size: .78rem; font-weight: 700; color: var(--text-soft); }
```
注意：`.peach` 变量已存在（#ffdab9）✓。

- [ ] **Step 6: base.html nav 加产品入口 + 回归 + 提交**

base.html nav block 之前加默认：
```html
      <nav class="nav" aria-label="导航">
        <a href="/product" data-i18n="product.title">{{ t("product.title", lang) }}</a>
        {% block nav %}{% endblock %}
      </nav>
```
Run: `uv run pytest tests/test_web.py -q`（检查既有 nav 断言不破坏——test_index_hero_nav_footer 断言 `href="#form"` 仍在 nav block 内 ✓）
Commit: `git add -A && git commit -m "feat: 产品页 landing"`

---

### Task 6: PWA（manifest + service worker）

**Files:**
- Create: `src/mathgen/static/manifest.webmanifest`
- Create: `src/mathgen/static/sw.js`
- Modify: `src/mathgen/templates/base.html`
- Modify: `src/mathgen/web.py`（manifest/sw 静态已由 static mount 覆盖，无需路由；确认 Content-Type）
- Test: `tests/test_web.py`

- [ ] **Step 1: 写失败测试**

`tests/test_web.py` 追加：
```python
def test_pwa_assets():
    r = client.get("/static/manifest.webmanifest")
    assert r.status_code == 200
    assert '"name"' in r.text and "kidsmath" in r.text
    assert r.headers.get("content-type", "").startswith("application/manifest")
    r2 = client.get("/static/sw.js")
    assert r2.status_code == 200
    assert "product" not in r2.text  # 产品页不缓存
    r3 = client.get("/")
    assert 'rel="manifest"' in r3.text
    assert "/static/sw.js" in r3.text
```
（若 content-type 断言失败——Starlette 对 .webmanifest 可能给 application/octet-stream——改为断言含 `manifest` 或宽松：`"manifest" in r.headers.get("content-type","")`）

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_web.py::test_pwa_assets -v` — FAIL

- [ ] **Step 3: manifest.webmanifest**

```json
{
  "name": "kidsmath 数学出题",
  "short_name": "kidsmath",
  "description": "小学数学练习题生成工具",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#fffdf7",
  "theme_color": "#a8e6cf",
  "icons": [
    { "src": "/static/math-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any" },
    { "src": "/static/math-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "maskable" }
  ]
}
```
（192/512 PNG 图标留 TODO 注释于 README）

- [ ] **Step 4: sw.js（app shell 缓存，排除 /product）**

```js
const CACHE = 'kidsmath-v1';
const ASSETS = [
  '/', '/static/style.css', '/static/lang.js', '/static/math-icon.svg',
  '/static/icons/settings.svg', '/static/icons/calculator.svg',
  '/static/icons/layout.svg', '/static/icons/batch.svg',
  '/static/fonts/yozai-400.woff2', '/static/fonts/yozai-700.woff2'
];
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/product')) return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (res.ok && url.origin === location.origin) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    }))
  );
});
```

- [ ] **Step 5: base.html 注册 + meta**

```html
  <link rel="manifest" href="/static/manifest.webmanifest">
  <meta name="theme-color" content="#a8e6cf">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
```
body 末尾（lang.js 后）：
```html
  <script>
    if ('serviceWorker' in navigator && location.protocol !== 'file:') {
      navigator.serviceWorker.register('/static/sw.js').catch(function () {});
    }
  </script>
```

- [ ] **Step 6: 回归 + 提交**

Run: `uv run pytest tests/test_web.py -q`
Commit: `git add -A && git commit -m "feat: PWA（manifest + service worker，产品页不缓存）"`

---

### Task 7: 用户/会员占位页面群

**Files:**
- Create: `src/mathgen/templates/placeholder.html`（通用占位模板）
- Modify: `src/mathgen/web.py`（9 路由 + helper）
- Modify: `src/mathgen/i18n.py`
- Modify: `src/mathgen/templates/base.html`（header 用户入口）
- Modify: `src/mathgen/static/style.css`（占位页样式）
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: `GET /user`、`/user/history`、`/user/saved`、`/member`、`/member/timer`、`/member/pomodoro`、`/member/errors`、`/member/review`；helper `_placeholder_context(lang, title_key, cards)`；模板 `placeholder.html` 接收 `title`/`cards`/`link` 上下文

- [ ] **Step 1: i18n 键（zh/en）**

```python
# UI_ZH：
"user.title": "用户中心",
"user.login_hint": "登录功能即将上线",
"user.history": "历史配置",
"user.history_desc": "查看最近生成的配置",
"user.saved": "保存配置",
"user.saved_desc": "收藏常用配置",
"user.member_status": "免费版",
"member.title": "会员中心",
"member.ai": "AI 智能配置",
"member.ai_desc": "用一句话描述需求，自动生成配置",
"member.timer": "在线计时",
"member.timer_desc": "做题计时与统计",
"member.pomodoro": "番茄钟",
"member.pomodoro_desc": "专注学习，含白噪音与音乐",
"member.errors": "错题本",
"member.errors_desc": "标记与回顾错题",
"member.review": "间隔复习",
"member.review_desc": "错题间隔重复复习",
"member.review_gen": "错题相关题型再次出题",
"coming_soon": "即将上线",
"back_home": "返回首页",
# UI_EN 对应：
"user.title": "Account",
"user.login_hint": "Sign-in coming soon",
"user.history": "History",
"user.history_desc": "Recently generated configs",
"user.saved": "Saved configs",
"user.saved_desc": "Your favorite configurations",
"user.member_status": "Free plan",
"member.title": "Membership",
"member.ai": "AI config",
"member.ai_desc": "Describe needs in one sentence, generate config",
"member.timer": "Online timer",
"member.timer_desc": "Timed practice with stats",
"member.pomodoro": "Pomodoro",
"member.pomodoro_desc": "Focused study with white noise & music",
"member.errors": "Mistake book",
"member.errors_desc": "Mark and review mistakes",
"member.review": "Spaced review",
"member.review_desc": "Review mistakes at intervals",
"member.review_gen": "Regenerate questions from mistakes",
"coming_soon": "Coming soon",
"back_home": "Back to home",
```

- [ ] **Step 2: 写失败测试**

`tests/test_web.py` 追加：
```python
def test_placeholder_pages():
    for path in ("/user", "/user/history", "/user/saved", "/member",
                 "/member/timer", "/member/pomodoro", "/member/errors", "/member/review"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "coming-soon" in r.text, path
    r = client.get("/")
    assert 'href="/user"' in r.text  # header 用户入口
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_web.py::test_placeholder_pages -v` — FAIL

- [ ] **Step 4: web.py 路由 + helper**

```python
PLACEHOLDER_PAGES = {
    "/user": ("user.title", [
        ("🧑", "user.history", "user.history_desc", "/user/history"),
        ("⭐", "user.saved", "user.saved_desc", "/user/saved"),
    ]),
    "/user/history": ("user.history", [("📜", "user.history", "coming_soon", None)]),
    "/user/saved": ("user.saved", [("⭐", "user.saved", "coming_soon", None)]),
    "/member": ("member.title", [
        ("🤖", "member.ai", "member.ai_desc", None),
        ("⏱️", "member.timer", "member.timer_desc", "/member/timer"),
        ("🍅", "member.pomodoro", "member.pomodoro_desc", "/member/pomodoro"),
        ("❌", "member.errors", "member.errors_desc", "/member/errors"),
        ("🔁", "member.review", "member.review_desc", "/member/review"),
    ]),
    "/member/timer": ("member.timer", [("⏱️", "member.timer", "member.timer_desc", None)]),
    "/member/pomodoro": ("member.pomodoro", [("🍅", "member.pomodoro", "member.pomodoro_desc", None)]),
    "/member/errors": ("member.errors", [("❌", "member.errors", "member.errors_desc", None)]),
    "/member/review": ("member.review", [
        ("🔁", "member.review", "member.review_desc", None),
        ("📝", "member.review_gen", "coming_soon", None),
    ]),
}

@app.get("/user")
@app.get("/user/history")
@app.get("/user/saved")
@app.get("/member")
@app.get("/member/timer")
@app.get("/member/pomodoro")
@app.get("/member/errors")
@app.get("/member/review")
async def placeholder_page(request: Request):
    lang = _lang(request)
    title_key, cards = PLACEHOLDER_PAGES[request.url.path]
    cards_i18n = [(icon, t(t_key, lang), t(d_key, lang),
                   link and t("coming_soon", lang) or None)
                  for icon, t_key, d_key, link in cards]
    return templates.TemplateResponse(request, "placeholder.html", {
        "lang": lang, "ui_json": _UI_JSON, "title": t(title_key, lang),
        "title_key": title_key, "cards": cards_i18n})
```
（注意：`t(d_key, lang)` 当 d_key == "coming_soon" 时直接取文案；cards 的 link 字段若为 None 则不显示链接）

- [ ] **Step 5: placeholder.html 模板**

```html
{% extends "base.html" %}
{% block title %}{{ title }} - mathgen{% endblock %}
{% block nav %}
<a href="/" data-i18n="back_home">{{ t("back_home", lang) }}</a>
{% endblock %}
{% block content %}
<section class="placeholder-hero">
  <h1 class="placeholder-title" data-i18n="{{ title_key }}">{{ title }}</h1>
  <p class="coming-soon" data-i18n="coming_soon">{{ t("coming_soon", lang) }}</p>
</section>
<section class="placeholder-grid">
  {% for icon, tkey, desc, link in cards %}
  <div class="placeholder-card">
    <span class="placeholder-icon">{{ icon }}</span>
    <h2>{{ tkey }}</h2>
    <p>{{ desc }}</p>
    {% if link %}<a class="btn btn-secondary btn-small" href="{{ link }}">{{ link }}</a>{% endif %}
  </div>
  {% endfor %}
</section>
{% endblock %}
```

- [ ] **Step 6: base.html header 用户入口 + CSS**

base.html header-controls 前加：
```html
      <a class="btn btn-secondary btn-small" href="/user" id="userEntry">👤 <span data-i18n="user.title">{{ t("user.title", lang) }}</span></a>
```
（data-i18n 的 key 为 `user.title` ✓；注意 header 无 ui_json 时 base 有 `{% if ui_json %}` 保护——所有新路由都传 ui_json ✓）

`style.css` 追加：
```css
/* ---- 占位页 ---- */
.placeholder-hero { text-align: center; padding: 2.4em var(--gap) 1em; }
.placeholder-title { font-size: 1.6rem; color: var(--text); }
.placeholder-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1em; max-width: var(--container-max); margin: 1.2em auto 2em; padding: 0 var(--gap); }
.placeholder-card { background: var(--card-bg); border: 1.5px solid var(--border);
  border-radius: var(--radius-lg); padding: 1.2em; text-align: center; box-shadow: var(--shadow-sm); }
.placeholder-icon { font-size: 1.8rem; display: block; margin-bottom: .4em; }
.placeholder-card h2 { font-size: 1.05rem; margin-bottom: .3em; }
.placeholder-card p { font-size: .88rem; color: var(--text-soft); margin-bottom: .6em; }
.btn-small { padding: .45em 1.1em; font-size: .85rem; }
```

- [ ] **Step 7: 回归 + 提交**

Run: `uv run pytest tests/test_web.py tests/test_ui_playwright.py -q`
Commit: `git add -A && git commit -m "feat: 用户/会员占位页面群（9 路由）"`

---

### Task 8: README + 收尾验证

**Files:**
- Modify: `README.md`
- Modify: `docs/deploy.md`（PWA 说明）

- [ ] **Step 1: README 更新**

追加：产品页 `/product`、用户/会员占位页说明（即将上线）、PWA 安装指引（浏览器"安装应用"；产品页不在离线缓存）、`--paren-weight` 参数、括号权重 tip、PNG 图标 TODO（192/512 待生成）。

- [ ] **Step 2: docs/deploy.md 追加**

PWA 段：https 或 localhost 下浏览器可安装；nginx/caddy 需 `Content-Type: application/manifest+json`（如缺失则 manifest 仍可解析）与 SW 正确缓存头。

- [ ] **Step 3: 全量验证**

Run: `uv run pytest -q` — 全部绿
Run: `node /home/hubert/.config/opencode/skills/impeccable/scripts/detect.mjs --json src/mathgen/templates/*.html src/mathgen/static/style.css` — 零发现或记录 brief 项
Run: `docker build -q -t mathgen:latest . && docker run -d -p 18091:8080 mathgen:latest && curl localhost:18091/healthz && curl -s -o /dev/null -w '%{http_code}' localhost:18091/product && curl -s -o /dev/null -w '%{http_code}' localhost:18091/member/timer` — healthz 200、product 200、member 200
Commit: `git add -A && git commit -m "docs: README 与部署文档（PWA/占位页/括号权重）" && git push`

---

## Self-Review 记录

- Spec 覆盖：§2.1 括号权重（T1）、§2.2 预览单页题数+跳页（T3）、§2.3 SVG 图标（T2）、§3 马卡龙配色（T4）、§4 产品页（T5）、§5 PWA（T6）、§6 用户/会员占位（T7）、§7 路由（T5/T7）、§9 测试（各任务内）、§10 文档（T8）。
- 命名一致性：`paren_weight` 贯穿 config/engine/cli/web/form；`#perPage`/`#jumpInput`/`#jumpBtn` 在 T3 模板与测试一致；`PLACEHOLDER_PAGES` 路由表与模板 `placeholder.html` 上下文键（title/title_key/cards）一致；i18n key 前缀 `product.*`/`user.*`/`member.*`/`preview.*`。
- 已知边界：manifest Content-Type 断言预留宽松分支（Step 1 注释）；PWA PNG 图标留 TODO（spec §8 非目标）。
