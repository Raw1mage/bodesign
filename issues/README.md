# issues/ — bug-report ledger conventions

This directory is the local-first bug/issue ledger (global AGENTS.md §8).
Top-level = open/active; `closed/` = resolved-and-effective; `observing/` =
watched-for-recurrence.

## Status line schema (BR_20260804l)

Every top-level `BR_*.md` MUST carry a machine-readable Status. The **canonical**
form is:

```
- **Status**: <OPEN | PARTIAL | FIXED | CLOSED> — <one line>
```

on **line 3** (right under the title, above the field table).

Why a schema at all: without one, 41 BRs drifted into 7 different Status
spellings, some buried on line 23+. A header-scoped sweep then reports "no
Status" for a BR that has one out of its window — the *absent* state and the
*out-of-window* state render identically, and the reader silently miscounts the
open ledger. The schema + checker collapse those two states back apart.

### States

| State | Meaning | Lives where |
| --- | --- | --- |
| `OPEN` | not yet fixed | top level |
| `PARTIAL` | main fix landed, an explicit scoped remainder is still open | top level (remainder listed) |
| `FIXED` | fixed but not yet verified-effective / not yet deployed | top level |
| `CLOSED` | verified-and-effective, no remainder | `closed/` (moved by `git mv`) |

Only a `CLOSED` BR with no remainder moves to `closed/`. A `PARTIAL` or a
fixed-but-undeployed BR stays at top level so it stays visible.

## Checker: `scripts/check_issue_headers.sh`

Two levels, mirroring the pre-commit hook's warn-never-block ethos:

- **ERROR (rc=1)** — a BR with ZERO Status line anywhere. This is the real
  scheduling hazard: a reader cannot tell whether it is open. The pre-commit
  hook surfaces this loudly.
- **WARN (rc=0)** — a BR that has a Status but not in the canonical line-3
  `- **Status**:` form. Listed for convergence; never blocks.

The checker **scans the full file, never a header window**, and prints its own
scan window (`scanned N, window=full-file`) so a reader can never mistake a
narrow view for a complete one (BR_20260804l §5 option 3 — the read-side half of
the fix; the schema above is the write-side half, and each fails independently).

### The checker has a built-in control group

`issues/.schema-fixtures/` holds two permanent fixtures — one guaranteed-ERROR
(no Status), one guaranteed-clean (canonical). The checker asserts both on every
run and refuses to report on live data if either flips. A checker whose green was
never contrasted against a real red is indistinguishable from a broken one
(BR_20260804l §9). Do NOT add a Status line to the ERROR fixture.

Run it:

```
bash scripts/check_issue_headers.sh              # self-test + live scan
bash scripts/check_issue_headers.sh --self-test  # control group only
```
