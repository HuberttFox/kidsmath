# mathgen — 小学数学出题工具

按年级与参数随机生成 1-6 年级数学题（口算/竖式/应用题），输出可打印 A4 PDF + 答案页。CLI 与网页双入口。

## 安装

推荐使用 uv（Python ≥3.11），一次安装运行与完整开发依赖：

```bash
uv sync
# 可选：下载打包字体（无网络时用系统字体兜底）
uv run python scripts/download_font.py
```

也可用 pip 做基础的可编辑安装；`.[dev]` 只含 pytest/httpx，Playwright、PDF 与图像开发工具仍建议使用 `uv sync`：

```bash
pip install -e .
pip install -e ".[dev]"
```

## 命令行

```bash
mathgen generate --grade 2 --count 50 -f 二年级练习.pdf
mathgen generate --grade 3 --topic vertical --count 20 --sheets 5 --zip
mathgen generate --grade 4 --parentheses --paren-weight 8 -f 带括号练习.pdf
mathgen generate -c examples/grade2.toml --format text
mathgen serve --host 0.0.0.0 --port 8080
```

## 网页

运行 `mathgen serve` 后浏览器打开 http://127.0.0.1:8080 ：选年级/参数 → 生成 → 预览 → 下载 PDF；多份下载 zip。生成、预览和下载无需登录。

其他页面：
- `/product`、`/guide`、`/docs` — 产品介绍、使用指南与站内文档。
- `/member`、`/member/timer`、`/member/pomodoro`、`/member/ai` — 工具页；番茄钟的记录和目标仅在登录后保存。
- `/user`、`/user/history`、`/user/saved` — 账户概览、已生成记录、保存的配置，均需登录；登录后生成的试卷会自动记录。
- `/member/worksheet`、`/member/errors`、`/member/review` — 在线答题、错题本与 SM-2 复习，均需登录。

## 参数

年级预设一键套用，显式参数覆盖。常用：`--operators`（+-×÷ 组合）、`--ranges`（每个运算数范围，逗号分隔）、`--carry/--borrow`（yes/no/any）、`--remainder`、`--table`（乘法表/商范围）、`--divisor-range`、`--gap`（无答题线时为题间距；有横线时均分额外书写留白）、`--answer-lines`（每题答题横线）、`--seed`（复现）、`--sheets`（多份不重复卷子）。

括号权重 `--paren-weight`（1-10，默认 5）：配合 `--parentheses` 使用，控制括号题出现比重；权重越大括号题越多。

网页界面字体使用悠哉圆体（Yozai，SIL OFL 1.1，许可见 [OFL-yozai.txt](src/mathgen/static/fonts/OFL-yozai.txt)），本地托管离线可用。

PWA：`/static/manifest.webmanifest` + `/static/sw.js`。浏览器地址栏/菜单选「安装应用」即可像 App 一样使用（需要 https 或 localhost，详见 [部署文档](docs/deploy.md)）；Service Worker 缓存 `/`、`/product`、`/guide`、`/docs` 和 `/static/` 下的资源，其余请求走网络。

## Docker

```bash
docker compose up -d --build
```

Compose 将 SQLite 数据库和用户上传音频持久化到命名卷的 `/data`。部署、备份和恢复说明见 [docs/deploy.md](docs/deploy.md)。

详见设计文档 `docs/superpowers/specs/2026-08-06-mathgen-design.md`。

## 许可

悠哉圆体使用 SIL OFL 1.1 许可，见 [OFL-yozai.txt](src/mathgen/static/fonts/OFL-yozai.txt)。


## 安卓 App（联网版 TWA）

- 方案与构建步骤：`docs/android.md`
- TWA 以 `/?app=1` 启动，App 模式仅将站点 logo 指向首页，产品页导航仍可访问
- PNG 图标：`scripts/generate_icons.py`（Pillow，192/512 + maskable），manifest 已引用
