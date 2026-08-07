from mathgen.parser import parse_examples


def _f(text):
    return parse_examples(text)["fields"]


def test_arithmetic_basic():
    f = _f("12 + 34 = 46\n23 - 11 = 12\n15 + 20 = 35")
    assert f["topic"] == "arithmetic"
    assert set(f["operators"]) == set("+-")
    assert f["operand_count"] == "2"
    assert f["result_range"] == "0-100"


def test_chain_expression_operand_count():
    f = _f("12 + 34 + 5 = 51\n7 + 8 + 9 = 24")
    assert f["operand_count"] == "3"


def test_operand_count_clamped_to_4():
    f = _f("1 + 2 + 3 + 4 + 5 = 15")
    assert f["operand_count"] == "4"


def test_vertical_folding():
    f = _f("23\n+48\n----\n71\n45\n-17\n----\n28")
    assert f["topic"] == "arithmetic"
    assert set(f["operators"]) == set("+-")


def test_word_problem_detection():
    f = _f("小明有 3 个苹果，又买了 5 个，一共几个？\n小红有 8 颗糖，吃了 3 颗，剩几颗？")
    assert f["topic"] == "word_problem"


def test_mixed_majority_arithmetic():
    f = _f("3 + 5 = 8\n4 - 1 = 3\n小明有 10 本书，借出 2 本，剩几本？")
    assert f["topic"] == "arithmetic"


def test_grade_mapping():
    assert _f("3 + 5 = 8")["grade"] == "1"
    assert _f("34 + 21 = 55")["grade"] == "2"
    assert _f("123 + 45 = 168")["grade"] == "3"
    assert _f("4 × 5 = 20")["grade"] == "3"


def test_parentheses_rate():
    f = _f("(3 + 5) × 2 = 16\n4 × 3 + 1 = 13")
    assert f["parentheses"] == "1"


def test_no_numbers():
    r = parse_examples("今天天气很好")
    assert r["fields"] == {} and r["notes"] == ["no_numbers"]


def test_operator_variants_and_fullwidth():
    f = _f("3x5=15\n6✕7=42\n8*9=72\n12 − 4 = 8")
    assert set(f["operators"]) == set("×-")


def test_numbering_variants():
    f = parse_examples("1. 3+5=8\n（2）4-1=3\n① 2+6=8")
    assert f["recognized"] == 3
    assert f["total"] == 3


def test_count_max_n_10():
    f = _f("3+5=8\n4-1=3\n2+2=4\n5+1=6\n6-2=4\n7+1=8\n8-3=5\n9+2=11\n1+9=10\n2+7=9")
    assert f["count"] == "10"
    f2 = _f("3+5=8\n4-1=3")
    assert f2["count"] == "10"
    f3 = _f("\n".join(f"3+{i}=8" for i in range(1, 16)))
    assert f3["count"] == "15"


def test_answer_suffix_stripped():
    f = parse_examples("23 + 48 = 71\n45 - 17 = 28")
    assert f["recognized"] == 2
    assert f["fields"]["operand_count"] == "2"
    assert set(f["fields"]["operators"]) == set("+-")


def test_negative_leading_line_not_folded():
    f = parse_examples("-3+5=2\n-4+1=-3")
    assert f["fields"]["topic"] == "arithmetic"
    assert f["recognized"] == 2


def test_vertical_expr_rate_not_word_problem():
    f = parse_examples("23\n+48\n----\n71\n45\n-17\n----\n28")
    assert f["fields"]["topic"] == "arithmetic"  # 折叠后 4 行、n=2、
    #                                             expr_rate=0.5（边界过阈值）
