# Task: Korean translation sample v2 (keep it lean)

Translate `source.tsv` (columns: id, speaker, English) into Korean for a Warhammer 40,000: Rogue Trader fan patch, following the style guide below exactly.

Output: write `out.tsv` — one line per id, same order: `id<TAB>Korean`. No other files, no scripts, no self-check runs. When done, reply only `DONE <line count>`.

---

# 로그 트레이더 한글패치 번역 원칙

## 1. 자연스러운 한국어가 먼저 (의역 허용)
- 직역하지 말고 한국 게임 대사처럼 읽히게 옮긴다. 영어 어순, 수동태, "그/그녀" 같은 대명사, "~하는 것이다" 남발 금지.
- 관용구·말장난은 한국어 관용구로 바꾼다.
  - "Easier said than done." → (X) 행하는 것보다 말하는 것이 쉽다 → (O) 말이야 쉽지.
  - "I'd rather die than serve a xenos." → (X) 나는 제노스를 섬기느니 차라리 죽는 것을 택하겠다 → (O) 제노스를 섬길 바엔 죽고 말지.
- 의역해도 정보는 그대로 둔다. 사실, 이름, 숫자, 조건, 약속, 선택지의 결과를 빼거나 보태지 않는다.
- 길이는 원문과 비슷하게. 선택지와 UI는 더 짧게.

## 2. 말투
- 인물마다 말투를 고정한다 (아래 표).
- 듣는 사람에 따라 높임을 바꾼다. 적·괴물·하인에게 외치는 말은 낮춘다 ("불타라, 이단자여!").

| 화자 | 말투 |
|---|---|
| SENESCHAL (집사장) | 깍듯한 하십시오체. 플레이어를 "로드 캡틴" 또는 "주군"으로 부른다 |
| TECHPRIEST (테크 프리스트) | 건조하고 기계적인 하십시오체 |
| SISTER (수녀) | 열성적인 하십시오체. 적에게는 해라체 |
| NAVIGATOR (항법사) | 귀족적이고 비꼬는 해요체 |
| SMUGGLER (밀수꾼) | 능글맞은 반말. 플레이어를 "보스"로 부른다 |
| PLAYER (로그 트레이더) | 위엄 있는 하오체 ("보고하시오") |
| NARRATOR | 문어체 해라체 |

## 3. 아이템·기술·특성 이름
- 영어로 남기지 않는다. 전부 한국어로, 짧고 게임다운 이름으로 짓는다.
- 40K 무기·장비 종류는 팬덤에서 굳어진 음차를 쓴다 (용어집).
- 성인·사람·장소 이름은 음차한다 (Vardeth → 바르데스). "X Pattern" → "X 양식", "Mk. II" → "마크 II".
- "A of B" 꼴은 한국어 어순으로 바꾼다 ("Refractor Field of the Unbroken Oath" → "꺾이지 않는 맹세의 굴절장").
- "Heroic Act: X" 같은 분류 머리말은 용어집대로 붙인다 ("영웅적 행동: X").

## 4. 기술·아이템·특성 설명
- 수치, 조건, 대상, 범위, 지속 시간, 중첩, 횟수를 정확히 옮긴다. 뭉개거나 빼지 않는다.
- 같은 효과는 늘 같은 문장틀로 쓴다: "~을 얻는다", "~이 X 증가한다/감소한다", "다음 턴 시작 시까지", "전투당 1회", "X칸 이내의 아군".
- 게임 용어는 용어집 그대로 쓴다. `{g|…}` 링크 안 글자도 용어집과 같아야 한다.
- 설명문은 "~한다/~된다"로 끝낸다.

## 5. 태그
- `{g|Encyclopedia:X}글자{/g}`: 태그는 그대로 두고 글자만 번역한다.
- `{mf|남|여}`: 구조를 유지하고 둘 다 번역한다. 한국어에서 같아지면 같은 말을 두 번 써도 된다.
- `{name}` 같은 변수와 `[거짓말]` 같은 선택지 머리말의 괄호는 유지한다 (머리말 글자는 번역).

## 6. 용어집

### 세계관
Emperor 황제 · Imperium 제국 · warp 워프 · immaterium 이머티리움 · xenos 제노스 · heretic 이단자 · Chaos 카오스 · daemon 악마 · Inquisitor 이단심문관 · Rogue Trader 로그 트레이더 · Lord Captain 로드 캡틴 · Navigator 항법사 · Seneschal 집사장 · Astropath 아스트로패스 · Geller field 겔러 필드 · voidship 공허선 · void 공허 · void shield 보이드 실드 · Ecclesiarchy 교회청 · Mechanicus 메카니쿠스 · machine spirit 기계령 · Fabricator 파브리케이터 · archeotech 아키오테크 · aquila 아퀼라 · Expanse 확장역 · High Gothic 고딕어 · Low Gothic 저고딕어 · servitor 서비터 · cogitator 코기테이터 · recaff 레카프 · promethium 프로메튬 · Profit Factor 수익 지수 · colony 식민지

### 무기·장비
bolter 볼터 · bolt pistol 볼트 피스톨 · lasgun 라스건 · laspistol 라스피스톨 · autogun 오토건 · stubber 스터버 · shotgun 샷건 · flamer 플레이머 · melta 멜타 · plasma gun 플라스마 건 · inferno pistol 인페르노 피스톨 · chainsword 체인소드 · power sword 파워 소드 · power axe 파워 액스 · thunder hammer 썬더 해머 · lance (함선 무장) 랜스 · carapace armour 카라페이스 아머 · flak armour 플랙 아머 · power armour 파워 아머 · refractor field 굴절장 · frag grenade 파편 수류탄 · krak grenade 크랙 수류탄

### 능력치·전투
Weapon Skill 근접술 · Ballistic Skill 사격술 · Strength 근력 · Toughness 강인함 · Agility 민첩 · Intelligence 지능 · Perception 지각 · Willpower 의지력 · Fellowship 친화력 · Wounds 체력 · Armour 방어도 · Deflection 피해 감소 · Dodge 회피 · Parry 막기 · Cover 엄폐 · Overwatch 경계 사격 · Action Points 행동력 · Movement Points 이동력 · Momentum 기세 · Heroic Act 영웅적 행동 · Desperate Measure 최후의 수단 · Righteous Fury 정의의 분노 · critical hit 치명타 · burst fire 연사 · Veil 장막 · Perils of the Warp 워프의 위험 · psychic 사이킥 · Talent 재능 · Archetype 직업

### 상태
Bleeding 출혈 · Burning 화상 · Toxin 중독 · Pinned 제압 · Stunned 기절 · Prone 넘어짐 · Fear 공포
