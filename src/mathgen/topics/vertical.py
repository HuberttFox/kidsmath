"""竖式题：加减乘除，layout 供 PDF 精确绘制。"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.engine import check_result, gen_operand, gen_pair, gen_result, pick_op
from mathgen.core.question import Question


def _stmt_add(op: str, a: int, b: int) -> str:
    w = max(len(str(a)), len(str(b))) + 1
    return f"{op} {a:>{w - 1}}\n{b:>{w}}\n{'-' * w}"


def gen(cfg: ResolvedConfig, rng: random.Random) -> Question:
    op = pick_op(rng, cfg)
    if op in "+-":
        # 偏离 brief：+ 恒传 allow_negative=True，与 arithmetic.py 一致。
        def make():
            a, b = gen_pair(rng, cfg.operand_ranges,
                            cfg.carry if op == "+" else None,
                            cfg.borrow if op == "-" else None,
                            True if op == "+" else cfg.allow_negative)
            return a, b, (a + b if op == "+" else a - b)

        a, b, result = gen_result(make, lambda t: check_result(cfg)(t[2]), *cfg.result_range)
        layout = {"kind": "vertical", "op": op, "numbers": [str(a), str(b)]}
        return Question("vertical", _stmt_add(op, a, b), str(result),
                        f"{a} {op} {b}", layout)
    if op == "×":
        if cfg.explicit_table or not cfg.explicit_ranges:
            lo, hi = cfg.multiplication_table

            def make():
                a = gen_operand(rng, lo, hi)
                b = gen_operand(rng, lo, hi)
                return a, b, a * b
        else:
            lo0, hi0 = cfg.operand_ranges[0]
            lo1, hi1 = cfg.operand_ranges[1]

            def make():
                a = gen_operand(rng, lo0, hi0)
                b = gen_operand(rng, lo1, hi1)
                return a, b, a * b

        a, b, result = gen_result(make, lambda t: check_result(cfg)(t[2]), *cfg.result_range)
        layout = {"kind": "vertical", "op": "×", "numbers": [str(a), str(b)]}
        return Question("vertical", _stmt_add("×", a, b), str(a * b),
                        f"{a} × {b}", layout)
    # ÷
    lo0, hi0 = cfg.operand_ranges[0]
    q_lo, q_hi = cfg.multiplication_table
    if cfg.explicit_table or cfg.explicit_divisor or not cfg.explicit_ranges:
        d_lo, d_hi = cfg.divisor_range
    else:
        d_lo, d_hi = cfg.operand_ranges[1]

    def make():
        divisor = gen_operand(rng, d_lo, d_hi)
        quotient = gen_operand(rng, q_lo, q_hi)
        remainder = gen_operand(rng, 0, divisor - 1) if cfg.allow_remainder else 0
        if rng.random() < 0.5:
            remainder = 0
        dividend = divisor * quotient + remainder
        return divisor, quotient, remainder, dividend

    divisor, quotient, remainder, dividend = gen_result(
        make, lambda t: lo0 <= t[3] <= hi0 and check_result(cfg)(t[1]),
        *cfg.result_range)
    layout = {"kind": "vertical", "op": "÷", "divisor": str(divisor),
              "dividend": str(dividend), "quotient": str(quotient),
              "remainder": str(remainder)}
    answer = str(quotient) if remainder == 0 else f"{quotient} {"R" if cfg.lang == "en" else "余"} {remainder}"
    stmt = f"{dividend} ÷ {divisor} = ____"
    return Question("vertical", stmt, answer, f"{dividend} ÷ {divisor}", layout)
