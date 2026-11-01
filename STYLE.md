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
- 듣는 사람에 따라 높임을 바꾼다. 적·괴물·하인에게 하는 말은 낮춘다 ("불타라, 이단자여!").
- 전투 중 짧은 외침(bark)은 대부분 적에게 하는 말이다. 평소 존댓말을 쓰는 인물도 적에게는 낮춘다.
- **아스타르테스(스페이스 마린·카오스 스페이스 마린)는 필멸자에게 존댓말을 쓰지 않는다.** 인정하는 필멸자(로그 트레이더 등)에게는 하게체("자네"), 낮잡거나 화날 때는 해라체("필멸자여"), 형제 아스타르테스에게는 반말. 원문이 특별한 존중(필멸자에게 고개를 숙이는 장면 등)을 분명히 보일 때만 그 줄에서 높인다.
- **제국 의전:** 아뎁타 소로리타스(시스터)에게는 누구든 존대하고 "시스터"라 부른다. 신하·가신은 하십시오체, 평소 해요체·반말인 동료(카시아·이디라·자이)는 해요체, 로그 트레이더는 자기 말투인 하오체. 이단심문관, 내비게이터 가문 귀족, 테크 프리스트처럼 제국 기관에 속한 인물에게도 필멸자 신하·가신은 존대한다.
- 인물 말투표의 높임이 먼저다. 로그 트레이더는 누구에게나 하오체(적·하인에게 해라체), 자이는 동료와 로그 트레이더에게 반말이다. 검수에서도 이것을 하십시오체로 올리지 않는다.

| 화자 | 말투 |
|---|---|
| SENESCHAL (집사장) | 깍듯한 하십시오체. 플레이어를 "로드 캡틴" 또는 "주군"으로 부른다 |
| TECHPRIEST (테크 프리스트) | 건조하고 기계적인 하십시오체 |
| SISTER (전투 수녀) | 열성적인 하십시오체. 적에게는 해라체 |
| NAVIGATOR (내비게이터) | 귀족적이고 비꼬는 해요체 |
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
- 수치, 조건, 대상, 범위, 지속 시간, 중첩, 횟수를 정확히 옮긴다. 뭉개거나 빼지 않는다. 지속 시간이 어느 효과에 걸리는지 원문 그대로 둔다.
- 같은 효과는 늘 같은 문장틀로 쓴다: "~을 얻습니다", "~이 X 증가합니다/감소합니다", "다음 턴 시작 시까지", "전투당 1회", "X칸 이내의 아군".
- 게임 용어는 용어집 그대로 쓴다. `{g|…}` 링크 안 글자도 용어집과 같아야 한다.
- **게임 설명과 UI는 존댓말(합쇼체)로 쓴다.** 아이템·기술·특성·상태 설명, 백과사전, 튜토리얼, 설정, 확인 창, 안내 문구 전부: "~합니다", "~됩니다", "~입니다", 질문은 "~하시겠습니까?", 안내는 "~하십시오"/"~하세요". 이야기 서술(대사 속 `{n}`, 이벤트 서술)만 해라체.
- **번역체 금지:** 영어 구조를 그대로 옮기지 말고 한국 게임에서 쓰는 말로 다시 쓴다.
  - "Choosing this difficulty is not recommended for players not familiar with Rogue Trader's system as well as its implementation in this game. Do you confirm your choice?" → (X) 로그 트레이더의 시스템과 이 게임에서의 구현 방식에 익숙하지 않은 플레이어에게는 이 난이도를 권장하지 않는다. 이 난이도를 선택할까? → (O) 로그 트레이더 규칙과 이 게임의 방식에 익숙하지 않다면 추천하지 않습니다. 이 난이도로 시작하시겠습니까?
  - "~에서의", "~에 있어서", "~하는 것은 ~이다", "~에 의해", 불필요한 "그/그녀/당신의"를 피한다.

## 5. 태그
- `{g|Encyclopedia:X}글자{/g}`, `{d|X}글자{/d}`: 태그는 그대로 두고 글자만 번역한다.
- `{n}글자{/n}`: 대사 속 서술(행동·모습 묘사)이다. 태그는 그대로 두고, 안은 서술체(해라체)로 옮긴다. 따옴표 안 대사만 화자 말투를 따른다.
- `{mf|남|여}`, `{rt_mf|남|여}`, `{nc|a|b}`: 구조를 유지하고 두 칸 다 번역한다 (`rt_mf`는 로그 트레이더의 성별). 한국어에서 같아지면 같은 말을 두 번 써도 된다.
- `{name}`, `{rt_name}`, `{uip|…}`, `{unit_stat|…}`, `{bind|…}`, `{br}` 같은 나머지 `{…}`와 `<b>`·`<i>` 같은 HTML 태그는 한 글자도 바꾸지 않는다.
- `[거짓말]` 같은 선택지 머리말은 괄호를 유지하고 글자만 번역한다.
- 입력의 `\n`(줄바꿈)은 같은 자리에 같은 개수로 둔다.

## 6. 용어집
- 40K 고유 용어는 국내 커뮤니티(나무위키 등)에서 굳어진 표기를 따른다. 새로 지어내지 않는다 (예: 하이 고딕·로우 고딕, 고딕어·저고딕어 X).
- 커뮤니티 표기 조사는 용어집을 만들 때 미리 끝낸다. **번역할 때는 웹 검색을 하지 않는다.** 용어집에 없는 고유 용어는 음차하고 넘어간다 (나중에 검사에서 모아 고친다).
- ✓ = 나무위키 로그 트레이더 문서에서 확인한 표기. ✓ 없는 것은 잠정이고, 원본을 받으면 게임 백과사전 용어를 전부 뽑아 커뮤니티 표기로 한 번에 맞춘다.

### 세계관
Emperor 황제 · God-Emperor 신황제 · Imperium 제국 · warp 워프 · immaterium 이머티리움 · xenos 제노스✓ · heretic 이단자 · Chaos 카오스✓ · daemon 데몬✓ · psyker 사이커✓ · Inquisitor 이단심문관✓ · Rogue Trader 로그 트레이더✓ · Lord Captain 로드 캡틴 · Warrant of Trade 무역 영장 · Navigator 내비게이터✓ · Navis Nobilite 나비스 노빌리테✓ · Novator 노베이터✓ · Seneschal 집사장✓ · Astropath 아스트로패스✓ · Tech-Priest 테크 프리스트✓ · Sister of Battle 전투 수녀✓ · Adepta Sororitas 아뎁타 소로리타스 · Ecclesiarchy 에클레시아키 · Ministorum 미니스토룸✓ · Imperial Creed 제국교✓ · Adeptus Mechanicus 아뎁투스 메카니쿠스✓ · Arbites 아르비테스✓ · Space Marine 스페이스 마린✓ · Space Wolves 스페이스 울프✓ · Aeldari 엘다리✓ · Drukhari 드루카리✓ · Koronus Expanse 코로누스 공역✓ · Footfall 풋폴✓ · Dargonus 다르고누스✓ · Rykad 리카드✓ · Geller field 겔러 필드 · voidship 공허선✓ · void 공허 · void shield 보이드 실드 · machine spirit 기계령 · Fabricator 패브리케이터 · archeotech 아키오테크 · aquila 아퀼라 · High Gothic 하이 고딕 · Low Gothic 로우 고딕 · servitor 서비터 · cogitator 코기테이터 · recaff 레카프 · promethium 프로메튬 · Profit Factor 수익 지수 · colony 식민지

### 동료 이름 ✓
Abelard Werserian 아벨라드 버세리안 · Argenta 아젠타 (호칭 포함: 시스터 아젠타) · Cassia Orsellio 카시아 오셀리오 · Heinrix van Calox 헤인릭스 반 칼록스 · Idira Tlass 이디라 틀라스 · Jae Heydari 자이 헤이다리 · Pasqal Haneumann 파스칼 하네이만 · Marazhai 마라자이 · Yrliet 이를리엣 · Ulfar 울파르 · Kibellah 키벨라

### 무기·장비
bolter 볼터 · bolt pistol 볼트 피스톨 · lasgun 라스건 · laspistol 라스피스톨 · autogun 오토건 · stubber 스터버 · shotgun 샷건 · flamer 플레이머 · melta 멜타 · plasma gun 플라스마 건 · inferno pistol 인페르노 피스톨 · chainsword 체인소드 · power sword 파워 소드 · power axe 파워 액스 · thunder hammer 썬더 해머 · lance (함선 무장) 랜스 · carapace armour 카라페이스 아머 · flak armour 플랙 아머 · power armour 파워 아머 · refractor field 굴절장 · frag grenade 파편 수류탄 · krak grenade 크랙 수류탄

### 능력치·전투
Weapon Skill 근접술 · Ballistic Skill 사격술 · Strength 근력 · Toughness 강인함 · Agility 민첩 · Intelligence 지능 · Perception 지각 · Willpower 의지력 · Fellowship 친화력 · Wounds 체력 · Armour 방어도 · Deflection 피해 감소 · Dodge 회피 · Parry 막기 · Cover 엄폐 · Overwatch 경계 사격 · Action Points 행동력 · Movement Points 이동력 · Momentum 원동력✓ · Heroic Act 영웅적 행동✓ · Desperate Measure 필사의 결단✓ · Righteous Fury 정의의 분노 · critical hit 치명타 · burst fire 연사 · Veil 베일✓ · Veil Degradation 베일 손상✓ · Perils of the Warp 페릴 오브 더 워프✓ · psychic 사이킥 · Talent 재능 · Archetype 아키타입✓ · Warrior 워리어✓ · Officer 오피서✓ · Operative 오퍼러티브✓ · Soldier 솔져✓ · Origin 기원 · Homeworld 홈월드✓

### 상태
Bleeding 출혈 · Burning 화상 · Toxin 중독 · Pinned 제압 · Stunned 기절 · Prone 넘어짐 · Fear 공포
