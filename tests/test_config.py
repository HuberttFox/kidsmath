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


def test_count_cap_raises():
    with pytest.raises(ConfigError, match="题目数量过大"):
        resolve(Config(count=501))


def test_sheets_cap_raises():
    with pytest.raises(ConfigError, match="卷子份数过大"):
        resolve(Config(sheets=101))


def test_all_grades_resolve():
    for g in range(1, 7):
        r = resolve(Config(grade=g))
        assert r.operators, f"grade {g} empty operators"


def test_operators_chinese_aliases_normalized():
    r = resolve(Config(operators="加减乘除"))
    assert r.operators == "+-×÷"
    r2 = resolve(Config(operators="加乘加除"))
    assert r2.operators == "+×÷"


def test_operators_mixed_chinese_and_symbols():
    r = resolve(Config(operators="加减×"))
    assert r.operators == "+-×"


def test_operators_unknown_chinese_still_errors():
    with pytest.raises(ConfigError, match="运算符"):
        resolve(Config(operators="加法"))


def test_lang_defaults_zh_title():
    r = resolve(Config(grade=2))
    assert r.lang == "zh"
    assert "小学数学练习" in r.title
    assert "姓名" in r.header


def test_lang_en_title_and_header():
    r = resolve(Config(grade=2, lang="en"))
    assert r.lang == "en"
    assert r.title == "Math Practice (Grade 2)"
    assert "Name:" in r.header
    r2 = resolve(Config(lang="en"))
    assert r2.title == "Math Practice"


def test_invalid_lang_raises():
    with pytest.raises(ConfigError, match="语言"):
        resolve(Config(lang="fr"))


def test_op_weights_validated_and_filtered():
    r = resolve(Config(grade=2, operators="+-×", op_weights={"+": 5, "-": 0, "×": 2}))
    assert r.op_weights == {"+": 5, "-": 0, "×": 2}
    with pytest.raises(ConfigError, match="权重"):
        resolve(Config(grade=2, operators="+-", op_weights={"÷": 5}))
    with pytest.raises(ConfigError, match="权重"):
        resolve(Config(grade=2, op_weights={"+": -1}))


def test_op_weights_chinese_keys_normalized():
    r = resolve(Config(operators="加减乘", op_weights={"加": 5, "乘": 1}))
    assert r.op_weights == {"+": 5, "×": 1}


def test_pick_op_respects_weights():
    from mathgen.core.engine import pick_op
    import random
    cfg = resolve(Config(grade=2, operators="+×", op_weights={"+": 1, "×": 0}))
    seen = {pick_op(random.Random(i), cfg) for i in range(50)}
    assert seen == {"+"}
    cfg2 = resolve(Config(grade=2, operators="+×"))
    seen2 = {pick_op(random.Random(i), cfg2) for i in range(50)}
    assert seen2 == {"+", "×"}


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


def test_grade5_preset_operand_count_kept():
    r = resolve(Config(grade=5))
    assert r.operand_count == 3
    assert len(r.operand_ranges) == 3


def test_grade6_preset_operand_count_kept():
    assert resolve(Config(grade=6)).operand_count == 4


def test_explicit_operand_count_overrides_grade5_preset():
    assert resolve(Config(grade=5, operand_count=2)).operand_count == 2


def test_explicit_sheets_overrides_preset_default():
    assert resolve(Config(grade=2, sheets=3)).sheets == 3


def test_bare_resolve_no_grade_no_crash():
    r = resolve(Config())
    assert r.divisor_range == (1, 9)
    assert r.multiplication_table == (1, 9)
