"""
Multi-ecosystem discovery — operational burden humans, not CMMC thread hunting.

Casts a wide discovery net across subreddits and semantic clusters.
Prey / predator / intent filters remain strict downstream.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# --- Discovery ecosystems (subreddit groups) ---
DISCOVERY_ECOSYSTEMS: Dict[str, Tuple[str, ...]] = {
    "government_contracting": (
        "govcontracts",
        "defensecontracting",
        "fednews",
        "federalcontracting",
        "NIST800171",
        "CMMC",
    ),
    "small_business": (
        "smallbusiness",
        "Entrepreneur",
        "startups",
        "manufacturing",
        "logistics",
        "procurement",
    ),
    "it_operations": (
        "sysadmin",
        "msp",
        "cybersecurity",
        "AskNetsec",
        "ITManagers",
        "techsupport",
    ),
    "security_burden": (
        "cybersecurity",
        "smallbusiness",
        "sysadmin",
        "msp",
    ),
}

ECOSYSTEM_ORDER = (
    "government_contracting",
    "small_business",
    "it_operations",
    "security_burden",
)

# --- Semantic discovery clusters (10) ---
CLUSTER_DIRECT_CMMC: Tuple[str, ...] = (
    "CMMC confusion",
    "DFARS confusion",
    "NIST 800-171 help",
    "CMMC level which",
    "SPRS score help",
)

CLUSTER_OPERATIONAL_SECURITY: Tuple[str, ...] = (
    "customer security requirements",
    "cybersecurity requirements small business",
    "security requirements government contract",
    "IT compliance",
    "security controls small business",
    "security assessment help",
    "customer audit security",
    "what applies to us",
    "do we actually need this",
    "where do we start compliance",
    "operational uncertainty CMMC",
    "implementation confusion security",
)

CLUSTER_VENDOR_PRESSURE: Tuple[str, ...] = (
    "vendor questionnaire",
    "vendor onboarding security",
    "vendor assessment requirements",
    "prime contractor asked us",
    "prime contractor sent questionnaire",
    "prime contractor requested",
    "customer asked for security",
    "customer asked for documentation",
)

CLUSTER_GOVERNMENT_CONTRACT: Tuple[str, ...] = (
    "government customer security",
    "government contract cybersecurity",
    "defense subcontractor requirements",
    "subcontractor requirements security",
    "contract flowdown security",
)

CLUSTER_DOCUMENTATION_BURDEN: Tuple[str, ...] = (
    "security paperwork",
    "compliance paperwork overwhelmed",
    "documentation request customer",
    "evidence request",
    "what documents do we need",
    "need cybersecurity policies",
    "need policies customer",
    "what paperwork is needed",
    "partial documentation",
    "partial paperwork compliance",
)

CLUSTER_CYBERSECURITY_QUESTIONNAIRE: Tuple[str, ...] = (
    "security questionnaire overwhelmed",
    "customer security questionnaire",
    "vendor security questionnaire",
    "cyber insurance questionnaire",
    "security forms help",
)

CLUSTER_SUPPLIER_REQUIREMENTS: Tuple[str, ...] = (
    "supplier onboarding security",
    "supplier requirements security",
    "supplier compliance requirements",
    "vendor security requirements",
)

CLUSTER_CYBER_INSURANCE: Tuple[str, ...] = (
    "cyber insurance requirements",
    "cyber insurance questionnaire",
    "insurance security requirements",
)

CLUSTER_MFA_SECURITY: Tuple[str, ...] = (
    "we got asked for MFA",
    "MFA requirements contract",
    "MFA requirements customer",
    "multi factor authentication requirements",
)

CLUSTER_SUBCONTRACTOR: Tuple[str, ...] = (
    "subcontractor compliance",
    "subcontractor security requirements",
    "flowdown requirements security",
    "prime contractor requirements small business",
)

DISCOVERY_CLUSTERS: Dict[str, Tuple[str, ...]] = {
    "direct_cmmc": CLUSTER_DIRECT_CMMC,
    "operational_security": CLUSTER_OPERATIONAL_SECURITY,
    "vendor_pressure": CLUSTER_VENDOR_PRESSURE,
    "government_contract": CLUSTER_GOVERNMENT_CONTRACT,
    "documentation_burden": CLUSTER_DOCUMENTATION_BURDEN,
    "cybersecurity_questionnaire": CLUSTER_CYBERSECURITY_QUESTIONNAIRE,
    "supplier_requirements": CLUSTER_SUPPLIER_REQUIREMENTS,
    "cyber_insurance_pressure": CLUSTER_CYBER_INSURANCE,
    "mfa_security_requirements": CLUSTER_MFA_SECURITY,
    "subcontractor_compliance": CLUSTER_SUBCONTRACTOR,
}

CLUSTER_ORDER = tuple(DISCOVERY_CLUSTERS.keys())

# Prefer ecosystems for subreddit-targeted searches per cluster
CLUSTER_ECOSYSTEM_HINTS: Dict[str, Tuple[str, ...]] = {
    "direct_cmmc": ("government_contracting",),
    "operational_security": ("it_operations", "small_business"),
    "vendor_pressure": ("government_contracting", "small_business"),
    "government_contract": ("government_contracting",),
    "documentation_burden": ("small_business", "security_burden"),
    "cybersecurity_questionnaire": ("security_burden", "small_business"),
    "supplier_requirements": ("small_business", "government_contracting"),
    "cyber_insurance_pressure": ("small_business", "security_burden"),
    "mfa_security_requirements": ("it_operations", "small_business"),
    "subcontractor_compliance": ("government_contracting",),
}

CLUSTER_CONTENT_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(cmmc|dfars|nist\s*800|sprs)\b", "direct_cmmc"),
    (r"\b(prime contractor|vendor questionnaire|vendor onboarding)\b", "vendor_pressure"),
    (r"\b(supplier onboarding|supplier requirements)\b", "supplier_requirements"),
    (r"\b(government (contract|customer)|federal contract)\b", "government_contract"),
    (r"\b(subcontractor|flowdown)\b", "subcontractor_compliance"),
    (r"\b(security questionnaire|questionnaire)\b", "cybersecurity_questionnaire"),
    (r"\b(cyber insurance|insurance questionnaire)\b", "cyber_insurance_pressure"),
    (r"\b(\bmfa\b|multi.?factor)\b", "mfa_security_requirements"),
    (r"\b(paperwork|documentation request|evidence request|need policies)\b", "documentation_burden"),
    (r"\b(security requirements|it compliance|security assessment|security controls)\b", "operational_security"),
    (r"\b(we got asked|what do they need|not sure what applies|customer sent)\b", "operational_security"),
]

MIN_CLUSTER_DIVERSITY = 6
MIN_SUBREDDIT_DIVERSITY = 5
MIN_ECOSYSTEM_DIVERSITY = 3
DEFAULT_MAX_GLOBAL_QUERIES = 14
DEFAULT_MAX_SUBREDDIT_SEARCHES = 12
QUERIES_PER_CLUSTER_CAP = 2
SUBREDDITS_PER_ECOSYSTEM_CAP = 2


def default_cluster_weights() -> Dict[str, float]:
    return {c: 1.0 for c in CLUSTER_ORDER}


def default_ecosystem_weights() -> Dict[str, float]:
    return {e: 1.0 for e in ECOSYSTEM_ORDER}


def build_cycle_queries(
    *,
    learning_state: Optional[Dict[str, Any]] = None,
    max_queries: int = DEFAULT_MAX_GLOBAL_QUERIES,
    min_clusters: int = MIN_CLUSTER_DIVERSITY,
) -> List[Dict[str, str]]:
    """Global Reddit search queries with cluster tags."""
    state = learning_state or {}
    weights = dict(default_cluster_weights())
    for k, v in (state.get("discovery_cluster_weights") or {}).items():
        if k in weights:
            weights[k] = float(v)

    selected: List[Dict[str, str]] = []
    used: set = set()

    for cluster in CLUSTER_ORDER:
        if len({s["discovery_source_cluster"] for s in selected}) >= min_clusters:
            if cluster in {s["discovery_source_cluster"] for s in selected}:
                continue
        for q in sorted(DISCOVERY_CLUSTERS[cluster], key=lambda x: -weights.get(cluster, 1.0)):
            if q.lower() not in used:
                selected.append({"query": q, "discovery_source_cluster": cluster})
                used.add(q.lower())
                break

    for cluster in CLUSTER_ORDER:
        if len(selected) >= max_queries:
            break
        n = sum(1 for s in selected if s["discovery_source_cluster"] == cluster)
        if n >= QUERIES_PER_CLUSTER_CAP:
            continue
        for q in DISCOVERY_CLUSTERS[cluster]:
            if len(selected) >= max_queries or n >= QUERIES_PER_CLUSTER_CAP:
                break
            if q.lower() in used:
                continue
            selected.append({"query": q, "discovery_source_cluster": cluster})
            used.add(q.lower())
            n += 1

    return selected[:max_queries]


def build_subreddit_search_plan(
    *,
    learning_state: Optional[Dict[str, Any]] = None,
    max_searches: int = DEFAULT_MAX_SUBREDDIT_SEARCHES,
    min_ecosystems: int = MIN_ECOSYSTEM_DIVERSITY,
) -> List[Dict[str, str]]:
    """Subreddit-scoped searches across ecosystems."""
    state = learning_state or {}
    eweights = dict(default_ecosystem_weights())
    for k, v in (state.get("discovery_ecosystem_weights") or {}).items():
        if k in eweights:
            eweights[k] = float(v)

    cweights = dict(default_cluster_weights())
    for k, v in (state.get("discovery_cluster_weights") or {}).items():
        if k in cweights:
            cweights[k] = float(v)

    plan: List[Dict[str, str]] = []
    used_pairs: set = set()

    def add(sub: str, query: str, cluster: str, ecosystem: str) -> None:
        key = (sub.lower(), query.lower())
        if key in used_pairs or len(plan) >= max_searches:
            return
        used_pairs.add(key)
        plan.append(
            {
                "subreddit": sub,
                "query": query,
                "discovery_source_cluster": cluster,
                "discovery_ecosystem": ecosystem,
            }
        )

    ecosystems_used: set = set()
    for ecosystem in sorted(ECOSYSTEM_ORDER, key=lambda e: -eweights.get(e, 1.0)):
        if len(ecosystems_used) >= min_ecosystems and ecosystem in ecosystems_used:
            continue
        subs = list(DISCOVERY_ECOSYSTEMS.get(ecosystem, ()))[:SUBREDDITS_PER_ECOSYSTEM_CAP]
        for sub in subs:
            for cluster in sorted(CLUSTER_ORDER, key=lambda c: -cweights.get(c, 1.0)):
                hints = CLUSTER_ECOSYSTEM_HINTS.get(cluster, ECOSYSTEM_ORDER)
                if ecosystem not in hints and cluster not in ("direct_cmmc", "government_contract", "subcontractor_compliance"):
                    continue
                q = DISCOVERY_CLUSTERS[cluster][0]
                add(sub, q, cluster, ecosystem)
                ecosystems_used.add(ecosystem)
                if len(plan) >= max_searches:
                    return plan

    for ecosystem in ECOSYSTEM_ORDER:
        if len(plan) >= max_searches:
            break
        for sub in DISCOVERY_ECOSYSTEMS.get(ecosystem, ())[:SUBREDDITS_PER_ECOSYSTEM_CAP]:
            for cluster in ("operational_security", "vendor_pressure", "documentation_burden"):
                if len(plan) >= max_searches:
                    break
                q = DISCOVERY_CLUSTERS[cluster][len(plan) % len(DISCOVERY_CLUSTERS[cluster])]
                add(sub, q, cluster, ecosystem)

    return plan[:max_searches]


def build_cycle_discovery_plan(
    learning_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "global_queries": build_cycle_queries(learning_state=learning_state),
        "subreddit_searches": build_subreddit_search_plan(learning_state=learning_state),
    }


def all_expanded_queries() -> List[str]:
    out: List[str] = []
    for cluster in CLUSTER_ORDER:
        out.extend(DISCOVERY_CLUSTERS[cluster])
    return out


def all_ecosystem_subreddits() -> List[str]:
    seen: set = set()
    out: List[str] = []
    for subs in DISCOVERY_ECOSYSTEMS.values():
        for s in subs:
            sl = s.lower()
            if sl not in seen:
                seen.add(sl)
                out.append(s)
    return out


def classify_discovery_cluster(title: str, body: str = "", fallback: str = "operational_security") -> str:
    blob = f"{title}\n{body}".lower()
    for pattern, cluster in CLUSTER_CONTENT_PATTERNS:
        if re.search(pattern, blob, re.I):
            return cluster
    return fallback


def classify_discovery_ecosystem(subreddit: str) -> str:
    sub = (subreddit or "").lower()
    for eco, subs in DISCOVERY_ECOSYSTEMS.items():
        if sub in {s.lower() for s in subs}:
            return eco
    return "small_business"


def apply_post_cluster_metadata(post: Dict[str, Any]) -> Dict[str, Any]:
    cluster = post.get("discovery_source_cluster") or classify_discovery_cluster(
        post.get("title", ""),
        post.get("selftext", ""),
    )
    post["discovery_source_cluster"] = cluster
    post["discovery_ecosystem"] = post.get("discovery_ecosystem") or classify_discovery_ecosystem(
        post.get("subreddit", "")
    )
    return post


def infer_burden_profile(
    post: Dict[str, Any],
    classification: Optional[Dict[str, Any]] = None,
    qualification: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """UI-facing burden context — does not affect prey gates."""
    cls = classification or {}
    qual = qualification or {}
    prob = qual.get("acquisition_probability") or {}
    cluster = post.get("discovery_source_cluster") or "operational_security"

    category_map = {
        "direct_cmmc": "Compliance framework confusion",
        "operational_security": "Operational security burden",
        "vendor_pressure": "Vendor pressure",
        "government_contract": "Government contract pressure",
        "documentation_burden": "Documentation burden",
        "cybersecurity_questionnaire": "Security questionnaire",
        "supplier_requirements": "Supplier requirements",
        "cyber_insurance_pressure": "Cyber insurance pressure",
        "mfa_security_requirements": "MFA / access requirements",
        "subcontractor_compliance": "Subcontractor compliance",
    }
    burden_category = category_map.get(cluster, "Operational burden")

    title = post.get("title", "")
    body = post.get("selftext", "")
    blob = f"{title}\n{body}".lower()
    context_bits: List[str] = []
    if re.search(r"prime contractor|vendor|supplier|questionnaire", blob):
        context_bits.append("Third-party requirements")
    if re.search(r"government|federal|defense|contract", blob):
        context_bits.append("Government/contract context")
    if re.search(r"small business|subcontractor", blob):
        context_bits.append("Small business operator")
    if re.search(r"mfa|insurance|audit|assessment", blob):
        context_bits.append("Security program gap")

    paperwork: List[str] = []
    if re.search(r"questionnaire|form", blob):
        paperwork.append("Questionnaire likely")
    if re.search(r"polic(y|ies)|evidence|document", blob):
        paperwork.append("Policies/evidence likely")
    if re.search(r"spreadsheet|partial|messy", blob):
        paperwork.append("Partial records likely")
    if cls.get("burden_score", 0) >= 40:
        paperwork.append("Burden signals present")

    badges = list(prob.get("prey_reasons") or []) + list(prob.get("soft_burden_badges") or [])
    cluster_badges = {
        "vendor_pressure": "Vendor pressure",
        "government_contract": "Government contract pressure",
        "documentation_burden": "Documentation burden",
        "cybersecurity_questionnaire": "Security questionnaire",
    }
    if cluster in cluster_badges and cluster_badges[cluster] not in badges:
        badges.insert(0, cluster_badges[cluster])

    return {
        "burden_category": burden_category,
        "operational_context": "; ".join(context_bits[:4]) or "Operational compliance pressure",
        "likely_paperwork_indicators": paperwork[:4],
        "burden_badges": badges[:8],
        "discovery_source_cluster": cluster,
        "discovery_ecosystem": post.get("discovery_ecosystem", ""),
    }


def ensure_semantic_diversity(
    posts: List[Dict[str, Any]],
    *,
    min_clusters: int = MIN_CLUSTER_DIVERSITY,
    max_posts: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return _interleave_posts(posts, key_fn=lambda p: p.get("discovery_source_cluster") or "unknown", max_posts=max_posts)


def ensure_subreddit_diversity(
    posts: List[Dict[str, Any]],
    *,
    min_subreddits: int = MIN_SUBREDDIT_DIVERSITY,
    max_posts: Optional[int] = None,
) -> List[Dict[str, Any]]:
    diversified = _interleave_posts(
        posts,
        key_fn=lambda p: (p.get("subreddit") or "unknown").lower(),
    )
    return ensure_semantic_diversity(diversified, min_clusters=MIN_CLUSTER_DIVERSITY, max_posts=max_posts)


def _interleave_posts(
    posts: List[Dict[str, Any]],
    *,
    key_fn,
    max_posts: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if not posts:
        return posts
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for p in posts:
        buckets.setdefault(key_fn(p), []).append(p)
    keys = list(buckets.keys())
    if len(keys) <= 1:
        out = posts
    else:
        out = []
        idx = {k: 0 for k in keys}
        while len(out) < len(posts):
            added = False
            for k in keys:
                lst = buckets[k]
                i = idx[k]
                if i < len(lst):
                    out.append(lst[i])
                    idx[k] += 1
                    added = True
            if not added:
                break
    if max_posts is not None:
        return out[:max_posts]
    return out


def record_cluster_outcome(learning_state: Dict[str, Any], cluster: str, outcome: str) -> Dict[str, Any]:
    stats = learning_state.setdefault("discovery_cluster_stats", {})
    row = stats.setdefault(cluster, {"queued": 0, "operator_approved": 0, "uploads_completed": 0})
    if outcome in row:
        row[outcome] = int(row.get(outcome, 0)) + 1
    weights = learning_state.setdefault("discovery_cluster_weights", default_cluster_weights())
    approved = int(row.get("operator_approved", 0))
    uploads = int(row.get("uploads_completed", 0))
    if approved + uploads >= 2:
        weights[cluster] = min(1.5, float(weights.get(cluster, 1.0)) + 0.05)
    elif int(row.get("queued", 0)) - approved > approved * 3 and int(row.get("queued", 0)) > 5:
        weights[cluster] = max(0.7, float(weights.get(cluster, 1.0)) - 0.03)
    return learning_state


def record_ecosystem_outcome(learning_state: Dict[str, Any], ecosystem: str, outcome: str) -> Dict[str, Any]:
    stats = learning_state.setdefault("discovery_ecosystem_stats", {})
    row = stats.setdefault(ecosystem, {"queued": 0, "operator_approved": 0, "uploads_completed": 0})
    if outcome in row:
        row[outcome] = int(row.get(outcome, 0)) + 1
    weights = learning_state.setdefault("discovery_ecosystem_weights", default_ecosystem_weights())
    approved = int(row.get("operator_approved", 0))
    uploads = int(row.get("uploads_completed", 0))
    if approved + uploads >= 2:
        weights[ecosystem] = min(1.5, float(weights.get(ecosystem, 1.0)) + 0.05)
    return learning_state


# Back-compat alias
security_questionnaire = "cybersecurity_questionnaire"
