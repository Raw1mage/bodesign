"""BR_20260730b — compose must not accept an argument it cannot honour.

Two defects found by a consumer running compose through the MCP facade, both of
which returned success over work that had silently not happened:

  N1  `symbol_dirs` declared NO type in the tool's inputSchema, so an MCP client
      serialised the array to text. `["/work/symbols"]` arrived as the 17-char
      STRING '["/work/symbols"]', which is not a path and can never exist. The
      str branch of the symbol_dirs merge wrapped it in a list, every custom
      library failed to resolve, and only the KiCad stdlib still loaded — so the
      run looked partly healthy (stock passives placed, nets counted) and the
      error blamed the callee's disk: "library not found in ['[\"/work/...\"]']".

  N2  A spec with no `components` key composed a 213-byte schematic holding zero
      symbols, and FOUR gates each truthfully blessed it: draftsman gate PASS
      (rects=0 — nothing cannot overlap), ERC 0 violations (nothing cannot be
      miswired), validation status="validated", call ok:true. Four green lights
      over an empty deliverable.

The decisive evidence for N1 was a single facade call in which `spec` (schema
`{"type": "object"}`) arrived as a real dict while `symbol_dirs` (schema `{}`)
arrived as text — same client, same transport, same request. Declared type
survived; undeclared type did not. Hence the schema assertions here: the fix is
half in composer (detect + refuse) and half in the schema (stop producing it).

These tests import from `bodesign_eda_bridge.composer` directly (the convention
`SymbolLoadError`'s tests already follow) and never require pcbnew, so they run
on a bare host rather than skipping into a false green.
"""

from __future__ import annotations

import ast
import json
import re
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SERVER_PY = REPO / "services" / "mcp" / "server.py"
COMPOSER_PY = REPO / "packages" / "eda-bridge" / "bodesign_eda_bridge" / "composer.py"

# A minimal well-formed spec: two parts, two nets. Used as the "everything else
# is fine" baseline so a failure can only be about the argument under test.
GOOD_SPEC = {
    "components": [
        {"ref": "U9", "symbol": "buck_3v3:TPS62826", "value": "TPS62826",
         "footprint": "Package_SON:VSON-HR-8"},
        {"ref": "C9", "symbol": "Device:C", "value": "10uF",
         "footprint": "Capacitor_SMD:C_0805_2012Metric"},
    ],
    "nets": [
        {"name": "VIN", "nodes": [["U9", "1"], ["C9", "1"]]},
        {"name": "GND", "nodes": [["U9", "4"], ["C9", "2"]]},
    ],
}


def _compose():
    from bodesign_eda_bridge.composer import compose_schematic
    return compose_schematic


class TestJsonEncodedSymbolDirsIsRefused(unittest.TestCase):
    """N1: a JSON-encoded list is not a directory — say so, do not search for it."""

    def test_encoded_list_raises_instead_of_becoming_a_bogus_path(self):
        from bodesign_eda_bridge.composer import SymbolDirsEncodingError
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(SymbolDirsEncodingError) as ctx:
                _compose()(out, "probe", GOOD_SPEC,
                           symbol_dirs='["/work/experiments/symbols"]')
        msg = str(ctx.exception)
        # The raw value AND the decoded form, so the caller can see what to pass.
        self.assertIn('["/work/experiments/symbols"]', msg)
        self.assertIn("/work/experiments/symbols", msg)
        self.assertIn("JSON-encoded list", msg)

    def test_the_error_carries_the_decoded_value_as_data_not_only_prose(self):
        # A caller fixing this programmatically should not have to parse English.
        from bodesign_eda_bridge.composer import SymbolDirsEncodingError
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(SymbolDirsEncodingError) as ctx:
                _compose()(out, "probe", GOOD_SPEC, symbol_dirs='["/a", "/b"]')
        self.assertEqual(ctx.exception.decoded, ["/a", "/b"])
        self.assertEqual(ctx.exception.raw, '["/a", "/b"]')

    def test_it_points_at_the_schema_as_the_likely_cause(self):
        # The consumer who hit this spent a whole round believing their symbol
        # libraries were broken. The error should name the actual mechanism.
        from bodesign_eda_bridge.composer import SymbolDirsEncodingError
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(SymbolDirsEncodingError) as ctx:
                _compose()(out, "probe", GOOD_SPEC, symbol_dirs='["/work/x"]')
        self.assertIn("inputSchema", str(ctx.exception))

    def test_it_refuses_rather_than_silently_decoding(self):
        # Auto-decoding would "work" and hide the schema defect that produced it
        # — a fallback that repairs the caller's bug invisibly. The 天條 says
        # fail loud, so assert the refusal is a raise and not a repair.
        from bodesign_eda_bridge.composer import SymbolDirsEncodingError
        self.assertTrue(issubclass(SymbolDirsEncodingError, TypeError))
        src = COMPOSER_PY.read_text()
        window = src[src.find("SymbolDirsEncodingError(symbol_dirs") - 700:
                     src.find("SymbolDirsEncodingError(symbol_dirs") + 200]
        self.assertIn("raise SymbolDirsEncodingError", window)
        self.assertNotIn("symbol_dirs = _decoded", src,
                         "decoding the caller's mistake instead of reporting it "
                         "is the silent fallback this BR line exists to remove")


class TestRealSymbolDirsStillWork(unittest.TestCase):
    """Reverse discrimination for N1.

    Without these, `raise SymbolDirsEncodingError` on ANY string would pass every
    refusal test above while making the argument unusable. The detector must be
    narrow: only a string that really is an encoded list.
    """

    def _dirs_arg_reaches_merge(self, value) -> bool:
        """True when `value` survives the encoding check (does not raise it)."""
        from bodesign_eda_bridge.composer import SymbolDirsEncodingError
        with tempfile.TemporaryDirectory() as out:
            try:
                _compose()(out, "probe", GOOD_SPEC, symbol_dirs=value)
            except SymbolDirsEncodingError:
                return False
            except Exception:
                # Any OTHER failure (missing lib, no kicad-cli) means the value
                # got past the encoding gate, which is what this asserts.
                return True
        return True

    def test_a_real_list_is_not_mistaken_for_an_encoded_one(self):
        self.assertTrue(self._dirs_arg_reaches_merge(["/work/experiments/symbols"]))

    def test_a_bare_path_string_is_not_mistaken_for_an_encoded_one(self):
        self.assertTrue(self._dirs_arg_reaches_merge("/work/experiments/symbols"))

    def test_a_directory_whose_name_starts_with_a_bracket_still_works(self):
        # The check is deliberately narrow: leading '[' AND valid JSON AND
        # decodes to a list. A real (if odd) directory name must pass through.
        self.assertTrue(self._dirs_arg_reaches_merge("/work/[staging]/symbols"))

    def test_a_json_object_string_is_not_treated_as_an_encoded_list(self):
        # '{"a": 1}' is encoded JSON but not a list; it is not this defect and
        # must not be reported as it.
        self.assertTrue(self._dirs_arg_reaches_merge('{"a": 1}'))

    def test_none_still_means_stdlib_only(self):
        self.assertTrue(self._dirs_arg_reaches_merge(None))


class TestEmptySpecIsRefused(unittest.TestCase):
    """N2: refuse the empty deliverable before four gates can bless it."""

    def test_spec_without_components_raises(self):
        from bodesign_eda_bridge.composer import EmptySpecError
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(EmptySpecError):
                _compose()(out, "probe", {"nets": []})

    def test_the_observed_trigger_names_the_keys_it_got(self):
        # The recorded case passed {"__spec_file__": "..."} — a caller guessing
        # that `spec` accepts a file reference. The error must show BOTH sides of
        # the key-name mismatch, because that is the entire fault.
        from bodesign_eda_bridge.composer import EmptySpecError
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(EmptySpecError) as ctx:
                _compose()(out, "probe", {"__spec_file__": "/work/spec.json"})
        msg = str(ctx.exception)
        self.assertIn("__spec_file__", msg, "must echo the key actually received")
        self.assertIn("components", msg, "must name the key it wanted")
        self.assertEqual(ctx.exception.spec_keys, ["__spec_file__"])

    def test_it_explains_why_a_green_gate_did_not_help(self):
        # Whoever hits this saw ok:true and PASS. The error has to reconcile
        # that, or it reads as a contradiction of what they just observed.
        from bodesign_eda_bridge.composer import EmptySpecError
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(EmptySpecError) as ctx:
                _compose()(out, "probe", {})
        msg = str(ctx.exception)
        self.assertIn("COMPOSE_EMPTY_SPEC", msg, "typed code for programmatic handling")
        self.assertIn("ERC", msg)

    def test_an_explicitly_empty_component_list_is_also_refused(self):
        # `{"components": []}` is the same empty deliverable as a missing key.
        from bodesign_eda_bridge.composer import EmptySpecError
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(EmptySpecError):
                _compose()(out, "probe", {"components": [], "nets": []})

    def test_a_populated_spec_is_not_refused(self):
        # Reverse discrimination: an unconditional raise would pass all of the
        # above and break every real caller.
        from bodesign_eda_bridge.composer import EmptySpecError
        with tempfile.TemporaryDirectory() as out:
            try:
                _compose()(out, "probe", GOOD_SPEC, symbol_dirs=None)
            except EmptySpecError:
                self.fail("a spec WITH components must never raise EmptySpecError")
            except Exception:
                pass  # any other failure is out of scope here

    def test_the_sibling_all_skipped_guard_still_exists(self):
        # N2 is the "never declared" half; the "declared but all skipped" half
        # predates it. Removing either reopens a path to the same empty sheet.
        src = COMPOSER_PY.read_text()
        self.assertIn("COMPOSE_ALL_COMPONENTS_SKIPPED", src)
        self.assertIn("if raw_components and not parsed:", src)


class TestKnownKeysIsDerivedNotHandCopied(unittest.TestCase):
    """`EmptySpecError.KNOWN_KEYS` duplicates a fact the code already states.

    The error advertises which spec keys compose reads. That list is a hand-copy
    of the real `spec.get(...)` call sites — the V4-c duplicate-fact shape this
    repo lints for (the same defect that made `_EE_GROUP_TOOLS` drift twice).
    Assert the copy against the source of truth so it cannot silently rot into
    telling callers to use a key that no longer exists.
    """

    def _real_spec_keys(self) -> set[str]:
        tree = ast.parse(COMPOSER_PY.read_text())
        keys: set[str] = set()
        for node in ast.walk(tree):
            # spec.get("key" ...)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "spec"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
            # spec["key"]
            if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                    and node.value.id == "spec"
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)):
                keys.add(node.slice.value)
        return keys

    def test_the_ast_scan_actually_finds_something(self):
        # Reverse discrimination for the scan itself: a broken walk returning an
        # empty set would make the comparison below vacuously pass forever.
        found = self._real_spec_keys()
        self.assertIn("components", found,
                      "AST scan found no spec key reads — the scan is broken, "
                      "so the comparison below proves nothing")
        self.assertGreaterEqual(len(found), 3)

    def test_every_spec_key_compose_reads_is_advertised(self):
        from bodesign_eda_bridge.composer import EmptySpecError
        missing = self._real_spec_keys() - set(EmptySpecError.KNOWN_KEYS)
        self.assertEqual(
            missing, set(),
            f"compose reads spec keys the error does not advertise: {sorted(missing)} "
            f"— a caller told to use {list(EmptySpecError.KNOWN_KEYS)} would not "
            f"discover them",
        )

    def test_it_does_not_advertise_keys_compose_ignores(self):
        # The other direction: promising a key that is silently ignored is worse
        # than omitting it, because the caller will set it and see no effect.
        from bodesign_eda_bridge.composer import EmptySpecError
        phantom = set(EmptySpecError.KNOWN_KEYS) - self._real_spec_keys()
        self.assertEqual(
            phantom, set(),
            f"advertised spec keys that compose never reads: {sorted(phantom)}",
        )


class TestFacadeSchemaDeclaresSymbolDirsType(unittest.TestCase):
    """The schema half of the N1 fix: stop producing the encoded string.

    Detecting the encoding in composer turns a silent degradation into a loud
    error, which is necessary but not sufficient — the caller still cannot make
    a correct call. The MCP inputSchema is the ONLY documentation an MCP client
    sees at call time (BR_20260729 §J), so the type has to be declared there.
    """

    def _compose_schema(self) -> dict:
        src = SERVER_PY.read_text()
        start = src.find('"name": "bodesign_compose_schematic"')
        self.assertNotEqual(start, -1, "compose tool entry not found in server.py")
        return src[start:start + 4000]

    def test_symbol_dirs_is_no_longer_an_untyped_schema(self):
        self.assertNotIn(
            '"symbol_dirs": {}', SERVER_PY.read_text(),
            "an untyped inputSchema is what let a client serialise the array to "
            "text in the first place",
        )

    def test_symbol_dirs_declares_a_single_array_type_never_a_union(self):
        # BR_20260730b §P: the anyOf that "fixed" N1 was itself a stringify
        # trigger. Declaring the union makes clients serialise the list to text
        # exactly like the untyped schema did, so a multi-directory call became
        # unmakeable while the error message still demanded a real array. The
        # schema must be NARROWER than the runtime, not a union of both shapes.
        seg = self._compose_schema()
        m = re.search(r'"symbol_dirs":\s*\{(.{0,400}?)"description"', seg, re.S)
        self.assertIsNotNone(m, "symbol_dirs schema shape not found")
        decl = m.group(1)
        self.assertNotIn('"anyOf"', decl,
                         "a union declaration is what breaks multi-value transport")
        self.assertNotIn('"oneOf"', decl)
        self.assertIn('"type": "array"', decl)

    def test_the_schema_description_warns_about_the_encoding_failure(self):
        # A type declaration alone does not tell a caller what goes wrong when a
        # client ignores it. §J's lesson: the schema is the documentation.
        seg = self._compose_schema()
        m = re.search(r'"symbol_dirs":.{0,3000}?"description":\s*"(.*?[^\\])"', seg, re.S)
        self.assertIsNotNone(m, "symbol_dirs description not found")
        desc = m.group(1)
        self.assertIn("BR_20260730b", desc, "trace the warning to its evidence")
        for expected in ("array", "SymbolDirsEncodingError"):
            self.assertIn(expected, desc)

    def test_the_schema_is_valid_json_schema_shaped(self):
        # A malformed schema fragment would break tools/list for every client,
        # which is a worse outcome than the bug being fixed.
        import importlib.util
        spec_src = SERVER_PY.read_text()
        # Extract the whole TOOLS literal is impractical; assert the fragment
        # parses as a Python literal instead.
        seg = self._compose_schema()
        m = re.search(r'"symbol_dirs":\s*(\{.*?\}),\n', seg, re.S)
        self.assertIsNotNone(m)
        try:
            node = ast.literal_eval(m.group(1).replace("_STR", '{"type": "string"}'))
        except (ValueError, SyntaxError) as exc:
            self.fail(f"symbol_dirs schema is not a valid literal: {exc}")
        self.assertIsInstance(node, dict)
        self.assertEqual(node.get("type"), "array")
        # Round-trips through JSON, i.e. a client can actually receive it.
        json.dumps(node)


if __name__ == "__main__":
    unittest.main()
