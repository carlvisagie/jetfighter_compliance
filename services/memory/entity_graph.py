"""Canonical entity graph — single source of linked identities."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from ..defensive_wiring import safe_write_text

from ..config import DATA

MEMORY_DIR = DATA / "memory"
ENTITIES_FILE = "entities.jsonl"


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def memory_dir(base: Optional[Path] = None) -> Path:
    d = base or MEMORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def normalize_company(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def email_domain(email: str) -> str:
    e = (email or "").strip().lower()
    return e.split("@", 1)[1] if "@" in e else ""


def _entities_path(base: Optional[Path] = None) -> Path:
    return memory_dir(base) / ENTITIES_FILE


def load_entities(base: Optional[Path] = None, *, limit: int = 5000) -> List[Dict[str, Any]]:
    from ..lazy_io import load_jsonl

    path = _entities_path(base)
    if not path.exists():
        return []
    return load_jsonl(path, limit=limit)


def build_indexes(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_id: Dict[str, Dict[str, Any]] = {}
    by_company: Dict[str, str] = {}
    by_domain: Dict[str, str] = {}
    by_ref: Dict[str, str] = {}
    for ent in entities:
        eid = ent.get("entity_id", "")
        by_id[eid] = ent
        cn = ent.get("company_norm") or ""
        if cn:
            by_company[cn] = eid
        dom = ent.get("email_domain") or ""
        if dom:
            by_domain[dom] = eid
        for link in ent.get("refs") or []:
            key = f"{link.get('ref_type')}:{link.get('ref_id')}"
            by_ref[key] = eid
    return {"by_id": by_id, "by_company": by_company, "by_domain": by_domain, "by_ref": by_ref}


def find_entity_id(
    *,
    email: str = "",
    company: str = "",
    lead_id: str = "",
    project_id: str = "",
    base: Optional[Path] = None,
) -> Optional[str]:
    entities = load_entities(base)
    idx = build_indexes(entities)
    for ref_type, ref_id in (
        ("lead", lead_id),
        ("project", project_id),
    ):
        if ref_id:
            hit = idx["by_ref"].get(f"{ref_type}:{ref_id}")
            if hit:
                return hit
    em = (email or "").strip().lower()
    if em:
        hit = idx["by_ref"].get(f"email:{em}")
        if hit:
            return hit
    dom = email_domain(email)
    if dom and dom in idx["by_domain"]:
        return idx["by_domain"][dom]
    cn = normalize_company(company)
    if cn and cn in idx["by_company"]:
        return idx["by_company"][cn]
    return None


def next_entity_id(entities: List[Dict[str, Any]], slug: str) -> str:
    prefix = f"E-{slug[:24]}-"
    nums = []
    for e in entities:
        eid = e.get("entity_id", "")
        if eid.startswith(prefix):
            try:
                nums.append(int(eid.rsplit("-", 1)[-1]))
            except ValueError:
                pass
    n = max(nums) + 1 if nums else 1
    return f"{prefix}{n:04d}"


def append_entity(entity: Dict[str, Any], base: Optional[Path] = None) -> Dict[str, Any]:
    path = _entities_path(base)
    memory_dir(base)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entity, ensure_ascii=False) + "\n")
    return entity


def compact_entities(
    base: Optional[Path] = None, *, keep_last_per_entity: bool = True
) -> Dict[str, Any]:
    """Rewrite `entities.jsonl` keeping one row per entity_id.

    Forensic-audit fix (2026-06-04, Central Memory): every upsert
    appends a full new row, so the entity graph accumulates many
    redundant snapshots of the same entity. Read code already dedupes
    (build_indexes() keeps the last row per id), but the file size
    grows without bound and the operator sees "7k rows for 200 real
    entities" — looks like a bug under inspection.

    This function performs an atomic compaction: load all rows, group
    by entity_id, keep the last one per group, and replace the file
    via a temp swap so we never lose the source of truth mid-write.
    Returns a small accounting payload for telemetry / operator
    visibility.
    """
    path = _entities_path(base)
    if not path.is_file():
        return {
            "ok": True,
            "rows_before": 0,
            "rows_after":  0,
            "rows_removed": 0,
            "entities_kept": 0,
            "compacted": False,
        }
    rows_before = 0
    last_by_id: Dict[str, Dict[str, Any]] = {}
    other_rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows_before += 1
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            eid = (row or {}).get("entity_id")
            if not eid:
                # Preserve rows without an entity_id rather than
                # silently dropping them.
                other_rows.append(row)
                continue
            if keep_last_per_entity:
                last_by_id[eid] = row
            else:
                other_rows.append(row)

        kept_rows = list(last_by_id.values()) + other_rows
        rows_after = len(kept_rows)
        if rows_after == rows_before:
            return {
                "ok": True,
                "rows_before": rows_before,
                "rows_after":  rows_after,
                "rows_removed": 0,
                "entities_kept": len(last_by_id),
                "compacted": False,
            }
        # Atomic swap.
        tmp = path.with_suffix(path.suffix + ".compact.tmp")
        tmp.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in kept_rows)
            + ("\n" if kept_rows else ""),
            encoding="utf-8",
        )
        tmp.replace(path)
        return {
            "ok": True,
            "rows_before": rows_before,
            "rows_after":  rows_after,
            "rows_removed": rows_before - rows_after,
            "entities_kept": len(last_by_id),
            "compacted": True,
        }
    except OSError as exc:
        return {"ok": False, "error": str(exc),
                "rows_before": rows_before, "rows_after": rows_before}


def upsert_entity(
    *,
    email: str = "",
    company: str = "",
    contact_name: str = "",
    display_name: str = "",
    base: Optional[Path] = None,
) -> Tuple[str, bool]:
    """Return (entity_id, created)."""
    entities = load_entities(base)
    existing_id = find_entity_id(email=email, company=company, base=base)
    dom = email_domain(email)
    cn = normalize_company(company)
    slug = cn or dom or "org"
    if existing_id:
        ent = get_entity(existing_id, base)
        if ent:
            ent = dict(ent)
            ent["updated_utc"] = utc_now()
            if company and not ent.get("company_norm"):
                ent["company_norm"] = cn
            if dom and not ent.get("email_domain"):
                ent["email_domain"] = dom
            if contact_name and not ent.get("contact_name"):
                ent["contact_name"] = contact_name
            if display_name:
                ent["display_name"] = display_name
            ent.setdefault("refs", list(ent.get("refs") or []))
            append_entity(ent, base)
        return existing_id, False

    eid = next_entity_id(entities, slug)
    ent = {
        "entity_id": eid,
        "entity_type": "organization",
        "display_name": display_name or company or dom or eid,
        "company_norm": cn,
        "email_domain": dom,
        "contact_name": contact_name,
        "refs": [],
        "created_utc": utc_now(),
        "updated_utc": utc_now(),
    }
    append_entity(ent, base)
    return eid, True


def add_ref(entity_id: str, ref_type: str, ref_id: str, base: Optional[Path] = None) -> None:
    if not ref_type or not ref_id:
        return
    ent = get_entity(entity_id, base)
    if not ent:
        return
    ent = dict(ent)
    refs = list(ent.get("refs") or [])
    key = f"{ref_type}:{ref_id}"
    if not any(f"{r.get('ref_type')}:{r.get('ref_id')}" == key for r in refs):
        refs.append({"ref_type": ref_type, "ref_id": ref_id, "linked_utc": utc_now()})
    ent["refs"] = refs
    ent["updated_utc"] = utc_now()
    append_entity(ent, base)


def add_refs(
    entity_id: str,
    refs: List[Tuple[str, str]],
    base: Optional[Path] = None,
) -> None:
    """Attach multiple refs in one entity snapshot (project, lead, inquiry, email, …)."""
    for ref_type, ref_id in refs:
        add_ref(entity_id, ref_type, ref_id, base)


def get_entity(entity_id: str, base: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    for e in reversed(load_entities(base)):
        if e.get("entity_id") == entity_id:
            return e
    return None
