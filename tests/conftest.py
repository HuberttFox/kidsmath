"""测试隔离：每个测试用独立临时 SQLite 库。"""
import pytest
import mathgen.db as db


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    db.configure(str(tmp_path / "test.db"))
    yield
    db.configure(None)
