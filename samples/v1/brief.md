# Task: Korean translation (measurement run, keep it lean)

Translate `source.tsv` (columns: id, speaker, English) into Korean for a Warhammer 40,000 CRPG fan patch.

Output: write `out.tsv` — one line per id, same order: `id<TAB>Korean`. No other files, no scripts, no self-check runs. When done, reply only `DONE <line count>`.

Rules
- Keep every `{...}` tag exactly. `{g|Encyclopedia:X}text{/g}`: keep the tag, translate only `text`. `{mf|A|B}`: keep the structure, translate A and B. Keep `[Lie]`-style prefixes translated in brackets, e.g. `[거짓말]`.
- Voice by speaker: SENESCHAL = 깍듯한 하십시오체, player is "로드 캡틴" or "주군". TECHPRIEST = 건조한 하십시오체, 기계적. SISTER = 열성적인 하십시오체. NAVIGATOR = 귀족적인 해요체, 비꼬는 말투. SMUGGLER = 능글맞은 반말, player is "보스". PLAYER = 위엄 있는 하오체 (예: 보고하시오). NARRATOR = 문어체 해라체. ITEM/ABILITY/GLOSSARY/QUEST = 게임 설명문(~한다/~이다). UI = 짧은 UI 문구.
- Glossary: Emperor 황제, Imperium 제국, warp 워프, immaterium 이머티리움, xenos 제노스, heretic 이단자, Inquisitor 이단심문관, Rogue Trader 로그 트레이더, Navigator 항법사, Seneschal 집사장, Geller field 겔러 필드, voidship 공허선, void 공허, Ecclesiarchy 교회청, Mechanicus 메카니쿠스, machine spirit 기계령, Fabricator 파브리케이터, archeotech 아키오테크, aquila 아퀼라, Expanse 확장역, Momentum 기세, Profit Factor 수익 지수, High/Low Gothic 고딕어/저고딕어, servitor 서비터, cogitator 코기테이터, recaff 레카프, lasgun 라스건, bolter 볼터, promethium 프로메튬.
