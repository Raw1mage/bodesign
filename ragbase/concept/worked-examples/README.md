---
slug: concept/worked-examples
title: Worked examples are illustrative, not dependencies
layer: ragbase
type: concept
confidence: partial
---
# Worked examples are illustrative, not dependencies

The stage guides cite worked examples by path (`thesmart_products/rockbox/…`, `openmv/…`, `aiguard/…`). These are the maintainer's private reference boards, resolved locally by gitignored root symlinks and **not bundled** with a distributed skill. Treat every such citation as **illustrative**: a concrete model to imitate when present, never a dependency the workflow needs. The `aiguard/` track is the reference implementation of the current flat-root convention; `rockbox/` and `openmv/` predate it and may still carry the legacy `03_output/` layout (migration debt to pay down on touch, not a sanctioned alternative).

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/worked/examples/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.worked.examples.md]] @ worked-examples.md: private reference boards, illustrative-not-dependency — source_weight 3

