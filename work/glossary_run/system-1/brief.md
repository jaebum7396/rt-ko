# 작업: 로그 트레이더 한글패치 용어집 (몫 하나)

`input.tsv`(열: english, count, kinds, example)의 용어마다 한국어 표기를 정해 `glossary.tsv`를 쓴다.

## 출력 — `glossary.tsv` (UTF-8, 첫 줄 머리줄)
`english<TAB>korean<TAB>category<TAB>source<TAB>confidence`
- english: input의 english 그대로, 한 줄에 하나, input의 모든 용어를 빠짐없이
- korean: 정한 표기. 변형이 필요하면 `/`로 (예: `로드 캡틴/캡틴`)
- category: `setting`(세계관·진영·인물·지명·칭호) | `system`(게임 규칙·능력치·상태·UI 용어) | `item`(아이템·무기·장비 이름) | `ability`(기술·재능·직업 이름) | `other`
- source: `namu:<문서 이름>`(나무위키에서 확인) | `community`(국내 공략·커뮤니티) | `style`(아래 이미 정한 표기) | `translit`(커뮤니티 표기가 없어 음차) | `translated`(뜻으로 번역)
- confidence: `high` | `mid` | `low`

## 규칙
- 40K 고유 용어·인명·지명·진영·칭호는 국내 커뮤니티(나무위키) 표기를 따른다. `Warhammer 40,000: Rogue Trader` 문서와 하위 문서(등장인물 등), 워해머 40K 설정 문서를 먼저 찾는다. 새로 지어내지 않는다.
- 아래 "이미 정한 표기"는 바꾸지 않는다.
- 게임 시스템 용어는 한국 게임에서 흔히 쓰는 짧은 말로, 같은 개념은 같은 말로.
- 아이템·기술 이름은 영어로 남기지 않고 짧고 게임다운 한국어로 (사람·장소 이름은 음차).
- 검색은 여러 용어를 묶어서 하고, 이미 아는 표준 표기는 검색하지 않는다.
- 스크립트를 쓰지 않는다. 다 쓰면 `DONE <줄 수>`만 답한다.


## 이미 정한 표기 (바꾸지 말 것)

## 6. 용어집
- 40K 고유 용어는 국내 커뮤니티(나무위키 등)에서 굳어진 표기를 따른다. 새로 지어내지 않는다 (예: 하이 고딕·로우 고딕, 고딕어·저고딕어 X).
- 커뮤니티 표기 조사는 용어집을 만들 때 미리 끝낸다. **번역할 때는 웹 검색을 하지 않는다.** 용어집에 없는 고유 용어는 음차하고 넘어간다 (나중에 검사에서 모아 고친다).
- ✓ = 나무위키 로그 트레이더 문서에서 확인한 표기. ✓ 없는 것은 잠정이고, 원본을 받으면 게임 백과사전 용어를 전부 뽑아 커뮤니티 표기로 한 번에 맞춘다.

### 세계관
Emperor 황제 · God-Emperor 신황제 · Imperium 제국 · warp 워프 · immaterium 이머티리움 · xenos 제노스✓ · heretic 이단자 · Chaos 카오스✓ · daemon 데몬✓ · psyker 사이커✓ · Inquisitor 이단심문관✓ · Rogue Trader 로그 트레이더✓ · Lord Captain 로드 캡틴 · Warrant of Trade 무역의 영장✓ · Navigator 내비게이터✓ · Navis Nobilite 나비스 노빌리테✓ · Novator 노베이터✓ · Seneschal 집사장✓ · Astropath 아스트로패스✓ · Tech-Priest 테크 프리스트✓ · Sister of Battle 전투 수녀✓ · Adepta Sororitas 아뎁타 소로리타스 · Ecclesiarchy 에클레시아키 · Ministorum 미니스토룸✓ · Imperial Creed 제국교✓ · Adeptus Mechanicus 아뎁투스 메카니쿠스✓ · Arbites 아르비테스✓ · Space Marine 스페이스 마린✓ · Space Wolves 스페이스 울프✓ · Aeldari 엘다리✓ · Drukhari 드루카리✓ · Koronus Expanse 코로누스 공역✓ · Footfall 풋폴✓ · Dargonus 다르고누스✓ · Rykad 리카드✓ · Geller field 겔러 필드 · voidship 공허선✓ · void 공허 · void shield 보이드 실드 · machine spirit 기계령 · Fabricator 파브리케이터 · archeotech 아키오테크 · aquila 아퀼라 · High Gothic 하이 고딕 · Low Gothic 로우 고딕 · servitor 서비터 · cogitator 코기테이터 · recaff 레카프 · promethium 프로메튬 · Profit Factor 수익 지수 · colony 식민지

### 동료 이름 ✓
Abelard Werserian 아벨라드 버세리안 · Argenta 아젠타 (호칭 포함: 시스터 아젠타) · Cassia Orsellio 카시아 오셀리오 · Heinrix van Calox 헤인릭스 반 칼록스 · Idira Tlass 이디라 틀라스 · Jae Heydari 자이 헤이다리 · Pasqal Haneumann 파스칼 하네이만 · Marazhai 마라자이 · Yrliet 이를리엣 · Ulfar 울파르 · Kibellah 키벨라

### 무기·장비
bolter 볼터 · bolt pistol 볼트 피스톨 · lasgun 라스건 · laspistol 라스피스톨 · autogun 오토건 · stubber 스터버 · shotgun 샷건 · flamer 플레이머 · melta 멜타 · plasma gun 플라스마 건 · inferno pistol 인페르노 피스톨 · chainsword 체인소드 · power sword 파워 소드 · power axe 파워 액스 · thunder hammer 썬더 해머 · lance (함선 무장) 랜스 · carapace armour 카라페이스 아머 · flak armour 플랙 아머 · power armour 파워 아머 · refractor field 굴절장 · frag grenade 파편 수류탄 · krak grenade 크랙 수류탄

### 능력치·전투
Weapon Skill 근접술 · Ballistic Skill 사격술 · Strength 근력 · Toughness 강인함 · Agility 민첩 · Intelligence 지능 · Perception 지각 · Willpower 의지력 · Fellowship 친화력 · Wounds 체력 · Armour 방어도 · Deflection 피해 감소 · Dodge 회피 · Parry 막기 · Cover 엄폐 · Overwatch 경계 사격 · Action Points 행동력 · Movement Points 이동력 · Momentum 원동력✓ · Heroic Act 영웅적 행동✓ · Desperate Measure 필사의 결단✓ · Righteous Fury 정의의 분노 · critical hit 치명타 · burst fire 연사 · Veil 베일✓ · Veil Degradation 베일 손상✓ · Perils of the Warp 페릴 오브 더 워프✓ · psychic 사이킥 · Talent 재능 · Archetype 아키타입✓ · Warrior 워리어✓ · Officer 오피서✓ · Operative 오퍼러티브✓ · Soldier 솔져✓ · Origin 오리진✓ · Homeworld 홈월드✓

### 상태
Bleeding 출혈 · Burning 화상 · Toxin 중독 · Pinned 제압 · Stunned 기절 · Prone 넘어짐 · Fear 공포
