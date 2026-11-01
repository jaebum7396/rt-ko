# 로그 트레이더 한글패치 (새 번역)

**Warhammer 40,000: Rogue Trader** 비공식 한글패치입니다. 게임 1.6.1.514 기준, 본편과 DLC 1~3의 텍스트 75,411줄 전부를 같은 원칙으로 새로 번역했습니다.

- **일반판**
- **해병문학체판**: 아스타르테스 대사만 해병문학체로 바꾼 판

> 다운로드: 공개 시 릴리스 링크

---

## 기존 한글패치와 무엇이 다른가

| | 기존 한글패치 | 이 패치 |
|---|---|---|
| **번역 방식** | AI 초벌 2종 + AI 재번역 + 일부 손번역 | 전체를 한 원칙으로 새로 번역, 화자와 장면 앞뒤 대사를 보고 옮김 |
| **인물 말투** | 번역한 사람·시기에 따라 다름 | 인물별 말투표, 동료 27명 · NPC 143명 |
| **로그 트레이더** | 반말 위주 | 하오체 |
| **용어** | 일부 흔들림: Inquisitor = 심문관 336줄, 이단심문관 63줄 | 나무위키 등 국내 커뮤니티 표기 기준 용어집 1,621개 |
| **이름** | — | 아이템·기술·지명 이름 4,501개를 메뉴와 대사에서 같게 |
| **아이템·기술 설명** | "~합니다" | "~한다", 같은 효과는 같은 문장틀 |
| **검사** | — | 모든 줄의 게임 태그·변수·줄바꿈 자동 검사 |
| **옵션** | — | 해병문학체판 |

### 말투 예

| 인물 | 말투 |
|---|---|
| 아벨라드 | 하십시오체, "로드 캡틴" |
| 시스터 아젠타 | 하십시오체 |
| 자이 헤이다리 | 반말, "보스" |
| 이를리엣 | 하오체 |
| 파스칼 | 하십시오체, 자신을 "본 개체" |
| 울파르 | 하게체, "자네" |

전체 말투표: [glossary/voices.tsv](glossary/voices.tsv) · 번역 원칙: [STYLE.md](STYLE.md)

---

## 예문 비교

### 대사

| 화자 | 원문 | 기존 패치 | 이 패치 |
|---|---|---|---|
| 아벨라드 | "Sister Argenta, it is a relief to see you. We require all the forces we can muster!" | "아르젠타 자매님, 무사한 모습을 뵈어 참으로 다행입니다. 우리가 동원할 수 있는 모든 병력이 시급히 필요합니다!" | "시스터 아젠타, 만나서 다행이네. 지금은 병력 한 명이라도 더 필요하네!" |
| 플레이어 | "Mutiny? But who would attempt a mutiny here, in the warp?" | "반란? 하지만 대체 누가 이 워프 한복판에서 그런 짓을?" | "반란이라고? 대체 누가 이 워프 한가운데서 반란을 일으키겠소?" |
| 플레이어 | "I am under no obligation to take such risks!" | "내가 왜 그런 위험을 감수해야 하는데!" | "내가 그런 위험까지 감수할 의무는 없소!" |
| 플레이어 | "We are both servants of the God-Emperor and Lady Theodora. Does it become anyone of our status to engage in petty feuds?" | "우리 둘 다 신-황제 폐하와 테오도라 각하의 종복입니다. 주제넘게 사소한 말다툼을 벌일 필요가 있겠습니까?" | "우리 둘 다 신황제와 테오도라 님의 종이오. 우리 같은 지위의 사람이 사소한 다툼이나 벌여서야 되겠소?" |

### 용어

| 원문 | 기존 패치 | 이 패치 |
|---|---|---|
| Sister Argenta | 아르젠타 자매님 | 시스터 아젠타 |
| Inquisitor | 심문관 / 이단심문관 | 이단심문관 |
| Warrant of Trade | 무역 영장 | 무역의 영장 |
| Momentum | 기세 | 원동력 |
| Desperate Measure | 필사적 수단 | 필사의 결단 |
| Veil | 장막 | 베일 |
| High / Low Gothic | — | 하이 고딕 / 로우 고딕 |

### 아이템·기술 설명

| 원문 | 기존 패치 | 이 패치 |
|---|---|---|
| This character gains +{THP} temporary wounds. | 이 캐릭터는 +{THP}의 임시 생명력을 얻습니다. | 이 캐릭터는 임시 체력을 +{THP} 얻는다. |
| Medium-range dorsal lance weapon dealing (from 32 to 40) damage. | 중거리 함배 랜스 무기로 (32~40) 피해를 입힙니다. | (32~40)의 피해를 주는 중거리 상부 랜스 무장이다. |

### 일반판과 해병문학체판

2차 번역이 끝나면 울파르 대사로 채웁니다.

---

## 설치 방법

1. 기존 한글패치의 자동 갱신 모드를 지웁니다. 게임을 켤 때마다 번역 파일을 덮어씁니다.
   `%USERPROFILE%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\KoreanPatch_AutoUpdate` 폴더 삭제
2. 한글 글꼴 모드 FontKorean이 필요합니다. 기존 한글패치를 쓰고 있었다면 이미 설치돼 있습니다. 없다면 [기존 한글패치 릴리스](https://github.com/geungogma/RogueTrader-KoreanPatch/releases)에서 `FontKorean.zip`을 받아 위 `UnityModManager` 폴더 안에 `FontKorean` 폴더째 넣습니다.
3. 게임 폴더의 `WH40KRT_Data\StreamingAssets\Localization\enGB.json`을 백업하고, 받은 `enGB.json`으로 바꿉니다.
   - 게임 폴더: 스팀 라이브러리에서 게임 우클릭 → 관리 → 로컬 파일 보기
4. 게임 언어를 English로 둡니다.

### 되돌리기 · 게임 업데이트 뒤
- 백업한 `enGB.json`을 다시 넣거나, 스팀에서 게임 파일 무결성 검사를 하면 영어로 돌아옵니다.
- 게임이 업데이트되면 `enGB.json`이 원래대로 돌아오므로 다시 넣어야 합니다.

---

## 어떻게 번역했나

1. 게임에 들어 있는 Owlcat 공식 모드 템플릿에서 줄마다 화자와 장면 위치를 함께 뽑았습니다.
2. 번역 원칙을 정했습니다: 자연스러운 한국어, 인물별 말투 고정, 아이템·기술 이름과 설명까지 번역. [STYLE.md](STYLE.md)
3. 용어 1,621개를 나무위키 등 국내 커뮤니티 표기와 대조해 정하고, 화자 170명의 말투를 정했습니다.
4. 대화를 장면째 묶어 298묶음으로 나누고, 묶음마다 해당 용어와 말투를 붙여 OpenAI GPT-6 Astra로 번역했습니다. 메뉴의 이름을 먼저 번역해 대사에서도 같은 이름을 쓰게 했습니다.
5. 모든 줄의 게임 태그·변수·줄바꿈을 스크립트로 검사하고, 걸린 줄만 다시 번역했습니다. 설계·검사·관리는 Claude가 맡았습니다.

AI 번역이라 어색한 문장이 남아 있을 수 있습니다. 발견하면 알려 주세요.

---

## 크레딧
- 한글 글꼴 모드 FontKorean, 기존 한글패치: [geungogma/RogueTrader-KoreanPatch](https://github.com/geungogma/RogueTrader-KoreanPatch)
- 용어 표기: [나무위키](https://namu.wiki/w/Warhammer%2040,000:%20Rogue%20Trader) 등 국내 워해머 커뮤니티
- 원작: Owlcat Games / Games Workshop. 비공식 팬 번역이며 상업적 목적이 없습니다.

개발 문서: [docs/DEV.md](docs/DEV.md)
