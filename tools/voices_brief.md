# 작업: 로그 트레이더 한글패치 화자 말투표

`input.tsv`(열: speaker, gender, lines, sample)는 화자별 영어 대사 예문이다. 화자마다 한국어 말투를 정해 `voices.tsv`를 쓴다.

## 출력 — `voices.tsv` (UTF-8, 첫 줄 머리줄)
`speaker<TAB>voice<TAB>example_en<TAB>example_ko`
- speaker: input의 speaker 그대로, 화자마다 한 줄, 빠짐없이
- voice: 한 줄로 — 기본 말투(하십시오체·하오체·해요체·반말·하게체 중 하나와 어울리는 상황), 로그 트레이더를 부르는 호칭, 성격과 어휘 특징 (예: `깍듯한 하십시오체 · 호칭 "로드 캡틴"/"주군" · 노장다운 절제, 의전 용어를 즐겨 씀`)
- example_en / example_ko: 그 화자다운 예문 하나와 그 말투로 옮긴 한국어 (아래 STYLE.md 원칙대로)

## 규칙
- 예문과 게임 속 인물 설정(필요하면 나무위키 `Warhammer 40,000: Rogue Trader/등장인물` 문서)을 근거로 정한다. 인물 이름 표기는 아래 STYLE.md 용어집을 따른다.
- 같은 인물이라도 상대(적·하인·상관)에 따라 높임이 달라지면 voice에 적는다.
- PLAYER는 로그 트레이더(플레이어 선택지)다. STYLE.md 표의 PLAYER 말투를 기준으로 다듬는다.
- 스크립트를 쓰지 않는다. 다 쓰면 `DONE <줄 수>`만 답한다.
