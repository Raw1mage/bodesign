# FIXTURE — canonical Status form (permanent control-group positive)

- **Status**: OPEN — control-group fixture, must pass the checker on every run

This file exists ONLY to give scripts/check_issue_headers.sh a guaranteed
positive: the canonical `- **Status**:` on line 3. If this ever fails, the
checker's OK verdict on live data is worthless (BR_20260804l §9).
