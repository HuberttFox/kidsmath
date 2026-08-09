# 用户指南

面向家长与老师的 mathgen（Kids Math）使用说明：网页出题、会员功能、PWA 安装与命令行用法。安装与环境准备见根目录 [README.md](../README.md)，部署见 [deployment.md](deployment.md)，接口细节见 [api.md](api.md)。

## 快速开始（网页）

```bash
uv sync
uv run mathgen-serve --host 0.0.0.0 --port 8080
```

浏览器打开 `http://127.0.0.1:8080`（本机调试用 `http://127.0.0.1:8080` 即可）：

1. 选**年级**（1-6 一键套用预设）或「自定义」；
2. 选**题型**（口算 / 竖式 / 应用题）并微调参数（运算数范围、进位/借位、题目数等）；
3. 点「生成」→ 页面预览题目；
4. 点「下载 PDF」；多份卷子（`sheets > 1`）时出现「下载 zip」。

生成、预览与下载**无需登录**。

## 生成流程

```mermaid
flowchart LR
    A[选年级/参数] --> B[resolve 合并预设+校验]
    B --> C[generate 随机出题]
    C --> D[预览]
    D --> E[下载 PDF / zip]
```

- **年级预设一键套用**：每个年级内置一套推荐参数（运算符、运算数范围、进位/借位、答案线数等）；显式勾选或填写的参数会**覆盖**预设。
- **seed 固定**：生成时会自动确定随机种子并写入下载链接；预览与下载共用同一个 seed，因此**看到的题目与下载到的一致**。链接可分享、可复现。
- 登录后生成会**自动记入历史**（上限 200 条），可在「我的历史」一键重新生成。

## 题型

| 题型 | 说明 | 典型用途 |
|---|---|---|
| `arithmetic` 口算 | 纯算式（如 `23 + 45 =`），无竖式布局 | 每日口算训练 |
| `vertical` 竖式 | 带精确竖式布局（进位/借位） | 竖式计算练习 |
| `word_problem` 应用题 | 模板池生成带情境的文字题 | 应用题综合 |

## 会员功能（登录后）

顶部/侧栏登录后可用以下页面：

| 页面 | 功能 |
|---|---|
| `/member/worksheet` 在线答题 | 按参数生成在线答题卷：可选**实时判断**（输入即对错反馈），交卷后显示得分与用时、展开错题解题步骤，并**自动把错题写入错题本** |
| `/member/errors` 错题本 | 全部 / 待复习 / 已掌握三种过滤；统计题型、运算符分布；可加笔记、标记掌握/取消、删除、**重出原题或变式预览**、导出单题或批量 PDF |
| `/member/review` SM-2 复习 | 到期错题单卡队列，三档自评（忘记 1 / 模糊 3 / 记住 5）驱动间隔重复；可**改期**重排 |
| `/member/timer` 计时器 | 倒计时 / 正计时（分钟、秒） |
| `/member/pomodoro` 番茄钟 | 专注/休息番茄记录、每日目标、月历与连续天数；**记录与目标仅在登录后保存**，未登录也可临时使用 |
| `/member/ai` 例题解析 | 粘贴一段例题文本，**本地正则**自动推断年级、题型、运算符、范围等出题配置并回填表单（非 LLM，无需联网） |

## 用户数据

| 页面/操作 | 说明 |
|---|---|
| `/user` 概览 | 生成次数、错题统计、番茄专注统计、保存配置数；主题/语言偏好 |
| `/user/history` 历史记录 | 已生成的配置快照列表（上限 200，登录后自动记录）；可查看题目详情、重新生成、删除、把该次题目加入错题本 |
| `/user/saved` 保存配置 | 把常用参数命名保存；一键套用、重命名、删除 |
| 配置导入/导出 | 表单内「导出配置 / 导入配置」：单次出题参数 JSON（公开可用） |
| **设置备份/恢复** | `/user` 页「导出设置」下载 zip（settings.json + 全部音频），「导入设置」整体恢复（含音乐）；需登录，导入前会先完整校验 |
| 账号 | 修改密码、删除账号（同时删除数据与上传文件） |

## PWA 安装

浏览器地址栏或菜单选「**安装应用**」即可像 App 一样使用。注意：

- 仅在 **https 或 localhost** 下可用；局域网 `http://<IP>:8080` 不显示安装入口，属浏览器限制；
- Service Worker 预缓存 `/`、`/product`、`/guide`、`/docs` 与 `/static/` 资源，可**离线**打开这些页面；
- 需登录的页面（`/user/*`、`/member/*`）与 `/api/*`、`/download.*` 一律**走网络**，不做离线缓存；
- 安卓 TWA（桌面图标版）见 [android.md](android.md)。

## CLI 用法

命令入口为 `mathgen`（默认子命令 `generate`，裸 `mathgen --grade 2 ...` 等价于 `mathgen generate --grade 2 ...`）。不传任何参数时为 `generate`。子命令 `serve` 启动网页。

### generate 参数

| 参数 | 取值 | 默认 | 说明 |
|---|---|---|---|
| `-g, --grade` | 1-6 | — | 年级预设，一键套用推荐参数 |
| `-t, --topic` | `arithmetic` / `vertical` / `word_problem` | `arithmetic` | 题型 |
| `-o, --operators` | 字符串 | 预设 | 运算符，如 `+-×÷`（也接受「加减乘除」） |
| `-n, --count` | 整数 | `20` | 题目数（上限 500） |
| `--operand-count` | 2-4 | `2` | 运算数个数 |
| `--ranges` | 逗号分隔范围 | 预设 | 每个运算数范围，如 `10-99,2-9` |
| `--result-range` | `lo-hi` | 推导 | 结果范围，如 `0-100` |
| `--carry` | `yes` / `no` / `any` | 预设 | 是否进位 |
| `--borrow` | `yes` / `no` / `any` | 预设 | 是否借位 |
| `--divisor-range` | `lo-hi` | `1-9` | 除数范围，如 `2-9` |
| `--dividend-range` | `lo-hi` | — | 被除数范围，如 `10-99` |
| `--left-factor-range` | `lo-hi` | — | 第一个因数范围（`a × b` 中 a） |
| `--right-factor-range` | `lo-hi` | — | 第二个因数范围（`a × b` 中 b） |
| `--remainder` | 标志 | 关 | 允许余数 |
| `--table` | `lo-hi` | `1-9` | 乘法表/商范围，如 `1-9` |
| `--seed` | 整数 | 随机 | 随机种子，固定后结果可复现 |
| `--no-dedupe` | 标志 | 关 | 关闭同题去重 |
| `--columns` | 1 / 2 / 3 | `2` | 分栏数 |
| `--gap` | 整数(pt) | 按题型 | 题间距 / 答题线留白，见下「gap 语义」 |
| `--answer-lines` | 整数 | 按题型 | 每题答题横线数 |
| `--no-answer-page` | 标志 | 答案页开 | 不生成答案页 |
| `--no-numbers` | 标志 | 显示题号 | 不显示题号 |
| `--number-direction` | `row` / `column` | `row` | 编号方向：横向 / 竖向 |
| `--title` | 字符串 | 自动 | 卷子标题 |
| `--header` | 字符串 | 自动 | 页眉（姓名/班级/日期） |
| `--sheets` | 整数 | `1` | 生成几份不重复卷子（上限 100） |
| `--lang` | `zh` / `en` | `zh` | 题目语言 |
| `--op-weights` | 字符串 | — | 运算符权重，如 `+=5,-=3,×=2`（`0` 表示排除） |
| `--parentheses` | 标志 | 关 | 混合运算带括号 |
| `--no-parentheses` | 标志 | — | 显式不带括号 |
| `--paren-weight` | 1-10 | `5` | 括号权重，越大括号题越多（配合 `--parentheses`） |
| `--zip` | 标志 | 关 | 多份时打包为 zip |
| `--format` | `text` / `pdf` | `pdf` | 输出格式（`text` 直接打印到终端） |
| `-f, --output` | 路径 | `math-sheet` | 输出路径；多份时作为文件名前缀 |
| `-c, --config` | TOML 路径 | — | 配置文件，其中 `table = [1, 9]` 用数组形式 |

### 常见示例

```bash
# 单份卷子
mathgen generate --grade 2 --count 50 -f 二年级练习.pdf

# 多份不重复卷子（输出 竖式-01.pdf … 竖式-05.pdf）
mathgen generate --grade 3 --topic vertical --count 20 --sheets 5 -f 竖式

# zip 打包多份
mathgen generate --grade 3 --topic vertical --count 20 --sheets 5 --zip

# TOML 配置（见 examples/grade2.toml）
mathgen generate -c examples/grade2.toml -f 练习.pdf

# 终端打印纯文本题目（不生成文件）
mathgen generate --grade 2 --count 5 --format text

# 启动网页界面
mathgen serve --host 0.0.0.0 --port 8080
```

## 输出

- **PDF**（默认）：A4 排版，含卷子 + 独立答案页（`--no-answer-page` 可去掉答案页）；
- **text**：终端打印算式文本，便于快速查看/导入；
- **zip**：多份卷子（`--sheets > 1`）时可打包 `sheet-01.pdf …`，一份 zip 方便分发。

**gap 语义**：`--gap` 无答题线时是**题与题之间的间距**；有答题线时（`--answer-lines > 0`）则把该值**均分到每道题的答题线间隔**，即额外书写留白。

## 语言切换

- 网页界面：右上角切换 中文 / English，即时生效（客户端 `[data-i18n]` 切换，偏好存 cookie，登录后跨设备跟随）。
- CLI 题目语言：`--lang zh`（默认）或 `--lang en`，影响标题、页眉与题干。
