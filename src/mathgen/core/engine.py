"""随机出题引擎：进位/借位控制、去重、seed 复现。"""
from __future__ import annotations

import random
from collections.abc import Callable
from typing import TypeVar

from mathgen.config import ResolvedConfig
from mathgen.core.question import Question

T = TypeVar("T")


class GenerationError(RuntimeError):
    """生成冲突，消息为中文。"""


def gen_operand(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


def check_result(cfg: ResolvedConfig) -> Callable[[int], bool]:
    """结果范围谓词：lo ≤ r ≤ hi 且 r ≥ 0（或 cfg.allow_negative）。"""
    lo, hi = cfg.result_range

    def ok(r: int) -> bool:
        return lo <= r <= hi and (r >= 0 or cfg.allow_negative)

    return ok


def gen_result(make: Callable[[], T], check: Callable[[T], bool]) -> T:
    """按 make() 生成候选，重试至多 1000 次直到 check 通过；失败抛 GenerationError。

    全题型共用：保证结果落在 result_range 且（默认）非负。
    """
    for _ in range(1000):
        result = make()
        if check(result):
            return result
    raise GenerationError(
        f"在运算数范围、结果范围约束下找不到题目。"
        f"建议：扩大结果范围或调小数值范围。")


def has_carry(a: int, b: int) -> bool:
    """加法 a+b 是否发生进位（十进制逐列）。"""
    while a or b:
        if (a % 10) + (b % 10) >= 10:
            return True
        a //= 10
        b //= 10
    return False


def has_borrow(a: int, b: int) -> bool:
    """减法 a-b 是否发生借位（十进制逐列）。"""
    while a or b:
        if (a % 10) < (b % 10):
            return True
        a //= 10
        b //= 10
    return False


def gen_pair(rng: random.Random, ranges: list[tuple[int, int]],
             carry: bool | None = None, borrow: bool | None = None,
             allow_negative: bool = False) -> tuple[int, int]:
    """生成满足进位/借位约束的一对运算数。carry/borrow 为 None 时不约束。"""
    lo0, hi0 = ranges[0]
    lo1, hi1 = ranges[1]
    for _ in range(1000):
        a = gen_operand(rng, lo0, hi0)
        b = gen_operand(rng, lo1, hi1)
        if not allow_negative and a < b:
            continue
        if carry is not None and has_carry(a, b) != carry:
            continue
        if borrow is not None and has_borrow(a, b) != borrow:
            continue
        return a, b
    raise GenerationError(
        f"在运算数范围 {ranges}、进位={carry}、借位={borrow} 约束下找不到题目。"
        f"建议：扩大数值范围，或放宽进位/借位要求（设为 随机）。")


def _signature(q: Question) -> tuple:
    """去重签名：× 交换律归一（排序），+ − ÷ 保持顺序。

    对 brief 的偏离：+ 不排序。原因：0–9 范围内无序进位对仅 25 个 < 30，
    brief 自身 test_carry_flag_respected 要求 30 道不重复进位题，必须保留顺序。
    数字位数增大（多位数范围）后可恢复 + 的交换律归一。

    Task 4 引入括号后（grade 5/6），括号会挂在数字 token 上（"(3"）导致 int() 崩溃；
    签名剥掉括号但保留 parens 标记，避免 "(1+2)×3" 与 "1+2×3" 误判为同题。
    """
    parts = q.expression.replace("(", "").replace(")", "").split(" ")
    ops = parts[1::2]
    nums = [int(parts[i]) for i in range(0, len(parts), 2)]
    if all(op == "×" for op in ops):
        return tuple(ops), tuple(sorted(nums)), "(" in q.expression
    return tuple(ops), tuple(nums), "(" in q.expression


def generate(cfg: ResolvedConfig) -> list[Question]:
    rng = random.Random(cfg.seed)
    from mathgen.topics import arithmetic, vertical, word_problem

    factory = {"arithmetic": arithmetic.gen, "vertical": vertical.gen,
               "word_problem": word_problem.gen}[cfg.topic]
    questions: list[Question] = []
    seen: set = set()
    guard = 0
    while len(questions) < cfg.count:
        guard += 1
        if guard > cfg.count * 200:
            raise GenerationError(
                f"生成 {cfg.count} 道不重复题目失败：参数过窄或可生成空间不足。"
                f"建议：扩大数值范围、允许更多运算符，或关闭去重。")
        q = factory(cfg, rng)
        if cfg.dedupe and _signature(q) in seen:
            continue
        seen.add(_signature(q))
        questions.append(q)
    return questions
