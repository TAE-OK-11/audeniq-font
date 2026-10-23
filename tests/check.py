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

# 한글 자간: 완성형 11,172자 — 폭 중앙값은 원본보다 40 좁고(−0.02em), 좌우 여백의 들쭉날쭉함은 HANGUL_OPTICAL만큼 줄었다.
import statistics  # noqa: E402

_sp = src.getBestCmap()
hangul = range(0xAC00, 0xD7A4)
widths = [f["hmtx"][cmap[u]][0] for u in hangul]
check(abs(statistics.median(widths) - (src["hmtx"][_sp[0xAC00]][0] - 40)) <= 10, f"한글 폭 중앙값 {statistics.median(widths)} (원본 1770 − 40 언저리)")


def gaps(font, cm):
    gs = font.getGlyphSet(location={"wght": 0.0}, normalized=True)
    out = []
    for u in range(0xAC00, 0xD7A4, 7):  # 1,596자 표본
        pen = BoundsPen(gs)
        gs[cm[u]].draw(pen)
        out.append(pen.bounds[0] + gs[cm[u]].width - pen.bounds[2])
    return out


g_new, g_old = gaps(f, cmap), gaps(src, _sp)
ratio = statistics.pstdev(g_new) / statistics.pstdev(g_old)
check(abs(ratio - 0.7) < 0.05, f"한글 좌우 여백 흩어짐 {ratio:.2f}배(광학 자간 0.3)")
gn = {}
for c in "니사":
    gs = f.getGlyphSet(location={"wght": 0.0}, normalized=True)
    pen = BoundsPen(gs)
    gs[cmap[ord(c)]].draw(pen)
    gn[c] = pen.bounds[0] + gs[cmap[ord(c)]].width - pen.bounds[2]
check(gn["니"] - gn["사"] < 260, f"'니'와 '사'의 여백 차이 {gn['니'] - gn['사']:.0f} (원본 약 350)")

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
check(abs(gsA[cmap[0xB7]].width - B.MIDDLE_DOT_WIDTH) <= 3 and abs((dot[1] + dot[3]) / 2 - B.MIDDLE_DOT_CENTER) <= 2,
      f"가운뎃점 폭 {B.MIDDLE_DOT_WIDTH}, 높이 가운데 {(dot[1]+dot[3])/2:.0f}")
check(cmap.get(0x2027) == cmap[0xB7], "U+2027도 같은 가운뎃점")
check(cmap.get(0x30FB) == src.getBestCmap()[0x30FB], "일본어 전각 ・(U+30FB)은 원래 전각 글리프")

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
    "***-**-5678": None, "USD,-2,-1.25": None, "1 / -1": "minus", "환불 -3,000원": "minus",
}
for text, want in cases.items():
    glyphs, _ = shape(VAR, text)
    has = "minus.case" in glyphs
    check(has == (want == "minus"), f"'{text}' → {'−' if has else '-'}")
glyphs, _ = shape(VAR, "-1,200", {"tnum": True})
check(glyphs[0] in ("minus.case", "aq.minus.tf"), "고정폭 숫자에서도 '-1,200' → '−'")
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

# 어데닉 문장 디테일: 실제 어데닉 문구의 문맥에서만 바뀐다(calt를 꺼도 같음).
import details as D  # noqa: E402

for text, want, absent in (
    ("계약 · 연동", "aq.periodcentered.spaced", None), ("심사·문의", "periodcentered", "aq.periodcentered.spaced"),
    ("콘솔 — 관리자", "aq.emdash.spaced", None), ("a—b", "emdash", "aq.emdash.spaced"),
    ("저장하는 중…", "ellipsis.hang", None), ("wait…", "ellipsis", "ellipsis.hang"),
    ("‘다시 검사’", "aq.quoteleft.hang", None), ("‘다시 검사’", "aq.quoteright.hang", None),
    ("“회사”", "aq.quotedblright.hang", None), ("don’t", "quoteright", "aq.quoteright.hang"),
    ("14:30", "colon.case", None), ("KR-A12-26-00001", "hyphen.case", None), ("D-1", "hyphen.case", None),
):
    for feats in ({}, {"calt": False}):
        glyphs, _ = shape(VAR, text, feats)
        ok = want in glyphs and (absent is None or absent not in glyphs)
        check(ok, f"'{text}'{' (calt 꺼짐)' if feats else ''} → {want}")
for user in (100, 400, 700, 900):
    dot = ink(f, "aq.periodcentered.spaced", user)
    gsU = f.getGlyphSet(location={"wght": user}, normalized=False)
    check(gsU["aq.periodcentered.spaced"].width == D.SPACED_DOT_WIDTH and abs((dot[1] + dot[3]) / 2 - D.SYMBOL_CENTER) <= 2
          and abs(dot[0] - (D.SPACED_DOT_WIDTH - dot[2])) <= 4, f"' · ' 굵기 {user}: 점 가운데 {(dot[1]+dot[3])/2:.0f}")
    dash = ink(f, "aq.emdash.spaced", user)
    check(abs((dash[1] + dash[3]) / 2 - D.SYMBOL_CENTER) <= 2, f"' — ' 굵기 {user}: 가운데 {(dash[1]+dash[3])/2:.0f}")
dash, full = ink(f, "aq.emdash.spaced", 400), ink(f, "emdash", 400)
check(abs((dash[2] - dash[0]) - (full[2] - full[0]) * D.SPACED_DASH_SCALE) <= 2, f"' — ' 길이 ×{D.SPACED_DASH_SCALE}")
q, q0 = ink(f, "aq.quoteleft.hang", 400), ink(f, "quoteleft", 400)
check(round(q[1] - q0[1]) == D.QUOTE_RAISE, f"한글 따옴표 +{D.QUOTE_RAISE}")
for w in (400, 700):
    p, c = ink(f, "uni2117", w), ink(f, "copyright", w)
    check(abs((p[3] - p[1]) - (c[3] - c[1])) <= 6 and abs((p[1] + p[3]) / 2 - (c[1] + c[3]) / 2) <= 3,
          f"℗와 ©가 같은 크기·높이 (굵기 {w}: {p[3]-p[1]:.0f} / {c[3]-c[1]:.0f})")

# 고정폭 숫자 열의 부호: 숫자와 같은 폭(모든 굵기).
for user in (100, 400, 700, 900):
    fnt = hb.Font(hb.Face(hb.Blob.from_file_path(VAR)))
    fnt.set_variations({"wght": user})
    for text in ("-22,000", "+3,000", "−5"):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(fnt, buf, {"tnum": True})
        w_sign, w_fig = buf.glyph_positions[0].x_advance, buf.glyph_positions[1].x_advance
        check(w_sign == w_fig, f"tnum '{text}' 굵기 {user}: 부호 폭 {w_sign} = 숫자 폭 {w_fig}")
# 시각 ':'·코드 '-'의 높이
for name, center in (("colon.case", D.CASE_COLON_CENTER), ("hyphen.case", D.CASE_HYPHEN_CENTER)):
    bb = ink(f, name, 400)
    check(abs((bb[1] + bb[3]) / 2 - center) <= 2, f"{name} 가운데 {(bb[1]+bb[3])/2:.0f}")
# 파일 크기: 굵기 마스터를 늘리지 않는다(0.3–0.5는 기본 모양을 옮겨 gvar가 4.8MB였다).
check(TTFont(VAR).reader.tables["gvar"].length < 3_700_000, "gvar 3.7MB 아래(마스터 45·400·930 그대로)")
check(all(len(v) <= 2 for v in f["gvar"].variations.values()), "모든 글리프의 굵기 차이값이 2개 이하")
# 사파리용 COLRv0 층
colr = f["COLR"].table
check(colr.BaseGlyphRecordCount == 2 and {r.BaseGlyph for r in colr.BaseGlyphRecordArray.BaseGlyphRecord} == {"aq.wordmark", "aq.mark"},
      "COLRv0 층(사파리): 워드마크·심볼")

# 한글 뒤 문장부호 커닝: '요.'의 '요'는 '요요'의 '요'보다 좁게 놓이고, 영문 'a.'는 그대로.
def adv0(text, feats=None):
    fnt = hb.Font(hb.Face(hb.Blob.from_file_path(VAR)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(fnt, buf, feats or {})
    return buf.glyph_positions[0].x_advance


for punct in (".", "!", "(", "…"):
    k = adv0("요" + punct) - adv0("요요")
    check(-100 < k < -50, f"'요{punct}' 커닝 {k}")
check(adv0("a.") == adv0("aa"), "영문 'a.'은 커닝 없음")
check(adv0("요.", {"kern": False}) == adv0("요요"), "kern을 끄면 커닝 없음")

# 기능 목록: 태그 이름순(OTS), 굵기별로 바꿔 끼우는 표(FeatureVariations)가 원본과 같은 기능을 가리킨다.
for tag in ("GSUB", "GPOS"):
    tags = [r.FeatureTag for r in f[tag].table.FeatureList.FeatureRecord]
    check(tags == sorted(tags), f"{tag} 기능 목록 이름순")


def fv_targets(font):
    t = font["GSUB"].table
    recs = t.FeatureList.FeatureRecord
    fv = getattr(t, "FeatureVariations", None)
    return sorted(recs[s.FeatureIndex].FeatureTag for r in fv.FeatureVariationRecord
                  for s in r.FeatureTableSubstitution.SubstitutionRecord) if fv else []


check(fv_targets(f) == fv_targets(src), f"굵기별 기능 바꿔 끼우기 대상 {fv_targets(f)} = 원본 {fv_targets(src)}")

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
