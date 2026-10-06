"""Phase 1: cross-FILE connectivity of same-named global_label (root + 2 leaves).

WHY THIS FILE EXISTS
--------------------
Every other task in the multi-sheet package presupposes that two leaf .kicad_sch
files, each carrying a global_label of the SAME name, end up on ONE net. That had
never been measured. Within a single file, same-name connectivity is trivial, and
it shares its observable ("the two ends are on one net") with the cross-file case
-- so the single-file evidence could not settle it.

DISCRIMINATING STRUCTURE (spec.md AC-4, plan test-vectors TV-1 / TV-2)
---------------------------------------------------------------------
TV-1 treatment: leafA and leafB both label NET_X  -> R1 and R2 must share a net.
TV-2 control:   leafA NET_X, leafB NET_Y          -> they must NOT share a net.

The control is not optional. Without it, a passing treatment cannot be told apart
from a netlist exporter that merges everything it sees, or from an exporter that
silently read only one leaf. Both would also report "the two ends are on one net".

A third witness adds evidence the two cells above do not state directly: each
netlist must contain sheetpaths /leafA/ AND /leafB/, naming the files the exporter
actually entered. TV-1 and TV-2 already assert that both R1 and R2 appear, so a
wholly unread leaf would surface there too; the sheetpath cell says which FILE was
entered rather than which symbol was found.

No fixture bytes are committed and no netlist is hand-written: the schematics are
generated into a scratch dir and arbitrated by the real `kicad-cli sch export
netlist`. When kicad-cli is absent the tests SKIP -- per errors.md, an unavailable
arbiter yields `indeterminate`, and recording that as a pass would be the exact
absence/failure collapse this package forbids.

Scratch is bound explicitly to $XDG_RUNTIME_DIR (repo AGENTS.md §3: /tmp and
/var/tmp are forbidden). The caller's TMPDIR is deliberately NOT consulted -- an
unset or non-directory XDG_RUNTIME_DIR raises rather than silently relocating.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCHEMATIC_VERSION = "20250114"
_SCRATCH_SLUG = "bodesign-multisheet-phase1"


def _scratch_root() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        raise RuntimeError(
            "XDG_RUNTIME_DIR is unset; this test refuses to fall back to TMPDIR or "
            "/tmp (repo AGENTS.md §3 scratch placement rule)")
    root = Path(runtime_dir)
    if not root.is_dir():
        raise RuntimeError(f"XDG_RUNTIME_DIR={runtime_dir!r} is not a directory")
    scratch = root / _SCRATCH_SLUG
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(scratch, 0o700)
    return scratch

# Minimal in-file symbol def. Two passive pins; only pin 1 is wired to the label,
# so pin 2 lands on an `unconnected-(Rn-Pad2)` net -- itself a useful signal that
# the exporter is doing real connectivity analysis rather than echoing labels.
_LIB_R = '''    (symbol "Device:R"
      (pin_numbers (hide yes))
      (pin_names (offset 0))
      (exclude_from_sim no) (in_bom yes) (on_board yes)
      (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
      (property "Value" "R" (at 0 0 90) (effects (font (size 1.27 1.27))))
      (symbol "R_0_1"
        (rectangle (start -1.016 -2.54) (end 1.016 2.54)
          (stroke (width 0.254) (type default)) (fill (type none)))
      )
      (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27)))))
      )
    )'''

_PROJECT_JSON = '{\n  "board": {},\n  "schematic": {},\n  "sheets": [],\n  "version": 1\n}\n'


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _leaf(root_uuid: str, sheet_uuid: str, ref: str, label: str, project: str) -> str:
    """A leaf sheet: one resistor whose pin 1 is wired to a global_label."""
    pin_x, pin_y = 100.0, 96.19     # pin 1 endpoint of an R placed at (100,100)
    lab_x, lab_y = 100.0, 90.0      # label anchor, joined to the pin by one wire
    return f'''(kicad_sch
  (version {SCHEMATIC_VERSION})
  (generator "bodesign")
  (generator_version "9.0")
  (uuid "{_new_uuid()}")
  (paper "A4")
  (lib_symbols
{_LIB_R}
  )
  (symbol (lib_id "Device:R") (at 100 100 0) (unit 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{_new_uuid()}")
    (property "Reference" "{ref}" (at 103 99 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "10k" (at 103 101 0) (effects (font (size 1.27 1.27)) (justify left)))
    (instances (project "{project}" (path "/{root_uuid}/{sheet_uuid}" (reference "{ref}") (unit 1))))
  )
  (wire (pts (xy {pin_x} {pin_y}) (xy {lab_x} {lab_y})) (stroke (width 0) (type default)) (uuid "{_new_uuid()}"))
  (global_label "{label}" (shape bidirectional) (at {lab_x} {lab_y} 90)
    (effects (font (size 1.27 1.27)) (justify left)) (uuid "{_new_uuid()}"))
  (sheet_instances (path "/" (page "1")))
)
'''


def _sheet_block(name, fname, sheet_uuid, root_uuid, project, page, pos_x) -> str:
    """One (sheet ...) block in the root. Fields per data-schema RootSheetBlock."""
    return f'''  (sheet (at {pos_x} 50) (size 20 20)
    (stroke (width 0.1524) (type solid))
    (fill (color 0 0 0 0.0000))
    (uuid "{sheet_uuid}")
    (property "Sheetname" "{name}" (at {pos_x} 49.3 0)
      (effects (font (size 1.27 1.27)) (justify left bottom)))
    (property "Sheetfile" "{fname}" (at {pos_x} 70.7 0)
      (effects (font (size 1.27 1.27)) (justify left top)))
    (instances (project "{project}" (path "/{root_uuid}" (page "{page}"))))
  )'''


def _write_case(out_dir: Path, label_a: str, label_b: str, project: str = "phase1") -> Path:
    """Build root + leafA + leafB on disk; return the root path.

    Filenames follow the frozen layout (design.md DD-7 clause 6):
    root `<out>/<project>.kicad_sch`, leaves `<out>/<sheet>.kicad_sch`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    root_uuid, sheet_a, sheet_b = _new_uuid(), _new_uuid(), _new_uuid()
    (out_dir / "leafA.kicad_sch").write_text(_leaf(root_uuid, sheet_a, "R1", label_a, project))
    (out_dir / "leafB.kicad_sch").write_text(_leaf(root_uuid, sheet_b, "R2", label_b, project))
    root_path = out_dir / f"{project}.kicad_sch"
    root_path.write_text(f'''(kicad_sch
  (version {SCHEMATIC_VERSION})
  (generator "bodesign")
  (generator_version "9.0")
  (uuid "{root_uuid}")
  (paper "A4")
  (lib_symbols
  )
{_sheet_block("leafA", "leafA.kicad_sch", sheet_a, root_uuid, project, 2, 50)}
{_sheet_block("leafB", "leafB.kicad_sch", sheet_b, root_uuid, project, 3, 100)}
  (sheet_instances (path "/" (page "1")))
)
''')
    (out_dir / f"{project}.kicad_pro").write_text(_PROJECT_JSON)
    return root_path


def _export_netlist(root_path: Path) -> str:
    """Run the real kicad-cli. Raises AssertionError with stderr on failure."""
    out_path = root_path.parent / "net.net"
    proc = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
         "-o", str(out_path), str(root_path)],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, f"kicad-cli rc={proc.returncode} stderr={proc.stderr!r}"
    assert out_path.exists(), f"kicad-cli rc=0 but wrote no netlist; stderr={proc.stderr!r}"
    return out_path.read_text()


_NET_RE = re.compile(
    r'\(net\s+\(code\s+"?\d+"?\)\s*\(name\s+"([^"]*)"\)(.*?)(?=\n\s*\(net\s|\Z)', re.S)
_NODE_RE = re.compile(r'\(node\s+\(ref\s+"([^"]+)"\)')


def _ref_to_nets(netlist_text: str) -> dict[str, set[str]]:
    """ref -> set of net names carrying at least one of its pins."""
    out: dict[str, set[str]] = {}
    for name, body in _NET_RE.findall(netlist_text):
        for ref in _NODE_RE.findall(body):
            out.setdefault(ref, set()).add(name)
    return out


@unittest.skipUnless(shutil.which("kicad-cli"), "kicad-cli not on host (arbitration indeterminate)")
class MultiSheetGlobalLabelLinkTest(unittest.TestCase):
    """AC-4: both cells required. Treatment alone cannot carry the claim."""

    def _run_case(self, label_a: str, label_b: str):
        with tempfile.TemporaryDirectory(
                prefix="ms_phase1_", dir=str(_scratch_root())) as scratch_dir:
            os.chmod(scratch_dir, 0o700)
            root = _write_case(Path(scratch_dir), label_a, label_b)
            text = _export_netlist(root)
            return text, _ref_to_nets(text)

    def test_same_name_global_labels_merge_across_files(self):
        """TV-1 treatment: leafA NET_X + leafB NET_X -> R1 and R2 share one net."""
        text, refs = self._run_case("NET_X", "NET_X")
        self.assertIn("R1", refs, f"R1 absent from netlist; refs={sorted(refs)}")
        self.assertIn("R2", refs, f"R2 absent from netlist; refs={sorted(refs)}")
        shared = refs["R1"] & refs["R2"]
        self.assertEqual(
            shared, {"NET_X"},
            f"expected R1/R2 to share exactly NET_X; R1={sorted(refs['R1'])} "
            f"R2={sorted(refs['R2'])} shared={sorted(shared)}")

    def test_different_name_global_labels_stay_separate(self):
        """TV-2 control: leafA NET_X + leafB NET_Y -> no shared net.

        Without this, a passing treatment is indistinguishable from an exporter
        that merges everything, or one that read a single leaf twice.
        """
        text, refs = self._run_case("NET_X", "NET_Y")
        self.assertIn("R1", refs)
        self.assertIn("R2", refs)
        shared = refs["R1"] & refs["R2"]
        self.assertEqual(
            shared, set(),
            f"different-named labels must NOT share a net; R1={sorted(refs['R1'])} "
            f"R2={sorted(refs['R2'])} shared={sorted(shared)}")
        self.assertIn("NET_X", refs["R1"])
        self.assertIn("NET_Y", refs["R2"])

    def test_both_leaf_files_were_actually_traversed(self):
        """Sheetpath witness: the netlist names the files the exporter entered.

        The two cells above already assert R1 and R2 are both present, so an
        entirely unread leaf shows up there as well. This cell adds the file-level
        statement -- which sheet was entered, not merely which symbol was found.
        """
        for label_b in ("NET_X", "NET_Y"):
            with self.subTest(label_b=label_b):
                text, _ = self._run_case("NET_X", label_b)
                self.assertIn('(sheetpath (names "/leafA/")', text,
                              "leafA was never traversed by kicad-cli")
                self.assertIn('(sheetpath (names "/leafB/")', text,
                              "leafB was never traversed by kicad-cli")


if __name__ == "__main__":
    unittest.main()
