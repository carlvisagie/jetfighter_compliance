"""Test data purge — safe operator cleanup with protections."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _is_test_intake(intake_id: str) -> bool:
    """Check if intake ID is test data (FB- prefix)."""
    return intake_id.startswith("FB-")


def _detect_customer_intakes() -> List[str]:
    """Detect intakes that look like customer data (non-FB prefix)."""
    from services.intake.storage import list_intake_ids
    
    customer_looking = []
    for iid in list_intake_ids(limit=500):
        if not _is_test_intake(iid):
            customer_looking.append(iid)
    return customer_looking


def _count_customer_data() -> int:
    """Count intakes that appear to be customer data."""
    return len(_detect_customer_intakes())


def _get_purgeable_paths() -> List[Path]:
    """Get paths that are safe to purge (test data only)."""
    from services.config import DATA
    
    data_root = Path(DATA)
    
    return [
        data_root / "intakes",
        data_root / "founding_pilot" / "intakes",
        data_root / "projects",
        data_root / "evidence_intelligence",
        data_root / "external_verification",
        data_root / "cognition",
    ]


def _get_protected_paths() -> List[Path]:
    """Get paths that must never be deleted."""
    from services.config import DATA
    
    data_root = Path(DATA)
    
    return [
        data_root / "compliance_intelligence",
        data_root / "knowledge_cockpit",
        data_root / "memory",
    ]


def _scan_directory_contents(path: Path) -> Dict[str, Any]:
    """Scan directory to report what would be deleted."""
    if not path.exists():
        return {
            "exists": False,
            "file_count": 0,
            "dir_count": 0,
            "size_bytes": 0,
        }
    
    file_count = 0
    dir_count = 0
    size_bytes = 0
    
    try:
        for item in path.rglob("*"):
            if item.is_file():
                file_count += 1
                try:
                    size_bytes += item.stat().st_size
                except OSError:
                    pass
            elif item.is_dir():
                dir_count += 1
    except OSError as e:
        logger.warning(f"Error scanning {path}: {e}")
    
    return {
        "exists": True,
        "file_count": file_count,
        "dir_count": dir_count,
        "size_bytes": size_bytes,
    }


def purge_test_data(
    *,
    dry_run: bool = True,
    confirm: str = "",
) -> Dict[str, Any]:
    """
    Purge all test data from production with safety checks.
    
    Args:
        dry_run: If True, only report what would be deleted (default: True)
        confirm: Must be "DELETE_TEST_DATA" to execute purge
    
    Returns:
        Report of purge operation including safety checks and results
    """
    errors: List[str] = []
    
    # Safety check 1: customer_count = 0
    customer_count = _count_customer_data()
    if customer_count > 0:
        customer_intakes = _detect_customer_intakes()
        return {
            "ok": False,
            "blocked": True,
            "block_reason": "customer_data_detected",
            "customer_count": customer_count,
            "customer_intakes": customer_intakes[:10],
            "error": f"Cannot purge: {customer_count} customer intake(s) detected",
        }
    
    # Safety check 2: all intakes are test (FB- prefix)
    from services.intake.storage import list_intake_ids
    
    all_intakes = list_intake_ids(limit=500)
    non_test_intakes = [iid for iid in all_intakes if not _is_test_intake(iid)]
    
    if non_test_intakes:
        return {
            "ok": False,
            "blocked": True,
            "block_reason": "non_test_intakes_detected",
            "non_test_intakes": non_test_intakes,
            "error": f"Cannot purge: {len(non_test_intakes)} non-test intake(s) detected",
        }
    
    # Get paths
    purgeable = _get_purgeable_paths()
    protected = _get_protected_paths()
    
    # Scan what would be deleted
    deleted_scan = {}
    for path in purgeable:
        scan = _scan_directory_contents(path)
        deleted_scan[str(path)] = scan
    
    # Scan what is protected
    preserved_scan = {}
    for path in protected:
        scan = _scan_directory_contents(path)
        preserved_scan[str(path)] = scan
    
    # Calculate totals
    total_files = sum(s["file_count"] for s in deleted_scan.values())
    total_dirs = sum(s["dir_count"] for s in deleted_scan.values())
    total_bytes = sum(s["size_bytes"] for s in deleted_scan.values())
    
    # Dry run mode - report only
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would_delete": deleted_scan,
            "would_preserve": preserved_scan,
            "total_files_to_delete": total_files,
            "total_dirs_to_delete": total_dirs,
            "total_bytes_to_delete": total_bytes,
            "customer_count": 0,
            "intake_count": len(all_intakes),
            "message": "Dry run - nothing deleted. Use dry_run=false&confirm=DELETE_TEST_DATA to execute.",
        }
    
    # Write mode - require confirmation
    if confirm != "DELETE_TEST_DATA":
        return {
            "ok": False,
            "blocked": True,
            "block_reason": "missing_confirmation",
            "error": "Write mode requires confirm=DELETE_TEST_DATA",
            "dry_run": False,
        }
    
    # Execute purge
    deleted_paths: List[str] = []
    deleted_counts = {
        "intakes": 0,
        "projects": 0,
        "evidence_intelligence": 0,
        "external_verification": 0,
        "cognition": 0,
    }
    
    for path in purgeable:
        if not path.exists():
            continue
        
        try:
            # Count items before deletion
            item_count = len(list(path.iterdir())) if path.is_dir() else 0
            
            # Delete contents (not the directory itself)
            for item in path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            
            deleted_paths.append(str(path))
            
            # Update counts by path type
            if "intakes" in path.name:
                deleted_counts["intakes"] += item_count
            elif "projects" in path.name:
                deleted_counts["projects"] += item_count
            elif "evidence_intelligence" in path.name:
                deleted_counts["evidence_intelligence"] += item_count
            elif "external_verification" in path.name:
                deleted_counts["external_verification"] += item_count
            elif "cognition" in path.name:
                deleted_counts["cognition"] += item_count
            
            logger.info(f"Purged test data: {path} ({item_count} items)")
        except Exception as e:
            error_msg = f"Failed to purge {path}: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    # Rebuild indexes
    try:
        from services.intake.storage import sync_index_from_filesystem
        sync_index_from_filesystem(max_rows=200)
        logger.info("Rebuilt intake indexes after purge")
    except Exception as e:
        error_msg = f"Failed to rebuild indexes: {e}"
        errors.append(error_msg)
        logger.error(error_msg)
    
    # Verify inventory agreement
    inventory_ok = False
    try:
        from services.intake.inventory import verify_inventory_agreement
        agreement = verify_inventory_agreement()
        inventory_ok = bool(agreement.get("ok"))
        logger.info(f"Verified inventory agreement: {inventory_ok}")
    except Exception as e:
        error_msg = f"Failed to verify inventory: {e}"
        errors.append(error_msg)
        logger.error(error_msg)
    
    # Recompute organism state
    organism_state: Dict[str, Any] = {}
    try:
        from organism_core import compute_organism_state
        state = compute_organism_state()
        organism_state = {
            "health_state": state.health_state,
            "current_bottleneck": state.current_bottleneck,
        }
        logger.info(f"Recomputed organism state: {organism_state}")
    except Exception as e:
        error_msg = f"Failed to recompute organism: {e}"
        errors.append(error_msg)
        logger.error(error_msg)
    
    # Get final counts
    from services.intake.storage import intake_diagnostics
    from services.intake.queue import get_operator_review_queue
    
    diag = intake_diagnostics()
    queue = get_operator_review_queue(limit=10)
    
    return {
        "ok": len(errors) == 0,
        "dry_run": False,
        "executed": True,
        "deleted_paths": deleted_paths,
        "deleted_counts": deleted_counts,
        "preserved_paths": [str(p) for p in protected],
        "project_count": deleted_counts.get("projects", 0),
        "intake_count": diag.get("intake_directories", 0),
        "evidence_count": deleted_counts.get("evidence_intelligence", 0),
        "external_verification_count": deleted_counts.get("external_verification", 0),
        "queue_depth": queue.get("queue_depth", 0),
        "health_state": organism_state.get("health_state"),
        "current_bottleneck": organism_state.get("current_bottleneck"),
        "inventory_ok": inventory_ok,
        "errors": errors,
        "total_files_deleted": total_files,
        "total_bytes_deleted": total_bytes,
    }
