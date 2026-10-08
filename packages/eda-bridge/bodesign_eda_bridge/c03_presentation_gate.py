"""DD-16 declaration accounting, not render-space or comprehension approval.

Pure Python. Native embedded libraries supply units/hidden/stacked inventory;
netlist nodes supply electrical identity. Missing library facts fail fast.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter

from .c04_gate import C04GateInputError, _kid, _kids, parse_sexpr

SCHEMA_VERSION = "presentation_plan/1.0.0"
GATE_IDS = tuple(f"PP-0{i}" for i in range(1, 6))


class C03PresentationInputError(ValueError):
    """Unavailable/unparseable upstream facts; no invented pin inventory."""


def _error(key):
    raise C03PresentationInputError("C03_PP_INPUT: " + key)


def _read(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return stream.read()
    except (OSError, TypeError) as exc:
        _error(f"{path!r}: {exc}")


def _json(path):
    try:
        value = json.loads(_read(path))
    except ValueError as exc:
        _error(f"{path}: {exc}")
    if not isinstance(value, dict):
        _error(f"{path}: expected JSON object")
    return value


def _sha(path):
    try:
        with open(path, "rb") as stream:
            return hashlib.sha256(stream.read()).hexdigest()
    except OSError as exc:
        _error(f"{path}: {exc}")


def _tree(path, kind):
    try:
        parsed = parse_sexpr(_read(path))
    except C04GateInputError as exc:
        _error(str(exc))
    if len(parsed) != 1 or not parsed[0] or parsed[0][0] != kind:
        _error(f"{path}: expected {kind}")
    return parsed[0]


def _value(node, key, context):
    child = _kid(node, key)
    if child is None or len(child) < 2 or not isinstance(child[1], str) or not child[1]:
        _error(f"{context}.{key}")
    return child[1]


def _schema_errors(value, schema, root, path="$", errors=None):
    """Validate the closed JSON-Schema vocabulary used by the v1 contract.

    Unsupported keywords are refused, never silently ignored. This is not a
    general JSON-Schema engine; no external dependency is required by core.
    """
    errors = [] if errors is None else errors
    allowed = {"$schema", "$defs", "$ref", "title", "type", "required", "properties",
               "additionalProperties", "items", "minItems", "maxItems", "uniqueItems",
               "minLength", "minimum", "pattern", "enum", "const"}
    unknown = set(schema) - allowed
    if unknown:
        _error(f"schema unsupported keywords at {path}: {sorted(unknown)}")
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
            _error(f"unsupported schema ref {ref!r}")
        target = root.get("$defs", {}).get(ref[8:])
        if not isinstance(target, dict):
            _error(f"unresolved schema ref {ref}")
        return _schema_errors(value, target, root, path, errors)
    types = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "integer": type(value) is int,
             "boolean": type(value) is bool, "null": value is None}
    wanted = schema.get("type")
    if wanted is not None:
        wanted = wanted if isinstance(wanted, list) else [wanted]
        if any(t not in types for t in wanted):
            _error(f"unsupported schema type at {path}")
        if not any(types[t] for t in wanted):
            errors.append({"path": path, "reason": "type", "expected": wanted})
            return errors
    for key in ("enum", "const"):
        if key in schema and (value not in schema[key] if key == "enum" else value != schema[key]):
            errors.append({"path": path, "reason": key})
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append({"path": path + "." + key, "reason": "required"})
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(props)):
                errors.append({"path": path + "." + key, "reason": "unknown field"})
        for key in sorted(set(value) & set(props)):
            _schema_errors(value[key], props[key], root, path + "." + key, errors)
    if isinstance(value, list):
        for key, bad in (("minItems", len(value) < schema.get("minItems", 0)),
                         ("maxItems", "maxItems" in schema and len(value) > schema["maxItems"])):
            if bad:
                errors.append({"path": path, "reason": key})
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append({"path": path, "reason": "uniqueItems"})
        if "items" in schema:
            for index, item in enumerate(value):
                _schema_errors(item, schema["items"], root, f"{path}[{index}]", errors)
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            errors.append({"path": path, "reason": "minLength"})
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append({"path": path, "reason": "pattern"})
    if type(value) is int and "minimum" in schema and value < schema["minimum"]:
        errors.append({"path": path, "reason": "minimum"})
    return errors


def _properties(node):
    result = {}
    for child in _kids(node, "property"):
        # Native property vs exported netlist property.
        if len(child) >= 3 and isinstance(child[1], str):
            result[child[1]] = child[2]
        else:
            result[_value(child, "name", "property")] = _value(child, "value", "property")
    return result


def netlist_inventory(path, repeated_refs=()):
    """Return physical refs and normalized pin nets; real net wins over NC view."""
    root = _tree(path, "export")
    components = _kid(root, "components")
    nets = _kid(root, "nets")
    design = _kid(root, "design")
    if components is None or nets is None or design is None:
        _error(f"{path}: components/nets/design missing")
    refs = {}
    for comp in _kids(components, "comp"):
        ref = _value(comp, "ref", "component")
        if ref.startswith("#"):
            continue
        source = _kid(comp, "libsource")
        if source is None:
            _error(f"{ref}.libsource")
        lib_id = _value(source, "lib", ref) + ":" + _value(source, "part", ref)
        if ref in refs:
            if ref not in repeated_refs or refs[ref]["lib_id"] != lib_id:
                _error(f"{path}: unapproved/conflicting duplicate physical ref {ref}")
            refs[ref]["view_nodes"].append(comp)
        else:
            refs[ref] = {"node": comp, "lib_id": lib_id, "view_nodes": [comp]}
    if not refs:
        _error(f"{path}: empty physical population")
    library = _kid(root, "libparts")
    if library is None:
        _error(f"{path}: libparts inventory absent")
    libraries = {}
    for part in _kids(library, "libpart"):
        lib_id = _value(part, "lib", "libpart") + ":" + _value(part, "part", "libpart")
        inventory = _kid(part, "pins")
        if inventory is None:
            _error(f"{path}: library {lib_id}.pins absent")
        libraries[lib_id] = {_value(p, "num", lib_id) for p in _kids(inventory, "pin")}
    expected = set()
    for ref, record in refs.items():
        if not libraries.get(record["lib_id"]):
            _error(f"{path}: library {record['lib_id']} unresolved for {ref}")
        expected.update((ref, p) for p in libraries[record["lib_id"]])
    candidates = {}
    for net in _kids(nets, "net"):
        name = _value(net, "name", "net")
        for node in _kids(net, "node"):
            ref = _value(node, "ref", "node")
            if ref.startswith("#"):
                continue
            if ref not in refs:
                _error(f"netlist orphan ref {ref}")
            pin = _value(node, "pin", ref)
            candidates.setdefault((ref, pin), set()).add(name)
    pins, conflicts = {}, []
    for key, names in sorted(candidates.items()):
        real = sorted(n for n in names if not n.startswith("unconnected-"))
        if len(real) > 1:
            conflicts.append({"ref": key[0], "pin": key[1], "nets": real})
        elif real:
            pins[key] = real[0]
        elif len(names) == 1:
            pins[key] = next(iter(names))
        else:
            # Several repeated views may emit differently named NC-only blocks.
            pins[key] = sorted(names)[0]
    sheets = []
    for sheet in _kids(design, "sheet"):
        name = _value(sheet, "name", "sheet")
        if name != "/":
            title = _kid(sheet, "title_block")
            if title is None:
                _error(f"{name}.title_block")
            sheets.append({"id": name.strip("/"), "source": _value(title, "source", name)})
    return {"refs": refs, "pins": pins, "expected": expected,
            "conflicts": conflicts, "sheets": sheets}


def native_inventory(path, ref, lib_id):
    """Resolve exact embedded symbol. Shared unit 0 pins are assigned to native unit.

    Unsupported inherited/multi-unit pin sharing is refused rather than guessed.
    """
    root = _tree(path, "kicad_sch")
    lib = _kid(root, "lib_symbols")
    if lib is None:
        _error(f"{path}: lib_symbols missing (inventory unmeasured)")
    symbols = [s for s in _kids(lib, "symbol") if len(s) > 1 and s[1] == lib_id]
    inst = [s for s in _kids(root, "symbol") if _properties(s).get("Reference") == ref]
    if len(symbols) != 1 or not inst:
        _error(f"{path}: {ref} library {lib_id} unresolved (inventory unmeasured)")
    if _kid(symbols[0], "extends") is not None:
        _error(f"{path}: inherited library {lib_id} unsupported (inventory unmeasured)")
    units, uuids = [], []
    for node in inst:
        if _value(node, "lib_id", ref) != lib_id:
            _error(f"{path}: {ref}.lib_id mismatch")
        unit_text = _value(node, "unit", ref)
        if not unit_text.isdigit() or int(unit_text) < 1:
            _error(f"{path}: {ref}.unit invalid")
        units.append(int(unit_text))
        uuids.append(_value(node, "uuid", ref))
    if len(set(units)) != len(units):
        _error(f"{path}: duplicate {ref} unit")
    pins = {}
    positions = {}
    for symbol in _kids(symbols[0], "symbol"):
        match = re.search(r"_(\d+)_(\d+)$", symbol[1])
        if match is None:
            _error(f"{path}: unit suffix missing in {symbol[1]}")
        unit = int(match[1])
        if unit == 0:
            if not _kids(symbol, "pin"):
                continue
            if len(units) != 1:
                _error(f"{path}: shared-unit pins require explicit mapping for {ref}")
            unit = units[0]
        if unit not in units:
            continue
        for pin in _kids(symbol, "pin"):
            number = _value(pin, "number", ref)
            at = _kid(pin, "at")
            if at is None or len(at) != 4:
                _error(f"{path}: {ref}.{number}.at")
            hidden = "hide" in pin or _kid(pin, "hide") == ["hide", "yes"]
            record = {"unit": unit, "hidden": hidden, "stacked_with": []}
            if number in pins and pins[number] != record:
                _error(f"{path}: alternate-unit pin conflict {ref}.{number}")
            pins[number] = record
            positions.setdefault((unit, tuple(at[1:3])), set()).add(number)
    if not pins:
        _error(f"{path}: {ref} pin inventory empty (inventory unmeasured)")
    for group in positions.values():
        for pin in group:
            pins[pin]["stacked_with"] = sorted(group - {pin})
    return {"units": sorted(units), "pins": pins, "native_uuid": "+".join(uuids)}


def _gate(offenders):
    return {"status": "fail" if offenders else "pass", "offenders": offenders}


def c03_presentation_gate(plan_path, schema_path, netlist_path, human_dir):
    """Check PP-01..05, read-only; approval values are never generated or changed."""
    plan = _json(plan_path)
    wrapper = _json(schema_path)
    schema = wrapper.get("presentation_plan", wrapper)
    if not isinstance(schema, dict):
        _error("presentation_plan schema missing")
    errors = _schema_errors(plan, schema, schema)
    if schema.get("properties", {}).get("schema_version", {}).get("const") != SCHEMA_VERSION:
        errors.append({"path": "schema.schema_version", "reason": "unsupported contract"})
    gates = {"PP-01": _gate(errors)}
    if errors:
        for key in GATE_IDS[1:]:
            gates[key] = {"status": "unmeasured", "reason": "PP-01 failed; malformed plan not traversed"}
        return {"ok": False, "schema": "c03_pp_gate/1", "gates": gates,
                "unmeasured": list(GATE_IDS[1:]), "not_checked": _not_checked()}
    base = os.path.dirname(os.path.abspath(plan_path))
    repeated = [i["ref"] for i in plan["instance_coverage"] if len(i["views"]) > 1]
    source = netlist_inventory(netlist_path, repeated)
    pages = {p["id"]: p for p in plan["pages"]}
    instances = {i["ref"]: i for i in plan["instance_coverage"]}
    bad2 = list(source["conflicts"])
    declared = [(i["ref"], p["pin"]) for i in plan["instance_coverage"] for p in i["pins"]]
    counts = Counter(declared)
    expected = source["expected"]
    if expected != set(source["pins"]):
        bad2.append({"reason": "library/net-node population differs", "missing_nodes": sorted(expected - set(source["pins"])),
                     "orphan_nodes": sorted(set(source["pins"]) - expected)})
    for key in sorted(expected | set(counts)):
        if counts[key] != 1 or key not in expected:
            bad2.append({"ref": key[0], "pin": key[1], "count": counts[key], "expected": key in expected})
    if len(instances) != len(plan["instance_coverage"]) or set(instances) != set(source["refs"]):
        bad2.append({"reason": "physical ref set/duplicates", "missing": sorted(set(source["refs"]) - set(instances)),
                     "extra": sorted(set(instances) - set(source["refs"]))})
    physical_ids = [i["physical_id"] for i in plan["instance_coverage"]]
    if len(set(physical_ids)) != len(physical_ids):
        bad2.append({"reason": "duplicate physical identity"})
    for ref, instance in instances.items():
        pinmap = {p["pin"]: p for p in instance["pins"]}
        views = instance["views"]
        if instance["home_page"] not in {v["page"] for v in views}:
            bad2.append({"ref": ref, "reason": "home view absent"})
        if len({v["page"] for v in views}) != len(views):
            bad2.append({"ref": ref, "reason": "duplicate view"})
        canonical_units = set()
        for view in views:
            page = pages.get(view["page"])
            if page is None or ref not in source["refs"]:
                bad2.append({"ref": ref, "reason": "orphan view"})
                continue
            native_path = os.path.join(base, page["native"]["path"])
            native = native_inventory(native_path, ref, source["refs"][ref]["lib_id"])
            canonical_units.update(native["units"])
            occurrence = Counter(p["pin"] for p in view["pins"])
            if set(occurrence) != set(native["pins"]) or any(n != 1 for n in occurrence.values()):
                bad2.append({"ref": ref, "page": view["page"], "reason": "view pin coverage"})
            if view["native_uuid"] != native["native_uuid"] or view["physical_id"] != instance["physical_id"]:
                bad2.append({"ref": ref, "page": view["page"], "reason": "view identity"})
            for pin, facts in native["pins"].items():
                declaration = pinmap.get(pin)
                if declaration is None or any(declaration[k] != facts[k] for k in facts):
                    bad2.append({"ref": ref, "pin": pin, "reason": "native inventory mismatch"})
        if set(instance["units"]) != canonical_units:
            bad2.append({"ref": ref, "reason": "unit coverage"})
        for pin, declaration in pinmap.items():
            key = (ref, pin)
            net = source["pins"].get(key)
            owner_views = [p for v in views if v["page"] == declaration["page"] for p in v["pins"] if p["pin"] == pin]
            if (net != declaration["net"] or declaration["page"] not in pages
                    or len(owner_views) != 1 or owner_views[0]["state"] != declaration["state"]):
                bad2.append({"ref": ref, "pin": pin, "reason": "net/page/state ownership mismatch"})
            nc = net is not None and net.startswith("unconnected-")
            for occurrence in [p for v in views for p in v["pins"] if p["pin"] == pin]:
                if (occurrence["state"] == "NC") != nc:
                    bad2.append({"ref": ref, "pin": pin, "reason": "NC vs real-net mismatch"})
                if occurrence["state"] == "hidden-stacked" and not (declaration["hidden"] or declaration["stacked_with"]):
                    bad2.append({"ref": ref, "pin": pin, "reason": "hidden/stacked without native evidence"})
    gates["PP-02"] = _gate(bad2)
    bad3 = []
    relationships = {r["id"]: r for r in plan["local_support"]}
    exceptions = {e["id"]: e for e in plan["exceptions"]}
    if len(relationships) != len(plan["local_support"]):
        bad3.append({"reason": "duplicate relationship id"})
    for rel in relationships.values():
        anchor = instances.get(rel["anchor_ref"])
        if (anchor is None or rel["page"] not in pages or not rel["anchor_pins"]
                or not set(rel["anchor_pins"]) <= {p["pin"] for p in anchor["pins"]}
                or any(s not in instances or rel["page"] not in {v["page"] for v in instances[s]["views"]}
                       for s in rel["support_refs"])):
            bad3.append({"id": rel["id"], "reason": "orphan support relationship"})
    for ref, instance in instances.items():
        for view in instance["views"]:
            for pin in view["pins"]:
                if pin["state"] != "off-page-label":
                    continue
                target = f"{view['page']}.{ref}.{pin['pin']}"
                rel = relationships.get(pin["relationship_id"])
                exc = exceptions.get(pin["exception_id"])
                approved = (exc is not None and exc["target"] == target and exc["approval"] is not None
                            and exc["approval"]["decision"] == "approved")
                destination = pin["destination"]
                resolved = []
                for dest_ref, dest_instance in instances.items():
                    for dest_view in dest_instance["views"]:
                        for dest_pin in dest_view["pins"]:
                            if destination == f"{dest_view['page']}.{dest_ref}.{dest_pin['pin']}":
                                resolved.append((dest_ref, dest_view, dest_pin))
                relationship_ok = False
                if rel is not None and len(resolved) == 1:
                    dest_ref, dest_view, dest_pin = resolved[0]
                    relationship_ok = (rel["anchor_ref"] == dest_ref and dest_pin["pin"] in rel["anchor_pins"]
                                       and rel["page"] == dest_view["page"] and dest_view["page"] != view["page"]
                                       and dest_pin["state"] in ("placed", "hidden-stacked")
                                       and source["pins"].get((ref, pin["pin"])) == source["pins"].get((dest_ref, dest_pin["pin"])))
                if not relationship_ok and not approved:
                    bad3.append({"target": target, "reason": "off-page label lacks named local support/destination or approved exception"})
    for interface in plan["interfaces"]:
        relation = relationships.get(interface["evidence_ref"])
        if relation is None or not any(
                e["page"] == relation["page"] and
                e["ref"] in [relation["anchor_ref"], *relation["support_refs"]]
                for e in interface["endpoints"]):
            bad3.append({"id": interface["id"], "reason": "interface lacks named local-support relationship"})
        for endpoint in interface["endpoints"]:
            ref, pin, page = endpoint["ref"], endpoint["pin"], endpoint["page"]
            if (ref not in instances or page not in {v["page"] for v in instances[ref]["views"]}
                    or source["pins"].get((ref, pin)) != interface["net"]):
                bad3.append({"id": interface["id"], "reason": "orphan interface endpoint/net"})
    gates["PP-03"] = _gate(bad3)
    bad4 = []
    if not isinstance(human_dir, str) or not os.path.isdir(human_dir):
        _error(f"human_dir unavailable: {human_dir!r}")
    homes = set(plan["home_pages"])
    book = {s["id"] for s in source["sheets"]}
    if homes != book or homes != {p["id"] for p in plan["pages"] if p["role"] == "home"}:
        bad4.append({"reason": "home-page set differs", "declared": sorted(homes), "book": sorted(book)})
    if len(pages) != len(plan["pages"]) or len({p["order"] for p in plan["pages"]}) != len(plan["pages"]):
        bad4.append({"reason": "duplicate page id/order"})
    disk = {s["id"] for s in source["sheets"]
            if os.path.isfile(os.path.join(base, s["source"]))
            and any(re.fullmatch(re.escape(s["id"]) + r"-v\d+\.png", n) for n in os.listdir(human_dir))}
    if disk != book:
        bad4.append({"reason": "book home pages missing on disk", "missing": sorted(book - disk)})
    for page in plan["pages"]:
        for kind in ("native", "image"):
            path = os.path.join(base, page[kind]["path"])
            if not os.path.isfile(path) or _sha(path) != page[kind]["sha256"]:
                bad4.append({"page": page["id"], "kind": kind, "reason": "missing/stale artifact"})
            if kind == "image" and os.path.dirname(os.path.realpath(path)) != os.path.realpath(human_dir):
                bad4.append({"page": page["id"], "reason": "image outside declared human tree"})
        for sheet in source["sheets"]:
            if page["id"] == sheet["id"] and os.path.realpath(os.path.join(base, page["native"]["path"])) != os.path.realpath(os.path.join(base, sheet["source"])):
                bad4.append({"page": page["id"], "reason": "native path differs from book export"})
    for instance in instances.values():
        if instance["home_page"] not in homes:
            bad4.append({"ref": instance["ref"], "reason": "home outside declared book"})
    if plan["baseline_refs"]["netlist"]["sha256"] != _sha(netlist_path):
        bad4.append({"reason": "stale netlist baseline"})
    gates["PP-04"] = _gate(bad4)
    bad5 = []
    named_targets = set(pages) | set(instances) | {i["physical_id"] for i in instances.values()}
    named_targets |= {f"{v['page']}.{i['ref']}.{p['pin']}" for i in instances.values() for v in i["views"] for p in v["pins"]}
    decision_ids = [d["id"] for d in plan["exceptions"] + plan["human_locks"]]
    if len(set(decision_ids)) != len(decision_ids):
        bad5.append({"reason": "duplicate decision id"})
    for decision in plan["exceptions"] + plan["human_locks"]:
        if decision["target"] not in named_targets or decision["approval"] is None or decision["approval"]["decision"] != "approved":
            bad5.append({"id": decision["id"], "reason": "unnamed target or explicit approval absent/rejected"})
    gates["PP-05"] = _gate(bad5)
    return {"ok": all(g["status"] == "pass" for g in gates.values()), "schema": "c03_pp_gate/1",
            "gates": gates, "unmeasured": [], "measured": {"physical_instances": len(source["refs"]),
            "expected_pins": len(expected), "declared_pins": len(declared), "home_pages": sorted(homes)},
            "inputs": {"plan_sha256": _sha(plan_path), "schema_sha256": _sha(schema_path), "netlist_sha256": _sha(netlist_path)},
            "not_checked": _not_checked()}


def _not_checked():
    return ["comprehension and design intent (independent blind review required)",
            "actual visible local wires/labels/NC marks and render-space readability",
            "approval authenticity (only supplied named fields checked; never issued)",
            "circuit correctness, electrical certification and manufacturing release"]
