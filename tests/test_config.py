import pytest
from mathgen.config import Config, ConfigError, PRESETS, resolve


def test_default_resolve_applies_preset_and_topic_defaults():
    r = resolve(Config(grade=2))
    assert r.operators == "+-×"
    assert r.operand_ranges == [(1, 99), (1, 99)]
    assert r.carry is True and r.borrow is True
    assert r.seed >= 0
    assert r.gap >= 10


def test_explicit_override_beats_preset():
    r = resolve(Config(grade=2, operand_count=3))
    assert r.operand_count == 3
    assert r.operand_ranges == [(1, 99), (1, 99), (1, 99)]


def test_bad_operator_raises_chinese_error():
    with pytest.raises(ConfigError, match="运算符"):
        resolve(Config(operators="%"))


def test_bad_range_raises_chinese_error():
    with pytest.raises(ConfigError, match="范围"):
        resolve(Config(grade=2, operand_ranges=[(99, 1), (1, 99)]))


def test_negative_count_raises():
    with pytest.raises(ConfigError):
        resolve(Config(count=0))


def test_all_grades_resolve():
    for g in range(1, 7):
        r = resolve(Config(grade=g))
        assert r.operators, f"grade {g} empty operators"


def test_explicit_false_overrides_preset_parentheses():
    r = resolve(Config(grade=5, parentheses=False))
    assert r.parentheses is False


def test_explicit_operators_overrides_preset():
    r = resolve(Config(grade=2, operators="+-"))
    assert r.operators == "+-"


def test_explicit_answer_page_false_overrides_preset():
    r = resolve(Config(grade=2, answer_page=False))
    assert r.answer_page is False


def test_zero_operand_count_raises_chinese_error():
    with pytest.raises(ConfigError, match="运算数个数"):
        resolve(Config(operand_count=0))
