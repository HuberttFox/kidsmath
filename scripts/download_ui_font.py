"""下载并子集化悠哉圆体（Yozai，OFL 1.1），输出到 src/mathgen/static/fonts/。

子集字符 = i18n 文案 + 模板静态文本 + ASCII/标点。离线或失败可跳过
（页面会降级系统字体栈）。网络可用时执行：
    uv run python scripts/download_ui_font.py
"""
import json
import sys
import urllib.request
from pathlib import Path

from fontTools import subset

REPO = "lxgw/yozai-font"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
LICENSE_URL = f"https://raw.githubusercontent.com/{REPO}/master/OFL.txt"
OUT = Path(__file__).resolve().parent.parent / "src" / "mathgen" / "static" / "fonts"
BASE_ASCII = "".join(chr(c) for c in range(32, 127))


def _fetch(url: str, dest: Path) -> None:
    print(f"下载 {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "mathgen-font-tool"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())


def _chars() -> set[str]:
    root = Path(__file__).resolve().parent.parent / "src" / "mathgen"
    texts: list[str] = [BASE_ASCII]
    # 扫描所有会以 Yozai 渲染的文案源：i18n 字典、模板、静态 js/css、
    # 以及运行时拼进步骤/题面/答案页的 topics/*.py 字符串。
    for pat in ("i18n.py", "templates/*.html", "static/*.js", "static/*.css",
                "topics/*.py"):
        for p in root.glob(pat):
            texts.append(p.read_text(encoding="utf-8"))
    return {c for t in texts for c in t if ord(c) > 31}


def _subset(ttf: Path, out_ttf: Path, out_woff2: Path, chars: set[str]) -> None:
    opts = subset.Options()
    opts.font_number = 0
    opts.ignore_missing_glyphs = True
    font = subset.load_font(str(ttf), opts)
    sub = subset.Subsetter(options=opts)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(font)
    subset.save_font(font, str(out_ttf), opts)
    try:
        import brotli  # noqa: F401
        w2 = subset.Options()
        w2.font_number = 0
        w2.flavor = "woff2"
        w2.ignore_missing_glyphs = True
        subset.save_font(font, str(out_woff2), w2)
        print(f"已生成 {out_ttf.name} / {out_woff2.name}")
    except ImportError:
        print("未安装 brotli，woff2 跳过（仅 ttf）")
    except Exception as e:
        print(f"woff2 生成失败（{e}），仅保留 ttf")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(RELEASE_API, timeout=30) as r:
            rel = json.load(r)
    except Exception as e:
        print(f"获取 release 失败：{e}；跳过（页面将降级系统字体）。")
        return 1
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    weights = {"Yozai-Regular.ttf": "400", "Yozai-Medium.ttf": "700"}
    chars = _chars()
    for name, w in weights.items():
        url = assets.get(name)
        if not url:
            print(f"缺少资产 {name}，跳过")
            continue
        tmp = OUT / f".{name}"
        try:
            _fetch(url, tmp)
        except Exception as e:
            print(f"下载 {name} 失败：{e}")
            tmp.unlink(missing_ok=True)
            continue
        _subset(tmp, OUT / f"yozai-{w}.ttf", OUT / f"yozai-{w}.woff2", chars)
        tmp.unlink(missing_ok=True)
    try:
        _fetch(LICENSE_URL, OUT / "OFL-yozai.txt")
    except Exception as e:
        print(f"许可证下载失败：{e}")
    print(f"字体已就绪：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
