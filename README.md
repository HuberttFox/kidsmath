# mathgen — 小学数学出题工具

按年级与参数随机生成 1-6 年级数学题（口算/竖式/应用题），输出可打印 A4 PDF + 答案页。CLI 与网页双入口。

## 安装

```bash
pip install -e ".[dev]"
# 可选：下载打包字体（无网络时用系统字体兜底）
python scripts/download_font.py
```

本项目用 uv 管理，也可以：

```bash
uv sync
```

## 命令行

```bash
mathgen generate --grade 2 --count 50 -o 二年级练习.pdf
mathgen generate --grade 3 --topic vertical --count 20 --sheets 5 --zip
mathgen generate -c examples/grade2.toml --format text
mathgen serve --host 0.0.0.0 --port 8080
```

## 网页

运行 `mathgen serve` 后浏览器打开 http://127.0.0.1:8080 ：选年级/参数 → 生成 → 预览 → 下载 PDF；多份下载 zip。

## 参数

年级预设一键套用，显式参数覆盖。常用：`--operators`（+-×÷ 组合）、`--ranges`（每个运算数范围，逗号分隔）、`--carry/--borrow`（yes/no/any）、`--remainder`、`--table`（乘法表/商范围）、`--divisor-range`、`--gap`（题间距，写步骤留空）、`--answer-lines`（每题答题横线）、`--seed`（复现）、`--sheets`（多份不重复卷子）。

网页界面字体使用悠哉圆体（Yozai，SIL OFL 1.1，见 `src/mathgen/static/fonts/OFL-yozai.txt`），本地托管离线可用。

详见设计文档 `docs/superpowers/specs/2026-08-06-mathgen-design.md`。

## 许可

字体使用 SIL OFL 1.1 许可，见 src/mathgen/assets/font/OFL.txt。
