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
#
# SECOND CHECK — BR ID UNIQUENESS (added 2026-08-31):
# Two BRs filed under the same identifier (e.g. two files both claiming
# BR_20260805h) make every later cross-reference ambiguous: "see BR_20260805h"
# resolves to two different defects and nothing says so. The ledger's own
# convention decides the unit of uniqueness, and it is NOT the bare date:
# measured on this tree (2026-08-31, issues/ + issues/closed/, 102 BR files),
# 12 bare-date ids are shared by 2..20 files each (BR_20260802 alone has 20) and
# ZERO suffixed ids collide. A bare date is therefore a same-day FAMILY, not a
# collision; a suffixed id is a unique handle. So:
#   ERROR (rc=1): the same SUFFIXED id (BR_YYYYMMDD[a-z]) on 2+ files.
#   WARN  (rc=0): a bare BR_YYYYMMDD shared by 2+ files — the pre-existing
#                 convention, listed for visibility, never blocks.
# Scope note: the dup scan covers issues/ AND issues/closed/, because reusing the
# id of an ARCHIVED BR is exactly the collision that is easy to make and hard to
# see. The Status scan keeps its original scope (issues/ only) — the two checks
# answer different questions and their windows are disclosed separately.

set -uo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repo" >&2; exit 2; }
cd "$repo_root" || exit 2

# Directories that hold the real ledger. The fixture tree is deliberately NOT
# here; self_test asserts that no fixture id can leak into a live report.
LIVE_DUP_DIRS=(issues issues/closed)

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

# ---------------------------------------------------------------------------
# BR ID uniqueness
# ---------------------------------------------------------------------------

# Emit "<id>\t<path>" for every *.md directly under the given dirs. A file whose
# NAME carries no BR id (README.md, OWNERS.md, KB_*, issue_*, HANDOVER_*) is
# emitted as "<NO-ID>" rather than dropped, so "no ids found" and "no files
# found" can never render as the same thing.
dup_pairs() {  # $@ = dirs
  local dir f base
  for dir in "$@"; do
    [ -d "$dir" ] || continue
    for f in "$dir"/*.md; do
      [ -e "$f" ] || continue
      base="${f##*/}"
      if [[ "$base" =~ ^(BR_[0-9]{8}[a-z]?)_ ]]; then
        printf '%s\t%s\n' "${BASH_REMATCH[1]}" "$f"
      else
        printf '%s\t%s\n' "<NO-ID>" "$f"
      fi
    done
  done
}

# rc: 0 iff no SUFFIXED id is claimed by 2+ files. Bare-date sharing is the
# ledger's same-day family convention -> WARN only (see header note).
run_dup_check() {  # $@ = dirs
  local -a pairs=()
  mapfile -t pairs < <(dup_pairs "$@")
  local -A files_of=()
  local total=0 noid=0 idful=0 p id path
  for p in "${pairs[@]}"; do
    id="${p%%$'\t'*}"; path="${p#*$'\t'}"
    total=$((total+1))
    if [ "$id" = "<NO-ID>" ]; then noid=$((noid+1)); continue; fi
    idful=$((idful+1))
    files_of["$id"]+="${path}"$'\n'
  done
  local collisions=0 families=0
  local -a coll_report=() fam_report=()
  local k n last
  for k in "${!files_of[@]}"; do
    n=$(printf '%s' "${files_of[$k]}" | grep -c .)
    [ "$n" -gt 1 ] || continue
    last="${k: -1}"
    if [[ "$last" =~ [a-z] ]]; then
      collisions=$((collisions+1))
      coll_report+=("$k|${files_of[$k]}")
    else
      families=$((families+1))
      fam_report+=("$k|$n")
    fi
  done
  # Window disclosure: state the scan scope AND the population, so a zero can be
  # read as "checked and clean" rather than "never looked".
  printf '[check_issue_headers] dup-scan: %d file(s) across [%s], %d with a BR id, %d without, %d distinct id(s)\n' \
    "$total" "$*" "$idful" "$noid" "${#files_of[@]}" >&2
  if [ "$collisions" -gt 0 ]; then
    printf '\033[0;31mERROR: %d duplicate BR ID(s) — the same suffixed id claimed by 2+ files:\033[0m\n' "$collisions" >&2
    local entry kk body line
    for entry in "${coll_report[@]}"; do
      kk="${entry%%|*}"; body="${entry#*|}"
      printf '  \033[0;31m✗\033[0m %s claimed by:\n' "$kk" >&2
      while IFS= read -r line; do
        [ -n "$line" ] && printf '      %s\n' "$line" >&2
      done <<< "$body"
    done
  fi
  if [ "$families" -gt 0 ]; then
    printf '\033[1;33mWARN: %d bare-date BR id(s) shared by multiple files (same-day family, not a collision):\033[0m\n' "$families" >&2
    local fentry
    for fentry in "${fam_report[@]}"; do
      printf '  \033[1;33m~\033[0m %s x%s\n' "${fentry%%|*}" "${fentry#*|}" >&2
    done
  fi
  [ "$collisions" -eq 0 ]
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

  # --- dup check control group -------------------------------------------
  # Negative: the fixture dir holds two files claiming BR_29991231z. The dup
  # check MUST go red on it. Positive: a dir with the same files minus one of
  # the twins MUST go green — that pair is what separates "the check works"
  # from "the check always reports red" and from "the check never looked".
  local a="$fx/BR_29991231z_FIXTURE_duplicate_id_must_ERROR_a.md"
  local b="$fx/BR_29991231z_FIXTURE_duplicate_id_must_ERROR_b.md"
  if [ ! -f "$a" ] || [ ! -f "$b" ]; then
    printf '\033[0;31mSELF-TEST BROKEN: duplicate-id fixtures missing under %s\033[0m\n' "$fx" >&2
    return 3
  fi
  local dout drc
  dout=$(run_dup_check "$fx" 2>&1)
  drc=$?
  if [ "$drc" -eq 0 ]; then
    printf '\033[0;31mSELF-TEST FAIL: dup fixtures did NOT trip the dup check (rc=0)\033[0m\n' "$drc" >&2
    fail=1
  elif ! printf '%s' "$dout" | grep -q 'BR_29991231z'; then
    printf '\033[0;31mSELF-TEST FAIL: dup check went red but did not NAME the colliding id\033[0m\n' >&2
    fail=1
  else
    printf '\033[0;32mself-test: duplicate-id fixtures -> ERROR naming BR_29991231z (rc=%d, control group has teeth)\033[0m\n' "$drc" >&2
  fi
  # Positive control: same checker, one twin removed -> must be green. Built in
  # $XDG_RUNTIME_DIR (never /tmp) and removed unconditionally.
  local scratch
  scratch=$(mktemp -d "${XDG_RUNTIME_DIR:-$HOME/.cache}/check_issue_headers.XXXXXX") || {
    printf '\033[0;31mSELF-TEST BROKEN: cannot create scratch dir\033[0m\n' >&2; return 3; }
  cp "$a" "$good" "$bad" "$scratch/" 2>/dev/null
  local pout prc
  pout=$(run_dup_check "$scratch" 2>&1)
  prc=$?
  rm -rf "$scratch"
  if [ "$prc" -ne 0 ]; then
    printf '\033[0;31mSELF-TEST FAIL: dup check went red on a collision-free dir (rc=%d)\033[0m\n' "$prc" >&2
    printf '%s\n' "$pout" >&2
    fail=1
  else
    printf '\033[0;32mself-test: collision-free dir -> clean (rc=0, check is not stuck red)\033[0m\n' >&2
  fi
  # Leak guard: the fixture id must never appear in a live-tree report.
  local lout
  lout=$(run_dup_check "${LIVE_DUP_DIRS[@]}" 2>&1)
  if printf '%s' "$lout" | grep -q 'BR_29991231z'; then
    printf '\033[0;31mSELF-TEST FAIL: fixture id BR_29991231z leaked into the live-tree scan\033[0m\n' >&2
    fail=1
  else
    printf '\033[0;32mself-test: fixture ids do not leak into the live scan\033[0m\n' >&2
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
    status_rc=0; dup_rc=0
    run_dir "issues" || status_rc=$?
    run_dup_check "${LIVE_DUP_DIRS[@]}" || dup_rc=$?
    # Both checks always run and always report; neither short-circuits the
    # other, so a failure in one can never hide the other's verdict.
    printf '[check_issue_headers] status_check_rc=%d dup_check_rc=%d\n' "$status_rc" "$dup_rc" >&2
    [ "$status_rc" -eq 0 ] && [ "$dup_rc" -eq 0 ]
    ;;
esac
