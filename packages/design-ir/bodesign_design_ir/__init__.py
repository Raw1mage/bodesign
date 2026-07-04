from .contracts import (
    NET_ROLES,
    BoardDesign,
    BoardLayer,
    BoardObject,
    ComponentInstance,
    GeometryPrimitive,
    Net,
    NetRole,
)
from .roles import map_netclass_to_role, nets_with_role, set_net_role

__all__ = [
    "NET_ROLES",
    "BoardDesign",
    "BoardLayer",
    "BoardObject",
    "ComponentInstance",
    "GeometryPrimitive",
    "Net",
    "NetRole",
    "map_netclass_to_role",
    "nets_with_role",
    "set_net_role",
]
