"""参数模型、校验与年级预设。所有错误消息为中文。"""
from __future__ import annotations

from dataclasses import dataclass, field


class ConfigError(ValueError):
    """参数校验失败，消息为中文。"""


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


def _check_range(name: str, r: tuple[int, int]) -> None:
    lo, hi = r
    if lo < 0 or hi < lo:
        raise ConfigError(f"{name}范围不合法：应为 (最小值, 最大值) 且最小值 ≥ 0，当前 {r}。建议调换大小或改为非负值。")


def resolve(cfg: Config) -> ResolvedConfig:
    """合并年级预设 + 题型默认 + 显式参数，校验后返回 ResolvedConfig。"""
    data: dict = vars(Config())
    data.pop("grade")
    if cfg.grade is not None:
        if cfg.grade not in PRESETS:
            raise ConfigError(f"年级 {cfg.grade} 不在 1-6 之间。建议改为 1 到 6。")
        data.update(PRESETS[cfg.grade])
    for key in ("operators", "operand_count", "parentheses", "allow_negative",
                "allow_decimal", "allow_remainder", "dedupe", "answer_page", "sheets"):
        value = getattr(cfg, key)
        if value is not None:
            data[key] = value

    for key, default in (("operators", "+-"), ("parentheses", False),
                         ("allow_negative", False), ("allow_decimal", False),
                         ("allow_remainder", False), ("dedupe", True),
                         ("answer_page", True), ("operand_count", 2),
                         ("sheets", 1)):
        if data.get(key) is None:
            data[key] = default

    if cfg.topic not in TOPICS:
        raise ConfigError(f"题型 {cfg.topic} 不支持，可选：{', '.join(TOPICS)}。")
    data["topic"] = cfg.topic

    for key, fld in (("operand_ranges", None), ("result_range", None),
                     ("carry", None), ("borrow", None), ("divisor_range", None),
                     ("multiplication_table", None), ("seed", None),
                     ("title", None), ("header", None)):
        v = getattr(cfg, key)
        if v is not None:
            data[key] = v
    data["count"] = cfg.count
    data["columns"] = cfg.columns
    data["gap"] = cfg.gap if cfg.gap is not None else TOPIC_DEFAULTS[cfg.topic]["gap"]
    data["answer_lines"] = cfg.answer_lines if cfg.answer_lines is not None else TOPIC_DEFAULTS[cfg.topic]["answer_lines"]
    if data["divisor_range"] is None:
        data["divisor_range"] = (1, 9)
    if data["multiplication_table"] is None:
        data["multiplication_table"] = (1, 9)

    # ---- 校验 ----
    if not data["operators"] or any(c not in OPERATORS for c in data["operators"]):
        raise ConfigError(f"运算符 {data['operators']!r} 不合法，可选字符：+ − × ÷（如 \"+−×\"）。")
    if data["count"] <= 0:
        raise ConfigError(f"题目数量必须 > 0，当前 {data['count']}。建议改为 1 或更大。")
    if data["sheets"] <= 0:
        raise ConfigError(f"卷子份数必须 > 0，当前 {data['sheets']}。")
    if data["columns"] not in (1, 2, 3):
        raise ConfigError(f"分栏数 {data['columns']} 不支持，可选 1、2、3。")
    if data["gap"] < 0:
        raise ConfigError(f"题间距不能为负，当前 {data['gap']}。")
    if data["answer_lines"] < 0:
        raise ConfigError(f"答题横线数不能为负，当前 {data['answer_lines']}。")
    if data["operand_count"] < 2:
        raise ConfigError(
            f"运算数个数必须 ≥ 2，当前 {data['operand_count']}。建议改为 2 到 4。")
    ranges = data["operand_ranges"]
    if ranges is None:
        ranges = [(1, 20), (1, 20)]
    if len(ranges) != data["operand_count"]:
        if cfg.operand_ranges is None:
            ranges = [ranges[0]] * data["operand_count"]
        else:
            raise ConfigError(
                f"运算数范围个数 {len(ranges)} 与运算数个数 {data['operand_count']} 不一致。"
                f"建议：每个运算数提供一个 (min, max)，如 {(1, 9)} ×{data['operand_count']}。")
    for r in ranges:
        _check_range("运算数", r)
    data["operand_ranges"] = list(ranges)

    rr = data.get("result_range")
    if rr is None:
        rr = (0, max(hi for _, hi in ranges) * (2 if "×" in data["operators"] else 1) + 9)
    _check_range("结果", rr)
    data["result_range"] = rr
    if data["result_range"][0] < 0 and not data["allow_negative"]:
        raise ConfigError("结果范围最小值为负，但 allow_negative=False。建议开启 allow_negative 或把结果最小值改为 0。")

    dr = data["divisor_range"]
    _check_range("除数", dr)
    if dr[0] < 1:
        raise ConfigError("除数范围最小值必须 ≥ 1，除数不能为 0。建议改为 (1, 9)。")
    data["divisor_range"] = dr

    mt = data["multiplication_table"]
    _check_range("乘法表", mt)
    data["multiplication_table"] = mt

    if data["seed"] is None:
        data["seed"] = random_seed()
    if data["title"] is None:
        data["title"] = f"小学数学练习（{'一二三四五六'[cfg.grade - 1] if cfg.grade else ''}年级）"
    if data["header"] is None:
        data["header"] = "姓名：__________  班级：__________  日期：__________"
    return ResolvedConfig(**data)


def random_seed() -> int:
    import secrets

    return secrets.randbelow(2**31)
