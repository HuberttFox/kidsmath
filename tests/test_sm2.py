from mathgen.sm2 import sm2_update


def test_q1_resets_and_lowers_ease():
    assert sm2_update(1, 2.5, 6, 3) == (2.30, 1, 0)


def test_q3_lowers_ease_slightly():
    assert sm2_update(3, 2.5, 0, 0) == (2.36, 1, 1)


def test_q5_raises_ease():
    assert sm2_update(5, 2.5, 0, 0) == (2.60, 1, 1)


def test_interval_progression():
    e, i, r = 2.5, 0, 0
    e, i, r = sm2_update(5, e, i, r)
    assert i == 1
    e, i, r = sm2_update(5, e, i, r)
    assert i == 6
    e, i, r = sm2_update(5, e, i, r)
    assert i == round(6 * e)


def test_ease_floor_1_3():
    assert sm2_update(1, 1.3, 1, 0)[0] == 1.3


def test_interval_monotonic_over_10_successes():
    e, i, r = 2.5, 0, 0
    prev = 0
    for _ in range(10):
        e, i, r = sm2_update(5, e, i, r)
        assert i >= prev
        prev = i
