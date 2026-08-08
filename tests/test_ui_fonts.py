"""UI 字体（Yozai 子集）覆盖测试：所有网页文案汉字必须已子集化。

若失败：运行 `uv run python scripts/download_ui_font.py` 重新子集化并提交字体。
emoji 区（U+1F000-1FAFF、✍-ⓘ 类 dingbat）走系统 emoji 字体，不属 Yozai 职责。
"""
import re
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "src" / "mathgen" / "static" / "fonts" / "yozai-400.ttf"
SRC = ROOT / "src" / "mathgen"
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2700-\u27BF\u2B50\uFE0F]")


def _source_chars() -> set[str]:
    chars: set[str] = set()
    # 与 scripts/download_ui_font.py 的扫描清单保持一致：含运行时渲染的
    # topics/*.py（解题步骤等），确保 Yozai 子集覆盖 PDF 之外的网页文案。
    for pat in ("i18n.py", "templates/*.html", "static/*.js", "static/*.css",
                "topics/*.py"):
        for p in SRC.glob(pat):
            chars |= {c for c in p.read_text(encoding="utf-8") if ord(c) > 127}
    return {c for c in chars if not EMOJI_RE.match(c)}


def test_yozai_covers_all_ui_chars():
    assert FONT.exists(), f"缺少字体 {FONT}，先运行 scripts/download_ui_font.py"
    cmap = TTFont(str(FONT)).getBestCmap()
    missing = sorted(c for c in _source_chars() if ord(c) not in cmap)
    assert not missing, (
        f"UI 文案 {len(missing)} 字不在 Yozai 子集：{''.join(missing)!r}。"
        f"运行 scripts/download_ui_font.py 重新子集化并提交。")


def test_yozai_hero_title_fully_covered():
    cmap = TTFont(str(FONT)).getBestCmap()
    title = "给孩子出数学题，像做游戏一样简单"
    missing = [c for c in title if ord(c) > 127 and ord(c) not in cmap]
    assert not missing, f"产品页标题缺字: {missing!r}"
