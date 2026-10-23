# Audeniq Sans · 어데닉 산스

AUDENIQ의 제품 서체예요. [Pretendard](https://github.com/orioncactus/pretendard) 1.3.9를 바탕으로 한글 자간, 숫자·영문 굵기, 금액의 빼기 기호를 어데닉 화면에 맞게 다듬었어요. 무엇을 왜 바꿨는지는 [DESIGN.md](DESIGN.md)에 있어요.

## 파일

| 경로 | 내용 |
|---|---|
| `fonts/variable/AudeniqSansVariable.ttf` | 가변 글꼴, 굵기 45–930 |
| `fonts/static/AudeniqSans-{Thin…Black}.ttf` | 고정 굵기 9개 (100–900) |
| `fonts/web/AudeniqSansVariable.woff2` | 웹용 가변 글꼴, 한글 11,172자 전체 |
| `fonts/web/AudeniqSansVariable-Subset.woff2` | 웹용 가변 글꼴, 자주 쓰는 한글 2,780자(KS X 1001 2,350자 포함) + 라틴·기호. Pretendard `subset_glyphs.txt`와 같은 범위 |
| `fonts/web/AudeniqSans-*.woff2` | 웹용 고정 굵기 |
| `css/audeniq-sans.css` | `@font-face`, 자간 토큰, `.aq-num` · `.aq-num-hero` · `.aq-code` |
| `specimen/index.html` | Pretendard와 나란히 보는 견본 |

## 스튜디오에 적용

1. `css/audeniq-sans.css`와 `fonts/web/`을 어데닉 CDN에 올려요.
2. 각 앱 `index.html`의 Pretendard jsDelivr 링크를 그 CSS로 바꾸고, CSP `font-src`·`style-src`를 CDN 주소로 맞춰요.
3. `tokens.css`의 `--font-brand`를 `"Audeniq Sans", "Pretendard Variable", Pretendard`로 바꿔요.
4. 한글 자간이 글꼴에 들어 있으니 화면 CSS의 `letter-spacing`을 0.02em씩 올려요(−0.02em → 0, −0.04em → −0.02em). 크기별 값은 DESIGN.md의 표를 따라요.

## 빌드

```sh
pip install -r build/requirements.txt
python3 build/build.py --check     # 원본을 npm에서 받아 해시 확인 → 빌드 → 검사
python3 build/build.py --variable-only   # 가변 글꼴만 (빠름)
```

원본(`sources/`)은 저장소에 넣지 않아요. 빌드가 npm의 `pretendard@1.3.9`를 받아 SHA-1을 확인해요. `tests/check.py`는 이름, 한글 폭, 숫자·영문 획 굵기, 빼기 기호 규칙, 고정폭 숫자, 세로 중심을 검사해요.

## 라이선스

SIL Open Font License 1.1 ([OFL.txt](OFL.txt)). Pretendard(길형진), Inter(Rasmus Andersson), 본고딕/Source Han Sans(Adobe, 산돌커뮤니케이션), M PLUS 1p를 바탕으로 했어요. OFL에 따라 Pretendard라는 이름은 쓰지 않아요.
