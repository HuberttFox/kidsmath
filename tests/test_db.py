import sqlite3
import pytest
import mathgen.db as db


def test_configure_and_tables():
    conn = db.get_conn()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "sessions", "config_history", "saved_configs"} <= tables


def test_user_crud():
    uid = db.create_user("家长", "hash1")
    assert db.get_user_by_name("家长")["id"] == uid
    assert db.get_user_by_name("家长")["password_hash"] == "hash1"
    assert db.get_user_by_id(uid)["username"] == "家长"
    assert db.get_user_by_name("不存在") is None


def test_duplicate_username_raises():
    db.create_user("a", "h")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("a", "h")


def test_sessions():
    uid = db.create_user("u", "h")
    db.create_session("tokhash", uid, "2099-01-01T00:00:00")
    assert db.get_user_by_token_hash("tokhash")["username"] == "u"
    assert db.get_user_by_token_hash("bad") is None
    db.create_session("exp", uid, "2000-01-01T00:00:00")
    assert db.get_user_by_token_hash("exp") is None  # 过期
    db.delete_session("tokhash")
    assert db.get_user_by_token_hash("tokhash") is None
    db.cleanup_sessions("2001-01-01T00:00:00")
    assert db.get_user_by_token_hash("exp") is None


def test_history_cap_200():
    uid = db.create_user("u", "h")
    for i in range(205):
        db.add_history(uid, f'{{"n": {i}}}')
    rows = db.list_history(uid)
    assert len(rows) == 200
    assert rows[0]["config_json"] == '{"n": 204}'  # 最新优先


def test_history_delete_owner_scoped():
    uid1 = db.create_user("u1", "h")
    uid2 = db.create_user("u2", "h")
    hid = db.add_history(uid1, "{}")
    assert not db.delete_history(uid2, hid)  # 跨用户 404
    assert db.delete_history(uid1, hid)


def test_saved_ops():
    uid = db.create_user("u", "h")
    sid = db.add_saved(uid, "卷A", "{}")
    assert db.get_saved(uid, sid)["name"] == "卷A"
    assert db.rename_saved(uid, sid, "卷B")
    assert db.get_saved(uid, sid)["name"] == "卷B"
    assert not db.delete_saved(uid + 1, sid)
    assert db.delete_saved(uid, sid)


def test_get_history_owner_scoped():
    uid1 = db.create_user("u1", "h")
    uid2 = db.create_user("u2", "h")
    hid = db.add_history(uid1, "{}")
    assert db.get_history(uid1, hid) is not None
    assert db.get_history(uid2, hid) is None


def test_mistake_crud_and_scoping():
    uid1 = db.create_user("u1", "h")
    uid2 = db.create_user("u2", "h")
    mid = db.add_mistake(uid1, "sheet", "vertical", "23 + 48 = ____", "71",
                         "23 + 48", '{"topic": "vertical"}', '{"grade": "2", "seed": 1}',
                         3, "粗心")
    row = db.get_mistake(uid1, mid)
    assert row["kind"] == "sheet" and row["question_json"] == '{"topic": "vertical"}'
    assert row["due_at"] == row["wrong_at"]
    assert db.get_mistake(uid2, mid) is None
    assert len(db.list_mistakes(uid1)) == 1
    assert db.update_review(uid1, mid, 2.6, 1, 1, "2099-01-01", 5)
    assert not db.update_review(uid2, mid, 2.5, 1, 1, "2099-01-01", 5)
    assert db.set_mastered(uid1, mid, "2099-01-01")
    assert db.due_mistakes(uid1, "2100-01-01") == []
    assert db.set_mastered(uid1, mid, None)
    assert db.due_mistakes(uid1, "2100-01-01") == []
    assert db.delete_mistake(uid1, mid)
    assert not db.delete_mistake(uid2, mid)


def test_due_queue_ordering():
    uid = db.create_user("u1", "h")
    a = db.add_mistake(uid, "manual", "arithmetic", "1+1", "2", None, None, None, None, None)
    b = db.add_mistake(uid, "manual", "arithmetic", "2+2", "4", None, None, None, None, None)
    db.update_review(uid, a, 2.5, 1, 0, "2020-01-01", None)
    due = db.due_mistakes(uid, "2030-01-01")
    assert due[0]["id"] == a
    assert [r["id"] for r in due] == [a, b]
