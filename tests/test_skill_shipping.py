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
import hashlib
import importlib.util
import io
import json
import re
import tarfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# BR_20260730 round 7 -- ONE definition, used both by the guard that scans the
# docs and by the test that proves the guard can see a rephrasing. The first
# attempt kept a second copy inside the capability test, so narrowing the live
# guard left every test green: a second declaration of the very rule this BR
# family exists to stop, inside the fix for it.
_COUNT_RESTATEMENT = re.compile(
    # (?<![\w.-]) keeps the digit from being the tail of an identifier:
    # "Bucket-2 verbs" and "R17.2 tools" name a bucket and a spec clause,
    # not a roster size.
    # ROSTER NOUNS ONLY. `deterministic` was here until round 8 and is an
    # ADJECTIVE, not a thing you can have N of: it matched "ran 300
    # deterministic tests", "2015 deterministic build" (a YEAR). A guard that
    # flags a year is a guard someone will silence.
    r"~?(?<![\w.-])\d+\b(?:\s+[\w-]+){0,3}?\s+"
    r"(?:verbs?|tools?)\b", re.IGNORECASE)

# Two exclusions, each for a reason -- not to make the guard quiet.
# 1. HTTP status codes: prose about this BR family says "answered 200 for a
#    tool that does not exist". That 200 is a status, not a roster size.
# 2. A sentence naming the authoritative source in the same breath is saying
#    WHERE the number comes from rather than restating it.
_COUNT_STATUS_CODE = re.compile(r"^(?:200|301|307|400|403|404|409|500)\b")


def count_restatements(text: str) -> list[str]:
    """Every hand-copied verb/tool count in `text`. Empty list == clean."""
    return [h for h in _COUNT_RESTATEMENT.findall(text)
            if not _COUNT_STATUS_CODE.match(h)
            and "--list" not in h and "/tools" not in h]
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
                           "../mcp.json", "packages", ".",
                           # Round-2 additions. Each of these is WELL-FORMED by
                           # `_SAFE_NAME_RE` and fails only at the filesystem, so
                           # the textual guard above never sees them -- exactly
                           # the class the first fix missed.
                           "a" * 256, "a" * 300, "a" * 4096):
            with self.assertRaises(SS.SkillShippingError) as ctx:
                SS.resolve_skill_dir(unservable)
            statuses.add(ctx.exception.status)
        self.assertEqual({404}, statuses,
                         f"unservable names must speak ONE status, got {sorted(statuses)}")
        # Accepting control: the guard is not simply "reject everything".
        self.assertTrue(SS.resolve_skill_dir("bodesign").is_dir())

    def test_name_longer_than_the_os_limit_is_a_404_not_a_crash(self):
        # Regression anchor for BR_20260730 round-2 (W1). NAME_MAX is 255 bytes
        # on Linux, and this defect lives EXACTLY at that seam: 255 was already a
        # clean 404 (the OS looks it up and says no), while 256 raised a bare
        # OSError(ENAMETOOLONG) out of the `is_dir()` stat and became a 500.
        #
        # The suite passed 24/24 while shipping this because every fixture was a
        # name a HUMAN would call suspicious -- traversal, NUL, a suffix. None was
        # merely LONG. The lesson is about fixture selection, not assertions: a
        # guard is only tested against the shapes someone thought to write down.
        boundary = {}
        for length in (254, 255, 256, 300, 4096):
            with self.assertRaises(SS.SkillShippingError) as ctx:
                SS.resolve_skill_dir("a" * length)
            boundary[length] = ctx.exception.status
        self.assertEqual({254: 404, 255: 404, 256: 404, 300: 404, 4096: 404}, boundary,
                         "crossing NAME_MAX must not change the status a client sees")
        # Accepting control -- a plain long-ish name is still rejected for being
        # unknown, not for being long, and a real name still resolves.
        self.assertTrue(SS.resolve_skill_dir("bodesign").is_dir())

    def test_static_asset_branch_answers_none_for_every_unservable_name(self):
        # Coverage for the OTHER `/skills/<name>` branch -- the one that served
        # BOTH round-1 (403) and round-2 (500) defects while the suite stayed
        # green. It had zero tests because it was an inline closure inside
        # `run_http`: constructing it needed starlette + a live app, so nothing
        # ever did. Extracting the decision to a pure function is what makes
        # this test possible at all, and that is the actual fix -- an untested
        # branch holding half the "is this name servable?" decision is how the
        # two branches drifted into different answers twice in a row.
        root = REPO_ROOT / "services" / "mcp" / "assets" / "skills"
        if not root.is_dir():
            self.skipTest("vendored bundle dir absent in this checkout")
        root = root.resolve()
        for unservable in ("../../mcp.json", "..", "nosuch.tar.gz", "bodesign\x00",
                           "a" * 256, "a" * 300, "a" * 4096, "", ".",
                           "/etc/passwd", "MANIFEST.md.bak"):
            with self.subTest(name=unservable[:24]):
                # `None` (-> 404) for every one, and never a raised exception:
                # an escaping OSError is exactly what became the round-2 500.
                self.assertIsNone(SS.resolve_static_asset(root, unservable))
        # Accepting control -- without it, a function that returned None
        # unconditionally would pass every assertion above.
        served = sorted(p.name for p in root.iterdir()
                        if p.is_file() and (p.name.endswith(".tar.gz")
                                            or p.name == "MANIFEST.md"))
        if served:
            self.assertIsNotNone(SS.resolve_static_asset(root, served[0]),
                                 "the guard must still serve a real vendored asset")

    def test_directory_without_skill_md_is_not_a_skill(self):
        with self.assertRaises(SS.SkillShippingError) as ctx:
            SS.resolve_skill_dir("packages")
        self.assertEqual(404, ctx.exception.status)

    def test_resolve_skill_dir_does_not_depend_on_an_outside_guard(self):
        # BR_20260730 round 3 residual. A NUL byte makes `resolve()` raise
        # ValueError, not OSError. The function was safe only because
        # `_SAFE_NAME_RE` rejects NUL a few lines earlier -- i.e. its safety was
        # borrowed from a guard OUTSIDE the try. That is the single-guard
        # dependency the sibling `resolve_static_asset` does not have, and
        # "safe by luck of ordering" is how two guards drift apart. Asserted
        # directly against the inner path so a future reorder cannot hide it.
        for pathological in ("bodesign\x00", "\x00", "a\x00b"):
            with self.subTest(name=repr(pathological)):
                with self.assertRaises(SS.SkillShippingError) as ctx:
                    SS.resolve_skill_dir(pathological)
                self.assertEqual(404, ctx.exception.status)
        # And the guard proper: catch ValueError even reaching it directly.
        try:
            (SS.skills_root() / "x\x00y").resolve()
        except ValueError:
            pass  # confirms the raise this test exists to contain
        except OSError:
            pass  # some libc/py combos surface it as OSError; either is caught
        self.assertTrue(SS.resolve_skill_dir("bodesign").is_dir())


class SkillRequestClassificationTests(unittest.TestCase):
    """BR_20260730 round 3 (D4) -- the OTHER half of the servability decision.

    Round 2 extracted the static-asset half out of the ``run_http`` closure and
    treated the structural problem as solved. The suffix routing and the
    membership gate stayed behind, still unconstructible without starlette and
    a live app, still untested -- the exact condition the round-2 commit message
    named as the root cause of two consecutive defects. These tests exist
    because that half is now reachable.
    """

    def test_zip_suffix_routes_to_the_dynamic_packer(self):
        self.assertEqual((SS.SERVE_ZIP, "bodesign"),
                         SS.classify_skill_request("bodesign.zip"))
        # Unknown-but-zip still routes to the packer: the 404 is the packer's
        # to raise (typed), not a silent fallthrough to the static branch --
        # otherwise `nosuch.zip` would answer with a bundle-dir miss instead of
        # a typed SKILL_NOT_FOUND.
        self.assertEqual((SS.SERVE_ZIP, "nosuch"),
                         SS.classify_skill_request("nosuch.zip"))

    def test_a_name_with_a_source_is_projected_never_served_frozen(self):
        # This distinction is load-bearing, not cosmetic, and round 4 (D4)
        # showed it was drawn in the wrong place. A name with an in-repo source
        # MUST be projected from it, so the format cannot encode a content
        # difference -- that drift was the original BR_20260730 defect. The
        # first cut applied it only to DECLARED skills, leaving `kicad`/`kidoc`
        # (folded in as `engines/<name>`) served from 2026-06-07 frozen copies
        # that had drifted 12 files and 9 byte-differences behind. Only a name
        # with genuinely NO source may reach the static branch.
        declared = {s["name"] for s in SS.list_shippable_skills()}
        self.assertIn("bodesign", declared, "fixture assumption")
        self.assertEqual((SS.SERVE_TARGZ, "bodesign"),
                         SS.classify_skill_request("bodesign.tar.gz"))
        self.assertEqual((SS.SERVE_ENGINE_TARGZ, "kicad"),
                         SS.classify_skill_request("kicad.tar.gz"))
        self.assertEqual((SS.SERVE_ENGINE_TARGZ, "kidoc"),
                         SS.classify_skill_request("kidoc.tar.gz"))
        # Accepting control for the OTHER side of the gate: a bundle with no
        # in-repo source must still fall through, or this "fix" would 404 the
        # 11 archives that legitimately have nowhere else to come from.
        self.assertIsNone(SS.resolve_engine_bundle("jlcpcb"))
        self.assertEqual((SS.SERVE_STATIC, "jlcpcb.tar.gz"),
                         SS.classify_skill_request("jlcpcb.tar.gz"))

    def test_projected_engine_bundle_carries_the_live_tree(self):
        # The regression anchor for D4: assert the SHIPPED bytes hold files the
        # frozen copy lacked. `ENGINE.md` is live-only in both engines, so its
        # presence proves the archive came from the tree, not the 7-week-old
        # snapshot -- exactly the assertion that would have caught the original
        # BR had it existed for this half.
        for bare in ("kicad", "kidoc"):
            with self.subTest(bundle=bare):
                blob = SS.pack_engine_targz(bare)
                with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
                    names = {m.name for m in tf.getmembers() if m.isfile()}
                self.assertIn(f"{bare}/ENGINE.md", names,
                              "shipped bundle lacks a live-only file; it is the frozen copy")
                self.assertEqual(0, int.from_bytes(blob[4:8], "little"))

    def test_engine_projection_refuses_a_name_with_no_source(self):
        # Negative control: without it, a `resolve_engine_bundle` that returned
        # some directory for everything would pass the positive tests above.
        with self.assertRaises(SS.SkillShippingError) as ctx:
            SS.pack_engine_targz("jlcpcb")
        self.assertEqual(404, ctx.exception.status)
        for hostile in ("../mcp.json", "", "a" * 4096, "kicad/../../etc"):
            with self.subTest(name=hostile[:20]):
                self.assertIsNone(SS.resolve_engine_bundle(hostile))

    def test_classification_never_raises_for_a_hostile_name(self):
        # A raise here would leave as a 500, which is the round-2 defect one
        # layer up. Every shape must classify into something the caller can
        # answer 404 with.
        for hostile in ("../mcp.json", "..", ".", "", "a" * 4096,
                        "a" * 4096 + ".zip", "bodesign\x00.tar.gz",
                        "/etc/passwd", ".tar.gz", ".zip"):
            with self.subTest(name=hostile[:24]):
                action, _ = SS.classify_skill_request(hostile)
                self.assertIn(action, (SS.SERVE_ZIP, SS.SERVE_TARGZ, SS.SERVE_STATIC))


class ArchiveReproducibilityTests(unittest.TestCase):
    """R9.11 — "did the shipped skill change?" MUST be answerable by hash.

    BR_20260730 round 4 (D2). Every member already carried a fixed timestamp,
    but ``tarfile.open(mode="w:gz")`` writes the WALL CLOCK into the gzip
    wrapper's header, so two requests one second apart produced two different
    sha256 over a byte-identical tar. A consumer diffing hashes to detect drift
    -- the precise question this BR exists to make answerable -- would see a
    change that did not happen, and would learn to ignore the signal.
    """

    def test_targz_bytes_are_identical_across_packs(self):
        first = SS.pack_skill_targz("bodesign")
        second = SS.pack_skill_targz("bodesign")
        self.assertEqual(first, second,
                         "two packs of an unchanged tree produced different bytes; "
                         "hash-based drift detection is unusable for .tar.gz")

    def test_targz_gzip_header_carries_no_wall_clock(self):
        # The decisive byte-level assertion: MTIME is bytes 4..8 of the gzip
        # header. A non-zero value here is the wall clock leaking in, which is
        # invisible to a whole-file comparison taken inside the same second --
        # the reason this defect survived a live probe.
        blob = SS.pack_skill_targz("bodesign")
        mtime = int.from_bytes(blob[4:8], "little")
        self.assertEqual(0, mtime,
                         f"gzip header MTIME={mtime} is a wall clock, not a fixed epoch")

    def test_zip_bytes_are_identical_across_packs(self):
        # Accepting control for the format that was already correct: without
        # it, a change making BOTH formats constant-but-empty would pass above.
        self.assertEqual(SS.pack_skill_zip("bodesign"), SS.pack_skill_zip("bodesign"))
        self.assertGreater(len(SS.pack_skill_zip("bodesign")), 100_000)

    def test_both_formats_project_the_same_member_set(self):
        # The original BR defect restated as an invariant: the format choice
        # must not be able to encode a content difference.
        with zipfile.ZipFile(io.BytesIO(SS.pack_skill_zip("bodesign"))) as zf:
            zip_names = {n for n in zf.namelist() if not n.endswith("/")}
        with tarfile.open(fileobj=io.BytesIO(SS.pack_skill_targz("bodesign"))) as tf:
            tar_names = {m.name for m in tf.getmembers() if m.isfile()}
        self.assertEqual(zip_names, tar_names)


class VendoredBundleClaimTests(unittest.TestCase):
    """MANIFEST.md's claims about the bundles must be checkable, not prose.

    BR_20260730 round 5 (Z2). Making `kicad`/`kidoc` current (round 4, D4) also
    made them non-installable: the live `engines/<name>` trees carry `ENGINE.md`,
    while the frozen copies they replaced carried `SKILL.md`. Both facts were
    true at once and only one was written down, so MANIFEST kept instructing
    `tar -xzf kicad.tar.gz -C ~/.claude/skills/` for an archive a skill manager
    cannot see. These tests bind the documentation to the bytes.
    """

    def test_projected_engine_trees_carry_engine_md_not_skill_md(self):
        # The shape MANIFEST now documents. If a future change adds a SKILL.md
        # to an engine tree, the docs become wrong in the OTHER direction --
        # this fails then too, which is the point.
        for bare in ("kicad", "kidoc"):
            with self.subTest(bundle=bare):
                with tarfile.open(fileobj=io.BytesIO(SS.pack_engine_targz(bare))) as tf:
                    names = {m.name for m in tf.getmembers() if m.isfile()}
                self.assertIn(f"{bare}/ENGINE.md", names)
                self.assertNotIn(f"{bare}/SKILL.md", names,
                                 "engine tree gained a SKILL.md; MANIFEST says it has none")

    def test_declared_skills_do_carry_skill_md(self):
        # Accepting control: without it, a change that stripped SKILL.md from
        # EVERYTHING would satisfy the assertion above.
        for item in SS.list_shippable_skills():
            with self.subTest(skill=item["name"]):
                with zipfile.ZipFile(io.BytesIO(SS.pack_skill_zip(item["name"]))) as zf:
                    self.assertIn(f"{item['name']}/SKILL.md", zf.namelist())

    def test_composite_bundles_stale_engine_shadow_does_not_grow(self):
        # BR_20260730 round 5: the composite `bodesign-eda-skills-bundle.tar.gz`
        # embeds a THIRD copy of kicad/kidoc, frozen 2026-06-07. It has no
        # in-repo source so it cannot be projected, and MANIFEST discloses it
        # rather than hiding it. This test is what makes that disclosure honest:
        # the shadow may not grow, and if the composite is ever regenerated from
        # the live tree the drift should go to zero and this test says so.
        composite = REPO_ROOT / "services" / "mcp" / "assets" / "skills" / \
            "bodesign-eda-skills-bundle.tar.gz"
        if not composite.is_file():
            self.skipTest("composite bundle not present")
        with tarfile.open(composite) as tf:
            frozen = {m.name: hashlib.sha256(tf.extractfile(m).read()).hexdigest()
                      for m in tf.getmembers() if m.isfile()}
        engines_root = SS.skills_root() / "bodesign" / "engines"
        drift = {}
        for bare in ("kicad", "kidoc"):
            live_dir = engines_root / bare
            if not live_dir.is_dir():
                continue
            live = {str(f.relative_to(live_dir)): hashlib.sha256(f.read_bytes()).hexdigest()
                    for f in SS._walk_skill_files(live_dir)}
            embedded = {k.split("/", 1)[1]: v for k, v in frozen.items()
                        if k.startswith(f"{bare}/") and "/" in k}
            if not embedded:
                continue
            drift[bare] = {
                "live_only": len(set(live) - set(embedded)),
                "differing": len([k for k in set(live) & set(embedded)
                                  if live[k] != embedded[k]]),
            }
        # MANIFEST discloses EXACT numbers, so the guard is exact in both
        # directions (BR_20260730 round 6, Defect 2: the original `<=` capped
        # growth only. A deleted live file, or live+composite rotting in
        # lockstep, shrinks the count and leaves the published figure wrong
        # while the test stays green -- a disclosure that silently stops
        # matching is the failure this BR family is about, not a smaller one).
        disclosed = {"kicad": (12, 9), "kidoc": (1, 1)}
        for bare, seen in drift.items():
            with self.subTest(bundle=bare):
                want_only, want_diff = disclosed[bare]
                self.assertEqual(want_only, seen["live_only"],
                                 f"{bare} shadow drift moved: MANIFEST discloses "
                                 f"{want_only} live-only, measured {seen['live_only']}. "
                                 f"Update the MANIFEST figure -- in EITHER direction.")
                self.assertEqual(want_diff, seen["differing"],
                                 f"{bare} shadow drift moved: MANIFEST discloses "
                                 f"{want_diff} byte-differences, measured "
                                 f"{seen['differing']}. Update the MANIFEST figure.")


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

    def test_source_digest_changes_when_the_tree_changes(self):
        # BR_20260730 round 4 (D3). The digest exists to make an image/commit
        # divergence remotely detectable, so its load-bearing property is that
        # it MOVES: a digest that is stable across a real content change would
        # be worse than none, since it would certify sameness that is false.
        import importlib.util
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            skill = fake / "skills" / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# demo\n" + "body\n" * 200)
            for i in range(5):
                (skill / f"f{i}.md").write_text(f"file {i}\n")
            (fake / "mcp.json").write_text(json.dumps({"skillPaths": ["skills"]}))
            (fake / "services" / "mcp").mkdir(parents=True)
            shutil.copy(REPO_ROOT / "services" / "mcp" / "skill_shipping.py",
                        fake / "services" / "mcp" / "skill_shipping.py")
            spec = importlib.util.spec_from_file_location(
                "ss_digest_probe", fake / "services" / "mcp" / "skill_shipping.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            before = mod.skill_source_digest()
            self.assertEqual(6, before["demo"]["files"])
            # Stable for an unchanged tree, or a consumer cannot diff it.
            self.assertEqual(before, mod.skill_source_digest())
            # An ADDED file (the exact D3 shape: untracked files swept into the
            # image) must move the digest.
            (skill / "swept_in.py").write_text("# untracked working-tree file\n")
            added = mod.skill_source_digest()
            self.assertNotEqual(before["demo"]["sha256"], added["demo"]["sha256"])
            self.assertEqual(7, added["demo"]["files"])
            # A same-SIZE content edit must move it too, or the digest would be
            # a file count wearing a hash's clothes.
            (skill / "f0.md").write_text("file X\n")
            edited = mod.skill_source_digest()
            self.assertNotEqual(added["demo"]["sha256"], edited["demo"]["sha256"])
            self.assertEqual(7, edited["demo"]["files"])

    def test_gate_rejects_a_decoy_tree_that_is_only_a_filename(self):
        # BR_20260730 round 4 (D5). The gate asserted PRESENCE only, so a tree
        # holding one truncated SKILL.md -- or an outright decoy reading "NOT
        # the real source" -- passed and served a 135-byte "skill". A gate that
        # cannot fail on an empty entry point is decoration, which is precisely
        # the accusation this BR has twice levelled at its own tests.
        import importlib.util
        import shutil
        import tempfile

        scenarios = {
            "empty entry point": "",
            "decoy stub": "# NOT the real source\n",
        }
        for label, entry_text in scenarios.items():
            with self.subTest(scenario=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fake = Path(tmp)
                    (fake / "skills" / "bodesign").mkdir(parents=True)
                    (fake / "skills" / "bodesign" / "SKILL.md").write_text(entry_text)
                    (fake / "mcp.json").write_text(json.dumps({"skillPaths": ["skills"]}))
                    (fake / "services" / "mcp").mkdir(parents=True)
                    shutil.copy(REPO_ROOT / "services" / "mcp" / "skill_shipping.py",
                                fake / "services" / "mcp" / "skill_shipping.py")
                    spec = importlib.util.spec_from_file_location(
                        f"ss_decoy_{abs(hash(label))}",
                        fake / "services" / "mcp" / "skill_shipping.py")
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    # Accepting control INSIDE the scenario: the decoy really is
                    # discoverable as a skill, so what follows is the floor
                    # firing, not the tree being invisible.
                    self.assertEqual(["bodesign"],
                                     [x["name"] for x in mod.list_shippable_skills()])
                    with self.assertRaises(RuntimeError) as ctx:
                        mod.assert_skill_source_parity("bodesign")
                    self.assertIn("parity violation", str(ctx.exception))

class ShippedSkillSelfContainmentTests(unittest.TestCase):
    """BR_20260730 round 6, Y1 — the archive is not self-sufficient, and that
    fact must live at the install step, not only in the error you hit later.

    The shipped skill carries `scripts/gate.py` but NOT the `packages/*` the
    verbs import, so a bare install can `--list` and nothing else. That is a
    legitimate architecture (the packages are large and version-coupled to the
    repo); what was NOT legitimate was MANIFEST's Install section telling you to
    extract and go, with no mention of `BODESIGN_SRC`. These tests pin the
    shape so the disclosure cannot silently stop matching the artifact.
    """

    MANIFEST = REPO_ROOT / "services" / "mcp" / "assets" / "skills" / "MANIFEST.md"

    def test_zip_really_omits_the_packages_the_verbs_import(self):
        # If this ever fails, the archive became self-contained -- good news,
        # but then the MANIFEST disclosure below is now a lie and must go.
        names = zipfile.ZipFile(io.BytesIO(SS.pack_skill_zip("bodesign"))).namelist()
        self.assertTrue(any(n.endswith("scripts/gate.py") for n in names),
                        "gate.py missing: the landing plane has no entrypoint at all")
        for pkg in ("workflow-core", "component-kb", "eda-bridge", "reverse-core"):
            self.assertFalse([n for n in names if f"packages/{pkg}" in n],
                             f"archive now ships packages/{pkg}; MANIFEST's "
                             f"BODESIGN_SRC disclosure is stale and must be removed")

    def test_manifest_discloses_the_dependency_at_install_time(self):
        text = self.MANIFEST.read_text(encoding="utf-8")
        install = text.split("## Install", 1)
        self.assertEqual(2, len(install), "MANIFEST lost its Install section")
        body = install[1].split("## Contents", 1)[0]
        for token in ("BODESIGN_SRC", "LANDING_PACKAGES_NOT_FOUND", "--list"):
            self.assertIn(token, body,
                          f"Install section no longer discloses {token!r}: a reader "
                          f"following it would extract, run a verb, and hit an "
                          f"undisclosed hard error (round 6, Y1)")

    def test_the_disclosed_error_code_is_the_one_gate_actually_raises(self):
        # Accepting control for the assertion above: naming a code that gate.py
        # does not emit would satisfy a substring check while misleading a reader.
        gate = (REPO_ROOT / "skills" / "bodesign" / "scripts" / "gate.py") \
            .read_text(encoding="utf-8")
        self.assertIn("LANDING_PACKAGES_NOT_FOUND", gate)
        self.assertIn("BODESIGN_SRC", gate)

    def test_docs_do_not_restate_a_hand_copied_verb_count(self):
        # Round 6 found SKILL.md claiming 52 landing verbs and 43 MCP tools while
        # the live values were 59 and 57. A number copied out of its source is a
        # second declaration, which is the exact failure mode of this BR family.
        # README.md's 0.2.0 changelog entry is exempt: it records what was true
        # on that date, and rewriting history is not the same as fixing a claim.
        import re
        for rel in ("skills/bodesign/SKILL.md",
                    "README.en.md",
                    "services/mcp/server.py",
                    "services/mcp/assets/skills/MANIFEST.md"):
            with self.subTest(doc=rel):
                text = (REPO_ROOT / rel).read_text(encoding="utf-8")
                hits = count_restatements(text)
                self.assertEqual([], hits,
                                 f"{rel} restates a verb/tool count: {hits}. Point at "
                                 f"`gate.py --list` / `/tools` instead -- they cannot drift.")


    def test_the_count_guard_is_not_blind_to_a_rephrasing(self):
        # BR_20260730 round 7, Defect 2: the first version of the guard above
        # matched only the two literal phrasings that happened to exist in the
        # tree, so it would have passed on "52 verbs" or "57 MCP tools" -- a
        # guard that is green for the wrong reason. This pins the CAPABILITY,
        # not just today's tree: run the guard's own pattern over synthetic
        # strings, so a future narrowing of the regex is caught here rather
        # than by the next verifier.
        # Calls the SAME helper the live guard calls -- deliberately NOT a local
        # copy of the pattern. Round 7's first attempt kept a copy here, so
        # narrowing the real guard left this green: the test proved its own
        # duplicate worked, which is precisely the second-declaration failure
        # this BR family is about.
        flags = count_restatements

        must_catch = ["the 52 deterministic verbs", "the 52 repo-local verbs",
                      "57 MCP tools", "43 container tools", "52 verbs",
                      "the container's 43 MCP tools", "~52 landing verbs"]
        for text in must_catch:
            with self.subTest(catch=text):
                self.assertTrue(flags(text),
                                f"guard is blind to {text!r}: a stale count in this "
                                f"phrasing would ship silently")

        # Accepting controls: a guard that flags everything is equally useless.
        must_ignore = ["Bucket-2 verbs moved to the landing plane",
                       "R17.2 tools whose declared asset paths",
                       "answered 200 for a tool that does not exist",
                       "`gate.py --list` is the authoritative roster",
                       "R9.11.3 by-construction", "the 0.2.0 release",
                       # Round 8, Defect 1: `deterministic` was a match target
                       # until now, so these three read as roster restatements.
                       # A test count and a build year are not rosters, and a
                       # guard that cries about a year gets switched off.
                       "ran 300 deterministic tests",
                       "2015 deterministic build",
                       "sympy has been deterministic since 2015"]
        for text in must_ignore:
            with self.subTest(ignore=text):
                self.assertEqual([], flags(text),
                                 f"guard false-positives on {text!r}")

    def test_list_discloses_the_universally_required_repo_flag(self):
        # BR_20260730 round 7, Defect 1: `--repo` is enforced for EVERY verb in
        # _build_args, before any per-verb check, yet appeared in no verb's
        # `required_args`. A caller reading the roster satisfied every listed
        # argument and still got VERB_ARGS_INVALID -- a roster that omits a
        # universal requirement is an incomplete declaration.
        import subprocess
        import sys
        gate = REPO_ROOT / "skills" / "bodesign" / "scripts" / "gate.py"
        env = {"PATH": "/usr/bin:/bin",
               "PYTHONPATH": ":".join(str(d) for d in (REPO_ROOT / "packages").iterdir()
                                      if d.is_dir())}
        out = subprocess.run([sys.executable, str(gate), "--list"],
                             capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(0, out.returncode, out.stderr[-2000:])
        result = json.loads(out.stdout)["result"]
        self.assertIn("always_required", result,
                      "--list no longer discloses CLI-level requirements")
        self.assertIn("--repo", result["always_required"])

        # Accepting control: the claim must match the code that enforces it, or
        # the disclosure is decoration pointing at a flag nobody checks.
        source = gate.read_text(encoding="utf-8")
        self.assertIn('"--repo <absolute project dir> is required"', source)


class ManifestDeclarationTests(unittest.TestCase):

    def test_manifest_declaration_matches_the_repo_layout(self):
        manifest = json.loads((REPO_ROOT / "mcp.json").read_text(encoding="utf-8"))
        for declared in manifest["skillPaths"]:
            self.assertTrue((REPO_ROOT / declared).is_dir(),
                            f"skillPaths declares {declared!r} which does not exist "
                            f"(R9.4.2: declaring is not shipping)")


if __name__ == "__main__":
    unittest.main()
