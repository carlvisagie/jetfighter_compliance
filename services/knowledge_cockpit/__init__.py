"""Solo Operator Knowledge Cockpit — canonical in-repo knowledge layer."""
from .context_retrieval import (
    context_bundle,
    explain,
    get_dashboard,
    search_all,
)
from .operational_explainer import explain_concept, explain_text

__all__ = [
    "search_all",
    "explain",
    "explain_concept",
    "explain_text",
    "get_dashboard",
    "context_bundle",
]
