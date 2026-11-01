#!/usr/bin/env bash
# 용어집·말투표 몫을 아스트라로 한꺼번에 돌린다 (RTKO-13~15). 사용: tools/run_glossary.sh [몫 이름 ...]
set -u
R=${GLOSSARY_RUN:-$(cd "$(dirname "$0")/.." && pwd)/work/glossary_run}
export CODEX_HOME=$HOME/.codex PATH=/home/jaebeom/.nvm/versions/node/v22.22.0/bin:$PATH
cd "$R"
shares=("$@"); [ ${#shares[@]} -eq 0 ] && shares=($(ls -d */ | tr -d /))
for s in "${shares[@]}"; do
  ( cd "$R/$s" && start=$(date +%s)
    codex exec -C "$R/$s" -m gpt-6-astra -c model_reasoning_effort='"medium"' --approve-for-me --skip-git-repo-check \
      --color never --json -o last.md - < brief.md > events.jsonl 2> stderr.log
    st=$(grep -q '"turn.completed"' events.jsonl && echo done || echo FAIL)
    echo "$(date +%T) $s $st $(( $(date +%s) - start ))s $(ls glossary.tsv voices.tsv 2>/dev/null | xargs -r wc -l | tail -1)" >> "$R/log.txt" ) &
  sleep 2
done
wait
echo "ALL DONE"; cat "$R/log.txt"
