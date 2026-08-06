"""压力测试：用户配置下生成 3000 道口算题，重点检测乘法表/商范围与除数范围约束。"""
import re

from mathgen.config import Config, resolve
from mathgen.core.engine import generate
from mathgen.topics.arithmetic import _eval_precedence, _intermediate_ok

USER_CFG = dict(
    grade=None,
    operators="-×÷",
    operand_count=3,
    parentheses=True,
    operand_ranges=[(1, 999), (1, 999), (1, 999)],
    result_range=(0, 1000),
    carry=True,
    borrow=True,
    divisor_range=(2, 9),
    multiplication_table=(2, 9),
)


def _group_value(toks, k):
    """求 tokens[k] 处的因子值：数字或括号组。"""
    if toks[k] == "(":
        end = toks.index(")", k)
        return _eval_precedence(toks[k:end + 1])
    if toks[k] == ")":
        depth = 0
        for m in range(k, -1, -1):
            depth += 1 if toks[m] == ")" else -1 if toks[m] == "(" else 0
            if toks[m] == "(" and depth == 0:
                return _eval_precedence(toks[m:k + 1])
    return int(toks[k])


def test_stress_3000_questions_table_and_divisor():
    stats = {"mul": 0, "div": 0, "paren": 0, "mul_factor_hi": 0, "divisor_hi": 0,
             "dividend_hi": 0}
    for batch in range(6):  # count ≤ 500，分 6 批
        cfg = resolve(Config(**USER_CFG, count=500, seed=9000 + batch))
        for q in generate(cfg):
            toks = q.expression.split(" ")
            # 括号形态合法（组值/答案一致由求值保证）
            assert _eval_precedence(toks) == int(q.answer), q.expression
            assert _intermediate_ok(toks, False), q.expression
            # 结果范围
            assert 0 <= int(q.answer) <= 1000, q.expression
            for j, t in enumerate(toks):
                if t == "×":
                    stats["mul"] += 1
                    for k in (j - 1, j + 1):
                        v = _group_value(toks, k)
                        assert 2 <= v <= 9, f"× 因数 {v} 超表: {q.expression}"
                        stats["mul_factor_hi"] = max(stats["mul_factor_hi"], v)
                if t == "÷":
                    stats["div"] += 1
                    divisor = _group_value(toks, j + 1)
                    assert 2 <= divisor <= 9, f"除数 {divisor} 超范围: {q.expression}"
                    stats["divisor_hi"] = max(stats["divisor_hi"], divisor)
                    dividend = _eval_precedence(toks[:j])
                    assert 4 <= dividend <= 81, f"被除数 {dividend}: {q.expression}"
                    stats["dividend_hi"] = max(stats["dividend_hi"], dividend)
                if t == "(":
                    stats["paren"] += 1
    print(f"3000 题统计: ×{stats['mul']} ÷{stats['div']} 括号组{stats['paren']} "
          f"因数上限{stats['mul_factor_hi']} 除数上限{stats['divisor_hi']} 被除数上限{stats['dividend_hi']}")
    assert stats["mul"] > 100, "× 题过少，配置异常"
    assert stats["div"] > 100, "÷ 题过少，配置异常"
