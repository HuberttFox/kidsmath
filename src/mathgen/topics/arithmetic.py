"""算术题型（最小实现：仅两运算数 +/−）。

供 Task 3 引擎测试使用。完整实现（×÷、多运算数、括号等）归 Task 4。
"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.engine import GenerationError, gen_pair
from mathgen.core.question import Question


def gen(cfg: ResolvedConfig, rng: random.Random) -> Question:
    """生成一道两运算数 +/− 题。

    Task 4 将扩展为完整 arithmetic 模块；此处仅覆盖引擎测试所需的最小行为。
    """
    if cfg.operand_count != 2:
        raise GenerationError(
            f"最小实现仅支持两个运算数（当前 {cfg.operand_count} 个），多运算数归 Task 4。")
    ops = [c for c in cfg.operators if c in "+-"]
    if not ops:
        raise GenerationError("最小实现仅支持 + −；× ÷ 归 Task 4。")
    op = rng.choice(ops)
    carry = cfg.carry if op == "+" else None
    borrow = cfg.borrow if op == "-" else None
    lo, hi = cfg.result_range
    for _ in range(1000):
        # "+" 结果永不为负，放开 a<b 以扩大组合空间（引擎 gen_pair 默认强制 a≥b）
        allow_neg = True if op == "+" else cfg.allow_negative
        a, b = gen_pair(rng, cfg.operand_ranges, carry=carry, borrow=borrow,
                        allow_negative=allow_neg)
        result = a + b if op == "+" else a - b
        if lo <= result <= hi:
            break
    else:
        raise GenerationError(
            f"在运算数范围 {cfg.operand_ranges}、结果范围 {cfg.result_range} 下找不到题目。"
            f"建议：扩大结果范围或放宽进位/借位要求。")
    expression = f"{a} {op} {b}"
    return Question(
        topic="arithmetic",
        statement=expression,
        answer=str(result),
        expression=expression,
    )
