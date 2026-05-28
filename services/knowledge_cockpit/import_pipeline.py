"""Curated import from legacy encyclopedia sources (explicit path only — not runtime)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import concepts_file
from .migration_audit import run_migration_audit


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:64] or "concept"


def run_import(
    *,
    source_path: Optional[Path] = None,
    dry_run: bool = True,
    max_entries: int = 200,
) -> Dict[str, Any]:
    """
    Import curated framework terms from a legacy HTML encyclopedia file.
    Caller must pass source_path explicitly — production never reads E:\\ or C:\\ paths.
    """
    if source_path is None:
        return {
            "ok": False,
            "error": "source_path required — no default legacy location in runtime",
            "dry_run": dry_run,
        }
    if not source_path.is_file():
        return {"ok": False, "error": f"source not found: {source_path}"}

    html = source_path.read_text(encoding="utf-8", errors="replace")
    # Minimal extraction: data-term="..." blocks with operational text
    pattern = re.compile(
        r'data-term="([^"]+)"[^>]*>.*?<p[^>]*class="[^"]*meaning[^"]*"[^>]*>([^<]+)',
        re.IGNORECASE | re.DOTALL,
    )
    found: List[Dict[str, str]] = []
    for m in pattern.finditer(html):
        term, meaning = m.group(1).strip(), m.group(2).strip()
        if len(meaning) < 40 or "what it is, why it matters, and how to implement" in meaning.lower():
            continue
        found.append({"term": term, "meaning": meaning})
        if len(found) >= max_entries:
            break

    cf = concepts_file()
    existing: Dict[str, Any] = {}
    if cf.is_file():
        existing = json.loads(cf.read_text(encoding="utf-8"))
    concepts: List[Dict[str, Any]] = list(existing.get("concepts") or [])
    ids = {c.get("id") for c in concepts}
    added = 0
    for row in found:
        cid = _slug(row["term"])
        if cid in ids:
            continue
        concepts.append(
            {
                "id": cid,
                "term": row["term"],
                "operational_meaning": row["meaning"],
                "why_it_matters": "Imported curated legacy term — review before production.",
                "tags": ["imported"],
            }
        )
        ids.add(cid)
        added += 1

    result = {
        "ok": True,
        "dry_run": dry_run,
        "source": str(source_path),
        "candidates_scanned": len(found),
        "would_add": added,
        "audit": run_migration_audit(),
    }
    if not dry_run and added:
        existing["concepts"] = concepts
        cf.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        result["written"] = True
    return result
