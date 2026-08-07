# P-C AI 自动配置（例题粘贴解析 → 回填出题表单）

日期：2026-08-07
前置：**依赖 P-B 已完成**（/member 首页改造 + 路由拆分先落地）。实施序：P-A → P-B → P-C。
- P-A：docs/superpowers/specs/2026-08-07-user-system-design.md
- P-B：docs/superpowers/specs/2026-08-07-member-design.md

## 1. 范围与定位

- 用户粘贴例题文本（多行，一行一题），规则解析器推断出题配置 → 回填主表单（`302 /?<fields>`，复用 P-A `_redirect_to_config` 机制）供确认修改。
- 页面 `/member/ai`，**公开**（纯工具，无用户数据，与 timer/pomodoro 同）。
- /member 首页 AI 卡「即将上线」→ 改为真实链接 `/member/ai`（P-B `test_member_home_has_ai_coming_soon` 同步更新）。
- 拍照/图片入口：不做 OCR。引导文案「拍下题目照片？可登录后在错题本手动录入」（链接 `/member/errors`；未登录 302 /login，设计接受）。

## 2. 约束

- 零新增 Python 依赖（正则规则解析）。
- 全 form-encoded；解析失败回解析页带错误条；成功 302 回填。
- i18n zh/en 键成对；新文案触发 Yozai 字体重生成。
- sw.js 白名单不含 `/member/ai`（公开页走网络，无新缓存项）。
- 不推断：carry/borrow、竖式 layout（文本无法可靠检测竖式，一律按算子 topic）、应用题四角色区间（grade 默认）、解析历史。

## 3. 解析器 `src/mathgen/parser.py`（纯函数）

```
parse_examples(text: str) -> ParseResult
ParseResult = {
  fields: dict,          # 可直喂 _config_from_form 的部分字段
  recognized: int,       # 成功识别题数
  total: int,            # 输入行数（清洗后非空行）
  notes: list[str],      # 结构化信号（页面 i18n 翻译渲染，不落中文）
  signals: {...}         # 中间结果（运算符频率/位数分布/括号率/算式率/operand_count 众数）
}
```

**规则管线**：
1. 分行 → 清洗：去空白、题号变体（`1.`、`(1)`、`①`）、全角 `−→-`、运算符变体（`x`/`✕`/`*`→`×`）。
2. 表达式识别：**整链正则** `(?:\d+\s*[+\-×÷*/]\s*)+\d+`（勿用二元段正则——`finditer("12+34+5")` 只命中 "12+34" 会截断、污染 operand_count 众数）；**匹配前剥离行尾答案** `\s*=\s*[\d.]+\s*$`（"23 + 48 = 71" 常见格式，答案不参与统计）；竖式线性化（`23\n+48\n----` 折叠为一行，续行 `fullmatch(r"[+\-×÷*xX＋－＊]\s*\d+\s*")`（算子+单个数字，含全角变体）或纯横线，`-3+5` 独立行不被吞）。
3. 应用题检测：算式率 < 50% 且含中文字句 → topic=word_problem；**混合输入以多数为准**（算式率 ≥50% → arithmetic，应用题行计入 notes 忽略）。
4. 运算符频率 → operators（top 2，`+`/`-`/`×`/`÷` 映射，含变体归一）。
5. 位数分布 → operand 主位数 d（众数）；**operand_count = 整链表达式数字个数众数，钳制到 [2, 4]**（>4 → 4，Config 上限 operand_count=4；<2 理论不可达，防御取 2）。
6. **grade 映射**：仅一位数±→1；两位数±→2；含 ×/÷→3；三位数±→3（数位可覆盖算子推断）。**应用题**：位数 ≤1 → grade 1，否则 grade 2（算式内部参数用该年级 preset）。
7. 括号率 >30% → parentheses=1。
8. **count = max(N, 10)**（N=recognized，显式回填，生成数 ≥ 粘贴行数）。
9. **result_range**：± → `(0, 10^d)`（d=主位数，2 位 → 0-100）；×/÷ **不推断**（交 grade preset；宽区间推断无意义）。含括号同样交 preset。
10. 无数字/纯空 → fields 空 + notes["no_numbers"]（回填按钮禁用）。

**负数边界**：前导负号（`-3+5`）按运算符处理，不特殊支持（儿童卷场景合理）。

## 4. 页面与端点

```
GET  /member/ai           — 页面（公开）
POST /api/ai/parse        — 解析（公开），渲染结果区
POST /api/ai/backfill     — 回填（公开）：form fields(JSON)+text → resolve 试校验 →
                             成功 302 /?<fields>（_as_query 非默认字段，去 seed），失败回解析页错误条
```

**`/member/ai` 页面**：
- 大文本框（多行，一行一题）+ 「开始解析」按钮。
- 拍照/图片引导区（见 §1）。
- POST /api/ai/parse → 渲染同页结果区：
  - 摘要：识别 `recognized/total` 题 + 逐项（题型/运算符/数位/括号/count）；识别项显示值，未识别项显示「默认」标记。
  - 「回填表单」按钮（fields 非空才可用）→ `302 /?<fields>`（urlencode）。
- 解析失败（resolve 校验不过）→ 同页错误条（error_text 中文文案）+ 保留输入。

**校验链**（与 P-A import 同模式）：
`fields` → `_config_from_form(fields)` → `resolve()` 试跑 → 失败渲染错误条回解析页；成功 302 回填。

## 5. 错误与降级

- 空输入/无数字行：recognized=0 → 摘要「未识别到算式」+ 回填按钮禁用。
- resolve 失败：错误条 + 输入保留。
- 混合输入：多数为准。
- 全角/变体运算符：归一后解析。
- 负数前导：不特殊支持。

## 6. 测试

新增：
- `tests/test_parser.py` 表驱动：算术行 / 竖式折叠 / 应用题检测 / 混合 majority / 无数字 / 括号率阈值 / 位数分布 / grade 映射 / operand_count 众数（含钳制）/ 变体运算符归一（`x ✕ *` → ×、全角 −）/ 题号清洗（`1.` `(1)` `①`）/ count=max(N,10) / **3 项链式行 → operand_count=3**。
- `tests/test_ai.py`（TestClient）：POST 解析渲染摘要 + 回填按钮；resolve 失败错误条；302 回填 query 断言（grade/topic/operators/operand_count/parentheses/result_range——**result_range 断言仅对 ± 例题成立**）；fields 空禁用按钮；公开无门禁。
- `tests/test_ui_playwright.py` 追加：粘贴 5 行 → 解析 → 摘要断言 → 点回填 → 表单值断言（grade/topic/operators 选中态）。

更新：
- `tests/test_web.py::test_placeholder_pages`、`test_member_home_has_ai_coming_soon`（P-B 文件 tests/test_mistakes.py）：AI 卡 → 真实链接 /member/ai。
- i18n 完整性测试自动纳入新键；Yozai 字体重生成。

## 7. 明确不做（YAGNI）

- OCR/拍照解析、LLM。
- 竖式布局检测、carry/borrow/应用题四角色推断。
- 解析历史、多语言例题解析（英文题面数字/运算符仍可识别）。

## 8. 实现顺序建议（供计划参考）

1. parser.py 纯函数 + 表驱动单测
2. /member/ai 页面 + /api/ai/parse 端点 + 校验链 + i18n
3. 首页 AI 卡链接改造 + P-B 测试更新
4. Playwright 回填链路 + 字体重生成 + 全量回归
