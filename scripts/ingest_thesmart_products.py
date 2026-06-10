"""Ingest thesmart_products component data into the bodesign Component Vault.

First real vault population. Sources (all client-owned, read-only):
  A. Rockbox client-cache import  rockbox/c03-ee/01_refs/datasheets/ (manifest v2)
  B. Rockbox datasheet PDFs       rockbox/c03-ee/01_refs/datasheets/*.pdf
  C. Rockbox key-part BOM usage   rockbox/c03-ee/03_output/Architecture_and_BOM.md
  D. OpenMV reference design      refs/02.OpenMV/*.pdf + src/datasheets_text/*.txt

Idempotent: sha256 dedup (documents), import dedup (specs), usage replace.
Run:  BODESIGN_VAULT_DIR=.run/vault PYTHONPATH=packages/shared:packages/component-kb:packages/doc-core \
      python3 scripts/ingest_thesmart_products.py [--verify]
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from bodesign_component_kb.repository import VaultRepository
from bodesign_component_kb.storage import open_vault

ACTOR = "ingest-thesmart-products"
SRC = Path("/home/pkcs12/projects/thesmart_products")
ROCKBOX_DS = SRC / "rockbox/c03-ee/01_refs/datasheets"
ROCKBOX_BOM = SRC / "rockbox/c03-ee/03_output/ROCKBOX_DVT_20250502A_check.BOM.xlsx"
OPENMV = SRC / "refs/02.OpenMV"
OPENMV_TXT = OPENMV / "src/datasheets_text"
EXTRACTOR = "openmv-datasheets-text-v1"

_SSML = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_rockbox_bom(path: Path) -> list[tuple[str, str, str, list[str]]]:
    """Parse the DVT check-BOM xlsx (sheet1) -> [(mpn, vendor, description, refdes)].

    Stdlib-only (zipfile + ElementTree); skips the trailing 'Total' row and
    rows without an MPN. Columns: Item, Quantity, MPN, Value, Vendor,
    Description, Location.
    """
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.iter(f"{_SSML}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_SSML}t")))
        root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        for row in root.iter(f"{_SSML}row"):
            vals: list[str] = []
            for cell in row.findall(f"{_SSML}c"):
                v = cell.find(f"{_SSML}v")
                if v is None or v.text is None:
                    vals.append("")
                elif cell.get("t") == "s":
                    vals.append(shared[int(v.text)])
                else:
                    vals.append(v.text)
            rows.append(vals)
    parts: list[tuple[str, str, str, list[str]]] = []
    for r in rows[1:]:
        r = (r + [""] * 7)[:7]
        item, _qty, mpn, _value, vendor, desc, location = (c.strip() for c in r)
        if not mpn or item.lower() == "total":
            continue
        refdes = [x.strip() for x in location.split(",") if x.strip()]
        parts.append((mpn, vendor, desc, refdes))
    return parts

# C. Architecture_and_BOM.md key-part table (mpn, manufacturer, refdes, role).
# refdes "—" in the table => no refdes recorded (never fabricated).
ROCKBOX_PARTS: list[tuple[str, str | None, list[str], str]] = [
    ("MDBT53-P1M", "Raytac", ["U-MOD"], "Cortex-M33 host application + BLE 5.x (nRF5340 SiP)"),
    ("nRF7002", "Nordic Semiconductor", ["U801"], "WiFi 802.11ax (SISO) companion over QSPI"),
    ("nRF9151", "Nordic Semiconductor", [], "LTE Cat-M1/NB1/NB2, SIM/eSIM, over UART"),
    ("PN7160A1HN", "NXP", [], "NFC pairing / config tap (I2C)"),
    ("RT9471DGQW", "Richtek", [], "USB-C 15W charger, I2C addr 0x53, OCP/OVP/OTP"),
    ("W25Q128JVSIQ", "Winbond", ["U402"], "16 MB SPI/QSPI system flash"),
    ("TLV75733PDRVR", "Texas Instruments", ["U302"], "3.3 V rail LDO (1 A)"),
    ("TLV74018PDQNR", "Texas Instruments", ["U303"], "1.8 V rail LDO (300 mA)"),
    ("ACAR4008-S698", "Abracon", ["ANT501"], "Chip antenna 960/2170/2700 MHz"),
    ("MM8030-2630RK0", "Murata", ["CON502"], "50 ohm coax test/ext antenna connector"),
    ("SIM8060-6-1-14", "GCT", ["J702"], "nano-SIM connector"),
]

# D. OpenMV: filename MPN = last whitespace token before .pdf.
OPENMV_SPECIAL = {
    # valid doc_type enum has no reference-manual/schematic kinds:
    "Reference Manual STM32N657L0.pdf": ("other", "STM32N657L0"),
    "OpenMV-N6-Schematic-Rev4.pdf": ("reference-design", "STM32N657L0"),
}


def chunk_text(raw: str, target: int = 2000) -> list[dict]:
    """Paragraph-merge chunking with character-offset anchors."""
    chunks: list[dict] = []
    buf: list[str] = []
    buf_start = 0
    offset = 0
    for para in raw.split("\n\n"):
        para_len = len(para) + 2
        if buf and sum(len(p) + 2 for p in buf) + para_len > target:
            content = "\n\n".join(buf).strip()
            if content:
                chunks.append(
                    {"chunk_kind": "text", "content": content, "anchor": f"offset:{buf_start}"}
                )
            buf = []
            buf_start = offset
        buf.append(para)
        offset += para_len
    content = "\n\n".join(buf).strip()
    if content:
        chunks.append({"chunk_kind": "text", "content": content, "anchor": f"offset:{buf_start}"})
    return chunks


def ingest(repo: VaultRepository) -> dict:
    stats = {
        "components": 0, "documents_new": 0, "documents_dedup": 0,
        "chunks": 0, "usage": 0, "txt_missing": [], "import": None,
    }

    # -- A. client-cache import (cache_root = parent of extracted/) ------
    stats["import"] = repo.import_client_cache(ROCKBOX_DS, actor=ACTOR)

    # -- B. Rockbox datasheet PDFs ---------------------------------------
    for pdf in sorted(ROCKBOX_DS.glob("*.pdf")):
        mpn = pdf.stem
        result = repo.ingest_document(
            pdf, doc_type="datasheet", provenance="user-provided", mpns=[mpn],
            provenance_detail="thesmart_products/rockbox/c03-ee/01_refs/datasheets", actor=ACTOR,
        )
        stats["documents_dedup" if result.dedup_hit else "documents_new"] += 1

    # -- C. Rockbox full BOM (82 MPN rows) + curated key-part roles -------
    # BOM xlsx is the authority for vendor/refdes; ROCKBOX_PARTS overlays
    # curated role descriptions (catalog text is noisier than a role line).
    merged: dict[str, dict] = {}
    for mpn, vendor, desc, refdes in read_rockbox_bom(ROCKBOX_BOM):
        merged[mpn] = {
            "manufacturer": vendor or None,
            "description": desc or None,
            "refdes": set(refdes),
        }
    for mpn, manufacturer, refdes, role in ROCKBOX_PARTS:
        hit = next((k for k in merged if k == mpn or k.startswith(mpn)), None)
        if hit is not None:
            merged[hit]["description"] = role
            merged[hit]["refdes"] |= set(refdes)
            if merged[hit]["manufacturer"] is None:
                merged[hit]["manufacturer"] = manufacturer
        else:
            merged[mpn] = {
                "manufacturer": manufacturer,
                "description": role,
                "refdes": set(refdes),
            }
    for mpn, info in merged.items():
        repo.upsert_component(
            mpn, manufacturer=info["manufacturer"], description=info["description"], actor=ACTOR
        )
        stats["components"] += 1
        repo.record_usage(
            mpn, project_id="rockbox", refdes=sorted(info["refdes"]),
            workflow="reverse-bom", actor=ACTOR,
        )
        stats["usage"] += 1

    # -- D. OpenMV reference design --------------------------------------
    for pdf in sorted(OPENMV.glob("*.pdf")):
        if pdf.name in OPENMV_SPECIAL:
            doc_type, mpn = OPENMV_SPECIAL[pdf.name]
        else:
            doc_type, mpn = "datasheet", pdf.stem.split()[-1]
        repo.upsert_component(mpn, actor=ACTOR)
        stats["components"] += 1
        result = repo.ingest_document(
            pdf, doc_type=doc_type, provenance="user-provided", mpns=[mpn],
            provenance_detail="thesmart_products/refs/02.OpenMV", actor=ACTOR,
        )
        stats["documents_dedup" if result.dedup_hit else "documents_new"] += 1

        txt = OPENMV_TXT / f"{pdf.stem}.txt"
        if txt.is_file():
            if not result.dedup_hit:  # chunks only on first ingest (idempotency)
                chunks = chunk_text(txt.read_text(encoding="utf-8", errors="replace"))
                if chunks:
                    chunk_result = repo.ingest_chunks(
                        result.document_id, chunks, extractor=EXTRACTOR, actor=ACTOR
                    )
                    stats["chunks"] += chunk_result.chunks_added
        else:
            stats["txt_missing"].append(pdf.name)

        if doc_type == "datasheet":
            # components.csv maps refdes->functional blocks, not MPNs: no refdes.
            repo.record_usage(mpn, project_id="openmv", refdes=[], workflow="reference-design", actor=ACTOR)
            stats["usage"] += 1

    return stats


def verify(repo: VaultRepository) -> None:
    r = repo.resolve("TLV75733PDRVR")
    print(f"resolve(TLV75733PDRVR): {r.status} -> {r.canonical_key}")
    hits = repo.search_chunks("dropout voltage", limit=5)
    print(f"search_chunks('dropout voltage'): {len(hits)} hits")
    for h in hits[:3]:
        print(f"  doc={h.filename} anchor={h.anchor} bm25={h.bm25:.2f}")
    occ = repo.occurrences("TLV75733PDRVR")
    print(f"occurrences(TLV75733PDRVR): {occ['project_count']} projects -> "
          f"{[p['project_id'] for p in occ.get('projects', [])]}")
    queue = repo.knowledge_queue(limit=5)
    print(f"knowledge_queue top {len(queue)}:")
    for item in queue:
        print(f"  {item}")


def main() -> int:
    storage = open_vault()
    repo = VaultRepository(storage)
    try:
        if "--verify" in sys.argv:
            verify(repo)
            return 0
        stats = ingest(repo)
        print("=== ingest summary ===")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return 0
    finally:
        storage.close()


if __name__ == "__main__":
    raise SystemExit(main())
