# Spec: eda-bridge_human-ai-collaborative-system

## Purpose

This specification defines the functional, geometric, and collaborative contracts for the `bodesign` schematic and layout co-design system. It guarantees that generated electronic schematics are rendered as readable, idiom-compliant circuits rather than netlist label tables, that human engineer modifications are respected and preserved via user-pinning, and that electrical fidelity is deterministically verified without silent degradation.

## Requirements

### Requirement: Subcircuit Motif Synthesis & Placement
The schematic composition engine SHALL recognize standard analog and passive functional subgraphs and place them using deterministic geometric templates before applying global force-directed placement.

#### Scenario: Decoupling Capacitor In-situ Attachment
- **WHEN** a capacitor has one node connected to an IC power pin and its other node connected to `GND`,
- **THEN** the emitter SHALL place the capacitor directly outside the host IC pin (offset 2.54–5.08mm) aligned with the pin's normal vector, connect the power node with a short straight wire, and attach an in-situ `power:GND` symbol to the ground node without routing through the global net bus.

#### Scenario: Voltage Divider Collinear Prevention
- **WHEN** two resistors form a series voltage divider between a voltage source and ground with an intermediate sense node,
- **THEN** the emitter SHALL stack the two resistors in a vertical column with a 5.08mm gap, place an explicit `junction` dot at the midpoint tap, and connect the bottom pin to an in-situ `power:GND` glyph, ensuring zero collinear overlap with adjacent nets.

### Requirement: Elimination of Serpentine Global Ground Wires
The emitter SHALL NOT route multi-node global ground nets as continuous serpentine Manhattan wires across the entire drawing canvas.

#### Scenario: Ground Net Generation
- **WHEN** components connect to `GND`,
- **THEN** the emitter SHALL emit point-of-use KiCad `power:GND` symbols at each terminal rather than daisy-chaining nodes with drawn copper wires.

### Requirement: Single Source of Truth for Route Policy
The system SHALL maintain exactly one implementation of the cross-IC route policy decision logic.

#### Scenario: Route Policy Determination
- **WHEN** `compose_schematic` determines which nets are converted to global labels,
- **THEN** it SHALL call `capacity_plan.decide_route_policy` as the sole authority and SHALL NOT execute duplicate inline pairwise counting loops.

### Requirement: Typography-Aware Keepout
The routing engine SHALL register all component text elements as spatial keepout obstacles.

#### Scenario: Orthogonal Wire Clearance
- **WHEN** `_orthogonal_route` computes a Manhattan polyline between pins,
- **THEN** it SHALL treat the bounding boxes of Reference, Value, Pin Names, and Net Labels as non-passable obstacles, ensuring zero wire strokes penetrate text characters.

### Requirement: Bidirectional User-Pinning
The system SHALL preserve engineer manual edits made inside KiCad during iterative AI design cycles.

#### Scenario: Human Component Nudge
- **WHEN** an engineer manually moves or rotates a component in `.kicad_sch` or `.kicad_pcb`,
- **THEN** the sync engine SHALL tag the component with `user_pinned: true`, and subsequent AI layout passes SHALL treat its position as an immovable obstacle.

## Acceptance Checks

- [ ] `btdongle` 45-component benchmark achieves $> 20$ junctions under `draftsman` style.
- [ ] Pin-to-label short stubs ($\le 5.2\,\text{mm}$) constitute $< 40\%$ of total drawn wires.
- [ ] Voltage divider circuit (`U1 -> R1 -> R2 -> GND`) passes `verify_partition_fidelity` with `moved = 0`.
- [ ] Zero wires intersect component Reference or Value text strings.
- [ ] `composer.py` contains zero duplicate implementations of `decide_route_policy`.
