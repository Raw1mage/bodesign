"""
Standard Library of Verified Circuit Blocks.

All circuit blocks in this library carry verified engineering citations (天條 4)
and encapsulate both electrical connectivity and spatial layout constraints.
"""

from __future__ import annotations

from .schema import (
    BlockComponent,
    BlockInternalNet,
    BlockLayoutConstraint,
    BlockPort,
    CircuitBlockDefinition,
)


def get_core_circuit_blocks() -> list[CircuitBlockDefinition]:
    """Returns the certified standard circuit blocks."""
    blocks: list[CircuitBlockDefinition] = []

    # 1. USB-C Sink Subsystem
    usb_c_sink = CircuitBlockDefinition(
        block_id="usb_c_sink",
        name="USB Type-C Sink 5V/3A Termination",
        category="interface",
        description="Standard USB-C UFP (Upstream Facing Port) sink CC termination with VBUS bulk and decoupling capacitors.",
        datasheet_citation="USB Type-C Cable and Connector Specification Release 2.0 §4.5.1 (Standard Downstream Facing Port CC termination)",
        external_ports=[
            BlockPort(name="VBUS", direction="power", description="5V incoming supply rail"),
            BlockPort(name="GND", direction="ground", description="Ground reference"),
            BlockPort(name="CC1", direction="signal", description="Configuration Channel 1"),
            BlockPort(name="CC2", direction="signal", description="Configuration Channel 2"),
            BlockPort(name="D_P", direction="bidirectional", description="USB 2.0 Data Positive", required=False),
            BlockPort(name="D_N", direction="bidirectional", description="USB 2.0 Data Negative", required=False),
        ],
        components=[
            BlockComponent(
                ref_prefix="R",
                value="5.1k 1%",
                package="R_0402_1005Metric",
                part_number="RC0402FR-075K1L",
                lcsc_part="C25905",
                description="CC1 5.1k pull-down to GND for 5V sink negotiation",
                pins={"1": "CC1", "2": "GND"},
            ),
            BlockComponent(
                ref_prefix="R",
                value="5.1k 1%",
                package="R_0402_1005Metric",
                part_number="RC0402FR-075K1L",
                lcsc_part="C25905",
                description="CC2 5.1k pull-down to GND for 5V sink negotiation",
                pins={"1": "CC2", "2": "GND"},
            ),
            BlockComponent(
                ref_prefix="C",
                value="10uF 25V",
                package="C_0805_2012Metric",
                part_number="CL21A106KAYNNNE",
                lcsc_part="C15850",
                description="VBUS bulk decoupling capacitor",
                pins={"1": "VBUS", "2": "GND"},
            ),
            BlockComponent(
                ref_prefix="C",
                value="0.1uF 50V",
                package="C_0402_1005Metric",
                part_number="CC0402KRX7R9BB104",
                lcsc_part="C1525",
                description="VBUS high-frequency decoupling capacitor",
                pins={"1": "VBUS", "2": "GND"},
            ),
        ],
        layout_constraints=[
            BlockLayoutConstraint(
                rule_type="max_distance_to_pin",
                target_elements=["R", "CC1"],
                max_distance_mm=5.0,
                description="CC termination resistors must be placed within 5.0mm of receptacle CC pins.",
            ),
            BlockLayoutConstraint(
                rule_type="max_distance_to_pin",
                target_elements=["C", "VBUS"],
                max_distance_mm=3.0,
                description="VBUS input decoupling capacitor within 3.0mm of connector power contacts.",
            ),
        ],
        mandated_passives=[
            {"ref_prefix": "R", "value": "5.1k", "purpose": "cc_pulldown", "required_count": 2}
        ],
    )
    blocks.append(usb_c_sink)

    # 2. 3.3V Low-Dropout Linear Regulator (LDO)
    power_ldo_3v3 = CircuitBlockDefinition(
        block_id="power_ldo_3v3",
        name="3.3V / 500mA Low-Dropout Linear Regulator",
        category="power",
        description="High-PSRR, low-noise 3.3V voltage regulator with input and output stabilization capacitors.",
        datasheet_citation="Diodes Inc AP2112 Datasheet §7.1 Application Information (Input/Output Capacitors)",
        external_ports=[
            BlockPort(name="VIN", direction="power", description="Input DC supply (3.8V - 6V)"),
            BlockPort(name="VOUT", direction="power", description="Regulated 3.3V output rail"),
            BlockPort(name="GND", direction="ground", description="Ground reference"),
            BlockPort(name="EN", direction="signal", description="Active high enable", required=False),
        ],
        components=[
            BlockComponent(
                ref_prefix="U",
                value="AP2112K-3.3",
                package="SOT-23-5",
                part_number="AP2112K-3.3TRG1",
                lcsc_part="C395353",
                description="3.3V 600mA Low-Dropout CMOS Regulator",
                pins={"1": "VIN", "2": "GND", "3": "EN", "4": "GND", "5": "VOUT"},
            ),
            BlockComponent(
                ref_prefix="C",
                value="1uF 16V",
                package="C_0402_1005Metric",
                part_number="CC0402KRX7R7BB105",
                lcsc_part="C52923",
                description="Input bypass capacitor",
                pins={"1": "VIN", "2": "GND"},
            ),
            BlockComponent(
                ref_prefix="C",
                value="2.2uF 10V",
                package="C_0402_1005Metric",
                part_number="CL05A225MP5NNNC",
                lcsc_part="C52924",
                description="Output stabilization capacitor (mandatory for loop stability)",
                pins={"1": "VOUT", "2": "GND"},
            ),
        ],
        layout_constraints=[
            BlockLayoutConstraint(
                rule_type="max_distance_to_pin",
                target_elements=["C", "VOUT"],
                max_distance_mm=1.5,
                description="Output capacitor MUST be within 1.5mm of VOUT pin to guarantee loop stability.",
            ),
            BlockLayoutConstraint(
                rule_type="max_distance_to_pin",
                target_elements=["C", "VIN"],
                max_distance_mm=2.0,
                description="Input capacitor within 2.0mm of VIN pin.",
            ),
        ],
        mandated_passives=[
            {"ref_prefix": "C", "value": "2.2uF", "purpose": "ldo_loop_stability", "required_count": 1}
        ],
    )
    blocks.append(power_ldo_3v3)

    # 3. Step-Down (Buck) Synchronous Converter
    power_dcdc_buck = CircuitBlockDefinition(
        block_id="power_dcdc_buck",
        name="Synchronous Buck Converter (High Efficiency)",
        category="power",
        description="Synchronous step-down DCDC converter with input filter, switching inductor, feedback network, and feedforward capacitor.",
        datasheet_citation="Silergy SY8089 Datasheet §Application Information & TI SLVA289 (Feedforward Capacitor Optimization)",
        external_ports=[
            BlockPort(name="VIN", direction="power", description="Input power rail (4.5V - 18V)"),
            BlockPort(name="VOUT", direction="power", description="Regulated output rail"),
            BlockPort(name="GND", direction="ground", description="Power and analog ground"),
            BlockPort(name="EN", direction="signal", description="Enable pin"),
        ],
        internal_nets=[
            BlockInternalNet(name="SW", net_role="high_current"),
            BlockInternalNet(name="FB", net_role="signal"),
        ],
        components=[
            BlockComponent(
                ref_prefix="U",
                value="SY8089AAAC",
                package="SOT-23-5",
                part_number="SY8089AAAC",
                lcsc_part="C15024",
                description="2A Synchronous Step-Down DC/DC Regulator",
                pins={"1": "EN", "2": "GND", "3": "SW", "4": "VIN", "5": "FB"},
            ),
            BlockComponent(
                ref_prefix="L",
                value="2.2uH 3A",
                package="IND_SMD_4x4mm",
                part_number="SWPA4030S2R2MT",
                lcsc_part="C19846",
                description="Power switching inductor",
                pins={"1": "SW", "2": "VOUT"},
            ),
            BlockComponent(
                ref_prefix="C",
                value="10uF 25V",
                package="C_0805_2012Metric",
                part_number="CL21A106KAYNNNE",
                lcsc_part="C15850",
                description="Input bulk ceramic capacitor",
                pins={"1": "VIN", "2": "GND"},
            ),
            BlockComponent(
                ref_prefix="C",
                value="22uF 10V",
                package="C_0805_2012Metric",
                part_number="CL21A226MPCLRNC",
                lcsc_part="C45783",
                description="Output filter capacitor",
                pins={"1": "VOUT", "2": "GND"},
            ),
            BlockComponent(
                ref_prefix="R",
                value="100k 1%",
                package="R_0402_1005Metric",
                part_number="RC0402FR-07100KL",
                lcsc_part="C25744",
                description="Feedback voltage divider upper resistor",
                pins={"1": "VOUT", "2": "FB"},
            ),
            BlockComponent(
                ref_prefix="R",
                value="20k 1%",
                package="R_0402_1005Metric",
                part_number="RC0402FR-0720KL",
                lcsc_part="C25768",
                description="Feedback voltage divider lower resistor",
                pins={"1": "FB", "2": "GND"},
            ),
            BlockComponent(
                ref_prefix="C",
                value="22pF 50V",
                package="C_0402_1005Metric",
                part_number="CC0402JRNPO9BN220",
                lcsc_part="C1546",
                description="Feedforward capacitor C_FF across R_TOP (Mandatory for phase margin, prevents BR_20260802)",
                pins={"1": "VOUT", "2": "FB"},
            ),
        ],
        layout_constraints=[
            BlockLayoutConstraint(
                rule_type="max_distance_to_pin",
                target_elements=["L", "SW"],
                max_distance_mm=2.0,
                description="Inductor L1 must be directly adjacent to SW pin to minimize radiated EMI.",
            ),
            BlockLayoutConstraint(
                rule_type="max_distance_to_pin",
                target_elements=["C", "VIN"],
                max_distance_mm=1.5,
                description="Input capacitor loop area (VIN -> CIN -> GND) must be minimized.",
            ),
        ],
        mandated_passives=[
            {"ref_prefix": "C", "value": "22pF", "purpose": "buck_feedforward_cff", "required_count": 1}
        ],
    )
    blocks.append(power_dcdc_buck)

    # 4. 4-Channel TVS ESD Protection Array
    esd_protection_array = CircuitBlockDefinition(
        block_id="esd_protection_array",
        name="4-Channel Low-Capacitance TVS Array",
        category="protection",
        description="Ultra-low capacitance (0.5pF) ESD protection diode array for high-speed differential and control signals.",
        datasheet_citation="Texas Instruments TPD4E05U06 Datasheet §10.2 Layout Example (High-Speed USB/HDMI Protection)",
        external_ports=[
            BlockPort(name="CH1", direction="bidirectional", description="Protected channel 1 (e.g. D+)"),
            BlockPort(name="CH2", direction="bidirectional", description="Protected channel 2 (e.g. D-)"),
            BlockPort(name="CH3", direction="bidirectional", description="Protected channel 3 (e.g. CC1)"),
            BlockPort(name="CH4", direction="bidirectional", description="Protected channel 4 (e.g. CC2)"),
            BlockPort(name="GND", direction="ground", description="Chassis / digital ground reference"),
            BlockPort(name="VBUS_CLAMP", direction="power", description="VBUS rail clamp", required=False),
        ],
        components=[
            BlockComponent(
                ref_prefix="D",
                value="TPD4E05U06",
                package="USON-10_2.5x1.0mm",
                part_number="TPD4E05U06DQAR",
                lcsc_part="C92873",
                description="4-Channel Transient Voltage Suppressor (IEC 61000-4-2 Level 4)",
                pins={
                    "1": "CH1",
                    "2": "CH2",
                    "3": "GND",
                    "4": "CH3",
                    "5": "CH4",
                    "6": "VBUS_CLAMP",
                },
            ),
        ],
        layout_constraints=[
            BlockLayoutConstraint(
                rule_type="proximity_to_connector",
                target_elements=["D"],
                max_distance_mm=2.5,
                description="TVS diode array must be placed directly between connector pins and protected ICs, ≤ 2.5mm from connector.",
            ),
            BlockLayoutConstraint(
                rule_type="max_distance_to_pin",
                target_elements=["D", "GND"],
                max_distance_mm=0.5,
                description="GND pin of TVS must connect to reference ground plane with immediate via ≤ 0.5mm.",
            ),
        ],
        mandated_passives=[],
    )
    blocks.append(esd_protection_array)

    # Validate all core blocks at definition time (fail fast)
    for b in blocks:
        b.validate()

    return blocks
