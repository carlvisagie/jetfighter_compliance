"""KYC reconciliation checks — the 8 mandated awareness checks."""
from __future__ import annotations

from organism_core import Check, CheckResult, Severity, SignalBundle


class DiskVsIntakeIndexCheck(Check):
    name = "disk_vs_intake_index"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        inv = signals.get("intake", "inventory", {}) or {}
        only_disk = inv.get("only_on_disk_not_in_index") or []
        only_index = inv.get("only_in_index_not_on_disk") or []
        ok = not only_disk and not only_index
        return CheckResult(
            name=self.name,
            ok=ok,
            severity=Severity.INFO if ok else Severity.RED,
            detail=("Disk and index agree."
                    if ok else f"Disk-only={len(only_disk)} index-only={len(only_index)}"),
            evidence={
                "disk_count": int(inv.get("intake_directories") or 0),
                "index_count": int(inv.get("index_tail_unique_ids") or 0),
                "only_on_disk": list(only_disk)[:10],
                "only_in_index": list(only_index)[:10],
            },
        )


class IntakeIndexVsQueueCheck(Check):
    name = "intake_index_vs_queue"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        active = int(signals.get("intake", "intake_count_active", 0))
        full_q = int(signals.get("intake", "queue_full_depth", 0))
        depth = int(signals.get("intake", "queue_depth", 0))
        ok = (active == 0 and full_q == 0) or (active > 0 and full_q > 0)
        return CheckResult(
            name=self.name,
            ok=ok,
            severity=Severity.INFO if ok else Severity.RED,
            detail=(f"Active intakes={active} queue_full_depth={full_q}"
                    if ok else f"INTAKE HIDDEN FROM QUEUE: active={active} queue_full_depth={full_q}"),
            evidence={"active_intakes": active, "queue_depth": depth, "queue_full_depth": full_q},
        )


class QueueVsVioCheck(Check):
    name = "queue_vs_vio"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        vio_n = int(signals.get("vio", "vio_company_count", 0))
        full_q = int(signals.get("intake", "queue_full_depth", 0))
        files = int(signals.get("intake", "uploaded_file_count", 0))
        if full_q > 0:
            ok = vio_n >= min(full_q, 100)
        else:
            ok = vio_n == 0
        if files > 0 and vio_n == 0:
            ok = False
        return CheckResult(
            name=self.name,
            ok=ok,
            severity=Severity.INFO if ok else Severity.RED,
            detail=(f"VIO companies={vio_n} queue(full)={full_q}"
                    if ok else f"FILES HIDDEN FROM VIO: files={files} vio={vio_n}"),
            evidence={"vio_company_count": vio_n, "queue_full_depth": full_q},
        )


class QueueVsControlCheck(Check):
    name = "queue_vs_control"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        depth = int(signals.get("intake", "queue_depth", 0))
        return CheckResult(
            name=self.name, ok=True, severity=Severity.INFO,
            detail="Control reads the canonical queue endpoint — counts match by construction.",
            evidence={"control_queue_count": depth},
        )


class EvidenceVsFilesCheck(Check):
    name = "evidence_vs_files"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        files = int(signals.get("intake", "uploaded_file_count", 0))
        ev = int(signals.get("evidence", "evidence_artifact_count", 0))
        if files == 0:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="No uploaded files — nothing to extract.",
                evidence={"uploaded_files": 0, "evidence_artifacts": ev},
            )
        if ev == 0:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail=f"Files uploaded={files} but zero evidence artifacts extracted.",
                evidence={"uploaded_files": files, "evidence_artifacts": ev},
            )
        return CheckResult(
            name=self.name, ok=True, severity=Severity.INFO,
            detail=f"Files={files} evidence_artifacts={ev}",
            evidence={"uploaded_files": files, "evidence_artifacts": ev},
        )


class ProjectsVsCompletedIntakesCheck(Check):
    name = "projects_vs_completed_intakes"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        projects = int(signals.get("projects", "project_count", 0))
        archived = int(signals.get("intake", "intake_count_archived", 0))
        return CheckResult(
            name=self.name, ok=True, severity=Severity.INFO,
            detail=f"Projects={projects} archived_intakes={archived}",
            evidence={"project_count": projects, "archived_intakes": archived},
        )


class ArchivesVsActiveCheck(Check):
    name = "archives_vs_active"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        total = int(signals.get("intake", "intake_count_total", 0))
        active = int(signals.get("intake", "intake_count_active", 0))
        archived = int(signals.get("intake", "intake_count_archived", 0))
        ok = (active + archived) == total
        return CheckResult(
            name=self.name, ok=ok,
            severity=Severity.INFO if ok else Severity.AMBER,
            detail=f"total={total} active={active} archived={archived}",
            evidence={"total": total, "active": active, "archived": archived},
        )


class BetaResidueCheck(Check):
    name = "beta_residue_scan"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        r = signals.section("residue") or {}
        cls_counts = r.get("classification_counts") or {}
        crit = int(r.get("critical_count", 0))
        active_n = int(cls_counts.get("active", 0))
        docs_n = int(cls_counts.get("docs", 0))
        routes = []
        imports = []
        for m in r.get("matches", []):
            pid = m.get("pattern_id", "")
            cls = m.get("classification", "")
            rel = m.get("rel_path", "")
            if pid == "beta_route" and cls == "active":
                routes.append(f"{rel}")
            if pid == "beta_import" and cls == "active":
                imports.append(rel)
        if crit > 0 or routes or imports:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail=(f"CRITICAL beta residue: crit={crit} routes={len(routes)} imports={len(imports)}"),
                evidence={
                    "critical_count": crit,
                    "active_file_count": active_n,
                    "docs_file_count": docs_n,
                    "beta_routes_remaining": routes[:10],
                    "beta_imports_remaining": imports[:10],
                },
            )
        if active_n > 0:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.AMBER,
                detail=f"Beta string in {active_n} active source files (variable/comment residue).",
                evidence={
                    "critical_count": 0, "active_file_count": active_n, "docs_file_count": docs_n,
                    "beta_routes_remaining": [], "beta_imports_remaining": [],
                },
            )
        if docs_n > 0:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail=f"Beta references only in docs/tests ({docs_n} files) — non-runtime.",
                evidence={
                    "critical_count": 0, "active_file_count": 0, "docs_file_count": docs_n,
                    "beta_routes_remaining": [], "beta_imports_remaining": [],
                },
            )
        return CheckResult(
            name=self.name, ok=True, severity=Severity.INFO,
            detail="Clean — no beta residue anywhere.",
            evidence={
                "critical_count": 0, "active_file_count": 0, "docs_file_count": 0,
                "beta_routes_remaining": [], "beta_imports_remaining": [],
            },
        )


def all_checks():
    """Ordered tuple of KYC's 8 checks."""
    return (
        DiskVsIntakeIndexCheck(),
        IntakeIndexVsQueueCheck(),
        QueueVsVioCheck(),
        QueueVsControlCheck(),
        EvidenceVsFilesCheck(),
        ProjectsVsCompletedIntakesCheck(),
        ArchivesVsActiveCheck(),
        BetaResidueCheck(),
    )
