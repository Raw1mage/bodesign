"""Documentation contract for the C02 enclosure render's single-colour limitation.

BR_20260901 c02 render per-part colour, option C (dispatcher ruling): per-part
colouring is NOT supported, and the caller must learn that from the tool
description instead of discovering it by burning a round-trip.

WHAT THIS TEST ANSWERS (write the question beside the check, code-thinker §8):

  Q1 (positive): does the SHIPPED description state all four required facts —
     STL carries no colour / color() is lost at export / one colour for the
     whole model / per-part colour map unsupported?
  Q2 (negative control): would the SAME predicate REJECT the pre-fix vague
     description? If it accepts that text too, the predicate measures nothing.
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


def missing_facts(text: str) -> list[str]:
    """Fact ids the text fails to state. Empty list == contract satisfied."""
    return [fact for fact, accepted in _REQUIRED_FACTS
            if not any(sub in text for sub in accepted)]


def false_claims(text: str) -> list[str]:
    """Affirmative claims of per-part support found in the text."""
    low = text.lower()
    return [claim for claim in _FORBIDDEN_CLAIMS if claim in low]


class C02RenderSingleColourContractTests(unittest.TestCase):
    def setUp(self):
        self.server = importlib.import_module("services.mcp.server")
        self.spec = self.server.TOOLS_BY_NAME["bodesign_c02_render_enclosure"]
        self.description = self.spec["description"]

    # ── Q1: the shipped description states the limitation ────────────────
    def test_shipped_description_states_every_required_fact(self):
        self.assertEqual([], missing_facts(self.description),
                         "shipped description omits required single-colour facts")

    def test_shipped_description_makes_no_false_per_part_claim(self):
        self.assertEqual([], false_claims(self.description))

    # ── Q2: negative control — the predicate must REJECT the old text ────
    def test_predicate_rejects_the_pre_fix_vague_description(self):
        # If this list ever comes back empty, `missing_facts` has lost its
        # discriminating power and the Q1 assertion above is decoration.
        missing = missing_facts(_PRE_FIX_DESCRIPTION)
        self.assertNotEqual([], missing,
                            "predicate accepted the pre-fix description; it discriminates nothing")
        # It must reject for the RIGHT reasons, not incidentally.
        self.assertIn("scad_colour_lost_at_export", missing)
        self.assertIn("no_per_part_map", missing)

    # ── Q3: forgery control — a false claim must be caught ───────────────
    def test_predicate_rejects_a_description_falsely_claiming_per_part_support(self):
        forged = self.description + " Per-part colour map is supported."
        self.assertNotEqual([], false_claims(forged),
                            "a description claiming per-part support was accepted")

    # ── the API surface the description describes must still be the one
    #    that exists: `color` stays a single string, no map field appeared ──
    def test_color_schema_is_still_a_single_string_and_no_map_field_exists(self):
        props = self.spec["schema"]["properties"]
        self.assertEqual("string", props["color"]["type"])
        for absent in ("part_colors", "color_map", "parts", "stl_paths"):
            self.assertNotIn(absent, props,
                             f"{absent} appeared; the single-colour description is now stale")


if __name__ == "__main__":
    unittest.main()
