"""口算/四则混合题。"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.engine import (GenerationError, check_result, gen_operand,
                                 gen_pair, gen_result, pick_op)
from mathgen.core.question import Question


def _pick_ops(rng: random.Random, cfg, n: int) -> list[str]:
    return [pick_op(rng, cfg) for _ in range(n)]


def gen(cfg: ResolvedConfig, rng: random.Random) -> Question:
    n = cfg.operand_count
    if n == 2:
        return _gen_two(cfg, rng)
    return _gen_multi(cfg, rng, n)


def _gen_two(cfg: ResolvedConfig, rng: random.Random) -> Question:
    op = pick_op(rng, cfg)
    if op in "+-":
        # 偏离 brief：+ 恒传 allow_negative=True。0–9 范围无序进位对仅 25 个 < 引擎 30 题去重需求，
        # 引擎 _signature 对 + 保留顺序（a<b 与 a>b 视为不同题），需有序对 55 个才能凑够。
        def make():
            a, b = gen_pair(rng, cfg.operand_ranges, cfg.carry if op == "+" else None,
                            cfg.borrow if op == "-" else None,
                            True if op == "+" else cfg.allow_negative)
            return a, b, (a + b if op == "+" else a - b)

        a, b, result = gen_result(make, lambda t: check_result(cfg)(t[2]), *cfg.result_range)
    elif op == "×":
        if cfg.explicit_ranges:
            lo0, hi0 = cfg.operand_ranges[0]
            lo1, hi1 = cfg.operand_ranges[1]

            def make():
                a = gen_operand(rng, lo0, hi0)
                b = gen_operand(rng, lo1, hi1)
                return a, b, a * b
        else:
            lo, hi = cfg.multiplication_table

            def make():
                a = gen_operand(rng, lo, hi)
                b = gen_operand(rng, lo, hi)
                return a, b, a * b

        a, b, result = gen_result(make, lambda t: check_result(cfg)(t[2]), *cfg.result_range)
    else:  # ÷
        lo0, hi0 = cfg.operand_ranges[0]
        q_lo, q_hi = cfg.multiplication_table
        if cfg.explicit_ranges:
            d_lo, d_hi = cfg.operand_ranges[1]
        else:
            d_lo, d_hi = cfg.divisor_range

        def make():
            divisor = gen_operand(rng, d_lo, d_hi)
            quotient = gen_operand(rng, q_lo, q_hi)
            remainder = gen_operand(rng, 0, divisor - 1) if cfg.allow_remainder else 0
            if rng.random() < 0.5:
                remainder = 0
            dividend = divisor * quotient + remainder
            return divisor, quotient, remainder, dividend

        divisor, quotient, remainder, dividend = gen_result(
            make,
            lambda t: lo0 <= t[3] <= hi0 and check_result(cfg)(t[1]),
            *cfg.result_range)
        # 偏离 brief：allow_remainder 时统一 "Q 余 R" 格式（含余 0），
        # 与测试 test_division_with_remainder 断言一致；否则仅输出商。
        if cfg.allow_remainder:
            rword = "R" if cfg.lang == "en" else "余"
            return Question("arithmetic", f"{dividend} ÷ {divisor} = ____",
                            f"{quotient} {rword} {remainder}", f"{dividend} ÷ {divisor}", None)
        return Question("arithmetic", f"{dividend} ÷ {divisor} = ____",
                        str(quotient), f"{dividend} ÷ {divisor}", None)
    expr = f"{a} {op} {b}"
    return Question("arithmetic", f"{expr} = ____", str(result), expr, None)


def _eval_precedence(tokens: list[str]) -> int | None:
    """标准优先级求值（先 ×÷ 后 +−，同级从左到右）；出现不整除时返回 None。

    偏离 brief：brief 自左向右顺序求值，与测试 _eval（Python 运算优先级）不一致，
    混合运算（如 "a + b × c"）会算错；改按标准优先级。
    """
    pos = 0

    def atom() -> int | None:
        """一个因子：数字或括号组（不吞后续 ×÷ 链）。"""
        nonlocal pos
        if tokens[pos] == "(":
            pos += 1
            v = term()
            if v is None or tokens[pos] != ")":
                return None
            pos += 1
            return v
        v = int(tokens[pos]); pos += 1
        return v

    def factor() -> int | None:
        """×÷ 链（左结合），链上的每个因子可为数字或括号组。"""
        nonlocal pos
        v = atom()
        while pos < len(tokens) and tokens[pos] in "×÷":
            op = tokens[pos]; pos += 1
            b = atom()
            if v is None or b is None:
                return None
            if op == "÷":
                if b == 0 or v % b != 0:
                    return None
                v //= b
            else:
                v *= b
        return v

    def term() -> int | None:
        nonlocal pos
        v = factor()
        while pos < len(tokens) and tokens[pos] in "+-":
            op = tokens[pos]; pos += 1
            rhs = factor()
            if v is None or rhs is None:
                return None
            v = v + rhs if op == "+" else v - rhs
        return v

    result = term()
    if result is None or pos != len(tokens):
        return None
    return result


def _gen_multi(cfg: ResolvedConfig, rng: random.Random, n: int) -> Question:
    for _ in range(1000):
        ops = _pick_ops(rng, cfg, n - 1)
        operands = [gen_operand(rng, *cfg.operand_ranges[0])]
        for i in range(1, n):
            prev = ops[i - 1]
            if prev == "×" and not cfg.explicit_ranges:
                lo, hi = cfg.multiplication_table
                operands.append(gen_operand(rng, lo, hi))
            elif prev == "÷" and not cfg.explicit_ranges:
                lo, hi = cfg.divisor_range
                operands.append(gen_operand(rng, lo, hi))
            else:
                operands.append(gen_operand(rng, *cfg.operand_ranges[i]))
        if not cfg.allow_negative and len(ops) == 1 and ops[0] == "-" and operands[0] < operands[1]:
            operands[0], operands[1] = operands[1], operands[0]
        groups = _paren_groups(ops) if cfg.parentheses and n >= 3 else None
        if groups:
            for s, e in groups:
                for idx in range(s, e + 2):
                    lo, hi = cfg.operand_ranges[min(idx, n - 1)]
                    lo = max(2, lo)
                    hi = max(lo, min(hi, 30))
                    operands[idx] = gen_operand(rng, lo, hi)
        tokens = []
        for i, op in enumerate(ops):
            tokens.append(str(operands[i]))
            tokens.append(op)
        tokens.append(str(operands[-1]))
        if groups:
            if len(groups) == 2 and all(s == e for s, e in groups) and len(ops) == 3:
                tokens = _wrap_two(tokens)
            else:
                tokens = _wrap_one(tokens, groups[0][0], groups[0][1])
        result = _eval_precedence(tokens)
        if result is None:
            continue
        if not check_result(cfg)(result):
            continue
        expr = " ".join(tokens)
        statement = expr.replace("(", "( ").replace(")", " )") + " = ____"
        return Question("arithmetic", statement, str(result), expr, None)
    raise GenerationError("multi_no_solution", n=n)


def _paren_groups(ops: list[str]) -> list[tuple[int, int]] | None:
    """找可加括号的 +- 连续片段（邻接 ×÷ 才改变运算顺序）。

    返回片段列表（运算符下标区间）；无可包片段返回 None。
    """
    def low(op: str) -> bool:
        return op in "+-"

    n = len(ops)
    runs: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if not low(ops[i]):
            i += 1
            continue
        j = i
        while j < n and low(ops[j]):
            j += 1
        has_high_neighbor = (i > 0 and not low(ops[i - 1])) or (j < n and not low(ops[j]))
        if has_high_neighbor:
            runs.append((i, j - 1))
        i = j
    return runs or None


def _wrap_one(tokens: list[str], s: int, e: int) -> list[str]:
    """包住 ops[s..e] 的 +- 片段（连同两侧运算数），如 a × ( b + c )。"""
    return tokens[:2 * s] + ["("] + tokens[2 * s:2 * e + 3] + [")"] + tokens[2 * e + 3:]


def _wrap_two(tokens: list[str]) -> list[str]:
    """双包：模式 [+-, ×÷, +-] → ( a + b ) × ( c + d )。"""
    return (["("] + tokens[:3] + [")"] + tokens[3:4]
            + ["("] + tokens[4:7] + [")"] + tokens[7:])
