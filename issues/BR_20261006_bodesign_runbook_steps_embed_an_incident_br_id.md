---
id: BR_20261006_bodesign_runbook_steps_embed_an_incident_br_id
title: A bodesign-store runbook embeds an incident BR id in its executable steps
date: 2026-10-06
status: closed-verified (archive move to issues/closed/ deferred to the S4 commit batch; user HOLD in effect)
severity: low
priority: P3
component: bodesign runbook store (workflow.task-path.migrate-bodesign-mcp-server-to-dockerlab-and-decommission-ws)
reporter: guest dispatch from opencode duty officer ses_f05594495ffed70mIx6CAPjb1H, on the user's request
edges:
  - to: /home/pkcs12/projects/opencode/issues/BR_20261005_runbook_retrospective_steps_lack_generalization_and_contain_incident_specific_brs.md
    type: same-family
    reason: opencode BR that found this entry and fixed the runbook contract
  - to: /home/pkcs12/projects/opencode/issues/BR_20261006_runbook_skill_missing_generalization_contract.md
    type: references-spec
    reason: the user's scope test and the generalized-runbook rule now in the runbook skill
---

# BR_20261006_bodesign_runbook_steps_embed_an_incident_br_id

## §1 Symptom

The runbook `workflow.task-path.migrate-bodesign-mcp-server-to-dockerlab-and-decommission-ws`
in the bodesign runbook store has this text in step 1 (quoted from the opencode BR_20261005 §1.2):

> `verify GET /invoke returns 403 Forbidden (BR_20260730d)`

User ruling (verbatim, 2026-10-06): 「runbook是優化泛化的工具呼叫流程，不是單一特定任務的筆記本」
(a runbook is an optimized, generalized tool-call workflow, not a notebook for one specific task).

User's scope test (verbatim, 2026-10-06): 「我的要求，是不是換一個文件任務也同樣適用？」
(would my request still apply if the document or task were swapped?)

## §2 RCA (observed; hypotheses marked)

Observed:
- The step cites a specific past incident BR (`BR_20260730d`) inside the executable steps.
- The opencode runbook contract (commit d04a54ab08, deployed at build 89fc3644a6) now states that
  past BR ids, session ids, dates and incident workarounds belong in `trail` or the task's own artifact,
  not in `steps`. `record`/`update` now return a non-blocking advisory when steps contain such tokens.
- The opencode worker could not read this entry from the opencode store (qualified get unresolved).
  So the CURRENT body and UUID of this runbook were not measured by the reporter.

Hypothesis, unverified: the `403` check itself may be a valid generalized acceptance step; only the
incident id needs to move to `trail`.

## §3 Proposed remediation

1. `runbook(action="get")` the entry from the bodesign store and read the current body.
2. Apply the scope test to each line. Keep the generalized check (for example, "verify the retired
   endpoint returns 403"). Move the incident id and any other case-specific facts to `trail`.
3. `runbook(action="update")` with the cleaned steps. An advisory in the result means a token is
   still present; re-check it.
4. Optionally scan the rest of the bodesign store for the same pattern.

## §4 Acceptance criteria

- `runbook(get)` of the entry shows steps with no BR id, session id or calendar date.
- The `update` result carries no ADVISORY line.
- The `Fastest path:` first line is unchanged in form.

## §5 Closure (duty officer ses_04db7a1c5ffelvbxyLP1p6xlRH, 2026-10-06)

- `runbook(get)` BEFORE: step 1 embedded `BR_20260730d`, literal host `192.168.100.141:8177` and tool count `61`.
- `runbook(update)` applied: steps now use `<remote-host>:<port>`, compare toolCount against `/healthz`, keep the generalized
  "GET /invoke returns 403" acceptance, add an explicit stop condition. Incident id, host and count moved to `trail`.
  Result line: `updated: … (evidence event event_2026-10-06_runbook-update-workflow-task-path-migrate-bodesign_wcurn0)` — no ADVISORY.
- `runbook(get)` AFTER: no BR id, session id or calendar date in steps. Heading/form unchanged.
- §3 step 4 scan: `runbook(list)` shows this is the only local runbook in the bodesign store; no other entry to clean.
