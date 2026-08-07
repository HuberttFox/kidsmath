"""例题文本 → 出题配置推断（零依赖正则规则）。"""
from __future__ import annotations

import re

_EXPR = re.compile(r"(?:\d+\s*[+\-×÷*/xX✕＊＋－−]\s*)+\d+")
_NUM = re.compile(r"\d+")
_ANSWER = re.compile(r"\s*=\s*[\d.]+\s*$")
_OP_ALIAS = {"x": "×", "✕": "×", "*": "×", "×": "×", "÷": "÷",
             "−": "-", "－": "-", "＋": "+"}
_LINE_NUM = re.compile(r"^(?:\d+[.、]|[（(]\d+[)）]|①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩)\s*")
_CN = re.compile(r"[\u4e00-\u9fff]")


def _clean_line(line: str) -> str:
    s = line.strip()
    s = _LINE_NUM.sub("", s)
    return s.strip()


def _fold_vertical(lines: list[str]) -> list[str]:
    """竖式线性化：将 '23 / +48 / ----' 连续行折叠为 '23+48'。
    续行必须「算子+单个数字」（fullmatch，含全角变体）或纯横线；
    "-3+5"（两个数字）这类独立负号行不被吞。"""
    out: list[str] = []
    i = 0
    while i < len(lines):
        seg = [lines[i]]
        j = i + 1
        while j < len(lines) and (
                re.fullmatch(r"[+\-×÷*xX＋－＊−]\s*\d+\s*", lines[j])
                or (lines[j] and set(lines[j]) <= set("-—–"))):
            seg.append(lines[j])
            j += 1
        if len(seg) > 1:
            nums = [n for s in seg for n in re.findall(r"\d+", s)]
            ops = [c for s in seg[1:] for c in s if c in "+-×÷*xX＋－＊"]
            body = ""
            for k, n in enumerate(nums):
                if k:
                    body += (ops[k - 1] if k - 1 < len(ops) else "+")
                body += n
            if body:
                out.append(body)
            i = j
        else:
            out.append(lines[i])
            i += 1
    return out


def parse_examples(text: str) -> dict:
    lines = [_clean_line(x) for x in text.splitlines() if x.strip()]
    lines = _fold_vertical(lines)
    total = len(lines)
    rows: list[dict] = []
    for line in lines:
        expr_line = _ANSWER.sub("", line)
        m = _EXPR.search(expr_line)
        has_cn = bool(_CN.search(line))
        if m:
            expr = m.group(0)
            nums = _NUM.findall(expr)
            ops = []
            for ch in expr:
                if ch in "+-×÷*/x✕−＋－":
                    ops.append(_OP_ALIAS.get(ch, ch))
            rows.append({"expr": expr, "nums": nums, "ops": ops,
                         "has_cn": has_cn,
                         "paren": "(" in expr_line or "（" in line})
        elif has_cn and _NUM.search(line):
            rows.append({"expr": None, "nums": _NUM.findall(line), "ops": [],
                         "has_cn": True, "paren": "（" in line})
    n = len(rows)
    if n == 0:
        return {"fields": {}, "recognized": 0, "total": total,
                "notes": ["no_numbers"], "signals": {}}

    op_freq: dict[str, int] = {}
    digit_counts: list[int] = []
    operand_counts: list[int] = []
    paren_cnt = 0
    for r in rows:
        for op in r["ops"]:
            op_freq[op] = op_freq.get(op, 0) + 1
        digit_counts += [len(d) for d in r["nums"]]
        operand_counts.append(len(r["nums"]))
        if r["paren"]:
            paren_cnt += 1
    expr_rate = sum(1 for r in rows if r["ops"]) / max(total, 1)
    cn_ratio = sum(1 for r in rows if r["has_cn"]) / n
    digit_mode = max(digit_counts) if digit_counts else 1  # 最大位数（123+45 → 3）
    operand_mode = max(set(operand_counts), key=operand_counts.count)
    operand_mode = min(4, max(2, operand_mode))

    top_ops = [op for op, _ in sorted(op_freq.items(), key=lambda kv: -kv[1])][:2]
    fields: dict = {}
    if expr_rate >= 0.5:
        fields["topic"] = "arithmetic"
        fields["operators"] = "".join(top_ops)
        fields["grade"] = ("3" if any(o in "×÷" for o in top_ops) or digit_mode >= 3
                           else "2" if digit_mode >= 2 else "1")
        fields["operand_count"] = str(operand_mode)
        if paren_cnt / n > 0.3:
            fields["parentheses"] = "1"
        if all(o not in "×÷" for o in top_ops):
            fields["result_range"] = f"0-{10 ** digit_mode}"
    else:
        fields["topic"] = "word_problem"
        fields["grade"] = "1" if digit_mode <= 1 else "2"

    fields["count"] = str(max(n, 10))
    notes = []
    if total > n:
        notes.append("ignored_lines")
    return {"fields": fields, "recognized": n, "total": total,
            "notes": notes,
            "signals": {"op_freq": op_freq, "digit_mode": digit_mode,
                        "paren_rate": paren_cnt / n, "expr_rate": expr_rate,
                        "operand_mode": operand_mode, "n": n}}
