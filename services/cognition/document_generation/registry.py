import os
from typing import Dict, Any
from services.cognition.document_generation.schemas import GeneratedDocument

def build_generated_document_path(project_id: str, document_id: str) -> str:
    return f"data/projects/{project_id}/generated/{document_id}.md"

def generated_document_to_markdown(document: GeneratedDocument) -> str:
    return document.content_markdown

def build_document_registry_event(document: GeneratedDocument, project_id: str) -> Dict[str, Any]:
    return {
        "event_type": "document_generated",
        "project_id": project_id,
        "doc_id": document.doc_id,
        "doc_type": document.doc_type,
        "provenance_count": len(document.provenance)
    }