from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

BUNDLED = Path(__file__).resolve().parent.parent / "src" / "mathgen" / "assets" / "font" / "NotoSansSC-Regular.ttf"

NEEDED = "数学练习卷参考答案班级姓名日期年级一二三四五六加减乘除" + " "


def test_bundled_font_coverage_and_instantiated():
    if not BUNDLED.exists():
        pytest.skip(f"打包字体不存在（未运行 scripts/download_font.py？）：{BUNDLED}")
    font = TTFont(BUNDLED)
    cmap = font.getBestCmap()
    missing = [c for c in NEEDED if ord(c) not in cmap]
    assert not missing, f"子集字体缺少字符：{''.join(missing)!r}"
    assert "fvar" not in font, "字体仍是可变字体（未实例化 wght），需重新运行 scripts/download_font.py"
    assert "gvar" not in font, "字体仍含 gvar（未实例化 wght），需重新运行 scripts/download_font.py"
