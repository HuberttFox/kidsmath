# 小学数学出题工具 (mathgen) 设计文档

- 日期: 2026-08-06
- 状态: 已确认

## 1. 定位与目标

面向小学生家长/老师的数学练习题生成工具：按年级与可调参数随机出题，输出可打印 A4 PDF 卷子与答案页，带网页界面方便分享。纯规则生成，不用 LLM。

**已确认需求**（用户确认）：
- 年级全覆盖：1-6 年级
- 题型：口算/四则、竖式、应用题（数字加减乘除即可）
- 输出：可打印 PDF + 答案页（无步骤解析）
- 使用场景：产品化，分享给他人（网页界面），CLI 保留给高级用户
- Python 3.11+（内置 tomllib）
- 参数体系要丰富、可控
- 无其他需求（不做错题本、题库历史、Excel 导出）

## 2. 架构总览

单一引擎，双入口：

```
src/mathgen/
├── __init__.py
├── cli.py            # CLI 入口 (console script: mathgen)
├── web.py            # FastAPI 入口 (console script: mathgen-serve)
├── config.py         # 参数 dataclass + 校验 + grade 预设表
├── core/
│   ├── engine.py     # 随机生成主流程：seed、去重、按位生成
│   ├── question.py   # Question(statement, answer, 可选 explain)
│   └── presets.py    # 年级 1-6 预设
├── topics/
│   ├── arithmetic.py   # 口算/四则
│   ├── vertical.py     # 竖式
│   └── word_problem.py # 应用题（模板池）
├── output/
│   ├── pdf.py        # reportlab A4 排版
│   ├── text.py       # 调试用纯文本
│   └── answer.py     # 答案页生成
├── templates/index.html   # 网页表单
├── static/                # 少量 CSS
├── assets/font/           # 打包的 Noto Sans SC 子集
└── pyproject.toml
```

数据流：`参数(CLI/配置文件/网页表单) → config.py 校验 → 引擎生成 (题目, 答案) 列表 → output 层渲染 PDF/文本 → 下载`。

三层参数优先级：**年级预设 < 配置文件 < 显式 CLI/表单参数**。

## 3. 参数体系（核心）

### 3.1 年级预设（--grade 1..6）

| 年级 | 默认内容 |
|------|----------|
| 1 | 20 以内加减，无进位为主 |
| 2 | 100 以内进退位加减、乘法口诀 1-9 |
| 3 | 三位数加减、两位数×一位数、整除/带余除法 |
| 4 | 三位数×两位数、四位数÷两位数 |
| 5 | 更大数、四则混合 2-3 步 |
| 6 | 混合运算带括号、更大范围 |

### 3.2 可调参数

**运算**
- `operators`: + − × ÷ 任意组合（字符串形式，如 `"+-"`、`"×÷"`）
- `operand_count`: 2-4
- `parentheses`: 混合运算括号开关

**数值**
- `operand_ranges`: 每个运算数独立范围（如三位数×一位数）
- `result_range`: 结果范围约束
- `allow_negative`: 默认 false
- `allow_decimal`: 默认 false

**小学数学专用**
- `carry`/`borrow`: 进位/借位开关（逐位生成控制）
- `division`: 除数范围、`allow_remainder` 开关、整除开关
- `multiplication_table`: 口诀表范围（如 1-9）

**生成**
- `count`: 题目数
- `seed`: 随机种子（可复现）
- `dedupe`: 同卷去重（算式标准化签名）

**输出**
- `columns`: 每页分栏数
- `gap`: 题与题之间垂直间距（pt），调大留写步骤空间；默认按题型区分（口算/竖式紧凑，应用题/混合运算宽松）
- `answer_lines`: 每题下方预留答题横线数（写步骤/竖式用），0 = 不预留
- `answer_page`: 答案页开关
- `title`: 卷子标题
- `header`: 页眉（班级/姓名栏）
- `sheets`: 一次生成几份不重复卷子（班级用），命名 sheet-01.pdf…

**校验规则**：范围 min<max、运算符合法、结果范围与数值范围兼容、count>0。错误信息中文，非法组合给修正建议。

## 4. 题型设计

### 4.1 口算/四则（arithmetic）
`operand_count` 个数 + `operators` 组合，按约束生成。结果按运算顺序计算。混合运算含括号开关。

### 4.2 竖式（vertical）
题目渲染为上下对齐数字 + 运算符 + 横线。加/减/乘/除四类；除法竖式用标准除号格式（除数）厂（被除数）结构。答案 = 结果。

### 4.3 应用题（word_problem）
生活场景模板池（水果、文具、跑步等），数字槽位走同一随机引擎，运算即加减乘除。输出：文字题 + 答案页显示算式和结果。

## 5. 随机引擎

- **按位生成**控制进位/借位：个位/十位分别约束（不进位加法 = 个位和<10），比拒绝采样可控
- **去重**：算式标准化后哈希（如 3+5 与 5+3 视是否允许交换律决定是否同签名）
- **seed** 固定 → 输出可复现
- 约束冲突时抛中文错误（如"要求进位但范围只有个位数"）

## 6. 输出层

- **PDF（reportlab）**：A4；标题/页眉；分栏布局；竖式用绘图原语（对齐+横线）；答案页独立页
- **间距与答题区**：`gap` 控制题间距；`answer_lines` > 0 时每题下方画答题横线（口算/竖式默认 0，应用题默认 2）
- **中文渲染**：打包 Noto Sans SC 子集（OFL 协议，fonttools 子集化 ~2MB），跨平台无缺字
- **text**：调试/CLI 预览用

## 7. 网页层（FastAPI）

- `GET /`：中文表单页（年级一键预设 + 高级参数折叠区）
- `POST /generate`：校验 → 生成 → 返回题目预览
- `GET /download`：PDF 下载；多份卷子 → zip
- 错误在页面中文展示
- 技术：FastAPI + uvicorn + Jinja2；无前端框架
- 启动：`mathgen serve --host 0.0.0.0 --port 8080`，文档覆盖局域网分享与公网部署

## 8. CLI

```
mathgen --grade 2 --operators "+-" --count 50 --format pdf --output sheet.pdf
mathgen --grade 3 --topic vertical --count 20 --sheets 5 --outdir ./class3
mathgen -c config.toml        # TOML 配置（tomllib）
```
CLI 参数覆盖配置文件；中文 help。

## 9. 错误处理

- 参数校验：config.py 集中校验，中文报错 + 修正建议
- 生成冲突（如进位要求与范围矛盾）：明确中文异常
- 网页层：校验错误回显表单，不 500
- CLI：非零退出码 + 中文 stderr

## 10. 测试策略（pytest）

- 每题型：生成 N 组，断言 (题, 答) 恒成立（用独立计算验证）
- 约束测试：进位/借位开关生效、范围约束生效、整除/余数开关生效
- 去重测试：同卷无重复
- seed 复现测试
- 校验测试：非法参数报中文错
- PDF 冒烟：生成不抛错、文件头 %PDF
- 竖式/应用题渲染测试

## 11. 实施分期

| 阶段 | 内容 |
|------|------|
| P1 | 项目骨架、config/presets、口算引擎、text/PDF 输出+答案页、测试 |
| P2 | 竖式、应用题 + 测试 |
| P3 | 网页表单 + 下载端点 + 批量 zip |
| P4 | 打包（console scripts）、README/示例、部署文档 |

每期结束可交付可运行版本。

## 12. 非目标（YAGNI）

- 不用 LLM 生成题目
- 不做分数/几何/方程题型（后续可扩展，架构预留 topics/ 目录）
- 不做错题本、题库历史、Excel 导出、用户系统
- 不做移动端原生应用
