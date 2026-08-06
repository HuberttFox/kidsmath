"""竖式题：加减乘除，layout 供 PDF 精确绘制。"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.engine import gen_operand, gen_pair
from mathgen.core.question import Question


def _stmt_add(op: str, a: int, b: int) -> str:
    w = max(len(str(a)), len(str(b))) + 1
    return f"{op} {a:>{w - 1}}\n{b:>{w}}\n{'-' * w}"


def gen(cfg: ResolvedConfig, rng: random.Random) -> Question:
    op = rng.choice(list(cfg.operators))
    if op in "+-":
        # 偏离 brief：+ 恒传 allow_negative=True，与 arithmetic.py 一致。
        a, b = gen_pair(rng, cfg.operand_ranges,
                        cfg.carry if op == "+" else None,
                        cfg.borrow if op == "-" else None,
                        True if op == "+" else cfg.allow_negative)
        layout = {"kind": "vertical", "op": op, "numbers": [str(a), str(b)]}
        result = a + b if op == "+" else a - b
        return Question("vertical", _stmt_add(op, a, b), str(result),
                        f"{a} {op} {b}", layout)
    if op == "×":
        lo, hi = cfg.multiplication_table
        a = gen_operand(rng, lo, hi)
        b = gen_operand(rng, lo, hi)
        layout = {"kind": "vertical", "op": "×", "numbers": [str(a), str(b)]}
        return Question("vertical", _stmt_add("×", a, b), str(a * b),
                        f"{a} × {b}", layout)
    # ÷
    lo0, hi0 = cfg.operand_ranges[0]
    q_lo, q_hi = cfg.multiplication_table
    d_lo, d_hi = cfg.divisor_range
    for _ in range(1000):
        divisor = gen_operand(rng, d_lo, d_hi)
        quotient = gen_operand(rng, q_lo, q_hi)
        remainder = gen_operand(rng, 0, divisor - 1) if cfg.allow_remainder else 0
        if rng.random() < 0.5:
            remainder = 0
        dividend = divisor * quotient + remainder
        if lo0 <= dividend <= hi0:
            break
    else:
        raise RuntimeError(f"无法生成除法竖式：被除数范围 {cfg.operand_ranges[0]} 内找不到 divisor×quotient(+r)。建议扩大范围。")
    layout = {"kind": "vertical", "op": "÷", "divisor": str(divisor),
              "dividend": str(dividend), "quotient": str(quotient),
              "remainder": str(remainder)}
    answer = str(quotient) if remainder == 0 else f"{quotient} 余 {remainder}"
    stmt = f"{dividend} ÷ {divisor} = ____"
    return Question("vertical", stmt, answer, f"{dividend} ÷ {divisor}", layout)
