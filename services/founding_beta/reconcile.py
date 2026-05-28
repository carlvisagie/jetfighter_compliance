"""Fleet reconciliation — disk, index, queue, audit, COTE must agree."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .retention import audit_receipt_path, hash_uploads_on_disk, load_audit_receipt
from .storage import (
    index_intake_ids,
    intake_dir,
    intake_json_path,
    is_pending_review,
    latest_index_row,
    list_intake_ids,
    load_intake_record,
)
from .transactions import intake_commit_complete, load_transaction_log


def reconcile_intake(intake_id: str) -> Dict[str, Any]:
    """Deterministic per-intake truth check."""
    idir = intake_dir(intake_id)
    ij = intake_json_path(intake_id)
    audit_path = audit_receipt_path(intake_id)
    on_disk = hash_uploads_on_disk(intake_id)
    disk_files = len(on_disk)

    record: Dict[str, Any] = {}
    load_err: Optional[str] = None
    try:
        record = load_intake_record(intake_id, persist_recovery=False)
    except Exception as exc:
        load_err = str(exc)

    ui = record.get("upload_integrity") or {}
    expected = int(ui.get("expected_file_count") or 0)
    received = int(ui.get("received_file_count") or 0)
    persisted = int(ui.get("persisted_file_count") or 0)
    verified = int(ui.get("verified_file_count") or 0)
    failed = int(ui.get("failed_file_count") or 0)
    file_count = int(record.get("file_count") or len(record.get("files") or []))

    audit = load_audit_receipt(intake_id)
    index_row = latest_index_row(intake_id)
    tx_log = load_transaction_log(intake_id, tail=100)
    commit_complete = intake_commit_complete(intake_id)

    issues: List[str] = []
    if not idir.is_dir():
        issues.append("intake_dir_missing")
    if disk_files > 0 and not ij.is_file():
        issues.append("files_on_disk_without_intake_json")
    if disk_files > 0 and not audit_path.is_file():
        issues.append("files_on_disk_without_audit_receipt")
    if file_count > 0 and disk_files == 0:
        issues.append("intake_json_claims_files_but_disk_empty")
    if disk_files > 0 and verified > 0 and verified != disk_files:
        issues.append("verified_count_disk_mismatch")
    if expected and received and expected != received:
        issues.append("expected_received_mismatch")
    if persisted and disk_files and persisted != disk_files:
        issues.append("persisted_disk_mismatch")
    if failed > 0 and str(record.get("custody_status") or "").lower() == "verified_complete":
        issues.append("fake_verified_complete_with_failures")
    if disk_files > 0 and not commit_complete:
        issues.append("upload_not_fully_committed")
    if index_row is None and file_count > 0 and ij.is_file():
        issues.append("missing_index_row")
    if index_row and index_row.get("committed") is False:
        issues.append("index_row_uncommitted")
    if load_err:
        issues.append(f"intake_json_load_error:{load_err}")

    queue_visible = False
    try:
        from .queue import get_operator_review_queue

        q = get_operator_review_queue(limit=200)
        queue_visible = intake_id in {r.get("intake_id") for r in q.get("queue") or []}
    except Exception:
        pass

    cote_signal: Dict[str, Any] = {}
    try:
        from .intake import _latest_intake_custody_signal

        cote_signal = _latest_intake_custody_signal()
    except Exception:
        cote_signal = {}

    cote_matches = (
        cote_signal.get("latest_intake_id") != intake_id
        or str(cote_signal.get("latest_custody_status") or "")
        == str(record.get("custody_status") or ui.get("custody_status") or "")
    )

    return {
        "ok": len(issues) == 0,
        "intake_id": intake_id,
        "issues": issues,
        "integrity_failure": len(issues) > 0,
        "disk_file_count": disk_files,
        "intake_json_exists": ij.is_file(),
        "audit_receipt_exists": audit is not None,
        "index_row_exists": index_row is not None,
        "index_committed": bool((index_row or {}).get("committed")),
        "commit_complete": commit_complete,
        "queue_visible": queue_visible,
        "cote_matches_storage": cote_matches,
        "custody_status": record.get("custody_status") or ui.get("custody_status"),
        "count_breakdown": {
            "expected_file_count": expected,
            "received_file_count": received,
            "persisted_file_count": persisted,
            "verified_file_count": verified,
            "failed_file_count": failed,
            "on_disk_file_count": disk_files,
            "intake_json_file_count": file_count,
        },
        "transaction_phases": [r.get("phase") for r in tx_log],
        "pending_review": is_pending_review(record.get("review_status")),
    }


def reconcile_fleet(*, limit: int = 100) -> Dict[str, Any]:
    """Compare disk inventory vs index vs queue vs latest COTE signal."""
    disk_ids = list_intake_ids(limit=limit)
    index_ids = index_intake_ids(tail_lines=max(limit, 500))
    index_set = set(index_ids)

    only_disk = [iid for iid in disk_ids if iid not in index_set]
    only_index = [iid for iid in index_ids if iid not in set(disk_ids)]

    intake_reports: List[Dict[str, Any]] = []
    failing: List[str] = []
    for iid in disk_ids[:limit]:
        rep = reconcile_intake(iid)
        intake_reports.append(rep)
        if rep.get("integrity_failure"):
            failing.append(iid)

    queue_depth = 0
    integrity_mismatch_count = 0
    try:
        from .queue import get_operator_review_queue

        q = get_operator_review_queue(limit=limit)
        queue_depth = int(q.get("queue_depth") or 0)
        integrity_mismatch_count = int(q.get("integrity_mismatch_count") or 0)
    except Exception:
        pass

    cote: Dict[str, Any] = {}
    try:
        from .intake import intake_flow_metrics

        cote = intake_flow_metrics()
    except Exception:
        pass

    fleet_ok = not failing and not only_disk and not only_index
    return {
        "ok": fleet_ok,
        "fleet_integrity_ok": fleet_ok,
        "disk_intake_count": len(disk_ids),
        "index_intake_count": len(index_ids),
        "only_on_disk_not_in_index": only_disk,
        "only_in_index_not_on_disk": only_index,
        "failing_intake_ids": failing,
        "intake_reports": intake_reports[:20],
        "queue_depth": queue_depth,
        "integrity_mismatch_count": integrity_mismatch_count,
        "cote_upload_node_severity": cote.get("upload_node_severity"),
        "cote_pending_review": cote.get("pending_review"),
        "latest_integrity_mismatch": next(
            (r for r in intake_reports if r.get("integrity_failure")),
            None,
        ),
    }
