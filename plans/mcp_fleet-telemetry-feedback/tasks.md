# Tasks: mcp_fleet-telemetry-feedback

## 1. Application Layer Implementation (bodesign MCP)

- [x] 1.1 Implement `services/mcp/feedback_drafts.py` providing `submit_retrospective`, SQLite persistence, and non-blocking IPC wake (id: flt-bodesign-drafts; status: ready_for_implementation) — artifact: services/mcp/feedback_drafts.py
- [x] 1.2 Wire `submit_retrospective` and alias `bodesign_submit_retrospective` into `services/mcp/server.py` tool registry and dispatch (id: flt-bodesign-server-wire; status: ready_for_implementation) — artifact: services/mcp/server.py

## 2. Deployment Harness & Outbox Implementation

- [x] 2.1 Implement deployment sidecar `deploy/fleet-outbox-adapter.py` supporting wake socket, HMAC-SHA256 wire signing, 5-attempt retry loop, and dead-letter isolation (id: flt-bodesign-sidecar; status: ready_for_implementation) — artifact: deploy/fleet-outbox-adapter.py
- [x] 2.2 Implement operator reconciliation CLI `scripts/fleet-outbox-reconcile.py` for dead-letter review and requeueing (id: flt-bodesign-reconcile; status: ready_for_implementation) — artifact: scripts/fleet-outbox-reconcile.py

## 3. Mother Fleet Node Registration

- [x] 3.1 Register bodesign node in Mother system `~/.config/opencode/fleet-nodes.json` bound to `ownerUser: pkcs12` and `owningRepo: /home/pkcs12/projects/bodesign` (id: flt-bodesign-registry; status: ready_for_implementation) — artifact: /home/pkcs12/.config/opencode/fleet-nodes.json

## 4. Verification & Architecture Alignment

- [x] 4.1 Implement automated unit tests for retrospective draft persistence, payload limits, and UUIDv7 timestamp coherence in `tests/test_feedback_drafts.py` (id: flt-bodesign-unit-test; status: ready_for_implementation) — artifact: tests/test_feedback_drafts.py
- [x] 4.2 Execute `deploy/fleet-outbox-adapter.py --self-test` to assert canonical wire vector agreement (id: flt-bodesign-adapter-test; status: ready_for_implementation) — artifact: deploy/fleet-outbox-adapter.py
- [x] 4.3 Synchronize `specs/architecture.md` in bodesign to record the MCP Fleet Telemetry feedback interface (id: flt-bodesign-arch-sync; status: ready_for_implementation) — artifact: specs/architecture.md
