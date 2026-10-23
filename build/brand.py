"""어데닉 로고를 글리프로 — 워드마크(U+F8F0)와 A 심볼(U+F8F1).

외곽선은 어데닉 저장소의 원본 SVG를 그대로 옮겼다.
  워드마크: web/studio/app/public/static/AUDENIQ_Logo_Light.svg
  A 심볼:   web/studio/app/public/static/favicon.svg
색이 있는 부분(Q 꼬리 그라데이션, A 가로획 파랑)은 COLRv1 층으로 남기고, 나머지는 글자 색을 따른다.
COLRv1을 못 읽는 사파리는 COLRv0 층으로 본체는 글자 색, 꼬리·가로획은 파랑(한 색)으로 보인다.
"""
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.misc.transform import Transform
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent

WORDMARK_CP = 0xF8F0
MARK_CP = 0xF8F1

# AUDENIQ_Logo_Light.svg (viewBox 24 0 1060 182). 글자 기준선 y=168, 대문자 윗선 y=14.
WORDMARK_BODY = [
    "M40 168 H69 L107 62 L145 168 H175 L123 26 Q118 14 107 14 Q96 14 91 26 Z",  # A
    "M196 14 H224 V106 C224 131 236 143 259.5 143 C282.5 143 295 130 295 106 V14 H323 V106 "
    "C323 146 299 169 259.5 169 C220 169 196 145 196 106 Z",  # U
    "M349 14 H404 C450 14 483 43 483 91 C483 139 450 168 404 168 H349 V141 H404 "
    "C436 141 455 122 455 91 C455 60 436 40 404 40 H349 Z",  # D
    "M510 14 H625 V40 H510 Z",  # E 윗획(떨어져 있음)
    "M510 76 H614 V102 H539 V141 H625 V168 H510 Z",  # E 몸
    "M647 168 V14 H655 L759 109 V14 H787 V168 H779 L675 76 V168 Z",  # N
    "M809 14 H837 V168 H809 Z",  # I
    "M956 8 C1004 8 1041 45 1041 90 C1041 105 1037 118 1030 129 L1009 108 C1011 102 1013 96 1013 90 "
    "C1013 58 988 35 956 35 C924 35 900 59 900 90 C900 121 924 146 956 146 C961 146 965 146 969 145 "
    "L990 166 C980 171 968 173 956 173 C909 173 872 136 872 90 C872 45 909 8 956 8 Z",  # Q
]
WORDMARK_TAIL = ["M948 106 H991 L1057 172 H1014 Z"]  # Q 꼬리(그라데이션)
WORDMARK_BASE, WORDMARK_TOP = 168, 14
WORDMARK_LEFT, WORDMARK_RIGHT = 40, 1057
# 그라데이션: #35BAEF → #4286F4 → #791EFF, (955,102)에서 (1064,172)로
ACCENT_STOPS = [(0.0, "#35BAEF"), (0.5, "#4286F4"), (1.0, "#791EFF")]
ACCENT_FROM, ACCENT_TO = (955, 102), (1064, 172)

# favicon.svg (viewBox 0 0 64 64). A 바닥 y=52, 꼭대기 곡선 y≈5.
MARK_BODY = ["M7 52 25 10 Q31 0 37 10 L57 52 H45 L31 21 19 52 Z"]
MARK_BAR = ["M25 37 H39 L43 47 H21 Z"]
MARK_BAR_COLOR = "#3182F6"
MARK_BASE, MARK_TOP = 52, 5
MARK_LEFT, MARK_RIGHT = 7, 57

SIDE = 60  # 로고 양옆 여백(유닛)


def _hex(c):
    return tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)) + (1.0,)


def _glyph(paths, transform, glyf):
    """SVG 경로들 → TrueType 글리프. 윤곽마다 시계 방향(TrueType 바깥 방향)으로 맞춘다."""
    tt = TTGlyphPen(None)
    for d in paths:
        rec = RecordingPen()
        parse_path(d, TransformPen(rec, transform))
        area = AreaPen()
        rec.replay(area)
        out = Cu2QuPen(tt, max_err=1.0, reverse_direction=False)
        rec.replay(ReverseContourPen(out) if area.value > 0 else out)
    g = tt.glyph()
    g.recalcBounds(glyf)
    return g


def _transform(base, top, left, cap):
    s = cap / (base - top)
    # SVG는 y가 아래로 자란다 → 뒤집고, 기준선을 0에, 왼쪽 잉크를 SIDE에.
    return Transform().translate(SIDE, 0).scale(s, -s).translate(-left, -base), s


def add_logo_glyphs(font):
    """워드마크·A 심볼 글리프와 COLR/CPAL을 더하고, 새 글리프 이름을 돌려준다."""
    glyf, hmtx, gvar = font["glyf"], font["hmtx"], font["gvar"]
    cap = font["OS/2"].sCapHeight
    order = font.getGlyphOrder()

    def put(name, glyph, adv):
        glyf[name] = glyph
        if name not in order:
            order.append(name)
        hmtx[name] = (adv, getattr(glyph, "xMin", 0))
        gvar.variations[name] = []  # 로고는 굵기와 상관없이 같은 모양

    def composite(name, parts, adv):
        g = Glyph()
        g.numberOfContours = -1
        g.components = []
        for i, p in enumerate(parts):
            c = GlyphComponent()
            c.glyphName, c.x, c.y = p, 0, 0
            c.flags = 0x0004 | (0x0400 if i == 0 else 0)  # ROUND_XY_TO_GRID, OVERLAP_COMPOUND
            g.components.append(c)
        g.recalcBounds(glyf)
        put(name, g, adv)

    t, s = _transform(WORDMARK_BASE, WORDMARK_TOP, WORDMARK_LEFT, cap)
    wm_adv = round((WORDMARK_RIGHT - WORDMARK_LEFT) * s + 2 * SIDE)
    put("aq.wordmark.body", _glyph(WORDMARK_BODY, t, glyf), wm_adv)
    put("aq.wordmark.tail", _glyph(WORDMARK_TAIL, t, glyf), wm_adv)
    composite("aq.wordmark", ["aq.wordmark.body", "aq.wordmark.tail"], wm_adv)
    g0, g1 = t.transformPoint(ACCENT_FROM), t.transformPoint(ACCENT_TO)

    tm, sm = _transform(MARK_BASE, MARK_TOP, MARK_LEFT, cap)
    mk_adv = round((MARK_RIGHT - MARK_LEFT) * sm + 2 * SIDE)
    put("aq.mark.body", _glyph(MARK_BODY, tm, glyf), mk_adv)
    put("aq.mark.bar", _glyph(MARK_BAR, tm, glyf), mk_adv)
    composite("aq.mark", ["aq.mark.body", "aq.mark.bar"], mk_adv)

    font.setGlyphOrder(order)
    glyf.glyphOrder = order
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[WORDMARK_CP] = "aq.wordmark"
            table.cmap[MARK_CP] = "aq.mark"

    # 팔레트: 0–2 그라데이션, 3 심볼 파랑. 0xFFFF = 지금 글자 색.
    palette = [_hex(c) for _, c in ACCENT_STOPS] + [_hex(MARK_BAR_COLOR)]
    font["CPAL"] = buildCPAL([palette])
    fg = {"Format": ot.PaintFormat.PaintSolid, "PaletteIndex": 0xFFFF, "Alpha": 1.0}
    # 그라데이션 축과 수직인 점 p2: p0에서 (p1-p0)을 90도 돌린 방향
    dx, dy = g1[0] - g0[0], g1[1] - g0[1]
    gradient = {
        "Format": ot.PaintFormat.PaintLinearGradient,
        "ColorLine": {"ColorStop": [{"StopOffset": o, "PaletteIndex": i, "Alpha": 1.0}
                                    for i, (o, _) in enumerate(ACCENT_STOPS)]},
        "x0": round(g0[0]), "y0": round(g0[1]), "x1": round(g1[0]), "y1": round(g1[1]),
        "x2": round(g0[0] - dy), "y2": round(g0[1] + dx),
    }
    bar = {"Format": ot.PaintFormat.PaintSolid, "PaletteIndex": 3, "Alpha": 1.0}

    def layers(*pairs):
        return {"Format": ot.PaintFormat.PaintColrLayers,
                "Layers": [{"Format": ot.PaintFormat.PaintGlyph, "Glyph": g, "Paint": p} for g, p in pairs]}

    glyph_map = font.getReverseGlyphMap(rebuild=True)
    colr = buildCOLR({
        "aq.wordmark": layers(("aq.wordmark.body", fg), ("aq.wordmark.tail", gradient)),
        "aq.mark": layers(("aq.mark.body", fg), ("aq.mark.bar", bar)),
    }, version=1, glyphMap=glyph_map)
    # 사파리는 COLRv1(그라데이션)을 못 읽는다. 같은 글리프에 COLRv0 층(한 색)을 함께 넣으면
    # v1을 읽는 브라우저는 v1을, 사파리는 v0을 쓴다. 꼬리는 그라데이션 가운데 색(#4286F4).
    v0 = {
        "aq.wordmark": [("aq.wordmark.body", 0xFFFF), ("aq.wordmark.tail", 1)],
        "aq.mark": [("aq.mark.body", 0xFFFF), ("aq.mark.bar", 3)],
    }
    t = colr.table
    bases, lays = [], []
    for base in sorted(v0, key=glyph_map.get):  # 글리프 번호 순
        rec = ot.BaseGlyphRecord()
        rec.BaseGlyph, rec.FirstLayerIndex, rec.NumLayers = base, len(lays), len(v0[base])
        bases.append(rec)
        for glyph, index in v0[base]:
            lay = ot.LayerRecord()
            lay.LayerGlyph, lay.PaletteIndex = glyph, index
            lays.append(lay)
    t.BaseGlyphRecordArray = ot.BaseGlyphRecordArray()
    t.BaseGlyphRecordArray.BaseGlyphRecord = bases
    t.LayerRecordArray = ot.LayerRecordArray()
    t.LayerRecordArray.LayerRecord = lays
    t.BaseGlyphRecordCount, t.LayerRecordCount = len(bases), len(lays)
    font["COLR"] = colr
    return ["aq.wordmark", "aq.mark"]
