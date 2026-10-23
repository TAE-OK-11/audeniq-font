"""Audeniq Sans 빌드 — Pretendard Variable 1.3.9를 받아 어데닉 규칙대로 고친다.

    python3 build/build.py            # sources/ 에 원본이 없으면 npm에서 받아 검증
    python3 build/build.py --check    # 빌드 뒤 tests/check.py까지
    python3 build/build.py --variable-only   # 고정 굵기(약 5분)는 건너뛰고 가변 글꼴만

바꾸는 것은 DESIGN.md의 '바꾼 것' 표와 한 줄씩 맞는다. 숫자(유닛)는 2048 UPM 기준.
"""
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import urllib.request

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib.iup import iup_delta
from fontTools.varLib.models import supportScalar
from fontTools.varLib import instancer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brand  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "sources")
OUT = os.path.join(ROOT, "fonts")

PRETENDARD_VERSION = "1.3.9"
PRETENDARD_TGZ = f"https://registry.npmjs.org/pretendard/-/pretendard-{PRETENDARD_VERSION}.tgz"
PRETENDARD_SHA1 = "b1f86d5a7a729f518974098fcf85f34fff3526b7"  # npm dist.shasum
PRETENDARD_MEMBER = "package/dist/public/variable/PretendardVariable.ttf"
SUBSET_MEMBER = "package/subset_glyphs.txt"

VERSION = "0.4.0"
FAMILY = "Audeniq Sans"
VENDOR = "AUDQ"

# 한글 자간: 어데닉 화면은 한글 본문에 letter-spacing -0.02em을 기본으로 써 왔다.
# 그 값을 글꼴 안에 넣어 letter-spacing 0이 어데닉 본문 자간이 되게 한다. 양쪽에서 반씩.
HANGUL_TIGHTEN = 40  # 유닛, 2048의 약 0.0195em
HANGUL_RANGES = [
    (0x1100, 0x11FF),  # 한글 자모
    (0x3131, 0x318E),  # 호환용 자모
    (0xA960, 0xA97F),  # 자모 확장 A
    (0xAC00, 0xD7A3),  # 완성형 11,172자
    (0xD7B0, 0xD7FF),  # 자모 확장 B
]

# 토스 제작기의 원칙(균형·맥락·형태)을 어데닉 화면에서 보고 정한 값. 토스 수치를 그대로 쓰지는 않는다.
# 2048 UPM. 괄호 안은 (Pretendard → 토스) 잰 값.
# 균형: 숫자를 조금 크게 — 금액이 문장보다 먼저 읽히게. (1468 → 1522)
FIGURE_SCALE = 1.025
FIGURE_EXTRA = "%₩$€¥£"  # 숫자와 같이 커지는 기호
FIGURE_FEATURES = {"tnum", "pnum", "zero", "cv01", "cv02", "cv03", "cv04", "cv09", "cv13",
                   "ss01", "ss02", "ss06", "ss08"}  # 이 기능들이 부르는 숫자 대체 글리프도 함께
FIGURE_TIGHTEN = 20  # 커진 만큼 숫자 옆 여백을 양쪽 10씩 덜어 금액이 흩어지지 않게. (여백 104 → 94)
# 형태: 6·8·9·5는 같은 굵기여도 0·2·3보다 진해 보인다(잉크 밀도 0.42–0.44 vs 0.36–0.38). 그만큼 가볍게.
FIGURE_LIGHTEN = {"eight": 16, "six": 12, "nine": 12, "five": 6, "uniE06F": 12, "uniE070": 12}
# 균형: 띄어쓰기. 한글 자간을 좁힌 만큼 띄어쓰기도 조금 좁게. (514 → 414)
SPACE_WIDTH = 460
# 균형: 한글을 영문 기준선보다 조금 위로(SD 고딕 Neo). 줄 상자도 같이 올려 한글이 줄 가운데.
HANGUL_RAISE = 16
# 굵기: Pretendard보다 조금 가볍고 시원하게. CSS 굵기 → Pretendard 굵기. 양 끝(45, 930)은 그대로.
# (토스 Regular ≈ Pretendard 380, 토스 Bold ≈ 610)
WEIGHT_MAP = {45: 45, 100: 100, 400: 390, 700: 650, 930: 930}
# 맥락: 가운뎃점은 마침표와 헷갈리지 않게 넓게, 한글 가운데 높이로. (폭 520 → 1031, 높이 633 → 735)
MIDDLE_DOT_WIDTH = 800
MIDDLE_DOT_CENTER = 745
MIDDLE_DOT_ALIASES = (0x2027, 0x30FB)  # 같은 모양으로 맞출 다른 가운뎃점(중앙점 통일)
# 균형·맥락: + − × ÷ = < > ± ~ 와 화살표를 소문자 가운데(567)에서 숫자·한글 가운데로.
SYMBOL_CENTER = 745
SYMBOLS = ["plus", "minus", "multiply", "divide", "equal", "less", "greater", "plusminus", "asciitilde",
           "arrowright", "arrowleft", "plus.case", "minus.case", "multiply.case", "divide.case", "equal.case",
           "less.case", "greater.case", "plusminus.case", "asciitilde.case", "arrowright.case", "arrowleft.case"]
SYMBOL_SPACE = 30  # 맥락: 기호 양옆 여백을 조금 더 — 아이콘처럼 한눈에
# 균형: 괄호를 한글 높이에 맞게 올린다. 기본 괄호는 영문 내림선까지 내려가 '(선택)'에서 처져 보였다.
BRACKETS = ["parenleft", "parenright", "bracketleft", "bracketright", "braceleft", "braceright"]
BRACKET_RAISE = 110

# 굵기 축 이름(STAT/fvar)
WEIGHTS = [
    (100, "Thin"), (200, "ExtraLight"), (300, "Light"), (400, "Regular"), (500, "Medium"),
    (600, "SemiBold"), (700, "Bold"), (800, "ExtraBold"), (900, "Black"),
]


def fetch_sources():
    os.makedirs(SRC_DIR, exist_ok=True)
    var_path = os.path.join(SRC_DIR, "PretendardVariable.ttf")
    subset_path = os.path.join(SRC_DIR, "subset_glyphs.txt")
    if os.path.exists(var_path) and os.path.exists(subset_path):
        return var_path, subset_path
    print(f"Pretendard {PRETENDARD_VERSION} 받는 중: {PRETENDARD_TGZ}")
    data = urllib.request.urlopen(PRETENDARD_TGZ).read()
    digest = hashlib.sha1(data).hexdigest()
    if digest != PRETENDARD_SHA1:
        sys.exit(f"원본 해시가 다릅니다: {digest} != {PRETENDARD_SHA1}")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member, path in ((PRETENDARD_MEMBER, var_path), (SUBSET_MEMBER, subset_path)):
            with open(path, "wb") as fh:
                fh.write(tar.extractfile(member).read())
    return var_path, subset_path


# ---------------------------------------------------------------- 1. 한글 자간

def tighten_hangul(font):
    cmap = font.getBestCmap()
    glyf, hmtx = font["glyf"], font["hmtx"]
    half = HANGUL_TIGHTEN // 2
    done, changed = set(), 0
    for lo, hi in HANGUL_RANGES:
        for u in range(lo, hi + 1):
            name = cmap.get(u)
            if not name or name in done:
                continue
            done.add(name)
            g = glyf[name]
            adv, _ = hmtx[name]
            if adv == 0:  # 결합용 자모(폭 0)는 그대로
                continue
            if g.isComposite():
                for c in g.components:
                    c.x -= half
            elif g.numberOfContours > 0:
                g.coordinates.translate((-half, 0))
            g.recalcBounds(glyf)
            # gvar의 위치 차이값은 상대값이라 그대로 두면 모든 굵기에 같은 만큼 적용된다.
            hmtx[name] = (adv - HANGUL_TIGHTEN, g.xMin if hasattr(g, "xMin") else 0)
            changed += 1
    return changed


# ---------------------------------------------------------------- 2. 토스·SD 고딕 Neo 비율

def _figure_glyphs(font, extra=FIGURE_EXTRA):
    """숫자 0–9, 숫자 옆 기호, 그리고 숫자 기능(FIGURE_FEATURES)이 바꿔 넣는 대체 글리프 전부."""
    cmap = font.getBestCmap()
    names = {cmap[ord(c)] for c in "0123456789" + extra}
    gsub = font["GSUB"].table
    lookups = {i for r in gsub.FeatureList.FeatureRecord if r.FeatureTag in FIGURE_FEATURES
               for i in r.Feature.LookupListIndex}
    grew = True
    while grew:
        grew = False
        for i in lookups:
            for st in gsub.LookupList.Lookup[i].SubTable:
                st = getattr(st, "ExtSubTable", st)
                for k, v in (getattr(st, "mapping", None) or {}).items():
                    if k in names and v not in names:
                        names.add(v)
                        grew = True
    return names


def scale_figures(font):
    """숫자를 토스처럼 크게. 원점 기준으로 외곽선·굵기 차이값·폭을 모두 FIGURE_SCALE배.
    부품 글리프는 부품 위치를 늘리고, 이 묶음 밖의 부품(사선 0의 빗금 등)은 부품 변환으로 함께 키운다."""
    s = FIGURE_SCALE
    glyf, gvar, hmtx = font["glyf"], font["gvar"], font["hmtx"]
    names = _figure_glyphs(font)
    for n in sorted(names):
        g = glyf[n]
        if g.isComposite():
            for c in g.components:
                c.x, c.y = round(c.x * s), round(c.y * s)
                if c.glyphName not in names:
                    t = getattr(c, "transform", [[1, 0], [0, 1]])
                    c.transform = [[t[0][0] * s, t[0][1] * s], [t[1][0] * s, t[1][1] * s]]
        elif g.numberOfContours > 0:
            g.coordinates.scale((s, s))
            g.coordinates.toInt()
        for tv in gvar.variations.get(n, []):
            tv.coordinates = [None if p is None else (round(p[0] * s), round(p[1] * s)) for p in tv.coordinates]
        g.recalcBounds(glyf)
        adv, _ = hmtx[n]
        hmtx[n] = (round(adv * s), getattr(g, "xMin", 0))
    # 숫자(기호 빼고)는 옆 여백을 줄인다. 부품 숫자(고정폭 등)는 바탕 숫자가 이미 옮겨져 있어 폭만 줄인다.
    half = FIGURE_TIGHTEN // 2
    for n in sorted(_figure_glyphs(font, extra="")):
        g = glyf[n]
        if not g.isComposite() and g.numberOfContours > 0:
            g.coordinates.translate((-half, 0))
        elif g.isComposite() and not any(c.glyphName in names for c in g.components):
            for c in g.components:
                c.x -= half
        g.recalcBounds(glyf)
        adv, _ = hmtx[n]
        hmtx[n] = (adv - FIGURE_TIGHTEN, getattr(g, "xMin", 0))
    return len(names)


def narrow_space(font):
    cmap = font.getBestCmap()
    for u in (0x20, 0xA0):
        n = cmap[u]
        font["hmtx"][n] = (SPACE_WIDTH, 0)
        for tv in font["gvar"].variations.get(n, []):  # 폭은 굵기와 상관없이 같게
            tv.coordinates = [None if p is None else (0, 0) for p in tv.coordinates]


def remap_weight(font):
    """기본 마스터를 Pretendard 380 모양으로 옮기고, avar로 CSS 굵기 → Pretendard 굵기를 WEIGHT_MAP대로 잇는다."""
    lo, hi = WEIGHT_MAP[45], WEIGHT_MAP[930]
    default = WEIGHT_MAP[400]
    font = instancer.instantiateVariableFont(font, {"wght": (lo, default, hi)})
    axis = font["fvar"].axes[0]
    axis.minValue, axis.defaultValue, axis.maxValue = 45, 400, 930

    def user(u):
        return (u - 400) / (400 - 45) if u < 400 else (u - 400) / (930 - 400)

    def inner(o):
        return (o - default) / (default - lo) if o < default else (o - default) / (hi - default)

    avar = newTable("avar")
    avar.segments = {"wght": {round(user(u), 4): round(inner(o), 4) for u, o in sorted(WEIGHT_MAP.items())}}
    font["avar"] = avar
    return font


def wide_middle_dot(font):
    """가운뎃점(·)을 넓은 폭, 한글 가운데 높이로. 다른 가운뎃점 코드도 같은 글리프로."""
    glyf, hmtx, cmap = font["glyf"], font["hmtx"], font.getBestCmap()
    n = cmap[0xB7]
    g = glyf[n]
    adv, _ = hmtx[n]
    dy = MIDDLE_DOT_CENTER - (g.yMin + g.yMax) / 2
    dx = (MIDDLE_DOT_WIDTH - adv) / 2
    if g.isComposite():  # periodcentered = period 부품
        for c in g.components:
            c.x, c.y = c.x + round(dx), c.y + round(dy)
    else:
        g.coordinates.translate((round(dx), round(dy)))
    g.recalcBounds(glyf)
    hmtx[n] = (MIDDLE_DOT_WIDTH, g.xMin)  # 폭 차이값(위상 점)은 그대로 — 굵을수록 조금 넓어진다
    for table in font["cmap"].tables:
        if table.isUnicode():
            for u in MIDDLE_DOT_ALIASES:
                table.cmap[u] = n


def _internal_norm(font, o):
    """remap_weight 뒤 내부 굵기 o(Pretendard 굵기)의 정규화 좌표."""
    lo, d, hi = WEIGHT_MAP[45], WEIGHT_MAP[400], WEIGHT_MAP[930]
    return {"wght": (o - d) / (d - lo) if o < d else (o - d) / (hi - d)}


def _coords_at(font, name, loc):
    """정규화 위치 loc에서 글리프 점 좌표(위상 점 4개 포함)."""
    glyf, gvar = font["glyf"], font["gvar"]
    coords, ctrl = glyf._getCoordinatesAndControls(name, font["hmtx"].metrics, None)
    out = GlyphCoordinates(coords)
    for tv in gvar.variations.get(name, []):
        scalar = supportScalar(loc, tv.axes)
        if not scalar:
            continue
        deltas = tv.coordinates
        if None in deltas:
            deltas = iup_delta(deltas, coords, ctrl.endPts)
        out += GlyphCoordinates(deltas) * scalar
    out.toInt()
    return out


def lighten_figures(font):
    """FIGURE_LIGHTEN: 진해 보이는 숫자의 외곽선을 같은 숫자의 조금 가는 굵기 모양으로 바꾼다.
    가장 가는 끝(45)은 더 가늘게 할 수 없어 그대로, 나머지 마스터는 k만큼 가는 위치의 모양."""
    glyf, gvar, hmtx = font["glyf"], font["gvar"], font["hmtx"]
    lo, d, hi = WEIGHT_MAP[45], WEIGHT_MAP[400], WEIGHT_MAP[930]
    for n, k in FIGURE_LIGHTEN.items():
        g = glyf[n]
        if g.isComposite() or g.numberOfContours <= 0:
            continue
        masters = ((lo, lo), (d, d - k), (hi, hi - k))
        shaped = {}
        for w, o in masters:
            orig = _coords_at(font, n, _internal_norm(font, w))
            new = _coords_at(font, n, _internal_norm(font, o))
            n_pts = len(orig) - 4
            # 그 굵기의 원래 폭은 지키고, 가늘어진 잉크를 폭 가운데로
            gap = ((orig[n_pts + 1][0] - orig[n_pts][0]) - (new[n_pts + 1][0] - new[n_pts][0])) // 2
            pts = [(x + gap, y) for x, y in new[:n_pts]] + list(orig[n_pts:])
            shaped[w] = GlyphCoordinates(pts)
        base = shaped[d]
        gvar.variations[n] = [
            TupleVariation(axes, [tuple(p) for p in (shaped[w] - base)])
            for w, axes in ((lo, {"wght": (-1.0, -1.0, 0.0)}), (hi, {"wght": (0.0, 1.0, 1.0)}))
        ]
        g.coordinates = GlyphCoordinates(base[:n_pts])
        g.recalcBounds(glyf)
        hmtx[n] = (base[n_pts + 1][0] - base[n_pts][0], g.xMin)
    return len(FIGURE_LIGHTEN)


def _shift(font, name, dx=0, dy=0):
    g = font["glyf"][name]
    if g.isComposite():
        for c in g.components:
            c.x, c.y = c.x + dx, c.y + dy
    elif g.numberOfContours > 0:
        g.coordinates.translate((dx, dy))
    g.recalcBounds(font["glyf"])


def center_symbols(font):
    """수학 기호·화살표의 세로 가운데를 SYMBOL_CENTER로, 양옆 여백을 SYMBOL_SPACE씩 더."""
    glyf, hmtx = font["glyf"], font["hmtx"]
    done = 0
    for n in SYMBOLS:
        if n not in glyf.glyphs:
            continue
        g = glyf[n]
        g.recalcBounds(glyf)
        dy = round(SYMBOL_CENTER - (g.yMin + g.yMax) / 2)
        # 이미 옮긴 기호를 부품으로 쓰는 .case는 세로만 맞춘다(가로 여백은 부품이 이미 가짐)
        inherited = g.isComposite() and all(c.glyphName in SYMBOLS for c in g.components)
        _shift(font, n, 0 if inherited else SYMBOL_SPACE, dy)
        adv, _ = hmtx[n]
        hmtx[n] = (adv + 2 * SYMBOL_SPACE, glyf[n].xMin)
        done += 1
    return done


def raise_brackets(font):
    for n in BRACKETS:
        _shift(font, n, 0, BRACKET_RAISE)
        font["hmtx"][n] = (font["hmtx"][n][0], font["glyf"][n].xMin)


def raise_hangul(font):
    """한글 글리프를 HANGUL_RAISE만큼 올리고, 줄 상자(ascent/descent)도 같이 올려 한글이 줄 가운데 오게 한다.
    영문은 줄 상자 안에서 그만큼 아래에 놓인다 — 토스 프로덕트 산스와 같은 관계."""
    cmap = font.getBestCmap()
    glyf = font["glyf"]
    done = set()
    for lo, hi in HANGUL_RANGES:
        for u in range(lo, hi + 1):
            n = cmap.get(u)
            if not n or n in done:
                continue
            done.add(n)
            g = glyf[n]
            if g.isComposite():
                for c in g.components:
                    c.y += HANGUL_RAISE
            elif g.numberOfContours > 0:
                g.coordinates.translate((0, HANGUL_RAISE))
            g.recalcBounds(glyf)
    r = HANGUL_RAISE
    hhea, os2 = font["hhea"], font["OS/2"]
    hhea.ascent += r
    hhea.descent += r
    os2.sTypoAscender += r
    os2.sTypoDescender += r
    os2.usWinAscent += r
    os2.usWinDescent -= r
    return len(done)


# ---------------------------------------------------------------- 3. 숫자 앞 빼기 기호

EXTRA_FEA = """
languagesystem DFLT dflt;
languagesystem latn dflt;

@AQ_FIG = [zero one two three four five six seven eight nine
           uniE071 uniE072 uniE073 uniE074 uniE075 uniE076 uniE077 uniE078 uniE079 uniE07A];
@AQ_HYPHEN = [hyphen hyphen.case];
@AQ_BEFORE = [@AQ_FIG A-Z a-z @AQ_HYPHEN minus minus.case];

# 금액·비율 앞의 '-'(Intl.NumberFormat이 내는 U+002D)를 '−'(minus.case) 모양으로.
# 앞 글자가 숫자·영문이면(ISRC KR-A12-26, 날짜 2026-10-23, 전화 010-1234) 그대로 둔다.
lookup AQ_MINUS {
    # 앞선 calt가 숫자 앞 '-'를 hyphen.case로 이미 바꿔 두므로 둘 다 받는다.
    ignore sub @AQ_BEFORE @AQ_HYPHEN' @AQ_FIG;
    sub @AQ_HYPHEN' @AQ_FIG by minus.case;  # U+2212를 직접 쓸 때와 같은 높이(숫자 가운데)
} AQ_MINUS;

# 브라우저는 letter-spacing이 0이 아니면 calt를 끈다(어데닉 금액은 자간을 쓴다).
# rclt(필수 문맥 대체)는 꺼지지 않으므로 같은 룩업을 둘 다에 건다.
feature calt {
    lookup AQ_MINUS;
} calt;

feature rclt {
    lookup AQ_MINUS;
} rclt;

# 어데닉 로고: 'AUDENIQ'를 대문자로 쓰고 ss20을 켜면 워드마크 한 글자가 된다(기본은 꺼짐 — 문장 속 AUDENIQ는 글자 그대로).
feature ss20 {
    featureNames {
        name "AUDENIQ wordmark";
        name 3 1 0x0412 "AUDENIQ 로고";
    };
    sub A U D E N I Q by aq.wordmark;
} ss20;
"""


def merge_features(font, fea):
    """원래 GSUB을 덮지 않고, 임시 글꼴에서 만든 룩업을 뒤에 붙인 뒤 기능 목록에 더한다."""
    tmp = TTFont()
    tmp.setGlyphOrder(font.getGlyphOrder())
    tmp["name"] = newTable("name")
    tmp["name"].names = []
    addOpenTypeFeaturesFromString(tmp, fea)
    # featureNames가 만든 이름(256~)을 원래 글꼴의 비어 있는 번호로 옮긴다.
    next_id = max(n.nameID for n in font["name"].names) + 1
    remap = {}
    for n in sorted(tmp["name"].names, key=lambda n: n.nameID):
        if n.nameID not in remap:
            remap[n.nameID] = next_id
            next_id += 1
        font["name"].setName(n.toUnicode(), remap[n.nameID], n.platformID, n.platEncID, n.langID)
    src = tmp["GSUB"].table
    dst = font["GSUB"].table
    base = len(dst.LookupList.Lookup)
    dst.LookupList.Lookup.extend(src.LookupList.Lookup)
    dst.LookupList.LookupCount = len(dst.LookupList.Lookup)
    # 체인 룩업 안의 룩업 번호도 옮긴다.
    for lk in src.LookupList.Lookup:
        for st in lk.SubTable:
            for rec in getattr(st, "SubstLookupRecord", []) or []:
                rec.LookupListIndex += base
            for rs in getattr(st, "ChainSubRuleSet", []) or []:
                for r in rs.ChainSubRule:
                    for rec in r.SubstLookupRecord:
                        rec.LookupListIndex += base
    added, params = {}, {}
    for rec in src.FeatureList.FeatureRecord:
        added.setdefault(rec.FeatureTag, []).extend(i + base for i in rec.Feature.LookupListIndex)
        fp = rec.Feature.FeatureParams
        if fp is not None and getattr(fp, "UINameID", None) in remap:
            fp.UINameID = remap[fp.UINameID]
        params[rec.FeatureTag] = fp
    have = set()
    for rec in dst.FeatureList.FeatureRecord:
        if rec.FeatureTag in added:
            have.add(rec.FeatureTag)
            rec.Feature.LookupListIndex = sorted(set(rec.Feature.LookupListIndex) | set(added[rec.FeatureTag]))
            rec.Feature.LookupCount = len(rec.Feature.LookupListIndex)
    # 원본에 없던 기능(rclt, ss20)은 새로 만들어 모든 언어 체계에 건다.
    for tag in sorted(set(added) - have):
        rec = otTables.FeatureRecord()
        rec.FeatureTag = tag
        rec.Feature = otTables.Feature()
        rec.Feature.FeatureParams = params.get(tag)
        rec.Feature.LookupListIndex = sorted(set(added[tag]))
        rec.Feature.LookupCount = len(rec.Feature.LookupListIndex)
        index = len(dst.FeatureList.FeatureRecord)
        dst.FeatureList.FeatureRecord.append(rec)
        for srec in dst.ScriptList.ScriptRecord:
            systems = [srec.Script.DefaultLangSys] + [r.LangSys for r in srec.Script.LangSysRecord]
            for ls in systems:
                if ls is not None:
                    ls.FeatureIndex.append(index)
                    ls.FeatureCount = len(ls.FeatureIndex)
    dst.FeatureList.FeatureCount = len(dst.FeatureList.FeatureRecord)


# ---------------------------------------------------------------- 4. 이름

def rename(font):
    """OFL 예약 이름(Pretendard)을 쓰지 않는다. 원작자 표기는 지킨다."""
    name = font["name"]
    keep_feature_names = {n.nameID: n.toUnicode() for n in name.names if n.nameID >= 256}
    name.names = []

    def put(i, s, ko=None):
        name.setName(s, i, 3, 1, 0x409)
        if ko:
            name.setName(ko, i, 3, 1, 0x412)

    put(0, "Copyright 2026 AUDENIQ. Based on Pretendard, Copyright 2021 Kil Hyung-jin, "
           "with Reserved Font Name Pretendard.",
        "Copyright 2026 AUDENIQ. Pretendard 기반 (Copyright 2021 길형진, 예약 글꼴 이름 Pretendard).")
    put(1, f"{FAMILY} Variable", "어데닉 산스 Variable")
    put(2, "Regular")
    put(3, f"{VERSION};{VENDOR};AudeniqSansVariable")
    put(4, f"{FAMILY} Variable", "어데닉 산스 Variable")
    put(5, f"Version {VERSION}; based on Pretendard {PRETENDARD_VERSION}")
    put(6, "AudeniqSansVariable-Regular")
    put(8, "AUDENIQ", "어데닉")
    put(9, "AUDENIQ (modifications); Kil Hyung-jin (Pretendard); Rasmus Andersson (Inter); "
           "Jang Soo-young, Kang Joo-yeon, Sandoll Communications (Source Han Sans); "
           "Coji Morishita (M PLUS 1p)")
    put(10, "Audeniq Sans is AUDENIQ's product typeface: Pretendard with Hangul spacing, "
            "figures and currency refined for music distribution and settlement screens.",
        "어데닉 산스는 Pretendard를 바탕으로 한글 자간·숫자·통화 기호를 어데닉 화면에 맞게 다듬은 서체예요.")
    put(11, "https://github.com/tae-ok-11/audeniq-font")
    put(13, "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
            "This license is available with a FAQ at: https://openfontlicense.org")
    put(14, "https://openfontlicense.org")
    put(16, FAMILY, "어데닉 산스")
    put(17, "Regular")
    put(25, "AudeniqSansVariable")
    for i, s in sorted(keep_feature_names.items()):
        s = s.replace("PretendardVariable", "AudeniqSansVariable")
        name.setName(s, i, 3, 1, 0x409)

    os2 = font["OS/2"]
    os2.achVendID = VENDOR
    font["head"].fontRevision = float(VERSION.rsplit(".", 1)[0]) + int(VERSION.rsplit(".", 1)[1]) / 1000


# ---------------------------------------------------------------- 출력

def save_web(font_path, woff2_path):
    f = TTFont(font_path)
    f.flavor = "woff2"
    f.save(woff2_path)


def subset(font_path, out_path, text_path):
    """자주 쓰는 한글 2,780자(KS X 1001 2,350자 포함) + 라틴·숫자·기호 — Pretendard subset_glyphs.txt와 같은 범위."""
    text = open(text_path, encoding="utf-8").read()
    f = TTFont(font_path)
    opts = Options()
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.flavor = "woff2"
    s = Subsetter(opts)
    s.populate(text=text + "−" + chr(brand.WORDMARK_CP) + chr(brand.MARK_CP))
    s.subset(f)
    f.flavor = "woff2"
    f.save(out_path)


def static_instance(var_path, wght, style):
    f = TTFont(var_path)
    inst = instancer.instantiateVariableFont(f, {"wght": wght}, updateFontNames=False)
    name = inst["name"]
    # 굵기 축 이름(fvar/STAT)만 지운다. ss·cv 기능 이름은 GSUB이 계속 부른다.
    used = set()
    for rec in inst["GSUB"].table.FeatureList.FeatureRecord:
        fp = rec.Feature.FeatureParams
        for attr in ("UINameID", "FeatUILabelNameID", "FeatUITooltipTextNameID", "SampleTextNameID", "FirstParamUILabelNameID"):
            if fp is not None and getattr(fp, attr, None):
                used.add(getattr(fp, attr))
        if fp is not None and getattr(fp, "NumNamedParameters", 0):
            used.update(range(fp.FirstParamUILabelNameID, fp.FirstParamUILabelNameID + fp.NumNamedParameters))
    for rec in list(name.names):
        if rec.nameID >= 256 and rec.nameID not in used:
            name.removeNames(nameID=rec.nameID)
    is_rbi = style in ("Regular", "Bold")
    for lang, fam in ((0x409, FAMILY), (0x412, "어데닉 산스")):
        name.setName(fam if is_rbi else f"{fam} {style}", 1, 3, 1, lang)
        name.setName(fam, 16, 3, 1, lang)
        name.setName(f"{fam} {style}", 4, 3, 1, lang)
    name.setName(style if is_rbi else "Regular", 2, 3, 1, 0x409)
    name.setName(style, 17, 3, 1, 0x409)
    name.setName(f"{VERSION};{VENDOR};AudeniqSans-{style}", 3, 3, 1, 0x409)
    name.setName(f"AudeniqSans-{style}", 6, 3, 1, 0x409)
    name.removeNames(nameID=25)
    for tag in ("STAT",):
        if tag in inst:
            del inst[tag]
    os2 = inst["OS/2"]
    os2.usWeightClass = wght
    os2.fsSelection &= ~(1 | 32 | 64)
    os2.fsSelection |= 32 if style == "Bold" else 64 if style == "Regular" else 0
    inst["head"].macStyle = 1 if style == "Bold" else 0
    inst["post"].italicAngle = 0
    return inst


def main():
    var_src, subset_txt = fetch_sources()
    font = TTFont(var_src, lazy=False)  # gvar를 먼저 다 풀어야 글리프를 바꿔도 점 개수가 어긋나지 않는다

    font = remap_weight(font)
    print("굵기: " + ", ".join(f"{u}→{o}" for u, o in WEIGHT_MAP.items()))
    n = tighten_hangul(font)
    print(f"한글 {n}자 자간 -{HANGUL_TIGHTEN}유닛")
    lighten_figures(font)
    n = scale_figures(font)
    print(f"숫자·기호 {n}자 ×{FIGURE_SCALE:.3f}")
    narrow_space(font)
    wide_middle_dot(font)
    n_sym = center_symbols(font)
    raise_brackets(font)
    raise_hangul(font)
    print(f"기호 {n_sym}자 가운데 {SYMBOL_CENTER}, 괄호 +{BRACKET_RAISE}, 6·8·9·5 가볍게")
    print(f"띄어쓰기 {SPACE_WIDTH}, 한글 +{HANGUL_RAISE}")
    brand.add_logo_glyphs(font)
    print(f"어데닉 로고 U+{brand.WORDMARK_CP:04X}, U+{brand.MARK_CP:04X}, ss20")
    merge_features(font, EXTRA_FEA)
    rename(font)

    for d in ("variable", "static", "web"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    var_out = os.path.join(OUT, "variable", "AudeniqSansVariable.ttf")
    font.save(var_out)
    save_web(var_out, os.path.join(OUT, "web", "AudeniqSansVariable.woff2"))
    subset(var_out, os.path.join(OUT, "web", "AudeniqSansVariable-Subset.woff2"), subset_txt)
    print("가변 글꼴:", var_out)

    if "--variable-only" in sys.argv:
        return
    for wght, style in WEIGHTS:
        inst = static_instance(var_out, wght, style)
        p = os.path.join(OUT, "static", f"AudeniqSans-{style}.ttf")
        inst.save(p)
        save_web(p, os.path.join(OUT, "web", f"AudeniqSans-{style}.woff2"))
        print("고정 굵기:", p)

    if "--check" in sys.argv:
        subprocess.check_call([sys.executable, os.path.join(ROOT, "tests", "check.py")])


if __name__ == "__main__":
    main()
