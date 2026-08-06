"""mathgen CLI：出题、批量、serve。"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from mathgen.config import Config, ConfigError, resolve
from mathgen.core.engine import GenerationError, generate
from mathgen.output.pdf import render_pdf
from mathgen.output.text import render_text


def _parse_argv(argv: list[str] | None) -> argparse.Namespace:
    if argv is None:
        argv = list(sys.argv[1:])
    if not argv or argv[0] not in ("generate", "serve"):
        argv = ["generate", *argv]
    p = argparse.ArgumentParser(
        prog="mathgen", description="小学数学练习题生成：口算/竖式/应用题，PDF + 答案页。")
    sub = p.add_subparsers(dest="sub")
    gen = sub.add_parser("generate", help="生成卷子（默认）")
    gen.add_argument("-g", "--grade", type=int, default=None, help="年级 1-6，一键预设")
    gen.add_argument("-t", "--topic", default=None,
                     choices=["arithmetic", "vertical", "word_problem"], help="题型")
    gen.add_argument("-o", "--operators", default=None, help="运算符，如 +-×÷")
    gen.add_argument("-n", "--count", type=int, default=None, help="题目数")
    gen.add_argument("--operand-count", type=int, default=None, help="运算数个数 2-4")
    gen.add_argument("--ranges", default=None, help="运算数范围，如 10-99,2-9")
    gen.add_argument("--result-range", default=None, help="结果范围，如 0-100")
    gen.add_argument("--carry", choices=["yes", "no", "any"], default=None, help="进位")
    gen.add_argument("--borrow", choices=["yes", "no", "any"], default=None, help="借位")
    gen.add_argument("--divisor-range", default=None, help="除数范围，如 2-9")
    gen.add_argument("--remainder", action="store_true", default=None, help="允许余数")
    gen.add_argument("--table", default=None, help="乘法表/商范围，如 1-9")
    gen.add_argument("--seed", type=int, default=None, help="随机种子")
    gen.add_argument("--no-dedupe", action="store_true", help="关闭去重")
    gen.add_argument("--columns", type=int, default=None, choices=[1, 2, 3], help="分栏")
    gen.add_argument("--gap", type=int, default=None, help="题间距 pt")
    gen.add_argument("--answer-lines", type=int, default=None, help="每题答题横线数")
    gen.add_argument("--no-answer-page", action="store_true", help="不要答案页")
    gen.add_argument("--title", default=None, help="卷子标题")
    gen.add_argument("--header", default=None, help="页眉")
    gen.add_argument("--sheets", type=int, default=None, help="生成几份不重复卷子")
    gen.add_argument("--zip", action="store_true", help="多份时打包 zip")
    gen.add_argument("--format", choices=["text", "pdf"], default="pdf")
    gen.add_argument("-f", "--output", default=None, help="输出路径（多份时为前缀）")
    gen.add_argument("-c", "--config", default=None, help="TOML 配置文件")
    serve = sub.add_parser("serve", help="启动网页界面")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    ns = p.parse_args(argv)
    if ns.sub is None:
        ns.sub = "generate"
    return ns


def _parse_range(s: str) -> tuple[int, int]:
    try:
        lo, hi = s.split("-")
        return int(lo), int(hi)
    except ValueError:
        raise ConfigError(f"范围格式应为 最小-最大，如 10-99（收到 {s!r}）。") from None


def _cfg_from_ns(ns: argparse.Namespace) -> Config:
    data: dict = {}
    if ns.config:
        with open(ns.config, "rb") as f:
            data = dict(tomllib.load(f))
        if "table" in data:
            data["multiplication_table"] = tuple(data.pop("table"))
    overrides = {
        "topic": ns.topic, "operators": ns.operators, "count": ns.count,
        "operand_count": ns.operand_count, "grade": ns.grade,
        "carry": {"yes": True, "no": False}.get(ns.carry),
        "borrow": {"yes": True, "no": False}.get(ns.borrow),
        "allow_remainder": ns.remainder, "seed": ns.seed,
        "dedupe": None if ns.no_dedupe is False else False if ns.no_dedupe else None,
        "columns": ns.columns, "gap": ns.gap, "answer_lines": ns.answer_lines,
        "answer_page": False if ns.no_answer_page else None,
        "title": ns.title, "header": ns.header, "sheets": ns.sheets,
    }
    if ns.ranges:
        overrides["operand_ranges"] = [_parse_range(s) for s in ns.ranges.split(",")]
    if ns.result_range:
        overrides["result_range"] = _parse_range(ns.result_range)
    if ns.divisor_range:
        overrides["divisor_range"] = _parse_range(ns.divisor_range)
    if ns.table:
        overrides["multiplication_table"] = _parse_range(ns.table)
    data.update({k: v for k, v in overrides.items() if v is not None})
    try:
        return Config(**data)
    except TypeError as e:
        raise ConfigError(f"配置项有误：未知的配置键或类型错误（{e}）。") from None


def _generate_sheet(cfg: Config, sheet_no: int) -> bytes:
    resolved = resolve(cfg)
    if cfg.seed is not None:
        resolved.seed = cfg.seed + sheet_no - 1
    questions = generate(resolved)
    return render_pdf(questions, resolved)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_argv(argv)
    try:
        if ns.sub == "serve":
            from mathgen.web import serve
            serve(ns.host, ns.port)
            return 0
        cfg = _cfg_from_ns(ns)
        resolved = resolve(cfg)
        if ns.format == "text":
            questions = generate(resolved)
            print(render_text(questions, resolved))
            return 0
        sheets = resolved.sheets
        out = ns.output or f"math-sheet"
        if sheets == 1:
            data = render_pdf(generate(resolved), resolved)
            path = out if out.endswith(".pdf") else out + ".pdf"
            Path(path).write_bytes(data)
            print(f"已生成：{path}")
            return 0
        if ns.zip:
            import zipfile
            zpath = out + ".zip"
            with zipfile.ZipFile(zpath, "w") as z:
                for i in range(1, sheets + 1):
                    data = _generate_sheet(cfg, i)
                    z.writestr(f"sheet-{i:02d}.pdf", data)
            print(f"已生成 {sheets} 份卷子：{zpath}")
            return 0
        base = out[:-4] if out.endswith(".pdf") else out
        paths = []
        for i in range(1, sheets + 1):
            path = f"{base}-{i:02d}.pdf"
            Path(path).write_bytes(_generate_sheet(cfg, i))
            paths.append(path)
        print(f"已生成 {sheets} 份卷子：{' '.join(paths)}")
        return 0
    except ConfigError as e:
        print(f"参数错误：{e}", file=sys.stderr)
        return 2
    except (GenerationError, OSError) as e:
        print(f"生成失败：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
