"""R9 skill-shipping conformance (BR_20260730).

owning spec: opencode ``specs/mcp-integration-standard/`` R9 (living)

These tests encode the contract the BR found broken, so a regression is a red
test rather than a silent 404 on a remote client:

  R9.9.1  every advertised ``name`` is BARE  — no ``.tar.gz``/``.zip`` suffix
  R9.10.2 every advertised name is actually SERVED at ``/skills/<name>.zip``
  R9.7.1  the produced archive carries no absolute path, no ``..``, no symlink
  R9.11   the served source IS the tree ``mcp.json skillPaths`` declares
  R9.6.2  an unknown name is a typed 4xx, never a 200 holding an empty archive

The negative controls matter as much as the positive ones: a guard that
rejects everything passes every positive test while shipping nothing (R6
checklist discipline), so each traversal case is paired with an accepting
control proving a legitimate name still works.
"""
import importlib.util
import io
import json
import tarfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "bodesign_skill_shipping_under_test", REPO_ROOT / "services" / "mcp" / "skill_shipping.py")
SS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(SS)


class SkillShippingListingTests(unittest.TestCase):
    """R9.9 — the listing advertises NAMES, and each is downloadable."""

    def test_declared_source_is_the_served_source(self):
        # R9.11 — the whole point of the rewrite: one tree, not two artifacts.
        declared = SS.declared_skill_paths()
        self.assertEqual(["skills"], declared)
        self.assertEqual((REPO_ROOT / "skills").resolve(), SS.skills_root())

    def test_every_advertised_name_is_bare(self):
        # The exact defect BR_20260730 measured: a filename in `name` makes a
        # conformant consumer dial `<file>.tar.gz.zip` and 404 on every skill.
        for item in SS.list_shippable_skills():
            name = item["name"]
            for suffix in (".zip", ".tar.gz", ".tgz", ".tar", ".gz"):
                self.assertFalse(name.endswith(suffix),
                                 f"{name!r} advertises an archive extension (R9.9.1)")
            self.assertNotIn("/", name)
            self.assertNotIn("\\", name)
            self.assertNotIn("..", name)

    def test_listing_covers_the_declared_tree(self):
        names = {i["name"] for i in SS.list_shippable_skills()}
        self.assertIn("bodesign", names, "the companion skill must be shipped")
        self.assertIn("bodesign-kb", names)

    def test_listing_only_includes_dirs_with_skill_md(self):
        # R9.10.2 — advertising a name the consumer cannot materialize (no
        # SKILL.md) is itself the violation, so the listing filter and the
        # consumer's success condition must be the same predicate.
        for item in SS.list_shippable_skills():
            self.assertTrue((SS.skills_root() / item["name"] / "SKILL.md").is_file())

    def test_advertised_url_matches_the_mandated_endpoint(self):
        for item in SS.list_shippable_skills():
            self.assertEqual(f"/skills/{item['name']}.zip", item["url"])


class SkillZipContentTests(unittest.TestCase):
    """R9.7.1 — the archive is untrusted input at the far end; produce it clean."""

    def setUp(self):
        self.blob = SS.pack_skill_zip("bodesign")
        self.zf = zipfile.ZipFile(io.BytesIO(self.blob))

    def test_zip_is_a_real_zip_and_not_empty(self):
        # R9.6.2 — a 200 with an empty body is worse than a 404 for a consumer.
        self.assertGreater(len(self.blob), 1000)
        self.assertIsNone(self.zf.testzip())
        self.assertGreater(len(self.zf.namelist()), 100)

    def test_members_are_wrapped_in_the_skill_dir(self):
        # opencode's pickSkillRoot accepts flat too, but the fleet precedent
        # (docxmcp) wraps, and a wrapped archive survives a naive unzip into a
        # skills parent without scattering files across it.
        for member in self.zf.namelist():
            self.assertTrue(member.startswith("bodesign/"), member)
        self.assertIn("bodesign/SKILL.md", self.zf.namelist())

    def test_no_absolute_paths_and_no_parent_segments(self):
        for member in self.zf.namelist():
            self.assertFalse(member.startswith("/"), member)
            self.assertFalse(member.startswith("\\"), member)
            self.assertNotIn("..", Path(member).parts, member)

    def test_no_symlink_members(self):
        # The retired vendored tarball carried 2 (engines/emc, engines/datasheets).
        # opencode's consumer hard-fails the WHOLE skill on any symlink, so one
        # stray link turns a 1 MB download into a failed materialization.
        for info in self.zf.infolist():
            mode = info.external_attr >> 16
            self.assertNotEqual(0o120000, mode & 0o170000,
                                f"{info.filename} is a symlink (R9.7.1)")

    def test_ships_the_content_the_frozen_tarball_had_lost(self):
        # Regression anchor for the drift the BR uncovered: the 2026-06-10
        # snapshot was missing the R15 doctrine one-source AND the entire
        # scripts/ dir (gate.py — the sole entrypoint for ~52 landing verbs).
        names = self.zf.namelist()
        self.assertIn("bodesign/doctrine.md", names)
        self.assertIn("bodesign/scripts/gate.py", names)

    def test_excludes_caches_and_dotfiles(self):
        for member in self.zf.namelist():
            parts = Path(member).parts[1:]  # drop the wrapper dir
            self.assertNotIn("__pycache__", parts, member)
            for part in parts:
                self.assertFalse(part.startswith("."), member)

    def test_private_vault_symlinks_are_not_shipped(self):
        # skills/bodesign/.gitignore marks openmv + thesmart_products as the
        # maintainer's product-board vault: "NEVER distribute". They are dangling
        # symlinks here, and the symlink exclusion must keep them out.
        for member in self.zf.namelist():
            self.assertNotIn("openmv", Path(member).parts, member)
            self.assertNotIn("thesmart_products", Path(member).parts, member)

    def test_archive_is_byte_reproducible(self):
        # Fixed mtimes: "did the shipped skill change?" must be answerable by
        # hash, not confounded by a fresh checkout's timestamps.
        self.assertEqual(self.blob, SS.pack_skill_zip("bodesign"))


class SkillTargzTests(unittest.TestCase):
    """Back-compat format, same tree — the format must not encode a difference."""

    def test_targz_projects_the_same_file_set_as_the_zip(self):
        names_tar = {m.name for m in tarfile.open(
            fileobj=io.BytesIO(SS.pack_skill_targz("bodesign")), mode="r:gz").getmembers()}
        names_zip = set(zipfile.ZipFile(io.BytesIO(SS.pack_skill_zip("bodesign"))).namelist())
        self.assertEqual(names_zip, names_tar,
                         "the two formats must project one tree, not two artifacts")

    def test_targz_has_no_symlinks(self):
        tf = tarfile.open(fileobj=io.BytesIO(SS.pack_skill_targz("bodesign")), mode="r:gz")
        for member in tf.getmembers():
            self.assertFalse(member.issym() or member.islnk(), member.name)


class SkillNameGuardTests(unittest.TestCase):
    """Defence in depth, each case paired with an accepting control (R6)."""

    def test_accepting_control_a_legitimate_name_resolves(self):
        # Without this, a reject-everything guard would pass every case below.
        self.assertTrue(SS.resolve_skill_dir("bodesign").is_dir())
        self.assertTrue(SS.resolve_skill_dir("bodesign-kb").is_dir())

    def test_traversal_shapes_are_rejected(self):
        # The status is asserted EXACTLY, not as `in (400, 404)`. That disjunction
        # was the hole: it let a malformed name answer 400 while an unknown name
        # answered 404, so `bodesign%00.zip` and `nosuch.zip` failed in two
        # different vocabularies and the test still passed. R9.7.1 pins ONE
        # status for "not servable" -- external verification of BR_20260730 (V4)
        # caught this precisely because the assertion was loose enough to hide it.
        for evil in ("../mcp.json", "..", "../../etc/passwd", "a/b",
                     "a\\b", "/etc/passwd", "bodesign/../../mcp.json",
                     "%2e%2e%2fmcp.json", "bodesign\x00", "."):
            with self.subTest(name=evil):
                with self.assertRaises(SS.SkillShippingError) as ctx:
                    SS.resolve_skill_dir(evil)
                self.assertEqual(404, ctx.exception.status,
                                 f"{evil!r} must be indistinguishable in STATUS from any "
                                 f"other unservable name (R9.7.1)")

    def test_unknown_name_is_a_typed_404_not_an_empty_archive(self):
        # R9.6.2 — "no such skill" and "here is nothing" must stay distinct.
        with self.assertRaises(SS.SkillShippingError) as ctx:
            SS.resolve_skill_dir("no-such-skill")
        self.assertEqual("SKILL_NOT_FOUND", ctx.exception.code)
        self.assertEqual(404, ctx.exception.status)

    def test_archive_suffixed_name_is_rejected(self):
        # The consumer refuses these outright; the producer must not mint them.
        with self.assertRaises(SS.SkillShippingError) as ctx:
            SS.resolve_skill_dir("bodesign.tar.gz")
        self.assertEqual(404, ctx.exception.status)

    def test_every_unservable_name_answers_one_status(self):
        # Regression anchor for BR_20260730 V4. The defect was not that any single
        # name answered wrongly -- each answer was individually defensible -- but
        # that the SET of rejections spoke three status codes (400/403/404). A
        # consumer branching on the status line cannot classify that.
        statuses = set()
        for unservable in ("bodesign\x00", "no-such-skill", "bodesign.tar.gz",
                           "../mcp.json", "packages", "."):
            with self.assertRaises(SS.SkillShippingError) as ctx:
                SS.resolve_skill_dir(unservable)
            statuses.add(ctx.exception.status)
        self.assertEqual({404}, statuses,
                         f"unservable names must speak ONE status, got {sorted(statuses)}")
        # Accepting control: the guard is not simply "reject everything".
        self.assertTrue(SS.resolve_skill_dir("bodesign").is_dir())

    def test_directory_without_skill_md_is_not_a_skill(self):
        with self.assertRaises(SS.SkillShippingError) as ctx:
            SS.resolve_skill_dir("packages")
        self.assertEqual(404, ctx.exception.status)


class SkillSourceParityTests(unittest.TestCase):
    """R9.11.1 — the startup gate that makes a silent drift unsurvivable."""

    def test_parity_holds_for_the_declared_companion(self):
        SS.assert_skill_source_parity("bodesign")  # must not raise

    def test_parity_fails_loud_for_an_undeclared_companion(self):
        # Negative control: the assertion must be capable of failing, or it is
        # decoration. A companion absent from the declared tree is exactly the
        # MCPSTD_SKILL_HALF_SHIPPED shape.
        with self.assertRaises(RuntimeError) as ctx:
            SS.assert_skill_source_parity("not-a-shipped-skill")
        self.assertIn("parity violation", str(ctx.exception))

    def test_manifest_declaration_matches_the_repo_layout(self):
        manifest = json.loads((REPO_ROOT / "mcp.json").read_text(encoding="utf-8"))
        for declared in manifest["skillPaths"]:
            self.assertTrue((REPO_ROOT / declared).is_dir(),
                            f"skillPaths declares {declared!r} which does not exist "
                            f"(R9.4.2: declaring is not shipping)")


if __name__ == "__main__":
    unittest.main()
