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
