"""口算/四则混合题。"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.engine import gen_operand, gen_pair
from mathgen.core.question import Question


def _pick_ops(rng: random.Random, ops: str, n: int) -> list[str]:
    return [rng.choice(list(ops)) for _ in range(n)]


def gen(cfg: ResolvedConfig, rng: random.Random) -> Question:
    n = cfg.operand_count
    if n == 2:
        return _gen_two(cfg, rng)
    return _gen_multi(cfg, rng, n)


def _gen_two(cfg: ResolvedConfig, rng: random.Random) -> Question:
    op = rng.choice(list(cfg.operators))
    if op in "+-":
        lo, hi = cfg.result_range
        # 偏离 brief：恢复结果范围约束（brief 删掉了 stub 的 result_range 过滤，
        # 会击穿既有引擎测试 test_result_within_range，如 95+42=137 > 100）。
        for _ in range(1000):
            # 偏离 brief：+ 恒传 allow_negative=True。0–9 范围无序进位对仅 25 个 < 引擎 30 题去重需求，
            # 引擎 _signature 对 + 保留顺序（a<b 与 a>b 视为不同题），需有序对 55 个才能凑够。
            a, b = gen_pair(rng, cfg.operand_ranges, cfg.carry if op == "+" else None,
                            cfg.borrow if op == "-" else None,
                            True if op == "+" else cfg.allow_negative)
            result = a + b if op == "+" else a - b
            if lo <= result <= hi:
                break
        else:
            raise RuntimeError(
                f"在运算数范围 {cfg.operand_ranges}、结果范围 {cfg.result_range} 下找不到题目。"
                f"建议：扩大结果范围或放宽进位/借位要求。")
    elif op == "×":
        lo, hi = cfg.multiplication_table
        r_lo, r_hi = cfg.result_range
        for _ in range(1000):
            a = gen_operand(rng, lo, hi)
            b = gen_operand(rng, lo, hi)
            result = a * b
            if r_lo <= result <= r_hi:
                break
        else:
            raise RuntimeError(
                f"在乘法表范围 {cfg.multiplication_table}、结果范围 {cfg.result_range} 下找不到题目。"
                f"建议：扩大结果范围或调小乘法表。")
    else:  # ÷
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
            raise RuntimeError(f"无法生成除法题：被除数范围 {cfg.operand_ranges[0]} 内找不到 divisor×quotient(+r)。建议扩大范围。")
        # 偏离 brief：allow_remainder 时统一 "Q 余 R" 格式（含余 0），
        # 与测试 test_division_with_remainder 断言一致；否则仅输出商。
        if cfg.allow_remainder:
            return Question("arithmetic", f"{dividend} ÷ {divisor} = ____",
                            f"{quotient} 余 {remainder}", f"{dividend} ÷ {divisor}", None)
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

    def factor() -> int | None:
        nonlocal pos
        v = int(tokens[pos]); pos += 1
        while pos < len(tokens) and tokens[pos] in "×÷":
            op = tokens[pos]; pos += 1
            b = int(tokens[pos]); pos += 1
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
        ops = _pick_ops(rng, cfg.operators, n - 1)
        operands = [gen_operand(rng, *cfg.operand_ranges[i]) for i in range(n)]
        if not cfg.allow_negative and len(ops) == 1 and ops[0] == "-" and operands[0] < operands[1]:
            operands[0], operands[1] = operands[1], operands[0]
        tokens = []
        for i, op in enumerate(ops):
            tokens.append(str(operands[i]))
            tokens.append(op)
        tokens.append(str(operands[-1]))
        result = _eval_precedence(tokens)
        if result is None:
            continue
        r_lo, r_hi = cfg.result_range
        if not (r_lo <= result <= r_hi) or (result < 0 and not cfg.allow_negative):
            continue
        expr = " ".join(tokens)
        if cfg.parentheses and n > 2:
            expr = f"({expr})" if rng.random() < 0.5 else expr
        statement = expr.replace("(", "( ").replace(")", " )") + " = ____"
        return Question("arithmetic", statement, str(result), expr, None)
    raise RuntimeError(f"无法生成 {n} 个运算数的整除混合题，建议减少 ÷ 运算符或调整范围。")
