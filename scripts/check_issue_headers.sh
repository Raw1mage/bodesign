#!/usr/bin/env bash
# bodesign issue-ledger Status checker — BR_20260804l
#
# WHY: the issues/ Status line had no schema (7 formats across 41 BRs, some on
# line 23+). A header-only sweep reports "no Status" for a BR whose Status is on
# line 23 — the absent state and the out-of-window state render identically. This
# checker resolves that by (a) scanning the FULL file, never a header window, and
# (b) printing its own scan window so a reader can never mistake a narrow view for
# a complete one (BR_20260804l §5 option 3).
#
# TWO LEVELS, mirroring the existing pre-commit hook's warn-never-block ethos:
#   ERROR (rc=1): a BR with ZERO Status-ish line anywhere. This is the real
#                 scheduling hazard — a reader cannot tell if it is open.
#   WARN  (rc=0): a BR that HAS a Status but not as the canonical
#                 `- **Status**:` on line 3. Listed for convergence, never blocks.
#
# CONTROL GROUP IS BUILT IN (BR_20260804l §9): this checker must prove it can go
# red on a real negative before its green means anything. Two permanent fixtures
# in issues/.schema-fixtures/ — one guaranteed-ERROR, one guaranteed-clean — are
# asserted on every run. A checker that has never gone red on real data is
# indistinguishable from a broken one.

set -uo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repo" >&2; exit 2; }
cd "$repo_root" || exit 2

# Canonical: `- **Status**:` on line 3. Anything matching STATUS_ANY_RE ANYWHERE
# in the file counts as "has a Status" (existence). The line-3 + bold form is the
# convergence target, checked separately for the WARN level.
STATUS_ANY_RE='^[-* ]*\**[Ss]tatus\**[:：]'
CANON_RE='^- \*\*Status\*\*[:：]'

scan_one() {  # $1 = file -> prints "ERROR|WARN|OK <file>"
  local f="$1"
  if ! grep -qE "$STATUS_ANY_RE" "$f"; then
    echo "ERROR $f"; return
  fi
  local l3
  l3=$(sed -n '3p' "$f")
  if echo "$l3" | grep -qE "$CANON_RE"; then
    echo "OK $f"
  else
    echo "WARN $f"
  fi
}

run_dir() {  # $1 = dir (relative to repo root)
  local dir="$1"
  local -a files
  mapfile -t files < <(cd "$dir" 2>/dev/null && ls BR_*.md 2>/dev/null)
  local n=${#files[@]}
  local errors=0 warns=0
  local -a err_list=() warn_list=()
  local f verdict
  for f in "${files[@]}"; do
    verdict=$(scan_one "$dir/$f")
    case "$verdict" in
      ERROR\ *) errors=$((errors+1)); err_list+=("$f") ;;
      WARN\ *)  warns=$((warns+1));  warn_list+=("$f") ;;
    esac
  done
  # Window disclosure (BR_20260804l §5 option 3): always state what was scanned.
  printf '[check_issue_headers] scanned %d file(s) in %s, window=full-file\n' "$n" "$dir" >&2
  if [ "$errors" -gt 0 ]; then
    printf '\033[0;31mERROR: %d BR(s) with NO Status line anywhere:\033[0m\n' "$errors" >&2
    for f in "${err_list[@]}"; do printf '  \033[0;31m✗\033[0m %s\n' "$f" >&2; done
  fi
  if [ "$warns" -gt 0 ]; then
    printf '\033[1;33mWARN: %d BR(s) have a Status but not the canonical `- **Status**:` on line 3:\033[0m\n' "$warns" >&2
    for f in "${warn_list[@]}"; do printf '  \033[1;33m~\033[0m %s\n' "$f" >&2; done
  fi
  [ "$errors" -eq 0 ]  # rc: 0 iff no ERRORs
}

self_test() {
  # Control group: the checker must go red on a real negative and green on a
  # real positive, on every run. If either fixture flips, the checker itself is
  # broken and its verdict on live data is worthless.
  local fx="issues/.schema-fixtures"
  local bad="$fx/FIXTURE_no_status_must_ERROR.md"
  local good="$fx/FIXTURE_canonical_status_must_pass.md"
  local fail=0
  if [ ! -f "$bad" ] || [ ! -f "$good" ]; then
    echo "SELF-TEST BROKEN: fixtures missing under $fx" >&2; return 3
  fi
  local vb vg
  vb=$(scan_one "$bad")
  vg=$(scan_one "$good")
  if [[ "$vb" != ERROR\ * ]]; then
    printf '\033[0;31mSELF-TEST FAIL: the no-status fixture did NOT produce ERROR (got: %s)\033[0m\n' "$vb" >&2
    fail=1
  else
    printf '\033[0;32mself-test: no-status fixture -> ERROR (control group has teeth)\033[0m\n' >&2
  fi
  if [[ "$vg" != OK\ * ]]; then
    printf '\033[0;31mSELF-TEST FAIL: the canonical fixture did NOT pass (got: %s)\033[0m\n' "$vg" >&2
    fail=1
  else
    printf '\033[0;32mself-test: canonical fixture -> OK\033[0m\n' >&2
  fi
  return "$fail"
}

case "${1:-}" in
  --self-test)
    self_test
    ;;
  *)
    # Always self-test first: a green run only means something if the control
    # group just proved the checker can still go red.
    if ! self_test; then
      echo "refusing to report on live data — self-test failed above" >&2
      exit 3
    fi
    run_dir "issues"
    ;;
esac
