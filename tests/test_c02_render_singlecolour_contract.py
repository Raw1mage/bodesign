"""Documentation contract for the C02 enclosure render's single-colour limitation.

BR_20260901 c02 render per-part colour, option C (dispatcher ruling): per-part
colouring is NOT supported, and the caller must learn that from the tool
description instead of discovering it by burning a round-trip.

BR_20260902 c02 voice_to_design single-colour disclosure: the SAME contract is
owed by the SECOND user-visible colour entry point. `bodesign_c02_voice_to_design`
takes its own `color` arg (server.py:322-328) and calls the same
`render_enclosure_model`, so a caller arriving through the voice loop never sees
the render tool's disclosure. The fact table below is deliberately NOT forked:
one `_REQUIRED_FACTS`, applied to every tool that exposes a `color` arg into the
C02 render path — a second table would let the two entry points drift apart
silently, which is the defect class this test exists to prevent.

WHAT THIS TEST ANSWERS (write the question beside the check, code-thinker §8):

  Q1 (positive): does EACH shipped description state all four required facts —
     STL carries no colour / color() is lost at export / one colour for the
     whole model / per-part colour map unsupported?
  Q2 (negative control): would the SAME predicate REJECT each tool's pre-fix
     description? If it accepts that text too, the predicate measures nothing
     FOR THAT TOOL — discriminating power is per (predicate, corpus) pair, not a
     property of the predicate alone.
  Q3 (forgery control): would it REJECT a description that falsely CLAIMS
     per-part support?

Q2/Q3 are what make Q1 evidence. A grep that returns empty proves nothing on
its own; these two make the empty result discriminating.
"""
import importlib
import unittest


# The four facts the description must carry. Each entry is
# (fact_id, tuple-of-accepted-substrings) — any ONE substring satisfies it, so
# wording may evolve without the contract silently evaporating.
_REQUIRED_FACTS = (
    ("stl_carries_no_colour", ("STL container carries NO colour", "STL carries no colour")),
    ("scad_colour_lost_at_export", ("DISCARDED at the c02_export_stl step", "discarded at the c02_export_stl step")),
    ("one_colour_whole_model", ("SINGLE-COLOUR BY DESIGN", "ONE colour for the WHOLE model")),
    ("no_per_part_map", ("PER-PART COLOURING IS NOT SUPPORTED", "never a per-part colour map")),
)

# Phrases that would be an affirmative FALSE claim of per-part support.
_FORBIDDEN_CLAIMS = (
    "per-part colour map is supported",
    "per-part color map is supported",
    "supports per-part colouring",
    "supports per-part coloring",
)

# The exact description shipped BEFORE this fix. It is factually true but says
# nothing about per-part colouring or about color() being lost — the ambiguity
# the BR was filed against. It is the negative control corpus.
_PRE_FIX_DESCRIPTION = (
    "Render a generated C02 enclosure STL (Enclosure.stl from c02_export_stl) to top/iso "
    "design-sketch PNGs — closes the 'voice-to-design' loop so a generated draft is *viewable*. "
    "Loads the STL natively via trimesh and rasterises offscreen via pyrender/EGL on the me worker "
    "(same backend as render_board_model). STL is already in mm; faces get a neutral enclosure grey "
    "since STL carries no colour, unless an optional CMF `color` (hex #RRGGBB[AA] / named EN+中文 "
    "e.g. white/黑/silver/銀 / RGB(A) array) is given for a single-colour design sketch. "
    "Output is marked prototype draft, not ME approval. Degrades to no-deps/no-gl rather than crashing."
)

# The exact description shipped for the SECOND entry point BEFORE BR_20260902.
# Verbatim from services/mcp/server.py:1213 at commit-time of that BR. It never
# mentions colour at all, so all four facts are missing — measured, not assumed.
_PRE_FIX_VOICE_TO_DESIGN_DESCRIPTION = (
    "Orchestrate the full voice-to-design loop: spoken intent → clarify → approval gate → "
    "enclosure source → STL → top/iso render. Calls plan_c02_intent; if constraints are "
    "incomplete returns the clarifying plan (no CAD); if ready and approve!=true returns the "
    "constraint set for confirmation (no CAD). Only with approve=true AND complete "
    "constraints+wall/clearance does it run generate_openscad → export_stl → render_enclosure, "
    "returning {status:approved, pipeline, images}. Honours the C02 approval gate and the "
    "no-guess-dimensions rule; degrades honestly when OpenSCAD CLI or GL is absent."
)

# Every tool that exposes a `color` arg feeding the C02 render path, paired with
# the text it shipped BEFORE its disclosure landed (its own negative-control
# corpus). Adding a third colour entry point means adding a row here — not
# copying the fact table.
_COLOUR_ENTRY_POINTS = (
    ("bodesign_c02_render_enclosure", _PRE_FIX_DESCRIPTION),
    ("bodesign_c02_voice_to_design", _PRE_FIX_VOICE_TO_DESIGN_DESCRIPTION),
)


def missing_facts(text: str) -> list[str]:
    """Fact ids the text fails to state. Empty list == contract satisfied."""
    return [fact for fact, accepted in _REQUIRED_FACTS
            if not any(sub in text for sub in accepted)]


def false_claims(text: str) -> list[str]:
    """Affirmative claims of per-part support found in the text."""
    low = text.lower()
    return [claim for claim in _FORBIDDEN_CLAIMS if claim in low]


class C02RenderSingleColourContractTests(unittest.TestCase):
    """One contract, applied to EVERY colour entry point into the C02 render path.

    Each assertion loops `_COLOUR_ENTRY_POINTS` and reports which tool failed via
    subTest, so a regression on the second entry point cannot hide behind a green
    first one — the failure names the tool.
    """

    def setUp(self):
        self.server = importlib.import_module("services.mcp.server")

    def _spec(self, tool_name: str) -> dict:
        return self.server.TOOLS_BY_NAME[tool_name]

    # ── Q1: every shipped description states the limitation ──────────────
    def test_shipped_description_states_every_required_fact(self):
        for tool_name, _ in _COLOUR_ENTRY_POINTS:
            with self.subTest(tool=tool_name):
                shipped = self._spec(tool_name)["description"]
                self.assertEqual([], missing_facts(shipped),
                                 f"{tool_name} description omits required single-colour facts")

    def test_shipped_description_makes_no_false_per_part_claim(self):
        for tool_name, _ in _COLOUR_ENTRY_POINTS:
            with self.subTest(tool=tool_name):
                self.assertEqual([], false_claims(self._spec(tool_name)["description"]))

    # ── Q2: negative control — the predicate must REJECT each old text ───
    def test_predicate_rejects_the_pre_fix_vague_description(self):
        # If any of these lists ever comes back empty, `missing_facts` has lost
        # its discriminating power FOR THAT TOOL's corpus and the matching Q1
        # assertion above is decoration. Discriminating power is a property of
        # the (predicate, corpus) pair, so each entry point needs its own row.
        for tool_name, pre_fix in _COLOUR_ENTRY_POINTS:
            with self.subTest(tool=tool_name):
                missing = missing_facts(pre_fix)
                self.assertNotEqual([], missing,
                                    f"predicate accepted {tool_name}'s pre-fix description; "
                                    "it discriminates nothing there")
                # It must reject for the RIGHT reasons, not incidentally.
                self.assertIn("scad_colour_lost_at_export", missing)
                self.assertIn("no_per_part_map", missing)

    def test_pre_fix_voice_to_design_was_silent_on_colour_entirely(self):
        # Sharper than the loop above: the second entry point said NOTHING about
        # colour, so all four facts are missing. Pinned as a literal so a future
        # weakening of _REQUIRED_FACTS shows up here as a shrinking list rather
        # than as a still-green suite.
        self.assertEqual(
            ["stl_carries_no_colour", "scad_colour_lost_at_export",
             "one_colour_whole_model", "no_per_part_map"],
            missing_facts(_PRE_FIX_VOICE_TO_DESIGN_DESCRIPTION))

    # ── Q3: forgery control — a false claim must be caught ───────────────
    def test_predicate_rejects_a_description_falsely_claiming_per_part_support(self):
        for tool_name, _ in _COLOUR_ENTRY_POINTS:
            with self.subTest(tool=tool_name):
                forged = self._spec(tool_name)["description"] + " Per-part colour map is supported."
                self.assertNotEqual([], false_claims(forged),
                                    f"a {tool_name} description claiming per-part support was accepted")

    # ── the API surface the descriptions describe must still be the one
    #    that exists: `color` stays a single string, no map field appeared ──
    def test_color_schema_is_still_a_single_string_and_no_map_field_exists(self):
        for tool_name, _ in _COLOUR_ENTRY_POINTS:
            with self.subTest(tool=tool_name):
                props = self._spec(tool_name)["schema"]["properties"]
                self.assertEqual("string", props["color"]["type"])
                for absent in ("part_colors", "color_map", "parts", "stl_paths"):
                    self.assertNotIn(absent, props,
                                     f"{absent} appeared on {tool_name}; "
                                     "the single-colour description is now stale")


if __name__ == "__main__":
    unittest.main()
