# 贡献指南

本文约定：改代码前先读，避免破坏既有的去重、参数往返、i18n 与测试隔离机制。环境搭建与测试命令见 [development.md](development.md)。

## 设计先行

- 重大改动先在 `docs/superpowers/specs/` 写设计文档（现状/目标/分期）。
- 实现计划放 `docs/superpowers/plans/`。
- 已有的设计/计划文档按日期命名，可参考最近一次迭代的写法。

## 提交规范

- 使用 conventional commits：`feat`/`fix`/`test`/`docs`/`refactor`…
- 提交消息中文。

## 语言约定

- 仓库文件、注释、错误消息以中文为第一语言；`en` 文案走 i18n 字典。
- 服务端：`src/mathgen/i18n.py` 的 `UI_ZH`/`UI_EN` 字典 + `t(key, lang)` 渲染模板；错误消息用 `error_text(code, params, lang)`。
- 客户端：`static/lang.js` 处理 `[data-i18n]` 属性动态切换，派发 `langchange`/`themechange` 事件（工作台 shell 收到后重载 iframe）。
- **新文案必须同时进 `UI_ZH` 与 `UI_EN` 两语言字典**，否则切英文时空缺。

## 新增题型

按以下步骤注册，缺一不可：

1. 建 `src/mathgen/topics/<name>.py`，暴露 `gen(cfg, rng)`（只消费引擎传入的 `rng`，保证 seed 复现）。
2. `config.py`：把题型名加进 `TOPICS` 元组；在 `TOPIC_DEFAULTS` 加默认 `gap`/`answer_lines`。
3. `core/engine.py`：在 `generate()` 的 `factory` 字典注册 `<name>: <name>.gen`。
4. `web.py`：在 `TOPIC_OPTIONS` 列表加 `(name, i18n_key)`；若需要别名（口算/竖式/应用题）同时维护 `TOPIC_ALIASES`。
5. 写测试（至少覆盖生成与去重），可参考 `tests/test_vertical.py`、`tests/test_word_problem.py` 的写法。

## 改 Config 字段

`web.py` 的两个函数必须同步维护：

- `_config_from_form(form)`：表单/JSON → `Config`（含范围 `"lo-hi"`、操作符串、权重等解析）。
- `_as_query(cfg)`：`Config` → query string（只序列化非默认值）。

历史记录、保存配置、错题 `params`、配置导入导出（`/api/config/export|import`）、`/download.pdf`、`/download.zip` 全部复用这套快照往返。只改一边会导致参数在「历史→重新生成」「保存→应用」链路中丢失或格式不匹配。

## 生成逻辑改动注意

- `core/engine.py` 的 `_signature()` 做去重签名：`×` 交换律归一（排序），`+ − ÷` 保持顺序，括号单独标记（剥括号但保留 parens 位，避免 `"(1+2)×3"` 与 `"1+2×3"` 误判）。
- `gen_pair()` 重试至多 1000 次，失败抛 `GenerationError("pair_no_solution")`；`gen_result()` 同理（`result_out_of_range`）。
- seed 复现约束：所有随机数只走引擎传入的 `rng`（`random.Random(cfg.seed)`），不要在 topics 里新建 `random` 实例。
- 改去重/生成前先读 `_signature` 与 `gen_pair` 的注释——有对 brief 的已知偏离：如 `+` 恒传 `allow_negative=True`（0–9 范围无序进位对仅 25 个 < 30 题去重需求），改动会波及这些边界。

## 测试约定

- `tests/conftest.py` 的 autouse fixture 给每个测试独立临时 SQLite（`db.configure(tmp_path)`），测试勿污染默认 `data/kidsmath.db`。
- 改生成逻辑（进位/借位/范围/去重/seed）优先跑 `tests/test_generation_matrix.py`（全年级×全题型恒等式，`(题,答)` 用独立求值验证）与 `tests/test_stress.py`（3000 题压力测试）。
- 新增 Web 接口参考 `tests/test_web.py`/`tests/test_mistakes.py` 的 `TestClient` 写法。

## 文档约定

- 文档中文优先；代码/命令/标识符用英文。
- 图表用 Mermaid。
- 新文档登记到 `docs/README.md` 地图；同目录内互链用相对文件名。
- 重大功能上线前确认与既有文档（`docs/architecture.md`、`docs/user-guide.md`、`docs/api.md`、`docs/database.md`、`docs/deployment.md`）的一致性。
