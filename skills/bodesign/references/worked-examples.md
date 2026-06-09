# Worked examples — the reference board vault

Throughout the stage guides you will see citations like
`thesmart_products/openmv/N6_board/C03_EE/Netlist_Status.md` or `openmv/C04-Layout/03_output/DELIVERABLES.md`.
These point at **real, completed reference boards** — the canonical "do it like this" artifacts the
SOPs are modelled on (the OpenMV-derived boards and the Rockbox product under `thesmart_products/`).

## They are private and NOT bundled with this skill

The vault is the maintainer's **product board data** (real customer/product names, full design
packages). It is **not** part of the distributable skill. It is made resolvable **locally** by two
root symlinks, mirroring the `engines/datasheets` and `engines/emc` convention:

| Symlink (skill root) | Target | Resolves citations of the form |
|---|---|---|
| `thesmart_products` | `../../thesmart_products` | `thesmart_products/openmv/…`, `thesmart_products/rockbox/…` |
| `openmv` | `../../thesmart_products/openmv` | bare `openmv/…` |

Both are listed in `.gitignore` so they are never committed or shipped. To recreate them on a
machine that has the vault as a sibling of the skills directory:

```bash
cd <skills>/bodesign
ln -sfn ../../thesmart_products thesmart_products
ln -sfn ../../thesmart_products/openmv openmv
```

## On a distributed copy

If you received this skill **without** the vault, those symlinks are absent and the citations will
not resolve — that is expected. **Treat every worked-example citation as illustrative.** Each stage
guide's SOP is self-contained: the cited file is a concrete model to imitate when you have it, never
a dependency the workflow needs to run. Generate your own artifacts to the same shape; do not block
on a missing example.
