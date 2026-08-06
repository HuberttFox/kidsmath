"""下载并子集化 Noto Sans SC（OFL），输出到 src/mathgen/assets/font/NotoSansSC-Regular.ttf。
子集字符 = 应用题模板 + 常用 UI 字。离线或失败可跳过（有系统字体兜底）。"""
import sys
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.varLib.instancer import instantiateVariableFont

URL = ("https://raw.githubusercontent.com/google/fonts/main/"
       "ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf")
OUT = Path(__file__).resolve().parent.parent / "src" / "mathgen" / "assets" / "font" / "NotoSansSC-Regular.ttf"
EXTRA = "数学练习卷参考答案班级姓名日期年级题号一二三四五六七八九十加减乘除等于在有个小明小红小华小丽小刚苹果铅笔书本橡皮梨桃子草莓糖果气球小鸟鱼兔猫狗树花操场教室商店书店公园家里水彩笔作业本格子尺子跑步分钟小时元角分还剩多少一共原来后来又买送吃了走回家" + "0123456789（）()。，、：:____×÷＋－+- "


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".otf")
    print(f"下载 {URL} → {tmp}")
    urllib.request.urlretrieve(URL, tmp)
    text = "".join(p.read_text(encoding="utf-8") for p in
                   (Path(__file__).resolve().parent.parent / "src" / "mathgen" / "topics").glob("*.py"))
    # 修复 F1：不再用正则过滤，全量子集化 topics/*.py + EXTRA 中的字符。
    # 旧实现的正则白名单漏掉全角标点（？；）与数学符号（− –），模板字符会静默丢失；
    # 全量子集由 tests/test_fonts.py 回归测试兜底（断言 topics 全部非 ASCII 字符在 cmap）。
    chars = sorted(set(text + EXTRA))
    opts = subset.Options()
    opts.font_number = 0
    opts.ignore_missing_glyphs = True
    font = subset.load_font(tmp, opts)
    subsetter = subset.Subsetter(options=opts)
    subsetter.populate(text="".join(chars))
    subsetter.subset(font)
    font = instantiateVariableFont(font, {"wght": 400})
    subset.save_font(font, OUT, opts)
    tmp.unlink()
    print(f"已生成 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
