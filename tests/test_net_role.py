import unittest

from bodesign_design_ir import (
    NET_ROLES,
    BoardDesign,
    Net,
    map_netclass_to_role,
    nets_with_role,
    set_net_role,
)
from bodesign_shared import EvidenceRef


def _ev(sid: str = "sch1", path: str = "netclass/PWR") -> EvidenceRef:
    return EvidenceRef(source_id=sid, target_path=path)


class NetRoleSchemaTests(unittest.TestCase):
    def test_tv1_backcompat_no_role(self):
        # TV-1: a Net built the old way has role/role_evidence None, other fields intact.
        net = Net(name="N1", connected_pads=["U1-1", "R1-2"])
        self.assertIsNone(net.role)
        self.assertIsNone(net.role_evidence)
        self.assertEqual(net.connected_pads, ["U1-1", "R1-2"])

    def test_tv1_positional_and_keyword_construction(self):
        # Existing positional/keyword construction unaffected by the appended fields.
        pos = Net("N2", ["A-1"], {"z0": 50.0})
        self.assertIsNone(pos.role)
        kw = Net(name="N3", constraints={"len": 10.0})
        self.assertIsNone(kw.role)


class SetNetRoleTests(unittest.TestCase):
    def test_tv2_valid_role_with_evidence(self):
        net = Net(name="VBUS")
        set_net_role(net, "power", _ev())
        self.assertEqual(net.role, "power")
        self.assertEqual(net.role_evidence, _ev())

    def test_tv3_role_without_evidence_raises(self):
        net = Net(name="GND")
        with self.assertRaises(ValueError):
            set_net_role(net, "ground", None)
        # Invariant preserved: net stays roleless after the rejected call.
        self.assertIsNone(net.role)
        self.assertIsNone(net.role_evidence)

    def test_out_of_enum_token_leaves_none(self):
        net = Net(name="CLK")
        set_net_role(net, "clock", _ev())  # type: ignore[arg-type]
        self.assertIsNone(net.role)
        self.assertIsNone(net.role_evidence)

    def test_none_role_clears(self):
        net = Net(name="X")
        set_net_role(net, "rf", _ev())
        set_net_role(net, None, None)
        self.assertIsNone(net.role)
        self.assertIsNone(net.role_evidence)


class MapNetclassToRoleTests(unittest.TestCase):
    def test_tv4_known_class_maps(self):
        table = {"PWR": "power", "GND": "ground"}
        self.assertEqual(map_netclass_to_role("PWR", table), "power")

    def test_tv5_unmapped_class_none(self):
        self.assertIsNone(map_netclass_to_role("MYSTERY", {"PWR": "power"}))

    def test_none_class_none(self):
        self.assertIsNone(map_netclass_to_role(None, {"PWR": "power"}))

    def test_invalid_table_value_none(self):
        self.assertIsNone(map_netclass_to_role("BAD", {"BAD": "clock"}))  # type: ignore[dict-item]


class NetsWithRoleTests(unittest.TestCase):
    def _design(self) -> BoardDesign:
        nets = []
        for name, role in [("P1", "power"), ("S1", None), ("P2", "power"), ("G1", "ground")]:
            net = Net(name=name)
            if role is not None:
                set_net_role(net, role, _ev())  # type: ignore[arg-type]
            nets.append(net)
        return BoardDesign(id="b", version="1", title="t", nets=nets)

    def test_tv6_filters_and_excludes_none(self):
        design = self._design()
        result = nets_with_role(design, "power")
        self.assertEqual([n.name for n in result], ["P1", "P2"])

    def test_tv6_byte_identical_repeat(self):
        design = self._design()
        a = [n.name for n in nets_with_role(design, "power")]
        b = [n.name for n in nets_with_role(design, "power")]
        self.assertEqual(a, b)

    def test_tv7_unknown_role_raises(self):
        with self.assertRaises(ValueError):
            nets_with_role(self._design(), "clock")  # type: ignore[arg-type]

    def test_net_roles_closed_set(self):
        self.assertEqual(
            NET_ROLES,
            ("power", "ground", "high_current", "rf", "signal", "differential"),
        )


if __name__ == "__main__":
    unittest.main()
