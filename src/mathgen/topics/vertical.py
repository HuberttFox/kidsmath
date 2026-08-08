"""竖式题：加减乘除，layout 供 PDF 精确绘制。"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.engine import (GenerationError, check_result, gen_operand,
                                 gen_pair, gen_result, pick_op, divisor_range,
                                 left_factor_range, quotient_range,
                                 right_factor_range)
from mathgen.core.question import Question
from mathgen.topics.steps import vertical_steps


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
                        f"{a} {op} {b}", layout,
                        steps=vertical_steps(op, layout, cfg.lang, result=result))
    if op == "×":
        lo0, hi0 = left_factor_range(cfg)
        lo1, hi1 = right_factor_range(cfg)

        def make():
            a = gen_operand(rng, lo0, hi0)
            b = gen_operand(rng, lo1, hi1)
            return a, b, a * b

        a, b, result = gen_result(make, lambda t: check_result(cfg)(t[2]), *cfg.result_range)
        layout = {"kind": "vertical", "op": "×", "numbers": [str(a), str(b)]}
        return Question("vertical", _stmt_add("×", a, b), str(a * b),
                        f"{a} × {b}", layout,
                        steps=vertical_steps("×", layout, cfg.lang, result=result))
    # ÷
    lo0, hi0 = cfg.operand_ranges[0]
    d_lo, d_hi = divisor_range(cfg)
    q_range = quotient_range(cfg)
    if q_range is None:
        raise GenerationError("div_no_solution", ranges=cfg.dividend_range)
    q_lo, q_hi = q_range
    explicit_dividend = cfg.explicit_dividend

    def make():
        if explicit_dividend:
            alo, ahi = cfg.dividend_range
            for _ in range(100):
                dividend = gen_operand(rng, alo, ahi)
                divisor = gen_operand(rng, d_lo, d_hi)
                if rng.random() < 0.5 and dividend % divisor != 0:
                    continue
                quotient = dividend // divisor
                if quotient == 0 or not (q_lo <= quotient <= q_hi):
                    continue
                if not (lo0 <= dividend <= hi0):
                    continue
                return divisor, quotient, dividend % divisor, dividend
        else:
            for _ in range(100):
                divisor = gen_operand(rng, d_lo, d_hi)
                quotient = gen_operand(rng, q_lo, q_hi)
                if quotient == 0:
                    continue
                remainder = gen_operand(rng, 0, divisor - 1) if cfg.allow_remainder else 0
                if rng.random() < 0.5:
                    remainder = 0
                dividend = divisor * quotient + remainder
                if not (lo0 <= dividend <= hi0):
                    continue
                return divisor, quotient, remainder, dividend
        raise GenerationError("div_no_solution", ranges=(d_lo, d_hi))

    divisor, quotient, remainder, dividend = gen_result(
        make, lambda t: lo0 <= t[3] <= hi0 and check_result(cfg)(t[1]),
        *cfg.result_range)
    layout = {"kind": "vertical", "op": "÷", "divisor": str(divisor),
              "dividend": str(dividend), "quotient": str(quotient),
              "remainder": str(remainder)}
    answer = str(quotient) if remainder == 0 else f"{quotient} {"R" if cfg.lang == "en" else "余"} {remainder}"
    stmt = f"{dividend} ÷ {divisor} = ____"
    return Question("vertical", stmt, answer, f"{dividend} ÷ {divisor}", layout,
                    steps=vertical_steps("÷", layout, cfg.lang))
