"""Unit tests for Mechanical, Feature Graph, CAD Job, and Adoption Contracts (Task 2.4 / AC10, AC12..AC15).

Covers:
- Finite rigid right-handed frames (4x4 matrix, det=+1, R^T R = I, bottom row [0,0,0,1], mm units).
- FeatureGraph DAG compilation, cycle detection (CYCLE_DETECTED), unique IDs, supported ops.
- Revision-bound single anchors (cardinality=1, ambiguous anchor rejection).
- Explicit missing 3D models and sourced engineering calculations (rejects unverified defaults).
- InterferenceRecord: AABB-not-exact flag, exact-unavailable cannot certify exact clearance.
- ReferenceAdoption: license clearance gating (is_extraction_allowed requires approved clearance).
- CadExecutionJob: request deduplication key, timeout mapping to 'unknown' without blind replay.
"""

import math
import unittest

from bodesign_design_ir.rebuild_contracts import (
    ArtifactRef,
    CadExecutionJob,
    CadJobRegistry,
    DuplicateCadRequestError,
    EngineeringCalculation,
    FeatureAnchor,
    FeatureGraph,
    FeatureNode,
    MechanicalBridge,
    ReferenceAdoption,
    validate_rigid_frame_4x4,
)
from bodesign_workflow_core.rebuild_contracts import InterferenceRecord


class TestMechanicalBridgeAndRigidFrames(unittest.TestCase):
    """Tests for MechanicalBridge 4x4 rigid right-handed frame validation."""

    def test_valid_identity_and_rotation_matrix(self):
        # 1. Identity frame with translation
        identity_transform = [
            [1.0, 0.0, 0.0, 10.0],
            [0.0, 1.0, 0.0, 20.0],
            [0.0, 0.0, 1.0, 5.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        bridge = MechanicalBridge(
            board_manifest_sha256="a" * 64,
            enclosure_manifest_sha256="b" * 64,
            frame={
                "units": "mm",
                "axes": "right-handed",
                "origin": [10.0, 20.0, 5.0],
                "board_normal": [0.0, 0.0, 1.0],
                "transform": identity_transform,
            },
            models=[{"object_id": "CONN1", "solid_hash": "c" * 64}],
            fixed_constraints=[{"type": "edge_distance", "value": 5.0}],
        )
        self.assertEqual(bridge.frame["units"], "mm")
        self.assertEqual(bridge.frame["axes"], "right-handed")
        d = bridge.to_dict()
        self.assertEqual(d["frame"]["units"], "mm")

        # 2. 90-degree Z rotation (cos 90 = 0, sin 90 = 1)
        z_rot_90 = [
            [0.0, -1.0, 0.0, 0.0],
            [1.0,  0.0, 0.0, 0.0],
            [0.0,  0.0, 1.0, 0.0],
            [0.0,  0.0, 0.0, 1.0],
        ]
        validate_rigid_frame_4x4(z_rot_90)

    def test_rejects_reflection_det_minus_one(self):
        # Reflection across XY plane has det = -1 (left-handed)
        reflection_frame = [
            [1.0, 0.0,  0.0, 0.0],
            [0.0, 1.0,  0.0, 0.0],
            [0.0, 0.0, -1.0, 0.0],
            [0.0, 0.0,  0.0, 1.0],
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_rigid_frame_4x4(reflection_frame)
        self.assertIn("reflection", str(ctx.exception).lower())

    def test_rejects_scaling_or_shear_non_orthogonal(self):
        # Uniform scaling factor 2.0 (det = 8.0, non-orthogonal)
        scaling_frame = [
            [2.0, 0.0, 0.0, 0.0],
            [0.0, 2.0, 0.0, 0.0],
            [0.0, 0.0, 2.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_rigid_frame_4x4(scaling_frame)
        self.assertIn("orthonormal", str(ctx.exception).lower())

    def test_rejects_non_finite_values_and_wrong_bottom_row(self):
        # NaN value
        nan_frame = [
            [float("nan"), 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_rigid_frame_4x4(nan_frame)
        self.assertIn("non-finite", str(ctx.exception).lower())

        # Invalid bottom row (affine distortion)
        bad_bottom_frame = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.1, 0.0, 0.0, 1.0],
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_rigid_frame_4x4(bad_bottom_frame)
        self.assertIn("bottom row", str(ctx.exception).lower())

    def test_explicit_missing_models_declaration(self):
        # Model without solid_hash MUST declare is_missing=True explicitly
        with self.assertRaises(ValueError):
            MechanicalBridge(
                board_manifest_sha256="a" * 64,
                enclosure_manifest_sha256="b" * 64,
                frame={
                    "units": "mm",
                    "axes": "right-handed",
                    "origin": [0.0, 0.0, 0.0],
                    "board_normal": [0.0, 0.0, 1.0],
                    "transform": [
                        [1.0, 0.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0, 0.0],
                        [0.0, 0.0, 1.0, 0.0],
                        [0.0, 0.0, 0.0, 1.0],
                    ],
                },
                models=[{"object_id": "U1_SOIC8"}],  # Neither solid_hash nor is_missing!
                fixed_constraints=[],
            )

        # Valid with explicit is_missing=True
        bridge_ok = MechanicalBridge(
            board_manifest_sha256="a" * 64,
            enclosure_manifest_sha256="b" * 64,
            frame={
                "units": "mm",
                "axes": "right-handed",
                "origin": [0.0, 0.0, 0.0],
                "board_normal": [0.0, 0.0, 1.0],
                "transform": [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
            },
            models=[{"object_id": "U1_SOIC8", "is_missing": True}],
            fixed_constraints=[],
        )
        self.assertTrue(bridge_ok.models[0]["is_missing"])


class TestFeatureGraphAndAnchors(unittest.TestCase):
    """Tests for FeatureGraph DAG validation, cycles, and single-anchor cardinality."""

    def test_valid_dag_compilation(self):
        anchor = FeatureAnchor(
            object_id="base_box_top_face",
            semantic_role="enclosure_mating_face",
            source_revision="rev_mcad_1",
            geometric_predicate="coplanar",
            tolerance=0.05,
            cardinality=1,
        )
        node_base = FeatureNode(
            id="base_box",
            operation="enclosure",
            depends_on=[],
            parameters={"width": {"value": 100.0, "unit": "mm"}, "height": {"value": 50.0, "unit": "mm"}},
            anchor_refs=["base_box_top_face"],
        )
        node_boss = FeatureNode(
            id="mounting_boss_1",
            operation="boss",
            depends_on=["base_box"],
            parameters={"diameter": {"value": 6.0, "unit": "mm"}, "height": {"value": 10.0, "unit": "mm"}},
        )
        graph = FeatureGraph(
            schema_version="1.0.0",
            source_manifest_sha256="e" * 64,
            nodes=[node_base, node_boss],
            anchors=[anchor],
        )
        self.assertEqual(graph.execution["topological_order"], ["base_box", "mounting_boss_1"])
        # No synthesized isolation claim
        self.assertNotIn("isolated_candidate", graph.execution)

    def test_feature_graph_schema_anchor_and_parameter_validation(self):
        anchor = FeatureAnchor(
            object_id="face_a", semantic_role="mating_face", source_revision="rev_1",
            geometric_predicate="coplanar", tolerance=0.05,
        )
        node = FeatureNode(id="n1", operation="enclosure", anchor_refs=["face_a"],
                           parameters={"w": {"value": 1.0, "unit": "mm"}})
        # Unsupported schema version
        with self.assertRaises(ValueError):
            FeatureGraph(schema_version="2.0.0", source_manifest_sha256="e" * 64, nodes=[node], anchors=[anchor])
        # Dangling anchor ref
        with self.assertRaises(ValueError) as ctx:
            FeatureGraph(schema_version="1.0.0", source_manifest_sha256="e" * 64,
                         nodes=[FeatureNode(id="n2", operation="boss", anchor_refs=["ghost"])], anchors=[anchor])
        self.assertIn("DANGLING_ANCHOR_REF", str(ctx.exception))
        # Anchors bound to different source revisions
        anchor_other = FeatureAnchor(
            object_id="face_b", semantic_role="mating_face", source_revision="rev_2",
            geometric_predicate="coplanar", tolerance=0.05,
        )
        with self.assertRaises(ValueError) as ctx:
            FeatureGraph(schema_version="1.0.0", source_manifest_sha256="e" * 64, nodes=[node], anchors=[anchor, anchor_other])
        self.assertIn("ANCHOR_REVISION_MISMATCH", str(ctx.exception))
        # Bare numeric parameter without unit
        with self.assertRaises(ValueError):
            FeatureGraph(schema_version="1.0.0", source_manifest_sha256="e" * 64,
                         nodes=[FeatureNode(id="n3", operation="boss", parameters={"d": 6.0})])
        # Caller-asserted isolation is refused
        with self.assertRaises(ValueError):
            FeatureGraph(schema_version="1.0.0", source_manifest_sha256="e" * 64, nodes=[node], anchors=[anchor],
                         execution={"isolated_candidate": True})
        # NaN tolerance rejected
        with self.assertRaises(ValueError):
            FeatureAnchor(object_id="x", semantic_role="r", source_revision="rev", geometric_predicate="p",
                          tolerance=math.nan)

    def test_cycle_detection_reports_cycle_detected(self):
        # A -> B -> A cycle
        node_a = FeatureNode(id="node_a", operation="cutout", depends_on=["node_b"])
        node_b = FeatureNode(id="node_b", operation="cutout", depends_on=["node_a"])

        with self.assertRaises(ValueError) as ctx:
            FeatureGraph(
                schema_version="1.0.0",
                source_manifest_sha256="e" * 64,
                nodes=[node_a, node_b],
            )
        self.assertIn("CYCLE_DETECTED", str(ctx.exception))

    def test_duplicate_node_ids_rejected(self):
        node1 = FeatureNode(id="dup_id", operation="boss", depends_on=[])
        node2 = FeatureNode(id="dup_id", operation="cutout", depends_on=[])
        with self.assertRaises(ValueError) as ctx:
            FeatureGraph(
                schema_version="1.0.0",
                source_manifest_sha256="e" * 64,
                nodes=[node1, node2],
            )
        self.assertIn("DUPLICATE_NODE_ID", str(ctx.exception))

    def test_unsupported_operation_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            FeatureNode(id="bad_op", operation="unsupported_metal_fold", depends_on=[])  # type: ignore
        self.assertIn("UNSUPPORTED_OPERATION", str(ctx.exception))

    def test_ambiguous_anchor_cardinality_rejected(self):
        # Ambiguous anchor resolving to multiple faces (cardinality != 1) is rejected
        with self.assertRaises(ValueError) as ctx:
            FeatureAnchor(
                object_id="ambiguous_face",
                semantic_role="mating_face",
                source_revision="rev_mcad_1",
                geometric_predicate="coplanar",
                tolerance=0.05,
                cardinality=2,  # Ambiguous! Must be exactly 1
            )
        self.assertIn("cardinality must be exactly 1", str(ctx.exception))


class TestEngineeringCalculation(unittest.TestCase):
    """Tests for sourced engineering calculations and rejecting unverified defaults."""

    def test_valid_sourced_calculation(self):
        calc = EngineeringCalculation(
            model={
                "formula_id": "ipc_2152_internal_trace",
                "version": "1.0",
                "topology_applicable": True,
            },
            inputs=[
                {"name": "current_amps", "value": 2.5, "unit": "A", "source": "datasheet:max_active_current"},
                {"name": "temp_rise_c", "value": 10.0, "unit": "degC", "source": "spec:thermal_envelope"},
                {"name": "copper_weight_oz", "value": 1.0, "unit": "oz", "source": "fab:jlcpcb_4layer"},
            ],
            result={"trace_width_mm": 0.45},
            gaps=[],
            limitations=[],
        )
        self.assertEqual(calc.result["trace_width_mm"], 0.45)
        self.assertEqual(len(calc.gaps), 0)

    def test_missing_sources_or_inputs_blocks_result_with_gaps(self):
        # When required input is missing (value=None), calculation result is nullified and gap is reported
        calc = EngineeringCalculation(
            model={
                "formula_id": "microstrip_z0",
                "version": "1.0",
                "topology_applicable": True,
            },
            inputs=[
                {"name": "dielectric_constant", "value": None, "unit": "epsilon_r", "source": "datasheet"},
            ],
            result={"impedance_ohms": 50.0},  # Tentative result will be nullified
            gaps=[],
        )
        # Invariant: result must be None and gap must be recorded
        self.assertIsNone(calc.result)
        self.assertTrue(any("Missing required input: dielectric_constant" in g for g in calc.gaps))

    def test_result_without_inputs_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            EngineeringCalculation(
                model={"formula_id": "f", "version": "1", "topology_applicable": True},
                inputs=[],
                result={"x": 1.0},
            )
        self.assertIn("non-empty sourced inputs", str(ctx.exception))
        # Non-bool applicability flag rejected
        with self.assertRaises(ValueError):
            EngineeringCalculation(
                model={"formula_id": "f", "version": "1", "topology_applicable": "yes"},
                inputs=[{"name": "a", "value": 1, "unit": "u", "source": "s"}],
            )


class TestInterferenceRecord(unittest.TestCase):
    """Tests for InterferenceRecord and AABB-not-exact flag."""

    def test_aabb_broad_phase_cannot_certify_exact_pass(self):
        # AC13: AABB overlap is not exact collision; AABB broad-phase cannot certify exact clearance
        record_aabb = InterferenceRecord(
            subject_manifest_sha256="9" * 64,
            method="aabb-broad-phase",
            pairs=[],
            policy={
                "required_clearance_mm": 0.5,
                "declared_contacts": [],
                "tolerance_mm": 0.05,
                "backend": "bodesign_aabb_broad_phase",
                "backend_version": "1.0.0",
            },
            coverage={
                "expected_model_ids": ["U1", "CONN1"],
                "available_solid_ids": ["U1", "CONN1"],
                "missing_ids": [],
            },
        )
        # Broad-phase cannot certify exact clearance
        self.assertFalse(record_aabb.is_exact_certified)

    def test_exact_solid_with_missing_models_cannot_certify(self):
        # Even with exact-solid method, missing models prevent exact certification
        record_partial = InterferenceRecord(
            subject_manifest_sha256="9" * 64,
            method="exact-solid",
            pairs=[],
            policy={
                "required_clearance_mm": 0.5,
                "declared_contacts": [],
                "tolerance_mm": 0.05,
                "backend": "cad_kernel_exact",
                "backend_version": "1.0.0",
            },
            coverage={
                "expected_model_ids": ["U1", "CONN1"],
                "available_solid_ids": ["U1"],
                "missing_ids": ["CONN1"],  # Missing solid!
            },
        )
        self.assertFalse(record_partial.is_exact_certified)

    def test_exact_solid_fully_covered_certifies(self):
        # Certification requires EXECUTED pairs with collision + clearance results
        record_full = InterferenceRecord(
            subject_manifest_sha256="9" * 64,
            method="exact-solid",
            pairs=[
                {"a": "U1", "b": "CONN1", "collides": False, "clearance_mm": 1.2},
            ],
            policy={
                "required_clearance_mm": 0.5,
                "declared_contacts": [],
                "tolerance_mm": 0.05,
                "backend": "cad_kernel_exact",
                "backend_version": "1.0.0",
            },
            coverage={
                "expected_model_ids": ["U1", "CONN1"],
                "available_solid_ids": ["U1", "CONN1"],
                "missing_ids": [],
            },
        )
        self.assertTrue(record_full.is_exact_certified)
        self.assertEqual(record_full.certification_blockers, [])

    def test_empty_pairs_or_invalid_policy_cannot_certify(self):
        base_policy = {
            "required_clearance_mm": 0.5,
            "declared_contacts": [],
            "tolerance_mm": 0.05,
            "backend": "cad_kernel_exact",
            "backend_version": "1.0.0",
        }
        cov = {"expected_model_ids": ["U1", "CONN1"], "available_solid_ids": ["U1", "CONN1"], "missing_ids": []}
        # pairs=[] is absence of evidence
        rec_empty = InterferenceRecord(subject_manifest_sha256="9" * 64, method="exact-solid",
                                       pairs=[], policy=dict(base_policy), coverage=cov)
        self.assertFalse(rec_empty.is_exact_certified)
        self.assertTrue(any("pairs=[]" in b for b in rec_empty.certification_blockers))
        # Pair without executed collision result
        rec_noexec = InterferenceRecord(subject_manifest_sha256="9" * 64, method="exact-solid",
                                        pairs=[{"a": "U1", "b": "CONN1"}], policy=dict(base_policy), coverage=cov)
        self.assertFalse(rec_noexec.is_exact_certified)
        # Colliding pair
        rec_collide = InterferenceRecord(subject_manifest_sha256="9" * 64, method="exact-solid",
                                         pairs=[{"a": "U1", "b": "CONN1", "collides": True, "clearance_mm": 0.0}],
                                         policy=dict(base_policy), coverage=cov)
        self.assertFalse(rec_collide.is_exact_certified)
        # Insufficient clearance
        rec_short = InterferenceRecord(subject_manifest_sha256="9" * 64, method="exact-solid",
                                       pairs=[{"a": "U1", "b": "CONN1", "collides": False, "clearance_mm": 0.3}],
                                       policy=dict(base_policy), coverage=cov)
        self.assertFalse(rec_short.is_exact_certified)
        # NaN tolerance in policy
        nan_policy = dict(base_policy, tolerance_mm=math.nan)
        rec_nan = InterferenceRecord(subject_manifest_sha256="9" * 64, method="exact-solid",
                                     pairs=[{"a": "U1", "b": "CONN1", "collides": False, "clearance_mm": 1.2}],
                                     policy=nan_policy, coverage=cov)
        self.assertFalse(rec_nan.is_exact_certified)
        # Declared contact pair is allowed to touch
        contact_policy = dict(base_policy, declared_contacts=[["U1", "CONN1"]])
        rec_contact = InterferenceRecord(subject_manifest_sha256="9" * 64, method="exact-solid",
                                         pairs=[{"a": "U1", "b": "CONN1", "collides": True, "clearance_mm": 0.0}],
                                         policy=contact_policy, coverage=cov)
        self.assertTrue(rec_contact.is_exact_certified)


class TestReferenceAdoption(unittest.TestCase):
    """Tests for ReferenceAdoption and license clearance gating."""

    def test_approved_license_allows_extraction(self):
        adoption = ReferenceAdoption(
            source={
                "url": "https://github.com/Rockbox/rockbox",
                "commit": "d83b56a",
                "paths": ["apps/codec/decoder.c"],
                "evidence_kind": "source",
            },
            license={
                "grant": "MIT",
                "notice_paths": ["COPYING"],
                "reviewed": True,
                "approved": True,
            },
            integration="selective-extraction",
        )
        self.assertTrue(adoption.is_extraction_allowed)

    def test_unapproved_license_forbids_extraction(self):
        # Unapproved or unreviewed grant forbids selective extraction
        adoption_unapproved = ReferenceAdoption(
            source={
                "url": "https://example.com/vendor",
                "commit": "v1.0",
                "paths": ["driver.c"],
                "evidence_kind": "source",
            },
            license={
                "grant": "Proprietary",
                "notice_paths": ["LICENSE"],
                "reviewed": True,
                "approved": False,  # Not approved!
            },
            integration="selective-extraction",
        )
        self.assertFalse(adoption_unapproved.is_extraction_allowed)

    def test_string_false_is_not_approval_and_non_extraction_modes_do_not_extract(self):
        src = {"url": "https://example.com/v", "commit": "c", "paths": ["a.c"], "evidence_kind": "source"}
        # String 'false' (and any non-bool) is rejected outright, never coerced
        with self.assertRaises(ValueError):
            ReferenceAdoption(
                source=src,
                license={"grant": "MIT", "notice_paths": ["LICENSE"], "reviewed": True, "approved": "false"},
                integration="selective-extraction",
            )
        with self.assertRaises(ValueError):
            ReferenceAdoption(
                source=src,
                license={"grant": "MIT", "notice_paths": ["LICENSE"], "reviewed": "yes", "approved": True},
                integration="selective-extraction",
            )
        # Cleared license but non-extraction mode: extraction is NOT allowed
        deferred = ReferenceAdoption(
            source=src,
            license={"grant": "MIT", "notice_paths": ["LICENSE"], "reviewed": True, "approved": True},
            integration="deferred",
        )
        self.assertFalse(deferred.is_extraction_allowed)


class TestCadExecutionJob(unittest.TestCase):
    """Tests for CadExecutionJob deduplication, timeout mapping, and no blind replay."""

    def test_job_lifecycle_and_timeout_mapping_to_unknown(self):
        job = CadExecutionJob(
            request_id="job_freeroute_01",
            payload_digest="sha256_input_spec_params_v1",
            baseline_revision="rev_board_v1",
            capability_revision="freerouting_1.9.0",
            state="running",
        )
        self.assertEqual(job.state, "running")

        # On timeout, running job state transitions to 'unknown' without blind replay
        job.handle_timeout()
        self.assertEqual(job.state, "unknown")
        self.assertIsNotNone(job.receipt)
        self.assertEqual(job.receipt["error"], "EXECUTION_TIMEOUT")

    def test_cancelled_queued_job_state(self):
        job = CadExecutionJob(
            request_id="job_cad_02",
            payload_digest="dedup_02",
            baseline_revision="rev_v1",
            capability_revision="v1",
            state="queued",
        )
        cancelled = job.cancel()
        self.assertTrue(cancelled)
        self.assertEqual(job.state, "cancelled-before-start")

        # Running job cannot be cancelled side-effect-free
        job_running = CadExecutionJob(
            request_id="job_cad_03",
            payload_digest="dedup_03",
            baseline_revision="rev_v1",
            capability_revision="v1",
            state="running",
        )
        cancelled_running = job_running.cancel()
        self.assertFalse(cancelled_running)
        self.assertEqual(job_running.state, "running")

    def test_registry_rejects_duplicate_request_id_and_payload(self):
        reg = CadJobRegistry()
        reg.register(CadExecutionJob(request_id="r1", payload_digest="p1",
                                     baseline_revision="b1", capability_revision="c1"))
        with self.assertRaises(DuplicateCadRequestError) as ctx:
            reg.register(CadExecutionJob(request_id="r1", payload_digest="p2",
                                         baseline_revision="b1", capability_revision="c1"))
        self.assertIn("DUPLICATE_REQUEST_ID", str(ctx.exception))
        with self.assertRaises(DuplicateCadRequestError) as ctx:
            reg.register(CadExecutionJob(request_id="r2", payload_digest="p1",
                                         baseline_revision="b1", capability_revision="c1"))
        self.assertIn("DUPLICATE_PAYLOAD", str(ctx.exception))
        # Empty baseline / capability revision rejected
        with self.assertRaises(ValueError):
            CadExecutionJob(request_id="r3", payload_digest="p3", baseline_revision="", capability_revision="c1")
        with self.assertRaises(ValueError):
            CadExecutionJob(request_id="r3", payload_digest="p3", baseline_revision="b1", capability_revision="")


if __name__ == "__main__":
    unittest.main()
