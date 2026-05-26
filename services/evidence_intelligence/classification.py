"""Rule-based document classification."""
from __future__ import annotations

import re
from typing import List, Tuple

from .schemas import ClassificationResult, DocumentType

RULES: List[Tuple[DocumentType, List[str], float]] = [
    ("mfa_evidence", ["multi-factor", "mfa", "2fa", "authenticator", "two-factor"], 0.85),
    ("training_record", ["training completed", "awareness training", "knowbe4", "phishing simulation"], 0.82),
    ("vulnerability_report", ["vulnerability scan", "nessus", "qualys", "cve-", "penetration test"], 0.8),
    ("asset_inventory", ["asset inventory", "device inventory", "hardware inventory"], 0.8),
    ("backup_evidence", ["backup", "restore test", "recovery test", "retention policy"], 0.78),
    ("incident_response", ["incident response", "ir plan", "security incident"], 0.78),
    ("access_control_evidence", ["access control", "user access review", "privileged access"], 0.76),
    ("vendor_document", ["vendor management", "supplier security", "third-party"], 0.75),
    ("ssp", ["system security plan", " ssp", "security plan"], 0.8),
    ("poam", ["plan of action", "poa&m", "poam", "remediation plan"], 0.8),
    ("policy", ["policy", "information security policy", "acceptable use"], 0.72),
    ("procedure", ["procedure", "standard operating", "work instruction"], 0.7),
    ("contract", ["master service agreement", "statement of work", "contract", "nda"], 0.68),
    ("invoice_or_receipt", ["invoice", "receipt", "purchase order"], 0.65),
    ("system_diagram", ["network diagram", "architecture diagram", "topology"], 0.7),
]


def classify_document(text: str, filename: str) -> ClassificationResult:
    blob = f"{filename}\n{text}".lower()
    best_type: DocumentType = "unknown"
    best_score = 0.0
    signals: List[str] = []

    if re.search(r"\.(png|jpg|jpeg|gif|webp)$", filename.lower()):
        if any(k in blob for k in ("mfa", "2fa", "authenticator", "login", "security settings")):
            return ClassificationResult(
                document_type="screenshot",
                confidence=0.75,
                source_file=filename,
                signals=["image_extension", "mfa_context"],
            )

    for doc_type, keywords, base_conf in RULES:
        hits = [k for k in keywords if k in blob]
        if not hits:
            continue
        score = min(0.98, base_conf + 0.03 * min(len(hits), 3))
        if score > best_score:
            best_score = score
            best_type = doc_type
            signals = hits[:5]

    if best_type == "unknown" and filename:
        fn = filename.lower()
        if "policy" in fn:
            best_type, best_score, signals = "policy", 0.6, ["filename_policy"]
        elif "training" in fn:
            best_type, best_score, signals = "training_record", 0.6, ["filename_training"]
        elif "mfa" in fn or "2fa" in fn:
            best_type, best_score, signals = "mfa_evidence", 0.65, ["filename_mfa"]

    return ClassificationResult(
        document_type=best_type,
        confidence=best_score,
        source_file=filename,
        signals=signals,
    )
