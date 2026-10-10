"""S1 readability instrument -- calibration gate (master DD-14 / AC16), round 2.

Two exemplar populations, both required:

  REJECTING  the archived CP3 leaf renders that carry an independent NO on file
             (usbc / power_rail / battery, reviewer notes copied verbatim into the
             fixture dir). The instrument must return a NON-EMPTY offender set
             naming the class(es) the reviewer named. A YES here = instrument
             rejected; thresholds are not tuned to pass.
  ACCEPTING  a hand-verified clean fixture (divider + cap, every local net drawn,
             dots only at real 3-branch meets, no crossings, no text clash)
             natively exported with kicad-cli 9.0.9 and carrying an export
             receipt. Classes a-e must return an EMPTY offender set.
  B1 CONTROL a fixture with a DOTTED foreign contact (declared NETB wired onto
             NETA under a junction dot). Round-2 invariant 2: the union at the
             dot must not erase the conflict. B1 must fire with declared intent;
             without it the contact is not "clean" -- the class reports the
             identity source and d reports not_assessed for the shunt.

Every fixture is sha256-pinned; a byte drift fails the pin test before any
class assertion runs.

CP1 / CP2 cells: no source/render pairs exist on disk (officer search
2026-10-06: 0/25 PNG hashes match). Permanently BLOCKED, not reconstructed.

Provenance (round-2 invariant 1): the CP3 archived .net predates its .kicad_sch
by ~55 min. Their export receipts record the regenerated-netlist lineage, so
measuring against the archived .net reports provenance=mismatch and
verdict=indeterminate while retaining every finding. This is asserted, not
hidden.

This instrument models the cited failure classes; it is not equivalent to human
perception and a pass does not replace the fresh-eyes gate.
"""
import hashlib
import json
import unittest
from pathlib import Path

from bodesign_eda_bridge.readability_render import (
    CALIBRATION_RECORD_SCHEMA,
    DOES_NOT_AUTHORIZE,
    POLICY,
    ReadabilityInputError,
    measure,
    parse_sexpr,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "readability_render"
CP3 = FIX / "cp3"
CLEAN = FIX / "clean"
B1 = FIX / "b1"

# sha256 of the exact bytes measured. CP3 = archive copy of
# /home/pkcs12/.cache/scratch/p2-leaf-delivery/first/ (2026-10-06 06:43 render).
PINS = {
    "e_label_flag/usbc_r6.kicad_sch": "8cd238d2f87a36056d6e035c8b29cb92057c253de03af766fa6d86c18f3da24c",
    "e_label_flag/usbc_r6.svg": "7e7a1d2d3aea05498f9236097152b8de605d2bf580db1ea35f6614a015536d45",
    "e_label_flag/usbc_r6.net": "4b83aae76d9f186de431f3f4a67e431b23f6ed68b631bdcb4f7a4dd3a57583b3",
    "e_label_flag/power_rail_r7.kicad_sch": "8d5e3e7d5d5731e645b3de796833d12ccaada7c39d8c971ad140efbe0fb8c6fd",
    "e_label_flag/power_rail_r7.svg": "c55ea2a767e871f539af13ab861162dc51ac0c2588861de6794a48d157840907",
    "e_label_flag/power_rail_r7.net": "cecc3c0f9a5e4af7a6b2b2a2655d22384f54c6f1b899b40b671e6cd538a344cc",
    "e_label_flag/adjacent_pin_synthetic.kicad_sch": "5e8dba4d25a1fd949efcb13b7cdf1b3a3882a0fd53dcfd1829a59b7bcd431e9a",
    "e_label_flag/adjacent_pin_synthetic.net": "a656ebed5399e8e501162607b0ba1e7ed022cdcf64481d6f3b23a1ea2b4b2973",
    "e_label_flag/adjacent_pin_synthetic.svg": "d91ef331dfcba817080bd028f0c74fe67db115b3469b0b7532a8c0590ee49639",
    "e_label_flag/power_rail_v4_site1.kicad_sch": "48a63e6606a37066c329227d874e8b33b9ce051b7336b54aaeb35cec1f772816",
    "e_label_flag/power_rail_v4_site1.net": "f8ee3ba8102f7b182777b7862086f894b9a604b44bd356fccaf1566450814d2e",
    "e_label_flag/power_rail_v4_site1.svg": "7d1bfd8f860a2c2bdb28bca357282ccaabebea47806b1bd5adfc085a29953017",
    "cp3/usbc.kicad_sch": "63432d2fe61134d3f78cbfd542b6add59eff25a1f401104593aef1e8796f2760",
    "cp3/usbc.svg": "1e670c1a2c51b93c8bd7ee26911ef56e27635a1655bd905a7ff207ceab1ad8f8",
    "cp3/usbc.archived.net": "2fb48c0911fa6dbe720cae2df9c76560d07634f4587dc1a9c26f0b1150e0205e",
    "cp3/usbc.reviewer-cp3.md": "393fdfbffbd987c6e1db968a8197e6f53be094ae67c3b7f8521b408ef3c92d74",
    "cp3/usbc.export-receipt.json": "bd69948f4893ffe59f02d829c133f8cc5f2febe6f7e92924981534ddf5ea8d0f",
    "cp3/power_rail.kicad_sch": "e91672c4f35990263274ca5f57c72a5ba543b41aa45004ac64ccc6809dc2f933",
    "cp3/power_rail.svg": "bf19a2bd51ee84b2e38397d13dd36b670a0cb2d28235d38ef4571ed6dfd87289",
    "cp3/power_rail.archived.net": "97a2f6ec57569c9930964ccf45ab2bda5c6f1988dc6f250559bdc8761d860c18",
    "cp3/power_rail.reviewer-cp3.md": "b04e7c330da2bdc6052efa3222031926af04c1669d2a2a536bc4f6133c2f142d",
    "cp3/power_rail.export-receipt.json": "9d4ca8931004558f0e20c4d2d8ca97480c62ff0cf8275870c5ac845cec96f195",
    "cp3/battery.kicad_sch": "71375ea2e32a0d787add272131d33c8ae885474c67baadf45ed76219dea38f61",
    "cp3/battery.svg": "ee3a50a6174be8b2da2e33ceeb1a221ebb955e8336a37a5a3404e2956f229d9b",
    "cp3/battery.archived.net": "922152aa88938cb6799833a205f283088c1562e4c644849fce845131cbf750dd",
    "cp3/battery.reviewer-cp3.md": "710aa68c9720a3fb6384b167e350b220eb288ebb449a875f27eb1bd15f04433b",
    "cp3/battery.export-receipt.json": "3a87b5514dffbb320b98e82c31a8b8cdd969703f645d8bd3e4bb1d4e3cfa1c64",
    "clean/clean_divider.kicad_sch": "606b142d71c2c0d8dddc9cb97c63e64294b971e5a2139d2ef68a53983e7dde62",
    "clean/clean_divider.svg": "01be7b193daad9696560fe94b22b4a6efad41b1f2931a0dfb844e25d9671861b",
    "clean/clean_divider.net": "7c6b2d9a14c961f75078d05ed9b1bde5015a647c6c8c4f5d96dd2a86dd92d52d",
    "clean/clean_divider.export-receipt.json": "1df4429399d0883efd95586887bd386cafe29e07a0b52b072926186ebaaaa8e2",
    "b1/b1_dotted_contact.kicad_sch": "306a0dabc4f2b94580fc6aa5a1f5b25d239f5089dfd220edcbc1bb9ef15ad542",
    "b1/b1_dotted_contact.svg": "11fc987275346723d57cc452e3c80431d5623409453b648df9c49ebc537e531c",
    "b1/b1_dotted_contact.net": "3e5fce5cb0c20ebffb9f4b7122d9059e70d7c190feb0321b8ca7bab79d3a84ca",
    "b1/b1_dotted_contact.export-receipt.json": "ca98f0c094194796c74db4422b5cdaba14f3b0da4eff96fac8d0bb879935bae3",
    # round 5: immutable copy of S3 run-20261006-133234 (usbc, ELK path first leaf)
    "s3_usbc_20261006/usbc.kicad_sch": "dcfdc6b2e6ac2d830922b6e56cd02190ccd30439dc3e495dc66918ba20095bf5",
    "s3_usbc_20261006/usbc.svg": "28bd7d5e7355ec5e6711439700d18fb4c564c8ce7899a18cee45679c398e91c8",
    "s3_usbc_20261006/usbc.net": "aed12f2f50943e7293e5d8c3df91450716423f23d2971ee11d16c230e164fa8a",
    "s3_usbc_20261006/usbc.export-receipt.json": "58e79522652937b2dc86d4ed6276afb782678ef8d7a37c74560acd0b6fe7b659",
    "s3_usbc_20261006/s1_invocation.json": "780d6c81dd26fcf99c1635ae2427b9da8a1e43e509c1e22e09d756f2f07dc0f3",
    # round 6: hand-built transform fixtures (native kicad-cli 9.0.9 export) + run-150709 copy
    "xform/r150709/s1_invocation.json": "b807e443ec39d5da61532efe3b0e16cf77715fc4e8c77390ac5e7a550a7fe8e6",
    "xform/r150709/s1_report.json": "3164f85e5d36ee32805afaae9bd98caa78eb164ba1ff1318746d902d9ae990f7",
    "xform/r150709/usbc.export-receipt.json": "791e196966b0d021ab9577559b6eda4d5ff3765c9da0f291167b8c6c3e692760",
    "xform/r150709/usbc.kicad_sch": "9db00c805f478d19eda73794e78281b4e49a117402467ce8032e75d39c931418",
    "xform/r150709/usbc.net": "677e8d08c415ed58b2d31f088e8525836842fede9f6bdb1e4d7c36afa52bb790",
    "xform/r150709/usbc.svg": "8cc7f3228758c563d9d52ca844725c42992c99b432a02a45991bad2c927ee6ac",
    "xform/sweep_r270_my.kicad_sch": "626e23fbb5eb30f4e7834022f91fa4dee97b5cfeb726467ffc9cb3fda7f711bd",
    "xform/sweep_r270_my.svg": "559028b1f1a461fa6e253fd4b6af9db9814a57db544904ee84b3d9e6b7cf89f5",
    "xform/sweep_r90_mx.kicad_sch": "4d1eb4befb88c8b634092260f418e090810601b435b0b84cf5ef08c49dc89909",
    "xform/sweep_r90_mx.svg": "bb8696512c5244217286c2f5626b26bb025ee19bf51972f9dc83b256de5f52a5",
    "xform/xm.export-receipt.json": "58de53b72e601d7b11d23ef9b34a2ef6d470350dd9c70cfb46353675686767ac",
    "xform/xm.kicad_sch": "6182109855067eff229b6da892fdc0b4175f68888ea6b82f855de45ab90c8b7f",
    "xform/xm.net": "fa961ffe75f5a81fa1888fd718d920d942a9bbbec12632e3af8808fbb1c249cc",
    "xform/xm.svg": "8b37e608303bf4aae1fa89129c92229cd211db1ff2314b254ed47be5e561cb29",
    "xform/xr180.export-receipt.json": "9665a1f63e151dc250999f85e29659eab00a0f501d113c420fe4f9911362e415",
    "xform/xr180.kicad_sch": "27a24cb52ccbb980b288a122e4516192e8d39ad758dd7b6a74166bb8184dac2a",
    "xform/xr180.net": "55b90ae4d7605f9ccdb21e80a39edbc4c73c5fa86e5f0adb0319a4021171cd75",
    "xform/xr180.svg": "74ab65557e15b691542c372a818a1bfc2b63c3bc7442daba991d4eb602f7e8e4",
    # round 9: byte-preserving copy of S3 run-r5b-s1-165624 (the one real subject with a sheet rectangle)
    "r5b_usbc_20261006/usbc.kicad_sch": "1a898ecc9158197e9d403b9a8fcc5886ba578aa86d303a8f463f38d17185856b",
    "r5b_usbc_20261006/usbc.net": "188cc95ccbe36242878750ef6f2637b45c02485e2cb9b724f2eb19f9fbb993f2",
    "r5b_usbc_20261006/usbc.svg": "54fca7ad2508d686f15d0cdb7a455181c65fc3096a8b031dceea29510009f10b",
    "r5b_usbc_20261006/usbc.export-receipt.json": "3619b26b92ad60bc9996c4a565c51ce748f4dba7f3297b1d8df9dbe408a41bc6",
    "r5b_usbc_20261006/README.md": "781856bfd768d88c5a5f18f420f856db270fbc2dea8946ab98c70b1fdbe21295",
    "r5b_usbc_20261006/MANIFEST.sha256": "19d75d0213032c821534a0ee8e722317685a6a41cbd0002b03872f7d848a5511",
    # round 9: synthetic ink fixtures = clean_divider + one root-level rectangle, native kicad-cli 9.0.9 export
    "synthetic_ink/ac3_wire_cross.kicad_sch": "55058743e66c395dc7d6c576612209eed039db731027ce1267965ad6302104f5",
    "synthetic_ink/ac3_wire_cross.net": "e92b8f9cd3fae747583c61d1f9dd4f86b3c1b03cc1391274efead782980fa517",
    "synthetic_ink/ac3_wire_cross.svg": "fe4dd202430b4f5999c324413e083346271da01438d32940aae06da1e58f539e",
    "synthetic_ink/ac3_wire_cross.export-receipt.json": "90311ac6ac55688580d8087d74c2d841cd2d6046d5757f24e9b493ba73137025",
    "synthetic_ink/ac4_enclose_two_pins.kicad_sch": "2c845462b2a2e32e3a06165375b3ccb066993d984b929f09f60ebe2f3447ee26",
    "synthetic_ink/ac4_enclose_two_pins.net": "eb37ce7499385d3ca1400adb6b03ab4e48d0f79845bbed1b184e3081fee6de95",
    "synthetic_ink/ac4_enclose_two_pins.svg": "08c7cddc26059e3411273614442b6bc856d0059c4ad33f2c4183f5d0a6246976",
    "synthetic_ink/ac4_enclose_two_pins.export-receipt.json": "db8248175105c9c6a7b3fdf033017f0537d049065990962b1843998abb5a8f7e",
}

# Reviewer -> class mapping (from the verbatim CP3 notes). "classes" is MY mapping
# of the reviewer's cited defects onto a-f; "evidence" localizes the SAME defect.
# Classes the instrument flags beyond this set are UNADJUDICATED EXTRAS, not
# confirmed false positives (no reviewer ruled on them).
REVIEWER_CELLS = {
    "usbc": {
        "verdict": "NO",
        "classes": {"a", "c", "d", "f"},
        "evidence": {
            # "F1 bypassed: VBUS_CON wire runs along top rail past F1 top pin"
            "d": ("D_DOT_ON_PIN_CONTINUES", "F1"),
            "a": ("A_DOT_ON_PIN_TIP", "F1.1"),
            # "R1/R2 not wired to J1 (label-only)"
            "c": ("C_PIN_LABEL_ONLY", "R1.1"),
            # "D1 refdes/GND flag/value overlap" (text clash) -> class f
            "f": ("F_WIRE_THROUGH_TEXT", "VBUS_CON"),
        },
    },
    "power_rail": {
        "verdict": "NO",
        "classes": {"b", "c", "e", "f"},
        "evidence": {
            # "L1 not wired to U1 SW (label-only SW_NODE both ends)"
            "c": ("C_PIN_LABEL_ONLY", "L1.1"),
            # "ISET2 vertical runs adjacent to all U1 left pin tips"
            "e": ("E_PIN_ROW_CORRIDOR", "U1.13"),
            # "crossed by VBUS ... wires" with no junction dot
            "b": ("B2_FOREIGN_CROSS_NO_DOT", "/ISET2"),
            # "VBUS label over pin-2 name"
            "f": ("F_TEXT_TEXT_OVERLAP", "VBUS"),
        },
    },
    "battery": {
        "verdict": "NO",
        "classes": {"c", "e", "f"},
        "evidence": {
            # "Q1 pin 2 has only a plain-text BAT_EXT at pin end (no wire)"
            "c": ("C_PIN_LABEL_ONLY", "Q1.2"),
            # "BAT_EXT wire ... runs rightward straight through the J2 connector body"
            "e": ("E_WIRE_THROUGH_BODY", "J2"),
            # "BAT_EXT label text overprinted on J2 pin 1 stub, pin number 1"
            "f": ("F_TEXT_TEXT_OVERLAP", "BAT_EXT"),
        },
    },
}

# Declared circuit intent for the B1 fixture: R3.1 is NETB, but the drawing dots
# it onto the NETA rail at (60,40). Native export fuses them (one net), so only the
# declared authority can expose the dotted foreign contact.
B1_DECLARED = {"R1.1": "NETA", "R2.1": "NETA", "R3.1": "NETB",
               "R1.2": "GND", "R2.2": "GND", "R3.2": "GND",
               "R4.1": "SHUNT", "R4.2": "SHUNT"}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _policy_digest() -> str:
    return hashlib.sha256(repr(sorted(POLICY.items())).encode()).hexdigest()[:16]


def _rejecting_entries(cls: str) -> list[dict]:
    """Content-bound rejecting evidence: every CP3 cell whose reviewer named
    `cls` -> (render hash, reviewer decision ref). Classes no reviewer named
    have NO rejecting evidence; the record must not invent any."""
    return [{"artifact_sha256": PINS[f"cp3/{leaf}.svg"],
             "decision_ref": f"cp3/{leaf}.reviewer-cp3.md#NO"}
            for leaf, cell in REVIEWER_CELLS.items() if cls in cell["classes"]]


def _calibration_record(policy_digest: str | None = None, classes: str = "abcde",
                        accepting: dict[str, list[dict]] | None = None,
                        rotations: list | None = None) -> dict:
    """The evidence we actually hold on 2026-10-06: CP3 rejecting cells x3 with
    independent NO decisions, and NO independently reviewed accepting case for
    any class (the clean fixture is hand-verified by this worker only -- that is
    not an independent YES and is not cited). `accepting` lets a test inject a
    hypothetical YES to prove the resolver would accept real evidence; it is
    never used to claim calibration in the receipt."""
    acc = accepting or {}
    return {
        "schema": CALIBRATION_RECORD_SCHEMA,
        "version": "s1-cal-r3",
        "policy_digest": policy_digest or _policy_digest(),
        "supported_scope": {"rotations": rotations if rotations is not None else [0],
                            "classes": list(classes)},
        "classes": {c: {"rejecting": _rejecting_entries(c), "accepting": acc.get(c, [])}
                    for c in classes},
    }


# A HYPOTHETICAL independent YES per class, pointing at the clean fixture
# render. Used only to show the resolver accepts well-formed evidence; the
# decision_ref names no real reviewer document and must not be cited as one.
_HYPOTHETICAL_YES = {c: [{"artifact_sha256": PINS["clean/clean_divider.svg"],
                          "decision_ref": "HYPOTHETICAL: no independent YES exists on 2026-10-06"}]
                     for c in "abcde"}


def _cp3(leaf: str, **kw):
    return measure(CP3 / f"{leaf}.kicad_sch", CP3 / f"{leaf}.svg",
                   CP3 / f"{leaf}.archived.net",
                   export_receipt=CP3 / f"{leaf}.export-receipt.json", **kw)


def _clean(**kw):
    return measure(CLEAN / "clean_divider.kicad_sch", CLEAN / "clean_divider.svg",
                   CLEAN / "clean_divider.net",
                   export_receipt=CLEAN / "clean_divider.export-receipt.json", **kw)


def _b1(**kw):
    return measure(B1 / "b1_dotted_contact.kicad_sch", B1 / "b1_dotted_contact.svg",
                   B1 / "b1_dotted_contact.net",
                   export_receipt=B1 / "b1_dotted_contact.export-receipt.json", **kw)


class FixturePins(unittest.TestCase):
    """Bytes measured == bytes pinned. Runs first (alphabetical) so a drift fails
    before any verdict is read."""

    def test_every_fixture_matches_its_pin(self):
        for rel, want in PINS.items():
            p = FIX / rel
            self.assertTrue(p.is_file(), f"fixture missing: {p}")
            self.assertEqual(_sha(p), want, f"byte drift: {rel}")

    def test_pin_table_covers_every_fixture_file(self):
        on_disk = {str(p.relative_to(FIX)) for p in FIX.rglob("*") if p.is_file()}
        self.assertEqual(on_disk, set(PINS), "unpinned or missing fixture files")


class RejectingExemplars(unittest.TestCase):
    """Every archived NO must stay non-passing AND localize the reviewer's class.
    CP3 cells carry a provenance MISMATCH (archived .net predates the sch).
    Round 3: mismatch takes precedence -- the OVERALL verdict is indeterminate;
    the class FAILs and their findings are retained as diagnostics."""

    def _cell(self, leaf):
        rep = _cp3(leaf)
        self.assertEqual(rep.execution, "succeeded")
        self.assertEqual(rep.render_context["provenance"]["status"], "mismatch")
        self.assertTrue(any(a.startswith("PROVENANCE_MISMATCH") for a in rep.anomalies))
        self.assertEqual(rep.verdict, "indeterminate", f"{leaf}: unknown lineage cannot yield a verdict")
        self.assertEqual(rep.scoped_verdict, "indeterminate")
        self.assertTrue(any(c.verdict == "fail" for c in rep.classes),
                        f"{leaf}: class outcomes must be retained as diagnostics")
        self.assertTrue(rep.offender_classes(), f"{leaf}: a YES on a NO artifact rejects the instrument")
        return rep

    def _assert_evidence(self, leaf, rep):
        cell = REVIEWER_CELLS[leaf]
        got = rep.offender_classes()
        self.assertTrue(cell["classes"] <= got,
                        f"{leaf}: reviewer classes {sorted(cell['classes'])} not all flagged; got {sorted(got)}")
        by_cls = rep.offenders()
        for cls, (code, obj) in cell["evidence"].items():
            hits = [f for f in by_cls.get(cls, []) if f.code == code
                    and any(obj in o for o in f.objects)]
            self.assertTrue(hits, f"{leaf}/{cls}: no {code} finding naming {obj!r}; "
                                  f"have {[(f.code, f.objects) for f in by_cls.get(cls, [])]}")
            for f in hits:
                self.assertIsNotNone(f.at or f.region, "finding must be localized")

    def test_usbc_cp3_is_rejected_with_reviewer_classes(self):
        self._assert_evidence("usbc", self._cell("usbc"))

    def test_power_rail_cp3_is_rejected_with_reviewer_classes(self):
        self._assert_evidence("power_rail", self._cell("power_rail"))

    def test_battery_cp3_is_rejected_with_reviewer_classes(self):
        self._assert_evidence("battery", self._cell("battery"))

    def test_d_is_an_illusion_finding_never_an_electrical_bypass_claim(self):
        rep = _cp3("usbc")
        d = next(c for c in rep.classes if c.id == "d")
        codes = {f.code for f in d.findings}
        self.assertIn("D_DOT_ON_PIN_CONTINUES", codes)
        self.assertNotIn("D_DRAWN_BYPASS", codes)
        for f in d.findings:
            self.assertEqual(f.kind, "perceptual")

    def test_b_splits_electrical_from_perceptual(self):
        rep = _cp3("power_rail")
        b = next(c for c in rep.classes if c.id == "b")
        self.assertGreater(b.measurements["b2_perceptual"], 0)
        for f in b.findings:
            self.assertEqual(f.kind, "perceptual" if f.code.startswith("B2") else "electrical")


class Provenance(unittest.TestCase):
    """Round-2 invariant 1: lineage is the export receipt, not filename pairing."""

    def test_cp3_archived_netlist_is_a_provenance_mismatch_with_findings_retained(self):
        for leaf in REVIEWER_CELLS:
            rep = _cp3(leaf)
            prov = rep.render_context["provenance"]
            self.assertEqual(prov["status"], "mismatch", leaf)
            self.assertTrue(any(a.startswith("PROVENANCE_MISMATCH") for a in rep.anomalies), leaf)
            self.assertNotEqual(rep.verdict, "pass", leaf)
            self.assertTrue(rep.offender_classes(), f"{leaf}: findings must be retained")

    def test_mismatch_outranks_class_fail_for_the_overall_verdict(self):
        """Round-3 invariant 1: provenance precedence. CP3 cells have class FAILs;
        the overall verdict is still indeterminate and nothing is dropped."""
        for leaf in REVIEWER_CELLS:
            rep = _cp3(leaf)
            self.assertEqual(rep.render_context["provenance"]["status"], "mismatch", leaf)
            self.assertEqual(rep.verdict, "indeterminate", leaf)
            self.assertEqual(rep.scoped_verdict, "indeterminate", leaf)
            failed = {c.id for c in rep.classes if c.verdict == "fail"}
            self.assertTrue(REVIEWER_CELLS[leaf]["classes"] <= failed | rep.offender_classes(), leaf)
            self.assertTrue(rep.offender_classes(), leaf)

    def test_no_receipt_is_unknown_and_blocks_pass(self):
        rep = measure(CLEAN / "clean_divider.kicad_sch", CLEAN / "clean_divider.svg",
                      CLEAN / "clean_divider.net",
                      calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))
        self.assertEqual(rep.render_context["provenance"]["status"], "unknown")
        self.assertEqual(rep.verdict, "indeterminate")
        self.assertEqual(rep.scoped_verdict, "indeterminate")
        for c in rep.classes:
            self.assertEqual(c.findings, [], c.id)

    def test_verified_receipt_binds_hashes_version_and_command(self):
        rep = _clean(calibration_record=_calibration_record())
        prov = rep.render_context["provenance"]
        self.assertEqual(prov["status"], "verified")
        self.assertEqual(prov["kicad_version"], "9.0.9")
        self.assertTrue(prov["commands"])
        rec = json.loads((CLEAN / "clean_divider.export-receipt.json").read_text())
        self.assertEqual(rec["render_sha256"], PINS["clean/clean_divider.svg"])
        self.assertEqual(rec["netlist_sha256"], PINS["clean/clean_divider.net"])

    def test_same_named_changed_sheet_is_refused(self):
        """A receipt whose sheet_set hash differs (same name, other bytes) => mismatch."""
        rec = json.loads((CLEAN / "clean_divider.export-receipt.json").read_text())
        rec["sheet_set"]["clean_divider.kicad_sch"] = "0" * 64
        rep = measure(CLEAN / "clean_divider.kicad_sch", CLEAN / "clean_divider.svg",
                      CLEAN / "clean_divider.net", export_receipt=rec,
                      calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))
        self.assertEqual(rep.render_context["provenance"]["status"], "mismatch")
        self.assertEqual(rep.verdict, "indeterminate")
        self.assertEqual(rep.scoped_verdict, "indeterminate")

    def test_stale_export_is_refused(self):
        rec = json.loads((CLEAN / "clean_divider.export-receipt.json").read_text())
        rec["netlist_sha256"] = "f" * 64
        rep = measure(CLEAN / "clean_divider.kicad_sch", CLEAN / "clean_divider.svg",
                      CLEAN / "clean_divider.net", export_receipt=rec,
                      calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))
        self.assertEqual(rep.render_context["provenance"]["status"], "mismatch")
        self.assertEqual(rep.verdict, "indeterminate")
        self.assertEqual(rep.scoped_verdict, "indeterminate")


class B1DottedForeignContact(unittest.TestCase):
    """Round-2 invariant 2: a dotted foreign contact must be detectable; the
    union at the dot must not erase the conflict."""

    def test_b1_fires_under_declared_identity(self):
        rep = _b1(declared_pin_nets=B1_DECLARED)
        b = next(c for c in rep.classes if c.id == "b")
        hits = [f for f in b.findings if f.code == "B1_FOREIGN_CONTACT_WITH_DOT"]
        self.assertTrue(hits, [f.code for f in b.findings])
        self.assertEqual(hits[0].at, (60.0, 40.0))
        self.assertEqual(hits[0].kind, "electrical")
        self.assertTrue({"net:NETA", "net:NETB"} <= set(hits[0].objects), hits[0].objects)
        self.assertEqual(b.measurements["b1_electrical"], 1)
        self.assertEqual(b.measurements["b2_perceptual"], 0)

    def test_b1_is_distinct_from_the_no_dot_b2_case(self):
        rep = _cp3("power_rail")
        b = next(c for c in rep.classes if c.id == "b")
        self.assertTrue(any(f.code == "B2_FOREIGN_CROSS_NO_DOT" for f in b.findings))
        self.assertFalse(any(f.code == "B1_FOREIGN_CONTACT_WITH_DOT" for f in b.findings))

    def test_native_only_identity_cannot_see_the_dotted_short_and_says_so(self):
        """kicad-cli already fused NETA/NETB at the dot, so native identity has one
        net there. The report must NOT claim clean: class b passes on its own
        evidence but class d reports R4 as not_assessed and the sheet is not PASS."""
        rep = _b1()
        b = next(c for c in rep.classes if c.id == "b")
        self.assertIn("native netlist", b.applicability)
        d = next(c for c in rep.classes if c.id == "d")
        self.assertEqual(d.verdict, "indeterminate")
        self.assertEqual(d.measurements["not_assessed"], 1)
        self.assertNotEqual(rep.verdict, "pass")

    def test_empty_pin_authority_is_unmeasured_not_clean(self):
        rep = _b1(declared_pin_nets=None, policy=None)
        # simulate: no netlist content -> measure refuses before here; so test the
        # class directly through an empty declared map on a netlist with no nets
        from bodesign_eda_bridge.readability_render import (
            ClassReport, _class_b, build_drawn_graph, parse_sheet)
        sheet = parse_sheet((B1 / "b1_dotted_contact.kicad_sch").read_text())
        g = build_drawn_graph(sheet, {}, POLICY["coord_eps_mm"])
        rep_b = _class_b(sheet, g, POLICY, {}, "none")
        self.assertFalse(rep_b.measured)
        self.assertEqual(rep_b.verdict, "indeterminate")
        self.assertIsInstance(rep_b, ClassReport)
        self.assertIsNotNone(rep)


class CalibrationRecord(unittest.TestCase):
    """Round-3 invariant 2: calibration is a content-bound record (v2), checked
    for internal consistency; a declaration without evidence resolves to nothing."""

    def test_todays_evidence_is_partial_and_the_clean_fixture_cannot_pass(self):
        """Honest state on 2026-10-06: CP3 rejecting x3, no independent YES for any
        class => every class partial => overall indeterminate. The clean fixture
        is clean (no findings) but it is NOT a calibrated PASS."""
        rep = _clean(calibration_record=_calibration_record())
        self.assertEqual(rep.anomalies, [])
        self.assertEqual(rep.render_context["provenance"]["status"], "verified")
        for c in rep.classes:
            if c.id in "abcde":
                self.assertEqual(c.findings, [], f"class {c.id} false positive on clean fixture")
        cal = rep.calibration_ref
        self.assertEqual(cal["status"], "partial")
        self.assertEqual(cal["partial_classes"], list("abcde"))
        for cid in "abcde":
            self.assertEqual(cal["classes"][cid]["accepting"], 0, cid)
            self.assertIn("no independently reviewed accepting case", cal["classes"][cid]["missing"], cid)
        # rejecting evidence present only where a reviewer named the class
        self.assertEqual(cal["classes"]["a"]["rejecting"], 1)   # usbc
        self.assertEqual(cal["classes"]["b"]["rejecting"], 1)   # power_rail
        self.assertEqual(cal["classes"]["c"]["rejecting"], 3)   # all three
        self.assertEqual(cal["classes"]["d"]["rejecting"], 1)   # usbc
        self.assertEqual(cal["classes"]["e"]["rejecting"], 2)   # power_rail, battery
        self.assertEqual(rep.scoped_verdict, "indeterminate")
        self.assertEqual(rep.verdict, "indeterminate")

    def test_resolver_accepts_wellformed_evidence_but_six_class_report_stays_partial(self):
        """With a (hypothetical) independent YES per class, a-e would be calibrated
        and the SCOPED verdict pass; the six-class verdict is still not pass
        because f is explicitly partial. The injected refs are labelled
        HYPOTHETICAL and are not evidence of anything in the receipt."""
        rep = _clean(calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))
        self.assertEqual(rep.calibration_ref["status"], "calibrated")
        self.assertEqual(rep.verdict_scope, "a-e")
        self.assertEqual(rep.scoped_verdict, "pass")
        self.assertEqual(rep.verdict, "indeterminate")

    def test_no_record_is_uncalibrated_and_indeterminate(self):
        rep = _clean()
        self.assertEqual(rep.calibration_ref["status"], "uncalibrated")
        self.assertEqual(rep.verdict, "indeterminate")

    def test_caller_assertion_without_evidence_is_rejected(self):
        rep = _clean(calibration_record={"status": "calibrated"})
        self.assertEqual(rep.calibration_ref["status"], "uncalibrated")
        self.assertEqual(rep.verdict, "indeterminate")

    def test_v1_declaration_record_is_no_longer_accepted(self):
        rec = {"schema": "s1-calibration-record-v1", "policy_digest": _policy_digest(),
               "classes": {c: {"population": "x", "reviewer_evidence": ["y"]} for c in "abcde"}}
        rep = _clean(calibration_record=rec)
        self.assertEqual(rep.calibration_ref["status"], "uncalibrated")

    def test_wrong_policy_digest_is_uncalibrated(self):
        rep = _clean(calibration_record=_calibration_record(policy_digest="0000000000000000"))
        self.assertEqual(rep.calibration_ref["status"], "uncalibrated")
        self.assertEqual(rep.verdict, "indeterminate")

    def test_partial_class_cover_is_partial_not_calibrated(self):
        rep = _clean(calibration_record=_calibration_record(classes="abc", accepting=_HYPOTHETICAL_YES))
        self.assertEqual(rep.calibration_ref["status"], "partial")
        self.assertEqual(rep.calibration_ref["partial_classes"], ["d", "e"])
        self.assertEqual(rep.verdict, "indeterminate")

    def test_entry_without_hash_or_decision_is_inconsistent(self):
        bad = {c: [{"artifact_sha256": "not-a-hash", "decision_ref": "x"}] for c in "abcde"}
        rep = _clean(calibration_record=_calibration_record(accepting=bad))
        self.assertEqual(rep.calibration_ref["status"], "inconsistent")
        self.assertTrue(any("artifact_sha256" in p for p in rep.calibration_ref["problems"]))
        bad = {c: [{"artifact_sha256": "0" * 64, "decision_ref": ""}] for c in "abcde"}
        rep = _clean(calibration_record=_calibration_record(accepting=bad))
        self.assertEqual(rep.calibration_ref["status"], "inconsistent")
        self.assertTrue(any("decision_ref" in p for p in rep.calibration_ref["problems"]))
        self.assertEqual(rep.verdict, "indeterminate")

    def test_subject_rotation_outside_supported_scope_is_refused(self):
        # the clean fixture is 0-rotation only; a record supporting only 90 does not cover it
        rep = _clean(calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES, rotations=[90]))
        self.assertEqual(rep.calibration_ref["status"], "out_of_scope")
        self.assertEqual(rep.verdict, "indeterminate")
        rep = _clean(calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES, rotations=[0, 90]))
        self.assertEqual(rep.calibration_ref["status"], "calibrated")
        self.assertEqual(rep.calibration_ref["subject_scope"]["rotations"], [0])

    def test_clean_divider_measures_a_real_population(self):
        rep = _clean()
        m = {c.id: c.measurements for c in rep.classes}
        self.assertGreaterEqual(m["a"]["dots"], 1)
        self.assertGreaterEqual(m["c"]["required_pairs"], 2)
        self.assertGreaterEqual(m["d"]["series_elements"], 2)


class Population(unittest.TestCase):
    """expected / examined / omitted reconcile; n1==n2 is not_assessed without intent."""

    def test_class_d_expected_equals_examined_plus_omitted(self):
        for rep in (_cp3("usbc"), _cp3("power_rail"), _b1(), _b1(declared_pin_nets=B1_DECLARED)):
            d = next(c for c in rep.classes if c.id == "d")
            self.assertEqual(len(d.expected_ids), len(d.examined_ids) + len(d.omitted),
                             f"{d.expected_ids} vs {d.examined_ids} + {d.omitted}")

    def test_shunt_without_declared_intent_is_not_assessed(self):
        d = next(c for c in _b1().classes if c.id == "d")
        self.assertEqual(d.measurements["not_assessed"], 1)
        self.assertEqual(d.verdict, "indeterminate")
        self.assertIn("R4", [o["ref"] for o in d.omitted])

    def test_shunt_with_declared_intent_is_assessed(self):
        d = next(c for c in _b1(declared_pin_nets=B1_DECLARED).classes if c.id == "d")
        self.assertEqual(d.measurements["not_assessed"], 0)
        self.assertEqual(d.verdict, "pass")

    def test_class_c_consumes_explicit_required_pairs(self):
        rep = _cp3("power_rail", required_local_pairs=[("L1.1", "U1.3")],
                   local_exceptions={"U1.4": "continuation"})
        c = next(cl for cl in rep.classes if cl.id == "c")
        self.assertEqual(c.measurements["required_pairs"], 1)
        self.assertEqual([o for o in c.omitted if o.get("pin") == "U1.4"][0]["reason"], "continuation")
        self.assertTrue(any("L1.1" in f.objects[0] for f in c.findings))

    def test_class_c_global_label_does_not_exempt_the_whole_net(self):
        # battery: BAT_EXT net has local labels only; GND is global. A pin on a
        # global-labelled net with an on-sheet peer is still a required pair.
        c = next(cl for cl in _cp3("battery").classes if cl.id == "c")
        self.assertGreaterEqual(c.measurements["required_pairs"], 3)


S3 = FIX / "s3_usbc_20261006"
PX_PER_MM = 5.906  # 150 dpi PDF-path PNG, 1754x1240


def _s3():
    """measure() on the exact S3 subject with the authority inputs the officer
    run used (declared nets, explicit required pairs, exceptions)."""
    inv = json.loads((S3 / "s1_invocation.json").read_text())
    return measure(S3 / "usbc.kicad_sch", S3 / "usbc.svg", S3 / "usbc.net",
                   export_receipt=S3 / "usbc.export-receipt.json",
                   calibration_record=inv["calibration_record"],
                   declared_pin_nets=inv["declared_pin_nets"],
                   required_local_pairs=[tuple(p) for p in inv["required_local_pairs"]],
                   local_exceptions=inv["local_exceptions"])


class S3UsbcCoverage(unittest.TestCase):
    """Round 5: the four reviewer-2 defects on the S3 usbc leaf (PDF-path PNG
    pixels -> mm at 5.906 px/mm). Before round 5 class f returned
    wire_through_text=0 for all four: its 3-sample test (t=.25/.5/.75 of the whole
    wire) steps over a glyph box that a long wire crosses between samples, and
    label-flag outline ink was never modelled. Reviewer e/f labels are history and
    stay; the instrument reports all four under class f (text-vs-ink), mapped in
    receipt section 10."""

    def _f(self):
        rep = _s3()
        self.assertEqual(rep.render_context["provenance"]["status"], "verified")
        return next(c for c in rep.classes if c.id == "f")

    def _hit(self, f, code, text, other, px, tol_px=12):
        hits = [x for x in f.findings if x.code == code and x.objects[0] == text
                and any(other in o for o in x.objects[1:])]
        self.assertTrue(hits, f"{code} {text!r}/{other!r} absent; have "
                              f"{[(x.code, x.objects) for x in f.findings]}")
        near = [x for x in hits if abs(x.at[0] * PX_PER_MM - px[0]) <= tol_px
                and abs(x.at[1] * PX_PER_MM - px[1]) <= tol_px]
        self.assertTrue(near, f"{text!r}: no hit within {tol_px}px of {px}; "
                              f"have {[(round(x.at[0]*PX_PER_MM), round(x.at[1]*PX_PER_MM)) for x in hits]}")

    def test_1_cc1_vbus_con_verticals_strike_usb_c_16p(self):
        f = self._f()
        # reviewer: verticals at x~420/435 px strike the text at (396-458, 339)
        self._hit(f, "F_WIRE_THROUGH_TEXT", "USB_C_16P", "cacea585", (435, 340))
        self._hit(f, "F_WIRE_THROUGH_TEXT", "USB_C_16P", "d62747ae", (420, 340))

    def test_2_cc2_label_sits_on_the_cc1_wire(self):
        f = self._f()
        # reviewer: CC2 label at (417,283) on the CC1 wire
        self._hit(f, "F_WIRE_THROUGH_TEXT", "CC2", "d62747ae", (420, 284))

    def test_3_cc1_label_struck_by_the_vbus_con_vertical(self):
        f = self._f()
        # reviewer: CC1 label (421-441, 432) struck by the VBUS_CON vertical x~435
        self._hit(f, "F_WIRE_THROUGH_TEXT", "CC1", "cacea585", (435, 434))

    def test_4_gnd_flag_outline_overlaps_d1_refdes_and_value(self):
        f = self._f()
        # reviewer: GND flag (497-540, 480) overlaps D1 refdes/value
        self._hit(f, "F_FLAG_THROUGH_TEXT", "D1", "flag:global_label:GND", (523, 473))
        self._hit(f, "F_FLAG_THROUGH_TEXT", "PESD5V0L4UF", "flag:global_label:GND", (524, 488))
        self.assertEqual(f.measurements["flag_through_text"], 2)

    def test_report_delta_f_flips_to_fail_others_unchanged(self):
        rep = _s3()
        v = {c.id: (c.verdict, len(c.findings)) for c in rep.classes}
        # pre-round-5 (s1_report.json, same inputs): a pass 0, b fail 1, c pass 0,
        # d pass 0, e pass 0, f pass 0, overall fail (carried by b)
        self.assertEqual(v["a"], ("pass", 0))
        self.assertEqual(v["b"], ("fail", 1))
        self.assertEqual(v["c"], ("pass", 0))
        self.assertEqual(v["d"], ("pass", 0))
        self.assertEqual(v["e"], ("pass", 0))
        self.assertEqual(v["f"][0], "fail")
        self.assertEqual(v["f"][1], 9)
        self.assertEqual(rep.subject_manifest_sha256,
                         "b47236dd11851977995578178045373f7cec013e500b3be093b6ebf21d713811")

    def test_own_label_wire_is_not_a_strike(self):
        """Control: a label sitting at the END of its own wire is not struck. The
        clean fixture has labelled wires and must stay f-clean."""
        f = next(c for c in _clean().classes if c.id == "f")
        self.assertEqual([x for x in f.findings if x.code in ("F_WIRE_THROUGH_TEXT", "F_FLAG_THROUGH_TEXT")], [])

    def test_flag_own_text_is_not_a_strike(self):
        """Control: every GND flag's own text sits inside its outline. Only the one
        flag whose outline crosses D1's text is reported (5 flags on the leaf)."""
        f = self._f()
        flags = {o for x in f.findings if x.code == "F_FLAG_THROUGH_TEXT" for o in x.objects[1:]}
        self.assertEqual(flags, {"flag:global_label:GND@(83.82, 81.28)"})


XF = FIX / "xform"


def _xf(name, **kw):
    return measure(XF / f"{name}.kicad_sch", XF / f"{name}.svg", XF / f"{name}.net",
                   export_receipt=XF / f"{name}.export-receipt.json", **kw)


def _r150709():
    d = XF / "r150709"
    inv = json.loads((d / "s1_invocation.json").read_text())
    return measure(d / "usbc.kicad_sch", d / "usbc.svg", d / "usbc.net",
                   export_receipt=d / "usbc.export-receipt.json",
                   calibration_record=inv["calibration_record"],
                   declared_pin_nets=inv["declared_pin_nets"],
                   required_local_pairs=[tuple(p) for p in inv["required_local_pairs"]],
                   local_exceptions=inv["local_exceptions"])


def _sig(rep):
    """Order-independent, hashable signature of every class outcome."""
    return {c.id: (c.verdict, sorted((f.code, tuple(f.objects),
                                      tuple(round(v, 2) for v in f.at) if f.at else None)
                                     for f in c.findings)) for c in rep.classes}


def _old_transform(sym_at, rot, mirror, px, py):
    """The pre-round-6 order (mirror THEN rotate), kept only to measure before/after."""
    import math
    if mirror == "y":
        px = -px
    if mirror == "x":
        py = -py
    r = math.radians(rot)
    cs, sn = round(math.cos(r), 12), round(math.sin(r), 12)
    return (round(sym_at[0] + px * cs - py * sn, 4), round(sym_at[1] - (px * sn + py * cs), 4))


def _ink_ends(svg_path):
    from bodesign_eda_bridge.readability_render import parse_svg
    svg = parse_svg(Path(svg_path).read_text())
    return [(e[0] * svg.unit_scale, e[1] * svg.unit_scale) for pts, _ in svg.paths for e in (pts[0], pts[-1])]


def _ink_rects(svg_path):
    import re
    out = []
    for x, y, w, h in re.findall(r'<rect x="([-0-9.]+)" y="([-0-9.]+)" width="([-0-9.]+)" height="([-0-9.]+)"',
                                 Path(svg_path).read_text()):
        x, y, w, h = float(x), float(y), float(w), float(h)
        if w < 200:  # drop the page rect
            out.append((x, y, x + w, y + h))
    return out


class TransformCoverage(unittest.TestCase):
    """Round 6. MEASURED, not assumed: rotation/mirror support is checked against
    native kicad-cli 9.0.9 ink. Geometry (pin tips, pin stub ends, body box) is
    transform-correct for every rot x mirror after the round-6 fix; class
    detectors are exercised on one rotated (R180) and one mirrored (MY/MX) fixture
    carrying a same-net T and foreign crossings. Nothing here widens
    supported_scope or declares calibration."""

    CASES = {"xr180": ("U1", 180.0, None), "xm": ("U1", 0.0, "y"),
             "sweep_r90_mx": ("U1", 90.0, "x"), "sweep_r270_my": ("U1", 270.0, "y")}

    def _sheet(self, name):
        from bodesign_eda_bridge.readability_render import parse_sheet
        return parse_sheet((XF / f"{name}.kicad_sch").read_text())

    def test_fixtures_really_carry_the_transform_under_test(self):
        for name, (ref, rot, mir) in self.CASES.items():
            u = next(s for s in self._sheet(name).symbols if s.ref == ref)
            self.assertEqual((u.rot, u.mirror), (rot, mir), name)

    def test_pin_tips_and_stub_ends_land_on_native_ink(self):
        for name in self.CASES:
            ends = _ink_ends(XF / f"{name}.svg")
            u = next(s for s in self._sheet(name).symbols if s.ref == "U1")
            self.assertEqual(len(u.pins), 3, name)
            for p in u.pins:
                for what, pt in (("tip", p.tip), ("end", p.end)):
                    import math
                    self.assertTrue(any(math.dist(e, pt) <= 0.02 for e in ends),
                                    f"{name} {p.id} {what} {pt} not on kicad-cli ink")

    def test_body_box_equals_native_body_rectangle(self):
        for name in self.CASES:
            u = next(s for s in self._sheet(name).symbols if s.ref == "U1")
            self.assertTrue(any(all(abs(a - b) <= 0.02 for a, b in zip(r, u.body))
                                for r in _ink_rects(XF / f"{name}.svg")),
                            f"{name}: body {u.body} not among {_ink_rects(XF / f'{name}.svg')}")

    def test_old_mirror_then_rotate_order_was_wrong_at_90_and_270(self):
        """Before/after on the sweep fixtures: the pre-round-6 order puts every pin
        of a 90/270 x mirror symbol off the ink; at 0/180 the orders agree."""
        import math
        import bodesign_eda_bridge.readability_render as rr
        keep = rr._transform
        try:
            rr._transform = _old_transform
            for name in ("sweep_r90_mx", "sweep_r270_my"):
                ends = _ink_ends(XF / f"{name}.svg")
                u = next(s for s in self._sheet(name).symbols if s.ref == "U1")
                on = [any(math.dist(e, p.tip) <= 0.02 for e in ends) for p in u.pins]
                self.assertEqual(on, [False, False, False], f"{name}: old order unexpectedly right")
            for name in ("xr180", "xm"):
                ends = _ink_ends(XF / f"{name}.svg")
                u = next(s for s in self._sheet(name).symbols if s.ref == "U1")
                self.assertTrue(all(any(math.dist(e, p.tip) <= 0.02 for e in ends) for p in u.pins), name)
        finally:
            rr._transform = keep

    def test_detectors_on_rotated_and_mirrored_fixtures(self):
        """Same topology, rotated (R180) and mirrored (MY/MX): same findings. Same-net
        T at (125,112) with a dot -> class a clean (1 dot, no spurious/missing);
        foreign crossing at (115,102.54) with no dot -> class b B2; a foreign wire
        entering the U1 body -> class e E_WIRE_THROUGH_BODY; c/d clean; f clean."""
        for name, other in (("xr180", "net:Net-(U1-A)"), ("xm", "net:Net-(U1-B)")):
            rep = _xf(name)
            self.assertEqual(rep.anomalies, [], name)
            self.assertEqual(rep.render_context["provenance"]["status"], "verified", name)
            cls = {c.id: c for c in rep.classes}
            self.assertEqual(cls["a"].verdict, "pass", name)
            self.assertEqual(cls["a"].measurements["dots"], 1, name)
            b = [f for f in cls["b"].findings]
            self.assertEqual([(f.code, f.at) for f in b], [("B2_FOREIGN_CROSS_NO_DOT", (115.0, 102.54))], name)
            self.assertTrue({"net:GND", other} <= set(b[0].objects), (name, b[0].objects))
            e = cls["e"].findings
            self.assertEqual([f.code for f in e], ["E_WIRE_THROUGH_BODY"], name)
            self.assertIn("symbol:U1", e[0].objects)
            self.assertEqual(cls["c"].findings, [], name)
            self.assertEqual(cls["d"].findings, [], name)
            self.assertEqual(cls["f"].findings, [], name)

    def test_rotated_and_mirrored_subjects_are_out_of_supported_scope(self):
        """Transform-correct geometry does not make a rotated/mirrored subject
        calibrated: with the record's rotations [0] the status is out_of_scope,
        the subject scope names what is present, findings are retained, and the
        scoped verdict can never be pass."""
        for name, want in (("xr180", [180]), ("xm", [0, "mirror"])):
            rep = _xf(name, calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))
            self.assertEqual(rep.calibration_ref["status"], "out_of_scope", name)
            self.assertIn("not in supported", rep.calibration_ref["reason"], name)
            self.assertTrue(rep.offender_classes(), f"{name}: findings must be retained")
            self.assertNotEqual(rep.scoped_verdict, "pass", name)
            self.assertNotEqual(rep.verdict, "pass", name)
            self.assertEqual(sorted(self._sheet(name).symbols and
                                    {int(s.rot) % 360 for s in self._sheet(name).symbols}
                                    | ({"mirror"} if any(s.mirror for s in self._sheet(name).symbols) else set()),
                                    key=str), sorted(want, key=str), name)

    def test_mixed_scope_record_does_not_crash_the_resolver(self):
        """Round-6 defect: sorting [0, 'mirror'] raised TypeError. Fixed; a record
        that names the mirror scope still gets only the status its evidence earns."""
        rep = _xf("xm", calibration_record=_calibration_record(rotations=[0, "mirror"]))
        self.assertEqual(rep.calibration_ref["status"], "partial")
        self.assertIs(rep.calibration_ref["evidence_authenticated"], False)
        self.assertNotEqual(rep.scoped_verdict, "pass")

    def test_rotation_zero_subjects_have_no_transform_exposure(self):
        from bodesign_eda_bridge.readability_render import parse_sheet
        for p in (CP3 / "usbc.kicad_sch", CP3 / "power_rail.kicad_sch", CP3 / "battery.kicad_sch",
                  CLEAN / "clean_divider.kicad_sch", B1 / "b1_dotted_contact.kicad_sch",
                  S3 / "usbc.kicad_sch", XF / "r150709" / "usbc.kicad_sch"):
            sh = parse_sheet(p.read_text())
            self.assertEqual({(int(s.rot) % 360, s.mirror) for s in sh.symbols}, {(0, None)}, p.name)

    def test_rotation_zero_findings_are_identical_old_vs_new_transform(self):
        """Before/after on rotation-0 subjects: CP3 x3, clean, b1, run-133234 and
        run-150709, measured under the old and the new transform; every class
        verdict and every finding (code, objects, location) is identical."""
        import bodesign_eda_bridge.readability_render as rr
        runs = {"cp3/usbc": lambda: _cp3("usbc"), "cp3/power_rail": lambda: _cp3("power_rail"),
                "cp3/battery": lambda: _cp3("battery"), "clean": _clean, "b1": _b1,
                "run-133234": _s3, "run-150709": _r150709}
        after = {k: _sig(f()) for k, f in runs.items()}
        keep = rr._transform
        try:
            rr._transform = _old_transform
            before = {k: _sig(f()) for k, f in runs.items()}
        finally:
            rr._transform = keep
        for k in runs:
            self.assertEqual(before[k], after[k], f"{k}: rotation-0 findings moved")

    def test_run_150709_matches_its_stored_report(self):
        """The stored s1_report.json (module d0dca6c8) and a fresh run agree class by
        class on verdict and findings: the S1 identity d0dca6c8 -> this revision
        changes nothing on that candidate."""
        stored = json.loads((XF / "r150709" / "s1_report.json").read_text())
        rep = _r150709()
        self.assertNotEqual(rep.subject_manifest_sha256, stored["subject_manifest_sha256"])
        self.assertEqual(rep.subject_manifest_sha256,
                         "84311bdc2da747d82cbc3a3cd44bd8e4e0c33c5e3e4b7bf168ae266b6c5a88bb")
        got = _sig(rep)
        for c in stored["classes"]:
            want = (c["verdict"], sorted((f["code"], tuple(f["objects"]),
                                          tuple(round(v, 2) for v in f["at"]) if f["at"] else None)
                                         for f in c["findings"]))
            self.assertEqual(got[c["id"]], want, c["id"])


class Contract(unittest.TestCase):
    def test_policy_is_versioned_and_page_use_is_not_a_gate(self):
        self.assertTrue(POLICY["version"])
        self.assertIsNone(POLICY["page_use_gate"])
        f = next(c for c in _cp3("battery").classes if c.id == "f")
        self.assertIn("page_use_bbox_ratio", f.measurements)
        self.assertEqual(f.measurements["page_use_gate"], None)

    def test_f_cannot_contribute_a_full_pass(self):
        rep = _clean(calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))
        f = next(c for c in rep.classes if c.id == "f")
        self.assertIn("partial", f.applicability)
        self.assertEqual(rep.verdict_scope, "a-e")
        self.assertEqual(rep.scoped_verdict, "pass")
        self.assertNotEqual(rep.verdict, "pass")

    def test_report_binds_hashes_and_never_authorizes(self):
        rep = _cp3("usbc")
        h = rep.render_context["artifact_hashes"]
        self.assertEqual(h["sheet"], PINS["cp3/usbc.kicad_sch"])
        self.assertEqual(h["svg"], PINS["cp3/usbc.svg"])
        self.assertEqual(h["netlist"], PINS["cp3/usbc.archived.net"])
        self.assertEqual(rep.does_not_authorize, DOES_NOT_AUTHORIZE)
        self.assertEqual({c.id for c in rep.classes}, set("abcdef"))

    def test_subject_manifest_binds_authority_inputs(self):
        """Round-3 invariant 3: changing declared nets / required pairs /
        exceptions / policy under the same artifact bytes changes the subject."""
        base = _cp3("power_rail")
        self.assertEqual(set(base.authority_digests),
                         {"declared_pin_nets", "required_local_pairs", "local_exceptions", "policy_digest"})
        self.assertEqual(base.authority_digests["policy_digest"], base.policy_ref["digest"])
        variants = [
            _cp3("power_rail", required_local_pairs=[("L1.1", "U1.3")]),
            _cp3("power_rail", local_exceptions={"U1.4": "continuation"}),
            _cp3("power_rail", declared_pin_nets={"L1.1": "SW_NODE"}),
            _cp3("power_rail", policy={"pin_tip_band_mm": 1.0}),
        ]
        seen = {base.subject_manifest_sha256}
        for v in variants:
            self.assertEqual(v.render_context["artifact_hashes"], base.render_context["artifact_hashes"])
            self.assertNotIn(v.subject_manifest_sha256, seen)
            seen.add(v.subject_manifest_sha256)
        # identical inputs => identical subject
        self.assertEqual(_cp3("power_rail").subject_manifest_sha256, base.subject_manifest_sha256)

    def test_none_and_empty_required_pairs_are_distinct_subjects(self):
        """Round-4 residual 1: None = derive under policy K, [] = explicit empty
        population. Same bytes, different authority mode => different subject
        AND different class-c findings."""
        derived = _cp3("power_rail", required_local_pairs=None)
        explicit_empty = _cp3("power_rail", required_local_pairs=[])
        self.assertEqual(derived.render_context["artifact_hashes"],
                         explicit_empty.render_context["artifact_hashes"])
        self.assertNotEqual(derived.subject_manifest_sha256, explicit_empty.subject_manifest_sha256)
        self.assertNotEqual(derived.authority_digests["required_local_pairs"],
                            explicit_empty.authority_digests["required_local_pairs"])
        c_derived = next(c for c in derived.classes if c.id == "c")
        c_empty = next(c for c in explicit_empty.classes if c.id == "c")
        self.assertIn("derived", c_derived.applicability)
        self.assertIn("caller-declared", c_empty.applicability)
        self.assertGreater(c_derived.measurements["required_pairs"], 0)
        self.assertEqual(c_empty.measurements["required_pairs"], 0)
        self.assertTrue(c_derived.findings)
        self.assertEqual(c_empty.findings, [])

    def test_calibration_ref_declares_evidence_not_authenticated(self):
        """Round-4 residual 2: the record check is structural; no boundary has
        bound entries to reviewed artifacts, and the report says so."""
        for rep in (_clean(calibration_record=_calibration_record()),
                    _clean(calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))):
            self.assertIs(rep.calibration_ref["evidence_authenticated"], False)
            self.assertIsNone(rep.calibration_ref["authenticated_by"])

    def test_svg_alone_is_refused(self):
        with self.assertRaises(ReadabilityInputError):
            measure(CP3 / "usbc.svg", CP3 / "usbc.svg", CP3 / "usbc.archived.net")

    def test_missing_input_is_refused_not_passed(self):
        with self.assertRaises(ReadabilityInputError):
            measure(CP3 / "usbc.kicad_sch", CP3 / "usbc.svg", CP3 / "nope.net")

    def test_mismatched_pair_is_indeterminate(self):
        rep = measure(CP3 / "usbc.kicad_sch", CP3 / "battery.svg", CP3 / "usbc.archived.net")
        self.assertTrue(rep.anomalies)
        self.assertEqual(rep.verdict, "indeterminate")

    def test_sexpr_reader_is_string_aware(self):
        self.assertEqual(parse_sexpr('(a "x ) y" (b 1))'), ["a", "x ) y", ["b", "1"]])

    def test_collinear_split_counts_as_one_meet(self):
        a = next(c for c in _clean().classes if c.id == "a")
        self.assertEqual([f for f in a.findings if f.code in ("A_DOT_SPURIOUS", "A_DOT_MISSING")], [])


# =========================================================================== round 9
# Sheet-layer graphic ink (spec s1-sheet-graphics-spec.md). AC ids in test names.

import math
import os
import re
import shutil
import uuid as _uuid

import bodesign_eda_bridge.readability_render as rr

R5B = FIX / "r5b_usbc_20261006"
SYN = FIX / "synthetic_ink"
R5B_RECT = "6fe52893-6baa-5a25-8e33-fdae41b26d87"
R6_SCRATCH = Path.home() / ".cache/scratch/s3-elk-spike/run-r6-173849"


def _scratch_dir(name):
    d = Path.home() / ".cache/scratch/s1-ink-tests" / name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, mode=0o700)
    return d


def _m(d, n, **kw):
    return measure(d / f"{n}.kicad_sch", d / f"{n}.svg", d / f"{n}.net",
                   export_receipt=d / f"{n}.export-receipt.json", **kw)


def _r5b(**kw):
    return measure(R5B / "usbc.kicad_sch", R5B / "usbc.svg", R5B / "usbc.net",
                   export_receipt=R5B / "usbc.export-receipt.json", **kw)


def _graph_sha(sheet_path, net_path=None):
    """Canonical dump of the electrical structure (AC2). Identical algorithm to the
    one that produced the 9c18bc51 baseline values pinned below."""
    sheet = rr.parse_sheet(Path(sheet_path).read_text())
    nets = rr.parse_netlist(Path(net_path).read_text()) if net_path else {}
    g = rr.build_drawn_graph(sheet, nets, rr.POLICY["coord_eps_mm"])
    members = {}
    for i, c in enumerate(g.wire_comp):
        members.setdefault(repr(c), []).append(f"w{i}")
    for pid, c in g.pin_comp.items():
        members.setdefault(repr(c), []).append(f"p:{pid}")
    dump = {
        "wires": [(w.a, w.b, w.uuid) for w in sheet.wires],
        "junctions": sorted(sheet.junctions),
        "pins": sorted((p.id, p.tip, p.end, p.hidden, p.pin_type) for s in sheet.symbols for p in s.pins),
        "bodies": sorted((s.ref, s.body) for s in sheet.symbols),
        "partition": sorted(sorted(v) for v in members.values()),
        "comp_nets": sorted((sorted(members.get(repr(c), [])), sorted(n)) for c, n in g.comp_nets.items()),
        "contacts": sorted((a, b, w) for a, b, w in g.contacts),
        "pin_wires": sorted((k, sorted(v)) for k, v in g.pin_wires.items()),
        "pin_net": sorted(g.pin_net.items()),
    }
    return hashlib.sha256(json.dumps(dump, sort_keys=True, default=str).encode()).hexdigest()


def _classes_hash(rep):
    cl = {c.id: [c.verdict, sorted([f.code, list(f.objects), [round(v, 2) for v in f.at] if f.at else None]
                                    for f in c.findings)] for c in rep.classes}
    return hashlib.sha256(json.dumps(cl, sort_keys=True).encode()).hexdigest()[:16]


# 9c18bc51 baseline (module sha256 9c18bc518eafa436...), measured on the same bytes
# before any round-9 edit: (manifest, verdict, scoped, classes-hash, graph-hash), 16 hex.
BASE_9C18 = {
    "cp3/usbc": ("006915c40a8af28d", "indeterminate", "indeterminate", "a9e695c1a533c93c", "c7a274d12f61038c"),
    "cp3/power_rail": ("f5a2c3a24dc51eb8", "indeterminate", "indeterminate", "163a80cf2a65b471", "119b1c5d4515c640"),
    "cp3/battery": ("fbdefeb6058c9216", "indeterminate", "indeterminate", "bbee0d324a2bf402", "ca98113cc9d53a79"),
    "clean": ("04848947a0a8f2e0", "indeterminate", "indeterminate", "29d40aff8b7dc82a", "3d7d790efcb1add0"),
    "b1": ("af4740c9985e2dcf", "indeterminate", "indeterminate", "62a9abb769bd2578", "c22c0b13064ababc"),
    "b1+declared": ("dc93d30a85e8c82b", "fail", "fail", "bbc66e865223377b", "c22c0b13064ababc"),
    "s3_usbc_20261006": ("63ee49dbfbde24d6", "fail", "fail", "f65568a821a67d42", "4460404b3758e1be"),
    "xform/xr180": ("74d47c810eccd202", "fail", "fail", "317f6c6007a38d3e", "1f298a1874ed9f17"),
    "xform/xm": ("32971c24c78091cf", "fail", "fail", "8e34f1b05fe8d587", "de6d86263e105f39"),
    "xform/r150709": ("5bfb8cf4e5023f81", "fail", "fail", "a2128ab674597c90", "676fa561301bd28e"),
    # R5b carries ink: its manifest legitimately changes (ink authority joins the
    # subject identity); verdicts, classes and graph must not.
    "r5b": ("87b44e5fdd205cb7", "indeterminate", "indeterminate", "29d40aff8b7dc82a", "0f41b4af0ef3bd14"),
}
BASE_GRAPH_ONLY = {"xform/sweep_r90_mx": "754f71347014897a", "xform/sweep_r270_my": "754f71347014897a"}

# Historical BASE_9C18 is retained above. New decision policy intentionally changes
# every manifest and adds adjudicated/unadjudicated flag findings, not graph identity.
# BASE_FLAG is the v2 record under policy 63bee5d02a5ec147, instrument 53acfd4b (see s1-calibration-record-v2.json).
# Retained for reference; InkAC2AC6Unchanged now iterates BASE_RECAL_V3 under policy 210cdba1bd6f4e52.
BASE_FLAG = {
    "cp3/usbc": ("65de5e4253bf198f", "indeterminate", "indeterminate", "33ae1088a4f4547f"),
    "cp3/power_rail": ("8eb33e4bf21dc496", "indeterminate", "indeterminate", "cd899edbcaa85e69"),
    "cp3/battery": ("90cc5cf2ee86ddc9", "indeterminate", "indeterminate", "5bb4bfc42ebd8ae2"),
    "clean": ("612e9bdd9a159c8f", "indeterminate", "indeterminate", "29d40aff8b7dc82a"),
    "b1": ("85819c994ce86359", "fail", "fail", "12c2531993dc0b30"),
    "b1+declared": ("5d113bddaa77d170", "fail", "fail", "63c2a16fe2110262"),
    "s3_usbc_20261006": ("8134d3770c063e18", "fail", "fail", "f65568a821a67d42"),
    "xform/xr180": ("3a4060d763e8b222", "fail", "fail", "317f6c6007a38d3e"),
    "xform/xm": ("5ef2827e9e7d3438", "fail", "fail", "8e34f1b05fe8d587"),
    "xform/r150709": ("e98a0fab23d7631c", "fail", "fail", "a2128ab674597c90"),
    "r5b": ("2e207a26d22a22f7", "fail", "fail", "e8861de4912079d3"),
}

BASE_RECAL_V3 = {
    "cp3/usbc": ("8f87ca843dce3956", "indeterminate", "indeterminate", "33ae1088a4f4547f"),
    "cp3/power_rail": ("3eb1513111158bc5", "indeterminate", "indeterminate", "7a3becc1a0afa89b"),
    "cp3/battery": ("26712bb158f5cc73", "indeterminate", "indeterminate", "f5dcfde905d460f1"),
    "clean": ("ec6cc22628021975", "indeterminate", "indeterminate", "29d40aff8b7dc82a"),
    "b1": ("11f3b240b964f810", "fail", "fail", "12c2531993dc0b30"),
    "b1+declared": ("ea351b1cc711d431", "fail", "fail", "63c2a16fe2110262"),
    "s3_usbc_20261006": ("b47236dd11851977", "fail", "fail", "f65568a821a67d42"),
    "xform/xr180": ("31d77497678b1a7c", "fail", "fail", "317f6c6007a38d3e"),
    "xform/xm": ("be7ee759ee41545f", "fail", "fail", "8e34f1b05fe8d587"),
    "xform/r150709": ("84311bdc2da747d8", "fail", "fail", "a2128ab674597c90"),
    "r5b": ("7b287cff4f5f93ef", "fail", "fail", "e8861de4912079d3"),
}


def _subject(key):
    return {
        "cp3/usbc": lambda: _cp3("usbc"), "cp3/power_rail": lambda: _cp3("power_rail"),
        "cp3/battery": lambda: _cp3("battery"), "clean": _clean, "b1": _b1,
        "b1+declared": lambda: _b1(declared_pin_nets=B1_DECLARED), "s3_usbc_20261006": _s3,
        "xform/xr180": lambda: _xf("xr180"), "xform/xm": lambda: _xf("xm"),
        "xform/r150709": _r150709, "r5b": _r5b,
    }[key]()


def _sheet_net(key):
    return {
        "cp3/usbc": (CP3 / "usbc.kicad_sch", CP3 / "usbc.archived.net"),
        "cp3/power_rail": (CP3 / "power_rail.kicad_sch", CP3 / "power_rail.archived.net"),
        "cp3/battery": (CP3 / "battery.kicad_sch", CP3 / "battery.archived.net"),
        "clean": (CLEAN / "clean_divider.kicad_sch", CLEAN / "clean_divider.net"),
        "b1": (B1 / "b1_dotted_contact.kicad_sch", B1 / "b1_dotted_contact.net"),
        "b1+declared": (B1 / "b1_dotted_contact.kicad_sch", B1 / "b1_dotted_contact.net"),
        "s3_usbc_20261006": (S3 / "usbc.kicad_sch", S3 / "usbc.net"),
        "xform/xr180": (XF / "xr180.kicad_sch", XF / "xr180.net"),
        "xform/xm": (XF / "xm.kicad_sch", XF / "xm.net"),
        "xform/r150709": (XF / "r150709/usbc.kicad_sch", XF / "r150709/usbc.net"),
        "r5b": (R5B / "usbc.kicad_sch", R5B / "usbc.net"),
    }[key]


class InkAC1Count(unittest.TestCase):
    """AC1: ink-list count equals the hand count (anchored root-level pattern; the
    15 lib-symbol rectangles on R5b must NOT be counted)."""

    ROOT_PAT = re.compile(r"^(?:\t| {2})\((?:rectangle|polyline|circle|arc)\b", re.M)

    def test_ac1_r5b_has_exactly_one_ink_item(self):
        text = (R5B / "usbc.kicad_sch").read_text()
        self.assertEqual(text.count("(rectangle"), 16, "control: 15 lib-symbol bodies + 1 sheet rectangle")
        sh = rr.parse_sheet(text)
        self.assertEqual(len(sh.ink), 1)
        it = sh.ink[0]
        self.assertEqual((it.uuid, it.kind, it.stroke_type, it.stroke_width, it.fill_type, it.closed, it.source_line),
                         (R5B_RECT, "rectangle", "dash", 0.1524, "none", True, 1620))
        self.assertEqual(it.geometry_mm["corners"],
                         [(99.06, 76.2), (101.6, 76.2), (101.6, 101.6), (99.06, 101.6)])
        self.assertEqual(it.owner, "unknown")

    def test_ac1_hand_count_matches_on_every_pinned_sheet(self):
        for p in sorted(FIX.rglob("*.kicad_sch")):
            if SYN in p.parents:
                continue
            text = p.read_text()
            hand = len(self.ROOT_PAT.findall(text))
            sh = rr.parse_sheet(text)
            self.assertEqual(len(sh.ink), hand, str(p.relative_to(FIX)))
            if R5B not in p.parents:
                self.assertEqual((len(sh.ink), sh.ink_unparsed, sh.ink_missing_uuid), (0, {}, 0),
                                 f"{p.relative_to(FIX)}: no sheet-level graphics expected")

    def test_ac1_synthetic_fixtures_have_one_rectangle_each(self):
        for n, u in (("ac3_wire_cross", "5a000000-0000-4000-8000-0000000000a3"),
                     ("ac4_enclose_two_pins", "5a000000-0000-4000-8000-0000000000a4")):
            sh = rr.parse_sheet((SYN / f"{n}.kicad_sch").read_text())
            self.assertEqual([(i.uuid, i.kind) for i in sh.ink], [(u, "rectangle")])

    def test_ac1_r6_candidate_has_zero_ink(self):
        sch = R6_SCRATCH / "out" / "usbc.kicad_sch"
        if not sch.is_file():
            self.skipTest("R6 candidate run is unpinned scratch and absent on this host")
        self.assertEqual(_sha(sch), "8cd238d2f87a36056d6e035c8b29cb92057c253de03af766fa6d86c18f3da24c")
        sh = rr.parse_sheet(sch.read_text())
        self.assertEqual((len(sh.ink), sh.ink_unparsed), (0, {}))


class InkAC2AC6Unchanged(unittest.TestCase):
    """AC2 (electrical graph byte-identical) and AC6 (existing populations unchanged,
    per subject by available scope) against values measured on the 9c18bc51 build."""

    def test_ac2_graph_structure_hash_identical_on_every_subject(self):
        for key, (_m_, _v, _s, _c, gh) in BASE_9C18.items():
            sheet, net = _sheet_net(key)
            self.assertEqual(_graph_sha(sheet, net)[:16], gh, key)
        for key, gh in BASE_GRAPH_ONLY.items():
            sheet = XF / f"{key.split('/')[1]}.kicad_sch"
            self.assertEqual(_graph_sha(sheet)[:16], gh, key)

    def test_ac6_verdicts_classes_and_manifests_unchanged(self):
        for key, (man, verdict, scoped, ch) in BASE_RECAL_V3.items():
            rep = _subject(key)
            self.assertEqual((rep.verdict, rep.scoped_verdict), (verdict, scoped), key)
            self.assertEqual(_classes_hash(rep), ch, key)
            self.assertEqual(rep.subject_manifest_sha256[:16], man, key)
            self.assertNotEqual(man, BASE_9C18[key][0], key)
            self.assertEqual(rep.policy_ref["digest"], "210cdba1bd6f4e52", key)
            self.assertIs(rep.calibration_ref.get("evidence_authenticated", False), False, key)

    def test_ac6_r5b_manifest_changes_only_by_the_ink_authority(self):
        rep = _r5b()
        self.assertNotEqual(rep.subject_manifest_sha256[:16], BASE_9C18["r5b"][0])
        self.assertEqual(set(rep.authority_digests) - {"declared_pin_nets", "required_local_pairs",
                                                      "local_exceptions", "policy_digest"},
                          {"ink_owner", "measurement_scope_version", "ink_chord_tol_mm"})
        self.assertEqual(_classes_hash(rep), BASE_RECAL_V3["r5b"][3])

    def test_ac6_sweep_subjects_support_parser_and_geometry_only(self):
        """sweep_r90_mx / sweep_r270_my have sheet + svg only (no net, no export
        receipt): no report is claimed for them, and none is invented."""
        for n in ("sweep_r90_mx", "sweep_r270_my"):
            self.assertFalse((XF / f"{n}.net").exists())
            self.assertFalse((XF / f"{n}.export-receipt.json").exists())
            sh = rr.parse_sheet((XF / f"{n}.kicad_sch").read_text())
            self.assertEqual(sh.ink, [])
            self.assertTrue(any(s.rot or s.mirror for s in sh.symbols), n)

    def test_ac6_r6_candidate_unchanged_when_present(self):
        d = R6_SCRATCH
        if not (d / "out" / "usbc.kicad_sch").is_file():
            self.skipTest("R6 candidate run is unpinned scratch and absent on this host")
        inv = json.loads((d / "s1_invocation.json").read_text())
        rep = measure(d / "out/usbc.kicad_sch", d / "native/svg/usbc.svg", d / "native/usbc.net",
                      export_receipt=d / "native/usbc.export-receipt.json",
                      calibration_record=inv["calibration_record"], declared_pin_nets=inv["declared_pin_nets"],
                      required_local_pairs=[tuple(p) for p in inv["required_local_pairs"]],
                      local_exceptions=inv["local_exceptions"])
        self.assertEqual((rep.verdict, rep.scoped_verdict, _classes_hash(rep)),
                         ("fail", "fail", "57afa35dc7983559"))
        self.assertNotEqual(rep.subject_manifest_sha256[:16], "c812c0019dedc7e8")
        self.assertEqual(rep.ink_report["count"], 0)


class InkAC11R5bFixture(unittest.TestCase):
    def test_ac11_copied_bytes_match_the_original_run_hashes(self):
        want = {"usbc.kicad_sch": "1a898ecc9158197e9d403b9a8fcc5886ba578aa86d303a8f463f38d17185856b",
                "usbc.net": "188cc95ccbe36242878750ef6f2637b45c02485e2cb9b724f2eb19f9fbb993f2",
                "usbc.svg": "54fca7ad2508d686f15d0cdb7a455181c65fc3096a8b031dceea29510009f10b",
                "usbc.export-receipt.json": "3619b26b92ad60bc9996c4a565c51ce748f4dba7f3297b1d8df9dbe408a41bc6"}
        for f, h in want.items():
            self.assertEqual(_sha(R5B / f), h, f)
            self.assertEqual(PINS[f"r5b_usbc_20261006/{f}"], h)

    def test_ac11_manifest_and_readme(self):
        man = dict(reversed(l.split("  ", 1)) for l in (R5B / "MANIFEST.sha256").read_text().splitlines())
        for f in ("usbc.kicad_sch", "usbc.net", "usbc.svg", "usbc.export-receipt.json", "README.md"):
            self.assertEqual(man[f], _sha(R5B / f), f)
        readme = (R5B / "README.md").read_text()
        for needle in ("out/usbc.kicad_sch", "native/usbc.net", "native/svg/usbc.svg",
                       "native/usbc.export-receipt.json", "NOT a new export receipt", "internal review use only"):
            self.assertIn(needle, readme)

    def test_ac11_pairing_is_verified_and_no_stale_netlist_caveat(self):
        rep = _r5b()
        self.assertEqual(rep.render_context["provenance"]["status"], "verified")
        self.assertEqual(rep.anomalies, [])


AC3_UUID = "5a000000-0000-4000-8000-0000000000a3"
AC4_UUID = "5a000000-0000-4000-8000-0000000000a4"
WIRE_DA = "9c2f1b3e-0000-4000-8000-0000000000da"


def _f_of(rep):
    return next(c for c in rep.classes if c.id == "f")


def _obs(rep, code=None):
    return [o for o in _f_of(rep).observations if code is None or o.code == code]


class InkAC3AC4Synthetic(unittest.TestCase):
    """AC3 (P1 positive), AC4 (no union leak). Twin = clean_divider (same bytes minus
    the one rectangle), measured under the same build."""

    def test_ac3_one_wire_crossing_gives_exactly_one_observation_and_no_finding(self):
        rep, twin = _m(SYN, "ac3_wire_cross"), _clean()
        obs = _obs(rep)
        self.assertEqual([(o.code, o.label) for o in obs], [("F_WIRE_THROUGH_INK", "cross")])
        self.assertEqual(obs[0].ink_uuid, AC3_UUID)
        self.assertEqual(obs[0].other, f"wire:{WIRE_DA}")
        self.assertEqual(obs[0].points, [(80.0, 60.0)])
        self.assertEqual(obs[0].kind, "observation")
        self.assertEqual(_classes_hash(rep), _classes_hash(twin))
        self.assertEqual(rep.offenders(), {})

    def test_ac4_rectangle_enclosing_two_different_net_pins_leaks_nothing(self):
        rep, twin = _m(SYN, "ac4_enclose_two_pins"), _clean()
        self.assertEqual(rep.ink_report["count"], 1)
        self.assertEqual(_classes_hash(rep), _classes_hash(twin))      # a-f verdicts + findings
        self.assertEqual((rep.verdict, rep.scoped_verdict), (twin.verdict, twin.scoped_verdict))
        sheet, net = SYN / "ac4_enclose_two_pins.kicad_sch", SYN / "ac4_enclose_two_pins.net"
        self.assertEqual(_graph_sha(sheet, net), _graph_sha(CLEAN / "clean_divider.kicad_sch", CLEAN / "clean_divider.net"))
        for c in rep.classes:
            if c.id in "abcde":
                self.assertEqual(c.findings, [], c.id)
        # the two enclosed pins sit on DIFFERENT nets; no merged component, no B1/B2
        g = rr.build_drawn_graph(rr.parse_sheet(sheet.read_text()), rr.parse_netlist(net.read_text()),
                                 rr.POLICY["coord_eps_mm"])
        self.assertNotEqual(g.pin_net["R2.1"], g.pin_net["R2.2"])
        self.assertNotEqual(g.pin_comp["R2.1"], g.pin_comp["R2.2"])


class InkAC3dIsolation(unittest.TestCase):
    """AC3d / spec 2.1: observations never reach findings, defect counts, any verdict
    or any calibration cell, solely because they exist."""

    def test_valid_outline_with_observations_changes_no_verdict(self):
        for n in ("ac3_wire_cross", "ac4_enclose_two_pins"):
            rep, twin = _m(SYN, n), _clean()
            self.assertTrue(_obs(rep), n)
            self.assertEqual([(c.id, c.verdict, len(c.findings)) for c in rep.classes],
                             [(c.id, c.verdict, len(c.findings)) for c in twin.classes], n)
            self.assertEqual((rep.verdict, rep.scoped_verdict), (twin.verdict, twin.scoped_verdict), n)
            self.assertEqual(_f_of(twin).observations, [])

    def test_observations_are_not_findings_and_not_counted(self):
        rep = _m(SYN, "ac3_wire_cross")
        f = _f_of(rep)
        self.assertEqual(f.verdict, "pass")
        self.assertFalse(f.findings)
        self.assertNotIn("f", rep.offender_classes())
        self.assertFalse(any(o.kind != "observation" for o in f.observations))
        self.assertNotIn("observations", f.measurements)
        for k in ("F_WIRE_THROUGH_INK", "F_INK_THROUGH_TEXT", "F_FLAG_THROUGH_INK", "F_INK_THROUGH_PIN"):
            self.assertNotIn(k, repr(f.measurements))

    def test_observations_never_enter_a_calibration_cell(self):
        rec = _calibration_record(accepting=_HYPOTHETICAL_YES)
        rep = _m(SYN, "ac3_wire_cross", calibration_record=rec)
        self.assertNotIn("F_WIRE_THROUGH_INK", json.dumps(rep.calibration_ref, default=str))
        base = _clean(calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))
        self.assertEqual(rep.calibration_ref["status"], base.calibration_ref["status"])
        self.assertEqual(rep.calibration_ref["classes"], base.calibration_ref["classes"])
        self.assertIs(rep.calibration_ref["evidence_authenticated"], False)
        self.assertIsNone(rep.calibration_ref["authenticated_by"])

    def test_expected_equals_examined_plus_omitted(self):
        for rep in (_m(SYN, "ac3_wire_cross"), _m(SYN, "ac4_enclose_two_pins"), _r5b()):
            for code, c in _f_of(rep).observation_counts.items():
                self.assertEqual(c["expected"], c["examined"] + len(c["omitted"]), code)
                self.assertEqual(c["emitted"], len(_obs(rep, code)), code)

    def test_r5b_with_and_without_its_rectangle_gives_identical_classes(self):
        """Twin = the R5b sheet text with the one root-level rectangle removed, same
        svg/net (no receipt: the sheet bytes differ by construction)."""
        d = _scratch_dir("r5b-twin")
        text = (R5B / "usbc.kicad_sch").read_text()
        i = text.index("  (rectangle (start 99.06 76.2)")
        j = text.index('(uuid "6fe52893-6baa-5a25-8e33-fdae41b26d87"))', i) + len('(uuid "6fe52893-6baa-5a25-8e33-fdae41b26d87"))')
        (d / "usbc.kicad_sch").write_text(text[:i] + text[j:].lstrip("\n"))
        self.assertEqual(rr.parse_sheet((d / "usbc.kicad_sch").read_text()).ink, [])
        shutil.copyfile(R5B / "usbc.svg", d / "usbc.svg")
        shutil.copyfile(R5B / "usbc.net", d / "usbc.net")
        twin = measure(d / "usbc.kicad_sch", d / "usbc.svg", d / "usbc.net")
        rep = _r5b()
        self.assertEqual(_classes_hash(rep), _classes_hash(twin))
        # Native subject fails e; the non-native twin remains provenance-indeterminate.
        self.assertEqual((rep.scoped_verdict, twin.scoped_verdict), ("fail", "indeterminate"))
        self.assertEqual((rep.verdict, twin.verdict), ("fail", "indeterminate"))
        self.assertEqual(_f_of(twin).observations, [])
        self.assertTrue(_obs(rep), "R5b with its rectangle must carry observations (D1 pin stubs)")
        shutil.rmtree(d, ignore_errors=True)


def _ink(kind, uuid="5b000000-0000-4000-8000-000000000001", **geom):
    closed = kind in ("rectangle", "circle") or (kind == "polyline" and geom["points"][0] == geom["points"][-1])
    return rr.InkItem(uuid=uuid, kind=kind, geometry_mm=geom, stroke_type="dash", stroke_width=0.1524,
                      fill_type="none", closed=closed)


def _rect(x0, y0, x1, y1, **kw):
    return _ink("rectangle", corners=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **kw)


def _poly(*pts, **kw):
    return _ink("polyline", points=list(pts), **kw)


def _run_obs(ink, wires=(), texts=(), labels=(), polys=(), pins=()):
    """Unit-level: hand-built Sheet/SvgDoc (NOT a native export); exercises
    _ink_observations only. unit_scale = 1.0 so svg units are mm."""
    sym = rr.Symbol(ref="U9", lib_id="Test:U", uuid="", at=(0.0, 0.0), rot=0.0, mirror=None,
                    in_bom=True, on_board=True, unit=1,
                    pins=[rr.Pin(ref="U9", number=str(i + 1), name="~", tip=t, end=e, hidden=False, pin_type="passive")
                          for i, (t, e) in enumerate(pins)])
    sheet = rr.Sheet(paper="A4", symbols=[sym] if pins else [],
                     wires=[rr.Wire(a=a, b=b, uuid=f"w{i}") for i, (a, b) in enumerate(wires)],
                     junctions=[], labels=list(labels), no_connects=[], texts=[], ink=list(ink))
    svg = rr.SvgDoc(width_mm=297.0, height_mm=210.0, viewbox=(0, 0, 297.0, 210.0), unit_scale=1.0,
                    paths=[], circles=[], segments=set(), polys=list(polys),
                    texts=[rr.SvgText(content=c, anchor=(b[0], b[3]), bbox=b, font_size=1.27, rotation=0.0)
                           for c, b in texts])
    return rr._ink_observations(sheet, svg, dict(POLICY))


class InkAC3bP2P3P4(unittest.TestCase):
    """AC3b: positive + non-contact cell for each of P2, P3, P4 (6 cells, unit level)."""

    def test_p2_ink_through_text_positive(self):
        obs, cnt = _run_obs([_poly((15, 5), (15, 15))], texts=[("TXT", (10, 10, 20, 12))])
        self.assertEqual([(o.code, o.other, o.ink_uuid) for o in obs],
                         [("F_INK_THROUGH_TEXT", "text:TXT", "5b000000-0000-4000-8000-000000000001")])

    def test_p2_ink_through_text_non_contact(self):
        obs, cnt = _run_obs([_poly((30, 5), (30, 15))], texts=[("TXT", (10, 10, 20, 12))])
        self.assertEqual(obs, [])
        self.assertEqual((cnt["F_INK_THROUGH_TEXT"]["expected"], cnt["F_INK_THROUGH_TEXT"]["examined"]), (1, 1))

    def _flag(self):
        lab = rr.Label(kind="global_label", text="GND", at=(10.0, 10.0), uuid="l1")
        poly = ([(10.0, 10.0), (12.0, 9.0), (20.0, 9.0), (20.0, 11.0), (12.0, 11.0)], 0.15)
        return [lab], [poly]

    def test_p3_flag_through_ink_positive(self):
        labs, polys = self._flag()
        obs, _ = _run_obs([_poly((16, 5), (16, 15))], labels=labs, polys=polys)
        self.assertEqual([(o.code, o.label) for o in obs], [("F_FLAG_THROUGH_INK", "cross")])
        self.assertEqual(obs[0].other, "flag:global_label:GND@(10.0, 10.0)")

    def test_p3_flag_through_ink_non_contact(self):
        labs, polys = self._flag()
        obs, cnt = _run_obs([_poly((30, 5), (30, 15))], labels=labs, polys=polys)
        self.assertEqual(obs, [])
        self.assertEqual(cnt["F_FLAG_THROUGH_INK"]["examined"], 1)

    def test_p4_ink_through_pin_positive_is_class_f_observation(self):
        obs, _ = _run_obs([_poly((45, 51), (55, 51))], pins=[((50.0, 50.0), (50.0, 52.54))])
        self.assertEqual([(o.code, o.cls, o.kind, o.label) for o in obs],
                         [("F_INK_THROUGH_PIN", "f", "observation", "cross")])
        self.assertEqual(obs[0].other, "pin:U9.1")

    def test_p4_ink_through_pin_non_contact(self):
        obs, _ = _run_obs([_poly((45, 60), (55, 60))], pins=[((50.0, 50.0), (50.0, 52.54))])
        self.assertEqual(obs, [])


class InkAC3cGeometryKinds(unittest.TestCase):
    """AC3c: geometry kinds, tangent/endpoint handling, dedup. Unit level."""

    def _w(self, ink, a, b):
        return _run_obs([ink], wires=[(a, b)])[0]

    def test_open_polyline_positive_and_not_implicitly_closed(self):
        open_pl = _poly((0, 0), (10, 0), (10, 10))
        self.assertFalse(open_pl.closed)
        self.assertEqual([o.label for o in self._w(open_pl, (5, -5), (5, 5))], ["cross"])
        # the implicit closing diagonal (10,10)->(0,0) would be crossed at (5,5): an open path has none
        self.assertEqual(self._w(open_pl, (4, 6), (6, 4)), [])

    def test_closed_polyline_positive(self):
        closed = _poly((0, 0), (10, 0), (10, 10), (0, 0))
        self.assertTrue(closed.closed)
        self.assertEqual([o.label for o in self._w(closed, (4, 6), (6, 4))], ["cross"])

    def test_circle_positive_two_points_one_observation_and_non_contact(self):
        circ = _ink("circle", center=(50.0, 50.0), radius=5.0)
        obs = self._w(circ, (40, 51), (60, 51))
        self.assertEqual([o.label for o in obs], ["cross"])
        self.assertEqual(len(obs[0].points), 2)
        self.assertEqual(self._w(circ, (40, 60), (60, 60)), [])

    def test_circle_chord_approximation_is_documented_not_exact(self):
        """A wire on the TRUE tangent (y = cy - r) is not guaranteed to meet the chord
        polyline (sagitta <= INK_CHORD_TOL_MM): the result is the documented
        approximation, and the constant is the reported tolerance."""
        self.assertEqual(rr.INK_CHORD_TOL_MM, 0.05)
        circ = _ink("circle", center=(50.0, 50.0), radius=5.0)
        segs = rr._ink_paths(circ)
        for a, b in segs:  # every chord vertex lies on the circle; chord midpoints sag <= tol
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            self.assertLessEqual(5.0 - math.hypot(mid[0] - 50, mid[1] - 50), rr.INK_CHORD_TOL_MM + 1e-9)
        self.assertGreaterEqual(len(segs), 8)

    def test_arc_positive_and_non_contact(self):
        arc = _ink("arc", start=(45.0, 50.0), mid=(50.0, 45.0), end=(55.0, 50.0))
        self.assertFalse(arc.closed)
        self.assertEqual([o.label for o in self._w(arc, (48, 40), (48, 60))], ["cross"])
        self.assertEqual(self._w(arc, (48, 50.5), (48, 60)), [])

    def test_rectangle_interior_is_not_ink(self):
        self.assertEqual(self._w(_rect(0, 0, 10, 10), (3, 3), (7, 7)), [])

    def test_endpoint_on_edge_is_touch_and_collinear_is_overlap(self):
        r = _rect(0, 0, 10, 10)
        self.assertEqual([o.label for o in self._w(r, (5, 5), (5, 0))], ["touch"])
        self.assertEqual([o.label for o in self._w(r, (2, 0), (8, 0))], ["overlap"])

    def test_two_crossings_on_one_pair_give_one_observation_with_two_points(self):
        obs = self._w(_rect(0, 0, 10, 10), (-5, 5), (15, 5))
        self.assertEqual(len(obs), 1)
        self.assertEqual((obs[0].label, sorted(obs[0].points)), ("cross", [(0.0, 5.0), (10.0, 5.0)]))


def _synthetic_owned_sheet(name):
    """SYNTHETIC (separately labelled): ac3_wire_cross bytes with the rectangle uuid
replaced by uuid5(R1.uuid, 'presentation.outline'). Not a historical subject."""
    d = _scratch_dir(name)
    text = (SYN / "ac3_wire_cross.kicad_sch").read_text()
    r1 = next(s for s in rr.parse_sheet(text).symbols if s.ref == "R1")
    want = str(_uuid.uuid5(_uuid.UUID(r1.uuid), "presentation.outline"))
    (d / "s.kicad_sch").write_text(text.replace(AC3_UUID, want))
    shutil.copyfile(SYN / "ac3_wire_cross.svg", d / "s.svg")
    shutil.copyfile(SYN / "ac3_wire_cross.net", d / "s.net")
    return d, want


class InkAC5Ownership(unittest.TestCase):
    RULE = {"id": "presentation-outline", "version": "1", "name": "presentation.outline", "targets": ["R1"]}

    def _sheet(self):
        return rr.parse_sheet((SYN / "ac3_wire_cross.kicad_sch").read_text())

    def test_ac5_no_declaration_is_unknown_and_listed(self):
        rep = _m(SYN, "ac3_wire_cross")
        self.assertEqual(rep.sheet_graphic_ink[0]["owner"], "unknown")
        self.assertEqual(rep.ink_report["ink_owner_unknown"], [AC3_UUID])
        self.assertEqual((rep.ink_report["owner_mode"], rep.ink_report["owner_declaration_mismatch"]), ("none", []))
        self.assertEqual(_obs(rep)[0].ownership_assessment, "unmeasured")
        self.assertEqual(_obs(rep)[0].owner, "unknown")

    def test_ac5_explicit_map_checks_exact_identities_only(self):
        sh = self._sheet()
        res = rr._resolve_ink_owners(sh, {AC3_UUID: "R1"}, None)
        self.assertEqual((sh.ink[0].owner, res["mode"], res["mismatches"]), ("R1", "explicit_map", []))
        # a map never reproduces uuid5: a map naming an absent ink uuid is a mismatch
        sh = self._sheet()
        res = rr._resolve_ink_owners(sh, {"not-on-sheet": "R1"}, None)
        self.assertEqual(sh.ink[0].owner, "unknown")
        self.assertEqual(res["mismatches"][0]["reason"], "ink uuid not on sheet")

    def test_ac5_wrong_declaration_is_unknown_plus_mismatch(self):
        for decl in ({AC3_UUID: "NOPE"},):
            sh = self._sheet()
            res = rr._resolve_ink_owners(sh, decl, None)
            self.assertEqual(sh.ink[0].owner, "unknown")
            self.assertEqual(res["mismatches"][0]["reason"], "symbol ref not on sheet")
        sh = self._sheet()  # rule that does not reproduce this (non-uuid5) ink uuid
        res = rr._resolve_ink_owners(sh, None, self.RULE)
        self.assertEqual(sh.ink[0].owner, "unknown")
        self.assertIn("does not reproduce", res["mismatches"][0]["reason"])

    def test_ac5_duplicate_or_ambiguous_targets_assign_no_owner(self):
        sh = self._sheet()
        sh.ink.append(_rect(0, 0, 1, 1, uuid=AC3_UUID))   # duplicate ink uuid
        res = rr._resolve_ink_owners(sh, {AC3_UUID: "R1"}, None)
        self.assertEqual({i.owner for i in sh.ink}, {"unknown"})
        self.assertIn("ambiguous", res["mismatches"][0]["reason"])
        sh = self._sheet()
        sh.symbols.append(sh.symbols[0])                    # duplicate symbol ref R2? (first symbol)
        ref = sh.symbols[0].ref
        res = rr._resolve_ink_owners(sh, {AC3_UUID: ref}, None)
        self.assertEqual(sh.ink[0].owner, "unknown")
        self.assertIn("ambiguous", res["mismatches"][0]["reason"])

    def test_ac5_both_modes_at_once_is_refused(self):
        with self.assertRaises(ReadabilityInputError):
            rr._resolve_ink_owners(self._sheet(), {AC3_UUID: "R1"}, self.RULE)

    def test_ac5_rule_positive_on_a_labelled_synthetic_fixture(self):
        d, want = _synthetic_owned_sheet("ac5-synthetic")
        rep = measure(d / "s.kicad_sch", d / "s.svg", d / "s.net", ink_owner_rule=self.RULE)
        self.assertEqual(rep.sheet_graphic_ink[0]["uuid"], want)
        self.assertEqual(rep.sheet_graphic_ink[0]["owner"], "R1")
        self.assertEqual((rep.ink_report["owner_mode"], rep.ink_report["owner_declaration_mismatch"],
                          rep.ink_report["ink_owner_unknown"]), ("rule", [], []))
        self.assertTrue(all(o.owner == "R1" and o.ownership_assessment == "measured" for o in _obs(rep)))
        shutil.rmtree(d, ignore_errors=True)

    def test_ac5_containment_alone_never_sets_an_owner_on_r5b(self):
        rep = _r5b()
        self.assertEqual(rep.sheet_graphic_ink[0]["owner"], "unknown")
        self.assertEqual(rep.ink_report["ink_owner_unknown"], [R5B_RECT])
        self.assertTrue(_obs(rep), "the rectangle encloses D1's pins; containment must not own it")
        self.assertTrue(all(o.owner == "unknown" for o in _obs(rep)))

    def test_ac5_r5b_rule_result_is_recorded_not_claimed(self):
        """UNRESOLVED PENDING S3 RECONCILIATION. This is a recorded measurement of what
the declared rule does on the R5b bytes; it is NOT the historical AC5 claim, which
requires reproduction against BOTH pinned subjects (R5b and the S3 run-162241 D1
record) and S3-owner provenance reconciliation. No S3 run-162241 subject is pinned
here, so the claim cannot be made from this repo."""
        rep = _r5b(ink_owner_rule={"id": "presentation-outline", "version": "1",
                                   "name": "presentation.outline", "targets": ["D1"]})
        self.assertEqual(rep.ink_report["owner_mode"], "rule")
        self.assertEqual(rep.ink_report["owner_declaration_mismatch"], [])   # recorded, see receipt s13
        self.assertEqual(rep.sheet_graphic_ink[0]["owner"], "D1")
        self.assertEqual(_classes_hash(rep), BASE_RECAL_V3["r5b"][3])           # owner never moves a finding


class InkAC7AC8AC9Contract(unittest.TestCase):
    def test_ac7_authority_changes_change_the_subject_none_vs_empty_distinct(self):
        base = _m(SYN, "ac3_wire_cross")
        rule = {"id": "p", "version": "1", "name": "presentation.outline", "targets": ["R1"]}
        variants = {
            "empty_map": dict(ink_owner_map={}),
            "map_R1": dict(ink_owner_map={AC3_UUID: "R1"}),
            "map_R2": dict(ink_owner_map={AC3_UUID: "R2"}),
            "rule": dict(ink_owner_rule=rule),
            "rule_name": dict(ink_owner_rule={**rule, "name": "other"}),
            "rule_targets": dict(ink_owner_rule={**rule, "targets": ["R2"]}),
            "rule_version_only": dict(ink_owner_rule={**rule, "version": "2"}),
            "rule_extra_param": dict(ink_owner_rule={**rule, "namespace": "x"}),
        }
        seen = {base.subject_manifest_sha256}
        for k, kw in variants.items():
            try:
                rep = _m(SYN, "ac3_wire_cross", **kw)
            except ReadabilityInputError:
                self.fail(k)
            self.assertEqual(rep.render_context["artifact_hashes"], base.render_context["artifact_hashes"], k)
            self.assertNotIn(rep.subject_manifest_sha256, seen, k)
            seen.add(rep.subject_manifest_sha256)
        self.assertEqual(_m(SYN, "ac3_wire_cross").subject_manifest_sha256, base.subject_manifest_sha256)

    def test_ac7_ink_free_subjects_ignore_the_none_declaration(self):
        """An ink-free sheet with no declaration keeps its 9c18bc51 manifest (AC6)."""
        self.assertEqual(_clean().subject_manifest_sha256[:16], BASE_RECAL_V3["clean"][0])

    def test_ac8_unparsed_kinds_are_counted_not_dropped(self):
        text = (CLEAN / "clean_divider.kicad_sch").read_text().rstrip()
        extra = ('  (bezier (pts (xy 0 0) (xy 1 1) (xy 2 2) (xy 3 3)) (uuid "5c000000-0000-4000-8000-000000000001"))\n'
                 '  (text_box "hi" (at 1 1 0) (size 5 5) (uuid "5c000000-0000-4000-8000-000000000002"))\n')
        sh = rr.parse_sheet(text[:-1] + extra + ")\n")
        self.assertEqual(sh.ink, [])
        self.assertEqual(sh.ink_unparsed, {"bezier": 1, "text_box": 1})

    def test_ac8_missing_uuid_is_counted_not_invented(self):
        text = (CLEAN / "clean_divider.kicad_sch").read_text().rstrip()
        sh = rr.parse_sheet(text[:-1] + "  (rectangle (start 0 0) (end 1 1) (stroke (width 0.1) (type default)) (fill (type none)))\n)\n")
        self.assertEqual((len(sh.ink), sh.ink[0].uuid, sh.ink_missing_uuid), (1, "", 1))

    def test_ac9_every_new_code_is_class_f_observation_and_no_coherence_claim(self):
        codes = {"F_WIRE_THROUGH_INK", "F_INK_THROUGH_TEXT", "F_FLAG_THROUGH_INK", "F_INK_THROUGH_PIN"}
        rep = _r5b()
        self.assertEqual(set(_f_of(rep).observation_counts), codes)
        for rr_ in (rep, _m(SYN, "ac3_wire_cross"), _m(SYN, "ac4_enclose_two_pins")):
            for o in _f_of(rr_).observations:
                self.assertEqual((o.cls, o.kind), ("f", "observation"))
                self.assertIn(o.code, codes)
            for c in rr_.classes:
                self.assertFalse({f.code for f in c.findings} & codes)
        src = Path(rr.__file__).read_text()
        self.assertFalse(re.search(r'code="[A-Z_]*(COHERENCE|GROUP|PACKAGE)[A-Z_]*"', src))
        e = next(c for c in rep.classes if c.id == "e")
        self.assertTrue(e.measured)                      # class e keeps its existing geometric checks
        self.assertIn("symbol coherence", " ".join(rep.measurement_scope["not_assessed"]))

    def test_ac9_calibration_stays_partial_and_unauthenticated(self):
        for rep in (_r5b(calibration_record=_calibration_record()),
                    _m(SYN, "ac3_wire_cross", calibration_record=_calibration_record(accepting=_HYPOTHETICAL_YES))):
            self.assertIs(rep.calibration_ref["evidence_authenticated"], False)
            self.assertIsNone(rep.calibration_ref["authenticated_by"])
            self.assertNotEqual(rep.calibration_ref["status"], "calibrated") if rep.calibration_ref["status"] == "partial" else None
        self.assertEqual(_r5b(calibration_record=_calibration_record()).calibration_ref["status"], "partial")

    def test_identity_scope_version_is_reported_beside_the_policy_digest(self):
        rep = _r5b()
        self.assertEqual(rep.measurement_scope["version"], rr.MEASUREMENT_SCOPE_VERSION)
        self.assertEqual(rep.measurement_scope["policy_digest"], rep.policy_ref["digest"])
        self.assertEqual(rep.policy_ref["digest"], "210cdba1bd6f4e52")   # recalibrated adjacent-pin stub
        self.assertEqual(rep.measurement_scope["ink_chord_tol_mm"], 0.05)


class LabelFlagCorridor(unittest.TestCase):
    def native(self, name):
        root = FIX / "e_label_flag"
        return measure(root / (name + ".kicad_sch"), root / (name + ".svg"), root / (name + ".net"))

    def findings(self, rep):
        return [f for c in rep.classes for f in c.findings if f.code == "E_LABEL_FLAG_CORRIDOR"]

    def cell(self, offset=False, kind="global_label", detached=False):
        sh = rr.parse_sheet((CLEAN / "clean_divider.kicad_sch").read_text())
        sh.symbols = []
        sh.labels = [rr.Label(kind, "TEST", (10., 10.), "flag")]
        sh.wires = [rr.Wire((10., 10.), (14., 10.), "attached")]
        if offset:
            sh.wires.append(rr.Wire((6., 5.), (6., 15.), "passing"))
        if detached:
            sh.wires = [sh.wires[-1]]
        svg = rr.parse_svg((CLEAN / "clean_divider.svg").read_text())
        svg.polys = [([(10., 10.), (9., 9.), (7., 9.), (7., 11.), (9., 11.)], .1524)]
        g = rr.build_drawn_graph(sh, {}, .01)
        return rr._class_e(sh, g, svg, POLICY)

    def test_a_r6_outline_vertex(self):
        fs = self.findings(self.native("usbc_r6"))
        f = next(f for f in fs if "wire:a0ef10fe-4c98-47a9-9ad6-b9fbf6e0424e" in f.objects
                 and "label:5da45a9f-269b-4f2f-b76f-f95fc0eb8d85" in f.objects)
        self.assertAlmostEqual(f.measurements["distance_mm"], .4347, places=4)
        self.assertAlmostEqual(f.at[0], 67.31, places=4)
        self.assertAlmostEqual(f.at[1], 48.26, places=4)
        self.assertEqual(f.measurements["net_relation"], "foreign")

    def test_b_r7_top_edge(self):
        fs = self.findings(self.native("power_rail_r7"))
        f = next(f for f in fs if "wire:cd03567b-651e-4a1e-8ab4-5be11774d395" in f.objects
                 and "label:4554b19c-1dea-431a-80e4-4d5e2e2a8dac" in f.objects)
        self.assertAlmostEqual(f.measurements["distance_mm"], 1.2696, places=4)
        self.assertEqual(f.measurements["net_relation"], "same")
        self.assertEqual(f.measurements["label_net_authority"], "attached_wire")

    def test_c_clean(self):
        self.assertEqual(self.findings(_clean()), [])

    def test_d_terminating_anchor_exemption(self):
        self.assertEqual(self.cell().findings, [])

    def test_e_offset(self):
        fs = self.cell(offset=True, detached=True).findings
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0].measurements["net_relation"], "unbound")
        self.assertEqual(fs[0].measurements["label_net_authority"], "none")
        self.assertEqual(fs[0].measurements["contact"], "corridor")

    def test_f_hierarchical(self):
        fs = self.cell(offset=True, kind="hierarchical_label").findings
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0].code, "E_LABEL_FLAG_CORRIDOR")

    def test_g_adjacent_pin_synthetic_accepting(self):
        fs = self.findings(self.native("adjacent_pin_synthetic"))
        self.assertEqual(fs, [])

    def test_h_power_rail_v4_accepting(self):
        fs = self.findings(self.native("power_rail_v4_site1"))
        self.assertEqual(fs, [])


if __name__ == "__main__":
    unittest.main()
