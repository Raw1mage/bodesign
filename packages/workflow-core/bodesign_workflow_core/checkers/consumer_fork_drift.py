"""control.quality.consumer-fork-drift — 產品 repo 不得長出平台函式的獨立實作。

BR_20260730 §4 沉澱。§A–§L 十二個修復在 2026-07-29 全部落地於平台
`packages/eda-bridge/bodesign_eda_bridge/routing.py`，但一個都沒到產品 repo：
`03.aiguard/C04-Layout/02_build/generated/tools/` 有 22 個檔，其中 6 個與平台函式
一對一重複且凍結在 2026-07-07。實測：

    產品 net2pcb.py  grep -c footprint_lib_unresolved -> 0
    平台 routing.py  grep -c footprint_lib_unresolved -> 2   (§B 修於 1269a20)

那份 fork **仍在活躍路徑上**（`build_c04.sh:46` 呼叫 `pour.py`，還帶
`>/dev/null 2>&1`），且 22 個只有 2 個進版控。`01.openmv` 有同一批 19 個 fork ——
這是架構層缺口的**重複發生**，不是某個 agent 的個別疏失。

## 為何是 lint 而不是「刪掉 fork」

fork 的存在本身是 GUIDE 明文允許的（c04-layout GUIDE:104/:394 稱之為
worked example / reference）。問題不是它存在，而是**沒有任何機制會發現它落後了**。
平台修了一個靜默降級缺陷，產品 repo 繼續跑舊版、繼續靜默丟棄 8 顆 IC，而所有
gate 全綠。這條 lint 就是那個「會發現」的機制。

## 判準句（review 時問這一句就夠）

    產品 repo 裡有沒有一個函式，它的名字對得上平台某個已修復的函式，
    而它的檔案裡沒有那次修復留下的痕跡？

## 與 no_silent_degradation.py 的結構關係

同屬 source-code lint（非 design-IR checker），因此同樣**不註冊進
`build_pilot_registry()`** —— 那張表的語意是「control -> design-IR checker」，
硬塞會逼我們在 `ir_fields` 填假路徑，而那正是這族 control 自己禁止的捏造。
由 CI / 開發期直接呼叫（見檔末 __main__）。

## 為何比對「修復痕跡」而不比對整份原始碼

逐行 diff 對這個問題零用處：fork 本來就該與平台不同（它沒有 MCP 包裝、沒有
worker 分派、參數是 argv 而非 kwargs）。有意義的問題只有一個——**那次修復到了嗎**。
所以判準是「平台某個 sentinel token 在 fork 裡缺席」，sentinel 由已 commit 的修復
自己提供（`footprint_lib_unresolved`、`courtyard_missing`、`plane_layers_applied`
…），不是憑猜。

Sentinel 必須來自**真實 commit**：每一條都標了引入它的 commit sha，
`tests/test_consumer_fork_drift.py` 會用 `git log -S` 驗證那個 token 真的由那個
commit 引入。否則這張表就是又一份會漂移的手抄副本（BR_20260729 V4-c）。
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

# ── platform sentinels ──────────────────────────────────────────────────────
# token -> (引入它的 commit, 該修復在治什麼)
# 新增一條的規矩：token 必須是那次修復**新引入**的字串，且 `git log -S<token>`
# 能指回所標的 commit。test_consumer_fork_drift.py 逐條驗證這件事。
# token -> (引入它的 commit, 擁有它的平台函式, 該修復在治什麼)
#
# **owner 欄位是必要的，不是註解。** 第一版把全部 sentinel 無差別套到每個 fork，於是
# `pour.py` 被報「缺 8/8 修復」，而 `footprint_lib_unresolved` 根本屬於
# `net2pcb_board` —— 11 個 finding 裡真正相關的只有 4 個。那正是本 BR 的 F2 提案被
# 駁回的同一個理由（喊狼 31 次的 gate 會被忽略），我在自己的 checker 裡犯了一次。
# owner 由 `awk '/^def /{f=$2} index($0,tok)'` 從平台原始碼實測得出，非推測。
PLATFORM_SENTINELS: dict[str, tuple[str, str, str]] = {
    "footprint_lib_unresolved": ("1269a20", "net2pcb_board", "§B 靜默丟棄無法解析 footprint 的元件"),
    "dropped_components": ("1269a20", "net2pcb_board", "§B 丟棄清單須回傳給呼叫端"),
    "plane_layers_applied": ("cdbcb02", "net2pcb_board", "§D power plane 是否真的建立"),
    "vias_per_ref": ("58c37cd", "via_in_pad", "§G 逐 ref 回報打了幾個孔"),
    # 以下 sentinel 的 owner 目前**沒有對應的 fork**，保留在表中是為了讓
    # `git log -S` provenance 測試涵蓋全部已落地修復；它們不會套到任何 fork 上。
    "courtyard_missing": ("cdbcb02", "footprint_extent", "§C 退回含絲印 bbox 時必須標記"),
    "implausible_measurement": ("cdbcb02", "placement_preflight", "§C 面積灌水須自報"),
    "passes_limit": ("740ac75", "autoroute_preflight", "§J 須回報有效搜尋預算上限"),
    "router_via_matches_existing": ("b13ae58", "router_via_budget", "§K 授權 via 與既有 via 是否一致"),
}

# fork 檔名 -> 平台函式名。名字必須是平台**真實存在**的 def；
# test_consumer_fork_drift.py 會逐條驗證。第一版寫成 `widen` / `length_match`
# （平台實際叫 `widen_bus_tracks` / `length_match_bus`），於是 AST fallback 把
# 01.openmv 一個完全無關的 local `widen(block, name)` schematic helper 判成 fork ——
# 用一個不存在的基準去指控。錯名不是筆誤，是會產生假紅的缺陷。
KNOWN_FORKS: dict[str, str] = {
    "net2pcb.py": "net2pcb_board",
    "viainpad.py": "via_in_pad",
    "pour.py": "pour_planes",
    "widen.py": "widen_bus_tracks",
    "si_check.py": "si_check",
    "length_match.py": "length_match_bus",
}

_PLATFORM_MODULE = "packages/eda-bridge/bodesign_eda_bridge/routing.py"


@dataclass(frozen=True, slots=True)
class DriftFinding:
    rule: str            # D1 fork-behind | D2 unassessable | D3 silenced-invocation
    path: str
    fork_of: str         # 平台函式名（D2/D3 可為 "-"）
    message: str

    def __str__(self) -> str:
        return f"{self.rule} {self.path} [{self.fork_of}] {self.message}"


@dataclass(slots=True)
class DriftCoverage:
    """掃描實際涵蓋了什麼（比照 no_silent_degradation 的 L10）。

    只回 findings 的 checker 本身就是這族反模式的實例：`0 findings` 時呼叫端
    無法分辨 `clean` 與 `never scanned`。這裡曾真的踩過 —— consumer repo 路徑
    在 Google Drive 掛載上，一個打錯的路徑會安靜地貢獻零 finding。
    """
    roots: list[str]
    missing_roots: list[str]
    sentinels_used: int
    sentinels_absent_from_platform: list[str]
    fork_files_found: int
    files_scanned: int
    # 找到 fork 但沒有屬於該平台函式的 sentinel -> 判不出落後與否。
    # 這是本表的覆蓋缺口，不是對方的缺陷。
    forks_unassessable: list[dict]


def platform_sentinel_state(repo_root: str | Path) -> dict[str, bool]:
    """每個 sentinel 在平台原始碼裡是否真的存在。

    這是這條 lint 的**前提檢查**，不是裝飾。若平台端已經沒有某個 token（重構改名、
    或那條表項本來就寫錯），拿它去掃 fork 只會得到「fork 落後」的假紅 —— 用一個
    不存在的基準去指控別人。所以先驗基準，缺了就在 coverage 裡點名。
    """
    src = Path(repo_root) / _PLATFORM_MODULE
    text = src.read_text(encoding="utf-8") if src.is_file() else ""
    return {tok: (tok in text) for tok in PLATFORM_SENTINELS}


def sentinels_for(platform_fn: str, live: dict[str, tuple[str, str, str]]) -> dict:
    """只回**擁有者就是這個函式**的 sentinel。

    一個 fork 缺少別的函式的修復痕跡不是缺陷 —— 它本來就不該有。無差別套用會把
    1 個真 finding 稀釋成 8 個，呼叫端於是學會忽略整條規則。
    """
    return {tok: meta for tok, meta in live.items() if meta[1] == platform_fn}


def _defined_functions(path: Path) -> set[str]:
    """檔案裡定義的 top-level 函式名（AST，不用正則猜）。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    return {n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _delegates_to_platform(path: Path) -> bool:
    """薄 wrapper（實作 delegate 回平台）不算 fork —— 它不可能凍結。

    這是 BR §6 F4(b) 想要的終局形態，所以必須辨識得出來並放行，否則 lint 會處罰
    正確做法。判準：import 了 bodesign_eda_bridge。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return bool(re.search(r"^\s*(from|import)\s+bodesign_eda_bridge", text, re.M))


def check_consumer_repo(consumer_root: str | Path, *, platform_root: str | Path,
                        with_coverage: bool = False):
    """掃一個 consumer repo，找凍結在修復前的平台函式 fork。

    Returns findings，或 (findings, DriftCoverage) 當 with_coverage。
    """
    croot = Path(consumer_root)
    sentinel_state = platform_sentinel_state(platform_root)
    live = {tok: meta for tok, meta in PLATFORM_SENTINELS.items() if sentinel_state[tok]}

    findings: list[DriftFinding] = []
    missing_roots: list[str] = []
    unassessable: list[dict] = []
    fork_files = 0
    scanned = 0

    if not croot.exists():
        missing_roots.append(str(croot))
        cov = DriftCoverage(
            roots=[str(croot)], missing_roots=missing_roots, sentinels_used=len(live),
            sentinels_absent_from_platform=sorted(t for t, ok in sentinel_state.items() if not ok),
            fork_files_found=0, files_scanned=0, forks_unassessable=[])
        return (findings, cov) if with_coverage else findings

    for path in sorted(croot.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        scanned += 1
        name = path.name
        fork_of = KNOWN_FORKS.get(name)
        if fork_of is None:
            # 檔名沒對上時，用 AST 看有沒有定義同名函式（改名的 fork 也要抓到）。
            defined = _defined_functions(path)
            hit = defined & set(KNOWN_FORKS.values())
            if not hit:
                continue
            fork_of = sorted(hit)[0]

        if _delegates_to_platform(path):
            continue                      # 薄 wrapper，放行

        fork_files += 1
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(DriftFinding("D1", str(path), fork_of, "無法讀取（非 UTF-8）"))
            continue

        applicable = sentinels_for(fork_of, live)
        if not applicable:
            # 沒有任何 sentinel 屬於這個函式 -> 判不出它是否落後。
            # **這是平台 sentinel 表的缺口，不是 consumer repo 的缺陷** —— 記成
            # per-file finding 等於拿我方的不完整去記在對方帳上，而且會把 finding
            # 數灌水（實測 11 筆裡有 4 筆是這種）。歸入 coverage：讓「判不出」可見，
            # 但不冒充判決。"我看不到" 不是 "那裡沒東西"，也不是 "那裡有東西"。
            unassessable.append({"path": str(path), "fork_of": fork_of})
            continue

        behind = [(tok, meta) for tok, meta in applicable.items() if tok not in text]
        if behind:
            detail = "; ".join(f"{tok} ({sha}: {why})" for tok, (sha, _own, why) in
                              ((t, m) for t, m in behind))
            findings.append(DriftFinding(
                "D1", str(path), fork_of,
                f"獨立實作平台 `{fork_of}`，缺少 {len(behind)}/{len(applicable)} 個"
                f"該函式已落地修復的痕跡 — {detail}"))

        if re.search(r">\s*/dev/null\s+2>&1|2>\s*/dev/null", text):
            findings.append(DriftFinding(
                "D3", str(path), fork_of,
                "把輸出導入 /dev/null — fork 的失敗連看都看不到"))

    # build script 層的靜默呼叫（fork 不只被 python import，也被 shell 呼叫）
    for sh in sorted(croot.rglob("*.sh")):
        try:
            text = sh.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line in text.splitlines():
            if not any(f in line for f in KNOWN_FORKS):
                continue
            if re.search(r">\s*/dev/null\s+2>&1|2>\s*/dev/null", line):
                fork = next(f for f in KNOWN_FORKS if f in line)
                findings.append(DriftFinding(
                    "D3", str(sh), KNOWN_FORKS[fork],
                    f"呼叫 {fork} 並丟棄其輸出 — gate 判決建立在看不見的執行上"))

    cov = DriftCoverage(
        roots=[str(croot)], missing_roots=missing_roots, sentinels_used=len(live),
        sentinels_absent_from_platform=sorted(t for t, ok in sentinel_state.items() if not ok),
        fork_files_found=fork_files, files_scanned=scanned,
        forks_unassessable=unassessable)
    return (findings, cov) if with_coverage else findings


if __name__ == "__main__":  # pragma: no cover - CI entry point
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m ...consumer_fork_drift <consumer_root> [platform_root]",
              file=sys.stderr)
        sys.exit(64)
    consumer = sys.argv[1]
    platform = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).parents[4])

    results, cov = check_consumer_repo(consumer, platform_root=platform, with_coverage=True)
    for f in results:
        print(f)
    by_rule: dict[str, int] = {}
    for f in results:
        by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
    print(f"\n{len(results)} finding(s): " +
          ", ".join(f"{k}={v}" for k, v in sorted(by_rule.items())) or "\n0 finding(s)")
    # coverage 與它所限定的計數並排印出，無條件。
    print(f"coverage: roots={cov.roots} files_scanned={cov.files_scanned} "
          f"fork_files={cov.fork_files_found} sentinels_used={cov.sentinels_used}")
    if cov.forks_unassessable:
        print(f"UNASSESSABLE ({len(cov.forks_unassessable)} fork(s) have no sentinel for "
              f"their platform function — add one to cover them):")
        for u in cov.forks_unassessable:
            print(f"  {u['fork_of']:20s} {u['path']}")
    if cov.missing_roots or cov.sentinels_absent_from_platform:
        # 基準本身有缺口時，findings 的意義是可疑的 —— 不得靜默通過。
        print(f"COVERAGE GAP: missing_roots={cov.missing_roots} "
              f"sentinels_absent_from_platform={cov.sentinels_absent_from_platform}")
        sys.exit(2)
    sys.exit(1 if results else 0)
