# mathgen 包

mathgen（小学数学出题工具）的 Python 包源码：按年级与参数随机生成 1-6 年级数学题（口算/竖式/应用题），输出 PDF 卷子与答案页，并提供 CLI 与 FastAPI 网页双入口。纯规则生成，无 LLM。

## 模块

| 模块 | 职责 |
|---|---|
| `config.py` | 参数模型（`Config`/`ResolvedConfig`）与校验、年级预设合并 |
| `cli.py` | CLI 入口 `mathgen`（`generate`/`serve` 子命令） |
| `web.py` | FastAPI 网页入口 `mathgen-serve`：表单 → 预览 → PDF/zip 下载 |
| `db.py` | SQLite 数据层：用户/会话/历史/保存/错题/音频（单例连接 + Lock） |
| `auth.py` | pbkdf2 密码哈希 + 会话 token |
| `sm2.py` | 简化 SM-2 间隔重复算法（q∈{1,3,5}） |
| `parser.py` | 例题文本 → 出题配置推断（零依赖正则规则） |
| `i18n.py` | 中/英文案与错误消息字典，zh 默认 |
| `core/question.py` | `Question` 数据类（题面/答案/规范化算式/layout/steps） |
| `core/engine.py` | 随机出题引擎：题型分派、去重、seed 复现 |
| `topics/arithmetic.py` | 口算/四则混合题 |
| `topics/vertical.py` | 竖式题（layout 供 PDF 精确绘制） |
| `topics/word_problem.py` | 应用题（生活场景模板池） |
| `topics/steps.py` | 已生成答案的分步解题步骤（纯函数，无随机） |
| `output/text.py` | 分栏/编号方向布局（`arrange`，PDF/预览共用）+ 纯文本渲染 |
| `output/pdf.py` | reportlab A4 卷子渲染：布局/标题/答题线/答案页/竖式 |
| `output/answer.py` | 答案页行生成 |
| `output/fonts.py` | PDF 中文字体回退链：包内字体 → 系统字体 → CID 兜底 |

## 设置与测试

```bash
uv sync                        # 安装依赖（Python ≥3.11，uv 管理）
uv run pytest                  # 跑全部测试（testpaths=tests）
```

开发工作流、依赖分组与测试约定见 [../../docs/development.md](../../docs/development.md)。

## 相关文档

- [../../README.md](../../README.md) — 项目总览与快速上手
- [../../docs/architecture.md](../../docs/architecture.md) — 架构与数据流
- [../../docs/development.md](../../docs/development.md) — 开发指南与测试
