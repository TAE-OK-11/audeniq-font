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


def add_detail_glyphs(font):
    hmtx = font["hmtx"]
    # 숫자를 키운 만큼 ':'·'-'의 가운데도 올린다(.case는 대문자 가운데 724에 있었다)
    for name, center in (("colon.case", CASE_COLON_CENTER), ("hyphen.case", CASE_HYPHEN_CENTER)):
        g = font["glyf"][name]
        x0, y0, x1, y1 = _bounds(font, name)
        dy = round(center - (y0 + y1) / 2)
        if g.isComposite():
            for c in g.components:
                c.y += dy
        else:
            g.coordinates.translate((0, dy))
        g.recalcBounds(font["glyf"])
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
    return f"""
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
