"""
Discovery expansion — find operational burden without explicit CMMC/DFARS/NIST vocabulary.

Expands search candidates; prey/predator/soft_burden filters retain precision.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Layer 1: direct compliance framework language
CLUSTER_DIRECT_CMMC: Tuple[str, ...] = (
    "CMMC confusion",
    "DFARS confusion",
    "NIST 800-171 help",
    "CMMC level which",
    "SPRS score help",
)

# Layer 2: operational compliance language
CLUSTER_OPERATIONAL_SECURITY: Tuple[str, ...] = (
    "customer security requirements",
    "cybersecurity requirements small business",
    "security requirements government contract",
    "IT compliance requirements",
    "MFA requirements contract",
    "security assessment small business",
)

CLUSTER_VENDOR_PRESSURE: Tuple[str, ...] = (
    "vendor onboarding security",
    "vendor assessment requirements",
    "supplier onboarding security",
    "prime contractor security requirements",
    "prime contractor sent questionnaire",
)

CLUSTER_GOVERNMENT_CONTRACT: Tuple[str, ...] = (
    "government contract cybersecurity",
    "government customer security",
    "defense subcontractor requirements",
    "contract flowdown security",
)

CLUSTER_DOCUMENTATION_BURDEN: Tuple[str, ...] = (
    "compliance paperwork overwhelmed",
    "security paperwork help",
    "documentation request customer",
    "evidence request compliance",
    "we got asked for documents",
    "need cybersecurity policies",
)

CLUSTER_SECURITY_QUESTIONNAIRE: Tuple[str, ...] = (
    "security questionnaire overwhelmed",
    "customer security questionnaire",
    "vendor security questionnaire",
    "questionnaire not sure what",
)

# Layer 3: pain-driven semantic (may not name frameworks)
CLUSTER_PAIN_SEMANTIC: Tuple[str, ...] = (
    "what do they need from us security",
    "we got asked for security",
    "not sure what applies requirements",
    "customer sent security form",
    "small business security audit",
    "cyber insurance requirements",
    "requirements list security",
)

DISCOVERY_CLUSTERS: Dict[str, Tuple[str, ...]] = {
    "direct_cmmc": CLUSTER_DIRECT_CMMC,
    "operational_security": CLUSTER_OPERATIONAL_SECURITY,
    "vendor_pressure": CLUSTER_VENDOR_PRESSURE,
    "government_contract": CLUSTER_GOVERNMENT_CONTRACT,
    "documentation_burden": CLUSTER_DOCUMENTATION_BURDEN,
    "security_questionnaire": CLUSTER_SECURITY_QUESTIONNAIRE,
    "pain_semantic": CLUSTER_PAIN_SEMANTIC,
}

CLUSTER_ORDER = (
    "direct_cmmc",
    "operational_security",
    "vendor_pressure",
    "government_contract",
    "documentation_burden",
    "security_questionnaire",
    "pain_semantic",
)

# Classify discovered post text into cluster (for UI / learning)
CLUSTER_CONTENT_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(cmmc|dfars|nist\s*800|sprs)\b", "direct_cmmc"),
    (r"\b(prime contractor|vendor onboarding|supplier onboarding|vendor assessment)\b", "vendor_pressure"),
    (r"\b(government (contract|customer)|defense subcontractor|flowdown)\b", "government_contract"),
    (r"\b(security questionnaire|vendor questionnaire|customer questionnaire)\b", "security_questionnaire"),
    (r"\b(paperwork|documentation request|evidence request|policies)\b", "documentation_burden"),
    (r"\b(cyber insurance|mfa|it requirements|security requirements|cybersecurity requirements)\b", "operational_security"),
    (r"\b(we got asked|what do they need|not sure what applies|customer sent)\b", "pain_semantic"),
]

MIN_CLUSTER_DIVERSITY = 4
DEFAULT_MAX_QUERIES_PER_CYCLE = 18
QUERIES_PER_CLUSTER_CAP = 3


def default_cluster_weights() -> Dict[str, float]:
    return {c: 1.0 for c in CLUSTER_ORDER}


def build_cycle_queries(
    *,
    learning_state: Optional[Dict[str, Any]] = None,
    max_queries: int = DEFAULT_MAX_QUERIES_PER_CYCLE,
    min_clusters: int = MIN_CLUSTER_DIVERSITY,
) -> List[Dict[str, str]]:
    """
    Build a diverse query list for one discovery cycle.
    Returns [{query, discovery_source_cluster}, ...]
    """
    state = learning_state or {}
    weights = dict(default_cluster_weights())
    learned = (state.get("discovery_cluster_weights") or {})
    for k, v in learned.items():
        if k in weights:
            weights[k] = float(v)

    selected: List[Dict[str, str]] = []
    used_queries: set = set()

    # Round 1: at least one query per cluster (diversity floor)
    for cluster in CLUSTER_ORDER:
        if len({s["discovery_source_cluster"] for s in selected}) >= min_clusters and cluster in {
            s["discovery_source_cluster"] for s in selected
        }:
            continue
        queries = list(DISCOVERY_CLUSTERS[cluster])
        queries.sort(key=lambda q: -weights.get(cluster, 1.0))
        for q in queries[:1]:
            if q.lower() not in used_queries:
                selected.append({"query": q, "discovery_source_cluster": cluster})
                used_queries.add(q.lower())
                break

    # Round 2: fill to max with weighted extra picks per cluster
    for cluster in CLUSTER_ORDER:
        if len(selected) >= max_queries:
            break
        count_in_cluster = sum(1 for s in selected if s["discovery_source_cluster"] == cluster)
        if count_in_cluster >= QUERIES_PER_CLUSTER_CAP:
            continue
        for q in DISCOVERY_CLUSTERS[cluster]:
            if len(selected) >= max_queries:
                break
            if q.lower() in used_queries:
                continue
            if count_in_cluster >= QUERIES_PER_CLUSTER_CAP:
                break
            selected.append({"query": q, "discovery_source_cluster": cluster})
            used_queries.add(q.lower())
            count_in_cluster += 1

    return selected[:max_queries]


def all_expanded_queries() -> List[str]:
    out: List[str] = []
    for cluster in CLUSTER_ORDER:
        out.extend(DISCOVERY_CLUSTERS[cluster])
    return out


def classify_discovery_cluster(title: str, body: str = "", fallback: str = "pain_semantic") -> str:
    """Infer discovery cluster from post content."""
    blob = f"{title}\n{body}".lower()
    for pattern, cluster in CLUSTER_CONTENT_PATTERNS:
        if re.search(pattern, blob, re.I):
            return cluster
    return fallback


def apply_post_cluster_metadata(post: Dict[str, Any]) -> Dict[str, Any]:
    """Attach discovery_source_cluster from search tag or content."""
    cluster = post.get("discovery_source_cluster") or classify_discovery_cluster(
        post.get("title", ""),
        post.get("selftext", ""),
        fallback=post.get("search_cluster", "pain_semantic"),
    )
    post["discovery_source_cluster"] = cluster
    return post


def ensure_semantic_diversity(
    posts: List[Dict[str, Any]],
    *,
    min_clusters: int = MIN_CLUSTER_DIVERSITY,
    max_posts: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Prefer a diverse mix of discovery clusters in the candidate set.
    Does not weaken prey filtering — only shapes which discovered posts are processed first.
    """
    if not posts:
        return posts

    by_cluster: Dict[str, List[Dict[str, Any]]] = {}
    for p in posts:
        c = p.get("discovery_source_cluster") or "pain_semantic"
        by_cluster.setdefault(c, []).append(p)

    clusters_present = list(by_cluster.keys())
    if len(clusters_present) <= 1:
        out = posts
    else:
        out = []
        indices = {c: 0 for c in clusters_present}
        while len(out) < len(posts):
            added = False
            for c in clusters_present:
                lst = by_cluster[c]
                idx = indices[c]
                if idx < len(lst):
                    out.append(lst[idx])
                    indices[c] += 1
                    added = True
            if not added:
                break

    if max_posts is not None:
        return out[:max_posts]
    return out


def record_cluster_outcome(
    learning_state: Dict[str, Any],
    cluster: str,
    outcome: str,
) -> Dict[str, Any]:
    """Track which discovery clusters convert (approved, uploads, etc.)."""
    stats = learning_state.setdefault("discovery_cluster_stats", {})
    row = stats.setdefault(cluster, {"queued": 0, "operator_approved": 0, "uploads_completed": 0})
    if outcome in row:
        row[outcome] = int(row.get(outcome, 0)) + 1
    weights = learning_state.setdefault("discovery_cluster_weights", default_cluster_weights())
    approved = int(row.get("operator_approved", 0))
    uploads = int(row.get("uploads_completed", 0))
    if approved + uploads >= 2:
        weights[cluster] = min(1.5, float(weights.get(cluster, 1.0)) + 0.05)
    denied = int(row.get("queued", 0)) - approved
    if denied > approved * 3 and denied > 5:
        weights[cluster] = max(0.7, float(weights.get(cluster, 1.0)) - 0.03)
    return learning_state
