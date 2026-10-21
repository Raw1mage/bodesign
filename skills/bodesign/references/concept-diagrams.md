# Concept Diagram Router

Route by diagram content when authoring concept or structure diagrams.

| Diagram Depiction | Emitter Verb | Notes |
|---|---|---|
| Board-level partition / fan-out | `c03_emit_partition_diagram` | Layered SVG for board partition. |
| SoC/MCU functional block diagram | `c03_emit_host_block_diagram` | Layered SVG for central host and peripherals. |
| Mechanical look & feel | `c01_emit_id_visual_package` | Layered SVG for ID skeleton. |
| Physical placement | `emit_layout` | Constraint-first placement. |
