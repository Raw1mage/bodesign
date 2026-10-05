import unittest

from bodesign_eda_bridge.decision_gate import (
    choose_power_architecture, choose_passive_package, choose_component_alternative,
)


class DecisionGateTests(unittest.TestCase):
    def test_power_options_and_determinism(self):
        prompts = []
        def ask(payload):
            prompts.append(payload)
            return "buck"
        result = choose_power_architecture(ask)
        self.assertEqual(result, choose_power_architecture(ask))
        self.assertEqual(result["selected_id"], "buck")
        self.assertTrue(result["requires_engineering_validation"])
        self.assertEqual([o["id"] for o in prompts[0]["options"]], ["ldo", "buck"])

    def test_packages(self):
        for size in ("0402", "0603", "0805"):
            self.assertEqual(choose_passive_package(lambda _: size)["selected_id"], size)

    def test_invalid_answers_no_default(self):
        for answer in (None, "", "LDO", ["ldo"], True, "unknown"):
            with self.subTest(answer=answer), self.assertRaisesRegex(ValueError, "INVALID_CHOICE"):
                choose_power_architecture(lambda _: answer)
        with self.assertRaisesRegex(ValueError, "CALLBACK_REQUIRED"):
            choose_power_architecture(None)

    def test_callback_errors_propagate(self):
        def ask(_):
            raise RuntimeError("UI unavailable")
        with self.assertRaisesRegex(RuntimeError, "UI unavailable"):
            choose_passive_package(ask)

    def test_bom_evidence_and_input_isolation(self):
        options = [{"id": "a", "mpn": "MPN-A", "label": "A", "description": "Candidate", "evidence": "datasheet-A"},
                   {"id": "b", "mpn": "MPN-B", "label": "B", "description": "Candidate", "evidence": "datasheet-B"}]
        def ask(payload):
            payload["options"][0]["mpn"] = "MUTATED"
            return "a"
        result = choose_component_alternative(options, ask)
        self.assertEqual(result["selected_option"]["mpn"], "MPN-A")
        self.assertEqual(result["selected_option"]["evidence"], "datasheet-A")
        result["selected_option"]["mpn"] = "CHANGED"
        self.assertEqual(options[0]["mpn"], "MPN-A")

    def test_invalid_options_do_not_prompt(self):
        good = {"id": "a", "mpn": "A", "label": "A", "description": "candidate"}
        for options in ([], [good], [good, good], [{"id": "a"}, good]):
            with self.assertRaises(ValueError):
                choose_component_alternative(options, lambda _: self.fail("must validate before prompting"))
