"""SQLite 数据层：用户/会话/历史配置/保存配置。模块单例连接 + Lock。"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_DB = Path("data/kidsmath.db")
HISTORY_CAP = 200
SESSION_DAYS = 30

_lock = threading.RLock()  # configure→get_conn 重入
_conn: sqlite3.Connection | None = None
_path: str | None = None


def configure(path: str | None = None) -> None:
    """设置数据库路径并重建连接（None = 重置）。测试隔离用。"""
    global _conn, _path
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
        _path = path
        if path is not None:
            get_conn()


def _resolve_path() -> str:
    env = os.environ.get("KIDSMATH_DB")
    if env:
        return env
    p = _path or str(DEFAULT_DB)
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    return p


def get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            conn = sqlite3.connect(_resolve_path(), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # 注意：不用 WAL——在 drvfs/网络盘上 WAL 共享内存会挂起
            conn.execute("PRAGMA busy_timeout=5000")
            _init_tables(conn)
            _conn = conn
        return _conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
      token_hash TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL REFERENCES users(id),
      expires_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS config_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      config_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS saved_configs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      config_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_history_user ON config_history(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_saved_user ON saved_configs(user_id);
    CREATE TABLE IF NOT EXISTS mistakes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id),
      kind TEXT NOT NULL,
      topic TEXT NOT NULL,
      problem TEXT NOT NULL,
      answer TEXT NOT NULL,
      expression TEXT,
      question_json TEXT,
      params TEXT,
      q_index INTEGER,
      note TEXT,
      wrong_at TEXT NOT NULL,
      ease REAL NOT NULL DEFAULT 2.5,
      interval INTEGER NOT NULL DEFAULT 0,
      reps INTEGER NOT NULL DEFAULT 0,
      due_at TEXT NOT NULL,
      last_q INTEGER,
      mastered_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_mistakes_queue ON mistakes(user_id, due_at);
    """)
    conn.commit()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_user(username: str, password_hash: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, now_iso()))
    conn.commit()
    return cur.lastrowid


def get_user_by_name(username: str) -> dict | None:
    row = get_conn().execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE username=?",
        (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(uid: int) -> dict | None:
    row = get_conn().execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE id=?",
        (uid,)).fetchone()
    return dict(row) if row else None


def create_session(token_hash: str, user_id: int, expires_at: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, expires_at))
    conn.commit()


def get_user_by_token_hash(token_hash: str) -> dict | None:
    row = get_conn().execute(
        "SELECT u.id, u.username, u.password_hash, u.created_at "
        "FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash=? AND s.expires_at > ?",
        (token_hash, now_iso())).fetchone()
    return dict(row) if row else None


def delete_session(token_hash: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
    conn.commit()


def cleanup_sessions(now: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    conn.commit()


def add_history(user_id: int, config_json: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO config_history (user_id, config_json, created_at) VALUES (?, ?, ?)",
        (user_id, config_json, now_iso()))
    conn.execute(
        "DELETE FROM config_history WHERE id NOT IN ("
        "SELECT id FROM config_history WHERE user_id=? "
        "ORDER BY created_at DESC, id DESC LIMIT ?) AND user_id=?",
        (user_id, HISTORY_CAP, user_id))
    conn.commit()
    return cur.lastrowid


def list_history(user_id: int) -> list[dict]:
    rows = get_conn().execute(
        "SELECT id, config_json, created_at FROM config_history "
        "WHERE user_id=? ORDER BY created_at DESC, id DESC",
        (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_history(user_id: int, hid: int) -> dict | None:
    row = get_conn().execute(
        "SELECT id, config_json, created_at FROM config_history "
        "WHERE id=? AND user_id=?", (hid, user_id)).fetchone()
    return dict(row) if row else None


def delete_history(user_id: int, hid: int) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM config_history WHERE id=? AND user_id=?", (hid, user_id))
    conn.commit()
    return cur.rowcount > 0


def add_saved(user_id: int, name: str, config_json: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO saved_configs (user_id, name, config_json, created_at) "
        "VALUES (?, ?, ?, ?)", (user_id, name, config_json, now_iso()))
    conn.commit()
    return cur.lastrowid


def list_saved(user_id: int) -> list[dict]:
    rows = get_conn().execute(
        "SELECT id, name, config_json, created_at FROM saved_configs "
        "WHERE user_id=? ORDER BY created_at DESC, id DESC",
        (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_saved(user_id: int, sid: int) -> dict | None:
    row = get_conn().execute(
        "SELECT id, name, config_json, created_at FROM saved_configs "
        "WHERE id=? AND user_id=?", (sid, user_id)).fetchone()
    return dict(row) if row else None


def rename_saved(user_id: int, sid: int, name: str) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "UPDATE saved_configs SET name=? WHERE id=? AND user_id=?",
        (name, sid, user_id))
    conn.commit()
    return cur.rowcount > 0


def delete_saved(user_id: int, sid: int) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM saved_configs WHERE id=? AND user_id=?", (sid, user_id))
    conn.commit()
    return cur.rowcount > 0


def add_mistake(user_id, kind, topic, problem, answer, expression,
                question_json, params, q_index, note) -> int:
    conn = get_conn()
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO mistakes (user_id, kind, topic, problem, answer, expression, "
        "question_json, params, q_index, note, wrong_at, due_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, kind, topic, problem, answer, expression, question_json,
         params, q_index, note, now, now))
    conn.commit()
    return cur.lastrowid


def list_mistakes(user_id):
    rows = get_conn().execute(
        "SELECT * FROM mistakes WHERE user_id=? ORDER BY wrong_at DESC, id DESC",
        (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_mistake(user_id, mid):
    row = get_conn().execute(
        "SELECT * FROM mistakes WHERE id=? AND user_id=?", (mid, user_id)).fetchone()
    return dict(row) if row else None


def update_review(user_id, mid, ease, interval, reps, due_at, last_q) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "UPDATE mistakes SET ease=?, interval=?, reps=?, due_at=?, last_q=? "
        "WHERE id=? AND user_id=?", (ease, interval, reps, due_at, last_q, mid, user_id))
    conn.commit()
    return cur.rowcount > 0


def set_mastered(user_id, mid, ts) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "UPDATE mistakes SET mastered_at=? WHERE id=? AND user_id=?", (ts, mid, user_id))
    conn.commit()
    return cur.rowcount > 0


def delete_mistake(user_id, mid) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM mistakes WHERE id=? AND user_id=?", (mid, user_id))
    conn.commit()
    return cur.rowcount > 0


def update_note(user_id, mid, note) -> bool:
    conn = get_conn()
    cur = conn.execute("UPDATE mistakes SET note=? WHERE id=? AND user_id=?",
                       (note, mid, user_id))
    conn.commit()
    return cur.rowcount > 0


def due_mistakes(user_id, now):
    rows = get_conn().execute(
        "SELECT * FROM mistakes WHERE user_id=? AND mastered_at IS NULL "
        "AND due_at <= ? ORDER BY due_at ASC, id ASC", (user_id, now)).fetchall()
    return [dict(r) for r in rows]
