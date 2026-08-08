"""Step-by-step calculation steps for generated answers.

Pure functions of already-computed values (no generation, no rng). Each step is
one short line (<= ~40 chars) for the PDF answer page and the online worksheet.

NOTE: every non-ASCII char in this file must be present in the bundled subset
font cmap (tests/test_fonts.py scans topics/*.py), because steps are drawn into
PDFs with that font. Docstrings/comments are English for this reason.
"""
from __future__ import annotations

_OP_ZH = {"加": "+", "减": "-", "乘": "×", "除": "÷",
          "x": "×", "X": "×", "*": "×", "/": "÷"}

# Place names: index 0 is the ones place. The subset font lacks the chars for
# hundreds/thousands/millions, so higher places fall back to 第N位 ("Nth place").
_PLACE_ZH = ("个位", "十位")
_PLACE_EN = ("ones", "tens", "hundreds", "thousands", "ten-thousands",
             "hundred-thousands", "millions")


def _norm_op(op: str) -> str:
    """Normalize an operator: accept a symbol or a Chinese char."""
    op = op.strip()
    return _OP_ZH.get(op, op)


def _place(n: int, lang: str) -> str:
    """Name of place n (0 = ones)."""
    if lang == "en":
        return _PLACE_EN[n] if n < len(_PLACE_EN) else f"col {n + 1}"
    return _PLACE_ZH[n] if n < len(_PLACE_ZH) else f"第{n + 1}位"


def _digits(x: int) -> list[int]:
    """Digits of x, ones first."""
    return [int(d) for d in str(abs(x))[::-1]]


def _add_cols(a: int, b: int) -> list[dict]:
    """Split addition column by column (ones upward); one dict per column."""
    ad, bd = _digits(a), _digits(b)
    n = max(len(ad), len(bd))
    cols: list[dict] = []
    carry = 0
    for i in range(n):
        ai = ad[i] if i < len(ad) else 0
        bi = bd[i] if i < len(bd) else 0
        s = ai + bi + carry
        cols.append({"col": i, "ad": ai, "bd": bi, "carry_in": carry,
                     "sum": s, "write": s % 10, "carry_out": s // 10})
        carry = s // 10
    if carry:
        cols.append({"col": n, "ad": 0, "bd": 0, "carry_in": carry,
                     "sum": carry, "write": carry, "carry_out": 0})
    return cols


def _sub_cols(a: int, b: int) -> list[dict]:
    """Split subtraction column by column (a >= b); one dict per column."""
    ad, bd = _digits(a), _digits(b)
    n = max(len(ad), len(bd))
    cols: list[dict] = []
    borrow = 0
    for i in range(n):
        ai = ad[i] if i < len(ad) else 0
        bi = bd[i] if i < len(bd) else 0
        a_eff = ai - borrow
        if a_eff < bi:
            dd = a_eff + 10 - bi
            cols.append({"col": i, "ad": ai, "bd": bi, "a_eff": a_eff,
                         "dd": dd, "borrowed": True})
            borrow = 1
        else:
            dd = a_eff - bi
            cols.append({"col": i, "ad": ai, "bd": bi, "a_eff": a_eff,
                         "dd": dd, "borrowed": False})
            borrow = 0
    return cols


def arith_steps(op: str, a: int, b: int, result: int, lang: str,
                remainder: int | None = None) -> list[str]:
    """Steps for a 2-operand calculation (+ - x /). result is the answer
    (for / it is the quotient).

    For /, the remainder is derived as a - b x result (0 means exact) unless
    an explicit remainder is passed (e.g. the "Q 余 R" format used when
    allow_remainder is on).
    """
    op = _norm_op(op)
    zh = lang != "en"
    if op == "÷":
        q = result
        r = a - b * result if remainder is None else remainder
        if r == 0 and remainder is None:
            # exact division, plain quotient answer
            if zh:
                return [f"乘法表：{b} × {q} = {a}", f"结果：{q}"]
            return [f"Times table: {b} × {q} = {a}", f"Result: {q}"]
        # explicit remainder (incl. 0): the answer is "Q 余 R", so keep the
        # remainder line and name the equality correctly when r == 0
        if zh:
            eq = "等于" if r == 0 else "小于"
            return [f"{b} × {q} = {b * q}，{eq} {a}", f"{a} - {b * q} = {r}",
                    f"结果：{q} 余 {r}"]
        eq = "equals" if r == 0 else "not more than"
        return [f"{b} × {q} = {b * q}, {eq} {a}", f"{a} - {b * q} = {r}",
                f"Result: {q} R {r}"]
    if op == "×":
        return _mul_steps(a, b, result, lang)
    if op == "+":
        out = []
        for col in _add_cols(a, b):
            if col["ad"] == 0 and col["bd"] == 0 and col["carry_in"]:
                # only the carried digit remains: name the place it lands in
                label = _place(col["col"], lang)
                if zh:
                    out.append(f"进上来的1在{label}")
                else:
                    out.append(f"the carried 1 goes to the {label} place")
                continue
            carry = f" + {col['carry_in']}" if col["carry_in"] else ""
            if col["carry_out"]:
                line = (f"{col['ad']} + {col['bd']}{carry} = {col['sum']}"
                        f"，个位是{col['write']}，进1" if zh else
                        f"{col['ad']} + {col['bd']}{carry} = {col['sum']}"
                        f", write {col['write']}, carry 1")
                out.append(line)
            else:
                label = _place(col["col"], lang)
                if zh:
                    out.append(f"{col['ad']} + {col['bd']}{carry} = {col['sum']}（{label}）")
                else:
                    out.append(f"{col['ad']} + {col['bd']}{carry} = {col['sum']} ({label})")
        out.append(f"结果：{result}" if zh else f"Result: {result}")
        return out
    # subtraction
    out = []
    for col in _sub_cols(a, b):
        if col["borrowed"]:
            if zh:
                if col["a_eff"] >= 0:
                    out.append("不够减，加上10")
                else:
                    out.append("不够减，向上加10")
                out.append(f"加10后：{col['a_eff'] + 10} - {col['bd']} = {col['dd']}")
            else:
                if col["a_eff"] >= 0:
                    out.append(f"{col['bd']} - {col['a_eff']} is too small, borrow 1")
                else:
                    out.append("Still too small, borrow again")
                out.append(f"After borrow: {col['a_eff'] + 10} - {col['bd']} = {col['dd']}")
        else:
            label = _place(col["col"], lang)
            if zh:
                out.append(f"{col['a_eff']} - {col['bd']} = {col['dd']}（{label}）")
            else:
                out.append(f"{col['a_eff']} - {col['bd']} = {col['dd']} ({label})")
    out.append(f"结果：{result}" if zh else f"Result: {result}")
    return out


def _mul_steps(a: int, b: int, result: int, lang: str) -> list[str]:
    """Multiplication steps; order a,b so the multi-digit operand is on the left."""
    zh = lang != "en"
    a_str, b_str = str(a), str(b)
    if len(a_str) == 1 and len(b_str) == 1:
        return [f"乘法表：{a} × {b} = {result}" if zh else
                f"Times table: {a} × {b} = {result}",
                f"结果：{result}" if zh else f"Result: {result}"]
    # keep the single digit on the right
    if len(a_str) == 1 and len(b_str) > 1:
        a_str, b_str = b_str, a_str
        a, b = b, a
    if len(b_str) == 1:
        out = []
        carry = 0
        for i in range(len(a_str)):
            ai = int(a_str[len(a_str) - 1 - i])
            prod = ai * b + carry
            label = _place(i, lang)
            if zh:
                if prod >= 10:
                    out.append(f"{label}：{ai} × {b}"
                               + (f" + {carry}" if carry else "")
                               + f" = {prod}，进{prod // 10}，留{prod % 10}")
                else:
                    out.append(f"{label}：{ai} × {b}"
                               + (f" + {carry}" if carry else "")
                               + f" = {prod}")
            else:
                if prod >= 10:
                    out.append(f"{label}: {ai} × {b}"
                               + (f" + {carry}" if carry else "")
                               + f" = {prod}, write {prod % 10}, carry {prod // 10}")
                else:
                    out.append(f"{label}: {ai} × {b}"
                               + (f" + {carry}" if carry else "")
                               + f" = {prod}")
            carry = prod // 10
        out.append(f"结果：{result}" if zh else f"Result: {result}")
        return out
    # multi x multi: partial products per place of b, then add them
    out = []
    partials = []
    for i in range(len(b_str)):
        bd = int(b_str[len(b_str) - 1 - i]) * (10 ** i)
        partial = a * bd
        partials.append(partial)
        label = _place(i, lang)
        out.append(f"{label}：{a} × {bd} = {partial}" if zh else
                   f"{label}: {a} × {bd} = {partial}")
    sum_expr = " + ".join(str(p) for p in partials)
    out.append(f"相加：{sum_expr} = {result}" if zh else f"Add: {sum_expr} = {result}")
    out.append(f"结果：{result}" if zh else f"Result: {result}")
    return out


def _eval_with_steps(tokens: list[str]) -> tuple[int | None, list[tuple[str, int]]]:
    """Evaluate with standard precedence while recording (subexpr, value) steps.

    Mirrors arithmetic._eval_precedence: innermost parens first, then x and /
    left-to-right, then + and - left-to-right; division must be exact.
    Returns (None, []) when the expression cannot be evaluated.
    """
    pos = 0
    steps: list[tuple[str, int]] = []

    def atom() -> tuple[int | None, str]:
        nonlocal pos
        if tokens[pos] == "(":
            start = pos
            pos += 1
            v, _ = term()
            if v is None or tokens[pos] != ")":
                return None, ""
            pos += 1
            return v, " ".join(tokens[start:pos])
        v = int(tokens[pos]); pos += 1
        return v, str(v)

    def factor() -> tuple[int | None, str]:
        nonlocal pos
        v, disp = atom()
        while pos < len(tokens) and tokens[pos] in "×÷":
            op = tokens[pos]; pos += 1
            b, bdisp = atom()
            if v is None or b is None:
                return None, ""
            if op == "÷":
                if b == 0 or v % b != 0:
                    return None, ""
                v //= b
            else:
                v *= b
            disp = f"{disp} {op} {bdisp}"
            steps.append((disp, v))
        return v, disp

    def term() -> tuple[int | None, str]:
        nonlocal pos
        v, disp = factor()
        while pos < len(tokens) and tokens[pos] in "+-":
            op = tokens[pos]; pos += 1
            rhs, rdisp = factor()
            if v is None or rhs is None:
                return None, ""
            v = v + rhs if op == "+" else v - rhs
            disp = f"{disp} {op} {rdisp}"
            steps.append((disp, v))
        return v, disp

    result, _ = term()
    if result is None or pos != len(tokens):
        return None, []
    return result, steps


def multi_steps(tokens: list[str], result: int, lang: str) -> list[str]:
    """Steps for multi-operand mixed arithmetic (parens allowed), by precedence."""
    zh = lang != "en"
    _, evals = _eval_with_steps(tokens)
    out = [f"先算：{sub} = {v}" if zh else f"First: {sub} = {v}"
           for sub, v in evals]
    out.append(f"结果：{result}" if zh else f"Result: {result}")
    return out


def vertical_steps(op: str, layout: dict, lang: str, result: int | None = None) -> list[str]:
    """Steps for the vertical topic. + - x use layout['numbers']; / uses the
    divisor/dividend/quotient/remainder keys of the layout."""
    op = _norm_op(op)
    zh = lang != "en"
    if op == "÷":
        divisor = int(layout["divisor"])
        dividend = int(layout["dividend"])
        quotient = int(layout["quotient"])
        remainder = int(layout["remainder"])
        p = divisor * quotient
        if zh:
            out = [f"乘法表：{divisor} × {quotient} = {p}"]
            if remainder:
                out.append(f"余数：{dividend} - {p} = {remainder}")
                out.append(f"结果：{quotient} 余 {remainder}")
            else:
                out.append(f"结果：{quotient}")
        else:
            out = [f"Times table: {divisor} × {quotient} = {p}"]
            if remainder:
                out.append(f"Remainder: {dividend} - {p} = {remainder}")
                out.append(f"Result: {quotient} R {remainder}")
            else:
                out.append(f"Result: {quotient}")
        return out
    a_str, b_str = layout["numbers"]
    a, b = int(a_str), int(b_str)
    if result is None:
        result = a + b if op == "+" else (a - b if op == "-" else a * b)
    return arith_steps(op, a, b, result, lang)


def word_steps(op: str, a: int, b: int, result: int, lang: str) -> list[str]:
    """Steps for word problems: equation, work, answer. Operator-neutral
    (no partition/grouping meaning asserted for division)."""
    op = _norm_op(op)
    zh = lang != "en"
    if zh:
        return [f"列式：{a} {op} {b}",
                f"算式：{a} {op} {b} = {result}",
                f"答：{result}"]
    return [f"Equation: {a} {op} {b}",
            f"Work: {a} {op} {b} = {result}",
            f"Answer: {result}"]
