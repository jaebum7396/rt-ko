# 원본 형식 (RTKO-8)

게임 1.6.1.514 (2026-07-17, Steam build 24257885). 원본은 `src/` → `/data2/rt-ko`.

## 1. 게임이 읽는 파일 — `src/game/WH40KRT_Data/StreamingAssets/Localization/<locale>.json`
- 언어: enGB deDE esES frFR jaJP ruRU trTR zhCN (+ dev, Sound). 한국어 칸은 없다.
- 형식: `{"strings": {"<GUID>": {"Offset": 0, "Text": "..."}}}` — 77,691줄, Offset은 전부 0.
- enGB.json: BOM 없음, CRLF 줄바꿈, 들여쓰기 2칸. 18.7MB.
- 글 안에 줄바꿈(`\n`)이 있는 줄 1,904개, 탭은 없다.
- 한글패치는 **enGB.json을 한국어로 바꿔치기**한다 (영어 칸 사용).

## 2. 번역 원본 — `src/template/Strings/` (모드 템플릿 `Modding/WhRtModificationTemplate.tar`에서 Strings만 풀었다)
- 줄 하나 = JSON 파일 하나. 파일 77,915개(고유 GUID 77,852개 — 겹치는 63개는 전부 Credits), 701MB. 경로가 곧 분류다 (`Mechanics/Blueprints/<분류>/…`).
- 필드
  - `key`: 게임 파일의 GUID와 같다 (enGB 77,691줄 모두 파일이 있다)
  - `source`: 원문 언어 (대부분 ruRU — 영어도 번역본이다)
  - `ownerGuid`: 이 줄을 가진 블루프린트
  - `speaker`, `speakerGender`(Male/Female/n/a): 화자 — 대사 20,220줄에 있다, 화자 497명
  - `comment`: 개발자 메모(러시아어) 1,152줄 — 상황 설명이라 번역 맥락으로 쓸 만하다
  - `languages[]`: 언어별 `text`, `translated_from`, `original_text`, `traits[]`
- 대사 파일 이름: `Cue_0003_Text`(NPC 대사), `Answer_0001_Text`(플레이어 선택지), `Answer_N_SoulMarkShift.Description` 등. 같은 폴더 = 한 장면(대화 블루프린트). 대화 나무 구조는 템플릿에 없어서, 순서는 번호로 어림한다.

## 3. 분량 (번역 대상 75,496줄 / 1,795,931단어)
| 묶음 | 줄 | 단어 |
|---|---|---|
| 동료 대화·개인 퀘스트·로맨스 | 10,339 | 297,627 |
| 2막 | 8,099 | 212,458 |
| DLC1 / DLC2 / DLC3 | 7,241 / 5,480 / 6,485 | 185,449 / 136,716 / 181,930 |
| 4~5막·에필로그 | 5,151 | 164,716 |
| 공통 대화·여행·탐사·퀘스트 | 5,139 | 113,201 |
| 프롤로그·1막 | 3,922 | 107,052 |
| 함선·식민지·탐사 | 4,782 | 106,429 |
| UI·시스템·백과사전·유닛 | 8,110 | 102,173 |
| 3막 | 3,666 | 95,399 |
| 기술·재능·아키타입·상태 | 3,772 | 52,785 |
| 아이템·무기·장비 | 3,310 | 39,996 |
| 제외 (테스트·크레딧·빈 줄) | 1,545 (+650) | 12,647 |

묶음 규칙은 `tools/groups.py`가 정본이다.

## 4. 글 안의 표시 (번역할 때 지킬 것)
| 표시 | 개수 | 다루는 법 |
|---|---|---|
| `{g|Encyclopedia:X}글자{/g}` | 17,066 | 태그 유지, 글자만 번역 (용어집) |
| `{n}글자{/n}` | 16,939 | 대사 속 서술. 태그 유지, 안은 서술체(해라체) |
| `{d|X}글자{/d}` | 706 | 태그 유지, 글자만 번역 |
| `{mf|남|여}`, `{rt_mf|남|여}`, `{nc|a|b}` | 3,419 / 134 / 4 | 구조 유지, 두 칸 다 번역 (`rt_mf` = 로그 트레이더 성별) |
| `{name}`, `{rt_name}`, `{petname}` 등 변수 | 1,539 / 11 / 65 | 그대로 |
| `{uip|…}`, `{unit_stat|…}`, `{bind|…}`, `{console_bind|…}`, `{mouse_icon|…}`, `{br}`, `{text}`, `{target}`, `{count}`… | 42종 | 그대로 |
| `<b>`, `<i>`, `<indent>` 같은 HTML 태그 | | 그대로 |

## 5. 지금 쓰는 한글패치 — `src/ref/korean-patch/` (geungogma/RogueTrader-KoreanPatch v1.0.0)
- `enGB.json`: 77,689줄(우리 원본보다 2줄 적다), 76,711줄에 한글
- `font/FontKorean/`: UMM 모드 (`FontKorean.dll` + `Resources/notosanskr` 에셋번들, 폴백 글꼴) → 재사용
- `autoupdate/`: 게임을 켤 때마다 enGB.json을 받아 덮어쓴다 → 우리 패치와 함께 쓰면 안 된다
