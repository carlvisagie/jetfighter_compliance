"""KYC reconciliation checks — the 8 mandated awareness checks."""
from __future__ import annotations

from organism_core import Check, CheckResult, Severity, SignalBundle
from services.compliance_health.organism_check import ComplianceHealthCoverageCheck


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
    """Compare the operator-control queue count against the canonical
    intake queue depth (separate signal sources).

    Forensic-audit fix (2026-06-04): the previous implementation
    returned ok=True unconditionally on the grounds that both sides
    "match by construction." That was a hardcoded-green vanity check
    and is a real first-customer trust embarrassment when surfaced in
    the operator cockpit. The control count is now read separately
    from the operator-cockpit collector signal; the check stays silent
    only when the cockpit signal is genuinely absent.
    """

    name = "queue_vs_control"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        depth = int(signals.get("intake", "queue_depth", 0))
        control = signals.get("operator_cockpit", "queue_count", None)
        if control is None:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="No operator cockpit signal - skipped.",
                evidence={"canonical_queue_depth": depth,
                          "control_queue_count": None},
            )
        control_n = int(control)
        ok = control_n == depth
        return CheckResult(
            name=self.name,
            ok=ok,
            severity=Severity.INFO if ok else Severity.AMBER,
            detail=(f"Control={control_n} canonical={depth}"
                    if ok else
                    f"DIVERGENCE: operator-cockpit queue={control_n} "
                    f"vs canonical queue={depth}"),
            evidence={"canonical_queue_depth": depth,
                      "control_queue_count": control_n,
                      "delta": control_n - depth},
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
        subjects = int(signals.get("evidence", "evidence_subject_count", 0))
        if ev == 0:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail=(
                    f"Files uploaded={files} but zero evidence artifacts extracted "
                    f"(evidence_subjects_scanned={subjects})."
                ),
                evidence={
                    "uploaded_files": files,
                    "evidence_artifacts": ev,
                    "evidence_subjects_scanned": subjects,
                },
            )
        return CheckResult(
            name=self.name, ok=True, severity=Severity.INFO,
            detail=(
                f"Received {files} files; {ev} evidence artifacts across "
                f"{subjects} subject(s)."
            ),
            evidence={
                "uploaded_files": files,
                "evidence_artifacts": ev,
                "evidence_subjects_scanned": subjects,
            },
        )


class ProjectsVsCompletedIntakesCheck(Check):
    """Reality check: completed intakes should produce kickoff projects.

    Forensic-audit fix (2026-06-04): the previous implementation
    returned ok=True unconditionally — hardcoded-green vanity. Now
    flags AMBER when archived intakes exist but no projects do, and
    RED when many archived intakes are missing project artifacts (more
    than a 10% gap), which is a real "kickoff stopped firing" signal.

    Stays INFO when there's no archived intake to compare against; we
    don't punish a quiet day.
    """

    name = "projects_vs_completed_intakes"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        projects = int(signals.get("projects", "project_count", 0))
        archived = int(signals.get("intake", "intake_count_archived", 0))
        if archived == 0:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="No archived intakes yet — nothing to verify.",
                evidence={"project_count": projects, "archived_intakes": 0},
            )
        deficit = archived - projects
        if deficit <= 0:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail=(f"Projects={projects} cover archived "
                        f"intakes={archived}"),
                evidence={"project_count": projects,
                          "archived_intakes": archived,
                          "deficit": deficit},
            )
        sev = (Severity.RED if deficit > max(1, archived * 0.10)
                              else Severity.AMBER)
        return CheckResult(
            name=self.name, ok=False, severity=sev,
            detail=(f"KICKOFF DEFICIT: archived={archived} but only "
                    f"{projects} project(s) - deficit={deficit}"),
            evidence={"project_count": projects,
                      "archived_intakes": archived,
                      "deficit": deficit},
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


class DiskPersistenceCheck(Check):
    """
    Surfaces the disk-substrate verdict from DiskPersistenceCollector as a
    first-class organism check.

    States → Severity:
      verified_persistent      → INFO  (disk survived a restart — trusted)
      pending_first_restart    → AMBER (first boot of a fresh disk;
                                        provable only after next restart)
      ephemeral_lost           → RED   (marker disappeared between boots —
                                        likely customer data loss event)
      unconfigured             → RED   (no disk substrate to verify)
      write_failed             → RED   (marker write raised OSError)
    """

    name = "disk_persistence_check"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        s = signals.section("disk_persistence") or {}
        raw_state = s.get("state")
        # No collector ran (legacy test paths or partial signal bundles):
        # the check has no evidence to act on, so it must stay silent.
        if not raw_state:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="Disk persistence not probed in this signal bundle.",
                evidence={"state": "not_probed"},
            )
        state = str(raw_state).lower()
        evidence = {
            "state": state,
            "verified": bool(s.get("verified")),
            "marker_birth_utc": s.get("marker_birth_utc"),
            "marker_birth_disk_id": s.get("marker_birth_disk_id"),
            "age_before_process_seconds": s.get("age_before_process_seconds"),
            "process_started_utc": s.get("process_started_utc"),
            "marker_path": s.get("marker_path"),
        }
        if state == "verified_persistent":
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="Disk birth marker survived a restart - substrate is persistent.",
                evidence=evidence,
            )
        if state == "pending_first_restart":
            return CheckResult(
                name=self.name, ok=True, severity=Severity.AMBER,
                detail="First boot on this disk — persistence will be confirmed after the next restart.",
                evidence=evidence,
            )
        if state == "ephemeral_lost":
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail=(
                    "DISK PERSISTENCE LOST — birth marker missing on this boot. "
                    "Previous customer data was likely destroyed. SEV-1 incident logged."
                ),
                evidence=evidence,
            )
        if state == "write_failed":
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail="Disk birth marker write failed — storage is unwritable.",
                evidence=evidence,
            )
        if state == "unconfigured":
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail="No durable disk configured (KYC_DATA unset or invalid).",
                evidence=evidence,
            )
        return CheckResult(
            name=self.name, ok=False, severity=Severity.AMBER,
            detail=f"Disk persistence state unrecognised: {state!r}",
            evidence=evidence,
        )


class LegacyLanguageCheck(Check):
    name = "legacy_language_scan"

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
            if pid == "legacy_route" and cls == "active":
                routes.append(f"{rel}")
            if pid == "legacy_import" and cls == "active":
                imports.append(rel)
        if crit > 0 or routes or imports:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail=(f"CRITICAL legacy residue: crit={crit} routes={len(routes)} imports={len(imports)}"),
                evidence={
                    "critical_count": crit,
                    "active_file_count": active_n,
                    "docs_file_count": docs_n,
                    "legacy_routes_remaining": routes[:10],
                    "legacy_imports_remaining": imports[:10],
                },
            )
        if active_n > 0:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.AMBER,
                detail=f"Legacy string in {active_n} active source files (variable/comment residue).",
                evidence={
                    "critical_count": 0, "active_file_count": active_n, "docs_file_count": docs_n,
                    "legacy_routes_remaining": [], "legacy_imports_remaining": [],
                },
            )
        if docs_n > 0:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail=f"Legacy references only in docs/tests ({docs_n} files) - non-runtime.",
                evidence={
                    "critical_count": 0, "active_file_count": 0, "docs_file_count": docs_n,
                    "legacy_routes_remaining": [], "legacy_imports_remaining": [],
                },
            )
        return CheckResult(
            name=self.name, ok=True, severity=Severity.INFO,
            detail="Clean — no legacy residue anywhere.",
            evidence={
                "critical_count": 0, "active_file_count": 0, "docs_file_count": 0,
                "legacy_routes_remaining": [], "legacy_imports_remaining": [],
            },
        )


class UnconfirmedPaymentsCheck(Check):
    """Awareness check: payment-link → payment-confirmed loop.

    Forensic-audit fix (2026-06-04, Revenue Pipeline): with no PayPal
    webhook, customers can pay and the system stays silent until an
    operator manually confirms via `confirm_payment_received`. The
    UnconfirmedPaymentsCollector quantifies how many links are
    waiting past the SLA; this check escalates accordingly.

    Severity ladder:
      ok        → no breached links
      AMBER     → ≤ 2 breached links (operator should follow up)
      RED       → ≥ 3 breached links OR any link aged > 2x SLA
    """

    name = "unconfirmed_payments"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        section = signals.section("unconfirmed_payments") or {}
        if not section:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="No unconfirmed-payments signal available.",
                evidence={},
            )
        breached = int(section.get("links_breached") or 0)
        pending  = int(section.get("links_pending") or 0)
        sla_h    = int(section.get("sla_hours") or 0)
        samples  = section.get("samples") or []
        max_age_h = max(
            [float((s or {}).get("age_hours") or 0) for s in samples],
            default=0.0,
        )
        if breached == 0:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail=(f"Pending={pending} confirmed={section.get('links_confirmed') or 0}; "
                        f"no payment link past {sla_h}h."),
                evidence=dict(section),
            )
        if breached >= 3 or max_age_h > 2 * sla_h:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail=(f"PAYMENT LOOP STALLED: {breached} payment "
                        f"link(s) older than {sla_h}h; oldest "
                        f"{max_age_h:.1f}h. Confirm via "
                        f"operator/intake/<id>/payment/confirm."),
                evidence=dict(section),
            )
        return CheckResult(
            name=self.name, ok=False, severity=Severity.AMBER,
            detail=(f"{breached} payment link(s) past {sla_h}h SLA — "
                    f"operator follow-up needed."),
            evidence=dict(section),
        )


class SchedulerHeartbeatCheck(Check):
    """Awareness check: the background scheduler is alive and ticking.

    Forensic-audit fix (2026-06-04, Organism Awareness): a starved
    scheduler used to be invisible to the awareness layer. Now any
    scheduler signal absence or stale heartbeat surfaces as AMBER/RED
    so the operator notices before customers do.

    Stays INFO when the heartbeat signal is unavailable (legacy paths
    or fresh boots before telemetry rolls in) so we don't false-alarm.
    """

    name = "scheduler_heartbeat"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        section = signals.section("scheduler_heartbeat") or {}
        if not section.get("available"):
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail=(
                    f"No scheduler heartbeat signal "
                    f"({section.get('reason') or 'no_data'})."
                ),
                evidence=dict(section),
            )
        last_run = section.get("last_organ_run_utc")
        seconds_since = section.get("seconds_since_last_run")
        expected_max = int(section.get(
            "expected_max_interval_seconds") or 0)
        fail_count = int(section.get("recent_failure_count") or 0)

        if last_run is None or seconds_since is None:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.AMBER,
                detail=("Scheduler heartbeat MISSING — no "
                        "scheduler_*_ran rows in recent telemetry."),
                evidence=dict(section),
            )

        if expected_max and int(seconds_since) > expected_max:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail=(f"Scheduler heartbeat STALE — "
                        f"{seconds_since}s since last run "
                        f"(threshold {expected_max}s)."),
                evidence=dict(section),
            )

        if fail_count > 0:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.AMBER,
                detail=(f"Scheduler running but {fail_count} recent "
                        f"failure(s) in telemetry."),
                evidence=dict(section),
            )

        return CheckResult(
            name=self.name, ok=True, severity=Severity.INFO,
            detail=f"Scheduler alive - last run {seconds_since}s ago.",
            evidence=dict(section),
        )


class CognitionValidationCheck(Check):
    name = "cognition_validation_quality"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        section = signals.section("cognition_validation") or {}
        if not section.get("available"):
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="No cognition validation data available.",
                evidence=dict(section),
            )
            
        checked = int(section.get("projects_checked", 0))
        safety = int(section.get("projects_with_safety_warnings", 0))
        malformed = int(section.get("malformed_reports", 0))
        gen_no_val = int(section.get("generated_without_validation", 0))
        human_rev = int(section.get("projects_with_human_review", 0))
        conf = float(section.get("avg_confidence", 0.0))
        blocker_projects = section.get("blocker_projects", []) or []
        
        # PATCH PRODUCTION-ONLY-2: Include classification data in evidence
        evidence = dict(section)
        evidence["blocker_projects"] = blocker_projects
        
        # Count blockers by classification
        real_blockers = [p for p in blocker_projects if p.get("real_customer")]
        test_blockers = [p for p in blocker_projects if not p.get("real_customer")]
        evidence["real_blocker_count"] = len(real_blockers)
        evidence["test_blocker_count"] = len(test_blockers)
        
        if checked == 0 and not malformed and not gen_no_val:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="No projects with cognition validation reports yet.",
                evidence=evidence,
            )

        if safety > 0 or malformed > 0 or gen_no_val > 0 or (checked > 0 and conf < 0.50):
            if safety > 0 or malformed > 0:
                detail = f"Cognition validation RED: {safety + malformed} project(s) have safety_warnings or malformed validation output."
            elif gen_no_val > 0:
                detail = f"Cognition validation RED: {gen_no_val} project(s) generated documents without a validation report."
            else:
                detail = f"Cognition validation RED: average confidence {conf:.2f} is below 0.50 threshold."
            
            # Add classification context
            if len(real_blockers) == 0 and len(test_blockers) > 0:
                detail += f" [TEST CONTAMINATION: 0 REAL, {len(test_blockers)} TEST/VALIDATION]"
                
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail=detail,
                evidence=evidence,
            )

        if human_rev > 0:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.AMBER,
                detail=f"Cognition validation requires review: {human_rev} project(s) contain human_review_items.",
                evidence=evidence,
            )

        if conf >= 0.75:
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail=f"Cognition validation healthy: {checked} project(s) checked; 0 safety warnings; average confidence {conf:.2f}.",
                evidence=evidence,
            )

        return CheckResult(
            name=self.name, ok=False, severity=Severity.AMBER,
            detail=f"Cognition validation confidence marginal: average confidence {conf:.2f}.",
            evidence=evidence,
        )


class ComplianceIntelligenceHealthCheck(Check):
    name = "compliance_intelligence_health"

    def evaluate(self, signals: SignalBundle) -> CheckResult:
        section = signals.section("compliance_intelligence_status") or {}
        if not section.get("available"):
            return CheckResult(
                name=self.name, ok=True, severity=Severity.INFO,
                detail="No compliance intelligence data available.",
                evidence=dict(section),
            )
            
        high = int(section.get("high_severity_pending", 0))
        medium = int(section.get("medium_severity_pending", 0))
        stale = int(section.get("sources_stale", 0))
        failed = bool(section.get("failed_compliance_cycle"))
        
        if high > 0 or stale > 0 or failed:
            details = []
            if high > 0: details.append(f"{high} high severity pending")
            if stale > 0: details.append(f"{stale} sources stale")
            if failed: details.append("failed compliance cycle")
            
            return CheckResult(
                name=self.name, ok=False, severity=Severity.RED,
                detail="Compliance intelligence RED: " + ", ".join(details) + ".",
                evidence=dict(section),
            )

        if medium > 0:
            return CheckResult(
                name=self.name, ok=False, severity=Severity.AMBER,
                detail=f"Compliance intelligence AMBER: {medium} medium severity pending.",
                evidence=dict(section),
            )

        return CheckResult(
            name=self.name, ok=True, severity=Severity.INFO,
            detail="Compliance intelligence GREEN: No actionable items pending.",
            evidence=dict(section),
        )


def all_checks():
    """Ordered tuple of KYC's 14 checks."""
    return (
        DiskPersistenceCheck(),
        DiskVsIntakeIndexCheck(),
        IntakeIndexVsQueueCheck(),
        QueueVsVioCheck(),
        QueueVsControlCheck(),
        EvidenceVsFilesCheck(),
        ProjectsVsCompletedIntakesCheck(),
        ArchivesVsActiveCheck(),
        LegacyLanguageCheck(),
        SchedulerHeartbeatCheck(),
        UnconfirmedPaymentsCheck(),
        CognitionValidationCheck(),
        ComplianceIntelligenceHealthCheck(),
        ComplianceHealthCoverageCheck(),
    )
