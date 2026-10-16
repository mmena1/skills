#!/bin/bash
# Usage: run_probe.sh <run-root> <agent-project> <invocation-id>
set -uo pipefail
R=$1; A=$2; ID=$3; WT=$R/review-wt
SID=$(python3 -c 'import uuid; print(uuid.uuid4())')
echo "$SID" > "$R/evidence/$ID-session-id"
date -u +%FT%TZ > "$R/evidence/$ID-started"
cd "$A"
timeout 2400 claude -p "$(cat "$R/evidence/prompts/$ID.txt")" \
  --agent deep-review-validator-probe --setting-sources project,local \
  --output-format stream-json --verbose --session-id "$SID" \
  --allowedTools "Read" "Grep" "Glob" "Bash" "Edit(/$WT/**)" "Write(/$WT/**)" \
  > "$R/evidence/$ID-events.jsonl" 2> "$R/evidence/$ID-stderr.log"
echo $? > "$R/evidence/$ID-exit"
date -u +%FT%TZ > "$R/evidence/$ID-finished"
