"""어데닉 문장 디테일 — 어데닉 화면 문구(web/ 아래 한국어 문자열)에서 실제로 많이 쓰는 기호를 문맥에 맞게.

센 값(한국어 문자열 안, 2026-10 기준):
  ·  1,571번 — 한글·한글 붙여 씀 1,019(65%), 앞뒤 띄어 씀 316(20%), 영문·영문 113
  ‘’ 208번 — 거의 다 한글을 감쌈(‘다시 검사’)
  —  96번 — 모두 앞뒤를 띄어 씀(콘솔 — 관리자)
  …  79번 — 74번이 한글 바로 뒤(저장하는 중…)
  ℗ © 39번 — 발매 정보에서 나란히(℗ 2026 레이블 / © 2026 레이블)
  :  시각(14:30), -  코드(ISRC KR-A12-26, D-1 ~ D-11, 날짜 2026-09-30)

글자 모양은 문맥에서만 바뀐다. 영어 문장의 '·', '—', '…', 따옴표는 그대로다.
"""
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontTools.ttLib.tables.TupleVariation import TupleVariation

MASTER_TUPLES = ((-1.0, {"wght": (-1.0, -1.0, 0.0)}), (1.0, {"wght": (0.0, 1.0, 1.0)}))

SYMBOL_CENTER = 745  # build.SYMBOL_CENTER와 같은 높이(숫자·한글 가운데)
SPACED_DOT_WIDTH = 560  # 띄어 쓴 ' · '의 점 폭 — 양옆 띄어쓰기가 이미 여백이다
SPACED_DASH_SCALE = 0.75  # 띄어 쓴 ' — '는 1em 가까운 줄이 너무 길다(0.6은 하이픈처럼 보였다)
SPACED_DASH_SIDE = 40
QUOTE_RAISE = 140  # 한글을 감싸는 따옴표: 영문 대문자 높이(1448) → 한글 윗선(약 1630) 쪽으로
CASE_COLON_CENTER = 740  # 시각 14:30의 ':' — 숫자 가운데(약 742)
CASE_HYPHEN_CENTER = 735  # 코드 KR-A12-26의 '-' — 대문자(724)와 숫자(742) 사이
PHONOGRAM_SCALE = 1.318  # ℗를 ©와 같은 크기로(작은 ℗ 고리 1132 → © 고리 1492)


def _composite(font, name, parts, adv):
    """parts: [(glyph, dx, dy, (sx, sy) 또는 None)]"""
    glyf, hmtx, gvar = font["glyf"], font["hmtx"], font["gvar"]
    g = Glyph()
    g.numberOfContours = -1
    g.components = []
    for base, dx, dy, scale in parts:
        c = GlyphComponent()
        c.glyphName, c.x, c.y = base, round(dx), round(dy)
        c.flags = 0x0004  # ROUND_XY_TO_GRID
        if scale:
            c.transform = [[scale[0], 0], [0, scale[1]]]
        g.components.append(c)
    order = font.getGlyphOrder()
    glyf[name] = g
    if name not in order:
        order.append(name)
    g.recalcBounds(glyf)
    hmtx[name] = (round(adv), getattr(g, "xMin", 0))
    gvar.variations[name] = []  # 부품 위치는 굵기와 상관없이 같다(부품 모양은 굵기에 따라 바뀐다)
    font.setGlyphOrder(order)
    glyf.glyphOrder = order


def _bounds_at(font, name, n):
    """정규화 굵기 n(-1 · 0 · 1 = 마스터)에서 잉크 상자."""
    gs = font.getGlyphSet(location={"wght": n}, normalized=True)
    pen = BoundsPen(gs)
    gs[name].draw(pen)
    return pen.bounds


def center_y(font, name, target):
    """글리프의 세로 가운데를 모든 굵기에서 target으로. 원래 기호는 굵어질수록 위로 움직이기도 해서
    (Pretendard의 + 는 400 → 900에서 +21), 마스터마다 옮길 양을 따로 구해 굵기 차이값에 더한다."""
    from fontTools.varLib.iup import iup_delta
    glyf, gvar = font["glyf"], font["gvar"]
    g = glyf[name]
    dy = {}
    for n in (-1.0, 0.0, 1.0):
        b = _bounds_at(font, name, n)
        dy[n] = round(target - (b[1] + b[3]) / 2)
    if g.isComposite():
        coords, ends = None, None
    else:
        coords, ctrl = glyf._getCoordinatesAndControls(name, font["hmtx"].metrics, None)
        ends = ctrl.endPts
    for tv in gvar.variations.get(name, []):
        peak = tv.axes["wght"][1]
        extra = dy.get(peak, 0) - dy[0.0]
        if not extra:
            continue
        d = tv.coordinates
        if None in d and coords is not None:
            d = iup_delta(d, coords, ends)
        n_main = len(d) - 4
        tv.coordinates = [(round(x), round(y + extra)) if i < n_main else (round(x), round(y))
                          for i, (x, y) in enumerate((p if p is not None else (0, 0)) for p in d)]
    if g.isComposite():
        for c in g.components:
            c.y += dy[0.0]
    else:
        g.coordinates.translate((0, dy[0.0]))
        now, ctrl = glyf._getCoordinatesAndControls(name, font["hmtx"].metrics, None)
        for tv in gvar.variations.get(name, []):
            if None not in tv.coordinates:
                tv.optimize(now, ctrl.endPts, tolerance=0.5)
    g.recalcBounds(glyf)


def _follow(font, name, place):
    """부품 하나짜리 글리프의 부품 위치를 마스터마다 place(부품 잉크 상자) → (dx, dy)로 다시 잡는다."""
    g = font["glyf"][name]
    base = g.components[0].glyphName
    x0, y0 = place(_bounds_at(font, base, 0.0))
    g.components[0].x, g.components[0].y = round(x0), round(y0)
    font["gvar"].variations[name] = [
        TupleVariation(axes, [(round(place(_bounds_at(font, base, n))[0]) - round(x0),
                               round(place(_bounds_at(font, base, n))[1]) - round(y0)),
                              (0, 0), (0, 0), (0, 0), (0, 0)])
        for n, axes in MASTER_TUPLES
    ]
    g.recalcBounds(font["glyf"])


def _bounds(font, name):
    g = font["glyf"][name]
    g.recalcBounds(font["glyf"])
    return g.xMin, g.yMin, g.xMax, g.yMax


def decompose(font, name):
    """늘이거나 줄인 부품을 외곽선으로 풀어 둔다(일부 렌더러가 변환된 부품을 잘못 그린다 — fontbakery
    transformed-components). 세 마스터에서 각각 풀어 같은 점 구조의 굵기 차이값을 만든다."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    glyf, gvar = font["glyf"], font["gvar"]
    outlines = {}
    for n in (-1.0, 0.0, 1.0):
        gs = font.getGlyphSet(location={"wght": n}, normalized=True)
        rec = DecomposingRecordingPen(gs)
        gs[name].draw(rec)
        pen = TTGlyphPen(None)
        rec.replay(pen)
        outlines[n] = pen.glyph()
    adv = {n: font.getGlyphSet(location={"wght": n}, normalized=True)[name].width for n in outlines}
    base = outlines[0.0]
    base.recalcBounds(glyf)
    glyf[name] = base
    variations = []
    for n, axes in MASTER_TUPLES:
        o = outlines[n]
        assert len(o.coordinates) == len(base.coordinates), name
        pts = [(round(x1 - x0), round(y1 - y0)) for (x1, y1), (x0, y0) in zip(o.coordinates, base.coordinates)]
        pts += [(0, 0), (round(adv[n] - adv[0.0]), 0), (0, 0), (0, 0)]
        variations.append(TupleVariation(axes, pts))
    gvar.variations[name] = variations
    font["hmtx"][name] = (round(adv[0.0]), base.xMin)


def add_detail_glyphs(font):
    hmtx = font["hmtx"]
    # 숫자를 키운 만큼 ':'·'-'의 가운데도 올린다(.case는 대문자 가운데 724에 있었다)
    for name, center in (("colon.case", CASE_COLON_CENTER), ("hyphen.case", CASE_HYPHEN_CENTER)):
        center_y(font, name, center)
    # ' · ' — 점은 그대로, 폭만 좁게, 높이는 기호 가운데
    x0, y0, x1, y1 = _bounds(font, "period")
    _composite(font, "aq.periodcentered.spaced",
               [("period", (SPACED_DOT_WIDTH - (x1 - x0)) / 2 - x0, SYMBOL_CENTER - (y0 + y1) / 2, None)],
               SPACED_DOT_WIDTH)
    # 마침표는 굵어질수록 위로만 커진다 → 굵기마다 가운데를 다시 맞춘다
    _follow(font, "aq.periodcentered.spaced",
            lambda b: ((SPACED_DOT_WIDTH - (b[2] - b[0])) / 2 - b[0], SYMBOL_CENTER - (b[1] + b[3]) / 2))
    # ' — ' — 가로로 줄이고 한글 가운데 높이로
    x0, y0, x1, y1 = _bounds(font, "emdash")
    s = SPACED_DASH_SCALE
    _composite(font, "aq.emdash.spaced",
               [("emdash", SPACED_DASH_SIDE - x0 * s, SYMBOL_CENTER - (y0 + y1) / 2, (s, 1))],
               (x1 - x0) * s + 2 * SPACED_DASH_SIDE)
    _follow(font, "aq.emdash.spaced", lambda b: (SPACED_DASH_SIDE - b[0] * s, SYMBOL_CENTER - (b[1] + b[3]) / 2))
    # 한글을 감싸는 따옴표
    for q in ("quoteleft", "quoteright", "quotedblleft", "quotedblright"):
        _composite(font, f"aq.{q}.hang", [(q, 0, QUOTE_RAISE, None)], hmtx[q][0])
    # ℗를 ©와 같은 크기·같은 가운데로. 고리 굵기는 ©와 400 언저리에서 맞는다(작은 ℗는 고리가 얇게 그려져 있다).
    cx0, cy0, cx1, cy1 = _bounds(font, "copyright")
    px0, py0, px1, py1 = _bounds(font, "uni2117")
    k = PHONOGRAM_SCALE
    src = "aq.phonogram.small"
    font["glyf"][src] = font["glyf"]["uni2117"]
    font["gvar"].variations[src] = font["gvar"].variations.get("uni2117", [])
    hmtx[src] = hmtx["uni2117"]
    order = font.getGlyphOrder()
    if src not in order:
        order.append(src)
    font.setGlyphOrder(order)
    font["glyf"].glyphOrder = order
    dx = (cx0 + cx1) / 2 - (px0 + px1) / 2 * k
    dy = (cy0 + cy1) / 2 - (py0 + py1) / 2 * k
    _composite(font, "uni2117", [(src, dx, dy, (k, k))], hmtx["copyright"][0])
    for name in ("uni2117", "aq.emdash.spaced"):
        decompose(font, name)


HANGUL_PUNCT = ("period", "exclam", "ellipsis.hang")  # 한글 뒤에서 한글 사이 간격만큼으로 당길 문장부호
HANGUL_BRACKET_KERN_SHARE = 0.5  # 여는 괄호는 곡선이라 같은 셈의 절반만


def _hangul_kerns(font):
    """한글 뒤 문장부호 커닝 = (한글 사이 간격 중앙값) − (한글 오른쪽 여백 중앙값 + 부호 왼쪽 여백)."""
    import statistics
    cmap = font.getBestCmap()
    gs = font.getGlyphSet(location={"wght": 0.0}, normalized=True)
    ls, rs = [], []
    for u in range(0xAC00, 0xD7A4, 5):
        pen = BoundsPen(gs)
        gs[cmap[u]].draw(pen)
        ls.append(pen.bounds[0])
        rs.append(gs[cmap[u]].width - pen.bounds[2])
    gap, rsb = statistics.median(ls) + statistics.median(rs), statistics.median(rs)
    out = {}
    for name in HANGUL_PUNCT + ("parenleft", "bracketleft"):
        pen = BoundsPen(gs)
        gs[name].draw(pen)
        k = gap - (rsb + pen.bounds[0])
        if name.endswith("left"):
            k *= HANGUL_BRACKET_KERN_SHARE
        out[name] = min(0, round(k))
    return out


def detail_fea(font):
    cmap = font.getBestCmap()
    kerns = _hangul_kerns(font)
    kern_rules = "\n".join(f"    pos @AQ_HANGUL {g} {v};" for g, v in kerns.items() if v)
    hangul = " ".join(sorted({cmap[u] for u in range(0xAC00, 0xD7A4) if u in cmap}))
    allowed = {cmap[u] for u in (0x20, 0xA0, 0x3000, 0x28, 0x5B, 0x7B) if u in cmap}
    allowed |= {n for n in ("parenleft.case", "bracketleft.case", "braceleft.case") if n in font.getReverseGlyphMap()}
    not_sign = " ".join(n for n in font.getGlyphOrder() if n not in allowed and not n.startswith(".notdef"))
    return f"""
# 금액·비율 앞의 '-'(Intl.NumberFormat이 내는 U+002D)를 '−'(minus.case) 모양으로.
# 바꾸는 것은 앞이 비었거나(줄 처음) 띄어쓰기·여는 괄호일 때뿐이다('-22,000원', '환불 -3', '(-5%)').
# 그 밖에는 모두 그대로: ISRC KR-A12-26, 날짜 2026-10-23, 전화 010-1234, 가린 계좌 ***-**-5678, CSV ,-2
@AQ_HYPHEN = [hyphen hyphen.case];
@AQ_NOT_SIGN = [{not_sign}];
lookup AQ_MINUS {{
    # 앞선 calt가 숫자 앞 '-'를 hyphen.case로 이미 바꿔 두므로 둘 다 받는다.
    ignore sub @AQ_NOT_SIGN @AQ_HYPHEN' @AQ_FIG;
    sub @AQ_HYPHEN' @AQ_FIG by minus.case;  # U+2212를 직접 쓸 때와 같은 높이(숫자 가운데)
}} AQ_MINUS;

# 브라우저는 letter-spacing이 0이 아니면 calt를 끈다(어데닉 금액은 자간을 쓴다).
# rclt(필수 문맥 대체)는 꺼지지 않으므로 같은 룩업을 둘 다에 건다.
feature calt {{
    lookup AQ_MINUS;
}} calt;

feature rclt {{
    lookup AQ_MINUS;
}} rclt;

@AQ_HANGUL = [{hangul}];
@AQ_CODE = [@AQ_FIG A-Z];

lookup AQ_DETAILS {{
    # 시각 14:30 — 숫자 사이 ':'를 숫자 가운데로(Pretendard는 calt에서만 해 줘서 자간을 주면 내려앉았다)
    sub @AQ_FIG colon' @AQ_FIG by colon.case;
    # 코드 KR-A12-26, D-1, 2026-09-30 — 대문자·숫자 사이 '-'를 가운데로
    sub @AQ_CODE hyphen' @AQ_CODE by hyphen.case;
    # 띄어 쓴 ' · ', ' — '
    sub space periodcentered' space by aq.periodcentered.spaced;
    sub space [emdash emdash.case]' space by aq.emdash.spaced;  # 앞선 calt가 emdash.case로 바꿔 두기도 한다
    # 한글 뒤 말줄임표는 가운데로(저장하는 중…)
    sub @AQ_HANGUL ellipsis' by ellipsis.hang;
    # 한글을 감싸는 따옴표는 한글 높이로(‘다시 검사’)
    sub quoteleft' @AQ_HANGUL by aq.quoteleft.hang;
    sub quotedblleft' @AQ_HANGUL by aq.quotedblleft.hang;
    sub @AQ_HANGUL quoteright' by aq.quoteright.hang;
    sub @AQ_HANGUL quotedblright' by aq.quotedblright.hang;
}} AQ_DETAILS;

feature calt {{
    lookup AQ_DETAILS;
}} calt;

# 고정폭 숫자 열에서 부호도 숫자 폭으로 — 표에서 −22,000과 +3,000의 자리가 맞는다
lookup AQ_TNUM_SIGNS {{
    sub [minus minus.case] by aq.minus.tf;
    sub [plus plus.case] by aq.plus.tf;
}} AQ_TNUM_SIGNS;

feature tnum {{
    lookup AQ_TNUM_SIGNS;
}} tnum;

# 한글 뒤 '. ! …'와 여는 괄호: 영문 기준 여백이라 '주세요.'의 마침표가 떠 보였다.
# 한글 사이 간격만큼으로 당긴다(kern은 브라우저 기본으로 켜져 있다).
lookup AQ_HANGUL_KERN {{
{kern_rules}
}} AQ_HANGUL_KERN;

feature kern {{
    lookup AQ_HANGUL_KERN;
}} kern;

feature rclt {{
    lookup AQ_DETAILS;
}} rclt;
"""
