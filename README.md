# kidsmath — 小学数学出题工具

按年级与参数随机生成 1-6 年级数学题（口算/竖式/应用题），输出可打印 A4 PDF 卷子与答案页。CLI 与网页双入口，纯规则生成，无 LLM。

## 快速上手

推荐使用 uv（Python ≥3.11）：

```bash
uv sync
uv run mathgen generate --grade 2 --count 50 -f 练习.pdf
uv run mathgen-serve --host 0.0.0.0 --port 8080
```

- CLI 出题：`mathgen generate` 写 PDF（`-f` 指定输出路径），参数与示例见 [docs/user-guide.md](docs/user-guide.md)。
- 网页：`mathgen-serve` 启动后打开 http://127.0.0.1:8080 ，选年级/参数 → 生成 → 预览 → 下载 PDF/zip。
- pip 备选：`pip install -e .` 可做基础安装；完整开发环境建议 `uv sync`（见 [docs/development.md](docs/development.md)）。

## 功能要点

- 三种题型：口算、竖式、应用题；年级预设一键套用，显式参数覆盖。
- seed 复现：`--seed` 指定随机种子，生成/预览/下载共用，保证题目一致。
- 多份打包：`--sheets` 生成多份不重复卷子，可 zip 打包下载。
- PWA 可安装：https 或 localhost 下「安装应用」像 App 一样使用（详见 [docs/deployment.md](docs/deployment.md)）。
- 用户系统：登录、历史与保存配置、在线答题、错题本（SM-2 间隔复习）、番茄钟。
- 国际化：中文（默认）/英文双语界面与明暗主题。

## 文档导航

| 文档 | 内容 | 面向 |
|---|---|---|
| [docs/README.md](docs/README.md) | 文档总览与导航 | 所有人 |
| [docs/user-guide.md](docs/user-guide.md) | 使用指南：参数/CLI/网页操作 | 终端用户 |
| [docs/architecture.md](docs/architecture.md) | 架构、数据流与模块 | 开发者 |
| [docs/api.md](docs/api.md) | HTTP API 参考 | 开发者 |
| [docs/database.md](docs/database.md) | SQLite 表结构与备份 | 开发者/运维 |
| [docs/development.md](docs/development.md) | 开发环境、测试与贡献 | 开发者 |
| [docs/deployment.md](docs/deployment.md) | 部署、Docker、备份与恢复 | 运维 |
| [docs/android.md](docs/android.md) | 安卓 TWA 打包 | 运维 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 常见问题排查 | 所有人 |
| [docs/contributing.md](docs/contributing.md) | 贡献指南 | 贡献者 |
| [src/mathgen/README.md](src/mathgen/README.md) | 包级模块表 | 开发者 |

终端用户从 [docs/user-guide.md](docs/user-guide.md) 开始；开发者看 [docs/development.md](docs/development.md) 与 [docs/api.md](docs/api.md)；部署运维看 [docs/deployment.md](docs/deployment.md)。

## 许可

网页与 PDF 界面字体悠哉圆体（Yozai）使用 [SIL OFL 1.1](src/mathgen/static/fonts/OFL-yozai.txt) 许可，本地托管离线可用。

## 链接

- [docs/README.md](docs/README.md) — 文档入口
- [docs/deployment.md](docs/deployment.md) — 部署与备份
- [docs/android.md](docs/android.md) — 安卓 App（TWA 联网版）
- [设计文档](docs/superpowers/specs/2026-08-06-mathgen-design.md) — 2026-08-06 产品设计
