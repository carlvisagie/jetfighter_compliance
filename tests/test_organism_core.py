"""Generic tests for organism_core — zero KYC imports.

These tests exercise the reusable core with a synthetic "demo" organism
to prove the architecture stands alone and can be plugged into any product.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from organism_core import (
    AwarenessEngine,
    Check,
    CheckResult,
    HealthState,
    LocationRule,
    Pattern,
    RecommendationRegistry,
    ResidueScanner,
    Severity,
    SignalBundle,
    SignalCollector,
    derive_health,
    write_snapshot,
)


# ---------- Health derivation -----------------------------------------------

def test_derive_health_returns_green_when_all_info():
    results = [
        CheckResult("a", ok=True, severity=Severity.INFO, detail="ok"),
        CheckResult("b", ok=True, severity=Severity.INFO, detail="ok"),
    ]
    v = derive_health(results)
    assert v.state is HealthState.GREEN
    assert v.bottleneck == "none"
    assert v.mismatches == []


def test_derive_health_returns_amber_on_amber_check():
    results = [
        CheckResult("a", ok=True, severity=Severity.INFO, detail="ok"),
        CheckResult("b", ok=False, severity=Severity.AMBER, detail="slow"),
        CheckResult("c", ok=True, severity=Severity.INFO, detail="ok"),
    ]
    v = derive_health(results)
    assert v.state is HealthState.AMBER
    assert v.bottleneck == "b"


def test_derive_health_returns_red_on_red_check():
    results = [
        CheckResult("a", ok=True, severity=Severity.INFO, detail="ok"),
        CheckResult("b", ok=False, severity=Severity.AMBER, detail="slow"),
        CheckResult("c", ok=False, severity=Severity.RED, detail="boom"),
    ]
    v = derive_health(results)
    assert v.state is HealthState.RED
    assert v.bottleneck == "c"
    assert set(v.mismatches) == {"b", "c"}


def test_derive_health_gating_failure_forces_red():
    results = [CheckResult("a", ok=True, severity=Severity.INFO, detail="ok")]
    v = derive_health(results, gating_failure=("missing_dep", "need DB"))
    assert v.state is HealthState.RED
    assert v.bottleneck == "missing_dep"


# ---------- Severity coercion ------------------------------------------------

def test_severity_coerces_aliases():
    assert Severity.coerce("critical") is Severity.RED
    assert Severity.coerce("warning") is Severity.AMBER
    assert Severity.coerce("info") is Severity.INFO
    assert Severity.coerce("") is Severity.INFO


# ---------- SignalBundle -----------------------------------------------------

def test_signal_bundle_namespaces_and_lookups():
    b = SignalBundle()
    b.add("alpha", {"x": 1, "y": 2})
    b.add("pilot", {"x": 99})
    assert b.get("alpha", "x") == 1
    assert b.get("pilot", "x") == 99
    assert b.get("missing", "x", default=42) == 42
    assert "alpha.x" in b.flat()
    assert "pilot.x" in b.flat()


# ---------- Collector / Check safe wrappers ---------------------------------

class _BadCollector(SignalCollector):
    name = "bad"

    def collect(self) -> Dict[str, Any]:
        raise RuntimeError("boom")


class _GoodCollector(SignalCollector):
    name = "good"

    def collect(self) -> Dict[str, Any]:
        return {"value": 42}


def test_collector_safe_returns_error_marker_without_raising():
    out = _BadCollector().safe_collect()
    assert "_collector_error" in out


class _BadCheck(Check):
    name = "explosive"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        raise ValueError("nope")


def test_check_safe_returns_amber_without_raising():
    result = _BadCheck().safe_evaluate(SignalBundle())
    assert result.ok is False
    assert result.severity is Severity.AMBER
    assert "explosive" in result.name or "explosive" in result.detail.lower() or result.name == "explosive"


# ---------- Residue scanner --------------------------------------------------

def _setup_demo_tree(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "live.py").write_text("import old_module\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "history.md").write_text("# old_module legacy\n", encoding="utf-8")


def test_residue_scanner_classifies_by_location(tmp_path):
    _setup_demo_tree(tmp_path)
    scanner = ResidueScanner(
        patterns=[Pattern("old_general", r"\bold_module\b")],
        rules=[
            LocationRule("active_src", "active", path_prefixes=["src/"]),
            LocationRule("docs_tree", "docs", path_prefixes=["docs/"]),
        ],
    )
    report = scanner.scan(tmp_path)
    assert report.detected is True
    assert report.classification_counts.get("active", 0) >= 1
    assert report.classification_counts.get("docs", 0) >= 1


def test_residue_scanner_critical_package_existence(tmp_path):
    pkg = tmp_path / "legacy_pkg" / "__init__.py"
    pkg.parent.mkdir(parents=True)
    pkg.write_text("", encoding="utf-8")
    scanner = ResidueScanner(
        patterns=[],
        rules=[],
        critical_packages=["legacy_pkg/__init__.py"],
    )
    report = scanner.scan(tmp_path)
    assert report.detected is True
    assert "legacy_pkg/__init__.py" in report.critical_paths
    assert report.critical_count >= 1


def test_residue_scanner_self_paths_skipped(tmp_path):
    """A scanner can be told to ignore its own source files."""
    (tmp_path / "scanner_itself").mkdir()
    (tmp_path / "scanner_itself" / "x.py").write_text("old_module = 1\n", encoding="utf-8")
    scanner = ResidueScanner(
        patterns=[Pattern("old", r"old_module")],
        rules=[LocationRule("active", "active", path_prefixes=["scanner_itself/"])],
        self_paths=["scanner_itself/"],
    )
    report = scanner.scan(tmp_path)
    assert report.detected is False


# ---------- RecommendationRegistry ------------------------------------------

def test_recommendation_registry_uses_callable_with_evidence():
    reg = RecommendationRegistry()

    def dynamic(r: CheckResult) -> str:
        return f"fix {r.evidence.get('thing', '?')}"

    reg.register("widget", dynamic)
    r = CheckResult("widget", ok=False, severity=Severity.RED, detail="x", evidence={"thing": "bolts"})
    assert reg.action_for_check(r) == "fix bolts"


def test_recommendation_registry_recommend_for_states():
    reg = RecommendationRegistry(
        idle_action="rest",
        active_action="work",
    )
    reg.register("c1", "fix c1")
    reg.register("c2", "fix c2")
    red = CheckResult("c1", ok=False, severity=Severity.RED, detail="")
    amber = CheckResult("c2", ok=False, severity=Severity.AMBER, detail="")
    info = CheckResult("c3", ok=True, severity=Severity.INFO, detail="")
    assert reg.recommend(state=HealthState.RED, results=[info, red]) == "fix c1"
    assert reg.recommend(state=HealthState.AMBER, results=[info, amber]) == "fix c2"
    assert reg.recommend(state=HealthState.GREEN, results=[info], green_workload_indicator=False) == "rest"
    assert reg.recommend(state=HealthState.GREEN, results=[info], green_workload_indicator=True) == "work"


# ---------- AwarenessEngine end-to-end --------------------------------------

class _CountCollector(SignalCollector):
    name = "count"

    def __init__(self, n):
        self._n = n

    def collect(self) -> Dict[str, Any]:
        return {"n": self._n}


class _ThresholdCheck(Check):
    name = "threshold"

    def __init__(self, threshold: int):
        self._t = threshold

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        n = int(signals.get("count", "n", 0))
        ok = n >= self._t
        return CheckResult(
            name=self.name, ok=ok,
            severity=Severity.INFO if ok else Severity.RED,
            detail=f"n={n} threshold={self._t}",
            evidence={"n": n, "threshold": self._t},
        )


def test_engine_assembles_and_returns_snapshot(tmp_path):
    snap_path = tmp_path / "demo_state.json"
    engine = AwarenessEngine(
        organism_name="demo",
        collectors=[_CountCollector(5)],
        checks=[_ThresholdCheck(3)],
        recommendations=RecommendationRegistry().register_many({"threshold": "raise n"}),
        snapshot_path=snap_path,
        metadata={"version": "0.1"},
    )
    snap = engine.snapshot()
    assert snap["organism"] == "demo"
    assert snap["health_state"] == "GREEN"
    assert snap["current_bottleneck"] == "none"
    assert snap["signals"]["count"]["n"] == 5
    assert snap_path.is_file()
    on_disk = json.loads(snap_path.read_text(encoding="utf-8"))
    assert on_disk["organism"] == "demo"


def test_engine_reports_red_when_check_fails(tmp_path):
    engine = AwarenessEngine(
        organism_name="demo",
        collectors=[_CountCollector(1)],
        checks=[_ThresholdCheck(10)],
        recommendations=RecommendationRegistry().register_many({"threshold": "raise n"}),
    )
    snap = engine.snapshot(persist=False)
    assert snap["health_state"] == "RED"
    assert snap["current_bottleneck"] == "threshold"
    assert snap["next_recommended_action"] == "raise n"


def test_engine_gating_forces_red():
    def gate(signals: SignalBundle):
        return ("missing_capability", "demo gating")

    engine = AwarenessEngine(
        organism_name="demo",
        collectors=[_CountCollector(50)],
        checks=[_ThresholdCheck(3)],
        recommendations=RecommendationRegistry(),
        gating=gate,
    )
    snap = engine.snapshot(persist=False)
    assert snap["health_state"] == "RED"
    assert snap["current_bottleneck"] == "missing_capability"


def test_engine_isolates_collector_failures():
    engine = AwarenessEngine(
        organism_name="demo",
        collectors=[_BadCollector(), _GoodCollector()],
        checks=[],
        recommendations=RecommendationRegistry(),
    )
    snap = engine.snapshot(persist=False)
    assert "_collector_error" in snap["signals"]["bad"]
    assert snap["signals"]["good"]["value"] == 42


def test_snapshot_writer_atomic(tmp_path):
    target = tmp_path / "out.json"
    written = write_snapshot({"hello": "world"}, path=target)
    assert written == target
    assert json.loads(target.read_text(encoding="utf-8")) == {"hello": "world"}
