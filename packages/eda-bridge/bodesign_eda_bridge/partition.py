"""Component -> leaf-sheet partition (plan eda-bridge_multi-sheet-subsystem-schematics, A1).

Pure function. No I/O, no KiCad, no LLM. Given a circuit spec it answers exactly one
question: WHICH LEAF SHEET does each component live on, and which clusters exist on
each sheet.

CONTRACT (frozen; see design.md DD-7 for the three attribution tiers)
--------------------------------------------------------------------
RULED by the user 2026-09-08 (option C-2):
  * `sheet` is the ONLY assignment channel. A missing sheet is NEVER derived from
    `group`, from net topology, or from a catch-all.
  * `group` keeps its cluster-placement meaning and is scoped PER SHEET: the cluster
    key is the ORDERED PAIR (sheet, group). Equal group strings on different sheets
    are independent clusters. Within one sheet, `group` behaves exactly as today.
  * The legacy single-sheet path is preserved.

DERIVED by this package (negotiable, unlike the RULED tier): the all-or-nothing rule,
the error codes, the name whitelist and the collision rule.

ERROR PRECEDENCE (DERIVED, literal, stated because it is otherwise ambiguous)
----------------------------------------------------------------------------
Checks run in this fixed order and the FIRST failure raises:

  0. Spec shape -- a dict carrying a `components` list, or the list itself.
     Anything else => E_SPEC_MALFORMED. A `components` value that is not a list is
     NOT coerced to an empty one: "the caller passed a broken spec" and "the caller
     passed no components" must not share an output.
  1. Per component, in spec order:
       a. not a mapping / has no attributes  => E_COMPONENT_MALFORMED
       b. `ref` key absent, or `None`        => E_REF_MISSING
       c. `ref` present, blank after strip   => E_REF_BLANK
     No synthetic identifier is ever fabricated for a missing ref. A placeholder would
     make an unidentifiable component look partitionable and would let it be COUNTED
     in the strict-partition sum.
  2. Declaration shape -- `sheet` present on every component, or on none.
     Partial => E_UNASSIGNED_REFS. This precedes value checks on purpose: a spec that
     is not even fully declared should be repaired at the shape level, and reporting a
     name defect first would send the caller to the wrong repair.
  3. Per-component value, in spec order:
       a. not a `str`               => E_SHEET_NAME_INVALID
       b. `str`, blank after strip  => E_SHEET_NAME_EMPTY
       c. fails the frozen regex    => E_SHEET_NAME_INVALID
     (b) precedes (c) because a blank string also fails the regex, and the blank case
     has its own code so that "declared but empty" never collapses into the generic one.
  4. Repeated ref, classified rather than merged:
       a. same ref on two DIFFERENT sheets => E_REF_ON_MULTIPLE_SHEETS
       b. same ref twice on ONE sheet      => E_DUPLICATE_REF
     Both are strict-partition violations; they are separate codes because they have
     different repairs (fix the assignment vs. remove the duplicate row), and keeping
     (a) reachable is what stops it becoming an unfalsifiable check.
     On the legacy path there is one bucket, so any repetition is (b). The check runs
     BEFORE the legacy early-return, otherwise a duplicate would be silently accepted
     whenever no sheet was declared.
  5. A leaf stem equal to `project_name` => E_SHEET_NAME_COLLISION.
     Last because it is the only check needing a SECOND input, and both names are
     individually legal.

STRICT PARTITION IDENTITY (the invariant the above exists to protect)
---------------------------------------------------------------------
    sum(len(v) for v in sheets.values()) == len(distinct refs) == len(components)

All three terms are asserted together by `assert_partition_identity`. A duplicate ref
breaks the second equality; a fabricated ref breaks the meaning of the third.

EXPLICIT N=1 IS NOT THE LEGACY PATH (design.md DD-10, coordinator ruling 2026-09-08)
------------------------------------------------------------------------------------
No `sheet` anywhere => the legacy flat route, unchanged. ANY explicit declaration --
including exactly one distinct sheet name -- => root + N leaves. The two are never
equated: `partition_source` is the field that keeps them apart, and a spec declaring
one sheet keeps that sheet's own name rather than the internal legacy bucket.

CLUSTERING AUTHORITY (why the legacy path returns no clusters)
---------------------------------------------------------------
On the legacy route `composer._cluster` owns clustering, and when no `group` is
declared it uses NET-DEGREE topology with hub degree-capping -- something this pure
function cannot reproduce, since it never sees the nets. So the legacy branch returns
EMPTY clusters and `clustering_authority="composer-legacy"`. Returning singletons
there would have been a fabricated answer that merely looked like composer's.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# The single frozen predicate (design.md DD-7 clause 5). `fullmatch` is used rather
# than `match` + `$`: Python's `$` also matches immediately before a trailing newline,
# so "power\n" would be accepted by `re.match(r"...$", ...)` and reach the filesystem.
SHEET_NAME_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}")
SHEET_NAME_PATTERN = "^[A-Za-z0-9_][A-Za-z0-9_-]{0,63}$"

#: Bucket name for the legacy path. Never reaches a filename: on the legacy route the
#: emitter keeps its original flat output path (design.md DD-10).
LEGACY_BUCKET = "__single__"

#: `clustering_authority` values. On the legacy route this module does not decide
#: clustering at all -- see the module docstring.
AUTHORITY_PARTITION = "partition"
AUTHORITY_COMPOSER_LEGACY = "composer-legacy"

#: `ClusterKey.kind` values. Two DISJOINT namespaces, so a component with no `group`
#: can never collide with a component whose declared group happens to spell the same
#: string.
KIND_DECLARED = "declared"
KIND_UNGROUPED = "ungrouped"

_SENTINEL = object()


class PartitionError(ValueError):
    """A partition contract violation. `ValueError` per errors.md Error Catalogue.

    Carries `code` so a caller can branch on the machine identity of the failure
    instead of matching on message text.
    """

    def __init__(self, code: str, message: str, **details):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class ClusterKey:
    """Identity of one cluster. `kind` keeps two namespaces structurally apart.

    A component with no `group` gets `kind="ungrouped"` and its own ref as the value;
    a component declaring `group="auto-R1"` gets `kind="declared"`. Under the earlier
    string scheme both produced the literal "auto-R1" and MERGED -- a declared group
    could silently absorb an unrelated ungrouped component. Two fields cannot collide,
    so the defect is removed by construction rather than by choosing a rarer prefix.
    """

    sheet: str
    kind: str   # KIND_DECLARED | KIND_UNGROUPED
    value: str  # the declared group string, or the ref when ungrouped

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.sheet, self.kind, self.value)


@dataclass(frozen=True)
class ReplicaView:
    """One DISPLAY view of a canonical component on a non-home sheet (DD-13 4c).

    `nets` is an explicit subset, never a shorthand for "all canonical nets". The
    reason is locality -- one page shows one subsystem. It is NOT that an all-net
    view would be unfalsifiable: F-1/F-2 compare every drawn attachment against the
    canonical map, so an all-net view drawn wrong still fails.
    """

    sheet: str
    nets: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"sheet": self.sheet, "nets": list(self.nets)}


@dataclass
class SheetMap:
    """Return type of `partition_components` (data-schema.json §SheetMap)."""

    sheets: dict[str, list[str]]
    partition_source: str  # "declared" | "none-declared"
    unassigned_refs: list[str] = field(default_factory=list)
    #: Ordered cluster keys, in first-appearance order.
    cluster_keys: list[ClusterKey] = field(default_factory=list)
    clusters: dict[ClusterKey, list[str]] = field(default_factory=dict)
    #: False when `project_name` was not supplied, so the caller can tell
    #: "no collision" from "collision never examined".
    collision_checked: bool = False
    #: Who decides clustering for this result. On the legacy route the answer is
    #: `composer-legacy` and `clusters` is EMPTY -- this module does not see nets and
    #: cannot reproduce composer's net-degree fallback.
    clustering_authority: str = AUTHORITY_PARTITION
    #: DD-13 clause 6: ref -> its replica views, in declaration order. Kept OUT of
    #: `sheets` on purpose -- a replica living there would break I-1's
    #: `sum == distinct` exactly the way a duplicate row does.
    replica_map: dict[str, list[ReplicaView]] = field(default_factory=dict)
    #: False when the spec carried no `nets`, so "no non-canonical net found" is
    #: distinguishable from "the canonical-net check never ran".
    replica_nets_checked: bool = False

    @property
    def component_count(self) -> int:
        """Distinct refs -- I-1's third term. NOT the number of drawn symbols."""
        return len({ref for refs in self.sheets.values() for ref in refs})

    @property
    def drawn_instance_count(self) -> int:
        """`component_count` + every replica view; equal to it when there are none.

        Deliberately a different name: after DD-13 "how many components" and "how
        many symbols are drawn" have different answers, and one number reported as
        "N components" would be read as whichever the reader expected.
        """
        return self.component_count + sum(
            len(views) for views in self.replica_map.values())

    def replicas_on(self, sheet: str) -> list[tuple[str, ReplicaView]]:
        """(ref, view) pairs to be DRAWN on `sheet`, in declaration order."""
        return [(ref, view)
                for ref, views in self.replica_map.items()
                for view in views if view.sheet == sheet]

    @property
    def is_multi_sheet(self) -> bool:
        """True when the caller declared sheets -- including exactly one (DD-10)."""
        return self.partition_source == "declared"

    def clusters_on(self, sheet: str) -> list[list[str]]:
        """Member lists of every cluster on one sheet, in first-appearance order."""
        return [self.clusters[key] for key in self.cluster_keys if key.sheet == sheet]

    def to_dict(self) -> dict:
        return {
            "sheets": {name: list(refs) for name, refs in self.sheets.items()},
            "partition_source": self.partition_source,
            "unassigned_refs": list(self.unassigned_refs),
            "cluster_keys": [list(key.as_tuple()) for key in self.cluster_keys],
            "clusters": {"\x1f".join(k.as_tuple()): list(v)
                         for k, v in self.clusters.items()},
            "collision_checked": self.collision_checked,
            "clustering_authority": self.clustering_authority,
            "replica_map": {ref: [view.to_dict() for view in views]
                            for ref, views in self.replica_map.items()},
            "replica_nets_checked": self.replica_nets_checked,
            "component_count": self.component_count,
            "drawn_instance_count": self.drawn_instance_count,
        }


def assert_replica_wellformed(result: SheetMap) -> None:
    """Invariant I-2 (DD-13 clause 6). A SECOND assertion, never folded into I-1.

    Three distinct shapes, three codes, because the three repairs differ. Merging
    them into one count could not tell a corrupt home partition from a malformed
    replica list.

    VACUOUSLY TRUE when `replica_map` is empty -- which is every spec that exists
    today. A test cell asserting only this on a replica-free spec proves nothing and
    MUST supply a non-empty map.
    """
    home_of = {ref: sheet for sheet, refs in result.sheets.items() for ref in refs}
    for ref, views in result.replica_map.items():
        if ref not in home_of:
            COUNTERS.raised_replica_unknown_ref += 1
            raise PartitionError(
                "E_REPLICA_UNKNOWN_REF",
                f"replica declared for {ref!r}, which has no home sheet. A replica "
                f"is netlist-neutral RELATIVE TO a home; without one there is "
                f"nothing for it to be neutral against.",
                ref=ref, known_refs=sorted(home_of),
            )
        seen: set[str] = set()
        for view in views:
            if view.sheet == home_of[ref]:
                COUNTERS.raised_replica_on_home += 1
                raise PartitionError(
                    "E_REPLICA_ON_HOME_SHEET",
                    f"{ref}: replica sheet {view.sheet!r} is its own home sheet. "
                    f"Drawing it twice on one page has no reader benefit, and "
                    f"KiCad merges same-sheet duplicates into one comp (measured).",
                    ref=ref, sheet=view.sheet,
                )
            if view.sheet in seen:
                COUNTERS.raised_replica_duplicate += 1
                raise PartitionError(
                    "E_REPLICA_DUPLICATE",
                    f"{ref}: sheet {view.sheet!r} appears twice in `replicas`. Two "
                    f"views of one ref on one page are indistinguishable to a "
                    f"reader and would double the drawn-instance count.",
                    ref=ref, sheet=view.sheet,
                )
            seen.add(view.sheet)


def assert_partition_identity(result: SheetMap, component_count: int) -> None:
    """The frozen invariant, checked rather than trusted.

    Raised as `PartitionError` (not `AssertionError`) so it survives `python -O` and
    reaches a caller through the same channel as every other contract violation.
    """
    assigned = [ref for refs in result.sheets.values() for ref in refs]
    distinct = len(set(assigned))
    if not (len(assigned) == distinct == component_count):
        raise PartitionError(
            "E_PARTITION_IDENTITY_BROKEN",
            f"strict partition identity violated: sum={len(assigned)} "
            f"distinct={distinct} components={component_count}",
            assigned=len(assigned), distinct=distinct,
            component_count=component_count,
        )


@dataclass
class _Counters:
    """Branch-ENTRY counters (errors.md §排放點紀律).

    These count which code path was entered, not what was returned. Instrumenting the
    result cannot separate "the legacy branch ran and produced one bucket" from "the
    function was never called at all"; a per-branch entry counter can.
    """

    calls_entered: int = 0
    legacy_branch_entered: int = 0
    declared_branch_entered: int = 0
    raised_spec_malformed: int = 0
    raised_component_malformed: int = 0
    raised_ref_missing: int = 0
    raised_ref_blank: int = 0
    raised_unassigned: int = 0
    raised_name_empty: int = 0
    raised_name_invalid: int = 0
    raised_ref_multi_sheet: int = 0
    raised_duplicate_ref: int = 0
    raised_name_collision: int = 0
    collision_check_skipped_no_project: int = 0
    # DD-13 clause 4c/6 -- replica input side.
    replica_branch_entered: int = 0
    raised_replica_view_malformed: int = 0
    raised_replica_view_empty: int = 0
    raised_replica_unknown_sheet: int = 0
    raised_replica_without_home: int = 0
    raised_replica_unknown_ref: int = 0
    raised_replica_on_home: int = 0
    raised_replica_duplicate: int = 0
    raised_replica_net_not_canonical: int = 0
    replica_net_check_skipped_no_nets: int = 0

    def reset(self) -> None:
        for name in self.__dataclass_fields__:
            setattr(self, name, 0)

    def snapshot(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


#: Module-level so a caller (or a test) can read which branches actually executed.
#: `calls_entered == 0` is the module's own `not-run` signal: it distinguishes a
#: partition that was never invoked from one that ran and returned a single bucket.
COUNTERS = _Counters()


def _raw_components(spec) -> list:
    """Precedence step 0. A malformed spec raises; it never becomes an empty list."""
    if spec is None:
        COUNTERS.raised_spec_malformed += 1
        raise PartitionError(
            "E_SPEC_MALFORMED",
            "spec is None. An absent spec is not an empty component list -- pass "
            "{'components': []} to mean 'no components'.",
            received_type="NoneType",
        )
    if isinstance(spec, dict):
        if "components" not in spec:
            COUNTERS.raised_spec_malformed += 1
            raise PartitionError(
                "E_SPEC_MALFORMED",
                "spec dict has no 'components' key. A missing key is not an empty "
                "list: the earlier code coerced it and a typo'd key silently "
                "partitioned zero components.",
                keys=sorted(str(k) for k in spec),
            )
        raw = spec["components"]
    else:
        raw = spec
    if isinstance(raw, (str, bytes, dict)) or not isinstance(raw, (list, tuple)):
        COUNTERS.raised_spec_malformed += 1
        raise PartitionError(
            "E_SPEC_MALFORMED",
            f"`components` must be a list or tuple, received "
            f"{type(raw).__name__} {raw!r}.",
            received_type=type(raw).__name__, received=raw,
        )
    return list(raw)


def _declared_sheet(comp) -> object:
    """The component's `sheet` value, or `_SENTINEL` when the key is ABSENT.

    A JSON `null` returns None (present-and-invalid), never `_SENTINEL` -- otherwise
    "the author wrote null" and "the author wrote nothing" would share one output.
    """
    if isinstance(comp, dict):
        return comp.get("sheet", _SENTINEL)
    return getattr(comp, "sheet", _SENTINEL)


def _ref_of(comp, index: int) -> str:
    """Precedence step 1. Returns a REAL ref or raises -- never a synthetic one.

    The earlier version returned `f"<component#{index}>"` for a missing ref. That
    placeholder let an unidentifiable component be counted in the strict-partition
    sum and be written to a sheet, so a malformed spec produced a result that looked
    complete.
    """
    if isinstance(comp, dict):
        has_ref = "ref" in comp
        ref = comp.get("ref")
    elif hasattr(comp, "ref"):
        has_ref = True
        ref = getattr(comp, "ref")
    elif isinstance(comp, (str, bytes, int, float, bool)) or comp is None:
        COUNTERS.raised_component_malformed += 1
        raise PartitionError(
            "E_COMPONENT_MALFORMED",
            f"component #{index} is {type(comp).__name__} {comp!r}; expected a "
            f"mapping or an object carrying `ref`.",
            index=index, received=comp, received_type=type(comp).__name__,
        )
    else:
        has_ref = False
        ref = None

    if not has_ref or ref is None:
        COUNTERS.raised_ref_missing += 1
        raise PartitionError(
            "E_REF_MISSING",
            f"component #{index} has no usable `ref` "
            f"({'ref=None' if has_ref else 'key absent'}). No synthetic identifier "
            f"is generated -- an unidentifiable component cannot be partitioned.",
            index=index, ref_key_present=has_ref,
        )
    text = str(ref).strip()
    if not text:
        COUNTERS.raised_ref_blank += 1
        raise PartitionError(
            "E_REF_BLANK",
            f"component #{index} has a blank `ref` ({ref!r}). Blank is declared-and-"
            f"empty, which is a different defect from an absent key "
            f"(E_REF_MISSING) and keeps its own code.",
            index=index, received=ref,
        )
    return text


def _group_of(comp) -> str | None:
    if isinstance(comp, dict):
        group = comp.get("group")
    else:
        group = getattr(comp, "group", None)
    if group is None:
        return None
    text = str(group).strip()
    return text or None


def _validate_name(ref: str, value) -> str:
    """Apply precedence step 2 to one value. Returns the validated name."""
    if not isinstance(value, str) or isinstance(value, bool):
        COUNTERS.raised_name_invalid += 1
        raise PartitionError(
            "E_SHEET_NAME_INVALID",
            f"{ref}: `sheet` must be a str, received {type(value).__name__} "
            f"{value!r} (condition: type check). A JSON null counts as declared, "
            f"not as an absent key.",
            ref=ref, received=value, received_type=type(value).__name__,
            condition="not-a-str",
        )
    if not value.strip():
        COUNTERS.raised_name_empty += 1
        raise PartitionError(
            "E_SHEET_NAME_EMPTY",
            f"{ref}: `sheet` is declared but blank after strip() ({value!r}). "
            f"Supply a real name, or remove the key from EVERY component to take "
            f"the legacy path -- this does NOT degrade to E_UNASSIGNED_REFS.",
            ref=ref, received=value,
        )
    if SHEET_NAME_RE.fullmatch(value) is None:
        COUNTERS.raised_name_invalid += 1
        raise PartitionError(
            "E_SHEET_NAME_INVALID",
            f"{ref}: `sheet` {value!r} fails {SHEET_NAME_PATTERN} "
            f"(condition: regex). The name is used verbatim as the leaf filename "
            f"stem, and this engine does not sanitize -- rename it.",
            ref=ref, received=value, condition="regex",
            pattern=SHEET_NAME_PATTERN,
        )
    return value


def _replica_views_of(comp) -> object:
    """The component's `replicas` value, or `_SENTINEL` when the key is ABSENT."""
    if isinstance(comp, dict):
        return comp.get("replicas", _SENTINEL)
    return getattr(comp, "replicas", _SENTINEL)


def _parse_replica_views(ref: str, raw) -> list[ReplicaView]:
    """Precedence step 6a: shape and value checks on ONE component's `replicas`.

    A bare string entry is the OLD (round-44a) shape. It is rejected loudly rather
    than reinterpreted as "all nets": silently upgrading it would make a stale spec
    produce a view whose net subset nobody chose.
    """
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        COUNTERS.raised_replica_view_malformed += 1
        raise PartitionError(
            "E_REPLICA_VIEW_MALFORMED",
            f"{ref}: `replicas` must be a list of view objects, received "
            f"{type(raw).__name__} {raw!r}.",
            ref=ref, received=raw, received_type=type(raw).__name__,
        )
    views: list[ReplicaView] = []
    for position, entry in enumerate(raw):
        if not isinstance(entry, dict):
            COUNTERS.raised_replica_view_malformed += 1
            raise PartitionError(
                "E_REPLICA_VIEW_MALFORMED",
                f"{ref}: `replicas`[{position}] is {type(entry).__name__} "
                f"{entry!r}; expected {{'sheet': <str>, 'nets': [<str>, ...]}}. A "
                f"bare sheet name is the pre-round-44b shape and is refused rather "
                f"than read as 'all nets'.",
                ref=ref, index=position, received=entry,
                received_type=type(entry).__name__,
            )
        sheet = _validate_name(ref, entry.get("sheet"))
        raw_nets = entry.get("nets")
        if raw_nets is None or (isinstance(raw_nets, (list, tuple))
                                and len(raw_nets) == 0):
            COUNTERS.raised_replica_view_empty += 1
            raise PartitionError(
                "E_REPLICA_VIEW_EMPTY",
                f"{ref}: replica view on {sheet!r} names no nets. An empty subset "
                f"is a symbol attached to nothing -- a decoration, not a subsystem "
                f"view. It is NOT shorthand for 'all nets': accepting it would let "
                f"'named none' and 'wanted everything' share one output.",
                ref=ref, sheet=sheet,
            )
        if not isinstance(raw_nets, (list, tuple)):
            COUNTERS.raised_replica_view_malformed += 1
            raise PartitionError(
                "E_REPLICA_VIEW_MALFORMED",
                f"{ref}: replica view on {sheet!r} has `nets` of type "
                f"{type(raw_nets).__name__}; expected a list of net names.",
                ref=ref, sheet=sheet, received_type=type(raw_nets).__name__,
            )
        names: list[str] = []
        for net in raw_nets:
            if not isinstance(net, str) or not net.strip():
                COUNTERS.raised_replica_view_malformed += 1
                raise PartitionError(
                    "E_REPLICA_VIEW_MALFORMED",
                    f"{ref}: replica view on {sheet!r} lists net {net!r}; every "
                    f"entry must be a non-blank str.",
                    ref=ref, sheet=sheet, received=net,
                )
            names.append(net.strip())
        views.append(ReplicaView(sheet=sheet, nets=tuple(names)))
    return views


def canonical_pin_nets(raw_nets) -> dict[str, set[str]]:
    """ref -> the set of net names the SPEC assigns to any pin of that ref.

    Used only for the `E_REPLICA_NET_NOT_CANONICAL` input check. Tolerant of a
    missing/None `nets` because the CALLER decides whether the check ran -- see
    `replica_nets_checked`, which is what keeps "no violation" apart from "never
    examined".
    """
    by_ref: dict[str, set[str]] = {}
    if not isinstance(raw_nets, (list, tuple)):
        return by_ref
    for net in raw_nets:
        if not isinstance(net, dict):
            continue
        name = str(net.get("name", "")).strip()
        if not name:
            continue
        for node in net.get("nodes") or ():
            ref = str(node).partition(".")[0].strip()
            if ref:
                by_ref.setdefault(ref, set()).add(name)
    return by_ref


def partition_components(spec, project_name: str | None = None) -> SheetMap:
    """Partition components onto leaf sheets and cluster them per (sheet, group).

    spec:         a dict carrying `components`, or the component list itself. Each
                  component is a dict (or object) with `ref`, optional `group`, and
                  optional `sheet`.
    project_name: the root schematic stem. Required for the leaf-vs-root collision
                  check; when omitted the check is SKIPPED and the returned
                  `collision_checked` is False, so its absence is visible rather than
                  looking like a clean result.

    Raises `PartitionError` per the precedence documented in the module docstring.
    """
    COUNTERS.calls_entered += 1
    components = _raw_components(spec)

    refs: list[str] = []
    declared: list[object] = []
    for index, comp in enumerate(components):
        refs.append(_ref_of(comp, index))
        declared.append(_declared_sheet(comp))

    present = [i for i, value in enumerate(declared) if value is not _SENTINEL]

    # --- precedence 2: declaration shape ------------------------------------
    if not present:
        COUNTERS.legacy_branch_entered += 1
        # Duplicates are rejected on BOTH routes. Checking after this early return
        # would have accepted a duplicate whenever no sheet was declared.
        _reject_duplicate_refs(refs, [LEGACY_BUCKET] * len(refs))
        # A replica has no home on the legacy route, so there is nothing for it to
        # be netlist-neutral against. Refused rather than ignored: ignoring it would
        # drop a drawing the caller asked for and still return a clean result.
        for index, comp in enumerate(components):
            raw_replicas = _replica_views_of(comp)
            if raw_replicas is not _SENTINEL and raw_replicas:
                COUNTERS.raised_replica_without_home += 1
                raise PartitionError(
                    "E_REPLICA_WITHOUT_HOME",
                    f"{refs[index]}: `replicas` declared but no component declares "
                    f"`sheet`, so this spec takes the legacy flat route and there "
                    f"is no home sheet for the replica to be neutral against.",
                    ref=refs[index], received=raw_replicas,
                )
        result = SheetMap(
            sheets={LEGACY_BUCKET: list(refs)},
            partition_source="none-declared",
            unassigned_refs=[],
            # Clustering on this route belongs to composer._cluster, which uses
            # net-degree topology this function cannot see. Empty, not fabricated.
            cluster_keys=[],
            clusters={},
            collision_checked=False,
            clustering_authority=AUTHORITY_COMPOSER_LEGACY,
        )
        assert_partition_identity(result, len(components))
        return result

    if len(present) != len(components):
        missing = [refs[i] for i, value in enumerate(declared) if value is _SENTINEL]
        COUNTERS.raised_unassigned += 1
        raise PartitionError(
            "E_UNASSIGNED_REFS",
            f"`sheet` is all-or-nothing: {len(present)}/{len(components)} components "
            f"declare it. Missing on: {missing}. The engine will not infer the sheet "
            f"from `group`, from topology, or from a catch-all.",
            unassigned_refs=missing,
            declared_count=len(present),
            component_count=len(components),
        )

    COUNTERS.declared_branch_entered += 1

    # --- precedence 3: per-component value ----------------------------------
    names = [_validate_name(refs[i], declared[i]) for i in range(len(components))]

    # --- precedence 4: repeated refs ----------------------------------------
    _reject_duplicate_refs(refs, names)

    # --- precedence 5: leaf stem vs root stem --------------------------------
    if project_name is None:
        COUNTERS.collision_check_skipped_no_project += 1
        collision_checked = False
    else:
        collision_checked = True
        colliding = sorted({name for name in names if name == project_name})
        if colliding:
            COUNTERS.raised_name_collision += 1
            raise PartitionError(
                "E_SHEET_NAME_COLLISION",
                f"leaf stem {colliding[0]!r} equals the root stem "
                f"(project_name={project_name!r}); the leaf write would silently "
                f"truncate the root while the file set still looked complete.",
                colliding_name=colliding[0], project_name=project_name,
            )

    sheets: dict[str, list[str]] = {}
    for ref, name in zip(refs, names):
        sheets.setdefault(name, []).append(ref)

    # --- precedence 6: replica views (DD-13 clause 4c) ------------------------
    replica_map: dict[str, list[ReplicaView]] = {}
    for index, comp in enumerate(components):
        raw_replicas = _replica_views_of(comp)
        if raw_replicas is _SENTINEL:
            continue
        views = _parse_replica_views(refs[index], raw_replicas)
        if views:
            replica_map[refs[index]] = views
    if replica_map:
        COUNTERS.replica_branch_entered += 1

    declared_sheets = set(sheets)
    for ref, views in replica_map.items():
        for view in views:
            if view.sheet not in declared_sheets:
                COUNTERS.raised_replica_unknown_sheet += 1
                raise PartitionError(
                    "E_REPLICA_UNKNOWN_SHEET",
                    f"{ref}: replica sheet {view.sheet!r} is not a sheet any "
                    f"component declares as home. A replica is drawn on an "
                    f"EXISTING leaf; it never creates one.",
                    ref=ref, sheet=view.sheet,
                    known_sheets=sorted(declared_sheets),
                )

    raw_spec_nets = spec.get("nets") if isinstance(spec, dict) else None
    if raw_spec_nets is None:
        COUNTERS.replica_net_check_skipped_no_nets += 1
        replica_nets_checked = False
    else:
        replica_nets_checked = True
        by_ref = canonical_pin_nets(raw_spec_nets)
        for ref, views in replica_map.items():
            canonical = by_ref.get(ref, set())
            for view in views:
                stray = [net for net in view.nets if net not in canonical]
                if stray:
                    COUNTERS.raised_replica_net_not_canonical += 1
                    raise PartitionError(
                        "E_REPLICA_NET_NOT_CANONICAL",
                        f"{ref}: replica view on {view.sheet!r} names net(s) "
                        f"{stray} that the canonical design does not assign to any "
                        f"pin of {ref}. Drawing them would invent connectivity the "
                        f"netlist cannot contradict, because replica pins are "
                        f"absent from it by construction.",
                        ref=ref, sheet=view.sheet, stray_nets=stray,
                        canonical_nets=sorted(canonical),
                    )

    keys = []
    for index, comp in enumerate(components):
        group = _group_of(comp)
        if group is None:
            keys.append(ClusterKey(names[index], KIND_UNGROUPED, refs[index]))
        else:
            keys.append(ClusterKey(names[index], KIND_DECLARED, group))
    cluster_keys, clusters = _build_clusters(keys, refs)

    result = SheetMap(
        sheets=sheets,
        partition_source="declared",
        unassigned_refs=[],
        cluster_keys=cluster_keys,
        clusters=clusters,
        collision_checked=collision_checked,
        clustering_authority=AUTHORITY_PARTITION,
        replica_map=replica_map,
        replica_nets_checked=replica_nets_checked,
    )
    assert_partition_identity(result, len(components))
    assert_replica_wellformed(result)
    return result


def _reject_duplicate_refs(refs: list[str], names: list[str]) -> None:
    """Precedence step 4. Both repetition shapes raise, with distinct codes."""
    seen: dict[str, list[str]] = {}
    for ref, name in zip(refs, names):
        seen.setdefault(ref, []).append(name)

    multi = {ref: sorted(set(where)) for ref, where in seen.items()
             if len(set(where)) > 1}
    if multi:
        COUNTERS.raised_ref_multi_sheet += 1
        raise PartitionError(
            "E_REF_ON_MULTIPLE_SHEETS",
            f"strict partition violated: {sorted(multi)} each appear on more than "
            f"one sheet ({multi}).",
            refs_on_multiple_sheets=multi,
        )

    dupes = {ref: len(where) for ref, where in seen.items() if len(where) > 1}
    if dupes:
        COUNTERS.raised_duplicate_ref += 1
        raise PartitionError(
            "E_DUPLICATE_REF",
            f"strict partition violated: {sorted(dupes)} appear more than once "
            f"({dupes}). The identity sum == distinct == components requires each "
            f"ref exactly once; remove the duplicate row.",
            duplicate_refs=dupes,
        )


def _build_clusters(keys: list[ClusterKey], refs: list[str]):
    """ClusterKey -> members, preserving first-appearance order."""
    order: list[ClusterKey] = []
    members: dict[ClusterKey, list[str]] = {}
    for key, ref in zip(keys, refs):
        if key not in members:
            members[key] = []
            order.append(key)
        members[key].append(ref)
    return order, members
