#!/usr/bin/env bash
# scripts/run_tests.sh — the explicit, discoverable entry point for this repo's
# test suite.  See BR_20260831a (family G13-harness-disclosure).
#
# WHY THIS SCRIPT EXISTS
# ----------------------
# `tests/__init__.py` is the *mechanism* layer: it puts `packages/*/` on
# sys.path for anyone who imports `tests.<module>`, so the direct
# `python3 -m unittest tests.foo` call now works with no environment setup.
# This script is the *explicit* layer on top of it. It adds three things the
# bare interpreter call cannot do for you:
#
#   1. clears `__pycache__` first — `python3 -B` does NOT stop an already
#      existing stale `.pyc` from being loaded (AGENTS.md §6.3);
#   2. enumerates the test modules explicitly, because
#      `unittest discover -s tests` has its own absence/failure ambiguity in
#      this repo (see DISCOVERY NOTE below);
#   3. `--self-test` — a control group proving this script goes red when it
#      should, instead of asking you to trust that it would.
#
# USAGE
#   scripts/run_tests.sh                      # whole suite
#   scripts/run_tests.sh tests.test_layout    # one or more modules
#   scripts/run_tests.sh test_layout          # `tests.` prefix is optional
#   scripts/run_tests.sh --self-test          # run this script's own controls
#   scripts/run_tests.sh --list               # print the module list, run nothing
#
# READING THE OUTPUT — the one thing worth knowing
#   The discriminating field is N in `Ran N tests`, NOT the exit code.
#   `Ran 1 test / FAILED (errors=1) / rc=1` is what you get when a module
#   failed to IMPORT — identical in every visible respect to what you get when
#   the module does not exist. A real regression shows the full N with
#   `failures=`. Always read N before concluding anything from rc.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="${PYTHON:-python3}"

clear_pycache() {
  # AGENTS.md §6.3: -B prevents WRITING bytecode; it does not prevent READING
  # an existing stale .pyc. Only removal treats the case that already exists.
  find "$REPO_ROOT" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
  return 0
}

# DISCOVERY NOTE
#   `python3 -m unittest discover -s tests` historically raised
#   "ImportError: Start directory is not importable" in this repo, and a
#   zero-test discovery looks exactly like a clean run. We therefore enumerate
#   the modules from the filesystem and pass them explicitly: if the glob ever
#   yields nothing, list_modules() fails loudly instead of running zero tests
#   and reporting OK.
list_modules() {
  local mods=()
  local f base
  for f in "$REPO_ROOT"/tests/test_*.py; do
    [ -e "$f" ] || continue
    base="$(basename "$f" .py)"
    mods+=("tests.$base")
  done
  if [ "${#mods[@]}" -eq 0 ]; then
    echo "run_tests.sh: FATAL — no tests/test_*.py found under $REPO_ROOT/tests" >&2
    return 1
  fi
  printf '%s\n' "${mods[@]}"
}

# Normalise a user-supplied argument: `test_layout` and `tests.test_layout`
# both resolve to `tests.test_layout`.
normalise_module() {
  case "$1" in
    tests.*) printf '%s\n' "$1" ;;
    *)       printf 'tests.%s\n' "$1" ;;
  esac
}

# ---------------------------------------------------------------------------
# --self-test : control groups for THIS script and for the bootstrap it relies
# on. Each case states the question it answers and what the answer must be.
# A check that cannot fail is not a check, so every "must pass" cell is paired
# with a "must fail" cell exercising the same machinery.
# ---------------------------------------------------------------------------
self_test() {
  local fails=0
  local out rc n got ok

  # _check <name> <expectation-text> <observed-text> <ok:0|1>
  #
  # The verdict is the CALLER's boolean, never a string comparison between
  # the expectation and the observation. An earlier draft of this function
  # compared those two strings and reported PASS/FAIL from that; it printed
  # FAIL for `expected="rc=0 n>=2"` vs `got="rc=0 n=5"` — a correct result
  # rendered as a failure. Expectation text is for the human reading the
  # transcript; it is not the predicate.
  _check() {
    if [ "$4" -eq 0 ]; then
      printf 'PASS  %-52s expect[%s] got[%s]\n' "$1" "$2" "$3"
    else
      printf 'FAIL  %-52s expect[%s] got[%s]\n' "$1" "$2" "$3"
      fails=$((fails + 1))
    fi
  }

  clear_pycache

  # -- 1. Q: does the bootstrap make a real module importable with NO
  #         PYTHONPATH set at all?  (positive control)
  out="$(env -u PYTHONPATH "$PY" -m unittest tests.test_fidelity_gate 2>&1)"
  rc=$?
  n="$(printf '%s\n' "$out" | sed -n 's/^Ran \([0-9]*\) test.*/\1/p')"
  ok=1
  case "$n" in
    ''|*[!0-9]*) ok=1 ;;
    *) [ "$rc" -eq 0 ] && [ "$n" -ge 2 ] && ok=0 ;;
  esac
  _check "bootstrap makes tests.test_fidelity_gate importable" "rc=0 n>=2" \
         "rc=$rc n=$n" "$ok"

  # -- 2. Q: with the bootstrap DISABLED, does that same module fail to
  #         import?  (reverse control — proves cell 1 measured the bootstrap
  #         and not some other path provider such as an inherited PYTHONPATH,
  #         a .pth file, or an installed distribution)
  clear_pycache
  out="$(env -u PYTHONPATH BODESIGN_TEST_BOOTSTRAP=0 \
         "$PY" -m unittest tests.test_fidelity_gate 2>&1)"
  rc=$?
  ok=1
  case "$out" in
    *ModuleNotFoundError*) got="rc=$rc ModuleNotFoundError=yes"
                           [ "$rc" -ne 0 ] && ok=0 ;;
    *)                     got="rc=$rc ModuleNotFoundError=no" ;;
  esac
  _check "bootstrap disabled => module is NOT importable" \
         "rc!=0 ModuleNotFoundError=yes" "$got" "$ok"

  # -- 3. Q: does the runner go non-zero for a module that does not exist?
  #         (negative control for the runner itself; note N=1 here, which is
  #         exactly the ambiguity BR_20260831a is about)
  out="$(env -u PYTHONPATH "$PY" -m unittest \
         tests.test_NON_EXISTENT_MODULE_CONTROL 2>&1)"
  rc=$?
  n="$(printf '%s\n' "$out" | sed -n 's/^Ran \([0-9]*\) test.*/\1/p')"
  ok=1
  [ "$rc" -ne 0 ] && [ "$n" = "1" ] && ok=0
  _check "nonexistent module => non-zero exit, N=1" "rc!=0 n=1" \
         "rc=$rc n=$n" "$ok"

  # -- 4. Q: does THIS SCRIPT propagate a failure, i.e. can it go red at all?
  #         Without this cell, cells 1-3 could all be green while the script
  #         always exits 0.
  ( "$0" tests.test_NON_EXISTENT_MODULE_CONTROL ) >/dev/null 2>&1
  rc=$?
  ok=1
  [ "$rc" -ne 0 ] && ok=0
  _check "run_tests.sh exits non-zero on a failing module" "rc!=0" \
         "rc=$rc" "$ok"

  # -- 4b. Q: and does it exit ZERO for a module that passes? Paired with 4:
  #          a script that always exits non-zero would satisfy 4 alone.
  ( "$0" tests.test_fidelity_gate ) >/dev/null 2>&1
  rc=$?
  ok=1
  [ "$rc" -eq 0 ] && ok=0
  _check "run_tests.sh exits zero on a passing module" "rc=0" "rc=$rc" "$ok"

  # -- 5. Q: does the bootstrap actually record what it injected? (guards
  #         against a no-op bootstrap that silently adds nothing)
  out="$(env -u PYTHONPATH "$PY" -c \
        'import tests; print(len(tests.BOOTSTRAPPED_PATHS))' 2>&1)"
  rc=$?
  ok=1
  case "$out" in
    ''|*[!0-9]*) ok=1 ;;
    0)           ok=1 ;;
    *)           [ "$rc" -eq 0 ] && ok=0 ;;
  esac
  _check "tests.BOOTSTRAPPED_PATHS is non-empty" "rc=0 count>0" \
         "rc=$rc count=$out" "$ok"

  # -- 6. Q: and is it empty when disabled? (paired with 5 — a constant
  #         non-empty value would pass 5 without measuring anything)
  out="$(env -u PYTHONPATH BODESIGN_TEST_BOOTSTRAP=0 "$PY" -c \
        'import tests; print(len(tests.BOOTSTRAPPED_PATHS))' 2>&1)"
  rc=$?
  ok=1
  [ "$rc" -eq 0 ] && [ "$out" = "0" ] && ok=0
  _check "BOOTSTRAPPED_PATHS empty when disabled" "rc=0 count=0" \
         "rc=$rc count=$out" "$ok"

  # -- 7. Q: does list_modules() find anything? (a zero-module run would
  #         report OK while testing nothing)
  n="$(list_modules | wc -l)"
  ok=1
  [ "$n" -gt 0 ] && ok=0
  _check "list_modules() enumerates test modules" "count>0" "count=$n" "$ok"

  # -- 8. Q: does list_modules() go red when there is nothing to enumerate?
  #         (reverse control for 7)
  #
  #    An earlier draft of this cell re-implemented the enumeration loop inline
  #    and asserted that the INLINE COPY went red. That proved nothing about
  #    list_modules(): the copy could stay correct while the real function
  #    rotted, and this cell would have kept printing PASS. It was a decoration
  #    wearing a control's name, which is worse than no cell at all — a green
  #    row here tells every later reader "the empty-repo case is covered".
  #
  #    So run the REAL script. `REPO_ROOT` is derived from `BASH_SOURCE`, so a
  #    copy of this file placed in a scratch repo skeleton roots itself there:
  #    the copy sees an existing-but-empty `tests/` and must exit non-zero with
  #    FATAL. Invoked with `--list`, not `--self-test`, so it does not recurse.
  local probe_root probe_rc probe_out probe_script
  probe_root="$(mktemp -d "${XDG_RUNTIME_DIR:-$HOME/.cache}/run_tests_selftest.XXXXXX")"
  chmod 700 "$probe_root"
  mkdir -p -m 700 "$probe_root/emptyrepo/tests" "$probe_root/emptyrepo/scripts"
  probe_script="$probe_root/emptyrepo/scripts/run_tests.sh"
  cp "${BASH_SOURCE[0]}" "$probe_script"
  chmod +x "$probe_script"
  probe_out="$("$probe_script" --list 2>&1)"
  probe_rc=$?
  ok=1
  case "$probe_out" in
    *FATAL*) [ "$probe_rc" -ne 0 ] && ok=0 ;;
  esac
  _check "empty repo: the REAL list_modules() goes red" "rc!=0 out~FATAL" \
         "rc=$probe_rc out=${probe_out##*$'\n'}" "$ok"

  # -- 8b. cleanup, with a control proving the removal hit the scratch dir and
  #        not something else: the scratch path must be gone AND its parent
  #        (XDG_RUNTIME_DIR) must still exist.
  rm -rf "$probe_root"
  local scratch_gone=1 parent_alive=1
  [ ! -e "$probe_root" ] && scratch_gone=0
  [ -e "${XDG_RUNTIME_DIR:-$HOME/.cache}" ] && parent_alive=0
  ok=1
  [ "$scratch_gone" -eq 0 ] && [ "$parent_alive" -eq 0 ] && ok=0
  _check "scratch removed, its parent intact" "gone=yes parent=yes" \
         "gone=$([ "$scratch_gone" -eq 0 ] && echo yes || echo no) parent=$([ "$parent_alive" -eq 0 ] && echo yes || echo no)" \
         "$ok"

  echo
  if [ "$fails" -eq 0 ]; then
    echo "run_tests.sh --self-test: ALL CONTROLS PASSED"
    return 0
  fi
  echo "run_tests.sh --self-test: $fails CONTROL(S) FAILED"
  return 1
}

# ---------------------------------------------------------------------------
main() {
  case "${1:-}" in
    --self-test) self_test; exit $? ;;
    --list)      clear_pycache; list_modules; exit $? ;;
    -h|--help)   sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
  esac

  clear_pycache

  local mods=()
  if [ "$#" -gt 0 ]; then
    local a
    for a in "$@"; do mods+=("$(normalise_module "$a")"); done
  else
    local line
    while IFS= read -r line; do mods+=("$line"); done < <(list_modules) || exit 1
    if [ "${#mods[@]}" -eq 0 ]; then
      echo "run_tests.sh: FATAL — module enumeration produced nothing" >&2
      exit 1
    fi
  fi

  "$PY" -m unittest "${mods[@]}"
  exit $?
}

main "$@"
