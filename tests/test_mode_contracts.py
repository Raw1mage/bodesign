import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    enter_c01_mode,
    layer_relevant_prd_sections,
    list_work_packets,
    return_blocker,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class ModeContractTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-mode-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_c01_relevant_sections_are_derived_from_template(self):
        sections = layer_relevant_prd_sections("C01")
        # s05 (ID/ME requirements) hands off to C01 per the committed template.
        self.assertIn("s05_id_me_requirements", sections)
        # s06 electrical does NOT hand off to C01.
        self.assertNotIn("s06_electrical_requirements", sections)

    def test_enter_c01_mode_dispatches_packet_and_emits_package(self):
        entry = enter_c01_mode(self.work, c00={"product": "wearable tracker"})
        # A C01 work packet was dispatched, scoped to the derived PRD sections.
        self.assertEqual(entry.packet["target_layer"], "C01")
        self.assertEqual(entry.packet["target_role"], "industrial_design")
        self.assertIn("s05_id_me_requirements", entry.packet["source"]["sections"])
        self.assertEqual([w.packet_id for w in list_work_packets(self.work)], ["C00-WP-0001"])
        # The Rockbox C01 package exists (under the C01-ID slot).
        self.assertTrue((self.work / "C01-ID" / "Ai file" / "Design_Direction.md").exists())
        self.assertTrue((self.work / "C01-ID" / "Interface_Constraints.json").exists())
        # And there is a next C01 preference question to ask the user.
        self.assertIn("question", entry.next_question)

    def test_blocker_path_from_c01_back_to_c00(self):
        entry = enter_c01_mode(self.work, c00={"product": "x"})
        packet_id = entry.packet["packet_id"]
        blk = return_blocker(
            self.work, packet_id, severity="decision",
            summary="Primary face is ambiguous from the PRD.",
            question_for_user="Which surface is the primary user-facing face?",
            affected_c00_fields=["s05_id_me_requirements"],
        )
        self.assertEqual(blk.source_layer, "C01")
        self.assertEqual(blk.proposed_state, "blocked")

    def test_enter_c01_mode_autoloads_c00_corpus_from_state(self):
        # Regression for the aiguard sand-table break: the autonomous loop calls
        # enter_c01_mode WITHOUT passing c00; it must auto-load C00's answered content
        # so C01 detects the real exposed components instead of emitting an empty package.
        from bodesign_workflow_core import scaffold_c00_prd_package
        scaffold_c00_prd_package(self.work, project_name="aiguard", include_rf=False)
        sp = self.work / "C00-PRD" / "answer_state.json"
        st = json.loads(sp.read_text())
        # Drop a realistic spec value (with component keywords) into the first field.
        doc = next(iter(st["documents"].values()))
        f = next(iter(doc["sections"][0]["fields"].values()))
        f["state"] = "answered"
        f["value"] = "OV5640 camera via DCMI, Wi-Fi/BLE antenna, USB-C, status LED, setup button"
        sp.write_text(json.dumps(st))

        entry = enter_c01_mode(self.work)  # NO c00 passed — must auto-load from state
        constraints = json.loads((self.work / "C01-ID" / "Interface_Constraints.json").read_text())
        names = {c["name"] for c in constraints["exposed_components"]}
        self.assertNotIn("missing — exposed component list not confirmed", names)
        self.assertTrue({"camera", "usb-c", "led", "antenna"} & names)

    def test_entry_to_dict_states_the_boundary(self):
        entry = enter_c01_mode(self.work, c00={"product": "x"})
        self.assertIn("does not", entry.to_dict()["boundary"].lower())


if __name__ == "__main__":
    unittest.main()
