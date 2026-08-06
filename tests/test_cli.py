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


def test_generation_conflict_returns_1_chinese_no_traceback():
    r = run_cli("--operators", "-", "--ranges", "0-9,0-9",
                "--result-range", "100-200", "--format", "text")
    assert r.returncode == 1
    assert "生成失败" in r.stderr
    assert "Traceback" not in r.stderr


def test_config_unknown_key_returns_2_chinese_no_traceback():
    import tempfile
    import pathlib
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "c.toml"
        p.write_text('operator = "+"\ncount = 4\n', encoding="utf-8")
        r = run_cli("-c", str(p), "--format", "text")
    assert r.returncode == 2
    assert "配置项有误" in r.stderr
    assert "Traceback" not in r.stderr


def test_bare_generate_text():
    r = run_cli("--format", "text")
    assert r.returncode == 0, r.stderr
    assert "1." in r.stdout


def test_toml_table_alias_maps_to_multiplication_table():
    import tempfile
    import pathlib
    from mathgen.cli import _cfg_from_ns, _parse_argv
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "c.toml"
        p.write_text('table = [1, 9]\ncount = 4\n', encoding="utf-8")
        cfg = _cfg_from_ns(_parse_argv(["-c", str(p)]))
    assert cfg.multiplication_table == (1, 9)


def test_toml_topic_not_clobbered_by_flag_default():
    import tempfile
    import pathlib
    from mathgen.cli import _cfg_from_ns, _parse_argv
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "c.toml"
        p.write_text('topic = "vertical"\ncount = 4\n', encoding="utf-8")
        cfg = _cfg_from_ns(_parse_argv(["-c", str(p)]))
    assert cfg.topic == "vertical"


def test_topic_flag_beats_toml():
    import tempfile
    import pathlib
    from mathgen.cli import _cfg_from_ns, _parse_argv
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "c.toml"
        p.write_text('topic = "vertical"\ncount = 4\n', encoding="utf-8")
        cfg = _cfg_from_ns(_parse_argv(["-c", str(p), "-t", "arithmetic"]))
    assert cfg.topic == "arithmetic"


def test_sheets_without_zip_writes_individual_pdfs():
    import pathlib
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        prefix = str(d / "sheet")
        r = run_cli("--sheets", "2", "--format", "pdf", "-f", prefix)
        assert r.returncode == 0, r.stderr
        assert (d / "sheet-01.pdf").exists()
        assert (d / "sheet-02.pdf").exists()
        assert not (d / "sheet.zip").exists()


def test_sheets_with_zip_writes_single_zip():
    import pathlib
    import tempfile
    import zipfile
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        prefix = str(d / "sheet")
        r = run_cli("--sheets", "2", "--zip", "--format", "pdf", "-f", prefix)
        assert r.returncode == 0, r.stderr
        z = d / "sheet.zip"
        assert z.exists()
        with zipfile.ZipFile(z) as zf:
            assert sorted(zf.namelist()) == ["sheet-01.pdf", "sheet-02.pdf"]
