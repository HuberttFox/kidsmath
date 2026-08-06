"""参数模型、校验与年级预设。错误消息为中文（web 层可按语言渲染英文）。"""
from __future__ import annotations

from dataclasses import dataclass, field

from mathgen.i18n import error_text


class ConfigError(ValueError):
    """参数校验失败。code+params 供多语言渲染，str() 输出中文。"""

    def __init__(self, code: str, **params):
        self.code = code
        self.params = params
        super().__init__(error_text(code, params, "zh"))


TOPICS = ("arithmetic", "vertical", "word_problem")
OPERATORS = set("+-×÷")


# 年级预设：默认 topic=arithmetic，可被显式参数覆盖
PRESETS: dict[int, dict] = {
    1: {
        "operators": "+-",
        "operand_ranges": [(0, 9), (0, 9)],
        "result_range": (0, 20),
        "carry": False,
        "borrow": False,
        "divisor_range": (1, 9),
        "multiplication_table": (1, 9),
        "gap": 18,
        "answer_lines": 0,
    },
    2: {
        "operators": "+-×",
        "operand_ranges": [(1, 99), (1, 99)],
        "result_range": (0, 100),
        "carry": True,
        "borrow": True,
        "divisor_range": (1, 9),
        "multiplication_table": (1, 9),
        "gap": 16,
        "answer_lines": 0,
    },
    3: {
        "operators": "+-×÷",
        "operand_ranges": [(100, 999), (100, 999)],
        "result_range": (0, 1000),
        "carry": True,
        "borrow": True,
        "divisor_range": (2, 9),
        "multiplication_table": (10, 99),
        "gap": 18,
        "answer_lines": 1,
    },
    4: {
        "operators": "+-×÷",
        "operand_ranges": [(1000, 9999), (1000, 9999)],
        "result_range": (0, 10000),
        "carry": True,
        "borrow": True,
        "divisor_range": (10, 99),
        "multiplication_table": (10, 999),
        "gap": 18,
        "answer_lines": 1,
    },
    5: {
        "operators": "+-×÷",
        "operand_count": 3,
        "operand_ranges": [(10, 999), (10, 999), (10, 999)],
        "result_range": (0, 10000),
        "carry": True,
        "borrow": True,
        "parentheses": True,
        "divisor_range": (2, 99),
        "multiplication_table": (2, 99),
        "gap": 20,
        "answer_lines": 1,
    },
    6: {
        "operators": "+-×÷",
        "operand_count": 4,
        "operand_ranges": [(10, 9999), (10, 9999), (10, 9999), (10, 9999)],
        "result_range": (0, 100000),
        "carry": True,
        "borrow": True,
        "parentheses": True,
        "divisor_range": (2, 99),
        "multiplication_table": (2, 99),
        "gap": 22,
        "answer_lines": 2,
    },
}

# 题型默认（gap 题间距 pt / answer_lines 每题答题横线数）
TOPIC_DEFAULTS = {
    "arithmetic": {"gap": 16, "answer_lines": 0},
    "vertical": {"gap": 20, "answer_lines": 0},
    "word_problem": {"gap": 28, "answer_lines": 2},
}


@dataclass
class Config:
    """用户输入参数，全部有默认值。None 表示未显式指定。"""

    topic: str = "arithmetic"
    operators: str | None = None
    operand_count: int | None = None
    parentheses: bool | None = None
    operand_ranges: list[tuple[int, int]] | None = None
    result_range: tuple[int, int] | None = None
    allow_negative: bool | None = None
    allow_decimal: bool | None = None
    carry: bool | None = None
    borrow: bool | None = None
    divisor_range: tuple[int, int] | None = None
    allow_remainder: bool | None = None
    multiplication_table: tuple[int, int] | None = None
    count: int = 20
    seed: int | None = None
    dedupe: bool | None = None
    columns: int = 2
    gap: int | None = None
    answer_lines: int | None = None
    answer_page: bool | None = None
    title: str | None = None
    header: str | None = None
    sheets: int | None = None
    grade: int | None = None
    lang: str | None = None
    op_weights: dict[str, int] | None = None
    show_numbers: bool | None = None
    number_direction: str | None = None


@dataclass
class ResolvedConfig:
    """预设与显式参数合并、校验后的具体配置，无 None 可选值（除 carry/borrow 可 None）。"""

    topic: str
    operators: str
    operand_count: int
    parentheses: bool
    operand_ranges: list[tuple[int, int]]
    result_range: tuple[int, int]
    allow_negative: bool
    allow_decimal: bool
    carry: bool | None
    borrow: bool | None
    divisor_range: tuple[int, int]
    allow_remainder: bool
    multiplication_table: tuple[int, int]
    count: int
    seed: int
    dedupe: bool
    columns: int
    gap: int
    answer_lines: int
    answer_page: bool
    title: str
    header: str
    sheets: int
    lang: str
    op_weights: dict[str, int]
    show_numbers: bool
    number_direction: str
    explicit_ranges: bool


_OP_ALIASES = {"加": "+", "减": "-", "乘": "×", "除": "÷"}


def normalize_operators(ops: str) -> str:
    """把汉字运算符（加减乘除）归一为 +-×÷，去重且保持顺序。"""
    out: list[str] = []
    for c in ops:
        c = _OP_ALIASES.get(c, c)
        if c not in out:
            out.append(c)
    return "".join(out)


def _check_range(code: str, r: tuple[int, int]) -> None:
    lo, hi = r
    if lo < 0 or hi < lo:
        raise ConfigError(code, r=r)


def resolve(cfg: Config) -> ResolvedConfig:
    """合并年级预设 + 题型默认 + 显式参数，校验后返回 ResolvedConfig。"""
    data: dict = vars(Config())
    data.pop("grade")
    data.pop("lang")
    data["lang"] = cfg.lang or "zh"
    if data["lang"] not in ("zh", "en"):
        raise ConfigError("invalid_lang", lang=data["lang"])
    if cfg.grade is not None:
        if cfg.grade not in PRESETS:
            raise ConfigError("invalid_grade", g=cfg.grade)
        data.update(PRESETS[cfg.grade])
    for key in ("operators", "operand_count", "parentheses", "allow_negative",
                "allow_decimal", "allow_remainder", "dedupe", "answer_page", "sheets",
                "show_numbers", "number_direction"):
        value = getattr(cfg, key)
        if value is not None:
            data[key] = value

    for key, default in (("operators", "+-"), ("parentheses", False),
                         ("allow_negative", False), ("allow_decimal", False),
                         ("allow_remainder", False), ("dedupe", True),
                         ("answer_page", True), ("operand_count", 2),
                         ("sheets", 1), ("show_numbers", True),
                         ("number_direction", "row")):
        if data.get(key) is None:
            data[key] = default

    if cfg.topic not in TOPICS:
        raise ConfigError("invalid_topic", topic=cfg.topic, choices="、".join(TOPICS))
    data["topic"] = cfg.topic

    for key, fld in (("operand_ranges", None), ("result_range", None),
                     ("carry", None), ("borrow", None), ("divisor_range", None),
                     ("multiplication_table", None), ("seed", None),
                     ("title", None), ("header", None), ("op_weights", None)):
        v = getattr(cfg, key)
        if v is not None:
            data[key] = v
    data["count"] = cfg.count if cfg.count is not None else data["count"]
    data["columns"] = cfg.columns if cfg.columns is not None else data["columns"]
    data["gap"] = cfg.gap if cfg.gap is not None else TOPIC_DEFAULTS[cfg.topic]["gap"]
    data["answer_lines"] = cfg.answer_lines if cfg.answer_lines is not None else TOPIC_DEFAULTS[cfg.topic]["answer_lines"]
    if data["divisor_range"] is None:
        data["divisor_range"] = (1, 9)
    if data["multiplication_table"] is None:
        data["multiplication_table"] = (1, 9)
    data["explicit_ranges"] = cfg.operand_ranges is not None

    # ---- 校验 ----
    data["operators"] = normalize_operators(data["operators"])
    if not data["operators"] or any(c not in OPERATORS for c in data["operators"]):
        raise ConfigError("invalid_operators", ops=data["operators"])
    weights = data.get("op_weights") or {}
    data["op_weights"] = {
        normalize_operators(k): v for k, v in weights.items()}
    for k, v in data["op_weights"].items():
        if k not in data["operators"]:
            raise ConfigError("invalid_op_weight", op=k, ops=data["operators"])
        if v < 0:
            raise ConfigError("negative_op_weight", op=k, v=v)
    if data["count"] <= 0:
        raise ConfigError("count_positive", n=data["count"])
    if data["count"] > 500:
        raise ConfigError("count_too_many", n=data["count"])
    if data["sheets"] <= 0:
        raise ConfigError("sheets_positive", n=data["sheets"])
    if data["sheets"] > 100:
        raise ConfigError("sheets_too_many", n=data["sheets"])
    if data["columns"] not in (1, 2, 3):
        raise ConfigError("invalid_columns", n=data["columns"])
    if data["gap"] < 0:
        raise ConfigError("gap_negative", n=data["gap"])
    if data["answer_lines"] < 0:
        raise ConfigError("answer_lines_negative", n=data["answer_lines"])
    if data["number_direction"] not in ("row", "column"):
        raise ConfigError("invalid_number_direction", v=data["number_direction"])
    if data["operand_count"] < 2 or data["operand_count"] > 4:
        raise ConfigError("operand_count_range", n=data["operand_count"])
    ranges = data["operand_ranges"]
    if ranges is None:
        ranges = [(1, 20), (1, 20)]
    if len(ranges) != data["operand_count"]:
        if cfg.operand_ranges is None:
            ranges = [ranges[0]] * data["operand_count"]
        else:
            raise ConfigError("ranges_count_mismatch", got=len(ranges),
                              want=data["operand_count"], example=(1, 9))
    for r in ranges:
        _check_range("range_invalid_operand", r)
    data["operand_ranges"] = list(ranges)

    rr = data.get("result_range")
    if rr is None:
        rr = (0, max(hi for _, hi in ranges) * (2 if "×" in data["operators"] else 1) + 9)
    _check_range("range_invalid_result", rr)
    data["result_range"] = rr
    if data["result_range"][0] < 0 and not data["allow_negative"]:
        raise ConfigError("result_negative")

    dr = data["divisor_range"]
    _check_range("range_invalid_divisor", dr)
    if dr[0] < 1:
        raise ConfigError("divisor_min")
    data["divisor_range"] = dr

    mt = data["multiplication_table"]
    _check_range("range_invalid_table", mt)
    data["multiplication_table"] = mt

    if data["seed"] is None:
        data["seed"] = random_seed()
    if data["title"] is None:
        if data["lang"] == "en":
            data["title"] = f"Math Practice (Grade {cfg.grade})" if cfg.grade else "Math Practice"
        else:
            data["title"] = f"小学数学练习（{'一二三四五六'[cfg.grade - 1] if cfg.grade else ''}年级）"
    if data["header"] is None:
        data["header"] = ("Name: __________  Class: __________  Date: __________"
                          if data["lang"] == "en" else
                          "姓名：__________  班级：__________  日期：__________")
    return ResolvedConfig(**data)


def random_seed() -> int:
    import secrets

    return secrets.randbelow(2**31)
