import base64
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bodesign_workflow_core import assess_c01_package_readiness, emit_c01_rockbox_package, generate_c01_concept_image


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


if __name__ == "__main__":
    unittest.main()
