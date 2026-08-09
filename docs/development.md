# 开发指南

面向在本仓库搭建环境、跑测试、改代码的开发者。架构细节见 [architecture.md](architecture.md)，改动流程见 [contributing.md](contributing.md)。

## 环境要求

- Python ≥ 3.11（`pyproject.toml` 中 `requires-python = ">=3.11"`）
- 推荐使用 [uv](https://docs.astral.sh/uv/) 管理依赖，`uv.lock` 已提交仓库，可锁版本复现

## 安装

```bash
uv sync        # 安装全部依赖（含 dev 组）
```

`uv sync` 一次装齐运行与开发依赖。dev 组（`[dependency-groups].dev`）包含：pytest、httpx、playwright、pypdf、pillow。

可选：下载并子集化打包字体（无网络时自动跳过，走系统字体兜底）：

```bash
uv run python scripts/download_font.py     # PDF 用 Noto Sans SC 子集 → assets/font/
uv run python scripts/download_ui_font.py  # 网页 UI 用 Yozai 子集 → static/fonts/
```

pip 备选（基础安装，dev 依赖较少）：

```bash
pip install -e .
pip install -e ".[dev]"   # 只含 pytest/httpx；playwright/pypdf/pillow 仍需 uv sync 或手动安装
```

## 运行

```bash
# 网页（FastAPI + uvicorn）
uv run mathgen-serve --host 0.0.0.0 --port 8080

# CLI 出题
uv run mathgen generate --grade 2 --count 50 -f 练习.pdf
```

更多 CLI 参数见 [user-guide.md](user-guide.md)。

## 测试

```bash
uv run pytest                        # 全量（testpaths=tests）
uv run pytest tests/test_engine.py::test_seed_reproducible   # 单个测试
uv run pytest tests/test_ui_playwright.py                    # 浏览器 e2e（需先装浏览器）
uv run playwright install chromium   # 首次跑 e2e 前安装 Chromium
```

- e2e 通过 `pytest.importorskip("playwright.sync_api")` 优雅跳过：未安装 playwright/浏览器时整文件跳过，不阻塞全量。
- `tests/test_ui_playwright.py` 的 fixture 起本地 uvicorn（`127.0.0.1:18099`），用 Chromium 驱动真实点击，验证 JS 联动（年级预设回填、权重框禁用、语言/主题切换、生成-预览-下载全链路）。
- Docker 镜像构建不带测试依赖（`uv sync --no-dev`）。

## 测试隔离

`tests/conftest.py` 的 autouse fixture 给每个测试配置独立临时 SQLite：

```python
@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    db.configure(str(tmp_path / "test.db"))
    yield
    db.configure(None)
```

测试勿污染默认 `data/kidsmath.db`；`db.configure(None)` 在用例结束后重置单例连接。

## 测试文件地图

| 文件 | 覆盖内容 |
| --- | --- |
| `tests/test_ai.py` | `/member/ai` 页面、`/api/ai/parse` 与 `/api/ai/backfill` 回填流程 |
| `tests/test_arithmetic.py` | 口算题生成：运算符/进位/借位/括号/优先级求值 |
| `tests/test_auth.py` | pbkdf2 密码哈希往返、会话 token |
| `tests/test_cli.py` | CLI 子进程：`--help`、generate 参数解析 |
| `tests/test_config.py` | `resolve()` 三层优先级、`PRESETS` 预设、`ConfigError` |
| `tests/test_db.py` | SQLite 建表与增删查（users/sessions/history/saved 等） |
| `tests/test_engine.py` | `generate()` seed 复现、去重、结果范围 |
| `tests/test_fonts.py` | 打包 Noto 子集字体 cmap 覆盖 topics 全部非 ASCII 字符 |
| `tests/test_generation_matrix.py` | 全年级×全题型恒等式（`(题,答)` 独立求值）+ 关键参数组合大样本约束 |
| `tests/test_mistakes.py` | 错题 API：录入/列表/掌握/删除/笔记/改期 |
| `tests/test_mistakes_export.py` | 错题单题/批量合成 PDF（original/variant 两种模式） |
| `tests/test_output.py` | 文本渲染与 `answer_lines` 行排版 |
| `tests/test_parser.py` | 例题文本正则解析（`/member/ai` 回填） |
| `tests/test_pdf.py` | PDF 渲染（`render_pdf`/`_draw_vertical`、字体注册） |
| `tests/test_sm2.py` | SM-2 间隔重复状态更新 |
| `tests/test_steps.py` | 解题步骤：每题非空、末步含答案、多运算数括号题也带步骤 |
| `tests/test_stress.py` | 3000 题压力测试（乘法表/商/除数范围约束） |
| `tests/test_ui_fonts.py` | 网页 Yozai 子集覆盖全部 UI 文案汉字 |
| `tests/test_ui_playwright.py` | Playwright 真实浏览器 e2e（端口 18099） |
| `tests/test_userdata.py` | 用户数据导出/导入/清空/删号 |
| `tests/test_vertical.py` | 竖式题生成与 `layout` |
| `tests/test_web.py` | 网页路由：首页/下载/表单回显 |
| `tests/test_word_problem.py` | 应用题生成 |

## 项目布局

源码在 `src/mathgen/`（hatchling 打包 `packages = ["src/mathgen"]`）。`src/mathgen/` 各模块职责见 [architecture.md](architecture.md#模块表)，这里只补充网页层目录：

`templates/`：Jinja2 模板。壳页面 `index.html`（工作台 SPA 侧边栏 + `<iframe id="stage">`），其余页面以 `?embed=1` 加载；另含 form/preview/product/guide/docs/member\*/user\* 等页面。

`static/`：前端资源。

| 资源 | 说明 |
| --- | --- |
| `style.css` | 全局样式（亮/暗主题） |
| `lang.js` | `[data-i18n]` 客户端动态切换语言，派发 `langchange`/`themechange` |
| `timer.js` | 计时/番茄钟核心（去秒、后台节流处理） |
| `audio.js` | 提示音（WebAudio 振荡器，`playChime`） |
| `sound.js` | 环境音（白/粉/棕噪声 + 导入音乐，WebAudio + HTMLAudio） |
| `sw.js` | Service Worker（PWA 缓存） |
| `manifest.webmanifest` | PWA 清单 |
| `icons/`、`math-icon.svg`、`fonts/` | 图标与悠哉圆体 Yozai 子集（OFL） |

## 字体

- PDF（`output/fonts.py` `register_fonts()`）：包内 `assets/font/NotoSansSC-Regular.ttf` → 系统字体（Noto CJK / 文泉驿 / 微软雅黑 / 宋体 / 苹方 / 华文黑体）→ CID 兜底 `STSong-Light`。无系统字体时仍可输出，但回退到 CID 字形。
- 网页 UI：悠哉圆体 Yozai（`static/fonts/`，SIL OFL 1.1，许可见 `OFL-yozai.txt`），本地托管离线可用；未子集化的字符降级系统字体栈。

## PWA

- `static/sw.js` 缓存白名单：`/`、`/product`、`/guide`、`/docs` 与 `/static/` 下资源，缓存优先策略；其余请求走网络（含 `/user/*`、`/member/*`、`/login`、`/api/*`、`/generate`、`/download.*`）。
- `activate` 阶段自动删除旧版本缓存。**改动静态资源或缓存策略后必须 bump `CACHE` 版本号**（当前 `kidsmath-v11`），否则用户命中旧缓存。

## Docker 开发

```bash
docker compose up -d --build
```

- 多阶段构建（uv 锁版本，`--no-dev` 不带测试依赖），镜像以非 root 的 `mathgen` 用户运行。
- 命名卷 `mathgen-data` 挂载到 `/data`，保存 SQLite（`KIDSMATH_DB=/data/kidsmath.db`）与用户上传音频 `/data/user_audio/<uid>`。
- 健康检查轮询 `/healthz`，重启策略 `unless-stopped`。部署与备份细节见 [deployment.md](deployment.md)。

## 相关文档

- [contributing.md](contributing.md) — 改动流程与约定
- [architecture.md](architecture.md) — 架构与数据流
