"""Platform etiquette — anti-spam, anti-bot patterns."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

SPAM_PATTERNS: List[str] = [
    r"\bclick here\b",
    r"\blimited time\b",
    r"\bact now\b",
    r"\bdm me\b",
    r"\bbook a call\b",
    r"\bschedule a demo\b",
    r"\bour (amazing|best) (tool|service|platform)\b",
    r"\bsign up now\b",
    r"\bguaranteed (certification|compliance)\b",
    r"\bwww\.\S+",
]

REPETITIVE_OPENERS = (
    "check out our",
    "we offer",
    "our platform",
    "as a customer i used",
)


def validate_reply(text: str) -> Dict[str, Any]:
    issues: List[str] = []
    blob = (text or "").lower()
    for pat in SPAM_PATTERNS:
        if re.search(pat, blob, re.I):
            issues.append(f"spam_pattern:{pat}")
    for opener in REPETITIVE_OPENERS:
        if opener in blob:
            issues.append(f"marketing_opener:{opener}")
    if blob.count("http") > 1:
        issues.append("multiple_links")
    return {"ok": len(issues) == 0, "issues": issues}


def sanitize_reply(text: str, fallback: str) -> str:
    result = validate_reply(text)
    if result["ok"]:
        return text
    return fallback
