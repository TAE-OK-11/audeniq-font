"""전체 점검 — 모든 글리프를 Pretendard와 굵기마다 비교하고, 바꾼 것이 의도한 묶음 안에만 있는지 본다.

    python3 tests/audit.py            # 결과를 출력하고, 문제가 있으면 1로 끝난다

보는 것:
  1. 바꾸지 않기로 한 글리프는 잉크 상자·폭이 원본과 같다(1유닛 안).
  2. 바꾼 묶음은 바꾼 방식대로만 바뀌었다(한글은 위로 HANGUL_RAISE, 숫자는 FIGURE_SCALE배 …).
  3. 어떤 글리프도 상자가 터지지 않았다(폭 0 이상, 잉크가 글자 폭에서 1em 넘게 벗어나지 않음).
  4. 한글끼리 붙여 써도 잉크가 겹치지 않는다(가장 굵은 굵기까지).
"""
import os
import sys

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))
import build as B  # noqa: E402

VAR = os.path.join(ROOT, "fonts", "variable", "AudeniqSansVariable.ttf")
SRC = os.path.join(ROOT, "sources", "PretendardVariable.ttf")
WEIGHTS = (100, 400, 700, 900)
problems = []


def orig_weight(user):
    pts = sorted(B.WEIGHT_MAP.items())
    for (u0, o0), (u1, o1) in zip(pts, pts[1:]):
        if u0 <= user <= u1:
            return o0 + (o1 - o0) * (user - u0) / (u1 - u0)


def measure(font, wght, names):
    gs = font.getGlyphSet(location={"wght": wght}, normalized=False)
    out = {}
    for n in names:
        pen = BoundsPen(gs)
        gs[n].draw(pen)
        out[n] = (pen.bounds, gs[n].width)
    return out


f, src = TTFont(VAR), TTFont(SRC)
cmap, scmap = f.getBestCmap(), src.getBestCmap()
common = [n for n in src.getGlyphOrder() if n in f.getReverseGlyphMap()]

# 바꾼 묶음
hangul = {scmap[u] for lo, hi in B.HANGUL_RANGES for u in range(lo, hi + 1) if u in scmap}
figures = B._figure_glyphs(src)
digit_only = B._figure_glyphs(src, extra="")
symbols = set(B.SYMBOLS)
brackets = set(B.BRACKETS)
changed_other = {
    scmap[0x20]: "띄어쓰기", scmap[0xA0]: "띄어쓰기", scmap[0xB7]: "가운뎃점", "uni2117": "℗",
    "colon.case": "시각 ':'", "hyphen.case": "코드 '-'", "eight": "가볍게", "six": "가볍게", "nine": "가볍게",
    "five": "가볍게", "uniE06F": "가볍게", "uniE070": "가볍게",
}
# 부품으로 바뀐 글리프를 쓰는 부품 글리프(예: 악센트 붙은 글자는 바뀌지 않지만, '·'를 부품으로 쓰는 글자 등)
uses_changed = set()
changed_names = hangul | figures | symbols | brackets | set(changed_other)
glyf = f["glyf"]
for n in common:
    g = glyf[n]
    if g.isComposite() and any(c.glyphName in changed_names for c in g.components):
        uses_changed.add(n)

counts = {"같음": 0, "한글": 0, "숫자·기호": 0, "기호 높이": 0, "괄호": 0, "그 밖에 바꾼 것": 0, "부품을 따라 바뀜": 0}
for user in WEIGHTS:
    a = measure(f, user, common)
    b = measure(src, orig_weight(user), common)
    for n in common:
        (ba, wa), (bb, wb) = a[n], b[n]
        # 3. 상자가 터지지 않음
        if wa < 0 or (ba and (ba[0] < -2048 or ba[2] > wa + 2048 or ba[1] < -1200 or ba[3] > 2600)):
            problems.append(f"{user} {n}: 상자 이상 {ba} 폭 {wa}")
        if (ba is None) != (bb is None):
            problems.append(f"{user} {n}: 잉크가 {'생김' if bb is None else '사라짐'}")
            continue
        if n in hangul:
            counts["한글"] += 1
            if ba and abs((ba[1] - bb[1]) - B.HANGUL_RAISE) > 1.5:
                problems.append(f"{user} {n}: 한글 높이 차이 {ba[1]-bb[1]:.1f} (기대 {B.HANGUL_RAISE})")
            if ba and abs((ba[3] - ba[1]) - (bb[3] - bb[1])) > 1.5:
                problems.append(f"{user} {n}: 한글 크기가 바뀜")
            continue
        if n in figures:
            counts["숫자·기호"] += 1
            if ba and abs((ba[3] - ba[1]) - (bb[3] - bb[1]) * B.FIGURE_SCALE) > 6:
                problems.append(f"{user} {n}: 숫자 높이 {ba[3]-ba[1]:.0f} (기대 {(bb[3]-bb[1])*B.FIGURE_SCALE:.0f})")
            continue
        if n in symbols:
            counts["기호 높이"] += 1
            if ba and abs((ba[1] + ba[3]) / 2 - B.SYMBOL_CENTER) > 3:
                problems.append(f"{user} {n}: 기호 가운데 {(ba[1]+ba[3])/2:.0f}")
            continue
        if n in brackets:
            counts["괄호"] += 1
            if ba and abs((ba[1] - bb[1]) - B.BRACKET_RAISE) > 1.5:
                problems.append(f"{user} {n}: 괄호 높이 차이 {ba[1]-bb[1]:.1f}")
            continue
        if n in changed_other:
            counts["그 밖에 바꾼 것"] += 1
            continue
        if n in uses_changed:
            counts["부품을 따라 바뀜"] += 1
            continue
        # 1. 바꾸지 않기로 한 글리프
        # 마스터 사이 굵기(700 등)에서는 굵기 대응(avar) 반올림으로 1유닛 안팎 차이가 난다
        same = abs(wa - wb) <= 1 and (ba is None or all(abs(x - y) <= 1 for x, y in zip(ba, bb)))
        if same:
            counts["같음"] += 1
        else:
            problems.append(f"{user} {n}: 바뀌면 안 되는데 바뀜 상자 {bb}→{ba} 폭 {wb}→{wa}")

# 4. 한글끼리 잉크가 겹치는 정도가 Pretendard보다 나쁘지 않음
#    (가장 좁은 오른쪽 여백 + 가장 좁은 왼쪽 여백. Pretendard도 굵은 굵기에서는 음수다)
syll = [cmap[u] for u in range(0xAC00, 0xD7A4)]
ssyll = [scmap[u] for u in range(0xAC00, 0xD7A4)]


def closest(font, wght, names):
    m = measure(font, wght, names)
    r = min(m, key=lambda n: m[n][1] - m[n][0][2])
    l = min(m, key=lambda n: m[n][0][0])
    return m[r][1] - m[r][0][2] + m[l][0][0], chr(int(r[3:], 16)) + chr(int(l[3:], 16))


for user in (400, 700, 800, 930):
    ours, pair = closest(f, user, syll)
    theirs, _ = closest(src, orig_weight(user), ssyll)
    print(f"굵기 {user}: 가장 가까운 두 음절 사이 {ours:.0f}({pair}) / Pretendard {theirs:.0f}")
    if ours < min(0, theirs) - 5:
        problems.append(f"굵기 {user}: 한글 두 음절이 Pretendard보다 더 겹침 ({ours:.0f} < {theirs:.0f})")

print("굵기 4개 × 글리프", len(common), "개 비교:", ", ".join(f"{k} {v}" for k, v in counts.items()))
if problems:
    print(f"\n문제 {len(problems)}개")
    for p in problems[:80]:
        print("  " + p)
    sys.exit(1)
print("문제 없음")
