# 번역 파이프라인 규격 (RTKO-8) — 모든 도구가 따르는 공용 계약

## 폴더
| 경로 | 내용 | git |
|---|---|---|
| `src/` → `/data2/rt-ko` | `game/`, `template/Strings/`, `ref/korean-patch/` | 제외 |
| `tools/groups.py` | 경로 → 묶음 (정본) | O |
| `glossary/*.tsv` | `setting.tsv`, `system.tsv`, `voices.tsv`, `names.tsv` | O |
| `work/chunks/<묶음>/<청크>.src.tsv` | 아스트라 입력 | 제외 |
| `work/chunks/<묶음>/<청크>.keys.tsv` | 줄 번호 → GUID | 제외 |
| `work/chunks/<묶음>/<청크>.terms.tsv` | 청크에 나오는 용어만 | 제외 |
| `work/manifest.json` | 청크 목록·상태 | O |
| `work/out/<묶음>/<청크>.tsv` | 아스트라 출력 (번역 결과) | O |
| `work/check/` | 검사 결과·재번역 목록 | O |
| `work/run/<청크>/` | 아스트라 작업 폴더·로그 | 제외 |
| `build/` | 만든 enGB.json·설치 zip | 제외 |

청크 이름: `<묶음>-<3자리 번호>` (예: `w2-act01-004`).

## 글자 이스케이프 (TSV 안)
`\` → `\\`, 줄바꿈 → `\n`. 되돌릴 때는 반대 순서로. 원문에 탭은 없다.

## 청크 입력 — `<청크>.src.tsv` (UTF-8, 머리줄 없음)
```
# scene: World/Dialogs/Ch1/RaycadMinoris/RM_Governor
1	FootfallLiege	"You took your time, Lord Captain."
2	PLAYER	[Lie] I was delayed by the warp.
3	-	Bolt Pistol
```
- `#`로 시작하는 줄은 장면 머리줄이다. 번역하지 않고 출력에도 넣지 않는다.
- 열: `n`(청크 안 1부터 읽는 순서), `speaker`, `text`(영어, 이스케이프)
- speaker: Strings의 `speaker` 그대로 (예: `AbelardCompanion`). `Answer_*` 줄은 `PLAYER`. 화자 없는 대사는 `?`, 대사가 아닌 글은 `-`.
- GUID는 넣지 않는다 (토큰 낭비). `<청크>.keys.tsv`: `n<TAB>GUID<TAB>Strings 상대 경로`.

## 청크 나누기
- 묶음은 `groups.group_of(경로)`. `skip`과 빈 줄(`''`, `Placeholder`, `draft`), 글자가 하나도 없는 줄(숫자·태그만)은 넣지 않는다 (만들 때 원문 그대로 복사).
- 장면 = 줄 파일이 들어 있는 가장 깊은 폴더. 장면은 쪼개지 않고, 경로 순서대로 이어 붙여 **청크당 약 6,000단어**(최대 9,000)로 만든다.
- 9,000단어가 넘는 장면만 줄 경계에서 자르고, 뒤 조각 머리줄에 `(2부)`처럼 표시한다.
- 장면 안 순서: 파일 번호 순, 같은 번호면 Cue → Answer.

## 청크 용어 — `<청크>.terms.tsv`
`english<TAB>korean<TAB>메모` — glossary/*.tsv 중 영어 용어가 청크 원문에 나오는 것만 (대소문자 무시, 단어 경계). 2차(대화) 청크는 `names.tsv`(1차 결과의 이름)도 넣는다.

## 청크 출력 — `work/out/<묶음>/<청크>.tsv`
`n<TAB>한국어` — 입력의 모든 n이 정확히 한 번, 같은 순서, 같은 이스케이프. 머리줄·설명 금지.

## 아스트라 실행
- 지시서 = 머리말 + STYLE.md + 청크 용어 + "src.tsv를 번역해 out.tsv만 쓴다. 스크립트 작성·자체 검사 금지. 끝나면 `DONE <줄 수>`만 답한다".
- `gpt-6-astra`, `-c model_reasoning_effort="medium"`. 청크당 새 세션 하나.

## 검사 (check.py) — 실패한 줄만 재번역
- 오류: 빠지거나 겹친 n, 빈 번역, `{…}` 표시 불일치(`{g}`·`{d}`·`{n}` 안 글자와 `{mf}`·`{rt_mf}` 두 칸 내용은 제외하고 비교), `\n` 개수 불일치, HTML 태그 불일치
- 경고: 한글 없음, 영어 단어 3개 이상 연속 잔존(태그·용어 제외), 용어집 위반(원문에 용어가 있는데 정한 한국어가 없음), 길이 비율 이상(한글 글자 수 / 영어 글자 수가 0.25~1.6 밖)

## 만들기 (build.py)
- 원본 enGB.json에서 시작해 번역된 GUID의 `Text`만 바꾼다. 번역이 없는 줄은 지금 한글패치 문장 → 없으면 영어 순으로 채운다.
- 출력 형식은 원본과 같게 (BOM 없음, CRLF, 들여쓰기 2칸).
- 설치 zip: `enGB.json` + `FontKorean/` + 설치 안내 ("자동 갱신 모드 KoreanPatch_AutoUpdate를 먼저 지울 것"이 첫 줄).
- 게임 업데이트: 이전·새 enGB.json을 비교해 바뀐·새 GUID만 청크로 만든다.
