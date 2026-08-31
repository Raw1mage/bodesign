# FIXTURE — duplicate BR ID, copy A (permanent control-group negative)

- **Status**: OPEN — control-group fixture, must make the dup check go red every run

This file and `BR_29991231z_FIXTURE_duplicate_id_must_ERROR_b.md` deliberately
claim the SAME suffixed id `BR_29991231z`. They exist only to give
scripts/check_issue_headers.sh a guaranteed duplicate to detect, on every run.
Do NOT renumber either file. The date is 2999-12-31 so it can never collide with
a real BR.

If a uniqueness checker has never gone red on a real duplicate, its green is
indistinguishable from a checker that never looked (BR_20260804l §9).
