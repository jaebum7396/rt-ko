# rt-ko — 로그 트레이더 한글패치

Warhammer 40,000: Rogue Trader 번역기 한글패치를 대신할 한글패치. 개인 프로젝트, **비공개 유지** (번역문은 게임 텍스트 파생물).

- 작업 관리: Plane RTKO — https://plane.codism.co.kr/jay-trader/projects/23f0a096-6c97-449f-b796-c2c097fee955/issues
- 번역 원칙·말투표·용어집: [STYLE.md](STYLE.md)
- 번역: 아스트라(gpt-6-astra, 생각 단계 medium) / 도구·관제·검수: Claude

## 폴더
| 경로 | 내용 |
|---|---|
| `STYLE.md` | 번역 원칙 정본 |
| `samples/` | 예문 시험 (직접 쓴 40K 풍 예문, 게임 텍스트 아님) |
| `docs/` | 원본 형식·파이프라인 규격 (RTKO-8) |
| `tools/` | 추출·검사·묶기·실행기 (RTKO-9~12) |
| `glossary/` | 용어집·말투표 (RTKO-13~15) |
| `src/` | 게임 원본·참고 패치 링크 — git 제외 |

## 원본
- 게임: 서버 `/data2/rt-ko/game` (SteamCMD, `+@sSteamCmdForcePlatformType windows +login jaebum7396 +app_update 2186680` — 업데이트도 같은 명령)
- 참고 패치: `/data2/rt-ko/ref/korean-patch` (geungogma/RogueTrader-KoreanPatch — 글꼴 모드만 재사용)
