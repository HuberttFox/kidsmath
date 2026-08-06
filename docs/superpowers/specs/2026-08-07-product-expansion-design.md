# kidsmath 产品化扩展（占位页为主）设计文档

- 日期: 2026-08-07
- 状态: 已确认

## 1. 定位与目标

在现有出题工具（主页表单/预览/PDF 下载）基础上做产品化扩展：新增产品页、PWA 可安装、用户/会员占位页面群，以及 3 个真实小功能（括号出现权重、预览单页题数与跳页、分区 SVG 图标）。用户系统与会员功能**仅占位页面**，不实现后端功能。

**占位原则**：功能不实现，页面结构与 UI 需完整且符合现有马卡龙风格（复用 base.html + style.css + i18n）。

## 2. 真实功能

### 2.1 括号出现权重（paren_weight）
- `Config.paren_weight: int | None = None`（相对权重 1-10，None 物化为 5 = 50% 基线）
- 校验：非 1-10 → `ConfigError("invalid_paren_weight")` 中文
- 引擎（`topics/arithmetic.py` `_gen_multi`）：括号应用条件 = `cfg.parentheses and n >= 3 and rng.random() < cfg.paren_weight / 10`
- CLI：`--paren-weight`（choices 1-10 或 int 校验）
- 表单：数值与运算区"括号权重"数字输入（1-10，默认 5）+ ⓘ tip；回显/`_as_query` 回传（非 5 时显式）/换一批/修改参数全链路
- i18n：`f.paren_weight` / `tip.paren_weight` zh+en

### 2.2 预览单页题数与跳页
- 纯客户端：preview.html 分页区（`#sheet` + `#pager`）增加：
  - 单页题数下拉（6/12/18/24/30，默认 `ncols×6` 现行为 6 行/页）——切换后仅分页区局部重渲染（现有 render() 机制，不改整页）
  - 跳页输入框 + 按钮（"跳到第 N 页"），越界钳制
- i18n：`preview.per_page` / `preview.jump` / `preview.jump_placeholder` zh+en

### 2.3 主页分区 SVG 图标
- `static/icons/`：4 个手写 SVG（描边风格，与 math-icon.svg 协调）：
  - `settings.svg`（基础设置：滑块）
  - `calculator.svg`（数值与运算：加减乘除符号）
  - `layout.svg`（卷面排版：页面/网格）
  - `batch.svg`（批量：层叠卡片）
- index.html legend 图标圆（`.legend-icon`）改用各自 SVG（替换统一 math-icon）

## 3. 背景色修正（禁纯白纯黑）

- light：`--white: #ffffff` → `#fffdf7`（暖白）；`--card-bg`/`--input-bg` 跟随 var 自动
- dark：`--white: #2b2823` → `#2e2a25`（微调，已非纯黑）；`--bg #221f1b` 保留（非纯黑）
- 全 css 无 `#fff`/`#000` 精确值

## 4. 产品页 `/product`（完整 landing）

- 复用 base.html（页头 nav 增加"产品"入口）+ 马卡龙样式，新增 `.landing-*` CSS 段
- 区块：
  1. hero：badge + 标题"给孩子出数学题，像做游戏一样简单" + tagline + CTA"去生成练习卷"（链接 `/`）
  2. 功能卡 6 张（复用 feature-card 样式）：多题型、参数精细可控、一键 PDF 打印、中英双语、明暗主题、家长友好
  3. 三步引导（选参数 → 生成预览 → 下载打印）
  4. 会员功能预告区：计时/番茄钟/错题本/间隔复习 4 张卡 + "即将上线"徽章（链接占位页）
  5. PWA 安装指引区（说明：浏览器菜单"安装应用"即可像 App 一样使用）
  6. 页脚（复用）
- i18n：`product.*` 键组 zh+en
- **产品页不进入 PWA 离线缓存**

## 5. PWA（家长"安装"）

- `static/manifest.webmanifest`：name "kidsmath 数学出题"、short_name、start_url `/`、display standalone、theme_color 马卡龙主色、icons（SVG any + maskable；192/512 PNG 生成留 TODO）
- `static/sw.js`：缓存 app shell（css/js/fonts/图标/首页），**排除 /product**；离线兜底
- base.html：`<link rel="manifest">` + theme-color meta + apple-mobile-web-app 标签 + SW 注册脚本（仅 https/localhost）
- README 记录 PWA 说明与 PNG 图标 TODO

## 6. 用户/会员占位页面群（两段式）

| 路由 | 页面 | 内容（占位） |
|------|------|-------------|
| `/user` | 用户中心 | 头像占位圆、昵称"未登录"、我的配置入口卡、会员状态条 |
| `/user/history` | 历史配置 | 空列表 UI + "即将上线" |
| `/user/saved` | 保存配置 | 同上 |
| `/member` | 会员中心 | 功能网格卡：AI 智能配置/在线计时/番茄钟/错题本/间隔复习 + 免费版状态条 |
| `/member/timer` | 在线计时 | 占位计时 UI（时间数字 + 开始/暂停按钮 disabled） |
| `/member/pomodoro` | 番茄钟 | 25 分钟环形 UI + 音乐/白噪音/音乐导入三个标签占位 |
| `/member/errors` | 错题本 | 占位列表 |
| `/member/review` | 间隔复习 | 占位日历网格 |

- 统一组件：`.coming-soon` 徽章（"即将上线"）
- header：用户入口按钮（登录态占位，点击进 `/user`）；nav 增"产品"
- i18n：`user.*` / `member.*` 键组 zh+en
- 每个占位页复用 base + macaron；独立模板文件 `user.html`、`user_section.html`、`member.html`、`member_section.html`（通用模板 + 路由传参复用，减少 8 个近似文件）

## 7. 路由结构（web.py 新增）

```
GET /product
GET /user
GET /user/history
GET /user/saved
GET /member
GET /member/timer
GET /member/pomodoro
GET /member/errors
GET /member/review
```

统一 `_placeholder_context(lang, title_key, section)` 渲染通用占位模板。

## 8. 非目标（YAGNI）

- 用户系统后端（登录/存储/鉴权）不做
- 会员功能全部不做（AI 配置、计时、番茄钟音乐/白噪音/导入、错题标记、间隔重复算法）
- 桌面原生打包（Tauri/Electron）不做——PWA 满足"家长安装使用"
- iOS PNG 图标、离线产品页不做（TODO 记录）

## 9. 测试

- web：9 个新路由 200 + 关键区块断言（hero/功能卡/即将上线徽章/PWA 安装指引）；manifest/sw 200 + 内容断言
- css：无 `#fff`/`#000` 精确值断言
- 括号权重：引擎统计（10 → >60% 括号率、1 → <40%）、校验非法、CLI/表单回传
- Playwright：预览每页题数切换（cell 数变化）与跳页（页码跳转）
- 全量 pytest 保持绿 + Docker 冒烟

## 10. 影响面

`config.py`、`i18n.py`、`topics/arithmetic.py`、`cli.py`、`web.py`、`templates/`（base/index/preview 修改 + 新模板）、`static/`（icons/manifest/sw/css）、`tests/`、README
