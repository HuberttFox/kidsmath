import subprocess
import sys


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "mathgen.cli", *args],
                          capture_output=True, text=True)


def test_help_exits_zero():
    r = run_cli("--help")
    assert r.returncode == 0
    assert "grade" in r.stdout


def test_generate_text():
    r = run_cli("--grade", "1", "--count", "3", "--format", "text")
    assert r.returncode == 0, r.stderr
    assert "1." in r.stdout and "= ____" in r.stdout


def test_bad_grade_returns_2():
    r = run_cli("--grade", "9")
    assert r.returncode == 2
    assert "年级" in r.stderr


def test_config_file_toml():
    import tempfile
    import pathlib
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "c.toml"
        p.write_text('grade = 1\ncount = 4\n', encoding="utf-8")
        r = run_cli("-c", str(p), "--format", "text")
    assert r.returncode == 0, r.stderr
    assert "1." in r.stdout
