import base64
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bodesign_workflow_core import (
    assess_c01_package_readiness,
    c01_id_package,
    c01_next_question,
    c01_update_answers,
    emit_c01_cmf_package,
    emit_c01_id_visual_package,
    emit_c01_rockbox_package,
    emit_c01_uiux_package,
    generate_c01_concept_image,
)


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class C01IdPackageTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c01-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_emit_rockbox_like_package(self):
        result = emit_c01_rockbox_package(
            self.work,
            {
                "summary": "Portable edge AI camera with microphone, USB-C charging, BLE, and status LED.",
                "project_overall": "Handheld POC for local sensing.",
            },
            {
                "product_name": "EdgeSense POC",
                "form_archetype": "handheld sensor",
                "primary_face": "front face with camera and status LED",
                "cmf_direction": "rugged dark enclosure with subtle brand accent",
                "display_uiux": "No screen; LED shows boot, normal, error, pairing, and charging states.",
                "owner": "ID designer + product owner",
            },
        )

        self.assertTrue(result.readiness.usable)
        self.assertEqual(100, result.readiness.readiness_pct)
        for rel in [
            "C01-ID/Ai file/Design_Direction.md",
            "C01-ID/CMF/CMF_Direction.md",
            "C01-ID/Display UIUX/UIUX_Requirements.md",
            "C01-ID/Interface_Constraints.json",
            "C01-ID/Handoff_to_ID_Designer.md",
        ]:
            path = self.work / rel
            self.assertTrue(path.exists(), rel)
            self.assertGreater(path.stat().st_size, 80)

        constraints = json.loads((self.work / "C01-ID/Interface_Constraints.json").read_text(encoding="utf-8"))
        names = {item["name"] for item in constraints["exposed_components"]}
        self.assertIn("camera", names)
        self.assertIn("microphone", names)
        self.assertIn("usb-c", names)
        self.assertIn("antenna", names)
        self.assertIn("C05", constraints["downstream_targets"])

        handoff = (self.work / "C01-ID/Handoff_to_ID_Designer.md").read_text(encoding="utf-8")
        self.assertIn("not final `.ai`", handoff)
        self.assertIn("not final", handoff)

    def test_readiness_reports_missing_outputs(self):
        (self.work / "C01-ID" / "Ai file").mkdir(parents=True)
        (self.work / "C01-ID" / "Ai file" / "Design_Direction.md").write_text("draft", encoding="utf-8")

        readiness = assess_c01_package_readiness(self.work)

        self.assertFalse(readiness.usable)
        self.assertLess(readiness.readiness_pct, 100)
        statuses = {artifact.key: artifact.status for artifact in readiness.artifacts}
        self.assertEqual("present", statuses["ai_file"])
        self.assertEqual("missing", statuses["cmf"])
        self.assertIn("CMF", readiness.next_step)

    def test_next_question_bootstraps_without_writing_state(self):
        question = c01_next_question(self.work)

        self.assertEqual("question_available", question.status)
        self.assertEqual("form_archetype", question.target_field)
        self.assertFalse(question.answer_state_exists)
        self.assertFalse((self.work / "C01-ID" / "answer_state.json").exists())

    def test_update_answers_persists_state_and_regenerates_package(self):
        result = c01_update_answers(
            self.work,
            {
                "form_archetype": "desktop sensor",
                "usage_posture": {"value": "placed on desk", "state": "answered", "source": "user"},
                "cmf_direction": {"value": "matte black utility", "state": "drafted", "source": "AI suggestion"},
            },
            "Desk AI sensor with camera, mic, USB-C, and BLE.",
        )

        self.assertEqual("answers_updated", result.status)
        self.assertIn("form_archetype", result.updated_fields)
        self.assertFalse(result.to_dict()["human_approved"])
        self.assertTrue((self.work / "C01-ID" / "answer_state.json").exists())
        self.assertTrue((self.work / "C01-ID" / "Ai file" / "Design_Direction.md").exists())
        state = json.loads((self.work / "C01-ID" / "answer_state.json").read_text(encoding="utf-8"))
        self.assertEqual("answered", state["fields"]["form_archetype"]["state"])
        self.assertEqual("drafted", state["fields"]["cmf_direction"]["state"])
        self.assertEqual("primary_face", result.next_question.target_field)

    def test_readiness_uses_field_gaps_when_answer_state_exists(self):
        c01_update_answers(
            self.work,
            {
                "form_archetype": "desktop sensor",
                "usage_posture": "placed on desk",
                "cmf_direction": {"value": "matte black utility", "state": "drafted"},
            },
            "Desk AI sensor with camera, mic, USB-C, and BLE.",
        )

        readiness = assess_c01_package_readiness(self.work)

        self.assertFalse(readiness.usable)
        self.assertLess(readiness.readiness_pct, 100)
        self.assertEqual("C01-ID/answer_state.json", readiness.answer_state_path)
        gap_states = {gap["key"]: gap["state"] for gap in readiness.field_gaps}
        self.assertEqual("missing", gap_states["primary_face"])
        self.assertEqual("drafted", gap_states["cmf_direction"])
        self.assertIn("primary_face", readiness.next_step)
        self.assertFalse(readiness.to_dict()["human_approved"])

    def test_readiness_treats_answered_fields_as_ready_without_approval(self):
        answers = {
            "form_archetype": "desktop sensor",
            "usage_posture": "placed on desk",
            "primary_face": "front face",
            "visible_component_treatment": "subtle integrated openings",
            "exposed_components": "camera, microphone, usb-c, led",
            "cmf_direction": "matte black utility",
            "display_uiux": "LED-only status model",
            "owner": "product owner + ID designer",
            "reference_image_cues": {"value": "no reference image preference", "state": "no-preference"},
        }

        c01_update_answers(self.work, answers, "Desk AI sensor with camera, mic, USB-C, and BLE.")
        readiness = assess_c01_package_readiness(self.work)

        self.assertTrue(readiness.usable)
        self.assertEqual(100, readiness.readiness_pct)
        self.assertEqual([], readiness.field_gaps)
        self.assertFalse(readiness.to_dict()["human_approved"])

    def test_concept_image_requires_google_key(self):
        missing_accounts = self.work / "missing-accounts.json"
        with patch.dict(os.environ, {"BODESIGN_GOOGLE_API_KEY": "", "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "BODESIGN_OPENCODE_ACCOUNTS_JSON": str(missing_accounts)}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "Google AI Studio API key"):
                generate_c01_concept_image(self.work, "compact desktop edge AI camera sensor")

    def test_concept_image_writes_reference_metadata(self):
        fake_png = b"\x89PNG\r\n\x1a\n"

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "candidates": [{
                        "content": {
                            "parts": [{
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64.b64encode(fake_png).decode("ascii"),
                                }
                            }]
                        }
                    }]
                }).encode("utf-8")

        with patch("bodesign_workflow_core.c01_id_package.urllib.request.urlopen", return_value=FakeResponse()):
            result = generate_c01_concept_image(self.work, "compact desktop edge AI camera sensor", api_key="test-key")

        self.assertEqual("google-ai-studio", result.provider)
        self.assertEqual("image/png", result.mime_type)
        self.assertTrue((self.work / result.image_path).exists())
        reference = (self.work / result.reference_path).read_text(encoding="utf-8")
        self.assertIn("not manufacturing-ready", reference)
        self.assertIn("compact desktop edge AI camera sensor", reference)

    def test_concept_image_uses_opencode_accounts_api_key(self):
        accounts_path = self.work / "accounts.json"
        accounts_path.write_text(json.dumps({
            "version": 2,
            "families": {
                "gemini-cli": {
                    "activeAccount": "gemini-cli-api-test",
                    "accounts": {
                        "gemini-cli-api-test": {
                            "type": "api",
                            "name": "test",
                            "apiKey": "account-json-key",
                            "addedAt": 1,
                        }
                    },
                }
            },
        }), encoding="utf-8")

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "candidates": [{
                        "content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"png").decode("ascii")}}]}
                    }]
                }).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return FakeResponse()

        env = {
            "BODESIGN_GOOGLE_API_KEY": "",
            "GEMINI_API_KEY": "",
            "GOOGLE_API_KEY": "",
            "BODESIGN_OPENCODE_ACCOUNTS_JSON": str(accounts_path),
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("bodesign_workflow_core.c01_id_package.urllib.request.urlopen", side_effect=fake_urlopen):
                result = generate_c01_concept_image(self.work, "account backed prompt")

        self.assertIn("key=account-json-key", captured["url"])
        self.assertTrue((self.work / result.image_path).exists())

    # ── N6: constraint hardening ────────────────────────────────────
    def test_exposed_components_carry_owner_status_downstream_risk(self):
        emit_c01_rockbox_package(self.work, c00="A wearable with antenna, USB-C, LED, and a button.")
        constraints = json.loads((self.work / "C01-ID" / "Interface_Constraints.json").read_text())
        comps = constraints["exposed_components"]
        self.assertTrue(comps)
        for c in comps:
            for field in ("name", "decision_status", "owner", "downstream_targets", "risk_notes"):
                self.assertIn(field, c)
        antenna = next((c for c in comps if c["name"] == "antenna"), None)
        if antenna:
            self.assertIn("C03", antenna["downstream_targets"])
            self.assertIn("RF", antenna["risk_notes"])

    # ── A2: prompt artifacts ────────────────────────────────────────
    def test_emit_concept_prompts_reference_only(self):
        from bodesign_workflow_core import emit_c01_concept_prompts
        res = emit_c01_concept_prompts(self.work, c00="A handheld with a screen.")
        for rel in ("C01-ID/Ai file/Concept_Image_Prompts.md",
                    "C01-ID/Ai file/Moodboard_Prompts.md",
                    "C01-ID/Display UIUX/UI_Concept_Prompts.md"):
            self.assertIn(rel, res.files)
        self.assertTrue(res.to_dict()["reference_only"])
        self.assertIn("reference-only", (self.work / "C01-ID" / "Ai file" / "Concept_Image_Prompts.md").read_text())

    # ── N7/N8: reference image intake + traceability ────────────────
    def test_reference_cue_stays_reference_derived_until_confirmed(self):
        from bodesign_workflow_core import c01_add_reference_image, c01_confirm_reference_cue
        r = c01_add_reference_image(self.work, "refs/watch.jpg", "form",
                                    "soft rounded corners, matte finish", target_artifact="Ai file")
        cue = r.cues[0]
        self.assertEqual(cue["cue_id"], "C01-CUE-0001")
        self.assertEqual(cue["user_confirmation"], "reference-derived")  # not auto-approved
        self.assertEqual(cue["source_image"], "refs/watch.jpg")
        self.assertEqual(r.to_dict()["unconfirmed_count"], 1)
        data = json.loads((self.work / "C01-ID" / "reference_cues.json").read_text())
        self.assertEqual(data["schema"], "bodesign.c01.reference_cues.v1")
        r2 = c01_confirm_reference_cue(self.work, "C01-CUE-0001", "confirmed", note="borrow corner radius only")
        self.assertEqual(r2.cues[0]["user_confirmation"], "confirmed")
        self.assertEqual(r2.to_dict()["unconfirmed_count"], 0)

    def test_reference_cue_validation_fails_fast(self):
        from bodesign_workflow_core import c01_add_reference_image, c01_confirm_reference_cue
        with self.assertRaises(ValueError):
            c01_add_reference_image(self.work, "x.jpg", "bogus-type", "cue")
        with self.assertRaises(ValueError):
            c01_add_reference_image(self.work, "", "form", "cue")
        c01_add_reference_image(self.work, "x.jpg", "form", "cue")
        with self.assertRaises(ValueError):
            c01_confirm_reference_cue(self.work, "C01-CUE-9999", "confirmed")
        with self.assertRaises(ValueError):
            c01_confirm_reference_cue(self.work, "C01-CUE-0001", "maybe")


class C01IdNativeBucketTests(unittest.TestCase):
    """v2 (BR): three ID-native bucket emitters + readiness dual-track."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c01b-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # ── TV-1: Ai file bucket normal output + draft markings + layers ──
    def test_tv1_ai_file_bucket_full_output(self):
        res = emit_c01_id_visual_package(self.work, {
            "form_archetype": "handheld",
            "primary_face": "front",
            "exposed_components": ["camera", "led", "usb-c", "button"],
            "cmf_direction": "rugged",
        }).to_dict()
        self.assertEqual("success", res["status"])
        self.assertEqual("ai_file", res["bucket"])
        joined = " ".join(res["files"])
        self.assertIn("Ai file/", joined)
        self.assertIn("_ID_skeleton.svg", joined)
        self.assertIn("figma_import_spec.json", joined)
        self.assertIn("README.md", joined)
        self.assertTrue(res["draft_markings"])
        self.assertFalse(res["ai_emitted"])
        for layer in ("outline", "panel", "cmf-fill", "components", "annotations"):
            self.assertIn(layer, res["layers"])
        # SVG actually written and contains the layers + component groups.
        svg = next(p for p in self.work.rglob("*_ID_skeleton.svg"))
        svg_text = svg.read_text(encoding="utf-8")
        for layer in ("outline", "panel", "cmf-fill", "components", "annotations"):
            self.assertIn(f'id="{layer}"', svg_text)
        self.assertIn("component-camera-1", svg_text)
        self.assertIn("not final industrial design", svg_text)

    # ── TV-1b: HTML preview + PNG raster .ai substitutes (DD-9) ──
    def test_tv1b_ai_file_html_and_png_substitutes(self):
        res = emit_c01_id_visual_package(self.work, {
            "form_archetype": "handheld",
            "primary_face": "front",
            "exposed_components": ["led", "usb-c"],
            "cmf_direction": "rugged",
        }).to_dict()
        self.assertEqual("success", res["status"])
        joined = " ".join(res["files"])
        # HTML preview is ALWAYS emitted (pure string wrap, no dependency).
        self.assertIn("_ID_skeleton.preview.html", joined)
        html = next(p for p in self.work.rglob("*_ID_skeleton.preview.html"))
        html_text = html.read_text(encoding="utf-8")
        self.assertIn("<svg", html_text)               # SVG embeds inline
        self.assertIn("not final industrial design", html_text)
        self.assertIn("Edit the SVG directly", html_text)
        # every declared file must exist on disk (no phantom deliverable).
        for rel in res["files"]:
            self.assertTrue((self.work / rel).exists(), f"declared but missing: {rel}")

    # ── TV-1c: PNG-pending honesty — toolchain absent → .png NOT in files ──
    def test_tv1c_png_pending_not_listed(self):
        with patch.object(c01_id_package, "_render_svg_to_png",
                          return_value=(False, "PNG pending — cairosvg unavailable (C01V-E003)")):
            res = emit_c01_id_visual_package(self.work, {
                "form_archetype": "handheld",
                "primary_face": "front",
                "exposed_components": ["led"],
                "cmf_direction": "rugged",
            }).to_dict()
        self.assertEqual("success", res["status"])
        self.assertFalse(res["png_rendered"])
        # no phantom .png in the deliverable list, and none on disk.
        self.assertNotIn("_ID_skeleton.png", " ".join(res["files"]))
        self.assertFalse(list(self.work.rglob("*_ID_skeleton.png")))
        # HTML + SVG remain the honest substitutes.
        self.assertIn("_ID_skeleton.preview.html", " ".join(res["files"]))

    # ── TV-2: uncovered component placeholder ──
    def test_tv2_uncovered_component_placeholder(self):
        res = emit_c01_id_visual_package(self.work, {
            "form_archetype": "desktop-sensor",
            "primary_face": "top",
            "exposed_components": ["camera", "exotic-sensor-xyz"],
            "cmf_direction": "premium",
        }).to_dict()
        self.assertEqual("success", res["status"])
        self.assertIn("exotic-sensor-xyz", res["placeholders"])

    # ── TV-3: Ai file fail-fast missing form_archetype ──
    def test_tv3_ai_file_fail_fast_missing_form(self):
        res = emit_c01_id_visual_package(self.work, {
            "primary_face": "front",
            "exposed_components": ["led"],
            "cmf_direction": "rugged",
        }).to_dict()
        self.assertEqual("missing", res["status"])
        self.assertIn("form_archetype", res["missing_fields"])
        self.assertFalse(list(self.work.rglob("*_ID_skeleton.svg")))

    # ── TV-4: CMF bucket normal output ──
    def test_tv4_cmf_bucket_full_output(self):
        res = emit_c01_cmf_package(self.work, {
            "cmf_direction": "rugged",
            "exposed_components": ["antenna", "usb-c"],
        }).to_dict()
        self.assertEqual("success", res["status"])
        self.assertEqual("cmf", res["bucket"])
        joined = " ".join(res["files"])
        self.assertIn("CMF/", joined)
        self.assertIn("_CMF_Direction.pdf", joined)
        self.assertIn("cmf_tokens.json", joined)
        self.assertIn("README.md", joined)
        self.assertIn("not CMF approval", res["draft_markings"])
        tokens = res["cmf_tokens"]
        self.assertEqual("not-approved", tokens["approval_state"])
        self.assertTrue(tokens["material_family"])
        self.assertTrue(tokens["rf_transparent_zones"])  # antenna present
        # markdown source written even if PDF pending
        self.assertTrue(list(self.work.rglob("*_CMF_Direction.md")))
        self.assertTrue((self.work / "C01-ID" / "CMF" / "cmf_tokens.json").exists())

    # ── TV-5: CMF fail-fast missing cmf_direction ──
    def test_tv5_cmf_fail_fast_missing_direction(self):
        res = emit_c01_cmf_package(self.work, {"exposed_components": ["led"]}).to_dict()
        self.assertEqual("missing", res["status"])
        self.assertIn("cmf_direction", res["missing_fields"])
        self.assertFalse((self.work / "C01-ID" / "CMF" / "cmf_tokens.json").exists())

    # ── TV-6: UIUX bucket with display ──
    def test_tv6_uiux_bucket_with_display(self):
        res = emit_c01_uiux_package(self.work, {
            "display_uiux": "OLED screen with status icons",
            "exposed_components": ["display", "led", "button", "usb-c"],
        }).to_dict()
        self.assertEqual("success", res["status"])
        self.assertEqual("display_uiux", res["bucket"])
        joined = " ".join(res["files"])
        self.assertIn("Display UI_UX/", joined)
        self.assertIn("_UIUX_Flow.pdf", joined)
        self.assertIn("uiux_wireframes.svg", joined)
        self.assertIn("README.md", joined)
        self.assertIn("not UI sign-off", res["draft_markings"])
        states_text = " ".join(res["states"]).lower()
        for needle in ("oled", "led", "charging", "error"):
            self.assertIn(needle, states_text)

    # ── TV-7: UIUX no-display maps to LED/status ──
    def test_tv7_uiux_no_display_maps_led(self):
        res = emit_c01_uiux_package(self.work, {
            "display_uiux": "led only status",
            "exposed_components": ["led", "button"],
        }).to_dict()
        self.assertEqual("success", res["status"])
        self.assertFalse(res["has_display"])
        self.assertIn("led", " ".join(res["states"]).lower())

    # ── TV-8: UIUX fail-fast no status described ──
    def test_tv8_uiux_fail_fast_no_status(self):
        res = emit_c01_uiux_package(self.work, {"exposed_components": []}).to_dict()
        self.assertEqual("missing", res["status"])
        self.assertIn("display_uiux", res["missing_fields"])
        self.assertFalse((self.work / "C01-ID" / "Display UI_UX" / "uiux_wireframes.svg").exists())

    # ── TV-9: readiness dual-track + backward compatible + not approved ──
    def test_tv9_readiness_dual_track(self):
        # Five core companions present.
        emit_c01_rockbox_package(self.work, c00="Handheld with camera, mic, USB-C, BLE, LED.")
        # Ai file bucket present; CMF + Display UI_UX absent.
        emit_c01_id_visual_package(self.work, {
            "form_archetype": "handheld",
            "primary_face": "front",
            "exposed_components": ["camera", "led"],
            "cmf_direction": "rugged",
        })
        readiness = assess_c01_package_readiness(self.work).to_dict()
        # backward compatibility: core fields still present + semantics intact
        self.assertIn("readiness_pct", readiness)
        self.assertIn("usable", readiness)
        self.assertIn("artifacts", readiness)
        # dual-track
        self.assertEqual(100, readiness["companion_readiness"]["readiness_pct"])
        self.assertEqual(1, readiness["id_native_readiness"]["present"])
        self.assertEqual(3, readiness["id_native_readiness"]["total"])
        # ID-native output never lifts to approved
        self.assertFalse(readiness["human_approved"])

    # ── TV-10: no Figma path still emits figma_import_spec.json, no .ai ──
    def test_tv10_no_figma_emits_spec_no_ai(self):
        res = emit_c01_id_visual_package(self.work, {
            "form_archetype": "wearable",
            "primary_face": "front",
            "exposed_components": ["led"],
            "cmf_direction": "playful",
        }, figma_available=False).to_dict()
        self.assertEqual("success", res["status"])
        self.assertIn("figma_import_spec.json", " ".join(res["files"]))
        self.assertFalse(res["ai_emitted"])
        self.assertFalse(list(self.work.rglob("*.ai")))

    # ── Reads from persisted answer_state + Interface_Constraints.json ──
    def test_bucket_reads_persisted_inputs(self):
        c01_update_answers(self.work, {
            "form_archetype": "desktop sensor",
            "primary_face": "front face",
            "exposed_components": "camera, led, usb-c",
            "cmf_direction": "industrial",
        }, "Desk AI sensor.")
        res = emit_c01_id_visual_package(self.work).to_dict()
        self.assertEqual("success", res["status"])


if __name__ == "__main__":
    unittest.main()
