"""빌드한 Audeniq Sans가 DESIGN.md의 약속을 지키는지 확인한다.  python3 tests/check.py"""
import glob
import os
import sys

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAR = os.path.join(ROOT, "fonts", "variable", "AudeniqSansVariable.ttf")
SRC = os.path.join(ROOT, "sources", "PretendardVariable.ttf")
fails = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok:
        fails.append(msg)


def shape(path, text, features=None):
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features or {})
    return [font.glyph_to_string(i.codepoint) for i in buf.glyph_infos], sum(p.x_advance for p in buf.glyph_positions)


def ink(font, glyph, wght):
    gs = font.getGlyphSet(location={"wght": wght}, normalized=False)
    pen = BoundsPen(gs)
    gs[glyph].draw(pen)
    return pen.bounds


f = TTFont(VAR)
src = TTFont(SRC)
cmap = f.getBestCmap()

# 이름: OFL 예약 글꼴 이름 Pretendard를 글꼴 이름으로 쓰지 않는다(저작권 표기 0번은 예외).
for path in [VAR] + sorted(glob.glob(os.path.join(ROOT, "fonts", "static", "*.ttf"))):
    t = TTFont(path, lazy=True)
    bad = [n.nameID for n in t["name"].names if n.nameID in (1, 3, 4, 6, 16, 21, 25) and "Pretendard" in n.toUnicode()]
    check(not bad, f"{os.path.basename(path)}: 이름에 Pretendard 없음 {bad or ''}")
check(f["name"].getDebugName(1) == "Audeniq Sans Variable", "가변 글꼴 패밀리 이름")
check(f["OS/2"].achVendID == "AUDQ", "제작사 코드 AUDQ")

# 한글 자간: 완성형 11,172자 모두 원본보다 40유닛 좁다. 라틴·숫자는 그대로.
hangul = [u for u in range(0xAC00, 0xD7A4)]
diff = {src["hmtx"][src.getBestCmap()[u]][0] - f["hmtx"][cmap[u]][0] for u in hangul}
check(diff == {40}, f"한글 11,172자 폭 -40유닛 (차이 {sorted(diff)})")
# 숫자·영문·통화 기호는 한글보다 살짝 굵게: 400에서 세로 획이 원본보다 굵고, 폭 변화는 2% 안.
for ch in "Il1H0₩":
    g = cmap[ord(ch)]
    grow = f["hmtx"][g][0] - src["hmtx"][g][0]
    check(0 <= grow <= src["hmtx"][g][0] * 0.02, f"'{ch}' 폭 +{grow}유닛 (2% 안)")
for ch, w, least in (("l", 400, 4), ("l", 100, 1), ("I", 400, 4)):
    a, b = ink(f, cmap[ord(ch)], w), ink(src, cmap[ord(ch)], w)
    stem_new, stem_old = a[2] - a[0], b[2] - b[0]
    check(stem_new - stem_old >= least, f"'{ch}' 굵기 {w}: 세로 획 {stem_old:.0f} → {stem_new:.0f}")
a, b = ink(f, "l", 930), ink(src, "l", 930)
check(abs((a[2] - a[0]) - (b[2] - b[0])) < 1, "가장 굵은 930은 원본과 같은 굵기")
for w in (100, 400, 900):
    a = ink(f, "uniAC00", w)
    b = ink(src, "uniAC00", w)
    check(round(b[0] - a[0]) == 20 and round(b[2] - a[2]) == 20, f"'가' 잉크가 굵기 {w}에서 20유닛 왼쪽으로(양쪽 20씩)")

# 숫자 앞 '-'는 빼기 모양, 코드·날짜·전화번호 안의 '-'는 그대로.
cases = {
    "-1,200원": "minus", "(-5%)": "minus", " -3": "minus",
    "KR-A12-26-00001": None, "2026-10-23": None, "010-1234-5678": None, "a-1": None,
}
for text, want in cases.items():
    glyphs, _ = shape(VAR, text)
    has = "minus.case" in glyphs
    check(has == (want == "minus"), f"'{text}' → {'−' if has else '-'}")
glyphs, _ = shape(VAR, "-1,200", {"tnum": True})
check(glyphs[0] == "minus.case", "고정폭 숫자에서도 '-1,200' → '−'")
glyphs, _ = shape(VAR, "-1,200", {"calt": False})
check(glyphs[0] == "minus.case", "calt를 꺼도(letter-spacing을 쓴 글자) rclt로 '−'")

# 고정폭 숫자: 0–9 폭이 모두 같다.
widths = {shape(VAR, d, {"tnum": True})[1] for d in "0123456789"}
check(len(widths) == 1, f"tnum 숫자 폭 하나 {widths}")

# 세로: 한 줄 상자 가운데에 한글·대문자 중심이 온다(버튼 안에서 따로 보정하지 않아도 되게).
hhea = f["hhea"]
box_mid = (hhea.ascent + hhea.descent) / 2
for ch in "한H0":
    b = ink(f, cmap[ord(ch)], 400)
    mid = (b[1] + b[3]) / 2
    check(abs(mid - box_mid) < 40, f"'{ch}' 중심 {mid:.0f} ≈ 줄 상자 중심 {box_mid:.0f}")

# 어데닉 로고: U+F8F0 워드마크, U+F8F1 A 심볼, ss20을 켤 때만 'AUDENIQ' → 워드마크.
check(cmap.get(0xF8F0) == "aq.wordmark" and cmap.get(0xF8F1) == "aq.mark", "로고 글자 U+F8F0·U+F8F1")
glyphs, _ = shape(VAR, "AUDENIQ 스튜디오")
check(glyphs[:2] == ["A", "U"], "기본은 문장 속 AUDENIQ를 글자 그대로")
glyphs, _ = shape(VAR, "AUDENIQ 스튜디오", {"ss20": True})
check(glyphs[0] == "aq.wordmark", "ss20을 켜면 AUDENIQ → 워드마크")
glyphs, _ = shape(VAR, "Audeniq", {"ss20": True})
check("aq.wordmark" not in glyphs, "대문자 AUDENIQ만 바뀜")
colr = {r.BaseGlyph for r in f["COLR"].table.BaseGlyphList.BaseGlyphPaintRecord}
check(colr == {"aq.wordmark", "aq.mark"}, "COLRv1 색 층: 워드마크·심볼")
for name in ("aq.wordmark", "aq.mark"):
    b = ink(f, name, 400)
    check(abs(b[3] - f["OS/2"].sCapHeight) < 120 and b[1] > -60, f"{name} 높이는 대문자 높이 ({b[1]:.0f}..{b[3]:.0f})")

# 고정 굵기 글꼴도 ss·cv 기능 이름을 갖고 있다.
for path in sorted(glob.glob(os.path.join(ROOT, "fonts", "static", "*.ttf")))[:1]:
    t = TTFont(path)
    missing = [r.FeatureTag for r in t["GSUB"].table.FeatureList.FeatureRecord
               if r.Feature.FeatureParams is not None and getattr(r.Feature.FeatureParams, "UINameID", None)
               and t["name"].getDebugName(r.Feature.FeatureParams.UINameID) is None]
    check(not missing, f"{os.path.basename(path)}: 기능 이름 빠짐 없음 {missing or ''}")

if fails:
    print(f"\n{len(fails)}개 실패")
    sys.exit(1)
print("\n모두 통과")
