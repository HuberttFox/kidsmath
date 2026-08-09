# 文档中心

本目录是 mathgen（Kids Math）仓库的技术文档，面向开发者、维护者与自部署者。终端用户的使用帮助请用应用内 `/docs`（见下文区别）。

## 文档地图

| 文档 | 读者 | 内容 | 链接 |
| --- | --- | --- | --- |
| README.md（仓库根） | 所有用户 | 概述、快速上手、功能要点、文档导航、许可 | [../README.md](../README.md) |
| docs/README.md | 开发者 | 本文档：文档地图 + 约定 + 应用内/仓库文档关系 | [README.md](README.md) |
| architecture.md | 开发者 | 系统架构：双入口、配置模型、出题引擎、Web 层、i18n | [architecture.md](architecture.md) |
| user-guide.md | 终端用户 | 网页使用：参数、预览、下载、会员功能、CLI 参数 | [user-guide.md](user-guide.md) |
| api.md | 开发者 | HTTP 路由与 API 契约、query-string 参数往返 | [api.md](api.md) |
| database.md | 开发者 / 自部署者 | SQLite 表结构、连接行为、音频存储、备份 | [database.md](database.md) |
| deployment.md | 自部署者 | 局域网 / 公网 / Docker 部署、备份与恢复 | [deployment.md](deployment.md) |
| android.md | 安卓维护者 | TWA 包装、签名、APK 构建 | [android.md](android.md) |
| development.md | 贡献者 | 开发环境、测试约定、项目布局 | [development.md](development.md) |
| contributing.md | 贡献者 | 提交规范、新增题型流程、i18n 约定 | [contributing.md](contributing.md) |
| troubleshooting.md | 所有用户 | 常见问题排查（现象 → 原因 → 解决） | [troubleshooting.md](troubleshooting.md) |
| src/mathgen/README.md | 包维护者 | `src/mathgen` 包模块速览 | [../src/mathgen/README.md](../src/mathgen/README.md) |
| superpowers/specs/ | 架构师 | 设计规格归档（现状 / 目标 / 分期） | [superpowers/specs/](superpowers/specs/) |
| superpowers/plans/ | 实施者 | 实现计划归档（Claude Code 工作流写入路径） | [superpowers/plans/](superpowers/plans/) |

## 约定

- 中文第一语言：叙述用中文，代码、命令、标识符保留英文。
- 图表一律用 Mermaid fenced block，便于 GitHub 渲染与版本差异对比。
- superpowers 归档用途：`specs/` 放设计规格（现状 / 目标 / 分期），`plans/` 放实现计划；Claude Code 在重大改动前按「设计先行」工作流写入这两处路径。
- 同一目录内文档互相链接用相对文件名（如 `architecture.md`），不重复引用内容，用链接代替。

## 应用内 `/docs` 与仓库 `docs/` 的区别

- 应用内 `/docs`：FastAPI 渲染 `templates/docs.html`，文案走 i18n 字典（中英双语），面向终端用户介绍出题参数、输出格式、数据隐私与 FAQ。数据保存在本机 SQLite，用户可在「用户信息」页导出整体备份。
- 仓库 `docs/`：本目录，面向开发者与自部署者，描述实现细节与运维步骤。
- 两者互补、互不替代；应用内不链接本目录（离线 PWA 打包不含技术文档）。
