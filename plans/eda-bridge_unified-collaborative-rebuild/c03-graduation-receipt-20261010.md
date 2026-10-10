# C03 graduation receipt — six-leaf package on v5 (R-N, freeze §4.24) — 2026-10-10

Handler: `ses_ed97ec935ffe6uUVTzQboaBZvn` (replaces dead codex workers `ses_ed99a0539ffe6RKi68bWIjxbyy`, `ses_ed98302cbffeDJuuWshnuUfHIh`).
Subject: repo HEAD `bff5b209e9e5527f0f8c1e7b4f6551f941cf41e6` (S56) plus the uncommitted officer edit of `c04-entry-freeze-20261007.md`; v5 emitted at S54 `cf35774c8a2a8b07ed5bddb0631f11aed4ffdeee`; v5 source manifest `hashes.sha256` = `b3db0c26a0d1a3ff884c13913a9f24f34415de9617a1d92be5eded0c2e420925` (63 entries).
Procedure: R-L 1(d) / S51 (`s3-formalisation-receipt-20261009.md` "1(d) final bundle v4"), repeated on v5 bytes. No leaf regenerated. No edit under `packages/` or `services/`. No stage, commit, restart, or human-tree write.

## 1. Pre-check (v5 hashes, both sides)

```sh
# cwd: /home/pkcs12/projects/bodesign/experiments/s3-formal/c03_engine-v5
sha256sum -c hashes.sha256          # 63 lines "OK", rc=0
# cwd: /home/pkcs12/products/bodesign/outputs/btdongle_ms/c03_engine-v5
sha256sum -c hashes.sha256          # rc=0
diff -r /home/pkcs12/projects/bodesign/experiments/s3-formal/c03_engine-v5 \
        /home/pkcs12/products/bodesign/outputs/btdongle_ms/c03_engine-v5   # rc=0
```

Raw: `rc=0` / `prod rc=0` / `diff rc=0`. The two v5 trees are byte-identical before bundling.

## 2. Bundle

Location: `experiments/s3-formal/c03_engine-v5/bundle/`. Layout and names match the v4 bundle (S51). The manifest name is the same as on v4: `c03_bundle_manifest-v1.json`. The schema is bumped to `c03-bundle-manifest-v3` because there are new keys: `engine_params`, `emission_commit`, `form_result.s1_v3`, `form_result.s1_v2_control`, `form_result.review36`, and `deferred_items`.

New relative to v4: `evidence/check_c03/` (raw before/after call and SSE) and `evidence/s1_v2_control/` (the six v5 reports from frozen v2 plus `v2-tables.json`, copied unchanged from S55 `~/.cache/scratch/s3-formal/round4/`).

Steps (scratch `~/.cache/scratch/s3-formal/graduation/`):

```sh
# library binding audit, read-only, inside EE (v4 script with c03_engine-v4 -> c03_engine-v5)
docker exec -i bodesign-pkcs12-bodesign-ee-1 python3 - < bundle_library_pins.py > library_pin_binding.json
#   -> 14 symbols / 45 refs
# served export_bom x6 over UDS /mcp/ (v4 script retargeted to c03_engine-v5, out_dir bundle-bom-v5)
python3 export_all_boms.py          # "All 6 leaves successfully exported!"
# assembly + normalised per-ref BOM + served check_c03 before/after + manifest + hashes
python3 assemble_bundle_v5.py       # cwd /home/pkcs12/projects/bodesign
```

Raw output of `assemble_bundle_v5.py` (rc=0):

```text
CROSSCHECK expected/native/missing/extra/mismatch: 45/45/0/0/0
CHECK_C03 before: gate=FAIL blocking=['R3_DRAWABILITY']
CHECK_C03 after: gate=PASS blocking=[]
MANIFEST c03_bundle_manifest-v1.json entries=95 sha256=722cae82e4cc65010ec11d72f4d3cb4653b2a9bc61636daf8a609fa35ab0df9f
HASHES covering 96 files sha256=ec2b274c2bb17ebe54f9b12225b1c647d1c57eef45ff3d9c2faf629da5675bb0
bundle sha256sum -c rc=0
```

The bundle holds 97 files: 95 in the manifest, plus the manifest, plus `hashes.sha256`. `hashes.sha256` covers 96 files: everything except itself.

Per-ref BOM: `bom/bom_per_ref.csv` has the header `ref,value,footprint,symbol_source`. The method is the same normalisation as S51: normalised from the root native netlist, served `export_bom` kept raw, and `symbol_source` filled in from the EE library bindings (`official: /usr/share/kicad/symbols/<lib>.kicad_sym (sha256=…)` / `vendor: …`). The served export_bom outer result is `ok:true`, `status:ok`, `component_count:0`, `warnings:[]` on all six leaves. This is the same lossy-grouping TOOL DEFECT as on v4 (open BR). `component_count 0` is not a measured zero.

Manifest contents (as the dispatch requires): subject HEAD and emission commit; `engine_params` (the formal_invocation arguments without the spec body: `layout_engine elk-layered`, `connection_style wire`, `power_ports false`, `engine_placement_models`, `engine_spacing_overrides`, `engine_orientation_sets`, `subsystem_views`, `symbol_dirs`, `spec_component_count 45`). S1 v3: instrument `3efefede90910f3349d6bce07b8c90c9a06061108f23007c2e3f156eca0f6bf0` (asserted equal to the working-tree and HEAD `readability_render.py`), policy `210cdba1bd6f4e52` (asserted per leaf), calibration `s1-calibration-record-v3 (BASE_RECAL_V3)`. S1 v2 control column: instrument `53acfd4b8399091b35db4eff9b80929a5f8e754ae2d782ee29b6cb5f74f029af`, policy `63bee5d02a5ec147`, measurement script `ef29b528a8002f67b5997a63ad8fba9308f9127c5b7818607c35a4c972a0388d`. Review 36 per leaf (below). The deferred items. The non-claims list.

| leaf | comps | nets | S1 v3 verdict, a..f | S1 v2 control a..f | Review 36 session | images | SIGN | BLOCKING | NOTE | report sha256 |
|---|---:|---:|---|---|---|---|---|---:|---:|---|
| usbc | see manifest | 5 | indeterminate 0,0,0,0,0,0 | 0,0,0,0,0,0 | ses_ed99478cc | 5/5 | yes-with-notes | 0 | 3 | `7b40cbd342c777691810879d1a9e182d0b6b13b181dfe8f81fe77580694f0603` |
| power_rail | see manifest | 11 | indeterminate 0,0,0,0,0,0 | 0,0,0,0,7,0 | ses_ed99443eb | 12/12 | yes-with-notes | 0 | 5 | `90b6184f6e9d6477c9ddcebaf71bf44387a043eac057384e3071bd2b4c6a59cb` |
| battery | see manifest | 4 | indeterminate 0,0,0,0,0,0 | 0,0,0,0,1,0 | ses_ed99416b7 | 5/5 | yes-with-notes | 0 | 5 | `1ec24e40556cd865fc09c2d26c52e67fb603c3ccf8779c95457689d2d4013a28` |
| charge_enable | see manifest | 5 | indeterminate 0,0,0,0,0,0 | 0,0,0,0,0,0 | ses_ed9917057 | 4/4 | yes-with-notes | 0 | 8 | `3580faa5423355783787af9c1c796779d60101f6084812d761a296b975f03f26` |
| mcu_swd | see manifest | 10 | indeterminate 0,0,0,0,0,0 | 0,0,0,0,2,0 | ses_ed9914a5e | 6/6 | yes-with-notes | 0 | 7 | `1142f70dd0bff023f10a2d8971d21e4c8f2f6e58549789cb5d1d841194b7f162` |
| io | see manifest | 10 | indeterminate 0,0,0,0,0,0 | 0,0,0,0,0,0 | ses_ed9912f66 | 4/4 | yes-with-notes | 0 | 7 | `0a5a5a1221cd140fd2be8083bc88ad200b2da8385751f513b35d34aee3e55d49` |

Totals: 36/36 READ_OK, 6/6 yes-with-notes, 0 BLOCKING, 35 NOTE (an assert in the script checks the sum). v2 total [0,0,0,0,10,0]. The per-leaf component counts, ERC lib/non-lib/accepted counts and fidelity are in `README.md` and in the manifest `electrical_result`. Report sha256s were recomputed from `~/.cache/scratch/s3-formal/review36/<leaf>.md`, and their prefixes match the Review 36 receipt.

## 3. Served check_c03 (before / after)

**Transport deviation.** The dispatch names the LAN endpoint `http://192.168.100.141:8177/mcp/` as "used in S51". The S51 receipt and its scripts (`bundle-v4/assemble_bundle_v4.py`, `test_check_c03_after.py`) used the local UDS `/home/pkcs12/projects/bodesign/.run/bodesign.sock` (`http://localhost/mcp/`), not the LAN endpoint. I measured the LAN endpoint: `/healthz` returns `status ok, version 0.3.0, tools 73` and `initialize` succeeds, but the CT105 host does not see this host's files. The same `check_c03` call with the v5 bundle BOM returns:

```text
data: {"jsonrpc":"2.0","id":"check_c03_v5_lan","result":{"content":[{"type":"text","text":"{\n  \"ok\": false,\n  \"error\": \"ValueError: BOM_MISSING: /work/experiments/s3-formal/c03_engine-v5/bundle/bom/bom_per_ref.csv not found — run C03 BOM export first.\"\n}"}],"isError":false}}
```

(Raw: `~/.cache/scratch/s3-formal/graduation/check_c03-lan-response.sse`, sha256 `c715d913cdb66aba90ef269ede8046df051d27d8d3f8e74551a9ce177d0a7d83`. The v4 product BOM path and the v4 bundle-bom path give the same `BOM_MISSING`.) So the gate of record below ran over the local UDS, which is the S51 transport. The LAN endpoint gives no gate verdict on these bytes. Bundle staging to CT105 was not attempted.

Target netlist `/work/experiments/s3-formal/c03_engine-v5/native/root/btdongle_ms.net`. Raw files: `bundle/evidence/check_c03/check_c03-{before,after}-{call.json,response.sse}`.

- **Before** (`bom_csv` = `c03_engine-v1/bundle/bom/bom_per_ref.csv`, no symbol_source column): `"gate": "FAIL"`, blocking `R3_DRAWABILITY` ("no symbol-source column found in BOM header (looked for: symbol_source, symbol, sym_source, drawability, deck_status) — cannot assess drawability for any row"). bom_rows 45, passive_completeness `run`.
- **After** (`bom_csv` = `/work/experiments/s3-formal/c03_engine-v5/bundle/bom/bom_per_ref.csv`): `"gate": "PASS"`, `blocking: []`, `warnings: []`, bom_rows 45. R3_DRAWABILITY PASS, with no blocking finding. passive_completeness (PC-001) `status run`, `rails_checked 3`, `ics_without_identifiable_rail []`; U1 rails `[VBUS]` verdict `ok`; U2 rails `[+3V3, SYS]` verdict `ok`; identified_by `type` on every rail.

Raw gate lines (grep of the SSE):

```text
check_c03-after-response.sse:\"gate\": \"PASS\"
check_c03-before-response.sse:\"gate\": \"FAIL\"
check_c03-after-response.sse:\"verdict\": \"ok\"   (U1)
check_c03-after-response.sse:\"verdict\": \"ok\"   (U2)
```

## 4. Crosscheck fidelity

`bom/bom_crosscheck.json`: expected_refs 45, native_refs 45, missing 0, extra 0, mismatch 0, duplicate_ref 0. This reads **45/45/0/0/0**, as on v4. The bytes are identical to the v4 crosscheck (`59ee612d…`), and `bom_per_ref.csv` is identical to v4 (`f404ba13…`), which is expected because v5 changed only geometry, not the BOM. All six leaf nets are qualified subsets of the root (`netlist_subset_counts.json`, `14e6d722…`, same as v4).

## 5. Product mirror

```sh
cp -r /home/pkcs12/projects/bodesign/experiments/s3-formal/c03_engine-v5/bundle \
      /home/pkcs12/products/bodesign/outputs/btdongle_ms/c03_engine-v5/bundle   # destination did not exist beforehand
(cd <repo bundle>    && sha256sum -c --quiet hashes.sha256)   # repo bundle rc=0
(cd <product bundle> && sha256sum -c --quiet hashes.sha256)   # product bundle rc=0
diff -r <repo bundle> <product bundle>                        # diff rc=0
```

Note on the path: freeze §4.24 item 1 names `~/products/bodesign/outputs/btdongle_ms/c03_engine-v1/v5/`. That directory does not exist. The live v5 mirror is `outputs/btdongle_ms/c03_engine-v5/`, and the dispatch names `c03_engine-v5/bundle/`. I followed the dispatch.

## 6. Human-eye tree `~/products/bodesign/btdongle_ms/` (measured only, nothing written)

C03 files at the top level (ls, 2026-10-10): `07.u2_power_swd-v6.png`, `08.u2_user_io-v5.png`, `09.u1_power_battery-v7.png`, `10.u1_control_status-v5.png`, `11.j1_usb-v4.png`. These are the older per-subsystem PNGs (Oct 7). Correction to the dispatch: in the human tree they are PNG only. The matching `*-vN.kicad_sch` sheets are under `outputs/btdongle_ms/` (`07.u2_power_swd-v6.kicad_sch` … `11.j1_usb-v4.kicad_sch`). The top level has no six-leaf (v5) C03 file. The other prefixes in use are `00` overview/pdf, `01.c04-*`, `02.c02p-*`, `03.c01-*`, and `12.c00-prd-*`. There is also a `.history/` directory that holds superseded versions.

**Proposal (ASK — officer rules on names):** land the six-leaf v5 package under the `04` prefix, which is unused and follows the `0N.<stage>-` pattern of `01.c04`, `02.c02p` and `03.c01`:

| proposed name | source |
|---|---|
| `04.c03-usbc-v5.png` / `.svg` | `bundle/evidence/native/usbc/svg/usbc.svg` (+ raster) |
| `04.c03-power_rail-v5.png` / `.svg` | power_rail SVG |
| `04.c03-battery-v5.png` / `.svg` | battery SVG |
| `04.c03-charge_enable-v5.png` / `.svg` | charge_enable SVG |
| `04.c03-mcu_swd-v5.png` / `.svg` | mcu_swd SVG |
| `04.c03-io-v5.png` / `.svg` | io SVG |
| `04.c03-bom-v5.csv` | `bundle/bom/bom_per_ref.csv` |
| `04.c03-bundle_manifest-v5.json` | `bundle/c03_bundle_manifest-v1.json` |

Open points for the ruling: (a) whether `vN` counts the engine revision (v5) or restarts at v1 per new name; (b) which renderer the PNGs come from: the S55 cairosvg packet (`v5-png/<leaf>-full.png`, scratch) or a fresh render; (c) whether to move `07..11` into `.history/` (they are superseded by the six-leaf set) or keep them; (d) whether to add a `04.c03-review36-v5.md` summary. No file was renamed, written or deleted.

### 6.1 Landed (officer ruling, freeze §4.24 item 5)

Rulings applied: (a) vN = engine revision v5. (b) The PNGs are the S55 cairosvg full-sheet rasters `~/.cache/scratch/s3-formal/v5-png/<leaf>-full.png`, with no fresh render. (c) 07..11 stay; nothing was moved or deleted. (d) No review summary.

S55 checksum verification before the copy: each `<leaf>-full.png` was compared with its row in `six-leaf-ef-repair-20261009.md` §15.13. Result: `S55 OK` for all 6. In addition, `sha256sum -c --quiet hashes.sha256` in `v5-png/` returned rc=0.

Byte copies (`cp`). Each destination was checked to be absent before the copy. Columns: source sha256, destination sha256, file:

```text
75a70114269422b8dae47b65a184bcc12f2208d30539b8a1f30ba51659a4372e 75a70114269422b8dae47b65a184bcc12f2208d30539b8a1f30ba51659a4372e 04.c03-usbc-v5.png          <- v5-png/usbc-full.png
0098b2080e5d8926256cb0329afd3aee3375dbef6c56b43204f5572242bfd852 0098b2080e5d8926256cb0329afd3aee3375dbef6c56b43204f5572242bfd852 04.c03-power_rail-v5.png    <- v5-png/power_rail-full.png
41d9f1d5da53edef39da11666a2138a1e78956400e773f713156f1d53fe3cb65 41d9f1d5da53edef39da11666a2138a1e78956400e773f713156f1d53fe3cb65 04.c03-battery-v5.png       <- v5-png/battery-full.png
b3dec358ea21d5b7eb3ad21338f8441a20d3f0b3087224a5f58761bafcb67914 b3dec358ea21d5b7eb3ad21338f8441a20d3f0b3087224a5f58761bafcb67914 04.c03-charge_enable-v5.png <- v5-png/charge_enable-full.png
c990cc0d449f185a023c2f02608647f85215095ae7682933ff4eaffdccac33b7 c990cc0d449f185a023c2f02608647f85215095ae7682933ff4eaffdccac33b7 04.c03-mcu_swd-v5.png       <- v5-png/mcu_swd-full.png
d110b9d64e92e252e9774d75beb591ba421036c7c0bf92c5348120e3d9f27e8b d110b9d64e92e252e9774d75beb591ba421036c7c0bf92c5348120e3d9f27e8b 04.c03-io-v5.png            <- v5-png/io-full.png
f404ba13efa3554cee19474fd68314f725d27f854d83b10a4be21d9671010fe7 f404ba13efa3554cee19474fd68314f725d27f854d83b10a4be21d9671010fe7 04.c03-bom-v5.csv           <- bundle/bom/bom_per_ref.csv
722cae82e4cc65010ec11d72f4d3cb4653b2a9bc61636daf8a609fa35ab0df9f 722cae82e4cc65010ec11d72f4d3cb4653b2a9bc61636daf8a609fa35ab0df9f 04.c03-bundle_manifest-v5.json <- bundle/c03_bundle_manifest-v1.json
```

Human-tree index: `~/products/bodesign/btdongle_ms/README.md` exists. It has a top-level file table (lines 9–28). Three rows were appended after the `repo_binding-v1.json` row: one for the six PNGs, one for the BOM, and one for the manifest. This was the only text edit in the human tree. 07..11 are still present.

## 7. Deferred items (freeze §4.24 item 2, as ruled)

| item | status |
|---|---|
| page occupancy (io ≈80 %, charge_enable ≈85–90 %, usbc ≈70 % blank), A4 + `fit_page` 1.27 mm | ACCEPTED |
| power_rail four-wire 2.54 mm corridor (~170 mm), parallel not collinear | ACCEPTED |
| net naming (`PWR_LED_K`, `CHG_LED_A`), from the declared circuit | SANDBOX-ASSUMPTION |
| charge_enable SW1 SPDT common-to-GND and D2 STAT polarity (dark-while-charging if STAT is open-drain active-low) | SANDBOX-ASSUMPTION — recorded for the design owner |

## 8. Post-check (v5 hashes unchanged)

```text
post repo v5 rc=0       # experiments/s3-formal/c03_engine-v5, sha256sum -c hashes.sha256
post product v5 rc=0    # outputs/btdongle_ms/c03_engine-v5, sha256sum -c hashes.sha256
```

The source manifest still reads `b3db0c26…` (it is copied as `bundle/evidence/hashes.sha256`). `git status --porcelain packages/ services/` shows only the pre-existing peer edit ` M packages/shared/bodesign_shared/paths.py`. This handler did not touch it.

## 9. SHA256 of new files

Scratch scripts and intermediates (`~/.cache/scratch/s3-formal/graduation/`):

```text
2f7ca165c3d5a85fec591dd38c045f0cd60bdfad542e119287401bf586ab42f8  assemble_bundle_v5.py
165d11da289014a8af3f4262d31c6c11f9888e7f94c31210f830566a85b87d8a  bundle_library_pins.py
69b6cbc90f39c697792e67875b0ec524aac6bce8d27d80ebaea603acfd26da1f  export_all_boms.py
86f26e7e2bee035c30f8b38267b8da2a95b94a83005621030c5688179aa2fa11  library_pin_binding.json
c715d913cdb66aba90ef269ede8046df051d27d8d3f8e74551a9ce177d0a7d83  check_c03-lan-response.sse
```

Served BOM outputs (`experiments/s3-formal/bundle-bom-v5/<leaf>/<leaf>-bom.csv`) are byte-identical to the `bom/<leaf>-bom.csv` entries below.

Bundle `hashes.sha256` (self) `ec2b274c2bb17ebe54f9b12225b1c647d1c57eef45ff3d9c2faf629da5675bb0`; manifest `722cae82e4cc65010ec11d72f4d3cb4653b2a9bc61636daf8a609fa35ab0df9f`. The list of 96 files, relative to `bundle/`, is the raw content of `bundle/hashes.sha256`. Only the new/derived entries are excerpted here; every `evidence/native/**`, `evidence/formal_invocation.json` and `schematic/**` entry is a byte copy that `evidence/hashes.sha256` (`b3db0c26…`) already lists:

```text
6dc89440186f2addfe65c40e6106f015c2165f1b03b8c5a07b32c8ef936f1cd5  README.md
a5b596120ca26baa5ff0d5ef7f7ce8aa136e96ecbdad8ea8389de3331338fc66  bom/battery-bom.csv
d29d1662b52676e01c642d41f6d7335a05b1ddfdd761933245cc0fe366ffe3ad  bom/bom-call-battery.json
319aa4d1e95938e6a1f4127d33979ac079b6e52e8cc9677c56ed0a5043353dd2  bom/bom-call-charge_enable.json
583d8831baa9a064c5eb28c965825d507ecce0172474f351ecfdbe54b8272f6c  bom/bom-call-io.json
b311b9f30ca6e9f764d07f15fbae8176e1d1c7cd16aca1cc5fdff7cb41b06b52  bom/bom-call-mcu_swd.json
06372f160b14e22a8805f41014ce8df0883000e14a860cc9127d553401655522  bom/bom-call-power_rail.json
ea064bee7a14ac492ad0d5154951a8b628ba3ad6aa7bce759db2a602550317b3  bom/bom-call-usbc.json
82e63955436c75786cd61b11cdb098f1ac0be38abf131e8ae8458a2adecafbab  bom/bom-response-battery.sse
01807ba3518545969c3427b9854d768883b64f34a22326d33fb03a038f4d6131  bom/bom-response-charge_enable.sse
b50ac91d5f2c90e8efa4c2a13d1c840f64e28c26ecc8d321a23c8e7fd4719335  bom/bom-response-io.sse
e6fc6d622be6cf3a773f810ce73ce5677281a36e5040515c99743d40cc7a555e  bom/bom-response-mcu_swd.sse
3db2bc0c19aae32f0329e4d5fd583d98c50f63f7c536c480315e69cf56ea2e8f  bom/bom-response-power_rail.sse
bcef90dfb49611ffa230d416e0f732e43ce1655ecaf80efa1e3bbb528a04cdba  bom/bom-response-usbc.sse
59ee612d0c442de964e1201774a7ed35f6e9ab156bfa979ee75620c50f3f3934  bom/bom_crosscheck.json
f404ba13efa3554cee19474fd68314f725d27f854d83b10a4be21d9671010fe7  bom/bom_per_ref.csv
187479efd756007966c88cd3d90e0a261ab516bfd9fd43cbd69b7a73f2ede43f  bom/charge_enable-bom.csv
30e50d56d59eadac3bf16ee01fb5ab3c286949288b6fcf36078bbee0ccbd8755  bom/io-bom.csv
d74c4cf3997bde4fe93a1a7c86726b3fc09ece3139152109a02a5fe7c8356f93  bom/mcu_swd-bom.csv
24bbe53ac43f2908d61d1436cb2c83e889663fd4dcbb1cc43b652e9ee7934223  bom/power_rail-bom.csv
135803240cc5e62a85abf710c500a6c15f4e48a18af661b176fddd44c62cc63c  bom/usbc-bom.csv
722cae82e4cc65010ec11d72f4d3cb4653b2a9bc61636daf8a609fa35ab0df9f  c03_bundle_manifest-v1.json
349a5737727f299f6042346f60d8f35bd527081d8bd6dacedd3a3bf7498c7890  evidence/check_c03/check_c03-after-call.json
1c46c663c530b46971449aa9d83799957f9f0854f8d66f4dd61a59368b6c5127  evidence/check_c03/check_c03-after-response.sse
337b45d366f4d096076df4baa2d7a0b7e51dc32bba7a05e05d69d959d623a9e4  evidence/check_c03/check_c03-before-call.json
ef333d35d53f6d624a206da472f6a258b6923643ad9a17c453188947e3c5242f  evidence/check_c03/check_c03-before-response.sse
b3db0c26a0d1a3ff884c13913a9f24f34415de9617a1d92be5eded0c2e420925  evidence/hashes.sha256
ab70fa2e1014435c335178514a4249190387b7a0126caed095d95c8b6d98f6b9  evidence/s1_v2_control/battery.v2-report.json
e981a5a8cf72712a863739bae937670e916566953b6743a3f700f0595b83d03d  evidence/s1_v2_control/charge_enable.v2-report.json
da91c4a1c724a41519b9b7f000caff57f0b804938443448222ec41cd234ccee3  evidence/s1_v2_control/io.v2-report.json
5ed360d941782b1efa7172bb4d67947a5b7862f63e86b8fc6d5962a665af78e8  evidence/s1_v2_control/mcu_swd.v2-report.json
6846e80473ff8a4400eb78199abe13f540fcc1d26c97e366c158a2d71c996d00  evidence/s1_v2_control/power_rail.v2-report.json
91f68b6e67934d85e4ad832b71940db59732909433f21b4d196dc133c680d27b  evidence/s1_v2_control/usbc.v2-report.json
2eb13f994a075305c20a7db0b019ec5ab5c179c6c0d4d45d558a9dbdb9ce5d8f  evidence/s1_v2_control/v2-tables.json
86f26e7e2bee035c30f8b38267b8da2a95b94a83005621030c5688179aa2fa11  library_pin_binding.json
14e6d7221ed44315ca294fb6271588e3ba03d02bc0086102fe5dba4da304309c  netlist_subset_counts.json
```

## NOT MEASURED

- check_c03 through the LAN endpoint on these bytes: CT105 cannot see them (`BOM_MISSING`, §3). The gate of record is UDS, the S51 transport.
- S1 was not re-run. The v3 counts are the S54 `s1_report.json` files copied unchanged, and the v2 column is the S55 measurement copied unchanged.
- ERC/netlist were not re-exported. They are the S54 native exports copied unchanged.
- No new visual review. Review 36 results are quoted, not reproduced.
- Historical library-file byte identity at S54 emission: the library hashes are the current EE sources.
- No tests were run (dispatch: none). The `specs/architecture.md` C03 sync and the `tasks.md` ticks (§4.24 item 3) were not done. Architecture Sync: pending officer (§4.24 item 3).
- Human-tree landing: measurement and proposal only (§6).
- Electrical design approval, release, PCB/fab/license, AC18/AC19: not claimed.
