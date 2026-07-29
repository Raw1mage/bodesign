"""control.quality.no-silent-degradation — 部分失敗不得靜默降級為完全成功。

BR_20260729 沉澱：一輪 C04 交付撞出 5 個同族缺陷（§B/§C/§D/§E + S2），全部通過了
當時的全部測試。這證明 No-silent-fallback 天條當時只是 prose，不是可執行的閘。
本模組把它變成可跑的 AST lint。

與 `checkers/` 其餘模組的**結構差異（重要，勿誤用）**：
其餘 checker 檢的是 *design IR*（一塊板的幾何/網表），簽章吃 IR dict、回傳 violation
list、掛在 C00–C04 管線階段上、evidence 走 ORACLE_TOOLS envelope。**本模組檢的是
Python 原始碼**——它沒有 IR 輸入、不屬於任何管線階段、也不產生板級 evidence。
它因此**不註冊進 `build_pilot_registry()`**：那張表的語意是「control → design-IR
checker」，硬塞一條 source-code lint 會逼我們在 `ir_fields` 填假路徑，而那正是本
control 自己禁止的捏造。它改由 CI / 開發期直接呼叫（見檔末 __main__）。

判準句（review 時問這一句就夠）：
    如果呼叫端只讀 `ok` 或只讀一個計數就會得出錯誤結論，這個 API 就違反本 invariant。

變體分類（BR_20260729）：
    V1 元素靜默丟棄      — 迴圈 skip 掉元素，計數器不涵蓋此類          （§B, §D）
    V2 量測降級無標記    — fallback 到語意不同的量測法，回傳不標 basis  （§C）
    V3 狀態不反映降級    — 降級資訊有傳出，但 ok/status 恆為成功        （S2）
    V4 量測基準分散      — 同一物理量多處各自實作，修正只落其中一處     （§E）

tier 由**實測訊噪比**決定，不是由提案推測決定。對 §B/§C/§D/§E 修復前後的
routing.py 各掃一次，看每條規則是否「修復前命中、修復後歸零」：

    規則  修前  修後   tier
    L2     2     0    T-A   except 只有 pass/log 而函式有回傳值      → V1/V2（§D）
    L6     1     0    T-A   呼叫端傳入的 key 查找失敗即靜默跳過      → V1（§D）
    L8     1     0    T-A   同一量測 API 在 >1 個函式各自實作        → V4（§E）
    L1    19    19    T-C   迴圈內 continue 未記錄被跳過的元素       → V1

L1 **降為 advisory（預設不輸出，需 include_advisory=True）**：它修復前後都報 19 筆，
命中的是 `_parse_netlist` 的 regex 不匹配跳過、`via_in_pad` 的 keep-ring 篩選這類
**正常的 filter 語意**——那些 `continue` 不是在丟棄呼叫端交付的元素，而是在表達
「這一項本來就不該處理」。AST 分不出「篩掉」與「丟掉」，硬當 T-A 會讓 19 筆雜訊
淹掉 3 筆真訊號，最後沒人跑這條 lint。誠實標 T-C，勝過假裝它是硬閘。

**誠實未實作**（不假裝覆蓋）：
    L3  expected vs actual 計數      — 需回傳 schema 對照，AST 看不到
    L4  primary/fallback 量測標記    — 需語意判斷哪條是 fallback
    L5  荒謬值 tripwire              — **runtime domain 檢查，靜態不可判**。
        它是設計規則不是 lint：每個物理量在回傳前自檢定義域（占用率>1.0、
        面積>母體、距離為負、計數>母集合）→ ok:false + implausible_measurement。
        reference implementation: `routing.py::placement_preflight` 的
        `implausible` 分支（BR_20260729 §C）。
    L7  key 書寫法正規化             — advisory，靠 review 提問
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# 名稱含這些 token 的容器，視為「有記錄被跳過的元素」。
_DROP_TOKENS = ("drop", "skip", "unresolved", "missing", "fail", "reject",
                "invalid", "unknown", "degraded", "absent", "omitted",
                "unmapped", "unplaced", "warn")

# L8：同一物理量的取得 API。分散在多個函式各自實作 = V4。
#
# 量測對象（receiver）不同就不是同一物理量：`pad.GetBoundingBox()` 量的是一個
# pad，`fp.GetBoundingBox()` 量的是整顆元件。實測不區分會把 `_pad_radius_iu`
# 跟 `footprint_extent` 報成重複實作（誤報），所以以 (receiver, api) 配對為鍵。
_MEASUREMENT_APIS = ("GetBoundingBox", "GetCourtyard", "GetCourtyardBoundingBox")
_MEASUREMENT_RECEIVERS = ("fp", "footprint", "mod", "module", "part")

# T-C: reported only when explicitly asked for (see module docstring).
_ADVISORY_RULES = frozenset({"L1"})


@dataclass(frozen=True, slots=True)
class Finding:
    rule: str          # L1 | L2 | L6 | L8
    variant: str       # V1 | V2 | V3 | V4
    path: str
    line: int
    func: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} [{self.rule}/{self.variant}] {self.func}: {self.message}"


def _records_drop(nodes: list[ast.AST]) -> bool:
    """True if any statement in `nodes` appends/assigns to a drop-ish container."""
    for node in nodes:
        for sub in ast.walk(node):
            # x.append(...) / x.add(...) where x is drop-ish
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                if sub.func.attr in ("append", "add", "extend", "setdefault", "update"):
                    base = sub.func.value
                    name = base.id if isinstance(base, ast.Name) else (
                        base.attr if isinstance(base, ast.Attribute) else "")
                    if any(t in name.lower() for t in _DROP_TOKENS):
                        return True
            # x[k] = ... / x += ... where x is drop-ish
            if isinstance(sub, (ast.Assign, ast.AugAssign)):
                targets = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
                for tgt in targets:
                    for t2 in ast.walk(tgt):
                        if isinstance(t2, ast.Name) and any(
                                t in t2.id.lower() for t in _DROP_TOKENS):
                            return True
                        if isinstance(t2, ast.Attribute) and any(
                                t in t2.attr.lower() for t in _DROP_TOKENS):
                            return True
            # raise = fail-loud, which satisfies the invariant
            if isinstance(sub, ast.Raise):
                return True
    return False


def _has_return_value(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Return) and sub.value is not None:
            return True
    return False


def _enclosing_stmts(loop: ast.AST) -> list[ast.AST]:
    body = getattr(loop, "body", [])
    orelse = getattr(loop, "orelse", [])
    return list(body) + list(orelse)


class _Visitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.findings: list[Finding] = []
        self._func_stack: list[str] = []
        self._l6_lines: set[int] = set()
        # L8: measurement API -> set of functions that call it
        self.measurement_sites: dict[str, set[str]] = {}

    # -- function context ---------------------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._func_stack.append(node.name)
        self._check_L1(node)
        self._check_L2(node)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    @property
    def _func(self) -> str:
        return self._func_stack[-1] if self._func_stack else "<module>"

    # -- L8 -----------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Attribute) and node.func.attr in _MEASUREMENT_APIS:
            recv = node.func.value
            name = recv.id if isinstance(recv, ast.Name) else (
                recv.attr if isinstance(recv, ast.Attribute) else "")
            # only footprint-level receivers count as "the same physical quantity"
            if any(r == name.lower() for r in _MEASUREMENT_RECEIVERS):
                key = f"{name}.{node.func.attr}"
                self.measurement_sites.setdefault(key, set()).add(self._func)
        self.generic_visit(node)

    # -- L1 / L6 ------------------------------------------------------------
    def _check_L1(self, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """continue/pass inside a loop that records nothing about the skipped element."""
        seen_lines: set[int] = set()
        for loop in ast.walk(fn):
            if not isinstance(loop, (ast.For, ast.AsyncFor, ast.While)):
                continue
            stmts = _enclosing_stmts(loop)
            for node in ast.walk(loop):
                if not isinstance(node, ast.Continue):
                    continue
                # a `continue` inside a nested loop is reachable from both the
                # outer and inner walk; report each source line once.
                if node.lineno in seen_lines:
                    continue
                seen_lines.add(node.lineno)
                # Look at the branch that owns this `continue`: find the nearest
                # enclosing If and check whether that branch records the skip.
                owner = _owning_branch(loop, node)
                if _records_drop(owner if owner else stmts):
                    continue
                self.findings.append(Finding(
                    rule="L1", variant="V1", path=self.path,
                    line=node.lineno, func=fn.name,
                    message=("loop `continue` skips an element without recording it "
                             "(no drop/skip/unresolved container, no raise) — the "
                             "caller cannot tell this element was dropped")))
            self._check_L6(loop, fn)

    # -- L6 -----------------------------------------------------------------
    def _check_L6(self, loop: ast.AST, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """The §D shape: `v = d.get(k)` then `if v is not None:` with NO else.

        Note this has NO `continue` — the element falls off the end of the loop
        body and vanishes. That is precisely why L1 alone did not cover §D and
        why plane_layers went unnoticed: nothing in the source *looks* like a skip.
        """
        # names assigned from a .get(...) call inside this loop
        from_get: set[str] = set()
        for node in ast.walk(loop):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Attribute) and call.func.attr == "get":
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            from_get.add(tgt.id)
        if not from_get:
            return
        for node in ast.walk(loop):
            if not isinstance(node, ast.If) or node.orelse:
                continue
            # nested loops reach the same If from both walks — report the line once
            if node.lineno in self._l6_lines:
                continue
            test = node.test
            if not (isinstance(test, ast.Compare) and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.IsNot)
                    and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value is None):
                continue
            if not (isinstance(test.left, ast.Name) and test.left.id in from_get):
                continue
            if _records_drop(list(node.body)):
                continue
            self._l6_lines.add(node.lineno)
            self.findings.append(Finding(
                rule="L6", variant="V1", path=self.path, line=node.lineno,
                func=fn.name,
                message=(f"`{test.left.id}` came from a .get() lookup and the "
                         f"`is not None` guard has no else branch — a key the "
                         f"caller supplied but we failed to resolve is silently "
                         f"dropped. Normalise the key or fail loud (BR_20260729 §D)")))

    # -- L2 -----------------------------------------------------------------
    def _check_L2(self, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """except body that only passes / only logs, in a value-returning function."""
        if not _has_return_value(fn):
            return
        for handler in ast.walk(fn):
            if not isinstance(handler, ast.ExceptHandler):
                continue
            body = handler.body
            silent = all(
                isinstance(st, ast.Pass)
                or (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call)
                    and _is_log_call(st.value))
                for st in body
            )
            if silent and not _records_drop(body):
                self.findings.append(Finding(
                    rule="L2", variant="V2", path=self.path, line=handler.lineno,
                    func=fn.name,
                    message=("`except` swallows the failure (only pass/log) in a "
                             "function that returns a value — the return cannot "
                             "distinguish success from a swallowed failure")))


def _owning_branch(loop: ast.AST, target: ast.Continue) -> list[ast.AST]:
    """Return the statement list of the nearest If-branch containing `target`."""
    best: list[ast.AST] = []
    for node in ast.walk(loop):
        if isinstance(node, ast.If):
            for branch in (node.body, node.orelse):
                if any(target is sub for st in branch for sub in ast.walk(st)):
                    best = list(branch)
    return best


def _is_log_call(call: ast.Call) -> bool:
    fn = call.func
    if isinstance(fn, ast.Attribute):
        base = fn.value
        name = base.id if isinstance(base, ast.Name) else ""
        return ("log" in name.lower() or "logger" in name.lower()
                or fn.attr in ("debug", "info", "warning", "warn", "error", "exception"))
    if isinstance(fn, ast.Name):
        return fn.id in ("print",)
    return False


def check_file(path: str | Path, *, include_advisory: bool = False) -> list[Finding]:
    """Scan one file. `include_advisory` adds the T-C rules (L1) — off by default
    because their signal-to-noise does not justify blocking on them (see module
    docstring: 19 findings before AND after the fixes they were meant to catch)."""
    p = Path(path)
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    except SyntaxError as exc:  # a file we cannot parse is reported, never skipped
        return [Finding(rule="L0", variant="V0", path=str(p), line=exc.lineno or 0,
                        func="<parse>", message=f"could not parse: {exc.msg}")]
    v = _Visitor(str(p))
    v.visit(tree)
    findings = [f for f in v.findings if include_advisory or f.rule not in _ADVISORY_RULES]
    for api, funcs in v.measurement_sites.items():
        if len(funcs) > 1:
            findings.append(Finding(
                rule="L8", variant="V4", path=str(p), line=0,
                func=", ".join(sorted(funcs)),
                message=(f"`{api}` is called from {len(funcs)} different functions — "
                         f"the same physical quantity is measured by independent "
                         f"implementations; converge on one helper (BR_20260729 §E)")))
    return findings


@dataclass(slots=True)
class Coverage:
    """What the scan ACTUALLY covered (BR_20260729 L10).

    A checker that returns only findings is itself an instance of the anti-pattern
    it enforces: on "0 findings" the caller cannot distinguish `clean` from
    `never scanned`. That is not hypothetical — this checker's own default roots
    once omitted services/, so the documented 11-finding baseline printed as 5 and
    a CI run would have gone green over unscanned code. Every scan therefore
    reports its roots, how many files it actually parsed, and what it skipped.
    """
    roots: list[str]
    missing_roots: list[str]
    files_scanned: int
    files_skipped: int
    unparsable: list[str]


def check_paths(roots: list[str | Path], *, include_advisory: bool = False,
                with_coverage: bool = False):
    """Scan `roots`. Returns findings, or (findings, Coverage) when with_coverage."""
    out: list[Finding] = []
    missing: list[str] = []
    scanned = skipped = 0
    unparsable: list[str] = []
    for root in roots:
        rp = Path(root)
        if not rp.exists():
            # A root that does not exist is a coverage hole, not an empty result:
            # a typo'd path would otherwise silently contribute zero findings.
            missing.append(str(root))
            continue
        files = sorted(rp.rglob("*.py")) if rp.is_dir() else [rp]
        for f in files:
            if "__pycache__" in f.parts or f.name.startswith("test_"):
                skipped += 1
                continue
            got = check_file(f, include_advisory=include_advisory)
            out.extend(got)
            # check_file never raises on a bad parse — it reports L0 and moves on,
            # which is the right call (a file we cannot read is a finding, not a
            # skip). Derive coverage from that finding rather than from an except
            # branch that could never fire. A file we failed to parse is NOT
            # counted as scanned: inflating the count with files the rules never
            # actually ran over is the very dishonesty this coverage exists to stop.
            if any(g.rule == "L0" for g in got):
                unparsable.append(str(f))
            else:
                scanned += 1
    if not with_coverage:
        return out
    return out, Coverage(roots=[str(r) for r in roots], missing_roots=missing,
                         files_scanned=scanned, files_skipped=skipped,
                         unparsable=unparsable)


if __name__ == "__main__":  # pragma: no cover - CI entry point
    import sys
    # Default roots must match the documented baseline in
    # ragbase/control/no-silent-degradation/README.md (11 findings). Scanning only
    # two sub-packages under-reported by 6 (all of services/), so a CI run on the
    # default would have gone green while services/mcp/server.py still carried L2s.
    targets = sys.argv[1:] or ["packages", "services"]
    results, cov = check_paths(targets, with_coverage=True)  # type: ignore[arg-type]
    for f in results:
        print(f)
    by_rule: dict[str, int] = {}
    for f in results:
        by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
    print(f"\n{len(results)} finding(s): " +
          ", ".join(f"{k}={v}" for k, v in sorted(by_rule.items())))
    # Coverage is printed unconditionally, next to the count it qualifies.
    print(f"coverage: roots={cov.roots} files_scanned={cov.files_scanned} "
          f"files_skipped={cov.files_skipped}")
    if cov.missing_roots or cov.unparsable:
        print(f"COVERAGE GAP: missing_roots={cov.missing_roots} "
              f"unparsable={cov.unparsable}")
        sys.exit(2)
