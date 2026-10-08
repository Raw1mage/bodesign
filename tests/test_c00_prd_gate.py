"""Synthetic AC26 controls; the optional live specimen asserts shape only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from bodesign_eda_bridge import C00PrdInputError, c00_prd_gate

SCRATCH = Path.home() / ".cache/scratch/c00-gate"
LIVE = max((Path.home() / "products/bodesign/outputs/btdongle_ms").glob("c00_prd_manifest-v*.json"), key=lambda p: int(p.stem.rsplit("-v", 1)[1]), default=Path.home() / "products/bodesign/outputs/btdongle_ms/c00_prd_manifest-v1.json")


class PrdGate(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.d = Path(tempfile.mkdtemp(dir=SCRATCH))
        self.addCleanup(shutil.rmtree, self.d)
        self.docx("source.docx", "Source")
        self.put("source.md", b"Source body")
        self.put("prd.md", b"FR-01 NFR-01 ER-01 D-1 D-3 PO-1")
        self.docx("prd.docx", "FR-01 NFR-01 ER-01")
        self.put("prd.pdf", self.pdf(2))
        self.put("decisions.md", "### D-1 — First\nDecision\n### D-3 — Prior\nRepealed by PO-1\n### PO-1 — Override\n".encode())
        self.js("bridge.json", {"functional_requirements": [{"id": "FR-01"}],
                                "non_functional_requirements": [{"id": "NFR-01"}],
                                "enclosure_requirements": [{"id": "ER-01"}],
                                "unrelated": {"id": "D-99"}})
        self.put("bom.csv", b"ref,mpn\nU1,CHIP-A\n")
        self.js("board.json", {"outline": {"units": "mm", "polygon": [[2, 3], [30, 3], [30, 96], [2, 96]]}})
        self.m = {"source_docx_path": "source.docx", "source_body_md_path": "source.md",
                  "decision_log_path": "decisions.md", "requirements_bridge_path": "bridge.json",
                  "output_docx_path": "prd.docx", "output_pdf_path": "prd.pdf", "markdown_path": "prd.md",
                  "requirement_ids": ["FR-01", "NFR-01", "ER-01"], "decision_ids": ["D-1", "D-3", "PO-1"],
                  "pipeline": {"tool": "bodesign_emit_doc", "repo-function": "emit_document", "version": "synthetic-1"},
                  "page_count": 2, "expects_in_bom": ["CHIP-A"], "expects_absent_from_bom": ["FORBIDDEN"],
                  "expects_board_outline_mm": [28, 93]}
        self.rehash()
        self.save()

    def put(self, name, data):
        (self.d / name).write_bytes(data)

    def js(self, name, value):
        (self.d / name).write_text(json.dumps(value), encoding="utf-8")

    def docx(self, name, text):
        with zipfile.ZipFile(self.d / name, "w") as z:
            z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       '<w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>')

    @staticmethod
    def pdf(n):
        # A complete uncompressed PDF with xref, page tree and empty page streams.
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
                   ("<< /Type /Pages /Count %d /Kids [%s] >>" %
                    (n, " ".join(f"{3+i} 0 R" for i in range(n)))).encode()]
        objects.extend(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> >>" for _ in range(n))
        data, offsets = b"%PDF-1.4\n", [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(data))
            data += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
        start = len(data)
        data += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
        data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
        return data + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()

    def rehash(self):
        for key, path in list(self.m.items()):
            if key.endswith("_path") and key != "markdown_path":
                self.m[key.removesuffix("_path") + "_sha256"] = hashlib.sha256((self.d / path).read_bytes()).hexdigest()

    def save(self):
        self.js("manifest.json", self.m)

    def run_gate(self, stage=True, **kw):
        if stage:
            kw.setdefault("bom_csv_path", str(self.d / "bom.csv"))
            kw.setdefault("board_manifest_path", str(self.d / "board.json"))
        return c00_prd_gate(str(self.d / "manifest.json"), str(self.d / "bridge.json"), str(self.d / "decisions.md"), **kw)

    def failed(self, gate, **kw):
        r = self.run_gate(**kw)
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["gates"][gate]["status"], "fail", r)
        self.assertTrue(r["gates"][gate]["offenders"], r)
        return r

    def test_positive_all_gates(self):
        r = self.run_gate()
        self.assertTrue(r["ok"], r)
        self.assertEqual({g["status"] for g in r["gates"].values()}, {"pass"})
        self.assertIn("P-05 rendered overflow", r["unmeasured"])
        self.assertEqual(r["gates"]["P-05"]["detail"]["page_count"], 2)

    def test_p01_source_hash_tamper(self):
        for name in ("source.docx", "source.md", "decisions.md", "bridge.json"):
            with self.subTest(name=name):
                old = (self.d / name).read_bytes()
                self.put(name, old + b"\n")
                self.failed("P-01")
                self.put(name, old)

    def test_p01_output_hash_tamper(self):
        self.m["output_docx_sha256"] = "0" * 64
        self.save()
        self.failed("P-01")

    def test_p01_missing_source_path_or_file(self):
        del self.m["source_docx_path"]
        self.save()
        r = self.failed("P-01")
        self.assertEqual(r["gates"]["P-01"]["offenders"][0]["field"], "source_docx_path")
        self.m["source_docx_path"] = "missing.docx"
        self.save()
        self.failed("P-01")

    def test_p01_missing_output(self):
        (self.d / "prd.pdf").unlink()
        self.failed("P-01")

    def test_p01_unapproved_pipeline(self):
        self.m["pipeline"]["tool"] = "hand-assembled"
        self.save()
        self.failed("P-01")

    def test_p01_argument_path_binding(self):
        self.put("copy.json", (self.d / "bridge.json").read_bytes())
        r = c00_prd_gate(str(self.d / "manifest.json"), str(self.d / "copy.json"), str(self.d / "decisions.md"))
        self.assertFalse(r["ok"])
        self.assertEqual(r["gates"]["P-01"]["status"], "fail")

    def test_p02_missing_markdown_requirement(self):
        self.put("prd.md", b"NFR-01 ER-01 D-1 D-3 PO-1")
        self.failed("P-02")

    def test_p02_missing_docx_requirement(self):
        self.docx("prd.docx", "FR-01 ER-01")
        self.rehash()
        self.save()
        self.failed("P-02")

    def test_p02_orphans_both_directions(self):
        self.m["requirement_ids"] = ["FR-99", "NFR-01", "ER-01"]
        self.put("prd.md", b"FR-99 NFR-01 ER-01 D-1 D-3 PO-1")
        self.docx("prd.docx", "FR-99 NFR-01 ER-01")
        self.rehash()
        self.save()
        r = self.failed("P-02")
        self.assertEqual({o["reason"] for o in r["gates"]["P-02"]["offenders"]}, {"missing", "orphan"})

    def test_p02_token_boundary_and_split_docx_runs(self):
        self.put("prd.md", b"FR-010 NFR-01 ER-01 D-1 D-3 PO-1")
        self.failed("P-02")
        self.put("prd.md", b"FR-01 NFR-01 ER-01 D-1 D-3 PO-1")
        self.docx("prd.docx", 'FR-</w:t></w:r><w:r><w:t>01 NFR-01 ER-01')
        self.rehash()
        self.save()
        self.assertTrue(self.run_gate()["ok"])

    def test_p02_bridge_schema_fail_fast(self):
        self.js("bridge.json", {"functional_requirements": []})
        with self.assertRaisesRegex(C00PrdInputError, "schema mismatch"):
            self.run_gate()

    def test_p02_enclosure_family_orphan(self):
        self.js("bridge.json", {"functional_requirements": [{"id": "FR-01"}],
                                "non_functional_requirements": [{"id": "NFR-01"}],
                                "enclosure_requirements": [{"id": "ME-01"}]})
        self.m["requirement_ids"] = ["FR-01", "NFR-01", "ME-01"]
        self.put("prd.md", b"FR-01 NFR-01 ME-01 ME-99 D-1 D-3 PO-1")
        self.docx("prd.docx", "FR-01 NFR-01 ME-01")
        self.rehash()
        self.save()
        r = self.failed("P-02")
        self.assertIn({"id": "ME-99", "where": "markdown", "reason": "orphan"}, r["gates"]["P-02"]["offenders"])

    def test_p03_uncited_repealed_decision(self):
        self.put("prd.md", b"FR-01 NFR-01 ER-01 D-1 PO-1")
        r = self.failed("P-03")
        self.assertIn({"id": "D-3", "where": "markdown", "reason": "missing"}, r["gates"]["P-03"]["offenders"])

    def test_p03_orphan_manifest_decision(self):
        self.m["decision_ids"].append("PO-99")
        self.save()
        self.failed("P-03")

    def test_p04_bom_missing_and_forbidden(self):
        self.put("bom.csv", b"ref,mpn\nU1,CHIP-A1\nU2,FORBIDDEN\n")
        r = self.failed("P-04")
        self.assertEqual(len(r["gates"]["P-04"]["offenders"]), 2)

    def test_p04_outline_mismatch_ordered(self):
        self.m["expects_board_outline_mm"] = [93, 28]
        self.save()
        self.failed("P-04")

    def test_p04_outline_tolerance(self):
        self.m["expects_board_outline_mm"] = [28.01, 93]
        self.save()
        self.assertTrue(self.run_gate()["ok"])
        self.m["expects_board_outline_mm"] = [28.011, 93]
        self.save()
        self.failed("P-04")

    def test_p04_absent_and_partial_unmeasured(self):
        for kw in ({}, {"bom_csv_path": str(self.d / "bom.csv")}, {"board_manifest_path": str(self.d / "board.json")}):
            with self.subTest(kw=kw):
                r = self.run_gate(stage=False, **kw)
                self.assertTrue(r["ok"])
                self.assertEqual(r["gates"]["P-04"]["status"], "unmeasured")
                self.assertTrue(any(s.startswith("P-04") for s in r["unmeasured"]))
        self.put("bom.csv", b"ref,mpn\nU1,WRONG\n")
        self.failed("P-04", stage=False, bom_csv_path=str(self.d / "bom.csv"))

    def test_p04_malformed_board_fail_fast(self):
        self.js("board.json", {"outline": {"units": "inch", "polygon": []}})
        with self.assertRaisesRegex(C00PrdInputError, "schema mismatch"):
            self.run_gate()

    def test_p05_page_count_mismatch(self):
        self.m["page_count"] = 3
        self.save()
        self.failed("P-05")

    def test_p05_empty_header_and_trailer(self):
        for pdf in (b"", b"not pdf\n%%EOF", b"%PDF-1.4\nno trailer"):
            with self.subTest(pdf=pdf):
                self.put("prd.pdf", pdf)
                self.rehash()
                self.save()
                self.failed("P-05")

    def test_p05_stream_page_tokens_not_counted(self):
        self.put("prd.pdf", self.pdf(2).replace(b"trailer\n", b"20 0 obj\n<< /Length 12 >>\nstream\n/Type /Page\nendstream\nendobj\ntrailer\n"))
        self.rehash()
        self.save()
        self.assertEqual(self.run_gate()["gates"]["P-05"]["detail"]["page_count"], 2)

    def test_p05_object_stream_unmeasured(self):
        self.put("prd.pdf", self.pdf(2).replace(b"trailer\n", b"20 0 obj\n<< /Type /ObjStm >>\nendobj\ntrailer\n"))
        self.rehash()
        self.save()
        r = self.run_gate()
        self.assertEqual(r["gates"]["P-05"]["status"], "unmeasured")
        self.assertIsNone(r["gates"]["P-05"]["detail"]["page_count"])

    def test_malformed_manifest_fail_fast(self):
        for value in ([], {"page_count": 0}, {**self.m, "requirement_ids": "FR-01"},
                      {**self.m, "pipeline": {"tool": "docxmcp"}}):
            with self.subTest(value=value):
                self.js("manifest.json", value)
                with self.assertRaisesRegex(C00PrdInputError, "C00_PRD_INPUT"):
                    self.run_gate()
        self.put("manifest.json", b"invalid JSON")
        with self.assertRaises(C00PrdInputError):
            self.run_gate()

    def test_malformed_docx_fail_fast(self):
        self.put("prd.docx", b"not a zip")
        self.rehash()
        self.save()
        with self.assertRaisesRegex(C00PrdInputError, "malformed DOCX"):
            self.run_gate()


class ServerRegistration(unittest.TestCase):
    def test_registered_handler_and_schema(self):
        path = Path(__file__).resolve().parent.parent / "services/mcp/server.py"
        spec = importlib.util.spec_from_file_location("bodesign_server_prd_test", path)
        srv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(srv)
        tool = {t["name"]: t for t in srv.TOOLS}["bodesign_c00_prd_gate"]
        self.assertEqual(set(tool["schema"]["required"]), {"manifest_path", "requirements_bridge_path", "decision_log_path"})
        result = tool["handler"]({})
        self.assertFalse(result["ok"])
        self.assertIn("C00_PRD_INPUT", result["error"])


@unittest.skipUnless(LIVE.is_file(), "Track A PRD manifest not on disk")
class PrdSpecimen(unittest.TestCase):
    def test_live_report_shape_only(self):
        m = json.loads(LIVE.read_text(encoding="utf-8"))
        r = c00_prd_gate(str(LIVE), str(LIVE.parent / m["requirements_bridge_path"]),
                         str(LIVE.parent / m["decision_log_path"]))
        self.assertEqual(set(r), {"ok", "gates", "inputs", "measured", "unmeasured"})
        self.assertIsInstance(r["ok"], bool)
        self.assertEqual(set(r["gates"]), {"P-01", "P-02", "P-03", "P-04", "P-05"})
        for gate in r["gates"].values():
            self.assertIn(gate["status"], {"pass", "fail", "unmeasured"})
            self.assertIsInstance(gate["offenders"], list)
            self.assertIn("detail", gate)
