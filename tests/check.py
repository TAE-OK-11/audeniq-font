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
# 값은 build/build.py의 상수 하나에서 온다(DESIGN.md 표와 같은 값).
sys.path.insert(0, os.path.join(ROOT, "build"))
import build as B  # noqa: E402

W = B.WEIGHT_MAP
d, lo, hi = W[400], W[45], W[930]


def orig_weight(user):
    """CSS 굵기 → Pretendard 굵기(WEIGHT_MAP 사이는 직선)."""
    pts = sorted(W.items())
    for (u0, o0), (u1, o1) in zip(pts, pts[1:]):
        if u0 <= user <= u1:
            return o0 + (o1 - o0) * (user - u0) / (u1 - u0)


# 굵기: CSS 굵기 → Pretendard 굵기. 양 끝은 그대로.
for user in (100, 400, 700, 930):
    a, b = ink(f, "l", user), ink(src, "l", orig_weight(user))
    check(abs((a[2] - a[0]) - (b[2] - b[0])) <= 2, f"굵기 {user} = Pretendard {orig_weight(user):.0f} ('l' 획 {a[2]-a[0]:.0f} / {b[2]-b[0]:.0f})")

# 한글: 양쪽 20씩 좁히고 HANGUL_RAISE만큼 위로.
for user in (100, 400, 900):
    a, b = ink(f, "uniAC00", user), ink(src, "uniAC00", orig_weight(user))
    check(abs(b[0] - a[0] - 20) <= 1 and abs(b[2] - a[2] - 20) <= 1, f"'가' 굵기 {user}: 잉크가 20 왼쪽으로(양쪽 20씩)")
    check(abs(a[1] - b[1] - B.HANGUL_RAISE) <= 1, f"'가' 굵기 {user}: {B.HANGUL_RAISE} 위로")

# 숫자: FIGURE_SCALE배, 옆 여백은 FIGURE_TIGHTEN만큼 덜어 낸다. 기호(% ₩)는 키우기만.
gsA = f.getGlyphSet(location={"wght": 400}, normalized=False)
gsP = src.getGlyphSet(location={"wght": d}, normalized=False)
s_fig = B.FIGURE_SCALE
for ch in "0148":
    top = ink(f, cmap[ord(ch)], 400)[3]
    src_top = ink(src, cmap[ord(ch)], d)[3]
    check(abs(top - src_top * s_fig) <= 3, f"'{ch}' 높이 {top:.0f} (Pretendard {src_top:.0f} × {s_fig})")
    w_new, w_old = gsA[cmap[ord(ch)]].width, gsP[cmap[ord(ch)]].width
    check(abs(w_new - (w_old * s_fig - B.FIGURE_TIGHTEN)) <= 3, f"'{ch}' 폭 {w_new} (Pretendard {w_old} × {s_fig} − {B.FIGURE_TIGHTEN})")
check(abs(ink(f, cmap[ord("%")], 400)[3] - ink(src, cmap[ord("%")], d)[3] * s_fig) <= 3, "'%'도 같이 커짐")
check(abs(ink(f, "H", 400)[3] - 1448) <= 1, "대문자 높이는 그대로 1448")

# 6·8·9·5는 가볍게: 같은 숫자의 원본보다 잉크가 적고, 폭은 굵기마다 원본과 같은 비율.
from fontTools.pens.areaPen import AreaPen  # noqa: E402


def area(font, name, wght):
    gs = font.getGlyphSet(location={"wght": wght}, normalized=False)
    pen = AreaPen(gs)
    gs[name].draw(pen)
    return abs(pen.value)


for name in ("six", "eight", "nine"):
    ratio = area(f, name, 400) / (area(src, name, d) * s_fig * s_fig)
    check(0.95 < ratio < 0.99, f"'{name}' 잉크 {ratio:.3f}배(가볍게)")
zero_ratio = area(f, "zero", 400) / (area(src, "zero", d) * s_fig * s_fig)
check(abs(zero_ratio - 1) < 0.005, f"'zero'는 그대로 ({zero_ratio:.3f})")
for user in (100, 400, 700, 900):
    gsU = f.getGlyphSet(location={"wght": user}, normalized=False)
    gsO = src.getGlyphSet(location={"wght": orig_weight(user)}, normalized=False)
    want = gsO["eight"].width * s_fig - B.FIGURE_TIGHTEN
    check(abs(gsU["eight"].width - want) <= 4, f"'8' 폭 굵기 {user}: {gsU['eight'].width} ≈ {want:.0f}")

# 띄어쓰기·가운뎃점.
check(all(f.getGlyphSet(location={"wght": w}, normalized=False)[cmap[0x20]].width == B.SPACE_WIDTH for w in (100, 400, 900)),
      f"띄어쓰기 {B.SPACE_WIDTH}, 모든 굵기")
dot = ink(f, cmap[0xB7], 400)
check(gsA[cmap[0xB7]].width == B.MIDDLE_DOT_WIDTH and abs((dot[1] + dot[3]) / 2 - B.MIDDLE_DOT_CENTER) <= 2,
      f"가운뎃점 폭 {B.MIDDLE_DOT_WIDTH}, 높이 가운데 {(dot[1]+dot[3])/2:.0f}")
check(cmap.get(0x2027) == cmap[0xB7] and cmap.get(0x30FB) == cmap[0xB7], "U+2027·U+30FB도 같은 가운뎃점")

# 기호: 숫자·한글 가운데로, calt가 꺼져도(letter-spacing) 같은 높이.
for name in ("plus", "minus", "equal", "arrowright", "plus.case", "minus.case"):
    b = ink(f, name, 400)
    check(abs((b[1] + b[3]) / 2 - B.SYMBOL_CENTER) <= 2, f"'{name}' 가운데 {(b[1]+b[3])/2:.0f}")
for text in ("+3", "1 + 2", "→ 다음"):
    glyphs, _ = shape(VAR, text, {"calt": False})
    sym = [g for g in glyphs if g.startswith(("plus", "arrowright"))][0]
    b = ink(f, sym, 400)
    check(abs((b[1] + b[3]) / 2 - B.SYMBOL_CENTER) <= 2, f"calt 없이 '{text}'의 기호도 가운데")
b, b0 = ink(f, "parenleft", 400), ink(src, "parenleft", d)
check(abs(b[1] - b0[1] - B.BRACKET_RAISE) <= 1, f"괄호 {B.BRACKET_RAISE} 위로")

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
