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
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib.iup import iup_delta
from fontTools.varLib.models import supportScalar
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "sources")
OUT = os.path.join(ROOT, "fonts")

PRETENDARD_VERSION = "1.3.9"
PRETENDARD_TGZ = f"https://registry.npmjs.org/pretendard/-/pretendard-{PRETENDARD_VERSION}.tgz"
PRETENDARD_SHA1 = "b1f86d5a7a729f518974098fcf85f34fff3526b7"  # npm dist.shasum
PRETENDARD_MEMBER = "package/dist/public/variable/PretendardVariable.ttf"
SUBSET_MEMBER = "package/subset_glyphs.txt"

VERSION = "0.1.0"
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

# 숫자·영문 굵기: 400에서 wght +30만큼(약 획 +5%). 한글은 그대로.
LATIN_BOOST = 30
LATIN_BOOST_RANGES = [(0x30, 0x39), (0x41, 0x5A), (0x61, 0x7A)]
LATIN_BOOST_MARKS = ",.:;%₩$€¥£"  # 금액·비율에서 숫자 바로 옆에 붙는 기호와 통화 기호

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


# ---------------------------------------------------------------- 2. 숫자·영문을 한글보다 살짝 굵게

def _norm(w):
    return {"wght": (w - 400) / (400 - 45) if w < 400 else (w - 400) / (930 - 400)}


def _coords_at(font, name, loc):
    """굵기 위치 loc에서 글리프 점 좌표(위상 점 4개 포함)."""
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


def boost_latin(font):
    """토스 프로덕트 산스처럼, 한글과 같은 굵기 값이면 얇아 보이는 숫자·영문을 조금 굵게.
    각 마스터 위치의 외곽선을 조금 더 굵은 위치의 외곽선으로 바꾼다(원래 보간 안의 모양이라 새 모양이 생기지 않는다).
    400에서 +LATIN_BOOST, 45에서 그 절반, 930(가장 굵음)은 그대로 — 굵을수록 차이가 줄어든다."""
    cmap = font.getBestCmap()
    names = {cmap[u] for lo, hi in LATIN_BOOST_RANGES for u in range(lo, hi + 1) if u in cmap}
    names |= {cmap[ord(c)] for c in LATIN_BOOST_MARKS}
    # 고정폭·대체 숫자(cv/ss/tnum이 부르는 uniE06B–uniE080)도 같은 획 굵기여야 한다.
    names |= {n for n in font.getGlyphOrder() if n.startswith(("uniE06", "uniE07", "uniE080"))}
    shift = {45: 45 + LATIN_BOOST // 2, 400: 400 + LATIN_BOOST, 930: 930}
    glyf, gvar, hmtx = font["glyf"], font["gvar"], font["hmtx"]
    changed = 0
    for n in sorted(names):
        g = glyf[n]
        if g.isComposite() or g.numberOfContours <= 0:
            continue  # 부품 글리프는 바뀐 바탕 글리프를 따라간다
        new = {w: _coords_at(font, n, _norm(shift[w])) for w in shift}
        base = new[400]
        n_pts = len(base) - 4
        gvar.variations[n] = [
            TupleVariation(axes, [tuple(p) for p in (new[w] - base)])
            for w, axes in ((45, {"wght": (-1.0, -1.0, 0.0)}), (930, {"wght": (0.0, 1.0, 1.0)}))
        ]
        g.coordinates = GlyphCoordinates(base[:n_pts])
        g.recalcBounds(glyf)
        hmtx[n] = (base[n_pts + 1][0] - base[n_pts][0], g.xMin)
        changed += 1
    return changed


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
"""


def merge_features(font, fea):
    """원래 GSUB을 덮지 않고, 임시 글꼴에서 만든 룩업을 뒤에 붙인 뒤 기능 목록에 더한다."""
    tmp = TTFont()
    tmp.setGlyphOrder(font.getGlyphOrder())
    addOpenTypeFeaturesFromString(tmp, fea)
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
    added = {}
    for rec in src.FeatureList.FeatureRecord:
        added.setdefault(rec.FeatureTag, []).extend(i + base for i in rec.Feature.LookupListIndex)
    have = set()
    for rec in dst.FeatureList.FeatureRecord:
        if rec.FeatureTag in added:
            have.add(rec.FeatureTag)
            rec.Feature.LookupListIndex = sorted(set(rec.Feature.LookupListIndex) | set(added[rec.FeatureTag]))
            rec.Feature.LookupCount = len(rec.Feature.LookupListIndex)
    # 원본에 없던 기능(rclt)은 새로 만들어 모든 언어 체계에 건다.
    for tag in sorted(set(added) - have):
        rec = otTables.FeatureRecord()
        rec.FeatureTag = tag
        rec.Feature = otTables.Feature()
        rec.Feature.FeatureParams = None
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
    s.populate(text=text + "−")
    s.subset(f)
    f.flavor = "woff2"
    f.save(out_path)


def static_instance(var_path, wght, style):
    f = TTFont(var_path)
    inst = instancer.instantiateVariableFont(f, {"wght": wght}, updateFontNames=False)
    name = inst["name"]
    for rec in list(name.names):
        if rec.nameID >= 256:
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

    n = tighten_hangul(font)
    print(f"한글 {n}자 자간 -{HANGUL_TIGHTEN}유닛")
    n = boost_latin(font)
    print(f"숫자·영문 {n}자 굵기 +{LATIN_BOOST}")
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
